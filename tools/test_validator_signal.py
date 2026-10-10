#!/usr/bin/env python3
"""test_validator_signal.py -- validate_registries reports a signal, not a dump (issue #8).

  1. A finding class is reported ONCE with its count and a few example rows
     (`--examples N`, 'all' for every row); a single-row class prints as before.
  2. The documented unknown sentinels (condition.is_control null,
     anatomy.is_whole_body null, subject.source pending-db) are COVERAGE
     lines, not warnings; a missing block is still a WARN.
  3. Multi-value hygiene: `A;;B`, `A;`, `A;A` in subject_ids / modalities_in_study /
     project_id are WARNs (one class each); `A; B` (whitespace) is not reported.
  4. Age sanity: an acquisition dated before its subject's date_of_birth is a
     WARN; the pair count is an info line.
  5. /raw/ orphan walk: an ACQ-ID folder with no row and no tombstone is a WARN;
     a live or a retired id is not; non-ACQ names are ignored.
  6. Back-compat: errors/warnings stay (acq_id, msg) tuples; the operator info
     line is unchanged; a clean registry prints "No issues found."

Temporary directories only: no NAS, no database, no pytest.

Run:  python tools/test_validator_signal.py      (exit 0 = pass)
"""

import contextlib
import csv
import io
import json
import os
import sys
import tempfile

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import validate_registries as vr  # noqa: E402
from ingest import registry, retired, subjects_table  # noqa: E402
# The fixture builders of the operator-hold suite (registry bytes, a minimal NAS).
import test_operator_hold as toh  # noqa: E402

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok:   {msg}")


def validate(nas, enrich=False):
    with contextlib.redirect_stderr(io.StringIO()):
        return vr.validate(nas, check_enrich=enrich)


def report(issues, n, examples=vr.DEFAULT_EXAMPLES):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        vr.print_report(issues, n, examples=examples)
    return out.getvalue()


def write_subjects(nas, rows):
    path = os.path.join(nas, "registries", "registry_subjects.csv")
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=subjects_table.SUBJECT_FIELDS)
        w.writeheader()
        for r in rows:
            full = {k: "" for k in subjects_table.SUBJECT_FIELDS}
            full.update(r)
            w.writerow(full)


def write_sidecar(nas, row, md):
    folder = os.path.join(nas, *row["canonical_path"].strip("/").split("/"))
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(md, f)


def cls_of(issues, level="warn"):
    return list(dict.fromkeys(issues.warn_cls if level == "warn" else issues.error_cls))


# ---- 1. grouping ----------------------------------------------------------------

def test_grouping():
    print("[a finding class is reported once, with examples]")
    with tempfile.TemporaryDirectory() as d:
        rows = [toh.reg_row(f"ACQ-20220118-MRI-{i:03d}", operator=toh.PH) for i in range(1, 9)]
        rows.append(toh.reg_row("ACQ-20220119-MRI-001", sample_type="plasma"))
        nas = toh.write_nas(d, toh.registry_bytes(rows), rows)
        issues, n = validate(nas)
        check(n == 9 and len(issues.errors) == 9, f"9 rows, 9 errors (got {len(issues.errors)})")
        check(all(isinstance(e, tuple) and len(e) == 2 for e in issues.errors),
              "errors stay (acq_id, msg) 2-tuples")
        check(len(issues.error_cls) == len(issues.errors), "a class per error, in parallel")
        text = report(issues, n)
        lines = text.splitlines()
        head = [l for l in lines if "still contains unsubstituted template syntax -- 8 row(s)" in l]
        check(len(head) == 1, "the 8 placeholder rows are one class with a count")
        shown = [l for l in lines if l.strip().startswith("[ACQ-20220118-MRI-")]
        check(len(shown) == 5, f"5 example rows by default (got {len(shown)})")
        check(any("and 3 more" in l for l in lines), "the remainder is counted")
        check(any("ERROR: [ACQ-20220119-MRI-001] sample_type 'plasma'" in l for l in lines),
              "a single-row class prints as one plain line")
        text_all = report(issues, n, examples=None)
        check(sum(1 for l in text_all.splitlines() if l.strip().startswith("[ACQ-20220118-MRI-")) == 8,
              "--examples all lists every row")
        text_zero = report(issues, n, examples=0)
        check("8 row(s)" in text_zero and "and 8 more" in text_zero
              and not any(l.strip().startswith("[ACQ-20220118-MRI-") for l in text_zero.splitlines()),
              "--examples 0 shows counts only")
        check(vr._parse_examples("all") is None and vr._parse_examples("3") == 3,
              "--examples parses 'all' and a number")


# ---- 2. sentinels as coverage ---------------------------------------------------------

