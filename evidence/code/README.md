# The regression policy, as code

## `eval_regression.py`

The gate. Given a current run and the sealed lock, it decides whether the run regressed. Three of
its functions are pure and testable with no corpus at all: `compute_integrity_hash`, `verify_lock`,
`is_regression`.

Exit codes are a contract here, not a convenience: `0` within policy, `1` regression, `2` cannot
gate. The third one exists so that a broken instrument never reads as a pass.

## `tie_policy.py`

How tied scores are handled when the metric is computed. See
`../decisions/0013-tie-handling-in-evaluation.md` for why this needed a decision record of its own.

## `test_eval_regression.py`

35 tests. They run on a clean checkout, with no corpus and no network:

    python3 -m pytest -q evidence/code/test_eval_regression.py

The bench also carries tests for `tie_policy`, but they load two bench runners that are not part of
this repository, so they would fail here. They are left out, since a broken test costs more than it gives.
