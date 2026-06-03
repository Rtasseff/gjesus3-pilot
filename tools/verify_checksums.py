#!/usr/bin/env python3
"""verify_checksums.py -- read-only fixity checker for the /raw/ area.

Re-verifies the SHA-256 checksums recorded in each acquisition's
`checksums.json` against the current on-disk files. This is the periodic
fixity / bit-rot check (tasks.md SS3.2): ingest already verified source-vs-dest
at copy time and wrote `checksums.json`; this tool answers the later question
"are the bytes still what we stored?".

WHAT IT CHECKS
    Each acquisition folder under `<nas_root>/raw/` that contains a
    `checksums.json` has, at its root, a JSON file of the shape written by
    `ingest.checksum.write_checksums`:

        {
          "generated": "<ISO-8601 UTC>",
          "algorithm": "sha256",
          "files": { "<relpath-from-acq-folder>": "<hex digest>", ... }
        }

    The relpaths are relative to the acquisition folder itself (for
    folder-as-primary / DICOM acquisitions they include the `<ACQ-ID>.data/`
    subfolder; for microscopy it is the single `<ACQ-ID>.czi`). For each
    recorded (relpath, expected_hash) we recompute the hash of the on-disk
    file with `ingest.checksum.sha256_file` -- the SAME hashing the ingest
    used -- and compare. An acquisition PASSes only if every recorded file
    exists and matches.

    NOT a mismatch: extra files on disk that are not in `checksums.json`
    (e.g. README.txt, a later-written sidecar). Fixity is about the bytes we
    committed to, not about forbidding additions. They are reported as INFO.

READ-ONLY
    This tool never writes anything -- not to the NAS, not to the registry.
    It only reads `checksums.json` files and re-hashes the data they cover.

USAGE
    # Verify a single acquisition by ACQ-ID:
    python tools/verify_checksums.py --acq MICROSCOPY-CELL-20250512-0003 --nas-root J:\\gjesus3-data

    # Walk all acquisitions under <nas_root>/raw/ :
    python tools/verify_checksums.py --nas-root J:\\gjesus3-data

    # nas_root also comes from $GJESUS3_ROOT:
    $env:GJESUS3_ROOT = 'J:\\gjesus3-data'; python tools/verify_checksums.py

EXIT CODES
    0  all verified acquisitions PASS
    1  one or more acquisitions FAIL (mismatch or missing recorded file)
    2  usage / environment error (bad --nas-root, --acq not found, etc.)
"""

import argparse
import json
import os
import sys
from datetime import datetime

# Allow `from ingest import ...` whether run from tools/ or elsewhere.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from ingest import checksum, registry  # noqa: E402


CHECKSUMS_FILENAME = "checksums.json"


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {level}: {msg}", file=sys.stderr)


# ---- checksums.json reading ---------------------------------------------