def test_coverage():
    print("[unknown sentinels are coverage, missing blocks are warnings]")
    with tempfile.TemporaryDirectory() as d:
        rows = [
            toh.reg_row("ACQ-20220118-MRI-001", sample_type="organism"),  # all unknown
            toh.reg_row("ACQ-20220118-MRI-002", sample_type="organism"),  # all known
            toh.reg_row("ACQ-20220118-MRI-003", sample_type="tissue"),    # no condition block
            toh.reg_row("ACQ-20220118-MRI-004", sample_type="cells"),     # not enriched
        ]
        nas = toh.write_nas(d, toh.registry_bytes(rows), rows)
        write_sidecar(nas, rows[0], {"subject": {"source": "pending-db"},
                                     "condition": {"is_control": None},
                                     "anatomy": {"is_whole_body": None}})
        write_sidecar(nas, rows[1], {"subject": {"source": "animal-facility-db"},
                                     "condition": {"is_control": True},
                                     "anatomy": {"is_whole_body": False}})
        write_sidecar(nas, rows[2], {"subject": {"source": "animal-facility-db"}})
        issues, n = validate(nas, enrich=True)
        check(not issues.errors, "0 errors")
        check([m for _a, m in issues.warnings] == ["sidecar missing condition: block"],
              f"the only warning is the missing block (got {[m for _a, m in issues.warnings]})")
        cov = issues.coverage
        check(cov["condition.is_control known (not null)"] == {"known": 1, "unknown": 1},
              "is_control coverage counted (1 known, 1 unknown)")
        check(cov["anatomy.is_whole_body known (not null; organism rows)"] == {"known": 1, "unknown": 1},
              "is_whole_body coverage counted on organism rows only")
        check(cov["subject recovered (not `pending-db`)"] == {"known": 2, "unknown": 1},
              "pending-db counted as coverage, not warned")
        text = report(issues, n)
        check("COVERAGE" in text and "condition.is_control known (not null): 1 of 2 (1 unknown)" in text,
              "the report prints coverage lines")
        check("age sanity: 0 (acquisition, subject) pair(s)" in text, "the info section prints the age-pair count")


# ---- 3. multi-value hygiene -------------------------------------------------------------

def test_multivalue():
    print("[multi-value cell hygiene]")
    with tempfile.TemporaryDirectory() as d:
        rows = [
            toh.reg_row("ACQ-20220118-MRI-001", subject_ids="1-AE-biomaGUNE-0525;;2-AE-biomaGUNE-0525"),
            toh.reg_row("ACQ-20220118-MRI-002", modalities_in_study="MR;"),
            toh.reg_row("ACQ-20220118-MRI-003", subject_ids="3-AE-biomaGUNE-0525;3-AE-biomaGUNE-0525"),
            toh.reg_row("ACQ-20220118-MRI-004", subject_ids="4-AE-biomaGUNE-0525; 5-AE-biomaGUNE-0525"),
            toh.reg_row("ACQ-20220118-MRI-005", subject_ids="6-AE-biomaGUNE-0525"),
        ]
        nas = toh.write_nas(d, toh.registry_bytes(rows), rows)
        issues, _n = validate(nas)
        check(not issues.errors, "hygiene findings are WARNs, not errors")
        got = {(a, c) for (a, _m), c in zip(issues.warnings, issues.warn_cls)}
        check(("ACQ-20220118-MRI-001", "column 'subject_ids' has an empty segment") in got, "A;;B -> empty segment")
        check(("ACQ-20220118-MRI-002", "column 'modalities_in_study' starts or ends with the separator") in got,
              "A; -> trailing separator")
        check(("ACQ-20220118-MRI-003", "column 'subject_ids' repeats a member") in got, "A;A -> duplicate member")
        check(not any(a in ("ACQ-20220118-MRI-004", "ACQ-20220118-MRI-005") for a, _c in got),
              "whitespace around the separator, and a single value, are not reported")
        check(len(issues.warnings) == 3, f"exactly three warnings (got {len(issues.warnings)})")


# ---- 4. age sanity -------------------------------------------------------------------------

