# `tools/` — master tool map

Every script that touches gjesus3, in one place: what it does, how you start it,
and where its full docs live. New to the system? Pick your role in
[Which tool do I want?](#which-tool-do-i-want) first.

> **Audience:** mixed. Most rows are for the **data office** (Ryan / superusers).
> Instrument **operators** don't run these directly — they use the GUI or the
> two Linux scripts (see [the operator GUI + scripts](#operator-front-ends-no-yaml)).
> **Researchers** don't run anything here — they use the
> [Finder](#researcher-facing) (`registries/index.html`, double-click over SMB).
> A term you don't recognise → [`GLOSSARY.md`](../GLOSSARY.md).

*Last Updated: 2026-06-26*

---

## Which tool do I want?

- **I run an instrument and want to put my data on gjesus3.** Use the
  **operator front-ends**, not the CLIs below:
  - microscopy (AxioScan 7 / Cell Observer / LSM 900) **or** MRI (Bruker
    ParaVision) on a Windows machine → the **`gjesus3_ingest.exe`** GUI.
  - MRI or Nuclear Imaging on the Linux acquisition box → **`mri-ingest`** /
    **`ni-ingest`**.
  - Start here: [`../START_HERE.md`](../START_HERE.md) and
    [`OPERATOR_FAQ.md`](OPERATOR_FAQ.md).
- **I'm a researcher and want to find / open my data.** Don't run any tool —
  open the **Finder**: double-click `registries\index.html` on the share
  (or your project's own `index.html`). Guide: [`FINDER.md`](FINDER.md),
  [`RESEARCHER_GUIDE.md`](../RESEARCHER_GUIDE.md), [`FAQ.md`](FAQ.md).
- **I'm the data office / a superuser** running an ingest from YAML, creating a
  project, checking registry health, or doing a one-time back-fill / migration →
  the [top-level CLIs](#top-level-clis) below.

---

## Top-level CLIs

The primary command-line tools, run with `python tools/<name>.py …`. Most read
or write the NAS, so they need to know where it is mounted — pass `--nas-root`
(e.g. `J:\gjesus3-data`) or set the `GJESUS3_ROOT` environment variable. Several
need `PYTHONPATH=tools` (or to be run from the repo root) so `from ingest …`
resolves.

| Tool | What it does | Start it | Docs |
|------|--------------|----------|------|
| **`ingest_raw.py`** | The core pipeline: copy raw data from staging into `/raw/`, register one row per acquisition, write the `metadata.json` sidecar, hard-link it into a project, and auto-refresh the Finder. Idempotent; **always dry-run first**. | `python tools/ingest_raw.py -c <config>.yaml -n` (preview) then drop `-n`; `-i` for a single interactive case | [`INGEST_CLI.md`](INGEST_CLI.md), specs [`10_TOOLS.md`](../mfb-rdm-docs/10_TOOLS.md) · [`03_RAW_STORAGE.md`](../mfb-rdm-docs/03_RAW_STORAGE.md) |
| **`create_project.py`** | Create a new project workspace under `projects/` (folder skeleton + `provenance.csv` + a `registry_projects.csv` row). Called automatically by `ingest_raw.py` when a config opts into auto-create. | `python tools/create_project.py --name "<short>" --description "…" --owner <code>` (or `--interactive`) | spec [`05_PROJECTS.md`](../mfb-rdm-docs/05_PROJECTS.md), [`10_TOOLS.md`](../mfb-rdm-docs/10_TOOLS.md) |
| **`generate_index.py`** | Write the self-contained searchable HTML **Finder** — the global `registries/index.html` and (with `--per-project`) one `index.html` per project folder. You rarely run it by hand: every successful ingest auto-refreshes it. | `PYTHONPATH=tools python tools/generate_index.py --nas-root J:/gjesus3-data [--per-project]` | [`FINDER.md`](FINDER.md) |
| **`find_acq.py`** | The search/join engine behind the Finder, plus a read-only CLI: free-text + filters (`--instrument --researcher --subject --anatomy --project --since --until`) over `registry_raw.csv` joined to `registry_projects.csv`, printing the resolved data path. | `PYTHONPATH=tools python tools/find_acq.py <query> [filters]` | [`FINDER.md`](FINDER.md) |
| **`relink_projects.py`** | One-time, idempotent migration of legacy project links to **hard links** (the [decided method](../mfb-rdm-docs/10_TOOLS.md)); also `--create-missing` to add an absent link for an already-ingested acquisition. Historical migration is done; kept for repair. | `python tools/relink_projects.py --nas-root "J:/gjesus3-data" --dry-run` | spec [`10_TOOLS.md`](../mfb-rdm-docs/10_TOOLS.md) |
| **`validate_registries.py`** | Read-only consistency checker for `registries/` + `/raw/` (REG-04): header matches the schema, no duplicate `acq_id`, required fields present, `canonical_path` resolves on disk, enrichment gaps reported as non-fatal WARNs. Exits nonzero on any ERROR. Safe on a read-only mount. | `python tools/validate_registries.py --nas-root J:\gjesus3-data` | spec [`06_REGISTRIES.md`](../mfb-rdm-docs/06_REGISTRIES.md) |
| **`backfill_subjects_table.py`** | One-time, idempotent build of `registry_subjects.csv` (one row per subject) from the cached `subject:` blocks in existing `metadata.json` sidecars — no live DB needed. Upserts through the same writer the ingest uses. | `PYTHONPATH=tools python tools/backfill_subjects_table.py --nas-root J:/gjesus3-data --dry-run` then `--apply` | spec [`06_REGISTRIES.md`](../mfb-rdm-docs/06_REGISTRIES.md) |
| **`ftp_mirror.py`** | Standalone SFTP mirror: pull a remote tree (e.g. the MRI platform's FTP server) into a local staging dir, then run `ingest_raw.py` against the local copy. Decoupled from ingest; idempotent (skips files already present). | `python tools/ftp_mirror.py --remote <path> --local D:/staging/<batch>` (credentials via `GJESUS3_FTP_*` env vars) | [`mri-platform/mri_data_access_strategy.md`](../equipment/mri-platform/mri_data_access_strategy.md) |

---

## Operator front-ends (no YAML)

For instrument operators ingesting their own data — same validated pipeline as
`ingest_raw.py`, but point-at-a-folder with no config editing. Thin front-ends
over a shared core (`tools/operator/`); none reimplements ingest logic.
Overview: [`operator/README.md`](operator/README.md). Operator questions:
[`OPERATOR_FAQ.md`](OPERATOR_FAQ.md).

| Front-end | For | Where it runs | Entry point |
|-----------|-----|---------------|-------------|
| **`gjesus3_ingest.exe`** (GUI) | microscopy (ZWSI / CELL / LSM9) **and** MRI (ParaVision) operators | Windows (opens in the browser) | The frozen executable deployed on the NAS (~95 MB, PyInstaller/Flask). Source: [`operator/gui/`](operator/gui/) (`app.py`, built via `gjesus3_ingest.spec`) — [`operator/gui/README.md`](operator/gui/README.md) |
| **`mri-ingest`** | MRI (Bruker ParaVision) operators | Linux acquisition machine | `python tools/operator/mri_ingest.py /path/to/study` (previews, then `Proceed? [y/N]`) |
| **`ni-ingest`** | Nuclear Imaging (Molecubes / MILabs PET/SPECT/CT) operators | Linux acquisition machine | `python tools/operator/ni_ingest.py /path/to/folder` (previews, then `Proceed? [y/N]`) |

> **Name note:** the GUI is **`gjesus3_ingest.exe`** (microscopy **and** MRI
> pages). The older name *`microscopy_ingest.exe`* is obsolete.

---

## Researcher-facing

Researchers do not run scripts. They use the **Finder** — the generated
`registries/index.html` on the share (plus a per-project `index.html` in each
project folder): double-click over SMB, search by id / instrument / date /
subject / region, and **Copy path** straight to the data. See
[`FINDER.md`](FINDER.md), [`RESEARCHER_GUIDE.md`](../RESEARCHER_GUIDE.md), and
the researcher [`FAQ.md`](FAQ.md). (The Finder is produced by
`generate_index.py` / `find_acq.py` above, but that is the data office's
concern, not the researcher's.)

---

## Supporting utilities (data office)

Read-only checks, recovery, and one-off helpers. Run `python tools/<name>.py …`.

| Tool | What it does |
|------|--------------|
| **`verify_checksums.py`** | Read-only fixity check: recompute checksums under `/raw/` and compare against the registry / sidecars. |
| **`gather_metadata.py`** | Read-only merged "single source of truth" view of an acquisition's registry row + sidecar. |
| **`metadata_completeness.py`** | Read-only enrichment-gap report (which acquisitions still carry unknown-sentinel subject/condition/anatomy values). |
| **`recover_subject_metadata.py`** | Superuser deferred-recovery: re-resolve subject metadata for acquisitions ingested while the animal-facility DB was unreachable. |
| **`migrate_registry_columns.py`** | Schema-evolution helper (back up → migrate → register the `.bak`). The pattern for any future registry column change. |
| **`backfill_microscopy_anatomy.py`**, **`backfill_mri_anatomy.py`**, **`backfill_microscopy_bestguess.py`** | One-time anatomy back-fills for historical acquisitions. See [`ANATOMY_BACKFILL.md`](ANATOMY_BACKFILL.md). |
| **`extract_ni_archives.py`**, **`extract_xmri_archives.py`** | Unpack archived source data into staging ahead of an ingest. |

---

## Supporting structure

- [`ingest/`](ingest/) — the pipeline package every front-end shares (config
  parsing, ACQ-ID allocation, checksums, registry writer, hard-linker, metadata
  sidecar, enrichment, locking, subjects table). One source of truth; no parallel
  write paths.
- [`operator/`](operator/) — the shared operator core + the GUI
  ([`operator/gui/`](operator/gui/)) and Linux scripts above.
- [`templates/`](templates/) — ingest config templates: the universal
  `ingest_template.yaml` + per-instrument templates under
  `templates/instruments/`. Copy and edit; never edit in place.
- `configs/` — per-batch configs (version-locked with the scripts); each row's
  `ingest_config` column records which config produced it.
- [`requirements.txt`](requirements.txt) — Python dependencies.

## Reference docs in this folder

- [`INGEST_CLI.md`](INGEST_CLI.md) — full `ingest_raw.py` CLI + config-schema reference (data-office / YAML path).
- [`FINDER.md`](FINDER.md) — the researcher Finder: how it works, how to generate it.
- [`FAQ.md`](FAQ.md) — researcher FAQ (find / open / cite your data).
- [`OPERATOR_FAQ.md`](OPERATOR_FAQ.md) — operator / tech FAQ (getting data onto the NAS).
- [`ANATOMY_BACKFILL.md`](ANATOMY_BACKFILL.md) — the one-time anatomy back-fill procedures.
