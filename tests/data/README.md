# Groundtruth fixtures

Real compiler output, paired with the image the PDB describes. The pairing is
the point: `tests/_pe.py` reads the image with nothing but `struct` and never
consults the PDB, so when the two agree on a section table or an export address
that agreement is evidence rather than a shared assumption.

These files are in the repository but excluded from the sdist and wheel, so
installing purepdb does not pull down 12 MB of binaries. `test_groundtruth.py`
skips when they are absent.

| fixture | toolchain | what it covers |
|---|---|---|
| `sqlite/x86/sqlite3.{dll,pdb}` | MSVC `link.exe`, VS2019-era, x86 | 3539 procs, 685 publics, 277 exports, cdecl underscore-decorated aliases |
| `sqlite/x64/sqlite3.{dll,pdb}` | MSVC `link.exe`, VS2019-era, x64 | 3522 procs, 660 publics, 277 exports, C++ decorated aliases |
| `rustpe/rust_pe_symbols_msvc.{exe,pdb}` | `rust-lld`, rustc 1.97.1, x64 | 248 procs, 451 publics, EH funclets, and 143 code publics with the function flag *clear* |
| `rustpe32/rust_pe_symbols_i686.{exe,pdb}` | `rust-lld`, rustc 1.94.1, i686 | 2 procs, 5 publics, 13 inline sites, and 4 code publics with the flag clear — the `code_publics` rule at 32 bits |

The rustpe fixtures are the ones that pin the `code_publics` rule: `link.exe`
sets `PUBLIC_FLAG_FUNCTION` on every code public, `rust-lld` does not, and
without the executable-section fallback the x64 binary loses 36% of its
functions and the i686 one loses 4 of 6.

What decides the flag turned out not to be the architecture or the linker. It
is the contributing object's COFF symbol type: `rust-lld` sets the flag for
every symbol rustc and clang emit, and leaves it clear for symbols defined in
hand-written assembly, which declares no function type. The x64 fixture's
unflagged publics are all CRT-shim and import symbols for that reason. The
i686 fixture reproduces it deliberately and small enough to read in full —
`stubs.s` beside it is four assembly stubs and nothing else.

## Provenance

All are redistributable and none is third-party licensed material.

**sqlite3** — built with MSVC from sqlite's own sources, which are public domain.
Image bases `0x10000000` (x86) and `0x180000000` (x64).

**rust_pe_symbols_msvc** — our own build, regenerable from the `main.rs` beside
it. rustc 1.97.1 (`8bab26f4f`, 2026-07-14), release profile, `debuginfo=2`,
`CARGO_INCREMENTAL=0`:

```bash
cargo build --release --target x86_64-pc-windows-msvc
```

Built on Linux: `rust-lld` plus mingw-w64 import libraries and a small
locally-written CRT shim, so no Microsoft-licensed material is involved. **It is
not runnable** — the CRT symbols (`mainCRTStartup`, `__chkstk`, `floor`, …) are
stubs sufficient to link but not to execute. That is deliberate; the file exists
to be parsed and disassembled. The Rust function bodies come from the same
prebuilt std rlibs a Windows-hosted build would link, so the code under test is
representative.

**rust_pe_symbols_i686** — our own build, regenerable with the `build.sh` beside
it. rustc 1.94.1 (`e408947bf`, 2026-03-25), `-O -C debuginfo=2 -C panic=abort`,
linked by `rust-lld` with `/nodefaultlib`. It is `#![no_std] #![no_main]`, so it
links against no CRT and no import library at all, and `stubs.s` is assembled by
clang — no Microsoft-licensed material is involved. **It is not runnable**: the
stubs return constants. It exists to be parsed. `hash_round` and `mix_pair` are
`#[inline(always)]`, which is where its 13 inline sites come from.

## Adding to this set

The shapes that once needed a fixture are now covered, two of them without one:

* **32-bit rust-lld** — `rustpe32/`, above.
* **No section-header stream** — covered by deriving it. `test_sectionmap.py`
  clears Optional Debug Header slot 5 in a byte copy of each real PDB and
  requires every function to come back at the address it had before, resolved
  from the DBI Section Map instead. A PDB a toolchain genuinely emitted that
  way would still be worth having, to confirm such files look like these.
* **OMAP tables** — likewise derived. `test_omap.py` re-serialises a real PDB
  with an address map and an original section table added, so the container,
  the DBI stream and every symbol record are real and only the tables are
  ours. BBT is not publicly available, so a genuinely BBT-processed PDB from a
  vendor symbol server remains the one shape no test here has seen.

