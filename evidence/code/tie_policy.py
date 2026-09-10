#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tie_policy — the SCORING-REGIME guard (ADR-0013 acceptance precondition, S31).

**What this module is.** The repository already refuses one class of incommensurable
comparison in code: ``transfer_eval.ComparabilityError`` raises on an absolute
``llm_judge`` x ``native`` compare (``transfer_eval.py:73``, raised at ``:139``, ``:158``,
``:222``). **There was no equivalent for a comparison across SCORING REGIMES.** This module
is that equivalent, and it is the object ADR-0013's acceptance made a **precondition** of the
code lot: *« persisted metrics must carry a ``tie_policy`` or equivalent regime marker, and
comparison/gate code must refuse mixed pre-change/post-change regimes »*
(``docs/audit/SOCLE_S30/AUD3_adr0013_fresh_codex_verdict.md:163``).

**What this module is NOT.** It does not change how ties are scored. ADR-0013's rule change —
``score_trec`` ceasing to break ties, each measure becoming the expectation over the uniform
distribution of orders within a tie group — is a **later, separate lot**, and nothing here
starts it. Every metric value this repository produces is the same after this module exists as
it was before. The marker's **first** recorded value names the **current, pre-change** regime,
which is the whole reason the marker must exist before the change: once the change lands,
every number already on disk is identifiable as belonging to the old instrument.

**The marker's shape** is ``<policy-name>/v<N>``.

**The current regime's name is derived from what the scorer actually does today**, not from
ADR-0013's proposed post-change name. ``run_pilot.score_trec`` (``run_pilot.py:59``) asks
``ir_measures.calc_aggregate`` for ``[nDCG@10, RR@10, R@100]`` in one call and **implements no
tie rule of its own**: tie handling is entirely whatever the installed ``ir_measures`` provider
dispatch does. That dispatch is a ``FallbackEvaluator`` splitting the call across
``PytrecEvalEvaluator`` (nDCG@10, R@100 — ``doc_id`` **descending**) and ``MsMarcoEvaluator``
(RR@10 — ``doc_id`` **ascending**), so the regime is *provider-delegated, doc_id-lexicographic
and internally split* (ADR-0013 § C1). ``ir-measures-provider-tiebreak/v1`` names exactly that
and claims no single direction, because there is none.

**The absent ≡ pre-regime rule.** A persisted record with **no** ``tie_policy`` field is a
*pre-regime* record — a **different value** from a future post-change marker, **never a missing
one**. Today the pre-regime marker and the current marker are the **same string**
(:data:`PRE_REGIME_POLICY` == :data:`CURRENT_TIE_POLICY`), so an unmarked record and a freshly
stamped one compare **without raising**. That is load-bearing rather than lax: every anchor
comparison in this repository puts a recorded value beside a fresh computation — ADR-0009's B1
cross-time reproduction is exactly that shape — and a guard that raised on it would break every
one of them on the day it landed. The two constants **diverge** the moment the tie rule changes:
:data:`CURRENT_TIE_POLICY` moves to the new string, :data:`PRE_REGIME_POLICY` does not, and from
that moment an unmarked record and a fresh one raise.

**The writer is policed, not the reader (S31 L7).** The first version of this guard asked every
recorder to remember the marker, and an independent non-Claude review
(``docs/audit/SOCLE_S31/AUD3_regime_guard_codex_verdict.md``, verdict ``DOES-NOT-SATISFY``)
established that two of them do not: ``run_methods._strip`` and ``transfer_eval``'s persisted
``metrics`` object both re-key a scorer output and drop the field. So *« absent means legacy
pre-regime »* was a **hope** about the repository, not a statement about it. The repair is
structural: :func:`metrics_view` is the one way to build a compact metrics record and it
**cannot** produce one without the marker, :func:`write_run_record` is the one door a whole JSON
record goes through and it **raises** on an unmarked metric, and
:func:`enumerate_metric_records` is the executable enumeration that pins both — so a recorder
added next year fails the suite instead of silently dropping the regime.

