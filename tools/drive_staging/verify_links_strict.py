#!/usr/bin/env python3
"""Post-write check against silent link merges (stream F's hazard). For every registry row of one
ingest config with a project: its link folder raw_linked\\<expected name> must hold EXACTLY the
acquisition's own .dcm files: the same count, every file os.path.samefile with /raw/, and no extra
file. The expected name is rebuilt as MRI_<sample_id>_<ACQ-ID date>_<exam>_<recon indices from
the .data/ file names>. Read-only. Exit 1 on any problem.
usage: verify_links_strict.py <nas_root> <ingest_config relpath>"""
import csv, json, os, re, sys

def main(nas, cfg):
    projects = {p["project_id"]: p["folder_location"] for p in csv.DictReader(open(os.path.join(nas, "registries", "registry_projects.csv"), encoding="utf-8-sig"))}
    rows = [r for r in csv.DictReader(open(os.path.join(nas, "registries", "registry_raw.csv"), encoding="utf-8-sig"))
            if r["ingest_config"].replace("\\", "/") == cfg and r["project_id"]]
    ok, bad = 0, []
    for r in rows:
        data = os.path.join(nas, r["canonical_path"].strip("/"), r["primary_file_name"])
        dcms = sorted(f for f in os.listdir(data) if f.lower().endswith(".dcm"))
        # the link template's recon part = sidecar mri.reconstruction.indices_present (every pdata/<idx>)
        side = json.load(open(os.path.join(nas, r["canonical_path"].strip("/"), "metadata.json"), encoding="utf-8"))
        idx = [str(x) for x in ((side.get("mri") or {}).get("reconstruction") or {}).get("indices_present") or []]
        exam = r["original_name"].replace("\\", "/").rstrip("/").split("/")[-1]
        name = f"MRI_{r['sample_id']}_{r['acq_id'].split('-')[1]}_{exam}_{','.join(idx)}"
        ldir = os.path.join(nas, projects[r["project_id"]].strip("/"), "raw_linked", name)
        if not os.path.isdir(ldir):
            bad.append(f"{r['acq_id']}: no link folder {name}"); continue
        lf = sorted(os.listdir(ldir))
        extra = [f for f in lf if f not in dcms]
        miss = [f for f in dcms if f not in lf]
        notsame = [f for f in dcms if f in lf and not os.path.samefile(os.path.join(data, f), os.path.join(ldir, f))]
        if extra or miss or notsame:
            bad.append(f"{r['acq_id']} {name}: extra {len(extra)} missing {len(miss)} not-samefile {len(notsame)}")
        else:
            ok += 1
    print(f"rows with project {len(rows)}; link folders exact {ok}; problems {len(bad)}")
    for b in bad[:20]:
        print("  ", b)
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main(*sys.argv[1:3])
