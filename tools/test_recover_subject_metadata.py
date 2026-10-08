#!/usr/bin/env python3
"""test_recover_subject_metadata.py -- the superuser subject recovery, against a scratch NAS.

Pins two things found on 2026-10-08, the first time it ran after an on-box NI sync:
  * the pending list stores sidecar_path NAS-RELATIVE (`/raw/.../metadata.json`, as
    ingest Step 8.4 writes it). The tool used the path as-is, so from Windows every
    DB hit failed "sidecar not found" and stayed pending. It must resolve under the
    NAS root (and still accept an absolute path that exists).
  * `--acq-ids` / `only=`: rows outside the set are neither looked up nor touched.
Plus the contract it already had: dry-run writes nothing; --apply fills only
placeholder subject fields, verifies, and flips the row to `recovered`.

Run:  python tools/test_recover_subject_metadata.py
"""
import csv
import hashlib
import json
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import animal_db  # noqa: E402
import recover_subject_metadata as rec  # noqa: E402
from ingest import pending  # noqa: E402

FAILED = []


def check(cond, msg):
    print(f"  {'ok' if cond else 'FAIL'}:   {msg}")
    if not cond:
        FAILED.append(msg)


PLACEHOLDER = {"facility_animal_id": "", "species": "", "strain": "", "sex": "unknown",
               "date_of_birth": None, "age_at_acquisition": "", "genotype": "",
               "weight_at_acquisition_g": None, "cohort_id": "", "procedures": [],
               "source": "pending-db"}
DB = {"species": "Mus musculus", "strain": "C57BL/6J", "sex": "F",
      "date_of_birth": "2025-01-10", "procedures": [], "source": "animal-facility-db"}


def lookup(alias, code):
    return animal_db.LookupResult("found", subject=dict(DB, facility_animal_id=f"{code}-AE-biomaGUNE-{alias}"),
                                  detail="fake")


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def build(nas):
    reg = os.path.join(nas, "registries")
    os.makedirs(reg)
    rows = []
    for acq, animal in (("ACQ-20250304-CT-001", "128"), ("ACQ-20250304-CT-002", "129")):
        rel = f"/raw/DICOM/2025/2025-03/{acq}/metadata.json"
        p = os.path.join(nas, *rel.strip("/").split("/"))
        os.makedirs(os.path.dirname(p))
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"acq_id": acq, "discovered": {"acq_datetime_full": "20250304145758"},
                       "subject": dict(PLACEHOLDER, facility_animal_id=f"{animal}-AE-biomaGUNE-0522")},
                      f, indent=2)
        rows.append({"acq_id": acq, "sidecar_path": rel,
                     "facility_animal_id": f"{animal}-AE-biomaGUNE-0522", "reason": "no-credentials",
                     "logged_at": "2026-10-08T17:40:00Z", "status": "pending", "recovered_at": ""})
    with open(pending.pending_path(reg), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=pending.PENDING_FIELDS)
        w.writeheader()
        w.writerows(rows)
    return reg


