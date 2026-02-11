# 09 — Supported Modalities

**Parent:** [Documentation Index](00_INDEX.md)  
**Status:** ⚠️ Gaps identified  
**Last Updated:** 2026-02-02

---

## Purpose

This document describes the imaging modalities (data types and instruments) supported by the system, including file formats, embedded metadata, and typical workflows.

---

## 1. Confirmed Modalities

### 1.1 Optical Microscopy — Whole-Slide Imaging

| Attribute | Value |
|-----------|-------|
| **Instrument** | Zeiss Axiocam 7 |
| **Code** | `ZWSI` |
| **Primary format** | .czi (Carl Zeiss Image) |
| **Typical size** | 1-10 GB per slide |
| **Embedded metadata** | Extensive (acquisition parameters, dimensions, objectives) |
| **Not embedded** | Sample information, experimental context |
| **Analysis tools** | ZEN, QuPath, ImageJ/FIJI |
| **Status** | ✅ Confirmed for pilot |

### 1.2 Optical Microscopy — Conventional Histology

| Attribute | Value |
|-----------|-------|
| **Instrument** | Various light microscopes |
| **Code** | `HIST` |
| **Primary formats** | .tif, .czi, .jpg |
| **Typical size** | 10 MB - 1 GB |
| **Embedded metadata** | Varies; often minimal for TIFF |
| **Not embedded** | Most sample and acquisition info |
| **Analysis tools** | ImageJ/FIJI, QuPath |
| **Status** | ✅ Confirmed for pilot |

### 1.3 Reconstructed Biomedical Imaging

| Attribute | Value |
|-----------|-------|
| **Sources** | PET, SPECT, CT, MRI scanners |
| **Codes** | `PET`, `SPECT`, `CT`, `MRI` |
| **Primary format** | DICOM (.dcm, DICOM directories) |
| **Typical size** | 100 MB - 10 GB per series |
| **Embedded metadata** | Extensive (DICOM standard) |
| **Not embedded** | Study context beyond DICOM headers |
| **Analysis tools** | 3D Slicer, ITK-SNAP, OsiriX, MATLAB |
| **Status** | ✅ Confirmed for pilot |

**Note:** We store **reconstructed** DICOM, not raw scanner data. Raw data (e.g., PET listmode files) is maintained by the platforms operating the equipment.

---

## 2. Under Evaluation

### 2.1 Electron Microscopy (SEM/TEM)

| Attribute | Value |
|-----------|-------|
| **Sources** | SEM and TEM from EM platform |
| **Codes** | `SEM`, `TEM` (if included) |
| **Primary formats** | .tif, .dm3, .dm4, proprietary |
| **Use case** | Nanomaterial characterization |
| **Status** | ❓ Awaiting confirmation |

> **📣 INPUT NEEDED:** Is SEM/TEM data a good fit for this system?
> - What's the typical workflow?
> - Who would deposit data?
> - Is the EM platform already managing this?

---

## 3. Data Type Sign-Up Sheet

> **⚠️ GAP:** Need researchers to confirm data types they work with.

**Purpose:** Identify all data types, assign volunteer owners, and conduct show-and-tell sessions.

### 3.1 Requested Information

| Column | Description |
|--------|-------------|
| Data type label | Your name for this type of data |
| Source instrument | Specific instrument or system |
| File format(s) | Extensions and formats produced |
| Typical file size | Range of file sizes |
| Downstream tools | What software you use to analyze |
| Current naming pattern | How you currently name files |
| Volunteer owner | Who will demo this data type |

### 3.2 Current Status

| Data Type | Volunteer | Status |
|-----------|-----------|--------|
| Zeiss WSI (.czi) | TBD | 📣 Needs volunteer |
| Histology (.tif) | TBD | 📣 Needs volunteer |
| PET DICOM | TBD | 📣 Needs volunteer |
| MRI DICOM | TBD | 📣 Needs volunteer |
| SEM/TEM | TBD | ❓ Pending inclusion decision |

