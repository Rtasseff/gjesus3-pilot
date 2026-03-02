"""Create links / manifests for project folder references.

Supports multiple linking methods (deferred until NAS testing):
- manifest: CSV text file mapping names to paths (always generated)
- symlink: filesystem symlink (needs Samba config testing)
- lnk: Windows .lnk shortcut (needs pylnk3)
"""

import csv
import os


def create_manifest_entry(manifest_path, acq_id, original_name, canonical_path):
    """Append an entry to a text manifest CSV.

    The manifest tracks the mapping from original source names
    to ingested ACQ-IDs and paths.
    """
    file_exists = os.path.exists(manifest_path)

    fieldnames = ["acq_id", "original_name", "canonical_path"]
    with open(manifest_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "acq_id": acq_id,
            "original_name": original_name,
            "canonical_path": canonical_path,
        })
