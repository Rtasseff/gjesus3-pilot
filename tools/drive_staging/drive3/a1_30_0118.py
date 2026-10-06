"""A1 step 3: protocol 0118 (MRI\\Proyecto 0118 (Ratas hipoxia)) in detail, and against K:\\gjesus\\MRI.

Per study: date, animal (and the facility DB's species / MRI date, from a1_24's lookups), exams
and their A1 classes, DICOM / 2dseq / k-space presence, reconstruction sets, scan types, bytes.

Then K:\\gjesus\\MRI\\Proyecto 0118 (read-only): every study folder there is listed; for a study
whose NAME is also on the drive, every file is SHA-256-hashed and compared inner path by inner
path; for the others only each exam's `acqp` is hashed (an acqp carries the acquisition's own
timestamps, so identical acqp bytes = the same acquisition under another name).

Writes a1\\p0118_studies.csv, a1\\p0118_exams.csv, a1\\p0118_vs_K.csv, a1\\p0118_summary.txt.

    python a1_30_0118.py
"""
import collections
import json
import os

from a1_common import CACHE, cache_load, gb, out_path, sha256_file, lp, write_csv

K_0118 = r"K:\gjesus\MRI\Proyecto 0118"


def walk_k(root):
    """study folder name -> {inner relpath: (abs path, size)} under K:\\...\\Proyecto 0118 (listing only)."""
    studies = {}
    for name in sorted(os.listdir(lp(root))):
        p = os.path.join(root, name)
        if not os.path.isdir(lp(p)):
            continue
        files = {}
        for dp, dn, fn in os.walk(lp(p)):
            for f in fn:
                ap = os.path.join(dp, f)
                rel = os.path.relpath(ap, lp(p))
                files[rel] = (ap, os.path.getsize(ap))
        studies[name] = files
    return studies


