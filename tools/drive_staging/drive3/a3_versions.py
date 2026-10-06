"""A3 step 10 -- more than one mask for the same stack and phase: re-saves, edits or independent readers? (read-only)

SHA-256 settles byte duplicates (a3_labels_distinct.csv already folds them). This step looks at DIFFERENT
files that label the SAME thing: traced cine masks grouped by (production study, label dims, phase, value
scheme). Within a group, every pair is compared voxel by voxel:
  voxel-identical  same label array, different bytes (a re-save: other compression, header or name);
  near-identical   mean Dice over the foreground labels >= 0.98 (a small edit of the same tracing);
  different        Dice < 0.98 (an independent reading, or a substantial correction).
This is what a curator needs to pick ONE version per (session, phase) or to keep several as readers.
Output: a3_versions_pairs.csv, a3_versions_groups.csv.
"""
import itertools
import os
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a3_common as C  # noqa: E402

import numpy as np  # noqa: E402

TRACED = ("acquisition", "acquisition-stack", "acquisition-stack-geometry", "acquisition-group")
SETS = ("S-CINE-LVRV", "S-CINE-MASS", "S-FLOW-ROI")


def load(rel):
    p = C.staged_path(rel)
    if rel.lower().endswith((".nii", ".nii.gz")):
        return np.asanyarray(C.load_nifti(p).dataobj)
    return C.read_metaimage(p)[1]


def dice(a, b, vals):
    ds = []
    for v in vals:
        x, y = a == v, b == v
        s = x.sum() + y.sum()
        if s:
            ds.append(2.0 * (x & y).sum() / s)
    return float(np.mean(ds)) if ds else 1.0


def main():
    D = C.read_csv_dicts(os.path.join(C.OUT_DIR, "a3_labels_distinct.csv"))
    groups = defaultdict(list)
    for d in D:
        if d["set_id"] in SETS and d["final_level"] in TRACED and d["kind"] == "label":
            key = (d["prod_study"] or d["final_acq_ids"].split(";")[0], "x".join(d["dims"].split("x")[:3]),
                   d["phase"], d["values"])
            groups[key].append(d)
    multi = {k: v for k, v in groups.items() if len(v) > 1}
    print(f"groups {len(groups)}, with >1 distinct file {len(multi)}", flush=True)

    def one(item):
        key, ds = item
        arrs = {}
        for d in ds:
            try:
                arrs[d["sha256"]] = np.asarray(load(d["example_relpath"])).squeeze()
            except Exception as e:  # noqa: BLE001
                arrs[d["sha256"]] = e
        vals = [int(v) for v in key[3].split(";") if v and v != "0"]
        rows = []
        for d1, d2 in itertools.combinations(ds, 2):
            a, b = arrs[d1["sha256"]], arrs[d2["sha256"]]
            if isinstance(a, Exception) or isinstance(b, Exception) or a.shape != b.shape:
                rel = "unreadable-or-shape-differs"
                dsc = ""
            elif np.array_equal(a, b):
                rel, dsc = "voxel-identical", 1.0
            else:
                dsc = dice(a, b, vals)
                rel = "near-identical" if dsc >= 0.98 else "different"
            rows.append({"study": key[0], "dims": key[1], "phase": key[2], "scheme": key[3], "relation": rel,
                         "dice_mean": round(dsc, 4) if dsc != "" else "",
                         "sha_a": d1["sha256"], "sha_b": d2["sha256"],
                         "readers_a": d1["reader_hints"], "readers_b": d2["reader_hints"],
                         "mtime_a": d1["earliest_mtime"], "mtime_b": d2["earliest_mtime"],
                         "path_a": d1["example_relpath"], "path_b": d2["example_relpath"]})
        return rows

    pairs = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        for rows in ex.map(one, multi.items()):
            pairs += rows
    C.write_csv(os.path.join(C.OUT_DIR, "a3_versions_pairs.csv"), pairs)
    g = defaultdict(Counter)
    for p in pairs:
        g[(p["study"], p["dims"], p["phase"], p["scheme"])][p["relation"]] += 1
    grows = [{"study": k[0], "dims": k[1], "phase": k[2], "scheme": k[3], "versions": len(groups[k]),
              **{rel: c[rel] for rel in ("voxel-identical", "near-identical", "different", "unreadable-or-shape-differs")}}
             for k, c in g.items()]
    C.write_csv(os.path.join(C.OUT_DIR, "a3_versions_groups.csv"), grows)
    print("pairs:", Counter(p["relation"] for p in pairs))
    print("groups by versions:", Counter(r["versions"] for r in grows))


if __name__ == "__main__":
    main()
