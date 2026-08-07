# Handoff — operator GUI: reversible browse order + one obvious "load from folder"

**Branch:** `feat/gui-browse-sort-and-reload`
**Worktree:** `…\gjesus3-archive\gjesus3-dev\gui-browse-sort-and-reload`
**Branched from:** `main` @ `8b5aec4` · **Written:** 2026-08-07 · **Status:** 🔶 not started (scoped only)

Two usability problems reported by the **microscopy operator** using the deployed
`gjesus3_ingest.exe`. Both live in the shared GUI layer, so **the MRI page is
affected too** — treat this as "the operator GUI", not "the microscopy GUI".
Every line reference below is against `main` @ `8b5aec4`.

> **Framing that matters.** Neither of these is a crash or a wrong-data bug. They
> are both *"the operator can't tell what the tool wants from them next."* Judge a
> fix by whether an operator who has never read a doc does the right thing — not by
> whether the mechanism is technically reachable.

---

## Issue A — the folder browser can't reverse its sort order

### What the operator sees

The **Browse…** modal lists folders A→Z with no way to flip it. They expect the
Explorer / Finder behaviour: click a column header, the order reverses.

### Why it actually bites (the real motivation)

Instrument source folders are **named by date** — `S:\goptical\GOpticalUsers data\AxioScan\20260522`.
Ascending name order buries **today's folder at the bottom** of a list that grows
by one entry per acquisition day. Reverse-name-sort *is* newest-first for these
folders, which is what the operator wants nearly every time.

There is already a precedent for exactly this reasoning in the codebase — the MRI
SFTP exam browser sorts **reverse by name for newest-first** and says so:
`app.py:1303-1306` (docstring) and `app.py:1336`.

### Where the code is

| What | File · lines |
|---|---|
| Backend listing (`POST /api/listdir`) | `tools/operator/gui/app.py:522-566` |
| The sort itself — folders first, then case-insensitive name | `app.py:559` |
| Entry cap (**note this**, see the trap below) | `app.py:511` (`_BROWSE_LIMIT = 3000`), applied at `app.py:560-562` |
| Browser front-end — microscopy | `static/app.js:122-216` (`fb` state `:127`, `fbLoad()` `:149`, row render `:170-187`) |
| Browser front-end — **MRI (a near-verbatim duplicate)** | `static/mri.js:64-110` |
| Markup (both pages carry their own copy) | `templates/index.html:283-306` · `templates/mri.html:154-176` |
| Styles | `static/style.css:163-183` (`.fb-list`, `.fb-item`) |

### ⚠️ The trap — don't reverse on the client alone

`app.py` sorts ascending and **then truncates to 3000**. A purely client-side
reverse of what came back gives you entries 3000→1, i.e. it silently shows the
*wrong end* of a large folder while looking correct. An instrument dir with years
of day-folders can plausibly exceed 3000.

**Recommended:** pass the order to the backend (`{"path": …, "desc": true}`) and
sort **before** truncating, so the cap always trims the far end. It costs one
round trip per toggle on a local Flask app — irrelevant.
*Alternative:* keep it client-side and only refetch when `data.truncated` is set.
Slightly faster, meaningfully more logic; only worth it if the toggle feels laggy.

### Suggested shape (adjust freely)

- A thin clickable header strip above `#fb-list` — `Name ▲ / ▼` — matching the
  column-header idiom operators named. One control; `is_dir` grouping stays
  (folders first, always) and only the name order flips.
- Persist the choice for the session (`fb.sortDesc`), so toggling once holds
  while they navigate down a tree — re-sorting to A→Z on every `fbLoad()` would
  reintroduce the complaint one level deeper.
- **Do it once, use it twice.** The browser is copy-pasted into `app.js` and
  `mri.js`. Either factor the component into a shared `static/folder_browser.js`
  loaded by both templates (cleaner, and kills a standing drift risk — the
  duplication is real today), or apply the identical change in both files. **Do
  not fix only `app.js`** — a `.exe` where microscopy sorts and MRI doesn't is a
  worse bug report than the one we started with.

