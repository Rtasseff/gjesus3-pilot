#!/usr/bin/env python3
"""c_manifest_check.py -- stream C (drive 3): the coordinator's INDEPENDENT check of ingested batches,
straight against the drive manifest. READ-ONLY on the NAS root it is given.

It does not use the plan (expected.csv) at all, so it checks the plan as much as the run:

  rows      the registry rows whose ingest_config is each batch's config; their count equals the
            batch's `files` in the committed batches.csv; no original_name or acq_id twice in the registry
  manifest  each row's original_name is `drive3_MJesus-MFB/<path>`; that path is a row of the DRIVE
            MANIFEST (D:\\...\\drive3_manifest.csv, the staging record); the acquisition's live
            checksums.json holds exactly ONE hash, under the primary's name, equal to the manifest's
            sha256; and the primary's size on the NAS equals the manifest's size
  link      a row with a project has the committed case table's drv_link_name in that project's
            raw_linked\\, and it IS the primary (same file)
  orphans   every ACQ-* folder under raw\\MICROSCOPY\\<yyyy>\\<yyyy-mm>\\ of the months these rows fall in is
            a live registry row or a retired one (a crashed run can leave a copied folder behind)

    python tools/drive_staging/drive3/c_manifest_check.py --nas-root J:\\gjesus3-data --batch C01 [--batch C02 ...]
    python tools/drive_staging/drive3/c_manifest_check.py --nas-root <rehearsal root> --batch C01

Exit 1 on any failure. Close-out step 1 ("every ingested file's SHA-256 matched against the drive
manifest") is this command over every batch.
"""
import argparse
import collections
import csv
import io
import json
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.dirname(HERE)
sys.path.insert(0, DS)
import ingest_plan as P  # noqa: E402

P.use_profile("drive3_2026-10")        # the default; --profile drive3x_2026-10 for the Biodonostia XMIC batches
LABEL = P.DRIVES["D3"][1]


def rd(path):
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--nas-root", required=True)
    ap.add_argument("--batch", action="append", required=True)
    ap.add_argument("--profile", default="drive3_2026-10", choices=[p for p in P.PROFILES if p.startswith("drive3")])
    args = ap.parse_args()
    P.use_profile(args.profile)
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")
    nas = args.nas_root
    reg = rd(os.path.join(nas, "registries", "registry_raw.csv"))
    retired = set()
    rp = os.path.join(nas, "registries", "retired_acquisitions.csv")
    if os.path.isfile(rp):
        retired = {r["acq_id"] for r in rd(rp)}
    projects = {r["project_id"]: r for r in rd(os.path.join(nas, "registries", "registry_projects.csv"))}
    batches = {r["batch"]: r for r in rd(os.path.join(P.CONFIG_DIR, "batches.csv"))}
    man = P.load_manifest(P.MANIFEST)
    fails = collections.OrderedDict((k, []) for k in ("rows", "manifest", "link", "orphans"))
    ids = collections.Counter(r["acq_id"] for r in reg)
    names = collections.Counter(r["original_name"] for r in reg if r["original_name"])
    live = {r["acq_id"] for r in reg}
    months = set()
    n_rows = 0
    for b in args.batch:
        if b not in batches:
            raise SystemExit(f"batch {b} is not in {P.CONFIG_DIR}\\batches.csv")
        cases = {c["original_name"]: c for c in rd(os.path.join(P.CONFIG_DIR, f"cases_{b}.csv"))}
        mine = [r for r in reg if r["ingest_config"] == P.config_file(b)]
        n_rows += len(mine)
        if len(mine) != int(batches[b]["files"]):
            fails["rows"].append(f"{b}: {len(mine)} registry rows, batches.csv says {batches[b]['files']}")
        for r in mine:
            aid = r["acq_id"]
            if ids[aid] > 1 or names[r["original_name"]] > 1:
                fails["rows"].append(f"{aid}: acq_id or original_name twice in the registry")
            if not r["original_name"].startswith(LABEL + "/"):
                fails["manifest"].append(f"{aid}: original_name is not under {LABEL}/")
                continue
            rel = r["original_name"][len(LABEL) + 1:].replace("/", "\\")
            m = man.get(rel)
            if m is None:
                fails["manifest"].append(f"{aid}: {rel} is not in the drive manifest")
                continue
            acq_dir = os.path.join(nas, r["canonical_path"].strip("/").replace("/", "\\"))
            months.add(os.path.dirname(acq_dir.rstrip("\\")))
            try:
                with io.open(os.path.join(acq_dir, "checksums.json"), encoding="utf-8") as f:
                    files = json.load(f).get("files", {})
                prim = os.path.join(acq_dir, r["primary_file_name"])
                if list(files) != [r["primary_file_name"]] or files[r["primary_file_name"]] != m["sha256"]:
                    fails["manifest"].append(f"{aid}: checksums.json {files} != manifest {m['sha256'][:16]}")
                if os.path.getsize(prim) != int(m["size"]):
                    fails["manifest"].append(f"{aid}: primary {os.path.getsize(prim)} B != manifest {m['size']} B")
            except Exception as ex:   # counted as a failure, never swallowed
                fails["manifest"].append(f"{aid}: {type(ex).__name__}: {ex}")
                continue
            pid = (r["project_id"] or "").strip()
            if pid:
                c = cases.get(r["original_name"])
                link = os.path.join(nas, projects[pid]["folder_location"].strip("/").replace("/", "\\"),
                                    "raw_linked", c["drv_link_name"] if c else "?")
                try:
                    if not os.path.samefile(link, prim):
                        fails["link"].append(f"{aid}: {link} is not the primary")
                except FileNotFoundError:
                    fails["link"].append(f"{aid}: no link {link}")
    for mdir in sorted(months):
        for d in sorted(os.listdir(mdir)):
            if d.startswith("ACQ-") and d not in live and d not in retired:
                fails["orphans"].append(f"{os.path.join(mdir, d)}: a folder with no registry row")
    print(f"batches {args.batch}: {n_rows} registry rows checked against {P.MANIFEST} "
          f"({len(man):,} manifest rows); {len(months)} month folders scanned for orphans")
    for k, v in fails.items():
        print(f"{'PASS' if not v else 'FAIL'}  {k}  ({len(v)})")
        for x in v[:15]:
            print(f"      {x}")
    return 0 if not any(fails.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
