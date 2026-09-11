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

import pytest

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


def test_une_interdiction_dans_la_section_d_ecriture_refuse_le_perimetre(tmp_path):
    """Le contrat a change le 2026-09-11, et le refus est passe de 1 a 2.

    Cette ligne etait sautee en silence. Ici, avec le chemin sur la meme ligne, le resultat
    etait juste par accident : rien ne suivait le marqueur. Sur deux lignes, les chemins
    d'apres devenaient des autorisations d'ecriture, ce qui est le cas le plus tenace du
    garde en service, dix recidives sur six sessions.

    Une intention reconnue que la grammaire ne sait pas placer ne peut pas etre ignoree.
    Le perimetre n'est pas etabli, donc code 2, et le prompt se reecrit avec <interdit>.
    """
    p = tmp_path / "interdit.md"
    p.write_text(
        "<scope>\n  <écriture>\n"
        "    - src/ok.py\n"
        "    INTERDIT src/secret.py\n"
        "  </écriture>\n</scope>\n", encoding="utf-8")
    patterns, niveau = sg.extract_scope_patterns(p)
    assert patterns == []
    assert niveau == "interdiction-hors-grammaire"
    assert sg.run_check(p, ["src/secret.py"])[0] == sg.EXIT_SANS_PERIMETRE
    # Et le temoin : ecrite dans la grammaire, la meme intention refuse en 1 et nomme.
    q = tmp_path / "structure.md"
    q.write_text(
        "<scope>\n  <écriture>\n    - src/\n  </écriture>\n"
        "  <interdit>\n    - src/secret.py\n  </interdit>\n</scope>\n", encoding="utf-8")
    code, hors, _ = sg.run_check(q, ["src/secret.py"])
    assert code == sg.EXIT_DEPASSEMENT
    assert hors == ["src/secret.py"]


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


# ── Le commit n'est pas une liste de chemins de destination ───────────────────
#
# Deux revues exterieures independantes ont trouve le meme contournement le 2026-09-11 :
# `git diff --cached --name-only` detecte les renommages et n'affiche que la destination.
# Un agent qui deplace un fichier interdit vers un chemin autorise sortait le fichier du
# perimetre, et le garde declarait conforme. Les tests ci-dessous travaillent sur un vrai
# depot git : le defaut vivait dans l'appel a git, pas dans la politique.


def _depot(tmp_path, fichiers: dict[str, str]):
    """Depot git jetable, un commit initial, rien d'indexe."""
    import subprocess

    def git(*a):
        subprocess.run(["git", *a], cwd=tmp_path, check=True,
                       capture_output=True, text=True)

    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    for chemin, contenu in fichiers.items():
        cible = tmp_path / chemin
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_text(contenu, encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "init")
    return git


def test_un_renommage_depuis_un_chemin_interdit_est_refuse(tmp_path):
    """Le P0 des deux revues. Le commit supprime `src/auth/session.py`, qui est en
    <interdit>, en le deplacant vers un chemin autorise."""
    git = _depot(tmp_path, {"src/auth/session.py": "logique\n" * 50})
    (tmp_path / "src/ingestion/connectors").mkdir(parents=True)
    git("mv", "src/auth/session.py", "src/ingestion/connectors/metrics.py")

    staged = sg.get_staged_files(tmp_path)
    assert "src/auth/session.py" in staged
    assert "src/ingestion/connectors/metrics.py" in staged

    code, hors, _ = sg.run_check(AVEC, staged)
    assert code == sg.EXIT_DEPASSEMENT
    assert hors == ["src/auth/session.py"]


def test_un_renommage_dans_le_perimetre_passe(tmp_path):
    """Le durcissement ne doit pas refuser un deplacement dont les deux cotes sont
    autorises : sinon le garde devient impraticable et se fait contourner par principe."""
    git = _depot(tmp_path, {"src/ingestion/connectors/__init__.py": "x\n"})
    git("mv", "src/ingestion/connectors/__init__.py", "src/ingestion/connectors/metrics.py")
    assert sg.run_check(AVEC, sg.get_staged_files(tmp_path))[0] == sg.EXIT_CONFORME


