# ADR-0006 — Weighted-RRF α-grid + lower-k extension {1, 2, 5} on the hybrid arm

**Status:** Accepted  
**Date:** 2026-06-23  
**Deciders:** Matteo (operator)  
**Proposed by:** retrieval-engineer + eval-lead (S9)

---

## Context

Two connected signals from J3.1 (S7) and J3.2 (S8) together motivate both the weighted-RRF
parameter and a finer/lower-k extension. They are treated in one ADR (operator decision, S9:
more convention churn avoided by folding them).

### Signal 1 — Dense-only beats hybrid for both J3.2 models (J3.2, S8)

On the SP.4 holdout (n=310, cluster-disjoint, project-stratified, seed 13):

| model | dense-only nDCG@10 | hybrid@k10 nDCG@10 |
|-------|--------------------|--------------------|
| bge-small-en-v1.5 | 0.517659 | 0.509686 |
| gte-small | **0.535097** | 0.513906 |

For **both** models, the dense-only arm beats its own hybrid arm at the best-k from the J3.0
grid. The magnitude of the gap (bge: −0.008; gte: −0.021) exceeds noise. Mechanism:
**unweighted RRF assigns equal weight (0.5 / 0.5) to the dense arm and the keyword arm; when
the dense arm is strong and the keyword arm weaker, the fusion dilutes the dense signal rather
than amplifying it.**

### Signal 2 — SP.7 dilution pattern: every J3.1 holdout loss is RRF dilution (J3.1, S7)

SP.7 seed analysis on the J3.1 holdout (79 wins / 202 ties / 29 losses, 9.4% loss rate):
every one of the 29 losses is the **RRF-dilution pattern** — the keyword arm ranks the
duplicate well, the dense arm ranks it worse, and unweighted RRF dilutes a good lexical hit.
Rank-1 in 15/29 cases. **No dense false-positive found.** This is the symmetric case to
Signal 1: when the keyword arm is the stronger arm, unweighted RRF again dilutes it.

Both signals share the same root cause: **a fixed 0.5/0.5 fusion weight is a poor fit when
one arm consistently outperforms the other**. Weighted-RRF (per-arm α) is the minimal fix
that subsumes the current unweighted configuration as a special case (α = 0.5).

### Signal 3 — k = 10 is the grid floor (J3.1, S7)

J3.1 swept the J3.0-fixed grid **k ∈ {10, 20, 40, 60, 80, 100}** on the tuning split. The
sweep was monotone-decreasing in nDCG@10 (k10 = 0.505889 → k100 = 0.491731), so **k = 10 was
selected** — but it is the floor of the grid, not an interior optimum. The true RRF-k minimum
may lie below 10. The ablation convention forbids post-hoc grid expansion, so a lower-k probe
requires a new ADR.

### Standing numbers for reference

- **e5-hybrid@k10** (J3.1, confirmed standing, lock-anchored): holdout nDCG@10 = **0.477218**
  (Δ +0.071626 vs keyword 0.405592; p=1.76e-07; d_z=0.304; bootstrap 95% CI [0.044, 0.098]).
- gte-dense = **0.535097** — best absolute score in the lab but J3.2 is exploratory/uncorrected
  (2 models on the same holdout → p-values not Bonferroni-corrected); treat as hypothesis, not
  confirmed. The **J3.1 e5 result remains the confirmed standing number**.

---

## Decision

### D1 — Weighted-RRF parametrisation

Adopt the **single-parameter form**: α = dense arm weight, (1−α) = keyword arm weight.

**Fixed α grid: α ∈ {0, 0.25, 0.5, 0.6, 0.75, 1.0}** (6 values).

Rationale for each boundary / interior point:
- **α = 0** → keyword-only fusion (degenerate, included as sanity check).
- **α = 0.5** → **reproduces the current unweighted RRF** (equal weights). This is the
  standing baseline from J3.1; its inclusion in the grid means any weighted gain is measured
  against the current configuration, not against an uncontrolled reference.
- **α = 0.6** → added (beyond the prompt suggestion of {0, 0.25, 0.5, 0.75, 1.0}) to sample
  the empirically motivated dense-leaning region more finely. J3.2 evidence shows both models'
  dense arms outperform their hybrid arms; the hypothesis is that the optimum lies in the
  moderate-dense-lean zone (0.5 < α ≤ 0.75) rather than at a hard corner. One extra grid
  point here is cheap (re-fusion of cached rank lists, no re-encoding) and reduces the risk of
  a coarse grid mis-selecting the corner (α = 0.75) when the real peak is at ~0.65.
- **α = 1.0** → dense-only fusion (degenerate; included to confirm that weighted-RRF at α = 1
  reproduces the dense-only arm — a consistency check).

### D2 — Lower-k extension

**Extended k grid: k ∈ {1, 2, 5, 10, 20, 40, 60, 80, 100}** (9 values).

