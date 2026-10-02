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
         "imaging_root": None, "excluded_reason": None, "derived": None, "ingested": False}
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
    h = N.holding_rel("drive2_MFB-Disco-2", "a\\b.txt")
    check(h == "staging\\historical_drives_unassigned\\drive2_MFB-Disco-2\\a\\b.txt", f"holding {h}")


def test_decide():
    print("decide")
    D = lambda **kw: N.decide(rec(**kw), CTX)  # noqa: E731
    check(D()[0] == "place" and D()[2] == "AE-biomaGUNE-1123", "confirmed figure -> place")
    check(D(verdict="A")[0] == "place", "(A) -> place")
    check(D(verdict="", proposed_project="")[0] == "holding", "no claim -> holding")
    check(D(verdict="C", proposed_project="")[0] == "holding", "(C) -> holding")
    check(D(verdict="B", proposed_project="")[2] == "Project-0521", "(B) -> Project-0521")
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
    check(D(**{"class": "czi-unreadable"}, size="5")[0] == "unclear", "unreadable czi with bytes -> unclear")
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
    check(N.nested_special(n)[0] == "unclear", ".svs -> question")
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
    test_copy()
    print(f"\n{'FAILED: ' + str(len(FAILS)) if FAILS else 'all passed'}")
    sys.exit(1 if FAILS else 0)
