#!/usr/bin/env python3
"""test_ingest_small_fixes.py -- the ingest engine small fixes of 2026-10-10 (issue #7).

  1. dicom_utils.extract_study_date keeps reading past undated leading instances
     (the HPIC shape: >20 presentation states before the first dated image) and
     returns None only when no instance in the tree is dated; detect_modality
     reports the IMAGE modality, not the presentation states that sort first;
     summarize_source counts primary files from one walk.
  2. ingest_raw._resolve_acq_date: config date wins; else the DICOM StudyDate
     (backfilled into acquisition_datetime); else the case is REFUSED (None),
     unless ingest.allow_unknown_acquisition_date is set, which gives today
     with acq_date_is_real == False.
  3. operator/preview._preview_acq_id honours the .acq_id_seq.json reservation
     high-water, as allocate_acq_id does.
  4. metadata_sidecar.write_sidecar and checksum.write_checksums pin LF + UTF-8.
  5. paravision_metadata._scanner_model reads "BIOSPEC 500" as 11.7T (the 1H
     frequency in MHz), and the x10 stations as before.
  6. expand_batch exposes discovered.filename_stem beside discovered.filename.

Temporary directories only: no NAS, no database, no pytest.

Run:  python tools/test_ingest_small_fixes.py      (exit 0 = pass)
"""

import csv
import inspect
import json
import os
import sys
import tempfile
from datetime import datetime, timezone

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import pydicom  # noqa: E402
from pydicom.dataset import Dataset, FileMetaDataset  # noqa: E402
from pydicom.uid import ExplicitVRLittleEndian, generate_uid  # noqa: E402

from ingest import acq_id as acq_id_mod  # noqa: E402
from ingest import checksum, config, dicom_utils, metadata_sidecar  # noqa: E402
from ingest import paravision_metadata as pv  # noqa: E402
from ingest import registry  # noqa: E402
import ingest_raw  # noqa: E402

# `tools/operator/` clashes with the stdlib `operator` module; load it through
# its own loader under a non-colliding alias (tools/operator/IMPORT_CONTRACT.md).
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location(
    "gj_operator_loader", os.path.join(_THIS_DIR, "operator", "_loader.py"))
_l = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_l)
preview = _l.load().preview

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok:   {msg}")


# ---- Fixtures ---------------------------------------------------------------

def _write_dicom(path, modality, study_date=None):
    """A minimal but real DICOM file (preamble + DICM) with the given tags."""
    ds = Dataset()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.MediaStorageSOPClassUID = generate_uid()
    ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.SOPClassUID = ds.file_meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = ds.file_meta.MediaStorageSOPInstanceUID
    ds.Modality = modality
    ds.PatientID = "HPIC02"
    if study_date:
        ds.StudyDate = study_date
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    try:
        ds.save_as(path, enforce_file_format=True)   # pydicom >= 3
    except TypeError:
        ds.save_as(path, write_like_original=False)  # pydicom 2.x


def _hpic_like_tree(root):
    """25 undated presentation states in the top folder (they sort first), then
    the dated MR images one level down -- the layout that beat limit=20."""
    for i in range(25):
        _write_dicom(os.path.join(root, f"I{i:04d}.dcm"), "PR")
    sub = os.path.join(root, "S00")
    os.makedirs(sub)
    for i in range(5):
        _write_dicom(os.path.join(sub, f"I{i:04d}"), "MR", "20191022")  # extensionless
    with open(os.path.join(root, "README"), "w") as f:
        f.write("not a dicom\n")


# ---- 1. dicom_utils ------------------------------------------------------------

