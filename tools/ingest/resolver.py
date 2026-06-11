"""Resolve YAML `registry:` block values against per-case `discovered` fields.

Three value forms supported in YAML:

    operator:    discovered.operator                  # bare reference
    notes:       "Slide ${discovered.sample_id} (${discovered.stain})"
                                                       # interpolation
    data_source: internal                              # literal
    sample_type: NA                                    # explicit empty

`discovered` is the dict assembled by `auto_discover` per case (filename
parser output + parent-folder-derived date today; embedded-metadata
extractors will add to it in future work).
"""

import re


class ResolverError(ValueError):
    """Raised when a registry value references a discovered field that
    isn't present, or fails validation."""


_BARE_REF_RE = re.compile(r"^\s*discovered\.([A-Za-z_][A-Za-z0-9_]*)\s*$")
_INTERP_RE   = re.compile(r"\$\{discovered\.([A-Za-z_][A-Za-z0-9_]*)\}")


def is_na(value):
    """True for None, empty string, or the case-insensitive sentinel 'NA'."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip().upper() in ("NA", ""):
        return True
    return False


def resolve_value(value, discovered, key_for_error=""):
    """Resolve a single registry-block value.

    Returns the resolved string ("" for NA/missing).
    Raises ResolverError if a referenced discovered field is absent.
    """
    if is_na(value):
        return ""
    if not isinstance(value, str):
        return str(value)  # numbers, bools coerced

    m = _BARE_REF_RE.match(value)
    if m:
        name = m.group(1)
        if name not in discovered:
            raise ResolverError(
                f"registry.{key_for_error}: discovered.{name} is not in "
                f"discovered fields {sorted(discovered.keys())}"
            )
        return str(discovered[name])

    def _interp(match):
        name = match.group(1)
        if name not in discovered:
            raise ResolverError(
                f"registry.{key_for_error}: ${{discovered.{name}}} is not "
                f"in discovered fields {sorted(discovered.keys())}"
            )
        return str(discovered[name])

    return _INTERP_RE.sub(_interp, value)


# Columns the user is allowed to set in the YAML `registry:` block.
USER_CONTROLLABLE_COLUMNS = {
    "acquisition_datetime",
    "data_ecosystem",
    "instrument",
    "instrument_model",
    "modalities_in_study",
    "researcher",    # RENAMED from "operator" 2026-06-09 — experiment owner; the
                     # acquisition operator is the sidecar-only top-level `operator:`
    "data_source",
    "sample_id",
    "sample_type",
    "session_id",    # DRAFT 2026-05-20 — ISA "study" grouping; see 06_REGISTRIES §2.3a
    "project_hint",
    "notes",
}

# Must be present in `registry:` (NA allowed; a missing key is an error).
REQUIRED_REGISTRY_KEYS = {
    "instrument",
    "data_ecosystem",
    "researcher",    # RENAMED from "operator" 2026-06-09
    "data_source",
}

# Auto-populated by the pipeline; user must NOT set them in `registry:`.
AUTO_COLUMNS = {
    "acq_id",
    "registration_datetime",
    "primary_file_name",
    "file_format",
    "file_size_mb",
    "file_count",
    "canonical_path",
    "checksum_present",
    "extended_metadata_present",
    "original_name",
    "ingest_config",
    "subject_id",   # DECIDED 2026-06-11 — auto from the enrichment subject
                    # block (facility_animal_id); never operator-set in registry:
}


def validate_registry_block(registry_block):
    """Return list of validation error strings (empty if OK)."""
    errors = []
    if registry_block is None:
        return ["Missing required `registry:` block in config"]
    if not isinstance(registry_block, dict):
        return [f"`registry:` must be a mapping, got {type(registry_block).__name__}"]

    for k in REQUIRED_REGISTRY_KEYS:
        if k not in registry_block:
            errors.append(
                f"registry: missing required key '{k}' "
                f"(use NA if intentionally blank)"
            )

    for k in registry_block:
        if k in AUTO_COLUMNS:
            errors.append(
                f"registry: '{k}' is auto-populated by the pipeline and "
                f"must not appear in the registry: block"
            )
        elif k not in USER_CONTROLLABLE_COLUMNS:
            errors.append(
                f"registry: '{k}' is not a known column. Allowed: "
                f"{sorted(USER_CONTROLLABLE_COLUMNS)}"
            )

    return errors


def resolve_registry_block(registry_block, discovered):
    """Resolve every key in the registry block. Returns dict column -> value."""
    if not registry_block:
        return {}
    return {
        key: resolve_value(value, discovered, key_for_error=key)
        for key, value in registry_block.items()
    }


# Fields recognized in the optional `auto_create_project:` YAML block.
# These map directly to the project-creation arguments of create_project.
AUTO_CREATE_PROJECT_FIELDS = {"owner", "description", "notes"}


def validate_auto_create_project_block(block):
    """Return list of validation error strings for the auto_create_project: block.

    The block is OPTIONAL — None / missing is fine (returns []). When
    present it must be a mapping, and may only contain keys in
    AUTO_CREATE_PROJECT_FIELDS. See [10_TOOLS §2.1.4] for semantics.
    """
    if block is None:
        return []
    if not isinstance(block, dict):
        return [
            f"`auto_create_project:` must be a mapping, "
            f"got {type(block).__name__}"
        ]
    errors = []
    for k in block:
        if k not in AUTO_CREATE_PROJECT_FIELDS:
            errors.append(
                f"auto_create_project: '{k}' is not a recognized field. "
                f"Allowed: {sorted(AUTO_CREATE_PROJECT_FIELDS)}"
            )
    return errors


# Pattern for the `link_filename:` resolver. Broader than the registry-
# block resolver: matches `${X}` where X can be a flat key (e.g.
# `sample_id`, `acq_date`) or a dotted reference (e.g. `discovered.foo`).
# Allows `-` and `.` in keys so names like `mri_recon_indices` work as well
# as future dotted paths.
_LINK_REF_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_.]*)\}")


def resolve_link_filename(template, cfg_single, acq_id_str, acq_date):
    """Resolve the top-level `link_filename:` YAML field for this case.

    Returns the resolved string, or None if `template` is empty / not set
    (caller falls back to a default like `original_name`).

    The context dict against which `${X}` references are resolved is
    richer than the registry-block resolver. It includes:

      - `discovered.<key>` for every entry in `cfg_single['discovered']`
        (the auto-discovered namespace — filename chunks + embedded
        extractor output like `discovered.mri_exam_number`)
      - Resolved registry fields directly by name: `sample_id`,
        `session_id`, `instrument`, `instrument_model`, `operator`,
        `data_source`, `sample_type`, `acquisition_datetime`,
        `project_hint`, `original_name`, `data_ecosystem`, `notes`
      - `acq_id` — the generated ACQ-ID string for this case
      - `acq_date` — YYYYMMDD form of the acquisition date (already
        computed in ingest_raw.py Step 3)

    Unresolved references log a WARN and are left as a literal `${X}`
    in the output — better than silently producing a half-formed name.
    Resolved-to-empty substitutions go through quietly (operator's
    choice if they reference a key that may be empty).

    No filename-character sanitisation is applied — the documented
    `discovered.*` fields don't contain Windows-unsafe characters in
    practice. Add a sanitisation pass later if a real case requires it.
    """
    if not template or not isinstance(template, str):
        return None

    # Build the flat context dict.
    context = {}
    discovered = cfg_single.get("discovered") or {}
    for k, v in discovered.items():
        context[f"discovered.{k}"] = "" if v is None else str(v)
    for k in (
        "instrument", "instrument_model", "operator", "data_source",
        "sample_id", "sample_type", "session_id", "acquisition_datetime",
        "project_hint", "original_name", "data_ecosystem", "notes",
    ):
        if k in cfg_single:
            v = cfg_single[k]
            if k == "original_name" and v:
                # original_name may carry a staging-relative path (e.g.
                # microscopy nested folders, "Itziar/HLF/Colageno/x.czi");
                # a link name cannot contain path separators, so use the
                # basename. The registry keeps the full original_name — only
                # the link-name context is reduced. Splits on both separators
                # for cross-platform safety.
                context[k] = str(v).replace("\\", "/").rstrip("/").split("/")[-1]
            else:
                context[k] = "" if v is None else str(v)
    context["acq_id"] = acq_id_str or ""
    context["acq_date"] = acq_date or ""

    def _sub(match):
        key = match.group(1)
        if key in context:
            return context[key]
        print(
            f"[resolve_link_filename] WARN: ${{{key}}} not found in "
            f"context (keys: {sorted(context.keys())}); leaving literal."
        )
        return match.group(0)

    return _LINK_REF_RE.sub(_sub, template)


def resolve_auto_create_project_block(block, discovered):
    """Resolve owner/description/notes for first-time project auto-creation.

    Returns dict with all three keys always present (empty string when
    the field was not supplied or resolves to empty). Missing-discovered
    references degrade gracefully to an empty string with a WARN — the
    create-project step proceeds with empty values and the operator can
    fix them by hand in `_project.yaml` later. This is intentional: the
    auto_create_project: block sets initial defaults, not strict
    requirements. Strict naming/ownership is the operator's call.
    """
    out = {key: "" for key in AUTO_CREATE_PROJECT_FIELDS}
    if not block:
        return out
    for key in AUTO_CREATE_PROJECT_FIELDS:
        raw = block.get(key)
        if raw is None:
            continue
        try:
            out[key] = resolve_value(
                raw, discovered, key_for_error=f"auto_create_project.{key}"
            )
        except ResolverError as e:
            print(
                f"[resolve_auto_create_project] WARN: {e} -- "
                f"leaving '{key}' empty; edit _project.yaml after creation."
            )
            out[key] = ""
    return out


# ---- Phase 3 enrichment: condition / anatomy / subject blocks ----------
# These mirror the lenient auto_create_project resolver: structural config
# errors fail fast (the validate_* functions, called at expand_batch /
# prep_single_case time), but missing or empty DATA never raises — the
# non-blocking metadata model (08_METADATA §4.7) writes explicit sentinels
# (null / "" / "unknown") and the orchestrator WARNs instead. The enrichment
# orchestrator (ingest/enrichment.py) adds WARN logging + the animal-DB
# lookup on top of these pure resolvers.

CONDITION_FIELDS = [
    "is_control", "disease_model", "disease_state", "control_type",
    "treatment", "timepoint_days", "study_arm", "source",
]
ANATOMY_FIELDS = ["is_whole_body", "region", "additional_regions", "source", "auto_hint"]
ANATOMY_REGION_FIELDS = {"label", "ontology", "id"}
# Operator-override subject: block (overrides the DB lookup); 06_METADATA §4.4.
SUBJECT_FIELDS = {
    "facility_animal_id", "species", "strain", "sex", "date_of_birth",
    "age_at_acquisition", "genotype", "weight_at_acquisition_g", "cohort_id",
    "procedures", "source",
}
SUBJECT_LOOKUP_FIELDS = {"project_alias", "animal_code"}

_TRUE_STRINGS = {"true", "yes", "1", "y", "t"}
_FALSE_STRINGS = {"false", "no", "0", "n", "f"}


def to_tristate(value):
    """Coerce a YAML value to True | False | None (None = unknown).

    YAML parses bare `true`/`false` to bool already; this also accepts the
    common string spellings and treats anything else (including absence /
    "unknown") as None — the non-blocking default.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in _TRUE_STRINGS:
        return True
    if s in _FALSE_STRINGS:
        return False
    return None


