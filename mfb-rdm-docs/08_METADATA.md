# 08 — Metadata

**Parent:** [Documentation Index](00_INDEX.md)  
**Status:** 🔶 Draft  
**Last Updated:** 2026-06-03 (**Phase 3 enrichment writer IMPLEMENTED** — `subject:`/`condition:`/`anatomy:` are now written at ingest Step 8.4 via `tools/ingest/enrichment.py` + `metadata_sidecar.build_sidecar`, non-blocking per §4.7; deferred-recovery pending list `registries/pending_subject_metadata.csv` (`tools/ingest/pending.py`) + superuser recovery `tools/recover_subject_metadata.py`; standalone read-only tools `gather_metadata.py` / `validate_registries.py` / `verify_checksums.py` / `metadata_completeness.py`. Status tables §4.4.5/§4.5.5/§4.6.4 + §4.7.4 flipped to IMPLEMENTED; backfill + registry `subject_id`/`anatomical_entity` columns stay deferred. Earlier same-day: **Non-blocking metadata model §4.7** — `subject:`/`condition:`/`anatomy:` NEVER block ingest; `is_control` + `is_whole_body` softened from hard-required to tri-state recommended-WARN (`true`/`false`/`null`), set-once-per-batch propagation, best-effort auto, bulk enrichment later, archive data ingests with guesses/unknown. NEW `anatomy:` §4.6 (`is_whole_body` + UBERON `region`); animal-DB explored + Subject/Sample identity model → `subject:` §4.4 (`facility_animal_id` reused subject id, `procedures` STRUCTURED, META-07 retired); identity model in [06_REGISTRIES §2.3](06_REGISTRIES.md). Prior: 2026-06-02 DOB + deferred-recovery §4.4.6)

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
  "subject":       { ... },                       // when sample_type ∈ {organism, tissue} — see §4.4
  "condition":     { ... },                       // when sample_type ∈ {organism, tissue} — see §4.5 (is_control tri-state, non-blocking)
  "anatomy":       { ... },                       // when sample_type = organism (in-vivo NI/MRI) — see §4.6 (is_whole_body tri-state, non-blocking)
  "<ecosystem_section>": { ... }
}
```

| Section | Source |
|---------|--------|
| `user_supplied` | The resolved values from the YAML `registry:` block (literal text, `discovered.<x>` references, or `${...}` interpolation — see [10_TOOLS §2.1](10_TOOLS.md)). |
| `discovered` | Everything `auto_discover` surfaced for the case: filename-parser output, parent-folder date, `folder_name` / `filename`, and embedded extracts (`discovered.czi_*` for microscopy, `discovered.mri_*` for ParaVision). |
| `subject` (when `sample_type ∈ {organism, tissue}`) | DRAFT 2026-05-29, extended 2026-06-03. Preclinical subject metadata: `facility_animal_id` (the reused canonical **subject id**) + species / strain / sex / date_of_birth → derived age_at_acquisition (required) + optional genotype / weight / cohort_id / **structured** procedures `[{type,date}]`. **Per-subject, fixed.** Source: animal-facility-DB > study-level YAML > instrument auto-extracts. On ingest-time DB miss / no-credentials, written as `source: "pending-db"` and queued for superuser recovery (§4.4.6). See §4.4. |
| `condition` (when `sample_type ∈ {organism, tissue}`) | DRAFT 2026-05-29; **non-blocking** 2026-06-03. Disease state + experimental role: `is_control` (highly-recommended **tri-state** `true`/`false`/`null` — WARN if null, never blocks), `disease_model` + `disease_state` (recommended free-text) + optional `control_type` / `treatment` / `timepoint_days` / `study_arm`. **Per-acquisition; set once per batch/session.** Source: operator-entered; `disease_model` auto-seeds from DB `projects.name`. See §4.5 + §4.7. |
| `anatomy` (when `sample_type = organism`) | DRAFT 2026-06-03; **non-blocking**. Anatomical coverage of an in-vivo scan: `is_whole_body` (highly-recommended **tri-state** — WARN if null, never blocks — the dead-simple full-body-vs-ROI flag) + UBERON-coded `region` (recommended when not whole-body) + optional `additional_regions` / `auto_hint`. **Per-acquisition.** Source: operator-entered (not in the animal-DB; DICOM `BodyPartExamined` empty upstream); optional non-authoritative auto-hint from MRI ProtocolName+FOV / NI bed-range. See §4.6 + §4.7. |
| `<ecosystem_section>` | The structured embedded-metadata block keyed by ecosystem subfield: `microscopy` (for .czi), `mri` (for Bruker ParaVision — new 2026-05-20). Each has curated buckets at the top for human skimming + a `_raw_metadata` dump for forensic preservation. |

> **✅ Enrichment writer IMPLEMENTED (Phase 3, 2026-06-03).** The `subject:` / `condition:` / `anatomy:` blocks above are no longer planned-only — they are written at ingest. New orchestrator `tools/ingest/enrichment.py` (`build_enrichment`) is called from `ingest_raw.py` **Step 8.4** and its result is nested by `metadata_sidecar.build_sidecar(... subject=, condition=, anatomy=)` in the key order `acq_id, generated, generator, user_supplied, discovered, subject, condition, anatomy, <ecosystem_section>`. The writer is **non-blocking** (§4.7): it never raises on missing data, writing explicit sentinels (`is_control`/`is_whole_body` `null`, free-text `""`, `source: "unknown"` or `"pending-db"`) + a WARN. Supporting modules: `ingest/subject_id.py` (short-code parser `m13→13`, `ID13B→13`+organ; project-alias from `project_hint`), `ingest/pending.py` (the deferred-recovery pending list, §4.4.6), `ingest/resolver.py` (validate/resolve for `condition`/`anatomy`/`subject`/`subject_lookup`/`subject_from_db` + `to_tristate`/`to_number` coercers), and the animal-facility-DB lookup `tools/animal_db.py`. The YAML surface that feeds it (`auto_discover.subject_from_db` + `subject_lookup:`, top-level `condition:` / `anatomy:` / optional `subject:`) is documented in [10_TOOLS §2.1](10_TOOLS.md). The per-block status tables (§4.4.5 / §4.5.5 / §4.6.4) still mark **backfill of existing acqs** and the **registry `subject_id` / `anatomical_entity` columns** as deferred to the true-production restart — only the *writer* shipped.

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

### 4.4 `subject:` Block — Preclinical Subject Metadata (DRAFT 2026-05-29)

> **🔶 DRAFT (2026-05-29; extended 2026-06-02 after animal-facility-DB access; identity model + DB exploration 2026-06-03).** New top-level `subject:` block in `metadata.json` for acquisitions whose subject is an organism or organism-derived tissue. The **required fields** (`species` / `strain` / `sex` / `date_of_birth` → derived `age_at_acquisition`) are **✅ DECIDED** — universal preclinical reporting standards (ARRIVE 2.0, EU Directive 2010/63/EU, NIH Sex-As-Biological-Variable policy). They are sourced from the **animal-facility DB** (`animal_facility` MariaDB schema, explored 2026-06-02). `facility_animal_id` is the **subject identifier** — the facility's canonical `<animal_code>-AE-biomaGUNE-<NNNN>` reused verbatim (the Subject/Sample identity model is in [06_REGISTRIES §2.3](06_REGISTRIES.md)). `procedures` is a **structured `[{type,date}]` list** from the DB's controlled vocabulary, not free text (§4.4.7). **Required-eventually, not at-ingest:** because the DB may lag the acquisition or credentials may be absent, a DB miss WARNs and queues the acquisition for superuser recovery rather than failing the ingest — the deferred-recovery mechanism is §4.4.6.

#### 4.4.1 When this block is required

Whenever `registry_raw.csv` has `sample_type ∈ {organism, tissue}` (see [06_REGISTRIES §2.4](06_REGISTRIES.md)). In current scope:

- **Always required** for internal MRI and Nuclear Imaging (sample_type = `organism`).
- **Required when applicable** for AxioScan 7 / Cell Observer / LSM 900 microscopy — i.e. whenever the imaged tissue or cell preparation originated from an animal (the typical case in this group). Not required for non-biological samples (`material`, `phantom`) or non-animal-derived `cells`.

#### 4.4.2 Schema

```json
"subject": {
  "facility_animal_id":       "13-AE-biomaGUNE-0525",  // the SUBJECT ID — animal-facility canonical animal ID, reused verbatim (<animal_code>-AE-biomaGUNE-<NNNN>). The DB lookup key + the link every animal acquisition carries. See identity model in 06_REGISTRIES §2.3.
  "species":                  "Mus musculus",       // REQUIRED — scientific binomial. DB stores common name ("Mouse"/"Rat" in specie.type) → writer normalizes (Mouse→Mus musculus, Rat→Rattus norvegicus).
  "strain":                   "C57BL/6J",           // REQUIRED — from strain.type (proper nomenclature, e.g. "Crl:WI(Han)"). DB also offers strain.aka (alias) + strain.tg (transgenic flag → genotype hint).
  "sex":                      "M",                  // REQUIRED — M | F | unknown. DB stores "Male"/"Female" (animals.sex) → writer normalizes.
  "date_of_birth":            "2025-07-31",         // REQUIRED — ISO-8601 date; the DB's authoritative birth date (animals.date_of_birth, native DATE).
  "age_at_acquisition":       "P12W",               // REQUIRED — DERIVED by the writer = acquisition_datetime − date_of_birth, emitted as ISO-8601 duration. Free-text "12 weeks" accepted only when date_of_birth is unavailable.
  "genotype":                 "WT",                 // optional but recommended (WT | KO:<gene> | TG:<construct> | Cre:<driver> | ...); strain.tg can seed this.
  "weight_at_acquisition_g":  24.3,                 // optional — numeric grams (instrument-recorded preferred; DB animals.weight is entry-weight, usually empty).
  "cohort_id":                "AE-0424-cohort-A",   // optional — experimental cohort grouping
  "procedures":               [                     // optional — STRUCTURED list from the DB's 80-value controlled vocab (animal_procedures → procedures.type + date). NOT free text. See §4.4.7.
    {"type": "MRI", "date": "2025-10-29"},
    {"type": "Tail vein injection", "date": "2025-10-29"}
  ],
  "source":                   "animal-facility-db"  // DRAFT — provenance: animal-facility-db | operator-entered | bruker-auto-extracted | molecubes-auto-extracted | pending-db
}
```

> **Note — `anatomical_entity` is a *sample*-level field, not a subject field.** For tissue acquisitions the organ (e.g. the `B` in `ID13B`) describes the *specimen*, not the animal; it lives with the sample (registry `anatomical_entity` column at the restart; sidecar meanwhile). See the Subject/Sample identity model in [06_REGISTRIES §2.3](06_REGISTRIES.md). `facility_animal_id` above is the **subject identifier**; `sample_id` is the sample identifier; they coincide only for in-vivo (`organism`) acquisitions where the animal *is* the sample.

> **Required-eventually, not required-at-ingest.** Unlike `condition.is_control` (§4.5, hard-blocks the sidecar write if missing), the DB-sourced `subject:` required fields are **required-to-eventually-be-present** rather than required-at-ingest. The animal-facility DB may not yet hold the animal at acquisition time (see §4.4.6 on the timing delay), and the operator's machine may lack DB credentials — failing the ingest in either case is operationally unacceptable (data must land when it is acquired). Instead the ingest WARNs, writes a placeholder `subject:` block (`source: "pending-db"`), and logs the acquisition to a pending list for a superuser to recover later. The deferred-recovery mechanism is §4.4.6.

#### 4.4.3 Source hierarchy

When the sidecar is built, `subject:` is populated from the highest-confidence source available:

1. **Animal facility DB** — authoritative. **Explored 2026-06-02** (MariaDB `animal_facility` schema; read-only via `~/.my.cnf`). Lookup = `projects.projectAlias = <NNNN>` (from `project_hint` `ae-biomegune-NNNN`) + `animals.animal_code` (the leading number of the instrument short code, `m13`→`13`); returns species/strain/sex/DOB + the structured `procedures` list. Set `source: "animal-facility-db"`. When the DB lookup at ingest fails (animal not yet in the DB, or no credentials on the operator's machine), fall through to the deferred-recovery path (§4.4.6) — write `source: "pending-db"` and queue for superuser recovery, rather than dropping straight to the lower-confidence sources below.
2. **Study-level metadata** at `/projects/<proj>/metadata/subjects.yaml`, keyed by `sample_id` (operator-entered via the Excel importer when it ships). Set `source: "operator-entered"`.
3. **Instrument auto-extracts** — last-resort fallback from the existing `_raw_metadata` extracts:
   - ParaVision: `mri._raw_metadata.subject.SUBJECT_sex` / `SUBJECT_weight` / `SUBJECT_type` / `SUBJECT_id` (often partially populated; species/strain/age typically empty unless the user entered them in ParaVision's subject form).
   - Molecubes: `ni._raw_metadata.protocol_txt["Animal ID"]` / `"Animal weight (g)"` (no species/strain/sex/age fields in the Molecubes form).
   - Set `source: "bruker-auto-extracted"` or `"molecubes-auto-extracted"`.

The sidecar holds a **frozen snapshot** at ingest time, refreshed at project close-out before the `/projects/<proj>/` folder is deleted (see [§1.3](#13-permanent-vs-ephemeral-storage)). The mutable source-of-truth during the project's life lives at `/projects/<proj>/metadata/subjects.yaml`; the sidecar copy is what survives close-out into `/raw/`.

#### 4.4.4 Why these required fields

The required fields (species / strain / sex / date_of_birth → derived age_at_acquisition) are the minimum reporting standard for any publishable preclinical imaging work. Capturing **`date_of_birth`** rather than a hand-typed age means age is computed and verifiable (acquisition_datetime − DOB) instead of transcribed:

| Standard | Requirement |
|---|---|
| **ARRIVE 2.0** (Animal Research: Reporting of In Vivo Experiments) | Species, strain/sub-strain, sex, age/developmental stage are mandatory in the "Essential 10" reporting items. Required by most biomedical journals. |
| **EU Directive 2010/63/EU** | Species + strain/stock, sex, age at procedure are mandatory record-keeping fields. |
| **NIH Sex As a Biological Variable** policy (2016+) | Sex is non-negotiable for NIH-funded preclinical work. |

Capturing these four fields at ingest time — rather than recovering them later from researchers' notebooks — is the single highest-leverage metadata investment for preclinical data on gjesus3.

#### 4.4.5 Status & implementation

| Aspect | Status |
|---|---|
| Required-fields schema (species / strain / sex) | ✅ DECIDED (2026-05-29) |
| `date_of_birth` required + `age_at_acquisition` derived from it | ✅ DECIDED — DB field confirmed `animals.date_of_birth` (native DATE), 2026-06-02 |
| `facility_animal_id` = canonical subject ID `<animal_code>-AE-biomaGUNE-<NNNN>` (reused) | ✅ DECIDED 2026-06-03 — Subject/Sample identity model, [06_REGISTRIES §2.3](06_REGISTRIES.md) |
| species/sex normalization (`Mouse`/`Rat`→binomial; `Male`/`Female`→M/F) | ✅ DECIDED 2026-06-03 — writer-side normalization (confirmed DB values) |
| `procedures` structured `[{type,date}]` from DB controlled vocab | ✅ DECIDED optional (2026-06-03) — NOT free text; §4.4.7. **META-07 retired** |
| `source:` provenance tag values | 🔶 DRAFT |
| `subject:` writer | ✅ IMPLEMENTED (Phase 3, 2026-06-03) — `tools/ingest/enrichment.py::build_enrichment`, nested by `metadata_sidecar.build_sidecar`, called from `ingest_raw.py` Step 8.4; non-blocking (§4.7) |
| Animal-facility-DB fetcher (`tools/animal_db.py`) | ✅ IMPLEMENTED — read-only lookup via `~/.my.cnf` + pymysql; injectable into the writer (fail-soft without credentials) |
| Deferred-recovery pending list + superuser retro-update | ✅ IMPLEMENTED (2026-06-03) — pending list `registries/pending_subject_metadata.csv` written by `tools/ingest/pending.py`; superuser retro-update `tools/recover_subject_metadata.py` (dry-run by default). Design in §4.4.6 |
| Registry `subject_id` + `anatomical_entity` columns | 🔶 DEFERRED to true-production restart (Option B) — sidecar carries them meanwhile; [06_REGISTRIES §2.3](06_REGISTRIES.md) |
| Backfill of existing 97 MRI + 84 NI acqs + animal-derived microscopy | ⚠️ Queued — `tasks/tasks.md §3.2` Phase 4 |

Until the animal-DB integration lands, operators may set `subject:` manually via study-level YAML (once the Excel importer ships) or fall back to whatever the instrument auto-extracted into `_raw_metadata`.

### 4.4.6 Deferred recovery — ingest-time DB miss + superuser retro-update (DRAFT 2026-06-02)

> **🔶 DRAFT (2026-06-02).** The animal-facility DB is authoritative for the `subject:` required fields, but it is not always queryable *at the moment of ingest*. Two failure modes must not block an ingest, yet must not silently lose the metadata either. This section specifies the catch-and-recover mechanism.

#### 4.4.6.1 The two ingest-time failure modes

| Mode | Cause | Why it happens |
|---|---|---|
| **DB-miss (timing delay)** | The animal (or some of its fields) is not yet in the DB when the data is ingested. | Going forward, researchers ingest **right after acquisition**, which can precede the animal-facility staff updating the DB for that animal/procedure. (The current archival/historical backfills don't hit this — the DB is already fully populated for past studies — but live ingests will.) |
| **No-credentials** | The operator's machine has no DB credentials. | DB access is credential-gated; not every operator workstation will hold them. |

In **both** cases the ingest must **WARN, not fail** — the acquisition still lands in `/raw/` with a placeholder `subject:` block (`source: "pending-db"`, required fields blank or best-effort from instrument auto-extracts) — and the acquisition is appended to a pending list for later recovery.

#### 4.4.6.2 The pending list

**Location:** `registries/pending_subject_metadata.csv` (on the NAS, under the container `gjesus3-data/registries/`).

**Why `registries/` and not `raw/`:** under the applied permission model ([11_OPERATIONS §2.1.1](11_OPERATIONS.md)), operators have **Modify on `registries/`** (the ingest already appends rows to `registry_raw.csv` there) but only **write-but-not-modify on `raw/`**. The pending list is written by the operator's ingest at acquisition time, so it has to live where the operator can append — `registries/` is the only such place. (This is the same reason the *recovery* step must be a superuser — see §4.4.6.4.)

**Proposed columns** (DRAFT — finalize alongside the writer):

| Column | Meaning |
|---|---|
| `acq_id` | The acquisition needing recovery |
| `sidecar_path` | Canonical path to the `/raw/.../metadata.json` to be updated |
| `facility_animal_id` | The DB lookup key (may be blank if even that wasn't known at ingest) |
| `reason` | `db-miss` \| `no-credentials` |
| `logged_at` | ISO-8601 UTC timestamp of the ingest that logged the gap |
| `status` | `pending` \| `recovered` \| `unresolvable` (set by the recovery tool) |
| `recovered_at` | ISO-8601 UTC timestamp when a superuser resolved it (blank until then) |

Entries are idempotent on `acq_id` — re-ingesting the same acquisition updates the existing row rather than duplicating it.

#### 4.4.6.3 What the operator sees

A clear WARN at ingest, e.g.:

```
WARN  ACQ-20260602-MRI-014: subject metadata not recovered from animal-facility DB
      reason=db-miss (animal MFB-2025-0420-m17 not found)
      → logged to registries/pending_subject_metadata.csv for superuser recovery
      → acquisition ingested with placeholder subject: block (source=pending-db)
