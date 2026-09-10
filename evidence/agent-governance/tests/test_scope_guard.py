"""Ce que le garde de perimetre refuse, et le contournement qu'il a fallu fermer.

Le test le plus interessant du fichier est `test_le_bloc_entier_n_est_pas_un_perimetre`.
Il code un contournement reel : quand le XML du prompt ne parse pas, une version naive du
garde retombe sur le bloc `<scope>` entier et prend les chemins de `<lecture>` et de
`<interdit>` pour des autorisations d'ecriture. Le garde laisse alors passer exactement ce
qu'il devait bloquer, sans rien signaler.

Ce cas s'est produit a la premiere execution de cet extrait, le 2026-09-10, sur l'exemple
livre : le placeholder `reports/W3_<TS>.json` contient `<TS>`, que le parseur XML lit comme
une balise ouvrante jamais fermee.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scope_guard as sg  # noqa: E402

EXEMPLE = Path(__file__).resolve().parent.parent / "example"
AVEC = EXEMPLE / "prompt_avec_scope.md"
SANS = EXEMPLE / "prompt_sans_scope.md"


# ── Le comportement de base ───────────────────────────────────────────────────


def test_une_ecriture_dans_le_perimetre_passe():
    code, hors, _ = sg.run_check(AVEC, ["src/ingestion/connectors/metrics.py"])
    assert code == sg.EXIT_CONFORME
    assert hors == []


def test_une_ecriture_hors_perimetre_est_refusee():
    """Le cas qui justifie le garde : un agent qui touche l'authentification alors que
    son prompt lui donnait le repertoire d'ingestion."""
    code, hors, _ = sg.run_check(
        AVEC, ["src/ingestion/connectors/metrics.py", "src/auth/session.py"])
    assert code == sg.EXIT_DEPASSEMENT
    assert hors == ["src/auth/session.py"]


def test_un_placeholder_dynamique_est_couvert():
    """Un rapport dont le nom porte l'horodatage ne peut pas etre nomme a l'avance."""
    code, hors, _ = sg.run_check(AVEC, ["reports/W3_2026-09-10T21-15.json"])
    assert code == sg.EXIT_CONFORME


def test_un_prompt_sans_perimetre_ne_passe_pas_pour_autant():
    """Absence de perimetre n'est pas autorisation universelle. Code 2, pas code 0 :
    le garde ne peut pas verifier, donc il ne conclut pas."""
    code, _, niveau = sg.run_check(SANS, ["n_importe_quoi.py"])
    assert code == sg.EXIT_SANS_PERIMETRE
    assert niveau == "no-scope"


# ── Le contournement, ferme et garde sous test ────────────────────────────────


def test_le_bloc_entier_n_est_pas_un_perimetre(tmp_path):
    """CONTOURNEMENT REEL. XML casse, sous-balise <écriture> presente : le garde doit
    lire la sous-balise par expression reguliere, jamais le bloc entier.

    Si ce test echoue, le garde a recommence a prendre <lecture> et <interdit> pour des
    autorisations d'ecriture, et il ne bloque plus rien.
    """
    patterns, niveau = sg.extract_scope_patterns(AVEC)
    assert niveau == "xml-regex", "le XML de l'exemple ne parse pas, le repli doit servir"
    assert "src/auth/" not in patterns, "un chemin interdit est devenu une autorisation"
    assert "src/ingestion/" not in patterns, "un chemin de lecture est devenu une autorisation"
    assert "src/ingestion/connectors/metrics.py" in patterns


def test_une_sous_balise_ecriture_illisible_ne_degrade_pas_en_bloc_entier(tmp_path):
    """Meme sans repli possible, le garde rend une liste vide et non le bloc entier."""
    p = tmp_path / "casse.md"
    p.write_text(
        "<scope>\n"
        "  <lecture>\n    - src/\n  </lecture>\n"
        "  <écriture>\n    - src/ok.py\n"   # balise jamais refermee
        "</scope>\n", encoding="utf-8")
    patterns, niveau = sg.extract_scope_patterns(p)
    assert patterns == []
    assert niveau == "ecriture-illisible"
    code, _, _ = sg.run_check(p, ["src/ok.py"])
    assert code == sg.EXIT_SANS_PERIMETRE


