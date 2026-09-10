# ADR-0010 — Whether the lab builds a measure of the assistant

**Status: Accepted**  
**Date:** 2026-09-02  
**Deciders:** Matteo (operator) — **Accepted S24**, branch B, under the binding condition recorded in the Accept section  
**Proposed by:** eval-lead (S24, lot `S24_MA_PROTO`)

## Accept (S24)

- **Operator:** Matteo · **Session:** S24
- **Branch ticked:** ☐ A  ☒ **B**  ☐ C — « Un minimum, borné », accepted **verbatim** as
  **« Ok go reco »**, i.e. the operator took the recommendation of this ADR *together with the
  condition he attached to it* (below). No branch other than B is accepted, and accepting B is not
  a step towards C.
- **Reason in one sentence:** it puts an instrument on the one weakness this repo has actually
  measured, at a cost the lab can pay without competing with the retrieval bench, and it needs no
  judge gate to exist first because its calibration sample is human.
- **Gate:** the operator's own call. Branch B carries **no AUD-3 as a gate** (see the AUD-3 section
  below) — the non-Claude check is owed only if a B number is ever published as evidence *about the
  assistant's quality* rather than as a pre-demonstration guard.

### Condition attached to the Accept — BINDING, on this lot and on every later report

**The refusal figure is never published without, beside it, the sentence saying that it does not
measure the quality of the synthesis.** The number and that sentence travel together: in the report,
on any page, in any slide, in any spoken presentation of the figure. A reader who meets the number
must meet the caveat in the same breath, because the number is a count of refusals on a fixed probe
set and nothing more.

Three clauses follow from it and are equally binding:
1. **`RESERVE_PUIS_REPONSE` is reported beside `REFUS`, never folded into it.** Folding it in is the
   error the S24 query bench already caught, and it would turn a reserve into a refusal by
   arithmetic.
2. **The counter-argument stays.** The « strongest argument against it » in the Recommendation
   section below is **not** superseded by this Accept: it is what a reader needs in order to read the
   number correctly, and it is the reason this condition exists. B produces a green number on the
   *narrowest* failure; that green number must never be readable as « the assistant is monitored ».
3. **The figure does not make the model refuse.** It makes the rate visible. Any later lot that
   changes the refusal behaviour is a **separate** decision, taken after a measurement, never inside
   one.

### What this Accept authorises

Exactly the five numbered steps of branch B below and nothing beyond them: the three harness changes
(served snippets · the stronger format check alongside the substring one · both citation bracket
forms), the run of the 20 versioned probes of `docs/research/S24_assistant_probes.jsonl`, the
three-value §2.1 scoring, the one blind human calibration sheet, and a report that states both
directions symmetrically.

### What it does NOT authorise

Everything listed under « What an Accept would authorise — and what it would not » below, unchanged
and in full — in particular: no touch to `bench/runs/baseline_lock.json`, `pyproject.toml`,
`uv.lock` or `.venv`; **no change to the assistant's system prompt, its temperatures or
`ASSIST_TOP_K`**, which are the instrument as much as the model is; **no fixing** of the refusal
behaviour; **no reporting of any assistant number in the same frame as a bench result**. And it
authorises **no verdict on the assistant's grounding or synthesis quality**, which branch B does not
measure and this Accept does not open.

### Two limits this Accept does not remove

- **The model is still unpinned.** `qwen2.5:7b` is a mutable tag with no revision pin, so any number
  produced under this Accept **describes an unidentified model** and a pull can change the subject
  without changing a byte of this repo. The Accept does not create the pin; it inherits the gap.
- **A fixed set is only ever a guard.** Twenty probes × three passes bound very little on their own
  (rule of three, §1.4 of the design), and passes on the same query are not independent
  observations. Mitigation, and it is cheap: the set is versioned, and any out-of-corpus query heard
  in a real session is added to it afterwards.

> **Only Matteo accepts.** A worker may propose; a finder's verdict is not an Accept either — the
> Accept gate is the operator's, exactly as in ADR-0009. This section records his decision; it does
> not substitute for it.

---

