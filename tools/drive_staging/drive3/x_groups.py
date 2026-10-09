#!/usr/bin/env python3
"""x_groups.py -- the same-acquisition facts of the XMIC profile (drive3x_2026-10: Biodonostia's Axioscan 7 on
M. Jesus's drive), for .czi stored COMPRESSED, BEFORE ingest.

Why not c_groups.py (stream C): its tests (r4_groups.py) compare stored tile payloads AS PIXELS, so it refuses a
member stored compressed; Biodonostia's Axioscan writes JPEG XR. What can still be proved without decoding:
two files whose level-0 subblocks sit at the same relative positions with the same STORED payload bytes hold
the same pixels (one codec, the same bytes). A ZEN re-save that keeps the tiles (a new name, new metadata, a
pyramid rebuilt, even a moved coordinate origin) passes; anything else is not called identical. That is the only
relation these groups need: each group is a scan and its copies (measured: same second, same mosaic, same size
within 10 KB, or the same tiles at positions shifted by one offset).

    python tools/drive_staging/drive3/x_groups.py facts      # <plan>\\xgroups\\facts.csv (+ one tile list per file)
    python tools/drive_staging/drive3/x_groups.py prefix     # only the interrupted-copy relation, over facts.csv
    python tools/drive_staging/drive3/x_groups.py classify   # -> <plan>\\pixel_decisions.csv
    python tools/drive_staging/drive3/x_groups.py all        # facts (with prefix), then classify

Input: <plan>\\pixel_candidates.csv (ingest_plan.py --profile drive3x_2026-10 plan, pass 1). Members are files of
the local mirror (planned) or production primaries on J: (READ-ONLY). Output: pixel_decisions.csv in
ingest_plan.DECISION_COLS, which ingest_plan.same_acquisition_actions reads exactly as it reads c_groups.py's.

THE CLASSIFICATION (per group; a member's tile set = {(scene, M, start, shape): payload sha256} of level 0,
compared up to ONE translation of every start, so a re-save that moved the origin compares equal):
  * complete    every level-0 subblock reads whole and ends inside the file;
  * identical   two complete members with equal (translated) tile sets;
  * root        within a set of identical members, the EARLIEST ZEN CreationDate (the scanner's own save: a
                re-save gets a new one, user and all); on a tie, stream C's canonical rule: a claimed project
                (the plan's), a copy outside `biomaGUNE MJ`, the shorter path, the path: class `original`; the
                others `identical re-save` (or `scale-bar copy` when they carry a ScaleBar layer the root
                lacks), parent = the root;
  * truncated   a member with an unreadable or out-of-file tile whose readable payloads are all a complete
                member's: `export: subset`, complete N, parent = that member's root. A member czifile cannot
                open at all (an interrupted copy: the directory ZEN writes at the end is gone) is walked
                segment by segment instead: when every whole subblock segment it holds is byte-identical to one
                of a complete member's, it is that file cut short (`prefix`). ingest_plan drops a truncated
                copy that has the name of its root or of a complete identical copy (rule 1b);
  * distinct    a member that shares no stored payload with any other: `distinct` (another slide or scene);
  * ambiguous   anything else (payloads partly shared): `ambiguous` -- kept and flagged by ingest_plan.
Writes only under <plan>. Never writes to J:.
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

PROFILE = "drive3x_2026-10"
FACT_COLS = ["group", "member", "role", "sha256", "acq_id", "name", "path", "original_name", "size",
             "creation_date", "user", "has_scalebar", "n_level0", "n_read", "n_missing", "missing_note",
             "dir_inside", "compression", "tiles_sha", "prefix_of", "error"]


def xdir():
    return os.path.join(P.OUT, "xgroups")


def tiles_path(member):
    return os.path.join(xdir(), "tiles", hashlib.sha1(member.encode("utf-8")).hexdigest()[:16] + ".json")


def tile_key(e):
    return f"{int(e.scene_index)}|{int(e.mosaic_index)}|{','.join(str(int(v)) for v in e.start)}|" \
           f"{','.join(str(int(v)) for v in e.shape)}"


def read_tiles(path):
    """{tile key: sha256 of its STORED payload} over the level-0 subblocks, and the ones that cannot be read
    whole (a truncated file). Reads the payloads; decodes nothing."""
    import czifile
    lp = R.longpath(path)
    size = os.path.getsize(lp)
    tiles, missing, comp = {}, [], collections.Counter()
    with czifile.CziFile(lp) as czi:
        for e in sorted(czi.filtered_subblock_directory, key=lambda e: e.file_position):
            comp[str(e.compression).split(" ")[0].split(".")[-1]] += 1
            k = tile_key(e)
            try:
                seg = e.read_segment_data(czi)
                if seg.data_offset + seg.data_size > size:
                    raise ValueError("payload ends past the end of the file")
                raw = seg.data(raw=True)
                if len(raw) != seg.data_size:
                    raise ValueError(f"payload {len(raw)} B, directory says {seg.data_size}")
            except Exception as ex:          # a tile that cannot be read whole is a missing tile, recorded
                missing.append({"key": k, "why": f"{type(ex).__name__}: {ex}"[:200]})
                continue
            if k in tiles:
                raise ValueError(f"two level-0 subblocks at one position {k} in {path}")
            tiles[k] = hashlib.sha256(raw).hexdigest()
        last = max(czi.subblock_directory, key=lambda e: e.file_position)
        seg = last.read_segment_data(czi)
        inside = seg.data_offset + seg.data_size <= size
    return tiles, missing, inside, comp


def facts_one(r):
    f = {k: r.get(k, "") for k in ("group", "member", "role", "sha256", "acq_id", "name", "path", "original_name",
                                   "size")}
    try:
        feat = R.czi_features(r["path"])
        if feat.get("error"):
            raise ValueError(feat["error"])
        f.update(creation_date=feat.get("CreationDate", ""), user=feat.get("UserName", ""),
                 has_scalebar=str(feat.get("has_scalebar") is True), n_level0=feat.get("n_level0", ""))
        tiles, missing, inside, comp = read_tiles(r["path"])
        os.makedirs(os.path.dirname(tiles_path(r["member"])), exist_ok=True)
        with io.open(tiles_path(r["member"]), "w", encoding="utf-8") as fh:
            json.dump({"member": r["member"], "tiles": tiles, "missing": missing}, fh)
        f.update(n_read=len(tiles), n_missing=len(missing), missing_note=missing[0]["why"] if missing else "",
                 dir_inside="Y" if inside else "N", compression=";".join(sorted(comp)),
                 tiles_sha=hashlib.sha256(json.dumps(sorted(tiles.items())).encode()).hexdigest()[:16])
    except Exception as ex:   # counted and reported by the caller
        f["error"] = f"{type(ex).__name__}: {ex}"[:300]
    return f


def subblock_segments(path):
    """Walk a .czi's segments from the start WITHOUT its directory (which an interrupted copy has lost: ZEN writes
    it at the end): {sha256 of each whole ZISRAWSUBBLOCK segment's used bytes -- its directory entry (position),
    metadata and stored payload}, how many there are, and whether the file stops inside a segment."""
    import struct
    lp = R.longpath(path)
    size = os.path.getsize(lp)
    hashes, n, cut = set(), 0, False
    with open(lp, "rb") as f:
        pos = 0
        while pos + 32 <= size:
            f.seek(pos)
            head = f.read(32)
            sid = head[:16].rstrip(b"\0")
            alloc, used = struct.unpack("<qq", head[16:32])
            if alloc <= 0 or used < 0 or used > alloc:
                raise ValueError(f"bad segment header at {pos} in {path}")
            if pos + 32 + used > size:
                cut = True
                break
            if sid == b"ZISRAWSUBBLOCK":
                h = hashlib.sha256()
                left = used
                while left:
                    b = f.read(min(left, 16 * 1024 * 1024))
                    h.update(b)
                    left -= len(b)
                hashes.add(h.hexdigest())
                n += 1
            pos += 32 + alloc
    return hashes, n, cut or pos < size


def prefix_relations(facts):
    """A planned member czifile cannot open at all (its subblock directory, written at the end, is gone: an
    interrupted copy) is related by its SUBBLOCKS: walked from the start, every whole subblock segment it holds
    (position, metadata, stored payload) is byte-identical to one of a complete member of its group -> it is that
    file's acquisition cut short. In place: sets prefix_of, clears the error, records it as unreadable."""
    by_group = collections.defaultdict(list)
    for f in facts:
        by_group[f["group"]].append(f)
    for f in facts:
        if not f.get("error") or f["role"] != "plan" or not f["sha256"]:
            continue
        mine, n_mine, cut = subblock_segments(f["path"])
        if not n_mine:
            continue
        for o in by_group[f["group"]]:
            if o is f or o.get("error") or o.get("dir_inside") != "Y":
                continue
            theirs, n_theirs, _ = subblock_segments(o["path"])
            if mine <= theirs:
                err = f["error"]
                f.update(prefix_of=o["member"], error="", dir_inside="N", n_read=n_mine, n_missing=n_theirs - n_mine,
                         missing_note=f"interrupted copy: {n_mine} of {n_theirs} subblocks, each byte-identical to "
                                      f"{o['name']}'s; the file stops inside a segment: {cut}; no subblock directory "
                                      f"(czifile: {err[:60]})")
                os.makedirs(os.path.dirname(tiles_path(f["member"])), exist_ok=True)
                with io.open(tiles_path(f["member"]), "w", encoding="utf-8") as fh:
                    json.dump({"member": f["member"], "tiles": {}, "missing": [{"key": "*", "why": f["missing_note"]}]}, fh)
                break


