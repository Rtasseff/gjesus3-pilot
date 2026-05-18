# MFB gjesus3 RDM Pilot — Task List

**Last Updated:** 2026-05-18

This file consolidates all open and completed tasks. Completed items are kept for context but marked with ~~strikethrough~~.

---

## 0. Active Pass / Up Next

> **⚠️ All current ingests are quasi-production.** Each instrument is iterated test → purge → accept-as-quasi-production. After the team exhibition, **everything gets purged** and true production restarts incorporating exhibition feedback. "Done" below means done in the quasi-production sense; the TEST tagging in config filenames + registry notes is intentional and stays.

**Rounds completed in quasi-production state:**

| Round | Instrument | Outcome on NAS | Config(s) |
|-------|-----------|----------------|-----------|
| 1–2 | Collaborator DICOM (XMRI) | 75 acqs across PROJ-0001 (LIONS, 42) + PROJ-0002 (HPIC, 33) | `lions_*.yaml`, `hpic_*.yaml` |
| 4 | AxioScan 7 (ZWSI) | 28 acqs across PROJ-0003/0004/0005 (`ae-biomegune-{0423,0424,0525}`) | `axioscan7_20260506.yaml` (+ TEST) |
| 5 | Cell Observer (CELL) | **165 acqs across PROJ-0006/0007/0008** (`itziar-colageno`, `itziar-alphasma`, `itziar-colageno-permeabilizado`) — exercised **both filename-focused and path-focused metadata extraction** on real Ainhize/Itziar data | `cell_observer_itziar_alphasma_TEST.yaml`, `cell_observer_itziar_colageno_perm_TEST.yaml` |

Round-5 round-up (Cell Observer) detail trail in §4.6.B.

**We are now waiting on three external blockers — no rounds are actively code-blocked.** Pick up whichever lands first:

