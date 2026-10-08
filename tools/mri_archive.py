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

CLI:

    python tools/mri_archive.py list --out <listing.csv> [--max-depth 2]

writes one row per archive entry (path, kind, size, mtime) to a LOCAL csv.

    python tools/mri_archive.py fetch --plan <pull_plan.csv> --dest <local folder> [--dry-run]
                                      [--max-gb N] [--stop-at HH:MM] [--retry-bad] [--log-every N]

downloads the archives of the pull plan's pulled tiers (Ryan's rulings of 2026-10-07, STATUS §0.6) to
``<dest>\\<year folder>\\<archive>``, each verified against the ``.sha1`` (or ``.sha256``) beside it, or,
where none exists, by the compression's own check plus a full tar listing. ``--dry-run`` lists only
(allowed in working hours) and reads no contents. The run refuses to start in working hours, starts no
file it cannot finish before 08:00 on a weekday (or ``--stop-at``), and stops mid-file at that time,
leaving only a LOCAL ``.part`` that a re-run restarts. ``<dest>\\fetch_manifest.csv`` records every
attempt; a verified archive is skipped on a re-run.

Stdlib + paramiko (already a dependency of ``ftp_mirror.py``).
"""

import argparse
import configparser
import csv
import datetime as _dt
import gzip
import hashlib
import io
import lzma
import os
import posixpath
import re
import shutil
import stat as _stat
import sys
import tarfile
import threading
import time
import zlib

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
    """A remote file opened ``"rb"``: read, seek, tell, close. Nothing else exists on this object.

    ``guard`` (from :meth:`ReadOnlyArchive.open`) runs before every read and raises
    :class:`WorkingHoursError` once 08:00 Monday-Friday is reached, so a file opened at night cannot keep
    being read into working hours.
    """

    __slots__ = ("_read", "_seek", "_tell", "_close", "_closed", "_guard")

    def __init__(self, read, seek, tell, close, guard=None):
        self._read, self._seek, self._tell, self._close = read, seek, tell, close
        self._guard = guard
        self._closed = False

    def read(self, size=-1):
        if self._closed:
            raise ValueError("read on a closed archive file")
        if self._guard is not None:
            self._guard()
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

    def _contents_allowed(self):
        """Raise :class:`WorkingHoursError` between 08:00 and 18:00, Monday to Friday."""
        now = self._now()
        if in_working_hours(now):
            raise WorkingHoursError("file contents are read only outside 08:00-18:00 Monday-Friday "
                                    f"(now {now:%a %H:%M}); listing and stat are allowed")

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
        self._contents_allowed()
        with self._lock:
            self._before_call()
            try:
                fh = self._open(p, READ_ONLY_MODE)
            finally:
                self._after_call()
        return ReadOnlyFile(fh.read, fh.seek, fh.tell, fh.close, guard=self._contents_allowed)

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


# --------------------------------------------------------------------------------------------------
# Fetch: the pull plan's archives to LOCAL disk, verified
# --------------------------------------------------------------------------------------------------

# Ryan's rulings of 2026-10-07 (STATUS §0.6) on the census plan's tiers (tasks/mri_archive_census.md §5):
#   C  stream M's 130 for the drive-3 originals check (fetched first)    -- Q1
#   A  561 new MFB animal sessions; A2  12 second sessions                -- Q1
#   B  77 MFB phantoms / QC / unclear, the 6 code-less and 0220's 3 among them   -- Q1, Q2, Q4, Q5
#   not pulled: E  9 studies with other initials on 1116 (Q3); D aborted starts; X empty archives.
# Any other tier code is refused, so a changed plan never pulls by accident.
PULL_TIERS = ("C", "A", "A2", "B")
SKIP_TIERS = ("D", "E", "X")
CHECKSUM_HEXLEN = {"sha1": 40, "sha256": 64}

CHUNK_BYTES = 1 << 20
SIDECAR_MAX_BYTES = 64 * 1024
START_MARGIN_S = 300          # a file must be estimated to end at least this long before the deadline
ESTIMATE_FACTOR = 1.5         # ... at this many times its size / the measured rate
ASSUMED_RATE_BPS = 5e6        # the rate assumed before this run has measured one
MAX_CONSECUTIVE_ERRORS = 3
DISK_HEADROOM_BYTES = 10 * 10**9

MANIFEST_NAME = "fetch_manifest.csv"
MANIFEST_FIELDS = ["archive_path", "tier", "study", "size", "method", "expected_sha1", "computed_sha1",
                   "expected_sha256", "computed_sha256", "status", "started", "ended", "bytes_per_s",
                   "local_path", "note"]
# status: verified | bad (kept as .bad) | stopped (local .part left) | error | missing (not in the listing)

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+()=,@-]*$")
_GB = 1e9


class StopFetch(Exception):
    """A clean stop of the run (deadline, working hours, --max-gb, interrupt); the reason is the message."""


def tier_code(tier):
    """``"A2: MFB, a second session ..."`` -> ``"A2"``."""
    return (tier or "").split(":", 1)[0].strip()


def next_work_start(now):
    """The next moment working hours begin (``now`` itself when inside them): 08:00 of the next weekday."""
    if in_working_hours(now):
        return now
    t = now.replace(hour=WORK_START_HOUR, minute=0, second=0, microsecond=0)
    if t <= now:
        t += _dt.timedelta(days=1)
    while t.weekday() not in WORK_DAYS:
        t += _dt.timedelta(days=1)
    return t


def parse_stop_at(text, now):
    """``"HH:MM"`` -> its next occurrence after ``now``."""
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", (text or "").strip())
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        raise ArchiveError(f"--stop-at must be HH:MM, not {text!r}")
    t = now.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
    if t <= now:
        t += _dt.timedelta(days=1)
    return t


def deadline_for(now, stop_at=None):
    """When reading must end: the next 08:00 of a weekday, or ``stop_at`` (a datetime) if earlier."""
    d = next_work_start(now)
    return min(d, stop_at) if stop_at is not None else d


def parse_digest(data, kind):
    """The first ``sha1`` (40-hex) or ``sha256`` (64-hex) digest in a checksum file's bytes, lowercased; '' if none."""
    n = CHECKSUM_HEXLEN[kind]
    m = re.search(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{%d}(?![0-9A-Fa-f])" % n, data.decode("utf-8", "replace"))
    return m.group(0).lower() if m else ""


def load_plan(plan_csv):
    """The pull plan's rows (``pull_plan_<date>.csv`` of the census)."""
    with io.open(plan_csv, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    need = {"tier", "study", "date", "chosen_path", "compression", "size", "checksum"}
    lacking = need - set(rows[0].keys() if rows else ())
    if lacking:
        raise ArchiveError(f"{plan_csv}: not a pull plan (lacks {', '.join(sorted(lacking))})")
    return rows


def select_plan(rows):
    """Split the plan into (pull, skipped). ``pull`` is a list of items in fetch order: tier C first, then
    the rest by date. Each item is the plan's chosen copy of its study. Unknown tiers, paths outside the
    archive root, unsafe names and duplicate destinations are refused (nothing is guessed)."""
    pull, skipped, seen = [], [], set()
    for r in rows:
        code = tier_code(r["tier"])
        if code in SKIP_TIERS:
            skipped.append(r)
            continue
        if code not in PULL_TIERS:
            raise ArchiveError(f"unknown tier {r['tier']!r} ({r['study']}): the plan changed? refusing to guess")
        path = archive_path(r["chosen_path"])
        folder, name = posixpath.split(path)
        year = posixpath.basename(folder)
        if posixpath.dirname(folder) != ARCHIVE_ROOT or not _SAFE_NAME.match(year) or not _SAFE_NAME.match(name):
            raise ArchiveError(f"unexpected archive path {path!r} ({r['study']})")
        checksum = (r["checksum"] or "").strip()
        if checksum and checksum not in CHECKSUM_HEXLEN:
            raise ArchiveError(f"unknown checksum kind {checksum!r} ({r['study']})")
        key = (year.lower(), name.lower())
        if path in seen or key in seen:
            raise ArchiveError(f"two plan rows fetch the same archive: {path}")
        seen.update((path, key))
        pull.append({"tier": code, "study": r["study"], "date": r["date"], "path": path, "folder": year,
                     "name": name, "size": int(r["size"] or 0), "checksum": checksum,
                     "compression": r["compression"]})
    pull.sort(key=lambda it: (it["tier"] != "C", it["date"], it["study"]))
    return pull, skipped


def local_paths(dest, item):
    """(folder, final, .part, .bad) on LOCAL disk for one item."""
    d = os.path.join(dest, item["folder"])
    final = os.path.join(d, item["name"])
    return d, final, final + ".part", final + ".bad"


def check_local_dest(dest):
    """Refuse a network destination (UNC, or a mapped network drive): everything written stays local."""
    p = os.path.abspath(dest)
    if p.startswith("\\\\") or p.startswith("//"):
        raise ArchiveError(f"--dest must be a local disk, not a network path: {dest}")
    drive = os.path.splitdrive(p)[0]
    if drive and os.name == "nt":
        try:
            import ctypes
            if ctypes.windll.kernel32.GetDriveTypeW(drive + "\\") == 4:  # DRIVE_REMOTE
                raise ArchiveError(f"--dest must be a local disk, not the network drive {drive}")
        except (ImportError, AttributeError, OSError):
            pass
    return p


class Manifest:
    """``<dest>\\fetch_manifest.csv``: append-only, one row per attempt; the last row per archive wins."""

    def __init__(self, path):
        self.path = path

    def latest(self):
        out = {}
        if os.path.isfile(self.path):
            with io.open(self.path, encoding="utf-8", newline="") as fh:
                for r in csv.DictReader(fh):
                    if r.get("archive_path"):
                        out[r["archive_path"]] = r
        return out

    def append(self, row):
        new = not os.path.isfile(self.path) or os.path.getsize(self.path) == 0
        if not new:
            with io.open(self.path, "rb") as fh:
                fh.seek(-1, os.SEEK_END)
                torn = fh.read(1) not in (b"\n", b"\r")
        with io.open(self.path, "a", encoding="utf-8", newline="") as fh:
            if not new and torn:
                fh.write("\r\n")
            w = csv.DictWriter(fh, fieldnames=MANIFEST_FIELDS)
            if new:
                w.writeheader()
            w.writerow({k: row.get(k, "") for k in MANIFEST_FIELDS})
            fh.flush()
            os.fsync(fh.fileno())


def is_verified(item, latest, dest):
    r = latest.get(item["path"])
    if not r or r.get("status") != "verified":
        return False
    final = local_paths(dest, item)[1]
    return os.path.isfile(final) and str(os.path.getsize(final)) == r.get("size")


def verify_tar_listing(path, chunk=CHUNK_BYTES):
    """Integrity where the archive has no checksum file (Ryan's Q6): decompress the whole LOCAL file with
    gzip / lzma (their own CRC / check runs at the end of the stream) and list every tar member, reading
    each member's data. Returns (ok, note)."""
    with io.open(path, "rb") as fh:
        magic = fh.read(6)
    if magic[:2] == b"\x1f\x8b":
        opener = gzip.open
    elif magic == b"\xfd7zXZ\x00":
        opener = lzma.open
    else:
        return False, "neither gzip nor xz"
    members = data = 0
    try:
        with opener(path, "rb") as z:
            with tarfile.open(fileobj=z, mode="r|") as tf:
                for m in tf:
                    members += 1
                    if m.isfile():
                        f = tf.extractfile(m)
                        while True:
                            b = f.read(chunk)
                            if not b:
                                break
                            data += len(b)
            while z.read(chunk):  # to the end of the compressed stream, so its check is run
                pass
    except (tarfile.TarError, EOFError, OSError, lzma.LZMAError, zlib.error) as exc:
        return False, f"{type(exc).__name__}: {exc} (after {members} members)"
    if not members:
        return False, "the tar holds no members"
    return True, f"{members} tar members, {data} bytes"


def preflight(archive, items):
    """LIST the year folders the items live in (no contents). Returns {archive path: attrs}."""
    listed = {}
    for folder in sorted({posixpath.dirname(it["path"]) for it in items}):
        for a in archive.listdir_attr(folder):
            listed[posixpath.join(folder, a.filename)] = a
    return listed


def _listed_file(listed, path):
    a = listed.get(path)
    return a if a is not None and _stat.S_ISREG(getattr(a, "st_mode", 0) or 0) else None


def _fmt_gb(n):
    return f"{n / _GB:,.2f} GB"


def plan_summary(pull, skipped):
    """Lines: counts and GB per pulled tier (checksum kinds), and the tiers not pulled."""
    lines = ["pull, by tier (fetch order):"]
    for code in PULL_TIERS:
        its = [it for it in pull if it["tier"] == code]
        kinds = {}
        for it in its:
            kinds[it["checksum"] or "none"] = kinds.get(it["checksum"] or "none", 0) + 1
        ks = ", ".join(f"{k} {v}" for k, v in sorted(kinds.items()))
        lines.append(f"  {code:<3} {len(its):>4} archives  {_fmt_gb(sum(it['size'] for it in its)):>11}"
                     f"   checksum beside: {ks or '-'}")
    comp = {}
    for it in pull:
        comp[it["compression"]] = comp.get(it["compression"], 0) + 1
    lines.append(f"  all {len(pull):>4} archives  {_fmt_gb(sum(it['size'] for it in pull)):>11}   "
                 + ", ".join(f"{k} {v}" for k, v in sorted(comp.items())))
    sk = {}
    for r in skipped:
        c = tier_code(r["tier"])
        n, b = sk.get(c, (0, 0))
        sk[c] = (n + 1, b + int(r["size"] or 0))
    lines.append("not pulled: " + "; ".join(f"{c} {n} ({_fmt_gb(b)})" for c, (n, b) in sorted(sk.items())))
    return lines


def dry_run(archive, pull, skipped, dest, log=print):
    """Counts and GB per tier, what the manifest already holds, and a LISTING check (no contents read)."""
    for line in plan_summary(pull, skipped):
        log(line)
    latest = Manifest(os.path.join(dest, MANIFEST_NAME)).latest()
    done = [it for it in pull if is_verified(it, latest, dest)]
    left = [it for it in pull if it not in done]
    left_b = sum(it["size"] for it in left)
    log(f"already verified in {os.path.join(dest, MANIFEST_NAME)}: {len(done)}; left {len(left)} "
        f"({_fmt_gb(left_b)}): about {left_b / 10e6 / 3600:.1f} h at 10 MB/s, {left_b / 20e6 / 3600:.1f} h at 20 MB/s")
    calls0 = archive.calls
    listed = preflight(archive, pull)
    missing, differ, side_missing, side = [], [], [], {"sha1": 0, "sha256": 0}
    for it in pull:
        a = _listed_file(listed, it["path"])
        if a is None:
            missing.append(it)
            continue
        if getattr(a, "st_size", None) != it["size"]:
            differ.append((it, getattr(a, "st_size", None)))
        if it["checksum"]:
            side[it["checksum"]] += 1
            if _listed_file(listed, it["path"] + "." + it["checksum"]) is None:
                side_missing.append(it)
    nf = len({posixpath.dirname(it["path"]) for it in pull})
    log(f"listing (no contents read): {nf} folders, {archive.calls - calls0} remote calls: "
        f"{len(pull) - len(missing)} of {len(pull)} archives present, {len(differ)} with a size other than the plan's, "
        f"{len(missing)} missing; checksum files present: "
        + ", ".join(f"{k} {side[k] - sum(1 for i in side_missing if i['checksum'] == k)}/{side[k]}" for k in side))
    for it in missing[:20]:
        log(f"  MISSING {it['path']}")
    for it, s in differ[:20]:
        log(f"  SIZE {it['path']}: plan {it['size']}, listed {s}")
    for it in side_missing[:20]:
        log(f"  NO CHECKSUM FILE {it['path']}.{it['checksum']}")
    log("first in fetch order: " + ", ".join(f"{it['tier']} {it['name']}" for it in pull[:3]))
    try:
        free = shutil.disk_usage(_existing_ancestor(dest)).free
        log(f"free on the destination's disk: {_fmt_gb(free)}")
    except OSError:
        pass
    return {"missing": len(missing), "size_differs": len(differ), "checksum_files_missing": len(side_missing),
            "already_verified": len(done), "left": len(left), "left_bytes": left_b}


def _existing_ancestor(p):
    p = os.path.abspath(p)
    while not os.path.isdir(p) and os.path.dirname(p) != p:
        p = os.path.dirname(p)
    return p


def fetch_one(archive, item, dest, size, manifest, now, deadline, chunk=CHUNK_BYTES):
    """Download one archive to a LOCAL ``.part`` (SHA-1 while reading), verify it, rename it locally.

    Returns the manifest row. Raises :class:`StopFetch` after recording a ``stopped`` row (the deadline or
    the working-hours guard tripped mid-file, or an interrupt): only the local ``.part`` is left."""
    folder, final, part, bad = local_paths(dest, item)
    row = {"archive_path": item["path"], "tier": item["tier"], "study": item["study"], "size": size,
           "method": item["checksum"] or "crc+listing", "started": now().isoformat(timespec="seconds"),
           "local_path": final}
    os.makedirs(folder, exist_ok=True)
    expected = ""
    if item["checksum"]:
        with archive.open(item["path"] + "." + item["checksum"]) as sf:
            side = sf.read(SIDECAR_MAX_BYTES)
        with io.open(final + "." + item["checksum"], "wb") as out:  # a local copy, kept beside the archive
            out.write(side)
        expected = parse_digest(side, item["checksum"])
        row["expected_" + item["checksum"]] = expected
        if not expected:
            row.update(status="error", ended=now().isoformat(timespec="seconds"),
                       note=f"no {item['checksum']} digest found in the checksum file ({len(side)} bytes)")
            return row
    h1 = hashlib.sha1()
    h256 = hashlib.sha256() if item["checksum"] == "sha256" else None
    n, t0, stop = 0, time.monotonic(), None
    try:
        with archive.open(item["path"]) as rf, io.open(part, "wb") as out:
            while True:
                if now() >= deadline:
                    stop = f"the deadline {deadline:%a %H:%M} was reached mid-file"
                    break
                b = rf.read(chunk)
                if not b:
                    break
                out.write(b)
                h1.update(b)
                if h256 is not None:
                    h256.update(b)
                n += len(b)
            out.flush()
            os.fsync(out.fileno())
    except WorkingHoursError as exc:
        stop = f"the working-hours guard tripped mid-file ({exc})"
    except KeyboardInterrupt:
        stop = "interrupted"
    secs = time.monotonic() - t0
    row.update(ended=now().isoformat(timespec="seconds"), computed_sha1=h1.hexdigest() if stop is None else "",
               bytes_per_s=int(n / secs) if secs > 0 else "", _secs=secs)
    if stop is not None:
        row.update(status="stopped", note=f"{stop}; {n} of {size} bytes in the local .part (a re-run restarts it)",
                   local_path=part)
        manifest.append(row)
        raise StopFetch(stop)
    if h256 is not None:
        row["computed_sha256"] = h256.hexdigest()
    notes = []
    if n != size:
        ok = False
        notes.append(f"read {n} bytes, the listing says {size}")
    elif item["checksum"] == "sha1":
        ok = row["computed_sha1"] == expected
    elif item["checksum"] == "sha256":
        ok = row["computed_sha256"] == expected
    else:
        ok, note = verify_tar_listing(part, chunk)
        notes.append(note)
    if ok:
        os.replace(part, final)
        row.update(status="verified")
    else:
        os.replace(part, bad)
        row.update(status="bad", local_path=bad)
        if item["checksum"] and n == size:
            notes.append(f"{item['checksum']} differs from the checksum file")
    row["note"] = "; ".join(notes)
    return row


def fetch(archive, pull, dest, *, now=None, stop_at=None, max_bytes=None, retry_bad=False, log=print,
          log_every=10, chunk=CHUNK_BYTES, margin_s=START_MARGIN_S, assumed_bps=ASSUMED_RATE_BPS):
    """Download ``pull`` (from :func:`select_plan`) to LOCAL ``dest``, sequentially, on ``archive``.

    Refuses to start in working hours. The deadline is the next 08:00 of a weekday, or ``stop_at`` (a
    datetime) if earlier: no file is started unless it is estimated (``ESTIMATE_FACTOR`` x size / the
    measured rate, + ``margin_s``) to end before it, and a file still being read at the deadline is stopped
    there. Returns a summary dict (counts by status, bytes, the stop reason)."""
    now = now or _dt.datetime.now
    t = now()
    if in_working_hours(t):
        raise WorkingHoursError(f"fetch reads file contents: refused 08:00-18:00 Monday-Friday (now {t:%a %H:%M}); "
                                "use --dry-run to list")
    deadline = deadline_for(t, stop_at)
    dest = check_local_dest(dest)
    os.makedirs(dest, exist_ok=True)
    manifest = Manifest(os.path.join(dest, MANIFEST_NAME))
    latest = manifest.latest()
    todo = [it for it in pull if not is_verified(it, latest, dest)
            and (retry_bad or (latest.get(it["path"]) or {}).get("status") != "bad")]
    n_bad_kept = sum(1 for it in pull if (latest.get(it["path"]) or {}).get("status") == "bad"
                     and not is_verified(it, latest, dest)) if not retry_bad else 0
    todo_b = sum(it["size"] for it in todo)
    free = shutil.disk_usage(dest).free
    if free < todo_b + DISK_HEADROOM_BYTES:
        raise ArchiveError(f"not enough space on {dest}: {_fmt_gb(free)} free, {_fmt_gb(todo_b)} to fetch")
    log(f"fetch: {len(pull)} planned, {len(pull) - len(todo) - n_bad_kept} already verified, {n_bad_kept} kept as .bad "
        f"(--retry-bad retries them), {len(todo)} to fetch ({_fmt_gb(todo_b)}); deadline {deadline:%a %Y-%m-%d %H:%M}")
    listed = preflight(archive, todo) if todo else {}
    stats = {"verified": 0, "bad": 0, "stopped": 0, "error": 0, "missing": 0}
    run_b, run_s, left_b, consecutive, stop_reason = 0, 0.0, todo_b, 0, ""
    for i, it in enumerate(todo, 1):
        a = _listed_file(listed, it["path"])
        if a is None:
            manifest.append({"archive_path": it["path"], "tier": it["tier"], "study": it["study"], "size": it["size"],
                             "status": "missing", "started": now().isoformat(timespec="seconds"),
                             "note": "not in the archive's listing"})
            stats["missing"] += 1
            left_b -= it["size"]
            log(f"[{i}/{len(todo)}] MISSING {it['path']}")
            continue
        size = int(getattr(a, "st_size", it["size"]))
        if max_bytes is not None and run_b + size > max_bytes:
            stop_reason = f"--max-gb {max_bytes / _GB:g} reached"
            break
        rate = run_b / run_s if run_s > 0 and run_b > 0 else assumed_bps
        t = now()
        est = size / rate * ESTIMATE_FACTOR + margin_s
        if in_working_hours(t) or t + _dt.timedelta(seconds=est) > deadline:
            stop_reason = (f"not starting {it['name']} ({_fmt_gb(size)}, about {est / 60:.0f} min with margin): "
                           f"it would not end before {deadline:%a %H:%M}")
            break
        try:
            row = fetch_one(archive, it, dest, size, manifest, now, deadline, chunk)
        except StopFetch as exc:
            stats["stopped"] += 1
            stop_reason = str(exc)
            break
        except WorkingHoursError as exc:  # the guard tripped before the archive itself was opened
            stop_reason = f"the working-hours guard tripped ({exc})"
            break
        except ReadOnlyViolation:
            raise
        except Exception as exc:  # noqa: BLE001 -- recorded; the run stops after a few in a row
            row = {"archive_path": it["path"], "tier": it["tier"], "study": it["study"], "size": size,
                   "method": it["checksum"] or "crc+listing", "status": "error",
                   "ended": now().isoformat(timespec="seconds"), "local_path": local_paths(dest, it)[2],
                   "note": f"{type(exc).__name__}: {exc}"}
        manifest.append(row)
        if row["status"] == "error":
            consecutive += 1
        else:
            consecutive = 0
            if row.get("_secs"):
                run_b += size
                run_s += row["_secs"]
        stats[row["status"]] += 1
        left_b -= size
        log(f"[{i}/{len(todo)}] {row['status'].upper():8} {it['tier']:<2} {it['name']} {size / 1e6:,.0f} MB"
            + (f" {int(row['bytes_per_s']) / 1e6:.1f} MB/s" if row.get("bytes_per_s") else "")
            + (f" -- {row['note']}" if row.get("note") and row["status"] != "verified" else ""))
        if consecutive >= MAX_CONSECUTIVE_ERRORS:
            stop_reason = f"{consecutive} errors in a row"
            break
        if log_every and i % log_every == 0:
            r = run_b / run_s if run_s > 0 else 0
            log(f"  progress: {i}/{len(todo)} done this run, {_fmt_gb(run_b)} at {r / 1e6:.1f} MB/s; "
                f"left {_fmt_gb(left_b)}" + (f", about {left_b / r / 3600:.1f} h at this rate" if r else ""))
    else:
        stop_reason = "all planned archives attempted"
    r = run_b / run_s if run_s > 0 else 0
    log(f"fetch ended: {stop_reason}. This run: " + ", ".join(f"{k} {v}" for k, v in stats.items())
        + f"; {_fmt_gb(run_b)} at {r / 1e6:.1f} MB/s; left {_fmt_gb(left_b)}. Manifest: {manifest.path}")
    return dict(stats, bytes=run_b, rate_bps=r, left_bytes=left_b, stop_reason=stop_reason)


def main(argv=None):
    ap = argparse.ArgumentParser(description="READ-ONLY listing of the MRI platform's archive "
                                             f"({ARCHIVE_ROOT}). Nothing is ever written there.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list", help="list the archive into a local csv")
    ls.add_argument("--out", required=True, help="local csv to write")
    ls.add_argument("--root", default=ARCHIVE_ROOT, help="a folder inside the archive root")
    ls.add_argument("--max-depth", type=int, default=2)
    ls.add_argument("--cred-file", default=CRED_FILE)
    fe = sub.add_parser("fetch", help="download the pull plan's archives to LOCAL disk, verified "
                                      "(contents after hours only; --dry-run lists only)")
    fe.add_argument("--plan", required=True, help="the census pull plan csv (pull_plan_<date>.csv)")
    fe.add_argument("--dest", required=True, help=r"local folder, e.g. D:\projects\gjesus3\mri_archive\pull")
    fe.add_argument("--dry-run", action="store_true", help="counts per tier and a listing check; no contents read")
    fe.add_argument("--max-gb", type=float, help="fetch at most this many GB (10^9 bytes) in this run")
    fe.add_argument("--stop-at", metavar="HH:MM", help="end reading by this time (default: 08:00 of the next weekday)")
    fe.add_argument("--retry-bad", action="store_true", help="fetch again the archives recorded as bad")
    fe.add_argument("--log-every", type=int, default=10, help="log the rate and the GB left every N files")
    fe.add_argument("--cred-file", default=CRED_FILE)
    args = ap.parse_args(argv)

    if args.cmd == "list":
        t0 = time.time()
        with connect(args.cred_file) as archive:
            n = write_listing(walk(archive, args.root, args.max_depth), args.out)
            calls = archive.calls
        print(f"listed {n} entries in {calls} remote calls ({time.time() - t0:.1f}s) -> {args.out}")
        return 0

    dest = check_local_dest(args.dest)
    pull, skipped = select_plan(load_plan(args.plan))
    if args.dry_run:
        print(f"DRY RUN (listing only, no contents): plan {args.plan}, dest {dest}")
        with connect(args.cred_file) as archive:
            dry_run(archive, pull, skipped, dest)
        return 0
    start = _dt.datetime.now()
    if in_working_hours(start):
        print(f"refused: fetch reads file contents, and it is {start:%a %H:%M} (08:00-18:00 Monday-Friday). "
              "Use --dry-run to list.")
        return 1
    stop_at = parse_stop_at(args.stop_at, start) if args.stop_at else None
    os.makedirs(dest, exist_ok=True)
    log_path = os.path.join(dest, f"fetch_{start:%Y%m%d_%H%M%S}.log")
    with io.open(log_path, "a", encoding="utf-8") as lf:
        def log(msg):
            line = f"{_dt.datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
            print(line, flush=True)
            lf.write(line + "\n")
            lf.flush()
        log(f"plan {args.plan}; dest {dest}; log {log_path}")
        for line in plan_summary(pull, skipped):
            log(line)
        with connect(args.cred_file, log=log) as archive:
            res = fetch(archive, pull, dest, stop_at=stop_at,
                        max_bytes=int(args.max_gb * _GB) if args.max_gb is not None else None,
                        retry_bad=args.retry_bad, log=log, log_every=args.log_every)
            log(f"remote calls: {archive.calls}")
    return 2 if (res["bad"] or res["error"] or res["missing"]) else 0


if __name__ == "__main__":
    sys.exit(main())
