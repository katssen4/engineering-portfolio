# Agent governance

Two mechanisms from the harness I develop through, reduced to what can be published and
shipped with the tests that show them refusing.

**These are extracts, not the harness.** The system in service is roughly 3,000 lines across
126 Python files, plus nineteen domain validators that encode my own architecture rules and
a dispatch doctrine. None of that is here, and none of it needs to be: the rules are what took
time to earn, and the mechanisms below are the part anyone could rebuild in a weekend. What
they are worth reading for is not novelty. It is that they exist, they refuse, and the refusal
runs in CI.

    python3 -m pytest -q evidence/agent-governance/tests/     # 16 tests

## `scope_guard.py` — an agent commits only what its prompt declared

Every worker prompt carries a `<scope>` block naming the paths it may write. Before a commit,
the guard reads that block, compares it to the staged files, and exits 1 on anything outside.
A prompt with no declared scope exits 2, not 0: a missing perimeter is not permission to write
anywhere, it is a perimeter that cannot be checked.

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
took ten occurrences over six sessions. This extract keeps two of those levels and a rule that
the whole-block fallback never applies when an `<écriture>` tag is present. The case is locked
down by `test_le_bloc_entier_n_est_pas_un_perimetre`, which fails if the fallback ever returns.

## `audit_chain.py` — an append-only log you cannot quietly rewrite

Each event carries the SHA-256 of the previous record and an HMAC-SHA256 of its own canonical
serialisation. Modify an entry, delete one, reorder two, and `verify_chain` names the offending
event. Writes take an exclusive `flock` over read-then-append, so two agents running in parallel
cannot read the same `prev_hash` and diverge.

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

## What is not here

The commit broker that serialises parallel git writes, the nineteen domain validators, the
dispatch layer across model backends, and the doctrine documents. The first is a queue and would
add nothing to this page. The rest is the accumulated judgement of several hundred sessions, and
it is the part I keep.
