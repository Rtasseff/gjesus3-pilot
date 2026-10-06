#!/usr/bin/env python3
"""a2_files.py -- one row per drive-3 file: who owns it (A1 raw imaging / A2 non-raw / junk), its
class, its project claim, and whether its exact bytes are already in production.

Inputs (all read-only): the drive-3 manifest, a2\\dicom_magic.csv (a2_dicom_magic.py),
a2\\claims\\file_claims.csv (a2_claims.py), prod_raw_sha256.csv (the coordinator's /raw/ index), every
project's working\\historical_drives\\_INDEX.csv on the NAS (drives 1+2 placements) and the drives-1+2
holding folder's manifest.csv.

Output: a2\\files.csv (621,969 rows) and a2\\files_summary.txt.

"Already in production" follows HANDOFF.md §1: in /raw/, OR placed in a project folder by the drives
1+2 work, OR in its holding folder. Every comparison is by SHA-256 only.
"""
import collections
import os

import a2_common as C

FIELDS = ["relpath", "top", "size", "sha256", "mtime", "owner", "cls", "detail", "seg", "pv_study",
          "claim_id", "verdict", "proposed_project", "conflict", "in_raw", "placed12", "holding12",
          "dup_n", "dup_tops"]


def main():
    C.stdout_utf8()
    rows = C.load_manifest()
    C.say(f"manifest rows: {len(rows):,}")
    facts = C.DirFacts(rows)
    magic = C.load_dicom_magic()
    claims = {}
    for r in C.it(os.path.join(C.OUT, "claims", "file_claims.csv")):
        claims[r["relpath"]] = r
    C.say(f"file claims: {len(claims):,}")
    raw, placed, holding = C.load_dedup_sources()
    by_sha = collections.defaultdict(list)
    for r in rows:
        by_sha[r["sha256"]].append(r)
    out = []
    tot = collections.Counter()
    totb = collections.Counter()
    for r in rows:
        owner, cls, detail = C.classify(r, facts, magic)
        c = claims.get(r["relpath"], {})
        sha = r["sha256"]
        twins = by_sha[sha]
        rec = {
            "relpath": r["relpath"], "top": C.top_of(r["relpath"]), "size": r["size"], "sha256": sha,
            "mtime": r["mtime"], "owner": owner, "cls": cls, "detail": detail,
            "seg": "Y" if owner == "A2" and C.is_segmentation(r["relpath"], cls) else "",
            "pv_study": facts.study_folder(r["relpath"]),
            "claim_id": c.get("claim_id", ""), "verdict": c.get("verdict", "") or "NO-CLAIM",
            "proposed_project": c.get("proposed_project", ""), "conflict": c.get("conflict", ""),
            "in_raw": ";".join(sorted(set(raw.get(sha, [])))[:5]),
            "placed12": ";".join(sorted(placed.get(sha, {}))),
            "holding12": str(len(holding.get(sha, []))) if sha in holding else "",
            "dup_n": len(twins),
            "dup_tops": ";".join(sorted({C.top_of(t["relpath"]) for t in twins})) if len(twins) > 1 else "",
        }
        out.append(rec)
        tot[(owner, cls)] += 1
        totb[(owner, cls)] += r["size"]
    C.wcsv(C.out_path("files.csv"), FIELDS, out)
    lines = [f"files.csv: {len(out):,} rows", "", "owner  class                      files        GB"]
    for k in sorted(tot):
        lines.append(f"{k[0]:6s} {k[1]:24s} {tot[k]:9,d} {totb[k] / 1e9:9.2f}")
    for o in ("A1", "A2", "junk"):
        n = sum(v for k, v in tot.items() if k[0] == o)
        b = sum(v for k, v in totb.items() if k[0] == o)
        lines.append(f"TOTAL {o:5s} {n:9,d} files {b / 1e9:9.2f} GB")
    with open(C.out_path("files_summary.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
