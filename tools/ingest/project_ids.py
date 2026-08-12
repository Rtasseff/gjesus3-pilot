"""The `registry_raw.project_id` cell — ONE definition of the semicolon list.

An acquisition can belong to more than one project (a researcher re-homes a scan
into a second study). ✅ DECIDED 2026-08-11: that is recorded as a
**semicolon-separated list in the existing `project_id` column** —
``PROJ-0001;PROJ-0007`` — following the house convention already used by
`modalities_in_study` (``PT;CT``) and `subject_ids` (the packed facility ids). A
separate many-to-one mapping table was considered and rejected as
over-engineering: this is a simple registry, and turning it into a real DB schema
is a future endeavour, not this column's job.

Why a module rather than a `.split(";")` at each site: before this existed, five
readers joined or grouped on the WHOLE cell and every one of them failed
**silently** on a two-project value — `generate_index.py` formed a bogus
``"PROJ-0001;PROJ-0007"`` group so the acquisition appeared in NEITHER project's
index, `find_acq.py`'s `proj_idx.get()` missed so the record lost its project
folder/name/owner, and `validate_registries.py`'s `PROJ_ID_RE.match` failed so
the existence check was **skipped, not failed**. One definition here means adding
a second project can never quietly delete an acquisition from the index of the
project it was already in.

Ordering is meaningful and preserved: the FIRST id is the original association
(the one ingest stamped), and `add` appends after it. Nothing downstream depends
on that beyond display, but a stable order keeps diffs of the registry readable.

Spec: 06_REGISTRIES §2 (`project_id`) — this module is its integrity mirror.
Kept dependency-free (stdlib only) so every reader, the GUI and the pure
no-I/O modules can import it cheaply.
"""

SEP = ";"


def split_project_ids(cell):
    """The project ids in one `project_id` cell, in order, deduped, blanks dropped.

    ``""`` / ``None`` -> ``[]``. A single-valued cell -> a length-1 list, so
    callers have ONE code path for 1..N projects (the same shape `subject_ids`
    uses). Whitespace around a separator is tolerated — a hand edit in Excel
    routinely leaves ``PROJ-0001; PROJ-0007``.
    """
    out = []
    for part in (cell or "").split(SEP):
        pid = part.strip()
        if pid and pid not in out:
            out.append(pid)
    return out


def join_project_ids(ids):
    """Pack ids back into a cell value (deduped, order preserved, blanks dropped)."""
    out = []
    for pid in ids or ():
        pid = (pid or "").strip()
        if pid and pid not in out:
            out.append(pid)
    return SEP.join(out)


def has_project_id(cell, project_id):
    """True if `project_id` is one of the cell's ids (exact, not substring).

    The substring test the old filter used matched ``PROJ-001`` inside
    ``PROJ-0011`` — accidentally right for a prefix search, wrong for an
    identity check.
    """
    return (project_id or "").strip() in split_project_ids(cell)


def add_project_id(cell, project_id):
    """Return ``(new_cell, changed)`` with `project_id` added to the cell.

    Idempotent: adding an id the cell already carries is a no-op returning
    ``changed=False`` (a re-import must never produce ``PROJ-0001;PROJ-0001``).
    A blank cell becomes the bare id. An existing DIFFERENT id is preserved
    **first**, so the original association stays the primary one.
    """
    project_id = (project_id or "").strip()
    ids = split_project_ids(cell)
    if not project_id or project_id in ids:
        return join_project_ids(ids), False
    ids.append(project_id)
    return join_project_ids(ids), True


def remove_project_id(cell, project_id):
    """Return ``(new_cell, changed)`` with `project_id` dropped from the cell.

    The inverse of `add_project_id`, for a future "remove data from this project"
    path. Removing an id that isn't there is a no-op.
    """
    project_id = (project_id or "").strip()
    ids = split_project_ids(cell)
    if not project_id or project_id not in ids:
        return join_project_ids(ids), False
    ids.remove(project_id)
    return join_project_ids(ids), True
