# ADR-0013 — Tie handling in evaluation

**Status: Accepted**
**Date:** 2026-09-04
**Deciders:** Matteo (operator) — **Accepted S30, on 2026-09-05**, and **NOT unconditionally**: the non-Claude reviewer's **three conditions are inscribed verbatim**, and **condition 2 is posed as a PRECONDITION of the code lot**. Recorded in § *Accept (S30)*, **appended at the end of this file** — the same reason the two review sections and Amendment 1 were appended, so that every `:NNN` citation into this record still resolves. **Acceptance authorises a future code lot and performs none of it**: `bench/runners/run_pilot.py:59 score_trec` and its **51** in-process call sites are **unchanged**, and **no number in this repository has moved**. **This acceptance does not make the evaluator correct** — see § *Accept (S30)* § What this acceptance does NOT do.
**Proposed by:** eval-lead (S29, lot `S29_L14_ADR_B`)

> **Review order, and this ADR does not accept itself.** ADR-0012 **F7** binds any change that
> touches it to one sequence: *« any change to F7 is a fresh amendment, reviewed by a non-Claude
> finder, accepted by the operator — in that order, and never in flight »* (`:263-265`). This ADR
> moves the instrument that produces F7's target, so it is inside that sequence:
> **(1)** non-Claude review, **(2)** the operator's acceptance, **(3)** the code change — in that
> order and no other. **[UPDATED S30 — 2026-09-05. This paragraph is kept at its original line count on purpose, so that the 112 `:NNN` citations into this record still resolve. The two sentences that stood here until the operator's acceptance read: *« Neither (1) nor (2) has happened. Until both have, `run_pilot.score_trec` and its callers stay exactly as they are, and no number in this repository moves. »* They are kept quoted and dated rather than erased; the first of them is now false.]** **(1) has been run twice**, on two states of this record — `REJECT`, then `ACCEPT-WITH-CONDITIONS`, and **both verdicts stand**. **(2) happened on 2026-09-05** — § *Accept (S30)*, at the end of this file.
> **(3) has NOT happened and may NOT begin yet**: the operator posed the reviewer's condition 2 as a **PRECONDITION**, so **no code change is authorised to start before the scoring-regime guard exists**, and that guard **does not exist today**. Until (3) has been written, reviewed and run, `run_pilot.score_trec` and its callers stay exactly as they are, **no number in this repository moves**, and **the evaluator is not yet correct**.
>
> **This ADR contains no anchor value computed under the rule it decides.** The rule is chosen on
> its own justification (Decision D3), and what it returns on the repository's recorded anchors is
> measured **separately and afterwards**, in `docs/research/S29_regle_egalites_mesure.md`. The
> separation is deliberate and it is the point: a tie convention selected because it returns a
> wanted number would prove only that a search happened.

---

## Context

### C1 — The defect, measured

`bench/runners/run_pilot.py:59 score_trec` is the repository's **shared scorer**; its own docstring
records that the three retrieval methods are measured « by exactly one code path on the SAME qrels »
(`:62-64`). It asks `ir_measures` for three measures in one call (`:69`):

```python
measures = [nDCG @ 10, RR @ 10, R @ 100]
agg = ir_measures.calc_aggregate(measures, qrels, run)      # run_pilot.py:70-74
```

**That one call is served by two providers, and they break score ties in opposite directions.**
Measured on the installed packages by this lot, not inherited from a document:

```
ir_measures 0.4.3 · pytrec-eval-terrier 0.5.10 · .venv/lib/python3.12/site-packages/

ir_measures.evaluator([nDCG@10, RR@10, R@100], qrels)  ->  FallbackEvaluator
    PytrecEvalEvaluator   measures: ['R@100', 'nDCG@10']
    MsMarcoEvaluator      measures: ['RR@10']
```

| provider | measures it serves | tie rule at equal score | evidence |
|---|---|---|---|
| `pytrec_eval` | **nDCG@10**, R@100 | `doc_id` **descending** | synthetic probe, below |
| `msmarco` | **RR@10** | `doc_id` **ascending** | `ir_measures/providers/msmarco_provider.py:41` — `sorted(run[q].items(), key=lambda x: (-x[1], x[0]))` |

The probe, run by this lot on two documents at exact score equality:

```
run = {q1: {dAAA: 1.0, dZZZ: 1.0}}

relevant = dZZZ : nDCG@10 = 1.000000   RR@10 = 0.500000   R@100 = 1.000000
relevant = dAAA : nDCG@10 = 0.630930   RR@10 = 1.000000   R@100 = 1.000000
```

nDCG@10 ranks `dZZZ` first (the larger identifier); RR@10 ranks `dAAA` first (the smaller).
**Same call, same run, same tie, two opposite ranks for the same document on the same query.**

So a single report emitted by this repository can assert two contradictory ranks for one document,
and — where a tie group mixes a relevant and a non-relevant document — **which of them is credited
depends on the lexicographic order of a Jira ticket identifier.** That is a property of a character
string, not a property of retrieval.

Three further facts, each measured elsewhere in the repository and each load-bearing here:

- **The `.trec` rank column plays no part.** `ir_measures.util.read_trec_run` yields
  `ScoredDoc(query_id, doc_id, score)` and discards the rank the retriever wrote, so the order in
  the run file has no effect on scoring (`S28_egalites_evaluateur.md` §2.1). The evaluator does not
  measure the ordering the engine produced; among tied scores it invents one.
- **The aggregate carries the same signature.** Over the 310-query sealed holdout, the recorded
  `MRR@10 = 0.543614` falls on the ascending rule and never on the descending one (0.541952) —
  the provider split visible at scale rather than on a two-document probe
  (`S28_egalites_evaluateur.md` §3.1).
- **The mechanism has been observed in both directions on real queries.** On
  `cassandra:13318333` a one-ULP fp16 move collapsed a positive into an exact tie and the
  descending rule demoted it, `1.000000 → 0.630930` on the query; on `spark:13547049` at another
  encode batch a one-ULP move **broke** a tie and the demotion stopped, `0.148041 → 0.156426`
  (`S29_recuperation_f7.md` §H4; `S29_e1_determinisme.md` §2.3).

**The defect is permanent, not new.** It is present in every number this repository has produced;
it had simply never become visible, because no earlier query had put a relevant document inside a
mixed tie group.

### C2 — What is in scope here, and what is not

This ADR is about **how the evaluation instrument treats tied scores**. It is not about **why** a
fp16 query embedding moves by one ULP — the question open since S21, untouched by every S29 lot and
untouched here. The tie rule decides what a tie *does*; it does not decide what *causes* one.

### C3 — Blast radius, counted by this lot

A property of the codebase, not a result of the rule, which is why it can appear before the rule is
applied to anything. Recipe, and it is the corrected one — the earlier recipe omitted the extension
filter and did not reproduce (`S29_voies_B_C.md` §4(a), reservation 1 of the S29 fairness review):

```
grep -rEn --include='*.py' 'score_trec[[:space:]]*\(' bench/ .pilot/
```

**58 matched lines**, and this lot classified every one of them:

| kind | count | where |
|---|---|---|
| definition | **1** | `bench/runners/run_pilot.py:59` |
| textual mention (docstring / print string) | **4** | `diag_ties_s28.py:337` · `transfer_eval.py:25` · `rerank_eval.py:242` · `.pilot/scratch_aud3_score.py:6` |
| subprocess-string invocation | **2** | `diag_recover_s29.py:271` · `diag_recover_f7_s29.py:378` |
| **in-process call site** | **51** | 20 files, table below |

| file | call sites | file | call sites |
|---|---|---|---|
| `bench/runners/run_methods.py` | 6 | `bench/runners/diag_e1_determinisme_s29.py` | 2 |
| `bench/runners/sweep_weighted_rrf.py` | 6 | `bench/runners/finetune_f1.py` | 2 |
| `bench/runners/diag_recover_f7_s29.py` | 4 | `bench/runners/rerank_eval.py` | 2 |
| `bench/runners/diag_recover_s29.py` | 4 | `bench/runners/s21_encode_determinism_probe.py` | 2 |
| `bench/runners/s20_fresh_holdout.py` | 4 | `bench/runners/sweep_hybrid.py` | 2 |
| `bench/runners/compare.py` | 3 | `bench/runners/test_embedding_variants.py` | 2 |
| `bench/runners/embedding_variants.py` | 3 | `bench/runners/diag_ties_s28.py` | 1 |
| `bench/runners/a2_instruction_probe.py` | 2 | `bench/runners/run_pilot.py` (`:112`) | 1 |
| `.pilot/scratch_aud3_score.py` | 2 | `bench/runners/s21_corroboration_run.py` | 1 |
| `bench/runners/sp1_fixture.py` | 1 | `bench/runners/transfer_eval.py` | 1 |

**Plus a twenty-first file, reached indirectly:** `bench/runners/eval_regression.py:283` calls
`run_pilot.run_collection_B`, which calls `score_trec` at `run_pilot.py:112` — that is the **G9
regression gate**. Of the **52** `.py` modules in `bench/runners/`, **20** see their numbers move
(19 direct callers + `eval_regression.py`).

**Two of the callers are the repository's own control apparatus** — `sp1_fixture.py:216` (the CI
fixture) and `test_embedding_variants.py:181,192` (a test): the fixture and the test encode today's
tie behaviour and would need requalifying with everything else.

**A reflexive cost, and it is measured:** four of the 20 callers are the diagnostics that produced
the S28/S29 dossier's own figures (`diag_ties_s28.py`, `diag_recover_s29.py`,
`diag_recover_f7_s29.py`, `diag_e1_determinisme_s29.py`), as is June's own scoring script
`.pilot/scratch_aud3_score.py:47-48`. The dossier documenting this question would itself straddle
two scoring regimes.

**This count is the third independent one of this figure**, after `S28_egalites_evaluateur.md`
§5.2(a) (seven files — exact but incomplete by fourteen) and `S29_voies_B_C.md` §4(a). It
reproduces the second exactly: **58 = 1 + 4 + 2 + 51 over 20 files**, plus the indirect
`eval_regression.py`. `DISCREPANCY:` **none** against `S29_voies_B_C.md` §4(a).

### C4 — Prior art in this repository, and why the tie question was left open

`S28_egalites_evaluateur.md` §1 enumerated **seven** tie rules **and froze the list in writing
before any of them was computed**, then computed all seven (§3). It retained none, deliberately.
`S29_voies_B_C.md` §4 re-instructed the change as one of two paths and, equally deliberately,
retained none. **This ADR is the first document in the repository that chooses one**, and it does so
only because the operator has chosen the path.

That chronology discipline has a recorded weakness, and it is inherited here rather than hidden: the
S28 non-Claude reviewer found the pre-registration of the rule list **unattested** — commit `3bde088`
adds the document and the diagnostic together, and no earlier committed version of the list exists
(`S28_egalites_evaluateur.md` § *Amendement (S28)* §A1). The list is not contradicted; it is
unattested. The same objection could be raised against this ADR, and the only answer it can give is
the one it gives structurally: **the rule is committed before any value computed under it exists**
(see D3 and the note at the head of this file).

---

## Decision

### D1 — The rule

**`run_pilot.score_trec` stops breaking score ties. Every measure it returns is computed as the
expected value of that measure over the uniform distribution of orderings within each exact-score
tie group.** (McSherry & Najork, *Computing Information Retrieval Performance Measures Efficiently
in the Presence of Tied Scores*, ECIR 2008.) This is the rule enumerated as **R4** in
`S28_egalites_evaluateur.md` §1.

Stated precisely enough to implement and to check:

**(a) What a tie group is.** Documents of one query whose scores, **as read from the `.trec` run
file**, are **exactly equal**. Groups are formed in score-descending order. No tolerance, no
epsilon, no rounding beyond what the run file already carries.

**(b) What happens to a tie group.** It is **not ordered**. A group of `g` documents holding `r`
relevant ones, occupying positions `p … p+g−1` in the ranking, contributes to each measure the mean
of that measure over the `g!` orderings of the group. Closed form, no sampling:

- **nDCG@k** — every position of the group carries the same expected gain `r/g` by symmetry:
  `DCG += (r/g) × Σ 1/log2(q+1)` over `q` in `[p … min(p+g−1, k)]`. The ideal DCG denominator is
  unchanged: it is a function of the qrels, not of the run.
- **RR@k** — only the **first** group containing a relevant document can carry the first relevant
  one, so the expectation collapses to that group:
  `E[RR] = Σ_i ( C(g−1−i, r−1) / C(g, r) ) / (p+i)` for `i` in `[0 … g−r]` with `p+i ≤ k`.
- **R@k** — the same expectation. Where the cutoff does not fall **inside** a tie group it is a
  no-op, which is the case throughout collection B, where every query carries exactly 100 documents
  and the cutoff is 100 (`S28_egalites_evaluateur.md` §3.4 point 3).

**(c) In which direction.** In **none**. That is the substance of the rule: a system that emits a
tie has not ranked those documents, and the evaluator reports exactly that instead of crediting or
penalising an order the system never produced. The pessimistic and optimistic tie-breaks (S28's R5
and R6) are the bounds of that credit; the expectation is their principled interior point.

**(d) To which metrics.** **All three that `score_trec` returns** — nDCG@10, RR@10, R@100 — plus the
per-query nDCG@10 dict it emits (`run_pilot.py:75-81`), which is what every paired statistic in the
lab consumes.

**(e) How consistency across providers within one call is obtained.** **Structurally, not by
convention.** `ir_measures` splits the call across `PytrecEvalEvaluator` and `MsMarcoEvaluator`
(C1), and neither provider exposes a tie policy — the split is `FallbackEvaluator`'s dispatch, not a
setting. So the rule is **not** obtained by configuring `ir_measures`: it is implemented **once**,
inside `score_trec`, over one ranking read from the `.trec` file, and all three measures are derived
from **the same tie grouping of the same query**. The two providers can no longer disagree about
which of two tied documents ranks first because **that question is no longer asked of either of
them**.

