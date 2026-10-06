"""A1 step 2f: re-derive the hub's 639 / 308 / 331 split, and say what the difference is made of.

The hub (records\\coverage2.py) called a "study" every path segment shaped YYYYMMDD_HHMMSS_<rest>
(the first such segment of each file path) and compared the names with registry_raw.original_name
(instrument MRI, study part). That counts folders NAMED after a study that hold no ParaVision exam
(Splits volumes, segmentations, NIfTI exports: class (f), not an exam) as studies.

This script: (1) re-runs the hub's exact method against today's registry; (2) splits the names
into real ParaVision studies (an exam folder below them) and study-NAMED folders with no exam;
(3) for the second kind, what they hold and whether the study they are named after is in
production or on this drive; (4) checks every study-shaped name on the drive against the 57 study
folders the D3 re-scan found nowhere (tasks/mri_unparsed_rescan_review.md section 6).

Writes a1\\study_names.csv (one row per study-shaped name) and a1\\study_names_summary.txt.

    python a1_25_study_names.py
"""
import collections
import csv
import os
import re

from a1_common import cache_load, gb, out_path, read_csv_dicts, snapshot, write_csv

HUB_RX = re.compile(r"^(\d{8}_\d{6}_[^\\/]+)$")
LOST57 = r"D:\projects\gjesus3\scratch_mri-unparsed-report\D3_lost_studies_derivatives_20261005.csv"


def norm(name):
    """A study-named folder sometimes carries a suffix (' (1)', ' 2'): strip it for the join."""
    return re.sub(r"( \(\d+\)| \d+)$", "", name)


