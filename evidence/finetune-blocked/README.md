# The fine-tune whose score I have never read

I fine-tuned an embedding model on this corpus. The model exists. I do not know whether it is
better than the base model, because the protocol did not let me look.

## What to open, in order

**`F1_gate.json`** ran before any training. Four checks for leakage between the tuning pairs and
the held-out evaluation set: overlap of queries, held-out ids used as endpoints, held-out clusters
touched, tuning coverage. Overlap zero on the first three, `passed: true`, 476 endpoints over 740
tuning items. Leakage is checked before the run, because after the run there is an incentive not
to look.

**`guard_encode.json`** is the memory ceiling, measured rather than assumed, with the branch name
it would have taken had the ceiling been hit (`STOP-VRAM-ENCODE`).

**`F1_decision.json`** is the run itself, and the file worth reading closely:

    "control":  { "computed": 0.575258, "target": 0.576448,
                  "tolerance": 5e-07,   "passed": false }
    "status":   "fail"
    "verdict":  null

The protocol required a positive control before comparing the treated arm: put the base model back
through the same harness and check it reproduces its own reference. It returned 0.575258 against a
reference of 0.576448, outside a tolerance of 5e-7. The instrument was therefore not proven, so
nothing measured with it that day could be trusted, including a result that might have been good.

The decision record for what to do in that case was written before the run, not after (ADR-0012 in
the bench). It said: block the arm, issue no verdict, interpret no number. That is what the file
records, and the note it carries says so in those words.

No threshold was relaxed. Not the memory ceiling, not the control tolerance.

**`F1_finetune_run.md`** is the full narrative, including what was tried and what it cost.

## Recompute it yourself

`F1_artifacts/` ships the two TREC run files, the held-out judgements, and the per-query control
diagnostic. The base run, the fine-tuned run and the qrels are all here, so the control failure is
not something you have to take on my word.

## Why this is in a portfolio

A fine-tune that worked shows that a pipeline runs. A fine-tune stopped by its own control shows
what happens when the protocol becomes inconvenient. The second is the harder thing to
demonstrate, and it is the one that matters when a measurement informs a decision someone else
pays for.
