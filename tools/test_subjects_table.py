#!/usr/bin/env python3
"""test_subjects_table.py — self-contained checks for the subjects-table writer.

Exercises ingest/subjects_table.py (the one-row-per-SUBJECT registry_subjects.csv
upsert) WITHOUT a database and WITHOUT the NAS — every test runs against a fresh
temp dir and the real registry lock. No pytest dependency.

Run:  PYTHONPATH=tools python tools/test_subjects_table.py
"""

import os
import sys
import tempfile

from ingest import subjects_table as st


FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok:   {msg}")


def _row(fid, source="animal-facility-db", **kw):
    r = {"facility_id": fid, "source": source}
    r.update(kw)
    return r


def _read(d):
    return st.read_subjects(st.subjects_path(d))


def test_insert_and_idempotent():
    print("insert + idempotency (R7):")
    d = tempfile.mkdtemp()
    fid = "13-AE-biomaGUNE-0525"
    s = st.upsert_subjects(d, [_row(fid, species="Mus musculus", sex="M",
                                    animal_code="13", project_alias="0525",
                                    strain="C57BL/6")], now="T1")
    check(s == {"inserted": 1, "updated": 0, "unchanged": 0}, "first upsert inserts")
    t = _read(d)
    check(len(t) == 1, "one row on disk")
    r = t[fid]
    check(r["species"] == "Mus musculus" and r["sex"] == "M", "static fields stored")
    check(r["animal_code"] == "13" and r["project_alias"] == "0525", "code/alias stored")
    check(r["first_registered"] == "T1" and r["last_updated"] == "T1", "timestamps set on insert")
    # Re-upsert identical data at a LATER time -> no change, no bump, no new row.
    s2 = st.upsert_subjects(d, [_row(fid, species="Mus musculus", sex="M",
                                     animal_code="13", project_alias="0525",
                                     strain="C57BL/6")], now="T2")
    check(s2 == {"inserted": 0, "updated": 0, "unchanged": 1}, "re-upsert is a no-op")
    check(_read(d)[fid]["last_updated"] == "T1", "last_updated NOT bumped on no-op")


def test_two_ids_and_multianimal():
    print("distinct ids + multi-animal scan (one call):")
    d = tempfile.mkdtemp()
    st.upsert_subjects(d, [_row("1-AE-biomaGUNE-0525"), _row("2-AE-biomaGUNE-0525")], now="T1")
    check(len(_read(d)) == 2, "two distinct ids -> two rows")
    # A multi-animal NI scan contributes its 1-4 animals in a single upsert call.
    d2 = tempfile.mkdtemp()
    s = st.upsert_subjects(d2, [_row(f"{n}-AE-biomaGUNE-0124") for n in (2, 4, 5, 6)], now="T1")
    check(s["inserted"] == 4 and len(_read(d2)) == 4, "4-animal scan -> 4 rows, one call")


def test_pending_then_db_upgrade():
    print("pending-db stub -> later DB hit upgrades (no data lost):")
    d = tempfile.mkdtemp()
    fid = "9-AE-biomaGUNE-0525"
    st.upsert_subjects(d, [_row(fid, source="pending-db", animal_code="9",
                                project_alias="0525")], now="T1")
    r = _read(d)[fid]
    check(r["source"] == "pending-db" and r["species"] == "", "stub: source=pending-db, species blank")
    s = st.upsert_subjects(d, [_row(fid, source="animal-facility-db",
                                    species="Mus musculus", sex="F",
                                    strain="BALB/c")], now="T2")
    check(s["updated"] == 1, "DB hit updates the stub")
    r = _read(d)[fid]
    check(r["source"] == "animal-facility-db", "source upgraded to DB")
    check(r["species"] == "Mus musculus" and r["sex"] == "F", "DB fields filled in")
    check(r["first_registered"] == "T1" and r["last_updated"] == "T2", "first kept, last bumped")


def test_db_not_clobbered_by_later_pending():
    print("DB row is NOT clobbered by a later pending-db stub:")
    d = tempfile.mkdtemp()
    fid = "7-AE-biomaGUNE-0424"
    st.upsert_subjects(d, [_row(fid, species="Mus musculus", sex="M",
                                strain="C57BL/6")], now="T1")
    s = st.upsert_subjects(d, [_row(fid, source="pending-db")], now="T2")
    check(s["unchanged"] == 1, "blank lower-confidence stub changes nothing")
    r = _read(d)[fid]
    check(r["source"] == "animal-facility-db" and r["species"] == "Mus musculus",
          "DB record intact")
    check(r["last_updated"] == "T1", "no spurious last_updated bump")