def test_dicom_utils():
    print("[dicom_utils: date past the first 20, image modality, one walk]")
    with tempfile.TemporaryDirectory() as d:
        _hpic_like_tree(d)
        check(dicom_utils.extract_study_date(d) == "20191022",
              "StudyDate found although the first 25 instances carry none")
        check(dicom_utils.detect_modality(d) == "MR",
              "modality is MR (the images), not PR (the presentation states that sort first)")
        s = dicom_utils.summarize_source(d)
        check(s["file_count"] == 30, f"file_count counts .dcm + extensionless DICOM only (got {s['file_count']})")
        check(s["study_date"] == "20191022" and s["modality"] == "MR",
              "summarize_source carries the same date and modality")
        check(s["sample_header"] is not None and s["sample_header"].get("PatientID") == "HPIC02",
              "sample_header is the first DICOM's header")
        check(len(dicom_utils.find_dicom_files(d, limit=3)) == 3, "find_dicom_files honours limit")

    with tempfile.TemporaryDirectory() as d:
        for i in range(3):
            _write_dicom(os.path.join(d, f"I{i}.dcm"), "PR")
        check(dicom_utils.extract_study_date(d) is None,
              "no dated instance anywhere -> None (never a guess)")
        check(dicom_utils.detect_modality(d) == "PR",
              "only non-image objects present -> they are still reported")

    with tempfile.TemporaryDirectory() as d:
        s = dicom_utils.summarize_source(d)
        check(s["file_count"] == 0 and s["study_date"] is None and s["sample_header"] is None,
              "empty source summarizes to 0 / None / None")


# ---- 2. the date step -----------------------------------------------------------

def test_resolve_acq_date():
    print("[ingest_raw._resolve_acq_date: config, StudyDate, refuse, opt-in today]")
    logged = []

    def log_fn(msg, level="INFO"):
        logged.append((level, msg))

    r = ingest_raw._resolve_acq_date("2019-10-22T10:21:42+01:00", {"study_date": "20200101"}, {}, log_fn)
    check(r == ("20191022", True, None), "the config's acquisition_datetime wins over the StudyDate")

    logged.clear()
    r = ingest_raw._resolve_acq_date("", {"study_date": "20191022"}, {}, log_fn)
    check(r == ("20191022", True, "2019-10-22"), "no config date -> the DICOM StudyDate, backfilled as ISO")
    check(any("StudyDate" in m for _l, m in logged), "the StudyDate fallback is logged")

    logged.clear()
    r = ingest_raw._resolve_acq_date("", {"study_date": None}, {}, log_fn)
    check(r is None, "no date anywhere -> the case is refused (None), not dated to today")
    check(any(l == "ERROR" and "REFUSED" in m for l, m in logged), "the refusal is an ERROR line")

    logged.clear()
    r = ingest_raw._resolve_acq_date("", {}, {"allow_unknown_acquisition_date": True}, log_fn)
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    check(r == (today, False, None), "opt-in flag -> today, flagged as not real (age withheld)")
    check(any(l == "WARN" and "allow_unknown_acquisition_date" in m for l, m in logged),
          "the opt-in path WARNs and names the flag")

    r = ingest_raw._resolve_acq_date("NA", {"study_date": "2019"}, {}, log_fn)
    check(r is None, "a malformed StudyDate (not 8 digits) does not count as a date")

    src = inspect.getsource(ingest_raw.ingest_single)
    check("_resolve_acq_date(" in src and "return None, False" in src,
          "ingest_single calls the helper and returns (None, False) on refusal")


# ---- 3. preview honours the reservation -------------------------------------------

