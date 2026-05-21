"""Configuration loading and validation for ingest_raw."""

import os
import re
import glob as globmod
from pathlib import Path

import yaml

from . import (
    dicom_utils,
    microscopy_utils,
    filename_parser,
    paravision_metadata,
    registry,
    resolver,
)


# Maps a data_ecosystem to the summarize_source(path) -> dict callable
# that inventories files for that ecosystem. Each summarizer must return
# at least: file_count, total_size_mb, modality, study_date.
FORMAT_SUMMARIZERS = {
    "DICOM":      dicom_utils.summarize_source,
    "MICROSCOPY": microscopy_utils.summarize_source,
}


def _is_paravision_exam(path):
    """Heuristic: does this folder look like a Bruker ParaVision exam?

    A ParaVision examination folder has `acqp` AND `method` files at its
    root. (Collaborator XMRI zips, by contrast, never have these.) We
    don't require `visu_pars` because some exams may not have it yet.
    """
    p = Path(path)
    return p.is_dir() and (p / "acqp").is_file() and (p / "method").is_file()


def _extract_dicom_embedded(path):
    """Embedded-metadata dispatcher for the DICOM ecosystem.

    Detects ParaVision exam folders by content and dispatches to
    `paravision_metadata.extract`. For everything else under DICOM
    (collaborator XMRI zips, future PET/SPECT/CT), returns empty —
    pure-DICOM-header extraction is queued as deferred work.
    """
    if _is_paravision_exam(path):
        return paravision_metadata.extract(path)
    return ({}, {})


# Maps a data_ecosystem to an embedded-metadata extractor. Each must
# return (discovered_subset_dict, ecosystem_section_dict). DICOM
# dispatches by content — see `_extract_dicom_embedded`.
FORMAT_EMBEDDED_EXTRACTORS = {
    "MICROSCOPY": microscopy_utils.extract_embedded,
    "DICOM":      _extract_dicom_embedded,
}


def get_summarizer(ecosystem):
    """Return the summarize_source callable for an ecosystem, or None."""
    return FORMAT_SUMMARIZERS.get(ecosystem)


