"""What lives inside a project folder — the recommended subfolders and
`_project.yaml`.

ONE definition of the folder convention, so `create_project.py`, the Project
Manager GUI and the backfill script cannot drift. Spec: 05_PROJECTS §3 (the
directory tree) and §7 (`_project.yaml`).

The subfolder set is a **recommendation made real**: the tools create it, and a
researcher is free to add more. It is not enforced — nothing fails because a
project has extra folders, and nothing deletes what a researcher put there.

`metadata/` is created EMPTY on purpose. The directory now exists; the
study-metadata *layer* that fills it (writers, file shapes, close-out merge)
stays 🕗 PLANNED/DEFERRED — see 05_PROJECTS §3. Creating the directory is the
part that is done; do not read its existence as the layer having shipped.
"""

import os
import re

# Order matters only for display. `raw_linked/` is listed first because it is
# the one the system owns.
PROJECT_SUBFOLDERS = [
    ("raw_linked", "hard links to raw acquisitions. Tool-managed; don't hand-edit."),
    ("working",    "scratch and in-progress analysis."),
    ("outputs",    "results worth keeping: figures, derived images, reports."),
    ("metadata",   "study-level metadata. Directory created; contents still deferred."),
]

SUBFOLDER_NAMES = [name for name, _desc in PROJECT_SUBFOLDERS]

PROJECT_YAML_FILENAME = "_project.yaml"


def ensure_subfolders(project_dir, dry_run=False):
    """Create any missing recommended subfolders. Returns the names created.

    Idempotent and additive: an existing folder is left exactly as it is, and
    nothing else in the project is touched. No provenance row is written —
    provenance tracks FILES (07_PROVENANCE), and an empty directory is not one.
    """
    created = []
    for name in SUBFOLDER_NAMES:
        path = os.path.join(project_dir, name)
        if os.path.isdir(path):
            continue
        created.append(name)
        if not dry_run:
            os.makedirs(path, exist_ok=True)
    return created


def missing_subfolders(project_dir):
    """The recommended subfolders this project does not have (read-only)."""
    return [n for n in SUBFOLDER_NAMES
            if not os.path.isdir(os.path.join(project_dir, n))]


# ------------------------------------------------------------- _project.yaml

def project_yaml_path(project_dir):
    return os.path.join(project_dir, PROJECT_YAML_FILENAME)


def read_project_yaml(project_dir):
    """Parse `_project.yaml` -> dict, or None if absent / unreadable / not a map.

    Never raises: a hand-mangled YAML must not take down a GUI that is only
    trying to show a project. The registry row is the authoritative record
    (05_PROJECTS §7); this file is the copy a researcher sees in the folder.
    """
    path = project_yaml_path(project_dir)
    if not os.path.isfile(path):
        return None
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception:  # noqa: BLE001 — unreadable/unparseable is "no data"
        return None
    return data if isinstance(data, dict) else None


_KEY_RE_CACHE = {}


def _key_line_re(key):
    if key not in _KEY_RE_CACHE:
        _KEY_RE_CACHE[key] = re.compile(r"^" + re.escape(key) + r"\s*:(.*)$")
    return _KEY_RE_CACHE[key]


def _render_scalar(value):
    """A YAML-safe one-line scalar. Bare when it is an obvious plain token."""
    s = "" if value is None else str(value)
    if re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.\-+]*", s):
        return s
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _render_entry(key, value):
    """Lines for `key: value`, using a block scalar for multi-line text."""
    s = "" if value is None else str(value)
    if "\n" in s:
        out = [f"{key}: |\n"]
        for line in s.rstrip("\n").split("\n"):
            out.append(f"  {line}\n" if line else "\n")
        return out
    return [f"{key}: {_render_scalar(s)}\n"]


def update_project_yaml(project_dir, updates):
    """Rewrite the given top-level keys in `_project.yaml`, in place.

    Line-oriented on purpose. A `yaml.safe_load` + `safe_dump` round trip would
    silently strip the file's section comments (`# Timeline`, the `# active |
    paused | closed` gloss on `status`) — and a researcher opening the folder
    reads this file, so those comments are the point. Instead each managed key's
    lines are replaced in place, the rest of the file is untouched byte for
    byte, and a trailing comment on a plain scalar line is preserved.

    Handles block scalars (`notes: |`) by replacing the key line together with
    its indented continuation. A key that isn't present is appended.

    Writes atomically (pid-suffixed temp + `os.replace`), and verifies the
    result parses and carries the intended values before publishing it — if it
    doesn't, the original file is left untouched and RuntimeError is raised.
    Returns the keys actually changed ([] if the file is absent or nothing
    differed).
    """
    path = project_yaml_path(project_dir)
    if not os.path.isfile(path) or not updates:
        return []

    with open(path, "r", encoding="utf-8", newline="") as f:
        lines = f.readlines()

    changed = []
    for key, value in updates.items():
        pat = _key_line_re(key)
        idx = next((i for i, ln in enumerate(lines) if pat.match(ln)), None)
        new_lines = _render_entry(key, value)

        if idx is None:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines.extend(new_lines)
            changed.append(key)
            continue

        # How far does this entry reach? A block scalar (`|` / `>`) owns every
        # following indented-or-blank line.
        rest = pat.match(lines[idx]).group(1).strip()
        end = idx + 1
        if rest.startswith("|") or rest.startswith(">"):
            while end < len(lines) and (not lines[end].strip()
                                        or lines[end][:1] in (" ", "\t")):
                end += 1
            # Don't swallow blank lines that separate this entry from the next.
            while end > idx + 1 and not lines[end - 1].strip():
                end -= 1
        elif "#" in rest and len(new_lines) == 1:
            # Preserve a trailing comment (e.g. the status vocabulary gloss).
            comment = rest[rest.index("#"):].rstrip()
            new_lines = [new_lines[0].rstrip("\n") + "  " + comment + "\n"]

        if lines[idx:end] != new_lines:
            lines[idx:end] = new_lines
            changed.append(key)

    if not changed:
        return []

    text = "".join(lines)
    _verify_yaml(text, updates, path)

    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    os.replace(tmp, path)
    return changed


def _verify_yaml(text, updates, path):
    """Parse the rewritten text and confirm it carries `updates`.

    Cheap insurance against the line-editor producing something that looks fine
    and isn't — this file is the researcher-facing copy of the project record,
    and a broken one is worse than an un-edited one. A missing pyyaml skips the
    check rather than blocking the write (the registry row is authoritative).
    """
    try:
        import yaml
    except ImportError:
        return
    try:
        data = yaml.safe_load(text)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(
            f"refusing to write {path}: the edited YAML does not parse ({e}). "
            f"The file was left unchanged."
        )
    if not isinstance(data, dict):
        raise RuntimeError(
            f"refusing to write {path}: the edited YAML is not a mapping. "
            f"The file was left unchanged."
        )
    for key, value in updates.items():
        got = data.get(key)
        want = "" if value is None else str(value)
        if (("" if got is None else str(got)).strip() != want.strip()):
            raise RuntimeError(
                f"refusing to write {path}: after editing, {key!r} reads "
                f"{got!r} instead of {want!r}. The file was left unchanged."
            )
