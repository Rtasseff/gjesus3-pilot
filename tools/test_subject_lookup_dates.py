#!/usr/bin/env python3
"""test_subject_lookup_dates.py -- the dated, transfer-aware subject lookup and its users.

(protocol, code) names one animal only AT A POINT IN TIME (verified 2026-10-19). An
animal that changes protocol keeps its old pair in old_project /
old_project_animal_code / project_change_date, and the old code may later go to a
new animal. The old lookup asked for the CURRENT holder only. Each case below is
modelled on a real one from that check, with the DB rows reduced to what matters:

  0525 #49   moved to 1025 #1 on the scan day (DB id 18522); the code went to a
             new animal (19759) on 2026-09-10. The old lookup would write 19759.
  0721 #45   moved to 0821 with a ZERO change date; the code is still free.
  1123 #98   entered 2025-02-27: slides dated 2024-08-26 cannot be its tissue.
  1123 #26   born before, entered after the slide date (ex vivo: refused too).
  1123 #15   alive on the slide date: kept, flagged tissue-before-exit.
  1321 #73   born three days after its CT: refused (before birth / entry).
  0421 #404  same-day re-issue: the move day itself is ambiguous.

Runs offline: the real HolderIndex over synthetic rows, the real enrichment,
subjects table, recovery, backfill, audit and relink code on temp dirs.

Run:  python tools/test_subject_lookup_dates.py
"""
import csv
import functools
import io
import json
import os
import sys
import tempfile
from datetime import date

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import animal_db  # noqa: E402
import audit_subject_links as audit  # noqa: E402
import backfill_subjects_table as backfill  # noqa: E402
import recover_subject_metadata as rec  # noqa: E402
import relink_subjects as relink  # noqa: E402
from ingest import enrichment, pending, registry, subjects_table  # noqa: E402

FAILED = []


def check(cond, msg):
    print(f"  {'ok' if cond else 'FAIL'}:   {msg}")
    if not cond:
        FAILED.append(msg)


def quiet(*_a, **_k):
    pass


# ---- a synthetic facility DB ------------------------------------------------

PROJECTS = [
    {"id": 1, "project_code": "AE-biomaGUNE-0525", "projectAlias": "0525"},
    {"id": 2, "project_code": "AE-biomaGUNE-1025", "projectAlias": "1025"},
    {"id": 3, "project_code": "AE-biomaGUNE-0721", "projectAlias": "0721"},
    {"id": 4, "project_code": "AE-biomaGUNE-0821", "projectAlias": "0821"},
    {"id": 5, "project_code": "AE-biomaGUNE-1123", "projectAlias": "1123"},
    {"id": 6, "project_code": "AE-biomaGUNE-1321", "projectAlias": "1321"},
    {"id": 7, "project_code": "AE-biomaGUNE-0421", "projectAlias": "0421"},
    {"id": 8, "project_code": "AE-biomaGUNE-0219/PRO-AE-SS-002", "projectAlias": None},
    {"id": 9, "project_code": "AE-biomaGUNE-1317/PRO-AE-SS-101", "projectAlias": "1317"},
    {"id": 10, "project_code": "MRI-1/PRO-AE-SS-003", "projectAlias": None},
]


def animal(id_, pid, code, entry, dob, exit_=None, old=None, old_code="", changed=None,
           sex="Male", strain="C57BL/6J"):
    return {"id": id_, "id_project": pid, "animal_code": code, "sex": sex,
            "date_of_birth": dob, "date_of_entry": entry, "turn_date": exit_, "id_turn": None,
            "old_project": old, "old_project_animal_code": old_code,
            "project_change_date": changed, "specie_type": "Mouse", "strain_type": strain}


