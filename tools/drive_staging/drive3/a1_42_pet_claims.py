"""A1 step 4c: the project claim of every PET/CT reconstruction production lacks, checked in the facility DB.

For each distinct reconstruction that is NEW or only in the S:\\gnuclear snapshot (a1_40): the claimed
protocol = the nearest folder in its drive path holding a DB-valid protocol code; the animal = the
nearest folder below it that is a bare 1-3 digit number or m<n>/r<n> (the Molecubes researchers'
layout, e.g. PET\\0320\\14\\, PET\\0619\\0619 2DG\\Machos\\124\\); the date = the file's own timestamp.
The DB (SELECT only) says whether the animal is in the protocol and what it logs within 3 days.
Verdicts as in a1_24 (a check confirms a claim, never overrules it).

Writes a1\\pet_claims.csv.

    python a1_42_pet_claims.py
"""
import collections
import datetime as dt
import json
import os
import re
import sys

from a1_common import CACHE, OUT, TOOLS, out_path, read_csv_dicts, write_csv

sys.path.insert(0, TOOLS)
import animal_db  # noqa: E402
import ni_gnuclear_discover as g  # noqa: E402

ANIMAL_DIR = re.compile(r"^(?:[mMrR])?(\d{1,3})$")


def main():
    conn = animal_db.get_connection()
    dbc_p = os.path.join(CACHE, "db_lookups.json")
    dbc = json.load(open(dbc_p, encoding="utf-8")) if os.path.exists(dbc_p) else {}
    try:
        valid = g.valid_protocol_codes(conn)
        pet = read_csv_dicts(os.path.join(OUT, "pet_files.csv"))
        seen, rows = set(), []
        for r in pet:
            if r["kind"] != "molecubes-recon" or r["first_copy"] != "Y" or r["coverage"].startswith("in production"):
                continue
            if r["sha256"] in seen:
                continue
            seen.add(r["sha256"])
            segs = r["relpath"].split("\\")[:-1]
            code, ci = "", -1
            for i in range(len(segs) - 1, -1, -1):
                for c in re.findall(r"(?<!\d)(\d{4})(?!\d)", segs[i]):
                    if c in valid:
                        code, ci = c, i
                        break
                if code:
                    break
            animal = ""
            for s in reversed(segs[ci + 1:] if ci >= 0 else segs):
                m = ANIMAL_DIR.match(s.strip())
                if m:
                    animal = m.group(1)
                    break
            ts = dt.datetime.strptime(r["ts"], "%Y%m%d%H%M%S").date()
            verdict, ev = "", ""
            if not code:
                verdict = "C (no protocol code in the path)"
            elif not animal:
                verdict = "claim, protocol valid (no animal folder)"
            else:
                k = f"{code}|{int(animal)}"
                if k not in dbc:
                    res = animal_db.lookup(code, int(animal), conn=conn, use_cache=False)
                    if res.status == "unreachable":
                        raise SystemExit("DB unreachable")
                    dbc[k] = {"status": res.status, "procedures": (res.subject or {}).get("procedures", []),
                              "species": (res.subject or {}).get("species", ""),
                              "dob": (res.subject or {}).get("date_of_birth", "")}
                d = dbc[k]
                near = []
                for pr in d["procedures"]:
                    try:
                        pd_ = dt.date.fromisoformat(pr["date"][:10])
                    except (TypeError, ValueError):
                        continue
                    if pd_.year >= 1990 and abs((pd_ - ts).days) <= 3:
                        near.append(f"{pr['type']}@{pr['date'][:10]}")
                if d["status"] != "found":
                    verdict = "C (animal not in claimed protocol)"
                elif near:
                    verdict = "CONFIRMED"
                else:
                    verdict = "CLAIM-KEPT (animal in protocol, nothing logged within 3 days)"
                ev = f"{code}/{animal}: {d['status']}" + (f", {d['species']}" if d.get("species") else "") + \
                     (f", logs {', '.join(near)}" if near else "")
            rows.append({"relpath": r["relpath"], "ni_key": r["ni_key"], "coverage": r["coverage"], "date": str(ts),
                         "size": r["size"], "claim_code": code, "animal": animal, "verdict": verdict, "db_evidence": ev})
    finally:
        conn.close()
        with open(out_path("_cache", "db_lookups.json"), "w", encoding="utf-8") as f:
            json.dump(dbc, f, indent=0)
    write_csv("pet_claims.csv", rows, list(rows[0].keys()))
    c = collections.Counter((r["coverage"][:24], r["claim_code"], r["verdict"].split(" (")[0]) for r in rows)
    for k, v in sorted(c.items()):
        print(v, k)


if __name__ == "__main__":
    main()
