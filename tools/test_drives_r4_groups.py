#!/usr/bin/env python3
"""test_drives_r4_groups.py -- the logic of tools/drive_staging/r4_groups.py (the same-timestamp group
clean-up of the drives .czi ingest), on synthetic tiles: no .czi file, no NAS, no D: needed.

  1. subfolder_for: the retire list's `subfolder` is working\\historical_drives\\<drive label>\\<folder
     on the drive> (Ryan, 2026-10-02), the archive's own name included for a member.
  2. staged_path: where a plan row's staged / extracted copy lives.
  3. Haystack.locate: a byte-exact sub-array is found at its position, a near miss is not.
  4. hash_match: identical tiles at one offset; a scene split; a partial match is not complete.
  5. crop_match / stitch_match on tiles written to a scratch file the way a .czi stores them.
  6. classify_group: original + crop + scale-bar copy of the crop; master + scene splits; siblings;
     pixel-identical twins; a stitched copy; a member contained in two unrelated files.
  7. the original of a set of identical files (rank_key) and the retire-list row.

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


def main():
    for t in (test_subfolder_for, test_staged_path, test_haystack, test_hash_match, test_crop_and_stitch,
              test_classify, test_rank_key):
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