ANIMALS = [
    # 0525 #49 -> 1025 #1 on 2026-05-21; 0525 #49 re-issued 2026-09-10.
    animal(18522, 2, 1, "2026-04-30", "2026-03-05", "2026-05-28", old=1, old_code="49",
           changed="2026-05-21"),
    animal(19759, 1, 49, "2026-09-10", "2026-07-16", "2026-09-14", sex="Female"),
    # 0721 #45 -> 0821 #3, change date lost (MySQL zero date, returned as a string).
    animal(8500, 4, 3, "2022-09-01", "2022-07-28", "2022-12-01", old=3, old_code=" 45 ",
           changed="0000-00-00", strain="C57BL/6JRj"),
    # 1123: #98 entered 2025-02-27; #26 born before / entered after 2024-08-26; #15 alive then.
    animal(14671, 5, 98, "2025-02-27", "2025-01-02", "2025-03-04"),
    animal(14000, 5, 26, "2024-09-12", "2024-06-01", "2024-10-30"),
    animal(13900, 5, 15, "2024-08-08", "2024-06-01", "2024-09-02"),
    # 1321: #73 born 2023-08-10 (CT labelled 73 on 2023-08-07); #98 for the relink.
    animal(11733, 6, 73, "2023-10-05", "2023-08-10", "2023-11-06"),
    animal(11839, 6, 98, "2023-10-20", "2023-08-01", "2023-11-28"),
    # 0421 #404: moved 2024-12-19, the code re-issued the same day.
    animal(13371, 2, 77, "2024-10-01", "2024-08-01", None, old=7, old_code="404",
           changed="2024-12-19"),
    animal(14245, 7, 404, "2024-12-19", "2024-11-01", None),
    # 0219 (null alias) #23; the 1317 animal #23 that the unanchored LIKE used to return.
    animal(9000, 8, 23, "2019-03-01", "2019-01-01", None),
    animal(9001, 9, 23, "2019-03-01", "2019-01-01", None, sex="Female"),
    # A pre-2015 legacy pair: two current holders at once (no alias; unreachable by id).
    animal(329, 10, 1, "2013-12-05", "2013-10-17", "2015-02-20"),
    animal(1087, 10, 1, "2014-12-18", "2014-11-06", "2015-02-20"),
]

IDX = animal_db.HolderIndex(PROJECTS, ANIMALS)
LOOKUP = functools.partial(animal_db.lookup, index=IDX)


def look(alias, code, day, in_vivo=True):
    return animal_db.lookup(alias, code, on_date=day, in_vivo=in_vivo, index=IDX)


# ---- the lookup -------------------------------------------------------------

def test_dates():
    print("dates: ACQ-ID prefixes, ISO strings, zero dates")
    check(animal_db.acq_id_day("ACQ-20260521-MRI-001") == date(2026, 5, 21), "ACQ-ID -> date")
    check(animal_db.as_day("2026-05-21T08:17:17,940+0200") == date(2026, 5, 21), "vendor datetime")
    check(animal_db.as_day("0000-00-00") is None, "a MySQL zero date is unknown, not an error")
    check(animal_db.as_day("garbage") is None and animal_db.acq_id_day("x") is None,
          "unparseable -> None")


