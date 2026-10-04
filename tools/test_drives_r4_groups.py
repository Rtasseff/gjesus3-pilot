#!/usr/bin/env python3
"""test_drives_r4_groups.py -- the logic of tools/drive_staging/r4_groups.py (the same-timestamp group
clean-up of the drives .czi ingest), on synthetic tiles: no .czi file, no NAS, no D: needed.

  1. r4_destinations (stream A's short-path rule, Ryan 2026-10-04): the study folder, the frozen
     _PATHMAP, the 240-character budget, nothing already there, the same folder as A's other files of that
     drive folder; the merge of the new `_INDEX.csv` / `_PATHMAP.csv` rows (a superset, never an overwrite).
     Skipped, with a message, if stream A's historical_paths.py is not to be found.
  2. staged_path: where a plan row's staged / extracted copy lives.
  3. Haystack.locate: a byte-exact sub-array is found at its position, a near miss is not.
  4. hash_match: identical tiles at one offset; a scene split; a partial match is not complete.
  5. crop_match / stitch_match on tiles written to a scratch file the way a .czi stores them.
  5b. tileset_match + grid_score (re-placed tiles), cutset_match + trim_records (trimmed pieces),
     region_match + region_records (a crop re-blocked from its own origin), informative (blank tiles
     prove nothing), the rank correlation of a rendering.
  6. classify_group: original + crop + scale-bar copy of the crop; master + scene splits; siblings;
     pixel-identical twins; stitched copies; a member contained in two unrelated files; chains.
  7. the original of a set of identical files (rank_key); decide_action (lists a, r, b, k, waiting,
     conflict, closed; the 5% boundary between b and k); the retire-list row, its file format and
     the path checks.

Run:  python tools/test_drives_r4_groups.py
"""
import datetime as dt
import os
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "drive_staging"))
import r4_groups as R  # noqa: E402
import r4_destinations as D  # noqa: E402

FAILS = []


def check(cond, msg):
    print(f"  {'ok:  ' if cond else 'FAIL:'} {msg}")
    if not cond:
        FAILS.append(msg)


RNG = np.random.default_rng(7)


def img(h, w, s=3, dtype=np.uint16):
    return RNG.integers(0, 60000, size=(h, w, s)).astype(dtype)


# ---------------------------------------------------------------------------------------------
# a scratch "file" of tiles + the piece dicts a tile cache would hold for it
# ---------------------------------------------------------------------------------------------

class FakeFile:
    def __init__(self, tmp, name):
        self.path = os.path.join(tmp, name)
        self.f = open(self.path, "wb")
        self.pieces = []
        self.pos = 0
        self.scenes = {}

    def add(self, arr, x, y, scene=0, key=(("C", 0),)):
        raw = arr.tobytes()
        self.f.write(raw)
        h, w, s = arr.shape
        import hashlib
        self.pieces.append({"scene": scene, "m": len(self.pieces), "key": [list(k) for k in key], "x": x, "y": y,
                            "w": w, "h": h, "samples": s, "dtype": str(arr.dtype), "compression": "UNCOMPRESSED",
                            "stored": [1, h, w, s], "pos": self.pos, "nbytes": len(raw),
                            "hash": hashlib.sha256(raw).hexdigest()})
        self.pos += len(raw)
        self.scenes.setdefault(scene, [0, 0, 0, 0])
        return self

    def done(self):
        self.f.close()
        return {"path": self.path, "pieces": self.pieces, "scenes": self.scenes}


# ---------------------------------------------------------------------------------------------

def test_helpers():
    print("test_helpers")
    check(R.basename("drive1_FRIO-X6/a/b/c d.czi") == "c d.czi" and R.dirname("x/y/z.czi") == "x/y",
          "basename / dirname split on the forward slash")
    check(R.dirname("z.czi") == "", "a name with no folder has an empty dirname")


def test_staged_path():
    print("test_staged_path")
    loose = {"kind": "loose", "drive": "D2", "relpath": "A\\B\\c.czi", "archive": "", "member": ""}
    check(R.staged_path(loose).endswith(r"drive2_MFB-Disco-2_2322E4A112BD\files\A\B\c.czi"),
          "a loose D2 file is under drive2_...\\files")
    mem = {"kind": "member", "drive": "D1", "relpath": "", "archive": "Former students\\Z\\x.zip",
           "member": "in/side.czi"}
    p = R.staged_path(mem)
    check(p.startswith(R.EXTRACT) and "D1_" in p and p.endswith(r"x.zip\in\side.czi"),
          "an archive member is under _extract\\D1_<sha1>_<archive name>")
    import hashlib
    check(hashlib.sha1("D1|Former students\\Z\\x.zip".encode()).hexdigest()[:6] in p,
          "the extract folder key is the ingest plan's (sha1 of drive|archive, 6 chars)")


def test_haystack():
    print("test_haystack")
    b = img(300, 400)
    a = b[120:200, 55:310].copy()
    check(R.Haystack(b).locate(a) == [(120, 55)], "a sub-array is found at its exact position")
    a2 = a.copy()
    a2[40, 100, 1] ^= 1
    check(R.Haystack(b).locate(a2) == [], "a one-value difference is not a match")
    check(R.Haystack(b).locate(a.astype(np.uint8)) == [], "a different dtype is not a match")
    flat = np.zeros((50, 60, 3), np.uint16)
    check(R.Haystack(np.zeros((100, 100, 3), np.uint16)).locate(flat) == [], "a flat patch is not an anchor")
    big = img(100, 100)
    check(R.Haystack(big).locate(img(120, 50)) == [], "a patch larger than the haystack is not found")
    c = np.concatenate([b[:, :200], b[:, :200]], axis=1)         # the same 200 columns twice
    hits = R.Haystack(c).locate(b[50:90, 10:150])
    check(sorted(hits) == [(50, 10), (50, 210)], "a patch present twice is found twice")


