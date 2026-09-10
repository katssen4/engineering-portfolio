# Agent governance

Two mechanisms from the harness I develop through, reduced to what can be published and
shipped with the tests that show them refusing.

**These are extracts, not the harness.** The system in service is 32,159 lines across 126 Python
files; the two mechanisms below come to about 500 in reduced form. It also carries nineteen domain
validators encoding my own architecture rules, and a dispatch doctrine. None of that is here, and none of it needs to be: the rules are what took
time to earn, and the mechanisms below are the part anyone could rebuild in a weekend. What
they are worth reading for is not novelty. It is that they exist, they refuse, and the refusal
runs in CI.

    python3 -m pytest -q evidence/agent-governance/tests/     # 31 tests

## `scope_guard.py` : an agent commits only what its prompt declared

Every worker prompt carries a `<scope>` block naming the paths it may write. Before a commit,
the guard reads that block, compares it to the staged files, and exits 1 on anything outside.
It exits 2 whenever the perimeter cannot be established, and there are four ways for that to
happen: no `<scope>` block, several of them, a structured scope carrying `<lecture>` or `<interdit>`
but no writing section, and an enumeration of staged files that failed. The command line refuses the
same way when given no source of staged files at all. One sentence covers all four: not being able
to determine a perimeter never grants one.

    python3 scope_guard.py --prompt example/prompt_avec_scope.md \
        --staged src/ingestion/connectors/metrics.py src/auth/session.py

    [scope_guard] COMMIT REFUSE : 1 fichier(s) hors perimetre
        src/auth/session.py

**The bypass this extract reproduced on its first run.** The example prompt authorises
`reports/W3_<TS>.json`, a report whose name carries a timestamp not known in advance. To an XML
parser, `<TS>` is an opening tag that never closes, so the block fails to parse. A naive guard
then falls back to reading the whole `<scope>` block, which also contains `<lecture>` and
`<interdit>`, and treats those paths as write permissions. The guard passes exactly what it was
meant to block, silently.

That is why the version in service carries five extraction levels instead of one. Each was added
after an agent found a prompt shape the previous level could not see; the most persistent case
took ten occurrences over six sessions. This extract keeps two of those levels, plus a rule that the whole-block fallback never applies
to a scope that carries any known section at all. The case is locked
down by `test_le_bloc_entier_n_est_pas_un_perimetre`, which fails if the fallback ever returns.

## `audit_chain.py` : an append-only log you cannot quietly rewrite

Each event carries the SHA-256 of the previous record and an HMAC-SHA256 of its own canonical
serialisation. Modifying or reordering records, or deleting one that still has a successor, breaks
the chain, and `verify_chain` names the record.

**Truncating the tail does not.** A valid prefix of a chain is a valid chain: nothing inside the
file says the removed records ever existed. Detecting that needs a commitment to the expected head
stored where an attacker cannot truncate it, which this extract does not have. Since deleting the
most recent actions is the likeliest thing anyone would want, that limit ships as a passing test
rather than as a footnote. A missing or emptied log reads as clean for the same reason.

Writes take an exclusive `flock` over read-then-append, so two agents in parallel cannot read the
same `prev_hash` and diverge. When the lock cannot be taken, or the platform has no file locking at
all, the write is refused: a key present does not compensate for a critical section absent. Four
processes appending ten records each, verified as one linear chain, ships as a test.

`append-only` here is a discipline of this writer, not a property of the filesystem. Another
process with write permission can still truncate or replace the file. What the chain gives is
detection of some of that, named precisely above.

Without a key the HMAC degenerates to a constant, and the chain proves only that nobody edited
it carelessly. The strict mode is therefore the default and it fails closed: no key means the
log refuses to be written and refuses to be verified, instead of producing an audit trail that
looks like evidence and is not.

**What this does not protect against, stated because it matters.** The key sits on the same
workstation as the agents. The chain is evidence against a careless agent, a crashed write, and
a later edit by someone without the key. It is not evidence against me. A log signed with a key
its own author holds proves integrity, not innocence, and the two get confused often enough that
it is worth writing down. `test_en_mode_degrade_une_modification_passe_le_hmac` ships that limit
as a passing test.

## The question a security reviewer asks first

A client-side hook does not stop an agent with a shell. `git commit --no-verify` skips it, and
`.git/hooks/` is writable by whoever can write the repository. The guard is therefore no barrier
against a hostile agent, and presenting it as one would be wrong.

What it is: a control against an agent that drifts, which is the failure that actually happens. An
agent asked to touch the ingestion connectors and reaching into the authentication module is almost
never adversarial, it has lost the thread. The guard catches that, names the file, and stops the
commit. In the harness in service the write path is narrower still, since agents commit through a
broker instead of calling git themselves, but that broker is not shipped here and I will not lean
on a guarantee you cannot inspect.

## What is not here

The commit broker that serialises parallel git writes, the nineteen domain validators, the
dispatch layer across model backends, and the doctrine documents. The first is a queue and would
add nothing to this page. The rest is the accumulated judgement of several hundred sessions, and
it is the part I keep.
