# What outside review found, and what now holds it

Six outside reviews and two internal adversarial audits have run against this repository
since 2026-09-10. The README says the method is: reproduce the finding, pin it with a test,
then fix it or write the limit down. This file is that claim's evidence, one row per finding.

Read it as a register, not a changelog. A changelog says what changed. This says **what still
stops the same mistake from coming back**, and names the thing a reader can run.

Each row carries one of three anchors:

    [test]   a named test in evidence/**/test_*.py. tools/verify.py checks it still exists.
    [check]  a control in tools/verify.py, quoted by a distinctive fragment of its output.
    [doc]    a wording correction. Nothing executable pins it, and saying so is the point:
             most documentation drift cannot be tested, which is why it drifts.

**What this file cannot prove.** That the list is complete. Nothing here detects a finding
that was received and quietly dropped, and no mechanism could: the reviews are outside the
repository. The rows are checkable one by one; their number is a claim, and it is mine.

---

## 2026-09-10 — outside review, first pass

| Finding | Anchor |
|---|---|
| `is_regression` returned False when the metric dropped past the delta, significance was required, and no p-value existed. An absence of proof read as a proof of absence, on the one leg of the module that still failed open. | [test] `test_significance_required_but_no_p_value_refuses_to_gate` |
| The branch that concludes without needing a p-value had no test, so the fix above could have closed the gate permanently without anyone noticing. | [test] `test_pas_de_p_value_mais_pas_de_chute_ne_refuse_pas` |
| The README claimed every number on the page was recomputed. False for counts describing systems not shipped here. | [doc] the three families, recomputed, consistency-checked and declared, are named on the page |
| Two comments announced an uningested corpus and a stubbed step, contradicted by the lock that shipped beside them. | [doc] corrected, with the reason written in place |

## 2026-09-10 — two outside reviews, on `5c161c6`

| Finding | Anchor |
|---|---|
| `verify.py` read the control score out of the decision file instead of recomputing it. The central claim of the fine-tune section was a value it had been handed. | [check] `nDCG@10 recomputed from the run files` |
| Four numeric collisions in the anti-invention gate: `5.0` keyed as `50`, `1.20` as `120`, `-10` as `10`, `5 MB` as `5 GB`. | [test] `test_un_decimal_n_est_pas_l_entier_sans_le_point`, `test_le_signe_entre_dans_la_cle`, `test_l_unite_entre_dans_la_cle` |
| Two structural false negatives of the same gate, which cannot be closed by this design. Shipped as passing tests rather than hidden. | [test] `test_limite_une_affirmation_sans_chiffre_ni_nom_propre_passe`, `test_limite_une_omission_de_reserve_passe` |
| `evidence/README.md` said 32 checks while the root README said 34. A number written twice drifts. | [check] `evidence/README.md states no check count of its own` |
| The prober queries six systems, the page said five. | [test] `test_les_six_familles_sont_declarees` |

## 2026-09-10 — internal adversarial audit, not a review

Conducted by trying to break the repository rather than by reading it: lock altered, decision
doctored, run truncated. The first two attacks were caught. The third was not.

| Finding | Anchor |
|---|---|
| A damaged TREC file killed `verify.py` on a Python traceback before its first line of output, which reads as a silence rather than as a failure. | [check] `both TREC files parse cleanly` |
| Judged queries absent from the run file were not checked at all. | [check] `every judged query appears in the run file` |
| The memory peak printed on the page was neither recomputed nor declared. It is now confronted with the run narrative that carries it. | [check] `MiB on the page is the one in the run narrative` |
| The proof register's `[INVARIANT]` anchors proved a string existed, not that a guard worked. Ten claims moved to `[TESTED]`. | [check] `the proof register of evidence/gates passes its own check` |

## 2026-09-10 — outside reviews v2 and v3