Sorting by **modified date** was *not* asked for. `os.scandir` gives `e.stat().st_mtime`
almost free if you want to offer it, but it is scope creep — mention it, don't
build it unless Ryan asks.

---

## Issue B — "I picked a folder… now what do I press?"

### What the operator sees

They select a source folder (runner) or an example folder (builder), see red /
empty fields, and conclude **they did the pick wrong**. They try Preview. Some
things fill in, others don't. They open the Filter section and its dropdown says
`(show metadata labels first)` — with no button anywhere in that section. Meanwhile
*two other* sections each have a button labelled **"Show metadata labels from the
folder"**, both collapsed inside `<details>`.

Ryan's summary, which is the design brief for this issue:

> *To the users, it's all just doing the same thing — loading values to get stuff
> to look right (green, and see acquisitions loaded). There is no difference between
> preview and load metadata labels, and to do it in different places, and some and
> not others, is confusing.*

### The actual mechanics (why some things fill and others don't)

Four buttons, three behaviours, one shared backend call:

| Button (id) | Handler | Sets `…Keys` (filter dropdown + palette) | Sets `…DiscoveredRow` (live examples) | Renders the results table |
|---|---|---|---|---|
| **Runner** `#r-preview` "Preview" | `runnerPreview()` `app.js:565-598` | ❌ **no** | ❌ **no** | ✅ yes |
| **Runner** `#r-gaps-load` "Show metadata labels from the folder" | `loadGapFields()` `app.js:341-358` | ✅ | ✅ | ❌ |
| **Runner** `#r-meta-load-fields` "Show metadata labels from the folder" *(identical label!)* | `loadMetaFields()` `app.js:460-485` | ✅ | ✅ | ❌ |
| **Builder** `#b-refresh-grid` "Show the metadata labels this produces" | `refreshGrid()` `app.js:1074-1116` | ✅ | ✅ | ✅ (the discovered grid) |
| **Builder** `#b-preview` "Preview example" | `builderPreview()` `app.js:1280-1304` | ❌ **no** | ✅ (`:1298`) | ✅ |

So the operator's instinct — *"Preview should fill everything in"* — is right, and
the code simply doesn't do it. `runnerPreview()` never touches `runnerKeys` /
`runnerDiscoveredRow` at all; `builderPreview()` updates examples but leaves the
palette and the filter dropdown stale.

**Both loaders hit the same endpoint with the same arguments** (`POST /api/discovered`,
`limit: 5` — `app.js:344-347` vs `:463-468`). They are one function wearing two hats.
The comment at `app.js:471-476` is a previous session patching this by hand: it
explains that `loadMetaFields` *also* has to refresh the filter because otherwise
clicking one of the two identically-labelled buttons works and the other doesn't.
That patch is a symptom — the fix below removes the need for it.

### The structural half of the bug (worth fixing even though it's latent)

The Filter fieldset is **always visible** (`app.js:381`), but it owns **no loader**
— its dropdown is populated only as a side effect of the two panels above it, and
**each of those can be hidden**:

- `#r-gaps` is hidden when the recipe leaves no gaps — `app.js:270`
- `#r-meta` is hidden unless the instrument's template has a `condition:` block — `app.js:422-431`

Today every microscopy template carries `condition:` (verified: `axioscan7`,
`cell_observer_cells`, `lsm900`, `mri_bruker`, `molecubes_ni` — all yes), so at
least one loader always exists. That is **coincidence, not design**:
`molecubes_ni_live.yaml` has no `condition:` block, so the moment an instrument
like that reaches this GUI, a fully-specified recipe leaves the filter with *no
way at all* to populate its dropdown. Giving the filter its own load path retires
this class of bug permanently.

### Recommended fix — three layers, in priority order

**1 · Auto-load when a folder is chosen (this is the root fix).**
The operator's mental model is "I picked the folder, so read it." `fbSelect()`
already dispatches `input` + `change` on the target input (`app.js:197-198`), so
a listener on `#r-staging` / `#b-staging` is enough. Use the existing cheap
`limit: 5` call. Debounce typed input; fire immediately on a browser pick.
Failure must be quiet and non-blocking — a bad path should show the existing error
line, never a modal or a disabled UI.

