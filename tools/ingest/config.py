"""Configuration loading and validation for ingest_raw."""

import os
import glob as globmod
from pathlib import Path

import yaml


# Valid instrument codes (internal + collaborator X-prefix)
VALID_INSTRUMENTS = {
    # Internal
    "ZWSI", "CELL", "LSM9", "PET", "SPECT", "CT", "MRI",
    # Collaborator / external (X-prefix)
    "XMRI", "XCT", "XPET", "XSPECT",
}

# Map instrument code → data ecosystem
INSTRUMENT_ECOSYSTEM = {
    "ZWSI": "MICROSCOPY",
    "CELL": "MICROSCOPY",
    "LSM9": "MICROSCOPY",
    "PET": "DICOM",
    "SPECT": "DICOM",
    "CT": "DICOM",
    "MRI": "DICOM",
    "XMRI": "DICOM",
    "XCT": "DICOM",
    "XPET": "DICOM",
    "XSPECT": "DICOM",
}

# Map DICOM Modality tag values → our X-prefix codes
DICOM_MODALITY_TO_CODE = {
    "MR": "XMRI",
    "CT": "XCT",
    "PT": "XPET",
    "NM": "XSPECT",
    "ST": "XSPECT",
}

REQUIRED_SINGLE_FIELDS = [
    "source_path",
    "operator",
]


def load_config(config_path):
    """Load and return parsed YAML config."""
    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)
    if cfg is None:
        raise ValueError(f"Empty config file: {config_path}")
    return cfg


def is_batch_config(cfg):
    """Return True if config uses batch auto_discover mode."""
    return "auto_discover" in cfg


def expand_batch(cfg):
    """Expand a batch config into a list of single-case configs.

    Each returned dict has the same shape as a single-case config,
    with defaults merged in and source_path resolved.
    """
    defaults = dict(cfg.get("defaults", {}))
    disco = cfg["auto_discover"]
    staging_dir = disco["staging_dir"]
    pattern = disco.get("pattern", "*/")
    sample_id_from = disco.get("sample_id_from", "folder_name")

    # Discover cases
    search = os.path.join(staging_dir, pattern)
    matches = sorted(globmod.glob(search))
    # Keep only directories
    matches = [m for m in matches if os.path.isdir(m)]

    if not matches:
        raise ValueError(
            f"No directories found matching {search}"
        )

    cases = []
    for match_path in matches:
        case = dict(defaults)
        case["source_path"] = match_path
        folder_name = Path(match_path).name
        if sample_id_from == "folder_name":
            case.setdefault("sample_id", folder_name)
        case.setdefault("original_name", folder_name)
        cases.append(case)

    return cases


def validate_single(cfg):
    """Validate a single-case config dict. Returns list of errors."""
    errors = []
    for field in REQUIRED_SINGLE_FIELDS:
        if not cfg.get(field):
            errors.append(f"Missing required field: {field}")

    src = cfg.get("source_path", "")
    if src and not os.path.exists(src):
        errors.append(f"source_path does not exist: {src}")

    inst = cfg.get("instrument", "")
    if inst and inst != "auto" and inst not in VALID_INSTRUMENTS:
        errors.append(
            f"Unknown instrument code: {inst}. "
            f"Valid: {sorted(VALID_INSTRUMENTS)}"
        )

    return errors


def resolve_ecosystem(instrument):
    """Return the data ecosystem for an instrument code."""
    eco = INSTRUMENT_ECOSYSTEM.get(instrument)
    if eco is None:
        raise ValueError(f"No ecosystem mapping for instrument: {instrument}")
    return eco
