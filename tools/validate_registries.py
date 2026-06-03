#!/usr/bin/env python3
"""validate_registries.py — READ-ONLY consistency checker for the registry area.

Walks `registries/` + the `/raw/` tree under a NAS root and reports problems.
Implements REG-04 (tasks.md §3.2). NEVER writes anything; the NAS can be
mounted read-only. Exits nonzero (1) if any ERROR-level issue is found, 0
otherwise. WARN-level findings (Phase 3 enrichment gaps under the non-blocking
metadata model) never affect the exit code.

WHAT IT CHECKS
  registry_raw.csv structure
    - header EXACTLY equals ingest.registry.REGISTRY_FIELDS (the schema is
      imported, never hardcoded — 06_REGISTRIES is the contract).
    - no duplicate acq_id.
    - acq_id matches ACQ-YYYYMMDD-<CODE>-NNN.
    - required columns non-empty per row: acq_id, registration_datetime,
      data_ecosystem, instrument, canonical_path.
    - sample_type, when set, is in the controlled vocab
      {tissue, organism, cells, material, phantom}.
    - canonical_path starts with /raw/ and the acquisition folder exists on
      disk (canonical_path joined to nas_root).
    - project_hint, when set and matching PROJ-XXXX, exists in
      registries/registry_projects.csv.

  Phase 3 enrichment (WARN-level, non-blocking model — 08_METADATA §4.3-4.7)
    For rows whose sample_type is organism or tissue, the sidecar
    metadata.json must carry a subject: block AND a condition: block (and an
    anatomy: block for organism). Missing blocks are WARNs. So are the
    explicit unknown sentinels that signal an open enrichment gap:
    subject.source == "pending-db", condition.is_control == null,
    anatomy.is_whole_body == null. Under the non-blocking model these are
    legitimate (never-block) states, hence WARN not ERROR.

Usage:
    python tools/validate_registries.py --nas-root J:\\gjesus3-data
    python tools/validate_registries.py            # uses $GJESUS3_ROOT
    python tools/validate_registries.py --no-enrichment   # skip Phase 3 WARNs
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime

# Make `from ingest import ...` / `import animal_db` work whether the script
# is launched from the repo root or from tools/ (mirrors ingest_raw.py).
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from ingest import registry  # noqa: E402  (after sys.path tweak)


def log(msg, level="INFO"):
    """Timestamped log line to stderr; ASCII only for the Windows console."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {level}: {msg}", file=sys.stderr)


# ---- Constants -----------------------------------------------------------

# acq_id grammar: ACQ-YYYYMMDD-<CODE>-NNN (CODE = uppercase alnum instrument
# code, NNN = zero-padded sequence). 06_REGISTRIES §2.2.
ACQ_ID_RE = re.compile(r"^ACQ-\d{8}-[A-Z0-9]+-\d{3}$")
PROJ_ID_RE = re.compile(r"^PROJ-\d{4}$")

REQUIRED_COLUMNS = [
    "acq_id",
    "registration_datetime",
    "data_ecosystem",
    "instrument",
    "canonical_path",
]

# Controlled vocab for sample_type (06_REGISTRIES / data contract). Blank is
# allowed; any other non-blank value is an ERROR.
SAMPLE_TYPE_VOCAB = {"tissue", "organism", "cells", "material", "phantom"}

# sample_types that require Phase 3 preclinical enrichment blocks.
ENRICH_SAMPLE_TYPES = {"organism", "tissue"}


# ---- Issue collection ----------------------------------------------------

class Issues:
    """Accumulates ERROR/WARN findings with optional row context."""

    def __init__(self):
        self.errors = []
        self.warnings = []

    def error(self, msg, acq_id=None):
        self.errors.append((acq_id, msg))

    def warn(self, msg, acq_id=None):
        self.warnings.append((acq_id, msg))


# ---- Helpers -------------------------------------------------------------

def _read_csv_rows(path):
    """Read a CSV into (header, list-of-row-dicts).

    Tolerant of legacy non-UTF-8 bytes in older registries (e.g. accented
    project descriptions written with a cp1252 console): falls back to
    latin-1, which never raises on byte input. Returns (None, []) if absent.
    """
    if not os.path.exists(path):
        return None, []
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                f.seek(0)
                dreader = csv.DictReader(f)
                rows = list(dreader)
            return header, rows
        except UnicodeDecodeError:
            continue
    return None, []


def _acq_folder_on_disk(nas_root, canonical_path):
    """Join a /raw/-rooted canonical_path to nas_root -> local filesystem path.

    canonical_path is a POSIX-style, leading-slash path (e.g.
    "/raw/DICOM/2021/2021-10/ACQ-.../"); strip the leading slash and any
    trailing slash, split on "/" so it resolves correctly on Windows too.
    """
    rel = canonical_path.strip().lstrip("/").rstrip("/")
    parts = [p for p in rel.split("/") if p]
    return os.path.join(nas_root, *parts)


