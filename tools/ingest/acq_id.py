"""ACQ-ID generation: ACQ-YYYYMMDD-INST-SEQ."""

from . import registry


def generate_acq_id(date_str, instrument, registry_path):
    """Generate the next ACQ-ID for a given date and instrument.

    Args:
        date_str: Date in YYYYMMDD format (e.g., "20260215").
        instrument: Instrument code (e.g., "XMRI").
        registry_path: Path to registry_raw.csv.

    Returns:
        ACQ-ID string, e.g. "ACQ-20260215-XMRI-001".
    """
    # Validate date format
    if len(date_str) != 8 or not date_str.isdigit():
        raise ValueError(f"date_str must be YYYYMMDD, got: {date_str}")

    prefix = f"ACQ-{date_str}-{instrument}-"

    # Find highest existing sequence for this prefix
    existing = registry.read_registry(registry_path)
    max_seq = 0
    for row in existing:
        acq_id = row.get("acq_id", "")
        if acq_id.startswith(prefix):
            try:
                seq = int(acq_id.split("-")[-1])
                max_seq = max(max_seq, seq)
            except ValueError:
                continue

    next_seq = max_seq + 1
    return f"{prefix}{next_seq:03d}"


def parse_date_for_path(date_str):
    """Convert YYYYMMDD to (YYYY, YYYY-MM) for folder structure.

    Returns:
        Tuple of (year_str, year_month_str).
    """
    year = date_str[:4]
    month = date_str[4:6]
    return year, f"{year}-{month}"
