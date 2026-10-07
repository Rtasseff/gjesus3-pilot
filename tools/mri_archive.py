#!/usr/bin/env python3
"""mri_archive.py -- READ-ONLY access to the MRI platform's own archive of older 7T data.

The archive: ``mriuser@10.10.3.175``, folder ``/share/homes/mriuser/backup_7T_olddata_260824``: the
platform's archive of the studies moved off the 7T acquisition machine on 2026-08-24, one compressed
tarball per ParaVision study (``<study>.tar.gz`` / ``.tar.xz``) with a ``.sha1`` beside it, in year
folders (``2019_pv6`` ... ``2022_PV6_PV7``). It is the platform's, not ours, and the account CAN write
there. See ``equipment/historical_data_archives.md`` ("MRI platform archive").

The three rules (Ryan, 2026-10-07, "critical importance"), enforced here in code:

1. **Nothing is ever written, renamed, chmod-ed or deleted on the archive.** Every access goes through
   :class:`ReadOnlyArchive`, which holds exactly three remote callables (list a folder, stat a path,
   open a file for reading) and nothing else: no SFTP client, no transport, no shell, no command
   execution. ``open`` accepts mode ``"rb"`` only and returns a :class:`ReadOnlyFile` that can only
   read, seek, tell and close. Every path must lie inside :data:`ARCHIVE_ROOT`. No ``.part``, lock or
   temp file is ever created on the archive (a download writes locally only).
2. **One connection, sequential calls.** :func:`connect` refuses a second live connection in the same
   process, every call is serialised by a lock, and calls are paced during working hours.
   **File contents are read only outside 08:00-18:00 Monday-Friday** (local time): ``open`` raises
   :class:`WorkingHoursError` inside those hours. Listing and stat are allowed then, gently.
3. **Normal tools never point at it.** The GUI and ``ftp_mirror.py`` keep the ``[mri]`` section (the
   scanner). Only this module reads the ``[mri_archive]`` section of
   ``%USERPROFILE%\\.ssh\\gjesus3_mri.cred``, and it never falls back to ``[mri]``. The password is
   never printed, logged or put in a repr.

CLI (listing only):

    python tools/mri_archive.py list --out <listing.csv> [--max-depth 2]

writes one row per archive entry (path, kind, size, mtime) to a LOCAL csv. Nothing else is offered.

Stdlib + paramiko (already a dependency of ``ftp_mirror.py``).
"""

import argparse
import configparser
import csv
import datetime as _dt
import io
import os
import posixpath
import stat as _stat
import sys
import threading
import time

ARCHIVE_HOST = "10.10.3.175"
ARCHIVE_ROOT = "/share/homes/mriuser/backup_7T_olddata_260824"
CRED_FILE = os.path.join(os.path.expanduser("~"), ".ssh", "gjesus3_mri.cred")
CRED_SECTION = "mri_archive"

# Working hours, local time: Monday (0) .. Friday (4), 08:00 <= t < 18:00.
WORK_DAYS = frozenset(range(5))
WORK_START_HOUR = 8
WORK_END_HOUR = 18
# Pause between remote calls during working hours ("gently"); none outside them.
WORKING_HOURS_PACE_S = 0.2

READ_ONLY_MODE = "rb"


class ArchiveError(Exception):
    """Base class for every refusal of this module."""


class CredentialsError(ArchiveError):
    """The [mri_archive] section is missing or incomplete."""


class ReadOnlyViolation(ArchiveError):
    """Something other than a read was asked for."""


class WorkingHoursError(ArchiveError):
    """File contents were asked for between 08:00 and 18:00 on a weekday."""


class OutsideArchiveError(ArchiveError):
    """A path outside ARCHIVE_ROOT was asked for."""


class ConnectionInUseError(ArchiveError):
    """A second connection was asked for while one is live in this process."""


# --------------------------------------------------------------------------------------------------
# Credentials
# --------------------------------------------------------------------------------------------------

