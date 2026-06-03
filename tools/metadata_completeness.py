#!/usr/bin/env python3
"""metadata_completeness.py — READ-ONLY enrichment-gap report.

Walks <nas_root>/raw/ metadata.json sidecars and surfaces the *non-blocking*
enrichment GAPS so they can be bulk-filled. This is the gap-focused companion
to validate_registries: where the validator judges correctness, this tool is
deliberately non-judgemental — it only points at the explicit "unknown"
sentinels the non-blocking model writes (08_METADATA §4.7), so a superuser can
sweep them in bulk.

What counts as a gap (only for organism/tissue acquisitions, per §4.3):
    * condition.is_control is null            (tri-state "unknown")
    * anatomy.is_whole_body is null           (organism only; tri-state)
    * subject.source == "pending-db"          (queued for DB recovery)
    * an expected block is missing entirely:
        - subject / condition missing for organism/tissue
        - anatomy missing for organism

It also reads registries/pending_subject_metadata.csv (via ingest.pending) and
lists rows whose status == "pending" — the recovery backlog.

The report is a per-gap table (acq_id, gap-type, detail) grouped by gap-type,
followed by counts. An optional --project filter matches the registry
project_hint (read from registry_raw.csv via ingest.registry).

Read-only: opens the registry, the pending list, and the sidecars for reading
only. Never writes to the NAS.

Usage:
    python tools/metadata_completeness.py --nas-root J:\\
    python tools/metadata_completeness.py --nas-root J:\\ --project ae-biomegune-0525
    # or rely on the GJESUS3_ROOT env var:
    python tools/metadata_completeness.py
"""

import argparse
import json
import os
import sys
from collections import Counter, defaultdict

# Allow "from ingest import ..." / "import animal_db" whether run from the repo
# root (python tools/metadata_completeness.py) or from inside tools/.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from ingest import registry, pending  # noqa: E402


def log(msg, level="INFO"):
    """Log to stderr; the report itself goes to stdout."""
    from datetime import datetime
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {level}: {msg}", file=sys.stderr)


# Sample types that trigger the enrichment blocks (08_METADATA §4.3).
SUBJECT_CONDITION_TYPES = {"organism", "tissue"}
ANATOMY_TYPES = {"organism"}

# Gap-type identifiers (stable strings used to group the report).
GAP_CONDITION_IS_CONTROL_NULL = "condition.is_control == null"
GAP_ANATOMY_WHOLE_BODY_NULL = "anatomy.is_whole_body == null"
GAP_SUBJECT_PENDING_DB = "subject.source == pending-db"
GAP_SUBJECT_BLOCK_MISSING = "subject block missing"
GAP_CONDITION_BLOCK_MISSING = "condition block missing"
GAP_ANATOMY_BLOCK_MISSING = "anatomy block missing"
GAP_PENDING_LIST = "pending-list status == pending"

# Order gap-types are presented in the report.
GAP_ORDER = [
    GAP_SUBJECT_BLOCK_MISSING,
    GAP_CONDITION_BLOCK_MISSING,
    GAP_ANATOMY_BLOCK_MISSING,
    GAP_SUBJECT_PENDING_DB,
    GAP_CONDITION_IS_CONTROL_NULL,
    GAP_ANATOMY_WHOLE_BODY_NULL,
    GAP_PENDING_LIST,
]


def walk_raw(nas_root):
    """Yield (acq_id, metadata_path, metadata_dict_or_None) over /raw/.

    Mirrors phase4_backfill_inventory.walk_raw: /raw/<eco>/<year>/<month>/<acq>/
    metadata.json. A missing or unreadable sidecar yields md=None.
    """
    raw_root = os.path.join(nas_root, "raw")
    if not os.path.isdir(raw_root):
        return
    for ecosystem in sorted(os.listdir(raw_root)):
        eco_path = os.path.join(raw_root, ecosystem)
        if not os.path.isdir(eco_path):
            continue
        for year in sorted(os.listdir(eco_path)):
            year_path = os.path.join(eco_path, year)
            if not os.path.isdir(year_path):
                continue
            for month in sorted(os.listdir(year_path)):
                month_path = os.path.join(year_path, month)
                if not os.path.isdir(month_path):
                    continue
                for acq in sorted(os.listdir(month_path)):
                    acq_path = os.path.join(month_path, acq)
                    if not os.path.isdir(acq_path):
                        continue
                    md_path = os.path.join(acq_path, "metadata.json")
                    if not os.path.isfile(md_path):
                        yield acq, md_path, None
                        continue
                    try:
                        with open(md_path, "r", encoding="utf-8") as f:
                            md = json.load(f)
                    except Exception as e:
                        log(f"failed to read {md_path}: {e}", "WARN")
                        md = None
                    yield acq, md_path, md


