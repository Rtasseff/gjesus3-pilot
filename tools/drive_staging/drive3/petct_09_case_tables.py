"""Stream N, step 8: write the two case tables from out\\plan_202.csv into the worktree.

  tools/configs/drive3_petct/cases_drive3_petct_snapshot.csv   the 100, keyed on the acquisition key
  tools/configs/drive3_petct/cases_drive3_petct_drive.csv      the 102

Every column becomes discovered.<column> for its acquisition (ingest/config.py load_case_table), after
the path grammar has run, so each row states the decided values explicitly: project (alias, used for
the facility-DB lookup), project_name, subject (-> sample_id, session_id, link name), animal_codes,
sample_type, researcher_folder, note; the drive table also carries the original drive path.
"""
import csv
import os
import sys

sys.dont_write_bytecode = True
OUT = r"D:\projects\gjesus3\drive3_streams\petct\out"
WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))      # the repository root (tools/drive_staging/drive3/<this>)
DEST = os.path.join(WT, "tools", "configs", "drive3_petct")
COLS = ["original_name", "project", "project_name", "subject", "animal_codes", "sample_type",
        "researcher_folder", "note"]


def main():
    plan = list(csv.DictReader(open(os.path.join(OUT, "plan_202.csv"), encoding="utf-8")))
    os.makedirs(DEST, exist_ok=True)
    for source, name, extra in (("snapshot", "cases_drive3_petct_snapshot.csv", []),
                                ("drive", "cases_drive3_petct_drive.csv", ["drive_relpath"])):
        rows = []
        for p in sorted((p for p in plan if p["source"] == source), key=lambda p: p["acq_key"]):
            assert p["sample_type"] in ("organism", "phantom"), p
            if p["sample_type"] == "organism":
                assert p["project"] and p["project_name"] == f"AE-biomaGUNE-{p['project']}", p
                assert p["animal_codes"].isdigit() and p["subject"], p
            else:
                assert not p["project"] and not p["project_name"] and not p["animal_codes"], p
            r = {"original_name": p["acq_key"], **{c: p[c] for c in COLS[1:]}}
            for c in extra:
                r[c] = p[c]
            rows.append(r)
        with open(os.path.join(DEST, name), "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLS + extra, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        print(f"{name}: {len(rows)} rows")


if __name__ == "__main__":
    main()
