"""Stream AR, step 9: write the batch ingest configs (tools/configs/mri_archive/) from one template.

    python ar_08_configs.py

Every batch config is the same except its header, staging dir, case table and subject block; every per-exam value
comes from the case table (ar_07_cases.py), so no regex decides anything. operator is pending-claim (the historical
MRI hold, STATUS 0.5); researcher blank. Also writes the dedup-proof config (dry run only; guarded).
"""
import collections
import os
import sys
import textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ar_common as C  # noqa: E402

HEAD = """{what}
# Gate: tasks/mri_archive_ingest_gate.md. Census: tasks/mri_archive_census.md. Rulings: tasks/STATUS.md 0.5 (Hold), 0.6.
#
# SOURCE: the MRI platform's archive (mriuser@10.10.3.175 backup_7T_olddata_260824), pulled to LOCAL disk by
# tools/mri_archive.py fetch (each tarball SHA-1-verified) and extracted by tools/drive_staging/mri_archive/
# ar_01_extract.py (k-space excluded; every file hashed) to a FLAT tree on D::
#     D:/projects/gjesus3/mri_archive/extract/{b}/<study>/<exam>/
# so original_name = "<study>/<exam>", the shape of every production MRI row (the staging_dir trap), dated by
# VisuCreationDate as production: an exam already registered (e.g. from the M. Jesus drive) is skipped, never
# registered twice. Convert-first (Ryan, 2026-10-04): every exam in the case table holds DICOM (the scanner's own, or
# Dicomifier's, made in this extract tree before ingest). Exams NOT in the case table (spectroscopy, no reconstruction,
# never acquired, failed conversion) are skipped by name (on_missing: skip) and listed for a placement batch.
#
# PER-EXAM VALUES come from the case table (ar_07_cases.py):
#   drv_acq_datetime = exam visu_pars VisuCreationDate (production's rule), else acqp ACQ_time; never today
#   drv_model        = Bruker BioSpec 7T (Biospec 70/30), set explicitly
#   drv_alias / drv_animal / drv_sample / drv_sample_type / drv_session / drv_project / drv_hhmm / drv_note
# operator = pending-claim: historical internal MRI, listed in the claim workbook (STATUS 0.5, Ryan 2026-10-07).
#
# Dry run (read-only):
#   python tools/ingest_raw.py --config tools/configs/mri_archive/{name}.yaml --nas-root J:/gjesus3-data --dry-run
"""

BODY = """
ingest:
  delete_source_after_ingest: false
  auto_create_projects: false             # every target project exists (0220 is reopened first, Q5)
  acquisition_layout: folder
  copy_strategy: mri_paravision_v2        # DICOMs only
  reconstructions: all

auto_discover:
  staging_dir: "D:/projects/gjesus3/mri_archive/extract/{b}"
  pattern: "*/[0-9]*"
  case_table:
    file:       cases_{b}.csv
    key:        original_name
    on_missing: skip                      # the exams not registered (listed in out/not_registered*.csv)
{subject}
registry:
  instrument:           MRI
  data_ecosystem:       DICOM
  instrument_model:     "${{discovered.drv_model}}"
  modalities_in_study:  NA
  researcher:           "NA"
  data_source:          internal
  sample_id:            "${{discovered.drv_sample}}"
  sample_type:          "${{discovered.drv_sample_type}}"
  session_id:           "${{discovered.drv_session}}"
  acquisition_datetime: discovered.drv_acq_datetime
  project_name:         "${{discovered.drv_project}}"
  notes:                "Internal MRI ${{discovered.mri_sequence_name}} exam ${{discovered.mri_exam_number}}; recons kept: ${{discovered.mri_recon_indices}}; ${{discovered.drv_note}}"

operator: "pending-claim"
{link}"""

LINK = """
# Project link name: the MRI convention of 2026-10-05, MRI_<sample>_<YYYYMMDD>_<HHMM>_<exam>_<recons> (HHMM = the study
# start), so two sessions of one animal on one day never collide. Checked unique and free by ar_07_cases.py.
link_filename: "MRI_${sample_id}_${acq_date}_${discovered.drv_hhmm}_${discovered.mri_exam_number}_${discovered.mri_recon_indices}"
"""

SUBJ_DB = """  subject_from_db: true
  subject_lookup:
    project_alias: "${discovered.drv_alias}"
    animal_code:   "${discovered.drv_animal}"
"""
SUBJ_NONE = """  subject_from_db: false                  # no facility id is asserted for these studies (see the gate)
"""

