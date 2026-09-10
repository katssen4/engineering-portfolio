# Retrieval, measured

## `baseline_lock.json`

18 engine configurations frozen in one file: four projects times three engines, plus pooled and
alias entries. Each carries `ndcg@10`, `mrr`, `recall@100` and its query count.

The file is sealed. `integrity_hash` is a SHA-256 over the canonical serialisation of everything
else in it, so a later run compares against a fixed reference rather than against a memory of one.
To check the seal yourself:

    python3 -c "import sys; sys.path.insert(0,'evidence/code'); \
    import eval_regression as e; print(e.verify_lock('evidence/retrieval/baseline_lock.json'))"

The lock also carries the exact system that produced it: embedding model
`intfloat/e5-small-v2` pinned to revision `ffb93f3b`, `ranx` 0.3.20, `ir_measures` 0.4.3,
Python 3.12.3, `rrf_k` 60, seed 13. A measurement without its stack is not reproducible, so the
stack travels with the numbers.

## `regression_policy`, inside the lock

    primary_metric   ndcg@10
    delta_abs        0.01
    stat_test        paired-t
    max_p            0.05
    fail_on          primary_metric_drop_beyond_delta_AND_significant

Written before the results, not after. A drop fails the gate only when it is both beyond the delta
and statistically significant. Both conditions, which is the part that makes the policy usable
rather than decorative: it does not trip on noise, and it cannot be argued away when it trips.

## `qrels-provenance/`

Seven files, one per set of relevance judgements, 5,572 judgements in total. Each says where the
judgements came from: the source dataset, its release, how a judgement was derived, and what was
excluded.

This is the part of a retrieval measurement that is usually missing. Scores computed against
judgements of unknown origin are not arguable, because there is nothing to argue with.
