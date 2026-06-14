#!/usr/bin/env python3
"""One-off: create the project hard-links for the MRI no-DICOM regeneration batch.

Context
-------
The full no-DICOM regeneration run (2026-06-14, configs
`mri_jrc_animalfirst_regen.yaml` + `mri_jrc_projfirst_regen.yaml`) had to run from
WSL because Dicomifier is Linux-only. Over the CIFS NAS mount, `os.link` is refused
(`EPERM`), so the ~3,297 regenerated MRI acquisitions landed in `/raw/` correctly
(copied, verified, checksummed, registry row appended) but got **no project hard-link**.

The stock `relink_projects.py --create-missing` cannot rebuild these: the MRI
`link_filename` template needs `discovered.*` fields that aren't stored in the
registry, so it emits an unresolved `${discovered.mri_exam_number}` name and skips
every row. This script sources those two fields from data already on the NAS and
creates the links from Windows (the `J:` drive, where `os.link` works):

  - mri_exam_number   = basename(original_name)                         [registry]
  - mri_recon_indices = metadata.json -> mri.reconstruction.indices_present [sidecar]
                        fallback: distinct `recon<X>` prefixes in <ACQ>.data/

  link name = "MRI_<sample_id>_<acq_date>_<exam>_<recon>"   (matches the ingest name)

It is idempotent (skips any acq whose link already exists or whose `.data/` is empty —
spectroscopy/placeholder acqs already got an empty link folder at ingest time), and is
scoped to just the two regen configs so it never touches the earlier DICOM-bearing rows.

Usage (from Windows)
--------------------
    python tools/relink_mri_regen.py --nas-root J:/gjesus3-data --dry-run
    python tools/relink_mri_regen.py --nas-root J:/gjesus3-data
"""
import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ingest import linker, provenance  # noqa: E402

# Only the two no-DICOM regeneration batches (substring match on the ingest_config relpath).
REGEN_CONFIG_MARKERS = ("mri_jrc_animalfirst_regen", "mri_jrc_projfirst_regen")


def load_projects_index(nas_root):
    """PROJ-ID -> folder_location (e.g. '/projects/proj-ae-biomegune-0618/')."""
    path = os.path.join(nas_root, "registries", "registry_projects.csv")
    idx = {}
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        for r in csv.DictReader(f):
            idx[r["project_id"].strip()] = (r.get("folder_location") or "").strip()
    return idx


def raw_data_dir(nas_root, row):
    """Path to the acquisition's `<ACQ-ID>.data` folder (the hard-link source)."""
    raw_acq_dir = os.path.normpath(
        os.path.join(nas_root, (row.get("canonical_path") or "").lstrip("/"))
    )
    primary = (row.get("primary_file_name") or "").strip()
    return os.path.join(raw_acq_dir, primary) if primary else raw_acq_dir


def recon_indices(acq_dir, data_dir):
    """Comma-list of recons kept — from the sidecar, falling back to the .data files."""
    meta = os.path.join(acq_dir, "metadata.json")
    try:
        with open(meta, "r", encoding="utf-8") as f:
            d = json.load(f)
        ip = (((d.get("mri") or {}).get("reconstruction") or {}).get("indices_present"))
        if ip:
            return ",".join(str(x) for x in ip)
    except (OSError, ValueError):
        pass
    pre = set()
    if os.path.isdir(data_dir):
        for fn in os.listdir(data_dir):
            if fn.startswith("recon") and "_frame" in fn:
                pre.add(fn.split("_frame")[0][len("recon"):])
    return ",".join(sorted(pre))


