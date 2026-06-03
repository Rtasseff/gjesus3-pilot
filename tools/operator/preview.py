"""Read-only "what will happen" preview for an ingest config.

`config.expand_batch` resolves `discovered.*` + the `registry` row per case and
dedups against the live registry, but it does NOT compute the three values that
only appear mid-`ingest_single` (after its `--dry-run` early-return at
ingest_raw.py:757): the ACQ-ID, the canonical project, and the resolved
`link_filename`. This module replicates those three steps READ-ONLY so a
front-end can show a true preview before committing.

Replication faithfully mirrors `ingest_single`:

  - acq_date  : from registry acquisition_datetime[:10] stripped of '-' (Step 3).
                The DICOM-StudyDate / today fallbacks are NOT replicated here —
                for NI/MRI/microscopy the registry value is always present; a
                case missing it gets a warning and is reported with acq_date "".
  - acq_id    : acq_id.generate_acq_id(acq_date, instrument, registry_path)
                (Step 4). generate_acq_id only reads the on-disk registry, so to
                mirror ingest_single's sequential appends we maintain an in-batch
                counter keyed on (acq_date, instrument) — without it, two
                same-date/instrument cases would both preview as -001.
  - project   : linker.resolve_project (Step 9.5) -> "PROJ-XXXX" or, when absent
                and ingest.auto_create_projects is on, "will auto-create: <hint>".
  - link name : resolver.resolve_link_filename (Step 12), rstrip("/\\"),
                fallback to the FULL original_name (exactly as ingest_single).

MUST NOT write anything to the NAS. Every call is pure CSV reads
(read_registry / DictReader).
"""

import contextlib
import io
import os
from dataclasses import dataclass, field
from typing import Optional

# tools/ on sys.path (see templates.py) so `from ingest import ...` works.
from . import templates as _templates  # noqa: F401  (ensures sys.path setup)
from ingest import config, acq_id as acq_id_mod, linker, resolver


@dataclass
class CasePreview:
    """Per-case preview of what an ingest would produce."""
    source: str
    original_name: str
    discovered: dict
    registry_resolved: dict
    acq_date: str
    acq_id_preview: str
    project_preview: str          # "PROJ-XXXX" | "will auto-create: <hint>"
                                  # | "hint not found: <hint>" | "(no project)"
    link_filename_preview: str
    warnings: list = field(default_factory=list)


@dataclass
class PreviewResult:
    """Aggregate preview over a whole batch config."""
    cases: list = field(default_factory=list)         # list[CasePreview]
    n_matched: int = 0                                 # glob matches before dedup
    n_skipped: int = 0                                 # already-ingested / skipped
    n_new: int = 0                                     # cases that would ingest
    blocking_errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)       # batch-level warnings


def _derive_acq_date(case, warnings):
    """Mirror ingest_single Step 3 for the common (registry-supplied) path.

    Returns the YYYYMMDD string, or "" if no usable acquisition_datetime is on
    the case (we don't read DICOM headers here — that fallback is irrelevant for
    NI/MRI/microscopy, which always carry the date).
    """
    acq_dt_iso = (case.get("acquisition_datetime") or "")
    if acq_dt_iso and len(acq_dt_iso) >= 10:
        return acq_dt_iso[:10].replace("-", "")
    warnings.append(
        "no acquisition_datetime resolved for this case; acq_id date prefix "
        "cannot be previewed (the real ingest would fall back to DICOM "
        "StudyDate or today)."
    )
    return ""


def _count_glob_matches(cfg):
    """Best-effort count of glob matches (pre-dedup), to populate n_matched.

    Mirrors expand_batch's `glob(join(staging_dir, pattern), recursive=True)`
    filtered to existing files/dirs. Read-only.
    """
    disco = cfg.get("auto_discover") or {}
    staging_dir = disco.get("staging_dir")
    pattern = disco.get("pattern", "*/")
    if not staging_dir:
        return 0
    import glob as globmod
    search = os.path.join(staging_dir, pattern)
    matches = globmod.glob(search, recursive=True)
    return sum(1 for m in matches if os.path.isdir(m) or os.path.isfile(m))


