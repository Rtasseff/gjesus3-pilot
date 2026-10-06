#!/usr/bin/env python3
"""a2_db_0118.py -- protocol 0118 in the animal DB (SELECT only): which animals, when, which procedures,
and where the drive's 0118 material and production's AE-biomaGUNE-0118 acquisitions fall among them.

Why: Ryan ruled 0118 = two projects (rats hipoxia / Monocrotalina, 2026-09-30); AE-biomaGUNE-0118
(PROJ-0060) already exists, described as Monocrotalina, holding Lucia's Cell Observer histology. Whether
that histology is the Monocrotalina or the hypoxia cohort decides what each option would mean.
Output: a2\\db_0118_animals.csv (one row per animal: birth, species, sex, procedures by type and date).
"""
import collections
import re

import a2_common as C
import animal_db  # noqa: E402

RAT_RE = re.compile(r"_r(\d{2,3})_")


def main():
    C.stdout_utf8()
    conn = animal_db.get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT p.id, p.project_code, p.projectAlias, p.start_date, p.end_date "
                    "FROM projects p WHERE p.project_code LIKE %s OR p.projectAlias = %s",
                    ("%AE-biomaGUNE-0118%", "0118"))
        projs = cur.fetchall()
    C.say(f"DB projects for 0118: {[(p['project_code'], str(p['start_date']), str(p['end_date'])) for p in projs]}")
    pids = [p["id"] for p in projs]
    with conn.cursor() as cur:
        cur.execute("SELECT a.id, a.animal_code, a.date_of_birth, a.id_project FROM animals a WHERE a.id_project IN (%s)"
                    % ",".join(["%s"] * len(pids)), pids)
        animals = cur.fetchall()
        ids = [a["id"] for a in animals]
        procs = collections.defaultdict(list)
        if ids:
            cur.execute("SELECT ap.id_animal, ap.date, p.type AS type FROM animal_procedures ap "
                        "JOIN procedures p ON p.id = ap.id_procedure WHERE ap.id_animal IN (%s)"
                        % ",".join(["%s"] * len(ids)), ids)
            for r in cur.fetchall():
                procs[r["id_animal"]].append((str(r["date"]), r["type"] or ""))
    conn.close()
    rows = []
    for a in sorted(animals, key=lambda a: int(a["animal_code"] or 0)):
        ps = sorted(procs.get(a["id"], []))
        rows.append({"animal": a["animal_code"], "born": str(a["date_of_birth"]),
                     "procedures": "; ".join(f"{d} {t}" for d, t in ps)[:400]})
    C.wcsv(C.out_path("db_0118_animals.csv"), ["animal", "born", "procedures"], rows)
    # drive-3 0118 rats (study names) and their scan dates
    files = list(C.it(C.out_path("files.csv")))
    rats = collections.defaultdict(set)
    for f in files:
        if f["relpath"].startswith("MRI\\Proyecto 0118") or "2DG RATAS" in f["relpath"]:
            for m in re.finditer(r"(\d{8})_\d{6}_jrc\d{6}_([rm])(\d{2,3})", f["relpath"]):
                rats[(m.group(2) + m.group(3))].add(m.group(1))
    C.say("drive-3 0118 MRI subjects (study-name subject token: scan dates):")
    for k in sorted(rats, key=lambda k: int(k[1:])):
        C.say(f"   {k}: {sorted(rats[k])}")
    # cross-protocol check: for every (subject number, scan date) in a 0118-related study name, which
    # protocols log ANY procedure on that animal number on that date? (the engine's decisive test)
    pairs = sorted({(int(k[1:]), d) for k, ds in rats.items() for d in ds})
    for extra in ("Comparasion expiration vs inspiraiton\\Rata MCT",):
        for f in files:
            if extra in f["relpath"]:
                for m in re.finditer(r"(\d{8})_\d{6}_jrc\d{6}_([rm])(\d{2,3})", f["relpath"]):
                    pairs.append((int(m.group(3)), m.group(1)))
    pairs = sorted(set(pairs))
    conn = animal_db.get_connection()
    xrows = []
    with conn.cursor() as cur:
        for num, d in pairs:
            iso = f"{d[:4]}-{d[4:6]}-{d[6:]}"
            cur.execute("SELECT pr.project_code, pr.projectAlias, p.type AS type FROM animal_procedures ap "
                        "JOIN animals a ON a.id = ap.id_animal JOIN projects pr ON pr.id = a.id_project "
                        "JOIN procedures p ON p.id = ap.id_procedure "
                        "WHERE a.animal_code = %s AND ap.date = %s", (num, iso))
            hits = sorted({f"{r['project_code']}:{r['type']}" for r in cur.fetchall()})
            xrows.append({"subject": num, "scan_date": iso, "protocols_with_a_procedure_that_day": "; ".join(hits)})
    conn.close()
    C.wcsv(C.out_path("db_0118_scan_dates.csv"), ["subject", "scan_date", "protocols_with_a_procedure_that_day"], xrows)
    only = sum(1 for x in xrows if x["protocols_with_a_procedure_that_day"]
               and all("0118" in h for h in x["protocols_with_a_procedure_that_day"].split("; ")))
    C.say(f"cross-protocol check: {len(xrows)} (subject, scan date) pairs; {only} logged by 0118 only; "
          f"{sum(1 for x in xrows if not x['protocols_with_a_procedure_that_day'])} by no protocol; the rest by several")
    for x in xrows:
        if not (x["protocols_with_a_procedure_that_day"] and all("0118" in h for h in x["protocols_with_a_procedure_that_day"].split("; "))):
            C.say(f"   {x}")
    by_code = {str(r["animal"]): r for r in rows}
    C.say(f"DB animals of 0118: {len(rows)}; births {min(r['born'] for r in rows)}..{max(r['born'] for r in rows)}")
    for code in sorted({int(k[1:]) for k in rats} | {131, 132, 136, 137, 144, 145}):
        r = by_code.get(str(code))
        C.say(f"   animal {code}: " + (f"born {r['born']}; {r['procedures'][:220]}" if r else "NOT in 0118"))


if __name__ == "__main__":
    main()
