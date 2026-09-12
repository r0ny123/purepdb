# Shared plan — purepdb audit (started 2026-09-12)

Coordinator: main session. Tracks run in git worktrees, one branch each,
atomic commits. This file is the coordination point; every agent appends to
`LOG.md` beside it (findings, decisions, benchmarks, dead ends).

| track | worktree | branch | owner | status |
|---|---|---|---|---|
| research log | /home/user/purepdb | audit/research-log (was research/repo-audit) | main | active |
| corpus + fetch scripts | /home/user/purepdb (tools/) | research/repo-audit | agent-corpus | starting |
| perf | /home/user/wt/perf | perf/hot-paths | agent-perf | starting |
| PR review (#52 #53 #59) | /home/user/wt/review | (detached, notes only) | agent-review | starting |
| fixes | /home/user/wt/fixes | audit/fixes-2026-09 (was fix/audit-2026-09) | main | 12 commits, pushed |
| fuzz | scratchpad | - | main (background) | running |

Corpus lives at /home/user/corpus (NOT in the repo; not redistributable in
general). Manifest with provenance: /home/user/corpus/MANIFEST.md, mirrored
into docs/audit/corpus.md.

Rules: python only, zero runtime deps, tests+lint+fuzz before commit,
never `ruff format`, groundtruth counts change only deliberately.
