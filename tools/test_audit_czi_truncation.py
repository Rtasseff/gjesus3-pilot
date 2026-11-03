#!/usr/bin/env python3
"""test_audit_czi_truncation.py -- the read-only .czi truncation audit (issue #17).

  1. audit_file on a synthetic ZISRAW file (the writer from
     test_retire_acquisition_v2, copied here because that module runs on import):
     intact -> ok; the tail cut inside the last segment -> truncated with the
     exact shortfall; cut into the directories -> unreadable; not a CZI ->
     unreadable; absent -> missing.
  2. run_audit over a fake NAS: selects MICROSCOPY .czi rows only, writes one
     report row per acquisition with the status, tallies, and main() exits 1 on
     a finding, 0 when clean, 2 on a bad root; nothing is written under the NAS.

Temporary directories only: no NAS, no database, no pytest.

Run:  python tools/test_audit_czi_truncation.py      (exit 0 = pass)
"""

import contextlib
import csv
import io
import os
import struct
import sys
import tempfile
import uuid

import numpy as np

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import audit_czi_truncation as act  # noqa: E402
from ingest import registry  # noqa: E402

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok:   {msg}")


# ---- a minimal CZI writer (copied from test_retire_acquisition_v2.py) ------------------

def _seg(sid, data):
    alloc = (len(data) + 31) // 32 * 32
    return sid.encode().ljust(16, b"\0") + struct.pack("<qq", alloc, len(data)) + data + bytes(alloc - len(data))


def _dir_entry(file_pos, c, shape):
    out = b"DV" + struct.pack("<iqiiB5si", 1, file_pos, 0, 0, 0, bytes(5), 3)     # Gray16, uncompressed
    for name, start, size in (("X", 0, shape[1]), ("Y", 0, shape[0]), ("C", c, 1)):
        out += name.encode().ljust(4, b"\0") + struct.pack("<iifi", start, size, 0.0, size)
    return out


def _att_entry(file_pos, guid, ctype, name):
    return (b"A1" + bytes(10) + struct.pack("<qi", file_pos, 0) + guid.bytes
            + ctype.encode().ljust(8, b"\0") + name.encode().ljust(80, b"\0"))


def write_czi(path, xml, planes, attachments):
    n_sb, n_att = len(planes), len(attachments)
    pos = 32 + 512
    sbdir_pos = pos
    pos += 32 + (128 + n_sb * (32 + 60) + 31) // 32 * 32
    attdir_pos = pos
    pos += 32 + (256 + n_att * 128 + 31) // 32 * 32
    chunks = [("meta", None)] + [("sb", i) for i in range(n_sb)] + [("att", j) for j in range(n_att)]
    built, sb_entries, att_entries, meta_pos = [], {}, {}, None
    for kind, i in chunks:
        if kind == "meta":
            meta_pos = pos
            seg = _seg("ZISRAWMETADATA", struct.pack("<ii", len(xml), 0) + bytes(248) + xml)
        elif kind == "sb":
            data = np.ascontiguousarray(planes[i], dtype="<u2").tobytes()
            entry = _dir_entry(pos, i, planes[i].shape)
            fixed = struct.pack("<iiq", 0, 0, len(data)) + entry
            seg = _seg("ZISRAWSUBBLOCK", fixed + bytes(max(256, len(fixed)) - len(fixed)) + data)
            sb_entries[i] = entry
        else:
            name, ctype, payload, guid = attachments[i]
            entry = _att_entry(pos, guid, ctype, name)
            seg = _seg("ZISRAWATTACH", struct.pack("<i", len(payload)) + bytes(12) + entry + bytes(112) + payload)
            att_entries[i] = entry
        built.append(seg)
        pos += len(seg)
    fg = uuid.uuid4()
    hdr = struct.pack("<iiii", 1, 0, 0, 0) + fg.bytes + fg.bytes + struct.pack("<iqqiq", 0, sbdir_pos, meta_pos, 0,
                                                                            attdir_pos)
    out = (_seg("ZISRAWFILE", hdr + bytes(512 - len(hdr)))
           + _seg("ZISRAWDIRECTORY", struct.pack("<i", n_sb) + bytes(124) + b"".join(sb_entries[i] for i in range(n_sb)))
           + _seg("ZISRAWATTDIR", struct.pack("<i", n_att) + bytes(252) + b"".join(att_entries[j] for j in range(n_att)))
           + b"".join(built))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(out)
    return out


