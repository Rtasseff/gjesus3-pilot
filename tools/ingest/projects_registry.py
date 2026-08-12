"""Read and write `registries/registry_projects.csv` — the projects registry.

The sibling of `registry.py` (which owns `registry_raw.csv`): one home for the
projects-registry column order, the id/uniqueness rules, and the two write
paths. It exists because `create_project.py` was the only writer and did its
append with a bare `csv_safe.ensure_trailing_newline` + `open(..., "a")` — no
header check, no lock, no atomic rewrite. That was tolerable while one Data
Office person ran it from a shell. The Project Manager GUI puts it in front of
several students at once, where an unguarded read-modify-write on a 52-row CSV
over SMB is a lost update waiting to happen.

CONCURRENCY — read this before calling. Like `registry.append_row` /
`registry.update_row`, the functions here do NOT take the lock; the CALLER must
hold ``locking.registry_lock(registries_dir)`` across the whole
read-modify-write, because "pick the next PROJ id" / "is this name taken?" and
the write that acts on the answer are one critical section:

    with locking.registry_lock(registries_dir):
        rows = projects_registry.read_projects(path)
        pid = projects_registry.next_project_id(rows)     # reads max
        ...                                               # decide
        projects_registry.append_row(path, row)           # writes

Keep the held section SHORT — never across a file copy or a hard-link sweep.

Spec: 06_REGISTRIES §4 (projects registry) and 05_PROJECTS §8. This module is
that schema's integrity mirror.
"""

import csv
import os

from . import csv_safe

PROJECTS_FILENAME = "registry_projects.csv"

# Column order is the contract (06_REGISTRIES §4). `name` was RENAMED from
# `short_name` 2026-08-02 — it is the project's human key, case-preserved, and
# the folder name verbatim (05_PROJECTS §2a). When this list changes, the
# defensive header check refuses to write until the CSV is migrated.
PROJECT_REGISTRY_FIELDS = [
    "project_id",
    "name",
    "description",
    "owner",
    "start_date",
    "status",
    "last_activity",
    "folder_location",
    "notes",
]

# The project lifecycle vocabulary (05_PROJECTS §4 + §5 — ✅ DECIDED).
# Live data holds only `active` and `closed`, but `paused` is part of the
# decided lifecycle (§5 sets a 6-month maximum for it), so it is offered.
# Do NOT add a fourth value without a Data Office decision.
STATUS_VALUES = ["active", "paused", "closed"]

# What a researcher may edit after creation. Everything else in the row is
# identity (`project_id`, `name`, `folder_location`) or a derived date —
# `start_date` / `last_activity` mean ACQUISITION dates, not edit dates
# (production update 2026-07-14/15), so an edit must never touch them.
EDITABLE_FIELDS = ["description", "owner", "status", "notes"]


def projects_registry_path(nas_root):
    """Absolute path of the projects registry under a NAS root."""
    return os.path.join(nas_root, "registries", PROJECTS_FILENAME)


def read_projects(path):
    """Read the projects registry -> list of row dicts ([] if absent).

    Tolerant decode, mirroring `registry.read_registry`: prefer UTF-8 (with a
    BOM allowance, so an Excel round-trip can't turn the first key into
    `\\ufeffproject_id` and make every lookup miss), then latin-1 — legacy rows
    were written by `create_project.py` through a cp1252 console and a fixed
    UTF-8 read would crash on them.
    """
    if not os.path.exists(path):
        return []
    for enc in ("utf-8-sig", "latin-1"):
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    return []


def assert_header_compatible(path):
    """Raise RuntimeError if an existing CSV's header != PROJECT_REGISTRY_FIELDS.

    No-op when the file doesn't exist (the writers create it with the right
    header). Silently writing N+1 values into an N-column file shifts every
    subsequent read into the wrong columns.
    """
    if not os.path.exists(path):
        return
    existing = csv_safe.read_header(path)  # BOM-tolerant
    if existing and existing != PROJECT_REGISTRY_FIELDS:
        raise RuntimeError(
            f"projects-registry header mismatch in {path}\n"
            f"  file has {len(existing)} columns: {existing}\n"
            f"  code expects {len(PROJECT_REGISTRY_FIELDS)}: "
            f"{PROJECT_REGISTRY_FIELDS}\n"
            f"  refusing to write (would corrupt column alignment). "
            f"Migrate the CSV before re-running."
        )


