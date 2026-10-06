"""Stream M, step 6: write the batch ingest configs (tools/configs/drive3_mri/) from one template.

    python mri_05_configs.py

Every batch config is the same except its header, staging dir and case table; every per-exam value (date, animal,
protocol alias, sample, session, project, scanner model, note) comes from the case table that mri_04_cases.py built
from the staged exam, so no regex decides anything (57 of the 190 studies parse with neither production regex).
"""
import os
import sys
import textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mri_common as C  # noqa: E402

BATCHES = [
    ("M01", "drive3_mri_M01_0118", "protocol 0118 (rats, hypoxia and monocrotaline PAH models), 2019-09 / 2020-06 / "
     "2021-09, 27 studies; all to AE-biomaGUNE-0118 (Ryan, 2026-10-06, M1). m175/m178 (Ermal, 2021-09-02): the "
     "reconstruction byte-identical to K:\\gjesus\\MRI\\Proyecto 0118 (A1 R2). The facility DB holds a NULL alias for "
     "0118: animal_db composes from the caller's alias, so subject ids are <n>-AE-biomaGUNE-0118, never -None.", True),
    ("M02", "drive3_mri_M02_0619_2020", "protocol 0619, 2020 (hypoxia; flow studies), 25 studies; AE-biomaGUNE-0619.",
     True),
    ("M03", "drive3_mri_M03_0619_2021", "protocol 0619, 2021, 60 studies (10 of them on the 11.7T, 2021-09-27/28: "
     "instrument_model is set per exam, never derived: _scanner_model turns BIOSPEC 500 into '50T'); "
     "AE-biomaGUNE-0619.", True),
    ("M04", "drive3_mri_M04_0619_2022", "protocol 0619, 2022-01-25, animals 191-200, 6 studies (STATUS 0.4 N6 / A1 R3: "
     "on this drive with the scanner's DICOM); AE-biomaGUNE-0619.", True),
    ("M05", "drive3_mri_M05_1019_2020", "protocol 1019, 2020, 61 studies; AE-biomaGUNE-1019 (Ryan, 2026-10-06, M2).",
     True),
    ("M06", "drive3_mri_M06_0320_2022", "protocol 0320, 2022-03-03/04 (Usp11 KO), 7 studies, all on the 11.7T; "
     "AE-biomaGUNE-0320.", True),
    ("M07", "drive3_mri_M07_1116_0522", "two single studies: JRC191107_1116_m179_flow (2019-11-07, 11.7T; sits in a 0619 "
     "folder, its name and the facility DB say 1116) -> AE-biomaGUNE-1116; jrc240702_m93_0522 (2024-07-02, nowhere else "
     "we know, A1 R3) -> AE-biomaGUNE-0522.", True),
    ("M08", "drive3_mri_M08_noproject", "jrc191015_m174_flow (2019-10-15): its folder claims 0619, but animal 174 of 0619 "
     "was born on 2021-07-29 (facility DB): the claim is contradicted, so NO project and NO subject id (A1 2.6, "
     "verdict C).", False),
    ("M09", "drive3_mri_M09_0619_m145b", "jrc210726_m145b_0619 (2021-07-26, 22 exams): the name claims animal 145b, which "
     "the facility DB does not hold (A1 read it as 145, but 145 has its own session that day). The DB logs MRI 7T that "
     "day for 145, 146, 152 and 153; the drive holds m145b, m145, m152, m153, so probably 146 -- unconfirmed, so project "
     "AE-biomaGUNE-0619 (folder claim) and NO subject id. A question for M. Jesus.", False),
]

HEAD = """{what}
# Gate: tasks/drive3_mri_gate.md. Plan: tasks/drive3_production_plan.md. Assessment: tasks/drive3_raw_coverage.md (A1).
#
# SOURCE: the staged drive copy J:\\_staging_drive3_MJ\\drive3_MJesus_WX22D623YP29\\files (read-only), staged by
# tools/drive_staging/drive3/mri_02_stage.py to a FLAT copy on D: (k-space excluded, every file checked against the
# drive manifest's SHA-256):
#     D:/projects/gjesus3/drive3_streams/mri/stage/{b}/<study>/<exam>/
# so original_name = "<study>/<exam>", the shape of every production MRI row: a later ingest of the same exam from the
# MRI platform's archive is skipped as already registered (the staging_dir trap). Convert-first (Ryan, 2026-10-04):
# every exam staged here holds DICOM (the scanner's own, or Dicomifier's made on this copy before ingest).
#
# PER-EXAM VALUES come from the case table (tools/drive_staging/drive3/mri_04_cases.py), on_missing: error:
#   drv_acq_datetime = exam visu_pars VisuCreationDate (production's rule), else acqp ACQ_time; never today
#   drv_model        = Bruker BioSpec 7T (Biospec 70/30) or 11.7T (BIOSPEC 500), set explicitly
#   drv_alias / drv_animal / drv_sample / drv_session / drv_project / drv_note
#
# Dry run (read-only):
#   python tools/ingest_raw.py --config tools/configs/drive3_mri/{name}.yaml --nas-root J:/gjesus3-data --dry-run
"""

