"""Deferred-fill worklist for NI acquisitions registered before their DICOMs exist.

Molecubes reconstruction lags acquisition: a scan runs, the session folder and its
`recon_<idx>/` dirs are created, and the operator often syncs **before** reconstruction
has produced any DICOMs (NI recon can take far longer than the scan). With one
acquisition per reconstruction (the registry granularity, NI live), such a recon is
registered as a **placeholder** — a real registry row + `metadata.json` (the
acquisition/subject parse is already knowable from `protocol.txt`) + an empty
`<ACQ-ID>.data/` (`file_count=0`) — and queued HERE. The acquisition is findable
immediately; only the image pixels are deferred.

A later sync (the normal `ingest_raw` walk, or a dedicated fill pass) reads this list
and, for each row, **re-finds the recon at its original box path and fills the empty
`.data/`** — then flips `status` to `filled`. Unlike the MRI no-DICOM case
(`pending_dicom.py`), the NI box source is **never deleted** (`delete_source_after_
ingest: false`), so there is nothing to re-pull: `original_name` (`<anchor>/recon_<idx>`)
locates the recon directly on the box.

Mirrors `tools/ingest/pending_dicom.py` / `pending_links.py`: BOM-tolerant, header-
checked, read-all/write-all atomically, idempotent on `acq_id` (status preserved).
"""

import csv
import os
from datetime import datetime

from . import csv_safe

PENDING_NI_RECON_FILENAME = "pending_ni_recon.csv"

# Keep in sync with the columns written below + the defensive header check.
PENDING_NI_RECON_FIELDS = [
    "acq_id",           # the placeholder acquisition (fill its .data/)
    "original_name",    # <anchor-relpath>/recon_<idx> — the box source identity
    "recon_index",      # which recon_<idx> this acquisition represents
    "session_id",       # groups the visit's recons/modalities (for human triage)
    "canonical_path",   # the empty <ACQ-ID>.data/ on the NAS (fill target)
    "ingest_config",    # which config produced the placeholder
    "queued_datetime",
    "status",           # "pending" | (fill pass sets "filled")
]


def _now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def pending_ni_recon_path(registries_dir):
    return os.path.join(registries_dir, PENDING_NI_RECON_FILENAME)


def read_pending_ni_recon(path):
    """Rows of the worklist, or [] if it doesn't exist (BOM-tolerant)."""
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _assert_header(path):
    """Raise if an existing file's header != PENDING_NI_RECON_FIELDS."""
    if not os.path.isfile(path):
        return
    existing = csv_safe.read_header(path)  # BOM-tolerant
    if existing and existing != PENDING_NI_RECON_FIELDS:
        raise RuntimeError(
            f"{PENDING_NI_RECON_FILENAME} header mismatch:\n"
            f"  file has {len(existing)}: {existing}\n"
            f"  code expects {len(PENDING_NI_RECON_FIELDS)}: {PENDING_NI_RECON_FIELDS}\n"
            "Migrate the file before ingesting."
        )


def _write_all(path, rows):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    # Atomic temp+replace so a crash mid-write never truncates the worklist.
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PENDING_NI_RECON_FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in PENDING_NI_RECON_FIELDS})
    os.replace(tmp, path)


def append_pending_ni_recon(registries_dir, acq_id, original_name, recon_index,
                            canonical_path, session_id="", ingest_config="",
                            queued_at=None):
    """Queue (or refresh) a no-DICOM-yet NI recon placeholder for later fill.

    Idempotent on `acq_id`: a re-ingest refreshes the source/target fields but preserves
    `status` (a row the fill pass already marked "filled" is never reset to "pending").
    New rows get status="pending".

    Returns the absolute path written.
    """
    path = pending_ni_recon_path(registries_dir)
    _assert_header(path)
    rows = read_pending_ni_recon(path)
    queued_at = queued_at or _now_iso()

    by_id = {r.get("acq_id"): r for r in rows}
    if acq_id in by_id:
        r = by_id[acq_id]
        r["original_name"] = original_name
        r["recon_index"] = recon_index
        r["session_id"] = session_id
        r["canonical_path"] = canonical_path
        r["ingest_config"] = ingest_config
        r["queued_datetime"] = queued_at
        # status intentionally preserved.
    else:
        rows.append({
            "acq_id": acq_id,
            "original_name": original_name,
            "recon_index": recon_index,
            "session_id": session_id,
            "canonical_path": canonical_path,
            "ingest_config": ingest_config,
            "queued_datetime": queued_at,
            "status": "pending",
        })

    _write_all(path, rows)
    return path


def mark_filled(registries_dir, acq_id):
    """Flip a row's status to 'filled' once its `.data/` has been populated.

    Returns True if the row existed and was updated, False otherwise.
    """
    path = pending_ni_recon_path(registries_dir)
    rows = read_pending_ni_recon(path)
    hit = False
    for r in rows:
        if r.get("acq_id") == acq_id:
            r["status"] = "filled"
            hit = True
    if hit:
        _write_all(path, rows)
    return hit
