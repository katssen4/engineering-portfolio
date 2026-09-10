# Applied AI engineering, measured

I build AI systems inside regulated enterprises, and I measure whether they work.

This repository is a portfolio. It exists to show four things a hiring team cannot check from a
CV: that I can measure a component instead of asserting it, that I can govern agents that write
code, that I build tools which refuse rather than tools which warn, and that I publish the
numbers that do not favour me.

Everything below is a real artefact from work I built alone. Nothing here is a tutorial.

## Check it before you read it

Every number on this page is recomputed from files that ship with the repository:

    git clone https://github.com/katssen4/engineering-portfolio
    cd engineering-portfolio
    python3 tools/verify.py

32 checks. It verifies the SHA-256 seal on the reference lock, rebuilds the table below cell by
cell from that lock, confirms the blocked fine-tune really was blocked, runs the anti-invention
gate on the example documents that ship with it, and runs the 45 shipped unit tests. No network,
no corpus download, standard library plus pytest.

`evidence/` holds the working artefacts themselves, copied out of the bench that produced them.

---

## 1. Measuring a retrieval engine, and refusing to read the result

The task: given a new incident ticket, retrieve the past tickets closest to it.

Four projects, one protocol, a sealed corpus, and a locked reference. Selected numbers from the
reference lock, `nDCG@10` on the primary collection:

| Project | Keyword | Vector | Hybrid | Queries |
|---|---:|---:|---:|---:|
| Hadoop | 0.567 | 0.602 | **0.629** | 128 |
| Cassandra | 0.489 | 0.491 | **0.521** | 302 |
| HBase | 0.434 | 0.465 | **0.497** | 111 |
| Spark | 0.364 | 0.415 | **0.426** | 509 |

**The qualification, and it belongs directly under the table.** These are scores on a public
corpus of software tickets. They say the hybrid engine beats the keyword baseline on all four
collections, with these judgements. They do not say it would beat it on yours, and the gain is not
uniform: it is worth 0.062 on Spark and 0.032 on Cassandra, on collections of very different sizes.
What transfers is the protocol, not the number.

What makes the protocol worth showing:

- **A sealed corpus.** SHA-256 manifests, and 5,572 relevance judgements that each carry a
  provenance record saying where the judgement came from. Documenting the provenance of relevance
  judgements is rare, and it is what makes a retrieval measurement arguable rather than decorative.
- **A locked reference.** 18 engine configurations frozen in a single file with an integrity hash,
  so a later run can be compared to an earlier one rather than to a memory.
- **A regression policy written before the results.** Primary metric `nDCG@10`, trigger delta 0.01,
  paired t-test, significance threshold 0.05, and a failure declared only when a drop is **both**
  beyond the delta **and** significant. The failure condition is written down, and it requires both.

### The fine-tune whose score I have never read

I fine-tuned an embedding model on this corpus. The model exists. The memory guard was measured,
not estimated: **5,863.5 MiB peak against a 6,000 MiB ceiling** written before the run.

I do not know its score.

The protocol required a positive control before looking at the treated arm: run the base model
back through the same harness and check it reproduces its own reference. It returned 0.575258
against a reference of 0.576448, for a tolerance of 5e-7. The instrument was therefore suspect,
and the decision record written **before** the run said what to do about it. The run file says
`status: fail`, `verdict: null`, and the note reads: *the arm is BLOCKED, no verdict issued, no
number interpreted.*

No threshold was relaxed. Not the memory guard, not the control tolerance.

That is the piece of this repository I would most want a hiring team to read. Anyone can show a
fine-tune that worked. This one shows a protocol that held when it was inconvenient.

The files are in [`evidence/finetune-blocked/`](evidence/finetune-blocked/), including the two TREC
run files and the held-out judgements, so the control failure can be recomputed rather than taken
on my word.

---

## 2. Governing agents that write code

I develop through a harness I wrote, because I was not willing to let agents near a repository
without answers to three questions.

