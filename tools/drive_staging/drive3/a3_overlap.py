"""A3 step 3 -- SHA-256 overlap of drive 3's segmentation-relevant files with what production already holds.

Compared, by SHA-256 only (never name + size):
  * the four promoted datasets DS-SEG-0001..0004 (provenance.csv `sha256`, and `source_sha256` where a
    label was gzipped on promotion, DS-SEG-0003);
  * the four SegBioMed harvest deposits in curated_datasets\\_incoming (every harvested file, including
    split volumes, excluded masks and scripts) -- so "harvested but not promoted" is visible too;
  * production /raw/ (the coordinator's prod_raw_sha256.csv, built from every checksums.json);
  * drives 1+2 non-raw placements (projects\\<p>\\working\\historical_drives\\_INDEX.csv) and their holding
    folder (staging\\historical_drives_unassigned\\manifest.csv).
Read-only. Output: a3_overlap.csv (one row per drive file with at least one match) and a printed summary.
"""
import glob
import os
import sys
from collections import Counter, defaultdict

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a3_common as C  # noqa: E402


def load_sets():
    hits = defaultdict(list)  # sha -> [(source, detail)]
    # promoted datasets
    for d in sorted(glob.glob(os.path.join(C.CDS, "segmentation", "*", "DS-SEG-*"))):
        ds = os.path.basename(d)
        for r in C.read_csv_dicts(os.path.join(d, "provenance.csv")):
            for col in ("sha256", "source_sha256"):
                s = (r.get(col) or "").strip().lower()
                if s:
                    hits[s].append((f"{ds}:{col}", f"{r.get('file_path','')}|acq={r.get('acq_id','')}|role={r.get('file_role','')}"))
    # harvest deposits
    for m in sorted(glob.glob(os.path.join(C.CDS, "_incoming", "*", "harvest_copy_manifest.csv")) +
                    glob.glob(os.path.join(C.CDS, "_incoming", "*", "*", "harvest_copy_manifest.csv"))):
        dep = os.path.relpath(os.path.dirname(m), os.path.join(C.CDS, "_incoming"))
        for r in C.read_csv_dicts(m):
            s = (r.get("sha256") or "").strip().lower()
            if s:
                hits[s].append((f"harvest:{dep}", f"{r.get('class','')}|{r.get('confidence','')}|acq={r.get('matched_acq_ids','')[:120]}|src={r.get('source_path','')}"))
    # production raw
    with open(C.PROD_SHA, encoding="utf-8") as f:
        next(f)
        for line in f:
            p = line.rstrip("\n").split(",", 4)
            hits[p[0].lower()].append(("prod_raw", f"{p[1]}|{p[2]}|{p[3]}|{p[4]}"))
    # drives 1+2 placements and holding folder
    for idx in sorted(glob.glob(os.path.join(C.GJ, "projects", "*", "working", "historical_drives", "_INDEX.csv"))):
        proj = idx.split(os.sep)[-4]
        for r in C.read_csv_dicts(idx):
            s = (r.get("sha256") or r.get("﻿sha256") or "").strip().lower()
            if s:
                hits[s].append(("drives12_placed", f"{proj}|{r.get('new_path', r.get(chr(0xfeff) + 'new_path', ''))}"))
    hold = os.path.join(C.GJ, "staging", "historical_drives_unassigned", "manifest.csv")
    for r in C.read_csv_dicts(hold):
        s = (r.get("sha256") or "").strip().lower()
        if s:
            hits[s].append(("drives12_held", r.get("new_path", r.get("﻿new_path", ""))))
    return hits


def main():
    inv = C.read_csv_dicts(os.path.join(C.OUT_DIR, "a3_inventory.csv"))
    hits = load_sets()
    out = []
    per_src = Counter()
    per_role_src = Counter()
    for r in inv:
        h = hits.get(r["sha256"].lower())
        if not h:
            continue
        srcs = sorted({s.split(":")[0] if s.startswith(("harvest", "DS-SEG")) else s for s, _ in h})
        full = sorted({s for s, _ in h})
        for s in full:
            per_src[s] += 1
            per_role_src[(r["role_guess"], s.split(":")[0])] += 1
        out.append({"relpath": r["relpath"], "sha256": r["sha256"], "size": r["size"], "role_guess": r["role_guess"],
                    "match_sources": ";".join(full), "n_matches": len(h),
                    "match_detail": " || ".join(f"{s}={d}" for s, d in h[:4])})
    C.write_csv(os.path.join(C.OUT_DIR, "a3_overlap.csv"), out)
    print(f"inventory rows {len(inv)}, rows with a SHA-256 match {len(out)}")
    for k, v in sorted(per_src.items()):
        print(f"  {k:60s} {v}")
    print("by role x source:")
    for (role, s), v in sorted(per_role_src.items()):
        print(f"  {role:28s} {s:20s} {v}")


if __name__ == "__main__":
    main()