```

The ingest exit status stays success. Nothing about the gap is hidden — the pending list is the running, human-readable record of every acquisition still owing subject metadata.

#### 4.4.6.4 Superuser retro-update

A separate tool (superuser-run; tracked in `tasks/tasks.md §3.2`) walks `registries/pending_subject_metadata.csv`, and for each `status: pending` row:

1. Looks up `facility_animal_id` in the animal-facility DB (now populated / now with credentials).
2. If found, **modifies the `/raw/.../metadata.json` sidecar in place** — fills the `subject:` required fields, sets `source: "animal-facility-db"`, recomputes `age_at_acquisition` from `date_of_birth` + the acquisition datetime.
3. Marks the row `recovered` with `recovered_at`; leaves still-missing animals as `pending` (or `unresolvable` after a human decision).

**This step requires a superuser** because it **modifies an existing file under `/raw/`**, which the permission model forbids to operators and ordinary users (they are write-once / read-only on `raw/`; only superusers hold Full). It is the same controlled-write-to-`/raw/` pattern as the project close-out merge (§1.5a) and shares its safeguards (verify-after-write; never overwrite acquisition-level fields that were already correct).

This is a forward-only mechanism: the historical/archival backfills in progress now do **not** generate pending entries (the DB is already complete for past studies), but every live post-acquisition ingest is covered the day it starts.

### 4.4.7 `procedures` — structured, from the DB's controlled vocabulary (DRAFT 2026-06-02, revised after exploration)

> **🔶 DRAFT 2026-06-02; revised 2026-06-03 after DB exploration.** We expected a free-text procedures log; the DB exploration showed the opposite — procedures are **already structured**. `animal_procedures` (91,617 rows) links each animal to an **80-value controlled vocabulary** (`procedures.type`: `MRI`, `PET`, `SPECT`, `Surgery`, `Tail vein injection`, `RT administration + perfusion`, `Ischemia surgery`, `Organ sampling`, …) **with a date per entry**.

**What is decided:**
- `subject.procedures` is an **optional, structured list** `[{type, date}, …]`, copied directly from the DB join `animal_procedures → procedures.type` (+ `date`). No parsing, no inference, lossless and already queryable.

**META-07 (the LLM-tagging question) is largely retired.** The earlier worry — that procedures would be free text needing a manual-vs-LLM tagging step to become queryable — doesn't apply: the systematic tags we wanted to *derive* already exist as the DB's controlled vocab. There is nothing to parse. We simply carry the structured list.

**Residual (small):** if a *free-text procedural note* is ever wanted beyond the controlled vocab, the candidate source is `animal_observations` (13,329 rows) — a separate, genuinely free-text table not pulled today. Only then would the manual-vs-LLM-tagging discussion reopen; until a concrete need arises it stays out of scope. The verbatim controlled-vocab list remains canonical (same preserve-then-interpret principle as the REMBI projection deferral, §3.5).

### 4.5 `condition:` Block — Disease State and Experimental Role (DRAFT 2026-05-29)

> **🔶 DRAFT (2026-05-29; non-blocking model adopted 2026-06-03).** New top-level `condition:` block in `metadata.json` capturing the disease/control state of each acquisition. Sister block to §4.4 `subject:`; same trigger condition (`sample_type ∈ {organism, tissue}`).
>
> **⚠️ Non-blocking (revised 2026-06-03 — see the unified model in §4.7).** Nothing in this block ever blocks ingest. `is_control` is **highly recommended, not required** — it is **tri-state** `true | false | null` (where `null` = unknown), defaults to `null` when unsupplied, and the writer **WARNs** (never raises) if it is `null` for an organism/tissue acquisition. This reverses the earlier "DECIDED-required hard-block": a hard-block punished archive data and the realistic operator (who can barely supply a folder name), and "data + a guess" beats refusing the ingest.
>
> **Recommended/Optional split:**
> - **`is_control`** — highly recommended tri-state boolean (`true`/`false`/`null=unknown`). WARN if `null`. The primary cohort filter when present.
> - **`disease_model` / `disease_state`** — recommended free-text; WARN if missing **for a case** (see the control definition below). `disease_model` can be **pre-seeded** from the animal-DB `projects.name` (a project-level hint — see §4.5.4).
> - **Optional** (`control_type` / `treatment` / `timepoint_days` / `study_arm`) — write-through, no validation.

> **Definition of *control* (`is_control = true`) — DECIDED 2026-06-08.** A control is an animal with **no disease model, no perturbation, and no intervention** (naive / wild-type / untreated baseline). It follows that a control has no `disease_model` or `disease_state` to record — those characterize a **case** (`is_control = false`). The enrichment writer is therefore **gate-aware**: it WARNs about an empty `disease_model`/`disease_state` only for a *case*, never for a control (a control's empty disease fields are correct, not a gap). `control_type` (naive / sham / vehicle / littermate / …) optionally refines *what kind* of control it is.

#### 4.5.1 Why this is its own block (not folded into `subject:`)

| | `subject:` | `condition:` |
|---|---|---|
| **What it answers** | "Who is this animal?" | "What study state is this acquisition?" |
| **Variation** | Per-subject, fixed | Per-acquisition, varies (same animal at baseline + post-treatment) |
| **Source** | Animal-facility-DB (auto) > study YAML > instrument extracts | Operator-entered via per-batch YAML or `/projects/<proj>/metadata/`; `disease_model` can be pre-seeded from the DB `projects.name`, but `is_control` is not in the DB |
| **Recommended for** (non-blocking) | `sample_type ∈ {organism, tissue}` | `sample_type ∈ {organism, tissue}` |

Folding into `subject:` would conflate two different source pipelines (DB-auto vs. operator-only) and obscure the per-acquisition semantics.

#### 4.5.2 Schema

```json
"condition": {
  "is_control":        true,                    // HIGHLY RECOMMENDED — tri-state: true (control) | false (case/disease) | null (unknown). null = "not yet determined" (default when unsupplied); WARN, never block. Primary cohort filter.
  "disease_model":     "wild_type",            // RECOMMENDED — constitutive disease/model classification, OR "wild_type" / "non_transgenic" for naive animals. May be pre-seeded from the DB projects.name.
  "disease_state":     "baseline",              // RECOMMENDED — state at scan time. Free-text. Examples: "baseline", "day_7_post_MI", "endpoint", "6mo_AD_phenotype", "MPTP_day_21", "post_treatment_day_3"
  "control_type":      "naive",                 // optional (only meaningful when is_control=true): "naive" / "sham" / "vehicle" / "littermate" / "untreated_baseline"
  "treatment":         null,                    // optional free-text: e.g. "vehicle", "drug_X_5mg/kg_IP_day_0", "MI_LAD_ligation"
  "timepoint_days":    0,                       // optional numeric — days from study start or from intervention
  "study_arm":         "control_naive",         // optional — explicit experimental-arm label for cohort grouping
  "source":            "operator-entered"       // provenance / confidence: "operator-entered" | "study-yaml" | "imported-from-excel" | "auto-guess" (e.g. disease_model from project name) | "unknown"
}
```

Missing/unsupplied fields are written explicitly: `is_control: null`, free-text fields `""`, `source: "unknown"`. The block is always present for organism/tissue acquisitions — never omitted, never blocking.

#### 4.5.3 Query patterns this enables

| Query | Filter |
|---|---|
| All healthy controls | `condition.is_control == true` |
| All disease X scans | `condition.disease_model` contains `"X"` |
| Wild-type baseline | `disease_model == "wild_type" AND disease_state == "baseline"` |
| Post-MI day 7 cases | `disease_state contains "day_7" AND is_control == false` |
| All vehicle controls | `is_control == true AND control_type == "vehicle"` |

`is_control == true` / `== false` are the primary "needle in a haystack" filters; `null` (unknown) is simply excluded from both and surfaces in the completeness report (§4.7) as a gap to fill.

#### 4.5.4 Source: mostly operator-entered, with a project-level auto-seed — set once, propagate

The disease/control state is largely a property of the **study design**, not the animal — the same animal can be a baseline-scan control on day 0 and a post-MI case on day 7. The DB cannot fully supply it (the `animals.exp_group` group-link is unpopulated), but `projects.name` gives a usable **project-level `disease_model` hint** (e.g. *"…hipertensión pulmonar"* → `disease_model` seed). Set it via, in precedence order:

1. **Operator front-end at ingest — `ni-ingest` / `mri-ingest` (2026-06-08).** The simplest path for the Linux command-line operators: pass `--is-control true|false`, `--disease-model`, `--disease-state` and `--is-whole-body true|false` (the latter feeds the §4.6 `anatomy:` block), **or omit them and answer the interactive prompts** the tool shows before ingest. Set **once per run**, applied to every acquisition in the batch (the prompt banner says so, and warns to skip if the answer is not consistent across the batch). Disease fields are asked only for a **case** (`--is-control false`) and are optional — a blank leaves the sentinel, non-blocking. See `tools/INGEST_CLI.md`. The **microscopy GUI** has the equivalent per-run *Study metadata* panel for **tissue** instruments (AxioScan): the same `condition.*` values, typed or mapped from a CZI `discovered.*` field; the cell modes (Cell Observer / LSM 900) are `sample_type: cells` with no `condition:` block, so the panel is hidden for them. `anatomy.is_whole_body` is **not** offered in microscopy — it is an in-vivo (`organism`) concept.
2. **Per-batch YAML `condition:` block** (the data-office path) — **set once, applies to every acquisition the batch produces.** The operator (or Ryan) supplies the condition **once per ingest batch / session**, never per scan. A batch is typically one session or one animal-cohort's worth of scans, so one block covers them all.
   ```yaml
   condition:
     is_control: true            # tri-state; omit to leave null=unknown
     disease_model: "wild_type"
     disease_state: "baseline"
   ```
3. **Per-acquisition override** in `/projects/<proj>/metadata/<acq_id>.json` — only for the rare batch that genuinely mixes conditions; not the default.
4. **Project-level auto-seed** — `disease_model` pre-filled from the DB `projects.name` (`source: "auto-guess"`), overridable.
5. **Excel → study-metadata importer** (`tasks/tasks.md §3.2`) — researcher-driven bulk fill at the study level, the main tool for enriching archive data after the fact.

If none supply it, the block is still written with `is_control: null` + `source: "unknown"` and a WARN — the acquisition ingests and is flagged for later enrichment (§4.7). The sidecar holds a **frozen snapshot at ingest**, refreshed at project close-out before `/projects/<proj>/` deletion. Same lifecycle as `subject:`.

#### 4.5.5 Status & implementation

| Aspect | Status |
|---|---|
| `is_control` (tri-state `true`/`false`/`null`) | ✅ DECIDED highly-recommended, **non-blocking** (revised 2026-06-03) — writer WARNs if `null`, never refuses |
| `disease_model` + `disease_state` (free-text) | 🔶 Recommended — writer WARNs if missing, proceeds. `disease_model` auto-seed from `projects.name` |
| Optional fields (`control_type` / `treatment` / `timepoint_days` / `study_arm`) | 🔶 DRAFT, write-through |
| Controlled vocabulary for `disease_model` / `disease_state` | ❓ Deferred — preclinical model vocabularies are too domain-specific to fully control. Future: per-PI vocabularies in `/projects/<proj>/metadata/vocab.yaml`. |
| Writer | ✅ IMPLEMENTED (Phase 3, 2026-06-03) — `tools/ingest/enrichment.py`, called from `ingest_raw.py` Step 8.4; WARN-not-raise (§4.7) |
| YAML-level `condition:` block support in per-batch configs | ✅ IMPLEMENTED — top-level `condition:` block, resolver-evaluated, set-once-per-batch; in the per-instrument templates (`mri_bruker`, `molecubes_ni`, `axioscan7`) |
| Operator-CLI capture (`ni-ingest` / `mri-ingest` `--is-control` / `--disease-model` / `--disease-state` / `--is-whole-body`, or interactive prompts) | ✅ IMPLEMENTED (2026-06-08) — `tools/operator/metadata_prompt.py`; set once per run, applied to all acquisitions; disease fields gated to cases + optional; gate-aware WARNs (no disease nag for a control) |
| Backfill of existing 97 MRI + 84 NI + animal-derived microscopy | ⚠️ Queued — Phase 4; ingests now with `null`+WARN, enriched later via the Excel importer / bulk tools (§4.7) |

Until the writer ships, operators may include a `condition:` block in YAML configs as forward-compatible documentation; the loader will pick it up once Phase 3 lands.

### 4.6 `anatomy:` Block — Anatomical Coverage and Region (DRAFT 2026-06-03)

> **🔶 DRAFT (2026-06-03).** New top-level `anatomy:` block in `metadata.json` capturing **what part of the body an in-vivo scan covers**. Required for biomedical-imaging acquisitions of a whole organism (`sample_type = organism` — internal MRI + Nuclear Imaging). Answers the headline question *"is this a full-body scan or a region of interest?"* with a dead-simple boolean, plus an ontology-coded region for the detail.
>
> **⚠️ Non-blocking (2026-06-03 — same unified model as `condition:`, see §4.7).** Nothing here blocks ingest.
> - **`is_whole_body`** — highly recommended, **tri-state** `true | false | null` (`null` = unknown), defaults to `null`; the writer **WARNs** (never raises) if `null` for an `organism` acquisition. Sister of `condition.is_control`; the dead-simple full-body-vs-ROI filter when present.
> - **`region`** — recommended UBERON-coded term when `is_whole_body = false`; WARN if missing, never block.
> - **Optional:** `additional_regions`, `auto_hint`.
>
> (Reverses the earlier "DECIDED-required hard-block" — archive scans and the can-barely-name-a-folder operator must still ingest; a guess or `null` beats refusing the data.)

#### 4.6.1 Why its own block, and why operator-entered

Anatomical coverage is a property of the **imaging acquisition** (the field of view / bed range), not of the animal (`subject:`) and not of the study design (`condition:`) — so it is its own acquisition-level block in `/raw/` (immutable). It **cannot be reliably auto-derived** (established 2026-06-03 by inspecting real MRI + NI data):

| Candidate source | Verdict |
|---|---|
| Animal-facility DB | ❌ No region/coverage field (its `procedures` are interventions/modalities). |
| DICOM `BodyPartExamined` (0018,0015) | ❌ Empty in every Bruker (MRI) and Molecubes (NI) DICOM we hold — the standard tag isn't populated upstream. |
| MRI `ProtocolName` (e.g. `1_Localizer_multi_slice`) + FOV geometry | 🔶 Weak hint only — anatomy sometimes in the protocol name; coverage loosely inferable from FOV. |
| NI Molecubes bed-position range (`Scan bed position from X to Y`) + scan duration | 🔶 Weak hint only — more bed positions ≈ more axial coverage. |

So `anatomy:` is **operator-entered** (like `condition:`), with an *optional, non-authoritative* `auto_hint` the ingest may surface from the protocol name / bed range / FOV to pre-fill the operator's choice. The MRI/NI operator front-ends collect `is_whole_body` at ingest (the `--is-whole-body true|false` flag or an interactive prompt, 2026-06-08, set once per run); the UBERON `region` is **not** prompted there — when `is_whole_body = false` it is left `null` (WARN) and filled later via the per-acq metadata override, because a region needs a label + ontology id that don't belong in the dead-simple capture path.

#### 4.6.2 Schema

```json
"anatomy": {
  "is_whole_body": false,                          // HIGHLY RECOMMENDED — tri-state: true | false | null (unknown). Default null when unsupplied; WARN, never block. The dead-simple full-body-vs-ROI flag.
  "region": {                                      // RECOMMENDED when is_whole_body=false — the anatomical region, UBERON-coded. null when unknown.
    "label":    "brain",
    "ontology": "UBERON",
    "id":       "UBERON:0000955"
  },
  "additional_regions": [],                        // optional — extra UBERON terms when a scan spans more than one named region (e.g. thorax + abdomen)
  "source":    "operator-entered",                 // provenance / confidence: operator-entered | study-yaml | auto-hint-confirmed | auto-guess | unknown
  "auto_hint": "protocol:1_Localizer_multi_slice; fov_mm:[50,50]"  // optional, non-authoritative — surfaced from instrument metadata to assist/pre-fill the operator
}
```

For a **whole-body** scan: `is_whole_body = true`; `region` may be the whole-organism term `UBERON:0000468` ("multicellular organism") or left null. For a **regional** scan: `is_whole_body = false` and `region` carries the specific structure. **When unknown** (archive data, no operator input): `is_whole_body: null`, `region: null`, `source: "unknown"` — the block is still written and the scan ingests; the gap surfaces in the completeness report (§4.7).

**Ontology = UBERON** (Uberon cross-species anatomy ontology, OBO Foundry). Chosen because it is **species-agnostic** (covers Mouse *and* Rat — both present in our colony — plus human), has resolvable PIDs (`http://purl.obolibrary.org/obo/UBERON_0000955`), is REMBI-aligned ("use a relevant ontology"), and **harmonizes with the tissue-side `anatomical_entity`** from the Subject/Sample identity model ([06_REGISTRIES §2.3](06_REGISTRIES.md)) — both reference UBERON, so anatomy is queryable uniformly across in-vivo scans and ex-vivo sections.

