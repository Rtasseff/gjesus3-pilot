# 03 — Raw Storage Area

**Parent:** [Documentation Index](00_INDEX.md)
**Status:** 🔶 Draft
**Last Updated:** 2026-03-06

---

## Purpose

This document specifies the structure, conventions, and workflows for the Raw storage area — the authoritative archive for original imaging acquisitions.

---

## 1. Design Principles

> **✅ DECIDED:** Raw is the most rigidly defined area, intended for long-term archiving of original, immutable data.

| Principle | Implementation |
|-----------|----------------|
| **Immutable after deposit** | Files and folders become read-only after registration |
| **One primary file per acquisition** | Each acquisition folder contains exactly one primary data file (no exceptions — DICOM stored as compressed archive) |
| **Structured by data ecosystem and time** | Consistent hierarchy enables discovery and automation |
| **Minimal manual entry** | Scripts handle organization, renaming, checksums, and registry updates |

---

## 2. Directory Structure

> **✅ DECIDED:** Raw data is organized by **data ecosystem** (the tooling/standard family that handles the data) rather than by individual instrument. Instrument identity is captured in the acquisition ID and registry.

### 2.1 Rationale

Organizing by data ecosystem rather than by instrument solves several problems:

| Problem | How ecosystem organization addresses it |
|---------|----------------------------------------|
| New instruments doing the same thing (e.g., second MRI) | No new folder needed; same ecosystem |
| Hybrid instruments (e.g., PET/CT) | Stays together; one DICOM Study bundle |
| Collaborator data from unknown instruments | Classify by format ecosystem, not instrument |
| Folder proliferation | Three stable top-level folders instead of one per instrument |
| Tooling alignment | Maps directly to downstream servers (OMERO, XNAT/PACS) |

### 2.2 Data Ecosystems

| Ecosystem Folder | What Goes Here | File Standards | Downstream Tooling |
|------------------|----------------|----------------|---------------------|
| `MICROSCOPY/` | Light microscopy: WSI, confocal, epifluorescence, etc. | CZI, OME-TIFF, TIFF, ND2, etc. (Bio-Formats compatible) | OMERO, Bio-Formats, QuPath |
| `DICOM/` | Biomedical/preclinical imaging: MRI, PET, SPECT, CT, hybrid | DICOM (.dcm), possibly NIfTI | XNAT, PACS, 3D Slicer, PMOD |
| `EM/` | Electron microscopy: SEM, TEM | .tif, .dm3, .dm4, proprietary | Specialized EM tools |

### 2.3 Directory Tree

```
/gjesus3/
├── registries/
│   └── registry_raw.csv                # Master registry (see 06_REGISTRIES)
│
└── raw/
    ├── MICROSCOPY/                         # Bio-Formats / OMERO ecosystem
    │   └── 2026/
    │       └── 2026-02/
    │           ├── ACQ-20260215-ZWSI-001/  # Zeiss WSI acquisition
    │           │   ├── sample_slide.czi    # Primary data file (exactly one)
    │           │   ├── metadata.json       # Extended metadata (if extracted)
    │           │   ├── checksums.json      # Integrity manifest
    │           │   └── README.txt          # Acquisition notes
    │           │
    │           └── ACQ-20260218-LSM9-001/  # LSM 900 confocal acquisition
    │               ├── confocal_stack.czi
    │               ├── checksums.json
    │               └── README.txt
    │
    ├── DICOM/                              # DICOM ecosystem
    │   └── 2026/
    │       └── 2026-02/
    │           ├── ACQ-20260215-MRI-001/   # MRI acquisition
    │           │   ├── ACQ-20260215-MRI-001.zip   # Compressed DICOM archive (primary)
    │           │   ├── metadata.json              # Auto-extracted extended metadata
    │           │   ├── checksums.json
    │           │   └── README.txt
    │           │
    │           └── ACQ-20260220-PET-001/   # PET acquisition (or PET/CT hybrid)
    │               ├── ACQ-20260220-PET-001.zip   # Compressed DICOM archive (primary)
    │               ├── metadata.json              # Auto-extracted extended metadata
    │               ├── checksums.json
    │               └── README.txt
    │
    └── EM/                                 # Electron microscopy ecosystem
        └── 2026/
            └── 2026-03/
                └── ACQ-20260310-SEM-001/
                    ├── sample_surface.tif
                    ├── checksums.json
                    └── README.txt
```

### 2.4 Path Pattern

```
/raw/<ECOSYSTEM>/<YYYY>/<YYYY-MM>/<ACQ-ID>/
```

