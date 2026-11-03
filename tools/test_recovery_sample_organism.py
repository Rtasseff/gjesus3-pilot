#!/usr/bin/env python3
"""test_recovery_sample_organism.py -- a subject resolved after ingest fills registry_raw.sample_organism.

Found 2026-11-03 by the XNAT pilot's guard: the recovery and relink tools filled the sidecar and
the subjects table but never this column, so 338 recovered rows named an animal and no species.
Pins: only blank cells are filled, never an existing value; nothing else in the file moves, byte
for byte (mixed line endings, a quoted cell); dry run writes nothing; a second run is a no-op;
--organism-only needs no DB; scoping; only a DB-filled block counts.

Run:  python tools/test_recovery_sample_organism.py
"""
import csv
import hashlib
import io
import json
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import animal_db  # noqa: E402
import recover_subject_metadata as rec  # noqa: E402
import relink_subjects as relink  # noqa: E402
from ingest import pending, registry  # noqa: E402

FAILED = []
MOUSE, RAT = "Mus musculus", "Rattus norvegicus"


def check(cond, msg):
    print(f"  {'ok' if cond else 'FAIL'}:   {msg}")
    if not cond:
        FAILED.append(msg)


def quiet(*_a, **_k):
    pass


def block(fid, species="", source="pending-db"):
    return {"facility_animal_id": fid, "facility_db_id": None, "species": species, "strain": "", "sex": "unknown",
            "date_of_birth": None, "age_at_acquisition": "", "genotype": "", "weight_at_acquisition_g": None,
            "cohort_id": "", "procedures": [], "source": source}


def line(acq, subject, organism, notes="plain", end="\r\n"):
    row = {f: "" for f in registry.REGISTRY_FIELDS}
    row.update(acq_id=acq, canonical_path=f"/raw/DICOM/2025/2025-03/{acq}/", subject_ids=subject, sample_organism=organism, notes=notes)
    buf = io.StringIO()
    csv.writer(buf, lineterminator="").writerow([row[f] for f in registry.REGISTRY_FIELDS])
    return (buf.getvalue() + end).encode("utf-8")


