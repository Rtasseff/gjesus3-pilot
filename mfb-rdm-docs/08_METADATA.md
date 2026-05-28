# 08 — Metadata

**Parent:** [Documentation Index](00_INDEX.md)  
**Status:** 🔶 Draft  
**Last Updated:** 2026-05-27 (Round-6 v2 MRI redo: `mri:` block rewritten with per-DICOM `dicoms[]` list + UIDs first, mirroring NI v2.1; no-DICOM acquisition handling documented)

---

## Purpose

This document specifies the metadata requirements for raw acquisitions, including the README template and extended (REMBI-based) metadata.

---

## 1. Where Metadata Lives

> **✅ DECIDED (2026-05-12):** Metadata is split between **acquisition-level** (in `/raw/`, immutable after ingest) and **study-level** (in `/projects/`, writeable by researchers during the project's life). The split aligns with REMBI's hierarchy and lets `/raw/` enforce strict permissions without blocking researcher metadata work.

### 1.1 Three locations

| Location | What lives there | Set by | When | Mutable post-ingest? |
|----------|------------------|--------|------|----------------------|
| `registry_raw.csv` | Indexed core fields (`acq_id`, `instrument`, `sample_id`, `sample_type`, `project_hint`, etc.). See [06_REGISTRIES](06_REGISTRIES.md). | Auto + Operator (via YAML `registry:` block) | At ingest | Admin-only (corrections) |
| `/raw/<ACQ-ID>/metadata.json` | Per-acquisition sidecar — `user_supplied` (Operator at ingest), `discovered` (filename chunks + embedded auto-extracts), `<ecosystem_section>` (structured + `_raw_metadata` lossless). | Auto + Operator | At ingest | No (raw is read-only post-deposit) |
| `/projects/<proj>/metadata/` | Study-level metadata — experimental aim, biological subject details (strain, age, sex, treatment), experimental groups, per-acquisition supplements. REMBI's **Study** + **Biosample** context. | Researcher (eventually via the Excel-import tool — see [10_TOOLS](10_TOOLS.md)) | After ingest, iteratively | Yes (project owners write during the project's life) |

### 1.2 Why the split

REMBI is hierarchical: **Study** contains **Biosamples**, which undergo **Image Acquisitions**, which produce **Images**. Image-acquisition metadata is a property of the capture event (locked in at acquisition time). Study/biosample metadata is a property of the experiment (refined as the researcher learns and writes).

Collapsing both into `/raw/<ACQ-ID>/metadata.json` worked while the only writer was the Operator at ingest. As soon as researchers needed to edit study context, it conflicted with the "raw is immutable" rule. The split resolves it: `/raw/` stays strictly read-only after deposit; `/projects/` is where researchers do mutable work.

### 1.3 Permanent vs ephemeral storage

- `/raw/` and `/publications/` are **permanent archives.** RAID-protected; eventually cold storage. Anything that must survive in perpetuity lives here.
- `/projects/` is **temporary working space.** Projects are created, used, then closed and **deleted** (see [05_PROJECTS §5](05_PROJECTS.md)). Study-level metadata in `/projects/<proj>/metadata/` is therefore at risk of loss without an explicit preservation step.

**Implication: at project close-out, study-level metadata must migrate into the permanent archive** before the project folder is deleted. The intended mechanism is a close-out tool (run by the Data Mgmt Lead) that appends/merges the contents of `/projects/<proj>/metadata/` into the corresponding `/raw/<ACQ-ID>/metadata.json` files — a controlled, one-time admin write to `/raw/`. Tracked in `tasks/tasks.md` §3.2.

### 1.4 Joining the two locations

Consumers (OMERO, future indexing DB, ad-hoc analysis scripts) join `/raw/<ACQ-ID>/metadata.json` and `/projects/<proj>/metadata/<acq_id>.json` on `acq_id`. A small utility `tools/gather_metadata.py` will produce a merged view on demand; tracked in `tasks/tasks.md` §3.2. Until that ships, joins are a two-file read.

### 1.5a Project-level tool family (the things that write to `/projects/`)

A small family of project-scoped tools share the same pattern: read from `/raw/` (immutable), do their work under `/projects/<proj>/`, and accept that anything written under `/projects/` is **ephemeral** (lost at project close-out unless explicitly preserved). Tracked in `tasks/tasks.md` §3.2:

