"""Create links / manifests for project folder references.

Two outputs:
- manifest: append-only CSV mapping original names to ACQ-IDs and canonical paths.
- lnk: Windows .lnk shortcut placed in <project>/raw_linked/ named with the
  original archive name, targeting the acquisition's primary file (or folder)
  via UNC path. Created by shelling out to PowerShell's WScript.Shell COM
  object so the output is a fully Explorer-compatible shortcut (correct
  icon resolution, double-click open, etc.). Windows-only.
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
    nas_unc_root:   e.g. "\\\\GJESUS3\\gjesus3"
    Returns:        "\\\\GJESUS3\\gjesus3\\raw\\DICOM\\2021\\2021-10\\ACQ-20211022-XMRI-001"
    """
    rel = canonical_path.lstrip("/").rstrip("/").replace("/", "\\")
    root = nas_unc_root.rstrip("\\")
    return f"{root}\\{rel}"


def create_lnk(
    project_folder_abs,
    original_name,
    target_unc_path,
    description="",
    dry_run=False,
    working_dir_unc=None,
):
    """Create a Windows .lnk shortcut in <project>/raw_linked/.

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
