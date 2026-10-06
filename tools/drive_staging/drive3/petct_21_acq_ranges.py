"""The ACQ-IDs a NAS root gave the plan's 202 (read-only): ranges per date and modality, per project, per source."""
import collections
import csv
import io
import os
import sys

OUT = r"D:\projects\gjesus3\drive3_streams\petct\out"


def main():
    root = sys.argv[1]
    plan = {p["acq_key"]: p for p in csv.DictReader(open(os.path.join(OUT, "plan_202.csv"), encoding="utf-8"))}
    with io.open(os.path.join(root, "registries", "registry_raw.csv"), encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["original_name"] in plan]
    grp = collections.defaultdict(list)
    for r in rows:
        grp[r["acq_id"].rsplit("-", 1)[0]].append(int(r["acq_id"].rsplit("-", 1)[1]))
    parts = []
    for prefix in sorted(grp):
        s = sorted(grp[prefix])
        parts.append(f"{prefix}-{s[0]:03d}" + (f"…{s[-1]:03d}" if len(s) > 1 else "") +
                     ("" if s == list(range(s[0], s[-1] + 1)) else " (gaps)"))
    print(f"{len(rows)} rows; {len(grp)} date/modality prefixes:")
    print("  " + ", ".join(parts))
    print("by project_id:", sorted(collections.Counter(r["project_id"] or "(none)" for r in rows).items()))
    print("by source config:", sorted(collections.Counter(r["ingest_config"].rsplit("/", 1)[-1] for r in rows).items()))


if __name__ == "__main__":
    main()
