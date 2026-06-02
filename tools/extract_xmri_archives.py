"""Extract collaborator XMRI archives into per-case DICOM directories.

The collaborator cardiac-MRI deposits (LIONS `.zip`, HPIC `.rar`) each hold a
full DICOM tree (DICOMDIR + S####/I## extensionless instance files). The
ingest pipeline (`ingest_raw.py` with the lions_/hpic_ configs, `pattern: */`)
expects one *directory per acquisition*, so this utility expands every archive
under `--src` into `<dest>/<case>/`, where `<case>` is the archive basename
without extension (e.g. `LEONE_1.01.zip` -> `LEONE_1.01/`, `HPIC02.rar` ->
`HPIC02/`). That case-dir name becomes `discovered.folder_name` -> `sample_id`.

`.zip` is handled by the stdlib `zipfile`; `.rar` is shelled out to 7-Zip
(`7z.exe`). Run this from **native Windows Python** when `--dest` is on the NAS
so the created folders inherit correct Windows ACLs (the whole point of the
container rebuild). Idempotent: a case whose dest dir already exists and is
non-empty is skipped, so the run can be resumed after an interruption.

Usage (from the repo root, Windows):

    python tools/extract_xmri_archives.py ^
        --src  "C:/Users/rtasseff/temp/LIONS_42cases" ^
        --dest "J:/gjesus3-data/staging/LIONS_42cases_extracted"

    python tools/extract_xmri_archives.py ^
        --src  "C:/Users/rtasseff/temp/HPIC_33cases" ^
        --dest "J:/gjesus3-data/staging/HPIC_33cases_extracted"

Add `--limit N` to extract only the first N archives (cheap validation), and
`--dry-run` to list what would be extracted without writing anything.
"""

import argparse
import os
import subprocess
import sys
import zipfile
from pathlib import Path

DEFAULT_7Z = r"C:\Program Files\7-Zip\7z.exe"

# Archive extensions we know how to expand.
_ZIP_EXTS = {".zip"}
_RAR_EXTS = {".rar"}


def _is_nonempty_dir(path):
    return path.is_dir() and any(path.iterdir())


def _extract_zip(archive, case_dir):
    """Extract a .zip archive into case_dir using the stdlib."""
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(case_dir)


def _extract_rar(archive, case_dir, seven_zip):
    """Extract a .rar archive into case_dir by shelling out to 7-Zip.

    `7z x -o<dir> <archive> -y` recreates the internal tree under case_dir.
    """
    if not os.path.isfile(seven_zip):
        raise RuntimeError(
            f"7-Zip not found at {seven_zip!r}. Install 7-Zip or pass "
            f"--seven-zip with the correct path (needed for .rar archives)."
        )
    result = subprocess.run(
        [seven_zip, "x", f"-o{case_dir}", str(archive), "-y"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"7-Zip failed on {archive} (exit {result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )


def extract_all(src, dest, seven_zip=DEFAULT_7Z, limit=None, dry_run=False):
    """Extract every archive in `src` into `dest/<case>/`.

    Returns (extracted, skipped, failed) counts.
    """
    src = Path(src)
    dest = Path(dest)
    if not src.is_dir():
        raise RuntimeError(f"--src is not a directory: {src}")

    archives = sorted(
        p for p in src.iterdir()
        if p.is_file() and p.suffix.lower() in (_ZIP_EXTS | _RAR_EXTS)
    )
    if limit:
        archives = archives[:limit]
    if not archives:
        print(f"No .zip/.rar archives found under {src}")
        return 0, 0, 0

    print(f"Found {len(archives)} archive(s) under {src}")
    if not dry_run:
        dest.mkdir(parents=True, exist_ok=True)

    extracted = skipped = failed = 0
    for i, archive in enumerate(archives, 1):
        case = archive.stem  # basename without extension
        case_dir = dest / case
        if _is_nonempty_dir(case_dir):
            print(f"[{i}/{len(archives)}] SKIP {case} (already extracted)")
            skipped += 1
            continue
        if dry_run:
            print(f"[{i}/{len(archives)}] would extract {archive.name} -> {case_dir}")
            extracted += 1
            continue
        print(f"[{i}/{len(archives)}] extracting {archive.name} -> {case_dir} ...", flush=True)
        case_dir.mkdir(parents=True, exist_ok=True)
        try:
            if archive.suffix.lower() in _ZIP_EXTS:
                _extract_zip(archive, case_dir)
            else:
                _extract_rar(archive, case_dir, seven_zip)
            n_files = sum(1 for _ in case_dir.rglob("*") if _.is_file())
            print(f"    done ({n_files} files)")
            extracted += 1
        except Exception as e:
            print(f"    FAILED: {e}", file=sys.stderr)
            failed += 1

    print(
        f"\nDone. extracted={extracted} skipped={skipped} failed={failed} "
        f"(of {len(archives)} archives)"
    )
    return extracted, skipped, failed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, help="Directory of .zip/.rar archives")
    ap.add_argument("--dest", required=True, help="Destination root for per-case dirs")
    ap.add_argument("--seven-zip", default=DEFAULT_7Z, help=f"Path to 7z.exe (default {DEFAULT_7Z})")
    ap.add_argument("--limit", type=int, default=None, help="Only extract the first N archives")
    ap.add_argument("--dry-run", action="store_true", help="List actions without extracting")
    args = ap.parse_args(argv)

    _, _, failed = extract_all(
        args.src, args.dest,
        seven_zip=args.seven_zip, limit=args.limit, dry_run=args.dry_run,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
