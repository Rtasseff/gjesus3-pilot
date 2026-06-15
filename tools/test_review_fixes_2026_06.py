#!/usr/bin/env python3
"""test_review_fixes_2026_06.py — regression tests for the 2026-06 code-review
correction pass (branch review/code-inspection-2026-06-12).

Covers the higher-value functional fixes that previously lacked coverage:
  - jcampdx: the ##END= terminator is no longer captured as a junk key
  - dicom_utils: extensionless non-DICOM files are excluded (DICM-magic gate)
  - registry.assert_header_compatible: the pre-flight header check
  - extract_xmri_archives: .extracted sentinel + partial-cleanup + --force
  - ingest_raw._resolve_archive_primary: multi-dot (.tar.gz) extension match
  - readme: acquisition date falls back to acquisition_datetime

(The stale-lock-break race fix is covered in ingest/test_locking.py.)

Run:  PYTHONPATH=tools python tools/test_review_fixes_2026_06.py
"""

import csv
import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ on path

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok:   {msg}")


def test_jcampdx_end_terminator():
    print("[jcampdx ##END terminator]")
    from ingest import jcampdx
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "subject")
        with open(p, "w", encoding="utf-8") as f:
            f.write("##TITLE=Parameter List\n")
            f.write("##$SUBJECT_id=<m13>\n")
            f.write("##END=\n")
        out = jcampdx.parse_file(p)
        check("END" not in out, "##END= is NOT captured as a junk key")
        check(out.get("SUBJECT_id") == "m13", "the real ##$ parameter is parsed")
        check(out.get("TITLE") == "Parameter List", "the ## header is parsed")


def test_dicom_magic_gate():
    print("[dicom_utils DICM-magic gate]")
    from ingest import dicom_utils
    with tempfile.TemporaryDirectory() as d:
        dcm = os.path.join(d, "I0001")  # extensionless real DICOM
        with open(dcm, "wb") as f:
            f.write(b"\x00" * 128 + b"DICM" + b"payload")
        readme = os.path.join(d, "README")  # extensionless non-DICOM
        with open(readme, "w", encoding="utf-8") as f:
            f.write("not a dicom file")
        named = os.path.join(d, "scan.dcm")  # .dcm-suffixed (always accepted)
        with open(named, "wb") as f:
            f.write(b"anything")
        found = {os.path.basename(p) for p in dicom_utils.find_dicom_files(d)}
        check("I0001" in found, "extensionless DICOM (DICM magic) is counted")
        check("README" not in found, "extensionless non-DICOM is excluded")
        check("scan.dcm" in found, ".dcm-suffixed file is counted")
        check(dicom_utils._has_dicm_magic(dcm) is True, "_has_dicm_magic True for DICM preamble")
        check(dicom_utils._has_dicm_magic(readme) is False, "_has_dicm_magic False for text")


def test_registry_header_preflight():
    print("[registry.assert_header_compatible]")
    from ingest import registry
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "registry_raw.csv")
        registry.assert_header_compatible(path)  # missing file -> no-op
        check(True, "no-op on a missing registry file")
        with open(path, "w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow(registry.REGISTRY_FIELDS)
        registry.assert_header_compatible(path)  # correct header -> ok
        check(True, "passes on the correct header")
        with open(path, "w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow(["acq_id", "wrong_second_column"])
        raised = False
        try:
            registry.assert_header_compatible(path)
        except RuntimeError:
            raised = True
        check(raised, "raises RuntimeError on a header mismatch")


def test_archive_primary_multidot():
    print("[ingest_raw._resolve_archive_primary multi-dot]")
    import ingest_raw
    with tempfile.TemporaryDirectory() as d:
        for name in ("LEONE_1.tar.gz", "HPIC02.rar", "OTHER.zip"):
            open(os.path.join(d, name), "w").close()
        cfg = {"discovered": {"folder_name": "LEONE_1"}, "source_path": "/x/LEONE_1"}
        res = ingest_raw._resolve_archive_primary(cfg, {"archive_primary_from": d})
        check(os.path.basename(res) == "LEONE_1.tar.gz",
              "matches a .tar.gz compound extension (was a RuntimeError before)")
        cfg2 = {"discovered": {"folder_name": "HPIC02"}, "source_path": "/x/HPIC02"}
        res2 = ingest_raw._resolve_archive_primary(cfg2, {"archive_primary_from": d})
        check(os.path.basename(res2) == "HPIC02.rar", "matches a .rar single extension")


def test_extract_xmri_sentinel_force():
    print("[extract_xmri_archives sentinel + force]")
    import extract_xmri_archives as ex
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "src")
        os.makedirs(src)
        dest = os.path.join(d, "dest")
        with zipfile.ZipFile(os.path.join(src, "CASE1.zip"), "w") as z:
            z.writestr("a.dcm", "x")
            z.writestr("sub/b.dcm", "y")
        case_dir = os.path.join(dest, "CASE1")

        check(ex.extract_all(src, dest) == (1, 0, 0), "first run extracts")
        check(os.path.isfile(os.path.join(case_dir, ex.EXTRACTED_SENTINEL)),
              ".extracted sentinel is written on success")
        check(ex.extract_all(src, dest) == (0, 1, 0), "re-run skips (sentinel present)")

        # Simulate a partial/interrupted extraction: files present, no sentinel.
        os.remove(os.path.join(case_dir, ex.EXTRACTED_SENTINEL))
        check(ex.extract_all(src, dest) == (1, 0, 0),
              "a non-empty dir WITHOUT the sentinel is re-extracted (not accepted)")
        check(ex.extract_all(src, dest, force=True) == (1, 0, 0),
              "--force re-extracts even with the sentinel present")


def test_extract_xmri_partial_cleanup():
    print("[extract_xmri_archives partial cleanup on failure]")
    import extract_xmri_archives as ex
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "src")
        os.makedirs(src)
        dest = os.path.join(d, "dest")
        with open(os.path.join(src, "BAD.zip"), "wb") as f:
            f.write(b"this is not a valid zip archive")
        result = ex.extract_all(src, dest)
        check(result == (0, 0, 1), "a corrupt archive is reported as failed")
        check(not os.path.exists(os.path.join(dest, "BAD")),
              "the partial output dir is removed on failure (no truncated tree left)")


def test_readme_date_fallback():
    print("[readme acquisition-date fallback]")
    from ingest import readme
    with tempfile.TemporaryDirectory() as d:
        cfg = {
            "data_ecosystem": "MICROSCOPY",
            "acquisition_datetime": "2026-04-22T00:00:00Z",
            "primary_file_name": "ACQ-20260422-CELL-001.czi",
            "file_format": ".czi",
        }
        summary = {"file_count": 1, "total_size_mb": 1.0}  # no study_date
        readme.generate_readme("ACQ-20260422-CELL-001", cfg, summary, d)
        with open(os.path.join(d, "README.txt"), encoding="utf-8") as f:
            content = f.read()
        check("2026-04-22" in content,
              "README shows the date from acquisition_datetime (was 'unknown')")


def main():
    test_jcampdx_end_terminator()
    test_dicom_magic_gate()
    test_registry_header_preflight()
    test_archive_primary_multidot()
    test_extract_xmri_sentinel_force()
    test_extract_xmri_partial_cleanup()
    test_readme_date_fallback()
    print()
    if FAILS:
        print(f"FAILED ({len(FAILS)}):")
        for m in FAILS:
            print(f"  - {m}")
        return 1
    print("ALL PASS (2026-06 review correction-pass fixes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
