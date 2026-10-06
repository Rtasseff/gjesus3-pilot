"""A1 step 2e: for every drive study with an exam production lacks, the project it would go to
under the decided claim rules (HANDOFF section 3), with the facility-DB evidence. Proposes; decides nothing.

Claims read from the drive itself: the nearest folder above the study that names a protocol code
(`Proyecto 0619`, `PET\\0522` ...), and any 4-digit code slot in the study name. The animal is read
from the study name (`m78`, `r157`, `191` before a code); `r` = rat, `m` = mouse (hub brief 7.1).

The facility DB (tools/animal_db.py lookup(); SELECT only) is asked, for every (claimed code,
animal), whether the animal exists in that protocol and which procedures it logs within 3 days of
the study date (the in-vivo rule of tools/drive_staging/project_claims.py).

Verdict, per the rulings of 2026-09-29 (a check confirms a claim, never overrules it):
  CONFIRMED          the claimed protocol holds the animal and logs a procedure within 3 days
  CLAIM-KEPT         the claimed protocol holds the animal, nothing logged within 3 days
  CONFIRMED-NAME     the folder and the study name claim different codes; the DB's dates pick
                     exactly one (the in-vivo rule) -> that one
  C                  no claimed protocol holds the animal, or the claims conflict undecided, or the
                     DB CONTRADICTS the claim (the animal was born after the scan, or a perfusion /
                     organ sampling is logged before it). For a contradicted claim, the codes in the
                     sibling study names of the same folder are looked up too, as evidence only
  B?                 no animal in the name (a phantom / test): a new Project-NNNN or blank; for Ryan
Writes a1\\mri_missing_studies.csv (one row per study with any exam not in production).

    python a1_24_mri_projects.py
"""
import collections
import datetime as dt
import json
import os
import re
import sys

from a1_common import TOOLS, cache_load, out_path, read_csv_dicts, snapshot, write_csv, CACHE

sys.path.insert(0, TOOLS)
import animal_db  # noqa: E402  (SELECT-only helper)

ANIMAL_TOK = re.compile(r"^(?P<sp>[mMrR])(?P<n>\d{1,4})[A-Za-z]*$")
CODE_TOK = re.compile(r"^\d{4}$")
WINDOW = 3


def name_tokens(study):
    m = re.match(r"^\d{8}_\d{6}_(.*)$", study)
    rest = m.group(1) if m else study
    rest = re.sub(r"^[A-Za-z]+_?\d{6,8}_", "", rest)
    return rest.split("_")


def parse_animal_codes(study):
    toks = name_tokens(study)
    animal, sp, codes = "", "", []
    for i, t in enumerate(toks):
        a = ANIMAL_TOK.match(t)
        if a and not animal:
            animal, sp = a.group("n"), {"m": "mouse", "r": "rat"}[a.group("sp").lower()]
        elif CODE_TOK.match(t):
            codes.append(t)
        elif re.fullmatch(r"\d{1,3}", t) and not animal and i + 1 < len(toks) and CODE_TOK.match(toks[i + 1]):
            animal, sp = t, "(number only)"
    return animal, sp, codes


