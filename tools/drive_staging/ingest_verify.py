#!/usr/bin/env python3
"""ingest_verify.py -- after a historical-drives batch has run, prove it landed as planned, and emit
its provenance rows. Read-only against the NAS root it is given.

    python tools/drive_staging/ingest_verify.py --nas-root J:\\gjesus3-data --batch B01 [--batch B02 ...]
        [--provenance tasks/drives_ingest_provenance.csv]

For each batch it selects the registry rows whose `ingest_config` is that batch's config and checks,
against the plan (ingest_plan.py expected.csv):

  rows       the batch added exactly the expected set of original_names (no fewer, no more, none twice)
  fields     instrument, project_id (-> the planned project), researcher, operator, subject_ids,
             data_source, instrument_model, sample_type, acquisition_datetime (non-blank, the planned
             date, ACQ-ID date prefix == it), checksum_present = Y
  checksum   the acquisition's checksums.json holds exactly one sha256 and it equals the plan's --
             which is the staging manifest's (ingest_plan.py checked that) -- and the primary's size
  sidecar    metadata.json exists and names the acquisition; its discovered.drv_sha256 is the plan's
  link       a planned project link exists at projects/<folder>/raw_linked/<link_name> and IS the raw
             primary (same file), not a pre-existing file of the same name
  registry   whole-registry duplicate acq_id / original_name = 0

It prints PASS/FAIL per check and exits 1 on any failure. With --provenance it (re)writes the
provenance rows for these batches into that CSV: acq_id, drive, canonical relpath, sha256,
manifest_verified (Y when checksums.json == the staging manifest), other_copies.
"""
import argparse
import collections
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ingest_plan as P  # noqa: E402