def test_gap_fill_regardless_of_source():
    print("an empty/sentinel field is filled by any real value (even lower rank):")
    d = tempfile.mkdtemp()
    fid = "5-AE-biomaGUNE-0525"
    # DB row, but sex came back as the 'unknown' sentinel.
    st.upsert_subjects(d, [_row(fid, species="Mus musculus", sex="unknown")], now="T1")
    s = st.upsert_subjects(d, [_row(fid, source="pending-db", sex="M")], now="T2")
    check(s["updated"] == 1, "gap-fill counts as an update")
    r = _read(d)[fid]
    check(r["sex"] == "M", "sentinel sex filled by a real value")
    check(r["source"] == "animal-facility-db", "source label stays at the higher rank")
    check(r["species"] == "Mus musculus", "existing real field untouched")


def test_equal_rank_no_churn():
    print("equal-confidence conflict keeps the existing value (stable):")
    d = tempfile.mkdtemp()
    fid = "3-AE-biomaGUNE-0525"
    st.upsert_subjects(d, [_row(fid, strain="C57BL/6")], now="T1")
    s = st.upsert_subjects(d, [_row(fid, strain="BALB/c")], now="T2")
    check(s["unchanged"] == 1, "same-rank differing value does not overwrite")
    check(_read(d)[fid]["strain"] == "C57BL/6", "first strain retained")


def test_row_from_subject_block():
    print("row_from_subject_block projection:")
    canon = st.row_from_subject_block({
        "facility_animal_id": "13-AE-biomaGUNE-0525",
        "species": "Mus musculus", "sex": "M", "strain": "C57BL/6",
        "date_of_birth": "2025-01-02", "age_at_acquisition": "P12W",  # per-acq -> dropped
        "weight_at_acquisition_g": 24.1, "procedures": [{"type": "x"}],
        "source": "animal-facility-db",
    })
    check(canon["animal_code"] == "13" and canon["project_alias"] == "0525",
          "canonical id parsed into code + alias")
    check("age_at_acquisition" not in canon and "weight_at_acquisition_g" not in canon,
          "per-(scan,animal) fields dropped")
    check(canon["date_of_birth"] == "2025-01-02", "static DOB kept")
    noncanon = st.row_from_subject_block({"facility_animal_id": "weird-id", "sex": "F"})
    check(noncanon is not None and noncanon["animal_code"] == "" and noncanon["project_alias"] == "",
          "non-canonical id -> row kept, parsed parts blank")
    check(st.row_from_subject_block({"facility_animal_id": ""}) is None, "no id -> None")
    check(st.row_from_subject_block(None) is None, "no block -> None")
    check(st.row_from_subject_block({"facility_animal_id": "13-AE-biomaGUNE-0525",
                                     "date_of_birth": None})["date_of_birth"] == "",
          "None DOB normalized to empty string")


def test_no_pk_skipped():
    print("rows without a facility_id are skipped, not fatal:")
    d = tempfile.mkdtemp()
    s = st.upsert_subjects(d, [{"source": "unknown", "species": "x"}], now="T1")
    check(s == {"inserted": 0, "updated": 0, "unchanged": 0}, "no-PK row skipped")
    check(not os.path.exists(st.subjects_path(d)), "no file written when nothing to write")


def test_header_mismatch_fails_loud():
    print("a wrong-header file fails loud instead of being silently rewritten:")
    d = tempfile.mkdtemp()
    p = st.subjects_path(d)
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write("acq_id,animal\nX,Y\n")
    raised = False
    try:
        st.read_subjects(p)
    except RuntimeError:
        raised = True
    check(raised, "read_subjects raises on header mismatch")


def main():
    for fn in (test_insert_and_idempotent, test_two_ids_and_multianimal,
               test_pending_then_db_upgrade, test_db_not_clobbered_by_later_pending,
               test_gap_fill_regardless_of_source, test_equal_rank_no_churn,
               test_row_from_subject_block, test_no_pk_skipped,
               test_header_mismatch_fails_loud):
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
