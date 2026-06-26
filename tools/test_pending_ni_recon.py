"""Unit tests for tools/ingest/pending_ni_recon.py — the NI placeholder fill worklist.

No NAS, no network. Run: python tools/test_pending_ni_recon.py
"""
import csv
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from ingest import pending_ni_recon as pn

_fail = 0


def check(cond, msg):
    global _fail
    print(("  ok:   " if cond else "  FAIL: ") + msg)
    if not cond:
        _fail += 1


def rows_of(d):
    return pn.read_pending_ni_recon(pn.pending_ni_recon_path(d))


with tempfile.TemporaryDirectory() as d:
    # 1. first append creates the file with one pending row
    pn.append_pending_ni_recon(
        d, acq_id="ACQ-20260212-CT-001",
        original_name="260212/0324/0324_m61/20260212130722_CT/recon_0",
        recon_index="0", canonical_path="/raw/DICOM/2026/2026-02/ACQ-20260212-CT-001/ACQ-20260212-CT-001.data",
        session_id="0324_260212_0324_m61", ingest_config="tools/configs/x.yaml")
    rows = rows_of(d)
    check(len(rows) == 1, "first append -> 1 row")
    r = rows[0]
    check(r["acq_id"] == "ACQ-20260212-CT-001", "acq_id recorded")
    check(r["recon_index"] == "0", "recon_index recorded")
    check(r["original_name"].endswith("/recon_0"), "original_name = <anchor>/recon_<idx> (box identity)")
    check(r["session_id"] == "0324_260212_0324_m61", "session_id recorded")
    check(r["status"] == "pending", "new row status = pending")
    check(list(r.keys()) == pn.PENDING_NI_RECON_FIELDS, "header = PENDING_NI_RECON_FIELDS")

    # 2. a second recon of the same anchor = a distinct acquisition = a second row
    pn.append_pending_ni_recon(
        d, acq_id="ACQ-20260212-CT-002",
        original_name="260212/0324/0324_m61/20260212130722_CT/recon_1",
        recon_index="1", canonical_path="/raw/.../ACQ-20260212-CT-002.data")
    check(len(rows_of(d)) == 2, "second recon -> 2 rows")

    # 3. re-ingest of the SAME acq is idempotent (refresh, no duplicate)
    pn.append_pending_ni_recon(
        d, acq_id="ACQ-20260212-CT-001", original_name="NEW/recon_0",
        recon_index="0", canonical_path="/raw/.../new")
    rows = rows_of(d)
    check(len(rows) == 2, "re-append same acq -> still 2 rows (idempotent)")
    r1 = [x for x in rows if x["acq_id"] == "ACQ-20260212-CT-001"][0]
    check(r1["original_name"] == "NEW/recon_0", "re-append refreshes fields")

    # 4. mark_filled flips status; a later re-append preserves it (no reset to pending)
    check(pn.mark_filled(d, "ACQ-20260212-CT-001") is True, "mark_filled returns True for a known acq")
    r1 = [x for x in rows_of(d) if x["acq_id"] == "ACQ-20260212-CT-001"][0]
    check(r1["status"] == "filled", "mark_filled sets status=filled")
    pn.append_pending_ni_recon(
        d, acq_id="ACQ-20260212-CT-001", original_name="AGAIN/recon_0",
        recon_index="0", canonical_path="/raw/.../again")
    r1 = [x for x in rows_of(d) if x["acq_id"] == "ACQ-20260212-CT-001"][0]
    check(r1["status"] == "filled", "re-append PRESERVES a 'filled' status (no reset)")
    check(pn.mark_filled(d, "ACQ-nope") is False, "mark_filled returns False for unknown acq")

    # 5. read on a missing file -> []
    check(pn.read_pending_ni_recon(os.path.join(d, "nope.csv")) == [], "missing file -> []")

    # 6. header mismatch is caught
    bad = os.path.join(d, "bad.csv")
    with open(bad, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow(["acq_id", "wrong"])
    try:
        pn._assert_header(bad)
        check(False, "wrong header should raise")
    except RuntimeError:
        check(True, "wrong header raises RuntimeError")

print("\nALL PENDING-NI-RECON CHECKS PASSED" if _fail == 0 else f"\n{_fail} CHECK(S) FAILED")
sys.exit(1 if _fail else 0)
