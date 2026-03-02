# 10 — Tools and Automation

**Parent:** [Documentation Index](00_INDEX.md)  
**Status:** 🔶 Draft
**Last Updated:** 2026-03-02

---

## Purpose

This document specifies the scripts and tools needed to support the data management workflows, reducing manual effort and enforcing consistency.

---

## 1. Tool Priorities

| Priority | Tool | Purpose | Status |
|----------|------|---------|--------|
| **P1** | `ingest_raw` | Batch deposit from staging to raw | ✅ Implemented (`tools/ingest_raw.py`) |
| **P1** | `create_publication` | Create publication folder with templates | 📋 Requirements defined |
| **P2** | `log_activity` | Helper for provenance logging | 📋 Requirements defined |
| **P2** | `create_project` | Create project folder (if Projects included) | ❓ Depends on scope |
| **P3** | Metadata extractors | Extract embedded metadata to JSON | 📋 Future |
| **P3** | Validation scripts | Verify registry integrity | 📋 Future |

---

## 2. Core Scripts

### 2.1 `ingest_raw` — Raw Data Ingest

**Purpose:** Copy data from staging (or local source) to the structured raw area with proper naming, checksums, verification, and registry update.

**Location:** `tools/ingest_raw.py` (with supporting modules in `tools/ingest/`)

**Architecture:**
```
tools/
├── ingest_raw.py          # CLI entry point
├── ingest/
│   ├── __init__.py
│   ├── config.py          # YAML config loading + validation
│   ├── acq_id.py          # ACQ-ID generation (date + inst + seq)
│   ├── checksum.py        # SHA-256 checksums → checksums.json
│   ├── registry.py        # Read/append registry_raw.csv
│   ├── readme.py          # Generate README.txt from template
│   ├── dicom_utils.py     # DICOM header extraction (pydicom)
│   └── linker.py          # Create .lnk / symlink / manifest
├── templates/
│   └── README_raw.txt     # README template
└── requirements.txt       # pydicom, pyyaml, pylnk3, tqdm
```

**Workflow (per acquisition):**
1. Load + validate config (YAML or interactive)
2. Analyze source data (DICOM headers: modality, StudyDate, file count, size)
3. Generate ACQ-ID (read registry for next sequence number)
4. Create folder: `raw/<ECOSYSTEM>/<YYYY>/<YYYY-MM>/<ACQ-ID>/series/`
5. Copy files from staging to destination (with progress bar)
6. Generate `checksums.json` (SHA-256, all files)
7. Verify copy — recompute checksums on source, compare with destination
8. Generate `README.txt`
9. Append row to `registry_raw.csv` (including `original_name`)
10. Create link in project folder (if `--project` specified)
11. Report summary

**Single-case configuration (example):**
```yaml
# ingest_config.yaml
source_path: /staging/user_dump/
instrument: ZWSI
acquisition_date: 2026-02-15
operator: MBC
sample_id: MOUSE-2024-042
sample_type: mouse lung section
data_source: internal
notes: First test of ingest workflow
```

**Batch configuration (example):**
```yaml
defaults:
  data_ecosystem: DICOM
  instrument: XMRI       # or 'auto' to detect from DICOM headers
  operator: RT
  data_source: "collaborator:HPIC"
  acquisition_date: auto  # extract StudyDate from DICOM

auto_discover:
  staging_dir: /mnt/gjesus3/staging/HPIC_33cases/
  pattern: "HPIC*/"
  sample_id_from: folder_name
```

**Usage:**
```bash
python tools/ingest_raw.py --config batch_hpic.yaml --dry-run   # preview
python tools/ingest_raw.py --config batch_hpic.yaml              # execute
python tools/ingest_raw.py --interactive                          # single case
```

**Key features:**
- DICOM header auto-detection (modality, StudyDate via pydicom)
- Collaborator instrument codes: X-prefix (e.g., `XMRI` for external MRI)
- Copy verification: checksums computed on both source and destination, then compared
- `original_name` field in registry tracks pre-ingestion source name
- `--dry-run` mode for previewing without changes
- Batch auto-discovery for processing many cases at once

### 2.2 `create_publication` — Publication Package Setup

**Purpose:** Create a new publication folder with required structure and registry entry.

**Inputs:**
- Short name (folder name)
- Working title
- PI, first author
- Optional: description, linked raw data

**Actions:**
1. Validate short name is unique
2. Generate PUB-ID
3. Create folder structure:
   - `_publication.yaml` (from template)
   - `provenance.csv` (empty with headers)
   - `raw_linked/` folder
   - Optional: `figures/`, `analysis/`, `methods/`
4. Append entry to registry_publications.csv
5. Report success with folder path

