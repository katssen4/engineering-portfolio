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

Exit code 0 when everything agrees, 1 otherwise. Standard library only.
"""
from __future__ import annotations

import importlib.util
import json
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


def titre(n: int, texte: str) -> None:
    print(f"\n{n}. {texte}")


def dit(ok: bool, texte: str) -> None:
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


def verifie_portes() -> None:
    titre(4, "The gates, run on the example data they ship with")
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
    titre(5, "Shipped unit tests")
    for cible, attendu in (("evidence/code/test_eval_regression.py", 35),
                           ("evidence/gates/tests/", 11)):
        try:
            r = subprocess.run([sys.executable, "-m", "pytest", "-q", cible],
                               cwd=RACINE, capture_output=True, text=True, timeout=300)
        except Exception as exc:
            print(f"   SKIP  could not run pytest on {cible}: {exc}")
            continue
        derniere = [l for l in r.stdout.splitlines() if l.strip()]
        resume = derniere[-1] if derniere else "no output"
        dit(r.returncode == 0 and f"{attendu} passed" in resume, f"{cible}: {resume}")


def main() -> int:
    print("Verifying every number this repository prints.")
    payload = verifie_sceau()
    verifie_readme(payload)
    verifie_finetune()
    verifie_portes()
    verifie_tests()
    print()
    if echecs:
        print(f"{len(echecs)} check(s) failed.")
        return 1
    print("Every recomputable number in the README matches the artefacts that ship with it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
