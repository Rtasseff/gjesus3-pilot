# Equipment Index

**Last Updated:** 2026-06-26

This folder contains reference documentation for all imaging equipment whose data is in scope for the gjesus3 archival system. It is the map between the abstract system specs in [`mfb-rdm-docs/`](../mfb-rdm-docs/00_INDEX.md) and the concrete reality of each instrument: what its "raw" data looks like, how operators name and stage it, and how it reaches gjesus3.

> **Researchers:** to *find and use* your data (rather than understand the instruments), start at [`RESEARCHER_GUIDE.md`](../RESEARCHER_GUIDE.md). The one thing on this page that matters most to you is your instrument's **naming convention** — see the [naming quick-reference](#naming-convention-quick-reference) below.
>
> **Where the source/historical data lives** for each instrument (the archives we ingest *from*) is catalogued separately in [`historical_data_archives.md`](./historical_data_archives.md).

---

## How "Raw" Data Differs by Source

There are two categories of equipment, and the meaning of "raw" data on gjesus3 differs between them:

**Microscopes (lab-operated):** The actual instrument output (native image files) is deposited directly to gjesus3. This is the true raw acquisition data.

**Institutional imaging platforms (MRI, Nuclear Imaging):** The platforms operate the instruments and manage their own long-term storage of true acquisition data (e.g., PET listmode files, raw k-space MRI data). This truly raw data is usually not useful to end-user researchers. What the platforms provide to researchers are **reconstructed images** — internal MRI as Bruker ParaVision exam folders (with JCAMP-DX aux files + per-frame DICOM); Nuclear Imaging primarily as DICOM (possibly NIfTI from MILabs VECTor).

**On-disk shape on gjesus3 varies per ecosystem** (see [03_RAW_STORAGE §4](../mfb-rdm-docs/03_RAW_STORAGE.md)). `/raw/` is organised into **data-family ecosystems** — currently two are deployed plus one reserved:
- **`MICROSCOPY`** — the three Zeiss `.czi`-producing microscopes (AxioScan 7, Cell Observer, LSM 900). Primary entity = the single instrument file.
- **`DICOM`** — internal MRI and (legacy) collaborator DICOM, plus future Nuclear Imaging. Internal MRI (since round 6, 2026-05-22) is **folder-as-primary** (no zip); the acquisition folder contains `acquisition_aux/` + `reconstructions/pdata_<idx>/` (see [`mri-platform/internal_mri_data_handling_workflow_notes.md`](./mri-platform/internal_mri_data_handling_workflow_notes.md) "Systematic naming convention"). Legacy collaborator DICOM (rounds 1-2) is a compressed archive (.zip / .tar.gz), not re-shaped. Internal Nuclear Imaging convention is documented in [`nuclear-imaging/internal_ni_data_handling_workflow_notes.md`](./nuclear-imaging/internal_ni_data_handling_workflow_notes.md); on-disk shape will be finalised when that ingest round begins.
- **`EM`** — **reserved, not deployed.** The electron-microscopy ecosystem is allocated in the `/raw/` layout for future use; no instrument is onboarded and the folder is not populated. See [03_RAW_STORAGE §4](../mfb-rdm-docs/03_RAW_STORAGE.md).

The instrument's identity is recorded in the **ACQ-ID** and the registry (instrument code column), not in the ecosystem folder name (RAW-05) — so all three microscopes share `MICROSCOPY` and are told apart by code (`ZWSI` / `CELL` / `LSM9`).

These reconstructed images are treated as gjesus3's "raw" data — the authoritative starting point for the MFB group's research-facing analysis and archiving. The reframe in [13_GJESUS3_ROLE](../mfb-rdm-docs/13_GJESUS3_ROLE.md) elaborates on the two-tier model: gjesus3 as research-facing working layer, platforms as deep-time raw archive.

---

## Metadata architecture (two levels)

Every acquisition carries metadata at two levels — keep the distinction clear when reading any per-instrument note:

