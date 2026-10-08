#!/usr/bin/env python3
"""test_drive3_closeout.py -- the M. Jesus drive's close-out reconciliation (tools/drive_staging/drive3/closeout.py).

Builds a small NAS root and a staged copy in a temp folder and runs the tool end to end (live /raw/ index,
--stat, --walk), then checks:

  rules     one category per file, the first that applies: zero-byte before everything; in /raw/ before
            placed before holding; a placed file's own location preferred; an expanded .zip only when EVERY
            member is kept; junk (Ryan's list + A2's additions), personal (biomaGUNE MJ only), MRI ParaVision
            files of registered exams (a 2dseq only when /raw/ holds its reconstruction), DICOM re-exports,
            stream C's re-saves (parent live / twin in /raw/); anything else a BLOCKER with a hint
  verdict   BLOCKED: <n> files while anything blocks (a file in no category, a kept file missing on the NAS
            under --stat, a staged file its manifest does not list under --walk, an out-of-date /raw/ index);
            READY TO DELETE when nothing does
  read-only every file of the NAS root and of the staged copy is byte-identical, with the same mtime, after the
            runs; outputs only under --out

Run:  python tools/test_drive3_closeout.py
"""
import contextlib
import csv
import gzip
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "drive_staging", "drive3"))
sys.path.insert(0, os.path.join(HERE, "drive_staging"))
sys.path.insert(0, HERE)
import closeout as C  # noqa: E402

FAILS = []
BMJ = "biomaGUNE MJ\\"


