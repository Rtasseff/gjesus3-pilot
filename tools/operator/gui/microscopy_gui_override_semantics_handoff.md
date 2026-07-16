# Handoff — template/recipe override semantics: silent template reassertion

**Branch:** `fix/microscopy-gui-filters-and-gaps`
**Written:** 2026-07-16 (during manual GUI testing of the branch)
**Status:** ⚠️ **Design issue — needs review BEFORE the microscopy ingest test.** The
code on this branch is committed, but it exposed a deeper behaviour that means a
recipe can display one thing in the GUI and ingest another. Do not trust recipes
for the real ingest test until the decision in §5 is made.

> This doc is the review/design writeup the Data Office lead (Ryan) asked for. The
> mechanical GUI-fix context is in the sibling
> [`microscopy_gui_filters_gaps_handoff.md`](microscopy_gui_filters_gaps_handoff.md).

---

## 1. TL;DR — the issue in one paragraph

In the operator GUI, a recipe is a set of **overrides on top of a per-instrument
template**. At ingest the effective config is `template` deep-merged with the
recipe's overrides: **an override replaces its key; a key the recipe omits keeps
the template's value.** The builder only *writes* the structural keys (`filter`,
`filename_parse`, `path_parse`) when they are **non-empty**. So **emptying one of
these in the builder makes the recipe omit it, and the template's value silently
reasserts at ingest** — while the builder and runner still show the emptied
state. What you see is not what ingests. That is the bug.

---

## 2. Exactly what happens (proven against the real code)

Reproducible directly through `config_builder.build_config()` with the ZWSI
(AxioScan) template, whose `auto_discover` block defines
`filter: {group_code: MFB}` and a 6-field `filename_parse`:

| Operator action in the builder | Recipe stores | Effective at ingest |
|---|---|---|
| Change labels to `a,b,c` (3) | `filename_parse.fields:[a,b,c]` | `[a,b,c]` — sticks ✅ |
| Keep 5, drop `stain` | `fields:[…5…]` | those 5 — sticks ✅ (stain **not** re-added) |
| Keep 1 label | `fields:[researcher]` | `[researcher]` — sticks ✅ (does **not** snap to 6) |
| **Empty the labels box (0)** | *(key omitted)* | **template's 6 reassert** ⚠️ |
| Set a filter `x=y` | `filter:{x:y}` | `{x:y}` — sticks ✅ |
| **Drop the filter (0 rows)** | *(key omitted)* | **template's `group_code=MFB` reasserts** ⚠️ |

Key correction to an earlier miscommunication: the reassertion is **all-or-nothing
at the whole key**, and only when the field is emptied to **zero**. Partial edits
(add/remove/reorder labels, change a value) *stick*. The template never "adds back
an individual removed label" and never snaps 1→6.

A second, related runner bug in the same family: `runnerFilter()` sends the
operator's added conditions as the *entire* `auto_discover.filter`, which
**replaces** the template filter at ingest. So an operator who adds a condition to
*narrow* a batch actually **drops** `group_code=MFB` and *widens* scope — the
opposite of the "operator can only narrow" intent stated in the branch.

---

## 3. What can and cannot be overridden (the map Ryan asked for)

**Backend whitelist** (`config_builder.py`):

- **Overridable:** `auto_discover.{staging_dir, pattern, filename_parse,
  path_parse, filter, acquisition_date_from, subject_from_db, subject_lookup}`;
  ingest **flags** `{reconstructions, auto_regenerate_dicom,
  delete_source_after_ingest, auto_create_projects}`; any `registry.<column>`;
  `auto_create_project.*`, `condition.*`, `anatomy.*`, `subject.*`;
  `link_filename`; `operator`.
- **Hard-locked (raises `OverrideError`):** `ingest.copy_strategy`,
  `ingest.acquisition_layout` (they select the copy machinery / primary-file
  shape). Anything not on the whitelist is rejected outright.

**The nuance that caused the confusion:** at the **backend** every whitelisted key
is fully overridable *for any non-empty value*. The limitation is in the
**builder UI**, which cannot *express an empty* override for the structural keys —
so from the UI you can **change** them but not **clear** them. "Overridable
per-recipe" (backend) and "reasserts to template when emptied" (builder omission)
are both true; stated without that distinction they sound contradictory.

---

## 4. History — how we got here

1. **Value fields use a deliberate gap-field model** (see
   [`value_fields.py`](../value_fields.py)): a blank field = inherit the template
   default; an *explicit* blank (`""`) = a runner "fill per batch" gap. Coherent
   for registry values, and it's why "blank = inherit" feels natural.
2. **The structural keys reuse "blank = inherit" via omission** — but they have
   **no "explicit blank" control**, so in the UI a blank can *only* mean inherit.
   That asymmetry is the root of the trap.
3. The original branch made the **runner filter "additive"** assuming the recipe's
   filter override was the whole story. It isn't — templates carry filters too, so
   the runner both mis-displays and (via §2) can mis-enforce scope.
