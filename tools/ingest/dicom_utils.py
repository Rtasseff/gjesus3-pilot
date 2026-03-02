"""DICOM header extraction utilities using pydicom."""

import os
from pathlib import Path

try:
    import pydicom
    HAS_PYDICOM = True
except ImportError:
    HAS_PYDICOM = False


def find_dicom_files(source_dir, limit=None):
    """Find DICOM files in a directory tree.

    Returns list of file paths. Checks for .dcm extension first,
    then falls back to attempting pydicom read on extensionless files.
    """
    dcm_files = []
    for root, _dirs, files in os.walk(source_dir):
        for fname in sorted(files):
            fpath = os.path.join(root, fname)
            if fname.lower().endswith(".dcm"):
                dcm_files.append(fpath)
            elif not os.path.splitext(fname)[1]:
                # Extensionless file — may be DICOM
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
    all_files = []
    total_size = 0
    for root, _dirs, files in os.walk(source_dir):
        for fname in files:
            fpath = os.path.join(root, fname)
            all_files.append(fpath)
            total_size += os.path.getsize(fpath)

    summary = {
        "file_count": len(all_files),
        "total_size_mb": round(total_size / (1024 * 1024), 1),
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