def load_credentials(path=CRED_FILE, section=CRED_SECTION):
    """Read host / user / password / port from the ``[mri_archive]`` section.

    Raises :class:`CredentialsError` when the file, the section, or any of host / user / password is
    missing. Never falls back to ``[mri]`` (the scanner). The password is returned to the caller and
    never printed; the error messages name fields, never values.
    """
    if section != CRED_SECTION:
        raise CredentialsError(f"only the [{CRED_SECTION}] section names the archive")
    if not os.path.isfile(path):
        raise CredentialsError(f"credentials file not found: {path}")
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(path, encoding="utf-8")
    except (configparser.Error, OSError) as exc:
        raise CredentialsError(f"credentials file unreadable: {path} ({type(exc).__name__})") from None
    if not parser.has_section(section):
        raise CredentialsError(f"no [{section}] section in {path} (the [mri] section is the scanner's "
                               f"and is never used for the archive)")
    sec = parser[section]
    missing = [k for k in ("host", "user", "password") if not (sec.get(k) or "").strip()]
    if missing:
        raise CredentialsError(f"[{section}] in {path} lacks: {', '.join(missing)}")
    port_s = (sec.get("port") or "22").strip()
    try:
        port = int(port_s)
    except ValueError:
        raise CredentialsError(f"[{section}] port is not a number") from None
    return {"host": sec.get("host").strip(), "user": sec.get("user").strip(),
            "password": sec.get("password"), "port": port}


def describe_credentials(cred):
    """A printable summary: host, user, port, and only WHETHER a password is present."""
    return (f"[{CRED_SECTION}] {cred.get('user')}@{cred.get('host')}:{cred.get('port')} "
            f"(password present: {bool(cred.get('password'))})")


# --------------------------------------------------------------------------------------------------
# Hours and paths
# --------------------------------------------------------------------------------------------------

def in_working_hours(now=None):
    """True between 08:00 and 18:00, Monday to Friday, local time."""
    now = now or _dt.datetime.now()
    return now.weekday() in WORK_DAYS and WORK_START_HOUR <= now.hour < WORK_END_HOUR


def archive_path(path):
    """Normalise ``path`` (absolute, or relative to ARCHIVE_ROOT) and refuse anything outside the root."""
    if not isinstance(path, str) or not path:
        raise OutsideArchiveError("an archive path must be a non-empty string")
    p = path if path.startswith("/") else posixpath.join(ARCHIVE_ROOT, path)
    p = posixpath.normpath(p)
    if p != ARCHIVE_ROOT and not p.startswith(ARCHIVE_ROOT + "/"):
        raise OutsideArchiveError(f"outside the archive root: {path}")
    return p


# --------------------------------------------------------------------------------------------------
# The read-only wrapper
# --------------------------------------------------------------------------------------------------

class ReadOnlyFile:
    """A remote file opened ``"rb"``: read, seek, tell, close. Nothing else exists on this object."""

    __slots__ = ("_read", "_seek", "_tell", "_close", "_closed")

    def __init__(self, read, seek, tell, close):
        self._read, self._seek, self._tell, self._close = read, seek, tell, close
        self._closed = False

    def read(self, size=-1):
        if self._closed:
            raise ValueError("read on a closed archive file")
        return self._read(size) if size is not None and size >= 0 else self._read()

    def seek(self, offset, whence=0):
        return self._seek(offset, whence)

    def tell(self):
        return self._tell()

    def close(self):
        if not self._closed:
            self._closed = True
            self._close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def __repr__(self):
        return f"<ReadOnlyFile closed={self._closed}>"


