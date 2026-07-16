#!/usr/bin/env python3
"""test_backfill_dicom_regen.py — the no-DICOM backfill CLI (2026-07-16).

Covers everything testable WITHOUT Dicomifier or the NAS: the pure value
helpers, the controlled-write sidecar/README refreshes, and the full per-row
decision state machine (dry-run and apply) against tmpdir fixtures — including
the crash-recovery reconcile path end-to-end (verify → checksums.json →
registry.update_row under the lock → worklist flip). The only path NOT covered
here is the Dicomifier subprocess itself, which is the ingest's own
copy_mri_paravision (validated 2026-06-01) and is exercised by the staged
pilot run (--apply --limit 1) before the batch.

Run:  PYTHONPATH=tools python tools/test_backfill_dicom_regen.py
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import backfill_dicom_regen as bf  # noqa: E402
from ingest import checksum, pending_dicom, registry  # noqa: E402

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok:   {msg}")


def quiet_log(msg, level="INFO"):
    pass


# ------------------------------------------------------------ pure helpers

def test_parse_reconstructions():
    print("[parse_reconstructions round-trips the str()-ified worklist value]")
    check(bf.parse_reconstructions("") is None, "'' -> None")
    check(bf.parse_reconstructions("None") is None, "'None' -> None")
    check(bf.parse_reconstructions("all") == "all", "'all' -> 'all'")
    check(bf.parse_reconstructions("3") == "3", "'3' -> '3' (single index)")
    check(bf.parse_reconstructions("[1, 3]") == [1, 3], "'[1, 3]' -> [1, 3]")


def test_datetime_from_dicom_tags():
    print("[StudyDate/StudyTime -> registry-normalized ISO]")
    check(bf.datetime_from_dicom_tags("20220128", "085233")
          == "2022-01-28T08:52:33Z", "date+time -> full ISO")
    check(bf.datetime_from_dicom_tags("20220128", "085233.512")
          == "2022-01-28T08:52:33Z", "fractional seconds dropped")
    check(bf.datetime_from_dicom_tags("20220128", "")
          == "2022-01-28T00:00:00Z", "date-only form")
    check(bf.datetime_from_dicom_tags("", "085233") == "", "no date -> ''")
    check(bf.datetime_from_dicom_tags("2022012", "") == "", "malformed -> ''")


def test_staged_path_and_source_checks():
    print("[staged path resolution + 2dseq / no-source classification]")
    row = {"paravision_version": "7.0.0",
           "original_name": "20220128_083412_study_1_1/17"}
    with tempfile.TemporaryDirectory() as tmp:
        p = bf.staged_exam_path(tmp, row)
        check(p == os.path.join(tmp, "PV7.0.0",
                                "20220128_083412_study_1_1", "17"),
              "PV<ver>/<study>/<exam> layout")
        check(bf.staged_exam_path(tmp, {"paravision_version": "",
                                        "original_name": "a/1"}) is None,
              "missing PV version -> None")
        check(bf.staged_exam_path(tmp, {"paravision_version": "7.0.0",
                                        "original_name": "noslash"}) is None,
              "unsplittable original_name -> None")
        # 2dseq detection
        exam = os.path.join(tmp, "exam")
        os.makedirs(os.path.join(exam, "pdata", "1"))
        check(not bf.has_2dseq(exam), "pdata/1 without 2dseq -> False")
        open(os.path.join(exam, "pdata", "1", "2dseq"), "w").close()
        check(bf.has_2dseq(exam), "pdata/1/2dseq -> True")
        # no-source kind
        check(bf.no_source_kind(exam) == "header-only", "no fid -> header-only")
        open(os.path.join(exam, "fid"), "w").close()
        check(bf.no_source_kind(exam) == "fid-only", "fid present -> fid-only")


def test_update_sidecar_age():
    print("[sidecar age: blank-only fill, atomic, verified]")
    with tempfile.TemporaryDirectory() as tmp:
        sc = os.path.join(tmp, "metadata.json")

        def write(subject):
            with open(sc, "w", encoding="utf-8") as f:
                json.dump({"acq_id": "ACQ-X", "subject": subject}, f)

        write({"date_of_birth": "2021-06-09", "age_at_acquisition": ""})
        note = bf.update_sidecar_age(sc, "2022-01-28T08:52:33Z")
        check(note.startswith("filled age_at_acquisition=P"),
              f"blank age filled ({note})")
        fresh = json.load(open(sc, encoding="utf-8"))
        check(fresh["subject"]["age_at_acquisition"] == "P233D",
              "age derived from dob->StudyDate (233 days)")
        # already populated -> untouched
        note = bf.update_sidecar_age(sc, "2025-01-01T00:00:00Z")
        check(note == "skipped: age already populated",
              "populated age never overwritten")
        check(json.load(open(sc, encoding="utf-8"))["subject"]
              ["age_at_acquisition"] == "P233D", "value intact on disk")
        # no dob / no datetime -> explicit skips
        write({"date_of_birth": "", "age_at_acquisition": ""})
        check(bf.update_sidecar_age(sc, "2022-01-01") ==
              "skipped: no date_of_birth", "no dob -> skip")
        write({"date_of_birth": "2021-06-09", "age_at_acquisition": ""})
        check(bf.update_sidecar_age(sc, "") ==
              "skipped: no acquisition datetime", "no datetime -> skip")


README = """============================================================
  Raw Acquisition — ACQ-X