def test_age_sanity():
    print("[an acquisition before its subject's date of birth]")
    with tempfile.TemporaryDirectory() as d:
        rows = [
            toh.reg_row("ACQ-20230807-CT-006", instrument="CT", subject_ids="73-AE-biomaGUNE-1321"),
            toh.reg_row("ACQ-20230807-CT-007", instrument="CT", subject_ids="74-AE-biomaGUNE-1321;75-AE-biomaGUNE-1321"),
            toh.reg_row("ACQ-20230807-CT-008", instrument="CT", subject_ids="76-AE-biomaGUNE-1321"),  # no DOB
        ]
        nas = toh.write_nas(d, toh.registry_bytes(rows), rows)
        write_subjects(nas, [
            {"facility_id": "73-AE-biomaGUNE-1321", "project_alias": "1321", "date_of_birth": "2023-08-10"},
            {"facility_id": "74-AE-biomaGUNE-1321", "project_alias": "1321", "date_of_birth": "2023-06-01"},
            {"facility_id": "75-AE-biomaGUNE-1321", "project_alias": "1321", "date_of_birth": "2023-08-07"},
            {"facility_id": "76-AE-biomaGUNE-1321", "project_alias": "1321", "date_of_birth": ""},
        ])
        issues, _n = validate(nas)
        check(not issues.errors, "0 errors (the DOB finding is a WARN)")
        bad = [a for (a, _m), c in zip(issues.warnings, issues.warn_cls)
               if c == "acquisition dated before the subject's date of birth"]
        check(bad == ["ACQ-20230807-CT-006"], f"only the acquisition before the DOB is reported (got {bad})")
        check(any("3 (acquisition, subject) pair(s)" in m for m in issues.notes),
              "3 pairs checked (the subject with no DOB is skipped)")
        check(vr._iso_date("2023-08-07T10:21:42+01:00") == "2023-08-07" and vr._iso_date("20230807") == "2023-08-07"
              and vr._iso_date("") == "" and vr._iso_date("n/a") == "",
              "_iso_date handles ISO, compact and blank")


# ---- 5. /raw/ orphans --------------------------------------------------------------------

def test_raw_orphans():
    print("[/raw/ folders with no registry row and no tombstone]")
    with tempfile.TemporaryDirectory() as d:
        rows = [toh.reg_row("ACQ-20260710-MRI-018")]
        nas = toh.write_nas(d, toh.registry_bytes(rows), rows)
        month = os.path.join(nas, "raw", "DICOM", "2026", "2026-07")
        for i in range(1, 4):
            os.makedirs(os.path.join(month, f"ACQ-20260710-MRI-{i:03d}"))
        os.makedirs(os.path.join(month, "_notes"))
        with open(os.path.join(month, "ACQ-20260710-MRI-099"), "w") as f:
            f.write("a file, not a folder")
        # a tombstone for -002 (its folder deleted) and one for -003 (folder still there: check_retired's ERROR)
        tomb_path = retired.retired_path(os.path.join(nas, "registries"))
        with open(tomb_path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=retired.RETIRED_FIELDS)
            w.writeheader()
            for acq in ("ACQ-20260710-MRI-002", "ACQ-20260710-MRI-003"):
                t = {k: "" for k in retired.RETIRED_FIELDS}
                t.update({"acq_id": acq, "disposition": "orphan", "bytes_fate": sorted(retired.BYTES_FATES)[0],
                          "original_canonical_path": f"/raw/DICOM/2026/2026-07/{acq}/"})
                w.writerow(t)
        os.rmdir(os.path.join(month, "ACQ-20260710-MRI-002"))
        issues, _n = validate(nas)
        orphans = [a for (a, _m), c in zip(issues.warnings, issues.warn_cls)
                   if c == "/raw/ folder with no registry row and no tombstone"]
        check(orphans == ["ACQ-20260710-MRI-001"], f"only -001 is an orphan (got {orphans})")
        check(any("retired, but its /raw/ folder still exists" in c for c in issues.error_cls),
              "-003's surviving folder is check_retired's ERROR, not an orphan")
        check(any("/raw/ walk: 3 acquisition folder(s) seen, 1 live row(s), 2 tombstone(s)" in m
                  for m in issues.notes), f"the walk is summarised ({issues.notes})")

    with tempfile.TemporaryDirectory() as d:
        nas = toh.write_nas(d, toh.registry_bytes([]), [])
        issues, _n = validate(nas)
        check(not issues.warnings and not issues.errors, "no /raw/ at all: nothing reported")


# ---- 6. back-compat -----------------------------------------------------------------------

def test_backcompat():
    print("[a clean registry, the operator info line]")
    with tempfile.TemporaryDirectory() as d:
        rows = [toh.reg_row("ACQ-20220118-MRI-001", operator=toh.HOLD),
                toh.reg_row("ACQ-20220118-MRI-002", operator="AINHIZE")]
        nas = toh.write_nas(d, toh.registry_bytes(rows), rows)
        issues, n = validate(nas)
        check(not issues.errors and not issues.warnings and issues.operator_hold == 1, "0 errors, 0 warnings, 1 hold")
        text = report(issues, n)
        check(f"operator awaiting claim ({toh.HOLD}): 1" in text.splitlines(), "the info line is unchanged")
        check("No issues found." in text, "a clean registry still says so")
        check(vr.main(["--nas-root", nas, "--no-enrichment", "--examples", "all"]) == 0, "CLI exit 0 with --examples all")
        check(vr.main(["--nas-root", os.path.join(d, "nowhere")]) == 2, "CLI exit 2 on a bad root")


def main():
    test_grouping()
    test_coverage()
    test_multivalue()
    test_age_sanity()
    test_raw_orphans()
    test_backcompat()
    print()
    if FAILS:
        print(f"{len(FAILS)} FAILURE(S):")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print("ALL VALIDATOR-SIGNAL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
