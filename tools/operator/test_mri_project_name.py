#!/usr/bin/env python3
"""test_mri_project_name.py — the MRI page's destination project is token-valued.

The MRI ingest page long offered clickable `${discovered.*}` metadata chips for
the project LINK name but not for the **project name** — the field that decides
which project a scan is *associated with*. That field was a plain text box, so
it held one static string for a whole run, and an operator pulling several
protocols in one go had no way to express "each scan goes to the project its own
metadata names" without hand-editing YAML.

Nothing in the engine ever prevented this: `registry.project_name` is a
token-resolvable user-controllable column (`ingest/resolver.py`), and the MRI
template's own default is the token expression
`AE-biomaGUNE-${discovered.project_code}`. Only the UI was missing.

This test guards the four things that, if quietly undone, would put it back:
  1. the project field is a TokenField with a palette (not an `<input>`),
  2. that palette withholds the per-scan fields, which would mint one project
     per scan rather than group scans into projects,
  3. `_mri_overrides` passes a token expression through untouched, and
  4. an operator-named project doesn't inherit the template's auto-create
     description claiming it came from an animal-protocol code.

Pure: reads the GUI sources as text and imports `app.py` only if Flask is
present (skipping those checks cleanly if it is not, as `test_value_fields.py`
does for its own dependencies).

Run:  python tools/operator/test_mri_project_name.py
"""

import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.join(_HERE, "gui")

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok:   {msg}")


def _read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read()


# --------------------------------------------------------------- the markup
html = _read(_GUI, "templates", "mri.html")

check('id="project-field"' in html,
      "mri.html: the project name is a tokenfield container")
check('<input id="project-name"' not in html,
      "mri.html: the plain project-name <input> is gone")
check('id="project-palette"' in html,
      "mri.html: the project field has its own palette container")
check('id="project-example"' in html,
      "mri.html: the project field shows a live resolved example")
check("projectPaletteKeys" in html,
      "mri.html: the project palette keys reach the page")
check('id="project-summary"' in html,
      "mri.html: the preview has a per-destination project breakdown")

# ------------------------------------------------------------------- the JS
js = _read(_GUI, "static", "mri.js")

check('new TokenField($("#project-field")' in js,
      "mri.js: the project field is a TokenField")
check("spacesToHyphens: true" in js,
      "mri.js: typed spaces become hyphens (a project's name IS its folder name)")
check("projectNameInput" not in js,
      "mri.js: no leftover reference to the old plain input")
check("function distinctProjects(" in js and "function renderProjectSummary(" in js,
      "mri.js: the run's destination projects are summarised before ingest")
check("function projectError(" in js,
      "mri.js: an empty custom name is refused, not silently read as 'no project'")

# ------------------------------------------------------ the backend (needs Flask)
if importlib.util.find_spec("flask") is None:
    print("  skip: Flask not installed — backend checks skipped")
else:
    sys.path.insert(0, _GUI)
    import app as gui  # noqa: E402

    default = gui._mri_template_project_name()
    check(default.startswith("AE-biomaGUNE-") and "${discovered." in default,
          "the MRI template's own project_name is already a token expression")

    per_scan = {"mri_exam_number", "mri_recon_indices", "mri_sequence_name"}
    check("project_code" in gui.MRI_PROJECT_PALETTE_KEYS,
          "the project palette offers the animal-protocol code")
    check(not (per_scan & set(gui.MRI_PROJECT_PALETTE_KEYS)),
          "the project palette withholds per-scan fields (they'd mint one "
          "project per scan)")
    # A chip that names a field nothing produces would sit in the palette and
    # resolve to nothing — so every offered key must come from either the
    # template's own filename regex or the embedded ParaVision extractor.
    import re as _re
    _tpl = gui.templates.load_template(gui.MRI_KEY)
    _rx = ((_tpl.get("auto_discover") or {}).get("filename_parse") or {}).get("regex", "")
    parsed = set(_re.findall(r"\(\?P<([A-Za-z_]\w*)>", _rx))
    embedded = {k for k in gui.MRI_LINK_PALETTE_KEYS if k.startswith("mri_")}
    unknown = set(gui.MRI_PROJECT_PALETTE_KEYS) - parsed - embedded
    check(not unknown,
          f"every project-palette chip is a field that actually resolves "
          f"(unknown: {sorted(unknown)})")

    expr = "MFB-${discovered.project_code}"
    ov = gui._mri_overrides({"project_mode": "fixed", "project_name": expr})
    check(ov.get("registry.project_name") == expr,
          "a token expression reaches registry.project_name verbatim")
    check("animal-protocol code" not in
          ov.get("auto_create_project.description", ""),
          "an operator-named project isn't described as protocol-derived")

    ov_auto = gui._mri_overrides({"project_mode": "auto"})
    check("registry.project_name" not in ov_auto,
          "auto mode leaves the template's expression alone")
    check("auto_create_project.description" not in ov_auto,
          "auto mode leaves the template's auto-create description alone")

    ov_same = gui._mri_overrides({"project_mode": "fixed",
                                  "project_name": default})
    check("auto_create_project.description" not in ov_same,
          "re-typing the default does not rewrite the description")

    ov_none = gui._mri_overrides({"project_mode": "none"})
    check(ov_none.get("registry.project_name") == "",
          "'no project' still clears project_name (no links)")

    # Every override produced above must survive the operator whitelist.
    from gj_op_core import config_builder as cb  # noqa: E402
    tpl = {"registry": {}, "auto_create_project": {}, "ingest": {}}
    for label, o in (("fixed+token", ov), ("auto", ov_auto), ("none", ov_none)):
        try:
            cb.build_config(tpl, o)
            check(True, f"config_builder accepts the {label} overrides")
        except cb.OverrideError as e:
            check(False, f"config_builder accepts the {label} overrides ({e})")

print()
if FAILS:
    print(f"{len(FAILS)} CHECK(S) FAILED")
    sys.exit(1)
print("ALL MRI PROJECT-NAME CHECKS PASSED")
