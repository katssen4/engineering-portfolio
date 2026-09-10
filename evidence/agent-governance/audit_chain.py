"""Journal d'audit chaine, en append-only, signe en HMAC-SHA256.

EXTRAIT REDUIT du harnais en service, pas le harnais. Ce qui est conserve : la
serialisation canonique, le chainage par prev_hash, la signature HMAC, le verrou
flock sur la section critique, et le mode strict qui refuse d'ecrire un journal
non tamper-evident. Ce qui est retire : le schema d'evenements du harnais, ses
types d'evenements metier, et le module de configuration qui resout les chemins.

Ce fichier tourne seul : `python3 -m pytest tests/test_audit_chain.py`.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import uuid
from datetime import datetime, timezone

SCHEMA_VERSION = "1.0"


def make_uuid() -> str:
    return str(uuid.uuid4())


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

try:
    import fcntl  # type: ignore[import-not-found]

    _HAS_FCNTL = True
except ImportError:
    _HAS_FCNTL = False

_GENESIS_PREV_HASH = "0" * 64

# Une cle plus courte que la sortie de SHA-256 affaiblit le HMAC sans le dire.
_TAILLE_CLE_MINIMALE = 32


class AuditLockUnavailableError(RuntimeError):
    """Le verrou exclusif n'a pas pu etre pris, donc la section critique n'est pas garantie.

    Une cle presente ne compense pas un verrou absent : ce sont deux preconditions
    distinctes. Sans verrou, deux ecrivains concurrents lisent le meme prev_hash et la
    chaine diverge. Refuser est le seul comportement coherent avec le reste du module.
    """


class AuditTrailCorruptError(RuntimeError):
    """La derniere ligne du journal n'est pas du JSON valide.

    Le fichier n'est pas vide, donc il a une histoire, mais cette histoire est illisible :
    ecriture interrompue, corruption disque, retouche manuelle. Etendre un journal dans cet
    etat reviendrait a repartir d'une genese comme si rien n'avait precede.
    """


class AuditDurabilityError(RuntimeError):
    """L'ecriture n'a pas pu etre rendue durable, donc l'appelant ne doit pas la croire ecrite."""


class HMACKeyMissingError(RuntimeError):
    """Levée en mode strict (fail-closed) quand la clé HMAC est absente.

    L'audit trail n'est tamper-evident QUE si chaque record est signé. Sans clé,
    le HMAC dégénère en `0*64` constant et `verify_chain` ne vérifie plus que la
    chaîne `prev_hash` (recalculable par quiconque). Le mode strict refuse
    explicitement cette dégradation silencieuse.
    """


def _resolve_key_path() -> Path:
    """Path clé HMAC — env AUDIT_HMAC_KEY_PATH ou ~/.audit_chain.key."""
    env = os.environ.get("AUDIT_HMAC_KEY_PATH")
    if env:
        return Path(env)
    return Path.home() / ".audit_chain.key"


def _hmac_strict_mode() -> bool:
    """True si le mode strict (fail-closed) est actif — défaut : True (production).

    Désactivable explicitement via `AUDIT_HMAC_STRICT=0` (ou `false`/`no`) —
    réservé au bootstrap initial et aux tests du mode dégradé. En production,
    l'absence de clé doit être une erreur bloquante, pas un warning ignoré.
    """
    raw = os.environ.get("AUDIT_HMAC_STRICT", "1").strip().lower()
    return raw not in {"0", "false", "no", "off", ""}


def _load_key_or_none() -> bytes | None:
    """Charge la clé HMAC.

    Mode strict (défaut, fail-closed) : clé absente → `HMACKeyMissingError`.
    Mode dégradé (`AUDIT_HMAC_STRICT=0`) : clé absente → `None` + warning STDERR
    (chaîne `prev_hash` seule, NON tamper-evident — usage bootstrap/tests uniquement).
    """
    key_path = _resolve_key_path()
    if not key_path.exists():
        if _hmac_strict_mode():
            raise HMACKeyMissingError(
                f"HMAC key absente ({key_path}) — audit trail non signable. "
                f"Mode strict (fail-closed) actif : refus d'écrire un trail "
                f"non tamper-evident. Génère la clé via la commande donnee au README, "
                f"ou désactive explicitement via AUDIT_HMAC_STRICT=0 "
                f"(bootstrap/tests uniquement)."
            )
        print(
            f"[audit] WARNING — HMAC key absente ({key_path}) : mode dégradé "
            f"explicite (AUDIT_HMAC_STRICT=0), chain NON tamper-evident",
            file=sys.stderr,
        )
        return None
    cle = key_path.read_bytes()
    if len(cle) < _TAILLE_CLE_MINIMALE:
        raise HMACKeyMissingError(
            f"cle HMAC de {len(cle)} octet(s) dans {key_path} : en dessous du minimum de "
            f"{_TAILLE_CLE_MINIMALE}. Une cle courte se devine, et un journal signe avec une "
            f"cle devinable n'est pas opposable.")
    return cle