**2 · One loader, one name, refreshing everything.**
Collapse `loadGapFields()` + `loadMetaFields()` into a single `loadFromFolder()`
that makes one `/api/discovered` call and refreshes **every** dependent surface:
`runnerDiscoveredRow`, `runnerKeys`, the gaps palette, the meta chips, the filter
dropdown (`runnerFilterUI.refresh()`), and both example updaters. Then:

- **Make Preview do it too.** `/api/preview` already returns `cases[].discovered`
  (that's how `builderPreview()` gets its row at `:1298`), so the keys can be
  derived from `Object.keys(data.cases[0].discovered)` with **no second backend
  call** — or just call the shared loader alongside it. Either way: *pressing
  Preview must leave nothing stale.* Same for the builder's "Preview example".
- **Give the Filter section its own visible reload** (⟳ "Reload from folder"),
  removing its dependency on panels that may be hidden.
- **Un-bury the loaders** — they sit inside collapsed `<details>`
  (`index.html:78-85`, `:127-135`). A button nobody can see doesn't exist.
- **One verb, everywhere.** Right now: "Preview" / "Show metadata labels from the
  folder" (×2, identical) / "Show the metadata labels this produces" / "Preview
  example". Pick one word for *read the folder* and one for *show me the result*,
  and use them on both pages. Operator-visible strings also live in
  `static/help/microscopy_guide.html`, `static/help/mri_guide.html`,
  `tools/operator/README.md`, and `tools/OPERATOR_FAQ.md` — sweep them if you
  rename anything.

**3 · Say what's stale.**
If a value can't resolve yet because the folder hasn't been read, the message
should say *that* rather than showing an empty dropdown. `(show metadata labels
first)` at `app.js:845` is the one place that tries; it points at a button the
operator can't find. With layer 1 in place this should rarely appear at all.

### ⚠️ Do not regress these

- **The builder starts blank on purpose.** Template defaults load *only* via
  "Load template defaults" or when loading a saved recipe. A "reload" must reload
  **discovered data only** — never re-seed fields from the template. See the
  2026-07-16 update note in `microscopy_gui_filters_gaps_handoff.md`.
- **WYSIWYG / override semantics (fixed 2026-07-17).** A recipe must ingest what
  it displays. Don't let any new refresh path write into the override dict.
  Background: `microscopy_gui_override_semantics_review.md`.
- **Filter is narrow-only.** `runnerFilter()` `app.js:398-408` — the effective
  (template+recipe) filter wins on key collision; the runner can never widen it.
- **`runnerFilterUI.clear()` on recipe/instrument change** (`app.js:259`) — added
  conditions must not carry across recipes.
- `config_builder` locks `copy_strategy` / `acquisition_layout`. Untouched here.

---

## Scope, and what this branch is *not*

UI-only, inside `tools/operator/gui/` (+ possibly a new shared static JS file).
**No** changes to the ingest pipeline, resolver, registry, or config merge. No
**doc-governance integrity mirror** is implicated (06↔resolver/registry,
08↔sidecar, 09↔`EXPOSED_FIELDS`, 10↔templates) — none of them describe the GUI's
button layout. If operator-visible wording changes, update the help pages / FAQ
listed above and add a `CHANGELOG.md` row (append at the top; never rewrite a row).

---

## Running it in development

```powershell
pip install flask                       # only extra dep beyond the pipeline
$env:GJESUS3_ROOT = "J:\gjesus3-data"   # or set it in the RDM-System box in the UI
python tools\operator\gui\app.py        # serves http://127.0.0.1:5000, opens a browser
```

`--host --port --no-browser --debug`. The MRI page is `/mri` on the same server.
Point it at a **real** microscopy batch folder — the `discovered.*` grids only
populate from real files. `python tools\operator\test_value_fields.py` should stay
green (it guards the shared value-field catalogue).

### Test checklist

**A · browse order**
1. Browse… → a folder with many date-named subfolders → toggle → order reverses,
   **folders stay above files**.
2. Navigate down two levels → the chosen order **persists**.
3. A folder with >3000 entries → reversed view shows the *true* last entries
   (not a reversed first-3000). The `…list truncated` note still appears.
4. Repeat 1–3 on **`/mri`** — same behaviour, same look.

**B · loading**
5. Runner: pick a recipe, Browse… a real batch folder → **without pressing
   anything else**, the filter dropdown has labels, palettes are populated, and
   examples resolve.
6. Press **Preview** → table renders **and** nothing is left stale.
7. Use a recipe that leaves **no gaps** (so `#r-gaps` is hidden) → the filter can
   still be populated.
8. Switch recipe, then instrument → added filter rows clear; no stale labels from
   the previous folder linger.
9. Builder: pick an example folder → grid, palette, filter dropdown and examples
   all populate; "Preview example" leaves nothing stale; a **fresh builder is
   still blank** (no template defaults auto-applied).
10. Dry-run a small real batch on both pages — confirm nothing in the ingest path
    changed behaviour.

---

## Building the `.exe` (this box can do it — sessions have before)

PyInstaller works here (last verified builds: 2026-07-17 and 2026-07-20).
Full reference: `tools/operator/gui/README.md` §"Freeze to a single `.exe`".

```powershell
pip install flask paramiko pyinstaller czifile tifffile numpy pyyaml
pyinstaller --workpath D:\_build --distpath D:\_dist tools\operator\gui\gjesus3_ingest.spec
# -> D:\_dist\gjesus3_ingest.exe   (single self-extracting file, ~95 MB)
```

> **⚠️ Build OUTSIDE OneDrive — non-negotiable.** OneDrive locks PyInstaller's
> artifacts mid-build (`PermissionError` on `PYZ-00.pyz`). Always pass
> `--workpath`/`--distpath` to a non-synced location. Reading the spec from the
> repo is fine; only the write-heavy `build/` + `dist/` must be elsewhere.

New/renamed **static files must be added to the spec** (`gjesus3_ingest.spec`) or
they won't be in the bundle — this exact class of omission is what made the frozen
exe crash in July. If you factor the browser into `static/folder_browser.js`,
**check how `static/` is bundled** and verify by running the frozen exe, not just
`python app.py`. Freeze bugs do not reproduce in source mode.

### Deploying to production — **ask Ryan first**

Live location: `\\GJESUS3\gjesus3\gjesus3-data\tools\gjesus3_ingest.exe`.
Building is free; **replacing the production exe is an outward-facing change —
get explicit go-ahead.** The established procedure (2026-07-20, worked around a
transient SMB lock) is:

1. Back up the current exe **off-NAS** and verify the copy byte-for-byte.
2. Copy the new build up as `gjesus3_ingest.exe.new`, then **atomically rename** —
   never overwrite in place, so the tools dir is never without a working exe.
3. Checksum-verify the deployed file against the local build.
4. Erase the temp build dir.
5. Validate **through the deployed exe** with a real dry-run on both pages.

---

## Landing it

- **Commit freely on this branch** (repo rule); **never `git push`** without
  explicit permission. Stage specific files — **no `git add -A`**, and never stage
  `contacts.xlsx` or other binaries.
- Other sessions own the other worktrees under `gjesus3-dev\` — run
  `git worktree list` before touching anything there, and never remove one.
- On landing: add a `CHANGELOG.md` row, and **delete this handoff file** — the
  precedent (2026-07-17, 2026-07-20) is that temporary handoffs are dropped when
  the branch merges.

## Background reading (all on `main`)

| File | Why |
|---|---|
| `tools/operator/gui/README.md` | Architecture, endpoint map, freeze instructions |
| `tools/operator/gui/microscopy_gui_filters_gaps_handoff.md` | Prior fix to *this same* filter/labels area — read the 2026-07-16 update note |
| `tools/operator/gui/microscopy_gui_override_semantics_review.md` | Why the builder writes structural keys explicitly; the WYSIWYG contract |
| `tools/operator/value_fields.py` | Single source of truth for the builder/runner value fields |
| `tools/operator/README.md` · `tools/OPERATOR_FAQ.md` | Operator-facing wording that must stay in sync |
| `CHANGELOG.md` (2026-07-17, 2026-07-20) | The two most recent GUI ship+deploy cycles, incl. the deploy dance |
