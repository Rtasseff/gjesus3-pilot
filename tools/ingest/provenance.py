"""provenance.py — append entries to a project's provenance.csv.

Owns the schema and the append contract documented in
mfb-rdm-docs/07_PROVENANCE.md so callers (ingest_raw.py, create_project.py,
future Excel-importer / close-out / log_activity tools) don't reinvent it.

Project-level provenance lives at <project_folder>/provenance.csv. Any
tool that adds, removes, or changes a file under /projects/<proj>/
should also update this file. The first such caller is the ingest
pipeline's Step 12: when it creates a .lnk shortcut to a raw acquisition,
it appends a provenance entry capturing what was made, from what, and how.
"""

import csv
import os
import subprocess


PROVENANCE_HEADERS = [
    "file_id",
    "output_path",
    "output_name",
    "file_type",
    "date_created",
    "creator",
    "input_refs",
    "process_description",
    "software_version",
    "parameters_ref",
    "lab_notebook_ref",
    "notes",
]


def _read_rows(prov_path):
    if not os.path.exists(prov_path):
        return []
    with open(prov_path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def next_file_id(prov_path):
    """Return the next FILE-NNNN id for this provenance.csv (zero-padded to 4)."""
    max_num = 0
    for r in _read_rows(prov_path):
        fid = r.get("file_id") or ""
        if fid.startswith("FILE-"):
            try:
                n = int(fid.split("-", 1)[1])
                if n > max_num:
                    max_num = n
            except (ValueError, IndexError):
                pass
    return f"FILE-{max_num + 1:04d}"


def has_entry_for_output(prov_path, output_path):
    """True if a row already exists with this output_path. Used for idempotency."""
    target = (output_path or "").strip()
    if not target:
        return False
    for r in _read_rows(prov_path):
        if (r.get("output_path") or "").strip() == target:
            return True
    return False


def append_entry(prov_path, entry):
    """Append a single row to provenance.csv.

    `entry` is a dict keyed by `PROVENANCE_HEADERS`. Missing keys land as
    empty strings; unknown keys are dropped. If `file_id` is empty, the
    next sequential FILE-NNNN is auto-assigned.

    Idempotent on `output_path`: if a row with the same `output_path`
    already exists, returns `None` without writing.

    Returns the FILE-ID actually written, or `None` if the call was a
    no-op.
    """
    entry = dict(entry)
    output_path = (entry.get("output_path") or "").strip()
    if output_path and has_entry_for_output(prov_path, output_path):
        return None

    if not entry.get("file_id"):
        entry["file_id"] = next_file_id(prov_path)

    file_exists = os.path.exists(prov_path) and os.path.getsize(prov_path) > 0
    os.makedirs(os.path.dirname(prov_path), exist_ok=True)
    with open(prov_path, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=PROVENANCE_HEADERS, extrasaction="ignore")
        if not file_exists:
            w.writeheader()
        full = {k: entry.get(k, "") for k in PROVENANCE_HEADERS}
        w.writerow(full)
    return entry["file_id"]


def write_empty(prov_path):
    """Write a fresh provenance.csv containing only the header row.

    Used by create_project.py at project setup. Safe to call on an
    existing empty file (idempotent header rewrite).
    """
    os.makedirs(os.path.dirname(prov_path), exist_ok=True)
    with open(prov_path, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow(PROVENANCE_HEADERS)


def software_version_string(script_name="ingest_raw.py"):
    """Short version string for the `software_version` field.

    Tries to include the repo's git short SHA for reproducibility; falls
    back to the script name + project marker if git isn't available
    (e.g. tarball install, no .git directory).
    """
    here = os.path.abspath(__file__)               # tools/ingest/provenance.py
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(here)))
    try:
        sha = subprocess.check_output(
            ["git", "-C", repo_root, "rev-parse", "--short", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        sha = ""
    base = f"{script_name} (gjesus3-pilot tools)"
    return f"{base} @ {sha}" if sha else base