def test_preview_reservation():
    print("[preview._preview_acq_id reads .acq_id_seq.json]")
    with tempfile.TemporaryDirectory() as d:
        regs = os.path.join(d, "registries")
        os.makedirs(regs)
        reg_path = os.path.join(regs, "registry_raw.csv")
        with open(reg_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(registry.REGISTRY_FIELDS)
            row = dict.fromkeys(registry.REGISTRY_FIELDS, "")
            row["acq_id"] = "ACQ-20260710-MRI-002"
            w.writerow([row[c] for c in registry.REGISTRY_FIELDS])
        warnings = []
        got = preview._preview_acq_id("20260710", "MRI", reg_path, {}, warnings)
        check(got == "ACQ-20260710-MRI-003", f"no reservation: next after the registry ({got})")

        with open(os.path.join(regs, acq_id_mod.RESERVATIONS_FILENAME), "w", encoding="utf-8") as f:
            json.dump({"ACQ-20260710-MRI-": 17}, f)
        seq_seen = {}
        got = preview._preview_acq_id("20260710", "MRI", reg_path, seq_seen, warnings)
        check(got == "ACQ-20260710-MRI-018", f"reservation at 17 -> the preview shows -018 ({got})")
        got2 = preview._preview_acq_id("20260710", "MRI", reg_path, seq_seen, warnings)
        check(got2 == "ACQ-20260710-MRI-019", "and the in-batch counter continues from there")
        check(not os.path.exists(os.path.join(regs, acq_id_mod.RESERVATIONS_FILENAME + ".tmp"))
              and json.load(open(os.path.join(regs, acq_id_mod.RESERVATIONS_FILENAME))) == {"ACQ-20260710-MRI-": 17},
              "the preview wrote nothing (reservation unchanged)")
        real = acq_id_mod.allocate_acq_id("20260710", "MRI", reg_path, regs)
        check(real == "ACQ-20260710-MRI-018", "and the real allocation agrees with the preview")
        check(not warnings, f"no warnings raised ({warnings})")


# ---- 4. LF + UTF-8 writers --------------------------------------------------------

def test_writers_pin_newline():
    print("[write_sidecar / write_checksums: LF + UTF-8 on every OS]")
    for fn in (metadata_sidecar.write_sidecar, checksum.write_checksums):
        src = inspect.getsource(fn)
        check('newline="\\n"' in src and 'encoding="utf-8"' in src,
              f"{fn.__name__} opens with newline='\\n' and encoding='utf-8'")
    with tempfile.TemporaryDirectory() as d:
        p = metadata_sidecar.write_sidecar(d, {"a": 1, "name": "Jesús"})
        raw = open(p, "rb").read()
        check(b"\r" not in raw and raw.endswith(b"\n"), "sidecar bytes carry LF only")
        check(json.loads(raw.decode("utf-8"))["name"] == "Jesús", "sidecar round-trips UTF-8 content")
        cp = os.path.join(d, "checksums.json")
        checksum.write_checksums({"x.czi": "00"}, cp)
        raw = open(cp, "rb").read()
        check(b"\r" not in raw and json.loads(raw)["files"] == {"x.czi": "00"}, "checksums.json LF only")


# ---- 5. scanner model -----------------------------------------------------------------

def test_scanner_model():
    print("[paravision_metadata._scanner_model: BIOSPEC 500 is 11.7T]")
    cases = {
        "Biospec 70/30": "Bruker BioSpec 7T",
        "Biospec 117/16": "Bruker BioSpec 11.7T",
        "Biospec 94/20": "Bruker BioSpec 9.4T",
        "BIOSPEC 500": "Bruker BioSpec 11.7T",
        "Biospec 300": "Bruker BioSpec 7T",
        "Biospec 999": "",          # 23.5T: not a known BioSpec -> no guess
        "Avance": "",
    }
    for station, want in cases.items():
        got = pv._scanner_model({"acqp": {"ACQ_station": station}})
        check(got == want, f"{station!r} -> {want!r} (got {got!r})")


# ---- 6. discovered.filename_stem ----------------------------------------------------

def test_filename_stem():
    print("[config: discovered.filename_stem]")
    src = inspect.getsource(config.expand_batch) if hasattr(config, "expand_batch") else inspect.getsource(config)
    check('discovered["filename_stem"]' in src, "expand_batch sets discovered.filename_stem")
    gen = open(os.path.join(_THIS_DIR, "gen_microscopy_bestguess_configs.py"), encoding="utf-8").read()
    check("${{discovered.filename_stem}}" in gen and "${{discovered.filename}}\"" not in gen,
          "the best-guess generator uses the stem for sample_id")


def main():
    test_dicom_utils()
    test_resolve_acq_date()
    test_preview_reservation()
    test_writers_pin_newline()
    test_scanner_model()
    test_filename_stem()
    print()
    if FAILS:
        print(f"{len(FAILS)} FAILURE(S):")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print("ALL INGEST-SMALL-FIXES CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
