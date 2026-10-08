"""Stream AR, step 5: the per-study and per-exam plan for the new studies (tiers A, A2, B), against LIVE production.

    python ar_05_plan.py            # read-only on J:; writes out\\plan_*.csv
    python ar_05_plan.py --sort     # also moves each planned study from extract\\_in\\ to extract\\<batch>\\ (D: only)

Rulings applied (tasks/STATUS.md 0.5 "Hold", 0.6 Q1-Q7; HANDOFF): operator pending-claim, researcher blank;
original_name = <study>/<exam>, dated by VisuCreationDate (else ACQ_time); subject ids from the facility DB with the
project's code as alias (never -None); projects by protocol code:
  * a code in the name that is a gjesus3 project: that project. The DB check (ar_04_db_evidence.py) confirms and never
    overrules: CONFIRMED / CLAIM-KEPT -> the project and a subject id; NOT-IN-DB / no animal number -> the project, NO
    subject id (as stream M's M09); CONTRADICTED (born after the scan) -> no project, no subject (as M08);
  * 0917, 0116, 1316 (no gjesus3 project; Q4): no project, no subject id;
  * no code in the name: the DB's answer when it is unique (DB-RESOLVED: one protocol holds the animal, alive, with an
    MRI logged within 3 days, and it is a gjesus3 project) -> that project and a subject id; else no project;
  * tier B (phantoms / QC, Q2): no project, no subject id, as July's jrc phantoms;
  * 0220 (closed; Q5) gets its own batch: the coordinator reopens the project before it runs;
  * the A2 second sessions go with their project: their link names carry the study's HHMM, as every link here
    (MRI_<sample>_<YYYYMMDD>_<HHMM>_<exam>_<recons>, the 2026-10-05 convention).
Per exam: class c (scanner DICOM) registers; d (2dseq only) is converted first and registers if converted; e
(spectroscopy, no reconstruction, never acquired) and the incomplete exam of a short archive are NOT registered (listed
for a placement batch, plan only).
Writes out\\plan_studies.csv, plan_exams.csv, not_registered.csv, convert_input_<batch>.csv, plan_summary.txt.
"""
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ar_common as C  # noqa: E402

ANIMALFIRST = re.compile(r"(?P<jrc_id>(?P<pi_initials>[a-z]+)_?\d{6,8}_m(?P<animal_num>\d+)_(?P<project_code>\d{4}))")
STUDY_RE = re.compile(r"^(?P<date>\d{8})_(?P<time>\d{6})_(?P<core>.+?)_\d+_\d+$")
SUFFIXED = re.compile(r"(?i)(?:^|_)(?P<tok>[mr]\d{1,4}[a-z]{1,3})(?=_|$)")      # m7e, m1a, m8b, m145b
PLAIN = re.compile(r"(?i)(?:^|_)(?P<tok>[mr]\d{1,4})(?=_|$|prueba)")              # tier B animals: m38, m3prueba
Q4 = {"0917", "0116", "1316"}
ORDER = ["0118", "0219", "0220", "0320", "0618", "0619", "0721", "1019", "1116", "1319", "1321", "1519"]


def batch_id(code, kind, subj):
    """One batch per project; a project's studies without a subject id get their own batch (subject_from_db false)."""
    if kind == "phantom":
        return "AR14_phantoms"
    if not code:
        return "AR13_noproject"
    return f"AR{ORDER.index(code) + 1:02d}{'' if subj else 'n'}_{code}"


def core_of(study):
    m = STUDY_RE.match(study)
    core = m.group("core") if m else study
    half = len(core) // 2
    # ParaVision 7 doubles the name ("<x>_<x>"); keep one half
    if len(core) % 2 == 1 and core[:half] == core[half + 1:] and core[half] == "_":
        core = core[:half]
    return core


def session_of(study):
    mm = ANIMALFIRST.search(study)
    return mm.group("jrc_id") if mm else core_of(study)


