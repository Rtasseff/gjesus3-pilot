# Plan: Operator-facing ingest tools for the acquisition machines

> **Persisted into the repo 2026-06-03** from the plan-mode artifact
> (`.claude/plans/we-had-an-issue-shimmering-starlight.md`). This is Phase 0 of
> the plan itself ("persist into the repo, not left only in `.claude/plans/`
> where future plans overwrite it"), which had not been executed. **Status:
> design locked, build DEFERRED** until the metadata lane (Phase 3, now landed)
> settled. Spec authority for conventions stays in `mfb-rdm-docs/` + the
> per-instrument templates; this is the build plan for the operator front-ends.

## Context — why we're doing this

Today the ingest pipeline (`tools/ingest_raw.py` + per-instrument YAML configs) is run by the
data office (Ryan) from his workstation. The next milestone is to let **operators / users run
ingest themselves on the acquisition machines**, logged in with dedicated "operator" accounts
(the applied permission model already gives operators write-but-not-modify on `raw\` + Modify on
`registries\`). The experience must be **dead simple** — no hand-written YAML — and split by lane:

- **NI (Nuclear Imaging)** and **MRI (Bruker ParaVision)** — run by users, likely on **Linux**
  acquisition machines. NI is on the network with clear network drives; MRI may need an **FTP**
  pull from the console. These are the **most well-defined** instruments, so the front-end can be
  a **dead-simple script**: "point at the session folder" — the script already knows it's NI/MRI
  and the per-instrument template supplies everything else.
- **Microscopy** (AxioScan7 / Cell Observer / LSM900) — all **Windows**, needs a **GUI**. The
  naming conventions vary a lot per batch (e.g. the recent AxioScan 7-chunk-with-`<section>` case),
  so this lane needs a visual way to define where files are, how to filter, how to parse dir/file
  names into auto-discovered metadata, and how to build the project-link name, project name, and
  registry fields from those discovered values.

**Intended outcome:** operators ingest their own data correctly and reproducibly, reusing the exact
validated pipeline the data office uses — no reimplementation, no divergence.

### Decisions locked (from the user, 2026-06-03)
- **Microscopy GUI = hybrid "recipes + builder".** Data office pre-builds per-convention *recipes*
  (saved configs); operators usually just **pick a recipe → point at folder → preview → Ingest**. A
  *builder* mode (live `discovered.*` preview + token mapping) exists for defining a NEW convention.
- **Microscopy GUI stack = local Flask web-app opened in the browser, packaged as a single
  PyInstaller `.exe`** (no Python/admin install needed; richest live-preview/token UI).
- **Build sequencing starts with NI** (this plan is ordered NI-first).
- **This plan must be persisted into the repo** (durable + visible), not left only in
  `.claude/plans/` where future plans overwrite it. Build is **deferred** until the other in-flight
  work (metadata lane, possible overlaps) settles — see Phase 0.

### Key architectural facts (verified this session)
- The pipeline is **programmatically invokable** with an in-memory dict — no YAML-on-disk, no
  shell-out: `config.expand_batch(cfg, nas_root)` → cases; `ingest_raw.run_batch(cfg, nas_root,
  dry_run, nas_unc, delete_source)` → `[(acq_id, ok)]`; `ingest_raw.ingest_single(case, …)` for one.
- Hard-link project linking is **cross-platform** (`linker.create_hardlink` → `os.link`; Linux
  ext4/NAS mounts work). The only Windows-only code is the dead `create_lnk` (PowerShell) seam.
- **Preview gap (the central engineering task):** `expand_batch` resolves `discovered.*` + the
  `registry` row but **does NOT** compute `acq_id`, the canonical project, or the resolved
  `link_filename` — those happen mid-`ingest_single`, and `--dry-run` returns early (≈
  `ingest_raw.py:757`) before them. The shared core must replicate those three steps **read-only**
  to give a true "what will happen" preview. The pieces are pure/reusable:
  `acq_id.generate_acq_id(date_str, instrument, registry_path)`,
  `resolver.resolve_link_filename(template, case, acq_id, acq_date)`,
  `linker.resolve_project(projects_registry, hint)` / `lookup_project_folder(...)`.
- Reuse-ready helpers: `ftp_mirror.mirror(sftp, remote_root, local_root, …)` (runs against an
  already-opened paramiko SFTP connection; creds via `GJESUS3_FTP_*`),
  `ni_metadata.is_ni_acquisition(path)`, `config._is_paravision_exam(path)`,
  `filename_parser.parse/parse_regex`, `resolver.resolve_value`.
- The per-instrument templates already encode every locked convention:
  `tools/templates/instruments/{molecubes_ni,mri_bruker,axioscan7,cell_observer_cells,lsm900}.yaml`.
  The front-ends **load these as the source of truth** and apply a small override set — never duplicate.

---

## Architecture: one shared core, three thin front-ends

```
tools/operator/                     # NEW shared, GUI-agnostic, cross-platform core
  templates.py        # load baked-in per-instrument template dicts (repo + PyInstaller aware)
  config_builder.py   # template dict + whitelisted overrides -> in-memory config dict
  scope.py            # "point at folder" -> (staging_dir, pattern) auto-detect (single vs batch root)
  preview.py          # expand_batch + read-only acq_id/project/link resolution -> PreviewResult
  runner.py           # commit: wraps ingest_raw.run_batch; streams log to a callback
  env.py              # nas_root resolution + validate (mirrors ingest_raw.main) + ftp creds check
  ni_ingest.py        # NI Linux script (front-end #1)
  mri_ingest.py       # MRI Linux script (front-end #2)
  gui/                # Microscopy Flask app + static HTML/JS (front-end #3) + PyInstaller spec
  recipes/            # saved per-convention microscopy recipes (configs the GUI picks from)
```

Both the Linux scripts and the Windows GUI call the **same** `preview.preview_batch(cfg, nas_root)`
then `runner.run(cfg, nas_root)`. All platform-specific code lives in the front-ends; the core is
pure Python.

---

## Phase 0 — Persist this plan + scope guard (do first, on approval)
- Write this plan into the repo at **`tasks/operator_ingest_tooling_plan.md`** (durable, visible,
  not overwritten by `.claude/plans/`). Add a one-line pointer under `tasks/tasks.md` §3.1
  future-work and a `reference`-type memory note. **[DONE 2026-06-03 — this file.]**
- Because other sessions may touch shared docs, keep all build work in the **new `tools/operator/`
  tree** (zero overlap with the metadata lane's extractors/docs). Do code work on a dedicated branch.
- **Do not start building** until the user confirms the overlapping work has settled. *(The
  metadata lane — Phase 3 — landed 2026-06-03, so that overlap is now clear.)*

## Phase 1 — Shared core `tools/operator/` (unblocks everything)
- `templates.load_template(key)` / `template_path(key)` — resolve template path from repo root, and
  from `sys._MEIPASS` when frozen (PyInstaller); `config.load_config()` to dict.
- `config_builder.build_config(template, overrides)` — deep-copy template, apply a **whitelist** of
  overrides into the right nested keys (`auto_discover.staging_dir/pattern/filename_parse/path_parse/
  filter`, `registry.*` expressions, `link_filename`, `auto_create_project.*`, and the operator-safe
  `ingest.*`: `reconstructions`, `auto_regenerate_dicom`, `delete_source_after_ingest`,
  `auto_create_projects`). `copy_strategy`/`acquisition_layout` stay template-locked.
- `preview.preview_batch(cfg, nas_root) -> PreviewResult` — calls `expand_batch`, then per case
  builds `CasePreview{source, original_name, discovered, registry_resolved, acq_date,
  acq_id_preview (in-memory incrementing peek), project_preview (resolve or "will auto-create"),
  link_filename_preview, warnings}`. Aggregate `n_matched/n_skipped/n_new/blocking_errors`.
  Decide warning capture: **small refactor** of `config.expand_batch`/`resolver` to collect
  warnings into a returned list (preferred — we own the code), or stdout-scrape for v1.
- `runner.run(cfg, nas_root, dry_run=False, delete_source=False)` — wraps `ingest_raw.run_batch`;
  routes `ingest_raw.log` to a caller callback (progress UI). Stamps the template/recipe path so the
  registry `ingest_config` column stays meaningful.
- `env.resolve_nas_root()/validate_nas_root()` — mirror `ingest_raw.main` fail-fast (a real NAS root
  has a `registries/` subdir); `ftp_creds_present()`.
- **Verify** the core against existing `tools/configs/*.yaml`: feed template+overrides through
  `preview_batch` and diff the resolved rows against a real `ingest_raw --dry-run`.

## Phase 2 — NI operator script (FIRST front-end)
- `tools/operator/ni_ingest.py`: `ni-ingest /path/to/folder [--dry-run] [--go]`. Default = preview
  table (acq_id, sample_id, project, link name, n_files) + `Proceed? [y/N]`; `--go` skips prompt.
  Hardcodes instrument key `NI` → `molecubes_ni.yaml`.
- `scope.resolve_scope("NI", path)` handles **"point at one session" vs "batch root"**: if the folder
  is itself an NI acquisition (`ni_metadata.is_ni_acquisition` / archive-name regex), set
  `staging_dir=parent`, `pattern=<basename>`; if its children look like sessions, keep
  `staging_dir=folder`, `pattern="*/"`. Idempotent dedup makes re-pointing safe.
- **Archive mode works today** (validated). If pointed at a `.tgz`, optionally run
  `extract_ni_archives.py` first.
- **NI live mode is blocked on platform manager Unai** (live folder layout undocumented). Scaffold a
  detector branch: if the folder looks like a live (non-extracted) acquisition, print
  *"NI live mode not yet supported — pending Unai's folder-layout confirmation; use archive mode"*
  rather than guessing. When unblocked, the only new work is authoring `molecubes_ni_live.yaml`
  (a template) + one detector branch — the script/core are unchanged.

## Phase 3 — MRI operator script
- `tools/operator/mri_ingest.py`: `mri-ingest /path/to/study [--reconstructions all|3|1,3]
  [--model 7T|11.7T] [--dry-run] [--go] [--ftp-remote /path]`. Hardcodes `MRI` → `mri_bruker.yaml`.
- `scope.resolve_scope("MRI", path)` via `config._is_paravision_exam`: single exam → narrow glob;
  study folder → `*/`; batch root → `*/*` (template default). `reconstructions`/`model` are the only
  per-run knobs.
- **FTP**: default assumes an already-mounted/pulled local path (no FTP). With `--ftp-remote`, open a
  paramiko SFTP (creds from `GJESUS3_FTP_*`) and call `ftp_mirror.mirror(...)` into a local staging
  dir, then run the normal preview/commit. Fetch and ingest stay decoupled (as today).

## Phase 4 — Microscopy GUI (hybrid recipes + builder; Flask-local `.exe`)
- **Flask app on localhost**, opened in the default browser, packaged as one PyInstaller
  `microscopy_ingest.exe` (`--add-data` bundles `tools/templates/instruments/*.yaml` +
  `tools/operator/recipes/*`). `templates.template_path` must be `sys._MEIPASS`-aware. Verify the
  frozen exe reads a real `.czi` (czifile/numpy/tifffile bundled).
- **Recipe-runner path (the common case):** pick instrument → pick a saved **recipe** → OS
  folder-picker for `staging_dir` → `preview_batch` table (acq_id, project, link name, resolved
  registry row, "X new / Y already-ingested") → **Ingest** with a live streaming log.
- **Builder path (define a new convention):** screens that edit the override dict and re-run
  `preview_batch` live — (a) positional `separator`+ordered `fields` list (drag a `<section>` in) or
  `regex`+`source`, plus `path_parse.levels`/`filter`, with a **live discovered.\* grid** over the
  first N real files; (b) map `registry.*` + `link_filename` + `project_hint` + `auto_create_project`
  via **clickable `discovered.*` token chips** (`${discovered.x}`, `${acq_id}`, `${acq_date}`,
  `${original_name}`), each field showing a live resolved example; unresolved `${…}` flag red. On
  success, **save as a recipe** to `tools/operator/recipes/` (and optionally to `tools/configs/`).
- Same screens serve all three microscopy instruments via their different template defaults — no
  per-instrument GUI code.

## Cross-cutting
- **Packaging:** NI/MRI = `tools/operator/*.py` + tiny `ni-ingest`/`mri-ingest` console entry points
  on the Linux acquisition machines (Ryan-managed checkout/venv; add `paramiko` to
  `tools/requirements.txt`). Optional `.desktop` launcher that prompts for the folder. Microscopy =
  standalone `.exe`.
- **NAS perms/env:** front-ends only need the NAS mounted + `GJESUS3_ROOT` set; `env` gives one clear
  error instead of the silent-phantom-path failure. GUI persists NAS root in `%LOCALAPPDATA%`.
- **Config/recipe reproducibility:** GUI saves the generated config as a recipe (default-on,
  opt-out), keeping the registry `ingest_config` pointer meaningful and matching the existing
  "one versioned config per batch" convention. Pure-operator machines may only have the exe → default
  save to a configurable folder; promoting a recipe into the repo is a data-office follow-up.
- **Errors for non-technical users:** translate common failures to plain language (no matches →
  "no files in that folder match this instrument's naming"; bad NAS root → the env message;
  unresolved token → "field references a value not found in these files"); always preview before
  commit; lean on idempotency ("safe to re-run").

## Critical files
- **Reuse (don't modify, except the optional warning-collection refactor):**
  `tools/ingest/config.py` (`expand_batch`, `load_config`, `_is_paravision_exam`),
  `tools/ingest_raw.py` (`run_batch`, `ingest_single`), `tools/ingest/resolver.py`
  (`resolve_link_filename`, `resolve_value`, `resolve_registry_block`),
  `tools/ingest/acq_id.py` (`generate_acq_id`), `tools/ingest/linker.py`
  (`resolve_project`, `lookup_project_folder`, `create_hardlink`),
  `tools/ingest/filename_parser.py`, `tools/ingest/ni_metadata.py`, `tools/ftp_mirror.py` (`mirror`),
  `tools/templates/instruments/*.yaml`.
- **Create:** `tools/operator/{__init__,templates,config_builder,scope,preview,runner,env,ni_ingest,
  mri_ingest}.py`, `tools/operator/gui/` (+ PyInstaller spec), `tools/operator/recipes/`,
  `tasks/operator_ingest_tooling_plan.md` (this plan), later `molecubes_ni_live.yaml`.
- Add `paramiko` (+ GUI/build deps) to `tools/requirements.txt`.

## Open items / assumptions to confirm at build time
- NI live folder layout (Unai) — only blocker; isolated to a future template.
- `scope.resolve_scope` heuristics — confirm single-session vs batch-root detection is reliable
  before relying on it.
- Linux operator machines have a managed repo checkout + venv (Ryan controls the accounts); Windows
  microscopy machine runs the `.exe` only.
- Warning-surfacing mechanism (small refactor vs stdout-scrape).

## Verification (per phase, end-to-end)
- **Core:** `preview_batch(template+overrides)` row-for-row matches `ingest_raw --dry-run` on the
  same inputs across the existing `tools/configs/*.yaml`.
- **NI/MRI scripts:** dry-run on a real session folder shows correct acq_id/project/link; a real run
  produces the acquisitions + hard links (spot-check shared inode + ACL), idempotent on re-run.
- **Microscopy GUI:** recipe-run reproduces a known batch (e.g. re-create the AxioScan 2026-05-22
  result in a throwaway project); builder mode reproduces the 7-chunk `<section>` parse with live
  preview; frozen `.exe` reads a real `.czi` and ingests without a Python install.
