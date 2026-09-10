# ADR-0008 — Mid-tier off-the-shelf embedder ladder vs the standing D1 (pre-registration)

**Status: Accepted**  
**Date:** 2026-06-25  
**Deciders:** Matteo (operator) — Accept gate pending  
**Proposed by:** eval-lead (S18)

## Accept (S18)

- **Operator:** Matteo · **Date:** 2026-06-25 · **Gate:** S18 Accept gate.
- **D3 decision = (a)** — reuse the B holdout with the **frozen m=3** family,
  **Holm-corrected** over the family. The pre-registration (frozen family before
  holdout contact) is the multiple-comparison mitigation; the residual non-renewable
  certification budget (D3) is accepted.
- The frozen arm family (D1), gates (D4), and encode discipline (D5) bind the
  post-Accept run-lot (`S18_LADDER_RUN`). No arm may be added/swapped without an
  amendment (a pinned model unavailable → STOP + report, never a silent substitution).

---

## Context

The lab now has its **first GPU-enabled engine path**. The encode path is cuda-capable since
`2c1c205` (S18) on the box's **RTX 3070 8 GB**, steady-state **~890 doc/sec** measured (batch 64,
warm ≈ 1070× the CPU 0.83 doc/sec floor), and the checkpointed embedding-cache (`dfda986`, S17 W5)
amortises corpus encodes across arms. For the first time, swapping the embedder for a *larger*
off-the-shelf model is cheap enough to measure rather than hypothesise — the precondition ADR-0002
("measure before engine") has been waiting on.

The standing engine is **D1 = gte-small dense-only**:

