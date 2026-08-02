#!/usr/bin/env python3
"""create_project.py — Create a new project workspace on gjesus3.

Usage:
    python create_project.py --name "ipf-biomarkers" --description "..." --owner MBC
    python create_project.py --interactive
    python create_project.py --name test --description "test" --owner RT --dry-run

See 05_PROJECTS.md and 10_TOOLS.md for full specification.
"""

import argparse
import csv
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Schema lives in the ingest package so every writer of provenance.csv
# (this script, ingest_raw.py Step 12, future Excel-importer, close-out
# tool) shares one source of truth.
from ingest import provenance as provenance_mod
from ingest import csv_safe
from ingest import resources
# The name -> folder rule has ONE home (2026-08-02); this script is the only
# thing that CREATES a project, and it derives the folder from there rather
# than building a path string of its own. See 05_PROJECTS "Project reference
# model".
from ingest.project_naming import (
    validate_project_name,
    normalize_project_name,
    folder_name as project_folder_name,
    folder_location as project_folder_location,
)


# --- Constants ---

PROJECT_REGISTRY_FIELDS = [
    "project_id",
    "name",              # RENAMED from "short_name" 2026-08-02 — the project's
                         # human key, case-preserved, and the folder verbatim.
    "description",
    "owner",
    "start_date",
    "status",
    "last_activity",
    "folder_location",
    "notes",
]


