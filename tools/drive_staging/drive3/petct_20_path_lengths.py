"""Longest source path the ingest opens, and longest project-link path it creates (no \\\\?\\ prefix in the ingest)."""
import csv
import os

OUT = r"D:\projects\gjesus3\drive3_streams\petct\out"
STAGE = r"D:\projects\gjesus3\drive3_streams\petct\stage\new102"
SNAP = r"J:\gjesus3-data\staging\ni_gnuclear_20260812"
plan = list(csv.DictReader(open(os.path.join(OUT, "plan_202.csv"), encoding="utf-8")))
src = [os.path.join(STAGE if p["source"] == "drive" else SNAP, p["source_rel"].replace("/", os.sep)) for p in plan]
links = [os.path.join(r"J:\gjesus3-data\projects", p["project_name"], "raw_linked",
                      f"{p['modality']}_{p['subject']}_{p['acq_date']}_{p['acq_key'][:14]}_recon{p['acq_key'][-1]}",
                      "recon0_frameMULTI.dcm") for p in plan if p["project_name"]]
print("longest source path:", max(map(len, src)), max(src, key=len))
print("longest link path:", max(map(len, links)))
