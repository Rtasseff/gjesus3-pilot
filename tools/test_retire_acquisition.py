"""Unit tests for tools/retire_acquisition.py and its helpers (csv_safe.remove_records, ingest/retired.py,
registry.resolve_acq_id, the tombstone-aware ACQ-ID allocator and dedup index, the validator's tombstone
checks).

Builds a small fake NAS in a temp dir -- registries, /raw/ acquisitions, projects with real hard links --
and retires duplicates, a derivative and an orphan in it. No NAS, no network.
Run: python tools/test_retire_acquisition.py
"""
import contextlib
import csv
import glob
import hashlib
import io
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import retire_acquisition as RA  # noqa: E402
import validate_registries as VR  # noqa: E402
from ingest import acq_id as acq_mod, config as cfg_mod, csv_safe, registry, retired, subjects_table  # noqa: E402

_fail = 0


def check(cond, msg):
    global _fail
    print(("  ok:   " if cond else "  FAIL: ") + msg)
    if not cond:
        _fail += 1


# ---- fixture --------------------------------------------------------------------------------------

def W(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def write_csv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:     # csv default terminator = CRLF
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def reg_row(acq, eco, prim, kind="file", project="", subjects="", oname="", notes=""):
    d = acq.split("-")[1]
    canon = f"/raw/{eco}/{d[:4]}/{d[:4]}-{d[4:6]}/{acq}/"
    r = {f: "" for f in registry.REGISTRY_FIELDS}
    r.update(acq_id=acq, registration_datetime="2026-06-14T21:00:00Z",
             acquisition_datetime=f"{d[:4]}-{d[4:6]}-{d[6:]}T10:00:00", data_ecosystem=eco,
             instrument=acq.split("-")[2], researcher="Jesús Pérez", operator="AUA", sample_type="tissue",
             subject_ids=subjects, primary_kind=kind, primary_file_name=prim, original_name=oname or prim,
             canonical_path=canon, project_id=project, notes=notes, checksum_present="Y")
    return r


def make_acq(nas, row, files):
    """files: {relative path under the acq folder: bytes}. Writes sidecars + checksums.json."""
    d = RA.nas_abs(nas, row["canonical_path"])
    sums = {}
    for rel, data in files.items():
        W(os.path.join(d, *rel.split("/")), data)
        sums[rel] = hashlib.sha256(data).hexdigest()
    W(os.path.join(d, "checksums.json"), json.dumps(sums).encode())
    W(os.path.join(d, "metadata.json"), json.dumps({"acq_id": row["acq_id"]}).encode())
    W(os.path.join(d, "README.txt"), f"{row['acq_id']}\r\n".encode())
    return d


def link(nas, project, name, row):
    prim = RA.raw_primary_path(nas, row)
    dest = os.path.join(nas, "projects", project, "raw_linked", name)
    RA.link_tree(prim, dest)
    prov = os.path.join(nas, "projects", project, "provenance.csv")
    with open(prov, "a", encoding="utf-8", newline="") as f:
        n = sum(1 for _ in open(prov, encoding="utf-8")) if os.path.exists(prov) else 0
        csv.writer(f).writerow([f"FILE-{n:04d}", f"raw_linked/{name}", name,
                                "hardlink-folder" if os.path.isdir(prim) else "hardlink", "2026-06-14",
                                "AUA", row["acq_id"], "Auto-created during ingest", "ingest_raw.py", "", "",
                                "Auto-generated entry from ingest"])
    return dest


X = b"czi-bytes-X" * 1000
Y = b"czi-bytes-Y" * 1000
X2 = b"czi-bytes-x" * 1000      # same size as X, different bytes (a re-save)
Z = b"scalebar-copy" * 300


def build(nas):
    rows = [
        reg_row("ACQ-20260304-ZWSI-001", "MICROSCOPY", "ACQ-20260304-ZWSI-001.czi", project="PROJ-0001",
                subjects="1-AE-biomaGUNE-1123", oname="20260304/a.czi",
                notes='multi-line, "quoted"\nnote with a comma'),
        reg_row("ACQ-20260304-ZWSI-002", "MICROSCOPY", "ACQ-20260304-ZWSI-002.czi", project="PROJ-0001",
                subjects="2-AE-biomaGUNE-1123", oname="20260304/b.czi"),
        reg_row("ACQ-20260304-ZWSI-023", "MICROSCOPY", "ACQ-20260304-ZWSI-023.czi", project="PROJ-0002",
                subjects="1-AE-biomaGUNE-1123", oname="a.czi"),                       # dup of -001
        reg_row("ACQ-20260304-ZWSI-024", "MICROSCOPY", "ACQ-20260304-ZWSI-024.czi", project="PROJ-0001",
                subjects="9-AE-biomaGUNE-1123", oname="b.czi"),                       # dup of -002
        reg_row("ACQ-20260304-ZWSI-025", "MICROSCOPY", "ACQ-20260304-ZWSI-025.czi", project="PROJ-0001",
                oname="a_resaved.czi"),                                               # re-save of -001
        reg_row("ACQ-20260304-ZWSI-026", "MICROSCOPY", "ACQ-20260304-ZWSI-026.czi", project="PROJ-0001",
                oname="cited.czi"),                                                   # cited by a dataset
        reg_row("ACQ-20260304-ZWSI-027", "MICROSCOPY", "ACQ-20260304-ZWSI-027.czi", project="PROJ-0001",
                oname="sub/a_scalebar.czi"),                                          # derivative of -001
        reg_row("ACQ-20260304-ZWSI-028", "MICROSCOPY", "ACQ-20260304-ZWSI-028.czi", project="PROJ-0003",
                oname="thumb.czi"),                                                   # derivative, closed proj
        reg_row("ACQ-20211209-MRI-001", "DICOM", "ACQ-20211209-MRI-001.data", kind="folder",
                project="PROJ-0001", oname="m85/12"),
        reg_row("ACQ-20211209-MRI-002", "DICOM", "ACQ-20211209-MRI-002.data", kind="folder",
                project="PROJ-0002", oname="m85_copy/12"),                            # folder dup of MRI-001
    ]
    R = {r["acq_id"]: r for r in rows}
    reg = os.path.join(nas, "registries")
    write_csv(os.path.join(reg, "registry_raw.csv"), registry.REGISTRY_FIELDS,
              [[r[f] for f in registry.REGISTRY_FIELDS] for r in rows])
    write_csv(os.path.join(reg, "ingest_manifest.csv"), ["acq_id", "original_name", "canonical_path"],
              [[r["acq_id"], r["original_name"], r["canonical_path"]] for r in rows])
    write_csv(os.path.join(reg, "pending_subject_metadata.csv"),
              ["acq_id", "sidecar_path", "facility_animal_id", "reason", "logged_at", "status", "recovered_at"],
              [["ACQ-20260304-ZWSI-024", "/raw/x/metadata.json", "9-AE-biomaGUNE-1123", "db-miss",
                "2026-08-12T10:00:00Z", "pending", ""]])
    write_csv(os.path.join(reg, "registry_subjects.csv"), subjects_table.SUBJECT_FIELDS, [
        [s, s.split("-")[0], "1123", "Mus musculus", "", "M", "", "", "", "animal-facility-db",
         "2026-06-14T21:00:00Z", "2026-06-14T21:00:00Z"]
        for s in ("1-AE-biomaGUNE-1123", "2-AE-biomaGUNE-1123", "9-AE-biomaGUNE-1123")])
    write_csv(os.path.join(reg, "registry_projects.csv"),
              ["project_id", "name", "description", "owner", "start_date", "status", "last_activity",
               "folder_location", "notes"],
              [["PROJ-0001", "projA", "A", "x", "2026-01-01", "active", "2026-06-01", "/projects/projA/", ""],
               ["PROJ-0002", "projB", "B", "x", "2026-01-01", "active", "2026-06-01", "/projects/projB/", ""],
               ["PROJ-0003", "projC", "C", "x", "2026-01-01", "closed", "2026-06-01", "/projects/projC/", ""]])
    write_csv(os.path.join(reg, "registry_datasets.csv"),
              ["dataset_id", "short_name", "source_acq_ids", "folder_location"],
              [["DS-SEG-0001", "ds", "see provenance.csv", "/curated_datasets/segmentation/DICOM/DS-SEG-0001/"]])
    W(os.path.join(nas, "curated_datasets", "segmentation", "DICOM", "DS-SEG-0001", "provenance.csv"),
      b"file_id,input_refs\r\nFILE-0001,ACQ-20260304-ZWSI-026\r\n")
    W(os.path.join(reg, ".acq_id_seq.json"), b'{"ACQ-20260304-ZWSI-": 28}')
    for p in ("projA", "projB", "projC"):
        os.makedirs(os.path.join(nas, "projects", p, "raw_linked"), exist_ok=True)
        os.makedirs(os.path.join(nas, "projects", p, "outputs"), exist_ok=True)
        write_csv(os.path.join(nas, "projects", p, "provenance.csv"),
                  ["file_id", "output_path", "output_name", "file_type", "date_created", "creator",
                   "input_refs", "process_description", "software_version", "parameters_ref",
                   "lab_notebook_ref", "notes"], [])
    data = {"ACQ-20260304-ZWSI-001": X, "ACQ-20260304-ZWSI-002": Y, "ACQ-20260304-ZWSI-023": X,
            "ACQ-20260304-ZWSI-024": Y, "ACQ-20260304-ZWSI-025": X2, "ACQ-20260304-ZWSI-026": Y + b"!",
            "ACQ-20260304-ZWSI-027": Z, "ACQ-20260304-ZWSI-028": Z + b"t"}
    for a, b in data.items():
        make_acq(nas, R[a], {R[a]["primary_file_name"]: b})
    for a in ("ACQ-20211209-MRI-001", "ACQ-20211209-MRI-002"):
        make_acq(nas, R[a], {f"{a}.data/recon0.dcm": b"dcm0" * 500, f"{a}.data/recon1.dcm": b"dcm1" * 500})
    # project links, as an ingest made them
    link(nas, "projA", "ZWSI_a.czi", R["ACQ-20260304-ZWSI-001"])
    link(nas, "projB", "ZWSI_a_copy.czi", R["ACQ-20260304-ZWSI-023"])     # dup linked where survivor isn't
    link(nas, "projA", "ZWSI_b.czi", R["ACQ-20260304-ZWSI-002"])
    link(nas, "projA", "ZWSI_b_again.czi", R["ACQ-20260304-ZWSI-024"])   # dup linked beside its survivor
    link(nas, "projA", "ZWSI_a_scalebar.czi", R["ACQ-20260304-ZWSI-027"])
    link(nas, "projA", "MRI_m85_12", R["ACQ-20211209-MRI-001"])
    link(nas, "projB", "MRI_m85_12_copy", R["ACQ-20211209-MRI-002"])
    # an orphan: a /raw/ folder whose registry row never landed
    W(os.path.join(nas, "raw", "DICOM", "2026", "2026-07", "ACQ-20260710-MRI-001", "metadata.json"), b"{}")
    os.makedirs(os.path.join(nas, "raw", "DICOM", "2026", "2026-07", "ACQ-20260710-MRI-001",
                             "ACQ-20260710-MRI-001.data"), exist_ok=True)
    return R


def snapshot(nas):
    out = {}
    for root, _d, files in os.walk(nas):
        for fn in files:
            p = os.path.join(root, fn)
            with open(p, "rb") as f:
                out[os.path.relpath(p, nas)] = hashlib.sha256(f.read()).hexdigest()
    return out


def run(nas, bk, *args, fail_after=""):
    RA.FAIL_AFTER = fail_after
    RA._HASH_CACHE.clear()
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = RA.main(["--nas-root", nas, "--backup-root", bk, "--no-index", "--allow-recent-registry-writes",
                      "--retired-by", "tester", *args])
    RA.FAIL_AFTER = ""
    return rc, out.getvalue()


def raw_bytes(nas, fn):
    with open(os.path.join(nas, "registries", fn), "rb") as f:
        return f.read()


def live_ids(nas):
    return set(RA.read_live(nas))


def tombs(nas):
    return retired.read_retired(retired.retired_path(os.path.join(nas, "registries")))


def validator_errors(nas):
    with contextlib.redirect_stderr(io.StringIO()):
        issues, _n = VR.validate(nas, check_enrich=False)
    return [m for _a, m in issues.errors]


def prov_rows(nas, project):
    with open(os.path.join(nas, "projects", project, "provenance.csv"), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# ---- 1. byte-exact record removal -----------------------------------------------------------------
print("1. csv_safe.split_records / remove_records")
with tempfile.TemporaryDirectory() as d:
    data = (b'acq_id,notes\r\nA,"two\r\nlines, ""q"""\r\nB,plain\r\nC,caf\xc3\xa9\r\nD,last-no-newline')
    check(b"".join(csv_safe.split_records(data)) == data, "split_records round-trips every byte")
    check(len(csv_safe.split_records(data)) == 5, "a quoted newline does not end a record")
    p = os.path.join(d, "t.csv")
    W(p, data)
    gone = csv_safe.remove_records(p, "acq_id", {"A", "C"}, dry_run=True)
    check(len(gone) == 2 and open(p, "rb").read() == data, "dry_run reports, writes nothing")
    gone = csv_safe.remove_records(p, "acq_id", {"A", "C"})
    check(open(p, "rb").read() == b"acq_id,notes\r\nB,plain\r\nD,last-no-newline",
          "removal keeps every other byte (CRLF, quoting, a missing final newline)")
    check(csv_safe.remove_records(p, "acq_id", {"ZZ"}) == [], "no match -> nothing removed")

with tempfile.TemporaryDirectory() as tmp:
    nas, bk = os.path.join(tmp, "nas"), os.path.join(tmp, "bk")
    os.makedirs(bk)
    R = build(nas)
    reg_dir = os.path.join(nas, "registries")

    # ---- 2. dry run writes nothing ----
    print("2. dry run")
    before = snapshot(nas)
    rc, out = run(nas, bk, "--acq-id", "ACQ-20260304-ZWSI-023", "--duplicate-of", "ACQ-20260304-ZWSI-001",
                  "--reason", "operator recipe re-ingested the bulk-config file")
    check(rc == 0 and "SHA-256 identical" in out and "replace" in out, "dry run passes, plans a re-point")
    check(snapshot(nas) == before and not os.listdir(bk), "dry run wrote nothing (NAS + backup root)")

    # ---- 3. refusals ----
    print("3. refusals (nothing written)")
    rc, out = run(nas, bk, "--acq-id", "ACQ-20260304-ZWSI-025", "--duplicate-of", "ACQ-20260304-ZWSI-001",
                  "--reason", "r", "--execute")
    check(rc == 2 and "differ" in out and "SHA-256" in out, "non-identical bytes (a re-save) -> refused")
    rc, out = run(nas, bk, "--acq-id", "ACQ-20260304-ZWSI-026", "--duplicate-of", "ACQ-20260304-ZWSI-002",
                  "--reason", "r", "--execute")
    check(rc == 2 and "DS-SEG-0001" in out, "cited by a curated dataset -> refused, dataset named")
    rc, out = run(nas, bk, "--acq-id", "ACQ-20260304-ZWSI-028", "--derivative-of", "ACQ-20260304-ZWSI-001",
                  "--to-project", "projC", "--reason", "r", "--execute")
    check(rc == 2 and "closed" in out and "reopen_project" in out, "closed project -> refused, reopen hint")
    rc, out = run(nas, bk, "--acq-id", "ACQ-20260304-ZWSI-099", "--duplicate-of", "ACQ-20260304-ZWSI-001",
                  "--reason", "r", "--execute")
    check(rc == 2, "unknown id -> refused")
    lst = os.path.join(tmp, "list.csv")
    write_csv(lst, ["acq_id", "disposition", "target_acq_id", "to_project", "reason"],
              [["ACQ-20260304-ZWSI-023", "duplicate", "ACQ-20260304-ZWSI-001", "", "r"],
               ["ACQ-20260304-ZWSI-001", "duplicate", "ACQ-20260304-ZWSI-002", "", "r"]])
    rc, out = run(nas, bk, "--list", lst, "--execute")
    check(rc == 2 and "itself being retired" in out, "survivor retired in the same run -> whole list refused")
    lock = os.path.join(reg_dir, ".registry.lock")
    W(lock, b"pid=1")
    RA.FAIL_AFTER = ""
    with contextlib.redirect_stdout(io.StringIO()) as o:
        rc = RA.main(["--nas-root", nas, "--backup-root", bk, "--no-index", "--acq-id",
                      "ACQ-20260304-ZWSI-023", "--duplicate-of", "ACQ-20260304-ZWSI-001", "--reason", "r",
                      "--execute"])
    os.remove(lock)
    check(rc == 2 and "registry.lock" in o.getvalue(), "an ingest's lock held -> refused")
    check(snapshot(nas) == before and not os.listdir(bk), "no refusal wrote anything")

    # ---- 4. duplicate, project link re-pointed at the survivor; shared subject kept ----
    print("4. duplicate retire (link re-pointed)")
    raw_before = raw_bytes(nas, "registry_raw.csv")
    man_before = raw_bytes(nas, "ingest_manifest.csv")
    rc, out = run(nas, bk, "--acq-id", "ACQ-20260304-ZWSI-023", "--duplicate-of", "ACQ-20260304-ZWSI-001",
                  "--reason", "operator recipe re-ingested the bulk-config file", "--execute")
    check(rc == 0, f"execute rc=0 (got {rc})")
    t = tombs(nas).get("ACQ-20260304-ZWSI-023")
    check(t is not None and t["disposition"] == "duplicate" and t["superseded_by"] == "ACQ-20260304-ZWSI-001",
          "tombstone row written")
    check(t["sha256"] == hashlib.sha256(X).hexdigest() and t["bytes_fate"] == "deleted", "sha256 + bytes_fate")
    check("ACQ-20260304-ZWSI-023" not in live_ids(nas), "row left registry_raw.csv")
    recs = csv_safe.split_records(raw_before)
    expect = b"".join(r for r in recs if not r.startswith(b"ACQ-20260304-ZWSI-023,"))
    check(raw_bytes(nas, "registry_raw.csv") == expect, "registry_raw.csv: every other byte unchanged "
          "(incl. a quoted multi-line note and UTF-8)")
    check(t["registry_raw_row"].encode("utf-8") + b"\r\n" in recs, "tombstone holds the row verbatim")
    recs = csv_safe.split_records(man_before)
    check(raw_bytes(nas, "ingest_manifest.csv") ==
          b"".join(r for r in recs if not r.startswith(b"ACQ-20260304-ZWSI-023,")), "manifest row removed, byte-exact")
    tb = raw_bytes(nas, retired.RETIRED_FILENAME)
    check(not tb.startswith(b"\xef\xbb\xbf") and tb.count(b"\r\n") >= 2 and b"\n" not in tb.replace(b"\r\n", b""),
          "tombstone file: no BOM, CRLF")
    lk = os.path.join(nas, "projects", "projB", "raw_linked", "ZWSI_a_copy.czi")
    surv = RA.raw_primary_path(nas, R["ACQ-20260304-ZWSI-001"])
    check(os.path.exists(lk) and os.path.samefile(lk, surv), "projB link kept its name, now IS the survivor")
    check(not os.path.exists(RA.nas_abs(nas, R["ACQ-20260304-ZWSI-023"]["canonical_path"])), "/raw/ folder gone")
    ev = [r for r in prov_rows(nas, "projB") if "retire_acquisition" in r["notes"]]
    check(len(ev) == 1 and ev[0]["input_refs"] == "ACQ-20260304-ZWSI-001" and len(prov_rows(nas, "projB")) == 3,
          "projB provenance: one replaced-by event APPENDED, history kept")
    subj = subjects_table.read_subjects(subjects_table.subjects_path(reg_dir))
    check("1-AE-biomaGUNE-1123" in subj, "shared subject kept (the survivor references it)")
    bks = glob.glob(os.path.join(bk, "gjesus3_retire_backup_*"))
    check(len(bks) == 1 and os.path.exists(os.path.join(bks[0], "registries", "registry_raw.csv"))
          and os.path.exists(os.path.join(bks[0], "acquisitions", "ACQ-20260304-ZWSI-023", "metadata.json"))
          and os.path.exists(os.path.join(bks[0], "projects", "projB", "provenance.csv"))
          and not glob.glob(os.path.join(bks[0], "**", "*.czi"), recursive=True),
          "backup: registries + sidecars + touched provenance; NO duplicate bytes")
    check(open(os.path.join(bks[0], "registries", "registry_raw.csv"), "rb").read() == raw_before,
          "backup holds the pre-run registry")
    check(not [e for e in validator_errors(nas)], "validator: clean")

    # ---- 5. idempotent re-run ----
    print("5. idempotent re-run")
    before = snapshot(nas)
    rc, out = run(nas, bk, "--acq-id", "ACQ-20260304-ZWSI-023", "--duplicate-of", "ACQ-20260304-ZWSI-001",
                  "--reason", "operator recipe re-ingested the bulk-config file", "--execute")
    check(rc == 0 and "no-op" in out, "re-run after success: exit 0, no-op")
    check(snapshot(nas) == before and len(glob.glob(os.path.join(bk, "gjesus3_retire_backup_*"))) == 1,
          "re-run wrote nothing, took no backup")
    rc, out = run(nas, bk, "--acq-id", "ACQ-20260304-ZWSI-001", "--duplicate-of", "ACQ-20260304-ZWSI-002",
                  "--reason", "r")
    check(rc == 2 and "superseded_by" in out, "retiring a survivor a tombstone points at -> refused")

    # ---- 6. duplicate whose survivor is already linked in the project; unshared subject KEPT ----
    print("6. duplicate retire (survivor already linked; unshared subject kept; pending row)")
    subj_bytes = raw_bytes(nas, "registry_subjects.csv")
    rc, out = run(nas, bk, "--acq-id", "ACQ-20260304-ZWSI-024", "--duplicate-of", "ACQ-20260304-ZWSI-002",
                  "--reason", "operator recipe re-ingest", "--execute")
    check(rc == 0, f"execute rc=0 (got {rc})")
    check(not os.path.exists(os.path.join(nas, "projects", "projA", "raw_linked", "ZWSI_b_again.czi")),
          "duplicate's link removed (survivor already linked as ZWSI_b.czi)")
    check(os.path.samefile(os.path.join(nas, "projects", "projA", "raw_linked", "ZWSI_b.czi"),
                           RA.raw_primary_path(nas, R["ACQ-20260304-ZWSI-002"])), "survivor's own link untouched")
    subj = subjects_table.read_subjects(subjects_table.subjects_path(reg_dir))
    t = tombs(nas)["ACQ-20260304-ZWSI-024"]
    o = retired.other_rows(t)
    check("9-AE-biomaGUNE-1123" in subj and "registry_subjects.csv" not in o,
          "subject only the retiree referenced: KEPT (subjects are never deleted, 06 §2.8.3)")
    check(raw_bytes(nas, "registry_subjects.csv") == subj_bytes, "registry_subjects.csv byte-identical")
    check(o.get(RA.pending.PENDING_FILENAME) and
          not RA.pending.read_pending(os.path.join(reg_dir, RA.pending.PENDING_FILENAME)),
          "pending_subject_metadata row removed, kept verbatim")
    check(not validator_errors(nas), "validator: clean")

    # ---- 7. derivative: moved into the project, raw_linked link removed ----
    print("7. derivative retire")
    rc, out = run(nas, bk, "--acq-id", "ACQ-20260304-ZWSI-027", "--derivative-of", "ACQ-20260304-ZWSI-001",
                  "--to-project", "projA", "--reason", "scale-bar copy of -001", "--execute")
    check(rc == 0, f"execute rc=0 (got {rc})")
    dest = os.path.join(nas, "projects", "projA", "outputs", "derived", "a_scalebar.czi")
    check(os.path.exists(dest) and open(dest, "rb").read() == Z, "bytes now at outputs/derived/<original name>")
    t = tombs(nas)["ACQ-20260304-ZWSI-027"]
    check(t["bytes_fate"] == "moved" and t["moved_to"] == "/projects/projA/outputs/derived/a_scalebar.czi"
          and t["sha256"] == hashlib.sha256(Z).hexdigest(), "tombstone: moved_to + sha256")
    check(not os.path.exists(os.path.join(nas, "projects", "projA", "raw_linked", "ZWSI_a_scalebar.czi")),
          "raw_linked link removed")
    check(not os.path.exists(RA.nas_abs(nas, R["ACQ-20260304-ZWSI-027"]["canonical_path"])), "/raw/ folder gone")
    notes = [r["notes"] for r in prov_rows(nas, "projA")]
    check(any("moved-to" in n for n in notes) and any("link-removed" in n for n in notes),
          "provenance: moved-to + link-removed events")
    check(not validator_errors(nas), "validator: clean")

    # ---- 8. crash after the tombstone append, then resume (folder primary) ----
    print("8. crash-resume (folder-primary duplicate)")
    rc, out = run(nas, bk, "--acq-id", "ACQ-20211209-MRI-002", "--duplicate-of", "ACQ-20211209-MRI-001",
                  "--reason", "copied study folder re-ingested", "--execute", fail_after="tombstone")
    check(rc == 4, f"injected crash -> exit 4 (got {rc})")
    errs = validator_errors(nas)
    check(any("both live" in e for e in errs), "validator flags the half-done commit (live AND retired)")
    rc, out = run(nas, bk, "--acq-id", "ACQ-20211209-MRI-002", "--duplicate-of", "ACQ-20211209-MRI-001",
                  "--reason", "copied study folder re-ingested", "--execute")
    check(rc == 0 and "commit-interrupted" in out, f"re-run finishes it (rc={rc})")
    lk = os.path.join(nas, "projects", "projB", "raw_linked", "MRI_m85_12_copy")
    sv = RA.raw_primary_path(nas, R["ACQ-20211209-MRI-001"])
    check(all(os.path.samefile(os.path.join(lk, f), os.path.join(sv, f)) for f in ("recon0.dcm", "recon1.dcm")),
          "folder-of-links re-pointed file by file")
    check(len([k for k in tombs(nas) if k == "ACQ-20211209-MRI-002"]) == 1, "one tombstone row, not two")
    check(not validator_errors(nas), "validator: clean after resume")

    # ---- 9. crash after the links step (bytes still in /raw/), then resume ----
    print("9. crash-resume (after links, before the delete)")
    R2 = reg_row("ACQ-20260304-ZWSI-029", "MICROSCOPY", "ACQ-20260304-ZWSI-029.czi", project="PROJ-0002",
                 oname="b_copy.czi")
    with open(os.path.join(reg_dir, "registry_raw.csv"), "a", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow([R2[k] for k in registry.REGISTRY_FIELDS])
    make_acq(nas, R2, {R2["primary_file_name"]: Y})
    link(nas, "projB", "ZWSI_b_copy.czi", R2)
    rc, out = run(nas, bk, "--acq-id", "ACQ-20260304-ZWSI-029", "--duplicate-of", "ACQ-20260304-ZWSI-002",
                  "--reason", "copy", "--execute", fail_after="links")
    check(rc == 4 and os.path.isdir(RA.nas_abs(nas, R2["canonical_path"])), "crash left the /raw/ bytes")
    check(any("still exists" in e for e in validator_errors(nas)), "validator flags the undeleted folder")
    rc, out = run(nas, bk, "--acq-id", "ACQ-20260304-ZWSI-029", "--duplicate-of", "ACQ-20260304-ZWSI-002",
                  "--reason", "copy", "--execute")
    check(rc == 0 and not os.path.exists(RA.nas_abs(nas, R2["canonical_path"])), "re-run re-hashed + deleted")
    ev = [r for r in prov_rows(nas, "projB") if "ZWSI-029" in r["notes"]]
    check(len(ev) == 1, "exactly one provenance event despite two runs")
    check(not validator_errors(nas), "validator: clean")

    # ---- 10. orphan ----
    print("10. orphan")
    rc, out = run(nas, bk, "--acq-id", "ACQ-20260710-MRI-001", "--orphan", "--reason",
                  "partial ingest 2026-07-16: folder written, registry commit never landed", "--execute")
    check(rc == 0, f"orphan rc=0 (got {rc})")
    t = tombs(nas)["ACQ-20260710-MRI-001"]
    check(t["disposition"] == "orphan" and t["registry_raw_row"] == "" and t["superseded_by"] == "",
          "orphan tombstone: no row, no superseded_by")
    bko = glob.glob(os.path.join(bk, "*", "acquisitions", "ACQ-20260710-MRI-001", "metadata.json"))
    check(len(bko) == 1 and not os.path.exists(os.path.join(nas, "raw", "DICOM", "2026", "2026-07",
                                                            "ACQ-20260710-MRI-001")),
          "orphan folder backed up whole, then deleted")
    check(not validator_errors(nas), "validator: clean")

    # ---- 11. lookups, allocator, dedup ----
    print("11. resolve_acq_id / allocator / dedup")
    r = registry.resolve_acq_id("ACQ-20260304-ZWSI-023", reg_dir)
    check(r["status"] == "retired" and r["resolved"] == "ACQ-20260304-ZWSI-001"
          and r["row"].get("original_name") == "a.czi", "retired id resolves to its survivor + original row")
    check(registry.resolve_acq_id("ACQ-20260304-ZWSI-001", reg_dir)["status"] == "live", "live id")
    check(registry.resolve_acq_id("ACQ-20260304-ZWSI-077", reg_dir)["status"] == "unknown", "unknown id")
    os.remove(os.path.join(reg_dir, ".acq_id_seq.json"))         # the reservation file is gone
    nxt = acq_mod.generate_acq_id("20260304", "ZWSI", os.path.join(reg_dir, "registry_raw.csv"))
    check(nxt == "ACQ-20260304-ZWSI-030", f"allocator never reuses a retired id (got {nxt}; -029 is retired)")
    keys = cfg_mod._build_dedupe_index(os.path.join(reg_dir, "registry_raw.csv"))
    check(("20260304", "a.czi") in keys, "dedup index still blocks the retired duplicate's source")

    # ---- 12. validator catches a dataset citing a retired id, and a broken superseded_by ----
    print("12. validator tombstone checks")
    W(os.path.join(nas, "curated_datasets", "segmentation", "DICOM", "DS-SEG-0001", "slice_map.csv"),
      b"acq\r\nACQ-20260304-ZWSI-024\r\n")
    errs = validator_errors(nas)
    check(any("cited by curated dataset" in e and "DS-SEG-0001" in e for e in errs),
          "a curated dataset citing a retired id -> ERROR")
    os.remove(os.path.join(nas, "curated_datasets", "segmentation", "DICOM", "DS-SEG-0001", "slice_map.csv"))
    tp = retired.retired_path(reg_dir)
    good = open(tp, "rb").read()
    W(tp, good.replace(b",ACQ-20260304-ZWSI-002,", b",ACQ-20260304-ZWSI-098,", 1))
    check(any("not a live acquisition" in e for e in validator_errors(nas)), "dangling superseded_by -> ERROR")
    W(tp, good)
    check(not validator_errors(nas), "validator: clean again")

# ---- 13. a crash at EVERY step resumes to the same end state ----
print("13. crash-resume sweep (derivative, every injection point)")
for step in ("placed", "tombstone", "commit", "links", "bytes", "provenance"):
    with tempfile.TemporaryDirectory() as tmp:
        nas, bk = os.path.join(tmp, "nas"), os.path.join(tmp, "bk")
        os.makedirs(bk)
        R = build(nas)
        args = ("--acq-id", "ACQ-20260304-ZWSI-027", "--derivative-of", "ACQ-20260304-ZWSI-001",
                "--to-project", "projA", "--reason", "scale-bar copy", "--execute")
        rc1, _ = run(nas, bk, *args, fail_after=step)
        rc2, out2 = run(nas, bk, *args)
        rc3, out3 = run(nas, bk, *args)
        t = tombs(nas)
        dest = os.path.join(nas, "projects", "projA", "outputs", "derived", "a_scalebar.czi")
        notes = [r["notes"] for r in prov_rows(nas, "projA") if "retire_acquisition" in r["notes"]]
        ok = (rc1 == 4 and rc2 == 0 and rc3 == 0 and "no-op" in out3
              and list(t) == ["ACQ-20260304-ZWSI-027"]
              and "ACQ-20260304-ZWSI-027" not in live_ids(nas)
              and open(dest, "rb").read() == Z
              and not os.path.exists(os.path.join(nas, "projects", "projA", "raw_linked", "ZWSI_a_scalebar.czi"))
              and not os.path.exists(RA.nas_abs(nas, R["ACQ-20260304-ZWSI-027"]["canonical_path"]))
              and sorted(n.split()[-1] for n in notes) == ["link-removed", "moved-to"]
              and not validator_errors(nas))
        check(ok, f"crash after '{step}': rc {rc1}->{rc2}->{rc3}, same end state, one tombstone, two events")

print("14. crash-resume sweep (duplicate, every injection point)")
for step in ("tombstone", "commit", "links", "bytes", "provenance"):
    with tempfile.TemporaryDirectory() as tmp:
        nas, bk = os.path.join(tmp, "nas"), os.path.join(tmp, "bk")
        os.makedirs(bk)
        R = build(nas)
        args = ("--acq-id", "ACQ-20260304-ZWSI-023", "--duplicate-of", "ACQ-20260304-ZWSI-001",
                "--reason", "dup", "--execute")
        rc1, _ = run(nas, bk, *args, fail_after=step)
        rc2, _ = run(nas, bk, *args)
        rc3, out3 = run(nas, bk, *args)
        lk = os.path.join(nas, "projects", "projB", "raw_linked", "ZWSI_a_copy.czi")
        notes = [r["notes"] for r in prov_rows(nas, "projB") if "retire_acquisition" in r["notes"]]
        ok = (rc1 == 4 and rc2 == 0 and rc3 == 0 and "no-op" in out3
              and list(tombs(nas)) == ["ACQ-20260304-ZWSI-023"]
              and os.path.samefile(lk, RA.raw_primary_path(nas, R["ACQ-20260304-ZWSI-001"]))
              and not os.path.exists(RA.nas_abs(nas, R["ACQ-20260304-ZWSI-023"]["canonical_path"]))
              and notes == ["retire_acquisition: ACQ-20260304-ZWSI-023 replaced-by ACQ-20260304-ZWSI-001"]
              and not validator_errors(nas))
        check(ok, f"crash after '{step}': rc {rc1}->{rc2}->{rc3}, link IS the survivor, one event")

print("ALL PASSED" if not _fail else f"{_fail} FAILURE(S)")
sys.exit(1 if _fail else 0)