| Component | Description |
|-----------|-------------|
| `<ECOSYSTEM>` | Data ecosystem: `MICROSCOPY`, `DICOM`, or `EM` |
| `<YYYY>` | Year of acquisition |
| `<YYYY-MM>` | Year-month of acquisition |
| `<ACQ-ID>` | Unique acquisition identifier (see Section 3.1) |

### 2.5 Ingestion Decision Rule

When depositing raw data:

| If the data is... | Deposit to | Examples |
|-------------------|------------|----------|
| Microscopy vendor files or Bio-Formats compatible | `MICROSCOPY/` | .czi, .nd2, .lif, .ome.tif |
| DICOM or originated as DICOM | `DICOM/` | .dcm folders, DICOM-derived .nii |
| Electron microscopy | `EM/` | .tif (from SEM/TEM), .dm3, .dm4 |
| Unclear / unclassifiable | `staging/` first | Classify before promotion to raw |

### 2.6 Acquisition Folder Contents

| File | Required | Description |
|------|----------|-------------|
| Primary data file | ✅ Yes | Exactly one (see Section 4). For DICOM, this is a compressed archive (.zip or .tar.gz) |
| `checksums.json` | ✅ Yes | SHA-256 checksums for all files |
| `README.txt` | 🔶 Recommended | Acquisition notes (see [08_METADATA](08_METADATA.md)) |
| `metadata.json` | 🔶 Recommended | Auto-extracted extended metadata (generated by full-mode ingest) |
| Supporting files | Optional | Logs, thumbnails, secondary exports |

---

## 3. Naming Conventions

### 3.1 Acquisition ID

> **🔶 DRAFT:** Format under refinement.

**Pattern:**
```
ACQ-<YYYYMMDD>-<INST>-<SEQ>
```

| Component | Description | Example |
|-----------|-------------|---------|
| `ACQ` | Fixed prefix indicating acquisition | `ACQ` |
| `<YYYYMMDD>` | Date of acquisition | `20260215` |
| `<INST>` | Instrument code (3-4 chars) | `ZWSI`, `LSM9`, `PET` |
| `<SEQ>` | Daily sequence number (3 digits) | `001`, `002` |

**Example:** `ACQ-20260215-ZWSI-001`

The instrument code in the ACQ-ID preserves discoverability (you can tell which instrument produced the data from the ID alone), even though the folder hierarchy is organized by ecosystem, not instrument.

> **📣 INPUT NEEDED:** Should operator be encoded in the ID? Previous spec included it (`20250122_ZWSI_MBC_001`) but this adds complexity. Operator is captured in registry and README.

### 3.2 Instrument Codes

Instrument codes identify the source instrument in the ACQ-ID and registry. They are **not** used as folder names.

| Code | Instrument/Category | Ecosystem | Formats | Data Source |
|------|---------------------|-----------|---------|-------------|
| `ZWSI` | Zeiss Axiocam 7 (whole-slide imaging) | MICROSCOPY | .czi | Microscope (direct) |
| `CELL` | Zeiss Axio Observer (Cell Observer) | MICROSCOPY | .czi | Microscope (direct) |
| `LSM9` | Zeiss LSM 900 (confocal) | MICROSCOPY | .czi | Microscope (direct) |
| `PET` | PET reconstructed (Molecubes beta-CUBE / MILabs VECTor) | DICOM | .dcm, possibly .nii (TBC) | Nuclear Imaging platform (reconstructed) |
| `SPECT` | SPECT reconstructed (Molecubes gamma-CUBE / MILabs VECTor) | DICOM | .dcm, possibly .nii (TBC) | Nuclear Imaging platform (reconstructed) |
| `CT` | CT reconstructed (Molecubes X-CUBE / MILabs VECTor) | DICOM | .dcm, possibly .nii (TBC) | Nuclear Imaging platform (reconstructed) |
| `MRI` | MRI reconstructed (Bruker BioSpec 11.7T and 7T) | DICOM | .dcm (TBC) | MRI platform (reconstructed) |

#### Collaborator / External Data Codes

> **✅ DECIDED:** External collaborator data uses an `X` prefix on the modality code.

| Code | Description | Ecosystem | Formats |
|------|-------------|-----------|---------|
| `XMRI` | External MRI (collaborator-provided DICOM) | DICOM | .dcm |
| `XCT` | External CT (collaborator-provided DICOM) | DICOM | .dcm |
| `XPET` | External PET (collaborator-provided DICOM) | DICOM | .dcm |
| `XSPECT` | External SPECT (collaborator-provided DICOM) | DICOM | .dcm |

The exact code is determined by DICOM header inspection during ingestion (Modality tag 0008,0060). The `data_source` registry field records the collaborator origin (e.g., `collaborator:HPIC`).

