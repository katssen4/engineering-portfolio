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


# ── Le transport suit la meme regle que la forme ──────────────────────────────
#
# `compter` refusait d'inventer un zero pendant que `sonder` en fabriquait un a chaque
# erreur reseau. Une revue exterieure a releve la contradiction le 2026-09-11 : le README
# de ce repertoire promet qu'un zero est un zero que quelqu'un a observe, et un 403 n'est
# pas une observation d'absence d'offre.


import urllib.error  # noqa: E402
import urllib.request  # noqa: E402

import pytest  # noqa: E402


class _Reponse:
    """Une reponse 200 minimale, du strict necessaire pour `with urlopen(...) as rep`."""

    status = 200

    def __init__(self, charge: bytes):
        self._charge = charge

    def read(self):
        return self._charge

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


ECHECS = [
    ("403", urllib.error.HTTPError("u", 403, "Forbidden", {}, None)),
    ("429", urllib.error.HTTPError("u", 429, "Too Many Requests", {}, None)),
    ("500", urllib.error.HTTPError("u", 500, "Server Error", {}, None)),
    ("delai depasse", TimeoutError("timed out")),
    ("echec DNS", urllib.error.URLError("Name or service not known")),
]


@pytest.mark.parametrize("nom,erreur", ECHECS, ids=[n for n, _ in ECHECS])
def test_une_non_reponse_ne_devient_jamais_zero_offre(monkeypatch, nom, erreur):
    def lever(*a, **k):
        raise erreur

    monkeypatch.setattr(urllib.request, "urlopen", lever)
    ligne = pb.sonder(("Entreprise", "terrain", "greenhouse", "jeton"))
    assert ligne["offres"] == -1, f"{nom} a ete lu comme une absence d'offre"
    assert ligne.get("note"), "la raison doit etre consignee, pas seulement le -1"


def test_un_zero_ne_sort_que_d_un_200_de_forme_reconnue(monkeypatch):
    """Le seul chemin qui a le droit de produire un zero."""
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Reponse(b'{"jobs": []}'))
    assert pb.sonder(("E", "t", "greenhouse", "j"))["offres"] == 0


def test_un_200_de_forme_inconnue_ne_vaut_pas_zero(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: _Reponse(b'{"resultats": []}'))
    assert pb.sonder(("E", "t", "greenhouse", "j"))["offres"] == -1


def test_un_200_qui_n_est_pas_du_json_ne_vaut_pas_zero(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: _Reponse(b"<html>maintenance</html>"))
    ligne = pb.sonder(("E", "t", "greenhouse", "j"))
    assert ligne["offres"] == -1
    assert ligne["note"] == "reponse non JSON"


def test_le_module_ne_promet_pas_de_signaler_les_injections():
    """Le docstring annoncait que les directives adressees a un agent etaient signalees.
    Ce module ne lit pas le texte des fiches : il compte. Le claim decrivait un mecanisme
    absent du fichier publie, ce que ce test empeche de reintroduire."""
    doc = pb.__doc__ or ""
    assert "elles sont signalees" not in doc
    assert "harnais prive" in doc
