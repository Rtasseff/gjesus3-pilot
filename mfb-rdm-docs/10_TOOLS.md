# 10 — Tools and Automation

**Parent:** [Documentation Index](00_INDEX.md)  
**Status:** 🔶 Draft
**Last Updated:** 2026-05-06

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
├── ingest_raw.py            # CLI entry point
├── ingest/
│   ├── __init__.py
│   ├── config.py            # YAML loading + validation; expand_batch (file/dir glob, filename_parse, filter, idempotency); FORMAT_SUMMARIZERS dispatch
│   ├── resolver.py          # Resolves the YAML registry: block — literal | discovered.<x> | ${...} interp | NA
│   ├── acq_id.py            # ACQ-ID generation (date + inst + seq)
│   ├── checksum.py          # SHA-256 checksums → checksums.json
│   ├── registry.py          # Read/append registry_raw.csv (REGISTRY_FIELDS includes ingest_config)
│   ├── readme.py            # Generate README.txt from template
│   ├── dicom_utils.py       # DICOM header extraction (pydicom)
│   ├── microscopy_utils.py  # Single-file inventory (.czi, .tif) — sibling of dicom_utils
│   ├── filename_parser.py   # Positional filename → {field: value}
│   ├── metadata_sidecar.py  # metadata.json writer (cross-format; discovered + user_supplied)
│   ├── probe_czi.py         # Standalone read-only .czi metadata probe (utility)
│   └── linker.py            # Create Windows .lnk shortcut + manifest CSV (see §2.1.1)
├── configs/                 # Committed ingest configs, one per batch / day folder
│   └── axioscan7_20260422.yaml
├── templates/
│   ├── README_raw.txt       # README template
│   └── ingest_template.yaml # Starter template for new batch configs
└── requirements.txt         # pydicom, pyyaml, tqdm, czifile
```

### 2.1.1 Project Linking — Windows-First Design Decision

> **✅ DECIDED — Windows-first, deliberately:** Project links are created as **Windows `.lnk` shell shortcuts** by shelling out to PowerShell's `WScript.Shell` COM object. This is the right choice for the **gjesus3 pilot specifically** and is **not** the recommended default for future RDM deployments. The linker module is structured as the obvious porting seam — see "Porting to other systems" below.

When `ingest_raw.py` is run with `--project <PROJ-ID>` (or `project_hint` set in the YAML config), Step 12 of full-mode ingest creates a shortcut at:

```
/projects/<project_folder>/raw_linked/<original_archive_name>.lnk
```

…targeting the primary archive on the NAS via UNC path (e.g. `\\GJESUS3\gjesus3\raw\DICOM\YYYY\YYYY-MM\ACQ-...\ACQ-....zip`). The shortcut filename preserves the **original** name from staging (e.g. `LEONE_1.01.zip.lnk`), so users browsing a project folder see familiar names; the shortcut's target points at the canonical renamed archive. Shortcuts are idempotent — re-running ingest skips any shortcut that already exists.

#### Why Windows-first for gjesus3

| Constraint | Effect on the choice |
|------------|----------------------|
| **MFB user base is Windows** | Researchers access the NAS via mapped SMB drives in Windows Explorer. Project links must look and behave like ordinary files they can double-click. `.lnk` shortcuts render with the right icon, support double-click, and "Open file location" works. |
| **WSL → SMB symlink path didn't work cleanly** | Creating filesystem-level symbolic links against the QNAP SMB share from WSL ran into problems we couldn't work around in reasonable time. |
| **SSH-into-NAS was blocked** | The robust alternative — creating server-side POSIX symlinks via SSH on the QNAP itself — was attempted but IT could not provide working SSH access to the appliance. We chose to stop pushing on that front and adopt a method that works within the access we already had. |
| **`.lnk` shortcuts work without server cooperation** | Pure client-side artifacts. The NAS doesn't need to understand them; they just sit on the share like any other file. |

#### Tradeoffs we accepted

- **Creation is Windows-only.** The linker shells out to `powershell.exe`. Ingest must run on a Windows machine (or a machine with PowerShell 7+ on Linux, untested here). *Reading* shortcuts works fine from any OS — WSL/Linux can list, inspect, and copy `.lnk` files; only creation is restricted.
- **Links are file-level pointers, not filesystem-level links.** They survive being browsed over SMB but are opaque to scripts that walk the filesystem and don't recognize `.lnk` as a follow-able pointer. The CSV manifest at `registries/ingest_manifest.csv` is the script-friendly equivalent and is always written.

#### Porting to other systems

This pilot is intentionally scoped as a test case for larger MFB-area RDM efforts. Future deployments will not share gjesus3's combination of Windows-only users + locked-down QNAP, and the linker module is the seam designed to be swapped:

| Target environment | Likely method | Implementation note |
|--------------------|---------------|---------------------|
| Linux/macOS user base, ext4/ZFS NAS | POSIX **symlinks** | Replace the body of `linker.create_lnk()` with `os.symlink(target, lnk_path)`. Drop `.lnk` extension from the filename. |
| Mixed user base, NAS supports SSH | Server-side POSIX symlinks via SSH | `ln -s` runs on the NAS itself; resulting symlinks are visible to every client filesystem-canonically. |
| Constrained / mixed-OS / no link support | Manifest-only | The CSV manifest at `registries/ingest_manifest.csv` is the portable, link-free reference and is already always written. Just don't call `create_lnk`. |
| Cross-platform desperate compromise | Both `.lnk` *and* a symlink | Possible but creates two artifacts per acquisition; usually not worth it. |

The choice should be made consciously at the start of any future deployment — it affects what users can browse, how durable links are across renames, and which OSes can run the ingest pipeline.

---

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
12. Append entry to `registries/ingest_manifest.csv` (always); if `--project` is set, also create a Windows `.lnk` shortcut in `<project>/raw_linked/` pointing at the canonical archive (see §2.1.1)
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

**Configuration schema (since 2026-05-06):**

Three top-level blocks. `defaults:` is gone — non-registry control flags moved to `ingest:`, and the per-column registry mapping is explicit in `registry:`.

| Block            | Purpose |
|------------------|---------|
| `ingest:`        | Pipeline control flags (e.g. `delete_source_after_ingest`). Not registry columns. |
| `auto_discover:` | How to discover cases and what variables to extract per case. Each case's discovered fields land in a `discovered` namespace, referenceable below. |
| `registry:`      | Explicit per-column registry mapping. Three value forms: literal text/number, `discovered.<field>` (bare reference), or `"...${discovered.<field>}..."` (interpolation). Use `NA` to leave a column intentionally empty. |

The user-controllable `registry:` columns are: `instrument`, `data_ecosystem`, `instrument_model`, `modalities_in_study`, `operator`, `data_source`, `sample_id`, `sample_type`, `acquisition_datetime`, `project_hint`, `notes`. Of these, **`instrument`, `data_ecosystem`, `operator`, `data_source` must be present** (NA allowed where intentional); the rest are optional. Auto-populated columns (`acq_id`, `registration_datetime`, `primary_file_name`, `file_format`, `file_size_mb`, `file_count`, `canonical_path`, `checksum_present`, `extended_metadata_present`, `original_name`, `ingest_config`) must NOT appear in `registry:`.

A starter template lives at [`tools/templates/ingest_template.yaml`](../tools/templates/ingest_template.yaml). Edited copies should be saved under [`tools/configs/`](../tools/configs/) (under git, version-locked with the script — the relative path is stamped into each registry row's `ingest_config` column).

**Batch configuration — file-mode with filename parsing (AxioScan and similar):**

```yaml
ingest:
  delete_source_after_ingest: false

