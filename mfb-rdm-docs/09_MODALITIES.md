# 09 — Supported Modalities

**Parent:** [Documentation Index](00_INDEX.md)  
**Status:** ⚠️ Gaps identified  
**Last Updated:** 2026-05-06

---

## Purpose

This document describes the imaging modalities (data types and instruments) supported by the system, including file formats, embedded metadata, and typical workflows.

---

## 1. Confirmed Modalities

> For detailed equipment specifications, see [equipment/INDEX.md](../equipment/INDEX.md).

### Two Categories of "Raw" Data

The instruments in scope fall into two categories, and the meaning of "raw" data on gjesus3 differs:

| Category | What goes to gjesus3 | Example |
|----------|----------------------|---------|
| **Microscopes** (lab-operated) | Actual instrument output — the native image files | .czi files from Zeiss microscopes |
| **Platform instruments** (MRI, Nuclear Imaging) | Reconstructed images provided to researchers by the platform | DICOM (stored as compressed archives on gjesus3), possibly NIfTI |

The platforms manage and archive their own true raw acquisition data (e.g., PET listmode files, raw k-space MRI data). That data is usually not useful to researchers. Our "raw" for platform data is the reconstructed images.

---

### 1.1 Whole-Slide Imaging — Zeiss Axio Scan 7

| Attribute | Value |
|-----------|-------|
| **Instrument** | Zeiss Axio Scan 7 (with Axiocam 705 color / 712 mono cameras) on motorized stage |
| **Category** | Microscope (direct raw) |
| **Code** | `ZWSI` |
| **Location** | MFB Lab |
| **Software** | ZEN Blue (Slidescan module) |
| **Primary format** | .czi (Carl Zeiss Image) — pyramidal, multi-resolution |
| **Typical size** | 0.5-10 GB per slide |
| **Imaging modes** | Brightfield WSI, fluorescence WSI, tile-stitching |
| **Embedded metadata** | Extensive (objective, camera settings, stage coordinates, acquisition time, calibration) |
| **Not embedded** | Sample information, experimental context |
| **Analysis tools** | ZEN, QuPath, ImageJ/FIJI, Bio-Formats compatible tools |
| **Status** | ✅ Confirmed for pilot, end-to-end ingest tested 2026-05-06 |

#### Auto-discovered fields (`discovered.czi_*`)

These are surfaced from each `.czi` file's embedded XML at ingest time and may be referenced from the YAML `registry:` block (e.g. `acquisition_datetime: discovered.czi_acquisition_datetime`). Curation lives in `tools/ingest/czi_metadata.py:EXPOSED_FIELDS` — that file is the single source of truth; this table is its mirror. Any field marked here applies equally to `CELL` and `LSM9` (§1.2, §1.3) since they share the `.czi` format and ZEN ecosystem.

