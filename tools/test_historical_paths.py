#!/usr/bin/env python3
"""test_historical_paths.py -- the destination rule for historical-drive material
(tools/drive_staging/historical_paths.py), pinned to Ryan's 2026-10-02 decision: no paths that throw
errors, no zips; drop high-level folders, shorten the fewest, keep an index so nothing is lost.

Run:  python tools/test_historical_paths.py
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "drive_staging"))
import historical_paths as H  # noqa: E402

FAILS = []
BASE = r"projects\AE-biomaGUNE-1019\working\historical_drives"
MJI = "Drive Maria Jesus and Irati 20211209.zip"
MJI_ROOT = MJI + r"!\Drive Maria Jesus and Irati 20211209\Pili y Mili\Proyecto 1019 Envejecimiento y dieta"


def check(cond, msg):
    print(f"  {'ok:  ' if cond else 'FAIL:'} {msg}")
    if not cond:
        FAILS.append(msg)


def item(i, member=None, relpath=None, archive=MJI, root=MJI_ROOT, drive="D1"):
    return H.Item(id=i, drive=drive, relpath=relpath or archive, archive=archive if member else "",
                  member=member or "", root=H.claim_root_segments(root) if root else None)


def test_root_and_drops():
    print("root folder first; everything above it dropped")
    p = H.Planner(BASE)
    it = item("a", "Drive Maria Jesus and Irati 20211209/Pili y Mili/Proyecto 1019 Envejecimiento y dieta/MRI/x.xlsx")
    d = p.plan([it])["a"]
    check(d == BASE + r"\FRIO-X6\Proyecto 1019 Envejecimiento y dieta\MRI\x.xlsx", d)
    o = p.origins([it])
    check(list(o.values())[0][0].startswith(r"drive1_FRIO-X6\Drive Maria Jesus and Irati 20211209.zip!"),
          f"_ORIGIN records the dropped path {o}")
    # a loose file under a loose claim root
    p = H.Planner(r"projects\AE-biomaGUNE-1123\working\historical_drives")
    it = H.Item(id="b", drive="D1", relpath=r"Cell observer\AINHIZE\1123\HE\ID 110.tif",
                root=H.claim_root_segments(r"Cell observer\AINHIZE\1123"))
    d = p.plan([it])["b"]
    check(d.endswith(r"\FRIO-X6\1123\HE\ID 110.tif"), d)
    # accents lost in the claims pass still find the root
    it = H.Item(id="c", drive="D1", relpath=r"A\Biodistribución\x.tif", root=H.claim_root_segments("A\\Biodistribuci�n"))
    check(H.Planner("b").plan([it])["c"].endswith(r"FRIO-X6\Biodistribución\x.tif"), "accent-blind root match")


def test_archives_below_root():
    print("an archive below the root becomes <stem>_<ext>, its repeated top folder dropped")
    p = H.Planner(BASE)
    it = H.Item(id="a", drive="D1", relpath=r"Former students\Manon.zip", archive=r"Former students\Manon.zip",
                member="Manon/Trucs/x.docx", root=H.claim_root_segments("Former students"))
    check(p.plan([it])["a"].endswith(r"FRIO-X6\Former students\Manon_zip\Trucs\x.docx"), p.plan([it])["a"])
    # nested archive member, no root (holding): full path, two archive folders
    p = H.Planner(r"staging\historical_drives_unassigned")
    it = H.Item(id="n", drive="D1", relpath="Drive zuri 170823.zip", archive="Drive zuri 170823.zip",
                member="Drive zuri 170823/Proyecto Cav1 CNIC/KI67 cav1 190423.zip!KI67 cav1 190423/35/a.tif")
    d = p.plan([it])["n"]
    check(d == r"staging\historical_drives_unassigned\FRIO-X6\Drive zuri 170823_zip\Proyecto Cav1 CNIC\KI67 cav1 190423_zip\35\a.tif", d)


def test_same_named_roots():
    print("two different roots with the same name get (2)")
    p = H.Planner(BASE)
    a = H.Item(id="a", drive="D1", relpath=r"X\MRI\a.txt", root=H.claim_root_segments(r"X\MRI"))
    b = H.Item(id="b", drive="D1", relpath=r"Y\MRI\b.txt", root=H.claim_root_segments(r"Y\MRI"))
    d = p.plan([a, b])
    check(d["a"].endswith(r"FRIO-X6\MRI\a.txt") and d["b"].endswith(r"FRIO-X6\MRI (2)\b.txt"), str(d))
    c = H.Item(id="c", drive="D2", relpath=r"Z\MRI\c.txt", root=H.claim_root_segments(r"Z\MRI"))
    check(H.Planner(BASE).plan([a, c])["c"].endswith(r"MFB-Disco-2\MRI\c.txt"), "same name on the other drive: no suffix")


def _deep(i, leaf="data.xlsx", sub="Sub"):
    long1 = "Comparasion expiration vs inspiraiton experiment series"
    long2 = "20201013_103404_jrc201013_m7_1019_1_1_extra_long_folder_name"
    return H.Item(id=i, drive="D1", relpath=rf"R\Proyecto 1019 Envejecimiento y dieta\{long1}\{long2}\{sub}\{leaf}",
                  root=H.claim_root_segments(r"R\Proyecto 1019 Envejecimiento y dieta"))


def test_budget_fewest_and_consistent():
    print("budget: the fewest folders shortened, a folder for everything in it")
    p = H.Planner(BASE)
    items = [_deep("a"), _deep("b", "b.xlsx"), _deep("c", "c" * 30 + ".xlsx", "OtherSub")]
    before = {it.id: len(H.UNC_PREFIX + BASE) + 1 for it in items}
    d = p.plan(items)
    check(all(H.unc_len(v) <= H.BUDGET for v in d.values()), f"all within {H.BUDGET}: {[H.unc_len(v) for v in d.values()]}")
    fa, fb = os.path.dirname(d["a"]), os.path.dirname(d["b"])
    check(fa == fb, "siblings stay in one folder")
    check("~" in d["a"], f"something was shortened: {d['a']}")
    check(items[0].extra["shortened"], "the index flag says shortened")
    # a short path is untouched
    q = H.Planner(BASE)
    s = H.Item(id="s", drive="D1", relpath=r"R\P\a.txt", root=H.claim_root_segments(r"R\P"))
    check(q.plan([s])["s"] == BASE + r"\FRIO-X6\P\a.txt" and not s.extra["shortened"], "short paths untouched")
    # a file whose own name alone breaks the budget: only the stem is cut, the extension kept
    r = H.Planner(BASE)
    f = H.Item(id="f", drive="D1", relpath="R\\P\\" + "n" * 230 + ".tif", root=H.claim_root_segments(r"R\P"))
    df = r.plan([f])["f"]
    check(H.unc_len(df) <= H.BUDGET and df.endswith(".tif") and "~" in os.path.basename(df), df)


def test_cut_order():
    print("cut order: sub-folders before the study folder, folders before the file name")
    # solvable by cutting the two long SUB-folders alone: then neither the study folder nor the file
    # name may be touched (a case that needs more is allowed to cut the study folder at 24, then the
    # file name -- the RANK table in historical_paths.py)
    study = "Proyecto 1019 Envejecimiento y dieta"
    subs = ["Comparasion expiration vs inspiraiton", "Documentos para la subsanacion final"]
    leaf = "for-ep-10v04_formulario_uso_de_roedores_modificados_geneticamente_mpv17.docx"
    it = H.Item(id="a", drive="D1", relpath="R\\" + study + "\\" + "\\".join(subs) + "\\" + leaf,
                root=H.claim_root_segments("R\\" + study))
    d = H.Planner(BASE).plan([it])["a"]
    parts = d.split("\\")
    check(H.unc_len(d) <= H.BUDGET, f"within budget ({H.unc_len(d)})")
    check(parts[5] == study, f"the study folder is kept whole: {parts[5]}")
    check(parts[-1] == leaf, f"the file name is kept whole: {parts[-1]}")


def test_frozen_pathmap():
    print("a later run never renames a folder already placed")
    tmp = tempfile.mkdtemp(prefix="hp_")
    try:
        p = H.Planner(BASE)
        first = _deep("a")
        d1 = p.plan([first])
        pm = os.path.join(tmp, H.PATHMAP_NAME)
        H.write_pathmap(pm, p.pathmap_rows())
        # later: a new, deeper file inside the SAME folders pushes the budget
        q = H.Planner(BASE)
        n = q.load_pathmap(pm)
        new = _deep("z", "z.xlsx", "Sub\\Another very long nested folder name here")
        d2 = q.plan([new])
        check(n > 0, f"pathmap loaded ({n} folders)")
        check(d2["z"].startswith(os.path.dirname(d1["a"])), f"existing folders keep their names:\n      {d1['a']}\n      {d2['z']}")
        check(H.unc_len(d2["z"]) <= H.BUDGET, "and the new file is still within budget")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_pinned_files():
    print("a file already placed keeps its recorded path, even a shortened file name")
    tmp = tempfile.mkdtemp(prefix="hp_pin_")
    try:
        first = _deep("a", "UNIVERSAL_12112020_085550_(1_No-Stain Labeled Membrane).tif")
        p = H.Planner(BASE, budget=200)          # tight budget: the first run cuts the file name too
        d1 = p.plan([first])["a"]
        H.write_pathmap(os.path.join(tmp, H.PATHMAP_NAME), p.pathmap_rows())
        H.write_index(os.path.join(tmp, H.INDEX_NAME), H.index_rows({"a": d1}, [first], BASE))
        q = H.Planner(BASE, budget=200)
        q.load_pathmap(os.path.join(tmp, H.PATHMAP_NAME))
        n = q.load_index(os.path.join(tmp, H.INDEX_NAME))
        again = _deep("a", "UNIVERSAL_12112020_085550_(1_No-Stain Labeled Membrane).tif")
        d2 = q.plan([again])["a"]
        check(n == 1 and d2 == d1, f"same path on a re-plan:\n      {d1}\n      {d2}")
        check(again.extra["shortened"] == ("~" in os.path.basename(d1) or "~" in d1), "shortened flag kept")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_uniqueness():
    print("two originals never share a destination")
    p = H.Planner(BASE)
    a = H.Item(id="a", drive="D1", relpath=r"R\P\X.txt", root=H.claim_root_segments(r"R\P"))
    b = H.Item(id="b", drive="D1", relpath=r"R\P\x.TXT", root=H.claim_root_segments(r"R\P"))
    try:
        p.plan([a, b])
        check(False, "case-insensitive duplicate must raise")
    except H.BudgetError:
        check(True, "case-insensitive duplicate raises")
    check(H.short_name("A" * 30 + "x") != H.short_name("A" * 30 + "y"), "same prefix, different names -> different short names")


def test_cli():
    print("CLI")
    rc = H.main(["dest", "--base", BASE, "--drive", "D1", "--relpath", r"R\P\a.txt", "--root", r"R\P"])
    check(rc == 0, "dest returns 0")


if __name__ == "__main__":
    test_root_and_drops()
    test_archives_below_root()
    test_same_named_roots()
    test_budget_fewest_and_consistent()
    test_cut_order()
    test_frozen_pathmap()
    test_pinned_files()
    test_uniqueness()
    test_cli()
    print(f"\n{'FAILED: ' + str(len(FAILS)) if FAILS else 'all passed'}")
    sys.exit(1 if FAILS else 0)
