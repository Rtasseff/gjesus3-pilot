#!/usr/bin/env python3
"""a2_biomagune_mj.py -- HANDOFF §6 item 6: `biomaGUNE MJ` (the researcher's own folder), inventory only.

Per subfolder (two and three levels down): size by class, the codes its files claim (engine verdicts),
and how much of it already exists elsewhere, all by SHA-256:
  elsewhere_on_drive  the same bytes in another top-level folder of drive 3 (Pili y Mili, MRI, PET, ...)
  in_raw              an acquisition file in production /raw/
  placed12 / held12   placed in a project, or in the holding folder, by drives 1+2
  unique              in none of those: what only this folder holds
Read-only. Output: a2\\biomagune_mj_inventory.csv.
"""
import collections
import os

import a2_common as C

GROUPS = {
    "raw-microscopy": "raw microscopy (A1)", "dicom": "DICOM (A1)", "paravision": "ParaVision (A1)",
    "volume": "volumes/Splits/NIfTI", "voi": "volumes/Splits/NIfTI", "tif": "figures/exports",
    "figure": "figures/exports", "document": "documents", "analysis": "analysis", "physiology": "analysis",
    "video": "figures/exports", "junk": "junk",
}


def main():
    C.stdout_utf8()
    files = list(C.it(os.path.join(C.OUT, "files.csv")))
    outside = collections.defaultdict(set)
    for f in files:
        if f["top"] != "biomaGUNE MJ":
            outside[f["sha256"]].add(f["top"])
    rows = []
    for depth in (2, 3):
        agg = collections.defaultdict(lambda: collections.Counter())
        for f in files:
            if f["top"] != "biomaGUNE MJ":
                continue
            parts = f["relpath"].split("\\")
            key = "\\".join(parts[:depth]) if len(parts) > depth else "\\".join(parts[:-1]) + "\\(files here)"
            a = agg[key]
            b = int(f["size"])
            a["files"] += 1
            a["bytes"] += b
            g = "segmentations" if f["seg"] == "Y" else GROUPS.get(f["cls"], "other")
            a["g:" + g] += b
            if f["proposed_project"]:
                a["p:" + f["proposed_project"]] += 1
            else:
                a["p:<" + f["verdict"] + ">"] += 1
            el = f["sha256"] in outside
            raw = bool(f["in_raw"])
            pl = bool(f["placed12"])
            hd = bool(f["holding12"])
            a["elsewhere"] += b if el else 0
            a["in_raw"] += b if raw else 0
            a["placed12"] += b if pl else 0
            a["held12"] += b if hd else 0
            a["unique"] += b if not (el or raw or pl or hd) else 0
            if f["owner"] == "A2":
                a["nonraw"] += b
                a["unique_nonraw"] += b if not (el or raw or pl or hd) else 0
            for t in outside.get(f["sha256"], ()):
                a["t:" + t] += b
        for key, a in sorted(agg.items(), key=lambda kv: (-kv[1]["bytes"])):
            if depth == 3 and a["bytes"] < 50e6:
                continue
            rows.append({
                "level": depth, "folder": key, "files": a["files"], "gb": C.gb(a["bytes"]),
                "by_class_gb": "; ".join(f"{k[2:]} {C.gb(v)}" for k, v in sorted(a.items(), key=lambda kv: -kv[1])
                                          if k.startswith("g:") and v >= 1e7),
                "codes_claimed": "; ".join(f"{k[2:]} {v}" for k, v in sorted(a.items(), key=lambda kv: -kv[1])
                                           if k.startswith("p:"))[:300],
                "gb_elsewhere_on_drive": C.gb(a["elsewhere"]),
                "where_else": "; ".join(f"{k[2:]} {C.gb(v)}" for k, v in sorted(a.items(), key=lambda kv: -kv[1])
                                        if k.startswith("t:")),
                "gb_in_raw": C.gb(a["in_raw"]), "gb_placed_by_drives12": C.gb(a["placed12"]),
                "gb_in_drives12_holding": C.gb(a["held12"]), "gb_unique": C.gb(a["unique"]),
                "pct_unique": f"{100 * a['unique'] / a['bytes']:.1f}" if a["bytes"] else "0",
                "gb_nonraw": C.gb(a["nonraw"]), "gb_unique_nonraw": C.gb(a["unique_nonraw"]),
            })
    C.wcsv(C.out_path("biomagune_mj_inventory.csv"), list(rows[0].keys()), rows, bom=True)
    mj = [f for f in files if f["top"] == "biomaGUNE MJ"]
    tot = sum(int(f["size"]) for f in mj)
    C.say(f"biomaGUNE MJ: {len(mj):,} files, {C.gb(tot)} GB; unique (level-2 sum) "
          f"{sum(float(r['gb_unique']) for r in rows if r['level'] == 2):.2f} GB, of which non-raw "
          f"{sum(float(r['gb_unique_nonraw']) for r in rows if r['level'] == 2):.2f} GB")
    for r in rows:
        if r["level"] == 2:
            C.say(f"  {r['folder']:62s} {r['files']:7,d} {r['gb']:>8s} GB  elsewhere {r['gb_elsewhere_on_drive']:>7s}  "
                  f"in_raw {r['gb_in_raw']:>7s}  placed12 {r['gb_placed_by_drives12']:>6s}  unique {r['gb_unique']:>7s} "
                  f"({r['pct_unique']}%), non-raw {r['gb_nonraw']} of which unique {r['gb_unique_nonraw']}")
            C.say(f"      classes: {r['by_class_gb']}")
            C.say(f"      codes: {r['codes_claimed'][:200]}")


if __name__ == "__main__":
    main()
