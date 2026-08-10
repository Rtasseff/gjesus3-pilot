# Ingest GUI (`gjesus3_ingest.exe`) — microscopy + MRI

*Last Updated: 2026-08-10*

A local Flask web-app that lets an operator run the validated ingest pipeline
from the browser — no hand-written YAML. It is a **thin front-end** over the
shared operator core
(`tools/operator/{templates,config_builder,scope,preview,runner,env}.py`) and
reuses the exact pipeline the data office uses (`ingest.*` + `ingest_raw`). The
frozen Windows build, **`gjesus3_ingest.exe`**, serves **two pages**: microscopy
(ZWSI / CELL / LSM9, the default `/`) and MRI (Bruker ParaVision, `/mri`).

Phase 4 of [`tasks/archive/operator_ingest_tooling_plan.md`](../../../tasks/archive/operator_ingest_tooling_plan.md).

> **Operator-facing help:** the click-by-click usage lives in
> [`tools/operator/README.md`](../README.md); plain-language troubleshooting is in
> [`tools/OPERATOR_FAQ.md`](../../OPERATOR_FAQ.md). This page is the developer /
> data-office reference (architecture, freezing, the core endpoint map).

## Two verbs

Everything an operator presses is one of two things, and both pages use the
same word for each (2026-08-10 — before that there were five differently-worded
buttons for what is really these two actions, and operators couldn't tell them
apart):

- **Read folder** — read the source/example folder's `discovered.*` metadata
  labels and refresh EVERY surface that depends on them: both chip palettes,
  the filter dropdown, and the live "→ example" lines. One function,
  `loadFromFolder()` (runner) / `refreshGrid()` (builder), one
  `POST /api/discovered`. **It also runs on its own** when a folder is picked or
  typed, so in the normal case nobody has to press it — the button is the retry.
  It reads discovered data only; it never seeds field values from the template.
- **Preview** — show the resulting read-only table. Preview *also* refreshes the
  label surfaces, from the `cases[].discovered` its own response already
  carries (no second call), so pressing it can never leave anything stale.

## Two paths

- **Run a recipe** (the common case): pick instrument → pick a saved recipe
  (from `tools/operator/recipes/`) → point at the day/batch folder (its labels
  load by themselves) → **Preview** (a read-only "what will happen" table:
  acq_id, project, link name, resolved registry row, *X new / Y
  already-ingested*, warnings) → **Ingest** with a live streaming log. A
  *Dry-run* checkbox (default on) writes nothing.
  - **Dry-run default (testing period).** Dry-run defaults **ON** so operators
    learn the tool with no risk of an accidental write; a high-contrast banner
    shows while it is on, and a dry run ends with a clear "NOTHING was written"
    summary. **Once the testing period is over, flip the default to OFF** —
    remove `checked` from `#r-dry` in `templates/index.html` (the
    `TODO(dry-run-default)` marker flags the exact spot).
  - **Researcher field** — a text box → `registry.researcher` (the person who set
    up the experiment; renamed from `operator` 2026-06-09, 06_REGISTRIES §2.3a-bis).
    Blank = the template default (cells resolve it from `discovered.researcher`;
    AxioScan has only a placeholder, so set it). The **operator** (the tech who
    ran the scope) comes from the filename and is sidecar-only.
  - **Study metadata panel** — shown when the instrument's template carries a
    `condition:` block, gated on the `condition` field of `GET /api/template`.
    All microscopy templates now carry one (AxioScan tissue + the Cell Observer /
    LSM 900 cell modes — cells gained `condition:` 2026-06-09). Lets the operator
    set `condition.is_control` (control/case/skip) and, for a case,
    `condition.disease_model` / `disease_state` — typed or mapped from a CZI
    `discovered.*` field via token chips (reusing `POST /api/discovered`). The
    values are added to the override dict as `condition.*` and applied to every
    acquisition in the run (the GUI equivalent of `ni/mri-ingest --is-control`
    etc.). `anatomy.is_whole_body` is intentionally not offered — in-vivo only.
- **Build a recipe** (define a new convention): edit the parse rules
  (positional `separator` + ordered fields, or `regex` + source; plus
  `path_parse.levels` + `filter`) and watch a live `discovered.*` grid over the
  first real files; map `registry.*` / `link_filename` / `project_name` /
  `auto_create_project` via clickable `discovered.*` token chips, each field
  showing a live resolved example (unresolved `${…}` flag red); **Save recipe**
  to `tools/operator/recipes/`.

## Run (development — Python, no freeze)