def multi_animal():
    """2026-10-08: a two-mouse NI scan's pending row names the LAST animal queued (12),
    while the primary `subject` block is animal 11. Each block must get ITS OWN record."""
    print("multi-animal scan: every block gets its own animal's record")
    records = {11: dict(DB, sex="M", date_of_birth="2026-03-05"),
               12: dict(DB, sex="F", date_of_birth="2026-02-01")}

    def per_animal(alias, code):
        return animal_db.LookupResult("found", subject=dict(
            records[int(code)], facility_animal_id=f"{int(code)}-AE-biomaGUNE-{alias}"), detail="fake")

    with tempfile.TemporaryDirectory() as tmp:
        nas = os.path.join(tmp, "nas")
        reg = os.path.join(nas, "registries")
        os.makedirs(reg)
        acq = "ACQ-20260526-CT-007"
        rel = f"/raw/DICOM/2026/2026-05/{acq}/metadata.json"
        side = os.path.join(nas, *rel.strip("/").split("/"))
        os.makedirs(os.path.dirname(side))
        ph = lambda n: dict(PLACEHOLDER, facility_animal_id=f"{n}-AE-biomaGUNE-1025")  # noqa: E731
        with open(side, "w", encoding="utf-8") as f:
            json.dump({"acq_id": acq, "discovered": {"acq_datetime_full": "20260526120000"},
                       "subject": ph(11), "subjects": [ph(11), ph(12)]}, f, indent=2)
        with open(pending.pending_path(reg), "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=pending.PENDING_FIELDS)
            w.writeheader()
            w.writerow({"acq_id": acq, "sidecar_path": rel, "facility_animal_id": "12-AE-biomaGUNE-1025",
                        "reason": "no-credentials", "logged_at": "2026-10-08T17:40:00Z",
                        "status": "pending", "recovered_at": ""})
        quiet = lambda *a_, **k: None  # noqa: E731
        s = rec.recover_all(reg, apply=True, lookup_fn=per_animal, log=quiet)
        d = json.load(open(side, encoding="utf-8"))
        check(s["counts"] == {"recovered": 1}, f"the row recovers (got {s['counts']})")
        check((d["subject"]["sex"], d["subject"]["date_of_birth"]) == ("M", "2026-03-05"),
              "the primary block (animal 11) has animal 11's record, not the row's animal 12")
        check([(b["facility_animal_id"], b["sex"]) for b in d["subjects"]] ==
              [("11-AE-biomaGUNE-1025", "M"), ("12-AE-biomaGUNE-1025", "F")],
              "subjects[] entries each carry their own animal's record")

        # A DB answer for a different animal than the block's is refused, nothing written.
        with open(side, "w", encoding="utf-8") as f:
            json.dump({"acq_id": acq, "subject": ph(11), "subjects": [ph(11), ph(12)]}, f)
        before = sha(side)
        wrong = lambda alias, code: animal_db.LookupResult(  # noqa: E731
            "found", subject=dict(DB, facility_animal_id="99-AE-biomaGUNE-1025"), detail="fake")
        r = rec.recover_one({"acq_id": acq, "sidecar_path": rel, "facility_animal_id": "11-AE-biomaGUNE-1025",
                             "status": "pending"}, apply=True, lookup_fn=wrong, log=quiet, nas_root=nas)
        check(r["outcome"] == "error" and sha(side) == before,
              "a record for another animal is refused and the sidecar is untouched")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        nas = os.path.join(tmp, "nas")
        reg = build(nas)
        a = os.path.join(nas, "raw", "DICOM", "2025", "2025-03", "ACQ-20250304-CT-001", "metadata.json")
        b = os.path.join(nas, "raw", "DICOM", "2025", "2025-03", "ACQ-20250304-CT-002", "metadata.json")
        quiet = lambda *a_, **k: None  # noqa: E731

        print("sidecar_path is NAS-relative and resolves under the NAS root")
        check(rec.resolve_sidecar_path("/raw/x/metadata.json", nas) ==
              os.path.join(nas, "raw", "x", "metadata.json"), "a /raw/... path joins under the NAS root")
        check(rec.resolve_sidecar_path(a, nas) == a, "an absolute path that exists is used unchanged")

        print("dry run: would recover both, writes nothing")
        before = (sha(a), sha(b), sha(pending.pending_path(reg)))
        s = rec.recover_all(reg, apply=False, lookup_fn=lookup, log=quiet)
        check(s["counts"] == {"would-recover": 2}, f"both rows would recover (got {s['counts']})")
        check((sha(a), sha(b), sha(pending.pending_path(reg))) == before, "dry run changed no file")

        print("--acq-ids scope: only the listed acquisition is touched")
        s = rec.recover_all(reg, apply=True, lookup_fn=lookup, log=quiet, only={"ACQ-20250304-CT-001"})
        check(s["counts"] == {"recovered": 1}, f"one row processed and recovered (got {s['counts']})")
        subj = json.load(open(a, encoding="utf-8"))["subject"]
        check(subj["species"] == "Mus musculus" and subj["source"] == "animal-facility-db",
              "its sidecar got the DB values")
        check(sha(b) == before[1], "the other acquisition's sidecar is untouched")
        rows = {r["acq_id"]: r for r in pending.read_pending(pending.pending_path(reg))}
        check(rows["ACQ-20250304-CT-001"]["status"] == "recovered"
              and rows["ACQ-20250304-CT-002"]["status"] == "pending",
              "the pending list: recovered for the listed row, still pending for the other")
        s = rec.recover_all(reg, apply=True, lookup_fn=lookup, log=quiet, only={"ACQ-20250304-CT-001"})
        check(s["counts"] == {"already-recovered": 1}, "a re-run is a no-op (idempotent)")

    multi_animal()

    if FAILED:
        print(f"\n{len(FAILED)} CHECK(S) FAILED")
        sys.exit(1)
    print("\nALL RECOVER-SUBJECT-METADATA CHECKS PASSED")


if __name__ == "__main__":
    main()