XML = (b'<?xml version="1.0" encoding="utf-8"?><ImageDocument><Metadata><Information><Image>'
       b'<SizeX>8</SizeX></Image></Information></Metadata></ImageDocument>')
RNG = np.random.default_rng(17)
PLANES = [RNG.integers(0, 4000, (6, 8)).astype(np.uint16) for _ in range(3)]
ATTS = [("Thumbnail", "JPG", b"jpg-bytes" * 40, uuid.uuid4())]


def write_truncated(src_bytes, path, cut):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(src_bytes[:-cut])


# ---- 1. one file ----------------------------------------------------------------------

def test_audit_file():
    print("[audit_file]")
    with tempfile.TemporaryDirectory() as d:
        good = os.path.join(d, "good.czi")
        data = write_czi(good, XML, PLANES, ATTS)
        r = act.audit_file(good)
        check(r["status"] == "ok", f"an intact file is ok ({r['detail']})")
        check(r["furthest_end"] == len(data), "the furthest segment ends exactly at the end of the file")

        short = os.path.join(d, "short.czi")
        write_truncated(data, short, 100)
        r = act.audit_file(short)
        check(r["status"] == "truncated" and r["short_by"] == 100,
              f"100 bytes cut from the tail -> truncated, short by 100 ({r['detail']})")

        # cut deep enough to lose the whole attachment segment and part of a subblock: the
        # directories survive (near the start), the furthest entries point past EOF -> truncated
        deep = os.path.join(d, "deep.czi")
        write_truncated(data, deep, 1000)
        r = act.audit_file(deep)
        check(r["status"] == "truncated" and int(r["short_by"]) >= 1,
              f"cut into the body -> truncated ({r['detail'][:90]})")

        stub = os.path.join(d, "stub.czi")
        write_truncated(data, stub, len(data) - 40)
        r = act.audit_file(stub)
        check(r["status"] == "unreadable", f"a 40-byte stub is unreadable ({r['detail'][:60]})")

        text = os.path.join(d, "text.czi")
        with open(text, "wb") as f:
            f.write(b"not a czi at all" * 100)
        r = act.audit_file(text)
        check(r["status"] == "unreadable", "a non-CZI is unreadable")
        check(act.audit_file(os.path.join(d, "nope.czi"))["status"] == "missing", "an absent file is missing")


# ---- 2. the registry walk --------------------------------------------------------------

def reg_row(acq, eco, instrument, canonical, primary):
    row = dict.fromkeys(registry.REGISTRY_FIELDS, "")
    row.update({"acq_id": acq, "registration_datetime": "2026-06-15T11:24:12Z", "data_ecosystem": eco,
                "instrument": instrument, "canonical_path": canonical, "primary_file_name": primary,
                "primary_kind": "file"})
    return row