auto_discover:
  staging_dir: "S:/goptical/GOpticalUsers data/AxioScan/20260422"
  pattern: "*.czi"
  filename_parse:
    separator: "_"
    fields: [group_code, operator, project, sample_id, stain, magnification]
  filter:
    group_code: MFB
  acquisition_date_from: parent_folder_name

registry:
  instrument:           ZWSI
  data_ecosystem:       MICROSCOPY
  instrument_model:     "Zeiss Axio Scan 7"
  modalities_in_study:  NA
  operator:             discovered.operator
  data_source:          internal
  sample_id:            discovered.sample_id
  sample_type:          NA
  acquisition_datetime: discovered.acquisition_date
  project_hint:         NA
  notes:                "Routine WSI; ${discovered.stain} @ ${discovered.magnification}"
```

**Batch configuration — directory-mode (DICOM):**

```yaml
ingest:
  delete_source_after_ingest: false

auto_discover:
  staging_dir: /data/local_staging/HPIC_33cases/
  pattern: "HPIC*/"           # trailing / matches directories
  # acquisition_date_from: parent_folder_name  # if applicable

registry:
  instrument:           XMRI
  data_ecosystem:       DICOM
  instrument_model:     NA
  modalities_in_study:  NA
  operator:             RT
  data_source:          "collaborator:HPIC"
  sample_id:            discovered.folder_name
  sample_type:          NA
  acquisition_datetime: "20260301"     # literal; or NA to backfill later
  project_hint:         NA
  notes:                "HPIC batch ingest"
