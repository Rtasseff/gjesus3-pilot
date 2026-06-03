"""Load per-instrument ingest templates to in-memory dicts.

The per-instrument templates at `tools/templates/instruments/*.yaml` encode
every locked convention (filename parse, registry mapping, project_hint,
link_filename, copy_strategy, acquisition_layout). The operator front-ends
load these as the source of truth and apply only a small whitelisted override
set (see `config_builder.build_config`) — they never duplicate the conventions.

Template path resolution is dual-mode so the same code works both from a repo
checkout (the Linux NI/MRI scripts) AND from inside a frozen PyInstaller `.exe`
(the microscopy GUI), where the templates are bundled and unpacked to
`sys._MEIPASS`:

  - Frozen (`sys.frozen` + `sys._MEIPASS`): look under
    `<_MEIPASS>/tools/templates/instruments/` first, then `<_MEIPASS>/templates/
    instruments/` (depending on how `--add-data` mapped them).
  - Source checkout: walk up from this file to the repo root and use
    `tools/templates/instruments/`.
"""

import os
import sys

# tools/ must be importable so `from ingest import config` works regardless of
# where the front-end is launched from. This file lives at tools/operator/.
#
# IMPORTANT — stdlib collision: this package's directory is named `operator`,
# which shadows the Python stdlib `operator` module. We therefore APPEND tools/
# to sys.path (never insert at the front): that keeps the stdlib `operator`
# winning the bare-name lookup (so `collections`/`dataclasses`/etc. internals
# that lazily `import operator` keep working), while the non-colliding `ingest`
# / `ingest_raw` names still resolve from tools/. For the same reason this
# package must be loaded under a NON-`operator` import name (see
# tools/operator/_loader.py) and uses only relative intra-package imports.
_TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TOOLS_DIR not in sys.path:
    sys.path.append(_TOOLS_DIR)

from ingest import config  # noqa: E402  (after sys.path setup)


# Instrument key -> per-instrument template filename. Keys are the operator-
# facing instrument identifiers used by the front-ends; the files are the
# locked convention templates under tools/templates/instruments/.
INSTRUMENT_TEMPLATES = {
    "NI":   "molecubes_ni.yaml",
    "MRI":  "mri_bruker.yaml",
    "ZWSI": "axioscan7.yaml",
    "CELL": "cell_observer_cells.yaml",
    "LSM9": "lsm900.yaml",
}


def _candidate_dirs():
    """Yield candidate directories that may hold the instrument templates.

    Order matters: frozen/bundled locations first (so a packaged .exe finds its
    bundled copy), then the repo-checkout location.
    """
    # PyInstaller one-file: data is unpacked to a temp dir exposed as
    # sys._MEIPASS; sys.frozen is set. We bundle the templates with
    # `--add-data "tools/templates/instruments;tools/templates/instruments"`
    # (or the templates/ subpath), so try both shapes.
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        yield os.path.join(meipass, "tools", "templates", "instruments")
        yield os.path.join(meipass, "templates", "instruments")
        yield os.path.join(meipass, "instruments")

    # Source checkout: tools/operator/ -> tools/ -> templates/instruments/.
    yield os.path.join(_TOOLS_DIR, "templates", "instruments")


def template_path(key):
    """Return the absolute path to the per-instrument template for `key`.

    `key` is one of INSTRUMENT_TEMPLATES (case-insensitive). Resolves from a
    repo checkout AND from a frozen PyInstaller bundle (sys._MEIPASS-aware).

    Raises:
        KeyError: if `key` is not a known instrument key.
        FileNotFoundError: if no candidate directory holds the template file.
    """
    norm = (key or "").strip().upper()
    if norm not in INSTRUMENT_TEMPLATES:
        raise KeyError(
            f"Unknown instrument key {key!r}. "
            f"Known keys: {sorted(INSTRUMENT_TEMPLATES)}"
        )
    filename = INSTRUMENT_TEMPLATES[norm]
    tried = []
    for d in _candidate_dirs():
        candidate = os.path.join(d, filename)
        tried.append(candidate)
        if os.path.isfile(candidate):
            return candidate
    raise FileNotFoundError(
        f"Template {filename!r} for instrument {norm!r} not found. "
        f"Looked in:\n  - " + "\n  - ".join(tried)
    )


def load_template(key):
    """Load the per-instrument template for `key` to a dict (via config.load_config).

    Returns a fresh dict each call (config.load_config re-reads the file), so
    callers may mutate the result freely.

    Raises:
        KeyError / FileNotFoundError: see `template_path`.
        ValueError: if the template file is empty (from config.load_config).
    """
    return config.load_config(template_path(key))


def known_keys():
    """Return the sorted list of supported instrument keys."""
    return sorted(INSTRUMENT_TEMPLATES)
