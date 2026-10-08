#!/usr/bin/env python3
"""c_groups.py -- stream C (drive 3): the pixel check of every same-acquisition group, BEFORE ingest.

A group is every planned .czi that shares one instrument and acquisition SECOND, plus the production
acquisitions of that second (ingest_plan.py --profile drive3_2026-10 plan writes them to
<plan>\\pixel_candidates.csv). ZEN gives a derived file -- a scale-bar copy, a renamed re-save, a crop
("ROI"), a scene split, a stitched copy -- its parent's acquisition time, and a re-saved file keeps its
name and time with new bytes, so these files are told apart by their pixels, never by name or size.

The tests are the drives' (tools/drive_staging/r4_groups.py, unit-tested in tools/test_drives_r4_groups.py,
reviewed in tasks/drives_r4_cleanup_review.md), called UNCHANGED: identical tiles, cut tiles, region,
re-placed tiles, trimmed pieces, stitched interiors, rendering; then classify_group and the rendering
pass. What this wrapper adds:
  * the members are files of the local mirror (planned) or production primaries on J: (READ-ONLY);
  * a TOLERANT tile cache: a tile whose payload is short (a truncated file: the drives 1+2
    ACQ-20251031-CELL-003 lesson) is recorded as missing instead of stopping the run, so a truncated twin
    is related to its complete one by its remaining tiles and reported `complete=N`;
  * every file's subblock directory is checked against its size (the last subblock must end inside it);
  * a member stored COMPRESSED is refused (the tests compare stored payloads as pixels).

    python tools/drive_staging/drive3/c_groups.py members     # pixel_candidates.csv -> groups\\members.csv
    python tools/drive_staging/drive3/c_groups.py features    # XML + subblock directory per member
    python tools/drive_staging/drive3/c_groups.py pieces      # the tolerant tile cache (reads each file once)
    python tools/drive_staging/drive3/c_groups.py relations   # the pixel tests, per group
    python tools/drive_staging/drive3/c_groups.py classify    # -> <plan>\\pixel_decisions.csv
    python tools/drive_staging/drive3/c_groups.py all

Writes only under <plan>\\groups\\ and <plan>\\pixel_decisions.csv. Reads J: (production primaries) and
the local mirror; never writes to either. ingest_plan.py then applies Ryan's rule to the facts written
here (ingest_plan.same_acquisition_actions).
"""
import argparse
import collections
import concurrent.futures as cf
import hashlib
import io
import json
import os
import sys
import time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.dirname(HERE)
sys.path.insert(0, DS)
import ingest_plan as P  # noqa: E402
import r4_groups as R  # noqa: E402

P.use_profile("drive3_2026-10")
GROUPS = os.path.join(P.OUT, "groups")
MEMBER_COLS = ["group", "group_n", "acq_id", "role", "name", "folder", "size", "sha256", "cache_key",
               "staged_path", "project_name", "instrument", "acquisition_datetime", "original_name"]


def cache_key(row):
    """Tile caches are keyed by content: the planned file's sha256, a production file's checksum."""
    return row["sha256"] or ("acq_" + row["acq_id"])


# ---------------------------------------------------------------------------------------------
# members
# ---------------------------------------------------------------------------------------------

def cmd_members(args):
    rows = list(P.rcsv(os.path.join(P.OUT, "pixel_candidates.csv")))
    by = collections.defaultdict(list)
    for r in rows:
        by[r["group"]].append(r)
    out, problems = [], []
    for g, rs in sorted(by.items()):
        for r in rs:
            path = r["path"]
            if r["role"] == "plan":
                if not os.path.isfile(R.longpath(path)):
                    problems.append(f"not in the local mirror (run ingest_plan.py localize): {path}")
                elif os.path.getsize(R.longpath(path)) != int(r["size"]):
                    problems.append(f"local mirror size differs from the plan: {path}")
            elif not os.path.normcase(path).startswith(os.path.normcase(P.NAS)):
                problems.append(f"a production member outside the NAS root: {path}")
            out.append({"group": g, "group_n": len(rs), "acq_id": r["member"], "role": r["role"],
                        "name": r["name"], "folder": R.dirname(r["original_name"]), "size": r["size"],
                        "sha256": r["sha256"], "cache_key": cache_key(r), "staged_path": path,
                        "project_name": r["project"], "instrument": g.split("|")[0],
                        "acquisition_datetime": g.split("|", 1)[1], "original_name": r["original_name"]})
    os.makedirs(GROUPS, exist_ok=True)
    R.wcsv(os.path.join(GROUPS, "members.csv"), MEMBER_COLS, out)
    print(f"members.csv: {len(out)} members in {len(by)} groups, {len(problems)} problems")
    for p in problems[:20]:
        print("  PROBLEM:", p)
    return 1 if problems else 0


