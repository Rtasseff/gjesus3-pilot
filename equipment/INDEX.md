# Equipment Index

This folder contains reference documentation for all imaging equipment whose data is in scope for the gjesus3 archival system.

---

## How "Raw" Data Differs by Source

There are two categories of equipment, and the meaning of "raw" data on gjesus3 differs between them:

**Microscopes (lab-operated):** The actual instrument output (native image files) is deposited directly to gjesus3. This is the true raw acquisition data.

**Institutional imaging platforms (MRI, Nuclear Imaging):** The platforms operate the instruments and manage their own long-term storage of true acquisition data (e.g., PET listmode files, raw k-space MRI data). This truly raw data is usually not useful to end-user researchers. What the platforms provide to researchers are **reconstructed images**, likely in DICOM format (format to be confirmed). On gjesus3, these reconstructed images are treated as our "raw" data — the authoritative starting point for the MFB group's analysis and archiving.

---

## Equipment Summary

| # | Equipment | Type | Category | Our "Raw" Data | Primary Format | Source Document |
|---|-----------|------|----------|----------------|----------------|-----------------|
| 1 | Zeiss Axiocam 7 (WSI) | Whole-slide imager | Microscope | Instrument output | .czi | [Technical Review (docx)](Whole%20Slide%20Imaging%20with%20Zeiss%20Axiocam%207_%20Technical%20Review.docx) |
| 2 | Zeiss Axio Observer (Cell Observer) | Inverted epifluorescence microscope | Microscope | Instrument output | .czi, .tif | [Description (pdf)](cell_observer_description_2.pdf) |
| 3 | Zeiss LSM 900 (Confocal) | Confocal microscope | Microscope | Instrument output | .czi | [Description (pdf)](confocal_microscopelsm900description.pdf) |
| 4a | Bruker BioSpec 11.7T MRI | Preclinical MRI scanner | Platform instrument | Reconstructed images (from platform) | DICOM (TBC) | [Platform description (md)](mri_platform_discription.md) |
| 4b | Bruker BioSpec 7T MRI | Preclinical MRI scanner | Platform instrument | Reconstructed images (from platform) | DICOM (TBC) | [Platform description (md)](mri_platform_discription.md) |
| 5a | Molecubes PET/SPECT/CT | Modular trimodal nuclear imaging | Platform instrument | Reconstructed images (from platform) | DICOM (TBC) | [Platform description (md)](nuclearImaging_platform_description.md) |
| 5b | MILabs VECTor PET/SPECT/CT/OI | Integrated multimodal nuclear imaging | Platform instrument | Reconstructed images (from platform) | DICOM, NIfTI | [Platform description (md)](nuclearImaging_platform_description.md) |

---

## Microscopes (Direct Raw Acquisition)

### 1. Zeiss Axiocam 7 — Whole-Slide Imaging

- **Full name:** Zeiss Axiocam 7 series (705 color / 712 mono) on motorized stage
- **Location:** MFB Lab
- **Software:** ZEN Blue (Slidescan module)
- **Output format:** .czi (Carl Zeiss Image) — pyramidal, multi-resolution, rich embedded metadata
- **Typical file size:** 0.5-2 GB per slide (can be larger)
- **Imaging modes:** Brightfield WSI, fluorescence WSI, tile-stitching
- **Embedded metadata:** Extensive (objective, camera settings, stage coordinates, acquisition time, calibration)
- **Not embedded:** Sample information, experimental context
- **Reference doc:** Detailed technical review covering formats, software ecosystem, OMERO compatibility, FAIR considerations

### 2. Zeiss Axio Observer — Cell Observer (Inverted Microscope)

- **Full name:** Cell Observer (Axio Observer, Zeiss)
- **Location:** Room 2.66
- **Software:** ZEN Blue v2.3
- **Cameras:** Axiocam MRR3 (B&W), Axiocam 305 (color)
- **Output format:** .czi (primary), possibly .tif exports
- **Illumination:** Metal halide arc lamp + Colibri LED module (365, 470, 530, 590 nm)
- **Imaging modes:** Epifluorescence, brightfield, phase contrast, DIC; time lapse, z-stack, large-area tiling
- **Objectives:** 5x to 100x (air and oil immersion)
- **Embedded metadata:** Expected to be similar to other ZEN-based Zeiss instruments

### 3. Zeiss LSM 900 — Confocal Microscope

- **Full name:** Confocal Microscope 900 (Zeiss LSM 900)
- **Location:** Room 2.66
- **Platform:** Optical Spectroscopy and Microscopy Platform (Irantzu Llarena)
- **Software:** ZEN Blue (full license, including LSMPlus, Tile & Position, linear unmixing, colocalization, 3D Viewer)
- **Excitation lasers:** 405, 488, 561, 640 nm
- **Detectors:** 2 PMTs + 1 GaAsP (fluorescence) + ESID (brightfield)
- **Output format:** .czi
- **Scanner resolution:** Up to 6144x6144 pixels; max 512x512 at 8 fps
- **Imaging modes:** Confocal fluorescence (3 simultaneous channels), z-stack, time series, tile, FRAP, FRET
- **Objectives:** 2.5x to 63x (air, water multi-immersion, oil)
- **Embedded metadata:** Expected to be extensive (ZEN-based)