def test_une_suppression_hors_perimetre_est_refusee(tmp_path):
    """Supprimer est une ecriture. Elle l'etait deja avant le correctif, ce test le fige."""
    git = _depot(tmp_path, {"src/auth/session.py": "x\n"})
    git("rm", "-q", "src/auth/session.py")
    code, hors, _ = sg.run_check(AVEC, sg.get_staged_files(tmp_path))
    assert code == sg.EXIT_DEPASSEMENT
    assert hors == ["src/auth/session.py"]


def test_un_chemin_accentue_du_perimetre_n_est_pas_refuse_a_tort(tmp_path):
    """Sans `-z`, git rend `"src/.../m\\303\\251triques.py"`, guillemets et echappement
    octal compris. Le chemin ne correspondait alors a aucun motif et etait refuse a tort.
    Un refus sans danger, mais bruyant dans un code en francais."""
    _depot(tmp_path, {"src/ingestion/connectors/metrics.py": "x\n"})
    (tmp_path / "src/ingestion/connectors/métriques.py").write_text("y\n", encoding="utf-8")
    import subprocess
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    assert sg.get_staged_files(tmp_path) == ["src/ingestion/connectors/métriques.py"]


def test_une_sortie_de_git_tronquee_leve_au_lieu_de_rendre_une_liste_partielle(monkeypatch):
    """Un statut R sans ses deux chemins doit lever, pas rendre la moitie du renommage :
    c'est la meme regle que l'echec d'enumeration, ne pas savoir n'autorise pas."""
    import subprocess

    class Sortie:
        returncode = 0
        stdout = "R100\0src/auth/session.py\0"   # la destination manque
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: Sortie())
    with pytest.raises(sg.StagedFilesUnavailableError):
        sg.get_staged_mutations()


def test_un_repertoire_de_travail_absent_leve_au_lieu_de_planter(tmp_path):
    """`git` lance hors d'un repertoire existant mourait sur une trace Python. Une trace
    n'est pas un refus : elle se lit comme un silence, et c'est exactement le defaut que
    l'audit interne du 2026-09-11 a trouve dans `verify.py`."""
    with pytest.raises(sg.StagedFilesUnavailableError):
        sg.get_staged_files(tmp_path / "pas-un-repertoire")


# ── Trois regles de classe, en matrice ────────────────────────────────────────
#
# Les revues v4 et v5 font la meme remarque de fond : chaque iteration corrigeait le cas
# signale, et la meme classe de defaut reapparaissait juste a cote. Un glob corrige pour les
# placeholders mais pas pour les globs explicites, une liste noire de noms de sections au
# lieu d'une liste blanche. Les trois matrices ci-dessous testent la regle, pas l'incident.


BLOCS_NON_INTERPRETABLES = [
    ("en-tete en majuscules", "- src/ingestion/metrics.py\nINTERDIT :\n- src/auth/"),
    ("titre markdown", "- src/ingestion/metrics.py\n## Interdit\n- src/auth/"),
    ("balise anglaise", "<read>\n- src/auth/\n</read>"),
    ("balise composee", "<read-only>\n- src/auth/\n</read-only>"),
    ("balise inconnue", "<perimetre-lecture>\n- src/auth/\n</perimetre-lecture>"),
    ("phrase libre", "Tu peux ecrire dans src/ingestion/\n- src/auth/"),
]


@pytest.mark.parametrize("nom,bloc", BLOCS_NON_INTERPRETABLES,
                         ids=[n for n, _ in BLOCS_NON_INTERPRETABLES])
def test_un_bloc_non_interpretable_refuse_au_lieu_d_autoriser(tmp_path, nom, bloc):
    """Liste blanche : ce que le garde ne sait pas classer, il le refuse. La liste noire
    precedente laissait passer par construction tout nom de section qu'elle ignorait, et
    les rediger des prompts sont souvent des agents, qui varient les noms."""
    p = tmp_path / f"{abs(hash(nom))}.md"
    p.write_text(f"# W\n\n<scope>\n{bloc}\n</scope>\n", encoding="utf-8")
    assert sg.extract_scope_patterns(p)[0] == []
    assert sg.run_check(p, ["src/auth/session.py"])[0] == sg.EXIT_SANS_PERIMETRE