| Pass | Section | Blocked on |
|------|---------|-----------|
| LSM 900 confocal (`LSM9`) | §4.6.C | Ainhize Urkola Arsuaga to provide a detailed example. Expected source `K:\gjesus\Ainhize\CONFOCAL LSM 900\`. Should reuse Cell Observer cells-mode template with minor tweaks. |
| Platform MRI DICOM (`MRI`) | §4.5 | (a) Platform manager to answer FTP/access questions; (b) sample MRI DICOM dataset. Strategy doc: [`equipment/mri-platform/mri_data_access_strategy.md`](../equipment/mri-platform/mri_data_access_strategy.md). |
| Nuclear Imaging (`PET`/`SPECT`/`CT`) | §4.7 | Platform Manager **Unai** to answer one outstanding question before we submit the data-workflow documentation + example. |

**Code-side prerequisite** that's independent of all three waits and worth doing in the interim: **DICOM full-mode metadata extractor + compress-on-ingest** (§3.1). Mirrors what `tools/ingest/czi_metadata.py` did for `.czi`. Can be prototyped against the existing 75 collaborator XMRI acquisitions; needed for both MRI and Nuclear Imaging rounds.

**If switching between passes**, each per-pass section has a "Pickup context" subsection written to be read cold.

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
- [x] ~~**`path_parse` YAML feature** (design intent locked 2026-05-13; implemented 2026-05-14 in `tools/ingest/config.py:expand_batch`).~~ Symmetric to `filename_parse`: name the path levels between `staging_dir` and the file via `auto_discover.path_parse.levels: [...]`; each becomes `discovered.<name>`. Recursive glob auto-enabled. Mismatched-depth files skip with WARN. Filename chunks override path levels on name collision. Documented in [10_TOOLS §2.1.3](../mfb-rdm-docs/10_TOOLS.md). Cell Observer use exercised via synthetic-fixture smoke test; first real-data exercise pending in §4.6.B.
- [x] ~~**`auto_create_project:` YAML block** (DECIDED + implemented 2026-05-14).~~ Optional top-level block, peer to `auto_discover:` / `registry:`. Supplies `owner` / `description` / `notes` for first-time project auto-creation; resolver-evaluated. First-write-wins (subsequent ingests with the same project_hint log INFO and skip the block). Empty resolved values WARN and continue. Documented in [10_TOOLS §2.1.4](../mfb-rdm-docs/10_TOOLS.md); cross-refs in [05_PROJECTS §7+§10](../mfb-rdm-docs/05_PROJECTS.md), [06_REGISTRIES §4.2](../mfb-rdm-docs/06_REGISTRIES.md). Universal template + AxioScan template updated. Cell Observer template still to be created (round-5 §4.6.B).
- [x] ~~**Cross-check WARN for path_parse / filename_parse collisions** (surfaced during round-5 Cell Observer 2026-05-15; implemented 2026-05-15).~~ When path_parse and filename_parse both produce values for the same `discovered.<key>` and the values disagree, a per-key WARN fires naming the file + both values + the documented "filename wins" behaviour. Same-value collisions are silent (redundant but harmless). Implemented in `tools/ingest/config.py:expand_batch`. Documented in [10_TOOLS §2.1.3](../mfb-rdm-docs/10_TOOLS.md). Smoke-test verified with mismatched / matched / orthogonal cases. Related deferred cleanup: support `_` placeholder chunks in `filename_parse.fields` / `path_parse.levels` to express "this position is informational, don't store it" — would let configs avoid intentional collisions altogether. Optional strict mode (fail on mismatch) also deferred — WARN-and-continue is the right default during the pilot.
- [ ] Implement `--lightweight` flag in `ingest_raw.py` — tested in Section 4.2
- [ ] Add NIfTI handling (single file, no archive) — tested in Section 4.8 if applicable
- [ ] Implement `backfill_metadata` utility for upgrading lightweight ingests
- [ ] Finalize scripts after all modality passes (Section 4.9)
- [ ] **Sample-ID convention follow-ups** (round-4 raised, no urgency):
  - [ ] PI sign-off on the DRAFT composite `sample_id = <short_project>_<short_sample>` (REG-01 still open; see [06_REGISTRIES §2.3](../mfb-rdm-docs/06_REGISTRIES.md))
  - [ ] Confirm with team whether the trailing organ letter (`H`, `B`, ...) inside short sample IDs is a real convention worth parsing — feeds into the `anatomical_entity` future column below.
  - [ ] (Optional / future) Predefined chunk-name set that auto-promotes to specific registry columns — explicit `registry:` mapping is the model today; this would be a layer on top, not a replacement.
- [ ] **Sample-type vocabulary follow-ups** (REG-07; see [06_REGISTRIES §2.4](../mfb-rdm-docs/06_REGISTRIES.md)):
  - [ ] PI sign-off on the DRAFT 5-value vocab (`tissue` / `organism` / `cells` / `material` / `phantom`).
  - [ ] Apply across remaining instruments as they come online — set the appropriate default in each per-instrument template under `tools/templates/instruments/`.
  - [ ] (Future) Add dedicated `sample_organism` (e.g. `Mus musculus`) and `anatomical_entity` (e.g. `heart`, `brain`) columns to the raw registry — splits the current freeform `"mouse lung section"`-style strings into queryable fields. Coordinate with REG-01 (composite sample_id) and the organ-letter parsing question so we don't duplicate effort.
- [ ] **Refactor [11_OPERATIONS §3.2 Quick Start](../mfb-rdm-docs/11_OPERATIONS.md) for multi-instrument** — current text is AxioScan-7-specific (share path example, config-name example, filename pattern). Once 2-3 instruments are live, separate the common workflow steps from the per-instrument specifics (per-instrument Quick Start subsections or table of "for your instrument, share = ... / filename pattern = ... / starter config = ...").

### 3.2 Other Scripts
- [x] ~~`create_project.py` implemented~~ — CLI + interactive, dry-run
- [ ] `create_publication` — requirements defined, not yet implemented
- [ ] `log_activity` (provenance helper) — requirements defined, not yet implemented
- [ ] `validate_registries` — planned (REG-04)
- [ ] `verify_checksums` — planned
- [ ] **Study-metadata work stream** (architecture in [08_METADATA §1](../mfb-rdm-docs/08_METADATA.md), 2026-05-12). Order is roughly: gather → import → close-out. None blocks the first user-driven Phase B ingest.
  - [ ] **`gather_metadata.py`** (read-only utility) — given an acq_id (or project), join `/raw/<ACQ-ID>/metadata.json` with the corresponding `/projects/<proj>/metadata/<acq_id>.json` (and `study.json` / `biosamples.json`) on `acq_id` and emit a merged view (JSON or pretty-printed). The "single source of truth" for consumers (OMERO, future DB, analysis scripts) until indexing is built. Small (~40 lines); ship early.
  - [ ] **Excel → study-metadata importer** (researcher-facing). Reads a per-project `study.xlsx` with a defined sheet layout (study sheet + biosamples sheet + optional per-acquisition supplements sheet), validates against a schema, writes `/projects/<proj>/metadata/{study,biosamples,<acq_id>}.json`. Schema needs design; the Excel layout will live alongside the tool. This is what unblocks Users (researchers) to actually contribute REMBI study/biosample context.
  - [ ] **Project close-out tool** (Data Mgmt Lead procedure). Given a project ready for closure: (1) read `/projects/<proj>/metadata/`; (2) for each acq_id referenced, merge the study-level metadata into `/raw/<ACQ-ID>/metadata.json` under a `study:` block (additive, never overwriting acquisition-level fields); (3) if the project promoted to a publication, also stage a copy under `/publications/<pub-id>/`; (4) verify writes; (5) only then delete the project folder. Requires admin write access to `/raw/`. Has implications for the raw-immutability lockdown (§4.3) — that lockdown design must allow the Lead to perform these merges. Document the procedure (manual recipe first, scripted tool after).
  - [ ] Document the merge format in [08_METADATA](../mfb-rdm-docs/08_METADATA.md) — `metadata.json.study` block shape — once the Excel-importer schema settles.

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
- [ ] **The lockdown must preserve a Data-Mgmt-Lead write path** — the project close-out tool (§3.2) needs to merge study-level metadata into `/raw/<ACQ-ID>/metadata.json` post-lockdown. Either: (a) Lead has an admin account whose group ACL allows write on `/raw/` even when general users see it as read-only; or (b) Lead temporarily un-locks → writes → re-locks. Pick when implementing the lockdown.
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

> **Pickup context (read first if returning to this section cold):**
> - Round-5 candidate alternative to §4.6.B Cell Observer. Pick whichever has a sample dataset available first (see §0 Active Pass).
> - DICOM ingest already works for **collaborator XMRI** (HPIC + LIONS, 75 production rows ingested round-1/2). MRI Platform DICOM is **different source, same format** — expect different header conventions, different series structure (platform-reconstructed vs collaborator-archived).
> - Today's ingest skips DICOM full-mode metadata extraction (the `discovered.dicom_*` + `microscopy._raw_metadata`-equivalent block) — that's queued in §3.1 as **deferred**. Round-5 MRI is the natural moment to implement it, mirroring what we did for `.czi` in round-3 (`tools/ingest/czi_metadata.py`).
> - DICOM compress-on-ingest is also still queued in §3.1. The 75 production collaborator rows came in as already-zipped `.zip`/`.rar` from collaborators; for platform MRI we'll need to compress at ingest time (the source folders contain many `.dcm` instances).
> - Two MRI systems live on the platform (Bruker BioSpec 11.7T and 7T) — open question whether they need separate instrument codes or share `MRI`. See `equipment/mri-platform/` for the platform description.
> - **🔑 ACCESS IS THE BLOCKER, NOT CODE.** The MRI acquisition machine is NOT directly network-accessible the way the other instruments are — researchers pull data via FTP from the acq machine to their own workstations. Architectural options, recommended pacing (Option A: pull-from-FTP via our ingest first; Option B: on-machine agent later if needed), open questions for the platform manager, and a working email draft are captured in [`equipment/mri-platform/mri_data_access_strategy.md`](../equipment/mri-platform/mri_data_access_strategy.md). Read that doc before resuming MRI work. The code-side prerequisites (DICOM full-mode extractor + compress-on-ingest from §3.1) are independent of access negotiation — can be prototyped against the existing collaborator XMRI data while platform-access conversation is in flight.

**Prerequisites (need before starting):**
- [ ] **Ryan:** Obtain one sample MRI DICOM dataset from the MRI Platform (Irantzu's group). One acquisition's worth of `.dcm` files in their typical folder layout.
- [ ] Confirm DICOM is the output format (MOD-05).

**Round-5 execution:**
- [ ] Inspect file structure and headers — compare with collaborator DICOM (HPIC/LIONS reference).
- [ ] Audit embedded metadata — what header fields are populated? What differs from collaborator DICOM? (feeds §2.2)
- [ ] Implement DICOM full-mode metadata extraction (`tools/ingest/dicom_metadata.py`, mirrors `czi_metadata.py`): curated `discovered.dicom_*` fields + structured `dicom:` sidecar block + full pydicom-dump `_raw_metadata`.
- [ ] Implement compress-on-ingest for DICOM (`.zip` archive of the source `.dcm` collection, `file_count` from archive central directory per §3.1).
- [ ] Test full-mode ingest on one MRI case.
- [ ] Verify `metadata.json.dicom` captures MRI-specific fields.
- [ ] Resolve: do the two MRI systems need separate instrument codes? (§2.4)

**Documentation (during / after the pass):**
- [ ] `09_MODALITIES.md` MRI section — per-instrument `discovered.dicom_*` fields table.
- [ ] `08_METADATA.md` — update for `dicom:` sidecar block.
- [ ] `00_INDEX.md` — version history.

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

**4.6.B Cell Observer (`CELL`) — Round 5 (DONE 2026-05-15, quasi-production):**

> **Round-5 outcome (the short version):** 165 `.czi` acquisitions across 3 auto-created projects on the NAS, exercising **both ways of providing discoverable metadata** that the new YAML features enable. This is the canonical exhibit for showing the team how the same pipeline machinery handles different conventions by changing only the YAML — no code change.
>
> | Project | Acqs | Config | Approach exhibited |
> |---------|------|--------|--------------------|
> | PROJ-0006 `itziar-colageno` | 30 | `cell_observer_itziar_alphasma_TEST.yaml` | Filename-focused, side-effect (the `Itziar/**/*.czi` pattern caught the `colageno` experiment alongside `alphasma`) |
> | PROJ-0007 `itziar-alphasma` | 61 | `cell_observer_itziar_alphasma_TEST.yaml` | **Filename-focused** — 5-chunk filename carries `cell_line / experiment / magnification / condition / image_num`; path adds the same `cell_line` + `experiment` levels redundantly (collision-WARN exercised — see §3.1 done-item 2026-05-15) |
> | PROJ-0008 `itziar-colageno-permeabilizado` | 74 | `cell_observer_itziar_colageno_perm_TEST.yaml` | **Path-focused** — only 2-chunk filename (`condition_image_num`); the path levels (`researcher / cell_line / experiment`) supply the rest |
>
> Both TEST configs and the TEST notes in `registry_raw.csv` remain as-is by design — the whole quasi-production batch will be purged after the exhibition (see §0 banner). The exhibition-ready exhibit IS the contrast between the two configs.

**Pickup context (if returning cold):**
> - Cell Observer is a **separate physical instrument** from AxioScan 7 — different hardware (inverted epifluorescence vs. WSI scanner). Same vendor (Zeiss) and **same `.czi` format**, so `tools/ingest/czi_metadata.py` reused 1:1 — confirmed on the round-5 probe.
> - Operator workflow differs from AxioScan: data lives on the **instrument-local PC**, operator manually saves retained files to their own group-drive folder (variable per-operator path, no day-folder convention). See `equipment/cell-observer/cell_observer_data_handling_workflow_notes.md` for the full operator walkthrough.
> - Two effective modes of Cell Observer use: (a) **cell-assay / live-cell / plate-based** (sparse filenames, hierarchical folders by researcher / cell-line / experiment) — what round 5 shipped; (b) **animal/histology** (more AxioScan-like naming) — deferred (see below).
> - **Operators:** Both Ainhize Urkola Arsuaga and Marta operate the Cell Observer (and AxioScan); they're interchangeable for our purposes. Round 5 sample data came from Ainhize.
> - **The confocal (LSM 900) follows the same Cell Observer playbook**, so most of round-5's work transfers — see §4.6.C.

**Round-5 execution checklist:**
- [x] ~~Implement `path_parse` YAML feature~~ — done 2026-05-14, see §3.1.
- [x] ~~Implement `auto_create_project:` YAML block~~ — done 2026-05-14, see §3.1.
- [x] ~~Read-only probe with `tools/ingest/probe_czi.py` on Ainhize's sample `.czi`~~ — done; 21 curated `discovered.czi_*` fields populated as expected; `mosaic.tile_count` absent on non-tiled cells acquisitions (handled gracefully). MOD-07 confirmed.
- [x] ~~Create `tools/templates/instruments/cell_observer_cells.yaml`~~ — done. `path_parse: [researcher, cell_line, experiment]`, `filename_parse: [cell_line, experiment, magnification, condition, image_num]`, `sample_type: cells`, composite `sample_id: ${discovered.cell_line}_${discovered.condition}`, provisional `project_hint: ${discovered.researcher}-${discovered.experiment}` with the PROJ-05 warning prominent in comments. `auto_create_project` block with `owner: ${discovered.researcher}`.
- [x] ~~Author per-batch configs~~ — TWO configs landed (filename-focused + path-focused variants — see outcome table above).
- [x] ~~Real test ingest~~ — done 2026-05-14 and 2026-05-15. 165 acqs across 3 auto-created projects, all on the NAS in `J:\raw\MICROSCOPY\2025\` and `J:\projects\proj-itziar-*\`. Idempotency check passed; `.lnk` shortcuts created per project.
- [x] ~~Surface and fix collision behavior~~ — round-5 exposed that the same `discovered.<key>` can be populated by both `path_parse` and `filename_parse`; documented filename-wins behaviour and added the per-key WARN on mismatch. Tracked in §3.1.
- [ ] **User-driven Phase B re-ingest** (researcher self-runs the configs to validate the Quick Start docs) — deferred until after the team exhibition since the whole batch will be purged anyway. The exhibition itself is the Phase B substitute for round 5.
- [ ] **Physical `.lnk` double-click verification** (carried over from round 4) — user clicks a Cell Observer shortcut from `proj-itziar-alphasma\raw_linked\` and confirms it opens the canonical `.czi`. One-time UX confirmation.

**Documentation status:**
- [ ] `mfb-rdm-docs/09_MODALITIES.md` §1.2 (Cell Observer) — per-instrument `discovered.czi_*` fields table (mirror the AxioScan §1.1 table; note deviations from AxioScan such as absent mosaic.tile_count). Pending.
- [ ] `mfb-rdm-docs/11_OPERATIONS.md §3.2` Quick Start — refactor AxioScan-specific examples now that a second validated instrument exists. Pending.
- [ ] `mfb-rdm-docs/00_INDEX.md` — round-5 entry added 2026-05-18 (see version history).

**Deferred from this pass (queued for later):**
- [ ] **Animal/histology-mode Cell Observer template** — needs a real example folder of historical histology work (likely from a different researcher's older folder). The pipeline machinery is the same; only the YAML differs. Each historical batch / researcher convention probably needs its own per-batch config. Plan: one `cell_observer_histology.yaml` template once we have a representative example.
- [ ] **Historical Cell Observer histology backfill** — separate stream from going-forward cells-mode work. Operators used Cell Observer heavily for histology before AxioScan arrived; that data still needs ingest. Different researchers, different conventions per researcher / era. Use the same machinery, one per-batch YAML per historical batch.
- [ ] LSM 900 (§4.6.C) — should reuse most of the Cell Observer cells-mode template once validated; same instrument family, same data-handling model per the operator.

**4.6.C LSM 900 confocal (`LSM9`) — reuses 4.6.B Cell Observer template:**

> **Pickup context (read first if returning cold):**
> - LSM 900 is a Zeiss confocal microscope. Same vendor + same `.czi` format as Cell Observer and AxioScan, so `tools/ingest/czi_metadata.py` should reuse 1:1.
> - Per the operator walkthrough, LSM 900 follows the **same data-handling playbook as Cell Observer** — operator saves files manually to a group-drive folder, no day-folder convention, folder structure carries metadata. Expected source path: `K:\gjesus\Ainhize\CONFOCAL LSM 900\`.
> - Plan: reuse `cell_observer_cells.yaml` as the starting template; clone to `tools/templates/instruments/lsm900.yaml`, swap `instrument: LSM9`, adjust `path_parse` / `filename_parse` field names if Ainhize's confocal folder convention differs. Likely small delta.
> - **Blocked on:** Ainhize Urkola Arsuaga to provide a detailed example folder + filename convention. Once one real `.czi` arrives, this pass should be small (mirror round-5 §4.6.B closely).

**Prerequisites (need before starting):**
- [ ] **Ainhize:** Provide one detailed `.czi` example from the LSM 900, ideally with the typical folder layout intact. Expected location once provided: `K:\gjesus\Ainhize\CONFOCAL LSM 900\<researcher>\...`.
- [ ] **Ryan:** Copy locally for probing once Ainhize confirms the path.

**Execution (mirrors §4.6.B Cell Observer):**
- [ ] Read-only probe with `tools/ingest/probe_czi.py` — confirm similarity to Cell Observer / AxioScan (MOD-07 follow-up).
- [ ] Create `tools/templates/instruments/lsm900.yaml` (clone of `cell_observer_cells.yaml`, adjusted).
- [ ] Author the first per-batch config + dry-run + real test ingest (quasi-production).

**4.6.D Lightweight mode for microscopy:**
- [ ] Test `--lightweight` mode on one `.czi` file (sets `extended_metadata_present=N`, no sidecar)

### 4.7 Pass 4: Platform DICOM — Nuclear Imaging (`PET`, `SPECT`, `CT`)

> **Pickup context (read first if returning cold):**
> - Multimodal platform — PET, SPECT, CT, OI from Molecubes (γ/β/X-CUBES) + MILabs VECTor; may include hybrid PET/CT or PET/SPECT/CT sessions. Tests the multi-modality handling (a hybrid session should stay as one acquisition with `modalities_in_study` populated). Platform description: `equipment/nuclear-imaging/nuclearImaging_platform_description.md`.
> - Both DICOM and NIfTI exports are produced (per the platform description). Confirm output format(s) with the platform manager when we engage them.
> - **Blocked on:** Platform Manager **Unai** to answer one outstanding question (around the data naming convention) before we submit our data-workflow documentation + example to him. Until that round-trip closes, we can't formalize the ingest workflow proposal, and we don't have sample data to probe yet.
> - **Code-side prerequisite shared with §4.5 MRI:** the DICOM full-mode metadata extractor + compress-on-ingest (§3.1) is the same code path. Prototype it against the existing 75 collaborator XMRI acquisitions while waiting on Unai — it'll be ready when sample data lands.

**Prerequisites (need before starting):**
- [ ] **Ryan:** Resolve the open question with Unai (Platform Manager) on the naming convention; submit data-workflow documentation + example for his review once resolved.
- [ ] **Ryan:** Obtain sample Nuclear Imaging datasets (ideally one single-modality and one hybrid).
- [ ] Confirm output format(s) from the platform — DICOM, NIfTI, or both per acquisition? (MOD-05, Section 2.4).

**Execution (once unblocked):**
- [ ] Inspect file structure and headers — compare with MRI and collaborator DICOM.
- [ ] Audit embedded metadata (feeds 2.2).
- [ ] Test full-mode ingest on one case.
- [ ] Test hybrid handling — does a PET/CT session stay as one acquisition? Verify `modalities_in_study` field.

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
