"""Deferred project-hard-link worklist for acquisitions whose link couldn't be made.

The project link is a hard link (or folder of per-file hard links) placed in
`<project>/raw_linked/` — zero extra storage, same inode as the raw primary
(`tools/ingest/linker.py::create_hardlink`). Hard links require a hard-link-capable
mount: NTFS/SMB **from Windows** works (proven by the historical load), but **macOS
over SMB returns `ENOTSUP` (`[Errno 45]`)** — the NI acquisition console is a Mac, so
an on-box NI ingest registers every acquisition fine but **cannot** create the
`raw_linked/` link. Before this worklist, that failure only WARNed and scrolled past,
leaving no record of which acquisitions still needed linking.

When `create_hardlink` raises, the ingest still commits the acquisition (raw copy +
checksums + metadata + subjects + registry row are all written) and then queues the
acquisition HERE. A later **`tools/relink_pending.py` pass on a hard-link-capable
machine** (the Windows workstation, mounting the same NAS) reads this list and creates
the real hard link for each row, then flips `status` to `linked`.

WHY each field: the recovery pass needs to recreate `linker.create_hardlink(
project_folder_abs, link_name, raw_primary_abs)` exactly — so we record the resolved
`link_name`, the `raw_primary_canonical` (`/raw/...` the link points at), the
`primary_kind` (file ⇒ single link; folder ⇒ folder-of-per-file-links), and the
`project_id` (→ its `folder_location` via `registry_projects.csv`). `reason`/`host_os`
are diagnostics (so it's clear the Mac-SMB `ENOTSUP` is what deferred it).

Mirrors `tools/ingest/pending_dicom.py`: BOM-tolerant, header-checked, read-all/
write-all atomically, idempotent on `acq_id` (status preserved across re-ingests).
"""

import csv
import os
from datetime import datetime

from . import csv_safe

PENDING_LINKS_FILENAME = "pending_links.csv"

# Keep in sync with the columns written below + the defensive header check.
PENDING_LINKS_FIELDS = [
    "acq_id",                 # the registered acquisition needing a project link
    "project_id",             # PROJ-XXXX the link belongs in (-> folder_location)
    "link_name",              # resolved link_filename: -> raw_linked/<link_name>
    "raw_primary_canonical",  # /raw/... path the link points at (the link source)
    "primary_kind",           # "file" | "folder" (folder => folder of per-file links)
    "reason",                 # OSError text + errno (e.g. "ENOTSUP [Errno 45]")
    "host_os",                # platform that hit the failure (e.g. "darwin")
    "queued_datetime",
    "status",                 # "pending" | (relink pass sets "linked")
]


def _now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def pending_links_path(registries_dir):
    return os.path.join(registries_dir, PENDING_LINKS_FILENAME)


def read_pending_links(path):
    """Rows of the worklist, or [] if it doesn't exist (BOM-tolerant)."""
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _assert_header(path):
    """Raise if an existing file's header != PENDING_LINKS_FIELDS."""
    if not os.path.isfile(path):
        return
    existing = csv_safe.read_header(path)  # BOM-tolerant
    if existing and existing != PENDING_LINKS_FIELDS:
        raise RuntimeError(
            f"{PENDING_LINKS_FILENAME} header mismatch:\n"
            f"  file has {len(existing)}: {existing}\n"
            f"  code expects {len(PENDING_LINKS_FIELDS)}: {PENDING_LINKS_FIELDS}\n"
            "Migrate the file before ingesting."
        )


def _write_all(path, rows):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    # Atomic temp+replace so a crash mid-write never truncates the worklist.
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PENDING_LINKS_FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in PENDING_LINKS_FIELDS})
    os.replace(tmp, path)


def append_pending_link(registries_dir, acq_id, project_id, link_name,
                        raw_primary_canonical, primary_kind, reason="",
                        host_os="", queued_at=None):
    """Queue (or refresh) an acquisition whose project hard link couldn't be made.

    Idempotent on `acq_id`: a re-ingest refreshes the recovery fields but preserves
    `status` (so a row the relink pass already marked "linked" is never reset to
    "pending"). New rows get status="pending".

    Returns the absolute path written.
    """
    path = pending_links_path(registries_dir)
    _assert_header(path)
    rows = read_pending_links(path)
    queued_at = queued_at or _now_iso()

    by_id = {r.get("acq_id"): r for r in rows}
    if acq_id in by_id:
        r = by_id[acq_id]
        r["project_id"] = project_id
        r["link_name"] = link_name
        r["raw_primary_canonical"] = raw_primary_canonical
        r["primary_kind"] = primary_kind
        r["reason"] = reason
        r["host_os"] = host_os
        r["queued_datetime"] = queued_at
        # status intentionally preserved.
    else:
        rows.append({
            "acq_id": acq_id,
            "project_id": project_id,
            "link_name": link_name,
            "raw_primary_canonical": raw_primary_canonical,
            "primary_kind": primary_kind,
            "reason": reason,
            "host_os": host_os,
            "queued_datetime": queued_at,
            "status": "pending",
        })

    _write_all(path, rows)
    return path
