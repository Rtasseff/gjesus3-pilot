#!/usr/bin/env python3
"""audit_czi_truncation.py -- READ-ONLY audit of production `.czi` primaries for truncation.

Why (issue #17; tasks/BACKLOG.md "audit production .czi for truncated primaries"):
`ACQ-20251031-CELL-003` was 5.1 MB short in production (its last tile unreadable)
and `ACQ-20230707-CELL-001` was a 0.5 MB preview of a 360 MB scan. Both came from
the 2026-06-15 best-guess ingests that read `K:\\gjesus\\Ainhize`, a live share.
`checksums.json` matched the truncated bytes, because the ingest hashed what it
copied, so `verify_checksums` cannot catch this class. Others may be affected.

How: a `.czi` (ZISRAW) is a sequence of segments, each with a 32-byte header
(`SID`, `AllocatedSize`, `UsedSize`). The file header names the positions of
the subblock directory, the metadata and the attachment directory; the
directories name every subblock's / attachment's position. A truncation cuts
the tail, so the segment that reaches FURTHEST into the file is the one that
ends beyond the end of the file. This tool reads the header, the two
directories, and the segment headers of the furthest subblock and attachment
and of the metadata segment: a few KB per file, no pixels, so it is cheap over
SMB (an AxioScan file is tens of GB). A file the library cannot even open is
reported as `unreadable` (a truncation into the directories looks like that).

What it does NOT do: compare pixels, recompute checksums, or write anything.
Repairs follow the in-place pattern (`tools/repair_primary_inplace.py`) from a
complete copy, one at a time, on Ryan's go.

Usage:
    python tools/audit_czi_truncation.py --nas-root J:\\gjesus3-data --out czi_audit.csv
    python tools/audit_czi_truncation.py --nas-root ... --acq-ids ACQ-20251031-CELL-003 ACQ-...
    python tools/audit_czi_truncation.py --nas-root ... --instruments CELL LSM9   # a subset

Exit code: 0 when every file is ok; 1 when any is truncated, unreadable or missing
(so a scheduled run is noticed); 2 on a bad NAS root.
"""

import argparse
import csv
import os
import sys
import time
from datetime import datetime

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from ingest import registry  # noqa: E402

STATUSES = ("ok", "truncated", "unreadable", "missing")
REPORT_FIELDS = ["acq_id", "instrument", "status", "detail", "path",
                 "size_bytes", "furthest_end", "short_by"]


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {level}: {msg}", file=sys.stderr)


# ---- the check -------------------------------------------------------------

def segment_end(czi, offset):
    """The byte just past the segment at `offset` (its header + allocated size).

    When the 32-byte segment header itself cannot be read -- the file ends
    before or inside it -- the segment is at least header-sized, so its end is
    `offset + 32` at the very least: that is already past the end of the file,
    which is the finding. (A directory that points at a position beyond EOF is
    exactly what a truncation into the body looks like.)
    """
    import czifile
    try:
        seg = czifile.CziSegment(czi, offset)
    except czifile.CziSegmentNotFoundError:
        return offset + 32, "?"
    return seg.data_offset + seg.allocated_size, seg.sid


def czi_segment_ends(path):
    """[(label, end_offset)] for the segments that reach furthest into the file.

    Reads: the file header; the subblock directory (one segment); the attachment
    directory (one segment); then the segment header of the furthest subblock,
    the furthest attachment and the metadata segment. Raises on a file the
    library cannot parse (the caller reports it as unreadable).
    """
    import czifile
    ends = []
    with czifile.CziFile(path) as czi:
        hdr = czi.header
        for label, pos in (("directory", hdr.directory_position),
                           ("metadata", hdr.metadata_position),
                           ("attachment_directory", hdr.attachment_directory_position)):
            if pos:
                end, _sid = segment_end(czi, pos)
                ends.append((label, end))
        entries = czi.subblock_directory
        if entries:
            furthest = max(entries, key=lambda e: e.file_position)
            end, _sid = segment_end(czi, furthest.file_position)
            ends.append((f"furthest subblock (of {len(entries)})", end))
        try:
            atts = czi.attachment_directory
        except Exception:  # noqa: BLE001 -- no attachments, or an unreadable directory
            atts = ()
        atts = [a for a in atts if getattr(a, "file_position", None)]
        if atts:
            furthest = max(atts, key=lambda a: a.file_position)
            end, _sid = segment_end(czi, furthest.file_position)
            ends.append((f"furthest attachment (of {len(atts)})", end))
    return ends


