"""A3 step 6c -- which label SCHEMA does each cine mask use, by cohort (read-only, local CSVs only).

The same value set can mean different things: {0,1,2} is LV/RV blood pools in most cohorts but LV cavity /
LV myocardium ring in the 1519 (post-surgery) masks; {0,1,2,3,4} is either the ITK-SNAP endo/epi palette or
the Massventricles order. Classified per file from its measured topology (a3_label_topology.csv):
  LVRV-pools   {1,2}: both regions solid, separate, touching the outside; 1 round, 2 crescent
  LV-endo-epi  {1,2}: 1 enclosed (exterior contact < 0.1) and inside 2's outline
  4C-endo-epi  {1..4}: 1 inside 2  (ITK-SNAP: LV Endo, LV Epi, RV Endo, RV Epi)
  4C-mass      {1..4}: 1 inside 3  (Massventricles: LV cav, RV cav, LV myo, RV wall)
Output: a3_schema_by_cohort.csv
"""
import os
import sys
from collections import Counter, defaultdict

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a3_common as C  # noqa: E402
import a3_sets as S  # noqa: E402


def classify(v):
    f = lambda val, col: float(v[val][col]) if val in v and v[val].get(col, "") != "" else None  # noqa: E731
    keys = sorted(v)
    if keys == [1, 2]:
        e1, e2 = f(1, "exterior_contact"), f(2, "exterior_contact")
        if e1 is not None and e1 < 0.1 and (f(1, "enclosed_by_2") or 0) >= 0.5:
            return "LV-endo-epi"
        if e1 is not None and e2 is not None and e1 >= 0.9 and e2 >= 0.9 and (f(1, "solidity_median") or 0) > (f(2, "solidity_median") or 0):
            return "LVRV-pools"
        return "{1,2}-unclear"
    if keys == [1, 2, 3, 4]:
        if (f(1, "enclosed_by_2") or 0) >= 0.5:
            return "4C-endo-epi"
        if (f(1, "enclosed_by_3") or 0) >= 0.5:
            return "4C-mass"
        return "{1..4}-unclear"
    return "{" + ",".join(map(str, keys)) + "}"


def main():
    topo = defaultdict(dict)
    for r in C.read_csv_dicts(os.path.join(C.OUT_DIR, "a3_label_topology.csv")):
        if r.get("value"):
            topo[r["sha256"]][int(r["value"])] = r
    D = C.read_csv_dicts(os.path.join(C.OUT_DIR, "a3_labels_distinct.csv"))
    agg = defaultdict(Counter)
    traced = defaultdict(Counter)
    for d in D:
        if d["sha256"] not in topo:
            continue
        cl = classify(topo[d["sha256"]])
        key = (d["set_id"], S.protocol_of(d), S.year_of(d))
        agg[key][cl] += 1
        if d["final_level"] in ("acquisition", "acquisition-stack", "acquisition-stack-geometry", "acquisition-group"):
            traced[key][cl] += 1
    rows = []
    for k in sorted(agg):
        for cl, n in agg[k].most_common():
            rows.append({"set_id": k[0], "protocol": k[1], "year": k[2], "schema": cl, "distinct_files": n, "traced": traced[k][cl]})
    C.write_csv(os.path.join(C.OUT_DIR, "a3_schema_by_cohort.csv"), rows)
    tot = Counter()
    for k, c in agg.items():
        tot.update(c)
    print(tot.most_common())
    for r in rows:
        if r["schema"] in ("LV-endo-epi", "{1,2}-unclear", "{1..4}-unclear"):
            print(r)


if __name__ == "__main__":
    main()
