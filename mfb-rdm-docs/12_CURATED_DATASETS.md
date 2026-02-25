# 12 — Curated Datasets Area

**Parent:** [Documentation Index](00_INDEX.md)
**Status:** ❓ Under Evaluation
**Last Updated:** 2026-02-25

---

## Purpose

This document specifies the *proposed* Curated Datasets storage area — a permanent, controlled space for high-value derived datasets (starting with segmentation ground truth) that accumulate across projects and support long-term reuse such as model training and benchmarking.

> **❓ EVALUATING:** This area addresses a real need (permanent storage for derived assets that span projects), but represents a scope expansion beyond the original "archival storage for original imaging data" mandate. The specification is written here so the design is captured. Deployment timing depends on pilot progress with RAW and PUBLICATIONS.

---

## 1. The Problem

### 1.1 Why This Is Needed

Several types of high-value derived data do not fit cleanly into the existing storage areas:

| Data Type | Why RAW is wrong | Why PUBLICATIONS is wrong | Why PROJECTS is wrong |
|-----------|-----------------|--------------------------|----------------------|
| Manual segmentation masks (ground truth) | Not raw — it's derived | Not tied to one publication | Projects are temporary; training data must persist |
| Curated training corpora | Breaks immutability semantics | May serve many publications | Would be deleted on project closure |
| Benchmark evaluation sets | Not original instrument output | Not publication-specific | Needs permanence |

The core issue: **segmentation ground truth and other curated derived assets accumulate across projects and are more valuable as a collective corpus than as project-specific artifacts.**

### 1.2 Motivating Use Case: Segmentation

The immediate driver is systematic storage of manual ground-truth segmentations to support:

- **Per-project classifiers:** Train segmentation models for specific studies
- **Cross-project pretraining:** Build modality-level encoders (e.g., self-supervised pretraining on all available microscopy labels)
- **Benchmarking:** Evaluate new methods against a stable, growing reference set

This requires labels to be:
- Findable across projects (not buried in project folders)
- Traceable to their RAW sources (for reproducibility)
- Versioned (as labels are corrected or expanded)
- Organized by data ecosystem (microscopy labels and DICOM labels have different downstream tools)

---

## 2. Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Curated, not dumped** | Data enters only through a promotion/review process |
| **Permanent and cumulative** | Datasets persist across project lifecycles |
| **Traceable to RAW** | Every item must reference its source acquisition(s) |
| **Versioned** | Material changes produce new versions, not silent overwrites |
| **Controlled access** | Write access restricted to curators; read access open |

---

## 3. What Goes Here (and What Does Not)

### 3.1 Belongs in CURATED_DATASETS

- Manual ground-truth segmentation masks (reviewed and finalized)
- Curated training corpora for model development
- Benchmark/evaluation sets with defined composition
- Approved annotation sets (ROIs, landmarks, etc.)

### 3.2 Does NOT Belong in CURATED_DATASETS

| Item | Where It Belongs |
|------|-----------------|
| Raw acquisitions | `RAW/` |
| Work-in-progress annotations | `PROJECTS/` (or local) |
| Draft segmentations under review | `PROJECTS/` until promoted |
| Publication figures | `PUBLICATIONS/` |
| One-off analysis outputs | `PUBLICATIONS/` or local |
| Intermediate processing results | `PROJECTS/` or local |

---

## 4. Directory Structure

### 4.1 Top-Level Layout

```
/gjesus3/
└── curated_datasets/
    ├── registry_datasets.csv                 # Dataset registry (see 06_REGISTRIES)
    ├── README_START_HERE.txt                 # Rules and quick reference
    │
    └── segmentation/                         # Dataset type
        ├── MICROSCOPY/                       # Mirrors RAW ecosystem
        │   └── DS-SEG-0001/                  # Individual dataset
        │       ├── _dataset.yaml             # Dataset metadata
        │       ├── provenance.csv            # Provenance log
        │       ├── masks/                    # The actual label data
        │       │   ├── ACQ-20260215-ZWSI-001_mask.tif
        │       │   ├── ACQ-20260216-ZWSI-002_mask.tif
        │       │   └── ...
        │       └── README.txt                # Dataset description and usage notes
        │
        ├── DICOM/
        │   └── DS-SEG-0002/
        │       ├── _dataset.yaml
        │       ├── provenance.csv
        │       ├── masks/
        │       │   ├── ACQ-20260215-MRI-001_seg.nii.gz
        │       │   └── ...
        │       └── README.txt
        │
        └── EM/
            └── ...
```

