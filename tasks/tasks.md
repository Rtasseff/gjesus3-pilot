# MFB gjesus3 RDM Pilot — Task List

**Last Updated:** 2026-03-06

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

### 2.1 Data Types Inventory
- [x] ~~Data types sign-up sheet created~~ — done (09_MODALITIES Section 3)
- [ ] Complete data type sign-up sheet — need volunteer owners per type (MOD-02)
- [ ] Conduct show-and-tell walkthrough for each confirmed data type (MOD-03)
- [ ] Collect one representative example dataset per type for script testing

### 2.2 Instrument Metadata Audit
- [ ] Examine sample .czi files from Axiocam 7 (WSI) for embedded metadata fields
- [ ] Examine sample .czi files from Cell Observer for embedded metadata fields
- [ ] Examine sample .czi files from LSM 900 for embedded metadata fields
- [ ] Confirm Cell Observer and LSM 900 .czi metadata is similar to WSI .czi (MOD-07)
- [ ] Examine sample DICOM from MRI platform for relevant fields
- [ ] Examine sample DICOM from Nuclear Imaging platform for relevant fields
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

### 3.1 Ingest Pipeline
- [x] ~~`ingest_raw.py` implemented~~ — single-case, batch, interactive, dry-run modes
- [ ] Implement full-mode ingest additions: DICOM metadata extraction, DICOM compression, metadata.json sidecar generation
- [ ] Implement `--lightweight` flag in `ingest_raw.py`
- [ ] Implement `backfill_metadata` utility for upgrading lightweight ingests

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

## 4. Staging Data — Ingestion

### 4.1 HPIC Dataset (33 cases, ~15 GB compressed)
- [x] ~~Backup originals to `staging/_originals_backup/`~~
- [ ] Extract all archives in place in staging (unrar/unzip)
- [ ] Inspect extracted DICOM contents (verify structure, count files, check headers with pydicom)
- [ ] Test ingestion: dry-run on one HPIC case, then real run, verify outputs
- [ ] Batch ingest all 33 HPIC cases
- [ ] Post-ingestion verification (registry completeness, checksum spot-check, Windows SMB access)

### 4.2 LIONS Dataset (42 cases, ~36 GB compressed)
- [x] ~~Backup originals to `staging/_originals_backup/`~~
- [ ] Extract all archives in place in staging
- [ ] Inspect extracted DICOM contents
- [ ] Batch ingest all 42 LIONS cases
- [ ] Post-ingestion verification

---

## 5. Operations

- [ ] Define intake roles: who can promote staging to raw (OPS-01)
- [ ] Configure NAS user/group permissions (OPS-02)
- [ ] Write Quick Start guide for pilot users (OPS-03)
- [ ] Schedule pilot start date (OPS-04)
- [ ] Set pilot review cadence (weekly for 4-6 weeks) — defined in 11_OPERATIONS, not yet scheduled

---

## 6. Infrastructure

- [ ] Backup strategy — RAID 5 only, no offsite; define minimal mitigation
- [ ] Snapshot retention policy and restore procedure — snapshots confirmed active, details TBD
- [ ] Filesystem type confirmation — affects linking method options (symlinks, hard links)
- [ ] Test `.lnk` and symlink on NAS from Windows — determines linking method for project/publication raw references

---

## 7. Deferred

- [ ] Curated datasets area — circle back after RAW ingestion is working (12_CURATED_DATASETS, EVALUATING)
- [ ] Raw data linking method for publications/projects — blocked on filesystem/symlink testing
- [ ] Filename parser for legacy uploads — deprioritized
- [ ] User-supplied metadata workflows (CSVs/Excel for sample context) — deferred to post-pilot
- [ ] GUI wrappers for tools — deferred to post-pilot based on user feedback
- [ ] Operator encoding in ACQ-ID — registry only for now (RAW-01)
