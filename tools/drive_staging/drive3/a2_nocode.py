#!/usr/bin/env python3
"""a2_nocode.py -- HANDOFF §6 item 5: folders with no code, and the evidence that could tie them to a
protocol. Read-only.

A "no-code group" = the files outside `biomaGUNE MJ` whose engine verdict is NO-CLAIM or (C), grouped by
their folder three levels down (two for files higher up). For each group, the evidence is MEASURED:
  * prod_projects   production's own registration of the group's raw files: every A1 file whose exact
                    bytes are an acquisition file in /raw/ names that acquisition's registered project;
  * twin_projects   projects of byte-identical copies elsewhere on drive 3 that DO carry a claim, and of
                    identical files already placed by drives 1+2;
  * study_matches   ParaVision study names in the group's paths that are also study folders under a
                    claimed `Proyecto` folder on the drive (the claimed folder's project);
  * held            how many of the group's bytes are already in the drives-1+2 holding folder.

Output: a2\\nocode_groups.csv. The classification (confirmed by evidence / A / B / C) is the report's,
§5, made from this table and stated with its evidence.
"""
import collections
import csv
import os
import re

import a2_common as C

STUDY_RE = re.compile(r"\d{8}_\d{6}_[^\\]+?_\d+_\d+")


def main():
    C.stdout_utf8()
    files = list(C.it(os.path.join(C.OUT, "files.csv")))
    acqs = {r["acq_id"]: r for r in C.it(C.PROD_ACQS)}
    pid2name = {r["project_id"]: n for n, r in C.load_projects().items()}
    by_sha = collections.defaultdict(list)
    for f in files:
        by_sha[f["sha256"]].append(f)
    # study name -> projects of the claimed folders that hold it
    study_proj = collections.defaultdict(set)
    for f in files:
        if f["proposed_project"] and f["verdict"] in ("CONFIRMED", "A"):
            for m in STUDY_RE.finditer(f["relpath"]):
                study_proj[m.group(0)].add(f["proposed_project"])
    groups = collections.defaultdict(list)
    for f in files:
        if f["top"] in ("biomaGUNE MJ", "(drive root)") or f["owner"] == "junk":
            continue
        if f["verdict"] not in ("NO-CLAIM", "C"):
            continue
        parts = f["relpath"].split("\\")
        key = "\\".join(parts[:3]) if len(parts) > 3 else "\\".join(parts[:-1])
        groups[key].append(f)
    out = []
    for key, fs in sorted(groups.items(), key=lambda kv: -sum(int(f["size"]) for f in kv[1])):
        own = collections.Counter(f["owner"] for f in fs)
        verd = collections.Counter(f["verdict"] for f in fs)
        prod = collections.Counter()
        twin = collections.Counter()
        study = collections.Counter()
        held = 0
        for f in fs:
            for a in filter(None, f["in_raw"].split(";")):
                p = acqs.get(a, {}).get("project_id", "")
                prod[pid2name.get(p, p or "(blank project)")] += 1
            tw = {t["proposed_project"] for t in by_sha[f["sha256"]]
                  if t is not f and t["proposed_project"] and t["verdict"] in ("CONFIRMED", "A")}
            for p in tw | set(filter(None, f["placed12"].split(";"))):
                twin[p] += 1
            for m in STUDY_RE.finditer(f["relpath"]):
                for p in study_proj.get(m.group(0), ()):
                    study[p] += 1
            held += bool(f["holding12"])
        out.append({"folder": key, "files": len(fs), "gb": C.gb(sum(int(f["size"]) for f in fs)),
                    "a1_files": own["A1"], "a2_files": own["A2"],
                    "verdicts": "; ".join(f"{k} {v}" for k, v in verd.most_common()),
                    "prod_projects": "; ".join(f"{k} {v}" for k, v in prod.most_common()),
                    "twin_projects": "; ".join(f"{k} {v}" for k, v in twin.most_common(4)),
                    "study_matches": "; ".join(f"{k} {v}" for k, v in study.most_common(4)),
                    "held_in_drives12_holding": held,
                    "example": fs[0]["relpath"][len(key) + 1:][:120]})
    C.wcsv(C.out_path("nocode_groups.csv"), list(out[0].keys()), out, bom=True)
    C.say(f"nocode_groups.csv: {len(out)} groups, {sum(o['files'] for o in out):,} files")
    for o in out[:45]:
        C.say(f"{o['files']:6d} {o['gb']:>7s} GB  A1 {o['a1_files']:5d} A2 {o['a2_files']:5d}  {o['folder']}")
        for k in ("prod_projects", "twin_projects", "study_matches"):
            if o[k]:
                C.say(f"          {k}: {o[k]}")


if __name__ == "__main__":
    main()
