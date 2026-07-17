# Handoff — operator GUI polish (metadata tokens · drop "NAS" · completion popup)

**Branch:** `feat/gui-operator-polish` · **Worktree:** `…/projects/gjesus3-dev/gui-operator-polish`
**Base:** `main` @ `7f0eba2` (includes both 2026-07-17 GUI fixes: frozen-exe resources + recipe-override WYSIWYG).
**Author of handoff:** prior session (GJ3 triage of the 2026-07-17 microscopy operator test).
**Status:** not started. This doc is self-contained — you need no prior context.

This branch is one of two spun off from the same operator test. The other is
`refactor/project-naming` (renames "project hint" → "project name" and normalises
project folders). **They are sequenced: this branch (G) lands first; that branch (P)
rebases onto `main` after G merges.** You do not need to coordinate live — just land
G cleanly. See §6.

---

## 0 · TL;DR — three independent GUI fixes, do in any order

1. **Metadata-token palette is missing fields (issue 2).** The runner's "Show
   metadata labels" palette shows only the filename-parsed `discovered.*` chunks. The
   ~12 other fields the resolver *does* support (`original_name`, `instrument`,
   `operator`, …) are never offered as draggable chips — even though they resolve
   fine at ingest. Expose the full documented resolver context in **both** the builder
   and runner palettes. (§2)
2. **Drop the word "NAS" from operator-visible text (issue 3).** Replace with
   **"RDM System"**. Operators don't know what a NAS is. Cosmetic; ~35 visible
   strings. Leave internal identifiers (`nas_root`, `/api/nas_root`, …) alone. Add a
   one-line glossary definition. (§3)
3. **Add a completion popup (issue 4).** On a real (non-dry-run) ingest completion,
   show a modal with a professional, lightly-positive tone and the run summary. Today
   it's only a small line at the bottom of the page that operators miss. Both the
   microscopy (`/`) and MRI (`/mri`) pages. (§4)

Then **rebuild + redeploy the exe and smoke-test through the frozen build** (§5).

