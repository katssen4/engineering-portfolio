#!/usr/bin/env python3
"""Replay, for real, what the harness demo in the README shows.

Every line printed here comes from the two governance extracts running on the example data
shipped with them. Nothing is typed by hand: the GIF in assets/demos/harness.gif is a
recording of this script's output.

    python3 tools/demo_harness.py

Standard library only. Works in a temporary directory and removes it at the end.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
GOUV = RACINE / "evidence" / "agent-governance"
EXEMPLE = GOUV / "example" / "prompt_avec_scope.md"


def montrer(commande: str) -> None:
    print(f"$ {commande}", flush=True)


def lancer(args: list[str], env: dict[str, str] | None = None) -> None:
    """Lance une commande reelle et recopie sa sortie telle quelle."""
    r = subprocess.run(args, capture_output=True, text=True, cwd=GOUV, env=env)
    sortie = (r.stdout + r.stderr).rstrip()
    if sortie:
        print(sortie, flush=True)
    print(f"(exit {r.returncode})", flush=True)
    print(flush=True)


def scope() -> None:
    print("# The prompt declares what this agent may write", flush=True)
    montrer("sed -n '/<écriture>/,/<\\/interdit>/p' example/prompt_avec_scope.md")
    texte = EXEMPLE.read_text(encoding="utf-8")
    debut = texte.index("  <écriture>")
    fin = texte.index("</interdit>") + len("</interdit>")
    print(texte[debut:fin], flush=True)
    print(flush=True)

    print("# A commit inside the scope passes", flush=True)
    montrer("scope_guard.py --prompt example/prompt_avec_scope.md --staged src/ingestion/connectors/metrics.py")
    lancer([sys.executable, "scope_guard.py", "--prompt", str(EXEMPLE),
            "--staged", "src/ingestion/connectors/metrics.py"])

    print("# The agent also touched the auth module: refused", flush=True)
    montrer("scope_guard.py --prompt example/prompt_avec_scope.md --staged src/ingestion/connectors/metrics.py src/auth/session.py")
    lancer([sys.executable, "scope_guard.py", "--prompt", str(EXEMPLE),
            "--staged", "src/ingestion/connectors/metrics.py", "src/auth/session.py"])


def audit(dossier: Path) -> None:
    sys.path.insert(0, str(GOUV))
    import audit_chain as ac  # noqa: E402

    journal = dossier / "events.jsonl"
    cle = dossier / "audit.key"

    print("# The audit log refuses to write without its signing key", flush=True)
    os.environ["AUDIT_HMAC_KEY_PATH"] = str(dossier / "absent.key")
    montrer("append_event('commit', ...)   # no key present")
    try:
        ac.append_event("commit", {"files": 1}, session="W3", events_path=journal)
        print("written (this should not happen)", flush=True)
    except ac.HMACKeyMissingError:
        print("HMACKeyMissingError: no signing key, the log is not writable", flush=True)
    print(f"log file created: {'yes' if journal.exists() else 'no'}", flush=True)
    print(flush=True)

    print("# With the key: three events, each signed and chained to the previous one", flush=True)
    cle.write_bytes(os.urandom(32))
    os.environ["AUDIT_HMAC_KEY_PATH"] = str(cle)
    for i, fichier in enumerate(["metrics.py", "__init__.py", "test_metrics_connector.py"], 1):
        h = ac.append_event("commit", {"file": fichier}, session="W3", events_path=journal)
        print(f"event {i}  {fichier:<28} hmac {h[:16]}...", flush=True)
    montrer("verify_chain(events.jsonl)")
    n, erreurs = ac.verify_chain(journal)
    print(f"{n} events, {len(erreurs)} error(s): chain intact", flush=True)
    print(flush=True)

    print("# Someone edits the second event after the fact", flush=True)
    lignes = journal.read_text(encoding="utf-8").splitlines()
    evenement = json.loads(lignes[1])
    cle_payload = "payload" if "payload" in evenement else next(k for k in evenement if isinstance(evenement[k], dict))
    evenement[cle_payload]["file"] = "src/auth/session.py"
    lignes[1] = json.dumps(evenement, ensure_ascii=False)
    journal.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    montrer("verify_chain(events.jsonl)")
    ids = [json.loads(l).get("event_id") for l in lignes]
    n, erreurs = ac.verify_chain(journal)
    print(f"{n} event(s) valid, {len(erreurs)} flagged:", flush=True)
    for e in erreurs:
        rang = ids.index(e) + 1 if e in ids else "?"
        motif = "signature no longer matches" if rang == 2 else "chain broken after the edit"
        print(f"  event {rang}: {motif}", flush=True)


def main() -> int:
    scope()
    with tempfile.TemporaryDirectory() as tmp:
        audit(Path(tmp))
    return 0


if __name__ == "__main__":
    sys.exit(main())
