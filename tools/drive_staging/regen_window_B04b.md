# Write window: DICOM regen + relink for B04b's 2 no-DICOM exams (stream B)

**Scope:** `ACQ-20200304-MRI-001` (m27/1 localizer) and `ACQ-20200304-MRI-055` (m32/12 cine), `PROJ-0004` (`AE-biomaGUNE-0619`). This is the documented deferred-backfill path (11_OPERATIONS §5.5). Nothing else is touched.

**Source:** `D:\projects\gjesus3\scratch_drives-dicom\stage_B04\` (fid + 2dseq present), symlinked into the tool's `PV<ver>/<study>/<exam>` layout at `~/regen_stage_b04/PV6.0.1/` in WSL (0 bytes).

**Dry runs done 2026-10-02 (registry unchanged):**
- `backfill_dicom_regen.py`: `WOULD-REGENERATE 2`, "source ready" for both.
- `relink_dicom_regen_drives.py --marker dicom_B04b_0619_bret_7T --dry-run`: matched 165, skipped_complete 163, skipped_empty 2 (these two, expected before regen), errors 0.

## Steps (only inside the window)

0. Back up the registries to a fresh dated folder, then compare each copy with `cmp`:
   ```bash
   D=/c/Users/rtasseff/temp/gjesus3_registry_backup_<YYYYMMDD>_dicom_B04b_regen; [ -e "$D" ] && echo STOP || { mkdir -p "$D"; cp -p J:/gjesus3-data/registries/*.csv "$D/"; }
   ```
1. Regenerate (WSL; `source` conda first, or Dicomifier is silently absent):
   ```bash
   source ~/miniforge3/etc/profile.d/conda.sh && conda activate dicomifier-pilot
   cd "/mnt/c/Users/rtasseff/OneDrive - CIC biomaGUNE/projects/DataInfra/gjesus3-archive/gjesus3-dev/drives-dicom"
   PYTHONPATH=tools python tools/backfill_dicom_regen.py --apply --nas-root /mnt/gjesus3/gjesus3-data \
     --staging ~/regen_stage_b04 --acq-id ACQ-20200304-MRI-001 --acq-id ACQ-20200304-MRI-055
   ```
2. Relink from Windows (`os.link` is refused over CIFS from WSL):
   ```bash
   python tools/drive_staging/relink_dicom_regen_drives.py --nas-root J:/gjesus3-data --marker dicom_B04b_0619_bret_7T --dry-run   # expect created 2
   python tools/drive_staging/relink_dicom_regen_drives.py --nas-root J:/gjesus3-data --marker dicom_B04b_0619_bret_7T
   ```
3. Verify:
   - `python tools/verify_checksums.py --nas-root J:/gjesus3-data --acq ACQ-20200304-MRI-001` (and `-055`): PASS, with n_files > 0.
   - `pending_dicom_regen.csv`: both rows `regenerated`.
   - Each link `raw_linked/MRI_m27_0619_20200304_1_1` and `MRI_m32_0619_20200304_12_1` holds as many `.dcm` as the `.data/`, each `os.path.samefile`.
   - `validate_registries`: 10,314 errors, 1 class; registry row count unchanged.
4. Only after step 3 passes: `stage_B04\` may be deleted (Ryan's approval).
