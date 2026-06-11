"""ACQ-ID generation: ACQ-YYYYMMDD-INST-SEQ."""

import json
import os

from . import registry


# A per-prefix high-water reservation, written under the registry lock by
# allocate_acq_id(). Lives in registries/ so a purge of that directory resets
# the high-water marks (true-production restart begins at 001). Dot-prefixed
# so registry tooling that globs *.csv ignores it.
RESERVATIONS_FILENAME = ".acq_id_seq.json"


def _validate_date(date_str):
    if len(date_str) != 8 or not date_str.isdigit():
        raise ValueError(f"date_str must be YYYYMMDD, got: {date_str}")


def _max_seq_in_registry(registry_path, prefix):
    """Highest committed sequence number for `prefix` in the registry (0 if none)."""
    max_seq = 0
    for row in registry.read_registry(registry_path):
        acq_id = row.get("acq_id", "")
        if acq_id.startswith(prefix):
            try:
                max_seq = max(max_seq, int(acq_id.split("-")[-1]))
            except ValueError:
                continue
    return max_seq


def generate_acq_id(date_str, instrument, registry_path):
    """Generate the next ACQ-ID for a date+instrument from the registry alone.

    Registry-only (no reservation side effect). Used for dry-run previews and
    by callers that already serialize themselves. Concurrent live ingests must
    use allocate_acq_id() under locking.registry_lock so the id can't be
    re-minted during the file copy that precedes the registry append.

    Args:
        date_str: Date in YYYYMMDD format (e.g., "20260215").
        instrument: Instrument code (e.g., "XMRI").
        registry_path: Path to registry_raw.csv.

    Returns:
        ACQ-ID string, e.g. "ACQ-20260215-XMRI-001".
    """
    _validate_date(date_str)
    prefix = f"ACQ-{date_str}-{instrument}-"
    return f"{prefix}{_max_seq_in_registry(registry_path, prefix) + 1:03d}"


def _reservations_path(registries_dir):
    return os.path.join(registries_dir, RESERVATIONS_FILENAME)


def _read_reservations(registries_dir):
    """Read the reservation map {prefix: high_water_seq}; {} if absent/corrupt."""
    try:
        with open(_reservations_path(registries_dir), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, ValueError, OSError):
        return {}


def _write_reservations(registries_dir, data):
    """Atomically replace the reservation map (write temp, os.replace)."""
    path = _reservations_path(registries_dir)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def allocate_acq_id(date_str, instrument, registry_path, registries_dir):
    """Allocate the next ACQ-ID AND persist a high-water reservation.

    MUST be called while holding locking.registry_lock(registries_dir). The
    reservation file (.acq_id_seq.json) records the highest seq handed out per
    ACQ-<date>-<instrument> prefix, so a concurrent ingest whose registry row
    isn't written yet (it's still copying files) cannot re-mint the same id.
    The next id is max(committed registry rows, reservation high-water) + 1.

    A failed ingest leaves its reserved seq unused — ids are never reused, a
    deliberate and harmless gap. Purging registries/ (which removes this file)
    resets the high-water marks so a true-production restart begins at 001.
    """
    _validate_date(date_str)
    prefix = f"ACQ-{date_str}-{instrument}-"
    reg_max = _max_seq_in_registry(registry_path, prefix)
    reservations = _read_reservations(registries_dir)
    try:
        res_max = int(reservations.get(prefix, 0))
    except (TypeError, ValueError):
        res_max = 0
    next_seq = max(reg_max, res_max) + 1
    reservations[prefix] = next_seq
    _write_reservations(registries_dir, reservations)
    return f"{prefix}{next_seq:03d}"


def parse_date_for_path(date_str):
    """Convert YYYYMMDD to (YYYY, YYYY-MM) for folder structure.

    Returns:
        Tuple of (year_str, year_month_str).
    """
    year = date_str[:4]
    month = date_str[4:6]
    return year, f"{year}-{month}"