BODY = """
ingest:
  delete_source_after_ingest: false
  auto_create_projects: false             # every target project exists and is active (checked in the gate)
  acquisition_layout: folder
  copy_strategy: mri_paravision_v2        # DICOMs only
  reconstructions: all

auto_discover:
  staging_dir: "D:/projects/gjesus3/drive3_streams/mri/stage/{b}"
  pattern: "*/[0-9]*"
  case_table:
    file:       cases_{b}.csv
    key:        original_name
    on_missing: error
{subject}
registry:
  instrument:           MRI
  data_ecosystem:       DICOM
  instrument_model:     "${{discovered.drv_model}}"
  modalities_in_study:  NA
  researcher:           "NA"
  data_source:          internal
  sample_id:            "${{discovered.drv_sample}}"
  sample_type:          organism
  session_id:           "${{discovered.drv_session}}"
  acquisition_datetime: discovered.drv_acq_datetime
  project_name:         "${{discovered.drv_project}}"
  notes:                "Internal MRI ${{discovered.mri_sequence_name}} exam ${{discovered.mri_exam_number}}; recons kept: ${{discovered.mri_recon_indices}}; ${{discovered.drv_note}}"

operator: "NA"

# Project link name: the production MRI template (mri_jrc_animalfirst.yaml). Without it the link falls back to
# original_name, "<study>/<exam>", whose slash would nest folders. Checked unique and free by mri_04_cases.py.
link_filename: "MRI_${{sample_id}}_${{acq_date}}_${{discovered.mri_exam_number}}_${{discovered.mri_recon_indices}}"
"""

SUBJ_DB = """  subject_from_db: true
  subject_lookup:
    project_alias: "${discovered.drv_alias}"
    animal_code:   "${discovered.drv_animal}"
"""
SUBJ_NONE = """  subject_from_db: false                  # the animal is not confirmed: no facility id is asserted
"""

DEDUP = """# The M. Jesus drive, stream M: DEDUP PROOF (DRY RUN ONLY -- never run for real; guarded below).
# Gate: tasks/drive3_mri_gate.md. Every exam of the drive that production ALREADY holds (A1 classes a and b: 3,965
# exams in 232 studies), staged the SAME way as the batches (flat <study>/<exam>, parameter files only:
# tools/drive_staging/drive3/mri_03_dedup_plan.py) and dated by the SAME rule (cases_DEDUP.csv, mri_04_cases.py).
# Expected dry run: Total 0; 3,958 exams "SKIP ... already in registry (idempotent re-run)" and 7 "has no row in
# auto_discover.case_table": the 7 have no date anywhere (never acquired) and production holds them as undated
# placeholders, so a date-keyed proof cannot include them (on_missing: skip, for them only).
# GUARD: copy_strategy below does not exist. A dry run never reaches the copy; a real run would fail every case at the
# copy step, before anything is registered.
#   python tools/ingest_raw.py --config tools/configs/drive3_mri/drive3_mri_dedup_proof.yaml --nas-root J:/gjesus3-data --dry-run

ingest:
  delete_source_after_ingest: false
  auto_create_projects: false
  acquisition_layout: folder
  copy_strategy: dedup_proof_never_run_for_real
  reconstructions: all

auto_discover:
  staging_dir: "D:/projects/gjesus3/drive3_streams/mri/stage/DEDUP"
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


def main():
    os.makedirs(C.CFG_DIR, exist_ok=True)
    for b, name, what, db in BATCHES:
        what = textwrap.fill(f"The M. Jesus drive (third historical drive), stream M, batch {b}: {what}", 116,
                             initial_indent="# ", subsequent_indent="# ")
        text = HEAD.format(b=b, what=what, name=name) + BODY.format(b=b, subject=SUBJ_DB if db else SUBJ_NONE)
        with open(os.path.join(C.CFG_DIR, name + ".yaml"), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print("wrote", name)
    with open(os.path.join(C.CFG_DIR, "drive3_mri_dedup_proof.yaml"), "w", encoding="utf-8", newline="\n") as f:
        f.write(DEDUP)
    print("wrote drive3_mri_dedup_proof")


if __name__ == "__main__":
    main()
