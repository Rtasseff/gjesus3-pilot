"""Read and append to registry_raw.csv."""

import csv
import os

# Field order must match 06_REGISTRIES.md schema (with original_name added)
REGISTRY_FIELDS = [
    "acq_id",
    "registration_datetime",
    "acquisition_datetime",
    "data_ecosystem",
    "instrument",
    "instrument_model",
    "modalities_in_study",
    "operator",
    "data_source",
    "sample_id",
    "sample_type",
    "primary_file_name",
    "original_name",
    "file_format",
    "file_size_mb",
    "file_count",
    "canonical_path",
    "checksum_present",
    "extended_metadata_present",
    "project_hint",
    "notes",
]


def read_registry(registry_path):
    """Read registry CSV and return list of row dicts.

    Returns empty list if file doesn't exist.
    """
    if not os.path.exists(registry_path):
        return []
    with open(registry_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def append_row(registry_path, row_dict):
    """Append a single row to the registry CSV.

    Creates the directory and file with headers if they don't exist.
    """
    os.makedirs(os.path.dirname(registry_path), exist_ok=True)
    file_exists = os.path.exists(registry_path)

    # Ensure all fields present (fill missing with empty string)
    row = {field: row_dict.get(field, "") for field in REGISTRY_FIELDS}

    with open(registry_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REGISTRY_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def build_row(acq_id, cfg, summary, dest_path, registration_dt):
    """Build a registry row dict from config and analysis results.

    Args:
        acq_id: The generated ACQ-ID.
        cfg: Single-case config dict.
        summary: Source summary dict from dicom_utils.summarize_source.
        dest_path: Canonical path to the acquisition folder.
        registration_dt: ISO datetime string for registration_datetime.

    Returns:
        Dict with all REGISTRY_FIELDS populated.
    """
    # Determine acquisition_datetime from DICOM StudyDate
    acq_dt = ""
    study_date = summary.get("study_date")
    if study_date and len(study_date) == 8:
        acq_dt = (
            f"{study_date[:4]}-{study_date[4:6]}-{study_date[6:8]}"
            f"T00:00:00Z"
        )

    instrument = cfg.get("instrument", "")
    data_ecosystem = cfg.get("data_ecosystem", "")

    # For DICOM data, primary file is series/
    primary_file = cfg.get("primary_file_name", "series/")
    file_format = cfg.get("file_format", ".dcm")

    return {
        "acq_id": acq_id,
        "registration_datetime": registration_dt,
        "acquisition_datetime": acq_dt,
        "data_ecosystem": data_ecosystem,
        "instrument": instrument,
        "instrument_model": cfg.get("instrument_model", ""),
        "modalities_in_study": summary.get("modality", ""),
        "operator": cfg.get("operator", ""),
        "data_source": cfg.get("data_source", ""),
        "sample_id": cfg.get("sample_id", ""),
        "sample_type": cfg.get("sample_type", ""),
        "primary_file_name": primary_file,
        "original_name": cfg.get("original_name", ""),
        "file_format": file_format,
        "file_size_mb": summary.get("total_size_mb", 0),
        "file_count": summary.get("file_count", 0),
        "canonical_path": dest_path,
        "checksum_present": "Y",
        "extended_metadata_present": "N",
        "project_hint": cfg.get("project_hint", ""),
        "notes": cfg.get("notes", ""),
    }
