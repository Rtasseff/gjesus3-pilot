#!/usr/bin/env python3
"""test_nonraw_placement.py -- the rules of the historical drives' non-raw placement
(tools/drive_staging/nonraw_placement.py), pinned to what Ryan decided on 2026-10-01/02.

  1. Destination layout: projects\\<folder>\\working\\historical_drives\\<label>\\<original path>;
     an archive member goes under `<archive stem>_<ext>\\<member path>`.
  2. The decision order: LEONE -> C; R3 derivatives placed in their parent's project; czi-raw never
     placed (the dot-file is the raw one-off); software/system/installers/personal/zero-byte
     excluded; imaging classes and their directories -> B; lsm and no-claim/(C) -> holding;
     (B) and the nested 0720 -> Project-0521; closed projects listed, not placed.
  3. The copy: verified, never overwrites, idempotent on identical bytes, provenance appended once.

Run:  python tools/test_nonraw_placement.py
"""
import csv
import hashlib
import os
import shutil
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "drive_staging"))
sys.path.insert(0, HERE)
import nonraw_placement as N  # noqa: E402

FAILS = []


def check(cond, msg):
    print(f"  {'ok:  ' if cond else 'FAIL:'} {msg}")
    if not cond:
        FAILS.append(msg)


PROJECTS = {
    "AE-biomaGUNE-1123": {"project_id": "PROJ-0014", "status": "active",
                          "folder_location": "/projects/AE-biomaGUNE-1123/"},
    "AE-biomaGUNE-1519": {"project_id": "PROJ-0008", "status": "closed",
                          "folder_location": "/projects/AE-biomaGUNE-1519/"},
}
CTX = {"projects": PROJECTS}


def rec(**kw):
    r = {"drive": "D1", "relpath": "a\\b.png", "archive": "", "member": "", "class": "figure",
         "flag": "", "size": "10", "verdict": "CONFIRMED", "proposed_project": "AE-biomaGUNE-1123",
         "imaging_root": None, "excluded_reason": None, "derived": None, "ingested": False,
         "from_b_kind": ""}
    r.update(kw)
    return r


def test_layout():
    print("layout")
    check(N.archive_folder_name("Manon.zip") == "Manon_zip", "Manon.zip -> Manon_zip")
    check(N.archive_folder_name("Haizpea_2020-2022.7z") == "Haizpea_2020-2022_7z", "7z stem")
    d = N.dest_rel("AE-biomaGUNE-1123", "drive1_FRIO-X6", "Cell observer\\X\\y.tif")
    check(d == "projects\\AE-biomaGUNE-1123\\working\\historical_drives\\drive1_FRIO-X6\\Cell observer\\X\\y.tif",
          f"loose dest {d}")
    d = N.dest_rel("Project-0521", "drive1_FRIO-X6", "Drive MJ.zip", "Drive MJ.zip", "Pili y Mili/P 0521/a.docx")
    check(d.endswith("drive1_FRIO-X6\\Drive MJ_zip\\Pili y Mili\\P 0521\\a.docx"), f"member dest {d}")
    d = N.dest_rel("P", "L", "x\\y\\in.zip", "x\\y\\in.zip", "m.txt")
    check(d.endswith("L\\x\\y\\in_zip\\m.txt"), f"nested-dir archive dest {d}")
    d = N.dest_rel("P", "L", "Drive zuri 170823.zip", "Drive zuri 170823.zip",
                   "Drive zuri 170823/Proyecto Cav1 CNIC/KI67 cav1 190423.zip!a/b.tif")
    check(d.endswith("L\\Drive zuri 170823_zip\\Drive zuri 170823\\Proyecto Cav1 CNIC\\KI67 cav1 190423_zip\\a\\b.tif"),
          f"nested-archive member dest {d}")
    check(N.member_key("H_2020\\p0420\\Modificaci�n 0420.doc") == N.member_key("H_2020/p0420/Modificación 0420.doc"),
          "member key: backslash + lost accent match the catalog's form")
    h = N.holding_rel("drive2_MFB-Disco-2", "a\\b.txt")
    check(h == "staging\\historical_drives_unassigned\\drive2_MFB-Disco-2\\a\\b.txt", f"holding {h}")


