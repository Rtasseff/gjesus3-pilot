#!/usr/bin/env python3
"""a2_numbers.py -- the figures quoted in tasks/drive3_projects_and_placement.md, re-derived from the a2
CSVs (run after a2_files, a2_project_map, a2_placement). Read-only. Output: a2\\report_numbers.txt.

    order of the whole part:  a2_dicom_magic -> a2_claims -> a2_files -> a2_project_map -> a2_reopen_1121
                              -> a2_placement -> a2_verify_placed -> a2_nocode -> a2_db_evidence
                              -> a2_db_0118 -> a2_biomagune_mj -> a2_numbers
    (run each with PYTHONDONTWRITEBYTECODE=1; all are read-only on J:\\ and the DB)
"""
import collections
import os

import a2_common as C


def main():
    C.stdout_utf8()
    lines = []

    def say(m=""):
        lines.append(m)
        print(m)

    files = list(C.it(os.path.join(C.OUT, "files.csv")))
    say(f"drive 3: {len(files):,} files, {C.gb(sum(int(f['size']) for f in files))} GB")
    own = collections.defaultdict(lambda: [0, 0])
    for f in files:
        own[f["owner"]][0] += 1
        own[f["owner"]][1] += int(f["size"])
    for k, (n, b) in sorted(own.items()):
        say(f"  owner {k:5s} {n:9,d} files {C.gb(b):>9s} GB")
    say("\nA2 by class (non-raw)")
    cls = collections.defaultdict(lambda: [0, 0])
    for f in files:
        if f["owner"] == "A2":
            k = "segmentation" if f["seg"] == "Y" else f["cls"]
            cls[k][0] += 1
            cls[k][1] += int(f["size"])
    for k, (n, b) in sorted(cls.items(), key=lambda kv: -kv[1][1]):
        say(f"  {k:16s} {n:8,d} {C.gb(b):>8s} GB")
    say("\nA2 by top folder")
    top = collections.defaultdict(lambda: [0, 0])
    for f in files:
        if f["owner"] == "A2":
            top[f["top"]][0] += 1
            top[f["top"]][1] += int(f["size"])
    for k, (n, b) in sorted(top.items(), key=lambda kv: -kv[1][1]):
        say(f"  {k:16s} {n:8,d} {C.gb(b):>8s} GB")
    mhd = [f for f in files if f["owner"] == "A2" and f["relpath"].lower().endswith((".mhd", ".raw")) and f["cls"] == "volume"]
    say(f"\nMetaImage .mhd/.raw volumes (Splits etc.), counted as raw Bruker by the hub: {len(mhd):,} files, "
        f"{C.gb(sum(int(f['size']) for f in mhd))} GB")
    say("\njunk (excluded)")
    junk = collections.defaultdict(lambda: [0, 0])
    for f in files:
        if f["owner"] == "junk":
            junk[f["detail"]][0] += 1
            junk[f["detail"]][1] += int(f["size"])
    for k, (n, b) in sorted(junk.items(), key=lambda kv: -kv[1][0]):
        say(f"  {n:6,d} {b / 1e6:9.1f} MB  {k}")
    a2_in_pv = [f for f in files if f["owner"] == "A2" and f["detail"] == "inside a ParaVision study folder"]
    say(f"\nA2 files that sit inside a ParaVision study folder (A1's study, A2's file): {len(a2_in_pv):,}, "
        f"{C.gb(sum(int(f['size']) for f in a2_in_pv))} GB")
    plan = list(C.it(os.path.join(C.OUT, "placement", "placement_plan.csv")))
    tgt = collections.defaultdict(lambda: [0, 0])
    for f in plan:
        if f["dec_rec"] in ("place", "place-after-reopen", "closed-project"):
            tgt[f["rec_project"]][0] += 1
            tgt[f["rec_project"]][1] += int(f["size"])
    say(f"\nprojects receiving files (recommended scenario): {len(tgt)}")
    for k, (n, b) in sorted(tgt.items(), key=lambda kv: -kv[1][1]):
        say(f"  {k:28s} {n:7,d} {C.gb(b):>7s} GB")
    seg = [f for f in plan if f["seg"] == "Y"]
    sd = collections.defaultdict(lambda: [0, 0])
    for f in seg:
        sd[f["dec_rec"]][0] += 1
        sd[f["dec_rec"]][1] += int(f["size"])
    say("\nsegmentation-class files (A3's subject) by placement decision")
    for k, (n, b) in sorted(sd.items(), key=lambda kv: -kv[1][1]):
        say(f"  {k:24s} {n:7,d} {C.gb(b):>7s} GB")
    with open(C.out_path("report_numbers.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
