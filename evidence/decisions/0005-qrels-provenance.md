# ADR-0005 — Qrels provenance: per-collection record + no cross-method absolute comparison

**Status:** accepted  
**Date:** 2026-06-21  
**Deciders:** Matteo (operator)

---

## Context

ADR-0004 fixed the measurement corpus as a **multi-collection IR suite** (A / B / C),
with **B = GitBugs** as the pilot. The collections do **not** share a relevance-judgement
method:

- **B (GitBugs)** carries **native duplicate annotations** — binary, upstream-authored,
  zero LLM-judge cost.
- **A (Zenodo 7384758 ITSM)** and **C (technical Q&A)** will receive qrels **later**,
  graded 0–3 by an **LLM-judge**.

This is therefore a **multi-method qrels suite**. The IR literature is explicit that
qrels built by different methods are distinct provenance classes: depth-k **pooling**
(TREC), **LLM-judge** grading (UMBRELA-style), and **native/linked** annotations are not
interchangeable, and LLM-judge qrels — while correlating well with human run-level
effectiveness — are a separate class that can be gamed if the process is public. Comparing
a raw NDCG computed against B's binary native qrels with one computed against A's
LLM-judge graded qrels would produce a **false cross-collection ranking**.

No provenance record exists today: `corpus/schemas/` is empty and the manifest format
(G7 / `CORPUS_MANIFEST.json`) is declared but not yet built. The ADR-0005 slot is free.
This decision is sourced from B_RES1 §4 (`docs/audit/SOCLE_S2/raw/B_RES1_output.md`).

---

## Decision

- **Each collection's qrels carries a provenance record.** Stored as a sidecar
  `corpus/qrels/<id>_provenance.json`, referenced from the collection's manifest entry via
  `qrels_provenance_ref` (G7).
- **Mandatory field set** (one record per collection):
  - `method ∈ {native_links, pooled, llm_judge, hybrid}`
  - `method_detail`
  - `grade_scale` (e.g. `binary`, `graded_0_3`)
  - `pool_depth` (when `pooled` / `hybrid`)
  - `judge { model, version, prompt_version }` (when `llm_judge` / `hybrid`)
  - `annotator` (when human)
  - `qrels_version`
  - `construction_date`
  - **`comparability_class`** (e.g. `native`, `pooled`, `llm_judge`)
- **No cross-method absolute comparison.** Qrels of different `comparability_class` are
  **never** compared by absolute score. Cross-collection statements are made only on
  **deltas within a single collection** or on **methodology** — never on raw NDCG between
  A (`llm_judge`) and B (`native`).
- **Pilot B (GitBugs):** `method = native_links`, `grade_scale = binary`,
  `comparability_class = native`, `judge = null` (zero LLM-judge cost — ADR-0004).
- **A / C (later):** `method = llm_judge`, `grade_scale = graded_0_3`,
  `comparability_class = llm_judge`, with `judge { model, version, prompt_version }` and
  `pool_depth` recorded; `hybrid` (human top-k + LLM deeper) is an allowed budget pattern.

---

## Consequences

**Positive:**
- Protects ADR-0004's multi-collection suite from a **false cross-collection ranking** by
  making `comparability_class` an explicit, machine-checkable field.
- Makes the GitBugs-native vs A/C-LLM-judge heterogeneity a recorded fact, not an implicit
  assumption — the regression gate (G9) keys baselines per `collection_id` accordingly.
- A/C onboarding becomes an integration task: fill the provenance record, don't redesign
  the comparison rules.

**Negative / trade-offs:**
- Adds a required artefact (the provenance sidecar) per collection before its qrels are
  usable in the bench.
- The "no absolute cross-collection comparison" rule means the suite reports per-collection
  results plus within-collection deltas, not a single headline number across A/B/C.

---

## Relationship to prior ADRs / gaps

- **ADR-0004 (corpus pivot)** — this ADR operationalises the multi-method qrels situation
  ADR-0004 created (B native vs A/C LLM-judge).
- **Gap G12** (`docs/audit/SOCLE_S2/BENCH_FOUNDATIONS.md`) is closed by this ADR; the
  provenance record is referenced from the G7 `CORPUS_MANIFEST.json` via `qrels_provenance_ref`.

---

> `[UNVERIFIED]`: the LLM-judge process for A/C (and its `prompt_version` scheme) is the
> deferred gap **G8** — to be spec'd when A/C land. This ADR fixes the *provenance record
> contract*, not the judge implementation.
