"""eval_regression.py — Ariane IR regression gate (G9, S2).

Role: gate a current IR run against a sealed baseline lock. Mirrors two Recherches
      idioms (B_RES1 §5): the baseline-lock integrity_hash + --verify shape of
      `tools/run_evals_baseline.py`, and the exit-1-on-regression + {json,md} report
      contract of `tools/drift_audit.py`.

Exit codes (drift_audit discipline):
    0 = within policy (no significant regression)
    1 = REGRESSION (CI gate trips)
    2 = setup / integrity error (cannot gate)

The pure functions (compute_integrity_hash / verify_lock / is_regression) are testable with
no corpus at all. The index -> query -> qrels -> metrics step is wired for the B collections
and exits 2 on any other, which is the honest behaviour for a gate that cannot run.
(This paragraph used to say the step was stubbed and the corpus not ingested. That stopped
being true when the FTS5 run was wired; corrected 2026-09-10 after an outside review read it
against baseline_lock.json and found the contradiction.)

ranx note (verified this session): `ranx.compare(qrels, runs, metrics, stat_test='student',
max_p=0.01, random_seed=42, ...)` — the kwarg to select the test is `stat_test=` (default
'student' = paired Student's t-test); significance threshold kwarg is `max_p=`. The baseline
policy `stat_test: "paired-t"` maps to ranx `stat_test="student"` (see _RANX_STAT_TEST_MAP).

Stdlib-only for the gate logic (json/hashlib/argparse/math). ir_measures/ranx are imported
lazily inside the run step so the pure functions and their tests need no corpus. (The word
"stubbed" stood here until 2026-09-11, three weeks after the FTS5 run was wired. Same drift
as the paragraph above, same review.)
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path


def _load_tie_policy():
    """Load ``tie_policy`` ONCE per process, registered in ``sys.modules``.

    Not a micro-optimisation — a correctness requirement. ``bench/`` is not a package, so
    every runner loads its siblings by path; a plain path-load would give each importer its
    OWN ``tie_policy`` module object and therefore its OWN ``ScoringRegimeError`` class, and
    ``except ScoringRegimeError`` in one module would then NOT catch the exception raised by
    another. (Found by making the guard fire, S31 — not by reading the source.) Registering
    the module under its canonical name makes the exception type a single identity, shared
    with a plain ``import tie_policy`` where ``bench/runners`` is on ``sys.path``.
    """
    import sys as _sys

    cached = _sys.modules.get("tie_policy")
    if cached is not None:
        return cached
    path = Path(__file__).resolve().parent / "tie_policy.py"
    spec = importlib.util.spec_from_file_location("tie_policy", path)
    if spec is None or spec.loader is None:  # pragma: no cover - import guard
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    _sys.modules["tie_policy"] = mod  # register BEFORE exec (stdlib idiom)
    spec.loader.exec_module(mod)
    return mod


# The scoring-regime guard (S31, ADR-0013 acceptance precondition). Stdlib-only and
# dependency-free, so the gate's pure functions stay importable with no corpus.
_tp = _load_tie_policy()
ScoringRegimeError = _tp.ScoringRegimeError
#: Re-exported for the same reason: a gate that refuses an UNSTATED regime must expose the
#: refusal under the canonical class, not a per-module copy of it (S31 L9).
UnstatedRegimeError = _tp.UnstatedRegimeError

# Exit codes (mirror drift_audit.py).
class CannotGateError(RuntimeError):
    """La porte refuse de conclure faute de la preuve que sa politique exige.

    Levee quand la metrique a chute au-dela du delta, que la politique exige la
    significativite, et qu'aucune p-value n'est disponible. Rendre False dans ce cas
    reviendrait a lire une absence de preuve comme une preuve d'absence : c'est le seul
    endroit du module ou la porte ne refusait pas, alors que le garde de regime de
    notation, lui, refuse depuis S31. Corrige le 2026-09-10 apres revue exterieure.
    """


EXIT_OK = 0
EXIT_REGRESSION = 1
EXIT_SETUP_ERROR = 2

# Maps the baseline-lock policy `stat_test` value to the installed ranx kwarg value.
# Verified: ranx.compare(..., stat_test: str = 'student', ...). 'student' = paired t-test.
_RANX_STAT_TEST_MAP = {
    "paired-t": "student",
    "student": "student",
    "fisher": "fisher",
    "tukey": "tukey",
}

_HASH_FIELD = "integrity_hash"


def assert_same_scoring_regime(current, baseline, *, context: str | None = None,
                               current_is_legacy: bool = False,
                               baseline_is_legacy: bool = False) -> dict:
    """Refuse a G9 comparison whose two sides disagree on the scoring regime (S31).

    Thin named wrapper over ``tie_policy.assert_same_regime`` so the gate's own module
    exposes the refusal, exactly as ``compare`` re-exports ``UnsealedFixtureError``.
    """
    return _tp.assert_same_regime(current, baseline, context=context,
                                 a_legacy_ok=current_is_legacy,
                                 b_legacy_ok=baseline_is_legacy)


# ── Pure functions: integrity (testable now) ────────────────────────────────────
def _canonical_blob(payload: dict) -> bytes:
    """Canonical serialization of `payload` minus the integrity_hash field.

    Mirror of Recherches `harness.integrity_hash`: sort_keys, no ASCII escaping.
    """
    without = {k: v for k, v in payload.items() if k != _HASH_FIELD}
    return json.dumps(without, sort_keys=True, ensure_ascii=False).encode("utf-8")


def compute_integrity_hash(payload: dict) -> str:
    """SHA-256 over the canonical JSON of `payload` minus `integrity_hash`.

    Returns a `sha256:<hex>` string (Recherches run_evals_baseline shape).
    """
    return "sha256:" + hashlib.sha256(_canonical_blob(payload)).hexdigest()


def verify_lock(path: str | Path) -> tuple[bool, str]:
    """Verify the stored `integrity_hash` of a baseline lock without re-running.

    Returns (ok, message). ok=False on missing file, invalid JSON, missing hash,
    or hash mismatch (tamper). A `null` placeholder hash (unsealed lock) is treated
    as an integrity failure — an unsealed lock must not be used to gate.
    """
    p = Path(path)
    if not p.exists():
        return (False, f"baseline lock missing: {p}")
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return (False, f"baseline lock invalid JSON: {exc}")
    stored = payload.get(_HASH_FIELD)
    if not stored:
        return (False, "integrity_hash absent or null (lock not sealed)")
    recomputed = compute_integrity_hash(payload)
    if stored == recomputed:
        return (True, f"integrity OK — {stored}")
    return (False, f"integrity BROKEN — stored={stored} recomputed={recomputed}")


_POLICY_REQUISE = ("primary_metric", "delta_abs", "require_significance", "max_p", "stat_test")


def validate_lock_for_gate(payload: dict, collection: str) -> tuple[bool, str]:
    """Check that a lock has the fields a gate needs, independently of its hash.

    `verify_lock` proves that the payload is the one that was sealed. It does not prove
    that the payload can gate anything. The two are different questions, and a review on
    2026-09-11 showed what happens when the second is skipped: a lock whose collection
    entry has no `ndcg@10` was read through `coll_baseline.get(primary_metric, 0.0)`, so a
    missing baseline became a baseline of zero, and a current score of 0.48 was declared an
    improvement over a number nobody ever measured.

    A hash-valid lock can be semantically incomplete: resealed after an edit, truncated by
    a partial write, or produced by an older schema. Integrity is not validity.

    Returns (ok, message). Every failure is a setup error, never a verdict.
    """
    if payload.get("sealed") is not True:
        return (False, "lock is not sealed")
    if not payload.get("schema"):
        return (False, "lock declares no schema")
    policy = payload.get("regression_policy")
    if not isinstance(policy, dict):
        return (False, "regression_policy absent or not an object")
    manquants = [k for k in _POLICY_REQUISE if k not in policy]
    if manquants:
        return (False, f"regression_policy missing {', '.join(manquants)}")
    if not isinstance(policy["primary_metric"], str) or not policy["primary_metric"]:
        return (False, "primary_metric is not a metric name")
    for champ in ("delta_abs", "max_p"):
        valeur = policy[champ]
        if not isinstance(valeur, (int, float)) or isinstance(valeur, bool):
            return (False, f"{champ} is not a number: {valeur!r}")
        if not math.isfinite(float(valeur)):
            return (False, f"{champ} is not finite: {valeur!r}")
    if float(policy["delta_abs"]) < 0:
        return (False, f"delta_abs is negative: {policy['delta_abs']!r}")
    if not 0.0 <= float(policy["max_p"]) <= 1.0:
        return (False, f"max_p is outside [0, 1]: {policy['max_p']!r}")
    if not isinstance(policy["require_significance"], bool):
        return (False, "require_significance is not a boolean")

    coll = payload.get("baselines", {}).get(collection)
    if not isinstance(coll, dict):
        return (False, f"no baseline for collection '{collection}'")
    metric = policy["primary_metric"]
    if metric not in coll:
        return (False, f"baseline for '{collection}' has no '{metric}'")
    valeur = coll[metric]
    if not isinstance(valeur, (int, float)) or isinstance(valeur, bool):
        return (False, f"baseline '{metric}' is not a number: {valeur!r}")
    if not math.isfinite(float(valeur)):
        return (False, f"baseline '{metric}' is not finite: {valeur!r}")
    n = coll.get("n_queries")
    if not isinstance(n, int) or isinstance(n, bool) or n <= 0:
        return (False, f"baseline '{collection}' has no usable n_queries: {n!r}")
    return (True, f"schema OK — {collection}/{metric}={valeur} over {n} queries")


def is_regression(
    current: float,
    baseline: float,
    policy: dict,
    p_value: float | None = None,
    *,
    current_tie_policy: str | None = None,
    baseline_tie_policy: str | None = None,
    current_is_legacy: bool = False,
    baseline_is_legacy: bool = False,
) -> bool:
    """Decide whether `current` is a regression vs `baseline` under `policy`.

    Regression iff the metric drops past the absolute delta AND (significance is not
    required OR the drop is statistically significant):

        current < baseline - delta_abs
        AND (not require_significance  OR  p_value < max_p)

    `policy` keys: delta_abs, require_significance, max_p. If the metric dropped past the
    delta, significance is required, and no `p_value` is supplied, the gate RAISES
    `CannotGateError` instead of returning a verdict. Returning False there would read an
    absence of proof as a proof of absence, on the one leg of this module that used to
    fail open. Changed 2026-09-10; the previous behaviour was documented and tested, and
    it was still the wrong default for a gate whose purpose is to refuse.

    **Scoring-regime guard (S31, ADR-0013 item 4 — the G9 path).** `current_tie_policy` and
    `baseline_tie_policy` are the regime markers of the two numbers. If they differ, the gate
    REFUSES to compare (`ScoringRegimeError`) rather than returning a verdict: a current
    number scored by one instrument and a locked baseline scored by another cannot be gated
    against each other in either direction.

    **An absent marker is no longer read as pre-regime unless the caller says so (S31 L9).**
    `current_is_legacy` / `baseline_is_legacy` default to **False on both sides**: this is the
    G9 gate, and no frozen call site forces a permissive default here. `main()` passes
    `baseline_is_legacy=True` — `baseline_lock.json` carries no marker and is byte-untouched
    since S5, so it is a genuine pre-marker artefact — and passes **nothing** on the current
    side, because a freshly computed number carrying no marker is a defect and must raise
    (`UnstatedRegimeError`) rather than be filed as pre-regime. This guard fails CLOSED, and since
    2026-09-10 the significance leg does too.
    """
    assert_same_scoring_regime(
        current_tie_policy, baseline_tie_policy, context="eval_regression.is_regression (G9)",
        current_is_legacy=current_is_legacy, baseline_is_legacy=baseline_is_legacy,
    )
    delta_abs = float(policy.get("delta_abs", 0.0))
    dropped_past_delta = current < (baseline - delta_abs)
    if not dropped_past_delta:
        return False
    if not policy.get("require_significance", False):
        return True
    if p_value is None:
        raise CannotGateError(
            f"significance required by policy but no p-value available "
            f"(current={current}, baseline={baseline}, "
            f"delta_abs={delta_abs}): cannot gate")
    return p_value < float(policy.get("max_p", 0.05))


# ── Manifest helpers ────────────────────────────────────────────────────────────
def _load_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _collection_entry(manifest: dict, collection_id: str) -> dict | None:
    for entry in manifest.get("collections", []):
        if entry.get("collection_id") == collection_id:
            return entry
    return None


# ── Evaluation views (ADR-0009 AUD3-C3, S21) ────────────────────────────────────
# A collection may carry a SECOND EVALUATION VIEW over the SAME sealed corpus: same
# corpus bytes, same collection_id, a re-sliced (queries, qrels) pair. Views are
# discriminated by an explicit `view` key on each file entry:
#   * file WITHOUT `view` → the collection's DEFAULT (sealed) view; the corpus file is
#     shared and deliberately carries no `view`, so it belongs to every view;
#   * file WITH `view` → that named view only.
# `DEFAULT_VIEW` is the selector value for "the default view ONLY". It is a sentinel
# name, never written into a manifest.
DEFAULT_VIEW = "default"

# View selection is explicit BY CONSTRUCTION: nothing resolves to a named view unless
# it is asked for by name (AUD3-C3 — silent default resolution to a new view is a defect).
ALL_VIEWS = None


def file_view(file_entry: dict) -> str:
    """The view a manifest file entry belongs to (`DEFAULT_VIEW` when it carries none)."""
    return file_entry.get("view") or DEFAULT_VIEW


def select_files(entry: dict, view: str | None) -> list[dict]:
    """The file entries constituting `view`.

    ``view=ALL_VIEWS`` (None, the default) → **every** file of the entry, so a single
    ``verify_manifest_hashes(m, "C")`` hard-verifies **every** view's committed anchor.
    ``view=DEFAULT_VIEW`` → the view-less (sealed) files only.
    ``view="<name>"`` → that view's files **plus** the shared view-less ones (the corpus).
    """
    files = entry.get("files", [])
    if view is ALL_VIEWS:
        return list(files)
    if view == DEFAULT_VIEW:
        return [f for f in files if file_view(f) == DEFAULT_VIEW]
    return [f for f in files if file_view(f) in (DEFAULT_VIEW, view)]


def verify_manifest_hashes(
    manifest: dict, collection_id: str, view: str | None = ALL_VIEWS
) -> tuple[bool, str]:
    """Re-hash the collection's sealed *committed* files and compare to the manifest.

    Returns (ok, message). Unsealed collections (sealed=false) are skipped — there is
    nothing to gate on yet (placeholders).

    For a sealed collection, files split by the `regenerable` flag (seal discipline =
    qrels-only, operator decision #c, S6 J1.4):

      * **regenerable=true**  → heavy, gitignored, rebuilt by the ingest scripts. Its
        *absence* must NOT fail the gate (a cold clone has no such file → CI must stay
        green). It is SKIPPED. If it happens to be present locally we soft-check it: a
        sha256 mismatch is reported as a non-fatal note (data drifted vs the seal) but
        does NOT fail — these files are regenerable, not the tamper-detection anchor.
      * **regenerable=false / absent** → committed + verifiable (the qrels .trec). These
        are HARD-verified: missing/empty sha256, missing file, or sha256 mismatch → FAIL
        (tamper-detection stays live). This is the whole basis of the seal.

    A regenerable file present-but-drifted is surfaced in the message but never fails the
    gate; cold-clone-correctness (gate independent of any gitignored file) is the
    invariant tests T7(a) + the cold-clone sim assert.

    ``view`` (ADR-0009 AUD3-C3) selects which evaluation view's files to verify. The
    default ``ALL_VIEWS`` keeps the caller contract **unchanged and strictly widening**:
    every file of the entry is checked, so a collection that grows a second view has
    **both** views' committed anchors hard-verified by the same ``make eval-verify`` line.
    Pass ``DEFAULT_VIEW`` to verify only the original sealed view, or a view name to
    verify that view plus the shared (view-less) files. See :func:`select_files`.
    """
    entry = _collection_entry(manifest, collection_id)
    if entry is None:
        return (False, f"collection '{collection_id}' not in manifest")
    if not entry.get("sealed", False):
        return (True, f"collection '{collection_id}' not sealed — hash verify skipped")
    repo_root = Path(__file__).resolve().parents[2]
    verified = 0
    skipped = 0
    soft_drift: list[str] = []
    for file_entry in select_files(entry, view):
        path = file_entry.get("path")
        # Regenerable (gitignored, rebuildable) → absence must not fail the gate.
        if file_entry.get("regenerable", False):
            skipped += 1
            fpath = repo_root / path
            recorded = file_entry.get("sha256")
            # Soft-check only if BOTH the file is present AND a sha256 is recorded;
            # a mismatch is a non-fatal drift note, never a gate failure.
            if recorded and fpath.exists():
                actual = hashlib.sha256(fpath.read_bytes()).hexdigest()
                if actual != recorded:
                    soft_drift.append(path)
            continue
        # Committed (qrels .trec) → HARD verify (tamper-detection live).
        recorded = file_entry.get("sha256")
        if not recorded:
            return (False, f"sealed committed file has no sha256: {path}")
        fpath = repo_root / path
        if not fpath.exists():
            return (False, f"sealed committed file missing: {path}")
        actual = hashlib.sha256(fpath.read_bytes()).hexdigest()
        if actual != recorded:
            return (
                False,
                f"sha256 mismatch for {path}: recorded={recorded} actual={actual}",
            )
        verified += 1
    scope = "all views" if view is ALL_VIEWS else f"view '{view}'"
    msg = (
        f"collection '{collection_id}' [{scope}] committed hashes OK "
        f"({verified} verified, {skipped} regenerable skipped)"
    )
    if soft_drift:
        msg += f" — NOTE: {len(soft_drift)} regenerable file(s) present-but-drifted (non-fatal): {soft_drift}"
    return (True, msg)


# ── Real run step (wired S3 B1 — GitBugs pilot slice) ────────────────────────────
def run_current_metrics(manifest: dict, collection_id: str, seed: int, policy: dict) -> dict:
    """Run the current index -> query -> qrels -> metrics pipeline for a collection.

    WIRED (S3 B1): for collection B (GitBugs pilot) this dispatches to
    `bench.runners.run_pilot.run_collection_B`, which builds the FTS5 index over the
    ingested slice, retrieves with BM25, and scores with ir_measures. It returns
    {primary_metric: float, "mrr", "recall@100", "n_queries", "per_query", "p_value"}.

    `p_value` is None until a *candidate* run is supplied to compare against the
    baseline run. When significance is required and the p-value is absent, the gate no
    longer fails open on that leg: it raises CannotGateError and the caller exits 2 (see
    is_regression's docstring). This sentence said the opposite until 2026-09-11, several
    weeks after the behaviour changed. The ranx paired test, when a candidate lands:

        from ranx import compare
        report = compare(qrels, runs=[baseline_run, current_run],
                         metrics=[policy["primary_metric"]],
                         stat_test=_RANX_STAT_TEST_MAP[policy["stat_test"]],
                         max_p=policy["max_p"], random_seed=seed)

    Collections other than B are not ingested yet (ADR-0004 builds B -> A -> C) and
    still raise NotImplementedError so `main()` exits 2 rather than gating on nothing.
    """
    if collection_id != "B":
        raise NotImplementedError(
            f"collection '{collection_id}' not ingested yet (ADR-0004 pilot = B). "
            "No current metric to gate on."
        )
    # Import lazily by path: run_pilot lives alongside this module in bench/runners/.
    import importlib.util

    runner_path = Path(__file__).resolve().parent / "run_pilot.py"
    spec = importlib.util.spec_from_file_location("run_pilot", runner_path)
    if spec is None or spec.loader is None:  # pragma: no cover - import guard
        raise NotImplementedError(f"cannot load run_pilot from {runner_path}")
    run_pilot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run_pilot)
    return run_pilot.run_collection_B(seed=seed)


# ── CLI ─────────────────────────────────────────────────────────────────────────
def _reseal(baseline_path: Path, session: str) -> int:
    """--update-baseline: recompute and store a fresh integrity_hash (re-seal the lock).

    The only sanctioned way to move the baseline (analogous to run_evals_baseline
    --session). Updates `session` and `integrity_hash`, leaves baselines as-is.
    """
    try:
        payload = _load_json(baseline_path)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"[eval-regression] cannot reseal: {exc}", file=sys.stderr)
        return EXIT_SETUP_ERROR
    if session:
        payload["session"] = session
    payload[_HASH_FIELD] = compute_integrity_hash(payload)
    baseline_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"[eval-regression] baseline re-sealed: {baseline_path} ({payload[_HASH_FIELD]})")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """Entry point — verify lock + manifest, run, gate. Exit 0/1/2."""
    parser = argparse.ArgumentParser(
        description="Ariane IR regression gate (G9). Exit 0=ok, 1=regression, 2=setup error.",
    )
    parser.add_argument("--baseline", required=True, help="path to baseline_lock.json")
    parser.add_argument("--manifest", required=True, help="path to CORPUS_MANIFEST.json")
    parser.add_argument("--collection", required=True, help="collection_id to gate (e.g. B)")
    parser.add_argument(
        "--view",
        default=None,
        help="evaluation view to hash-verify (ADR-0009). Omitted = ALL views of the "
        f"collection; '{DEFAULT_VIEW}' = the original sealed view only; a view name = "
        "that view plus the shared files.",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="re-seal a fresh integrity_hash (move the baseline) — does not gate",
    )
    parser.add_argument("--session", default="", help="session label for --update-baseline")
    args = parser.parse_args(argv)

    baseline_path = Path(args.baseline)

    # --update-baseline: re-seal and return (does not gate).
    if args.update_baseline:
        return _reseal(baseline_path, args.session)

    # 1. Verify lock integrity (exit 2 on mismatch / unsealed).
    ok, message = verify_lock(baseline_path)
    if not ok:
        print(f"[eval-regression] lock integrity error: {message}", file=sys.stderr)
        return EXIT_SETUP_ERROR

    try:
        baseline = _load_json(baseline_path)
        manifest = _load_json(args.manifest)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"[eval-regression] load error: {exc}", file=sys.stderr)
        return EXIT_SETUP_ERROR

    # 1bis. Verify the lock can gate at all. Integrity is not validity: a resealed but
    #       incomplete lock passes step 1 and still has no number to compare against.
    ok, message = validate_lock_for_gate(baseline, args.collection)
    if not ok:
        print(f"[eval-regression] lock schema error: {message}", file=sys.stderr)
        return EXIT_SETUP_ERROR

    policy = baseline["regression_policy"]
    primary_metric = policy["primary_metric"]
    seed = int(baseline.get("system", {}).get("seed", 0))
    coll_baseline = baseline["baselines"][args.collection]

    # 2. Verify manifest file hashes for the collection (exit 2 on mismatch).
    ok, message = verify_manifest_hashes(manifest, args.collection, view=args.view)
    if not ok:
        print(f"[eval-regression] manifest integrity error: {message}", file=sys.stderr)
        return EXIT_SETUP_ERROR

    # 3. Run current metrics. Wired for the B collections, exit 2 elsewhere.
    try:
        current = run_current_metrics(manifest, args.collection, seed, policy)
    except NotImplementedError as exc:
        print(f"[eval-regression] setup: {exc}", file=sys.stderr)
        return EXIT_SETUP_ERROR

    # 4. Gate. The scoring-regime guard (S31) runs FIRST, inside is_regression: a mixed
    #    pre-change/post-change comparison is a setup error (cannot gate), never a verdict.
    # No default here. `coll_baseline.get(primary_metric, 0.0)` turned an absent baseline
    # into a baseline of zero, which reads as "no regression" for any current score.
    # validate_lock_for_gate has already refused the lock if the key is missing.
    baseline_value = float(coll_baseline[primary_metric])
    try:
        regressed = is_regression(
            current[primary_metric],
            baseline_value,
            policy,
            p_value=current.get("p_value"),
            current_tie_policy=current.get(_tp.TIE_POLICY_FIELD),
            baseline_tie_policy=coll_baseline.get(_tp.TIE_POLICY_FIELD),
            # S31 L9 — the locked baseline is a genuine pre-marker artefact (no marker,
            # byte-untouched since S5). The current side declares nothing: unmarked there
            # is a defect, and must raise rather than resolve to pre-regime.
            baseline_is_legacy=True,
        )
    except (ScoringRegimeError, UnstatedRegimeError) as exc:
        print(f"[eval-regression] scoring-regime error: {exc}", file=sys.stderr)
        return EXIT_SETUP_ERROR
    except CannotGateError as exc:
        print(f"[eval-regression] cannot gate: {exc}", file=sys.stderr)
        return EXIT_SETUP_ERROR
    if regressed:
        print(
            f"[eval-regression] REGRESSION on {args.collection}/{primary_metric}: "
            f"current={current[primary_metric]} baseline={baseline_value}",
            file=sys.stderr,
        )
        return EXIT_REGRESSION
    print(
        f"[eval-regression] OK on {args.collection}/{primary_metric}: "
        f"current={current[primary_metric]} baseline={baseline_value} "
        f"tie_policy={_tp.regime_of(current.get(_tp.TIE_POLICY_FIELD))}"
    )
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
