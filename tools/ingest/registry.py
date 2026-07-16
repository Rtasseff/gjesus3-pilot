"""Read and append to registry_raw.csv."""

import csv
import os

from . import csv_safe


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
    "sample_organism",   # NEW 2026-06-10 (REG-07) — binomial species, e.g.
                         # "Mus musculus". Projection of the enrichment
                         # subject.species (animal DB). Blank for non-animal
                         # samples. AUTO (pipeline-derived, not a registry: key).
    "subject_ids",       # NEW 2026-06-10 (REG-01 Option B); RENAMED subject_id ->
                         # subject_ids 2026-06-12 (NI-LIVE-08). Packed, ;-joined,
                         # ALWAYS-A-LIST of canonical <animal_code>-AE-biomaGUNE-<NNNN>
                         # facility ids (= subject.facility_animal_id). A single-animal
                         # scan is a length-1 list (the bare id, no ';'); a multi-animal
                         # NI scan packs its 1–4 ids. Blank for non-animal samples. AUTO.
    "anatomical_entity", # NEW 2026-06-10 (REG-07 / META-09) — UBERON organ/region
                         # label, projection of anatomy.region.label. Blank when
                         # whole-body / unset / non-animal. AUTO.
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


def assert_header_compatible(registry_path):
    """Raise RuntimeError if an existing registry CSV's header doesn't match
    REGISTRY_FIELDS.

    No-op when the file doesn't exist yet (append_row creates it with the
    correct header). Call this as a PRE-FLIGHT check, before the expensive
    file copy, so a header/migration mismatch fails fast instead of after a
    multi-GB copy is already on the NAS — which the pre-commit rollback would
    then delete (forcing a needless re-copy). append_row runs the same check
    at write time, so this is a cheap early-out, not a new invariant.
    """
    if not os.path.exists(registry_path):
        return
    # BOM-tolerant header read (csv_safe): an Excel "Save As CSV UTF-8"
    # BOM must not make the header compare unequal and refuse every append.
    existing = csv_safe.read_header(registry_path)
    if existing != REGISTRY_FIELDS:
        raise RuntimeError(
            f"registry header mismatch in {registry_path}\n"
            f"  file has {len(existing)} columns: {existing}\n"
            f"  code expects {len(REGISTRY_FIELDS)}: {REGISTRY_FIELDS}\n"
            f"  refusing to append (would corrupt column alignment). "
            f"Migrate the CSV before re-running."
        )


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
        assert_header_compatible(registry_path)

    # Ensure all fields present (fill missing with empty string)
    row = {field: row_dict.get(field, "") for field in REGISTRY_FIELDS}

    # Guard against a missing trailing newline (Excel round-trip / hand edit),
    # which would otherwise concatenate this row onto the previous last row.
    csv_safe.ensure_trailing_newline(registry_path)
    with open(registry_path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REGISTRY_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def update_row(registry_path, acq_id, updates, only_if_blank=None):
    """Update fields on ONE existing registry_raw.csv row, matched by acq_id.

    `append_row` only ever ADDS rows; there was no way to fill in fields on an
    already-registered acquisition. The no-DICOM-regeneration backfill needs
    exactly that: when a placeholder's DICOMs are regenerated in place (keeping
    its ACQ-ID — the recovery pattern, NOT a re-ingest), its registry row must be
    updated with the now-real file_count / file_size_mb / checksum_present and a
    real acquisition_datetime. This is that update path.

    Read-all / rewrite-all with an atomic temp+os.replace, so a crash mid-write
    can't truncate the registry. Header-checked first (a mismatch means the CSV
    was migrated out from under the code — refuse rather than corrupt columns).

    CONCURRENCY: like `append_row`, this does NOT take the registry lock. The
    caller MUST hold `locking.registry_lock(registries_dir)` across the call —
    the read and the rewrite are one read-modify-write critical section. Keep it
    short (never hold the lock across a Dicomifier regen).

    Args:
        registry_path: path to registry_raw.csv.
        acq_id: the row to update (the unique key).
        updates: {field: new_value}. Every key must be a REGISTRY_FIELDS name.
        only_if_blank: optional iterable of field names to fill ONLY when the
            row's current value is blank (""/whitespace). Controlled-write: a
            field listed here whose existing value is real is LEFT UNTOUCHED and
            reported in `skipped`, never overwritten (e.g. acquisition_datetime,
            which 169 of the 247 pending rows already hold correctly). Fields not
            listed are written unconditionally.

    Returns (found, applied, skipped):
        found:   True if a row with `acq_id` existed.
        applied: {field: new_value} actually written.
        skipped: {field: existing_value} left alone by an only_if_blank guard.

    Raises RuntimeError if the header doesn't match REGISTRY_FIELDS or `updates`
    names a field not in REGISTRY_FIELDS (a typo'd field would otherwise be a
    silent no-op).
    """
    only_if_blank = set(only_if_blank or ())
    unknown = [k for k in updates if k not in REGISTRY_FIELDS]
    if unknown:
        raise RuntimeError(
            f"update_row: unknown field(s) {unknown} — not in REGISTRY_FIELDS. "
            f"Refusing to write (a mistyped column name is a silent no-op)."
        )
    if not os.path.exists(registry_path):
        return False, {}, {}
    assert_header_compatible(registry_path)

    rows = read_registry(registry_path)
    applied, skipped = {}, {}
    found = False
    for row in rows:
        if (row.get("acq_id") or "").strip() != acq_id:
            continue
        found = True
        for field, new_val in updates.items():
            if field in only_if_blank and (row.get(field) or "").strip():
                skipped[field] = row.get(field)
                continue
            row[field] = new_val
            applied[field] = new_val
        break

    if not found or not applied:
        # Nothing to write — leave the file byte-for-byte untouched (an
        # only_if_blank no-op, or acq_id absent). Report so the caller decides.
        return found, applied, skipped

    # Atomic rewrite: temp + os.replace. Write exactly REGISTRY_FIELDS columns
    # in order, UTF-8 (what read_registry prefers), so accented values round-trip.
    tmp = registry_path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REGISTRY_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in REGISTRY_FIELDS})
    os.replace(tmp, registry_path)
    return found, applied, skipped