| Field | Description | XML source |
|-------|-------------|------------|
| `czi_acquisition_datetime` | Full ISO timestamp of acquisition (preferred over folder date) | `Information.Image.AcquisitionDateAndTime` |
| `czi_microscope_name` | Microscope `@Name` (e.g. `"Axioscan 7"`) | `Information.Instrument.Microscopes.Microscope @Name` |
| `czi_microscope_type` | Geometry (e.g. `"Upright"`, `"Inverted"`) | `Information.Instrument.Microscopes.Microscope.Type` |
| `czi_objective_name` | First objective's `@Name` (e.g. `"Plan-Apochromat 20x/0.8 M27"`) | `Information.Instrument.Objectives.Objective[0] @Name` |
| `czi_objective_mag` | First objective's nominal magnification, no units | `…NominalMagnification` |
| `czi_objective_na` | First objective's numerical aperture | `…LensNA` |
| `czi_pixel_size_x_um` | Physical pixel size along X, in µm | `Scaling.Items.Distance[Id=X].Value` (m → µm) |
| `czi_pixel_size_y_um` | Physical pixel size along Y, in µm | `Scaling.Items.Distance[Id=Y].Value` |
| `czi_size_x` | Image width in pixels | `Information.Image.SizeX` |
| `czi_size_y` | Image height in pixels | `Information.Image.SizeY` |
| `czi_size_c` | Number of channels | `Information.Image.SizeC` |
| `czi_size_z` | Number of Z slices (empty for 2D scans) | `Information.Image.SizeZ` |
| `czi_size_t` | Number of timepoints (empty for single-shot) | `Information.Image.SizeT` |
| `czi_scene_count` | Number of scenes (regions) on the slide | `Information.Image.SizeS` |
| `czi_tile_count` | Number of mosaic tiles (high for WSI) | `Information.Image.SizeM` |
| `czi_pixel_type` | Pixel encoding (e.g. `"Bgr24"`, `"Gray16"`) | `Information.Image.PixelType` |
| `czi_compression` | Original compression (often `"JpegXr"` for WSI) | `Information.Image.OriginalCompressionMethod` |
| `czi_acquisition_mode` | First channel mode (e.g. `"WideField"`) | `…Channel[0].AcquisitionMode` |
| `czi_contrast_method` | First channel contrast (e.g. `"Brightfield"`) | `…Channel[0].ContrastMethod` |
| `czi_user` | ZEN account that captured the image (often a generic instrument account) | `Information.Document.UserName` |
| `czi_zen_version` | ZEN software version that produced the file | `Information.Application.Version` |

The richer structured form of all the above plus channels/detectors/objective lists/document info is preserved in the sidecar's `microscopy:` block — see [08_METADATA §4.3](08_METADATA.md). Library/route choice (`czifile`) and what's deferred (pylibCZIrw, Bio-Formats, OMERO export) is in [10_TOOLS §2.1.3](10_TOOLS.md).

### 1.2 Inverted Microscopy — Zeiss Axio Observer (Cell Observer)

| Attribute | Value |
|-----------|-------|
| **Instrument** | Cell Observer (Axio Observer, Zeiss) |
| **Category** | Microscope (direct raw) |
| **Code** | `CELL` |
| **Location** | Room 2.66 |
| **Software** | ZEN Blue v2.3 |
| **Cameras** | Axiocam MRR3 (B&W), Axiocam 305 (color) |
| **Primary format** | .czi (primary), possibly .tif exports |
| **Typical size** | Variable (single field to tiled large-area) |
| **Illumination** | Metal halide arc lamp + Colibri LED (365, 470, 530, 590 nm) |
| **Imaging modes** | Epifluorescence, brightfield, phase contrast, DIC; time lapse, z-stack, large-area tiling |
| **Objectives** | 5x-100x (air and oil immersion) |
| **Embedded metadata** | Expected extensive (ZEN-based .czi) |
| **Not embedded** | Sample information, experimental context |
| **Analysis tools** | ZEN, ImageJ/FIJI, QuPath |
| **Status** | ✅ Confirmed for pilot |

### 1.3 Confocal Microscopy — Zeiss LSM 900

| Attribute | Value |
|-----------|-------|
| **Instrument** | Confocal Microscope 900 (Zeiss LSM 900) |
| **Category** | Microscope (direct raw) |
| **Code** | `LSM9` |
| **Location** | Room 2.66 |
| **Platform** | Optical Spectroscopy and Microscopy Platform (Irantzu Llarena) |
| **Software** | ZEN Blue (full license: LSMPlus, Tile & Position, linear unmixing, colocalization, 3D Viewer) |
| **Excitation** | 405, 488, 561, 640 nm lasers |
| **Detectors** | 2 PMTs + 1 GaAsP (fluorescence) + ESID (brightfield) |
| **Primary format** | .czi |
| **Typical size** | Variable (single images to large tile/z-stack datasets) |
| **Scanner resolution** | Up to 6144x6144 px; max 512x512 at 8 fps |
| **Imaging modes** | Confocal fluorescence (3 simultaneous channels), z-stack, time series, tile, FRAP, FRET |
| **Objectives** | 2.5x-63x (air, water multi-immersion, oil) |
| **Embedded metadata** | Expected extensive (ZEN-based .czi) |
| **Not embedded** | Sample information, experimental context |
| **Analysis tools** | ZEN, ImageJ/FIJI, QuPath, Napari |
| **Status** | ✅ Confirmed for pilot |

