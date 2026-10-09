"""Tests for stream AR's extraction and helpers (no network, no J:, a temp dir only).

    python tools/drive_staging/mri_archive/test_ar_extract.py

  1. w() refuses a path outside BASE and any path under pull\\ (the tarballs are never written).
  2. jcamp_get reads ##$KEY=value and ##$KEY=( dims )<value>; nonimage_marker follows is_nonimage_exam's rule.
  3. extract_one: k-space listed, not extracted; every other file hashed; the tarball's SHA-1 checked against the
     manifest's; a member outside <study>/ refuses the study; a SHORT tarball is salvaged up to the cut, the member
     being read is removed and its exam recorded as incomplete.
"""
import hashlib
import io
import json
import os
import sys
import tarfile
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ar_common as C  # noqa: E402

FAILS = []


def check(ok, what):
    print(f"{'ok  ' if ok else 'FAIL'} {what}")
    if not ok:
        FAILS.append(what)


def make_tar(path, study, files, top=None):
    with tarfile.open(path, "w:gz") as tf:
        for name, data in files:
            ti = tarfile.TarInfo(f"{top or study}/{name}")
            ti.size = len(data)
            tf.addfile(ti, io.BytesIO(data))
    return hashlib.sha1(open(path, "rb").read()).hexdigest()


def main():
    tmp = tempfile.mkdtemp(prefix="ar_test_")
    C.BASE = tmp
    C.PULL = os.path.join(tmp, "pull")
    C.EXTRACT = os.path.join(tmp, "extract")
    C.XMAN = os.path.join(C.EXTRACT, "_manifests")
    C.OUT = os.path.join(tmp, "out")
    import ar_01_extract as X

    # 1. the write guard
    for bad in (os.path.join(tmp, "pull", "x.tar.gz"), os.path.join(os.path.dirname(tmp), "elsewhere", "f")):
        try:
            C.w(bad)
            check(False, f"w() refuses {bad}")
        except RuntimeError:
            check(True, f"w() refuses {os.path.relpath(bad, os.path.dirname(tmp))}")
    check(C.w(tmp, "extract", "C", "s").startswith(tmp), "w() allows a path under extract")

    # 2. the JCAMP reader
    p = os.path.join(tmp, "acqp")
    open(p, "w", encoding="latin-1").write(
        "##TITLE=x\n##$ACQ_method=<Bruker:FLASH>\n##$ACQ_scan_name=( 64 )\n<1_Localizer (E1)>\n"
        "##$ACQ_time=<2020-01-02T10:11:12,345+0100>\n##$PULPROG=<STEAM.ppg>\n##$NR=1\n$$ comment\n##END=\n")
    check(C.jcamp_get(p, "ACQ_method", "ACQ_scan_name", "ACQ_time", "NR", "MISSING") ==
          ["Bruker:FLASH", "1_Localizer (E1)", "2020-01-02T10:11:12,345+0100", "1", ""], "jcamp_get values")
    ex = os.path.join(tmp, "exam")
    os.makedirs(ex)
    os.replace(p, os.path.join(ex, "acqp"))
    check(C.nonimage_marker(ex) == "STEAM", "nonimage_marker from PULPROG")

    # 3. extraction
    study = "20200101_101010_jrc200101_m1_0619_1_1"
    files = [("1/acqp", b"a" * 100), ("1/fid", b"k" * 5000), ("1/pdata/1/2dseq", b"s" * 300),
             ("1/pdata/1/dicom/MRIm1.dcm", b"d" * 200), ("2/acqp", b"b" * 100), ("2/rawdata.job0", b"r" * 4000),
             ("2/pdata/1/2dseq", os.urandom(200000))]
    tp = os.path.join(tmp, "good.tar.gz")
    s1 = make_tar(tp, study, files)
    d = X.extract_one(study, "C", tp, s1, "")
    check(not d["errors"] and d["hash_matches_fetch"] is True and not d["truncated"], "a good tarball extracts cleanly")
    check(d["extracted_files"] == 5 and d["kspace_files"] == 2, "k-space listed, not extracted")
    got = os.path.join(C.EXTRACT, "C", study, "1", "pdata", "1", "dicom", "MRIm1.dcm")
    check(open(got, "rb").read() == b"d" * 200 and not os.path.exists(os.path.join(C.EXTRACT, "C", study, "1", "fid")),
          "the files land under extract\\C\\<study>, without k-space")
    m = {r["member"]: r for r in C.members(study)}
    check(m[f"{study}/1/pdata/1/dicom/MRIm1.dcm"]["sha256"] == hashlib.sha256(b"d" * 200).hexdigest(),
          "the member list carries each file's SHA-256")
    check(os.path.exists(os.path.join(C.XMAN, study + ".done")), ".done written")
    study2 = study.replace("m1", "m2")
    tp2 = os.path.join(tmp, "bad_sha.tar.gz")
    make_tar(tp2, study2, files)
    d = X.extract_one(study2, "C", tp2, "0" * 40, "")
    check(d["errors"] and not os.path.exists(os.path.join(C.XMAN, study2 + ".done")), "a SHA-1 mismatch refuses the study")
    study3 = study.replace("m1", "m3")
    tp3 = os.path.join(tmp, "outside.tar.gz")
    s3 = make_tar(tp3, study3, files, top="other_folder")
    d = X.extract_one(study3, "C", tp3, s3, "")
    check(d["errors"] and not os.path.exists(os.path.join(C.XMAN, study3 + ".done")), "a member outside <study>/ refuses")
    study4 = study.replace("m1", "m4")
    tp4 = os.path.join(tmp, "short.tar.gz")
    make_tar(tp4, study4, files)
    raw = open(tp4, "rb").read()
    short = raw[:len(raw) - 2000]
    open(tp4, "wb").write(short)
    d = X.extract_one(study4, "A", tp4, hashlib.sha1(short).hexdigest(), "")
    t = d.get("truncated") or {}
    check(not d["errors"] and t.get("incomplete_exam") == "2", f"a short tarball is salvaged; incomplete exam {t.get('incomplete_exam')}")
    base = os.path.join(C.EXTRACT, "_in", study4)
    check(os.path.exists(os.path.join(base, "1", "pdata", "1", "dicom", "MRIm1.dcm")) and
          not os.path.exists(os.path.join(base, "2", "pdata", "1", "2dseq")), "complete members kept, the cut one removed")
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)       # the test's own temp dir only
    print(f"\n{'all passed' if not FAILS else f'{len(FAILS)} FAILED'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