def log(msg, level="INFO"):
    """Print a timestamped log message."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {level}: {msg}")


def read_project_registry(registry_path):
    """Read project registry and return list of row dicts."""
    if not os.path.exists(registry_path):
        return []
    # utf-8-sig: tolerate an Excel BOM so the first column key stays
    # "project_id" for uniqueness / next-id checks.
    with open(registry_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def next_project_id(rows):
    """Determine the next PROJ-NNNN ID from existing registry rows."""
    max_num = 0
    for row in rows:
        pid = row.get("project_id", "")
        if pid.startswith("PROJ-"):
            try:
                num = int(pid.split("-")[1])
                if num > max_num:
                    max_num = num
            except (ValueError, IndexError):
                continue
    return f"PROJ-{max_num + 1:04d}"


def check_name_unique(rows, name):
    """Check that `name` is not already in the registry.

    Case-INSENSITIVE: the NAS filesystem is case-insensitive, so two names
    differing only in case would fight over one folder.
    """
    for row in rows:
        if row.get("name", "").lower() == name.lower():
            return False
    return True


def load_template(template_path):
    """Load the project.yaml template."""
    with open(template_path, "r") as f:
        return f.read()


def create_project(name, description, owner, nas_root, dry_run=False, notes=""):
    """Create a new project workspace.

    Args:
        name: The project's name — case-preserved, and the folder name
            verbatim (spaces are normalized to hyphens).
        description: Brief description of the project.
        owner: Owner initials.
        nas_root: Path to NAS root (e.g., /mnt/gjesus3).
        dry_run: If True, preview without making changes.
        notes: Optional notes.

    Returns:
        Tuple of (project_id, success).
    """
    # --- Normalize + validate the name (it becomes the folder) ---
    name = normalize_project_name(name)
    errors = validate_project_name(name)
    if errors:
        for e in errors:
            log(e, "ERROR")
        return None, False

    # --- Check registry ---
    registry_path = os.path.join(nas_root, "registries", "registry_projects.csv")
    rows = read_project_registry(registry_path)

    if not check_name_unique(rows, name):
        log(f"Project name '{name}' already exists in registry", "ERROR")
        return None, False

    # --- Generate ID ---
    project_id = next_project_id(rows)
    log(f"Generated project ID: {project_id}")

    # --- Determine paths (folder == name, verbatim) ---
    project_dir = os.path.join(nas_root, "projects", project_folder_name(name))
    canonical_path = project_folder_location(name)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # --- Summary ---
    log(f"  Name:        {name}")
    log(f"  Description: {description}")
    log(f"  Owner:       {owner}")
    log(f"  Project ID:  {project_id}")
    log(f"  Folder:      {project_dir}")
    log(f"  Start Date:  {today}")

    if dry_run:
        log("[DRY RUN] Would create folder and registry entry. Skipping.")
        return project_id, True

    # --- Create directory structure ---
    os.makedirs(project_dir, exist_ok=True)
    os.makedirs(os.path.join(project_dir, "raw_linked"), exist_ok=True)
    log("Created directory structure")

    # --- Write _project.yaml ---
    # Resolve the template so it works from a source checkout AND the frozen exe
    # (sys._MEIPASS-aware; see ingest/resources.py). The old naive
    # dirname(__file__) path silently missed the bundled copy in the exe and
    # fell through to the inline fallback below, writing a non-templated
    # _project.yaml. The os.path.exists guard stays as a belt-and-braces net.
    template_path = resources.resource_path("templates", "project.yaml")

    if os.path.exists(template_path):
        content = load_template(template_path)
        content = content.replace("{project_id}", project_id)
        content = content.replace("{name}", name)
        content = content.replace("{description}", description)
        content = content.replace("{owner}", owner)
        content = content.replace("{start_date}", today)
    else:
        # Fallback: generate inline
        content = (
            f"project_id: {project_id}\n"
            f"name: {name}\n"
            f'description: "{description}"\n'
            f"status: active\n"
            f"owner: {owner}\n"
            f"start_date: {today}\n"
            f"last_activity: {today}\n"
            f"closed_date: null\n"
            f"outcome: null\n"
            f"promoted_to: null\n"
            f"notes: |\n"
            f"  Created by create_project.py\n"
        )

    yaml_path = os.path.join(project_dir, "_project.yaml")
    # Atomic write: write to a sibling .tmp then os.replace, so a crash
    # mid-write can't truncate / corrupt the target.
    tmp_path = yaml_path + ".tmp"
    with open(tmp_path, "w") as f:
        f.write(content)
    os.replace(tmp_path, yaml_path)
    log("Wrote _project.yaml")

    # --- Create empty provenance.csv ---
    prov_path = os.path.join(project_dir, "provenance.csv")
    provenance_mod.write_empty(prov_path)
    log("Wrote provenance.csv (empty with headers)")

    # --- Append to registry ---
    os.makedirs(os.path.dirname(registry_path), exist_ok=True)
    file_exists = os.path.exists(registry_path)

    row = {
        "project_id": project_id,
        "name": name,
        "description": description,
        "owner": owner,
        "start_date": today,
        "status": "active",
        "last_activity": today,
        "folder_location": canonical_path,
        "notes": notes,
    }

    csv_safe.ensure_trailing_newline(registry_path)
    with open(registry_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PROJECT_REGISTRY_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
    log(f"Appended to registry: {registry_path}")

    log(f"DONE: {project_id} - {canonical_path}")
    return project_id, True


def run_interactive(nas_root, dry_run=False):
    """Interactive mode for project creation."""
    print("=== Create New Project ===\n")

    name = input(
        "Project name (also the folder name, e.g. 'AE-biomaGUNE-1123'): "
    ).strip()
    description = input("Description: ").strip()
    owner = input("Owner (initials): ").strip()
    notes = input("Notes (optional): ").strip()

    if not name or not description or not owner:
        log("Name, description, and owner are all required", "ERROR")
        sys.exit(1)

    project_id, ok = create_project(
        name, description, owner, nas_root, dry_run=dry_run, notes=notes
    )
    if not ok:
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Create a new project workspace on gjesus3.",
        epilog="See 05_PROJECTS.md and 10_TOOLS.md for full documentation.",
    )
    parser.add_argument(
        "--name", "-n",
        help="Project name — also the folder name (e.g. 'AE-biomaGUNE-1123')",
    )
    parser.add_argument(
        "--description", "-d",
        help="Brief description of the project",
    )
    parser.add_argument(
        "--owner", "-o",
        help="Owner initials (e.g. MBC, RT)",
    )
    parser.add_argument(
        "--notes",
        default="",
        help="Optional notes",
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode",
    )
    parser.add_argument(
        "--nas-root",
        default=os.environ.get("GJESUS3_ROOT", "/mnt/gjesus3"),
        help="Path to NAS root (default: $GJESUS3_ROOT or /mnt/gjesus3)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would happen without making changes",
    )

    args = parser.parse_args()

    if args.interactive:
        run_interactive(args.nas_root, dry_run=args.dry_run)
    elif args.name and args.description and args.owner:
        project_id, ok = create_project(
            args.name, args.description, args.owner,
            args.nas_root, dry_run=args.dry_run, notes=args.notes,
        )
        if not ok:
            sys.exit(1)
    else:
        parser.error(
            "Must provide --name, --description, and --owner (or use --interactive)"
        )


if __name__ == "__main__":
    main()