def main():
    rows = cache_load("mri_exam_rows")
    studies = collections.defaultdict(list)
    for r in rows:
        studies[r["study"]].append(r)
    missing = {st: rs for st, rs in studies.items() if any(r["class"] in ("c", "d", "e") for r in rs)}
    projects = read_csv_dicts(snapshot("registry_projects.csv"))
    by_name = {p["name"]: p for p in projects}
    cache_p = os.path.join(CACHE, "db_lookups.json")
    dbc = json.load(open(cache_p, encoding="utf-8")) if os.path.exists(cache_p) else {}
    if not animal_db.credentials_available():
        raise SystemExit("animal DB credentials not available")
    conn = animal_db.get_connection()
    out = []
    try:
        for st, rs in sorted(missing.items()):
            r0 = rs[0]
            animal, sp, name_codes = parse_animal_codes(st)
            near = [c for c in r0["path_claim_nearest"].split(";") if c]
            cands = list(dict.fromkeys(near + name_codes))
            sdate = dt.date(int(r0["study_date"][:4]), int(r0["study_date"][4:6]), int(r0["study_date"][6:8]))
            ev = {}
            for code in cands:
                if not animal:
                    continue
                k = f"{code}|{int(animal)}"
                if k not in dbc:
                    res = animal_db.lookup(code, int(animal), conn=conn, use_cache=False)
                    if res.status == "unreachable":
                        raise SystemExit(f"DB unreachable: {res.detail}")
                    dbc[k] = {"status": res.status,
                              "procedures": (res.subject or {}).get("procedures", []),
                              "species": (res.subject or {}).get("species", ""),
                              "dob": (res.subject or {}).get("date_of_birth", "")}
                d = dbc[k]
                near_p = []
                for p in d["procedures"]:
                    try:
                        pd_ = dt.date.fromisoformat(p["date"][:10])
                    except (TypeError, ValueError):
                        continue
                    if pd_.year >= 1990 and abs((pd_ - sdate).days) <= WINDOW:
                        near_p.append(f"{p['type']}@{p['date'][:10]}")
                ev[code] = {"found": d["status"] == "found", "near": near_p, "species": d["species"],
                            "dob": d["dob"]}
            # verdict
            n_ex_new = sum(1 for r in rs if r["class"] in ("c", "d", "e"))
            verdict, code_dec, why = "", "", ""
            if not animal:
                low = st.lower()
                verdict = "B?" if any(w in low for w in ("phantom", "fantom", "test", "prueba")) else "C"
                why = "no animal id in the study name"
            else:
                found_near = [c for c in near if ev.get(c, {}).get("found")]
                dated = [c for c in cands if ev.get(c, {}).get("near")]
                if near and len(set(near)) == 1 and ev.get(near[0], {}).get("found"):
                    c = near[0]
                    if ev[c]["near"]:
                        verdict, code_dec = "CONFIRMED", c
                        why = f"folder claim {c}; DB: animal {animal} in {c}, logs {', '.join(ev[c]['near'])}"
                    else:
                        verdict, code_dec = "CLAIM-KEPT", c
                        why = f"folder claim {c}; DB: animal {animal} in {c}, nothing logged within {WINDOW} days"
                    others = [x for x in name_codes if x != c]
                    if others:
                        why += f"; the study name carries {','.join(others)}"
                        if any(ev.get(x, {}).get("near") for x in others) and not ev[c]["near"]:
                            verdict, code_dec = "CONFIRMED-NAME", next(x for x in others if ev.get(x, {}).get("near"))
                            why += f" -> the DB logs the animal under {code_dec} that day (in-vivo rule)"
                        elif any(ev.get(x, {}).get("near") for x in others) and ev[c]["near"]:
                            verdict, code_dec = "C", ""
                            why += " -> both protocols log the animal that day: undecided"
                elif len(dated) == 1:
                    verdict, code_dec = "CONFIRMED-NAME" if dated[0] not in near else "CONFIRMED", dated[0]
                    why = (f"claims {cands}; DB logs animal {animal} only under {dated[0]} within {WINDOW} days: "
                           f"{', '.join(ev[dated[0]]['near'])}")
                else:
                    verdict = "C"
                    why = f"claims {cands or '(none)'}; DB: " + "; ".join(
                        f"{c} {'found' if ev[c]['found'] else 'not found'}" for c in ev) if ev else \
                        f"claims {cands or '(none)'}; nothing to check"
            # a claim the DB CONTRADICTS drops to C: the animal was born after the scan, or a terminal
            # procedure (perfusion / organ sampling) is logged before it (project_claims.py's in-vivo rule)
            contra = ""
            if code_dec and animal:
                d = dbc.get(f"{code_dec}|{int(animal)}", {})
                try:
                    if d.get("dob") and dt.date.fromisoformat(d["dob"][:10]) > sdate:
                        contra = f"animal {animal} of {code_dec} was born {d['dob'][:10]}, after the scan"
                except ValueError:
                    pass
                for pr in d.get("procedures", []):
                    try:
                        pd_ = dt.date.fromisoformat(pr["date"][:10])
                    except (TypeError, ValueError):
                        continue
                    if pd_.year >= 1990 and pd_ < sdate and re.search(r"perfusion|organ sampling", pr["type"], re.I):
                        contra = contra or f"{pr['type']} logged {pr['date'][:10]}, before the scan"
            sib_ev = ""
            if contra:
                verdict, why = "C", f"{why}; DB CONTRADICTS the claim: {contra}"
                # evidence only (never a verdict): codes carried by sibling study names in the same folder
                parent = rs[0]["canonical_dir"].rsplit("\\", 2)[0]
                sib_codes = sorted({c for s2, rs2 in studies.items() if rs2[0]["canonical_dir"].rsplit("\\", 2)[0] == parent
                                    for c in parse_animal_codes(s2)[2]} - {code_dec})
                for c in sib_codes:
                    k = f"{c}|{int(animal)}"
                    if k not in dbc:
                        res = animal_db.lookup(c, int(animal), conn=conn, use_cache=False)
                        dbc[k] = {"status": res.status, "procedures": (res.subject or {}).get("procedures", []),
                                  "species": (res.subject or {}).get("species", ""),
                                  "dob": (res.subject or {}).get("date_of_birth", "")}
                    near_s = [f"{p['type']}@{p['date'][:10]}" for p in dbc[k]["procedures"]
                              if p.get("date") and p["date"][:4].isdigit() and int(p["date"][:4]) >= 1990
                              and abs((dt.date.fromisoformat(p["date"][:10]) - sdate).days) <= WINDOW]
                    sib_ev += f"{c}/{animal}: {dbc[k]['status']}" + (f", logs {', '.join(near_s)}" if near_s else "") + "; "
                code_dec = ""
            proj = by_name.get(f"AE-biomaGUNE-{code_dec}") if code_dec else None
            proposal = ""
            if code_dec == "0118":
                proposal = ("Proyecto-0118-rats-hipoxia (ruling 2026-09-30) OR AE-biomaGUNE-0118 = "
                            f"{proj['project_id'] if proj else '?'} (exists since 2026-09-30): Ryan's call")
            elif proj:
                proposal = f"{proj['name']} = {proj['project_id']} ({proj['status']})"
            elif code_dec:
                proposal = f"AE-biomaGUNE-{code_dec} (no gjesus3 project yet)"
            else:
                proposal = "blank (C): listed for Ryan" if verdict == "C" else "Ryan: Project-NNNN or blank"
            cc = collections.Counter(r["class"] for r in rs)
            out.append({
                "study": st, "study_date": r0["study_date"], "year": r0["year"], "initials": r0["initials"],
                "regex_parse": r0["regex_parse"], "exams": len(rs), "exams_not_in_prod": n_ex_new,
                "c_native_dicom": cc["c"], "d_convertible": cc["d"], "e_not_convertible": cc["e"],
                "a_b_in_prod": cc["a"] + cc["b"],
                "animal": animal, "species_hint": sp, "name_codes": ";".join(name_codes),
                "folder_claim": ";".join(near), "subject_id": r0["subject_id"],
                "db_evidence": " | ".join(f"{c}: {'found' if e['found'] else 'not found'}"
                                          + (f", {e['species']}" if e['species'] else "")
                                          + (f", logs {', '.join(e['near'])}" if e['near'] else "")
                                          for c, e in ev.items()),
                "verdict": verdict, "decided_code": code_dec, "why": why, "proposed_project": proposal,
                "evidence_from_sibling_codes (never a verdict)": sib_ev.strip("; "),
                "distinct_bytes_new_exams": sum(r["distinct_bytes_all_copies"] for r in rs if r["class"] in ("c", "d", "e")),
                "dcm_bytes_new": sum(r["dcm_bytes"] for r in rs if r["class"] == "c"),
                "stations": ";".join(sorted({r["station"] for r in rs if r["station"]})),
                "canonical_location": rs[0]["canonical_dir"].rsplit("\\", 2)[0],
                "tops": ";".join(sorted({t for r in rs for t in r["tops"].split(";")})),
            })
    finally:
        conn.close()
        with open(out_path("_cache", "db_lookups.json"), "w", encoding="utf-8") as f:
            json.dump(dbc, f, indent=0)
    write_csv("mri_missing_studies.csv", out, list(out[0].keys()))
    print(f"studies with exams not in production: {len(out)}")
    print("verdicts:", collections.Counter(o["verdict"] for o in out))
    print("decided codes:", collections.Counter(o["decided_code"] for o in out))


if __name__ == "__main__":
    main()
