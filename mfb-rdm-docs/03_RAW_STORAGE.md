# 03 — Raw Storage Area

**Parent:** [Documentation Index](00_INDEX.md)
**Status:** 🔶 Draft
**Last Updated:** 2026-05-20 (per-ecosystem layouts: internal MRI folder-as-primary; one-file rule generalised — see §4)

---

## Purpose

This document specifies the structure, conventions, and workflows for the Raw storage area — the authoritative archive for original imaging acquisitions.

---

## 1. Design Principles

> **✅ DECIDED:** Raw is the most rigidly defined area, intended for long-term archiving of original, immutable data.

| Principle | Implementation |
|-----------|----------------|
| **Immutable after deposit** | Files and folders become read-only after registration |
| **One primary entity per acquisition (shape varies by ecosystem)** | Each acquisition folder contains exactly one primary entity. The *shape* of that entity is set by ecosystem (see §4): single file for microscopy; compressed archive for collaborator DICOM (legacy); structured folder bundle for internal MRI (per the [13_GJESUS3_ROLE](13_GJESUS3_ROLE.md) reframe — no-zip, directly viewable) |
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
    ├── MICROSCOPY/                              # Bio-Formats / OMERO ecosystem
    │   └── 2026/
    │       └── 2026-02/
    │           ├── ACQ-20260215-ZWSI-001/       # Zeiss WSI acquisition
    │           │   ├── ACQ-20260215-ZWSI-001.czi   # Primary data file (renamed to acq_id)
    │           │   ├── metadata.json            # Extended metadata (auto-extracted; full mode)
    │           │   ├── checksums.json           # Integrity manifest
    │           │   └── README.txt               # Acquisition notes
    │           │
    │           └── ACQ-20260218-LSM9-001/       # LSM 900 confocal acquisition
    │               ├── ACQ-20260218-LSM9-001.czi
    │               ├── metadata.json
    │               ├── checksums.json
    │               └── README.txt
    │
    ├── DICOM/                              # DICOM ecosystem — shape varies (see §4)
    │   ├── 2026/
    │   │   └── 2026-02/
    │   │       └── ACQ-20260215-XMRI-001/  # Collaborator DICOM (LEGACY shape: zip)
    │   │           ├── ACQ-20260215-XMRI-001.zip   # Compressed archive — primary
    │   │           ├── metadata.json
    │   │           ├── checksums.json
    │   │           └── README.txt
    │   │
    │   └── 2025/
    │       └── 2025-10/
    │           └── ACQ-20251016-MRI-029/   # Internal MRI (CURRENT shape: folder bundle, no zip)
    │               ├── metadata.json              # Rich mri: block from ParaVision JCAMP-DX
    │               ├── checksums.json
    │               ├── README.txt
    │               ├── reconstructions/           # User-selected recon indices preserved
    │               │   └── pdata_3/               # (e.g. /3 is the user-trusted reconstruction)
    │               │       ├── 2dseq              # Reconstructed image binary
    │               │       ├── visu_pars
    │               │       ├── reco
    │               │       └── dicom/             # Bruker-exported DICOM frames as-found
    │               │           ├── MRIm01.dcm
    │               │           └── MRIm15.dcm
    │               └── acquisition_aux/           # Study/exam-level ParaVision aux files
    │                   ├── acqp
    │                   ├── method
    │                   └── visu_pars
    │
    └── EM/                                 # Electron microscopy ecosystem
        └── 2026/
            └── 2026-03/
                └── ACQ-20260310-SEM-001/
                    ├── ACQ-20260310-SEM-001.tif    # Primary data file (renamed to acq_id)
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
| Primary entity (file, archive, or folder) | ✅ Yes | Exactly one per acquisition. Shape varies by ecosystem (see §4). |
| `checksums.json` | ✅ Yes | SHA-256 checksums for all files |
| `README.txt` | 🔶 Recommended | Acquisition notes (see [08_METADATA](08_METADATA.md)) |
| `metadata.json` | 🔶 Recommended | Auto-extracted extended metadata (generated by full-mode ingest; cross-format shape in [08_METADATA §4.3](08_METADATA.md#43-sidecar-generator-and-special-fields-promotion-implemented)) |
| Supporting files | Optional | Logs, thumbnails, secondary exports |

**Canonical naming rule (full-mode ingest):** the primary entity is named or organised canonically on copy:
- **Microscopy single-file** → `<ACQ-ID>.<ext>` (e.g. `<ACQ-ID>.czi`)
- **Collaborator DICOM** (legacy) → `<ACQ-ID>.zip` (compressed archive)
- **Internal MRI** (per the 2026-05-20 reframe) → no synthetic primary file; the acquisition folder itself is the primary entity, with `reconstructions/pdata_<idx>/` + `acquisition_aux/` substructure preserved as-found (no zip). Registry uses `primary_kind: folder`. See §4 for the full rule.

The original source name is preserved in the registry's `original_name` column and in `metadata.json`'s `user_supplied.original_name`, so the user-facing name from the source system is never lost.

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
| `ZWSI` | Zeiss Axio Scan 7 (whole-slide imaging) | MICROSCOPY | .czi | Microscope (direct) |
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

## 4. One Primary Entity per Acquisition (shape by ecosystem)

> **✅ DECIDED (generalised 2026-05-20):** Each acquisition folder contains exactly **one primary entity** — the authoritative thing that *is* the acquisition. The *shape* of that entity (single file vs. compressed archive vs. folder bundle) is set per ecosystem based on what the underlying data naturally produces and what the [research-facing reframe](13_GJESUS3_ROLE.md) requires for direct viewability.

### 4.1 Definition

The **primary entity** is:
- The authoritative raw output from the instrument (per gjesus3's research-facing scope — not necessarily byte-perfect originals; see [13_GJESUS3_ROLE §5](13_GJESUS3_ROLE.md))
- What analysis software opens (directly, or after a small project-level conversion step)
- What provenance refers to

### 4.2 Per-Ecosystem Shape

| Ecosystem / Source | Primary entity shape | Reasoning | Registry `primary_kind` |
|---|---|---|---|
| **Microscopy** (Zeiss `.czi`) | Single file `<ACQ-ID>.czi` | `.czi` is a modern container; one acquisition = one file natively | `file` |
| **Collaborator DICOM** (XMRI/XCT/XPET/XSPECT) | Compressed archive `<ACQ-ID>.zip` | LEGACY shape — many `.dcm` per session, zipped on deposit; existing 75 acqs (rounds 1-2) follow this pattern. Not the recommended shape going forward but stays for already-deposited data. | `archive` |
| **Internal MRI** (Bruker ParaVision) | Folder bundle `<ACQ-ID>/` (no zip, no synthetic single file) | Many `.dcm` per acquisition (per-frame DICOM is a 1990s-era format choice, not a conceptual mismatch — see [13_GJESUS3_ROLE §5.2](13_GJESUS3_ROLE.md)). No-zip per the research-facing reframe. Folder is directly viewable without extraction. | `folder` |
| **Internal PET/SPECT/CT** (planned) | TBD when those rounds are scoped — likely folder bundle following the MRI precedent | Same DICOM packaging problem as internal MRI | — |
| **EM** (planned) | Single file `<ACQ-ID>.<ext>` | One acquisition = one file natively for SEM/TEM | `file` |

### 4.3 Internal MRI folder bundle — detail

For internal MRI (ParaVision), the acquisition folder contains:

```
ACQ-<YYYYMMDD>-MRI-<exam>/
  metadata.json                    <-- rich mri: block from ParaVision JCAMP-DX
  checksums.json
  README.txt                       (optional)
  reconstructions/
    pdata_<idx>/                   <-- one subfolder per reconstruction index kept
      2dseq                            (per the `reconstructions:` config flag;
      visu_pars                        defaults are per-instrument-template)
      reco
      dicom/
        MRIm01.dcm
        ...
  acquisition_aux/
    acqp
    method
    visu_pars
    (specpar, uxnmr.par, ...)
```

The folder IS the unit. Researchers can open `metadata.json` to discover what's there; they can navigate `reconstructions/pdata_3/dicom/` to load the DICOM series into a viewer; they can read the JCAMP-DX aux files directly if they need sequence parameters.

### 4.4 Supporting vs. primary

| File Type | Classification | Notes |
|-----------|----------------|-------|
| Instrument native file (.czi, .nd2, etc.) | **Primary** | The raw acquisition |
| DICOM compressed archive (.zip/.tar.gz) | **Primary (legacy)** | Compressed archive of DICOM series — collaborator XMRI shape |
| Acquisition folder bundle | **Primary (no-zip ecosystems)** | The folder itself is the unit — internal MRI shape |
| Metadata exports (.xml, .json) | Supporting | Machine-readable metadata |
| Thumbnails, previews | Supporting | Convenience files |
| Acquisition logs | Supporting | Instrument logs |
| README.txt | Supporting | Human notes |
| `checksums.json` | Supporting | Integrity manifest |

### 4.5 Edge cases — guidance

| Pattern | Example | Handling |
|---------|---------|----------|
| Multi-channel as separate files | Some microscopes export each channel as separate .tif | Combine into one acquisition; treat the set as the primary file (or re-export as single .czi/.ome.tif) |
| Multiple biosamples in one session | Batch scan of multiple slides | Separate acquisition per slide |
| Multi-reconstruction MR exam | ParaVision `/1`, `/2`, `/3`, ... | One acquisition per exam; the `reconstructions:` config flag controls which recon indices land (e.g. `all`, `[3]`, `3`). Discarded indices stay only on the platform's deep-archive. |
| Multi-series DICOM (legacy zip case) | Multiple reconstruction methods, collaborator data | Single acquisition folder; all series in one archive; document in README |

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

## 8. Linking Raw to Projects and Publications

> **✅ DECIDED — Windows-first, deliberately:** Cross-references from project (and, in future, publication) folders back into raw use **Windows `.lnk` shell shortcuts**. This is a pilot-specific choice driven by the MFB Windows user base and constraints on the QNAP (no working SSH access to create server-side symlinks). It is **not** the recommended default for future RDM deployments — see [10_TOOLS §2.1.1](10_TOOLS.md#211-project-linking--windows-first-design-decision) for the full rationale, tradeoffs, and a porting guide for Linux/WSL or SSH-capable environments.

**Behavior at ingest time:** When `ingest_raw.py` is run with `--project <PROJ-ID>`, full-mode ingest creates a shortcut at `/projects/<project_folder>/raw_linked/<original_archive_name>.lnk` pointing at the canonical archive on the NAS via UNC path. Idempotent — re-running ingest skips any shortcut already in place.

**Manifest as portable fallback:** Independent of `.lnk` creation, every ingest appends a row to `registries/ingest_manifest.csv` mapping the original source name to its ACQ-ID and canonical path. Scripts and non-Windows tooling that can't (or don't want to) follow `.lnk` files should consume the manifest instead.

---

## 9. Related Documents

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