def test_run_audit():
    print("[run_audit / main over a fake NAS]")
    with tempfile.TemporaryDirectory() as d:
        nas = os.path.join(d, "nas")
        regs = os.path.join(nas, "registries")
        os.makedirs(regs)
        rows = [
            reg_row("ACQ-20250319-CELL-001", "MICROSCOPY", "CELL", "/raw/MICROSCOPY/2025/2025-03/ACQ-20250319-CELL-001/", "ACQ-20250319-CELL-001.czi"),
            reg_row("ACQ-20251031-CELL-003", "MICROSCOPY", "CELL", "/raw/MICROSCOPY/2025/2025-10/ACQ-20251031-CELL-003/", "ACQ-20251031-CELL-003.czi"),
            reg_row("ACQ-20260304-ZWSI-001", "MICROSCOPY", "ZWSI", "/raw/MICROSCOPY/2026/2026-03/ACQ-20260304-ZWSI-001/", "ACQ-20260304-ZWSI-001.czi"),
            reg_row("ACQ-20220118-MRI-001", "DICOM", "MRI", "/raw/DICOM/2022/2022-01/ACQ-20220118-MRI-001/", "ACQ-20220118-MRI-001.data"),
        ]
        with open(os.path.join(regs, "registry_raw.csv"), "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(registry.REGISTRY_FIELDS)
            for r in rows:
                w.writerow([r[c] for c in registry.REGISTRY_FIELDS])
        data = write_czi(act.primary_path(nas, rows[0]), XML, PLANES, ATTS)
        write_truncated(data, act.primary_path(nas, rows[1]), 1_000)
        # rows[2]'s primary is missing on purpose

        logged = []
        out = os.path.join(d, "report.csv")
        tally = act.run_audit(nas, out, log_fn=lambda m, level="INFO": logged.append((level, m)))
        check(tally == {"ok": 1, "truncated": 1, "unreadable": 0, "missing": 1}, f"tally ({tally})")
        with open(out, encoding="utf-8", newline="") as f:
            rep = {r["acq_id"]: r for r in csv.DictReader(f)}
        check(set(rep) == {"ACQ-20250319-CELL-001", "ACQ-20251031-CELL-003", "ACQ-20260304-ZWSI-001"},
              "one row per MICROSCOPY .czi acquisition; the MRI row is not audited")
        check(rep["ACQ-20251031-CELL-003"]["status"] == "truncated" and int(rep["ACQ-20251031-CELL-003"]["short_by"]) >= 1,
              "the truncated primary is reported with its shortfall")
        check(rep["ACQ-20260304-ZWSI-001"]["status"] == "missing", "the absent primary is reported missing")
        check(any(l == "WARN" and "TRUNCATED" in m for l, m in logged), "findings are logged as WARN lines")

        sel = list(act.select_rows(rows, instruments=["ZWSI"]))
        check([r["acq_id"] for r in sel] == ["ACQ-20260304-ZWSI-001"], "--instruments narrows the selection")
        sel = list(act.select_rows(rows, acq_ids=["ACQ-20250319-CELL-001"]))
        check([r["acq_id"] for r in sel] == ["ACQ-20250319-CELL-001"], "--acq-ids narrows the selection")

        nas_files_before = sorted(os.path.join(b, f) for b, _d, fs in os.walk(nas) for f in fs)
        with contextlib.redirect_stderr(io.StringIO()):
            rc = act.main(["--nas-root", nas, "--out", os.path.join(d, "r2.csv")])
            rc_clean = act.main(["--nas-root", nas, "--out", os.path.join(d, "r3.csv"),
                                 "--acq-ids", "ACQ-20250319-CELL-001"])
            rc_bad = act.main(["--nas-root", os.path.join(d, "nowhere")])
            rc_in_nas = act.main(["--nas-root", nas, "--out", os.path.join(nas, "r.csv")])
        check(rc == 1, "main exits 1 with findings")
        check(rc_clean == 0, "main exits 0 when every selected file is ok")
        check(rc_bad == 2 and rc_in_nas == 2, "main exits 2 on a bad root or a report under the NAS")
        nas_files_after = sorted(os.path.join(b, f) for b, _d, fs in os.walk(nas) for f in fs)
        check(nas_files_before == nas_files_after, "nothing was written under the NAS root")


def main():
    test_audit_file()
    test_run_audit()
    print()
    if FAILS:
        print(f"{len(FAILS)} FAILURE(S):")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print("ALL CZI-TRUNCATION-AUDIT CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
