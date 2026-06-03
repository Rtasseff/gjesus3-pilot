"""Build an in-memory ingest config dict from a per-instrument template + a
whitelisted set of operator overrides.

The template (loaded via `templates.load_template`) carries every locked
convention. The operator front-ends only ever change a small, safe set of
values per batch/run — the WHITELIST below. Anything outside the whitelist is
rejected so a front-end can never silently corrupt a convention.

`copy_strategy` and `acquisition_layout` are TEMPLATE-LOCKED: they select the
per-instrument copy function and the primary-entity shape, and changing them
would break the ingest. Attempts to override them raise.

The result is the same dict shape `config.load_config` returns, ready for
`config.expand_batch` / `ingest_raw.run_batch` — no YAML on disk required.
"""

import copy


class OverrideError(ValueError):
    """Raised when an override targets a key outside the whitelist or a
    template-locked key."""


# --- Whitelist (operator-safe override targets) ---------------------------
#
# Each entry is a dotted path into the config dict. Top-level keys (link_filename)
# and whole-block keys (registry, auto_create_project) are handled as families:
# `auto_discover.<leaf>`, `registry.<column>`, `auto_create_project.<field>`,
# and the operator-safe `ingest.<flag>` set below.

# auto_discover leaves the operator may set (where the files are / how to
# parse + filter them). copy_strategy / acquisition_layout live under `ingest`
# and are explicitly LOCKED (see below).
AUTO_DISCOVER_OVERRIDES = {
    "staging_dir",
    "pattern",
    "filename_parse",
    "path_parse",
    "filter",
    "acquisition_date_from",
    "subject_from_db",
    "subject_lookup",
}

# ingest: control flags the operator may set. Everything else under ingest
# (notably copy_strategy + acquisition_layout) is template-locked.
INGEST_OVERRIDES = {
    "reconstructions",
    "auto_regenerate_dicom",
    "delete_source_after_ingest",
    "auto_create_projects",
}

# ingest: keys that must NEVER be overridden (they select the copy machinery
# and the on-disk primary shape; the template owns them).
INGEST_LOCKED = {
    "copy_strategy",
    "acquisition_layout",
}

# Top-level scalar overrides.
TOPLEVEL_OVERRIDES = {
    "link_filename",
}

# Whole-block override families: an override key of the form "<family>.<leaf>"
# (or the bare family name carrying a dict) merges into that block.
BLOCK_FAMILIES = {
    "registry",            # any registry: column expression
    "auto_create_project",  # owner / description / notes
    "condition",           # Phase 3 preclinical
    "anatomy",             # Phase 3 preclinical
    "subject",             # Phase 3 operator-override subject block
}


def _ensure_dict(cfg, key):
    """Return cfg[key], creating an empty dict there if absent/None."""
    block = cfg.get(key)
    if not isinstance(block, dict):
        block = {}
        cfg[key] = block
    return block


def _apply_one(cfg, dotted_key, value):
    """Apply a single override (dotted_key -> value) into the right nested key.

    Raises OverrideError for keys outside the whitelist or template-locked keys.
    """
    parts = dotted_key.split(".", 1)
    head = parts[0]
    leaf = parts[1] if len(parts) == 2 else None

    if head == "ingest":
        if leaf is None:
            raise OverrideError(
                "ingest override must target a specific flag "
                f"(e.g. 'ingest.reconstructions'), got bare {dotted_key!r}"
            )
        if leaf in INGEST_LOCKED:
            raise OverrideError(
                f"'ingest.{leaf}' is template-locked and cannot be overridden "
                f"(it selects the per-instrument copy machinery / primary "
                f"shape). Locked keys: {sorted(INGEST_LOCKED)}"
            )
        if leaf not in INGEST_OVERRIDES:
            raise OverrideError(
                f"'ingest.{leaf}' is not an operator-overridable flag. "
                f"Allowed: {sorted(INGEST_OVERRIDES)}"
            )
        _ensure_dict(cfg, "ingest")[leaf] = value
        return

    if head == "auto_discover":
        if leaf is None:
            raise OverrideError(
                "auto_discover override must target a specific key "
                f"(e.g. 'auto_discover.staging_dir'), got bare {dotted_key!r}"
            )
        if leaf not in AUTO_DISCOVER_OVERRIDES:
            raise OverrideError(
                f"'auto_discover.{leaf}' is not an overridable key. "
                f"Allowed: {sorted(AUTO_DISCOVER_OVERRIDES)}"
            )
        _ensure_dict(cfg, "auto_discover")[leaf] = value
        return

    if head in BLOCK_FAMILIES:
        block = _ensure_dict(cfg, head)
        if leaf is None:
            # Bare family carrying a whole dict -> merge keys into the block.
            if not isinstance(value, dict):
                raise OverrideError(
                    f"override {head!r} must be a mapping when targeting the "
                    f"whole block, got {type(value).__name__}"
                )
            block.update(value)
        else:
            block[leaf] = value
        return

    if head in TOPLEVEL_OVERRIDES and leaf is None:
        cfg[head] = value
        return

    raise OverrideError(
        f"override {dotted_key!r} is not on the operator whitelist. "
        f"Allowed: auto_discover.<{sorted(AUTO_DISCOVER_OVERRIDES)}>, "
        f"ingest.<{sorted(INGEST_OVERRIDES)}>, "
        f"<{sorted(BLOCK_FAMILIES)}>.<key>, {sorted(TOPLEVEL_OVERRIDES)}. "
        f"('ingest.copy_strategy'/'ingest.acquisition_layout' are "
        f"template-locked.)"
    )


def build_config(template_dict, overrides):
    """Deep-copy `template_dict` and apply `overrides`, returning a new cfg dict.

    Args:
        template_dict: a per-instrument template dict (from
            templates.load_template). NOT mutated — deep-copied first.
        overrides: a flat dict of dotted-key -> value. Supported keys:
            - "auto_discover.<leaf>" for leaf in AUTO_DISCOVER_OVERRIDES
            - "ingest.<flag>" for flag in INGEST_OVERRIDES
            - "registry.<column>" / "auto_create_project.<field>" /
              "condition.<field>" / "anatomy.<field>" / "subject.<field>"
              (or the bare block name carrying a dict to merge)
            - "link_filename"

    Returns:
        A new config dict ready for config.expand_batch / run_batch.

    Raises:
        OverrideError: if any override key is outside the whitelist or targets
            a template-locked key (copy_strategy / acquisition_layout).
    """
    cfg = copy.deepcopy(template_dict)
    for dotted_key, value in (overrides or {}).items():
        _apply_one(cfg, dotted_key, value)
    return cfg
