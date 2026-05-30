# MFB gjesus3 Research Data Management — Documentation Index

**System Purpose:** Research-facing working layer for MFB group imaging data in the 5-year active window — organised, searchable, directly viewable. Complements (does not replace) the platforms' own deep-archive of raw bytes. See [13_GJESUS3_ROLE](13_GJESUS3_ROLE.md) for the two-tier framing.
**Infrastructure:** QNAP TS-864eU NAS (6 × 20 TB, RAID 5, ~100 TB system / ~63 TB user-available after snapshot reservation)
**Status:** Pilot development
**Last Updated:** 2026-05-29 (Preclinical subject metadata: new `subject:` block spec in the sidecar — 4 required fields DECIDED, optional fields DRAFT, animal-facility-DB integration queued)

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
| [11_OPERATIONS](11_OPERATIONS.md) | Workflows, permissions, onboarding | 📋 Planned |
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
| Project link method | **Windows `.lnk` shell shortcuts (Windows-first, pilot-specific)** | MFB user base is on Windows; WSL→SMB symlink path didn't work and SSH-into-NAS was blocked. **Deliberately not a default for future RDM deployments** — porting seam documented in [10_TOOLS §2.1.1](10_TOOLS.md#211-project-linking--windows-first-design-decision) |
| Provenance location | Per-publication/project folder | Local to context; enables independent archiving |
| Extended metadata | REMBI-based subset | Community standard; pruned to essential fields |
| **Metadata-location split** (DECIDED 2026-05-12) | Acquisition-level metadata (auto + Operator at ingest) lives in `/raw/<ACQ-ID>/metadata.json` (immutable). Study-level metadata (researcher-supplied: aim, biosample context, experimental groups) lives in `/projects/<proj>/metadata/` (mutable by project owners during the project's life). | Aligns with REMBI's Study/Biosample/Acquisition hierarchy; keeps `/raw/` strictly read-only post-deposit without blocking researcher metadata work; isolates the ephemeral working-space writes from the permanent archive. Requires project close-out to preserve study metadata into `/raw/` before project deletion. See [08_METADATA §1](08_METADATA.md), [05_PROJECTS §4.x](05_PROJECTS.md), [11_OPERATIONS §2.1](11_OPERATIONS.md). |
| **User role** (DECIDED 2026-05-12) | Fourth role added alongside Owner / Data Mgmt Lead / Operator. Researchers are Users — read-only on `/raw/`, read-write on their own `/projects/` (including the `metadata/` subfolder). Operators (technicians) deposit data and never write to `/raw/` after their ingest finishes. | Distinguishes "who brings data in" from "who works with data after". Folder-level permissions stay clean (no file-level ACLs needed). See [11_OPERATIONS §1.1 + §2.1](11_OPERATIONS.md). |
| Sample ID format (DRAFT) | Composite `<short_project>_<short_sample>` (e.g. `0525_ID26H`) | Short sample IDs are not unique on their own (reused across projects); composite makes them globally unique within `registry_raw.csv`. Applied via YAML `${...}` interpolation — no code change. Status remains open (REG-01) pending PI sign-off. See [06_REGISTRIES §2.3](06_REGISTRIES.md). |
| Sample type vocabulary (DRAFT) | 5-value controlled vocab: `tissue` / `organism` / `cells` / `material` / `phantom` | REMBI-aligned: `sample_type` is the *kind of biological material*, not the species or anatomy. Covers everything in current scope and the foreseeable future. AxioScan template pre-fills `tissue`. Status open (REG-07) pending PI sign-off. Species and anatomy columns are queued as future split (`tasks/tasks.md` §3.1). See [06_REGISTRIES §2.4](06_REGISTRIES.md). |
| **Preclinical subject metadata** (DRAFT spec, DECIDED required fields, 2026-05-29) | New top-level `subject:` block in `metadata.json` for acquisitions with `sample_type ∈ {organism, tissue}`. **Required (DECIDED):** species / strain / sex / age_at_acquisition — universal preclinical reporting standards (ARRIVE 2.0, EU Directive 2010/63, NIH Sex-As-Biological-Variable). **Optional (DRAFT):** genotype / weight_at_acquisition_g / facility_animal_id / cohort_id / `source:` provenance tag — DRAFT pending animal-facility-DB integration. **Source hierarchy:** animal-facility-DB > study-level YAML at `/projects/<proj>/metadata/subjects.yaml` > instrument auto-extracts. Sidecar holds a frozen snapshot at ingest, refreshed at project close-out. | Highest-leverage metadata investment for preclinical data: turns a `.dcm` blob from "some MRI of some mouse" into a searchable, reusable, publishable acquisition. Captures at ingest rather than from researcher notebooks. Doc spec lands ahead of code; animal-DB integration (`tasks/tasks.md §3.2`) is the bridge to auto-population. See [08_METADATA §4.4](08_METADATA.md), [09_MODALITIES](09_MODALITIES.md) cross-modality note, [13_GJESUS3_ROLE §5.6](13_GJESUS3_ROLE.md). |
| `path_parse` YAML feature (DECIDED 2026-05-14) | Optional `auto_discover.path_parse:` block — symmetric to `filename_parse`. Names the path levels between `staging_dir` and the file; each becomes `discovered.<name>` for use in `registry:` and `auto_create_project:`. Level labels are free-form. | Needed for instruments where folder structure carries more metadata than the filename (Cell Observer, LSM 900). Same WARN-on-mismatch semantics as `filename_parse`. See [10_TOOLS §2.1.3](10_TOOLS.md). |
| `auto_create_project:` block (DECIDED 2026-05-14) | Optional top-level YAML block, peer to `auto_discover:` / `registry:`. Supplies `owner` / `description` / `notes` for projects auto-created at ingest. Resolver-evaluated (literal \| `discovered.<x>` \| `${...}` \| `NA`). **First-write-wins:** read only on initial project creation; subsequent ingests ignore it. Empty values WARN and continue. | Lets the operator-acquires-for-researcher pattern (Cell Observer, LSM 900) auto-populate the actual data User as project owner instead of conflating with the Operator. Applies generically to any ingest, not just Cell Observer. See [10_TOOLS §2.1.4](10_TOOLS.md), [05_PROJECTS §7+§10](05_PROJECTS.md), [06_REGISTRIES §4.2](06_REGISTRIES.md). |

---

## Key Gaps / Open Questions

### Infrastructure (see [02_INFRASTRUCTURE](02_INFRASTRUCTURE.md))
- [ ] Backup strategy undefined — RAID 5 + daily snapshots, but no offsite backup
- [ ] Access limited to specific hardwired on-site machines (instruments + some workstations); laptops excluded — workable but inconvenient
- [x] ~~Snapshot capability~~ — confirmed active (daily snapshots running); retention policy and restore procedure still needed
- [x] ~~Filesystem type confirmation needed — affects linking method options~~ — **Resolved by chosen approach:** Windows `.lnk` shortcuts sidestep the filesystem question for the pilot (see [10_TOOLS §2.1.1](10_TOOLS.md#211-project-linking--windows-first-design-decision)). Filesystem type still unconfirmed but no longer blocking.

### Raw Storage (see [03_RAW_STORAGE](03_RAW_STORAGE.md))
- [x] ~~Organization by instrument vs. abstract modality~~ — **Resolved:** ecosystem-based (MICROSCOPY, DICOM, EM)
- [x] ~~Generic instrument codes for collaborator / external data~~ — **Resolved:** X-prefix codes (XMRI, XCT, XPET, XSPECT)

### Publications (see [04_PUBLICATIONS](04_PUBLICATIONS.md))
- [x] ~~Raw data linking method undecided~~ — **Resolved:** Windows `.lnk` shortcuts (pilot-specific Windows-first choice; see [10_TOOLS §2.1.1](10_TOOLS.md#211-project-linking--windows-first-design-decision))

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
- [ ] **Preclinical `subject:` block not yet auto-populated** (DRAFT 2026-05-29) — spec landed in [08_METADATA §4.4](08_METADATA.md); writer + animal-facility-DB integration are 4-phase work tracked in `tasks/tasks.md §3.2`. Phase 1 (DB API scoping) blocked on IT for programmatic database access.

### Tools (see [10_TOOLS](10_TOOLS.md))
- [x] ~~Ingest script requirements defined but not implemented~~ — **Resolved:** `ingest_raw.py` implemented in `tools/`
- [ ] Where scripts will run (designated workstation vs. user machines) undecided
- [ ] Script versioning/distribution approach undefined

### Operations (see [11_OPERATIONS](11_OPERATIONS.md))
- [ ] Who can promote staging → raw (intake roles)
- [ ] Permissions model details
- [x] ~~Quick Start guide not written~~ — **Resolved (2026-05-12):** researcher-facing daily flow in [11_OPERATIONS §3.2](11_OPERATIONS.md); CLI reference with flags + config cheat-sheet at [`tools/INGEST_CLI.md`](../tools/INGEST_CLI.md)
- [ ] Pilot review cadence not scheduled

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

| Date | Author | Changes |
|------|--------|---------|
| 2026-05-29 | R. Tasseff | **Preclinical subject metadata — DRAFT spec + DECIDED required fields.** New top-level `subject:` block in the `metadata.json` sidecar for acquisitions with `sample_type ∈ {organism, tissue}`. **Four required fields DECIDED** (species / strain / sex / age_at_acquisition) — universal preclinical reporting standards (ARRIVE 2.0, EU Directive 2010/63/EU, NIH Sex-As-Biological-Variable). **Optional fields + `source:` provenance tag DRAFT** until the animal-facility-DB integration locks the exact field names. **Trigger:** always required for internal MRI + Nuclear Imaging (sample is always an organism); required for microscopy when the sample is animal-derived (the typical case). **Source hierarchy:** animal-facility-DB > study-level YAML at `/projects/<proj>/metadata/subjects.yaml` > instrument auto-extracts (Bruker `SUBJECT_*` / Molecubes `protocol.txt`). Sidecar holds a frozen snapshot at ingest time, refreshed at project close-out before the project folder is deleted. **Why now:** highest-leverage metadata investment for preclinical data on gjesus3 — without species/strain/sex/age an acquisition is significantly less valuable for publication / reuse / cross-cohort analysis. Capturing at ingest beats recovering from notebooks. **Docs updated:** `08_METADATA §4.4` (new schema subsection — required-fields list, source hierarchy, ARRIVE/EU/NIH rationale, status table), `09_MODALITIES` (new cross-modality requirement note above §1 + per-instrument "Subject metadata" attribute rows added to §1.1/§1.2/§1.3 conditional and §1.4/§1.5 always-required), `06_REGISTRIES §2.4` (linked-requirement callout cross-referencing 08_METADATA §4.4), `13_GJESUS3_ROLE §5.6` (subject metadata added to "what we keep on gjesus3" table + new paragraph framing subject metadata as a reliability axis independent of platform archive trust). **New work stream in `tasks/tasks.md §3.2`:** 4-phase animal-facility-DB integration — Phase 1 scope DB API (blocked on IT), Phase 2 write `tools/animal_db.py` fetcher, Phase 3 wire into ingest via `auto_discover.subject_from_db:` flag, Phase 4 backfill existing 97 MRI + 84 NI + animal-derived microscopy acqs via idempotent re-ingest. Code implementation deferred — spec lands ahead of writer per the doc-first design model. |
| 2026-05-27 | R. Tasseff | **Round-6 v2 — internal MRI redo (mirror NI v2.1 conventions).** The round-6 v1 MRI ingest (2026-05-22, 97 acqs) had three structural problems matching NI v1's: (a) JCAMP-DX aux files (acqp/method/visu_pars/subject/fid/pulseprogram/...) copied to disk under `acquisition_aux/` — should be parsed-only in the sidecar; (b) per-recon non-DICOM (2dseq/visu_pars/reco) copied to disk under `reconstructions/pdata_<idx>/` — same issue; (c) per-frame DICOMs buried at `reconstructions/pdata_<idx>/dicom/MRIm<NN>.dcm` — should be flat under a `<ACQ-ID>.data/` subfolder mirroring the microscopy `<ACQ-ID>.czi` and NI `<ACQ-ID>.data/` conventions. Also discovered: the v1 default `reconstructions: [3]` silently dropped image data for any exam without a pdata/3 (most of the 97-acq cohort; verified `ACQ-20251016-MRI-001` at 872 KB = aux files only, NO recons kept). **Fix:** full purge of 97 MRI acqs + new `copy_mri_paravision` selective-copy function in `tools/ingest_raw.py` (same shape as `copy_ni_acquisition`); `paravision_metadata.py` extractor refactored to emit per-DICOM `dicoms[]` lists under each recon (`dst_basename` `recon<idx>_frame<NN>.dcm`, `src_relpath`, curated `headers` with `StudyInstanceUID`/`SeriesInstanceUID`/`SOPInstanceUID` first + MRI-specific tags `MagneticFieldStrength`/`EchoTime`/`RepetitionTime`/`FlipAngle`/`ScanningSequence`/`SequenceVariant`). Template default `reconstructions:` changed from `[3]` to `all` (DICOMs are tiny under the new slim layout). New `copy_strategy: mri_paravision_v2` selects between the legacy `paravision_exam` and the new path. Registry's `primary_file_name = <ACQ-ID>.data` for MRI now (was `<ACQ-ID>`); the .lnk dispatch from NI v2.1 already handles this generically (target the `.data` subfolder). **No-DICOM acquisition handling:** 3 of 7 source projects had ZERO DICOMs (students hadn't run Bruker's exporter). Ingest now registers these acqs with empty `<ACQ-ID>.data/` placeholder + fully populated `mri:` sidecar from JCAMP-DX; idempotent re-run after the student converts dedupes properly. Future-work FID→DICOM regeneration capability (no open-source Python library exists today — 2-4 week research project; Bruker GUI is closed-source) tracked in `tasks/tasks.md §3.1`. Docs synced: `03_RAW_STORAGE §4.4` (rewritten layout), `08_METADATA §4.3` (mri: block v2 shape), `09_MODALITIES §1.4` (storage + no-DICOM handling), `equipment/mri-platform/internal_mri_data_handling_workflow_notes.md` (Round-6 v2 reshape section + No-DICOM acquisition handling section + FID→DICOM future-work). Round-6 v2 commits pending. |
| 2026-05-27 | R. Tasseff | **Round-8 NI v2.1 — multi-frame DICOMs kept alongside per-frame.** Operator follow-up after v2 review: the platform-generated `frameMULTI` DICOMs (one per dynamic PET/SPECT acquisition, bundling all time frames in a single DICOM with `ImageType=DYNAMIC`) should be kept on gjesus3, not skipped. Now landing as `recon<X>_frameMULTI.dcm` under `<ACQ-ID>.data/` alongside the per-frame `recon<X>_frame<Y>.dcm` files. Both representations appear in the regular `metadata.json.ni.reconstruction.by_index.<idx>.dicoms[]` list — distinguishable by `ImageType` (`'DYNAMIC'` vs `'VOLUME'`) and `NumberOfFrames` (per-frame × n_frames vs per-frame). The separate `multi_frame_dicoms_on_platform` sidecar field introduced in v2 was retired. Only 1 acquisition in the round-8 cohort is affected (`ACQ-20251022-PET-001` m17 dynamic PET); spot-fixed via single-acq purge + re-ingest (now `ACQ-20251022-PET-007` because acq_id slots aren't reused). Code changes in `tools/ingest/ni_metadata.py::_plan_dcm_target` + the `dicoms` list now unified. Docs synced: `03_RAW_STORAGE §4.3`, `08_METADATA §4.3`, `09_MODALITIES §1.5`, `equipment/nuclear-imaging/internal_ni_data_handling_workflow_notes.md` "Multi-frame DICOM" section + v2 → v2.1 history table. Round-8 v2.1 commits pending. |
| 2026-05-27 | R. Tasseff | **Round-8 NI v2 — operator-feedback reshape + DICOM UID capture + linker UNC fix.** Three improvements after the user reviewed v1 (2026-05-26): (a) `metadata.json.ni._raw_metadata.protocol_txt` is now a parsed `{key: value}` dict (was a verbatim string); every line parsed, verbatim source-file keys preserved. (b) The on-disk shape is dramatically slimmer — `acquisition_aux/` removed entirely (parsed content lives only in the sidecar), per-recon non-DICOM files removed (parsed `reconparams.xml` content in `_raw_metadata.reconparams_by_idx`), data subfolder renamed from `reconstructions/` to `<ACQ-ID>.data/` mirroring microscopy's `<ACQ-ID>.czi` single-file convention. DICOMs renamed flat: CT → `recon<X>.dcm`, PET/SPECT → `recon<X>_frame<Y>.dcm` (iteration count dropped from filenames — fixed at 30 in current Molecubes setup; recoverable from sidecar). Registry `primary_file_name = <ACQ-ID>.data` for NI rows (was `<ACQ-ID>`); .lnk shortcut targets now point at the `.data` subfolder, mirroring how microscopy .lnk targets the `.czi` file directly. (c) Multi-frame DICOM handling: Molecubes generates `*frameMULTI*.dcm` files at recon root for dynamic PET/SPECT studies (one DICOM bundling all frames, `ImageType=DYNAMIC`, `NumberOfFrames` spanning all time-frame volumes). Per the user's observation that viewers struggle with these, gjesus3 does NOT copy them — only the per-frame DICOMs land. Existence + curated headers recorded in `metadata.json.ni.reconstruction.by_index.<idx>.multi_frame_dicoms_on_platform`. Future-work: validate multi-frame DICOM metadata and migrate to single-file-per-acquisition once verified. Tracked in equipment workflow notes "Multi-frame DICOM future-work" section. **DICOM UIDs** (`StudyInstanceUID` / `SeriesInstanceUID` / `SOPInstanceUID`) added to the curated `_DICOM_CURATED_TAGS` list — first in the per-DICOM `headers` bucket, required for any DICOM-aware tool (XNAT, PACS, OMERO). Each kept DICOM now gets its own `dicoms[]` entry under `reconstruction.by_index.<idx>` with `dst_basename` (on-NAS name), `src_relpath` (in platform archive), and the full curated header set. **Linker UNC fix:** `tools/ingest/linker.py::canonical_to_unc` now defensively normalizes the `nas_unc_root` argument to all-backslash form regardless of input (`//HOST/share` or `\\HOST\share` both work). Fixed after the v1 ingest's 84 .lnk shortcuts came out as 340-byte stubs Windows Explorer couldn't resolve — root cause was forward-slash input concatenated verbatim with backslash-converted relative path, producing the malformed mixed `//HOST/share\raw\...` UNC that `WScript.Shell.CreateShortcut` silently accepts but saves broken. New `feedback_unc_root_normalization.md` memory captures the lesson. Round-8 fully re-purged + re-ingested in v2 shape; 84 NI acqs (42 PET + 42 CT) across `proj-ae-biomegune-{0424, 0525}`; ~6.5 GB total on /raw/. Round-8 v2 commits pending. |
| 2026-05-26 | R. Tasseff | **Round-8 NI REDO + reframe refinement.** The 2026-05-22 round-8 NI ingest had a serious bug: it piggybacked on `tools/ingest_raw.py::copy_paravision_exam` (built for Bruker ParaVision, looks for `pdata/<idx>/`), which doesn't fit Molecubes NI archives (use `recon_<idx>/`). The fallback behaviour copied every file at the source root into `acquisition_aux/` — including ~6 GB of `data.raw` per acquisition — and **never copied any of the `.dcm` files** (which live inside `recon_<idx>/`). Net: ~358 GB of platform-owned raw event data on the NAS with zero analysis-ready DICOMs. **Fix:** full purge of 84 acqs + dedicated `copy_ni_acquisition` selective-allowlist copy function + new `tools/ingest/ni_metadata.py` extractor (parses `protocol.txt` + XML aux + DICOM headers into a structured `ni:` sidecar block analogous to `mri:`) + new `discovered.ni_*` curated subset (~15 fields). Re-ingested the same 84 acqs (42 PET + 42 CT) with slim shape: ~few MB per acquisition (DICOMs + small text/XML aux only), ~few GB total. **Reframe captured in docs:** [13_GJESUS3_ROLE §5.6](13_GJESUS3_ROLE.md) makes explicit that gjesus3 is NOT the long-term archive of original instrument bytes (the platforms own that — NI=trusted, MRI=reliable, microscopy=least-reliable), with per-modality "what we keep" rules driving selective inclusion; [13_GJESUS3_ROLE §5.7](13_GJESUS3_ROLE.md) captures the optical-microscopy-vs-biomedical-imaging file-shape paradigm distinction (one container vs many DICOM + dispersed aux). [03_RAW_STORAGE §4.2](03_RAW_STORAGE.md) NI row updated; new §4.3 details the slim NI folder shape; former §4.3 (MRI) renumbered to §4.4. [08_METADATA §4.3](08_METADATA.md) adds the `ni:` block shape. [09_MODALITIES §1.5](09_MODALITIES.md) reworked for the new ingest model + `discovered.ni_*` table. Equipment workflow notes ([`equipment/nuclear-imaging/internal_ni_data_handling_workflow_notes.md`](../equipment/nuclear-imaging/internal_ni_data_handling_workflow_notes.md)) updated with per-modality `recon_<idx>/` structure + the explicit keep-vs-drop table + a retrospective on the bug. Round-8 retrospective also documents the principle: **shared functions across instruments quietly fail when source structure differs from the function's assumptions; per-instrument `copy_strategy:` selectors are the right pattern.** Round-8 redo commits on `origin/main`: pending. |
| 2026-05-22 | R. Tasseff | **Round 8 — Nuclear Imaging (PET/CT) archive-mode landed in quasi-production state.** **84 acquisitions** (42 PET + 42 CT) ingested from Jesus's 2025 archive on `\\cicmgsp02\gnuclear2$\2025\Jesus\` (operator irene, Molecubes platform). Pipeline: `tools/extract_ni_archives.py` pulls the `.tgz` archives from the SMB share, extracts with `tar --strip-components=6` to `D:/projects/Nuke/test_data/`, then `tools/ingest_raw.py` ingests as folder-as-primary (same model as MRI round 6). Total ~374 GB unpacked, ~3.5 hours wall clock end-to-end (82 min extract + ~2 hr ingest including hash + copy to NAS). **Zero new projects** — full cross-modality reuse: 48 acqs landed in `proj-ae-biomegune-0525` (round-4 AxioScan + round-6 MRI + round-8 NI) and 36 in `proj-ae-biomegune-0424` (round-4 + round-6 + round-8). The animal-protocol-id-as-project-short_name convention proved its value at scale here. **Key framework facts:** archive name encodes the full registry-level metadata (user / series_id / date / short_project / short_sample / timestamp / modality) and is parsed via `filename_parse.regex:` — no new extractor module needed. `instrument = ${discovered.modality}` (per-case PET / CT / SPECT). `session_id` groups PET + CT of same animal-visit (verified on pilot: m13 PET + m13 CT share `irene_0525_251029_m13`). `acquisition_datetime` uses the archive name's 14-digit YYYYMMDDhhmmss form — `resolver.normalize_acquisition_datetime` extended to handle that (round-8 only code change). `metadata.json.dicom` block ships empty (no XML-aux extractor yet — Molecubes archives contain `.bin` reconstruction binaries + `protocol.xml`/`acqparams.xml`/etc. at the leaf, NOT `.dcm`; XML-aux extraction queued as future work). Live-machine NI workflow still blocked on Platform Manager Unai. Round-8 commits on `origin/main`: `359be7c` (framework + pilot). Conclusion commit pending. |
| 2026-05-22 | R. Tasseff | **Round 7 — Zeiss LSM 900 confocal (LSM9) landed in quasi-production state.** 13 `.czi` acquisitions ingested from the LAURA_UPTAKE_LP-IONP-doxo_MDA batch (researcher LAURA, cell line MDA, experiment "UPTAKE_LP-IONP-doxo"); auto-created project `proj-laura` (PROJ-0009); 13 unique `LSM9_<original_name>.czi.lnk` shortcuts in `proj-laura/raw_linked/`. **Zero new code** — third .czi-family instrument, reuses `tools/ingest/czi_metadata.py` 1:1; LSM 900 fingerprint confirmed via `czi_acquisition_mode = "LaserScanningConfocalMicroscopy"` (Cell Observer reports `"WideField"`). New per-instrument template at `tools/templates/instruments/lsm900.yaml` with a greedy-middle regex (`^(?P<researcher>[^_]+)_(?P<experiment>.+)_(?P<cell_line>[^_]+)$`) on the batch folder convention `<researcher>_<experiment-w/-internal-underscores>_<cell_line>` — same technique as the MRI round-6 `jrc` regex. Filename positional parse deferred: real-data chunk count varies 4–6 across the batch (`Z-stack` prefix optional, trailing replicate number optional, `ctrl` sometimes replaces timepoint) — would skip too many files; filename context lives in `${discovered.filename}` + the `.czi`-embedded `discovered.czi_*` (21 fields). Operator directions + parsable naming convention captured in `equipment/lsm900/lsm900_data_handling_workflow_notes.md`. `mfb-rdm-docs/09_MODALITIES.md` §1.3 updated with the round-7 status + cross-reference to the workflow notes; the `discovered.czi_*` table in §1.1 applies 1:1 (no separate table needed). Round-7 commit pending. |
| 2026-05-22 | R. Tasseff | **Round 6 — Internal MRI (Bruker ParaVision) landed in quasi-production state + `link_filename:` framework.** 97 `.czi`-equivalent ParaVision exams ingested across PROJ-0003 (26) + PROJ-0004 (71) with the new no-zip folder-as-primary layout, ParaVision JCAMP-DX metadata captured in `metadata.json.mri`, and the new `link_filename:` YAML field producing unique human-meaningful `.lnk` shortcut names (`MRI_<jrc_id>_<acq_date>_<exam>_<recon>`). Cross-modality demo verified — round-4 AxioScan `.lnk` and round-6 MRI `.lnk` coexist in the shared `ae-biomegune-{0423,0424}` project workspaces. The first round-6 ingest surfaced two bugs that were fixed before re-ingest: (a) the sidecar block key was `dicom:` instead of `mri:` (extractors now return a 3-tuple `(discovered, section, "mri")` to override the ecosystem-derived section name); (b) `.lnk` filename collisions when exam numbers like `27.lnk` repeated across animal sessions — fixed by the new `link_filename:` field. New systematic-naming-convention documentation added: extended `equipment/mri-platform/internal_mri_data_handling_workflow_notes.md` with the parsable `<project_folder>/<protocol_number>/pdata/<reconstruction>` breakdown including the `jrc` vs `jrc_` ambiguity handling; NEW `equipment/nuclear-imaging/internal_ni_data_handling_workflow_notes.md` documents the NI archive convention (`\\cicmgsp02\gnuclear2$\...\<archive>.tgz`) and tgz-nested structure for the future NI ingest round (round 7+). Per-instrument templates (`mri_bruker.yaml`, `axioscan7.yaml`, `cell_observer_cells.yaml`) all gained an exhaustive "AUTO-DISCOVERED FIELDS" comment block as the operator's reference card. New future-work items registered in `tasks/tasks.md`: user-as-operator permissions model for internal MRI/NI; NI ingest round (blocked on Unai's naming-convention question); NI tgz-aware staging; MRI naming-ambiguity stakeholder follow-up. Round-6 plan + history captured in `.claude/plans/i-have-the-creds-reactive-candle.md`; round-6 commits on `origin/main`: `17ac781` (Stream A docs reframe), `66887ae` (Stream B extractor), `943fd3e` (Stream C + D end-to-end). |
| 2026-05-18 | R. Tasseff | **Round 5 — Cell Observer (CELL) landed in quasi-production state.** 165 `.czi` acquisitions across 3 auto-created projects (`itziar-colageno` 30, `itziar-alphasma` 61, `itziar-colageno-permeabilizado` 74) ingested from operator Ainhize Urkola Arsuaga's data. **The round delivered the canonical exhibit for the team:** the SAME ingest pipeline machinery handles two different metadata-providing conventions by changing only the YAML — `cell_observer_itziar_alphasma_TEST.yaml` (filename-focused, 5-chunk filenames) vs. `cell_observer_itziar_colageno_perm_TEST.yaml` (path-focused, 2-chunk filenames with the rest from the path). The new `path_parse` / `auto_create_project:` / collision-WARN features all exercised end-to-end on real data. **All current ingests (collaborator DICOM rounds 1-2, AxioScan round 4, Cell Observer round 5) are quasi-production:** they live on the NAS, they're treated as real, but they will be purged in full after the team exhibition, with feedback rolled into the true production restart. Configs retain their `_TEST.yaml` filenames and the registry rows retain their "purge after review" notes by design. Detail trail in `tasks/tasks.md §4.6.B`; next active passes are §4.6.C (LSM 900 confocal, blocked on Ainhize example), §4.5 (MRI, blocked on platform manager + sample), §4.7 (Nuclear Imaging, blocked on Unai answering one naming-convention question). |
| 2026-05-14 | R. Tasseff | **Round-5 architectural prep: `auto_create_project:` block + formalized `path_parse` + project-naming open question.** Two new optional YAML features documented in [10_TOOLS §2.1.3](10_TOOLS.md) (`path_parse:` — path-level metadata extraction symmetric to `filename_parse`) and [10_TOOLS §2.1.4](10_TOOLS.md) (`auto_create_project:` — owner/description/notes for auto-created projects, resolver-evaluated, first-write-wins). [05_PROJECTS §7+§10](05_PROJECTS.md) and [06_REGISTRIES §4.2](06_REGISTRIES.md) cross-referenced. New §9 callout in [05_PROJECTS](05_PROJECTS.md) flags project naming as an open consensus question (PROJ-05) — provisional patterns (`ae-biomegune-NNNN`, `${researcher}-${experiment}`) are stopgaps; project-lead users must converge on a durable, meaning-bearing convention. Cell Observer cells-mode YAML example added to 10_TOOLS demonstrating both new features. Implementation (code + templates + Cell Observer round-5 test) tracked next. |
| 2026-05-13 | R. Tasseff | Round-5 prep + context-switching scaffolding. Cell Observer workflow notes (drafted from operator transcript) committed under `equipment/cell-observer/`. `equipment/INDEX.md` references the notes. `tasks/tasks.md` restructured: new top-level §0 "Active Pass / Up Next" makes the next-step branch (Cell Observer vs MRI DICOM, gated on which operator's sample data arrives first) discoverable in one read; §4.6.B Cell Observer and §4.5 MRI both rewritten with "Pickup context" subsections so either pass can be picked up cold after a context switch. Design intent for the `path_parse` YAML feature locked in §3.1 (symmetric to `filename_parse`, lets operators put metadata in folder names — needed for Cell Observer / LSM 900 where filenames are weak). Implementation deferred to round-5 Cell Observer pass when there's real folder structure to test against. |
| 2026-05-12 | R. Tasseff | **Provenance auto-logging on ingest.** Closed a gap caught in round-4: ingest created `.lnk` shortcuts under `/projects/<proj>/raw_linked/` but never wrote a row to the project's `provenance.csv`. Adopted the broader rule (07_PROVENANCE §2.1, DECIDED) that **any tool changing files under `/projects/`, `/publications/`, or curated datasets updates provenance**. New shared module `tools/ingest/provenance.py` owns the schema; `ingest_raw.py` Step 12 calls `provenance.append_entry()` immediately after `linker.create_lnk()` — idempotent on `output_path`, self-healing for existing-but-unlogged shortcuts. Aligned `provenance.csv` schema in `create_project.py` with the 12-field doc spec (was 10 fields with mismatched names like `output_type` / `inputs` / `process`). Migrated PROJ-0001 and PROJ-0002 `provenance.csv` files to the new header (no data rows to lose). |
| 2026-05-12 | R. Tasseff | **Metadata-location architecture decision.** Acquisition-level metadata (auto + Operator at ingest) stays in `/raw/<ACQ-ID>/metadata.json` (immutable post-deposit). Study-level researcher-supplied metadata (REMBI Study + Biosample context) moves to `/projects/<proj>/metadata/` (mutable). Added the `User` role (researchers) alongside `Operator` (technicians); refreshed [11_OPERATIONS §1.1 + §2.1](11_OPERATIONS.md) with the four-role permissions table. Project ephemerality made explicit — projects are deleted at close-out; [05_PROJECTS §4.x](05_PROJECTS.md) describes the close-out preservation step (study metadata merged into `/raw/` by Data Mgmt Lead). Future-tools queue in [tasks/tasks.md](../tasks/tasks.md) §3.2: `gather_metadata.py` (join /raw + /projects on acq_id), Excel-to-metadata importer (researcher-facing), project close-out tool. Raw-immutability lockdown design must preserve a Lead write path for close-out merges. |
| 2026-05-12 | R. Tasseff | Round-4 fixes from user handoff testing: fail-fast on invalid `--nas-root` (Windows users were silently writing to `C:\mnt\gjesus3\` due to WSL-style default path); user-facing path examples normalized to Windows backslash (`J:\`); `file_size_mb` switched from binary MiB (`/1024²`) to decimal MB (`/1000²`) matching the column name; `file_count` redefined as primary-data files (`.dcm` count for DICOM, `.czi`/`.tif`/`.tiff` count for microscopy) rather than destination-folder file count. New per-instrument template structure (`tools/templates/instruments/axioscan7.yaml`) with conventions locked in; docs (CLI, Operations, 10_TOOLS, CLAUDE) rewired to point users at per-instrument templates. New DRAFT `sample_type` controlled vocabulary (`tissue` / `organism` / `cells` / `material` / `phantom`, REG-07); AxioScan template defaults `tissue`. Quick Start flagged as AxioScan-specific until 2-3 instruments validated. Existing 75 production rows not backfilled (consistent across `file_size_mb`, `file_count`, sample_id format) — slated for opportunistic re-ingest. |
| 2026-05-12 | R. Tasseff | Round-4 AxioScan 7 validation: 28-acquisition test ingest from `S:\...\AxioScan\20260506\` (3 animal projects in one folder, 1 config, auto-create-then-reuse for all 3 projects), verified end-to-end then purged. Two pilot conventions adopted via YAML interpolation (no code change): composite `sample_id = ${discovered.project}_${discovered.sample_short}` (see [06_REGISTRIES §2.3](06_REGISTRIES.md) DRAFT, REG-01 still open pending PI sign-off) and full animal-project code as `project_hint = "AE-biomeGUNE-${discovered.project}"` → auto-created short_names `ae-biomegune-NNNN`. User-facing docs: researcher Quick Start in [11_OPERATIONS §3.2](11_OPERATIONS.md) + CLI reference at [`tools/INGEST_CLI.md`](../tools/INGEST_CLI.md). Production config `tools/configs/axioscan7_20260506.yaml` ready for user manual run (Phase B). |
| 2026-05-06 | R. Tasseff | AxioScan 7 (.czi) ingest end-to-end (3 test acqs on NAS, pending purge). New three-block YAML config schema (`ingest:` / `auto_discover:` / `registry:`) replaces `defaults:` + Python `SPECIAL_FIELDS` — per-column mapping explicit in YAML with `discovered.<field>` references and `${...}` interpolation; resolver in `tools/ingest/resolver.py`; configs live under `tools/configs/`. New `ingest_config` registry column records the YAML config that produced each row (CSV migrated 21→22 cols; defensive header check added to `registry.append_row`). `.czi`-internal metadata extraction implemented (`tools/ingest/czi_metadata.py`, library: `czifile`): 21 curated `discovered.czi_*` fields plus a structured `microscopy:` sidecar block (geometry, instrument, acquisition, mosaic, document_info). Per-instrument field reference table in [09_MODALITIES §1.1](09_MODALITIES.md); library/route rationale + OMERO/pylibCZIrw deferral in [10_TOOLS §2.1.2](10_TOOLS.md); REMBI projection deferred until cross-instrument batch data exists, plan in [08_METADATA §3.5](08_METADATA.md). Cross-doc updates in [10_TOOLS §2.1](10_TOOLS.md), [08_METADATA §4.3](08_METADATA.md), [06_REGISTRIES §2.2](06_REGISTRIES.md), [03_RAW_STORAGE §2.6](03_RAW_STORAGE.md). |
| 2026-05-05 | R. Tasseff | Project linking method resolved: Windows `.lnk` shell shortcuts (pilot-specific Windows-first choice); linker implemented in `tools/ingest/linker.py`; rationale and porting guide documented in [10_TOOLS §2.1.1](10_TOOLS.md#211-project-linking--windows-first-design-decision); cross-doc cleanup of "linking method TBD" references |
| 2026-03-06 | R. Tasseff | DICOM stored as compressed archives; primary staging off-NAS; two ingest modes (full + lightweight); metadata extraction integrated into full-mode ingest; one-primary-file rule simplified (no DICOM exception) |
| 2026-03-02 | R. Tasseff | Promoted Projects area to live feature (Draft); updated key decisions, removed from deferred |
| 2026-02-25 | R. Tasseff | Raw structure → ecosystem-based (MICROSCOPY/DICOM/EM); resolved RAW-05; added 12_CURATED_DATASETS spec; updated registries |
| 2026-02-02 | R. Tasseff | Restructured from monolithic spec to modular documents; refocused on archival scope |
| 2025-01-22 | R. Tasseff | v0.2 — Added discussion flags for stakeholder meeting |
| 2025-01-22 | R. Tasseff | v0.1 — Initial comprehensive draft |
