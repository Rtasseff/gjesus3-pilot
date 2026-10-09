"""Tests for retire_acquisition.py's `no-dicom` disposition (2026-10-08): DICOM-less MRI placeholders
(pending_dicom_regen not-applicable / no-source) retired, their folder's files moved into the project as
other data beside a README_not_registered.txt; plus the list builder and the validator / tombstone rules.

Builds a small fake NAS in a temp dir (registries, /raw/ placeholders, projects with real hard links).
No NAS, no network.  Run: python tools/test_retire_no_dicom.py
"""
import contextlib
import csv
import hashlib
import io
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import retire_acquisition as RA  # noqa: E402
import validate_registries as VR  # noqa: E402
from ingest import config as cfg_mod, pending_dicom, registry, retired, subjects_table  # noqa: E402

_fail = 0


def check(cond, msg):
    global _fail
    print(("  ok:   " if cond else "  FAIL: ") + msg)
    if not cond:
        _fail += 1


def W(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def write_csv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


PROV_HEADER = ["file_id", "output_path", "output_name", "file_type", "date_created", "creator", "input_refs",
               "process_description", "software_version", "parameters_ref", "lab_notebook_ref", "notes"]
S1 = "20220119_081642_jrc220119_m10_1521_1_1"
S2 = "20250526_105636_jrc250526_145_0522_1_1"


def mri_row(acq, exam, project="", study=S1, files=0):
    d = acq.split("-")[1]
    r = {f: "" for f in registry.REGISTRY_FIELDS}
    r.update(acq_id=acq, registration_datetime="2026-06-14T21:00:00Z",
             acquisition_datetime=f"{d[:4]}-{d[4:6]}-{d[6:]}T10:00:00", data_ecosystem="DICOM",
             instrument="MRI", sample_type="organism", primary_kind="folder", primary_file_name=f"{acq}.data",
             original_name=f"{study}/{exam}", canonical_path=f"/raw/DICOM/{d[:4]}/{d[:4]}-{d[4:6]}/{acq}/",
             project_id=project, file_count=str(files), checksum_present="N" if not files else "Y")
    return r


# acq -> (exam, project, pending status, marker, primary files)
SPEC = {
    "ACQ-20220119-MRI-039": ("3", "PROJ-0001", "not-applicable", "STEAM", 0),   # empty link -> removed
    "ACQ-20220119-MRI-040": ("4", "PROJ-0001", "no-source", "", 0),            # no link; placed k-space
    "ACQ-20220119-MRI-041": ("5", "PROJ-0001", "no-source", "", 0),            # link name held by MRI-001
    "ACQ-20220119-MRI-042": ("6", "PROJ-0001", "pending", "", 0),              # still regenerable: refused
    "ACQ-20220119-MRI-043": ("7", "PROJ-0001", "no-source", "", 1),            # primary holds a file: refused
    "ACQ-20220119-MRI-044": ("8", "PROJ-0001", "not-applicable", "PRESS", 0),  # shares an empty link with 045
    "ACQ-20220119-MRI-045": ("9", "PROJ-0001", "not-applicable", "WOBBLE", 0),
    "ACQ-20220119-MRI-050": ("10", "PROJ-0003", "no-source", "", 0),           # closed project: refused
    "ACQ-20250526-MRI-094": ("7", "", "no-source", "", 0),                     # no project: holding
    "ACQ-20220119-MRI-001": ("1", "PROJ-0001", "regenerated", "", 2),          # a real image exam
}


def build(nas):
    reg = os.path.join(nas, "registries")
    rows = []
    for acq, (exam, proj, _st, _mk, nfiles) in SPEC.items():
        # 043: the registry says empty (file_count 0) but the disk holds a file -- the disk check must catch it
        r = mri_row(acq, exam, proj, study=S2 if "2025" in acq else S1, files=0 if acq.endswith("043") else nfiles)
        rows.append(r)
        d = RA.nas_abs(nas, r["canonical_path"])
        os.makedirs(os.path.join(d, f"{acq}.data"), exist_ok=True)
        sums = {}
        for i in range(nfiles):
            data = f"dcm-{acq}-{i}".encode() * 200
            W(os.path.join(d, f"{acq}.data", f"recon1_frame{i:02d}.dcm"), data)
            sums[f"{acq}.data/recon1_frame{i:02d}.dcm"] = hashlib.sha256(data).hexdigest()
        W(os.path.join(d, "metadata.json"), json.dumps({"acq_id": acq, "mri": {"method": "x" * 300}}).encode())
        W(os.path.join(d, "checksums.json"), json.dumps(sums).encode())
        W(os.path.join(d, "README.txt"), f"Acquisition {acq}\r\n".encode())
    write_csv(os.path.join(reg, "registry_raw.csv"), registry.REGISTRY_FIELDS,
              [[r[f] for f in registry.REGISTRY_FIELDS] for r in rows])
    write_csv(os.path.join(reg, "ingest_manifest.csv"), ["acq_id", "original_name", "canonical_path"],
              [[r["acq_id"], r["original_name"], r["canonical_path"]] for r in rows])
    write_csv(os.path.join(reg, pending_dicom.PENDING_DICOM_FILENAME), pending_dicom.PENDING_DICOM_FIELDS,
              [[acq, f"{S1}/{e}", "all", mri_row(acq, e)["canonical_path"], "6.0.1", "cfg.yaml", mk,
                "2026-07-15T19:09:23+02:00", st] for acq, (e, _p, st, mk, _n) in SPEC.items()])
    write_csv(os.path.join(reg, "registry_subjects.csv"), subjects_table.SUBJECT_FIELDS, [])
    write_csv(os.path.join(reg, "registry_projects.csv"),
              ["project_id", "name", "description", "owner", "start_date", "status", "last_activity",
               "folder_location", "notes"],
              [["PROJ-0001", "projA", "A", "x", "2022-01-01", "active", "2022-06-01", "/projects/projA/", ""],
               ["PROJ-0003", "projC", "C", "x", "2022-01-01", "closed", "2022-06-01", "/projects/projC/", ""]])
    for p in ("projA",):
        write_csv(os.path.join(nas, "projects", p, "provenance.csv"), PROV_HEADER, [])
        os.makedirs(os.path.join(nas, "projects", p, "raw_linked"), exist_ok=True)
        os.makedirs(os.path.join(nas, "projects", p, "working"), exist_ok=True)
    R = {r["acq_id"]: r for r in rows}

    def link(name, acq, make=True):
        dest = os.path.join(nas, "projects", "projA", "raw_linked", name)
        if make:
            RA.link_tree(RA.raw_primary_path(nas, R[acq]), dest)
            os.makedirs(dest, exist_ok=True)       # an empty primary makes an empty folder
        with open(os.path.join(nas, "projects", "projA", "provenance.csv"), "a", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow(["", f"raw_linked/{name}", name, "hardlink-folder", "2026-06-14", "ingest",
                                    acq, "Auto-created during ingest", "ingest_raw.py", "", "", ""])
    link("MRI_m10_1521_20220119_1_1", "ACQ-20220119-MRI-001")
    link("MRI_m10_1521_20220119_3_1", "ACQ-20220119-MRI-039")
    link("MRI_m10_1521_20220119_1_1", "ACQ-20220119-MRI-041", make=False)   # its planned name, held by 001
    link("MRI_shared_8_1", "ACQ-20220119-MRI-044")
    link("MRI_shared_8_1", "ACQ-20220119-MRI-045", make=False)
    # a historical-drives placement holding other files of MRI-040's exam
    placed = os.path.join(nas, "projects", "projA", "working", "historical_drives", "DRV", "MRI", S1, "4")
    W(os.path.join(placed, "fid"), b"k-space" * 100)
    write_csv(os.path.join(nas, "projects", "projA", "working", "historical_drives", "_INDEX.csv"),
              ["new_path", "drive", "archive", "original_path", "size", "sha256", "claim_id", "shortened", "why",
               "note"], [[f"DRV\\MRI\\{S1}\\4\\fid", "drv", "", f"drv\\{S1}\\4\\fid", "700", "x", "", "N", "", ""]])
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


def tombs(nas):
    return retired.read_retired(retired.retired_path(os.path.join(nas, "registries")))


def validator_errors(nas):
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
        issues, _n = VR.validate(nas, check_enrich=False)
    return [m for _a, m in issues.errors]


def prov_rows(nas):
    with open(os.path.join(nas, "projects", "projA", "provenance.csv"), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def read_list(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_list(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=RA.LIST_FIELDS)
        w.writeheader()
        w.writerows(rows)


def dest_of(nas, exam, study=S1):
    return os.path.join(nas, "projects", "projA", "working", "mri_not_registered", study, exam)


# ---- 0. csv_safe.split_records (the fast form) = the byte-by-byte reference -------------------------
print("0. csv_safe.split_records equals the byte-by-byte reference")


def _split_reference(data):
    records, start, in_quote = [], 0, False
    for i, c in enumerate(data):
        if c == 0x22:
            in_quote = not in_quote
        elif c == 0x0A and not in_quote:
            records.append(data[start:i + 1])
            start = i + 1
    if start < len(data):
        records.append(data[start:])
    return records


import random  # noqa: E402
rng = random.Random(20261008)
cases = [b"", b"a", b"\n", b'"', b'a,"b\r\nc",d\r\ne,f', b'x,"""q""\n"\r\ny\n', b"a\r\nb\r\n", b'"\n"\n"']
cases += [bytes(rng.choice(b'ab,"\r\n') for _ in range(rng.randint(0, 60))) for _ in range(3000)]
from ingest import csv_safe  # noqa: E402
check(all(csv_safe.split_records(c) == _split_reference(c) for c in cases),
      f"identical records on {len(cases)} inputs (quoted newlines, escaped quotes, CRLF, no final newline)")

# ---- 1. the tombstone rules ---------------------------------------------------------------------
print("1. retired.append_retired / the validator accept no-dicom with no superseded_by")
with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, "retired_acquisitions.csv")
    retired.append_retired(path, {"acq_id": "ACQ-20220119-MRI-039", "disposition": "no-dicom",
                                  "superseded_by": "", "reason": "r", "bytes_fate": "moved"})
    check(list(retired.read_retired(path)) == ["ACQ-20220119-MRI-039"], "no-dicom appended with superseded_by blank")
    try:
        retired.append_retired(path, {"acq_id": "ACQ-20220119-MRI-040", "disposition": "derivative",
                                      "superseded_by": "", "reason": "r", "bytes_fate": "moved"})
        check(False, "a derivative without superseded_by is refused")
    except RuntimeError:
        check(True, "a derivative without superseded_by is still refused")
    check(set(retired.NO_SUPERSEDER) == {"orphan", "no-dicom"}, "NO_SUPERSEDER = orphan, no-dicom")

# ---- 2. the list builder -------------------------------------------------------------------------
print("2. --build-no-dicom-lists (read-only)")
with tempfile.TemporaryDirectory() as tmp:
    nas, bk, lists = os.path.join(tmp, "nas"), os.path.join(tmp, "bk"), os.path.join(tmp, "lists")
    os.makedirs(bk)
    build(nas)
    before = snapshot(nas)
    rc, out = run(nas, bk, "--build-no-dicom-lists", lists)
    op, cl, nop = (read_list(os.path.join(lists, f"no_dicom_{g}.csv")) for g in ("open", "closed", "no_project"))
    check(rc == 0 and snapshot(nas) == before, f"rc {rc}; nothing under the NAS root written")
    check(sorted(r["acq_id"][-3:] for r in op) == ["039", "040", "041", "043", "044", "045"],
          f"open: the terminal-status placeholders in active projects ({[r['acq_id'][-3:] for r in op]}); "
          f"'pending' and 'regenerated' left out")
    check([r["acq_id"][-3:] for r in cl] == ["050"] and [r["acq_id"][-3:] for r in nop] == ["094"],
          "closed: 050; no project: 094")
    r40 = next(r for r in op if r["acq_id"].endswith("040"))
    check(r40["see_also"] == f"projects/projA/working/historical_drives/DRV/MRI/{S1}/4"
          and r40["dest_name"] == f"{S1}/4" and r40["subfolder"] == RA.NO_DICOM_SUBFOLDER,
          "040: dest <study>/<exam>, see_also = the placed exam folder")
    check(nop[0]["subfolder"] == RA.NO_DICOM_HOLDING and nop[0]["to_project"] == "",
          "no project: the holding folder under staging/")
    check("spectroscopy" in next(r for r in op if r["acq_id"].endswith("039"))["reason"]
          and "no reconstruction" in r40["reason"], "the reason tells spectroscopy from no reconstruction")

    # ---- 3. dry runs ------------------------------------------------------------------------------
    print("3. dry runs refuse what is not an empty terminal placeholder; write nothing")
    rc, out = run(nas, bk, "--list", os.path.join(lists, "no_dicom_open.csv"))
    check(rc == 2 and "ACQ-20220119-MRI-043" in out and "holds files" in out and snapshot(nas) == before,
          "043 (primary holds a file) refuses the whole run; nothing written")
    rc, out = run(nas, bk, "--acq-id", "ACQ-20220119-MRI-042", "--no-dicom", "--to-project", "projA",
                  "--reason", "x")
    check(rc == 2 and "'pending'" in out, "042 (status pending, still regenerable) is refused")
    rc, out = run(nas, bk, "--list", os.path.join(lists, "no_dicom_closed.csv"))
    check(rc == 2 and "closed" in out, "050 (closed project) is refused")
    rc, out = run(nas, bk, "--acq-id", "ACQ-20220119-MRI-001", "--no-dicom", "--to-project", "projA",
                  "--reason", "x")
    check(rc == 2 and snapshot(nas) == before, "a real image exam (regenerated, DICOM) is refused")
    good = [r for r in op if not r["acq_id"].endswith("043")]
    write_list(os.path.join(lists, "good.csv"), good)
    rc, out = run(nas, bk, "--list", os.path.join(lists, "good.csv"))
    check(rc == 0 and snapshot(nas) == before and "5 item(s): 5 with work" in out, f"dry run rc {rc}, read-only")
    check("link: remove   /projects/projA/raw_linked/MRI_m10_1521_20220119_3_1" in out
          and "link: foreign  /projects/projA/raw_linked/MRI_m10_1521_20220119_1_1" in out
          and "link: remove   /projects/projA/raw_linked/MRI_shared_8_1" in out,
          "plan: 039's empty link removed, 041's name (held by 001) left alone, the shared empty one removed")
    one = [r for r in good if r["acq_id"].endswith("044")]
    write_list(os.path.join(lists, "one.csv"), one)
    rc, out = run(nas, bk, "--list", os.path.join(lists, "one.csv"))
    check(rc == 0 and "also the link entry of the live ACQ-20220119-MRI-045" in out,
          "044 alone: the empty folder is also 045's link entry, so it is left alone")

    # ---- 4. execute -------------------------------------------------------------------------------
    print("4. execute: rows, files, links, provenance, validator")
    reg = os.path.join(nas, "registries")
    raw_before = open(os.path.join(reg, "registry_raw.csv"), "rb").read()
    srcs = {}
    for r in good:
        acq = r["acq_id"]
        dd = RA.nas_abs(nas, mri_row(acq, "x")["canonical_path"])
        srcs[acq] = {fn: hashlib.sha256(open(os.path.join(dd, fn), "rb").read()).hexdigest()
                     for fn in ("metadata.json", "checksums.json", "README.txt")}
    foreign = os.path.join(nas, "projects", "projA", "raw_linked", "MRI_m10_1521_20220119_1_1")
    foreign_before = {fn: os.stat(os.path.join(foreign, fn)).st_ino for fn in os.listdir(foreign)}
    rc, out = run(nas, bk, "--list", os.path.join(lists, "good.csv"), "--execute")
    check(rc == 0 and "self-check: OK for 5 item(s)" in out, f"execute rc {rc}")
    T = tombs(nas)
    ids = {r["acq_id"] for r in good}
    check(set(T) == ids and all(t["disposition"] == "no-dicom" and t["superseded_by"] == ""
                                and t["bytes_fate"] == "moved" for t in T.values()),
          "5 tombstones: no-dicom, superseded_by blank, bytes moved")
    t39 = T["ACQ-20220119-MRI-039"]
    check(t39["moved_to"] == f"/projects/projA/working/mri_not_registered/{S1}/3/"
          and json.loads(t39["other_rows_removed"]).keys() == {"ingest_manifest.csv", "pending_dicom_regen.csv"},
          "moved_to = the folder; the manifest and pending_dicom_regen rows carried verbatim")
    _r, ev = retired.split_evidence(t39["reason"])
    check(ev["method"] == "no-dicom/1" and ev["pending_dicom_status"] == "not-applicable"
          and ev["nonimage_marker"] == "STEAM" and ev["files"] == srcs["ACQ-20220119-MRI-039"]
          and t39["sha256"] == RA.tree_digest(ev["files"]), "evidence: status, marker, every file's SHA-256")
    live = set(RA.read_live(nas))
    check(live == set(SPEC) - ids, "registry_raw lost exactly the retired set")
    kept = [ln for ln in raw_before.split(b"\r\n") if not any(a.encode() in ln for a in ids)]
    check(open(os.path.join(reg, "registry_raw.csv"), "rb").read().split(b"\r\n") == kept,
          "every other registry_raw byte unchanged")
    pdl = {r["acq_id"]: r["status"] for r in pending_dicom.read_pending_dicom(os.path.join(reg, "pending_dicom_regen.csv"))}
    check(set(pdl) == set(SPEC) - ids, "pending_dicom_regen: the retired rows left the worklist")
    moved_ok = all(hashlib.sha256(open(os.path.join(dest_of(nas, SPEC[a][0], S2 if "2025" in a else S1), fn),
                                       "rb").read()).hexdigest() == h
                   for a, fs in srcs.items() if a in ids and SPEC[a][1] for fn, h in fs.items())
    check(moved_ok, "every moved file SHA-256-identical at its destination")
    check(not any(os.path.exists(RA.nas_abs(nas, mri_row(a, 'x')['canonical_path'])) for a in ids),
          "the /raw/ folders are gone")
    rd = open(os.path.join(dest_of(nas, "4"), RA.NOTREG_README), encoding="utf-8").read()
    check("ACQ-20220119-MRI-040" in rd and "no reconstructed image" in rd
          and f"projects\\projA\\working\\historical_drives\\DRV\\MRI\\{S1}\\4" in rd,
          "README names the retired id, the reason and the placed copy")
    rd39 = open(os.path.join(dest_of(nas, "3"), RA.NOTREG_README), encoding="utf-8").read()
    check("spectroscopy or calibration (STEAM)" in rd39 and "raw_linked\\MRI_m10_1521_20220119_3_1" in rd39,
          "README (039): spectroscopy, and its removed link")
    check(not os.path.exists(os.path.join(nas, "projects", "projA", "raw_linked", "MRI_m10_1521_20220119_3_1"))
          and not os.path.exists(os.path.join(nas, "projects", "projA", "raw_linked", "MRI_shared_8_1")),
          "the empty link folders are removed")
    check({fn: os.stat(os.path.join(foreign, fn)).st_ino for fn in os.listdir(foreign)} == foreign_before
          and os.path.samefile(os.path.join(foreign, "recon1_frame00.dcm"),
                               os.path.join(RA.raw_primary_path(nas, mri_row("ACQ-20220119-MRI-001", "1")),
                                            "recon1_frame00.dcm")),
          "the link another acquisition holds is untouched")
    notes = sorted(r["notes"] for r in prov_rows(nas) if "retire_acquisition" in r["notes"])
    check(notes == sorted([f"retire_acquisition: {a} moved-to" for a in ids]
                          + ["retire_acquisition: ACQ-20220119-MRI-039 link-removed",
                             "retire_acquisition: ACQ-20220119-MRI-044 link-removed",
                             "retire_acquisition: ACQ-20220119-MRI-045 retired"]),
          f"provenance: one moved-to per exam, link-removed / retired per link entry ({len(notes)} rows)")
    errs = validator_errors(nas)
    check(not errs, f"validator: 0 errors ({errs[:3]})")
    rc, out = run(nas, bk, "--list", os.path.join(lists, "good.csv"), "--execute")
    check(rc == 0 and "no-op" in out, "re-run: no-op")
    keys = cfg_mod._build_dedupe_index(os.path.join(reg, "registry_raw.csv"))
    check(("20220119", f"{S1}/3") in keys, "a no-dicom tombstone keeps blocking a re-ingest (dedup index)")

    # ---- 5. holding ------------------------------------------------------------------------------
    print("5. no project: the holding folder")
    rc, out = run(nas, bk, "--list", os.path.join(lists, "no_dicom_no_project.csv"), "--execute")
    hold = os.path.join(nas, "staging", "mri_not_registered", S2, "7")
    t94 = tombs(nas)["ACQ-20250526-MRI-094"]
    check(rc == 0 and os.path.isfile(os.path.join(hold, "metadata.json"))
          and os.path.isfile(os.path.join(hold, RA.NOTREG_README))
          and t94["moved_to"] == f"/staging/mri_not_registered/{S2}/7/" and not validator_errors(nas),
          f"rc {rc}: files and README in staging/mri_not_registered/<study>/<exam>/")

# ---- 6. crash-resume sweep -------------------------------------------------------------------------
print("6. crash-resume sweep (no-dicom, every injection point)")
for step in ("placed", "tombstone", "commit", "links", "bytes", "provenance"):
    with tempfile.TemporaryDirectory() as tmp:
        nas, bk = os.path.join(tmp, "nas"), os.path.join(tmp, "bk")
        os.makedirs(bk)
        build(nas)
        args = ("--acq-id", "ACQ-20220119-MRI-039", "--no-dicom", "--to-project", "projA",
                "--reason", "spectroscopy", "--execute")
        rc1, _ = run(nas, bk, *args, fail_after=step)
        rc2, o2 = run(nas, bk, *args)
        rc3, out3 = run(nas, bk, *args)
        notes = sorted(r["notes"] for r in prov_rows(nas) if "retire_acquisition" in r["notes"])
        ok = (rc1 == 4 and rc2 == 0 and rc3 == 0 and "no-op" in out3
              and list(tombs(nas)) == ["ACQ-20220119-MRI-039"]
              and os.path.isfile(os.path.join(dest_of(nas, "3"), "metadata.json"))
              and not os.path.exists(os.path.join(nas, "projects", "projA", "raw_linked", "MRI_m10_1521_20220119_3_1"))
              and notes == ["retire_acquisition: ACQ-20220119-MRI-039 link-removed",
                            "retire_acquisition: ACQ-20220119-MRI-039 moved-to"]
              and not validator_errors(nas))
        check(ok, f"crash after '{step}': rc {rc1}->{rc2}->{rc3}, same end state, one tombstone, two events")

print("ALL PASSED" if not _fail else f"{_fail} FAILURE(S)")
sys.exit(1 if _fail else 0)
