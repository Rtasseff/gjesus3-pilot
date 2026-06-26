# 03 — Raw Storage Area

**Parent:** [Documentation Index](00_INDEX.md)
**Status:** 🔶 Draft (in production use — structure + conventions stable; a few sub-rules still 🔶/❓)
**Last Updated:** 2026-06-26

---

## Purpose

This document specifies the structure, conventions, and workflows for the Raw storage area — the authoritative, research-facing archive for original imaging acquisitions on gjesus3. It is **live in true production**: `/raw/` holds ~13,555 acquisitions across the MICROSCOPY and DICOM ecosystems and is read-only after deposit.

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
| `EM/` [^em] | Electron microscopy: SEM, TEM | .tif, .dm3, .dm4, proprietary | Specialized EM tools |

### 2.3 Directory Tree

```
/gjesus3/
├── registries/
│   ├── registry_raw.csv                # Master raw registry, 28 cols (see 06_REGISTRIES)
│   └── index.html                      # GENERATED researcher "Finder" (global, ~19 MB) —
│                                       # self-contained searchable index, auto-refreshed at
│                                       # the end of each successful ingest; not a source of
│                                       # truth, not in git (see 06_REGISTRIES §1.2, tools/FINDER.md).
│                                       # Each /projects/<proj>/ also gets its own index.html.
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
    │   ├── 2025/                           # CURRENT shape: internal MRI/NI folder bundle, no zip
    │   │   └── 2025-10/
    │   │       └── ACQ-20251016-MRI-029/   # Internal MRI (Bruker ParaVision)
    │   │           ├── metadata.json              # Rich mri: block from ParaVision JCAMP-DX
    │   │           ├── checksums.json
    │   │           ├── README.txt
    │   │           └── ACQ-20251016-MRI-029.data/ # The data bundle (parallels microscopy <ACQ-ID>.czi)
    │   │               ├── recon1_frame01.dcm     # Per-frame DICOMs, renamed flat
    │   │               ├── recon1_frame02.dcm     # recon<idx>_frame<NN>.dcm
    │   │               └── recon3_frame01.dcm     # (a second kept reconstruction, /3)
    │   │
    │   └── 2026/                           # LEGACY shape: collaborator DICOM as a zip archive
    │       └── 2026-02/                    # (rounds 1-2 historical; NOT in the current
    │           └── ACQ-20260215-XMRI-001/  #  true-production /raw/ — kept here as the
    │               ├── ACQ-20260215-XMRI-001.zip  #  documented archive shape, primary_kind=archive)
    │               ├── metadata.json
    │               ├── checksums.json
    │               └── README.txt
    │
    └── EM/                                 # RESERVED — not deployed (see footnote on §2.2)
        └── 2026/                           #  intended shape only; no EM acqs in production
            └── 2026-03/
                └── ACQ-20260310-SEM-001/
                    ├── ACQ-20260310-SEM-001.tif    # Primary data file (renamed to acq_id)
                    ├── checksums.json
                    └── README.txt
```

> The internal MRI / Nuclear-Imaging on-disk shape is **folder-as-primary**: the acquisition folder holds `metadata.json` + `checksums.json` + `README.txt` + a single `<ACQ-ID>.data/` subfolder of flat-renamed DICOMs. The verbose ParaVision/Molecubes aux files (`acqp`, `method`, `visu_pars`, `subject`, `2dseq`, `reco`, raw `fid`, listmode, …) are **not** copied to gjesus3 — their parsed content lives inside `metadata.json` and the byte-originals stay on the platform deep-archive. See §4.3 (NI) and §4.4 (MRI) for the full layout and the "what is NOT copied" lists.

### 2.4 Path Pattern

```
/raw/<ECOSYSTEM>/<YYYY>/<YYYY-MM>/<ACQ-ID>/
```

