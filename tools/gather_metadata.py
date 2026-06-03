#!/usr/bin/env python3
"""gather_metadata.py - READ-ONLY merged "single source of truth" view.

Joins the acquisition-level /raw/<...>/<ACQ-ID>/metadata.json sidecar with the
study-level /projects/<proj>/metadata/<acq_id>.json supplement (plus the
project-wide study.json + biosamples.json when present) on `acq_id`, and emits
ONE merged JSON document to stdout. Consumers (OMERO, a future indexing DB,
ad-hoc analysis scripts) otherwise have to do a two-file read by hand -- see
mfb-rdm-docs/08_METADATA.md §1.4 + tasks/tasks.md §3.2.

The merge is additive and NON-destructive: the raw sidecar is the base
document and is never overwritten; study-level data is nested under a "study"
key (with the project-wide "biosamples" alongside). Missing project metadata
is tolerated -- the raw sidecar is emitted alone.

NEVER WRITES. Read-only against --nas-root (or $GJESUS3_ROOT).

Usage:
    python gather_metadata.py --acq ACQ-20211022-XMRI-001
    python gather_metadata.py --project PROJ-0001
    python gather_metadata.py --project lions-cardiac-mri --nas-root J:\\gjesus3-data
"""

import argparse
import glob
import json
import os
import sys
from datetime import datetime

# Make the sibling ingest/ package importable whether run from tools/ or elsewhere.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ingest import registry  # noqa: E402  (REGISTRY_FIELDS is the canonical schema)


def log(msg, level="INFO"):
    """Timestamped log line to stderr (stdout is reserved for the JSON payload)."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {level}: {msg}", file=sys.stderr)


def _load_json(path):
    """Read a JSON file, or None if it is absent/unreadable (logged at WARN)."""
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as exc:
        log(f"could not read {path}: {exc}", "WARN")
        return None


def _raw_sidecar_path(nas_root, row):
    """Resolve the raw sidecar path for a registry row via its canonical_path
    (a /raw/.../<ACQ-ID>/ path), falling back to a glob if the column is empty."""
    canon = (row.get("canonical_path") or "").strip()
    if canon:
        rel = canon.lstrip("/").rstrip("/")
        cand = os.path.join(nas_root, *rel.split("/"), "metadata.json")
        if os.path.isfile(cand):
            return cand
    hits = glob.glob(os.path.join(nas_root, "raw", "**", row["acq_id"], "metadata.json"),
                     recursive=True)
    return hits[0] if hits else None


def _project_folder(nas_root, project_rows, project_hint):
    """Return the absolute /projects/<proj>/ folder for a row's project_hint
    (a PROJ-XXXX id), or None. Matches on project_id or short_name."""
    if not project_hint:
        return None
    key = project_hint.strip().lower()
    for prow in project_rows:
        if key in (prow.get("project_id", "").lower(), prow.get("short_name", "").lower()):
            loc = (prow.get("folder_location") or "").strip()
            if loc:
                return os.path.join(nas_root, *loc.lstrip("/").rstrip("/").split("/"))
    return None


def merge_acq(nas_root, row, project_rows):
    """Build the merged document for one registry row. The raw sidecar is the
    base; study-level data is added under "study" / "biosamples" without ever
    overwriting acquisition-level fields."""
    acq = row["acq_id"]
    sidecar = _raw_sidecar_path(nas_root, row)
    if not sidecar:
        log(f"no raw sidecar found for {acq}", "WARN")
        return None
    doc = _load_json(sidecar)
    if doc is None:
        log(f"raw sidecar unreadable for {acq}", "WARN")
        return None

    proj_dir = _project_folder(nas_root, project_rows, row.get("project_hint", ""))
    if proj_dir:
        meta_dir = os.path.join(proj_dir, "metadata")
        # Per-acq study supplement -> nest under "study" (never clobber raw keys).
        acq_study = _load_json(os.path.join(meta_dir, f"{acq}.json"))
        study = _load_json(os.path.join(meta_dir, "study.json"))
        biosamples = _load_json(os.path.join(meta_dir, "biosamples.json"))
        study_block = {}
        if study is not None:
            study_block["study"] = study
        if acq_study is not None:
            study_block["acquisition"] = acq_study
        # "study" is a study-level (projects-side) key; raw sidecars never
        # carry it, so a plain set is non-destructive to acquisition fields.
        if study_block:
            doc["study"] = study_block
        if biosamples is not None:
            doc["biosamples"] = biosamples
        if not (acq_study or study or biosamples):
            log(f"project metadata folder present but no files for {acq}: {meta_dir}", "INFO")
    else:
        log(f"no project metadata for {acq} (hint={row.get('project_hint', '') or 'none'})",
            "INFO")
    return doc


def main():
    p = argparse.ArgumentParser(description="Read-only merged metadata view (raw + study).")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--acq", help="Acquisition id, e.g. ACQ-20211022-XMRI-001")
    g.add_argument("--project", help="Project id (PROJ-XXXX) or short_name")
    p.add_argument("--nas-root", default=os.environ.get("GJESUS3_ROOT", "/mnt/gjesus3"),
                   help="NAS root (default: $GJESUS3_ROOT or /mnt/gjesus3)")
    args = p.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    nas_root = args.nas_root
    registries_dir = os.path.join(nas_root, "registries")
    if not os.path.isdir(nas_root) or not os.path.isdir(registries_dir):
        log(f"NAS root does not look valid: '{nas_root}' (expected a directory "
            f"containing a 'registries/' subfolder).", "ERROR")
        log("Pass --nas-root <path>, or set GJESUS3_ROOT. On Windows: "
            "$env:GJESUS3_ROOT = 'J:\\gjesus3-data'.", "ERROR")
        return 2

    raw_rows = registry.read_registry(os.path.join(registries_dir, "registry_raw.csv"))
    project_rows = registry.read_registry(os.path.join(registries_dir, "registry_projects.csv"))

    if args.acq:
        rows = [r for r in raw_rows if r.get("acq_id") == args.acq]
        if not rows:
            log(f"acq_id not found in registry_raw.csv: {args.acq}", "ERROR")
            return 1
    else:
        key = args.project.strip().lower()
        ids = {p.get("project_id", "").lower(): p.get("project_id") for p in project_rows}
        shorts = {p.get("short_name", "").lower(): p.get("project_id") for p in project_rows}
        proj_id = ids.get(key) or shorts.get(key) or args.project
        # Accept a row whose project_hint is the canonical PROJ id, the raw arg,
        # OR a short_name left in place by a canonicalization-failed ingest
        # (ingest_raw Step 9.5 leaves the raw hint when project lookup fails).
        accept = {proj_id.lower(), key}
        accept |= {s for s, pid in shorts.items() if pid and pid.lower() == proj_id.lower()}
        rows = [r for r in raw_rows if (r.get("project_hint") or "").strip().lower() in accept]
        if not rows:
            log(f"no acquisitions with project_hint matching {sorted(accept)}", "ERROR")
            return 1

    merged = [d for d in (merge_acq(nas_root, r, project_rows) for r in rows) if d is not None]
    if not merged:
        log("nothing to emit (no readable sidecars).", "ERROR")
        return 1

    out = merged[0] if args.acq else merged
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