def audit_file(path):
    """One file -> dict(status, detail, size_bytes, furthest_end, short_by)."""
    out = {"status": "", "detail": "", "size_bytes": "", "furthest_end": "", "short_by": ""}
    if not os.path.isfile(path):
        out.update(status="missing", detail="primary file not found")
        return out
    size = os.path.getsize(path)
    out["size_bytes"] = size
    try:
        ends = czi_segment_ends(path)
    except Exception as exc:  # noqa: BLE001 -- any parse failure is a finding, not a crash
        out.update(status="unreadable",
                   detail=f"{type(exc).__name__}: {exc}"[:300])
        return out
    if not ends:
        out.update(status="unreadable", detail="no segments located (empty directory?)")
        return out
    label, furthest = max(ends, key=lambda t: t[1])
    out["furthest_end"] = furthest
    if furthest > size:
        out.update(status="truncated", short_by=furthest - size,
                   detail=f"{label} ends at byte {furthest}, file is {size} bytes "
                          f"({furthest - size} bytes short)")
    else:
        out.update(status="ok", detail=f"{label} ends at byte {furthest} <= {size}")
    return out


# ---- the registry walk -----------------------------------------------------

def primary_path(nas_root, row):
    rel = (row.get("canonical_path") or "").strip().lstrip("/").rstrip("/")
    parts = [p for p in rel.split("/") if p]
    return os.path.join(nas_root, *parts, (row.get("primary_file_name") or "").strip())


def select_rows(rows, acq_ids=None, instruments=None):
    """The live registry rows whose primary is a .czi (MICROSCOPY ecosystem)."""
    want_ids = set(acq_ids or ())
    want_inst = set(instruments or ())
    for r in rows:
        if want_ids and (r.get("acq_id") or "").strip() not in want_ids:
            continue
        if want_inst and (r.get("instrument") or "").strip() not in want_inst:
            continue
        if (r.get("data_ecosystem") or "").strip().upper() != "MICROSCOPY":
            continue
        if not (r.get("primary_file_name") or "").lower().endswith(".czi"):
            continue
        yield r


def run_audit(nas_root, out_path, acq_ids=None, instruments=None, limit=None,
              log_fn=log, progress_every=200):
    """Audit every selected row; write the report CSV; return the status tally."""
    registry_path = os.path.join(nas_root, "registries", "registry_raw.csv")
    rows = list(select_rows(registry.read_registry(registry_path), acq_ids, instruments))
    if limit:
        rows = rows[:limit]
    tally = {s: 0 for s in STATUSES}
    t0 = time.time()
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=REPORT_FIELDS)
        w.writeheader()
        for i, r in enumerate(rows, start=1):
            path = primary_path(nas_root, r)
            res = audit_file(path)
            tally[res["status"]] += 1
            w.writerow({"acq_id": r.get("acq_id", ""), "instrument": r.get("instrument", ""),
                        "path": path, **res})
            if res["status"] != "ok":
                log_fn(f"{res['status'].upper()}: {r.get('acq_id')} {res['detail']}", "WARN")
            if progress_every and i % progress_every == 0:
                f.flush()
                rate = i / max(time.time() - t0, 1e-9)
                log_fn(f"  {i}/{len(rows)} files, {rate:.1f}/s, "
                       f"{sum(v for k, v in tally.items() if k != 'ok')} finding(s) so far")
    log_fn(f"done: {len(rows)} files in {time.time() - t0:.0f}s -> {out_path}; "
           + ", ".join(f"{k} {v}" for k, v in tally.items()))
    return tally


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Read-only audit of production .czi primaries for truncation (issue #17).")
    p.add_argument("--nas-root", default=os.environ.get("GJESUS3_ROOT", "/mnt/gjesus3"),
                   help="NAS root (default: $GJESUS3_ROOT or /mnt/gjesus3). Only read.")
    p.add_argument("--out", default=None,
                   help="Report CSV (default: czi_truncation_audit_<timestamp>.csv in the "
                        "current directory; never under the NAS root).")
    p.add_argument("--acq-ids", nargs="*", default=None, help="Only these ACQ-IDs.")
    p.add_argument("--instruments", nargs="*", default=None,
                   help="Only these instrument codes (e.g. CELL LSM9 ZWSI XMIC).")
    p.add_argument("--limit", type=int, default=None, help="Stop after N files (a trial run).")
    args = p.parse_args(argv)

    nas_root = args.nas_root
    if not os.path.isdir(os.path.join(nas_root, "registries")):
        log(f"NAS root does not look valid: {nas_root!r} (no registries/ folder)", "ERROR")
        return 2
    out_path = args.out or f"czi_truncation_audit_{datetime.now():%Y%m%d_%H%M%S}.csv"
    if os.path.abspath(out_path).startswith(os.path.abspath(nas_root) + os.sep):
        log("--out must not be under the NAS root (this tool writes nothing there)", "ERROR")
        return 2
    log(f"NAS root: {nas_root}; report: {out_path}")
    tally = run_audit(nas_root, out_path, args.acq_ids, args.instruments, args.limit)
    findings = sum(v for k, v in tally.items() if k != "ok")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