The lower values {1, 2, 5} are added below the current floor of 10. The existing upper half
{10, 20, 40, 60, 80, 100} is preserved unchanged so that J3.1-confirmed cells remain
comparable. RRF with small k strongly up-weights the top-ranked document in each arm; k = 1
is an extreme (winner-takes-most); k = 2 and k = 5 sample the interpolation between k = 1
and the confirmed k = 10.

### D3 — Sweep structure: joint α × k product grid

The α and k sweeps are run **jointly** as a full product grid: **6 × 9 = 54 cells** (the full
α grid × the full k grid). All 54 cells are pure re-fusions of existing cached rank lists — no
re-encoding, no index rebuild — so the marginal cost per cell is negligible.

Justification for joint over sequential:
- All 54 cells are pure re-fusions of **existing cached rank lists** (no re-encoding, no
  index rebuild). The marginal cost per cell is negligible.
- α and k interact: a dense-leaning α may change the optimal k (the dilution mechanism that
  motivates lower-k is partly relieved by re-weighting the dense arm). Sequential sweeping
  (lower-k first at α = 0.5, then α at best-k) risks selecting a k that is locally optimal
  under equal weights but sub-optimal under the best α. The joint grid avoids this coupling
  artefact.
- A sequential sweep would require two committed ablation passes and a second re-fixing step
  to record the intermediate winner; the joint approach is single-pass and cleaner under the
  define-before-experiment convention.

### D4 — Arm of first application: e5

The first weighted-RRF sweep targets the **e5-small-v2** arm — the confirmed, lock-anchored
standing dense arm (J3.1). Reasons:

- **Lock-anchored**: the reproduce-the-seal positive-control runs on e5 rank lists; any
  deviation is immediately detectable. A first sweep on bge or gte would require the positive
  control to be adapted (or a second lock anchor added), adding complexity.
- **Confirmed standing**: e5-hybrid@k10 is the only holdout result with a corrected p-value
  (uncorrected for multiple models); it is the fair reference for measuring weighted-RRF gain.
- **Index availability**: e5 vec0 indexes are already built, repaired at S7, and verified
  reproducible to 6 dp. gte would require a ~3.6 h cold rebuild; bge ~76 min. No new encoding
  is needed for a re-fusion sweep.

**bge and gte follow-up** is an explicit next step but is NOT in scope for this ADR's first
sweep.

### D5 — Reporting rule (eval-lead)

Every weighted-RRF sweep result MUST report:
1. **Holdout nDCG@10** for the selected (α, k) variant — PRIMARY, never swapped.
2. **Dense-only arm alongside** (α = 1.0 cell or the separately run dense-only baseline) so
   that the question "does the fused result beat dense-only?" is always answered.
3. Tuning-split selection is on nDCG@10; the holdout is reported-on-once for the selected
   variant (SP.4 policy unchanged).
4. The **reproduce-the-seal positive-control** (re-fuse e5 cached arms at the sealed k = 10
   with α = 0.5 → must match `bench/runs/J1_3_perquery.jsonl` to 6 dp) precedes any real-B
   run.

### D6 — Convention re-fixing

`conventions/CONVENTION_ABLATION_PROTOCOL.md` §2 and §3 are updated in the same commit as
this ADR to record the weighted-hybrid arm and the fixed grids (D1, D2) as per the
define-before-experiment protocol. The S8 NOTE block and the "optional/future/not-coded"
framing are replaced with the fixed grids and this ADR reference.

---

## Consequences

### Positive

- **Addresses both dilution directions** observed empirically (dense > hybrid in J3.2;
  keyword > hybrid in J3.1 SP.7 losses) with a single, minimal parametric extension.
- **Unweighted RRF is a grid point** (α = 0.5), not the implicit floor — the weighted gain is
  always measured against the current standing configuration, not against an uncontrolled
  reference.
- **No new encoding or index build** for the e5 sweep — all 54 cells are pure re-fusions of
  cached rank lists. The cost is small compared with any embedding variant (J3.2 ~8 h cold).
- **Convention churn bounded to one ADR**: folding weighted-RRF + lower-k into a single ADR
  (operator decision, S9) avoids two separate convention re-fixings and two separate
  define-before-experiment passes.
- **Joint grid eliminates α–k coupling risk** that would arise from a sequential two-pass
  sweep.

### Negative / trade-offs

- **54-cell sweep adds reporting surface** — more cells to tabulate, more risk of
  cherry-picking visual. Mitigated by: (a) the selection rule is nDCG@10 on the tuning
  split, committed in advance; (b) the holdout is reported-on-once for the single selected
  (α, k).
- **Reading too much into J3.2 gte/bge evidence**: the dense-dominant finding is compelling
  but J3.2 is exploratory/uncorrected (2 models, same holdout, uncorrected p). Weighted-RRF
  on e5 is motivated but the direction of the optimum is an **empirical question** — there is
  no guarantee the best α is in the dense-lean zone. The sweep will answer it; the ADR does
  not pre-suppose the answer.
