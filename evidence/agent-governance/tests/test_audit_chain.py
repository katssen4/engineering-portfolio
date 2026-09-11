"""Ce que la chaine d'audit garantit, et ce qu'elle ne garantit pas.

Le test qui compte est `test_une_entree_modifiee_casse_la_chaine`. Un journal d'audit sur
lequel personne n'a essaye de mentir ne prouve rien : ce qui se teste, c'est la detection.

Adapte des tests du harnais en service, reduits au perimetre publie ici.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import audit_chain as ac  # noqa: E402


@pytest.fixture()
def cle(tmp_path, monkeypatch):
    k = tmp_path / "hmac.key"
    k.write_bytes(b"une cle de test de trente-deux octets pile.")  # >= 32
    monkeypatch.setenv("AUDIT_HMAC_KEY_PATH", str(k))
    monkeypatch.setenv("AUDIT_HMAC_STRICT", "1")
    return k


@pytest.fixture()
def journal(tmp_path):
    return tmp_path / "events.jsonl"


def lignes(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


# ── Le chainage ───────────────────────────────────────────────────────────────


def test_le_premier_evenement_porte_le_hash_de_genese(cle, journal):
    ac.append_event("agent.start", {"agent": "W3"}, session="S1", events_path=journal)
    assert lignes(journal)[0]["prev_hash"] == "0" * 64


def test_chaque_evenement_pointe_le_precedent(cle, journal):
    for i in range(3):
        ac.append_event("agent.write", {"n": i}, session="S1", events_path=journal)
    entrees = lignes(journal)
    assert len(entrees) == 3
    for avant, apres in zip(entrees, entrees[1:]):
        assert apres["prev_hash"] == ac._record_hash(avant)


def test_une_chaine_intacte_se_verifie(cle, journal):
    for i in range(4):
        ac.append_event("agent.write", {"n": i}, session="S1", events_path=journal)
    n_valides, anomalies = ac.verify_chain(journal)
    assert (n_valides, anomalies) == (4, [])


# ── La detection, qui est la seule chose qui compte ───────────────────────────


def test_une_entree_modifiee_casse_la_chaine(cle, journal):
    """On modifie la charge utile sans recalculer le HMAC, comme le ferait quelqu'un qui
    reecrit l'histoire a la main. La verification doit nommer l'evenement fautif."""
    for i in range(3):
        ac.append_event("agent.write", {"n": i}, session="S1", events_path=journal)
    entrees = lignes(journal)
    entrees[1]["payload"]["n"] = 999
    journal.write_text("\n".join(json.dumps(e, sort_keys=True, ensure_ascii=False)
                                for e in entrees) + "\n", encoding="utf-8")

    n_valides, anomalies = ac.verify_chain(journal)
    assert entrees[1]["event_id"] in anomalies
    assert n_valides < 3


def test_une_entree_supprimee_casse_la_chaine(cle, journal):
    """Retirer une entree rompt le chainage de la suivante."""
    for i in range(3):
        ac.append_event("agent.write", {"n": i}, session="S1", events_path=journal)
    entrees = lignes(journal)
    del entrees[1]
    journal.write_text("\n".join(json.dumps(e, sort_keys=True, ensure_ascii=False)
                                for e in entrees) + "\n", encoding="utf-8")
    _, anomalies = ac.verify_chain(journal)
    assert anomalies, "la suppression d'une entree doit etre detectee"


# ── Le mode strict, qui refuse un journal non prouvable ───────────────────────


def test_sans_cle_le_mode_strict_refuse_d_ecrire(tmp_path, journal, monkeypatch):
    """Sans cle, le HMAC degenere en constante et le journal cesse d'etre opposable.
    Ecrire quand meme reviendrait a produire une preuve qui n'en est pas une."""
    monkeypatch.setenv("AUDIT_HMAC_KEY_PATH", str(tmp_path / "absente.key"))
    monkeypatch.setenv("AUDIT_HMAC_STRICT", "1")
    with pytest.raises(ac.HMACKeyMissingError):
        ac.append_event("agent.start", {}, session="S1", events_path=journal)
    assert not journal.exists(), "aucun fichier ne doit etre cree"


def test_sans_cle_le_mode_strict_refuse_aussi_de_verifier(tmp_path, journal, monkeypatch):
    monkeypatch.setenv("AUDIT_HMAC_KEY_PATH", str(tmp_path / "absente.key"))
    monkeypatch.setenv("AUDIT_HMAC_STRICT", "1")
    with pytest.raises(ac.HMACKeyMissingError):
        ac.verify_chain(journal)


def test_le_mode_degrade_doit_etre_demande_explicitement(tmp_path, journal, monkeypatch):
    """Le mode degrade existe pour l'amorcage. Il ne s'active jamais tout seul, et ce
    qu'il produit n'est pas inviolable : seul le chainage prev_hash tient, et n'importe
    qui peut le recalculer."""
    monkeypatch.setenv("AUDIT_HMAC_KEY_PATH", str(tmp_path / "absente.key"))
    monkeypatch.setenv("AUDIT_HMAC_STRICT", "0")
    ac.append_event("agent.start", {}, session="S1", events_path=journal)
    assert lignes(journal)[0]["hmac"] == "0" * 64