def build(nas):
    reg = os.path.join(nas, "registries")
    os.makedirs(reg)
    spec = [  # acq, subject, organism in the registry, pending status, the sidecar's block, line end
        ("ACQ-20250304-CT-001", "1-AE-biomaGUNE-0525", "", "pending", block("1-AE-biomaGUNE-0525"), "\r\n"),
        ("ACQ-20250304-CT-002", "2-AE-biomaGUNE-0525", "", "recovered", block("2-AE-biomaGUNE-0525", MOUSE, "animal-facility-db"), "\n"),
        ("ACQ-20250304-CT-003", "3-AE-biomaGUNE-0525", RAT, "recovered", block("3-AE-biomaGUNE-0525", MOUSE, "animal-facility-db"), "\r\n"),
        ("ACQ-20250304-CT-004", "4-AE-biomaGUNE-0525", "", "pending", block("4-AE-biomaGUNE-0525"), "\r\n"),
        ("ACQ-20250304-CT-005", "5-AE-biomaGUNE-0525", "", "recovered", block("5-AE-biomaGUNE-0525", MOUSE, "operator"), "\r\n"),
    ]
    raw = b",".join(f.encode() for f in registry.REGISTRY_FIELDS) + b"\r\n"
    rows = []
    for acq, subject, organism, status, side, end in spec:
        raw += line(acq, subject, organism, notes="a, quoted note", end=end)
        d = os.path.join(nas, "raw", "DICOM", "2025", "2025-03", acq)
        os.makedirs(d)
        with open(os.path.join(d, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump({"acq_id": acq, "subject": side}, f, indent=2)
        rows.append({"acq_id": acq, "sidecar_path": f"/raw/DICOM/2025/2025-03/{acq}/metadata.json", "facility_animal_id": subject,
                     "project_alias": "", "animal_code": "", "reason": "no-credentials", "queued_datetime": "T0", "status": status, "recovered_at": ""})
    with open(os.path.join(reg, "registry_raw.csv"), "wb") as f:
        f.write(raw)
    path = pending.pending_path(reg)
    fields = pending.PENDING_FIELDS if hasattr(pending, "PENDING_FIELDS") else list(rows[0])
    pending._write_all(path, [{k: r.get(k, "") for k in fields} for r in rows])
    return reg


def cells(reg):
    return {r["acq_id"]: r["sample_organism"] for r in registry.read_registry(os.path.join(reg, "registry_raw.csv"))}


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def lookup(alias, code, **_dated):
    if str(code) == "4":
        return animal_db.LookupResult("not_found", reason="db-miss", detail="no such animal")
    return animal_db.LookupResult("found", subject={"facility_animal_id": f"{code}-AE-biomaGUNE-{alias}", "facility_db_id": 100 + int(code),
                                                    "species": MOUSE, "strain": "C57BL/6J", "sex": "F", "date_of_birth": "2024-01-10",
                                                    "procedures": [], "source": "animal-facility-db"}, detail="fake")


def no_db(*_a, **_k):
    raise AssertionError("--organism-only must not look anything up")


def test_field_edit():
    print("registry.fill_sample_organism: bytes, blank only")
    with tempfile.TemporaryDirectory() as tmp:
        reg = build(tmp)
        path = os.path.join(reg, "registry_raw.csv")
        before = open(path, "rb").read()
        filled, kept = registry.fill_sample_organism(path, {"ACQ-20250304-CT-002": MOUSE, "ACQ-20250304-CT-003": MOUSE, "ACQ-NOT-THERE": MOUSE})
        after = open(path, "rb").read()
        check(filled == ["ACQ-20250304-CT-002"], "the blank row is filled")
        check(kept == {"ACQ-20250304-CT-003": RAT}, "an existing species is kept and reported, never overwritten")
        b, a = before.split(b"\n"), after.split(b"\n")
        diff = [i for i in range(len(b)) if b[i] != a[i]]
        check(len(b) == len(a) and diff == [2], "exactly one line changed")
        check(b"\r" not in a[2] and a[1].endswith(b"\r") and a[3].endswith(b"\r"), "mixed line endings kept")
        check(b'"a, quoted note"' in a[2], "another column's quoting kept")
        row = next(csv.DictReader(io.StringIO(after.decode("utf-8"))))
        check(row["subject_ids"] == "1-AE-biomaGUNE-0525", "the file still parses")
        check(registry.fill_sample_organism(path, {"ACQ-20250304-CT-002": MOUSE})[0] == [] and open(path, "rb").read() == after, "a second run changes nothing")
        try:
            registry.fill_sample_organism(path, {"ACQ-20250304-CT-001": 'Mus, "musculus"'})
            check(False, "a value that would need quoting is refused")
        except RuntimeError:
            check(True, "a value that would need quoting is refused")


def test_recovery():
    print("recover_subject_metadata: fills the column for recovered rows")
    with tempfile.TemporaryDirectory() as tmp:
        reg = build(tmp)
        path = os.path.join(reg, "registry_raw.csv")
        before = sha(path)
        s = rec.recover_all(reg, apply=False, lookup_fn=lookup, log=quiet)
        check(sha(path) == before, "a dry run writes nothing")
        check(s["organism"]["would_fill"] == 1, "a dry run counts the old recovered row")
        s = rec.recover_all(reg, apply=True, lookup_fn=lookup, log=quiet)
        c = cells(reg)
        check(s["counts"].get("recovered") == 1, "one row recovered by this run")
        check(c["ACQ-20250304-CT-001"] == MOUSE, "a row recovered in this run gets its species")
        check(c["ACQ-20250304-CT-002"] == MOUSE, "an older recovered row catches up")
        check(c["ACQ-20250304-CT-003"] == RAT, "an existing species is kept")
        check(c["ACQ-20250304-CT-004"] == "", "a row still pending stays blank")
        check(c["ACQ-20250304-CT-005"] == "", "a species not from the DB is not projected")
        check(any("no DB-filled species" in p for p in s["organism"]["problems"]), "and that row is reported")
        once = sha(path)
        rec.recover_all(reg, apply=True, lookup_fn=lookup, log=quiet)
        check(sha(path) == once, "a second run changes nothing")


def test_organism_only():
    print("--organism-only: no DB, no sidecars, scoped")
    with tempfile.TemporaryDirectory() as tmp:
        reg = build(tmp)
        side = os.path.join(tmp, "raw", "DICOM", "2025", "2025-03", "ACQ-20250304-CT-001", "metadata.json")
        before = sha(side)
        s = rec.recover_all(reg, apply=True, lookup_fn=no_db, log=quiet, organism_only=True, only={"ACQ-20250304-CT-003"})
        check(s["organism"]["filled"] == 0, "a row outside the scope, or already filled, is left alone")
        s = rec.recover_all(reg, apply=True, lookup_fn=no_db, log=quiet, organism_only=True)
        c = cells(reg)
        check(s["organism"]["filled"] == 1 and c["ACQ-20250304-CT-002"] == MOUSE, "the old recovered row is filled, without the DB")
        check(c["ACQ-20250304-CT-001"] == "" and sha(side) == before, "a pending row and its sidecar are untouched")


def test_multi_animal():
    print("species_of: several animals, as build_row")
    side = {"subject": block("1-AE-biomaGUNE-0525"), "subjects": [block("1-AE-biomaGUNE-0525", MOUSE, "animal-facility-db"), block("2-AE-biomaGUNE-0525", RAT, "animal-facility-db")]}
    check(rec.species_of(side) == MOUSE, "the first animal's species")
    check(rec.species_of({"subject": block("x")}) == "", "a placeholder gives nothing")


def test_relink():
    print("relink_subjects: a relinked row gets the new animal's species; an unlink changes nothing")
    items = [{"acq_id": "A1", "already": False, "new_id": "1-AE-biomaGUNE-1025", "block": {"species": MOUSE}},
             {"acq_id": "A2", "already": False, "new_id": "", "block": {"species": ""}},
             {"acq_id": "A3", "already": True, "new_id": "2-AE-biomaGUNE-1025"}]
    check(relink.organism_updates(items) == {"A1": MOUSE}, "only the rows relinked now")


if __name__ == "__main__":
    test_field_edit()
    test_recovery()
    test_organism_only()
    test_multi_animal()
    test_relink()
    print()
    if FAILED:
        print(f"{len(FAILED)} FAILED: {FAILED}")
        sys.exit(1)
    print("all passed")