def test_hash_match():
    print("test_hash_match")
    with tempfile.TemporaryDirectory() as tmp:
        t = [img(40, 50) for _ in range(4)]
        A = FakeFile(tmp, "a").add(t[0], 0, 0).add(t[1], 50, 0).add(t[2], 0, 40).add(t[3], 50, 40).done()
        B = FakeFile(tmp, "b").add(t[0], 100, 7).add(t[1], 150, 7).add(t[2], 100, 47).add(t[3], 150, 47).done()
        h = R.hash_match(A, B)
        m = h["maps"][0]
        check(h["complete"] and (m["dx"], m["dy"]) == (100, 7), "four identical tiles at one offset: complete, offset (100, 7)")
        C = FakeFile(tmp, "c").add(t[0], 100, 7).add(t[1], 150, 7).add(img(40, 50), 100, 47).done()
        h = R.hash_match(A, C)
        check(not h["complete"] and h["matched"] == 2, "two of four tiles present: 2 matched, not complete")
        # a scene split: A is one scene of the master M
        sc = [img(30, 30) for _ in range(5)]
        M = FakeFile(tmp, "m")
        for i, s in enumerate(sc):
            M.add(s, i * 1000, 0, scene=i)
        M = M.done()
        M["scenes"] = {i: [i * 1000, 0, 30, 30] for i in range(5)}
        S = FakeFile(tmp, "s").add(sc[3], 5, 5).done()
        h = R.hash_match(S, M)
        check(h["complete"] and h["maps"][0]["to_scene"] == 3, "a split file maps to scene 3 of the master")
        check(R.hash_match(M, S)["matched"] == 1 and not R.hash_match(M, S)["complete"],
              "the master is not contained in the split")
        # the cache-only check of the stage-position gate: a payload that two files share, anywhere
        x = FakeFile(tmp, "x").add(t[0], 0, 0).add(img(40, 50), 50, 0).done()
        y = FakeFile(tmp, "y").add(img(40, 50), 0, 0).add(img(40, 50), 60, 9).done()
        z = FakeFile(tmp, "z").add(img(40, 50), 3, 3).add(t[0], 500, 500).done()
        check(R.shared_payloads({"x": x, "y": y}) == 0, "two files with no tile in common share no payload")
        check(R.shared_payloads({"x": x, "y": y, "z": z}) == 1, "one payload at different positions in two files is found")
        dup = FakeFile(tmp, "dup").add(t[1], 0, 0).add(t[1], 60, 0).done()
        check(R.shared_payloads({"dup": dup}) == 0, "a payload repeated inside ONE file is not 'shared'")


def test_crop_and_stitch():
    print("test_crop_and_stitch")
    with tempfile.TemporaryDirectory() as tmp:
        tiles = {(r, c): img(80, 100) for r in range(3) for c in range(3)}
        B = FakeFile(tmp, "parent")
        for (r, c), a in tiles.items():
            B.add(a, c * 90, r * 70)          # 10 px / 10 px overlap
        B = B.done()
        # a crop whose border cuts four tiles: ZEN stores the cut pieces
        ox, oy = 95, 75
        A = FakeFile(tmp, "crop")
        for (r, c) in [(1, 1), (1, 2), (2, 1), (2, 2)]:
            t = tiles[(r, c)]
            x0, y0 = max(c * 90, ox), max(r * 70, oy)
            x1, y1 = min(c * 90 + 100, ox + 150), min(r * 70 + 80, oy + 100)
            if x1 > x0 and y1 > y0:
                A.add(t[y0 - r * 70:y1 - r * 70, x0 - c * 90:x1 - c * 90].copy(), x0 - ox, y0 - oy)
        A = A.done()
        res = R.crop_match(A, B, A["path"], B["path"])
        check(res["complete"] and (res["maps"][0]["dx"], res["maps"][0]["dy"]) == (95, 75),
              f"every cut piece is found in the parent at offset (95, 75): {res['matched']}/{res['pieces']}")
        # a crop with one altered piece is not complete
        A2 = FakeFile(tmp, "crop2")
        for p in A["pieces"]:
            arr = R.TileReader(A["path"]).read(p).copy()
            A2.add(arr, p["x"], p["y"])
        bad = R.TileReader(A["path"]).read(A["pieces"][0]).copy()
        bad[10, 10, 0] ^= 1
        A2.pieces[0]["hash"] = "x"
        A2.f.seek(0)
        A2.f.write(bad.tobytes())
        A2 = A2.done()
        res = R.crop_match(A2, B, A2["path"], B["path"])
        check(not res["complete"], "one altered value in one piece: not complete")
        # stitch: a canvas that holds each tile's interior shifted by its own integer offset
        S = FakeFile(tmp, "stitched")
        canvas = np.zeros((70 * 2 + 80 + 12, 90 * 2 + 100 + 12, 3), np.uint16)
        for (r, c), a in tiles.items():
            dy, dx = (r * 3) % 7, (c * 5) % 9
            canvas[r * 70 + dy:r * 70 + dy + 80, c * 90 + dx:c * 90 + dx + 100] = a
        S.add(canvas, 0, 0)
        S = S.done()
        st = R.stitch_match(S, B, S["path"], B["path"], sample=9)
        check(st["found"] == 9 and st["complete"], f"the interiors of 9/9 tiles are found in the stitched canvas: {st['found']}")
        other = FakeFile(tmp, "unrelated").add(img(300, 400), 0, 0).done()
        st = R.stitch_match(other, B, other["path"], B["path"], sample=9)
        check(st["found"] == 0 and not st["complete"], "an unrelated image contains none of the tiles")


def test_retile():
    print("test_retile")
    with tempfile.TemporaryDirectory() as tmp:
        t = [img(30, 40, 1) for _ in range(6)]
        grid = FakeFile(tmp, "grid")
        shifted = FakeFile(tmp, "shifted")
        for i, a in enumerate(t):
            r, c = divmod(i, 3)
            grid.add(a, c * 36, r * 26)
            shifted.add(a, c * 36 + 3 * i, r * 26 + 2 * i + 1)       # each tile re-placed by its own shift
        grid, shifted = grid.done(), shifted.done()
        check(not R.hash_match(shifted, grid)["complete"], "no single offset fits the re-placed tiles")
        ts = R.tileset_match(shifted, grid)
        check(ts["complete"] and ts["matched"] == 6, "but all 6 tile payloads are the grid file's")
        check(R.tileset_match(grid, shifted)["complete"], "and the other way round (mutual)")
        check(R.grid_score(grid) < 1.0 < R.grid_score(shifted),
              f"the regular grid scores low ({R.grid_score(grid):.2f}), the shifted one high ({R.grid_score(shifted):.2f})")
        other = FakeFile(tmp, "other").add(t[0], 0, 0).add(img(30, 40, 1), 36, 0).done()
        check(not R.tileset_match(other, grid)["complete"] and R.tileset_match(other, grid)["matched"] == 1,
              "one tile in common is a partial match")
        dup = FakeFile(tmp, "dup").add(t[0], 0, 0).add(t[0], 40, 0).done()
        one = FakeFile(tmp, "one").add(t[0], 0, 0).done()
        check(not R.tileset_match(dup, one)["complete"], "a payload is not counted more often than B holds it")