def _canonical_payload(record: dict[str, Any]) -> bytes:
    """Sérialisation JSON déterministe sans champ hmac (meme serialisation des deux cotes)."""
    payload = {k: v for k, v in record.items() if k != "hmac"}
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _record_hash(record: dict[str, Any]) -> str:
    """SHA-256 hex du record sérialisé canonique (inclut hmac — chain integrity)."""
    serialized = json.dumps(
        record, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def _compute_hmac(record_no_hmac: dict[str, Any], key: bytes | None) -> str:
    """HMAC-SHA256 hex digest — mode dégradé retourne 0*64 si key absente."""
    if key is None:
        return "0" * 64
    return hmac.new(key, _canonical_payload(record_no_hmac), hashlib.sha256).hexdigest()


def _read_last_record(path: Path) -> dict[str, Any] | None:
    """Lit la dernière ligne JSON d'events.jsonl — None si fichier vide/absent.

    NOTE : lecture non verrouillée — ne PAS utiliser dans `append_event` (race de
    chaînage sous multi-writer). Réservé aux lecteurs hors écriture.
    """
    if not path.exists() or path.stat().st_size == 0:
        return None
    with open(path, "rb") as f:
        return _read_last_record_from_handle(f)


def _derniere_ligne_brute(handle: Any) -> bytes | None:
    """Derniere ligne non vide, sans tenter de la decoder. Rend None si le fichier est vide.

    Sert a distinguer « journal vide » de « journal dont la queue est illisible », deux
    situations que `_read_last_record_from_handle` confondait en rendant None pour les deux.
    """
    handle.seek(0)
    derniere: bytes | None = None
    for brut in handle:
        if brut.strip():
            derniere = brut.strip()
    handle.seek(0, os.SEEK_END)
    return derniere


def _read_last_record_from_handle(handle: Any) -> dict[str, Any] | None:
    """Lit la dernière ligne JSON depuis un handle binaire DÉJÀ ouvert et positionné.

    Le handle doit être ouvert en mode binaire (`rb`/`a+b`). On rembobine en tête,
    on parcourt jusqu'à la dernière ligne non vide, puis on repositionne le curseur
    en fin de fichier (pour qu'un `write` ultérieur reste un append correct).
    Utilisé par `append_event` sous verrou `flock` — lecture + écriture atomiques.
    """
    handle.seek(0)
    last: bytes | None = None
    for raw in handle:
        stripped = raw.strip()
        if stripped:
            last = stripped
    handle.seek(0, os.SEEK_END)
    if last is None:
        return None
    try:
        return json.loads(last.decode("utf-8"))
    except json.JSONDecodeError:
        return None


def append_event(
    event_type: str,
    payload: dict[str, Any],
    *,
    session: str,
    worker_id: str | None = None,
    cmd_id: str | None = None,
    events_path: Path | None = None,
) -> str:
    """Append event JSONL chained — retourne hmac hex (event_hash) schema du journal."""
    event_kind = str(event_type)

    if events_path is None:
        raise ValueError("events_path est obligatoire dans cet extrait")
    target = events_path
    target.parent.mkdir(parents=True, exist_ok=True)

    # Chargé AVANT d'ouvrir/verrouiller le fichier : en mode strict, l'absence de
    # clé lève HMACKeyMissingError ici — pas de fichier vide créé, pas de verrou
    # pris inutilement.
    key = _load_key_or_none()

    # --- Section critique : lecture du dernier record + calcul prev_hash +
    # écriture, le tout sous UN SEUL verrou flock exclusif (race de chainage sous multi-writer).
    # Le fichier est ouvert en mode 'a+b' : 'a' garantit que tout write est un
    # append atomique au niveau OS ; '+' autorise la lecture du dernier record.
    # Verrou pris AVANT _read_last_record_from_handle → 2 writers concurrents ne
    # peuvent plus lire le même prev_hash puis diverger.
    with open(target, "a+b") as f:
        if not _HAS_FCNTL:
            raise AuditLockUnavailableError(
                "verrouillage de fichier indisponible sur cette plateforme : refus d'ecrire "
                "un journal multi-ecrivains sans section critique")
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        except OSError as exc:
            raise AuditLockUnavailableError(
                f"verrou exclusif impossible a prendre : {exc}") from exc

        derniere_brute = _derniere_ligne_brute(f)
        last_record = _read_last_record_from_handle(f)
        if derniere_brute is not None and last_record is None:
            raise AuditTrailCorruptError(
                "la derniere ligne du journal n'est pas du JSON valide : refus d'etendre "
                "un journal dont l'etat precedent est inconnu")
        prev_hash = (
            _record_hash(last_record) if last_record else _GENESIS_PREV_HASH
        )

        record: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "event_id": make_uuid(),
            "event_kind": event_kind,
            "timestamp_utc": utc_now_iso(),
            "session": session,
            "payload": payload,
            "prev_hash": prev_hash,
        }
        if worker_id is not None:
            record["worker_id"] = worker_id
        if cmd_id is not None:
            record["cmd_id"] = cmd_id

        record["hmac"] = _compute_hmac(record, key)

        line = json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n"
        # Curseur déjà en fin de fichier (SEEK_END posé par
        # _read_last_record_from_handle) ; le mode 'a' le garantit de toute façon.
        f.write(line.encode("utf-8"))
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError as exc:
            raise AuditDurabilityError(
                f"fsync a echoue, l'ajout n'est pas garanti durable : {exc}") from exc
        # flock libéré à la fermeture du handle (sortie du with).
    return record["hmac"]


