#!/usr/bin/env python3
"""relink_split_sidecars.py — re-point a project's raw_linked copy of an
acquisition's metadata.json at the /raw sidecar when the two have become
separate files.

Why (2026-11-07): a project's `raw_linked/<link>/` folder holds hard links to
every file of the acquisition, its `metadata.json` included, so the project
sees the sidecar the registry points to. A tool that rewrites the /raw sidecar
by temp file + os.replace puts a NEW file at the /raw path; the project link
keeps the old one and goes stale. `backfill_sidecar_condition.py` did that to
76 CNIC-HEARDS sidecars before it was changed to write in place. This tool
finds such splits and repairs them.

What it does, per `hardlink-folder` row of each project's provenance.csv:
  - same file as /raw                -> nothing to do
  - separate file                    -> (with --apply) hard-link the /raw
                                        sidecar to <link>.relink.tmp, replace the
                                        project copy with it, verify samefile
The /raw sidecar is the authority and is never written. Only the project-side
copy is replaced. DRY-RUN by default; --apply writes; --project limits it.

    python tools/relink_split_sidecars.py --nas-root J:/gjesus3-data [--project PROJ-0066] [--apply]
"""

import argparse
import csv
import os
import sys


def log(msg, level="INFO"):
    print(f"[relink-sidecars] {level}: {msg}")


def _samefile(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def find_pairs(nas_root, project=None):
    """Yield (project_id, acq_id, link_sidecar, raw_sidecar) for every project
    folder link whose folder holds a metadata.json."""
    regdir = os.path.join(nas_root, "registries")
    with open(os.path.join(regdir, "registry_raw.csv"), encoding="utf-8", newline="") as f:
        reg = {r["acq_id"]: r for r in csv.DictReader(f)}
    with open(os.path.join(regdir, "registry_projects.csv"), encoding="utf-8", newline="") as f:
        projs = list(csv.DictReader(f))
    for p in projs:
        if project and p["project_id"] != project:
            continue
        folder = (p.get("folder_location") or "").strip("/").split("/")[-1] or p.get("name", "")
        pdir = os.path.join(nas_root, "projects", folder)
        prov = os.path.join(pdir, "provenance.csv")
        if not os.path.isfile(prov):
            continue
        with open(prov, encoding="utf-8", newline="") as f:
            for e in csv.DictReader(f):
                if e.get("file_type") != "hardlink-folder":
                    continue
                r = reg.get(e.get("input_refs", ""))
                if not r:
                    continue
                link_sc = os.path.join(pdir, *e["output_path"].split("/"), "metadata.json")
                raw_sc = os.path.join(nas_root, *r["canonical_path"].strip("/").split("/"), "metadata.json")
                if os.path.isfile(link_sc) and os.path.isfile(raw_sc):
                    yield p["project_id"], r["acq_id"], link_sc, raw_sc


def relink(link_sc, raw_sc):
    """Replace the project copy with a hard link to the /raw sidecar. Returns (ok, detail)."""
    tmp = link_sc + ".relink.tmp"
    if os.path.exists(tmp):
        return False, f"leftover {tmp}; remove it by hand after checking"
    try:
        os.link(raw_sc, tmp)
        os.replace(tmp, link_sc)
    except OSError as e:
        if os.path.exists(tmp):
            os.remove(tmp)
        return False, f"relink failed: {e}"
    if not _samefile(link_sc, raw_sc):
        return False, "verify FAILED: project copy is still not the /raw file"
    return True, "relinked + verified"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--nas-root", required=True)
    ap.add_argument("--project", default=None, help="Only this project_id.")
    ap.add_argument("--apply", action="store_true", help="Write. Default is a dry-run.")
    args = ap.parse_args(argv)
    counts = {"pairs": 0, "same-file": 0, "split-identical": 0, "split-stale": 0, "relinked": 0, "error": 0}
    log(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}{' project=' + args.project if args.project else ''}")
    for pid, acq, link_sc, raw_sc in find_pairs(args.nas_root, args.project):
        counts["pairs"] += 1
        if _samefile(link_sc, raw_sc):
            counts["same-file"] += 1
            continue
        with open(link_sc, "rb") as a, open(raw_sc, "rb") as b:
            state = "split-identical" if a.read() == b.read() else "split-stale"
        counts[state] += 1
        if not args.apply:
            log(f"{pid} {acq}: {state}; WOULD relink {link_sc}")
            continue
        ok, detail = relink(link_sc, raw_sc)
        counts["relinked" if ok else "error"] += 1
        log(f"{pid} {acq}: {state}; {detail}", "INFO" if ok else "ERROR")
    print()
    log(f"Summary: {counts}")
    return 1 if counts["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
