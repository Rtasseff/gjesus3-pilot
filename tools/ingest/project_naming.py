"""The project-name rule — ONE definition of what a project name may be and
which folder it maps to.

Every layer reads the same two functions from here, so the name -> folder rule
can never drift again. See 05_PROJECTS.md "Project reference model" for the
model this implements; the short version:

    project_id    PROJ-XXXX   machine key, immutable, stored in registry_raw
    name          human key   what the operator types, and the folder VERBATIM

Before 2026-08 the folder rule lived in three places (create_project's
``f"proj-{name}"``, ingest_raw's ``.lower()``, and collisions.py re-deriving
``proj-<hint>``), which is how the folder drifted away from the name operators
saw in the GUI. Now: `folder_name` / `folder_location` are the only places that
know how a name becomes a path, and every other consumer reads the stored
`folder_location` out of registry_projects.csv.

Kept dependency-free (stdlib only) so the pure/no-I/O modules — collisions.py,
the GUI — can import it as cheaply as create_project.py does.
"""

import re

MAX_NAME_LEN = 60

# Windows/SMB-illegal in a path component. The FS is case-insensitive, so
# casing is preserved for display but never makes two names distinct.
_ILLEGAL_CHARS = set('\\/:*?"<>|')
_WHITESPACE_RUN = re.compile(r"\s+")


def normalize_project_name(raw):
    """Coerce operator input into the canonical name form.

    Trims, then collapses every internal whitespace run to a single hyphen
    (decision 2026-08-02: names are OS-safe, so a typed space becomes `-`).
    The GUI applies this live as the operator types so what they see is what
    is created; the CLI/YAML path applies it at resolve time so both front
    ends produce the same name for the same input.

    Casing is preserved — `AE-biomaGUNE-1123` stays exactly that.
    """
    if not raw:
        return ""
    return _WHITESPACE_RUN.sub("-", str(raw).strip())


def validate_project_name(name):
    """Return a list of error strings (empty if the name is usable).

    A name must be a legal single path component on Windows/SMB, because it
    IS the folder name. Renamed from create_project.validate_short_name
    2026-08-02 — the old rule forced lowercase, which is what made the folder
    stop matching the name the operator typed.
    """
    errors = []
    if not name:
        errors.append("Project name cannot be empty")
        return errors
    bad = sorted(set(name) & _ILLEGAL_CHARS)
    if bad:
        errors.append(
            f"Project name cannot contain {' '.join(bad)} "
            f"(it is used as the folder name): '{name}'"
        )
    if any(ord(c) < 32 for c in name):
        errors.append(f"Project name cannot contain control characters: '{name}'")
    if name != name.strip(" ."):
        errors.append(
            f"Project name cannot start or end with a space or dot: '{name}'"
        )
    if len(name) > MAX_NAME_LEN:
        errors.append(
            f"Project name too long ({len(name)} chars, max {MAX_NAME_LEN})"
        )
    return errors


def folder_name(name):
    """The on-disk folder basename for a project name — the name, verbatim.

    An identity function on purpose: the rule "folder == name" now has exactly
    one home, so a future change (a prefix, a slug) is a one-line edit here
    instead of a hunt through three modules.
    """
    return name


def folder_location(name):
    """The NAS-relative `folder_location` recorded in registry_projects.csv."""
    return f"/projects/{folder_name(name)}/"