> **❓ EVALUATING:** Additional codes pending:
> - `SEM` — Scanning electron microscopy (if included)
> - `TEM` — Transmission electron microscopy (if included)

### 3.3 Hybrid / Multi-Modal Instruments

For instruments that produce multiple modalities in a single session (e.g., PET/CT, PET/SPECT/CT):

> **✅ DECIDED:** Keep the entire output together as **one acquisition**. Do not split into separate folders per modality.

- Use the dominant modality code in the ACQ-ID (e.g., `PET` for a PET/CT session)
- Record all modalities present in the registry field `modalities_in_study` (e.g., `PT;CT`)
- The DICOM Study structure already groups related series; preserve this grouping

### 3.4 Collaborator Data

Data from external collaborators follows the same rules:

1. Classify by data ecosystem (MICROSCOPY, DICOM, or EM)
2. Assign an instrument code — use the actual instrument code if known, or the `X`-prefix generic code (e.g., `XMRI` for external MRI); see Section 3.2 for the full table
3. Record `data_source` as `collaborator:<name>` in registry; note external origin in README

---

## 4. One Primary File Rule

> **✅ DECIDED:** Each acquisition folder contains exactly **one primary data file**.

### 4.1 Definition

The **primary data file** is:
- The authoritative raw output from the instrument
- The file that would be opened in analysis software
- The file referenced in provenance tracking

### 4.2 What Counts as Primary vs. Supporting

| File Type | Classification | Notes |
|-----------|----------------|-------|
| Instrument native file (.czi, .nd2, etc.) | **Primary** | The raw acquisition |
| DICOM compressed archive (.zip/.tar.gz) | **Primary** | Compressed archive of DICOM series |
| Metadata exports (.xml, .json) | Supporting | Machine-readable metadata |
| Thumbnails, previews | Supporting | Convenience files |
| Acquisition logs | Supporting | Instrument logs |
| README.txt | Supporting | Human notes |
| Checksums | Supporting | Integrity manifest |

### 4.3 Generalized Rule

> **✅ DECIDED:** Every acquisition has exactly **one primary file** — no exceptions.

- For microscopy: the native instrument file (e.g., `.czi`)
- For DICOM: a compressed archive (`.zip` or `.tar.gz`) containing the DICOM series

This keeps the rule and registry semantics uniformly clean: one row per acquisition, one primary file per folder.

### 4.4 Edge Cases Under Investigation

> **🔶 DRAFT:** The one-primary-file rule has no exceptions. The patterns below may require guidance on how to split acquisitions or handle multi-file instrument outputs within the rule.

| Pattern | Example | Proposed Handling |
|---------|---------|-------------------|
| Multi-channel as separate files | Some microscopes export each channel as separate .tif | Combine into one acquisition; treat the set as the primary file (or re-export as single .czi/.ome.tif) |
| Multiple biosamples in one session | Batch scan of multiple slides | Separate acquisition per slide |
| Multi-series DICOM | Multiple reconstruction methods | Single acquisition folder; all series in one archive; document in README |

> **📣 INPUT NEEDED:** What multi-file patterns do current instruments produce? Will be investigated during per-modality ingestion testing.

---

## 5. Deposit Workflow

### 5.1 Overview

```
                    ┌──────────────────────┐
                    │  Acquire (instrument)│
                    └──────────┬───────────┘
                               │
              ┌────────────────┴────────────────┐
              ▼                                 ▼
┌───────────────────────┐         ┌───────────────────────┐
│  Fast local storage   │         │  NAS staging/         │
│  (recommended)        │         │  (secondary dump)     │
│  Full-mode ingest     │         │  Lightweight ingest   │
│  → extract metadata   │         │  → archive as-is      │
│  → compress DICOM     │         │  → minimum registry   │
│  → copy to NAS        │         │  → no extraction      │
└───────────┬───────────┘         └───────────┬───────────┘
            │                                 │
            └────────────────┬────────────────┘
                             ▼
                  ┌─────────────────────┐
                  │   Raw (rigid)       │
                  │   Structured        │
                  │   Registered        │
                  │   Permanent         │
                  │   Read-only         │
                  └─────────────────────┘
```

### 5.2 Staging and Source Locations

> **✅ DECIDED:** Primary staging for ingest uses fast local or network storage (off-NAS). The NAS `staging/` directory is retained as a secondary convenience dump.

#### Primary: Fast local/network storage (recommended)

**Purpose:** Data is placed on fast local storage (e.g., workstation SSD, local NAS, or fast network path) where extraction, metadata analysis, and compression can happen efficiently before copying the final result to the NAS.

