# 06 — Registries

**Parent:** [Documentation Index](00_INDEX.md)  
**Status:** 🔶 Draft  
**Last Updated:** 2026-02-02

---

## Purpose

This document specifies the three top-level registries that index and document the contents of the storage areas.

---

## 1. Overview

### 1.1 What Are Registries?

Registries are **CSV files** that serve as indexes (manifests) for each storage area. When data is added to the system, an entry is "registered" by adding a row to the appropriate registry.

### 1.2 Registry Locations

> **✅ DECIDED:** Registries are centralized at the top level, not distributed within each folder.

| Registry | Location | Purpose |
|----------|----------|---------|
| Raw Registry | `/gjesus3/raw/registry_raw.csv` | Indexes all raw acquisitions |
| Publications Registry | `/gjesus3/publications/registry_publications.csv` | Indexes all publication folders |
| Projects Registry | `/gjesus3/projects/registry_projects.csv` | Indexes all project folders (if used) |

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

**File:** `/gjesus3/raw/registry_raw.csv`

### 2.1 Purpose

Authoritative record of all raw acquisitions deposited in the system.

### 2.2 Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `acq_id` | String | ✅ Yes | Unique acquisition ID (e.g., `ACQ-20260215-ZWSI-001`) |
| `registration_datetime` | ISO DateTime | ✅ Yes | When this entry was added (auto) |
| `acquisition_datetime` | ISO DateTime | 🔶 Recommended | When the data was actually acquired |
| `instrument` | String | ✅ Yes | Instrument code (e.g., `ZWSI`, `HIST`, `PET`) |
| `operator` | String | ✅ Yes | Person who collected the data (name or initials) |
| `sample_id` | String | 🔶 Recommended | Sample or animal identifier |
| `sample_type` | String | 🔶 Recommended | Brief sample description |
| `primary_file_name` | String | ✅ Yes | Name of the primary data file |
| `file_format` | String | ✅ Yes | File extension/format (e.g., `.czi`, `.dcm`) |
| `file_size_mb` | Number | ✅ Yes | Size of primary file in MB |
| `file_count` | Number | ✅ Yes | Total files in acquisition folder |
| `canonical_path` | String | ✅ Yes | Full path to acquisition folder |
| `checksum_present` | Boolean | ✅ Yes | `Y` or `N` — is checksums.json present? |
| `extended_metadata_present` | Boolean | ✅ Yes | `Y` or `N` — is extended metadata file present? |
| `project_hint` | String | Optional | Associated project ID if known at deposit |
| `notes` | String | Optional | Free-text notes |

### 2.3 Example

```csv
acq_id,registration_datetime,acquisition_datetime,instrument,operator,sample_id,sample_type,primary_file_name,file_format,file_size_mb,file_count,canonical_path,checksum_present,extended_metadata_present,project_hint,notes
ACQ-20260215-ZWSI-001,2026-02-15T16:30:00Z,2026-02-15T14:00:00Z,ZWSI,MBC,MOUSE-2024-042,mouse lung section,sample_slide.czi,.czi,2450,4,/raw/zeiss-wsi/2026/2026-02/ACQ-20260215-ZWSI-001/,Y,Y,PROJ-0003,First pilot deposit
ACQ-20260215-HIST-001,2026-02-15T17:00:00Z,2026-02-15T10:30:00Z,HIST,IFF,SAMPLE-B12,tissue section,slide_001.tif,.tif,180,3,/raw/histology/2026/2026-02/ACQ-20260215-HIST-001/,Y,N,,H&E staining
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

**File:** `/gjesus3/publications/registry_publications.csv`

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

**File:** `/gjesus3/projects/registry_projects.csv`

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

## 5. Registry Management

### 5.1 Access Control

| Registry | Read | Write |
|----------|------|-------|
| Raw | All operators | Admin (or via deposit script) |
| Publications | All operators | Operator for own entries; Admin for all |
| Projects | All operators | Operator for own entries; Admin for all |

### 5.2 Backup

Registries are critical metadata. Consider:
- Git versioning (if repository set up)
- Periodic backup copies
- Include in any system backup

### 5.3 Validation

> **📋 Planned:** Scripts to validate registry integrity:
> - All paths resolve to actual folders
> - Required fields are populated
> - IDs are unique
> - Dates are valid format

---

## 6. ID Generation

### 6.1 Acquisition IDs

Pattern: `ACQ-<YYYYMMDD>-<INST>-<SEQ>`

Generation: Scripted (preferred) or manual with lookup of current day's highest sequence.

### 6.2 Publication IDs

Pattern: `PUB-<NNNN>`

Generation: Next available number (scan registry for highest, increment).

### 6.3 Project IDs

Pattern: `PROJ-<NNNN>`

Generation: Next available number.

---

## 7. Related Documents

- [03_RAW_STORAGE](03_RAW_STORAGE.md) — Raw area using this registry
- [04_PUBLICATIONS](04_PUBLICATIONS.md) — Publications area using this registry
- [05_PROJECTS](05_PROJECTS.md) — Projects area using this registry
- [10_TOOLS](10_TOOLS.md) — Scripts for registry management

---

## Open Questions Summary

| ID | Question | Owner | Status |
|----|----------|-------|--------|
| REG-01 | Include sample_id in raw registry as required or recommended? | Users | 🔶 Draft |
| REG-02 | What additional fields needed for REMBI/ISA alignment? | Data Mgmt Lead | 🔶 See [08_METADATA](08_METADATA.md) |
| REG-03 | Git versioning for registries? | Data Mgmt Lead | 📋 Future consideration |
| REG-04 | Validation script requirements | Data Mgmt Lead | 📋 Planned |
