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
took ten occurrences over six sessions. This extract keeps two of those levels, plus a rule that
the whole-block fallback applies only to a block whose every line is a path. That rule started as a
blacklist of section names, which two reviews broke on 2026-09-11 with four spellings it had never
heard of: `## Interdit`, a bare `INTERDIT :`, `<read>` and `<read-only>`. A blacklist admits by
construction everything it does not know, and the people writing these prompts are usually agents,
which vary the wording. It is a whitelist now, and `BLOCS_NON_INTERPRETABLES` in the tests carries
the six shapes as a table.

**Rules rather than patched cases.** A line the guard cannot classify refuses. A path under
`<interdit>` refuses even when a write rule covers it, which is how anyone naturally writes "you
may edit `src/ingestion/` except `secrets/`". And a `*` matches within one path segment; crossing a
directory is written `**`, it is not inferred.

**A permission has a form, and the form is not guessed.** Three writings, three meanings:

    src/foo/              a directory, and everything under it
    config/settings.json  that file, and nothing else
    reports/*.json        a match inside one path segment

The third line of that table used to be the first two at once. `config/settings.json` also
authorised `config/settings.json/evil.py`, because the path does start with
`config/settings.json/`, and nothing stops a directory from being named `settings.json`. A file
permission was silently a subtree permission. A directory now carries its trailing slash or it is
not a directory.

**A path containing a space is written between backticks, or it is refused.** The line was cut at
the first space, so `docs/my file.md` became the permission `docs/my`, which opens a whole subtree
the prompt never granted. An ambiguity in parsing was resolving into a *wider* permission. It now
refuses, and `` `docs/my file.md` `` is how you declare the file. A trailing comment in parentheses
still works, because a guard that refuses correct prompts is a guard that gets switched off.

**An interdiction the grammar cannot place refuses.** `## Interdit` beside an `<écriture>` section,
or `INTERDIT :` inside one, expresses an intention this parser cannot attach to anything. It used
to be skipped, which both lost the interdiction and, when paths followed the marker inside a
writing section, turned them into write permissions. That second case is the one the module
docstring calls the most persistent in service, ten relapses over six sessions: it had been closed
for the legacy format and was still open inside the structured grammar. Recognised and unplaceable
now means the perimeter is not established.

**A commit is not a list of destination paths.** `git diff --cached --name-only` detects renames and
prints only the destination, so an agent could move a forbidden file into an allowed directory and
the guard would see a legitimate create. Both reviews of 2026-09-11 found this independently, on the
same commit. The guard now reads `--name-status -z` and puts both sides of a rename through the
policy: for a permission gate, deleting and moving are writes like any other. `-z` came with it,
because without it git quotes and octal-escapes non-ASCII paths, and an accented filename inside the
perimeter was refused on its spelling.

## `audit_chain.py` : an append-only log you cannot quietly rewrite

Each event carries the SHA-256 of the previous record and an HMAC-SHA256 of its own canonical
serialisation. Modifying or reordering records, or deleting one that still has a successor, breaks
the chain, and `verify_chain` names the record.

**Neither the readers nor the writer speak in silence.** A line of the log that is not valid JSON
raises rather than being skipped: a view that omits what it could not read presents a partial
history as if it were whole, which in an audit trail is the wrong default. `verify_chain` always
detected that corruption, but nothing forced a caller through it before displaying a log.

**A failed `fsync` means the durability is unknown, not that nothing was written.** The call raises
`AuditDurabilityError`, and the bytes may already be in the page cache or on the filesystem. A
caller that retries can therefore produce two semantically identical events. That is the ordinary
semantics of a durability failure after a write, and it is written here because the alternative
reading, "the append definitely did not happen", is the one that costs you an event.

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

The key must be a regular file, and a symlink in its place is refused: a symlink substitutes a key
without changing the declared path. What is deliberately not checked is whether other accounts can
read the key. Permission bits carry no meaning on a Windows mount, and a check that refuses wrongly
on the author's own machine is a check that gets switched off. The property "someone else cannot
simply read the key" therefore rests on the workstation, not on this code.

Without a key the HMAC degenerates to a constant, and the chain proves only that nobody edited
it carelessly. The strict mode is therefore the default and it fails closed: no key means the
log refuses to be written and refuses to be verified, instead of producing an audit trail that
looks like evidence and is not.

**What this does not protect against, stated because it matters.** The key sits on the same
workstation as the agents. The chain is evidence against a careless agent, a partially persisted
or malformed tail, and a later edit by someone without the key. It said "a crashed write" until
2026-09-11, which was one word too broad: a crash that loses the last append entirely leaves a
valid prefix, and a valid prefix reads clean. That is the same limit as tail truncation, and it
has the same cause, no external commitment to the head. It is not evidence against me. A log signed with a key
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