```sh
pip install flask                 # the only extra dep beyond the pipeline's
# Tell the app where the NAS is (or set it in the NAS-root box in the UI):
#   PowerShell:  $env:GJESUS3_ROOT = "J:\gjesus3-data"
#   WSL/Linux:   export GJESUS3_ROOT=/mnt/gjesus3
python tools/operator/gui/app.py          # opens http://127.0.0.1:5000
```

Flags: `--host`, `--port`, `--no-browser`, `--debug`.

The pipeline's `.czi` metadata extraction also needs `czifile tifffile numpy`
(already in `tools/requirements.txt`); they are only exercised at *ingest* time,
not at preview.

The chosen NAS root persists in `%LOCALAPPDATA%\gjesus3-operator\nas_root.txt`
(Windows) / `$XDG_STATE_HOME` / `~` elsewhere.

## Freeze to a single `.exe` (PyInstaller)

The operator machine runs the `.exe` only (no Python/admin install). ONE exe
serves both pages — ship two shortcuts: `gjesus3_ingest.exe` (microscopy `/`) and
`gjesus3_ingest.exe --mri` (the MRI page `/mri`).

```sh
pip install flask paramiko pyinstaller czifile tifffile numpy pyyaml
# Build OUTSIDE OneDrive — see the warning below.
pyinstaller --workpath D:/_build --distpath D:/_dist tools/operator/gui/gjesus3_ingest.spec
# -> D:/_dist/gjesus3_ingest.exe   (single self-extracting file, ~95 MB)
```

The spec defaults to `ONEFILE = True` — one self-extracting `gjesus3_ingest.exe`,
chosen so the data office can drop a single file onto the NAS
(`...\tools\gjesus3_ingest.exe`) and run it in place. (Set `ONEFILE = False` in
the spec for the faster-starting one-folder build, where operators copy the whole
folder locally.) The deployed production exe (NAS, 2026-06-24) is the ~95 MB
single-file build.

> **⚠️ Build OUTSIDE OneDrive.** This repo lives under a OneDrive-synced folder,
> and OneDrive locks PyInstaller's build artifacts mid-build (`PermissionError`
> on `PYZ-00.pyz`). Always pass `--workpath`/`--distpath` to a non-synced
> location (e.g. `D:/`). The spec is read from the repo (fine); only the
> write-heavy `build/`+`dist/` must be elsewhere.

Smoke-tested 2026-06-24 (PyInstaller 6.18, py3.13): both pages render, static
assets serve, **paramiko is bundled and functions at runtime** (a live read-only
SFTP listing of 1083 studies through the frozen exe), and `~/.ssh/gjesus3_mri.cred`
resolves.

For the **MRI page**, the bundle also carries `paramiko` (lazy-imported → added as
a hidden import) and `tools/ftp_mirror.py` (loaded by path). The MRI page also
needs `~/.ssh/gjesus3_mri.cred` on the operator's machine to reach the scanner.

The spec bundles the per-instrument templates to
`<bundle>/tools/templates/instruments/` and the seed recipes to
`<bundle>/tools/operator/recipes/` — exactly the `sys._MEIPASS`-aware locations
the core's `templates.template_path()` and the GUI's `recipes_dir()` look in
first. Verify the frozen exe by previewing **and** dry-run-ingesting a real
`.czi` batch (the dry-run exercises `czifile`/`numpy`/`tifffile`).