def test_en_mode_degrade_une_modification_passe_le_hmac(tmp_path, journal, monkeypatch):
    """LIMITE CONNUE, et c'est la raison d'etre du mode strict. Sans cle, quelqu'un qui
    modifie une entree peut recalculer le chainage et le HMAC constant : rien ne le
    trahit. La securite vient de la cle, pas du chainage."""
    monkeypatch.setenv("AUDIT_HMAC_KEY_PATH", str(tmp_path / "absente.key"))
    monkeypatch.setenv("AUDIT_HMAC_STRICT", "0")
    for i in range(2):
        ac.append_event("agent.write", {"n": i}, session="S1", events_path=journal)
    entrees = lignes(journal)
    entrees[0]["payload"]["n"] = 999
    entrees[0]["hmac"] = "0" * 64
    entrees[1]["prev_hash"] = ac._record_hash(entrees[0])
    entrees[1]["hmac"] = "0" * 64
    journal.write_text("\n".join(json.dumps(e, sort_keys=True, ensure_ascii=False)
                                for e in entrees) + "\n", encoding="utf-8")
    n_valides, anomalies = ac.verify_chain(journal)
    assert anomalies == [] and n_valides == 2


# ── Les chemins fail-open trouves par la revue du 2026-09-11 ──────────────────


def test_sans_verrou_l_ecriture_est_refusee(cle, journal, monkeypatch):
    """Une cle presente ne compense pas un verrou absent : ce sont deux preconditions
    distinctes. Sans section critique, deux ecrivains lisent le meme prev_hash et la
    chaine diverge. Le module avalait l'echec de flock et ecrivait quand meme."""
    monkeypatch.setattr(ac, "_HAS_FCNTL", False)
    with pytest.raises(ac.AuditLockUnavailableError):
        ac.append_event("agent.write", {}, session="S1", events_path=journal)
    assert not journal.exists() or journal.read_text(encoding="utf-8") == ""


def test_un_verrou_impossible_a_prendre_refuse(cle, journal, monkeypatch):
    def refuse(*a, **k):
        raise OSError("verrou indisponible")
    monkeypatch.setattr(ac.fcntl, "flock", refuse)
    with pytest.raises(ac.AuditLockUnavailableError):
        ac.append_event("agent.write", {}, session="S1", events_path=journal)


def test_une_queue_corrompue_refuse_un_nouvel_append(cle, journal):
    """Un journal dont la derniere ligne est illisible a une histoire inconnue. Le module
    lisait None, le confondait avec un fichier vide, et repartait d'une genese."""
    ac.append_event("agent.write", {"n": 0}, session="S1", events_path=journal)
    journal.write_bytes(journal.read_bytes() + b'{"tronque": ')
    with pytest.raises(ac.AuditTrailCorruptError):
        ac.append_event("agent.write", {"n": 1}, session="S1", events_path=journal)
    assert len(journal.read_text(encoding="utf-8").splitlines()) == 2


def test_un_fsync_qui_echoue_est_remonte(cle, journal, monkeypatch):
    """Le README compte la durabilite parmi ses garanties. Une garantie dont l'echec est
    avale n'en est pas une."""
    def refuse(_fd):
        raise OSError("disque plein")
    monkeypatch.setattr(ac.os, "fsync", refuse)
    with pytest.raises(ac.AuditDurabilityError):
        ac.append_event("agent.write", {}, session="S1", events_path=journal)


def test_deux_ecrivains_concurrents_produisent_une_chaine_lineaire(cle, journal):
    """La garantie de concurrence etait affirmee et jamais exercee. Quatre processus,
    dix ajouts chacun : quarante entrees, une seule chaine, zero anomalie."""
    import multiprocessing as mp

    def ajoute(chemin, cle_path, n):
        import os as _os, sys as _sys
        _os.environ["AUDIT_HMAC_KEY_PATH"] = str(cle_path)
        _os.environ["AUDIT_HMAC_STRICT"] = "1"
        _sys.path.insert(0, str(Path(chemin).parent.parent))
        import audit_chain as _ac
        for i in range(10):
            _ac.append_event("agent.write", {"i": i}, session="S1", events_path=Path(chemin))

    procs = [mp.Process(target=ajoute, args=(str(journal), str(cle), i)) for i in range(4)]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=60)

    entrees = lignes(journal)
    assert len(entrees) == 40, f"{len(entrees)} entrees au lieu de 40"
    n_valides, anomalies = ac.verify_chain(journal)
    assert anomalies == [], f"chaine rompue : {anomalies}"
    assert n_valides == 40
    assert len({e["event_id"] for e in entrees}) == 40


# ── Limite connue, livree comme test qui passe ────────────────────────────────


