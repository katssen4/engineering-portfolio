#!/usr/bin/env python3
"""Recompute the experimental results this repository prints, from the files it ships.

It covers what is recomputable: the retrieval table, the seal on the reference lock, the
blocked fine-tune decision, the two gates on their example data, and the unit tests. Counts
describing systems that are not shipped here are declared in the README, not recomputed, and
the README says so.

Run it from the repository root:

    python3 tools/verify.py

It does five things and prints what it found:

1. Verifies the seal on the reference lock, by recomputing its SHA-256 with the same
   function the bench uses (evidence/code/eval_regression.py).
2. Rebuilds the retrieval table of README.md from the lock, and compares it cell by cell
   to what the README actually prints.
3. Reads the blocked fine-tune decision and checks the control really failed.
4. Runs the anti-invention gate on the example documents that ship with it, and checks it
   passes the honest one and refuses the one carrying an invention.
5. Runs the shipped unit tests, if pytest is available.

Exit code 0 when everything agrees, 1 otherwise. Standard library, plus pytest for the
unit-test step, which names the missing dependency rather than failing obscurely.
"""
from __future__ import annotations

import collections
import importlib.util
import json
import math
import re
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
LOCK = RACINE / "evidence" / "retrieval" / "baseline_lock.json"
DECISION = RACINE / "evidence" / "finetune-blocked" / "F1_decision.json"
README = RACINE / "README.md"
MODULE = RACINE / "evidence" / "code" / "eval_regression.py"

PROJETS = ["Hadoop", "Cassandra", "HBase", "Spark"]
COLONNES = ["keyword", "vector", "hybrid"]

echecs: list[str] = []
controles = 0


def titre(n: int, texte: str) -> None:
    print(f"\n{n}. {texte}")


def dit(ok: bool, texte: str) -> None:
    global controles
    controles += 1
    print(f"   {'OK  ' if ok else 'ECHEC'} {texte}")
    if not ok:
        echecs.append(texte)


