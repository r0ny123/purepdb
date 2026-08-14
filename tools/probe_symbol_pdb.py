#!/usr/bin/env python3
"""Probe a PE image and its Microsoft symbol-server PDB for fixture shapes.

Used to investigate github.com/danielplohmann/purepdb/issues/25: whether a
candidate binary carries OMAP tables (BBT-processed) or omits the section-header
stream (Optional Debug Header slot 5).

Requires purepdb (run from the repository root after install).
"""

from __future__ import annotations

import argparse
import struct
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

IMAGE_DEBUG_TYPE_CODEVIEW = 2
SYMBOL_SERVER = "https://msdl.microsoft.com/download/symbols"


@dataclass
class Rsds:
    pdb_name: str
    guid: str
    age: int

    @property
    def symbol_path(self) -> str:
        return f"{self.pdb_name}/{self.guid}{self.age:X}/{self.pdb_name}"


def _rva_to_offset(data: bytes, rva: int) -> int | None:
    (e_lfanew,) = struct.unpack_from("<I", data, 0x3C)
    coff = e_lfanew + 4
    _machine, num_sections = struct.unpack_from("<HH", data, coff)
    (size_of_optional,) = struct.unpack_from("<H", data, coff + 16)
    opt = coff + 20
    (magic,) = struct.unpack_from("<H", data, opt)
    if magic not in (0x10B, 0x20B):
        return None
    sec_off = opt + size_of_optional
    for i in range(num_sections):
        _name, vsize, vaddr, rawsize, rawptr = struct.unpack_from(
            "<8sIIII", data, sec_off + i * 40)
        if vaddr <= rva < vaddr + max(vsize, rawsize):
            return rawptr + (rva - vaddr)
    return None


def parse_rsds_from_pe(data: bytes) -> Rsds | None:
    (e_lfanew,) = struct.unpack_from("<I", data, 0x3C)
    coff = e_lfanew + 4
    opt = coff + 20
    (magic,) = struct.unpack_from("<H", data, opt)
    if magic == 0x10B:
        dir_off = opt + 96
    elif magic == 0x20B:
        dir_off = opt + 112
    else:
        return None
    debug_rva, debug_size = struct.unpack_from("<II", data, dir_off + 6 * 8)
    if not debug_rva or not debug_size:
        return None
    base = _rva_to_offset(data, debug_rva)
    if base is None:
        return None
    for i in range(debug_size // 28):
        off = base + i * 28
        (_chars, _stamp, _maj, _min, typ, size, _addr, ptr) = struct.unpack_from(
            "<IIHHIIII", data, off)
        if typ != IMAGE_DEBUG_TYPE_CODEVIEW:
            continue
        cv = data[ptr : ptr + size]
        if not cv.startswith(b"RSDS"):
            continue
        d1, d2, d3 = struct.unpack_from("<IHH", cv, 4)
        guid = f"{d1:08X}{d2:04X}{d3:04X}{cv[12:20].hex().upper()}"
        (age,) = struct.unpack_from("<I", cv, 20)
        name_end = cv.find(b"\x00", 24)
        pdb_name = cv[24:name_end].decode("ascii", "replace")
        return Rsds(pdb_name=pdb_name, guid=guid, age=age)
    return None


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "purepdb-fixture-probe/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def report_pdb(pdb_path: Path, label: str | None = None) -> int:
    from purepdb import PDB

    pdb = PDB.open(str(pdb_path))
    d = pdb.diagnose()
    dbi = pdb.dbi

    if label:
        print(f"label : {label}")
    print(f"pdb   : {pdb_path}")
    print(f"size  : {pdb_path.stat().st_size} bytes")
    print("optional debug header (stream indices):")
    names = {
        3: "OmapToSrc (slot 3)",
        4: "OmapFromSrc (slot 4)",
        5: "section headers (slot 5)",
        10: "original sections (slot 10)",
    }
    for slot, name in names.items():
        idx = dbi.dbg_stream(slot)
        state = f"stream {idx}" if idx != 0xFFFF else "absent"
        print(f"  {name:<28s} {state}")

    print()
    print(f"section headers    : {'yes' if d.has_section_headers else 'NO'}")
    if d.omap_entries or d.has_original_sections:
        print(f"omap entries       : {d.omap_entries}")
        print(f"original sections  : {'yes' if d.has_original_sections else 'no'}")
    print(f"functions          : {len(pdb.functions())}")
    print(f"proc records       : {d.proc_records}")
    print(f"public records     : {d.public_records}")
    print(f"modules            : {d.modules}")
    if d.derived_sections:
        print(f"derived segments   : {d.derived_sections}")
    for w in d.warnings:
        print(f"WARNING: {w}")

    has_omap = d.omap_entries > 0
    print()
    print(f"fixture shape #25 slot-5-less : {'no' if d.has_section_headers else 'YES'}")
    print(f"fixture shape #25 BBT OMAP      : {'YES' if has_omap else 'no'}")
    return 0


def probe_pe(pe_path: Path, download: bool, out_dir: Path | None) -> int:
    data = pe_path.read_bytes()
    rsds = parse_rsds_from_pe(data)
    if rsds is None:
        print(f"{pe_path}: no RSDS debug directory entry", file=sys.stderr)
        return 1

    url = f"{SYMBOL_SERVER}/{rsds.symbol_path}"
    print(f"image : {pe_path}")
    print(f"pdb   : {rsds.pdb_name}")
    print(f"guid  : {rsds.guid}")
    print(f"age   : {rsds.age}")
    print(f"url   : {url}")

    try:
        pdb_data = fetch(url)
    except urllib.error.HTTPError as exc:
        print(f"fetch : HTTP {exc.code} — PDB not on symbol server", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"fetch : {exc.reason}", file=sys.stderr)
        return 1

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        dest = out_dir / rsds.pdb_name
        dest.write_bytes(pdb_data)
        if download:
            pe_dest = out_dir / pe_path.name
            pe_dest.write_bytes(data)
        return report_pdb(dest)

    tmp = Path("/tmp") / rsds.pdb_name
    tmp.write_bytes(pdb_data)
    return report_pdb(tmp)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="PE image or PDB file")
    parser.add_argument("-o", "--out-dir", type=Path, help="directory to save fetched PDB/PE")
    parser.add_argument("--download", action="store_true", help="also copy the PE into --out-dir")
    args = parser.parse_args(argv)

    if args.path.suffix.lower() == ".pdb":
        return report_pdb(args.path)
    return probe_pe(args.path, download=args.download, out_dir=args.out_dir)


if __name__ == "__main__":
    raise SystemExit(main())
