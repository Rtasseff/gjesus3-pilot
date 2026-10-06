#!/usr/bin/env python3
"""test_subject_id_null_alias.py — the null-project-alias defect, both halves.

Covers the fix recorded in tasks/SUBJECT_ID_NULL_ALIAS_HANDOFF.md §4.1/§4.2:

  §4.1 animal_db.compose_subject_id REFUSES a null alias instead of formatting
       the plausible-but-ambiguous "<n>-AE-biomaGUNE-None". Plus the
       non-blocking contract: ingest enrichment must not start raising now
       that compose_subject_id can. (The _query_subject fallback itself is
       verified against the LIVE facility DB, not mocked here — see the
       comment above test_enrichment_stays_non_blocking.)

  §4.2 validate_registries flags every surviving bad id as an ERROR — in
       registry_raw.subject_ids and in registry_subjects.csv — while leaving
       the legitimate blank-alias DTS24 human subjects alone.

No database, no NAS, no pytest — pure string logic, an injected lookup, and a
temp dir. Anything that only the live DB can answer is deliberately not here.

Run:  PYTHONPATH=tools python tools/test_subject_id_null_alias.py
"""

import csv
import os
import sys
import tempfile

import animal_db
import validate_registries as vr
from ingest import enrichment, subjects_table


FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok:   {msg}")


def _refuses(code, alias):
    """True when compose_subject_id raises ValueError for this pair."""
    try:
        animal_db.compose_subject_id(code, alias)
        return False
    except ValueError:
        return True


# ---- §4.1a compose_subject_id --------------------------------------------

def test_compose_refuses_null_alias():
    print("compose_subject_id refuses a null alias:")
    for alias in (None, "", "   ", "None", "none", "NONE", "null", "NULL", " none "):
        check(_refuses(23, alias), f"refuses alias {alias!r}")


def test_compose_still_builds_good_ids():
    print("compose_subject_id still builds the canonical id:")
    check(animal_db.compose_subject_id(13, "0525") == "13-AE-biomaGUNE-0525",
          "compose(13, '0525') -> 13-AE-biomaGUNE-0525")
    check(animal_db.compose_subject_id("13", "0525") == "13-AE-biomaGUNE-0525",
          "animal_code accepts a string")
    check(animal_db.compose_subject_id("013", "0525") == "13-AE-biomaGUNE-0525",
          "animal_code leading zeros are dropped (int coercion)")
    check(animal_db.compose_subject_id(23, "0219") == "23-AE-biomaGUNE-0219",
          "alias leading zero is PRESERVED (0219 stays 0219, not 219)")
    check(animal_db.compose_subject_id(23, " 1521 ") == "23-AE-biomaGUNE-1521",
          "alias whitespace is stripped")
    # Round-trips through the parser that reads these ids back.
    alias, code = animal_db.parse_subject_id(animal_db.compose_subject_id(23, "0219"))
    check((alias, code) == ("0219", 23), "compose -> parse_subject_id round-trips")


# ---- §4.1b the ingest must NOT start raising ----------------------------
#
# The other half of §4.1 — _query_subject falling back to the caller's alias on
# a NULL projectAlias — is NOT tested here. It is one line whose whole point is
# what the live facility DB actually returns; a fake cursor matching query text
# would test the fake. It was verified against the real DB instead (read-only),
# and the output is in the commit message.

def test_enrichment_stays_non_blocking():
    print("enrichment honours the non-blocking contract (08_METADATA 4.7):")
    logged = []

    def _log(msg, level="INFO"):
        logged.append((level, msg))

    def _miss(alias, code):
        return animal_db.LookupResult("not_found", reason="db-miss",
                                      detail="fake miss")

    # An unresolvable alias used to yield "13-AE-biomaGUNE-"; compose now
    # refuses, and the caller must degrade rather than break the ingest.
    block = enrichment._resolve_one_db_subject(
        "", 13, "2026-01-01", "ACQ-20260101-MRI-001", "", "", True, _miss, _log)
    check(block["facility_animal_id"] == "",
          "an unresolvable alias yields a BLANK facility id, not a broken one")
    check(block["source"] == "pending-db", "the acquisition still queues as pending-db")
    check(any(lvl == "WARN" for lvl, _ in logged), "the refusal is WARNed, not swallowed")
    # A blank id must not become a subjects-table row keyed on nothing.
    check(subjects_table.row_from_subject_block(block) is None,
          "no subjects-table row is created for a blank facility id")

    # The normal miss path is untouched: a good alias still composes.
    logged.clear()
    ok = enrichment._resolve_one_db_subject(
        "0525", 13, "2026-01-01", "ACQ-20260101-MRI-001", "", "", True, _miss, _log)
    check(ok["facility_animal_id"] == "13-AE-biomaGUNE-0525",
          "a good alias still composes on the pending path")


# ---- §4.2 the detector ---------------------------------------------------

