"""Stream M, part 2: verify a NAS root after the P01 ingest (CNIC pig images), independently of the ingest (read-only).

    python mri_22_pig_verify.py <nas_root> <baseline dir> [--rehash]

<baseline dir>: the state before P01 (mri_09_backup.py <root> <dir> CNIC-HEARDS, taken AFTER the project was created).
  R1  registry_raw.csv append-only, +27; the new rows are exactly cases_P01.csv's folders
  R2  each row: XMRI, model, datetime (to the second), collaborator:CNIC, sample, organism Sus scrofa, no subject id,
      session, primary series/ (archive), file_count == the staged instances, project CNIC-HEARDS, config, note
  R3  no duplicate acq_id, (date, original_name)
  F1  <ACQ-ID>\\series\\ holds exactly the staged instances; --rehash: each == checksums.json == the drive manifest
  S1  sidecar: species Sus scrofa, no facility id; no dicom-block key holds a name or a birth date; patient id = the pig code
  L1  one link folder per row in CNIC-HEARDS\\raw_linked, an exact samefile mirror of the acquisition folder (X1 shape)
  P1  CNIC-HEARDS provenance.csv: +27 rows, append-only
  O1  registry_projects, retired, datasets, pending_dicom_regen, registry_subjects, pending_subject_metadata unchanged
"""
import collections
import csv
import hashlib
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mri_common as C  # noqa: E402

PROJECT = "CNIC-HEARDS"
CFG = f"{C.CFG_DIR_REL}/drive3_mri_P01_cnic_heards.yaml"
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)