def test_decide():
    print("decide")
    D = lambda **kw: N.decide(rec(**kw), CTX)  # noqa: E731
    check(D()[0] == "place" and D()[2] == "AE-biomaGUNE-1123", "confirmed figure -> place")
    check(D(verdict="A")[0] == "place", "(A) -> place")
    check(D(verdict="", proposed_project="")[0] == "holding", "no claim -> holding")
    check(D(verdict="C", proposed_project="")[0] == "holding", "(C) -> holding")
    check(D(verdict="B", proposed_project="Project-0521")[2] == "Project-0521", "(B) 0521 -> Project-0521")
    check(D(verdict="B", proposed_project="Project-0720")[2] == "Project-0521", "(B) 0720 folds into Project-0521")
    check(D(verdict="B", proposed_project="Project-0924")[0] == "holding",
          "(B) 0924 (drive 3, 2 CEEA documents, no project) -> holding, NOT Project-0521")
    check(D(verdict="B", proposed_project="")[0] == "holding", "(B) without a proposed project -> holding")
    r = D(verdict="C", proposed_project="", archive="Z.zip", relpath="Z.zip",
          member="Pili y Mili/Proyecto 0521 iNO/Antiguo proyecto 0720/doc.pdf")
    check(r[0] == "place" and r[2] == "Project-0521", "nested 0720 folds into Project-0521")
    check(D(proposed_project="AE-biomaGUNE-1519")[0] == "closed-project", "closed project -> listed")
    check(D(proposed_project="AE-biomaGUNE-1116")[0] == "place", "approved-new project -> place")
    check(D(proposed_project="AE-biomaGUNE-9999")[0] == "unclear", "unknown project -> unclear")
    check(D(**{"class": "czi-raw"})[0] == "exclude", "czi-raw never placed")
    check(D(**{"class": "czi-raw", "excluded_reason": "resave-of-production"})[1].endswith("(resave-of-production)"),
          "re-save excluded with its reason")
    check(D(**{"class": "czi-raw", "excluded_reason": "hidden-dotfile"})[0] == "raw-oneoff", "dot-file -> raw one-off")
    der = {"why": "scale-bar copy", "parent_acq_ids": "ACQ-1", "project": "AE-biomaGUNE-1123"}
    check(D(**{"class": "czi-raw", "derived": der, "verdict": ""})[0:3:2] == ("place", "AE-biomaGUNE-1123"),
          "R3 derivative placed in its parent's project, whatever its own claim")
    check(D(**{"class": "software"})[0] == "exclude", "software excluded")
    check(D(**{"class": "system"})[0] == "exclude", "system excluded")
    check(D(relpath="a\\._x.pzfx", **{"class": "analysis"})[0] == "exclude", "macOS ._ stub excluded")
    check(D(archive="z.zip", relpath="z.zip", member="d/._y.tif", **{"class": "tif"})[0] == "exclude", "._ stub in an archive excluded")
    check(D(flag="personal-admin-heuristic:cv")[1] == "personal-admin-heuristic", "personal excluded")
    check(D(size="0", flag="zero-byte")[1] == "zero-byte", "zero-byte excluded")
    check(D(**{"class": "bruker"})[1].startswith("B?"), "imaging class outside the roots -> B, flagged")
    check(D(**{"class": "other"}, imaging_root="mri: x")[0] == "other-stream", "file under a B root -> B")
    check(D(**{"class": "lsm"})[0] == "holding", "lsm -> holding even under a claim")
    check(D(relpath="LEONE.zip", **{"class": "archive"})[1].startswith("C:"), "LEONE -> C")
    check(D(archive="LEONE.zip", member="x/y.dcm")[1].startswith("C:"), "LEONE member -> C")
    inst = "2025-10-02 - Toshiba EXT (Backup)\\Origin\\OriginPro_2019b.part1_Downloadly.ir.rar"
    check(D(relpath=inst, **{"class": "archive"})[0] == "exclude", "installer archive excluded")
    check(D(relpath="x\\Manon.zip", **{"class": "archive"})[0] == "expanded", "archive -> expanded")
    check(D(**{"class": "czi-unreadable"}, size="5")[0] == "holding", "unreadable czi with bytes -> holding (Ryan)")
    check(D(**{"class": "bruker"}, imaging_root="nmr: x", nmr=True)[0] == "holding", "TopSpin NMR -> holding (Ryan)")
    exps = N.load_nmr("/nonexistent")
    exps[("D1", "-")].add(("former students", "lydia", "nmr", "zblm 1", "1"))
    exps[("D1", "Drive zuri 170823.zip")].add(("drive zuri 170823", "muestras hospital clinic 180723", "zb.11", "1"))
    check(N.is_nmr(exps, "D1", "", r"Former students\Lydia\NMR\ZBLM 1\1\acqus"), "loose experiment file matched")
    check(not N.is_nmr(exps, "D1", "", r"Former students\Lydia\NMR\ZBLM 1\10\acqus"), "a sibling experiment is not")
    check(N.is_nmr(exps, "D1", "Drive zuri 170823.zip",
                   "Drive zuri 170823/Muestras hospital clinic 180723.zip!Muestras hospital clinic 180723/ZB.11/1/acqu"),
          "nested-archive experiment matched in B's folder view")
    # stream B's non-raw list overrides the imaging root and the imaging class
    r = D(**{"class": "volume"}, imaging_root="mri: x", from_b="AE-biomaGUNE-1123")
    check(r[0] == "place" and r[2] == "AE-biomaGUNE-1123", "B->A row with a project -> place")
    check(D(**{"class": "volume"}, imaging_root="mri: x", from_b="")[0] == "holding", "B->A row, no project -> holding")
    check(D(from_b="AE-biomaGUNE-1519")[0] == "closed-project", "B->A row into a closed project -> listed")
    check(D(**{"class": "system"}, from_b="AE-biomaGUNE-1123")[0] == "exclude", "B->A system file still excluded")
    zr = dict(relpath="Former students\\Lydia\\NMR\\ZBLM.zip", **{"class": "archive"})
    check(D(imaging_root="nmr: x", **zr)[0] == "other-stream", "archive under a B root stays B's")
    check(D(imaging_root="mri: x", from_b="", **zr)[0] == "expanded", "archive B handed over -> expanded")
    # nested-archive specials
    n = {"nested": "Z/Gastos Giessen/Meals cost original documents.zip", "class": "document", "ext": ".pdf"}
    check(N.nested_special(n)[0] == "exclude", "meal receipts excluded")
    n = {"nested": "Z/Proyecto Cav1 CNIC/8583.zip", "class": "czi-raw", "ext": ".czi"}
    check(N.nested_special(n)[0] == "raw-oneoff", "nested czi-raw -> raw one-off")
    n = {"nested": "Z/PAPERS/T.zip", "class": "other", "ext": ".svs"}
    check(N.nested_special(n)[0] == "holding", ".svs -> holding (Ryan)")
    check(D(special=("raw-oneoff", "x", None), **{"class": "czi-raw"})[0] == "raw-oneoff", "special wins over czi-raw")


