# 06 — Registries

**Parent:** [Documentation Index](00_INDEX.md)
**Status:** 🔶 Draft
**Last Updated:** 2026-05-12

---

## Purpose

This document specifies the top-level registries that index and document the contents of the storage areas.

---

## 1. Overview

### 1.1 What Are Registries?

Registries are **CSV files** that serve as indexes (manifests) for each storage area. When data is added to the system, an entry is "registered" by adding a row to the appropriate registry.

### 1.2 Registry Locations

> **✅ DECIDED:** All registries live in a single top-level `registries/` directory — centralized, not distributed within each storage area.

| Registry | Location | Purpose |
|----------|----------|---------|
| Raw Registry | `/gjesus3/registries/registry_raw.csv` | Indexes all raw acquisitions |
| Publications Registry | `/gjesus3/registries/registry_publications.csv` | Indexes all publication folders |
| Projects Registry | `/gjesus3/registries/registry_projects.csv` | Indexes all project folders |
| Curated Datasets Registry | `/gjesus3/registries/registry_datasets.csv` | Indexes all curated datasets (if used) |

### 1.3 Why CSV?

| Consideration | CSV Advantage |
|---------------|---------------|
| Human-readable | Can open in any text editor or spreadsheet |
| Tool-friendly | Easy to parse, query, update with scripts |
| Version control | Works well with git if we version registries |
| No dependencies | No database setup or special software |
| Recovery | Even if corrupted, partial data is recoverable |

**Limitation:** Concurrent writes need care (but our low-volume use case makes this manageable).

---

## 2. Raw Registry

**File:** `/gjesus3/registries/registry_raw.csv`

### 2.1 Purpose

Authoritative record of all raw acquisitions deposited in the system.

### 2.2 Schema

> **✅ DECIDED:** Fields are classified by **Population** method — how they get filled during ingest. This enables lightweight mode to produce sparse-but-valid registry entries.

| Field | Type | Required | Population | Description |
|-------|------|----------|------------|-------------|
| `acq_id` | String | ✅ Yes | Auto | Unique acquisition ID (e.g., `ACQ-20260215-ZWSI-001`) |
| `registration_datetime` | ISO DateTime | ✅ Yes | Auto | When this entry was added |
| `acquisition_datetime` | ISO DateTime | 🔶 Recommended | User | When the data was actually acquired. User-supplied via the YAML `registry:` block — either a literal, a `discovered.<field>` reference (e.g. `discovered.acquisition_date` for AxioScan day folders), or `NA` to backfill later. Future: auto-extract from DICOM/.czi headers via the `discovered` namespace. |
| `data_ecosystem` | String | ✅ Yes | User | `MICROSCOPY`, `DICOM`, or `EM`. Determines the top-level folder. |
| `instrument` | String | ✅ Yes | User | Instrument code (e.g., `ZWSI`, `LSM9`, `PET`). |
| `instrument_model` | String | 🔶 Recommended | User | Full instrument name (e.g., `Bruker BioSpec 11.7T`). |
| `modalities_in_study` | String | Optional | User (or auto fallback) | For multi-modal acquisitions: semicolon-separated DICOM modality codes (e.g., `PT;CT`). If left empty/NA, falls back to the source summarizer's `modality` field. |
| `operator` | String | ✅ Yes | User | Person who collected the data. |
| `data_source` | String | ✅ Yes | User | `internal` or `collaborator:<name>`. |
| `sample_id` | String | 🔶 Recommended | User | Sample or animal identifier. See §2.3 for the recommended composite format. |
| `sample_type` | String | 🔶 Recommended | User | Category of biological material. Use the controlled vocabulary in §2.4 (DRAFT). |
| `primary_file_name` | String | ✅ Yes | Auto | Canonical name of the primary file (`<ACQ-ID>.<ext>` for microscopy / `<ACQ-ID>.zip` for DICOM, or `series/` for the legacy DICOM uncompressed layout). |
| `original_name` | String | ✅ Yes | Auto | Source filename / folder name before ingestion. |
| `file_format` | String | ✅ Yes | Auto | File extension/format (e.g., `.czi`, `.zip`). |
| `file_size_mb` | Number | ✅ Yes | Auto | Size of primary file/folder in **decimal MB** (bytes ÷ 1,000,000), rounded to 1 decimal. Convention adopted 2026-05-12; pre-cutover rows hold the binary value (bytes ÷ 1,048,576) and are not being backfilled. Windows Explorer uses its own hybrid (bytes ÷ 1024 ÷ 1000) and will not match either form exactly. |
| `file_count` | Number | ✅ Yes | Auto | Number of **primary-data files** in the acquisition — not auxiliary or bookkeeping artifacts (`metadata.json`, `checksums.json`, `README.txt`). DICOM: count of `.dcm` (or extensionless DICOM) files. Microscopy: `1` for single-file (`.czi`) acquisitions; for folder-mode batches, count of primary-format files (`.czi`/`.tif`/`.tiff`). Convention adopted 2026-05-12; pre-cutover DICOM rows hold an uninformative count (4 = destination-folder file count) and are not being backfilled. Once DICOM compress-on-ingest ships, the count should come from the archive's central directory rather than the source walk. |
| `canonical_path` | String | ✅ Yes | Auto | Full path to acquisition folder. |
| `checksum_present` | String (Y/N) | ✅ Yes | Auto | `Y` or `N` — is checksums.json present? |
| `extended_metadata_present` | String (Y/N) | ✅ Yes | Auto | `Y` (full mode) or `N` (lightweight mode). |
| `project_hint` | String | Optional | User | Associated project ID if known at deposit. Triggers `.lnk` creation when set. |
| `ingest_config` | String | 🔶 Recommended | Auto | Path (relative to repo root) of the YAML config that produced this row. Empty for interactive ingests or pre-2026-05-06 rows. Used for auditability and reproducibility. |
| `notes` | String | Optional | User | Free-text notes. Supports `${discovered.<field>}` interpolation. |

