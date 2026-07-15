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
    "nonimage_marker",    # "" for a normal image exam; else the matched
                          # paravision_regen._NONIMAGE_METHOD_MARKERS entry
                          # (STEAM/PRESS/WOBBLE) — see the status note below
    "queued_datetime",
    "status",             # "pending" | "not-applicable" | (data office: "regenerated")
]

# `status` values:
#   pending         — a normal image exam awaiting a Dicomifier pass. THE drain set.
#   regenerated     — the data office filled its .data/. Set by hand; never reset.
#   not-applicable  — a spectroscopy/calibration exam (`nonimage_marker` says which).
#                     Image-DICOM regeneration does NOT apply: paravision_regen
#                     REFUSES these (is_nonimage_exam -> RuntimeError -> empty
#                     .data/ placeholder), so queuing them as "pending" would mean
#                     the worklist could never reach zero. They are still listed
#                     because they ARE DICOM-less acquisitions and must not become
#                     invisible — they are the input set for the separate
#                     spectroscopy ingest path (tasks/BACKLOG.md), and the marker
#                     matters there: WOBBLE is tuning, STEAM/PRESS are real
#                     spectroscopy data.
# So: drain `status == "pending"`; the worklist is done when none remain.


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
                         nonimage_marker="", queued_at=None):
    """Queue (or refresh) a no-DICOM MRI acquisition for later regeneration.

    `nonimage_marker` non-empty (a STEAM/PRESS/WOBBLE match from
    `paravision_regen.is_nonimage_exam`) means regeneration can never apply, so
    the row is filed "not-applicable" rather than "pending" — see the status
    notes above.

    Idempotent on `acq_id`: a re-ingest refreshes the source/target fields but
    preserves `status`, so a row the data office already marked "regenerated" is
    never reset. The one exception is a correction: a row still sitting "pending"
    that we now know is non-image is moved to "not-applicable" — leaving it
    pending would keep an undrainable row in the drain set.

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
        r["nonimage_marker"] = nonimage_marker
        r["queued_datetime"] = queued_at
        # status preserved — except the pending -> not-applicable correction.
        if nonimage_marker and r.get("status") == "pending":
            r["status"] = "not-applicable"
    else:
        rows.append({
            "acq_id": acq_id,
            "original_name": original_name,
            "reconstructions": reconstructions,
            "canonical_path": canonical_path,
            "paravision_version": paravision_version,
            "ingest_config": ingest_config,
            "nonimage_marker": nonimage_marker,
            "queued_datetime": queued_at,
            "status": "not-applicable" if nonimage_marker else "pending",
        })

    _write_all(path, rows)
    return path
