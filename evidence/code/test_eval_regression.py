"""Unit tests for eval_regression pure functions (G9). No corpus needed.

Covers: compute_integrity_hash / verify_lock (round-trip + tamper-detect) and
is_regression (delta boundary + significance gate). Importable directly because
bench/runners has an __init__.py and is on sys.path via the test's own location.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make `bench/runners` importable regardless of pytest rootdir.
_RUNNERS_DIR = Path(__file__).resolve().parent
if str(_RUNNERS_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNNERS_DIR))

import eval_regression as er  # noqa: E402


# ── compute_integrity_hash / verify_lock ────────────────────────────────────────
def _sample_payload() -> dict:
    return {
        "schema": "ariane_baseline_lock_1.0",
        "session": "S2",
        "regression_policy": {"primary_metric": "ndcg@10", "delta_abs": 0.01},
        "baselines": {"B": {"ndcg@10": 0.42, "n_queries": 100}},
    }


def test_integrity_hash_is_deterministic_and_ignores_hash_field():
    payload = _sample_payload()
    h1 = er.compute_integrity_hash(payload)
    # Adding the hash field back must not change the recomputed hash.
    payload_with_hash = dict(payload, integrity_hash=h1)
    h2 = er.compute_integrity_hash(payload_with_hash)
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_integrity_hash_changes_on_payload_mutation():
    payload = _sample_payload()
    h1 = er.compute_integrity_hash(payload)
    mutated = dict(payload)
    mutated["baselines"] = {"B": {"ndcg@10": 0.99, "n_queries": 100}}
    assert er.compute_integrity_hash(mutated) != h1


def test_verify_lock_roundtrip_ok(tmp_path):
    payload = _sample_payload()
    payload["integrity_hash"] = er.compute_integrity_hash(payload)
    lock = tmp_path / "baseline_lock.json"
    lock.write_text(json.dumps(payload), encoding="utf-8")
    ok, msg = er.verify_lock(lock)
    assert ok is True
    assert "OK" in msg


def test_verify_lock_detects_tamper(tmp_path):
    payload = _sample_payload()
    payload["integrity_hash"] = er.compute_integrity_hash(payload)
    # Tamper with a value AFTER sealing — the stored hash no longer matches.
    payload["baselines"]["B"]["ndcg@10"] = 0.00
    lock = tmp_path / "baseline_lock.json"
    lock.write_text(json.dumps(payload), encoding="utf-8")
    ok, msg = er.verify_lock(lock)
    assert ok is False
    assert "BROKEN" in msg


def test_verify_lock_missing_file(tmp_path):
    ok, msg = er.verify_lock(tmp_path / "nope.json")
    assert ok is False
    assert "missing" in msg


def test_verify_lock_unsealed_null_hash(tmp_path):
    payload = _sample_payload()
    payload["integrity_hash"] = None  # placeholder — not sealed
    lock = tmp_path / "baseline_lock.json"
    lock.write_text(json.dumps(payload), encoding="utf-8")
    ok, msg = er.verify_lock(lock)
    assert ok is False
    assert "not sealed" in msg


# ── is_regression (delta boundary + significance gate) ───────────────────────────
_POLICY_SIG = {"delta_abs": 0.01, "require_significance": True, "max_p": 0.05}
_POLICY_NOSIG = {"delta_abs": 0.01, "require_significance": False, "max_p": 0.05}

#: S31 L9 — the delta-boundary tests below state no regime on either side, and since the
#: reviewer's *« absent can only mean legacy »* objection an unstated regime RAISES instead of
#: resolving. These six tests are about the arithmetic, so they DECLARE that both their numbers
#: stand for pre-marker records. The declaration is the point: it is written, not assumed.
_LEGACY = {"current_is_legacy": True, "baseline_is_legacy": True}


def test_no_regression_when_within_delta():
    # Drop of 0.005 < delta_abs 0.01 → not a regression regardless of p.
    assert er.is_regression(0.415, 0.420, _POLICY_SIG, p_value=0.001, **_LEGACY) is False


def test_regression_when_past_delta_and_significant():
    # Drop of 0.05 > delta and p < max_p → regression.
    assert er.is_regression(0.370, 0.420, _POLICY_SIG, p_value=0.001, **_LEGACY) is True


def test_no_regression_past_delta_but_not_significant():
    # Drop past delta but p >= max_p → not significant → not a regression.
    assert er.is_regression(0.370, 0.420, _POLICY_SIG, p_value=0.20, **_LEGACY) is False


def test_significance_required_but_no_p_value_does_not_flag():
    # Past delta, significance required, but no p_value supplied → cannot prove → no flag.
    assert er.is_regression(0.370, 0.420, _POLICY_SIG, p_value=None, **_LEGACY) is False


def test_regression_past_delta_when_significance_not_required():
    # Significance not required → δ leg alone trips the gate.
    assert er.is_regression(0.370, 0.420, _POLICY_NOSIG, p_value=None, **_LEGACY) is True


def test_delta_boundary_exactly_at_threshold_is_not_regression():
    # current == baseline - delta_abs exactly → NOT strictly less → no regression.
    assert er.is_regression(0.410, 0.420, _POLICY_NOSIG, p_value=None, **_LEGACY) is False


# ── run step wiring (S3 B1: GitBugs pilot) ───────────────────────────────────────
def test_run_current_metrics_uningested_collection_raises():
    # Collections other than B are not ingested yet (ADR-0004 pilot = B) → still a stub.
    with pytest.raises(NotImplementedError):
        er.run_current_metrics({}, "A", seed=13, policy=_POLICY_SIG)


def test_run_current_metrics_B_is_wired_to_real_pipeline():
    """B dispatches to run_pilot. With the slice ingested it returns the gate dict;
    in a clean checkout the heavy corpus is gitignored → FileNotFoundError. Either
    outcome proves the stub is gone and the wiring reaches the real pipeline; only the
    old NotImplementedError stub is now a failure for B."""
    repo_root = Path(__file__).resolve().parents[2]
    corpus = repo_root / "corpus" / "processed" / "B_gitbugs_corpus.jsonl"
    if not corpus.exists():
        with pytest.raises(FileNotFoundError):
            er.run_current_metrics({}, "B", seed=13, policy=_POLICY_SIG)
        return
    metrics = er.run_current_metrics({}, "B", seed=13, policy=_POLICY_SIG)
    assert set(metrics) >= {"ndcg@10", "mrr", "recall@100", "n_queries", "per_query"}
    assert 0.0 <= metrics["ndcg@10"] <= 1.0
    assert metrics["n_queries"] > 0
    assert len(metrics["per_query"]) == metrics["n_queries"]


# ── verify_manifest_hashes: seal discipline = qrels-only (S6 J1.4) ───────────────
# These three are the cold-clone proof of the seal: a sealed collection whose
# regenerable (gitignored) file is ABSENT must still PASS, while a committed file
# whose sha256 is tampered must FAIL. Pure-stdlib, no corpus needed.
def _write_file(path: Path, data: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _sealed_manifest_with_files(repo_root: Path, files: list[dict]) -> dict:
    return {
        "manifest_version": "1.0",
        "collections": [
            {
                "collection_id": "B",
                "dataset_id": "gitbugs",
                "status": "active",
                "source": {"url": "x", "license": "CC BY 4.0"},
                "sealed": True,
                "qrels_provenance_ref": "x",
                "files": files,
            }
        ],
    }


def test_verify_manifest_passes_when_regenerable_file_absent(tmp_path, monkeypatch):
    """T7(a) — sealed collection + a regenerable file that does NOT exist → verify PASSES.

    This is the whole point of the seal being cold-clone-correct: the gitignored
    corpus/queries JSONL are absent on a fresh checkout and their absence must not trip
    the gate. We rebind verify_manifest_hashes' repo_root (via __file__'s parents[2]) by
    pointing every path at tmp_path: we write ONLY the committed qrels, and leave the
    regenerable corpus file absent.
    """
    repo_root = tmp_path
    # Committed qrels: present + correct sha256 → hard-verified.
    qrels_sha = _write_file(repo_root / "qrels.trec", b"q0 0 d1 1\n")
    files = [
        # Regenerable corpus: NEVER written → absent on disk.
        {
            "role": "corpus",
            "project": "p",
            "path": "corpus.jsonl",
            "sha256": "0" * 64,
            "rows": 1,
            "regenerable": True,
        },
        {
            "role": "qrels",
            "project": "p",
            "path": "qrels.trec",
            "sha256": qrels_sha,
            "rows": 1,
            "regenerable": False,
        },
    ]
    manifest = _sealed_manifest_with_files(repo_root, files)
    # Make verify_manifest_hashes resolve repo_root → tmp_path. It computes
    # Path(__file__).resolve().parents[2]; patch eval_regression.Path so __file__ maps
    # into tmp_path. Simpler: monkeypatch the module's Path resolution by chdir + a
    # fake __file__. We instead patch the function's repo_root via a wrapper file tree.
    fake_module_file = repo_root / "bench" / "runners" / "eval_regression.py"
    fake_module_file.parent.mkdir(parents=True, exist_ok=True)
    fake_module_file.write_text("# placeholder for __file__ resolution\n")
    monkeypatch.setattr(er, "__file__", str(fake_module_file))
    ok, msg = er.verify_manifest_hashes(manifest, "B")
    assert ok is True, msg
    assert "1 verified" in msg
    assert "1 regenerable skipped" in msg


def test_verify_manifest_fails_on_tampered_committed_qrels(tmp_path, monkeypatch):
    """T7(b) — committed qrels with a MISMATCHED sha256 → verify FAILS (tamper-detect).

    The committed .trec is the seal's tamper-detection anchor; a recorded sha256 that
    does not match the on-disk bytes must hard-fail.
    """
    repo_root = tmp_path
    _write_file(repo_root / "qrels.trec", b"q0 0 d1 1\n")  # real bytes
    files = [
        {
            "role": "qrels",
            "project": "p",
            "path": "qrels.trec",
            "sha256": "f" * 64,  # WRONG sha → tamper
            "rows": 1,
            "regenerable": False,
        },
    ]
    manifest = _sealed_manifest_with_files(repo_root, files)
    fake_module_file = repo_root / "bench" / "runners" / "eval_regression.py"
    fake_module_file.parent.mkdir(parents=True, exist_ok=True)
    fake_module_file.write_text("# placeholder\n")
    monkeypatch.setattr(er, "__file__", str(fake_module_file))
    ok, msg = er.verify_manifest_hashes(manifest, "B")
    assert ok is False
    assert "mismatch" in msg


def test_verify_manifest_fails_on_missing_committed_qrels(tmp_path, monkeypatch):
    """T7(b′) — a committed (non-regenerable) file that is ABSENT → verify FAILS.

    Mirror of (a): for committed files, absence IS a failure (the .trec must be present
    and hashed). Guards the asymmetry between regenerable (absence ok) and committed
    (absence fatal)."""
    repo_root = tmp_path
    files = [
        {
            "role": "qrels",
            "project": "p",
            "path": "qrels.trec",  # never written → absent
            "sha256": "a" * 64,
            "rows": 1,
            "regenerable": False,
        },
    ]
    manifest = _sealed_manifest_with_files(repo_root, files)
    fake_module_file = repo_root / "bench" / "runners" / "eval_regression.py"
    fake_module_file.parent.mkdir(parents=True, exist_ok=True)
    fake_module_file.write_text("# placeholder\n")
    monkeypatch.setattr(er, "__file__", str(fake_module_file))
    ok, msg = er.verify_manifest_hashes(manifest, "B")
    assert ok is False
    assert "missing" in msg


def test_reseal_preserves_baselines_and_verify_passes_after(tmp_path):
    """T7(c) — re-seal preserves baselines (B ndcg@10 == 0.489051) and verify_lock passes.

    Sealing flips the flag + recomputes the hash; it must NEVER perturb a recorded score.
    """
    payload = {
        "schema": "ariane_baseline_lock_1.0",
        "session": "S5",
        "sealed": True,
        "regression_policy": {"primary_metric": "ndcg@10", "delta_abs": 0.01},
        "baselines": {
            "B": {"ndcg@10": 0.489051, "mrr": 0.462411, "recall@100": 0.769868, "n_queries": 302}
        },
    }
    lock = tmp_path / "baseline_lock.json"
    lock.write_text(json.dumps(payload), encoding="utf-8")
    # Re-seal via the sanctioned path.
    rc = er._reseal(lock, session="S6")
    assert rc == er.EXIT_OK
    resealed = json.loads(lock.read_text(encoding="utf-8"))
    # Baselines numerically identical — the score is untouched.
    assert resealed["baselines"]["B"]["ndcg@10"] == 0.489051
    assert resealed["baselines"]["B"]["mrr"] == 0.462411
    assert resealed["baselines"]["B"]["recall@100"] == 0.769868
    assert resealed["session"] == "S6"
    # verify_lock passes against the freshly sealed payload.
    ok, msg = er.verify_lock(lock)
    assert ok is True, msg
    # And a post-seal tamper of the score breaks the hash (sealing really anchors it).
    resealed["baselines"]["B"]["ndcg@10"] = 0.0
    lock.write_text(json.dumps(resealed), encoding="utf-8")
    ok2, _ = er.verify_lock(lock)
    assert ok2 is False


# ── verify_manifest_hashes: A-seal (S17 L2_SEAL_A) ───────────────────────────────
# Mirror of T7(a/b/b') above — same mechanism, collection_id='A'.
# A is comparability_class=llm_judge, sealed via manifest hashes + sealed:true ONLY
# (never via baseline_lock). Seal discipline = qrels-only (regenerable:false for the
# single .trec; the 2 JSONL carry regenerable:true → skipped by cold-clone-correct gate).

def _sealed_manifest_A_with_files(repo_root: Path, files: list[dict]) -> dict:
    return {
        "manifest_version": "1.0",
        "collections": [
            {
                "collection_id": "A",
                "dataset_id": "zenodo-7384758-itsm",
                "status": "active",
                "source": {"url": "https://zenodo.org/record/7384758", "license": "CC BY 4.0"},
                "sealed": True,
                "comparability_class": "llm_judge",
                "qrels_provenance_ref": "corpus/qrels/A_zenodo7384758_provenance.json",
                "files": files,
            }
        ],
    }


def test_verify_manifest_A_passes_when_regenerable_absent(tmp_path, monkeypatch):
    """T8(a) — A sealed + regenerable JSONL absent → verify PASSES (cold-clone-correct).

    Mirrors T7(a) for collection A. The 2 JSONL (corpus+queries) are gitignored and absent
    on a cold clone; their absence must NOT fail the gate. Only the committed qrels.trec
    is hard-verified.
    """
    repo_root = tmp_path
    qrels_sha = _write_file(repo_root / "A_qrels.trec", b"q1 0 d1 1\n")
    files = [
        {
            "role": "corpus",
            "path": "A_corpus.jsonl",
            "sha256": "0" * 64,
            "rows": 2229,
            "regenerable": True,
        },
        {
            "role": "queries",
            "path": "A_queries.jsonl",
            "sha256": "0" * 64,
            "rows": 150,
            "regenerable": True,
        },
        {
            "role": "qrels",
            "path": "A_qrels.trec",
            "sha256": qrels_sha,
            "rows": 2486,
            "regenerable": False,
        },
    ]
    manifest = _sealed_manifest_A_with_files(repo_root, files)
    fake_module_file = repo_root / "bench" / "runners" / "eval_regression.py"
    fake_module_file.parent.mkdir(parents=True, exist_ok=True)
    fake_module_file.write_text("# placeholder\n")
    monkeypatch.setattr(er, "__file__", str(fake_module_file))
    ok, msg = er.verify_manifest_hashes(manifest, "A")
    assert ok is True, msg
    assert "1 verified" in msg
    assert "2 regenerable skipped" in msg


def test_verify_manifest_A_fails_on_tampered_qrels(tmp_path, monkeypatch):
    """T8(b) — A sealed + committed qrels with WRONG sha256 → verify FAILS (tamper-detect).

    Mirrors T7(b) for collection A. The qrels.trec is the seal anchor; a sha256 mismatch
    must hard-fail regardless of comparability_class.
    """
    repo_root = tmp_path
    _write_file(repo_root / "A_qrels.trec", b"q1 0 d1 1\n")  # real bytes
    files = [
        {
            "role": "qrels",
            "path": "A_qrels.trec",
            "sha256": "f" * 64,  # WRONG sha → tamper
            "rows": 2486,
            "regenerable": False,
        },
    ]
    manifest = _sealed_manifest_A_with_files(repo_root, files)
    fake_module_file = repo_root / "bench" / "runners" / "eval_regression.py"
    fake_module_file.parent.mkdir(parents=True, exist_ok=True)
    fake_module_file.write_text("# placeholder\n")
    monkeypatch.setattr(er, "__file__", str(fake_module_file))
    ok, msg = er.verify_manifest_hashes(manifest, "A")
    assert ok is False
    assert "mismatch" in msg


def test_verify_manifest_A_fails_on_missing_committed_qrels(tmp_path, monkeypatch):
    """T8(b') — A sealed + committed qrels file ABSENT → verify FAILS.

    Mirrors T7(b') for collection A. For committed files absence is fatal (asymmetric
    from regenerable files where absence is allowed).
    """
    repo_root = tmp_path
    files = [
        {
            "role": "qrels",
            "path": "A_qrels.trec",  # never written → absent
            "sha256": "a" * 64,
            "rows": 2486,
            "regenerable": False,
        },
    ]
    manifest = _sealed_manifest_A_with_files(repo_root, files)
    fake_module_file = repo_root / "bench" / "runners" / "eval_regression.py"
    fake_module_file.parent.mkdir(parents=True, exist_ok=True)
    fake_module_file.write_text("# placeholder\n")
    monkeypatch.setattr(er, "__file__", str(fake_module_file))
    ok, msg = er.verify_manifest_hashes(manifest, "A")
    assert ok is False
    assert "missing" in msg


# ── verify_manifest_hashes: C-seal (S17 W3_SEAL_C) ───────────────────────────────
# Mirror of T8(a/b/b') above — same mechanism, collection_id='C'.
# C is comparability_class=native (cross-comparable to B), sealed via manifest hashes +
# sealed:true ONLY (baseline_lock untouched). Seal discipline = qrels-only (regenerable:false
# for the single .trec; the 2 JSONL carry regenerable:true → skipped by cold-clone-correct gate).

def _sealed_manifest_C_with_files(repo_root: Path, files: list[dict]) -> dict:
    return {
        "manifest_version": "1.0",
        "collections": [
            {
                "collection_id": "C",
                "dataset_id": "cqadupstack-unix",
                "status": "active",
                "source": {"url": "https://huggingface.co/datasets/BeIR/cqadupstack", "license": "CC BY-SA 4.0"},
                "sealed": True,
                "comparability_class": "native",
                "qrels_provenance_ref": "corpus/qrels/C_cqadupstack_provenance.json",
                "files": files,
            }
        ],
    }


def test_verify_manifest_C_passes_when_regenerable_absent(tmp_path, monkeypatch):
    """T9(a) — C sealed + regenerable JSONL absent → verify PASSES (cold-clone-correct).

    Mirrors T8(a) for collection C. The 2 JSONL (corpus+queries) are gitignored and absent
    on a cold clone; their absence must NOT fail the gate. Only the committed qrels.trec
    is hard-verified.
    """
    repo_root = tmp_path
    qrels_sha = _write_file(repo_root / "C_qrels.trec", b"q1 0 d1 1\n")
    files = [
        {
            "role": "corpus",
            "path": "C_corpus.jsonl",
            "sha256": "0" * 64,
            "rows": 47382,
            "regenerable": True,
        },
        {
            "role": "queries",
            "path": "C_queries.jsonl",
            "sha256": "0" * 64,
            "rows": 150,
            "regenerable": True,
        },
        {
            "role": "qrels",
            "path": "C_qrels.trec",
            "sha256": qrels_sha,
            "rows": 239,
            "regenerable": False,
        },
    ]
    manifest = _sealed_manifest_C_with_files(repo_root, files)
    fake_module_file = repo_root / "bench" / "runners" / "eval_regression.py"
    fake_module_file.parent.mkdir(parents=True, exist_ok=True)
    fake_module_file.write_text("# placeholder\n")
    monkeypatch.setattr(er, "__file__", str(fake_module_file))
    ok, msg = er.verify_manifest_hashes(manifest, "C")
    assert ok is True, msg
    assert "1 verified" in msg
    assert "2 regenerable skipped" in msg


def test_verify_manifest_C_fails_on_tampered_qrels(tmp_path, monkeypatch):
    """T9(b) — C sealed + committed qrels with WRONG sha256 → verify FAILS (tamper-detect).

    Mirrors T8(b) for collection C. The qrels.trec is the seal anchor; a sha256 mismatch
    must hard-fail regardless of comparability_class.
    """
    repo_root = tmp_path
    _write_file(repo_root / "C_qrels.trec", b"q1 0 d1 1\n")  # real bytes
    files = [
        {
            "role": "qrels",
            "path": "C_qrels.trec",
            "sha256": "f" * 64,  # WRONG sha → tamper
            "rows": 239,
            "regenerable": False,
        },
    ]
    manifest = _sealed_manifest_C_with_files(repo_root, files)
    fake_module_file = repo_root / "bench" / "runners" / "eval_regression.py"
    fake_module_file.parent.mkdir(parents=True, exist_ok=True)
    fake_module_file.write_text("# placeholder\n")
    monkeypatch.setattr(er, "__file__", str(fake_module_file))
    ok, msg = er.verify_manifest_hashes(manifest, "C")
    assert ok is False
    assert "mismatch" in msg


def test_verify_manifest_C_fails_on_missing_committed_qrels(tmp_path, monkeypatch):
    """T9(b') — C sealed + committed qrels file ABSENT → verify FAILS.

    Mirrors T8(b') for collection C. For committed files absence is fatal (asymmetric
    from regenerable files where absence is allowed).
    """
    repo_root = tmp_path
    files = [
        {
            "role": "qrels",
            "path": "C_qrels.trec",  # never written → absent
            "sha256": "a" * 64,
            "rows": 239,
            "regenerable": False,
        },
    ]
    manifest = _sealed_manifest_C_with_files(repo_root, files)
    fake_module_file = repo_root / "bench" / "runners" / "eval_regression.py"
    fake_module_file.parent.mkdir(parents=True, exist_ok=True)
    fake_module_file.write_text("# placeholder\n")
    monkeypatch.setattr(er, "__file__", str(fake_module_file))
    ok, msg = er.verify_manifest_hashes(manifest, "C")
    assert ok is False
    assert "missing" in msg


# ── verify_manifest_hashes: C SECOND EVALUATION VIEW (S21, ADR-0009 AUD3-C2/C3) ───
# C carries a second evaluation view over the SAME sealed corpus (ADR-0009): same
# corpus bytes, same collection_id "C", a re-sliced (queries, qrels) pair discriminated
# by an explicit `view` key. Files WITHOUT `view` are the DEFAULT (sealed 150) view.
# Mirror of T9(a/b) above, one level up: the view must have its OWN tamper anchor, and
# selecting a view must never move what the default call verifies.

def _sealed_manifest_C_two_views(files: list[dict]) -> dict:
    return {
        "manifest_version": "1.0",
        "collections": [
            {
                "collection_id": "C",
                "dataset_id": "cqadupstack-unix",
                "status": "active",
                "source": {"url": "https://huggingface.co/datasets/BeIR/cqadupstack", "license": "CC BY-SA 4.0"},
                "sealed": True,
                "comparability_class": "native",
                "qrels_provenance_ref": "corpus/qrels/C_cqadupstack_provenance.json",
                "files": files,
            }
        ],
    }


def _two_view_files(repo_root: Path) -> list[dict]:
    """The sealed C triple + the ADR-0009 view's 3 files, all with REAL sha256 on disk."""
    sealed_sha = _write_file(repo_root / "C_qrels.trec", b"q1 0 d1 1\n")
    view_sha = _write_file(repo_root / "C_view_qrels.trec", b"q1 0 d1 1\nq2 0 d2 1\n")
    primary_sha = _write_file(repo_root / "C_view_primary.json", b'["q2"]\n')
    return [
        {"role": "corpus", "path": "C_corpus.jsonl", "sha256": "0" * 64, "rows": 47382, "regenerable": True},
        {"role": "queries", "path": "C_queries.jsonl", "sha256": "0" * 64, "rows": 150, "regenerable": True},
        {"role": "qrels", "path": "C_qrels.trec", "sha256": sealed_sha, "rows": 239, "regenerable": False},
        {"role": "queries", "view": "judgeable1072", "path": "C_view_queries.jsonl",
         "sha256": "0" * 64, "rows": 1072, "regenerable": True},
        {"role": "qrels", "view": "judgeable1072", "path": "C_view_qrels.trec",
         "sha256": view_sha, "rows": 1693, "regenerable": False},
        {"role": "query_ids", "view": "judgeable1072", "path": "C_view_primary.json",
         "sha256": primary_sha, "rows": 922, "regenerable": False},
    ]


def _rebind_repo_root(repo_root: Path, monkeypatch) -> None:
    fake_module_file = repo_root / "bench" / "runners" / "eval_regression.py"
    fake_module_file.parent.mkdir(parents=True, exist_ok=True)
    fake_module_file.write_text("# placeholder\n")
    monkeypatch.setattr(er, "__file__", str(fake_module_file))


def test_verify_manifest_C_default_call_verifies_BOTH_views(tmp_path, monkeypatch):
    """T9(c) — AUD3-C2: `verify_manifest_hashes(m,'C')` hard-verifies both views' anchors.

    No `view` argument = ALL views, so the single `make eval-verify` line grows to cover
    the new view's qrels + frozen qid list without a Makefile change. 3 committed files
    hard-verified, 3 regenerable JSONL skipped (cold-clone-correct).
    """
    _rebind_repo_root(tmp_path, monkeypatch)
    manifest = _sealed_manifest_C_two_views(_two_view_files(tmp_path))
    ok, msg = er.verify_manifest_hashes(manifest, "C")
    assert ok is True, msg
    assert "3 verified" in msg and "3 regenerable skipped" in msg
    assert "all views" in msg


def test_verify_manifest_C_view_selector_restricts_the_set(tmp_path, monkeypatch):
    """T9(d) — AUD3-C3: an explicit view selects what is verified; DEFAULT_VIEW = sealed only."""
    _rebind_repo_root(tmp_path, monkeypatch)
    manifest = _sealed_manifest_C_two_views(_two_view_files(tmp_path))
    ok, msg = er.verify_manifest_hashes(manifest, "C", view=er.DEFAULT_VIEW)
    assert ok is True and "1 verified" in msg, msg  # the sealed qrels alone
    ok, msg = er.verify_manifest_hashes(manifest, "C", view="judgeable1072")
    assert ok is True and "3 verified" in msg, msg  # shared + the view's 2 anchors


def test_verify_manifest_C_fails_on_tampered_VIEW_qrels(tmp_path, monkeypatch):
    """T9(e) — a tampered VIEW qrels FAILS, while the sealed view's own bytes are intact.

    This is the half of AUD3-C2 that an untouched-seal-only implementation would miss:
    the new qrels needs its own tamper anchor, not just an honest neighbour.
    """
    _rebind_repo_root(tmp_path, monkeypatch)
    files = _two_view_files(tmp_path)
    for f in files:
        if f.get("view") == "judgeable1072" and f["role"] == "qrels":
            f["sha256"] = "f" * 64  # WRONG sha → tamper on the VIEW anchor only
    manifest = _sealed_manifest_C_two_views(files)
    ok, msg = er.verify_manifest_hashes(manifest, "C")
    assert ok is False and "mismatch" in msg and "C_view_qrels.trec" in msg
    # the sealed view alone still verifies — the failure is localised to the new view
    ok_sealed, msg_sealed = er.verify_manifest_hashes(manifest, "C", view=er.DEFAULT_VIEW)
    assert ok_sealed is True, msg_sealed


def test_verify_manifest_C_fails_on_tampered_frozen_primary_list(tmp_path, monkeypatch):
    """T9(f) — the frozen PRIMARY qid list is a tamper anchor too (the sample cannot drift)."""
    _rebind_repo_root(tmp_path, monkeypatch)
    files = _two_view_files(tmp_path)
    for f in files:
        if f["role"] == "query_ids":
            f["sha256"] = "e" * 64
    ok, msg = er.verify_manifest_hashes(_sealed_manifest_C_two_views(files), "C")
    assert ok is False and "mismatch" in msg and "C_view_primary.json" in msg


# ── the scoring-regime guard on the G9 path (S31 — ADR-0013 item 4) ──────────────
# The second of the two gates ADR-0013's item 4 names. G9 compares a freshly scored
# number against the value locked in baseline_lock.json; the lock carries no tie_policy
# and is byte-untouched since S5, so the absent ≡ pre-regime rule is what keeps it gating
# today — and what makes it refuse the day the tie rule moves.

_POST_CHANGE = "expected-over-tie-groups/v1"


def test_is_regression_REFUSES_a_cross_regime_gate():
    """RED — a current number and a locked baseline from two instruments cannot be gated."""
    with pytest.raises(er.ScoringRegimeError, match="REFUSED comparison across scoring regimes"):
        er.is_regression(
            0.370, 0.420, _POLICY_NOSIG,
            current_tie_policy=_POST_CHANGE,
            baseline_tie_policy=None,  # the lock, unmarked = pre-regime — DECLARED, S31 L9
            baseline_is_legacy=True,
        )


def test_is_regression_absent_baseline_versus_current_still_gates():
    """GREEN — the real G9 shape today: unmarked lock vs freshly stamped current."""
    import tie_policy as tp  # noqa: PLC0415 - imported here, next to its only use

    assert er.is_regression(
        0.370, 0.420, _POLICY_NOSIG,
        current_tie_policy=tp.CURRENT_TIE_POLICY,
        baseline_tie_policy=None,
        baseline_is_legacy=True,      # S31 L9 — the lock is a genuine pre-marker artefact
    ) is True
    assert er.is_regression(
        0.415, 0.420, _POLICY_NOSIG,
        current_tie_policy=tp.CURRENT_TIE_POLICY,
        baseline_tie_policy=None,
        baseline_is_legacy=True,
    ) is False


def test_is_regression_default_call_now_REFUSES_an_unstated_regime():
    """RED — **the contract that moved at S31 L9**, and the reason it moved.

    Until this lot, ``is_regression(current, baseline, policy)`` with no marker on either side
    gated happily: both sides resolved to pre-regime, silently. The independent reviewer refused
    that rule as *« too broad »* — a NEW number that forgot its marker is indistinguishable from
    a legacy record to the resolver, and gets filed as pre-regime. The gate now refuses, and a
    caller that really is reading a pre-marker artefact says so (the test below).
    """
    with pytest.raises(er.UnstatedRegimeError, match="REFUSED to resolve the scoring regime"):
        er.is_regression(0.370, 0.420, _POLICY_NOSIG)


def test_is_regression_gates_exactly_as_before_once_the_legacy_read_is_DECLARED():
    """GREEN — the arithmetic did not move; only the declaration is new."""
    assert er.is_regression(0.370, 0.420, _POLICY_NOSIG, **_LEGACY) is True
    assert er.is_regression(0.410, 0.420, _POLICY_NOSIG, **_LEGACY) is False


def test_main_exits_SETUP_ERROR_on_a_mixed_regime(tmp_path, monkeypatch, capsys):
    """RED at gate level — main() refuses to gate and exits 2, never 0 or 1.

    A mixed-regime comparison is a *cannot gate* condition (setup error), not a verdict:
    returning EXIT_OK would bless an incommensurable pass and EXIT_REGRESSION would assert
    a regression nobody measured.
    """
    payload = {
        "schema": "ariane_baseline_lock_1.0",
        "session": "S31",
        "regression_policy": {"primary_metric": "ndcg@10", "delta_abs": 0.01},
        "system": {"seed": 13},
        # No tie_policy here — exactly like the real lock, i.e. pre-regime.
        "baselines": {"B": {"ndcg@10": 0.489051, "n_queries": 302}},
    }
    payload["integrity_hash"] = er.compute_integrity_hash(payload)
    lock = tmp_path / "baseline_lock.json"
    lock.write_text(json.dumps(payload), encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"collections": []}), encoding="utf-8")

    monkeypatch.setattr(er, "verify_manifest_hashes", lambda *a, **k: (True, "stub"))
    monkeypatch.setattr(
        er, "run_current_metrics",
        lambda *a, **k: {"ndcg@10": 0.489051, "p_value": None, "tie_policy": _POST_CHANGE},
    )
    rc = er.main(["--baseline", str(lock), "--manifest", str(manifest), "--collection", "B"])
    assert rc == er.EXIT_SETUP_ERROR
    assert "scoring-regime error" in capsys.readouterr().err


