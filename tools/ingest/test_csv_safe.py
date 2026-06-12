#!/usr/bin/env python3
"""test_csv_safe.py — BOM + trailing-newline safety on registry appends (F-item 9).

Covers the two Excel-introduced CSV hazards that csv_safe guards against, end
to end through registry.append_row:

  1. A UTF-8 BOM on the header must NOT make append_row's defensive header
     check refuse the append.
  2. A missing trailing newline must NOT concatenate the new row onto the
     previous last row.

Run:  PYTHONPATH=tools python tools/ingest/test_csv_safe.py
"""

import csv
import os
import sys
import tempfile

# Allow `python tools/ingest/test_csv_safe.py` (add tools/ to path) as well as
# the documented PYTHONPATH=tools invocation.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingest import registry, csv_safe  # noqa: E402

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok:   {msg}")


def _row(acq_id):
    """A minimal valid row dict (append_row fills the rest with '')."""
    return {"acq_id": acq_id, "instrument": "CELL", "data_ecosystem": "MICROSCOPY"}


def test_bom_tolerated():
    print("[BOM on header]")
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "registry_raw.csv")
        # Write a header WITH a UTF-8 BOM + one existing row, as Excel's
        # "CSV UTF-8" export would.
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(registry.REGISTRY_FIELDS)
            w.writerow([_row("ACQ-20260101-CELL-001").get(c, "") for c in registry.REGISTRY_FIELDS])
        # Sanity: the raw bytes really start with a BOM.
        with open(path, "rb") as f:
            check(f.read(3) == b"\xef\xbb\xbf", "test file actually begins with a UTF-8 BOM")
        # read_header strips it.
        check(csv_safe.read_header(path) == registry.REGISTRY_FIELDS,
              "csv_safe.read_header strips the BOM -> header matches")
        # append_row must NOT raise the header-mismatch RuntimeError.
        try:
            registry.append_row(path, _row("ACQ-20260101-CELL-002"))
            appended = True
        except RuntimeError as e:
            appended = False
            print(f"    (append raised: {e})")
        check(appended, "append_row succeeds despite the BOM (no header-mismatch refusal)")
        rows = registry.read_registry(path)
        check(len(rows) == 2, f"both rows present after append (got {len(rows)})")
        check([r["acq_id"] for r in rows] == ["ACQ-20260101-CELL-001", "ACQ-20260101-CELL-002"],
              "acq_ids read back correctly (first column not mangled by BOM)")


def test_missing_trailing_newline():
    print("[missing trailing newline]")
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "registry_raw.csv")
        # Seed header + one row, then truncate the trailing newline so the file
        # ends mid-line (Excel round-trip / hand edit).
        registry.append_row(path, _row("ACQ-20260101-CELL-001"))
        with open(path, "rb") as f:
            data = f.read()
        check(data.endswith(b"\n") or data.endswith(b"\r\n"), "seeded file ends in a newline")
        stripped = data.rstrip(b"\r\n")
        with open(path, "wb") as f:
            f.write(stripped)
        check(not stripped.endswith(b"\n"), "trailing newline removed for the test")
        # Append: the guard must insert a newline so rows don't merge.
        registry.append_row(path, _row("ACQ-20260101-CELL-002"))
        rows = registry.read_registry(path)
        check(len(rows) == 2, f"row count is 2, not 1 merged row (got {len(rows)})")
        ids = [r.get("acq_id") for r in rows]
        check(ids == ["ACQ-20260101-CELL-001", "ACQ-20260101-CELL-002"],
              f"both acq_ids intact (no concatenation): {ids}")
        # Every line parses to the right column count.
        widths = {len(r) for r in rows}
        check(widths == {len(registry.REGISTRY_FIELDS)},
              f"every row has {len(registry.REGISTRY_FIELDS)} columns (got widths {widths})")


def main():
    test_bom_tolerated()
    test_missing_trailing_newline()
    print()
    if FAILS:
        print(f"FAILED ({len(FAILS)}):")
        for m in FAILS:
            print(f"  - {m}")
        return 1
    print("ALL PASS (csv_safe BOM + trailing-newline)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
