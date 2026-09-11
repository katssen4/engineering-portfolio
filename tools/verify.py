#!/usr/bin/env python3
"""Recompute the experimental results this repository prints, from the files it ships.

It covers what is recomputable: the retrieval table, the seal on the reference lock, the
blocked fine-tune decision, the two gates on their example data, and the unit tests. Counts
describing systems that are not shipped here are declared in the README, not recomputed, and
the README says so.

Run it from the repository root:

    python3 tools/verify.py

It prints what it found, section by section. The number of sections is not written here:
this docstring announced five of them while the script ran eight, which is the documentation
drift that section 8 was written to catch elsewhere. Section 8 now counts the sections too.

1. Verifies the seal on the reference lock, by recomputing its SHA-256 with the same
   function the bench uses (evidence/code/eval_regression.py).
2. Rebuilds the retrieval table of README.md from the lock, and compares it cell by cell
   to what the README actually prints.
3. Reads the blocked fine-tune decision and checks the control really failed.
4. Recomputes the control score from the TREC files, and checks the run file and the
   judgements describe the same set of queries.
5. Runs the anti-invention gate and the proof register on the example documents that ship
   with them, and checks they pass the honest one and refuse the one carrying an invention.
6. Runs the governance mechanisms on their own example data, and checks they refuse.
7. Runs the shipped unit tests, if pytest is available.
8. Counts the checks, the sections and the tests, and compares them to what the README says.

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
    print(f"   {'OK  ' if ok else 'FAIL'} {texte}")
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
        try:
            r_int = int(rang)
        except ValueError:
            malformees.append(f"B_holdout_base_run.trec:{n}")
            continue
        # Les rangs de ce fichier commencent a 0, pas a 1. Le controle ecrit d'abord
        # exigeait un rang >= 1 et declarait les 310 requetes malformees : une convention
        # supposee au lieu d'etre lue. Seule la negativite est une vraie anomalie.
        if r_int < 0:
            malformees.append(f"B_holdout_base_run.trec:{n} (negative rank {r_int})")
            continue
        # Deux documents au meme rang font departager par identifiant, puisque `sorted`
        # prend le second element du tuple comme cle secondaire. Le verificateur
        # inventerait alors sa propre regle de tie-break, dans un fichier dont tout
        # l'interet est qu'un fine-tune y a ete bloque pour une difference de tie-break.
        if any(existant == r_int for existant, _ in run[q]):
            malformees.append(f"B_holdout_base_run.trec:{n} (duplicate rank {r_int} for {q})")
            continue
        run[q].append((r_int, d))

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

    # L'inverse se verifie aussi. Une requete presente dans le run et absente des jugements
    # ne participe pas au score et disparaissait en silence : le score reste juste, mais
    # l'entree du calcul cesse d'etre celle que le fichier declare.
    surnumeraires = sorted(set(run) - set(jugements))
    dit(not surnumeraires,
        f"the run file holds no query the qrels do not judge"
        + (f"; {len(surnumeraires)} extra, first {surnumeraires[0]}" if surnumeraires else ""))

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
    # Nuance relevee par une revue exterieure : ceci lit le diagnostic livre, il ne le
    # reconstruit pas depuis les donnees primitives. La metrique, elle, est bien recalculee.
    # Le diagnostic doit d'abord couvrir toutes les requetes de la decision. Sans ce
    # controle, un diagnostic tronque a 100 lignes dont une seule diverge passait aussi
    # bien qu'un diagnostic complet : « tout l'ecart sur une requete » n'a de sens que si
    # l'on sait sur combien de requetes on a regarde.
    dit(len(diag) == c["n"],
        f"the diagnostic covers {len(diag)} queries, the decision record says {c['n']}")
    dit(len(ecarts) == 1,
        f"shipped diagnostic puts the whole gap on {len(ecarts)} query out of {len(diag)}"
        + (f": {ecarts[0]['qid']}, delta {ecarts[0]['delta']}" if len(ecarts) == 1 else "")
        + " (read from the diagnostic, not recomputed per query)")


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
    titre(7, "Shipped unit tests")
    if importlib.util.find_spec("pytest") is None:
        dit(False, "pytest is not installed. Run: pip install pytest")
        return
    # Le nombre attendu est le nombre de cas executes, superieur au nombre de fonctions
    # `def test_` depuis que trois suites sont pilotees par table. Section 8 compte les
    # fonctions, celle-ci compte les cas : les deux chiffres sont differents et le
    # README dit lequel il annonce.
    for cible, attendu in (("evidence/code/test_eval_regression.py", 50),
                           ("evidence/gates/tests/", 58),
                           ("evidence/agent-governance/tests/", 60)):
        try:
            r = subprocess.run([sys.executable, "-m", "pytest", "-q", cible],
                               cwd=RACINE, capture_output=True, text=True, timeout=300)
        except Exception as exc:
            # Un groupe de tests qu'on ne peut pas lancer n'est pas un groupe qui passe.
            # Le SKIP precedent laissait le verificateur conclure malgre une suite non
            # executee, ce qui est un fail-open de l'outil de preuve lui-meme.
            dit(False, f"could not run pytest on {cible}: {exc}")
            continue
        derniere = [l for l in r.stdout.splitlines() if l.strip()]
        resume = derniere[-1] if derniere else "no output"
        dit(r.returncode == 0 and f"{attendu} passed" in resume, f"{cible}: {resume}")


def verifie_gouvernance() -> None:
    """Les deux refus de la couche gouvernance, exerces sur les donnees livrees."""
    titre(6, "The governance mechanisms, refusing on the data they ship with")
    gouv = RACINE / "evidence" / "agent-governance"
    sys.path.insert(0, str(gouv))
    try:
        import scope_guard as sg
    finally:
        sys.path.pop(0)

    avec = gouv / "example" / "prompt_avec_scope.md"
    code, _, _ = sg.run_check(avec, ["src/ingestion/connectors/metrics.py"])
    dit(code == sg.EXIT_CONFORME, f"a write inside the declared scope passes: exit {code}")

    code, hors, _ = sg.run_check(avec, ["src/auth/session.py"])
    dit(code == sg.EXIT_DEPASSEMENT and hors == ["src/auth/session.py"],
        f"a write outside it is refused: exit {code}, {hors}")

    code, _, niveau = sg.run_check(gouv / "example" / "prompt_sans_scope.md", ["x.py"])
    dit(code == sg.EXIT_SANS_PERIMETRE,
        f"a prompt declaring no scope is refused too, not waved through: exit {code}")

    patterns, niveau = sg.extract_scope_patterns(avec)
    dit("src/auth/" not in patterns and "src/ingestion/" not in patterns,
        f"the forbidden and read-only paths never become write permissions ({niveau})")

    r = subprocess.run([sys.executable, "-m", "pytest", "-q",
                        "evidence/agent-governance/tests/test_audit_chain.py"],
                       cwd=RACINE, capture_output=True, text=True, timeout=300)
    derniere = [l for l in r.stdout.splitlines() if l.strip()]
    dit(r.returncode == 0,
        f"the audit chain detects tampering: {derniere[-1] if derniere else 'no output'}")


def verifie_comptes() -> None:
    """Le depot compte ses propres controles au lieu de les recopier a la main.

    Les deux revues du 2026-09-10 ont trouve `evidence/README.md` reste a 32 alors que le
    README racine annoncait 34. Un chiffre ecrit deux fois derive toujours ; celui-ci est
    desormais confronte a la realite a chaque execution.
    """
    titre(8, "The repository counts its own checks")
    texte = README.read_text(encoding="utf-8")
    tests = sum(len(re.findall(r"^def test_", f.read_text(encoding="utf-8"), re.M))
                for f in sorted(RACINE.rglob("evidence/**/test_*.py")))
    dit(f"{tests} shipped unit tests" in texte, f"README states \"{tests} shipped unit tests\"")

    # Le docstring de ce fichier annoncait cinq etapes pour huit sections. Un compteur
    # ecrit a la main derive ; celui-ci se compte lui-meme.
    moi = Path(__file__).read_text(encoding="utf-8")
    sections = {int(m) for m in re.findall(r"^    titre\((\d+),", moi, re.M)}
    annoncees = {int(m) for m in re.findall(r"^(\d+)\. ", __doc__ or "", re.M)}
    dit(sections == annoncees,
        f"the docstring lists the {len(sections)} sections this script actually runs"
        + (f"; runs {sorted(sections)}, lists {sorted(annoncees)}"
           if sections != annoncees else ""))
    carte = (RACINE / "evidence" / "README.md").read_text(encoding="utf-8")
    dit(not re.search(r"\b\d+ checks\b", carte),
        "evidence/README.md states no check count of its own, so it cannot drift")

    # Un mecanisme dont le dossier de preuves existe ne doit pas etre annonce comme non
    # livre. Le commit du 2026-09-11 l'avait dit lui-meme : « le commit precedent a echoue
    # en silence sur cette partie », et rien ne l'attrapait. Une reecriture de section qui
    # rate laisse une page qui contredit ses propres fichiers, et personne ne le voit.
    livres = {"scope guard": "evidence/agent-governance/scope_guard.py",
              "audit chain": "evidence/agent-governance/audit_chain.py",
              "anti-invention": "evidence/gates/anti_invention.py",
              "proof register": "evidence/gates/proof_registry.py"}
    section = texte.split("**What is declared and not shipped.**")
    contredits = []
    if len(section) > 1:
        # On ne lit que le paragraphe des non-livres, pas la page entiere.
        paragraphe = section[1].split("\n\n")[0].lower()
        for nom, chemin in livres.items():
            if nom in paragraphe and (RACINE / chemin).exists():
                contredits.append(f"{nom} is called not shipped, {chemin} exists")
    dit(not contredits,
        "nothing the README calls unshipped has a file in the repository"
        + (f"; {contredits[0]}" if contredits else ""))

    # Une revue exterieure a trouve un chemin cite dans un docstring et absent du depot.
    # Les chemins internes cites en `backticks` sont donc confrontes au disque.
    morts = []
    for f in sorted(RACINE.rglob("*.md")) + sorted(RACINE.rglob("*.py")):
        # Exclus : les ADR et les fichiers de `evidence/code/`, copies verbatim du banc.
        # Ils citent leur arbre d'origine, et les retoucher effacerait leur provenance.
        if ".git" in f.parts or "decisions" in f.parts or "code" in f.parts:
            continue
        for m in re.finditer(r"`((?:evidence|tools)/[A-Za-z0-9_./-]+)`",
                             f.read_text(encoding="utf-8", errors="replace")):
            if not (RACINE / m.group(1)).exists():
                morts.append(f"{f.relative_to(RACINE)} cites {m.group(1)}")
    dit(not morts, "every internal path quoted in the docs exists"
        + (f"; dead: {morts[0]}" if morts else ""))

    # En dernier, parce qu'il se compte lui-meme : l'ecart etait code en dur et derivait
    # des qu'un controle s'ajoutait a cette section.
    attendu = f"{controles + 1} checks"
    dit(attendu in texte, f"README states \"{attendu}\"")


def sans_trace(nom: str, fonction, *args):
    """Execute une section et convertit toute exception en echec nomme.

    Un verificateur qui meurt sur une trace Python ressemble a un verificateur silencieux :
    la trace sort avant la premiere ligne de resultat, et un lecteur presse la lit comme une
    erreur d'environnement. Une piece manquante ou abimee doit produire un FAIL nomme, pas
    un arret. Trouve a l'audit du 2026-09-11 sur quatre artefacts differents.
    """
    try:
        return fonction(*args)
    except Exception as exc:
        print(f"\n!  {nom} could not run")
        dit(False, f"{type(exc).__name__}: {exc}")
        return None


def main() -> int:
    print("Verifying the experimental results this repository prints.")
    payload = sans_trace("the reference lock", verifie_sceau)
    if payload is not None:
        sans_trace("the retrieval table", verifie_readme, payload)
    else:
        dit(False, "the retrieval table cannot be checked without the reference lock")
    sans_trace("the fine-tune decision", verifie_finetune)
    sans_trace("the recomputed control", verifie_recalcul)
    sans_trace("the gates", verifie_portes)
    sans_trace("the governance mechanisms", verifie_gouvernance)
    sans_trace("the unit tests", verifie_tests)
    sans_trace("the self-count", verifie_comptes)
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
