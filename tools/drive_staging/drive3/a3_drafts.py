"""A3 step 12 -- DRAFT _dataset.yaml + provenance.csv for each candidate set (read-only; writes only to a3\\drafts).

Promotes nothing and writes nothing under curated_datasets\\. Each draft follows the shape of the promoted
DS-SEG-0003/0004 files (their provenance columns, plus the drive-specific ones). Only labels traced to
production acquisitions enter a draft's provenance.csv; everything else stays listed in a3_labels_distinct.csv.

Candidates (one label schema each -- the value orders differ, so they are never mixed):
  CAND-A  mouse cardiac cine, 0/1/2 maps: 1 = LV blood pool, 2 = RV blood pool (topology + shape, measured)
  CAND-B  mouse cardiac cine, 0-4 maps in the ITK-SNAP 'LV Endo / LV Epi / RV Endo / RV Epi' order
  CAND-C  mouse cardiac cine, 0-4 'Massventricles' order: 1 LV cavity, 2 RV cavity, 3 LV myocardium, 4 RV wall
  CAND-D  mouse great-vessel flow ROIs (pulmonary artery; some aorta), one ROI per cardiac frame
  CAND-E  mouse organ masks on Molecubes PET/CT (NIfTI, values 1-3; meanings NOT recorded)
  CAND-F  mouse cardiac cine, 0/1/2 maps of the 1519 cohort: 1 = LV cavity, 2 = LV myocardium (NOT LV/RV)
Schema per file comes from a3_schema_by_cohort.classify (measured topology), never from the value set alone.
"""
import os
import re
import sys
from collections import Counter, defaultdict

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a3_common as C  # noqa: E402

TRACED = ("acquisition", "acquisition-stack", "acquisition-stack-geometry", "acquisition-group")
OUT = os.path.join(C.OUT_DIR, "drafts")


from a3_schema_by_cohort import classify  # noqa: E402  (one classifier for the report and the drafts)

SCHEMA_TO_CAND = {"LVRV-pools": "A", "4C-endo-epi": "B", "4C-mass": "C", "LV-endo-epi": "F"}


def topo_class(rows):
    """rows: topology rows of one file -> candidate letter, from the measured schema (a3_schema_by_cohort)."""
    v = {int(r["value"]): r for r in rows if r.get("value")}
    return SCHEMA_TO_CAND.get(classify(v), "other") if v else "other"


