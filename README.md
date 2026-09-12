# Evaluation and governance for enterprise AI

[![verify](https://github.com/katssen4/engineering-portfolio/actions/workflows/verify.yml/badge.svg)](https://github.com/katssen4/engineering-portfolio/actions/workflows/verify.yml)

Eight years keeping bought software running inside a regulated bank. Since March 2026 I build my
own systems, and I measure them before I believe them.

This repository holds the measurements. The experimental evidence comes from real runs; the gate
examples are synthetic and labelled as such.

## What I built

| System | What it does | Evidence here |
|---|---|---|
| Knowledge platform | Hybrid retrieval over enterprise documents, per-connector access control, agent access over MCP | Its retrieval engine, measured in section 1 |
| Evaluation bench | IR measurement under a written protocol, sealed corpus, regression gate | Most of `evidence/`, and the code in `evidence/code/` |
| Agent harness | Scoped development agents across five model backends, chained audit log | Write-scope guard and audit chain, shipped as reduced extracts in `evidence/agent-governance/` |
| labo-llm.fr | Bilingual technical corpus on language models | The live site, 149 articles in each language |

Three of those four are software products, and five more exist, so eight in all. Sizes and the
commands behind them are in [`evidence/declared-metrics.md`](evidence/declared-metrics.md), kept
off this page because a line count measures how much code there is and nothing else.

I designed and delivered them independently, without a software team. Coding agents are part of
that workflow, which is what section 2 is about, and the commit history here shows them.

## Check it before you read it

    git clone https://github.com/katssen4/engineering-portfolio
    cd engineering-portfolio
    python3 -m pip install -r requirements-ci.txt
    python3 tools/verify.py

60 checks. Once its one test dependency is installed the run touches no network and downloads no
corpus. GitHub runs it on every push, which is what the badge reports. Hand it a truncated run file
and it names the malformed line and stops, instead of dying on a stack trace.

Three families of number appear below, and they carry different weight.

*Recomputed.* The control score of the fine-tune. The script reads the positive-control run and
the held-out judgements, computes nDCG@10 itself, and gets 0.575258. No part of that comes from a
decision file, and it never touches the treated run.

*Consistency-checked.* The retrieval table. Its cells are compared against the sealed lock, so a
drifted page fails the check. The runs behind those numbers are not shipped, so this proves the
page matches the lock and nothing more. The seal itself is a self-hash: it catches drift, and
anyone who edits the lock can recompute it.

*Declared.* Line counts, pinned hashes, runbook lines, article totals. Each has its command, scope
and date in [`evidence/declared-metrics.md`](evidence/declared-metrics.md). You can read the
method. You cannot run it against a system you do not have.

The 140 shipped unit tests run in the same pass, 202 cases once the table-driven ones are
expanded, and the script finishes by counting its own checks against the numbers printed on this
page.

Six outside reviews and two internal adversarial audits have run against this repository. What
each one found, and the test or control that now stops it coming back, is one row per finding in
[`evidence/review-history.md`](evidence/review-history.md). The verifier resolves every anchor in
that file, so a row whose test disappears fails the run. The rows that nothing can pin are marked
as such, because most documentation drift cannot be tested, which is why it drifts.

## How I work

Eight years of taking a design written elsewhere and making it hold in someone else's
environment taught me the part of this job that has not changed: the problem arrives badly
stated, and someone has to carry it until it is executable. What the system must do, what it
must refuse, and how anyone would know it works. That is the part I do. Coding agents do a large
share of the typing. The commit history here shows them, and `evidence/review-history.md` shows
what outside readers found in what they produced.

I do not hold every layer of these systems in my head, and I do not claim to. I know what each
mechanism has to guarantee and why it is there. When a number does not land where it should, I
go down as far as that number requires. Section 1 is the case worth reading for this: a positive
control missed its own reference, and the entire gap sat in one query out of 310, where two
documents held the same score to the last fp16 bit and two providers broke that tie in opposite
directions. Reading the evaluation library was the only way to find it. Nothing here required me
to read it before the control failed.

That boundary is the reason the controls exist. A number recomputed by a script does not depend
on my remembering it correctly, and a write perimeter checked by a guard does not depend on my
remembering what I declared three weeks ago. Most of what is shipped in this repository is
machinery that refuses on my behalf.

---

## 1. Measuring a retrieval engine

Given a new incident ticket, retrieve the past tickets closest to it. Four projects, one protocol,
a sealed corpus and a locked reference. `nDCG@10` on the primary collection:

| Project | Keyword | Vector | Hybrid | Queries |
|---|---:|---:|---:|---:|
| Hadoop | 0.567 | 0.602 | **0.629** | 128 |
| Cassandra | 0.489 | 0.491 | **0.521** | 302 |
| HBase | 0.434 | 0.465 | **0.497** | 111 |
| Spark | 0.364 | 0.415 | **0.426** | 509 |

These are scores on a public corpus of software tickets, with these judgements. They say nothing
about yours. The gain is uneven: 0.062 on Spark against 0.032 on Cassandra, on collections of very
different sizes, and neither figure carries a confidence interval. What transfers is the protocol.

What makes the protocol worth showing. The corpus is sealed with SHA-256 manifests, and the 5,572
relevance judgements come with seven provenance records, one per judgement set, each naming the
source dataset, how a judgement was derived and what was excluded. The reference
is 18 engine configurations frozen in one file with an integrity hash. The regression policy was
written before any result: primary metric `nDCG@10`, trigger delta 0.01, paired t-test, threshold
0.05, and a failure declared only when a drop clears the delta **and** reaches significance.

The gate produces a verdict only from quantities it can defend. A baseline whose seal is valid but
whose payload cannot gate, a metric or p-value that is missing, non-numeric, non-finite or out of
range, a collection that is not sealed, a corpus present locally with a hash the manifest does not
recognise: each of those is a setup error and exits 2, never a pass. The last one is the reason the
list exists. A drifted corpus is not an integrity problem, it is a comparability problem, and a
gate that runs anyway compares the baseline's dataset against a different one and credits the
difference to the system under test.

### The fine-tune whose score I have never read

I fine-tuned an embedding model on this corpus. The model exists. The memory guard was measured at
**5,863.5 MiB peak against a 6,000 MiB ceiling** set before the run.

I do not know its score.

The protocol required a positive control first: put the base model back through the same harness
and check it reproduces its own reference. It returned 0.575258 against 0.576448, outside a
tolerance of 5e-7.

**The gap turned out to be the interesting part.** All of it sits in one query out of 310,
`cassandra:13318333`. Two documents there hold the same score to the last fp16 bit, `0.816895`,
one relevant and one not. The evaluation library serves two providers through a single aggregate
call, and they break that tie in opposite directions, so the reference and the control were never
ranking the same list. ADR-0013 documents the mechanism and specifies the guard it needs. That
guard is not built, so the control cannot be rerun yet, and the arm stays blocked.

The decision record written before the run said what to do when a control misses. The run file
says `status: fail`, `verdict: null`, and the note reads: *the arm is BLOCKED, no verdict issued,
no number interpreted.* No threshold was relaxed, on the memory guard or on the tolerance.

Everything is in [`evidence/finetune-blocked/`](evidence/finetune-blocked/), including the TREC run
files and the held-out judgements. `verify.py` recomputes the control failure from them, and checks
the shipped per-query diagnostic that puts the whole gap on one query.

**The blinding here is procedural, not technical, and you should know which.** The treated run and
the judgements are both shipped, so anyone can score the fine-tuned arm in a few lines. I have not,
and will not while the positive control is failing. What the repository guarantees is a decision
record written beforehand and a run file that carries no verdict. What it does not guarantee is
that the number is out of reach. Saying otherwise would be the kind of claim this page exists to
avoid.

---

## 2. Governing agents that write code

Two mechanisms from my development harness are shipped and tested in
[`evidence/agent-governance/`](evidence/agent-governance/), as reduced extracts. They are not the
harness, which is 32,159 lines across 126 Python files.

**What may the agent write.** Every worker prompt declares the paths it may write. A guard compares
that declaration to the paths the staged commit mutates, and exits 1 on anything outside. A commit
is not a list of destination paths: a rename is two positions, and both go through the policy, so
moving a forbidden file into an allowed directory is refused rather than seen as a create. A path
listed as forbidden refuses even when a write rule would otherwise allow it, and a `*` matches
inside one path segment, never across `/`.

The grammar is explicit, because a string that can mean two things is not a permission.
`src/foo/` is a directory and covers what is under it, `config/settings.json` is that file and
nothing else, `reports/*.json` matches inside one path segment, and `**` is how you write a
traversal. A path containing a space is written between backticks or it is refused, never
truncated at the space into a shorter and broader prefix.

It exits 2 whenever the perimeter cannot be established: no scope block, several of them in any
casing, a structured scope with no writing section, a block whose lines it cannot classify, a path
whose end it cannot determine, a forbidden section written in a form the grammar does not carry, or
an enumeration of staged files that failed. Not being able to determine either the write perimeter
or the full set of paths the commit mutates never grants permission.

    python3 scope_guard.py --prompt example/prompt_avec_scope.md --staged src/auth/session.py

    [scope_guard] COMMIT REFUSE : 1 fichier(s) hors perimetre
        src/auth/session.py

The tools speak French, the pages about them speak English. The line above is the real output,
transcribed rather than translated.

**What can be checked afterwards.** An application-level append-only writer, chaining records by
SHA-256 and authenticating each with HMAC-SHA256 under an exclusive lock. Modifying or reordering
records, or deleting one that still has a successor, breaks the chain and `verify_chain` names the
record. Truncating the tail does not: a valid prefix is a valid chain, and detecting that needs a
commitment to the expected head stored outside the file. That limit ships as a passing test, along
with the fact that the key sits on the same workstation as the agents, so the chain is evidence of
integrity and not of innocence.

**What is declared and not shipped.** The dispatch layer across five model backends, the commit
broker that serialises parallel git writes, the nineteen domain validators encoding my architecture
rules, and the doctrine documents. No file here demonstrates any of them.

All of this governs development agents on a workstation. It is no part of a production inference
platform, and I do not present it as one.

---

## 3. Tools that refuse

Four small programs built on one idea: a tool that produces something should be able to refuse,
with a non-zero exit code and the name of the control that failed.

The anti-invention gate is the one worth running. It compares a derived document against its
source of truth with a deliberately coarse lexical heuristic: numeric tokens keeping their sign,
unit and decimal part, and capitalised words that do not open a sentence. Example data ships with
it.

    cd evidence/gates
    python3 anti_invention.py example/source_of_truth.md example/derived_with_invention.md --banals Meridian

    SIGNAL  derived_with_invention.md
            nombres absents du socle : 90000
            noms absents du socle    : kubernetes

An inflated throughput figure and a deployment claim the source never made. The honest derivation
passes, including when it writes a number differently: `48k` and `48,000` give the same key, while
`5.0` and `50` do not.

**What it misses ships as tests.** Being lexical, it lets through a sentence that contradicts the
source without introducing a token: *Scaling across nodes has been validated in production* passes
against a source stating there is no cluster. It also compares only what a derivation adds, so
deleting a section of caveats is invisible to it. Both cases sit in
`evidence/gates/tests/test_anti_invention.py` as passing tests asserting the real behaviour, which
means improving the gate breaks them and forces this paragraph to change with the code.

The other three are shorter to describe. A document builder runs eleven layout controls before
writing a byte, and writes nothing when one fails. Worth being exact about what those controls
watch: ten of them guard the generator against itself, since it never emits a table, a header or a
second column, and its font sizes and contrast ratios come from its own constants. Only the em-dash
control can fail on the input, and it does, with the file unwritten. A prober calls the live endpoints of six
applicant tracking systems, because one of them answers 200 on identifiers that do not exist. A
proof register checks that its own claims still point at tests that exist and strings still present
in the code.

They come from a workbench I built for my own job search. The data that passed through stays
private; the machinery is here, with the personal parts turned into parameters. See
[`evidence/gates/`](evidence/gates/).

---

## 4. Writing, in two languages

[labo-llm.fr](https://labo-llm.fr) is a sourced corpus on large language models that I write and
publish alone. **149 articles in French and 149 in English**, in exact mirror. Each claim carries
its source, hypotheses are marked as such, and negative results are archived like positive ones.

---

## What is not here, and not in my experience

- **No Kubernetes in production, no Helm, no public cloud**, here or anywhere in my experience.
  What does exist on the platform this bench measures is containerisation: a Docker image on a slim
  base running as a non-root user, dependencies installed from a lock file carrying **1,311 pinned
  hashes**, a compose file with a health probe, and **3,310 lines of deployment runbook** down to
  DNS records and the first production cutover. That is a Docker host, and a Docker host is a
  different skill from a cluster.
- **No GPU orchestration, no inference platform at scale.** The bench runs on one machine.
- **No production traffic.** One application of mine is live, with two users. No on-call, no
  incident load, no multi-tenant scale of my own.
- **No external client reference.** My delivery record sits inside one employer and on my own time.
- **No evidence for the dispatch layer, the commit broker, or the domain validators.** The
  write-scope guard and the audit chain are shipped and tested. The other three are described only.

---

## Who I am

Systems and integration engineer, eight years in regulated banking on one recurring job: taking a
solution designed elsewhere and making it hold inside a real enterprise environment. Today I am
technical owner of a multi-tenant provisioning platform at the infrastructure arm of a French
banking group, covering 3 banking platforms and more than 200,000 telephony lines.

- Site: [labo-llm.fr](https://labo-llm.fr)
- LinkedIn: [matteo-l-35116a17a](https://www.linkedin.com/in/matteo-l-35116a17a/)
- Nantes, France. Open to roles worldwide, subject to work authorisation outside the European
  Economic Area.

---

## Licence

MIT. See [LICENSE](LICENSE). Take anything here and use it.
