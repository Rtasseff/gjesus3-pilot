"""Resolve bundled data files from BOTH a source checkout and a frozen exe.

The ingest/ layer reads a few data files that live under the repo `tools/`
directory but OUTSIDE any Python package — the README / _project.yaml templates
(`tools/templates/`) and the microscopy organ map (`tools/reference/`). A naive
`dirname(__file__)`-relative path works from a source checkout but breaks inside
a frozen PyInstaller `.exe`: the module's `__file__` is under `sys._MEIPASS`, so
the naive path points at `<_MEIPASS>/...` where the file is bundled to a
different subpath (or, if the spec forgot it, is absent). That is exactly the
bug the frozen operator GUI hit — `ingest/readme.py` crashed looking for
`<_MEIPASS>/templates/README_raw.txt`.

`tools/operator/templates.py::_candidate_dirs` already solves this for the
per-instrument templates (which is why the instrument YAMLs load fine in the
exe); this gives the ingest/ layer (and top-level `create_project.py`) the same
dual-mode resolution. Follow this precedent rather than inventing a new mechanism.

Call with parts relative to the repo `tools/` dir, e.g.

    resource_path("templates", "README_raw.txt")
    resource_path("reference", "microscopy_organ_map.yaml")

Resolution order (first existing wins): the frozen-bundle locations first (so a
packaged exe prefers its bundled copy), then the source-checkout location.
"""

import os
import sys


def resource_path(*relparts):
    """Return an absolute path to a bundled data file under `tools/<relparts>`.

    Works from a source checkout AND a frozen PyInstaller bundle
    (sys._MEIPASS-aware). Does NOT guarantee the returned path exists — callers
    that must have the file should check and raise a clear error (see
    ingest/readme.py). If nothing exists the source path is returned, so a
    caller's error names the dev-facing location rather than a temp `_MEIxxxx`.
    """
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        # Our spec maps data to <_MEIPASS>/tools/... (see gjesus3_ingest.spec);
        # also try the stripped shape in case a mapping drops the tools/ prefix.
        candidates.append(os.path.join(meipass, "tools", *relparts))
        candidates.append(os.path.join(meipass, *relparts))
    # Source checkout: this file is tools/ingest/resources.py -> tools/.
    tools_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates.append(os.path.join(tools_dir, *relparts))

    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[-1]  # source path — names the dev-facing location on error
