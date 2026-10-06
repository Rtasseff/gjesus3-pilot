"""A3 step 8 -- which untraced labels could become traceable by ingesting raw that is on THIS drive (read-only).

For every distinct label that traces to no production acquisition, take the ParaVision studies its folders
name and check, in the drive manifest, whether the raw Bruker study is on the drive: native DICOM under
pdata\\<n>\\dicom (ingestible as is under the 2026-10-04 MRI rule) or only 2dseq (needs DICOM generated before
ingest). A study counts once whatever the number of copies. Nothing here proposes an ingest; it measures what
an ingest would unlock, so Ryan can weigh it against A1's missing-study list.
Output: a3_unlock_studies.csv (one row per study named by untraced labels) and a printed per-set summary.
"""
import os
import re
import sys
from collections import Counter, defaultdict

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a3_common as C  # noqa: E402

TRACED = ("acquisition", "acquisition-stack", "acquisition-stack-geometry", "acquisition-group")


def main():
    D = C.read_csv_dicts(os.path.join(C.OUT_DIR, "a3_labels_distinct.csv"))
    need = defaultdict(list)
    for d in D:
        if d["final_level"] in TRACED:
            continue
        for st in filter(None, d["studies_named"].split(";")):
            need[st].append(d)
    # raw Bruker presence on the drive, per study folder name (exact component match)
    raw = defaultdict(lambda: {"dicom": 0, "2dseq": 0, "exams": set(), "where": set()})
    with open(C.MANIFEST, encoding="utf-8") as f:
        next(f)
        for line in f:
            rel = line.split(",", 1)[0]
            if rel.startswith('"'):
                rel = line[1:].split('",', 1)[0]
            comps = rel.split("\\")
            for i, c in enumerate(comps[:-1]):
                st = C.study_tokens(c)
                if st and st[0] in need:
                    rest = comps[i + 1:]
                    name = rest[-1]
                    if len(rest) >= 3 and rest[1] == "pdata" and name.lower().endswith(".dcm"):
                        raw[st[0]]["dicom"] += 1
                        raw[st[0]]["exams"].add(rest[0])
                    elif name == "2dseq":
                        raw[st[0]]["2dseq"] += 1
                        raw[st[0]]["exams"].add(rest[0])
                    raw[st[0]]["where"].add("\\".join(comps[:i + 1])[:120])
                    break
    acq_studies = {re.sub(r"__\d+$", "", a["original_name"].split("/")[0]) for a in C.read_csv_dicts(C.PROD_ACQS) if a["instrument"] == "MRI"}
    rows = []
    for st, ds in sorted(need.items()):
        r = raw.get(st, {"dicom": 0, "2dseq": 0, "exams": set(), "where": set()})
        rows.append({"study": st, "year": st[:4], "in_production": "Y" if st in acq_studies else "N",
                     "untraced_labels": len(ds), "sets": ";".join(sorted({d["set_id"] for d in ds})),
                     "drive_dicom_files": r["dicom"], "drive_2dseq_files": r["2dseq"], "drive_exams_with_data": len(r["exams"]),
                     "raw_on_drive": "native-dicom" if r["dicom"] else ("2dseq-only" if r["2dseq"] else "no"),
                     "drive_locations": " | ".join(sorted(r["where"]))[:400]})
    C.write_csv(os.path.join(C.OUT_DIR, "a3_unlock_studies.csv"), rows)
    by = defaultdict(Counter)
    lab = defaultdict(Counter)
    for r in rows:
        if r["in_production"] == "N":
            by[r["sets"]][r["raw_on_drive"]] += 1
            lab[r["sets"]][r["raw_on_drive"]] += r["untraced_labels"]
    for s in sorted(by):
        print(f"{s:45s} studies {dict(by[s])}  labels {dict(lab[s])}")
    tot = Counter()
    for r in rows:
        if r["in_production"] == "N":
            tot[r["raw_on_drive"]] += 1
    print("studies not in production named by untraced labels:", dict(tot))


if __name__ == "__main__":
    main()
