#!/usr/bin/env python3
"""Drain registries/pending_links.csv — create the deferred project hard links.

Context
-------
The project link is a hard link into `<project>/raw_linked/` (zero extra storage,
same inode as the raw primary). Hard links need a hard-link-capable mount: NTFS/SMB
**from Windows** works, but the NI acquisition console is a **Mac**, and macOS over
SMB refuses `os.link` (`ENOTSUP`/`[Errno 45]`). So an on-box NI ingest registers every
acquisition correctly but cannot make the `raw_linked/` link; each such acquisition is
queued to `registries/pending_links.csv` (see `tools/ingest/pending_links.py`).

This tool reads that worklist and, **run from a hard-link-capable machine** (the
Windows workstation mounting the same NAS — proven by the historical
`tools/relink_mri_regen.py` pass), creates the real hard link for each `pending` row
using exactly the same `linker.create_hardlink` that ingest uses. On success it removes
the `<link_name>.PENDING-LINK.txt` stand-in, writes the provenance entry, and flips the
row's `status` to `linked`. Idempotent: an already-present link is left as-is and the
row is still marked `linked`.

Usage (from Windows)
--------------------
    python tools/relink_pending.py --nas-root J:/gjesus3-sandbox --dry-run
    python tools/relink_pending.py --nas-root J:/gjesus3-data
"""
import argparse
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ingest import linker, pending_links, provenance  # noqa: E402


def main(argv):
    ap = argparse.ArgumentParser(
        description="Create the deferred project hard links queued in pending_links.csv."
    )
    ap.add_argument("--nas-root", required=True,
                    help="Hard-link-capable NAS mount (e.g. J:/gjesus3-data).")
    ap.add_argument("--dry-run", action="store_true",
                    help="Report what would be linked; create nothing, write nothing.")
    args = ap.parse_args(argv[1:])

    nas_root = os.path.normpath(args.nas_root)
    registries = os.path.join(nas_root, "registries")
    path = pending_links.pending_links_path(registries)
    rows = pending_links.read_pending_links(path)
    if not rows:
        print(f"No pending_links.csv (or it's empty) under {registries} — nothing to do.")
        return 0

    pending = [r for r in rows if (r.get("status") or "").strip() != "linked"]
    print(f"{len(rows)} row(s) in {path}; {len(pending)} pending.")

    linked = 0
    failed = 0
    for r in pending:
        acq = r.get("acq_id", "")
        project_id = (r.get("project_id") or "").strip()
        link_name = (r.get("link_name") or "").strip()
        raw_rel = (r.get("raw_primary_canonical") or "").strip()

        folder_rel = linker.lookup_project_folder(
            os.path.join(registries, "registry_projects.csv"), project_id
        )
        if not folder_rel:
            print(f"  SKIP {acq}: project {project_id!r} not in registry_projects.csv")
            failed += 1
            continue

        project_folder_abs = os.path.normpath(os.path.join(nas_root, folder_rel.lstrip("/")))
        raw_primary_abs = os.path.normpath(os.path.join(nas_root, raw_rel.lstrip("/")))

        if not os.path.exists(raw_primary_abs):
            print(f"  SKIP {acq}: raw primary missing: {raw_primary_abs}")
            failed += 1
            continue

        if args.dry_run:
            dest = os.path.join(project_folder_abs, "raw_linked", link_name)
            print(f"  [dry-run] would link {acq} -> {dest}")
            continue

        try:
            link_path = linker.create_hardlink(project_folder_abs, link_name, raw_primary_abs)
        except OSError as e:
            print(f"  FAIL {acq}: {e} (is this mount hard-link-capable?)")
            failed += 1
            continue

        is_dir_link = os.path.isdir(link_path)
        # Remove the cosmetic stand-in pointer now that the real link exists.
        ptr = os.path.join(project_folder_abs, "raw_linked", f"{link_name}.PENDING-LINK.txt")
        try:
            if os.path.exists(ptr):
                os.remove(ptr)
        except OSError:
            pass

        # Provenance entry, identical in shape to the ingest-time link entry
        # (idempotent on output_path — re-running won't duplicate it).
        prov_path = os.path.join(project_folder_abs, "provenance.csv")
        try:
            provenance.append_entry(prov_path, {
                "output_path":         f"raw_linked/{link_name}",
                "output_name":         link_name,
                "file_type":           "hardlink-folder" if is_dir_link else "hardlink",
                "date_created":        datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "creator":             "",
                "input_refs":          acq,
                "process_description": (
                    "Deferred relink pass (tools/relink_pending.py): folder of "
                    "per-file hard links to raw acquisition"
                    if is_dir_link else
                    "Deferred relink pass (tools/relink_pending.py): hard link to "
                    "raw acquisition"
                ),
                "software_version":    provenance.software_version_string("relink_pending.py"),
                "parameters_ref":      "",
                "lab_notebook_ref":    "",
                "notes":               "Created from registries/pending_links.csv",
            })
        except Exception as e:
            print(f"  WARN {acq}: link made but provenance append failed: {e}")

        r["status"] = "linked"
        linked += 1
        kind = "folder of per-file hard links" if is_dir_link else "hard link"
        print(f"  OK   {acq}: {kind} -> {link_path}")

    if not args.dry_run:
        pending_links._write_all(path, rows)

    print(f"\nDone. linked={linked}  failed/skipped={failed}  "
          f"{'(dry-run — nothing written)' if args.dry_run else ''}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
