"""Unit tests for tools/ingest/pending_links.py — the deferred project-link worklist.

No NAS, no network. Run: python tools/test_pending_links.py
"""
import csv
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from ingest import pending_links as pl

_fail = 0


def check(cond, msg):
    global _fail
    print(("  ok:   " if cond else "  FAIL: ") + msg)
    if not cond:
        _fail += 1


def rows_of(d):
    return pl.read_pending_links(pl.pending_links_path(d))


with tempfile.TemporaryDirectory() as d:
    # 1. first append creates the file with one pending row
    pl.append_pending_link(
        d, acq_id="ACQ-20260212-CT-001", project_id="PROJ-0006",
        link_name="CT_0324_m61_m62_2h_20260212_20260212130722",
        raw_primary_canonical="/raw/DICOM/2026/2026-02/ACQ-20260212-CT-001/ACQ-20260212-CT-001.data",
        primary_kind="folder", reason="OSError: Operation not supported [Errno 45]",
        host_os="darwin")
    rows = rows_of(d)
    check(len(rows) == 1, "first append -> 1 row")
    r = rows[0]
    check(r["acq_id"] == "ACQ-20260212-CT-001", "acq_id recorded")
    check(r["project_id"] == "PROJ-0006", "project_id recorded")
    check(r["primary_kind"] == "folder", "primary_kind recorded")
    check("Errno 45" in r["reason"], "reason carries the errno")
    check(r["host_os"] == "darwin", "host_os recorded (the Mac)")
    check(r["status"] == "pending", "new row status = pending")
    check(list(r.keys()) == pl.PENDING_LINKS_FIELDS, "header = PENDING_LINKS_FIELDS")

    # 2. a second acq appends a second row
    pl.append_pending_link(
        d, acq_id="ACQ-20260212-PET-001", project_id="PROJ-0006",
        link_name="PET_0324_m59_m60_20260212_20260212100620",
        raw_primary_canonical="/raw/.../ACQ-20260212-PET-001/ACQ-20260212-PET-001.data",
        primary_kind="folder")
    check(len(rows_of(d)) == 2, "second acq -> 2 rows")

    # 3. re-ingest of the SAME acq is idempotent (refresh, no duplicate)
    pl.append_pending_link(
        d, acq_id="ACQ-20260212-CT-001", project_id="PROJ-0006",
        link_name="NEW_NAME", raw_primary_canonical="/raw/.../new",
        primary_kind="folder", reason="refreshed", host_os="darwin")
    rows = rows_of(d)
    check(len(rows) == 2, "re-append same acq -> still 2 rows (idempotent)")
    r1 = [x for x in rows if x["acq_id"] == "ACQ-20260212-CT-001"][0]
    check(r1["link_name"] == "NEW_NAME", "re-append refreshes fields")

    # 4. status the relink pass set is preserved across a re-ingest
    path = pl.pending_links_path(d)
    rows = rows_of(d)
    for x in rows:
        if x["acq_id"] == "ACQ-20260212-CT-001":
            x["status"] = "linked"
    pl._write_all(path, rows)
    pl.append_pending_link(
        d, acq_id="ACQ-20260212-CT-001", project_id="PROJ-0006",
        link_name="AGAIN", raw_primary_canonical="/raw/.../again",
        primary_kind="folder")
    r1 = [x for x in rows_of(d) if x["acq_id"] == "ACQ-20260212-CT-001"][0]
    check(r1["status"] == "linked", "re-append PRESERVES a 'linked' status (no reset)")

    # 5. read on a missing file -> []
    check(pl.read_pending_links(os.path.join(d, "nope.csv")) == [], "missing file -> []")

    # 6. header mismatch is caught
    bad = os.path.join(d, "bad.csv")
    with open(bad, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow(["acq_id", "wrong"])
    try:
        pl._assert_header(bad)
        check(False, "wrong header should raise")
    except RuntimeError:
        check(True, "wrong header raises RuntimeError")

print("\nALL PENDING-LINKS CHECKS PASSED" if _fail == 0 else f"\n{_fail} CHECK(S) FAILED")
sys.exit(1 if _fail else 0)