| Tool | What it does | Status |
|---|---|---|
| `gather_metadata.py` | Read-only join of `/raw/<ACQ-ID>/metadata.json` + `/projects/<proj>/metadata/<acq_id>.json` | Planned |
| Excel → study-metadata importer | Researcher-facing tool that writes `/projects/<proj>/metadata/{study,biosamples,<acq_id>}.json` from a per-project Excel | Planned (schema in design) |
| Project close-out tool | Admin tool that merges `/projects/<proj>/metadata/` into the corresponding `/raw/<ACQ-ID>/metadata.json` files **before** the project folder is deleted; controlled one-time write to `/raw/` | Planned |
| Project-level NIfTI generation (NEW, planned 2026-05-20) | For MRI projects: read chosen ACQ-IDs via the project's `raw_linked/` shortcuts, run `dcm2niix` (or `bruker2nifti`) per acquisition, write `<ACQ-ID>.nii.gz` under `/projects/<proj>/derived_nifti/`. Removed at project close-out — regenerable from raw if needed later. Aligns with the [13_GJESUS3_ROLE](13_GJESUS3_ROLE.md) reframe (research-facing derivatives belong in projects). | Planned |

All of these are post-deposit; none of them modify `/raw/` except the close-out tool (which does a single controlled merge).

### 1.5 Project metadata layout

The intended layout under each project folder:

```
/projects/proj-<short_name>/
├── _project.yaml
├── provenance.csv
├── raw_linked/             # .lnk shortcuts to raw acquisitions
└── metadata/               # study-level metadata (this section)
    ├── study.json          # study aim, hypothesis, principal contact, biological-subject defaults
    ├── biosamples.json     # mouse-by-mouse details: strain, age, sex, treatment, timepoints
    └── <acq_id>.json       # per-acquisition supplements (optional, one per acq when needed)
```

Shape details are deferred to the Excel-import tool spec (`tasks/tasks.md` §3.2). For now the architectural rule is: **study/biosample/experimental-context metadata lives under `/projects/<proj>/metadata/`, period.**

---

## 2. README Template

**File:** `README.txt` in each acquisition folder

```
================================================================================
ACQUISITION NOTES — [ACQ-ID]
================================================================================
Date:               [YYYY-MM-DD]
Operator:           [Name]
Instrument:         [Instrument name/code]

SAMPLE
------
Sample ID:          [Internal identifier]
Sample Type:        [e.g., mouse lung tissue section]
Species:            [e.g., Mus musculus]
Preparation:        [e.g., FFPE, 5µm section]
Staining:           [e.g., H&E]

ACQUISITION
-----------
Objective:          [e.g., 20x / 0.8 NA]
Scan Area:          [e.g., full slide]
Channels:           [e.g., brightfield]

CONTEXT
-------
Project:            [Associated project ID]
Purpose:            [Why this acquisition]

NOTES
-----
[Quality issues, deviations, other notes]
================================================================================
```

**Minimum required:** ACQ-ID, Date, Operator, Instrument, Sample ID, Sample Type, Purpose

---

## 3. REMBI-Based Extended Metadata

### 3.1 Background

REMBI (Recommended Metadata for Biological Images) is the community standard for biological imaging metadata. We adopt a subset appropriate to our use cases.

### 3.2 Field Review Status

> **⚠️ GAP:** User review of REMBI fields is incomplete.

A spreadsheet was circulated for users to vote on each field. Limited responses received.

**Approach:** Start with minimal set; expand based on actual needs.

### 3.3 Proposed Minimal Set

| Category | Field | Required | Notes |
|----------|-------|----------|-------|
| **Biosample** | Sample ID | ✅ Yes | Internal identifier |
| | Biological entity | ✅ Yes | What is being imaged |
| | Organism/Species | ✅ Yes | Species |
| **Specimen** | Preparation method | ✅ Yes | How sample was prepared |
| | Staining/labeling | ✅ Yes | Contrast mechanism |
| **Acquisition** | Instrument | ✅ Yes | Which microscope |
| | Imaging method | ✅ Yes | e.g., brightfield, fluorescence |
| | Objective | 🔶 Recommended | Magnification, NA |
| | Pixel size | 🔶 Recommended | Physical resolution |

