#!/usr/bin/env python3
"""r4_window_checks.py -- snapshot before, verify after, each retire run of the r4 lists (stream D, write window 2026-10-04).

ONE-TIME tool. Read-only on the NAS: it only reads (and copies the registry files and the six trees' index documents to
<OUT>\\window\\ as a backup). Use it around each `retire_acquisition.py --list ... --execute`:

    python tools/drive_staging/r4_window_checks.py snapshot --lists scalebars        # BEFORE the run
    ... retire_acquisition.py --list ...2026-10_r4_scalebars.csv --execute ...
    python tools/drive_staging/r4_groups.py index --lists scalebars --execute
    python tools/drive_staging/r4_window_checks.py verify --lists scalebars         # AFTER the index step

`verify` is the close-out plan's Step 5 item 3 checklist, per list; it exits 1 on the first list of failures:
  registry   registry_raw.csv is the snapshot minus exactly the list's rows (byte for byte, every other row, line ending
             and quote untouched); ingest_manifest.csv likewise; the tombstones are appended; registry_subjects.csv and
             registry_projects.csv are byte-identical; no ACQ-ID of the list is live
  tombstone  one per row: disposition derivative, superseded_by = the original, moved_to = the planned destination
  raw        each retiree's /raw/ folder is gone
  file       each destination file exists, has the staged size, and its SHA-256 equals the staged drive copy's
  originals  each original is still live with the identical registry row, and its /raw/ folder is as it was (names,
             sizes, modification times)
  links      the raw_linked links the dry run said would go are gone, and nothing else in the six raw_linked folders changed
  provenance each touched project's provenance.csv grew by the events the dry run announced, and only grew
  index      each project's _INDEX.csv has the list's rows (note: "retired derivative of <original>, formerly <id>") and
             every other row unchanged; _PATHMAP.csv is a superset
The validator is run by hand (`validate_registries.py --no-enrichment`): see the review.
"""
import argparse
import collections
import concurrent.futures as cf
import csv
import hashlib
import io
import json
import os
import re
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r4_groups as R  # noqa: E402

NAS = R.NAS
OUT = R.OUT
W = os.path.join(OUT, "window")
SNAP = os.path.join(W, "snapshot.json")
REG_FILES = ("registry_raw.csv", "ingest_manifest.csv", "retired_acquisitions.csv", "registry_subjects.csv",
             "registry_projects.csv")
PROJECTS = ["AE-biomaGUNE-0219", "AE-biomaGUNE-0420", "AE-biomaGUNE-0721", "AE-biomaGUNE-1019", "AE-biomaGUNE-1123",
            "AE-biomaGUNE-1321"]
BASE = "working\\historical_drives"


def lp(path):
    path = os.path.abspath(path)
    if path.startswith("\\\\?\\"):
        return path
    return "\\\\?\\UNC\\" + path[2:] if path.startswith("\\\\") else "\\\\?\\" + path


def read_bytes(path):
    with open(lp(path), "rb") as f:
        return f.read()


def sha256_file(path, bufsize=8 << 20):
    h = hashlib.sha256()
    with open(lp(path), "rb") as f:
        while True:
            b = f.read(bufsize)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def project_dir(proj):
    return os.path.join(NAS, "projects", proj)


def list_rows(names):
    rows = []
    for n in names:
        for r in R.rcsv(os.path.join(R.RETIRE_LISTS, R.LIST_FILES[R.LIST_SHORT[n]])):
            r["list"] = n
            rows.append(r)
    return rows


def tree_walk(path):
    """{relative path: (size, mtime_ns)} of every file under `path`."""
    out = {}
    stack = [path]
    while stack:
        d = stack.pop()
        with os.scandir(lp(d)) as it:
            for e in it:
                if e.is_dir(follow_symlinks=False):
                    stack.append(e.path)
                else:
                    st = e.stat(follow_symlinks=False)
                    out[os.path.relpath(e.path.replace("\\\\?\\", ""), path)] = (st.st_size, st.st_mtime_ns)
    return out


def dry_run_links(names):
    """The raw_linked links the (full) dry run of each list said would be removed: [(project, link name)]."""
    out = []
    for n in names:
        log = os.path.join(OUT, "dryruns", f"2026-10_r4_{n}_full.log")
        txt = io.open(log, encoding="utf-8", errors="replace").read()
        for m in re.finditer(r"link: remove\s+/projects/([^/]+)/raw_linked/(.+?) -- now lives at", txt):
            out.append((m.group(1), m.group(2)))
    return out


