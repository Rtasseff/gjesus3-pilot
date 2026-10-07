# `tools/` — master tool map

Every script that touches gjesus3, in one place: what it does, how you start it,
and where its full docs live. New to the system? Pick your role in
[Which tool do I want?](#which-tool-do-i-want) first.

> **Audience:** mixed. Most rows are for the **data office** (Ryan / superusers).
> Instrument **operators** don't run these directly — they use the GUI or the
> two Linux scripts (see [the operator GUI + scripts](#operator-front-ends-no-yaml)).
> **Researchers** don't run anything here — they use the
> [Finder](#researcher-facing) (`registries/index.html`, double-click over SMB)
> and the **Project Manager** GUI.
> A term you don't recognise → [`GLOSSARY.md`](../GLOSSARY.md).

*Last Updated: 2026-09-28*

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
- **I'm a researcher and want to manage a project** — create one, edit its
  description/owner/status, put acquisitions or my own files into it → the
  **Project Manager** GUI (see [Researcher-facing](#researcher-facing)).
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
| **`create_project.py`** | Create a new project workspace under `projects/` — the folder + the recommended subfolders (`raw_linked/` `working/` `outputs/` `metadata/`) + `_project.yaml` + `provenance.csv` + a `registry_projects.csv` row, all under one registry-lock hold. Called automatically by `ingest_raw.py` when a config opts into auto-create, and by the Project Manager GUI. | `python tools/create_project.py --name "<short>" --description "…" --owner <code>` (or `--interactive`) | spec [`05_PROJECTS.md`](../mfb-rdm-docs/05_PROJECTS.md), [`10_TOOLS.md`](../mfb-rdm-docs/10_TOOLS.md) |
| **`generate_index.py`** | Write the self-contained searchable HTML **Finder** — the global `registries/index.html` and (with `--per-project`) one `index.html` per project folder. You rarely run it by hand: a scheduled job rebuilds the global index daily, and an ingest into a project refreshes that project's `index.html`. | `PYTHONPATH=tools python tools/generate_index.py --nas-root J:/gjesus3-data [--per-project]` | [`FINDER.md`](FINDER.md) |
| **`find_acq.py`** | The search/join engine behind the Finder, plus a read-only CLI: free-text + filters (`--instrument --researcher --subject --anatomy --project --since --until`) over `registry_raw.csv` joined to `registry_projects.csv`, printing the resolved data path. | `PYTHONPATH=tools python tools/find_acq.py <query> [filters]` | [`FINDER.md`](FINDER.md) |
| **`relink_projects.py`** | One-time, idempotent migration of legacy project links to **hard links** (the [decided method](../mfb-rdm-docs/10_TOOLS.md)); also `--create-missing` to add an absent link for an already-ingested acquisition. Historical migration is done; kept for repair. | `python tools/relink_projects.py --nas-root "J:/gjesus3-data" --dry-run` | spec [`10_TOOLS.md`](../mfb-rdm-docs/10_TOOLS.md) |
| **`validate_registries.py`** | Read-only consistency checker for `registries/` + `/raw/` (REG-04): header matches the schema, no duplicate `acq_id`, required fields present, `canonical_path` resolves on disk, enrichment gaps reported as non-fatal WARNs. Exits nonzero on any ERROR. Safe on a read-only mount. | `python tools/validate_registries.py --nas-root J:\gjesus3-data` | spec [`06_REGISTRIES.md`](../mfb-rdm-docs/06_REGISTRIES.md) |
| **`backfill_subjects_table.py`** | One-time, idempotent build of `registry_subjects.csv` (one row per subject) from the cached `subject:` blocks in existing `metadata.json` sidecars — no live DB needed. Upserts through the same writer the ingest uses. | `PYTHONPATH=tools python tools/backfill_subjects_table.py --nas-root J:/gjesus3-data --dry-run` then `--apply` | spec [`06_REGISTRIES.md`](../mfb-rdm-docs/06_REGISTRIES.md) |
| **`backfill_pending_dicom.py`** | One-time, idempotent catch-up for `registries/pending_dicom_regen.csv`: enrols the no-DICOM MRI placeholders that predate the 2026-06-24 auto-queue, so the invariant **"no DICOM-less acquisition without a worklist row"** holds retroactively. Trusts the disk (only enrols an `<ACQ-ID>.data/` that is genuinely empty), preserves a `regenerated` status on re-run. Also the invariant's checker: `--dry-run` reports 0 to add when it holds. | `PYTHONPATH=tools python tools/backfill_pending_dicom.py --nas-root J:/gjesus3-data --dry-run` then `--apply` | [`ingest/pending_dicom.py`](ingest/pending_dicom.py), spec [`10_TOOLS.md`](../mfb-rdm-docs/10_TOOLS.md) |
| **`ftp_mirror.py`** | Standalone SFTP mirror: pull a remote tree (e.g. the MRI platform's FTP server) into a local staging dir, then run `ingest_raw.py` against the local copy. Decoupled from ingest; idempotent (skips files already present). | `python tools/ftp_mirror.py --remote <path> --local D:/staging/<batch>` (credentials via `GJESUS3_FTP_*` env vars) | [`mri-platform/mri_data_access_strategy.md`](../equipment/mri-platform/mri_data_access_strategy.md) |
| **`mri_archive.py`** | **READ-ONLY** access to the MRI platform's archive of older 7 T studies (`mriuser@10.10.3.175`, `/share/homes/mriuser/backup_7T_olddata_260824`). Its wrapper can only list, stat and open `rb`, and only inside that folder. There is no write, delete or shell path. One connection; file contents only outside 08:00–18:00 Mon–Fri. Credentials come from `[mri_archive]` only; the normal MRI tools never point at it. | `python tools/mri_archive.py list --out <local.csv>` | [`historical_data_archives.md`](../equipment/historical_data_archives.md) |

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

Researchers do not run scripts — they use two double-click apps on the share.

**Finding data — the Finder.** The generated
`registries/index.html` on the share (plus a per-project `index.html` in each
project folder): double-click over SMB, search by id / instrument / date /
subject / region, and **Copy path** straight to the data. See
[`FINDER.md`](FINDER.md), [`RESEARCHER_GUIDE.md`](../RESEARCHER_GUIDE.md), and
the researcher [`FAQ.md`](FAQ.md). (The Finder is produced by
`generate_index.py` / `find_acq.py` above, but that is the data office's
concern, not the researcher's.)

**Managing a project — the Project Manager GUI** (`gjesus3_manager.exe`, source
[`manager/gui/`](manager/gui/)): list and edit projects, create one, add existing
`/raw/` acquisitions into a project as hard links, and copy local files in — each
with provenance. A thin front-end over [`manager/`](manager/) + [`ingest/`](ingest/);
it never reimplements a rule. Spec: [`10_TOOLS §5.3`](../mfb-rdm-docs/10_TOOLS.md).
**Deployed to the NAS 2026-08-12** (`gjesus3_manager.exe` + `Project Manager.lnk`).

---

## Supporting utilities (data office)

Read-only checks, recovery, and one-off helpers. Run `python tools/<name>.py …`.

| Tool | What it does |
|------|--------------|
| **`verify_checksums.py`** | Read-only fixity check: recompute checksums under `/raw/` and compare against the registry / sidecars. |
| **`gather_metadata.py`** | Read-only merged "single source of truth" view of an acquisition's registry row + sidecar. |
| **`metadata_completeness.py`** | Read-only enrichment-gap report (which acquisitions still carry unknown-sentinel subject/condition/anatomy values). |
| **`recover_subject_metadata.py`** | Superuser deferred-recovery: re-resolve subject metadata for acquisitions ingested while the animal-facility DB was unreachable. |
| **`retire_acquisition.py`** | **Data Office only.** Retires an ACQ-ID — a byte-identical duplicate (bytes deleted after a fresh SHA-256 match with the survivor; project links re-pointed), a derivative (moved into its original's project folder) or an orphan `/raw/` folder; v2 (✅ design accepted 2026-10-04; not yet used in production): a content-equivalent `.czi` re-save (`--equivalent-of`; `ingest/czi_compare.py`) and a mis-coded acquisition re-identified in place under its correct instrument code (`--reidentify-as`; `ingest/reidentify.py`). The row moves verbatim to `registries/retired_acquisitions.csv`; ids are never reused. Dry run by default, backup first, refuses during an ingest, crash-resumable. Tests: `python tools/test_retire_acquisition.py` and `tools/test_retire_acquisition_v2.py`. See [`10_TOOLS §3.9`](../mfb-rdm-docs/10_TOOLS.md) and [`11_OPERATIONS §5.7`](../mfb-rdm-docs/11_OPERATIONS.md). |
| **`migrate_registry_columns.py`** | Schema-evolution helper (back up → migrate → register the `.bak`). The pattern for any future registry column change. |
| **`migrate_project_naming.py`** | One-shot, already-executed (2026-08-02) migration to the [project reference model](../mfb-rdm-docs/05_PROJECTS.md) §2a: `registry_raw` header → `project_id`, `registry_projects` `short_name` → `name`, project folders renamed to their name, saved NAS recipes deleted. Kept as the paper trail — and as the worked example of a live-data migration (dry-run default, resumable, `--verify`, `--reverse --from-backup`). |
| **`backfill_project_subfolders.py`** | One-time (idempotent, `--dry-run` first) back-fill of the recommended project subfolders `working/` · `outputs/` · `metadata/` onto projects that predate the convention. Skips + lists closed projects whose folders were deleted; reports rather than repairs folders with no `_project.yaml`. See [`10_TOOLS §3.1a`](../mfb-rdm-docs/10_TOOLS.md). |
| **`backfill_microscopy_anatomy.py`**, **`backfill_mri_anatomy.py`**, **`backfill_microscopy_bestguess.py`** | One-time anatomy back-fills for historical acquisitions. See [`ANATOMY_BACKFILL.md`](ANATOMY_BACKFILL.md). |
| **`extract_ni_archives.py`**, **`extract_xmri_archives.py`** | Unpack archived source data into staging ahead of an ingest. |
| **`drive_staging/`** (`stage_copy.py` + `lock_usb.ps1` + `wait_for_drive.ps1`) | Copy an external drive that is the **only copy** of its data onto local staging disk: read each file once, hash it during that same read, verify the copy from the local disk alone. The drive can go back to its owner before verification starts. Pre-ingest only; never touches the NAS. See [`drive_staging/README.md`](drive_staging/README.md). |
| **`drive_staging/catalog.py`** | Read-only, resumable **per-file catalog of a staged drive** (2026-09-29): one row per file and per archive member with its class, the physical instrument that made each `.czi` (by device serial, from [`reference/microscopy_instruments.yaml`](reference/microscopy_instruments.yaml) — the stand name does not identify it), acquisition date, duplicate copies, and whether production already holds the bytes (by SHA-256). Facts about content only; project/animal claims are a separate table. Tests: `python tools/test_drive_catalog.py`. See [`drive_staging/README.md`](drive_staging/README.md#per-file-catalog-catalogpy). |
| **`drive_staging/project_claims.py`** | Read-only **classification of every project claim on a staged drive** (2026-09-29): finds the codes in folder names, filenames and archive listings, checks each one against the animal-facility DB (it must resolve, *and* the file's animals and the DB's own dates must agree), and sorts it into Confirmed / (A) corrected typo / (B) `Project-NNNN` / (C) uncertain. It also maps every file and folder to a project, researcher and (only where safe) subject id. Every rejected number is logged. See [`drive_staging/README.md`](drive_staging/README.md#project-claims-project_claimspy). |
| **`drive_staging/ingest_plan.py`** · `ingest_check.py` · `ingest_verify.py` | The **historical-drives `.czi` ingest** (2026-09-30, one-time): a per-file plan from the catalog + claims (one canonical copy per sha256, Ryan's 2026-09-29 rules), archive extraction, a hard-link farm whose layout makes `original_name` the source path, one generated config + case table per batch; the dry-run review (engine resolution vs plan, file by file); and the post-batch verifier + provenance. Procedure: [`../tasks/drives_microscopy_ingest_runbook.md`](../tasks/drives_microscopy_ingest_runbook.md). See [`drive_staging/README.md`](drive_staging/README.md#the-czi-ingest-ingest_planpy-ingest_checkpy-ingest_verifypy). |
| **`drive_staging/nonraw_placement.py`** · `historical_paths.py` · `drive3/p_plan.py` · `drive3/p_verify.py` | The **historical drives' non-raw placement** (one-time, 2026-10): copies exports, figures, documents, analysis, segmentations and derived volumes into `<project>\working\historical_drives\<drive>\…` (or the holding folder `staging\historical_drives_unassigned\`), byte-verified, never overwriting, with a provenance row each. `historical_paths.py` is THE destination rule (study folder first, every path ≤ 240 characters, `_INDEX.csv` / `_PATHMAP.csv` / `README.txt` / `_ORIGIN.txt` per tree, merged with what is already there). Drives 1+2: [`../tasks/drives_nonraw_placement_review.md`](../tasks/drives_nonraw_placement_review.md). The M. Jesús drive (D3): `p_plan.py` builds its manifest (decisions `place` / `holding` / `held`), and `release` / `handover` add later batches; `p_verify.py` snapshots before and verifies after each copy window. Record and production commands: [`../tasks/drive3_placement_gate.md`](../tasks/drive3_placement_gate.md). Tests: `python tools/test_nonraw_placement.py`, `test_historical_paths.py`, `test_drive3_placement.py`. |
| **`reopen_project.py`** | **Reopen a `closed` project** (2026-09-30): verified off-NAS backup, then the folder skeleton, a missing `_project.yaml` (from the 2026-07-14 close-out backup), every missing link to its registered acquisitions under the original name (+ provenance), status `active` with recomputed acquisition dates, and its Finder page. Never deletes; reports collisions; `--dry-run`; a re-run is a no-op. Procedure: [`05_PROJECTS §4.y`](../mfb-rdm-docs/05_PROJECTS.md). |
| **`repair_link_collisions.py`** | **Audit every project's `raw_linked/` by file identity, and repair what the old silent link merge left behind** (2026-10-05). `audit` (read-only) classifies each acquisition-with-a-project as OK / OK-EXTRA / POLLUTED / MISSING / PARTIAL-OWN / RESEARCHER-PRUNED / PENDING-LINK and lists every link folder that holds more than one acquisition's files (`link_polluted.csv`, for a decision; nothing is removed). `repair` gives each MISSING MRI acquisition its own link under the current MRI convention: dry run by default, `--execute` backs up first, checks the name is free, links, verifies by file id, adds provenance, refreshes the project's Finder page. Additive only; a re-run is a no-op. `prune-foreign` (Ryan, 2026-10-05) removes from each POLLUTED folder only the names of another acquisition's files, and only when the same file is also in `/raw/` and in that acquisition's own complete link: never an owner's file, never a file of no acquisition, never a last name; backup and a write-ahead `hardlink-removed` provenance event first, then each folder verified as exactly its owner's files. Fast per-folder file-id listing on Windows. Tests: `python tools/test_repair_link_collisions.py`. See [`10_TOOLS §2.1.5`](../mfb-rdm-docs/10_TOOLS.md). |
| **`repair_operator_hold.py`** | **Data Office only. Change `operator` cells of `registry_raw.csv` from one exact value to another, in bytes** (2026-10-05; the `operator` hold value `pending-claim` = "awaiting claim", [`06_REGISTRIES §2.3a-bis`](../mfb-rdm-docs/06_REGISTRIES.md)). Defaults: the 10,314 MRI cells that held the template instruction `<REQUIRED - set via mri-ingest --operator, or replace here>` → `pending-claim`; later `--from pending-claim --to-blank` when the claim window closes. **Dry run unless `--apply`**, which needs `--expect N` (refuses unless exactly N cells match) and a `--backup-dir` that does not exist yet (SHA-256-verified copy before any write). Takes the registry lock; edits only the matching cells (the placeholder is stored quoted, so the whole field is replaced), keeping no BOM and CRLF; re-reads and diffs against the backup, and restores it on any mismatch. Never touches sidecars. **Row selectors** (2026-10-07, Ryan's general rule: historical internal MRI loaded without an operator gets `pending-claim`): `--instrument X` and `--config-prefix P` (repeatable; `/` and `\` count as the same), every one of which must match; a blank `--from` (`--from-blank`) is refused without **both**, and the dry run reports the count per prefix. Tests: `python tools/test_operator_hold.py`. |
| **`claim_workbooks.py`** | **Data Office only. APPEND to the two shared workbooks in `projects\`, never rebuild them** (2026-10-07). `claims-append`: one row per MRI session (the scanner study folder) whose acquisitions hold `operator = pending-claim` and that `_MRI sessions - who ran them.xlsx` does not list yet, plus their acquisitions, each marked in an **Added** column (date + source) and one Read me line. `assign-append`: the M. Jesús drive's material with no project, grouped exactly as the 2b mapping groups it (`nonraw_placement.manifest_group` / `blank_list_group`, so an answer applies with the 2b tools): its holding-folder files (`MJesus-MFB`) and its acquisitions registered with a blank project, into `_Historical data - assign to projects.xlsx`, with a companion `drives_blank_project_list.csv`-shaped list for `apply-raw`. Refuses when Excel's lock file `~$…` exists. **Dry run by default** (a preview copy written off the NAS); `--apply` needs a `--backup-dir` that does not exist yet, and verifies that every existing cell is unchanged against that copy, restoring it on any mismatch. Tests: `python tools/test_claim_workbooks.py`. |
| **`repair_primary_inplace.py`** | **Repair a damaged single-file primary in `/raw/` in place** (2026-10-01; the recovery pattern: same ACQ-ID, not a re-ingest). Checks the good copy against its manifest SHA-256 and the damaged one against `checksums.json`; verified off-NAS backup; keeps the damaged bytes; overwrites the **same file** (`r+b`, truncate, fsync) so every project hard link sees the repair; re-hashes the primary and the given links (`.czi`: every subblock decodes); swaps the hash in `checksums.json` (bytes otherwise as found) and updates `file_size_mb` + `notes` via `registry.update_row` under the lock. `--dry-run`. First use: `ACQ-20251031-CELL-003` (truncated at ingest). |

---

## Supporting structure

- [`ingest/`](ingest/) — the pipeline package every front-end shares (config
  parsing, ACQ-ID allocation, checksums, registry writer, hard-linker, metadata
  sidecar, enrichment, locking, subjects table). One source of truth; no parallel
  write paths.
- [`operator/`](operator/) — the shared operator core + the GUI
  ([`operator/gui/`](operator/gui/)) and Linux scripts above.
- [`manager/`](manager/) — the Project Manager core (`projects`, `raw_import`,
  `local_import`, `acq_search`) + its GUI ([`manager/gui/`](manager/gui/)). Same
  rule as `operator/`: the front-end is thin, the logic is here.
- `filebrowse.py` — the folder-listing backend behind the in-page browser,
  shared by both GUIs (its front-end half is
  `operator/gui/static/folder_browser.js`, which the Project Manager serves from
  the same directory rather than copying).
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
