"""SHA-256 checksum generation and verification."""

import hashlib
import json
import os
from datetime import datetime, timezone


CHUNK_SIZE = 65536  # 64 KB read chunks


def sha256_file(filepath):
    """Compute SHA-256 hash of a file. Returns hex digest string."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def compute_checksums(directory, progress_callback=None):
    """Compute SHA-256 checksums for all files in directory.

    Args:
        directory: Root directory to checksum.
        progress_callback: Optional callable(filepath, index, total).

    Returns:
        Dict mapping relative file paths to hex digests.
    """
    all_files = []
    for root, _dirs, files in os.walk(directory):
        for fname in sorted(files):
            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, directory)
            all_files.append((rel, fpath))

    checksums = {}
    for i, (rel, fpath) in enumerate(all_files):
        if progress_callback:
            progress_callback(rel, i, len(all_files))
        checksums[rel] = sha256_file(fpath)

    return checksums


def write_checksums(checksums, output_path):
    """Write checksums dict to a checksums.json file.

    Format matches the spec in 03_RAW_STORAGE.md.
    """
    payload = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "algorithm": "sha256",
        "files": checksums,
    }
    with open(output_path, "w") as f:
        json.dump(payload, f, indent=2)


def verify_checksums(source_dir, dest_dir, progress_callback=None):
    """Verify that files in dest_dir match source_dir by checksum.

    Computes checksums on source files and compares with dest files.

    Returns:
        Tuple of (ok: bool, mismatches: list of relative paths).
    """
    source_checksums = compute_checksums(source_dir, progress_callback)
    dest_checksums = compute_checksums(dest_dir)

    mismatches = []
    for rel, src_hash in source_checksums.items():
        dst_hash = dest_checksums.get(rel)
        if dst_hash != src_hash:
            mismatches.append(rel)

    # Check for extra files in dest (excluding checksums.json, README.txt)
    generated_files = {"checksums.json", "README.txt"}
    for rel in dest_checksums:
        if rel not in source_checksums and rel not in generated_files:
            mismatches.append(f"[extra in dest] {rel}")

    return len(mismatches) == 0, mismatches