def dry_run_events(names):
    """{project: events announced} -- 'will: append N provenance event row(s)' per item, attributed to the item's
    project by the 'regenerate index.html for [PROJ-...]' line that follows it."""
    ev = collections.Counter()
    projs = {r["project_id"]: r["name"] for r in R.rcsv(os.path.join(NAS, "registries", "registry_projects.csv"))}
    for n in names:
        txt = io.open(os.path.join(OUT, "dryruns", f"2026-10_r4_{n}_full.log"), encoding="utf-8", errors="replace").read()
        for m in re.finditer(r"will: append (\d+) provenance event row\(s\)\s+will: regenerate index\.html for \['(PROJ-\d+)'", txt):
            ev[projs[m.group(2)]] += int(m.group(1))
    return ev


def line_count(path):
    with open(lp(path), "rb") as f:
        return sum(1 for _ in f)


def cmd_snapshot(args):
    names = [x for x in args.lists.split(",") if x]
    rows = list_rows(names)
    os.makedirs(W, exist_ok=True)
    tag = time.strftime("%H%M%S")
    bdir = os.path.join(W, f"before_{'_'.join(names)}_{tag}")
    os.makedirs(os.path.join(bdir, "registries"))
    for f in REG_FILES:
        shutil.copy2(os.path.join(NAS, "registries", f), os.path.join(bdir, "registries", f))
    for p in PROJECTS:
        d = os.path.join(bdir, "trees", p)
        os.makedirs(d)
        for f in ("_INDEX.csv", "_PATHMAP.csv"):
            shutil.copy2(lp(os.path.join(project_dir(p), BASE, f)), lp(os.path.join(d, f)))
    reg = {r["acq_id"]: r for r in R.rcsv(os.path.join(NAS, "registries", "registry_raw.csv"))}
    snap = {"names": names, "bdir": bdir, "time": time.strftime("%Y-%m-%d %H:%M:%S"), "rows": {}, "raw_linked": {},
            "provenance_lines": {}, "counts": {}, "sha": {}, "links": dry_run_links(names), "events": dict(dry_run_events(names))}
    for r in rows:
        a, t = reg.get(r["acq_id"]), reg.get(r["target_acq_id"])
        if not a or not t:
            print(f"STOP: {r['acq_id']} or its original {r['target_acq_id']} is not live in registry_raw")
            return 1
        snap["rows"][r["acq_id"]] = {"list": r["list"], "target": r["target_acq_id"], "project": r["to_project"],
                                     "subfolder": r["subfolder"], "dest_name": r["dest_name"], "retiree_row": a,
                                     "original_row": t, "orig_files": None}
    done = {}
    for acq, s in snap["rows"].items():
        t = s["original_row"]
        key = t["acq_id"]
        if key not in done:
            folder = os.path.join(NAS, t["canonical_path"].strip("/").replace("/", "\\"))
            done[key] = tree_walk(folder)
        s["orig_files"] = done[key]
    for p in PROJECTS:
        rl = os.path.join(project_dir(p), "raw_linked")
        snap["raw_linked"][p] = {n: list(v) for n, v in tree_walk(rl).items()} if os.path.isdir(lp(rl)) else {}
        pv = os.path.join(project_dir(p), "provenance.csv")
        snap["provenance_lines"][p] = line_count(pv) if os.path.exists(lp(pv)) else None
    for f in REG_FILES:
        snap["counts"][f] = line_count(os.path.join(NAS, "registries", f))
        snap["sha"][f] = hashlib.sha256(read_bytes(os.path.join(NAS, "registries", f))).hexdigest()
    with open(SNAP, "w", encoding="utf-8") as f:
        json.dump(snap, f)
    print(f"snapshot for {names}: {len(rows)} rows, {len(done)} originals, backup in {bdir}")
    print("  registry lines:", {k: v for k, v in snap["counts"].items()})
    print("  links expected to go:", len(snap["links"]), "| provenance events announced:", snap["events"])
    return 0


class Report:
    def __init__(self):
        self.fail = []
        self.n = 0

    def check(self, cond, msg):
        self.n += 1
        print(f"  {'ok:  ' if cond else 'FAIL:'} {msg}", flush=True)
        if not cond:
            self.fail.append(msg)


