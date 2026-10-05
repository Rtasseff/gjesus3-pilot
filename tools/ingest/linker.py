"""Create links / manifests for project folder references.

Outputs:
- manifest: append-only CSV mapping original names to ACQ-IDs and canonical paths.
- hardlink (CURRENT, 2026-06-02): NTFS/SMB hard link placed in
  <project>/raw_linked/ named like the acquisition's chosen link name (the
  resolved `link_filename:`, no extension). The project copy IS a real file
  identical to the raw primary — same inode, zero extra storage, and it
  carries raw's single security descriptor (set raw read-only and the link is
  read-only too). For folder-primary acquisitions (`<ACQ-ID>.data/` for
  internal MRI + NI) directories cannot be hard-linked on Windows, so the
  link is a REAL folder filled with one hard link per file. See
  `create_hardlink` and tasks.md §3.1 for the decision record. A link name
  that is already taken is refused (`LinkCollisionError`), never merged into
  (2026-10-05; `inspect_link_target` is the read-only check).
- lnk (LEGACY, superseded): Windows .lnk shortcut targeting the primary via
  UNC path, created via PowerShell WScript.Shell. Kept for reference / the
  porting seam; `create_hardlink` is the path used by ingest. Researchers
  adopt the real-file hard links better than shortcuts.
"""

import csv
import os
import subprocess
import sys

from . import csv_safe


def create_manifest_entry(manifest_path, acq_id, original_name, canonical_path):
    """Append an entry to the ingest manifest CSV.

    The manifest tracks the mapping from original source names
    to ingested ACQ-IDs and paths.
    """
    file_exists = os.path.exists(manifest_path)

    fieldnames = ["acq_id", "original_name", "canonical_path"]
    # Trailing-newline guard (csv_safe): never concatenate onto a last row that
    # lost its newline through an Excel round-trip.
    csv_safe.ensure_trailing_newline(manifest_path)
    with open(manifest_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "acq_id": acq_id,
            "original_name": original_name,
            "canonical_path": canonical_path,
        })