def has_dicoms(data_dir):
    return os.path.isdir(data_dir) and any(
        fn.lower().endswith(".dcm") for fn in os.listdir(data_dir)
    )


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nas-root", default=os.environ.get("GJESUS3_ROOT", "J:/gjesus3-data"))
    ap.add_argument("--dry-run", action="store_true",
                    help="report intended links without creating anything")
    args = ap.parse_args(argv)
    nas = os.path.normpath(args.nas_root)

    proj_idx = load_projects_index(nas)
    reg_path = os.path.join(nas, "registries", "registry_raw.csv")
    with open(reg_path, "r", encoding="utf-8", errors="replace", newline="") as f:
        rows = [r for r in csv.DictReader(f)
                if (r.get("instrument") or "").strip() == "MRI"
                and any(m in (r.get("ingest_config") or "") for m in REGEN_CONFIG_MARKERS)]

    stats = {"matched": len(rows), "created": 0, "skipped_complete": 0,
             "skipped_empty": 0, "errors": 0}
    print(f"MRI regen rows matched: {stats['matched']}  (nas={nas}, "
          f"dry_run={args.dry_run})")

    for row in rows:
        acq_id = row["acq_id"]
        sample_id = (row.get("sample_id") or "").strip()
        acq_date = acq_id.split("-")[1] if acq_id.count("-") >= 2 else ""
        exam = (row.get("original_name") or "").replace("\\", "/").rstrip("/").split("/")[-1]
        proj_id = (row.get("project_hint") or "").strip()
        folder_rel = proj_idx.get(proj_id, "")
        if not folder_rel:
            print(f"  ERROR {acq_id}: project {proj_id!r} not in registry_projects.csv")
            stats["errors"] += 1
            continue
        project_abs = os.path.normpath(os.path.join(nas, folder_rel.lstrip("/")))
        acq_dir = os.path.normpath(os.path.join(nas, (row.get("canonical_path") or "").lstrip("/")))
        data_dir = raw_data_dir(nas, row)

        if not has_dicoms(data_dir):
            stats["skipped_empty"] += 1   # spectroscopy / placeholder — already empty-linked
            continue

        recon = recon_indices(acq_dir, data_dir)
        link_name = f"MRI_{sample_id}_{acq_date}_{exam}_{recon}"
        if not sample_id or not exam or not recon or "${" in link_name \
                or "/" in link_name or "\\" in link_name:
            print(f"  ERROR {acq_id}: bad link name {link_name!r}")
            stats["errors"] += 1
            continue

        raw_linked = os.path.join(project_abs, "raw_linked")
        dest = os.path.join(raw_linked, link_name)
        # NB: the WSL run left EMPTY link-folder shells (parent dir created, then
        # os.link EPERM'd on the first file). So existence != complete — compare
        # the DICOM count. create_hardlink is idempotent (links only missing files).
        src_n = sum(1 for fn in os.listdir(data_dir) if fn.lower().endswith(".dcm"))
        dst_n = (sum(1 for fn in os.listdir(dest) if fn.lower().endswith(".dcm"))
                 if os.path.isdir(dest) else 0)
        if dst_n >= src_n:
            stats["skipped_complete"] += 1
            continue
        if args.dry_run:
            print(f"  [dry-run] {acq_id} -> raw_linked/{link_name}  (have {dst_n}/{src_n})")
            stats["created"] += 1
            continue

        try:
            os.makedirs(raw_linked, exist_ok=True)
            made = linker.create_hardlink(project_abs, link_name, data_dir)
            made_n = (sum(1 for fn in os.listdir(made) if fn.lower().endswith(".dcm"))
                      if os.path.isdir(made) else 0)
            if made_n < src_n:
                raise RuntimeError(f"only {made_n}/{src_n} hard links present after creation")
            provenance.append_entry(os.path.join(project_abs, "provenance.csv"), {
                "output_path": f"raw_linked/{link_name}",
                "output_name": link_name,
                "file_type": "hardlink-folder",
                "date_created": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "creator": row.get("operator", "") or "",
                "input_refs": acq_id,
                "process_description": (
                    "Created missing project link (relink_mri_regen.py): folder of "
                    "per-file hard links — no-DICOM regen ran from WSL where os.link "
                    "is refused over CIFS"
                ),
                "software_version": provenance.software_version_string("relink_mri_regen.py"),
                "parameters_ref": row.get("ingest_config", "") or "",
                "lab_notebook_ref": "",
                "notes": "Auto-generated: link missing after WSL regen (EPERM on CIFS hard link)",
            })
            stats["created"] += 1
            if stats["created"] % 200 == 0:
                print(f"  ... {stats['created']} links created")
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR {acq_id}: {e}")
            stats["errors"] += 1

    print("\nSUMMARY")
    for k, v in stats.items():
        print(f"  {k:16s} {v}")
    return stats


if __name__ == "__main__":
    main()
