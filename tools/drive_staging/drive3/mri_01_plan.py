"""Stream M, step 1: the per-exam plan for the drive's MRI that production lacks (read-only).

    python mri_01_plan.py

Inputs: A1's mri_exams.csv, mri_exam_copies.csv, mri_exam_headers.csv, mri_missing_studies.csv (the facility-DB
verdicts), the drive manifest, and the LIVE registries (registry_raw, registry_projects), read now.
Writes (out\\):
  plan_exams.csv        one row per exam A1 found not in production (3,380): disposition register / not, batch,
                        project, protocol alias, animal, sample id, session id, model, the drive copy to stage
  plan_studies.csv      one row per study (198)
  plan_stage_files.csv  every file to stage (the chosen copy of each exam, k-space excluded, + the study's subject)
  not_registered.csv    the exams that are not registered, and why (for stream P's second batch)
  recon_no_dicom.csv    reconstructions of registered exams that have a 2dseq but no DICOM (not stored in /raw/)
  plan_summary.txt

Rulings applied (tasks/STATUS.md section 0.5; HANDOFF): all 0118 -> AE-biomaGUNE-0118 (M1); 1019 2020 ->
AE-biomaGUNE-1019 (M2); 1116 by the DB; jrc191015_m174_flow -> no project and no subject (its claim is
contradicted); the rest by their DB-confirmed code. MRI registered only with DICOM (Ryan, 2026-10-04): class (c)
has the scanner's DICOM, (d) is converted first, (e) is not registered. m175 / m178: the copy byte-identical to
Ermal's K: copy (A1 R2): m175 from respiracion\\inspiracion, m178 from respiracion\\expiración.
"""
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mri_common as C  # noqa: E402

PROJECT = {"0118": "AE-biomaGUNE-0118", "0619": "AE-biomaGUNE-0619", "1019": "AE-biomaGUNE-1019",
           "0320": "AE-biomaGUNE-0320", "1116": "AE-biomaGUNE-1116", "0522": "AE-biomaGUNE-0522"}
MODEL = {"Biospec 70/30": "Bruker BioSpec 7T", "BIOSPEC 500": "Bruker BioSpec 11.7T"}
K_COPY = {"20210902_082356_jrc210902_m175_ermal_1_1": "\\respiracion\\inspiracion\\",
          "20210902_115741_jrc210902_m178_ermal_1_1": "\\respiracion\\expiración\\"}
CONTRADICTED = "20191015_153156_jrc191015_m174_flow_1_1"
# The study name claims animal "145b". The facility DB knows no 145b: A1 read it as 145, but 145 has its own session
# that day (m145, 10:47), and the DB logs MRI 7T on 2021-07-26 for 145, 146, 152 and 153 while the drive holds m145b,
# m145, m152, m153 -- so 145b is probably 146. A check confirms a claim and never overrules it, and "probably" is not
# an attribution: project 0619 (folder claim; every candidate is 0619), sample from its own name, NO subject id.
UNCONFIRMED_ANIMAL = "20210726_085549_jrc210726_m145b_0619_1_1"
# the production animal-first regex (tools/configs/mri_jrc_animalfirst.yaml), for the session id
ANIMALFIRST = re.compile(r"(?P<jrc_id>(?P<pi_initials>[a-z]+)_?\d{6,8}_m(?P<animal_num>\d+)_(?P<project_code>\d{4}))")
STUDY_RE = re.compile(r"^\d{8}_\d{6}_(?P<core>.+?)_\d+_\d+$")


def batch_of(code, year, study):
    if study == CONTRADICTED:
        return "M08"
    if study == UNCONFIRMED_ANIMAL:
        return "M09"
    return {("0118", None): "M01", ("0619", "2020"): "M02", ("0619", "2021"): "M03", ("0619", "2022"): "M04",
            ("1019", "2020"): "M05", ("0320", "2022"): "M06", ("1116", None): "M07", ("0522", None): "M07",
            }.get((code, None if code in ("0118", "1116", "0522") else year), "UNPLANNED")