class ReadOnlyArchive:
    """The ONLY way to touch the archive: ``listdir_attr``, ``stat``, ``open(path, "rb")``, ``close``.

    It is built from three callables (in production the bound ``listdir_attr``, ``stat`` and ``open``
    of one SFTP session) and a ``close`` callable for the connection. It keeps no SFTP client, no
    transport and no channel as an attribute, so no write, rename, chmod, delete, shell or command
    method exists on it. ``__slots__`` stops anything from being added later.
    """

    __slots__ = ("_listdir_attr", "_stat", "_open", "_close", "_lock", "_now", "_sleep", "_pace",
                 "_last_call", "_closed", "calls", "label")

    def __init__(self, listdir_attr, stat, open_, close=None, *, label="", now=None, sleep=None,
                 pace=WORKING_HOURS_PACE_S):
        self._listdir_attr = listdir_attr
        self._stat = stat
        self._open = open_
        self._close = close or (lambda: None)
        self._lock = threading.Lock()
        self._now = now or _dt.datetime.now
        self._sleep = sleep or time.sleep
        self._pace = pace
        self._last_call = 0.0
        self._closed = False
        self.calls = 0
        self.label = label

    # -- internal -------------------------------------------------------------------------------
    def _before_call(self):
        if self._closed:
            raise ArchiveError("the archive connection is closed")
        if in_working_hours(self._now()) and self._pace:
            wait = self._pace - (time.monotonic() - self._last_call)
            if wait > 0:
                self._sleep(wait)

    def _after_call(self):
        self._last_call = time.monotonic()
        self.calls += 1

    # -- the three reads ------------------------------------------------------------------------
    def listdir_attr(self, path):
        """The entries of one archive folder (paramiko ``SFTPAttributes``: filename, st_size, st_mtime, st_mode)."""
        p = archive_path(path)
        with self._lock:
            self._before_call()
            try:
                return self._listdir_attr(p)
            finally:
                self._after_call()

    def stat(self, path):
        """The attributes of one archive path."""
        p = archive_path(path)
        with self._lock:
            self._before_call()
            try:
                return self._stat(p)
            finally:
                self._after_call()

    def open(self, path, mode=READ_ONLY_MODE):
        """Open one archive file for reading. ``mode`` must be exactly ``"rb"``; refused 08:00-18:00 Mon-Fri."""
        if mode != READ_ONLY_MODE:
            raise ReadOnlyViolation(f"the archive is read-only: mode {mode!r} refused (only 'rb')")
        p = archive_path(path)
        if in_working_hours(self._now()):
            raise WorkingHoursError("file contents are read only outside 08:00-18:00 Monday-Friday "
                                    f"(now {self._now():%a %H:%M}); listing and stat are allowed")
        with self._lock:
            self._before_call()
            try:
                fh = self._open(p, READ_ONLY_MODE)
            finally:
                self._after_call()
        return ReadOnlyFile(fh.read, fh.seek, fh.tell, fh.close)

    # -- lifecycle ------------------------------------------------------------------------------
    def close(self):
        if not self._closed:
            self._closed = True
            self._close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def __repr__(self):
        return f"<ReadOnlyArchive {self.label} calls={self.calls} closed={self._closed}>"


# --------------------------------------------------------------------------------------------------
# Connecting (one connection per process)
# --------------------------------------------------------------------------------------------------

_ACTIVE = {"archive": None}