**Population key:**
- **Auto** — set by the ingest pipeline; user must NOT put it in the YAML `registry:` block.
- **User** — set in the YAML `registry:` block (literal, `discovered.<field>`, or `NA`). See [10_TOOLS §2.1](10_TOOLS.md).

### 2.3 Sample ID Format (DRAFT)

> **🔶 DRAFT pilot guidance.** Recommended `sample_id` format is `<short_project>_<short_sample>`. Status remains open (REG-01) pending PI sign-off after pilot validation.

The `sample_id` chunk recorded by an instrument (e.g. `ID26H` on an AxioScan filename) is typically **not unique on its own** — the same short ID gets reused across projects. The combination `<short_project>_<short_sample>` (e.g. `0525_ID26H`) is what makes a row globally identifiable within `registry_raw.csv`.

**Recommended pattern** (apply via YAML interpolation; no code change needed):

```yaml
registry:
  sample_id: "${discovered.project}_${discovered.sample_short}"
```

This composes the registry value at ingest time from filename chunks. The raw chunks remain in the per-acquisition `metadata.json` `discovered` block (alongside any auto-extracted embedded fields), so the decomposition is never lost.

**Notes:**

- If a `<short_project>` is genuinely unset (no project chunk in the filename), leave `sample_id` as the bare short ID and accept that uniqueness is project-scoped only. Flag in `notes`.
- This convention does **not** override official sample identifiers when they exist as a single string already (e.g. an animal registry ID like `MOUSE-2024-042`). Use those verbatim in `sample_id` and skip the composite.
- Organ-letter encoding inside the short ID (e.g. `H` = Heart, `B` = Brain in `ID26H`) is not parsed today; team convention is not yet confirmed. Tracked as a future enhancement.

### 2.4 Sample Type Vocabulary (DRAFT)

> **🔶 DRAFT pilot guidance.** `sample_type` is the category of biological material in REMBI terms — *not* the species and *not* the anatomy. Status open (REG-07) pending PI sign-off.

REMBI separates concerns: **sample type** (the kind of biological material), **organism/species**, **anatomical entity**, **preparation**, and **imaging mode**. In the current registry only one of these has its own column (`sample_type`); the others ride along in `sample_id` / `notes` for now (see future split tracked in `tasks/tasks.md` §3.1).

**Controlled vocabulary** — small enough to remember, broad enough to cover everything in scope:

| Value | Means | Examples in this project |
|-------|-------|--------------------------|
| `tissue` | Excised biological material (sections, slices, biopsies, fixed/unfixed) | All AxioScan / Cell Observer / LSM 900 WSI of mouse organ sections |
| `organism` | Whole live or post-mortem animal | In vivo MRI, PET/CT, SPECT of mice |
| `cells` | Cultured or isolated cell preparations | Future Cell Observer cell-culture work (if it lands in scope) |
| `material` | Non-biological samples (nanoparticles, contrast agents, synthetic constructs) | Future SEM/TEM nanomaterial characterization |
| `phantom` | Imaging calibration objects | Platform commissioning / QA scans, if archived |

