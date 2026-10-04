#!/usr/bin/env python3
"""Pre-write check (stream F's hazard, 2026-10-04): linker.create_hardlink does makedirs(exist_ok)
and links only missing files, so a link-folder name that is already taken SILENTLY MERGES two
acquisitions. For an MRI batch config + its case table + staging, compute every planned link name
  MRI_<sample_id>_<acq_date>_<exam>_<recon indices>
exactly as the production template does (recon indices = the pdata/<idx> with DICOM in the staged
exam, comma-joined), and check it case-insensitively against (a) the project's existing
raw_linked\\ entries and (b) the other names in the batch. Exit 1 on any collision. Read-only.
usage: check_link_collisions.py <staging_dir> <cases.csv> <project folder> <sample_id template: e.g. m{animal}_1519>
"""
import csv, glob, os, re, sys

def main(staging, cases, project_dir, sample_tpl):
    existing = {n.lower() for n in os.listdir(os.path.join(project_dir, "raw_linked"))}
    planned, bad = {}, []
    for r in csv.DictReader(open(cases, encoding="utf-8")):
        on = r["original_name"]; study, exam = on.rsplit("/", 1)
        m = re.search(r"_m(\d+)", study)
        sample = sample_tpl.format(animal=m.group(1) if m else "")
        acq_date = r["drv_acq_datetime"][:10].replace("-", "")
        ex = os.path.join(staging, *on.split("/"))
        # mri_recon_indices = EVERY pdata/<idx>/ subdirectory (paravision_metadata._recon_indices),
        # not only those holding DICOM.
        pd_root = os.path.join(ex, "pdata")
        idx = sorted((d for d in os.listdir(pd_root) if os.path.isdir(os.path.join(pd_root, d))),
                     key=lambda x: int(x) if x.isdigit() else x) if os.path.isdir(pd_root) else []
        name = f"MRI_{sample}_{acq_date}_{exam}_{','.join(idx)}"
        if not glob.glob(os.path.join(ex, "pdata", "*", "dicom", "*.dcm")):
            bad.append(f"NO-DICOM {on} -> {name}")
        k = name.lower()
        if k in existing:
            bad.append(f"COLLIDES-WITH-PROJECT {on} -> {name}")
        if k in planned:
            bad.append(f"COLLIDES-WITHIN-BATCH {on} and {planned[k]} -> {name}")
        planned[k] = on
    print(f"planned {len(planned)} link names; existing in project {len(existing)}; problems {len(bad)}")
    for b in bad[:30]:
        print("  ", b)
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main(*sys.argv[1:5])