DEDUP = """# The MRI platform's archive (stream AR): DEDUP PROOF (DRY RUN ONLY -- never run for real; guarded below).
# Gate: tasks/mri_archive_ingest_gate.md. The 130 tier-C studies are the M. Jesus drive's (stream M), registered from
# the drive on 2026-10-07. Every exam of them that production holds, extracted from the ARCHIVE the same way as the
# batches (flat <study>/<exam>) and dated by the SAME rule (cases_DEDUP.csv): the dry run must list NONE and skip every
# one "already in registry (idempotent re-run)". The other exams of those studies (no row) are skipped by name.
# GUARD: copy_strategy below does not exist. A dry run never reaches the copy; a real run would fail every case at the
# copy step, before anything is registered.
#   python tools/ingest_raw.py --config tools/configs/mri_archive/mri_archive_dedup_proof.yaml --nas-root J:/gjesus3-data --dry-run

ingest:
  delete_source_after_ingest: false
  auto_create_projects: false
  acquisition_layout: folder
  copy_strategy: dedup_proof_never_run_for_real
  reconstructions: all

auto_discover:
  staging_dir: "D:/projects/gjesus3/mri_archive/extract/C"
  pattern: "*/[0-9]*"
  case_table:
    file:       cases_DEDUP.csv
    key:        original_name
    on_missing: skip
  subject_from_db: false

registry:
  instrument:           MRI
  data_ecosystem:       DICOM
  instrument_model:     "Bruker BioSpec 7T"
  modalities_in_study:  NA
  researcher:           "NA"
  data_source:          internal
  sample_id:            "dedup-proof"
  sample_type:          organism
  session_id:           ""
  acquisition_datetime: discovered.drv_acq_datetime
  project_name:         ""
  notes:                "DEDUP PROOF, never registered"

operator: "NA"
"""


def describe(b, ss):
    proj = collections.Counter(s["project_name"] or "(no project)" for s in ss)
    tiers = collections.Counter(s["tier"] for s in ss)
    years = sorted({s["study"][:4] for s in ss})
    extra = {
        "AR03_0220": " AE-biomaGUNE-0220 is CLOSED today: the coordinator reopens it (tools/reopen_project.py, Q5) "
                     "before this batch runs.",
        "AR13_noproject": " No project (STATUS 0.6 Q4 for 0917/0116/1316; no code and no unique DB answer; or the DB "
                          "contradicts the claim); no subject id. Listed for the assign workbook.",
        "AR14_phantoms": " Phantoms / QC (STATUS 0.6 Q2), as July's jrc phantoms: no project, no subject id.",
    }.get(b, "")
    if b[4:5] == "n":
        extra = (" Studies of this project WITHOUT a subject id: the name's animal is not in the facility DB under "
                 "this protocol, or has no plain number (as stream M's M09).")
    return (f"The MRI platform's archive (stream AR), batch {b}: {len(ss)} studies "
            f"({', '.join(f'{k} {v}' for k, v in sorted(tiers.items()))}), {years[0]}-{years[-1]}; "
            f"{', '.join(f'{k} {v}' for k, v in proj.items())}.{extra}")


def main():
    studies = C.rows(os.path.join(C.OUT, "plan_studies.csv"))
    by = collections.defaultdict(list)
    for s in studies:
        if int(s["register_c"]) + int(s["convert_d"]):
            by[s["batch"]].append(s)
    os.makedirs(C.CFG_DIR, exist_ok=True)
    for b, ss in sorted(by.items()):
        name = f"mri_archive_{b}"
        subj = {bool(s["alias"]) for s in ss}
        if len(subj) != 1:
            raise SystemExit(f"{b}: mixes studies with and without a subject id")
        has_proj = {bool(s["project_name"]) for s in ss}
        what = textwrap.fill(describe(b, ss), 116, initial_indent="# ", subsequent_indent="# ")
        text = HEAD.format(b=b, what=what, name=name) + BODY.format(
            b=b, subject=SUBJ_DB if subj == {True} else SUBJ_NONE, link=LINK)
        if has_proj != {True} and has_proj != {False}:
            raise SystemExit(f"{b}: mixes studies with and without a project")
        with open(os.path.join(C.CFG_DIR, name + ".yaml"), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print("wrote", name)
    with open(os.path.join(C.CFG_DIR, "mri_archive_dedup_proof.yaml"), "w", encoding="utf-8", newline="\n") as f:
        f.write(DEDUP)
    print("wrote mri_archive_dedup_proof")


if __name__ == "__main__":
    main()
