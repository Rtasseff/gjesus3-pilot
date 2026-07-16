# Handoff — microscopy GUI filters & gaps fix

**Branch:** `fix/microscopy-gui-filters-and-gaps`
**Written:** 2026-07-10 (session paused for a workstation reset)
**Status:** ✅ committed + pushed 2026-07-16. Backend verified end-to-end; manual GUI
testing that day surfaced follow-on fixes **and a deeper design issue** — see the
update note below.

> **Update — 2026-07-16.** During manual GUI testing this branch grew beyond the
> two original fixes:
> - **Runner filter dropdown fix** — the two identically-labelled "Show metadata
>   labels from the folder" buttons now both populate the filter's label list.
> - **Builder starts blank** — template defaults no longer auto-load on page open
>   or instrument-change; they load only via the "Load template defaults" button
>   (or when loading a saved recipe). A fresh builder is no longer pre-filled.
> - **Preset filters round-trip** — a template filter (e.g. `group_code=MFB`) now
>   keeps its *field* in the dropdown even before metadata labels load, so it saves
>   into the recipe and reaches the runner instead of being silently dropped.
>
> Testing then uncovered a **template/recipe override-semantics problem** (a recipe
> can display one config but ingest another). That is written up separately and
> **must be reviewed before the microscopy ingest test**:
> [`microscopy_gui_override_semantics_handoff.md`](microscopy_gui_override_semantics_handoff.md).
> The original test steps (§5) and commit notes (§6) below are retained for record.

---

## 1. What this branch fixes

Two independent problems in the microscopy operator GUI
(`tools/operator/gui/`, the builder + recipe-runner pages):

