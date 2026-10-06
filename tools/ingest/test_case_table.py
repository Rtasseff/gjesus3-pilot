#!/usr/bin/env python3
"""test_case_table.py — the per-case override table (`auto_discover.case_table`).

The table exists so a batch can set project / researcher / operator / subject
PER FILE (the 2026-09-30 historical-drives ingest decided those per file
beforehand). Its failure modes would all be silent, so each is pinned here:

  1. Every column lands in discovered.<column> and resolves through registry:,
     operator: and subject_lookup: exactly as written, including a blank value.
  2. The table wins over a filename-parsed value of the same name.
  3. A file with NO row aborts the batch (on_missing: error, the default) or is
     skipped (on_missing: skip) -- never ingested with the batch-level default.
  4. A row that matches no file is reported.
  5. Keys are matched on original_name with forward slashes, even if the table
     was written with backslashes; a relative `file:` resolves from the
     config's directory; a duplicate key or unknown option is refused.
  6. No case_table block = the old behaviour, untouched.
  7. XMIC is a valid instrument code in the MICROSCOPY ecosystem.

Run:  PYTHONPATH=tools python tools/ingest/test_case_table.py
"""

import contextlib
import csv
import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingest import config  # noqa: E402

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok:   {msg}")


def _tree(td):
    """staging/<drive>/<a>/<b>/x_1.czi and staging/<drive>/c/y_2.czi (dummy bytes)."""
    staging = os.path.join(td, "staging")
    paths = [os.path.join(staging, "drive1_X", "Cell observer", "Ana", "ID5_0522_HE.czi"),
             os.path.join(staging, "drive1_X", "Other", "plain_2.czi")]
    for p in paths:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(b"not a real czi")
    return staging


def _table(path, rows, header=("original_name", "drv_project", "drv_researcher",
                               "drv_operator", "drv_animal", "drv_alias")):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def _cfg(staging, table_block, filename_parse=None):
    disco = {"staging_dir": staging, "pattern": "**/*.czi", "embedded_metadata": False,
             "case_table": table_block,
             "subject_lookup": {"project_alias": "${discovered.drv_alias}",
                                "animal_code": "${discovered.drv_animal}"}}
    if filename_parse:
        disco["filename_parse"] = filename_parse
    return {
        "ingest": {"auto_create_projects": False},
        "auto_discover": disco,
        "registry": {"instrument": "CELL", "data_ecosystem": "MICROSCOPY",
                     "researcher": "discovered.drv_researcher", "data_source": "internal",
                     "project_name": "discovered.drv_project",
                     "acquisition_datetime": "2024-01-02"},
        "operator": "discovered.drv_operator",
    }


def _run(cfg):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        cases = config.expand_batch(cfg, nas_root=None)
    return cases, out.getvalue()


def test_values_per_case():
    print("test_values_per_case")
    with tempfile.TemporaryDirectory() as td:
        staging = _tree(td)
        t = os.path.join(td, "cases.csv")
        _table(t, [
            ["drive1_X/Cell observer/Ana/ID5_0522_HE.czi", "AE-biomaGUNE-0522", "Ana", "AINHIZE", "5", "0522"],
            ["drive1_X\\Other\\plain_2.czi", "", "", "", "", ""],      # backslashes, all blank
        ])
        cases, _ = _run(_cfg(staging, {"file": t}))
        by = {c["original_name"]: c for c in cases}
        a = by.get("drive1_X/Cell observer/Ana/ID5_0522_HE.czi")
        b = by.get("drive1_X/Other/plain_2.czi")
        check(a and b and len(cases) == 2, "both files expand, keyed on forward-slash original_name")
        check(a["project_name"] == "AE-biomaGUNE-0522" and a["researcher"] == "Ana",
              "registry: project_name / researcher resolve per file")
        check(a["operator"] == "AINHIZE", "top-level operator: resolves per file")
        check(a["discovered"]["drv_animal"] == "5" and a["discovered"]["drv_alias"] == "0522",
              "subject_lookup inputs are present in discovered")
        check(b["project_name"] == "" and b["researcher"] == "" and b["operator"] == "",
              "a blank table value resolves to blank (not an error, not a default)")


