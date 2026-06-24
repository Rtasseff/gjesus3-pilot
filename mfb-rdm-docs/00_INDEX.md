# MFB gjesus3 Research Data Management — Documentation Index

**System Purpose:** Research-facing working layer for MFB group imaging data in the 5-year active window — organised, searchable, directly viewable. Complements (does not replace) the platforms' own deep-archive of raw bytes. See [13_GJESUS3_ROLE](13_GJESUS3_ROLE.md) for the two-tier framing.
**Infrastructure:** QNAP TS-864eU NAS (6 × 20 TB, RAID 5, ~100 TB system / ~63 TB user-available after snapshot reservation)
**Status:** Pilot development
**Last Updated:** 2026-06-24 — **operator GUI rollout** (`gjesus3_ingest`: the microscopy GUI + a new simple **MRI page** `/mri`, frozen to a single Windows `.exe` deployed at `\\gjesus3\gjesus3\gjesus3-data\tools\` with two shortcuts + HTML guides; MRI source = **read-only SFTP pull** from `kenia`, `instrument_model` auto-derived from `ACQ_station`, staging auto-deleted, NAS-validated-before-pull — [10_TOOLS §5.2](10_TOOLS.md), Key Decisions). Prior: 2026-06-23 — **researcher Finder enhancements** (branch `feat/finder-mvp`, merged to `main` — built at the data office's request: auto-refresh of `registries/index.html` at the end of each successful ingest (non-fatal); expanded table columns incl. project `short_name` + owner; detail-panel File size + Project description with Copy-path buttons for the metadata/raw/project paths (metadata path → native Chrome/Edge JSON-tree view); `DEFAULT_LINK_BASE` corrected to the container UNC `\\GJESUS3\gjesus3\gjesus3-data`; `index.html` documented as a generated artifact — [06_REGISTRIES §1.2](06_REGISTRIES.md), [`tools/FINDER.md`](../tools/FINDER.md)). Prior: 2026-06-15 — **2026-06 code-review correction pass merged to `main`** (the reviewed HIGH/MEDIUM/LOW bug-fix set — extractor resume-safety + `--force`, NI/MRI copy collision-guards, registry-lock stale-break TOCTOU, pre-flight registry-header check, operator/parsing/atomic-write fixes; source branch retired to tag `archive/review-code-inspection-2026-06-12`; see CHANGELOG 2026-06-15) **+ anatomy auto-derive + back-fill (MRI + microscopy)** (auto-fill `anatomy.region` from the MRI scan name / the AxioScan sample-id organ code at ingest, + back-fill tools for already-ingested acqs; high-confidence literal terms only, null if doubt; operator runbook [`tools/ANATOMY_BACKFILL.md`](../tools/ANATOMY_BACKFILL.md); UBERON ids OLS-verified — 08_METADATA §4.6.4) **+ true-production restart** (2026-06-10: quasi-prod purged; fresh registry schema adds the `sample_organism` + `subject_id` + `anatomical_entity` Auto columns, projections of the enrichment blocks via `registry.build_row`) **+ the post-first-review correction pass** (registry lock + CSV-append safety, archive-rerun / crash-orphan / empty-folder fixes, dry-run-default-ON GUI, CELL/LSM9 recipes, the `os.link` diagnostic, doc front-doors) **+ the NI multi-animal work** (NI-LIVE-08: the junction-table contradiction fixed to a one-row-per-subject `registry_subjects.csv`; the AUTO column `subject_id` → packed **`subject_ids`** rename DONE 2026-06-12 — code + sandbox header + rename-aware migrator; the subjects-table writer + multi-animal list-packing still pending). **Full dated history → [CHANGELOG.md](../CHANGELOG.md).**
**Newcomer pointers:** [START_HERE.md](../START_HERE.md) (operators) · [GLOSSARY.md](../GLOSSARY.md) (terms) · [CHANGELOG.md](../CHANGELOG.md) (history).

---

## Quick Links

| Document | Purpose | Status |
|----------|---------|--------|
| [01_OVERVIEW](01_OVERVIEW.md) | System scope, constraints, and design rationale | ✅ Current |
| [02_INFRASTRUCTURE](02_INFRASTRUCTURE.md) | Hardware, access, risk assessment | ⚠️ Gaps identified |
| [03_RAW_STORAGE](03_RAW_STORAGE.md) | Raw data area specification | 🔶 Draft |
| [04_PUBLICATIONS](04_PUBLICATIONS.md) | Publication archive specification | 🔶 Draft |
| [05_PROJECTS](05_PROJECTS.md) | Project workspace specification | 🔶 Draft |
| [06_REGISTRIES](06_REGISTRIES.md) | Registry schemas and workflows | 🔶 Draft |
| [07_PROVENANCE](07_PROVENANCE.md) | Provenance logging specification | 🔶 Draft |
| [08_METADATA](08_METADATA.md) | Extended metadata (REMBI-based) | 🔶 Draft |
| [09_MODALITIES](09_MODALITIES.md) | Supported data types and instruments | ⚠️ Needs input |
| [10_TOOLS](10_TOOLS.md) | Scripts and automation | 🔶 Draft |
| [11_OPERATIONS](11_OPERATIONS.md) | Workflows, permissions, onboarding | 🔶 Draft / In use |
| [12_CURATED_DATASETS](12_CURATED_DATASETS.md) | Curated derived datasets (segmentation, etc.) | ❓ Under evaluation |
| [13_GJESUS3_ROLE](13_GJESUS3_ROLE.md) | What gjesus3 is and is not, relative to platform archives | 🔶 Draft (reframe 2026-05-20) |

**Legend:** ✅ Current | 🔶 Draft | ⚠️ Gaps identified | ❓ Under evaluation | 📋 Planned

---

## What This System Is

A **research-facing working layer** for MFB group imaging data — organised, searchable, directly viewable — covering the 5-year active window where most of a project's value lives. Specifically, gjesus3:

1. Registers raw acquisitions in a structured registry with rich JSON metadata sidecars
2. Provides project workspaces with shortcuts back to raw data + space for project-level derivatives (e.g. NIfTI generated from MR raw)
3. Maintains publication-ready data packages with full provenance
4. Supports traceability from published figures back to source data
5. Operates in two-tier complement with the platforms' own deep-archives — see [13_GJESUS3_ROLE](13_GJESUS3_ROLE.md)

## What This System Is NOT

- **Not the deep-time archive of every raw byte.** The instrument platforms (MRI, Nuclear Imaging, microscopy facilities) already keep raw originals in their own — admittedly awkward — archives. gjesus3 doesn't replicate or replace that role; the 1% of cases needing forensic access to original bytes falls back to those archives.
- **Not a primary working drive for heavy active analysis** — access is limited to specific hardwired on-site machines (not laptops), and RAID 5 performance is not optimised for high-volume read/write. Researchers analyse on their own workstations and check derivatives back into project workspaces.
- **Not a general file share** — structured storage with enforced conventions, not open dumping.
- **Not a backup solution** — RAID 5 protects against single-drive failure only; no offsite backup currently configured.

---

## Current Scope

### Confirmed Equipment (Initial Pilot)

**Microscopes** (direct instrument output to gjesus3):

| Instrument | Type | Primary Format | Status |
|------------|------|----------------|--------|
| Zeiss Axio Scan 7 (WSI) | Whole-slide imager | .czi | ✅ Confirmed |
| Zeiss Axio Observer (Cell Observer) | Inverted epifluorescence microscope | .czi | ✅ Confirmed |
| Zeiss LSM 900 | Confocal microscope | .czi | ✅ Confirmed |

**Institutional platforms** (reconstructed images to gjesus3; platforms archive true raw data):

| Platform | Instruments | Our "Raw" Data | Format | Status |
|----------|-------------|----------------|--------|--------|
| MRI Platform | Bruker BioSpec 11.7T and 7T | Reconstructed images | DICOM (TBC) | ✅ Confirmed |
| Nuclear Imaging Platform | Molecubes PET/SPECT/CT + MILabs VECTor PET/SPECT/CT/OI | Reconstructed images | DICOM, possibly NIfTI (TBC) | ✅ Confirmed |

> For detailed equipment specs, see [equipment/INDEX.md](../equipment/INDEX.md).

### Under Evaluation

| Modality | Instrument/Source | Notes |
|----------|-------------------|-------|
| Electron microscopy (SEM/TEM) | EM platform | Mainly nanomaterial characterization; need confirmation of use case fit |
| Curated datasets area | N/A | Permanent storage for derived assets (segmentation ground truth, training corpora); see [12_CURATED_DATASETS](12_CURATED_DATASETS.md) |

### Deferred / Out of Scope

| Item | Reason |
|------|--------|
| Platform-originated true raw data | Maintained by platforms (listmode, k-space, etc.); we store reconstructed/exported files only |
| Non-imaging data | Current focus is imaging; may expand later |

---

## Key Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Storage areas | Raw + Publications + Projects (+ staging) | Curated datasets under evaluation |
| Registry location | Top-level centralized | Simpler management; single source of truth |
| Raw structure | **Ecosystem → Year → Month → Acquisition** | Organized by data ecosystem (MICROSCOPY, DICOM, EM) — stable, maps to tooling, avoids folder proliferation from new instruments or hybrids |
| Instrument identity | In ACQ-ID and registry, not folder path | Keeps folder structure stable; instrument detail in metadata |
| Hybrid instruments | Keep together as one acquisition | PET/CT etc. stored as single DICOM Study; modalities recorded in registry |
| One primary file rule | Yes (no exceptions — DICOM stored as archive) | Simplifies registry; archive format eliminates the bundle exception |
| DICOM archive format | Compressed archives (.zip/.tar.gz) | Millions of small .dcm files unworkable on SMB; archive is the single primary file |
| Primary staging location | Fast local/network storage (off-NAS) | NAS SMB too slow for extraction/compression; NAS staging/ retained as secondary dump |
| Two ingest modes | Full (default) + Lightweight | Full mode extracts metadata before archiving; lightweight for constrained environments |
| Metadata extraction at ingest | Integrated into full-mode ingest | Not a separate post-hoc tool; extraction happens before DICOM compression |
| Ingest config schema | Three-block YAML: `ingest:` / `auto_discover:` / `registry:` | Per-column registry mapping is explicit in YAML (literal \| `discovered.<field>` \| `${...}` interp \| `NA`); replaces the prior `defaults:` block + Python `SPECIAL_FIELDS`. Configs live under git in [`tools/configs/`](../tools/configs/); template at [`tools/templates/ingest_template.yaml`](../tools/templates/ingest_template.yaml). See [10_TOOLS §2.1](10_TOOLS.md). |
| Project link method | **NTFS/SMB hard links** (since 2026-06-02; supersedes Windows `.lnk` shortcuts) | Project copy is a real file identical to raw — same inode, zero extra storage, shares raw's ACL (read-only carries through). Folder-primary `.data` → real folder of per-file hard links. Drives adoption (looks like a normal file). `.lnk` retained as the porting seam for cross-volume / non-Windows cases. See [10_TOOLS §2.1.1](10_TOOLS.md#211-project-linking--hard-links-current-over-lnk-shortcuts) |
| Provenance location | Per-publication/project folder | Local to context; enables independent archiving |
| Extended metadata | REMBI-based subset | Community standard; pruned to essential fields |
| **Metadata-location split** (DECIDED 2026-05-12) | Acquisition-level metadata (auto + Operator at ingest) lives in `/raw/<ACQ-ID>/metadata.json` (immutable). Study-level metadata (researcher-supplied: aim, biosample context, experimental groups) lives in `/projects/<proj>/metadata/` (mutable by project owners during the project's life). | Aligns with REMBI's Study/Biosample/Acquisition hierarchy; keeps `/raw/` strictly read-only post-deposit without blocking researcher metadata work; isolates the ephemeral working-space writes from the permanent archive. Requires project close-out to preserve study metadata into `/raw/` before project deletion. See [08_METADATA §1](08_METADATA.md), [05_PROJECTS §4.x](05_PROJECTS.md), [11_OPERATIONS §2.1](11_OPERATIONS.md). |
| **User role** (DECIDED 2026-05-12) | Fourth role added alongside Owner / Data Mgmt Lead / Operator. Researchers are Users — read-only on `/raw/`, read-write on their own `/projects/` (including the `metadata/` subfolder). Operators (technicians) deposit data and never write to `/raw/` after their ingest finishes. | Distinguishes "who brings data in" from "who works with data after". Folder-level permissions stay clean (no file-level ACLs needed). See [11_OPERATIONS §1.1 + §2.1](11_OPERATIONS.md). |
| Subject/Sample identity (DRAFT, refines REG-01, 2026-06-03) | Model **Subject** (animal) and **Sample** (specimen) as distinct entities, each with its own id. `subject.facility_animal_id` = the facility canonical animal id `<animal_code>-AE-biomaGUNE-<NNNN>` **reused verbatim**; `sample_id` = the subject id for in-vivo (`organism`), or a within-subject specimen label for `tissue`; organ → structured `anatomical_entity`. **Option B:** in docs + sidecar now; registry `subject_id`/`anatomical_entity` columns deferred to the true-prod restart. | Grounded in FAIR/ISA/REMBI/BIDS/XNAT (all separate subject from sample; BIDS `participant_id` vs `sample_id`; FAIR "reuse existing identifiers, don't overload IDs with meaning"). Reusing the facility id makes it the DB join key for free. Supersedes the earlier bare `<short_project>_<short_sample>` composite. Open (REG-01/META-08) — a Data Office decision (user input welcome; this project has no PI sign-off gate). See [06_REGISTRIES §2.3](06_REGISTRIES.md). |
| Sample type vocabulary (DRAFT) | 5-value controlled vocab: `tissue` / `organism` / `cells` / `material` / `phantom` | REMBI-aligned: `sample_type` is the *kind of biological material*, not the species or anatomy. Covers everything in current scope and the foreseeable future. AxioScan template pre-fills `tissue`. Status open (REG-07) — a Data Office decision (user input welcome; no PI sign-off gate). Species and anatomy columns are queued as future split (`tasks/tasks.md` §3.1). See [06_REGISTRIES §2.4](06_REGISTRIES.md). |
| **Preclinical subject metadata** (DRAFT spec, DECIDED required fields, 2026-05-29; extended 2026-06-02) | New top-level `subject:` block in `metadata.json` for acquisitions with `sample_type ∈ {organism, tissue}`. **Required (DECIDED):** species / strain / sex / **date_of_birth** → derived age_at_acquisition (computed = acq_datetime − DOB) — universal preclinical reporting standards (ARRIVE 2.0, EU Directive 2010/63, NIH Sex-As-Biological-Variable). **Subject id:** `facility_animal_id` = canonical `<animal_code>-AE-biomaGUNE-<NNNN>` reused verbatim (see identity model §2.3). **Optional:** genotype / weight_at_acquisition_g / cohort_id / **procedures** (STRUCTURED `[{type,date}]` from the DB controlled vocab — not free text; META-07 retired) / `source:` provenance tag. **Source:** animal-facility-DB (`animal_facility` schema, **explored 2026-06-02**) > study-level YAML > instrument auto-extracts. **Required-eventually, not at-ingest:** an ingest-time DB miss / no-credentials WARNs (doesn't fail), writes `source: "pending-db"`, and queues to `registries/pending_subject_metadata.csv` for a superuser-run retro-update into `/raw/` (§4.4.6). Sidecar holds a frozen snapshot at ingest, refreshed at project close-out. | Highest-leverage metadata investment for preclinical data: turns a `.dcm` blob from "some MRI of some mouse" into a searchable, reusable, publishable acquisition. DOB makes age computed+verifiable; deferred-recovery keeps live ingests from failing when the DB lags acquisition. See [08_METADATA §4.4](08_METADATA.md), [09_MODALITIES](09_MODALITIES.md) cross-modality note, [13_GJESUS3_ROLE §5.6](13_GJESUS3_ROLE.md). |
| **Non-blocking metadata model** (DECIDED 2026-06-03) | The enrichment blocks `subject:`/`condition:`/`anatomy:` **never block ingest** ([08_METADATA §4.7](08_METADATA.md)). `is_control` + `is_whole_body` are **tri-state** (`true`/`false`/`null=unknown`), **highly-recommended not required** — writer WARNs if `null`, never refuses. Unknowns written as explicit sentinels. Enrichment is **set once per batch/session and propagates** (never per-scan); best-effort auto first (subject from DB, disease_model from project name, anatomy from hint); gaps tracked + bulk-filled later. | A hard-block punished the two cases gjesus3 most needs — archive data (nobody left to say control/whole-body) and the realistic MRI operator (barely supplies a folder name). "Data + a guess beats no data." Reverses the earlier DECIDED-required checks; supersedes META-06. |
| **Preclinical disease-state / control metadata** (DRAFT 2026-05-29; non-blocking 2026-06-03) | Top-level `condition:` block, sister to `subject:`, for `sample_type ∈ {organism, tissue}`. **Highly recommended (non-blocking):** `is_control` tri-state `true`/`false`/`null` (WARN if null, never refuses) + `disease_model` + `disease_state` (auto-seed from DB `projects.name`) + optional `control_type`/`treatment`/`timepoint_days`/`study_arm`. **Per-acquisition, set once per batch/session.** | Closes the "all healthy controls" / "all disease-X cases" query gap. `is_control == true`/`false` is the primary cohort filter; `null` is a tracked gap. See [08_METADATA §4.5 + §4.7](08_METADATA.md), [09_MODALITIES](09_MODALITIES.md), [13_GJESUS3_ROLE §5.6](13_GJESUS3_ROLE.md). |
| **Anatomical coverage** (`anatomy:` block, DRAFT 2026-06-03; non-blocking) | Top-level `anatomy:` block for in-vivo scans (`sample_type = organism`, NI/MRI). **Highly recommended (non-blocking):** `is_whole_body` tri-state `true`/`false`/`null` — the dead-simple full-body-vs-ROI flag (WARN if null) + UBERON-coded `region` when not whole-body + optional `additional_regions`/`auto_hint`. **Ontology = UBERON** (cross-species). **Operator-entered** — not auto-derivable (no animal-DB field; DICOM `BodyPartExamined` empty; only weak protocol/FOV/bed-range hints → optional auto-hint). | Closes the "whole-body or region of interest?" query gap with a boolean mirroring `condition.is_control`. UBERON keeps it queryable across Mouse/Rat + harmonizes with the tissue `anatomical_entity`. See [08_METADATA §4.6 + §4.7](08_METADATA.md), [09_MODALITIES](09_MODALITIES.md). |
| `path_parse` YAML feature (DECIDED 2026-05-14) | Optional `auto_discover.path_parse:` block — symmetric to `filename_parse`. Names the path levels between `staging_dir` and the file; each becomes `discovered.<name>` for use in `registry:` and `auto_create_project:`. Level labels are free-form. | Needed for instruments where folder structure carries more metadata than the filename (Cell Observer, LSM 900). Same WARN-on-mismatch semantics as `filename_parse`. See [10_TOOLS §2.1.3](10_TOOLS.md). |
| `auto_create_project:` block (DECIDED 2026-05-14) | Optional top-level YAML block, peer to `auto_discover:` / `registry:`. Supplies `owner` / `description` / `notes` for projects auto-created at ingest. Resolver-evaluated (literal \| `discovered.<x>` \| `${...}` \| `NA`). **First-write-wins:** read only on initial project creation; subsequent ingests ignore it. Empty values WARN and continue. | Lets the operator-acquires-for-researcher pattern (Cell Observer, LSM 900) auto-populate the actual data User as project owner instead of conflating with the Operator. Applies generically to any ingest, not just Cell Observer. See [10_TOOLS §2.1.4](10_TOOLS.md), [05_PROJECTS §7+§10](05_PROJECTS.md), [06_REGISTRIES §4.2](06_REGISTRIES.md). |
| **Operator GUI — `gjesus3_ingest`** (DECIDED, shipped 2026-06-24) | ONE Flask app, two pages over the shared validated pipeline: microscopy `/` (recipes/builder) + a deliberately-simple MRI `/mri` (pull-from-scanner → preview → ingest, no recipes). Frozen to a single Windows `.exe` (PyInstaller; `paramiko` hidden-import + bundled `ftp_mirror.py`) and deployed to `\\gjesus3\gjesus3\gjesus3-data\tools\` with two shortcuts (`MRI Ingest` = exe `--mri`) + HTML guides. **MRI source = SFTP pull, READ-ONLY** (only `listdir/stat/get` against `kenia`; no write path — audited); creds from `~/.ssh/gjesus3_mri.cred` (per-machine); staging to `<NAS>/staging` is invisible + auto-deleted after a clean ingest; `instrument_model` auto-derived from `acqp ACQ_station`; NAS validated before pull; link-collision + overwrite warnings; default-on Dicomifier regen (graceful). | Non-technical adoption: a one-click tool that does the right thing with the fewest choices. Reuses the proven pipeline (no reimplementation). Read-only SFTP guarantees the acquisition console is never touched. See [10_TOOLS §5.2](10_TOOLS.md), [09_MODALITIES §1.4](09_MODALITIES.md) (`mri_scanner_model`), `tools/operator/gui/README.md`. |

---

## Key Gaps / Open Questions

### Infrastructure (see [02_INFRASTRUCTURE](02_INFRASTRUCTURE.md))
- [ ] Backup strategy undefined — RAID 5 + daily snapshots, but no offsite backup
- [ ] Access limited to specific hardwired on-site machines (instruments + some workstations); laptops excluded — workable but inconvenient
- [x] ~~Snapshot capability~~ — confirmed active (daily snapshots running); retention policy and restore procedure still needed
- [x] ~~Filesystem type confirmation needed — affects linking method options~~ — **Resolved:** project links are **NTFS/SMB hard links** (since 2026-06-02; `.lnk` was the original pilot choice). Hard links were verified working on the QNAP SMB share, so the filesystem question is moot (see [10_TOOLS §2.1.1](10_TOOLS.md#211-project-linking--hard-links-current-over-lnk-shortcuts)).

### Raw Storage (see [03_RAW_STORAGE](03_RAW_STORAGE.md))
- [x] ~~Organization by instrument vs. abstract modality~~ — **Resolved:** ecosystem-based (MICROSCOPY, DICOM, EM)
- [x] ~~Generic instrument codes for collaborator / external data~~ — **Resolved:** X-prefix codes (XMRI, XCT, XPET, XSPECT)

### Publications (see [04_PUBLICATIONS](04_PUBLICATIONS.md))
- [x] ~~Raw data linking method undecided~~ — **Resolved:** **NTFS/SMB hard links** (2026-06-02; superseded the original Windows `.lnk` choice; see [10_TOOLS §2.1.1](10_TOOLS.md#211-project-linking--hard-links-current-over-lnk-shortcuts))

### Curated Datasets (see [12_CURATED_DATASETS](12_CURATED_DATASETS.md))
- [ ] Inclusion in pilot vs. defer to Phase 2
- [ ] Label format standardization per ecosystem
- [ ] Curator role assignments

### Modalities (see [09_MODALITIES](09_MODALITIES.md))
- [ ] SEM/TEM inclusion decision pending
- [ ] Data type sign-up sheet incomplete — need volunteer owners per type
- [ ] Embedded metadata audit incomplete — which instruments embed what?

### Metadata (see [08_METADATA](08_METADATA.md))
- [x] ~~Per-column registry field mapping (user-supplied)~~ — **Resolved (2026-05-06):** explicit YAML `registry:` block per config; `metadata.json` sidecar generator implemented; see [10_TOOLS §2.1](10_TOOLS.md) and [08_METADATA §4.3](08_METADATA.md).
- [ ] Auto-extraction of embedded metadata (DICOM headers, .czi internals) into the `discovered` namespace — sidecar framework is ready (`tools/ingest/probe_czi.py` for `.czi`); extraction implementation deferred.
- [ ] REMBI field selection not finalized — user voting incomplete
- [ ] ISA-TAB-Nano applicability for nanomaterial imaging unclear
- [x] ~~**Preclinical `subject:` block not yet auto-populated**~~ — **Phase 3 writer SHIPPED 2026-06-03** (non-blocking): `tools/ingest/enrichment.py` auto-populates `subject:` from the animal-facility DB (`tools/animal_db.py`) at ingest Step 8.4, with the §4.4.6 deferred-recovery pending list (`registries/pending_subject_metadata.csv`) + superuser `tools/recover_subject_metadata.py` for DB-miss / no-credentials. Spec in [08_METADATA §4.4](08_METADATA.md). **Still deferred:** the registry `subject_id` column + backfill of the existing 365+ acqs → true-production restart (`tasks/tasks.md §3.2` Phase 4).
- [x] ~~**`anatomy:` block writer not yet implemented**~~ — **Phase 3 writer SHIPPED 2026-06-03** (non-blocking): `tools/ingest/enrichment.py` writes the `anatomy:` block for `sample_type = organism` at ingest Step 8.4; `is_whole_body` highly-recommended tri-state (§4.7) + UBERON `region`, operator-entered via the top-level `anatomy:` YAML block (`mri_bruker` + `molecubes_ni` templates). Spec in [08_METADATA §4.6](08_METADATA.md). **Still deferred:** the registry `anatomical_entity` column + backfill of existing organism acqs → true-production restart (`tasks/tasks.md §3.2` Phase 4). New META-09.
- [x] ~~**Preclinical `condition:` block writer not yet implemented**~~ — **Phase 3 writer SHIPPED 2026-06-03** (non-blocking): `tools/ingest/enrichment.py` writes the `condition:` block for `sample_type ∈ {organism, tissue}` at ingest Step 8.4; `is_control` highly-recommended tri-state (§4.7) + `disease_model` + `disease_state`, operator-entered via the top-level `condition:` YAML block (`mri_bruker` / `molecubes_ni` / `axioscan7` templates), `disease_model` auto-seeds from DB `projects.name`. Spec in [08_METADATA §4.5](08_METADATA.md). **Still deferred:** backfill of existing acqs → true-production restart (`tasks/tasks.md §3.2` Phase 4).

### Tools (see [10_TOOLS](10_TOOLS.md))
- [x] ~~Ingest script requirements defined but not implemented~~ — **Resolved:** `ingest_raw.py` implemented in `tools/`
- [ ] Where scripts will run (designated workstation vs. user machines) undecided
- [ ] Script versioning/distribution approach undefined

### Operations (see [11_OPERATIONS](11_OPERATIONS.md))
- [ ] Who can promote staging → raw (intake roles) — partial resolution via the User / Operator / Data Mgmt Lead role split (DECIDED 2026-05-12); concrete per-instrument "who" assignments still open.
- [x] ~~**NAS group permissions**~~ — ✅ APPLIED 2026-06-02 on `J:\gjesus3-data\`. IT will not assist / won't create custom groups, so the planned `pilot-users`/`pilot-operators` are abandoned; model uses the existing `CICBIOMAGUNE\GJesus` group (Read baseline) + per-operator/superuser grants (operators write-but-not-modify on `raw\`, Modify on `registries\`; group Modify on projects/publications/staging; superusers Full; grant-only, never DENY). One verify pending: operator create-but-not-modify translation over SMB (testable only with a real operator account). Spec: [11_OPERATIONS §2.1.1 + §2.3](11_OPERATIONS.md); `tasks/tasks.md §4.3 + §6`.
- [x] ~~Quick Start guide not written~~ — **Resolved (2026-05-12):** researcher-facing daily flow in [11_OPERATIONS §3.2](11_OPERATIONS.md); CLI reference with flags + config cheat-sheet at [`tools/INGEST_CLI.md`](../tools/INGEST_CLI.md)
- [ ] Pilot review cadence not scheduled — effectively continuous via the per-round ingest cycle; formal cadence on hold until post-exhibition true-production restart.

### Projects (see [05_PROJECTS](05_PROJECTS.md))
- [ ] **Project naming convention requires group consensus** (PROJ-05). Project `short_name` should map to a durable, meaning-bearing unit (funded project name, animal-project approval ID, or explicit internal name). Experiments ≠ projects. Provisional patterns now in use: `ae-biomegune-NNNN` (AxioScan, reasonable interim) and `${researcher}-${experiment}` (Cell Observer cells-mode, stopgap only). Project-lead users must converge on a real convention before the pilot scales out. See [05_PROJECTS §9](05_PROJECTS.md).

---

## How to Use This Documentation

**For specific topics:** Navigate directly to the relevant module document.

**For stakeholder discussions:** Share only the relevant module(s) rather than the full specification.

**For gap tracking:** Each module has its own "Open Questions" section; this index summarizes cross-cutting gaps.

**For iteration:** Update individual modules as decisions are made; update this index to reflect status changes.

---

## Document Conventions

### Status Markers

Throughout these documents:

> **✅ DECIDED:** Finalized decision — implement as specified

> **🔶 DRAFT:** Proposed approach — feedback welcome, may change

> **⚠️ GAP:** Information or decision needed — cannot proceed without resolution

> **❓ EVALUATING:** Under active consideration — may be included, deferred, or dropped

### Cross-References

Documents reference each other by filename: `(see [06_REGISTRIES](06_REGISTRIES.md))`.

### Feedback Requests

Explicit calls for input are marked:

> **📣 INPUT NEEDED:** *[specific question or request]*

---

## Version History

The full dated history now lives in the single repo changelog — see [CHANGELOG.md](../CHANGELOG.md). The numbered docs in this folder carry the current state; CHANGELOG.md carries the narrative of how we got here.
