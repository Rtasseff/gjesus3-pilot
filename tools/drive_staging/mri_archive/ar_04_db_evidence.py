"""Stream AR, step 4: the facility-DB evidence for every new animal study (tiers A, A2), SELECT only.

    python ar_04_db_evidence.py

Per study (the census pull plan; the scan day is the study name's YYYYMMDD, the session start), the animal number is
read from the study name (m<n> / r<n>; anything else is "no animal number"). The facility DB is asked, in ONE query per
animal number, for every protocol that holds an animal of that number: its protocol code and alias, species, birth
date, and every logged procedure with its date. Per study:

  CLAIMED studies (a 4-digit code in the name; the census' protocol column):
    CONFIRMED      the claimed protocol holds the animal and logs a procedure within 3 days of the scan
    CLAIM-KEPT     the claimed protocol holds the animal, nothing logged within 3 days
    CONTRADICTED   the claimed protocol's animal was born after the scan, or a perfusion / organ sampling is logged
                   before the scan day
    NOT-IN-DB      the claimed protocol does not hold the animal (or the protocol is not in the DB): no subject id
  NO-CODE studies (no code in the name; census "No code in the name"):
    DB-RESOLVED    exactly ONE protocol holds an animal of that number, alive on the scan day (born before it, no
                   perfusion / organ sampling before it), with an MRI procedure (MRI, MRI 7T, MRI 11.7T, fMRI) logged
                   within 3 days of the scan (A1's window) -- and that protocol is a gjesus3 project
    UNRESOLVED     zero or several such protocols; or the one protocol is not a gjesus3 project: no project
The animal number: m<n> / r<n> in the name, or the project-first "<code>_<n>" at its end (jrc221121_0721_74).
Procedure dates before 2000 are the DB's placeholder (1970-01-01) and are ignored. Never prints credentials. Writes out\\db_evidence.csv and out\\db_evidence.txt.
"""
import collections
import datetime as dt
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ar_common as C  # noqa: E402

sys.path.insert(0, os.path.join(C.WT, "tools"))
import animal_db  # noqa: E402

ANIMAL = re.compile(r"^[mr]\d{1,4}$")
PROJFIRST = re.compile(r"_(\d{4})_(\d{1,3})_\d+_\d+$")
MRI_TYPES = {"MRI", "MRI 7T", "MRI 11.7T", "fMRI"}
DEATH = {"Perfusion", "Organ sampling", "RT administration + perfusion", "Organ sampling + Gamma counter"}
Q = ("SELECT pj.project_code, pj.projectAlias, a.id AS aid, a.animal_code, a.date_of_birth, s.type AS species, "
     "pr.type AS ptype, ap.date AS pdate "
     "FROM animals a JOIN projects pj ON pj.id = a.id_project JOIN specie s ON s.id = a.id_specie "
     "LEFT JOIN animal_procedures ap ON ap.id_animal = a.id LEFT JOIN procedures pr ON pr.id = ap.id_procedure "
     "WHERE a.animal_code = %s")


def code_of(project_code):
    m = re.match(r"^AE-biomaGUNE-(\d{4})", project_code or "")
    return m.group(1) if m else ""


def d(x):
    if x is None or x == "":
        return None
    if isinstance(x, dt.datetime):
        v = x.date()
    elif isinstance(x, dt.date):
        v = x
    else:
        try:
            v = dt.date.fromisoformat(str(x)[:10])
        except ValueError:
            return None
    return v if v.year >= 2000 else None      # 1970-01-01 is the DB's placeholder


def candidates(conn, n, cache):
    if n not in cache:
        with conn.cursor() as cur:
            cur.execute(Q, (int(n),))
            rows = cur.fetchall()
        by = collections.OrderedDict()
        for r in rows:
            k = (r["project_code"], r["aid"])
            c = by.setdefault(k, {"project_code": r["project_code"], "alias": r["projectAlias"] or "",
                                  "code": code_of(r["project_code"]), "species": r["species"],
                                  "dob": d(r["date_of_birth"]), "procs": []})
            if r["ptype"]:
                c["procs"].append((d(r["pdate"]), r["ptype"]))
        cache[n] = list(by.values())
    return cache[n]


