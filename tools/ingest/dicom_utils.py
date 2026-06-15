"""DICOM header extraction utilities using pydicom."""

import os
from pathlib import Path

try:
    import pydicom
    HAS_PYDICOM = True
except ImportError:
    HAS_PYDICOM = False


def _has_dicm_magic(path):
    """True if `path` carries the standard DICOM preamble (bytes 128..132 ==
    b"DICM"). Returns False on any OSError / short read."""
    try:
        with open(path, "rb") as f:
            f.seek(128)
            return f.read(4) == b"DICM"
    except OSError:
        return False


def find_dicom_files(source_dir, limit=None):
    """Find DICOM files in a directory tree.

    Returns list of file paths. Checks for .dcm extension first,
    then falls back to extensionless files that carry the DICOM magic
    (bytes 128..132 == b"DICM") so non-DICOM artifacts (README, LICENSE)
    are not mistaken for primary data and inflate file_count.
    """
    dcm_files = []
    for root, _dirs, files in os.walk(source_dir):
        for fname in sorted(files):
            fpath = os.path.join(root, fname)
            if fname.lower().endswith(".dcm"):
                dcm_files.append(fpath)
            elif not os.path.splitext(fname)[1] and _has_dicm_magic(fpath):
                # Extensionless file with the DICOM preamble — accept as DICOM
                dcm_files.append(fpath)
            if limit and len(dcm_files) >= limit:
                return dcm_files
    return dcm_files


def read_dicom_header(filepath):
    """Read a DICOM file and return key header fields.

    Returns dict with keys: Modality, StudyDate, PatientID,
    StudyDescription, or None values if missing.
    If pydicom is not installed, returns dict with error key.
    """
    if not HAS_PYDICOM:
        return {"error": "pydicom not installed"}

    try:
        ds = pydicom.dcmread(filepath, stop_before_pixels=True, force=True)
    except Exception as e:
        return {"error": str(e)}

    return {
        "Modality": getattr(ds, "Modality", None),
        "StudyDate": getattr(ds, "StudyDate", None),
        "PatientID": getattr(ds, "PatientID", None),
        "StudyDescription": getattr(ds, "StudyDescription", None),
        "SeriesDescription": getattr(ds, "SeriesDescription", None),
        "InstitutionName": getattr(ds, "InstitutionName", None),
    }


def extract_study_date(source_dir):
    """Extract StudyDate from the first readable DICOM file in source_dir.

    Returns date string in YYYYMMDD format, or None if not found.
    """
    dcm_files = find_dicom_files(source_dir, limit=20)
    for fpath in dcm_files:
        try:
            info = read_dicom_header(fpath)
            if info.get("StudyDate"):
                return info["StudyDate"]
        except Exception:
            continue
    return None


def detect_modality(source_dir):
    """Detect the dominant DICOM Modality from files in source_dir.

    Returns the most common Modality string, or None.
    """
    dcm_files = find_dicom_files(source_dir, limit=20)
    modalities = []
    for fpath in dcm_files:
        try:
            info = read_dicom_header(fpath)
            mod = info.get("Modality")
            if mod:
                modalities.append(mod)
        except Exception:
            continue

    if not modalities:
        return None

    # Return most common
    from collections import Counter
    counts = Counter(modalities)
    return counts.most_common(1)[0][0]


def summarize_source(source_dir):
    """Produce a summary dict of a DICOM source directory.

    Returns dict with: file_count, total_size_mb, modality, study_date,
    sample_dicom_info (full header of first file).
    """
    # Walk the source for total size; separately count primary-data files
    # (.dcm + extensionless DICOMs) for `file_count`. Per 06_REGISTRIES §2.2,
    # file_count is the count of primary-data files in the acquisition —
    # not auxiliary or bookkeeping artifacts.
    # TODO: once the DICOM compress-on-ingest path lands, count entries
    # inside the produced .zip's central directory rather than walking the
    # source — keeps the semantic correct when the source is already an
    # archive provided by a collaborator.
    total_size = 0
    for root, _dirs, files in os.walk(source_dir):
        for fname in files:
            total_size += os.path.getsize(os.path.join(root, fname))

    dcm_files = find_dicom_files(source_dir)

    summary = {
        "file_count": len(dcm_files),
        "total_size_mb": round(total_size / 1_000_000, 1),
        "modality": detect_modality(source_dir),
        "study_date": extract_study_date(source_dir),
    }

    # Sample header from first DICOM
    dcm_files = find_dicom_files(source_dir, limit=1)
    if dcm_files:
        summary["sample_header"] = read_dicom_header(dcm_files[0])
    else:
        summary["sample_header"] = None

    return summary
