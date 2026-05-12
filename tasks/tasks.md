# MFB gjesus3 RDM Pilot — Task List

**Last Updated:** 2026-05-06

This file consolidates all open and completed tasks. Completed items are kept for context but marked with ~~strikethrough~~.

---

## 1. Design and Documentation

### 1.1 Storage Zones and Structure
- [x] ~~Define the four zones (staging, raw, publications, projects)~~ — done (01_OVERVIEW, 03–05)
- [x] ~~Decide registry location (centralized vs embedded)~~ — done: centralized `registries/` (DECIDED)
- [x] ~~Choose generic term for raw unit~~ — done: "acquisition" (`ACQ`)
- [x] ~~Raw sub-structure: instrument-first vs ecosystem-first~~ — done: ecosystem-based (DECIDED)
- [x] ~~One primary file per acquisition rule~~ — done (DECIDED, no exceptions — DICOM as archive)
- [x] ~~Create NAS directory skeleton~~ — done: staging/, raw/, publications/, projects/, registries/, curated_datasets/
- [ ] Retention policy — define "long-term" and "temporary" concretely (years, migration triggers)

### 1.2 Registries
- [x] ~~Raw registry schema~~ — done (06_REGISTRIES)
- [x] ~~Publication registry schema~~ — done (06_REGISTRIES)
- [x] ~~Project registry schema~~ — done (06_REGISTRIES)
- [x] ~~Curated datasets registry schema~~ — done (06_REGISTRIES, EVALUATING)
- [x] ~~ID schemes (ACQ, PUB, PROJ, DS)~~ — done (06_REGISTRIES Section 7)
- [x] ~~Registry update rules~~ — done (06_REGISTRIES Sections 2.4, 3.4, 4.3)

### 1.3 Provenance
- [x] ~~Provenance format and template~~ — done (07_PROVENANCE)
- [x] ~~Minimum provenance rules for projects and publications~~ — done (07_PROVENANCE)

### 1.4 DICOM Storage and Ingest Architecture
- [x] ~~DICOM storage format (expanded vs archive)~~ — done: compressed archives (DECIDED)
- [x] ~~Primary staging location~~ — done: off-NAS fast local storage (DECIDED)
- [x] ~~Two ingest modes (full + lightweight)~~ — done: documented in 03, 10 (DECIDED)
- [x] ~~Metadata extraction integrated into full-mode ingest~~ — done: documented in 08, 10 (DECIDED)
- [ ] Archive format preference: .zip vs .tar.gz — EVALUATING (RAW-09)

---

## 2. Data Types and Metadata

> **Note:** Most items in 2.1–2.2 will be resolved through the per-modality ingestion testing in Section 4. Each modality test pass examines real files, audits embedded metadata, exercises extraction code, and produces a working example dataset.

### 2.1 Data Types Inventory
- [x] ~~Data types sign-up sheet created~~ — done (09_MODALITIES Section 3)
- [ ] Complete data type sign-up sheet — need volunteer owners per type (MOD-02)
- [ ] Conduct show-and-tell walkthrough for each confirmed data type (MOD-03)
- [ ] Collect one representative example dataset per type for script testing — resolved per-modality in Section 4

### 2.2 Instrument Metadata Audit
> Resolved per-modality during ingestion testing (Section 4). Each test pass audits embedded metadata for that format.
- [ ] DICOM (collaborator) — resolved during Section 4.2
- [ ] .czi from Axio Scan 7 (WSI) — resolved during Section 4.6
- [ ] .czi from Cell Observer — resolved during Section 4.6
- [ ] .czi from LSM 900 — resolved during Section 4.6
- [ ] Confirm Cell Observer and LSM 900 .czi metadata is similar to WSI .czi (MOD-07)
- [ ] DICOM from MRI platform — resolved during Section 4.7
- [ ] DICOM from Nuclear Imaging platform — resolved during Section 4.8
- [ ] Confirm DICOM as the output format from both platforms (MOD-05)