def load_members():
    mem = R.rcsv(os.path.join(GROUPS, "members.csv"))
    for m in mem:
        m["sha256"] = m["cache_key"]          # r4_groups keys its tile cache by m["sha256"]
    return mem


# ---------------------------------------------------------------------------------------------
# features (XML + directory) and the directory check
# ---------------------------------------------------------------------------------------------

FEATURE_COLS = R.FEATURE_COLS + ["dir_entries", "last_end", "file_size", "dir_inside"]


def features_of(m):
    f = dict(R.czi_features(m["staged_path"]), sha256=m["cache_key"])
    try:
        import czifile
        with czifile.CziFile(R.longpath(m["staged_path"])) as czi:
            alld = czi.subblock_directory
            last = max(alld, key=lambda e: e.file_position)
            seg = last.read_segment_data(czi)
            f["dir_entries"] = len(alld)
            f["last_end"] = seg.data_offset + seg.data_size
            if f.get("error", "").startswith("StopIteration") and not czi.scenes:
                # r4_groups.czi_features stops at the first scene, and this file has none (its only level-0
                # subblock is downsampled: a preview). Its XML fields are already read; take the layout from
                # the directory and say so -- it is a finding, not an error.
                fd = czi.filtered_subblock_directory
                f["dims"] = ",".join(fd[0].dims) if fd else ""
                f["dtype"] = str(fd[0].dtype) if fd else ""
                f["compression"] = ";".join(sorted({str(e.compression).split(" ")[0].split(".")[-1] for e in fd}))
                f["error"] = ""
                f["scene_shapes"] = "(no scene)"
        f["file_size"] = os.path.getsize(R.longpath(m["staged_path"]))
        f["dir_inside"] = "Y" if int(f["last_end"]) <= int(f["file_size"]) else "N"
    except Exception as ex:   # counted and reported by the caller
        f["error"] = (f.get("error") or "") + f" | directory: {type(ex).__name__}: {ex}"
    return f


def cmd_features(args):
    mem = load_members()
    t0 = time.time()
    with cf.ThreadPoolExecutor(args.workers) as ex:
        feats = list(ex.map(features_of, mem))
    R.wcsv(os.path.join(GROUPS, "features.csv"), FEATURE_COLS, feats)
    errs = [f for f in feats if f.get("error")]
    comp = collections.Counter(f.get("compression", "") for f in feats)
    outside = [f for f in feats if f.get("dir_inside") == "N"]
    print(f"features.csv: {len(feats)} files in {time.time() - t0:.0f}s, {len(errs)} errors; compression {dict(comp)}; "
          f"{len(outside)} with a subblock past the end of the file")
    for f in errs[:20]:
        print("  ERROR:", f["path"], f["error"])
    return 1 if errs else 0


def load_members_with_features():
    mem = load_members()
    feats = {r["sha256"]: r for r in R.rcsv(os.path.join(GROUPS, "features.csv"))}
    for m in mem:
        m["feat"] = feats[m["cache_key"]]
    return mem


# ---------------------------------------------------------------------------------------------
# the tolerant tile cache
# ---------------------------------------------------------------------------------------------