1. **Value-field / gap drift (the main bug).** The **builder** page ("3 · Set the
   values to record") and the **runner** page ("Fill in for this batch") each kept
   their *own* hard-coded list of fields:
   - builder → a JS `REQUIRED_FIELDS` array in `static/app.js`
   - runner → a Python `CRITICAL_FIELDS` list in `app.py`

   The two lists disagreed. Concretely: `registry.session_id` existed only in the
   builder's list, so leaving it blank in a recipe **never surfaced** as a
   fillable gap in the runner — the operator could never supply it per batch,
   while a sibling field like `registry.project_hint` (present in both lists)
   worked fine. Silent, field-dependent behaviour.

2. **Runner filter was all-or-nothing.** When a recipe defined a filter, the
   runner showed it read-only and **blocked** the operator from adding any
   further conditions; the operator's own filter rows only worked when the recipe
   set *no* filter. There was no way to narrow a filtered recipe for a single
   batch.

---

## 2. The fix (design)

**Single source of truth for value fields.** New module
`tools/operator/value_fields.py` holds ONE `VALUE_FIELDS` catalogue. Both
front-ends now draw from it:

- builder fetches it once at page load via new endpoint **`GET /api/value_fields`**
  (returns `value_fields.builder_fields()`), and renders its rows from that
  instead of the deleted JS `REQUIRED_FIELDS`;
- runner's **`POST /api/recipe_gaps`** now iterates `value_fields.gap_fields()`
  instead of the deleted Python `CRITICAL_FIELDS`.

Result: **blank-in-builder → fillable-in-runner for EVERY field**, uniformly.
Adding/renaming a field is now a one-line edit in `value_fields.py` that both
sides pick up — they can't drift again.

Each catalogue entry carries: `key, label, kind ("token" | "sampletype"), hint,
star, required, gap`. See the module docstring for the exact meaning of each
(esp. `gap` = "blank is saved as an explicit `""` the runner prompts for, instead
of falling back to the template default").

**Runner filter is now additive.** The recipe's filter (if any) is shown
read-only **and forcibly applied**; the operator can **always** add more
`label=value` conditions on top. They're ANDed in, and on a key collision the
**recipe wins** — so the operator can only *narrow* a batch, never weaken the
recipe's scope. Logic is in `runnerFilter()` / `updateFilterPanel()` in `app.js`.

---

## 3. Files changed

| File | State | What |
|---|---|---|
| `tools/operator/value_fields.py` | **new** | The single `VALUE_FIELDS` catalogue + `builder_fields()` / `gap_fields()` helpers. Pure data, no Flask — imports anywhere. |
| `tools/operator/test_value_fields.py` | **new** | Invariants for the catalogue: shape, `required ⇒ gap`, helper copies, and **every key is a real `config_builder` override target**. Runs standalone. |
| `tools/operator/gui/app.py` | modified | Deleted `CRITICAL_FIELDS`; imports `value_fields` through the core loader; added `/api/value_fields`; `/api/recipe_gaps` now uses `value_fields.gap_fields()`. |
| `tools/operator/gui/static/app.js` | modified | Deleted `REQUIRED_FIELDS`; fetches the catalogue into `VALUE_FIELDS` via `loadValueFields()` in a new async `initBuilder()` bootstrap; grid + template-seed + override collection are now data-driven over it; runner filter made additive (`runnerFilter`, `updateFilterPanel`); `loadGaps()` clears added filter rows on recipe/instrument change. |
| `tools/operator/gui/templates/index.html` | modified | Updated the two explanatory HTML comments (gaps section + filter section) to match the new additive-filter / shared-catalogue behaviour. |

Nothing else touched. No changes to the ingest pipeline, resolver, or registry.

---

## 4. Current state

- `python tools/operator/test_value_fields.py` → **all invariants hold** (green as of writing).
- **Nothing is committed on this branch yet** (`git log main..HEAD` is empty). All
  five files above are in the working tree only.
- The integrity-mirror rule in `CLAUDE.md` (09 spec ↔ `EXPOSED_FIELDS`, 10 ↔
  templates) was *not* obviously implicated by this change — it only reshuffles
  where the GUI's field list lives, not the registry schema — but **double-check
  `mfb-rdm-docs/09` / `10` before committing** in case the field catalogue is
  documented there and should point at `value_fields.py` now.

---

## 5. HOW TO TEST THE GUI (the thing we paused for)

Dev run (Windows, from the repo root):

```
pip install flask          # once, if not already present
python tools/operator/gui/app.py
```

It serves **http://127.0.0.1:5000** (opens a browser). Point it at a folder of
real staging microscopy files for the discovered.* grids to populate.

**Check the two fixes:**

1. **Shared catalogue / session_id gap (main bug).**
   - Builder page → "3 · Set the values to record": confirm every field renders,
     including **Session ID** (`registry.session_id`) and **Notes**.
   - Leave **Session ID** blank, fill the ★ required ones, save as a recipe.
   - Runner page → pick that recipe → confirm **Session ID now appears** under
     "Fill in for this batch" (before the fix it was invisible). Confirm the ★
     fields (Researcher, Sample ID, Sample type) block ingest until filled and
     the rest are optional.

2. **Additive runner filter.**
   - Use a recipe that **sets a filter**. Runner should show it read-only ("This
     recipe filters to … — always applied") **and** still offer the "add
     conditions" UI.
   - Add an extra `label=value` row → Preview → confirm the batch is the recipe's
     filter **AND** your added condition (narrower), and that a row whose key
     collides with the recipe's does **not** override it (recipe wins).
   - Switch recipe/instrument → confirm added filter rows reset (they shouldn't
     carry over).

3. Sanity: builder still seeds correctly from the template on load, and a blank
   field left blank comes back as a runner gap (not silently defaulted).

---

## 6. When the GUI test passes — commit

Suggested (stage only these five files — repo rule: no `git add -A`):

```
git add tools/operator/value_fields.py \
        tools/operator/test_value_fields.py \
        tools/operator/gui/app.py \
        tools/operator/gui/static/app.js \
        tools/operator/gui/templates/index.html

git commit -m "fix(operator-gui): single value-field catalogue + additive runner filter

Share one VALUE_FIELDS catalogue (tools/operator/value_fields.py) between the
builder and the runner so blank-in-builder always becomes fillable-in-runner
(fixes registry.session_id being un-promptable). Make the runner filter additive:
the recipe filter is force-applied and the operator can AND extra conditions on
top (recipe wins on collision). Adds test_value_fields.py."
```

Then open a PR to `main` if that's the flow. Before committing, re-run the unit
test and glance at `mfb-rdm-docs/09`/`10` per §4.

---

## 7. If something's wrong in testing

- The catalogue is the one place to edit fields: `tools/operator/value_fields.py`.
  Re-run `python tools/operator/test_value_fields.py` after any change there.
- Filter merge logic: `runnerFilter()` in `static/app.js` (recipe keys win via
  `Object.assign({}, own, recipeFilter)`).
- Builder bootstrap order matters: `initBuilder()` awaits `loadValueFields()`
  **before** `buildRequiredGrid()` — if the grid renders empty, the fetch failed
  (an error banner shows in `#b-errors`).
