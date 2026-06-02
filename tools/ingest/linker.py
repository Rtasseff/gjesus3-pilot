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
  `create_hardlink` and tasks.md §3.1 for the decision record.
- lnk (LEGACY, superseded): Windows .lnk shortcut targeting the primary via
  UNC path, created via PowerShell WScript.Shell. Kept for reference / the
  porting seam; `create_hardlink` is the path used by ingest. Researchers
  adopt the real-file hard links better than shortcuts.
"""

import csv
import os
import subprocess
import sys


def create_manifest_entry(manifest_path, acq_id, original_name, canonical_path):
    """Append an entry to the ingest manifest CSV.

    The manifest tracks the mapping from original source names
    to ingested ACQ-IDs and paths.
    """
    file_exists = os.path.exists(manifest_path)

    fieldnames = ["acq_id", "original_name", "canonical_path"]
    with open(manifest_path, "a", newline="") as f:
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
    e.g. "/projects/proj-lions-cardiac-mri/".
    """
    if not project_id or not os.path.exists(projects_registry_path):
        return None
    with open(projects_registry_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("project_id") == project_id:
                return row.get("folder_location") or None
    return None


def resolve_project(projects_registry_path, hint):
    """Resolve a project hint to (project_id, folder_location).

    Looks up `hint` first as a `project_id` (canonical PROJ-XXXX), then
    falls back to matching `short_name` (case-insensitive). This lets a
    YAML config use `project_hint: discovered.project` where the parsed
    value is a human short name like "1022" — the registry row will
    still record the canonical PROJ-XXXX after resolution.

    Returns (None, None) if the registry doesn't exist or the hint
    matches nothing.
    """
    if not hint or not os.path.exists(projects_registry_path):
        return None, None
    hint_lower = hint.lower()
    with open(projects_registry_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("project_id") == hint:
                return row["project_id"], row.get("folder_location") or None
            if (row.get("short_name") or "").lower() == hint_lower:
                return row["project_id"], row.get("folder_location") or None
    return None, None


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

    Args:
        project_folder_abs: Absolute local path to the project folder on the
            machine running the script (e.g. ``J:\\gjesus3-data\\projects\\proj-x``).
        link_name: Destination name with NO extension — what the legacy `.lnk`
            shortcut was called, minus ``.lnk`` (the resolved ``link_filename:``;
            any trailing slash already stripped by the caller).
        raw_primary_abs: Absolute local path to the acquisition's primary —
            either a single file or the ``<ACQ-ID>.data`` folder. MUST be on
            the same NAS volume as ``project_folder_abs`` (hard links cannot
            cross volumes).
        dry_run: If True, return the would-be destination without creating it.

    Returns:
        Absolute path to the created (or would-be) link / folder.

    Raises:
        RuntimeError: If ``raw_primary_abs`` does not exist.
        OSError: If the hard link cannot be created (e.g. cross-volume, or the
            filesystem does not support hard links).

    Idempotent: an existing file link, or an already-present file inside the
    folder-of-links, is left untouched — so a partially-created folder is
    completed on a re-run.
    """
    raw_linked_dir = os.path.join(project_folder_abs, "raw_linked")
    dest = os.path.join(raw_linked_dir, link_name)

    if dry_run:
        return dest

    if not os.path.exists(raw_primary_abs):
        raise RuntimeError(
            f"raw primary not found, cannot hard-link: {raw_primary_abs!r}"
        )

    os.makedirs(raw_linked_dir, exist_ok=True)

    if os.path.isdir(raw_primary_abs):
        # Folder primary -> real folder of per-file hard links.
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

    # File primary -> single hard link.
    if not os.path.exists(dest):
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
            machine running the script (e.g. \\\\GJESUS3\\gjesus3\\projects\\proj-x\\).
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