**Notes:**

- Use lowercase, one of the five values verbatim. If a future sample doesn't fit, flag for vocab extension before ingest rather than inventing a value on the fly.
- Species/anatomy details that today appear as freeform `"mouse lung section"`-style strings in pre-cutover example rows should migrate to dedicated columns once REG-07 closes (proposed `sample_organism` + `anatomical_entity`; tracked in `tasks/tasks.md` §3.1).
- For batches where every acquisition shares the same type, set the value at the YAML template level rather than per-row. The AxioScan 7 per-instrument template pre-fills `sample_type: tissue` for this reason.

### 2.5 Example

```csv
acq_id,registration_datetime,acquisition_datetime,data_ecosystem,instrument,instrument_model,modalities_in_study,operator,data_source,sample_id,sample_type,primary_file_name,original_name,file_format,file_size_mb,file_count,canonical_path,checksum_present,extended_metadata_present,project_hint,ingest_config,notes
ACQ-20260215-ZWSI-001,2026-02-15T16:30:00Z,2026-02-15T14:00:00Z,MICROSCOPY,ZWSI,Zeiss Axio Scan 7,,MBC,internal,MOUSE-2024-042,mouse lung section,ACQ-20260215-ZWSI-001.czi,MFB_MBC_PROJ-0003_MOUSE-2024-042_HE_20x.czi,.czi,2450,4,/raw/MICROSCOPY/2026/2026-02/ACQ-20260215-ZWSI-001/,Y,Y,PROJ-0003,tools/configs/axioscan7_20260215.yaml,First pilot deposit
ACQ-20260215-MRI-001,2026-02-15T17:00:00Z,2026-02-15T10:30:00Z,DICOM,MRI,Bruker BioSpec 11.7T,,IFF,internal,MOUSE-2024-042,mouse brain,ACQ-20260215-MRI-001.zip,,.zip,1800,4,/raw/DICOM/2026/2026-02/ACQ-20260215-MRI-001/,Y,Y,,tools/configs/mri_20260215.yaml,MRI follow-up (full-mode ingest)
ACQ-20260220-PET-001,2026-02-20T11:00:00Z,2026-02-20T09:00:00Z,DICOM,PET,Molecubes beta-CUBE,PT;CT,CLM,internal,MOUSE-2024-042,mouse tumor,ACQ-20260220-PET-001.zip,,.zip,2100,4,/raw/DICOM/2026/2026-02/ACQ-20260220-PET-001/,Y,Y,,tools/configs/pet_20260220.yaml,PET/CT hybrid session (full-mode ingest)
ACQ-20260301-XMRI-001,2026-03-01T09:00:00Z,,DICOM,XMRI,,,RT,collaborator:HPIC,HPIC-case-01,,ACQ-20260301-XMRI-001.zip,case_01.zip,.zip,450,3,/raw/DICOM/2026/2026-03/ACQ-20260301-XMRI-001/,Y,N,,,Lightweight ingest from NAS staging
```

### 2.6 Update Rules

| Action | Allowed | Who | When |
|--------|---------|-----|------|
| Add new entry | ✅ Yes | Operator (via deposit) | At deposit time |
| Correct metadata | ✅ Yes | Admin | If error discovered (log correction) |
| Delete entry | ❌ No | — | Entries are permanent |
| Modify after deposit | ⚠️ Limited | Admin | Only to fix errors, not change facts |

---

## 3. Publications Registry

**File:** `/gjesus3/registries/registry_publications.csv`

### 3.1 Purpose

Index of all publication folders with status tracking and bibliographic information.

### 3.2 Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `pub_id` | String | ✅ Yes | Unique ID (e.g., `PUB-0001`) |
| `short_name` | String | ✅ Yes | Folder name (e.g., `lung-fibrosis-markers-2026`) |
| `working_title` | String | ✅ Yes | Current/working title |
| `status` | Enum | ✅ Yes | `created`, `in_progress`, `submitted`, `published`, `abandoned` |
| `pi` | String | ✅ Yes | Principal investigator |
| `first_author` | String | ✅ Yes | First author |
| `corresponding_author` | String | 🔶 Recommended | Corresponding author (if different) |
| `created_date` | Date | ✅ Yes | When folder was created |
| `submitted_date` | Date | Optional | When manuscript was submitted |
| `published_date` | Date | Optional | When paper was published |
| `closed_date` | Date | Optional | When folder was locked |
| `journal` | String | Optional | Target/actual journal |
| `doi` | String | Optional | Publication DOI |
| `repository_link` | String | Optional | Link to data repository (Zenodo, etc.) |
| `folder_location` | String | ✅ Yes | Current path to folder |
| `notes` | String | Optional | Free-text notes |