def test_null_alias_of():
    print("null_alias_of classifies ids:")
    check(vr.null_alias_of("23-AE-biomaGUNE-None") == "None",
          "the production defect is caught")
    check(vr.null_alias_of("3-ae-biomagune-null") == "null",
          "case-insensitive, and 'null' too")
    check(vr.null_alias_of("13-AE-biomaGUNE-") == "",
          "a bare stem with no alias is caught")
    check(vr.null_alias_of("13-AE-biomaGUNE-0525") is None, "a good id is clean")
    check(vr.null_alias_of("13-AE-biomaGUNE-0219") is None,
          "a repaired 0219 id is clean")
    check(vr.null_alias_of("LEONE_1.01") is None,
          "a DTS24 human id is out of scope (not a facility id)")
    check(vr.null_alias_of("") is None and vr.null_alias_of(None) is None,
          "blank / None -> nothing to report")
    # Belt and braces: ids that fail the grammar but still end in the broken
    # stem must NOT slip past — that is how a backfill claims a clean sweep.
    check(vr.null_alias_of("-AE-biomaGUNE-None") == "None",
          "a malformed id with no animal code is still caught")
    check(vr.null_alias_of("m13-AE-biomaGUNE-None") == "None",
          "a stray-prefixed id is still caught")
    check(vr.null_alias_of("x-AE-biomaGUNE-") == "",
          "a malformed id ending in a bare stem is still caught")
    check(vr.null_alias_of("13-AE-biomaGUNE-None-extra") is None,
          "a non-null alias that merely contains 'None' is NOT flagged")

    check(vr.is_facility_id("13-AE-biomaGUNE-0525") and
          not vr.is_facility_id("LEONE_1.01") and not vr.is_facility_id(""),
          "is_facility_id draws the animal/human line")


def test_check_subject_ids():
    print("check_subject_ids over a registry_raw cell:")
    iss = vr.Issues()
    vr.check_subject_ids("23-AE-biomaGUNE-None", "ACQ-1", iss)
    check(len(iss.errors) == 1 and iss.errors[0][0] == "ACQ-1",
          "one ERROR, tagged with the acq label")

    iss = vr.Issues()
    vr.check_subject_ids("13-AE-biomaGUNE-0525;14-AE-biomaGUNE-None;15-AE-biomaGUNE-0525",
                         "ACQ-2", iss)
    check(len(iss.errors) == 1 and "14-AE-biomaGUNE-None" in iss.errors[0][1],
          "a multi-animal cell reports only the bad member")

    iss = vr.Issues()
    vr.check_subject_ids("13-AE-biomaGUNE-0525;14-AE-biomaGUNE-0525", "ACQ-3", iss)
    vr.check_subject_ids("", "ACQ-4", iss)
    vr.check_subject_ids(None, "ACQ-5", iss)
    check(not iss.errors, "clean / empty / None cells produce nothing")


def _write_subjects_csv(d, rows):
    path = os.path.join(d, subjects_table.SUBJECTS_FILENAME)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=subjects_table.SUBJECT_FIELDS,
                           extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in subjects_table.SUBJECT_FIELDS})
    return path


def test_check_subjects_registry():
    print("check_subjects_registry over registry_subjects.csv:")
    with tempfile.TemporaryDirectory() as d:
        _write_subjects_csv(d, [
            # 1 bad: literal "None" in both the id and the alias column.
            {"facility_id": "23-AE-biomaGUNE-None", "project_alias": "None"},
            # 2 bad: a clean-looking id whose alias column leaked the string.
            {"facility_id": "23-AE-biomaGUNE-0219", "project_alias": "None"},
            # 3 good: fully repaired.
            {"facility_id": "23-AE-biomaGUNE-1521", "project_alias": "1521"},
            # 4 good (handoff 7): DTS24 human subject, no animal protocol.
            {"facility_id": "LEONE_1.01", "project_alias": "",
             "source": "dicom-header"},
            # 5 bad: a facility id with an empty alias column.
            {"facility_id": "9-AE-biomaGUNE-0618", "project_alias": ""},
        ])
        iss = vr.Issues()
        n = vr.check_subjects_registry(d, iss)
        check(n == 5, "all 5 rows read")
        bad_ids = sorted({e[0] for e in iss.errors})
        check(bad_ids == ["23-AE-biomaGUNE-0219", "23-AE-biomaGUNE-None",
                          "9-AE-biomaGUNE-0618"],
              f"exactly the 3 broken rows are ERRORs (got {bad_ids})")
        check(not any(e[0] == "LEONE_1.01" for e in iss.errors),
              "the DTS24 human subject is NOT reported")
        check(not iss.warnings, "no warnings when the table exists")

    with tempfile.TemporaryDirectory() as d:
        iss = vr.Issues()
        check(vr.check_subjects_registry(d, iss) == 0 and not iss.errors
              and len(iss.warnings) == 1,
              "a missing table is a WARN, not an ERROR")


def main():
    for fn in (test_compose_refuses_null_alias,
               test_compose_still_builds_good_ids,
               test_enrichment_stays_non_blocking,
               test_null_alias_of,
               test_check_subject_ids,
               test_check_subjects_registry):
        fn()
    print()
    if FAILS:
        print(f"FAILED ({len(FAILS)}):")
        for m in FAILS:
            print(f"  - {m}")
        sys.exit(1)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
