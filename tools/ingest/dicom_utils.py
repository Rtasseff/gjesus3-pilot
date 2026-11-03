"""DICOM header extraction utilities using pydicom.

History worth knowing (tasks/BACKLOG.md "Misc", 2026-08-12/13):

- `extract_study_date` used to read only the first 20 instances it met and
  return None when none of them carried a StudyDate -- and the ingest then
  fell back to TODAY for the ACQ-ID prefix and the registry date. Two HPIC
  acquisitions (nested one level deeper than LIONS) were committed as
  `ACQ-20260812-...` that way. It now walks lazily and keeps reading until a
  dated instance turns up, and the ingest refuses a case with no date at all
  (ingest_raw.py Step 3) instead of inventing one.
- `summarize_source` walked the tree three times (size, file_count, then the
  bounded header reads each re-walked) and, for extensionless DICOM, opened
  every file to check the `DICM` magic. It now walks once and shares the file
  list with the header readers.
"""

import os
from collections import Counter

try:
    import pydicom
    HAS_PYDICOM = True
except ImportError:
    HAS_PYDICOM = False


# Modalities that are not image series: a presentation state, a structured
# report, a key-object selection. A case often STARTS with one of these (they
# sort first), so a modality vote must not let them outvote the images.
_NON_IMAGE_MODALITIES = frozenset({"PR", "SR", "KO"})

# How many instances `detect_modality` parses at most. The date search has no
# such bound on purpose: it stops at the first dated instance, and a tree
# with no dated instance at all is exactly the case that must be reported,
# not guessed.
_MODALITY_MAX_PARSED = 20
# ... unless everything parsed so far is a non-image object; then keep going
# (bounded) until an image modality shows up, so "PR" is not reported as the
# modality of an MR exam.
_MODALITY_MAX_PARSED_SEEKING_IMAGE = 200


def _has_dicm_magic(path):
    """True if `path` carries the standard DICOM preamble (bytes 128..132 ==
    b"DICM"). Returns False on any OSError / short read."""
    try:
        with open(path, "rb") as f:
            f.seek(128)
            return f.read(4) == b"DICM"
    except OSError:
        return False


def iter_dicom_files(source_dir):
    """Yield DICOM file paths under `source_dir`, lazily, in walk order.

    A file counts as DICOM when it has the `.dcm` extension, or when it has no
    extension and carries the DICOM magic (bytes 128..132 == b"DICM"), so
    non-DICOM artifacts (README, LICENSE) are not mistaken for primary data.
    Directory entries are visited sorted, so the order is deterministic.
    """
    for root, dirs, files in os.walk(source_dir):
        dirs.sort()
        for fname in sorted(files):
            fpath = os.path.join(root, fname)
            if fname.lower().endswith(".dcm"):
                yield fpath
            elif not os.path.splitext(fname)[1] and _has_dicm_magic(fpath):
                yield fpath


def find_dicom_files(source_dir, limit=None):
    """Find DICOM files in a directory tree (see `iter_dicom_files`).

    Returns a list of file paths; at most `limit` of them when `limit` is set.
    """
    dcm_files = []
    for fpath in iter_dicom_files(source_dir):
        dcm_files.append(fpath)
        if limit and len(dcm_files) >= limit:
            break
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


def _iter_headers(source_dir, dcm_files=None):
    """Yield (path, header-dict) for each DICOM under `source_dir`, lazily.

    `dcm_files` lets a caller that already listed the files (summarize_source)
    avoid a second walk. Unreadable files are skipped, never raised.
    """
    paths = dcm_files if dcm_files is not None else iter_dicom_files(source_dir)
    for fpath in paths:
        try:
            info = read_dicom_header(fpath)
        except Exception:
            continue
        if info.get("error"):
            continue
        yield fpath, info


def extract_study_date(source_dir, dcm_files=None):
    """The StudyDate of the first DICOM instance under `source_dir` that has one.

    Returns the date string as stored (YYYYMMDD), or None when NO instance in
    the whole tree carries a StudyDate. There is deliberately no cap on how
    many instances are read: the search stops at the first dated one, and a
    tree where none is dated must come back as None so the ingest can refuse
    the case (a wrong date is worse than a deferred one).
    """
    for _fpath, info in _iter_headers(source_dir, dcm_files):
        if info.get("StudyDate"):
            return info["StudyDate"]
    return None


def detect_modality(source_dir, dcm_files=None):
    """Detect the dominant image Modality of the DICOM files under `source_dir`.

    Votes over the first `_MODALITY_MAX_PARSED` readable instances. Non-image
    objects (PR / SR / KO) take part in the vote only when NO image modality
    was seen at all, and the scan keeps reading (bounded) past a run of them
    until an image instance appears -- a case that sorts its presentation
    states first must still report the modality of its images.

    Returns the most common modality string, or None.
    """
    image_votes = []
    other_votes = []
    parsed = 0
    for _fpath, info in _iter_headers(source_dir, dcm_files):
        mod = info.get("Modality")
        if mod:
            parsed += 1
            if mod in _NON_IMAGE_MODALITIES:
                other_votes.append(mod)
            else:
                image_votes.append(mod)
        if image_votes and parsed >= _MODALITY_MAX_PARSED:
            break
        if parsed >= _MODALITY_MAX_PARSED_SEEKING_IMAGE:
            break

    votes = image_votes or other_votes
    if not votes:
        return None
    return Counter(votes).most_common(1)[0][0]


def summarize_source(source_dir):
    """Produce a summary dict of a DICOM source directory.

    Returns dict with: file_count, total_size_mb, modality, study_date,
    sample_header (key header fields of the first DICOM, or None).

    One walk of the tree: the byte total covers every file; `file_count` is
    the number of primary-data files (`.dcm` + extensionless DICOMs, per
    06_REGISTRIES §2.2 -- not auxiliary or bookkeeping artifacts); the header
    readers below reuse that file list instead of walking again.
    """
    # TODO (BACKLOG "external collaborator archives", issue #32): for
    # `acquisition_layout: archive`, count entries inside the stored archive's
    # central directory rather than walking the extracted source -- keeps the
    # semantic correct when the source is an archive provided by a
    # collaborator, and spares the walk over ~20k extracted instances.
    total_size = 0
    dcm_files = []
    for root, dirs, files in os.walk(source_dir):
        dirs.sort()
        for fname in sorted(files):
            fpath = os.path.join(root, fname)
            try:
                total_size += os.path.getsize(fpath)
            except OSError:
                pass
            if fname.lower().endswith(".dcm"):
                dcm_files.append(fpath)
            elif not os.path.splitext(fname)[1] and _has_dicm_magic(fpath):
                dcm_files.append(fpath)

    summary = {
        "file_count": len(dcm_files),
        "total_size_mb": round(total_size / 1_000_000, 1),
        "modality": detect_modality(source_dir, dcm_files),
        "study_date": extract_study_date(source_dir, dcm_files),
    }

    # Sample header from the first DICOM
    summary["sample_header"] = read_dicom_header(dcm_files[0]) if dcm_files else None

    return summary
