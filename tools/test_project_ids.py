#!/usr/bin/env python3
"""test_project_ids.py — the `;`-separated `registry_raw.project_id` cell.

Covers ingest/project_ids.py itself AND the two readers whose failure mode is
SILENT and expensive:

  * generate_index._write_per_project — an acquisition in two projects must
    appear in BOTH per-project indexes. Grouping on the joined cell put it in
    neither, i.e. adding an acquisition to a second project quietly deleted it
    from the index of the project it was already in.
  * find_acq.build_records — the project join must resolve per id, not on the
    whole cell (a two-project row used to lose its folder / name / owner).

Run:  python tools/test_project_ids.py
"""
import csv
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import find_acq                          # noqa: E402
import generate_index                    # noqa: E402
from ingest import project_ids as pids   # noqa: E402
from ingest import registry              # noqa: E402

FAILED = []


def check(cond, msg):
    print(f"  {'ok' if cond else 'FAIL'}:   {msg}")
    if not cond:
        FAILED.append(msg)


# --------------------------------------------------------------- unit: the cell

def test_cell():
    print("\n-- the project_id cell --")
    check(pids.split_project_ids("") == [], "blank -> []")
    check(pids.split_project_ids(None) == [], "None -> []")
    check(pids.split_project_ids("PROJ-0001") == ["PROJ-0001"],
          "single value -> length-1 list")
    check(pids.split_project_ids("PROJ-0001;PROJ-0007")
          == ["PROJ-0001", "PROJ-0007"], "two values -> both, in order")
    check(pids.split_project_ids("PROJ-0001; PROJ-0007 ")
          == ["PROJ-0001", "PROJ-0007"], "tolerates Excel-style spacing")
    check(pids.split_project_ids("PROJ-0001;PROJ-0001") == ["PROJ-0001"],
          "duplicates collapse")

    cell, changed = pids.add_project_id("", "PROJ-0001")
    check((cell, changed) == ("PROJ-0001", True), "blank + id -> bare id")
    cell, changed = pids.add_project_id("PROJ-0001", "PROJ-0007")
    check((cell, changed) == ("PROJ-0001;PROJ-0007", True),
          "existing id stays FIRST (original association is primary)")
    cell, changed = pids.add_project_id("PROJ-0001;PROJ-0007", "PROJ-0001")
    check((cell, changed) == ("PROJ-0001;PROJ-0007", False),
          "re-adding is idempotent — never PROJ-0001;PROJ-0001")

    check(pids.has_project_id("PROJ-0001;PROJ-0007", "PROJ-0007"),
          "membership finds the second id")
    check(not pids.has_project_id("PROJ-0011", "PROJ-001"),
          "membership is exact, not substring (PROJ-001 is not in PROJ-0011)")
    cell, changed = pids.remove_project_id("PROJ-0001;PROJ-0007", "PROJ-0001")
    check((cell, changed) == ("PROJ-0007", True), "remove drops just that id")


# ----------------------------------------------------------- fixture: a mini NAS

PROJECT_COLS = ["project_id", "name", "description", "owner", "start_date",
                "status", "last_activity", "folder_location", "notes"]


def build_nas(root):
    reg_dir = os.path.join(root, "registries")
    os.makedirs(reg_dir)
    with open(os.path.join(reg_dir, "registry_projects.csv"), "w",
              encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(PROJECT_COLS)
        w.writerow(["PROJ-0001", "alpha", "Alpha study", "AA", "2026-01-01",
                    "active", "2026-01-01", "/projects/alpha/", ""])
        w.writerow(["PROJ-0007", "beta", "Beta study", "BB", "2026-02-01",
                    "active", "2026-02-01", "/projects/beta/", ""])
        w.writerow(["PROJ-0009", "gone", "Closed study", "CC", "2020-01-01",
                    "closed", "2020-01-01", "/projects/gone/", ""])
    for name in ("alpha", "beta"):
        os.makedirs(os.path.join(root, "projects", name))

    rows = [
        # in ONE project
        {"acq_id": "ACQ-20260101-ZWSI-001", "project_id": "PROJ-0001",
         "canonical_path": "/raw/MICROSCOPY/2026/2026-01/ACQ-20260101-ZWSI-001/",
         "instrument": "ZWSI", "acquisition_datetime": "2026-01-01T09:00:00"},
        # in TWO projects — the case this whole change exists for
        {"acq_id": "ACQ-20260102-ZWSI-002", "project_id": "PROJ-0001;PROJ-0007",
         "canonical_path": "/raw/MICROSCOPY/2026/2026-01/ACQ-20260102-ZWSI-002/",
         "instrument": "ZWSI", "acquisition_datetime": "2026-01-02T09:00:00"},
        # in the OTHER project only
        {"acq_id": "ACQ-20260103-CELL-001", "project_id": "PROJ-0007",
         "canonical_path": "/raw/MICROSCOPY/2026/2026-01/ACQ-20260103-CELL-001/",
         "instrument": "CELL", "acquisition_datetime": "2026-01-03T09:00:00"},
        # closed project -> no folder to write into
        {"acq_id": "ACQ-20260104-CELL-002", "project_id": "PROJ-0009",
         "canonical_path": "/raw/MICROSCOPY/2026/2026-01/ACQ-20260104-CELL-002/",
         "instrument": "CELL", "acquisition_datetime": "2026-01-04T09:00:00"},
    ]
    reg_path = os.path.join(reg_dir, "registry_raw.csv")
    with open(reg_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=registry.REGISTRY_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in registry.REGISTRY_FIELDS})
    return root