def test_0525_transfer_and_reissue():
    print("0525 #49: the scan-day holder, not the code's later animal")
    r = look("0525", 49, "2026-05-21")
    check(r.status == "found" and r.subject["facility_db_id"] == 18522,
          "MRI on the move day -> DB id 18522 (the old lookup said 19759)")
    check(r.subject["facility_animal_id"] == "49-AE-biomaGUNE-0525",
          "the subject id stays the code the scan was labelled with")
    check(r.subject["date_of_birth"] == "2026-03-05" and r.subject["sex"] == "M",
          "the record is the scanned animal's (born 2026-03-05, male)")
    check(r.holder["kind"] == "moved-out" and r.holder["current_facility_id"] == "1-AE-biomaGUNE-1025",
          "the holder says where the animal is now (1025 #1)")
    r = look("0525", 49, "2026-09-12")
    check(r.status == "found" and r.subject["facility_db_id"] == 19759,
          "a September scan -> the new animal 19759")
    r = look("0525", 49, "2026-07-01")
    check(r.status == "not_found" and r.reason == animal_db.REASON_DATE_CONFLICT,
          "between the two holders nobody held 49: refused as db-date-conflict")
    r = look("0525", 49, None)
    check(r.status == "not_found" and r.reason == animal_db.REASON_DATE_CONFLICT
          and "date is needed" in r.detail,
          "without a date a code with two holders is refused, never guessed")
    r = look("1025", 1, "2026-05-22")
    check(r.status == "found" and r.subject["facility_db_id"] == 18522
          and r.holder["kind"] == "current",
          "the same animal under its new code, from its change date (PET/CT 2026-05-22)")
    r = look("1025", 1, "2026-05-15")
    check(r.status == "not_found", "before it moved in, 1025 #1 was nobody's")


def test_0721_zero_change_date():
    print("0721 #45: moved with a lost change date, code still free")
    r = look("0721", 45, "2022-10-15")
    check(r.status == "found" and r.subject["facility_db_id"] == 8500,
          "found through old_project / old_project_animal_code (whitespace in the varchar)")
    check(r.holder["current_facility_id"] == "3-AE-biomaGUNE-0821", "now 0821 #3")
    check(r.warnings == [], "no warning inside its life")
    r = look("0721", 45, "2023-01-15")
    check(r.status == "found" and r.warnings == ["after-exit"],
          "an in-vivo scan after the DB exit is kept and flagged after-exit")


def test_label_errors_refused():
    print("1123 / 1321: label errors no join can fix are refused")
    r = look("1123", 98, "2024-08-26", in_vivo=False)
    check(r.status == "not_found" and r.reason == animal_db.REASON_DATE_CONFLICT,
          "a slide dated before the animal entered (and was born) is refused")
    r = look("1123", 98, "2025-04-11", in_vivo=False)
    check(r.status == "found" and r.subject["facility_db_id"] == 14671,
          "the animal's real slides (after its exit) still resolve: ex vivo has no end bound")
    r = look("1123", 26, "2024-08-26", in_vivo=False)
    check(r.status == "not_found", "born before but entered after the slide: refused")
    r = look("1123", 15, "2024-08-26", in_vivo=False)
    check(r.status == "found" and r.warnings == ["tissue-before-exit"],
          "a slide while the animal was alive is kept, flagged tissue-before-exit")
    r = look("1321", 73, "2023-08-07")
    check(r.status == "not_found" and r.reason == animal_db.REASON_DATE_CONFLICT,
          "a CT three days before the animal's birth is refused")


def test_birth_guard_and_tolerance():
    print("choose_holder: the birth guard, the tolerance, ambiguity")
    h = animal_db.build_holders([animal(1, 1, 5, "2020-01-10", "2020-03-01")], 1, 5)
    got, reason, why = animal_db.choose_holder(h, "2020-02-01")
    check(got is None and reason == animal_db.REASON_DATE_CONFLICT and "precedes the birth" in why,
          "inside the tenure but before birth (a DB date typo): refused")
    h = animal_db.build_holders([animal(1, 1, 5, "2020-01-10", "2019-11-01")], 1, 5)
    got, _r, _w = animal_db.choose_holder(h, "2020-01-09")
    check(got is not None, "one day before the entry date fits within the tolerance")
    got, _r, _w = animal_db.choose_holder(h, "2020-01-08")
    check(got is None, "two days before does not")
    r = look("0421", 404, "2024-12-19")
    check(r.status == "not_found" and "2 animals fit" in r.detail,
          "a same-day re-issue: the move day fits both holders exactly -> refused")
    r = look("0421", 404, "2024-12-20")
    check(r.status == "found" and r.subject["facility_db_id"] == 14245,
          "the day after: the exact fit (new holder) beats the tolerant one (old holder)")
    holders = animal_db.build_holders(IDX.holder_rows(10, 1), 10, 1)
    got, reason, _w = animal_db.choose_holder(holders, "2015-01-10")
    check(got is None and reason == animal_db.REASON_DATE_CONFLICT,
          "two animals holding one code at once (the 2014-15 legacy pair) -> refused")
    check(animal_db.choose_holder([], "2020-01-01")[1] == animal_db.REASON_MISS,
          "no holder ever -> db-miss")


