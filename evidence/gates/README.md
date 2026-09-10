# Tools that refuse

Four small programs, each built for a different job, all built on the same idea: a tool that
produces something should be able to refuse. Not warn, not log, not colour a line orange. Refuse,
with a non-zero exit code, and say which control failed.

They come from a job-search workbench I wrote for myself. The data that went through them, offers,
letters, salary expectations, is mine and stays private. What is here is the machinery, with the
personal parts made into parameters. Colleagues who watched it run asked for a copy, which is why
it is in a portfolio rather than in a drawer.

The comments are in French, the working language of the lab, while the rest of this repository is
in English. Stated rather than translated after the fact.

## `anti_invention.py`

Compares a derived document against its source of truth with a deliberately coarse lexical
heuristic, and exits 1 on a token the source does not carry.

Numeric tokens keep their sign, their decimal part and their unit, so `-10` differs from `10`,
`5.0` from `50`, and `5 MB` from `5 GB`. Thousands separators and the `k`/`M` multipliers are
normalised, so `48k`, `48,000` and `48 000` are the same key. Proper nouns are capitalised words
that are not sentence openers, which is why `--banals` exists.

The example directory ships a fictional datasheet and two documents derived from it. One is
honest. One inflates a throughput figure and adds a deployment claim that was never made:

    python3 anti_invention.py example/source_of_truth.md example/derived_ok.md --banals Meridian
    OK      derived_ok.md : aucun nombre ni nom propre absent du socle

    python3 anti_invention.py example/source_of_truth.md example/derived_with_invention.md --banals Meridian
    SIGNAL  derived_with_invention.md
            nombres absents du socle : 90000
            noms absents du socle    : kubernetes

**What it does not catch, and the tests that say so.** Being lexical, it misses a sentence that
contradicts the source without adding a token: *Scaling across nodes has been validated in
production* passes against a source stating there is no cluster. And it compares what a derivation
adds, never what it removes, so deleting a whole section of caveats is invisible to it. Both cases
are in `tests/test_anti_invention.py` as passing tests that assert the real behaviour: improving
the gate breaks them, which forces this paragraph to change at the same time.

Within its remit it over-reports rather than under-reports. For a gate that guards facts, a false
alarm costs a glance and a missed invention costs credibility.

## `build_document.py`

Writes a single-column OOXML `.docx` by hand, no library, from a Markdown source, and runs eleven
mechanical controls before writing: margins, body size, line spacing, absence of tables, absence
of headers and footers, declared document language, contrast ratio of every text colour, no empty
paragraph. If one fails, nothing is written.

`--controler-pdf` runs seven more on the exported PDF, including whether the extracted text starts
with the expected name, which is how you find out that a reader will parse the document in the
wrong order.

Set `NOM_ATTENDU` in the environment for that last one.

## `probe_job_boards.py`

Calls the public endpoints of six applicant tracking systems and records what actually answered.
Nothing here comes from memory: every URL is really called and the result is written down as it
came.

It exists because of one finding. SmartRecruiters answers HTTP 200 with `totalFound: 0` on an
identifier that does not exist, so a 200 there proves nothing. Greenhouse, Lever and Ashby return
a clean 404. A prober that trusted status codes would have reported open doors that are not there.

No target list ships with it: pass your own JSON file of `[name, field, ats, token]`.

## `proof_registry.py`

Reads a register of claims and checks the ones that can be checked. `[TESTED]` must cite a test
that still exists, `[INVARIANT]` must cite a string that is still in the code, `[OBSERVED]` must
carry a real date. `[DESIGN]` and `[KNOWN GAP]` are exempt by definition, and that is the point:
a format that forces you to write a proof you do not have manufactures false ones.

`PREUVES.md` in this directory is its own register, and it passes:

    python3 proof_registry.py
    10 énoncé(s) — 6 vérifiable(s) mécaniquement · TESTED 2 · INVARIANT 3 · OBSERVED 1 · DESIGN 2 · KNOWN GAP 2

It caught two dead test names in that register while I was writing it, which is the whole
argument for having it.

    python3 -m pytest -q evidence/gates/tests/
