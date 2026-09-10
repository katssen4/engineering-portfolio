"""Tests du dossier de preuve (Phase S7).

Ce que ces tests protègent : que le registre ne devienne pas décoratif. C'est le
destin ordinaire de ce genre de document — les énoncés restent, les preuves qu'ils
citent disparaissent, et il suffit alors d'un fichier qui *affirme* être un dossier
de preuve pour croire qu'on en a un.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import proof_registry as preuves  # noqa: E402


def defauts(texte: str) -> list[str]:
    enonces, malformees = preuves.lire_registre(texte)
    return preuves.verifier(enonces) + [f"mal formée : {l}" for l in malformees]


def test_un_test_cite_qui_n_existe_plus_fait_echouer() -> None:
    """Le cas qui compte : un test renommé ou supprimé laisserait un énoncé qui
    prétend être vérifié alors qu'il ne l'est plus."""
    d = defauts("- [TESTED] Quelque chose — preuve : test_qui_n_existe_pas_du_tout")
    assert len(d) == 1 and "n'existe plus" in d[0]


def test_un_test_reellement_present_passe() -> None:
    assert defauts("- [TESTED] Une puce mal formée est signalée — "
                   "preuve : test_une_puce_mal_formee_est_signalee_pas_ignoree") == []


def test_un_invariant_absent_du_code_fait_echouer() -> None:
    """Un garde-fou retiré du code laisserait un énoncé qui promet une protection
    disparue — exactement le mode de panne silencieuse que le domaine refuse."""
    d = defauts("- [INVARIANT] Un garde imaginaire — preuve : `CE TEXTE N EXISTE NULLE PART`")
    assert len(d) == 1 and "absent du code" in d[0]


def test_un_invariant_present_dans_le_code_passe() -> None:
    assert defauts("- [INVARIANT] Le sondeur appelle vraiment — preuve : `urllib.request`") == []


def test_un_observe_sans_date_fait_echouer() -> None:
    """« Constaté » sans date n'est pas une observation : c'est une affirmation."""
    d = defauts("- [OBSERVED] On l'a vu une fois — preuve : lors d'un essai")
    assert len(d) == 1 and "sans date" in d[0]


def test_un_observe_avec_une_date_invalide_fait_echouer() -> None:
    d = defauts("- [OBSERVED] Constaté — preuve : 2026-13-45, essai")
    assert len(d) == 1 and "invalide" in d[0]


def test_design_et_known_gap_n_exigent_aucune_preuve() -> None:
    """Leur absence de preuve EST leur définition. Un format qui forcerait à en
    écrire une fabriquerait du faux."""
    assert defauts("- [DESIGN] Affirmé par construction\n"
                   "- [KNOWN GAP] Ce qui manque, et ce qu'il faudrait") == []


def test_une_categorie_inventee_fait_echouer() -> None:
    """La liste est fermée, comme celle des thèmes et celle des états."""
    d = defauts("- [PROBABLE] Ça devrait aller — preuve : mon intuition")
    assert len(d) == 1 and "catégorie inconnue" in d[0]


def test_une_puce_mal_formee_est_signalee_pas_ignoree() -> None:
    """L'ignorer viderait le registre sans que le compteur bouge — un dossier de
    preuve qui rétrécit en silence est pire qu'un dossier absent."""
    d = defauts("- [TESTED] il manque le séparateur de preuve ici")
    assert len(d) == 1 and "sans pointeur" in d[0]


def test_le_registre_reel_du_domaine_tient() -> None:
    """Le contrôle de fond : le dossier livré doit passer son propre contrôle."""
    registre = Path(preuves.REGISTRE)
    assert registre.exists()
    enonces, malformees = preuves.lire_registre(registre.read_text(encoding="utf-8"))
    assert not malformees, malformees
    assert not preuves.verifier(enonces)
    assert len(enonces) >= 10, "le registre a rétréci, vérifier ce qui a disparu"


def test_le_registre_porte_ses_manques_declares() -> None:
    """Un dossier qui ne porterait que du [TESTED] mentirait par omission. Les
    manques déclarés sont la partie la plus utile à lire."""
    enonces, _ = preuves.lire_registre(Path(preuves.REGISTRE).read_text(encoding="utf-8"))
    categories = [e["categorie"] for e in enonces]
    assert categories.count("KNOWN GAP") >= 2
    assert "DESIGN" in categories
