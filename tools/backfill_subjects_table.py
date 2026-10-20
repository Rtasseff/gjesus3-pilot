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

--with-db (2026-10-20) also fills `facility_db_id`, the facility DB's own key
for the animal (06_REGISTRIES §2.8.1). Every (acquisition, subject) link is put
through the DATED lookup (animal_db: the animal that held the code on the
acquisition day, following transfers), with the DB read once, read-only. A
DB-sourced row gets the id only when all its links agree on ONE animal; links
the lookup refuses, and ids behind which two animals stand, are reported and
leave the column blank. Rows not yet filled from the DB (`pending-db`) are left
to the recovery tool, which writes the id into the sidecar.

Usage:
  PYTHONPATH=tools python tools/backfill_subjects_table.py --nas-root J:/gjesus3-data --dry-run
  PYTHONPATH=tools python tools/backfill_subjects_table.py --nas-root J:/gjesus3-data --apply
  PYTHONPATH=tools python tools/backfill_subjects_table.py --nas-root J:/gjesus3-data --dry-run --with-db
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

import animal_db
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


def collect_rows(nas_root, log, limit=0, only=None):
    """Walk registry_raw.csv, read the subject-bearing sidecars, and return
    (rows, stats): one richest row per distinct subject, in first-seen order.
    `only`: an optional set of ACQ-IDs; every other acquisition is skipped unread
    (e.g. refreshing the subjects of just-recovered acquisitions, 2026-10-08)."""
    reg_path = os.path.join(nas_root, "registries", "registry_raw.csv")
    acqs = registry.read_registry(reg_path)
    log(f"registry_raw.csv: {len(acqs)} acquisitions")

    best = {}        # facility_id -> richest row seen
    order = []       # first-seen order -> a stable table
    done = set()     # subjects we already have a complete DB record for
    stats = Counter()
    scanned = 0
    for r in acqs:
        if only is not None and r.get("acq_id", "") not in only:
            continue
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


def resolve_link_db_ids(acqs, index, only=None):
    """Every (acquisition, subject) link through the dated lookup.

    Returns (by_id, refused): by_id maps a facility id to {db id: [acq ids]};
    refused lists (acq_id, facility_id, reason, detail) for links the lookup
    would not answer (no animal held the code that day, the date precedes the
    birth, or no animal ever)."""
    by_id = defaultdict(lambda: defaultdict(list))
    refused = []
    for r in acqs:
        acq = r.get("acq_id", "")
        if only is not None and acq not in only:
            continue
        in_vivo = (r.get("sample_type") or "").strip().lower() != "tissue"
        day = animal_db.acq_id_day(acq)
        for fid in (x.strip() for x in (r.get("subject_ids") or "").split(";")):
            try:
                animal_db.parse_subject_id(fid)
            except ValueError:
                continue  # blank, or not a facility id (e.g. a collaborator's DICOM subject)
            res = animal_db.lookup_by_subject_id(fid, on_date=day, in_vivo=in_vivo, index=index)
            if res.status == "found":
                by_id[fid][res.subject["facility_db_id"]].append(acq)
            else:
                refused.append((acq, fid, res.reason, res.detail))
    return by_id, refused


def apply_db_ids(rows, by_id):
    """Set `facility_db_id` on DB-sourced rows whose links name ONE animal.
    Returns the facility ids behind which the links name several animals,
    as {facility id: {db id: [acq ids]}} (left blank, for a person)."""
    split = {}
    for row in rows:
        fid = row.get("facility_id", "")
        found = by_id.get(fid) or {}
        if len(found) > 1:
            split[fid] = found
            continue
        if found and (row.get("source") or "") == "animal-facility-db" \
                and not (row.get("facility_db_id") or "").strip():
            row["facility_db_id"] = str(next(iter(found)))
    return split


def main(argv):
    ap = argparse.ArgumentParser(
        description="Back-fill registry_subjects.csv from existing acquisitions.")
    ap.add_argument("--nas-root", required=True, help="e.g. J:/gjesus3-data")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="report only; write nothing")
    mode.add_argument("--apply", action="store_true", help="write registry_subjects.csv")
    ap.add_argument("--limit", type=int, default=0, help="cap acqs scanned (debug)")
    ap.add_argument("--acq-ids", metavar="FILE",
                    help="only these acquisitions: one ACQ-ID per line ('#' comments allowed)")
    ap.add_argument("--with-db", action="store_true",
                    help="also fill facility_db_id through the dated lookup "
                         "(reads the facility DB once, read-only; needs ~/.my.cnf)")
    args = ap.parse_args(argv[1:])

    def log(m, level="INFO"):
        print(m if level == "INFO" else f"[{level}] {m}")

    nas_root = args.nas_root.rstrip("/").rstrip("\\")
    registries_dir = os.path.join(nas_root, "registries")
    only = None
    if args.acq_ids:
        with open(args.acq_ids, encoding="utf-8-sig") as f:
            only = {ln.split("#", 1)[0].strip() for ln in f} - {""}
        log(f"scope: {len(only)} ACQ-ID(s) from {args.acq_ids}")
    rows, stats = collect_rows(nas_root, log, limit=args.limit, only=only)

    print("\n=== BACK-FILL SUMMARY ===")
    print(f"subject-bearing acqs : {stats['acqs_with_subjects']}")
    print(f"sidecars read        : {stats['sidecars_read']}  "
          f"(skipped-complete: {stats['acqs_skipped_complete']}, "
          f"missing: {stats['sidecars_missing']}, unreadable: {stats['sidecars_unreadable']})")
    print(f"distinct subjects    : {len(rows)}  (thin fallback rows: {stats['thin_fallback_rows']})")
    print("by source            :", dict(Counter(r.get("source", "") for r in rows)))

    if args.with_db:
        conn = animal_db.get_connection()
        try:
            index = animal_db.HolderIndex.from_connection(conn)
        finally:
            conn.close()
        acqs = registry.read_registry(os.path.join(registries_dir, "registry_raw.csv"))
        by_id, refused = resolve_link_db_ids(acqs, index, only=only)
        split = apply_db_ids(rows, by_id)
        n_links = sum(len(a) for ids in by_id.values() for a in ids.values())
        print(f"\nDB links resolved    : {n_links}  (refused: {len(refused)}, "
              f"by reason {dict(Counter(x[2] for x in refused))})")
        print(f"rows given a DB id   : {sum(1 for r in rows if r.get('facility_db_id'))}")
        for acq, fid, reason, detail in refused[:200]:
            print(f"  REFUSED {acq} {fid}: {reason}: {detail}")
        if len(refused) > 200:
            print(f"  ... and {len(refused) - 200} more refused link(s)")
        for fid, ids in split.items():
            print(f"  SPLIT   {fid}: links name several animals "
                  f"{ {k: len(v) for k, v in ids.items()} } - left blank")

    # Preview the merge against whatever is already on disk using the SAME merge
    # the writer uses (plan_upserts) — so the dry-run delta == the apply delta.
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    existing = subjects_table.read_subjects(subjects_table.subjects_path(registries_dir))
    _, plan = subjects_table.plan_upserts(existing, rows, now)
    conflicts = plan.pop("conflicts")
    print(f"vs existing table    : {dict(plan)}  (existing rows: {len(existing)})")
    for fid, have, got in conflicts:
        print(f"  CONFLICT {fid}: the table names DB animal {have}, this run {got} - not merged")
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
