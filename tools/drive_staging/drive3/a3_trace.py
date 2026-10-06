"""A3 step 4 -- group every label on drive 3 into sets and trace each one to production ACQ-IDs (read-only).

A "label" is a file whose voxel census (a3_headers.csv) says label/label_empty, plus the non-voxel label
formats: PMOD .voi, Amira label fields, NDP.view (.ndpa) and QuPath (.qpdata) annotations.

Trace routes, strongest first, each recorded with its evidence (never a guess):
  sha-source     a source image sitting beside the label is byte-identical (SHA-256) to a production
                 /raw/ file -> that file's ACQ-ID (PET/CT DICOM beside PET masks, .czi beside .ndpa);
  dsseg-twin     the label itself is byte-identical to a promoted DS-SEG file -> that file's ACQ-IDs;
  name-source    a source DICOM beside the label is named exactly as a production original_name
                 (Molecubes '<YYYYMMDDhhmmss>_<MOD>_<RECON>_<n>');
  nifti-exam     the label's dims + affine equal one NIfTI conversion in its folder whose name carries
                 the ParaVision exam number (Cine_IG_FLASH_<exam>_Proc<k>) and the folder's study is in
                 production -> original_name '<study>/<exam>';
  cine-split     the label's dims equal a per-phase split volume of a production study; the slice ->
                 acquisition map comes from a3_ncc.py (direct pixel cross-correlation against the
                 production DICOM), or, without it, stays at session level;
  session-only   the study / session is in production but the acquisition(s) are not established;
  none           no production study / acquisition (with why: older than the scanner horizon, foreign
                 instrument, no session token, ...).
Outputs (D:\\projects\\gjesus3\\drive3_analysis\\a3\\): a3_labels.csv (one row per label file copy),
a3_label_sessions.csv (one row per study / session met), a3_cine_ncc_todo.csv (work list for a3_ncc.py).
"""
import os
import re
import sys
from collections import Counter, defaultdict

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a3_common as C  # noqa: E402

TS_DCM = re.compile(r"^(\d{14})_(PET|CT|SPECT)_([A-Za-z0-9]+)_(\d+)\.dcm$", re.I)
# NIfTI conversions of ParaVision exams: Cine_IG_FLASH_20_Proc1, 1_Localizer_multi_slice_7_Proc1,
# Velocity_map_18_Velocitymap1mm, Cine_IG_FLASH_11_0.8mm. Exam numbers have no leading zero (keeps '0522' out).
NIFTI_EXAM = re.compile(r"^(?:ID\d+_)?(?P<proto>.+?)_(?P<exam>[1-9]\d{0,2})(?:_Proc(?P<proc>\d+)|_[A-Za-z0-9.]+)?\.nii(?:\.gz)?$", re.I)
SPLIT_RE = re.compile(r"^Time_(?P<t>\d+)_rat_(?P<study>.+)\.mhd$", re.I)


# ----------------------------------------------------------------------------------------------- production
def load_prod():
    acqs = C.read_csv_dicts(C.PROD_ACQS)
    reg = {r["acq_id"]: r for r in C.read_csv_dicts(os.path.join(C.REG, "registry_raw.csv"))}
    by_study = defaultdict(list)      # MRI study folder -> acq rows
    by_session = defaultdict(list)
    by_orig = {}
    by_ts = defaultdict(list)         # 14-digit timestamp -> PET/CT/SPECT rows
    for a in acqs:
        g = reg.get(a["acq_id"], {})
        a["notes"] = g.get("notes", "")
        a["subject_ids"] = g.get("subject_ids", "")
        m = re.search(r"Bruker:(\w+)|User:(\w+)", a["notes"])
        a["method"] = (m.group(1) or m.group(2)) if m else ""
        m = re.search(r"recons kept: ([\d,]+)", a["notes"])
        a["recons"] = m.group(1) if m else ""
        on = a["original_name"]
        by_orig[on] = a
        if a["instrument"] == "MRI" and "/" in on:
            study = re.sub(r"__\d+$", "", on.split("/")[0])
            a["study"] = study
            a["exam"] = on.split("/")[1]
            by_study[study].append(a)
        if a["session_id"]:
            by_session[a["session_id"]].append(a)
        m = re.match(r"^(\d{14})_", on)
        if m and a["instrument"] in ("PET", "CT", "SPECT"):
            by_ts[m.group(1)].append(a)
    sha2acq = {}
    with open(C.PROD_SHA, encoding="utf-8") as f:
        next(f)
        for line in f:
            p = line.rstrip("\n").split(",", 4)
            sha2acq.setdefault(p[0].lower(), p[1])
    return acqs, by_study, by_session, by_orig, by_ts, sha2acq


