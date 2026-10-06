"""A3 step 6b -- summarise a3_label_topology.csv by value scheme (read-only, local CSVs only).

For each scheme (the set of foreground values a file carries, e.g. {1,2} or {1,2,3,4}) and set:
median / quartiles of exterior_contact per value, and of enclosed_by_<w> for the pairs that decide the
meaning question (is 1 inside 2? is 3 inside 4?). Also reports the same numbers for the drive files that are
byte-identical to DS-SEG-0004 masks, so the evidence can be read against that dataset's open question.
Output: a3_topology_summary.csv and a printed table.
"""
import os
import sys
from collections import defaultdict

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a3_common as C  # noqa: E402

import numpy as np  # noqa: E402


def q(v):
    v = [x for x in v if x == x]
    if not v:
        return ""
    a = np.array(v, dtype=float)
    return f"{np.median(a):.3f} [{np.percentile(a, 25):.3f}-{np.percentile(a, 75):.3f}] n={len(a)}"


def main():
    rows = C.read_csv_dicts(os.path.join(C.OUT_DIR, "a3_label_topology.csv"))
    labels = C.read_csv_dicts(os.path.join(C.OUT_DIR, "a3_labels.csv"))
    twin = {r["sha256"] for r in labels if r["trace_route"] == "dsseg-twin"}
    by_file = defaultdict(dict)
    setof = {}
    for r in rows:
        if r.get("error") or not r.get("value"):
            continue
        by_file[r["sha256"]][int(r["value"])] = r
        setof[r["sha256"]] = r["set_id"]
    out = []
    groups = defaultdict(list)
    for sha, vals in by_file.items():
        scheme = "{" + ",".join(str(v) for v in sorted(vals)) + "}"
        groups[(setof[sha], scheme)].append(sha)
        groups[("ALL", scheme)].append(sha)
        if sha in twin:
            groups[("DS-SEG-0004-twins", scheme)].append(sha)
    for (set_id, scheme), shas in sorted(groups.items(), key=lambda kv: (kv[0][0], -len(kv[1]))):
        if len(shas) < 3 and set_id != "DS-SEG-0004-twins":
            continue
        rec = {"set_id": set_id, "scheme": scheme, "files": len(shas)}
        vals = sorted({v for s in shas for v in by_file[s]})
        for v in vals:
            rec[f"ext_contact_{v}"] = q([float(by_file[s][v]["exterior_contact"]) for s in shas
                                         if v in by_file[s] and by_file[s][v]["exterior_contact"] != ""])
            rec[f"solidity_{v}"] = q([float(by_file[s][v]["solidity_median"]) for s in shas
                                      if v in by_file[s] and by_file[s][v].get("solidity_median", "") != ""])
            rec[f"voxels_{v}"] = q([float(by_file[s][v]["voxels"]) for s in shas if v in by_file[s]])
        for a_, b_ in ((1, 2), (2, 1), (3, 4), (4, 3), (1, 3), (3, 1)):
            col = f"enclosed_by_{b_}"
            xs = [float(by_file[s][a_][col]) for s in shas if a_ in by_file[s] and by_file[s][a_].get(col, "") != ""]
            if xs:
                rec[f"{a_}_inside_{b_}"] = q(xs)
        out.append(rec)
    C.write_csv(os.path.join(C.OUT_DIR, "a3_topology_summary.csv"), out)
    for r in out:
        print(r)


if __name__ == "__main__":
    main()
