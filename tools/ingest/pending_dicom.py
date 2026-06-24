"""Deferred DICOM-regeneration worklist for no-DICOM ParaVision MRI exams.

When an MRI exam arrives with NO DICOMs (the researcher skipped Bruker's GUI
exporter) AND Dicomifier isn't available at ingest time — the common case on an
operator's Windows box running the frozen GUI, where Dicomifier (a WSL/conda
tool) cannot run — the ingest files an empty `<ACQ-ID>.data/` placeholder with a
full `metadata.json` (from the JCAMP-DX) and queues the acquisition HERE. The
acquisition is registered and findable immediately; only the image pixels are
deferred.

A later data-office pass on a **Dicomifier-equipped Linux/WSL box** reads this
list and, for each row, **re-pulls the source exam from the platform host**
(`kenia` — the gjesus3 staging copy was already auto-deleted, and gjesus3 never
archived the raw `fid`/`2dseq` bytes; the platform IS the deep archive of those),
regenerates the DICOMs via `tools/ingest/paravision_regen.py`, and idempotently
re-ingests to fill the `.data/`.

WHY `original_name`, not a staging path: the staging dir (`<NAS>/staging/<batch>/
<study>`) is auto-deleted after a clean ingest, so it is useless for recovery.
`original_name` is the ParaVision `<study>/<exam>` identity — the study folder
name is the same on `kenia`, so the regen pass FINDS it by name on the PV root
matching the sidecar's `paravision_version` (PV 7.0.0 → `/opt/PV-7.0.0/data/nmr`,
PV 6.0.1 → `/opt/PV6.0.1/data/nmr`; search both if unsure — study names are
unique, timestamp-prefixed).

Mirrors `tools/ingest/pending.py` (the `pending_subject_metadata.csv` pattern):
BOM-tolerant, header-checked, read-all/write-all, idempotent on `acq_id`.
"""

import csv
import os
from datetime import datetime

from . import csv_safe

PENDING_DICOM_FILENAME = "pending_dicom_regen.csv"

# Keep in sync with the columns written below + the defensive header check.
PENDING_DICOM_FIELDS = [
    "acq_id",             # the registered acquisition (regen fills its .data/)
    "original_name",      # <study>/<exam> — the kenia source identity
    "reconstructions",    # the recon selection from the ingest config (all|int|list)
    "canonical_path",     # the empty <ACQ-ID>.data/ on the NAS (regen target)
    "paravision_version", # picks the PV root on kenia to re-pull from
    "ingest_config",      # which config produced the placeholder
    "queued_datetime",
    "status",             # "pending" | (data office sets "regenerated")
]


def _now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def pending_dicom_path(registries_dir):
    return os.path.join(registries_dir, PENDING_DICOM_FILENAME)


def read_pending_dicom(path):
    """Rows of the worklist, or [] if it doesn't exist (BOM-tolerant)."""
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _assert_header(path):
    """Raise if an existing file's header != PENDING_DICOM_FIELDS."""
    if not os.path.isfile(path):
        return
    existing = csv_safe.read_header(path)  # BOM-tolerant
    if existing and existing != PENDING_DICOM_FIELDS:
        raise RuntimeError(
            f"{PENDING_DICOM_FILENAME} header mismatch:\n"
            f"  file has {len(existing)}: {existing}\n"
            f"  code expects {len(PENDING_DICOM_FIELDS)}: {PENDING_DICOM_FIELDS}\n"
            "Migrate the file before ingesting."
        )


def _write_all(path, rows):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    # Atomic temp+replace so a crash mid-write never truncates the worklist.
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PENDING_DICOM_FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in PENDING_DICOM_FIELDS})
    os.replace(tmp, path)


def append_pending_dicom(registries_dir, acq_id, original_name, reconstructions,
                         canonical_path, paravision_version="", ingest_config="",
                         queued_at=None):
    """Queue (or refresh) a no-DICOM MRI acquisition for later regeneration.

    Idempotent on `acq_id`: a re-ingest refreshes the source/target fields but
    preserves `status` (so a row the data office already marked "regenerated"
    is never reset to "pending"). New rows get status="pending".

    Returns the absolute path written.
    """
    path = pending_dicom_path(registries_dir)
    _assert_header(path)
    rows = read_pending_dicom(path)
    queued_at = queued_at or _now_iso()

    by_id = {r.get("acq_id"): r for r in rows}
    if acq_id in by_id:
        r = by_id[acq_id]
        r["original_name"] = original_name
        r["reconstructions"] = reconstructions
        r["canonical_path"] = canonical_path
        r["paravision_version"] = paravision_version
        r["ingest_config"] = ingest_config
        r["queued_datetime"] = queued_at
        # status intentionally preserved.
    else:
        rows.append({
            "acq_id": acq_id,
            "original_name": original_name,
            "reconstructions": reconstructions,
            "canonical_path": canonical_path,
            "paravision_version": paravision_version,
            "ingest_config": ingest_config,
            "queued_datetime": queued_at,
            "status": "pending",
        })

    _write_all(path, rows)
    return path
