"""Stream AR: verify a NAS root after the archive batches, independently of the ingest's own checks (read-only).

    python ar_12_verify.py <nas_root> <baseline dir> <batches, comma-separated | all> [--rehash]

Stream M's mri_10_verify.py for this stream. <baseline dir> = the state BEFORE the first batch (tools/drive_staging/
drive3/mri_09_backup.py <root> <dir> <projects>). The expected rows are the case tables of the named batches
(tools/configs/mri_archive/cases_<b>.csv) and the extracted exams they were built from.

  R1  registry_raw.csv append-only (old bytes a prefix); the new rows are exactly the batches' original_names
  R2  every new row equals the plan: ACQ-ID shape and date, datetime (to the second), MRI, model, researcher blank,
      operator pending-claim, internal, sample, sample type, subject id <animal>-AE-biomaGUNE-<alias> (blank where
      no alias), session, primary, file count == the exam's DICOMs, checksum flag, project, config, the archive path
      in the notes
  R3  no duplicate acq_id or (date, original_name); no new row shares its original_name with any row
  F1  each acquisition folder: metadata.json, checksums.json, README.txt, <ACQ-ID>.data\\ holding exactly the exam's
      DICOMs under their production names; with --rehash every file re-hashed == checksums.json == the extracted file,
      and, for the scanner's DICOM, == the hash recorded when it was extracted from the SHA-1-verified tarball
  S1  sidecar subject: facility id == subject_ids, source animal-facility-db; none where no alias
  L1  one link folder per row with a project, MRI_<sample>_<YYYYMMDD>_<HHMM>_<exam>_<recons>, holding exactly the
      .data files, each os.path.samefile; each project's raw_linked gained exactly these and lost nothing
  P1  provenance.csv append-only, one row per new link
  T1  every new subject id once in registry_subjects.csv; pending_subject_metadata.csv unchanged
  M1  ingest_manifest.csv append-only, + the new rows
  O1  registry_projects, retired_acquisitions, registry_datasets, pending_dicom_regen byte-identical
"""
import collections
import csv
import glob
import hashlib
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ar_common as C  # noqa: E402

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


def prefix_ok(old, new):
    return open(new, "rb").read().startswith(open(old, "rb").read())


def staged_dicoms(batch, on):
    study, exam = on.split("/")
    res = {}
    for p in glob.glob(os.path.join(C.EXTRACT, batch, study, exam, "pdata", "*", "dicom", "*.dcm")):
        name = C.dcm_prod_name(p.split(os.sep)[-3], os.path.basename(p))
        assert name not in res, (on, name)
        res[name] = p
    return res


