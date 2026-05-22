#!/usr/bin/env python3
"""extract_ni_archives.py — Extract Nuclear Imaging .tgz archives to staging.

Walks a Nuclear Imaging archive root (typically `\\cicmgsp02\gnuclear2$\<year>\<PI>\`),
finds every `.tgz`, and extracts each to its own folder under a local staging
directory. The 6-level outer nesting (`<user>/<series>/<date>/<short_project>_<short_sample>/<timestamp>_<modality>/<timestamp>_<modality>/...`)
is stripped so the staged folder contains the acquisition's actual files
(protocol.xml, acqparams.xml, recon_<idx>/, etc.) directly.

Parallel to `tools/ftp_mirror.py` in role: it's the fetch/extract step
the operator runs BEFORE `ingest_raw.py`. Decoupled from ingest — fetch
first, then point ingest at the local staging dir.

Background: Nuclear Imaging archives are stored as `.tgz` on a network
share that gjesus3 ingest can't write to. Extraction is also slow against
the live SMB read path + the nested structure makes glob patterns
awkward, so the cleaner path is "extract once locally with consistent
layout, then ingest from there." See `equipment/nuclear-imaging/internal_ni_data_handling_workflow_notes.md`
for the archive structure and the round-8 archive-mode design.

Usage:
    # Extract every .tgz under one PI's annual archive:
    python tools/extract_ni_archives.py \\
        --archive-root "//cicmgsp02/gnuclear2$/2025/Jesus/" \\
        --staging      "D:/projects/Nuke/test_data/"

    # Dry-run (list what would be extracted, touch nothing):
    python tools/extract_ni_archives.py \\
        --archive-root "//cicmgsp02/gnuclear2$/2025/Jesus/" \\
        --staging      "D:/projects/Nuke/test_data/" \\
        --dry-run

    # Limit to the first N archives (useful for piloting):
    python tools/extract_ni_archives.py \\
        --archive-root "//cicmgsp02/gnuclear2$/2025/Jesus/" \\
        --staging      "D:/projects/Nuke/test_data/" \\
        --limit 2

Idempotent: skips any archive whose staged folder already exists with a
sentinel `.extracted` marker. Use `--force` to re-extract.

The staged folder name is the archive basename without `.tgz` (e.g.
`irene_0525_251029_0525_m14_20251029100641_PET`). That basename is what
the round-8 ingest YAML regex parses to populate `discovered.user`,
`discovered.series_id`, `discovered.modality`, etc.
"""

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {level}: {msg}", flush=True)


def _retry(fn, attempts=5, initial_delay=2, what="SMB operation"):
    """Run fn() with up to `attempts` retries on OSError (covers WinError 59
    "unexpected network error" + other transient SMB issues observed on
    \\cicmgsp02\\gnuclear2$).

    Exponential backoff starting at `initial_delay` seconds.
    """
    delay = initial_delay
    last_err = None
    for i in range(1, attempts + 1):
        try:
            return fn()
        except OSError as e:
            last_err = e
            if i == attempts:
                raise
            log(
                f"{what} failed (attempt {i}/{attempts}): {e}. "
                f"Retrying in {delay}s...",
                "WARN",
            )
            time.sleep(delay)
            delay = min(delay * 2, 60)
    # Unreachable, but keep linter happy.
    raise last_err  # type: ignore


def find_tgz(archive_root):
    """Recursively find all .tgz files under archive_root.

    Returns sorted list of absolute paths. Sort makes the order
    deterministic across runs (helpful when extracting in batches
    via --limit). Retries on SMB transient errors.
    """
    def _walk():
        root = Path(archive_root)
        if not root.is_dir():
            raise SystemExit(f"Archive root is not a directory: {archive_root}")
        return sorted(root.rglob("*.tgz"))
    found = _retry(_walk, what=f"finding .tgz under {archive_root}")
    return [str(p) for p in found]


def is_already_extracted(staged_dir):
    """True if staged_dir exists and has the `.extracted` sentinel."""
    return os.path.isfile(os.path.join(staged_dir, ".extracted"))


