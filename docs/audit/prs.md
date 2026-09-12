# Branches ready as pull requests (2026-09 audit)

All branches are on `r0ny123/purepdb`. Branch names carry a `-clean` or
`audit/` prefix because the first push was refused for the author email the
session was configured with; the replayed branches carry the GitHub noreply
identity and identical trees. Base is upstream `main` at e978f3a
(0.5.0) unless noted. Each was gated on the full suite, `ruff check`,
`ty check`, and a 2000-input fuzz pass before every commit.

## `audit/fixes-2026-09` — correctness fixes from the corpus audit

Title: *read what MSVC writes: S_INLINESITE2, separated code, the fused
annotation cursor, stripped files, and the large block sizes*

What it fixes, each with a test and a changelog entry:

1. **Inline sites on MSVC output.** MSVC writes `S_INLINESITE2` (48608 of
   48642 sites in python312.pdb; 0.5.0 saw 34). The fused
   `ChangeCodeLengthAndCodeOffset` length does not move the cursor — the old
   rule put 5582 of 79187 ranges past their procedure — and
   `ChangeCodeOffsetBase n` names the procedure's n'th `S_SEPCODE` chunk
   (PGO cold code), which used to drop the site as "no code". **Moves
   addresses** on every rust-lld/clang file's second-and-later ranges; the
   changelog says so.
2. **Stripped PDBs** (`/PDBSTRIPPED`, every Microsoft public symbol file)
   produced no `diagnose()` warning. DBI Flags and BuildNumber are read;
   `Diagnostics.private_symbols_stripped`, `linker_version`; three warnings.
3. **MSF block sizes 8192/16384/32768** accepted (huge PDBs were refused).
4. **Directory memory bomb**: sum of stream sizes must fit the file.
5. **S_LPROC32_DPC/_DPC_ID** are procedures (cvinfo.h puts them on PROCSYM32).
6. **DEBUG_S_LINES BlockSize** floored at the bytes read (no re-reading
   entries as headers).
7. **Unnamed inline sites** counted and explained (VS2015 decorated ids;
   missing IPI stream).
8. Validator: 13 checks (was 9), llvm crashes and its S_TRAMPOLINE/inlinee
   rendering quirks handled, `\x1c` in section names, S_INLINESITE2 skipped
   with a note; OMAP check follows Win7 export stubs → 0 far misses on real
   BBT output; fuzzer `--seed-dir`.

Evidence: 251 real PDBs agree with llvm-pdbutil on every comparable check
(python.org 2.7–3.14 x64/x86/arm64, node, symbol-server Win7/10/11 and XP,
self-built clang/lld/rust); OMAP verified against six symbol-server images;
trampoline targets verified against `jmp rel32` in sqlite3.dll.

## `perf/hot-paths` — measured speedups, identical output

See `docs/audit/perf.md` on that branch for before/after per operation and
file. Output snapshots are byte-identical to the unmodified parser on every
fixture and corpus file (inline sites excepted where main is known-wrong).

## `pr53-clean` = `fix-correctness-audit` (PR #53) + one commit

Fast-forward of the PR head. To update the PR: `git push origin
pr53-clean:fix-correctness-audit` (a refspec push this session was not
allowed to make). Per the review in `pr-review.md`: DBI overrun clamps and is diagnosed
(`Diagnostics.dbi_overrun`), negative sizes still raise; C13 zero padding is
not damage; CLI test for the C13 warning; the coordinate-space test pins its
fix with a damaged End. Merge after #52 (one keep-both conflict hunk).

## `diagnose-single-pass` (PR #52) — unchanged, merge as is

Counts proven identical on all fixtures.

## `pr59-clean` = `release/modernize-release-workflow` (PR #59) + one commit

Fast-forward of the PR head; `git push origin
pr59-clean:release/modernize-release-workflow` updates the PR. The Python
floor bump is reverted here (it was an unrelated breaking change
riding a tooling PR) and lives on its own branch:

## `python-3.12-floor-clean` — new, one commit from main

`requires-python >=3.12`, CI matrix, ruff target, docs, `Removed` entry.
Tested on 3.12. Merge whenever the ecosystem decision is taken.

## dependabot #56/#57/#58 — merge as is

`ruff check`, `ty check` and `make package` are clean under the bumped
versions.