### 3.3 Example

```csv
pub_id,short_name,working_title,status,pi,first_author,corresponding_author,created_date,submitted_date,published_date,closed_date,journal,doi,repository_link,folder_location,notes
PUB-0001,lung-fibrosis-markers-2026,Quantification of fibrotic markers in IPF lung tissue,in_progress,Jesús Ruiz-Cabello,Marta Beraza,Jesús Ruiz-Cabello,2026-02-15,,,,,,/publications/lung-fibrosis-markers-2026/,Initial pilot publication
PUB-0002,pet-mri-fusion-2025,Multimodal PET-MRI fusion for tumor characterization,published,Jesús Ruiz-Cabello,Claudia Miranda,Jesús Ruiz-Cabello,2025-06-01,2025-09-15,2025-12-20,2025-12-22,J Nuclear Med,10.1234/jnm.2025.12345,https://zenodo.org/record/1234567,/publications/pet-mri-fusion-2025/,Archived and closed
```

### 3.4 Update Rules

| Action | Allowed | Who | When |
|--------|---------|-----|------|
| Add new entry | ✅ Yes | Operator | At folder creation |
| Update status | ✅ Yes | Operator/Admin | As publication progresses |
| Add DOI/links | ✅ Yes | Operator/Admin | When published |
| Close entry | ✅ Yes | Admin | At folder lock |
| Delete entry | ❌ No | — | Entries are permanent |

---

## 4. Projects Registry

**File:** `/gjesus3/registries/registry_projects.csv`

### 4.1 Purpose

Index of project workspaces with ownership and status tracking.

### 4.2 Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `project_id` | String | ✅ Yes | Unique ID (e.g., `PROJ-0001`) |
| `short_name` | String | ✅ Yes | Folder name |
| `description` | String | ✅ Yes | Brief description of project scope |
| `owner` | String | ✅ Yes | Primary owner/SPOC |
| `start_date` | Date | ✅ Yes | When project started |
| `status` | Enum | ✅ Yes | `active`, `paused`, `closed` |
| `last_activity` | Date | 🔶 Recommended | Last modification (for retention tracking) |
| `folder_location` | String | ✅ Yes | Path to folder |
| `notes` | String | Optional | Free-text notes |

### 4.3 Example

```csv
project_id,short_name,description,owner,start_date,status,last_activity,folder_location,notes
PROJ-0001,ipf-biomarkers,IPF biomarker quantification study,MBC,2026-01-15,active,2026-02-10,/projects/proj-ipf-biomarkers/,May lead to PUB-0001
```

---

## 5. Curated Datasets Registry

**File:** `/gjesus3/registries/registry_datasets.csv`

> **❓ EVALUATING:** Curated datasets area is under evaluation. See [12_CURATED_DATASETS](12_CURATED_DATASETS.md) for full specification.

### 5.1 Purpose

Index of curated, versioned datasets (e.g., segmentation ground truth, benchmark sets) that accumulate across projects and are intended for long-term reuse.

### 5.2 Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `dataset_id` | String | ✅ Yes | Unique ID (e.g., `DS-SEG-0001`) |
| `short_name` | String | ✅ Yes | Human-readable folder name |
| `description` | String | ✅ Yes | What this dataset contains and its purpose |
| `dataset_type` | String | ✅ Yes | Category: `segmentation`, `registration`, `benchmark`, etc. |
| `data_ecosystem` | String | ✅ Yes | Which RAW ecosystem this relates to: `MICROSCOPY`, `DICOM`, or `EM` |
| `owner` | String | ✅ Yes | Dataset curator / responsible person |
| `created_date` | Date | ✅ Yes | When dataset was created |
| `version` | String | ✅ Yes | Version identifier (e.g., `v1.0`) |
| `status` | Enum | ✅ Yes | `active`, `superseded`, `archived` |
| `sample_count` | Number | 🔶 Recommended | Number of labeled samples / items |
| `source_acq_ids` | String | ✅ Yes | Semicolon-separated list of RAW ACQ-IDs this dataset derives from |
| `folder_location` | String | ✅ Yes | Path to dataset folder |
| `provenance_present` | Boolean | ✅ Yes | `Y` or `N` — does the dataset include provenance documentation? |
| `notes` | String | Optional | Free-text notes |

### 5.3 Example

