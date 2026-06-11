"""locking.py — a cross-platform lockfile mutex for the registries directory.

Serializes the two registry critical sections of an ingest so concurrent
ingests (two operators, or two batches at once) cannot:
  - mint the same ACQ-ID — acq_id allocation reads max-seq then returns, and
    the registry row isn't written until much later (after the file copy), so
    two ingests can read the same max and both pick seq+1; and
  - interleave a torn line into a registry CSV written over SMB.

Mechanism: an atomic O_EXCL create of ``registries/.registry.lock``. On
``FileExistsError`` the caller spins (short sleep) until it acquires the lock
or ``timeout`` elapses. The lockfile records the holder's pid + ISO timestamp.
A lock older than ``stale_after`` is treated as abandoned (holder crashed) and
reclaimed with a WARN. The lock is always released (lockfile deleted) in a
``finally``. O_EXCL create is atomic on local filesystems and adequately atomic
for this low-contention case over SMB; the stale-break + timeout cover the
crash-with-lock-held case.

Hold the locked section SHORT. In ingest_raw.py the lock is taken twice —
once around ACQ-ID allocation (acq_id.allocate_acq_id, which writes a durable
reservation) and once around registry.append_row — and is NEVER held across
the file copy in between.

Usage:
    from ingest import locking
    with locking.registry_lock(registries_dir):
        acq_id_str = acq_id.allocate_acq_id(date, inst, reg_path, registries_dir)
    # ... copy files (UNLOCKED) ...
    with locking.registry_lock(registries_dir):
        registry.append_row(reg_path, row)

See 06_REGISTRIES.md (Concurrency / locking) and 10_TOOLS.md.
"""

import contextlib
import os
import time
from datetime import datetime, timezone


LOCK_FILENAME = ".registry.lock"


class LockTimeout(RuntimeError):
    """Raised when the registry lock can't be acquired within ``timeout``."""


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_log(msg, level="INFO"):
    print(f"[locking] {level}: {msg}")


def _is_stale(lock_path, stale_after):
    """True if the lockfile exists and is older than ``stale_after`` seconds."""
    try:
        age = time.time() - os.path.getmtime(lock_path)
    except OSError:
        return False
    return age > stale_after


def _break_stale(lock_path, log):
    try:
        os.unlink(lock_path)
        log(f"registry_lock: reclaimed a stale lock ({lock_path})", "WARN")
    except OSError:
        pass  # another waiter just reclaimed / the holder released it — fine


@contextlib.contextmanager
def registry_lock(registries_dir, timeout=60.0, poll=0.2, stale_after=600.0,
                  log=None):
    """Hold an exclusive lock on ``registries_dir`` for the duration of the block.

    Acquire by atomically creating ``registries/.registry.lock``; release by
    deleting it (always, in a ``finally``). Raises :class:`LockTimeout` if the
    lock can't be acquired within ``timeout`` seconds. Keep the held section
    short — never hold it across a file copy.
    """
    log = log or _default_log
    os.makedirs(registries_dir, exist_ok=True)
    lock_path = os.path.join(registries_dir, LOCK_FILENAME)
    deadline = time.monotonic() + timeout
    fd = None
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            break
        except FileExistsError:
            if _is_stale(lock_path, stale_after):
                _break_stale(lock_path, log)
                continue
            if time.monotonic() >= deadline:
                raise LockTimeout(
                    f"could not acquire {lock_path} within {timeout:g}s — "
                    f"another ingest may be writing the registry. If none is, "
                    f"delete the stale lockfile and retry."
                )
            time.sleep(poll)
    try:
        try:
            os.write(fd, f"pid={os.getpid()} acquired={_now_iso()}\n".encode())
        finally:
            os.close(fd)
            fd = None
        yield lock_path
    finally:
        if fd is not None:
            os.close(fd)
        try:
            os.unlink(lock_path)
        except FileNotFoundError:
            pass  # already reclaimed as stale by another waiter — acceptable