> **Built & verified 2026-06-11 (Python 3.13, Windows, PyInstaller 6.18).** The
> freeze runs clean and the frozen exe launches, serves the UI (dry-run ON by
> default, banner shown), and loads the CELL/LSM9 seed recipes from the bundle.
>
> **Frozen-path fix that was required:** in the bundle `app.py.__file__` points
> at the exe dir, not `tools/operator/gui/`, so the source-relative derivation of
> `_PKG_DIR`/`_GUI_DIR` looked for `_loader.py` (and Flask's templates/static)
> beside the exe and crashed. `app.py` now derives those dirs from
> `sys._MEIPASS` when `sys.frozen` is set, and Flask is given explicit
> `template_folder`/`static_folder`. Source-mode runs are unchanged.
>
> **Still pending a real sample:** the end-to-end `.czi` read in the frozen
> build (the actual `czifile`/`tifffile`/`numpy` extraction) was not exercised —
> it needs a representative `.czi` on the build machine. Run a dry-run preview +
> ingest of one `.czi` batch on the microscopy machine to close that out.
>
> Build note: this repo lives under OneDrive; building into the repo `dist/` can
> hit sync locks on rebuild. Build into a non-OneDrive `--distpath` (e.g. a temp
> dir) if cleanup fails. `dist/` and `build/` are git-ignored.

## How it talks to the core

| endpoint | core call | writes? |
|---|---|---|
| `GET /api/recipes` | reads `recipes_dir()` | no |
| `GET /api/template` | `templates.load_template` (returns `auto_discover`/`registry`/`link_filename`/`ingest` defaults + the `condition` block if any — the runner gates the Study-metadata panel on it) | no |
| `GET/POST /api/nas_root` | `env.is_valid_nas_root` | NAS-root state file only |
| `POST /api/preview` | `scope.resolve_scope` → `config_builder.build_config` → `preview.preview_batch` | no |
| `POST /api/discovered` | same, returns the `discovered.*` grid (+ `blocking_errors`, so an auto-read that finds nothing can say why) | no |
| `POST /api/listdir` | `os.scandir` for the folder-browser modal; `desc` flips the name order **before** the 3000-entry cap | no |
| `POST /api/save_recipe` | writes a YAML recipe into `recipes_dir()`; refuses an existing filename with **409 + `{exists, file}`** unless `overwrite: true` | recipe file only |
| `POST /api/ingest` | `runner.run` (SSE-streamed log) | **yes — the real ingest** |

The operator's folder pick (`scope.resolve_scope`) always sets
`auto_discover.staging_dir`; the recipe/builder overrides supply everything
else. `copy_strategy` / `acquisition_layout` stay template-locked
(`config_builder` rejects any attempt to override them).

## Shared front-end files (`static/`)

Both pages are plain classic scripts sharing one global scope, so a shared file
must expose itself on `window` and declare nothing else globally — `app.js` and
`mri.js` already define `$`, `$$`, `esc`, `postJSON` there, and a redeclaration
is a page-killing `SyntaxError`.

| file | exposes | loaded by |
|---|---|---|
| `tokenfield.js` | `TokenField`, `renderPalette`, `paletteEntries`, `tfHumanizeRef` | both |
| `completion_modal.js` | `showCompletionModal` | both |
| `folder_browser.js` | `browseInto` | both |
| `app.js` / `mri.js` | the page itself | one each |

`folder_browser.js` is the Browse… modal, factored out of the two near-verbatim
copies in `app.js`/`mri.js` (2026-08-10). Its **markup** is still duplicated in
`templates/index.html` and `templates/mri.html` — same ids in both; change one,
change the other. Two behaviours worth knowing:

- **Sort.** The `Name ▲/▼` header re-fetches with `desc` rather than reversing
  the received list, because `/api/listdir` truncates at 3000 entries *after* it
  sorts — a client-side reverse would silently show the wrong end of a large
  folder.
- **Where it opens.** In order: the target box's own value → the folder that
  button was last left in → the home folder. The last folder is remembered **per
  target** (`{inputId: path}`), because one modal serves the source folder, the
  RDM System root, the recipes folder and the MRI staging folder. A remembered
  folder that no longer resolves falls back to home **silently** and is
  forgotten (`fbLoad(path, {remembered: true})`) — a stale memory is not the
  operator's mistake; a path they *typed* still errors normally.

Both preferences live in `localStorage` (`gj3.folderBrowser.sortDesc`,
`gj3.folderBrowser.lastDir`), every access wrapped — a browser that blocks it
just loses the memory, it never breaks the browser.

### `postJSON` carries the refusal, not only its text

`postJSON()` (both copies) attaches `status` and the parsed body to the thrown
`Error`. Some refusals are things the caller must **act on**, not merely print:
`/api/save_recipe` answers a name collision with `409 + {exists, file}` so the
save handler can offer to replace. Keep the two copies identical even though the
MRI page has no endpoint that needs it — the point is that neither becomes the
odd one out. Every existing `catch (e) { … e.message }` is unaffected.

**Replacing a recipe** (`#b-save`): first attempt without `overwrite`; on
`409 + exists`, a `window.confirm` naming **the file** (not the typed name —
`"Study A"` and `"Study/A"` both sanitise to `study_a.yaml`), then the identical
body resent with `overwrite: true`, reported as *Replaced* rather than *Saved*.
The confirm says the replaced version is **not kept** (a deliberate 2026-08-10
call — no `.bak`), and warns that the recipe is **shared on the RDM System** when
`recipes_dir()` is the default; if the operator has pointed it somewhere else it
names that folder instead.

The spec bundles `static/` as a whole directory, so a new file here needs no
`gjesus3_ingest.spec` edit — but verify through the frozen exe anyway.

## Import-collision note

The package directory is named `operator`, which collides with the stdlib
`operator` module — so this app loads the core through
`tools/operator/_loader.py` (alias `gj_op_core`), never `import operator`. See
[`../IMPORT_CONTRACT.md`](../IMPORT_CONTRACT.md).
