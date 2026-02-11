# 03 — Raw Storage Area

**Parent:** [Documentation Index](00_INDEX.md)  
**Status:** 🔶 Draft  
**Last Updated:** 2026-02-02

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
| **Structured by instrument and time** | Consistent hierarchy enables discovery and automation |
| **Minimal manual entry** | Scripts handle organization, renaming, checksums, and registry updates |

---

## 2. Directory Structure

```
/gjesus3/
└── raw/
    ├── registry_raw.csv                    # Master registry (see 06_REGISTRIES)
    │
    ├── zeiss-wsi/                          # Instrument: Zeiss Axiocam 7 WSI
    │   └── 2026/
    │       └── 2026-02/
    │           └── ACQ-20260215-ZWSI-001/  # Acquisition folder
    │               ├── sample_slide.czi    # Primary data file (exactly one)
    │               ├── metadata.xml        # Extended metadata (if extracted)
    │               ├── checksums.json      # Integrity manifest
    │               └── README.txt          # Acquisition notes
    │
    ├── cell-observer/                      # Zeiss Axio Observer (Cell Observer)
    │   └── 2026/
    │       └── 2026-02/
    │           └── ACQ-20260215-CELL-001/  # Code TBD
    │               ├── timelapse.czi
    │               ├── checksums.json
    │               └── README.txt
    │
    ├── lsm900/                            # Zeiss LSM 900 (confocal)
    │   └── 2026/
    │       └── 2026-02/
    │           └── ACQ-20260215-LSM9-001/  # Code TBD
    │               ├── confocal_stack.czi
    │               ├── checksums.json
    │               └── README.txt
    │
    ├── pet/                               # PET reconstructed imaging
    │   └── 2026/
    │       └── 2026-02/
    │           └── ACQ-20260215-PET-001/
    │               ├── series/            # DICOM series folder
    │               │   ├── *.dcm
    │               │   └── ...
    │               ├── checksums.json
    │               └── README.txt
    │
    └── mri/                               # MRI reconstructed imaging
        └── 2026/
            └── 2026-02/
                └── ACQ-20260215-MRI-001/
                    ├── series/            # DICOM series folder
                    │   ├── *.dcm
                    │   └── ...
                    ├── checksums.json
                    └── README.txt
```

### 2.1 Path Pattern

```
/raw/<instrument>/<YYYY>/<YYYY-MM>/<ACQ-ID>/
```

| Component | Description |
|-----------|-------------|
| `<instrument>` | Instrument or modality code (see Section 3.2) |
| `<YYYY>` | Year of acquisition |
| `<YYYY-MM>` | Year-month of acquisition |
| `<ACQ-ID>` | Unique acquisition identifier (see Section 3.1) |

### 2.2 Acquisition Folder Contents

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
| `<INST>` | Instrument code (3-4 chars) | `ZWSI`, `HIST`, `PET` |
| `<SEQ>` | Daily sequence number (3 digits) | `001`, `002` |

**Example:** `ACQ-20260215-ZWSI-001`

> **📣 INPUT NEEDED:** Should operator be encoded in the ID? Previous spec included it (`20250122_ZWSI_MBC_001`) but this adds complexity. Operator is captured in registry and README.

### 3.2 Instrument Codes

> **🔶 DRAFT:** Likely to organize by instrument rather than abstract modality (more concrete for users), but this still needs team discussion.

| Code | Instrument/Category | Formats | Data Source |
|------|---------------------|---------|-------------|
| `ZWSI` | Zeiss Axiocam 7 (whole-slide imaging) | .czi | Microscope (direct) |
| TBD | Zeiss Axio Observer (Cell Observer) | .czi | Microscope (direct) |
| TBD | Zeiss LSM 900 (confocal) | .czi | Microscope (direct) |
| `PET` | PET reconstructed (Molecubes beta-CUBE / MILabs VECTor) | .dcm, possibly .nii (TBC) | Nuclear Imaging platform (reconstructed) |
| `SPECT` | SPECT reconstructed (Molecubes gamma-CUBE / MILabs VECTor) | .dcm, possibly .nii (TBC) | Nuclear Imaging platform (reconstructed) |
| `CT` | CT reconstructed (Molecubes X-CUBE / MILabs VECTor) | .dcm, possibly .nii (TBC) | Nuclear Imaging platform (reconstructed) |
| `MRI` | MRI reconstructed (Bruker BioSpec 11.7T and 7T) | .dcm (TBC) | MRI platform (reconstructed) |

> **🔶 DRAFT:** Codes for Cell Observer and LSM 900 need to be assigned.

> **❓ EVALUATING:** Additional codes pending:
> - `SEM` — Scanning electron microscopy (if included)
> - `TEM` — Transmission electron microscopy (if included)

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

### 4.3 Known Exceptions

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
2. **Create acquisition folder:** Using correct path and ACQ-ID
3. **Copy files:** Primary file + any supporting files
4. **Generate checksums:** `sha256sum` or script
5. **Add README:** Minimum required metadata
6. **Register:** Add entry to `registry_raw.csv`
7. **Lock:** Notify admin to set read-only permissions

#### Option B: Script-Assisted Deposit (Target State)

1. **Place files in staging:** Any naming convention
2. **Prepare config file:** Specify metadata (instrument, date, sample info, etc.)
3. **Run ingest script:** Script handles:
   - Creating acquisition folder with correct structure
   - Renaming files (if configured)
   - Generating checksums
   - Creating README from config
   - Appending to registry
   - Optionally: linking to project folder
4. **Verify and lock:** Review output; admin sets read-only

> **⚠️ GAP:** Ingest script not yet implemented. See [10_TOOLS](10_TOOLS.md).

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

---

## Open Questions Summary

| ID | Question | Owner | Status |
|----|----------|-------|--------|
| RAW-01 | Include operator in ACQ-ID or registry only? | Data Mgmt Lead | 🔶 Draft |
| RAW-02 | How to handle multi-file primary outputs? | Data Mgmt Lead + Users | ⚠️ Need examples |
| RAW-03 | SEM/TEM inclusion decision | PI | ❓ Evaluating |
| RAW-04 | Verification automation approach | Data Mgmt Lead | 📋 Future |
| RAW-05 | Organize by instrument or by abstract modality? Instrument-based is likely but needs team discussion. | Data Mgmt Lead + Users | 🔶 Draft |