@pytest.mark.parametrize("ecriture", ["src/ingestion/", "src/ingestion/*.py",
                                      "src/ingestion/**"])
def test_un_chemin_interdit_refuse_meme_sous_une_autorisation(tmp_path, ecriture):
    """Le refus l'emporte. « Tu peux modifier src/ingestion/ sauf secrets/ » est la facon
    naturelle d'ecrire une exception, et <interdit> n'etait qu'une absence d'autorisation."""
    p = tmp_path / "exception.md"
    p.write_text(
        f"# W\n\n<scope>\n  <écriture>\n    - {ecriture}\n  </écriture>\n"
        "  <interdit>\n    - src/ingestion/secrets/\n  </interdit>\n</scope>\n",
        encoding="utf-8")
    assert sg.run_check(p, ["src/ingestion/secrets/keys.py"])[0] == sg.EXIT_DEPASSEMENT
    assert sg.run_check(p, ["src/ingestion/ok.py"])[0] == sg.EXIT_CONFORME


MOTIFS = [
    ("reports/*.json", "reports/a.json", True),
    ("reports/*.json", "reports/private/secret.json", False),
    ("reports/**/*.json", "reports/private/secret.json", True),
    ("reports/W3_<TS>.json", "reports/W3_2026-09-11.json", True),
    ("reports/W3_<TS>.json", "reports/W3_x/nested/any.json", False),
    ("src/a?.py", "src/ab.py", True),
    ("src/a?b.py", "src/a/b.py", False),
    ("src/foo/", "src/foo/profond/a.py", True),
]


@pytest.mark.parametrize("motif,chemin,attendu", MOTIFS,
                         ids=[f"{m}~{c}" for m, c, _ in MOTIFS])
def test_un_joker_ne_franchit_jamais_un_separateur(motif, chemin, attendu):
    """Meme regle pour les placeholders et pour les globs explicites : `*` designe un
    fragment de nom. La traversee d'arborescence s'ecrit `**`, elle ne se devine pas."""
    assert sg.file_matches_scope(chemin, [motif]) is attendu


# ── Une permission est une forme, pas une chaine qu'on interprete ─────────────
#
# Les deux P0 de la revue du 2026-09-11 au soir ont la meme cause : une seule chaine
# essayait de representer un fichier, un repertoire, un motif et un placeholder, et le
# code devinait ensuite lequel. Les deux fois, la devinette elargissait la permission.


def test_un_chemin_avec_espace_ne_devient_pas_un_prefixe_plus_large(tmp_path):
    """`docs/my file.md` etait coupe au premier espace et donnait la permission
    `docs/my`, qui ouvre tout un sous-arbre. Une ambiguite d'analyse ne peut pas se
    resoudre en elargissement de privilege."""
    p = tmp_path / "espace.md"
    p.write_text("<scope>\n  <écriture>\n    - `docs/my file.md`\n  </écriture>\n</scope>\n",
                 encoding="utf-8")
    assert sg.extract_scope_patterns(p)[0] == ["docs/my file.md"]
    assert sg.run_check(p, ["docs/my file.md"])[0] == sg.EXIT_CONFORME
    assert sg.run_check(p, ["docs/my/secret.txt"])[0] == sg.EXIT_DEPASSEMENT


def test_un_chemin_nu_avec_espace_refuse_au_lieu_d_etre_tronque(tmp_path):
    """Sans accents graves, le garde ne sait pas ou finit le chemin. Il refuse."""
    p = tmp_path / "nu.md"
    p.write_text("<scope>\n  <écriture>\n    - docs/my file.md\n  </écriture>\n</scope>\n",
                 encoding="utf-8")
    patterns, niveau = sg.extract_scope_patterns(p)
    assert patterns == []
    assert niveau == "chemin-ambigu"
    assert sg.run_check(p, ["docs/my/secret.txt"])[0] == sg.EXIT_SANS_PERIMETRE


