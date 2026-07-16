# Independent review — override-semantics design issue

**Reviews:** [`microscopy_gui_override_semantics_handoff.md`](microscopy_gui_override_semantics_handoff.md) (the dev's writeup) + the code on this branch.
**Branch:** `fix/microscopy-gui-filters-and-gaps` @ `0a590f4`
**Reviewer:** independent session (did not author this branch); verified against the code, not just the doc.
**Date:** 2026-07-16

---

## 0. Verdict

**The diagnosis is correct and the doc is honest.** I reproduced the core behaviour
directly and read the full front-end diff. Three things to carry into the decision:

1. **The merge layer (`config_builder`) is behaving correctly.** Omission→inherit,
   explicit-empty→clear, override→replace all work as intended. The defect is entirely
   **UI-side**: the builder can't *express* an explicit empty for the structural keys,
   and the runner filter is built over the wrong base. This **shrinks the fix** and
   answers Ryan's "touches too many things" worry — the correct fix does **not** touch
   ingest/merge semantics.
2. **This branch's changes are good and should be kept** — but its "additive runner
   filter" fix is **only partial**: it still drops the template filter (`group_code=MFB`)
   whenever the recipe *inherits* it (the common case). See §5.
3. **C and D are a false dichotomy** (Ryan's question). The template filter is *already*
   a removable default; the fix is A+B, no engine change, no lock, no removal. See §4.

**Recommended fix:** **A + B** (make the recipe self-complete for structural keys **and**
show/consume the *effective* config), with structural keys treated differently from value
fields (§6). **Reject C** (locks out the collaboration case). **Reject D** (discards a
useful default). Do **not** revert this branch — build the fix on top of it.

---

## 1. What I verified independently

- **Reproduced handoff §2/§8** against `config_builder.build_config()` with the ZWSI
  template (this branch does not touch `config_builder.py`/`templates.py`, so the
  behaviour here is identical to the branch):

  | override | effective `auto_discover.filter` |
  |---|---|
  | `{}` (recipe omits filter) | `{'group_code': 'MFB'}` — template reasserts |
  | `{"auto_discover.filter": {}}` (explicit empty) | `{}` — **cleared** |
  | `{"auto_discover.filter": {"stain": "foo"}}` | `{'stain': 'foo'}` — **replaces** (MFB gone) |

  → Confirms the trap is real, and that an *explicit empty clears the filter*. The
  engine already supports "remove the template filter"; only the builder can't send it.

- **Read the full front-end diff** (`app.js`, `app.py`, `value_fields.py`, `index.html`).
- **Traced the ingest consumer** of `filename_parse` (`config.py`, `filename_parser.py`)
  to settle handoff open-question §7.1.

---

## 2. §7.1 resolved: ingest **does** tolerate `filename_parse.fields = []`

`filename_parser.parse()` raises on empty fields (`filename_parser.py:41-42`), **but the
ingest path never calls it with empty fields** — `config.py` guards it:

```python
# config.py:455
if parse_fields or parse_regex:        # whole parse+filter block gated
    ...
    if parse_fields:                   # :465 positional parse additionally gated
        parsed.update(filename_parser.parse(...))
```

With `fields=[]` and no regex the block is skipped: no parse, no error, `discovered` just
gets nothing from the filename. This holds for **preview and ingest** (same code path).

**Consequences:**
- Ryan's **"zero labels must not break ingest" requirement holds** — confirmed in code.
- **Solution A is safe**: writing an explicit `fields: []` will not break ingest.
- The retracted "block saving with zero labels" idea is **correctly retracted** — no such
  guard is needed.

## 3. Finding beyond the handoff: `filter` is coupled to `filename_parse`

The doc treats `filter` and `filename_parse` as independent structural keys. In the engine
they are not. The filter is a **predicate over the parsed filename values** (`config.py:474-485`,
`parsed.get(k) != expected`), and that loop is nested **inside** the same
`if parse_fields or parse_regex:` guard. So:

1. **Empty the labels → the `group_code=MFB` filter silently stops working** (no `parsed`
   to match against). "Empty fields" and "drop the filter" are **not independent**.
2. **A filter on a key that isn't a parsed field zeroes the whole batch** — `parsed.get(k)`
   is `None`, never equals `"MFB"`, so *every* file is skipped and nothing ingests.

This directly bears on the MFB decision (§4) and the runner "narrow-only" feature (§5): a
filter only functions in tandem with parsing its key. **Recommendation:** the builder/runner
should only offer filter keys that are in the parse set (or warn) — otherwise "add a
condition" can silently empty a batch.

---

## 4. Ryan's question: why can't the template keep `group_code=MFB` *and* let the operator remove it?

**It can — that's already the engine's behaviour, and it's the right model.** The C/D framing
is a false dichotomy created by the *builder UI*, not the engine:

- Template filter = **default**. Recipe **omits** it → inherit `MFB`; recipe sets `{}` →
  **cleared**; recipe sets `{k:v}` → **replaced** (proven in §1).
- The only reason it *feels* locked is that the builder **omits** the filter key when the
  box is empty (it has no way to serialize an explicit empty), so from the UI you can change
  the filter but not clear it.

So for the exact scenario Ryan described — **MFB by default, one group today, but drop/relax
it for an occasional collaboration** — the fix is **A + B**, with **no** engine change:

- **A** lets the builder express an explicit empty/edited filter, so "remove MFB for this
  recipe" is possible and sticks.
- **B** shows the *effective* filter, so the operator **sees** MFB is in force (inherited)
  and removes it as a conscious choice.

- **Reject C (instrument-lock):** it removes exactly the collaboration option Ryan wants to keep.
- **Reject D (delete MFB from the template):** it throws away a useful default; MFB is a good
  default *because* it's removable.

---

## 5. This branch's changes — keep them; the runner-filter fix is only half-done

**Keep (good, well-scoped, independently valuable):**

- **`value_fields.py`** — a single source of truth for the "values to record" catalogue,
  replacing the drifting JS `REQUIRED_FIELDS` / Python `CRITICAL_FIELDS`. This fixes a real
  bug (`registry.session_id` was un-promptable). Clean, dependency-free, tested. **Keep.**
- **`GET /api/value_fields` + data-driven builder grid + `recipe_gaps` from the shared list.**
  **Keep.**
- **Filter-dropdown preset round-trip** (`app.js` `fieldOptions()` unshifts a preset/kept
  field so it isn't silently dropped on save) — good bug fix. **Keep.**
- **Both "Show metadata labels" buttons feed the filter dropdown** — good fix. **Keep.**

**Needs work:**

- **Runner filter is only *partially* additive.** `runnerFilter()` (app.js) now merges the
  operator's rows with `currentRecipeOverrides()["auto_discover.filter"]` — the recipe's
  **explicit** override. But when the recipe **inherits** the filter from the template (e.g.
  `Axioscan7_6Chunks_MFB-v3`, which stores no filter of its own), that key is `undefined`,
  so:
  - operator adds **no** condition → sends `{}` → template `MFB` inherited → ✅ correct;
  - operator adds `stain=X` → sends `{stain:X}` → **replaces** template filter → **MFB
    dropped**, batch widened to all groups. ⚠️ The handoff's §2 second bug persists for
    inherited filters (the common case). The front-end can't fix this alone — it doesn't
    know the template's filter. **This is why B is required, not merely cosmetic.**
  - The new runner note is also actively misleading for inherited filters: it says *"This
    recipe defines no filter of its own — add conditions to scope this batch,"* while ingest
    is in fact filtering to `MFB`. B fixes the message too.
- **Blank-start builder increases exposure.** Making the builder start blank (no auto-seed)
  is reasonable **for value fields**, but for **structural keys** it means a from-scratch
  recipe omits `filter`/`filename_parse` and silently inherits the template — the exact trap.
  See §6 for the reconciliation.

**On "touches too many things":** the breadth is *mostly justified* — these are real,
independent fixes. The issue isn't that the branch does too much; it's that it doesn't yet
do the **one** semantic thing (A+B) that makes the rest honest. Add it; don't revert.

---

## 6. Recommendation — A + B, with structural keys ≠ value fields

The key design move the handoff doesn't quite make explicit: **structural keys and value
fields want *different* blank-semantics.**

- **Value fields** (researcher, sample_id, …): blank = a deliberate **gap** the runner
  prompts for. This branch's model (`value_fields.py` `gap` flag) is correct — **keep it**.
- **Structural keys** (`filter`, `filename_parse`, `path_parse`): these encode a *convention*,
  not a per-batch value. They should be **seeded from the template, shown, and always written
  explicitly** by the builder (solution A). Then:
  - a from-scratch recipe captures the instrument convention (incl. `MFB` + the 6 parse
    fields) rather than silently inheriting it;
  - editing or **clearing** them sticks and is visible (WYSIWYG);
  - "remove MFB for a collaboration" becomes an explicit, honest recipe.

  This is a *targeted* partial-revert of the blank-start behaviour **for structural keys
  only** — it keeps the blank-start intent where it belongs (value fields).

- **B — expose the effective config.** `build_config(template, overrides)` already produces
  the merged config server-side. Expose it (e.g. `POST /api/effective_config` → merged
  `auto_discover`), and have **both** front-ends display "what will actually ingest," and
  have the **runner build its filter over the effective filter** (AND the operator's rows
  onto template+recipe), which is what finally fixes the drop-MFB bug in §5.

- **Filter-key guard** (from §3): only offer filter keys that are in the effective parse
  set; warn otherwise.

---

## 7. Concrete change plan (minimal, by file)

1. **`gui/app.py`** — add `POST /api/effective_config` returning
   `config_builder.build_config(template, overrides)["auto_discover"]` (filter +
   filename_parse + path_parse). (`build_config` is already imported and used by
   `recipe_gaps`.)
2. **`gui/static/app.js` — builder:**
   - seed `filter` / `filename_parse` / `path_parse` from the template on builder init and
     instrument-change (partial revert of the blank-start, structural keys only);
   - in `builderOverrides()`, **always** emit those three keys explicitly, including an
     explicit empty (`filter:{}`, `filename_parse:{separator, fields:[]}`);
   - restrict the filter-key dropdown to the current parse fields (+ warn).
3. **`gui/static/app.js` — runner:**
   - fetch `/api/effective_config` for the chosen instrument+recipe;
   - display the **effective** filter ("this batch will ingest only `group_code=MFB` —
     from the template") instead of the recipe-only view;
   - build `runnerFilter()` as `{...effectiveFilter, ...operatorRows}` with a rule that
     operator rows may only **add/narrow** (or make "widen/clear" an explicit, confirmed action).
4. **`gui/templates/index.html`** — copy updates to match the effective-config display.
5. **No change to `config_builder.py`, `config.py`, `filename_parser.py`, `templates.py`,
   or anything under `ingest/`.** The semantics are already correct.

## 8. Decisions still needed from Ryan

1. **Widen/clear from the runner:** may an operator *widen* (drop MFB) from the **runner**,
   or only from the **builder** (per-recipe)? Recommendation: runner **narrows only**;
   widening/collaboration is a deliberate builder/recipe act. (This also sidesteps §3's
   zero-batch trap.)
2. **From-scratch recipe with no template loaded:** confirm it should capture the
   convention (implied by §6) rather than be allowed to save empty structural keys.

## 9. Verification plan for the fix (once implemented)

- **Backend/unit:** `build_config` round-trips `filter:{}` and `filename_parse:{fields:[]}`
  (shown in §1); `/api/effective_config` returns template values for an inheriting recipe.
- **Ingest tolerance:** a preview with `fields:[]` runs and parses nothing, no error (§2).
- **Live GUI (this worktree, `python app.py --port 5001` — port 5000 has production exes):**
  1. load `Axioscan7_6Chunks_MFB-v3` in the runner → it now **shows** `group_code=MFB` as
     effective; add `stain=X` → preview shows the batch still scoped to `MFB` **AND** `stain=X`.
  2. in the builder, clear the filter, save → the recipe stores `filter:{}` and preview shows
     **no** MFB filter (collaboration case), WYSIWYG.
  3. empty the labels box, save → recipe stores `fields:[]`, preview parses nothing and does
     not error, and the runner reflects it.
