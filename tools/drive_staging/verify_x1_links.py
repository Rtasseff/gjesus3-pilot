#!/usr/bin/env python3
"""Strict post-check for the X1 one-off (generic DICOM shape, <ACQ-ID>/series/): each row's link
raw_linked\\<expected name> holds exactly its own series/ files, all os.path.samefile. Read-only.
usage: verify_x1_links.py <nas_root>"""
import csv, os, sys
CFG = "tools/configs/drives_2026-09/dicom/dicom_X1_oneoff_acqpless.yaml"
def main(nas):
    projects = {p["project_id"]: p["folder_location"] for p in csv.DictReader(open(os.path.join(nas, "registries", "registry_projects.csv"), encoding="utf-8-sig"))}
    rows = [r for r in csv.DictReader(open(os.path.join(nas, "registries", "registry_raw.csv"), encoding="utf-8-sig")) if r["ingest_config"].replace("\\", "/") == CFG]
    bad = []
    for r in rows:
        src = os.path.join(nas, r["canonical_path"].strip("/"), r["primary_file_name"].strip("/"))
        files = sorted(os.listdir(src)) if os.path.isdir(src) else []
        on = r["original_name"]; study, exam = on.rsplit("__", 1)
        animal = study.split("_m")[1].split("_")[0]; proto = "1519" if "1519" in study else "0619"
        name = f"MRI_m{animal}_{proto}_{r['acq_id'].split('-')[1]}_{exam}_dicom"
        ldir = os.path.join(nas, projects[r["project_id"]].strip("/"), "raw_linked", name)
        lf = sorted(os.listdir(ldir)) if os.path.isdir(ldir) else None
        if lf is None: bad.append(f"{r['acq_id']} no link {name}"); continue
        if lf != files or not all(os.path.samefile(os.path.join(src, f), os.path.join(ldir, f)) for f in files):
            bad.append(f"{r['acq_id']} {name}: link {len(lf)} vs series {len(files)}")
        print(f"{r['acq_id']} {on} -> {name}: {len(files)} files")
    print(f"rows {len(rows)}; problems {len(bad)}"); [print("  ", b) for b in bad]
    sys.exit(1 if bad or len(rows) != 3 else 0)
if __name__ == "__main__":
    main(sys.argv[1])