Keep fixtures small, keep them own builds or public-domain sources, and record
the toolchain here — a fixture whose provenance is unclear cannot stay in a
public repository.

## Issue #25: shapes still missing from this corpus

Tracked in [issue #25](https://github.com/danielplohmann/purepdb/issues/25).
Two PDB shapes are not represented by any file committed here:

1. a toolchain-genuine PDB **without** Optional Debug Header slot 5 (no
   section-header stream);
2. a **genuinely BBT-processed** PDB carrying real OMAP tables (slots 3/4 and,
   typically, slot 10).

Both are exercised today by derivation (`test_sectionmap.py`, `test_omap.py`),
but neither has been checked in because no redistributable example has been
found.

### How to probe a candidate

`tools/probe_symbol_pdb.py` fetches a PE's symbol-server PDB (via the RSDS
record) or inspects a local `.pdb`, then prints slot occupancy and runs
`purepdb diagnose()`:

```bash
# from a PE on disk (downloads the matching PDB):
python tools/probe_symbol_pdb.py /path/to/module.dll -o /tmp/probe

# from a PDB already downloaded:
python tools/probe_symbol_pdb.py /tmp/probe/ntdll.pdb
```

The symbol-server URL is
`https://msdl.microsoft.com/download/symbols/<name>/<guid><age:X>/<name>` where
`guid` and `age` come from the PE's `IMAGE_DEBUG_TYPE_CODEVIEW` / RSDS entry.

### BBT-processed PDB with real OMAP — found, not committable

**Windows 10/11 system binaries do not carry OMAP.** Post-link reordering moved
into PGO at compile/link time; modern `ntdll.dll` PDBs have slot 5 present and
slots 3/4/10 absent. Do not spend time on current Windows builds for this shape.

**Windows XP-era symbol-server PDBs do carry OMAP.** Probed 2026-08-14 against
`msdl.microsoft.com` (files kept outside this repository):

| PDB | GUID+age | OMAP entries | slot 5 | slot 10 | purepdb |
|---|---|---:|---|---|---|
| `ntdll.pdb` (XP SP2) | `A618C674A4FC40F5B1781029C2C7F68E2` | 37 118 | present | present | 2 213 functions, 0 warnings |
| `ntdll.pdb` (XP, alt build) | `1751003260CA42598C0FB326585000ED2` | 37 061 | present | present | 2 207 functions |
| `ntkrnlmp.pdb` (XP) | `B883868B88CB415A92EC010CF6A115A52` | 145 549 | present | present | 8 158 functions |

These are the first real-world OMAP tables purepdb has been run against. They
confirm the parser handles a stripped public PDB with OMAP and original section
headers — proc records are absent (public-sourced listing only), and every
address resolves.

**They cannot be added to `tests/data/`.** The Microsoft Debugging Tools for
Windows license terms prohibit redistributing symbol files accessed from the
symbol server. The acceptance criterion in #25 explicitly allows recording that
a shape *cannot* be sourced redistributably; this is that record.

Manual verification: download one of the PDBs above, then
`purepdb diagnose <path>` — `omap entries` is printed whenever slot 4 or slot
10 is present.

### Slot-5-less PDB — not found

Every committed fixture (`sqlite/`, `rustpe/`, `rustpe32/`) has slot 5
present. Every symbol-server PDB probed for the OMAP search above also had slot
5 present (including the XP OMAP files, which carry *both* final section
headers and the pre-BBT original table in slot 10).

No redistributable candidate has been identified. Plausible sources called out
in #25 — an older linker, a non-Microsoft toolchain, or a constructed PDB from
a writer — remain untried here. Until one is built or found under a license
this repository can ship, `test_sectionmap.py` remains the evidence for the
fallback path.

### Win10 `ntdll` (issue comment, confirmed)

A Windows 10 VM `ntdll.dll` + symbol-server PDB (not committed) parsed with no
warnings: 4 055 functions, 1 428 proc records agreeing with 1 428 proc refs,
and 12 extra functions from the `code_publics` rule — all real `.text` symbols
(`ExpInterlockedPopEntrySListResume`, `KiUserCallbackDispatcherContinue`,
`RtlpUmsThreadYield`). Slots 3/4/10 absent; slot 5 present. Useful as a
parser smoke test on a vendor stripped public PDB, but not an OMAP fixture.
