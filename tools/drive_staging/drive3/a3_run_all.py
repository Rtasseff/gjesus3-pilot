"""A3 -- re-derive every number in tasks/drive3_segmentations_cds.md, in order (read-only on J:\\ and K:\\).

    python tools/drive_staging/drive3/a3_run_all.py            # resume: keeps a3_headers.csv / a3_ncc_stacks.csv rows
    python tools/drive_staging/drive3/a3_run_all.py --fresh    # recompute the two slow steps from nothing (~25 min)

Inputs (coordinator, 2026-10-06): D:\\projects\\gjesus3\\drive3_analysis\\drive3_manifest.csv,
prod_raw_sha256.csv, prod_raw_acqs.csv; live registries and curated_datasets\\ on J:\\ (read only); the
staged files under J:\\_staging_drive3_MJ\\ (headers and voxels read; nothing written).
Outputs: D:\\projects\\gjesus3\\drive3_analysis\\a3\\ only. Bytecode is disabled so no __pycache__ appears.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STEPS = [
    "a3_inventory.py",          # 1  every segmentation-relevant file (manifest only)
    "a3_headers.py",            # 2  header + voxel census per distinct SHA-256 (slow; resumable)
    "a3_overlap.py",            # 3  SHA-256 overlap: DS-SEG, harvest deposits, /raw/, drives 1+2
    "a3_trace.py",              # 4  sets + first-pass trace; writes the NCC / image work lists
    "a3_ncc.py",                # 5  cine stacks resolved by pixels vs production DICOM (resumable)
    "a3_imgmatch.py",           # 5b beside-label NIfTI images matched by pixels
    "a3_geostack.py",           # 5c stacks without split volumes: membership by sidecar geometry
    "a3_label_topology.py",     # 6  what the label values mean (measured topology + shape)
    "a3_topology_summary.py",   # 6b
    "a3_sets.py",               # 7  final trace per label, per set / cohort, DS-SEG session overlap
    "a3_schema_by_cohort.py",   # 6c schema per file by cohort (needs a3_labels_distinct.csv)
    "a3_unlock.py",             # 8  untraced labels whose raw is on this drive
    "a3_versions.py",           # 10 several masks for one stack + phase: re-save, edit or reader?
    "a3_slicemap_check.py",     # 9  promoted DS-SEG slice maps vs this drive's split volumes
    "a3_inventory_summary.py",  # 11 roll-ups for the report
    "a3_pig_check.py",          # 13 the pig set's source series
    "a3_drafts.py",             # 12 draft _dataset.yaml + provenance.csv per candidate (a3\\drafts only)
]


def main():
    out = r"D:\projects\gjesus3\drive3_analysis\a3"
    if "--fresh" in sys.argv:
        for f in ("a3_headers.csv", "a3_ncc_stacks.csv", "a3_ncc_slices.csv"):
            p = os.path.join(out, f)
            if os.path.exists(p):
                os.remove(p)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    for s in STEPS:
        print(f"=== {s}", flush=True)
        r = subprocess.run([sys.executable, os.path.join(HERE, s)], env=env)
        if r.returncode:
            sys.exit(f"{s} failed ({r.returncode})")


if __name__ == "__main__":
    main()
