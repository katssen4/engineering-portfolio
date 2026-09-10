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
    k.write_bytes(b"une cle de test, 32 octets ....")
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