**Why off-NAS:** The NAS SMB share is too slow for operations like extracting thousands of small DICOM files, reading headers, and recompressing. Performing these operations locally avoids an extra copy hop and is dramatically faster.

**Usage:** Full-mode ingest reads from a local source path, processes the data, and writes the final output to the NAS raw area.

#### Secondary: NAS `/gjesus3/staging/`

**Purpose:** Convenience dump for users who do not have access to the recommended local workflow. Researchers can drop files with any naming convention. Data deposited here can be ingested in lightweight mode (archive as-is, minimum registry info, no metadata extraction).

**Retention:** Very temporary — clear periodically (weekly? after ingest?)

> **Note:** Lightweight ingests from NAS staging can be upgraded later using the `backfill_metadata` utility (see [10_TOOLS](10_TOOLS.md)).

### 5.3 Deposit Steps

> **✅ DECIDED:** Two ingest modes — full (default) and lightweight. Both are script-assisted via `ingest_raw.py`.

**Full Mode** (default): Source on fast local storage. Analyzes data, extracts embedded metadata to `metadata.json`, compresses DICOM to archive, copies result to NAS, populates all registry fields.

**Lightweight Mode** (`--lightweight`): Source on NAS staging or any path. Copies archive as-is, populates minimum registry fields, sets `extended_metadata_present` = `N`. Can be upgraded later using `backfill_metadata`.

> See [10_TOOLS](10_TOOLS.md) Section 2.1 for the detailed step-by-step workflow for each mode.

> **✅ Implemented:** See `tools/ingest_raw.py` and [10_TOOLS](10_TOOLS.md) for details.

### 5.4 Timeline

> **✅ DECIDED:** Registration must occur **same day** as acquisition.

This ensures metadata is captured while fresh and prevents accumulation of unregistered data.

---

## 6. Integrity Verification

### 6.1 Checksum Format

**File:** `checksums.json`

```json
{
  "generated": "2026-02-15T14:30:00Z",
  "algorithm": "sha256",
  "files": {
    "sample_slide.czi": "a1b2c3d4e5f6...",
    "README.txt": "f6e5d4c3b2a1..."
  }
}
```

### 6.2 Verification Schedule

| Frequency | Scope | Purpose |
|-----------|-------|---------|
| At deposit | All files in acquisition | Baseline integrity |
| Quarterly | Random sample (10%?) | Detect silent corruption |
| On retrieval | Requested files | Verify before use |

> **🔶 DRAFT:** Verification automation not yet planned.

---

## 7. Access Control

| When | Permissions |
|------|-------------|
| During deposit | Operator can write to acquisition folder |
| After registration | Folder set to read-only for all users |
| Corrections needed | Admin temporarily unlocks; changes logged |

**Implementation:** File system permissions (chmod or ACL). Admin role required for changes.

---

## 8. Related Documents

- [06_REGISTRIES](06_REGISTRIES.md) — Raw registry schema
- [08_METADATA](08_METADATA.md) — README template and extended metadata
- [09_MODALITIES](09_MODALITIES.md) — Detailed instrument information
- [10_TOOLS](10_TOOLS.md) — Ingest script specification
- [12_CURATED_DATASETS](12_CURATED_DATASETS.md) — Curated derived datasets (references raw by ACQ-ID)

---

## Open Questions Summary

| ID | Question | Owner | Status |
|----|----------|-------|--------|
| RAW-01 | Include operator in ACQ-ID or registry only? | Data Mgmt Lead | 🔶 Draft |
| RAW-02 | How to handle multi-file primary outputs? | Data Mgmt Lead + Users | ⚠️ Need examples |
| RAW-03 | SEM/TEM inclusion decision | PI | ❓ Evaluating |
| RAW-04 | Verification automation approach | Data Mgmt Lead | 📋 Future |
| ~~RAW-05~~ | ~~Organize by instrument or by abstract modality?~~ | — | ✅ Resolved: ecosystem-based (see Section 2) |
| ~~RAW-06~~ | ~~Generic instrument codes for collaborator / external data~~ | — | ✅ Resolved: X-prefix codes (e.g., `XMRI`, `XCT`); see Section 3.2 |
| ~~RAW-07~~ | ~~DICOM storage format (expanded vs. archive)?~~ | — | ✅ Resolved: compressed archives (.zip/.tar.gz); see Sections 2.3, 4.3 |
| ~~RAW-08~~ | ~~Primary staging location (NAS vs. off-NAS)?~~ | — | ✅ Resolved: primary off-NAS (fast local); NAS staging secondary; see Section 5.2 |
| RAW-09 | Archive format preference: .zip vs .tar.gz? | Data Mgmt Lead | ❓ Evaluating — .zip has Windows compatibility edge |