**Verified UBERON starter set** (2026-06-03 via EBI OLS; extend per study at implementation):

| Region | UBERON id |
|---|---|
| whole organism (whole-body) | `UBERON:0000468` |
| brain | `UBERON:0000955` |
| heart | `UBERON:0000948` |
| lung | `UBERON:0002048` |
| thoracic cavity | `UBERON:0002224` |
| abdomen | `UBERON:0000916` |

#### 4.6.3 Query patterns this enables

| Query | Filter |
|---|---|
| **All full-body scans** | `anatomy.is_whole_body == true` |
| **All region-of-interest scans** | `anatomy.is_whole_body == false` |
| All brain scans | `anatomy.region.id == "UBERON:0000955"` (or `anatomy.region.label == "brain"`) |
| All thoracic scans (incl. multi-region) | `region` or `additional_regions` contains a thoracic UBERON term |

The `is_whole_body` flag is the primary "needle in a haystack" filter — `== true` / `== false` are unambiguous for cohort builders or future XNAT/OMERO migration; `null` (unknown) is excluded from both and surfaces in the completeness report (§4.7). Exactly mirrors how `condition.is_control` works.

#### 4.6.4 Status & implementation

| Aspect | Status |
|---|---|
| `is_whole_body` (tri-state `true`/`false`/`null`) | ✅ DECIDED highly-recommended, **non-blocking** (2026-06-03) — writer WARNs if `null`, never refuses |
| `region` UBERON-coded | 🔶 Recommended when `is_whole_body=false` — writer WARNs but proceeds |
| Ontology = UBERON | ✅ DECIDED (2026-06-03) — cross-species; harmonizes with tissue `anatomical_entity` |
| Optional `additional_regions` / `auto_hint` | 🔶 DRAFT, write-through |
| `anatomy:` writer | ✅ IMPLEMENTED (Phase 3, 2026-06-03) — `tools/ingest/enrichment.py`, called from `ingest_raw.py` Step 8.4; WARN-not-raise (§4.7). Top-level `anatomy:` YAML block in the `mri_bruker` + `molecubes_ni` templates (organism-only) |
| Auto-hint extractor (MRI ProtocolName+FOV, NI bed-range) | 🔶 Future — non-authoritative pre-fill only |
| Backfill of existing 97 MRI + 84 NI organism acqs | ⚠️ Queued — Phase 4; ingests now with `null`+WARN, enriched later (§4.7) |