def to_number(value):
    """Coerce to int/float; '' / 'NA' / None / non-numeric -> None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    s = str(value).strip()
    if not s or s.upper() == "NA":
        return None
    try:
        return int(s) if re.fullmatch(r"[+-]?\d+", s) else float(s)
    except ValueError:
        return None


def _resolve_text_lenient(value, discovered, key):
    """Resolve a free-text enrichment field; NA/missing -> ''. Never raises."""
    if is_na(value):
        return ""
    try:
        return resolve_value(value, discovered, key_for_error=key)
    except ResolverError as e:
        print(f"[resolve_enrichment] WARN: {e} -- leaving '{key}' empty.")
        return ""


def _resolve_optional_text(value, discovered, key):
    """Like _resolve_text_lenient but the unsupplied sentinel is None (for
    fields whose 'not set' value is null, e.g. condition.treatment)."""
    if value is None or is_na(value):
        return None
    try:
        return resolve_value(value, discovered, key_for_error=key)
    except ResolverError as e:
        print(f"[resolve_enrichment] WARN: {e} -- leaving '{key}' null.")
        return None


def validate_condition_block(block):
    """Structural validation of the optional top-level `condition:` block."""
    if block is None:
        return []
    if not isinstance(block, dict):
        return [f"`condition:` must be a mapping, got {type(block).__name__}"]
    allowed = set(CONDITION_FIELDS)
    return [
        f"condition: '{k}' is not a recognized field. Allowed: {sorted(allowed)}"
        for k in block if k not in allowed
    ]


def resolve_condition_block(block, discovered):
    """Resolve the `condition:` block to all-keys-present sentinels.

    is_control is tri-state (true/false/null); free-text -> '' (treatment ->
    null); timepoint_days -> number|null. Never raises (08_METADATA §4.7).
    """
    b = block or {}
    return {
        "is_control": to_tristate(b.get("is_control")),
        "disease_model": _resolve_text_lenient(b.get("disease_model"), discovered, "condition.disease_model"),
        "disease_state": _resolve_text_lenient(b.get("disease_state"), discovered, "condition.disease_state"),
        "control_type": _resolve_text_lenient(b.get("control_type"), discovered, "condition.control_type"),
        "treatment": _resolve_optional_text(b.get("treatment"), discovered, "condition.treatment"),
        "timepoint_days": to_number(b.get("timepoint_days")),
        "study_arm": _resolve_text_lenient(b.get("study_arm"), discovered, "condition.study_arm"),
        "source": (_resolve_text_lenient(b.get("source"), discovered, "condition.source")
                   or ("operator-entered" if block else "unknown")),
    }


def validate_anatomy_block(block):
    """Structural validation of the optional top-level `anatomy:` block."""
    if block is None:
        return []
    if not isinstance(block, dict):
        return [f"`anatomy:` must be a mapping, got {type(block).__name__}"]
    errors = [
        f"anatomy: '{k}' is not a recognized field. Allowed: {sorted(ANATOMY_FIELDS)}"
        for k in block if k not in set(ANATOMY_FIELDS)
    ]
    region = block.get("region")
    if "region" in block and region is not None and not isinstance(region, dict):
        errors.append("anatomy.region: must be a mapping (label/ontology/id) or null")
    elif isinstance(region, dict):
        errors += [
            f"anatomy.region: '{rk}' is not recognized. Allowed: {sorted(ANATOMY_REGION_FIELDS)}"
            for rk in region if rk not in ANATOMY_REGION_FIELDS
        ]
    ar = block.get("additional_regions")
    if "additional_regions" in block and ar is not None and not isinstance(ar, list):
        errors.append("anatomy.additional_regions: must be a list")
    return errors


def resolve_anatomy_block(block, discovered):
    """Resolve the `anatomy:` block to all-keys-present sentinels.

    is_whole_body tri-state; region {label,ontology,id} | null (ontology
    defaults to UBERON). Never raises (08_METADATA §4.7).
    """
    b = block or {}
    region_raw = b.get("region")
    if isinstance(region_raw, dict):
        region = {
            "label": _resolve_text_lenient(region_raw.get("label"), discovered, "anatomy.region.label"),
            "ontology": region_raw.get("ontology") or "UBERON",
            "id": _resolve_text_lenient(region_raw.get("id"), discovered, "anatomy.region.id"),
        }
    else:
        region = None
    ar = b.get("additional_regions")
    return {
        "is_whole_body": to_tristate(b.get("is_whole_body")),
        "region": region,
        "additional_regions": ar if isinstance(ar, list) else [],
        "source": (_resolve_text_lenient(b.get("source"), discovered, "anatomy.source")
                   or ("operator-entered" if block else "unknown")),
        "auto_hint": _resolve_text_lenient(b.get("auto_hint"), discovered, "anatomy.auto_hint"),
    }


def validate_subject_block(block):
    """Structural validation of the optional top-level `subject:` operator-
    override block (overrides the animal-DB lookup; 08_METADATA §4.4)."""
    if block is None:
        return []
    if not isinstance(block, dict):
        return [f"`subject:` must be a mapping, got {type(block).__name__}"]
    return [
        f"subject: '{k}' is not a recognized field. Allowed: {sorted(SUBJECT_FIELDS)}"
        for k in block if k not in SUBJECT_FIELDS
    ]


def validate_subject_lookup(block):
    """Structural validation of the optional `auto_discover.subject_lookup:`
    block (how to build the animal-DB key from discovered.* fields)."""
    if block is None:
        return []
    if not isinstance(block, dict):
        return [f"`subject_lookup:` must be a mapping, got {type(block).__name__}"]
    return [
        f"subject_lookup: '{k}' is not a recognized field. Allowed: {sorted(SUBJECT_LOOKUP_FIELDS)}"
        for k in block if k not in SUBJECT_LOOKUP_FIELDS
    ]


def validate_subject_from_db(value):
    """`auto_discover.subject_from_db:` must be a boolean (or absent)."""
    if value is None:
        return []
    if not isinstance(value, bool):
        return [f"`subject_from_db:` must be true/false, got {type(value).__name__}"]
    return []


def normalize_acquisition_datetime(value):
    """Coerce a date-shaped string into ISO. Empty pass-through; ISO pass-through.

    Accepts:
        ""                 -> ""
        "20260422"         -> "2026-04-22T00:00:00Z"
        "2026-04-22"       -> "2026-04-22T00:00:00Z"
        "20251029100641"   -> "2025-10-29T10:06:41Z" (Molecubes NI archive
                              names use this 14-digit YYYYMMDDhhmmss form;
                              added round 8, 2026-05-22)
        "<already ISO>"    -> as-is
        "<ParaVision ISO with , decimal and tight tz>" -> normalised ISO
    """
    if not value:
        return ""
    s = value.strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}T00:00:00Z"
    if len(s) == 14 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}T{s[8:10]}:{s[10:12]}:{s[12:14]}Z"
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return f"{s}T00:00:00Z"
    # ParaVision dialect: "2025-10-16T08:38:22,085+0200" — comma decimal
    # before the timezone, and tight `+HHMM` tz without colon. Normalize
    # both to standard ISO 8601 (`.` decimal, `+HH:MM` tz).
    s = re.sub(r"(\d{2}:\d{2}:\d{2}),(\d+)", r"\1.\2", s)
    s = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", s)
    return s
