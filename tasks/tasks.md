# MFB gjesus3 RDM Pilot — Task List

**Last Updated:** 2026-05-29

This file consolidates all open and completed tasks. Completed items are kept for context but marked with ~~strikethrough~~.

---

## 0. Active Pass / Up Next

> **⚠️ All current ingests are quasi-production.** Each instrument is iterated test → purge → accept-as-quasi-production. After the team exhibition, **everything gets purged** and true production restarts incorporating exhibition feedback. "Done" below means done in the quasi-production sense; the TEST tagging in config filenames + registry notes is intentional and stays.
>
> **⚠️ System role reframed 2026-05-20.** gjesus3 = research-facing working layer (5-year active window), complementing — not replacing — the platforms' deep-archive of raw bytes. Folder-as-primary is now permitted for ecosystems whose data lands as many files (internal MRI). See [`13_GJESUS3_ROLE`](../mfb-rdm-docs/13_GJESUS3_ROLE.md).

**Rounds completed in quasi-production state:**

| Round | Instrument | Outcome on NAS | Config(s) |
|-------|-----------|----------------|-----------|
| 1–2 | Collaborator DICOM (XMRI) | 75 acqs across PROJ-0001 (LIONS, 42) + PROJ-0002 (HPIC, 33) | `lions_*.yaml`, `hpic_*.yaml` |
| 4 | AxioScan 7 (ZWSI) | 28 acqs across PROJ-0003/0004/0005 (`ae-biomegune-{0423,0424,0525}`) | `axioscan7_20260506.yaml` (+ TEST) |
| 5 | Cell Observer (CELL) | **165 acqs across PROJ-0006/0007/0008** (`itziar-colageno`, `itziar-alphasma`, `itziar-colageno-permeabilizado`) — exercised **both filename-focused and path-focused metadata extraction** on real Ainhize/Itziar data | `cell_observer_itziar_alphasma_TEST.yaml`, `cell_observer_itziar_colageno_perm_TEST.yaml` |
| 6 | Internal MRI (Bruker ParaVision) | **v2 LANDED 2026-05-27** — 97 acqs re-ingested from `D:\projects\gjesus3\data_test\` (7 source projects) with the NI v2.1 layout: flat-DICOM under `<ACQ-ID>.data/`, parsed JCAMP-DX in sidecar, DICOM UIDs first in headers. 3 of 7 source projects have empty `.data/` placeholders (students hadn't run Bruker's exporter; 2026-05-29 Dicomifier pilot validated PV-7 → DICOM regeneration as the fix path — §3.1). Cross-modality reuse with round-4 AxioScan + round-8 NI workspaces verified. Commit: `f5fefa5`. See §4.5 for full v1 → v2 history. | `mri_bruker_20251016_TEST.yaml` |
| 7 | LSM 900 confocal (LSM9) | 13 acqs in PROJ-0009 (`proj-laura`) — first batch LAURA_UPTAKE_LP-IONP-doxo_MDA. Third .czi-family instrument; reuses czi_metadata.py extractor. New folder-name regex on `<researcher>_<experiment>_<cell_line>` batch convention; filename variable-chunk handling deferred. | `lsm900_laura_uptake_TEST.yaml` |
| 8 | Nuclear Imaging archive (PET/CT) | **84 acqs** from Jesus's 2025 NI archive (42 PET + 42 CT). Zero new projects: 48 in `proj-ae-biomegune-0525`, 36 in `proj-ae-biomegune-0424`. **v2.1 landed 2026-05-27** (`<ACQ-ID>.data/` flat-DICOM layout incl. multi-frame `recon<X>_frameMULTI.dcm`, parsed protocol.txt + XML aux in sidecar, DICOM UIDs captured). v2 (skipped multi-frame DICOMs — fixed in v2.1) + v1 (slim-folder rewrite) preceded; original 2026-05-22 had the ParaVision-piggyback bug — see §4.7 retros. Archive mode only; live-machine still pending Unai. | `ni_jesus_archive_2025_TEST.yaml` |

Round-5 round-up (Cell Observer) detail trail in §4.6.B.

### Round 8 — **Nuclear Imaging archive (PET/CT)** — v2.1 LANDED 2026-05-27

**Archive-mode ingest** of Jesus's 2025 NI archive on `\\cicmgsp02\gnuclear2$\2025\Jesus\`. 84 `.tgz` archives (42 PET + 42 CT) from operator Irene, ~298 GB compressed across series 0525 (12 animals × 2 modalities on one date) and series 1207 (multi-visit study, ~30 animal-visits × 2 modalities). All from the Molecubes system.

> **⚠️ Round-8 v1 retrospective (the bug fixed 2026-05-26):** the original 2026-05-22 ingest piggybacked on `tools/ingest_raw.py::copy_paravision_exam` (built for Bruker ParaVision — looks for `pdata/<idx>/` for reconstructions). Molecubes archives have `recon_<idx>/` instead. The function found no `pdata/`, fell back to "copy every file at source root into `acquisition_aux/`," and dumped ~6 GB of `data.raw` + raw event data per acquisition while **never copying any `.dcm` files** (which live inside `recon_<idx>/` and were ignored). Net result: ~358 GB of platform-owned raw bytes on the NAS, zero analysis-ready DICOMs. **Fix (2026-05-26):** full purge + new dedicated `copy_ni_acquisition()` selective-allowlist copy + new `tools/ingest/ni_metadata.py` extractor + new `copy_strategy:` YAML field selecting between the per-instrument copy functions. Round-8 re-ingested with slim shape (~few MB per acquisition; total ~few GB instead of ~358 GB), populated `ni:` sidecar block, all DICOMs present. **Principle to remember:** shared functions across instruments quietly fail when source structure differs from the function's assumptions; per-instrument `copy_strategy:` is the right pattern. The doc reframe in [`13_GJESUS3_ROLE §5.6`](../mfb-rdm-docs/13_GJESUS3_ROLE.md) and [`§5.7`](../mfb-rdm-docs/13_GJESUS3_ROLE.md) captures the broader framing that drove the redo — gjesus3 is NOT the long-term archive of original instrument bytes; the platforms are.
>
> **🔄 Round-8 v2 reshape (2026-05-27):** following operator review of v1, three improvements landed: (1) `protocol_txt` in the sidecar is now a parsed `{key: value}` dict (every line, verbatim keys preserved) instead of a verbatim string; (2) the on-disk shape was slimmed further — `acquisition_aux/` removed entirely, per-recon non-DICOM aux removed, data subfolder renamed `<ACQ-ID>.data/` mirroring microscopy's `<ACQ-ID>.czi`, DICOMs renamed flat (`recon<X>.dcm` for CT, `recon<X>_frame<Y>.dcm` for PET/SPECT); (3) DICOM UIDs (`StudyInstanceUID` / `SeriesInstanceUID` / `SOPInstanceUID`) added to the curated headers — critical for XNAT/PACS interop. **Linker UNC bug fix:** v1 ingest produced 84 broken 340-byte .lnk stubs because `--nas-unc "//GJESUS3/gjesus3"` (forward slashes) concatenated with backslash-converted paths to produce mixed-separator UNCs that `WScript.Shell.CreateShortcut` silently accepts but saves malformed. `linker.canonical_to_unc` now defensively normalizes regardless of input form. Memory: `feedback_unc_root_normalization.md`.
>
> **🔄 Round-8 v2.1 multi-frame DICOMs included (2026-05-27 follow-up):** v2 skipped the platform-generated `frameMULTI` DICOMs at recon root entirely; v2.1 reverses that — they're now kept alongside per-frame DICOMs as `recon<X>_frameMULTI.dcm` under `<ACQ-ID>.data/`. Both representations appear in `metadata.json.ni.reconstruction.by_index.<idx>.dicoms[]`; the `multi_frame_dicoms_on_platform` sidecar field from v2 was retired. Only 1 acquisition in the cohort was affected (`ACQ-20251022-PET-001` m17 dynamic PET); spot-fix via single-acq purge + re-ingest (m17 now lives at `ACQ-20251022-PET-007` — acq_id slots aren't reused). Multi-frame DICOMs distinguishable by `ImageType` containing `'DYNAMIC'` (per-frame: `'VOLUME'`) and `NumberOfFrames` = per-frame_NumberOfFrames × n_frames. Multi-frame is the closer-to-"one-file-per-acquisition" form; advanced metadata not yet validated (future-work in §3.1).

**Live-machine workflow** still pending Platform Manager Unai's answer on workflow + access. Round 8 is archive-mode-only — a pragmatic Phase A that validates the framework against representative NI data while the live-mode conversation continues. See `equipment/nuclear-imaging/internal_ni_data_handling_workflow_notes.md` for the archive-vs-live design.

**Pipeline:**
1. [`tools/extract_ni_archives.py`](../tools/extract_ni_archives.py) — pulls `.tgz` from SMB, extracts to `D:/projects/Nuke/test_data/<archive_basename>/` with `--strip-components=6` (strips the 6-level outer nesting). Idempotent (`.extracted` sentinel). Retry-hardened against transient `WinError 59` SMB drops.
2. [`tools/ingest_raw.py`](../tools/ingest_raw.py) with [`tools/configs/ni_jesus_archive_2025_TEST.yaml`](../tools/configs/ni_jesus_archive_2025_TEST.yaml) — folder-as-primary ingest. Each `.tgz` → one ACQ (PET or CT) under `/raw/DICOM/<year>/<year-month>/`. `link_filename` produces `<modality>_<animal>_<acq_date>_<acq_datetime_full>.lnk` (unique per acq).

**Decisions locked for this round:**
- Archive name encodes the full registry-level metadata; no new extractor module needed. `filename_parse.regex:` on the staged folder basename (= archive basename without `.tgz`) extracts 7 `discovered.*` fields.
- `instrument: discovered.modality` — per-case PET / CT / SPECT (one .tgz = one modality).
- `project_hint: ae-biomegune-${discovered.short_project}` — same animal-protocol convention as AxioScan + MRI; cross-modality reuse with `proj-ae-biomegune-{0424,0525}` from rounds 4 + 6.
- `session_id: ${discovered.user}_${discovered.series_id}_${discovered.acq_date_short}_${discovered.short_sample}` — groups PET + CT of the same animal-visit into one ISA "study" (verified on pilot: PET m13 + CT m13 share `session_id=irene_0525_251029_m13`).
- `acquisition_datetime` resolver now handles 14-digit `YYYYMMDDhhmmss` timestamps (Molecubes archive-name format) — small extension to `normalize_acquisition_datetime`.
- DICOM-Modality-tag auto-detect produces incidental noise (e.g. extensionless files like `ACQSTATUS` get mistaken for DICOM); ignored since the registry `instrument` is driven by `discovered.modality` from the filename regex, not auto-detection. WARN messages are informational.
- `metadata.json.dicom` block ships empty (no NI XML-aux extractor yet — queued as future work).

§4.7 has the full execution checklist + scope.

### Round 7 — LSM 900 confocal (LSM9) — ✅ COMPLETE (in quasi-production)

13 acqs in PROJ-0009 (`proj-laura`); first batch LAURA_UPTAKE_LP-IONP-doxo_MDA. Third .czi-family instrument; reused `tools/ingest/czi_metadata.py` 1:1 (zero new code). Folder-name regex on `<researcher>_<experiment-w/-internal-underscores>_<cell_line>` batch convention. Commit: `2bbbf4d`. §4.6.C has the detail trail.

### Round 6 — Internal MRI (Bruker ParaVision) — ✅ v2 LANDED 2026-05-27 (97 acqs in quasi-production)

**v1 (2026-05-22)**: 97 acqs across PROJ-0003/0004; cross-modality demo with round-4 AxioScan workspaces. Commits: `17ac781` (Stream A docs reframe), `66887ae` (Stream B extractor), `943fd3e` (Stream C+D end-to-end), `6883991` (documentation consolidation). PURGED 2026-05-27 as part of the v2 reshape.

**v2 (2026-05-27, landed)**: 97 acqs re-ingested from `D:\projects\gjesus3\data_test\` (7 source projects) with the slim NI v2.1 layout (`<ACQ-ID>.data/` flat-DICOM, parsed JCAMP-DX in sidecar, DICOM UIDs first, no-DICOM acquisition handling). 3 of 7 source projects have empty `.data/` placeholders pending Dicomifier-based regeneration (§3.1; pilot validated 2026-05-29 — PV-7 → DICOM works on PV-7 source). Commit: `f5fefa5`. See §4.5 for the full detail trail + v1→v2 retro.

**Key round-6 deliverables (still in force):**
- `13_GJESUS3_ROLE.md` reframe (research-facing working layer; two-tier model with platform deep-archive).
- ISA terminology (investigation/study/assay → project/session/acquisition); DRAFT registry columns `session_id` + `primary_kind`.
- No-zip folder-as-primary layout (`acquisition_layout: folder`) + selective `reconstructions:` flag.
- ParaVision JCAMP-DX extractor (`paravision_metadata.py` + `jcampdx.py`) — canonical metadata source for internal MRI; `metadata.json.mri` block via the 3-tuple section-name-override mechanism.
- `link_filename:` YAML field framework — per-instrument templates ship recommended defaults; operator override per-batch.
- New systematic-naming-convention docs in `equipment/mri-platform/` and `equipment/nuclear-imaging/`.
- Future-work items registered: user-as-operator permissions, NI ingest (blocked on Unai), NI tgz-aware staging, MRI naming-ambiguity stakeholder follow-up, project-level NIfTI generation tool.

### 2026-05-29 follow-ups (post-round-8 / post-round-6 quasi-production)

| Stream | Section | Status |
|---|---|---|
| **Preclinical subject metadata DRAFT spec** (species/strain/sex/age — ARRIVE-aligned) | §3.2 (4-phase animal-DB integration) | ✅ Spec landed (`08_METADATA §4.4` + `09_MODALITIES` per-instrument + `06_REGISTRIES §2.4` cross-ref + `13_GJESUS3_ROLE §5.6`). Phase 1 (animal-facility-DB API access) blocked on IT. |
| **Preclinical disease-state / control metadata DRAFT spec** (`is_control` DECIDED + `disease_model`/`disease_state` DRAFT) | §3.2 (same Phase 3 writer as `subject:`) | ✅ Spec landed (`08_METADATA §4.5` + `09_MODALITIES` per-instrument rows + `06_REGISTRIES §2.4` extended + `13_GJESUS3_ROLE §5.6` extended). Operator-entered only — no IT dependency. Phase 3 writer adds the `is_control` REQUIRED-check that refuses sidecar write if missing. |
| **Dicomifier pilot** — ParaVision-7 → DICOM regeneration (`tools/animal_db.py`-style, supersedes "no open-source library" assessment) | §3.1 | ✅ Pilot GREEN 2026-05-29 (12 m13 exams + m17 side-by-side, UIDs round-trip identical with Bruker GUI export). Phase 2 (`paravision_regen.py` subprocess wrapper) pending user confirmation Monday + 3D-Slicer PixelSpacing axis-order check. |
| **QNAP permissions cleanup** (group ACLs across the share root + subdirs; raw immutability part of §4.3 below) | §4.3 + §6 | ⏳ Waiting on IT — Ryan's request open with the IT team handling QNAP. Folder ACLs (`pilot-users` R + RW-on-projects/publications/staging; `pilot-operators` R + RW-on-raw/registries) blocked until IT clarifies group setup. |

**Active waits:**

| Pass | Section | Blocked on |
|------|---------|-----------|
| Nuclear Imaging live-machine workflow (`PET`/`SPECT`/`CT`) | §4.7 | Platform Manager **Unai** to answer one outstanding question before we submit the data-workflow documentation + example. |
| Animal/histology-mode Cell Observer | §4.6.B Deferred | Real example folder of historical histology work; backfill round. |
| QNAP NAS group permissions + raw immutability | §4.3, §6 | IT team to define groups + apply ACLs server-side (Windows-Explorer ACLs don't propagate cleanly). |
| Animal-facility-DB programmatic access | §3.2 | IT team to expose the DB API (REST/SQL/CSV — TBD). |
| ParaVision → DICOM regeneration integration (Phase 2) | §3.1 | User confirmation of pilot on Monday 2026-06-01 + visual axis-order check in 3D Slicer. |

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
- [ ] Complete data type sign-up sheet — need volunteer owners per type (MOD-02) — partially superseded by the per-instrument-template + per-batch-config pattern (each instrument has a documented operator workflow + working extractor); the "named volunteer per type" framing is now lower priority.
- [ ] Conduct show-and-tell walkthrough for each confirmed data type (MOD-03) — supplanted by the team exhibition (uses the round-1..8 ingest results as the substrate).
- [x] ~~Collect one representative example dataset per type for script testing~~ — done per-modality in Section 4 (rounds 1-2 / 4 / 5 / 6 / 7 / 8 each ingested representative real data).

### 2.2 Instrument Metadata Audit
> Resolved per-modality during ingestion testing (Section 4). Each test pass audits embedded metadata for that format.
- [x] ~~DICOM (collaborator) — resolved during Section 4.2~~ — audit complete; per-acquisition DICOM-header extractor for XMRI still queued (§3.1 future work).
- [x] ~~.czi from Axio Scan 7 (WSI) — resolved during Section 4.6~~ — 21 curated `discovered.czi_*` fields + `microscopy:` sidecar block landed 2026-05-06.
- [x] ~~.czi from Cell Observer — resolved during Section 4.6~~ — same `.czi` extractor reused 1:1; confirmed via round-5 probe.
- [x] ~~.czi from LSM 900 — resolved during Section 4.6~~ — same extractor; confirmed via round-7 probe.
- [x] ~~Confirm Cell Observer and LSM 900 .czi metadata is similar to WSI .czi (MOD-07)~~ — confirmed; round-5 + round-7 (`czi_acquisition_mode` distinguishes LSM 900 confocal from Cell Observer widefield).
- [x] ~~DICOM from MRI platform — resolved during Section 4.7~~ — round-6 v2 audit complete; ParaVision JCAMP-DX is canonical metadata source + per-DICOM headers in sidecar (`mri:` block).
- [x] ~~DICOM from Nuclear Imaging platform — resolved during Section 4.8~~ — round-8 v2.1 audit complete; protocol.txt + XML aux + DICOM headers all parsed (`ni:` block).
- [x] ~~Confirm DICOM as the output format from both platforms (MOD-05)~~ — MRI: DICOM is one of three (DICOM/NIfTI/raw); we keep DICOM. NI: DICOM is the analysis-ready format alongside raw event data; we keep DICOM. Both confirmed.

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

#### Round 6 (Internal MRI / Bruker ParaVision) — ✅ COMPLETE (v2 landed 2026-05-27)

All round-6 framework items below shipped across commits `17ac781` → `66887ae` → `943fd3e` → `6883991` (v1) → `f5fefa5` (v2 reshape). See §4.5 for the full implementation history.

- [x] ~~**`tools/ingest/jcampdx.py`**~~ — minimal pure-Python JCAMP-DX text parser (~80 LOC). Handles `##KEY=value` scalars, `##KEY=( N )` arrays spanning multiple lines, `<...>` strings, `$$` comments. No third-party dependency. Used by `paravision_metadata.py`.
- [x] ~~**`tools/ingest/paravision_metadata.py`**~~ — Bruker ParaVision metadata extractor mirroring `czi_metadata.py` shape. v2 reshape rewrote `load_paravision_exam()` to walk per-frame DICOMs, emit per-DICOM `dicoms[]` lists with curated headers (UIDs first + MRI-specific tags). ParaVision aux files (`subject`/`acqp`/`method`/`visu_pars`) are canonical metadata source. Documented in [10_TOOLS §2.1.2b](../mfb-rdm-docs/10_TOOLS.md), [08_METADATA §4.3](../mfb-rdm-docs/08_METADATA.md), [09_MODALITIES §1.4](../mfb-rdm-docs/09_MODALITIES.md).
- [x] ~~**`tools/ingest/probe_paravision.py`**~~ — read-only probe utility mirroring `probe_czi.py`. Dumps parsed JCAMP-DX + curated subset to `_probes/`.
- [x] ~~**Detector dispatch under `FORMAT_EMBEDDED_EXTRACTORS["DICOM"]`**~~ in `tools/ingest/config.py`. Content-based detect: if `acqp` + `method` present alongside the source, calls `paravision_metadata.extract`; else returns empty for collaborator XMRI behaviour. Passes 3-tuple unchanged via `_extract_dicom_embedded`.
- [x] ~~**`regex_extract:` option in `filename_parse`**~~ — optional `regex:` block in `auto_discover.filename_parse`. Reusable beyond MRI. Documented in [10_TOOLS §2.1.3](../mfb-rdm-docs/10_TOOLS.md).
- [x] ~~**`acquisition_layout: file | archive | folder` flag**~~ in `ingest:` block (default `file`). MRI uses `folder` (no zip, folder-as-primary). v2 added `copy_strategy:` for per-instrument copy-function selection. Documented in [10_TOOLS](../mfb-rdm-docs/10_TOOLS.md) `ingest:` flags table and [03_RAW_STORAGE §4.2](../mfb-rdm-docs/03_RAW_STORAGE.md).
- [x] ~~**`reconstructions:` flag**~~ (MRI-specific) — `all` \| integer \| list of integers. v2 default changed to `all` (DICOMs are tiny under the slim layout).
- [x] ~~**`tools/ftp_mirror.py`**~~ — standalone SFTP CLI using `paramiko`. Recursively mirrors a study folder to local staging; idempotent. Decoupled from `ingest_raw.py`.
- [x] ~~**`link_filename:` YAML field**~~ (added 2026-05-22 in response to round-6 first-ingest `.lnk` collision bug). Resolver-evaluated at link-creation time. Per-instrument templates ship recommended defaults. Documented in [10_TOOLS §2.1.5](../mfb-rdm-docs/10_TOOLS.md).
- [x] ~~**Sidecar section-name override**~~ (round-6 first-ingest fix). Embedded-metadata extractors may return a 3-tuple `(discovered, section_dict, section_name_override)`. ParaVision uses this to put data under `metadata.json.mri` (not `dicom`).
- [x] ~~**v2 reshape additions (2026-05-27)**~~: new `copy_mri_paravision` selective-copy function in `tools/ingest_raw.py` (mirrors `copy_ni_acquisition`); `copy_strategy: mri_paravision_v2` YAML field; `_DICOM_CURATED_TAGS` list with UIDs first + MRI-specific tags; per-DICOM `dicoms[]` lists under each recon; `primary_file_name = <ACQ-ID>.data`; .lnk dispatch targets the `.data` subfolder; no-DICOM acquisition handling (empty `.data/` placeholder + populated sidecar).

