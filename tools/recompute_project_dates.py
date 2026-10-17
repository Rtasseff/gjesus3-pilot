#!/usr/bin/env python3
"""recompute_project_dates.py -- set every project's start_date / last_activity from its acquisitions.

    python tools/recompute_project_dates.py --nas-root "J:\\gjesus3-data"
    python tools/recompute_project_dates.py --nas-root "J:\\gjesus3-data" --project-id PROJ-0042
    python tools/recompute_project_dates.py --nas-root "J:\\gjesus3-data" --apply ^
        --backup-dir "C:\\Users\\rtasseff\\temp\\gjesus3_project_dates_backup_20261020"

WHY. Since 2026-07-14 the two columns mean the project's first and newest ACQUISITION date
(06_REGISTRIES §4), and the retention close-out ("newest acquisition older than 3 years") reads
them. They were backfilled once that day and nothing maintained them until the ingest's Step 11b
(2026-10): a project an ingest created carries its creation date, and later ingests never moved
`last_activity`. This is the one-time repair, and the tool to re-run whenever the range is in doubt.

WHAT IT DOES. For each project in registry_projects.csv: the min / max usable acquisition date
over the live rows of registry_raw.csv that name it (`projects_registry.acquisition_date_ranges`,
the same function reopen_project.py uses; blank or unusable dates excluded). Unlike the ingest's
widening, a recompute may move a date INWARD -- that is the point. A project with no dated
acquisition keeps its dates and is reported.

Dry run by default: a table of project, current dates, recomputed dates, changed?. Writes nothing.
--apply needs --backup-dir, a directory that must NOT exist yet. Under the registry lock it copies
registry_projects.csv there, verifies the copy by SHA-256, re-reads registry_raw.csv, and rewrites
only the date columns of the rows that change. Only start_date / last_activity are ever written.
"""
import argparse
import os
import shutil
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
from ingest import checksum, locking, projects_registry, registry  # noqa: E402


def plan(proj_rows, raw_rows, scope=None):
    """[{project_id, name, cur_start, cur_last, new_start, new_last, changed, note}], one per project.

    `scope` is a set of project_ids to restrict to (None = all)."""
    ranges = projects_registry.acquisition_date_ranges(raw_rows)
    out = []
    for p in proj_rows:
        pid = (p.get("project_id") or "").strip()
        if scope is not None and pid not in scope:
            continue
        cur_s, cur_l = p.get("start_date") or "", p.get("last_activity") or ""
        lo, hi, n, undated = ranges.get(pid, ("", "", 0, 0))
        if lo:
            new_s, new_l = lo, hi
            note = f"{n} acquisitions" + (f", {undated} without a date" if undated else "")
        else:
            new_s, new_l = cur_s, cur_l
            note = (f"{n} acquisitions, none dated -- kept" if n
                    else "no acquisitions -- kept")
        out.append({"project_id": pid, "name": p.get("name") or "",
                    "cur_start": cur_s, "cur_last": cur_l,
                    "new_start": new_s, "new_last": new_l,
                    "changed": (new_s, new_l) != (cur_s, cur_l), "note": note})
    return out


def print_table(items, tag=""):
    hdr = ("project_id", "name", "start_date", "last_activity", "-> start_date", "-> last_activity", "changed?")
    print(f"{tag}{hdr[0]:<10} {hdr[1]:<24} {hdr[2]:<10} {hdr[3]:<13} {hdr[4]:<13} {hdr[5]:<16} {hdr[6]}")
    for it in items:
        print(f"{tag}{it['project_id']:<10} {it['name'][:24]:<24} {it['cur_start']:<10} {it['cur_last']:<13} "
              f"{it['new_start']:<13} {it['new_last']:<16} {'YES' if it['changed'] else 'no'}  ({it['note']})")
    n = sum(it["changed"] for it in items)
    print(f"{tag}{len(items)} project(s); {n} would change" if tag else
          f"{len(items)} project(s); {n} changed")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--nas-root", required=True)
    ap.add_argument("--project-id", action="append", default=None,
                    help="restrict to this project (PROJ-XXXX or name); repeatable")
    ap.add_argument("--apply", action="store_true", help="write the changes (default: dry run)")
    ap.add_argument("--backup-dir", help="with --apply: a NEW directory for the verified backup")
    args = ap.parse_args(argv)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass
    nas = os.path.normpath(args.nas_root)
    reg_dir = os.path.join(nas, "registries")
    proj_csv = projects_registry.projects_registry_path(nas)
    raw_csv = os.path.join(reg_dir, "registry_raw.csv")
    if not os.path.isfile(proj_csv) or not os.path.isfile(raw_csv):
        print(f"REFUSED: {proj_csv} or {raw_csv} not found")
        return 2

    proj_rows = projects_registry.read_projects(proj_csv)
    scope = None
    if args.project_id:
        scope = set()
        for ref in args.project_id:
            row = projects_registry.find_project(proj_rows, ref)
            if not row:
                print(f"REFUSED: {ref} is not in {proj_csv}")
                return 2
            scope.add(row["project_id"].strip())

    if not args.apply:
        print_table(plan(proj_rows, registry.read_registry(raw_csv), scope), tag="[dry-run] ")
        print("[dry-run] nothing written; re-run with --apply --backup-dir <new dir>")
        return 0

    if not args.backup_dir:
        print("REFUSED: --apply needs --backup-dir <a new directory>")
        return 2
    bk = os.path.abspath(args.backup_dir)
    if os.path.exists(bk):
        print(f"REFUSED: backup dir {bk} already exists (use a new one)")
        return 3

    with locking.registry_lock(reg_dir):
        os.makedirs(bk)
        dst = os.path.join(bk, projects_registry.PROJECTS_FILENAME)
        shutil.copy2(proj_csv, dst)
        if checksum.sha256_file(proj_csv) != checksum.sha256_file(dst):
            print(f"STOP: the backup of {proj_csv} does not verify; nothing written")
            return 3
        print(f"backup: {dst} (SHA-256 verified)")
        # Re-read both inside the lock: an ingest may have committed or widened since the dry run.
        items = plan(projects_registry.read_projects(proj_csv), registry.read_registry(raw_csv), scope)
        for it in items:
            if it["changed"]:
                projects_registry.update_row(
                    proj_csv, it["project_id"],
                    {"start_date": it["new_start"], "last_activity": it["new_last"]},
                    allowed=projects_registry.DATE_FIELDS)
    print_table(items)
    return 0


if __name__ == "__main__":
    sys.exit(main())