---

## Institutional Imaging Platforms (Reconstructed Data)

### 4. MRI Platform — Bruker BioSpec 11.7T and 7T

The MRI platform has **two** preclinical MRI systems:

**Bruker BioSpec 11.7T:**
- **Field strength:** 11.7 Tesla
- **Gradient:** 9 cm high-performance gradient, up to 750 mT/m
- **Transmit/receive:** 4 broadband transmit channels, up to 8 parallel receive channels
- **Multinuclear:** 1H, 13C, 19F, 31P detection
- **Applications:** Ultra-high resolution preclinical imaging — physiological, cardiovascular, neurological, metabolic research

**Bruker BioSpec 7T:**
- **Field strength:** 7 Tesla, 30 cm bore (70/30 USR)
- **Gradients:** Interchangeable — 20 cm (200 mT/m) and 12 cm (400 mT/m) gradient sets
- **Transmit/receive:** 2 broadband transmit channels, 4 parallel receive channels
- **Applications:** Neuroimaging, physiology, pharmacology, molecular biology

**Both systems:**
- **Techniques:** High-resolution anatomical imaging (2D/3D), ultrafast imaging (EPI, spiral), parallel imaging (GRAPPA, mSENSE), volume selective spectroscopy and spectroscopic imaging (1H, 13C, 19F, 31P)
- **Our "raw" data:** Reconstructed images provided to researchers by the platform
- **Expected format:** DICOM (to be confirmed)
- **True raw data:** Managed and archived by the MRI platform (e.g., k-space data, raw FIDs)

### 5. Nuclear Imaging Platform — PET/SPECT/CT/OI

The Nuclear Imaging platform has **two** multimodal imaging systems plus an autoradiography system:

**Molecubes PET/SPECT/CT (trimodal, modular):**
- **Modules:** Three independent, combinable units:
  - **gamma-CUBE (SPECT):** High-resolution/sensitivity SPECT; static full-body imaging of rats and mice
  - **beta-CUBE (PET):** High-resolution PET; 13 cm axial FOV; full-body dynamic acquisitions; cardiac gating; up to 4 mice simultaneously
  - **X-CUBE (CT):** High-performance CT; 50 µm resolution; respiratory gating
- **Reconstruction:** Iterative 3DOSEM algorithm with scatter correction and CT-based attenuation correction

**MILabs VECTor PET/SPECT/CT/OI (integrated multimodal):**
- **Capabilities:** Fully integrated PET, SPECT, CT, and 2D Optical Imaging in one system
- **Resolution:** Submillimeter PET and SPECT
- **Unique features:** True multi-isotope imaging including simultaneous PET/SPECT and PET/PET (e.g., 18F and 89Zr); cardiac and respiratory dual gating across PET, SPECT, CT
- **Reconstruction:** Advanced algorithms (MLEM, POSEM, SROSEM); dedicated GPU-based reconstruction server (36 TB)
- **Export formats:** DICOM and NIfTI

**Autoradiography system:** High-resolution endpoint nuclear imaging.

**Workstations:** 3 dedicated workstations with PMOD and Imalytics licenses

**Both systems:**
- **Our "raw" data:** Reconstructed images provided to researchers by the platform
- **Expected format:** DICOM and/or NIfTI (MILabs confirms both; Molecubes format TBC)
- **True raw data:** Managed and archived by the Nuclear Imaging platform (e.g., PET listmode files, raw sinograms)

---

## Open Questions

| ID | Question | Status |
|----|----------|--------|
| EQUIP-01 | Confirm output format for reconstructed images from MRI platform (DICOM assumed) | ⚠️ Needs confirmation |
| EQUIP-02 | Confirm output format for Molecubes system (DICOM assumed but not stated in description) | ⚠️ Needs confirmation |
| EQUIP-03a | MILabs VECTor exports both DICOM and NIfTI — which does the platform provide to researchers, or both? Do we store both? | ⚠️ Needs platform input |
| EQUIP-03b | If NIfTI is in scope, it needs to be added to format handling and registry specifications | 🔶 Depends on EQUIP-03a |
| EQUIP-04 | What specific reconstructed outputs does each platform provide? (e.g., which reconstruction methods, series types) | ⚠️ Needs platform input |
| EQUIP-05 | Do the Cell Observer and LSM 900 produce any multi-file outputs that need special handling? | ⚠️ Needs investigation |
| EQUIP-06 | Confirm embedded metadata details for Cell Observer and LSM 900 .czi files | 📋 Planned |
