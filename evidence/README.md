# Evidence

Every experimentally verifiable claim in the top-level README has a file here, with one named
exception: the dispatch layer and the commit broker of section 2 are described and not shipped,
and the README says so where it says it.

The evidence directories hold the original artefacts wherever they can be published safely,
copied out of the bench that produced them, with absolute paths made relative and nothing else
changed. The README files, this one included, exist only for navigation and context.

Start here:

    python3 tools/verify.py

It recomputes the control score of the blocked fine-tune from the TREC files, checks the seal on
the reference lock, rebuilds the retrieval table of the README cell by cell, exercises the gates on
their example data, runs the shipped unit tests, and counts its own checks against what the README
claims. No network, no corpus download, standard library plus pytest. The count is printed by the
script and stated in the root README only, so it cannot drift between two documents.

| Directory | What it holds |
|---|---|
| `retrieval/` | The sealed reference lock, and where each set of relevance judgements came from |
| `finetune-blocked/` | The blocked fine-tune, its treated run, and the positive-control artefacts `verify.py` uses to recompute the failed control |
| `code/` | The regression policy as executable code, and its tests |
| `decisions/` | Architecture decision records |
| `declared-metrics.md` | The declared numbers, each with the command behind it |
| `gates/` | Four tools that refuse, with example data so the refusal can be seen |
| `agent-governance/` | The write-scope guard and the chained audit log, reduced, with the tests that show them refusing |

## What is not here

The search engine itself, the knowledge platform it serves, and the corpus of tickets. The first
two are large and private. The corpus is public data (Apache JIRA issues, CQADupStack, GitBugs)
and the provenance files in `retrieval/qrels-provenance/` say exactly which release of each was
used, so anyone can fetch the same thing.
