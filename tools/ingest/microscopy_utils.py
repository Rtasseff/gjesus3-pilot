"""Source summarization + embedded-metadata extraction for microscopy.

`summarize_source` mirrors `dicom_utils.summarize_source` and is wired
into `config.FORMAT_SUMMARIZERS` (file inventory: counts and sizes).

`extract_embedded` produces the per-case `discovered.czi_*` subset and
the structured `microscopy:` sidecar section. It dispatches on file
extension; today only `.czi` is implemented (delegating to
`czi_metadata.extract`). Wired into `config.FORMAT_EMBEDDED_EXTRACTORS`.
"""

import os

from . import czi_metadata


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
            "total_size_mb": round(size / 1_000_000, 1),
            "modality": "",
            "study_date": "",
            "primary_extension": ext,
            "primary_filename": os.path.basename(source_path),
        }

    # Folder mode: locate the single primary file inside.
    primary = None
    extra_files = []
    total_size = 0
    primary_count = 0
    for root, _dirs, files in os.walk(source_path):
        for fname in files:
            fpath = os.path.join(root, fname)
            total_size += os.path.getsize(fpath)
            ext = os.path.splitext(fname)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                primary_count += 1
                if primary is None:
                    primary = fpath
                else:
                    extra_files.append(fpath)

    return {
        "file_count": primary_count,
        "total_size_mb": round(total_size / 1_000_000, 1),
        "modality": "",
        "study_date": "",
        "primary_extension": (
            os.path.splitext(primary)[1].lower() if primary else ""
        ),
        "primary_filename": os.path.basename(primary) if primary else "",
        "extra_microscopy_files": extra_files,
    }


def extract_embedded(source_path):
    """Extract embedded metadata from a microscopy source file.

    Returns (discovered_subset, ecosystem_section_dict). For .czi files,
    delegates to czi_metadata.extract. For .tif/.tiff (not yet
    supported), returns ({}, {}). For unrecognized extensions, also
    ({}, {}).

    Per-format extractors should never raise on simple "no metadata
    found" — only on real errors (file unreadable, library missing).
    Callers can decide whether to swallow exceptions per case.
    """
    ext = os.path.splitext(source_path)[1].lower()
    if ext == ".czi":
        return czi_metadata.extract(source_path)
    return {}, {}
