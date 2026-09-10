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
| 4,005 lines of deployment runbook | three deployment documents of the same platform | `wc -l README_DEPLOY.md RUNBOOK_DEPLOY.md RUNBOOK_DEPLOY_v2.md` | 55 + 695 + 3255 | 2026-09-10 |
| 149 French and 149 English articles | the published corpus of labo-llm.fr, drafts excluded | `find src/content/articles -type f \( -name '*.md' -o -name '*.mdx' \) -not -path '*/en/*' -not -path '*/prive/*' \| wc -l`, then the same for `en/` | 149 and 149 | 2026-09-09 |
| 5,572 relevance judgements | the seven TREC judgement files of the bench | `wc -l corpus/qrels/*.trec` | 5572 | 2026-09-09 |

## Two things worth knowing about these numbers

**A line count is a size, not a quality.** 284,347 lines of Python says the system is large. It
does not say it is well factored, and a reader is right to ask why a knowledge platform needs
that much. The test to source ratio on the same tree is 1.31, which is the number I would actually
defend. I keep the line count because removing it would look like hiding it.

**The article counts are a repository measure, not an editorial one.** The tree holds 332 files;
298 are published and 34 are drafts marked `draft: true`, none of which leave the private
directory. The README says 149 and 149 for that reason, and not 332.