def test_retrim():
    print("test_retrim")
    with tempfile.TemporaryDirectory() as tmp:
        tiles = [img(80, 100, 3) for _ in range(4)]
        B = FakeFile(tmp, "orig")
        for i, t in enumerate(tiles):
            B.add(t, (i % 2) * 90, (i // 2) * 70)
        B = B.done()
        # a fused/stitched copy: every tile trimmed by its own amounts and re-placed
        A = FakeFile(tmp, "fused")
        trims = [(0, 10, 0, 8), (5, 0, 3, 0), (0, 0, 12, 4), (7, 3, 1, 1)]       # left, right, top, bottom
        for i, (t, (l, r, tp, bt)) in enumerate(zip(tiles, trims)):
            A.add(t[tp:80 - bt, l:100 - r].copy(), (i % 2) * 85 + i, (i // 2) * 66 + 2 * i)
        A = A.done()
        c = R.cutset_match(A, B, A["path"], B["path"])
        check(c["complete"] and c["matched"] == 4, "all 4 trimmed tiles are sub-rectangles of the original's tiles")
        check(len(set(c["shifts"])) == 4, "each at its own offset (4 different shifts)")
        check(not R.crop_match(A, B, A["path"], B["path"])["complete"], "no single offset explains them (not a crop)")
        check(not R.cutset_match(B, A, B["path"], A["path"])["complete"],
              "the original is not made of pieces of the trimmed copy")
        other = FakeFile(tmp, "other").add(img(60, 70, 3), 0, 0).done()
        check(R.cutset_match(other, B, other["path"], B["path"])["matched"] == 0, "an unrelated tile is not found")
        ms = [{"acq_id": "A", "feat": {"pxX": "6.9E-07", "scene_centers": "1,2"}, "staged_path": A["path"]},
              {"acq_id": "B", "feat": {"pxX": "6.9E-07", "scene_centers": "1,2"}, "staged_path": B["path"]}]
        recs = R.trim_records(ms, {"A": dict(A, scenes={0: [0, 0, 1, 1]}), "B": dict(B, scenes={0: [0, 0, 1, 1]})}, set())
        check(len(recs) == 1 and recs[0]["a"] == "A" and recs[0]["b"] == "B" and recs[0]["complete"],
              "trim_records: A (the smaller) is trimmed from B, recorded in that direction only")
        ms[1]["feat"]["scene_centers"] = "9,9"
        check(R.trim_records(ms, {"A": dict(A, scenes={0: [0, 0, 1, 1]}), "B": dict(B, scenes={0: [0, 0, 1, 1]})}, set()) == [],
              "files with different stage positions are not tested")


def test_region():
    print("test_region")
    with tempfile.TemporaryDirectory() as tmp:
        full = img(520, 640, 3)                                  # the original's whole image
        B = FakeFile(tmp, "orig")                                # stored in 256 x 256 blocks from its origin
        for by in range(0, 520, 256):
            for bx in range(0, 640, 256):
                B.add(full[by:by + 256, bx:bx + 256].copy(), bx, by)
        B = B.done()
        B["scenes"] = {0: [0, 0, 640, 520]}

        def crop(name, x0, y0, w, h, edit=None):
            sub = full[y0:y0 + h, x0:x0 + w].copy()
            if edit:
                edit(sub)
            f = FakeFile(tmp, name)                              # the crop is re-blocked from its OWN origin
            for by in range(0, h, 256):
                for bx in range(0, w, 256):
                    f.add(sub[by:by + 256, bx:bx + 256].copy(), bx, by)
            d = f.done()
            d["scenes"] = {0: [0, 0, w, h]}
            return d

        A = crop("reblocked", 45, 33, 480, 360)                  # its blocks straddle the original's
        check(not R.crop_match(A, B, A["path"], B["path"])["complete"], "no block of the crop is a piece of one tile")
        check(not R.cutset_match(A, B, A["path"], B["path"])["complete"], "nor does the trimmed-tile test find them")
        g = R.region_match(A, B, A["path"], B["path"])
        check(g["complete"] and (g["maps"]["dx"], g["maps"]["dy"]) == (45, 33) and g["area_frac"] == 1.0,
              f"the whole image is found in the original at offset (45, 33): {g['matched']}/{g['pieces']} blocks, "
              f"{g['area_frac']:.0%}")
        bad = crop("edited", 45, 33, 480, 360, edit=lambda a: a.__setitem__((100, 200, 1), a[100, 200, 1] ^ 1))
        g = R.region_match(bad, B, bad["path"], B["path"])
        check(not g["complete"] and 0.99 < g["area_frac"] < 1.0,
              "one altered value: found, but not complete, and the share says how close")
        other = FakeFile(tmp, "other").add(img(200, 300, 3), 0, 0).done()
        other["scenes"] = {0: [0, 0, 300, 200]}
        g = R.region_match(other, B, other["path"], B["path"])
        check(not g["complete"] and g["matched"] == 0 and g["area_frac"] == 0.0, "an unrelated image has no offset at all")
        flat = FakeFile(tmp, "flat").add(np.zeros((150, 200, 3), np.uint16), 0, 0).done()
        flat["scenes"] = {0: [0, 0, 200, 150]}
        flatb = FakeFile(tmp, "flatb").add(np.zeros((520, 640, 3), np.uint16), 0, 0).done()
        flatb["scenes"] = {0: [0, 0, 640, 520]}
        check(not R.region_match(flat, flatb, flat["path"], flatb["path"])["complete"], "a blank image proves nothing")
        ms = [{"acq_id": "A", "feat": {"pxX": "6.9E-07", "scene_centers": "1,2"}, "staged_path": A["path"]},
              {"acq_id": "B", "feat": {"pxX": "6.9E-07", "scene_centers": "1,2"}, "staged_path": B["path"]}]
        P = {"A": A, "B": B}
        recs = R.region_records(ms, P, set())
        check(len(recs) == 1 and recs[0]["a"] == "A" and recs[0]["b"] == "B" and recs[0]["complete"]
              and recs[0]["kind"] == "region", "region_records: A (the smaller) is a region of B, in that direction only")
        check(R.region_records(ms, P, {("A", "B")}) == [], "a member already found contained in something is not tested")
        ms[1]["feat"]["scene_centers"] = "9,9"
        check(R.region_records(ms, P, set()) == [], "files with different stage positions are not tested")
    # the classification: a region record is a crop
    c = R.classify_group([node("O", "orig.czi"), node("K", "orig_2.czi")],
                         [dict(rel("K", "O", "region", pieces=6, n_b=12), maps={"dx": 45, "dy": 33})])
    check(c["K"]["class"] == R.C_CROP and c["O"]["class"] == R.C_ORIGINAL and "(45, 33)" in c["K"]["evidence"],
          "a region relation classifies the member as a crop of the original, evidence gives the offset")


def test_informative():
    print("test_informative")
    with tempfile.TemporaryDirectory() as tmp:
        blank = FakeFile(tmp, "blank").add(np.zeros((200, 200, 3), np.uint16), 0, 0).done()
        check(not R.informative(blank["path"], blank["pieces"]), "an all-black tile carries no image content")
        sat = FakeFile(tmp, "sat").add(np.full((200, 200, 3), 65535, np.uint16), 0, 0).done()
        check(not R.informative(sat["path"], sat["pieces"]), "a saturated tile carries none either")
        real = FakeFile(tmp, "real").add(img(200, 200), 0, 0).done()
        check(R.informative(real["path"], real["pieces"]), "a noisy tile does")
        mixed = FakeFile(tmp, "mixed").add(np.zeros((50, 50, 3), np.uint16), 0, 0).add(img(200, 200), 60, 0).done()
        check(R.informative(mixed["path"], mixed["pieces"]), "one informative tile among the largest is enough")


def test_similarity():
    print("test_similarity")
    a = RNG.random((60, 80))
    check(abs(R.rank_correlation(a, a) - 1.0) < 1e-9, "an image has rank correlation 1 with itself")
    check(abs(R.rank_correlation(a, a ** 3 * 255) - 1.0) < 1e-9, "a monotone re-rendering keeps rank correlation 1")
    check(abs(R.rank_correlation(a, RNG.random((60, 80)))) < 0.1, "unrelated noise is near 0")
    check(R.rank_correlation(np.zeros((10, 10)), a[:10, :10]) == 0.0, "a flat plane has no correlation")
    with tempfile.TemporaryDirectory() as tmp:
        base = img(100, 120, 1)
        A = FakeFile(tmp, "a16").add(base, 0, 0, key=(("C", 0),)).done()
        rgb = np.repeat((base // 257).astype(np.uint8), 3, axis=2)
        B = FakeFile(tmp, "b8").add(rgb, 0, 0, key=(("C", 0),)).done()
        sim = R.pair_similarity(B["path"], B, A["path"], A)
        check(sim is not None and sim[0] > 0.99 and sim[1] == 1, "an 8-bit rendering of a 16-bit plane: correlation > 0.99")
        C = FakeFile(tmp, "c16").add(img(100, 120, 1), 0, 0).done()
        sim = R.pair_similarity(C["path"], C, A["path"], A)
        check(sim is not None and sim[0] < 0.2, "an unrelated plane of the same size: low correlation")
        D2 = FakeFile(tmp, "tiled").add(img(50, 50, 1), 0, 0).add(img(50, 50, 1), 50, 0).done()
        check(R.pair_similarity(D2["path"], D2, A["path"], A) is None, "a file with several tiles per plane is not compared")


def node(i, name, project="", scalebar=False, creation=None):
    return {"id": i, "name": name, "project": project, "scalebar": scalebar,
            "creation": creation or dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)}


def rel(a, b, kind="hash", complete=True, pieces=4, n_b=4, scenes_b=(0,), n_scenes_b=1, matched=None, area=1.0):
    return {"a": a, "b": b, "kind": kind, "complete": complete, "pieces": pieces,
            "matched": pieces if matched is None else matched, "area_frac": area, "maps": {0: {"dx": 1, "dy": 2}},
            "n_b": n_b, "scenes_b": list(scenes_b), "n_scenes_b": n_scenes_b, "n_scenes_a": 1}


def test_classify():
    print("test_classify")
    # original O, a crop K of it, a scale-bar copy SK of the crop (identical to K, crop of O)
    ns = [node("O", "orig.czi", "P1"), node("K", "crop.czi"), node("SK", "crop-scale.czi", scalebar=True)]
    rs = [rel("K", "O", "crop"), rel("SK", "O", "crop"), rel("K", "SK"), rel("SK", "K")]
    c = R.classify_group(ns, rs)
    check(c["O"]["class"] == R.C_ORIGINAL and c["K"]["class"] == R.C_CROP and c["K"]["parent"] == "O",
          "original / crop of the original")
    check(c["SK"]["class"] == R.C_CROP and c["SK"]["parent"] == "O",
          "a scale-bar copy of a crop is a crop of the original, not a copy of the whole")
    # whole-image scale-bar copy and a plain renamed re-save
    ns = [node("O", "x.czi"), node("S", "x-scale.czi", scalebar=True), node("R", "x.czi1.czi")]
    rs = [rel("S", "O"), rel("O", "S"), rel("R", "O"), rel("O", "R"), rel("R", "S"), rel("S", "R")]
    c = R.classify_group(ns, rs)
    check(c["O"]["class"] == R.C_ORIGINAL, "the file that is not copy-like is the original")
    check(c["S"]["class"] == R.C_SCALEBAR and c["R"]["class"] == R.C_RESAVE, "scale-bar copy vs identical re-save")
    # a master and scene splits
    ns = [node("M", "plate.czi")] + [node(f"S{i}", f"plate-Scene-{i}.czi") for i in range(3)]
    rs = [rel(f"S{i}", "M", pieces=2, n_b=6, scenes_b=(i,), n_scenes_b=3) for i in range(3)]
    c = R.classify_group(ns, rs)
    check(c["M"]["class"] == R.C_ORIGINAL and all(c[f"S{i}"]["class"] == R.C_SPLIT for i in range(3)),
          "a master and its scene splits")
    # siblings: three roots, nothing related
    ns = [node("A", "a.czi"), node("B", "b.czi"), node("C", "c.czi")]
    c = R.classify_group(ns, [])
    check(all(v["class"] == R.C_DISTINCT for v in c.values()), "unrelated members are distinct")
    # a lone member
    check(R.classify_group([node("A", "a.czi")], [])["A"]["class"] == R.C_ORIGINAL, "a single root is the original")
    # pixel-identical twins, both clean: the one with a project, then the earlier date, is the original
    d1 = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
    d2 = dt.datetime(2024, 1, 2, tzinfo=dt.timezone.utc)
    ns = [node("X", "x.czi", "", creation=d1), node("Y", "x1.czi", "P1", creation=d2)]
    c = R.classify_group(ns, [rel("X", "Y"), rel("Y", "X")])
    check(c["Y"]["class"] == R.C_ORIGINAL and c["X"]["class"] == R.C_RESAVE, "twins: the one with a project is the original")
    ns = [node("X", "x.czi", "", creation=d2), node("Y", "x1.czi", "", creation=d1)]
    c = R.classify_group(ns, [rel("X", "Y"), rel("Y", "X")])
    check(c["Y"]["class"] == R.C_ORIGINAL, "twins, no project: the earlier CreationDate is the original")
    # a stitched copy
    ns = [node("T", "tiles.czi"), node("S", "tiles-Stitching-01.czi")]
    c = R.classify_group(ns, [rel("S", "T", "stitch", pieces=16, n_b=200)])
    check(c["S"]["class"] == R.C_STITCHED and c["T"]["class"] == R.C_ORIGINAL, "a stitched copy of the tiled original")
    r1 = rel("S", "T", "retile", pieces=20, n_b=20)
    r1["maps"] = {"grid": [2.0, 0.45]}
    c = R.classify_group(ns, [r1])
    check(c["S"]["class"] == R.C_STITCHED and c["T"]["class"] == R.C_ORIGINAL and "re-placed" in c["S"]["evidence"],
          "a stitched copy that kept its tiles (re-placed): stitched, evidence says so")
    u1, u2 = rel("S", "T", "retile", complete=False, pieces=20, n_b=20), rel("T", "S", "retile", complete=False, pieces=20, n_b=20)
    u1["undecided"] = u2["undecided"] = True
    c = R.classify_group(ns, [u1, u2])
    check(c["S"]["class"] == R.C_AMBIGUOUS and c["T"]["class"] == R.C_AMBIGUOUS and "grids" in c["S"]["evidence"],
          "same tiles at other positions and the grids cannot tell which is the acquisition: ambiguous, said so")
    # contained in two unrelated roots: ambiguous
    ns = [node("A", "a.czi"), node("B", "b.czi"), node("K", "k.czi")]
    c = R.classify_group(ns, [rel("K", "A", "crop"), rel("K", "B", "crop")])
    check(c["K"]["class"] == R.C_AMBIGUOUS, "a crop that two unrelated files contain is ambiguous")
    # a partial match only
    ns = [node("A", "a.czi"), node("B", "b.czi")]
    c = R.classify_group(ns, [rel("A", "B", complete=False, pieces=4, matched=3, area=0.75)])
    check(c["A"]["class"] == R.C_AMBIGUOUS and "75%" in c["A"]["evidence"], "75% of the tiles match: ambiguous, said so")
    # a time-point subset
    ns = [node("M", "lapse.czi"), node("U", "lapse-subset.czi")]
    c = R.classify_group(ns, [rel("U", "M", pieces=15, n_b=165, scenes_b=(0, 1, 2), n_scenes_b=3)])
    check(c["U"]["class"] == R.C_SUBSET, "same scenes, fewer tiles: a subset")


def test_rank_key():
    print("test_rank_key")
    a = node("a", "plate.czi", "")
    b = node("b", "plate-scale.czi", "P1", scalebar=True)
    check(R.rank_key(a) < R.rank_key(b), "not copy-like beats copy-like, even when the copy has the project")
    c = node("c", "plate.czi", "P1")
    check(R.rank_key(c) < R.rank_key(a), "then a project")
    check(R.copy_like(node("d", "ID1-escala-200um.czi")) and not R.copy_like(node("e", "ID1.czi")),
          "'scale' / 'escala' in the name, or an overlay, make a file copy-like")


def test_lists():
    print("test_lists")
    parent = {"project_name": "AE-biomaGUNE-0721", "size": "1000000"}
    noproj = {"project_name": "", "size": "1000000"}
    blank = {"project_name": "", "size": "10000"}
    own = {"project_name": "AE-biomaGUNE-0721", "size": "10000"}
    other = {"project_name": "AE-biomaGUNE-1321", "size": "10000"}
    big = {"project_name": "", "size": "800000"}
    st = {"AE-biomaGUNE-0721": "active", "AE-biomaGUNE-1019": "closed"}
    d = R.decide_action
    check(d(blank, {"class": R.C_CROP}, parent, st)[0] == "b", "a crop under 5% of its original, original has a project -> list b")
    check(d(big, {"class": R.C_CROP}, parent, st)[0] == "k" and d(big, {"class": R.C_SUBSET}, parent, st)[0] == "k",
          "a larger crop or subset (an ROI re-save) -> list k, for its own decision")
    check(d(dict(blank, size="49999"), {"class": R.C_CROP}, parent, st)[0] == "b"
          and d(dict(blank, size="50000"), {"class": R.C_CROP}, parent, st)[0] == "k",
          "'under 5%' is strict: the boundary is 5% of the original's size")
    check(d(blank, {"class": R.C_SCALEBAR}, parent, st)[0] == "a", "a scale-bar copy -> list a")
    check(d(own, {"class": R.C_RESAVE}, parent, st)[0] == "r", "an identical re-save, same project -> list r")
    check(d(blank, {"class": R.C_CROP}, noproj, st)[0] == "waiting", "the original has no project -> waiting")
    check(d(other, {"class": R.C_CROP}, parent, st)[0] == "conflict", "own project differs from the original's -> conflict")
    check(d(blank, {"class": R.C_CROP}, {"project_name": "AE-biomaGUNE-1019"}, st)[0] == "closed",
          "the original's project is closed -> not listed")
    check(d(blank, {"class": R.C_SPLIT}, parent, st)[0] == "c" and d(blank, {"class": R.C_STITCHED}, noproj, st)[0] == "c",
          "scene splits and stitched copies are Ryan's proposal, never listed")
    check(d(blank, {"class": R.C_ORIGINAL}, None, st)[0] == "stay"
          and d(blank, {"class": R.C_DISTINCT}, None, st)[0] == "stay", "an original / distinct member stays")
    row = {"group": "CELL|2023-06-02T07:11:34.7133079Z", "acq_id": "ACQ-20230602-CELL-002", "class": R.C_CROP,
           "parent_acq_id": "ACQ-20230602-CELL-005", "parent_name": "0721-M113-Kidney-PB-20X.czi",
           "parent_project": "AE-biomaGUNE-0721", "evidence": "4/4 tiles ...", "action": "b",
           "folder": "drive2_MFB-Disco-2/2025-10-02 - Toshiba EXT (Backup)/P/Histologias", "name": "Kidney-PB.czi"}
    dests = {"ACQ-20230602-CELL-002": (r"working\historical_drives\MFB-Disco-2\0721\Histologias", "Kidney-PB.czi")}
    rows = R.list_rows([row, dict(row, acq_id="ACQ-X", action="stay")], "b", dests)
    check(len(rows) == 1 and rows[0]["disposition"] == "derivative" and rows[0]["target_acq_id"] == "ACQ-20230602-CELL-005"
          and rows[0]["to_project"] == "AE-biomaGUNE-0721" and rows[0]["dest_name"] == "Kidney-PB.czi",
          "a list row: derivative of the original, into the original's project, under the planned file name")
    check(rows[0]["subfolder"] == r"working\historical_drives\MFB-Disco-2\0721\Histologias",
          "the subfolder is the planned one (stream A's short-path rule), not the drive folder")
    check([r["acq_id"] for r in R.list_plan_rows([row, dict(row, acq_id="ACQ-X", action="stay"),
                                                  dict(row, acq_id="ACQ-Y", action="k")])] == ["ACQ-20230602-CELL-002", "ACQ-Y"]
          and R.list_plan_rows([row])[0]["to_project"] == "AE-biomaGUNE-0721",
          "the destination plan covers the members of all four lists, with the original's project")
    check("export: crop of 0721-M113-Kidney-PB-20X.czi (ACQ-20230602-CELL-005)" in rows[0]["reason"],
          "the reason names the class and the original")
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "l.csv")
        R.write_list(p, rows)
        raw = open(p, "rb").read()
        check(raw.startswith(b"acq_id,disposition,target_acq_id,to_project,reason,subfolder,dest_name\n")
              and b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf"),
              "the list has the retire tool's header (+ subfolder, dest_name), LF endings, no BOM")
    pi = R.path_issues
    check(pi("P", r"working\historical_drives\d1\a b", "x'y].czi") == [], "apostrophe, bracket and spaces are fine")
    check(pi("P", r"working\d1\a ", "x.czi") != [], "a trailing space on a folder is reported")
    check(pi("P", r"working\d1", "a:b.czi") != [] and pi("P", r"working\con", "x.czi") != [],
          "an illegal character or a reserved name is reported")
    check(pi("P", "w\\" + "x" * 300, "a.czi") != [], "a 300-character component is reported")


def mem_row(acq, relpath, drive="D1", archive="", member="", size="100", sha="a" * 64):
    return {"acq_id": acq, "drive": drive, "relpath": relpath, "archive": archive, "member": member,
            "size": size, "sha256": sha}


def test_destinations():
    print("test_destinations (stream A's short-path rule)")
    try:
        H, NP = D.load_stream_a()
    except D.StreamAMissing as e:
        print(f"  skipped: {e}")
        return
    proj = "AE-biomaGUNE-0999"
    base = "projects\\AE-biomaGUNE-0999\\working\\historical_drives"
    projects = {proj: {"name": proj, "folder_location": "/projects/AE-biomaGUNE-0999"}}
    cr = H.claim_root_segments
    by_key = {cr("Cell observer\\Person\\Study 0999"): {proj},
              cr("Drive\\Stuff.zip!Stuff\\Study 0999 zip"): {proj}}
    members = {
        "A1": mem_row("A1", "Cell observer\\Person\\Study 0999\\ID5\\x.czi"),
        "A2": mem_row("A2", "", archive="Drive\\Stuff.zip", member="Stuff/Study 0999 zip/ID6/y.czi"),
        "A3": mem_row("A3", "Other\\Folder\\z.czi", drive="D2"),
    }
    rows = [{"acq_id": a, "to_project": proj} for a in members]

    def tree(nas):
        os.makedirs(os.path.join(nas, base))
        return os.path.join(nas, base)

    with tempfile.TemporaryDirectory() as nas:
        tree(nas)
        plan = D.plan_destinations(rows, members, nas, by_key=by_key, projects=projects)
        d = plan.dests
        check(d["A1"]["dest"] == base + "\\FRIO-X6\\Study 0999\\ID5\\x.czi",
              "a loose file: <tag>\\<study folder>\\<path below>, everything above the study folder dropped")
        check(d["A1"]["subfolder"] == "working\\historical_drives\\FRIO-X6\\Study 0999\\ID5" and d["A1"]["dest_name"] == "x.czi",
              "the retire list's subfolder is inside the project folder, the name is the file's own")
        check(d["A2"]["dest"] == base + "\\FRIO-X6\\Study 0999 zip\\ID6\\y.czi",
              "an archive member: the archive and its top folder above the study folder are dropped")
        check(d["A3"]["dest"] == base + "\\MFB-Disco-2\\Other\\Folder\\z.czi" and d["A3"]["root"] is None,
              "no study folder on the path: the drive path is kept (as in the holding folder)")
        check(d["A1"]["unc_len"] == len(H.UNC_PREFIX) + len(d["A1"]["dest"]), "the length is measured on \\\\GJESUS3\\gjesus3\\")
        stat, problems = D.check_plan(plan, nas, members)
        check(problems == [] and stat["max_unc"] == max(x["unc_len"] for x in d.values()) and stat["no_root"] == 1,
              "a clean plan: no problem, the longest path and the no-root count reported")
        idx = D.index_rows_for(plan, members, {"A1": "ORIG-1", "A2": "ORIG-2", "A3": "ORIG-3"})[proj]
        r1 = [r for r in idx if r["new_path"].endswith("x.czi")][0]
        check(r1["note"] == "retired derivative of ORIG-1, formerly A1" and r1["drive"] == "drive1_FRIO-X6"
              and r1["original_path"] == "drive1_FRIO-X6\\Cell observer\\Person\\Study 0999\\ID5\\x.czi"
              and r1["sha256"] == "a" * 64 and r1["size"] == "100" and r1["shortened"] == "N",
              "an index row: new path, drive, full original path, size, sha256, the note names the original and the retired id")
        r2 = [r for r in idx if r["new_path"].endswith("y.czi")][0]
        check(r2["archive"] == "Drive\\Stuff.zip" and "Stuff.zip!Stuff\\Study 0999 zip\\ID6\\y.czi" in r2["original_path"],
              "an archive member's index row keeps the archive and the member path")
        nodes = D.planned_nodes(plan)[proj]
        check(nodes.get("D1:Cell observer\\Person\\Study 0999") == "FRIO-X6\\Study 0999"
              and nodes.get("D1:Cell observer\\Person\\Study 0999\\ID5") == "FRIO-X6\\Study 0999\\ID5"
              and nodes.get("D2:Other\\Folder") == "MFB-Disco-2\\Other\\Folder",
              "the folders on the way are what _PATHMAP.csv must freeze")
        origin = D.new_origin_docs(plan, nas)
        key = base + "\\FRIO-X6\\Study 0999\\_ORIGIN.txt"
        check(key in origin and b"drive1_FRIO-X6\\Cell observer\\Person\\Study 0999" in origin[key]
              and not any("MFB-Disco-2" in k for k in origin),
              "a new study folder gets an _ORIGIN.txt naming what was dropped above it; a no-root folder gets none")
        os.makedirs(os.path.join(nas, base, "FRIO-X6", "Study 0999"))
        with open(os.path.join(nas, base, "FRIO-X6", "Study 0999", "_ORIGIN.txt"), "wb") as f:
            f.write(b"A wrote this")
        check(key not in D.new_origin_docs(plan, nas), "an existing _ORIGIN.txt is never replaced")
        # a study folder that is the drive's own top folder: nothing was dropped above it, so no _ORIGIN.txt
        m_top = dict(members, A4=mem_row("A4", "Top\\sub\\w.czi"))
        by_top = dict(by_key)
        by_top[cr("Top")] = {proj}
        plan_top = D.plan_destinations(rows + [{"acq_id": "A4", "to_project": proj}], m_top, nas, by_key=by_top, projects=projects)
        check(plan_top.dests["A4"]["dest"] == base + "\\FRIO-X6\\Top\\sub\\w.czi"
              and not any(k.endswith("FRIO-X6\\Top\\_ORIGIN.txt") for k in D.new_origin_docs(plan_top, nas)),
              "a study folder with nothing above it on the drive gets no _ORIGIN.txt (its path here is its path there)")

    with tempfile.TemporaryDirectory() as nas:        # a folder stream A already placed keeps its frozen name
        t = tree(nas)
        H.write_pathmap(os.path.join(t, "_PATHMAP.csv"),
                        [{"node_key": "D1:Cell observer\\Person\\Study 0999", "rendered": "FRIO-X6\\Study 0999 (kept)"},
                         {"node_key": "D1:Cell observer\\Person\\Study 0999\\ID5", "rendered": "FRIO-X6\\Study 0999 (kept)\\ID5"}])
        plan = D.plan_destinations(rows, members, nas, by_key=by_key, projects=projects)
        check(plan.dests["A1"]["dest"] == base + "\\FRIO-X6\\Study 0999 (kept)\\ID5\\x.czi",
              "the tree's frozen _PATHMAP.csv decides the folder names stream A already used")
        H.write_index(os.path.join(t, "_INDEX.csv"), [
            {"new_path": "FRIO-X6\\Study 0999 (kept)\\ID5\\other.tif", "drive": "drive1_FRIO-X6", "archive": "",
             "original_path": "drive1_FRIO-X6\\Cell observer\\Person\\Study 0999\\ID5\\other.tif", "size": "1", "sha256": "f" * 64,
             "claim_id": "c", "shortened": "N", "why": "", "note": ""},
            {"new_path": "MFB-Disco-2\\Other\\Folder\\Z.CZI", "drive": "drive2_MFB-Disco-2", "archive": "",
             "original_path": "drive2_MFB-Disco-2\\Other\\Folder\\Z.CZI", "size": "1", "sha256": "e" * 64,
             "claim_id": "c", "shortened": "N", "why": "", "note": ""}])
        stat, problems = D.check_plan(plan, nas, members)
        check(stat["folder_agree"] == 2 and stat["folder_differ"] == 0 and stat["in_a_index"] == 1
              and any("_INDEX.csv" in p for p in problems),
              "the same folder as A's other files of that drive folder is counted (A1 and A3 both agree); a "
              "destination already in the index (any case: Z.CZI vs z.czi) is a problem")
        dest = os.path.join(nas, plan.dests["A1"]["dest"])
        os.makedirs(os.path.dirname(dest))
        with open(dest, "wb") as f:
            f.write(b"x")
        check(any("already exists" in p for p in D.check_plan(plan, nas, members)[1]), "a destination that exists is a problem")
        pa1, pa3 = D.check_plan(plan, nas, members, only={"A1"}), D.check_plan(plan, nas, members, only={"A3"})
        check(pa1[0]["items"] == 1 and any("already exists" in p for p in pa1[1]) and not any("_INDEX.csv" in p for p in pa1[1])
              and any("_INDEX.csv" in p for p in pa3[1]) and not any("already exists" in p for p in pa3[1]),
              "check_plan(only=...) judges only those files: between two retire runs only the lists still to run")
        H.write_index(os.path.join(t, "_INDEX.csv"), [
            {"new_path": "FRIO-X6\\Elsewhere\\other.tif", "drive": "drive1_FRIO-X6", "archive": "",
             "original_path": "drive1_FRIO-X6\\Cell observer\\Person\\Study 0999\\ID5\\other.tif", "size": "1", "sha256": "f" * 64,
             "claim_id": "c", "shortened": "N", "why": "", "note": ""}])
        stat, problems = D.check_plan(plan, nas, members)
        check(stat["folder_differ"] == 1 and any("A put the other files" in p for p in problems),
              "A's other files of the same drive folder in another folder is a problem")

    with tempfile.TemporaryDirectory() as nas:        # a promoted study folder and a claim-less sibling in the same folder
        proj7 = "AE-biomaGUNE-0721"                    # one of the projects where stream A groups under the parent
        base7 = "projects\\AE-biomaGUNE-0721\\working\\historical_drives"
        os.makedirs(os.path.join(nas, base7))
        projects7 = {proj7: {"name": proj7, "folder_location": "/projects/AE-biomaGUNE-0721"}}
        key7 = cr("Top\\Lab\\Histologias\\Raw-images")   # a claim made by a file NAME in Raw-images: promoted to its parent
        NP.FILENAME_ROOTS.add(key7)
        try:
            by7 = {key7: {proj7}}
            m7 = {"R1": mem_row("R1", "Top\\Lab\\Histologias\\Raw-images\\a.czi"),
                  "R2": mem_row("R2", "Top\\Lab\\Histologias\\b.czi"),                 # no claim on its path
                  "R3": mem_row("R3", "Top\\Lab\\Histologias\\Raw-images\\sub\\c.czi")}
            rows7 = [{"acq_id": a, "to_project": proj7} for a in m7]
            plan7 = D.plan_destinations(rows7, m7, nas, by_key=by7, projects=projects7)
            ds = {a: d["dest"][len(base7) + 1:] for a, d in plan7.dests.items()}
            check(plan7.dests["R1"]["root"] is not None and plan7.dests["R2"]["root"] is None,
                  "the premise: one file has a (promoted) study folder, its sibling in the parent folder has none")
            check(ds == {"R1": "FRIO-X6\\Histologias\\Raw-images\\a.czi", "R2": "FRIO-X6\\Histologias\\b.czi",
                         "R3": "FRIO-X6\\Histologias\\Raw-images\\sub\\c.czi"},
                  "a folder that is the study folder of any file is one for everything in it: all three share FRIO-X6\\Histologias")
            nodes = D.planned_nodes(plan7)[proj7]
            H.write_pathmap(os.path.join(nas, base7, "_PATHMAP.csv"),
                            [{"node_key": k, "rendered": v} for k, v in sorted(nodes.items())])
            again = D.plan_destinations(rows7, m7, nas, by_key=by7, projects=projects7)
            check({a: d["dest"] for a, d in again.dests.items()} == {a: d["dest"] for a, d in plan7.dests.items()},
                  "re-planning after the index step has frozen every folder gives the same destinations (a fixed point)")
            root_nk = "D1:Top\\Lab\\Histologias"
            H.write_pathmap(os.path.join(nas, base7, "_PATHMAP.csv"), [{"node_key": root_nk, "rendered": nodes[root_nk]}])
            part = D.plan_destinations(rows7, m7, nas, by_key=by7, projects=projects7)
            check({a: d["dest"] for a, d in part.dests.items()} == {a: d["dest"] for a, d in plan7.dests.items()},
                  "and with only the study folder frozen (a partial merge) nothing moves either")
        finally:
            NP.FILENAME_ROOTS.discard(key7)

    with tempfile.TemporaryDirectory() as nas:        # the 240-character budget: the fewest folders are cut
        tree(nas)
        names = ["alpha " + "x" * 70, "beta " + "y" * 70, "gamma " + "z" * 70]
        long_rel = "Cell observer\\Person\\Study 0999\\" + "\\".join(names) + "\\f.czi"
        m2 = {"B1": mem_row("B1", long_rel)}
        plain = H.unc_len(base + "\\FRIO-X6\\Study 0999\\" + "\\".join(names) + "\\f.czi")
        plan = D.plan_destinations([{"acq_id": "B1", "to_project": proj}], m2, nas, by_key=by_key, projects=projects)
        b1 = plan.dests["B1"]
        cut = [c for c in b1["dest"].split("\\") if "~" in c]
        check(plain > 240 and b1["unc_len"] <= 240 and b1["shortened"] and 1 <= len(cut) < 3
              and all(len(c) <= 255 for c in b1["dest"].split("\\")),
              f"a path of {plain} characters is brought to {b1['unc_len']} by cutting {len(cut)} of its 3 long folders")
        check(D.check_plan(plan, nas, m2)[0]["shortened"] == 1, "check_plan counts the shortened files")


def test_merges():
    print("test_merges")
    ex = [{"new_path": "A\\a.tif", "sha256": "1", "note": ""}, {"new_path": "B\\b.tif", "sha256": "2", "note": ""},
          {"new_path": "D\\d.tif", "sha256": "4", "note": ""}]
    new = [{"new_path": "C\\c.czi", "sha256": "3", "note": "retired derivative of X, formerly Y"},
           {"new_path": "E\\e.czi", "sha256": "5", "note": "retired derivative of X, formerly Z"}]
    merged, added, already, conflicts = D.merge_index_rows(ex, new)
    check([r["new_path"] for r in merged] == ["A\\a.tif", "B\\b.tif", "C\\c.czi", "D\\d.tif", "E\\e.czi"]
          and added == 2 and already == 0 and not conflicts and merged[0] is ex[0],
          "new rows are interleaved in path order; the existing rows are the same rows, in the same order")
    again, a2, al2, c2 = D.merge_index_rows(merged, new)
    check(a2 == 0 and al2 == 2 and again == merged and not c2, "merging the same rows again changes nothing")
    clash = [dict(new[0], new_path="b\\B.TIF", sha256="9")]
    m3, a3, _al3, c3 = D.merge_index_rows(ex, clash)
    check(len(c3) == 1 and a3 == 0 and m3 == ex, "a different file at an existing path (any case) is a conflict; nothing is merged")
    check(D.merge_index_rows(ex, [dict(new[0], new_path="a\\A.TIF", sha256="1")])[3] != [],
          "the same bytes at an existing path that is not a retired derivative is still a conflict")
    unsorted = [{"new_path": "Z\\z", "sha256": "1", "note": ""}, {"new_path": "A\\a", "sha256": "2", "note": ""}]
    m4 = D.merge_index_rows(unsorted, new)[0]
    check(m4[:2] == unsorted and [r["new_path"] for r in m4[2:]] == ["C\\c.czi", "E\\e.czi"],
          "an existing index that is not sorted keeps its order; the new rows are appended")
    pm = [{"node_key": "D1:a", "rendered": "FRIO-X6\\a"}]
    rows, n, conf = D.merge_pathmap_rows(pm, {"D1:a": "FRIO-X6\\a", "D1:b": "FRIO-X6\\b"})
    check(n == 1 and not conf and [r["node_key"] for r in rows] == ["D1:a", "D1:b"], "a new folder is added to the pathmap")
    rows, n, conf = D.merge_pathmap_rows(pm, {"D1:a": "FRIO-X6\\other"})
    check(n == 0 and len(conf) == 1 and rows == pm, "a frozen folder keeps its name: another rendering is a conflict")
    import types
    stub = types.SimpleNamespace(INDEX_FIELDS=["new_path", "drive", "note"])
    b = D.serialize_index([{"new_path": "x", "drive": "d", "note": "café"}], stub)
    check(b.startswith(b"\xef\xbb\xbf") and b.endswith(b"\r\n") and b"\n" not in b.replace(b"\r\n", b""),
          "_INDEX.csv is written as stream A writes it: UTF-8 with a BOM, CRLF")
    check(D.serialize_pathmap([{"node_key": "k", "rendered": "r"}]) == b"\xef\xbb\xbfnode_key,rendered\r\nk,r\r\n",
          "_PATHMAP.csv likewise")
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "i.csv")
        rows_in = [{"new_path": "x\\y,z", "drive": "d", "note": 'say "hi"'}, {"new_path": "q", "drive": "", "note": "café"}]
        with open(p, "wb") as f:
            f.write(D.serialize_index(rows_in, stub))
        check(D.rcsv(p) == rows_in and D.serialize_index(D.rcsv(p), stub) == open(p, "rb").read(),
              "an index re-serialises byte for byte (quoting, accents), so a merge cannot change A's rows")
    full = ["new_path", "drive", "archive", "original_path", "size", "sha256", "claim_id", "shortened", "why", "note"]
    older = [f for f in full if f != "why"]                       # stream A added `why` after writing some trees
    stub10 = types.SimpleNamespace(INDEX_FIELDS=full)
    check(D.index_fields_problem(older, stub10) is None and D.index_fields_problem(full, stub10) is None,
          "an older 9-column index (no `why`) can take our rows")
    check("missing" in D.index_fields_problem(["new_path", "note"], stub10)
          and "unknown" in D.index_fields_problem(older + ["bogus"], stub10), "a header that lacks a column we fill, or has an unknown one, is refused")
    row = {f: "" for f in full}
    row.update(new_path="a", drive="d", note="n", why="ignored here")
    b9 = D.serialize_index([row], stub10, older)
    check(b9.decode("utf-8-sig").splitlines()[0] == ",".join(older) and b"ignored here" not in b9,
          "merging under an older header keeps that header (no `why` column is added)")
    check(D.split_dest("projects\\P1\\working\\historical_drives\\FRIO-X6\\S\\f.czi", "P1")
          == ("working\\historical_drives\\FRIO-X6\\S", "f.czi"), "a destination splits into the retire list's subfolder and name")


def main():
    for t in (test_helpers, test_destinations, test_merges, test_staged_path, test_haystack, test_hash_match,
              test_crop_and_stitch, test_retile, test_retrim, test_region, test_informative, test_similarity,
              test_classify, test_rank_key, test_lists):
        t()
    print()
    if FAILS:
        print(f"FAILED: {len(FAILS)}")
        for f in FAILS:
            print("  -", f)
        return 1
    print("ALL PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