## Context

**This ADR produces NO measurement and attempts none.** It records a **decision to be taken**, and the
design that a follow-up lot would execute if the decision authorises one
(`docs/research/S24_assistant_measure_design.md`).

Ariane runs two models and only one of them is measured
(`docs/research/S23_agent_releve.md` §0). The **retriever** is measured under
`docs/adr/0002-measure-before-engine.md`: sealed holdout, nDCG@10, Holm on m=3, a non-Claude
adjudication rule, cross-collection corroboration, `bench/runs/baseline_lock.json` byte-untouched
since S5. The **assistant** — `qwen2.5:7b` via ollama, which translates the French query and writes
the French synthesis — is measured by nothing: S23's closing item **18** records *"no qrels exist for
the synthesis task, no judge, no holdout… Nothing in this repo measures the assistant"*; its selection
was a comparative trial of **n≈3, one operator, no protocol** (§1b); and `demo/assistant.py` is
exercised by **no test** (26 tests now defined in `demo/tests/test_demo.py`, none of which imports it).

**This is not an oversight** — it is the *measure before engine* doctrine applied honestly: the
assistant is a reading aid, it selects no ticket, and measuring it would cost a reference corpus of
syntheses, therefore human judgement, therefore time the retrieval bench already consumes.

**But the price is now visible, twice measured, and it is the one thing nothing watches.** S23 found
refusal **0/2** on out-of-corpus queries. S24's query bench
(`docs/presentation/S24_banc_requetes.md` §7.2, traces `S24_banc_requetes_traces.jsonl`) replayed that
on a 4.5× larger sample, three passes each: **refusal 0 out of 9** — the system answers, well-formed,
in three sections, citing **real** ticket ids for claims those tickets do not carry. The citation
guard passed **90 / 90**, and that number proves nothing about grounding, **because it is an existence
test, never a groundedness test** (`demo/assistant.py:149-158`).

The operator's notebook states the stake in one sentence
(`docs/presentation/CARNET_HORS_LIGNE.md` §4.3):

> **« Sans décision explicite, l'état de fait devient la politique par dérive. »**

---

## Decision put to the operator — three branches, tick exactly one

The branches are the operator's own, verbatim from `CARNET_HORS_LIGNE.md` §4.3. They are not renamed
and not re-scoped. Each is stated so that **ticking it is a complete instruction to the next lot**.

### ☐ Branch A — « Non, et on l'assume par écrit »

**Instruction to the next lot if ticked:** none — the work is this ADR. Fill the Accept section with
branch A and the one-sentence reason; the served pages already state the absence on screen and are
held there by `demo/tests/test_demo.py:225-247`. **No probe is run, no harness is changed, no metric
is created.** `docs/research/S24_assistant_probes.jsonl` stays in the repo as unexecuted material.

### ☐ Branch B — « Un minimum, borné » (a bounded guard set)

**Instruction to the next lot if ticked, in the order it must be done:**
1. **Change the harness before measuring anything**: `demo/query_bench.py` must record, per row, the
   **served snippets** (`summary` + `snippet` of each of the 5 cards) — today only ids are stored, so
   no grounding grade is reproducible from the artefact — plus the **stronger format check** of the
   design's §2.4 alongside the existing substring one, and a citation extraction covering **both**
   observed bracket forms (`[id]` and `[id, id]`).
2. **Run the 20 probes of `docs/research/S24_assistant_probes.jsonl`**, foreground and bounded, on a
   **dedicated port** — never the operator's server.
3. **Score with the design's §2.1 three-value refusal scale** — `REFUS` / `RESERVE_PUIS_REPONSE` /
   `REPONSE`. The reported rate is `REFUS / n`; `RESERVE_PUIS_REPONSE` is reported **separately and
   never folded in**.
4. **Calibrate the detector on ~20–30 blind human calls, once** (the sheet form of
   `.pilot/_outputs/A_human_adjud_sheet.md`, never committed). A keyword rule alone cannot apply §2.1:
   Q29's reserve is the standing counter-example.
