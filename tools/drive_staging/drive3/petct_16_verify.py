"""Stream N: verify a NAS root after the stream-N ingest, independently of the ingest's own checks.

    python petct_16_verify.py <nas_root> <baseline dir>

<baseline dir> is the state BEFORE the write: the registry files at its top level, provenance\\<project>.csv
(each target project's provenance.csv) and raw_linked\\<project>.txt (each target project's raw_linked
entry names). For the rehearsal it is built from the setup copies; for production it is the fresh dated
backup taken before the write (gate document, section 6). Read-only on <nas_root>.

Checks, each printed PASS/FAIL with counts:
  R1  registry_raw.csv grew by exactly the plan's 202 rows, append-only (the old bytes are a prefix)
  R2  every new row equals the plan (key, ACQ-ID shape, instrument, datetime, researcher, operator blank,
      sample, subject id, session, project, primary, file count, checksum flag, config, note)
  R3  no duplicate acq_id, (date, original_name) or NI (timestamp, modality) anywhere in the registry
  F1  each new acquisition folder holds exactly metadata.json, checksums.json, README.txt, <ACQ-ID>.data\\
      with exactly the one expected DICOM; its SHA-256 re-hashed now == checksums.json == the drive manifest
  S1  each sidecar: discovered.project, subject.facility_animal_id (DB-sourced) or none for the phantom,
      anatomy whole-body
  L1  each animal acquisition has exactly its own link folder (one hard link, os.path.samefile with /raw/);
      the phantom has none; raw_linked gained nothing else
  P1  provenance.csv of each project: append-only, one new row per new link
  T1  registry_subjects.csv append-only/upsert: every new subject id present once; pending lists unchanged
  M1  ingest_manifest.csv: append-only, +202
  O1  registry_projects / retired / datasets / pending_dicom_regen byte-identical
"""
import collections
import csv
import hashlib
import io
import json
import os
import re
import sys

