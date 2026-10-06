"""Reading and editing projects — the "Update project" half of the manager.

Thin composition over `ingest/projects_registry.py` (the CSV) and
`ingest/project_layout.py` (the folder). Nothing here talks HTTP; the GUI is a
front-end over these functions and a script can call them just as well.

Two facts shape everything in this module:

* **A registry row without a folder is NORMAL.** Eight projects were closed on
  2026-07-14/15 and their folders deleted; the rows stay so the acquisitions
  remain findable (05_PROJECTS §5). `describe` reports `folder_exists: False`
  for those instead of treating them as corruption, and nothing here recreates
  a folder as a side effect of reading.
* **`start_date` / `last_activity` mean ACQUISITION dates, not edit dates**
  (production update 2026-07-14/15). Editing a description must NOT stamp
  `last_activity` to today — that would silently redefine the column across
  every project a researcher opens. `EDITABLE_FIELDS` is the whole of what an
  edit may touch, and it is enforced in `projects_registry.update_row`.
"""

import os

from ingest import locking, project_layout, projects_registry
from ingest import project_naming


def _project_dir(nas_root, row):
    """Absolute path of a project's folder from its STORED folder_location.

    Never rebuilt from the name — that is the one construction-site rule
    (05_PROJECTS §2a). A row with no folder_location has no folder.
    """
    rel = (row.get("folder_location") or "").strip()
    if not rel:
        return None
    return os.path.normpath(os.path.join(nas_root, rel.lstrip("/")))


def list_projects(nas_root):
    """Every project row + the folder facts the GUI needs, newest id first.

    Adds (all derived, never stored):
      folder_path     absolute path, or None when folder_location is blank
      folder_exists   False for a closed-and-deleted project — a normal state
      has_yaml        `_project.yaml` present
      missing_subfolders  which of the recommended set are absent
    """
    rows = projects_registry.read_projects(
        projects_registry.projects_registry_path(nas_root))
    out = []
    for row in rows:
        d = _project_dir(nas_root, row)
        exists = bool(d) and os.path.isdir(d)
        rec = dict(row)
        rec["folder_path"] = d
        rec["folder_exists"] = exists
        rec["has_yaml"] = exists and os.path.isfile(
            project_layout.project_yaml_path(d))
        rec["missing_subfolders"] = (
            project_layout.missing_subfolders(d) if exists else [])
        out.append(rec)
    out.sort(key=lambda r: (r.get("project_id") or ""), reverse=True)
    return out


def get_project(nas_root, name_or_id):
    """One project (the `list_projects` shape) by PROJ-id or name, or None."""
    for rec in list_projects(nas_root):
        if (rec.get("project_id") == name_or_id
                or (rec.get("name") or "").lower() == (name_or_id or "").lower()):
            return rec
    return None


def update_project(nas_root, project_id, updates, write_yaml=True):
    """Apply an edit to a project. Returns ``(applied, yaml_changed, warnings)``.

    Only `projects_registry.EDITABLE_FIELDS` may be changed; anything else
    raises. `status` is checked against the decided vocabulary
    (`STATUS_VALUES`) rather than accepted free-form — a typo'd status is a
    silently wrong lifecycle state, and the close-out rules key off it.

    **Both copies are written.** The registry row is authoritative
    (05_PROJECTS §7), but `_project.yaml` holds the same four fields and is
    what a researcher reads when they open the folder — leaving it stale would
    make the folder lie. The YAML write is best-effort and reported in
    `warnings`: a project whose folder was deleted at close-out, or whose YAML
    predates `create_project.py` (five such folders exist), still gets its
    registry edit.
    """
    unknown = [k for k in updates if k not in projects_registry.EDITABLE_FIELDS]
    if unknown:
        raise ValueError(
            f"Not editable here: {', '.join(unknown)}. Editable fields are "
            f"{', '.join(projects_registry.EDITABLE_FIELDS)}."
        )
    status = updates.get("status")
    if status is not None and status not in projects_registry.STATUS_VALUES:
        raise ValueError(
            f"status must be one of {', '.join(projects_registry.STATUS_VALUES)} "
            f"(got {status!r})."
        )

    registries_dir = os.path.join(nas_root, "registries")
    path = projects_registry.projects_registry_path(nas_root)
    warnings = []

    # The read and the rewrite are one critical section — this file is ~50 rows
    # and a lost update loses a project.
    with locking.registry_lock(registries_dir):
        found, applied = projects_registry.update_row(path, project_id, updates)
    if not found:
        raise ValueError(f"No project {project_id} in the registry.")

    yaml_changed = []
    if write_yaml and applied:
        row = get_project(nas_root, project_id) or {}
        d = row.get("folder_path")
        if not d or not os.path.isdir(d):
            warnings.append(
                "The registry was updated. This project has no folder on the "
                "share (it was closed and its folder deleted), so there is no "
                "_project.yaml to keep in step."
            )
        elif not os.path.isfile(project_layout.project_yaml_path(d)):
            warnings.append(
                "The registry was updated. This project folder has no "
                "_project.yaml (it predates create_project.py), so nothing was "
                "written there."
            )
        else:
            try:
                yaml_changed = project_layout.update_project_yaml(d, applied)
            except (OSError, RuntimeError) as e:
                warnings.append(
                    f"The registry was updated, but _project.yaml could not be: "
                    f"{e}"
                )
    return applied, yaml_changed, warnings


def validate_new_name(nas_root, raw_name):
    """Check a proposed project name. Returns ``(normalized, errors)``.

    Applied live as the researcher types, so what they see is what gets
    created — the same normalization the operator GUI does for its "Project
    name" field, and the same rule `create_project` applies at commit
    (`ingest/project_naming.py` is the one home for it).

    Uniqueness is case-INSENSITIVE because the NAS filesystem is: two names
    differing only in case would fight over one folder. This is an early
    warning, not the guarantee — `create_project` re-checks it under the lock,
    which is what actually makes it exclusive.
    """
    name = project_naming.normalize_project_name(raw_name)
    errors = list(project_naming.validate_project_name(name))
    if name and not errors:
        rows = projects_registry.read_projects(
            projects_registry.projects_registry_path(nas_root))
        if not projects_registry.check_name_unique(rows, name):
            errors.append(
                f"A project called '{name}' already exists (names are compared "
                f"without case, because the share's folder names are)."
            )
    return name, errors
