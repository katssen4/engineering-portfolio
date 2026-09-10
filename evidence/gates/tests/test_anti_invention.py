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