| Component | Description |
|-----------|-------------|
| `<ECOSYSTEM>` | Data ecosystem: `MICROSCOPY` or `DICOM` (live); `EM` reserved, not deployed [^em] |
| `<YYYY>` | Year of acquisition |
| `<YYYY-MM>` | Year-month of acquisition |
| `<ACQ-ID>` | Unique acquisition identifier (see Section 3.1) |

### 2.5 Ingestion Decision Rule

When depositing raw data:

| If the data is... | Deposit to | Examples |
|-------------------|------------|----------|
| Microscopy vendor files or Bio-Formats compatible | `MICROSCOPY/` | .czi, .nd2, .lif, .ome.tif |
| DICOM or originated as DICOM | `DICOM/` | .dcm folders, DICOM-derived .nii |
| Electron microscopy | `EM/` (reserved — not yet in scope) [^em] | .tif (from SEM/TEM), .dm3, .dm4 |
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
| **Collaborator DICOM** (XMRI/XCT/XPET/XSPECT) | Compressed archive `<ACQ-ID>.zip` | LEGACY shape — many `.dcm` per session, zipped on deposit. Used by the rounds 1-2 collaborator cohort historically; **not present in the current true-production `/raw/`** and not the recommended shape going forward. Retained as a documented, registry-supported shape (`primary_kind: archive`) for any future already-zipped collaborator drop. | `archive` |
| **Internal MRI** (Bruker ParaVision) | Folder `<ACQ-ID>/` containing a `<ACQ-ID>.data/` data bundle (per-frame DICOMs only, renamed flat: `recon<idx>_frame<NN>.dcm`) + `metadata.json` carrying the parsed JCAMP-DX content. Round-6 v2 2026-05-27 (mirrors NI v2.1). | Bruker exports per-frame DICOMs (15-ish per recon, a 1990s-era one-image-per-file choice, not a conceptual mismatch — see [13_GJESUS3_ROLE §5.2](13_GJESUS3_ROLE.md)). The `.data/` subfolder mirrors microscopy's `<ACQ-ID>.czi` and NI's `<ACQ-ID>.data/` conventions; parsed `metadata.json.mri._raw_metadata` preserves what would otherwise live in scattered JCAMP-DX aux files. The raw `fid` (k-space signal) stays only on the platform acquisition machine — see §4.4. | `folder` (primary_file_name = `<ACQ-ID>.data`) |
| **Internal PET/SPECT/CT** (Molecubes / MILabs) | Folder `<ACQ-ID>/` containing a `<ACQ-ID>.data/` data bundle (DICOMs only, renamed flat: `recon<X>.dcm` for CT, `recon<X>_frame<Y>.dcm` for PET/SPECT) + `metadata.json` carrying the parsed aux content. Round-8 v2 2026-05-27. | Source archives contain a mix of analysis-ready DICOMs and raw detector data the platform owns long-term ([13_GJESUS3_ROLE §5.6](13_GJESUS3_ROLE.md)). The `.data` subfolder mirrors microscopy's `<ACQ-ID>.czi` single-file convention; the parsed `metadata.json.ni._raw_metadata` preserves what would otherwise live in scattered aux files. | `folder` (primary_file_name = `<ACQ-ID>.data`) |
| **EM** (reserved — not deployed) [^em] | Single file `<ACQ-ID>.<ext>` | Intended shape only: one acquisition = one file natively for SEM/TEM. No EM acquisitions in production. | `file` |

### 4.3 Internal Nuclear Imaging folder bundle — detail (round-8 v2 2026-05-27)

For internal NI (Molecubes archive-mode), the acquisition folder mirrors microscopy's one-file-per-acquisition convention as closely as a multi-DICOM reconstruction allows: a single `<ACQ-ID>.data/` subfolder holds the DICOMs (renamed flat — `recon<X>.dcm` for CT, `recon<X>_frame<Y>.dcm` for PET/SPECT). Everything else from the upstream Molecubes archive — raw detector data, calibration, operational logs, AND the acquisition aux text/XML files — stays on the platform archive (`\\cicmgsp02\gnuclear2$`). The aux file *contents* are preserved in parsed form inside `metadata.json.ni._raw_metadata`, so no meaningful information is lost from the gjesus3 surface.

