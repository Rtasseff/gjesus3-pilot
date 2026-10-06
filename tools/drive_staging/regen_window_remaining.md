# Stream B: remaining write window (X1 → B07 → B08 → B06)

**Order:** `X1` (3) → `B07` (123) → `B08` (363) → `B06` (37). Expected **+526 rows**.

**For each batch:**
1. A fresh dated backup: `C:\Users\rtasseff\temp\gjesus3_registry_backup_<YYYYMMDD>_dicom_<batch>\`, compared with `cmp`.
2. A collision pre-check (only X1 creates project links; B07/B08/B06 have a blank project, so no links).
3. A re-dry-run, checked equal to the line below.
4. The real run.
5. Verification: `verify_batch.py <cfg> <n> <rows before>`, then the strict link check (X1: `verify_x1_links.py`).
6. Then the next batch.

| Batch | Config | Expected dry run | Links |
|---|---|---|---|
| X1 | `dicom_X1_oneoff_acqpless.yaml` | 3 / 3 / 0; `series/` shape; `0619` ×2, `1519` ×1 | `MRI_m27_0619_20200304_4_dicom`, `MRI_m31_0619_20200304_4_dicom`, `MRI_m14_1519_20200923_8_dicom`: all free (checked 2026-10-04) |
| B07 | `dicom_B07_phantoms_collab_2022_23.yaml` | 125 cases → 123 listed / 2 skipped (no-recon), every listed exam with files > 0 | none (blank project) |
| B08 | `dicom_B08_icon_madrid_2024.yaml` | 363 / 363 / 0, XMRI, files > 0 | none (blank project) |
| B06 | `dicom_B06_1019_mrs_2021.yaml` | 37 listed (29 skipped: 8 never-acquired + 21 spectroscopy), files > 0 | none (blank project) |

**After each:** DICOMs that I produced before ingest are in the staging; the sidecar `notes` say so (`drv_dicom_origin`). After all four are verified, these can be deleted: `stage_oneoff2`, `stage_sib_cardiac`, `stage_sib_ni`, `stage_B06`, `stage_B07`, `stage_B08`.
