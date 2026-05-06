"""Source summarization for microscopy single-file acquisitions (.czi etc.).

Mirrors the dicom_utils.summarize_source signature so the format-summarizer
dispatch in ingest_raw.py can swap implementations by ecosystem.

Embedded-metadata extraction (objective, pixel size, channels, ...) is a
separate concern — that lives in a future probe-driven extractor and is
not handled here. This module only inventories files.
"""

import os


SUPPORTED_EXTENSIONS = (".czi", ".tif", ".tiff")


def summarize_source(source_path):
    """Inventory a microscopy source (single file or folder containing one).

    Returns dict shape compatible with dicom_utils.summarize_source:
        file_count, total_size_mb, modality (always ""), study_date (""),
        primary_extension, primary_filename.

    `primary_extension` and `primary_filename` are convenience fields used
    downstream when copying the file under a canonical name.
    """
    if os.path.isfile(source_path):
        size = os.path.getsize(source_path)
        ext = os.path.splitext(source_path)[1].lower()
        return {
            "file_count": 1,
            "total_size_mb": round(size / (1024 * 1024), 1),
            "modality": "",
            "study_date": "",
            "primary_extension": ext,
            "primary_filename": os.path.basename(source_path),
        }

    # Folder mode: locate the single primary file inside.
    primary = None
    extra_files = []
    total_size = 0
    file_count = 0
    for root, _dirs, files in os.walk(source_path):
        for fname in files:
            fpath = os.path.join(root, fname)
            file_count += 1
            total_size += os.path.getsize(fpath)
            ext = os.path.splitext(fname)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                if primary is None:
                    primary = fpath
                else:
                    extra_files.append(fpath)

    return {
        "file_count": file_count,
        "total_size_mb": round(total_size / (1024 * 1024), 1),
        "modality": "",
        "study_date": "",
        "primary_extension": (
            os.path.splitext(primary)[1].lower() if primary else ""
        ),
        "primary_filename": os.path.basename(primary) if primary else "",
        "extra_microscopy_files": extra_files,
    }
