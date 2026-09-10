# Evidence

Every experimentally verifiable claim in the top-level README has a file here. One claim does
not: agent governance, in section 2, is described and not shipped. That gap is named in the
README itself rather than covered over.

Nothing in this directory is a summary written for a reader: these are the working artefacts,
copied out of the bench that produced them, with absolute paths made relative and nothing else
changed.

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
| `finetune-blocked/` | The fine-tune whose score was never read, with the runs to recompute it |
| `code/` | The regression policy as executable code, and its tests |
| `decisions/` | Architecture decision records |
| `declared-metrics.md` | The numbers that are declared rather than recomputed, with the command behind each |
| `gates/` | Four tools that refuse, with example data so the refusal can be seen |

## What is not here

The search engine itself, the knowledge platform it serves, and the corpus of tickets. The first
two are large and private. The corpus is public data (Apache JIRA issues, CQADupStack, GitBugs)
and the provenance files in `retrieval/qrels-provenance/` say exactly which release of each was
used, so anyone can fetch the same thing.