def test_limite_supprimer_la_fin_du_journal_reste_indetectable(cle, journal):
    """LIMITE CONNUE ET STRUCTURELLE. Un prefixe de chaine valide reste une chaine valide.

    Supprimer une entree du milieu casse le lien de sa suivante et se voit. Supprimer les
    dernieres n'en casse aucun : rien dans le fichier ne dit qu'elles ont existe. C'est la
    limite d'une chaine de hachage sans engagement externe sur la tete attendue, et c'est
    aussi l'attaque la plus probable sur un journal d'audit, puisqu'elle efface les
    dernieres actions. La fermer demande une ancre hors du fichier.
    """
    for i in range(5):
        ac.append_event("agent.write", {"i": i}, session="S1", events_path=journal)
    l = journal.read_text(encoding="utf-8").splitlines(keepends=True)
    journal.write_text("".join(l[:3]), encoding="utf-8")
    n_valides, anomalies = ac.verify_chain(journal)
    assert (n_valides, anomalies) == (3, [])


def test_limite_un_journal_absent_se_lit_comme_propre(cle, journal):
    """LIMITE CONNUE, meme cause. Sans compteur attendu, un journal absent est
    indiscernable d'un journal jamais ecrit."""
    assert ac.verify_chain(journal) == (0, [])


def test_une_cle_trop_courte_est_refusee(tmp_path, journal, monkeypatch):
    """Une cle d'un octet se devine, et un journal signe avec une cle devinable n'est pas
    opposable. Le module acceptait n'importe quelle taille."""
    k = tmp_path / "courte.key"
    k.write_bytes(b"x")
    monkeypatch.setenv("AUDIT_HMAC_KEY_PATH", str(k))
    monkeypatch.setenv("AUDIT_HMAC_STRICT", "1")
    with pytest.raises(ac.HMACKeyMissingError):
        ac.append_event("agent.start", {}, session="S1", events_path=journal)


# ── Les lecteurs : chemin obligatoire, corruption jamais silencieuse ──────────
#
# Artefact de reduction trouve le 2026-09-11 : `append_event` et `verify_chain` avaient ete
# nettoyes pour rendre le chemin obligatoire dans l'extrait, les deux lecteurs avaient garde
# un repli sur `events_jsonl()`, un resolveur du harnais complet qui n'existe pas ici. Tout
# appel sans chemin explicite mourait sur un NameError.


def test_read_events_exige_un_chemin():
    with pytest.raises(ValueError):
        list(ac.read_events())


def test_read_last_n_events_exige_un_chemin():
    with pytest.raises(ValueError):
        ac.read_last_n_events()


def test_un_lecteur_ne_saute_pas_une_ligne_corrompue_en_silence(tmp_path):
    """Une vue qui omet ce qu'elle n'a pas su lire presente une histoire partielle comme
    si elle etait entiere. Dans un journal d'audit, le silence est le mauvais defaut."""
    journal = tmp_path / "events.jsonl"
    journal.write_text('{"event_kind": "a"}\n{ceci n\'est pas du json}\n{"event_kind": "b"}\n',
                       encoding="utf-8")
    with pytest.raises(ac.AuditTrailCorruptError):
        list(ac.read_events(events_jsonl_path=journal))
    with pytest.raises(ac.AuditTrailCorruptError):
        ac.read_last_n_events(events_jsonl_path=journal)


def test_un_lecteur_non_strict_saute_mais_il_faut_le_demander(tmp_path):
    """Le comportement permissif reste disponible, il cesse d'etre le defaut."""
    journal = tmp_path / "events.jsonl"
    journal.write_text('{"event_kind": "a"}\n{casse}\n{"event_kind": "b"}\n', encoding="utf-8")
    assert len(list(ac.read_events(events_jsonl_path=journal, strict=False))) == 2
    assert len(ac.read_last_n_events(events_jsonl_path=journal, strict=False)) == 2


def test_une_cle_remplacee_par_un_lien_symbolique_est_refusee(tmp_path, monkeypatch):
    """Un lien symbolique fait lire une cle que le proprietaire du chemin n'a pas posee,
    sans que le chemin declare change. Refuse, contrairement aux bits de permission, qui
    ne veulent rien dire sur un montage Windows et dont la limite est ecrite au README."""
    vraie = tmp_path / "ailleurs.key"
    vraie.write_bytes(b"k" * 64)
    lien = tmp_path / "audit.key"
    try:
        lien.symlink_to(vraie)
    except (OSError, NotImplementedError):
        pytest.skip("les liens symboliques ne sont pas disponibles ici")
    monkeypatch.setenv("AUDIT_HMAC_KEY_PATH", str(lien))
    with pytest.raises(ac.HMACKeyMissingError):
        ac._load_key_or_none()


def test_une_cle_ordinaire_de_taille_suffisante_est_acceptee(tmp_path, monkeypatch):
    """Le temoin du test precedent : c'est bien le lien qui est refuse, pas le contenu."""
    cle = tmp_path / "audit.key"
    cle.write_bytes(b"k" * 64)
    monkeypatch.setenv("AUDIT_HMAC_KEY_PATH", str(cle))
    assert ac._load_key_or_none() == b"k" * 64
