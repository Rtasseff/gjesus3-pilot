"""Tests for tools/relink_pending.py, the drain of the deferred project-link worklist.

Scratch folders only: no NAS, no network. Run: python tools/test_relink_pending.py
"""
import csv
import os
import sys
import tempfile
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))
import relink_pending
from ingest import linker, locking, pending_links as pl

_fail = 0
PROJECT = "PROJ-0001"
FOLDER = "/projects/AE-biomaGUNE-0324"


def check(cond, msg):
    global _fail
    print(("  ok:   " if cond else "  FAIL: ") + msg)
    if not cond:
        _fail += 1


def make_nas(root):
    reg = os.path.join(root, "registries")
    os.makedirs(reg)
    os.makedirs(os.path.join(root, "projects", "AE-biomaGUNE-0324", "raw_linked"))
    with open(os.path.join(reg, "registry_projects.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["project_id", "name", "folder_location"])
        w.writerow([PROJECT, "AE-biomaGUNE-0324", FOLDER])
    return reg


def queue(root, reg, acq):
    """A scan in /raw/ whose link the Mac could not make, as a sync leaves it."""
    rel = f"raw/DICOM/2026/2026-02/{acq}/{acq}.data/recon0.dcm"
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        f.write("synthetic " + acq)
    link = f"CT_{acq}"
    pl.append_pending_link(reg, acq_id=acq, project_id=PROJECT, link_name=link,
                           raw_primary_canonical="/" + rel, primary_kind="file",
                           reason="OSError [Errno 45]", host_os="darwin")
    stand_in = os.path.join(root, "projects", "AE-biomaGUNE-0324", "raw_linked",
                            f"{link}.PENDING-LINK.txt")
    with open(stand_in, "w", encoding="utf-8") as f:
        f.write("pending")
    return path, stand_in


def run(root):
    return relink_pending.main(["relink_pending.py", "--nas-root", root])


def statuses(reg):
    return {r["acq_id"]: r["status"] for r in pl.read_pending_links(pl.pending_links_path(reg))}


print("1. the drain: link made, stand-in gone, row marked, provenance written")
with tempfile.TemporaryDirectory() as root:
    reg = make_nas(root)
    raw, stand_in = queue(root, reg, "ACQ-20260212-CT-001")
    rc = run(root)
    links = [n for n in os.listdir(os.path.dirname(stand_in)) if not n.endswith(".txt")]
    check(rc == 0, "exit 0")
    check(statuses(reg) == {"ACQ-20260212-CT-001": "linked"}, "row marked linked, not removed")
    check(not os.path.exists(stand_in), "stand-in removed")
    check(len(links) == 1 and os.path.samefile(
        os.path.join(os.path.dirname(stand_in), links[0]), raw), "a true hard link to the raw file")
    check(os.path.exists(os.path.join(os.path.dirname(os.path.dirname(stand_in)), "provenance.csv")),
          "provenance written")
    check(run(root) == 0 and statuses(reg) == {"ACQ-20260212-CT-001": "linked"},
          "a second run is a no-op")

print("2. a sync queues a row while the drain is running: the row survives")
with tempfile.TemporaryDirectory() as root:
    reg = make_nas(root)
    queue(root, reg, "ACQ-20260212-CT-001")
    real = linker.create_hardlink

    def link_then_sync_queues(*a, **k):
        out = real(*a, **k)
        if "ACQ-20260212-CT-002" not in statuses(reg):
            queue(root, reg, "ACQ-20260212-CT-002")
        return out

    with mock.patch.object(linker, "create_hardlink", side_effect=link_then_sync_queues):
        rc = run(root)
    check(rc == 0, "exit 0")
    check(statuses(reg) == {"ACQ-20260212-CT-001": "linked", "ACQ-20260212-CT-002": "pending"},
          "the row queued mid-run is kept, still pending")
    check(run(root) == 0 and set(statuses(reg).values()) == {"linked"}, "the next run links it")

print("3. the status write holds the registry lock; the linking does not")
with tempfile.TemporaryDirectory() as root:
    reg = make_nas(root)
    queue(root, reg, "ACQ-20260212-CT-001")
    lock_file = os.path.join(reg, locking.LOCK_FILENAME)
    seen = {}
    real_link, real_write = linker.create_hardlink, pl._write_all

    def spy_link(*a, **k):
        seen["link"] = os.path.exists(lock_file)
        return real_link(*a, **k)

    def spy_write(*a, **k):
        seen["write"] = os.path.exists(lock_file)
        return real_write(*a, **k)

    with mock.patch.object(linker, "create_hardlink", side_effect=spy_link), \
            mock.patch.object(pl, "_write_all", side_effect=spy_write):
        run(root)
    check(seen.get("link") is False, "no lock held while linking (a sync is not blocked)")
    check(seen.get("write") is True, "lock held for the status write")

print("4. the lock is busy: non-zero exit, the row stays pending, and a re-run recovers")
with tempfile.TemporaryDirectory() as root:
    reg = make_nas(root)
    raw, _ = queue(root, reg, "ACQ-20260212-CT-001")
    with mock.patch.object(locking, "registry_lock", side_effect=locking.LockTimeout("busy")):
        rc = run(root)
    check(rc == 1, "non-zero exit")
    check(statuses(reg) == {"ACQ-20260212-CT-001": "pending"}, "row still pending")
    check(run(root) == 0 and statuses(reg) == {"ACQ-20260212-CT-001": "linked"},
          "the re-run finds the link in place and marks the row")

print("5. a row that cannot be linked: stays pending, non-zero exit, the others still go through")
with tempfile.TemporaryDirectory() as root:
    reg = make_nas(root)
    raw, _ = queue(root, reg, "ACQ-20260212-CT-001")
    queue(root, reg, "ACQ-20260212-CT-002")
    os.remove(raw)
    rc = run(root)
    check(rc == 1, "non-zero exit, so a scheduler can report it")
    check(statuses(reg) == {"ACQ-20260212-CT-001": "pending", "ACQ-20260212-CT-002": "linked"},
          "the bad row stays pending, the good one is marked")

print("6. --dry-run writes nothing")
with tempfile.TemporaryDirectory() as root:
    reg = make_nas(root)
    _, stand_in = queue(root, reg, "ACQ-20260212-CT-001")
    rc = relink_pending.main(["relink_pending.py", "--nas-root", root, "--dry-run"])
    check(rc == 0, "exit 0")
    check(statuses(reg) == {"ACQ-20260212-CT-001": "pending"}, "row untouched")
    check(os.path.exists(stand_in), "stand-in untouched")
    check(os.listdir(os.path.dirname(stand_in)) == [os.path.basename(stand_in)], "no link made")

print("\nALL RELINK-PENDING CHECKS PASSED" if _fail == 0 else f"\n{_fail} CHECK(S) FAILED")
sys.exit(1 if _fail else 0)