**Out of scope — do NOT touch here:** the dedup key (deferred to `BACKLOG.md`, section
"Dedup identity — content-anchored…"); renaming `project_hint` (that's branch P).
You *may* add a `${project_hint}` chip in §2 — that's expected; P will rename it later.

---

## 1 · Where the GUI lives

One Flask app, two pages, one exe:
- Backend: `tools/operator/gui/app.py`
- Microscopy page: `tools/operator/gui/templates/index.html` + `static/app.js`
- MRI page: `tools/operator/gui/templates/mri.html` + `static/mri.js`
- Shared CSS: `tools/operator/gui/static/style.css`
- Help pages: `tools/operator/gui/static/help/{microscopy_guide,mri_guide}.html`
- Field catalogue (shared by both front-ends): `tools/operator/value_fields.py`
- PyInstaller spec: `tools/operator/gui/gjesus3_ingest.spec`

Run from source while developing (no exe needed):
```
pip install flask paramiko pyyaml czifile tifffile numpy
python tools/operator/gui/app.py          # opens http://127.0.0.1:5000/  (microscopy)
python tools/operator/gui/app.py --mri    # opens /mri
```
You need a valid NAS root (a folder with a `registries/` subfolder) set in the UI —
point it at `J:\gjesus3-data` (the live share) for realistic previews, or make a
throwaway one with `tools/operator/make_test_nas.py`.

---

## 2 · Issue 2 — expose the full metadata-token palette

### What the operator saw
Loading the metadata labels in the microscopy GUI, `original name` and `instrument`
did **not** appear as draggable tokens — but they exist and work (Load-template-defaults
puts them into the "Project link name" field and they resolve correctly at ingest).
The operator's question: what is the criterion for a field to appear as a token, and
is the problem bigger than these two? **It is bigger.**

### How it works today (verified)
- The rows in the GUI's **"Set the values to record"** section come from
  `value_fields.py::VALUE_FIELDS` (researcher, operator, sample_id, sample_type,
  acquisition_datetime, project_hint, session_id, notes, link_filename). Each is a
  `kind:"token"` TokenField — free text **plus draggable metadata-label chips**.
- The **chips** you can drag in come from `paletteEntries(...)` in `static/app.js`.
  There are three palettes, and they are fed *different* sources:
  - **Builder** (`#b-palette`, `app.js:1057-1058`):
    `paletteEntries(builderKeys, ["${acq_id}", "${acq_date}", "${original_name}"])`
    → the `discovered.*` keys **plus three hard-coded extras**.
  - **Runner "Show metadata labels"** (`#r-meta-chips`, `app.js:~452`):
    `paletteEntries(data.keys || [])` → `discovered.*` keys **only, no extras**.
  - **Runner gaps** (`#r-gaps-palette`, `app.js:~323`):
    `paletteEntries(runnerKeys)` → `discovered.*` only, no extras.
- `discovered.*` = fields parsed from the filename chunks (+ any embedded-metadata
  extractor output), returned by `POST /api/discovered` (`app.py:724`).

So the **criterion today** is: *a token chip appears only if it's a `discovered.*`
field* — except the builder, which also hard-codes `acq_id`/`acq_date`/`original_name`.
The operator was in the **runner**, which offers no extras at all — hence no
`original_name`, and no `instrument` anywhere.

### What the resolver actually supports (the correct source of truth)
`tools/ingest/resolver.py::resolve_link_filename` (lines ~232-250) resolves `${…}`
references against this context:
- every `discovered.<key>`
- the fixed set: `instrument`, `instrument_model`, `operator`, `data_source`,
  `sample_id`, `sample_type`, `session_id`, `acquisition_datetime`, `project_hint`,
  `original_name`, `data_ecosystem`, `notes`
- `acq_id`, `acq_date`

Every one of those is a legal token, but only `discovered.*` (+3 in the builder) are
offered. That's the gap.

### The fix
Expose the **full documented resolver context** as palette chips in **both** the
builder and the runner palettes. Concretely:
- Define the fixed-extras list **once** so it can't drift from the resolver. Best:
  add a small endpoint (e.g. `GET /api/link_tokens`) or a constant sourced from a
  single place, listing the fixed resolver fields above. A pragmatic option is to
  export the list from `resolver.py` (the fields it iterates in `resolve_link_filename`)
  so the palette and the resolver are guaranteed consistent — today they're two
  hand-maintained lists that already disagree.
- Feed that list as the `extras` argument to **all three** `paletteEntries(...)`
  calls (builder + both runner palettes), unioned with the per-file `discovered.*`
  keys. Order suggestion: `discovered.*` first (positional, read left-to-right), then
  the fixed fields.
- At minimum `original_name` and `instrument` must appear in the runner — but do the
  whole set; the operator explicitly asked you to.
- **Check the MRI page too** (`static/mri.js`): the MRI link-name field has its own
  palette/token handling (see the collision logic around `mri.js:238`). Apply the
  same fix so the MRI "Project link name" offers the full set.

### Watch
- `${project_hint}` will be in this set. Include it — branch P renames it to
  `project_name` later and will catch the new reference. Don't pre-rename it here.
- Some fixed fields can resolve to empty for a given file (e.g. `session_id`); that's
  fine — the resolver already substitutes empty quietly. Don't filter them out.
- Confirm the chip's inserted text matches what the resolver expects: `${original_name}`,
  `${instrument}`, and `${discovered.foo}` (dotted) for discovered fields. `paletteEntries`
  already builds `${discovered.x}` for bare keys — make sure the fixed fields insert as
  `${instrument}` (no `discovered.` prefix), matching `resolve_link_filename`'s context.

### Verify
From source, load a real AxioScan staging folder, open the runner's "Show metadata
labels", confirm `original_name`, `instrument`, `operator`, `sample_id`, etc. all
appear and drag in; run a dry-run and confirm the resolved link name is correct.

---

## 3 · Issue 3 — replace operator-visible "NAS" with "RDM System"

Operators don't know what "NAS" means; it reads as meaningless jargon. Use
**"RDM System"** (the data office's choice). On first mention on a page, consider
"the RDM System (gjesus3 storage)"; thereafter "RDM System" alone.

### Rule (important)
Change **operator-visible text only**. Do **not** rename internal identifiers — they're
invisible to operators and renaming them risks breakage for zero UX gain:
- leave `nas_root`, `/api/nas_root`, `is_valid_nas_root`, `validate_nas_root`,
  `nas_root.txt`, the `nasInput`/`nasStatus` JS ids, function names, and code comments.
- change only: `<label>`/visible copy in templates, user-facing status strings in
  `app.js`/`mri.js`, the help pages, and the two user-facing error strings in `app.py`.

### Find them
```
git grep -n '\bNAS\b' tools/operator/gui/templates tools/operator/gui/static
git grep -n '\bNAS\b' tools/operator/gui/app.py     # keep comments; change only jsonify() error strings
```
Known operator-visible hits (from the triage grep; verify against current code):
- `templates/index.html`: lines ~15, 23, 24, 44, 80, 130 (labels, dry-run warning,
  the recipes-dir placeholder `<NAS>\recipes`, the "Set the folder + NAS root" copy).
- `templates/mri.html`: lines ~15, 28, 63 (destination label, dry-run warning, staging note).
- `static/app.js`: lines ~81 (placeholder), 653, 660, 683 (dry-run/live/status messages).
- `static/mri.js`: lines ~44 ("not a NAS root"), 141, 238, 427, 431, 449, 533, 538.
- `static/help/mri_guide.html`: ~52, 109 · `static/help/microscopy_guide.html`: ~90.
- `app.py`: the two `jsonify({"error": "…NAS…"})` strings at ~744 and ~1325 (user-facing).
- `tools/operator/gui/README.md`: operator-facing mentions — optional, low priority
  (it's a dev/operator doc, not the UI).

### Glossary definition (do this here so the term is documented)
Add to `GLOSSARY.md` (repo root): **RDM System** — the operator-facing name for the
gjesus3 storage; concretely the QNAP NAS "gjesus3" (`\\GJESUS3\gjesus3\gjesus3-data`,
mapped `J:\gjesus3-data`). Cross-reference the existing NAS description in
`mfb-rdm-docs/02_INFRASTRUCTURE.md`.

### Watch
Issue 4 rewrites the exact completion-message lines that contain "NAS" (`app.js:653/660`,
`mri.js:427/431`). Do issues 3 and 4 together, or do 4 first, so you don't edit those
strings twice / conflict with yourself.

---

## 4 · Issue 4 — completion popup on real ingest

### Today
On completion the code just sets `resEl.innerHTML` to a one-line message at the bottom
of the page (`app.js:653` dry-run / `:660` live; `mri.js:427` dry-run / `:431` live).
Operators miss it.

### Want
A **modal popup** shown on a real (non-dry-run) successful/finished ingest, on both
pages. Professional but a little warm (this is a research institute — think a clean
check-mark and a clear headline, not confetti). Include the run summary.

### Data you already have
The ingest streams over SSE; the final `done` event (`app.py:882-929`) carries:
```json
{ "results": [ {"acq_id": "ACQ-…", "ok": true}, … ], "ok": <int>, "total": <int>, "dry_run": <bool> }
```
So the modal can show: **N of M acquisitions ingested**, any failures (`ok=false`
rows), the destination (RDM System root), and the project/recipe used. The front-ends
already parse this event to render the bottom-line message — reuse that handler and
route it into the modal when `!dry_run`.

### Notes
- Keep the small bottom-line message for dry-runs (or show a lighter modal) — the big
  celebratory modal is for **real** completions.
- Make it dismissible (button + `Esc`), move focus to it (accessibility), and don't
  block the log the operator may want to scroll.
- Style it in `static/style.css`; reuse any existing modal pattern in the app
  (the folder-browser uses a modal — `/api/listdir` + a modal in `app.js`; mirror it).
- **Optional (ties to the dedup backlog item):** if you also surface the
  already-ingested/skipped count through the `done` event (a small backend touch in
  the worker/`runner.run`), show "N skipped — already ingested" in the modal. The
  preview already computes `n_already_ingested` via `/api/discovered`; the commit path
  doesn't currently report skips. Nice-to-have, not required for issue 4.

---

## 5 · Build, deploy, verify

No spec change is needed — all assets these fixes touch are already bundled (the
2026-07-17 frozen-exe fix added the templates/reference bundling). After all three
fixes land and merge to `main`:

```
pip install flask paramiko pyinstaller czifile tifffile numpy pyyaml
pyinstaller tools/operator/gui/gjesus3_ingest.spec      # -> dist/gjesus3_ingest.exe
```
Then follow the established 2026-07-17 production-deploy pattern (see
`memory/gui_frozen_exe_readme_bug.md` / the CHANGELOG 2026-07-17 entry):
1. **Back up** the current `\\gjesus3\…\tools\gjesus3_ingest.exe` off-NAS **and back
   up the registry CSVs** off-NAS first.
2. Copy the new exe over the deployed one; checksum-verify the copy.
3. **Smoke-test through the frozen exe** (unit tests can't exercise the packaged
   build): a small real AxioScan ingest — confirm the tokens appear, no "NAS" text is
   visible, the completion modal shows, README + anatomy still write (regression guard
   from the last fix). Remove the smoke-test acqs afterward and confirm the registry
   count returns to baseline.

**Rebuild coordination with P:** branch P also changes the GUI and needs its own
rebuild+redeploy. Options: (a) rebuild+deploy G now so operators get the polish, then
rebuild again after P; or (b) if P lands soon, batch one rebuild after both. Data
office's call — flag it, don't decide unilaterally.

---

## 6 · Coordination with branch P (project-naming)

- P renames `project_hint` → `project name` across code, docs, GUI, configs, and does
  a live project-folder migration. It touches many of the same files you do
  (`app.js`, `app.py`, `value_fields.py`).
- **The plan:** G lands on `main` first. P's first action is to rebase/merge the
  latest `main` (with G) and then run its rename sweep, so it catches anything G added
  (including a `${project_hint}` token chip from §2).
- **Your only obligation:** land G as a clean merge to `main`. Don't rename
  `project_hint` here; don't start the folder migration.

---

## 7 · File / line reference

| Concern | File | Anchor |
|---|---|---|
| Field catalogue (the "values to record" rows) | `tools/operator/value_fields.py` | `VALUE_FIELDS` 47-57 |
| Builder palette (3 extras) | `tools/operator/gui/static/app.js` | ~1057-1058 |
| Runner "Show metadata labels" palette (no extras) | `static/app.js` | ~452 |
| Runner gaps palette (no extras) | `static/app.js` | ~323 |
| `paletteEntries()` helper | `static/app.js` | search `function paletteEntries` |
| Resolver context = source of truth for tokens | `tools/ingest/resolver.py` | `resolve_link_filename` ~232-250 |
| `/api/discovered` (discovered.* + n_already_ingested) | `tools/operator/gui/app.py` | 724 |
| Microscopy completion message | `static/app.js` | 653 (dry) / 660 (live) |
| MRI completion message | `static/mri.js` | 427 (dry) / 431 (live) |
| SSE `done` event shape | `app.py` | 921-929 |
| MRI link-name palette / collision | `static/mri.js` | ~238 |
| "NAS" visible strings | templates + static + help + app.py error strings | `git grep -n '\bNAS\b'` |
| Modal pattern to mirror | `static/app.js` (folder browser) + `static/style.css` | search `listdir` |

## 8 · Definition of done
- [ ] Runner + builder palettes offer the full resolver token set (incl. `original_name`,
      `instrument`); MRI page too. Sourced from one list, not two hand-kept ones.
- [ ] No operator-visible "NAS" remains; "RDM System" used; `GLOSSARY.md` defines it;
      internal identifiers untouched.
- [ ] Real-ingest completion shows a clear modal (both pages), dismissible + accessible.
- [ ] Exe rebuilt, smoke-tested through the frozen build, deployed per the 2026-07-17
      backup-first pattern; smoke-test acqs removed; registry back to baseline.
- [ ] Merged to `main` cleanly; CHANGELOG entry added; `tasks/STATUS.md` noted.