### 2.3 Extended Metadata (REMBI)
- [ ] Complete REMBI field review with users — limited responses so far (META-01)
- [ ] Determine ISA-TAB-Nano applicability for nanomaterial imaging (META-04, if SEM/TEM included)

### 2.4 Modality Decisions
- [ ] SEM/TEM inclusion decision (MOD-01) — awaiting PI confirmation
- [ ] MRI: do the two systems (7T, 11.7T) need separate instrument codes? (09_MODALITIES)
- [ ] NIfTI: confirm whether Nuclear Imaging platform provides NIfTI, and if so, accepted format on gjesus3

---

## 3. Scripts and Tooling

> **Note:** Script implementation and finalization happens iteratively through the per-modality ingestion tests (Section 4). Each modality may expose new requirements for extraction, compression, and registry population.

### 3.1 Ingest Pipeline
- [x] ~~`ingest_raw.py` implemented~~ — single-case, batch, interactive, dry-run modes
- [x] ~~Format-summarizer dispatch (DICOM + microscopy)~~ — `FORMAT_SUMMARIZERS` map in `config.py`; replaces hard-coded DICOM in Step 1
- [x] ~~Microscopy single-file ingest path~~ — non-DICOM `primary_file_name = {acq_id}{ext}`, single-file copy + verify
- [x] ~~Filename parser~~ — `tools/ingest/filename_parser.py` (positional, named fields)
- [x] ~~`metadata.json` sidecar writer~~ — `tools/ingest/metadata_sidecar.py`; cross-format shape matching the on-disk DICOM example (`user_supplied` + `discovered` + `<ecosystem_section>`)
- [x] ~~Auto-discover generalization~~ — `expand_batch` accepts file globs, `filename_parse`, `filter`, `acquisition_date_from: parent_folder_name`; everything lands in the per-case `discovered` namespace
- [x] ~~Idempotent re-runs~~ — `expand_batch` skips files already in registry by `(acquisition_date, original_name)`
- [x] ~~`--delete-source` flag~~ — cross-instrument; default OFF; never touches the parent of `source_path`
- [x] ~~`probe_czi.py` utility~~ — read-only embedded-metadata probe (informs follow-up extraction)
- [x] ~~Three-block YAML schema (`ingest:` / `auto_discover:` / `registry:`) replaces `defaults:` and `SPECIAL_FIELDS`~~ — explicit per-column registry mapping with literal | `discovered.X` | `${...}` interp | NA. Resolver in `tools/ingest/resolver.py`; template at `tools/templates/ingest_template.yaml`; configs land in `tools/configs/`.
- [x] ~~`ingest_config` registry column~~ — relative path of the YAML config that produced each row, for auditability/reproducibility.
- [x] ~~`.czi`-internal metadata → `discovered.czi_*` + `metadata.json.microscopy`~~ — done 2026-05-06; `tools/ingest/czi_metadata.py` surfaces 21 curated fields (precise acquisition timestamp, microscope, objective, pixel size, dimensions, channels, etc.) and a structured 5-bucket `microscopy:` sidecar block. Library: `czifile`. Per-instrument table in [09_MODALITIES §1.1](../mfb-rdm-docs/09_MODALITIES.md), library rationale in [10_TOOLS §2.1.2](../mfb-rdm-docs/10_TOOLS.md).
- [x] ~~Defensive header validation in `registry.append_row`~~ — refuses to write if existing CSV header doesn't match `REGISTRY_FIELDS`; prevents silent column-shift corruption like the one caught when `ingest_config` was added.
- [ ] **REMBI projection** — defer until batch ingestion across multiple instruments gives us real data to map *from*; then design per-instrument projections in a separate utility (lossless sidecar stays canonical). See [08_METADATA §3.5](../mfb-rdm-docs/08_METADATA.md).
- [ ] DICOM full-mode metadata extraction → `discovered.dicom_*` + `metadata.json.dicom` (deferred — separate stream); compression to `.zip`/`.tar.gz` — tested in Section 4.2. Will mirror the `.czi` pattern.
- [ ] **XMRI/DICOM `acquisition_datetime` auto-extract from DICOM headers → `discovered.dicom_*`.** Currently a manual literal in the `registry:` block. Becomes automatic once the DICOM extractor ships.
- [ ] **OMERO export / pylibCZIrw / Bio-Formats** — currently unneeded; revisit when there's a concrete use case (image server, OME-XML normalization, pixel access). See [10_TOOLS §2.1.2](../mfb-rdm-docs/10_TOOLS.md).
- [ ] Implement `--lightweight` flag in `ingest_raw.py` — tested in Section 4.2
- [ ] Add NIfTI handling (single file, no archive) — tested in Section 4.8 if applicable
- [ ] Implement `backfill_metadata` utility for upgrading lightweight ingests
- [ ] Finalize scripts after all modality passes (Section 4.9)
- [ ] **Sample-ID convention follow-ups** (round-4 raised, no urgency):
  - [ ] PI sign-off on the DRAFT composite `sample_id = <short_project>_<short_sample>` (REG-01 still open; see [06_REGISTRIES §2.3](../mfb-rdm-docs/06_REGISTRIES.md))
  - [ ] Confirm with team whether the trailing organ letter (`H`, `B`, ...) inside short sample IDs is a real convention worth parsing into `sample_type` — currently surfaced only as part of the raw chunk; not parsed.
  - [ ] (Optional / future) Predefined chunk-name set that auto-promotes to specific registry columns — explicit `registry:` mapping is the model today; this would be a layer on top, not a replacement.