def get_embedded_extractor(ecosystem):
    """Return the extract_embedded callable for an ecosystem, or None."""
    return FORMAT_EMBEDDED_EXTRACTORS.get(ecosystem)


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
        auto_create_projects: true             # see ingest_raw.py auto-create site
        archive_format: zip                    # DICOM only (planned)

      auto_discover:
        staging_dir: <dir>
        pattern: <glob>                        # "*/" (dirs) or "*.czi" (files);
                                               # "**/*.czi" for recursive (path_parse)
        filename_parse:                        # file mode; positional split
          separator: "_"
          fields: [group_code, operator, sample_id, ...]
        path_parse:                            # OPTIONAL; names path levels
          levels: [researcher, cell_line, experiment]
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

      auto_create_project:                     # OPTIONAL; first-write-wins
        owner:       "${discovered.researcher}"
        description: "..."
        notes:       "..."

    Per case, expand_batch builds case["discovered"] (path_parse +
    filename-parser output + parent-folder date + folder_name/filename,
    in that order — filename chunks override path levels on name
    collision), then resolves cfg["registry"] against it and promotes
    the result to flat top-level keys on the case dict. The raw
    auto_create_project: block is stashed on the case for later
    resolution at the auto-create site in ingest_raw.py.
    """
    disco = cfg["auto_discover"]
    staging_dir = disco["staging_dir"]
    pattern = disco.get("pattern", "*/")

    parse_cfg = disco.get("filename_parse") or {}
    parse_sep = parse_cfg.get("separator", "_")
    parse_fields = parse_cfg.get("fields") or []
    parse_regex = parse_cfg.get("regex") or ""
    # `source: name` (default — match basename) | `source: parent_name`
    # (parent folder of the match — useful when the meaningful name is
    # one level up, as for Bruker ParaVision exam folders).
    parse_source = parse_cfg.get("source", "name")

    # path_parse: free-form named levels between staging_dir and the file.
    # Each level becomes a discovered.<name>. Requires a recursive glob
    # ("**/...") on `pattern` for any non-trivial hierarchy.
    path_parse_cfg = disco.get("path_parse") or {}
    path_levels = path_parse_cfg.get("levels") or []

    filter_cfg = disco.get("filter") or {}
    date_from = disco.get("acquisition_date_from", "")
    embed_metadata = disco.get("embedded_metadata", True)
    # Resolve which ecosystem we're in so we know which embedded
    # extractor to use. If `registry.data_ecosystem` references a
    # discovered field (unusual), the lookup falls back to nothing —
    # ecosystem-specific extraction simply won't run.
    eco_for_extract = (cfg.get("registry") or {}).get("data_ecosystem", "")

    registry_block = cfg.get("registry")
    block_errors = resolver.validate_registry_block(registry_block)
    if block_errors:
        raise ValueError(
            "Invalid registry: block:\n  - " + "\n  - ".join(block_errors)
        )

    acp_block = cfg.get("auto_create_project")
    acp_errors = resolver.validate_auto_create_project_block(acp_block)
    if acp_errors:
        raise ValueError(
            "Invalid auto_create_project: block:\n  - " + "\n  - ".join(acp_errors)
        )

    # Build idempotency index from existing registry (if known)
    registry_path = (
        os.path.join(nas_root, "registries", "registry_raw.csv")
        if nas_root else None
    )
    existing_keys = _build_dedupe_index(registry_path)

    # Discover cases (allow both files and directories).
    # recursive=True is harmless for non-"**" patterns and enables
    # recursive discovery when path_parse expects multiple folder levels.
    search = os.path.join(staging_dir, pattern)
    matches = sorted(globmod.glob(search, recursive=True))
    if not matches:
        raise ValueError(f"No matches for {search}")

    cases = []
    for match_path in matches:
        is_dir = os.path.isdir(match_path)
        is_file = os.path.isfile(match_path)
        if not (is_dir or is_file):
            continue

        match_basename = Path(match_path).name
        # Carry the top-level ingest: and auto_create_project: blocks into
        # each case so ingest_single can read control flags and supply
        # project-creation metadata on first-time auto-create.
        case = {
            "source_path": match_path,
            "ingest": cfg.get("ingest") or {},
            "auto_create_project": acp_block,
        }
        discovered = {}

        # path_parse: split the path components between staging_dir and
        # the file (or directory) basename into the named levels.
        if path_levels:
            rel_path = os.path.relpath(match_path, staging_dir)
            rel_parts = list(Path(rel_path).parts)
            # Strip the basename (the matched file/dir itself) so what
            # remains is the levels between staging_dir and the match.
            path_parts = rel_parts[:-1] if rel_parts else []
            if len(path_parts) != len(path_levels):
                print(
                    f"[expand_batch] SKIP {match_basename}: path_parse expects "
                    f"{len(path_levels)} level(s) {path_levels}, got "
                    f"{len(path_parts)} {path_parts}"
                )
                continue
            for level_name, component in zip(path_levels, path_parts):
                discovered[level_name] = component

        case["original_name"] = match_basename
        if is_file:
            discovered["filename"] = match_basename
        else:
            discovered["folder_name"] = match_basename

        # Pick the source for filename_parse / regex_extract. `name`
        # uses the match basename (file or folder); `parent_name` uses
        # the parent folder name (useful when the meaningful name is
        # one level up — e.g. Bruker ParaVision exams where the JRC ID
        # is in the study folder name).
        if parse_source == "parent_name":
            parse_target = Path(match_path).parent.name
        else:
            parse_target = match_basename

        # Run filename_parse (positional and/or regex) on parse_target.
        # Both flavours produce a {field: value} dict; results are
        # merged with regex first, then positional (positional wins on
        # collision, since that's the historical behaviour).
        if parse_fields or parse_regex:
            parsed = {}
            if parse_regex:
                try:
                    parsed.update(filename_parser.parse_regex(
                        parse_target, parse_regex,
                    ))
                except filename_parser.FilenameParseError as e:
                    print(f"[expand_batch] SKIP {match_basename}: {e}")
                    continue
            if parse_fields:
                try:
                    parsed.update(filename_parser.parse(
                        parse_target, parse_sep, parse_fields,
                    ))
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
            # Cross-check: WARN when path_parse and filename_parse
            # produce DIFFERENT values for the same discovered key.
            # filename still wins on collision (documented behaviour
            # — see 10_TOOLS §2.1.3), but a mismatch is a useful
            # misfiled-file signal worth surfacing. Same-value
            # collisions are silent (redundant but harmless).
            for k, fname_v in parsed.items():
                if k in path_levels:
                    path_v = discovered.get(k)
                    if path_v != fname_v:
                        print(
                            f"[expand_batch] WARN {match_basename}: "
                            f"path_parse and filename_parse disagree on "
                            f"'{k}': path={path_v!r}, filename={fname_v!r}. "
                            f"Using filename value (documented behaviour); "
                            f"confirm this file isn't misfiled."
                        )
            # filename_parse runs AFTER path_parse; on name collision
            # the filename chunk wins (it's typically the more
            # specific value). Operators who want to distinguish
            # should give the two sides different names.
            discovered.update(parsed)

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

        # Embedded-metadata extraction. Runs at expand_batch time so
        # that discovered.<eco>_* references in the registry: block
        # resolve cleanly. Opt-out per config. Works for both file
        # matches (e.g. .czi → discovered.czi_*) and folder matches
        # (e.g. Bruker ParaVision exam → discovered.mri_*); each
        # ecosystem's extractor decides what it accepts.
        eco_section = {}
        if embed_metadata and (is_file or is_dir):
            extractor = get_embedded_extractor(eco_for_extract)
            if extractor:
                try:
                    eco_disc, eco_section = extractor(match_path)
                except Exception as e:
                    print(
                        f"[expand_batch] WARN: embedded extraction failed "
                        f"for {match_basename}: {e}"
                    )
                    eco_disc, eco_section = {}, {}
                # Merge without overwriting earlier discovered values.
                for k, v in (eco_disc or {}).items():
                    if k not in discovered or not discovered[k]:
                        discovered[k] = v

        case["discovered"] = discovered
        case["ecosystem_section"] = eco_section

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
    acp_errors = resolver.validate_auto_create_project_block(
        cfg.get("auto_create_project")
    )
    if acp_errors:
        raise ValueError(
            "Invalid auto_create_project: block:\n  - " + "\n  - ".join(acp_errors)
        )
    cfg.setdefault("discovered", {})
    src = cfg.get("source_path", "")
    if src:
        cfg.setdefault("original_name", Path(src).name)

    # Single-case embedded extraction (parallels expand_batch's logic).
    # Accepts both file and folder source_paths so that ecosystem
    # extractors that work on folders (e.g. ParaVision exam folders)
    # are reachable here too.
    eco_section = {}
    embed = (cfg.get("auto_discover") or {}).get("embedded_metadata", True)
    eco = (registry_block or {}).get("data_ecosystem", "")
    if embed and src and os.path.exists(src):
        extractor = get_embedded_extractor(eco)
        if extractor:
            try:
                eco_disc, eco_section = extractor(src)
                for k, v in (eco_disc or {}).items():
                    if k not in cfg["discovered"] or not cfg["discovered"][k]:
                        cfg["discovered"][k] = v
            except Exception as e:
                print(f"[prep_single_case] WARN: embedded extraction failed: {e}")
    cfg["ecosystem_section"] = eco_section

    apply_registry_block(cfg, registry_block)
    return cfg


def resolve_ecosystem(instrument):
    """Return the data ecosystem for an instrument code."""
    eco = INSTRUMENT_ECOSYSTEM.get(instrument)
    if eco is None:
        raise ValueError(f"No ecosystem mapping for instrument: {instrument}")
    return eco
