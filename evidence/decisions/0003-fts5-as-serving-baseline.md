# ADR-0003 — FTS5 keyword-only as serving baseline

**Status:** accepted  
**Date:** 2026-06-20  
**Deciders:** Matteo (operator)

> **Amended by ADR-0004** (corpus pivot UCI → bug-report suite). FTS5/known-item/nDCG unchanged.

---

## Context

Ariane needs a retrieval engine that can be stood up quickly, requires no GPU,
produces deterministic results, and is auditable by the operator. The serving
baseline must support the bench evaluation loop (ADR-0002) before any advanced
retrieval algorithm is considered.

Candidate options evaluated at project inception:

| Option           | Setup cost | GPU req. | Deterministic | Auditable |
|------------------|------------|----------|---------------|-----------|
| FTS5 (SQLite)    | Very low   | No       | Yes           | Yes       |
| BM25 (Lucene)    | Medium     | No       | Yes           | Partial   |
| Dense (FAISS)    | High       | Yes      | Partial       | No        |
| Hybrid (vec0)    | High       | Yes      | Partial       | No        |

FTS5 is SQLite's built-in full-text search engine. It supports BM25-style ranking,
requires zero external dependencies beyond Python's stdlib `sqlite3`, and operates
entirely in-process. For a 24 918-document corpus of short ITSM tickets, FTS5
delivers sub-second query latency on commodity hardware.

---

## Decision

- **FTS5 is the designated serving baseline** for known-item retrieval over the
  UCI ITSM corpus (24 918 incidents).
- The `engine/` directory targets FTS5 as its first concrete implementation
  (`engine/indexer/`, `engine/retriever/`).
- **vec0 (SQLite-vec) and hybrid retrieval are CAP-frozen**: they will not be
  implemented until:
  1. FTS5 nDCG baseline scores are recorded and reproducible.
  2. The bench shows FTS5 is insufficient for the operational target.
  3. The operator explicitly lifts the freeze.
- The `engine/api/` layer abstracts the retrieval backend so future swap to
  vec0/hybrid requires only a new adapter, not a rewrite.

---

## Consequences

**Positive:**
- Zero additional dependencies for the indexer/retriever (Python stdlib `sqlite3`).
- Deterministic ranking — same query always returns the same ranked list.
- Easy to audit and debug: the index is a single `.db` file inspectable with
  standard SQLite tooling.
- Fast iteration: index rebuild over 24 918 short documents takes seconds.

**Negative / trade-offs:**
- FTS5 does not model semantic similarity; synonym and paraphrase matching
  will be limited without additional query expansion.
- If the known-item nDCG target cannot be reached with keyword retrieval alone,
  unfreezing vec0/hybrid will require additional infrastructure investment.
- BM25 parameters in FTS5 are less tunable than Lucene / Elasticsearch variants.