CANDS = {
    "CAND-A": dict(short="mouse-cardiac-cine-lvrv-bloodpool-drive3-draft", sets={"S-CINE-LVRV", "S-CINE-MASS"},
                   desc="Manual left- and right-ventricle masks of mouse self-gated cine MRI (Bruker IgFLASH, 7T), one label volume per cardiac phase, traced in ITK-SNAP on per-phase split volumes. 0/1/2 map.",
                   classes={0: "background/unlabelled", 1: "LV blood pool (cavity)", 2: "RV blood pool (cavity)"},
                   evidence="MEASURED on every file (a3_label_topology.csv): labels 1 and 2 are solid, separate regions that each touch the outside background along ~all their boundary (never a ring, never touching each other: the septum between them is unlabelled) -> cavities, not myocardium; label 1 is round (solidity ~0.95), label 2 crescent-shaped (~0.75) -> LV and RV. Same result on the 168 drive files byte-identical to DS-SEG-0004.",
                   process="Manual LV/RV blood-pool segmentation of a self-gated cine (IgFLASH) short-axis stack, traced on the per-phase split image volume; one label volume per cardiac phase; label 1=LV cavity, 2=RV cavity, 0=background"),
    "CAND-B": dict(short="mouse-cardiac-cine-endoepi-4class-drive3-draft", sets={"S-CINE-LVRV"},
                   desc="Manual 4-class ventricle masks of mouse self-gated cine MRI, ITK-SNAP 'LV Endo / LV Epi / RV Endo / RV Epi' palette, one volume per cardiac phase.",
                   classes={0: "background", 1: "LV Endo (LV cavity)", 2: "LV Epi (LV myocardium ring)", 3: "RV Endo (RV cavity)", 4: "RV Epi (RV free wall)"},
                   evidence="NAMES from the ITK-SNAP label description 'Segmentation Labels.label' found 3x on the drive (same SHA-256); GEOMETRY measured: label 1 lies inside label 2's filled outline (1_inside_2 = 1.000 median), 2 is a ring, 3 is nearly enclosed, 4 is a thin wall.",
                   process="Manual 4-class LV/RV endocardial + epicardial segmentation of a self-gated cine short-axis stack, ITK-SNAP label palette LV Endo/LV Epi/RV Endo/RV Epi, one label volume per cardiac phase"),
    "CAND-C": dict(short="mouse-cardiac-cine-massventricles-drive3-draft", sets={"S-CINE-MASS", "S-CINE-LVRV"},
                   desc="Manual 'Massventricles' masks of mouse self-gated cine MRI (myocardial mass analysis), usually at end-diastole/end-systole phases only.",
                   classes={0: "background", 1: "LV cavity", 2: "RV cavity", 3: "LV myocardium (ring around 1)", 4: "RV free wall"},
                   evidence="MEASURED, not named anywhere: label 1 lies inside label 3's outline (1_inside_3 = 0.955 median), 2 is nearly enclosed (exterior contact 0.08), 3 is a ring, 4 a thin crescent. NOT the CAND-B order -- never merge the two. The 8 drive files byte-identical to DS-SEG-0004's readerA_massventricles masks show the same pattern, as do the 2 files DS-SEG-0004 excluded as 'probably mis-named Massventricles'.",
                   process="Manual myocardial-mass ('Massventricles') segmentation of a self-gated cine short-axis stack: LV/RV cavities and LV myocardium / RV wall"),
    "CAND-D": dict(short="mouse-flow-roi-mpa-aorta-drive3-draft", sets={"S-FLOW-ROI"},
                   desc="Manual great-vessel ROIs (main pulmonary artery; some aorta) on mouse phase-contrast flow MRI (cine magnitude + velocity map, one slice), one ROI per cardiac frame stored as slice z = frame with value = frame number.",
                   classes={0: "background", "1..N": "vessel lumen ROI at cardiac frame N (value = frame index)"},
                   evidence="MEASURED: values 1..20 exactly equal the third dimension (20 frames); structure from the file name (MPA / aorta). Each ROI's dims + affine equal the NIfTI conversions of BOTH the cine magnitude and the velocity-map exams of the same slice (acquisition-group).",
                   process="Manual ROI of the vessel lumen per cardiac frame on phase-contrast flow MRI, for flow quantification"),
    "CAND-F": dict(short="mouse-cardiac-cine-lv-endoepi-1519-drive3-draft", sets={"S-CINE-LVRV"},
                   desc="Manual LV-only masks of mouse self-gated cine MRI from the 1519 post-surgery cohort (2020): LV cavity and LV myocardium, one volume per cardiac phase. SAME value set as CAND-A, DIFFERENT meaning.",
                   classes={0: "background", 1: "LV cavity (endocardium)", 2: "LV myocardium (ring between endo- and epicardium)"},
                   evidence="MEASURED: label 1 is fully enclosed (exterior contact 0.0) inside label 2's outline; label 2 is a ring. All 833 0/1/2 masks of the 1519 2020 cohort follow this schema; only 59 trace to production today.",
                   process="Manual LV endocardial + epicardial segmentation (LV cavity, LV myocardium) of a self-gated cine short-axis stack, one label volume per cardiac phase"),
    "CAND-E": dict(short="mouse-petct-organ-masks-drive3-draft", sets={"S-PETCT-MASK"},
                   desc="Organ masks (NIfTI) drawn on Molecubes PET/CT exports (SUV and CT resampled to the CT grid), one mask volume per animal session.",
                   classes={0: "background", 1: "UNKNOWN", 2: "UNKNOWN", 3: "UNKNOWN"},
                   evidence="Label meanings are NOT recorded anywhere on the drive; folder siblings (VOI stats, 'Lungs-ID136' files) suggest thoracic organs. Must come from the analyst.",
                   process="Manual organ segmentation on PET/CT exports (SUV + CT on the CT grid)"),
}