def czi_pieces_tolerant(path):
    """r4_groups.czi_pieces, except that a tile whose payload reads short (a truncated file), or whose
    stored size is not its extent (a DOWNSAMPLED subblock standing in for level-0 data: a preview), is
    recorded in `missing` and left out, instead of stopping the run or being compared as if it were
    pixels. `complete` is True when no level-0 tile is missing."""
    import czifile
    pieces, scenes, missing = [], {}, []
    with czifile.CziFile(R.longpath(path)) as czi:
        for sid, im in czi.scenes.items():
            scenes[int(sid)] = list(im.bbox)
        for e in sorted(czi.filtered_subblock_directory, key=lambda e: e.file_position):
            if e.dims[-3:] != ("Y", "X", "S"):
                raise ValueError(f"unexpected dimension order {e.dims} in {path}")
            d = dict(zip(e.dims, e.start))
            sh = dict(zip(e.dims, e.shape))
            if tuple(int(v) for v in e.stored_shape[-3:-1]) != (int(sh["Y"]), int(sh["X"])):
                missing.append({"pos": int(e.file_position),
                                "why": f"downsampled: stored {e.stored_shape[-2]} x {e.stored_shape[-3]} px for a "
                                       f"{sh['X']} x {sh['Y']} px extent (C={d.get('C', '?')}); no full-resolution data"})
                continue
            expect = int(e.stored_shape[-3]) * int(e.stored_shape[-2]) * int(e.stored_shape[-1]) * e.dtype.itemsize
            try:
                seg = e.read_segment_data(czi)
                raw = seg.data(raw=True)
            except Exception as ex:      # an unreadable tile is a missing tile, recorded
                missing.append({"pos": int(e.file_position), "why": f"{type(ex).__name__}: {ex}"[:200]})
                continue
            if len(raw) != expect:
                missing.append({"pos": int(e.file_position), "why": f"payload {len(raw)} B, expected {expect}"})
                continue
            pieces.append({
                "scene": max(int(e.scene_index), 0), "m": int(e.mosaic_index),
                "key": [[k, int(d[k])] for k in e.dims if k not in ("X", "Y", "S")],
                "x": int(d["X"]), "y": int(d["Y"]), "w": int(sh["X"]), "h": int(sh["Y"]),
                "samples": int(sh["S"]), "dtype": str(e.dtype), "compression": str(e.compression),
                "stored": [int(v) for v in e.stored_shape], "pos": int(seg.data_offset), "nbytes": len(raw),
                "hash": hashlib.sha256(raw).hexdigest()})
    return {"path": path, "size": os.path.getsize(R.longpath(path)), "scenes": scenes, "pieces": pieces,
            "missing": missing, "complete": not missing}


def build_cache(m):
    cp = R.pieces_cache_path(GROUPS, m["cache_key"])
    if os.path.exists(cp):
        return "cached"
    data = czi_pieces_tolerant(m["staged_path"])
    data["sha256"] = m["cache_key"]
    os.makedirs(os.path.dirname(cp), exist_ok=True)
    tmp = cp + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, cp)
    return "built"


def cmd_pieces(args):
    mem = load_members_with_features()
    comp = [m for m in mem if (m["feat"].get("compression") or "").replace("UNCOMPRESSED", "").strip(";")]
    if comp:
        for m in comp[:20]:
            print("  COMPRESSED:", m["staged_path"], m["feat"].get("compression"))
        print(f"STOP: {len(comp)} members are stored compressed; the pixel tests compare stored payloads")
        return 1
    todo = [m for m in mem if not os.path.exists(R.pieces_cache_path(GROUPS, m["cache_key"]))]
    todo.sort(key=lambda m: -int(m["size"]))
    print(f"{len(mem)} members, {len(todo)} to read ({sum(int(m['size']) for m in todo) / 1e9:.1f} GB)", flush=True)
    t0, done, errs = time.time(), 0, []
    with cf.ThreadPoolExecutor(args.workers) as ex:
        futs = {ex.submit(build_cache, m): m for m in todo}
        for fut in cf.as_completed(futs):
            m = futs[fut]
            try:
                fut.result()
            except Exception as e:   # counted, reported, non-zero exit
                errs.append((m["staged_path"], f"{type(e).__name__}: {e}"))
            done += 1
            if done % 25 == 0 or done == len(todo):
                print(f"  {done}/{len(todo)} files, {time.time() - t0:.0f}s, {len(errs)} errors", flush=True)
    for p, e in errs:
        print("  ERROR:", p, e)
    incomplete = []
    for m in mem:
        cp = R.pieces_cache_path(GROUPS, m["cache_key"])
        if os.path.exists(cp):
            with io.open(cp, encoding="utf-8") as f:
                d = json.load(f)
            if not d.get("complete", True) or len(d["pieces"]) + len(d.get("missing", [])) != int(m["feat"]["n_level0"] or -1):
                incomplete.append((m["staged_path"], len(d.get("missing", [])), len(d["pieces"]), m["feat"]["n_level0"]))
    print(f"tile caches: {len(mem) - len(errs)} ready, {len(incomplete)} incomplete (truncated) or inconsistent")
    for x in incomplete[:20]:
        print("  INCOMPLETE:", x)
    return 1 if errs else 0