# ----------------------------------------------------------------------------------------------- drive
def load_drive():
    inv = C.read_csv_dicts(os.path.join(C.OUT_DIR, "a3_inventory.csv"))
    hdr = {r["sha256"]: r for r in C.read_csv_dicts(os.path.join(C.OUT_DIR, "a3_headers.csv"))}
    folders = defaultdict(list)   # every manifest file, by parent folder (for context: DICOM, images, splits)
    for r in C.read_csv_dicts(C.MANIFEST):
        rel = r["relpath"]
        parent, _, name = rel.rpartition("\\")
        if not C.is_junk(name):
            folders[parent].append((name, r["sha256"], int(r["size"]), rel))
    return inv, hdr, folders


def dsseg_twins():
    import glob
    tw = {}
    for d in sorted(glob.glob(os.path.join(C.CDS, "segmentation", "*", "DS-SEG-*"))):
        ds = os.path.basename(d)
        for r in C.read_csv_dicts(os.path.join(d, "provenance.csv")):
            for col in ("sha256", "source_sha256"):
                s = (r.get(col) or "").lower()
                if s:
                    tw[s] = (ds, r.get("acq_ids_all") or r.get("acq_id", ""), r.get("file_path", ""), r.get("session_id", ""))
    return tw


# ----------------------------------------------------------------------------------------------- sets
def assign_set(rel, name, h):
    low = rel.lower()
    vals = (h or {}).get("values", "")
    dims = (h or {}).get("dims", "")
    if "arteria pulmonar cerdos" in low:
        return "S-PIG-PA-FLOW", "pig pulmonary artery, phase-contrast flow MRI (Philips 3T, CNIC)"
    if "segmentacion 2dg ratas" in low:
        return "S-RAT-2DG-2019-PRED", "rat cardiac cine, model predictions + post-processing (2019, 2DG)"
    if low.endswith(".ndpa") or low.endswith(".qpdata"):
        return "S-HISTO-ANNOT", "histology annotations (NDP.view / QuPath) on .czi slides"
    if "amira" in low or low.endswith((".labels", ".am")):
        return "S-AMIRA-LUNG-CT", "lung label field drawn in Amira on a PET/CT (fumadores)"
    if low.endswith(".voi"):
        return "S-PMOD-VOI", "PMOD VOI sets on Molecubes PET/CT"
    if "\\predict_slicer\\" in low or name.lower().endswith("_cardiac_segmentation.mha"):
        return "S-CINE-PRED-VICOMTECH", "mouse cardiac cine, Vicomtech PH_segmentation_tool predictions (5-class)"
    if "mri grasas" in low:
        return "S-FAT-1019", "mouse fat (fat-fraction MRI) masks, Proyecto 1019 'MRI grasas Irati'"
    # per-frame ROI stacks: one ROI per cardiac frame, value = frame number (0;1;..;N with N = number of slices)
    vl = vals.split(";") if vals else []
    if len(vl) >= 11 and vl == [str(i) for i in range(len(vl))] and dims.split("x")[2:3] == [str(len(vl) - 1)]:
        return "S-FLOW-ROI", "mouse great-vessel ROIs on phase-contrast flow MRI (pulmonary artery; some aorta)"
    if re.search(r"(?i)mpa ?flow|flowmpa|pa_flujo|_flow\.nii|flow\b", name) or "\\flujo" in low or "pruebas flujo" in low:
        return "S-FLOW-ROI", "mouse great-vessel ROIs on phase-contrast flow MRI (pulmonary artery; some aorta)"
    if re.search(r"(?i)(\\pet\\|suv|fdg|ftha|flurpiridaz|\\pet-)", rel) and "\\mri\\" not in low:
        return "S-PETCT-MASK", "organ masks (NIfTI) on Molecubes PET/CT exports"
    if re.search(r"(?i)expiration|inspiraiton|respiracion|ermal", rel):
        return "S-RAT-0118-RESP", "rat cardiac cine masks, protocol 0118 hypoxia / MCT, respiration comparison"
    if re.search(r"(?i)massventric|mass\.nii|-mass", name):
        return "S-CINE-MASS", "mouse cardiac cine, 'Massventricles' myocardial-mass masks"
    return "S-CINE-LVRV", "mouse cardiac cine ventricle masks (ITK-SNAP), per cardiac phase"


