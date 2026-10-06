#!/usr/bin/env python3
"""Strict post-check for the X1 one-off (generic DICOM shape: primary "series/", primary_kind archive).
For this layout the engine hard-links the WHOLE acquisition folder (README.txt, checksums.json,
metadata.json, series/), unlike the internal-MRI .data/ links, which hold DICOMs only (found at
the X1 write, 2026-10-04). So each row's raw_linked\\<expected name> must be an exact mirror of its
OWN /raw/ acquisition folder: the same relative file set, every file os.path.samefile. Read-only.
usage: verify_x1_links.py <nas_root>"""
import csv, os, sys
CFG = "tools/configs/drives_2026-09/dicom/dicom_X1_oneoff_acqpless.yaml"

def tree(root):
    return {os.path.relpath(os.path.join(d, f), root).replace("\\", "/") for d, _s, fs in os.walk(root) for f in fs}

def main(nas):
    projects = {p["project_id"]: p["folder_location"] for p in csv.DictReader(open(os.path.join(nas, "registries", "registry_projects.csv"), encoding="utf-8-sig"))}
    rows = [r for r in csv.DictReader(open(os.path.join(nas, "registries", "registry_raw.csv"), encoding="utf-8-sig")) if r["ingest_config"].replace("\\", "/") == CFG]
    bad = []
    for r in rows:
        acq = os.path.join(nas, r["canonical_path"].strip("/"))
        study, exam = r["original_name"].rsplit("__", 1)
        animal = study.split("_m")[1].split("_")[0]; proto = "1519" if "1519" in study else "0619"
        name = f"MRI_m{animal}_{proto}_{r['acq_id'].split('-')[1]}_{exam}_dicom"
        ldir = os.path.join(nas, projects[r["project_id"]].strip("/"), "raw_linked", name)
        if not os.path.isdir(ldir):
            bad.append(f"{r['acq_id']} no link {name}"); continue
        ta, tb = tree(acq), tree(ldir)
        dcm = sum(1 for f in ta if f.lower().endswith(".dcm"))
        notsame = [f for f in ta & tb if not os.path.samefile(os.path.join(acq, f), os.path.join(ldir, f))]
        if ta != tb or notsame:
            bad.append(f"{r['acq_id']} {name}: raw {len(ta)} vs link {len(tb)}, not-samefile {len(notsame)}")
        print(f"{r['acq_id']} -> {name}: {len(tb)} files ({dcm} DICOM), exact mirror {ta == tb and not notsame}")
    print(f"rows {len(rows)}; problems {len(bad)}")
    for b in bad:
        print("  ", b)
    sys.exit(1 if bad or len(rows) != 3 else 0)

if __name__ == "__main__":
    main(sys.argv[1])
