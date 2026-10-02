#!/usr/bin/env python3
"""repair_primary_inplace.py -- replace a DAMAGED single-file primary in /raw/ with a verified good copy
of the SAME acquisition, in place, keeping its ACQ-ID (the recovery pattern: repair, not re-ingest).

    python tools/repair_primary_inplace.py --nas-root "J:\\gjesus3-data" --acq ACQ-20251031-CELL-003 \\
        --source "D:\\...\\ID59_1022_tumor_CD206.czi" --source-sha256 <manifest sha> \\
        --keep-dir "D:\\projects\\gjesus3\\staging\\_repair\\ACQ-20251031-CELL-003" \\
        --note "2026-10-01: primary repaired in place ..." [--dry-run]

First use (Ryan's approval, 2026-10-01): ACQ-20251031-CELL-003, whose ingested primary was truncated
(5.1 MB short, last of 108 tiles unreadable -- probably copied while ZEN was still writing it); the
historical drive held the complete file.

IN PLACE, on purpose. The primary is hard-linked into project folders. os.replace or delete-and-copy
would create a NEW file and every existing link would keep the truncated bytes. So the existing file is
opened r+b, the good bytes are written from offset 0, truncate(size), flush, os.fsync -- same file, all
links see the repair.

Order (every step verified before the next; a failure stops the run):
  1. the source's SHA-256 equals --source-sha256 (the staging manifest), and the current primary's
     SHA-256 equals its checksums.json (it is the damaged file we think it is);
  2. backup to a FRESH dated off-NAS folder, SHA-256-verified: the registries' CSVs + .acq_id_seq.json,
     and the acquisition's checksums.json + metadata.json; the damaged primary itself is copied to
     --keep-dir (for the record) and verified;
  3. overwrite in place; SHA-256 of the primary == the source's; for .czi every subblock decodes;
     every --link given (the project hard links) hashes the same;
  4. checksums.json: only the hash string is replaced, bytes otherwise as found (line endings kept);
     registry_raw: file_size_mb + a notes clause, through registry.update_row under the registry lock.
  The sidecar is left alone: none of its fields depends on the byte size (checked: they are image
  dimensions from the file's own metadata, identical in both copies).
"""
import argparse
import datetime as dt
import glob
import hashlib
import os
import shutil
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
from ingest import locking, registry  # noqa: E402

CHUNK = 8 * 1024 * 1024


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(CHUNK), b""):
            h.update(b)
    return h.hexdigest()


def czi_all_tiles(path):
    import czifile
    bad = n = 0
    with czifile.CziFile(path) as c:
        for e in c.filtered_subblock_directory:
            n += 1
            try:
                e.read_segment_data(c).data()
            except Exception:  # noqa: BLE001 -- counted
                bad += 1
    return n, bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--nas-root", required=True)
    ap.add_argument("--acq", required=True)
    ap.add_argument("--source", required=True)
    ap.add_argument("--source-sha256", required=True)
    ap.add_argument("--keep-dir", required=True)
    ap.add_argument("--link", action="append", default=[], help="a project hard link to re-hash after")
    ap.add_argument("--note", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")
    nas = os.path.normpath(a.nas_root)
    reg_dir = os.path.join(nas, "registries")
    reg_path = os.path.join(reg_dir, "registry_raw.csv")
    row = next((r for r in registry.read_registry(reg_path) if r["acq_id"] == a.acq), None)
    if not row:
        print(f"STOP: {a.acq} not in the registry")
        return 2
    acq_dir = os.path.join(nas, row["canonical_path"].strip("/").replace("/", os.sep))
    prim = os.path.join(acq_dir, row["primary_file_name"])
    cs_path = os.path.join(acq_dir, "checksums.json")
    cs_raw = open(cs_path, "rb").read()
    new_size = os.path.getsize(a.source)
    print(f"{a.acq}: primary {prim} ({os.path.getsize(prim)} B) <- {a.source} ({new_size} B)")

    # 1. identities
    src_sha = sha256(a.source)
    if src_sha != a.source_sha256:
        print(f"STOP: source sha256 {src_sha} != manifest {a.source_sha256}")
        return 3
    old_sha = sha256(prim)
    if old_sha.encode() not in cs_raw:
        print(f"STOP: current primary sha256 {old_sha} is not the one in checksums.json")
        return 3
    print(f"1. source sha256 == manifest; primary sha256 == checksums.json ({old_sha[:12]})")
    for ln in a.link:
        if sha256(ln) != old_sha:
            print(f"STOP: link {ln} is not the current primary (hash differs)")
            return 3
    print(f"   {len(a.link)} link(s) hash as the current primary")
    if a.dry_run:
        print(f"[dry-run] would back up, keep the damaged copy in {a.keep_dir}, overwrite in place, "
              f"set file_size_mb={round(new_size / 1e6, 1)} and add the note")
        return 0

    # 2. backups
    bk = os.path.join(r"C:\Users\rtasseff\temp", f"gjesus3_repair_backup_{dt.datetime.now():%Y%m%d_%H%M%S}_{a.acq}")
    os.makedirs(bk)
    srcs = glob.glob(os.path.join(reg_dir, "*.csv")) + [os.path.join(reg_dir, ".acq_id_seq.json"),
                                                         cs_path, os.path.join(acq_dir, "metadata.json")]
    for s in srcs:
        d = os.path.join(bk, os.path.basename(s))
        shutil.copy2(s, d)
        if sha256(s) != sha256(d):
            print(f"STOP: backup of {s} does not verify")
            return 4
    os.makedirs(a.keep_dir, exist_ok=True)
    keep = os.path.join(a.keep_dir, os.path.basename(prim) + ".truncated")
    if not os.path.exists(keep):
        shutil.copy2(prim, keep)
    if sha256(keep) != old_sha:
        print("STOP: the kept damaged copy does not verify")
        return 4
    print(f"2. backup {bk} verified; damaged copy kept at {keep}")

    # 3. overwrite IN PLACE (same file: every hard link sees it)
    with open(a.source, "rb") as src, open(prim, "r+b") as dst:
        dst.seek(0)
        for b in iter(lambda: src.read(CHUNK), b""):
            dst.write(b)
        dst.truncate(new_size)
        dst.flush()
        os.fsync(dst.fileno())
    got = sha256(prim)
    if got != src_sha:
        print(f"STOP: after the write the primary hashes {got}, not {src_sha} -- restore from {keep}")
        return 5
    if prim.lower().endswith(".czi"):
        n, bad = czi_all_tiles(prim)
        print(f"   czi: {n} subblocks, {bad} unreadable")
        if bad:
            print("STOP: subblocks still unreadable")
            return 5
    for ln in a.link:
        if sha256(ln) != src_sha:
            print(f"STOP: link {ln} does not hash as the repaired primary")
            return 5
    print(f"3. repaired in place: sha256 {src_sha[:12]}, {len(a.link)} link(s) hash the same")

    # 4. records
    new_cs = cs_raw.replace(old_sha.encode(), src_sha.encode())
    tmp = cs_path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(new_cs)
    os.replace(tmp, cs_path)
    notes = (row.get("notes") or "").rstrip()
    upd = {"file_size_mb": f"{round(new_size / 1e6, 1)}",
           "notes": (notes + " " if notes else "") + a.note}
    with locking.registry_lock(reg_dir):
        found, applied, _ = registry.update_row(reg_path, a.acq, upd)
    print(f"4. checksums.json hash replaced (other bytes as found); registry {sorted(applied)} updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
