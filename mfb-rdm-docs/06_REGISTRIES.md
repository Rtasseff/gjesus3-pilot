# 06 — Registries

**Parent:** [Documentation Index](00_INDEX.md)
**Status:** 🔶 Draft
**Last Updated:** 2026-03-02

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
| Projects Registry | `/gjesus3/registries/registry_projects.csv` | Indexes all project folders (if used) |
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

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `acq_id` | String | ✅ Yes | Unique acquisition ID (e.g., `ACQ-20260215-ZWSI-001`) |
| `registration_datetime` | ISO DateTime | ✅ Yes | When this entry was added (auto) |
| `acquisition_datetime` | ISO DateTime | 🔶 Recommended | When the data was actually acquired |
| `data_ecosystem` | String | ✅ Yes | Top-level folder: `MICROSCOPY`, `DICOM`, or `EM` |
| `instrument` | String | ✅ Yes | Instrument code (e.g., `ZWSI`, `LSM9`, `PET`) |
| `instrument_model` | String | 🔶 Recommended | Full instrument name (e.g., `Bruker BioSpec 11.7T`) |
| `modalities_in_study` | String | Optional | For multi-modal acquisitions: semicolon-separated DICOM modality codes (e.g., `PT;CT`) |
| `operator` | String | ✅ Yes | Person who collected the data (name or initials) |
| `data_source` | String | 🔶 Recommended | `internal` or `collaborator:<name>` |
| `sample_id` | String | 🔶 Recommended | Sample or animal identifier |
| `sample_type` | String | 🔶 Recommended | Brief sample description |
| `primary_file_name` | String | ✅ Yes | Name of the primary data file (or primary bundle folder) |
| `original_name` | String | 🔶 Recommended | Original source name before ingestion (e.g., archive filename); required when data is renamed during ingest |
| `file_format` | String | ✅ Yes | File extension/format (e.g., `.czi`, `.dcm`) |
| `file_size_mb` | Number | ✅ Yes | Size of primary file in MB |
| `file_count` | Number | ✅ Yes | Total files in acquisition folder |
| `canonical_path` | String | ✅ Yes | Full path to acquisition folder |
| `checksum_present` | String (Y/N) | ✅ Yes | `Y` or `N` — is checksums.json present? |
| `extended_metadata_present` | String (Y/N) | ✅ Yes | `Y` or `N` — is extended metadata file present? |
| `project_hint` | String | Optional | Associated project ID if known at deposit |
| `notes` | String | Optional | Free-text notes |

### 2.3 Example

```csv
acq_id,registration_datetime,acquisition_datetime,data_ecosystem,instrument,instrument_model,modalities_in_study,operator,data_source,sample_id,sample_type,primary_file_name,original_name,file_format,file_size_mb,file_count,canonical_path,checksum_present,extended_metadata_present,project_hint,notes
ACQ-20260215-ZWSI-001,2026-02-15T16:30:00Z,2026-02-15T14:00:00Z,MICROSCOPY,ZWSI,Zeiss Axiocam 7,,MBC,internal,MOUSE-2024-042,mouse lung section,sample_slide.czi,,.czi,2450,4,/raw/MICROSCOPY/2026/2026-02/ACQ-20260215-ZWSI-001/,Y,Y,PROJ-0003,First pilot deposit
ACQ-20260215-MRI-001,2026-02-15T17:00:00Z,2026-02-15T10:30:00Z,DICOM,MRI,Bruker BioSpec 11.7T,,IFF,internal,MOUSE-2024-042,mouse brain,series/,,.dcm,1800,312,/raw/DICOM/2026/2026-02/ACQ-20260215-MRI-001/,Y,N,,MRI follow-up
ACQ-20260220-PET-001,2026-02-20T11:00:00Z,2026-02-20T09:00:00Z,DICOM,PET,Molecubes beta-CUBE,PT;CT,CLM,internal,MOUSE-2024-042,mouse tumor,series/,,.dcm,2100,486,/raw/DICOM/2026/2026-02/ACQ-20260220-PET-001/,Y,N,,PET/CT hybrid session
```

### 2.4 Update Rules

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

> **❓ EVALUATING:** Projects area may be deferred. This section applies if included.

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
| REG-01 | Include sample_id in raw registry as required or recommended? | Users | 🔶 Draft |
| REG-02 | What additional fields needed for REMBI/ISA alignment? | Data Mgmt Lead | 🔶 See [08_METADATA](08_METADATA.md) |
| REG-03 | Git versioning for registries? | Data Mgmt Lead | 📋 Future consideration |
| REG-04 | Validation script requirements | Data Mgmt Lead | 📋 Planned |
| REG-05 | Curated datasets registry: finalize schema after pilot experience | Data Mgmt Lead | ❓ Evaluating |
