#!/usr/bin/env python3
"""test_drives_r4_groups.py -- the logic of tools/drive_staging/r4_groups.py (the same-timestamp group
clean-up of the drives .czi ingest), on synthetic tiles: no .czi file, no NAS, no D: needed.

  1. subfolder_for: the retire list's `subfolder` is working\\historical_drives\\<drive label>\\<folder
     on the drive> (Ryan, 2026-10-02), the archive's own name included for a member.
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

def test_subfolder_for():
    print("test_subfolder_for")
    f = R.subfolder_for
    check(f("drive1_FRIO-X6/Cell observer/AINHIZE/1123/ID 7-20/PR/x.czi")
          == r"working\historical_drives\drive1_FRIO-X6\Cell observer\AINHIZE\1123\ID 7-20\PR",
          "drive 1 loose file: the drive label and the folder, backslashes")
    check(f("drive2_MFB-Disco-2/2025-10-02 - Toshiba EXT (Backup)/Proyectos/LP+IONP/Histologias/Raw-images/a.czi")
          == r"working\historical_drives\drive2_MFB-Disco-2\2025-10-02 - Toshiba EXT (Backup)\Proyectos\LP+IONP"
             r"\Histologias\Raw-images",
          "drive 2: spaces, parentheses and + survive")
    check(f("drive1_FRIO-X6/Haizpea_2020-2022.7z/Haizpea_2020-2022/project0420/x/id2.czi")
          == r"working\historical_drives\drive1_FRIO-X6\Haizpea_2020-2022.7z\Haizpea_2020-2022\project0420\x",
          "an archive member keeps the archive's own name as a folder")
    try:
        f("a.czi")
        check(False, "a name with no folder is refused")
    except ValueError:
        check(True, "a name with no folder is refused")
    check(R.basename("drive1_FRIO-X6/a/b/c d.czi") == "c d.czi" and R.dirname("x/y/z.czi") == "x/y",
          "basename / dirname split on the forward slash")


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
    rows = R.list_rows([row, dict(row, acq_id="ACQ-X", action="stay")], "b")
    check(len(rows) == 1 and rows[0]["disposition"] == "derivative" and rows[0]["target_acq_id"] == "ACQ-20230602-CELL-005"
          and rows[0]["to_project"] == "AE-biomaGUNE-0721" and rows[0]["dest_name"] == "Kidney-PB.czi",
          "a list row: derivative of the original, into the original's project, under the file's own name")
    check(rows[0]["subfolder"] == r"working\historical_drives\drive2_MFB-Disco-2\2025-10-02 - Toshiba EXT (Backup)\P\Histologias",
          "the subfolder mirrors the drive folder")
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


def main():
    for t in (test_subfolder_for, test_staged_path, test_haystack, test_hash_match, test_crop_and_stitch,
              test_retile, test_retrim, test_region, test_informative, test_similarity, test_classify, test_rank_key,
              test_lists):
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
