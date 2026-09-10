# Evaluation and governance for enterprise AI

[![verify](https://github.com/katssen4/engineering-portfolio/actions/workflows/verify.yml/badge.svg)](https://github.com/katssen4/engineering-portfolio/actions/workflows/verify.yml)

Eight years keeping bought software running inside a regulated bank. Since March 2026 I build my
own systems, and I measure them before I believe them.

This repository holds the measurements. Every artefact is a file from a real run.

## What I built

| System | What it does | Status |
|---|---|---|
| Knowledge platform | Hybrid retrieval over enterprise documents, per-connector access control, agent access over MCP | Built, 284,347 lines of Python |
| Evaluation bench | IR measurement under a written protocol, sealed corpus, regression gate | Built, and the source of most of this page |
| Agent harness | Scoped development agents across five model backends, chained audit log | In daily use, described in section 2 |
| labo-llm.fr | Bilingual technical corpus on language models | Live, 149 articles in each language |

Six others exist. The eight together come to 448,866 lines, built alone, without a software team.
Coding agents are part of that workflow, which is what section 2 is about, and the commit history
of this repository shows them.

## Check it before you read it

    git clone https://github.com/katssen4/engineering-portfolio
    cd engineering-portfolio
    python3 tools/verify.py

41 checks, no network, standard library plus a pinned pytest. GitHub runs it on every push, which
is what the badge reports.

Three families of number appear below, and they carry different weight.

*Recomputed.* The control score of the fine-tune. The script reads the two TREC run files and the
judgements, computes nDCG@10 itself, and gets 0.575258. No part of that comes from a decision file.

*Consistency-checked.* The retrieval table. Its cells are compared against the sealed lock, so a
drifted page fails the check. The runs behind those numbers are not shipped, so this proves the
page matches the lock and nothing more. The seal itself is a self-hash: it catches drift, and
anyone who edits the lock can recompute it.

*Declared.* Line counts, pinned hashes, runbook lines, article totals. Each has its command, scope
and date in [`evidence/declared-metrics.md`](evidence/declared-metrics.md). You can read the
method. You cannot run it against a system you do not have.

The 58 shipped unit tests run in the same pass, and the script finishes by counting its own checks
against the numbers printed on this page.

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

What makes the protocol worth showing. The corpus is sealed with SHA-256 manifests, and each of
the 5,572 relevance judgements carries a provenance record saying where it came from. The reference
is 18 engine configurations frozen in one file with an integrity hash. The regression policy was
written before any result: primary metric `nDCG@10`, trigger delta 0.01, paired t-test, threshold
0.05, and a failure declared only when a drop clears the delta **and** reaches significance.

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
files and the held-out judgements, so `verify.py` recomputes the failure and localises it to that
single query.

---

## 2. Governing agents that write code, declared and not shipped

**Read this section as a claim, because that is what it currently is.** No file here demonstrates
it. The evidence layer for it is planned and absent, and calling it proven would contradict the
rest of the page.

I develop through a harness I wrote, because I wanted answers to three questions before letting
agents near a repository.

**What is the agent allowed to touch.** Per-agent write scopes, enforced by a git `pre-commit` hook
that refuses the commit.

**How do I prove afterwards what it did.** An append-only audit log chained with HMAC-SHA256, a
chain verification function, and a guard that refuses to run in a mode where the chain would not be
tamper-evident. The key lives on the workstation, so the chain is evidence against silent
corruption and against a careless agent, not against me.

**What happens if one vendor disappears.** A dispatch layer across five model backends, and a
commit broker that serialises the git writes of parallel agents so `.git/index.lock` collisions
cannot occur.

This governs development agents on a workstation. It is no part of a production inference
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
writing a byte, and writes nothing when one fails. A prober calls the live endpoints of six
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
  hashes**, a compose file with a health probe, and **4,005 lines of deployment runbook** down to
  DNS records and the first production cutover. That is a Docker host, and a Docker host is a
  different skill from a cluster.
- **No GPU orchestration, no inference platform at scale.** The bench runs on one machine.
- **No production traffic.** One application of mine is live, with two users. No on-call, no
  incident load, no multi-tenant scale of my own.
- **No external client reference.** My delivery record sits inside one employer and on my own time.
- **No agent-governance evidence yet**, as section 2 says.

---

## Who I am

Systems and integration engineer, eight years in regulated banking on one recurring job: taking a
solution designed elsewhere and making it hold inside a real enterprise environment. Today I am
technical owner of a multi-tenant provisioning platform at the infrastructure arm of a French
banking group, covering 3 banking platforms and more than 200,000 lines.

- Site: [labo-llm.fr](https://labo-llm.fr)
- LinkedIn: [matteo-l-35116a17a](https://www.linkedin.com/in/matteo-l-35116a17a/)
- Nantes, France. Open to roles worldwide, subject to work authorisation outside the European
  Economic Area.

---

## Licence

MIT. See [LICENSE](LICENSE). Take anything here and use it.