| Finding | Anchor |
|---|---|
| **The costliest one.** The "4,005 runbook lines" added a v1 and the v2 that declares it replaced. Double count; the real figure is 3,310. It was on seven CV documents outside this repository. | [doc] corrected here and at the source |
| The fine-tune's blinding was presented in a way that suggested the treated score was out of reach. The treated run and the judgements both ship, so it is publicly computable. The blinding is procedural. | [doc] named as procedural on the page |
| Absolute phrasings that were false: "every artefact is a file from a real run", "nothing in this directory is a summary written for a reader". | [doc] both removed |
| The gap localisation reads the shipped diagnostic, it does not rebuild it query by query. The page said otherwise. | [check] `read from the diagnostic, not recomputed per query` |
| A path quoted in a docstring did not exist in the repository. | [check] `every internal path quoted in the docs exists` |

## 2026-09-11 — outside reviews v4 and v5, on `d4dd6ab`

Two independent reviewers audited the same commit and found the same P0 by the same route.

| Finding | Anchor |
|---|---|
| **P0.** `git diff --cached --name-only` detects renames and prints only the destination. An agent moving a forbidden file into an allowed directory removed it from the perimeter, and the guard called the commit conforming. | [test] `test_un_renommage_depuis_un_chemin_interdit_est_refuse` |
| The same fix must not refuse a rename whose two sides are both allowed, or the guard becomes unusable and gets bypassed on principle. | [test] `test_un_renommage_dans_le_perimetre_passe` |
| Without `-z`, git quotes and octal-escapes non-ASCII paths, so an accented filename inside the perimeter was refused on its spelling. | [test] `test_un_chemin_accentue_du_perimetre_n_est_pas_refuse_a_tort` |
| **P0.** `coll_baseline.get(primary_metric, 0.0)` turned an absent baseline into a baseline of zero, so any current score looked like an improvement. | [test] `test_a_hash_valid_but_incomplete_lock_cannot_gate` |
| A lock can be hash-valid and semantically unusable. Integrity and validity are different questions. | [test] `test_an_incomplete_lock_is_still_hash_valid` |
| The whole-block fallback was gated by a blacklist of section names, which admitted four spellings it had never heard of. Replaced by a whitelist. | [test] `test_un_bloc_non_interpretable_refuse_au_lieu_d_autoriser` |
| `<interdit>` was only excluded from permissions, never applied as a refusal. | [test] `test_un_chemin_interdit_refuse_meme_sous_une_autorisation` |
| `*` crossed `/` for explicit globs, having been fixed for placeholders only. | [test] `test_un_joker_ne_franchit_jamais_un_separateur` |
| Both log readers called a resolver that does not exist in this reduced extract, so any call without an explicit path died on a `NameError`. | [test] `test_read_events_exige_un_chemin` |
| The readers skipped unreadable lines in silence. A view that omits what it could not read presents a partial history as whole. | [test] `test_un_lecteur_ne_saute_pas_une_ligne_corrompue_en_silence` |
| The prober returned 0 offers on 403, 429, 500, timeout and DNS failure, while its own counting function refused to invent a zero. | [test] `test_une_non_reponse_ne_devient_jamais_zero_offre` |
| Its docstring claimed it signalled instructions addressed to an agent. It counts openings and does not read posting text. | [test] `test_le_module_ne_promet_pas_de_signaler_les_injections` |
| `Nantes`, `Ariane`, `Alex` and `Doe` were hardcoded in the anti-invention gate's stopword list, so an invented location passed unremarked. | [test] `test_un_fait_du_dossier_n_est_pas_un_mot_structurel` |
| A prefixed currency was not bound to its number: `$5` and `€5` had the same key. | [test] `test_deux_montants_ne_se_confondent_pas_par_leur_seul_chiffre` |
| The proof register only read bullets starting `- ` at column zero, so a purely typographic change could drop a claim. | [test] `test_toutes_les_formes_de_puce_entrent_dans_le_registre` |
| An HMAC key replaced by a symlink was read. Permission bits are deliberately not checked, and that limit is written rather than guessed. | [test] `test_une_cle_remplacee_par_un_lien_symbolique_est_refusee` |
| The diagnostic was never confronted with the 310 queries of the decision, so a truncated one passed. | [check] `the diagnostic covers` |
| Two TREC documents at the same rank made the verifier invent a tie-break, in a file whose entire subject is a fine-tune blocked over tie-breaking. | [check] `duplicate rank` |
| A run query absent from the judgements took part in nothing and passed unremarked. | [check] `the run file holds no query the qrels do not judge` |
| `verify.py` announced five steps in its docstring while running eight. | [check] `the docstring lists the` |
| Nothing stopped the README from calling a mechanism unshipped once its evidence existed. The previous commit had failed silently on exactly that rewrite. | [check] `nothing the README calls unshipped has a file in the repository` |