def test_un_commentaire_entre_parentheses_reste_lisible(tmp_path):
    """Le durcissement ne doit pas fermer la forme courante `- src/foo/ (le connecteur)`,
    sinon le garde devient impraticable et finit desactive."""
    p = tmp_path / "commentaire.md"
    p.write_text("<scope>\n  <écriture>\n    - src/foo/ (le connecteur)\n  </écriture>\n</scope>\n",
                 encoding="utf-8")
    assert sg.extract_scope_patterns(p)[0] == ["src/foo/"]


FORMES = [
    ("fichier exact, lui-meme", "config/settings.json", "config/settings.json", True),
    ("fichier exact, pseudo sous-arbre", "config/settings.json",
     "config/settings.json/evil.py", False),
    ("repertoire, son contenu", "src/foo/", "src/foo/a.py", True),
    ("repertoire, en profondeur", "src/foo/", "src/foo/profond/a.py", True),
    ("repertoire, lui-meme", "src/foo/", "src/foo", True),
    ("motif, enfant direct", "reports/*.json", "reports/a.json", True),
    ("motif, sous-repertoire", "reports/*.json", "reports/prive/a.json", False),
    ("motif recursif explicite", "reports/**/*.json", "reports/prive/a.json", True),
]


@pytest.mark.parametrize("nom,motif,chemin,attendu", FORMES, ids=[f[0] for f in FORMES])
def test_les_trois_formes_de_permission_se_distinguent(nom, motif, chemin, attendu):
    """`config/settings.json` autorisait `config/settings.json/evil.py`, parce que le
    chemin commence bien par `config/settings.json/`. Rien n'interdit a un repertoire de
    s'appeler `settings.json`. Un repertoire s'ecrit avec sa barre finale."""
    assert sg.file_matches_scope(chemin, [motif]) is attendu


def test_deux_scopes_de_casse_differente_sont_ambigus(tmp_path):
    """Le comptage se faisait en deux passes, la premiere sensible a la casse. Un prompt
    portant `<scope>` puis `<SCOPE>` sortait de la premiere avec un seul bloc, et le second
    n'etait jamais compte : l'ambiguite passait a cause de la casse."""
    p = tmp_path / "casse.md"
    p.write_text("<scope>\n- src/a/\n</scope>\n\n<SCOPE>- src/b/</SCOPE>\n", encoding="utf-8")
    patterns, niveau = sg.extract_scope_patterns(p)
    assert patterns == []
    assert niveau == "perimetre-ambigu"
    assert sg.run_check(p, ["src/b/x.py"])[0] == sg.EXIT_SANS_PERIMETRE


INTERDICTIONS_HORS_GRAMMAIRE = [
    ("titre markdown a cote de la section",
     "<scope>\n  <écriture>\n    - src/\n  </écriture>\n\n  ## Interdit\n  - src/secrets/\n</scope>\n"),
    ("marqueur dans la section d'ecriture",
     "<scope>\n  <écriture>\n    - src/foo/\n    INTERDIT :\n    - src/secrets/\n  </écriture>\n</scope>\n"),
    ("marqueur anglais",
     "<scope>\n  <écriture>\n    - src/\n  </écriture>\n  FORBIDDEN:\n  - src/secrets/\n</scope>\n"),
    ("lecture seule en toutes lettres",
     "<scope>\n  <écriture>\n    - src/\n  </écriture>\n  LECTURE SEULE : src/secrets/\n</scope>\n"),
]


@pytest.mark.parametrize("nom,texte", INTERDICTIONS_HORS_GRAMMAIRE,
                         ids=[n for n, _ in INTERDICTIONS_HORS_GRAMMAIRE])
def test_une_interdiction_hors_grammaire_refuse_le_perimetre(tmp_path, nom, texte):
    """Ces lignes etaient sautees en silence. L'interdiction disparaissait, et quand des
    chemins la suivaient dans une section d'ecriture, ils devenaient des autorisations.
    Une intention reconnue que la grammaire ne sait pas placer refuse."""
    p = tmp_path / f"{abs(hash(nom))}.md"
    p.write_text(texte, encoding="utf-8")
    patterns, niveau = sg.extract_scope_patterns(p)
    assert patterns == []
    assert niveau == "interdiction-hors-grammaire"
    assert sg.run_check(p, ["src/secrets/keys.py"])[0] == sg.EXIT_SANS_PERIMETRE
