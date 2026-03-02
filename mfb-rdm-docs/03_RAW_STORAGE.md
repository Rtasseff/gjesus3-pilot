# 03 — Raw Storage Area

**Parent:** [Documentation Index](00_INDEX.md)
**Status:** 🔶 Draft
**Last Updated:** 2026-03-02

---

## Purpose

This document specifies the structure, conventions, and workflows for the Raw storage area — the authoritative archive for original imaging acquisitions.

---

## 1. Design Principles

> **✅ DECIDED:** Raw is the most rigidly defined area, intended for long-term archiving of original, immutable data.

| Principle | Implementation |
|-----------|----------------|
| **Immutable after deposit** | Files and folders become read-only after registration |
| **One primary file per acquisition** | Each acquisition folder contains exactly one primary data file (with documented exceptions) |
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
    │           │   ├── series/             # DICOM series folder (primary)
    │           │   │   ├── *.dcm
    │           │   │   └── ...
    │           │   ├── checksums.json
    │           │   └── README.txt
    │           │
    │           └── ACQ-20260220-PET-001/   # PET acquisition (or PET/CT hybrid)
    │               ├── series/             # Entire DICOM Study kept together
    │               │   ├── *.dcm
    │               │   └── ...
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
| Primary data file | ✅ Yes | Exactly one (see Section 4) |
| `checksums.json` | ✅ Yes | SHA-256 checksums for all files |
| `README.txt` | 🔶 Recommended | Acquisition notes (see [08_METADATA](08_METADATA.md)) |
| `metadata.xml` or `.json` | Optional | Extended metadata export (instrument-dependent) |
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
| DICOM series folder | **Primary** | Treat the folder as the primary "file" |
| Metadata exports (.xml, .json) | Supporting | Machine-readable metadata |
| Thumbnails, previews | Supporting | Convenience files |
| Acquisition logs | Supporting | Instrument logs |
| README.txt | Supporting | Human notes |
| Checksums | Supporting | Integrity manifest |

### 4.3 Generalized Rule

The primary payload is **one primary entity per acquisition folder**:

- Either **one primary file** (e.g., a `.czi` file)
- Or **one primary bundle** (e.g., a DICOM series folder containing many `.dcm` instances)

This keeps the registry semantics clean (one row per acquisition) without fighting the reality of multi-file formats like DICOM.

### 4.4 Known Exceptions

> **🔶 DRAFT:** Exceptions to be handled case-by-case. Document the pattern when encountered.

| Exception Pattern | Example | Handling |
|-------------------|---------|----------|
| Multi-channel as separate files | Some microscopes export each channel as separate .tif | TBD — may need multi-primary convention |
| Multiple biosamples in one session | Batch scan of multiple slides | Separate acquisition per slide, OR document all in README |
| Multi-series DICOM | Multiple reconstruction methods | Single acquisition folder; document in README |

> **📣 INPUT NEEDED:** What multi-file patterns do current instruments produce? We need examples from each modality.

---

## 5. Deposit Workflow

### 5.1 Overview

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Acquire    │ ──▶ │  Staging    │ ──▶ │    Raw      │
│  (local)    │     │  (flexible) │     │  (rigid)    │
└─────────────┘     └─────────────┘     └─────────────┘
                          │                    │
                    No structure          Structured
                    No registry           Registered
                    Temporary             Permanent
                                          Read-only
```

### 5.2 Staging Area

> **✅ DECIDED:** A staging area allows flexible temporary storage before formal deposit.

**Purpose:**
- Researchers can dump files with any naming convention
- No structure or documentation requirements
- Files are reviewed and organized before promotion to Raw

**Location:** `/gjesus3/staging/` (or similar)

**Retention:** Very temporary — clear periodically (weekly? after ingest?)

### 5.3 Deposit Steps

#### Option A: Manual Deposit (Interim)

1. **Prepare locally:** Gather files, note acquisition details
2. **Identify ecosystem:** Determine if data is MICROSCOPY, DICOM, or EM
3. **Create acquisition folder:** Using correct path (`/raw/<ECOSYSTEM>/<YYYY>/<YYYY-MM>/<ACQ-ID>/`)
4. **Copy files:** Primary file + any supporting files
5. **Generate checksums:** `sha256sum` or script
6. **Add README:** Minimum required metadata
7. **Register:** Add entry to `registry_raw.csv`
8. **Lock:** Notify admin to set read-only permissions

#### Option B: Script-Assisted Deposit (Target State)

1. **Place files in staging:** Any naming convention
2. **Prepare config file:** Specify metadata (instrument, date, sample info, etc.)
3. **Run ingest script:** Script handles:
   - Determining ecosystem from instrument code
   - Creating acquisition folder with correct structure
   - Renaming files (if configured)
   - Generating checksums
   - Creating README from config
   - Appending to registry
   - Optionally: linking to project folder
4. **Verify and lock:** Review output; admin sets read-only

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
