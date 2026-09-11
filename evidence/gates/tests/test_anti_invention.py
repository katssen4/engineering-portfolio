"""Ce que la porte anti-invention sait faire, et ce qu'elle ne sait pas faire.

Les cas de la seconde moitie du fichier sont des LIMITES CONNUES, pas des defauts a corriger
un jour en silence. Ils sont ecrits comme des tests qui passent, avec le comportement reel en
assertion, pour qu'une amelioration future les fasse echouer et force a mettre a jour la
documentation en meme temps que le code.

Origine : deux revues exterieures du 2026-09-10 ont teste la porte de facon adverse et
trouve trois faux negatifs, un faux positif et quatre collisions numeriques. Les collisions
et le faux positif sont corriges ci-dessous ; les faux negatifs sont structurels.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

import anti_invention as ai  # noqa: E402

EXEMPLE = Path(__file__).resolve().parent.parent / "example"


def cles(t: str) -> set:
    return set(ai.nombres(t))


# ── Ce que la normalisation numerique doit distinguer ──────────────────────────


def test_les_milliers_s_ecrivent_comme_on_veut():
    """Une virgule anglaise, un point, une espace fine : meme nombre, meme cle."""
    assert cles("90,000") == cles("90000") == cles("90 000")


def test_un_decimal_n_est_pas_l_entier_sans_le_point():
    """Le cas releve par la revue : 5.0 valait 50 apres normalisation."""
    assert cles("5.0") != cles("50")
    assert cles("1.20") != cles("120")


def test_les_zeros_de_fin_ne_changent_pas_la_valeur():
    assert cles("5.0") == cles("5")
    assert cles("1.20") == cles("1.2")


def test_le_signe_entre_dans_la_cle():
    """Passer de -10 % a +10 % est un renversement de fait, pas une reformulation."""
    assert cles("-10") != cles("10")


def test_l_unite_entre_dans_la_cle():
    assert cles("5 MB") != cles("5 GB")
    assert cles("12%") != cles("12")


def test_un_multiplicateur_colle_vaut_sa_valeur():
    """48k et 48 000 sont le meme fait ecrit deux fois."""
    assert cles("48k") == cles("48000")
    assert cles("5M") == cles("5000000")


def test_un_multiplicateur_en_toutes_lettres_vaut_sa_valeur():
    """Faux positif releve en revue : « 312M » et « 312 million » donnaient deux cles."""
    assert cles("312M") == cles("312 million") == cles("312000000")
    assert cles("5 milliards") == cles("5000000000")


def test_un_identifiant_long_ne_perd_pas_de_precision():
    """Decimal et non float : deux identifiants voisins ne doivent pas se confondre."""
    assert cles("12345678901234567890") != cles("12345678901234567891")


# ── Ce que la porte attrape, de bout en bout ──────────────────────────────────


def porte(derive: str) -> int:
    import subprocess
    tmp = Path(__file__).resolve().parent / "_derive_temporaire.md"
    tmp.write_text("# Meridian\n\n" + derive + "\n", encoding="utf-8")
    try:
        r = subprocess.run(
            [sys.executable, str(EXEMPLE.parent / "anti_invention.py"),
             str(EXEMPLE / "source_of_truth.md"), str(tmp), "--banals", "Meridian"],
            capture_output=True, text=True, timeout=60)
        return r.returncode
    finally:
        tmp.unlink(missing_ok=True)


def test_un_chiffre_gonfle_est_refuse():
    assert porte("Sustained throughput of 90000 events per second.") == 1


def test_une_affirmation_non_sourcee_est_refusee():
    assert porte("Deployed on Kubernetes across the estate.") == 1


def test_une_reformulation_honnete_passe():
    assert porte("Sustained throughput of 48,000 events per second.") == 0


# ── Limites connues, livrees et executees ─────────────────────────────────────


def test_limite_une_affirmation_sans_chiffre_ni_nom_propre_passe():
    """LIMITE CONNUE. La porte est lexicale : elle compare des jetons, pas du sens.

    Cette phrase contredit frontalement la section « Not measured » de la source, qui dit
    qu'il n'y a pas de grappe et que rien n'est connu au-dela d'un noeud. Aucun chiffre
    nouveau, aucun mot capitalise nouveau : la porte ne voit rien.
    """
    assert porte("Scaling across nodes has been validated in production.") == 0


def test_limite_une_omission_de_reserve_passe():
    """LIMITE CONNUE. Retirer une reserve est une distorsion, et la porte ne la voit pas.

    Elle compare ce que la derivation ajoute, jamais ce qu'elle enleve. Supprimer la
    rubrique « Not measured » rend le document plus flatteur sans ajouter un seul jeton.
    """
    source = (EXEMPLE / "source_of_truth.md").read_text(encoding="utf-8")
    tronque = source.split("## Not measured")[0]
    tmp = Path(__file__).resolve().parent / "_tronque_temporaire.md"
    tmp.write_text(tronque, encoding="utf-8")
    try:
        import subprocess
        r = subprocess.run(
            [sys.executable, str(EXEMPLE.parent / "anti_invention.py"),
             str(EXEMPLE / "source_of_truth.md"), str(tmp), "--banals", "Meridian"],
            capture_output=True, text=True, timeout=60)
        assert r.returncode == 0
    finally:
        tmp.unlink(missing_ok=True)


# ── Un mot est banal pour deux raisons, et il ne faut pas les confondre ───────
#
# Un mot echappe au signalement parce qu'il est grammatical, ou parce que le fait qu'il
# nomme est autorise par le dossier. La liste globale melangeait les deux : « Nantes »,
# « Ariane », « Alex » et « Doe » y etaient codes en dur, donc une localisation ou un nom
# de produit inventes passaient sans un mot. Releve le 2026-09-11.


FAITS_QUI_NE_SONT_PAS_BANALS = ["Nantes", "Ariane", "Alex", "Doe"]


@pytest.mark.parametrize("mot", FAITS_QUI_NE_SONT_PAS_BANALS)
def test_un_fait_du_dossier_n_est_pas_un_mot_structurel(mot):
    assert mot not in ai.BANALS, (
        f"« {mot} » est un fait, il entre par --banals quand le dossier l'autorise")


def test_une_localisation_absente_du_socle_est_signalee():
    """Le cas concret : le socle ne porte aucune localisation, la variante en annonce une."""
    assert "nantes" in {n.lower() for n in ai.noms("Based in Nantes.")}


def test_un_fait_declare_par_l_appelant_cesse_d_etre_signale(monkeypatch):
    """La porte reste utilisable : ce qui est autorise se declare, il ne se devine pas.
    `noms` lit BANALS au moment de l'appel, exactement comme le fait le point d'entree."""
    autorises = ai.charger_banals(["--banals", "Nantes,Ariane"])
    monkeypatch.setattr(ai, "BANALS", ai.BANALS | autorises)
    trouves = ai.noms("Based in Nantes, on Ariane.")
    assert "nantes" not in trouves
    assert "ariane" not in trouves


# ── Une devise en prefixe appartient au nombre ───────────────────────────────


DEVISES = [
    ("$5", "€5", False),      # meme chiffre, devises differentes
    ("$5", "5 $", True),      # meme montant, symbole devant ou derriere
    ("€5", "5 €", True),
    ("$5", "$5", True),
]


@pytest.mark.parametrize("a,b,identiques", DEVISES, ids=[f"{a}~{b}" for a, b, _ in DEVISES])
def test_deux_montants_ne_se_confondent_pas_par_leur_seul_chiffre(a, b, identiques):
    """« $5 » et « €5 » se normalisaient tous deux en « 5 » : une variante pouvait changer
    la devise d'un montant sans que la porte voie un jeton nouveau."""
    assert (set(ai.nombres(a)) == set(ai.nombres(b))) is identiques
