"""Configuration loading and validation for ingest_raw."""

import os
import re
import glob as globmod
from pathlib import Path

import yaml

from . import dicom_utils, microscopy_utils, filename_parser, registry, resolver


# Maps a data_ecosystem to the summarize_source(path) -> dict callable
# that inventories files for that ecosystem. Each summarizer must return
# at least: file_count, total_size_mb, modality, study_date.
FORMAT_SUMMARIZERS = {
    "DICOM":      dicom_utils.summarize_source,
    "MICROSCOPY": microscopy_utils.summarize_source,
}


def get_summarizer(ecosystem):
    """Return the summarize_source callable for an ecosystem, or None."""
    return FORMAT_SUMMARIZERS.get(ecosystem)


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
]


def load_config(config_path):
    """Load and return parsed YAML config."""
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if cfg is None:
        raise ValueError(f"Empty config file: {config_path}")
    return cfg


def is_batch_config(cfg):
    """Return True if config uses batch auto_discover mode."""
    return "auto_discover" in cfg


_DATE_YYYYMMDD = re.compile(r"(?P<y>\d{4})(?P<m>\d{2})(?P<d>\d{2})")
_DATE_DDMMYYYY = re.compile(r"(?P<d>\d{2})(?P<m>\d{2})(?P<y>\d{4})")


def _extract_date_from_name(name):
    """Pull a YYYYMMDD-formatted date out of a folder name. Returns None on no match.

    Tries YYYYMMDD first, then DDMMYYYY (an older convention noted in the
    AxioScan workflow doc).
    """
    m = _DATE_YYYYMMDD.search(name)
    if m and 1900 < int(m.group("y")) < 2100 and 1 <= int(m.group("m")) <= 12 and 1 <= int(m.group("d")) <= 31:
        return f"{m.group('y')}{m.group('m')}{m.group('d')}"
    m = _DATE_DDMMYYYY.search(name)
    if m and 1900 < int(m.group("y")) < 2100 and 1 <= int(m.group("m")) <= 12 and 1 <= int(m.group("d")) <= 31:
        return f"{m.group('y')}{m.group('m')}{m.group('d')}"
    return None


def _build_dedupe_index(registry_path):
    """Build a set of (acq_date, original_name) keys from registry_raw.csv.

    Skipped if the registry doesn't exist yet. Uses date prefix from
    acquisition_datetime (YYYYMMDD), and falls back to "" when missing.
    Empty-string original_name rows are skipped (legacy data).
    """
    rows = registry.read_registry(registry_path) if registry_path else []
    keys = set()
    for r in rows:
        oname = (r.get("original_name") or "").strip()
        if not oname:
            continue
        adt = (r.get("acquisition_datetime") or "").strip()
        date_key = adt[:10].replace("-", "") if adt else ""
        keys.add((date_key, oname))
        keys.add(("", oname))  # also match by name alone for safety
    return keys


def apply_registry_block(case, registry_block):
    """Resolve cfg["registry"] against case["discovered"] and merge into case top-level.

    After this, the per-case dict has its registry-controlled values
    (instrument, operator, sample_id, ...) as flat top-level keys, ready
    for the rest of the pipeline.
    """
    discovered = case.get("discovered") or {}
    resolved = resolver.resolve_registry_block(registry_block, discovered)
    if "acquisition_datetime" in resolved:
        resolved["acquisition_datetime"] = resolver.normalize_acquisition_datetime(
            resolved["acquisition_datetime"]
        )
    case["registry_resolved"] = resolved
    # Promote resolved values to top-level cfg keys (only if not already
    # set — handles e.g. interactive mode where keys may be pre-populated).
    for k, v in resolved.items():
        case.setdefault(k, v)