def verify_chain(events_jsonl_path: Path | None = None) -> tuple[int, list[str]]:
    """Relit + vérifie chain HMAC + prev_hash — retourne (n_valid, anomalies event_ids).

    Mode strict (défaut) : si la clé HMAC est absente → `HMACKeyMissingError`
    (fail-closed — on ne peut pas attester l'intégrité d'un trail non signable).
    Mode dégradé (`AUDIT_HMAC_STRICT=0`) : vérifie seulement la chaîne
    `prev_hash`, le HMAC est ignoré (`key is None`) — NON tamper-evident.
    """
    if events_jsonl_path is None:
        raise ValueError("events_jsonl_path est obligatoire dans cet extrait")
    target = events_jsonl_path
    # Clé vérifiée AVANT l'existence du fichier : en mode strict, l'absence de clé
    # est un défaut de configuration de l'audit (fail-closed), indépendant du fait
    # que le trail soit encore vide. Avec clé présente, fichier absent → (0, []).
    key = _load_key_or_none()
    if not target.exists():
        return (0, [])

    n_valid = 0
    anomalies: list[str] = []
    prev_record: dict[str, Any] | None = None

    with open(target, "r", encoding="utf-8") as f:
        for line_no, raw in enumerate(f, start=1):
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                anomalies.append(f"line_{line_no}_invalid_json")
                continue

            event_id = record.get("event_id", f"line_{line_no}")
            expected_prev = (
                _record_hash(prev_record) if prev_record else _GENESIS_PREV_HASH
            )
            if record.get("prev_hash") != expected_prev:
                anomalies.append(event_id)
                prev_record = record
                continue

            stored_hmac = record.get("hmac", "")
            recomputed = _compute_hmac(record, key)
            if key is not None and not hmac.compare_digest(stored_hmac, recomputed):
                anomalies.append(event_id)
                prev_record = record
                continue

            n_valid += 1
            prev_record = record

    return (n_valid, anomalies)


def read_events(
    filter_type: str | None = None,
    filter_session: str | None = None,
    events_jsonl_path: Path | None = None,
) -> Iterator[dict[str, Any]]:
    """Itérateur lazy events filtrés par event_kind/session — saute lignes invalides."""
    target = events_jsonl_path if events_jsonl_path is not None else events_jsonl()
    if not target.exists():
        return
    with open(target, "r", encoding="utf-8") as f:
        for raw in f:
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if filter_type is not None and record.get("event_kind") != filter_type:
                continue
            if filter_session is not None and record.get("session") != filter_session:
                continue
            yield record


def read_last_n_events(
    n: int = 10, events_jsonl_path: Path | None = None
) -> list[dict[str, Any]]:
    """Lit dernières N events (deque maxlen pour grand fichier)."""
    from collections import deque

    target = events_jsonl_path if events_jsonl_path is not None else events_jsonl()
    if not target.exists():
        return []
    buffer: deque[dict[str, Any]] = deque(maxlen=max(n, 0))
    with open(target, "r", encoding="utf-8") as f:
        for raw in f:
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                buffer.append(json.loads(stripped))
            except json.JSONDecodeError:
                continue
    return list(buffer)
