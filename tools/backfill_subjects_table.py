#!/usr/bin/env python3
"""backfill_subjects_table.py — build registry_subjects.csv from existing acqs.

The subjects-table writer (ingest/subjects_table.py) was added AFTER 13k+
acquisitions were ingested, so the live registry carries packed subject_ids on
every animal row but has no registry_subjects.csv. This one-time, idempotent
back-fill walks registry_raw.csv, reads each subject-bearing acquisition's
metadata.json sidecar (which cached the animal-facility-DB record at ingest time
— no live DB needed), and upserts one row per subject through the SAME writer the
ingest uses. Re-running is safe (the upsert merges; no duplicate rows).

Reuses, with NO parallel write path:
  - ingest.registry.read_registry                  (read registry_raw.csv)
  - ingest.subjects_table.row_from_subject_block    (sidecar block -> table row)
  - ingest.subjects_table.plan_upserts              (dry-run preview = the real merge)
  - ingest.subjects_table.upsert_subjects           (the write, under the lock)

Usage:
  PYTHONPATH=tools python tools/backfill_subjects_table.py --nas-root J:/gjesus3-data --dry-run
  PYTHONPATH=tools python tools/backfill_subjects_table.py --nas-root J:/gjesus3-data --apply
"""
import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone

from ingest import registry, subjects_table


def _sidecar_path(nas_root, canonical_path):
    """`/raw/.../ACQ-.../` (root-relative, as stored in registry_raw) -> the
    on-disk metadata.json path under the NAS root."""
    rel = (canonical_path or "").strip().strip("/")
    return os.path.join(nas_root, rel, "metadata.json")


def _subject_blocks(sidecar):
    """Yield subject blocks from a sidecar dict: the multi-animal subjects[]
    array if present (the future live-sync shape), else the single subject
    block (every historical acquisition)."""
    subs = sidecar.get("subjects")
    if isinstance(subs, list) and subs:
        for s in subs:
            if isinstance(s, dict):
                yield s
        return
    s = sidecar.get("subject")
    if isinstance(s, dict):
        yield s


def _db_complete(row):
    """True when we have a full DB record for a subject and need not read any
    more of its sidecars — lets the walk skip the many repeat scans of one
    animal (MRI especially: many exams per animal)."""
    if (row.get("source") or "") != "animal-facility-db":
        return False
    if (row.get("sex") or "").strip().lower() in ("", "unknown"):
        return False
    return all((row.get(f) or "").strip() for f in ("species", "strain", "date_of_birth"))


def collect_rows(nas_root, log, limit=0):
    """Walk registry_raw.csv, read the subject-bearing sidecars, and return
    (rows, stats): one richest row per distinct subject, in first-seen order."""
    reg_path = os.path.join(nas_root, "registries", "registry_raw.csv")
    acqs = registry.read_registry(reg_path)
    log(f"registry_raw.csv: {len(acqs)} acquisitions")

    best = {}        # facility_id -> richest row seen
    order = []       # first-seen order -> a stable table
    done = set()     # subjects we already have a complete DB record for
    stats = Counter()
    scanned = 0
    for r in acqs:
        packed = (r.get("subject_ids") or "").strip()
        if not packed:
            continue
        stats["acqs_with_subjects"] += 1
        ids = [x.strip() for x in packed.split(";") if x.strip()]
        if ids and all(i in done for i in ids):
            stats["acqs_skipped_complete"] += 1
            continue
        if limit and scanned >= limit:
            continue
        scanned += 1

        blocks = {}
        side = _sidecar_path(nas_root, r.get("canonical_path", ""))
        if os.path.isfile(side):
            try:
                with open(side, encoding="utf-8") as f:
                    sc = json.load(f)
                stats["sidecars_read"] += 1
                for b in _subject_blocks(sc):
                    fid = (b.get("facility_animal_id") or "").strip()
                    if fid:
                        blocks[fid] = b
            except Exception:
                stats["sidecars_unreadable"] += 1
        else:
            stats["sidecars_missing"] += 1

        species_hint = (r.get("sample_organism") or "").strip()
        for fid in ids:
            if fid in done:
                continue
            blk = blocks.get(fid)
            if blk:
                row = subjects_table.row_from_subject_block(blk)
            else:
                # No sidecar block for this id — keep the id with whatever the
                # registry knows (species from sample_organism); mark pending-db
                # so the recovery tool can complete it later.
                row = subjects_table.row_from_subject_block({
                    "facility_animal_id": fid,
                    "species": species_hint,
                    "source": "pending-db",
                })
                stats["thin_fallback_rows"] += 1
            if not row:
                continue
            if fid not in best:
                order.append(fid)
            # Keep the richer of what we've seen (preview only; the writer's
            # merge is the authority at apply time).
            prev = best.get(fid)
            if prev is None or (_db_complete(row) and not _db_complete(prev)):
                best[fid] = row
            if _db_complete(best[fid]):
                done.add(fid)
        if scanned % 1000 == 0:
            log(f"  ... scanned {scanned} acqs, {len(order)} subjects so far")

    return [best[fid] for fid in order], stats


def main(argv):
    ap = argparse.ArgumentParser(
        description="Back-fill registry_subjects.csv from existing acquisitions.")
    ap.add_argument("--nas-root", required=True, help="e.g. J:/gjesus3-data")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="report only; write nothing")
    mode.add_argument("--apply", action="store_true", help="write registry_subjects.csv")
    ap.add_argument("--limit", type=int, default=0, help="cap acqs scanned (debug)")
    args = ap.parse_args(argv[1:])

    def log(m, level="INFO"):
        print(m if level == "INFO" else f"[{level}] {m}")

    nas_root = args.nas_root.rstrip("/").rstrip("\\")
    registries_dir = os.path.join(nas_root, "registries")
    rows, stats = collect_rows(nas_root, log, limit=args.limit)

    print("\n=== BACK-FILL SUMMARY ===")
    print(f"subject-bearing acqs : {stats['acqs_with_subjects']}")
    print(f"sidecars read        : {stats['sidecars_read']}  "
          f"(skipped-complete: {stats['acqs_skipped_complete']}, "
          f"missing: {stats['sidecars_missing']}, unreadable: {stats['sidecars_unreadable']})")
    print(f"distinct subjects    : {len(rows)}  (thin fallback rows: {stats['thin_fallback_rows']})")
    print("by source            :", dict(Counter(r.get("source", "") for r in rows)))

    # Preview the merge against whatever is already on disk using the SAME merge
    # the writer uses (plan_upserts) — so the dry-run delta == the apply delta.
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    existing = subjects_table.read_subjects(subjects_table.subjects_path(registries_dir))
    _, plan = subjects_table.plan_upserts(existing, rows, now)
    print(f"vs existing table    : {dict(plan)}  (existing rows: {len(existing)})")
    print("\nsample rows:")
    for r in rows[:8]:
        print(f"  {r['facility_id']:<26} {r.get('species', ''):<14} "
              f"sex={r.get('sex', ''):<8} strain={r.get('strain', ''):<12} "
              f"dob={r.get('date_of_birth', ''):<12} src={r.get('source', '')}")

    if args.dry_run:
        print("\n[DRY RUN] nothing written. Re-run with --apply to write the table.")
        return 0

    res = subjects_table.upsert_subjects(registries_dir, rows, now=now, log=log)
    print(f"\nAPPLIED -> {subjects_table.subjects_path(registries_dir)}")
    print(f"  {res}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