def _load_project_ids(registries_dir, issues):
    """Return the set of project_id values in registry_projects.csv.

    A missing projects registry is a WARN (project_hint cross-checks are then
    skipped), not a hard ERROR — the file may legitimately not exist yet on a
    fresh NAS.
    """
    path = os.path.join(registries_dir, "registry_projects.csv")
    header, rows = _read_csv_rows(path)
    if header is None:
        issues.warn(
            "registry_projects.csv not found; project_hint existence checks "
            "skipped."
        )
        return None
    return {(r.get("project_id") or "").strip() for r in rows}


# ---- Sidecar enrichment check (Phase 3, WARN-level) ----------------------

def check_enrichment(acq_id, sample_type, folder, issues):
    """Inspect the acquisition's metadata.json for Phase 3 enrichment blocks.

    All findings here are WARN-level by design: the non-blocking metadata model
    (08_METADATA §4.3-4.7) treats unknown as an explicit, legitimate sentinel
    that must never block ingest — so a missing/placeholder block is a gap to
    chase, not a structural error.
    """
    sidecar = os.path.join(folder, "metadata.json")
    if not os.path.isfile(sidecar):
        issues.warn(
            f"sample_type={sample_type} but no metadata.json sidecar at "
            f"{sidecar}", acq_id)
        return
    try:
        with open(sidecar, "r", encoding="utf-8") as f:
            md = json.load(f)
    except (OSError, ValueError) as exc:
        issues.warn(f"could not parse sidecar {sidecar}: {exc}", acq_id)
        return
    # A valid-JSON-but-wrong-shape sidecar (e.g. a hand-edited block that ended
    # up a string/list, or a top-level array) must WARN, never crash the run
    # (non-blocking contract). Guard every .get with an isinstance(dict) check.
    if not isinstance(md, dict):
        issues.warn(f"sidecar {sidecar} is not a JSON object", acq_id)
        return

    subject = md.get("subject")
    condition = md.get("condition")
    anatomy = md.get("anatomy")

    if subject is None:
        issues.warn("sidecar missing subject: block", acq_id)
    elif not isinstance(subject, dict):
        issues.warn("subject: block is not a JSON object", acq_id)
    elif subject.get("source") == "pending-db":
        issues.warn(
            "subject.source == 'pending-db' (deferred-recovery gap)", acq_id)

    if condition is None:
        issues.warn("sidecar missing condition: block", acq_id)
    elif not isinstance(condition, dict):
        issues.warn("condition: block is not a JSON object", acq_id)
    elif condition.get("is_control", "MISSING") is None:
        issues.warn("condition.is_control is null (unknown sentinel)", acq_id)

    if sample_type == "organism":
        if anatomy is None:
            issues.warn("sidecar missing anatomy: block (organism)", acq_id)
        elif not isinstance(anatomy, dict):
            issues.warn("anatomy: block is not a JSON object", acq_id)
        elif anatomy.get("is_whole_body", "MISSING") is None:
            issues.warn(
                "anatomy.is_whole_body is null (unknown sentinel)", acq_id)


# ---- Main registry walk --------------------------------------------------