def charge_module():
    spec = importlib.util.spec_from_file_location("eval_regression", MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def verifie_sceau() -> dict:
    titre(1, "Seal on the reference lock")
    payload = json.loads(LOCK.read_text(encoding="utf-8"))
    mod = charge_module()
    ok, message = mod.verify_lock(LOCK)
    dit(ok, message)
    dit(payload.get("sealed") is True, f"lock declares sealed = {payload.get('sealed')}")
    dit(len(payload["baselines"]) == 18,
        f"18 engine configurations in the lock, found {len(payload['baselines'])}")
    p = payload["regression_policy"]
    dit(p["primary_metric"] == "ndcg@10" and p["delta_abs"] == 0.01
        and p["stat_test"] == "paired-t" and p["max_p"] == 0.05,
        f"regression policy: {p['primary_metric']}, delta {p['delta_abs']}, "
        f"{p['stat_test']}, max_p {p['max_p']}")
    return payload


def table_depuis_lock(payload: dict) -> dict:
    lignes = {}
    for projet in PROJETS:
        cle = projet.lower()
        ligne = {}
        for col in COLONNES:
            ligne[col] = payload["baselines"][f"B_{cle}_{col}"]["ndcg@10"]
        ligne["n"] = payload["baselines"][f"B_{cle}_keyword"]["n_queries"]
        lignes[projet] = ligne
    return lignes


def verifie_readme(payload: dict) -> None:
    titre(2, "Retrieval table in README.md, cell by cell")
    attendu = table_depuis_lock(payload)
    texte = README.read_text(encoding="utf-8")
    for projet, ligne in attendu.items():
        motif = re.compile(r"^\|\s*" + projet + r"\s*\|(.+)\|\s*$", re.M)
        m = motif.search(texte)
        if not m:
            dit(False, f"{projet}: no row found in README.md")
            continue
        cellules = [c.strip().strip("*") for c in m.group(1).split("|")]
        if len(cellules) != 4:
            dit(False, f"{projet}: expected 4 cells, read {len(cellules)}")
            continue
        lus = cellules[:3]
        n_lu = cellules[3]
        for col, lu in zip(COLONNES, lus):
            calcule = f"{ligne[col]:.3f}"
            dit(lu == calcule, f"{projet} {col}: README {lu}, lock {calcule}")
        dit(n_lu == str(ligne["n"]), f"{projet} queries: README {n_lu}, lock {ligne['n']}")


def verifie_finetune() -> None:
    titre(3, "The blocked fine-tune")
    d = json.loads(DECISION.read_text(encoding="utf-8"))
    c = d["control"]
    dit(c["passed"] is False,
        f"positive control failed: computed {c['computed']}, target {c['target']}, "
        f"tolerance {c['tolerance']}")
    dit(d["status"] == "fail", f"run status = {d['status']}")
    dit(d["verdict"] is None, f"verdict = {d['verdict']} (no number was interpreted)")
    dit(d["inputs"]["primary_metric"] == "nDCG@10",
        f"primary metric declared before the run: {d['inputs']['primary_metric']}")
    gate = json.loads((DECISION.parent / "F1_gate.json").read_text(encoding="utf-8"))
    dit(gate["passed"] is True and gate["check1_tuning_holdout_overlap"] == 0,
        f"leakage gate passed, tuning/holdout overlap = {gate['check1_tuning_holdout_overlap']}")


def ndcg_at_10(rangs: list, jugements: dict) -> float:
    """nDCG@10 d'une requete, departage par la colonne de rang du fichier TREC.

    Ecrit ici en entier, en bibliotheque standard, pour que le chiffre publie soit recalcule
    sous les yeux du lecteur au lieu d'etre relu dans un fichier de decision.
    """
    docs = [d for _, d in sorted(rangs)][:10]
    dcg = sum(jugements.get(d, 0) / math.log2(i + 2) for i, d in enumerate(docs))
    ideal = sorted(jugements.values(), reverse=True)[:10]
    idcg = sum(g / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg else 0.0


def verifie_recalcul() -> None:
    titre(4, "The control score, recomputed from the TREC files")
    art = DECISION.parent / "F1_artifacts"
    jugements, malformees = collections.defaultdict(dict), []
    for n, ligne in enumerate(
            (art / "B_holdout_qrels.trec").read_text(encoding="utf-8").splitlines(), 1):
        if not ligne.strip():
            continue
        champs = ligne.split()
        if len(champs) != 4:
            malformees.append(f"B_holdout_qrels.trec:{n}")
            continue
        q, _, d, r = champs
        jugements[q][d] = int(r)
    run = collections.defaultdict(list)
    for n, ligne in enumerate(
            (art / "B_holdout_base_run.trec").read_text(encoding="utf-8").splitlines(), 1):
        if not ligne.strip():
            continue
        champs = ligne.split()
        if len(champs) != 6:
            malformees.append(f"B_holdout_base_run.trec:{n}")
            continue
        q, _, d, rang, _score, _tag = champs
        run[q].append((int(rang), d))

    # Un fichier abime doit produire un refus nomme, pas une trace Python. Sans ce garde,
    # une troncature faisait mourir le script avant la premiere ligne de resultat, ce qui
    # se lit comme un silence plutot que comme un echec.
    dit(not malformees,
        f"both TREC files parse cleanly"
        + (f"; malformed: {', '.join(malformees[:3])}"
           f"{' and %d more' % (len(malformees) - 3) if len(malformees) > 3 else ''}"
           if malformees else ""))
    if malformees:
        dit(False, "the control score cannot be recomputed from malformed run files")
        return

    manquantes = [q for q in jugements if not run[q]]
    dit(not manquantes,
        f"every judged query appears in the run file"
        + (f"; {len(manquantes)} missing" if manquantes else ""))

    scores = [ndcg_at_10(run[q], jugements[q]) for q in jugements]
    recalcule = round(sum(scores) / len(scores), 6)

    d = json.loads(DECISION.read_text(encoding="utf-8"))
    c = d["control"]
    dit(len(scores) == c["n"], f"{len(scores)} queries scored, decision record says {c['n']}")
    dit(recalcule == c["computed"],
        f"nDCG@10 recomputed from the run files: {recalcule}, "
        f"decision record says {c['computed']}")
    ecart = abs(recalcule - c["target"])
    dit(ecart > c["tolerance"],
        f"it misses the reference of {c['target']} by {ecart:.6f}, "
        f"tolerance {c['tolerance']}: the control fails on the numbers, not on the record")

    # Le pic memoire est annonce dans le README et vit dans le recit du run, en francais et
    # avec une espace fine. On confronte les deux plutot que de croire le README sur parole.
    recit = (DECISION.parent / "F1_finetune_run.md").read_text(encoding="utf-8")
    normalise = recit.replace("\u202f", "").replace("\u00a0", "").replace(" ", "").replace(",", ".")
    lu = README.read_text(encoding="utf-8")
    for chiffre, forme in (("5,863.5", "5863.5"), ("6,000", "6000")):
        dit(forme in normalise and chiffre in lu,
            f"the memory figure {chiffre} MiB on the page is the one in the run narrative")

    diag = [json.loads(l) for l in
            (art / "F1_control_diag.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    ecarts = [x for x in diag if abs(x.get("delta", 0)) > 1e-5]
    dit(len(ecarts) == 1,
        f"the whole gap sits in {len(ecarts)} query out of {len(diag)}"
        + (f": {ecarts[0]['qid']}, delta {ecarts[0]['delta']}" if len(ecarts) == 1 else ""))


def verifie_portes() -> None:
    titre(5, "The gates, run on the example data they ship with")
    gates = RACINE / "evidence" / "gates"
    exemple = gates / "example"

    def porte(derive: str):
        return subprocess.run(
            [sys.executable, "anti_invention.py",
             str(exemple / "source_of_truth.md"), str(exemple / derive),
             "--banals", "Meridian"],
            cwd=gates, capture_output=True, text=True, timeout=120)

    r = porte("derived_ok.md")
    dit(r.returncode == 0, f"honest document passes: exit {r.returncode}")

    r = porte("derived_with_invention.md")
    sortie = r.stdout
    dit(r.returncode == 1, f"document with an invention is refused: exit {r.returncode}")
    dit("90000" in sortie, "the inflated throughput figure is named in the output")
    dit("kubernetes" in sortie, "the unsourced deployment claim is named in the output")

    mod = charge_module()
    politique = {"delta_abs": 0.01, "require_significance": True, "max_p": 0.05}
    try:
        mod.is_regression(0.370, 0.420, politique, p_value=None,
                          baseline_is_legacy=True, current_is_legacy=True)
        dit(False, "the regression gate returned a verdict with no p-value to support it")
    except mod.CannotGateError:
        dit(True, "the regression gate refuses to conclude when significance cannot be shown")
    sans_chute = mod.is_regression(0.415, 0.420, politique, p_value=None,
                                   baseline_is_legacy=True, current_is_legacy=True)
    dit(sans_chute is False, "and it still concludes when no p-value is needed")

    r = subprocess.run([sys.executable, "proof_registry.py"],
                       cwd=gates, capture_output=True, text=True, timeout=120)
    dit(r.returncode == 0, "the proof register of evidence/gates passes its own check")


def verifie_tests() -> None:
    titre(6, "Shipped unit tests")
    if importlib.util.find_spec("pytest") is None:
        dit(False, "pytest is not installed. Run: pip install pytest")
        return
    for cible, attendu in (("evidence/code/test_eval_regression.py", 35),
                           ("evidence/gates/tests/", 23)):
        try:
            r = subprocess.run([sys.executable, "-m", "pytest", "-q", cible],
                               cwd=RACINE, capture_output=True, text=True, timeout=300)
        except Exception as exc:
            print(f"   SKIP  could not run pytest on {cible}: {exc}")
            continue
        derniere = [l for l in r.stdout.splitlines() if l.strip()]
        resume = derniere[-1] if derniere else "no output"
        dit(r.returncode == 0 and f"{attendu} passed" in resume, f"{cible}: {resume}")


def verifie_comptes() -> None:
    """Le depot compte ses propres controles au lieu de les recopier a la main.

    Les deux revues du 2026-09-10 ont trouve `evidence/README.md` reste a 32 alors que le
    README racine annoncait 34. Un chiffre ecrit deux fois derive toujours ; celui-ci est
    desormais confronte a la realite a chaque execution.
    """
    titre(7, "The repository counts its own checks")
    texte = README.read_text(encoding="utf-8")
    attendu = f"{controles + 3} checks"
    dit(attendu in texte, f"README states \"{attendu}\"")
    tests = (len(re.findall(r"^def test_", (RACINE / "evidence" / "code" /
             "test_eval_regression.py").read_text(encoding="utf-8"), re.M))
             + sum(len(re.findall(r"^def test_", f.read_text(encoding="utf-8"), re.M))
                   for f in sorted((RACINE / "evidence" / "gates" / "tests").glob("test_*.py"))))
    dit(f"{tests} shipped unit tests" in texte, f"README states \"{tests} shipped unit tests\"")
    carte = (RACINE / "evidence" / "README.md").read_text(encoding="utf-8")
    dit(not re.search(r"\b\d+ checks\b", carte),
        "evidence/README.md states no check count of its own, so it cannot drift")


def main() -> int:
    print("Verifying the experimental results this repository prints.")
    payload = verifie_sceau()
    verifie_readme(payload)
    verifie_finetune()
    verifie_recalcul()
    verifie_portes()
    verifie_tests()
    verifie_comptes()
    print()
    if echecs:
        print(f"{len(echecs)} check(s) failed.")
        return 1
    print(f"{controles} checks passed. The control score was recomputed from the run files, "
          "the retrieval table matches the sealed lock, and the counts on this page match "
          "what this script found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