- **Acquisition-level — `/raw/<ACQ-ID>/metadata.json` — ✅ LIVE + immutable.** A `metadata.json` sidecar sits next to each acquisition in `/raw/`. It holds what the operator supplied plus fields auto-extracted at ingest (including the 21 `czi_*` fields pulled from each Zeiss `.czi`), and — for animal-derived data — `subject` / `condition` / `anatomy` blocks. It is written once and never edited in place. The enrichment writer that fills `subject`/`condition`/`anatomy` is **non-blocking**: an unknown becomes an explicit sentinel plus a WARN, never an ingest failure. Spec: [08_METADATA](../mfb-rdm-docs/08_METADATA.md).
- **Study-level — `/projects/<proj>/metadata/` — 🕗 PLANNED/DEFERRED (Phase 4).** A richer, *study-level* metadata area inside each project (study aim, biosample sheets, per-acquisition overrides) is designed but **not deployed** — it exists on none of the live projects today. Until it lands, study context that isn't captured at the instrument is kept in researcher notes and flagged to the Data Management Lead. Status/plan: [tasks/BACKLOG.md](../tasks/BACKLOG.md); design: [05_PROJECTS §3](../mfb-rdm-docs/05_PROJECTS.md). Several per-instrument notes below mention this `/projects/<proj>/metadata/<acq_id>.json` override path — read those mentions as **planned**, not deployed.

The split (immutable acquisition facts in `/raw/`, mutable study context in `/projects/`) and its close-out implications are decided in [08_METADATA §1](../mfb-rdm-docs/08_METADATA.md).

---

## Naming-convention quick-reference

The single highest-leverage thing a researcher or operator controls is the **file/folder name at the instrument** — a good name lets the ingest auto-extract sample, subject, and project context; a poor one means that information has to be re-entered by hand. Each instrument's authoritative convention (and the `discovered.*` fields its per-instrument template can therefore expose) lives in its workflow note:

| Instrument | Code | Convention anchor | Naming-convention note | Per-instrument template |
|---|---|---|---|---|
| Axio Scan 7 (WSI) | `ZWSI` | Filename: `<group>_<operator>_<project>_<sample>_<stain>_<mag>.czi` in a `<YYYYMMDD>` day folder | [`axioscan7-wsi/…workflow_notes.md`](./axioscan7-wsi/axioscan7_data_handling_workflow_notes.md) | [`axioscan7.yaml`](../tools/templates/instruments/axioscan7.yaml) |
| Cell Observer | `CELL` | Folder path carries most context (`<researcher>/<cell_line>/<experiment>/`); lighter filename | [`cell-observer/…workflow_notes.md`](./cell-observer/cell_observer_data_handling_workflow_notes.md) | [`cell_observer_cells.yaml`](../tools/templates/instruments/cell_observer_cells.yaml) |
| LSM 900 (confocal) | `LSM9` | Batch folder `<researcher>_<experiment>_<cell_line>`; `.czi`-embedded metadata is the canonical truth | [`lsm900/…workflow_notes.md`](./lsm900/lsm900_data_handling_workflow_notes.md) | [`lsm900.yaml`](../tools/templates/instruments/lsm900.yaml) |
| Bruker MRI (ParaVision) | `MRI` | `<project_folder>/<protocol_number>/pdata/<reconstruction>` | [`mri-platform/internal_mri_…workflow_notes.md`](./mri-platform/internal_mri_data_handling_workflow_notes.md) | [`mri_bruker.yaml`](../tools/templates/instruments/mri_bruker.yaml) |
| Nuclear Imaging (PET/SPECT/CT) | `PET` `SPECT` `CT` | `<YYYYMMDDhhmmss>_<MODALITY>` folder anchor (live); archive layout for historical | [`nuclear-imaging/internal_ni_…workflow_notes.md`](./nuclear-imaging/internal_ni_data_handling_workflow_notes.md) | [`molecubes_ni.yaml`](../tools/templates/instruments/molecubes_ni.yaml) |

> Per-instrument templates are **operator reference cards** — each template's header comments list every `discovered.*` field auto-populated for that instrument. The workflow notes never invent `discovered.*` fields; they point at the template header.

---

## How data reaches gjesus3 (the ingest path)

All instruments follow the same shape, with the per-instrument template supplying the instrument-specific parse:

