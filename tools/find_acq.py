#!/usr/bin/env python3
"""find_acq.py — search the acquisition registry (the join engine + a CLI).

Reads ``<nas>/registries/registry_raw.csv`` (+ ``registry_projects.csv`` for the
per-project folder) and produces one flat, searchable record per acquisition:
the researcher-relevant fields + the resolved data path. Used by the CLI here
AND by ``generate_index.py`` (the self-contained HTML "Finder"). No DB, no
XNAT/OMERO — just the registry you already maintain.

CLI examples (read-only):
    PYTHONPATH=tools python tools/find_acq.py m17
    PYTHONPATH=tools python tools/find_acq.py MRI --since 2026-02
    PYTHONPATH=tools python tools/find_acq.py --subject 13 --anatomy heart
    PYTHONPATH=tools python tools/find_acq.py --instrument ZWSI --project PROJ-0003

See tools/FINDER.md.
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ingest import registry  # noqa: E402  (BOM-tolerant read_registry)

# Free-text search is matched against the lower-cased concatenation of these.
SEARCH_FIELDS = [
    "acq_id", "acquisition_datetime", "instrument", "instrument_model",
    "modalities_in_study", "sample_id", "subject_ids", "sample_organism",
    "anatomical_entity", "researcher", "operator", "project_hint", "session_id",
    "original_name", "notes", "data_source",
]


def _projects_index(nas):
    """project_id -> {folder, short, owner} from registry_projects.csv."""
    path = os.path.join(nas, "registries", "registry_projects.csv")
    idx = {}
    if os.path.isfile(path):
        with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
            for r in csv.DictReader(f):
                pid = (r.get("project_id") or "").strip()
                if pid:
                    idx[pid] = {
                        "folder": (r.get("folder_location") or "").strip(),
                        "short": (r.get("short_name") or "").strip(),
                        "owner": (r.get("owner") or "").strip(),
                    }
    return idx


def build_records(nas):
    """Return (records, projects_index).

    Each record is the full registry row plus a few derived helpers:
      _raw_path        share-relative canonical path (e.g. /raw/.../ACQ.../)
      _project_folder  share-relative project folder (or "")
      _project_short   project short_name (or "")
      _search          lower-cased blob for free-text matching
    Keeping the full row means the detail view / CLI can show any field.
    """
    nas = os.path.normpath(nas)
    proj_idx = _projects_index(nas)
    rows = registry.read_registry(os.path.join(nas, "registries", "registry_raw.csv"))
    records = []
    for r in rows:
        rec = dict(r)
        rec["_raw_path"] = (r.get("canonical_path") or "").strip()
        p = proj_idx.get((r.get("project_hint") or "").strip()) or {}
        rec["_project_folder"] = p.get("folder", "")
        rec["_project_short"] = p.get("short", "")
        rec["_search"] = " ".join(str(r.get(f, "")) for f in SEARCH_FIELDS).lower()
        records.append(rec)
    return records, proj_idx


def matches(rec, *, query="", instrument="", researcher="", subject="",
            anatomy="", project="", since="", until=""):
    """True if a record passes all supplied filters (all case-insensitive)."""
    if query and query.lower() not in rec["_search"]:
        return False
    if instrument and instrument.lower() != (rec.get("instrument") or "").lower():
        return False
    if researcher and researcher.lower() not in (rec.get("researcher") or "").lower():
        return False
    if subject and subject.lower() not in (rec.get("subject_ids") or "").lower() \
            and subject.lower() not in (rec.get("sample_id") or "").lower():
        return False
    if anatomy and anatomy.lower() not in (rec.get("anatomical_entity") or "").lower():
        return False
    if project and project.lower() not in (rec.get("project_hint") or "").lower():
        return False
    day = (rec.get("acquisition_datetime") or "")[:10]  # YYYY-MM-DD
    if since and day and day < since:
        return False
    if until and day and day > until:
        return False
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query", nargs="?", default="",
                    help="free-text (id / sample / subject / instrument / date / ...)")
    ap.add_argument("--nas-root", default=os.environ.get("GJESUS3_ROOT", "J:/gjesus3-data"))
    ap.add_argument("--instrument")
    ap.add_argument("--researcher")
    ap.add_argument("--subject")
    ap.add_argument("--anatomy")
    ap.add_argument("--project")
    ap.add_argument("--since", help="YYYY-MM-DD (acquisition date >=)")
    ap.add_argument("--until", help="YYYY-MM-DD (acquisition date <=)")
    ap.add_argument("--limit", type=int, default=50)
    args = ap.parse_args(argv)

    records, _ = build_records(args.nas_root)
    hits = [r for r in records if matches(
        r, query=args.query, instrument=args.instrument or "",
        researcher=args.researcher or "", subject=args.subject or "",
        anatomy=args.anatomy or "", project=args.project or "",
        since=args.since or "", until=args.until or "")]
    print(f"{len(hits)} of {len(records)} acquisitions match")
    for r in hits[:args.limit]:
        print(f"  {r.get('acq_id',''):28s} {(r.get('acquisition_datetime') or '')[:10]:11s} "
              f"{r.get('instrument',''):6s} {r.get('sample_id',''):18s} "
              f"{r.get('anatomical_entity',''):10s} {r.get('_raw_path','')}")
    if len(hits) > args.limit:
        print(f"  ... +{len(hits) - args.limit} more (raise --limit)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