def main():
    ex = C.rows(os.path.join(C.A1, "mri_exams.csv"))
    cp = C.rows(os.path.join(C.A1, "mri_exam_copies.csv"))
    hd = {r["exam_key"]: r for r in C.rows(os.path.join(C.A1, "mri_exam_headers.csv"))}
    st = {r["study"]: r for r in C.rows(os.path.join(C.A1, "mri_missing_studies.csv"))}
    copies = collections.defaultdict(list)
    for r in cp:
        copies[r["exam_key"]].append(r)
    new = [r for r in ex if r["class"] in ("c", "d", "e")]

    # ---- the live registry, read now ------------------------------------------------------------------------
    reg = C.live_registry()
    projs = {p["name"]: p for p in C.live_projects()}
    names = collections.defaultdict(list)
    for r in reg:
        names[r["original_name"].replace("\\", "/")].append(r["acq_id"])
    sessions = collections.Counter(r["session_id"] for r in reg if r["instrument"] in ("MRI", "XMRI"))

    plan, files, notreg, nodcm = [], [], [], []
    for r in new:
        s = st[r["study"]]
        key = r["exam_key"]
        study, exam = r["study"], r["exam"]
        year = r["year"]
        code = s["decided_code"]
        # the drive copy to stage
        cands = copies[key]
        if study in K_COPY:
            pick = [c for c in cands if K_COPY[study] in c["exam_dir"]]
        else:
            pick = [c for c in cands if c["canonical"] == "Y"]
        assert len(pick) == 1, (key, [c["exam_dir"] for c in cands])
        pick = pick[0]
        h = hd.get(key, {})
        station = h.get("ACQ_station") or r["station"]
        # disposition
        if r["class"] == "e":
            disp = "not-registered"
        else:
            disp = "register"
        animal = s["animal"]
        m = re.search(r"_([mr])(\d+)", study)
        prefix = m.group(1) if m else ("r" if s["species_hint"] == "rat" else "m")
        if study == CONTRADICTED:
            project, alias, sample = "", "", f"m{animal}"
        elif study == UNCONFIRMED_ANIMAL:
            project, alias, sample = PROJECT[code], "", f"m145b_{code}"
        else:
            project, alias, sample = PROJECT[code], code, f"{prefix}{animal}_{code}"
        mm = ANIMALFIRST.search(study)
        core = STUDY_RE.match(study)
        session = mm.group("jrc_id") if mm else (core.group("core") if core else study)
        rec = {
            "exam_key": key, "study": study, "exam": exam, "original_name": f"{study}/{exam}",
            "class": r["class"], "class_detail": r["class_detail"], "disposition": disp,
            "batch": batch_of(code, year, study) if disp == "register" else "",
            "year": year, "study_date": r["study_date"], "acq_time": r["acq_time"],
            "protocol": code, "project_name": project, "project_id": projs[project]["project_id"] if project else "",
            "project_status": projs[project]["status"] if project else "", "verdict": s["verdict"],
            "db_evidence": s["db_evidence"], "alias": alias, "animal": animal, "species_hint": s["species_hint"],
            "sample_id": sample, "session_id": session, "station": station, "model": MODEL.get(station, "UNKNOWN"),
            "method": r["method"], "scan_name": r["scan_name"], "nonimage_marker": r["nonimage_marker"],
            "n_dcm_drive": pick["n_dcm"], "dcm_recons": pick["dcm_recons"], "seq_recons": pick["seq_recons"],
            "kspace": pick["kspace"], "drive_exam_dir": pick["exam_dir"], "n_copies": pick["n_copies"],
            "vs_canonical": pick["vs_canonical"], "regex_parse": r["regex_parse"],
            "subject_id_in_file": h.get("SUBJECT_id", ""),
            "prod_name_hits": ";".join(names.get(f"{study}/{exam}", []) + names.get(f"{study}__{exam}", [])),
            "prod_session_hits": sessions.get(session, 0),
        }
        plan.append(rec)
        if disp != "register":
            notreg.append({**rec, "reason": r["class_detail"]})
        else:
            sr = set(x for x in rec["seq_recons"].split(";") if x)
            dr = set(x for x in rec["dcm_recons"].split(";") if x)
            if rec["class"] == "c" and sr - dr:
                nodcm.append({"original_name": rec["original_name"], "recons_without_dicom": ";".join(sorted(sr - dr)),
                              "drive_exam_dir": rec["drive_exam_dir"], "method": rec["method"],
                              "scan_name": rec["scan_name"]})

    # ---- the files to stage: every file of the chosen copy except k-space, + the study's subject ------------------
    reg_exams = [p for p in plan if p["disposition"] == "register"]
    dirs = {p["drive_exam_dir"]: p for p in reg_exams}
    study_dirs = {p["drive_exam_dir"].rsplit("\\", 1)[0]: p for p in reg_exams}
    man = C.manifest_under(sorted({d.split("\\", 1)[0] for d in dirs}))
    per_exam = collections.Counter()
    subj_cands = collections.defaultdict(list)
    for rel, (size, sha) in man.items():
        d, name = rel.rsplit("\\", 1)
        # exam files: <exam_dir>\...
        hit = None
        for cut in range(rel.count("\\"), 0, -1):
            head = rel.rsplit("\\", cut)[0] if cut else rel
            if head in dirs:
                hit = head
                break
        if hit is not None:
            p = dirs[hit]
            inner = rel[len(hit) + 1:]
            if C.is_kspace(name):
                continue
            files.append({"batch": p["batch"], "exam_key": p["exam_key"], "drive_relpath": rel,
                          "staged_rel": f"{p['batch']}\\{p['study']}\\{p['exam']}\\{inner}", "size": size,
                          "sha256": sha})
            per_exam[p["exam_key"]] += 1
        elif d in study_dirs and name == "subject":
            subj_cands[study_dirs[d]["study"]].append((rel, size, sha))
    # one subject per study; when a study's exams come from two copies, both subject files must be identical
    subj_conflict = []
    for study, cs in sorted(subj_cands.items()):
        p = next(x for x in reg_exams if x["study"] == study)
        if len({c[2] for c in cs}) != 1:
            subj_conflict.append(study)
        rel, size, sha = sorted(cs)[0]
        files.append({"batch": p["batch"], "exam_key": "", "drive_relpath": rel,
                      "staged_rel": f"{p['batch']}\\{p['study']}\\subject", "size": size, "sha256": sha})
    seen = set()
    dup = [f["staged_rel"] for f in files if f["staged_rel"] in seen or seen.add(f["staged_rel"])]
    assert not dup, dup[:5]
    missing_files = [p["exam_key"] for p in reg_exams if not per_exam[p["exam_key"]]]
    subj_studies = {f["staged_rel"].split("\\")[1] for f in files if f["exam_key"] == ""}
    zero_dcm = [f["drive_relpath"] for f in files if f["size"] == 0 and f["drive_relpath"].lower().endswith(".dcm")]

    C.write_csv(C.out("plan_exams.csv"), plan)
    # convert-first inputs, one per batch holding class (d) exams (convert_staged_exams.py reads original_name only)
    for b in sorted({p["batch"] for p in reg_exams if p["class"] == "d"}):
        C.write_csv(C.out(f"convert_input_{b}.csv"),
                    [{"original_name": p["original_name"]} for p in reg_exams if p["batch"] == b and p["class"] == "d"])
    C.write_csv(C.out("plan_stage_files.csv"), files)
    C.write_csv(C.out("not_registered.csv"), notreg)
    C.write_csv(C.out("recon_no_dicom.csv"), nodcm,
                ["original_name", "recons_without_dicom", "drive_exam_dir", "method", "scan_name"])
    studies = collections.OrderedDict()
    for p in plan:
        s = studies.setdefault(p["study"], {"study": p["study"], "batch": "", "year": p["year"], "protocol": p["protocol"],
                                            "project_name": p["project_name"], "verdict": p["verdict"], "animal": p["animal"],
                                            "sample_id": p["sample_id"], "session_id": p["session_id"], "model": p["model"],
                                            "regex_parse": p["regex_parse"], "exams": 0, "register": 0, "c": 0, "d": 0,
                                            "not_registered": 0, "drive_study_dir": p["drive_exam_dir"].rsplit("\\", 1)[0]})
        s["exams"] += 1
        if p["disposition"] == "register":
            s["register"] += 1
            s[p["class"]] += 1
            s["batch"] = p["batch"]
        else:
            s["not_registered"] += 1
    C.write_csv(C.out("plan_studies.csv"), list(studies.values()))

    # ---- summary ----------------------------------------------------------------------------------------------------
    L = []
    L.append(f"live registry rows read now: {len(reg)}")
    L.append(f"exams not in production (A1): {len(plan)} in {len(studies)} studies; classes "
             f"{dict(collections.Counter(p['class'] for p in plan))}")
    L.append(f"register: {len(reg_exams)} (c {sum(p['class'] == 'c' for p in reg_exams)}, d "
             f"{sum(p['class'] == 'd' for p in reg_exams)}) in {sum(1 for s in studies.values() if s['register'])} studies; "
             f"not registered: {len(notreg)} {dict(collections.Counter(p['class_detail'] for p in notreg))}")
    L.append(f"LIVE CHECK: exams whose original_name (or <study>__<exam>) is in the registry now: "
             f"{sum(1 for p in plan if p['prod_name_hits'])}")
    L.append(f"LIVE CHECK: studies whose session id is used by a production MRI row now: "
             f"{sorted({p['session_id'] for p in plan if p['prod_session_hits']})}")
    L.append(f"projects: {dict(collections.Counter((p['project_name'], p['project_status']) for p in reg_exams))}")
    L.append(f"models: {dict(collections.Counter(p['model'] for p in reg_exams))}")
    by = collections.defaultdict(lambda: [0, 0, 0, set(), 0])
    fb = collections.defaultdict(lambda: [0, 0])
    for f in files:
        fb[f["batch"]][0] += 1
        fb[f["batch"]][1] += f["size"]
    for p in reg_exams:
        b = by[p["batch"]]
        b[0] += 1
        b[1 if p["class"] == "c" else 2] += 1
        b[3].add(p["study"])
    L.append("batch: exams (c / d), studies, files to stage, GB to stage")
    for k in sorted(by):
        b = by[k]
        L.append(f"  {k}: {b[0]} ({b[1]} / {b[2]}), {len(b[3])} studies, {fb[k][0]} files, {fb[k][1] / 1e9:.2f} GB; "
                 f"projects {sorted({p['project_name'] for p in reg_exams if p['batch'] == k})}; models "
                 f"{dict(collections.Counter(p['model'] for p in reg_exams if p['batch'] == k))}")
    L.append(f"files to stage: {len(files)}, {sum(f['size'] for f in files) / 1e9:.2f} GB; exams with no file: "
             f"{len(missing_files)}; studies with a subject file: {len(subj_studies)} of "
             f"{len({p['study'] for p in reg_exams})}; zero-byte .dcm: {zero_dcm}; subject files that differ between copies: {subj_conflict}")
    L.append(f"registered exams with a 2dseq-only reconstruction (not stored): {len(nodcm)} in "
             f"{len({n['original_name'].split('/')[0] for n in nodcm})} studies")
    L.append(f"studies outside every planned batch: {sorted({p['study'] for p in reg_exams if p['batch'] == 'UNPLANNED'})}")
    open(C.out("plan_summary.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