PROV_COLS = ["acq_id", "batch", "drive", "relpath", "archive", "member", "sha256", "manifest_verified",
             "other_copies"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--nas-root", required=True)
    ap.add_argument("--batch", action="append", required=True)
    ap.add_argument("--out", default=P.OUT)
    ap.add_argument("--provenance")
    args = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    nas = args.nas_root
    want = set(args.batch)
    exp = {e["original_name"]: e for e in P.load_expected(args.out) if e["batch"] in want}
    rows = list(P.rcsv(os.path.join(nas, "registries", "registry_raw.csv")))
    projects = {r["project_id"]: r for r in P.rcsv(os.path.join(nas, "registries", "registry_projects.csv"))}
    by_name = {r["name"].lower(): r["project_id"] for r in projects.values()}
    cfgs = {f"{P.CONFIG_DIR_REL}/drives_{b}.yaml": b for b in want}
    mine = [r for r in rows if r["ingest_config"] in cfgs]
    fails = collections.OrderedDict((k, []) for k in
                                    ("rows", "fields", "checksum", "sidecar", "link", "registry"))

    # rows
    names = collections.Counter(r["original_name"] for r in mine)
    fails["rows"] += [f"twice: {n}" for n, k in names.items() if k > 1]
    fails["rows"] += [f"missing: {n}" for n in exp if n not in names]
    fails["rows"] += [f"unplanned: {n}" for n in names if n not in exp]
    fails["rows"] += [f"{r['original_name']}: in {cfgs[r['ingest_config']]}, planned {exp[r['original_name']]['batch']}"
                      for r in mine if r["original_name"] in exp
                      and exp[r["original_name"]]["batch"] != cfgs[r["ingest_config"]]]

    prov = []
    for r in mine:
        e = exp.get(r["original_name"])
        if not e:
            continue
        aid = r["acq_id"]
        # fields
        want_pid = by_name.get(e["project"].lower(), "") if e["project"] else ""
        checks = [("instrument", r["instrument"], e["instrument"]),
                  ("project_id", r["project_id"], want_pid),
                  ("researcher", r["researcher"], e["researcher"]),
                  ("operator", r["operator"], e["operator"]),
                  ("subject_ids", r["subject_ids"], e["subject_id"]),
                  ("data_source", r["data_source"], e["data_source"]),
                  ("sample_type", r["sample_type"], e["sample_type"]),
                  ("checksum_present", r["checksum_present"], "Y"),
                  ("acquisition_date", r["acquisition_datetime"][:10], e["acquisition_datetime"][:10]),
                  ("acq_id_date", aid[4:12], e["acquisition_datetime"][:10].replace("-", ""))]
        if e["instrument_model"]:
            checks.append(("instrument_model", r["instrument_model"], e["instrument_model"]))
        elif not r["instrument_model"]:
            checks.append(("instrument_model", "", "(non-blank)"))
        if e["project"] and not want_pid:
            checks.append(("project exists", "no", e["project"]))
        for f, got, w in checks:
            if got != w:
                fails["fields"].append(f"{aid} {r['original_name']}: {f} = {got!r}, planned {w!r}")
        # checksum + primary
        acq_dir = os.path.join(nas, r["canonical_path"].strip("/").replace("/", "\\"))
        ok_sum = False
        try:
            with open(os.path.join(acq_dir, "checksums.json"), encoding="utf-8") as f:
                cs = json.load(f)
            vals = list(cs.values()) if isinstance(cs, dict) else []
            flat = [v.get("sha256") if isinstance(v, dict) else v for v in vals]
            if isinstance(cs, dict) and "files" in cs:
                flat = [x.get("sha256") for x in cs["files"]] if isinstance(cs["files"], list) else \
                       [v.get("sha256") if isinstance(v, dict) else v for v in cs["files"].values()]
            ok_sum = flat == [e["sha256"]]
            if not ok_sum:
                fails["checksum"].append(f"{aid}: checksums.json {flat} != plan {e['sha256']}")
            prim = os.path.join(acq_dir, r["primary_file_name"])
            if os.path.getsize(prim) != int(e["size"]):
                fails["checksum"].append(f"{aid}: primary size {os.path.getsize(prim)} != {e['size']}")
                ok_sum = False
        except Exception as ex:  # noqa: BLE001 -- tallied as a failure, never swallowed
            fails["checksum"].append(f"{aid}: {type(ex).__name__}: {ex}")
        # sidecar
        try:
            with open(os.path.join(acq_dir, "metadata.json"), encoding="utf-8") as f:
                sc = json.load(f)
            if sc.get("acq_id") != aid:
                fails["sidecar"].append(f"{aid}: sidecar acq_id {sc.get('acq_id')!r}")
            if (sc.get("discovered") or {}).get("drv_sha256") != e["sha256"]:
                fails["sidecar"].append(f"{aid}: sidecar discovered.drv_sha256 != plan")
        except Exception as ex:  # noqa: BLE001
            fails["sidecar"].append(f"{aid}: {type(ex).__name__}: {ex}")
        # link
        if e["project"] and want_pid:
            folder = projects[want_pid]["folder_location"].strip("/").replace("/", "\\")
            link = os.path.join(nas, folder, "raw_linked", e["link_name"])
            prim = os.path.join(acq_dir, r["primary_file_name"])
            try:
                if not os.path.samefile(link, prim):
                    fails["link"].append(f"{aid}: {link} exists but is NOT the raw primary")
            except FileNotFoundError:
                fails["link"].append(f"{aid}: no link {link}")
        prov.append({"acq_id": aid, "batch": e["batch"], "drive": P.DRIVES[e["drive"]][1],
                     "relpath": e["relpath"], "archive": e["archive"], "member": e["member"],
                     "sha256": e["sha256"], "manifest_verified": "Y" if ok_sum else "N",
                     "other_copies": e["other_copies"]})

    # registry-wide duplicates
    ids = collections.Counter(r["acq_id"] for r in rows)
    fails["registry"] += [f"duplicate acq_id {k}" for k, n in ids.items() if n > 1]
    on = collections.Counter(r["original_name"] for r in rows if r["original_name"])
    fails["registry"] += [f"duplicate original_name {k}" for k, n in on.items() if n > 1 and k in exp]

    print(f"batches {sorted(want)}: planned {len(exp)}, registry rows from these configs {len(mine)}")
    for k, v in fails.items():
        print(f"{'PASS' if not v else 'FAIL'}  {k}  ({len(v)})")
        for x in v[:15]:
            print(f"      {x}")
    if args.provenance:
        old = []
        if os.path.isfile(args.provenance):
            old = [p for p in P.rcsv(args.provenance) if p["batch"] not in want]
        P.wcsv(args.provenance, PROV_COLS, sorted(old + prov, key=lambda p: p["acq_id"]))
        print(f"provenance: {len(prov)} rows for {sorted(want)} -> {args.provenance}")
    sys.exit(0 if not any(fails.values()) else 1)


if __name__ == "__main__":
    main()