# ----------------------------------------------------------------------------------------------- helpers
norm_session = C.norm_session
split_study = C.split_study


def folder_context(parent, folders, hdr, by_session):
    """What sits beside a label: studies named, source DICOM, NIfTI exam images, split volumes."""
    ctx = {"studies": set(), "sessions": set(), "dcm": [], "nifti_imgs": [], "splits": []}
    for comp in parent.split("\\"):
        ctx["studies"].update(C.study_tokens(comp))
        ctx["sessions"].update(norm_session(s) for s in C.session_tokens(comp))
    for name, sha, size, rel in folders.get(parent, []):
        ms = SPLIT_RE.match(name)
        if ms:
            st = split_study(ms.group("study"), by_session)
            if re.match(r"^\d{8}_\d{6}_", st):
                ctx["studies"].add(st)
            else:
                ctx["sessions"].add(norm_session(st))
            ctx["splits"].append((int(ms.group("t")), st, sha, rel))
            continue
        if TS_DCM.match(name):
            ctx["dcm"].append((name, sha, rel))
            continue
        me = NIFTI_EXAM.match(name)
        if me and name.lower().endswith((".nii", ".nii.gz")):
            hh = hdr.get(sha, {})
            if hh.get("kind") == "image":
                ctx["nifti_imgs"].append((int(me.group("exam")), int(me.group("proc") or 0), me.group("proto"), sha, hh))
    return ctx


PET_SETS = {"S-PETCT-MASK", "S-PMOD-VOI", "S-AMIRA-LUNG-CT"}


def pet_keys(rel):
    """(animal, protocol, yyyymmdd) from a PET label's path -- each only when the path states it plainly."""
    comps = rel.split("\\")
    name = comps[-1]
    animal = comps[-2] if re.fullmatch(r"\d{1,3}", comps[-2]) else ""
    if not animal:
        m = re.search(r"(?i)(?:^|[_\-\s])(?:m|ID ?)(\d{1,3})(?=[_\-\s.])", name)
        animal = m.group(1) if m else ""
    proto = ""
    for comp in comps[:-1]:
        m = re.search(r"(?i)proyecto[\s_-]*(\d{4})", comp)
        if m:
            proto = m.group(1)
    if not proto:
        for comp in comps[:-1]:
            if re.fullmatch(r"[01]\d{3}", comp):
                proto = comp
    if not proto:
        m = re.search(r"[-_]([01]\d{3})(?=[-_.])", name)
        proto = m.group(1) if m else ""
    date = ""
    for comp in comps[:-1]:
        m = re.match(r"^(2[0-6])(0[1-9]|1[0-2])([0-2]\d|3[01])(?!\d)", comp)
        if m:
            date = "20" + m.group(0)
    return animal, proto, date


def norm_affine(s):
    try:
        return tuple(round(float(v), 3) for v in s.split(";"))
    except ValueError:
        return None


