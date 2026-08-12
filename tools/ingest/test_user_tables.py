#!/usr/bin/env python3
"""test_user_tables.py — operator-supplied table attachment (08_METADATA §4.8).

Covers the join hazards that make `user_metadata:` blocks fail SILENTLY, which
is the dangerous failure mode here: a case that doesn't match simply has no
block, and nobody notices until the data is already in /raw/.

  1. decimal2 — Excel stores an ID like `1.10` as the NUMBER 1.1. Without the
     transform the case folder `LEONE_1.10` never matches its row. This bit the
     real LIONS sheet: 3 of 42 cases (1.10 / 2.10 / 2.20) were affected.
  2. first_token / strip_prefix — the folder carries an accession suffix or a
     cohort prefix the table's key column does not.
  3. A missing row is non-blocking by default (WARN + omit) but blocks when the
     table declares `on_missing: error`.
  4. The key column in the emitted record is the NORMALIZED key, with the raw
     Excel cell preserved in _source.matched_on.raw_value.
  5. Validation rejects a malformed block before any data is copied.

Run:  PYTHONPATH=tools python tools/ingest/test_user_tables.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingest import user_tables  # noqa: E402

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok:   {msg}")


def _sheet(tmpdir, name, rows, sheet_title="Sheet1"):
    """Write `rows` (list of lists) to a real .xlsx and return its path."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_title
    for row in rows:
        ws.append(row)
    path = os.path.join(tmpdir, name)
    wb.save(path)
    wb.close()
    return path


def test_decimal2_join():
    print("test_decimal2_join")
    with tempfile.TemporaryDirectory() as td:
        # Numbers, exactly as Excel stores 1.01 / 1.10 / 1.20.
        path = _sheet(td, "t.xlsx", [
            ["ID", "centre"],
            [1.01, "H12O"],
            [1.10, "H12O"],
            [1.20, "HCLN"],
        ])
        block = [{
            "label": "t", "file": path, "sheet": "Sheet1", "header_row": 1,
            "key_column": "ID", "key_transform": "decimal2",
            "match": "${discovered.folder_name}",
            "match_transform": "strip_prefix:LEONE_",
            "on_missing": "error",
        }]
        check(user_tables.validate_user_metadata_block(block) == [],
              "block validates")

        out = user_tables.build_user_metadata(block, {"folder_name": "LEONE_1.10"})
        check(out is not None and "t" in out, "1.10 matched despite float storage")
        rec = out["t"]
        check(rec["centre"] == "H12O", f"correct row joined (got {rec.get('centre')})")
        check(rec["ID"] == "1.10",
              f"key column normalized to '1.10' (got {rec.get('ID')!r})")
        check(rec["_source"]["matched_on"]["raw_value"] == 1.1,
              "raw Excel cell preserved in _source.matched_on.raw_value")

        # The regression this guards: WITHOUT the transform, 1.10 must not match.
        no_tf = [dict(block[0], key_transform=None, on_missing="warn")]
        out2 = user_tables.build_user_metadata(no_tf, {"folder_name": "LEONE_1.10"})
        check(out2 is None, "without decimal2 the float key does NOT match (the bug)")


def test_first_token_and_missing():
    print("test_first_token_and_missing")
    with tempfile.TemporaryDirectory() as td:
        path = _sheet(td, "h.xlsx", [
            ["AcquisitionID", "centre"],
            ["HPIC37", "H12O"],
            ["HPIC38", "H12O"],
        ])
        base = {
            "label": "h", "file": path, "sheet": "Sheet1", "header_row": 1,
            "key_column": "AcquisitionID", "match": "${discovered.folder_name}",
            "match_transform": "first_token",
        }
        out = user_tables.build_user_metadata([base], {"folder_name": "HPIC37 S63090"})
        check(out and out["h"]["centre"] == "H12O",
              "folder 'HPIC37 S63090' joins row 'HPIC37' via first_token")

        # Missing row: warn (default) omits the block, error raises.
        warned = []
        out = user_tables.build_user_metadata(
            [dict(base, on_missing="warn")], {"folder_name": "HPIC99"},
            log=lambda m, lvl="INFO": warned.append((lvl, m)))
        check(out is None, "unmatched case yields no block under on_missing: warn")
        check(any(lvl == "WARN" for lvl, _ in warned), "and emits a WARN")

        try:
            user_tables.build_user_metadata(
                [dict(base, on_missing="error")], {"folder_name": "HPIC99"})
            check(False, "on_missing: error should raise")
        except user_tables.UserTableError:
            check(True, "on_missing: error raises UserTableError")