def build_row(acq_id, cfg, summary, dest_path, registration_dt,
              subject=None, anatomy=None, subjects=None):
    """Build a registry row dict from config and analysis results.

    Args:
        acq_id: The generated ACQ-ID.
        cfg: Single-case config dict.
        summary: Source summary dict from dicom_utils.summarize_source.
        dest_path: Canonical path to the acquisition folder.
        registration_dt: ISO datetime string for registration_datetime.
        subject: the non-blocking enrichment subject block (or None for
            non-animal samples) — sources sample_organism + subject_ids.
        subjects: OPTIONAL list of subject blocks for a multi-animal NI scan
            (NI-LIVE-08). When given it supersedes `subject` — subject_ids is the
            ;-joined facility ids of the 1–4 animals; single-subject instruments
            keep passing `subject` (the length-1 path, unchanged).
        anatomy: the enrichment anatomy block (or None) — sources
            anatomical_entity from anatomy.region.label. Both blocks are built
            at ingest Step 8.4, before this row, so the values are in hand here.

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

    # The three preclinical descriptor columns are projections of the
    # non-blocking enrichment blocks (built at Step 8.4, before this row). They
    # are pipeline-derived (AUTO), not registry: keys, and blank for non-animal
    # samples (subject/anatomy are None for cells/material/phantom).
    # Normalize to a subject LIST: an explicit `subjects` list (a multi-animal
    # NI scan, NI-LIVE-08) wins; otherwise wrap the single `subject` (every
    # other instrument) as a length-1 list. The packed subject_ids +
    # sample_organism projections then come from the list either way — ONE code
    # path for 1..4 animals, no divergence between single- and multi-subject.
    subj_list = [s for s in (subjects if subjects is not None
                             else ([subject] if subject else [])) if s]
    packed_subject_ids = ";".join(
        fa for s in subj_list
        for fa in [(s.get("facility_animal_id") or "").strip()] if fa)
    sample_organism = next(
        ((s.get("species") or "").strip() for s in subj_list
         if (s.get("species") or "").strip()), "")
    anatomy = anatomy or {}
    region = anatomy.get("region") or {}

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
        # Projections over the subject LIST (built at Step 8.4). AUTO; blank for
        # non-animal samples. sample_organism = the (single) species; subject_ids
        # = the ;-joined facility ids (NI-LIVE-08) — a length-1 list for every
        # single-animal instrument, the packed 1–4 for a multi-animal NI scan.
        "sample_organism": sample_organism,
        "subject_ids": packed_subject_ids,
        "anatomical_entity": (region.get("label", "") if isinstance(region, dict) else "") or "",
        "session_id": cfg.get("session_id", ""),
        "primary_kind": cfg.get("primary_kind", ""),
        "primary_file_name": primary_file,
        "original_name": cfg.get("original_name", ""),
        "file_format": file_format,
        "file_size_mb": summary.get("total_size_mb", 0),
        "file_count": summary.get("file_count", 0),
        "canonical_path": dest_path,
        # "Y" unless the pipeline set it otherwise (the no-DICOM MRI placeholder
        # writes an empty checksums.json — nothing was actually checksummed, so a
        # hardcoded "Y" would misreport it). Default stays "Y" for the branches
        # that always write ≥1 checksum. See ingest_raw.py folder-copy branch.
        "checksum_present": cfg.get("checksum_present", "Y"),
        "extended_metadata_present": cfg.get("extended_metadata_present", "N"),
        "project_hint": cfg.get("project_hint", ""),
        "ingest_config": cfg.get("ingest_config", ""),
        "notes": cfg.get("notes", ""),
    }