def next_project_id(rows):
    """The next `PROJ-NNNN` id, from the maximum already present.

    Ids are never reused — a deleted project keeps its number retired, the same
    rule the ACQ-ID sequence follows.
    """
    max_num = 0
    for row in rows:
        pid = (row.get("project_id") or "").strip()
        if pid.startswith("PROJ-"):
            try:
                num = int(pid.split("-")[1])
            except (ValueError, IndexError):
                continue
            max_num = max(max_num, num)
    return f"PROJ-{max_num + 1:04d}"


def check_name_unique(rows, name):
    """True if `name` is not already taken.

    Case-INSENSITIVE: the name IS the folder name and the NAS filesystem is
    case-insensitive, so two names differing only in case would fight over one
    folder.
    """
    wanted = (name or "").strip().lower()
    return not any((r.get("name") or "").strip().lower() == wanted for r in rows)


def find_project(rows, name_or_id):
    """The row matching a `PROJ-XXXX` id or a project `name` (case-insensitive).

    Returns the row dict, or None. Mirrors `linker.resolve_project`'s matching
    rule so the GUI and the ingest resolve a reference the same way.
    """
    wanted = (name_or_id or "").strip()
    if not wanted:
        return None
    low = wanted.lower()
    for r in rows:
        if (r.get("project_id") or "").strip() == wanted:
            return r
        if (r.get("name") or "").strip().lower() == low:
            return r
    return None


def append_row(path, row_dict):
    """Append one project row. CALLER MUST HOLD the registry lock.

    Creates the file with headers if absent, header-checks an existing one, and
    guards against a missing trailing newline (an Excel round-trip or hand edit
    would otherwise concatenate this row onto the previous last row).
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    file_exists = os.path.exists(path)
    if file_exists:
        assert_header_compatible(path)

    row = {f: row_dict.get(f, "") for f in PROJECT_REGISTRY_FIELDS}
    csv_safe.ensure_trailing_newline(path)
    with open(path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PROJECT_REGISTRY_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
    return row


def update_row(path, project_id, updates, allowed=None):
    """Update fields on ONE project row, matched by `project_id`.

    Read-all / rewrite-all with an atomic temp + `os.replace`, so a crash
    mid-write can't truncate the registry — the same contract as
    `registry.update_row`, which this deliberately mirrors.

    CONCURRENCY: does NOT take the lock. The caller MUST hold
    ``locking.registry_lock(registries_dir)`` across the call — the read and the
    rewrite are one critical section, and this file is only ~50 rows, every one
    of which a bad write would lose.

    Args:
        path: registry_projects.csv.
        project_id: the row to update (the unique key).
        updates: {field: new_value}.
        allowed: optional whitelist of writable field names. Defaults to
            `EDITABLE_FIELDS` — so a caller cannot rewrite `folder_location`
            or stamp `last_activity` by accident. Pass an explicit list (e.g.
            the full field set) when a tool legitimately needs more.

    Returns (found, applied):
        found:   True if a row with `project_id` existed.
        applied: {field: new_value} actually written ({} if nothing changed).

    Raises RuntimeError if the header doesn't match, or if `updates` names a
    field outside `allowed` (a mistyped column would otherwise be a silent
    no-op — or worse, a new column appended to one row only).
    """
    allowed = list(EDITABLE_FIELDS if allowed is None else allowed)
    unknown = [k for k in updates if k not in allowed]
    if unknown:
        raise RuntimeError(
            f"update_row: field(s) {unknown} are not writable here "
            f"(allowed: {allowed}). Refusing to write."
        )
    bad_schema = [k for k in updates if k not in PROJECT_REGISTRY_FIELDS]
    if bad_schema:
        raise RuntimeError(
            f"update_row: field(s) {bad_schema} are not in "
            f"PROJECT_REGISTRY_FIELDS. Refusing to write."
        )
    if not os.path.exists(path):
        return False, {}
    assert_header_compatible(path)

    rows = read_projects(path)
    found, applied = False, {}
    for row in rows:
        if (row.get("project_id") or "").strip() != project_id:
            continue
        found = True
        for field, new_val in updates.items():
            if (row.get(field) or "") == (new_val or ""):
                continue          # no-op: leave the file byte-for-byte alone
            row[field] = new_val
            applied[field] = new_val
        break

    if not found or not applied:
        return found, applied

    # Atomic rewrite: pid-suffixed temp + os.replace. The pid keeps two
    # processes from colliding on one shared temp name (the same reason
    # pending.py does it) — without it, process A's replace can publish B's
    # half-written bytes over the only copy of the projects registry.
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PROJECT_REGISTRY_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in PROJECT_REGISTRY_FIELDS})
    os.replace(tmp, path)
    return found, applied