## 2026-09-11 — outside review v6, on `c341f1d`

Eleven findings, nine real. Two report as open a control present in the commit they audit:
the diagnostic cardinality and the duplicate-rank refusal, both rows in the section above.
Four of the nine exist because of the previous pass's fixes.

| Finding | Anchor |
|---|---|
| **P0.** A path was cut at its first space, so `docs/my file.md` became the permission `docs/my`, a *wider* prefix opening a subtree the prompt never granted. A parsing ambiguity was resolving into privilege. | [test] `test_un_chemin_avec_espace_ne_devient_pas_un_prefixe_plus_large` |
| Unquoted, the guard cannot know where the path ends, so it refuses instead of truncating. | [test] `test_un_chemin_nu_avec_espace_refuse_au_lieu_d_etre_tronque` |
| The hardening must not close the ordinary `- src/foo/ (comment)` form, or the guard gets switched off. | [test] `test_un_commentaire_entre_parentheses_reste_lisible` |
| **P0.** `config/settings.json` also authorised `config/settings.json/evil.py`. Nothing stops a directory from being named `settings.json`, so a file permission was silently a subtree permission. | [test] `test_les_trois_formes_de_permission_se_distinguent` |
| Scope blocks were counted in two passes, the first case-sensitive, so `<scope>` followed by `<SCOPE>` left the ambiguity undetected. | [test] `test_deux_scopes_de_casse_differente_sont_ambigus` |
| An interdiction written outside the structured grammar was skipped. **Found wider than reported while reproducing it**: `INTERDIT :` inside an `<écriture>` section turned the paths after it into write permissions, which is the case the module calls its most persistent in service, ten relapses over six sessions. | [test] `test_une_interdiction_hors_grammaire_refuse_le_perimetre` |
| The same case, on the exact shape a previous test had frozen as merely skipped. | [test] `test_une_interdiction_dans_la_section_d_ecriture_refuse_le_perimetre` |
| **P0.** Every decision in the gate is an inequality, and every inequality against NaN is False. A NaN metric read as "did not drop past the delta", a NaN p-value as "not significant". | [test] `test_une_valeur_non_finie_ne_peut_pas_produire_de_verdict` |
| And the witness, because a guard that refuses everything is not a guard. | [test] `test_les_valeurs_valides_produisent_toujours_un_verdict` |
| **P0.** An unsealed collection, and a regenerable corpus present with a drifted hash, both let `main` reach a verdict. The inspection helper's permissiveness was inherited by the gating path. | [test] `test_la_politique_d_arbitrage_distingue_les_quatre_etats` |
| The drifted-corpus case is the only one that makes a verdict **wrong** rather than absent: baseline on one dataset against current on another, with the difference credited to the system. | [test] `test_un_corpus_derive_est_un_probleme_de_comparabilite_pas_d_integrite` |
| `stat_test` was required present, never required supported. An unknown name blew up later on a `KeyError`, a crash rather than a refusal. | [test] `test_un_stat_test_non_supporte_rend_le_verrou_ingatable` |
| `--update-baseline` resealed without validating, so the sanctioned way to move the baseline could stamp an unusable lock as official. | [test] `test_le_reseal_refuse_de_signer_un_verrou_ingatable` |

---

## Two defects this machinery caught on its own

Neither was reported by anyone. Both were introduced while fixing the rows above, and both
were caught before the commit left the working tree. That is the part of the method that does
not depend on someone else looking.

- A rank guard added to the TREC parser required ranks starting at 1. The shipped run file
  starts at 0, and the check declared all 310 queries malformed on its first execution. A
  convention assumed instead of read.
- A `@dataclass` added to a module that `verify.py` loads by path killed `dataclasses` with
  `AttributeError: 'NoneType' object has no attribute '__dict__'`, because the module was not
  registered in `sys.modules` before execution. The verifier lost its first two sections to a
  traceback, which is exactly the failure mode row three of the internal audit describes.
