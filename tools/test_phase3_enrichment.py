#!/usr/bin/env python3
"""test_phase3_enrichment.py — self-contained checks for the Phase 3 writer.

Exercises the non-blocking enrichment orchestrator (ingest/enrichment.py), the
condition/anatomy resolvers (ingest/resolver.py), and the pending-list writer
(ingest/pending.py) WITHOUT a live database — the animal-DB lookup is injected.

Run:  PYTHONPATH=tools python tools/test_phase3_enrichment.py
"""

import os
import sys
import tempfile

from ingest import enrichment, resolver, pending
import animal_db


FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok:   {msg}")


# A fake animal-DB lookup so the branchy logic is testable offline.
_DB_SUBJECT = {
    "facility_animal_id": "13-AE-biomaGUNE-0423",
    "species": "Mus musculus",
    "strain": "C57BL/6J",
    "sex": "M",
    "date_of_birth": "2025-07-31",
    "procedures": [{"type": "MRI", "date": "2025-10-27"}],
    "source": "animal-facility-db",
}


def make_lookup(status):
    def _fn(alias, code):
        if status == "found":
            return animal_db.LookupResult("found", subject=dict(_DB_SUBJECT),
                                          detail=_DB_SUBJECT["facility_animal_id"])
        if status == "not_found":
            return animal_db.LookupResult("not_found", reason="db-miss",
                                          detail="no such animal")
        return animal_db.LookupResult("unreachable", reason="no-credentials",
                                      detail="no creds")
    return _fn


def collecting_log():
    msgs = []
    def _log(m, level="INFO"):
        msgs.append(f"{level}: {m}")
    return msgs, _log


def base_case(sample_type, **extra):
    case = {
        "sample_type": sample_type,
        "discovered": {"animal_num": "13", "project_code": "0423"},
        "project_hint": "ae-biomegune-0423",
        "subject_from_db": True,
        "subject_lookup": {"project_alias": "${discovered.project_code}",
                           "animal_code": "${discovered.animal_num}"},
    }
    case.update(extra)
    return case


def build_one(*args, **kwargs):
    """Test shim: build_enrichment now returns a subjects LIST (NI-LIVE-08
    multi-animal). These single-subject checks want the primary block."""
    subjects, condition, anatomy = enrichment.build_enrichment(*args, **kwargs)
    return (subjects[0] if subjects else None), condition, anatomy


def test_resolvers():
    print("[resolvers]")
    # condition: unsupplied -> sentinels
    c = resolver.resolve_condition_block(None, {})
    check(c["is_control"] is None, "condition.is_control defaults to null")
    check(c["disease_model"] == "", "condition.disease_model sentinel ''")
    check(c["treatment"] is None, "condition.treatment sentinel null")
    check(c["timepoint_days"] is None, "condition.timepoint_days sentinel null")
    check(c["source"] == "unknown", "condition.source unknown when no block")
    # condition: supplied
    c2 = resolver.resolve_condition_block(
        {"is_control": True, "disease_model": "wild_type", "timepoint_days": 0}, {})
    check(c2["is_control"] is True, "condition.is_control True passes through")
    check(c2["timepoint_days"] == 0, "condition.timepoint_days 0 preserved (not null)")
    check(c2["source"] == "operator-entered", "condition.source operator-entered when block present")
    # anatomy
    a = resolver.resolve_anatomy_block(None, {})
    check(a["is_whole_body"] is None, "anatomy.is_whole_body defaults null")
    check(a["region"] is None, "anatomy.region sentinel null")
    check(a["additional_regions"] == [], "anatomy.additional_regions []")
    a2 = resolver.resolve_anatomy_block(
        {"is_whole_body": False,
         "region": {"label": "brain", "id": "UBERON:0000955"}}, {})
    check(a2["region"]["ontology"] == "UBERON", "anatomy.region.ontology defaults UBERON")
    check(a2["region"]["label"] == "brain", "anatomy.region.label preserved")
    # tri-state coercion
    check(resolver.to_tristate("true") is True, "to_tristate 'true' -> True")
    check(resolver.to_tristate("nope") is None, "to_tristate garbage -> None")
    # validators
    check(resolver.validate_condition_block({"bogus": 1}), "unknown condition key rejected")
    check(resolver.validate_anatomy_block({"region": "notadict"}), "bad anatomy.region rejected")
    check(resolver.validate_subject_from_db("yes"), "non-bool subject_from_db rejected")
    check(resolver.validate_condition_block({"is_control": True}) == [], "valid condition accepted")