- [ ] **Refactor [11_OPERATIONS §3.2 Quick Start](../mfb-rdm-docs/11_OPERATIONS.md) for multi-instrument** — current text is AxioScan-7-specific (share path example, config-name example, filename pattern). Once 2-3 instruments are live, separate the common workflow steps from the per-instrument specifics (per-instrument Quick Start subsections or table of "for your instrument, share = ... / filename pattern = ... / starter config = ...").

### 3.2 Other Scripts
- [x] ~~`create_project.py` implemented~~ — CLI + interactive, dry-run
- [ ] `create_publication` — requirements defined, not yet implemented
- [ ] `log_activity` (provenance helper) — requirements defined, not yet implemented
- [ ] `validate_registries` — planned (REG-04)
- [ ] `verify_checksums` — planned

### 3.3 Infrastructure Decisions
- [ ] Where scripts will run — designated workstation vs user machines (TOOL-01)
- [ ] Git repo location and access for scripts (TOOL-02)
- [ ] Script distribution approach — git repo, shared folder, or pip package
- [ ] User training on CLI tools (TOOL-03)
- [ ] GUI wrapper priority — gather user feedback (TOOL-04)

---

## 4. Per-Modality Ingestion Testing

> **Approach:** Each modality gets its own test pass. This is how we work through the metadata audit (Section 2.2), example datasets (2.1), format confirmations (2.4), and script refinement (3.1). Each pass follows the same pattern: get sample data → inspect files → test extraction → test ingest → verify outputs. Script improvements carry forward to subsequent passes.
>
> **Prerequisite for all passes:** Ryan manually copies data to local drive before extraction/ingestion. Primary ingest path uses fast local storage per the off-NAS staging decision.

### 4.1 Prepare Local Staging (one-time)
- [x] ~~Backup originals to `staging/_originals_backup/` on NAS~~
- [x] ~~**Ryan:** Copy `staging/HPIC_33cases/` and `staging/LIONS_42cases/` from NAS to local drive~~
- [x] ~~Extract all archives on local drive (unrar/unzip)~~

