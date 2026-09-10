# Evidence

Every claim in the top-level README has a file here. Nothing in this directory is a summary
written for a reader: these are the working artefacts, copied out of the bench that produced
them, with absolute paths made relative and nothing else changed.

Start here:

    python3 tools/verify.py

It recomputes the seal on the reference lock, rebuilds the retrieval table of the README cell by
cell, checks the blocked fine-tune really was blocked, runs the anti-invention gate on its example
data, and runs the shipped unit tests. 32 checks, no network, no corpus download, standard library
plus pytest.

| Directory | What it holds |
|---|---|
| `retrieval/` | The sealed reference lock, and where each set of relevance judgements came from |
| `finetune-blocked/` | The fine-tune whose score was never read, with the runs to recompute it |
| `code/` | The regression policy as executable code, and its tests |
| `decisions/` | Architecture decision records |
| `gates/` | Four tools that refuse, with example data so the refusal can be seen |

## What is not here

The search engine itself, the knowledge platform it serves, and the corpus of tickets. The first
two are large and private. The corpus is public data (Apache JIRA issues, CQADupStack, GitBugs)
and the provenance files in `retrieval/qrels-provenance/` say exactly which release of each was
used, so anyone can fetch the same thing.