#### Future work (documented for later, not in scope this round)

- [ ] **Multi-frame DICOM validation + potential migration to single-file-per-acquisition** (2026-05-27, NI v2.1). Molecubes generates a `*frameMULTI*.dcm` file at recon root for dynamic PET/SPECT studies — one DICOM bundling all frames with `ImageType=DYNAMIC` and `NumberOfFrames` spanning all time-frame volumes (e.g. 768 for a 2-frame study with 384 z-slices each). Closer to the "one file per acquisition" ideal than per-frame DICOMs. **v2.1 now keeps both representations on gjesus3** (as `recon<X>_frameMULTI.dcm` alongside `recon<X>_frame<Y>.dcm`); future action when ready: verify the multi-frame DICOM's advanced metadata (per-frame functional groups, frame time vectors, frame reference time, dose history vector). If clean across observed viewers, consider making multi-frame the canonical and dropping the per-frame copies (sidecar shape supports this transition with no code changes). See `equipment/nuclear-imaging/internal_ni_data_handling_workflow_notes.md` "Multi-frame DICOM" section.
- [x] ~~**Linker UNC normalization** (fixed 2026-05-27).~~ `linker.canonical_to_unc` now defensively normalizes the `nas_unc_root` argument to all-backslash UNC form (`replace("/", "\\")` + `strip("\\")` + prepend `\\\\`) regardless of input form. Catches the bug where `--nas-unc "//HOST/share"` (forward slashes — what Git Bash autocompletes) silently produced 340-byte stub .lnk files Windows Explorer couldn't resolve. Memory: `feedback_unc_root_normalization.md`.