```
ACQ-<YYYYMMDD>-<MODALITY>-NNN/        (MODALITY = PET / CT / SPECT)
  metadata.json                       <-- rich ni: block: parsed protocol.txt + 3 XMLs + DICOM headers (incl. UIDs)
  checksums.json
  README.txt                          (optional)
  <ACQ-ID>.data/                      <-- the data bundle (parallels microscopy <ACQ-ID>.czi)
    recon0.dcm                          (CT, no frame subdirs)
    recon1.dcm
    recon2.dcm
    recon0_frame0.dcm                   (PET/SPECT static — one frame)
    recon0_frame1.dcm, recon0_frame2.dcm  (PET dynamic — per-frame)
    recon0_frameMULTI.dcm               (PET dynamic — bundled all-frames DICOM, kept alongside)
```

**Per-modality DICOM naming:**

| Modality | Source structure | gjesus3 DICOM name(s) | Recons per acq |
|---|---|---|---|
| **CT** | `recon_<X>/<basename>.dcm` direct | `recon<X>.dcm` | Multiple (typical 3 — ISRA standard, ISRA variant, ATTMAP for PET attenuation correction); all kept — different recons answer different analysis questions |
| **PET / SPECT static** | `recon_0/frame_0/iter_30/<basename>.dcm` | `recon0_frame0.dcm` | Typically 1 |
| **PET / SPECT dynamic** | `recon_0/frame_<Y>/iter_30/<basename>.dcm` per time-frame, plus a single multi-frame DICOM at recon root (`<basename>_frameMULTI_iter30.dcm`) | `recon0_frame<Y>.dcm` per frame **plus** `recon0_frameMULTI.dcm` for the bundled-all-frames file | Typically 1 recon with multiple frames + 1 multi-frame DICOM |

The iteration count (typically `30` in current Molecubes setup) is dropped from the gjesus3 filename — it's preserved verbatim in `metadata.json.ni._raw_metadata.reconparams_by_idx.<X>.ReconstructionTemplate/iterations`. If iteration count ever varies across recons of the same acquisition, the filename convention will need extension.

**Platform-generated multi-frame DICOMs** (filename contains `frameMULTI`) are observed in some dynamic PET acquisitions — the platform bundles all frames into one DICOM file at the recon root (e.g. `recon_0/<basename>_frameMULTI_iter30.dcm`). gjesus3 keeps these alongside the per-frame DICOMs, naming them `recon<X>_frameMULTI.dcm` under `<ACQ-ID>.data/`. They appear in the regular `metadata.json.ni.reconstruction.by_index.<idx>.dicoms[]` list (distinguishable by `ImageType` containing `'DYNAMIC'` instead of `'VOLUME'`). See `equipment/nuclear-imaging/internal_ni_data_handling_workflow_notes.md` "Multi-frame DICOM" section for the rationale and future-work (potential migration to multi-frame as the canonical single primary file once its advanced metadata is validated).

**What's explicitly NOT copied** (lives only on `\\cicmgsp02\gnuclear2$`):
- Acquisition root files (all of them): `protocol.txt`, `protocol.xml`, `acqparams.xml`, `recontemplate.xml`, `acquisition.log` (parsed forms in sidecar), `data.raw` (6+ GB CT raw detector), `bright.raw`/`dark.raw`/`badpixels.map` (calibration), `attmap.amap`, `eventdata_*.list/.dt/.header` (PET event lists), `singles.stat`, `spectrum.bin`, `monitoring.csv`, `sequence.csv`, `xrayserver.log`, `calibrationParameters.xml`, `recon.ini` at acq root, `ACQSTATUS`, `DOWNLOADED`, `REMIDOWNLOADED`, `registration.matrix`, `reconstructionParameters*.xml`
- Per recon (all non-DICOM): `.img` (binary mirror of the DICOM), `RECONSTATUS`, `preview.res`, `.bin` files, `bed0_counts.stat`, `atten_*.bin`, `reconparams.txt`/`reconparams.xml` (parsed forms in sidecar), `reconstruction.log`, `recon.ini`
- (v2.1: multi-frame DICOMs are NOT dropped — kept alongside per-frame as `recon<X>_frameMULTI.dcm`)

