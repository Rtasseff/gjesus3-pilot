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
    "operator",
    "data_source",
    "sample_id",
    "sample_type",
    "project_hint",
    "notes",
}

# Must be present in `registry:` (NA allowed; a missing key is an error).
REQUIRED_REGISTRY_KEYS = {
    "instrument",
    "data_ecosystem",
    "operator",
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


def normalize_acquisition_datetime(value):
    """Coerce a date-shaped string into ISO. Empty pass-through; ISO pass-through.

    Accepts:
        ""           -> ""
        "20260422"   -> "2026-04-22T00:00:00Z"
        "2026-04-22" -> "2026-04-22T00:00:00Z"
        "<already ISO>" -> as-is
    """
    if not value:
        return ""
    s = value.strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}T00:00:00Z"
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return f"{s}T00:00:00Z"
    return s