sys.dont_write_bytecode = True
csv.field_size_limit(2 ** 31 - 1)
OUT = r"D:\projects\gjesus3\drive3_streams\petct\out"
DRIVE_MANIFEST = r"J:\_staging_drive3_MJ\drive3_MJesus_WX22D623YP29\manifest.csv"
SNAP_MANIFEST = r"J:\gjesus3-data\staging\ni_gnuclear_20260812\_manifest.jsonl"
CFG = {"snapshot": "tools/configs/drive3_petct/drive3_petct_snapshot.yaml",
       "drive": "tools/configs/drive3_petct/drive3_petct_drive.yaml"}
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(8 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rows_of(path):
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def prefix_ok(old, new):
    a, b = open(old, "rb").read(), open(new, "rb").read()
    return b.startswith(a), len(a), len(b)


def main():
    root, base = sys.argv[1], sys.argv[2]
    reg = os.path.join(root, "registries")
    plan = {p["acq_key"]: p for p in csv.DictReader(open(os.path.join(OUT, "plan_202.csv"), encoding="utf-8"))}
    projects = {r["name"]: r for r in rows_of(os.path.join(base, "registry_projects.csv"))}

    # ---- R1 -----------------------------------------------------------------------------------------
    old_rows = rows_of(os.path.join(base, "registry_raw.csv"))
    new_rows_all = rows_of(os.path.join(reg, "registry_raw.csv"))
    pre, la, lb = prefix_ok(os.path.join(base, "registry_raw.csv"), os.path.join(reg, "registry_raw.csv"))
    old_ids = {r["acq_id"] for r in old_rows}
    added = [r for r in new_rows_all if r["acq_id"] not in old_ids]
    check("R1 registry_raw append-only, +202", pre and len(new_rows_all) - len(old_rows) == 202 == len(added),
          f"{len(old_rows)} -> {len(new_rows_all)} rows; old bytes a prefix: {pre}")
    keys = {r["original_name"] for r in added}
    check("R1 new rows are exactly the plan's 202 keys", keys == set(plan), f"{len(keys)} keys")

    # ---- R2 -----------------------------------------------------------------------------------------
    bad = []
    by_key = {}
    for r in added:
        p = plan.get(r["original_name"])
        if not p:
            continue
        by_key[p["acq_key"]] = r
        k = p["acq_key"]
        ts = k[:14]
        exp = {
            "data_ecosystem": "DICOM", "instrument": p["modality"], "instrument_model": "Molecubes (PET/SPECT/CT)",
            "acquisition_datetime": f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}T{ts[8:10]}:{ts[10:12]}:{ts[12:14]}Z",
            "researcher": p["researcher_folder"], "operator": "", "data_source": "internal",
            "sample_id": p["subject"], "sample_type": p["sample_type"],
            "sample_organism": "Mus musculus" if p["sample_type"] == "organism" else "",
            "subject_ids": f"{p['animal_codes']}-AE-biomaGUNE-{p['project']}" if p["sample_type"] == "organism" else "",
            "session_id": f"{p['subject']}_{ts[:8]}", "primary_kind": "folder",
            "primary_file_name": f"{r['acq_id']}.data", "file_count": "1", "checksum_present": "Y",
            "extended_metadata_present": "Y",
            "project_id": projects[p["project_name"]]["project_id"] if p["project_name"] else "",
            "ingest_config": CFG[p["source"]],
            "canonical_path": f"/raw/DICOM/{ts[:4]}/{ts[:4]}-{ts[4:6]}/{r['acq_id']}/",
        }
        for c, v in exp.items():
            if r.get(c, "") != v:
                bad.append(f"{k} {c}: {r.get(c)!r} != {v!r}")
        if not re.fullmatch(rf"ACQ-{ts[:8]}-{p['modality']}-\d{{3}}", r["acq_id"]):
            bad.append(f"{k} acq_id {r['acq_id']}")
        if p["note"] not in r["notes"]:
            bad.append(f"{k} note missing from notes")
        if p["source"] == "snapshot" and p["source_rel"] not in r["notes"]:
            bad.append(f"{k} snapshot path missing from notes")
        if p["source"] == "drive" and p["drive_relpath"] not in r["notes"]:
            bad.append(f"{k} drive path missing from notes")
    check("R2 every new row equals the plan", not bad, f"{len(bad)} disagreements")
    for b in bad[:15]:
        print("      ", b)

    # ---- R3 -----------------------------------------------------------------------------------------
    ids = [r["acq_id"] for r in new_rows_all]
    dn = collections.Counter((r["acquisition_datetime"][:10], r["original_name"]) for r in new_rows_all)
    ni = collections.Counter(("".join(c for c in r["acquisition_datetime"] if c.isdigit())[:14], r["instrument"])
                             for r in new_rows_all if r["instrument"] in ("PET", "CT", "SPECT", "OI"))
    ni_old = collections.Counter(("".join(c for c in r["acquisition_datetime"] if c.isdigit())[:14], r["instrument"])
                                 for r in old_rows if r["instrument"] in ("PET", "CT", "SPECT", "OI"))
    new_dup_ni = [k for k, v in ni.items() if v > 1 and ni_old.get(k, 0) != v]
    check("R3 no duplicate acq_id", len(ids) == len(set(ids)))
    check("R3 no duplicate (date, original_name)", all(v == 1 for v in dn.values()),
          f"{sum(1 for v in dn.values() if v > 1)} duplicated keys")
    check("R3 no NEW duplicate NI (timestamp, modality)", not new_dup_ni,
          f"NI rows {sum(ni_old.values())} -> {sum(ni.values())}; pre-existing duplicates "
          f"{sum(1 for v in ni_old.values() if v > 1)}")

    # ---- F1 / S1 / L1 ---------------------------------------------------------------------------------
    fbad, sbad, lbad = [], [], []
    links_expected = collections.Counter()
    for k, r in by_key.items():
        p = plan[k]
        acq_dir = os.path.join(root, r["canonical_path"].strip("/").replace("/", os.sep))
        data = os.path.join(acq_dir, f"{r['acq_id']}.data")
        top = sorted(os.listdir(acq_dir)) if os.path.isdir(acq_dir) else []
        if top != sorted(["README.txt", "checksums.json", "metadata.json", f"{r['acq_id']}.data"]):
            fbad.append(f"{k} folder holds {top}")
            continue
        files = os.listdir(data)
        idx = k.split("_")[3]
        fname = os.path.basename(p["source_rel"])
        m = re.search(r"_frame(MULTI|\d+)", fname)
        want = f"recon{idx}_frame{m.group(1)}.dcm" if m else f"recon{idx}.dcm"
        if files != [want]:
            fbad.append(f"{k} .data holds {files}, want [{want}]")
            continue
        h = sha(os.path.join(data, want))
        cj = json.load(open(os.path.join(acq_dir, "checksums.json"), encoding="utf-8"))["files"]
        cvals = list(cj.values())
        if not (len(cvals) == 1 and cvals[0] == h == p["sha256"]):
            fbad.append(f"{k} sha now {h[:12]} checksums {[c[:12] for c in cvals]} manifest {p['sha256'][:12]}")
        sc = json.load(open(os.path.join(acq_dir, "metadata.json"), encoding="utf-8"))
        subj = sc.get("subject")
        if p["sample_type"] == "organism":
            if (sc.get("discovered", {}).get("project") != p["project"]
                    or not subj or subj.get("facility_animal_id") != r["subject_ids"]
                    or subj.get("source") != "animal-facility-db"
                    or (sc.get("anatomy") or {}).get("is_whole_body") is not True):
                sbad.append(f"{k} sidecar project={sc.get('discovered', {}).get('project')} subject={subj and subj.get('facility_animal_id')} src={subj and subj.get('source')}")
            link = os.path.join(root, "projects", p["project_name"], "raw_linked",
                                f"{p['modality']}_{p['subject']}_{k[:8]}_{k[:14]}_recon{idx}")
            links_expected[p["project_name"]] += 1
            if not os.path.isdir(link) or os.listdir(link) != [want] or not os.path.samefile(
                    os.path.join(link, want), os.path.join(data, want)):
                lbad.append(f"{k} link {link} -> {os.listdir(link) if os.path.isdir(link) else 'MISSING'}")
        else:
            if subj or sc.get("anatomy"):
                sbad.append(f"{k} phantom sidecar carries subject/anatomy")
    # F1b: the same hashes against the manifests themselves, not a derived table: the drive manifest
    # (every drive copy of each acquisition) and, for the 100, the S:\gnuclear snapshot's manifest.
    man = {}
    with open(DRIVE_MANIFEST, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            man[r["relpath"]] = r["sha256"]
    snapman = {}
    for line in open(SNAP_MANIFEST, encoding="utf-8"):
        j = json.loads(line)
        snapman[j["rel"]] = j["sha256"]
    inv = {r["acq_key"]: r for r in csv.DictReader(open(os.path.join(OUT, "acq_inventory.csv"), encoding="utf-8"))}
    for k, r in by_key.items():
        p = plan[k]
        copies = inv[p["acq_key_a1"]]["all_drive_relpaths"].split(" | ")
        hs = {man.get(c) for c in copies}
        if hs != {p["sha256"]}:
            fbad.append(f"{k} drive manifest has {len(hs)} hash(es) for its {len(copies)} copies, or a copy is missing")
        if p["source"] == "snapshot" and snapman.get(p["source_rel"]) != p["sha256"]:
            fbad.append(f"{k} snapshot manifest disagrees")
    check("F1 folders, files and SHA-256 (now == checksums.json == drive manifest [== snapshot manifest])",
          not fbad, f"{len(fbad)} bad; drive copies checked against {os.path.basename(DRIVE_MANIFEST)}")
    for b in fbad[:10]:
        print("      ", b)
    check("S1 sidecars (project, DB subject, whole-body; phantom bare)", not sbad, f"{len(sbad)} bad")
    for b in sbad[:10]:
        print("      ", b)
    check("L1 one hard-link folder per animal acquisition (samefile)", not lbad,
          f"{sum(links_expected.values())} expected: {dict(links_expected)}")
    for b in lbad[:10]:
        print("      ", b)
    # <base>\raw_linked\<project>.txt lists the project's raw_linked entries BEFORE the write
    extra = []
    for proj, n in links_expected.items():
        names = set(os.listdir(os.path.join(root, "projects", proj, "raw_linked")))
        before = set(l.rstrip("\n") for l in open(os.path.join(base, "raw_linked", proj + ".txt"),
                                                   encoding="utf-8") if l.strip())
        if not before <= names or len(names - before) != n:
            extra.append(f"{proj}: {len(before)} before, {len(names)} after, {n} expected new; "
                         f"lost {len(before - names)}")
    check("L1 raw_linked gained exactly the new links and lost nothing", not extra, "; ".join(extra))

    # ---- P1 -----------------------------------------------------------------------------------------
    # <base>\provenance\<project>.csv is the project's provenance.csv BEFORE the write
    pbad = []
    for proj, n in links_expected.items():
        newp = os.path.join(root, "projects", proj, "provenance.csv")
        oldp = os.path.join(base, "provenance", proj + ".csv")
        ok, a, b = prefix_ok(oldp, newp)
        nrows = len(rows_of(newp)) - len(rows_of(oldp))
        if not ok or nrows != n:
            pbad.append(f"{proj}: prefix {ok}, +{nrows} rows, {n} expected")
    check("P1 provenance.csv append-only, one row per new link", not pbad, "; ".join(pbad))

    # ---- T1 / M1 / O1 ----------------------------------------------------------------------------------
    subj_new = rows_of(os.path.join(reg, "registry_subjects.csv"))
    subj_old = rows_of(os.path.join(base, "registry_subjects.csv"))
    sid_col = "subject_id" if "subject_id" in (subj_new[0] if subj_new else {}) else list(subj_new[0].keys())[0]
    cnt = collections.Counter(r[sid_col] for r in subj_new)
    want_ids = {r["subject_ids"] for r in added if r["subject_ids"]}
    missing = [s for s in want_ids if cnt.get(s, 0) != 1]
    check("T1 every new subject id is in registry_subjects.csv exactly once", not missing,
          f"subjects {len(subj_old)} -> {len(subj_new)}; new ids {len(want_ids)}; "
          f"previously present {len(want_ids & {r[sid_col] for r in subj_old})}")
    for n in ("pending_subject_metadata.csv",):
        check(f"T1 {n} unchanged (no DB miss)", sha(os.path.join(base, n)) == sha(os.path.join(reg, n)))
    ok, a, b = prefix_ok(os.path.join(base, "ingest_manifest.csv"), os.path.join(reg, "ingest_manifest.csv"))
    nm = len(rows_of(os.path.join(reg, "ingest_manifest.csv"))) - len(rows_of(os.path.join(base, "ingest_manifest.csv")))
    check("M1 ingest_manifest.csv append-only, +202", ok and nm == 202, f"+{nm}")
    for n in ("registry_projects.csv", "retired_acquisitions.csv", "registry_datasets.csv", "pending_dicom_regen.csv"):
        check(f"O1 {n} byte-identical", sha(os.path.join(base, n)) == sha(os.path.join(reg, n)))

    fails = [n for n, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(fails)}/{len(RESULTS)} checks PASS")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
