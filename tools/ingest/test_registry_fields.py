#!/usr/bin/env python3
"""test_registry_fields.py — registry schema + subject_ids wiring (S1, 2026-06-11).

Checks the subject_ids column is positioned, populated by build_row, and
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
    # The three enrichment-projection columns sit together between sample_type
    # and session_id (designer's restart schema; consolidated with S1).
    fields = registry.REGISTRY_FIELDS
    i = fields.index("subject_ids")
    check(fields[i - 1] == "sample_organism", "subject_ids follows sample_organism")
    check(fields[i + 1] == "anatomical_entity", "subject_ids precedes anatomical_entity")
    st = fields.index("sample_type")
    se = fields.index("session_id")
    check(st < fields.index("sample_organism") < i < fields.index("anatomical_entity") < se,
          "sample_organism / subject_ids / anatomical_entity sit between sample_type and session_id")


def test_build_row():
    print("[build_row projects subject/anatomy -> 3 columns]")
    summary = {"file_count": 1, "total_size_mb": 1.0}
    cfg = {"instrument": "MRI", "data_ecosystem": "DICOM", "sample_type": "organism"}
    # build_row projects straight from the enrichment blocks (subject=/anatomy=).
    row = registry.build_row(
        "ACQ-20260101-MRI-001", cfg, summary, "/raw/x/", "2026-06-12T00:00:00Z",
        subject={"facility_animal_id": "13-AE-biomaGUNE-0423", "species": "Mus musculus"},
        anatomy={"region": {"label": "heart"}},
    )
    check(row["subject_ids"] == "13-AE-biomaGUNE-0423", "subject_ids <- subject.facility_animal_id")
    check(row["sample_organism"] == "Mus musculus", "sample_organism <- subject.species")
    check(row["anatomical_entity"] == "heart", "anatomical_entity <- anatomy.region.label")
    # Non-animal: subject=None / anatomy=None -> all three blank, no KeyError.
    row2 = registry.build_row("ACQ-20260101-CELL-001", {"sample_type": "cells"}, summary, "/raw/y/", "z")
    check(row2["subject_ids"] == "" and row2["sample_organism"] == "" and row2["anatomical_entity"] == "",
          "all three blank for a non-animal sample (no subject/anatomy)")
    check(set(row.keys()) == set(registry.REGISTRY_FIELDS), "row has exactly REGISTRY_FIELDS keys")


def test_auto_classification():
    print("[auto-populated, not operator-set]")
    for col in ("subject_ids", "sample_organism", "anatomical_entity"):
        check(col in resolver.AUTO_COLUMNS, f"{col} is in AUTO_COLUMNS")
        check(col not in resolver.USER_CONTROLLABLE_COLUMNS, f"{col} is NOT user-controllable")
    # A registry: block that sets subject_ids must be rejected.
    errs = resolver.validate_registry_block({
        "instrument": "MRI", "data_ecosystem": "DICOM", "researcher": "RT",
        "data_source": "internal", "subject_ids": "x",
    })
    check(any("subject_ids" in e for e in errs),
          "validate_registry_block rejects an operator-set subject_ids")


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
    print("ALL PASS (registry subject_ids wiring)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