# ---------------------------------------------------------------------------------------------
# relations and classification
# ---------------------------------------------------------------------------------------------

def cmd_relations(args):
    mem = load_members_with_features()
    groups = R.groups_of(mem)
    rdir = os.path.join(GROUPS, "relations")
    os.makedirs(rdir, exist_ok=True)
    sib = R.sibling_group_keys(mem)
    todo = []
    for k, ms in groups.items():
        f = os.path.join(rdir, hashlib.sha1(k.encode("utf-8")).hexdigest()[:16] + ".json")
        sig = P.group_signature([m["acq_id"] for m in ms])
        if os.path.exists(f) and not args.redo:
            with io.open(f, encoding="utf-8") as fh:
                if json.load(fh).get("signature") == sig:
                    continue
        todo.append((k, f, sig))
    print(f"{len(groups)} groups, {len(todo)} to compare ({len(sib)} sibling groups: distinct stage positions)")
    t0, errs = time.time(), []

    def one(item):
        k, f, sig = item
        ms = groups[k]
        # a member with no comparable level-0 tile (only a downsampled preview, or nothing readable) cannot be
        # related by bytes: it stays out of the tests and is classified on its own (its evidence says why)
        cmp_ = [m for m in ms if R.load_pieces(GROUPS, m["cache_key"], m["staged_path"])["pieces"]]
        rels = R.group_relations(cmp_, GROUPS, exhaustive=args.exhaustive) if len(cmp_) > 1 else []
        tmp = f + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"group": k, "signature": sig, "ids": [m["acq_id"] for m in ms], "rels": rels,
                       "not_compared": [m["acq_id"] for m in ms if m not in cmp_]}, fh)
        os.replace(tmp, f)

    with cf.ThreadPoolExecutor(args.workers) as ex:
        futs = {ex.submit(one, it): it for it in todo}
        for n, fut in enumerate(cf.as_completed(futs), 1):
            try:
                fut.result()
            except Exception as e:   # counted, reported, non-zero exit
                errs.append((futs[fut][0], f"{type(e).__name__}: {e}"))
            if n % 20 == 0 or n == len(todo):
                print(f"  {n}/{len(todo)} groups, {time.time() - t0:.0f}s, {len(errs)} errors", flush=True)
    for k, e in errs:
        print("  ERROR:", k, e)
    return 1 if errs else 0


def load_relations():
    rdir = os.path.join(GROUPS, "relations")
    res = {}
    for f in sorted(os.listdir(rdir)) if os.path.isdir(rdir) else []:
        if f.endswith(".json"):
            with io.open(os.path.join(rdir, f), encoding="utf-8") as fh:
                d = json.load(fh)
            res[d["group"]] = d
    return res