5. **Report both directions symmetrically.** A refusal rate that has not moved is as publishable as
   one that has; nothing in the instruction anticipates either.

### ☐ Branch C — « Oui, un vrai banc de synthèse »

**Instruction to the next lot if ticked:** do **not** build the bench first. Run the **judge gate**
first, exactly in the shape of `docs/research/A_pilot_judge_gate.md` → `A_pilot_judge_gate_qwen.md`:
a capability probe on constructed known-answer items with **PASS / FAIL / INCONCLUSIVE all
admissible**, the lab's own **≥ 5/7** floor, the judge **never `qwen2.5:7b`** (it is the subject).
Only if the gate passes: build per-`(sentence, id)` labels on the design's **`support` × `pertinence`
split** (§2.2), validate against a **blind human sheet of 30** on the pre-registered decision rule of
§3.3, and only then a holdout and a metric. **If the gate returns *escalate*, stop and return to the
operator** — choosing between a bigger local model and an egress decision is his call, not a worker's.

---

## Consequences of each branch

| | **closes** | **explicitly does NOT close** | **cost (worker-lots · human adjudication)** | **failure mode that would make it a waste** |
|---|---|---|---|---|
| **A** | the drift: the state of fact becomes a dated, signed choice | refusal 0/9 · grounding · the guard's blind spot · the n≈3 model choice | **0 lots** beyond this Accept · **0 human calls** | a written assumption stops nothing — the first out-of-corpus query typed by someone who has not read `docs/presentation/MES_REQUETES.md` produces the same confident wrong answer, now pre-admitted |
| **B** | the §4/§13 line: the refusal instruction stops being unwatched — a dated number exists and moves or does not | grounding · synthesis quality · the existence-vs-support gap · and **it does not make the model refuse** | **2 lots** (harness+runner · run+report) · **~20–30 blind calls, once** | measuring a keyword instead of a behaviour; and a fixed set becoming the only thing ever checked, so a live query outside it fails silently |
| **C** | the quality question, comparably across models — and it turns the **n≈3** model choice into a measured one | the assistant's role (it still selects no ticket) · the format-vs-refusal tension, which is a **prompt** decision | **≥ 5 lots** (judge gate + escalation · build · second-model agreement · human sheet · freeze) · **≥ 1 operator adjudication session** — the A precedent's actual shape | the S15 pattern on harder ground: judge and second model converge, the human breaks them, a region turns out not reliably gradeable — and for free-text there is no obvious feature to identify and demote it by |

---

## Recommendation, and the argument against it

**Recommended: Branch B**, scoped as the three-value refusal scale over a versioned probe set **plus**
a small fixed `support` × `pertinence` spot-check graded by the human sheet rather than by a judge.

**The reason, in one sentence:** it is the only branch that puts an instrument on the **one weakness
this repo has actually measured**, at a cost the lab can pay without competing with the retrieval
bench — and it needs **no judge gate to exist first**, because its calibration sample is human.

**The strongest argument against it.** B measures the property that is easiest to measure, not the one
that matters most. The demonstration's real risk is **not** the obviously out-of-corpus query — the
operator can simply not type one, and `docs/presentation/MES_REQUETES.md` already names these three on
a do-not-type list. The real risk is a confident, well-formed, correctly-cited **wrong explanation for
an in-corpus query**, which B does not touch. And by producing a green number, B manufactures the
impression that the assistant is *monitored* when only its narrowest failure is — a false assurance
that **A**, which claims nothing, never creates. If that reading is right, the coherent choices are
**A** (honest, free) or **C** (which measures the thing), and **B is the comfortable middle**.

---

## What an Accept would authorise — and what it would not

**Would authorise (branch-dependent):** exactly the numbered instruction of the ticked branch above,
and nothing beyond it.

**Would NOT authorise, under any branch:**
- touching `bench/runs/baseline_lock.json`, `pyproject.toml`, `uv.lock` or `.venv`. **This ADR concerns
  the assistant, which appears in no bench number**; nothing here can move the standing engine, and no
  outcome of any branch is a supersede or a re-seal;