def sample_type_of(md):
    """Best-effort sample_type from a sidecar dict; '' if not parseable."""
    if not md:
        return ""
    us = md.get("user_supplied", {}) or {}
    return (us.get("sample_type") or "").strip().lower()


def load_project_hints(nas_root):
    """Map acq_id -> project_hint from registry_raw.csv (empty dict if absent)."""
    reg_path = os.path.join(nas_root, "registries", "registry_raw.csv")
    hints = {}
    for row in registry.read_registry(reg_path):
        acq = (row.get("acq_id") or "").strip()
        if acq:
            hints[acq] = (row.get("project_hint") or "").strip()
    return hints


def resolve_project_filter(nas_root, project_filter):
    """Return the set of acceptable project_hint values (lowercased) for a
    --project arg that may be a PROJ-XXXX id OR a human short_name.

    Mirrors gather_metadata so the two tools agree: a short_name is resolved
    to its canonical PROJ id via registry_projects.csv, and rows whose hint was
    left as a raw short_name (canonicalization-failed ingest) still match.
    Returns None when no filter is given.
    """
    if not project_filter:
        return None
    key = project_filter.strip().lower()
    proj_rows = registry.read_registry(
        os.path.join(nas_root, "registries", "registry_projects.csv"))
    ids = {(p.get("project_id") or "").lower(): (p.get("project_id") or "")
           for p in proj_rows}
    shorts = {(p.get("short_name") or "").lower(): (p.get("project_id") or "")
              for p in proj_rows}
    proj_id = ids.get(key) or shorts.get(key) or project_filter
    accept = {proj_id.lower(), key}
    accept |= {s for s, pid in shorts.items()
               if pid and pid.lower() == proj_id.lower()}
    return accept


def find_sidecar_gaps(acq_id, md):
    """Return a list of (gap_type, detail) for one acquisition's sidecar.

    Only organism/tissue acquisitions can produce gaps (anatomy: organism
    only). A None sidecar produces no gaps here — that is a structural issue
    for validate_registries, not an enrichment gap.
    """
    gaps = []
    if not md:
        return gaps
    st = sample_type_of(md)
    needs_subject_condition = st in SUBJECT_CONDITION_TYPES
    needs_anatomy = st in ANATOMY_TYPES
    if not needs_subject_condition:
        return gaps

    subject = md.get("subject")
    condition = md.get("condition")
    anatomy = md.get("anatomy")

    # Missing expected blocks.
    if not isinstance(subject, dict):
        gaps.append((GAP_SUBJECT_BLOCK_MISSING,
                     f"sample_type={st}; no subject block"))
    if not isinstance(condition, dict):
        gaps.append((GAP_CONDITION_BLOCK_MISSING,
                     f"sample_type={st}; no condition block"))
    if needs_anatomy and not isinstance(anatomy, dict):
        gaps.append((GAP_ANATOMY_BLOCK_MISSING,
                     f"sample_type={st}; no anatomy block"))

    # Sentinel gaps within present blocks.
    if isinstance(subject, dict) and subject.get("source") == "pending-db":
        fa = subject.get("facility_animal_id") or "(no facility_animal_id)"
        gaps.append((GAP_SUBJECT_PENDING_DB,
                     f"facility_animal_id={fa}"))

    if isinstance(condition, dict) and condition.get("is_control") is None:
        gaps.append((GAP_CONDITION_IS_CONTROL_NULL,
                     f"sample_type={st}; is_control unknown"))

    if needs_anatomy and isinstance(anatomy, dict) \
            and anatomy.get("is_whole_body") is None:
        gaps.append((GAP_ANATOMY_WHOLE_BODY_NULL,
                     "is_whole_body unknown"))

    return gaps


def collect_pending_gaps(nas_root):
    """Return (gap_type, detail) rows from the pending list with status==pending.

    Yields (acq_id, gap_type, detail) tuples.
    """
    path = pending.pending_path(os.path.join(nas_root, "registries"))
    out = []
    for row in pending.read_pending(path):
        if (row.get("status") or "").strip().lower() != "pending":
            continue
        acq = (row.get("acq_id") or "").strip()
        fa = row.get("facility_animal_id") or "(none)"
        reason = row.get("reason") or "(none)"
        logged = row.get("logged_at") or ""
        detail = f"facility_animal_id={fa}; reason={reason}; logged_at={logged}"
        out.append((acq, GAP_PENDING_LIST, detail))
    return out


