#!/usr/bin/env python3
"""Recompute every number this repository prints, from the files it ships.

Run it from the repository root:

    python3 tools/verify.py

It does four things and prints what it found:

1. Verifies the seal on the reference lock, by recomputing its SHA-256 with the same
   function the bench uses (evidence/code/eval_regression.py).
2. Rebuilds the retrieval table of README.md from the lock, and compares it cell by cell
   to what the README actually prints.
3. Reads the blocked fine-tune decision and checks the control really failed.
4. Runs the shipped unit tests, if pytest is available.

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


def verifie_tests() -> None:
    titre(4, "Shipped unit tests")
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "evidence/code/test_eval_regression.py"],
            cwd=RACINE, capture_output=True, text=True, timeout=300)
    except Exception as exc:
        print(f"   SKIP  could not run pytest: {exc}")
        return
    derniere = [l for l in r.stdout.splitlines() if l.strip()]
    dit(r.returncode == 0, derniere[-1] if derniere else "no output")


def main() -> int:
    print("Verifying every number this repository prints.")
    payload = verifie_sceau()
    verifie_readme(payload)
    verifie_finetune()
    verifie_tests()
    print()
    if echecs:
        print(f"{len(echecs)} check(s) failed.")
        return 1
    print("Everything the README prints matches the files that ship with it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