def main():
    root, base, which = sys.argv[1], sys.argv[2], sys.argv[3]
    rehash = "--rehash" in sys.argv
    reg = os.path.join(root, "registries")
    batches = (sorted(os.path.basename(p)[6:-4] for p in glob.glob(os.path.join(C.CFG_DIR, "cases_AR*.csv")))
               if which == "all" else which.split(","))
    cases = {}
    for b in batches:
        for r in C.rows(os.path.join(C.CFG_DIR, f"cases_{b}.csv")):
            cases[r["original_name"]] = {**r, "batch": b}
    studies = {s["study"]: s for s in C.rows(os.path.join(C.OUT, "plan_studies.csv"))}
    projects = {r["name"]: r for r in rows_of(os.path.join(base, "registry_projects.csv"))}
    xhash = {}
    for s in {on.split("/")[0] for on in cases}:
        for m in C.members(s):
            if m["action"] == "extracted":
                xhash[m["member"]] = m["sha256"]          # <study>/<exam>/pdata/<idx>/dicom/<file>

    old = rows_of(os.path.join(base, "registry_raw.csv"))
    new_all = rows_of(os.path.join(reg, "registry_raw.csv"))
    pre = prefix_ok(os.path.join(base, "registry_raw.csv"), os.path.join(reg, "registry_raw.csv"))
    old_ids = {r["acq_id"] for r in old}
    added = [r for r in new_all if r["acq_id"] not in old_ids]
    check(f"R1 registry_raw append-only, +{len(cases)}", pre and len(added) == len(cases) == len(new_all) - len(old),
          f"{len(old)} -> {len(new_all)} rows; old bytes a prefix: {pre}")
    check("R1 the new rows are exactly the batches' exams", {r["original_name"] for r in added} == set(cases),
          f"{len({r['original_name'] for r in added} & set(cases))} of {len(cases)}")

    r2, f1, s1, l1 = [], [], [], []
    links_new = collections.Counter()
    nfiles = 0
    for r in added:
        c = cases.get(r["original_name"])
        if not c:
            continue
        b = c["batch"]
        s = studies[r["original_name"].split("/")[0]]
        d8 = c["drv_acq_datetime"][:10].replace("-", "")
        dcms = staged_dicoms(b, r["original_name"])
        subj = f"{c['drv_animal']}-AE-biomaGUNE-{c['drv_alias']}" if c["drv_alias"] else ""
        exp = {"data_ecosystem": "DICOM", "instrument": "MRI", "instrument_model": c["drv_model"], "researcher": "",
               "operator": "pending-claim", "data_source": "internal", "sample_id": c["drv_sample"],
               "sample_type": c["drv_sample_type"], "subject_ids": subj, "session_id": c["drv_session"],
               "primary_kind": "folder", "primary_file_name": f"{r['acq_id']}.data", "file_count": str(len(dcms)),
               "checksum_present": "Y",
               "project_id": projects[c["drv_project"]]["project_id"] if c["drv_project"] else "",
               "ingest_config": f"{C.CFG_DIR_REL}/mri_archive_{b}.yaml",
               "canonical_path": f"/raw/DICOM/{d8[:4]}/{d8[:4]}-{d8[4:6]}/{r['acq_id']}/"}
        for k, v in exp.items():
            if r.get(k, "") != v:
                r2.append(f"{r['original_name']} {k}: {r.get(k)!r} != {v!r}")
        if not re.fullmatch(rf"ACQ-{d8}-MRI-\d{{3}}", r["acq_id"]):
            r2.append(f"{r['original_name']} acq_id {r['acq_id']}")
        if r["acquisition_datetime"][:19] != c["drv_acq_datetime"].replace(",", ".")[:19]:
            r2.append(f"{r['original_name']} datetime {r['acquisition_datetime']} vs {c['drv_acq_datetime']}")
        if s["archive"].split("backup_7T_olddata_260824/")[-1] not in r["notes"] or s["archive_sha1"] not in r["notes"]:
            r2.append(f"{r['original_name']} archive path / SHA-1 not in notes")
        acq = os.path.join(root, r["canonical_path"].strip("/").replace("/", os.sep))
        data = os.path.join(acq, f"{r['acq_id']}.data")
        top = sorted(os.listdir(acq)) if os.path.isdir(acq) else []
        if top != sorted(["README.txt", "checksums.json", "metadata.json", f"{r['acq_id']}.data"]):
            f1.append(f"{r['acq_id']} folder holds {top}")
            continue
        files = sorted(os.listdir(data))
        if files != sorted(dcms):
            f1.append(f"{r['acq_id']} .data holds {len(files)}, staged {len(dcms)}")
            continue
        cj = json.load(open(os.path.join(acq, "checksums.json"), encoding="utf-8"))["files"]
        cjn = {k.replace("\\", "/").split("/")[-1]: v for k, v in cj.items()}
        if sorted(cjn) != files:
            f1.append(f"{r['acq_id']} checksums.json lists {len(cjn)} files")
        if rehash:
            scanner = c["drv_dicom_origin"].startswith("scanner")
            for n in files:
                now, src = sha(os.path.join(data, n)), sha(dcms[n])
                rel = os.path.relpath(dcms[n], os.path.join(C.EXTRACT, b)).replace(os.sep, "/")
                want = xhash.get(rel)
                nfiles += 1
                if not (now == cjn.get(n) == src) or (scanner and want != now):
                    f1.append(f"{r['acq_id']} {n}: now {now[:10]} checksums {str(cjn.get(n))[:10]} staged {src[:10]} "
                              f"extracted {str(want)[:10]}")
        sc = json.load(open(os.path.join(acq, "metadata.json"), encoding="utf-8"))
        sb = sc.get("subject") or {}
        if subj:
            if sb.get("facility_animal_id") != subj or sb.get("source") != "animal-facility-db":
                s1.append(f"{r['acq_id']} subject {sb.get('facility_animal_id')} / {sb.get('source')}")
        elif sb.get("facility_animal_id"):
            s1.append(f"{r['acq_id']} carries a facility id {sb.get('facility_animal_id')}")
        if c["drv_project"]:
            idx = [str(x) for x in ((sc.get("mri") or {}).get("reconstruction") or {}).get("indices_present") or []]
            name = (f"MRI_{r['sample_id']}_{r['acq_id'].split('-')[1]}_{c['drv_hhmm']}_"
                    f"{r['original_name'].split('/')[1]}_{','.join(idx)}")
            ldir = os.path.join(root, "projects", c["drv_project"], "raw_linked", name)
            links_new[c["drv_project"]] += 1
            lf = sorted(os.listdir(ldir)) if os.path.isdir(ldir) else None
            if lf != files or any(not os.path.samefile(os.path.join(ldir, n), os.path.join(data, n)) for n in files):
                l1.append(f"{r['acq_id']} link {name}: {('missing' if lf is None else f'{len(lf)} files')}")
    check("R2 every new row equals the plan", not r2, f"{len(r2)} disagreements")
    for x in r2[:12]:
        print("      ", x)
    check(f"F1 acquisition folders and files{' (re-hashed)' if rehash else ''}", not f1,
          f"{len(f1)} bad; files re-hashed {nfiles}")
    for x in f1[:12]:
        print("      ", x)
    check("S1 sidecar subject blocks", not s1, f"{len(s1)} bad")
    for x in s1[:8]:
        print("      ", x)
    check("L1 one exact hard-link folder per acquisition with a project", not l1,
          f"{sum(links_new.values())} expected {dict(links_new)}; {len(l1)} bad")
    for x in l1[:8]:
        print("      ", x)
    lost = []
    for proj, n in links_new.items():
        now = set(os.listdir(os.path.join(root, "projects", proj, "raw_linked")))
        before = {l.rstrip("\n") for l in open(os.path.join(base, "raw_linked", proj + ".txt"), encoding="utf-8") if l.strip()}
        if not before <= now or len(now - before) != n:
            lost.append(f"{proj}: before {len(before)}, now {len(now)}, expected +{n}, lost {len(before - now)}")
    check("L1 raw_linked gained exactly the new links and lost nothing", not lost, "; ".join(lost))

    ids = [r["acq_id"] for r in new_all]
    dn = collections.Counter((r["acquisition_datetime"][:10], r["original_name"].replace("\\", "/")) for r in new_all)
    check("R3 no duplicate acq_id", len(ids) == len(set(ids)))
    mine = {(r["acquisition_datetime"][:10], r["original_name"]) for r in added}
    check("R3 no duplicate (date, original_name) among or against the new rows", all(dn[k] == 1 for k in mine),
          f"{sum(1 for k in mine if dn[k] > 1)} duplicated")
    byname = collections.Counter(r["original_name"].replace("\\", "/") for r in new_all)
    check("R3 no new row shares its original_name with any other row", all(byname[r["original_name"]] == 1 for r in added))

    pb = []
    for proj, n in links_new.items():
        newp, oldp = os.path.join(root, "projects", proj, "provenance.csv"), os.path.join(base, "provenance", proj + ".csv")
        k = len(rows_of(newp)) - len(rows_of(oldp))
        if not prefix_ok(oldp, newp) or k != n:
            pb.append(f"{proj}: +{k} rows, {n} expected")
    check("P1 provenance.csv append-only, one row per new link", not pb, "; ".join(pb))
    sn, so = rows_of(os.path.join(reg, "registry_subjects.csv")), rows_of(os.path.join(base, "registry_subjects.csv"))
    col = "subject_id" if sn and "subject_id" in sn[0] else list(sn[0].keys())[0]
    cnt = collections.Counter(r[col] for r in sn)
    want = {r["subject_ids"] for r in added if r["subject_ids"]}
    check("T1 every new subject id in registry_subjects.csv exactly once", all(cnt[s] == 1 for s in want),
          f"subjects {len(so)} -> {len(sn)}; ids {len(want)}, of them new {len(want - {r[col] for r in so})}")
    check("T1 pending_subject_metadata.csv unchanged (no DB miss)",
          sha(os.path.join(base, "pending_subject_metadata.csv")) == sha(os.path.join(reg, "pending_subject_metadata.csv")))
    nm = len(rows_of(os.path.join(reg, "ingest_manifest.csv"))) - len(rows_of(os.path.join(base, "ingest_manifest.csv")))
    check(f"M1 ingest_manifest.csv append-only, +{len(cases)}",
          prefix_ok(os.path.join(base, "ingest_manifest.csv"), os.path.join(reg, "ingest_manifest.csv")) and nm == len(cases),
          f"+{nm}")
    for n in ("registry_projects.csv", "retired_acquisitions.csv", "registry_datasets.csv", "pending_dicom_regen.csv"):
        check(f"O1 {n} byte-identical", sha(os.path.join(base, n)) == sha(os.path.join(reg, n)))
    fails = [n for n, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(fails)}/{len(RESULTS)} checks PASS")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
