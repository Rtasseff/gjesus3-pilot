#!/usr/bin/env python3
"""x_placement.py -- the hand-over lists of the M. Jesus drive's FOURTH placement batch (stream P's tool, its
later-batch path `p_plan.py handover`, as `biomaGUNE MJ` was the third). Record: tasks/drive3_foreign_raw_gate.md.

Three kinds of file the raw streams left out, each placed as project material, never registered:
  * the Leica TCS SP8 #8100000207 confocal files (`.lif` 17, `.lifext` 9): biomaGUNE's own former microscope
    (Irene, 2026-10-08); gjesus3 has no `.lif` reader and no instrument code for it, so they are not registered.
    Project: the claim's, when that project is active (else the holding folder);
  * the one `.czi` with no instrument metadata (A1 `czi-processed`, 2 copies of one content): no hardware or
    experiment block, so not an acquisition record. Project: its claim's (none: the holding folder, "no claim");
  * AFTER the XMIC ingest (`nonraw`): the Biodonostia Axioscan files the plan routed to the project folder as
    non-raw (pixel-identical copies under another name), each tied to its parent's ACQ-ID.

    python tools/drive_staging/drive3/x_placement.py lists  --out DIR [--nas J:\\gjesus3-data]
    python tools/drive_staging/drive3/x_placement.py nonraw --out DIR [--nas J:\\gjesus3-data]
then `p_plan.py handover --csv DIR\\<list> --stream X ...` (the gate's commands).

READ-ONLY on J: (the registry and the project list are read). Writes only under --out.
"""
import argparse
import collections
import csv
import io
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(DS))
for _p in (DS, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

ANALYSIS = r"D:\projects\gjesus3\drive3_analysis"
A2_FILES = os.path.join(ANALYSIS, "a2", "files.csv")
OUT_OF_SCOPE = os.path.join(REPO, "tasks", "drive3_czi_out_of_scope.csv")     # stream C's list: the input
LEICA_REASON = ("raw confocal images from biomaGUNE's former Leica TCS SP8 (#8100000207; Irene, 2026-10-08); "
                "not registered: gjesus3 has no reader or instrument code for Leica .lif files")
HANDOVER_COLS = ["relpath", "kind", "project", "reason", "parent_acq_ids", "sha256", "class", "claim_id", "verdict"]


def rd(path):
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def wcsv(path, cols, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def projects_of(nas):
    return {r["name"].strip(): r for r in rd(os.path.join(nas, "registries", "registry_projects.csv"))}


def leica_and_processed(oos, a2, projects):
    """The hand-over rows for the Leica files and the processed .czi (pure: tested). oos: stream C's
    out-of-scope rows; a2: {relpath: A2 files.csv row}; projects: {name: registry_projects row}."""
    rows, problems = [], []
    for r in oos:
        if r["serials"] == "4661000340":
            continue                                  # the Axioscan: registered as XMIC, not placed
        a = a2.get(r["relpath"])
        if a is None or a["sha256"] != r["sha256"] or int(a["size"]) != int(r["size"]):
            problems.append(f"not in A2's table with the same bytes: {r['relpath']}")
            continue
        leica = r["ext"].lower() in (".lif", ".lifext")
        if not leica and r["czi_class"] != "czi-processed":
            problems.append(f"neither Leica nor the processed .czi: {r['relpath']}")
            continue
        claim = a["proposed_project"] if a["verdict"] in ("CONFIRMED", "A") else ""
        status = (projects.get(claim) or {}).get("status", "").strip() if claim else ""
        project = claim if status == "active" else ""
        if claim and not project:
            problems.append(f"{r['relpath']}: its claim {claim} is {status or 'not registered'}: holding? (stop)")
            continue
        if leica:
            reason = LEICA_REASON
        else:
            reason = "no claim" if not claim else ("a .czi with no instrument metadata (no hardware or "
                                                   "experiment block): not an acquisition record")
        rows.append({"relpath": r["relpath"], "kind": "other", "project": project, "reason": reason,
                     "parent_acq_ids": "", "sha256": r["sha256"], "class": a["cls"] if leica else "czi-processed",
                     "claim_id": a["claim_id"], "verdict": a["verdict"] if a["verdict"] != "NO-CLAIM" else ""})
    return rows, problems


def cmd_lists(args):
    oos = rd(OUT_OF_SCOPE)
    want = {r["relpath"] for r in oos}
    a2 = {r["relpath"]: r for r in rd(A2_FILES) if r["relpath"] in want}
    rows, problems = leica_and_processed(oos, a2, projects_of(args.nas))
    for p in problems:
        print("  PROBLEM:", p)
    if problems:
        return 1
    out = os.path.join(args.out, "foreign_handover.csv")
    wcsv(out, HANDOVER_COLS, rows)
    c = collections.Counter((r["project"] or "(holding)", r["class"]) for r in rows)
    print(f"foreign_handover.csv: {len(rows)} rows, {sum(int(x['size']) for x in oos if x['relpath'] in {r['relpath'] for r in rows}) / 1e9:.2f} GB; "
          f"{dict(c)} -> {out}")
    return 0


def nonraw_rows(nonraw, reg, config_prefix):
    """The XMIC plan's non-raw rows with their parent's ACQ-ID from the registry (pure: tested). nonraw: the
    plan's nonraw_derived.csv; reg: registry rows; config_prefix: the XMIC configs' ingest_config prefix."""
    by_name = collections.defaultdict(list)
    for r in reg:
        if (r.get("ingest_config") or "").startswith(config_prefix):
            by_name[r["original_name"]].append(r)
    rows, problems = [], []
    for n in nonraw:
        parent = by_name.get(n["parent_original_name"], [])
        if len(parent) != 1:
            problems.append(f"{n['relpath']}: parent {n['parent_original_name']} has {len(parent)} XMIC registry "
                            "rows (run after the XMIC ingest)")
            continue
        p = parent[0]
        rows.append({"relpath": n["relpath"], "kind": "derivative", "project": n["destination_project"],
                     "reason": f"{n['class']}, pixel-identical to {p['acq_id']} under another name "
                               "(Biodonostia Axioscan 7; tasks/drive3_foreign_raw_gate.md)",
                     "parent_acq_ids": p["acq_id"], "sha256": n["sha256"], "class": "derivative-czi",
                     "claim_id": "", "verdict": ""})
    return rows, problems


def cmd_nonraw(args):
    import ingest_plan as P
    P.use_profile("drive3x_2026-10")
    nonraw = rd(os.path.join(P.OUT, "nonraw_derived.csv"))
    reg = rd(os.path.join(args.nas, "registries", "registry_raw.csv"))
    rows, problems = nonraw_rows(nonraw, reg, P.CONFIG_DIR_REL + "/" + P.CONFIG_PREFIX)
    for p in problems:
        print("  PROBLEM:", p)
    if problems:
        return 1
    out = os.path.join(args.out, "xmic_nonraw_handover.csv")
    wcsv(out, HANDOVER_COLS, rows)
    print(f"xmic_nonraw_handover.csv: {len(rows)} rows "
          f"{dict(collections.Counter(r['project'] or '(holding)' for r in rows))} -> {out}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--nas", default=r"J:\gjesus3-data", help="read-only: the registry and the project list")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("lists", "nonraw"):
        s = sub.add_parser(name)
        s.add_argument("--out", required=True)
    args = ap.parse_args()
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")
    return {"lists": cmd_lists, "nonraw": cmd_nonraw}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
