"""collisions.py -- detect project-link-name collisions in an operator batch.

The project hard link placed under
``/projects/<proj>/raw_linked/<link_filename>`` must be UNIQUE per acquisition
within a project. The MRI GUI lets the operator EDIT the link-name template, so a
careless edit (dropping the exam / recon that makes the name unique) can make two
acquisitions resolve to the SAME link name in the same project -- the round-6
collision bug, where four animals each had exam 27 and the bare ``27`` link
clashed so only one survived (06_REGISTRIES / the mri_bruker template note).

This module finds those collisions from a preview's cases BEFORE any write, so a
front-end can WARN the operator (the user's "do a dry-run to ensure there are no
overwrites or collisions"). Two checks:

  - ``find_link_collisions(cases)`` -- IN-BATCH: two cases that resolve to the
    same (project_name, link_filename). Pure; no I/O. This is the primary risk
    once the link name is editable.
  - ``find_existing_link_targets(cases, nas_root)`` -- ON-NAS (best-effort): a
    link target that already exists on disk for a DIFFERENT acquisition (a name
    reused across batches). Re-ingesting the SAME acquisition is deduped upstream
    and is NOT flagged here.

Both group by the case's ``project_name`` (the project key -- and, since
2026-08-02, the folder name verbatim), NOT the preview's project string -- two
distinct auto-create names both previewing as "will auto-create" must not be
mistaken for the same project. Grouping is case-INSENSITIVE, because the NAS
filesystem is: ``AE-biomaGUNE-1123`` and ``ae-biomagune-1123`` are one folder and
so genuinely can collide.

Each ``case`` is a dict as produced by the GUI's ``_case_to_dict`` (or any mapping
carrying ``acq_id``, ``link_filename`` and a ``registry_resolved`` dict with
``project_name``).
"""

import csv
import os
from collections import defaultdict

from ingest import project_naming


def _norm(s):
    return (s or "").strip()


def _project_of(case):
    """The project name for a case (the project key), or ''."""
    reg = case.get("registry_resolved") or {}
    return _norm(reg.get("project_name"))


def _link_of(case):
    return _norm(case.get("link_filename"))


def _acq_of(case):
    return case.get("acq_id") or case.get("original_name") or "?"


def find_link_collisions(cases):
    """Return in-batch link-name collisions.

    Groups the cases by ``(project_name, link_filename)`` -- the project part
    case-insensitively, since one folder serves both spellings -- and returns
    every group with more than one acquisition; those would write the same link
    name into the same project. Cases with no project create no link and are
    skipped; so are cases with an empty link name.

    Returns a list (sorted for stable display) of::

        {"project_name": ..., "link_filename": ..., "acq_ids": [...]}
    """
    groups = defaultdict(list)
    display = {}
    for c in cases:
        project = _project_of(c)
        link = _link_of(c)
        if not project or not link:
            continue  # no project -> no link -> cannot collide
        key = (project.lower(), link)
        display.setdefault(key, project)
        groups[key].append(_acq_of(c))

    collisions = []
    for key, acq_ids in groups.items():
        if len(acq_ids) > 1:
            collisions.append({
                "project_name": display[key],
                "link_filename": key[1],
                "acq_ids": sorted(acq_ids),
            })
    collisions.sort(key=lambda d: (d["project_name"].lower(), d["link_filename"]))
    return collisions


def _folder_index(nas_root):
    """Map name.lower() and project_id -> the STORED folder_location basename.

    Read once per check from registry_projects.csv. Reading the recorded
    location (rather than re-deriving a path from the name) is the rule this
    module used to break: it built ``proj-<hint>`` itself, so it went on
    checking a folder convention the rest of the system had left behind.
    Returns {} when the registry is unreadable -- callers fall back to the
    name-derived folder, which is correct for a not-yet-created project.
    """
    path = os.path.join(nas_root, "registries", "registry_projects.csv")
    index = {}
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                folder = (row.get("folder_location") or "").strip("/").split("/")[-1]
                if not folder:
                    continue
                name = (row.get("name") or "").strip()
                pid = (row.get("project_id") or "").strip()
                if name:
                    index[name.lower()] = folder
                if pid:
                    index[pid.lower()] = folder
    except (OSError, csv.Error):
        return {}
    return index


def _project_folder(nas_root, project_name, index):
    """The on-disk ``raw_linked`` dir for a project, as a path string.

    Uses the project's recorded folder when it exists; for a project that has
    not been created yet (an auto-create preview) falls back to the derived
    folder -- which under the folder-==-name rule is what create_project would
    make. Not guaranteed to exist.
    """
    folder = index.get(project_name.lower()) or project_naming.folder_name(project_name)
    return os.path.join(nas_root, "projects", folder, "raw_linked")


def find_existing_link_targets(cases, nas_root):
    """Best-effort ON-NAS overwrite check.

    For each case with a project + link name, test whether
    ``<nas>/<the project's folder>/raw_linked/<link_filename>`` already exists.
    An existing target for a DIFFERENT acquisition means this run would
    overwrite / collide with a previously-linked acquisition. A re-ingest of the
    SAME acquisition is deduped upstream (it never reaches the linker), so
    anything surfaced here is a genuine cross-batch name reuse worth a warning.

    Never raises (a stat error on one path is skipped). Returns a list of::

        {"project_name": ..., "link_filename": ..., "acq_id": ..., "path": ...}
    """
    out = []
    if not nas_root:
        return out
    index = _folder_index(nas_root)
    for c in cases:
        project = _project_of(c)
        link = _link_of(c)
        if not project or not link:
            continue
        target = os.path.join(_project_folder(nas_root, project, index), link)
        try:
            if os.path.exists(target):
                out.append({
                    "project_name": project,
                    "link_filename": link,
                    "acq_id": _acq_of(c),
                    "path": target,
                })
        except OSError:
            continue
    out.sort(key=lambda d: (d["project_name"].lower(), d["link_filename"]))
    return out