============================================================

Acquisition Date : unknown
Registration Date: 2026-06-13T16:01:38Z

File Count       : 0
Total Size (MB)  : 0.0

Notes:
whatever
"""


def test_refresh_readme():
    print("[README: only the three stale lines are touched]")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "README.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(README)
        note = bf.refresh_readme(tmp, "2022-01-28T08:52:33Z", 9, 3.4)
        check(note == "refreshed 3 line(s)", f"three lines refreshed ({note})")
        text = open(path, encoding="utf-8").read()
        check("Acquisition Date : 2022-01-28\n" in text, "date filled")
        check("File Count       : 9\n" in text, "count updated")
        check("Total Size (MB)  : 3.4\n" in text, "size updated")
        check("Registration Date: 2026-06-13T16:01:38Z" in text,
              "original registration date PRESERVED")
        # A real (non-'unknown') acquisition date is never overwritten.
        note = bf.refresh_readme(tmp, "2099-01-01T00:00:00Z", 10, 5.0)
        text = open(path, encoding="utf-8").read()
        check("Acquisition Date : 2022-01-28\n" in text,
              "real README date not overwritten on re-run")


def test_verify_data_dir():
    print("[verify-after-write catches a corrupted / missing file]")
    with tempfile.TemporaryDirectory() as tmp:
        data = os.path.join(tmp, "ACQ-X.data")
        os.makedirs(data)
        f1 = os.path.join(data, "recon1_frame01.dcm")
        with open(f1, "wb") as f:
            f.write(b"payload-1")
        good = {"ACQ-X.data/recon1_frame01.dcm": checksum.sha256_file(f1)}
        ok, detail = bf.verify_data_dir(tmp, "ACQ-X.data", good, log=quiet_log)
        check(ok, f"clean dir verifies ({detail})")
        with open(f1, "wb") as f:
            f.write(b"corrupted!")
        ok, detail = bf.verify_data_dir(tmp, "ACQ-X.data", good, log=quiet_log)
        check(not ok and "mismatch" in detail, "corruption detected")
        os.remove(f1)
        ok, detail = bf.verify_data_dir(tmp, "ACQ-X.data", good, log=quiet_log)
        check(not ok and "missing" in detail, "missing file detected")
        ok, detail = bf.verify_data_dir(tmp, "ACQ-X.data", {}, log=quiet_log)
        check(not ok, "empty checksum set refuses to 'verify'")


# ------------------------------------------------- fixture for process_row

def make_fixture(tmp, acq_id="ACQ-20220128-MRI-001",
                 original_name="20220128_083412_study_1_1/17",
                 pv="7.0.0", status="pending", nonimage_marker="",
                 data_files=(), staged=True, with_2dseq=True,
                 method_marker=None):
    """Build a minimal NAS + staging + worklist + registry around one row."""
    nas = os.path.join(tmp, "nas")
    staging = os.path.join(tmp, "staging")
    registries = os.path.join(nas, "registries")
    canonical = f"/raw/DICOM/2022/2022-01/{acq_id}/"
    acq_dir = os.path.join(nas, canonical.strip("/").replace("/", os.sep))
    data_dir = os.path.join(acq_dir, f"{acq_id}.data")
    os.makedirs(data_dir)
    os.makedirs(registries)
    for name in data_files:
        with open(os.path.join(data_dir, name), "wb") as f:
            f.write(b"dcm-bytes-" + name.encode())
    with open(os.path.join(acq_dir, "metadata.json"), "w",
              encoding="utf-8") as f:
        json.dump({"acq_id": acq_id,
                   "subject": {"date_of_birth": "2021-06-09",
                               "age_at_acquisition": ""}}, f)
    with open(os.path.join(acq_dir, "README.txt"), "w",
              encoding="utf-8") as f:
        f.write(README)
    checksum.write_checksums({}, os.path.join(acq_dir, "checksums.json"))

    registry.append_row(os.path.join(registries, "registry_raw.csv"), {
        "acq_id": acq_id, "instrument": "MRI", "file_count": "0",
        "file_size_mb": "0.0", "checksum_present": "N",
        "acquisition_datetime": "", "canonical_path": canonical,
        "original_name": original_name,
    })
    row = {"acq_id": acq_id, "original_name": original_name,
           "reconstructions": "all", "canonical_path": canonical,
           "paravision_version": pv, "ingest_config": "cfg.yaml",
           "nonimage_marker": nonimage_marker, "status": status}
    pending_dicom._write_all(
        pending_dicom.pending_dicom_path(registries),
        [dict(row, queued_datetime="2026-07-15T19:09:23+02:00")])

    if staged:
        study, _, exam = original_name.partition("/")
        exam_dir = os.path.join(staging, f"PV{pv}", study, exam)
        os.makedirs(os.path.join(exam_dir, "pdata", "1"))
        if with_2dseq:
            open(os.path.join(exam_dir, "pdata", "1", "2dseq"), "w").close()
        if method_marker:
            with open(os.path.join(exam_dir, "method"), "w") as f:
                f.write(f"##$Method=<Bruker:{method_marker}>\n##END=\n")

    ctx = {"nas_root": nas, "registries_dir": registries, "staging": staging,
           "apply": False, "limit": 0, "acq_ids": [], "mark_no_source": False}
    return row, ctx, acq_dir


def _wl_status(ctx, acq_id):
    rows = pending_dicom.read_pending_dicom(
        pending_dicom.pending_dicom_path(ctx["registries_dir"]))
    return next(r["status"] for r in rows if r["acq_id"] == acq_id)


def test_process_row_dry_run_decisions():
    print("[process_row: the dry-run decision table]")
    # regenerable source -> would-regenerate
    with tempfile.TemporaryDirectory() as tmp:
        row, ctx, _ = make_fixture(tmp)
        r = bf.process_row(row, ctx)
        check(r["outcome"] == "would-regenerate",
              f"ready source -> would-regenerate ({r['detail']})")
    # not pending -> skipped
    with tempfile.TemporaryDirectory() as tmp:
        row, ctx, _ = make_fixture(tmp, status="regenerated")
        check(bf.process_row(row, ctx)["outcome"] == "skipped-status",
              "regenerated row skipped (idempotent)")
    # pending + nonimage_marker -> anomaly, untouched
    with tempfile.TemporaryDirectory() as tmp:
        row, ctx, _ = make_fixture(tmp, nonimage_marker="STEAM")
        check(bf.process_row(row, ctx)["outcome"] == "anomaly",
              "pending row with a marker flagged as anomaly")
    # populated .data/ -> would-reconcile, NOT would-regenerate
    with tempfile.TemporaryDirectory() as tmp:
        row, ctx, _ = make_fixture(tmp, data_files=("recon1_frame01.dcm",))
        r = bf.process_row(row, ctx)
        check(r["outcome"] == "would-reconcile",
              "populated placeholder -> reconcile path (never re-regen)")
    # populated with NON-dcm junk -> error (inspect by hand)
    with tempfile.TemporaryDirectory() as tmp:
        row, ctx, _ = make_fixture(tmp, data_files=("junk.txt",))
        check(bf.process_row(row, ctx)["outcome"] == "error",
              "non-DICOM content -> error, hands off")
    # staged source absent -> source-missing, stays pending
    with tempfile.TemporaryDirectory() as tmp:
        row, ctx, _ = make_fixture(tmp, staged=False)
        r = bf.process_row(row, ctx)
        check(r["outcome"] == "source-missing", "absent staging reported")
        check(_wl_status(ctx, row["acq_id"]) == "pending", "row left pending")
    # no 2dseq, no flag -> no-source-unmarked (report only)
    with tempfile.TemporaryDirectory() as tmp:
        row, ctx, _ = make_fixture(tmp, with_2dseq=False)
        r = bf.process_row(row, ctx)
        check(r["outcome"] == "no-source-unmarked" and
              "header-only" in r["detail"],
              "no 2dseq without --mark-no-source -> report only")
        check(_wl_status(ctx, row["acq_id"]) == "pending",
              "not auto-marked (human-gated)")
    # no 2dseq + flag, dry-run -> would-mark-no-source
    with tempfile.TemporaryDirectory() as tmp:
        row, ctx, _ = make_fixture(tmp, with_2dseq=False)
        ctx["mark_no_source"] = True
        check(bf.process_row(row, ctx)["outcome"] == "would-mark-no-source",
              "dry-run --mark-no-source only previews")
        check(_wl_status(ctx, row["acq_id"]) == "pending",
              "dry-run wrote nothing")
    # spectroscopy staged source, dry-run -> would-correct
    with tempfile.TemporaryDirectory() as tmp:
        row, ctx, _ = make_fixture(tmp, method_marker="STEAM")
        check(bf.process_row(row, ctx)["outcome"]
              == "would-correct-not-applicable",
              "non-image staged source detected in dry-run")
    # --mark-no-source is a DEDICATED pass: regenerable rows are not attempted
    with tempfile.TemporaryDirectory() as tmp:
        row, ctx, _ = make_fixture(tmp)  # has 2dseq
        ctx.update(apply=True, mark_no_source=True)
        r = bf.process_row(row, ctx)
        check(r["outcome"] == "skipped-regenerable",
              "--mark-no-source never attempts regeneration")
        check(_wl_status(ctx, row["acq_id"]) == "pending",
              "regenerable row untouched by the no-source pass")


def test_process_row_apply_transitions():
    print("[process_row --apply: worklist transitions that need no Dicomifier]")
    # mark-no-source flips the row
    with tempfile.TemporaryDirectory() as tmp:
        row, ctx, _ = make_fixture(tmp, with_2dseq=False)
        ctx.update(apply=True, mark_no_source=True)
        r = bf.process_row(row, ctx)
        check(r["outcome"] == "marked-no-source", "apply marks no-source")
        check(_wl_status(ctx, row["acq_id"]) == "no-source",
              "worklist row -> no-source")
    # non-image correction flips to not-applicable + records the marker
    with tempfile.TemporaryDirectory() as tmp:
        row, ctx, _ = make_fixture(tmp, method_marker="PRESS")
        ctx.update(apply=True)
        r = bf.process_row(row, ctx)
        check(r["outcome"] == "corrected-not-applicable",
              "apply corrects a mis-filed spectroscopy row")
        rows = pending_dicom.read_pending_dicom(
            pending_dicom.pending_dicom_path(ctx["registries_dir"]))
        me = rows[0]
        check(me["status"] == "not-applicable" and
              me["nonimage_marker"] == "PRESS",
              "status + nonimage_marker recorded")


def test_process_row_apply_reconcile_end_to_end():
    print("[--apply reconcile: verify -> checksums -> registry -> worklist]")
    with tempfile.TemporaryDirectory() as tmp:
        row, ctx, acq_dir = make_fixture(
            tmp, data_files=("recon1_frame01.dcm", "recon1_frame02.dcm"))
        ctx.update(apply=True)
        r = bf.process_row(row, ctx)
        check(r["outcome"] == "reconciled", f"reconciled ({r['detail']})")
        # checksums.json now covers the two files
        cj = json.load(open(os.path.join(acq_dir, "checksums.json")))
        check(len(cj["files"]) == 2, "checksums.json rebuilt from disk")
        # registry row updated in place, same acq_id, still exactly one row
        reg = registry.read_registry(
            os.path.join(ctx["registries_dir"], "registry_raw.csv"))
        check(len(reg) == 1, "STILL exactly one registry row (no duplicate)")
        check(reg[0]["acq_id"] == row["acq_id"], "ACQ-ID unchanged")
        check(reg[0]["file_count"] == "2" and
              reg[0]["checksum_present"] == "Y",
              "file_count/checksum_present updated")
        check(_wl_status(ctx, row["acq_id"]) == "regenerated",
              "worklist row -> regenerated")
        # idempotent: a second run skips it
        rows2 = pending_dicom.read_pending_dicom(
            pending_dicom.pending_dicom_path(ctx["registries_dir"]))
        r2 = bf.process_row(rows2[0], ctx)
        check(r2["outcome"] == "skipped-status", "second run is a no-op")


def main():
    test_parse_reconstructions()
    test_datetime_from_dicom_tags()
    test_staged_path_and_source_checks()
    test_update_sidecar_age()
    test_refresh_readme()
    test_verify_data_dir()
    test_process_row_dry_run_decisions()
    test_process_row_apply_transitions()
    test_process_row_apply_reconcile_end_to_end()
    print()
    if FAILS:
        print(f"FAILED ({len(FAILS)}):")
        for m in FAILS:
            print(f"  - {m}")
        return 1
    print("ALL PASS (backfill_dicom_regen)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