**Usage:**
```bash
create_publication \
  --name "lung-fibrosis-markers-2026" \
  --title "Quantification of fibrotic markers in IPF lung tissue" \
  --pi "Jesús Ruiz-Cabello" \
  --first-author "Marta Beraza"
```

### 2.3 `log_activity` — Provenance Helper

**Purpose:** Simplify adding entries to the provenance log.

**Inputs:**
- Output file path
- Input references (ACQ-IDs, FILE-IDs, or paths)
- Process description
- Creator
- Optional: software version, parameter file, notebook reference

**Actions:**
1. Determine which provenance.csv to update (from output path)
2. Generate next FILE-ID
3. Validate input references exist
4. Append entry to provenance.csv
5. Confirm entry

**Usage:**
```bash
log_activity \
  --output figures/fig1_panel_a.tiff \
  --inputs "ACQ-20260115-ZWSI-001" \
  --process "ROI extraction and contrast adjustment" \
  --creator MBC \
  --software "ImageJ 1.54f"
```

---

## 3. Utility Scripts

### 3.1 `create_project` (if Projects included)

Similar to `create_publication` but for project folders.

### 3.2 `validate_registries`

**Purpose:** Check registry integrity.

**Checks:**
- All paths resolve to existing folders
- Required fields are populated
- IDs are unique
- Dates are valid format
- Cross-references are valid

### 3.3 `verify_checksums`

**Purpose:** Verify file integrity against stored checksums.

**Usage:**
```bash
verify_checksums --scope /raw/MICROSCOPY/2026/  # Check specific path
verify_checksums --sample 10  # Random 10% sample
```

### 3.4 `extract_metadata`

**Purpose:** Extract embedded metadata from data files to JSON sidecar.

**Supported formats:** .czi, DICOM, others TBD

---

## 4. Implementation Decisions

### 4.1 Language

> **🔶 RECOMMENDATION:** Python 3.10+

Rationale:
- Good library support for file handling, CSV, JSON
- Libraries for format-specific metadata extraction
- Familiar to scientific computing community

### 4.2 Where Scripts Run

> **⚠️ GAP:** Need to decide execution environment.

| Option | Pros | Cons |
|--------|------|------|
| **Designated workstation** | Controlled environment; consistent | Requires access to that machine |
| **User machines** | Convenient; work where you are | Dependency management; consistency |
| **NAS (QNAP apps)** | Runs where data is | Limited environment; complexity |

**Tentative:** Designated workstation with network access to NAS

### 4.3 Distribution and Versioning

> **⚠️ GAP:** Need to establish script management.

| Approach | Description |
|----------|-------------|
| Git repository | Version controlled; users pull updates |
| Shared folder | Scripts on network drive; single source |
| Package | pip-installable package (more overhead) |

**Tentative:** Git repository with periodic releases copied to shared folder

---

## 5. User Interface Options

### 5.1 Command Line (Primary)

All tools available as CLI scripts. Suitable for power users and scripting.

### 5.2 Simple GUI Wrappers (Future)

For less technical users, consider:
- Tkinter-based simple dialogs
- Web interface (Flask/FastAPI)
- Jupyter notebooks with widgets

> **📋 Future consideration:** GUI wrappers based on user feedback during pilot.

---

## 6. Dependencies

**Python packages likely needed:**
- `pyyaml` — Configuration files
- `python-dateutil` — Date parsing
- `tqdm` — Progress bars
- `hashlib` (stdlib) — Checksums
- `pydicom` — DICOM metadata
- `tifffile` — TIFF metadata
- `czifile` or `aicspylibczi` — Zeiss CZI metadata

---

## 7. Development Roadmap

| Phase | Tools | Timeline |
|-------|-------|----------|
| **Pilot** | `ingest_raw`, `create_publication` | Before pilot start |
| **Pilot+** | `log_activity`, `validate_registries` | During pilot |
| **Post-pilot** | Metadata extractors, GUI wrappers | Based on demand |

---

## 8. Related Documents

- [03_RAW_STORAGE](03_RAW_STORAGE.md) — Ingest workflow
- [04_PUBLICATIONS](04_PUBLICATIONS.md) — Publication creation
- [07_PROVENANCE](07_PROVENANCE.md) — Provenance logging
- [11_OPERATIONS](11_OPERATIONS.md) — Who uses which tools

---

## Open Questions

| ID | Question | Owner | Status |
|----|----------|-------|--------|
| TOOL-01 | Where will scripts run? | Data Mgmt Lead + IT | ⚠️ Needs decision |
| TOOL-02 | Git repo location and access | Data Mgmt Lead | ⚠️ Needs setup |
| TOOL-03 | User training on CLI tools | Data Mgmt Lead | 📋 Planned |
| TOOL-04 | GUI wrapper priority | Users | 📣 Need feedback |