### 4.2 Path Pattern

```
/curated_datasets/<TYPE>/<ECOSYSTEM>/<DATASET-ID>/
```

| Component | Description |
|-----------|-------------|
| `<TYPE>` | Dataset type: `segmentation`, `registration`, `benchmark`, etc. |
| `<ECOSYSTEM>` | Data ecosystem (mirrors RAW): `MICROSCOPY`, `DICOM`, or `EM` |
| `<DATASET-ID>` | Unique dataset identifier (e.g., `DS-SEG-0001`) |

### 4.3 Future Type Folders

Only `segmentation/` is created initially. Additional types are added when there is an actual use case:

| Type Folder | Purpose | Status |
|-------------|---------|--------|
| `segmentation/` | Ground-truth labels (masks, ROIs, annotations) | Initial scope |
| `registration/` | Registered/aligned image sets | Future |
| `denoising/` | Denoised reference datasets | Future |
| `benchmark/` | Curated evaluation sets | Future |

---

## 5. Dataset Metadata

### 5.1 Dataset Metadata File

**File:** `_dataset.yaml`

```yaml
dataset_id: DS-SEG-0001
short_name: lung-fibrosis-gt-v1
description: |
  Manual segmentation masks for IPF lung tissue sections.
  H&E-stained whole-slide images, annotated for fibrotic regions.
  Intended for training fibrosis segmentation models.

dataset_type: segmentation
data_ecosystem: MICROSCOPY
version: v1.0

# Ownership
owner: Ryan Tasseff
created_date: 2026-03-15
last_updated: 2026-03-15

# Content
sample_count: 24
label_format: .tif  # binary masks, same dimensions as source images
label_classes:
  - background
  - fibrotic_region
annotation_tool: QuPath 0.5.1

# Provenance
source_acquisitions:
  - ACQ-20260215-ZWSI-001
  - ACQ-20260216-ZWSI-002
  - ACQ-20260217-ZWSI-003
  # ... (full list in provenance.csv)

# Status
status: active  # active | superseded | archived
superseded_by: null  # DS-ID of replacement, if superseded

notes: |
  Initial training set. Labels reviewed by RT and MBC.
  Fibrotic regions annotated at 10x equivalent resolution.
```

### 5.2 Provenance

Each dataset folder contains a `provenance.csv` following the same format as Publications (see [07_PROVENANCE](07_PROVENANCE.md)), with one entry per label/output file.

**Minimum per label:**
- Source RAW acquisition (`acq_id`)
- Who created the label (`creator`)
- When (`date_created`)
- How (`process_description` — e.g., "Manual annotation in QuPath")
- Software/tool and version

### 5.3 Label File Naming

Label files should reference their source acquisition for discoverability:

```
<ACQ-ID>_<suffix>.<ext>
```

**Examples:**
- `ACQ-20260215-ZWSI-001_mask.tif` (binary segmentation mask)
- `ACQ-20260215-MRI-001_seg.nii.gz` (NIfTI segmentation)
- `ACQ-20260215-ZWSI-001_rois.geojson` (ROI annotations)

---

## 6. Promotion Workflow

Data enters CURATED_DATASETS through a controlled **promotion** process, not direct deposit.

### 6.1 Lifecycle

```
┌─────────────┐     ┌─────────────┐     ┌──────────────────┐
│  Work in    │ ──▶ │  Review     │ ──▶ │  CURATED_DATASETS│
│  PROJECTS/  │     │  (curator)  │     │  (permanent)     │
└─────────────┘     └─────────────┘     └──────────────────┘
       │                   │                      │
  Draft labels        Quality check          Registered
  Evolving            Complete provenance    Versioned
  Temporary           Curator approval      Read-only (mostly)
```

### 6.2 Promotion Checklist

Before a dataset can be promoted to CURATED_DATASETS:

- [ ] All labels have been reviewed for quality
- [ ] Every label traces to a valid RAW acquisition (ACQ-ID exists in raw registry)
- [ ] `_dataset.yaml` is complete
- [ ] `provenance.csv` has entries for all label files
- [ ] Dataset has been registered in `registry_datasets.csv`
- [ ] Curator has approved the promotion