def main():
    df = cache_load("files")
    rows_exam = cache_load("mri_exam_rows")
    reg = read_csv_dicts(snapshot("registry_raw.csv"))
    prod_mri_hub = {r["original_name"].split("/")[0] for r in reg if r["instrument"] == "MRI"}
    prod_any = set()
    for r in reg:
        if r["instrument"] in ("MRI", "XMRI"):
            on = r["original_name"]
            prod_any.add(on.split("/")[0] if "/" in on else on.rsplit("__", 1)[0])
    exam_studies = {r["study"] for r in rows_exam}
    st_inprod = collections.defaultdict(bool)
    for r in rows_exam:
        if r["class"] in ("a", "b"):
            st_inprod[r["study"]] = True
    # the hub's method, verbatim: first study-shaped segment of each path; inner path -> size
    hub_files = collections.defaultdict(dict)
    hub_copies = collections.defaultdict(set)
    seg_files = collections.defaultdict(list)       # name -> [(relpath, size, sha, a1class)]
    for rp, size, sha, cls in zip(df["relpath"], df["size"], df["sha256"], df["a1class"]):
        parts = rp.split("\\")
        for i, seg in enumerate(parts[:-1]):
            if HUB_RX.match(seg):
                hub_files[seg]["\\".join(parts[i + 1:])] = size
                hub_copies[seg].add("\\".join(parts[:i + 1]))
                seg_files[seg].append((rp, size, sha, cls))
                break
    names = sorted(hub_files)
    have = [s for s in names if s in prod_mri_hub]
    miss = [s for s in names if s not in prod_mri_hub]
    ub = lambda s: sum(hub_files[s].values())  # noqa: E731
    lost = {}
    if os.path.exists(LOST57):
        for r in read_csv_dicts(LOST57):
            lost[r["folder"]] = r
    out = []
    for s in names:
        fl = seg_files[s]
        shas = {}
        for rp, size, sha, cls in fl:
            shas[sha] = size
        cls_c = collections.Counter(cls for _, _, _, cls in fl)
        kind = "paravision-study" if s in exam_studies else "study-named folder, no exam (f)"
        base = norm(s)
        out.append({
            "name": s, "kind": kind, "hub_in_production_today": "Y" if s in prod_mri_hub else "N",
            "exam_in_production": ("Y" if st_inprod[s] else "N") if s in exam_studies else "",
            "named_after_study_in_production": "Y" if base in prod_any else "N",
            "named_after_study_on_drive": "Y" if base in exam_studies else "N",
            "in_D3_57_lost": "Y" if s in lost or base in lost else "N",
            "copies": len(hub_copies[s]), "files": len(fl), "hub_unique_bytes": ub(s),
            "sha_distinct_bytes": sum(shas.values()),
            "classes": "; ".join(f"{k} {v}" for k, v in cls_c.most_common()),
            "locations": " | ".join(sorted(hub_copies[s]))})
    write_csv("study_names.csv", out, list(out[0].keys()))
    L = []
    L.append("THE HUB'S METHOD, RE-RUN AGAINST TODAY'S REGISTRY (records\\coverage2.py logic)")
    L.append(f"  production MRI study names today: {len(prod_mri_hub):,} (hub, 2026-09-30: 984)")
    L.append(f"  study-shaped names on the drive: {len(names)}  ({sum(1 for s in names if len(hub_copies[s]) > 1)} in more than one place)")
    L.append(f"    in production by name : {len(have)}  {gb(sum(ub(s) for s in have)):.1f} GB  ({sum(ub(s) for s in have)/2**30:.1f} GiB) hub-unique")
    L.append(f"    NOT in production     : {len(miss)}  {gb(sum(ub(s) for s in miss)):.1f} GB  ({sum(ub(s) for s in miss)/2**30:.1f} GiB) hub-unique")
    L.append("    (hub on 2026-09-30: 308 / 331; 156.9 / 188.0 'GB' = GiB)")
    k = collections.Counter((o["kind"], o["hub_in_production_today"]) for o in out)
    L.append("WHAT THE NAMES ARE")
    for (kind, inp), n in sorted(k.items()):
        L.append(f"  {kind:40s} in production by name {inp}: {n}")
    f_ = [o for o in out if o["kind"].startswith("study-named")]
    L.append(f"  study-named folders with no exam: {len(f_)}, {gb(sum(o['sha_distinct_bytes'] for o in f_)):.1f} GB distinct;"
             f" named after a study in production: {sum(1 for o in f_ if o['named_after_study_in_production'] == 'Y')};"
             f" after a study on this drive: {sum(1 for o in f_ if o['named_after_study_on_drive'] == 'Y')};"
             f" after neither: {sum(1 for o in f_ if o['named_after_study_in_production'] == 'N' and o['named_after_study_on_drive'] == 'N')}")
    fc = collections.Counter()
    for o in f_:
        for part in o["classes"].split("; "):
            c, n = part.rsplit(" ", 1)
            fc[c] += int(n)
    L.append("  their files by class: " + "; ".join(f"{c} {n}" for c, n in fc.most_common()))
    # the hub's own 331-row list (records\mri_missing_studies.csv), today
    hub_list = os.path.join(r"C:\Users\rtasseff\OneDrive - CIC biomaGUNE\projects\DataInfra\gjesus3-archive"
                            r"\historical-mjesus-drive\records", "mri_missing_studies.csv")
    if os.path.exists(hub_list):
        hub_rows = read_csv_dicts(hub_list)
        by = {o["name"]: o for o in out}
        rec = collections.Counter()
        cfg = collections.Counter()
        for h in hub_rows:
            o = by.get(h["bruker_study"])
            k = (o["kind"] if o else "not found on drive", "in production today" if h["bruker_study"] in prod_mri_hub else "not in production")
            rec[k] += 1
            if h["bruker_study"] in prod_mri_hub:
                for r in reg:
                    if r["instrument"] == "MRI" and r["original_name"].split("/")[0] == h["bruker_study"]:
                        cfg[r["ingest_config"].rsplit("/", 1)[-1]] += 1
                        break
        L.append(f"THE HUB'S 331-ROW LIST TODAY ({len(hub_rows)} rows):")
        for (kind, st), n in sorted(rec.items()):
            L.append(f"  {kind:40s} {st:22s} {n}")
        L.append("  ingested since by (first row's config): " + "; ".join(f"{k} {v}" for k, v in cfg.most_common()))
    hits = [o for o in out if o["in_D3_57_lost"] == "Y"]
    L.append(f"D3's 57 study folders 'found nowhere' that are on this drive: {len(hits)}")
    for o in hits:
        L.append(f"    {o['name']}  ({o['kind']}; {o['files']} files)")
    txt = "\n".join(L)
    with open(out_path("study_names_summary.txt"), "w", encoding="utf-8") as f:
        f.write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