### D2 — The two ambiguities inside this rule, named and resolved

An unresolved variant is where this decision would stall, so both are settled here with their
reason.

**(i) What counts as a tie: exact equality, or equality within a tolerance?** — **Exact equality is
chosen.** A tolerance re-introduces a fitted parameter, and ADR-0009 **A2.6** rejected exactly that
object class: *« Arbitrary, and its value would be chosen after seeing the miss it must accommodate.
A threshold fitted to the observation it must survive is not a gate. »* S28's **R7** is the tolerance
variant of this same rule (one fp16 ULP, then the expectation) and it is rejected on that ground,
reinforced by two findings of the S28 non-Claude reviewer: the scores are serialised to six decimals
before the scorer ever sees them (`ladder_run.py:288-291`), so R7 would operate on printed decimals
rather than on the fp16 values that motivate it; and its greedy grouping
(`diag_ties_s28.py:116-129`) is not a general equivalence relation, so the grouping could depend on
traversal order (`S28_egalites_evaluateur.md` § *Amendement (S28)* §A2). A rule whose grouping is
order-dependent cannot be the rule that removes an order dependency.

**(ii) A tie group straddling the cutoff `k`.** — **The expectation is taken over the positions the
group actually occupies, truncated at `k`.** A group at positions `p … p+g−1` contributes only over
`q ≤ k`. The reason is that this is the only treatment under which the returned number *is* the mean
of the measure over the permutations: counting the whole group's mass regardless of the cutoff would
return something that is not an expectation of nDCG@k, and the rule would no longer mean what it
says.

### D3 — The justification the rule is chosen on, in full, and what it excludes

**Each criterion below is a property of the rule. None refers to any anchor value, and no candidate
rule was scored against any target before this section was written.**

1. **Determinism.** Closed-form expectation — no sampling, no seed, no permutation enumeration. One
   `(run, qrels)` pair yields one value, always.
2. **Independence from identifier lexicography.** The `doc_id` string plays no part in any measure.
   This is the defect's actual mechanism, and this is the criterion that removes it rather than
   relocating it.
3. **Consistency across providers within one call.** Obtained structurally, as D1(e) states: the
   tie-break question disappears instead of being answered twice.
4. **Faithfulness to what the system produced.** The evaluator reports what the engine did — it
   ranked, or it did not — instead of manufacturing an order to score.
5. **It is the domain's standard answer** to tied scores, published and citable, not a lab-local
   invention.
6. **It is checkable.** The two closed forms in D1(b) can be verified by hand on a small fixture,
   and the repository already carries a tie fixture to verify them on (`sp1_fixture.py`).

**What each rejected alternative fails on, in the same terms:**

| rejected | fails on | detail |
|---|---|---|
| **R1** — `doc_id` descending (**the status quo**) | criteria 2, 3, 4 | Deterministic and canonical to `trec_eval`, but the rank of a relevant document depends on the lexicographic order of a ticket identifier, and it contradicts the `msmarco` provider inside the same call. **Its strongest argument is real and is recorded as a cost, not dismissed** — see *Negative / trade-offs*. |
| **R2** — `doc_id` ascending | criteria 2, 4 | Aligns the two providers and so removes the visible contradiction, while keeping the arbitrary dependency intact. It fixes the symptom this repository happened to notice, not the defect. |
| **R3** — run-file order | criteria 1, 4 (and it is not a tie rule) | `ir_measures` discards the rank column (C1), so adopting R3 means changing the **read path**, not the tie policy. And among tied scores the retriever's own order is `np.argsort(-sims)` (`ladder_run.py:272`) — an artefact of a sort routine, not a ranking decision. It substitutes one arbitrary order for another. |
| **R5 / R6** — pessimistic / optimistic | not conventions | They exist to **bound** what tie-breaking decides (S28 §1 says so at their enumeration: *« aucune des deux n'est une convention d'évaluation sérieuse »*). Adopting a bound as the measure is a category error. |
| **R7** — one fp16 ULP, then the expectation | criterion 1, plus A2.6 | See D2(i). |

**And the criterion that was NOT used.** No rule was chosen, ranked, or eliminated because of what
it returns on any recorded value of this repository — not the F7 target, not any other. S28
enumerated seven rules, computed all seven, and **none of them returns the F7 target**
(`S28_egalites_evaluateur.md` §3.4 point 1). Re-searching conventions until a wanted number returned
would demonstrate only that a search occurred. If the chosen rule moves an anchor, that is a
**consequence, reported in `docs/research/S29_regle_egalites_mesure.md` after this ADR is
committed** — never a criterion, and no such value appears anywhere in this file.

### D4 — Scope of the code change this ADR describes (and does not authorise)

- **One implementation site:** `bench/runners/run_pilot.py:59 score_trec`. The rule is implemented
  there and nowhere else, so that the docstring's claim — one code path, three methods — stays true.
- **No caller is rewritten.** The 51 call sites keep their signatures; their **numbers** move.
- **No qrels, no corpus, no query set, no `.trec`, no `baseline_lock.json`** is touched by the rule.
  `baseline_lock.json` seals the **e5 / keyword** baseline; ADR-0012 F6.2 and ADR-0009 A2.14 both
  state that no outcome opens it, and this ADR does not.
- **This ADR authorises none of the above.** It describes the change; the review and the acceptance
  authorise it, in that order.

---

## What this ADR invalidates

**Nothing measured becomes false. Numbers change instrument.** A figure recorded under the current
tie rule remains exactly what it was: the value that this repository's scoring chain returned on that
day, on that artefact, under `doc_id` descending. What it stops being is **a figure of the installed
chain** — after the change, the installed chain is a different instrument, and a number from before
and a number from after are not commensurable without requalification.

**The two the record leans on, named:**

- **`bench/runs/S18_ladder_results.md:191`** — the within-B sealed-holdout row for the standing
  arm (n=310), carrying nDCG@10, `Δ +0.041352`, `p 0.0089`, `CI [+0.011744, +0.071714]`, `d_z +0.150`.
  **What happens to it:** it is not rewritten, not retracted and not marked wrong. It becomes the
  record of its epoch and stops being a **target**. The **ADR-0008 within-B win rests on this
  nDCG@10**; whether Δ keeps its sign, its size or its significance under the new rule is **not
  measured and not assumed here** — `[NON VÉRIFIÉ]`, and it is one of the things
  `docs/research/S29_regle_egalites_mesure.md` measures.
- **`bench/runs/S20_a2_fresh_holdout.md:106`** — the July reproduction of that same value on the
  previous host. **What happens to it:** the same. It additionally records a reproduction *of the
  old instrument's number*; after the change it can no longer be quoted as a reproduction of
  anything the installed chain produces. Its own artefacts (`.trec`, qrels, `result.json`) are in a
  temporary directory that no longer exists (`S20_a2_fresh_holdout.md:205`), so this row **cannot be
  recomputed under the new rule at all** — a limit stated here rather than discovered later.

**One live gate passes through this scorer and must be named.** ADR-0009 **A2.11 condition 1**
requires a fresh Form B control in the same session as the 922 primary — *« D1 0.396385 to 6 dp »*
plus N ≥ 3 byte-identical sealed-150 `.trec` on both arms (`ADR-0009:634`). That 6-dp gate is
crossed **through this scorer**. Changing the tie rule reopens it mechanically. The 922 primary is
**unspent**, so this is a live consequence and not a historical one.

**[CORRECTED S30 — the premise in the paragraph above is FALSE, and the superseded wording is kept in
place, quoted and dated, rather than erased: *« The 922 primary is unspent, so this is a live
consequence and not a historical one. »*]** **The 922 primary is spent.** It was computed **once**, on
**2026-08-26**, and committed as **`e7e7cab`**; the marker of un-spentness ADR-0009 wrote down in its
own words — *« the 922 primary remains un-spent and
`bench/runs/S21_within_c_corroboration_decision.json` remains absent »*
(`docs/adr/0009-within-c-corroboration.md:587-588`, `:700-702`) — is **present and tracked at HEAD**
(`git ls-files --error-unmatch`, exit **0**), carrying `computed_once` **`true`**, `primary.n`
**`922`** and `verdict` **`CORROBORATES`**; and **condition 1 itself is recorded discharged in that
same artefact** — `positive_control.B1_cross_time_d1` has `computed` **`0.396385`** = `recorded`
**`0.396385`**, `n_queries` **`150`**, `passed` **`true`**. Those ADR-0009 sentences were **true when
Amendment 2 was written, before S21 ran**; nothing dated them, and every later record that quoted them
re-published a transient state as current. **The consequence named above is therefore historical, not
live:** the gate **passed** in August and, D4 being **`m = 1`** and spent, **it cannot fail again**.
What a tie-rule change actually does is make **a recorded past pass no longer reproducible under a new
instrument** — a statement about comparing numbers across scoring regimes, not a live gate blocking a
future run. See `docs/adr/0009-within-c-corroboration.md` § **Amendment 3 (S30)** (`50255ab`,
`Status: Proposed`), A3.2 / A3.3, which records this where the gate lives. **This correction WEAKENS
the procedural objection that rested on the premise; it does NOT annul it** — ADR-0009 **A2.5 Form B /
B1 cross-time reproduction** is a **standing** clause that further runs would use, and whether the
objection survives is **for the fresh non-Claude review and the operator**, not for this record.
**Nothing here changes this ADR's `Status`, accepts it, authorises any code, or makes F7 pass, and no
fine-tuning result exists or is stated in any direction.**

### The comparability guard, proposed in code terms and NOT written here

The repository already refuses one class of incommensurable comparison **in code**:
`transfer_eval.py` raises `ComparabilityError` on any absolute `llm_judge` × `native` compare, at
three sites (`:139`, `:158`, `:222`). **There is no equivalent for comparison across scoring
regimes, and that is exactly the object this ADR creates.** Nothing in the repository today prevents
a reader from quoting a pre-change anchor beside a post-change number. Proposed shape, so that a
reader **or a test** can tell which regime produced a number:

1. **`score_trec` returns the regime.** A `"tie_policy"` field beside the metrics, carrying an
   explicit version string (e.g. `expected-over-tie-groups/v1`), so the regime travels **with the
   number** rather than with the reader's memory.
2. **Every recorder writes it.** Any runner that persists a metric into `bench/runs/` writes
   `tie_policy` next to it. A record with **no** `tie_policy` field means *pre-regime* — which is a
   **different** value from the new one, never a missing one.
3. **A raising guard, modelled on `ComparabilityError`.** A comparison — paired statistic,
   regression gate, positive control — between two numbers whose `tie_policy` differ (or where one
   is absent) **raises**, exactly as the cross-collection guard raises. The misuse becomes
   impossible, not merely discouraged.
4. **The gates read it.** `compare.py::sp3_stat` and `eval_regression`'s G9 path refuse a comparison
   whose two sides disagree on the regime.
5. **A test pins it.** One test asserting the policy string and one worked tie fixture, so a silent
   change of tie policy fails CI rather than moving numbers quietly.

**No line of that is written by this ADR**, and the five items are a proposal for the change lot,
not a specification frozen by acceptance.

---

## The consequential amendments this would require — named, and NOT written

Both are **named here and written nowhere**. Each follows acceptance, never precedes it, and each is
its own amendment with its own review.