def read_recorded_checksums(checksums_path):
    """Read a checksums.json and return its {relpath: hexdigest} files map.

    Returns the files dict. Raises ValueError if the file is malformed or
    declares an algorithm this checker can't recompute.
    """
    with open(checksums_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError("checksums.json is not a JSON object")
    algo = (payload.get("algorithm") or "sha256").lower()
    if algo != "sha256":
        raise ValueError(
            f"unsupported algorithm '{algo}' (this checker recomputes sha256 "
            f"via ingest.checksum.sha256_file)"
        )
    files = payload.get("files")
    if not isinstance(files, dict):
        raise ValueError("checksums.json has no 'files' object")
    return files


# ---- per-acquisition verification ---------------------------------------

def verify_acquisition(acq_folder):
    """Re-verify one acquisition folder against its checksums.json.

    Re-hashes every file recorded in checksums.json (relpath is relative to
    `acq_folder`) using ingest.checksum.sha256_file and compares.

    Returns a result dict:
        {
          "folder": <abs path>,
          "status": "PASS" | "FAIL" | "ERROR",
          "n_files": <int recorded>,
          "missing": [relpath, ...],     # recorded but absent on disk
          "mismatched": [relpath, ...],  # present but hash differs
          "extra": [relpath, ...],       # on disk, not in checksums.json (INFO)
          "error": <str or None>,        # set when status == "ERROR"
        }
    """
    result = {
        "folder": acq_folder,
        "status": "PASS",
        "n_files": 0,
        "missing": [],
        "mismatched": [],
        "extra": [],
        "error": None,
    }
    checksums_path = os.path.join(acq_folder, CHECKSUMS_FILENAME)
    try:
        recorded = read_recorded_checksums(checksums_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result["status"] = "ERROR"
        result["error"] = str(exc)
        return result

    result["n_files"] = len(recorded)

    for rel, expected in recorded.items():
        # checksums.json keys may be backslash-separated (legacy DICOM manifest
        # written on Windows) or forward-slash (folder-as-primary, normalized).
        # Split on BOTH so the path resolves whether we verify on Windows or
        # WSL/Linux — otherwise a Windows-written backslash key falsely reports
        # MISSING when verified from Linux.
        parts = [p for p in rel.replace("\\", "/").split("/") if p]
        fpath = os.path.join(acq_folder, *parts) if parts else acq_folder
        if not os.path.isfile(fpath):
            result["missing"].append(rel)
            continue
        try:
            actual = checksum.sha256_file(fpath)
        except OSError as exc:
            result["missing"].append(f"{rel} (unreadable: {exc})")
            continue
        if actual != expected:
            result["mismatched"].append(rel)

    # Report (but do not fail on) files present on disk that aren't recorded.
    # checksums.json and known generated aux files are expected extras.
    # Compare on a forward-slash-normalized form so backslash keys still match.
    generated = {CHECKSUMS_FILENAME, "README.txt"}
    recorded_norm = {r.replace("\\", "/").strip("/") for r in recorded}
    for root, _dirs, files in os.walk(acq_folder):
        for fname in files:
            abspath = os.path.join(root, fname)
            rel = os.path.relpath(abspath, acq_folder).replace(os.sep, "/")
            if rel in recorded_norm:
                continue
            if rel in generated:
                continue
            result["extra"].append(rel)

    if result["missing"] or result["mismatched"]:
        result["status"] = "FAIL"
    return result


# ---- acquisition discovery ----------------------------------------------

def iter_acquisition_folders(raw_root):
    """Yield every folder under raw_root that contains a checksums.json.

    Walks the /raw/ tree once. A folder is an acquisition iff it holds a
    checksums.json at its own root.
    """
    for root, _dirs, files in os.walk(raw_root):
        if CHECKSUMS_FILENAME in files:
            yield root


def find_acq_folder(nas_root, raw_root, acq_id):
    """Resolve a single ACQ-ID to its on-disk acquisition folder.

    Prefers the registry's canonical_path (authoritative). Falls back to a
    walk of /raw/ for a folder named exactly <acq_id> with a checksums.json.
    Returns the absolute folder path, or None if not found.
    """
    registry_path = os.path.join(nas_root, "registries", "registry_raw.csv")
    rows = registry.read_registry(registry_path)
    for row in rows:
        if row.get("acq_id") == acq_id:
            canonical = (row.get("canonical_path") or "").strip()
            if canonical:
                # canonical_path is like "/raw/<eco>/<yyyy>/<mm>/<ACQ-ID>/"
                rel = canonical.lstrip("/").replace("/", os.sep)
                cand = os.path.join(nas_root, rel)
                if os.path.isdir(cand):
                    return os.path.normpath(cand)
            break  # acq_id found but canonical_path unusable; fall through

    # Fallback: locate by folder name under /raw/.
    for folder in iter_acquisition_folders(raw_root):
        if os.path.basename(os.path.normpath(folder)) == acq_id:
            return os.path.normpath(folder)
    return None


# ---- reporting ----------------------------------------------------------

def report_result(res):
    """Emit one acquisition's outcome to stderr at the appropriate level."""
    name = os.path.basename(os.path.normpath(res["folder"]))
    if res["status"] == "PASS":
        log(f"PASS  {name}  ({res['n_files']} files)")
        for rel in res["extra"]:
            log(f"  (extra on disk, not in checksums.json) {rel}")
    elif res["status"] == "ERROR":
        log(f"ERROR {name}  could not read checksums.json: {res['error']}", "ERROR")
    else:  # FAIL
        log(
            f"FAIL  {name}  "
            f"({len(res['missing'])} missing, {len(res['mismatched'])} mismatched "
            f"of {res['n_files']} recorded)",
            "ERROR",
        )
        for rel in res["missing"]:
            log(f"  MISSING    {rel}", "ERROR")
        for rel in res["mismatched"]:
            log(f"  MISMATCH   {rel}", "ERROR")


def main():
    parser = argparse.ArgumentParser(
        description="Read-only re-verification of /raw/ checksums.json fixity.",
        epilog="See tasks.md SS3.2. Exit 0 = all PASS, 1 = any FAIL, 2 = usage error.",
    )
    parser.add_argument(
        "--nas-root",
        default=os.environ.get("GJESUS3_ROOT", "/mnt/gjesus3"),
        help="Path to NAS root (default: $GJESUS3_ROOT or /mnt/gjesus3)",
    )
    parser.add_argument(
        "--acq",
        help="Verify a single acquisition by ACQ-ID (default: walk all of raw/)",
    )
    args = parser.parse_args()

    # Keep accented paths/notes legible on the Windows console; we only print
    # to stderr but reconfigure stdout too for parity with the other tools.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    nas_root = args.nas_root
    log(f"NAS root: {nas_root}")

    # Fail fast if nas_root doesn't look like a real NAS root (mirrors
    # ingest_raw.py): a valid root is a directory with a registries/ subfolder.
    registries_dir = os.path.join(nas_root, "registries")
    if not os.path.isdir(nas_root) or not os.path.isdir(registries_dir):
        log(
            f"NAS root does not look valid: '{nas_root}' (expected a "
            f"directory containing a 'registries/' subfolder).",
            "ERROR",
        )
        log(
            "Pass --nas-root <path> explicitly, or set GJESUS3_ROOT in your "
            "shell. On Windows PowerShell: $env:GJESUS3_ROOT = 'J:\\gjesus3-data'  "
            "(adjust to your NAS mount). On WSL: typically /mnt/gjesus3.",
            "ERROR",
        )
        return 2

    raw_root = os.path.join(nas_root, "raw")
    if not os.path.isdir(raw_root):
        log(f"No raw/ folder under NAS root: '{raw_root}'", "ERROR")
        return 2

    # Collect the acquisition folders to verify.
    if args.acq:
        folder = find_acq_folder(nas_root, raw_root, args.acq)
        if folder is None:
            log(
                f"ACQ-ID '{args.acq}' not found (no registry canonical_path "
                f"and no folder of that name with a {CHECKSUMS_FILENAME} under "
                f"{raw_root}).",
                "ERROR",
            )
            return 2
        folders = [folder]
        log(f"Verifying single acquisition: {folder}")
    else:
        folders = sorted(iter_acquisition_folders(raw_root))
        log(f"Found {len(folders)} acquisition(s) with {CHECKSUMS_FILENAME} under {raw_root}")
        if not folders:
            log("Nothing to verify.")
            return 0

    # Verify each and tally.
    n_pass = n_fail = n_error = 0
    for folder in folders:
        res = verify_acquisition(folder)
        report_result(res)
        if res["status"] == "PASS":
            n_pass += 1
        elif res["status"] == "FAIL":
            n_fail += 1
        else:
            n_error += 1

    log("---- summary ----")
    log(f"PASS:  {n_pass}")
    log(f"FAIL:  {n_fail}", "ERROR" if n_fail else "INFO")
    log(f"ERROR: {n_error}", "ERROR" if n_error else "INFO")
    log(f"TOTAL: {len(folders)}")

    # Nonzero on any mismatch/missing-file (FAIL) or unreadable manifest (ERROR).
    return 1 if (n_fail or n_error) else 0


if __name__ == "__main__":
    sys.exit(main())
