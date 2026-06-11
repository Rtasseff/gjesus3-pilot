# 09 — Supported Modalities

**Parent:** [Documentation Index](00_INDEX.md)  
**Status:** ⚠️ Gaps identified
**Last Updated:** 2026-06-09 (**`condition:` now written for `sample_type = cells`** — Cell Observer + LSM 900; cell cultures are control-vs-case too — AND **`anatomy:` extended to `tissue`**: AxioScan sections now record the UBERON `region` the section was cut from (`is_whole_body` N/A), the same UBERON field as in-vivo scan region (corrects the earlier "anatomy is organism-only / `anatomical_entity` = REMBI 'Location within biosample'" — that REMBI field is spatial, §2.3 fixed). `subject:` stays tissue/organism-only. §4.5/§4.6 + the per-instrument rows below. Prior 2026-06-03: per-instrument subject + condition + anatomy metadata — `subject:` §4.4 / `condition:` §4.5 / `anatomy:` §4.6; **non-blocking model §4.7** — `is_control` + `is_whole_body` are highly-recommended tri-state, WARN-not-block; **the enrichment writer is now IMPLEMENTED** — Phase 3, fires at ingest for `sample_type ∈ {organism, tissue}`, see [10_TOOLS §2.1.6](10_TOOLS.md))

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
| **Platform instruments** (MRI, Nuclear Imaging) | Reconstructed images provided to researchers by the platform | DICOM and/or NIfTI; on-disk shape varies by ecosystem (see [03_RAW_STORAGE §4](03_RAW_STORAGE.md)). Internal MRI uses folder-as-primary (no zip) since round 6 (2026-05-20). Collaborator DICOM continues with the legacy zipped-archive shape. |

The platforms manage and archive their own true raw acquisition data (e.g., PET listmode files, raw k-space MRI data). gjesus3 is the **research-facing working layer** — see [13_GJESUS3_ROLE](13_GJESUS3_ROLE.md) for the two-tier framing. Our "raw" for platform data is the reconstructed images.

### Cross-modality requirement: subject + condition metadata for preclinical acquisitions

