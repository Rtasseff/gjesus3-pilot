#!/usr/bin/env python3
"""a2_db_evidence.py -- animal-DB evidence (SELECT only, tools/animal_db.py) for the files that
`Pili y Mili\\Proyecto 0522  PAH\\IFs and histologies` holds and 0522 cannot own: whose animals ARE they?

This is EVIDENCE for Ryan, not a reading: Ryan's rule is that a DB check confirms a claim but never
overrules it, and these files sit in a 0522 folder. Output: a2\\db_evidence_0522_ifs.csv.
"""
import collections
import os
import re

import a2_common as C
import animal_db  # noqa: E402  (read-only; credentials stay in ~/.my.cnf)

PREFIX = "Pili y Mili\\Proyecto 0522  PAH\\IFs and histologies\\"
CANDIDATES = ["0522", "0619", "1019", "0424"]


def main():
    C.stdout_utf8()
    fclaims = {r["relpath"]: r for r in C.it(os.path.join(C.OUT, "claims", "file_claims.csv"))}
    man = {r["relpath"]: r for r in C.load_manifest() if r["relpath"].startswith(PREFIX)}
    conn = animal_db.get_connection()
    nums = collections.defaultdict(list)
    for rel, r in man.items():
        tok = fclaims.get(rel, {}).get("animal_token", "")
        m = re.search(r"(\d+)", tok)
        if m:
            nums[int(m.group(1))].append(r["mtime"][:10])
    rows = []
    for n in sorted(nums):
        rec = {"animal": n, "files": len(nums[n]), "file_dates": f"{min(nums[n])}..{max(nums[n])}"}
        for code in CANDIDATES:
            res = animal_db.lookup(code, n, conn=conn, use_cache=False)
            if res.status == "unreachable":
                raise SystemExit(f"animal DB unreachable: {res.detail}")
            if res.status == "found":
                s = res.subject
                procs = [p for p in s["procedures"] if re.search(r"(?i)organ sampling|perfusion", p["type"] or "")]
                rec[code] = (f"born {s['date_of_birth']}; {s['species']} {s['sex']}"
                             + (f"; terminal {procs[0]['date']}" if procs else ""))
            else:
                rec[code] = res.status
        rows.append(rec)
    conn.close()
    C.wcsv(C.out_path("db_evidence_0522_ifs.csv"), ["animal", "files", "file_dates"] + CANDIDATES, rows)
    for r in rows:
        C.say(f"ID {r['animal']:4d} files {r['files']:3d} {r['file_dates']} | " +
              " | ".join(f"{c}: {r[c]}" for c in CANDIDATES))


if __name__ == "__main__":
    main()
