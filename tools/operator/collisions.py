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
    same (project_hint, link_filename). Pure; no I/O. This is the primary risk
    once the link name is editable.
  - ``find_existing_link_targets(cases, nas_root)`` -- ON-NAS (best-effort): a
    link target that already exists on disk for a DIFFERENT acquisition (a name
    reused across batches). Re-ingesting the SAME acquisition is deduped upstream
    and is NOT flagged here.

Both group by the resolved ``project_hint`` (the actual project folder key), NOT
the preview's project string -- two distinct auto-create hints both previewing as
"will auto-create" must not be mistaken for the same project.

Each ``case`` is a dict as produced by the GUI's ``_case_to_dict`` (or any mapping
carrying ``acq_id``, ``link_filename`` and a ``registry_resolved`` dict with
``project_hint``).
"""

import os
from collections import defaultdict


def _norm(s):
    return (s or "").strip()


def _hint_of(case):
    """The resolved project_hint for a case (the project-folder key), or ''."""
    reg = case.get("registry_resolved") or {}
    return _norm(reg.get("project_hint"))


def _link_of(case):
    return _norm(case.get("link_filename"))


def _acq_of(case):
    return case.get("acq_id") or case.get("original_name") or "?"


def find_link_collisions(cases):
    """Return in-batch link-name collisions.

    Groups the cases by ``(project_hint, link_filename)`` and returns every group
    with more than one acquisition -- those would write the same link name into
    the same project. Cases with no project (blank hint) create no link and are
    skipped; so are cases with an empty link name.

    Returns a list (sorted for stable display) of::

        {"project_hint": ..., "link_filename": ..., "acq_ids": [...]}
    """
    groups = defaultdict(list)
    for c in cases:
        hint = _hint_of(c)
        link = _link_of(c)
        if not hint or not link:
            continue  # no project -> no link -> cannot collide
        groups[(hint, link)].append(_acq_of(c))

    collisions = []
    for (hint, link), acq_ids in groups.items():
        if len(acq_ids) > 1:
            collisions.append({
                "project_hint": hint,
                "link_filename": link,
                "acq_ids": sorted(acq_ids),
            })
    collisions.sort(key=lambda d: (d["project_hint"], d["link_filename"]))
    return collisions


def _project_folder(nas_root, project_hint):
    """The on-disk project folder for a hint: <nas>/projects/proj-<hint>.

    Mirrors the linker's convention (the project link lives under
    ``projects/proj-<short_name>/raw_linked/``). Best-effort: the hint is the
    short_name; the folder is ``proj-<short_name>``. Returns the path string
    (not guaranteed to exist).
    """
    return os.path.join(nas_root, "projects", f"proj-{project_hint}", "raw_linked")


def find_existing_link_targets(cases, nas_root):
    """Best-effort ON-NAS overwrite check.

    For each case with a project + link name, test whether
    ``<nas>/projects/proj-<hint>/raw_linked/<link_filename>`` already exists. An
    existing target for a DIFFERENT acquisition means this run would overwrite /
    collide with a previously-linked acquisition. A re-ingest of the SAME
    acquisition is deduped upstream (it never reaches the linker), so anything
    surfaced here is a genuine cross-batch name reuse worth a warning.

    Never raises (a stat error on one path is skipped). Returns a list of::

        {"project_hint": ..., "link_filename": ..., "acq_id": ..., "path": ...}
    """
    out = []
    if not nas_root:
        return out
    for c in cases:
        hint = _hint_of(c)
        link = _link_of(c)
        if not hint or not link:
            continue
        target = os.path.join(_project_folder(nas_root, hint), link)
        try:
            if os.path.exists(target):
                out.append({
                    "project_hint": hint,
                    "link_filename": link,
                    "acq_id": _acq_of(c),
                    "path": target,
                })
        except OSError:
            continue
    out.sort(key=lambda d: (d["project_hint"], d["link_filename"]))
    return out