def test_roots():
    print("imaging roots (stream B)")
    import io as _io
    tmp = tempfile.mkdtemp(prefix="nonraw_roots_")
    try:
        p = os.path.join(tmp, "roots.csv")
        with _io.open(p, "w", encoding="utf-8", newline="") as f:
            f.write("drive,archive,path_prefix,kind,files,gb,note\n"
                    "D1,-,Former students\\Lydia\\NMR,nmr,1,0,x\n"
                    "D1,Cardiac MRI.zip,,mri,1,0,whole\n"
                    "D1,H.7z,H/project0420/MRI_0420,mri,1,0,x\n")
        R = N.load_imaging_roots(p)
        check(N.imaging_root(R, "D1", "-", "Former students\\Lydia\\NMR\\ZBLM.zip"), "loose file under a root")
        check(N.imaging_root(R, "D1", "-", "Former students\\Lydia\\NMR") is not None, "the root itself")
        check(N.imaging_root(R, "D1", "-", "Former students\\Lydia\\NMRx\\a.txt") is None, "prefix is per folder, not per string")
        check(N.imaging_root(R, "D2", "-", "Former students\\Lydia\\NMR\\a") is None, "drive matters")
        check(N.imaging_root(R, "D1", "Cardiac MRI.zip", "Cardiac MRI/anything.txt"), "whole archive")
        check(N.imaging_root(R, "D1", "H.7z", "H/project0420/MRI_0420/1/acqp"), "member under a member root")
        check(N.imaging_root(R, "D1", "H.7z", "H/project0420/histo/a.tif") is None, "member outside -> mine")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_worksheet_roundtrip():
    print("2b worksheet round trip (Excel on a Spanish-locale machine)")
    g = N.group_key("D1", "Zuriñe", "Former students\\Zuriñe\\0 IMAGEN CONFOCAL\\a\\b.tif", "", "")
    check(g[:3] == ("D1", "Zuriñe", "0 IMAGEN CONFOCAL"), f"loose group {g}")
    g = N.group_key("D1", "zuri", "Drive zuri 170823.zip", "", "", "Drive zuri 170823/PAPERS/x/y.pdf")
    check(g[2] == "Drive zuri 170823.zip!PAPERS/x", f"drive-root archive: first two folders below its top {g[2]}")
    g = N.group_key("D1", "Zuriñe", r"Former students\Zuriñe\0 IMAGEN CONFOCAL\CDH5\F.zip", "", "", "ki67/C PBS/a.tif")
    check(g[2] == "0 IMAGEN CONFOCAL", f"archive inside a researcher folder joins that folder's group {g[2]}")
    check(N.group_key("D1", "X", "a\\b.tif", "C", "CL-0473")[2] == "(C) CL-0473", "(C) group = claim id")
    key = N.key_string("D1", "Zuriñe", "0 IMAGEN CONFOCAL")
    tmp = tempfile.mkdtemp(prefix="nonraw_ws_")
    try:
        # what Excel (es-ES) writes on "Save as CSV": `;` separators, cp1252, no BOM
        p = os.path.join(tmp, "ws_excel.csv")
        with open(p, "wb") as f:
            f.write(("group;project;note_for_ryan;group_key\r\n"
                     f"G001;AE-biomaGUNE-1123;ok;{key}\r\n"
                     "G002;;;D1|Laura|Cell observer\r\n").encode("cp1252"))
        m = N.load_mapping(p)
        check(m == {N.norm_key(key): "AE-biomaGUNE-1123"}, f"; + cp1252 read, blank project skipped: {m}")
        # the same, saved as "CSV UTF-8" with commas and a BOM
        p2 = os.path.join(tmp, "ws_utf8.csv")
        with open(p2, "w", encoding="utf-8-sig", newline="") as f:
            f.write(f"group,project,group_key\r\nG001,AE-biomaGUNE-1123,{key}\r\n")
        check(N.load_mapping(p2) == m, "UTF-8 + BOM read gives the same mapping")
        # an accent lost on the way still joins
        check(N.norm_key("D1|Zuri?e|0 IMAGEN CONFOCAL") == N.norm_key(key), "lost ñ still joins")
        # a deleted group_key column must stop the run, not silently map nothing
        p3 = os.path.join(tmp, "ws_bad.csv")
        with open(p3, "w", encoding="utf-8", newline="") as f:
            f.write("group,project\r\nG001,AE-biomaGUNE-1123\r\n")
        try:
            N.load_mapping(p3)
            check(False, "a mapped row without group_key must stop")
        except SystemExit:
            check(True, "a mapped row without group_key stops the run")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_link_names():
    print("2b raw links: unique names in a flat raw_linked\\ (the ingest's rule)")
    rows = [{"acq_id": "ACQ-1", "instrument": "CELL", "original_name": "d1/a/10x-1.czi", "acquisition_datetime": "2023-05-03T10:00"},
            {"acq_id": "ACQ-2", "instrument": "CELL", "original_name": "d1/b/10x-1.czi", "acquisition_datetime": "2023-05-04T10:00"},
            {"acq_id": "ACQ-3", "instrument": "CELL", "original_name": "d1/c/10x-1.czi", "acquisition_datetime": "2023-05-04T11:00"}]
    n = N.link_names_for(rows, "/nonexistent", taken={"cell_10x-1.czi"})
    check(n["ACQ-1"] == "CELL_10x-1_20230503.czi", f"existing name taken -> date suffix {n['ACQ-1']}")
    check(n["ACQ-2"] == "CELL_10x-1_20230504.czi", f"next one gets its own date {n['ACQ-2']}")
    check(n["ACQ-3"] == "CELL_10x-1_ACQ-3.czi", f"same name, same day -> ACQ-ID suffix {n['ACQ-3']}")
    check(len(set(v.lower() for v in n.values())) == 3, "all unique")


def test_remap():
    print("2b remap from a stored manifest (no catalog, no D:)")
    base = {"drive": "D1", "drive_label": "drive1_FRIO-X6", "archive": "", "member": "", "verdict": "",
            "claim_id": "", "class": "tif", "size": "5", "sha256": "x", "project_name": "", "project_id": "",
            "project_status": "", "note": ""}
    rows = [dict(base, relpath="Cell observer\\Laura\\Cell observer\\Gota\\a.tif", researcher="Laura",
                 decision="holding", reason="no claim", dest_rel="staging\\x"),
            dict(base, relpath="Cell observer\\Laura\\Cell observer\\Gota\\b.lsm", researcher="Laura",
                 decision="holding", reason="lsm", dest_rel="staging\\y", **{"class": "lsm"}),
            dict(base, relpath="Other\\Z\\c.tif", researcher="Z", decision="holding", reason="no claim", dest_rel="s")]
    rows[1]["class"] = "lsm"
    gk = N.manifest_group(rows[0])
    m = {N.norm_key(N.key_string(gk[0], gk[1], gk[2])): "AE-biomaGUNE-1123"}
    out, used = N.remap_rows(rows, m, PROJECTS)
    check(out[0]["decision"] == "place" and out[0]["project_name"] == "AE-biomaGUNE-1123", "mapped group -> place")
    check(out[0]["dest_rel"].startswith("projects\\AE-biomaGUNE-1123\\working\\historical_drives\\drive1_FRIO-X6\\"),
          f"dest under the project {out[0]['dest_rel'][:70]}")
    check(out[1]["decision"] == "holding", ".lsm stays in holding even in a mapped group")
    check(out[2]["decision"] == "holding", "unmapped group untouched")
    m2 = {N.norm_key(N.key_string(gk[0], gk[1], gk[2])): "AE-biomaGUNE-1519"}
    check(N.remap_rows(rows, m2, PROJECTS)[0][0]["decision"] == "closed-project", "mapped to a closed project -> listed")
    check(rows[0]["decision"] == "holding", "input rows are not modified")


