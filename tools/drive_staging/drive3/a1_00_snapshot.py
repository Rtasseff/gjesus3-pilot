"""A1 step 0: take dated, hashed copies of the live inputs that A1 reads, so every number re-derives.

Reads (read-only, 'rb'): J:\\gjesus3-data\\registries\\*.csv, the drives 1+2 holding manifest and the
18 per-project _INDEX.csv of the drives 1+2 placements, the hub's drive3_duplicates_of_12.csv.
Writes: D:\\projects\\gjesus3\\drive3_analysis\\a1\\_inputs\\ (+ _inputs\\SNAPSHOT.txt).

    python a1_00_snapshot.py
"""
import datetime as dt
import glob
import os
import shutil

from a1_common import (D12_HOLDING_MANIFEST, HUB, NAS, REGISTRIES, lp, out_path, sha256_file)

REG_FILES = ["registry_raw.csv", "registry_projects.csv", "registry_subjects.csv",
             "retired_acquisitions.csv", "pending_dicom_regen.csv", "registry_datasets.csv"]


def copy(src, *dst_parts):
    dst = out_path("_inputs", *dst_parts)
    with open(lp(src), "rb") as fi, open(dst, "wb") as fo:
        shutil.copyfileobj(fi, fo, 8 * 1024 * 1024)
    return dst


def main():
    lines = [f"A1 input snapshot taken {dt.datetime.now().isoformat(timespec='seconds')}", ""]
    for name in REG_FILES:
        src = os.path.join(REGISTRIES, name)
        dst = copy(src, name)
        lines.append(f"{name:32s} {os.path.getsize(dst):>12,d}  {sha256_file(dst)}  <- {src}")
    dst = copy(D12_HOLDING_MANIFEST, "d12", "holding_manifest.csv")
    lines.append(f"{'d12/holding_manifest.csv':32s} {os.path.getsize(dst):>12,d}  {sha256_file(dst)}  <- {D12_HOLDING_MANIFEST}")
    idx = sorted(glob.glob(os.path.join(NAS, "projects", "*", "working", "historical_drives", "_INDEX.csv")))
    for src in idx:
        proj = src.split(os.sep)[-4]
        dst = copy(src, "d12", f"{proj}__INDEX.csv")
        lines.append(f"{'d12/' + proj + '__INDEX.csv':32s} {os.path.getsize(dst):>12,d}  {sha256_file(dst)}  <- {src}")
    src = os.path.join(HUB, "drive3_duplicates_of_12.csv")
    dst = copy(src, "hub_drive3_duplicates_of_12.csv")
    lines.append(f"{'hub_drive3_duplicates_of_12.csv':32s} {os.path.getsize(dst):>12,d}  {sha256_file(dst)}  <- {src}")
    lines.append(f"\n{len(idx)} drives-1+2 placement indexes")
    with open(out_path("_inputs", "SNAPSHOT.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
