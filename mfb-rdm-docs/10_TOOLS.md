# 10 — Tools and Automation

**Parent:** [Documentation Index](00_INDEX.md)  
**Status:** 🔶 Draft
**Last Updated:** 2026-03-06

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
| **P1** | `create_project` | Create project folder with templates | ✅ Implemented (`tools/create_project.py`) |
| **P1** | Metadata extraction | Auto-extract embedded metadata (integrated into full-mode ingest) | 🔶 Design decided; implementation pending |
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

**Two Ingest Modes:**

> **✅ DECIDED:** Full mode (default) extracts metadata and compresses DICOM before archiving. Lightweight mode copies as-is for constrained environments.

**Full Mode (default) — per acquisition:**
1. Load + validate config (YAML or interactive)
2. Analyze source data (DICOM headers: modality, StudyDate, file count, size)
3. Extract embedded metadata → `metadata.json` sidecar
4. Compress DICOM (if applicable) → `.zip` or `.tar.gz` archive
5. Generate ACQ-ID (read registry for next sequence number)
6. Create folder: `raw/<ECOSYSTEM>/<YYYY>/<YYYY-MM>/<ACQ-ID>/`
7. Copy files to destination (archive + metadata.json + README.txt, with progress bar)
8. Generate `checksums.json` (SHA-256, all files in acquisition folder)
9. Verify copy — recompute checksums on destination, compare
10. Generate `README.txt`
11. Append row to `registry_raw.csv` (all fields populated, including `original_name`)
12. Create link in project folder (if `--project` specified)
13. Report summary

**Lightweight Mode (`--lightweight`) — per acquisition:**
1. Load + validate config (fewer required fields)
2. Generate ACQ-ID
3. Create folder: `raw/<ECOSYSTEM>/<YYYY>/<YYYY-MM>/<ACQ-ID>/`
4. Copy archive as-is to destination (user provides pre-compressed archive or files)
5. Generate `checksums.json`
6. Generate `README.txt`
7. Append row to `registry_raw.csv` (auto fields only; `extended_metadata_present` = `N`)
8. Report summary

**Single-case configuration (example):**
```yaml
# ingest_config.yaml
source_path: /data/local_staging/user_dump/   # local path (recommended for full mode)
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
  archive_format: zip     # zip (default) or tar.gz

auto_discover:
  source_dir: /data/local_staging/HPIC_33cases/   # local path for full mode
  pattern: "HPIC*/"
  sample_id_from: folder_name
```

**Usage:**
```bash
python tools/ingest_raw.py --config batch_hpic.yaml --dry-run    # preview (full mode)
python tools/ingest_raw.py --config batch_hpic.yaml               # execute (full mode)
python tools/ingest_raw.py --interactive                           # single case (full mode)
python tools/ingest_raw.py --config quick.yaml --lightweight       # lightweight mode
python tools/ingest_raw.py --interactive --lightweight             # lightweight interactive
```

**Key features:**
- Two ingest modes: full (default) and lightweight (`--lightweight`)
- DICOM header auto-detection (modality, StudyDate via pydicom) — full mode
- DICOM archive creation (compress to .zip or .tar.gz) — full mode
- Metadata sidecar generation (`metadata.json`) — full mode
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

### 3.1 `create_project` — Project Workspace Setup

**Purpose:** Create a new project folder with required structure and registry entry.

**Location:** `tools/create_project.py`

**Inputs:**
- Short name (folder name)
- Description
- Owner (initials)

**Actions:**
1. Validate short name is unique (scan `registry_projects.csv`)
2. Generate PROJ-ID (`PROJ-NNNN`, next available)
3. Create folder: `/projects/proj-<short_name>/`
4. Write `_project.yaml` from template
5. Create empty `provenance.csv` with headers
6. Create `raw_linked/` directory
7. Append entry to `registries/registry_projects.csv`
8. Print summary

**Usage:**
```bash
python tools/create_project.py \
  --name "ipf-biomarkers" \
  --description "IPF biomarker quantification study" \
  --owner MBC

python tools/create_project.py --interactive
python tools/create_project.py --name test --description "test" --owner RT --dry-run
```

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

### 3.4 Metadata Extraction and Backfill

> **✅ DECIDED:** Auto-extraction of embedded metadata is integrated into full-mode ingest — not a separate standalone tool. The DICOM archive format decision is resolved (compressed archives); extraction happens before compression during full-mode ingest.

**Metadata extraction (integrated into `ingest_raw` full mode):**
- Reads embedded metadata from raw files (DICOM headers via pydicom, .czi metadata, etc.)
- Writes `metadata.json` sidecar in the acquisition folder
- Sets `extended_metadata_present` = `Y` in registry

**`backfill_metadata` — upgrade lightweight ingests:**

**Purpose:** Retroactively extract metadata from acquisitions that were ingested in lightweight mode. Decompresses the archive to a temp directory, extracts metadata, writes `metadata.json`, updates registry.

**Usage:**
```bash
python tools/backfill_metadata.py --acq-id ACQ-20260301-XMRI-001   # single
python tools/backfill_metadata.py --scope /raw/DICOM/2026/          # batch
python tools/backfill_metadata.py --dry-run --scope /raw/DICOM/     # preview
```

**Supported formats:** DICOM (.dcm via pydicom), .czi (via aicspylibczi or czifile), others TBD

> **Note:** User-supplied metadata (sample context, experimental notes via CSVs/Excel) remains deferred.

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
| **Pilot** | `ingest_raw` (full + lightweight modes), `create_publication`, `create_project` | Before pilot start |
| **Pilot** | Metadata extractors (integrated into full-mode ingest) | Before first batch ingest |
| **Pilot+** | `backfill_metadata` (upgrade lightweight ingests) | During pilot |
| **Pilot+** | `log_activity`, `validate_registries` | During pilot |
| **Post-pilot** | GUI wrappers, user-supplied metadata workflows | Based on demand |

---

## 8. Related Documents

- [03_RAW_STORAGE](03_RAW_STORAGE.md) — Ingest workflow
- [04_PUBLICATIONS](04_PUBLICATIONS.md) — Publication creation
- [05_PROJECTS](05_PROJECTS.md) — Project creation
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