### 1.4 Reconstructed Biomedical Imaging — MRI Platform

| Attribute | Value |
|-----------|-------|
| **Instruments** | Bruker BioSpec 11.7T (9 cm gradient, 750 mT/m) and Bruker BioSpec 7T (30 cm bore, 200-400 mT/m) |
| **Category** | Platform instrument (reconstructed data) |
| **Code** | `MRI` |
| **Capabilities** | High-resolution anatomical (2D/3D), ultrafast (EPI, spiral), parallel imaging (GRAPPA, mSENSE), multinuclear spectroscopy (1H, 13C, 19F, 31P) |
| **Source format** | DICOM (.dcm directories) — provided by MRI platform as expanded directories |
| **Storage on gjesus3** | Compressed archive (.zip or .tar.gz) — DICOM directories are archived before deposit |
| **Typical size** | 100 MB - 10 GB per series |
| **Embedded metadata** | Extensive (DICOM standard) |
| **Not embedded** | Study context beyond DICOM headers |
| **Analysis tools** | 3D Slicer, ITK-SNAP, MATLAB, PMOD |
| **Raw data responsibility** | MRI platform archives true raw data (k-space, FIDs) |
| **Status** | ✅ Confirmed for pilot |

> **📣 INPUT NEEDED:** Do the two MRI systems need separate instrument codes (e.g., `MRI7` and `MRI11`), or is a single `MRI` code sufficient?

### 1.5 Reconstructed Biomedical Imaging — Nuclear Imaging Platform

| Attribute | Value |
|-----------|-------|
| **System 1** | Molecubes PET/SPECT/CT — modular trimodal (gamma-CUBE SPECT, beta-CUBE PET with 13 cm axial FOV, X-CUBE CT at 50 µm); 3DOSEM reconstruction |
| **System 2** | MILabs VECTor PET/SPECT/CT/OI — integrated multimodal; submillimeter PET/SPECT; multi-isotope (e.g., 18F + 89Zr simultaneous); MLEM/POSEM/SROSEM reconstruction; GPU server (36 TB) |
| **Other** | Autoradiography system (endpoint imaging) |
| **Category** | Platform instrument (reconstructed data) |
| **Codes** | `PET`, `SPECT`, `CT` (individual codes per modality) |
| **Workstations** | 3 dedicated workstations with PMOD and Imalytics |
| **Primary format** | DICOM and NIfTI (MILabs confirms both exports; Molecubes **format TBC**) |
| **Storage on gjesus3** | DICOM stored as compressed archive (.zip or .tar.gz); NIfTI files stored as-is (single files, no archive needed) |
| **Typical size** | 100 MB - 10 GB per series |
| **Embedded metadata** | Extensive (DICOM standard); NIfTI has limited header metadata |
| **Not embedded** | Study context beyond headers |
| **Analysis tools** | PMOD, Imalytics, 3D Slicer, ITK-SNAP, MATLAB |
| **Raw data responsibility** | Nuclear Imaging platform archives true raw data (listmode, sinograms) |
| **Status** | ✅ Confirmed for pilot |

> **⚠️ GAP:** MILabs VECTor exports both DICOM and NIfTI. Need to confirm which format(s) the platform provides to researchers, and whether NIfTI should be an accepted format on gjesus3.

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