1. **Stage** the acquisition(s) — at the instrument's network/group-drive location, or copied to a staging area.
2. **Ingest** with `tools/ingest_raw.py` (the engine), driven by the matching per-instrument template under [`tools/templates/instruments/`](../tools/templates/instruments/) copied into a per-batch config. Microscopy and MRI operators can use the frozen GUI **`gjesus3_ingest.exe`** instead of the CLI (it has microscopy + MRI pages). See [`tools/INGEST_CLI.md`](../tools/INGEST_CLI.md) and [`START_HERE.md`](../START_HERE.md).
3. The ingest deposits the acquisition into the right ecosystem under **`/raw/`** (microscopy → `/raw/MICROSCOPY/`, MRI/NI → `/raw/DICOM/`), writes the immutable `metadata.json` sidecar, and appends one row per acquisition to **`registries/registry_raw.csv`** (the live registry — 28 columns; the packed `subject_ids` column is auto-populated for animal-derived data).
4. The acquisition is **hard-linked** into its project (`/projects/<proj>/raw_linked/`) — a hard link looks and opens like the real file but takes no extra space and never copies or moves the original. (Hard links are the linking method, DECIDED + APPLIED 2026-06-02; the older Windows `.lnk` shortcut method is retired. See [10_TOOLS §2.1.1](../mfb-rdm-docs/10_TOOLS.md).)
5. The **Finder** (`registries/index.html` — a self-contained searchable web page, plus a per-project `index.html` in each project folder) is auto-refreshed so the new acquisition is immediately searchable. See [`tools/FINDER.md`](../tools/FINDER.md).

---

## Equipment Summary

> For instrument codes used in the ACQ-ID and registry (e.g., `ZWSI`, `CELL`, `LSM9`, `MRI`, `PET`), see [09_MODALITIES](../mfb-rdm-docs/09_MODALITIES.md) and [03_RAW_STORAGE](../mfb-rdm-docs/03_RAW_STORAGE.md) Section 3.2.

| # | Equipment | Code | Type | Category | Our "Raw" Data | Primary Format | Reference Folder |
|---|-----------|------|------|----------|----------------|----------------|------------------|
| 1 | Zeiss Axio Scan 7 (WSI) | `ZWSI` | Whole-slide imager | Microscope | Instrument output | .czi | [`axioscan7-wsi/`](./axioscan7-wsi/) |
| 2 | Zeiss Axio Observer (Cell Observer) | `CELL` | Inverted epifluorescence microscope | Microscope | Instrument output | .czi, .tif | [`cell-observer/`](./cell-observer/) |
| 3 | Zeiss LSM 900 (Confocal) | `LSM9` | Confocal microscope | Microscope | Instrument output | .czi | [`lsm900/`](./lsm900/) |
| 4a | Bruker BioSpec 11.7T MRI | `MRI` | Preclinical MRI scanner | Platform instrument | Reconstructed images | DICOM | [`mri-platform/`](./mri-platform/) |
| 4b | Bruker BioSpec 7T MRI | `MRI` | Preclinical MRI scanner | Platform instrument | Reconstructed images | DICOM | [`mri-platform/`](./mri-platform/) |
| 5a | Molecubes PET/SPECT/CT | `PET`/`SPECT`/`CT` | Modular trimodal nuclear imaging | Platform instrument | Reconstructed images | DICOM (TBC) | [`nuclear-imaging/`](./nuclear-imaging/) |
| 5b | MILabs VECTor PET/SPECT/CT/OI | `PET`/`SPECT`/`CT` | Integrated multimodal nuclear imaging | Platform instrument | Reconstructed images | DICOM, NIfTI | [`nuclear-imaging/`](./nuclear-imaging/) |

Each reference folder is a free-form home for vendor specs, platform descriptions, user protocols, screenshots, and any other equipment-specific context. Drop new files in directly; no schema. The narrative sections below summarize what's currently in each folder.

---

## Microscopes (Direct Raw Acquisition)

### 1. Zeiss Axio Scan 7 — Whole-Slide Imaging