def check(cond, msg):
    print(f"  {'ok:  ' if cond else 'FAIL:'} {msg}")
    if not cond:
        FAILS.append(msg)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def wcsv(path, fields, rows, gz=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    opener = gzip.open if gz else open
    with opener(path, "wb") as fb:
        with io.TextIOWrapper(fb, encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in rows:
                w.writerow(r)


def put(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def tree_state(root):
    out = {}
    for d, _ds, fs in os.walk(root):
        for f in fs:
            p = os.path.join(d, f)
            st = os.stat(p)
            out[os.path.relpath(p, root)] = (st.st_size, st.st_mtime_ns, sha(open(p, "rb").read()))
    return out


# ------------------------------------------------------------------------------------------- the fixture

DRIVE_FILES = {   # relpath -> bytes (b"" = zero-byte)
    "MRI\\S1\\5\\pdata\\1\\dicom\\MRIm01.dcm": b"dicom-in-raw",           # in /raw/ (and placed: raw wins)
    "MRI\\S1\\5\\fid": b"kspace-S1-5",                                     # mri-kspace
    "MRI\\S1\\5\\acqp": b"acqp-S1-5",                                      # mri-params
    "MRI\\S1\\5\\pdata\\1\\2dseq": b"2dseq-S1-5-r1",                       # mri-2dseq (recon 1 held)
    "MRI\\S1\\subject": b"subject-S1",                                     # mri-params, study-level
    "MRI\\S3\\2\\pdata\\1\\dicom\\MRIm01.dcm": b"reexport",                # mri-dicom-reexport (b-export)
    "Pili y Mili\\docs\\a.docx": b"doc-a",                                 # placed (own location preferred)
    "Pili y Mili\\docs\\copy of a.docx": b"doc-a",                         # placed (same bytes)
    "Otros\\loose\\b.txt": b"held-b",                                      # holding
    "Pili y Mili\\docs\\pack.zip": None,                                   # archive-expanded (built below)
    "Pili y Mili\\docs\\desktop.ini": b"[.ShellClassInfo]",                # junk (Ryan's list)
    "Otros\\seg\\._x.nii": b"appledouble",                                 # junk (AppleDouble)
    "Otros\\seg\\Icon": b"icon-bytes",                               # junk (A2's addition)
    "Otros\\Install Western Digital Software for Windows.exe": b"wd",      # junk (installer)
    "MRI\\Flow\\folders.cache": b"MATLAB 5.0 MAT-file cache",               # junk (A2's addition)
    "Pili y Mili\\docs\\empty.txt": b"",                                   # zero-byte
    "MRI\\S1\\5\\empty_in_raw": b"",                                       # zero-byte even though '' is in /raw/
    BMJ + "Proteomica\\Muestras\\IMG_20220905_135733.jpg": b"photo",       # personal
    "Microscopio\\resave.czi": b"czi-resave-of-prod",                      # czi-resave-of-production
    "Microscopio\\twin.czi": b"czi-resave-within",                         # czi-resave-within-drive
    "MRI\\S4\\7\\acqp": b"acqp-S4-7",                                      # a placeholder's file, once placed: placed
}
BLOCKING = {   # relpath -> bytes: each must come out BLOCKER
    "MRI\\S1\\5\\pdata\\2\\2dseq": b"2dseq-S1-5-r2",                       # recon 2 not in /raw/
    "MRI\\S9\\subject": b"subject-S9",                                     # study with no registered exam
    "MRI\\S9\\4\\fid": b"kspace-S9-4",                                     # exam not registered
    "MRI\\S2\\3\\pdata\\1\\dicom\\MRIm01.dcm": b"dicom-not-in-raw",        # registered, A1 a1-identical, bytes absent
    "Microscopio\\orphan_resave.czi": b"czi-parent-gone",                  # parent ACQ not live
    "Microscopio\\crop.czi": b"czi-derivative",                            # stream C derivative, never handed over
    "Microscopio\\biodonostia\\scan.czi": b"czi-foreign",                  # outside-instrument raw
    "Pili y Mili\\docs\\half.zip": None,                                   # a zip with a member not kept
    "Otros\\notes\\IMG_20220905_135733.jpg": b"photo-elsewhere",           # the personal screen is biomaGUNE MJ's only
    "Otros\\notes\\lost.txt": b"lost",                                     # nothing at all
    "MRI\\S4\\7\\fid": b"kspace-S4-7",                                     # a DICOM-less placeholder's k-space, not placed
}


def zip_bytes(members):
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w") as z:
        for n, b in members:
            z.writestr(n, b)
    return bio.getvalue()


def build(tmp, with_blockers=True):
    nas = os.path.join(tmp, "nas")
    staged = os.path.join(tmp, "staging", "drive3_x")
    files = dict(DRIVE_FILES)
    files["Pili y Mili\\docs\\pack.zip"] = zip_bytes([("m1.txt", b"member-1"), ("sub/m2.txt", b"member-2")])
    if with_blockers:
        files.update(BLOCKING)
        files["Pili y Mili\\docs\\half.zip"] = zip_bytes([("m1.txt", b"member-1"), ("m3.txt", b"member-3-lost")])
    for rel, b in files.items():
        put(os.path.join(staged, "files", rel), b)
    wcsv(os.path.join(staged, "manifest.csv"), ["relpath", "size", "mtime", "birthtime", "atime", "mtime_ns", "sha256"],
         [{"relpath": r, "size": len(b), "mtime": "", "birthtime": "", "atime": "", "mtime_ns": "", "sha256": sha(b)}
          for r, b in files.items()])
    with open(os.path.join(staged, "run_info.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps({"started": "2026-09-30T01:32:06", "files": len(files),
                            "bytes": sum(len(b) for b in files.values())}) + "\n")
    # production: four acquisitions
    acqs = [
        ("ACQ-20200101-MRI-001", "MRI", "S1/5", "/raw/DICOM/2020/2020-01/ACQ-20200101-MRI-001/",
         {"ACQ-20200101-MRI-001.data/recon1_frame01.dcm": b"dicom-in-raw", "ACQ-20200101-MRI-001.data/x.dcm": b""}),
        ("ACQ-20200101-MRI-002", "MRI", "S2/3", "/raw/DICOM/2020/2020-01/ACQ-20200101-MRI-002/",
         {"ACQ-20200101-MRI-002.data/recon1_frame01.dcm": b"S2-3-production-bytes"}),
        ("ACQ-20200101-MRI-003", "MRI", "S3__2", "/raw/DICOM/2020/2020-01/ACQ-20200101-MRI-003/",
         {"ACQ-20200101-MRI-003.data/recon1_frame01.dcm": b"S3-2-production-bytes"}),
        ("ACQ-20200101-MRI-004", "MRI", "S4/7", "/raw/DICOM/2020/2020-01/ACQ-20200101-MRI-004/", {}),   # placeholder
        ("ACQ-20230101-CELL-001", "CELL", "x/parent.czi", "/raw/MICROSCOPY/2023/2023-01/ACQ-20230101-CELL-001/",
         {"ACQ-20230101-CELL-001.czi": b"czi-parent"}),
        ("ACQ-20230101-CELL-002", "CELL", "x/kept-twin.czi", "/raw/MICROSCOPY/2023/2023-01/ACQ-20230101-CELL-002/",
         {"ACQ-20230101-CELL-002.czi": b"czi-kept-twin"}),
    ]
    reg = []
    for acq, inst, name, cp, fl in acqs:
        d = os.path.join(nas, cp.strip("/").replace("/", os.sep))
        for rel, b in fl.items():
            put(os.path.join(d, rel.replace("/", os.sep)), b)
        put(os.path.join(d, "checksums.json"), json.dumps({"files": {r: sha(b) for r, b in fl.items()}}).encode())
        reg.append({"acq_id": acq, "registration_datetime": "2026-10-01T00:00:00Z", "instrument": inst,
                    "original_name": name, "canonical_path": cp})
    wcsv(os.path.join(nas, "registries", "registry_raw.csv"),
         ["acq_id", "registration_datetime", "instrument", "original_name", "canonical_path"], reg)
    wcsv(os.path.join(nas, "registries", "registry_projects.csv"), ["project_id", "name", "status", "folder_location"],
         [{"project_id": "PROJ-0001", "name": "AE-biomaGUNE-0001", "status": "active",
           "folder_location": "/projects/AE-biomaGUNE-0001/"}])
    tree = os.path.join(nas, "projects", "AE-biomaGUNE-0001", "working", "historical_drives")
    idx = []

    def place(new, rel, b, member=""):
        put(os.path.join(tree, new), b)
        orig = C.H.original_display(C.DRIVE_LABEL, rel, rel if member else "", member)
        idx.append({"new_path": new, "drive": C.DRIVE_LABEL, "archive": rel if member else "", "original_path": orig,
                    "size": len(b), "sha256": sha(b)})

    place("MJesus-MFB\\other\\a-elsewhere.docx", "Pili y Mili\\elsewhere\\a.docx", b"doc-a")
    place("MJesus-MFB\\docs\\copy of a.docx", "Pili y Mili\\docs\\copy of a.docx", b"doc-a")
    place("MJesus-MFB\\docs\\a.docx", "Pili y Mili\\docs\\a.docx", b"doc-a")
    place("MJesus-MFB\\dicom\\MRIm01.dcm", "MRI\\S1\\5\\pdata\\1\\dicom\\MRIm01.dcm", b"dicom-in-raw")
    place("MJesus-MFB\\MRI\\S4\\7\\acqp", "MRI\\S4\\7\\acqp", b"acqp-S4-7")
    place("MJesus-MFB\\docs\\pack_zip\\m1.txt", "Pili y Mili\\docs\\pack.zip", b"member-1", "m1.txt")
    place("MJesus-MFB\\docs\\pack_zip\\sub\\m2.txt", "Pili y Mili\\docs\\pack.zip", b"member-2", "sub/m2.txt")
    wcsv(os.path.join(tree, "_INDEX.csv"), ["new_path", "drive", "archive", "original_path", "size", "sha256"], idx)
    hold = os.path.join(nas, "staging", "historical_drives_unassigned")
    put(os.path.join(hold, "MJesus-MFB", "Otros", "loose", "b.txt"), b"held-b")
    wcsv(os.path.join(hold, "manifest.csv"), ["new_path", "drive", "archive", "original_path", "size", "sha256"],
         [{"new_path": "MJesus-MFB\\Otros\\loose\\b.txt", "drive": C.DRIVE_LABEL, "archive": "",
           "original_path": f"{C.DRIVE_LABEL}\\Otros\\loose\\b.txt", "size": 6, "sha256": sha(b"held-b")}])
    # A1, stream C
    an = os.path.join(tmp, "analysis")
    a1 = []
    for rel in files:
        cls, ed, sd = "", "", ""
        if rel.startswith("MRI\\S"):
            parts = rel.split("\\")
            sd = "\\".join(parts[:2])
            if len(parts) > 3:
                ed = "\\".join(parts[:3])
            name = parts[-1]
            cls = ("mri-dicom" if name.endswith(".dcm") else "mri-kspace" if name == "fid" else
                   "mri-2dseq" if name == "2dseq" else "mri-study-params" if not ed else "mri-params")
        a1.append({"relpath": rel, "a1class": cls, "exam_dir": ed, "study_dir": sd})
    wcsv(os.path.join(an, "a1_files.csv.gz"), ["relpath", "a1class", "exam_dir", "study_dir"], a1, gz=True)
    wcsv(os.path.join(an, "mri_exams.csv"), ["exam_key", "class_detail"],
         [{"exam_key": "S1/5", "class_detail": "a1-identical"}, {"exam_key": "S2/3", "class_detail": "a1-identical"},
          {"exam_key": "S3/2", "class_detail": "b-export (same names, different bytes)"},
          {"exam_key": "S9/4", "class_detail": "e-neveracquired"},
          {"exam_key": "S4/7", "class_detail": "b-empty-prod (pending_dicom_regen: no-source)"}])
    wcsv(os.path.join(an, "excluded.csv"), ["sha256", "instrument", "size", "reason", "detail", "copies", "path"], [
        {"sha256": sha(b"czi-resave-of-prod"), "reason": "resave-of-production",
         "detail": "resave-of-production:ACQ-20230101-CELL-001; size diff 0 B"},
        {"sha256": sha(b"czi-resave-within"), "reason": "resave-within-plan",
         "detail": f"same name and second, pixel-identical: a re-save of x.czi; kept {sha(b'czi-kept-twin')}"},
        {"sha256": sha(b"czi-parent-gone"), "reason": "resave-of-production",
         "detail": "resave-of-production:ACQ-20230101-CELL-999; size diff 0 B"},
        {"sha256": sha(b"czi-derivative"), "reason": "derivative-nonraw", "detail": "crop; -> nonraw_derived.csv"}])
    wcsv(os.path.join(an, "out_of_scope.csv"), ["relpath", "sha256", "reason"],
         [{"relpath": "Microscopio\\biodonostia\\scan.czi", "sha256": sha(b"czi-foreign"),
           "reason": "Axioscan 7 #4661000340: not gjesus3's ZWSI"}])
    wcsv(os.path.join(an, "archive_check.csv"), ["original_name", "archive_result"],
         [{"original_name": "S1/5", "archive_result": "not in the archive (11.7 T study (the archive is the 7 T's))"}])
    wcsv(os.path.join(an, "archive_studies.csv"), ["study"], [{"study": "S3"}])
    return nas, staged, an


def run(tmp, nas, staged, an, out, extra=()):
    argv = ["--out", out, "--nas", nas, "--manifest", os.path.join(staged, "manifest.csv"), "--drive-manifest", "",
            "--a1-files", os.path.join(an, "a1_files.csv.gz"), "--a1-exams", os.path.join(an, "mri_exams.csv"),
            "--czi-excluded", os.path.join(an, "excluded.csv"), "--czi-out-of-scope", os.path.join(an, "out_of_scope.csv"),
            "--archive-check", os.path.join(an, "archive_check.csv"),
            "--archive-studies", os.path.join(an, "archive_studies.csv"), "--workers", "2", *extra]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = C.main(argv)
    text = buf.getvalue()
    with gzip.open(os.path.join(out, "closeout_files.csv.gz"), "rt", encoding="utf-8", newline="") as f:
        cats = {r["relpath"]: r for r in csv.DictReader(f)}
    return rc, text, cats


# ------------------------------------------------------------------------------------------------ tests

def test_rules_unit():
    print("the small rules")
    check(C.junk_rule("X\\desktop.ini").startswith("ruled"), "desktop.ini is Ryan's junk")
    check(C.junk_rule("X\\._a.nii") != "", "an AppleDouble file is junk")
    check(C.junk_rule("X\\Icon") != "" and C.junk_rule("X\\Icon\r") != "", "Icon<CR> is junk, either spelling")
    check(C.junk_rule("X\\~$report.docx") != "", "an Office owner file is junk")
    check(C.junk_rule("Otros\\Install Western Digital Software for Mac.dmg") != "", "the WD installer is junk")
    check(C.junk_rule("Y\\Install Western Digital Software for Mac.dmg") == "", "an installer of the same name elsewhere is not")
    check(C.junk_rule("X\\notes.ini") == "" and C.junk_rule("X\\thumbs.db.bak") == "", "ordinary names are not junk")
    check(C.personal_rule(BMJ + "Proteomica\\IMG_20220905_135733.jpg") != "", "a phone photo in biomaGUNE MJ is personal")
    check(C.personal_rule("Otros\\IMG_20220905_135733.jpg") == "", "the screen judges biomaGUNE MJ only")
    check(C.personal_rule(BMJ + "X\\CV Maria.pdf") == "", "an unjudged screen hit is no ruling (it stays a blocker)")
    check(C.mri_name_key("S__4") == "S/4" and C.mri_name_key("S/4") == "S/4", "both original_name forms")
    check(C.exam_key_of("MRI\\P\\S1\\5") == "S1/5", "the exam key is <study>/<exam>")
    check(C.verdict_line(0) == "READY TO DELETE" and C.verdict_line(3) == "BLOCKED: 3 files", "the verdict line")
    tmp = tempfile.mkdtemp(prefix="closeout_czi_")
    try:
        fields = ["sha256", "reason", "detail"]
        wcsv(os.path.join(tmp, "c.csv"), fields, [{"sha256": "a" * 64, "reason": "resave-within-plan", "detail": "C"}])
        wcsv(os.path.join(tmp, "f.csv"), fields, [{"sha256": "b" * 64, "reason": "resave-within-plan", "detail": "F"},
                                                  {"sha256": "a" * 64, "reason": "derivative-nonraw", "detail": "F"}])
        wcsv(os.path.join(tmp, "o.csv"), ["sha256", "reason"], [])
        ctx = C.Ctx()
        C.load_czi(ctx, [os.path.join(tmp, "c.csv"), os.path.join(tmp, "f.csv")], os.path.join(tmp, "o.csv"))
        check(set(ctx.czi) == {"a" * 64, "b" * 64} and ctx.czi["a" * 64][1] == "C",
              "several excluded lists (stream C's, a later .czi batch's): all read, the first list wins a repeat")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_end_to_end():
    print("end to end: every rule, the blockers, --stat, --walk, read-only")
    tmp = tempfile.mkdtemp(prefix="closeout_test_")
    try:
        nas, staged, an = build(tmp)
        before_nas, before_staged = tree_state(nas), tree_state(staged)
        put(os.path.join(staged, "files", "Otros", "unlisted.txt"), b"not in the manifest")
        rc, text, cats = run(tmp, nas, staged, an, os.path.join(tmp, "out1"), ["--stat", "--walk"])
        os.remove(os.path.join(staged, "files", "Otros", "unlisted.txt"))
        want = {
            "MRI\\S1\\5\\pdata\\1\\dicom\\MRIm01.dcm": "in-raw", "MRI\\S1\\5\\fid": "mri-kspace",
            "MRI\\S1\\5\\acqp": "mri-params", "MRI\\S1\\5\\pdata\\1\\2dseq": "mri-2dseq",
            "MRI\\S1\\subject": "mri-params", "MRI\\S3\\2\\pdata\\1\\dicom\\MRIm01.dcm": "mri-dicom-reexport",
            "Pili y Mili\\docs\\a.docx": "placed", "Pili y Mili\\docs\\copy of a.docx": "placed",
            "Otros\\loose\\b.txt": "holding", "Pili y Mili\\docs\\pack.zip": "archive-expanded",
            "Pili y Mili\\docs\\desktop.ini": "junk", "Otros\\seg\\._x.nii": "junk", "Otros\\seg\\Icon": "junk",
            "Otros\\Install Western Digital Software for Windows.exe": "junk", "MRI\\Flow\\folders.cache": "junk",
            "Pili y Mili\\docs\\empty.txt": "zero-byte", "MRI\\S1\\5\\empty_in_raw": "zero-byte",
            BMJ + "Proteomica\\Muestras\\IMG_20220905_135733.jpg": "personal",
            "Microscopio\\resave.czi": "czi-resave-of-production", "Microscopio\\twin.czi": "czi-resave-within-drive",
            "MRI\\S4\\7\\acqp": "placed",
        }
        want.update({r: "BLOCKER" for r in BLOCKING})
        bad = {r: (cats.get(r) or {}).get("category") for r, c in want.items() if (cats.get(r) or {}).get("category") != c}
        check(not bad, f"every file in its expected category ({len(want)} files){'' if not bad else ': ' + str(bad)}")
        check(len(cats) == len(want), "one row per manifest row")
        check(cats["Pili y Mili\\docs\\a.docx"]["detail"] == "MJesus-MFB\\docs\\a.docx",
              "a placed file points at its OWN copy, not the first with the same bytes")
        check("same bytes" in cats["Pili y Mili\\docs\\copy of a.docx"]["detail"] or
              cats["Pili y Mili\\docs\\copy of a.docx"]["detail"] == "MJesus-MFB\\docs\\copy of a.docx",
              "a copy is placed by its bytes")
        check(cats["MRI\\S1\\5\\pdata\\1\\dicom\\MRIm01.dcm"]["where"] == "ACQ-20200101-MRI-001",
              "bytes both in /raw/ and placed: /raw/ wins")
        hints = {r: cats[r]["detail"] for r in BLOCKING}
        check("feat/drive3-foreign-raw" in hints["Microscopio\\biodonostia\\scan.czi"], "foreign raw: its hint")
        check("never handed over" in hints["Microscopio\\crop.czi"], "a stream C derivative: its hint")
        check("holds no DICOM" in hints["MRI\\S1\\5\\pdata\\2\\2dseq"], "a 2dseq-only reconstruction: its hint")
        check("no registered exam" in hints["MRI\\S9\\subject"], "a study-level file of an unregistered study: its hint")
        check("placeholder" in hints["MRI\\S4\\7\\fid"] and "ACQ-20200101-MRI-004" in hints["MRI\\S4\\7\\fid"],
              "a DICOM-less placeholder's k-space is never ruled out (Ryan 2026-10-08): it blocks until placed")
        n = len(BLOCKING) + 1
        check(rc == 1 and text.rstrip().endswith(f"BLOCKED: {n} files"),
              f"the verdict: BLOCKED: {n} files ({len(BLOCKING)} in no category + 1 unlisted staged file)")
        check("unlisted 1" in text, "--walk finds the file its manifest does not list")
        check("MRI ORIGINALS NOT KEPT" in text and "M: not in the archive" in text, "the MRI originals statement")
        for name in ("categories.csv", "blockers.csv", "blockers_by_folder.csv", "mri_originals.csv",
                     "closeout_summary.txt", "live_raw_index.csv", "walk_differences.csv"):
            check(os.path.exists(os.path.join(tmp, "out1", name)), f"output {name}")
        check(tree_state(nas) == before_nas, "the NAS root is unchanged (every file: size, mtime, bytes)")
        st = tree_state(staged)
        check(st == before_staged, "the staged copy is unchanged")
        # --stat: a kept file gone from the NAS blocks
        tmp2 = tempfile.mkdtemp(prefix="closeout_test_")
        try:
            nas2, staged2, an2 = build(tmp2, with_blockers=False)
            rc, text, _c = run(tmp2, nas2, staged2, an2, os.path.join(tmp2, "out"), ["--stat", "--walk"])
            check(rc == 0 and text.rstrip().endswith("READY TO DELETE"), "nothing blocks -> READY TO DELETE (exit 0)")
            os.remove(os.path.join(nas2, "staging", "historical_drives_unassigned", "MJesus-MFB", "Otros", "loose", "b.txt"))
            rc, text, _c = run(tmp2, nas2, staged2, an2, os.path.join(tmp2, "out2"), ["--stat"])
            check(rc == 1 and text.rstrip().endswith("BLOCKED: 1 files"), "--stat: a held file missing on the NAS blocks")
            rc, text, _c = run(tmp2, nas2, staged2, an2, os.path.join(tmp2, "out3"))
            check(rc == 0, "without --stat the same run does not look (and says so)")
            check("not checked: --stat" in text, "... and says what it did not check")
            # a saved /raw/ index older than the registry
            idx = os.path.join(tmp2, "out3", "live_raw_index.csv")
            regp = os.path.join(nas2, "registries", "registry_raw.csv")
            with open(regp, "a", encoding="utf-8", newline="") as f:
                f.write("ACQ-20261009-CELL-001,2026-10-09T09:00:00Z,CELL,x/new.czi,/raw/MICROSCOPY/2026/2026-10/ACQ-20261009-CELL-001/\n")
            rc, text, _c = run(tmp2, nas2, staged2, an2, os.path.join(tmp2, "out4"), ["--raw-index", idx])
            check(rc == 1 and "input problem" in text.splitlines()[-1], "a /raw/ index older than the registry blocks")
        finally:
            shutil.rmtree(tmp2, ignore_errors=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_records_copy():
    print("the evidence copy (closeout_records.py): plan, dry run, copy, re-run, verify")
    import closeout_records as R
    tmp = tempfile.mkdtemp(prefix="closeout_records_test_")
    try:
        staged = os.path.join(tmp, "staging", "drive3_x")
        for name, b in (("manifest.csv", b"relpath,size\r\n"), ("copy.log", b"log"), ("drive_info.txt", b"info")):
            put(os.path.join(staged, name), b)
        put(os.path.join(staged, "files", "MRI", "x.dcm"), b"image")
        an = os.path.join(tmp, "d", "drive3_analysis")
        st = os.path.join(tmp, "d", "drive3_streams")
        put(os.path.join(an, "drive3_manifest.csv"), b"relpath,size\r\n")
        put(os.path.join(an, "a1", "report.txt"), b"a1")
        put(os.path.join(an, "a1", "_cache", "x.pkl"), b"cache")
        put(os.path.join(st, "mri", "out", "plan.csv"), b"plan")
        put(os.path.join(st, "mri", "out", "list.csv.gz"), b"gz")
        put(os.path.join(st, "mri", "stage", "S", "1", "fid"), b"kspace")
        put(os.path.join(st, "petct", "rehearsal_nas", "registries", "registry_raw.csv"), b"copy")
        put(os.path.join(st, "petct", "out", "frame.dcm"), b"image")
        put(os.path.join(st, "closeout", "records_plan_20261008", "records_plan.csv"), b"an earlier plan")
        rec = os.path.join(tmp, "nas", "records")
        put(os.path.join(rec, "README.txt"), b"Historical operator drives\r\nWho to ask: the Data Office.\r\n")
        put(os.path.join(rec, "records_manifest.csv"), "﻿relpath,size,sha256\r\n_tools\\a.py,1,abc\r\n".encode("utf-8"))
        before = open(os.path.join(rec, "records_manifest.csv"), "rb").read()
        out = os.path.join(tmp, "plan")
        src = [f"drive3_analysis={an}", f"drive3_streams={st}"]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = R.main(["plan", "--out", out, "--staged", staged, "--records", rec, "--source", *src])
        with open(os.path.join(out, "records_plan.csv"), encoding="utf-8", newline="") as f:
            plan = list(csv.DictReader(f))
        dests = {p["dest_rel"] for p in plan}
        want = {f"{R.DRIVE_DIR}\\manifest.csv", f"{R.DRIVE_DIR}\\copy.log", f"{R.DRIVE_DIR}\\drive_info.txt",
                f"{R.DRIVE_DIR}\\drive3_analysis\\a1\\report.txt", f"{R.DRIVE_DIR}\\drive3_streams\\mri\\out\\plan.csv",
                f"{R.DRIVE_DIR}\\drive3_streams\\mri\\out\\list.csv.gz"}
        check(rc == 0 and dests == want, "the plan: the staging run's records and the documents, nothing else"
              + ("" if dests == want else f": {sorted(dests ^ want)}"))
        check(all(p["sha256"] == sha(open(p["source"], "rb").read()) for p in plan), "the plan hashes every source")
        with open(os.path.join(out, "excluded.csv"), encoding="utf-8", newline="") as f:
            why = {os.path.basename(x["path"]): x["why"] for x in csv.DictReader(f)}
        check({"_cache", "stage", "rehearsal_nas", "drive3_manifest.csv", "frame.dcm", "records_plan_20261008"} <= set(why),
              "left out and said why: caches, staging copies, rehearsal roots, the duplicate manifest, image files, "
              "an earlier evidence plan")
        with contextlib.redirect_stdout(io.StringIO()):
            rc = R.main(["copy", "--plan", os.path.join(out, "records_plan.csv"), "--records", rec])
        check(rc == 0 and not os.path.exists(os.path.join(rec, R.DRIVE_DIR)), "copy without --execute writes nothing")
        with contextlib.redirect_stdout(io.StringIO()):
            rc = R.main(["copy", "--plan", os.path.join(out, "records_plan.csv"), "--records", rec, "--execute"])
        after = open(os.path.join(rec, "records_manifest.csv"), "rb").read()
        check(rc == 0 and after.startswith(before) and after.count(b"\r\n") == before.count(b"\r\n") + len(plan),
              "records_manifest.csv: the old bytes kept, one CRLF row per new file")
        readme = open(os.path.join(rec, "README.txt"), "rb").read()
        check(readme.count(R.README_MARK.encode()) == 1 and b"\n" not in readme.replace(b"\r\n", b"")
              and readme.startswith(b"Historical operator drives\r\nWho to ask"),
              "README.txt keeps its text and gains the drive-3 section once, CRLF only")
        with contextlib.redirect_stdout(io.StringIO()):
            rc = R.main(["copy", "--plan", os.path.join(out, "records_plan.csv"), "--records", rec, "--execute"])
        check(rc == 0 and open(os.path.join(rec, "records_manifest.csv"), "rb").read() == after
              and open(os.path.join(rec, "README.txt"), "rb").read() == readme,
              "a re-run copies nothing and changes neither document")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = R.main(["verify", "--plan", os.path.join(out, "records_plan.csv"), "--records", rec])
        check(rc == 0 and "RECORDS VERIFY PASS" in buf.getvalue(), "verify: PASS")
        put(os.path.join(rec, R.DRIVE_DIR, "copy.log"), b"tampered")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = R.main(["verify", "--plan", os.path.join(out, "records_plan.csv"), "--records", rec])
            rc2 = R.main(["copy", "--plan", os.path.join(out, "records_plan.csv"), "--records", rec, "--execute"])
        check(rc == 1 and rc2 == 2 and "CONFLICT" in buf.getvalue(),
              "a changed copy: verify FAILS, and copy refuses to write over it")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    test_rules_unit()
    test_end_to_end()
    test_records_copy()
    print(f"\n{'all passed' if not FAILS else f'{len(FAILS)} FAILED'}")
    sys.exit(1 if FAILS else 0)