### 4.2 Pass 1: Collaborator DICOM (HPIC/LIONS — `XMRI`)
> First modality. Exercises DICOM header reading, archive compression, full vs lightweight modes.
- [x] ~~Inspect extracted DICOM contents (verify structure, count files, check headers with pydicom)~~
- [x] ~~Audit embedded metadata — what DICOM fields are present and useful? (feeds 2.2)~~
- [x] ~~Test full-mode ingest: dry-run on one HPIC case, verify outputs~~
- [x] ~~Test maximal metadata extraction (all available DICOM header fields → metadata.json)~~
- [ ] Test lightweight mode (sparse registry entry, `extended_metadata_present` = `N`) — full-mode covered, lightweight path still untested
- [x] ~~Test real ingest on one HPIC case, verify: acquisition folder, archive, metadata.json, checksums.json, registry row~~

### 4.3 Linking Method and Raw Immutability
> **Critical constraint:** Raw acquisition folders must be read-only after deposit (DECIDED — see 03_RAW_STORAGE Section 7). The linking method must work *without* requiring write access to raw folders.

**Linking method — decision and unit test (resolved):**
- [x] ~~Decide linking method~~ — **Windows `.lnk` shell shortcuts** (Windows-first, pilot-specific; see 10_TOOLS §2.1.1)
- [x] ~~Validate `.lnk` behavior over SMB empirically~~ — 75 manually-created links across HPIC and LIONS work fine
- [x] ~~Update `linker.py` to actually create `.lnk` files~~ — done 2026-05-05; PowerShell `WScript.Shell` shell-out, idempotent, Windows-only for creation
- [x] ~~Wire linker into `ingest_raw.py`~~ — Step 12; runs when `project_hint` is set and `--nas-unc` is provided
- [x] ~~Linker unit sanity test~~ — `create_lnk()` standalone produces a working `.lnk` (correct icon, double-click opens, target UNC correct)

**Linking — end-to-end testing (still open; the new code path has never been exercised through a real ingest):**
- [ ] Dry-run an ingest config with `project_hint: PROJ-0001` — verify Step 12 logs the would-be `.lnk` path without creating anything
- [ ] Real single-case ingest with `--project PROJ-0001` on a fresh acquisition — verify the new `.lnk` appears in `projects/proj-lions-cardiac-mri/raw_linked/` and behaves like the existing 75
- [ ] Idempotency check — re-run the same ingest, confirm no error and the existing `.lnk` is left untouched
- [ ] Failure-mode sanity: bogus `--project PROJ-9999` → warns + skips, ingest still succeeds
- [ ] Failure-mode sanity: `--nas-unc ""` → disables `.lnk` creation, ingest still succeeds
- [ ] (Optional) Backfill check — re-run the original LIONS/HPIC batch configs with the new linker code to confirm idempotency on the existing 75

**Raw immutability (still open):**
- [ ] Apply post-deposit lockdown on one test acquisition folder (chmod or ACL — determine which works on QNAP SMB)
- [ ] Verify raw folder is truly read-only from Windows SMB and WSL
- [ ] Verify links are **read-only traversal** — users can follow the link and read files but not modify raw data through the link
- [ ] Decide: script the post-deposit lockdown into `ingest_raw.py`, or keep it as a separate admin step?
- [ ] (Deferred to future deployments) Symlink-based linking via WSL or SSH-into-NAS — see porting note in 10_TOOLS §2.1.1

### 4.4 Batch Ingest: Collaborator DICOM
- [x] ~~End-to-end dry-run of batch config for HPIC (all 33 cases)~~
- [x] ~~Batch ingest all 33 HPIC cases~~ — registry confirmed (PROJ-0002)
- [x] ~~Post-ingestion verification: registry completeness, checksum spot-check, Windows SMB access~~
- [x] ~~End-to-end dry-run of batch config for LIONS (all 42 cases)~~
- [x] ~~Batch ingest all 42 LIONS cases~~ — registry confirmed (PROJ-0001)
- [x] ~~Post-ingestion verification~~