- **nDCG@10 = 0.535097** on collection **B** (GitBugs native, pooled SP.4 holdout, **CONFIRMED
  STANDING** — Holm-corrected over D1's own post-hoc {bge, gte} family, ADR-0006/0007). The pooled
  win is **spark-carried, cassandra-negative** (ADR-0007 Context: spark +0.121, cassandra −0.026).
- **nDCG@10 = 0.396385 within-C** (2nd native collection, native, `b8b86d9`, S18; MRR 0.389063,
  R@100 0.756111, n=150). D1 **GENERALIZES** — C lands ~0.139 lower than B but is **non-degenerate**
  (34 perfect + R@100 0.756): a coherent dense signal on a 2nd native collection, **not a B-only
  artifact**. C shows **ranking-depth headroom** — 43 % of queries score 0@10 while R@100 = 0.756,
  i.e. the right doc is retrieved but mis-ranked out of the top-10.

The open question, framed neutrally per R1 (the experiment is pre-registered, the **result is
unknown**):

> **Does a mid-tier off-the-shelf embedder beat D1 (gte-small dense-only) within-collection?**

This ADR follows the **define-before-experiment** discipline of ADR-0006 (fix the α×k grid before
T2 ran it) and ADR-0007 (frame the protocol, run nothing): it **pre-registers the experiment + its
gates and freezes the arm family BEFORE any holdout contact**. It **commits NO run** — the run is a
separate post-Accept lot.

### Why pre-registration is the point

D1's incumbency was earned on the B holdout; adding new arms re-uses a holdout that has already
certified a winner. An **open holdout becomes a leaderboard** — keep trying embedders until one
beats D1 by chance and the standing dies to multiple comparisons (the #1 eval-validity trap flagged
by codex). The mitigation is to **freeze the candidate family and the decision rule before looking**,
exactly as a clinical pre-registration freezes endpoints before unblinding.

### Rejected-engine precedent (this is not the lab's first off-the-shelf swap)

- **Off-the-shelf cross-encoder rerankers — m=2 rejected**: ms-marco (S11, Δ−0.105), quora (S17,
  Δ−0.345). Lesson: **task-match ≠ distribution-match** — a model trained on the right *task* can
  still lose on this *distribution*. A bigger off-the-shelf embedder is the same bet one layer up;
  the same falsifier applies.
- **Per-project routing — rejected** (ADR-0007: holdout-leakage + non-transferable project-name key).
- **Weighted-RRF — does not beat dense-only for strong embedders** (ADR-0006, Δ−0.0078 n.s.).

The base-rate from this history is **embedder/reranker swaps often do not beat D1**. That is why the
falsifier (no arm wins → D1 reinforced) is a **first-class, publishable outcome**, not a failure.

---

## Decision — what this ADR pre-registers (frozen)

### D1 — The frozen arm family (m = 3), each tested dense-only, within-collection

Every arm is evaluated **dense-only** — apples-to-apples against the incumbent. No fusion, no
reranker, no sparse arm enters this experiment (those are deferred, below).

| arm | model | role | VRAM order (inference) |
|---|---|---|---|
| incumbent | `Sentence-Transformers` gte-small (= **D1**) | reference to beat | ~0.1 GB (≈30 M params) |
| A1 | `BAAI/bge-m3` — **dense mode ONLY** | mid-tier | ~2 GB (≈0.6 B params) |
| A2 | `Qwen/Qwen3-Embedding-0.6B` | mid-tier | ~2 GB (≈0.6 B params) |
| A3 | `Alibaba-NLP/gte-Qwen2-1.5B-instruct` | mid-tier (**lineage continuity** with gte-small) | ~4 GB (≈1.5 B params) |

All three fit the **3070 8 GB** for inference (largest ≈4 GB fp16, leaving headroom for activations
+ the query batch). `bge-m3` is admitted here **in dense mode only**; its sparse + multi-vector
(ColBERT) capability is a **separate DEFERRED arm** — mixing modes inside this ladder would break the
dense-only apples-to-apples contract.

> **FREEZE (binding).** This m=3 family is **frozen by this ADR**. **No post-hoc arm may be added
> without a new ADR.** The run-lot **pins exact model revisions (commit/sha) + verifies availability
> before any encode**; if a pinned model is unavailable or its revision cannot be pinned, the run-lot
> **amends this ADR** (a recorded swap under a new revision) — **never a silent substitution**. The
> freeze is the multiple-comparison mitigation; a silent swap voids it.

### D2 — Scope

Within-collection only: **within-B** (the standing) **+ within-C** (the 2nd native, already cached).
**nDCG@10 is PRIMARY** (never swapped). **MRR@10 + R@100 secondary.** **Per-query + per-project
deltas recorded** for every arm. No cross-collection comparison is made (comparability guard:
within-collection same-class ALLOWED; cross-collection FLAGGED; cross-class REFUSED).

C's R@100 0.756-with-43 %-0@10 headroom makes it a **discriminating** within-collection test: an arm
that genuinely ranks better should convert C's retrieved-but-mis-ranked recall into top-10 gains —
an effect nDCG@10 will register where B (already high) may saturate.

### D3 — The holdout-reuse question (made explicit + recommended)

The B holdout already certified D1, so adding the m=3 arms is a **multiple-comparison risk on an
already-reported set**. Two disciplines are possible; the operator chooses at the Accept gate.

- **(a) Reuse the B holdout with the m=3 family pre-registered + Holm-corrected.** The
  pre-registration **is** the mitigation: the family is frozen (D1) before holdout contact, the
  correction is over a known m=3, and this is **cleaner than D1's own incumbency**, which was Holm'd
  over a *post-hoc* {bge, gte} family. Cheaper, preserves the full tuning split.
- **(b) Carve a fresh held-out test split** (a third partition, disjoint from tuning + the existing
  holdout). **Statistically stronger** (the arms never touch the certification set) but **costlier**
  and it **shrinks the tuning split**, weakening selection for every future lot.

**Recommendation: (a)** — reuse the B holdout with the frozen m=3 family, Holm-corrected.
**Residual stated:** the B holdout will then have informed two engine decisions (D1's incumbency +
this ladder), so its remaining certification budget is non-renewable; a *future* embedder family
beyond these three would force discipline (b) or a fresh collection. **Final pick is the operator's
at the Accept gate** — this ADR records the trade-off, it does not decide it.

### D4 — Gates for a WIN (to supersede or join D1)

An arm WINS (supersedes D1, or joins it as a co-standing) **only if all five hold**:

1. **Beats D1 within-collection** with **p < 0.05** (paired) **and a bootstrap CI excluding 0** and
   **Holm-correction over the m=3 family** (a Δ whose CI spans 0 is a TIE, never a win — eval-lead
   reporting discipline, ADR-0006 D5 / ADR-0007 C-3).
2. **Project-level deltas are a MANDATORY diagnostic.** A pooled gain that is spark-only while it
   **hurts cassandra** is **narrower specialization, not progress** (codex): the standing already
   over-indexes on spark (ADR-0007). An arm that beats D1 pooled but regresses a project must be
   reported as such; superseding on a spark-only gain is refused.
3. **Anti-leakage SP.4**: tune on the tuning split, **report once on the holdout** (or on the (b)
   fresh test split if chosen). No arm selection reads a holdout per-query value.
4. **A non-Claude (codex) AUD before any STANDING supersede (AUD-3)** — the independent
   certification that gated D1's promotion (ADR-0007 GTE_CERTIF) gates this one too. No
   Claude-only supersede of a CONFIRMED STANDING.
5. **`baseline_lock.json` integrity preserved** — byte-untouched S5→S18; this experiment adds **no**
   new lock, modifies **no** existing seal. A supersede updates the *recorded standing* (STATE),
   not the lock.

### D5 — Encode discipline (the S18 within-C anomaly is the warning)

The S18 within-C run split **GPU-system-python corpus encode vs venv-CPU query encode**
(sentence-transformers 5.3.0 vs 5.6.0) — **negligible there, unacceptable as a ladder default**: a
ladder compares arms, and a per-arm env skew is confounded with the arm. Therefore:

- **One unified torch / sentence-transformers stack** for **BOTH** corpus and query encode, **per
  arm**, pinned in the run-lot. Same library version, same device policy, same dtype path on both
  sides of every arm.
- **The cache key must disambiguate arms by `model + revision + dtype + tokenizer + pooling +
  max-len + normalization`** — **not just model name** (codex's cache-identity-drift trap: two arms
  or two revisions colliding on a name-only key silently serve each other's vectors). The existing
  cache is collection + model + revision keyed (`dfda986`); this extends the key to the full encode
  identity so a dtype/pooling/max-len change forces a re-encode rather than a stale hit.

---

## Consequences

### Positive

- **The holdout cannot become a leaderboard.** A frozen m=3 family + Holm + the explicit no-post-hoc
  rule (D1) means the worst multiple-comparison failure mode is closed before the run starts.
- **First real GPU-engine evidence, leakage-safe.** The ladder answers "is a bigger off-the-shelf
  embedder worth a bigger GPU?" on measured within-collection numbers, not on model-card claims —
  the ADR-0002 posture, now finally affordable.
- **Lineage continuity (A3).** gte-Qwen2-1.5B-instruct shares the gte family with the incumbent, so
  a win/loss there separates *scale* from *family* — a cleaner mechanistic read than a cross-family
  jump alone.
- **The falsifier is publishable.** If no arm beats D1, that **reinforces D1** as a NO-WIN result in
  the lab's own tradition (ADR-0007 option C deferred, J3.3 reranker NO-WIN) — a recorded negative,
  not wasted compute.

### Negative / trade-offs

- **Holdout certification budget spend.** Under the recommended (a), the B holdout informs a second
  engine decision; its remaining budget shrinks. Mitigated by the freeze (the spend is bounded to
  exactly m=3, pre-declared), but real.
- **The base-rate is against a win.** Every prior off-the-shelf swap (rerankers m=2, weighted-RRF)
  failed to beat D1: task-match ≠ distribution-match. The mid-tier embedders may land the same way;
  the ADR does **not** presuppose otherwise (R1).
- **8 GB is a hard ceiling.** The ladder is confined to ≤4 GB-inference arms; high-tier 4B–8B
  embedders cannot be measured on this box and are deferred behind a GPU upgrade (below). A within-
  ladder win does not establish that the *bigger* models would not win by more.
- **Two-stage commitment.** This ADR pre-registers; the operator must re-decide at the Accept gate
  (holdout discipline a vs b) and again at any supersede (AUD-3). Intentional — each stage is a
  fresh gate — but adds process.

### Deferred (gated on this ladder's evidence)

- **High-tier 4B–8B embedders** (need > 8 GB → a bigger GPU). **Gated on this ladder's evidence**: a
  GPU upgrade is justified only if the mid-tier ladder shows a real within-collection gain that
  plausibly scales. No upgrade is requested by this ADR.
- **In-domain fine-tune** of the winning (or incumbent) embedder — the lab's move #3, after
  off-the-shelf scale is measured.
- **BGE-M3 sparse / multi-vector + ColBERT** — a separate arm under its own ADR; explicitly **not**
  in this dense-only ladder.

### Falsifier / rollback

**If no arm beats D1 within-collection (gates D4.1–D4.2 unmet on B and C) → D1 is REINFORCED** and
stands unchanged; the result is recorded as a **publishable NO-WIN** (cf. ADR-0007 C, J3.3
reranker). **This ADR commits NO run** — it pre-registers the experiment, its frozen family, and its
gates; the encode + score is a **separate post-Accept lot**.

---

## Relationship to prior ADRs / conventions

- **ADR-0002 (measure-before-engine)** — direct parent. The GPU encode path makes the embedder swap
  *measurable*; this ADR refuses to adopt a bigger engine that has not been measured leakage-free.
- **ADR-0004 (corpus pivot)** — GitBugs (B) + the 2nd native (C) are the disposable pilots;
  transferable = pipeline / qrels / metrics / methodology, disposable = absolute scores. The ladder
  result transfers as *method* (does scaling the off-the-shelf embedder help within a native
  collection?), not as GitBugs numbers.
- **ADR-0006 (weighted-RRF + lower-k)** — the define-before-experiment template (fix the family
  before the run) and the precedent that fusion does not beat dense-only for strong embedders — why
  every ladder arm is tested **dense-only**.
- **ADR-0007 (per-project engine selection)** — source of D1's CONFIRMED STANDING, the
  spark-carried/cassandra-negative caveat (→ D4.2 mandatory project diagnostic), the codex
  certification precedent (→ D4.4 AUD-3), and the Proposed→Accepted gate pattern this ADR follows.
- **`CONVENTION_HOLDOUT_POLICY` (SP.4)** — binding: tune-on-tuning, report-once-on-holdout (D4.3).
  This ADR adds **no** new holdout use until Accept; D3 records the reuse-vs-fresh-split trade-off
  for the operator.
- **`baseline_lock.json`** — byte-untouched S5→S18; preserved (D4.5). No new lock anchor is created
  by this ladder.

---

## Outcome / Amendment (S20) — the D4.4 gate CLEARED → A2 supersedes D1

**The ladder produced a standing change.** Recording the outcome of the pre-registration; the ADR
body above (context, frozen family, gates, encode discipline) is **unchanged** — this section is
appended, nothing is rewritten.

- **m=3 family (closed S19):** **A1** bge-m3 NO-WIN (p 0.354) · **A2** qwen3-0.6B **WIN within-B**
  (Δ+0.041352, raw p 0.0089, Holm adj-p **0.0267<0.05**) · **A3** gte-Qwen2-1.5B NO-WIN (p 0.472);
  within-C **TIE all three**. A2 was the sole arm to clear Holm.
- **D4.4 (NO AUTO-SUPERSEDE) held twice.** At **S19** the independent non-Claude codex AUD-3 refused
  the supersede — **A2 = conditional reject** (cassandra-carried · spark point-negative · within-C
  TIE) — and set a bar of **≥1 of**: (a) a significant within-C win · (b) a **fresh independent
  holdout** · (c) a per-project floor eliminating the spark regression.
- **S20 met condition (b)** (`08f3725`): a **pre-registered replication on the fresh, disjoint
  seed-13 tuning split** of B (n=740, disjoint from the sealed n=310 holdout, higher-powered) →
  **REPLICATES** — pooled **Δ+0.035002, p 0.00046947, 95% CI [+0.015545, +0.054784], d_z 0.129**;
  positive control reproduces D1 0.535097 / A2 0.576448 to 6 dp; the S19 **spark objection resolves**
  (Δ **−0.001612**, p 0.91 = null).
- **The fresh codex AUD-3 re-adjudication returned `Verdict: SUPERSEDE`** — independent recompute
  matched exactly, **no leakage** (tuning 740/740 covered, tuning↔holdout overlap 0, 0 overlap with
  the sealed holdout), D1-sourcing judged **fair**. With **Matteo's GO**, the **D4.4 gate is CLEARED**.

> **→ A2 (`Qwen/Qwen3-Embedding-0.6B`, rev `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`, fp16,
> dense-only — mean-pool + L2, cosine KNN top-100, no fusion) SUPERSEDES D1 (`thenlper/gte-small`
> dense-only) as THE STANDING ENGINE** at within-B sealed-holdout nDCG@10 **0.576448** (n=310), vs
> D1's **0.535097**. The first standing change since S10.

**Qualified — the rider travels with the standing (A2 is NOT broadly better):**
- **cassandra-carried** — drop cassandra and the remaining 3 B projects are **Δ+0.005272, p 0.6469,
  CI [−0.017255, +0.027485]** (non-significant); cassandra alone **+0.108560** (p 2.78e-08).
- **within-C is a TIE** (0.422090 vs 0.396385, Δ+0.025705, p 0.35, CI spans 0) → **no
  corpus-transfer corroboration**. Condition (a) was never met and stays open as an opportunity.
- **Single non-Claude finder** (codex-only; the ≥1-non-Claude AUD-3 bar is met, gemini/opencode down).

**D4.5 preserved — supersede ≠ re-seal:** `baseline_lock.json` is **byte-untouched S5→S20** (last
commit `f34b74a`, S6). The lock anchors the *e5/keyword seal*; the standing engine is a **recorded
result**, never a lock entry — moving the standing creates no new lock anchor. Verdict persisted:
`docs/audit/SOCLE_S20/AUD3_A2_codex_verdict.md`. Substrate: `bench/runs/S20_a2_fresh_holdout.md`.

---

> **Coding note:** this ADR is **Proposed** and **changes no code, no run files, no indexes, no
> `baseline_lock.json`, and no `conventions/`** — the change set is this ADR file only. The frozen
> arm family (D1), the win-gates (D4), and the encode/cache disciplines (D5) are **defined here, run
> later**: no arm is encoded, no holdout is touched, no score is computed by this ADR. If accepted,
> a separate post-Accept lot pins the model revisions, verifies availability, builds the unified
> encode stack, and runs the within-B + within-C scoring under the gates above.
