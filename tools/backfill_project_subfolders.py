#!/usr/bin/env python3
"""backfill_project_subfolders.py — give existing projects the recommended
subfolders (`raw_linked/`, `working/`, `outputs/`, `metadata/`).

New projects get these at creation (`create_project.py`, via
`ingest/project_layout.py`). This is the one-time pass for the projects that
predate the convention — as of 2026-08-11, **0 of 49** live folders had
`working/`, `outputs/` or `metadata/`.

Deliberately a standalone script, not a side effect of the GUI starting up: it
is the house pattern (`relink_projects.py`, `backfill_*.py`), it is auditable,
and a researcher opening a tool should never trigger a sweep over every project
on the share.

What it does — and only this:
  * creates the MISSING subfolders, and nothing else;
  * writes NO provenance rows — provenance tracks files (07_PROVENANCE), and an
    empty directory is not one;
  * SKIPS registry rows whose project has no folder, and lists them. Those are
    normal: eight projects were closed on 2026-07-14/15 and their folders
    deleted while their rows stayed, so the acquisitions remain findable. A
    tool that "repaired" them would resurrect exactly what was deliberately
    removed;
  * REPORTS project folders with no `_project.yaml` rather than writing one.
    Five such folders exist, all predating `create_project.py`. Writing one
    means inventing an owner and a start date, which is worse than the gap.

Idempotent: a second run creates nothing. Read-only until you drop `--dry-run`.

Usage:
    python tools/backfill_project_subfolders.py --nas-root J:/gjesus3-data --dry-run
    python tools/backfill_project_subfolders.py --nas-root J:/gjesus3-data
    python tools/backfill_project_subfolders.py --nas-root J:/gjesus3-data --project AE-biomaGUNE-0424
"""

import argparse
import os
import sys
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from ingest import project_layout, projects_registry  # noqa: E402


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {level}: {msg}")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nas-root",
                    default=os.environ.get("GJESUS3_ROOT", "J:/gjesus3-data"))
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be created; write nothing")
    ap.add_argument("--project", action="append", metavar="ID_OR_NAME",
                    help="limit to this project (PROJ-id or name); repeatable")
    args = ap.parse_args(argv)

    nas = os.path.normpath(args.nas_root)
    reg_path = projects_registry.projects_registry_path(nas)
    if not os.path.isfile(reg_path):
        ap.error(f"projects registry not found: {reg_path}")

    rows = projects_registry.read_projects(reg_path)
    if args.project:
        want = {v.strip().lower() for v in args.project}
        rows = [r for r in rows
                if (r.get("project_id") or "").lower() in want
                or (r.get("name") or "").lower() in want]
        missing = want - {(r.get("project_id") or "").lower() for r in rows} \
                       - {(r.get("name") or "").lower() for r in rows}
        for m in sorted(missing):
            log(f"no such project: {m}", "WARN")

    log(f"NAS root: {nas}")
    log(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    log(f"Projects considered: {len(rows)}")
    log(f"Subfolders: {', '.join(project_layout.SUBFOLDER_NAMES)}")
    print()

    no_folder, no_yaml, touched = [], [], []
    created_total = 0

    for row in rows:
        pid = (row.get("project_id") or "").strip()
        name = (row.get("name") or "").strip()
        label = f"{pid} ({name})" if name else pid
        rel = (row.get("folder_location") or "").strip()
        # The STORED folder_location, never rebuilt from the name — the one
        # construction-site rule (05_PROJECTS §2a).
        folder = os.path.normpath(os.path.join(nas, rel.lstrip("/"))) if rel else None

        if not folder or not os.path.isdir(folder):
            no_folder.append((label, row.get("status", ""), rel or "(blank)"))
            continue

        if not os.path.isfile(project_layout.project_yaml_path(folder)):
            no_yaml.append(label)

        missing = project_layout.missing_subfolders(folder)
        if not missing:
            continue
        project_layout.ensure_subfolders(folder, dry_run=args.dry_run)
        created_total += len(missing)
        touched.append((label, missing))
        verb = "would create" if args.dry_run else "created"
        print(f"  {label}: {verb} {', '.join(missing)}")

    print()
    print("=" * 64)
    print("backfill — project subfolders")
    print("=" * 64)
    label_created = "subfolders to create" if args.dry_run else "subfolders created"
    print(f"{'projects with folders touched':<30}: {len(touched)}")
    print(f"{label_created:<30}: {created_total}")
    print(f"{'already complete':<30}: "
          f"{len(rows) - len(touched) - len(no_folder)}")

    if no_folder:
        print()
        print(f"-- registry rows with NO folder ({len(no_folder)}) "
              "— expected, not repaired " + "-" * 8)
        print("   (closed projects keep their row so acquisitions stay findable;")
        print("    the folder was deleted at close-out. Recreating it would undo that.)")
        for label, status, rel in no_folder:
            print(f"   {label:<40} status={status or '?':<8} {rel}")

    if no_yaml:
        print()
        print(f"-- project folders with NO _project.yaml ({len(no_yaml)}) "
              "— reported, not written " + "-" * 4)
        print("   (these predate create_project.py; writing one means inventing")
        print("    an owner and a start date. A Data Office call, not a backfill.)")
        for label in no_yaml:
            print(f"   {label}")

    if args.dry_run:
        print()
        print("DRY RUN — nothing was written. Re-run without --dry-run to apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
