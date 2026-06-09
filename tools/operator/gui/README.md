# Microscopy operator ingest GUI

A local Flask web-app that lets a microscopy operator (ZWSI / CELL / LSM9) run
the validated ingest pipeline from the browser — no hand-written YAML. It is a
**thin front-end** over the shared operator core
(`tools/operator/{templates,config_builder,scope,preview,runner,env}.py`) and
reuses the exact pipeline the data office uses (`ingest.*` + `ingest_raw`).

Phase 4 of [`tasks/operator_ingest_tooling_plan.md`](../../../tasks/operator_ingest_tooling_plan.md).

## Two paths

- **Run a recipe** (the common case): pick instrument → pick a saved recipe
  (from `tools/operator/recipes/`) → point at the day/batch folder → **Preview**
  (a read-only "what will happen" table: acq_id, project, link name, resolved
  registry row, *X new / Y already-ingested*, warnings) → **Ingest** with a live
  streaming log. A *Dry-run* checkbox (default on) writes nothing.
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
  first real files; map `registry.*` / `link_filename` / `project_hint` /
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

The Windows microscopy machine runs the `.exe` only (no Python/admin install).

```sh
pip install flask pyinstaller czifile tifffile numpy pyyaml
pyinstaller tools/operator/gui/microscopy_ingest.spec
# -> dist/microscopy_ingest/microscopy_ingest.exe
```

The spec bundles the per-instrument templates to
`<bundle>/tools/templates/instruments/` and the seed recipes to
`<bundle>/tools/operator/recipes/` — exactly the `sys._MEIPASS`-aware locations
the core's `templates.template_path()` and the GUI's `recipes_dir()` look in
first. Verify the frozen exe by previewing **and** dry-run-ingesting a real
`.czi` batch (the dry-run exercises `czifile`/`numpy`/`tifffile`).

> The freeze itself is a documented build step and is **not** executed by the
> build pass that created this GUI; only the Python-run path is verified.

## How it talks to the core

| endpoint | core call | writes? |
|---|---|---|
| `GET /api/recipes` | reads `recipes_dir()` | no |
| `GET /api/template` | `templates.load_template` (returns `auto_discover`/`registry`/`link_filename`/`ingest` defaults + the `condition` block if any — the runner gates the Study-metadata panel on it) | no |
| `GET/POST /api/nas_root` | `env.is_valid_nas_root` | NAS-root state file only |
| `POST /api/preview` | `scope.resolve_scope` → `config_builder.build_config` → `preview.preview_batch` | no |
| `POST /api/discovered` | same, returns the `discovered.*` grid | no |
| `POST /api/save_recipe` | writes a JSON recipe into `recipes_dir()` | recipe file only |
| `POST /api/ingest` | `runner.run` (SSE-streamed log) | **yes — the real ingest** |

The operator's folder pick (`scope.resolve_scope`) always sets
`auto_discover.staging_dir`; the recipe/builder overrides supply everything
else. `copy_strategy` / `acquisition_layout` stay template-locked
(`config_builder` rejects any attempt to override them).

## Import-collision note

The package directory is named `operator`, which collides with the stdlib
`operator` module — so this app loads the core through
`tools/operator/_loader.py` (alias `gj_op_core`), never `import operator`. See
[`../IMPORT_CONTRACT.md`](../IMPORT_CONTRACT.md).
