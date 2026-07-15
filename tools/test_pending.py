"""Unit tests for tools/ingest/pending.py — the subject-metadata recovery queue.

Covers the 2026-07 integrity fix: the queue write is now atomic (temp+replace,
no truncate-in-place) and append_pending serializes under the registry lock, so
a crash mid-write can't wipe the queue and two concurrent DB-miss ingests can't
lost-update it. Also re-checks the idempotency + header contract.

No NAS, no network. Run: python tools/test_pending.py
"""
import csv
import glob
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from ingest import pending  # noqa: E402

_fail = 0


def check(cond, msg):
    global _fail
    print(("  ok:   " if cond else "  FAIL: ") + msg)
    if not cond:
        _fail += 1


def rows_of(d):
    return pending.read_pending(pending.pending_path(d))


with tempfile.TemporaryDirectory() as d:
    # 1. first append creates the file with one pending row
    pending.append_pending(
        d, acq_id="ACQ-20260101-MRI-001",
        sidecar_path="/raw/DICOM/2026/2026-01/ACQ-20260101-MRI-001/metadata.json",
        facility_animal_id="13-AE-biomaGUNE-0423", reason="db-miss")
    rows = rows_of(d)
    check(len(rows) == 1, "first append -> 1 row")
    r = rows[0]
    check(r["acq_id"] == "ACQ-20260101-MRI-001", "acq_id recorded")
    check(r["status"] == "pending", "new row status = pending")
    check(list(r.keys()) == pending.PENDING_FIELDS, "header = PENDING_FIELDS")

    # 2. a second acq appends a second row
    pending.append_pending(
        d, acq_id="ACQ-20260101-MRI-002", sidecar_path="/raw/.../002/metadata.json",
        facility_animal_id="13-AE-biomaGUNE-0424", reason="no-credentials")
    check(len(rows_of(d)) == 2, "second acq -> 2 rows")

    # 3. re-ingest of the SAME acq is idempotent (refresh, no duplicate)
    pending.append_pending(
        d, acq_id="ACQ-20260101-MRI-001", sidecar_path="/raw/.../NEW/metadata.json",
        facility_animal_id="99-AE-biomaGUNE-0001", reason="db-miss")
    rows = rows_of(d)
    check(len(rows) == 2, "re-append same acq -> still 2 rows (idempotent)")
    r1 = [x for x in rows if x["acq_id"] == "ACQ-20260101-MRI-001"][0]
    check(r1["facility_animal_id"] == "99-AE-biomaGUNE-0001", "re-append refreshes fields")

    # 4. a status/recovered_at a superuser set is preserved across a re-ingest
    path = pending.pending_path(d)
    rows = rows_of(d)
    for x in rows:
        if x["acq_id"] == "ACQ-20260101-MRI-001":
            x["status"] = "recovered"
            x["recovered_at"] = "2026-07-01T00:00:00Z"
    pending._write_all(path, rows)
    pending.append_pending(
        d, acq_id="ACQ-20260101-MRI-001", sidecar_path="/raw/.../AGAIN/metadata.json",
        facility_animal_id="13-AE-biomaGUNE-0423", reason="db-miss")
    r1 = [x for x in rows_of(d) if x["acq_id"] == "ACQ-20260101-MRI-001"][0]
    check(r1["status"] == "recovered", "re-append PRESERVES a 'recovered' status (no reset)")
    check(r1["recovered_at"] == "2026-07-01T00:00:00Z", "re-append PRESERVES recovered_at")

    # 5. atomic write leaves NO stray temp file behind (temp+os.replace)
    stray = glob.glob(os.path.join(d, "*.tmp*"))
    check(stray == [], f"no leftover temp file after writes (found {stray})")

    # 6. _hold_lock=False path still works (used when a caller already holds the
    #    registry lock — must not deadlock by re-acquiring)
    pending.append_pending(
        d, acq_id="ACQ-20260101-MRI-003", sidecar_path="/raw/.../003/metadata.json",
        facility_animal_id="13-AE-biomaGUNE-0425", reason="db-miss", _hold_lock=False)
    check(len(rows_of(d)) == 3, "_hold_lock=False append works (no self-lock, no deadlock)")

    # 7. read on a missing file -> []
    check(pending.read_pending(os.path.join(d, "nope.csv")) == [], "missing file -> []")

    # 8. header mismatch is caught before a write can corrupt column alignment
    bad = os.path.join(d, "bad.csv")
    with open(bad, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow(["acq_id", "wrong"])
    try:
        pending._assert_header(bad)
        check(False, "wrong header should raise")
    except RuntimeError:
        check(True, "wrong header raises RuntimeError")

print("\nALL PENDING CHECKS PASSED" if _fail == 0 else f"\n{_fail} CHECK(S) FAILED")
sys.exit(1 if _fail else 0)