- [ ] **ParaVision → DICOM regeneration for no-DICOM internal MRI acquisitions** (UPDATED 2026-05-29 — Dicomifier identified as candidate; previously assessed as 2-4 week build-from-scratch). When researchers don't run Bruker's GUI DICOM exporter, the acquisition's `pdata/<idx>/dicom/` is missing entirely; round-6 v2 detected 3 of 7 source projects in this state. Currently the ingest registers these as empty-`.data/` placeholders.

  **Lead candidate: [Dicomifier](https://github.com/lamyj/dicomifier)** (open-source, lamyj/dicomifier — IADI lab, Inserm/Université de Lorraine). Python (~87%) + C++ (~11%) core. Available via conda-forge (`conda install -c conda-forge dicomifier`). Provides `bruker2dicom` — reads ParaVision exam folders (acqp/method/visu_pars/subject + 2dseq) and emits conformant DICOM aligned with the DICOM dictionary. Also provides `dicom2nifti` — independent of this task, but useful for the project-level NIfTI tool in §3.2.

  **Caveat — ParaVision 7 validation needed.** Dicomifier docs state field-testing on PV 4/5/6. Our internal MRI is on PV 7.0.0 (`/opt/PV-7.0.0/data/nmr/`). JCAMP-DX is generally stable across PV versions and the format changes have mostly been in `pdata/` shape, not the canonical `acqp`/`method`/`subject`/`fid` files — so PV 7 should work, but needs empirical confirmation. Latest Dicomifier release is v2.4.0 (Feb 2023); not super-active but not abandoned. If PV 7 needs upstream fixes, contributing back is far cheaper than building from scratch.

  **Revised effort estimate (assuming Dicomifier works on PV 7):**

  | Phase | Effort |
  |---|---|
  | Pilot validation on PV 7 (this task — in progress 2026-05-29) | ~1 day |
  | Integrate as ingest backfill module (`tools/ingest/paravision_regen.py` calling Dicomifier) | 2-3 days |
  | Wire into ingest dispatch (run when `pdata/<idx>/dicom/` empty + flag enabled) | 1-2 days |
  | Validation against the 3 no-DICOM round-6 acquisitions + idempotent re-ingest | 2-3 days |
  | **Total** | **~1-2 weeks** (was 2-4 weeks for build-from-scratch) |

  **Pilot test — ✅ GREEN (executed 2026-05-29; user confirmation pending Monday):**

  Setup: Dicomifier 2.5.3 installed via miniforge3 in WSL Ubuntu (`conda create -n dicomifier-pilot -c conda-forge dicomifier pydicom`). Source data at `/mnt/d/projects/gjesus3/data_test/` (preserved from round-6 v2).

  **Test 1 — m13 protocol 0423 (no-DICOM target, 12 exams, mix of T1_FLASH / T2_TurboRARE / T1_RARE / Diffusion_weight_SE / 1_Localizer):**
  - Result: **all 12 exams converted cleanly**. 162 conformant DICOMs produced in a single flat folder via `dicomifier to-dicom --layout flat`. All series have correct slice counts matching source `2dseq` frame counts.
  - Curated tag coverage: `StudyInstanceUID` / `SeriesInstanceUID` / `SOPInstanceUID` populated; `Modality`=MR; `Manufacturer`="Bruker BioSpin MRI GmbH"; patient block from JCAMP-DX `subject` (`PatientID`, `PatientName`, `PatientSex`=O, `PatientWeight`); all MRI-specific tags present (`MagneticFieldStrength`=7.05T, `EchoTime`, `RepetitionTime`, `FlipAngle`, `ScanningSequence`, `SequenceVariant`); geometry (`Rows`/`Columns`/`PixelSpacing`/`SliceThickness`).
  - Minor gap: `ManufacturerModelName` not populated by Dicomifier (Bruker GUI fills with "Biospec 70/30"). One field, derivable from study context or accepted as gap.

  **Test 2 — m17 protocol 0424 exam 29 pdata/3 (side-by-side vs Bruker GUI export):** chose this exam because it has BOTH `fid` AND `pdata/3/dicom/MRIm01.dcm`..`MRIm15.dcm` from a previous Bruker-GUI export. Ran Dicomifier on the same source, compared the cardiac CINE series byte-by-byte.
  - **Slice count: identical** (15 vs 15).
  - **StudyInstanceUID + SeriesInstanceUID: EXACT MATCH** — both Dicomifier and Bruker GUI emit the same canonical ParaVision-assigned UIDs from `visu_pars`/`acqp`. This is the critical interop property: XNAT / PACS / OMERO would treat Dicomifier-regenerated DICOMs as the same study as Bruker-GUI-exported ones. `SOPInstanceUID` differs per-frame (expected — independently generated).
  - **Geometry parity:** Rows (128), Columns (256), SliceThickness (0.8mm), MRAcquisitionType (2D), `Modality`, `Manufacturer` — all EXACT.
  - **Acquisition parameters:** TE / TR / B0 / FlipAngle / NumberOfAverages — match to floating-point precision (Dicomifier preserves more decimal places; physically identical values).
  - **Patient info parity:** PatientID / PatientName / PatientSex / PatientBirthDate / PatientWeight — all EXACT or string-formatting-only diff.
  - **Findings worth flagging (none are blockers):**
    1. `SeriesDescription` and `ProtocolName` are *transposed* between Bruker GUI and Dicomifier (Bruker uses `Cine_slice_1_12` for SeriesDescription and `Cine_IG_FLASH` for ProtocolName; Dicomifier swaps them). Both fields populated correctly, just labelled differently. Easy to handle in our `_DICOM_CURATED_TAGS` extractor — fall back across both fields.
    2. `PixelSpacing` is *ordering-swapped*: Bruker `[0.1953125, 0.09765625]` (row, column) vs Dicomifier `[0.09765625, 0.1953125]`. For 128 rows × 256 columns, the Bruker ordering matches DICOM Part 3 convention (`[row spacing, column spacing]`). **Potentially a real Dicomifier bug** — would cause viewers strictly reading PixelSpacing to render the image axis-flipped. Worth confirming with a quick load into 3D Slicer / ITK-SNAP before integrating; if confirmed, file upstream issue. Workaround: swap in our extractor pre-ingest if needed.
    3. `SequenceVariant`: Bruker "SP" (Spoiled gradient), Dicomifier "NONE" — minor metadata gap, not blocking.
    4. `StudyDescription` is missing from Bruker but Dicomifier provides `"jrc_251016_m17_0424"` — Dicomifier WINS.
    5. `ImageType`: Bruker `[ORIGINAL, PRIMARY, OTHER]` vs Dicomifier `[ORIGINAL, PRIMARY, '', MAGNITUDE_IMAGE]` — Dicomifier provides the semantic MAGNITUDE_IMAGE tag, slightly more informative.

  **Conclusion:** Dicomifier works on ParaVision 7.0.0. UIDs round-trip identically through ParaVision's canonical UID assignment, so regenerated DICOMs are interoperable with the platform-archive originals. Two minor findings (PixelSpacing axis order + ProtocolName/SeriesDescription transpose) need quick visual verification in an imaging viewer, but neither blocks integration.

  **Next step (pending user confirmation Monday):** proceed to Phase 2 — write `tools/ingest/paravision_regen.py` calling Dicomifier as a subprocess; wire into ingest via a config flag (e.g. `auto_regenerate_dicom: true` in MRI YAML); apply to the 3 round-6 no-DICOM acquisitions via idempotent re-ingest. Verify PixelSpacing orientation in 3D Slicer before locking the integration design.

  **When this lands:** backfills empty-`.data/` placeholders via idempotent re-ingest with no other code changes. The `subject:` block work (§3.2) is independent — both can land in either order.
- [ ] **Enhanced MR / Multi-Frame DICOM evaluation.** The classic per-frame `.dcm` layout is why an MR acquisition lands as N files. The modern DICOM standard (Enhanced MR / Multi-Frame DICOM) puts all frames in one file — if we adopt it, we get back to one-primary-file-per-ACQ even for DICOM. Evaluate in connection with the previous future-task.
- [ ] **DICOM full-mode metadata extraction for collaborator XMRI** (existing §3.1 deferred item, independent of round-6 work). Will mirror the `.czi` pattern: curated `discovered.dicom_*` + structured `dicom:` sidecar block + full pydicom dump. Library: `pydicom`. Doesn't block any in-flight round; can be prototyped against the 75 existing XMRI acquisitions whenever.
- [ ] **User-as-operator permissions model for internal MRI / internal NI** (added 2026-05-22). Unlike microscopy, internal MRI and NI have no dedicated operator — researchers run the equipment themselves. Today the data office runs ingest under a shared platform-account identity. Future model needs an ingest-time write path to `/raw/` that respects the "raw is read-only after deposit" rule without requiring a dedicated technician account. Coordinate with the raw-immutability lockdown design (§4.3) and the project close-out tool's controlled-write path (§3.2). Open question to the platform managers: do they have user-accounts that could be used? Or should ingest always run under a service identity? Captured but not designed.
- [ ] **Internal Nuclear Imaging (NI) ingest round** — likely round 7 or 8, depending on when Unai answers the naming-convention question (§4.7). Conventions documented in [`equipment/nuclear-imaging/internal_ni_data_handling_workflow_notes.md`](../equipment/nuclear-imaging/internal_ni_data_handling_workflow_notes.md); per-instrument template will be cloned from `mri_bruker.yaml` and adapted. Pre-requisite work that's not blocked on Unai: design the tgz-aware staging step (below).
- [ ] **NI tgz nested-archive parsing** (future-round prep). NI data lands as `.tgz` archives on `\\cicmgsp02\gnuclear2$`; inside is a `.tar` containing the recon-level dir structure. Two options: (a) extract tgz → local staging area before `expand_batch` runs (simpler, matches the `ftp_mirror.py → ingest` pattern); (b) extend the ingest with a tgz-aware glob. Option (a) recommended. Will need a small `tgz_extract.py` utility or just a shell-out step before ingest. Documented in the NI workflow notes.
- [ ] **MRI naming-convention stakeholder follow-up** (added 2026-05-22). The platform's project-folder naming has a documented ambiguity: `<group PI initials><YYYYMMDD>` is sometimes written `jrc251016` (intended convention) and sometimes `jrc_251016` (with underscore). The round-6 `regex:` extractor handles both, but a long-term fix is to ask the platform manager to standardise. Captured in [`equipment/mri-platform/internal_mri_data_handling_workflow_notes.md`](../equipment/mri-platform/internal_mri_data_handling_workflow_notes.md) "Systematic naming convention" section.

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
  - [ ] **Project-level NIfTI generation tool** (NEW 2026-05-20, MRI-driven but generalizable). Reads chosen ACQ-IDs via the project's `raw_linked/` shortcuts, runs `dcm2niix` (or `bruker2nifti`) per acquisition, writes `<ACQ-ID>.nii.gz` under `/projects/<proj>/derived_nifti/`. Removed at project close-out — regenerable from raw if needed later. Aligns with the [13_GJESUS3_ROLE](../mfb-rdm-docs/13_GJESUS3_ROLE.md) reframe (research-facing derivatives belong in projects, not in `/raw/`). Library choice (dcm2niix subprocess vs bruker2nifti Python) TBD when implementation starts. Cross-referenced in [08_METADATA §1.5a](../mfb-rdm-docs/08_METADATA.md).
  - [ ] **Preclinical metadata auto-population — `subject:` + `condition:` blocks** (NEW 2026-05-29, expanded 2026-05-29). Spec landed in [08_METADATA §4.4](../mfb-rdm-docs/08_METADATA.md) (`subject:`) + [08_METADATA §4.5](../mfb-rdm-docs/08_METADATA.md) (`condition:`). Required for `sample_type ∈ {organism, tissue}` — always for internal MRI + NI, typically for animal-derived microscopy. The two blocks have different source pipelines but share a writer.

    **`subject:` block** — species / strain / sex / age_at_acquisition (4 required fields DECIDED) + optional fields. **Auto-populatable from animal-facility-DB once integration lands.** Per-subject, fixed.

    **`condition:` block** — `is_control` (DECIDED-required strict boolean), `disease_model` + `disease_state` (DRAFT-required free-text), optional `control_type` / `treatment` / `timepoint_days` / `study_arm`. **Operator-entered only** (no DB source — disease state is a property of study design, not the animal). Per-acquisition, varies.

    **4-phase work:**
    - [ ] **Phase 1 — Scope the animal-facility-DB API** (`subject:` only). Confirm DB system + query interface (REST? SQL? CSV export?), what fields it exposes per animal, auth model. **BLOCKED on IT** for programmatic access — request open with the IT team that's also working the QNAP permissions cleanup. Output: a one-page note documenting endpoint + auth + field-to-`subject:`-block mapping. (`condition:` block has no DB dependency — it's operator-entered.)
    - [ ] **Phase 2 — Write `tools/animal_db.py` fetcher** (`subject:` only). Function `lookup(facility_animal_id) -> dict` returning the populated `subject:` block (or empty dict + log warning if animal not in DB). Cache locally (idempotent re-runs shouldn't hammer the DB). Credentials from env var / config file outside repo, same pattern as `ftp_mirror.py`. Standalone unit test against a couple of known animal IDs.
    - [ ] **Phase 3 — Wire into ingest** (covers BOTH blocks). New YAML field `auto_discover.subject_from_db: true` (default false) for `subject:` DB-fetch. New top-level `condition:` YAML block (peer to `registry:`) for operator-entered condition data — resolver-evaluated, same `${discovered.<x>}` interpolation as `registry:`. `metadata_sidecar.py` writes both blocks:
       - For `subject:`: when `subject_from_db: true`, call `animal_db.lookup()` → write with `source: "animal-facility-db"`. Operator override via explicit `subject:` YAML block (overrides DB; `source: "operator-entered"`).
       - For `condition:`: read from YAML `condition:` block, resolve, write with `source: "operator-entered"` / `"study-yaml"`. **`is_control` REQUIRED-CHECK: writer raises if missing for `sample_type ∈ {organism, tissue}`** (DECIDED enforcement). `disease_model` + `disease_state` missing → WARN but continue (DRAFT enforcement; tighten to DECIDED via META-06 after pilot use).
       - Per-acquisition override (mixed-condition batches): `/projects/<proj>/metadata/<acq_id>.json` `condition:` overrides YAML batch-level.
       Documented in [10_TOOLS](../mfb-rdm-docs/10_TOOLS.md) once schema settles.
    - [ ] **Phase 4 — Backfill existing acquisitions.** Round-6 v2 MRI (97 acqs) + Round-8 v2.1 NI (84 acqs) + animal-derived microscopy (AxioScan 28 + Cell Observer 165 + LSM 900 13, to the extent samples are animal-derived) have neither `subject:` nor `condition:` blocks today. Two paths: (a) idempotent re-ingest after Phase 3 lands — re-walks staging, re-writes sidecar with both blocks; (b) standalone `subject_condition_backfill.py` that walks `/raw/` and adds both blocks in-place (controlled write to `/raw/` like the project close-out tool — coordinate with the raw-immutability lockdown design §4.3). Path (a) preferred when staging is around; (b) for acqs whose staging is gone. **`condition:` backfill needs operator recall** — Ryan + researcher will need to reconstruct disease/control state from study notebooks for the 246+ existing animal-derived acqs; queued for the post-exhibition true-production restart.
    - [ ] **Future enhancement:** add `subject:` + `condition:` field validation to `validate_registries` (Phase 4 of §3.2) — flag rows with `sample_type ∈ {organism, tissue}` whose sidecar's `subject:` is missing required fields OR whose `condition:` is missing `is_control`. Surfaces the gap during the quasi-production → true-production transition. The DECIDED-required `is_control` flag makes the "all controls" / "all cases" cohort-builder queries trivial; the writer-level check (Phase 3) catches new ingests, the validator catches the backfill backlog.

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

### 4.5 Pass 2: Platform DICOM — Internal MRI (`MRI`) — ✅ ROUND 6 v2 COMPLETE 2026-05-27 (97 acqs in quasi-production)

> **🔄 Round-6 v2 retrospective (2026-05-27):** following the NI v2/v2.1 work, the original round-6 v1 (2026-05-22) had three structural problems that mirror NI v1's: (a) JCAMP-DX aux files (acqp/method/visu_pars/subject/fid/pulseprogram/...) copied to disk under `acquisition_aux/` instead of parsed-only into the sidecar; (b) per-recon non-DICOM (2dseq/visu_pars/reco) copied to disk under `reconstructions/pdata_<idx>/` (same issue); (c) per-frame DICOMs buried at `reconstructions/pdata_<idx>/dicom/MRIm<NN>.dcm` instead of flat under `<ACQ-ID>.data/`. Also discovered: the v1 default `reconstructions: [3]` silently dropped image data for any exam without a pdata/3 (verified `ACQ-20251016-MRI-001` at 872 KB = aux files only, NO recons kept). 3 of 7 source projects have ZERO DICOMs (students hadn't run Bruker's exporter). **v2 fix:** full purge + new `copy_mri_paravision` selective-copy function in `tools/ingest_raw.py` (sister of `copy_ni_acquisition`); `paravision_metadata.py` refactored to emit per-DICOM `dicoms[]` under each recon (`dst_basename` `recon<idx>_frame<NN>.dcm`, curated `headers` with `StudyInstanceUID`/`SeriesInstanceUID`/`SOPInstanceUID` first + MRI-specific tags `MagneticFieldStrength`/`EchoTime`/`RepetitionTime`/`FlipAngle`/`ScanningSequence`/`SequenceVariant`); default `reconstructions: all` (DICOMs are tiny under the slim layout); `copy_strategy: mri_paravision_v2` selects between legacy `paravision_exam` and the new path; `primary_file_name = <ACQ-ID>.data` for MRI; .lnk target points at the `.data` subfolder (reuses NI v2.1 dispatch). **No-DICOM acquisition handling:** ingest registers placeholder acqs with empty `<ACQ-ID>.data/` + fully populated `mri:` sidecar from JCAMP-DX; idempotent re-run after the student runs Bruker's exporter dedupes properly. Future-work FID→DICOM regeneration capability (no open-source Python library exists; closed-source Bruker GUI is the only path today; 2-4 week research project) tracked in §3.1. **Plan file:** [the round-6 v2 plan](../../../.claude/plans/i-have-the-creds-reactive-candle.md).

### 4.5.v1 Pass 2 history — Round 6 v1 2026-05-20→05-22 (PURGED 2026-05-27 for v2)

> **Pickup context (read first if returning to this section cold):**
> - **This is round 6 of the pilot, in progress.** Internal MRI = Bruker ParaVision platform (two systems: 7T and 11.7T, three ParaVision versions coexist v3.6/v6/v7). NOT to be confused with collaborator XMRI (rounds 1-2, already deposited as zips).
> - **Access:** SFTP credentials obtained 2026-05-20. Sample data manually pulled to `D:\projects\gjesus3\data_test\` (one ParaVision study with ~10–16 numbered exams). Full access-strategy still in [`equipment/mri-platform/mri_data_access_strategy.md`](../equipment/mri-platform/mri_data_access_strategy.md) — Option A (FTP-from-workstation) is what we're executing.
> - **Round 6 reframe** ([13_GJESUS3_ROLE](../mfb-rdm-docs/13_GJESUS3_ROLE.md), 2026-05-20): gjesus3 is the research-facing working layer; the platform's own archive handles deep preservation. This justifies the no-zip / folder-as-primary layout for internal MRI.
> - **Acquisition unit:** examination (assay). One numbered ParaVision exam = one ACQ-ID. ISA terminology: investigation=project, study=session (`session_id` column DRAFT), assay=acquisition.
> - **Metadata source:** ParaVision JCAMP-DX aux files (`subject`/`acqp`/`method`/`visu_pars`/per-recon `visu_pars`+`reco`) are **canonical**, not DICOM headers. New `paravision_metadata.py` + `jcampdx.py` modules mirror the `.czi` extractor shape. Collaborator XMRI DICOM-header extraction stays deferred as an independent stream.
> - **Layout:** `/raw/DICOM/<year>/<year-month>/ACQ-<date>-MRI-<exam>/` with `metadata.json` + `checksums.json` at the root, `reconstructions/pdata_<idx>/` subfolders (per `reconstructions:` YAML flag), `acquisition_aux/` for exam-level aux files. No zip. `primary_kind: folder` in the registry.
> - **Two MRI systems** (Bruker BioSpec 11.7T and 7T) — open question whether they need separate instrument codes or share `MRI`. Default: share, until evidence pushes otherwise.
> - **NIfTI conversion is OUT OF SCOPE** for this round at `/raw/` ingest. Project-level NIfTI generation tool tracked in §3.2 as future work. The platform's own NIfTI from `tools.all2nifti.sh` may or may not be in the source data; we don't depend on it.
> - **Plan file:** [the round-6 plan](../../../.claude/plans/i-have-the-creds-reactive-candle.md) has the full design + sizing.

**Prerequisites:**
- [x] ~~SFTP credentials obtained~~ — 2026-05-20.
- [x] ~~Sample data pulled to `D:\projects\gjesus3\data_test\`~~ — one ParaVision study with ~10–16 numbered exams.
- [x] ~~Confirm DICOM and/or NIfTI is on the source~~ — sample shows: ParaVision `2dseq` + Bruker-exported `.dcm` per reconstruction (when student ran Bruker exporter; 3 of 7 v2 source projects had no DICOMs); NIfTI not present. NIfTI generation deferred to project-level tool per [13_GJESUS3_ROLE §5.3](../mfb-rdm-docs/13_GJESUS3_ROLE.md).

**Stream A — Documentation (committed `17ac781` 2026-05-20):**
- [x] ~~[13_GJESUS3_ROLE.md](../mfb-rdm-docs/13_GJESUS3_ROLE.md) — NEW (the reframe doc).~~
- [x] ~~[01_OVERVIEW.md](../mfb-rdm-docs/01_OVERVIEW.md) §2 + §5.3 reframe.~~
- [x] ~~[03_RAW_STORAGE.md](../mfb-rdm-docs/03_RAW_STORAGE.md) — per-ecosystem layouts + MRI folder exception in §4.~~
- [x] ~~[06_REGISTRIES.md](../mfb-rdm-docs/06_REGISTRIES.md) §2.3a ISA terminology + DRAFT `session_id` + `primary_kind` columns.~~
- [x] ~~[08_METADATA.md](../mfb-rdm-docs/08_METADATA.md) §4.3 `mri:` block + project-level tool family additions.~~
- [x] ~~[10_TOOLS.md](../mfb-rdm-docs/10_TOOLS.md) §2.1.2b ParaVision extractor + §2.1.3 `regex_extract:` + `ingest:` flags table updates.~~
- [x] ~~[tasks.md §0 + §3.1 + §3.2](.) — round-6 active state + future-work entries.~~

**Stream B — Extractor + JCAMP-DX parser + probe (committed `66887ae` 2026-05-21):**
- [x] ~~`tools/ingest/jcampdx.py` (NEW) — JCAMP-DX text parser (~80 LOC).~~
- [x] ~~`tools/ingest/paravision_metadata.py` (NEW) — extractor mirroring `czi_metadata.py` (~250 LOC).~~ Rewritten in v2 (2026-05-27, commit `f5fefa5`) to emit per-DICOM `dicoms[]` lists with UIDs first + MRI-specific tags.
- [x] ~~`tools/ingest/filename_parser.py` — add optional `regex:` extraction (~30 LOC).~~
- [x] ~~`tools/ingest/config.py` — wire ParaVision dispatcher under `FORMAT_EMBEDDED_EXTRACTORS["DICOM"]` (content-based detect).~~
- [x] ~~`tools/ingest/probe_paravision.py` (NEW) — probe utility (~40 LOC).~~
- [x] ~~**Probe verification** — confirmed `discovered.mri_*` fields populate from sample data.~~

**Stream C — Ingest pipeline + per-instrument template + per-batch config + FTP retrieval (committed `943fd3e` 2026-05-22):**
- [x] ~~`tools/ingest/config.py` — add `acquisition_layout: file | archive | folder` flag~~. v2 added `copy_strategy:` for per-instrument copy-function selection (commit `f5fefa5`).
- [x] ~~`tools/ingest_raw.py` — honour `reconstructions:` and no-zip folder layout for MRI.~~ v2 replaced v1's `copy_paravision_exam` with the slim `copy_mri_paravision` (mirrors `copy_ni_acquisition`).
- [x] ~~`tools/templates/instruments/mri_bruker.yaml` (NEW) — per-instrument template.~~ Updated in v2 (`copy_strategy: mri_paravision_v2`, `reconstructions: all` default).
- [x] ~~`tools/configs/mri_bruker_20251016_TEST.yaml` (NEW) — first per-batch config against `D:\projects\gjesus3\data_test\`.~~
- [x] ~~**Dry-run + real ingest** against the sample.~~ v1: 97/97 success (with link-collision bug — see Stream D). v2: 97/97 success with slim shape + no-DICOM placeholders for 3 of 7 projects.
- [x] ~~**Idempotency check** — re-run, verify zero duplicate rows.~~
- [x] ~~`tools/ftp_mirror.py` (NEW) — SFTP CLI via `paramiko`.~~

**Documentation (during / after the pass):**
- [x] ~~[09_MODALITIES.md](../mfb-rdm-docs/09_MODALITIES.md) MRI section — per-instrument `discovered.mri_*` fields table.~~ Done (committed `66887ae` 2026-05-21, refined in v2 commit `f5fefa5`).
- [x] ~~[08_METADATA.md](../mfb-rdm-docs/08_METADATA.md) §4.3 — `mri:` sidecar block shape (committed in Stream A 17ac781).~~
- [x] ~~[10_TOOLS.md](../mfb-rdm-docs/10_TOOLS.md) §2.1.2b — ParaVision extractor; §2.1.3 — `regex_extract:`; §2.1.5 — `link_filename:` (committed in Stream A 17ac781 + Stream D).~~
- [x] ~~[equipment/mri-platform/internal_mri_data_handling_workflow_notes.md](../equipment/mri-platform/internal_mri_data_handling_workflow_notes.md) — new "Systematic naming convention" section (2026-05-22).~~
- [x] ~~[equipment/nuclear-imaging/internal_ni_data_handling_workflow_notes.md](../equipment/nuclear-imaging/internal_ni_data_handling_workflow_notes.md) — NEW doc capturing NI convention for the future round (2026-05-22).~~
- [x] ~~`00_INDEX.md` — version history.~~ 2026-05-22 (Round-6 v1) + 2026-05-27 (Round-6 v2 redo) + 2026-05-29 (Dicomifier pilot) entries all landed.

**Stream D — round-6 follow-up (committed `943fd3e` 2026-05-22):**
The first round-6 ingest (97/97 success against `D:\projects\gjesus3\data_test\`) surfaced two bugs that the round-6 plan was extended to fix:
1. **Sidecar key `dicom:` should be `mri:` for ParaVision data.** Fixed: extractor dispatcher returns a 3-tuple `(discovered, section, "mri")` to override the ecosystem-derived section name. See `tools/ingest/config.py::_extract_dicom_embedded`.
2. **`.lnk` filename collisions** — 35 of 97 shortcuts silently lost because exam numbers (e.g. `27.lnk`) clash when multiple animal sessions land in the same project. Fixed via new top-level `link_filename:` YAML field; per-instrument templates ship recommended defaults. MRI default: `MRI_${sample_id}_${acq_date}_${discovered.mri_exam_number}_${discovered.mri_recon_indices}`. See [10_TOOLS §2.1.5](../mfb-rdm-docs/10_TOOLS.md).

**Outstanding (v1):**
- [x] ~~**Purge** the first-ingest 97 acqs~~ — done 2026-05-22 prior to v1 Stream-D re-ingest.
- [x] ~~**Re-ingest** with the new `link_filename` pattern.~~ — done 2026-05-22; 97 unique `.lnk` names, `metadata.json.mri` populated, cross-modality demo verified.
- [x] ~~**Commit Stream C + Stream D** as one atomic round-6 changeset~~ — `943fd3e` (Stream C+D end-to-end).

**v2 reshape (2026-05-27, committed `f5fefa5`):**
The round-6 v1 surface had the same three structural problems NI v1 had — JCAMP-DX aux files copied to disk, per-recon non-DICOM copied to disk, per-frame DICOMs buried in subfolders. Also discovered: default `reconstructions: [3]` silently dropped image data for any exam without pdata/3, and 3 of 7 source projects had ZERO DICOMs (no-DICOM acquisition handling required).
- [x] ~~Full purge of v1 97 acqs.~~
- [x] ~~New `copy_mri_paravision` selective-copy function (sister of `copy_ni_acquisition`).~~
- [x] ~~`paravision_metadata.py` refactored to emit per-DICOM `dicoms[]` under each recon.~~
- [x] ~~Default `reconstructions: all`; `copy_strategy: mri_paravision_v2`.~~
- [x] ~~No-DICOM acquisition handling — empty `<ACQ-ID>.data/` placeholder + fully populated `mri:` sidecar from JCAMP-DX.~~
- [x] ~~Re-ingest 97 acqs in v2 shape.~~
- [x] ~~Verification — all docs synced (`03_RAW_STORAGE §4.4`, `08_METADATA §4.3`, `09_MODALITIES §1.4`, equipment workflow notes).~~

**Recovery path for no-DICOM placeholders (3 acqs):** Dicomifier 2.5.3 pilot validated on PV 7 (2026-05-29) — see §3.1 for the integration plan. Phase 2 pending user confirmation Monday.

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
- [x] ~~`mfb-rdm-docs/09_MODALITIES.md` §1.2 (Cell Observer) — per-instrument `discovered.czi_*` fields table~~ — implicit via §1.1's "applies equally to CELL and LSM9" note (shared .czi extractor). Explicit table not needed; cross-reference suffices.
- [ ] `mfb-rdm-docs/11_OPERATIONS.md §3.2` Quick Start — refactor AxioScan-specific examples now that 3+ instruments are validated. Tracked under §3.1 multi-instrument-Quick-Start follow-up.
- [x] ~~`mfb-rdm-docs/00_INDEX.md` — round-5 entry~~ — 2026-05-18 entry landed.

**Deferred from this pass (queued for later):**
- [ ] **Animal/histology-mode Cell Observer template** — needs a real example folder of historical histology work (likely from a different researcher's older folder). The pipeline machinery is the same; only the YAML differs. Each historical batch / researcher convention probably needs its own per-batch config. Plan: one `cell_observer_histology.yaml` template once we have a representative example.
- [ ] **Historical Cell Observer histology backfill** — separate stream from going-forward cells-mode work. Operators used Cell Observer heavily for histology before AxioScan arrived; that data still needs ingest. Different researchers, different conventions per researcher / era. Use the same machinery, one per-batch YAML per historical batch.
- [ ] LSM 900 (§4.6.C) — should reuse most of the Cell Observer cells-mode template once validated; same instrument family, same data-handling model per the operator.

**4.6.C LSM 900 confocal (`LSM9`) — ROUND 7 ACTIVE 2026-05-22:**

> **Pickup context (read first if returning cold):**
> - LSM 900 is a Zeiss confocal microscope (Room 2.66). Third .czi-family instrument; `tools/ingest/czi_metadata.py` reuses 1:1 (no new code needed). Confirmed by probe: 21 `discovered.czi_*` fields populate.
> - Same operator (Ainhize Urkola Arsuaga) + same K: share + same `Ainhize/` parent folder as Cell Observer. Subfolder: `CONFOCAL LSM 900/`.
> - Distinguishing fingerprint vs Cell Observer: `czi_acquisition_mode = "LaserScanningConfocalMicroscopy"` (Cell Observer = `"WideField"`). `czi_microscope_name` reports `"Axio Observer.Z1 / 7"` — same as Cell Observer (the LSM 900 sits on an Axio Observer stage), so the name alone isn't a reliable distinguisher.
> - Per-instrument template at `tools/templates/instruments/lsm900.yaml` ships with a folder-name regex extracting `researcher / experiment / cell_line` from the batch folder convention `<researcher>_<experiment-w/-internal-underscores>_<cell_line>`. Filename positional parse is **deferred** (real-data chunk count varies 4–6; would skip too many files).
> - First batch: `LAURA_UPTAKE_LP-IONP-doxo_MDA` (~14 .czi files). Operator directions + parsable naming convention captured in `equipment/lsm900/lsm900_data_handling_workflow_notes.md`.

**Prerequisites (done 2026-05-22):**
- [x] ~~**Ainhize:** Provide one detailed `.czi` example from the LSM 900.~~ Received: `LAURA_UPTAKE_LP-IONP-doxo_MDA` batch on K: share.
- [x] ~~**Ryan:** Probe one .czi via `probe_czi.py`.~~ 21 `discovered.czi_*` fields populated; LSM 900 fingerprint confirmed.

**Execution (round 7) — ✅ COMPLETE 2026-05-22 (commit `2bbbf4d`):**
- [x] ~~Create `tools/templates/instruments/lsm900.yaml`~~ — done 2026-05-22.
- [x] ~~Author the first per-batch TEST config (`tools/configs/lsm900_laura_uptake_TEST.yaml`)~~ — done 2026-05-22.
- [x] ~~Capture operator directions + parsable naming convention in `equipment/lsm900/lsm900_data_handling_workflow_notes.md`~~ — done 2026-05-22.
- [x] ~~Dry-run + real ingest of the LAURA_UPTAKE batch.~~ — done 2026-05-22; 13 acqs (one excluded by filter; original estimate of 14 was off-by-one).
- [x] ~~Verify NAS state: `proj-laura` auto-created, `LSM9_*.lnk` shortcuts, sidecar `microscopy:` block populated.~~ — 13/13 confirmed.

**Documentation (during / after the pass):**
- [x] ~~`mfb-rdm-docs/09_MODALITIES.md` §1.3 LSM 900 — round-7 status update, cross-ref workflow notes~~ — done 2026-05-22.
- [x] ~~`mfb-rdm-docs/00_INDEX.md` — version history~~ — 2026-05-22 entry landed.

**Deferred from this pass (queued for later):**
- [ ] **Filename positional parse for LSM 900.** Real-data chunk count varies (4–6); a positional spec would skip half the files. The .czi-embedded metadata + the folder regex give us most of what we need at registry level; filename-only fields (condition / timepoint / replicate) can land in project-level metadata via the `/projects/<proj>/metadata/<acq_id>.json` flow. A future enhancement (per-component `source:` for `filename_parse` so the regex can target `parent_name` while a separate positional spec targets the filename) is the cleanest path when an operator asks for filename-chunk metadata at registry-row level.
- [ ] **Other LSM 900 batches** (Claudia, IFF, IRENE, ITZIAR, MARINA, Lysotracker, etc.) on the K: share. Each gets its own per-batch config; the template stays stable. Add as the operators request them.
- [ ] **`Free doxo/` subfolder inside LAURA_UPTAKE_LP-IONP-doxo_MDA.** Excluded from round 7 (non-recursive pattern). Include via a separate batch config if needed.

**4.6.D Lightweight mode for microscopy:**
- [ ] Test `--lightweight` mode on one `.czi` file (sets `extended_metadata_present=N`, no sidecar)

### 4.7 Pass 4: Nuclear Imaging — ✅ ROUND 8 v2.1 LANDED 2026-05-27 (archive mode, 84 acqs in quasi-production)

> **Round 8 split into two streams:**
> - **Archive mode (active 2026-05-22):** ingest pre-archived `.tgz` files from `\\cicmgsp02\gnuclear2$\<year>\<PI>\`. Validates the framework against representative NI data while the live-machine workflow conversation continues.
> - **Live-machine mode (still blocked):** waiting on Platform Manager Unai to answer one outstanding question on the workflow + naming convention. Will get its own per-instrument template + per-batch config when ready.
>
> Both modes are documented in [`equipment/nuclear-imaging/internal_ni_data_handling_workflow_notes.md`](../equipment/nuclear-imaging/internal_ni_data_handling_workflow_notes.md).

**Round-8 archive-mode scope (Jesus's 2025 archive):**

| Series ID | Date(s) | Animals | PET | CT | Notes |
|---|---|---|---|---|---|
| 0525 | 251029 | m13–m22 | 12 | 12 | All one session date |
| 1207 | 251021 + 3 dates | various | 30 | 30 | Multi-visit study |
| **Total** | | | **42** | **42** | **84 .tgz archives, ~298 GB compressed** |

All from operator `irene` under PI Jesus. All Molecubes (PET + CT modalities; no SPECT/OI in this archive).

**Pipeline (orchestrated by the operator):**

1. **Extraction:** `python tools/extract_ni_archives.py --archive-root "//cicmgsp02/gnuclear2\$/2025/Jesus/" --staging "D:/projects/Nuke/test_data/"` — pulls each `.tgz`, extracts with `--strip-components=6` to its own folder under D:. Idempotent (`.extracted` sentinel). Retry-hardened against transient `WinError 59` SMB drops (observed in the round-8 first run on 2026-05-22).
2. **Ingest:** `python tools/ingest_raw.py --config tools/configs/ni_jesus_archive_2025_TEST.yaml --nas-root J:/` — folder-as-primary ingest from the staged copies. Idempotent via the registry's (acquisition_date, original_name) dedup.

**Files created (2026-05-22):**
- [`tools/extract_ni_archives.py`](../tools/extract_ni_archives.py) — SMB → staging extraction utility.
- [`tools/templates/instruments/molecubes_ni.yaml`](../tools/templates/instruments/molecubes_ni.yaml) — per-instrument template with exhaustive `discovered.*` reference card.
- [`tools/configs/ni_jesus_archive_2025_TEST.yaml`](../tools/configs/ni_jesus_archive_2025_TEST.yaml) — round-8 batch config.

**Files updated (2026-05-22):**
- [`tools/ingest/resolver.py`](../tools/ingest/resolver.py) — `normalize_acquisition_datetime` now handles the 14-digit `YYYYMMDDhhmmss` form from Molecubes archive names.
- [`equipment/nuclear-imaging/internal_ni_data_handling_workflow_notes.md`](../equipment/nuclear-imaging/internal_ni_data_handling_workflow_notes.md) — rewritten for archive mode + corrected the earlier "DICOM .dcm at leaf" claim (Molecubes is .bin + XML aux).

**Execution checklist (round 8 archive-mode):**

- [x] ~~Pilot: 2 archives (m13 PET + m13 CT, series 0525) end-to-end.~~ Done 2026-05-22; both landed in `proj-ae-biomegune-0525` with cross-modality session_id grouping confirmed.
- [x] ~~Full extraction of all 84 .tgz to D:/projects/Nuke/test_data/.~~ Done 2026-05-22 — 82 extracted + 2 skipped (pilot dedup) in 82 minutes; 374 GB total unpacked.
- [x] ~~Full ingest of all 84 acquisitions to NAS.~~ Done 2026-05-22 — 82/82 success (+ 2 pilot already there) in ~2 hours.
- [x] ~~Verify on NAS.~~ 84 NI registry rows (42 PET + 42 CT). proj-ae-biomegune-0525: 48 NI .lnk shortcuts (series 0525 m13–m22 PET+CT + 1207-series animals with `short_project=0525`). proj-ae-biomegune-0424: 36 NI .lnk shortcuts (1207-series animals with `short_project=0424`). All `metadata.json.dicom` blocks empty as designed (no NI XML-aux extractor yet).
- [x] ~~00_INDEX.md version history entry.~~

**Live-machine workflow follow-up (future, not in scope this round):**
- [ ] **Ryan:** Resolve the open question with Unai on the naming convention; submit data-workflow documentation + example.
- [ ] Once unblocked: design and ship a live-mode per-instrument template (`molecubes_ni_live.yaml` or similar). Source = a folder on the acq machine, not a .tgz on the archive. Different inner structure, possibly DICOM/NIfTI exports.

**Deferred (queued in §3.1 or §3.2):**
- [x] ~~**NI XML-aux metadata extractor**~~ — landed in round-8 v2 (2026-05-27, commit `f5fefa5`). `tools/ingest/ni_metadata.py` + `ni_xml.py` parse `protocol.txt` + the three XML aux files (`protocol.xml`/`acqparams.xml`/`recontemplate.xml`) + per-recon `reconparams.xml`. Populates ~15 `discovered.ni_*` fields + structured `ni:` sidecar block (study / subject / acquisition / reconstruction buckets + lossless `_raw_metadata`).
- [ ] **MILabs VECTor format check** — when MILabs data appears in our archives, audit its inner structure (it may differ from Molecubes; the platform description says it exports both DICOM and NIfTI).
- [ ] **User-as-operator permissions** for internal NI — same model gap as internal MRI (§3.1 future work).

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

- [ ] Define intake roles: who can promote staging to raw (OPS-01) — partial resolution via the User / Operator / Data Mgmt Lead role split (DECIDED 2026-05-12, see [11_OPERATIONS §1.1](../mfb-rdm-docs/11_OPERATIONS.md)); concrete "who" assignments still open per-instrument.
- [ ] **Configure NAS user/group permissions (OPS-02)** — ⏳ ACTIVE 2026-05-29. Plan: two QNAP groups (`pilot-users` R on share root + RW on projects/publications/staging; `pilot-operators` R on share root + RW on raw/registries). Blocked on IT — Ryan handed over the plan; IT confirmed Windows-Explorer-set ACLs don't propagate cleanly and that the existing folder creation method left orphan ACL entries. Awaiting IT to (a) define groups in QNAP web admin + (b) apply ACLs server-side. See `icacls J:\raw` baseline captured 2026-05-29.
- [x] ~~Write Quick Start guide for pilot users (OPS-03)~~ — done 2026-05-12; researcher Quick Start in [11_OPERATIONS §3.2](../mfb-rdm-docs/11_OPERATIONS.md); CLI reference at [`tools/INGEST_CLI.md`](../tools/INGEST_CLI.md). Needs multi-instrument refactor (currently AxioScan-specific examples) — tracked in §3.1.
- [ ] Schedule pilot start date (OPS-04) — moot; pilot is in **quasi-production state** with 462 acqs ingested across 6 instruments (rounds 1-2 / 4 / 5 / 6 / 7 / 8). True production restart scheduled after team exhibition (all quasi-production data purged + re-ingested with exhibition feedback).
- [ ] Set pilot review cadence (weekly for 4-6 weeks) — defined in 11_OPERATIONS, not yet scheduled (effectively continuous via the per-round ingest cycle).

---

## 7. Infrastructure

- [ ] Backup strategy — RAID 5 only, no offsite; define minimal mitigation
- [ ] Snapshot retention policy and restore procedure — snapshots confirmed active, details TBD
- [ ] Filesystem type confirmation — affects linking method and permission enforcement (resolved during Section 4.3)
- [ ] Raw immutability enforcement mechanism — chmod vs QNAP SMB ACLs; script vs manual (resolved during Section 4.3)

---

## 8. Deferred

- [ ] Curated datasets area — circle back after RAW ingestion is working (12_CURATED_DATASETS, EVALUATING)
- [x] ~~Raw data linking method for publications/projects~~ — **Resolved 2026-05-05:** Windows `.lnk` shell shortcuts (pilot-specific Windows-first choice). See [10_TOOLS §2.1.1](../mfb-rdm-docs/10_TOOLS.md#211-project-linking--windows-first-design-decision).
- [ ] Filename parser for legacy uploads — deprioritized
- [ ] User-supplied metadata workflows (CSVs/Excel for sample context) — partial: the Excel → study-metadata importer is now planned in §3.2 (study-metadata work stream); the broader sample-context workflows still deferred to post-pilot.
- [ ] GUI wrappers for tools — deferred to post-pilot based on user feedback
- [ ] Operator encoding in ACQ-ID — registry only for now (RAW-01)