def main():
    plan = C.pull_plan()
    ev = {r["study"]: r for r in C.rows(os.path.join(C.OUT, "db_evidence.csv"))}
    inv = collections.defaultdict(list)
    for e in C.rows(os.path.join(C.OUT, "inventory_exams.csv")):
        if e["tier"] in ("A", "A2", "B"):
            inv[e["study"]].append(e)
    done = C.extracted()
    projs = {p["name"]: p for p in C.live_projects()}
    reg = C.live_registry()
    names = collections.defaultdict(list)
    for r in reg:
        names[r["original_name"].replace("\\", "/")].append(r["acq_id"])
    sess_day = collections.defaultdict(list)
    sample_day = collections.defaultdict(set)
    for r in reg:
        if r["instrument"] in ("MRI", "XMRI"):
            sess_day[(r["session_id"].lower(), r["acquisition_datetime"][:10])].append(r["original_name"].split("/")[0])
            sample_day[(r["sample_id"].lower(), r["acquisition_datetime"][:10])].add(r["original_name"].split("/")[0])
    studies, exams, notreg = [], [], []
    for study, p in sorted(plan.items()):
        if p["tier"] not in ("A", "A2", "B"):
            continue
        e = ev.get(study, {})
        claim = p["protocol"]
        core = core_of(study)
        suf = SUFFIXED.search(core)
        pl = PLAIN.search(core)
        if p["tier"] == "B":
            token = pl.group("tok").lower() if pl else ""
        else:
            token = suf.group("tok").lower() if suf else e.get("animal", "")
        plain = re.fullmatch(r"[mr]\d+", token) is not None
        why = ""
        if p["tier"] == "B":
            kind = "phantom"
            code, subj = "", False
            why = "phantom / QC study (Q2): no project, as July's jrc phantoms"
            stype = ("tissue" if "exvivo" in core.lower() else "organism" if plain else "phantom")
            sample = token if stype == "organism" else core
        else:
            kind = "animal"
            stype = "organism"
            v = e.get("verdict", "")
            if claim in Q4:
                code, subj = "", False
                why = f"protocol {claim} is no gjesus3 project (Q4): no project; DB {v}"
            elif claim:
                if v in ("CONFIRMED", "CLAIM-KEPT"):
                    code, subj = claim, True
                elif v in ("NOT-IN-DB", "NO-ANIMAL-NUMBER"):
                    code, subj = claim, False
                    why = f"the name claims {claim}; {v} in the facility DB: the project is kept, no subject id (as M09)"
                elif v == "CONTRADICTED":
                    code, subj = "", False
                    why = f"the name claims {claim}, the facility DB contradicts it ({e.get('evidence')}): no project, no subject id (as M08)"
                else:
                    raise SystemExit(f"{study}: claim {claim} with verdict {v!r}")
            else:
                if v == "DB-RESOLVED":
                    code, subj = e["decided_code"], True
                else:
                    code, subj = "", False
                    why = f"no code in the name; facility DB {v}: no project"
            sample = (f"{token}_{code}" if code and token else token if token else core)
        alias = code if subj else ""
        animal = e.get("animal", "")[1:] if subj else ""
        if subj and not (animal and re.fullmatch(r"\d+", animal)):
            raise SystemExit(f"{study}: a subject id without an animal number")
        project = f"AE-biomaGUNE-{code}" if code else ""
        if project and project not in projs:
            raise SystemExit(f"{study}: project {project} is not in production")
        b = batch_id(code, kind, subj)
        m = STUDY_RE.match(study)
        hhmm = m.group("time")[:4] if m else ""
        session = session_of(study)
        ex = inv.get(study, [])
        trunc = (done.get(study) or {}).get("truncated") or {}
        srec = {"study": study, "tier": p["tier"], "batch": b, "kind": kind, "claim": claim,
                "db_verdict": e.get("verdict", ""), "db_evidence": e.get("evidence", ""), "project_name": project,
                "project_status": projs[project]["status"] if project else "", "alias": alias, "animal": animal,
                "sample_id": sample, "sample_type": stype, "session_id": session, "study_hhmm": hhmm,
                "why": why, "extracted": "Y" if study in done else "N", "truncated_exam": trunc.get("incomplete_exam", ""),
                "exams": len(ex), "register_c": 0, "convert_d": 0, "not_registered": 0,
                "archive": p["chosen_path"], "archive_sha1": (done.get(study) or {}).get("sha1", ""),
                "census_size": p["size"], "copies_differ": p["copies_differ"],
                "prod_same_session_day": ";".join(sorted(set(sess_day.get((session.lower(), f"{study[:4]}-{study[4:6]}-{study[6:8]}"), []))))}
        for x in ex:
            on = x["original_name"]
            if trunc and x["exam"] == trunc.get("incomplete_exam"):
                disp, reason = "not-registered", "incomplete: the archive's copy ends inside this exam"
            elif x["class"] == "c":
                disp, reason = "register", ""
            elif x["class"] == "d":
                disp, reason = "convert-first", ""
            else:
                disp, reason = "not-registered", x["class_detail"]
            if disp != "not-registered" and not x["acq_datetime"]:
                disp, reason = "not-registered", "no VisuCreationDate and no ACQ_time"
            if disp != "not-registered" and x["model"].startswith("UNKNOWN"):
                disp, reason = "not-registered", f"unknown station {x['station']}"
            d8 = x["acq_datetime"][:10].replace("-", "")
            rec = {**{k: srec[k] for k in ("study", "tier", "batch", "kind", "project_name", "alias", "animal",
                                           "sample_id", "sample_type", "session_id", "study_hhmm")},
                   "exam": x["exam"], "original_name": on, "class": x["class"], "class_detail": x["class_detail"],
                   "disposition": disp, "reason": reason, "acq_datetime": x["acq_datetime"],
                   "date_source": x["date_source"], "acq_time": x["acq_time"], "model": x["model"],
                   "method": x["method"], "scan_name": x["scan_name"], "pdata": x["pdata"],
                   "recons_dicom": x["recons_dicom"], "recons_without_dicom": x["recons_without_dicom"],
                   "n_dicom": x["n_dicom"], "dicom_set_sha256": x["dicom_set_sha256"],
                   "link_name": (f"MRI_{srec['sample_id']}_{d8}_{hhmm}_{x['exam']}_{x['pdata'].replace(';', ',')}"
                                 if srec["project_name"] and disp != "not-registered" else ""),
                   "prod_name_hits": ";".join(names.get(on, []) + names.get(on.replace("/", "__"), [])),
                   "prod_same_sample_day": ";".join(sorted(sample_day.get((srec["sample_id"].lower(), x["acq_datetime"][:10]), set())))}
            exams.append(rec)
            srec["register_c" if disp == "register" else "convert_d" if disp == "convert-first" else "not_registered"] += 1
            if disp == "not-registered":
                notreg.append(rec)
        studies.append(srec)

    reg_ex = [x for x in exams if x["disposition"] != "not-registered"]
    C.write_csv(C.out("plan_studies.csv"), studies)
    C.write_csv(C.out("plan_exams.csv"), exams)
    C.write_csv(C.out("not_registered.csv"), notreg, list(exams[0].keys()) if exams else None)
    for b in sorted({x["batch"] for x in reg_ex if x["disposition"] == "convert-first"}):
        C.write_csv(C.out(f"convert_input_{b}.csv"),
                    [{"original_name": x["original_name"]} for x in reg_ex if x["batch"] == b and x["disposition"] == "convert-first"])
    # ---- invariants on the plan --------------------------------------------------------------------------------------
    seen = collections.defaultdict(list)
    for x in reg_ex:
        if x["link_name"]:
            seen[(x["project_name"], x["link_name"].lower())].append(x["original_name"])
    dup_links = {k: v for k, v in seen.items() if len(v) > 1}
    taken = []
    for proj in sorted({x["project_name"] for x in reg_ex if x["project_name"]}):
        rl = os.path.join(C.NAS, "projects", proj, "raw_linked")
        existing = {n.lower() for n in os.listdir(rl)} if os.path.isdir(rl) else set()
        taken += [x["link_name"] for x in reg_ex if x["project_name"] == proj and x["link_name"].lower() in existing]
    dn = collections.Counter((x["acq_datetime"][:10], x["original_name"]) for x in reg_ex)
    L = [f"live registry rows read now: {len(reg)}",
         f"studies planned: {len(studies)} {dict(collections.Counter(s['tier'] for s in studies))}; extracted "
         f"{sum(1 for s in studies if s['extracted'] == 'Y')}; truncated archives {[s['study'] for s in studies if s['truncated_exam']]}",
         f"exams: {len(exams)}; {dict(collections.Counter(x['disposition'] for x in exams))}",
         f"not registered: {dict(collections.Counter(x['reason'] for x in notreg).most_common())}",
         "batch: studies / exams register (c) + convert-first (d) / not registered; projects",
         ]
    for b in sorted({s["batch"] for s in studies}):
        ss = [s for s in studies if s["batch"] == b]
        L.append(f"  {b}: {len(ss)} studies ({sum(1 for s in ss if s['extracted'] == 'Y')} extracted); "
                 f"{sum(s['register_c'] for s in ss)} + {sum(s['convert_d'] for s in ss)} / {sum(s['not_registered'] for s in ss)}; "
                 f"{dict(collections.Counter(s['project_name'] or '(none)' for s in ss))}; subject ids "
                 f"{sum(1 for s in ss if s['alias'])} studies; tiers {dict(collections.Counter(s['tier'] for s in ss))}")
    L += [f"project status: {dict(collections.Counter((s['project_name'], s['project_status']) for s in studies if s['project_name']))}",
          f"LIVE CHECK: planned exams whose original_name (or <study>__<exam>) is in the registry now: "
          f"{sum(1 for x in exams if x['prod_name_hits'])}",
          f"LIVE CHECK: studies whose session id and day are in production (expected 0): "
          f"{sum(1 for s in studies if s['prod_same_session_day'])} {dict(collections.Counter(s['tier'] for s in studies if s['prod_same_session_day']))}",
          f"LIVE CHECK: planned studies with an exam whose sample and day production holds (another session that day; "
          f"the census' key 4 -- expected: the 12 A2 second sessions): "
          f"{dict(collections.Counter(s['tier'] for s in studies if any(x['prod_same_sample_day'] for x in exams if x['study'] == s['study'])))} "
          f"{sorted({x['study'] for x in exams if x['prod_same_sample_day'] and x['tier'] != 'A2'})[:6]}",
          f"link names: {sum(1 for x in reg_ex if x['link_name'])}; duplicated within the plan: {len(dup_links)} "
          f"{list(dup_links.items())[:3]}; already taken in production now: {len(taken)} {taken[:5]}",
          f"(date, original_name) duplicated within the plan: {sum(1 for v in dn.values() if v > 1)}",
          f"models: {dict(collections.Counter(x['model'] for x in reg_ex))}; date source "
          f"{dict(collections.Counter(x['date_source'] for x in reg_ex))}; dated 2026: "
          f"{sum(1 for x in reg_ex if x['acq_datetime'].startswith('2026'))}",
          f"exams whose date's day differs from the study name's day: "
          f"{sum(1 for x in reg_ex if x['acq_datetime'][:10].replace('-', '') != x['study'][:8])}"]
    open(C.out("plan_summary.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))

    if "--sort" in sys.argv:
        moved = 0
        for s in studies:
            if s["extracted"] != "Y":
                continue
            src = done[s["study"]]["dir"]
            dst = C.w(C.EXTRACT, s["batch"], s["study"])
            if src and os.path.abspath(src).lower() != dst.lower():
                os.rename(C.lp(src), C.lp(dst))
                moved += 1
        print(f"sorted into batch folders: {moved}")


if __name__ == "__main__":
    main()