```csv
dataset_id,short_name,description,dataset_type,data_ecosystem,owner,created_date,version,status,sample_count,source_acq_ids,folder_location,provenance_present,notes
DS-SEG-0001,lung-fibrosis-gt-v1,Manual segmentation masks for IPF lung tissue (H&E WSI),segmentation,MICROSCOPY,RT,2026-03-15,v1.0,active,24,ACQ-20260215-ZWSI-001;ACQ-20260216-ZWSI-002;ACQ-20260217-ZWSI-003,/curated_datasets/segmentation/MICROSCOPY/DS-SEG-0001/,Y,Initial training set for fibrosis segmentation model
```

### 5.4 Update Rules

| Action | Allowed | Who | When |
|--------|---------|-----|------|
| Add new entry | ✅ Yes | Dataset curator | At dataset promotion |
| Update sample count | ✅ Yes | Dataset curator | As dataset grows |
| Create new version | ✅ Yes | Dataset curator | Material changes → new version or new ID |
| Mark superseded | ✅ Yes | Dataset curator | When new version replaces old |
| Delete entry | ❌ No | — | Entries are permanent |

### 5.5 ID Generation

**Pattern:** `DS-<TYPE>-<NNNN>`

| Component | Description | Examples |
|-----------|-------------|----------|
| `DS` | Fixed prefix | `DS` |
| `<TYPE>` | Short dataset type code | `SEG` (segmentation), `REG` (registration), `BEN` (benchmark) |
| `<NNNN>` | Sequential number (4 digits) | `0001`, `0002` |

---

## 6. Registry Management

### 6.1 Access Control

| Registry | Read | Write |
|----------|------|-------|
| Raw | All operators | Admin (or via deposit script) |
| Publications | All operators | Operator for own entries; Admin for all |
| Projects | All operators | Operator for own entries; Admin for all |
| Curated Datasets | All operators | Dataset curator or Admin only |

### 6.2 Backup

Registries are critical metadata. Consider:
- Git versioning (if repository set up)
- Periodic backup copies
- Include in any system backup

### 6.3 Validation

> **📋 Planned:** Scripts to validate registry integrity:
> - All paths resolve to actual folders
> - Required fields are populated
> - IDs are unique
> - Dates are valid format
> - `data_ecosystem` values match actual folder locations

---

## 7. ID Generation

### 7.1 Acquisition IDs

Pattern: `ACQ-<YYYYMMDD>-<INST>-<SEQ>`

Generation: Scripted (preferred) or manual with lookup of current day's highest sequence.

### 7.2 Publication IDs

Pattern: `PUB-<NNNN>`

Generation: Next available number (scan registry for highest, increment).

### 7.3 Project IDs

Pattern: `PROJ-<NNNN>`

Generation: Next available number.

### 7.4 Dataset IDs

Pattern: `DS-<TYPE>-<NNNN>`

Generation: Next available number within each type.

---

## 8. Related Documents

- [03_RAW_STORAGE](03_RAW_STORAGE.md) — Raw area using this registry
- [04_PUBLICATIONS](04_PUBLICATIONS.md) — Publications area using this registry
- [05_PROJECTS](05_PROJECTS.md) — Projects area using this registry
- [12_CURATED_DATASETS](12_CURATED_DATASETS.md) — Curated datasets area using this registry

---

## Open Questions Summary

| ID | Question | Owner | Status |
|----|----------|-------|--------|
| REG-01 | Include sample_id in raw registry as required or recommended? Composite format `<short_project>_<short_sample>` recommended (§2.3); PI sign-off pending. | Users / PI | 🔶 Draft |
| REG-02 | What additional fields needed for REMBI/ISA alignment? | Data Mgmt Lead | 🔶 See [08_METADATA](08_METADATA.md) |
| REG-03 | Git versioning for registries? | Data Mgmt Lead | 📋 Future consideration |
| REG-04 | Validation script requirements | Data Mgmt Lead | 📋 Planned |
| REG-05 | Curated datasets registry: finalize schema after pilot experience | Data Mgmt Lead | ❓ Evaluating |
| REG-06 | Track DICOM instance count (.dcm files) in registry or only in extended metadata? | Data Mgmt Lead | 🔶 Draft |
| REG-07 | Sample type controlled vocabulary (`tissue`/`organism`/`cells`/`material`/`phantom`) DRAFT in §2.4; PI sign-off + first round of cross-instrument application pending. Future split of species/anatomy into dedicated columns. | Users / PI | 🔶 Draft |