def cmd_facts(args):
    rows = list(P.rcsv(os.path.join(P.OUT, "pixel_candidates.csv")))
    problems = []
    for r in rows:
        if r["role"] == "plan":
            if not os.path.isfile(R.longpath(r["path"])):
                problems.append(f"not in the local mirror (run ingest_plan.py localize --subset pixel): {r['path']}")
            elif os.path.getsize(R.longpath(r["path"])) != int(r["size"]):
                problems.append(f"local mirror size differs from the plan: {r['path']}")
        elif not os.path.normcase(r["path"]).startswith(os.path.normcase(P.NAS)):
            problems.append(f"a production member outside the NAS root: {r['path']}")
    if problems:
        for p in problems[:20]:
            print("  PROBLEM:", p)
        return 1
    t0 = time.time()
    with cf.ThreadPoolExecutor(args.workers) as ex:
        facts = list(ex.map(facts_one, rows))
    prefix_relations(facts)
    os.makedirs(xdir(), exist_ok=True)
    R.wcsv(os.path.join(xdir(), "facts.csv"), FACT_COLS, facts)
    errs = [f for f in facts if f.get("error")]
    print(f"facts.csv: {len(facts)} members of {len({r['group'] for r in rows})} groups in {time.time() - t0:.0f}s; "
          f"{len(errs)} errors; {sum(1 for f in facts if f.get('n_missing') not in ('', 0, '0'))} with missing tiles; "
          f"compression {dict(collections.Counter(f.get('compression', '') for f in facts))}")
    for f in errs[:20]:
        print("  ERROR:", f["path"], f["error"])
    return 1 if errs else 0