def cmd_classify(args):
    mem = load_members_with_features()
    groups = R.groups_of(mem)
    rels = load_relations()
    sibling = R.sibling_group_keys(mem)
    rows, missing, stops = [], [], []
    for k, ms in groups.items():
        sig = P.group_signature([m["acq_id"] for m in ms])
        d = rels.get(k)
        if d is None or d.get("signature") != sig:
            missing.append(k)
            continue
        caches = {m["acq_id"]: R.load_pieces(GROUPS, m["cache_key"], m["staged_path"]) for m in ms}
        byid = {m["acq_id"]: m for m in ms}
        rr = d["rels"]
        for r in rr:
            # a whole-tile match made only of blank tiles proves nothing (r4_groups.cmd_classify's guard)
            if r["kind"] == "hash" and r["complete"] and not r.get("weak"):
                a = byid[r["a"]]
                if not R.informative(a["staged_path"], caches[r["a"]]["pieces"]):
                    r["complete"], r["weak"] = False, True
        nodes = [{"id": m["acq_id"], "name": m["name"], "project": m["project_name"],
                  "scalebar": m["feat"].get("has_scalebar") == "True",
                  "creation": R.parse_dt(m["feat"].get("CreationDate"))} for m in ms]
        cl = R.classify_group(nodes, rr)
        if k not in sibling:
            R.similarity_pass(ms, cl, GROUPS)
        elif R.shared_payloads(caches):
            stops.append(f"group {k}: members at distinct stage positions share tile payloads (the gate is "
                         "contradicted): re-run `relations --redo --exhaustive`")
        for m in ms:
            c = cl[m["acq_id"]]
            cache = caches[m["acq_id"]]
            parent = byid.get(c["parent"]) if c["parent"] else None
            ev = c["evidence"]
            if c["class"] == R.C_DISTINCT and not ev:
                ev = ("a different stage position from every other member (XML scene centre); no tile payload is "
                      "shared with any other member" if k in sibling else
                      "no tile of it is in another member and no tile of another member is in it")
            miss = cache.get("missing", [])
            if not cache["pieces"]:
                ev = ("not comparable by pixels: no full-resolution tile (" + (miss[0]["why"] if miss else "no tile")
                      + ")" + (f"; {ev}" if ev else ""))
            rows.append({"group": k, "member": m["acq_id"], "role": m["role"],
                         "sha256": m["cache_key"] if m["role"] == "plan" else "",
                         "acq_id": m["acq_id"] if m["role"] == "production" else "", "name": m["name"],
                         "size": m["size"], "class": c["class"], "parent": c["parent"] or "",
                         "parent_name": parent["name"] if parent else "", "via": c["via"], "evidence": ev,
                         "complete": "Y" if (not miss and m["feat"].get("dir_inside") == "Y") else "N",
                         "complete_note": (f"{len(miss)} of {len(miss) + len(cache['pieces'])} level-0 tiles "
                                           f"unreadable: {miss[0]['why']}" if miss else "")
                         + ("" if m["feat"].get("dir_inside") == "Y" else "; a subblock ends past the end of the file"),
                         "has_scalebar": m["feat"].get("has_scalebar", ""),
                         "creation_date": m["feat"].get("CreationDate", ""), "group_signature": sig})
    R.wcsv(os.path.join(P.OUT, "pixel_decisions.csv"), P.DECISION_COLS, rows)
    print(f"pixel_decisions.csv: {len(rows)} members in {len(groups) - len(missing)} groups; "
          f"{len(missing)} groups not compared yet")
    print("classes:", dict(collections.Counter(r["class"] for r in rows)))
    print("incomplete:", sum(1 for r in rows if r["complete"] != "Y"))
    for s in stops:
        print("STOP:", s)
    return 1 if (missing or stops) else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("members")
    for name in ("features", "pieces"):
        s = sub.add_parser(name)
        s.add_argument("--workers", type=int, default=4)
    s = sub.add_parser("relations")
    s.add_argument("--workers", type=int, default=4)
    s.add_argument("--redo", action="store_true")
    s.add_argument("--exhaustive", action="store_true", help="every pair, no gates (validation)")
    sub.add_parser("classify")
    s = sub.add_parser("all")
    s.add_argument("--workers", type=int, default=4)
    s.add_argument("--redo", action="store_true")
    s.add_argument("--exhaustive", action="store_true")
    args = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    if args.cmd == "all":
        for step in (cmd_members, cmd_features, cmd_pieces, cmd_relations, cmd_classify):
            rc = step(args)
            if rc:
                return rc
        return 0
    return {"members": cmd_members, "features": cmd_features, "pieces": cmd_pieces, "relations": cmd_relations,
            "classify": cmd_classify}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
