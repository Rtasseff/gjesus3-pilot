#!/usr/bin/env python3
"""ingest_raw.py — Ingest raw data from staging into the structured raw area.

Usage:
    python ingest_raw.py --config batch.yaml --dry-run   # preview
    python ingest_raw.py --config batch.yaml              # execute
    python ingest_raw.py --interactive                     # single case

See 10_TOOLS.md and 03_RAW_STORAGE.md for full specification.
"""

import argparse
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from ingest import config, acq_id, checksum, registry, readme, dicom_utils, linker

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


def log(msg, level="INFO"):
    """Print a timestamped log message."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {level}: {msg}")


def copy_files(src_dir, dst_dir):
    """Copy all files from src_dir into dst_dir, preserving subdirectory structure.

    Returns number of files copied.
    """
    count = 0
    all_files = []
    for root, _dirs, files in os.walk(src_dir):
        for fname in files:
            src_path = os.path.join(root, fname)
            rel = os.path.relpath(src_path, src_dir)
            all_files.append((src_path, rel))

    if HAS_TQDM:
        iterator = tqdm(all_files, desc="Copying", unit="file")
    else:
        iterator = all_files

    for src_path, rel in iterator:
        dst_path = os.path.join(dst_dir, rel)
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        shutil.copy2(src_path, dst_path)
        count += 1

    return count


def ingest_single(cfg_single, nas_root, dry_run=False):
    """Run the ingestion workflow for a single acquisition.

    Args:
        cfg_single: Validated single-case config dict.
        nas_root: Path to NAS root (e.g., /mnt/gjesus3).
        dry_run: If True, print what would happen without doing it.

    Returns:
        Tuple of (acq_id_str, success_bool).
    """
    source_path = cfg_single["source_path"]
    original_name = cfg_single.get("original_name", Path(source_path).name)
    cfg_single["original_name"] = original_name

    # --- Step 1: Analyze source ---
    log(f"Analyzing: {source_path}")

    # Determine if this is DICOM data
    is_dicom = cfg_single.get("data_ecosystem", "").upper() == "DICOM"
    instrument = cfg_single.get("instrument", "auto")

    if is_dicom or instrument in ("auto",) or instrument.startswith("X"):
        summary = dicom_utils.summarize_source(source_path)
    else:
        # Non-DICOM: simple file inventory
        file_count = 0
        total_size = 0
        for root, _dirs, files in os.walk(source_path):
            for fname in files:
                fpath = os.path.join(root, fname)
                file_count += 1
                total_size += os.path.getsize(fpath)
        summary = {
            "file_count": file_count,
            "total_size_mb": round(total_size / (1024 * 1024), 1),
            "modality": None,
            "study_date": None,
        }

    # --- Step 2: Resolve instrument code ---
    if instrument == "auto":
        dicom_mod = summary.get("modality")
        if dicom_mod and dicom_mod in config.DICOM_MODALITY_TO_CODE:
            instrument = config.DICOM_MODALITY_TO_CODE[dicom_mod]
            log(f"Auto-detected instrument: {instrument} (DICOM Modality={dicom_mod})")
        else:
            log(f"Cannot auto-detect instrument. DICOM Modality={dicom_mod}", "ERROR")
            return None, False
        cfg_single["instrument"] = instrument

    # Validate / confirm instrument matches DICOM
    if is_dicom and summary.get("modality"):
        expected_code = config.DICOM_MODALITY_TO_CODE.get(summary["modality"])
        if expected_code and expected_code != instrument:
            log(
                f"WARNING: DICOM Modality={summary['modality']} suggests "
                f"{expected_code}, but config says {instrument}",
                "WARN",
            )

    # Resolve ecosystem
    data_ecosystem = config.resolve_ecosystem(instrument)
    cfg_single["data_ecosystem"] = data_ecosystem

    # --- Step 3: Resolve acquisition date ---
    acq_date = cfg_single.get("acquisition_date", "auto")
    if acq_date == "auto":
        study_date = summary.get("study_date")
        if study_date:
            acq_date = study_date
            log(f"Using StudyDate from DICOM: {acq_date}")
        else:
            acq_date = datetime.now(timezone.utc).strftime("%Y%m%d")
            log(f"No StudyDate found, using today: {acq_date}", "WARN")
    elif len(acq_date) == 10 and "-" in acq_date:
        # Convert YYYY-MM-DD to YYYYMMDD
        acq_date = acq_date.replace("-", "")

    cfg_single["acquisition_date"] = acq_date

    # --- Step 4: Generate ACQ-ID ---
    registry_path = os.path.join(nas_root, "registries", "registry_raw.csv")
    acq_id_str = acq_id.generate_acq_id(acq_date, instrument, registry_path)
    log(f"Generated ACQ-ID: {acq_id_str}")

    # --- Step 5: Determine destination path ---
    year_str, month_str = acq_id.parse_date_for_path(acq_date)
    dest_dir = os.path.join(
        nas_root, "raw", data_ecosystem,
        year_str, month_str, acq_id_str,
    )
    # For DICOM, files go inside series/ subfolder
    if data_ecosystem == "DICOM":
        copy_dest = os.path.join(dest_dir, "series")
        cfg_single["primary_file_name"] = "series/"
        cfg_single["file_format"] = ".dcm"
    else:
        copy_dest = dest_dir

    canonical_path = f"/raw/{data_ecosystem}/{year_str}/{month_str}/{acq_id_str}/"

    # --- Summary ---
    log(f"  Source:      {source_path}")
    log(f"  Original:    {original_name}")
    log(f"  Instrument:  {instrument}")
    log(f"  Ecosystem:   {data_ecosystem}")
    log(f"  Acq Date:    {acq_date}")
    log(f"  Files:       {summary['file_count']}")
    log(f"  Size (MB):   {summary['total_size_mb']}")
    log(f"  Destination: {dest_dir}")
    if summary.get("modality"):
        log(f"  DICOM Mod:   {summary['modality']}")

    if dry_run:
        log("[DRY RUN] Would create folder and copy files. Skipping.")
        return acq_id_str, True

    # --- Step 6: Create folder + copy ---
    os.makedirs(copy_dest, exist_ok=True)
    log("Copying files...")
    n_copied = copy_files(source_path, copy_dest)
    log(f"Copied {n_copied} files")

    # --- Step 7: Generate checksums ---
    log("Computing checksums on destination...")
    if HAS_TQDM:
        pbar = tqdm(total=0, desc="Checksums", unit="file")
        def cb(rel, i, total):
            pbar.total = total
            pbar.update(1)
        dest_checksums = checksum.compute_checksums(dest_dir, progress_callback=cb)
        pbar.close()
    else:
        dest_checksums = checksum.compute_checksums(dest_dir)

    checksum_path = os.path.join(dest_dir, "checksums.json")
    checksum.write_checksums(dest_checksums, checksum_path)
    log(f"Wrote checksums.json ({len(dest_checksums)} files)")

    # --- Step 8: Verify copy ---
    log("Verifying copy integrity...")
    ok, mismatches = checksum.verify_checksums(source_path, copy_dest)
    if ok:
        log("Verification PASSED — all files match")
    else:
        log(f"Verification FAILED — {len(mismatches)} mismatches:", "ERROR")
        for m in mismatches[:10]:
            log(f"  {m}", "ERROR")
        return acq_id_str, False

    # --- Step 9: Generate README ---
    readme.generate_readme(acq_id_str, cfg_single, summary, dest_dir)
    log("Wrote README.txt")

    # --- Step 10: Update registry ---
    reg_dt = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    row = registry.build_row(acq_id_str, cfg_single, summary, canonical_path, reg_dt)
    registry.append_row(registry_path, row)
    log(f"Appended to registry: {registry_path}")

    # --- Step 11: Manifest entry (always) ---
    manifest_path = os.path.join(nas_root, "registries", "ingest_manifest.csv")
    linker.create_manifest_entry(manifest_path, acq_id_str, original_name, canonical_path)

    log(f"DONE: {acq_id_str}")
    return acq_id_str, True


def run_batch(cfg, nas_root, dry_run=False):
    """Run batch ingestion from a batch config.

    Returns list of (acq_id, success) tuples.
    """
    cases = config.expand_batch(cfg)
    log(f"Batch: {len(cases)} cases discovered")

    results = []
    for i, case in enumerate(cases):
        log(f"\n{'='*60}")
        log(f"Case {i+1}/{len(cases)}: {case.get('source_path', '?')}")
        log(f"{'='*60}")

        errors = config.validate_single(case)
        if errors:
            for e in errors:
                log(e, "ERROR")
            results.append((None, False))
            continue

        acq_id_str, ok = ingest_single(case, nas_root, dry_run=dry_run)
        results.append((acq_id_str, ok))

    # --- Summary ---
    print(f"\n{'='*60}")
    print("BATCH SUMMARY")
    print(f"{'='*60}")
    n_ok = sum(1 for _, ok in results if ok)
    n_fail = sum(1 for _, ok in results if not ok)
    print(f"  Total:    {len(results)}")
    print(f"  Success:  {n_ok}")
    print(f"  Failed:   {n_fail}")
    if n_fail > 0:
        print("  Failed cases:")
        for i, (aid, ok) in enumerate(results):
            if not ok:
                print(f"    Case {i+1}: {cases[i].get('source_path', '?')}")
    print()
    return results


def run_interactive(nas_root, dry_run=False):
    """Interactive mode for single-case ingestion."""
    print("=== Interactive Raw Data Ingestion ===\n")

    cfg_single = {}
    cfg_single["source_path"] = input("Source path (staging folder): ").strip()
    cfg_single["instrument"] = input(
        "Instrument code (e.g., XMRI, ZWSI, or 'auto'): "
    ).strip()
    cfg_single["operator"] = input("Operator (initials): ").strip()
    cfg_single["data_source"] = input(
        "Data source (e.g., 'internal' or 'collaborator:NAME'): "
    ).strip()
    cfg_single["acquisition_date"] = input(
        "Acquisition date (YYYYMMDD or 'auto' for DICOM): "
    ).strip() or "auto"
    cfg_single["sample_id"] = input("Sample ID (optional): ").strip()
    cfg_single["sample_type"] = input("Sample type (optional): ").strip()
    cfg_single["notes"] = input("Notes (optional): ").strip()

    # Determine ecosystem
    inst = cfg_single["instrument"]
    if inst != "auto":
        cfg_single["data_ecosystem"] = config.resolve_ecosystem(inst)

    errors = config.validate_single(cfg_single)
    if errors:
        for e in errors:
            log(e, "ERROR")
        sys.exit(1)

    acq_id_str, ok = ingest_single(cfg_single, nas_root, dry_run=dry_run)
    if not ok:
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Ingest raw data from staging to structured raw area.",
        epilog="See 10_TOOLS.md for full documentation.",
    )
    parser.add_argument(
        "--config", "-c",
        help="Path to YAML config file (single or batch)",
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode (single case)",
    )
    parser.add_argument(
        "--nas-root",
        default=os.environ.get("GJESUS3_ROOT", "/mnt/gjesus3"),
        help="Path to NAS root (default: $GJESUS3_ROOT or /mnt/gjesus3)",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Preview what would happen without making changes",
    )
    parser.add_argument(
        "--project",
        help="Project ID to link acquisitions to (future use)",
    )

    args = parser.parse_args()

    if not args.config and not args.interactive:
        parser.error("Must specify --config or --interactive")

    nas_root = args.nas_root
    log(f"NAS root: {nas_root}")

    if args.dry_run:
        log("*** DRY RUN MODE — no changes will be made ***")

    if args.interactive:
        run_interactive(nas_root, dry_run=args.dry_run)
    else:
        cfg = config.load_config(args.config)
        if config.is_batch_config(cfg):
            run_batch(cfg, nas_root, dry_run=args.dry_run)
        else:
            # Single-case config
            errors = config.validate_single(cfg)
            if errors:
                for e in errors:
                    log(e, "ERROR")
                sys.exit(1)
            _, ok = ingest_single(cfg, nas_root, dry_run=args.dry_run)
            if not ok:
                sys.exit(1)


if __name__ == "__main__":
    main()