### 4.7 Metadata Completeness — the Non-Blocking Model (DECIDED 2026-06-03)

> **✅ DECIDED (2026-06-03).** The enrichment blocks — `subject:` (§4.4), `condition:` (§4.5), `anatomy:` (§4.6) — follow one rule: **they never block ingest.** Data always lands; metadata is layered on afterwards. This reverses the earlier hard-required `is_control` / `is_whole_body` checks.

#### 4.7.1 Why

A hard-block on a field that no automation can supply and that the operator may not know fails the two cases gjesus3 most needs to serve:
- **Archive / historical data** — nobody is left to say "control vs case" or "whole-body vs ROI." Refusing it means losing the data entirely. **Data + a guess (or an honest `unknown`) beats no data.**
- **The realistic operator** — for internal MRI we are lucky to get a session *folder name*; requiring extra per-scan fields at sub-folder granularity is an adoption dead-end.

#### 4.7.2 The four principles

1. **Never block.** No writer ever raises on a missing enrichment field. The acquisition is registered and the sidecar is written regardless.
2. **Explicit sentinels, not absence.** Unknowns are written, not omitted: tri-state booleans (`is_control`, `is_whole_body`) take `null` = unknown; free-text → `""`; `source` → `"unknown"`. A consumer can always tell "false" from "not yet known."
3. **Set once, propagate down — never per-scan.** Enrichment is supplied at the **batch / session / project / animal** level and inherited by every acquisition in scope (per-batch YAML block is the normal path; per-acquisition override is the rare exception). The operator answers once per session, not once per scan.
4. **WARN + track, then bulk-fill.** Missing recommended fields emit a WARN and are recorded as gaps (the pending/completeness tracker), to be filled **later, in bulk**, by the people who know — not at ingest time under pressure.