def judge(c, day):
    near = sorted({t for pd, t in c["procs"] if pd and abs((pd - day).days) <= 3})
    mri = sorted({f"{pd}:{t}" for pd, t in c["procs"] if pd and t in MRI_TYPES and abs((pd - day).days) <= 3})
    dead = sorted({f"{pd}:{t}" for pd, t in c["procs"] if pd and t in DEATH and pd < day})
    born_after = bool(c["dob"] and c["dob"] > day)
    return near, mri, dead, born_after


def main():
    plan = C.pull_plan()
    projs = {p["name"]: p for p in C.live_projects()}
    gj3 = {n.split("-")[-1]: n for n in projs if re.match(r"^AE-biomaGUNE-\d{4}$", n)}
    conn = animal_db.get_connection()
    cache, out = {}, []
    for study, p in sorted(plan.items()):
        if p["tier"] not in ("A", "A2"):
            continue
        animal = p["animal"].lower() if ANIMAL.match(p["animal"].lower()) else ""
        pf = PROJFIRST.search(study)
        if not animal and p["protocol"] and pf and pf.group(1) == p["protocol"]:
            animal = f"m{int(pf.group(2))}"       # project-first "<code>_<n>": the species is the DB's
        day = dt.date(int(study[:4]), int(study[4:6]), int(study[6:8]))
        claim = p["protocol"]
        rec = {"study": study, "tier": p["tier"], "day": day.isoformat(), "animal": animal, "claim": claim,
               "claim_is_gj3_project": "Y" if claim in gj3 else "N", "verdict": "", "decided_code": "",
               "evidence": "", "candidates": ""}
        if not animal:
            rec["verdict"] = "NO-ANIMAL-NUMBER"
            out.append(rec)
            continue
        cands = candidates(conn, animal[1:], cache)
        desc = []
        for c in cands:
            near, mri, dead, ba = judge(c, day)
            desc.append(f"{c['code'] or c['project_code']}[{c['species']},dob {c['dob']},"
                        f"{'BORN-AFTER,' if ba else ''}{'DEAD:' + dead[0] + ',' if dead else ''}"
                        f"near {'+'.join(near) or 'none'}{',MRI ' + mri[0] if mri else ''}]")
        rec["candidates"] = " ".join(desc)
        if claim:
            mine = [c for c in cands if c["code"] == claim]
            if not mine:
                rec["verdict"] = "NOT-IN-DB"
            else:
                c = mine[0]
                near, mri, dead, ba = judge(c, day)
                if ba or dead:
                    rec["verdict"] = "CONTRADICTED"
                    rec["evidence"] = f"born {c['dob']}; {dead[:1]}"
                elif near:
                    rec["verdict"] = "CONFIRMED"
                    rec["evidence"] = "+".join(near)
                else:
                    rec["verdict"] = "CLAIM-KEPT"
                rec["decided_code"] = claim if rec["verdict"] in ("CONFIRMED", "CLAIM-KEPT") else ""
        else:
            ok = []
            for c in cands:
                near, mri, dead, ba = judge(c, day)
                if mri and not dead and not ba:
                    ok.append((c, mri))
            codes = sorted({c["code"] or c["project_code"] for c, _ in ok})
            if len(codes) == 1 and codes[0] in gj3:
                rec["verdict"] = "DB-RESOLVED"
                rec["decided_code"] = codes[0]
                rec["evidence"] = f"{ok[0][0]['species']}; {ok[0][1][0]}"
            else:
                rec["verdict"] = "UNRESOLVED"
                rec["evidence"] = f"protocols with this animal alive and an MRI logged within 3 days: {codes or 'none'}"
        out.append(rec)
    conn.close()
    C.write_csv(C.out("db_evidence.csv"), out)
    L = [f"studies (tiers A, A2): {len(out)}; distinct animal numbers asked: {len(cache)}",
         f"claimed: {dict(collections.Counter(r['verdict'] for r in out if r['claim']))}",
         f"claimed, per code: {dict(sorted(collections.Counter((r['claim'], r['verdict']) for r in out if r['claim']).items()))}",
         f"no code: {dict(collections.Counter(r['verdict'] for r in out if not r['claim']))}",
         f"no code, resolved to: {dict(collections.Counter(r['decided_code'] for r in out if not r['claim'] and r['decided_code']))}"]
    open(C.out("db_evidence.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