Stdlib only, no dependency on any other bench module — so any recorder or gate can import it by
path without dragging in the scorer. It writes files (:func:`write_run_record`) and reads Python
sources (:func:`enumerate_metric_records`); it never reads or writes a metric of its own.
"""
from __future__ import annotations

import ast
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

# ── The two constants, and the whole design is in their relationship ─────────────
#: What a persisted record with NO ``tie_policy`` field was produced under. This value is
#: FROZEN: it names the regime every unmarked number on disk belongs to, and it must not be
#: edited when the tie rule changes.
PRE_REGIME_POLICY = "ir-measures-provider-tiebreak/v1"

#: What ``run_pilot.score_trec`` implements TODAY. Equal to :data:`PRE_REGIME_POLICY` because
#: the tie rule has not changed — ADR-0013 step (3) has not happened. **When it happens, this
#: constant (and only this one) moves** to the new regime's name, e.g.
#: ``expected-over-tie-groups/v1``; the guard below then raises on every pre-regime × post-change
#: pair with no further code change.
CURRENT_TIE_POLICY = PRE_REGIME_POLICY

#: The field name a recorder writes beside its metrics.
TIE_POLICY_FIELD = "tie_policy"

#: The regime of a number a diagnostic computed with its **own** ranking/tie implementation
#: instead of asking ``run_pilot.score_trec``. It is deliberately **different** from
#: :data:`CURRENT_TIE_POLICY`: such a number was produced by a different instrument, and the
#: guard SHOULD refuse to compare it with an ``ir_measures`` number. Stamping those records with
#: :data:`CURRENT_TIE_POLICY` would have been a false label — the marker names an instrument, and
#: "add the marker everywhere" is not the same instruction as "add the *same* marker everywhere".
LOCAL_REIMPL_POLICY = "diagnostic-local-reimplementation/unversioned"

#: The aggregate field names that make a mapping a **metrics record**. A mapping carrying
#: :data:`METRIC_QUORUM` or more of them must state the regime it was produced under.
METRIC_FIELDS = frozenset({
    "ndcg@10", "ndcg@100", "ndcg", "mrr", "mrr@10", "rr@10", "recall@10", "recall@100",
    "recall@1000", "r@100", "map", "n_queries", "per_query", "per_query_ndcg10", "p_value",
})

#: The subset of :data:`METRIC_FIELDS` that names a **measured score** — a number an evaluation
#: instrument produced. **One of these is already a measurement**, so a mapping carrying a single
#: one IS a metrics record: there is no reading of ``{"ndcg@10": 0.58}`` under which the number is
#: not a score. This is the S31 L9 closure of the reviewer's *« it explicitly misses exactly-one-
#: field records »* (AUD3 re-adjudication, *Read Evidence* 2).
SCORE_FIELDS = frozenset({
    "ndcg@10", "ndcg@100", "ndcg", "mrr", "mrr@10", "rr@10", "recall@10", "recall@100",
    "recall@1000", "r@100", "map",
})

#: The rest of :data:`METRIC_FIELDS`: fields that are *about* a measurement without being one —
#: a count (``n_queries``), a payload (``per_query``, ``per_query_ndcg10``) or a statistic
#: (``p_value``). **These, and only these, still need a second field**, because each of them
#: alone genuinely occurs on ordinary records. That is measured, not assumed: at quorum 1 over
#: all of :data:`METRIC_FIELDS`, ``bench/runners`` yields 12 one-field sites, and the 7 that are
#: NOT metrics records are exactly the ones whose lone field is a context field — ``n_queries``
#: in a corpus manifest (``llm_judge_qrels.py:251``), in a reproduction check
#: (``s21_corroboration_run.py:238``, ``:240``, ``:408``) and in a determinism probe
#: (``s21_encode_determinism_probe.py:157``), ``per_query`` in a timing block
#: (``rerank_eval.py:257``, ``:486``). The 5 that ARE metrics records all carry a score field.
CONTEXT_FIELDS = METRIC_FIELDS - SCORE_FIELDS

#: How many :data:`CONTEXT_FIELDS` make a mapping a metrics record when it carries **no** score
#: field. **Two, not one**, for the reason measured above.
METRIC_QUORUM = 2


def record_fields(keys) -> frozenset:
    """The metric fields that make ``keys`` a metrics record — empty when it is not one.

    One rule, used by both the runtime check (:func:`is_metrics_mapping`) and the static one
    (:func:`enumerate_metric_records`), so the two cannot drift apart: **one score field, or two
    metric fields of any kind.**
    """
    keys = {str(k).lower() for k in keys}
    matched = keys & METRIC_FIELDS
    if (keys & SCORE_FIELDS) or len(matched) >= METRIC_QUORUM:
        return frozenset(matched)
    return frozenset()


class UnmarkedMetricError(RuntimeError):
    """Raised when a metrics record is about to be PERSISTED without a regime marker.

    Distinct from :class:`ScoringRegimeError`, and deliberately not a subclass of it: that one
    refuses a *comparison* between two known regimes, this one refuses a *write* whose regime
    is unstated. A caller catching one must not silently catch the other.
    """


class UnstatedRegimeError(RuntimeError):
    """Raised when a reader is asked to resolve the regime of a record that states none.

    The third refusal, and deliberately a sibling of the other two rather than a subclass:
    :class:`UnmarkedMetricError` refuses a **write**, :class:`ScoringRegimeError` refuses a
    **comparison between two known regimes**, and this one refuses a **read** whose regime is
    unstated. Before S31 L9 that read did not refuse — it resolved silently to
    :data:`PRE_REGIME_POLICY`, and the independent reviewer demonstrated the consequence:
    *« I could still make an unmarked metric object serialize via plain JSON, and ``regime_of()``
    would classify it as pre-regime »*. "Absent means legacy" is now a statement the **caller**
    makes about the record it is reading (``legacy_ok=True``), not an assumption the resolver
    makes on its behalf.
    """


class ScoringRegimeError(RuntimeError):
    """Raised when two numbers produced under DIFFERENT scoring regimes are compared.

    Modelled on ``transfer_eval.ComparabilityError`` and raised for the same reason: two
    numbers whose instrument differs are not commensurable, so the harness refuses to
    subtract, test or gate on them rather than silently emitting a misleading delta.
    """


def regime_of(x: Any, *, legacy_ok: bool = False) -> str:
    """Normalise a guard argument into the scoring regime that produced it.

    **``legacy_ok`` is the caller's statement that an absent marker here means a pre-marker
    artefact** — a record written before the guard existed. Without it, an absent marker is
    :class:`UnstatedRegimeError`, **not** :data:`PRE_REGIME_POLICY`. The rule *« absent can only
    mean legacy »* was refused by the independent reviewer as too broad precisely because this
    function applied it to every mapping it was handed, including one a new recorder had just
    written and forgotten to mark. It is now opted into, per call site, where it is true.

    Accepts:

    * ``None`` — an **absent** marker → :data:`PRE_REGIME_POLICY` when ``legacy_ok``, else raise;
    * a ``str`` — the marker itself, returned as-is;
    * a ``Mapping`` — a metrics- / record-shaped object; its ``tie_policy`` field is read, and
      if the mapping carries none, a single nested ``metrics`` mapping is consulted (so a
      ``compare.py`` arm ``{"method": ..., "metrics": {...}}`` can be passed whole). A mapping
      with no marker anywhere is **absent** — pre-regime when ``legacy_ok``, else a raise.

    Unlike ``transfer_eval._comparand``, a bare string **is** accepted: a scoring regime is
    fully identified by its marker, whereas a comparability class alone could not tell a
    within-collection bake-off from a cross-collection comparison.

    Raises ``ValueError`` on a present-but-blank marker (a malformed record — that is not the
    same thing as an absent one) and ``TypeError`` on any other type.
    """
    if x is None:
        return _absent(legacy_ok)
    if isinstance(x, str):
        if not x.strip():
            raise ValueError(
                "tie_policy is present but blank — a malformed regime marker. An ABSENT "
                f"marker means pre-regime ('{PRE_REGIME_POLICY}'); an empty string means "
                "a recorder wrote a broken one."
            )
        return x.strip()
    if isinstance(x, Mapping):
        marker = x.get(TIE_POLICY_FIELD)
        if marker is None:
            nested = x.get("metrics")
            if isinstance(nested, Mapping):
                marker = nested.get(TIE_POLICY_FIELD)
        return regime_of(marker, legacy_ok=legacy_ok)
    raise TypeError(
        "assert_same_regime/regime_of expect None (absent marker), a policy string, or a "
        f"metrics-shaped mapping carrying '{TIE_POLICY_FIELD}'. Got {type(x).__name__}."
    )


def _absent(legacy_ok: bool) -> str:
    """What an ABSENT marker resolves to — or the refusal when no caller has claimed it."""
    if legacy_ok:
        return PRE_REGIME_POLICY
    raise UnstatedRegimeError(
        f"REFUSED to resolve the scoring regime of a record carrying no "
        f"'{TIE_POLICY_FIELD}'. An absent marker is only a PRE-REGIME record "
        f"('{PRE_REGIME_POLICY}') when the CALLER says it is reading a pre-marker artefact: "
        f"pass legacy_ok=True (regime_of / is_pre_regime) or the matching *_is_legacy flag "
        f"(compare.sp3_stat, eval_regression.is_regression) at a site that legitimately reads "
        f"one. It is refused by default because a NEW record that forgot the marker is "
        f"indistinguishable from a legacy one to this function, and resolving it silently is "
        f"exactly the bypass the S31 AUD-3 re-adjudication demonstrated. To write a record, "
        f"use tie_policy.metrics_view() or tie_policy.stamp()."
    )


def is_pre_regime(x: Any, *, legacy_ok: bool = False) -> bool:
    """True iff ``x`` resolves to the pre-change regime. ``legacy_ok`` as in :func:`regime_of`."""
    return regime_of(x, legacy_ok=legacy_ok) == PRE_REGIME_POLICY


def assert_same_regime(a: Any, b: Any, *, context: str | None = None,
                       a_legacy_ok: bool = False, b_legacy_ok: bool = False) -> dict:
    """Decide whether two numbers may be compared, and REFUSE across scoring regimes.

    ``a`` and ``b`` are each a marker (``None`` / ``str``) or a metrics-shaped mapping; see
    :func:`regime_of`. The rule is one line: **equal regimes compare, different regimes raise**.
    ``a_legacy_ok`` / ``b_legacy_ok`` are **per side**, because the two sides are not
    symmetrical in practice: a gate reads a locked baseline written years ago (legacy is true of
    it) beside a number computed seconds ago (legacy is false of it, and an absent marker there
    is a defect, not a legacy record). An absent marker on a side that did not declare itself
    legacy raises :class:`UnstatedRegimeError`. With the declaration:

    * absent × absent → ALLOW (two records of the old instrument);
    * absent × :data:`CURRENT_TIE_POLICY` → **ALLOW today** (they are the same regime) and
      **REFUSE** once the tie rule has changed — the same code, no edit;
    * current × current → ALLOW;
    * pre-regime × post-change → **REFUSE** (:class:`ScoringRegimeError`).

    Returns a verdict dict ``{comparable, tie_policy, regimes, absent_resolved, context}`` — the
    shape ``transfer_eval.assert_absolute_comparable`` returns, so a caller may record which
    regime a comparison was made under instead of merely not crashing.
    """
    ra = regime_of(a, legacy_ok=a_legacy_ok)
    rb = regime_of(b, legacy_ok=b_legacy_ok)
    if ra != rb:
        where = f" [{context}]" if context else ""
        raise ScoringRegimeError(
            f"REFUSED comparison across scoring regimes{where}: '{ra}' vs '{rb}'. These two "
            f"numbers were produced by DIFFERENT evaluation instruments (ADR-0013 tie "
            f"handling) and their delta, paired statistic or gate verdict is meaningless. A "
            f"record carrying no '{TIE_POLICY_FIELD}' field is the PRE-REGIME value "
            f"'{PRE_REGIME_POLICY}', never a missing one. Requalify the older number under "
            f"the installed instrument, or report each side standalone with its regime named."
        )
    return {
        "comparable": True,
        "tie_policy": ra,
        "regimes": [ra, rb],
        "absent_resolved": [_explicit(a) is None, _explicit(b) is None],
        "context": context,
    }


def _explicit(x: Any) -> str | None:
    """The marker a record carries EXPLICITLY (``None`` when it carries none)."""
    if x is None:
        return None
    if isinstance(x, str):
        return x.strip() or None
    if isinstance(x, Mapping):
        marker = x.get(TIE_POLICY_FIELD)
        if marker is None:
            nested = x.get("metrics")
            if isinstance(nested, Mapping):
                marker = nested.get(TIE_POLICY_FIELD)
        return _explicit(marker)
    return None


def stamp(record: dict, policy: str | None = None) -> dict:
    """Write the regime marker into ``record`` **in place** and return it.

    The one call every recorder makes. Defaults to :data:`CURRENT_TIE_POLICY` — a recorder
    stamps what the installed instrument is, never a value of its own choosing.
    """
    record[TIE_POLICY_FIELD] = policy or CURRENT_TIE_POLICY
    return record


# ── Policing the WRITER: the marker cannot be forgotten, because it cannot be omitted ────

def is_metrics_mapping(m: Any) -> bool:
    """True iff ``m`` is a mapping :func:`record_fields` calls a metrics record."""
    if not isinstance(m, Mapping):
        return False
    return bool(record_fields(m.keys()))


def unmarked_metric_paths(payload: Any, *, _at: str = "", _in_scope: bool = False) -> list[str]:
    """Dotted paths of every metrics mapping in ``payload`` with NO marker in scope.

    A marker is *in scope* for a mapping when the mapping itself carries
    :data:`TIE_POLICY_FIELD`, or when an **enclosing** mapping does — a record that names its
    regime once at the top does not have to repeat it on every nested block.
    """
    out: list[str] = []
    if isinstance(payload, Mapping):
        scoped = _in_scope or _explicit(payload.get(TIE_POLICY_FIELD)) is not None
        if is_metrics_mapping(payload) and not scoped:
            out.append(_at or "<root>")
        for k, v in payload.items():
            out.extend(unmarked_metric_paths(
                v, _at=f"{_at}.{k}" if _at else str(k), _in_scope=scoped))
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        for i, v in enumerate(payload):
            out.extend(unmarked_metric_paths(v, _at=f"{_at}[{i}]", _in_scope=_in_scope))
    return out


def assert_marked(payload: Any, *, where: str = "", authored: Sequence[str] | None = None) -> None:
    """REFUSE a payload that persists a metric without stating its scoring regime.

    ``authored`` restricts the check to the dotted subtrees this caller actually **wrote**. A
    recorder that merges into a record already on disk (``baseline_lock.json`` is the case here)
    cannot be held responsible for blocks written years ago by another lot — but it MUST name
    what it wrote, and naming it is precisely what makes forgetting the marker impossible: the
    named subtree is exactly where the check bites.
    """
    if authored is None:
        bad = unmarked_metric_paths(payload)
    else:
        bad = []
        for dotted in authored:
            node: Any = payload
            for seg in dotted.split("."):
                node = node.get(seg) if isinstance(node, Mapping) else None
            if node is None:
                raise UnmarkedMetricError(
                    f"authored subtree '{dotted}' is absent from the payload — a recorder must "
                    "name what it actually wrote."
                )
            bad.extend(f"{dotted}.{p}" if p != "<root>" else dotted
                       for p in unmarked_metric_paths(node))
    if bad:
        w = f" [{where}]" if where else ""
        raise UnmarkedMetricError(
            f"REFUSED to persist a metric with no scoring regime{w}: {', '.join(sorted(bad))}. "
            f"A persisted metric must carry '{TIE_POLICY_FIELD}' (ADR-0013 acceptance "
            f"precondition). This is refused rather than defaulted BECAUSE a missing field "
            f"resolves to the PRE-REGIME value '{PRE_REGIME_POLICY}': a NEW record that forgot "
            f"the marker would be silently filed as pre-regime and would hide a real "
            f"incommensurability the day the tie rule changes. Build the view with "
            f"tie_policy.metrics_view(), or stamp it with tie_policy.stamp()."
        )


def metrics_view(src: Mapping, *keys: str, policy: str | None = None,
                 extra: Mapping | None = None) -> dict:
    """Build a compact metrics view that **cannot** be built without the regime marker.

    The replacement for every hand-written ``{"ndcg@10": m["ndcg@10"], ...}`` re-key — the shape
    that dropped the marker in ``run_methods._strip`` and in ``transfer_eval``'s persisted
    ``metrics`` object. ``keys`` default to the four headline fields.

    ``policy`` names the instrument explicitly and is required when ``src`` carries no marker of
    its own: an unmarked *source* is either a legacy record (pass :data:`PRE_REGIME_POLICY`) or a
    number computed by something other than the shared scorer (pass
    :data:`LOCAL_REIMPL_POLICY`). It is never guessed here.
    """
    marker = policy if policy is not None else _explicit(src)
    if marker is None:
        raise UnmarkedMetricError(
            f"metrics_view() refuses to build a metrics record from a source carrying no "
            f"'{TIE_POLICY_FIELD}'. Pass policy=... naming the instrument that produced these "
            f"numbers ({CURRENT_TIE_POLICY!r} for the shared scorer, {PRE_REGIME_POLICY!r} for a "
            f"legacy record, {LOCAL_REIMPL_POLICY!r} for a local re-implementation)."
        )
    view = {k: src[k] for k in (keys or ("ndcg@10", "mrr", "recall@100", "n_queries"))}
    if extra:
        view.update(extra)
    view[TIE_POLICY_FIELD] = marker
    return view


def write_run_record(path: str | Path, payload: Any, *, indent: int | None = 2,
                     sort_keys: bool = False, ensure_ascii: bool = False,
                     trailing_newline: bool = True, authored: Sequence[str] | None = None,
                     where: str = "") -> Path:
    """The ONE door a whole JSON run record goes through. Validates, then writes.

    Validation is :func:`assert_marked` — the write does not happen when a metric would land on
    disk with no regime beside it. Serialisation options are explicit because two recorders here
    have a byte-identical-output contract (``compare.write_outputs``: ``sort_keys=True``).
    """
    path = Path(path)
    assert_marked(payload, where=where or path.name, authored=authored)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=indent, sort_keys=sort_keys, ensure_ascii=ensure_ascii)
    path.write_text(text + ("\n" if trailing_newline else ""), encoding="utf-8")
    return path


# ── The enumeration, as an executable instrument rather than a grep recipe ───────────────

def enumerate_metric_records(runners_dir: str | Path) -> dict[str, list[dict]]:
    """Every place a module under ``runners_dir`` builds a **metrics record** in source.

    **Why this exists.** The previous enumeration grepped for the literal string ``bench/runs``
    and therefore missed every recorder that *builds* its output path
    (``REPO_ROOT / "bench" / "runs" / ...``) — ``rerank_eval.py`` is the reviewer's example. This
    one asks a different, decidable question. It does **not** ask "which file does this write
    reach", because in this repository that is a **runtime** property: most recorders take their
    destination from the command line, so no static analysis can answer it. It asks the question
    that IS statically decidable and that covers the same defect: **where is a metrics record
    constructed, and does it state its regime?**

    Returns ``{module: [{"line", "fields", "marked"}]}`` for every dict literal
    :func:`record_fields` calls a metrics record — **one score field, or two metric fields of
    any kind** (S31 L9; it was two of any kind before, which is the gap the reviewer named).
    Test files are excluded: they build unmarked records on purpose, to exercise the legacy path.
    """
    out: dict[str, list[dict]] = {}
    for src_path in sorted(Path(runners_dir).glob("*.py")):
        if src_path.name.startswith("test_"):
            continue
        found: list[dict] = []
        for node in ast.walk(ast.parse(src_path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Dict):
                continue
            keys = {k.value.lower() for k in node.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)}
            fields = record_fields(keys)
            if fields:
                found.append({"line": node.lineno, "fields": sorted(fields),
                              "marked": TIE_POLICY_FIELD in keys})
        if found:
            out[src_path.name] = found
    return out


def enumerate_serialization_sites(runners_dir: str | Path) -> dict[str, list[int]]:
    """Every place a module under ``runners_dir`` **persists** JSON without going through
    :func:`write_run_record` — the serialization door, enumerated the same way as the record
    door (S31 L9).

    **Why this exists, and what it can and cannot do.** The independent reviewer demonstrated
    a bypass that :func:`assert_marked` cannot see: *« Plain ``json.dumps()`` still serializes
    that same unmarked payload »*. Whether a given payload is marked is a **runtime** property
    — the object does not exist until the module runs — so no static rule can answer it, and a
    rule that pretended to would be worse than none. **What is statically decidable is the
    route**: a ``json.dump``/``json.dumps`` whose result reaches a file. This function returns
    every such route, and the frozen inventory in ``test_tie_policy.py`` turns *adding one*
    into a failing test rather than a silent new bypass. A lot that adds a persistence route
    must either send it through :func:`write_run_record` — which validates at runtime, where
    the answer lives — or declare it, in a diff, with a reason.

    A call counts as **persisting** when it is ``json.dump(obj, fh)`` (two positional args, the
    file object) or when it sits inside a ``.write_text`` / ``.write`` / ``.writelines`` /
    ``.write_bytes`` call. ``print(json.dumps(...))`` is not persistence and is not counted.

    Returns ``{module: [line, ...]}``, test files excluded.
    """
    def _is_json_ser(n: Any) -> bool:
        return (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr in {"dump", "dumps"}
                and isinstance(n.func.value, ast.Name) and n.func.value.id == "json")

    def _is_sink(n: Any) -> bool:
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in {
                "write_text", "write", "writelines", "write_bytes"}:
            return True
        return _is_json_ser(n) and len(n.args) >= 2

    out: dict[str, list[int]] = {}
    for src_path in sorted(Path(runners_dir).glob("*.py")):
        if src_path.name.startswith("test_"):
            continue
        hits: set[int] = set()
        for node in ast.walk(ast.parse(src_path.read_text(encoding="utf-8"))):
            if not _is_sink(node):
                continue
            for sub in ast.walk(node):
                if _is_json_ser(sub):
                    hits.add(sub.lineno)
        if hits:
            out[src_path.name] = sorted(hits)
    return out