- **ADR-0009 — Amendment 2, A2.11 condition 3.** The five conditions are **binding** and the 922
  primary is **unspent**, so they are **active**. Condition 3 reads *« No encode-path,
  model-loading, cache-key, numeric-flag, or pinning change may be introduced before the 922 run.
  Additive recording only. »* **Precision, carried from `S29_voies_B_C.md` §4(b) and verified
  verbatim here:** a *scorer tie-break rule* is **not literally among the five enumerated
  categories**. What covers it is the **next sentence of the same condition** — *« Additive
  recording only »* — together with **A2.7**'s statement that additive recording is safe and
  changing the instrument is not. **The prohibition holds; the ground usually cited for it does
  not**, and a reviewer checking the original citation would find the gap. **Why it is touched:**
  this change is not additive recording, it is an instrument change, and A2.11 condition 1's live
  `0.396385` gate runs through it (above).
  **[CORRECTED S30 — two clauses in this bullet are FALSE as stated and are kept, quoted and dated,
  rather than erased: *« the 922 primary is unspent, so they are active »* and *« A2.11
  condition 1's live `0.396385` gate »*.]** **The 922 primary is SPENT** — computed once on
  **2026-08-26**, `e7e7cab`, the decision artefact present and tracked at HEAD with `computed_once`
  `true`, `primary.n` `922`, `verdict` `CORROBORATES` — and **condition 1 is recorded DISCHARGED** in
  that artefact (`positive_control.B1_cross_time_d1`: `computed` `0.396385` = `recorded` `0.396385`,
  `n_queries` `150`, `passed` `true`), so it is not a live gate and, D4 being `m = 1` and spent, it
  cannot fail again. **This note says nothing about conditions 2, 3, 4 and 5** — it did not establish
  their state and does not assert one. **What is unaffected is the reason this bullet gives for naming
  the amendment:** a scorer tie-break rule is still **not additive recording**, and A2.7 still
  distinguishes additive recording from an instrument change. See
  `docs/adr/0009-within-c-corroboration.md` § **Amendment 3 (S30)** (`50255ab`, `Proposed`), A3.2 /
  A3.3. **This WEAKENS the procedural objection resting on the premise and does NOT annul it; nothing
  is accepted, no code is authorised, and F7 stays missed.**
- **ADR-0012 — F5 and F7.** **F5** freezes the comparison and names `compare.py::sp3_stat` as the
  statistic; `compare.py` is a **measured caller** of `score_trec` (3 sites: `:204`, `:213`,
  `:232`), so F5's statistic would be computed from per-query values produced by a different
  instrument. **F7**'s target is `bench/runs/S18_ladder_results.md:191` — a number produced by the
  instrument this ADR moves — so F7 is touched whether or not its text changes.

---

## Alternatives considered

- **Do nothing.** Available, and it is a **state rather than an action**: the two providers keep
  disagreeing, tied relevance keeps depending on ticket-identifier lexicography, and the F7 control
  stays missed. It costs nothing and requires no one's approval. It is listed because « change
  nothing » must be a read possibility and not a forgotten one.
- **Align the two providers on one lexicographic convention (R2).** See D3. Rejected: it removes the
  visible contradiction and keeps the arbitrary dependency.
- **Change the retrieval side so ties stop occurring** (higher-precision similarity, deterministic
  disambiguation before writing the `.trec`). **Not considered a substitute and not rejected on the
  merits** — it addresses the *cause* of ties, which C2 puts outside this ADR's scope, and it would
  not repair an evaluator that answers the same tie in two directions. It remains open and is
  neither excluded nor endorsed here.
- **Re-anchor the control instead** — path C of `S29_voies_B_C.md` §5. **Out of scope by decision,
  not by argument:** the operator has chosen the path, and this ADR neither re-opens that choice nor
  argues against the alternative.

---

## Consequences

### Positive

- The scoring chain stops depending on the lexicographic order of an identifier for the one thing a
  tie decides.
- One call can no longer report two contradictory ranks for the same document.
- The reported number becomes a property of the run and the qrels alone — the same
  `(run, qrels)` pair yields the same number under any identifier scheme, any file order, any sort
  routine.
- The convention becomes citable to a published method rather than to an implementation detail of
  whichever provider `ir_measures` happens to dispatch to.

### Negative / trade-offs

- **External comparability is lost, and this is the strongest argument against the decision.**
  `doc_id` descending is `trec_eval`'s canonical convention, the field's reference tool since
  TREC-1. Departing from it means this lab's numbers are no longer directly comparable to numbers
  computed the standard way — a real cost, paid deliberately, and it is why R1's case is recorded in
  D3 rather than dismissed.
- **The expectation is not the score of a realisable ranking.** It is a mean over orderings the
  system permits, so no single result list would produce it. That is the known price of the method.
- **Its behaviour on collections A and C is untested here.** No probe in this repository has
  exercised the expectation-based rules on A or C (`S28_egalites_evaluateur.md` §7 point 7) —
  `[NON VÉRIFIÉ]`.
- **Every recorded number becomes a number of another instrument** (see *What this ADR
  invalidates*), across **20 files** and **51 call sites**, including the G9 regression gate, the CI
  fixture, one test, and the four diagnostics that produced this dossier's own figures.
- **Two collections move, not one.** Across the six June anchor artefacts (bge-m3 · qwen3-0.6B ·
  gte-Qwen2-1.5B, collections **B and C**), **17 queries** distinguish descending from ascending
  tie-breaking (`S29_recuperation_ecart.md` §H9). A tie-rule change is not a within-B event.
- **The defect it repairs is rare.** **5 of 310** holdout queries carry a tie group mixing relevant
  and non-relevant documents — the only case where the tie rule decides anything at all
  (`S28_egalites_evaluateur.md` §4.1, five identifiers confirmed). A reader should weigh the blast
  radius against that number, in both directions.

### Deferred

- **The upstream cause** — why a fp16 query embedding moves by one ULP — stays open, exactly where
  S21 left it. Nothing here approaches it.
- **The cross-time `gte-small` encode gate at the recorded within-B value** has never been run on
  this machine, so its outcome is unknown; note that under this ADR that value is produced by the
  instrument this ADR moves, so the gate would have to be requalified before it could be read
  (`S29_voies_B_C.md` §3).
- **The five-item comparability guard** is proposed, not specified, and not written.

### Falsifier / rollback

Written now so it is accepted in advance rather than discovered:

1. **A pre-change anchor is quoted beside a post-change number without requalification.** Nothing in
   the code prevents it today; that is what the guard exists to make impossible.
2. **The expectation-based rule turns out to carry its own untested fragility** on collection A or
   C, where no probe has exercised it.
3. **The upstream cause turns out to be recoverable.** The defect would then have been in the
   encoding leg, and the scoring instrument will have been changed for a symptom. This one is
   partly foreseeable **now** and is accepted as such, not deferred as a surprise.
4. **Rollback** is a revert of one function plus a requalification of everything measured in
   between — which is precisely why the guard's `tie_policy` field is proposed as part of the
   change and not after it.

---

## Reserves

A reserve is a finding, not a licence.

1. **This ADR does not make F7 pass, and does not pretend to.** S28 enumerated seven tie rules,
   computed all seven on both reachable artefacts, and **none returns the F7 target**
   (`S28_egalites_evaluateur.md` §3.4 point 1). Whoever reads this ADR as the repair of the blocked
   control has misread it.
2. **The F7 situation is not resolved by this ADR.** ADR-0012 F7 stands as written and remains
   binding; ADR-0012 Amendment 1 stays `Proposed` and was returned `Verdict: REJECT` by a non-Claude
   reviewer (`docs/audit/SOCLE_S29/AUD3_f7_codex_verdict.md:132`); `bench/runs/F1_decision.json`
   still carries `"status": "fail"` / `"verdict": null`.
3. **The fine-tuned arm stays unscored.** It has never been scored, it is not scored here, its
   `.trec` was not opened by this lot, and **no fine-tuning result is stated in any direction.**
4. **The timing is against this ADR and is stated rather than managed.** This changes an evaluation
   instrument **after** a pre-registered control produced by it blocked a preferred path. The
   ADR-0012 Accept froze F7 with the words *« may not be adjusted after a number exists »*
   (`:23-26`), and a number exists. The non-Claude reviewer's closing finding against the F7
   amendment applies here in its own terms: *« this is the second control gate amended after
   blocking the preferred path … disclosure does not neutralize it »*
   (`AUD3_f7_codex_verdict.md:130`). **Disclosing it does not neutralise it here either.** It is
   written into the ADR so a reviewer meets it as a stated cost rather than as a discovery.
5. **The rule's independence from the F7 target is a structural claim, not an attestable one.** It
   rests on this document being committed before any value computed under the rule exists — the
   commit order is the evidence, and it is the same class of claim the S28 reviewer found unattested
   for the rule list (C4). A reviewer should check the commit order rather than take this sentence's
   word for it.
6. **The rarity cuts both ways and is not resolved here.** 5/310 mixed tie groups is a small
   number to move 51 call sites for, and a permanent defect present in every figure the repository
   has produced is a large one to leave in place. This ADR takes the second reading; it does not
   claim the first is unreasonable.
7. **Numbers that cannot be recomputed under the new rule are named, not glossed.**
   `S20_a2_fresh_holdout.md:106` is the concrete case: its artefacts are gone, so it cannot be
   requalified — only re-labelled as the record of an epoch.
8. **This ADR does not accept itself.** `Status: Proposed`. It authorises **no code change**, and
   the review order at the head of this file is the only route out of that state.

---

## Relationship to prior ADRs / conventions

| document | relation |
|---|---|
| **ADR-0009 A2.11 condition 3 / A2.7** | **Touched — amendment required, named and not written.** See above. Conditions active; 922 primary unspent. |
| **ADR-0009 A2.11 condition 1** | The live `0.396385` 6-dp gate is crossed **through this scorer** and reopens mechanically. |
| **ADR-0009 A2.6** | **Used as the ground for D2(i)**: a tolerance whose value is chosen after seeing the gap it must absorb is not a gate. That is why R7 is rejected. |
| **ADR-0012 F5** | **Touched** — `compare.py::sp3_stat` is a measured caller (3 sites). |
| **ADR-0012 F7** | **Touched** — its target is produced by the instrument this ADR moves. F7 stands unamended and binding; nothing here amends it. |
| **ADR-0012 Amendment 1** | `Proposed`, reviewed, **REJECT**. Not revisited, not re-argued, not inherited. |
| **ADR-0012 F6.2 · ADR-0009 A2.14** | `baseline_lock.json` is not opened by any outcome, and is not opened here. |
| **ADR-0008** | Its within-B win rests on the affected nDCG@10; the direction of Δ under the new rule is unmeasured here. |
| **ADR-0005** | qrels provenance untouched — the rule reads qrels, never writes them. |
| **`CONVENTION_ABLATION_PROTOCOL` §3** | Primary metric stays **nDCG@10**; this ADR changes how it treats ties, never which metric is primary. |
| **`S28_egalites_evaluateur.md` §1, §3** | The enumeration and the computation this decision selects from. **This ADR retains R4; S28 retained none.** |
| **`S29_voies_B_C.md` §4** | The instruction document for this path, and the source of the blast-radius recipe re-counted in C3. It chose nothing; the operator chose. |

**[CORRECTED S30 — two rows of the table above carry the false premise and are kept, quoted and
dated, rather than erased.]** *« Conditions active; 922 primary unspent »* (ADR-0009 A2.11
condition 3 / A2.7 row) and *« The live `0.396385` 6-dp gate is crossed through this scorer and
reopens mechanically »* (ADR-0009 A2.11 condition 1 row) **state a premise that is false today**. The
**922 primary is SPENT** — computed once on **2026-08-26**, `e7e7cab`; the decision artefact
`bench/runs/S21_within_c_corroboration_decision.json` is **present and tracked at HEAD**
(`computed_once` `true`, `primary.n` `922`, `verdict` `CORROBORATES`) — and **condition 1 is recorded
DISCHARGED** in that same artefact (`positive_control.B1_cross_time_d1`: `computed` `0.396385` =
`recorded` `0.396385`, `n_queries` `150`, `passed` `true`). The gate **passed** and, D4 being
`m = 1` and spent, **cannot fail again**; what a tie-rule change does is make a **recorded past pass
non-reproducible under a new instrument**, not reopen a live gate. **This note asserts nothing about
conditions 2, 3, 4 and 5**, and the rest of the table is untouched. Source:
`docs/adr/0009-within-c-corroboration.md` § **Amendment 3 (S30)** (`50255ab`, `Proposed`), A3.2 /
A3.3. **It WEAKENS the objection resting on the premise and does NOT annul it; nothing is accepted,
no code is authorised, this ADR's `Status` is unchanged, and F7 stays missed.**

---

## What this ADR does NOT decide

- **It does not accept itself, and it does not authorise a code change.** Non-Claude review, then the
  operator's acceptance, then the change — in that order.
- **It does not amend ADR-0009 or ADR-0012**, and it writes no draft of either amendment.
- **It does not re-open the operator's choice of path**, does not argue for or against path C or the
  status quo, and does not re-litigate the rejected F7 amendment.
- **It states no fine-tuning result in any direction.** There is none.
- **It changes no code, no runner, no test, no corpus, no qrels, no manifest, no seal, no served
  page, no `bench/runs/` record, no `docs/ROADMAP.md`, no `.pilot/STATE.md`, and no other ADR.**
  The change set of the commit carrying this ADR is **this file only**.
- **It contains no anchor value computed under the rule it decides.** Those are measured after this
  file is committed, in `docs/research/S29_regle_egalites_mesure.md`.

---

## The non-Claude review of this ADR, and its verdict: **REJECT** (S30)

**Recorded, not resolved. Nothing above this section is edited, cut, repaired or softened by it** —
the Context, the Decision, its closed forms, the Reserves and the Consequences stand exactly as they
were written before review, so that claim → challenge reads in sequence. This follows the precedent
of ADR-0012 **§ A1.8**, where a rejection of an amendment was attached to the record it rejected
without touching the record; that precedent in turn followed ADR-0009 **A2.12**.

**The review that step (1) requires has been run and it returned `Verdict: REJECT`.** Date
**2026-09-05**; reviewer **`codex` / `gpt-5.5`** (OpenAI), **non-Claude**, **read-only**,
**non-interactive**, **exit 0**, from `.pilot/_prompts/S30/S30_L2_FINDER_ADR0013.md`. The verdict is
reproduced **verbatim and in full**, with its provenance, its independent re-measurements, its
confirmations and its reserves, in `docs/audit/SOCLE_S30/AUD3_adr0013_codex_verdict.md`. The reviewer
was given this record, the measurement document `docs/research/S29_regle_egalites_mesure.md`, the
documents where the routes were instructed, ADR-0009 **A2.6** and **A2.11**, and **both S29 verdicts**
(`docs/audit/SOCLE_S29/AUD3_f7_codex_verdict.md`, `AUD3_voies_codex_verdict.md`); it was told the
operator **had already chosen among the S29 routes** and that it **must not re-open, rank or recommend
among them**, and that it must **state no fine-tuning result in any direction**.

**The two objections that carry the verdict**, in the reviewer's own terms. Elisions are marked `[…]`
and remove only citation links and connective sentences; nothing is paraphrased inside the quotes, and
the block is reproduced unelided in the verdict file.

**1 — A specification defect in the rule this ADR decides.** The nDCG closed form at `:186` — expected
gain `r/g` in a tied group — is correct **only for binary qrels**:

> The nDCG closed form is only correct for binary qrels as written. […] That is correct when every
> relevant gain is 1. It is not the general nDCG rule for this shared scorer: collection A has graded
> qrels, and the measurement document itself found that the installed scorer uses linear graded gain
> […]. For graded qrels, the expected gain in a tied group is `sum(gain(doc))/g`, not `r/g`. This is a
> real specification defect because `score_trec` is qrels-agnostic and is called by
> transfer/collection-A paths.

The graded-qrels finding is the measurement document's own, at
`docs/research/S29_regle_egalites_mesure.md:127`. **The closed form at `:186` is not rewritten here.**

**2 — A procedural objection, which is the sentence the verdict turns on.** This ADR names at `:312`
the live **ADR-0009 A2.11 condition-1** gate that runs through this scorer. The reviewer
**independently re-measured the break** — **`0.396384978 → 0.394604968`**, rounded **`0.394605`**, so
the live `D1 0.396385` gate no longer passes — and recorded that **the record proposes no replacement
value** (`docs/research/S29_regle_egalites_mesure.md:219`). Having argued both readings of *« is this
the same blocked control, worked around? »* — and quoted its predecessor's warning that disclosure
does not neutralize post-blocking gate changes (`docs/audit/SOCLE_S29/AUD3_f7_codex_verdict.md:128`) —
it concluded:

> **I accept the scorer defect as real; I do not accept adopting this ADR before the live gate
> amendment is written and reviewed.**

**No replacement value is proposed here and no gate amendment is drafted here.** Writing one is a
fresh amendment needing a fresh review, and commissioning it is the operator's call.

**[CORRECTED S30 — the premise this objection was handed is FALSE, and the record above is kept
exactly as written, including the reviewer's verbatim block, which is not touched, not annotated
inside its fence and not renumbered.]** The paragraph above says *« the live **ADR-0009 A2.11
condition-1** gate »* and *« the live `D1 0.396385` gate no longer passes »*. **The gate is not live.**
The 922 primary was computed **once**, on **2026-08-26**, and committed as **`e7e7cab`**;
`bench/runs/S21_within_c_corroboration_decision.json` is **present and tracked at HEAD**
(`computed_once` **`true`**, `primary.n` **`922`**, `verdict` **`CORROBORATES`**), and **condition 1 is
recorded discharged in that same artefact** (`positive_control.B1_cross_time_d1`: `computed`
**`0.396385`** = `recorded` **`0.396385`**, `n_queries` **`150`**, `passed` **`true`**). D4 is
**`m = 1`** and spent, so the control **cannot fail again**.

**Whose error this was: the lab's, and it was handed to the reviewer.** The dispatch prompt
`.pilot/_prompts/S30/S30_L2_FINDER_ADR0013.md:64` put the premise in front of the reviewer as fact —
*« the **live, in-force ADR-0009 A2.11 condition-1 gate** (`D1 0.396385` to 6 dp, on the 922 primary
that is still unspent) »* — and this ADR's own `:312-316` and `:353` said the same. The reviewer did
not discover the premise; it reasoned correctly from what it was given. **A false premise supplied to a
reviewer is not cured by the review.**

**What this changes and what it does not, stated so it cannot be read backwards.** It **weakens** the
procedural objection that rests on the premise: the objection's *« live gate »* is a gate that
**passed** and is discharged. It **does NOT annul it.** What remains true is that a tie-rule change
makes a **recorded past pass non-reproducible under a new instrument**, and ADR-0009 **A2.5 Form B /
B1 cross-time reproduction** is a **standing** clause that further runs would use. **Whether that is
enough to sustain the objection is for the fresh non-Claude review and the operator, and it is not
decided here.** `Status` stays **`Proposed`**, the verdict stays **`REJECT`** and is neither answered
nor argued with, no replacement value and no gate amendment is drafted, no code is authorised, F7
stays missed, and **no fine-tuning result exists or is stated in any direction**. Source:
`docs/adr/0009-within-c-corroboration.md` § **Amendment 3 (S30)** (`50255ab`, `Status: Proposed`),
A3.2 / A3.3 — cited, not duplicated.

**What the reviewer confirmed by independent re-measurement**, kept separate from what it read, in its
own separation (*« I independently reproduced the load-bearing figures without encoding or model
load »*): the **21 anchor table rows it checked** matched the document, including **`0.576118636`**,
**`0.394604968`** (rounded `0.394605`), the **15 rise / 3 fall / 3 unchanged** split and **`R@100`
unchanged on all checked rows**; the reconstructed D1 within-B row reproducing `score_trec = 0.535097`
and R4 `0.535162944`; via `diag_ties_s28.py`, the F7-control R4 row `0.576119 / MRR 0.543141`, the June
row `0.576766` and **the provider split**; and **the blast radius reproducing exactly** — **58** matched
`.py` lines = **1 definition + 4 textual mentions + 2 subprocess strings + 51 in-process call sites**,
`bench/runners` holding **52** Python modules, with the indirect **G9** path
`bench/runners/eval_regression.py:283` → `bench/runners/run_pilot.py:112`. **Nothing failed to
reproduce**; the rejection rests on the reasoning of this record, not on an error in its numbers.

**What the mathematics review confirmed.** *« For binary qrels, the closed forms are correct. »* The
reviewer re-derived nDCG, RR and R@k under the stated expectation over uniform orderings, and found
that **the straddling-group truncation at `:231` « matches the definition of expectation over
permutations »**.

**The limit on the pre-registration ordering, which is not separable from the finding.** `0d40874`
adds only this ADR at **19:05:27**; `8cc97c1` adds only the measurement document at **19:14:38**. In
the reviewer's words: *« This establishes repository-level ordering only. It does not establish that
no uncommitted local calculation existed before `0d40874`; terminal logs or append-only execution
records would establish that. »* The word this record may use is **ordered**, not **attested**.

**The reserve attached to exact equality.** The predicate defined at `:178` is well defined **at the
serialized `.trec` level** and *« reproducible for a fixed file »*, but *« not stable across
dtype/platform/re-encode; near-ties remain ordered, and one ULP can move a document into or out of
exact equality. »* It is *« coherent with A2.6's ban on fitted tolerances »*
(`docs/adr/0009-within-c-corroboration.md:546`), **« but it should not be sold as solving numerical
instability. »**

**Consequence, in one sentence: this ADR is not accepted, `bench/runners/run_pilot.py:59 score_trec`
and its 51 in-process call sites are unchanged, neither defect the reviewer named is repaired here,
and the operator has not been asked by this record to decide anything.**

`Status` stays **`Proposed`**. The header is **not** changed, the ADR is **not** marked `Rejected`,
`Accepted` or `Superseded`, and no `Deciders:` value is added — the S29 precedent kept the record as
submitted, with its review attached. Of the three steps this ADR's own header names — **(1)** a
non-Claude review, **(2)** the operator's acceptance, **(3)** the code change — **the first has now
been run and did not clear**; the second has not been requested and the third has not happened. No
route instructed in S29 is re-opened, ranked or recommended here, and **no fine-tuning result exists
or is stated in any direction** — the arm was encoded and never scored.

---

## Amendment 1 (S30) — the closed forms of D1(b), generalised beyond binary qrels · **Status: ACCEPTED (S30, 2026-09-05, with this ADR) — and its replacement for D1(b) is now the operative rule.** **[The body of this amendment below is kept EXACTLY as it was written on 2026-09-05 before the acceptance — including its own *« `Proposed` — not accepted, not in force »* sentence, A1.7's conditional *« would read as follows »*, and A1.9 point 1's `Status: Proposed`. Those are dated statements of what the amendment lot itself did, they are not erased, and they are SUPERSEDED by § *Accept (S30)* at the end of this file, which is the operative text. Nothing below this line is edited, and the line count of this file is unchanged above the appended Accept section, so every `:NNN` citation into this record still resolves.]**

**Date:** 2026-09-05 · **Proposed by:** eval-lead (S30, lot `S30_L8_ADR13_GRADED`) · **Status:
`Proposed` — not accepted, not in force.** **D1(b) as written above is unchanged and remains the text
of this ADR.** It stays the text until a **non-Claude finder** has reviewed this amendment and the
**operator** has accepted it — in that order, which is F7's own sentence
(`docs/adr/0012-embedder-finetune-preregistration.md:263-265`) and the order this ADR's own header
names. Nothing below is in force because it is written here. This section is **purely additive**: no
line of this ADR is edited, moved or removed, the `Status:` header is untouched, no `Deciders:` value
is added, and the original D1(b) is quoted in A1.7 beside its proposed replacement so that both are
readable at once. The internal `:NNN` citations this record and its sibling documents use are
unaffected, because nothing above this line moves.

> **THIS AMENDMENT CARRIES NOT ONE COMPUTED VALUE.** No anchor, no nDCG, no MRR, no recall, no delta,
> no re-scored figure, no *« under this form the gate becomes … »*. **No scorer was run by the lot
> that wrote it** — not `ir_measures.calc_aggregate`, not `run_pilot.score_trec`, not `ranx`, and no
> `.trec` was scored in any way. What it does carry is of two kinds only: **algebra** (expectations
> derived by hand from the definitions of the three measures) and **reads** (line-cited source of the
> installed packages, and the gain column of the committed qrels files, counted). The reason is the
> S29 lesson and it is stated here rather than assumed: **a rule chosen because it returns a wanted
> number proves only that a search happened.** What this corrected form returns on the repository's
> recorded anchors is a **separate lot, after this one, in a separate commit** — exactly as `0d40874`
> preceded `8cc97c1`, and for the same reason.

### A1.0 — Why this amendment exists, and the fact that carries it

The non-Claude review that F7 requires was run on this record and returned **`Verdict: REJECT`**
(§ *The non-Claude review of this ADR* above; verdict file
`docs/audit/SOCLE_S30/AUD3_adr0013_codex_verdict.md`). Its **first objection is a specification
defect, not an opinion**: the nDCG closed form written at `:186` is correct only for **binary**
qrels, and the shared scorer it specifies is called on a collection whose qrels are **graded**.

**The fact that has to be recorded before the repair, because it is the finding and not a footnote:
three Claude lots wrote, measured and cross-checked the material this defect sits in, and none of
them saw it.** `S29_L14_ADR_B` wrote D1(b); the measurement lot that produced
`docs/research/S29_regle_egalites_mesure.md` **measured the graded gain function itself** — its §3(b)
records that collection A's gain function *« a dû être mesurée et non supposée »*, that a `2^g − 1`
re-implementation failed the instrument gate and that the installed scorer uses a **linear** graded
gain (`:127-140`) — and still did not carry that finding back to the `r/g` written in the ADR
committed **one commit earlier** (`0d40874` → `8cc97c1`); and the lot that attached the verdict to
this record transcribed the objection
without repairing it, correctly, because repairing a record in flight is what the review forbids. The
defect survived a writer, a measurer and a cross-checker of the same model family. **That is a
convergence failure of the kind ADR-0009 A2.12 and this lab's own doctrine name, and it was caught by
the non-Claude gate — which is the argument for keeping that gate, stated by the only case that can
make it.**

### A1.1 — What the reviewer found, in its own words

Quoted from `docs/audit/SOCLE_S30/AUD3_adr0013_codex_verdict.md` § 2, which reproduces the reviewer's
final reply verbatim. Elisions are marked `[…]` and remove only citation links; nothing inside the
quote is paraphrased.

> The nDCG closed form is only correct for binary qrels as written. ADR-0013 says `r/g` expected gain
> for a group with `r` relevant documents at […]. That is correct when every relevant gain is 1. It
> is not the general nDCG rule for this shared scorer: collection A has graded qrels, and the
> measurement document itself found that the installed scorer uses linear graded gain […]. For graded
> qrels, the expected gain in a tied group is `sum(gain(doc))/g`, not `r/g`. This is a real
> specification defect because `score_trec` is qrels-agnostic and is called by transfer/collection-A
> paths.

**The last clause is verified here rather than taken on the reviewer's word.** `transfer_eval.py:386`
calls `_run_pilot.score_trec(run_path, triple["qrels"])`, and the triple it resolves for collection A
carries `corpus/qrels/A_zenodo7384758_qrels.trec` (`bench/runners/test_transfer_eval.py:132`). The
scorer's own docstring is qrels-agnostic by design — one code path, three methods, *« on the SAME
qrels »* (`run_pilot.py:62-64`) — so **the qrels file decides what the closed form must be, and D1(b)
as written assumes an answer for it.**

**And the reviewer gave one half of the repair, not the whole of it.** It generalised nDCG@k and left
RR@k and R@k unexamined. A1.3 and A1.4 examine them, and find that **the generalisation is not one
substitution but two different quantities that D1(b) writes with one symbol.** An amendment that
silently corrected nDCG and left the other two alone would be the same defect one level down.

### A1.2 — nDCG@k, generalised: the derivation, the reduction to binary, and the ideal denominator

**Setup, and it is the one D1(a) already fixes.** For a query `q`, the documents of the run are
partitioned into tie groups by exact score equality, groups taken in score-descending order. Write
`G` for a group of `g` documents occupying positions `p … p+g−1` (1-indexed), and

    gain(d) := the integer relevance of (q, d) in the qrels, or 0 if the qrels carry no row for it.

**Derivation.** DCG@k is `Σ_{ranks j ≤ k} gain(doc at j) / log2(j+1)`. Under the uniform distribution
over the `g!` orderings of `G`, the document landing at position `p+m` is uniform over `G`, so

    E[ gain(doc at p+m) ]  =  ( Σ_{d ∈ G} gain(d) ) / g      for every m in [0 … g−1].

Every position of the group therefore carries **the same expected gain, the group's mean gain**, and
by linearity of expectation

    E[ DCG contribution of G ]  =  ( Σ_{d ∈ G} gain(d) / g ) × Σ_{j = p}^{min(p+g−1, k)} 1 / log2(j+1).

**So the general expected gain per tied position is `Σ_{d ∈ G} gain(d) / g` — the reviewer's
`sum(gain(doc))/g` — and `r/g` is the special case, not the rule.** The symmetry argument D1(b)
already uses is the correct one; what it substituted into it was a count where a sum belongs.

**Reduction to binary — the amendment changes nothing on a binary collection.** If every judged
document carries gain exactly `1` and every unjudged document gain `0`, then `Σ_{d ∈ G} gain(d)` is
by definition the **number** of judged documents in `G`, which is the `r` of the original text.
`Σ gain / g` **is** `r/g`, position by position, group by group, query by query. This is an algebraic
identity, not a measurement: **no number computed on a binary qrels file moves because of this
amendment**, and none is computed here to say so.

**The ideal denominator: the original text's claim holds, and is not amended.** D1(b) says *« The
ideal DCG denominator is unchanged: it is a function of the qrels, not of the run. »* IDCG@k is built
from the multiset of graded labels the qrels carry for `q`, sorted descending, discounted and
truncated at the cutoff. **It contains no reference to the run, therefore none to the tie grouping,
therefore none to any permutation.** Two riders, both stated rather than left implicit:

1. It is a function of the qrels **and of `k`** — the installed scorer truncates the ideal at the
   cutoff, which is **measured**, not assumed: the instrument gate whose table sits at
   `S29_regle_egalites_mesure.md:133-138` accepted the linear gain **with a truncated ideal** and
   rejected the untruncated variants, and `:140` states that conclusion.
2. Because IDCG@k is a per-query **constant**, the expectation passes through the division —
   `E[nDCG@k] = E[DCG@k] / IDCG@k`. That is what makes a closed form legitimate at all, and it is
   equally true with graded gains as with binary ones.

### A1.3 — RR@k and R@k do not consume gains; they consume a **threshold**, and the threshold is measured

This is the half the reviewer did not examine. **Neither RR nor R reads a gain magnitude.** Each
binarises the qrels at a `rel` threshold and counts. The threshold in force is **not** taken from
documentation or from memory below; it is read in the packages **as installed** under
`.venv/lib/python3.12/site-packages/` (`ir_measures` **0.4.3**, `pytrec-eval-terrier` **0.5.10**),
and `score_trec` passes **no** `rel` argument (`run_pilot.py:69` — `measures = [nDCG @ 10, RR @ 10,
R @ 100]`), so each measure's default applies.

| measure | provider that serves it | threshold in force | where that is read, as installed |
|---|---|---|---|
| **RR@10** | `MsMarcoEvaluator` | **`rel = 1`** | default declared at `ir_measures/measures/rr.py:19` — `'rel': ParamInfo(dtype=int, default=1, desc='minimum relevance score to be considered relevant (inclusive)')`; applied at `ir_measures/providers/msmarco_provider.py:34-35` — `if qrel.relevance >= rel: self.qrels_by_rel[rel].setdefault(...)[qrel.doc_id] = 1`, the value read from the measure at `:20` |
| **R@100** | `PytrecEvalEvaluator` | **`rel = 1`** | default declared at `ir_measures/measures/r.py:17` (same `ParamInfo` line, `default=1`); routed as `recall_100` into an invocation keyed on `measure['rel']` at `ir_measures/providers/pytrec_eval_provider.py:98-100`, and handed to `pte.RelevanceEvaluator(..., relevance_level=rel_level, ...)` at `:204`, whose parameter is documented *« Minimum relevance level considered relevant (default: 1) »* at `pytrec_eval/__init__.py:112` and `:120` |
| **nDCG@10** | `PytrecEvalEvaluator` | **none — it has no `rel` parameter at all** | `ir_measures/measures/ndcg.py:17-22` declares exactly `cutoff`, `dcg`, `gains`, `judged_only`; and `pytrec_eval_provider.py:83-91` places an nDCG with no `gains` into **any** existing invocation with the comment *« Doesn't matter where this goes »* — i.e. the installed package states that nDCG's value does not depend on the invocation's `relevance_level` |

Two further reads that belong with the table:

- **The magnitude is discarded on the RR path.** `msmarco_provider.py:35` writes the literal `1` for
  every document that meets the threshold, and `ir_measures/bin/msmarco_eval.py:129` then tests only
  membership (`if pid in target_pid`). A grade-3 document and a grade-1 document are the same object
  to RR@10.
- **`judged_only` is `False` for all three** (`rr.py:20`, `r.py:18`, `ndcg.py:21`) and `score_trec`
  does not set it. **An unjudged document is therefore a gain-0, non-threshold-meeting document, not
  an excluded one** — a tie group may mix judged and unjudged documents, and the rule must treat the
  unjudged as gain 0 rather than drop them from `g`.

**The closed forms, restated in terms of « documents in the group meeting the threshold ».** Write

    r_thr(G) := | { d ∈ G : gain(d) ≥ rel } |,   with rel = 1 as installed.

- **RR@k.** Only the **first** group containing a threshold-meeting document can host the first
  relevant one, so the expectation collapses to that group, exactly as D1(b) says. Within it, with
  `r = r_thr(G) ≥ 1`: the number of `r`-subsets of the group's `g` positions whose minimum offset is
  `i` (0-indexed) is `C(g−1−i, r−1)`, and there are `C(g, r)` subsets in all, so

      P(first threshold-meeting document at offset i) = C(g−1−i, r−1) / C(g, r),   i ∈ [0 … g−r],

  which sums to 1 over that range by the hockey-stick identity, and

      E[RR@k] = Σ_i ( C(g−1−i, r−1) / C(g, r) ) / (p+i)   for i ∈ [0 … g−r] with p+i ≤ k.

  **The formula written at D1(b) is correct as an algebraic form. What it does not say is which `r`
  it means**, and A1.4 is about that.

- **R@k.** By linearity of expectation, each position of a group holds a threshold-meeting document
  with probability `r_thr(G)/g`, so a group contributing `t` positions at or before `k` contributes
  expected count `t × r_thr(G)/g`; a group entirely at or before `k` contributes its **actual**
  `r_thr(G)` (the case `t = g`), and the truncation at `:231` is the case `t < g`. The denominator is
  the number of documents in `q`'s qrels meeting the threshold — **a function of the qrels, not of
  the run**, so the tie rule does not move it, on the same argument as IDCG.

### A1.4 — The finding beyond the reviewer's half: **`r` is two different quantities, and D1(b) writes one symbol for both**

The two counts a tie group can produce are:

    S(G)     := Σ_{d ∈ G} gain(d)          — what nDCG@k consumes (A1.2)
    r_thr(G) := |{ d ∈ G : gain(d) ≥ 1 }|  — what RR@k and R@k consume (A1.3)

**They can differ, and on this repository they do.** With non-negative integer grades and `rel = 1`,
`S(G) ≥ r_thr(G)`, with **equality if and only if every threshold-meeting document in `G` carries
gain exactly 1**. Any tie group containing a document graded 2 or 3 breaks the equality. **So a
reader of D1(b) who assumes one `r` will write a scorer in which either nDCG is wrong on graded qrels
or RR and R are wrong on them — and the single symbol in the current text invites exactly that.**

**This is why the amendment does not stop at the reviewer's substitution.** Rewriting `r/g` to
`sum(gain(doc))/g` in the nDCG bullet and leaving `r` standing in the RR and R@k bullets would
produce a text in which the same letter means a gain sum three lines above and a threshold count
three lines below. The correction is therefore **two named quantities**, not one substitution, and
A1.7 writes them out.

**What does not change.** On a binary qrels file `S(G) = r_thr(G)` by A1.2's identity, so the two
quantities coincide and the amended text and the original text specify the same computation.

### A1.5 — Where the gain function comes from: the qrels, never an assumption of binarity

**The rule must read gains from the qrels file passed to `score_trec`, and from nowhere else.** The
chain is short and is read here rather than described: `run_pilot.py:70-74` hands
`ir_measures.read_trec_qrels(str(qrels_path))` straight to the providers;
`pytrec_eval_provider.py:53` converts it to a dict-of-dict and `:173` / `:204` hand it to the
evaluator **unmapped**, since `score_trec` passes no `gains` argument (the remap branch at
`:170-172` is not taken); `msmarco_provider.py:31-35` thresholds it. A TREC qrels row is
`<query_id> 0 <doc_id> <relevance>` (`pytrec_eval/__init__.py:55-56`), and the fourth column **is**
the gain the installed scorer uses, linearly (`S29_regle_egalites_mesure.md:140`).

So, stated as the rule and not as a description:

- `gain(d)` for a document of the tie group is the fourth column of the qrels row for `(q, d)`, or
  **0** when the qrels carry no such row. **Binarity is never assumed** and no `2^g − 1` transform is
  applied — that transform was **tried and rejected by measurement**, not by preference
  (`S29_regle_egalites_mesure.md:140`).
- **On a qrels file whose gains are all 1: nothing changes.** `S(G)` is the count of judged documents
  in the group, equal to `r_thr(G)`, and every closed form returns what the original D1(b) specified.
- **On a qrels file carrying grades > 1:** `S(G)` and `r_thr(G)` diverge, nDCG@k follows `S(G)`, RR@k
  and R@k follow `r_thr(G)`, and only the amended text specifies the expectation of what the
  installed scorer actually computes.

### A1.6 — Which collections this reaches, **measured from the qrels files themselves**

Not asserted on the reviewer's word. The gain column of every committed qrels file was read and its
distinct values counted, with `awk '{print $4}' <file> | sort -n | uniq -c` over
`corpus/qrels/*.trec`. Counting distinct grades in a committed file is a read, not a computation, and
**no scorer was involved**.

| collection | file | rows | queries | distinct gains (count per grade) | verdict |
|---|---|---|---|---|---|
| **A** | `A_zenodo7384758_qrels.trec` | 2 486 | 147 | **`{1, 2, 3}`** — 513 / 1 008 / 965 | **GRADED** |
| **B** | `B_gitbugs_qrels.trec` | 344 | 302 | `{1}` — 344 | binary |
| **B** | `hadoop_qrels.trec` | 134 | 128 | `{1}` — 134 | binary |
| **B** | `hbase_qrels.trec` | 120 | 111 | `{1}` — 120 | binary |
| **B** | `spark_qrels.trec` | 556 | 509 | `{1}` — 556 | binary |
| **C** | `C_cqadupstack_qrels.trec` | 239 | 150 | `{1}` — 239 | binary |
| **C** | `C_cqadupstack_judgeable1072_qrels.trec` | 1 693 | 1 072 | `{1}` — 1 693 | binary |

**The reviewer's claim is confirmed and not contradicted: A is the only graded collection, and it is
graded on 1 973 of its 2 486 rows** (grades 2 and 3), so the divergence of A1.4 is the common case on
A and not an edge case. Two cross-checks that were available and were made:

- **B's four files total 1 154 rows, every row graded 1** — which is independently what ADR-0012 **F2**
  counted when it built the training pairs (`:107-108`, *« 1154 rows, every row graded `1` — binary,
  upstream-authored »*). Two counts, taken by different lots for different purposes, agree.
- The **2 486 rows** of A agree with the count `S29_regle_egalites_mesure.md:128` reports.

**The limit of this table, stated rather than left to be found:** it covers `corpus/qrels/*.trec` and
nothing else. Qrels artefacts held elsewhere — the sealed-holdout qrels under `bench/runs/`, for
instance — **were not opened by this lot** and this table makes no claim about them. `bench/` was
outside this amendment's scope.

**Consequence for D1(b)'s reach.** Exactly one of the three collections carries graded judgements,
and it is the one reached by the qrels-agnostic call the reviewer named
(`transfer_eval.py:386` → `corpus/qrels/A_zenodo7384758_qrels.trec`). On B and C the amendment is a
no-op by A1.2's identity; **on A it is the difference between a specification that matches the
installed scorer and one that does not.**

### A1.7 — The proposed replacement for D1(b), written out in full

**The original, kept quoted and visible** (it remains in force above, at `:182-194`, unedited):

> **(b) What happens to a tie group.** It is **not ordered**. A group of `g` documents holding `r`
> relevant ones, occupying positions `p … p+g−1` in the ranking, contributes to each measure the mean
> of that measure over the `g!` orderings of the group. Closed form, no sampling:
>
> - **nDCG@k** — every position of the group carries the same expected gain `r/g` by symmetry:
>   `DCG += (r/g) × Σ 1/log2(q+1)` over `q` in `[p … min(p+g−1, k)]`. The ideal DCG denominator is
>   unchanged: it is a function of the qrels, not of the run.
> - **RR@k** — only the **first** group containing a relevant document can carry the first relevant
>   one, so the expectation collapses to that group:
>   `E[RR] = Σ_i ( C(g−1−i, r−1) / C(g, r) ) / (p+i)` for `i` in `[0 … g−r]` with `p+i ≤ k`.
> - **R@k** — the same expectation. Where the cutoff does not fall **inside** a tie group it is a
>   no-op, which is the case throughout collection B, where every query carries exactly 100 documents
>   and the cutoff is 100 (`S28_egalites_evaluateur.md` §3.4 point 3).

**The proposed replacement.** If — and only if — this amendment is reviewed by a non-Claude finder
and accepted by the operator, in that order, D1(b) would read as follows.

> **(b) What happens to a tie group.** It is **not ordered**. A group `G` of `g` documents occupying
> positions `p … p+g−1` in the ranking contributes to each measure the mean of that measure over the
> `g!` orderings of the group. Closed form, no sampling.
>
> **The two quantities a group carries, which are different objects and are named separately because
> the measures consume different ones:**
>
> - `gain(d)` is the **fourth column of the qrels row** for `(q, d)`, or **0** when the qrels carry no
>   row for it. It is read from the qrels and never assumed binary; the installed scorer applies it
>   **linearly** with the ideal truncated at the cutoff (measured, `S29_regle_egalites_mesure.md:140`).
> - `S(G) = Σ_{d ∈ G} gain(d)` — the group's **gain sum**. Consumed by nDCG@k.
> - `r(G) = |{ d ∈ G : gain(d) ≥ rel }|` — the number of group members **meeting the relevance
>   threshold**. Consumed by RR@k and R@k. As installed, `rel = 1` for both, by their own declared
>   defaults (`ir_measures/measures/rr.py:19`, `ir_measures/measures/r.py:17`), which `score_trec`
>   does not override.
>
> `S(G) ≥ r(G)`, with **equality if and only if every threshold-meeting member carries gain exactly
> 1** — i.e. on binary qrels the two coincide and everything below reduces to the binary forms.
>
> - **nDCG@k** — every position of the group carries the same expected gain `S(G)/g` by symmetry:
>   `DCG += (S(G)/g) × Σ 1/log2(j+1)` over `j` in `[p … min(p+g−1, k)]`. On binary qrels
>   `S(G)/g = r(G)/g`. The ideal DCG denominator is **unchanged**: it is a function of the qrels and
>   the cutoff, not of the run, so no tie grouping can move it; and because it is a per-query
>   constant, `E[nDCG@k] = E[DCG@k] / IDCG@k`.
> - **RR@k** — only the **first** group containing a threshold-meeting document can carry the first
>   relevant one, so the expectation collapses to that group. With `r = r(G) ≥ 1`:
>   `E[RR] = Σ_i ( C(g−1−i, r−1) / C(g, r) ) / (p+i)` for `i` in `[0 … g−r]` with `p+i ≤ k`.
>   **The threshold count, not the gain sum**: RR discards grade magnitude
>   (`ir_measures/providers/msmarco_provider.py:35` writes the literal `1`).
> - **R@k** — the same expectation, on the **threshold count**. A group entirely at or before `k`
>   contributes its actual `r(G)`; a group straddling `k` and contributing `t` positions at or before
>   `k` contributes expected count `t × r(G)/g`. The denominator — the number of the query's judged
>   documents meeting the threshold — is a function of the qrels, not of the run. Where the cutoff
>   does not fall **inside** a tie group the straddling term is a no-op, which is the case throughout
>   collection B, where every query carries exactly 100 documents and the cutoff is 100
>   (`S28_egalites_evaluateur.md` §3.4 point 3).
>
> **An unjudged document is a gain-0, non-threshold-meeting member of its group, not an excluded
> one** — `judged_only` is `False` for all three measures as installed (`rr.py:20`, `r.py:18`,
> `ndcg.py:21`) and `score_trec` does not set it, so a tie group may mix judged and unjudged documents
> and `g` counts both.

**What that replacement does and does not move.** It changes **no other clause of this ADR**: D1(a),
D1(c), D1(d), D1(e), D2(i), D2(ii), D3, D4 and every Reserve stand exactly as written. In particular
the straddling-group truncation of **D2(ii)** is **not** amended — see A1.8, where the reviewer's
confirmation of it is recorded.

### A1.8 — What the reviewer **confirmed**, recorded beside the defect

An amendment that reported only the objection would misrepresent the review, so the confirmations are
recorded here in the reviewer's own terms (verdict file § 2, § *Mathematics*, and § 5):

- **« For binary qrels, the closed forms are correct. »** The reviewer re-derived all three
  independently — nDCG (`r/g` per tied position, truncated at `k`, IDCG denominator unchanged), RR
  (`C(g-1-i, r-1)/C(g, r)` for the first relevant at offset `i`, with `p+i <= k`) and Recall@k (the
  straddling block contributing `t*r/g`, full groups before the cutoff contributing their actual
  relevant count) — and its derivations **agree with this amendment's**, which is why A1.2 and A1.3
  present them as generalisations and not as corrections of the algebra.
- **The straddling-group truncation at `:231` is confirmed**: it *« matches the definition of
  expectation over permutations »*. **D2(ii) is therefore not amended**, and this amendment proposes
  no change to it.
- **Nothing in this record failed to reproduce.** The reviewer re-measured the load-bearing figures
  independently and reported no divergence; **the rejection rests on the reasoning of the record, not
  on an error in its numbers.** (Those figures are not restated here — this amendment carries no
  computed value.)

**So the defect is narrow and is stated narrowly: the binary case was right, and the text presented
the binary case as the general rule.**

### A1.9 — What this amendment does **not** do

1. **It does not accept itself, and it accepts nothing.** `Status: Proposed`. The header of this ADR
   is untouched, no `Deciders:` value is added, and the record is **not** marked `Rejected`,
   `Accepted` or `Superseded`. **It authorises no code change.** `bench/runners/run_pilot.py:59
   score_trec` and its **51** in-process call sites stay exactly as they are, and no number in this
   repository moves because this section exists.
2. **It does not answer the reviewer's second objection, and does not pretend to.** That objection —
   *« I accept the scorer defect as real; I do not accept adopting this ADR before the live gate
   amendment is written and reviewed »* — is about the **live ADR-0009 A2.11 condition-1** gate that
   runs through this scorer (named at `:312` above). **It is out of this amendment's hands.** A
   sibling lot of this same session, **`S30_L9_ADR9_GATE`**, is writing that amendment against
   `docs/adr/0009-within-c-corroboration.md`; **no draft of it is written here**, no replacement value
   is proposed here, and this section neither anticipates nor constrains what that lot concludes.
   Repairing the specification defect **does not lift the procedural objection**, and this amendment
   does not claim it does.

   **[CORRECTED S30 — two statements in the gloss above are FALSE, and both are kept in place, quoted
   and dated, rather than erased. The reviewer's verbatim sentence inside this point is NOT touched,
   NOT annotated inside its quotation marks and NOT re-punctuated.]**

   **(a) *« is about the live ADR-0009 A2.11 condition-1 gate that runs through this scorer »* — the
   gate is not live.** The 922 primary was computed **once**, on **2026-08-26**, and committed as
   **`e7e7cab`**; `bench/runs/S21_within_c_corroboration_decision.json` is **present and tracked at
   HEAD** (`git ls-files --error-unmatch`, exit **0**) and carries `computed_once` **`true`**,
   `primary.n` **`922`** and `verdict` **`CORROBORATES`**, and **condition 1 is recorded discharged in
   that same artefact** — `positive_control.B1_cross_time_d1`: `computed` **`0.396385`** = `recorded`
   **`0.396385`**, `n_queries` **`150`**, `passed` **`true`**. D4 is **`m = 1`** and spent, so the
   control **cannot fail again**. The cross-reference *« named at `:312` above »* still resolves and is
   left as it is: `:312-316` is itself the superseded paragraph, already corrected in place at
   `:318-340`, so a reader who follows the pointer lands on the correction. The same correction is
   carried at `:387-395` and at `:632-641`; **§ Amendment 1 was outside the scope of the lot that made
   them, which is why this site was missed.**

   **(b) *« A sibling lot of this same session, `S30_L9_ADR9_GATE`, is writing that amendment »* — no
   amendment was written.** `docs/adr/0009-within-c-corroboration.md` § **Amendment 3 (S30)**
   (`50255ab`, `Status: Proposed`) is titled, in its own words, *« A2.11 condition 1 under a changed
   scorer: **no amendment is written**, because the fact the request rests on is wrong »*. Its A3.5
   enumerates **four** forms — **(1)** re-express the target under the new instrument · **(2)** make
   the condition instrument-invariant (byte-identical `.trec`) · **(3)** change nothing here and make
   ADR-0013's acceptance conditional on the gate being spent first · **(4)** change nothing and record
   the correction of fact — and takes **(4)**, *« because it is the narrowest form that does not weaken
   the gate »*, recording **(2)** as a forward recommendation binding on nothing. Its own scope
   statement (A3.9) reads: *« **Does:** record that A2.11 condition 1 is **discharged, not live**;
   record the enumeration above and the choice among it; record the hazard in A3.7. That is all it
   does. »* **Conditions 1, 2, 3, 4 and 5 are untouched** and the byte-verbatim block above them is not
   edited. So the sentence corrected here is wrong in both halves: no amendment is *being written*, and
   on that lot's finding there is **nothing live to amend**. What that lot did leave standing is the
   hazard it names in A3.7: re-scoring the Form B `.trec` under a changed scorer **will not return the
   value condition 1 names** — a fact about comparison across scoring regimes, not a control failure.

   **The reviewer's quoted sentence stands exactly as written and is not corrected here.** It is the
   verbatim text of an external, non-Claude reviewer. The premise it reasons from — *« the live gate »*
   — was **supplied by the lab**: this ADR's own `:312-316` said it, and the dispatch prompt put it in
   front of the reviewer as fact (`:643-648` above). A false premise handed to a reviewer is the lab's
   error to record, never the reviewer's words to edit.

   **What this changes and what it does not, stated so it cannot be read backwards.** It **weakens**
   the second objection, because the gate that objection names **passed** and is discharged. It **does
   NOT annul it**: a tie-rule change still makes a **recorded past pass non-reproducible under a new
   instrument**, and ADR-0009 **A2.5 Form B / B1 cross-time reproduction** is a **standing** clause
   that further runs would use. **Whether the objection survives is for the fresh non-Claude review and
   the operator, and it is not decided here.** Everything else in this point stands as written: no
   draft of a gate amendment is written here, no replacement value is proposed here, and repairing the
   specification defect **does not lift the procedural objection**. `Status` stays **`Proposed`**,
   nothing is accepted, **no code is authorised** — `bench/runners/run_pilot.py:59 score_trec` and its
   **51** in-process call sites are unchanged — **ADR-0012 F7 stays missed**, and **no fine-tuning
   result exists or is stated in any direction**.

3. **It does not make this record accepted.** F7's sequence is unchanged and both of its first two
   steps are still owed: **(1)** a **fresh** non-Claude review — of the **amended** record, not of the
   one already reviewed — then **(2)** the operator's acceptance, then **(3)** the code. In that order
   and never in flight. The review already run does not carry over to a record that has changed.
4. **It states no fine-tuning result in any direction.** There is none: the arm was encoded and
   **never scored**. Its `.trec` was not opened by this lot.
5. **It computes nothing**, as the note at the head of this amendment states and as the lot that wrote
   it executed: no scorer was run, no run was scored, no model was loaded, no GPU was used and no
   network call was made. The only figures in this section are **row and grade counts read from
   committed qrels files** and **line numbers in installed packages**.
6. **It does not re-open the operator's choice of path**, does not rank or recommend among the routes
   instructed in S29, and does not re-litigate the rejected ADR-0012 Amendment 1.
7. **It touches no other ADR, no runner, no test, no corpus, no qrels, no manifest, no seal, no
   `.trec`, no `bench/runs/` record, no served page, no `docs/ROADMAP.md` and no `.pilot/STATE.md`.**
   The change set of the commit carrying this amendment is **this file only**, and nothing above this
   section is edited, so every `:NNN` citation into this record — including those a sibling document
   makes — still resolves.
8. **It does not claim the defect was hard to see.** It was in the text for a session, under three
   Claude lots, one of which measured the very gain function that contradicts it. **A1.0 records that
   as the finding.**

**Touches:** the closed forms of **D1(b)**, and nothing else.

**Explicitly unchanged, and not to be read as amended here:** D1(a) · D1(c) · D1(d) · D1(e) ·
**D2(i)** (exact equality, and the A2.6 ground it rests on) · **D2(ii)** (the straddling truncation,
which the reviewer confirmed) · D3 · D4 · *What this ADR invalidates* · the comparability-guard
proposal · the consequential amendments named there · *Alternatives considered* · *Consequences* ·
the eight *Reserves* · and the § *The non-Claude review of this ADR* section, whose verdict is quoted
against this amendment in A1.0 and is not edited by it.

**Pending, in this order and no other: (1) a fresh non-Claude finder's review of this amended record;
(2) the operator's acceptance.** Until both clear, this section is `Proposed`, D1(b) stands exactly as
originally written, no code changes, and **the measurement of what the corrected form returns is a
separate lot in a separate commit, after this one.**

---

## The **fresh** non-Claude review of this record **as amended**, and its verdict: **ACCEPT-WITH-CONDITIONS** (S30) — **and nothing is accepted**

**Recorded, not acted on. Nothing above this section is edited, cut, repaired or softened by it** —
the Context, the Decision and its closed forms, the Reserves, the Consequences, the § *The non-Claude
review of this ADR* section carrying the first verdict, and **§ Amendment 1 in its entirety** stand
exactly as they were written before this review, so that claim → challenge → correction → second
challenge reads in sequence. This section is **appended at the end of the file on purpose**: every
`:NNN` citation into this record — including the ones the reviewer itself makes, and the ones sibling
documents make — still resolves.

**`Status:` stays `Proposed`.** The header is **not** changed, no `Deciders:` value is added, and the
record is **not** marked `Accepted`, `Rejected` or `Superseded`. **`bench/runners/run_pilot.py:59
score_trec` and its 51 in-process call sites are unchanged.** Of the three steps this ADR's own header
names — **(1)** a non-Claude review, **(2)** the operator's acceptance, **(3)** the code change — **(1)
has now been run twice, on two different states of this record; (2) has not been requested and (3) has
not happened.** **ADR-0012 F7 remains missed** — the reviewer says so itself — **nothing here unblocks
it**, and **no outcome of the F7 question is named, ranked, recommended or hinted at.** **No
fine-tuning result is stated in any direction**: the arm was encoded and **never scored**, and its
`.trec` was not opened by this lot.

**The review that step (1) requires has been run a second time and it returned `Verdict:
ACCEPT-WITH-CONDITIONS`.** Date **2026-09-05**; reviewer **`codex` / `gpt-5.5`** (OpenAI),
**non-Claude**, **read-only**, **non-interactive**, **exit 0**, from
`.pilot/_prompts/S30/S30_L11_REVUE_FRAICHE.md`. The verdict is reproduced **verbatim and in full**,
with its provenance, its independent re-measurements, its reserves and the check that the
transcription is verbatim, in `docs/audit/SOCLE_S30/AUD3_adr0013_fresh_codex_verdict.md`.

### The verdict changed, and **both verdicts stand in the record**

The first review of this ADR returned **`Verdict: REJECT`**
(`docs/audit/SOCLE_S30/AUD3_adr0013_codex_verdict.md`, `c33996d`, attached above by `c3a5870`).
**It is not deleted, not superseded, not marked obsolete, and not edited by this section.** It was
**correct on the premises it was given** — and **one of those premises was the lab's own error**: its
objection 2 rested in part on the ADR-0009 **A2.11 condition-1** gate being *live* and the 922 primary
*un-spent*, which the lab wrote into its own dispatch prompt
(`.pilot/_prompts/S30/S30_L2_FINDER_ADR0013.md:64`) and into this ADR at `:312-316`. The 922 primary
had been **spent since `e7e7cab`** (2026-08-26) and condition 1 is **recorded discharged**; that is
established above at `:632-655` and in `docs/adr/0009-within-c-corroboration.md` § **Amendment 3**,
A3.2 / A3.3.

**So this is a second reading, not a replacement of the first.** The second reviewer read the
corrected record; the first read a record the lab had mis-described to it. **A false premise supplied
to a reviewer is not cured by the review, and it is not cured by a second review either** — what the
first objection needed was the corrected fact returned to a fresh review, and that is what happened.
The reviewer's own opening objection puts the change no higher than it goes, and it is quoted here
rather than characterised:

> 1. **The predecessor’s `REJECT` does not stand unchanged, but unconditional accept is still not warranted.** My verdict is `ACCEPT-WITH-CONDITIONS`, not `REJECT`. The false premise materially weakens objection 2: `bench/runs/S21_within_c_corroboration_decision.json` is tracked from `e7e7cab` and records `computed_once: true`, `primary.n: 922`, `verdict: CORROBORATES`, and `positive_control.B1_cross_time_d1` `computed == recorded == 0.396385`, `passed: true`. That makes the A2.11 condition-1 gate discharged, not live.

### The three conditions, **verbatim**, and **what each one binds**

Reproduced unchanged from the verdict file § 2. **What each binds was established by reading this
record, not by assertion**, and the evidence is given. **This section acts on none of them.**

**Condition 1 — binds step (2), the acceptance artefact itself. Not satisfiable before acceptance.**

> 1. The operator-facing accepted text must make the Amendment 1 replacement at `docs/adr/0013-tie-handling-in-evaluation.md:976-1016` operative, so D1(b) no longer leaves `r/g` as the general nDCG rule.

Its subject is *« The operator-facing **accepted** text »*, and no such text exists. § A1.7 introduces
the replacement blockquote with a conditional — *« and accepted by the operator, in that order, D1(b)
**would** read as follows »* (`:974`) — and § A1.9 point 1 records `Status: Proposed` and that the
amendment *« authorises no code change »*. **D1(b) at `:186` still reads `r/g`, and it is not changed
here.** Making the replacement operative **is** accepting Amendment 1, which is precisely what has not
happened.

**Condition 2 — binds step (3), the code-change lot.**

> 2. The code-change lot must implement a checkable scoring-regime guard: persisted metrics must carry a `tie_policy` or equivalent regime marker, and comparison/gate code must refuse mixed pre-change/post-change regimes.

It names its own subject: *« The **code-change lot** »*. This ADR's comparability-guard section is a
**proposal** and says so in its own closing sentence — *« **No line of that is written by this ADR**,
and the five items are a proposal for the change lot, not a specification frozen by acceptance »*
(`:366-367`) — and the reviewer reads it the same way, recording that the record *« proposes a
`tie_policy`/comparability guard at `docs/adr/0013-tie-handling-in-evaluation.md:342-367`, but does
not freeze or implement it »*. **No line of guard code is written here.**

**Condition 3 — binds an acceptance note or a change note; neither exists.**

> 3. Any acceptance/change note must state ADR-0009 A2.11 condition 1 as discharged on 2026-08-26 under `e7e7cab`, not as a live gate, and must not introduce a replacement target for the spent D4 run.

Its subject is *« Any **acceptance/change** note »* — a note attending step (2) or step (3). **This
section is neither**: it accepts nothing and changes no code. **So condition 3 binds a document that
does not exist yet, and this section does not claim to satisfy it.** Recorded as an observation and
**not** as satisfaction: the discharge is already stated in this record at `:632-655` and in ADR-0009
§ Amendment 3 A3.3, and **no replacement target for the spent D4 run is introduced here** — as none was
introduced when the first verdict was attached.

**None of the three binds this record now.** Read literally, **condition 2** binds a step that comes
*after* acceptance while **conditions 1 and 3** bind the acceptance artefact *itself*; the distinction
is written the narrow way on purpose. **The operative consequence is the same in all three cases:
nothing in them is an instruction to this lot, and this lot acts on none of them.** And the verdict is
the **reviewer's**, not the operator's — F7 names two gates and this is the first.

### What the reviewer confirmed by **independent re-measurement**, kept separate from what it read

The reviewer made the separation itself, its § 5 opening *« Independent re-measurement reproduced the
requested S30 figures. With `CUDA_VISIBLE_DEVICES=` and `.venv/bin/python` »*:

- **The graded `T2` figure** — `T2 nDCG@10 = 0.694808` — **matching an already-published value** at
  `docs/research/S29_regle_egalites_mesure.md:90`.
- **The `T2 − T1` deltas** — `-0.04654913716748743` for `nDCG@10`, **`0.0`** for `RR@10` and `R@100`.
- **`T1 == T2` on both binary runs** — B *« in all three cells »*, C *« in all three cells »*.
- **The divergence census** — A `1072/5728` all groups, `436/2843` true ties, `542/1091` top10; **B and
  C all divergent counts `0`** — matching `docs/research/S30_regle_graduee_mesure.md:260-265`.
- **Its own `--verify-threshold` run** — `RR.rel_default: 1`, `R.rel_default: 1`,
  `nDCG.has_rel_param: false` — which is the measured ground under § A1.3.

**It named no figure that failed to reproduce.** **These are its measurements, not this record's**:
nothing here re-measures them, and the lot writing this section ran no scorer, no model and no GPU.
**Two limits travel with them and are not dropped:** the dispatch prompt **named the target figures**
it was asked to reproduce (`:65-72` of that prompt), so this was a re-measurement against stated
values and not a blind reproduction; and it asked the reviewer to *« Report anything that does not
reproduce »*, which is the form in which the absence of a failure is reported.

**And its `CANNOT ESTABLISH`, recorded as the reviewer stated it — a result, not an omission:**

>    - `--selftest` could not run in this sandbox because Python could not create a temporary directory. CANNOT ESTABLISH selftest here; a writable temp directory would establish it.

**The instrument's selftest is therefore unestablished by this review**, and what would establish it is
named. This is **not** softened into « the selftest passed » or « the selftest was not needed ».

### Pre-registration: **repository-level ordering, NOT attestation**

> 6. **Pre-registration ordering is established only at repository level.** `9bb18e9` is `2026-09-05T14:15:45+02:00` and adds the instrument; `1799af3` is `2026-09-05T14:22:29+02:00` and adds the measurement. That proves repository ordering, not attestation. As the record itself says at `docs/research/S30_regle_graduee_mesure.md:402-408`, terminal logs or append-only execution records would be needed to establish no earlier local calculation existed.

**The word this record may use is « ordered ». It may not write « attested ».** That is the limit the
S29 reviewer imposed, it is restated here unstrengthened, and what would establish more — terminal
logs or append-only execution records — **is not in this repository today**.

### It found **no correction overshoot** in the records it sampled

Its objection 4: *« I did not find correction overshoot in the sampled records »*, on the ground that
superseded wording is *« generally retained quoted and dated »*, with four sites named by `file:line`
(`docs/research/S29_regle_egalites_mesure.md:229-259`, `docs/research/S29_voies_B_C.md:369-382`,
`docs/adr/0012-embedder-finetune-preregistration.md:752-754`,
`docs/audit/SOCLE_S30/AUD3_adr0013_codex_verdict.md:320-351`). On the **one site a lot deliberately
left alone** — `docs/research/S21_env_forensics.md:399-400` — it **re-derived the `git blame`
timestamps itself**: `a5b2046` at `2026-08-26T19:32:30+02:00` against the decision artefact at
`e7e7cab`, `2026-08-26T21:54:36+02:00`, *« two hours twenty-two minutes later »*, concluding *« Leaving
it alone as a dated lot statement is correct. »*

**Two limits, stated because this finding is favourable to the lab.** The reviewer wrote *« in the
**sampled** records »* and *« **generally** »* retained. **« No overshoot found in a sample » is not
upgraded here into « no overshoot ».**

### What this section does **not** do

1. **It accepts nothing and authorises nothing.** `Status: Proposed`; header untouched; no `Deciders:`;
   not `Accepted`, `Rejected` or `Superseded`. **No code changes.** `bench/runners/run_pilot.py:59
   score_trec` and its **51** in-process call sites stay exactly as they are, and **no number in this
   repository moves because this section exists.**
2. **It does not modify § Amendment 1**, does not make its replacement operative, and does not touch
   **D1(b)** at `:186`, which still reads `r/g`. It touches **no** clause of this ADR.
3. **It acts on none of the three conditions** and drafts no guard, no `tie_policy` marker, no
   acceptance note and no replacement value for the spent D4 run.
4. **It does not retire the first verdict.** `Verdict: REJECT` stands in the record beside
   `Verdict: ACCEPT-WITH-CONDITIONS`, and the file carrying it is not edited.
5. **It argues nothing back at either reviewer** — no rebuttal, no softening, no gloss inside a quoted
   block — and it re-measures nothing the second reviewer measured.
6. **It does not unblock anything. F7 remains missed**, `bench/runs/F1_decision.json` still carries
   `"status": "fail"` / `"verdict": null`, ADR-0012 § Amendment 1 stays `Proposed` and rejected, and
   **no outcome of the F7 question is named, ranked, recommended or hinted at.**
7. **It states no fine-tuning result in any direction.** There is none: the arm was encoded and **never
   scored**.
8. **It computes nothing.** No scorer was run, no run was scored, no model was loaded, no GPU was used,
   no network call was made, and no `.trec` was opened. **Every figure in this section is quoted from
   the verdict or from a committed record, with its source.**
9. **It re-opens no route** chosen by the operator in S29 and ranks none, and it **modifies no other
   ADR** — `docs/adr/0009-*.md` and `docs/adr/0012-*.md` are untouched — and nothing under `bench/`,
   `demo/`, `security/`, `docs/research/`, `.pilot/scripts/`, `.pilot/STATE.md` or `docs/ROADMAP.md`.

**Pending, in this order and no other: (2) the operator's acceptance; (3) the code change.** Step (1)
has returned twice. **Neither of the remaining two has happened, and this section requests neither.**

---

## Accept (S30)

**Appended at the end of this file on purpose.** Every `:NNN` citation into this record — 112 of
them across the repository, plus the ones this record makes into itself — still resolves: the header
and the § *Amendment 1* heading were rewritten **at their original line counts**, and nothing above
this section moved. That is the same reason the two review sections and Amendment 1 were appended.

- **Operator:** Matteo · **Session:** S30 · **Date:** **2026-09-05**
- **Accepted in the terminal**, in French, recorded **untranslated, unexpanded, unparaphrased**:
  *« Accepter, les trois conditions inscrites verbatim, et la condition 2 posée comme PRÉCONDITION
  du lot de code : rien ne bouge dans le dépôt tant que cette garde n'existe pas. »*
- **The acceptance is NOT unconditional.** ADR-0012's acceptance was — *« No condition was attached,
  and none is invented here »* (`docs/adr/0012-embedder-finetune-preregistration.md:19-20`). This one
  is not, and the difference is the substance: three conditions are inscribed **verbatim** below, and
  the second is raised by the operator from a reviewer's condition into a **precondition of the code
  lot**.
- **This is step (2) of the three this ADR's header names** — *(1) non-Claude review, (2) the
  operator's acceptance, (3) the code change*. **Step (1) has returned twice. Step (3) has NOT
  happened and this section is not it.**
- **What the acceptance changes in this file:** the `Status:` header, the `Deciders:` line, the
  review-order paragraph in the header blockquote, the § *Amendment 1* heading, and this section.
  **No clause of the Decision is deleted, and no clause of Amendment 1 is deleted.** D1(b) stands at
  `:182-194` exactly as written, and is quoted again below beside the rule that now replaces it.

### The three conditions, verbatim, and what each one binds

Reproduced **from the verdict file** — `docs/audit/SOCLE_S30/AUD3_adr0013_fresh_codex_verdict.md`
§ 2, lines `161`, `163`, `165` — and **not** from any dispatch prompt or paraphrase of them. **What
each binds was established by reading their own subjects**, and the evidence is given with each.
**Two of the three bind this acceptance artefact itself; one binds the future code lot.**

> 1. The operator-facing accepted text must make the Amendment 1 replacement at `docs/adr/0013-tie-handling-in-evaluation.md:976-1016` operative, so D1(b) no longer leaves `r/g` as the general nDCG rule.

**Binds: this artefact.** Its subject is *« The operator-facing **accepted** text »*. Until
2026-09-05 no such text existed and the condition was **not satisfiable**; § *The three conditions*
of the fresh-review section says exactly that at `:1205-1214`. **This section is that text**, and it
discharges the condition below under *Condition 1, made operative*. **Evidence:** the condition's
own subject noun; the cited target range `:976-1016` is § A1.7's replacement blockquote, verified to
still resolve after this edit.

> 2. The code-change lot must implement a checkable scoring-regime guard: persisted metrics must carry a `tie_policy` or equivalent regime marker, and comparison/gate code must refuse mixed pre-change/post-change regimes.

**Binds: the future code lot — step (3).** It names its own subject: *« The **code-change lot** »*.
**Evidence:** this ADR's comparability-guard section is a **proposal** and says so in its own closing
sentence — *« **No line of that is written by this ADR**, and the five items are a proposal for the
change lot, not a specification frozen by acceptance »* (`:366-367`) — and the reviewer read it the
same way, recording that the record *« proposes a `tie_policy`/comparability guard at
`docs/adr/0013-tie-handling-in-evaluation.md:342-367`, but does not freeze or implement it »*
(verdict file `:144`). **No line of guard code is written by this acceptance either.**

> 3. Any acceptance/change note must state ADR-0009 A2.11 condition 1 as discharged on 2026-08-26 under `e7e7cab`, not as a live gate, and must not introduce a replacement target for the spent D4 run.

**Binds: this artefact.** Its subject is *« Any **acceptance**/change note »* — a note attending step
(2) or step (3). When the fresh-review section was written, **no such note existed** and it recorded
the condition as binding a document that did not exist yet (`:1231-1236`). **This section is an
acceptance note**, so condition 3 now binds it, and it is discharged below under *Condition 3,
satisfied in this text*.

### Condition 1, made operative — the rule that is now in force

**The rule accepted here is § Amendment 1's generalised form, NOT D1(b)'s original `r/g`.**

**D1(b)'s original is not deleted and is not hidden.** It stands unedited in the Decision at
`:182-194`, it is quoted in A1.7 at `:959-971`, and its operative clause is quoted here so that what
was replaced is readable beside what replaced it:

> - **nDCG@k** — every position of the group carries the same expected gain `r/g` by symmetry:
>   `DCG += (r/g) × Σ 1/log2(q+1)` over `q` in `[p … min(p+g−1, k)]`. The ideal DCG denominator is
>   unchanged: it is a function of the qrels, not of the run.

**That form is correct only on binary qrels**, which is the non-Claude reviewer's first objection
(§ A1.1) and the defect § Amendment 1 was written to repair. **Collection A's qrels are graded** —
`{1, 2, 3}`, measured from the qrels file itself (`:927`) — so the general rule could not be `r/g`.

**The operative text, from this acceptance forward, is the replacement at `:976-1016`, reproduced
here verbatim so that the accepted text is self-contained:**

> **(b) What happens to a tie group.** It is **not ordered**. A group `G` of `g` documents occupying
> positions `p … p+g−1` in the ranking contributes to each measure the mean of that measure over the
> `g!` orderings of the group. Closed form, no sampling.
>
> **The two quantities a group carries, which are different objects and are named separately because
> the measures consume different ones:**
>
> - `gain(d)` is the **fourth column of the qrels row** for `(q, d)`, or **0** when the qrels carry no
>   row for it. It is read from the qrels and never assumed binary; the installed scorer applies it
>   **linearly** with the ideal truncated at the cutoff (measured, `S29_regle_egalites_mesure.md:140`).
> - `S(G) = Σ_{d ∈ G} gain(d)` — the group's **gain sum**. Consumed by nDCG@k.
> - `r(G) = |{ d ∈ G : gain(d) ≥ rel }|` — the number of group members **meeting the relevance
>   threshold**. Consumed by RR@k and R@k. As installed, `rel = 1` for both, by their own declared
>   defaults (`ir_measures/measures/rr.py:19`, `ir_measures/measures/r.py:17`), which `score_trec`
>   does not override.
>
> `S(G) ≥ r(G)`, with **equality if and only if every threshold-meeting member carries gain exactly
> 1** — i.e. on binary qrels the two coincide and everything below reduces to the binary forms.
>
> - **nDCG@k** — every position of the group carries the same expected gain `S(G)/g` by symmetry:
>   `DCG += (S(G)/g) × Σ 1/log2(j+1)` over `j` in `[p … min(p+g−1, k)]`. On binary qrels
>   `S(G)/g = r(G)/g`. The ideal DCG denominator is **unchanged**: it is a function of the qrels and
>   the cutoff, not of the run, so no tie grouping can move it; and because it is a per-query
>   constant, `E[nDCG@k] = E[DCG@k] / IDCG@k`.
> - **RR@k** — only the **first** group containing a threshold-meeting document can carry the first
>   relevant one, so the expectation collapses to that group. With `r = r(G) ≥ 1`:
>   `E[RR] = Σ_i ( C(g−1−i, r−1) / C(g, r) ) / (p+i)` for `i` in `[0 … g−r]` with `p+i ≤ k`.
>   **The threshold count, not the gain sum**: RR discards grade magnitude
>   (`ir_measures/providers/msmarco_provider.py:35` writes the literal `1`).
> - **R@k** — the same expectation, on the **threshold count**. A group entirely at or before `k`
>   contributes its actual `r(G)`; a group straddling `k` and contributing `t` positions at or before
>   `k` contributes expected count `t × r(G)/g`. The denominator — the number of the query's judged
>   documents meeting the threshold — is a function of the qrels, not of the run. Where the cutoff
>   does not fall **inside** a tie group the straddling term is a no-op, which is the case throughout
>   collection B, where every query carries exactly 100 documents and the cutoff is 100
>   (`S28_egalites_evaluateur.md` §3.4 point 3).
>
> **An unjudged document is a gain-0, non-threshold-meeting member of its group, not an excluded
> one** — `judged_only` is `False` for all three measures as installed (`rr.py:20`, `r.py:18`,
> `ndcg.py:21`) and `score_trec` does not set it, so a tie group may mix judged and unjudged documents
> and `g` counts both.

**Stated plainly, because the condition exists to prevent an ambiguity:** where the two forms
disagree, **the replacement above is the rule and D1(b)'s `r/g` is not**. The gain-weighted measure
(nDCG@k) consumes the group's **gain sum** `S(G) = Σ gain(d)`, applied as `S(G)/g`; **RR@k and R@k
consume the threshold count** `r(G) = |{ d ∈ G : gain(d) ≥ rel }|`, with `rel = 1` as installed. On
binary qrels `S(G) = r(G)` and the replacement reduces to D1(b), which is why the original is kept
readable rather than erased. **Everything else in Amendment 1 § A1.7's closing paragraph holds: no
other clause of this ADR moves** — D1(a), D1(c), D1(d), D1(e), D2(i), D2(ii), D3, D4 and every
Reserve stand exactly as written, and the straddling-group truncation of **D2(ii)** is **not**
amended.

**What making it operative does NOT do: it does not execute it.** The rule now in force is the rule
this ADR *specifies*; **the scorer does not implement it**, and it will not until the code lot of
condition 2 has been written, reviewed and run.

### Condition 2, recorded as a PRECONDITION — in the operator's own framing

The reviewer wrote condition 2 as a requirement **on** the code lot. **The operator raised it into a
gate in front of the code lot**, in his own words: *« la condition 2 posée comme PRÉCONDITION du lot
de code : rien ne bouge dans le dépôt tant que cette garde n'existe pas. »*

**So, operatively:**

1. **The code lot may not begin** until a **checkable scoring-regime guard** exists: **persisted
   metrics must carry a `tie_policy` — or an equivalent regime marker — and comparison/gate code must
   refuse mixed pre-change/post-change regimes.**
2. **NO CODE CHANGE IS AUTHORISED TO START BEFORE THAT GUARD EXISTS.** Not `run_pilot.score_trec`,
   not any of its **51** in-process call sites, not a partial or preparatory edit to either.
   *« Rien ne bouge dans le dépôt tant que cette garde n'existe pas. »*
3. **That guard does not exist today.** This ADR's § *The comparability guard* is a **proposal**
   (`:342-367`), it is **not** frozen by this acceptance, and **no line of it is written here**. What
   the guard must satisfy is condition 2's text above, quoted verbatim; **how** it is built is the
   code lot's to specify and a fresh review's to check.
4. **This acceptance therefore authorises a lot that cannot yet be started.** That is not a
   contradiction — it is what a precondition is. **The order is: guard, then the code change.**

### Condition 3, satisfied in this text

**ADR-0009 A2.11 condition 1 is DISCHARGED — discharged on 2026-08-26 under `e7e7cab` — and it is
NOT a live gate.**

**Established by command by this lot, not inherited from a document.** The commands and their output:

```
$ git log -1 --format='%H%n%cI' e7e7cab
e7e7cab3a32f15f6575140cdfd87338bf12c794a
2026-08-26T21:54:36+02:00

$ git ls-files --error-unmatch bench/runs/S21_within_c_corroboration_decision.json ; echo $?
bench/runs/S21_within_c_corroboration_decision.json
0

$ git log --oneline --diff-filter=A -- bench/runs/S21_within_c_corroboration_decision.json
e7e7cab [ariane] ADR-0009 D4 within-C corroboration on the never-scored 922: VERDICT CORROBORATES …
```

**The artefact's fields, quoted as read from the tracked file:**

| Field | Value |
|---|---|
| `computed_once` | `true` |
| `primary.n` | `922` |
| `verdict` | `CORROBORATES` |
| `positive_control.B1_cross_time_d1.arm` | `D1 (thenlper/gte-small)` |
| `positive_control.B1_cross_time_d1.computed` | `0.396385` |
| `positive_control.B1_cross_time_d1.recorded` | `0.396385` |
| `positive_control.B1_cross_time_d1.n_queries` | `150` |
| `positive_control.B1_cross_time_d1.passed` | `true` |

`computed == recorded` and `passed` is `true`: **the control passed, and the gate it guarded is
spent.** D4 is **`m = 1`**; the 922 primary was computed **once** and committed at `e7e7cab`, whose
committer date is **2026-08-26T21:54:36+02:00** — the same commit that **added** the artefact. **The
control cannot fail again, because it cannot run again.**

**NO REPLACEMENT TARGET FOR THE SPENT D4 RUN IS INTRODUCED HERE.** In those words: this acceptance
**introduces no replacement target for the spent D4 run** — no new anchor, no re-derived
`0.396385`, no substitute control, no re-run of D4 under the accepted rule, and no figure of any kind
computed under it. **This lot ran no scorer, no model, no GPU, no encode and no network call, and
opened no `.trec`.**

**The residue that survives the discharge is NOT annulled by it, and is restated rather than
softened.** A tie-rule change makes a **recorded past pass non-reproducible under a new instrument**,
and ADR-0009 **A2.5 Form B / B1 cross-time reproduction** is a **standing** clause that further runs
would use. The reviewer said the same — *« Objection 2 survives only as a comparability and future-
instrument risk, not as a live gate failure »* (verdict file `:144`) — and that residue is precisely
what condition 2's guard exists to make checkable. **ADR-0009 is not edited by this acceptance**, and
its § Amendment 3 stays `Proposed`.

### What this acceptance does NOT do — stated as plainly as what it does

1. **It does not make ADR-0012 F7 pass. F7 REMAINS MISSED.** `bench/runs/F1_decision.json` still
   carries `"status": "fail"` / `"verdict": null`, ADR-0012 § Amendment 1 stays `Proposed` and
   rejected, ADR-0012 is **not edited by this acceptance**, and **no outcome of the F7 question is
   named, ranked, recommended or hinted at here.** Nothing in this acceptance unblocks F7.
2. **It states NO fine-tuning result, in any direction.** There is none: **the arm was encoded and
   never scored.** No `.trec` of it was opened by this lot — not
   `bench/runs/anchors/F1_artifacts/B_holdout_f1_finetuned_run.trec`, not any other.
3. **IT DOES NOT MAKE THE EVALUATOR CORRECT.** This is the sentence that matters most and it is not
   softened: **the evaluator becomes correct only once the code lot has been written, reviewed and
   run.** Today the shared scorer still breaks score ties, still splits one call across two providers
   that break them in opposite directions, and still returns what D1(b)'s superseded `r/g` would
   never have described correctly on graded qrels. **An accepted specification is not a repaired
   instrument.** What acceptance produces is an **authorisation**, and that authorisation is itself
   held shut by condition 2's precondition.
4. **It changes NO code.** `bench/runners/run_pilot.py:59 score_trec` and its **51** in-process call
   sites are byte-identical to what they were before this section existed. **No number in this
   repository has moved.** Nothing under `bench/`, `security/`, `docs/research/`, `.pilot/scripts/`,
   `.pilot/STATE.md` or `docs/ROADMAP.md` is touched by it.
5. **It freezes nothing beyond the rule.** The comparability-guard proposal at `:342-367` and the
   consequential amendments named at `:371-405` are **not** frozen by acceptance; they remain
   proposals for the code lot, exactly as their own text says.
6. **It computes nothing.** Every figure in this section is read from a tracked artefact or quoted
   from a committed record, with its source.

### Both verdicts stay in the record — the REJECT included

**The first review returned `Verdict: REJECT`** (`docs/audit/SOCLE_S30/AUD3_adr0013_codex_verdict.md`,
`c33996d`). **It is not deleted, not superseded, not marked obsolete, and not edited by this
acceptance**, and neither is the § *The non-Claude review of this ADR* section that carries it.

**It was correct on the premises it was given, and one of those premises was the lab's own error.**
Its objection 2 rested in part on the ADR-0009 **A2.11 condition-1** gate being *live* and the 922
primary *un-spent* — which the lab wrote into its own dispatch prompt
(`.pilot/_prompts/S30/S30_L2_FINDER_ADR0013.md:64`) and into this ADR at `:312-316`. **The premise was
false**, as established by command above. **A false premise supplied to a reviewer is not cured by the
review, and it is not cured by a second review either** — what the first objection needed was the
corrected fact returned to a fresh review, and that is what happened. The second reviewer said so
itself, and its own words put the change no higher than it goes: *« The predecessor's `REJECT` does
not stand unchanged, but unconditional accept is still not warranted. »* **The operator's acceptance
is not unconditional, for that reason.**

**Two limits from the fresh review travel with this acceptance and are not dropped:** the reviewer's
`--selftest` **CANNOT ESTABLISH** — *« `--selftest` could not run in this sandbox because Python could
not create a temporary directory »* — is **not** softened into « the selftest passed »; and the
pre-registration ordering of the graded measurement is established at **repository level only**, so
this record may write *« ordered »* and **may not write « attested »**.

### Statements below this section that describe what an earlier lot did

§ Amendment 1, § *The non-Claude review of this ADR*, and § *The fresh non-Claude review … (S30)*
each contain sentences of the form *« `Status:` stays `Proposed` »*, *« it accepts nothing »*,
*« (2) has not been requested »* and *« Pending … (2) the operator's acceptance »*. **Every one of
them is a dated statement of what that section's own lot did, on the day it did it, and every one of
them was true then.** They are **kept exactly as written, quoted and dated, and not erased** — the
repository's convention for superseded wording. **They are superseded by this section**, which is the
operative text on the question of acceptance. **Nothing in them is edited, annotated inside a quoted
block, or renumbered by this acceptance.**