def test_project_resolution():
    print("project resolution in the index matches the live SQL rules")
    r = look("0219", 23, "2020-01-01")
    check(r.status == "found" and r.subject["facility_db_id"] == 9000
          and r.subject["facility_animal_id"] == "23-AE-biomaGUNE-0219",
          "a NULL-alias protocol resolves through project_code, composed with the asked alias")
    r = look("101", 23, "2020-01-01")
    check(r.status == "not_found" and r.reason == animal_db.REASON_MISS,
          "anchored: protocol 101 does NOT match AE-biomaGUNE-1317/PRO-AE-SS-101")
    check("procedures" not in look("0525", 49, "2026-05-21").subject,
          "an index answer carries no procedures (not loaded)")


# ---- ingest enrichment ------------------------------------------------------

def _case(sample_type, alias, code):
    return {"sample_type": sample_type, "subject_from_db": True,
            "subject_lookup": {"project_alias": alias, "animal_code": f"m{code}"},
            "project_name": f"AE-biomaGUNE-{alias}", "discovered": {}}


def test_enrichment_dated():
    print("ingest enrichment asks for the scan-day holder")
    logs = []
    subs, _c, _a = enrichment.build_enrichment(
        _case("organism", "0525", 49), acq_id="ACQ-20260521-MRI-001", acq_date="20260521",
        acq_dt_iso="2026-05-21T08:17:17Z", lookup_fn=LOOKUP,
        log=lambda m, level="INFO": logs.append((level, m)))
    s = subs[0]
    check(s["facility_db_id"] == 18522 and s["date_of_birth"] == "2026-03-05",
          "the 0525 #49 MRI gets the scanned animal (18522), not the September one")
    check(list(s)[:2] == ["facility_animal_id", "facility_db_id"], "facility_db_id sits after the id")
    check(s["age_at_acquisition"] == "P11W", "age from the right birth date")

    with tempfile.TemporaryDirectory() as reg:
        logs.clear()
        subs, _c, _a = enrichment.build_enrichment(
            _case("tissue", "1123", 98), acq_id="ACQ-20240826-CELL-001", acq_date="20240826",
            canonical_path="/raw/MICROSCOPY/x/ACQ-20240826-CELL-001", registries_dir=reg,
            lookup_fn=LOOKUP, log=lambda m, level="INFO": logs.append((level, m)))
        s = subs[0]
        check(s["source"] == "pending-db" and s["date_of_birth"] is None and s["facility_db_id"] is None,
              "a refused lookup withholds the WHOLE record (not just the age)")
        rows = pending.read_pending(pending.pending_path(reg))
        check(len(rows) == 1 and rows[0]["reason"] == "db-date-conflict",
              "the acquisition is queued with reason db-date-conflict")
        check(any(lvl == "WARN" and "no animal held the code" in m for lvl, m in logs),
              "the refusal and its reason are WARNed")

    logs.clear()
    subs, _c, _a = enrichment.build_enrichment(
        _case("tissue", "1123", 15), acq_id="ACQ-20240826-CELL-041", acq_date="20240826",
        lookup_fn=LOOKUP, dry_run=True, log=lambda m, level="INFO": logs.append((level, m)))
    check(subs[0]["facility_db_id"] == 13900, "tissue (ex vivo) resolves on its start date")
    check(any(lvl == "WARN" and "tissue-before-exit" in m for lvl, m in logs),
          "a soft signal is WARNed at ingest")