Per-acquisition size on gjesus3 is ~MB-scale (DICOMs only — CT ~94 MB across 3 recons, PET static ~28 MB, PET dynamic ~55 MB across 2 frames). Total NI footprint on gjesus3 ~6.5 GB across all 84 acqs in the round-8 cohort — vs ~358 GB if we'd copied the upstream archives verbatim.

The microscopy structural parallel: a microscopy acquisition has `<ACQ-ID>.czi` (single file primary) inside its `<ACQ-ID>/` folder; an NI acquisition has `<ACQ-ID>.data/` (folder primary) inside its `<ACQ-ID>/` folder. The registry's `primary_kind` records which shape (`file` vs `folder`); `primary_file_name` names the thing.

See [13_GJESUS3_ROLE §5.6](13_GJESUS3_ROLE.md) for the framing this implements, [`equipment/nuclear-imaging/internal_ni_data_handling_workflow_notes.md`](../equipment/nuclear-imaging/internal_ni_data_handling_workflow_notes.md) for the source-side archive structure + multi-frame DICOM details, and [08_METADATA §4.3](08_METADATA.md) for the `ni:` sidecar block shape (parsed protocol.txt + XMLs + per-DICOM headers with UIDs).

### 4.4 Internal MRI folder bundle — detail (round-6 v2 2026-05-27)