def cmd_verify(args):
    names = [x for x in args.lists.split(",") if x]
    snap = json.load(open(SNAP, encoding="utf-8"))
    if snap["names"] != names:
        print(f"STOP: the snapshot is for {snap['names']}, not {names}")
        return 1
    rep = Report()
    rows = snap["rows"]
    ids = set(rows)
    bdir = snap["bdir"]
    nrow = len(rows)
    t0 = time.time()

    print(f"\n[registry] {nrow} rows of {names}")
    for f in ("registry_raw.csv", "ingest_manifest.csv"):
        before = read_bytes(os.path.join(bdir, "registries", f)).splitlines(keepends=True)
        after = read_bytes(os.path.join(NAS, "registries", f)).splitlines(keepends=True)
        gone = [ln for ln in before if ln.split(b",", 1)[0].decode("utf-8", "replace").lstrip("﻿") in ids]
        want = [ln for ln in before if ln not in gone]
        rep.check(len(gone) == nrow, f"{f}: the snapshot holds {len(gone)} row(s) of the list (expected {nrow})")
        rep.check(after == want, f"{f}: now the snapshot minus exactly those {len(gone)} rows, byte for byte "
                                 f"({len(before)} -> {len(after)} lines)")
    rep.check(not (ids & {r["acq_id"] for r in R.rcsv(os.path.join(NAS, "registries", "registry_raw.csv"))}),
              "no ACQ-ID of the list is live in registry_raw")
    for f in ("registry_subjects.csv", "registry_projects.csv"):
        rep.check(hashlib.sha256(read_bytes(os.path.join(NAS, "registries", f))).hexdigest() == snap["sha"][f],
                  f"{f}: byte-identical (subjects are never touched)")
    tb0 = read_bytes(os.path.join(bdir, "registries", "retired_acquisitions.csv"))
    tb1 = read_bytes(os.path.join(NAS, "registries", "retired_acquisitions.csv"))
    rep.check(tb1.startswith(tb0), "retired_acquisitions.csv: the old tombstones are untouched, new ones appended")
    tomb = {r["acq_id"]: r for r in R.rcsv(os.path.join(NAS, "registries", "retired_acquisitions.csv"))}

    print(f"\n[tombstone, raw folder] one per row")
    bad = 0
    for acq, s in sorted(rows.items()):
        t = tomb.get(acq)
        want_moved = "/projects/" + s["project"] + "/" + s["subfolder"].replace("\\", "/") + "/" + s["dest_name"]
        if not t or t["disposition"] != "derivative" or t["superseded_by"] != s["target"] or t["moved_to"].strip() != want_moved:
            bad += 1
            print(f"     {acq}: tombstone {None if not t else (t['disposition'], t['superseded_by'], t['moved_to'])} != "
                  f"(derivative, {s['target']}, {want_moved})")
    rep.check(bad == 0, f"{nrow - bad}/{nrow} tombstones: derivative of the right original, moved_to = the planned destination")
    left = [acq for acq, s in rows.items()
            if os.path.exists(lp(os.path.join(NAS, s["retiree_row"]["canonical_path"].strip("/").replace("/", "\\"))))]
    rep.check(not left, f"the /raw/ folder of every retiree is gone ({nrow - len(left)}/{nrow})" + (f"; STILL THERE: {left[:3]}" if left else ""))

    print(f"\n[file] destination exists, staged size, SHA-256 = the staged drive copy's")
    mem = {m["acq_id"]: m for m in R.rcsv(os.path.join(OUT, "members.csv"))}
    jobs = []
    missing = wrong = 0
    for acq, s in sorted(rows.items()):
        p = os.path.join(NAS, "projects", s["project"], s["subfolder"], s["dest_name"])
        if not os.path.exists(lp(p)):
            missing += 1
            print(f"     MISSING {p}")
            continue
        if os.path.getsize(lp(p)) != int(mem[acq]["size"]):
            wrong += 1
            print(f"     SIZE {acq}: {os.path.getsize(lp(p))} != {mem[acq]['size']}")
            continue
        jobs.append((acq, p))
    rep.check(missing == 0 and wrong == 0, f"{len(jobs)}/{nrow} destination files exist with the staged size")
    bad_sha = []
    done_gb = 0.0
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(sha256_file, p): (acq, p) for acq, p in jobs}
        for i, fu in enumerate(cf.as_completed(futs), 1):
            acq, p = futs[fu]
            if fu.result() != mem[acq]["sha256"]:
                bad_sha.append(acq)
            done_gb += int(mem[acq]["size"]) / 1e9
            if i % 10 == 0 or i == len(futs):
                print(f"     hashed {i}/{len(futs)} ({done_gb:.1f} GB, {time.time() - t0:.0f} s)", flush=True)
    rep.check(not bad_sha and len(jobs) == nrow, f"SHA-256 of {len(jobs) - len(bad_sha)}/{nrow} destination files equals the staged drive copy's"
              + (f"; DIFFERENT: {bad_sha[:3]}" if bad_sha else ""))

    print(f"\n[originals] untouched")
    reg_now = {r["acq_id"]: r for r in R.rcsv(os.path.join(NAS, "registries", "registry_raw.csv"))}
    odiff, fdiff = [], []
    seen = set()
    for acq, s in rows.items():
        t = s["original_row"]
        if t["acq_id"] in seen:
            continue
        seen.add(t["acq_id"])
        if reg_now.get(t["acq_id"]) != t:
            odiff.append(t["acq_id"])
        folder = os.path.join(NAS, t["canonical_path"].strip("/").replace("/", "\\"))
        now = tree_walk(folder) if os.path.isdir(lp(folder)) else None
        if now is None or {k: list(v) for k, v in now.items()} != {k: list(v) for k, v in s["orig_files"].items()}:
            fdiff.append(t["acq_id"])
    rep.check(not odiff, f"{len(seen)} originals: the registry row of each is identical" + (f"; CHANGED: {odiff[:3]}" if odiff else ""))
    rep.check(not fdiff, f"{len(seen)} originals: the /raw/ folder of each is as it was (names, sizes, mtimes)" + (f"; CHANGED: {fdiff[:3]}" if fdiff else ""))

    print(f"\n[links] raw_linked")
    expected = set(map(tuple, snap["links"]))
    for p in PROJECTS:
        rl = os.path.join(project_dir(p), "raw_linked")
        now = {n: list(v) for n, v in tree_walk(rl).items()} if os.path.isdir(lp(rl)) else {}
        before = snap["raw_linked"][p]
        gone = {n for n in before if n not in now}
        added = {n for n in now if n not in before}
        changed = {n for n in now if n in before and now[n] != before[n]}
        want = {n for (pp, n) in expected if pp == p}
        rep.check(gone == want and not added and not changed,
                  f"{p}: {len(gone)} links gone (expected {len(want)}), {len(added)} added, {len(changed)} changed"
                  + (f"; unexpected gone: {sorted(gone - want)[:2]}, not gone: {sorted(want - gone)[:2]}" if gone != want else ""))

    print(f"\n[provenance] events")
    for p in PROJECTS:
        pv = os.path.join(project_dir(p), "provenance.csv")
        b, a = snap["provenance_lines"][p], (line_count(pv) if os.path.exists(lp(pv)) else None)
        want = snap["events"].get(p, 0)
        rep.check(b is not None and a is not None and a - b == want, f"{p}: provenance.csv {b} -> {a} lines (the dry run announced +{want})")

    print(f"\n[index] _INDEX.csv / _PATHMAP.csv")
    irows = [r for r in R.rcsv(R.INDEX_ROWS_FILE)]
    mine = {}
    for r in irows:
        m = re.search(r"formerly (ACQ-\d{8}-[A-Z0-9]+-\d{3})$", r["note"])
        if m and m.group(1) in ids:
            mine[(r["project"], r["new_path"].lower())] = r
    for p in PROJECTS:
        before = R.rcsv(os.path.join(bdir, "trees", p, "_INDEX.csv"))
        now = R.rcsv(os.path.join(project_dir(p), BASE, "_INDEX.csv"))
        keyset = {k[1] for k in mine if k[0] == p}
        added = [r for r in now if r["new_path"].lower() in keyset]
        others = [r for r in now if r["new_path"].lower() not in keyset]
        rep.check(len(added) == len(keyset) and others == before,
                  f"{p}: {len(added)} of the list's {len(keyset)} rows are in _INDEX.csv, every other row unchanged and in order "
                  f"({len(before)} -> {len(now)})")
        pb = R.rcsv(os.path.join(bdir, "trees", p, "_PATHMAP.csv"))
        pn = R.rcsv(os.path.join(project_dir(p), BASE, "_PATHMAP.csv"))
        rep.check(all(r in pn for r in pb), f"{p}: _PATHMAP.csv keeps all {len(pb)} rows ({len(pn) - len(pb)} added)")
    print(f"\n{rep.n} checks, {len(rep.fail)} failed ({time.time() - t0:.0f} s)")
    for f in rep.fail:
        print("   FAILED:", f)
    return 1 if rep.fail else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=("snapshot", "verify"))
    ap.add_argument("--lists", required=True, help="scalebars,resaves,exports,roi_crops (one run's lists)")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    return {"snapshot": cmd_snapshot, "verify": cmd_verify}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