#### 4.7.3 Source precedence (best-effort auto first)

| Block | Auto (best-effort) | Then | Sentinel if nothing |
|---|---|---|---|
| `subject:` | **Animal-facility DB** (strong — §4.4) | study YAML > instrument extract | `source:"pending-db"` + pending list (§4.4.6) |
| `condition:` | `disease_model` seed from DB `projects.name` (weak) | per-batch YAML > per-acq override > Excel import | `is_control:null`, `source:"unknown"` |
| `anatomy:` | `auto_hint` from protocol/FOV/bed-range (weak, non-authoritative) | per-batch YAML > per-acq override | `is_whole_body:null`, `source:"unknown"` |

`subject:` carries the load (it auto-fills); `condition:`/`anatomy:` get a weak seed/hint and otherwise rely on set-once-per-batch input or later bulk enrichment.

#### 4.7.4 Tools that make it easy (help, never require)

- **Per-batch YAML blocks** — ✅ IMPLEMENTED (Phase 3): the set-once-per-ingest path; top-level `condition:` / `anatomy:` / optional `subject:` resolver-evaluated blocks (and `auto_discover.subject_from_db` + `subject_lookup:`), in the per-instrument templates.
- **Metadata-completeness report** — ✅ IMPLEMENTED: `tools/metadata_completeness.py` (read-only) lists which acquisitions have `is_control:null` / `is_whole_body:null` / `subject.source:"pending-db"`; `tools/validate_registries.py` (REG-04 validator) additionally emits Phase 3 enrichment-gap WARNs. Both extend the `registries/pending_subject_metadata.csv` idea into a general "what's missing" view. (Companion read-only tools landed alongside: `tools/gather_metadata.py` merged raw+study view, `tools/verify_checksums.py` fixity re-check.)
- **Deferred-recovery** — ✅ IMPLEMENTED: `tools/recover_subject_metadata.py` (superuser, dry-run by default) fills `pending-db` sidecars in place from the DB; see §4.4.6.
- **Excel → study-metadata importer** (`tasks/tasks.md §3.2`) — Planned: the main bulk-fill tool for archive data; a researcher fills a per-project sheet (one row per animal/session), and it writes `condition:`/`anatomy:`/`subject:` overrides at the study level.
- **Auto-hint pre-fill** — Planned: surfaces the protocol/FOV/bed-range guess so the operator *confirms* rather than types.

