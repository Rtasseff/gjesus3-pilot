#!/usr/bin/env python3
"""One-shot migration: bring an existing registry_raw.csv up to the current
REGISTRY_FIELDS column layout.

Generic — it auto-detects whichever columns REGISTRY_FIELDS in
tools/ingest/registry.py has gained since the file was written and inserts them
at their canonical positions. (Past additions: session_id + primary_kind on
2026-05-20; subject_id on 2026-06-11. Rename: subject_id -> subject_ids on
2026-06-12, NI-LIVE-08.) Run it once after REGISTRY_FIELDS changes; the
defensive header check in `append_row()` refuses to write until the on-disk
header matches.

Approach:
  1. Read the existing CSV (any header layout; BOM-tolerant).
  2. Apply known column RENAMES (COLUMN_RENAMES) to the on-disk header first, so
     a renamed column's DATA carries over to its new name (not dropped).
  3. Re-emit each row in the canonical REGISTRY_FIELDS order, padding new
     columns with empty strings (matched by column NAME, so reordering and
     insertion are both handled). Aborts if, after renames, the file still has
     columns NOT in the target schema (an unknown rename/removal needs a human).
  4. Backup the original to <path>.bak.<timestamp> before overwriting.

Usage:
    python tools/migrate_registry_columns.py [--registry <path>] [--dry-run]

Defaults to the registry under GJESUS3_ROOT or /mnt/gjesus3. Run with --dry-run
first; verify the first-row preview; then run live.
"""

import argparse
import csv
import os
import shutil
import sys
from datetime import datetime

# Add tools/ to path for sibling import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ingest.registry import REGISTRY_FIELDS  # noqa: E402

# Known column renames (old on-disk name -> new schema name). A pure rename
# preserves the column's DATA under the new name; without this map the generic
# add/drop logic below would treat the old name as an "extra" column, abort, and
# (if forced) drop its data. Add an entry whenever a REGISTRY_FIELDS column is
# renamed rather than added.
COLUMN_RENAMES = {
    "subject_id": "subject_ids",   # 2026-06-12, NI-LIVE-08 — singular -> packed list
}


def migrate(registry_path, dry_run=False):
    """Migrate the registry CSV to the current REGISTRY_FIELDS layout."""
    if not os.path.isfile(registry_path):
        print(f"ERROR: registry not found: {registry_path}")
        return 1

    # utf-8-sig: tolerate an Excel BOM on the existing header (matches the
    # BOM-tolerant readers in ingest/csv_safe.py).
    with open(registry_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        print("ERROR: registry is empty")
        return 1

    raw_header = rows[0]
    data_rows = rows[1:]

    # Apply known renames to the on-disk header FIRST so a renamed column's data
    # carries over to its new name (zip(existing_header, row) below keys on this).
    existing_header = [COLUMN_RENAMES.get(c, c) for c in raw_header]
    applied_renames = {o: COLUMN_RENAMES[o] for o in raw_header if o in COLUMN_RENAMES}
    if applied_renames:
        print(f"Applying column renames: {applied_renames}")

    if existing_header == REGISTRY_FIELDS and not applied_renames:
        print(
            f"Registry already at current schema "
            f"({len(REGISTRY_FIELDS)} columns); no migration needed."
        )
        return 0

    missing_cols = [c for c in REGISTRY_FIELDS if c not in existing_header]
    extra_cols = [c for c in existing_header if c not in REGISTRY_FIELDS]
    print(f"Existing header: {len(existing_header)} columns")
    print(f"Target header:   {len(REGISTRY_FIELDS)} columns")
    print(f"Columns to add:  {missing_cols}")
    if extra_cols:
        print(
            f"REFUSING to migrate — existing columns not in target schema: "
            f"{extra_cols}. Aborting (nothing written); reconcile these "
            f"columns first, then re-run."
        )
        return 2

    # Build a per-row dict view of existing data, then re-emit with the
    # new field order. Missing values become empty strings.
    migrated = []
    for row in data_rows:
        # Pad / truncate to existing_header length
        padded = list(row) + [""] * max(0, len(existing_header) - len(row))
        padded = padded[: len(existing_header)]
        row_dict = dict(zip(existing_header, padded))
        new_row = [row_dict.get(field, "") for field in REGISTRY_FIELDS]
        migrated.append(new_row)

    print(f"\nMigrating {len(migrated)} data rows...")

    if dry_run:
        print("[DRY RUN] Would write new header + migrated rows. Skipping.")
        # Show first migrated row alongside its source for confidence
        if migrated:
            print("\nFirst row preview:")
            for col, val in zip(REGISTRY_FIELDS, migrated[0]):
                print(f"  {col}: {val!r}")
        return 0

    # Backup
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = f"{registry_path}.bak.{ts}"
    shutil.copy2(registry_path, backup)
    print(f"Backed up original to: {backup}")

    # Write new CSV
    with open(registry_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(REGISTRY_FIELDS)
        writer.writerows(migrated)
    print(f"Wrote migrated registry: {registry_path}")
    print(f"  {len(REGISTRY_FIELDS)} columns x {len(migrated)} rows")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    default_root = os.environ.get("GJESUS3_ROOT", "/mnt/gjesus3")
    ap.add_argument(
        "--registry",
        default=os.path.join(default_root, "registries", "registry_raw.csv"),
        help="Path to registry_raw.csv (default: $GJESUS3_ROOT/registries/registry_raw.csv)",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    return migrate(args.registry, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
