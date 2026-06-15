#!/usr/bin/env python3
"""test_locking.py — registry lock concurrency + reservation safety (F item 8).

Proves the registry lock (ingest/locking.py) + the durable reservation
(ingest/acq_id.allocate_acq_id) make concurrent allocate+append atomic:

  - no two workers mint the same ACQ-ID (the reservation read-modify-write is
    serialized; without the lock, concurrent workers re-read the same max and
    collide),
  - the registry row count == the number of appends (no lost/torn writes),
  - every row parses to the full column width (no interleaved torn lines).

Plus unit checks for stale-lock reclaim, always-released, and timeout.

Run:  PYTHONPATH=tools python tools/ingest/test_locking.py
"""

import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingest import locking, acq_id, registry  # noqa: E402

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok:   {msg}")


def _seed_registry(registries_dir):
    os.makedirs(registries_dir, exist_ok=True)
    path = os.path.join(registries_dir, "registry_raw.csv")
    import csv
    with open(path, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow(registry.REGISTRY_FIELDS)
    return path


def test_concurrent_allocate_append():
    print("[concurrent allocate + append]")
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        registries_dir = os.path.join(d, "registries")
        reg_path = _seed_registry(registries_dir)
        date, inst = "20260211", "CELL"
        n_threads, per_thread = 8, 25
        expected = n_threads * per_thread
        errors = []

        def worker():
            for _ in range(per_thread):
                try:
                    with locking.registry_lock(registries_dir, timeout=30):
                        aid = acq_id.allocate_acq_id(date, inst, reg_path, registries_dir)
                        # A small in-lock pause widens the window the lock must
                        # cover (the allocate read-modify-write + the append).
                        time.sleep(0.001)
                        registry.append_row(reg_path, {
                            "acq_id": aid, "instrument": inst,
                            "data_ecosystem": "MICROSCOPY",
                        })
                except Exception as e:  # noqa: BLE001 - surface any worker failure
                    errors.append(repr(e))

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        check(not errors, f"no worker raised (got {len(errors)}: {errors[:3]})")
        rows = registry.read_registry(reg_path)
        ids = [r["acq_id"] for r in rows]
        check(len(rows) == expected, f"row count == {expected} appends (got {len(rows)})")
        check(len(set(ids)) == len(ids), f"no duplicate ACQ-IDs (got {len(ids) - len(set(ids))} dupes)")
        # Sequence is dense 001..expected (reservation high-water never skipped).
        seqs = sorted(int(i.split("-")[-1]) for i in ids)
        check(seqs == list(range(1, expected + 1)),
              f"sequences are a dense 1..{expected} range")
        widths = {len(r) for r in rows}
        check(widths == {len(registry.REGISTRY_FIELDS)},
              f"every row has {len(registry.REGISTRY_FIELDS)} columns (got {widths})")
        # No lockfile / temp reservation file left behind.
        check(not os.path.exists(os.path.join(registries_dir, locking.LOCK_FILENAME)),
              "lockfile released (not left behind)")


def test_stale_lock_reclaimed():
    print("[stale lock reclaim]")
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        registries_dir = os.path.join(d, "registries")
        os.makedirs(registries_dir)
        lock_path = os.path.join(registries_dir, locking.LOCK_FILENAME)
        with open(lock_path, "w") as f:
            f.write("pid=999999 acquired=stale\n")
        # Backdate it well past stale_after.
        old = time.time() - 5000
        os.utime(lock_path, (old, old))
        acquired = {"ok": False}
        with locking.registry_lock(registries_dir, timeout=5, stale_after=600,
                                   log=lambda *a, **k: None):
            acquired["ok"] = True
        check(acquired["ok"], "a stale lock is reclaimed and acquired")
        check(not os.path.exists(lock_path), "lockfile released after the block")


def test_break_stale_spares_fresh_lock():
    print("[stale-break spares a fresh lock]")
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        registries_dir = os.path.join(d, "registries")
        os.makedirs(registries_dir)
        lock_path = os.path.join(registries_dir, locking.LOCK_FILENAME)
        # A FRESH lock (mtime = now). The steal-by-rename re-check must NOT
        # reclaim it — this is the guard the old bare-unlink lacked, which let
        # two waiters both delete-and-acquire and end up co-holding the lock.
        with open(lock_path, "w") as f:
            f.write("pid=123 acquired=now\n")
        reclaimed = locking._break_stale(lock_path, 600.0, lambda *a, **k: None)
        check(reclaimed is False, "_break_stale returns False for a fresh lock")
        check(os.path.exists(lock_path), "the fresh lock is left in place")
        # And a genuinely stale one IS reclaimed by the same call.
        old = time.time() - 5000
        os.utime(lock_path, (old, old))
        reclaimed2 = locking._break_stale(lock_path, 600.0, lambda *a, **k: None)
        check(reclaimed2 is True, "_break_stale returns True for a stale lock")
        check(not os.path.exists(lock_path), "the stale lock is removed")
        # No sideline temp files left behind.
        leftovers = [n for n in os.listdir(registries_dir)
                     if n.startswith(locking.LOCK_FILENAME + ".stale.")]
        check(not leftovers, f"no .stale sideline files left (got {leftovers})")


def test_always_released_and_reacquire():
    print("[always released / re-acquire]")
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        registries_dir = os.path.join(d, "registries")
        os.makedirs(registries_dir)
        lock_path = os.path.join(registries_dir, locking.LOCK_FILENAME)
        with locking.registry_lock(registries_dir, timeout=5):
            check(os.path.exists(lock_path), "lockfile exists while held")
        check(not os.path.exists(lock_path), "lockfile gone after release")
        # A second sequential acquisition must succeed (always-released).
        with locking.registry_lock(registries_dir, timeout=5):
            check(os.path.exists(lock_path), "re-acquired cleanly after release")


def test_timeout_when_held():
    print("[timeout while held]")
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        registries_dir = os.path.join(d, "registries")
        os.makedirs(registries_dir)
        # Simulate a live holder with a FRESH lockfile (not stale).
        lock_path = os.path.join(registries_dir, locking.LOCK_FILENAME)
        with open(lock_path, "w") as f:
            f.write("pid=123 acquired=now\n")
        raised = False
        try:
            with locking.registry_lock(registries_dir, timeout=0.5, poll=0.05,
                                       stale_after=600, log=lambda *a, **k: None):
                pass
        except locking.LockTimeout:
            raised = True
        check(raised, "LockTimeout raised when the lock is held and not stale")
        os.unlink(lock_path)


def main():
    test_concurrent_allocate_append()
    test_stale_lock_reclaimed()
    test_break_stale_spares_fresh_lock()
    test_always_released_and_reacquire()
    test_timeout_when_held()
    print()
    if FAILS:
        print(f"FAILED ({len(FAILS)}):")
        for m in FAILS:
            print(f"  - {m}")
        return 1
    print("ALL PASS (registry lock + reservation)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