---

## 4. Per-Modality Show-and-Tell

For each confirmed data type, we need a short walkthrough covering:

### 4.1 Acquisition Workflow
- Where data is acquired (which computer/room)
- How data is named at acquisition
- How data is transferred from instrument

### 4.2 File Structure
- What files are produced per acquisition
- Which file is the "primary" data file
- What supporting files exist (metadata, logs, previews)

### 4.3 Embedded Metadata
- What metadata is embedded in the file
- How to extract it (if tools exist)
- What must be captured separately

### 4.4 Analysis Workflow
- What tools are used
- Typical processing steps
- What outputs are produced

---

## 5. Format Reference

### 5.1 File Formats

| Format | Extension | Source | Metadata | Notes |
|--------|-----------|--------|----------|-------|
| Carl Zeiss Image | .czi | Zeiss microscopes | Rich | Native format; preserves all metadata |
| TIFF | .tif, .tiff | Various | Variable | Common export; metadata depends on source |
| OME-TIFF | .ome.tif | Various/export | Rich | Open standard; embedded OME-XML |
| DICOM | .dcm, (folder) | Medical imaging | Rich | Standard for medical images |
| JPEG | .jpg, .jpeg | Various | Minimal | Lossy; avoid for quantitative work |
| PNG | .png | Various | Minimal | Lossless; limited metadata |
| Gatan DM | .dm3, .dm4 | Gatan TEM | Rich | Proprietary TEM format |

### 5.2 Format Handling

| Format | Action at Deposit | Conversion Needed? |
|--------|-------------------|-------------------|
| .czi | Deposit as-is | No |
| .tif (native) | Deposit as-is | No |
| .ome.tif | Deposit as-is | No |
| DICOM | Deposit folder as single unit | No |
| .jpg (primary) | ⚠️ Discourage | Convert to TIFF if possible |
| Proprietary | Deposit native + OME-TIFF export | Recommended |

---

## 6. Instrument Metadata Audit

> **⚠️ GAP:** Need to audit each instrument for embedded metadata.

### 6.1 Template

| Field | Zeiss WSI | Histology | DICOM | SEM | TEM |
|-------|-----------|-----------|-------|-----|-----|
| Acquisition date/time | ✅ | 🔶 | ✅ | ? | ? |
| Objective/magnification | ✅ | 🔶 | N/A | ? | ? |
| Pixel size | ✅ | 🔶 | ✅ | ? | ? |
| Exposure | ✅ | 🔶 | ✅ | ? | ? |
| Sample ID | ❌ | ❌ | 🔶 | ? | ? |
| Operator | ❌ | ❌ | 🔶 | ? | ? |

**Legend:** ✅ Embedded | 🔶 Sometimes | ❌ Not embedded | ? Unknown

### 6.2 Action Items

- [ ] Examine sample .czi files for Zeiss metadata
- [ ] Examine sample histology files for metadata variability
- [ ] Examine sample DICOM for relevant fields
- [ ] If SEM/TEM included: Examine sample EM files

---

## 7. Related Documents

- [03_RAW_STORAGE](03_RAW_STORAGE.md) — Storage structure by instrument
- [08_METADATA](08_METADATA.md) — Extended metadata specification
- [10_TOOLS](10_TOOLS.md) — Format-specific processing scripts

---

## Open Questions

| ID | Question | Owner | Status |
|----|----------|-------|--------|
| MOD-01 | Include SEM/TEM in pilot? | PI | ❓ Awaiting decision |
| MOD-02 | Complete data type sign-up sheet | Users | ⚠️ Incomplete |
| MOD-03 | Conduct show-and-tell for each type | Data Mgmt Lead + Users | 📋 Planned |
| MOD-04 | Complete metadata audit per format | Data Mgmt Lead | ⚠️ Incomplete |