**Cleanup follow-ups discovered post-ingest (2026-05-05 audit):**
- [ ] Dedupe `registries/ingest_manifest.csv` — `LEONE_1.01.zip` appears 2×, `HPIC02.rar` appears 3× (raw registry itself is clean — single row per ACQ)
- [ ] Backfill `acquisition_datetime` for `ACQ-20260310-XMRI-001` (HPIC11) — date couldn't be parsed at ingest, fell back to registration date
- [ ] (Optional) Re-run ingest on existing 75 acquisitions with new linker code — idempotent (skips existing `.lnk` files); confirms all 75 project links are accounted for and creates any that are missing

### 4.5 Pass 2: Platform DICOM — MRI (`MRI`)
> Different DICOM source — platform-reconstructed rather than collaborator. May have different header conventions, different series structure.
- [ ] **Ryan:** Obtain sample MRI DICOM dataset from MRI platform
- [ ] Confirm DICOM as the output format from MRI platform (MOD-05)
- [ ] Inspect file structure and headers — compare with collaborator DICOM
- [ ] Audit embedded metadata — what fields differ from collaborator DICOM? (feeds 2.2)
- [ ] Test full-mode ingest on one MRI case
- [ ] Verify metadata.json captures MRI-specific fields
- [ ] Resolve: do the two MRI systems need separate instrument codes? (Section 2.4)

### 4.6 Pass 3: Microscopy .czi (`ZWSI`, `CELL`, `LSM9`)
> Completely different format — single-file primary, no archive needed, different metadata extraction library (czifile / aicspylibczi).

