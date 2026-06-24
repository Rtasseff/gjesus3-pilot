"""Unit tests for tools/ingest/pending_dicom.py — the no-DICOM regen worklist.

No NAS, no network. Run: python tools/test_pending_dicom.py
"""
import csv
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from ingest import pending_dicom as pd

_fail = 0


def check(cond, msg):
    global _fail
    print(("  ok:   " if cond else "  FAIL: ") + msg)
    if not cond:
        _fail += 1


def rows_of(d):
    return pd.read_pending_dicom(pd.pending_dicom_path(d))


with tempfile.TemporaryDirectory() as d:
    # 1. first append creates the file with one pending row
    pd.append_pending_dicom(
        d, acq_id="ACQ-20220112-MRI-001",
        original_name="20220112_153439_jrc220112_m149_0618_1_1/1",
        reconstructions="all", canonical_path="/raw/DICOM/2022/2022-01/ACQ-20220112-MRI-001/",
        paravision_version="6.0.1", ingest_config="tools/configs/x.yaml")
    rows = rows_of(d)
    check(len(rows) == 1, "first append -> 1 row")
    r = rows[0]
    check(r["acq_id"] == "ACQ-20220112-MRI-001", "acq_id recorded")
    check(r["original_name"].endswith("/1"), "original_name = study/exam (kenia identity)")
    check(r["paravision_version"] == "6.0.1", "paravision_version recorded (picks the PV root)")
    check(r["status"] == "pending", "new row status = pending")
    check(list(r.keys()) == pd.PENDING_DICOM_FIELDS, "header = PENDING_DICOM_FIELDS")

    # 2. a second acq appends a second row
    pd.append_pending_dicom(
        d, acq_id="ACQ-20220112-MRI-002", original_name="…/2",
        reconstructions="all", canonical_path="/raw/.../ACQ-20220112-MRI-002/")
    check(len(rows_of(d)) == 2, "second acq -> 2 rows")

    # 3. re-ingest of the SAME acq is idempotent (refresh, no duplicate)
    pd.append_pending_dicom(
        d, acq_id="ACQ-20220112-MRI-001", original_name="NEW/9",
        reconstructions="[3]", canonical_path="/raw/.../ACQ-20220112-MRI-001/")
    rows = rows_of(d)
    check(len(rows) == 2, "re-append same acq -> still 2 rows (idempotent)")
    r1 = [x for x in rows if x["acq_id"] == "ACQ-20220112-MRI-001"][0]
    check(r1["original_name"] == "NEW/9", "re-append refreshes fields")

    # 4. status the data office set is preserved across a re-ingest
    path = pd.pending_dicom_path(d)
    rows = rows_of(d)
    for x in rows:
        if x["acq_id"] == "ACQ-20220112-MRI-001":
            x["status"] = "regenerated"
    pd._write_all(path, rows)
    pd.append_pending_dicom(
        d, acq_id="ACQ-20220112-MRI-001", original_name="AGAIN/1",
        reconstructions="all", canonical_path="/raw/.../ACQ-20220112-MRI-001/")
    r1 = [x for x in rows_of(d) if x["acq_id"] == "ACQ-20220112-MRI-001"][0]
    check(r1["status"] == "regenerated", "re-append PRESERVES a 'regenerated' status (no reset)")

    # 5. read on a missing file -> []
    check(pd.read_pending_dicom(os.path.join(d, "nope.csv")) == [], "missing file -> []")

    # 6. header mismatch is caught
    bad = os.path.join(d, "bad.csv")
    with open(bad, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow(["acq_id", "wrong"])
    try:
        pd._assert_header(bad)
        check(False, "wrong header should raise")
    except RuntimeError:
        check(True, "wrong header raises RuntimeError")

print("\nALL PENDING-DICOM CHECKS PASSED" if _fail == 0 else f"\n{_fail} CHECK(S) FAILED")
sys.exit(1 if _fail else 0)
