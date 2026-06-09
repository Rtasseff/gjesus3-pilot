"""Read and append to registry_raw.csv."""

import csv
import os


# Field order must match 06_REGISTRIES.md schema. The `ingest_config`
# column records the YAML config that produced each row (relative path
# from repo root) for auditability and reproducibility.
#
# `session_id` and `primary_kind` are DRAFT additions 2026-05-20 (round
# 6 / ISA terminology + per-ecosystem primary-entity shape — see
# 06_REGISTRIES.md §2.3a). When this list changes, the defensive header
# check in append_row() refuses to write until the existing CSV is
# migrated to match (tools/migrate_registry_columns.py).
REGISTRY_FIELDS = [
    "acq_id",
    "registration_datetime",
    "acquisition_datetime",
    "data_ecosystem",
    "instrument",
    "instrument_model",
    "modalities_in_study",
    "researcher",        # RENAMED from "operator" 2026-06-09 — the person who
                         # set up / ran the study. "user" = software only.
    "operator",          # ADDED BACK 2026-06-09 (REG-decision #4.2) — the person
                         # who RAN the equipment for the acquisition. Recorded for
                         # EVERY study (~half the time == researcher) so operators
                         # can find their own scans in the registry without opening
                         # sidecars. Populated from the top-level `operator:` config
                         # key (NOT the registry: block) — same value also written
                         # to the metadata_sidecar. See 06_REGISTRIES §2.3a.
    "data_source",
    "sample_id",
    "sample_type",
    "session_id",        # DRAFT 2026-05-20
    "primary_kind",      # DRAFT 2026-05-20
    "primary_file_name",
    "original_name",
    "file_format",
    "file_size_mb",
    "file_count",
    "canonical_path",
    "checksum_present",
    "extended_metadata_present",
    "project_hint",
    "ingest_config",
    "notes",
]


def read_registry(registry_path):
    """Read registry CSV and return list of row dicts.

    Returns empty list if file doesn't exist.
    """
    if not os.path.exists(registry_path):
        return []
    # Tolerant decode: prefer UTF-8 (what append_row writes — so accented
    # operator/notes values round-trip correctly), but fall back to latin-1
    # (which never raises) for legacy files written with a cp1252 console
    # (e.g. registry_projects.csv produced by create_project). A fixed UTF-8
    # read would crash on those; the platform-default read would mojibake the
    # UTF-8 ones — the fallback chain reads both correctly.
    for enc in ("utf-8-sig", "latin-1"):
        try:
            with open(registry_path, "r", encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    return []


def append_row(registry_path, row_dict):
    """Append a single row to the registry CSV.

    Creates the directory and file with headers if they don't exist.

    Raises RuntimeError if the existing file's header doesn't match
    REGISTRY_FIELDS — silently writing N+1 values into an N-column file
    corrupts every subsequent read (values shift into the wrong columns).
    When this fires, run the migration: rewrite the CSV with the new
    header and pad/reorder existing rows.
    """
    os.makedirs(os.path.dirname(registry_path), exist_ok=True)
    file_exists = os.path.exists(registry_path)

    if file_exists:
        with open(registry_path, "r", encoding="utf-8", newline="") as f:
            existing = next(csv.reader(f), [])
        if existing != REGISTRY_FIELDS:
            raise RuntimeError(
                f"registry header mismatch in {registry_path}\n"
                f"  file has {len(existing)} columns: {existing}\n"
                f"  code expects {len(REGISTRY_FIELDS)}: {REGISTRY_FIELDS}\n"
                f"  refusing to append (would corrupt column alignment). "
                f"Migrate the CSV before re-running."
            )

    # Ensure all fields present (fill missing with empty string)
    row = {field: row_dict.get(field, "") for field in REGISTRY_FIELDS}

    with open(registry_path, "a", encoding="utf-8", newline="") as f:
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
    # User-controlled values come from cfg (already resolved from the
    # YAML registry: block by config.expand_batch / config.prep_single_case).
    # acquisition_datetime is normalized to ISO at resolve time.
    instrument = cfg.get("instrument", "")
    data_ecosystem = cfg.get("data_ecosystem", "")
    primary_file = cfg.get("primary_file_name", "series/")
    file_format = cfg.get("file_format", ".dcm")

    # `modalities_in_study` is unique among user-controllable columns: if
    # the user left it empty/NA, fall back to whatever the source
    # summarizer detected (e.g. DICOM Modality tag). Explicit user values
    # always win.
    modalities = cfg.get("modalities_in_study", "") or summary.get("modality", "") or ""

    return {
        "acq_id": acq_id,
        "registration_datetime": registration_dt,
        "acquisition_datetime": cfg.get("acquisition_datetime", ""),
        "data_ecosystem": data_ecosystem,
        "instrument": instrument,
        "instrument_model": cfg.get("instrument_model", ""),
        "modalities_in_study": modalities,
        "researcher": cfg.get("researcher", ""),
        "operator": cfg.get("operator", ""),   # top-level operator: -> column + sidecar
        "data_source": cfg.get("data_source", ""),
        "sample_id": cfg.get("sample_id", ""),
        "sample_type": cfg.get("sample_type", ""),
        "session_id": cfg.get("session_id", ""),
        "primary_kind": cfg.get("primary_kind", ""),
        "primary_file_name": primary_file,
        "original_name": cfg.get("original_name", ""),
        "file_format": file_format,
        "file_size_mb": summary.get("total_size_mb", 0),
        "file_count": summary.get("file_count", 0),
        "canonical_path": dest_path,
        "checksum_present": "Y",
        "extended_metadata_present": cfg.get("extended_metadata_present", "N"),
        "project_hint": cfg.get("project_hint", ""),
        "ingest_config": cfg.get("ingest_config", ""),
        "notes": cfg.get("notes", ""),
    }