### 6.3 Who Can Promote

> **🔶 DRAFT:** Write access to CURATED_DATASETS should be limited to designated curators.

| Role | Access |
|------|--------|
| Dataset curator (Data Mgmt Lead + designated backup) | Read + Write |
| All other operators | Read only |

---

## 7. Versioning

### 7.1 When to Version

| Change Type | Action |
|-------------|--------|
| Adding more labels to existing dataset | Update in place; increment version (e.g., `v1.0` → `v1.1`); update `sample_count` |
| Correcting existing labels | Update in place; increment version; document corrections in notes |
| Major revision (different annotation schema, classes, etc.) | Create new dataset ID (e.g., `DS-SEG-0002`); mark old as `superseded` |

### 7.2 Version Tracking

- Current version recorded in `_dataset.yaml` and registry
- If a dataset is superseded, the old entry remains in the registry with `status: superseded` and `superseded_by: <new-DS-ID>`
- Old dataset folders are retained (read-only) for reproducibility of prior results

---

## 8. Guardrails

These rules are non-negotiable for maintaining the value of CURATED_DATASETS:

### 8.1 Curation Required

Data moves into CURATED_DATASETS **only** when it is considered stable and reusable. Ongoing annotation work stays in PROJECTS.

### 8.2 Traceability Required

Every label/output must reference its RAW source(s). Minimum: ACQ-ID + creator + date + tool/method description.

### 8.3 No Silent Overwrites

Changes to promoted datasets must be versioned. Do not silently replace files without updating the version and documenting the change.

### 8.4 Controlled Write Access

Write access limited to curators. This prevents the area from becoming another dumping ground.

---

## 9. Relationship to Other Areas

```
RAW/                          ──── source data ────▶  CURATED_DATASETS/
  (immutable originals)                                  (derived labels)
                                                              │
PROJECTS/                     ──── promotion ────▶           │
  (work-in-progress labels)                                  │
                                                              │
PUBLICATIONS/                 ◀──── references ────          │
  (papers using the models                                    │
   trained on these datasets)
```

| Relationship | Direction | Mechanism |
|--------------|-----------|-----------|
| RAW → CURATED_DATASETS | Source | ACQ-ID references in provenance |
| PROJECTS → CURATED_DATASETS | Promotion | Curator review and copy |
| CURATED_DATASETS → PUBLICATIONS | Reference | Publication provenance cites dataset ID |

---

## 10. Immediate Scope (If Approved)

If this area is approved for the pilot:

1. Create `/gjesus3/curated_datasets/` with `README_START_HERE.txt`
2. Create `segmentation/MICROSCOPY/` and `segmentation/DICOM/` scaffolding
3. Initialize `registry_datasets.csv` with headers
4. Promote first segmentation dataset as proof of concept

What is **not** in initial scope:
- `registration/`, `denoising/`, `benchmark/` type folders (future)
- `EM/` subfolder (pending EM inclusion decision)
- Automated promotion tooling (manual for pilot)

---

## 11. Related Documents

- [03_RAW_STORAGE](03_RAW_STORAGE.md) — Source data referenced by datasets
- [06_REGISTRIES](06_REGISTRIES.md) — Curated datasets registry schema
- [07_PROVENANCE](07_PROVENANCE.md) — Provenance logging format
- [05_PROJECTS](05_PROJECTS.md) — Where work-in-progress lives before promotion

---

## Open Questions Summary

| ID | Question | Owner | Status |
|----|----------|-------|--------|
| CDS-01 | Include curated datasets area in pilot or defer to Phase 2? | Data Mgmt Lead + PI | ❓ Evaluating |
| CDS-02 | Who are the designated curators beyond Data Mgmt Lead? | Data Mgmt Lead | 🔶 Draft |
| CDS-03 | Label format standardization: should we mandate specific formats per ecosystem? (e.g., OME-TIFF for microscopy, NIfTI for DICOM) | Data Mgmt Lead | 🔶 Draft |
| CDS-04 | How to handle labels that span multiple acquisitions (e.g., a registered atlas built from many MRI scans)? | Data Mgmt Lead | 📋 Future |
| CDS-05 | Integration with ML training pipelines — do we need a standard manifest format for data loaders? | Data Mgmt Lead | 📋 Future |