def main():
    rows = cache_load("mri_exam_rows")
    copies = cache_load("mri_copies")
    keys = cache_load("mri_keys")
    db = json.load(open(os.path.join(CACHE, "db_lookups.json"), encoding="utf-8"))
    p0118 = [r for r in rows if "0118" in r["path_claim_nearest"].split(";")]
    studies = collections.defaultdict(list)
    for r in p0118:
        studies[r["study"]].append(r)
    ex_rows, st_rows = [], []
    from a1_24_mri_projects import parse_animal_codes
    df = cache_load("files")
    for st, rs in sorted(studies.items()):
        animal, sp, _ = parse_animal_codes(st)
        d = db.get(f"0118|{int(animal)}", {}) if animal else {}
        mri_dates = sorted({p["date"][:10] for p in d.get("procedures", []) if "MRI" in p["type"].upper()})
        pet_dates = sorted({p["date"][:10] for p in d.get("procedures", []) if "PET" in p["type"].upper()})
        cc = collections.Counter(r["class"] for r in rs)
        scans = collections.Counter(r["method"].replace("Bruker:", "") for r in rs)
        shas = set()
        for r in rs:
            for e in keys[r["exam_key"]]:
                shas.update(copies[e]["inner"].values())
        st_rows.append({
            "study": st, "date": rs[0]["study_date"], "animal": animal, "name_prefix": sp,
            "db_species": d.get("species", ""), "db_status": d.get("status", ""),
            "db_mri_dates": ";".join(mri_dates), "db_pet_dates": ";".join(pet_dates),
            "subject_id_in_file": rs[0]["subject_id"], "exams": len(rs),
            "a": cc["a"], "b": cc["b"], "c": cc["c"], "d": cc["d"], "e": cc["e"],
            "exams_with_dicom": sum(1 for r in rs if int(r["n_dcm"]) > 0),
            "dicom_files": sum(int(r["n_dcm"]) for r in rs),
            "exams_with_2dseq": sum(1 for r in rs if r["seq_recons"]),
            "exams_with_kspace": sum(1 for r in rs if r["kspace"] == "Y"),
            "recon_sets_without_dicom": sum(1 for r in rs if set(r["seq_recons"].split(";")) - set(r["dcm_recons"].split(";")) - {""}),
            "methods": "; ".join(f"{k} {v}" for k, v in scans.most_common()),
            "station": ";".join(sorted({r["station"] for r in rs})), "pv": ";".join(sorted({r["pv"] for r in rs})),
            "copies": rs[0]["n_copies"], "location": rs[0]["canonical_dir"].rsplit("\\", 2)[0],
            "dicom_bytes": sum(int(r["dcm_bytes"]) for r in rs),
            "distinct_bytes": sum(int(r["distinct_bytes_all_copies"]) for r in rs),
        })
        for r in rs:
            ex_rows.append({k: r[k] for k in ("exam_key", "class", "class_detail", "scan_name", "method", "acq_time",
                                             "n_dcm", "dcm_recons", "seq_recons", "kspace", "dcm_bytes", "bytes",
                                             "station", "pv", "canonical_dir")})
    write_csv("p0118_studies.csv", st_rows, list(st_rows[0].keys()))
    write_csv("p0118_exams.csv", ex_rows, list(ex_rows[0].keys()))

    # ---- K: comparison
    k = walk_k(K_0118)
    drive_acqp = {}
    for r in rows:
        c = next(copies[e] for e in keys[r["exam_key"]] if copies[e]["canonical"])
        if c["acqp_sha"]:
            drive_acqp.setdefault(c["acqp_sha"], set()).add(r["exam_key"])
    kc = []
    for name, files in sorted(k.items()):
        on_drive = name in studies or name in {r["study"] for r in rows}
        if on_drive:
            # hash every file of the K: copy, compare with every drive copy of the same study
            dcopies = sorted({copies[e]["study_dir"] for r in rows if r["study"] == name for e in keys[r["exam_key"]]})
            dmap = {}
            for sd in dcopies:
                sub = df[df["relpath"].str.startswith(sd + "\\")]
                dmap[sd] = {rp[len(sd) + 1:]: sha for rp, sha in zip(sub["relpath"], sub["sha256"])}
            kmap = {rel: sha256_file(ap) for rel, (ap, size) in files.items()}
            for sd, dm in dmap.items():
                same = sum(1 for rel, s in kmap.items() if dm.get(rel) == s)
                diff = sum(1 for rel, s in kmap.items() if rel in dm and dm[rel] != s)
                k_only = sum(1 for rel in kmap if rel not in dm)
                d_only = sum(1 for rel in dm if rel not in kmap)
                kc.append({"k_study": name, "on_drive_by_name": "Y", "drive_copy": sd, "k_files": len(kmap),
                           "k_bytes": sum(s for _, s in files.values()), "drive_files": len(dm),
                           "identical_files": same, "differing_files": diff, "k_only_files": k_only,
                           "drive_only_files": d_only,
                           "k_only_examples": "; ".join(sorted(rel for rel in kmap if rel not in dm)[:5]),
                           "drive_only_examples": "; ".join(sorted(rel for rel in dm if rel not in kmap)[:5]),
                           "acqp_same_as_drive_exam": ""})
        else:
            hits = []
            for rel, (ap, size) in files.items():
                if os.path.basename(rel) == "acqp" and rel.count(os.sep) == 1:
                    s = sha256_file(ap)
                    if s in drive_acqp:
                        hits.append(f"{rel.split(os.sep)[0]}={','.join(sorted(drive_acqp[s]))}")
            kc.append({"k_study": name, "on_drive_by_name": "N", "drive_copy": "", "k_files": len(files),
                       "k_bytes": sum(s for _, s in files.values()), "acqp_same_as_drive_exam": "; ".join(hits) or "none"})
    write_csv("p0118_vs_K.csv", kc, ["k_study", "on_drive_by_name", "drive_copy", "k_files", "k_bytes", "drive_files",
                                     "identical_files", "differing_files", "k_only_files", "drive_only_files",
                                     "k_only_examples", "drive_only_examples", "acqp_same_as_drive_exam"])
    # study-NAMED folders of the same `r<n>_2DG` series that hold no scan (segmentations only): which
    # animals, and does the facility DB put them in 0118 with an MRI that day? (SELECT only; evidence)
    import re
    import sys
    from a1_common import OUT, TOOLS, read_csv_dicts
    sys.path.insert(0, TOOLS)
    import animal_db
    seg = []
    names = read_csv_dicts(os.path.join(OUT, "study_names.csv"))
    conn = animal_db.get_connection()
    try:
        for n in names:
            m = re.match(r"^(\d{8})_\d{6}_jrc\d{6}_r(\d+)_2DG", n["name"])
            if not m or n["kind"].startswith("paravision"):
                continue
            res = animal_db.lookup("0118", int(m.group(2)), conn=conn, use_cache=False)
            day = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}"
            procs = [p["type"] for p in (res.subject or {}).get("procedures", []) if (p.get("date") or "")[:10] == day]
            seg.append({"name": n["name"], "animal": m.group(2), "db_0118": res.status,
                        "species": (res.subject or {}).get("species", ""), "procedures_that_day": ";".join(procs),
                        "files": n["files"], "classes": n["classes"], "locations": n["locations"]})
    finally:
        conn.close()
    if seg:
        write_csv("p0118_segmentation_only.csv", seg, list(seg[0].keys()))
    L = [f"0118 studies on the drive (folder MRI\\Proyecto 0118 (Ratas hipoxia)): {len(st_rows)}; "
         f"exams {sum(s['exams'] for s in st_rows)}; distinct {gb(sum(s['distinct_bytes'] for s in st_rows)):.2f} GB "
         f"({sum(s['distinct_bytes'] for s in st_rows)/2**30:.2f} GiB); DICOM {gb(sum(s['dicom_bytes'] for s in st_rows)):.2f} GB"]
    L.append("by year: " + str(collections.Counter(s["date"][:4] for s in st_rows)))
    L.append("classes: " + str(collections.Counter(r["class"] for r in p0118)))
    L.append("details: " + str(collections.Counter(r["class_detail"] for r in p0118)))
    L.append(f"K:\\gjesus\\MRI\\Proyecto 0118: {len(k)} study folders; on the drive by name: "
             f"{sum(1 for x in kc if x['on_drive_by_name'] == 'Y')} comparisons")
    for x in kc:
        L.append(f"   {x['k_study']}: on drive {x['on_drive_by_name']}; " +
                 (f"identical {x['identical_files']}/{x['k_files']} K files, differing {x['differing_files']}, "
                  f"K-only {x['k_only_files']}, drive-only {x['drive_only_files']} ({x['drive_copy']})"
                  if x["on_drive_by_name"] == "Y" else f"acqp found on drive: {x['acqp_same_as_drive_exam']}"))
    L.append(f"segmentation-only folders of the r<n>_2DG series (no scan on the drive or in production): {len(seg)}")
    for s in seg:
        L.append(f"   {s['name']}: 0118/{s['animal']} {s['db_0118']} {s['species']}; that day: {s['procedures_that_day']}")
    txt = "\n".join(L)
    with open(out_path("p0118_summary.txt"), "w", encoding="utf-8") as f:
        f.write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
