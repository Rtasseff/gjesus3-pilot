"""Single source of truth for the operator GUI's "values to record" fields.

This is the catalogue of the rows in the microscopy GUI's
**"3 · Set the values to record"** section. ONE list, consumed by BOTH
front-ends so they can never drift:

  * the **builder** renders an editor row per entry, and decides how to emit a
    blank field (see `gap` below);
  * the **runner** asks `/api/recipe_gaps` which of these a chosen recipe leaves
    blank and renders a "Fill in for this batch" input for each.

Before this module the two sides kept independent hard-coded lists (a JS
`REQUIRED_FIELDS` and a Python `CRITICAL_FIELDS`). They disagreed — e.g.
`registry.session_id` existed only in the builder, so leaving it blank in a
recipe silently never surfaced in the runner, while `registry.project_name`
(present in both) worked. Driving both front-ends from this single list makes
the behaviour uniform: blank-in-builder → fillable-in-runner for EVERY field,
and adding/renaming a field is a one-line edit here that both sides pick up.

Keep this module dependency-free (pure data) so it loads anywhere — the GUI
imports it through the operator-core loader, and `test_value_fields.py` imports
it directly without Flask.

Each entry:
  key      dotted config path: a ``registry.<column>`` expression, or a
           top-level config key (``operator`` / ``link_filename``). Must match a
           `config_builder` whitelist target so the override actually applies.
  label    operator-facing label shown beside the input.
  kind     "token"      -> metadata-label chips + free text (a TokenField), or
           "sampletype" -> the controlled sample_type dropdown.
  hint     short gloss shown after the label (may be "").
  star     high-priority field; the builder marks it with a ★. Visual only.
  required a real GAP in this field BLOCKS ingest until the operator fills it in
           the runner. Non-required gaps are offered but skippable.
  gap      gap-capable. When True, the builder emits the field even when blank
           (an explicit "" — a DELIBERATE "prompt per batch" that overrides the
           template default), and the runner offers it whenever the effective
           value is blank. When False, a blank field is omitted from the recipe
           and falls back to the template default (never surfaced in the runner).

           Every field is currently gap-capable so the behaviour is uniform; the
           flag is kept explicit so a future field can opt out deliberately
           rather than by accident.
"""

# Order here is the builder's top-to-bottom display order.
VALUE_FIELDS = [
    {"key": "registry.researcher",          "label": "Researcher",        "kind": "token",      "hint": "who ran the study",           "star": True,  "required": True,  "gap": True},
    {"key": "operator",                     "label": "Operator",          "kind": "token",      "hint": "who ran the equipment",       "star": True,  "required": False, "gap": True},
    {"key": "registry.sample_id",           "label": "Sample ID",         "kind": "token",      "hint": "",                            "star": True,  "required": True,  "gap": True},
    {"key": "registry.sample_type",         "label": "Sample type",       "kind": "sampletype", "hint": "controlled vocabulary",       "star": False, "required": True,  "gap": True},
    {"key": "registry.acquisition_datetime", "label": "Acquisition date", "kind": "token",      "hint": "",                            "star": False, "required": False, "gap": True},
    {"key": "registry.project_name",        "label": "Project name",      "kind": "token",      "hint": "the project's name — matches its folder", "star": False, "required": False, "gap": True},
    {"key": "registry.session_id",          "label": "Session ID",        "kind": "token",      "hint": "",                            "star": False, "required": False, "gap": True},
    {"key": "registry.notes",               "label": "Notes",             "kind": "token",      "hint": "",                            "star": False, "required": False, "gap": True},
    {"key": "link_filename",                "label": "Project link name", "kind": "token",      "hint": "the file name if left blank", "star": False, "required": False, "gap": True},
]

# The two input renderings a `kind` may select.
VALID_KINDS = {"token", "sampletype"}


def builder_fields():
    """The catalogue as the builder consumes it (every field, in order)."""
    return [dict(f) for f in VALUE_FIELDS]


def gap_fields():
    """The gap-capable subset — the only fields the runner can prompt for."""
    return [dict(f) for f in VALUE_FIELDS if f.get("gap")]