def test_vertical_and_skip():
    print("test_vertical_and_skip")
    with tempfile.TemporaryDirectory() as td:
        path = _sheet(td, "v.xlsx", [
            ["Field", "Description", "Value"],
            ["ProjectID", "the grant code", "PI17/01569"],
            ["SPOC/owner", "who owns it", "Juan Delgado"],
        ])
        block = [{
            "label": "source_project", "file": path, "sheet": "Sheet1",
            "orientation": "vertical", "header_row": 1,
            "field_column": 1, "value_column": 3, "description_column": 2,
        }]
        check(user_tables.validate_user_metadata_block(block) == [], "vertical validates")
        out = user_tables.build_user_metadata(block, {})
        rec = out["source_project"]
        check(rec["ProjectID"] == "PI17/01569", "vertical Field/Value read")
        check(rec["SPOC/owner"] == "Juan Delgado", "second vertical row read")
        check(rec["_source"]["field_descriptions"]["ProjectID"] == "the grant code",
              "description_column captured")
        # Same block for every case: no match expression involved.
        out2 = user_tables.build_user_metadata(block, {"folder_name": "anything"})
        check(out2["source_project"]["ProjectID"] == "PI17/01569",
              "vertical block is batch-constant")


def test_skip_columns_and_validation():
    print("test_skip_columns_and_validation")
    with tempfile.TemporaryDirectory() as td:
        path = _sheet(td, "s.xlsx", [
            ["ID", "keep", "drop"],
            ["a", "yes", "no"],
        ])
        block = [{
            "label": "s", "file": path, "sheet": "Sheet1", "header_row": 1,
            "key_column": "ID", "match": "a", "skip_columns": ["drop"],
        }]
        out = user_tables.build_user_metadata(block, {})
        check("keep" in out["s"] and "drop" not in out["s"], "skip_columns drops a column")

        bad = [
            ({"file": path}, "missing label"),
            ({"label": "x", "file": os.path.join(td, "nope.xlsx")}, "missing file"),
            ({"label": "_x", "file": path, "key_column": "ID", "match": "a"},
             "underscore label"),
            ({"label": "x", "file": path, "match": "a"}, "row table without key_column"),
            ({"label": "x", "file": path, "key_column": "ID", "match": "a",
              "key_transform": "bogus"}, "unknown transform"),
            ({"label": "x", "file": path, "key_column": "ID", "match": "a",
              "on_missing": "explode"}, "bad on_missing"),
        ]
        for entry, why in bad:
            errs = user_tables.validate_user_metadata_block([entry])
            check(errs != [], f"validation rejects: {why}")

        dupe = [{"label": "d", "file": path, "key_column": "ID", "match": "a"},
                {"label": "d", "file": path, "key_column": "ID", "match": "a"}]
        check(user_tables.validate_user_metadata_block(dupe) != [],
              "validation rejects duplicate labels")


def test_absent_block_is_noop():
    print("test_absent_block_is_noop")
    check(user_tables.build_user_metadata(None, {}) is None,
          "no user_metadata: -> None (sidecar shape unchanged)")
    check(user_tables.build_user_metadata([], {}) is None,
          "empty user_metadata: -> None")
    check(user_tables.validate_user_metadata_block(None) == [],
          "absent block validates clean")


def main():
    test_decimal2_join()
    test_first_token_and_missing()
    test_vertical_and_skip()
    test_skip_columns_and_validation()
    test_absent_block_is_noop()
    print()
    if FAILS:
        print(f"FAILED ({len(FAILS)}):")
        for m in FAILS:
            print(f"  - {m}")
        return 1
    print("ALL PASS (user_tables join / validation / non-blocking)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