#### 4.7.5 What this means for the existing 365+ acquisitions

They ingest cleanly today: `subject:` auto-fills from the DB, `condition.disease_model` gets a project-name seed, everything else is `null`/`unknown` + WARN. Nothing is lost, nothing is blocked, and the completeness report + Excel importer drive enrichment at the post-exhibition true-production restart (Phase 4).

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
| META-05 | Animal-facility-DB programmatic access + auto-populate `subject:` block (§4.4) | Data Mgmt Lead + IT | 🔶 **Access obtained 2026-06-02** — Phase 1 exploration (schema/auth/field mapping) in progress; then fetcher + deferred-recovery tooling. 4-phase plan in `tasks/tasks.md §3.2` |
| ~~META-06~~ | ~~Tighten `disease_model`/`disease_state`/`is_control` to DECIDED-required (hard-block)~~ | Data Mgmt Lead | ✅ Resolved 2026-06-03 — **superseded by the non-blocking model (§4.7).** Hard-required checks are off the table (adoption + archive-data killer); all enrichment fields are recommended-WARN, never blocking. |
| ~~META-07~~ | ~~How to fill optional `procedure_tags` from the `procedures` free-text~~ | Data Mgmt Lead | ✅ Retired 2026-06-03 — DB exploration showed procedures are **already a structured controlled vocabulary** (`animal_procedures`→`procedures.type`+date); we carry the `[{type,date}]` list directly, no free-text parsing needed (§4.4.7). Reopens only if free-text `animal_observations` notes are ever pulled. |
| META-08 | Subject/Sample two-tier identity model (reused facility animal ID as subject; registry `subject_id`/`anatomical_entity` columns) — confirm at PI sign-off (REG-01) + add registry columns at true-prod restart | Data Mgmt Lead + PI | 🔶 DRAFT 2026-06-03 — model adopted (Option B), grounded in FAIR/ISA/REMBI/BIDS/XNAT; see [06_REGISTRIES §2.3](06_REGISTRIES.md) |
| META-09 | `anatomy:` block — `is_whole_body` (highly-recommended tri-state, non-blocking §4.7) + UBERON `region` (§4.6). Confirm UBERON starter vocabulary per study; decide whether/when to build the optional auto-hint extractor (MRI ProtocolName+FOV, NI bed-range) | Data Mgmt Lead | 🔶 DRAFT 2026-06-03 — block adopted; operator-entered (not auto-derivable); writer is Phase 3 |