def main():
    acqs, by_study, by_session, by_orig, by_ts, sha2acq = load_prod()
    inv, hdr, folders = load_drive()
    twins = dsseg_twins()
    # where each split volume exists on the drive: study -> {t: [(sha, rel, dims)]}
    split_index = defaultdict(lambda: defaultdict(list))
    for r in inv:
        if r["role_guess"] == "image_split" and r["ext"] == ".mhd":
            m = SPLIT_RE.match(r["name"])
            if m:
                st = split_study(m.group("study"), by_session)
                split_index[st][int(m.group("t"))].append((r["sha256"], r["relpath"], hdr.get(r["sha256"], {}).get("dims", "")))
    # raw Bruker study folders present on the drive (for "could be made traceable by ingesting it")
    drive_study_raw = defaultdict(lambda: {"dicom": 0, "2dseq": 0})
    for parent, files in folders.items():
        comps = parent.split("\\")
        for i, c in enumerate(comps):
            st = C.study_tokens(c)
            if st and i + 1 < len(comps):
                for name, _, _, _ in files:
                    if name.lower().endswith(".dcm") and "pdata" in comps:
                        drive_study_raw[st[0]]["dicom"] += 1
                    elif name == "2dseq":
                        drive_study_raw[st[0]]["2dseq"] += 1
                break

    labels = []
    for r in inv:
        h = hdr.get(r["sha256"])
        kind = (h or {}).get("kind", "")
        is_label = kind in ("label", "label_empty") or r["role_guess"] in (
            "voi_pmod", "amira_labelfield", "annotation_ndp", "annotation_qupath")
        if r["role_guess"] == "amira_data" and "labelfield" in r["name"].lower():
            is_label = True
        if not is_label:
            continue
        labels.append((r, h or {}))

    ctx_cache = {}
    out = []
    sess_rows = {}
    ncc_todo = {}
    img_todo = {}
    for r, h in labels:
        rel, name, parent = r["relpath"], r["name"], r["parent"]
        set_id, set_desc = assign_set(rel, name, h)
        if parent not in ctx_cache:
            ctx_cache[parent] = folder_context(parent, folders, hdr, by_session)
        ctx = ctx_cache[parent]
        studies = set(filter(None, r["study_tokens"].split(";"))) | ctx["studies"]
        sessions = {norm_session(s) for s in r["session_tokens"].split(";") if s} | ctx["sessions"]
        rec = {"relpath": rel, "sha256": r["sha256"], "size": r["size"], "mtime": r["mtime"], "birthtime": r["birthtime"],
               "set_id": set_id, "set_desc": set_desc, "top": r["top"], "fmt": h.get("fmt", r["ext"]),
               "dims": h.get("dims", ""), "spacing": h.get("spacing", ""), "dtype": h.get("dtype", ""),
               "values": h.get("values", ""), "kind": h.get("kind", "label-format"), "phase": r["phase_from_name"],
               "reader_hints": r["reader_hints"], "project_codes_in_path": r["project_codes_in_path"],
               "studies": ";".join(sorted(studies)), "sessions": ";".join(sorted(sessions)),
               "trace_route": "none", "trace_level": "none", "acq_ids": "", "prod_study": "", "evidence": "", "why_not": ""}
        # 0. the label itself is a promoted DS-SEG file
        tw = twins.get(r["sha256"].lower())
        if tw:
            rec.update(trace_route="dsseg-twin", trace_level="acquisition", acq_ids=tw[1],
                       evidence=f"byte-identical to {tw[0]} {tw[2]} (session {tw[3]})")
        # 1. PET/CT-style: source DICOM beside the label
        if rec["trace_route"] == "none" and ctx["dcm"]:
            hit_sha, hit_name = [], []
            for dname, dsha, drel in ctx["dcm"]:
                a = sha2acq.get(dsha.lower())
                if a:
                    hit_sha.append(a)
                stem = dname[:-4]
                if stem in by_orig:
                    hit_name.append(by_orig[stem]["acq_id"])
            if hit_sha:
                rec.update(trace_route="sha-source", trace_level="acquisition", acq_ids=";".join(sorted(set(hit_sha))),
                           evidence=f"{len(hit_sha)} source DICOM beside the label byte-identical to production /raw/")
            elif hit_name:
                rec.update(trace_route="name-source", trace_level="acquisition", acq_ids=";".join(sorted(set(hit_name))),
                           evidence="source DICOM beside the label named exactly as production original_name (bytes differ or unindexed)")
            else:
                rec["why_not"] = "source DICOM beside the label (" + ",".join(d[0] for d in ctx["dcm"][:3]) + ") not in production by SHA-256 or name"
        # 1b. PET labels with no DICOM beside them: animal + protocol + date stated in the path
        if rec["trace_route"] == "none" and set_id in PET_SETS:
            animal, proto, date = pet_keys(rel)
            rec["evidence"] = f"path says animal={animal or '?'} protocol={proto or '?'} date={date or '?'}"
            if animal and proto:
                subj = f"{animal}-AE-biomaGUNE-{proto}"
                cands = [a for a in acqs if a["instrument"] in ("PET", "CT", "SPECT") and subj in a["subject_ids"].split(";")]
                dates = sorted({a["acquisition_datetime"][:10].replace("-", "") for a in cands})
                if date and date in dates:
                    ids = sorted(a["acq_id"] for a in cands if a["acquisition_datetime"][:10].replace("-", "") == date)
                    rec.update(trace_route="subject-date", trace_level="acquisition", acq_ids=";".join(ids),
                               evidence=rec["evidence"] + f"; production holds {subj} PET/CT on that date ({len(ids)} acqs); grid reference not verified")
                elif date:
                    rec["why_not"] = f"production has no PET/CT of {subj} on {date} (has: {','.join(dates) or 'none'})"
                elif dates:
                    rec["why_not"] = f"no date in the path; production holds {subj} PET/CT on {len(dates)} date(s) ({','.join(dates[:4])}) -- not chosen"
                else:
                    rec["why_not"] = f"production holds no PET/CT for {subj}"
            elif not rec["why_not"]:
                rec["why_not"] = "PET label: animal or protocol not stated in the path"
        # 2. MRI: study in production?
        prod_studies = sorted(s for s in studies if s in by_study)
        if not prod_studies and sessions:
            cand = sorted({a["study"] for s in sessions for a in by_session.get(s, []) if a.get("study")})
            if len(cand) == 1:
                prod_studies = cand
                rec["evidence"] += (" | " if rec["evidence"] else "") + "study via session_id token"
            elif len(cand) > 1:
                rec["why_not"] = f"session token matches {len(cand)} production studies: " + ",".join(cand[:4])
        if len(prod_studies) > 1:
            rec["why_not"] = "label folder names several production studies: " + ",".join(prod_studies[:4])
        # DS-SEG twins: their trace comes from the dataset, but if this drive holds the split volumes of the
        # stack, queue an independent pixel check of the dataset's slice map (a3_slicemap_check.py reads it)
        if rec["trace_route"] == "dsseg-twin" and len(prod_studies) == 1:
            d3 = h.get("dims", "").split("x")[:3]
            sp = split_index.get(prod_studies[0], {})
            if any(dd.split("x")[:3] == d3 for lst in sp.values() for (_, _, dd) in lst):
                key = (prod_studies[0], "x".join(d3))
                ncc_todo.setdefault(key, {"study": prod_studies[0], "dims": "x".join(d3), "n_labels": 0, "split_examples": "dsseg-check"})
                ncc_todo[key]["n_labels"] += 1
        # NIfTI exam conversions beside the label with identical dims + affine (whatever the study status)
        la = norm_affine(h.get("affine", ""))
        img_hits = [(e, p, proto, s) for e, p, proto, s, hh in ctx["nifti_imgs"]
                    if la and hh.get("dims", "").split("x")[:3] == h.get("dims", "").split("x")[:3] and norm_affine(hh.get("affine", "")) == la]
        rec["img_hit_shas"] = ";".join(sorted({s for _, _, _, s in img_hits}))
        if img_hits and not prod_studies and rec["trace_route"] == "none":
            # no production study named: the beside-image can still be matched by pixels (a3_imgmatch.py)
            animal, proto, _ = pet_keys(rel)
            m = re.search(r"(?i)(?:^|[_\-\s\\])m(\d{1,3})(?=[_\-\s.\\])", parent + "\\" + name)
            animal = m.group(1) if m else animal
            codes = re.findall(r"(?<!\d)([01]\d{3})(?!\d)", parent.split("\\")[-1] + " " + name) or \
                [c for c in r["project_codes_in_path"].split(";") if c]
            rec["trace_route"], rec["trace_level"] = "image-ncc-pending", "pending"
            rec["evidence"] = f"label dims+affine equal {len(img_hits)} NIfTI exam conversion(s) beside it; no study token -> pixel match"
            for e, p, prt, s in img_hits:
                key = (s, animal, codes[0] if codes else "")
                img_todo.setdefault(key, {"image_sha": s, "image_relpath": next(rr for nn, ss, _, rr in folders[parent] if ss == s),
                                          "exam_in_name": e, "animal": animal, "protocol": codes[0] if codes else "", "n_labels": 0})
                img_todo[key]["n_labels"] += 1
        if len(prod_studies) == 1 and rec["trace_route"] in ("none",):
            st = prod_studies[0]
            rec["prod_study"] = st
            rows = by_study[st]
            rec["trace_route"], rec["trace_level"] = "session-only", "session"
            rec["acq_ids"] = ""
            # 2a. NIfTI exam conversions with identical geometry
            la = norm_affine(h.get("affine", ""))
            hits = [(e, p, proto) for e, p, proto, s, hh in ctx["nifti_imgs"]
                    if hh.get("dims", "").split("x")[:3] == h.get("dims", "").split("x")[:3] and norm_affine(hh.get("affine", "")) == la]
            if hits and la:
                exams = sorted({e for e, _, _ in hits})
                ids = [by_orig[f"{st}/{e}"]["acq_id"] for e in exams if f"{st}/{e}" in by_orig]
                if len(exams) == 1 and ids:
                    rec.update(trace_route="nifti-exam", trace_level="acquisition", acq_ids=ids[0],
                               evidence=f"dims+affine equal the NIfTI conversion of exam {exams[0]} ({hits[0][2]}) in the same folder")
                elif len(exams) > 1 and len(ids) == len(exams):
                    # e.g. a flow measurement: magnitude cine + velocity map, two exams on the identical slice
                    rec.update(trace_route="nifti-exam-group", trace_level="acquisition-group", acq_ids=";".join(ids),
                               evidence=f"dims+affine equal the conversions of {len(exams)} exams ({','.join(hits[i][2] + '#' + str(hits[i][0]) for i in range(len(hits)))[:160]}) "
                                        "sharing one slice geometry: the label is spatially valid on all; which one the analyst drew on is not recorded")
                elif len(exams) > 1:
                    rec["why_not"] = f"geometry matches exams {exams[:6]} but only {len(ids)} are production original_names"
                elif not ids:
                    rec["why_not"] = f"geometry matches exam {exams[0]} but '{st}/{exams[0]}' is not a production original_name"
            # 2b. cine split stack
            if rec["trace_route"] == "session-only":
                d3 = h.get("dims", "").split("x")[:3]
                sp = split_index.get(st, {})
                same = sorted({t for t, lst in sp.items() for (_, _, dd) in lst if dd.split("x")[:3] == d3})
                if same:
                    rec["trace_route"] = "cine-split"
                    rec["evidence"] = f"label dims {'x'.join(d3)} equal the split volumes of {st} (phases {same[:3]}..)"
                    key = (st, "x".join(d3))
                    ncc_todo.setdefault(key, {"study": st, "dims": "x".join(d3), "n_labels": 0,
                                              "split_examples": ";".join(f"{t}:{lst[0][1]}" for t, lst in sorted(sp.items()) if t in (1, 8, 15))})
                    ncc_todo[key]["n_labels"] += 1
                    rec["acq_ids"] = "pending-ncc"
                elif sp:
                    rec["why_not"] = f"split volumes of {st} exist on the drive but none has the label's dims {'x'.join(d3)}"
                else:
                    rec["why_not"] = "no split volume of this study on the drive; stack unresolved without the analyst"
            srow = sess_rows.setdefault(st, {"study": st, "in_production": "Y", "n_label_files": 0,
                                             "prod_acqs": len(rows), "prod_igflash": sum(1 for a in rows if a["method"] == "IgFLASH"),
                                             "project_id": ";".join(sorted({a["project_id"] for a in rows if a["project_id"]})),
                                             "sets": set()})
            srow["n_label_files"] += 1
            srow["sets"].add(set_id)
        elif rec["trace_route"] == "none":
            # record the studies named but absent from production, with raw availability on this drive
            for st in sorted(studies):
                srow = sess_rows.setdefault(st, {"study": st, "in_production": "N", "n_label_files": 0, "prod_acqs": 0,
                                                 "prod_igflash": 0, "project_id": "", "sets": set()})
                srow["n_label_files"] += 1
                srow["sets"].add(set_id)
                dr = drive_study_raw.get(st, {})
                srow["drive_raw_dicom_files"] = dr.get("dicom", 0)
                srow["drive_raw_2dseq_files"] = dr.get("2dseq", 0)
            if not rec["why_not"]:
                if studies:
                    yrs = sorted({s[:4] for s in studies})
                    rec["why_not"] = f"study not in production ({';'.join(sorted(studies))[:120]}); year {','.join(yrs)}"
                elif sessions:
                    rec["why_not"] = "session token(s) not in production: " + ";".join(sorted(sessions))[:120]
                else:
                    rec["why_not"] = "no study / session token in the path"
        out.append(rec)

    C.write_csv(os.path.join(C.OUT_DIR, "a3_labels.csv"), out)
    srows = []
    for s in sess_rows.values():
        s = dict(s)
        s["sets"] = ";".join(sorted(s["sets"]))
        srows.append(s)
    C.write_csv(os.path.join(C.OUT_DIR, "a3_label_sessions.csv"), sorted(srows, key=lambda x: x["study"]))
    C.write_csv(os.path.join(C.OUT_DIR, "a3_cine_ncc_todo.csv"), list(ncc_todo.values()))
    C.write_csv(os.path.join(C.OUT_DIR, "a3_img_todo.csv"), list(img_todo.values()),
                ["image_sha", "image_relpath", "exam_in_name", "animal", "protocol", "n_labels"])
    c = Counter((o["set_id"], o["trace_route"]) for o in out)
    print(f"labels {len(out)} (distinct sha {len({o['sha256'] for o in out})}); sessions {len(srows)}; ncc todo {len(ncc_todo)}")
    for k, v in sorted(c.items()):
        print(f"  {k[0]:24s} {k[1]:14s} {v}")


if __name__ == "__main__":
    main()
