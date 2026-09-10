#!/usr/bin/env python3
"""Vérifie le dossier de preuve du domaine. Usage : preuves.py [--detail]

Ce que ce script empêche. Un registre de preuves est le genre de document qui
part bien et devient décoratif en un mois : les énoncés restent, les preuves
qu'ils citent disparaissent, et plus personne ne relit. Il suffit alors d'un
document qui *affirme* être un dossier de preuve pour croire qu'on en a un.

Trois des cinq catégories sont donc **vérifiables mécaniquement** :

    [TESTED]     cite un test qui doit exister dans tests/
    [INVARIANT]  cite un garde-fou dont le texte doit exister dans le code
    [OBSERVED]   cite une date, qui doit être une date

Les deux autres ne le sont pas, et c'est leur raison d'être :

    [DESIGN]     affirmé par construction, jamais vérifié — à lire comme tel
    [KNOWN GAP]  manque déclaré, avec ce qu'il faudrait pour le combler

Un énoncé sans catégorie, ou dont la preuve a disparu, fait échouer ce contrôle.
Phase S7.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parent
REGISTRE = RACINE / "PREUVES.md"
CATEGORIES = ("TESTED", "INVARIANT", "OBSERVED", "DESIGN", "KNOWN GAP")
VERIFIABLES = ("TESTED", "INVARIANT", "OBSERVED")

# Le pointeur de preuve est OPTIONNEL dans la forme, et obligatoire dans le fond
# pour les seules catégories vérifiables. Exiger « — preuve : » partout obligerait
# à en inventer un pour [DESIGN] et [KNOWN GAP], dont l'absence de preuve EST la
# définition. Un format qui force à écrire ce qu'on n'a pas fabrique du faux.
LIGNE = re.compile(
    r"^- \[(?P<cat>[A-Z ]+)\] (?P<enonce>.+?)(?: — preuve : (?P<preuve>.+?))?\s*$")


def tests_existants() -> set[str]:
    noms = set()
    for f in (RACINE / "tests").glob("test_*.py"):
        noms |= set(re.findall(r"^def (test_\w+)", f.read_text(encoding="utf-8"), re.M))
    return noms


def code_du_domaine() -> str:
    """Le code où un garde-fou peut vivre : scripts et modules, pas les tests."""
    morceaux = []
    for motif in ("*.py", "scripts/*.sh", "scripts/lanceur/*.sh"):
        for f in RACINE.glob(motif):
            morceaux.append(f.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(morceaux)


def lire_registre(texte: str) -> tuple[list[dict], list[str]]:
    """Rend (énoncés, lignes mal formées). Une ligne de puce qui ne suit pas le
    format est signalée : silencieusement l'ignorer viderait le registre sans
    que le compteur bouge."""
    enonces, malformees = [], []
    for brut in texte.splitlines():
        if not brut.startswith("- ["):
            continue
        if (m := LIGNE.match(brut)):
            enonces.append({"categorie": m["cat"].strip(),
                            "enonce": m["enonce"].strip(),
                            "preuve": (m["preuve"] or "").strip()})
        else:
            malformees.append(brut.strip())
    return enonces, malformees


def verifier(enonces: list[dict]) -> list[str]:
    """Rend la liste des défauts. Vide = le dossier tient."""
    defauts, tests, code = [], tests_existants(), code_du_domaine()
    for e in enonces:
        cat, preuve, court = e["categorie"], e["preuve"], e["enonce"][:58]
        if cat not in CATEGORIES:
            defauts.append(f"catégorie inconnue [{cat}] — {court}")
            continue
        if cat in VERIFIABLES and not preuve:
            defauts.append(f"[{cat}] sans pointeur de preuve — {court}")
            continue
        if cat == "TESTED":
            noms = re.findall(r"\btest_\w+", preuve)
            if not noms:
                defauts.append(f"[TESTED] sans nom de test — {court}")
            for n in noms:
                if n not in tests:
                    defauts.append(f"[TESTED] cite {n}, qui n'existe plus — {court}")
        elif cat == "INVARIANT":
            garde = preuve.strip("`")
            if garde not in code:
                defauts.append(f"[INVARIANT] cite « {garde} », absent du code — {court}")
        elif cat == "OBSERVED":
            if not (m := re.search(r"\d{4}-\d{2}-\d{2}", preuve)):
                defauts.append(f"[OBSERVED] sans date — {court}")
            else:
                try:
                    date.fromisoformat(m.group())
                except ValueError:
                    defauts.append(f"[OBSERVED] date invalide {m.group()} — {court}")
    return defauts


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--detail", action="store_true")
    args = a.parse_args()

    if not REGISTRE.exists():
        print(f"registre absent : {REGISTRE.name}")
        return 1

    enonces, malformees = lire_registre(REGISTRE.read_text(encoding="utf-8"))
    defauts = verifier(enonces) + [f"ligne mal formée : {l[:70]}" for l in malformees]

    compte = {c: sum(1 for e in enonces if e["categorie"] == c) for c in CATEGORIES}
    verifie = sum(compte[c] for c in VERIFIABLES)
    print(f"{len(enonces)} énoncé(s) — {verifie} vérifiable(s) mécaniquement · " +
          " · ".join(f"{c} {compte[c]}" for c in CATEGORIES if compte[c]))

    if args.detail:
        for e in enonces:
            print(f"  [{e['categorie']}] {e['enonce'][:74]}")

    if defauts:
        print(f"DOSSIER DE PREUVE ABÎMÉ : {len(defauts)} défaut(s)")
        for d in defauts:
            print(f"  {d}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
