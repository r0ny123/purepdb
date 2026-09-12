
## Coordinator log (main session)

### 2026-09-12 — context

- Fork `r0ny123/purepdb` main == upstream main (e978f3a, 0.5.0). Upstream has
  0 open issues (12 closed, all by the maintainer or r0ny123) and 6 open PRs:
  #52 (fork `diagnose-single-pass`), #53 (fork `fix-correctness-audit`), #59
  (fork `release/modernize-release-workflow`), and dependabot #56/#57/#58.
  None reviewed yet. Every earlier fork PR (#1–#16) is closed/merged upstream.
- Baseline on a clean tree: 588 tests pass (AGENTS.md says 583 — stale),
  ruff + ty clean, fuzz 2000 clean. llvm-pdbutil 18.1.3 is on PATH.
- Toolchains available for corpus building: clang-cl/lld-link 18, rustc
  1.94.1 with the three windows-msvc targets, msiextract, 7z. No MSVC, so
  nothing here can write an _ST-era or a /PDBSTRIPPED file; lld-link prints
  "ignoring /pdbstripped flag, it is not yet supported".

### Bugs found and fixed (branch fix/audit-2026-09)

1. **Stripped PDBs produced no warning.** A synthetic publics-only file with
   modules whose `sym_stream` is 0xFFFF gave `diagnose().warnings == []`.
   Every warning is reached by walking a module stream, so a file with none
   to walk was silent. Confirmed on all 14 Microsoft symbol-server files in
   the corpus: `Is stripped: true` per llvm-pdbutil; the Win7/XP ones have
   0 modules with symbols, the Win10/11 ones keep S_GPROC32/S_LPROC32 and
   S_SEPCODE (ntdll 7085…: 1484 procs, 6524 publics, 1110 S_SEPCODE) despite
   the flag. Fix reads DBI Flags bit 1 and BuildNumber; three new warnings.
2. **BuildNumber is a version only with bit 15 set.** XP files carry 0x3800
   and printed as "56.00" before the gate was added.
3. **Block sizes 8192/16384/32768 refused.** LLVM accepts them; link.exe
   writes them for PDBs past a few GB. Nothing in the corpus needs them yet
   (node.pdb 350 MB is 4096), but the refusal was a hard error on exactly the
   huge inputs.
4. **Directory memory bomb.** Each stream's block list is bounded by the
   directory, but nothing bounded the sum of stream sizes; a 4 MB file whose
   lists all name block 3 would allocate GBs in `read_stream`. Sum ≤
   num_blocks × block_size is a real invariant (checked: 0 duplicate blocks
   across all fixtures). Now MsfError.
5. **S_INLINESITE2 (0x115D)** undecoded — has an `invocations` u32 before the
   annotations. **S_LPROC32_DPC/_DPC_ID (0x1155/0x1156)** not in PROC_KINDS
   though cvinfo.h puts them on PROCSYM32. Both from the header, no corpus
   file carries them (python/node audit pending).
6. **DEBUG_S_LINES BlockSize below the bytes read** re-read line entries as a
   block header; now floored at header+entries.
7. Validator: llvm-pdbutil cuts inlinee names at 32 chars + "..."; four Rust
   std PDBs failed the inline-site check on that alone. Now shortened on both
   sides; 24/24 self-built files agree on every check.

### Observations, not bugs

- lld (lld-link and rust-lld) always writes DBI BuildNumber 14.11; MSVC
  writes its own (9.00 = VS2008 on Win7 files, 11.00, 14.14, 14.30).
- Microsoft's Win7-era and XP-era files carry OMAP (slot 4) *and* slot 10:
  kernel32 61182 entries, ntdll 67714, user32 38222, XP kernel32 42544, XP
  ntdll 37474. First genuinely BBT-processed files this project has had.
  Ground-truth check needs the matching PE images — requested from the
  corpus track (symbol server serves images by TimeDateStamp+SizeOfImage).

### 2026-09-12 — inline sites were wrong on MSVC output (fixed on fix/audit-2026-09)

Three findings from the python.org PDBs (MSVC 14.3x, PGO), all in one commit:

- **MSVC writes `S_INLINESITE2`**, not `S_INLINESITE`: 48608 of the 48642
  sites in python312.pdb. 0.5.0 reported 34. llvm-pdbutil 18 prints the
  record as a size and nothing else, so the reference could not have shown it.
- **The fused `ChangeCodeLengthAndCodeOffset` length does not move the
  cursor.** Four interpretations tested against proc/chunk sizes on
  python312.pdb (79187 ranges): advance-after-fused → 5582 ranges end past
  their procedure or chunk; no-advance → 0 overflow, 0 overlap; swapped
  operands → overlaps. clang/rust files fit under any rule (their sites are
  small), which is why no fixture caught it. 0.5.0 had rebuilt the validator
  on the wrong rule and documented llvm as the odd one out. Reversed: purepdb
  now matches llvm-pdbutil and cvinfo.h. This moves second-and-later ranges on
  every rust-lld/clang file — recorded as address-moving in the changelog.
- **`ChangeCodeOffsetBase n` = the n'th `S_SEPCODE` chunk** of the procedure
  (cvinfo.h: "nth separated code chunk (main code chunk == 0)"). MSVC emits
  `S_SEPCODE` after the proc's S_END with `sectParent:offParent` = the proc
  address; the site's ranges are relative to the chunk start and fit its
  length exactly (chunk 0x22: ranges (19,9),(29,5)). 21/103 sites in
  _bz2.pdb were "unplaced" for this. Now placed; a chunk in another section
  becomes a second InlineFunction (never seen: MSVC keeps cold code in .text).

Validator: llvm-pdbutil 18 crashes (SIGSEGV in TpiStream::getNumTypeRecords)
on all five XP-era symbol-server files; purepdb reads them and pdbparse agrees
on every public (907/4849/2926/10469/10526). Crash is now a ToolLimitation,
not a FAIL. Section names with control bytes (`PAGEVRFY\x1c!\x03` in
ntkrnlmp) broke the SC-row regex; relaxed.

Corpus of corrupt derivatives (182 files): 0 escaped exceptions. purepdb opens
`bitflip_01_per_4k` (6 functions) where llvm-pdbutil refuses ("DBI Length
does not equal sum of substreams") — relevant to the #53 discussion on
raising vs. tolerating DBI size damage.

Not found in any file: `_ST` (pre-VS2005 length-prefixed) records — the XP
files already carry S_PUB32. python 2.7 (VS2008) has 0 inline sites. Leaving
`_ST` support out; there is no file to test it against.

Observation (no action): `public_symbols()` order on ntkrnlmp is "unsorted" by
one descent — `__pte_top` at 34:0xFFFFFFFF sorts before `__guard_eh_cont_count`
at 34:0. The publics address map is sorted with the offset as a *signed* int32
(MS's own comparator); purepdb keeps the map's order, which is correct. Both
are absolute symbols (segment = sections+1), RVA None.

node.pdb (354 MB, clang-cl, 3340 modules): diagnose 2m28s wall on the fixes
branch under contention; 96917 procs, 139920 publics, 1584395 inline sites,
0 malformed, 0 truncations, no warnings.

### 2026-09-12 — OMAP verified against real BBT output; validator widened

- The corpus track fetched the PE images matching the symbol-server PDBs
  (symbol server serves images keyed by TimeDateStamp+SizeOfImage). Running
  `dev/validate_omap_against_windows.py`: Win7 x86 kernel32 (61182 OMAP
  entries), ntdll (67714), user32 (38222) — **0 far misses on every pair**
  once the harness follows Win7's export stubs (hot-patch prologue + short
  jump, +13/+7/-11 explained byte by byte) and counts exports named under a
  different name (`Beep` → `_BeepImplementation@8`) as address agreement.
  Untranslated counterfactual: 0 of 3857. OMAP translation is correct on
  genuine BBT output, which the repo had never been able to check.
- llvm-pdbutil 18 prints an S_TRAMPOLINE's thunk offset in its target slot
  (bug in the reference). purepdb's targets verified against the `jmp rel32`
  in sqlite3.dll: 348/348 (x64), all (x86); pinned by a new groundtruth test.
- Validator now has 13 checks (+data, thread locals, thunks, trampolines);
  211 python.org PDBs (2.7 VS2008, 3.4 VS2010, 3.5 VS2015, 3.8, 3.12, 3.13,
  3.14; x64/x86/arm64) agree on every check. The 20 "no inlinee" errors in
  the first python run were the pre-fix validator; gone on re-run.

### Section Map reconstruction measured on the corpus

`sections_from_map` vs the real table on 33 corpus PDBs with slot 5:
- exact on every user-mode link.exe and lld image (python 2.7–3.14 incl.
  arm64, node x64/arm64, clang, rust std, Win10/11 kernel32/ntdll/ucrtbase);
- exact against **slot 10** on the five BBT-processed files (the map describes
  the pre-BBT layout, so comparing to slot 5 there is the wrong question);
- wrong on kernel-mode images linked with a small /ALIGN: hal.dll first
  section at 0x380 (align 0x80), ntkrnlpa at 0x600 (0x200) — the documented
  0x1000 assumption; ntkrpamp happens to match;
- ntkrnlmp (33 sections): addresses all exact, but section 28 is executable
  in the real table while the map's flags (0x10b) lack SEG_EXECUTE, so with
  slot 5 gone its publics would not count as code publics.
GUID/age agree with llvm-pdbutil on 68/68 files.
Fuzzer gained --seed-dir; a run over msdl+xp+clang+rust seeds is in progress.

### VS2015 inline sites with compiler-internal ids

python 3.5 (MSVC 14.0) PDBs carry `S_INLINESITE` records whose inlinee is
`0x80000000 | n` with tiny `n` — cvinfo.h's `DecoratedItemId` ("combined
encoding of TI or FuncId, in compiler implementation"), which the VS2015
linker never remapped into the IPI. `_hashlib.pdb` (x86): 5802 of 6554 sites;
`_decimal.pdb`: 201/1978. llvm-pdbutil prints them nameless too, and the
DEBUG_S_INLINEELINES entries carry the same ids, so nothing in the file names
them. Not fixable; now counted (`Diagnostics.unnamed_inline_sites`) and
warned about, and a missing IPI stream is warned about as well (it was not).

### Fuzzing

- fixtures, seeds 1 and 2, 4455 + 4620 inputs (1500 s each under load): clean.
- `--seed-dir` msdl+xp+clang+rust (stripped, OMAP, 1024-byte-block shapes),
  seed 7, 6000 inputs: clean.
- corrupt corpus, 182 derived files: 0 escapes, every refusal a PdbError.

### PRs improved on their branches (not pushed yet)

- #53 `fix-correctness-audit` +1 commit: overrun clamps and is diagnosed
  (`Diagnostics.dbi_overrun`), negative sizes still raise; C13 zero padding is
  padding; CLI test; damaged-End test that actually pins the coordinate fix.
- #59 `release/modernize-release-workflow` +1 commit: floor back to 3.11; the
  bump lives on `python-3.12-floor` (1 commit from main, tested on 3.12).

### Final differential run (fixes branch, 13 checks)

`dev/validate_against_llvm.py` over 257 PDBs — every fixture, python.org
2.7/3.4/3.5/3.8/3.12/3.13/3.14 (x64, x86, arm64), symbol-server Win7/10/11
and XP, self-built clang/lld and rust: **257 of 257 agree with llvm-pdbutil
on every check** (the five XP files on the checks llvm-pdbutil survives —
contributions and lines — since it crashes on their type stream).
`dev/audit_corpus.py` with the fixes branch over msdl/xp/python/clang/rust/
corrupt: 0 refused among real files, 0 escaped exceptions anywhere.

xul.pdb (1.9 GB, mmap): open 1.8 s / 267 MB RSS, publics 3.4 s, functions()
230 s / 3.2 GB RSS on the fixes branch — the perf track's target.

Branch logistics: the session's configured git email is refused by GitHub's
privacy setting, so every branch was replayed (cherry-pick -n + commit -C
--author, trees verified identical) under the noreply identity and pushed as
`audit/fixes-2026-09`, `audit/research-log`, `pr53-clean`, `pr59-clean`,
`python-3.12-floor-clean`. Updating the two PR heads needs a refspec push
this session could not make; see prs.md.

- Fuzz seed 3 (fixtures, 4623 inputs in 1500 s): clean. Total fuzz this
  audit: 4455 + 4620 + 4623 fixture-seeded, 6000 corpus-seeded, plus the
  2000-input pass before every commit — no escaped exception anywhere.
- S_COMPILE2 (VS2008 and link.exe import-library modules) now decoded;
  python27.pdb compile_info 500 → 511, sqlite fixtures 155 → 159 and
  145 → 149 (golden counts moved deliberately).

### xul.pdb (1.9 GB, Firefox) on the fixes branch, via mmap

open 1.8 s / 267 MB; publics 25231 in 3.4 s; functions() 265345 in 230 s
(3.2 GB RSS); diagnose() 954 s and **11.4 GB RSS**: 11 073 218 inline sites,
342 642 procs, 250 unnamed sites (the VS2015-style decorated ids again, in a
current clang-cl build). The memory was diagnose() materialising eleven
million InlineFunction objects to count two integers; `_inline_listing`
gained a `keep=False` mode (commit 2e7fb98) and the re-measurement is in
progress. Time is the perf track's problem (single-pass survey).
Re-measured after 2e7fb98: diagnose() 866 s, peak RSS 7.2 GB (from 11.4 GB;
~1.9 GB of that is the mapped file's resident pages). The rest is transient
per-module garbage on modules hundreds of MB long — the perf track's
single-pass survey is the next lever; a per-module `gc`/streaming walk the
one after.

## PR review

Full write-up: `docs/audit/pr-review.md`. Verdicts: #52 merge as is (diagnose()
output byte-identical on all 7 fixtures between main and the branch; timing
within noise, as the commit says; one trivial keep-both conflict with #53).
#53 merge with changes: the named-streams, PublicsStream and C13 fixes are real
and proven before/after, but `_check_substream` raising on a past-end size turns
a DBI stream missing its last 8 bytes from fully readable into unopenable
(clamp + `Diagnostics.dbi_overrun` suggested; the negative-size raise stays),
`iter_subsections` reports 1-4 trailing zero pad bytes as "lines missing", and
the inline-site signature test passes on main unchanged so it pins nothing.
#59 merge with changes: pins verified real via ls-remote, guard tests are
network-free, `make package` fine, but the 3.12 floor is an unrelated breaking
change inside a tooling PR (split it out; `msf.py:36` comment goes stale; the
suite is no longer run against the built artefact, only imported). Dependabot
#56/#57/#58 merge as is: ruff 0.16.6, ty 0.0.79 and build 1.6.0 all clean on
this tree. Suggested order: deps, #52, #53, then #59 only after the maintainer
creates the trusted publishers and environments. Coordinator has since applied
the #53/#59 suggestions on `pr53-clean` / `pr59-clean`.
