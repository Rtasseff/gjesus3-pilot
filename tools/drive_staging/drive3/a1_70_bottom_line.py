"""A1 step 7: the bottom line. Genuinely new raw imaging on the drive, by class, project and year,
and for MRI what ingesting it would need. Measures and proposes; decides nothing.

"New" = not in production /raw/ by SHA-256 AND not the same acquisition in another form:
  MRI           exam classes (c) (d) (e) of a1_22 (an exam in production in any form is not new)
  PET/CT        Molecubes reconstructions not in production by bytes, name or time (a1_40); the
                ones that are only in the S:\\gnuclear snapshot are listed apart (production can take
                them from the snapshot; the drive adds only their folder claims)
  microscopy    distinct files not byte-identical and not a re-save of a production acquisition (a1_50)
  other DICOM   the extension-less series (a1_05): pig cardiac MRI from an external scanner
Each distinct file / exam is counted once (SHA-256 dedup inside the drive).

Writes a1\\bottom_line.csv (long form), a1\\bottom_line_summary.txt.

    python a1_70_bottom_line.py
"""
import collections
import csv
import re

from a1_common import cache_load, gb, out_path, read_csv_dicts, snapshot, write_csv, OUT
import os


def main():
    rows = []
    projects = {p["name"]: p for p in read_csv_dicts(snapshot("registry_projects.csv"))}

    def proj(code):
        if not code:
            return "(no claim)"
        if code == "0118":
            return "0118: Proyecto-0118-rats-hipoxia or AE-biomaGUNE-0118 (PROJ-0060)"
        p = projects.get(f"AE-biomaGUNE-{code}")
        return f"AE-biomaGUNE-{code} ({p['project_id']}, {p['status']})" if p else f"AE-biomaGUNE-{code} (no project)"

    # ---------------- MRI
    ex = cache_load("mri_exam_rows")
    keys = cache_load("mri_keys")
    fcache = cache_load("files")
    held = {}
    ks = fcache[fcache["a1class"] == "mri-kspace"]
    for ed, h in zip(ks["exam_dir"], ks["in_d12_hold"]):
        held.setdefault(ed, []).append(bool(h))
    ms = {r["study"]: r for r in read_csv_dicts(os.path.join(OUT, "mri_missing_studies.csv"))}
    for r in ex:
        if r["class"] not in ("c", "d", "e"):
            continue
        st = ms.get(r["study"], {})
        code = st.get("decided_code", "")
        need = {"c": "ingest the native DICOM (copy_strategy mri_paravision_v2); scoped config where the name parses with neither regex",
                "d": "convert first (convert_staged_exams.py, Dicomifier) then ingest; Ryan's 2026-10-04 rule",
                "e": "not registered (2026-10-04 rule): keep as other data with a README"}[r["class"]]
        label = r["class"] + " " + r["class_detail"].split(" (")[0]
        hs = [x for e_ in keys[r["exam_key"]] for x in held.get(e_, [])]
        if r["class"] == "e" and hs and all(hs):
            label += " (k-space already in the drives-1+2 holding folder)"
            need = "nothing: already kept as other data by stream A (drives 1+2)"
        rows.append({"domain": "MRI (Bruker 7T/11.7T)", "class": label,
                     "project": proj(code) if code or st.get("verdict") != "C" else "blank (C): the DB contradicts the folder claim",
                     "verdict": st.get("verdict", ""), "year": r["year"],
                     "unit": "exam", "units": 1, "files": 0, "bytes_source": int(r["distinct_bytes_all_copies"]),
                     "bytes_to_raw": int(r["dcm_bytes"]) if r["class"] == "c" else 0,
                     "what_ingest_needs": need, "regex": r["regex_parse"]})
    # ---------------- PET / CT
    pet = read_csv_dicts(os.path.join(OUT, "pet_files.csv"))
    seen = set()
    for r in pet:
        if r["kind"] != "molecubes-recon" or r["first_copy"] != "Y" or r["coverage"].startswith("in production"):
            continue
        if r["sha256"] in seen:
            continue
        seen.add(r["sha256"])
        codes = [c for seg in r["relpath"].split("\\")[:-1] for c in re.findall(r"(?<!\d)((?:0[1-9]|1[0-9])(?:1[6-9]|2[0-6]))(?!\d)", re.sub(r"\d{6,8}", " ", seg))]
        code = codes[-1] if codes else ""
        snap = r["coverage"].startswith("only in the S")
        rows.append({"domain": "PET/CT (Molecubes)", "class": "in the S:\\gnuclear snapshot only (held back)" if snap else "NEW",
                     "project": proj(code) + (" [path claim]" if code else ""), "verdict": "path claim" if code else "",
                     "year": r["ts"][:4], "unit": "reconstruction", "units": 1, "files": 1,
                     "bytes_source": int(r["size"]), "bytes_to_raw": int(r["size"]),
                     "what_ingest_needs": ("ingest from the snapshot (no drive bytes needed); protocol code from the path"
                                           if snap else "NI ingest (ni_flat) from the staged copy; code from the drive path"),
                     "regex": ""})
    # ---------------- microscopy
    mic = read_csv_dicts(os.path.join(OUT, "microscopy_files.csv"))
    seen = set()
    for r in mic:
        if r["sha256"] in seen:
            continue
        seen.add(r["sha256"])
        if r["in_prod_raw"] == "Y" or r["vs_production"].startswith("re-save"):
            continue
        inst = r["instrument"]
        label = {"CELL": "Cell Observer (CELL)", "unknown": "Axioscan 7 serial 4661000340 (not gjesus3's)"}.get(inst, inst)
        if inst == "unknown" and r["serials"] != "4661000340":
            label = "unreadable / no fingerprint"
        rows.append({"domain": "microscopy", "class": label,
                     "project": proj(r["claim_code"]) + (" [path claim]" if r["claim_code"] else ""),
                     "verdict": r["claim_verdict"], "year": (r["acq_dt"] or "")[:4] or "?", "unit": "file", "units": 1,
                     "files": 1, "bytes_source": int(r["size"]), "bytes_to_raw": int(r["size"]),
                     "what_ingest_needs": ("microscopy ingest; same-timestamp groups first through the stream-D rule"
                                           if inst == "CELL" else "external instrument: needs an X-code decision first"),
                     "regex": ""})
    # ---------------- other DICOM (extension-less)
    pr = read_csv_dicts(os.path.join(OUT, "noext_dicom_probe.csv"))
    files = cache_load("files")
    size = dict(zip(files["relpath"], files["size"]))
    shas = dict(zip(files["relpath"], files["sha256"]))
    seen = set()
    for r in pr:
        if r["is_dicm"] != "Y" or "cerdos" not in r["relpath"]:
            continue
        if shas[r["relpath"]] in seen:
            continue
        seen.add(shas[r["relpath"]])
        rows.append({"domain": "other DICOM", "class": "pig cardiac MRI, Philips Achieva (CNIC), external",
                     "project": "(no claim)", "verdict": "", "year": r["study_year"] or "?", "unit": "file", "units": 1,
                     "files": 1, "bytes_source": size[r["relpath"]], "bytes_to_raw": size[r["relpath"]],
                     "what_ingest_needs": "external scanner (would be XMRI); Ryan's call; A3's segmentation question",
                     "regex": ""})
    # aggregate
    agg = collections.defaultdict(lambda: [0, 0, 0, 0])
    for r in rows:
        k = (r["domain"], r["class"], r["project"], r["year"], r["unit"], r["what_ingest_needs"])
        a = agg[k]
        a[0] += r["units"]
        a[1] += r["files"]
        a[2] += r["bytes_source"]
        a[3] += r["bytes_to_raw"]
    out = [{"domain": k[0], "class": k[1], "project": k[2], "year": k[3], "unit": k[4], "units": v[0],
            "GB_source": gb(v[2]), "GB_to_raw": gb(v[3]), "what_ingest_needs": k[5]}
           for k, v in sorted(agg.items())]
    write_csv("bottom_line.csv", out, ["domain", "class", "project", "year", "unit", "units", "GB_source", "GB_to_raw",
                                       "what_ingest_needs"])
    L = []
    for dom in ("MRI (Bruker 7T/11.7T)", "PET/CT (Molecubes)", "microscopy", "other DICOM"):
        d = [r for r in rows if r["domain"] == dom]
        L.append(f"== {dom}: {sum(r['units'] for r in d):,} {d[0]['unit'] if d else ''}s, "
                 f"{gb(sum(r['bytes_source'] for r in d)):.1f} GB source, {gb(sum(r['bytes_to_raw'] for r in d)):.1f} GB to /raw/")
        by = collections.defaultdict(lambda: [0, 0, 0])
        for r in d:
            b = by[(r["class"], r["project"])]
            b[0] += r["units"]
            b[1] += r["bytes_source"]
            b[2] += r["bytes_to_raw"]
        for (c, p), v in sorted(by.items(), key=lambda kv: -kv[1][1]):
            L.append(f"   {c[:48]:48s} {p[:62]:62s} {v[0]:6,d}  {gb(v[1]):7.1f} GB  ->raw {gb(v[2]):6.1f} GB")
        yy = collections.Counter()
        for r in d:
            yy[r["year"]] += r["units"]
        L.append("   by year: " + ", ".join(f"{y} {n:,}" for y, n in sorted(yy.items())))
    txt = "\n".join(L)
    with open(out_path("bottom_line_summary.txt"), "w", encoding="utf-8") as f:
        f.write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
