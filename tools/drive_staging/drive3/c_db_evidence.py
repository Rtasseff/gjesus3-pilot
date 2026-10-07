#!/usr/bin/env python3
"""c_db_evidence.py -- stream C (drive 3): facility-DB evidence for the planned (C) files whose engine
reason is "nested claims disagree ... animal N is found in BOTH <near> and <outer>, and the DB dates do not
separate them". SELECTs only (tools/animal_db.py; the credentials stay in its .my.cnf, never printed).

For each such file it looks the animal up in BOTH protocols and records sex, date of birth and the first
terminal procedure (organ sampling / perfusion), next to what the file's own folders say (e.g. `Female`).
This is EVIDENCE for a proposed reading the coordinator may accept or not; it changes nothing in the plan.

    python tools/drive_staging/drive3/c_db_evidence.py      # -> <plan>\\db_evidence_c.csv + a summary
"""
import collections
import csv
import io
import os
import re
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.dirname(HERE)
TOOLS = os.path.dirname(DS)
sys.path.insert(0, DS)
sys.path.insert(0, TOOLS)
import ingest_plan as P  # noqa: E402
import animal_db  # noqa: E402

P.use_profile("drive3_2026-10")
RX = re.compile(r"nearest (\d{4}) \(CONFIRMED\) vs outer (\d{4}); animal (\d+) is found in BOTH")
TERMINAL = re.compile(r"organ sampling|perfusion", re.I)


def first_terminal(procs):
    ds = sorted(str(p.get("date") or "")[:10] for p in procs or []
                if TERMINAL.search(str(p.get("type") or "")) and str(p.get("date") or "")[:4] > "1990")
    return ds[0] if ds else ""


def main():
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")
    exp = list(P.rcsv(os.path.join(P.OUT, "expected.csv")))
    want = {e["relpath"]: e for e in exp if e["verdict"] == "C"}
    fc = {}
    with io.open(os.path.join(P.CODES, "file_claims.csv"), encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["relpath"] in want:
                fc[r["relpath"]] = r
    conn = animal_db.get_connection()
    cache, rows = {}, []
    try:
        for rel, e in sorted(want.items()):
            m = RX.search(fc[rel]["conflict"])
            if not m:
                continue
            near, outer, animal = m.group(1), m.group(2), int(m.group(3))
            rec = {"relpath": rel, "acquisition_date": e["acquisition_datetime"][:10], "near": near, "outer": outer,
                   "animal": animal, "folder_says": ";".join(sorted({w for w in ("Female", "Male", "female", "male")
                                                                       if re.search(rf"(?<![A-Za-z]){w}(?![a-z])", rel)}))}
            for tag, code in (("near", near), ("outer", outer)):
                k = (code, animal)
                if k not in cache:
                    res = animal_db.lookup(code, animal, conn=conn, use_cache=False)
                    if res.status == "unreachable":
                        raise SystemExit(f"animal DB unreachable: {res.detail}")
                    s = res.subject or {}
                    cache[k] = {"status": res.status, "sex": s.get("sex", ""), "dob": str(s.get("date_of_birth") or ""),
                                "terminal": first_terminal(s.get("procedures"))}
                for f_, v in cache[k].items():
                    rec[f"{tag}_{f_}"] = v
            rows.append(rec)
    finally:
        conn.close()
    cols = ["relpath", "acquisition_date", "folder_says", "near", "outer", "animal",
            "near_status", "near_sex", "near_dob", "near_terminal", "outer_status", "outer_sex", "outer_dob",
            "outer_terminal"]
    P.wcsv(os.path.join(P.OUT, "db_evidence_c.csv"), cols, rows)
    pat = collections.Counter((r["near"], r["outer"], r["folder_says"], r["near_sex"], r["outer_sex"]) for r in rows)
    print(f"{len(rows)} (C) files with a both-protocols animal; (near, outer, folder says, near sex, outer sex):")
    for k, n in pat.most_common():
        print(f"  {n:4d}  {k}")
    before = collections.Counter(
        (r["near"], "near-sampled-by-file-date" if r["near_terminal"] and r["near_terminal"] <= r["acquisition_date"] else "-",
         "outer-sampled-by-file-date" if r["outer_terminal"] and r["outer_terminal"] <= r["acquisition_date"] else "-")
        for r in rows)
    print("terminal procedure on or before the file date (the drives 1+2 DB-date reading):")
    for k, n in before.most_common():
        print(f"  {n:4d}  {k}")
    print(f"distinct animals: {len({(r['near'], r['animal']) for r in rows})}")


if __name__ == "__main__":
    main()
