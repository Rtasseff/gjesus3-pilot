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

    def __init__(self, arr):
        import numpy as np
        if arr.ndim != 3:
            raise ValueError("a (H, W, S) array is needed")
        self.arr = np.ascontiguousarray(arr)
        self.hay = self.arr.tobytes()

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
        cands = sorted({0, h // 4, h // 2, (3 * h) // 4, h - 1})
        best, best_n = cands[0], -1
        for r in cands:
            n = len(np.unique(a[r]))
            if n > best_n:
                best, best_n = r, n
        if best_n < 4 and w * s > 8:      # a flat row: no useful anchor
            return []
        needle = np.ascontiguousarray(a[best]).tobytes()
        stride = ww * item
        hits = []
        for i in find_all(self.hay, needle):
            row, byte_col = divmod(i, stride)
            if byte_col % item or byte_col + len(needle) > stride:
                continue
            oy, ox = row - best, byte_col // item
            if oy < 0 or oy + h > hh or ox + w > ww:
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
            out["scene_centers"] = ";".join(_tx(s, "CenterPosition") for s in sc)[:400]
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


def cmd_pieces(args):
    rows = rcsv(os.path.join(args.out, "members.csv"))
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

    def read(self, p):
        import numpy as np
        if any(v != 1 for v in p["stored"][:-3]):
            raise ValueError("a subblock with more than one plane")
        self.fh.seek(p["pos"])
        raw = self.fh.read(p["nbytes"])
        if len(raw) != p["nbytes"]:
            raise IOError(f"short read at {p['pos']}")
        h, w, s = p["stored"][-3:]
        return np.frombuffer(raw, dtype=np.dtype(p["dtype"])).reshape(h, w, s)


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
            n_m, a_m = verify(hint)
            if n_m * 2 >= n_a:
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


def stitch_match(S, T, s_path, t_path, sample=16, frac=0.30):
    """Does the stitched candidate S contain, byte for byte, the interiors of the tiles of T?

    ZEN's stitching re-places and blends tiles, so S cannot match T tile for tile; but where one tile
    alone contributes, S holds that tile's pixels unchanged. For up to `sample` informative tiles of T
    (evenly spaced), the central `frac` x `frac` patch is searched for in S's pixel data. A found
    patch is exact equality of every value; the per-tile shifts show the re-placement."""
    import numpy as np
    tiles = [p for p in T["pieces"] if p["h"] >= 64 and p["w"] >= 64]
    tiles.sort(key=lambda p: (p["scene"], p["y"], p["x"]))
    step = max(1, len(tiles) // sample)
    chosen = tiles[::step][:sample]
    found, shifts = 0, []
    with TileReader(t_path) as rt, TileReader(s_path) as rs:
        hays = []                       # S's pixel data, built once
        for sp in S["pieces"]:
            hays.append((sp, Haystack(rs.read(sp))))
        for tp in chosen:
            tarr = rt.read(tp)
            h, w, _ = tarr.shape
            r0, r1 = int(h * (0.5 - frac / 2)), int(h * (0.5 + frac / 2))
            c0, c1 = int(w * (0.5 - frac / 2)), int(w * (0.5 + frac / 2))
            patch = tarr[r0:r1, c0:c1]
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
    return {"method": "stitch", "sampled": len(chosen), "found": found, "shifts": shifts,
            "complete": len(chosen) >= 4 and found >= 0.9 * len(chosen)}


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
    """Cheap preconditions for 'A is a crop of B' -- no pixels read: some B tile is at least as big as
    A's largest tile, the same pixel size (1%), and the same stage position when both files say one."""
    aw, ah = max_tile(PA)
    if not any(q["w"] >= aw and q["h"] >= ah for q in PB["pieces"]):
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
            if h["matched"]:
                rels.append({"a": a, "b": b, "kind": "hash", "complete": h["complete"], "pieces": h["pieces"],
                             "matched": h["matched"], "area_frac": round(h["area_frac"], 4),
                             "maps": h["maps"], "n_b": len(P[b]["pieces"]),
                             "scenes_b": sorted({v["to_scene"] for v in h["maps"].values() if "to_scene" in v}),
                             "n_scenes_b": len(P[b]["scenes"]), "n_scenes_a": len(P[a]["scenes"])})
                if h["complete"]:
                    done_complete.add((a, b))
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
C_AMBIGUOUS = "ambiguous"
DERIVATIVE_CLASSES = (C_SCALEBAR, C_RESAVE, C_CROP, C_SUBSET, C_SPLIT, C_STITCHED)
LIST_A = (C_SCALEBAR, C_RESAVE)            # pixel-identical to the original
LIST_B = (C_CROP, C_SUBSET)                # smaller: a crop or a subset of the original
PROPOSAL_C = (C_SPLIT, C_STITCHED)         # Ryan decides (scene splits, stitched copies)


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
    if r["kind"] == "stitch":
        return "stitched"
    if r["kind"] == "crop":
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
                    out[m] = {"class": C_SCALEBAR if copy_like(by[m]) else C_RESAVE, "parent": rep[c],
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
                kind = compose([k for (k, _r) in chain])
                last = chain[-1][1]
                via = f"{kind} (through {by[last['b']]['name']})"
                ev = evidence_text(last, by[last["b"]]["name"])
            if kind == "identical":
                cls = C_SCALEBAR if copy_like(by[m]) else C_RESAVE
            else:
                cls = {"crop": C_CROP, "subset": C_SUBSET, "split": C_SPLIT, "stitched": C_STITCHED}[kind]
            out[m] = {"class": cls, "parent": rep[rc], "via": via, "evidence": ev}
    # a root member with only a partial relation is not 'distinct' or 'original': say so
    partial = collections.defaultdict(list)
    complete_pairs = {(r["a"], r["b"]) for r in comp}
    for r in rels:
        # a partial hit between files that are fully related (either way) is just the container's
        # share of the contained file; only a partial relation with no complete one is a finding
        if not r["complete"] and r.get("area_frac", 0) >= 0.5                 and (r["a"], r["b"]) not in complete_pairs and (r["b"], r["a"]) not in complete_pairs:
            partial[r["a"]].append(r)
    for m, rs in partial.items():
        if out[m]["class"] in (C_DISTINCT, C_ORIGINAL):
            best = max(rs, key=lambda r: r["area_frac"])
            out[m] = {"class": C_AMBIGUOUS, "parent": None, "via": "",
                      "evidence": (f"{best['kind']} match covers {best['area_frac']:.0%} of its tiles inside "
                                   f"{by[best['b']]['name']} (not complete)")}
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
    t0 = time.time()
    todo = []
    for gi, k in enumerate(keys):
        f = os.path.join(rdir, f"{gi:03d}.json")
        if os.path.exists(f) and not args.redo:
            continue
        if not all(os.path.exists(pieces_cache_path(args.out, m["sha256"])) for m in groups[k]):
            continue                              # tile cache not finished for this group yet
        todo.append((gi, k, f))
    print(f"{len(keys)} groups, {len(todo)} to do now")
    errs = []

    def one(item):
        gi, k, f = item
        ms = groups[k]
        rels = group_relations(ms, args.out, exhaustive=args.exhaustive)
        tmp = f + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"group": k, "ids": [m["acq_id"] for m in ms], "rels": rels}, fh)
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
              "class", "parent_acq_id", "parent_name", "via", "evidence", "own_project", "parent_project",
              "parent_project_status", "has_scalebar", "creation_date", "action", "action_note"]


def decide_action(m, c, parent, projects_status):
    """What the class means for the retire lists: ('a'|'b'|'c'|'stay'|'waiting'|'conflict'|'closed', note)."""
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
    return ("a" if cls in LIST_A else "b"), ""


def cmd_classify(args):
    mem = load_members_with_features(args.out)
    groups = groups_of(mem)
    rels = load_relations(args.out)
    missing = [k for k in groups if k not in rels]
    if missing:
        print(f"{len(missing)} groups have no relations yet; run `relations` first", file=sys.stderr)
        return 1
    projects = {r["name"]: r["status"] for r in rcsv(os.path.join(NAS, "registries", "registry_projects.csv"))}
    rows = []
    for k, ms in groups.items():
        nodes = []
        for m in ms:
            f = m["feat"]
            nodes.append({"id": m["acq_id"], "name": m["name"], "project": m["project_name"],
                          "scalebar": f.get("has_scalebar") == "True", "creation": parse_dt(f.get("CreationDate"))})
        cl = classify_group(nodes, rels[k])
        byid = {m["acq_id"]: m for m in ms}
        for m in ms:
            c = cl[m["acq_id"]]
            parent = byid.get(c["parent"]) if c["parent"] else None
            action, note = decide_action(m, c, parent, projects) if parent else \
                ("stay", "") if c["class"] != C_AMBIGUOUS else ("stay", "ambiguous: stays in /raw/")
            rows.append({"group": k, "group_n": m["group_n"], "acq_id": m["acq_id"], "name": m["name"],
                         "folder": m["folder"], "drive": m["drive"], "size": m["size"],
                         "instrument": m["instrument"], "acquisition_datetime": m["acquisition_datetime"],
                         "class": c["class"], "parent_acq_id": c["parent"] or "",
                         "parent_name": parent["name"] if parent else "", "via": c["via"],
                         "evidence": c["evidence"], "own_project": m["project_name"],
                         "parent_project": parent["project_name"] if parent else "",
                         "parent_project_status": projects.get(parent["project_name"], "") if parent else "",
                         "has_scalebar": m["feat"].get("has_scalebar", ""), "creation_date": m["feat"].get("CreationDate", ""),
                         "action": action, "action_note": note})
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


def write_list(path, rows):
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LIST_COLS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def cmd_lists(args):
    classified = rcsv(os.path.join(args.out, "classified.csv"))
    names = {"a": "2026-10_r4_scalebars.csv", "b": "2026-10_r4_exports.csv"}
    os.makedirs(args.lists_dir, exist_ok=True)
    for action, fn in names.items():
        rows = list_rows(classified, action)
        write_list(os.path.join(args.lists_dir, fn), rows)
        gb = sum(int(r["size"]) for r in classified if r["action"] == action) / 1e9
        print(f"{fn}: {len(rows)} rows, {gb:.1f} GB")
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
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("table", "features", "pieces", "relations", "classify", "lists"):
        sub.add_parser(name)
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    return {"table": cmd_table, "features": cmd_features, "pieces": cmd_pieces, "relations": cmd_relations,
            "classify": cmd_classify, "lists": cmd_lists}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