def test_subject_found():
    print("[subject: DB found]")
    msgs, log = collecting_log()
    subj, cond, anat = build_one(
        base_case("organism"), acq_id="ACQ-X", acq_date="20251027",
        acq_dt_iso="2025-10-27T09:30:13Z", log=log, lookup_fn=make_lookup("found"))
    check(subj["source"] == "animal-facility-db", "subject.source animal-facility-db")
    check(subj["species"] == "Mus musculus", "subject.species from DB")
    expected_age = animal_db.age_iso8601("2025-07-31", "2025-10-27T09:30:13Z")
    check(subj["age_at_acquisition"] == expected_age,
          f"age_at_acquisition derived ({expected_age})")
    check(list(subj.keys()) == enrichment.SUBJECT_ORDER, "subject key order canonical")
    check(cond is not None and anat is not None, "organism gets condition + anatomy")


def test_subject_pending(reason):
    print(f"[subject: DB {reason} -> pending]")
    tmp = tempfile.mkdtemp()
    msgs, log = collecting_log()
    status = "not_found" if reason == "db-miss" else "unreachable"
    subj, cond, anat = build_one(
        base_case("organism"), acq_id="ACQ-Y", acq_date="20251027",
        acq_dt_iso="2025-10-27T09:30:13Z", canonical_path="/raw/DICOM/2025/2025-10/ACQ-Y/",
        registries_dir=tmp, dry_run=False, log=log, lookup_fn=make_lookup(status))
    check(subj["source"] == "pending-db", "subject.source pending-db on miss")
    check(subj["facility_animal_id"] == "13-AE-biomaGUNE-0423", "pending subject keeps composed id")
    rows = pending.read_pending(pending.pending_path(tmp))
    check(len(rows) == 1, "one pending row written")
    check(rows[0]["reason"] == reason, f"pending reason == {reason}")
    check(rows[0]["status"] == "pending", "pending status == pending")
    check(rows[0]["acq_id"] == "ACQ-Y", "pending acq_id correct")
    check(any("WARN" in m and "pending-db" in m for m in msgs), "WARN emitted for pending")
    # idempotency: a re-ingest must not duplicate
    build_one(
        base_case("organism"), acq_id="ACQ-Y", acq_date="20251027",
        acq_dt_iso="2025-10-27T09:30:13Z", canonical_path="/raw/DICOM/2025/2025-10/ACQ-Y/",
        registries_dir=tmp, dry_run=False, log=log, lookup_fn=make_lookup(status))
    rows2 = pending.read_pending(pending.pending_path(tmp))
    check(len(rows2) == 1, "pending list idempotent on acq_id (still one row)")


def test_dry_run_no_pending():
    print("[subject: dry-run writes no pending row]")
    tmp = tempfile.mkdtemp()
    _, log = collecting_log()
    build_one(
        base_case("organism"), acq_id="ACQ-Z", acq_date="20251027",
        registries_dir=tmp, dry_run=True, log=log, lookup_fn=make_lookup("not_found"))
    check(not os.path.exists(pending.pending_path(tmp)), "no pending file in dry-run")


def test_operator_override():
    print("[subject: operator override]")
    _, log = collecting_log()
    case = base_case("organism", subject={"species": "Rattus norvegicus",
                                           "strain": "Crl:WI(Han)", "sex": "F",
                                           "date_of_birth": "2025-01-01"})
    subj, _, _ = build_one(
        case, acq_id="ACQ-OP", acq_date="20251027",
        acq_dt_iso="2025-10-27T09:30:13Z", log=log, lookup_fn=make_lookup("found"))
    check(subj["source"] == "operator-entered", "operator subject overrides DB")
    check(subj["species"] == "Rattus norvegicus", "operator species used")
    check(subj["age_at_acquisition"], "operator subject age derived from DOB")


def test_tissue_and_cells():
    print("[sample_type gating]")
    _, log = collecting_log()
    subj, cond, anat = build_one(
        base_case("tissue"), acq_id="ACQ-T", acq_date="20251027",
        log=log, lookup_fn=make_lookup("found"))
    check(subj is not None and cond is not None, "tissue gets subject + condition")
    # 2026-06-09: anatomy: extended to ex-vivo tissue (region-only; is_whole_body
    # N/A). See 08_METADATA §4.6 / 09_MODALITIES.
    check(anat is not None, "tissue gets an anatomy block (region-only) — 2026-06-09")
    s2, c2, a2 = build_one(
        {"sample_type": "cells", "discovered": {}}, acq_id="ACQ-C",
        acq_date="20251027", log=log, lookup_fn=make_lookup("found"))
    # 2026-06-09: condition: written for cells too (control-vs-case applies to a
    # disease-model line vs a wild-type/untreated control); subject/anatomy stay off.
    check(s2 is None and c2 is not None and a2 is None,
          "cells gets condition only (no subject / no anatomy) — 2026-06-09")


