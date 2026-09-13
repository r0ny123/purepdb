# Shared plan — purepdb audit (started 2026-09-12)

Coordinator: main session. Tracks run in git worktrees, one branch each,
atomic commits. This file is the coordination point; every agent appends to
`LOG.md` beside it (findings, decisions, benchmarks, dead ends).

| track | worktree | branch | owner | status |
|---|---|---|---|---|
| research log | /home/user/purepdb | audit/research-log | main | done: LOG.md, SUMMARY.md, prs.md, corpus.md, perf.md, pr-review.md |
| corpus + fetch scripts | /home/user/purepdb (tools/) | audit/research-log + audit/fixes-2026-09 | agent-corpus | done: 421 PDBs, tools/fetch_corpus.py |
| perf | /home/user/wt/perf | audit/perf-hot-paths (11 commits on the fixes) | agent-perf | done, pushed |
| PR review (#52 #53 #59) | /home/user/wt/review | pr-review.md; pr53-clean, pr59-clean, python-3.12-floor-clean | agent-review + main | done, pushed |
| fixes | /home/user/wt/fixes | audit/fixes-2026-09 (was fix/audit-2026-09) | main | 12 commits, pushed |
| fuzz | scratchpad | - | main (background) | done: 19.7k inputs clean |

Corpus lives at /home/user/corpus (NOT in the repo; not redistributable in
general). Manifest with provenance: /home/user/corpus/MANIFEST.md, mirrored
into docs/audit/corpus.md.

Rules: python only, zero runtime deps, tests+lint+fuzz before commit,
never `ruff format`, groundtruth counts change only deliberately.
