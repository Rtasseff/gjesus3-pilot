#!/usr/bin/env python3
"""One-off (historical drives, DICOM stream): run the stock tools/relink_mri_regen.py, but
scoped to the drives' MRI configs instead of its hard-coded 2026-06 regen configs.

Why a wrapper: relink_mri_regen.REGEN_CONFIG_MARKERS is a module constant naming the two
2026-06 regen configs. The drives' no-DICOM exams (first: B04b ACQ-20200304-MRI-001, -055)
are regenerated from WSL by tools/backfill_dicom_regen.py, which cannot hard-link over CIFS,
so their project link shells stay empty; the stock tool fills such shells by DICOM count.
This wrapper only swaps the marker tuple, so the shared tool is unchanged. Rows whose link
is already complete are skipped by the tool itself (idempotent).

Usage (from Windows, after the WSL regen):
    python tools/drive_staging/relink_dicom_regen_drives.py --nas-root J:/gjesus3-data --dry-run
    python tools/drive_staging/relink_dicom_regen_drives.py --nas-root J:/gjesus3-data --marker dicom_B04b_0619_bret_7T
"""
import os
import sys

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
import relink_mri_regen  # noqa: E402

if __name__ == "__main__":
    argv = sys.argv[1:]
    markers = []
    while "--marker" in argv:
        i = argv.index("--marker")
        markers.append(argv[i + 1])
        del argv[i:i + 2]
    if not markers:
        sys.exit("give at least one --marker <ingest_config substring>, e.g. dicom_B04b_0619_bret_7T")
    relink_mri_regen.REGEN_CONFIG_MARKERS = tuple(markers)
    print(f"[relink_dicom_regen_drives] scope = {relink_mri_regen.REGEN_CONFIG_MARKERS}")
    relink_mri_regen.main(argv)