def test_une_section_interdit_n_autorise_rien(tmp_path):
    p = tmp_path / "interdit.md"
    p.write_text(
        "<scope>\n  <écriture>\n"
        "    - src/ok.py\n"
        "    INTERDIT src/secret.py\n"
        "  </écriture>\n</scope>\n", encoding="utf-8")
    patterns, _ = sg.extract_scope_patterns(p)
    assert patterns == ["src/ok.py"]
    code, hors, _ = sg.run_check(p, ["src/secret.py"])
    assert code == sg.EXIT_DEPASSEMENT


# ── Les chemins fail-open trouves par la revue du 2026-09-11 ──────────────────


def test_un_scope_lecture_seule_ne_devient_jamais_ecrivable(tmp_path):
    """Le pire des cas trouves : un perimetre qui ne declare aucune ecriture.

    Le bloc porte <lecture> et <interdit>, pas de <écriture>. Le garde retombait sur le
    bloc entier et promouvait `src/auth/` en autorisation d'ecriture, alors que le prompt
    le donnait en lecture. Ne pas pouvoir etablir un perimetre d'ecriture doit refuser.
    """
    p = tmp_path / "lecture_seule.md"
    p.write_text("<scope>\n  <lecture>\n    - src/auth/\n  </lecture>\n"
                 "  <interdit>\n    - secrets/\n  </interdit>\n</scope>\n", encoding="utf-8")
    patterns, niveau = sg.extract_scope_patterns(p)
    assert patterns == []
    assert niveau == "scope-structure-sans-section-ecriture"
    assert sg.run_check(p, ["src/auth/session.py"])[0] == sg.EXIT_SANS_PERIMETRE


def test_un_scope_interdit_seul_ne_devient_jamais_ecrivable(tmp_path):
    p = tmp_path / "interdit_seul.md"
    p.write_text("<scope>\n  <interdit>\n    - secrets/\n  </interdit>\n</scope>\n",
                 encoding="utf-8")
    assert sg.extract_scope_patterns(p)[0] == []
    assert sg.run_check(p, ["secrets/token"])[0] == sg.EXIT_SANS_PERIMETRE


def test_un_ancien_format_sans_section_reste_lisible(tmp_path):
    """Le durcissement ci-dessus ne doit pas fermer le format simple, qui n'a aucune
    section et dont toutes les puces sont des autorisations d'ecriture."""
    p = tmp_path / "simple.md"
    p.write_text("<scope>\n- src/foo/\n- reports/*.json\n</scope>\n", encoding="utf-8")
    patterns, niveau = sg.extract_scope_patterns(p)
    assert patterns == ["src/foo/", "reports/*.json"]
    assert niveau == "xml-direct"
    assert sg.run_check(p, ["src/foo/a.py"])[0] == sg.EXIT_CONFORME


def test_un_placeholder_ne_franchit_pas_un_separateur():
    """`fnmatch` laissait `*` traverser les `/` : le perimetre `reports/W3_<TS>.json`
    acceptait `reports/W3_x/nested/any.json`. Un placeholder tient dans son segment."""
    assert sg.file_matches_scope("reports/W3_2026-09-11.json", ["reports/W3_<TS>.json"])
    assert not sg.file_matches_scope("reports/W3_x/nested/any.json", ["reports/W3_<TS>.json"])


def test_une_enumeration_de_stages_qui_echoue_leve(tmp_path):
    """Ne pas savoir ce que contient le commit n'est pas la meme chose qu'un commit vide.
    `git diff` hors depot rendait une liste vide, et le garde concluait conforme."""
    import pytest
    with pytest.raises(sg.StagedFilesUnavailableError):
        sg.get_staged_files(tmp_path)


def test_le_cli_sans_source_de_stages_refuse():
    """Invoque sans --staged ni --staged-from-git, le garde n'a rien a controler et le
    disait « OK : 0 fichier(s) ». Il refuse desormais."""
    code = sg.main(["--prompt", str(EXEMPLE / "prompt_avec_scope.md")])
    assert code == sg.EXIT_SANS_PERIMETRE


def test_plusieurs_blocs_scope_refusent(tmp_path):
    """Choisir le plus long etait une heuristique. Une duplication de prompt suffisait a
    designer le mauvais perimetre. Une ambiguite de permission refuse."""
    p = tmp_path / "deux.md"
    p.write_text("<scope>\n- src/a/\n</scope>\n\ntexte\n\n<scope>\n- src/b/\n- src/c/\n</scope>\n",
                 encoding="utf-8")
    patterns, niveau = sg.extract_scope_patterns(p)
    assert patterns == []
    assert niveau == "perimetre-ambigu"
    assert sg.run_check(p, ["src/b/x.py"])[0] == sg.EXIT_SANS_PERIMETRE