**What is the agent allowed to touch.** Per-agent write scopes, enforced by a git `pre-commit` hook
that refuses the commit rather than warning about it.

**How do you prove afterwards what it did.** An append-only audit log chained with HMAC-SHA256, a
chain verification function, and a guard that refuses to run in a mode where the chain would not be
tamper-evident.

**What happens if one vendor disappears.** A dispatch layer that routes work across five model
backends, and a commit broker that serialises the git writes of parallel agents, removing
`.git/index.lock` collisions by construction rather than by retry.

**Stated precisely, because it matters:** this governs development agents on a workstation. It is
not a multi-tenant inference platform in production, and I do not present it as one.

---

## 3. Tools that refuse

Four small programs, one idea: a tool that produces something should be able to refuse. Not warn,
not log, not colour a line orange. Refuse, with a non-zero exit code, naming the control that
failed.

The one worth running is the anti-invention gate. It compares a derived document against its
source of truth, extracts every number and every proper noun from both, and exits 1 on anything
that appeared out of nowhere. The example data ships with it:

    cd evidence/gates
    python3 anti_invention.py example/source_of_truth.md example/derived_with_invention.md --banals Meridian

    SIGNAL  derived_with_invention.md
            nombres absents du socle : 90000
            noms absents du socle    : kubernetes

An inflated throughput figure and a deployment claim that was never made, both caught. The honest
derivation of the same source passes.

The others: a document builder that runs eleven layout controls before writing a single byte and
writes nothing if one fails, a prober that calls the real endpoints of five applicant tracking
systems because one of them answers 200 on identifiers that do not exist, and a proof register
that checks its own claims still point at tests that exist and strings that are still in the code.

These come from a workbench I built for my own job search. The data that went through them stays
private; the machinery is here, with the personal parts turned into parameters. Details in
[`evidence/gates/`](evidence/gates/).

---

## 4. Writing, in two languages

[labo-llm.fr](https://labo-llm.fr) is a sourced corpus on large language models that I write and
publish alone. **149 articles in French and 149 in English**, in exact mirror. Each claim carries
its source, hypotheses are separated from facts, and negative results are archived like positive
ones.

---

## What is not in this repository, and not in my experience

I would rather you read this here than find it in an interview.

- **No Kubernetes in production, no Helm, no public cloud.** Not here, and nowhere in my
  experience. What does exist, in the platform this bench measures, is containerisation: a Docker
  image on a slim base running as a non-root user, dependencies installed from a lock file carrying
  **1,311 pinned hashes**, a compose file with a health probe, and **4,005 lines of step-by-step
  deployment runbook** down to DNS records and the first production cutover. That is a Docker host,
  not a cluster, and the two are not the same skill. I would rather name the difference than blur
  it.
- **No GPU orchestration, no inference platform at scale.** The bench runs on one machine.
- **No production traffic.** One application of mine is live, with two users. No on-call, no
  incident load, no multi-tenant scale.
- **No external client reference.** My delivery record is inside one employer and on my own time.

These are the four things a serious reviewer will look for. They are absent, and the plan to close
the first of them is real work, not a line on a CV.

---

## Who I am

Systems and integration engineer, eight years in regulated banking on one recurring job: taking a
solution designed elsewhere and making it hold inside a real enterprise environment. Today I am
technical owner of a multi-tenant provisioning platform at the infrastructure arm of a French
banking group.

Since March 2026 I have designed and shipped eight software products on my own, in Python and
TypeScript, among them an enterprise knowledge platform of 284,347 lines of Python with hybrid
retrieval, per-connector access control and agent access over the Model Context Protocol.

- Site: [labo-llm.fr](https://labo-llm.fr)
- LinkedIn: [matteo-l-35116a17a](https://www.linkedin.com/in/matteo-l-35116a17a/)
- Location: Nantes, France. Open to roles worldwide, with the usual work authorisation caveat
  outside the European Economic Area.

---

## Licence

MIT. See [LICENSE](LICENSE). You may take anything here and use it.