def extract_one(tgz_path, staging_root, strip_components=6, dry_run=False):
    """Extract a single .tgz to staging_root/<basename>/.

    Strips `strip_components` levels of leading path components so the
    staged folder directly contains the acquisition's files (protocol.xml,
    recon_<idx>/, etc.) rather than the platform's 6-deep nested layout.

    Returns (staged_dir, status) where status is one of:
      - "extracted" (newly extracted this run)
      - "skipped"   (already extracted, idempotency hit)
      - "failed"    (extraction error; staged_dir may be partial)
    """
    basename = os.path.basename(tgz_path)
    if not basename.endswith(".tgz"):
        log(f"Skipping non-.tgz file: {basename}", "WARN")
        return None, "skipped"
    stem = basename[:-4]  # strip ".tgz"
    staged_dir = os.path.join(staging_root, stem)

    if is_already_extracted(staged_dir):
        return staged_dir, "skipped"

    if dry_run:
        log(f"  [DRY-RUN] Would extract {basename} -> {staged_dir}")
        return staged_dir, "extracted"

    os.makedirs(staged_dir, exist_ok=True)
    # `tar -xzf <tgz> --strip-components=N -C <dst>` extracts the
    # archive's contents with N leading path components stripped.
    # Universally available on Git Bash for Windows.
    cmd = [
        "tar", "-xzf", tgz_path,
        f"--strip-components={strip_components}",
        "-C", staged_dir,
    ]
    # Wrap the tar subprocess in retry logic — the SMB read of large
    # multi-GB archives is the most failure-prone step.
    attempts = 3
    delay = 5
    for attempt in range(1, attempts + 1):
        t0 = time.time()
        proc = subprocess.run(cmd, capture_output=True, text=True)
        elapsed = time.time() - t0
        if proc.returncode == 0:
            break
        if attempt < attempts:
            log(
                f"  tar attempt {attempt}/{attempts} failed ({elapsed:.0f}s): "
                f"{proc.stderr.strip()[:200]}. Retrying in {delay}s...",
                "WARN",
            )
            time.sleep(delay)
            delay *= 2
    if proc.returncode != 0:
        log(
            f"FAILED extracting {basename} after {attempts} attempts "
            f"({elapsed:.0f}s last): {proc.stderr.strip()[:300]}",
            "ERROR",
        )
        return staged_dir, "failed"

    # Write the sentinel marker. Includes a timestamp + source path for
    # auditability.
    with open(os.path.join(staged_dir, ".extracted"), "w") as fh:
        fh.write(
            f"source: {tgz_path}\n"
            f"extracted_at: {datetime.now().isoformat()}\n"
            f"strip_components: {strip_components}\n"
        )
    log(f"  Extracted {basename} ({elapsed:.0f}s)")
    return staged_dir, "extracted"


def main():
    p = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--archive-root", required=True,
        help="Root path on the NI archive (e.g. //cicmgsp02/gnuclear2$/2025/Jesus/).",
    )
    p.add_argument(
        "--staging", required=True,
        help="Local staging directory (will be created if missing).",
    )
    p.add_argument(
        "--strip-components", type=int, default=6,
        help="Number of leading path components to strip from each archive "
             "(default 6, matching the Molecubes/Nuclear-Imaging archive "
             "convention `<user>/<series>/<date>/<short_project>_<short_sample>/"
             "<timestamp>_<modality>/<timestamp>_<modality>/...`).",
    )
    p.add_argument(
        "--limit", type=int, default=0,
        help="If > 0, only extract the first N archives (sorted alphabetically). "
             "Useful for piloting.",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="List what would be extracted; touch nothing.",
    )
    p.add_argument(
        "--force", action="store_true",
        help="Re-extract even if the staged folder already has the "
             "`.extracted` sentinel.",
    )
    args = p.parse_args()

    log(f"Archive root: {args.archive_root}")
    log(f"Staging:      {args.staging}")
    log(f"Strip levels: {args.strip_components}")

    if not args.dry_run:
        os.makedirs(args.staging, exist_ok=True)

    log("Walking archive root...")
    archives = find_tgz(args.archive_root)
    log(f"Found {len(archives)} .tgz files")

    if args.limit > 0:
        archives = archives[: args.limit]
        log(f"Limited to first {len(archives)} for this run (--limit)")

    n_extracted = 0
    n_skipped = 0
    n_failed = 0
    t_start = time.time()

    for i, tgz in enumerate(archives, 1):
        basename = os.path.basename(tgz)
        # Getting the .tgz size also touches SMB; wrap in retry.
        try:
            size_mb = _retry(
                lambda: os.path.getsize(tgz) / 1_000_000,
                what=f"sizing {basename}",
            ) if not args.dry_run else 0
        except OSError as e:
            log(f"Skipping {basename}: cannot stat ({e})", "ERROR")
            n_failed += 1
            continue
        log(f"[{i}/{len(archives)}] {basename} ({size_mb:.0f} MB)")
        staged_dir, status = extract_one(
            tgz, args.staging,
            strip_components=args.strip_components,
            dry_run=args.dry_run,
        )
        if status == "extracted":
            n_extracted += 1
        elif status == "skipped":
            n_skipped += 1
            log(f"  Skipped (already extracted): {staged_dir}")
        elif status == "failed":
            n_failed += 1

    elapsed = time.time() - t_start
    log("")
    log("=" * 60)
    log(f"Summary: {n_extracted} extracted, {n_skipped} skipped, {n_failed} failed "
        f"in {elapsed/60:.1f} min")
    return 1 if n_failed else 0


if __name__ == "__main__":
    sys.exit(main())