- changing the assistant's **system prompt**, its temperatures, or `ASSIST_TOP_K` as part of a
  measuring lot. The prompt is the instrument as much as the model is: changing it while measuring it
  destroys the comparability the guard set exists to create. A prompt change is a **separate**
  decision, taken after a measurement, never inside one;
- **fixing** the refusal behaviour. Measuring it and changing it are two lots and two decisions;
- reporting any assistant number in the same frame as a bench result. The reading rule of S23 stands:
  bench results and engineering observations are never mixed, and `test_demo.py:122-136` already
  forbids a bench score anywhere near a live result on screen;
- pronouncing any verdict on the assistant if a judge is used and its output is **degenerate** — that
  is an instrument failure before it is a finding (`A_pilot_judge_gate.md`), and the correct output is
  *escalate*, not a number.

**Pinning, as a precondition rather than a refinement.** The assistant's identity is the **mutable tag**
`qwen2.5:7b` — no revision pin (S23 closing item 6), unlike the embedder which is pinned to a commit
sha and CI-enforced. Any number produced under branch B or C before a pin exists **describes an
unidentified model**, and a pull can change the subject without changing a byte of this repo.

---

## AUD-3 — which branch needs a non-Claude check before it binds anything

- **Branch A** — no AUD-3. It creates no instrument and binds no future number; it is an operator
  decision recorded in an ADR, and the operator is the independent voice.
- **Branch B** — no AUD-3 **as a gate**. It produces a guard, not a claim about the engine, and it
  binds nothing outside the demonstration. If its number is ever published as evidence *about the
  assistant's quality* rather than as a pre-demo check, that publication needs the check, not the run.
- **Branch C — yes, and on the design, before the spend.** C constructs **ground-truth labels**, and
  the lab's own hardest lesson is at that layer: in S15 two models converged on the labels and **only
  the independent human broke them** (`docs/ROADMAP.md:570-572`). C's rubric, its judge choice and its
  human-sample decision rule are a *design* — the same object ADR-0009 §D7 sent to a non-Claude finder
  **before** paying. The finder is **codex** (S18 operator decision; S19 records the backend as
  codex-only). Its verdict is **not** an Accept: the Accept gate stays Matteo's.

---

## Relationship to prior ADRs and to the convergence rule

- **`docs/adr/0002-measure-before-engine.md`** — the doctrine this ADR applies. Branch A is *"the
  assistant is not the contribution, and we say so"*; B and C extend the doctrine to a second object.
- **`docs/adr/0001-local-first-monorepo.md`** — binds branch C's judge: a hosted judge would ship
  ticket text and model prose off the host. The J2.2 precedent resolved to **local-qwen / 0-egress**
  and kept the hosted option a last-resort **operator** call.
- **`docs/adr/0009-within-c-corroboration.md`** — the shape followed here: Status / Date / Deciders /
  Proposed by, an Accept section the operator fills, an explicit statement of what an Accept does and
  does not authorise, and outcomes weighted symmetrically before the run.
- **Convergence caveat (mandatory).** This ADR is a single-model (Claude) design of a measurement of a
  non-Claude model, written by the same family that writes this lab's other designs. Its
  **recommendation** is the part most exposed to that risk — a recommendation is easier to manufacture
  by motivated reading than a negative finding — which is why the counter-argument above is stated at
  the same length and why the decision is the operator's alone.

---

## Falsifier / rollback

- **A is falsified** the day an out-of-corpus answer is given in front of an audience: the ADR then
  records a decision whose cost was paid publicly, and the branch reopens at **B**.
- **B is falsified** if its refusal detector disagrees with the human sample beyond the design's §3.3
  rule, or if a live demonstration query outside the probe set produces the failure the guard was
  supposed to watch. Rollback: the probe set is versioned; the number is retired, not patched.
- **C is falsified** if no available judge clears the **≥ 5/7** capability floor and the operator
  declines both escalations — then the grounding definition has no instrument and C is unbuildable as
  written, leaving a human-only design whose cost is a different decision.
- **All three are falsified** by an unpinned model change (above), which voids every number produced
  under them.
