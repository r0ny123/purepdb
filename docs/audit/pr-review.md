# PR review — purepdb open pull requests (2026-09-12)

Reviewed from detached worktrees under `/home/user/wt/` (`review-52`,
`review` = #53, `review-59`, `review-main`, `review-deps`), each with its own
venv built per `AGENTS.md` (`pip install --group dev -e .`). Base for every
diff is upstream `main` at `e978f3a` (release 0.5.0). PR descriptions on
GitHub were not fetched (no API access from this session); the review is of
the commits and their messages, which the PR titles quote.

Experiment scripts: `/home/user/wt/exp/exp.py` (claim proofs, run once per
venv), `/home/user/wt/exp/c13pad.py` (C13 padding), and the per-worktree
`*.checks.txt` / `*.fuzz.txt` files beside the worktrees.

## Summary

| PR | branch | verdict | one line |
|---|---|---|---|
| #52 | `diagnose-single-pass` | **merge as is** | counts proven identical on all 7 fixtures; trivial conflict with #53 |
| #53 | `fix-correctness-audit` | **merge with changes** | five real fixes, all proven; the DBI past-end raise and the C13 trailing-pad report need softening; one test does not pin its fix |
| #59 | `release/modernize-release-workflow` | **merge with changes** | workflow is sound and pins are real; the 3.12 floor bump is an unrelated breaking change riding a tooling PR and should be its own PR |
| #56 | `dependabot/pip/build-1.6.0` | **merge as is** | `make package` builds cleanly with build 1.6.0 |
| #57 | `dependabot/pip/ruff-0.16.6` | **merge as is** | `ruff check .` clean under 0.16.6 |
| #58 | `dependabot/pip/ty-0.0.79` | **merge as is** | `ty check` clean under 0.0.79 |

Baseline on every branch (`pytest -q`, `ruff check .`, `ty check`,
`tools/fuzz.py --iterations 2000 --seed 0`):

| worktree | tests | ruff | ty | fuzz |
|---|---|---|---|---|
| main | 588 passed | clean | clean | FUZZ_MAIN |
| #52 | 588 passed | clean | clean | FUZZ_52 |
| #53 | 596 passed | clean | clean | FUZZ_53 |
| #59 (py3.12 venv) | 601 passed | clean | clean | FUZZ_59 |
| deps (ty 0.0.79 + ruff 0.16.6 + build 1.6.0 installed) | 588 passed | clean | clean | n/a |

Note the `AGENTS.md` figure "583 tests pass" is already stale on `main`
(588), before any of these PRs; #53 and #59 move it again and neither updates
the sentence. Not blocking, but whoever merges should fix the number once.

## Merge cleanliness

`git merge-tree --write-tree main <ref>`: every one of the six branches merges
onto `main` without conflict. Between branches:

- **#52 × #53**: conflict in `purepdb/pdb.py`, one hunk, both sides add a
  local declaration at the top of `diagnose()`:
  ```
  <<<<<<< diagnose-single-pass
          procs: list[codeview.ProcSymbol] = []
  =======
          c13_truncations: list[tuple[str, c13.C13Truncation]] = []
  >>>>>>> fix-correctness-audit
  ```
  Resolution is "keep both lines". Everything else in the two `diagnose()`
  edits touches different lines (#52 adds `procs.extend(...)` after the
  truncation loop and `public_records = ...` in the symrecord block; #53 adds
  the C13 walk before `body = ...`).
- **#53 × #59**: conflict in `CHANGELOG.md` — both replace `Nothing yet.`
  under `## [Unreleased]`. Resolution: concatenate (`Added` from both, `Fixed`
  from #53, `Removed` from #59).
- **#56 × #57 × #58**: adjacent-line conflicts in `pyproject.toml`
  `[dependency-groups]`; dependabot rebases the remaining ones itself after
  each merge.

**Recommended order**: #56, #57, #58 (rebase each after the previous merges) →
#52 → #53 (rebase; keep-both resolution above) → #59 last, and only after the
maintainer has created the PyPI/TestPyPI trusted publishers and the `pypi` /
`testpypi` GitHub environments it documents — merging it earlier makes the
next `v*` tag fail at the publish job after the gates pass, which then needs
the tag deleted and re-pushed.

---

## PR #52 — count the procs and publics diagnose() has already read

**Verdict: merge as is.** 1 commit, +12/−2 in `purepdb/pdb.py`.

### Claims checked

1. *"The totals are unchanged on all seven fixtures."* — Verified.
   `exp.py` dumps `dataclasses.asdict(pdb.diagnose())` (plus `warnings`) for
   every `tests/data/**/*.pdb` on `main` and on the branch;
   `diff diag-review-main.json diag-review-52.json` is empty. Counts:
   rustpe 248/451, rustpe32 2/5 (both), sqlite x64 3522/660, sqlite x86
   3539/685, syzygy 241/956, tls 2/10 (procs/publics).
2. *"Not a measurable speedup."* — Consistent with measurement. Best of 7
   `diagnose()` calls, quiet machine:
   TIMING_RESULTS
   The removed work (`module_procs()` re-slicing, `public_symbols()` sorting
   through the publics hash) is small next to the three `count_*` walks per
   module, as the commit says.

### Equivalence argument

`module_procs()` is `extract_procs(module_symbol_bytes(mod))` over the same
module list, and the loop's `if not body: continue` skips exactly the modules
where `extract_procs(b"")` would have returned `[]`. `public_symbols()` is
`extract_publics(read_stream(idx))` guarded by the same `is_valid_stream(idx)`
test, then a sort that `len()` discards. So the two counts are the same by
construction, and the fixture diff confirms it.

### Problems

None. The comments carry the *why* in the house style. One nit if a reviewer
wants it: the `procs` list is materialised only to be `len()`'d; summing
`len(codeview.extract_procs(body))` would hold less memory on a 393 MB file
(the corpus case the surrounding comments mention), but it is one list of
dataclasses that `module_procs()` used to build anyway, so this is not a
regression.

---

## PR #53 — harden parse boundary, C13 diagnostics, and DBI/GSI error handling

**Verdict: merge with changes.** 8 commits, 14 files, +321/−26.

### Claims checked, with before/after

All "before" runs use `main`'s package with #53's `tests/_synth.py` (its
`build_msf` accepts `None` for a nil stream, which `main`'s does not).

| # | claim (commit) | before (main) | after (#53) | verdict |
|---|---|---|---|---|
| 1 | `named_streams()` returns `{}` when PDB Info is absent (79173bb) | `named_streams()`, `string_table()`, `list(lines())`, `diagnose()` all raise `MsfError: stream 1 is a nil stream`; `functions()` works | all four return `{}` / `None` / `[]` / warnings, and `diagnose()` says *"the PDB Info stream cannot be read (stream 1 is a nil stream)"* | **true, real fix** — `diagnose()` raising is exactly what rule 2 forbids |
| 2 | `PublicsStream.parse` raises `PdbError` not `ValueError` (ae43f1e, 545b364) | `ValueError` from both short-header and map-past-end inputs | `PdbError` (plain, `type(...) is PdbError`); `publics_stream()` still returns `None` and `public_symbols()` still `0` on a 10-byte garbage hash stream | **true**; no boundary change since `publics_stream()` caught `ValueError` before, but the class is now honest for direct callers of `gsi` |
| 3 | DBI negative substream sizes raise `MsfError` (a6b7a62) | ModInfo size = −1: opens, 0 modules, 0 functions; SecContrib size = −4: opens, 0 contributions, `['main']` | `MsfError: DBI ModuleInfo substream size is negative (-1)` / `... SectionContribution ... (-4)` from `PDB.from_bytes` | **true**; see weighing below |
| 4 | DBI size past end raises (a6b7a62) | ModInfo size = 10⁶: opens, **1 module, 1 function** (Python slicing clamps) | `MsfError: ... runs past end of stream (starts at 64, size 1000000, stream length 160)` | **true, but a regression in coverage** — see below |
| 5 | DBI stream shorter than its header claims raises (545b364) | stream cut 8 bytes short (loses the tail of the optional debug header): opens, `['main.obj']`, `['main']`; cut to the 64-byte header: opens, `[]`, `[]` | both raise `MsfError` | **true**; same weighing |
| 6 | C13 truncations reported (94fba01) | `Diagnostics` has no `c13_truncations`; CLI `diagnose` on a module whose DEBUG_S_LINES header claims 500 bytes of an 8-byte payload prints `line info : 16 bytes` and nothing else | field present; CLI prints `WARNING: 1 C13 line-info section(s) stopped early; ... (subsection 0xf2 length 500 runs 492 bytes past the end of the 16-byte C13 stream)` | **true**; `c13_truncations == []` on all 7 fixtures, so no false positive on real output |
| 7 | inline sites offset by signature size only when stripped (94d854b) | test `test_inline_site_in_stream_without_c13_signature` **passes on `main` unchanged**; `inline_sites()` → `[('helper','outer')]` both before and after | same | **not observable** — see below |
| 8 | fuzzer exercises `publics_stream()` (8bb4739) | — | `exercise()` gains the call; fuzz clean | true |
| 9 | `Reader.align` removed (94e2183) | `grep -rn "\.align(" purepdb tests tools` finds no caller | — | true, dead code |

### Weighing the DBI raise (claims 3–5) against `AGENTS.md` rule 2

`DbiStream.parse` runs inside `PDB.__init__`, so an `MsfError` here means
`PDB.open()` fails and nothing on the file is reachable — not even
`diagnose()`, the tool the project built to explain damage. There is
precedent for that at this layer: `main` already raises `MsfError` for a DBI
stream shorter than its 64-byte header, and `UnsupportedPdbError` for an
empty one, so "container-level damage raises" is an existing line, and the
commit message argues the substream table is on the container side of it.

But experiment 5 is the case that decides it: a DBI stream missing its **last
8 bytes** — the tail of the optional debug header, which `_parse_dbg_header`
already tolerates being short — went from *every function recovered* to
*file unopenable*. Experiment 4 likewise went from 1/1 recovered to nothing.
Those are files a caller sweeping a directory could read yesterday and gets a
`PdbError` for tomorrow, with no diagnostic to tell them the damage was eight
bytes at the end of one substream. That is a coverage regression the
CHANGELOG lists under *Fixed*.

The negative-size check is different: a negative size makes the *next*
substream's offset go backwards, so every later slice aliases earlier bytes
and any result is fiction. Raising there is right.

**Suggested change**: keep the raise for `size < 0`; for `off + size >
len(data)` record the overrun once on the `DbiStream` and clamp, then surface
it through `Diagnostics` (new field + warning sentence), which is what the
*Empty results are the contract* gotcha asks for. The parsers already cope
with the clamped slice — that is what `main` was doing implicitly.

```diff
--- a/purepdb/dbi.py
+++ b/purepdb/dbi.py
@@ class DbiStream:
     dbg_header: DbgHeader
     module_list_stopped_at: int | None
+    #: The first substream whose declared size ran past the end of the DBI
+    #: stream, or None. What follows it in the stream is missing, and the
+    #: parsers were handed what was there rather than what the header claimed.
+    substream_overrun: str | None
@@ def parse(cls, data: bytes) -> DbiStream:
+        self.substream_overrun = None
+
-        def _check_substream(name: str, size: int) -> None:
+        def _check_substream(name: str, size: int) -> int:
+            # A negative size is unrecoverable: the next substream's offset
+            # goes backwards and every later slice aliases bytes that were
+            # never substream data. A size past the end is a stream cut short,
+            # which the parsers below already survive -- read what is there,
+            # and say so once, in the place diagnose() can find it.
             if size < 0:
                 raise MsfError(f"DBI {name} substream size is negative ({size})")
             if off + size > len(data):
-                raise MsfError(
-                    f"DBI {name} substream runs past end of stream "
-                    f"(starts at {off}, size {size}, stream length {len(data)})"
-                )
+                if self.substream_overrun is None:
+                    self.substream_overrun = (
+                        f"DBI {name} substream runs past end of stream "
+                        f"(starts at {off}, size {size}, stream length {len(data)})")
+                return max(0, len(data) - off)
+            return size

-        _check_substream("ModuleInfo", modinfo_size)
+        modinfo_size = _check_substream("ModuleInfo", modinfo_size)
         self.modules, self.module_list_stopped_at = _parse_module_list(
             data[off : off + modinfo_size]
         )
         off += modinfo_size

-        _check_substream("SectionContribution", seccontrib_size)
+        seccontrib_size = _check_substream("SectionContribution", seccontrib_size)
         ...  # same for SectionMap, SourceInfo, TypeServerMap, EC, OptionalDebugHeader
```

```diff
--- a/purepdb/pdb.py
+++ b/purepdb/pdb.py
@@ class Diagnostics:
+    dbi_overrun: str | None = None
+    """A DBI substream whose declared size ran past the stream, if any. The
+    substreams after it were read as empty, so modules, contributions, the
+    section map or the debug-header slots may be missing."""
@@ def warnings(self) -> list[str]:
+        if self.dbi_overrun is not None:
+            out.append(
+                f"the DBI stream is shorter than its header claims ({self.dbi_overrun}); "
+                f"the substreams after that point were read as empty, so modules, "
+                f"section contributions, the section map or the debug-header slots "
+                f"may be missing"
+            )
@@ def diagnose(self) -> Diagnostics:
             module_list_stopped_at=self.dbi.module_list_stopped_at,
+            dbi_overrun=self.dbi.substream_overrun,
```

and in `tests/test_errors.py` turn `test_a_dbi_stream_shorter_than_its_header_claims_raises`
into the assertion that the cut-short stream still yields `['main.obj']`
with `substream_overrun` set and the warning present, keeping the
`pytest.raises(MsfError, match="substream size is negative")` half of
`test_dbi_substream_corrupted_sizes_raise_msf_error` and dropping its
"runs past end" half. If the maintainer prefers the hard-failure line the
commit argues for, the CHANGELOG entry should at least move out of *Fixed*
and say plainly that some previously openable damaged files now raise.

### Other problems

1. **C13 trailing zero padding is reported as damage** (`purepdb/c13.py:117-121`
   on the branch). `iter_subsections` reports any `pos < len(data)` after the
   loop. `c13pad.py`: appending 1, 2, 3 *or 4* zero bytes after a valid
   subsection pair yields
   `('module 0 (main.obj)', '4 trailing byte(s) are too few for a subsection header')`
   and the CLI warning says *"lines after that point are missing"* — false:
   `lines()` still yields the one line. No fixture module has a
   `c13_byte_size` that is not a multiple of 4 (checked: 0 of 220 C13-bearing
   modules across the 7 files), so nothing in the repo trips it, but a linker
   that pads the region is not damage. Suggested:

   ```diff
   --- a/purepdb/c13.py
   +++ b/purepdb/c13.py
   @@ def iter_subsections(data: bytes, *,
   -    if pos < len(data) and truncation is not None:
   +    # Fewer than eight bytes after the last subsection cannot be a header;
   +    # when they are zero they are padding, and only non-zero leftovers are
   +    # evidence that something was cut.
   +    if pos < len(data) and truncation is not None and any(data[pos:]):
            truncation.append(C13Truncation(
   ```

   and the same `and any(payload[pos:])` guard on the trailing-bytes report at
   the foot of `parse_lines` (`c13.py:185`).

2. **Claim 7's test does not pin its fix** (`tests/test_inline.py:399`). On
   `main` both proc and site offsets were shifted by the same `+4`, and the
   only comparison against an *unshifted* stream offset is `site_offset >=
   proc.end`. A site record is at least 12 bytes and precedes the `S_END`
   that `pEnd` points at, so a well-formed stream cannot land in the 4-byte
   window where the shift flips the answer — which is why the new test passes
   on `main` unchanged. The change is a correct coordinate-space cleanup, but
   the CHANGELOG line *"preventing mismatched coordinate spaces when
   evaluating procedure enclosures"* claims an observable fix that does not
   exist on valid input. Either reword the entry (it is a latent
   inconsistency, no listing changes) or add the one case that does differ:
   a proc whose `pEnd` field is deliberately set to `site_offset + 2` (a
   damaged pointer) — on `main` the site is dropped, on the branch it is
   placed. Both are fine; the test should not claim to cover a change it
   cannot detect.

3. **`Diagnostics.c13_truncations` reaches the CLI only through `warnings`**
   (`purepdb/__main__.py:_diagnose`). That matches how `truncations` is
   handled (`truncated streams : N` plus the warning) except there is no
   count line; acceptable, since the warning names the count. But
   `tests/test_cli.py` has no case for it — `test_diagnose` runs on a healthy
   sample. Suggested test, using the same shape as
   `test_c13_subsection_length_past_end_is_warned_about`:

   ```diff
   --- a/tests/test_cli.py
   +++ b/tests/test_cli.py
   +def test_diagnose_reports_a_c13_section_that_stops_early(tmp_path, capsys):
   +    from purepdb import c13
   +    from tests._synth import (build_msf, dbi_stream, gproc32, module_info,
   +                              module_sym_stream, names_stream, pdb_info_stream,
   +                              publics_hash_stream, section_header)
   +
   +    symbols = gproc32("main", 1, 0x10)
   +    region = struct.pack("<II", c13.DEBUG_S_LINES, 500) + b"\x00" * 8
   +    mods = module_info("main.obj", "main.obj", sym_stream=5,
   +                       sym_byte_size=4 + len(symbols), c13_byte_size=len(region))
   +    streams = [
   +        b"", pdb_info_stream({"/names": 7}), b"",
   +        dbi_stream(public_stream=4, symrecord_stream=8, module_list=mods,
   +                   dbg_header=[0xFFFF] * 5 + [6]),
   +        publics_hash_stream([]), module_sym_stream(symbols) + region,
   +        section_header(".text", 0x1000, 0x10000), names_stream([""])[0], b"",
   +    ]
   +    path = tmp_path / "c13.pdb"
   +    path.write_bytes(build_msf(streams))
   +    out, _err = _run(capsys, "diagnose", str(path))
   +    assert "1 C13 line-info section(s) stopped early" in out
   +    assert "runs 492 bytes past the end" in out
   ```

4. `C13Truncation` in `__all__` — **yes, it belongs**: `Truncation` (the
   symbol-record twin) is already exported, `Diagnostics.c13_truncations` is
   typed with it, and a caller inspecting the field needs the name. Consistent.

5. Fuzz coverage of the new paths: `exercise()` already consumes
   `pdb.diagnose().warnings` and `list(pdb.lines())`, so the C13 truncation
   walk, the named-stream fallback and the DBI checks are all driven by the
   existing fuzzer; 8bb4739 adds `publics_stream()`. Fuzz is clean on the
   branch. Fine.

6. Style nits, non-blocking: `tests/test_errors.py:308` imports `Path` inside
   the test body and hand-rolls the fixture skip, where the rest of the suite
   uses a module-level `_open`/`pytest.skip` helper (`tests/test_lines.py:231`);
   the DBI header-offset comment in that test is correct against `_HEADER`
   (`dbi.py:46-53`). The CHANGELOG entry for the named-streams fix reads well.

### Docs figures

No number cited in `docs/*.md` moves: proc/public/function counts are
identical on every fixture (same diff as for #52, `diag-review.json`).

---

## PR #59 — release on a tag through trusted publishing

**Verdict: merge with changes** — split out the Python-floor bump.
2 commits, 15 files, +703/−133.

### What was checked

- **Action pins are real.** `git ls-remote` against each action repository:
  `pypa/gh-action-pypi-publish` `refs/tags/v1.14.2^{}` →
  `dc37677b2e1c63e2034f94d8a5b11f265b73ba33` (matches);
  `actions/upload-artifact v7.0.1^{}` → `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`;
  `actions/download-artifact v8.0.1^{}` → `3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c`
  (both already used by `main`'s `release.yml`). `checkout` and
  `setup-python` pins are unchanged from `main`. All full SHAs, no tags.
- **`tests/test_release_guard.py` runs without network**: 13 passed in 0.07 s
  with every proxy variable pointed at a dead port; the script and test import
  nothing beyond `argparse/re/tomllib/pathlib/importlib`. It skips when the
  script is absent, but the sdist actually ships `.github/` (hatchling
  includes tracked files; `tar tzf` shows
  `purepdb-0.5.0/.github/workflows/scripts/release_guard.py`), so the sdist CI
  job runs it too. Fine either way.
- **`release_guard.py` against the real tree**: `--tag v0.5.0` passes and
  writes the 0.5.0 changelog section as notes; `--tag v0.6.0` fails with
  `tag v0.6.0 does not match the packaged version (pyproject.toml = 0.5.0,
  purepdb.__version__ = 0.5.0)`, exit 1. `ruff check --show-files` lists the
  script and `ty check` on it is clean, so it is under the same lint as the
  package.
- **`make package`** with a 3.12 venv: builds sdist + wheel. Building under
  the 3.11 venv also succeeds (`build` does not check `requires-python`), but
  installing the resulting wheel into 3.11 is refused:
  `Package 'purepdb' requires a different Python: 3.11.15 not in '>=3.12'`.
  That is the intended effect of the bump, and it is also why this session's
  default `python3` (3.11) could not install the branch at all.
- **Workflow logic** read line by line. Least-privilege permissions per job;
  `id-token: write` is alone in the publish job; secrets never reach a fork
  PR (`changelog.yml` uses `pull_request`, not `_target`); every
  `${{ }}` that carries user-influenced text goes through `env:`; concurrency
  refuses to cancel a publish; TestPyPI rehearsal via `workflow_dispatch` is
  gated to tag refs by the first step, which `RELEASING.md` documents.
  `.github/release.yml` category labels (`dependencies`, `github_actions`)
  are dependabot's defaults, and `dependabot.yml` sets none, so they match.

### Problems

1. **The Python floor bump does not belong in this PR** (`pyproject.toml:13`,
   `ci.yml`, `fuzz.yml`, `validate.yml`, `AGENTS.md:195-200`, `README.md:17`,
   the CHANGELOG *Removed* entry). The commit says *"Nothing in the parser
   needed 3.12"* and justifies it by an ecosystem-wide floor. That is a
   legitimate maintainer decision, but it is a user-visible breaking change
   (a `Removed` in Keep-a-Changelog terms, and it is what makes
   `pip install` refuse on 3.11) packaged inside a tooling change whose title
   says nothing about it. `AGENTS.md`'s own text on `main` says 3.11+ and CI
   tests 3.11–3.14; this PR edits those sentences consistently (grep for
   `3.11` in the branch finds only historical CHANGELOG entries and one stale
   comment, below), so it is not *inconsistent* — it is *unreviewable* as
   part of a release-workflow PR. Recommend: revert the floor to 3.11 here
   (the workflows run fine on 3.11; nothing in them needs 3.12 — `tomllib` is
   3.11) and open the bump as its own PR with the CHANGELOG *Removed* entry.
   The second commit (`50eeaca`, the Windows `shutil.which` stub fix) belongs
   with the bump, since it is only needed on 3.12.

   ```diff
   --- a/pyproject.toml
   +++ b/pyproject.toml
   -requires-python = ">=3.12"
   +requires-python = ">=3.11"
   @@
   +    "Programming Language :: Python :: 3.11",
   @@
   -target-version = "py312"
   +target-version = "py311"
   ```
   plus the matching one-word reverts in `ci.yml` (matrix `"3.11", "3.12",
   "3.13", "3.14"` and the three `python-version: "3.11"`), `fuzz.yml`,
   `validate.yml`, `publish-release.yml` (`PYTHON_VERSION: "3.11"`),
   `AGENTS.md`, `README.md`, and dropping the CHANGELOG *Removed* entry.

2. If the bump stays: `purepdb/msf.py:36` still says *"3.11 has no
   `collections.abc.Buffer` to name"* as the reason `Buffer` is a hand-written
   union. On a 3.12 floor that reason is gone; either switch to
   `collections.abc.Buffer` or reword the comment to the remaining reason
   (`unpack_from` wants a real buffer, not a protocol).

3. **The suite no longer runs against the built artefact.** `main`'s
   `release.yml` had *"Run the suite against what was built"*; the new build
   job imports the wheel from a clean venv, checks `__version__` and
   `py.typed`, and runs `purepdb --help`. `AGENTS.md` (on the branch, too)
   says the sdist CI job proves testability from an sdist, so the check is
   not lost, only moved — but the commit message's *"runs it"* undersells the
   change from "runs pytest" to "imports it". Worth one sentence in
   `RELEASING.md`, or a `pytest` run in the smoke venv against the sdist's
   `tests/` (the sdist ships them).

4. **Naming**: `release_guard.py` uses `declaredVersions` / `changelogSection`
   — camelCase in a repository whose every other function is snake_case.
   Ruff passes only because `N` is not in the selected rule set. The docstring
   explains it is shared verbatim across the MCRIT repositories (smda's
   convention), which is a reasonable trade if stated; it is stated. Leave it,
   but the tests that call them (`tests/test_release_guard.py`) now carry the
   mixed style into the suite. Non-blocking.

5. **Maintainer-side prerequisites are a hard dependency**: PyPI and
   TestPyPI trusted publishers for `publish-release.yml` with environments
   `pypi` / `testpypi`, the two GitHub environments, and the `no-changelog`
   label. `RELEASING.md` lists them. `main`'s `release.yml` said explicitly
   that automating publish "is the maintainer's decision"; this PR makes it
   for them, from a fork. Fine as a proposal, but the merge should wait for
   the setup (see merge order), and the `changelog.yml` check will start
   failing PRs that touch `purepdb/` without a CHANGELOG line the moment it
   lands — #52 is exactly such a PR (no CHANGELOG entry), so if #59 merges
   first, #52 needs the `no-changelog` label.

6. Minor: `AGENTS.md` on the branch still says *"583 tests pass"* while the
   branch has 601.

---

## Dependabot PRs #56 / #57 / #58

**Verdict: merge as is**, in any order, letting dependabot rebase the
adjacent-line `pyproject.toml` conflicts.

Checked in `review-deps` (branch `ty-0.0.79`, then `pip install ruff==0.16.6
build==1.6.0` so all three bumps are in one venv on Python 3.11):

- `ruff 0.16.6`: `ruff check .` → *All checks passed!* (no new rule hits from
  0.16.3 → 0.16.6 on this tree).
- `ty 0.0.79`: `ty check` → *All checks passed!* (0.0.72 → 0.0.79 introduces
  no new diagnostics here; same on #59's tree, which also passed under
  `ty 0.0.72`).
- `build 1.6.0`: `make package PYTHON=.venv/bin/python` → sdist + wheel
  built with `--no-isolation`.
- Tests: 588 passed; fuzz not re-run (runtime code unchanged).

Each bump is one line in `[dependency-groups]`, the single source of truth
`AGENTS.md` demands; no second copy exists to drift.

---

## Cross-cutting notes

- `AGENTS.md` "583 tests pass" is stale on `main` (588) and will be stale
  by a different number after each of #53 (596) and #59 (601). Fix once,
  after the merges.
- Corpus at `/home/user/corpus` was still archives only (`_dl/`) at review
  time, so the "does #53 make previously openable damaged files unreadable"
  question was answered with synthetic inputs rather than a real-world sweep.
  Once the corpus track extracts it, a one-liner worth running:
  open every PDB on `main` and on #53 and list the files where one raises and
  the other does not.