- **Full name:** Zeiss Axio Scan 7 (uses Axiocam 705 color / 712 mono cameras) on motorized stage
- **Location:** MFB Lab
- **Software:** ZEN Blue (Slidescan module)
- **Output format:** .czi (Carl Zeiss Image) — pyramidal, multi-resolution, rich embedded metadata
- **Typical file size:** 0.5-2 GB per slide (can be larger)
- **Imaging modes:** Brightfield WSI, fluorescence WSI, tile-stitching
- **Embedded metadata:** Extensive (objective, camera settings, stage coordinates, acquisition time, calibration)
- **Not embedded:** Sample information, experimental context
- **Reference materials** ([`axioscan7-wsi/`](./axioscan7-wsi/)):
  - Technical review (docx) — formats, software ecosystem, OMERO compatibility, FAIR considerations
  - Data handling workflow notes (md) — observed/documented use at biomaGUNE: Gopticals network storage, file naming convention, post-scan review and transfer practices, open questions

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
- **Reference materials** ([`cell-observer/`](./cell-observer/)):
  - Vendor description (pdf)
  - Data handling workflow notes (md) — operator walkthrough from rough transcript: local-PC acquisition + manual save to operator's group-drive folder; filename convention weaker than AxioScan; **directory structure carries most context**; two effective modes (animal/histology vs. cell-assay / live-cell / plate-based); confocal LSM 900 reportedly follows the same model. Open questions captured at end of file.

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
- **Reference materials** ([`lsm900/`](./lsm900/)):
  - Confocal microscope description (pdf)

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
- **Reference materials** ([`mri-platform/`](./mri-platform/)):
  - Platform description (md) — both BioSpec systems
  - Data access & ingestion strategy (md) — acquisition machine is NOT directly network-accessible; researchers FTP from acq machine to their workstations. Captures three architectural options (FTP-pull, on-machine push agent, hybrid), recommended pacing, the technical + forward-looking questions to ask the platform manager, and a working email draft. Round-6 (2026-05-22) executed Option A (FTP-from-workstation) using `tools/ftp_mirror.py`.
  - Data handling workflow notes (md) — full operator walkthrough + **the systematic naming convention** (parsable `<project_folder>/<protocol_number>/pdata/<reconstruction>` structure, `jrc` vs `jrc_` PI-initials ambiguity, `<short sample id>` shape, animal-id composition, MRI "project" vs NI funded-project-id terminology distinction). The reference for what `discovered.*` fields the MRI per-instrument template can expose.
  - **No-DICOM regeneration runbook** ([`mri-platform/mri_no_dicom_regeneration_runbook.md`](./mri-platform/mri_no_dicom_regeneration_runbook.md)) — **the procedure for the historical pull** when an exam arrives without DICOMs (researcher skipped Bruker's exporter): the ingest regenerates them from `2dseq`+JCAMP-DX via Dicomifier (in WSL), applies the two PV-7 image fixes, and deposits into `/raw/`. Setup → config flag → run → verify.

**Round 6 outcome (2026-05-22, historical quasi-production round — now superseded by the true-production system):** 97 ParaVision exam acquisitions ingested across PROJ-0003 (26) and PROJ-0004 (71) — cross-modality reuse with round-4 AxioScan project workspaces. No-zip folder-as-primary layout; ParaVision JCAMP-DX metadata in `metadata.json.mri`; project links named `MRI_<jrc_id>_<acq_date>_<exam>_<recon>` (hard links into `raw_linked/` — the current method; the older `.lnk` shortcut form is retired). Per-instrument template at [`../tools/templates/instruments/mri_bruker.yaml`](../tools/templates/instruments/mri_bruker.yaml).

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
- **Reference materials** ([`nuclear-imaging/`](./nuclear-imaging/)):
  - Platform description (md) — covers Molecubes, MILabs VECTor, and autoradiography
  - Internal NI data-handling workflow notes (md, future-round prep, 2026-05-22) — documents the archive structure on `\\cicmgsp02\gnuclear2$`, the `<archive name>.tgz → .tar → user/series/.../recon_<idx>/frame_<n>iter_30/*.dcm` nested layout, the **funded-project-id** semantics (distinct from MRI's animal-protocol short id), and the proposed `link_filename` pattern for the future NI ingest round. **Not implemented yet** — blocked on Platform Manager Unai answering one outstanding question on the naming convention.
  - **Live-machine data layout & sync rules** (md, 2026-06-11) — [`nuclear-imaging/live_machine_data_layout_and_sync_rules.md`](./nuclear-imaging/live_machine_data_layout_and_sync_rules.md). Analysis of a real recursive listing of the **Molecubes acquisition-box data dir** (3191 acquisitions), for the "researcher syncs their own folder to gjesus3" goal. Establishes the one reliable anchor (`<YYYYMMDDhhmmss>_<MODALITY>` folder), the variable-depth/noise/clock-skew messiness, and 10 concrete sync rules + a staged plan. The complement to the archive-mode notes (which defer this live path).

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