def validate(nas_root, check_enrich=True):
    """Run all checks. Returns (Issues, n_rows)."""
    issues = Issues()
    registries_dir = os.path.join(nas_root, "registries")
    registry_path = os.path.join(registries_dir, "registry_raw.csv")

    header, rows = _read_csv_rows(registry_path)
    if header is None:
        issues.error(f"registry_raw.csv not found at {registry_path}")
        return issues, 0

    # 1. Header EXACTLY matches the imported schema.
    if header != registry.REGISTRY_FIELDS:
        issues.error(
            "registry_raw.csv header does not match REGISTRY_FIELDS.\n"
            f"    file has {len(header)} columns: {header}\n"
            f"    schema expects {len(registry.REGISTRY_FIELDS)}: "
            f"{registry.REGISTRY_FIELDS}"
        )
        # Header is the contract for every per-row check below; if it is wrong,
        # column->value alignment is unreliable. Report and stop here.
        return issues, len(rows)

    project_ids = _load_project_ids(registries_dir, issues)

    seen_acq = {}
    for i, row in enumerate(rows, start=2):  # +2: header is line 1
        acq = (row.get("acq_id") or "").strip()
        label = acq or f"<row {i}>"

        # 2. duplicate acq_id
        if acq:
            if acq in seen_acq:
                issues.error(
                    f"duplicate acq_id (first seen on line {seen_acq[acq]})",
                    acq)
            else:
                seen_acq[acq] = i

        # 3. acq_id format
        if acq and not ACQ_ID_RE.match(acq):
            issues.error(
                "acq_id does not match ACQ-YYYYMMDD-<CODE>-NNN", label)

        # 4. required columns non-empty
        for col in REQUIRED_COLUMNS:
            if not (row.get(col) or "").strip():
                issues.error(f"required column '{col}' is empty", label)

        # 5. sample_type controlled vocab (blank allowed)
        sample_type = (row.get("sample_type") or "").strip()
        if sample_type and sample_type not in SAMPLE_TYPE_VOCAB:
            issues.error(
                f"sample_type '{sample_type}' not in controlled vocab "
                f"{sorted(SAMPLE_TYPE_VOCAB)}", label)

        # 6. canonical_path /raw/-rooted + folder exists on disk
        canonical = (row.get("canonical_path") or "").strip()
        folder = None
        if canonical:
            if not canonical.startswith("/raw/"):
                issues.error(
                    f"canonical_path '{canonical}' does not start with /raw/",
                    label)
            else:
                folder = _acq_folder_on_disk(nas_root, canonical)
                if not os.path.isdir(folder):
                    issues.error(
                        f"acquisition folder not found on disk: {folder} "
                        f"(from canonical_path '{canonical}')", label)
                    folder = None  # don't chase a sidecar we can't reach

        # 7. project_hint existence (only PROJ-XXXX form, only if we have a set)
        hint = (row.get("project_hint") or "").strip()
        if hint and PROJ_ID_RE.match(hint) and project_ids is not None:
            if hint not in project_ids:
                issues.error(
                    f"project_hint '{hint}' not found in "
                    f"registry_projects.csv", label)

        # 8. Phase 3 enrichment (WARN) — needs a resolvable folder
        if (check_enrich and sample_type in ENRICH_SAMPLE_TYPES
                and folder is not None):
            check_enrichment(acq or label, sample_type, folder, issues)

    return issues, len(rows)


# ---- Reporting -----------------------------------------------------------

def print_report(issues, n_rows):
    """Print summary + itemized findings to stdout."""
    print("=" * 64)
    print("registry validation report")
    print("=" * 64)
    print(f"rows checked: {n_rows}")
    print(f"errors:       {len(issues.errors)}")
    print(f"warnings:     {len(issues.warnings)}")
    print()

    if issues.errors:
        print(f"-- ERRORS ({len(issues.errors)}) " + "-" * 40)
        for acq, msg in issues.errors:
            prefix = f"[{acq}] " if acq else ""
            print(f"  ERROR: {prefix}{msg}")
        print()

    if issues.warnings:
        print(f"-- WARNINGS ({len(issues.warnings)}) " + "-" * 38)
        for acq, msg in issues.warnings:
            prefix = f"[{acq}] " if acq else ""
            print(f"  WARN:  {prefix}{msg}")
        print()

    if not issues.errors and not issues.warnings:
        print("No issues found.")


# ---- CLI -----------------------------------------------------------------

def main(argv=None):
    # Keep accented values (e.g. legacy project descriptions) legible on the
    # Windows console; output is otherwise ASCII.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser(
        description="Read-only validator for the gjesus3 registry area (REG-04)."
    )
    parser.add_argument(
        "--nas-root",
        default=os.environ.get("GJESUS3_ROOT", "/mnt/gjesus3"),
        help="Path to NAS root (default: $GJESUS3_ROOT or /mnt/gjesus3).",
    )
    parser.add_argument(
        "--no-enrichment",
        action="store_true",
        help="Skip the Phase 3 enrichment (sidecar) WARN-level checks.",
    )
    args = parser.parse_args(argv)

    nas_root = args.nas_root
    log(f"NAS root: {nas_root}")

    # Fail fast if nas_root doesn't look real (mirror ingest_raw.py): without
    # this, os.path.join silently builds a phantom tree and every row "fails".
    registries_dir = os.path.join(nas_root, "registries")
    if not os.path.isdir(nas_root) or not os.path.isdir(registries_dir):
        log(
            f"NAS root does not look valid: '{nas_root}' (expected a "
            f"directory containing a 'registries/' subfolder).", "ERROR")
        log(
            "Pass --nas-root <path> explicitly, or set GJESUS3_ROOT. On "
            "Windows PowerShell: $env:GJESUS3_ROOT = 'J:\\gjesus3-data'.",
            "ERROR")
        return 2

    issues, n_rows = validate(nas_root, check_enrich=not args.no_enrichment)
    print_report(issues, n_rows)

    if issues.errors:
        log(f"validation FAILED: {len(issues.errors)} error(s).", "ERROR")
        return 1
    log(f"validation OK: 0 errors, {len(issues.warnings)} warning(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
