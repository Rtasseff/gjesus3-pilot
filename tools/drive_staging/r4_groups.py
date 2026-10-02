#!/usr/bin/env python3
"""r4_groups.py -- classify the 247 same-timestamp groups (819 files) the drives .czi ingest kept in
/raw/, with a pixel check on every proposed copy, and write the retire lists.

ONE-TIME TOOL for stream D of the 2026-10 close-out (branch feat/drives-r4-cleanup). Read-only on
the staged drive data on D: and on production; writes only under its --out folder (default
D:\\projects\\gjesus3\\staging\\_analysis\\drives-r4-cleanup) and the retire-list CSVs it is told to.
It never runs a retirement: `tools/retire_acquisition.py --execute` is a separate, approved step.

THE QUESTION. Gate rule R4 (tasks/drives_ingest_dryrun_review.md) kept every member of a same
(instrument, acquisition timestamp to the second) group in /raw/, flagged `drv_acq_group`. ZEN gives a
timestamp to every file it derives from one acquisition -- scene splits, crops ("ROI"), stitched
copies, scale-bar copies, renamed re-saves -- so a group is one acquisition plus whatever was made
from it, OR several unrelated scenes of one acquisition whose master file is not on the drive.
Ryan's principle (2026-10-01): the acquisition goes in /raw/; derivatives go to the project folder;
a file stays in /raw/ flagged only when it is genuinely ambiguous.

THE EVIDENCE. Every file is UNCOMPRESSED (819 of 819), so pixels are compared as stored, not decoded
and re-rendered. Each file is read once into a cache of its level-0 subblocks (tiles): position,
shape and the SHA-256 of the pixel payload. Two exact tests then relate a member A to a candidate
parent B:

  hash match   every A tile is byte-identical to some B tile, all at ONE constant offset
               (identical copy, scale-bar copy -- the overlay is metadata --, scene split, re-save);
  crop match   an A tile is a byte-exact sub-rectangle of a B tile (ZEN cuts the tiles at a crop's
               border), all at ONE constant offset.

A third check covers a stitched copy, which re-tiles and blends and so cannot match tile for tile:
the interior of each tile of the tiled original is searched for, byte for byte, in the stitched
file. Whatever matches none of these is `distinct` (or `ambiguous`, with the evidence listed).

    python tools/drive_staging/r4_groups.py table      # one row per member: ACQ-ID, project, ...
    python tools/drive_staging/r4_groups.py features   # metadata + scale-bar overlay per member
    python tools/drive_staging/r4_groups.py pieces     # the tile cache (reads ~730 GB once)
    python tools/drive_staging/r4_groups.py relations  # pairwise pixel tests per group
    python tools/drive_staging/r4_groups.py classify   # class per member + tables
    python tools/drive_staging/r4_groups.py lists      # tasks/retire_lists/2026-10_r4_*.csv

Pure helpers (path, subfolder, list rows, byte-search) are unit-tested by
tools/test_drives_r4_groups.py.
"""
import argparse
import collections
import concurrent.futures as cf
import csv
import datetime as dt
import hashlib
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
REPO = os.path.dirname(TOOLS)
sys.path.insert(0, HERE)

STAGING = r"D:\projects\gjesus3\staging"
PLAN = os.path.join(STAGING, "_analysis", "ingest", "expected.csv")
OUT = os.path.join(STAGING, "_analysis", "drives-r4-cleanup")
PROVENANCE = os.path.join(REPO, "tasks", "drives_ingest_provenance.csv")
NAS = r"J:\gjesus3-data"
RETIRE_LISTS = os.path.join(REPO, "tasks", "retire_lists")

# plan drive code -> (label that is the first component of original_name, staged folder)
DRIVES = {"D1": "drive1_FRIO-X6", "D2": "drive2_MFB-Disco-2"}
STAGED = {"D1": "drive1_FRIO-X6_2322E4A111E7", "D2": "drive2_MFB-Disco-2_2322E4A112BD"}
EXTRACT = os.path.join(STAGING, "_extract")
WORKING_ROOT = "working\\historical_drives"      # Ryan, 2026-10-02: <project>\working\historical_drives\...

# the one scale-bar-by-name pattern in the BACKLOG measurement; the overlay in the XML is the evidence
SCALE_WORDS = ("scale", "escala")


# ---------------------------------------------------------------------------------------------
# small shared helpers
# ---------------------------------------------------------------------------------------------

def rcsv(path):
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def wcsv(path, cols, rows):
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    os.replace(tmp, path)


def longpath(p):
    p = os.path.abspath(p)
    return p if p.startswith("\\\\?\\") else "\\\\?\\" + p


def basename(original_name):
    return original_name.replace("\\", "/").rsplit("/", 1)[-1]


def dirname(original_name):
    parts = original_name.replace("\\", "/").rsplit("/", 1)
    return parts[0] if len(parts) == 2 else ""


def subfolder_from_folder(folder):
    """working\\historical_drives\\<folder>, where `folder` is a registry original_name's folder
    (`<drive label>/<path on the drive>`, forward slashes)."""
    return WORKING_ROOT + "\\" + folder.replace("/", "\\")


def subfolder_for(original_name):
    """The retire list's `subfolder` for a file whose registry original_name is
    `<drive label>/<path on the drive>/<name>`: working\\historical_drives\\<drive label>\\<folder
    path on the drive> (Ryan, 2026-10-02). The name stays the file's own (retire_acquisition's
    default dest_name). An archive member's folder includes the archive's own name, as it does in
    original_name."""
    folder = dirname(original_name)
    if not folder:
        raise ValueError(f"original_name has no folder: {original_name!r}")
    return subfolder_from_folder(folder)


def staged_path(row):
    """Local path of the staged (or extracted) copy of a plan row. Same layout as ingest_plan."""
    if row["kind"] == "loose":
        return os.path.join(STAGING, STAGED[row["drive"]], "files", row["relpath"])
    h = hashlib.sha1(f"{row['drive']}|{row['archive']}".encode("utf-8")).hexdigest()[:6]
    key = f"{row['drive']}_{h}_{row['archive'].split(chr(92))[-1]}"
    return os.path.join(EXTRACT, key, row["member"].replace("/", "\\"))


def find_all(buf, needle, limit=5000):
    """All start offsets of `needle` in `buf` (overlapping matches included), at most `limit`."""
    out, pos = [], 0
    while len(out) < limit:
        i = buf.find(needle, pos)
        if i < 0:
            break
        out.append(i)
        pos = i + 1
    return out