def expand_batch(cfg, nas_root=None):
    """Expand a batch config into a list of validated, registry-resolved cases.

    Schema:

      ingest:
        delete_source_after_ingest: false      # control flags
        archive_format: zip                    # DICOM only (planned)

      auto_discover:
        staging_dir: <dir>
        pattern: <glob>                        # "*/" (dirs) or "*.czi" (files)
        filename_parse:                        # file mode only
          separator: "_"
          fields: [group_code, operator, sample_id, ...]
        filter:                                # file mode; on parsed values
          group_code: MFB
        acquisition_date_from: parent_folder_name

      registry:                                # explicit per-column mapping
        instrument:           ZWSI
        data_ecosystem:       MICROSCOPY
        operator:             discovered.operator
        data_source:          internal
        sample_id:            discovered.sample_id
        acquisition_datetime: discovered.acquisition_date
        notes:                "Slide ${discovered.stain} @ ${discovered.magnification}"

    Per case, expand_batch builds case["discovered"] (filename-parser
    output + parent-folder date + folder_name/filename), then resolves
    cfg["registry"] against it and promotes the result to flat top-level
    keys on the case dict.
    """
    disco = cfg["auto_discover"]
    staging_dir = disco["staging_dir"]
    pattern = disco.get("pattern", "*/")

    parse_cfg = disco.get("filename_parse") or {}
    parse_sep = parse_cfg.get("separator", "_")
    parse_fields = parse_cfg.get("fields") or []

    filter_cfg = disco.get("filter") or {}
    date_from = disco.get("acquisition_date_from", "")

    registry_block = cfg.get("registry")
    block_errors = resolver.validate_registry_block(registry_block)
    if block_errors:
        raise ValueError(
            "Invalid registry: block:\n  - " + "\n  - ".join(block_errors)
        )

    # Build idempotency index from existing registry (if known)
    registry_path = (
        os.path.join(nas_root, "registries", "registry_raw.csv")
        if nas_root else None
    )
    existing_keys = _build_dedupe_index(registry_path)

    # Discover cases (allow both files and directories).
    search = os.path.join(staging_dir, pattern)
    matches = sorted(globmod.glob(search))
    if not matches:
        raise ValueError(f"No matches for {search}")

    cases = []
    for match_path in matches:
        is_dir = os.path.isdir(match_path)
        is_file = os.path.isfile(match_path)
        if not (is_dir or is_file):
            continue

        match_basename = Path(match_path).name
        case = {"source_path": match_path}
        discovered = {}

        if is_file:
            case["original_name"] = match_basename
            discovered["filename"] = match_basename
            if parse_fields:
                try:
                    parsed = filename_parser.parse(
                        match_basename, parse_sep, parse_fields,
                    )
                except filename_parser.FilenameParseError as e:
                    print(f"[expand_batch] SKIP {match_basename}: {e}")
                    continue
                # filter
                skip = False
                for k, expected in filter_cfg.items():
                    if parsed.get(k) != expected:
                        print(
                            f"[expand_batch] SKIP {match_basename}: "
                            f"filter {k}={expected!r} "
                            f"!= parsed {parsed.get(k)!r}"
                        )
                        skip = True
                        break
                if skip:
                    continue
                discovered.update(parsed)
        else:
            case["original_name"] = match_basename
            discovered["folder_name"] = match_basename

        if date_from == "parent_folder_name":
            parent_name = Path(match_path).parent.name
            date = _extract_date_from_name(parent_name)
            if date:
                discovered["acquisition_date"] = date
            else:
                print(
                    f"[expand_batch] WARN: could not extract date from "
                    f"parent folder '{parent_name}' for {match_basename}"
                )

        case["discovered"] = discovered

        try:
            apply_registry_block(case, registry_block)
        except resolver.ResolverError as e:
            print(f"[expand_batch] SKIP {match_basename}: {e}")
            continue

        # Idempotency: skip if already ingested. Use the resolved
        # acquisition_datetime (date prefix only) if available.
        adt = (case.get("acquisition_datetime") or "")[:10].replace("-", "")
        if (adt, match_basename) in existing_keys or ("", match_basename) in existing_keys:
            print(
                f"[expand_batch] SKIP {match_basename}: "
                f"already in registry (idempotent re-run)"
            )
            continue

        cases.append(case)

    if not cases:
        print(
            f"[expand_batch] No new cases to ingest (matched {len(matches)} paths)."
        )

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


def prep_single_case(cfg):
    """Prepare a single-case (non-batch) config: validate & resolve `registry:`.

    Single-case configs have no auto-discovery; `discovered` is empty so
    every registry: value must be a literal (or NA). Mutates `cfg` in
    place by promoting resolved values to top-level keys.
    """
    registry_block = cfg.get("registry")
    block_errors = resolver.validate_registry_block(registry_block)
    if block_errors:
        raise ValueError(
            "Invalid registry: block:\n  - " + "\n  - ".join(block_errors)
        )
    cfg.setdefault("discovered", {})
    src = cfg.get("source_path", "")
    if src:
        cfg.setdefault("original_name", Path(src).name)
    apply_registry_block(cfg, registry_block)
    return cfg


def resolve_ecosystem(instrument):
    """Return the data ecosystem for an instrument code."""
    eco = INSTRUMENT_ECOSYSTEM.get(instrument)
    if eco is None:
        raise ValueError(f"No ecosystem mapping for instrument: {instrument}")
    return eco
