#!/usr/bin/env python3
"""ftp_mirror.py — Standalone SFTP mirror utility.

Pulls a remote directory tree from an SFTP server into a local staging
directory. Decoupled from the ingest pipeline: fetch first (manually
via this tool or via FileZilla), then run `ingest_raw.py` against the
local staging copy.

Built for round-6 internal MRI workflow per
`equipment/mri-platform/mri_data_access_strategy.md` (Phase A: pull
from the platform's FTP server using credentials provided by the
manager; researcher workstation runs this tool). Reusable for any
other SFTP-only data source the project encounters.

OUT OF SCOPE: a script that runs ON the acquisition machine
(`mri_data_access_strategy.md` Phase 4) and any concept of "push from
the platform side."

Usage:
    # Credentials via env vars (recommended):
    set GJESUS3_FTP_HOST=<host>
    set GJESUS3_FTP_USER=<user>
    set GJESUS3_FTP_PASSWORD=<password>
    python tools/ftp_mirror.py --remote /path/on/server --local D:/staging/<batch>

    # Or via flags (passwords visible in process list — env vars preferred):
    python tools/ftp_mirror.py \\
        --host <host> --user <user> --password <password> \\
        --remote /path --local D:/staging

    # Dry-run shows what would be transferred, no writes:
    python tools/ftp_mirror.py --remote /path --local D:/staging --dry-run

Idempotent: re-running skips files already present locally with matching
size + mtime. To force re-download, pass --force.
"""

import argparse
import getpass
import os
import stat
import sys
from datetime import datetime

try:
    import paramiko
    HAS_PARAMIKO = True
except ImportError:
    HAS_PARAMIKO = False


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {level}: {msg}")


def is_dir(sftp, path):
    try:
        return stat.S_ISDIR(sftp.stat(path).st_mode)
    except IOError:
        return False


def walk_remote(sftp, root):
    """Recursively yield (remote_path, st) tuples for files under root.

    Mirrors os.walk semantics but for SFTP. Yields files only (not dirs).
    """
    stack = [root]
    while stack:
        cur = stack.pop()
        try:
            entries = sftp.listdir_attr(cur)
        except IOError as e:
            log(f"Cannot list {cur}: {e}", "WARN")
            continue
        for entry in sorted(entries, key=lambda e: e.filename):
            child = cur.rstrip("/") + "/" + entry.filename
            if stat.S_ISDIR(entry.st_mode):
                stack.append(child)
            else:
                yield child, entry


def needs_transfer(local_path, remote_st, force):
    """Return True if the remote file should be downloaded.

    Skips when local exists with matching size AND mtime within 2s (file
    system rounding). --force overrides.
    """
    if force:
        return True
    if not os.path.isfile(local_path):
        return True
    local_st = os.stat(local_path)
    if local_st.st_size != remote_st.st_size:
        return True
    if abs(local_st.st_mtime - remote_st.st_mtime) > 2:
        return True
    return False


def mirror(sftp, remote_root, local_root, dry_run=False, force=False):
    """Mirror remote_root -> local_root over an existing SFTP connection.

    Returns (n_transferred, n_skipped, total_bytes_transferred).
    """
    n_transferred = 0
    n_skipped = 0
    bytes_transferred = 0

    if not is_dir(sftp, remote_root):
        raise RuntimeError(f"Remote path is not a directory: {remote_root}")

    log(f"Walking remote tree: {remote_root}")
    files = list(walk_remote(sftp, remote_root))
    log(f"Found {len(files)} remote files")

    for i, (remote_path, st) in enumerate(files, 1):
        rel = remote_path[len(remote_root):].lstrip("/")
        local_path = os.path.join(local_root, rel)

        if not needs_transfer(local_path, st, force):
            n_skipped += 1
            continue

        if dry_run:
            log(f"  [DRY-RUN] {rel} ({st.st_size:,} bytes)")
            n_transferred += 1
            bytes_transferred += st.st_size
            continue

        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        try:
            # Download to a .part file then atomically rename, so an interrupted
            # transfer never leaves a wrong-sized file at the final path (which
            # would defeat the size-based idempotency check on the next run).
            part_path = local_path + ".part"
            sftp.get(remote_path, part_path)
            os.replace(part_path, local_path)
            # Preserve mtime so the idempotency check works on re-runs.
            os.utime(local_path, (st.st_atime, st.st_mtime))
        except Exception as e:
            log(f"Failed: {rel} ({e})", "ERROR")
            continue

        n_transferred += 1
        bytes_transferred += st.st_size
        if i % 25 == 0:
            log(
                f"  Progress: {i}/{len(files)} "
                f"({bytes_transferred / 1_000_000:.1f} MB)"
            )

    return n_transferred, n_skipped, bytes_transferred


def main():
    p = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Env vars (preferred for password):\n"
            "  GJESUS3_FTP_HOST, GJESUS3_FTP_USER, GJESUS3_FTP_PASSWORD,\n"
            "  GJESUS3_FTP_PORT (default 22)\n\n"
            "See equipment/mri-platform/mri_data_access_strategy.md for the\n"
            "MRI-specific access model and the open questions for the\n"
            "platform manager."
        ),
    )
    p.add_argument("--host", default=os.environ.get("GJESUS3_FTP_HOST"))
    p.add_argument("--port", type=int,
                   default=int(os.environ.get("GJESUS3_FTP_PORT", "22")))
    p.add_argument("--user", default=os.environ.get("GJESUS3_FTP_USER"))
    p.add_argument("--password", default=os.environ.get("GJESUS3_FTP_PASSWORD"),
                   help="SFTP password. Prefer GJESUS3_FTP_PASSWORD env var. "
                        "If neither is set, you'll be prompted.")
    p.add_argument("--remote", required=True,
                   help="Remote directory to mirror (e.g. /opt/PV-7.0.0/data/nmr/<study>)")
    p.add_argument("--local", required=True,
                   help="Local staging directory (will be created if missing)")
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would be transferred, no writes")
    p.add_argument("--force", action="store_true",
                   help="Re-download files even if local copy looks current")

    args = p.parse_args()

    if not HAS_PARAMIKO:
        log("paramiko is not installed. Run: pip install paramiko", "ERROR")
        return 2

    if not args.host or not args.user:
        log("--host and --user are required (or set env vars).", "ERROR")
        return 2

    password = args.password
    if not password:
        password = getpass.getpass(f"SFTP password for {args.user}@{args.host}: ")

    log(f"Connecting: sftp://{args.user}@{args.host}:{args.port}")
    transport = paramiko.Transport((args.host, args.port))
    try:
        transport.connect(username=args.user, password=password)
        sftp = paramiko.SFTPClient.from_transport(transport)

        if not args.dry_run:
            os.makedirs(args.local, exist_ok=True)

        log(f"Mirroring {args.remote} -> {args.local}")
        n_xfer, n_skip, n_bytes = mirror(
            sftp, args.remote, args.local,
            dry_run=args.dry_run, force=args.force,
        )

        action = "would transfer" if args.dry_run else "transferred"
        log(
            f"Done. {action} {n_xfer} files ({n_bytes / 1_000_000:.1f} MB); "
            f"skipped {n_skip} already-present"
        )
    finally:
        transport.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
