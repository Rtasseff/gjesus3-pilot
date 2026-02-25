# 07 — Provenance Logging

**Parent:** [Documentation Index](00_INDEX.md)  
**Status:** 🔶 Draft  
**Last Updated:** 2026-02-02

---

## Purpose

This document specifies how provenance (origin and transformation history) is tracked for derived files in the Publications, Projects, and Curated Datasets areas.

---

## 1. What Is Provenance?

Provenance documents **where data came from and how it was transformed**.

For any derived file (figure, analysis result, processed image), provenance answers:
- **What are the inputs?** (raw data, intermediate files, parameters)
- **What process created it?** (script, manual analysis, software tool)
- **Who created it and when?**

### 1.1 Why Provenance Matters

| Purpose | Benefit |
|---------|---------|
| **Publication traceability** | Trace any published figure back to its source data |
| **Reproducibility** | Understand how results were generated |
| **Audit trail** | Defend results if questioned |
| **Future reuse** | Reprocess data with updated methods |

### 1.2 Provenance vs. Metadata

| Concept | Scope | Example |
|---------|-------|---------|
| **Metadata** | Describes a single file/object | "This image is 1024×1024, acquired at 20x magnification" |
| **Provenance** | Describes relationships and transformations | "This figure was created from ACQ-001 using ImageJ segmentation" |

---

## 2. Provenance Model

We use a simple **input → process → output** model:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Inputs    │ ──▶ │   Process   │ ──▶ │   Output    │
│ (raw data,  │     │ (script,    │     │ (derived    │
│  files)     │     │  analysis)  │     │  file)      │
└─────────────┘     └─────────────┘     └─────────────┘
```

**Each output file gets one provenance entry** that documents its inputs and the process that created it.

---

## 3. Provenance File Specification

### 3.1 Location

Provenance logs are **local to each publication, project, or curated dataset folder**:

- `/gjesus3/publications/<short-name>/provenance.csv`
- `/gjesus3/projects/<short-name>/provenance.csv`
- `/gjesus3/curated_datasets/<type>/<ecosystem>/<dataset-id>/provenance.csv`

### 3.2 Why Local (Not Centralized)?

| Reason | Explanation |
|--------|-------------|
| **Self-contained packages** | Publication folder contains everything needed |
| **Portable archiving** | Can export folder with provenance intact |
| **Simpler management** | Each folder is independent |
| **Collaboration** | Multiple people can log to their own context |

### 3.3 File Format

**Format:** CSV with headers

**Filename:** `provenance.csv`

### 3.4 Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file_id` | String | ✅ Yes | Unique ID within this folder (e.g., `FILE-0001`) |
| `output_path` | String | ✅ Yes | Relative path to the output file |
| `output_name` | String | ✅ Yes | Filename without path (for readability) |
| `file_type` | String | ✅ Yes | Extension/format (e.g., `.tiff`, `.csv`) |
| `date_created` | Date | ✅ Yes | When the file was created (YYYY-MM-DD) |
| `creator` | String | ✅ Yes | Who created the file |
| `input_refs` | String | ✅ Yes | Semicolon-separated list of inputs (see Section 4) |
| `process_description` | String | ✅ Yes | Description of the transformation (see Section 5) |
| `software_version` | String | 🔶 Recommended | Software and version used |
| `parameters_ref` | String | Optional | Path to parameter file or config |
| `lab_notebook_ref` | String | Optional | Reference to lab notebook entry |
| `notes` | String | Optional | Additional context |

### 3.5 Example

```csv
file_id,output_path,output_name,file_type,date_created,creator,input_refs,process_description,software_version,parameters_ref,lab_notebook_ref,notes
FILE-0001,figures/fig1_panel_a.tiff,fig1_panel_a.tiff,.tiff,2026-02-15,MBC,ACQ-20260115-ZWSI-001,ROI extraction and contrast adjustment,ImageJ 1.54f,,ELN-2026-0042,Main figure panel
FILE-0002,figures/fig1_panel_b.tiff,fig1_panel_b.tiff,.tiff,2026-02-15,MBC,ACQ-20260115-ZWSI-001;ACQ-20260116-ZWSI-002,Merged overlay of two acquisitions,ImageJ 1.54f,,,Composite image
FILE-0003,analysis/segmentation_results.csv,segmentation_results.csv,.csv,2026-02-16,MBC,ACQ-20260115-ZWSI-001;methods/cell_segmentation.py,Automated cell segmentation,Python 3.11 + scikit-image 0.21,methods/seg_params.json,,
FILE-0004,figures/fig2_quantification.png,fig2_quantification.png,.png,2026-02-16,MBC,FILE-0003,Bar chart of segmentation counts,Python 3.11 + matplotlib 3.8,,,Generated from segmentation output
```

---

## 4. Input References

### 4.1 Format

The `input_refs` field contains a **semicolon-separated list** of inputs.

| Input Type | Format | Example |
|------------|--------|---------|
| Raw acquisition | ACQ-ID | `ACQ-20260115-ZWSI-001` |
| File within same folder | FILE-ID | `FILE-0003` |
| Relative path | Path | `methods/config.yaml` |
| External reference | URL or identifier | `https://example.com/resource` |

### 4.2 Examples

| Scenario | `input_refs` Value |
|----------|-------------------|
| Single raw acquisition | `ACQ-20260115-ZWSI-001` |
| Multiple raw acquisitions | `ACQ-20260115-ZWSI-001;ACQ-20260116-ZWSI-002` |
| Raw acquisition + parameter file | `ACQ-20260115-ZWSI-001;methods/params.json` |
| Another derived file | `FILE-0003` |
| Multiple derived files | `FILE-0001;FILE-0002` |
| Mixed inputs | `ACQ-20260115-ZWSI-001;FILE-0003;methods/config.yaml` |