| Data Type | Instrument | Volunteer | Status |
|-----------|------------|-----------|--------|
| Whole-slide .czi | Zeiss Axio Scan 7 | TBD | 📣 Needs volunteer |
| Inverted microscopy .czi | Cell Observer (Axio Observer) | TBD | 📣 Needs volunteer |
| Confocal .czi | Zeiss LSM 900 | TBD | 📣 Needs volunteer |
| MRI DICOM (reconstructed) | Bruker 11.7T | TBD | 📣 Needs volunteer |
| PET DICOM (reconstructed) | Nuclear Imaging platform | TBD | 📣 Needs volunteer |
| SPECT DICOM (reconstructed) | Nuclear Imaging platform | TBD | 📣 Needs volunteer |
| CT DICOM (reconstructed) | Nuclear Imaging platform | TBD | 📣 Needs volunteer |
| SEM/TEM | EM platform | TBD | ❓ Pending inclusion decision |

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
| DICOM | .dcm (stored as .zip/.tar.gz on gjesus3) | Medical imaging | Rich | Standard for medical images |
| NIfTI | .nii, .nii.gz | Medical imaging / analysis | Limited (header) | Common neuroimaging format; may come from Nuclear Imaging platform |
| JPEG | .jpg, .jpeg | Various | Minimal | Lossy; avoid for quantitative work |
| PNG | .png | Various | Minimal | Lossless; limited metadata |
| Gatan DM | .dm3, .dm4 | Gatan TEM | Rich | Proprietary TEM format |

### 5.2 Format Handling

| Format | Action at Deposit | Conversion Needed? |
|--------|-------------------|-------------------|
| .czi | Deposit as-is | No |
| .tif (native) | Deposit as-is | No |
| .ome.tif | Deposit as-is | No |
| DICOM | Compress to archive (.zip/.tar.gz) before deposit | No (compressed, not converted) |
| .jpg (primary) | ⚠️ Discourage | Convert to TIFF if possible |
| Proprietary | Deposit native + OME-TIFF export | Recommended |

---

## 6. Instrument Metadata Audit

> **⚠️ GAP:** Need to audit each instrument for embedded metadata.

### 6.1 Template

| Field | Axio Scan 7 WSI (.czi) | Cell Observer (.czi) | LSM 900 (.czi) | DICOM (recon) | SEM/TEM |
|-------|----------------------|----------------------|-----------------|---------------|---------|
| Acquisition date/time | ✅ | ✅ (expected) | ✅ (expected) | ✅ | ? |
| Objective/magnification | ✅ | ✅ (expected) | ✅ (expected) | N/A | ? |
| Pixel size | ✅ | ✅ (expected) | ✅ (expected) | ✅ | ? |
| Exposure | ✅ | ✅ (expected) | ✅ (expected) | ✅ | ? |
| Channels/lasers | ✅ | ✅ (expected) | ✅ (expected) | N/A | ? |
| Sample ID | ❌ | ❌ | ❌ | 🔶 | ? |
| Operator | ❌ | ❌ | ❌ | 🔶 | ? |

**Legend:** ✅ Embedded | 🔶 Sometimes | ❌ Not embedded | ? Unknown

> **Note:** All three Zeiss microscopes use ZEN Blue and save to .czi, so their embedded metadata is expected to be similar. However, this should be confirmed with sample files from each instrument.

### 6.2 Action Items

- [ ] Examine sample .czi files from Axio Scan 7 (WSI) for metadata fields
- [ ] Examine sample .czi files from Cell Observer for metadata fields
- [ ] Examine sample .czi files from LSM 900 for metadata fields
- [ ] Examine sample DICOM from MRI platform for relevant fields
- [ ] Examine sample DICOM from Nuclear Imaging platform for relevant fields
- [ ] Confirm DICOM as the output format from both platforms
- [ ] If SEM/TEM included: Examine sample EM files

---

## 7. Related Documents

- [equipment/INDEX.md](../equipment/INDEX.md) — Detailed equipment specifications and reference documents
- [03_RAW_STORAGE](03_RAW_STORAGE.md) — Storage structure by data ecosystem
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
| MOD-05 | Confirm DICOM as output format from MRI and Nuclear Imaging platforms | Data Mgmt Lead + Platforms | ⚠️ Needs confirmation |
| ~~MOD-06~~ | ~~Assign instrument codes for Cell Observer and LSM 900~~ | — | ✅ Resolved: `CELL` and `LSM9` |
| MOD-07 | Confirm Cell Observer and LSM 900 .czi metadata is similar to WSI .czi | Data Mgmt Lead | 📋 Planned |
