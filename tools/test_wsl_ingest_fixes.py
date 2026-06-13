#!/usr/bin/env python3
"""test_wsl_ingest_fixes.py — WSL/Dicomifier execution-environment fixes (2026-06-13).

Covers the blockers the historical MRI pull hit when run from WSL:
  - _copy_to_nas: copies file bytes even when the CIFS mount rejects
    timestamp/mode preservation (the WSL->NAS copy2/os.utime crash)
  - paravision_regen.is_nonimage_exam: STEAM/PRESS/Wobble detected + skipped
    (so spectroscopy doesn't crash the image-regen path)
  - animal_db.credentials_available: False when the .my.cnf is missing
    (drives the one-time "all subjects -> pending" pre-flight WARN)

Run:  PYTHONPATH=tools python tools/test_wsl_ingest_fixes.py
"""

import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/

import ingest_raw  # noqa: E402
import animal_db  # noqa: E402
from ingest import paravision_regen  # noqa: E402

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok:   {msg}")


def test_copy_to_nas_tolerates_copystat_failure():
    print("[_copy_to_nas survives a CIFS utime/copystat rejection]")
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "src.bin")
        dst = os.path.join(d, "dst.bin")
        payload = b"DICOM-ish bytes " * 4096
        with open(src, "wb") as f:
            f.write(payload)
        # Simulate a CIFS mount that rejects timestamp/mode preservation:
        # copystat raises OSError (as os.utime does on such mounts).
        orig = shutil.copystat

        def boom(*a, **k):
            raise OSError("utime: operation not permitted (CIFS)")

        shutil.copystat = boom
        try:
            ingest_raw._copy_to_nas(src, dst)
        finally:
            shutil.copystat = orig
        check(os.path.isfile(dst), "destination file was created")
        with open(dst, "rb") as f:
            check(f.read() == payload, "bytes copied intact despite copystat OSError")


def test_nonimage_exam_detection():
    print("[paravision_regen.is_nonimage_exam]")
    with tempfile.TemporaryDirectory() as d:
        method = os.path.join(d, "method")

        def write_method(value):
            with open(method, "w", encoding="utf-8") as f:
                f.write(f"##$Method=<{value}>\n##END=\n")

        write_method("Bruker:STEAM")
        nonimg, marker = paravision_regen.is_nonimage_exam(d)
        check(nonimg and marker == "STEAM", "STEAM method flagged non-image")

        write_method("User:PRESS")
        nonimg2, marker2 = paravision_regen.is_nonimage_exam(d)
        check(nonimg2 and marker2 == "PRESS", "PRESS method flagged non-image")

        write_method("Bruker:IgFLASH")
        nonimg3, _ = paravision_regen.is_nonimage_exam(d)
        check(not nonimg3, "FLASH (image) method is NOT flagged (regenerable)")

        # No method file at all -> empty signature -> treated as image (don't
        # over-skip; the per-file backstop still protects regen).
        with tempfile.TemporaryDirectory() as empty:
            nonimg4, _ = paravision_regen.is_nonimage_exam(empty)
            check(not nonimg4, "missing method file -> not flagged non-image")


def test_credentials_available():
    print("[animal_db.credentials_available]")
    orig = animal_db.CNF_PATH
    animal_db.CNF_PATH = os.path.join(tempfile.gettempdir(), "definitely_no_such.my.cnf")
    try:
        check(animal_db.credentials_available() is False,
              "missing .my.cnf -> credentials unavailable (drives the pending WARN)")
    finally:
        animal_db.CNF_PATH = orig


def main():
    test_copy_to_nas_tolerates_copystat_failure()
    test_nonimage_exam_detection()
    test_credentials_available()
    print()
    if FAILS:
        print(f"FAILED ({len(FAILS)}):")
        for m in FAILS:
            print(f"  - {m}")
        return 1
    print("ALL PASS (WSL/Dicomifier execution-environment fixes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