def main():
    os.makedirs(OUT, exist_ok=True)
    D = C.read_csv_dicts(os.path.join(C.OUT_DIR, "a3_labels_distinct.csv"))
    topo = defaultdict(list)
    for r in C.read_csv_dicts(os.path.join(C.OUT_DIR, "a3_label_topology.csv")):
        topo[r["sha256"]].append(r)
    vers = defaultdict(list)
    for p in C.read_csv_dicts(os.path.join(C.OUT_DIR, "a3_versions_pairs.csv")):
        vers[p["sha_a"]].append((p["relation"], p["dice_mean"], p["sha_b"]))
        vers[p["sha_b"]].append((p["relation"], p["dice_mean"], p["sha_a"]))
    dsseg = {r["sha256"] for r in D if "DS-SEG" in r["overlap"]}
    bulk_days = {k for k, v in Counter(d["earliest_mtime"][:10] for d in D).items() if v >= 50}
    stack_note = {}
    for r in C.read_csv_dicts(os.path.join(C.OUT_DIR, "a3_geostack.csv")):
        stack_note[r["study"]] = r["note"]

    assign = defaultdict(list)
    for d in D:
        if d["final_level"] not in TRACED or d["kind"] != "label":
            continue
        if d["set_id"] in ("S-CINE-LVRV", "S-CINE-MASS"):
            t = topo_class(topo.get(d["sha256"], []))
            if t in ("A", "B", "C", "F"):
                assign["CAND-" + t].append((d, t))
        elif d["set_id"] == "S-FLOW-ROI":
            assign["CAND-D"].append((d, ""))
        elif d["set_id"] == "S-PETCT-MASK":
            assign["CAND-E"].append((d, ""))

    summary = []
    for cand, spec in CANDS.items():
        rows = assign.get(cand, [])
        prov = []
        sessions, subjects, acq_all, projects = set(), set(), set(), Counter()
        for d, t in sorted(rows, key=lambda x: (x[0]["prod_session"], x[0]["phase"], x[0]["sha256"])):
            ids = d["final_acq_ids"].split(";")
            sessions.add(d["prod_session"])
            subjects.update(s for s in d["prod_subject"].split(";") if s)
            acq_all.update(ids)
            projects[d["prod_project_name"] or "(no project_id in registry_raw: 2021 Proyecto 1019 pull)"] += 1
            flags = []
            if d["sha256"] in dsseg:
                flags.append("already-in-DS-SEG (byte-identical)")
            if d["final_level"] == "acquisition-stack-geometry":
                flags.append("slice-order-unverified")
            if d["final_level"] == "acquisition-group":
                flags.append("valid-on-N-exams")
            v = vers.get(d["sha256"], [])
            if v:
                flags.append("other-versions:" + ",".join(sorted({x[0] for x in v})))
            if d["earliest_mtime"][:10] in bulk_days:
                flags.append("mtime-on-bulk-day")
            if not d["phase"] and cand in ("CAND-A", "CAND-B", "CAND-C"):
                flags.append("no-phase-in-name")
            phase = int(d["phase"]) if d["phase"].isdigit() else 0
            sess = d["prod_session"] or "unknown"
            name = os.path.basename(d["example_relpath"])
            ext = ".nii.gz" if name.lower().endswith(".nii.gz") else os.path.splitext(name)[1].lower()
            prov.append({
                "file_path": f"masks/{sess}/{sess}_phase{phase:02d}_{d['sha256'][:8]}{ext}" if cand != "CAND-E" else f"masks/{sess}/{sess}_{d['sha256'][:8]}{ext}",
                "file_role": "label", "label_format": ext, "label_origin": "manual (inferred; no record)",
                "session_id": d["prod_session"], "subject_id": d["prod_subject"], "timepoint": "unknown",
                "phase_index": d["phase"], "acq_id": ids[0], "acq_ids_all": ";".join(ids),
                "exam_match_method": d["verification"], "slice_order_verified":
                    "direct-ncc" if d["final_level"] == "acquisition-stack" else ("no" if d["final_level"] == "acquisition-stack-geometry" else "n/a"),
                "geometry_reference_status": {"acquisition-stack": "stack-of-per-slice-acquisitions", "acquisition-stack-geometry": "stack-of-per-slice-acquisitions",
                                              "acquisition-group": "one-slice, several exams", "acquisition": "single acquisition"}[d["final_level"]],
                "creator": ("folder/file-attributed:" + d["reader_hints"] + " (UNCONFIRMED)") if d["reader_hints"] else "unknown",
                "date_created": d["earliest_mtime"], "date_created_precision": "file-mtime (earliest copy)" + ("; bulk-copy day" if d["earliest_mtime"][:10] in bulk_days else ""),
                "process_description": spec["process"], "producing_tool": "ITK-SNAP (inferred)" if cand != "CAND-E" else "unknown",
                "tool_version": "unknown", "review_status": "unknown",
                "source_filename": name, "source_path_original": "drive3:" + d["example_relpath"], "sha256": d["sha256"],
                "copies_on_drive": d["copies"], "values": d["values"], "dims": d["dims"], "spacing": d["spacing"],
                "schema_check": t, "other_versions": ";".join(f"{x[0]}:{x[1]}:{x[2][:8]}" for x in v)[:300],
                "quality_flag": ";".join(flags), "drives12_placed_or_held": "Y" if "drives12" in d["overlap"] else "N",
                "prod_project": d["prod_project_name"],
            })
        cdir = os.path.join(OUT, cand)
        os.makedirs(cdir, exist_ok=True)
        C.write_csv(os.path.join(cdir, "provenance.csv"), prov)
        n_new = sum(1 for p in prov if "already-in-DS-SEG" not in p["quality_flag"])
        y = []
        y.append(f"# DRAFT -- produced by tools/drive_staging/drive3/a3_drafts.py on drive-3 evidence. NOT promoted, NOT registered.")
        y.append(f"dataset_id: (to be assigned at promotion: next DS-SEG-NNNN)")
        y.append(f"short_name: {spec['short']}")
        y.append("description: |")
        for line in wrap(spec["desc"]):
            y.append("  " + line)
        y.append("dataset_type: segmentation")
        y.append("data_ecosystem: DICOM")
        y.append("version: v0.1-draft")
        y.append("owner: (curator at promotion -- Data Management Lead)")
        y.append("created_date: (at promotion)")
        y.append(f"sample_unit: \"{'animal-session cine stack, one label volume per phase' if cand in ('CAND-A','CAND-B','CAND-C') else ('one flow slice x all cardiac frames' if cand=='CAND-D' else 'one animal PET/CT session')}\"")
        y.append(f"label_file_count: {len(prov)}   # distinct files (SHA-256); {n_new} not already in a promoted dataset")
        y.append(f"sessions: {len(sessions)}")
        y.append(f"subject_count: {len(subjects)}")
        y.append(f"source_acquisition_count: {len(acq_all)}")
        y.append("source_projects: " + "; ".join(f"{k} ({v})" for k, v in projects.most_common()))
        y.append("label_formats: [" + ", ".join(sorted({p['label_format'] for p in prov})) + "]")
        y.append("label_classes:")
        for k, v in spec["classes"].items():
            y.append(f"  {k}: {v}")
        y.append("label_classes_evidence: |")
        for line in wrap(spec["evidence"]):
            y.append("  " + line)
        y.append("annotation_tool: " + ("ITK-SNAP (version unknown; inferred from the uint16 / qform-1 save signature, the ITK-SNAP label file and the folder 'Segmentaciones ITK SNAP' -- no header records a tool)" if cand != "CAND-E" else "unknown"))
        y.append("creator: unknown   # per-file reader hints in provenance.csv are folder/file-name attributions, NOT confirmed")
        y.append("review_status: unknown")
        qf = Counter(f.split(":")[0] for p in prov for f in p["quality_flag"].split(";") if f)
        y.append("quality_flags_count: " + "; ".join(f"{k}: {v}" for k, v in qf.most_common()))
        y.append("status: draft")
        y.append("missing_before_promotion: |")
        for line in MISSING[cand]:
            y.append("  - " + line)
        with open(os.path.join(cdir, "_dataset.yaml"), "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(y) + "\n")
        summary.append({"candidate": cand, "short_name": spec["short"], "label_files": len(prov), "not_in_dsseg": n_new,
                        "sessions": len(sessions), "subjects": len(subjects), "acquisitions": len(acq_all),
                        "projects": "; ".join(f"{k} ({v})" for k, v in projects.most_common()),
                        "flags": "; ".join(f"{k}: {v}" for k, v in qf.most_common())})
    C.write_csv(os.path.join(OUT, "drafts_summary.csv"), summary)
    for s in summary:
        print(s)


def wrap(text, width=100):
    words, line, out = text.split(), "", []
    for w in words:
        if len(line) + len(w) + 1 > width:
            out.append(line)
            line = w
        else:
            line = (line + " " + w).strip()
    if line:
        out.append(line)
    return out


MISSING = {
    "CAND-A": ["Creator(s) confirmed by name (hints only: 'MJ' file/folder names, 'IRE', 'IF'); several sessions carry 2+ readers.",
               "Choose per (session, phase): which version is final (a3_versions_pairs.csv: 'Inicial' vs 'Revision' folders in 1121, IRE vs MJ in 0522-2023) or keep them as readers, as DS-SEG-0004 did.",
               "Quality review: no review record exists; the 1121 'Revision' folders are the only evidence of one.",
               "Timepoint per session (folder hints only: 'Mes 10', 'Basal', ...).",
               "Slice order for the geometry-only stacks (0320, part of 0619 2022): split volumes are not on the drive; ask the analyst or accept order_verified = no as DS-SEG-0001 did.",
               "Decide extend-vs-new for the files on DS-SEG-0001/0004 sessions (new readings of already-curated stacks)."],
    "CAND-B": ["As CAND-A; plus confirm the ITK-SNAP palette (1 LV Endo, 2 LV Epi, 3 RV Endo, 4 RV Epi) applied to these files -- the topology agrees.",
               "Most 4-class masks are 2020 and untraced (studies not in production): this draft holds only the traced minority."],
    "CAND-C": ["Confirm the Massventricles value meanings with the analyst -- here they are MEASURED from geometry, not recorded.",
               "Which phases (end-diastole / end-systole) each file is."],
    "CAND-D": ["Which exam each ROI was drawn on (magnitude cine or velocity map): both share the slice, so the ROI is spatially valid on both (acquisition-group).",
               "Structure per file where the name does not say (20 unnamed); 'without artefact' variants: which one is final.",
               "Creator, tool and review."],
    "CAND-F": ["Only 59 of 833 such masks trace today: the other 1519 2020 sessions are not in production (raw on this drive for some, see a3_unlock_studies.csv).",
               "Confirm the LV-only meaning with the analyst; creator, review and timepoint ('Semana 2' etc. from folders)."],
    "CAND-E": ["Label meanings (values 1-3) -- NOT recorded anywhere; mandatory before promotion.",
               "Relationship to DS-SEG-0002 (PMOD VOIs on many of the same sessions): extend it (its planned v1.1 is NIfTI masks) or keep separate.",
               "Creator, tool, review; which grid (CT) each mask is on -- the exports are on the CT grid, not checked per file."],
}

if __name__ == "__main__":
    main()
