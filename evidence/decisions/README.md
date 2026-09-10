# Architecture decision records

The bench carries 13 numbered decision records, from `0001-local-first-monorepo` to
`0013-tie-handling-in-evaluation`. Six are here.

**The seven that are not here discuss my employer's context**: their target corpus, their vendor
situation, their integration horizon. They are not mine to publish, and one of them
(`0011-vendor-boundary`) already carries a note saying it is a personal R&D document and not an
official position of the company. So it stays where it was written.

What that leaves is the part that transfers anyway: how the engine was chosen, why the judgements
carry their provenance, how ties are handled in the metric, and how the embedder ladder was
climbed.

| Record | What it decides |
|---|---|
| `0003-fts5-as-serving-baseline` | Keyword search as the baseline to beat, and why the baseline has to be a real one |
| `0005-qrels-provenance` | Every set of relevance judgements carries where it came from |
| `0006-weighted-rrf-and-lower-k` | How the two rankings are fused, and the value of k |
| `0008-mid-tier-embedder-ladder` | Which embedding models to try, in which order, and when to stop |
| `0010-assistant-measurement` | Measuring an assistant's answers, not only the retrieval under it |
| `0013-tie-handling-in-evaluation` | What a tied score means in the metric, and why the choice moves results |

**The paths inside them do not resolve here.** These records were written inside the bench and
cite it: `bench/runners/compare.py`, `docs/research/...`, the seven decision records that stayed
behind. Fifty distinct paths of that kind appear across the six files. They are left exactly as
written, because editing a dated record to make it look tidy in a new context is the opposite of
what a decision record is for. Read them as documents from another tree.

A decision record is dated, numbered, and says what was rejected. Read `0013` first if you only
read one: tie handling is the kind of detail that silently moves a published number, and a
measurement either states it or hides it.
