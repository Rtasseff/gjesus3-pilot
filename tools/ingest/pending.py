"""pending.py — the deferred-recovery pending list for subject metadata.

When a live ingest can't resolve an animal in the animal-facility DB (the DB
lags the acquisition, or the operator machine has no credentials), the
acquisition still lands in /raw/ with a placeholder `subject:` block
(source="pending-db") and a row is queued here for a superuser to recover
later (08_METADATA §4.4.6). The file lives in `registries/` — operators have
Modify there but only write-once on `raw/` (permission model,
11_OPERATIONS §2.1.1).

Idempotent on `acq_id`: re-ingesting the same acquisition updates its row
rather than duplicating it. Defensive header check mirrors
`registry.append_row` — refuses to write into a file whose columns don't match.
"""

import csv
import os
from datetime import datetime, timezone

from . import csv_safe, locking


PENDING_FILENAME = "pending_subject_metadata.csv"

# Column order is the contract (08_METADATA §4.4.6.2). When it changes, the
# defensive header check below refuses to write until the CSV is migrated.
PENDING_FIELDS = [
    "acq_id",
    "sidecar_path",
    "facility_animal_id",
    "reason",          # "db-miss" | "no-credentials"
    "logged_at",       # ISO-8601 UTC of the ingest that logged the gap
    "status",          # "pending" | "recovered" | "unresolvable"
    "recovered_at",    # ISO-8601 UTC when a superuser resolved it (else "")
]


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def pending_path(registries_dir):
    """Absolute path of the pending list under a registries/ directory."""
    return os.path.join(registries_dir, PENDING_FILENAME)


def read_pending(path):
    """Read the pending list -> list of row dicts (empty if absent)."""
    if not os.path.exists(path):
        return []
    # utf-8-sig: BOM-tolerant (Excel round-trip), matching csv_safe.read_header.
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _assert_header(path):
    """Raise RuntimeError if an existing file's header != PENDING_FIELDS."""
    if not os.path.exists(path):
        return
    existing = csv_safe.read_header(path)  # BOM-tolerant
    if existing and existing != PENDING_FIELDS:
        raise RuntimeError(
            f"pending-list header mismatch in {path}\n"
            f"  file has {len(existing)} columns: {existing}\n"
            f"  code expects {len(PENDING_FIELDS)}: {PENDING_FIELDS}\n"
            f"  refusing to write (would corrupt column alignment)."
        )


def _write_all(path, rows):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    # Atomic temp+replace so a crash mid-write can never truncate the queue.
    # The previous truncate-in-place `open(path, "w")` left an empty/partial
    # file if the process died between truncate and full write — wiping the
    # ONLY record of which acquisitions still need subject-metadata recovery.
    # Mirrors pending_dicom._write_all / subjects_table.write_subjects. The
    # pid-suffixed temp keeps two processes (e.g. an ingest and the manual
    # recovery tool) from colliding on the same temp name.
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PENDING_FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in PENDING_FIELDS})
    os.replace(tmp, path)


def append_pending(registries_dir, acq_id, sidecar_path, facility_animal_id,
                   reason, logged_at=None, _hold_lock=True):
    """Queue (or refresh) an acquisition for subject-metadata recovery.

    Idempotent on `acq_id`: if a row already exists it is refreshed
    (sidecar_path / facility_animal_id / reason / logged_at) while its
    `status` and `recovered_at` are preserved — so a re-ingest never
    duplicates and never clobbers a row a superuser already marked
    `recovered`. New rows are written with status="pending", recovered_at="".

    The whole read-modify-write runs under ``locking.registry_lock`` (the same
    mutex the registry append uses), so two concurrent DB-miss ingests can't
    lost-update the queue (each would otherwise read the same rows and the
    second write would drop the first's addition). Pass ``_hold_lock=False``
    only from a caller that already holds the lock — it is not reentrant. The
    single ingest caller (enrichment.build_enrichment, ingest Step 8.4) runs
    before the Step 10 registry lock, so it self-locks with the default.

    Returns the absolute path written.
    """
    path = pending_path(registries_dir)
    logged_at = logged_at or _now_iso()

    def _do():
        _assert_header(path)
        rows = read_pending(path)
        by_id = {r.get("acq_id"): r for r in rows}
        if acq_id in by_id:
            r = by_id[acq_id]
            r["sidecar_path"] = sidecar_path
            r["facility_animal_id"] = facility_animal_id
            r["reason"] = reason
            r["logged_at"] = logged_at
            # status / recovered_at intentionally preserved.
        else:
            rows.append({
                "acq_id": acq_id,
                "sidecar_path": sidecar_path,
                "facility_animal_id": facility_animal_id,
                "reason": reason,
                "logged_at": logged_at,
                "status": "pending",
                "recovered_at": "",
            })
        _write_all(path, rows)
        return path

    if _hold_lock:
        with locking.registry_lock(registries_dir):
            return _do()
    return _do()