def test_parent_grouping():
    print("group under the parent (Ryan, 2026-10-04): session / animal level study folders climb")
    def climb(path, i, fn=False):
        segs = [p for p in path.split("\\")]
        names = [s.lower() for s in segs]
        kinds = ["dir"] * (len(segs) - 1) + ["file"]
        return segs[N.promote_root(names, kinds, i, fn)]
    p = r"T\Biodistribucion Noviembre22\20221006_120152_jrc221006_m42_0721_1_1\pdata\x.nii"
    check(climb(p, 2) == "Biodistribucion Noviembre22", "a ParaVision session climbs to its study folder")
    p = r"C\AXIOSCAN\Prueba jpeg\ID205\a.czi"
    check(climb(p, 3, fn=True) == "Prueba jpeg", "an animal folder from a file-name claim climbs")
    p = r"C\PR REPETICION\Grupo B\a.tif"
    check(climb(p, 2) == "PR REPETICION", "Grupo B climbs")
    p = r"C\Proyecto 0619\MRI\a.xlsx"
    check(climb(p, 1) == "Proyecto 0619", "a real study folder stays")
    segs = r"A\Pili y Mili\Proyecto 1019 Envejecimiento y dieta\MRI\a.xlsx".split("\\")
    i = N.promote_root([x.lower() for x in segs], ["dir"] * 4 + ["file"], 2, True, code="1019")
    check(segs[i] == "Proyecto 1019 Envejecimiento y dieta", "a folder named for the project never climbs")
    p = r"Top\20221006_120152_x_m42\a.nii"
    check(climb(p, 1) == "20221006_120152_x_m42", "never climbs onto the drive's top folder")


def test_not_registered():
    print("not-registered MRI (Ryan, 2026-10-04): placed / held as other data, README per group")
    D = lambda **kw: N.decide(rec(**kw), CTX)  # noqa: E731
    r = D(**{"class": "bruker"}, imaging_root="mri: x", from_b="AE-biomaGUNE-1123", from_b_kind="notregistered:no-recon")
    check(r[0] == "place" and "not registered" in r[1], f"with a project -> placed {r[:2]}")
    r = D(**{"class": "bruker"}, imaging_root="mri: x", from_b="", from_b_kind="notregistered:conversion-failed")
    check(r[:2] == ("holding", "B->A not registered, no project"), f"no project -> holding {r[:2]}")
    check(N.mappable("B->A not registered, no project"), "a not-registered group without a project is mappable in 2b")
    base = r"projects\P\working\historical_drives"
    why = N.NOTREG_WHY["no-recon"]
    f = N.notreg_folders(base, [(base + r"\FRIO-X6\S\sess\5\acqp", why), (base + r"\FRIO-X6\S\sess\5\pdata\1\2dseq", why),
                                (base + r"\FRIO-X6\S\sess\6\acqp", why)])
    check(sorted(f) == [r"FRIO-X6\S\sess\5", r"FRIO-X6\S\sess\6"], f"one README per exam folder {sorted(f)}")
    deep = "FRIO-X6\\" + "\\".join(["x" * 40] * 4)
    f = N.notreg_folders(base, [(base + "\\" + deep + "\\a", why)])
    (k,) = f
    check(H_ok(base, k), f"a README that would break the budget moves up ({k.count(chr(92))} levels)")
    txt = N.notreg_text({why, N.NOTREG_WHY["non-image"]})
    check("spectroscopy" in txt and "_INDEX.csv" in txt and "CAN be" in txt,
          "README text says why, that it can be registered later, and where to look")
    check(set(N.NOTREG_WHY) == {"no-recon", "non-image", "conversion-failed"}, "all three of B's kinds have a plain reason")


def H_ok(base, folder):
    import historical_paths as H
    return H.unc_len(f"{base}\\{folder}\\{N.NOTREG_README}") <= H.BUDGET


