"""Migrate existing project raw links from `.lnk` shortcuts to hard links.

One-time (idempotent) migration that converts the legacy Windows `.lnk`
shortcuts under `projects/<proj>/raw_linked/` into the new hard-link form
(see `tools/ingest/linker.py::create_hardlink`) WITHOUT re-ingesting any raw
data. For each existing `.lnk` it:

  1. derives the link name = the `.lnk` filename minus the `.lnk` extension
     (so the hard link gets exactly the name the shortcut had, sans suffix),
  2. looks up the acquisition the shortcut pointed at — via the project's
     `provenance.csv` (`output_name` -> `input_refs` = ACQ-ID) joined to
     `registries/registry_raw.csv` for the canonical raw path,
  3. creates the hard link (file primary) or folder-of-hard-links (folder
     primary, `<ACQ-ID>.data`) in place,
  4. verifies it exists, removes the `.lnk`, and appends a provenance row.

Run from **native Windows Python** (hard links use local NAS-volume paths;
both the raw primary and the project link must be on the same volume, which
they are inside the `gjesus3-data` container). Idempotent: a link that already
exists is left as-is; a `.lnk` whose hard link is already present is simply
deleted.

Usage (PowerShell, from the repo root):

    python tools/relink_projects.py --nas-root "J:/gjesus3-data" --dry-run
    python tools/relink_projects.py --nas-root "J:/gjesus3-data"
    python tools/relink_projects.py --nas-root "J:/gjesus3-data" --project proj-lions-cardiac-mri

`--dry-run` reports every intended action without creating or deleting
anything. `--keep-lnk` creates the hard links but leaves the `.lnk` files in
place (for a cautious first pass). `--project` (repeatable) limits the run to
named project folders.
"""

import argparse
import csv
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ingest import linker, provenance  # noqa: E402