**4.6.A Axio Scan 7 (`ZWSI`) — first .czi pass:**
- [x] ~~Filename-driven auto-discover (group/operator/sample_id/...) wired into `expand_batch`~~ (see §3.1)
- [x] ~~Microscopy single-file copy + verify + canonical rename `{acq_id}.czi`~~ (see §3.1)
- [x] ~~`metadata.json` sidecar with `user_supplied` + `discovered`~~ (see §3.1)
- [x] ~~Read-only probe of one real .czi from `S:\...\AxioScan\20260422` (czifile + XML dump to `_probes/`)~~
- [x] ~~Real ingest of 3 `.czi` files from `S:\...\AxioScan\20260422` to NAS (first pass: filename-only metadata)~~ — first ingest 2026-05-06, then purged.
- [x] ~~Re-ingest of the same 3 files with .czi-internal metadata extraction~~ — 2026-05-06; populated `microscopy:` sidecar blocks (geometry, instrument, acquisition, mosaic, document_info, plus full `_raw_metadata` for lossless preservation; sidecar ~850 KB matching the probe) and 21-field `discovered.czi_*` curated subset. Registry CSV migrated to 22-column schema (added `ingest_config`); defensive header check added in `registry.append_row`.
- [x] ~~Project auto-create via `ingest.auto_create_projects: true`~~ — 2026-05-06; on first ingest with an unknown `project_hint`, ingest_raw creates the project (short_name = hint) and sets the registry's `project_hint` to the canonical `PROJ-XXXX`; subsequent acqs reuse via `short_name` lookup. Tested: PROJ-0003 (short_name=1022, owner=AUA) auto-created, 3 .lnk shortcuts placed in `/projects/proj-1022/raw_linked/`.
- [x] ~~Round-4 scale + multi-project + composite sample_id test (2026-05-12)~~ — `S:\...\AxioScan\20260506\` (28 MFB `.czi` files across 3 animal projects), single config `axioscan7_20260506_TEST.yaml`, end-to-end successful (28/28). Validated: composite `sample_id` via `${discovered.project}_${discovered.sample_short}`; full-code `project_hint = "AE-biomeGUNE-${discovered.project}"` → 3 projects auto-created with short_names `ae-biomegune-{0423,0424,0525}` and reused on subsequent files; 28 `.lnk` shortcuts (8/8/12 split); idempotent re-run (0 new rows, 28 dedupe skips + 1 filter skip); sidecar `discovered` block contains all 6 filename chunks + 21 `czi_*` fields, `microscopy._raw_metadata` ~366 KB. Purged after verification.
- [x] ~~User-facing manual-ingest documentation~~ (2026-05-12) — researcher Quick Start in [`11_OPERATIONS.md §3.2`](../mfb-rdm-docs/11_OPERATIONS.md); CLI reference (flags, config cheat-sheet, free-form chunk note) at [`tools/INGEST_CLI.md`](../tools/INGEST_CLI.md). Production config `axioscan7_20260506.yaml` shipped for user-driven Phase B re-ingest.
- [ ] **User (Phase B):** manually run `tools/configs/axioscan7_20260506.yaml` following the new Quick Start in `11_OPERATIONS.md §3.2`. Dry-run first, then real. Outputs become production data (PROJ-0003..0005 will be re-created with the same `ae-biomegune-*` short_names). Capture any doc-gap moments so the docs can absorb them.
- [ ] **User:** physically verify a `.lnk` shortcut opens the correct `.czi` on double-click for the new microscopy single-file shortcuts (covers the long-standing "open from .lnk" check originally tracked for the 2026-04-22 batch).

**4.6.B Cell Observer (`CELL`) — reuses 4.6.A pipeline:**
- [ ] **Ryan:** Obtain sample `.czi` from Cell Observer
- [ ] Audit embedded metadata — confirm similarity to Axio Scan 7 (MOD-07)
- [ ] Dry-run + real ingest of one `.czi` file (filename parser config may differ if naming convention differs)

**4.6.C LSM 900 (`LSM9`) — reuses 4.6.A pipeline:**
- [ ] **Ryan:** Obtain sample `.czi` from LSM 900
- [ ] Audit embedded metadata — confirm similarity to Axio Scan 7 (MOD-07)
- [ ] Dry-run + real ingest of one `.czi` file

**4.6.D Lightweight mode for microscopy:**
- [ ] Test `--lightweight` mode on one `.czi` file (sets `extended_metadata_present=N`, no sidecar)

### 4.7 Pass 4: Platform DICOM — Nuclear Imaging (`PET`, `SPECT`, `CT`)
> May include hybrid multi-modal acquisitions (PET/CT, PET/SPECT/CT). Tests the multi-modality handling.
- [ ] **Ryan:** Obtain sample Nuclear Imaging datasets (ideally one single-modality and one hybrid)
- [ ] Confirm output format(s) from Nuclear Imaging platform — DICOM, NIfTI, or both? (MOD-05, Section 2.4)
- [ ] Inspect file structure and headers — compare with MRI and collaborator DICOM
- [ ] Audit embedded metadata (feeds 2.2)
- [ ] Test full-mode ingest on one case
- [ ] Test hybrid handling — does a PET/CT session stay as one acquisition? Verify `modalities_in_study` field

### 4.8 Pass 5: NIfTI (if applicable)
> Only if Nuclear Imaging platform provides NIfTI. Single file, no archive, limited header metadata.
- [ ] Confirm NIfTI is a real output from the platform (Section 2.4)
- [ ] If yes: inspect NIfTI header metadata — what's available?
- [ ] Implement NIfTI handling in ingest (single file, no compression) (feeds 3.1)
- [ ] Test ingest on one NIfTI file
- [ ] If no: mark this pass as N/A

### 4.9 Pass 6: EM (if included)
> Only if SEM/TEM is confirmed for pilot (MOD-01).
- [ ] Awaiting PI decision on SEM/TEM inclusion
- [ ] If included: obtain sample EM files, inspect formats and metadata
- [ ] Test ingest workflow for EM data

### 4.10 Finalize Scripts (WSL)
> After all modality passes are complete, finalize and harden the scripts.
- [ ] Finalize `ingest_raw.py` — full mode covering all tested modalities
- [ ] Finalize `ingest_raw.py` — lightweight mode (`--lightweight`)
- [ ] Finalize `linker.py` based on linking method decision (Section 4.3)
- [ ] Implement `backfill_metadata` utility
- [ ] Update documentation (10_TOOLS, 03_RAW_STORAGE) with any changes discovered during testing

---

## 5. Publication Back-Test

> **Approach:** After ingestion testing is working (Section 4), take a real completed publication from Susana or Irene and use it as a test case to validate the publication workflow end-to-end. These publications were assembled ad hoc — the raw data exists somewhere but there is no formal provenance trail or structured link back to raw acquisitions. Working backward from the finished product will reveal what provenance recording looks like in practice, how intermediate files should be tracked, and what the `raw_linked/` and `provenance.csv` setup should look like for a real publication folder.

### 5.1 Select and Set Up Test Case
- [ ] **Ryan:** Identify one completed publication from Susana or Irene that has data suitable for open access
- [ ] Inventory the publication folder contents — what files exist? (figures, analysis outputs, raw-adjacent files, scripts, etc.)
- [ ] Identify which raw acquisitions the publication depends on — are they already ingested? Can they be matched?

### 5.2 Trace Provenance Backward
- [ ] For each key output file (figures, processed images), trace back: what raw data did it come from? What intermediate steps were taken?
- [ ] Document the provenance chain — even if incomplete, capture what can be reconstructed
- [ ] Identify gaps: what information is lost because it wasn't recorded at the time?

### 5.3 Build the Publication Package
- [ ] Create a formal publication folder using `create_publication` (or manual equivalent)
- [ ] Populate `raw_linked/` — link back to the raw acquisitions (test the linking method decided in Section 4.3)
- [ ] Populate `provenance.csv` — record the traced provenance chain using the format from 07_PROVENANCE
- [ ] Identify intermediate/derived files — where do they live? How should they be referenced?

### 5.4 Evaluate and Refine
- [ ] Does the provenance format (07_PROVENANCE) work for this real case? What's awkward or missing?
- [ ] Does the publication folder structure (04_PUBLICATIONS) work? What needs adjusting?
- [ ] What would users need to do differently *during* a project to make this easy at publication time?
- [ ] Update documentation (04_PUBLICATIONS, 07_PROVENANCE) based on lessons learned
- [ ] Use findings to inform `create_publication` script requirements and `log_activity` design

---

## 6. Operations (after Sections 4–5)

- [ ] Define intake roles: who can promote staging to raw (OPS-01)
- [ ] Configure NAS user/group permissions (OPS-02)
- [ ] Write Quick Start guide for pilot users (OPS-03)
- [ ] Schedule pilot start date (OPS-04)
- [ ] Set pilot review cadence (weekly for 4-6 weeks) — defined in 11_OPERATIONS, not yet scheduled

---

## 7. Infrastructure

- [ ] Backup strategy — RAID 5 only, no offsite; define minimal mitigation
- [ ] Snapshot retention policy and restore procedure — snapshots confirmed active, details TBD
- [ ] Filesystem type confirmation — affects linking method and permission enforcement (resolved during Section 4.3)
- [ ] Raw immutability enforcement mechanism — chmod vs QNAP SMB ACLs; script vs manual (resolved during Section 4.3)

---

## 8. Deferred

- [ ] Curated datasets area — circle back after RAW ingestion is working (12_CURATED_DATASETS, EVALUATING)
- [ ] Raw data linking method for publications/projects — resolved during Section 4.3 testing
- [ ] Filename parser for legacy uploads — deprioritized
- [ ] User-supplied metadata workflows (CSVs/Excel for sample context) — deferred to post-pilot
- [ ] GUI wrappers for tools — deferred to post-pilot based on user feedback
- [ ] Operator encoding in ACQ-ID — registry only for now (RAW-01)