### 4.3 Traceability Chain

By following `input_refs`, any output can be traced back to raw acquisitions:

```
fig1_panel_b.tiff (FILE-0002)
    ↓ input_refs
ACQ-20260115-ZWSI-001, ACQ-20260116-ZWSI-002
    ↓ registered in
/raw/MICROSCOPY/2026/2026-01/ACQ-20260115-ZWSI-001/
/raw/MICROSCOPY/2026/2026-01/ACQ-20260116-ZWSI-002/
```

---

## 5. Process Description

### 5.1 What to Capture

The `process_description` field should be **sufficient to understand what was done**, even if not fully reproducible from description alone.

| Level | Example | When to Use |
|-------|---------|-------------|
| **Brief** | "Cropped and adjusted brightness" | Simple manual editing |
| **Method reference** | "Cell segmentation using method in Section 2.1" | Published/documented method |
| **Script reference** | "Ran analysis/pipeline.py" | Scripted analysis |
| **Tool description** | "QuPath cell detection with default parameters" | Software tool |

### 5.2 Supporting Details

For complex processes, use additional fields:

| Field | Purpose | Example |
|-------|---------|---------|
| `software_version` | Specific software and version | `QuPath 0.4.3` |
| `parameters_ref` | Path to parameter/config file | `methods/qupath_detection.json` |
| `lab_notebook_ref` | Reference to detailed notes | `ELN-2026-0042` or `Notebook 3, p. 47` |

### 5.3 Examples

| Scenario | `process_description` |
|----------|----------------------|
| Manual image adjustment | "Cropped ROI, adjusted contrast using Levels in ImageJ" |
| Scripted analysis | "Ran cell_segmentation.py v1.2 with default parameters" |
| Pipeline | "Processing pipeline: (1) background subtraction, (2) thresholding, (3) particle analysis" |
| External service | "Uploaded to CellProfiler cloud, used saved pipeline 'lung_analysis_v3'" |
| Manual annotation | "Manual ROI annotation in QuPath, saved as GeoJSON" |

---

## 6. Provenance Requirements

### 6.1 What Must Be Logged

| Area | Requirement | Minimum Scope |
|------|-------------|---------------|
| **Publications** | ✅ Required | All files in `figures/` and any file appearing in manuscript |
| **Projects** | 🔶 Recommended | Files intended for publication, sharing, or reuse |
| **Curated Datasets** | ✅ Required | All label/output files; every item must trace to RAW |

### 6.2 What Can Be Skipped

| File Type | Log Required? | Reason |
|-----------|---------------|--------|
| Boilerplate (`_publication.yaml`, `provenance.csv`) | ❌ No | System files |
| Scratch/temporary files | ❌ No | Not retained |
| Exploratory analysis (not used) | ❌ No | Discretionary |
| Documentation (protocols, notes) | ❌ No | Not derived from data |

### 6.3 Closure Requirement

Before a publication folder can be "closed":

- [ ] Every file in `figures/` has a provenance entry
- [ ] All `FILE-*` references resolve to existing entries
- [ ] All `ACQ-*` references exist in raw registry

---

## 7. Workflow Integration

### 7.1 When to Log

| Approach | Description | Trade-offs |
|----------|-------------|------------|
| **Log as you go** | Add entry immediately when creating file | Most accurate; requires discipline |
| **Batch at milestones** | Log multiple files at end of work session | Less interruption; may forget details |
| **Log before submission** | Complete provenance before manuscript submission | Concentrated effort; may miss details |

> **🔶 RECOMMENDATION:** Log as you go, especially for complex processing. A helper tool can reduce friction.

### 7.2 Helper Tool Concept

> **📋 Planned:** `log_activity` script to streamline logging.

```bash
# Example usage concept
log_activity \
  --output figures/fig1.tiff \
  --inputs "ACQ-20260115-ZWSI-001;methods/params.json" \
  --process "ROI extraction with contrast adjustment" \
  --software "ImageJ 1.54f" \
  --creator MBC
```

The script would:
- Generate next FILE-ID
- Validate input references
- Append to provenance.csv
- Optionally prompt for missing fields

---

## 8. Provenance for Multiple Outputs

If a single process creates multiple outputs, log each output as a separate row with the same inputs and process:

```csv
file_id,output_path,...,input_refs,process_description,...
FILE-0010,figures/panel_a.tiff,...,ACQ-001,Split multi-channel image into panels,...
FILE-0011,figures/panel_b.tiff,...,ACQ-001,Split multi-channel image into panels,...
FILE-0012,figures/panel_c.tiff,...,ACQ-001,Split multi-channel image into panels,...
```

---

## 9. Related Documents

- [04_PUBLICATIONS](04_PUBLICATIONS.md) — Where provenance is required
- [05_PROJECTS](05_PROJECTS.md) — Where provenance is recommended
- [12_CURATED_DATASETS](12_CURATED_DATASETS.md) — Where provenance is required (for labels)
- [10_TOOLS](10_TOOLS.md) — Provenance logging helper

---

## Open Questions Summary

| ID | Question | Owner | Status |
|----|----------|-------|--------|
| PROV-01 | Is this level of detail feasible for routine work? | Users | 📣 Need feedback |
| PROV-02 | What's the minimum viable provenance for pilot? | Data Mgmt Lead | 🔶 Current spec may be minimum |
| PROV-03 | Helper tool priority | Data Mgmt Lead | 📋 Planned |
| PROV-04 | How to handle provenance for collaborative files (multiple creators)? | Data Mgmt Lead | 🔶 Use primary creator |