4. **This session's changes** (see §7) fixed the runner filter-dropdown
   population, made the builder **start blank** (no auto-load of template
   defaults), and made a preset filter **round-trip** into the recipe. The
   blank-builder change is good UX but **increases** how often a from-scratch
   recipe omits structural keys → more reliance on template reassertion → makes
   resolving this issue more urgent, not less.

---

## 5. Possible solutions (the decision to make)

- **A — Recipe-complete for structural keys (recommended).** The builder *always*
  writes `filter` / `filename_parse` / `path_parse` explicitly, including an
  explicit *empty*. The template becomes only the "Load template defaults"
  scaffold, never a silent ingest override. WYSIWYG holds and it matches Ryan's
  model ("the recipe is the source of truth"). Open sub-question: what an *empty*
  from-scratch recipe should mean (see §6/§7).
- **B — Keep "omit = inherit", but display the EFFECTIVE (template+recipe) config**
  in both builder and runner (backend returns the merged config). Nothing is
  hidden even if it can't be cleared. Smallest, safest first step; pairs with A.
- **C — Instrument-locked filter.** If `group_code=MFB` is really a fixed safety
  net, mark it locked (like `copy_strategy`) and show it as *enforced /
  non-editable* in both UIs. Removes the "can I drop it?" ambiguity.
- **D — Remove `group_code=MFB` from the template.** A data-scope decision; then
  there's no filter inheritance to reconcile.

Recommendation: **B now** (make it visible / honest immediately) **+ A** (make the
recipe authoritative) as the real fix; decide **C vs D** for the MFB filter
specifically as a separate data-scope call.

---

## 6. Ryan's concerns (to honor in the review)

- **Scope:** the fix "touches too many things" — wants a review before adoption.
- **Zero labels must NOT break ingest.** Filename parsing is a **convenience** for
  auto-populating registry values (`${discovered.*}`), **not a requirement**.
  Registry values can be entered manually or derived from folders. ⇒ An earlier
  suggestion here to *block saving with zero labels* is **suspect and must not be
  implemented** without first verifying the discovery/scope code actually tolerates
  `filename_parse.fields = []` (see §7). Treat that suggestion as retracted pending
  verification.
- **Communication:** "overridable per-recipe" vs "reasserts to template" read as
  contradictory; §2–§3 above are the corrected, precise statement.
- **Timing:** the microscopy ingest test planned for the next day may be
  **postponed** until this is resolved.

---

## 7. Open questions / to verify

1. **Does ingest tolerate `filename_parse.fields = []` (no parsing at all)?**
   Expected **yes** per the architecture (registry filled manually / from
   folders). Must be checked in `scope.py` / `preview.py` / the discovery path
   before any "require labels" behaviour is even considered.
2. For solution **A**: how to represent/confirm "deliberately no filter / no
   parse" vs "not yet configured" in a from-scratch recipe.
3. Should registry gap-field semantics and structural-key semantics be **unified**
   or intentionally kept different?

---

## 8. What changed on this branch (for the reviewer)

- **New:** [`value_fields.py`](../value_fields.py) + [`test_value_fields.py`](../test_value_fields.py)
  — one shared "values to record" catalogue for builder + runner.
- **`gui/app.py`** — `GET /api/value_fields`; `recipe_gaps` uses
  `value_fields.gap_fields()`; deleted the old `CRITICAL_FIELDS`.
- **`gui/static/app.js`** — shared catalogue drives builder + runner; runner filter
  additive; **dual "Show metadata labels" button** both feed the filter dropdown;
  **builder starts blank** (no auto-load on init or instrument-change); **preset
  filter round-trips** (field kept in the dropdown even before labels load); filter
  area always states its status.
- **`gui/templates/index.html`** — explanatory-comment updates.
- **No change to `config_builder.py`.** The merge semantics in §2 are the
  *existing* behaviour — documented here, **not** yet altered.

Reproduce the trap directly (no browser needed):

```python
import sys; sys.path.insert(0, "tools/operator/gui")
import app as gui
t = gui.templates.load_template("ZWSI")
f = lambda ov: (gui.config_builder.build_config(t, ov).get("auto_discover") or {}).get("filter")
print(f({}))                               # {'group_code': 'MFB'}  (template)
print(f({"auto_discover.filter": {}}))     # {}   -> an explicit empty DOES clear it
# ...but the builder omits the key when the filter is empty, so the recipe never
# sends {}, and the template's {'group_code':'MFB'} reasserts at ingest.
```

---

## 9. Resume / how to test the GUI

- Dev server: `python tools/operator/gui/app.py --port 5001`
  (**use 5001** — port 5000 currently has 3 *production* `gjesus3_ingest.exe`
  instances running from the NAS; leave those alone). Hard-refresh (Ctrl+F5) to
  pick up static JS changes.
- Repro in the UI: load `Axioscan7_6Chunks_MFB-v3` in the runner → it shows no
  recipe filter, yet ingest filters to `group_code=MFB`; or empty the labels box
  in the builder, save, and observe the template's 6 fields reassert at ingest.
