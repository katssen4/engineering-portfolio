# Declared metrics

The numbers in the top-level README that describe systems **not shipped here**. They are not
recomputed by `tools/verify.py`, because the systems they measure are private. What is public is
the method: the exact command, the tree it ran against, and the date.

You can read the command and judge whether it measures what the sentence claims. You cannot run
it, and I would rather say that plainly than imply otherwise.

Every command excludes vendored and generated trees: `node_modules`, `venv`, `.venv`,
`site-packages`, `vendor/`, `*.min.js`, `.next/`, `dist/`, `build/`.

| Claim in the README | Scope | Command | Result | Measured |
|---|---|---|---:|---|
| 284,347 lines of Python | the knowledge platform, Python only, 990 files | `git ls-files projets/ariane \| grep -E '\.py$' \| grep -vE '<exclusions>' \| tr '\n' '\0' \| xargs -0 cat \| wc -l` | 284347 | 2026-09-09 |
| eight products, 448,866 lines | the eight applications, Python and TypeScript, 1,827 files | same command per project, summed | 448866 | 2026-09-09 |
| 1,311 pinned hashes | the deployment lock file of the containerised platform | `grep -c 'sha256:' requirements.lock` | 1311 | 2026-09-10 |
| 3,310 lines of deployment runbook | the deployment documents in force: the deployment README and the v2 runbook | `wc -l README_DEPLOY.md RUNBOOK_DEPLOY_v2.md` | 55 + 3255 | 2026-09-10 |
| 149 French and 149 English articles | the published corpus of labo-llm.fr, drafts excluded | `find src/content/articles -type f \( -name '*.md' -o -name '*.mdx' \) -not -path '*/en/*' -not -path '*/prive/*' \| wc -l`, then the same for `en/` | 149 and 149 | 2026-09-09 |
| 5,572 relevance judgements | the seven TREC judgement files of the bench | `wc -l corpus/qrels/*.trec` | 5572 | 2026-09-09 |
| 3 banking platforms, 200,000+ lines | the provisioning platform I am technical owner of | none: this is my job, not a repository | see below | ongoing |

## A figure this page carried wrong until 2026-09-10

The runbook line count read **4,005** and summed three documents. That was a double count: the
v2 runbook opens with `remplace: RUNBOOK_DEPLOY.md (S222, conservé pour traçabilité)`, so its
695-line predecessor is superseded and kept only as history. The figure in force is 3,310, and an
outside review caught the overlap by reading the file names. It has been corrected here, on the
page, and on every CV that carried it.

## The one number with no command at all

**3 banking platforms and more than 200,000 Cisco and Microsoft Teams lines.** No command produces
this. It is the scope of the job I hold, and a personal repository cannot measure an employer's
platform. It rests on my word, and the way to check it is a reference call, which I am happy to
have made. I keep it on the page because removing it would misrepresent what I do all day, and I
flag it here because a page about measurement should say which of its numbers are not measured.

The memory figures in section 1, **5,863.5 MiB peak against a 6,000 MiB ceiling**, are not in the
table above because they are not declared: they sit in `evidence/finetune-blocked/F1_finetune_run.md`
and `tools/verify.py` checks that the page and that file agree.

## Two things worth knowing about these numbers

**A line count is a size, not a quality.** 284,347 lines of Python says the system is large. It
does not say it is well factored, and a reader is right to ask why a knowledge platform needs
that much. The test to source ratio on the same tree is 1.31, which is the number I would actually
defend. I keep the line count because removing it would look like hiding it.

**The article counts are a repository measure, not an editorial one.** The tree holds 332 files;
298 are published and 34 are drafts marked `draft: true`, none of which leave the private
directory. The README says 149 and 149 for that reason, and not 332.