def test_table_beats_filename():
    print("test_table_beats_filename")
    with tempfile.TemporaryDirectory() as td:
        staging = _tree(td)
        t = os.path.join(td, "cases.csv")
        _table(t, [["drive1_X/Cell observer/Ana/ID5_0522_HE.czi", "P", "R", "O", "5", "0522"],
                   ["drive1_X/Other/plain_2.czi", "P", "R", "O", "", ""]],
               header=("original_name", "drv_project", "drv_researcher", "drv_operator",
                       "drv_animal", "drv_alias"))
        # filename_parse would set drv_researcher from the first chunk
        fp = {"regex": r"^(?P<drv_researcher>[^_]+)_"}
        cases, _ = _run(_cfg(staging, {"file": t}, filename_parse=fp))
        check(all(c["researcher"] == "R" for c in cases) and len(cases) == 2,
              "the table's value wins over a filename-parsed value of the same name")


def test_missing_rows():
    print("test_missing_rows")
    with tempfile.TemporaryDirectory() as td:
        staging = _tree(td)
        t = os.path.join(td, "cases.csv")
        _table(t, [["drive1_X/Other/plain_2.czi", "", "", "", "", ""],
                   ["drive1_X/gone.czi", "", "", "", "", ""]])
        try:
            _run(_cfg(staging, {"file": t}))
            check(False, "a file with no row aborts the batch (on_missing: error)")
        except ValueError as e:
            check("no row" in str(e), "a file with no row aborts the batch (on_missing: error)")
        cases, out = _run(_cfg(staging, {"file": t, "on_missing": "skip"}))
        check([c["original_name"] for c in cases] == ["drive1_X/Other/plain_2.czi"],
              "on_missing: skip ingests only the files that have a row")
        check("SKIP" in out and "no row" in out, "the skipped file is logged")
        check("1 case_table row(s) matched no file" in out, "a row matching no file is reported")


def test_validation_and_relative_path():
    print("test_validation_and_relative_path")
    with tempfile.TemporaryDirectory() as td:
        staging = _tree(td)
        cfgdir = os.path.join(td, "configs")
        os.makedirs(cfgdir)
        _table(os.path.join(cfgdir, "rel.csv"),
               [["drive1_X/Cell observer/Ana/ID5_0522_HE.czi", "", "", "", "", ""],
                ["drive1_X/Other/plain_2.czi", "", "", "", "", ""]])
        cfg = _cfg(staging, {"file": "rel.csv"})
        cfg["_config_dir"] = cfgdir
        cases, _ = _run(cfg)
        check(len(cases) == 2, "a relative file: resolves from the config's directory")
        for bad, why in (({"file": "rel.csv", "key": "sha256"}, "only original_name"),
                         ({"file": "rel.csv", "on_missing": "maybe"}, "on_missing"),
                         ({"file": "rel.csv", "colour": "x"}, "unknown key"),
                         ({}, None)):
            if not bad:
                continue
            try:
                config.load_case_table(bad, cfgdir)
                check(False, f"malformed block refused ({why})")
            except ValueError:
                check(True, f"malformed block refused ({why})")
        dup = os.path.join(cfgdir, "dup.csv")
        _table(dup, [["a/b.czi", "", "", "", "", ""], ["a\\b.czi", "", "", "", "", ""]])
        try:
            config.load_case_table({"file": dup}, cfgdir)
            check(False, "a duplicate key (after slash normalisation) is refused")
        except ValueError:
            check(True, "a duplicate key (after slash normalisation) is refused")


def test_absent_block_is_noop():
    print("test_absent_block_is_noop")
    check(config.load_case_table(None) == (None, None), "no block -> (None, None)")
    with tempfile.TemporaryDirectory() as td:
        staging = _tree(td)
        cfg = _cfg(staging, None)
        cfg["registry"].update(researcher="NA", project_name="NA")
        cfg["operator"] = "NA"
        cfg["auto_discover"].pop("subject_lookup")
        cases, _ = _run(cfg)
        check(len(cases) == 2 and all(c["researcher"] == "" for c in cases),
              "without a case_table the batch expands exactly as before")


def test_xmic_code():
    print("test_xmic_code")
    check("XMIC" in config.VALID_INSTRUMENTS, "XMIC is a valid instrument code")
    check(config.resolve_ecosystem("XMIC") == "MICROSCOPY", "XMIC -> MICROSCOPY")


def main():
    test_values_per_case()
    test_table_beats_filename()
    test_missing_rows()
    test_validation_and_relative_path()
    test_absent_block_is_noop()
    test_xmic_code()
    print()
    if FAILS:
        print(f"FAILED ({len(FAILS)}):")
        for m in FAILS:
            print(f"  - {m}")
        return 1
    print("ALL PASS (case_table per-case override / XMIC code)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
