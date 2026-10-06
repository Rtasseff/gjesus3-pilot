"""Stream N: targeted facility-DB probes (SELECT only) for the acquisitions whose header and folder
disagree. Never prints credentials; uses tools/animal_db.get_connection().

    python petct_06a_db_probe.py
"""
import os
import sys

sys.dont_write_bytecode = True
WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))      # the repository root (tools/drive_staging/drive3/<this>)
sys.path.insert(0, os.path.join(WT, "tools"))
import animal_db  # noqa: E402

PAIRS = [("0619", 173), ("1019", 173), ("0320", 29), ("0320", 30), ("0619", 201), ("1422", 1),
         ("1123", 22), ("1123", 23)]
DATES = [("2021-10-19", "2021-10-19"), ("2022-02-17", "2022-02-17"), ("2022-05-18", "2022-05-18")]


def main():
    conn = animal_db.get_connection()
    try:
        for alias, code in PAIRS:
            res = animal_db.lookup(alias, code, conn=conn, use_cache=False)
            if res.status != "found":
                print(f"{alias}/{code}: {res.status}")
                continue
            s = res.subject
            procs = [f"{p['type']}@{p['date']}" for p in s.get("procedures", [])]
            print(f"{alias}/{code}: found {s['facility_animal_id']} {s['species']} {s['sex']} dob {s['date_of_birth']}")
            print("     procedures:", "; ".join(procs))
        # who logged a PET on these days (protocol, animal, procedure)
        with conn.cursor() as cur:
            for d0, d1 in DATES:
                cur.execute(
                    "SELECT pr.projectAlias AS alias, pr.project_code AS code, a.animal_code AS animal, "
                    "       p.type AS ptype, ap.date AS d "
                    "FROM animal_procedures ap "
                    "JOIN procedures p ON p.id = ap.id_procedure "
                    "JOIN animals a ON a.id = ap.id_animal "
                    "JOIN projects pr ON pr.id = a.id_project "
                    "WHERE ap.date BETWEEN %s AND %s AND p.type LIKE %s "
                    "ORDER BY pr.projectAlias, a.animal_code", (d0, d1, "%PET%"))
                rows = cur.fetchall()
                print(f"\nPET procedures logged {d0}..{d1}: {len(rows)}")
                for r in rows:
                    print(f"   {r['alias'] or r['code']}/{r['animal']} {r['ptype']} {r['d']}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
