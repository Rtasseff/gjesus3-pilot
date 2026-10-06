"""The `registry_raw.project_id` cell — ONE definition of how it is read and written.

**✅ DECIDED 2026-08-12: an acquisition is registered to exactly ONE project.**
`project_id` is **write-once** — set at ingest when a project resolves, or by the
first Project Manager assignment if it was blank — and thereafter **never appended
to and never overwritten** by a tool. Sharing an acquisition between projects is
fully supported at the *filesystem* level (the Project Manager creates the hard
link and writes the destination project's provenance row); it is simply **not
registered**. See 06_REGISTRIES §2.3b for the reasoning, and 05_PROJECTS §3a for
the ownership boundary that motivates it.

Why the reversal: the multi-project list shipped 2026-08-11 and was reconsidered a
day later against how the system is actually used. Searching the registry by project
is rare, and when it happens it means *the project the acquisition was ingested for*.
Against that, a growing list cost eight reader sites which each failed **silently**
when they forgot to split — no error, just fewer rows. The honest boundary is that the
registry records what the SYSTEM knows (the ingest-time association) and does not try
to track what researchers do afterwards in space they own and may reorganise freely. A
real many-to-many belongs in the metadata database that eventually replaces these
CSVs, not in a CSV column.

**The readers stay list-tolerant on purpose — this is not dead code.** Every function
here still handles a `;`-separated cell, and a single value is simply a length-1 list.
So: the eight readers written for the list keep working unchanged; a hand-edited or
legacy multi-value cell degrades gracefully instead of silently missing rows; and the
seam the future database will need is already in place. Nothing in the system *writes*
a second id — see `set_project_id_if_blank`, which is the only writer policy.

Ordering is meaningful and preserved: the FIRST id is the original association.

Spec: 06_REGISTRIES §2 + §2.3b — this module is its integrity mirror.
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


def set_project_id_if_blank(cell, project_id):
    """**The writer policy.** Return ``(new_cell, changed)`` — set only if unset.

    Write-once semantics (✅ DECIDED 2026-08-12, module docstring): an acquisition
    is registered to exactly one project.

    - blank cell            -> set to `project_id`, ``changed=True``
    - already ANY id        -> **untouched**, ``changed=False`` — including when
      the existing id is a *different* project. That is the shared-acquisition
      case: the link and the provenance row are still written by the caller, but
      the registry keeps the original association.

    Callers must not report ``changed=False`` as a failure — nothing went wrong.
    """
    project_id = (project_id or "").strip()
    ids = split_project_ids(cell)
    if ids or not project_id:
        return join_project_ids(ids), False
    return project_id, True


def add_project_id(cell, project_id):
    """Return ``(new_cell, changed)`` with `project_id` APPENDED to the cell.

    ⚠️ **NOT the writer policy — nothing in the system calls this.** Registering a
    second project was retired on 2026-08-12 in favour of write-once
    `set_project_id_if_blank`; see the module docstring. Kept (with `remove_project_id`)
    as the tested mechanics for a deliberate future migration — the metadata database
    that models project↔acquisition properly will need exactly this. **Do not wire it
    into a tool without changing the decision in 06_REGISTRIES §2.3b first.**

    Idempotent: adding an id the cell already carries is a no-op returning
    ``changed=False``. A blank cell becomes the bare id. An existing DIFFERENT id
    is preserved **first**, so the original association stays primary.
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
