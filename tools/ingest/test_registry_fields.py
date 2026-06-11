#!/usr/bin/env python3
"""test_registry_fields.py — registry schema + subject_id wiring (S1, 2026-06-11).

Checks the subject_id column is positioned, populated by build_row, and
correctly classified as auto-populated (never operator-set in a registry: block).

Run:  PYTHONPATH=tools python tools/ingest/test_registry_fields.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingest import registry, resolver  # noqa: E402

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok:   {msg}")


def test_position():
    print("[schema position]")
    i = registry.REGISTRY_FIELDS.index("subject_id")
    check(registry.REGISTRY_FIELDS[i - 1] == "sample_type",
          "subject_id immediately follows sample_type")
    check(registry.REGISTRY_FIELDS[i + 1] == "session_id",
          "subject_id immediately precedes session_id")


def test_build_row():
    print("[build_row populates subject_id]")
    cfg = {
        "instrument": "MRI", "data_ecosystem": "DICOM",
        "sample_type": "organism",
        "subject_id": "13-AE-biomaGUNE-0423",
    }
    summary = {"file_count": 1, "total_size_mb": 1.0}
    row = registry.build_row("ACQ-20260101-MRI-001", cfg, summary, "/raw/x/", "2026-06-11T00:00:00Z")
    check(row["subject_id"] == "13-AE-biomaGUNE-0423", "subject_id flows cfg -> row")
    # Non-animal / missing -> empty string, never KeyError.
    row2 = registry.build_row("ACQ-20260101-CELL-001", {"sample_type": "cells"}, summary, "/raw/y/", "z")
    check(row2["subject_id"] == "", "subject_id empty when cfg has none (non-animal)")
    # Every REGISTRY_FIELD present in the row (full-width).
    check(set(row.keys()) == set(registry.REGISTRY_FIELDS), "row has exactly REGISTRY_FIELDS keys")


def test_auto_classification():
    print("[auto-populated, not operator-set]")
    check("subject_id" in resolver.AUTO_COLUMNS, "subject_id is in AUTO_COLUMNS")
    check("subject_id" not in resolver.USER_CONTROLLABLE_COLUMNS,
          "subject_id is NOT user-controllable")
    # A registry: block that sets subject_id must be rejected.
    errs = resolver.validate_registry_block({
        "instrument": "MRI", "data_ecosystem": "DICOM", "researcher": "RT",
        "data_source": "internal", "subject_id": "x",
    })
    check(any("subject_id" in e for e in errs),
          "validate_registry_block rejects an operator-set subject_id")


def main():
    test_position()
    test_build_row()
    test_auto_classification()
    print()
    if FAILS:
        print(f"FAILED ({len(FAILS)}):")
        for m in FAILS:
            print(f"  - {m}")
        return 1
    print("ALL PASS (registry subject_id wiring)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
