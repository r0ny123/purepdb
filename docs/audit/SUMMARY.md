# purepdb audit, 2026-09-12 — summary

Scope: upstream `danielplohmann/purepdb` and the fork `r0ny123/purepdb`,
both at 0.5.0 (e978f3a). Everything below was measured; the running record
is `LOG.md`, the corpus `corpus.md`, the PR review `pr-review.md`, the
performance track `perf.md` (on `perf/hot-paths`), and the branch-to-PR map
`prs.md`.

## Repo state

- Fork `main` == upstream `main`. 0 open issues upstream. 6 open PRs: #52,
  #53, #59 (all from the fork) and three dependabot bumps. Reviewed
  (`pr-review.md`); #53 and #59 improved on `pr53-clean` / `pr59-clean`.
- Baseline: 588 tests (AGENTS.md said 583), lint clean, fuzz clean.

## Corpus (rebuildable with `tools/fetch_corpus.py`)

421 PDBs + 6 PE images, 3.1 GB: python.org 2.7–3.14 (VS2008 → VS2022; x64,
x86, arm64; PGO), node v22 (355 MB), Firefox xul.pdb (1.93 GB), Microsoft
symbol-server files (Win7/10/11 and XP, stripped, five with real OMAP tables
and their matching images), 16 clang-cl/lld-link and 10 rustc builds made
here, 168 corrupted derivatives.

## Bugs found and fixed (`audit/fixes-2026-09`, 15 commits)

1. **MSVC inline sites were mostly invisible and partly misplaced.** MSVC
   writes `S_INLINESITE2` (python312.pdb: 48608 of 48642 sites; 0.5.0 saw
   34). The fused `ChangeCodeLengthAndCodeOffset` length does not move the
   cursor: 0.5.0's rule put 5582 of 79187 ranges past their procedure, the
   corrected rule 0. `ChangeCodeOffsetBase n` selects the n'th `S_SEPCODE`
   chunk (PGO cold code); 21 of 103 sites in `_bz2.pdb` were dropped for it.
   The 0.5.0 note that called llvm-pdbutil's cursor wrong is reversed.
2. **Stripped PDBs gave no `diagnose()` warning** (every Microsoft public
   symbol file). DBI Flags + BuildNumber now read; three new warnings;
   `linker` line in the CLI.
3. **Block sizes 8192/16384/32768 refused** (files past a few GB).
4. **Directory memory bomb**: stream sizes must sum within the file.
5. `S_LPROC32_DPC/_DPC_ID` are procedures; `S_COMPILE2` (VS2008, and
   link.exe's import-library modules) feeds `compile_info()`.
6. `DEBUG_S_LINES` BlockSize floored at the bytes read.
7. Unnamed inline sites (VS2015 decorated ids: 5802/6554 in `_hashlib.pdb`)
   and a missing IPI stream are now counted and explained.
8. `diagnose()` no longer materialises every inline site to count them
   (xul.pdb: 11.4 GB → 7.2 GB RSS).

## Verification

- `dev/validate_against_llvm.py` now runs 13 checks (data, thread-locals,
  thunks, trampolines added) and copes with three llvm-pdbutil limits found
  on the corpus (crash on XP files, thunk offset printed as trampoline
  target, 32-char inlinee names, `\x1c` in section names). **257 of 257
  corpus PDBs agree on every check.**
- OMAP translation verified for the first time against genuine BBT output:
  Win7 kernel32/ntdll/user32 with their images, 0 far misses once the
  harness reads Win7's export stubs. Untranslated counterfactual 0/3857.
- Trampoline targets verified against `jmp rel32` bytes in sqlite3.dll
  (348/348), pinned by a groundtruth test.
- Section-map reconstruction exact on every user-mode image (33 files),
  wrong only on kernel images linked with a small `/ALIGN` — documented.
- Fuzz: 13.7k fixture-seeded + 6k corpus-seeded (`--seed-dir`, new) inputs,
  168 corrupt files: no escaped exception.

## Performance (`audit/perf-hot-paths`, 11 commits on top of the fixes)

Output snapshots byte-identical to the fixes branch on every fixture and
corpus file. Best-of-N wall seconds, `tools/bench.py` (details in `perf.md`):

| file | op | before | after | speedup |
|---|---|---:|---:|---:|
| sqlite x64 (3 MB) | all listings | 1.19 | 0.30 | 4.0x |
| python314.pdb (21 MB, MSVC PGO) | diagnose | 6.69 | 0.88 | 7.6x |
| | functions | 1.77 | 0.27 | 6.6x |
| | all listings | 12.5 | 2.7 | 4.6x |
| ntkrnlmp.pdb (8.5 MB, stripped) | diagnose | 1.36 | 0.22 | 6.3x |
| node.pdb (355 MB) | functions | 21.6 | 3.5 | 6.2x |
| | diagnose | 107 | 30 | 3.6x |
| | all listings | 193 | 61 | 3.2x |
| xul.pdb (1.93 GB) | diagnose | 954 (11.4 GB) | 152 (7.0 GB) | 6.3x |

How: one `unpack_from` per record header and kind-filtered walks; a struct
per fixed record portion; one walk per module stream for `functions()` and
`diagnose()`; contiguous block runs read as single slices; positional IPI
counting; slotted `Line`/`InlineFunction`/`RawRecord`; per-file and
per-segment lookups hoisted out of the line loop. Not done (measured, see
`perf.md`): mmap in `PDB.open`, and streaming the largest modules to cut
xul's 7 GB peak further.

## What remains

- Stripped files that keep procs (Win10/11) get no note beyond the CLI's
  `linker` line — fine, but a `Diagnostics` reader has to look at the flag.
- No `/DEBUG:FASTLINK`, `_ST`-era (VS2003) or managed PDB in the corpus;
  nothing here can produce one.
- XP OMAP pairs unverified (no matching images obtainable).
- xul.pdb: diagnose is down to 152 s; the 7 GB peak (1.9 GB of it the file
  itself) is the next target — mmap in `PDB.open`, streaming the largest
  module streams.
- Two PR heads (#53, #59) need a refspec push this session could not make:
  `git push origin pr53-clean:fix-correctness-audit` and
  `git push origin pr59-clean:release/modernize-release-workflow`.