def lookup_project_folder(projects_registry_path, project_id):
    """Return the folder_location for a project_id, or None if not found.

    folder_location is the NAS-relative path stored in registry_projects.csv,
    e.g. "/projects/lions-cardiac-mri/" (== the project's name; 2026-08-02).
    """
    if not project_id or not os.path.exists(projects_registry_path):
        return None
    # utf-8-sig: tolerate an Excel BOM so the first column key stays
    # "project_id" (not "﻿project_id"), else lookups silently miss.
    with open(projects_registry_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("project_id") == project_id:
                return row.get("folder_location") or None
    return None


def resolve_project(projects_registry_path, name_or_id):
    """Resolve an operator-supplied project reference.

    Returns ``(project_id, name, folder_location)`` — the canonical triple
    from registry_projects.csv — or ``(None, None, None)`` when the registry
    doesn't exist or nothing matches.

    `name_or_id` is matched first as a `project_id` (canonical PROJ-XXXX),
    then against the project's `name` **case-insensitively** (the NAS
    filesystem is case-insensitive, so `ae-biomagune-1022` and
    `AE-biomaGUNE-1022` are the same project). Returning the stored `name`
    is what lets the caller CANONICALIZE casing: an operator who typed a
    lowercase variant, or who referenced the project by id, still gets the
    project's real name recorded downstream.

    Renamed from the old `hint` vocabulary 2026-08-02 (05_PROJECTS "Project
    reference model"): what the operator supplies is the project's name, and
    the column that stores the result is `project_id`.
    """
    if not name_or_id or not os.path.exists(projects_registry_path):
        return None, None, None
    wanted = name_or_id.lower()
    with open(projects_registry_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if (row.get("project_id") == name_or_id
                    or (row.get("name") or "").lower() == wanted):
                return (
                    row["project_id"],
                    row.get("name") or None,
                    row.get("folder_location") or None,
                )
    return None, None, None


def canonical_to_unc(canonical_path, nas_unc_root):
    """Convert a NAS-relative POSIX path to a UNC Windows path.

    canonical_path: e.g. "/raw/DICOM/2021/2021-10/ACQ-20211022-XMRI-001/"
    nas_unc_root:   e.g. "\\\\GJESUS3\\gjesus3" (also accepted: "//GJESUS3/gjesus3"
                    with forward slashes — defensively normalized below)
    Returns:        "\\\\GJESUS3\\gjesus3\\raw\\DICOM\\2021\\2021-10\\ACQ-20211022-XMRI-001"

    Defensive normalization (2026-05-27 fix): the input nas_unc_root is
    normalized to all-backslash form regardless of how it was passed.
    Windows UNCs MUST be all-backslash for `WScript.Shell.CreateShortcut`
    to produce a valid .lnk binary — mixed slashes (e.g.
    "//GJESUS3/gjesus3" from a --nas-unc passed with POSIX-style slashes)
    silently produce a stub .lnk file that Windows Explorer can't
    resolve. See `feedback_unc_root_normalization` memory + the round-8
    `.lnk` regeneration episode for the cautionary tale.
    """
    rel = canonical_path.lstrip("/").rstrip("/").replace("/", "\\")
    # Normalize the root to all-backslash form. Strip leading/trailing
    # separators of any kind, then re-add the canonical leading "\\".
    root = nas_unc_root.replace("/", "\\").strip("\\")
    if not root:
        raise ValueError(
            "nas_unc_root resolves to empty after normalization "
            f"(input was {nas_unc_root!r}); expected something like "
            r"'\\GJESUS3\gjesus3' or '//GJESUS3/gjesus3'."
        )
    return f"\\\\{root}\\{rel}"


class LinkCollisionError(Exception):
    """`raw_linked/<link_name>` is taken by something that is not this acquisition's own files.

    Raised by `create_hardlink` instead of writing into the destination
    (2026-10-05). Before that, a taken name was silently MERGED: a folder
    primary was linked file by file into the other acquisition's folder, and a
    file primary was silently skipped, so the second acquisition got no link
    of its own and no error (stream F, 2026-10-04: 209 production acquisitions).

    Deliberately NOT an `OSError`: ingest Step 12 and `manager/raw_import`
    queue an `OSError` to `registries/pending_links.csv` for a later relink
    pass, and relinking a taken name would only collide again. A collision
    needs a distinct name, which is a person's decision.
    """

    def __init__(self, dest, reason):
        super().__init__(f"project link name already taken: {dest} ({reason})")
        self.dest = dest
        self.reason = reason


# What `inspect_link_target` can say about `raw_linked/<link_name>`.
LINK_FREE = "free"        # nothing there: the link can be created
LINK_OWN = "own"          # exactly this acquisition's files, complete: nothing to do
LINK_PARTIAL = "partial"  # only this acquisition's files (or an empty folder), some missing: completable
LINK_TAKEN = "taken"      # anything else: never written into

PENDING_STANDIN_SUFFIX = ".PENDING-LINK.txt"


def _primary_files(raw_primary_abs):
    """``{relative path: absolute path}`` of a folder primary's files (normcased keys)."""
    out = {}
    for root, _dirs, files in os.walk(raw_primary_abs):
        for fn in files:
            full = os.path.join(root, fn)
            out[os.path.normcase(os.path.relpath(full, raw_primary_abs))] = full
    return out


def _samefile(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def inspect_link_target(project_folder_abs, link_name, raw_primary_abs=None):
    """Read-only: what sits at ``<project>/raw_linked/<link_name>``, and is it this acquisition's?

    Returns ``(state, dest, detail)`` where ``state`` is one of:

    - ``LINK_FREE``: nothing there.
    - ``LINK_OWN``: this acquisition's link, complete. A file primary: the
      same file (``os.path.samefile``). A folder primary: every one of its
      files, each the same file as the raw file at the same relative path,
      and no other file.
    - ``LINK_PARTIAL`` (folder primary only): only this acquisition's own
      files, but not all of them, or an empty folder (an interrupted run, or
      the empty shell a mount that cannot hard-link leaves behind). Completing
      it adds only this acquisition's files, so nothing is merged.
    - ``LINK_TAKEN``: anything else. A different file, another acquisition's
      files (a merge), a folder where a file belongs or the reverse.

    ``raw_primary_abs=None`` is the check a NEW acquisition makes before its
    copy (ingest Step 5.5). Its raw files do not exist yet, so nothing at the
    name can be its own: anything there, even an empty folder, or the
    ``<name>.PENDING-LINK.txt`` stand-in of a link still queued for another
    acquisition, is ``LINK_TAKEN``.

    ``detail`` is a short human-readable reason ("" when free).
    """
    dest = os.path.join(project_folder_abs, "raw_linked", link_name)
    new_acquisition = raw_primary_abs is None or not os.path.exists(raw_primary_abs)
    if not os.path.lexists(dest):
        if new_acquisition and os.path.exists(dest + PENDING_STANDIN_SUFFIX):
            return (LINK_TAKEN, dest,
                    f"claimed by a queued link ({link_name}{PENDING_STANDIN_SUFFIX}, "
                    f"registries/pending_links.csv)")
        return LINK_FREE, dest, ""
    if new_acquisition:
        what = "a folder" if os.path.isdir(dest) else "a file"
        return (LINK_TAKEN, dest,
                f"{what} with this name already exists; a new acquisition's link "
                f"name must be unused")

    if not os.path.isdir(raw_primary_abs):
        # File primary: the one name must be this very file.
        if os.path.isdir(dest):
            return LINK_TAKEN, dest, "a folder sits where this file's link belongs"
        if _samefile(dest, raw_primary_abs):
            return LINK_OWN, dest, "already this acquisition's link"
        return LINK_TAKEN, dest, "a different file has this name"

    # Folder primary: a real folder holding only this acquisition's files.
    if not os.path.isdir(dest):
        return LINK_TAKEN, dest, "a file sits where this acquisition's link folder belongs"
    own = _primary_files(raw_primary_abs)
    present = 0
    foreign = []
    for root, _dirs, files in os.walk(dest):
        for fn in files:
            full = os.path.join(root, fn)
            rel = os.path.normcase(os.path.relpath(full, dest))
            src = own.get(rel)
            if src is not None and _samefile(full, src):
                present += 1
            else:
                foreign.append(os.path.relpath(full, dest))
    if foreign:
        return (LINK_TAKEN, dest,
                f"the folder holds {len(foreign)} file(s) that are not this "
                f"acquisition's, e.g. {foreign[0]!r}")
    if present == len(own):
        return LINK_OWN, dest, "already this acquisition's link"
    return (LINK_PARTIAL, dest,
            f"holds {present} of this acquisition's {len(own)} files and nothing else")


def create_hardlink(project_folder_abs, link_name, raw_primary_abs, dry_run=False):
    """Create a hard link (or folder of hard links) in <project>/raw_linked/.

    This is the CURRENT project-linking mechanism (replaces `create_lnk`,
    2026-06-02). The project copy is a real file identical to the raw primary
    — same inode, zero extra storage — and it shares raw's single security
    descriptor, so a read-only raw file stays read-only through the project
    link even inside a read/write `projects` folder (validated on the live
    QNAP SMB share; see `hardlink_project_links` memory + tasks.md §3.1).

    Dispatch on what the raw primary is:

    - **File primary** (microscopy `.czi`, collaborator `.zip`/`.rar`):
      one hard link at `raw_linked/<link_name>` -> the raw file.
    - **Folder primary** (`<ACQ-ID>.data/` for internal MRI + NI): NTFS/SMB
      forbids hard-linking a directory, so we create a REAL folder
      `raw_linked/<link_name>/` and fill it with one hard link per file from
      the raw `.data/` tree (sub-directories are recreated; files are
      hard-linked). The flat `.data` layout means this is normally a single
      level of DICOMs, but the walk handles nesting defensively.

    **Never merges (2026-10-05).** The destination is inspected first
    (`inspect_link_target`). A name taken by anything that is not exactly this
    acquisition's own files raises `LinkCollisionError` and nothing is
    written. Before this, a taken folder name was filled in with the second
    acquisition's files and a taken file name was skipped, both silently.

    Args:
        project_folder_abs: Absolute local path to the project folder on the
            machine running the script (e.g. ``J:\\gjesus3-data\\projects\\my-project``).
        link_name: Destination name with NO extension — what the legacy `.lnk`
            shortcut was called, minus ``.lnk`` (the resolved ``link_filename:``;
            any trailing slash already stripped by the caller).
        raw_primary_abs: Absolute local path to the acquisition's primary —
            either a single file or the ``<ACQ-ID>.data`` folder. MUST be on
            the same NAS volume as ``project_folder_abs`` (hard links cannot
            cross volumes).
        dry_run: If True, create nothing: return the would-be destination,
            after the same read-only collision check (a taken name still
            raises `LinkCollisionError`).

    Returns:
        Absolute path to the created (or would-be) link / folder.

    Raises:
        LinkCollisionError: If the name is taken by anything that is not
            exactly this acquisition's own files (not an OSError, so callers
            never queue it for a relink).
        RuntimeError: If ``raw_primary_abs`` does not exist.
        OSError: If the hard link cannot be created (e.g. cross-volume, or the
            filesystem does not support hard links).

    Idempotent: re-running for the same acquisition is a no-op when its link
    is complete, and completes a folder-of-links that holds only some of its
    own files (an interrupted run, or an empty shell).
    """
    raw_linked_dir = os.path.join(project_folder_abs, "raw_linked")
    dest = os.path.join(raw_linked_dir, link_name)

    if dry_run:
        if raw_primary_abs and os.path.exists(raw_primary_abs):
            state, dest, detail = inspect_link_target(
                project_folder_abs, link_name, raw_primary_abs)
            if state == LINK_TAKEN:
                raise LinkCollisionError(dest, detail)
        return dest

    if not os.path.exists(raw_primary_abs):
        raise RuntimeError(
            f"raw primary not found, cannot hard-link: {raw_primary_abs!r}"
        )

    state, dest, detail = inspect_link_target(project_folder_abs, link_name, raw_primary_abs)
    if state == LINK_TAKEN:
        raise LinkCollisionError(dest, detail)
    if state == LINK_OWN:
        return dest

    os.makedirs(raw_linked_dir, exist_ok=True)

    if os.path.isdir(raw_primary_abs):
        # Folder primary -> real folder of per-file hard links. The folder is
        # free, or holds only this acquisition's own files (checked above).
        os.makedirs(dest, exist_ok=True)
        for root, _dirs, files in os.walk(raw_primary_abs):
            rel = os.path.relpath(root, raw_primary_abs)
            target_dir = dest if rel == "." else os.path.join(dest, rel)
            os.makedirs(target_dir, exist_ok=True)
            for fn in files:
                src_f = os.path.join(root, fn)
                dst_f = os.path.join(target_dir, fn)
                if not os.path.exists(dst_f):
                    os.link(src_f, dst_f)
        return dest

    # File primary -> single hard link (the name is free: checked above).
    os.link(raw_primary_abs, dest)
    return dest


def create_lnk(
    project_folder_abs,
    original_name,
    target_unc_path,
    description="",
    dry_run=False,
    working_dir_unc=None,
):
    """Create a Windows .lnk shortcut in <project>/raw_linked/.

    LEGACY / superseded by `create_hardlink` (2026-06-02). Retained for the
    porting seam and historical reference; ingest no longer calls this.

    Uses PowerShell's WScript.Shell COM object so the resulting shortcut
    is fully Explorer-compatible (correct icon, double-click open, etc.).
    Windows-only.

    Args:
        project_folder_abs: Absolute path to the project folder on the
            machine running the script (e.g. \\\\GJESUS3\\gjesus3\\projects\\my-project\\).
        original_name: Source archive name; used as the shortcut's filename
            with ".lnk" appended (e.g. "LEONE_1.01.zip" -> "LEONE_1.01.zip.lnk").
        target_unc_path: UNC path the shortcut should open. If this points
            at a file (e.g. an archive), Explorer renders the file's icon
            and double-click opens that file. If it points at a folder,
            Explorer opens the folder.
        description: Optional shortcut description (shown in tooltip).
        dry_run: If True, return the would-be path without creating anything.
        working_dir_unc: WorkingDirectory to set on the shortcut. Defaults
            to the parent of target_unc_path when target is a file, or
            target_unc_path itself when target is a folder.

    Returns:
        Absolute path to the created (or would-be) .lnk file.

    Raises:
        RuntimeError: If not on Windows, or if PowerShell invocation fails.
    """
    raw_linked_dir = os.path.join(project_folder_abs, "raw_linked")
    lnk_path = os.path.join(raw_linked_dir, f"{original_name}.lnk")

    if os.path.exists(lnk_path):
        return lnk_path  # idempotent: already there

    if dry_run:
        return lnk_path

    if sys.platform != "win32":
        raise RuntimeError(
            "create_lnk requires Windows (uses PowerShell WScript.Shell). "
            "Run ingest_raw.py from a Windows machine, or pass --nas-unc '' "
            "to skip .lnk creation."
        )

    os.makedirs(raw_linked_dir, exist_ok=True)

    if working_dir_unc is None:
        # If target ends with a backslash treat it as a folder; else use parent.
        if target_unc_path.endswith("\\"):
            working_dir_unc = target_unc_path.rstrip("\\")
        else:
            working_dir_unc = os.path.dirname(target_unc_path)

    desc = description or f"Raw acquisition: {original_name}"

    # PowerShell single-quoted strings treat backslashes literally; the only
    # character we have to escape is the single quote itself (doubled).
    def _ps_quote(s):
        return "'" + s.replace("'", "''") + "'"

    ps_script = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$lnk = $ws.CreateShortcut({_ps_quote(lnk_path)}); "
        f"$lnk.TargetPath = {_ps_quote(target_unc_path)}; "
        f"$lnk.WorkingDirectory = {_ps_quote(working_dir_unc)}; "
        f"$lnk.Description = {_ps_quote(desc)}; "
        "$lnk.Save()"
    )

    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy", "Bypass",
            "-Command", ps_script,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"PowerShell shortcut creation failed: {result.stderr.strip() or result.stdout.strip()}"
        )
    return lnk_path