### 3.4 Machine-Readable Format — Future REMBI Projection Target

**File:** `metadata.json` (auto-generated by full-mode ingest; optional in lightweight mode)

> **Note (2026-05-06):** The shape sketched below — `biosample` / `specimen` / `acquisition` keys at the top level — is a **future projection target**, not what the sidecar produces today. The current sidecar shape is described in §4.3 (`user_supplied` / `discovered` / `<ecosystem_section>`). See §3.5 for the deferral rationale and reconciliation plan.

```json
{
  "acq_id": "ACQ-20260215-ZWSI-001",
  "schema_version": "1.0",
  "biosample": {
    "sample_id": "MOUSE-2024-042",
    "biological_entity": "lung tissue section",
    "organism": "Mus musculus"
  },
  "specimen": {
    "preparation": "FFPE, 5µm section",
    "staining": "H&E"
  },
  "acquisition": {
    "instrument": "Zeiss Axio Scan 7",
    "imaging_method": "brightfield",
    "objective": "20x / 0.8 NA",
    "pixel_size_um": 0.5
  }
}
```

### 3.5 REMBI Mapping — Status & Plan

> **🔶 DEFERRED (2026-05-06):** Per-instrument mapping of vendor metadata into REMBI fields is **deferred** until we have batch ingestion across multiple instruments to map *from*. Until then, the sidecar preserves vendor metadata raw.

**Why defer.** REMBI is a community-curated subset, not a superset. Vendor metadata (CZI, DICOM, NIfTI, etc.) is rich and not all of it maps cleanly to REMBI fields. Designing the mapping before we have real data across multiple modalities risks (a) losing information that doesn't fit, (b) committing to mappings we'd revise once we see what users actually need. Lossless preservation is irreversible work; interpretation can be redone.

**Current pragmatic shape.** The sidecar today is `{ user_supplied, discovered, <ecosystem_section> }` — see §4.3. It captures everything we can surface from filename + folder + embedded vendor metadata, with no REMBI mapping in between.

**Reconciliation plan.**

1. Ingest representative batches across the in-scope instruments (Axio Scan 7, Cell Observer, LSM 900, MRI, Nuclear Imaging).
2. From the populated sidecars, design per-instrument projections into REMBI's `biosample / specimen / acquisition` shape.
3. Implement a separate utility (e.g. `metadata_to_rembi.py`) that reads sidecars and emits a REMBI-shaped derivative — independent of the ingest path, so the canonical sidecar remains lossless.
4. Update §3.4 once that utility ships, with the actual mapping rules per modality.

This separation keeps preservation and interpretation as distinct concerns.

---

## 4. Embedded Metadata

> **Where to find what we extract per instrument:** the per-instrument tables of `discovered.<eco>_*` fields (curated subset that YAML `registry:` blocks can reference) live alongside each instrument's other specs in [09_MODALITIES](09_MODALITIES.md). The richer structured form of those fields plus the lossless `_raw_metadata` dump live in the sidecar's `<ecosystem_section>` (see §4.3).

### 4.1 Instrument Audit Status