> **🔶 DRAFT 2026-05-29; extended 2026-06-02.** For any acquisition with `sample_type ∈ {organism, tissue}` (see [06_REGISTRIES §2.4](06_REGISTRIES.md)), `metadata.json` must include two new top-level blocks:
>
> **`subject:` block** — *who is this animal?* Identified by `facility_animal_id` = the facility canonical animal id `<animal_code>-AE-biomaGUNE-<NNNN>` **reused as the subject id** (Subject/Sample identity model, [06_REGISTRIES §2.3](06_REGISTRIES.md)). Required fields: `species` / `strain` / `sex` / `date_of_birth` → derived `age_at_acquisition` (ARRIVE-aligned, DECIDED). Optional `procedures` = a **structured `[{type,date}]` list** from the DB controlled vocab (not free text). Per-subject, fixed. Sourced from the **animal-facility DB** (explored 2026-06-02); ingest-time DB miss / no-credentials WARNs and queues for superuser recovery rather than failing (§4.4.6). Full schema in [08_METADATA §4.4](08_METADATA.md).
>
> **`condition:` block** — *what study state is this acquisition?* Highly recommended (**non-blocking**, §4.7): `is_control` (**tri-state** `true`/`false`/`null=unknown` — the healthy-vs-case flag, WARN if null) + free-text `disease_model` / `disease_state` (`disease_model` auto-seeds from DB `projects.name`). Per-acquisition, varies (same animal can be baseline + post-MI). Set once per batch/session. Full schema in [08_METADATA §4.5](08_METADATA.md).
>
> **`anatomy:` block** — *what body part?* For **in-vivo** scans: full-body-vs-ROI (`is_whole_body` **tri-state** `true`/`false`/`null=unknown`, WARN if null) + UBERON-coded `region`. For **ex-vivo tissue** (microscopy sections, extended 2026-06-09): the UBERON `region` the section was cut from (`is_whole_body` is N/A and stays null — same UBERON field, queryable with in-vivo region). Highly recommended (**non-blocking**, §4.7). Operator-entered (not in the animal-DB; DICOM `BodyPartExamined` empty upstream); optional non-authoritative auto-hint from MRI ProtocolName+FOV / NI bed-range. Full schema in [08_METADATA §4.6](08_METADATA.md).
>
> **Applicability per instrument in current scope** (all **non-blocking** — WARN, never refuse; §4.7):
> - Internal MRI (§1.4) and Nuclear Imaging (§1.5) — `subject:` + `condition:` + **`anatomy:`** always recommended (sample is always an organism; in-vivo scans need anatomical coverage). Unknowns written as `null` + WARN.
> - AxioScan 7 (§1.1), Cell Observer (§1.2), LSM 900 (§1.3) — **`condition:` is written for every microscopy sample** (tissue **and** `sample_type = cells` — a disease-model cell line vs a wild-type/untreated control is control-vs-case too; enabled 2026-06-09). Set it per run via the microscopy GUI's *Study metadata* panel or the template `condition:` block. **`subject:`** is written only for **animal-derived tissue** (DB-linked) — **not** for `sample_type = cells` (cell lines aren't in the animal-facility DB; record source-organism context in project metadata if needed). `anatomy:` is written for **tissue** (AxioScan) — the UBERON `region` the section was cut from, `is_whole_body` N/A (the *same* `region` field as in-vivo, so the old separate `anatomical_entity` is just its registry projection — [06_REGISTRIES §2.3](06_REGISTRIES.md)); it is **not** written for `cells` (a cell line's source organ is line-static — deferred 2026-06-09).
> - Not required for non-biological `material` / `phantom` samples.
>
> **Source hierarchies differ:**
> - **`subject:`** — animal-facility-DB (authoritative; **access granted 2026-06-02 and the lookup is implemented + live** in `tools/animal_db.py`, called from `ingest/enrichment.py` Step 8.4). Whether a given machine auto-fills `subject:` depends on whether it holds the read-only `~/.my.cnf` credentials (on-network/VPN) — **not on the OS**; a no-credentials or DB-miss ingest still succeeds, writes a `source: "pending-db"` placeholder, and queues for superuser recovery (§4.4.6). Then > study-level YAML at `/projects/<proj>/metadata/subjects.yaml` > instrument auto-extracts (often partial).
> - **`condition:`** — operator-entered only (per-batch YAML `condition:` block, or per-acquisition `/projects/<proj>/metadata/<acq_id>.json`, or via the Excel importer when it ships). The DB does NOT know disease state; it's a property of the study design, not the animal.
>
> **✅ Writer IMPLEMENTED (Phase 3, 2026-06-03).** The enrichment writer that produces these blocks now fires at ingest for every acquisition with `sample_type ∈ {organism, tissue}` (`anatomy:` for `organism` only) — **non-blocking** (§4.7): unknowns are written as explicit sentinels + a WARN, never an aborted ingest. The YAML surface that drives it (`auto_discover.subject_from_db` + `subject_lookup`, and the top-level `condition:` / `anatomy:` / `subject:` blocks) is documented in [10_TOOLS §2.1.6](10_TOOLS.md); the field contract stays in [08_METADATA §4.4-4.7](08_METADATA.md). The registry **`subject_id` column was added 2026-06-11 (S1)** — auto-populated from the sidecar `subject.facility_animal_id` (empty for non-animal samples; [06_REGISTRIES §2.2](06_REGISTRIES.md)). The `anatomical_entity` column remains **deferred** to the true-production restart — that block lives in the sidecar only.

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
| **Subject metadata** (DRAFT 2026-05-29; extended 2026-06-02) | 🔶 **Required when animal-derived** (typical case: H&E / IHC tissue sections from mouse organs → `sample_type = tissue`). Sidecar `subject:` block: species / strain / sex / date_of_birth (→ derived age_at_acquisition) + optional procedures. Not required for `material` (e.g. nanoparticle slides) or `phantom`. See [08_METADATA §4.4](08_METADATA.md). |
| **Condition / disease-state metadata** (DRAFT 2026-05-29) | 🔶 **Required when animal-derived** — sidecar `condition:` block: `is_control` (DECIDED boolean) + DRAFT-required `disease_model` + `disease_state`. Common case: comparing healthy-control vs disease-model tissue sections within the same staining batch. See [08_METADATA §4.5](08_METADATA.md). |
| **Anatomical region** (DRAFT 2026-06-09) | 🔶 **Recommended for `tissue`** — sidecar `anatomy:` block, **`region` only** (UBERON organ the section was cut from, e.g. heart / `UBERON:0000948`); `is_whole_body` is N/A for an ex-vivo section (stays null, not warned). Same UBERON field as the in-vivo scan `region`. Non-blocking (empty region WARNs). Set per batch in the config `anatomy:` block / per-acq override (not in the GUI yet). See [08_METADATA §4.6](08_METADATA.md). |
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
| **Subject metadata** (DRAFT 2026-05-29) | 🔶 Recommended for animal-derived **tissue**; **NOT auto-written for `sample_type = cells`** — the sidecar `subject:` writer is DB-only and cell lines aren't in the animal-facility DB. Capture a cell line's source-organism context in project-level study metadata instead. See [08_METADATA §4.4](08_METADATA.md). |
| **Condition / disease-state metadata** (DRAFT 2026-05-29) | 🔶 **Written for every acquisition** (incl. `sample_type = cells`, 2026-06-09) — sidecar `condition:` block: `is_control` + `disease_model` + `disease_state`, non-blocking (`null`/`""`+WARN until set). Set per run via the microscopy GUI *Study metadata* panel or the template block. For cell-line work, `disease_model` maps to the cell line's pathology context (e.g. `disease_model: "MDA-MB-231_breast_cancer"`, `disease_state: "untreated_baseline"`, `is_control: true` for untreated reference wells); can be mapped from the CZI `discovered.condition` chunk. See [08_METADATA §4.5](08_METADATA.md). |
| **Not embedded** | Sample information, experimental context |
| **Analysis tools** | ZEN, ImageJ/FIJI, QuPath |
| **Status** | ✅ Confirmed for pilot |

### 1.3 Confocal Microscopy — Zeiss LSM 900

| Attribute | Value |
|-----------|-------|
| **Instrument** | Confocal Microscope 900 (Zeiss LSM 900) — sits on an Axio Observer.Z1 stage |
| **Category** | Microscope (direct raw) |
| **Code** | `LSM9` |
| **Location** | Room 2.66 |
| **Platform** | Optical Spectroscopy and Microscopy Platform (Irantzu Llarena) |
| **Software** | ZEN Blue (full license: LSMPlus, Tile & Position, linear unmixing, colocalization, 3D Viewer) |
| **Excitation** | 405, 488, 561, 640 nm lasers |
| **Detectors** | 2 PMTs + 1 GaAsP (fluorescence) + ESID (brightfield) |
| **Primary format** | `.czi` — same Zeiss family as AxioScan + Cell Observer; same extractor (`tools/ingest/czi_metadata.py`) handles all three. |
| **Typical size** | Variable (single images to large tile/Z-stack datasets) |
| **Scanner resolution** | Up to 6144x6144 px; max 512x512 at 8 fps |
| **Imaging modes** | Confocal fluorescence (3 simultaneous channels), Z-stack, time series, tile, FRAP, FRET |
| **Objectives** | 2.5x-63x (air, water multi-immersion, oil) |
| **Embedded metadata** | Extensive (same 21 curated `discovered.czi_*` fields as §1.1 — same extractor). Distinguishing fingerprint vs Cell Observer: `czi_acquisition_mode = "LaserScanningConfocalMicroscopy"` (Cell Observer reports `"WideField"`). `czi_microscope_name` reports `"Axio Observer.Z1 / 7"` — same string as Cell Observer because the LSM 900 sits on an Axio Observer stage, so the name alone isn't a reliable fingerprint. |
| **Subject metadata** (DRAFT 2026-05-29) | 🔶 Same rule as Cell Observer (§1.2): **not auto-written for `sample_type = cells`** (DB-only writer; the round-7 batch is cultured MDA line on coverslips). Source-organism context goes in project metadata. See [08_METADATA §4.4](08_METADATA.md). |
| **Condition / disease-state metadata** (DRAFT 2026-05-29) | 🔶 **Written for every acquisition** (incl. `cells`, 2026-06-09) — same as Cell Observer (§1.2). For nanoparticle-uptake studies typical of LSM 900 work, `condition:` typically carries `disease_model: <cell_line_pathology>`, `disease_state: "<exposure_condition>_<timepoint>"`, `is_control: true` for vehicle/untreated wells, `treatment: "<nanoparticle>_<dose>"`; set via the GUI panel or template block. See [08_METADATA §4.5](08_METADATA.md). |
| **Not embedded** | Sample / experimental context — captured via per-instrument template's folder-name regex (researcher / experiment / cell_line) + project-level metadata for finer-grained context. |
| **Analysis tools** | ZEN, ImageJ/FIJI, QuPath, Napari |
| **Status** | 🔶 Round 7 active (2026-05-22). Per-instrument template at [`tools/templates/instruments/lsm900.yaml`](../tools/templates/instruments/lsm900.yaml); first test batch (LAURA_UPTAKE_LP-IONP-doxo_MDA) ingest in progress. |

**Auto-discovered fields** for LSM 900 are the same 21 `discovered.czi_*` fields documented in §1.1 (AxioScan 7), since all three Zeiss instruments share the `.czi` extractor. Per-instrument source convention (batch-folder regex extracting researcher / experiment / cell_line + the variable-chunk filename note) is documented in [`equipment/lsm900/lsm900_data_handling_workflow_notes.md`](../equipment/lsm900/lsm900_data_handling_workflow_notes.md).

### 1.4 Reconstructed Biomedical Imaging — Internal MRI Platform

| Attribute | Value |
|-----------|-------|
| **Instruments** | Bruker BioSpec 11.7T (9 cm gradient, 750 mT/m) and Bruker BioSpec 7T (30 cm bore, 200-400 mT/m) |
| **Category** | Platform instrument (reconstructed data) |
| **Code** | `MRI` |
| **Capabilities** | High-resolution anatomical (2D/3D), ultrafast (EPI, spiral), parallel imaging (GRAPPA, mSENSE), multinuclear spectroscopy (1H, 13C, 19F, 31P) |
| **Source format (Bruker ParaVision exam)** | Bruker ParaVision exam folders containing `acqp`/`method`/`visu_pars`/`subject` (JCAMP-DX text aux), raw `fid` (~12 MB k-space signal), `pdata/<idx>/` per-reconstruction subfolders each with `2dseq` (binary image), `visu_pars` (recon params), `reco`, and `dicom/MRIm<NN>.dcm` (per-frame DICOM export when the user has run Bruker's exporter). |
| **What lands on gjesus3 (round-6 v2 2026-05-27)** | **DICOMs only, flat in `<ACQ-ID>.data/`** ([03_RAW_STORAGE §4.4](03_RAW_STORAGE.md), [13_GJESUS3_ROLE §5.6](13_GJESUS3_ROLE.md)). The acquisition folder contains `metadata.json`, `checksums.json`, `README.txt`, and a `<ACQ-ID>.data/` subfolder holding renamed per-frame DICOMs: `recon<idx>_frame<NN>.dcm` (typically ~15 frames per recon × number of recons kept). NO aux files on disk — `acqp`/`method`/`visu_pars`/`subject`/`fid`/`2dseq`/`reco` all stay on the platform; their parsed content is in `metadata.json.mri._raw_metadata`. Multi-recon studies have all selected `pdata/<idx>/` recons in the same flat folder (e.g. `recon1_frame01.dcm`...`recon1_frame15.dcm` + `recon3_frame01.dcm`...`recon3_frame15.dcm`). |
| **No-DICOM acquisitions** | When a researcher hasn't run Bruker's DICOM exporter (~3 of 7 source projects in round 6), the ingest still registers the exam: `metadata.json.mri:` is fully populated from parsed JCAMP-DX, but `<ACQ-ID>.data/` is created empty and `mri.reconstruction.by_index.<idx>.dicoms[]` is `[]`. Idempotent re-run after the student converts will skip the placeholder + ingest the freshly-available DICOMs. Future-work FID→DICOM regeneration capability (tracked in `tasks/tasks.md §3.1`) would close this gap automatically. |
| **Typical size on gjesus3** | A few MB per acquisition (DICOMs only — ~200 KB × ~15-frame × N_recon, plus the few-KB sidecar). KB-scale for no-DICOM acquisitions. |
| **Embedded metadata** | Extensive. `tools/ingest/paravision_metadata.py` parses the JCAMP-DX aux files (`subject`/`acqp`/`method`/`visu_pars`/per-recon `visu_pars`+`reco`) — canonical source — plus the DICOM headers of every kept per-frame `.dcm`. Surfaces ~20 `discovered.mri_*` fields + a structured `mri:` sidecar block (subject/acquisition/geometry/reconstruction buckets + per-DICOM headers with `StudyInstanceUID`/`SeriesInstanceUID`/`SOPInstanceUID` first + lossless `_raw_metadata`). See `discovered.mri_*` table below + [08_METADATA §4.3](08_METADATA.md) `mri:` block shape. |
| **Subject metadata** (DRAFT 2026-05-29; extended 2026-06-02) | ✅ **Required** — `sample_type = organism`. Sidecar `subject:` block must carry species / strain / sex / date_of_birth (→ derived age_at_acquisition) + optional procedures (the DECIDED required fields, ARRIVE-aligned). Today the ParaVision `subject` file (`mri._raw_metadata.subject.SUBJECT_*`) is the only auto-source and is typically partial (sex/weight present; species/strain/DOB usually empty). **Animal-facility-DB integration (access obtained 2026-06-02) is the authoritative source**; on an ingest-time DB miss the acquisition is queued for superuser recovery (§4.4.6) rather than failing — see [08_METADATA §4.4](08_METADATA.md) + `tasks/tasks.md §3.2`. |
| **Condition / disease-state metadata** (DRAFT 2026-05-29; non-blocking 2026-06-03) | 🔶 **Recommended (non-blocking)** — `sample_type = organism`. Sidecar `condition:` block: `is_control` (tri-state `true`/`false`/`null`, WARN if null) + `disease_model` + `disease_state`. Particularly useful for MRI cohorts mixing cardiac MI / Alzheimer / oncology / metabolic models. Set once per batch/session; `disease_model` auto-seeds from DB `projects.name`. See [08_METADATA §4.5](08_METADATA.md) + §4.7. |
| **Anatomical coverage** (DRAFT 2026-06-03; non-blocking) | 🔶 **Recommended (non-blocking)** — `sample_type = organism`. Sidecar `anatomy:` block: `is_whole_body` (tri-state, WARN if null — full-body vs ROI) + UBERON-coded `region` when not whole-body. ParaVision exposes only weak hints (`ProtocolName` e.g. `1_Localizer_multi_slice` + `geometry.fov`); `BodyPartExamined` is empty → optional non-authoritative auto-hint. See [08_METADATA §4.6](08_METADATA.md) + §4.7. |
| **Not embedded** | Study context beyond what `subject` + `condition` already capture (e.g. specific research question, surgical preparation detail) |
| **Analysis tools** | 3D Slicer, ITK-SNAP, FSL, nibabel, PMOD, pydicom (most expect NIfTI for analysis; ingest does NOT generate NIfTI — that's a project-level tool, future, see [08_METADATA §1.5a](08_METADATA.md)). The kept DICOMs work directly in any DICOM-aware viewer. |
| **Raw data responsibility** | MRI platform archives the originals on the acquisition machines (`/opt/PV-7.0.0/data/nmr/` + FTP mirror). **Medium trust** ([13_GJESUS3_ROLE §5.6](13_GJESUS3_ROLE.md) — generally reliable, no formal byte-lock guarantee) — gjesus3 keeps the analysis-ready DICOMs; the raw `fid` (k-space) and platform-internal files stay only on the platform. |
| **Operator model** | **No dedicated technician** — researchers run the scanner themselves. Permission model for ingest-time `/raw/` writes is future work (see `tasks/tasks.md` §3.3 user-as-operator). |
| **Status** | ✅ Round-6 ingest **v2 landed 2026-05-27** with `<ACQ-ID>.data/` flat-DICOM layout (mirrors NI v2.1), parsed JCAMP-DX content in sidecar (no aux files duplicated to disk), DICOM UIDs first in curated headers, no-DICOM acquisition handling. v1 (2026-05-22) preceded — full purge + re-ingest history in `tasks/tasks.md §4.5` + equipment workflow notes "Round-6 v2 reshape" section. Convention + workflow documented in [`equipment/mri-platform/internal_mri_data_handling_workflow_notes.md`](../equipment/mri-platform/internal_mri_data_handling_workflow_notes.md). |

> **📣 INPUT NEEDED:** Do the two MRI systems need separate instrument codes (e.g., `MRI7` and `MRI11`), or is a single `MRI` code sufficient? Round 6 used shared `MRI` for sample data from the 7T system; question carried forward to first 11.7T batch.

#### Auto-discovered fields (`discovered.mri_*`)

These are surfaced from each Bruker ParaVision exam at ingest time by `tools/ingest/paravision_metadata.py`'s `EXPOSED_FIELDS`, parsed out of the JCAMP-DX `subject` (study root) + `acqp` / `method` / `visu_pars` (exam) + per-reconstruction `visu_pars` / `reco` files. Available for reference in any resolver-evaluated YAML field (`registry:`, `auto_create_project:`, `link_filename:`). The Python source is the single source of truth; this table is its mirror.

| Field | Description | JCAMP-DX source |
|-------|-------------|-----------------|
| `mri_study_name` | Study name from `subject` (canonical study/session identifier; same as `mri_animal_id` in MFB convention) | `subject.SUBJECT_study_name` |
| `mri_animal_id` | Subject/animal ID (typically matches study name) | `subject.SUBJECT_id` |
| `mri_animal_sex` | Animal sex | `subject.SUBJECT_sex` |
| `mri_animal_weight` | Animal weight (units per platform — typically kg in ParaVision) | `subject.SUBJECT_weight` |
| `mri_animal_type` | Animal type / category (e.g. `"Quadruped"`) | `subject.SUBJECT_type` |
| `mri_position` | Animal positioning (e.g. `"SUBJ_POS_Supine"`) | `subject.SUBJECT_position` |
| `mri_study_datetime` | Study start datetime from `subject` (ParaVision local time) | `subject.SUBJECT_date` |
| `mri_paravision_version` | ParaVision software version (e.g. `"7.0.0"`) | parsed from any `TITLE` line |
| `mri_exam_number` | ParaVision Examination Entry number (the exam folder name) | derived from exam path |
| `mri_acquisition_datetime` | Per-exam creation datetime from `visu_pars` (used in registry's `acquisition_datetime`) | `visu_pars.VisuCreationDate` |
| `mri_modality` | DICOM-style modality code from `visu_pars` (typically `"MR"`) | `visu_pars.VisuInstanceModality` |
| `mri_sequence_name` | Bruker method / sequence name (e.g. `"Bruker:IgFLASH"`) | `method.Method` |
| `mri_pulse_program` | Pulse program file (e.g. `"IgFLASH.ppg"`) | `acqp.PULPROG` |
| `mri_nucleus` | Primary nucleus (e.g. `"1H"`) | `method.PVM_Nucleus1` |
| `mri_echo_time_ms` | Echo time TE in ms | `method.PVM_EchoTime` |
| `mri_repetition_time_ms` | Repetition time TR in ms | `method.PVM_RepetitionTime` |
| `mri_scan_time_str` | Human-readable scan duration (e.g. `"0h3m17s865ms"`) | `method.PVM_ScanTimeStr` |
| `mri_matrix` | Acquisition matrix as `"NxM"` (e.g. `"256x128"`) | `method.PVM_Matrix` |
| `mri_frame_count` | Number of frames in the reconstructed image (slices / cardiac frames / etc.) | `visu_pars.VisuCoreFrameCount` |
| `mri_recon_indices` | Comma-separated list of `pdata/<idx>/` reconstructions present in the source (e.g. `"1,3"`) | derived from `pdata/` directory listing |

The richer structured form of all the above plus the full parsed JCAMP-DX dump is preserved in the sidecar's `mri:` block — see [08_METADATA §4.3](08_METADATA.md). Library / route choice (manual JCAMP-DX parser via `tools/ingest/jcampdx.py`; no third-party deps) and what's deferred (Enhanced MR / Multi-Frame DICOM evaluation, our-own-DICOM regeneration, project-level NIfTI generation) is tracked in `tasks/tasks.md` §3.1 Future work.

For the systematic naming convention used by the MRI platform (parsable folder-name structure, `jrc` vs `jrc_` PI-initials ambiguity, animal-id composition, terminology distinction from Nuclear Imaging's "project"), see [`equipment/mri-platform/internal_mri_data_handling_workflow_notes.md`](../equipment/mri-platform/internal_mri_data_handling_workflow_notes.md) "Systematic naming convention (parsable)" section.

### 1.5 Reconstructed Biomedical Imaging — Nuclear Imaging Platform

| Attribute | Value |
|-----------|-------|
| **System 1** | Molecubes PET/SPECT/CT — modular trimodal (gamma-CUBE SPECT, beta-CUBE PET with 13 cm axial FOV, X-CUBE CT at 50 µm); 3DOSEM reconstruction |
| **System 2** | MILabs VECTor PET/SPECT/CT/OI — integrated multimodal; submillimeter PET/SPECT; multi-isotope (e.g., 18F + 89Zr simultaneous); MLEM/POSEM/SROSEM reconstruction; GPU server (36 TB) |
| **Other** | Autoradiography system (endpoint imaging) |
| **Category** | Platform instrument (reconstructed data) |
| **Codes** | `PET`, `SPECT`, `CT` (one per archive — set per case via `discovered.modality` from the archive-name regex) |
| **Workstations** | 3 dedicated workstations with PMOD and Imalytics |
| **Source format (Molecubes archive)** | Molecubes archive on `\\cicmgsp02\gnuclear2$` contains BOTH the analysis-ready DICOMs AND the raw event/calibration data. Per-acquisition layout: `protocol.txt` + XML aux at acq root (`protocol.xml`, `acqparams.xml`, `recontemplate.xml`), plus `recon_<idx>/<basename>.dcm` (CT, multiple recons) or `recon_<idx>/frame_<n>/iter_30/<basename>.dcm` (PET/SPECT, possibly multiple frames). MILabs VECTor format **not yet observed** in our archives. |
| **What lands on gjesus3 (round-8 v2.1 2026-05-27)** | **DICOMs only, flat in `<ACQ-ID>.data/`** ([03_RAW_STORAGE §4.3](03_RAW_STORAGE.md), [13_GJESUS3_ROLE §5.6](13_GJESUS3_ROLE.md)). The acquisition folder contains `metadata.json`, `checksums.json`, `README.txt`, and a `<ACQ-ID>.data/` subfolder holding the renamed DICOMs: `recon<X>.dcm` for CT (one per recon), `recon<X>_frame<Y>.dcm` for PET/SPECT (one per time frame), `recon<X>_frameMULTI.dcm` for the platform-generated bundled-all-frames DICOM (present only for dynamic PET/SPECT studies, kept alongside the per-frame DICOMs). NO aux files on disk — their parsed content is in `metadata.json.ni._raw_metadata`. |
| **Typical size on gjesus3** | Few MB per acquisition (DICOMs + small aux). Source archive is 1-15 GB unpacked; the slim shape lives ~MB-scale. |
| **Embedded metadata** | Rich. `tools/ingest/ni_metadata.py` parses `protocol.txt` (key-value text) + the three XML aux files + DICOM headers of one representative `.dcm` per recon. Surfaces ~15 `discovered.ni_*` fields for YAML reference + a structured `ni:` sidecar block (study / subject / acquisition / reconstruction buckets + lossless `_raw_metadata`). See `discovered.ni_*` table below + [08_METADATA §4.3](08_METADATA.md) `ni:` block shape. |
| **Subject metadata** (DRAFT 2026-05-29; extended 2026-06-02) | ✅ **Required** — `sample_type = organism`. Sidecar `subject:` block must carry species / strain / sex / date_of_birth (→ derived age_at_acquisition) + optional procedures (the DECIDED required fields, ARRIVE-aligned). Molecubes' `protocol.txt` carries only `Animal ID` + `Animal weight (g)` — no species/strain/sex/DOB. **Animal-facility-DB integration (access obtained 2026-06-02) is the bridge**; ingest-time DB miss queues for superuser recovery rather than failing (§4.4.6) — see [08_METADATA §4.4](08_METADATA.md) + `tasks/tasks.md §3.2`. |
| **Condition / disease-state metadata** (DRAFT 2026-05-29; non-blocking 2026-06-03) | 🔶 **Recommended (non-blocking)** — `sample_type = organism`. Sidecar `condition:` block: `is_control` (tri-state `true`/`false`/`null`, WARN if null) + `disease_model` + `disease_state` + optional `treatment` (e.g. injected tracer + dose for PET). Set once per batch/session. The `protocol.txt` `Scan protocol` + `Isotope` + `Activity` fields are NOT a substitute (they describe acquisition, not subject disease state). See [08_METADATA §4.5](08_METADATA.md) + §4.7. |
| **Anatomical coverage** (DRAFT 2026-06-03; non-blocking) | 🔶 **Recommended (non-blocking)** — `sample_type = organism`. Sidecar `anatomy:` block: `is_whole_body` (tri-state, WARN if null — full-body vs ROI) + UBERON-coded `region` when not whole-body. Molecubes hint: the `protocol.txt` `Scan bed position from X to Y` range correlates with axial coverage (more positions ≈ whole-body) → optional non-authoritative auto-hint; `BodyPartExamined` is empty. See [08_METADATA §4.6](08_METADATA.md) + §4.7. |
| **Not embedded** | Study context (research question, sample preparation) — captured at project level. |
| **Analysis tools** | PMOD, Imalytics, 3D Slicer, ITK-SNAP, MATLAB, pydicom |
| **Raw data responsibility** | Nuclear Imaging platform archives true raw data (listmode, sinograms, event lists) on `\\cicmgsp02\gnuclear2$` indefinitely — **trusted as the long-term archive**. The 1% case of "we need the raw event data" routes back through the platform. See [13_GJESUS3_ROLE §5.6](13_GJESUS3_ROLE.md) per-platform reliability table. |
| **Operator model** | **No dedicated technician** — researchers run the equipment themselves. Permission model for ingest-time `/raw/` writes is future work (see `tasks/tasks.md` §3.3 user-as-operator). |
| **Status** | ✅ Round-8 ingest **v2.1 landed 2026-05-27** with `<ACQ-ID>.data/` flat-DICOM layout (renamed flat: `recon<X>.dcm` / `recon<X>_frame<Y>.dcm` / `recon<X>_frameMULTI.dcm`), parsed protocol.txt + XML aux content in sidecar (no aux files duplicated to disk), DICOM UIDs first in curated headers. Multi-frame DICOMs kept alongside per-frame for dynamic PET/SPECT studies. v1 (2026-05-26) and v2 (initial 2026-05-27) preceded — full purge + re-ingest history in `tasks/tasks.md §4.7` + equipment workflow notes "Round-8" section. Live-machine workflow still pending Platform Manager Unai's answer. |

> **⚠️ GAP:** MILabs VECTor exports both DICOM and NIfTI. Need to confirm which format(s) the platform provides to researchers, and whether NIfTI should be an accepted format on gjesus3.

#### Auto-discovered fields — archive-basename regex

These come from the archive-basename regex (`tools/templates/instruments/molecubes_ni.yaml`), parsed from the `.tgz` name `<user>_<series_id>_<YYMMDD>_<short_project>_<short_sample>_<YYYYMMDDhhmmss>_<modality>`.

| Field | Description |
|-------|-------------|
| `user` | NI user (e.g. `irene`) |
| `series_id` | **Funded-project id** (e.g. `0525`, `1207`). Different from MRI's animal-protocol short id; see workflow notes for the distinction. |
| `acq_date_short` | YYMMDD form of the acquisition date (e.g. `251029`) |
| `short_project` | **Animal-protocol short id** (e.g. `0525`, `0424`). Drives `project_hint` (cross-modality reuse with rounds 4 + 6 `ae-biomegune-NNNN` workspaces). |
| `short_sample` | Sample identifier — `<animal type><number>` for animals (e.g. `m13`) or `phantom_*` free-text for QC |
| `acq_datetime_full` | Full YYYYMMDDhhmmss timestamp (e.g. `20251029100641`) — drives the registry `acquisition_datetime`. Round-8 extended `resolver.normalize_acquisition_datetime` to handle this 14-digit form. |
| `modality` | `PET` / `CT` / `SPECT` / `OI` — drives the per-case `registry.instrument` |
| `folder_name` | Standard auto-discovery — equals the archive basename |

#### Auto-discovered fields (`discovered.ni_*`) — embedded extractor

These come from `tools/ingest/ni_metadata.py::EXPOSED_FIELDS`, parsed out of `protocol.txt` (the primary key-value text source) + the XML aux files + DICOM headers from one representative `.dcm` per reconstruction. The Python source is the single source of truth; this table is its mirror (per CLAUDE.md cross-ref rule).

| Field | Description | Source |
|-------|-------------|--------|
| `ni_study_name` | Study name from `protocol.txt` (typically the funded-project id, e.g. `0525`) | `protocol.txt: Study name` |
| `ni_series_name` | Series name from `protocol.txt` (typically the acquisition-date short form) | `protocol.txt: Series name` |
| `ni_pi` | **Intentionally empty (2026-06-09).** NOT taken from `protocol.txt`: the Molecubes platform writes the **operator's username** into the "Principal Investigator" field (a platform-labelling bug, under investigation), so it's unreliable. The curated `ni.study.principal_investigator` is also emptied; the raw (possibly-wrong) value is preserved verbatim in `ni._raw_metadata.protocol_txt`. The true PI comes from the archive `<year>/<PI first name>/<user>/<session>` tree at batch import, or operator entry (see `tasks/BACKLOG.md`). **PHASE-OUT:** restore reading `protocol.txt` once the platform is fixed. | `""` (was `protocol.txt: Principal Investigator`) |
| `ni_modality` | Modality reported by the platform: `PET` / `CT` / `SPECT` / `OI` | `protocol.txt: Modality` |
| `ni_acquisition_datetime` | Per-acquisition datetime from `protocol.txt` (machine-issued) | `protocol.txt: Date/time` |
| `ni_animal_id` | Subject/animal ID (e.g. `0525_m13` — combines short_project + short_sample) | `protocol.txt: Animal ID` |
| `ni_animal_weight_g` | Animal weight in grams (often `0` if not entered by operator) | `protocol.txt: Animal weight (g)` |
| `ni_scan_protocol` | Scan protocol name (e.g. `spiral high-resolution`) | `protocol.txt: Scan protocol` |
| `ni_bed_from` | Scan bed start position (mm) | `protocol.txt: Scan bed position from <X> to <Y>` (first capture) |
| `ni_bed_to` | Scan bed end position (mm) | `protocol.txt: Scan bed position from <X> to <Y>` (second capture) |
| `ni_isotope` | Radioisotope used (PET/SPECT only — empty for CT, e.g. `F-18`) | `protocol.txt: Isotope` |
| `ni_activity_mbq` | Injected activity in MBq (PET/SPECT only) | `protocol.txt: Activity` |
| `ni_n_frames` | Number of time frames (PET only; static = 1) | `protocol.txt: Number of frames` |
| `ni_scan_duration_s` | Scan duration in seconds (PET only) | `protocol.txt: Scan duration` |
| `ni_recons_present` | Comma-separated list of `recon_<idx>` subfolders kept on gjesus3 (e.g. `0,1,2` for CT, `0` for PET) | derived from `reconstructions/recon_*/` directory listing |

The structured form of all the above plus DICOM header summaries + parsed XML aux files + verbatim `protocol.txt` is in the sidecar's `ni:` block — see [08_METADATA §4.3](08_METADATA.md). Round-8 ingest config: [`tools/configs/ni_jesus_archive_2025_TEST.yaml`](../tools/configs/ni_jesus_archive_2025_TEST.yaml). Per-batch convention + per-recon detail: [`equipment/nuclear-imaging/internal_ni_data_handling_workflow_notes.md`](../equipment/nuclear-imaging/internal_ni_data_handling_workflow_notes.md).

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
| ~~MOD-07~~ | ~~Confirm Cell Observer and LSM 900 .czi metadata is similar to WSI .czi~~ | — | ✅ Resolved (Cell Observer): round-5 ingest 2026-05-15 confirmed `.czi` from Cell Observer surfaces the same 21 curated `discovered.czi_*` fields as AxioScan; `tools/ingest/czi_metadata.py` reused 1:1. LSM 900 confirmation still pending (awaiting Ainhize Urkola Arsuaga's example) but expected to follow the same pattern given shared format + vendor + ZEN software family. |
| MOD-08 | Internal MRI: `discovered.mri_*` table mirrors `paravision_metadata.EXPOSED_FIELDS` — when the extractor grows fields, update §1.4 in lockstep | Data Mgmt Lead | ✅ Convention documented (CLAUDE.md cross-ref rule); currently in sync as of 2026-05-27 (round-6 v2 redo) |