def sha(p):
    h = hashlib.sha256()
    with open(C.lp(p), "rb") as f:
        for b in iter(lambda: f.read(8 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rows_of(path):
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def walk(root):
    res = {}
    for d, _x, fs in os.walk(root):
        for f in fs:
            p = os.path.join(d, f)
            res[os.path.relpath(p, root).replace("\\", "/")] = p
    return res


def main():
    root, base = sys.argv[1], sys.argv[2]
    rehash = "--rehash" in sys.argv
    reg = os.path.join(root, "registries")
    cases = {c["original_name"]: c for c in C.rows(os.path.join(C.CFG_DIR, "cases_P01.csv"))}
    man = {r["staged_rel"]: r for r in C.rows(os.path.join(C.OUT, "stage_result_pig.csv"))}
    projects = {r["name"]: r for r in rows_of(os.path.join(reg, "registry_projects.csv"))}
    old = rows_of(os.path.join(base, "registry_raw.csv"))
    new_all = rows_of(os.path.join(reg, "registry_raw.csv"))
    pre = open(os.path.join(reg, "registry_raw.csv"), "rb").read().startswith(open(os.path.join(base, "registry_raw.csv"), "rb").read())
    old_ids = {r["acq_id"] for r in old}
    added = [r for r in new_all if r["acq_id"] not in old_ids]
    check("R1 registry_raw append-only, +27", pre and len(added) == 27 == len(new_all) - len(old), f"{len(old)} -> {len(new_all)}")
    check("R1 the new rows are exactly the 27 series folders", {r["original_name"] for r in added} == set(cases))
    r2, f1, s1, l1 = [], [], [], []
    for r in added:
        c = cases.get(r["original_name"])
        if not c:
            continue
        staged = walk(os.path.join(C.STAGE, "P01", r["original_name"]))
        d8 = c["drv_acq_datetime"][:10].replace("-", "")
        exp = {"instrument": "XMRI", "data_ecosystem": "DICOM", "instrument_model": c["drv_model"], "researcher": "",
               "operator": "", "data_source": "collaborator:CNIC", "sample_id": c["drv_sample"], "sample_type": "organism",
               "sample_organism": "Sus scrofa", "subject_ids": "", "session_id": c["drv_session"],
               "primary_kind": "archive", "primary_file_name": "series/", "file_count": str(len(staged)),
               "project_id": projects[PROJECT]["project_id"], "ingest_config": CFG,
               "canonical_path": f"/raw/DICOM/{d8[:4]}/{d8[:4]}-{d8[4:6]}/{r['acq_id']}/"}
        for k, v in exp.items():
            if r.get(k, "") != v:
                r2.append(f"{r['original_name']} {k}: {r.get(k)!r} != {v!r}")
        if not re.fullmatch(rf"ACQ-{d8}-XMRI-\d{{3}}", r["acq_id"]):
            r2.append(f"{r['original_name']} acq_id {r['acq_id']}")
        if r["acquisition_datetime"][:19] != c["drv_acq_datetime"][:19]:
            r2.append(f"{r['original_name']} datetime {r['acquisition_datetime']} vs {c['drv_acq_datetime']}")
        if r["original_name"] not in r["notes"]:
            r2.append(f"{r['original_name']} drive path not in notes")
        acq = os.path.join(root, r["canonical_path"].strip("/").replace("/", os.sep))
        ser = walk(os.path.join(acq, "series"))
        if sorted(ser) != sorted(staged):
            f1.append(f"{r['acq_id']} series/ holds {len(ser)}, staged {len(staged)}")
            continue
        cj = {k.replace("\\", "/"): v for k, v in json.load(open(os.path.join(acq, "checksums.json"), encoding="utf-8"))["files"].items()}
        cjn = {k.split("series/", 1)[-1]: v for k, v in cj.items()}
        if sorted(cjn) != sorted(ser):
            f1.append(f"{r['acq_id']} checksums.json lists {len(cjn)}")
        if rehash:
            for n, p in ser.items():
                want = man["PIG\\" + r["original_name"] + "\\DICOM\\" + n]["sha256"]
                if not sha(p) == cjn.get(n) == want:
                    f1.append(f"{r['acq_id']} {n} differs")
        sc = json.load(open(os.path.join(acq, "metadata.json"), encoding="utf-8"))
        sb = sc.get("subject") or {}
        if sb.get("species") != "Sus scrofa" or sb.get("facility_animal_id"):
            s1.append(f"{r['acq_id']} subject {sb}")
        # every KEY of the dicom block (the policy note names the denied tags in prose; keys are what is carried)
        keys = []
        stack = [sc.get("dicom") or {}]
        while stack:
            d = stack.pop()
            for k, v in d.items():
                keys.append(k.lower())
                if isinstance(v, dict):
                    stack.append(v)
        if any("name" in k or "birth" in k for k in keys):
            s1.append(f"{r['acq_id']} the dicom block carries {[k for k in keys if 'name' in k or 'birth' in k]}")
        if ((sc.get("dicom") or {}).get("subject") or {}).get("dicom_patient_id") != c["drv_sample"]:
            s1.append(f"{r['acq_id']} dicom_patient_id is not the pig code {c['drv_sample']}")
        link = os.path.join(root, "projects", PROJECT, "raw_linked", f"XMRI_{c['drv_session']}_{c['drv_series']}")
        lw = walk(link) if os.path.isdir(link) else {}
        aw = walk(acq)
        if sorted(lw) != sorted(aw) or any(not os.path.samefile(lw[k], aw[k]) for k in lw):
            l1.append(f"{r['acq_id']} link {os.path.basename(link)}: {len(lw)} vs {len(aw)} files")
    check("R2 every row equals the plan", not r2, f"{len(r2)} disagreements")
    for x in r2[:10]:
        print("      ", x)
    check(f"F1 series/ holds exactly the staged instances{' (re-hashed vs drive manifest)' if rehash else ''}", not f1, f"{len(f1)} bad")
    for x in f1[:10]:
        print("      ", x)
    check("S1 sidecars (Sus scrofa, no facility id, no denied patient field)", not s1, f"{len(s1)} bad")
    for x in s1[:5]:
        print("      ", x)
    check("L1 one exact samefile link folder per row", not l1, f"{len(l1)} bad")
    ids = [r["acq_id"] for r in new_all]
    dn = collections.Counter((r["acquisition_datetime"][:10], r["original_name"]) for r in new_all)
    check("R3 no duplicate acq_id or (date, original_name)", len(ids) == len(set(ids)) and all(
        dn[(r["acquisition_datetime"][:10], r["original_name"])] == 1 for r in added))
    pv_new = os.path.join(root, "projects", PROJECT, "provenance.csv")
    pv_old = os.path.join(base, "provenance", PROJECT + ".csv")
    k = len(rows_of(pv_new)) - (len(rows_of(pv_old)) if os.path.exists(pv_old) else 0)
    ok = (not os.path.exists(pv_old)) or open(pv_new, "rb").read().startswith(open(pv_old, "rb").read())
    check("P1 provenance.csv append-only, +27", ok and k == 27, f"+{k}")
    for n in ("registry_projects.csv", "retired_acquisitions.csv", "registry_datasets.csv", "pending_dicom_regen.csv",
              "registry_subjects.csv", "pending_subject_metadata.csv"):
        check(f"O1 {n} byte-identical", sha(os.path.join(base, n)) == sha(os.path.join(reg, n)))
    fails = [n for n, o in RESULTS if not o]
    print(f"\n{len(RESULTS) - len(fails)}/{len(RESULTS)} checks PASS")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
