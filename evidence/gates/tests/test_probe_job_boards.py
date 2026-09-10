"""Ce que le sondeur compte, et ce qu'il refuse de compter.

Ce module existe a cause d'une observation : SmartRecruiters rend HTTP 200 avec
`totalFound: 0` sur un identifiant qui n'existe pas, donc un code 200 ne prouve rien. La
regle qui en decoule est qu'un zero doit toujours etre un zero observe. L'audit du
2026-09-11 a trouve que la fonction de comptage reproduisait le piege chez elle : une
reponse dont la forme avait change rendait 0 au lieu de dire qu'elle n'avait pas su lire.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "probe_job_boards", Path(__file__).resolve().parent.parent / "probe_job_boards.py")
pb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pb)


def test_les_six_familles_sont_declarees():
    """Le texte publie annonce six systemes. S'il en annonce un autre nombre, c'est ici
    que la derive se voit."""
    assert len(pb.PATRONS) == 6
    assert set(pb.PATRONS) == {"greenhouse", "lever", "ashby", "smartrecruiters",
                               "workable", "recruitee"}


def test_un_zero_observe_vaut_zero():
    assert pb.compter("greenhouse", {"jobs": []}) == 0
    assert pb.compter("smartrecruiters", {"totalFound": 0, "content": []}) == 0
    assert pb.compter("lever", []) == 0


def test_un_compte_reel_est_rendu():
    assert pb.compter("greenhouse", {"jobs": [1, 2, 3]}) == 3
    assert pb.compter("lever", [1, 2]) == 2
    assert pb.compter("recruitee", {"offers": [1]}) == 1


def test_une_forme_inconnue_ne_vaut_pas_zero():
    """Le coeur du module. Une reponse qui ne ressemble pas a ce qu'on attend veut dire
    « je n'ai pas su compter », et surtout pas « il n'y a rien »."""
    assert pb.compter("greenhouse", {"autre": "chose"}) == -1
    assert pb.compter("greenhouse", {"jobs": "pas une liste"}) == -1
    assert pb.compter("lever", {"pas": "une liste"}) == -1
    assert pb.compter("recruitee", {"offers": None}) == -1
    assert pb.compter("smartrecruiters", {"content": "x"}) == -1


def test_un_systeme_inconnu_ne_vaut_pas_zero():
    assert pb.compter("inconnu", {"jobs": [1, 2]}) == -1