# ---- the subjects table -----------------------------------------------------

def test_subjects_table():
    print("registry_subjects.csv: facility_db_id, the legacy header, the conflict guard")
    with tempfile.TemporaryDirectory() as reg:
        path = subjects_table.subjects_path(reg)
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(subjects_table.LEGACY_SUBJECT_FIELDS)
            w.writerow(["49-AE-biomaGUNE-0525", "49", "0525", "Mus musculus", "C57BL/6J", "M",
                        "2026-03-05", "", "", "animal-facility-db", "T0", "T0"])
        t = subjects_table.read_subjects(path)
        check(t["49-AE-biomaGUNE-0525"]["facility_db_id"] == "", "a legacy-header table reads, column blank")
        s = subjects_table.upsert_subjects(reg, [{"facility_id": "49-AE-biomaGUNE-0525",
                                                 "facility_db_id": "18522",
                                                 "source": "animal-facility-db"}], now="T1")
        check(s["updated"] == 1, "a DB id fills the blank column")
        with open(path, encoding="utf-8") as f:
            check(f.readline().strip().split(",") == subjects_table.SUBJECT_FIELDS,
                  "the write upgrades the header to the current shape")
        s = subjects_table.upsert_subjects(reg, [{"facility_id": "49-AE-biomaGUNE-0525",
                                                 "facility_db_id": "19759", "sex": "F",
                                                 "date_of_birth": "2026-07-16",
                                                 "source": "animal-facility-db"}], now="T2")
        row = subjects_table.read_subjects(path)["49-AE-biomaGUNE-0525"]
        check(s["conflict"] == 1 and s["conflicts"] == [("49-AE-biomaGUNE-0525", "18522", "19759")],
              "a second animal under the same id is refused, and named")
        check(row["facility_db_id"] == "18522" and row["sex"] == "M" and row["last_updated"] == "T1",
              "the existing animal's row is untouched")
        block = dict(look("0525", 49, "2026-05-21").subject)
        check(subjects_table.row_from_subject_block(block)["facility_db_id"] == "18522",
              "row_from_subject_block carries the DB id")
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("facility_id,animal\nX,Y\n")
        try:
            subjects_table.read_subjects(path)
            check(False, "any other header still fails loud")
        except RuntimeError:
            check(True, "any other header still fails loud")


# ---- scratch NAS for the recovery / backfill / audit / relink tools ----------

PLACEHOLDER = {"facility_animal_id": "", "species": "", "strain": "", "sex": "unknown",
               "date_of_birth": None, "age_at_acquisition": "", "genotype": "",
               "weight_at_acquisition_g": None, "cohort_id": "", "procedures": [],
               "source": "pending-db"}


def _db_block(alias, code, day, in_vivo=True):
    res = look(alias, code, day, in_vivo)
    blk = enrichment._finalize_subject(dict(res.subject), day, "animal-facility-db")
    blk.pop("facility_db_id")  # production sidecars written before 2026-10-20 lack it
    return blk


SCRATCH = [
    # acq_id, sample_type, subject id, sidecar subject block, pending?
    ("ACQ-20260521-MRI-001", "organism", "49-AE-biomaGUNE-0525", None, True),
    ("ACQ-20221015-MRI-001", "organism", "45-AE-biomaGUNE-0721", None, True),
    ("ACQ-20240826-CELL-001", "tissue", "98-AE-biomaGUNE-1123", ("1123", 98, "2025-03-01"), False),
    ("ACQ-20250411-CELL-001", "tissue", "98-AE-biomaGUNE-1123", ("1123", 98, "2025-04-11"), False),
    ("ACQ-20230807-CT-006", "organism", "73-AE-biomaGUNE-1321", ("1321", 73, "2023-10-16"), False),
    ("ACQ-20260522-PET-001", "organism", "1-AE-biomaGUNE-1025", ("1025", 1, "2026-05-22"), False),
]