def normalized(tiles):
    """A member's tile set up to one translation: each key's start shifted by the member's smallest start per
    dimension, so that a re-save that moved the coordinate origin (`ID1_0424_H+L.czi`: every tile at the same
    offset from `2025_02_14__5234.czi`'s, payloads byte-identical) compares equal. Returns (map, origin)."""
    parsed = []
    for k, v in tiles.items():
        s, m, start, shape = k.split("|")
        parsed.append((s, m, [int(x) for x in start.split(",")], shape, v))
    if not parsed:
        return {}, ()
    origin = tuple(min(p[2][i] for p in parsed) for i in range(len(parsed[0][2])))
    return ({f"{s}|{m}|{','.join(str(x - o) for x, o in zip(start, origin))}|{shape}": v
             for s, m, start, shape, v in parsed}, origin)


def classify_members(ms, deprioritised=("biomaGUNE MJ",)):
    """Classify the members of ONE group from their facts (pure: tested). ms: dicts with member, name,
    original_name, creation (aware datetime or None), scalebar (bool), tiles {key: sha}, missing (int),
    inside (bool), optional project (the plan's claim) and prefix_of. Returns {member: (class, parent, evidence,
    complete)}. Tile sets are compared up to one translation (normalized); overlap is counted on payloads."""
    complete = {m["member"]: (m["missing"] == 0 and m["inside"]) for m in ms}
    by_id = {m["member"]: m for m in ms}
    norm = {m["member"]: normalized(m["tiles"]) for m in ms}
    payloads = {m["member"]: set(m["tiles"].values()) for m in ms}

    def order(m):
        """The root of an identical set: the earliest ZEN save (a re-save gets a new CreationDate); on a tie, stream
        C's canonical rule (a claimed project, a copy outside `biomaGUNE MJ`, the shorter path, the path)."""
        c = m["creation"]
        top = m["original_name"].split("/")[1] if "/" in m["original_name"] else ""
        return (c is None, c.timestamp() if c else 0, 0 if m.get("project") else 1, top in deprioritised,
                len(m["original_name"]), m["original_name"])

    # identical sets among the complete members
    sets = collections.defaultdict(list)
    for m in ms:
        if complete[m["member"]]:
            sets[json.dumps(sorted(norm[m["member"]][0].items()))].append(m)
    out, root_of = {}, {}
    for members in sets.values():
        members.sort(key=order)
        root = members[0]
        root_of.update({m["member"]: root["member"] for m in members})
        n = len(root["tiles"])
        if len(members) > 1:
            tie = members[1]["creation"] == root["creation"]
            out[root["member"]] = (R.C_ORIGINAL, "", f"{len(members) - 1} pixel-identical cop"
                                   f"{'y' if len(members) == 2 else 'ies'} ({n} of {n} level-0 tiles, stored "
                                   "payloads byte-identical); " + ("saved by ZEN at the same moment as its copy: "
                                                                   "chosen by the canonical rule (its claim)" if tie
                                                                   else "the earliest ZEN save"), "Y")
        for m in members[1:]:
            cls = R.C_SCALEBAR if m["scalebar"] and not root["scalebar"] else R.C_RESAVE
            shift = tuple(a - b for a, b in zip(norm[m["member"]][1], norm[root["member"]][1]))
            moved = "" if not any(shift) else f", every tile shifted by one offset {shift} (the origin moved)"
            out[m["member"]] = (cls, root["member"], f"{n} of {n} level-0 tiles byte-identical to {root['name']} "
                                f"(stored payloads{moved}); ZEN save {m['creation'] and m['creation'].isoformat()}, "
                                f"{root['name']} {root['creation'] and root['creation'].isoformat()}", "Y")
    for m in ms:
        mid = m["member"]
        if mid in out:
            continue
        if m.get("prefix_of") in root_of:          # an interrupted copy, related by its subblock segments
            o = by_id[m["prefix_of"]]
            out[mid] = (R.C_SUBSET, root_of[o["member"]],
                        m.get("missing_note") or f"interrupted copy: every subblock it holds is one of {o['name']}'s",
                        "N")
            continue
        shared = {o["member"]: len(payloads[mid] & payloads[o["member"]]) for o in ms if o is not m}
        if not complete[mid]:
            cover = [o for o in ms if complete[o["member"]] and m["tiles"]
                     and payloads[mid] <= payloads[o["member"]]]
            if cover:
                same = [o for o in cover if R.basename(o["original_name"]).lower() == R.basename(m["original_name"]).lower()]
                o = (same or cover)[0]
                out[mid] = (R.C_SUBSET, root_of[o["member"]],
                            f"truncated: {m['missing']} level-0 tile(s) unreadable; its {len(m['tiles'])} readable "
                            f"tiles are byte-identical to {o['name']}'s", "N")
                continue
        if not any(shared.values()):
            out[mid] = (R.C_DISTINCT, "", "no level-0 tile in common with any other member", "Y" if complete[mid] else "N")
        else:
            best = max(shared, key=lambda k: shared[k])
            out[mid] = (R.C_AMBIGUOUS, "", f"shares {shared[best]} of its {len(m['tiles'])} level-0 tiles with "
                        f"{by_id[best]['name']}, not all: cannot tell which is the acquisition",
                        "Y" if complete[mid] else "N")
    # a set of one complete member that is nobody's parent and was not otherwise classified: an original
    for m in ms:
        out.setdefault(m["member"], (R.C_ORIGINAL, "", "", "Y" if complete[m["member"]] else "N"))
    # an ambiguous member makes its group's roots ambiguous too (ingest_plan keeps them all, flagged)
    if any(v[0] == R.C_AMBIGUOUS for v in out.values()):
        for k, v in list(out.items()):
            if v[0] == R.C_ORIGINAL:
                out[k] = (R.C_AMBIGUOUS, "", "in a group with partly shared tiles: " + (v[2] or "the original?"), v[3])
    return out


