#!/usr/bin/env python3
"""One-off: disambiguate AxioScan project links for slides re-scanned across date folders.

The AxioScan link name is ZWSI_<original-basename> and the filename carries no scan
date (the date is the parent folder). So the SAME slide scanned/exported on multiple
days collides on one link name and only the first acq gets a distinct project hard
link (a single-file link is a silent no-op when the dest exists). 15 slide-filenames
appear in 2-3 date folders each -> 36 acqs across those groups.

This appends the acq date to the link name for every acq in a collision group:
    ZWSI_<stem>_<YYYYMMDD>.czi
and removes the ambiguous date-less ZWSI_<basename> link, so each re-scan has exactly
one distinct, dated project link. /raw/ is untouched (links are extra hard links to
the same inode). Idempotent. Run from Windows (J:/, where os.link works).

    python tools/relink_axioscan_collisions.py --nas-root J:/gjesus3-data --dry-run
    python tools/relink_axioscan_collisions.py --nas-root J:/gjesus3-data
"""
import argparse, csv, os, sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ingest import linker, provenance  # noqa: E402


def load_projects_index(nas):
    idx = {}
    with open(os.path.join(nas, "registries", "registry_projects.csv"),
              encoding="utf-8", errors="replace", newline="") as f:
        for r in csv.DictReader(f):
            idx[r["project_id"].strip()] = (r.get("folder_location") or "").strip()
    return idx


def raw_file_path(nas, row):
    acq_dir = os.path.normpath(os.path.join(nas, (row.get("canonical_path") or "").lstrip("/")))
    return os.path.join(acq_dir, (row.get("primary_file_name") or "").strip())


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--nas-root", default="J:/gjesus3-data")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    nas = os.path.normpath(args.nas_root)
    proj_idx = load_projects_index(nas)

    with open(os.path.join(nas, "registries", "registry_raw.csv"),
              encoding="utf-8", errors="replace", newline="") as f:
        zwsi = [r for r in csv.DictReader(f) if r["instrument"] == "ZWSI"]

    # Group case-INsensitively: Windows links are case-insensitive, so
    # "..._10X.czi" and "..._10x.czi" (same slide, mag-case drift) collide too.
    groups = defaultdict(list)
    for r in zwsi:
        b = os.path.basename((r.get("original_name") or "").replace("\\", "/"))
        groups[b.lower()].append(r)
    colliding = {b: rs for b, rs in groups.items() if len(rs) > 1}

    stats = {"groups": len(colliding), "linked": 0, "skipped_exist": 0,
             "removed_dateless": 0, "errors": 0}
    print(f"collision groups: {stats['groups']}  (nas={nas}, dry_run={args.dry_run})")

    for _key, rs in colliding.items():
        # project_abs -> set of ACTUAL (case-preserving) basenames to clean up
        proj_folders = defaultdict(set)
        for r in rs:
            acq = r["acq_id"]
            date = acq.split("-")[1] if acq.count("-") >= 2 else ""
            actual_b = os.path.basename((r.get("original_name") or "").replace("\\", "/"))
            stem = actual_b[:-4] if actual_b.lower().endswith(".czi") else actual_b
            ext = actual_b[len(stem):]
            link_name = f"ZWSI_{stem}_{date}{ext}"
            folder_rel = proj_idx.get((r.get("project_hint") or "").strip(), "")
            if not folder_rel:
                print(f"  ERROR {acq}: project {r.get('project_hint')!r} not found")
                stats["errors"] += 1
                continue
            project_abs = os.path.normpath(os.path.join(nas, folder_rel.lstrip("/")))
            proj_folders[project_abs].add(actual_b)
            src = raw_file_path(nas, r)
            dest = os.path.join(project_abs, "raw_linked", link_name)
            if os.path.exists(dest):
                stats["skipped_exist"] += 1
                continue
            if args.dry_run:
                print(f"  [dry-run] {acq} -> raw_linked/{link_name}")
                stats["linked"] += 1
                continue
            try:
                made = linker.create_hardlink(project_abs, link_name, src)
                if not os.path.exists(made):
                    raise RuntimeError("link missing after create")
                provenance.append_entry(os.path.join(project_abs, "provenance.csv"), {
                    "output_path": f"raw_linked/{link_name}",
                    "output_name": link_name,
                    "file_type": "hardlink",
                    "date_created": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    "creator": r.get("operator", "") or "",
                    "input_refs": acq,
                    "process_description": (
                        "Date-disambiguated project link (relink_axioscan_collisions.py): "
                        "same slide re-scanned across date folders -> appended acq date"),
                    "software_version": provenance.software_version_string("relink_axioscan_collisions.py"),
                    "parameters_ref": r.get("ingest_config", "") or "",
                    "lab_notebook_ref": "",
                    "notes": "Auto: AxioScan link-name collision (date-less link name); appended YYYYMMDD",
                })
                stats["linked"] += 1
                print(f"  NEW {acq} -> raw_linked/{link_name}")
            except Exception as e:  # noqa: BLE001
                print(f"  ERROR {acq}: {e}")
                stats["errors"] += 1
        # drop the ambiguous date-less link(s) ZWSI_<basename> in each project
        for project_abs, basenames in proj_folders.items():
            for ab in basenames:
                old = os.path.join(project_abs, "raw_linked", f"ZWSI_{ab}")
                if os.path.exists(old):
                    if args.dry_run:
                        print(f"  [dry-run] remove date-less raw_linked/ZWSI_{ab}")
                    else:
                        os.remove(old)
                        print(f"  removed date-less raw_linked/ZWSI_{ab}")
                    stats["removed_dateless"] += 1

    print("\nSUMMARY")
    for k, v in stats.items():
        print(f"  {k:16s} {v}")
    return stats


if __name__ == "__main__":
    main()