def build_report(rows, total_acqs, scanned_acqs, project_filter):
    """rows: list of (acq_id, gap_type, detail). Return the markdown report str."""
    by_type = defaultdict(list)
    for acq, gap_type, detail in rows:
        by_type[gap_type].append((acq, detail))

    counts = Counter(gap_type for _, gap_type, _ in rows)
    acqs_with_gaps = len({acq for acq, _, _ in rows})

    lines = []
    lines.append("# Metadata enrichment-gap report")
    lines.append("")
    scope = f" (project filter: {project_filter})" if project_filter else ""
    lines.append(
        f"Scanned {scanned_acqs} of {total_acqs} acquisitions{scope}; "
        f"found {len(rows)} gap(s) across {acqs_with_gaps} acquisition(s)."
    )
    lines.append("")

    if not rows:
        lines.append("No enrichment gaps found. Nothing to bulk-fill.")
        lines.append("")
        return "\n".join(lines)

    # Per-gap tables, grouped by gap-type in a stable order.
    ordered_types = [t for t in GAP_ORDER if t in by_type]
    ordered_types += [t for t in sorted(by_type) if t not in GAP_ORDER]

    for gap_type in ordered_types:
        entries = sorted(by_type[gap_type])
        lines.append(f"## {gap_type}  ({len(entries)})")
        lines.append("")
        lines.append("| acq_id | detail |")
        lines.append("|---|---|")
        for acq, detail in entries:
            lines.append(f"| {acq} | {detail} |")
        lines.append("")

    # Counts summary.
    lines.append("## Counts by gap-type")
    lines.append("")
    lines.append("| gap-type | count |")
    lines.append("|---|---|")
    for gap_type in ordered_types:
        lines.append(f"| {gap_type} | {counts[gap_type]} |")
    lines.append(f"| **total gaps** | **{len(rows)}** |")
    lines.append("")
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Read-only enrichment-gap report over /raw/ sidecars + "
                    "the subject-metadata pending list.")
    p.add_argument(
        "--nas-root",
        default=os.environ.get("GJESUS3_ROOT", "/mnt/gjesus3"),
        help="Path to NAS root (default: $GJESUS3_ROOT or /mnt/gjesus3). "
             "Must contain a 'registries/' subfolder.")
    p.add_argument(
        "--project", default="",
        help="Only report acquisitions whose registry project_hint matches "
             "this value (case-insensitive exact match).")
    args = p.parse_args(argv)

    # Keep accented DB values / paths legible on the Windows console; the
    # report is plain markdown but acq details may carry non-ASCII.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    nas_root = args.nas_root
    registries_dir = os.path.join(nas_root, "registries")
    if not os.path.isdir(nas_root) or not os.path.isdir(registries_dir):
        log(f"NAS root does not look valid: '{nas_root}' (expected a "
            f"directory containing a 'registries/' subfolder).", "ERROR")
        log("Pass --nas-root <path> explicitly, or set GJESUS3_ROOT. On "
            "Windows PowerShell: $env:GJESUS3_ROOT = 'J:\\'  (adjust drive "
            "letter). On WSL: typically /mnt/gjesus3.", "ERROR")
        return 2

    log(f"NAS root: {nas_root}")
    project_filter = args.project.strip()
    if project_filter:
        log(f"Project filter: {project_filter}")

    hints = load_project_hints(nas_root)
    accept = resolve_project_filter(nas_root, project_filter)  # None if no filter

    rows = []
    total = 0
    scanned = 0
    scanned_ids = set()
    for acq, _md_path, md in walk_raw(nas_root):
        total += 1
        if accept is not None and hints.get(acq, "").lower() not in accept:
            continue
        scanned += 1
        scanned_ids.add(acq)
        for gap_type, detail in find_sidecar_gaps(acq, md):
            rows.append((acq, gap_type, detail))

    # Pending list. Apply the same project filter (by acq_id -> project_hint).
    for acq, gap_type, detail in collect_pending_gaps(nas_root):
        if accept is not None and hints.get(acq, "").lower() not in accept:
            continue
        rows.append((acq, gap_type, detail))

    # An empty scope from a non-empty filter is a false-negative trap: warn so
    # "no gaps" isn't misread as "fully enriched" when nothing was scanned.
    if project_filter and scanned == 0:
        log(f"project filter '{project_filter}' matched 0 of {total} "
            f"acquisitions - check the PROJ id / short_name. This is NOT "
            f"'no gaps'.", "WARN")

    report = build_report(rows, total, scanned, project_filter)
    print(report)

    log(f"Done: {len(rows)} gap(s) over {scanned} scanned acquisition(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
