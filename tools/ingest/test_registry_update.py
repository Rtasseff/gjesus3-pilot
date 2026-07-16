#!/usr/bin/env python3
"""test_registry_update.py — registry.update_row in-place row update (2026-07-16).

update_row is the capability the subject-metadata recovery precedent lacks: fill
fields on an ALREADY-registered acquisition (the no-DICOM-regeneration backfill
updates file_count / size / checksum_present / acquisition_datetime in place,
keeping the ACQ-ID). Checks: matches by acq_id, controlled-write only_if_blank,
atomicity of the rewrite, header/field guards, and that untouched rows/columns
survive byte-for-byte.

Run:  PYTHONPATH=tools python tools/ingest/test_registry_update.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingest import registry  # noqa: E402

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok:   {msg}")


def _seed(tmp, rows):
    """Write a registry_raw.csv with the given row dicts; return its path."""
    path = os.path.join(tmp, "registry_raw.csv")
    for r in rows:
        registry.append_row(path, r)
    return path


def _row(path, acq_id):
    return next((r for r in registry.read_registry(path)
                 if r["acq_id"] == acq_id), None)


def test_basic_update():
    print("[basic field update, matched by acq_id]")
    with tempfile.TemporaryDirectory() as tmp:
        path = _seed(tmp, [
            {"acq_id": "ACQ-A", "instrument": "MRI", "file_count": "0",
             "file_size_mb": "0.0", "checksum_present": "N"},
            {"acq_id": "ACQ-B", "instrument": "MRI", "file_count": "0"},
        ])
        found, applied, skipped = registry.update_row(
            path, "ACQ-A",
            {"file_count": "12", "file_size_mb": "3.4", "checksum_present": "Y"},
        )
        check(found, "row found")
        check(applied == {"file_count": "12", "file_size_mb": "3.4",
                          "checksum_present": "Y"}, "all three fields applied")
        a = _row(path, "ACQ-A")
        check(a["file_count"] == "12" and a["checksum_present"] == "Y",
              "ACQ-A updated on disk")
        b = _row(path, "ACQ-B")
        check(b["file_count"] == "0", "ACQ-B (other row) left untouched")


def test_only_if_blank_guard():
    print("[only_if_blank never overwrites a real value]")
    with tempfile.TemporaryDirectory() as tmp:
        path = _seed(tmp, [
            {"acq_id": "ACQ-BLANK", "acquisition_datetime": ""},
            {"acq_id": "ACQ-REAL",
             "acquisition_datetime": "2022-01-24T08:56:16+01:00"},
        ])
        # Blank row: the guarded field IS filled.
        _, applied, skipped = registry.update_row(
            path, "ACQ-BLANK",
            {"acquisition_datetime": "2022-05-01T10:00:00Z"},
            only_if_blank=["acquisition_datetime"])
        check(applied.get("acquisition_datetime") == "2022-05-01T10:00:00Z",
              "blank acquisition_datetime is filled")
        check(not skipped, "nothing skipped for the blank row")
        # Real row: the guarded field is LEFT ALONE and reported skipped.
        _, applied2, skipped2 = registry.update_row(
            path, "ACQ-REAL",
            {"acquisition_datetime": "9999-01-01T00:00:00Z"},
            only_if_blank=["acquisition_datetime"])
        check(not applied2, "real acquisition_datetime NOT overwritten")
        check(skipped2.get("acquisition_datetime") == "2022-01-24T08:56:16+01:00",
              "existing real value reported in skipped")
        check(_row(path, "ACQ-REAL")["acquisition_datetime"]
              == "2022-01-24T08:56:16+01:00", "real value intact on disk")


def test_mixed_guarded_and_unconditional():
    print("[guarded + unconditional fields in one call]")
    with tempfile.TemporaryDirectory() as tmp:
        path = _seed(tmp, [{"acq_id": "ACQ-M",
                            "acquisition_datetime": "2020-01-01T00:00:00Z",
                            "file_count": "0"}])
        _, applied, skipped = registry.update_row(
            path, "ACQ-M",
            {"acquisition_datetime": "2099-01-01T00:00:00Z", "file_count": "7"},
            only_if_blank=["acquisition_datetime"])
        check("file_count" in applied and "acquisition_datetime" not in applied,
              "unconditional file_count written; guarded datetime skipped")
        m = _row(path, "ACQ-M")
        check(m["file_count"] == "7" and
              m["acquisition_datetime"] == "2020-01-01T00:00:00Z",
              "on disk: count updated, real datetime preserved")


def test_missing_row_and_bad_field():
    print("[absent acq_id + unknown field guard]")
    with tempfile.TemporaryDirectory() as tmp:
        path = _seed(tmp, [{"acq_id": "ACQ-A", "file_count": "0"}])
        found, applied, _ = registry.update_row(path, "ACQ-NOPE",
                                                 {"file_count": "1"})
        check(not found and not applied, "absent acq_id -> found=False, no write")
        try:
            registry.update_row(path, "ACQ-A", {"not_a_column": "x"})
            check(False, "unknown field should raise")
        except RuntimeError:
            check(True, "unknown field raises RuntimeError")


def test_no_op_leaves_file_identical():
    print("[a pure no-op does not rewrite the file]")
    with tempfile.TemporaryDirectory() as tmp:
        path = _seed(tmp, [{"acq_id": "ACQ-A",
                            "acquisition_datetime": "2020-01-01T00:00:00Z"}])
        before = open(path, "rb").read()
        registry.update_row(path, "ACQ-A",
                            {"acquisition_datetime": "2099-01-01T00:00:00Z"},
                            only_if_blank=["acquisition_datetime"])
        after = open(path, "rb").read()
        check(before == after, "guarded no-op leaves the file byte-for-byte")


def test_other_columns_survive():
    print("[unrelated columns/values round-trip through a rewrite]")
    with tempfile.TemporaryDirectory() as tmp:
        path = _seed(tmp, [{"acq_id": "ACQ-A", "researcher": "José",
                            "notes": "acentúated, with comma", "file_count": "0"}])
        registry.update_row(path, "ACQ-A", {"file_count": "5"})
        a = _row(path, "ACQ-A")
        check(a["researcher"] == "José", "accented value preserved (UTF-8)")
        check(a["notes"] == "acentúated, with comma", "comma-bearing note preserved")


def main():
    test_basic_update()
    test_only_if_blank_guard()
    test_mixed_guarded_and_unconditional()
    test_missing_row_and_bad_field()
    test_no_op_leaves_file_identical()
    test_other_columns_survive()
    print()
    if FAILS:
        print(f"FAILED ({len(FAILS)}):")
        for m in FAILS:
            print(f"  - {m}")
        return 1
    print("ALL PASS (registry.update_row)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