def load_registry_index(nas_root):
    """acq_id -> registry row dict, read from registries/registry_raw.csv."""
    path = os.path.join(nas_root, "registries", "registry_raw.csv")
    index = {}
    with open(path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            index[row["acq_id"]] = row
    return index


def load_lnk_to_acq(prov_path):
    """Map a project's `.lnk` filename -> ACQ-ID from its provenance.csv.

    Uses the rows the ingest wrote for each shortcut (file_type `.lnk`,
    output_name = `<name>.lnk`, input_refs = the ACQ-ID).
    """
    mapping = {}
    if not os.path.exists(prov_path):
        return mapping
    with open(prov_path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            name = (row.get("output_name") or "").strip()
            acq = (row.get("input_refs") or "").strip()
            if name.lower().endswith(".lnk") and acq:
                mapping[name] = acq
    return mapping


def raw_primary_path(nas_root, row):
    """Local path to the acquisition's primary (file or `<ACQ-ID>.data` folder).

    Mirrors the dispatch in ingest_raw.py Step 12 so the migration links the
    same target the ingest would.
    """
    acq_id = row["acq_id"]
    canonical = row.get("canonical_path", "")
    primary = (row.get("primary_file_name") or "").strip()
    kind = (row.get("primary_kind") or "").strip()
    raw_acq_dir = os.path.normpath(os.path.join(nas_root, canonical.lstrip("/")))
    if primary and kind == "folder" and primary != acq_id:
        return os.path.join(raw_acq_dir, primary)
    if primary and kind == "folder":
        return raw_acq_dir
    if primary and not primary.endswith("/"):
        return os.path.join(raw_acq_dir, primary)
    return raw_acq_dir


def relink_project(project_abs, registry, dry_run=False, keep_lnk=False):
    """Convert every `.lnk` in <project>/raw_linked/ to a hard link.

    Returns a dict of counters.
    """
    raw_linked = os.path.join(project_abs, "raw_linked")
    prov_path = os.path.join(project_abs, "provenance.csv")
    stats = {"lnk": 0, "file_links": 0, "folder_links": 0, "deleted": 0,
             "skipped": 0, "errors": 0}
    if not os.path.isdir(raw_linked):
        return stats

    lnk_to_acq = load_lnk_to_acq(prov_path)
    lnks = sorted(f for f in os.listdir(raw_linked) if f.lower().endswith(".lnk"))
    stats["lnk"] = len(lnks)

    for lnk in lnks:
        link_name = lnk[:-4]  # strip ".lnk"
        acq_id = lnk_to_acq.get(lnk)
        if not acq_id:
            print(f"    SKIP {lnk}: no ACQ-ID in provenance.csv")
            stats["skipped"] += 1
            continue
        row = registry.get(acq_id)
        if not row:
            print(f"    SKIP {lnk}: ACQ-ID {acq_id} not in registry_raw.csv")
            stats["skipped"] += 1
            continue
        src = raw_primary_path(NAS_ROOT, row)
        is_folder = os.path.isdir(src)
        kind = "folder" if is_folder else "file"
        if dry_run:
            print(f"    [dry-run] {lnk}  ->  hard {kind} 'raw_linked/{link_name}'  (src: {src})")
            stats["folder_links" if is_folder else "file_links"] += 1
            continue
        try:
            dest = linker.create_hardlink(project_abs, link_name, src)
            if not os.path.exists(dest):
                raise RuntimeError(f"hard link not present after creation: {dest}")
            stats["folder_links" if is_folder else "file_links"] += 1
            # Provenance row for the new hard link (output_path has no .lnk,
            # so it does not collide with the legacy shortcut's row).
            is_dir_link = os.path.isdir(dest)
            provenance.append_entry(prov_path, {
                "output_path": f"raw_linked/{link_name}",
                "output_name": link_name,
                "file_type": "hardlink-folder" if is_dir_link else "hardlink",
                "date_created": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "creator": row.get("operator", "") or "",
                "input_refs": acq_id,
                "process_description": (
                    "Migrated from .lnk to hard link (relink_projects.py): "
                    + ("folder of per-file hard links" if is_dir_link else "hard link")
                ),
                "software_version": provenance.software_version_string("relink_projects.py"),
                "parameters_ref": row.get("ingest_config", "") or "",
                "lab_notebook_ref": "",
                "notes": "Auto-generated during .lnk -> hard-link migration",
            })
            if not keep_lnk:
                os.remove(os.path.join(raw_linked, lnk))
                stats["deleted"] += 1
            print(f"    OK   {lnk}  ->  hard {kind} 'raw_linked/{link_name}'")
        except Exception as e:  # noqa: BLE001 - report and continue
            print(f"    ERROR {lnk}: {e}")
            stats["errors"] += 1
    return stats


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--nas-root", default=os.environ.get("GJESUS3_ROOT", "J:/gjesus3-data"),
                    help="NAS container root (default $GJESUS3_ROOT or J:/gjesus3-data)")
    ap.add_argument("--project", action="append", default=None,
                    help="Limit to this project folder name (repeatable)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Report actions without creating/deleting anything")
    ap.add_argument("--keep-lnk", action="store_true",
                    help="Create hard links but leave the .lnk files in place")
    args = ap.parse_args(argv)

    global NAS_ROOT
    NAS_ROOT = os.path.normpath(args.nas_root)
    projects_dir = os.path.join(NAS_ROOT, "projects")
    if not os.path.isdir(projects_dir):
        ap.error(f"projects dir not found under nas-root: {projects_dir}")

    registry = load_registry_index(NAS_ROOT)

    names = args.project or sorted(
        d for d in os.listdir(projects_dir)
        if os.path.isdir(os.path.join(projects_dir, d))
    )

    print(f"NAS root: {NAS_ROOT}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}"
          f"{' (keeping .lnk)' if args.keep_lnk else ''}")
    totals = {"lnk": 0, "file_links": 0, "folder_links": 0, "deleted": 0,
              "skipped": 0, "errors": 0}
    for name in names:
        project_abs = os.path.join(projects_dir, name)
        print(f"\n== {name} ==")
        s = relink_project(project_abs, registry,
                           dry_run=args.dry_run, keep_lnk=args.keep_lnk)
        for k in totals:
            totals[k] += s[k]
        print(f"   {name}: {s['lnk']} .lnk -> "
              f"{s['file_links']} file + {s['folder_links']} folder links, "
              f"{s['deleted']} .lnk removed, {s['skipped']} skipped, {s['errors']} errors")

    print("\n" + "=" * 60)
    print(f"TOTAL: {totals['lnk']} .lnk processed | "
          f"{totals['file_links']} file links | {totals['folder_links']} folder links | "
          f"{totals['deleted']} .lnk removed | {totals['skipped']} skipped | "
          f"{totals['errors']} errors")
    return 1 if totals["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