def build_nas(root):
    reg = os.path.join(root, "registries")
    os.makedirs(reg)
    fields = registry.REGISTRY_FIELDS
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=fields, lineterminator="\r\n")
    w.writeheader()
    prows, srows = [], {}
    for acq, st, fid, blk, pend in SCRATCH:
        rel = f"/raw/X/{acq}/"
        os.makedirs(os.path.join(root, "raw", "X", acq))
        block = dict(PLACEHOLDER, facility_animal_id=fid) if blk is None else _db_block(*blk)
        block["facility_animal_id"] = fid
        with open(os.path.join(root, "raw", "X", acq, "metadata.json"), "w", encoding="utf-8",
                  newline="\n") as f:
            json.dump({"acq_id": acq, "user_supplied": {"sample_type": st}, "subject": block}, f,
                      indent=2)
        row = {k: "" for k in fields}
        row.update(acq_id=acq, instrument=acq.split("-")[2], sample_type=st, subject_ids=fid,
                   canonical_path=rel, original_name=f"src/{acq}",
                   acquisition_datetime=f"{acq[4:8]}-{acq[8:10]}-{acq[10:12]}T10:00:00Z")
        w.writerow(row)
        if pend:
            prows.append({"acq_id": acq, "sidecar_path": rel + "metadata.json",
                          "facility_animal_id": fid, "reason": "db-miss", "logged_at": "T0",
                          "status": "pending", "recovered_at": ""})
        r = subjects_table.row_from_subject_block(block)
        if fid not in srows or r["source"] == "animal-facility-db":
            srows[fid] = r
    with open(os.path.join(reg, "registry_raw.csv"), "wb") as f:
        f.write(out.getvalue().encode("utf-8"))
    with open(pending.pending_path(reg), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=pending.PENDING_FIELDS)
        w.writeheader()
        w.writerows(prows)
    with open(subjects_table.subjects_path(reg), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=subjects_table.LEGACY_SUBJECT_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in srows.values():
            w.writerow(dict(r, first_registered="T0", last_updated="T0"))
    return reg


def test_recovery():
    print("recover_subject_metadata: the dated lookup, and facility_db_id filled")
    with tempfile.TemporaryDirectory() as tmp:
        reg = build_nas(tmp)
        s = rec.recover_all(reg, apply=True, lookup_fn=LOOKUP, log=quiet)
        check(s["counts"] == {"recovered": 2}, f"both pending rows recover (got {s['counts']})")
        md = json.load(open(os.path.join(tmp, "raw", "X", "ACQ-20260521-MRI-001", "metadata.json"),
                            encoding="utf-8"))
        b = md["subject"]
        check(b["facility_db_id"] == 18522 and b["date_of_birth"] == "2026-03-05" and b["sex"] == "M",
              "0525 #49 is filled from the scanned animal 18522, NOT the September 19759")
        check(list(b)[:3] == ["facility_animal_id", "facility_db_id", "species"],
              "the new field is placed in canonical order")
        md = json.load(open(os.path.join(tmp, "raw", "X", "ACQ-20221015-MRI-001", "metadata.json"),
                            encoding="utf-8"))
        check(md["subject"]["facility_db_id"] == 8500, "0721 #45 recovered through its transfer")

    print("recover_subject_metadata: a block naming another DB animal is refused")
    with tempfile.TemporaryDirectory() as tmp:
        reg = build_nas(tmp)
        side = os.path.join(tmp, "raw", "X", "ACQ-20260521-MRI-001", "metadata.json")
        md = json.load(open(side, encoding="utf-8"))
        md["subject"]["facility_db_id"] = 19759
        json.dump(md, open(side, "w", encoding="utf-8"), indent=2)
        r = rec.recover_one({"acq_id": "ACQ-20260521-MRI-001", "status": "pending",
                             "sidecar_path": "/raw/X/ACQ-20260521-MRI-001/metadata.json",
                             "facility_animal_id": "49-AE-biomaGUNE-0525"},
                            apply=True, lookup_fn=LOOKUP, log=quiet, nas_root=tmp)
        check(r["outcome"] == "error" and "refusing to mix" in r["detail"],
              "a sidecar already naming 19759 is not refilled from 18522")


def test_backfill_and_audit():
    print("backfill --with-db and the audit")
    with tempfile.TemporaryDirectory() as tmp:
        reg = build_nas(tmp)
        acqs = registry.read_registry(os.path.join(reg, "registry_raw.csv"))
        by_id, refused = backfill.resolve_link_db_ids(acqs, IDX)
        check(sorted((a, f) for a, f, _r, _d in refused) ==
              [("ACQ-20230807-CT-006", "73-AE-biomaGUNE-1321"),
               ("ACQ-20240826-CELL-001", "98-AE-biomaGUNE-1123")],
              "the two label errors are the refused links")
        check(dict(by_id["98-AE-biomaGUNE-1123"]) == {14671: ["ACQ-20250411-CELL-001"]},
              "98-1123's own slide names one animal")
        rows = [subjects_table.row_from_subject_block({"facility_animal_id": f, "source": s})
                for f, s in (("98-AE-biomaGUNE-1123", "animal-facility-db"),
                             ("49-AE-biomaGUNE-0525", "pending-db"))]
        split = backfill.apply_db_ids(rows, by_id)
        check(rows[0]["facility_db_id"] == "14671" and rows[1]["facility_db_id"] == "",
              "a DB-sourced row gets its id; a pending stub is left to the recovery")
        check(split == {}, "no id is split between animals here")
        two = {"49-AE-biomaGUNE-0525": {18522: ["A"], 19759: ["B"]}}
        r2 = [{"facility_id": "49-AE-biomaGUNE-0525", "source": "animal-facility-db"}]
        check(list(backfill.apply_db_ids(r2, two)) == ["49-AE-biomaGUNE-0525"]
              and not r2[0].get("facility_db_id"),
              "an id whose links name two animals is reported and left blank")

        cats = {(r["acq_id"], r["category"]) for r in audit.audit(reg, IDX)}
        check(cats == {("ACQ-20260521-MRI-001", "recoverable:reissued"),
                       ("ACQ-20221015-MRI-001", "recoverable:transfer"),
                       ("ACQ-20240826-CELL-001", "wrong:refused"),
                       ("ACQ-20250411-CELL-001", "unchanged"),
                       ("ACQ-20230807-CT-006", "wrong:refused"),
                       ("ACQ-20260522-PET-001", "unchanged")},
              f"each case lands in its audit category (got {sorted(cats)})")


def test_relink():
    print("relink_subjects: relink and unlink, bytes, idempotency, refusal")
    with tempfile.TemporaryDirectory() as tmp:
        reg = build_nas(tmp)
        raw = os.path.join(reg, "registry_raw.csv")
        before = open(raw, "rb").read()
        wl = [{"acq_id": "ACQ-20240826-CELL-001", "old_id": "98-AE-biomaGUNE-1123",
               "new_id": "98-AE-biomaGUNE-1321", "new_db_id": "11839", "evidence": "test"},
              {"acq_id": "ACQ-20230807-CT-006", "old_id": "73-AE-biomaGUNE-1321",
               "new_id": "", "new_db_id": "", "evidence": "test"},
              {"acq_id": "ACQ-20260521-MRI-001", "old_id": "49-AE-biomaGUNE-0525",
               "new_id": "1-AE-biomaGUNE-1025", "new_db_id": "18522", "evidence": "test"}]
        bad = [dict(wl[0], new_db_id="99999")]
        try:
            relink.plan(tmp, bad, lookup_fn=LOOKUP)
            check(False, "a worklist expecting another DB animal is refused")
        except RuntimeError:
            check(True, "a worklist expecting another DB animal is refused")
        try:
            relink.plan(tmp, [dict(wl[0], old_id="97-AE-biomaGUNE-1123")], lookup_fn=LOOKUP)
            check(False, "an old_id that production does not hold is refused")
        except RuntimeError:
            check(True, "an old_id that production does not hold is refused")
        check(open(raw, "rb").read() == before, "a refused plan writes nothing")

        items = relink.plan(tmp, wl, lookup_fn=LOOKUP)
        for i in items:
            relink.write_sidecar(i)
        n = relink.rewrite_registry_raw(raw, items)
        relink.flip_pending(reg, items, "T9")
        stats, dropped, kept = relink.update_subjects(reg, items, "T9")
        check(n == 3 and relink.verify(tmp, items) == [], "three rows rewritten and verified")
        after = open(raw, "rb").read()
        check(after.count(b"\r\n") == before.count(b"\r\n") and not after.startswith(b"\xef\xbb\xbf"),
              "registry_raw keeps CRLF and no BOM")
        changed = [(a, b) for a, b in zip(before.split(b"\r\n"), after.split(b"\r\n")) if a != b]
        check(len(changed) == 3 and all(a.replace(b"98-AE-biomaGUNE-1123", b"98-AE-biomaGUNE-1321")
                                        .replace(b"73-AE-biomaGUNE-1321", b"")
                                        .replace(b"49-AE-biomaGUNE-0525", b"1-AE-biomaGUNE-1025") == b
                                        for a, b in changed),
              "only the subject_ids values changed")
        md = json.load(open(os.path.join(tmp, "raw", "X", "ACQ-20230807-CT-006", "metadata.json"),
                            encoding="utf-8"))
        check(md["subject"]["facility_animal_id"] == "" and md["subject"]["source"] == "unknown",
              "an unlinked scan carries the unknown placeholder")
        md = json.load(open(os.path.join(tmp, "raw", "X", "ACQ-20240826-CELL-001", "metadata.json"),
                            encoding="utf-8"))
        check(md["subject"]["facility_db_id"] == 11839 and md["subject"]["date_of_birth"] == "2023-08-01",
              "a relinked slide carries the right animal's record")
        p = {r["acq_id"]: r for r in pending.read_pending(pending.pending_path(reg))}
        check(p["ACQ-20260521-MRI-001"]["status"] == "recovered", "its pending row is flipped")
        t = subjects_table.read_subjects(subjects_table.subjects_path(reg))
        check("49-AE-biomaGUNE-0525" not in t and dropped == ["49-AE-biomaGUNE-0525"],
              "the now-unreferenced pending stub row is dropped")
        check(t["98-AE-biomaGUNE-1321"]["facility_db_id"] == "11839"
              and "98-AE-biomaGUNE-1123" in t and "73-AE-biomaGUNE-1321" in t,
              "the new animal is upserted; DB rows still referenced stay")
        check(t["1-AE-biomaGUNE-1025"]["facility_db_id"] == "18522", "1025 #1 gains its DB id")
        again = relink.plan(tmp, wl, lookup_fn=LOOKUP)
        check(all(i["already"] for i in again), "a second run finds everything done")


def main():
    for fn in (test_dates, test_0525_transfer_and_reissue, test_0721_zero_change_date,
               test_label_errors_refused, test_birth_guard_and_tolerance, test_project_resolution,
               test_enrichment_dated, test_subjects_table, test_recovery, test_backfill_and_audit,
               test_relink):
        fn()
    print()
    if FAILED:
        print(f"FAILED ({len(FAILED)}):")
        for m in FAILED:
            print(f"  - {m}")
        sys.exit(1)
    print("ALL SUBJECT-LOOKUP-DATES CHECKS PASSED")


if __name__ == "__main__":
    main()