def preview_batch(cfg, nas_root):
    """Build a PreviewResult for the batch config `cfg` against `nas_root`.

    READ-ONLY: calls config.expand_batch (which only reads the registry for
    dedup) then replicates the acq_id / project / link resolution that
    ingest_single performs after its dry-run early-return. Never writes.

    Args:
        cfg: a batch config dict (from config_builder.build_config). Must have
            an `auto_discover` block (expand_batch requires it).
        nas_root: NAS root (its registries/ holds registry_raw.csv +
            registry_projects.csv). Should be validated by env.validate_nas_root
            before calling.

    Returns:
        PreviewResult.
    """
    result = PreviewResult()

    registry_path = os.path.join(nas_root, "registries", "registry_raw.csv")
    projects_registry = os.path.join(
        nas_root, "registries", "registry_projects.csv"
    )

    # n_matched: count glob matches before dedup (best-effort, read-only).
    try:
        result.n_matched = _count_glob_matches(cfg)
    except Exception as e:  # noqa: BLE001 — preview must never explode
        result.warnings.append(f"could not count glob matches: {e}")

    # expand_batch resolves discovered + registry_resolved + original_name and
    # dedups against the live registry. Structural config errors raise
    # ValueError -> a blocking error. Its per-case skip/warn lines go to stdout
    # via print(); capture them as batch-level warnings.
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            cases = config.expand_batch(cfg, nas_root=nas_root)
    except ValueError as e:
        result.blocking_errors.append(str(e))
        _drain_stdout(buf, result.warnings)
        return result
    _drain_stdout(buf, result.warnings)

    result.n_new = len(cases)
    # Skipped = matched-minus-new when we have a reliable match count; the
    # captured stdout WARN/SKIP lines carry the per-case detail.
    if result.n_matched:
        result.n_skipped = max(result.n_matched - result.n_new, 0)

    auto_create = bool((cfg.get("ingest") or {}).get("auto_create_projects"))

    # In-batch acq_id counter: (acq_date, instrument) -> last seq handed out.
    # Seeded lazily from generate_acq_id's on-disk baseline, then incremented
    # locally per same-key case (mirrors ingest_single appending each row
    # before the next case runs). See acq_id.generate_acq_id read-only note.
    seq_seen = {}

    for case in cases:
        warnings = []
        instrument = case.get("instrument") or ""
        acq_date = _derive_acq_date(case, warnings)

        acq_id_preview = _preview_acq_id(
            acq_date, instrument, registry_path, seq_seen, warnings
        )
        project_preview = _preview_project(
            case, projects_registry, auto_create
        )
        link_preview = _preview_link(case, acq_id_preview, acq_date, warnings)

        result.cases.append(CasePreview(
            source=case.get("source_path", ""),
            original_name=case.get("original_name", ""),
            discovered=case.get("discovered") or {},
            registry_resolved=case.get("registry_resolved") or {},
            acq_date=acq_date,
            acq_id_preview=acq_id_preview,
            project_preview=project_preview,
            link_filename_preview=link_preview,
            warnings=warnings,
        ))

    return result


def _drain_stdout(buf, warnings):
    """Move captured stdout lines into the warnings list (non-empty lines)."""
    text = buf.getvalue()
    for line in text.splitlines():
        line = line.rstrip()
        if line:
            warnings.append(line)


def _preview_acq_id(acq_date, instrument, registry_path, seq_seen, warnings):
    """Replicate Step 4 acq_id with an in-batch sequential counter.

    generate_acq_id reads only the on-disk registry, so for the first case of a
    given (acq_date, instrument) we take its result as the baseline; subsequent
    same-key cases increment locally to simulate the sequential appends the real
    ingest performs.
    """
    if not acq_date or not instrument:
        return ""
    # Surface an out-of-vocabulary instrument (reachable only via a GUI-builder
    # registry.instrument override): generate_acq_id will happily build an id
    # from it, but the commit rejects it at config.validate_single — so warn now
    # rather than let it look fine in preview and silently fail at commit.
    valid = getattr(config, "VALID_INSTRUMENTS", None)
    if valid and instrument not in valid:
        warnings.append(
            f"instrument '{instrument}' is not a recognized code; the commit "
            f"would reject this case (validate_single). Preview acq_id is shown "
            f"for reference only."
        )
    key = (acq_date, instrument)
    try:
        if key not in seq_seen:
            generated = acq_id_mod.generate_acq_id(
                acq_date, instrument, registry_path
            )
            # ACQ-YYYYMMDD-INST-SEQ -> trailing seq int.
            seq = int(generated.rsplit("-", 1)[-1])
            seq_seen[key] = seq
            return generated
        seq_seen[key] += 1
        return f"ACQ-{acq_date}-{instrument}-{seq_seen[key]:03d}"
    except ValueError as e:
        warnings.append(f"acq_id preview failed: {e}")
        return ""


def _preview_project(case, projects_registry, auto_create):
    """Replicate Step 9.5 project resolution, read-only.

    Returns "PROJ-XXXX" on a resolved hint, "will auto-create: <hint>" when the
    hint is absent and auto_create is on, "hint not found: <hint>" otherwise, or
    "(no project)" when no hint was set.
    """
    project_hint = (case.get("project_hint") or "").strip()
    if not project_hint:
        return "(no project)"
    proj_id, _folder = linker.resolve_project(projects_registry, project_hint)
    if proj_id:
        return proj_id
    if auto_create:
        return f"will auto-create: {project_hint}"
    return f"hint not found: {project_hint}"


def _preview_link(case, acq_id_preview, acq_date, warnings):
    """Replicate Step 12 link-name resolution, read-only.

    resolve_link_filename warns to stdout on unresolved ${...} refs; capture
    those into the per-case warnings. Falls back to the original_name basename
    when the template has no link_filename (same as ingest_single).
    """
    template = case.get("link_filename") or ""
    link_name = None
    if template:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            link_name = resolver.resolve_link_filename(
                template, case, acq_id_preview, acq_date
            )
        _drain_stdout(buf, warnings)
        if link_name:
            link_name = link_name.rstrip("/").rstrip("\\")
    if not link_name:
        # Fallback mirrors ingest_single (ingest_raw.py L1134) EXACTLY: the FULL
        # original_name, not the basename — so the preview is faithful to what
        # commit would attempt. (Every shipped template sets link_filename, so
        # this path only surfaces for a GUI-builder convention that leaves it
        # empty.)
        link_name = (case.get("original_name") or "").rstrip("/").rstrip("\\")
    return link_name