| Instrument / format | Embedded? | Audit status | What's extracted today | What's NOT embedded (still user-supplied) |
|---------------------|-----------|--------------|------------------------|-------------------------------------------|
| Zeiss .czi (ZWSI / CELL / LSM9) | Yes — extensive | ✅ Audited 2026-05-06 | 21 curated `discovered.czi_*` fields + 5 structured buckets (geometry, instrument, acquisition, mosaic, document_info) + full XML in `_raw_metadata`. See [09_MODALITIES §1.1](09_MODALITIES.md#11-whole-slide-imaging--zeiss-axio-scan-7) for the field list. | Sample info, experimental context, biological/specimen attributes |
| Histology .tif (if used) | Partial | 📋 Planned (may be deferred — mostly used for converted exports) | None yet | Most context |
| Bruker ParaVision (internal MRI) | Yes — extensive (JCAMP-DX aux files + per-DICOM headers) | ✅ Audited 2026-05-27 (round-6 v2 redo) | ~20 curated `discovered.mri_*` fields + 4 structured buckets (`subject`, `acquisition`, `geometry`, `reconstruction`) + per-DICOM curated headers with UIDs first (`StudyInstanceUID`, `SeriesInstanceUID`, `SOPInstanceUID` + MRI-specific tags `MagneticFieldStrength`, `EchoTime`, `RepetitionTime`, `FlipAngle`, `ScanningSequence`, `SequenceVariant`) + parsed JCAMP-DX dump in `_raw_metadata.{subject, acqp, method, visu_pars, pdata.<idx>.{visu_pars, reco}}`. Implementation in `tools/ingest/paravision_metadata.py` (mirrors `ni_metadata.py` shape). **ParaVision aux files are canonical** (acqp / method / visu_pars / subject); per-frame DICOM headers complement them with UIDs needed for downstream tooling. **No-DICOM case**: when students don't run Bruker's exporter, the JCAMP-DX-derived buckets + `_raw_metadata` are still populated; per-DICOM `dicoms[]` lists are empty. See §4.3 below + 09_MODALITIES MRI section. | Sample/experimental context beyond what `subject` already captures |
| Collaborator DICOM (XMRI / XCT / XPET / XSPECT) | Yes — embedded DICOM headers | ⚠️ Pending (§3.1 deferred item) | None yet — extractor will mirror the `.czi` pattern (`discovered.dicom_*` + sidecar `dicom._raw_metadata`). Independent of the ParaVision work above. | Study context varies; sample/experimental info |
| Internal PET / SPECT / CT (Molecubes archive) | Yes — protocol.txt + XML aux + DICOM headers | ✅ Audited 2026-05-26 (round-8 redo) | ~15 curated `discovered.ni_*` fields + 4 structured buckets (`study`, `subject`, `acquisition`, `reconstruction`) + verbatim `protocol.txt` + parsed XMLs in `_raw_metadata`. Implementation in `tools/ingest/ni_metadata.py` (mirrors `paravision_metadata.py` shape). See §4.3 below + 09_MODALITIES NI section. **MILabs VECTor format not yet observed** in our archives; extractor adds when sample data arrives. | Study context (research question, sample prep) — captured at project level |
| EM (.tif / .dm3 / .dm4) | Varies by source | ⚠️ Pending (and SEM/TEM scope itself is `EVALUATING`) | None yet | Most context |

### 4.2 Extraction Possibility

For instruments with embedded metadata:
- Extraction scripts could populate `metadata.json` automatically
- README would focus on what's NOT embedded (sample info, context)

> **✅ DECIDED:** Auto-extraction of embedded metadata is integrated into the full-mode ingest workflow (see [10_TOOLS](10_TOOLS.md)). DICOM storage format is resolved — compressed archives (.zip/.tar.gz); metadata is extracted before compression during full-mode ingest. Lightweight-mode ingests skip extraction but can be upgraded later via `backfill_metadata`. User-supplied metadata (sample context, experimental notes) remains deferred.

### 4.3 `metadata.json` Sidecar (implemented 2026-05-06)

The sidecar is written by `tools/ingest/metadata_sidecar.py` for every full-mode acquisition (DICOM and microscopy). On-disk shape:

```json
{
  "acq_id": "...",
  "generated": "<ISO UTC>",
  "generator": "ingest_raw.py",
  "user_supplied": { "operator", "data_source", "instrument", "sample_id", "sample_type", "original_name", "notes" },
  "discovered":    { "<field>": "<value>", ... },
  "<ecosystem_section>": { ... }
}
```

| Section | Source |
|---------|--------|
| `user_supplied` | The resolved values from the YAML `registry:` block (literal text, `discovered.<x>` references, or `${...}` interpolation — see [10_TOOLS §2.1](10_TOOLS.md)). |
| `discovered` | Everything `auto_discover` surfaced for the case: filename-parser output, parent-folder date, `folder_name` / `filename`, and embedded extracts (`discovered.czi_*` for microscopy, `discovered.mri_*` for ParaVision). |
| `<ecosystem_section>` | The structured embedded-metadata block keyed by ecosystem subfield: `microscopy` (for .czi), `mri` (for Bruker ParaVision — new 2026-05-20). Each has curated buckets at the top for human skimming + a `_raw_metadata` dump for forensic preservation. |

**Per-column registry mapping is in YAML, not Python.** The Python `SPECIAL_FIELDS` promotion mechanism (used briefly in early 2026-05) is gone — adding or renaming a column promotion is a YAML-only edit (see [10_TOOLS §2.1](10_TOOLS.md) for schema, validation rules, and template).

#### `mri:` block shape (round-6 v2 2026-05-27)

For an internal MRI acquisition (Bruker ParaVision), the sidecar's `mri:` block aggregates the parsed JCAMP-DX aux files from the exam + the curated DICOM headers of every kept per-frame DICOM. Mirrors the `ni:` v2.1 shape — curated buckets + per-DICOM `dicoms[]` list with UIDs first + lossless `_raw_metadata`. **No source aux files are copied to disk under `/raw/`** (the parsed form here IS the gjesus3 preservation surface; the original files stay on the platform acquisition machine).

```json
"mri": {
  "subject": {
    "id", "name", "study_name", "type", "sex",
    "birth_date", "weight", "position", "entry",
    "study_datetime", "referral", "instance_uid"
  },
  "acquisition": {
    "method", "pulse_program", "creation_datetime",
    "echo_time_ms", "repetition_time_ms",
    "averages", "repetitions", "scan_time_str", "scan_time_ms",
    "nucleus", "frequency_mhz", "receiver_gain",
    "frame_count", "frame_group_desc"
  },
  "geometry": {
    "spatial_dim", "matrix", "fov",
    "slice_thickness", "core_dim", "core_size",
    "core_extent", "core_units", "orientation", "position"
  },
  "reconstruction": {
    "indices_present": ["1", "3"],
    "by_index": {
      "1": {
        "reco_mode", "fov", "size", "frame_count",
        "data_min", "data_max", "frame_type", "frame_group_elem_desc",
        "dicoms": [
          {
            "dst_basename": "recon1_frame01.dcm",
            "src_relpath":  "pdata/1/dicom/MRIm01.dcm",
            "headers": {
              "StudyInstanceUID", "SeriesInstanceUID", "SOPInstanceUID",
              "Modality", "Manufacturer", "ManufacturerModelName",
              "SeriesDescription", "StudyDescription",
              "StudyDate", "StudyTime", "AcquisitionDate", "AcquisitionTime",
              "SeriesDate", "SeriesTime",
              "ImageType", "Rows", "Columns", "NumberOfFrames",
              "PixelSpacing", "SliceThickness", "SpacingBetweenSlices",
              "InstanceNumber",
              "PatientID", "PatientName", "PatientSex", "PatientWeight",
              "MagneticFieldStrength", "EchoTime", "RepetitionTime",
              "FlipAngle", "ScanningSequence", "SequenceVariant"
            }
          }
        ]
      },
      "3": {
        "...same shape...",
        "dicoms": [ "...one entry per recon3_frame<NN>.dcm..." ]
      }
    }
  },
  "_raw_metadata": {
    "subject":   { ...parsed JCAMP-DX dump of study-root subject file... },
    "acqp":      { ...parsed dump... },
    "method":    { ...parsed dump... },
    "visu_pars": { ...parsed dump... },
    "pdata": {
      "1": { "visu_pars": {...}, "reco": {...} },
      "3": { "visu_pars": {...}, "reco": {...} }
    }
  }
}
```

Notes:
- **DICOM UIDs** (`StudyInstanceUID` / `SeriesInstanceUID` / `SOPInstanceUID`) are first in the curated headers — required for any DICOM-aware tool (XNAT, PACS, OMERO) that joins data on UIDs. All per-frame DICOMs from one pdata/recon share `SeriesInstanceUID`; the parent ParaVision exam corresponds to one `StudyInstanceUID`.
- **MRI-specific curated tags** (`MagneticFieldStrength`, `EchoTime`, `RepetitionTime`, `FlipAngle`, `ScanningSequence`, `SequenceVariant`) — beyond the standard tags NI captures, these are populated by Bruker's DICOM exporter and useful for distinguishing sequences.
- **Each kept DICOM gets a `dicoms[]` entry** under its recon: `dst_basename` (what it's named on gjesus3 under `<ACQ-ID>.data/`), `src_relpath` (original path inside the upstream ParaVision exam), and curated headers.
- **`_raw_metadata`** carries the parsed JCAMP-DX dicts for every aux file. The verbatim originals stay on the platform acquisition machine — the parsed dicts here are the gjesus3 preservation surface.
- **For no-DICOM acquisitions** (students who didn't run Bruker's exporter): all curated buckets and `_raw_metadata` are still populated from the JCAMP-DX. Each recon's `dicoms[]` list is empty. The `<ACQ-ID>.data/` folder is created empty.
- Buckets are best-effort summaries; if a field is missed, it's still recoverable from `_raw_metadata` without re-reading the source.
- Curated `discovered.mri_*` subset (surfaced for YAML reference) is documented in `tools/ingest/paravision_metadata.py::EXPOSED_FIELDS` and mirrored in [09_MODALITIES](09_MODALITIES.md) per the CLAUDE.md cross-reference rule.

#### `ni:` block shape (round-8 v2 2026-05-27)

For an internal NI acquisition (Molecubes archive-mode), the sidecar's `ni:` block aggregates content from the per-acquisition `protocol.txt`, the three XML aux files (`protocol.xml`, `acqparams.xml`, `recontemplate.xml`), and the DICOM headers of **every** `.dcm` kept on gjesus3 (one per reconstruction for CT, one per frame for PET/SPECT). Mirrors the `mri:` block design — curated buckets + lossless `_raw_metadata`. **No source aux files are copied to disk under `/raw/`** (the parsed form here IS the gjesus3 preservation surface; the original files live on the Molecubes platform archive).

```json
"ni": {
  "study": {
    "study_name", "series_name", "principal_investigator", "modality",
    "datetime", "datetime_raw"
  },
  "subject": {
    "animal_id", "weight_g"
  },
  "acquisition": {
    "scan_protocol", "bed_position_from", "bed_position_to",
    "record_respiratory", "record_cardiac",
    "isotope", "activity_MBq", "activity_calibrated_at",
    "remaining_activity_MBq", "remaining_activity_calibrated_at",
    "injected_at",
    "n_frames", "scan_duration_s",
    "dose"
  },
  "reconstruction": {
    "recons_present": ["0", "1", "2"],
    "by_index": {
      "0": {
        "algorithm", "iterations", "voxel_size", "energy_peak",
        "energy_win", "gatingtype",
        "dicoms": [
          {
            "dst_basename": "recon0.dcm",              // CT or PET static
            "src_relpath": "recon_0/<original_filename>.dcm",
            "headers": {
              "StudyInstanceUID", "SeriesInstanceUID", "SOPInstanceUID",
              "Modality", "Manufacturer", "ManufacturerModelName",
              "SeriesDescription", "StudyDescription",
              "StudyDate", "StudyTime", "AcquisitionDate", "AcquisitionTime",
              "SeriesDate", "SeriesTime",
              "ImageType", "Rows", "Columns", "NumberOfFrames",
              "PixelSpacing", "SliceThickness", "SpacingBetweenSlices",
              "ReconstructionDiameter", "Units",
              "PatientID", "PatientName", "PatientSex", "PatientWeight",
              "RadiopharmaceuticalInformationSequence"
            }
          },
          {
            "dst_basename": "recon0_frame1.dcm",       // PET/SPECT dynamic — per-frame
            "src_relpath": "recon_0/frame_1/iter_30/<original>.dcm",
            "headers": { ... ImageType ends 'VOLUME', NumberOfFrames = z-slices ... }
          },
          {
            "dst_basename": "recon0_frameMULTI.dcm",   // PET/SPECT dynamic — bundled all-frames
            "src_relpath": "recon_0/<original>_frameMULTI_iter30.dcm",
            "headers": { ... ImageType ends 'DYNAMIC', NumberOfFrames = z-slices × n_frames ... }
          }
        ]
      }
    }
  },
  "_raw_metadata": {
    "protocol_txt":      { "Study name": "0525", "Series name": "251029", ... },  // parsed dict
    "protocol_xml":      { ...nested parsed XML... },
    "acqparams_xml":     { "Acquisition/FOV_width": "37.4", ... },                 // flat key:value
    "recontemplate_xml": { "ReconstructionTemplate/algorithm": "ISRA", ... },      // flat key:value
    "reconparams_by_idx": {
      "0": { "Acquisition/...": "..." },                                           // per-recon flat key:value
      "1": { ... },
      "2": { ... }
    }
  }
}
```

Notes:
- **DICOM UIDs** (`StudyInstanceUID` / `SeriesInstanceUID` / `SOPInstanceUID`) are first in the curated headers — required for any DICOM-aware tool (XNAT, PACS, OMERO) that joins data on UIDs. PET/SPECT acquisitions of the same animal session share `StudyInstanceUID` across modalities (note: NOT shared with the corresponding CT, which is a separate study acquisition on the Molecubes platform — verify per case).
- **`protocol_txt` is a parsed dict** (verbatim keys from the source file like `"Study name"`, `"Date/time"`, `"Animal weight (g)"`). Every non-empty line is parsed (no allowlist) plus the special `"Scan bed position from X to Y"` line which has no colon — split into `"Scan bed position from"` and `"Scan bed position to"`. Was a verbatim string in the v1 round-8 design; the dict form makes the sidecar machine-queryable without re-parsing.
- **Each kept DICOM gets a `dicoms[]` entry** with its new flat filename (`dst_basename` — what it's named on gjesus3 under `<ACQ-ID>.data/`), its original source path inside the upstream archive (`src_relpath`), and its curated headers. CT acquisitions have one entry per recon; PET/SPECT have one per frame.
- **Multi-frame DICOMs are KEPT** (v2.1, 2026-05-27 update) — platform-generated bundled DICOMs (`frameMULTI` in the source filename) for dynamic PET/SPECT studies land on gjesus3 as `recon<X>_frameMULTI.dcm` alongside the per-frame DICOMs, appearing in the same `dicoms[]` list. Distinguishable by `ImageType` containing `'DYNAMIC'` (per-frame have `'VOLUME'`) and `NumberOfFrames` equal to the per-frame value × number of frames. Researchers and downstream tools can pick either representation. See [03_RAW_STORAGE §4.3](03_RAW_STORAGE.md) and equipment workflow notes for the v2 → v2.1 history.
- **`_raw_metadata`** carries the parsed forms of all 4 source aux files + each per-recon `reconparams.xml`. The verbatim originals stay on the platform archive — the parsed dicts here are the gjesus3 preservation surface.
- Per-modality acquisition fields are populated when present (e.g. `isotope`/`activity_MBq` for PET; empty for CT — the bucket handles missing fields gracefully by emitting `""`).
- Curated `discovered.ni_*` subset (surfaced for YAML reference) is documented in `tools/ingest/ni_metadata.py::EXPOSED_FIELDS` and mirrored in [09_MODALITIES](09_MODALITIES.md) NI section per the CLAUDE.md cross-reference rule.

---

## 5. Nanomaterial Imaging Considerations

For SEM/TEM imaging of nanomaterials (if included):

> **❓ EVALUATING:** ISA-TAB-Nano may be relevant for material characterization metadata.

| Standard | Relevance |
|----------|-----------|
| REMBI | Imaging parameters — still applicable |
| ISA-TAB-Nano | Material description — extends ISA for nanomaterials |

---

## 6. Related Documents

- [03_RAW_STORAGE](03_RAW_STORAGE.md) — Where metadata lives
- [06_REGISTRIES](06_REGISTRIES.md) — Core metadata fields
- [09_MODALITIES](09_MODALITIES.md) — Instrument-specific metadata
- [10_TOOLS](10_TOOLS.md) — Metadata extraction integrated into ingest workflow

---

## Open Questions

| ID | Question | Owner | Status |
|----|----------|-------|--------|
| META-01 | Complete REMBI field review with users | Data Mgmt Lead | ⚠️ Blocked on user input |
| META-02 | Audit embedded metadata per instrument | Data Mgmt Lead | ⚠️ Open |
| ~~META-03~~ | ~~Develop metadata extraction scripts~~ | — | ✅ Resolved: integrated into full-mode ingest; see [10_TOOLS](10_TOOLS.md). Implementation pending. |
| META-04 | ISA-TAB-Nano for nanomaterials? | Data Mgmt Lead | ❓ If SEM/TEM included |