For internal MRI (Bruker ParaVision), the acquisition folder mirrors the NI v2.1 convention: a single `<ACQ-ID>.data/` subfolder holds the per-frame DICOMs (renamed flat — `recon<idx>_frame<NN>.dcm`). Everything else from the upstream ParaVision exam — the JCAMP-DX aux files (`acqp`, `method`, `visu_pars`, `subject`), the raw `fid`, per-recon `2dseq`/`visu_pars`/`reco`, miscellaneous platform files — stays on the platform archive (the acquisition machine's `/opt/PV-7.0.0/data/nmr/` and its mirrored FTP path). The aux file *contents* are preserved in parsed form inside `metadata.json.mri._raw_metadata`, so nothing meaningful is lost from the gjesus3 surface.

```
ACQ-<YYYYMMDD>-MRI-<exam>/
  metadata.json                       <-- rich mri: block: parsed subject/acqp/method/visu_pars + per-DICOM headers (incl. UIDs)
  checksums.json
  README.txt                          (optional)
  <ACQ-ID>.data/                      <-- the data bundle (parallels NI's <ACQ-ID>.data and microscopy's <ACQ-ID>.czi)
    recon1_frame01.dcm                  (Bruker MRIm01.dcm from pdata/1/dicom/)
    recon1_frame02.dcm
    ... (per-frame DICOMs from pdata/1)
    recon3_frame01.dcm                  (Bruker MRIm01.dcm from pdata/3/dicom/)
    recon3_frame02.dcm
    ... (per-frame DICOMs from pdata/3)
```

**DICOM naming**: Bruker exports per-frame DICOMs `MRIm01.dcm` ... `MRIm15.dcm` (typically 15 per reconstruction). Flat-renamed to `recon<idx>_frame<NN>.dcm` preserving Bruker's zero-padded NN. Multiple reconstructions (per `reconstructions:` YAML selection) live side-by-side in the same flat folder; the `recon<idx>` prefix distinguishes them.

**Reconstruction selection** (`reconstructions:` YAML flag in `mri_bruker.yaml`): operator picks `all` (default — DICOMs are tiny under this layout), `<int>` (e.g. `3`), or `[<int>, ...]` (e.g. `[1, 3]`). Indices not listed stay on the platform deep-archive. The original cardiac-flow workflow convention (`[3]` = user-trusted reconstruction) is still appropriate when an operator wants to minimise storage — but `all` is the safer default.

**No-DICOM acquisitions** (students who didn't run Bruker's DICOM exporter): the ingest still registers the acquisition. The `<ACQ-ID>.data/` folder is created empty; `metadata.json.mri:` is fully populated from the parsed JCAMP-DX (subject, acquisition parameters, geometry, per-recon parameters); `metadata.json.mri.reconstruction.by_index.<idx>.dicoms[]` is empty. Idempotent re-run after the student converts will skip the placeholder and ingest the freshly-available DICOMs. See [`equipment/mri-platform/internal_mri_data_handling_workflow_notes.md`](../equipment/mri-platform/internal_mri_data_handling_workflow_notes.md) "No-DICOM acquisition handling" section. The future-work FID→DICOM regeneration capability (tracked in [`tasks/BACKLOG.md`](../tasks/BACKLOG.md)) would close this gap.

**What's explicitly NOT copied** (lives only on the platform acquisition machine):
- Exam-root JCAMP-DX aux: `acqp`, `method`, `visu_pars`, `subject`, `pulseprogram`, `specpar`, `uxnmr.info`, `uxnmr.par`, `configscan`, `AdjStatePerScan` (parsed content in sidecar)
- Raw signal: `fid` (~12 MB per exam) — the actual k-space data; gjesus3 does not duplicate this. Future-work FID→DICOM regeneration would read this file as input.
- Per-recon non-DICOM: `2dseq` (binary image — DICOMs derive from it), `visu_pars`, `reco`, `id`, `procs`, `methreco` (parsed content in `_raw_metadata.pdata.<idx>` for `visu_pars` + `reco`)
- Reconstruction indices not listed in the operator's `reconstructions:` selection

Per-acquisition size on gjesus3 is ~MB-scale (DICOMs only; ~200 KB × 15-frame × N_recon). Acquisitions with no DICOMs are KB-scale (just `metadata.json` + `checksums.json` + `README.txt`).

See [13_GJESUS3_ROLE §5.6](13_GJESUS3_ROLE.md) for the framing this implements, [`equipment/mri-platform/internal_mri_data_handling_workflow_notes.md`](../equipment/mri-platform/internal_mri_data_handling_workflow_notes.md) for the source-side structure + reconstruction discipline (`/1` auto, `/2` duplicate, `/3` user-trusted), and [08_METADATA §4.3](08_METADATA.md) for the `mri:` sidecar block shape (parsed JCAMP-DX + per-DICOM headers with UIDs).

### 4.5 Supporting vs. primary

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

### 4.6 Edge cases — guidance

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

**Full Mode** (default): Source on fast local storage. Analyzes data, extracts embedded metadata to `metadata.json`, organises the primary entity into its canonical shape, copies the result to the NAS, and populates all registry fields. The "organise the primary entity" step is **per-ecosystem** (see §4.2): microscopy is renamed in place (`<ACQ-ID>.czi`); internal MRI/NI build the `<ACQ-ID>.data/` flat-DICOM bundle; the **legacy collaborator-DICOM path** is the one that compresses many `.dcm` into a `<ACQ-ID>.zip` archive (not used for the current internal-imaging ecosystems).

**Lightweight Mode** (`--lightweight`): Source on NAS staging or any path. Copies the primary entity as-is, populates minimum registry fields, sets `extended_metadata_present` = `N`. Can be upgraded later using `backfill_metadata`.

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

**Implementation (APPLIED 2026-06-02 on `J:\gjesus3-data\`):** NTFS/SMB ACLs via the existing `CICBIOMAGUNE\GJesus` group (no custom QNAP groups — IT will not create them). The "write during deposit, read-only after" rule is realised with a **write-but-not-modify** grant for operator accounts on `raw\`: "create files/folders" scoped to *folders only* + read-only on *files*, so operators can deposit new acquisitions but cannot modify or delete existing raw files. Superusers (Data Mgmt Lead + PI) retain Full for corrections / project close-out merges. **Caveat:** this fine-grained NTFS semantics may not map cleanly to the QNAP filesystem over SMB — pending verification with a real operator account (see [`tasks/STATUS.md`](../tasks/STATUS.md)); fallback is a tool-applied read-only lock at end-of-ingest. Traceability is backstopped by per-acquisition `checksums.json` (detects any change) and `@Recently-Snapshot` (recovery). Full applied model: [11_OPERATIONS §2.1.1](11_OPERATIONS.md).

---

## 8. Linking Raw to Projects and Publications

> **✅ DECIDED — NTFS/SMB hard links (2026-06-02; supersedes the original Windows `.lnk` choice):** Cross-references from project (and, in future, publication) folders back into raw use **NTFS/SMB hard links** — the project copy is a real file sharing raw's inode (zero extra storage; raw's read-only descriptor carries through). The original Windows `.lnk` shell shortcuts remain the cross-platform porting seam. Still a pilot-specific choice (MFB Windows user base; no SSH-to-NAS for server-side symlinks) and **not** the recommended default for future RDM deployments — see [10_TOOLS §2.1.1](10_TOOLS.md#211-project-linking--hard-links-current-over-lnk-shortcuts) for the full rationale, tradeoffs, and porting guide.

**Behavior at ingest time:** When `ingest_raw.py` is run with `--project <PROJ-ID>`, full-mode ingest creates a **hard link** under `/projects/<project_folder>/raw_linked/` that points at the canonical primary entity in `/raw/`:
- **File-primary** (microscopy `<ACQ-ID>.czi`, legacy collaborator `<ACQ-ID>.zip`) → a single hard link (one `os.link`) — the project copy is byte-for-byte the same inode as the raw file.
- **Folder-primary** (internal MRI/NI `<ACQ-ID>.data/`) → a real folder of per-file hard links mirroring the `.data/` bundle.

Because it is a hard link, the project copy looks and opens like a normal file/folder, costs zero extra storage, and shares raw's read-only ACL (so it cannot be used to mutate raw bytes). The step is idempotent — re-running ingest skips any link already in place. The retired Windows `.lnk` shortcut method is kept only as the cross-platform porting seam (see [10_TOOLS §2.1.1](10_TOOLS.md#211-project-linking--hard-links-current-over-lnk-shortcuts)); since 2026-06-02 it is **not** how live links are created (283 pre-existing `.lnk` links were migrated to hard links).

**Manifest as portable fallback:** Independent of the hard-link creation, every ingest appends a row to `registries/ingest_manifest.csv` mapping the original source name to its ACQ-ID and canonical path. Scripts and non-Windows tooling that can't (or don't want to) resolve project links should consume the manifest — or the searchable Finder (`registries/index.html`) — instead.

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
| ~~RAW-07~~ | ~~DICOM storage format (expanded vs. archive)?~~ | — | ✅ Resolved per-ecosystem (see §4.2): internal MRI/NI = folder-as-primary `<ACQ-ID>.data/` (no zip); legacy collaborator DICOM = compressed archive |
| ~~RAW-08~~ | ~~Primary staging location (NAS vs. off-NAS)?~~ | — | ✅ Resolved: primary off-NAS (fast local); NAS staging secondary; see Section 5.2 |
| RAW-09 | Archive format preference: .zip vs .tar.gz? | Data Mgmt Lead | ❓ Evaluating — .zip has Windows compatibility edge |

---

[^em]: **`EM/` is reserved, not deployed.** Electron microscopy (SEM/TEM) is a planned-but-not-confirmed scope item (see [09_MODALITIES §2.1](09_MODALITIES.md), MOD-01); no `EM/` folder exists in production and no EM acquisitions have been ingested. The two live ecosystems are `MICROSCOPY/` and `DICOM/`. The `EM/` rows in this document describe the *intended* shape should EM be brought in scope. Its instrument codes (`SEM`, `TEM`) are likewise reserved.
