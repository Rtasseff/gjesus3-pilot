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
    ni_metadata,
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

    Detects source shape by content and dispatches to the right
    extractor:
      - Bruker ParaVision exam folder (`acqp` + `method` present) →
        `paravision_metadata.extract` → section name "mri".
      - Molecubes NI acquisition folder (`protocol.txt` + `recon_<idx>/`
        present) → `ni_metadata.extract` → section name "ni".
      - Everything else under DICOM (collaborator XMRI zips, future
        general DICOM) → empty; pure-DICOM-header extraction is queued
        as deferred work.

    Returns either a 2-tuple `(discovered, section_dict)` or a 3-tuple
    `(discovered, section_dict, section_name)`. The 3-tuple form lets
    the dispatcher override the sidecar section name when the contents
    are platform-specific rather than generic DICOM headers (a
    `metadata.json.dicom` block is reserved for the eventual
    pure-DICOM-header extractor).
    """
    if _is_paravision_exam(path):
        # paravision_metadata.extract returns a 3-tuple
        # (discovered, mri_section, "mri") so the dispatcher can pass
        # it straight through. The optional `reconstructions=` arg is
        # NOT passed here — full per-DICOM header read happens at
        # expand_batch time; copy-time recon selection still gates which
        # files actually land on disk.
        return paravision_metadata.extract(path)
    if ni_metadata.is_ni_acquisition(path):
        return ni_metadata.extract(path)
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

    The dedup key relies on original_name being unique within an
    acquisition date. expand_batch sets original_name to the relative
    path from staging_dir — basename-only for patterns like `*.czi` /
    `*/`, parent-and-basename for `*/*`. The previous "name alone"
    safety fallback was removed (2026-05-27, round-6 v2 MRI redo):
    it caused false-positive dedups when the same exam-number basename
    appeared across acquisition dates (e.g. ParaVision exam `12`
    repeats across animal sessions). With unique original_name, the
    (date, original_name) key is sufficient.
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


def _apply_operator(case, operator_expr):
    """Resolve the SIDECAR-ONLY top-level `operator:` expr and set case["operator"].

    `operator` is the person who RAN the equipment for this acquisition. It is
    distinct from `registry.researcher` (the experiment owner — a registry
    column) and is written to the sidecar only (metadata_sidecar), kept for
    future DB/image-server search. For MRI/NI the two are the same person.
    Lenient: an unresolved ref WARNs and leaves operator "" (non-blocking).
    ("user" is reserved for "a person using the software"; not a role here.)
    """
    if operator_expr is None:
        return
    discovered = case.get("discovered") or {}
    try:
        case["operator"] = resolver.resolve_value(
            operator_expr, discovered, key_for_error="operator")
    except resolver.ResolverError as e:
        print(f"[expand_batch] WARN: operator: {e} -- leaving operator empty.")
        case["operator"] = ""


def _validate_enrichment_blocks(cfg, disco):
    """Validate the Phase 3 enrichment config and return the raw blocks.

    Reads the top-level `subject:` / `condition:` / `anatomy:` blocks and the
    `auto_discover.subject_from_db` flag + `auto_discover.subject_lookup` map.
    Raises ValueError on a structurally invalid config (fail-fast); the field
    VALUES are resolved non-blockingly later by ingest/enrichment.py.

    `disco` is cfg["auto_discover"] (or {} for single-case configs).
    """
    disco = disco or {}
    subject = cfg.get("subject")
    condition = cfg.get("condition")
    anatomy = cfg.get("anatomy")
    subject_from_db = disco.get("subject_from_db")
    subject_lookup = disco.get("subject_lookup")

    errors = []
    errors += resolver.validate_subject_block(subject)
    errors += resolver.validate_condition_block(condition)
    errors += resolver.validate_anatomy_block(anatomy)
    errors += resolver.validate_subject_from_db(subject_from_db)
    errors += resolver.validate_subject_lookup(subject_lookup)
    if errors:
        raise ValueError(
            "Invalid enrichment config:\n  - " + "\n  - ".join(errors)
        )
    return {
        "subject": subject,
        "condition": condition,
        "anatomy": anatomy,
        "subject_from_db": bool(subject_from_db),
        "subject_lookup": subject_lookup or {},
    }


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

    # Phase 3 preclinical enrichment blocks (08_METADATA §4.4–4.7). Validate
    # structure up front (fail-fast on a malformed config); the values
    # themselves resolve non-blockingly at the sidecar-write site. The raw
    # blocks are stashed on each case and consumed by ingest/enrichment.py.
    enrich_block = _validate_enrichment_blocks(cfg, disco)

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
        # project-creation metadata on first-time auto-create. Also
        # capture link_filename: (resolver-evaluated at .lnk creation
        # time — see resolver.resolve_link_filename).
        case = {
            "source_path": match_path,
            "ingest": cfg.get("ingest") or {},
            "auto_create_project": acp_block,
            "link_filename": cfg.get("link_filename") or "",
            # Phase 3 enrichment (raw blocks; resolved per-case at Step 8.5).
            "subject": enrich_block["subject"],
            "condition": enrich_block["condition"],
            "anatomy": enrich_block["anatomy"],
            "subject_from_db": enrich_block["subject_from_db"],
            "subject_lookup": enrich_block["subject_lookup"],
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

        # original_name needs to be unique within the staging_dir so that
        # the (acq_date, original_name) dedup key actually identifies a
        # unique acquisition. Just the match basename isn't enough for
        # patterns like `*/*` where matches come from different parent
        # folders but the basename is the same (e.g. MRI exam numbers
        # `12`, `13`, ... repeat across animal-session study folders,
        # AND can repeat across acquisition dates because Bruker's
        # examination numbering is per-platform-user-account, not
        # per-study). The relpath form is basename-only when pattern is
        # `*.czi` / `*/` (no parent), and `<parent>/<basename>` when
        # pattern is `*/*` (one parent) — so microscopy / NI / XMRI
        # behaviour is unchanged; MRI gets the disambiguator it needs.
        rel_match = os.path.relpath(match_path, staging_dir).replace(os.sep, "/")
        case["original_name"] = rel_match
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
        eco_section_name_override = None
        # Track whether a content-detecting extractor ran but recognised
        # nothing — the signal that this match is a non-primary sibling
        # folder (e.g. ParaVision's AdjResult / subject / ScanProgram dirs
        # that sit beside the numbered exam folders under a `*/*` scan).
        embedded_attempted = False
        embedded_yielded = False
        if embed_metadata and (is_file or is_dir):
            extractor = get_embedded_extractor(eco_for_extract)
            if extractor:
                embedded_attempted = True
                try:
                    result = extractor(match_path)
                except Exception as e:
                    print(
                        f"[expand_batch] WARN: embedded extraction failed "
                        f"for {match_basename}: {e}"
                    )
                    result = ({}, {})
                # Extractors return either a 2-tuple (discovered, section)
                # — section name comes from the ecosystem — or a 3-tuple
                # (discovered, section, name_override) — section name is
                # provided explicitly. The DICOM dispatcher uses the
                # 3-tuple form for ParaVision (override to "mri").
                if len(result) == 3:
                    eco_disc, eco_section, eco_section_name_override = result
                else:
                    eco_disc, eco_section = result
                embedded_yielded = bool(eco_disc) or bool(eco_section)
                # Merge without overwriting earlier discovered values.
                for k, v in (eco_disc or {}).items():
                    if k not in discovered or not discovered[k]:
                        discovered[k] = v

        # subject_parse: split the (messy, hand-typed) subject folder into a
        # project code + its 1-4 animal numbers, reusing the validated live-box
        # grammar (ni_live_discover.parse_subject). Populates discovered.project
        # + discovered.animal_codes (;-joined) so the multi-animal DB lookup and
        # project_hint resolve. The single-animal archive path (no subject_parse
        # block) is untouched.
        sp_cfg = disco.get("subject_parse") or {}
        if sp_cfg:
            import ni_live_discover
            subj_val = discovered.get(sp_cfg.get("field", "subject"), "")
            if subj_val:
                parsed = ni_live_discover.parse_subject(
                    subj_val, discovered.get("series"))
                if parsed.get("project"):
                    discovered.setdefault("project", parsed["project"])
                discovered["animal_codes"] = ";".join(
                    str(a["number"]) for a in parsed["animals"])
                if parsed.get("flags"):
                    discovered["subject_flags"] = ",".join(parsed["flags"])
                if parsed.get("phantom"):
                    discovered["phantom"] = "yes"

        case["discovered"] = discovered
        case["ecosystem_section"] = eco_section
        if eco_section_name_override:
            case["ecosystem_section_name"] = eco_section_name_override

        try:
            apply_registry_block(case, registry_block)
        except resolver.ResolverError as e:
            # A content-detecting extractor (ParaVision / NI) that recognised
            # nothing, whose registry row then can't resolve a scan-only
            # `discovered.<eco>_*` field, is a non-primary sibling folder under
            # a `*/*` scan — benign and expected. Say so plainly instead of
            # leaking the raw resolver error (which reads like a config bug).
            if (embedded_attempted and not embedded_yielded
                    and "is not in discovered fields" in str(e)):
                print(f"[expand_batch] SKIP {match_basename}: not a scan folder "
                      f"(no acquisition metadata; a sibling/housekeeping folder)")
            else:
                print(f"[expand_batch] SKIP {match_basename}: {e}")
            continue
        _apply_operator(case, cfg.get("operator"))

        # Idempotency: skip if already ingested. Key is (acq_date,
        # original_name) where original_name is the relpath set above.
        # No more "name alone" fallback (see _build_dedupe_index for
        # the rationale).
        adt = (case.get("acquisition_datetime") or "")[:10].replace("-", "")
        if (adt, rel_match) in existing_keys:
            print(
                f"[expand_batch] SKIP {rel_match}: "
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
    # Phase 3 enrichment: validate the top-level subject/condition/anatomy
    # blocks and promote the auto_discover lookup config to top-level keys so
    # ingest/enrichment.py finds them uniformly with the batch path.
    enrich_block = _validate_enrichment_blocks(cfg, cfg.get("auto_discover"))
    cfg["subject_from_db"] = enrich_block["subject_from_db"]
    cfg["subject_lookup"] = enrich_block["subject_lookup"]
    cfg.setdefault("discovered", {})
    src = cfg.get("source_path", "")
    if src:
        cfg.setdefault("original_name", Path(src).name)

    # Single-case embedded extraction (parallels expand_batch's logic).
    # Accepts both file and folder source_paths so that ecosystem
    # extractors that work on folders (e.g. ParaVision exam folders)
    # are reachable here too. Honours the 3-tuple section-name
    # override (see expand_batch).
    eco_section = {}
    eco_section_name_override = None
    embed = (cfg.get("auto_discover") or {}).get("embedded_metadata", True)
    eco = (registry_block or {}).get("data_ecosystem", "")
    if embed and src and os.path.exists(src):
        extractor = get_embedded_extractor(eco)
        if extractor:
            try:
                result = extractor(src)
                if len(result) == 3:
                    eco_disc, eco_section, eco_section_name_override = result
                else:
                    eco_disc, eco_section = result
                for k, v in (eco_disc or {}).items():
                    if k not in cfg["discovered"] or not cfg["discovered"][k]:
                        cfg["discovered"][k] = v
            except Exception as e:
                print(f"[prep_single_case] WARN: embedded extraction failed: {e}")
    cfg["ecosystem_section"] = eco_section
    if eco_section_name_override:
        cfg["ecosystem_section_name"] = eco_section_name_override

    apply_registry_block(cfg, registry_block)
    _apply_operator(cfg, cfg.get("operator"))
    return cfg


def resolve_ecosystem(instrument):
    """Return the data ecosystem for an instrument code."""
    eco = INSTRUMENT_ECOSYSTEM.get(instrument)
    if eco is None:
        raise ValueError(f"No ecosystem mapping for instrument: {instrument}")
    return eco