def connect(cred_path=CRED_FILE, *, timeout=30, log=print):
    """Open ONE SFTP session to the archive and return it wrapped in :class:`ReadOnlyArchive`.

    Only the SFTP subsystem is opened (no shell, no command). The SFTP client and the transport stay
    local to this function and to the wrapper's ``close`` callable; the wrapper never holds them.
    Refuses while another connection from this process is still open.
    """
    live = _ACTIVE["archive"]
    if live is not None and not live._closed:
        raise ConnectionInUseError("one archive connection per process: close the live one first")
    cred = load_credentials(cred_path)
    try:
        import paramiko
    except ImportError:
        raise ArchiveError("paramiko is not installed (pip install paramiko)") from None

    transport = paramiko.Transport((cred["host"], cred["port"]))
    transport.banner_timeout = timeout
    try:
        transport.connect(username=cred["user"], password=cred["password"])
        key = transport.get_remote_server_key()
        sftp = paramiko.SFTPClient.from_transport(transport)
    except Exception:
        transport.close()
        raise
    finally:
        cred["password"] = None
    fingerprint = ""
    try:
        import base64
        import hashlib
        fingerprint = "SHA256:" + base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip("=")
    except Exception:  # noqa: BLE001 -- the fingerprint is informational only
        pass

    def _close(sftp=sftp, transport=transport):
        try:
            sftp.close()
        finally:
            transport.close()

    archive = ReadOnlyArchive(sftp.listdir_attr, sftp.stat, sftp.open, _close,
                              label=f"{cred['user']}@{cred['host']}")
    del sftp
    _ACTIVE["archive"] = archive
    if log:
        log(f"connected read-only: {cred['user']}@{cred['host']}:{cred['port']} host key {key.get_name()} "
            f"{fingerprint}")
    return archive


# --------------------------------------------------------------------------------------------------
# Listing helper
# --------------------------------------------------------------------------------------------------

LISTING_FIELDS = ["path", "parent", "name", "kind", "size", "mtime", "mode", "depth"]


def _kind(mode):
    if mode is None:
        return "unknown"
    if _stat.S_ISDIR(mode):
        return "dir"
    if _stat.S_ISREG(mode):
        return "file"
    if _stat.S_ISLNK(mode):
        return "link"
    return "other"


def walk(archive, root=ARCHIVE_ROOT, max_depth=2):
    """Yield one dict per entry under ``root``, depth-first, sequentially (one listing at a time).

    ``depth`` 1 is ``root``'s own children. Folders deeper than ``max_depth`` are reported but not
    listed. Links are reported, never followed.
    """
    root = archive_path(root)
    stack = [(root, 1)]
    while stack:
        folder, depth = stack.pop()
        entries = sorted(archive.listdir_attr(folder), key=lambda a: a.filename)
        subdirs = []
        for a in entries:
            kind = _kind(getattr(a, "st_mode", None))
            mt = getattr(a, "st_mtime", None)
            row = {
                "path": posixpath.join(folder, a.filename),
                "parent": folder,
                "name": a.filename,
                "kind": kind,
                "size": getattr(a, "st_size", "") if kind != "dir" else "",
                "mtime": _dt.datetime.fromtimestamp(mt).isoformat(timespec="seconds") if mt else "",
                "mode": oct(a.st_mode) if getattr(a, "st_mode", None) is not None else "",
                "depth": depth,
            }
            yield row
            if kind == "dir" and depth < max_depth:
                subdirs.append((row["path"], depth + 1))
        stack.extend(reversed(subdirs))


def write_listing(rows, out_csv):
    """Write listing rows to a LOCAL csv (never to the archive)."""
    out_dir = os.path.dirname(os.path.abspath(out_csv))
    os.makedirs(out_dir, exist_ok=True)
    n = 0
    with io.open(out_csv, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=LISTING_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(r)
            n += 1
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description="READ-ONLY listing of the MRI platform's archive "
                                             f"({ARCHIVE_ROOT}). Nothing is ever written there.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list", help="list the archive into a local csv")
    ls.add_argument("--out", required=True, help="local csv to write")
    ls.add_argument("--root", default=ARCHIVE_ROOT, help="a folder inside the archive root")
    ls.add_argument("--max-depth", type=int, default=2)
    ls.add_argument("--cred-file", default=CRED_FILE)
    args = ap.parse_args(argv)

    if args.cmd == "list":
        t0 = time.time()
        with connect(args.cred_file) as archive:
            n = write_listing(walk(archive, args.root, args.max_depth), args.out)
            calls = archive.calls
        print(f"listed {n} entries in {calls} remote calls ({time.time() - t0:.1f}s) -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