```

**Single-case configuration:**

```yaml
source_path: /data/local_staging/user_dump/
ingest:
  delete_source_after_ingest: false
registry:
  instrument:           ZWSI
  data_ecosystem:       MICROSCOPY
  operator:             MBC
  data_source:          internal
  sample_id:            MOUSE-2024-042
  sample_type:          "mouse lung section"
  acquisition_datetime: "2026-02-15"
  notes:                "First test of ingest workflow"
```

**Usage:**
```bash
python tools/ingest_raw.py --config batch_hpic.yaml --dry-run    # preview (full mode)
python tools/ingest_raw.py --config batch_hpic.yaml               # execute (full mode)
python tools/ingest_raw.py --interactive                           # single case (full mode)
python tools/ingest_raw.py --config quick.yaml --lightweight       # lightweight mode
python tools/ingest_raw.py --config batch.yaml --delete-source     # remove source after verify (default OFF)
python tools/ingest_raw.py --interactive --lightweight             # lightweight interactive
```

**Key features:**
- Three-block YAML schema: `ingest:` (control), `auto_discover:` (extract `discovered.*`), `registry:` (explicit per-column mapping with literal | `discovered.X` | `${...}` interp | NA). Template at `tools/templates/ingest_template.yaml`.
- Auto-populated columns (`acq_id`, `registration_datetime`, `primary_file_name`, `file_format`, `file_size_mb`, `file_count`, `canonical_path`, `checksum_present`, `extended_metadata_present`, `original_name`, `ingest_config`) — script-controlled, not user-editable.
- `ingest_config` registry column records the relative path of the YAML config that produced the row, for auditability + reproducibility.
- Two ingest modes: full (default) and lightweight (`--lightweight`, planned)
- DICOM header auto-detection (modality, StudyDate via pydicom) — full mode
- DICOM archive creation (compress to .zip or .tar.gz) — full mode (planned)
- Microscopy single-file ingest (`.czi` etc.) with rename to canonical `{acq_id}{ext}`
- `metadata.json` sidecar (cross-format; `user_supplied` + `discovered`; ecosystem-specific section reserved for embedded-metadata extraction)
- Filename parser (positional) for instruments that encode metadata in filenames
- Collaborator instrument codes: X-prefix (e.g., `XMRI` for external MRI)
- Copy verification: SHA-256 source→dest comparison
- **Idempotent re-runs**: `expand_batch` checks the registry by `(acquisition_date, original_name)` and skips already-ingested files
- `--delete-source` flag removes the source file/folder after a successful verify (cross-instrument; default OFF; never touches the parent of `source_path`)
- Project link creation: `.lnk` shortcut placed in `<project>/raw_linked/` when `--project` is set (Windows-only — see §2.1.1)
- `--dry-run` mode for previewing without changes
- Batch auto-discovery for processing many cases at once (file or directory globs)

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