def test_main_gates_normally_when_both_sides_are_one_regime(tmp_path, monkeypatch, capsys):
    """GREEN at gate level — the shape G9 actually runs today: unmarked lock, stamped run."""
    import tie_policy as tp  # noqa: PLC0415

    payload = {
        "schema": "ariane_baseline_lock_1.0",
        "session": "S31",
        "regression_policy": {"primary_metric": "ndcg@10", "delta_abs": 0.01},
        "system": {"seed": 13},
        "baselines": {"B": {"ndcg@10": 0.489051, "n_queries": 302}},
    }
    payload["integrity_hash"] = er.compute_integrity_hash(payload)
    lock = tmp_path / "baseline_lock.json"
    lock.write_text(json.dumps(payload), encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"collections": []}), encoding="utf-8")

    monkeypatch.setattr(er, "verify_manifest_hashes", lambda *a, **k: (True, "stub"))
    monkeypatch.setattr(
        er, "run_current_metrics",
        lambda *a, **k: {"ndcg@10": 0.489051, "p_value": None,
                         "tie_policy": tp.CURRENT_TIE_POLICY},
    )
    rc = er.main(["--baseline", str(lock), "--manifest", str(manifest), "--collection", "B"])
    assert rc == er.EXIT_OK
    assert "tie_policy=" in capsys.readouterr().out