- **Lower-k values {1, 2} are aggressive** (strong rank-1 up-weighting) and may hurt on
  queries where the dense arm's rank-1 is wrong. Included because the grid-floor signal (J3.1
  k=10) justifies probing below 10; the selection rule will discard them if they under-perform.
- **e5-first means bge/gte weighted-RRF gains are not yet measured.** gte dense is the best
  absolute score in the lab (0.535); the question of whether gte weighted-hybrid beats gte
  dense is deferred. This is intentional: confirming the method on the lock-anchored arm
  first reduces risk of building on an uncorrected exploratory result.

---

## Rejected alternatives

### (a) No-ADR shortcut — silently sweep α and lower-k in T2

Rejected. Violates the **J3.0 define-before-experiment** rule: the ablation convention
explicitly prohibits post-hoc grid expansion. Running a sweep whose parameter values were
chosen after seeing J3.2 results — even if not formally "post-hoc" on the final holdout —
would be indistinguishable from p-hacking to reviewers. The ADR + convention re-fix makes the
grid commitment auditable.

### (b) Raw-score linear fusion instead of weighted-RRF

Rejected. Linear fusion of BM25 scores and cosine-similarity scores is **score-scale
sensitive**: BM25 scores are corpus-dependent (tf-idf weighting, document frequency
normalization), while cosine similarities are bounded [−1, 1] but affected by the embedding
model's geometry. The two score distributions are not commensurable across collections or
model changes. RRF operates on **rank positions** only — it is scale-agnostic and
corpus-agnostic, which is why the original RRF paper and subsequent IR literature use it for
heterogeneous retriever fusion. Weighted-RRF preserves this property (ranks only, no score
normalization needed).

### (c) Two separate ADRs: one for lower-k, one for weighted-RRF

Rejected. Both changes target the same parameter sweep over the same hybrid arm, and both are
motivated by the same empirical mechanism (RRF dilution). Two ADRs would produce two
convention re-fixings of `CONVENTION_ABLATION_PROTOCOL.md` §3 within the same session,
creating intermediate states where the lower-k grid is fixed but the α grid is not (or
vice-versa). The operator decided at S9 to fold them into one ADR to minimize convention
churn.

### (d) gte arm first (highest absolute score)

Rejected. gte dense is the best absolute score in the lab (0.535097), but the J3.2 result is
**exploratory/uncorrected** (2 models on the same holdout → uncorrected p-values; treat as
hypothesis). Building the first weighted-RRF sweep on gte would mean:
1. A ~3.6 h cold gte index rebuild is required before any re-fusion sweep.
2. The reproduce-the-seal positive-control (which verifies against the J3.1 e5 lock) does not
   apply directly to gte rank lists — a second positive-control anchor would be needed.
3. Any gain claim would rest on an uncorrected exploratory finding, not on the confirmed
   standing number. Risking operator trust in the methodology for a marginal time saving is
   not worthwhile. e5 first is the conservative, reproducibility-anchored choice.

---

## Relationship to prior ADRs / conventions

- **ADR-0001 (local-first)** — no conflict; all sweeps run locally.
- **ADR-0002 (measure-before-engine)** — this ADR is exactly that: the measurement bench
  gates the weighted-RRF parameter decision before any code lands.
- **ADR-0004 (corpus pivot)** — the pilot collection B (GitBugs) is unchanged; this ADR
  fixes the search-side fusion parameter only.
- **ADR-0005 (qrels provenance)** — no interaction; provenance records are collection-side,
  not engine-side.
- **J3.0 ablation protocol** (`CONVENTION_ABLATION_PROTOCOL.md`) — this ADR re-fixes §2 and
  §3 of that convention to add the weighted-hybrid arm and replace the "optional/future/not-
  coded" framing with the fixed grids. The no-post-hoc-expansion rule remains in force: the
  grids fixed here (D1, D2) are the only values that may be swept in T2.
- **J3.1** (S7, commit `0b680b0`) — source of the SP.7 dilution evidence and the k=10 floor
  signal. The standing e5-hybrid@k10 number (0.477218) is the reference against which any
  weighted-RRF gain will be measured.
- **J3.2** (S8, commits `88ca4ff` + `1c705f7`) — source of the dense>hybrid finding for bge
  and gte. Motivates the dense-leaning α region but is exploratory/uncorrected; does not
  replace the confirmed J3.1 standing number.
- **`CONVENTION_HOLDOUT_POLICY`** (SP.4) — the SP.4 split (cluster-disjoint, project-
  stratified, seed 13, 70/30 → tuning 740 / holdout 310) is unchanged. The weighted-RRF
  sweep selects on the tuning split and reports on the holdout exactly once for the selected
  (α, k) variant.

---

> **Coding note:** weighted-RRF is **defined here, built at T2**. No implementation exists
> in `bench/runners/compare.py` as of this ADR. T2 will add the α parameter to the fusion
> step; no existing run files, indexes, or lock artifacts are modified by this ADR.