def test_unknown_source():
    print("[subject: no source -> unknown]")
    _, log = collecting_log()
    case = base_case("organism")
    case["subject_from_db"] = False
    subj, _, _ = build_one(
        case, acq_id="ACQ-U", acq_date="20251027", log=log, lookup_fn=make_lookup("found"))
    check(subj["source"] == "unknown", "no flag + no override -> source unknown")


def test_review_fixes():
    """Regression guards for the Stage-4 adversarial-review findings."""
    print("[review fixes]")
    import recover_subject_metadata as rec

    # animal_db.age_iso8601 must tolerate non-ISO / vendor dates (return None,
    # never raise) — the root cause of the recover-walk crash + the operator
    # bad-DOB batch abort.
    for bad in ("<2025-09-15T14:30:00,500+0200>", "2025/10/29", "unknown", "", "x"):
        try:
            got = animal_db.age_iso8601(bad, "2025-10-16")
            check(got is None, f"age_iso8601 tolerates non-ISO dob {bad!r} -> None")
        except Exception as e:
            check(False, f"age_iso8601 raised on {bad!r}: {e}")
    check(animal_db.age_iso8601("2025-07-31", "2025-10-16T08:38:22,085") is not None,
          "age_iso8601 still parses comma-decimal ISO acquisition")

    # build_enrichment must NOT raise on an operator subject: with a bad DOB.
    _, log = collecting_log()
    case = base_case("organism", subject={"species": "Mus musculus",
                                           "date_of_birth": "unknown"})
    subj, _, _ = build_one(
        case, acq_id="ACQ-B", acq_date="20251016",
        acq_dt_iso="2025-10-16T00:00:00Z", log=log, lookup_fn=make_lookup("found"))
    check(subj["age_at_acquisition"] == "", "operator bad DOB -> age '' (non-blocking)")
    check(subj["source"] == "operator-entered", "operator override stays operator-entered")

    # operator sex: NA must keep the 'unknown' sentinel, not become ''.
    case2 = base_case("organism", subject={"species": "Mus musculus", "sex": "NA"})
    s2, _, _ = build_one(
        case2, acq_id="ACQ-S", acq_date="20251016", log=log, lookup_fn=make_lookup("found"))
    check(s2["sex"] == "unknown", "operator sex:NA -> sentinel 'unknown'")

    # recover: an operator-entered source that DISAGREES with the DB must be
    # KEPT (no false 'animal-facility-db' provenance) when no DB field is written.
    subject_op = {"species": "Rattus norvegicus", "strain": "Crl:WI(Han)",
                  "sex": "F", "date_of_birth": "2025-01-01",
                  "procedures": [{"type": "X", "date": "2025-02-02"}],
                  "source": "operator-entered", "age_at_acquisition": "P40W"}
    db_subj = {"species": "Mus musculus", "strain": "C57BL/6J", "sex": "M",
               "date_of_birth": "2024-04-04", "procedures": []}
    updates, skipped = rec.plan_subject_fill(subject_op, db_subj, "2025-10-16")
    check("source" not in updates, "recover: operator source kept (not flipped) when no DB field written")
    check(len(skipped) >= 3, "recover: real operator fields reported as skipped")

    # recover: a placeholder (pending-db) source IS flipped + fields filled.
    subject_ph = {"species": "", "strain": "", "sex": "unknown",
                  "date_of_birth": None, "procedures": [],
                  "source": "pending-db", "age_at_acquisition": ""}
    updates2, _ = rec.plan_subject_fill(subject_ph, db_subj, "2025-10-16")
    check(updates2.get("source") == "animal-facility-db", "recover: placeholder source flipped")
    check(updates2.get("species") == "Mus musculus", "recover: placeholder species filled from DB")


def main():
    test_resolvers()
    test_subject_found()
    test_subject_pending("db-miss")
    test_subject_pending("no-credentials")
    test_dry_run_no_pending()
    test_operator_override()
    test_tissue_and_cells()
    test_unknown_source()
    test_review_fixes()
    print()
    if FAILS:
        print(f"FAILED ({len(FAILS)}):")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print("ALL PHASE 3 ENRICHMENT CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