class Haystack:
    """A (H, W, S) pixel array plus its bytes, built once, so many arrays can be searched in it."""

    def __init__(self, arr, raw=None):
        import numpy as np
        if arr.ndim != 3:
            raise ValueError("a (H, W, S) array is needed")
        self.arr = np.ascontiguousarray(arr)
        # `raw`, when the caller has the array's own bytes, saves a copy of the whole tile
        self.hay = raw if raw is not None and len(raw) == self.arr.nbytes else self.arr.tobytes()

    def locate(self, a):
        """Positions (oy, ox) where the array `a` (h, w, S) occurs, byte for byte, inside this array.

        Same dtype and S required. Searches the bytes of one distinctive row of `a`, keeps matches
        that sit on a pixel boundary inside one row, then verifies the whole array -- so a hit is
        exact equality of every value. Returns a list (usually 0 or 1 long)."""
        import numpy as np
        b = self.arr
        if a.ndim != 3 or a.dtype != b.dtype or a.shape[2] != b.shape[2]:
            return []
        h, w, s = a.shape
        hh, ww, _ = b.shape
        if h > hh or w > ww:
            return []
        item = a.dtype.itemsize * s
        # the most distinctive row: most distinct values among a few candidates
        cands = sorted({0, h // 8, h // 4, (3 * h) // 8, h // 2, (5 * h) // 8, (3 * h) // 4, (7 * h) // 8, h - 1})
        best, best_n = cands[0], -1
        for r in cands:
            n = len(np.unique(a[r]))
            if n > best_n:
                best, best_n = r, n
        if best_n < 4 and w * s > 8:      # a flat row: no useful anchor
            return []
        needle = np.ascontiguousarray(a[best]).tobytes()
        stride = ww * item
        # two more rows to compare before the whole array: a dark image has many near-identical rows, so the
        # anchor can match thousands of places, and comparing the whole array at each costs about a millisecond
        checks = sorted({h // 3, (2 * h) // 3, h - 1} - {best})
        hits = []
        for i in find_all(self.hay, needle):
            row, byte_col = divmod(i, stride)
            if byte_col % item or byte_col + len(needle) > stride:
                continue
            oy, ox = row - best, byte_col // item
            if oy < 0 or oy + h > hh or ox + w > ww:
                continue
            if any(not np.array_equal(b[oy + r, ox:ox + w], a[r]) for r in checks):
                continue
            if np.array_equal(b[oy:oy + h, ox:ox + w], a):
                hits.append((oy, ox))
        return hits


def locate_subarray(a, b):
    """Positions (oy, ox) where `a` (h, w, S) occurs byte for byte inside `b` (H, W, S)."""
    return Haystack(b).locate(a)


# ---------------------------------------------------------------------------------------------
# 1. the group table
# ---------------------------------------------------------------------------------------------

TABLE_COLS = ["group", "group_n", "acq_id", "batch", "instrument", "drive", "label", "kind", "relpath",
              "archive", "member", "original_name", "name", "folder", "size", "sha256",
              "acquisition_datetime", "plan_project", "project_id", "project_name", "project_status",
              "canonical_path", "primary_file_name", "staged_path"]


def build_table(plan_csv=PLAN, prov_csv=PROVENANCE, nas=NAS):
    """One row per group member: the plan row, its ACQ-ID (provenance, joined on sha256 and checked
    against relpath/archive+member), and the production registry's project and path."""
    plan = [r for r in rcsv(plan_csv) if r["acq_group"]]
    prov = collections.defaultdict(list)
    for r in rcsv(prov_csv):
        prov[r["sha256"]].append(r)
    reg = {r["acq_id"]: r for r in rcsv(os.path.join(nas, "registries", "registry_raw.csv"))}
    projects = {r["project_id"]: r for r in rcsv(os.path.join(nas, "registries", "registry_projects.csv"))}
    retired = set()
    rp = os.path.join(nas, "registries", "retired_acquisitions.csv")
    if os.path.exists(rp):
        retired = {r["acq_id"] for r in rcsv(rp)}
    rows, problems = [], []
    for e in plan:
        ps = prov.get(e["sha256"], [])
        if len(ps) != 1:
            problems.append(f"{e['original_name']}: {len(ps)} provenance rows")
            continue
        p = ps[0]
        same = (p["relpath"] == e["relpath"] and p["archive"] == e["archive"] and p["member"] == e["member"])
        if not same:
            problems.append(f"{e['original_name']}: provenance row {p['acq_id']} names another path")
            continue
        r = reg.get(p["acq_id"])
        if r is None:
            problems.append(f"{p['acq_id']}: not in registry_raw ({'retired' if p['acq_id'] in retired else 'absent'})")
            continue
        if r["original_name"] != e["original_name"]:
            problems.append(f"{p['acq_id']}: registry original_name differs from the plan")
            continue
        pid = (r.get("project_id") or "").strip()
        pr = projects.get(pid, {})
        rows.append({
            "group": e["acq_group"], "group_n": e["acq_group_n"], "acq_id": p["acq_id"], "batch": e["batch"],
            "instrument": e["instrument"], "drive": e["drive"], "label": DRIVES[e["drive"]], "kind": e["kind"],
            "relpath": e["relpath"], "archive": e["archive"], "member": e["member"],
            "original_name": e["original_name"], "name": basename(e["original_name"]),
            "folder": dirname(e["original_name"]), "size": e["size"], "sha256": e["sha256"],
            "acquisition_datetime": e["acquisition_datetime"], "plan_project": e["project"],
            "project_id": pid, "project_name": pr.get("name", ""), "project_status": pr.get("status", ""),
            "canonical_path": r["canonical_path"], "primary_file_name": r["primary_file_name"],
            "staged_path": staged_path(e)})
    return rows, problems


def cmd_table(args):
    rows, problems = build_table()
    os.makedirs(args.out, exist_ok=True)
    wcsv(os.path.join(args.out, "members.csv"), TABLE_COLS, rows)
    print(f"members.csv: {len(rows)} rows, {len({r['group'] for r in rows})} groups, {len(problems)} problems")
    for p in problems:
        print("  PROBLEM:", p)
    mism = sum(1 for r in rows if (r["plan_project"] or "") != (r["project_name"] or ""))
    print(f"plan project != registry project name: {mism} rows")
    return 1 if problems else 0


# ---------------------------------------------------------------------------------------------
# 2. per-file metadata (XML only, no pixels)
# ---------------------------------------------------------------------------------------------

FEATURE_COLS = ["sha256", "path", "SizeX", "SizeY", "SizeZ", "SizeC", "SizeT", "SizeS", "SizeM", "SizeH",
                "PixelType", "pxX", "pxY", "AcquisitionDateAndTime", "CreationDate", "UserName", "App",
                "layer_elements", "has_scalebar", "n_channels_xml", "channels", "scenes_xml",
                "scene_centers", "n_level0", "n_entries", "scenes_dir", "scene_shapes", "dims", "dtype",
                "compression", "error"]


def _tx(node, path):
    e = node.find(path)
    return (e.text or "").strip() if e is not None and e.text else ""


def czi_features(path):
    """Metadata and layout of one .czi from its XML and subblock directory (no pixel read)."""
    import czifile
    from xml.etree import ElementTree as ET
    out = {"path": path}
    try:
        with czifile.CziFile(longpath(path)) as czi:
            xml = czi.metadata()
            if isinstance(xml, bytes):
                xml = xml.decode("utf-8", "replace")
            md = ET.fromstring(xml).find("Metadata")
            img = md.find("Information/Image")
            for k in ("SizeX", "SizeY", "SizeZ", "SizeC", "SizeT", "SizeS", "SizeM", "SizeH", "PixelType",
                      "AcquisitionDateAndTime"):
                out[k] = _tx(img, k)
            doc = md.find("Information/Document")
            out["CreationDate"] = _tx(doc, "CreationDate") if doc is not None else ""
            out["UserName"] = _tx(doc, "UserName") if doc is not None else ""
            app = md.find("Information/Application")
            out["App"] = (_tx(app, "Name") + " " + _tx(app, "Version")).strip() if app is not None else ""
            for ax in ("X", "Y"):
                e = md.find(f"Scaling/Items/Distance[@Id='{ax}']/Value")
                out["px" + ax] = (e.text or "") if e is not None else ""
            lay = md.find("Layers")
            els = []
            if lay is not None:
                for el in lay.iter("Elements"):
                    els += [c.tag for c in el]
            out["layer_elements"] = ";".join(sorted(els))
            out["has_scalebar"] = "ScaleBar" in els
            chs = md.findall("Information/Image/Dimensions/Channels/Channel")
            out["n_channels_xml"] = len(chs)
            out["channels"] = ";".join((c.get("Name") or "") for c in chs)
            sc = md.findall("Information/Image/Dimensions/S/Scenes/Scene")
            out["scenes_xml"] = len(sc)
            out["scene_centers"] = ";".join(_tx(s, "CenterPosition") for s in sc)    # all of them: a plate has 50+
            fd = czi.filtered_subblock_directory
            out["n_level0"] = len(fd)
            out["n_entries"] = len(czi.subblock_directory)
            out["scenes_dir"] = ";".join(str(s) for s in czi.scenes.keys())
            out["scene_shapes"] = ";".join(
                f"{s}:{'x'.join(str(v) for v in im.shape)}@{'.'.join(str(v) for v in im.bbox[:2])}"
                for s, im in czi.scenes.items())[:600]
            first = next(iter(czi.scenes.values()))
            out["dims"] = ",".join(first.dims)
            out["dtype"] = str(first.dtype)
            comp = collections.Counter(str(e.compression).split(" ")[0].split(".")[-1] for e in fd)
            out["compression"] = ";".join(sorted(comp))
    except Exception as ex:   # counted and reported by the caller, never swallowed silently
        out["error"] = f"{type(ex).__name__}: {ex}"
    return out


def cmd_features(args):
    rows = rcsv(os.path.join(args.out, "members.csv"))
    t0 = time.time()
    with cf.ThreadPoolExecutor(args.workers) as ex:
        feats = list(ex.map(lambda r: dict(czi_features(r["staged_path"]), sha256=r["sha256"]), rows))
    wcsv(os.path.join(args.out, "features.csv"), FEATURE_COLS, feats)
    errs = [f for f in feats if f.get("error")]
    print(f"features.csv: {len(feats)} files in {time.time() - t0:.0f}s, {len(errs)} errors")
    for f in errs:
        print("  ERROR:", f["path"], f["error"])
    return 1 if errs else 0


# ---------------------------------------------------------------------------------------------
# 3. the tile cache: every level-0 subblock's place, shape and payload SHA-256
# ---------------------------------------------------------------------------------------------

def czi_pieces(path):
    """Level-0 subblocks of one .czi: scene, mosaic index, non-spatial dimension index, x, y, w, h, the
    payload's file offset, size and SHA-256. Reads the whole file once."""
    import czifile
    pieces, scenes = [], {}
    with czifile.CziFile(longpath(path)) as czi:
        for sid, im in czi.scenes.items():
            scenes[int(sid)] = list(im.bbox)
        # in file order: the directory is sorted by mosaic index, which seeks all over a big file
        for e in sorted(czi.filtered_subblock_directory, key=lambda e: e.file_position):
            if e.dims[-3:] != ("Y", "X", "S"):
                raise ValueError(f"unexpected dimension order {e.dims} in {path}")
            d = dict(zip(e.dims, e.start))
            sh = dict(zip(e.dims, e.shape))
            seg = e.read_segment_data(czi)
            raw = seg.data(raw=True)
            expect = int(e.stored_shape[-3]) * int(e.stored_shape[-2]) * int(e.stored_shape[-1]) * e.dtype.itemsize
            if len(raw) != expect:            # a truncated file reads short without raising
                raise ValueError(f"short or long tile payload in {path}: {len(raw)} bytes, expected {expect}")
            pieces.append({
                "scene": max(int(e.scene_index), 0), "m": int(e.mosaic_index),
                "key": [[k, int(d[k])] for k in e.dims if k not in ("X", "Y", "S")],
                "x": int(d["X"]), "y": int(d["Y"]), "w": int(sh["X"]), "h": int(sh["Y"]),
                "samples": int(sh["S"]), "dtype": str(e.dtype), "compression": str(e.compression),
                "stored": [int(v) for v in e.stored_shape], "pos": int(seg.data_offset), "nbytes": len(raw),
                "hash": hashlib.sha256(raw).hexdigest()})
    return {"path": path, "size": os.path.getsize(longpath(path)), "scenes": scenes, "pieces": pieces}


def pieces_cache_path(out, sha):
    return os.path.join(out, "pieces", sha + ".json")


def load_pieces(out, sha, path):
    """The cached tile table of a file (computed and cached on first use)."""
    cp = pieces_cache_path(out, sha)
    if os.path.exists(cp):
        with io.open(cp, encoding="utf-8") as f:
            return json.load(f)
    data = czi_pieces(path)
    data["sha256"] = sha
    os.makedirs(os.path.dirname(cp), exist_ok=True)
    tmp = cp + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, cp)
    return data


def sibling_group_keys(mem):
    """Groups whose members all carry a stage position (XML scene centre) and no two coincide: the files
    are different scenes of one acquisition, so no member can be a copy, crop or stitch of another
    (derived files keep their parent's scene centre; checked on every relation found). The crop and
    stitch gates skip them; `pieces --skip-siblings` does not read them."""
    g = collections.defaultdict(list)
    for m in mem:
        g[m["group"]].append(scene_centers(m["feat"]))
    return {k for k, cs in g.items()
            if len(cs) > 1 and all(cs) and not any(a & b for i, a in enumerate(cs) for b in cs[i + 1:])}


def cmd_check(args):
    """Every tile cache: parses, holds as many tiles as the file's directory has, matches the file's
    size, and every payload has exactly the bytes its shape needs and lies inside the file."""
    import numpy as np
    mem = load_members_with_features(args.out)
    n = bad = missing = 0
    for m in mem:
        p = pieces_cache_path(args.out, m["sha256"])
        if not os.path.exists(p):
            missing += 1
            continue
        n += 1
        try:
            with io.open(p, encoding="utf-8") as f:
                d = json.load(f)
            probs = []
            if len(d["pieces"]) != int(m["feat"]["n_level0"]):
                probs.append(f"{len(d['pieces'])} tiles, directory has {m['feat']['n_level0']}")
            if d["size"] != int(m["size"]):
                probs.append("size differs from the plan's")
            for pc in d["pieces"]:
                h, w, sm = pc["stored"][-3:]
                if pc["nbytes"] != h * w * sm * np.dtype(pc["dtype"]).itemsize:
                    probs.append("a payload is short or long")
                    break
            if d["pieces"] and max(pc["pos"] + pc["nbytes"] for pc in d["pieces"]) > d["size"]:
                probs.append("a payload runs past the end of the file")
        except Exception as e:     # counted and reported
            probs = [f"{type(e).__name__}: {e}"]
        if probs:
            bad += 1
            print("  BAD:", m["name"], "; ".join(probs))
    print(f"tile caches: {n} checked, {bad} bad, {missing} not built")
    return 1 if bad else 0


def cmd_pieces(args):
    rows = rcsv(os.path.join(args.out, "members.csv"))
    if args.skip_siblings:
        mem = load_members_with_features(args.out)
        sib = sibling_group_keys(mem)
        rows = [r for r in rows if r["group"] not in sib]
        print(f"skipping the {len(sib)} sibling groups (distinct stage positions)")
    todo = [r for r in rows if not os.path.exists(pieces_cache_path(args.out, r["sha256"]))]
    print(f"{len(rows)} members, {len(todo)} to hash ({sum(int(r['size']) for r in todo) / 1e9:.0f} GB)")
    t0, done, errs = time.time(), 0, []

    def one(r):
        load_pieces(args.out, r["sha256"], r["staged_path"])
        return r

    # biggest first so the long tail of small files fills the gaps; workers bound the I/O contention
    todo.sort(key=lambda r: -int(r["size"]))
    with cf.ThreadPoolExecutor(args.workers) as ex:
        futs = {ex.submit(one, r): r for r in todo}
        for fut in cf.as_completed(futs):
            r = futs[fut]
            try:
                fut.result()
            except Exception as e:   # counted, reported, non-zero exit
                errs.append((r["staged_path"], f"{type(e).__name__}: {e}"))
            done += 1
            if done % 25 == 0 or done == len(todo):
                print(f"  {done}/{len(todo)} files, {time.time() - t0:.0f}s, {len(errs)} errors", flush=True)
    for p, e in errs:
        print("  ERROR:", p, e)
    return 1 if errs else 0


# ---------------------------------------------------------------------------------------------
# 4. pixel tests between two files: A (the candidate copy) contained in B (the candidate parent)
# ---------------------------------------------------------------------------------------------

def area(p):
    return p["w"] * p["h"]


def index_by_hash(F):
    """(payload hash, w, h) -> the tiles of F with that payload."""
    idx = collections.defaultdict(list)
    for q in F["pieces"]:
        idx[(q["hash"], q["w"], q["h"])].append(q)
    return idx


def hash_match(A, B, bidx=None):
    """Is every tile of A byte-identical to a tile of B, all at ONE constant offset?

    Per A scene: every (B scene, dx, dy) that some identical tile pair implies gets a vote; the best
    offset wins, and the A tiles that have a byte-identical B tile at exactly that offset are the
    matched ones. Returns a dict with the matched share by tile count and by area, the offset per A
    scene, and `complete` (all A tiles matched). `bidx` is index_by_hash(B), if the caller has it."""
    byhash = bidx if bidx is not None else index_by_hash(B)
    n_a = len(A["pieces"])
    tot_area = sum(area(p) for p in A["pieces"]) or 1
    n_m = a_m = 0
    maps = {}
    for sa in sorted({p["scene"] for p in A["pieces"]}):
        mine = [p for p in A["pieces"] if p["scene"] == sa]
        votes = collections.Counter()
        for p in mine:
            for q in byhash.get((p["hash"], p["w"], p["h"]), ()):
                votes[(q["scene"], q["x"] - p["x"], q["y"] - p["y"])] += 1
        if not votes:
            maps[sa] = {"n": 0, "of": len(mine)}
            continue
        (sb, dx, dy), _ = votes.most_common(1)[0]
        hit = 0
        for p in mine:
            if any(q["scene"] == sb and q["x"] - p["x"] == dx and q["y"] - p["y"] == dy
                   for q in byhash.get((p["hash"], p["w"], p["h"]), ())):
                hit += 1
                a_m += area(p)
        n_m += hit
        maps[sa] = {"to_scene": sb, "dx": dx, "dy": dy, "n": hit, "of": len(mine)}
    return {"method": "hash", "pieces": n_a, "matched": n_m, "area_frac": a_m / tot_area,
            "complete": n_m == n_a and n_a > 0, "maps": maps}


def tileset_match(A, B):
    """Is every tile of A byte-identical to a (distinct) tile of B, wherever it sits?

    ZEN's stitching of a tile scan can keep the tiles and re-place each one by its own small shift, so a
    stitched copy holds the same tile payloads at different positions: no one offset fits, yet every
    tile is the original's. Counts each payload (hash and shape) at most as often as B holds it."""
    cb = collections.Counter((q["hash"], q["w"], q["h"]) for q in B["pieces"])
    ca = collections.Counter((p["hash"], p["w"], p["h"]) for p in A["pieces"])
    n_a = len(A["pieces"])
    matched = sum(min(v, cb.get(k, 0)) for k, v in ca.items())
    return {"method": "retile", "pieces": n_a, "matched": matched,
            "area_frac": matched / n_a if n_a else 0.0, "complete": n_a > 0 and matched == n_a}


def grid_score(F):
    """How far a file's tile positions are from a regular grid: the distinct x and y positions per tile
    (about (columns + rows) / tiles for the acquisition's own grid, about 2 for a stitched file whose
    tiles were each shifted)."""
    ps = [p for p in F["pieces"]]
    if not ps:
        return 0.0
    keys = {(p["scene"], p["x"], p["y"]) for p in ps}
    xs = {(s, x) for (s, x, y) in keys}
    ys = {(s, y) for (s, x, y) in keys}
    return (len(xs) + len(ys)) / max(len(keys), 1)


class TileReader:
    """Reads uncompressed tile payloads of one .czi (by the offsets in its tile cache) as arrays."""

    def __init__(self, path):
        self.fh = open(longpath(path), "rb")

    def close(self):
        self.fh.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def read_raw(self, p):
        """The tile's payload bytes and its (h, w, s) shape."""
        if any(v != 1 for v in p["stored"][:-3]):
            raise ValueError("a subblock with more than one plane")
        self.fh.seek(p["pos"])
        raw = self.fh.read(p["nbytes"])
        if len(raw) != p["nbytes"]:
            raise IOError(f"short read at {p['pos']}")
        return raw, tuple(p["stored"][-3:])

    def read(self, p):
        import numpy as np
        raw, (h, w, s) = self.read_raw(p)
        return np.frombuffer(raw, dtype=np.dtype(p["dtype"])).reshape(h, w, s)

    def haystack(self, p):
        """A Haystack over the tile, sharing the payload bytes (no copy)."""
        import numpy as np
        raw, (h, w, s) = self.read_raw(p)
        return Haystack(np.frombuffer(raw, dtype=np.dtype(p["dtype"])).reshape(h, w, s), raw=raw)


def crop_match(A, B, a_path, b_path, hint=None, probes=3):
    """Is every tile of A a byte-exact sub-rectangle of a tile of B, all at ONE constant offset?

    The offset (B scene, dx, dy) comes from `hint` -- what a hash match of A's whole tiles implied --
    or, without one, from searching for the bytes of up to `probes` of A's largest tiles inside B's
    tiles. Then every A tile must either be byte-identical to a B tile at that offset (no read needed)
    or equal the region of the B tile it lands on."""
    import numpy as np
    byhash = index_by_hash(B)
    tot = sum(area(p) for p in A["pieces"]) or 1
    n_a = len(A["pieces"])
    with TileReader(b_path) as rb, TileReader(a_path) as ra:

        def verify(offset):
            sb, dx, dy = offset
            n_m = a_m = 0
            cache = {}
            for pa in A["pieces"]:
                if any(q["scene"] == sb and q["x"] - pa["x"] == dx and q["y"] - pa["y"] == dy
                       for q in byhash.get((pa["hash"], pa["w"], pa["h"]), ())):
                    n_m += 1
                    a_m += area(pa)
                    continue
                a_arr = ra.read(pa)
                x0, y0 = pa["x"] + dx, pa["y"] + dy
                for qi, q in enumerate(B["pieces"]):
                    if q["scene"] != sb or q["dtype"] != pa["dtype"] or q["samples"] != pa["samples"]:
                        continue
                    if q["x"] <= x0 and q["y"] <= y0 and x0 + pa["w"] <= q["x"] + q["w"] \
                            and y0 + pa["h"] <= q["y"] + q["h"]:
                        b_arr = cache.get(qi)
                        if b_arr is None:
                            b_arr = cache[qi] = rb.read(q)
                            if len(cache) > 64:
                                cache.pop(next(iter(cache)))
                        sub = b_arr[y0 - q["y"]:y0 - q["y"] + pa["h"], x0 - q["x"]:x0 - q["x"] + pa["w"]]
                        if np.array_equal(sub, a_arr):
                            n_m += 1
                            a_m += area(pa)
                            break
            return n_m, a_m

        def result(offset, n_m, a_m):
            sb, dx, dy = offset
            return {"method": "crop", "pieces": n_a, "matched": n_m, "area_frac": a_m / tot,
                    "complete": n_m == n_a, "maps": {0: {"to_scene": sb, "dx": dx, "dy": dy, "n": n_m, "of": n_a}}}

        if hint is not None:
            # whole tiles already pinned the offset: take the verdict at that offset, however partial
            n_m, a_m = verify(hint)
            return result(hint, n_m, a_m)
        a_sorted = sorted(range(n_a), key=lambda i: -area(A["pieces"][i]))
        for ia in a_sorted[:probes]:
            pa = A["pieces"][ia]
            a_arr = ra.read(pa)
            for q in B["pieces"]:
                if q["w"] < pa["w"] or q["h"] < pa["h"] or q["dtype"] != pa["dtype"] \
                        or q["samples"] != pa["samples"]:
                    continue
                hits = locate_subarray(a_arr, rb.read(q))
                if hits:
                    oy, ox = hits[0]
                    off = (q["scene"], q["x"] + ox - pa["x"], q["y"] + oy - pa["y"])
                    n_m, a_m = verify(off)
                    return result(off, n_m, a_m)
    return {"method": "crop", "pieces": n_a, "matched": 0, "area_frac": 0.0, "complete": False, "maps": {}}


def distinct_sample(arr, n=64):
    """How many distinct values among about `n` evenly spaced values of an array: a blank (black,
    saturated or empty-glass) tile has one or two, a tile with image content has dozens."""
    import numpy as np
    flat = arr.ravel()
    return int(len(np.unique(flat[::max(1, flat.size // n)])))


def stitch_match(S, T, s_path, t_path, sample=16, frac=0.30):
    """Does the stitched candidate S contain, byte for byte, the interiors of the tiles of T?

    ZEN's stitching re-places and blends tiles, so S cannot match T tile for tile; but where one tile
    alone contributes, S holds that tile's pixels unchanged. Of the evenly spaced tiles of T, the first
    `sample` whose central `frac` x `frac` patch carries image content (blank glass is skipped: it cannot
    be located) are searched for in S's pixel data. A found patch is exact equality of every value, so
    one hit proves S holds that tile's pixels; the per-tile shifts show the re-placement. `complete`:
    at least half of the tested tiles are found (the rest sit where S blended or corrected them)."""
    import numpy as np
    tiles = [p for p in T["pieces"] if p["h"] >= 64 and p["w"] >= 64]
    tiles.sort(key=lambda p: (p["scene"], p["y"], p["x"]))
    step = max(1, len(tiles) // (sample * 3))
    candidates = tiles[::step]
    found, tested, shifts = 0, 0, []
    with TileReader(t_path) as rt, TileReader(s_path) as rs:
        hays = []                       # S's pixel data, built once
        for sp in S["pieces"]:
            hays.append((sp, Haystack(rs.read(sp))))
        for tp in candidates:
            if tested >= sample:
                break
            tarr = rt.read(tp)
            h, w, _ = tarr.shape
            r0, r1 = int(h * (0.5 - frac / 2)), int(h * (0.5 + frac / 2))
            c0, c1 = int(w * (0.5 - frac / 2)), int(w * (0.5 + frac / 2))
            patch = tarr[r0:r1, c0:c1]
            if distinct_sample(patch) < 8:
                continue                # blank: nothing to find
            tested += 1
            hit = None
            for sp, hay in hays:
                if sp["dtype"] != tp["dtype"] or sp["samples"] != tp["samples"]:
                    continue
                hs = hay.locate(patch)
                if hs:
                    oy, ox = hs[0]
                    hit = (sp["x"] + ox - (tp["x"] + c0), sp["y"] + oy - (tp["y"] + r0))
                    break
            if hit is not None:
                found += 1
                shifts.append(hit)
    return {"method": "stitch", "sampled": tested, "found": found, "shifts": shifts,
            "complete": tested >= 4 and found * 2 >= tested}


def cutset_match(A, B, a_path, b_path, max_cached=96, probe=6):
    """Is every tile of A a byte-exact sub-rectangle of SOME tile of B, each at its own offset?

    ZEN's stitching can fuse the tiles: it trims each one to the part it contributes and re-places it, so
    a stitched copy's tiles are pieces of the original's tiles at offsets that differ from tile to tile
    (no one offset fits, and few tiles are whole). Each A tile is looked for in the B tiles that are at
    least as big, in the same channel / time plane; a hit is exact equality of every value. Whole tiles
    are found by payload hash first. A trimmed copy has almost every tile found, so once `probe`
    informative tiles have been searched for in vain the pair is given up (an unrelated pair would
    otherwise cost a full search per tile)."""
    import numpy as np
    byhash = index_by_hash(B)
    n_a = len(A["pieces"])
    tot = sum(area(p) for p in A["pieces"]) or 1
    found, a_found, shifts, tried = 0, 0, [], 0
    cache = collections.OrderedDict()
    with TileReader(b_path) as rb, TileReader(a_path) as ra:
        for pa in A["pieces"]:
            whole = byhash.get((pa["hash"], pa["w"], pa["h"]))
            if whole:
                q = whole[0]
                found += 1
                a_found += area(pa)
                shifts.append((q["x"] - pa["x"], q["y"] - pa["y"]))
                continue
            if found == 0 and tried >= probe:
                break                                       # nothing found in `probe` tries: not related
            a_arr = ra.read(pa)
            if distinct_sample(a_arr) < 8:
                continue                                    # blank: nothing to find
            tried += 1
            for qi, q in enumerate(B["pieces"]):
                if q["w"] < pa["w"] or q["h"] < pa["h"] or q["dtype"] != pa["dtype"] \
                        or q["samples"] != pa["samples"] or q["key"] != pa["key"]:
                    continue
                hay = cache.get(qi)
                if hay is None:
                    hay = cache[qi] = rb.haystack(q)
                    if len(cache) > max_cached:
                        cache.popitem(last=False)
                else:
                    cache.move_to_end(qi)
                hs = hay.locate(a_arr)
                if hs:
                    oy, ox = hs[0]
                    found += 1
                    a_found += area(pa)
                    shifts.append((q["x"] + ox - pa["x"], q["y"] + oy - pa["y"]))
                    break
    return {"method": "retrim", "pieces": n_a, "matched": found, "area_frac": a_found / tot,
            "complete": n_a > 0 and found == n_a, "shifts": shifts}


def trim_records(ms, P, complete_pairs, exhaustive=False):
    """Relation records for re-trimmed tiles (cutset_match) on the pairs no other test fully explained: same
    pixel size, a stage position in common, and the candidate copy A holds less pixel area than B.
    `exhaustive` drops the pixel-size and stage-position gates (to validate them on a sample)."""
    recs = []
    for ma in ms:
        for mb in ms:
            a, b = ma["acq_id"], mb["acq_id"]
            if a == b or (a, b) in complete_pairs or (b, a) in complete_pairs:
                continue
            if sum(area(p) for p in P[a]["pieces"]) >= sum(area(p) for p in P[b]["pieces"]):
                continue
            pa, pb = pixel_um(ma["feat"]), pixel_um(mb["feat"])
            if not exhaustive and pa and pb and abs(pa - pb) / pb > 0.01:
                continue
            ca, cb = scene_centers(ma["feat"]), scene_centers(mb["feat"])
            if not exhaustive and ca and cb and not (ca & cb):
                continue
            if len(P[a]["scenes"]) != 1 or len(P[b]["scenes"]) != 1:
                continue
            c = cutset_match(P[a], P[b], ma["staged_path"], mb["staged_path"])
            if c["matched"]:
                sh = c["shifts"]
                recs.append({"a": a, "b": b, "kind": "retrim", "complete": c["complete"], "pieces": c["pieces"],
                             "matched": c["matched"], "area_frac": round(c["area_frac"], 4),
                             "maps": {"shifts": sh[:6], "distinct_shifts": len(set(sh))},
                             "n_b": len(P[b]["pieces"]), "n_scenes_b": 1, "n_scenes_a": 1})
    return recs


def region_offset(A, B, ra, rb, seg=96, nrows=32, probes=4):
    """Where does A's image sit inside B's? Returns (dx, dy) with A(X, Y) = B(X + dx, Y + dy), or None.

    A distinctive stretch (`seg` pixels of one row, confirmed on the `nrows` rows below it) of each of A's
    `probes` largest informative tiles is searched for in the tiles of B -- each B tile is read once for
    all the probes. A crop that ZEN re-blocked from its own origin has blocks that straddle the
    original's, so no whole tile or tile-sized piece of it is found in B; its pixels still are."""
    import numpy as np
    needles = []
    for pa in sorted(A["pieces"], key=lambda q: -area(q)):
        if len(needles) >= probes:
            break
        if pa["w"] < seg + 2 or pa["h"] < nrows + 8:
            continue
        a = ra.read(pa)
        if distinct_sample(a) < 8:
            continue
        h, w, sm = a.shape
        # a different stretch of the tile for each probe: one grid phase must not make every probe straddle
        # a block boundary of B
        c0 = int((w - seg) * (0.2 + 0.2 * len(needles)))
        best, best_n = None, 15
        for r in sorted({h // 8, h // 4, h // 2, (3 * h) // 4, (7 * h) // 8}):
            if r + nrows > h:
                continue
            n = len(np.unique(a[r, c0:c0 + seg]))
            if n > best_n:
                best, best_n = r, n
        if best is None:
            continue
        needles.append({"pa": pa, "c0": c0, "row": best, "item": a.dtype.itemsize * sm,
                        "bytes": np.ascontiguousarray(a[best, c0:c0 + seg]).tobytes(),
                        "block": np.ascontiguousarray(a[best:best + nrows, c0:c0 + seg])})
    if not needles:
        return None
    for q in B["pieces"]:
        todo = [nd for nd in needles if q["dtype"] == nd["pa"]["dtype"] and q["samples"] == nd["pa"]["samples"]
                and q["key"] == nd["pa"]["key"] and q["w"] >= seg and q["h"] >= nrows]
        if not todo:
            continue
        hay = rb.haystack(q)
        bh, bw, _ = hay.arr.shape
        for nd in todo:
            stride = bw * nd["item"]
            for i in find_all(hay.hay, nd["bytes"], limit=50):
                row, byte_col = divmod(i, stride)
                if byte_col % nd["item"] or byte_col + len(nd["bytes"]) > stride or row + nrows > bh:
                    continue
                ox = byte_col // nd["item"]
                if np.array_equal(hay.arr[row:row + nrows, ox:ox + seg], nd["block"]):
                    return (q["x"] + ox - (nd["pa"]["x"] + nd["c0"]), q["y"] + row - (nd["pa"]["y"] + nd["row"]))
    return None


def region_compare(A, B, ra, rb, off, cache_max=48):
    """With A(X, Y) = B(X + off[0], Y + off[1]) assumed: how much of A's image is B's, pixel for pixel?

    Tile by tile: each A tile is compared with the B tiles under it (where B's tiles overlap, equal to any
    one of them counts). Returns pixel and tile counts, and the same for the informative (non-blank) tiles."""
    import numpy as np
    cache = collections.OrderedDict()

    def tile(qi):
        t = cache.get(qi)
        if t is None:
            t = cache[qi] = rb.read(B["pieces"][qi])
            if len(cache) > cache_max:
                cache.popitem(last=False)
        else:
            cache.move_to_end(qi)
        return t

    out = {"pixels": 0, "equal": 0, "tiles": 0, "equal_tiles": 0, "informative": 0, "equal_informative": 0}
    for pa in sorted(A["pieces"], key=lambda q: (str(q["key"]), q["y"], q["x"])):
        a = ra.read(pa)
        h, w, _ = a.shape
        x0, y0 = pa["x"] + off[0], pa["y"] + off[1]
        ok = np.zeros((h, w), bool)
        for qi, q in enumerate(B["pieces"]):
            if q["dtype"] != pa["dtype"] or q["samples"] != pa["samples"] or q["key"] != pa["key"]:
                continue
            ix0, iy0 = max(x0, q["x"]), max(y0, q["y"])
            ix1, iy1 = min(x0 + w, q["x"] + q["w"]), min(y0 + h, q["y"] + q["h"])
            if ix1 <= ix0 or iy1 <= iy0:
                continue
            b = tile(qi)
            sa = a[iy0 - y0:iy1 - y0, ix0 - x0:ix1 - x0]
            sb = b[iy0 - q["y"]:iy1 - q["y"], ix0 - q["x"]:ix1 - q["x"]]
            ok[iy0 - y0:iy1 - y0, ix0 - x0:ix1 - x0] |= (sa == sb).all(axis=-1)
        e = int(ok.sum())
        full = e == h * w
        out["pixels"] += h * w
        out["equal"] += e
        out["tiles"] += 1
        out["equal_tiles"] += int(full)
        if distinct_sample(a) >= 8:
            out["informative"] += 1
            out["equal_informative"] += int(full)
    return out


def region_match(A, B, a_path, b_path):
    """Is A's whole image a region of B's image, byte for byte (a crop whose blocks are its own)?

    `complete`: every pixel of A equals the pixel of B at one constant offset, and A has content (at
    least half of its tiles are not blank). A pair whose offset is found but whose pixels equal only in
    part is returned as a partial match (area_frac = the equal share), so it can be flagged."""
    with TileReader(a_path) as ra, TileReader(b_path) as rb:
        off = region_offset(A, B, ra, rb)
        if off is None:
            return {"method": "region", "pieces": len(A["pieces"]), "matched": 0, "area_frac": 0.0,
                    "complete": False, "maps": {}}
        c = region_compare(A, B, ra, rb, off)
    frac = c["equal"] / max(c["pixels"], 1)
    complete = (c["equal"] == c["pixels"] and c["informative"] > 0
                and c["equal_informative"] * 2 >= c["informative"])
    return {"method": "region", "pieces": c["tiles"], "matched": c["equal_tiles"], "area_frac": frac,
            "complete": complete, "maps": {"dx": off[0], "dy": off[1], "equal_share": round(frac, 6),
                                           "informative": c["informative"]}}


def region_records(ms, P, complete_pairs, exhaustive=False):
    """Relation records for a re-blocked crop (region_match): only for a member that no other test has found
    contained in anything, against each member that is larger, has the same pixel size and shares a stage
    position (the same gates as trim_records). `exhaustive` drops the pixel-size and stage-position gates."""
    recs = []
    contained = {a for (a, _b) in complete_pairs}
    for ma in ms:
        a = ma["acq_id"]
        if a in contained or len(P[a]["scenes"]) != 1:
            continue
        for mb in ms:
            b = mb["acq_id"]
            if a == b or (b, a) in complete_pairs or len(P[b]["scenes"]) != 1:
                continue
            if sum(area(p) for p in P[a]["pieces"]) >= sum(area(p) for p in P[b]["pieces"]):
                continue
            pa, pb = pixel_um(ma["feat"]), pixel_um(mb["feat"])
            if not exhaustive and pa and pb and abs(pa - pb) / pb > 0.01:
                continue
            ca, cb = scene_centers(ma["feat"]), scene_centers(mb["feat"])
            if not exhaustive and ca and cb and not (ca & cb):
                continue
            g = region_match(P[a], P[b], ma["staged_path"], mb["staged_path"])
            if g["complete"] or g["area_frac"] >= 0.5:
                recs.append({"a": a, "b": b, "kind": "region", "complete": g["complete"], "pieces": g["pieces"],
                             "matched": g["matched"], "area_frac": round(g["area_frac"], 4), "maps": g["maps"],
                             "n_b": len(P[b]["pieces"]), "n_scenes_b": 1, "n_scenes_a": 1})
    return recs


# ---------------------------------------------------------------------------------------------
# 5. the relations of one group
# ---------------------------------------------------------------------------------------------

def parse_dt(s):
    """A ZEN timestamp (7-digit fraction, Z or +hh:mm) as an aware datetime; None if blank/bad."""
    s = (s or "").strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    if "." in s:
        head, rest = s.split(".", 1)
        i = 0
        while i < len(rest) and rest[i].isdigit():
            i += 1
        s = head + "." + rest[:i][:6].ljust(6, "0") + rest[i:]
    try:
        d = dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def scene_centers(feat):
    """The set of (x, y) stage positions (um, 2 decimals) of a file's scenes, from its XML."""
    out = set()
    for c in (feat.get("scene_centers") or "").split(";"):
        parts = c.split(",")
        if len(parts) == 2:
            try:
                out.add((round(float(parts[0]), 2), round(float(parts[1]), 2)))
            except ValueError:
                pass
    return out


def pixel_um(feat):
    try:
        return float(feat.get("pxX") or "") * 1e6
    except ValueError:
        return None


def max_tile(F):
    return (max((p["w"] for p in F["pieces"]), default=0), max((p["h"] for p in F["pieces"]), default=0))


def crop_gate(FA, FB, PA, PB):
    """Cheap preconditions for 'A is a crop of B' -- no pixels read: A's canvas is strictly smaller than
    one of B's scenes (a file cannot be a crop of a smaller or an equal one; equal ones are the hash
    test's), some B tile is at least as big as A's largest tile, the same pixel size (1%), and the
    same stage position when both files say one."""
    aw, ah = max_tile(PA)
    if not any(q["w"] >= aw and q["h"] >= ah for q in PB["pieces"]):
        return False
    a_area = max((b[2] * b[3] for b in PA["scenes"].values()), default=0)
    if not any(b[2] * b[3] > a_area for b in PB["scenes"].values()):
        return False
    pa, pb = pixel_um(FA), pixel_um(FB)
    if pa and pb and abs(pa - pb) / pb > 0.01:
        return False
    ca, cb = scene_centers(FA), scene_centers(FB)
    if ca and cb and not (ca & cb):
        return False
    return True


def stitch_gate(FA, FB, PA, PB):
    """Cheap preconditions for 'S=A is the stitched copy of the tiled B': B has clearly more tiles,
    similar canvas (-35%..+50% area), same pixel size, same stage position when both say one."""
    na, nb = len(PA["pieces"]), len(PB["pieces"])
    if nb < max(4, 3 * na):
        return False
    aa = sum(area(p) for p in PA["pieces"]) or 1
    ab = sum(area(p) for p in PB["pieces"]) or 1
    if not (0.4 <= aa / ab <= 1.6):
        return False
    pa, pb = pixel_um(FA), pixel_um(FB)
    if pa and pb and abs(pa - pb) / pb > 0.01:
        return False
    ca, cb = scene_centers(FA), scene_centers(FB)
    if ca and cb and not (ca & cb):
        return False
    return True


def informative(path, pieces, min_distinct=8, tries=3):
    """Does at least one of the `tries` largest tiles of a file carry image content? A black or saturated
    tile is byte-identical to every other black tile, so a match made only of such tiles proves nothing."""
    import numpy as np
    best = sorted(pieces, key=lambda p: -area(p))[:tries]
    with TileReader(path) as r:
        for p in best:
            if distinct_sample(r.read(p)) >= min_distinct:
                return True
    return False


def single_planes(path, F, max_bytes=200 * 10**6):
    """The image planes of a small single-tile-per-plane file as 2D float arrays (the samples of an RGB
    plane averaged), or None when the file is large or has several tiles per plane."""
    import numpy as np
    if sum(p["nbytes"] for p in F["pieces"]) > max_bytes or len(F["scenes"]) != 1:
        return None
    pos = {(p["x"], p["y"], p["w"], p["h"]) for p in F["pieces"]}
    if len(pos) != 1:
        return None
    out = []
    with TileReader(path) as r:
        for p in F["pieces"]:
            out.append(r.read(p).astype(np.float64).mean(axis=2))
    return out


def rank_correlation(a, b):
    """Spearman correlation of two same-shape 2D arrays (on a 1-in-4 pixel sample)."""
    import numpy as np
    x, y = a[::2, ::2].ravel(), b[::2, ::2].ravel()
    # dense ranks: equal values share a rank, so a flat plane has one rank and no correlation with anything
    rx = np.unique(x, return_inverse=True)[1].astype(np.float64)
    ry = np.unique(y, return_inverse=True)[1].astype(np.float64)
    if rx.std() == 0 or ry.std() == 0:
        return 0.0
    return float(np.corrcoef(rx, ry)[0, 1])


def pair_similarity(pa, Fa, pb, Fb):
    """For two small files with planes of the same shape: for each plane of A, the best rank correlation
    with a plane of B. Returns (min over A's planes of that best value, number of A planes), or None."""
    A, B = single_planes(pa, Fa), single_planes(pb, Fb)
    if not A or not B:
        return None
    best = []
    for a in A:
        vals = [rank_correlation(a, b) for b in B if b.shape == a.shape]
        if not vals:
            return None
        best.append(max(vals))
    return min(best), len(A)


def retile_records(ms, P, complete_pairs):
    """Relation records for re-placed tiles. A stitched copy that kept its tiles holds the original's tile
    payloads at positions that no single offset explains. Mutual (the same tiles both ways): the file whose
    positions are further from a regular grid is the stitched one; if the grids do not tell them apart the
    pair is undecided (recorded, not complete). `complete_pairs` are the ordered pairs already fully
    related by any other test. Returns (records, the ordered pairs this adds as complete)."""
    retile = {}
    for ma in ms:
        for mb in ms:
            a, b = ma["acq_id"], mb["acq_id"]
            if a == b or (a, b) in complete_pairs or (b, a) in complete_pairs:
                continue
            t = tileset_match(P[a], P[b])
            if t["complete"] and informative(ma["staged_path"], P[a]["pieces"]):
                retile[(a, b)] = t
    recs, done = [], set()
    for (a, b), t in retile.items():
        ga, gb = grid_score(P[a]), grid_score(P[b])
        undecided = False
        if (b, a) in retile:
            if gb > ga + 0.3:
                continue                                  # recorded from the other side
            undecided = not (ga > gb + 0.3)
        recs.append({"a": a, "b": b, "kind": "retile", "complete": not undecided, "pieces": t["pieces"],
                     "matched": t["matched"], "area_frac": round(t["area_frac"], 4),
                     "maps": {"grid": [round(ga, 2), round(gb, 2)]}, "n_b": len(P[b]["pieces"]),
                     "undecided": undecided, "n_scenes_b": len(P[b]["scenes"]),
                     "n_scenes_a": len(P[a]["scenes"])})
        if not undecided:
            done.add((a, b))
    return recs, done


def group_relations(ms, out, exhaustive=False):
    """Pixel relations between the members of one group.

    `ms` are members.csv rows with `feat` (features row) added. Returns a list of records
    {a, b, kind (hash | crop | stitch), complete, ...}: A is contained in B (a stitch record: A is the
    stitched copy of the tiled B). The cheap hash test runs on every ordered pair; the crop and stitch
    tests run on pairs that pass their gates (or on every pair with `exhaustive`, used to validate the
    gates on a sample of groups)."""
    P = {m["acq_id"]: load_pieces(out, m["sha256"], m["staged_path"]) for m in ms}
    bidx = {i: index_by_hash(p) for i, p in P.items()}
    rels = []
    done_complete = set()
    hres = {}
    for ma in ms:
        for mb in ms:
            a, b = ma["acq_id"], mb["acq_id"]
            if a == b:
                continue
            h = hres[(a, b)] = hash_match(P[a], P[b], bidx[b])
            if h["complete"] and not informative(ma["staged_path"], P[a]["pieces"]):
                h = dict(h, complete=False, weak=True)       # only blank tiles match: proves nothing
                hres[(a, b)] = h
            if h["matched"]:
                rels.append({"a": a, "b": b, "kind": "hash", "complete": h["complete"], "pieces": h["pieces"],
                             "weak": bool(h.get("weak")),
                             "matched": h["matched"], "area_frac": round(h["area_frac"], 4),
                             "maps": h["maps"], "n_b": len(P[b]["pieces"]),
                             "scenes_b": sorted({v["to_scene"] for v in h["maps"].values() if "to_scene" in v}),
                             "n_scenes_b": len(P[b]["scenes"]), "n_scenes_a": len(P[a]["scenes"])})
                if h["complete"]:
                    done_complete.add((a, b))
    recs, done = retile_records(ms, P, done_complete)
    rels.extend(recs)
    done_complete |= done
    # pairs that the crop and stitch tests below fully explain are not trimmed-tile candidates: run those
    # tests first, then the trim test on whatever is left (see the end of this function)
    for ma in ms:
        for mb in ms:
            a, b = ma["acq_id"], mb["acq_id"]
            if a == b or (a, b) in done_complete or (b, a) in done_complete:
                continue
            if exhaustive or crop_gate(ma["feat"], mb["feat"], P[a], P[b]):
                if len(P[a]["scenes"]) == 1:        # a crop is one image; a multi-scene file is a copy/split
                    hm = next(iter(hres[(a, b)]["maps"].values()), {})
                    hint = (hm["to_scene"], hm["dx"], hm["dy"]) if "to_scene" in hm else None
                    c = crop_match(P[a], P[b], ma["staged_path"], mb["staged_path"], hint=hint)
                    if c["matched"]:
                        rels.append({"a": a, "b": b, "kind": "crop", "complete": c["complete"],
                                     "pieces": c["pieces"], "matched": c["matched"],
                                     "area_frac": round(c["area_frac"], 4), "maps": c["maps"],
                                     "n_b": len(P[b]["pieces"]), "n_scenes_b": len(P[b]["scenes"]),
                                     "n_scenes_a": len(P[a]["scenes"])})
                        if c["complete"]:
                            continue
            if exhaustive or stitch_gate(ma["feat"], mb["feat"], P[a], P[b]):
                s = stitch_match(P[a], P[b], ma["staged_path"], mb["staged_path"])
                if s["found"]:
                    rels.append({"a": a, "b": b, "kind": "stitch", "complete": s["complete"],
                                 "pieces": s["sampled"], "matched": s["found"],
                                 "area_frac": round(s["found"] / max(s["sampled"], 1), 4),
                                 "maps": {"shifts": s["shifts"][:8]}, "n_b": len(P[b]["pieces"]),
                                 "n_scenes_b": len(P[b]["scenes"]), "n_scenes_a": len(P[a]["scenes"])})
    complete_now = {(r["a"], r["b"]) for r in rels if r["complete"]}
    rels.extend(trim_records(ms, P, complete_now | done_complete, exhaustive=exhaustive))
    complete_now = {(r["a"], r["b"]) for r in rels if r["complete"]}
    rels.extend(region_records(ms, P, complete_now | done_complete, exhaustive=exhaustive))
    return rels


# ---------------------------------------------------------------------------------------------
# 6. from relations to classes (pure: nodes and relation records in, a class per member out)
# ---------------------------------------------------------------------------------------------

C_ORIGINAL = "original"
C_DISTINCT = "distinct"
C_SCALEBAR = "scale-bar copy"
C_RESAVE = "identical re-save"
C_CROP = "export: crop"
C_SUBSET = "export: subset"
C_SPLIT = "scene split"
C_STITCHED = "stitched copy"
C_RENDER = "export: rendering"
C_AMBIGUOUS = "ambiguous"
DERIVATIVE_CLASSES = (C_SCALEBAR, C_RESAVE, C_CROP, C_SUBSET, C_SPLIT, C_STITCHED, C_RENDER)
LIST_A = (C_SCALEBAR,)                     # pixel-identical to the original, with a scale bar
LIST_R = (C_RESAVE,)                       # pixel-identical to the original, renamed re-save
LIST_B = (C_CROP, C_SUBSET)                # smaller: a crop or a subset of the original
SMALL_EXPORT = 0.05                        # an export under 5% of the original's size is list b;
                                           # a larger crop (an ROI re-save) is list k, for its own decision
# Ryan decides: scene splits, stitched copies, and renderings (an 8-bit RGB rendering of a 16-bit image:
# its pixels are derived, but equal only by correlation, never byte for byte)
PROPOSAL_C = (C_SPLIT, C_STITCHED, C_RENDER)

BITS = {"Gray8": 8, "Bgr24": 8, "Gray16": 16, "Bgr48": 16}


def copy_like(n):
    """The file looks like a made-from-another copy: a scale-bar overlay in its XML, or 'scale' in its name."""
    low = n["name"].lower()
    return bool(n.get("scalebar")) or any(w in low for w in SCALE_WORDS)


def rank_key(n):
    """Which of several pixel-identical files is the one to call the original (smaller sorts first):
    one that is not copy-like, then one with a project, then the earliest CreationDate, then the
    shorter and alphabetically first name."""
    cd = n.get("creation")
    return (1 if copy_like(n) else 0, 0 if n.get("project") else 1,
            cd.timestamp() if cd else float("inf"), len(n["name"]), n["name"])


def _edge_kind(r):
    """The relation type of a complete record 'A is contained in B'."""
    if r["kind"] in ("stitch", "retile", "retrim"):
        return "stitched"
    if r["kind"] in ("crop", "region"):
        return "crop"
    covered = len(r.get("scenes_b") or [])
    if r.get("n_scenes_b", 1) > 1 and 0 < covered < r["n_scenes_b"]:
        return "split"          # A holds some of B's scenes
    if r["n_b"] > r["pieces"]:
        return "subset"         # same scenes, fewer tiles (a time point, a channel)
    return "identical"


EDGE_RANK = {"identical": 0, "crop": 1, "subset": 2, "split": 3, "stitched": 4}


def compose(kinds):
    """The relation to the root along a chain of contained-in steps."""
    for k in ("stitched", "split", "crop", "subset"):
        if k in kinds:
            return k
    return "identical"


def evidence_text(rec, parent_name):
    if rec["kind"] == "hash":
        return f"{rec['matched']}/{rec['pieces']} tiles byte-identical to tiles of {parent_name}"
    if rec["kind"] == "crop":
        m = next(iter(rec["maps"].values()), {})
        return (f"{rec['matched']}/{rec['pieces']} tiles are byte-exact sub-rectangles of tiles of "
                f"{parent_name}, one offset ({m.get('dx')}, {m.get('dy')})")
    if rec["kind"] == "region":
        m = rec.get("maps", {})
        return (f"all its pixels equal {parent_name}'s at one offset ({m.get('dx')}, {m.get('dy')}), byte for byte "
                f"({rec['pieces']} blocks; they are the crop's own, not the original's, so no block is a piece of one)")
    if rec["kind"] == "retrim":
        m = rec.get("maps", {})
        return (f"all {rec['pieces']} tiles are byte-exact sub-rectangles of tiles of {parent_name}, each at its own "
                f"offset ({m.get('distinct_shifts', '?')} different offsets: stitching trimmed and re-placed them)")
    if rec["kind"] == "retile":
        g = rec.get("maps", {}).get("grid", ["?", "?"])
        return (f"all {rec['pieces']} tiles are byte-identical to tiles of {parent_name} but sit at positions no "
                f"single offset explains (stitching re-placed them; tile-position irregularity {g[0]} vs {g[1]} "
                f"for the original)")
    return (f"{rec['matched']}/{rec['pieces']} sampled tile interiors of {parent_name} found byte for byte "
            f"in it (stitched: tiles re-placed)")


def classify_group(nodes, rels):
    """Classify every member of one group.

    nodes: dicts with id, name, project (name or ''), scalebar (bool), creation (datetime or None).
    rels: records from group_relations. Returns {id: {class, parent, via, evidence}} where `parent`
    is the original the member is derived from (None for an original / distinct member).

    A member is derived when its pixels are contained, byte for byte, in another member's. Members
    that contain each other (identical pixels) are one equivalence class; the original of a class is
    chosen by rank_key. A class contained in no other class is a root; a root with derivatives (or
    pixel-identical twins) is `original`, a lone root in a group with several roots is `distinct` (a
    sibling scene of an acquisition whose master is not on the drive)."""
    by = {n["id"]: n for n in nodes}
    comp = [r for r in rels if r["complete"]]
    hc = {(r["a"], r["b"]): r for r in comp if r["kind"] == "hash"}
    uf = {i: i for i in by}

    def find(x):
        while uf[x] != x:
            uf[x] = uf[uf[x]]
            x = uf[x]
        return x

    for (a, b) in hc:
        if (b, a) in hc:
            uf[find(a)] = find(b)
    cid = {i: find(i) for i in by}
    classes = collections.defaultdict(list)
    for i in by:
        classes[cid[i]].append(i)
    rep = {c: min(ms, key=lambda i: rank_key(by[i])) for c, ms in classes.items()}
    # edges between different classes: class -> [(target class, kind, record)]
    edges = collections.defaultdict(list)
    for r in comp:
        if cid[r["a"]] != cid[r["b"]]:
            edges[cid[r["a"]]].append((cid[r["b"]], _edge_kind(r), r))
    roots = {c for c in classes if not edges.get(c)}

    def paths_to_roots(c):
        """{root class: shortest chain of (kind, record) from class c}."""
        found, queue, seen = {}, collections.deque([(c, [])]), {c}
        while queue:
            cur, chain = queue.popleft()
            if cur in roots:
                found.setdefault(cur, chain)
                continue
            for (nb, kind, rec) in edges[cur]:
                if nb not in seen or nb in roots:
                    seen.add(nb)
                    queue.append((nb, chain + [(kind, rec)]))
        return found

    out = {}
    has_derivative = set()
    reach = {c: paths_to_roots(c) for c in classes if c not in roots}
    for c, pr in reach.items():
        has_derivative.update(pr)
    for c, members in classes.items():
        if c in roots:
            twins = len(members) > 1
            for m in members:
                if m == rep[c]:
                    cls = C_ORIGINAL if (c in has_derivative or twins or len(roots) == 1) else C_DISTINCT
                    out[m] = {"class": cls, "parent": None, "via": "",
                              "evidence": ("pixel-identical twins: " + ", ".join(
                                  by[x]["name"] for x in members if x != m)) if twins else ""}
                else:
                    r = hc.get((m, rep[c]))
                    out[m] = {"class": C_SCALEBAR if by[m].get("scalebar") else C_RESAVE, "parent": rep[c],
                              "via": "identical",
                              "evidence": evidence_text(r, by[rep[c]]["name"]) if r else ""}
            continue
        pr = reach[c]
        for m in members:
            if len(pr) != 1:
                names = ", ".join(sorted(by[rep[rc]]["name"] for rc in pr)) or "none"
                out[m] = {"class": C_AMBIGUOUS, "parent": None, "via": "",
                          "evidence": f"contained in {len(pr)} unrelated members: {names}"}
                continue
            rc, chain = next(iter(pr.items()))
            # the member's own direct edge to the root, if it has one (the best kind among them)
            direct = [(EDGE_RANK[k], k, r) for (nb, k, r) in edges[c] if nb == rc and r["a"] == m]
            if direct:
                _, kind, rec = min(direct, key=lambda t: t[0])
                via, ev = kind, evidence_text(rec, by[rep[rc]]["name"])
            else:
                # no relation of its own to the root: it is contained in another derivative, which is
                # contained in the root. Say so with the member's own first relation.
                kind = compose([k for (k, _r) in chain])
                first_kind, first = chain[0]
                own = [(EDGE_RANK[k], r) for (nb, k, r) in edges[c] if nb == cid[first["b"]] and r["a"] == m]
                if own:
                    first = min(own, key=lambda t: t[0])[1]
                mid = by[first["b"]]["name"]
                via = f"{kind} (through {mid})"
                ev = evidence_text(first, mid)
                if len(chain) > 1:
                    ev += f"; {mid} is in turn {chain[1][0]} of {by[rep[rc]]['name']}"
            if kind == "identical":
                cls = C_SCALEBAR if by[m].get("scalebar") else C_RESAVE
            else:
                cls = {"crop": C_CROP, "subset": C_SUBSET, "split": C_SPLIT, "stitched": C_STITCHED}[kind]
            out[m] = {"class": cls, "parent": rep[rc], "via": via, "evidence": ev}
    # a root member with only a partial relation is not 'distinct' or 'original': say so
    partial = collections.defaultdict(list)
    complete_pairs = {(r["a"], r["b"]) for r in comp}
    for r in rels:
        # a partial hit between files that are fully related (either way) is just the container's
        # share of the contained file; only a partial relation with no complete one is a finding
        if (not r["complete"] and r.get("area_frac", 0) >= 0.5
                and (r["a"], r["b"]) not in complete_pairs and (r["b"], r["a"]) not in complete_pairs):
            partial[r["a"]].append(r)
    for m, rs in partial.items():
        if out[m]["class"] in (C_DISTINCT, C_ORIGINAL):
            best = max(rs, key=lambda r: r["area_frac"])
            why = ("; the matching tiles carry no image content (blank), so it proves nothing"
                   if best.get("weak") else
                   "; the same tiles at different positions, and the grids do not say which is the acquisition's own"
                   if best.get("undecided") else " (not complete)")
            out[m] = {"class": C_AMBIGUOUS, "parent": None, "via": "",
                      "evidence": (f"{best['kind']} match covers {best['area_frac']:.0%} of its "
                                   f"{'pixels' if best['kind'] == 'region' else 'tiles'} inside "
                                   f"{by[best['b']]['name']}{why}")}
    return out


# ---------------------------------------------------------------------------------------------
# 7. the commands that run the relations, classify, and write the lists
# ---------------------------------------------------------------------------------------------

def load_members_with_features(out):
    mem = rcsv(os.path.join(out, "members.csv"))
    feats = {r["sha256"]: r for r in rcsv(os.path.join(out, "features.csv"))}
    for m in mem:
        m["feat"] = feats[m["sha256"]]
    return mem


def groups_of(mem):
    g = collections.defaultdict(list)
    for m in mem:
        g[m["group"]].append(m)
    return dict(sorted(g.items()))


def cmd_relations(args):
    mem = load_members_with_features(args.out)
    groups = groups_of(mem)
    rdir = os.path.join(args.out, "relations")
    os.makedirs(rdir, exist_ok=True)
    keys = list(groups)
    sib = sibling_group_keys(mem)
    t0 = time.time()
    todo = []
    only = [x for x in (args.only or "").split(",") if x]
    for gi, k in enumerate(keys):
        f = os.path.join(rdir, f"{gi:03d}.json")
        if only and not any(k.startswith(x) for x in only):
            continue
        if os.path.exists(f) and not args.redo:
            continue
        if not all(os.path.exists(pieces_cache_path(args.out, m["sha256"])) for m in groups[k]):
            if k in sib:
                # different stage positions throughout: related by no gate, tiles deliberately not read
                with io.open(f, "w", encoding="utf-8") as fh:
                    json.dump({"group": k, "ids": [m["acq_id"] for m in groups[k]], "rels": [],
                               "gate": "sibling: distinct stage positions, tiles not read"}, fh)
            continue                              # else: tile cache not finished for this group yet
        todo.append((gi, k, f))
    print(f"{len(keys)} groups, {len(todo)} to do now")
    errs = []

    def one(item):
        gi, k, f = item
        ms = groups[k]
        rels = group_relations(ms, args.out, exhaustive=args.exhaustive)
        tmp = f + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"group": k, "ids": [m["acq_id"] for m in ms], "rels": rels, "retile_checked": True,
                           "stitch_version": 2, "trim_checked": True, "region_checked": True}, fh)
        os.replace(tmp, f)
        return gi

    done = 0
    with cf.ThreadPoolExecutor(args.workers) as ex:
        futs = {ex.submit(one, it): it for it in todo}
        for fut in cf.as_completed(futs):
            gi, k, f = futs[fut]
            try:
                fut.result()
            except Exception as e:     # counted, reported, non-zero exit
                errs.append((k, f"{type(e).__name__}: {e}"))
            done += 1
            if done % 10 == 0 or done == len(todo):
                print(f"  {done}/{len(todo)} groups, {time.time() - t0:.0f}s, {len(errs)} errors", flush=True)
    for k, e in errs:
        print("  ERROR:", k, e)
    return 1 if errs else 0


def cmd_retile(args):
    """Add the re-placed-tiles records (retile_records) to the relation files made before that test
    existed. Cheap: tile payload hashes only, plus one tile read per member. Idempotent."""
    mem = load_members_with_features(args.out)
    groups = groups_of(mem)
    rdir = os.path.join(args.out, "relations")
    n = added = 0
    for gi, k in enumerate(groups):
        f = os.path.join(rdir, f"{gi:03d}.json")
        if not os.path.exists(f):
            continue
        with io.open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        if d.get("retile_checked") or d.get("gate"):
            continue
        ms = groups[k]
        if not all(os.path.exists(pieces_cache_path(args.out, m["sha256"])) for m in ms):
            continue
        P = {m["acq_id"]: load_pieces(args.out, m["sha256"], m["staged_path"]) for m in ms}
        complete_pairs = {(r["a"], r["b"]) for r in d["rels"] if r["complete"]}
        recs, _done = retile_records(ms, P, complete_pairs)
        d["rels"].extend(recs)
        d["retile_checked"] = True
        tmp = f + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as fh:
            json.dump(d, fh)
        os.replace(tmp, f)
        n += 1
        added += len(recs)
    print(f"retile: {n} relation files updated, {added} records added")
    return 0


def cmd_restitch(args):
    """Re-run the stitched-interiors test (stitch_match, version 2: blank tiles skipped, half the tested
    tiles is enough) on every gated pair of the relation files made with version 1. Replaces the stitch
    records of those pairs. Idempotent."""
    mem = load_members_with_features(args.out)
    groups = groups_of(mem)
    rdir = os.path.join(args.out, "relations")
    n = pairs = 0
    t0 = time.time()
    for gi, k in enumerate(groups):
        f = os.path.join(rdir, f"{gi:03d}.json")
        if not os.path.exists(f):
            continue
        with io.open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        if d.get("stitch_version") == 2 or d.get("gate"):
            continue
        ms = groups[k]
        if not all(os.path.exists(pieces_cache_path(args.out, m["sha256"])) for m in ms):
            continue
        P = {m["acq_id"]: load_pieces(args.out, m["sha256"], m["staged_path"]) for m in ms}
        complete_pairs = {(r["a"], r["b"]) for r in d["rels"] if r["complete"] and r["kind"] != "stitch"}
        keep = [r for r in d["rels"] if r["kind"] != "stitch"]
        for ma in ms:
            for mb in ms:
                a, b = ma["acq_id"], mb["acq_id"]
                if a == b or (a, b) in complete_pairs or (b, a) in complete_pairs:
                    continue
                if not stitch_gate(ma["feat"], mb["feat"], P[a], P[b]):
                    continue
                pairs += 1
                s_ = stitch_match(P[a], P[b], ma["staged_path"], mb["staged_path"])
                if s_["found"]:
                    keep.append({"a": a, "b": b, "kind": "stitch", "complete": s_["complete"],
                                 "pieces": s_["sampled"], "matched": s_["found"],
                                 "area_frac": round(s_["found"] / max(s_["sampled"], 1), 4),
                                 "maps": {"shifts": s_["shifts"][:8]}, "n_b": len(P[b]["pieces"]),
                                 "n_scenes_b": len(P[b]["scenes"]), "n_scenes_a": len(P[a]["scenes"])})
        d["rels"], d["stitch_version"] = keep, 2
        tmp = f + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as fh:
            json.dump(d, fh)
        os.replace(tmp, f)
        n += 1
        print(f"  group {gi:03d} {k[:26]}: done ({time.time() - t0:.0f}s)", flush=True)
    print(f"restitch: {n} relation files, {pairs} gated pairs tested")
    return 0


def cmd_retrim(args):
    """Add the re-trimmed-tiles records (trim_records) to the relation files made before that test existed.
    Reads the tiles of the pairs it tests. Idempotent (marks the file `trim_checked`)."""
    mem = load_members_with_features(args.out)
    groups = groups_of(mem)
    rdir = os.path.join(args.out, "relations")
    n = added = 0
    t0 = time.time()
    for gi, k in enumerate(groups):
        f = os.path.join(rdir, f"{gi:03d}.json")
        if not os.path.exists(f):
            continue
        with io.open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        if d.get("trim_checked") or d.get("gate"):
            continue
        ms = groups[k]
        if not all(os.path.exists(pieces_cache_path(args.out, m["sha256"])) for m in ms):
            continue
        P = {m["acq_id"]: load_pieces(args.out, m["sha256"], m["staged_path"]) for m in ms}
        complete_pairs = {(r["a"], r["b"]) for r in d["rels"] if r["complete"]}
        recs = trim_records(ms, P, complete_pairs)
        d["rels"] = [r for r in d["rels"] if r["kind"] != "retrim"] + recs
        d["trim_checked"] = True
        tmp = f + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as fh:
            json.dump(d, fh)
        os.replace(tmp, f)
        n += 1
        added += len(recs)
        if recs:
            print(f"  group {gi:03d} {k[:26]}: {len(recs)} records ({time.time() - t0:.0f}s)", flush=True)
    print(f"retrim: {n} relation files checked, {added} records added")
    return 0


def cmd_region(args):
    """Add the re-blocked-crop records (region_records) to the relation files made before that test existed.
    Reads the tiles of the pairs it tests (few: only members still unrelated to everything). Idempotent
    (marks the file `region_checked`)."""
    mem = load_members_with_features(args.out)
    groups = groups_of(mem)
    rdir = os.path.join(args.out, "relations")
    n = added = 0
    t0 = time.time()
    for gi, k in enumerate(groups):
        f = os.path.join(rdir, f"{gi:03d}.json")
        if not os.path.exists(f):
            continue
        with io.open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        if d.get("region_checked") or d.get("gate"):
            continue
        ms = groups[k]
        if not all(os.path.exists(pieces_cache_path(args.out, m["sha256"])) for m in ms):
            continue
        P = {m["acq_id"]: load_pieces(args.out, m["sha256"], m["staged_path"]) for m in ms}
        complete_pairs = {(r["a"], r["b"]) for r in d["rels"] if r["complete"]}
        recs = region_records(ms, P, complete_pairs)
        d["rels"] = [r for r in d["rels"] if r["kind"] != "region"] + recs
        d["region_checked"] = True
        tmp = f + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as fh:
            json.dump(d, fh)
        os.replace(tmp, f)
        n += 1
        added += len(recs)
        if recs:
            print(f"  group {gi:03d} {k[:26]}: {len(recs)} records ({time.time() - t0:.0f}s)", flush=True)
    print(f"region: {n} relation files checked, {added} records added")
    return 0


def cmd_validate(args):
    """Validate the crop/stitch gates: on a sample of groups where the gates skipped every pair (stage
    positions that never coincide), run the crop and stitch tests on ALL pairs; any complete relation
    this finds that the gated run did not is a gate false negative."""
    mem = load_members_with_features(args.out)
    groups = groups_of(mem)
    rels = load_relations(args.out)
    cands = []
    for k, ms in groups.items():
        if k not in rels or any(r["complete"] for r in rels[k]) or len(ms) < 2:
            continue
        cs = [scene_centers(m["feat"]) for m in ms]
        if not all(cs) or any(a & b for i, a in enumerate(cs) for b in cs[i + 1:]):
            continue                      # a member without a stage position, or two that coincide: not gated out
        cands.append((sum(int(m["size"]) for m in ms), k))
    cands.sort()
    cands = [c for c in cands if c[0] <= args.max_gb * 1e9]
    step = max(1, len(cands) // args.sample)
    chosen = [k for _, k in cands[::step][:args.sample]]
    print(f"{len(cands)} gated-out groups under {args.max_gb} GB; validating {len(chosen)}")
    out = []
    for k in chosen:
        ms = groups[k]
        t0 = time.time()
        ex = group_relations(ms, args.out, exhaustive=True)
        found = [r for r in ex if r["complete"]]
        out.append({"group": k, "members": [m["name"] for m in ms], "gb": sum(int(m["size"]) for m in ms) / 1e9,
                    "complete_found": [(r["kind"], r["a"], r["b"]) for r in found],
                    "partial": [(r["kind"], r["a"], r["b"], r["area_frac"]) for r in ex if not r["complete"]]})
        print(f"  {k[:30]}  n={len(ms)}  {out[-1]['gb']:.1f} GB  complete relations found: {len(found)}  ({time.time() - t0:.0f}s)", flush=True)
    with io.open(os.path.join(args.out, "gate_validation.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    miss = sum(len(o["complete_found"]) for o in out)
    print(f"gate false negatives: {miss} in {len(out)} groups")
    return 1 if miss else 0


def load_relations(out):
    rdir = os.path.join(out, "relations")
    res = {}
    for f in sorted(os.listdir(rdir)):
        if f.endswith(".json"):
            with io.open(os.path.join(rdir, f), encoding="utf-8") as fh:
                d = json.load(fh)
            res[d["group"]] = d["rels"]
    return res


CLASS_COLS = ["group", "group_n", "acq_id", "name", "folder", "drive", "size", "instrument", "acquisition_datetime",
              "size_x", "size_y", "scenes", "channels", "tiles", "pyramid", "pixel_type",
              "class", "parent_acq_id", "parent_name", "via", "evidence", "own_project", "parent_project",
              "parent_project_status", "has_scalebar", "creation_date", "action", "action_note"]


def dims_columns(f):
    """The dimension columns of the group table, from a features row."""
    return {"size_x": f.get("SizeX", ""), "size_y": f.get("SizeY", ""),
            "scenes": len([x for x in (f.get("scenes_dir") or "").split(";") if x]),
            "channels": f.get("SizeC", ""), "tiles": f.get("n_level0", ""),
            "pyramid": "Y" if int(f.get("n_entries") or 0) > int(f.get("n_level0") or 0) else "N",
            "pixel_type": f.get("PixelType", "")}


def decide_action(m, c, parent, projects_status):
    """What the class means for the retire lists: ('a'|'r'|'b'|'k'|'c'|'stay'|'waiting'|'conflict'|'closed', note):
    a = scale-bar copy, r = identical re-save, b = small export (crop/subset under 5% of the original),
    k = larger crop/subset (an ROI re-save), c = Ryan's proposal (splits, stitched, renderings)."""
    cls = c["class"]
    if cls not in DERIVATIVE_CLASSES:
        return "stay", ""
    pp = parent["project_name"]
    if cls in PROPOSAL_C:
        return "c", ("" if pp else "original has no project")
    if not pp:
        return "waiting", "original has no project: waits for the no-project mapping round (plan item 2b)"
    if m["project_name"] and m["project_name"] != pp:
        return "conflict", f"its own project {m['project_name']} differs from the original's {pp}"
    if projects_status.get(pp) == "closed":
        return "closed", f"project {pp} is closed: reopen it first"
    if cls in LIST_A:
        return "a", ""
    if cls in LIST_R:
        return "r", ""
    small = int(m["size"]) < SMALL_EXPORT * int(parent["size"])
    return ("b" if small else "k"), ""


ID65 = "ID65_PB_lung_20x_scale.czi"


def id65_row(projects):
    """The one file the BACKLOG names that has no group flag. Its timestamp is unique in the plan AND in
    production (any instrument), so no other record of the acquisition exists: the file is the
    acquisition, its scale bar a metadata overlay. It is not a copy of anything, so it stays."""
    reg = rcsv(os.path.join(NAS, "registries", "registry_raw.csv"))
    hit = [r for r in reg if r["original_name"].endswith("/" + ID65)]
    if len(hit) != 1:
        raise SystemExit(f"{ID65}: {len(hit)} registry rows")
    r = hit[0]
    ts = r["acquisition_datetime"][:19]
    same_ts = [x["acq_id"] for x in reg if x["acquisition_datetime"][:19] == ts]
    pid = {x["project_id"]: x["name"] for x in rcsv(os.path.join(NAS, "registries", "registry_projects.csv"))}
    return {"group": "(no group flag)", "group_n": "", "acq_id": r["acq_id"], "name": ID65,
            "folder": dirname(r["original_name"]), "drive": "D1", "size": str(int(float(r["file_size_mb"]) * 1e6)),
            "instrument": r["instrument"], "acquisition_datetime": r["acquisition_datetime"],
            "class": C_ORIGINAL, "parent_acq_id": "", "parent_name": "", "via": "",
            "evidence": (f"no other record of this acquisition: {len(same_ts)} registry row at {ts} (any instrument), "
                         "no file of the same name without _scale on either drive; a ScaleBar overlay is in its XML, "
                         "90 tiles, written at the end of the scan"),
            "own_project": pid.get(r["project_id"], ""), "parent_project": "", "parent_project_status": "",
            "has_scalebar": "True", "creation_date": "", "action": "stay",
            "action_note": "NOT a copy: it is the only record of the ID65 acquisition (BACKLOG expected a scale-bar copy)"}


def similarity_pass(ms, cl, out):
    """Roots of a group that are the same size but share no tile: are they one image rendered twice?

    For every such pair (small files only) the rank correlation of the image planes is computed. At 0.98 or
    more, the file with the lower bit depth (an 8-bit RGB rendering of a 16-bit image) is an `export:
    rendering` of the other, whose class becomes `original`. From 0.90, both are `ambiguous` (the same
    image, differently processed, and nothing says which is the acquisition). Below that, the evidence
    just records the numbers. Changes `cl` in place."""
    roots = [m for m in ms if cl[m["acq_id"]]["class"] in (C_DISTINCT, C_ORIGINAL)]
    for i, m in enumerate(roots):
        for o in roots[i + 1:]:
            cm, co = cl[m["acq_id"]], cl[o["acq_id"]]
            if cm["class"] == C_ORIGINAL and co["class"] == C_ORIGINAL:
                continue
            if not m["feat"]["SizeX"] or (m["feat"]["SizeX"], m["feat"]["SizeY"]) != (o["feat"]["SizeX"], o["feat"]["SizeY"]):
                continue
            bm, bo = BITS.get(m["feat"]["PixelType"], 0), BITS.get(o["feat"]["PixelType"], 0)
            lo, hi = (m, o) if bm < bo else (o, m)
            Fm = load_pieces(out, m["sha256"], m["staged_path"])
            Fo = load_pieces(out, o["sha256"], o["staged_path"])
            s1 = pair_similarity(m["staged_path"], Fm, o["staged_path"], Fo)
            s2 = pair_similarity(o["staged_path"], Fo, m["staged_path"], Fm)
            if not s1 or not s2:
                continue
            rho = min(s1[0], s2[0]) if bm == bo else (s1[0] if lo is m else s2[0])
            note = (f"same dimensions as {{other}}; rank correlation of the image planes {rho:.2f}")
            if rho >= 0.98 and bm != bo:
                cl[lo["acq_id"]] = {"class": C_RENDER, "parent": hi["acq_id"], "via": "rendering",
                                    "evidence": (note.format(other=hi["name"]) + f": a {BITS[lo['feat']['PixelType']]}-bit "
                                                 f"rendering of the {BITS[hi['feat']['PixelType']]}-bit image (pixel values "
                                                 "are display-mapped, so not byte-identical)")}
                if cl[hi["acq_id"]]["class"] == C_DISTINCT:
                    cl[hi["acq_id"]] = {"class": C_ORIGINAL, "parent": None, "via": "", "evidence": ""}
            elif rho >= 0.90:
                for x, y in ((m, o), (o, m)):
                    if cl[x["acq_id"]]["class"] == C_DISTINCT:
                        cl[x["acq_id"]] = {"class": C_AMBIGUOUS, "parent": None, "via": "",
                                           "evidence": note.format(other=y["name"])
                                           + ": the same image processed differently, not byte-identical; "
                                             "nothing says which is the acquisition"}
            else:
                for x, y in ((m, o), (o, m)):
                    if cl[x["acq_id"]]["class"] == C_DISTINCT and not cl[x["acq_id"]]["evidence"]:
                        cl[x["acq_id"]]["evidence"] = note.format(other=y["name"]) + ": unrelated content"


def cmd_classify(args):
    mem = load_members_with_features(args.out)
    groups = groups_of(mem)
    rels = load_relations(args.out)
    missing = [k for k in groups if k not in rels]
    if missing and not args.allow_missing:
        print(f"{len(missing)} groups have no relations yet; run `relations` first", file=sys.stderr)
        return 1
    if missing:
        print(f"PREVIEW: {len(missing)} groups without relations are left out", file=sys.stderr)
    projects = {r["name"]: r["status"] for r in rcsv(os.path.join(NAS, "registries", "registry_projects.csv"))}
    sibling = sibling_group_keys(mem)
    rows = []
    weak_checked = {}
    for k, ms in groups.items():
        if k not in rels:
            continue
        nodes = []
        for m in ms:
            f = m["feat"]
            nodes.append({"id": m["acq_id"], "name": m["name"], "project": m["project_name"],
                          "scalebar": f.get("has_scalebar") == "True", "creation": parse_dt(f.get("CreationDate"))})
        byid = {m["acq_id"]: m for m in ms}
        for r in rels[k]:
            # a whole-tile match made only of blank tiles proves nothing (relations run before this guard
            # existed did not apply it): demote it
            if r["kind"] == "hash" and r["complete"] and not r.get("weak"):
                a = byid[r["a"]]
                if a["acq_id"] not in weak_checked:
                    weak_checked[a["acq_id"]] = informative(
                        a["staged_path"], load_pieces(args.out, a["sha256"], a["staged_path"])["pieces"])
                if not weak_checked[a["acq_id"]]:
                    r["complete"], r["weak"] = False, True
        cl = classify_group(nodes, rels[k])
        if k not in sibling:
            similarity_pass(ms, cl, args.out)
        for m in ms:
            c = cl[m["acq_id"]]
            if c["class"] == C_DISTINCT and not c["evidence"]:
                c["evidence"] = (
                    "a different stage position from every other member (XML scene centre); tiles not compared"
                    if k in sibling else
                    "no tile of it is in another member and no tile of another member is in it")
            parent = byid.get(c["parent"]) if c["parent"] else None
            action, note = decide_action(m, c, parent, projects) if parent else \
                ("stay", "") if c["class"] != C_AMBIGUOUS else ("stay", "ambiguous: stays in /raw/")
            rows.append({"group": k, "group_n": m["group_n"], "acq_id": m["acq_id"], "name": m["name"],
                         "folder": m["folder"], "drive": m["drive"], "size": m["size"],
                         "instrument": m["instrument"], "acquisition_datetime": m["acquisition_datetime"],
                         **dims_columns(m["feat"]),
                         "class": c["class"], "parent_acq_id": c["parent"] or "",
                         "parent_name": parent["name"] if parent else "", "via": c["via"],
                         "evidence": c["evidence"], "own_project": m["project_name"],
                         "parent_project": parent["project_name"] if parent else "",
                         "parent_project_status": projects.get(parent["project_name"], "") if parent else "",
                         "has_scalebar": m["feat"].get("has_scalebar", ""), "creation_date": m["feat"].get("CreationDate", ""),
                         "action": action, "action_note": note})
    rows.append(id65_row(projects))
    wcsv(os.path.join(args.out, "classified.csv"), CLASS_COLS, rows)
    cnt = collections.Counter(r["class"] for r in rows)
    print("classes:", dict(cnt))
    print("actions:", dict(collections.Counter(r["action"] for r in rows)))
    return 0


def reason_text(r):
    return (f"R4 group {r['group'].split('|')[0]} {r['group'].split('|')[1][:19]}: {r['class']} of "
            f"{r['parent_name']} ({r['parent_acq_id']}) -- {r['evidence']}")


def list_rows(classified, action):
    """Retire-list rows (acq_id, disposition, target_acq_id, to_project, reason, subfolder, dest_name) for
    the classified members whose action is `action`."""
    out = []
    for r in classified:
        if r["action"] != action:
            continue
        out.append({"acq_id": r["acq_id"], "disposition": "derivative", "target_acq_id": r["parent_acq_id"],
                    "to_project": r["parent_project"], "reason": reason_text(r),
                    "subfolder": subfolder_from_folder(r["folder"]), "dest_name": r["name"]})
    return out


LIST_COLS = ["acq_id", "disposition", "target_acq_id", "to_project", "reason", "subfolder", "dest_name"]
RESERVED = {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} | {f"lpt{i}" for i in range(1, 10)}


def path_issues(project, subfolder, name):
    """Things on the destination path that Windows / SMB / QNAP could refuse or mangle (empty when none):
    an illegal character, a trailing space or dot, a reserved device name, a component over 255
    characters, a total path over 600 (the NAS folder prefix included)."""
    issues = []
    comps = [c for c in subfolder.split("\\") if c] + [name]
    for c in comps:
        if any(ch in c for ch in '<>:"|?*'):
            issues.append(f"illegal character in {c!r}")
        if c != c.rstrip(" .") or c != c.lstrip(" "):
            issues.append(f"leading/trailing space or dot in {c!r}")
        if c.split(".")[0].lower() in RESERVED:
            issues.append(f"reserved name {c!r}")
        if len(c) > 255:
            issues.append(f"component over 255 characters: {c[:40]!r}...")
    total = len(NAS) + len("\\projects\\") + len(project) + 1 + len(subfolder) + 1 + len(name)
    if total > 600:
        issues.append(f"path of {total} characters")
    return issues


def write_list(path, rows):
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LIST_COLS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def cmd_lists(args):
    classified = rcsv(os.path.join(args.out, "classified.csv"))
    names = {"a": "2026-10_r4_scalebars.csv", "b": "2026-10_r4_exports.csv", "r": "2026-10_r4_resaves.csv",
             "k": "2026-10_r4_roi_crops.csv"}
    os.makedirs(args.lists_dir, exist_ok=True)
    held = []
    for action, fn in names.items():
        rows = list_rows(classified, action)
        keep = []
        for r in rows:
            iss = path_issues(r["to_project"], r["subfolder"], r["dest_name"])
            (held if iss else keep).append((r, iss) if iss else r)
        write_list(os.path.join(args.lists_dir, fn), keep)
        ids = {r["acq_id"] for r in keep}
        gb = sum(int(r["size"]) for r in classified if r["acq_id"] in ids) / 1e9
        # past the classic Windows limit of 259 characters (J:\gjesus3-data\projects\... form): the retire tool
        # uses long-path forms, but Explorer, Office and older tools on the lab's machines may not
        long_ = [r for r in keep if len(NAS) + len("\\projects\\") + len(r["to_project"]) + 1 + len(r["subfolder"]) + 1
                 + len(r["dest_name"]) > 259]
        print(f"{fn}: {len(keep)} rows, {gb:.1f} GB" + (f"; {len(long_)} destination path(s) over 259 characters" if long_ else ""))
        for r in long_:
            print(f"    over 259: {r['acq_id']} {r['dest_name']}")
    for r, iss in held:
        print(f"  HELD (path issue, not listed): {r['acq_id']} {r['dest_name']}: {'; '.join(iss)}")
    return 0


def cmd_verify_lists(args):
    """Read-only checks of the written lists against production, before any dry run: every retiree and
    original is live in registry_raw; the original's registry project is the row's `to_project`, active;
    the retiree's own project is blank or the same; no id is both retiree and original; and the SHA-256 in
    each acquisition's own checksums.json equals the staged file's (so the pixel check was made on the
    bytes that are in production)."""
    reg = {r["acq_id"]: r for r in rcsv(os.path.join(NAS, "registries", "registry_raw.csv"))}
    projs = {r["project_id"]: r for r in rcsv(os.path.join(NAS, "registries", "registry_projects.csv"))}
    mem = {m["acq_id"]: m for m in rcsv(os.path.join(args.out, "members.csv"))}
    bad = 0
    for fn in ("2026-10_r4_scalebars.csv", "2026-10_r4_exports.csv", "2026-10_r4_resaves.csv",
               "2026-10_r4_roi_crops.csv"):
        path = os.path.join(args.lists_dir, fn)
        rows = rcsv(path)
        retirees = {r["acq_id"] for r in rows}
        targets = {r["target_acq_id"] for r in rows}
        problems = []
        if retirees & targets:
            problems.append(f"ids both retiree and original: {sorted(retirees & targets)}")
        shas = 0
        for r in rows:
            a, t = reg.get(r["acq_id"]), reg.get(r["target_acq_id"])
            if not a or not t:
                problems.append(f"{r['acq_id']}: retiree or original not live")
                continue
            pt = projs.get(t["project_id"], {})
            if pt.get("name") != r["to_project"] or pt.get("status") != "active":
                problems.append(f"{r['acq_id']}: original's project is {pt.get('name')!r} ({pt.get('status')})")
            pa = projs.get(a["project_id"], {}).get("name", "")
            if pa and pa != r["to_project"]:
                problems.append(f"{r['acq_id']}: own project {pa} differs")
            for acq, row in ((r["acq_id"], a), (r["target_acq_id"], t)):
                cj = os.path.join(NAS, row["canonical_path"].strip("/").replace("/", "\\"), "checksums.json")
                with io.open(cj, encoding="utf-8") as f:
                    got = json.load(f)["files"].get(row["primary_file_name"])
                if got != mem[acq]["sha256"]:
                    problems.append(f"{acq}: production checksums.json {got} != staged {mem[acq]['sha256']}")
                else:
                    shas += 1
        print(f"{fn}: {len(rows)} rows, {len(targets)} originals, {shas} sha256 matches, {len(problems)} problems")
        for p in problems:
            print("   PROBLEM:", p)
        bad += len(problems)
    return 1 if bad else 0


def md_table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def cmd_report(args):
    """Markdown tables for the review doc, from classified.csv: counts and GB per class and per action."""
    rows = rcsv(os.path.join(args.out, "classified.csv"))
    grouped = [r for r in rows if r["group"] != "(no group flag)"]
    out = []

    def gb(rs):
        return f"{sum(int(r['size']) for r in rs) / 1e9:,.1f}"

    cls_order = [C_ORIGINAL, C_DISTINCT, C_SCALEBAR, C_RESAVE, C_CROP, C_SUBSET, C_SPLIT, C_STITCHED, C_RENDER,
                 C_AMBIGUOUS]
    t = []
    for c in cls_order:
        rs = [r for r in grouped if r["class"] == c]
        t.append((c, len(rs), gb(rs), len({r["group"] for r in rs}), sum(1 for r in rs if r["own_project"])))
    t.append(("**all**", len(grouped), gb(grouped), len({r["group"] for r in grouped}),
              sum(1 for r in grouped if r["own_project"])))
    out.append("### Members by class\n\n" + md_table(["class", "files", "GB", "groups", "files with a project"], t))
    acts = collections.OrderedDict([("a", "list (a): scale-bar copies"), ("r", "list (a2): identical re-saves"),
                                    ("b", "list (b): small exports (crops and subsets under 5% of the original)"),
                                    ("k", "list (b2): larger crops and subsets (ROI re-saves)"),
                                    ("c", "proposal (c): scene splits, stitched copies"),
                                    ("waiting", "derivative, original has no project"),
                                    ("conflict", "derivative's own project differs from the original's"),
                                    ("closed", "original's project is closed"), ("stay", "stays in /raw/")])
    t = []
    for a, lab in acts.items():
        rs = [r for r in grouped if r["action"] == a]
        t.append((lab, len(rs), gb(rs)))
    out.append("### What each class means for the lists\n\n" + md_table(["action", "files", "GB"], t))
    t = []
    for c in DERIVATIVE_CLASSES:
        row = [c]
        for a in ("a", "r", "b", "k", "c", "waiting", "conflict", "closed"):
            rs = [r for r in grouped if r["class"] == c and r["action"] == a]
            row.append(f"{len(rs)} ({gb(rs)} GB)" if rs else "-")
        t.append(row)
    out.append("### Derivatives: class x action\n\n" + md_table(
        ["class", "list a", "list a2", "list b", "list b2", "proposal c", "waiting (no project)", "conflict",
         "closed project"], t))
    t = []
    for a in ("a", "r", "b", "k"):
        byp = collections.defaultdict(list)
        for r in grouped:
            if r["action"] == a:
                byp[r["parent_project"]].append(r)
        for pn, rs in sorted(byp.items()):
            t.append((a, pn, len(rs), gb(rs)))
    out.append("### List rows by destination project\n\n" + md_table(["list", "project", "files", "GB"], t))
    # the groups whose original has no project but which hold derivatives: input of the no-project mapping round
    wait = collections.defaultdict(list)
    for r in grouped:
        if r["action"] in ("waiting", "c") and not r["parent_project"]:
            wait[(r["group"], r["parent_acq_id"], r["parent_name"])].append(r)
    byid = {r["acq_id"]: r for r in grouped}
    wrows = []
    for (g, pid, pname), rs in sorted(wait.items()):
        par = byid[pid]
        wrows.append({"group": g, "original_acq_id": pid, "original_name": pname, "instrument": par["instrument"],
                      "original_folder": par["folder"], "derivatives": len(rs),
                      "classes": "; ".join(f"{c} {n}" for c, n in sorted(collections.Counter(x["class"] for x in rs).items())),
                      "derivative_gb": round(sum(int(x["size"]) for x in rs) / 1e9, 2)})
    wcsv(os.path.join(args.out, "waiting_groups.csv"),
         ["group", "original_acq_id", "original_name", "instrument", "original_folder", "derivatives", "classes",
          "derivative_gb"], wrows)
    out.append(f"### Groups whose original has no project but which hold derivatives\n\n{len(wrows)} groups, "
               f"{sum(w['derivatives'] for w in wrows)} derivatives, {sum(w['derivative_gb'] for w in wrows):.1f} GB "
               "(`waiting_groups.csv`)")
    amb = [r for r in rows if r["class"] == C_AMBIGUOUS]
    out.append("### Ambiguous members\n\n" + md_table(
        ["acq_id", "name", "group", "evidence"],
        [(r["acq_id"], r["name"], r["group"][:24], r["evidence"]) for r in amb]))
    with io.open(os.path.join(args.out, "report_tables.md"), "w", encoding="utf-8") as f:
        f.write("\n\n".join(out) + "\n")
    print("\n\n".join(out))
    return 0


# ---------------------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--lists-dir", default=RETIRE_LISTS)
    ap.add_argument("--redo", action="store_true", help="relations: recompute groups already done")
    ap.add_argument("--exhaustive", action="store_true",
                    help="relations: run the crop and stitch tests on every pair (validates the gates)")
    ap.add_argument("--only", default="", help="relations: only the groups whose key starts with one of these, comma-separated")
    ap.add_argument("--allow-missing", action="store_true",
                    help="classify: preview, leaving out the groups whose relations are not computed yet")
    ap.add_argument("--skip-siblings", action="store_true",
                    help="pieces: do not read groups whose members are distinct stage positions")
    ap.add_argument("--sample", type=int, default=20, help="validate: how many gated-out groups to test")
    ap.add_argument("--max-gb", type=float, default=6.0, help="validate: largest group (GB) to test")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("table", "features", "pieces", "check", "relations", "retile", "restitch", "retrim", "region", "validate", "classify", "lists",
                 "verify-lists", "report"):
        sub.add_parser(name)
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    return {"table": cmd_table, "features": cmd_features, "pieces": cmd_pieces, "check": cmd_check,
            "relations": cmd_relations, "retile": cmd_retile, "restitch": cmd_restitch, "retrim": cmd_retrim, "region": cmd_region,
            "validate": cmd_validate,
            "classify": cmd_classify, "lists": cmd_lists, "verify-lists": cmd_verify_lists,
            "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