def cmd_classify(args):
    facts = list(P.rcsv(os.path.join(xdir(), "facts.csv")))
    if any(f["error"] for f in facts):
        print("STOP: facts.csv has errors; re-run facts")
        return 1
    groups = collections.defaultdict(list)
    project_of = {r["member"]: r["project"] for r in P.rcsv(os.path.join(P.OUT, "pixel_candidates.csv"))}
    for f in facts:
        with io.open(tiles_path(f["member"]), encoding="utf-8") as fh:
            t = json.load(fh)
        groups[f["group"]].append({"member": f["member"], "role": f["role"], "sha256": f["sha256"],
                                   "acq_id": f["acq_id"], "name": f["name"], "original_name": f["original_name"],
                                   "size": f["size"], "prefix_of": f.get("prefix_of", ""),
                                   "project": project_of.get(f["member"], ""),
                                   "creation": R.parse_dt(f["creation_date"]),
                                   "creation_date": f["creation_date"], "scalebar": f["has_scalebar"] == "True",
                                   "tiles": t["tiles"], "missing": len(t["missing"]),
                                   "missing_note": f["missing_note"], "inside": f["dir_inside"] == "Y"})
    rows = []
    for g, ms in sorted(groups.items()):
        sig = P.group_signature([m["member"] for m in ms])
        cl = classify_members(ms, P.DEPRIORITISED_TOPS)
        by = {m["member"]: m for m in ms}
        for m in ms:
            cls, parent, ev, comp = cl[m["member"]]
            rows.append({"group": g, "member": m["member"], "role": m["role"],
                         "sha256": m["sha256"] if m["role"] == "plan" else "",
                         "acq_id": m["acq_id"] if m["role"] == "production" else "", "name": m["name"],
                         "size": m["size"], "class": cls, "parent": parent,
                         "parent_name": by[parent]["name"] if parent else "", "via": "stored-payload identity",
                         "evidence": ev, "complete": comp,
                         "complete_note": (f"{m['missing']} level-0 tile(s) unreadable: {m['missing_note']}"
                                           if m["missing"] else "") + ("" if m["inside"] else
                                                                       "; a subblock ends past the end of the file"),
                         "has_scalebar": str(m["scalebar"]), "creation_date": m["creation_date"],
                         "group_signature": sig})
    R.wcsv(os.path.join(P.OUT, "pixel_decisions.csv"), P.DECISION_COLS, rows)
    print(f"pixel_decisions.csv: {len(rows)} members in {len(groups)} groups")
    print("classes:", dict(collections.Counter(r["class"] for r in rows)))
    print("incomplete:", sum(1 for r in rows if r["complete"] != "Y"))
    return 0