# ------------------------------------------------------------------ the readers

def test_find_acq(nas):
    print("\n-- find_acq.build_records --")
    records, proj_idx = find_acq.build_records(nas)
    by_id = {r["acq_id"]: r for r in records}

    shared = by_id["ACQ-20260102-ZWSI-002"]
    check(shared["_project_ids"] == ["PROJ-0001", "PROJ-0007"],
          "two-project row -> both ids on the record")
    check(shared["_project_folder"] == "/projects/alpha/",
          "folder resolves to the FIRST project (was '' before the fix)")
    check(shared["_project_name"] == "alpha;beta",
          "names carry the whole list")
    check(shared["_project_owner"] == "AA;BB", "owners carry the whole list")

    single = by_id["ACQ-20260101-ZWSI-001"]
    check(single["_project_name"] == "alpha", "single-project row is unchanged")

    check(find_acq.matches(shared, project="PROJ-0007"),
          "--project matches the SECOND id of a shared row")
    check(find_acq.matches(shared, project="beta"),
          "--project matches the second project's NAME")
    check(not find_acq.matches(single, project="PROJ-0007"),
          "--project does not match a row that isn't in it")
    check(not find_acq.matches(shared, project="0001;PROJ"),
          "--project cannot match ACROSS the separator")
    return records, proj_idx


def test_per_project_index(nas, records, proj_idx, out):
    print("\n-- generate_index per-project grouping --")
    written = generate_index._write_per_project(
        records, proj_idx, r"\\GJESUS3\gjesus3\gjesus3-data", nas, out)
    check(sorted(written) == ["PROJ-0001", "PROJ-0007"],
          "both open projects written; the closed one skipped")

    def acqs_in(pid):
        path = os.path.join(out, pid, "index.html")
        if not os.path.isfile(path):
            return set()
        html = open(path, encoding="utf-8").read()
        return {a for a in ("ACQ-20260101-ZWSI-001", "ACQ-20260102-ZWSI-002",
                            "ACQ-20260103-CELL-001") if a in html}

    a, b = acqs_in("PROJ-0001"), acqs_in("PROJ-0007")
    # THE regression this guards: before the fix the shared acq was grouped
    # under the literal "PROJ-0001;PROJ-0007" and appeared in NEITHER index.
    check("ACQ-20260102-ZWSI-002" in a,
          "shared acq appears in the FIRST project's index")
    check("ACQ-20260102-ZWSI-002" in b,
          "shared acq appears in the SECOND project's index")
    check(a == {"ACQ-20260101-ZWSI-001", "ACQ-20260102-ZWSI-002"},
          "first project's index holds exactly its own two")
    check(b == {"ACQ-20260102-ZWSI-002", "ACQ-20260103-CELL-001"},
          "second project's index holds exactly its own two")
    check(not os.path.isfile(os.path.join(out, "PROJ-0009", "index.html")),
          "closed project gets no index (its folder was deleted at close-out)")

    # Targeted mode (the path the GUI uses after an import).
    hit = generate_index._write_per_project(
        records, proj_idx, r"\\GJESUS3\gjesus3", nas, out, only={"beta"})
    check(hit == ["PROJ-0007"], "targeted refresh by NAME resolves one project")
    hit = generate_index._write_per_project(
        records, proj_idx, r"\\GJESUS3\gjesus3", nas, out, only={"PROJ-0001"})
    check(hit == ["PROJ-0001"], "targeted refresh by id resolves one project")


def main():
    test_cell()
    tmp = tempfile.mkdtemp(prefix="gj3_projids_")
    try:
        nas = build_nas(os.path.join(tmp, "nas"))
        records, proj_idx = test_find_acq(nas)
        test_per_project_index(nas, records, proj_idx, os.path.join(tmp, "out"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAILED:
        print(f"{len(FAILED)} CHECK(S) FAILED")
        for m in FAILED:
            print(f"  - {m}")
        return 1
    print("ALL PROJECT-ID CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