def test_publish():
    print("publishing a tree's index documents (what was previewed is what lands)")
    import historical_paths as H
    tmp = tempfile.mkdtemp(prefix="nonraw_pub_")
    try:
        out, nas = os.path.join(tmp, "out"), os.path.join(tmp, "nas")
        manifest = os.path.join(out, "placement_manifest.csv")
        base = r"projects\P\working\historical_drives"
        tdir = N.tree_preview_dir(manifest, base)
        os.makedirs(tdir)
        H.write_index(os.path.join(tdir, H.INDEX_NAME), [{"new_path": r"FRIO-X6\S\a.tif", "drive": "drive1_FRIO-X6",
                      "archive": "", "original_path": r"drive1_FRIO-X6\X\S\a.tif", "size": "1", "sha256": "x",
                      "claim_id": "CL-1", "shortened": "N", "note": ""}])
        H.write_pathmap(os.path.join(tdir, H.PATHMAP_NAME), [{"node_key": r"D1:X\S", "rendered": r"FRIO-X6\S"}])
        N.wcsv(os.path.join(tdir, "_ORIGINS.csv"), ["folder", "original"],
               [{"folder": r"FRIO-X6\S", "original": r"drive1_FRIO-X6\X\S"}])
        res = N.publish_tree(nas, manifest, base, execute=True)
        names = sorted(os.path.basename(r) for r, _w in res)
        check(names == ["README.txt", "_INDEX.csv", "_ORIGIN.txt", "_PATHMAP.csv"], f"documents {names}")
        check(all(w for _r, w in res), "first run writes them all")
        check(os.path.exists(os.path.join(nas, base, "FRIO-X6", "S", "_ORIGIN.txt")), "_ORIGIN.txt inside the study folder")
        check(open(os.path.join(nas, base, "_INDEX.csv"), "rb").read()[:3] == b"\xef\xbb\xbf", "_INDEX.csv has a BOM (Excel)")
        check(not any(w for _r, w in N.publish_tree(nas, manifest, base, execute=True)), "a re-run writes nothing")
        # holding: manifest.csv instead of _INDEX.csv, plus the not-copied row
        hdir = N.tree_preview_dir(manifest, N.HOLDING_BASE)
        os.makedirs(hdir)
        shutil.copy(os.path.join(tdir, H.INDEX_NAME), hdir)
        shutil.copy(os.path.join(tdir, H.PATHMAP_NAME), hdir)
        extra = N.not_copied_rows([{"decision": "exclude", "reason": "not copied: truncated", "drive_label": "drive1_FRIO-X6",
                                    "drive": "D1", "relpath": "Simu_2_V_XYZ.zip", "archive": "", "member": "", "size": "97", "sha256": "", "claim_id": ""}])
        docs = N.tree_documents(manifest, N.HOLDING_BASE, holding=True, extra_index_rows=extra)
        man = docs[N.HOLDING_BASE + "\\manifest.csv"].decode("utf-8-sig")
        check("Simu_2_V_XYZ.zip" in man and "not copied" in man, "holding manifest lists the not-copied archive")
        check("Simu_2_V_XYZ.zip" in docs[N.HOLDING_BASE + "\\README.txt"].decode("utf-8"), "holding README says so too")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_publish_merges():
    print("re-publishing MERGES with the NAS (stream D's rows, older header, frozen folders are kept)")
    import historical_paths as H
    tmp = tempfile.mkdtemp(prefix="nonraw_merge_")
    try:
        out, nas = os.path.join(tmp, "out"), os.path.join(tmp, "nas")
        manifest = os.path.join(out, "placement_manifest.csv")
        base = r"projects\P\working\historical_drives"
        tdir = N.tree_preview_dir(manifest, base)
        os.makedirs(tdir)
        H.write_index(os.path.join(tdir, H.INDEX_NAME), [{"new_path": r"FRIO-X6\S\mine.tif", "drive": "drive1_FRIO-X6",
                      "archive": "", "original_path": r"drive1_FRIO-X6\X\S\mine.tif", "size": "1", "sha256": "a",
                      "claim_id": "", "shortened": "N", "why": "", "note": ""}])
        H.write_pathmap(os.path.join(tdir, H.PATHMAP_NAME), [{"node_key": r"D1:X\S", "rendered": r"FRIO-X6\S"}])
        N.wcsv(os.path.join(tdir, "_ORIGINS.csv"), ["folder", "original"], [{"folder": r"FRIO-X6\S", "original": r"drive1_FRIO-X6\X\S"}])
        # what is already on the NAS: stream D's row under the OLDER 9-column header (no `why`), a
        # stale copy of our own row, D's frozen folder, and an _ORIGIN with another original path
        tree = os.path.join(nas, base)
        os.makedirs(os.path.join(tree, "FRIO-X6", "S"))
        old9 = ["new_path", "drive", "archive", "original_path", "size", "sha256", "claim_id", "shortened", "note"]
        with open(os.path.join(tree, H.INDEX_NAME), "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=old9 + ["retired_from"])
            w.writeheader()
            w.writerow({"new_path": r"FRIO-X6\S\derivative_from_D.czi", "drive": "drive1_FRIO-X6", "archive": "",
                        "original_path": r"drive1_FRIO-X6\X\S\derivative_from_D.czi", "size": "9", "sha256": "d",
                        "claim_id": "", "shortened": "N", "note": "stream D", "retired_from": "ACQ-1"})
            w.writerow({"new_path": r"FRIO-X6\S\mine.tif", "drive": "drive1_FRIO-X6", "archive": "",
                        "original_path": r"drive1_FRIO-X6\X\S\mine.tif", "size": "0", "sha256": "OLD",
                        "claim_id": "", "shortened": "N", "note": "", "retired_from": ""})
        H.write_pathmap(os.path.join(tree, H.PATHMAP_NAME), [{"node_key": r"D1:X\S", "rendered": r"FRIO-X6\S"},
                                                            {"node_key": r"D1:Y\T", "rendered": r"FRIO-X6\T"}])
        with open(os.path.join(tree, "FRIO-X6", "S", H.ORIGIN_NAME), "w", encoding="utf-8") as f:
            f.write(H.origin_text([r"drive2_MFB-Disco-2\Other\S"]))
        N.publish_tree(nas, manifest, base, execute=True)
        rows = list(csv.DictReader(open(os.path.join(tree, H.INDEX_NAME), encoding="utf-8-sig", newline="")))
        paths = {r["new_path"]: r for r in rows}
        check(r"FRIO-X6\S\derivative_from_D.czi" in paths, "stream D's row is KEPT")
        check(paths[r"FRIO-X6\S\derivative_from_D.czi"]["retired_from"] == "ACQ-1", "its extra column is kept too")
        check(len(rows) == 2 and paths[r"FRIO-X6\S\mine.tif"]["sha256"] == "a", "our own row is replaced, not duplicated")
        check("why" in rows[0] and "retired_from" in rows[0], "header = ours + any existing column (older header merged)")
        pm = list(csv.DictReader(open(os.path.join(tree, H.PATHMAP_NAME), encoding="utf-8-sig", newline="")))
        check({r["node_key"] for r in pm} == {r"D1:X\S", r"D1:Y\T"}, "D's frozen folder stays in _PATHMAP.csv")
        org = open(os.path.join(tree, "FRIO-X6", "S", H.ORIGIN_NAME), encoding="utf-8").read()
        check(r"drive2_MFB-Disco-2\Other\S" in org and r"drive1_FRIO-X6\X\S" in org, "_ORIGIN.txt keeps both origins")
        check(not any(w for _r, w in N.publish_tree(nas, manifest, base, execute=True)), "a re-run writes nothing")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_third_drive():
    print("the third drive (D3, M. Jesus's working drive, staged on the NAS 2026-09-29/30)")
    check(N.DRIVES["D3"] == ("drive3_MJesus-MFB", r"J:\_staging_drive3_MJ\drive3_MJesus_WX22D623YP29"),
          f"D3 staged root {N.DRIVES['D3']}")
    check(N.DRIVES["D1"][0] == "drive1_FRIO-X6" and N.DRIVES["D2"][0] == "drive2_MFB-Disco-2", "D1/D2 unchanged")
    check(N.CLAIMS_DRIVE.get("drive3") == "D3", "the claims engine's drive3 maps to D3")
    check(N.staged_path({"drive": "D3", "relpath": r"Pili y Mili\a.docx"}) ==
          r"J:\_staging_drive3_MJ\drive3_MJesus_WX22D623YP29\files\Pili y Mili\a.docx", "staged path of a D3 file")
    r = {"drive": "D1", "drive_label": "drive1_FRIO-X6", "relpath": "a\\b.png", "archive": "", "member": "",
         "dest_rel": r"projects\P\working\historical_drives\FRIO-X6\a\b.png", "class": "figure",
         "reason": "claim CONFIRMED", "claim_id": "CL-1", "sha256": "x"}
    old = ("Copied by nonraw_placement.py from the historical operator drive drive1_FRIO-X6 (staged 2026-09-22/28): "
           "non-raw project material (class figure; claim CONFIRMED). Byte-verified against the drive manifest.")
    check(N.prov_entry(r, "RUN", "t", "x")["process_description"] == old, "D1 provenance wording unchanged")
    d3 = N.prov_entry(dict(r, drive="D3", drive_label="drive3_MJesus-MFB"), "RUN", "t", "x")["process_description"]
    check("drive3_MJesus-MFB" in d3 and "2026-09-29/30" in d3 and "operator" not in d3,
          f"D3 provenance names its drive and staging dates: {d3[:90]}")
    # the not-registered README: drives 1+2 text unchanged; a drive-3 group names its drive
    t12 = N.notreg_text({"x"})
    check("(FRIO-X6 and MFB-Disco-2, staged in September 2026)" in t12 and t12 == N.notreg_text({"x"}, {"FRIO-X6"}),
          "drives 1+2 not-registered README unchanged")
    t3 = N.notreg_text({"x"}, {"MJesus-MFB"})
    check("(MJesus-MFB, staged in September 2026)" in t3 and "FRIO-X6" not in t3, "drive-3 README names drive 3 only")
    # the holding README: three drives, the not-copied archive, the model outputs, biomaGUNE MJ
    for s in ("FRIO-X6", "2322E4A111E7", "MFB-Disco-2", "2322E4A112BD", "MJesus-MFB", "WX22D623YP29",
              "Simu_2_V_XYZ.zip", "PH_analysis_Segmentation_tool", "Predict_Slicer", "biomaGUNE MJ", "manifest.csv"):
        check(s in N.README_TXT, f"holding README names {s}")


def _d3_stage(tmp):
    """A staged drive-3 tree in tmp: files\\A\\S\\{p.txt, h.txt, held.txt} -> (stage root, {name: bytes})."""
    stage = os.path.join(tmp, "stage3")
    os.makedirs(os.path.join(stage, "files", "A", "S"))
    data = {"p.txt": b"placed now", "h.txt": b"to the holding folder", "held.txt": b"waits on M1"}
    for n, b in data.items():
        with open(os.path.join(stage, "files", "A", "S", n), "wb") as f:
            f.write(b)
    return stage, data


def test_held_never_copied():
    print("decision `held` (drive 3): planned, never copied by copy / holding, ignored by verify")
    tmp = tempfile.mkdtemp(prefix="nonraw_held_")
    old = N.DRIVES
    try:
        stage, data = _d3_stage(tmp)
        N.DRIVES = dict(old, D3=("drive3_MJesus-MFB", stage))
        nas, out = os.path.join(tmp, "nas"), os.path.join(tmp, "out")
        os.makedirs(os.path.join(nas, "registries"))
        with open(os.path.join(nas, "registries", "registry_projects.csv"), "w", encoding="utf-8", newline="") as f:
            f.write("project_id,name,description,owner,start_date,status,last_activity,folder_location,notes\r\n"
                    "PROJ-0001,P,,x,,active,,/projects/P/,\r\n")
        from ingest import provenance
        provenance.write_empty(os.path.join(nas, "projects", "P", "provenance.csv"))
        projects = N.load_projects(nas)
        base = {"drive": "D3", "drive_label": "drive3_MJesus-MFB", "archive": "", "member": "", "class": "document",
                "ext": ".txt", "flag": "", "claim_id": "CL-9", "verdict": "CONFIRMED", "researcher": "",
                "project_id": "PROJ-0001", "project_status": "active", "dest_rel": "", "note": "", "shortened": "",
                "why": "", "why_detail": ""}
        rows = [dict(base, row=1, relpath=r"A\S\p.txt", project_name="P", decision="place", reason="claim CONFIRMED",
                     root_key="a|s", hold=""),
                dict(base, row=2, relpath=r"A\S\h.txt", project_name="", decision="holding", reason="(C) claim",
                     root_key="-", hold=""),
                dict(base, row=3, relpath=r"A\S\held.txt", project_name="P", decision="held",
                     reason="claim CONFIRMED | HELD: M1", root_key="a|s", hold="M1-0118")]
        for r in rows:
            r["size"] = str(len(data[os.path.basename(r["relpath"])]))
            r["sha256"] = _sha(data[os.path.basename(r["relpath"])])
        N.assign_destinations(rows, projects, nas, out, lambda m: None, {}, None)
        check(rows[0]["dest_rel"] == r"projects\P\working\historical_drives\MJesus-MFB\S\p.txt", rows[0]["dest_rel"])
        check(rows[2]["dest_rel"] == "", "a held row gets no destination from the copy plan")
        rows[2]["dest_rel"] = r"projects\P\working\historical_drives\MJesus-MFB\S\held.txt"   # as p_plan sets it
        manifest = os.path.join(out, "placement_manifest.csv")
        N.wcsv(manifest, N.MANIFEST_FIELDS, rows)
        scratch = os.path.join(tmp, "scratch")
        rc = N.main(["--out", out, "--nas", nas, "copy", "--manifest", manifest, "--execute", "--scratch", scratch])
        tree = os.path.join(nas, "projects", "P", "working", "historical_drives")
        check(rc == 0 and open(os.path.join(tree, "MJesus-MFB", "S", "p.txt"), "rb").read() == data["p.txt"],
              "copy --execute placed the place row")
        check(not os.path.exists(os.path.join(tree, "MJesus-MFB", "S", "held.txt")), "copy never copies a held row")
        idx = list(csv.DictReader(open(os.path.join(tree, "_INDEX.csv"), encoding="utf-8-sig", newline="")))
        check([x["new_path"] for x in idx] == [r"MJesus-MFB\S\p.txt"], f"the published index lists no held row {idx}")
        check(idx[0]["drive"] == "drive3_MJesus-MFB" and idx[0]["original_path"] == r"drive3_MJesus-MFB\A\S\p.txt",
              "index row names drive 3")
        org = open(os.path.join(tree, "MJesus-MFB", "S", "_ORIGIN.txt"), encoding="utf-8").read()
        check(r"drive3_MJesus-MFB\A\S" in org, "_ORIGIN.txt in the study folder names the drive-3 path")
        check(open(os.path.join(tree, "README.txt"), "rb").read() ==
              N.H.PROJECT_README.replace("\n", "\r\n").encode("utf-8"), "README.txt is the three-drive text")
        rc = N.main(["--out", out, "--nas", nas, "holding", "--manifest", manifest, "--execute", "--scratch", scratch])
        hold = os.path.join(nas, "staging", "historical_drives_unassigned")
        check(rc == 0 and open(os.path.join(hold, "MJesus-MFB", "A", "S", "h.txt"), "rb").read() == data["h.txt"],
              "holding --execute copied the holding row, in its original structure")
        hm = list(csv.DictReader(open(os.path.join(hold, "manifest.csv"), encoding="utf-8-sig", newline="")))
        check([x["new_path"] for x in hm] == [r"MJesus-MFB\A\S\h.txt"], f"holding manifest: the holding row only {hm}")
        check(not os.path.exists(os.path.join(hold, "MJesus-MFB", "A", "S", "held.txt")), "holding never copies a held row")
        rc = N.main(["--out", out, "--nas", nas, "verify", "--manifest", manifest, "--sample", "1.0"])
        check(rc == 0, "verify passes: the held row is not expected on the NAS")
        rc = N.main(["--out", out, "--nas", nas, "copy", "--manifest", manifest, "--execute", "--scratch", scratch])
        provs = list(csv.DictReader(open(os.path.join(nas, "projects", "P", "provenance.csv"), encoding="utf-8", newline="")))
        check(rc == 0 and len([p for p in provs if p["output_path"].endswith("p.txt")]) == 1,
              "a re-run is idempotent: one provenance row per file")
    finally:
        N.DRIVES = old
        shutil.rmtree(tmp, ignore_errors=True)


def test_publish_merges_third_drive():
    print("drive-3 rows MERGE into a drives 1+2 tree (the AE-biomaGUNE-0118 case: 9-column header, D1 folders)")
    import historical_paths as H
    tmp = tempfile.mkdtemp(prefix="nonraw_merge3_")
    try:
        out, nas = os.path.join(tmp, "out"), os.path.join(tmp, "nas")
        manifest = os.path.join(out, "placement_manifest.csv")
        base = r"projects\AE-biomaGUNE-0118\working\historical_drives"
        tree = os.path.join(nas, base)
        os.makedirs(os.path.join(tree, "FRIO-X6", "Proyecto 0118 Monocrotalina"))
        old9 = ["new_path", "drive", "archive", "original_path", "size", "sha256", "claim_id", "shortened", "note"]
        d1 = [{"new_path": rf"FRIO-X6\Proyecto 0118 Monocrotalina\doc{i}.pdf", "drive": "drive1_FRIO-X6",
               "archive": "Drive MJ.zip", "original_path": rf"drive1_FRIO-X6\Drive MJ.zip!Pili y Mili\Proyecto 0118 Monocrotalina\doc{i}.pdf",
               "size": str(i), "sha256": f"d1sha{i}", "claim_id": "CL-1", "shortened": "N", "note": ""} for i in range(3)]
        with open(os.path.join(tree, H.INDEX_NAME), "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=old9, lineterminator="\r\n")
            w.writeheader()
            w.writerows(d1)
        H.write_pathmap(os.path.join(tree, H.PATHMAP_NAME),
                        [{"node_key": r"D1:Drive MJ.zip\Pili y Mili\Proyecto 0118 Monocrotalina",
                          "rendered": r"FRIO-X6\Proyecto 0118 Monocrotalina"}])
        d1_origin = H.origin_text([r"drive1_FRIO-X6\Drive MJ.zip!Pili y Mili\Proyecto 0118 Monocrotalina"]).encode("utf-8")
        with open(os.path.join(tree, "FRIO-X6", "Proyecto 0118 Monocrotalina", H.ORIGIN_NAME), "wb") as f:
            f.write(d1_origin)
        with open(os.path.join(tree, H.README_NAME), "w", encoding="utf-8") as f:
            f.write("the old two-drive README")
        # this run's preview: three drive-3 documents in the same-named study folder
        it3 = [H.Item(id=str(i), drive="D3", relpath=rf"Pili y Mili\Proyecto 0118 Monocrotalina\MRI 2DG ratas\x{i}.xlsx",
                      root=H.claim_root_segments(r"Pili y Mili\Proyecto 0118 Monocrotalina"),
                      extra={"size": "5", "sha256": f"d3sha{i}", "claim_id": "CL-1176"}) for i in range(3)]
        p = H.Planner(base)
        p.load_pathmap(os.path.join(tree, H.PATHMAP_NAME))
        dests = p.plan(it3)
        tdir = N.tree_preview_dir(manifest, base)
        H.write_index(os.path.join(tdir, H.INDEX_NAME), H.index_rows(dests, it3, base))
        H.write_pathmap(os.path.join(tdir, H.PATHMAP_NAME), p.pathmap_rows())
        N.wcsv(os.path.join(tdir, "_ORIGINS.csv"), ["folder", "original"],
               [{"folder": k, "original": o} for k, v in p.origins(it3).items() for o in v])
        check(all(r"\MJesus-MFB\Proyecto 0118 Monocrotalina\MRI 2DG ratas" in d for d in dests.values()),
              "drive 3's study folder sits beside drive 1's, under its own tag, with no (2)")
        N.publish_tree(nas, manifest, base, execute=True)
        rows = list(csv.DictReader(open(os.path.join(tree, H.INDEX_NAME), encoding="utf-8-sig", newline="")))
        kept = [r for r in rows if r["drive"] == "drive1_FRIO-X6"]
        check(len(kept) == 3 and all(any(all(k[c] == r[c] for c in old9) for r in kept) for k in d1),
              "all 3 drive-1 rows kept, every column unchanged")
        check(len([r for r in rows if r["drive"] == "drive3_MJesus-MFB"]) == 3 and len(rows) == 6, "3 drive-3 rows added")
        pm = {r["node_key"]: r["rendered"] for r in csv.DictReader(open(os.path.join(tree, H.PATHMAP_NAME), encoding="utf-8-sig", newline=""))}
        check(pm.get(r"D1:Drive MJ.zip\Pili y Mili\Proyecto 0118 Monocrotalina") == r"FRIO-X6\Proyecto 0118 Monocrotalina"
              and any(k.startswith("D3:") for k in pm), "_PATHMAP.csv keeps D1's folder and adds D3's")
        check(open(os.path.join(tree, "FRIO-X6", "Proyecto 0118 Monocrotalina", H.ORIGIN_NAME), "rb").read() == d1_origin,
              "drive 1's _ORIGIN.txt is not touched (byte-identical)")
        check(os.path.exists(os.path.join(tree, "MJesus-MFB", "Proyecto 0118 Monocrotalina", H.ORIGIN_NAME)),
              "drive 3's study folder gets its own _ORIGIN.txt")
        check(open(os.path.join(tree, H.README_NAME), "rb").read() == H.PROJECT_README.replace("\n", "\r\n").encode("utf-8"),
              "README.txt is rewritten to the three-drive text")
        check(not any(w for _r, w in N.publish_tree(nas, manifest, base, execute=True)), "a re-publish writes nothing")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def test_copy():
    print("copy")
    tmp = tempfile.mkdtemp(prefix="nonraw_test_")
    try:
        stage = os.path.join(tmp, "stage")
        nas = os.path.join(tmp, "nas")
        os.makedirs(os.path.join(stage, "files", "a"))
        os.makedirs(os.path.join(nas, "projects", "P"))
        data = b"hello non-raw"
        with open(os.path.join(stage, "files", "a", "b.png"), "wb") as f:
            f.write(data)
        with zipfile.ZipFile(os.path.join(stage, "files", "arc.zip"), "w") as z:
            z.writestr("in/doc.txt", b"member bytes")
        old = N.DRIVES
        N.DRIVES = {"D1": ("drive1_X", stage)}
        try:
            r = {"drive": "D1", "drive_label": "drive1_X", "relpath": "a\\b.png", "archive": "",
                 "member": "", "sha256": _sha(data), "size": str(len(data)),
                 "dest_rel": N.dest_rel("P", "drive1_X", "a\\b.png"), "class": "figure",
                 "reason": "claim CONFIRMED", "claim_id": "CL-1"}
            ms = N.MemberSource(os.path.join(tmp, "scratch"))
            check(N.copy_one(r, nas, ms) == "copied", "loose file copied")
            dest = os.path.join(nas, r["dest_rel"])
            check(open(dest, "rb").read() == data, "bytes in place")
            check(not [f for f in os.listdir(os.path.dirname(dest)) if f.endswith(".part")], "no temp left")
            check(N.copy_one(r, nas, ms) == "skipped-identical", "re-run skips identical")
            m = dict(r, relpath="arc.zip", archive="arc.zip", member="in/doc.txt",
                     sha256=_sha(b"member bytes"), dest_rel=N.dest_rel("P", "drive1_X", "arc.zip", "arc.zip", "in/doc.txt"))
            check(N.copy_one(m, nas, ms) == "copied", "zip member copied")
            check(open(os.path.join(nas, m["dest_rel"]), "rb").read() == b"member bytes", "member bytes")
            bad = dict(r, sha256=_sha(b"other"))
            try:
                N.copy_one(bad, nas, ms)
                check(False, "different bytes at dest raise Collision")
            except N.Collision:
                check(open(dest, "rb").read() == data, "collision leaves the existing file untouched")
            wrong = dict(r, dest_rel=N.dest_rel("P", "drive1_X", "a\\c.png"), sha256=_sha(b"nope"))
            try:
                N.copy_one(wrong, nas, ms)
                check(False, "source/manifest mismatch must fail")
            except RuntimeError:
                check(not os.path.exists(os.path.join(nas, wrong["dest_rel"])), "mismatch: nothing placed")
            # --from-holding: the source is the file's copy in the NAS holding folder, still verified
            hold = os.path.join(nas, N.holding_rel("drive1_X", "a\\h.png"))
            os.makedirs(os.path.dirname(hold))
            with open(hold, "wb") as f:
                f.write(b"held bytes")
            hr = dict(r, relpath="a\\h.png", sha256=_sha(b"held bytes"), _src=hold,
                      dest_rel=N.dest_rel("P", "drive1_X", "a\\h.png"))
            check(N.copy_one(hr, nas, ms) == "copied", "copy from the holding folder")
            check(open(os.path.join(nas, hr["dest_rel"]), "rb").read() == b"held bytes", "holding bytes in place")
            check(os.path.exists(hold), "the holding copy is left in place (copies only)")
            ms.close()
            prov = os.path.join(nas, "projects", "P", "provenance.csv")
            from ingest import provenance
            provenance.write_empty(prov)
            e1 = N.prov_entry(r, "RUN", "tester", "2026-10-03")
            e2 = N.prov_entry(m, "RUN", "tester", "2026-10-03")
            check(e1["output_path"] == "working/historical_drives/drive1_X/a/b.png", f"prov path {e1['output_path']}")
            check(e2["input_refs"] == "drive1_X/arc.zip!in/doc.txt", f"member input_refs {e2['input_refs']}")
            check(N.append_provenance(prov, [e1, e2]) == 2, "two rows appended")
            check(N.append_provenance(prov, [e1, e2]) == 0, "provenance idempotent")
            rows = list(csv.DictReader(open(prov, encoding="utf-8", newline="")))
            check([x["file_id"] for x in rows] == ["FILE-0001", "FILE-0002"], "sequential FILE ids")
            d = dict(r, reason="R3 derivative of ACQ-20230904-CELL-109 (scale-bar copy)")
            check(N.prov_entry(d, "RUN", "t", "x")["input_refs"].startswith("ACQ-20230904-CELL-109; "),
                  "derivative input_refs carry the parent ACQ-ID")
        finally:
            N.DRIVES = old
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    test_layout()
    test_decide()
    test_roots()
    test_worksheet_roundtrip()
    test_link_names()
    test_remap()
    test_parent_grouping()
    test_not_registered()
    test_publish()
    test_publish_merges()
    test_copy()
    test_third_drive()
    test_held_never_copied()
    test_publish_merges_third_drive()
    print(f"\n{'FAILED: ' + str(len(FAILS)) if FAILS else 'all passed'}")
    sys.exit(1 if FAILS else 0)