def cmd_prefix(args):
    """Re-run only the byte-prefix relation over an existing facts.csv (the members' tile lists are kept)."""
    path = os.path.join(xdir(), "facts.csv")
    facts = list(P.rcsv(path))
    before = sum(1 for f in facts if f["error"])
    prefix_relations(facts)
    R.wcsv(path, FACT_COLS, facts)
    errs = [f for f in facts if f["error"]]
    print(f"facts.csv: {before} unreadable member(s); {before - len(errs)} related by their subblocks; {len(errs)} errors left")
    for f in facts:
        if f.get("prefix_of"):
            print(f"  {f['path']}: every subblock it holds is one of member {f['prefix_of'][:16]}'s")
    for f in errs:
        print("  ERROR:", f["path"], f["error"])
    return 1 if errs else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--profile", default=PROFILE, choices=[PROFILE])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("facts", "all"):
        s = sub.add_parser(name)
        s.add_argument("--workers", type=int, default=3)
    sub.add_parser("prefix")
    sub.add_parser("classify")
    args = ap.parse_args()
    P.use_profile(args.profile)
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    if args.cmd == "all":
        return cmd_facts(args) or cmd_classify(args)
    return {"facts": cmd_facts, "prefix": cmd_prefix, "classify": cmd_classify}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
