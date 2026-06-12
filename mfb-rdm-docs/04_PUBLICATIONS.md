# 04 — Publications Area

**Parent:** [Documentation Index](00_INDEX.md)  
**Status:** 🔶 Draft  
**Last Updated:** 2026-02-02

---

## Purpose

This document specifies the structure, conventions, and workflows for the Publications storage area — the archive for publication-related data packages.

---

## 1. Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Long-term preservation** | Publication folders become static after publication |
| **Self-contained packages** | Each publication folder contains (or links to) everything needed to reproduce figures |
| **Provenance required** | Every non-boilerplate file has documented origin |
| **Flexible until closed** | Internal structure can evolve during preparation; rigidity only at closure |

---

## 2. Directory Structure

```
/gjesus3/
├── registries/
│   └── registry_publications.csv       # Publication registry (see 06_REGISTRIES)
│
└── publications/
    ├── lung-fibrosis-markers-2026/         # Publication folder (short name)
    │   ├── _publication.yaml               # Publication metadata
    │   ├── provenance.csv                  # Local provenance log
    │   ├── raw_linked/                     # Windows .lnk shortcuts to source raw acquisitions (see Section 5)
    │   │   ├── ACQ-20260115-ZWSI-001      # Link or reference to raw acquisition
    │   │   └── ACQ-20260116-ZWSI-002      # ...
    │   ├── figures/                        # Final publication figures
    │   │   ├── fig1_panel_a.tiff
    │   │   ├── fig1_panel_b.tiff
    │   │   └── ...
    │   ├── analysis/                       # Analysis outputs (intermediate OK)
    │   │   ├── segmentation_results.csv
    │   │   └── statistical_analysis.xlsx
    │   ├── methods/                        # Protocols, scripts, parameters
    │   │   ├── analysis_pipeline.py
    │   │   └── imaging_protocol.pdf
    │   └── manuscript/                     # Optional: manuscript files
    │       └── ...
    │
    └── tumor-margin-quantification-2026/
        └── ...
```

### 2.1 Required Contents

| Item | Required | Created When |
|------|----------|--------------|
| `_publication.yaml` | ✅ Yes | At folder creation |
| `provenance.csv` | ✅ Yes | At folder creation (empty template) |
| `raw_linked/` | ✅ Yes | At folder creation; populated during work |
| Final figures | ✅ Before closure | During preparation |
| Provenance entries for figures | ✅ Before closure | During preparation |

### 2.2 Optional but Recommended

| Item | Purpose |
|------|---------|
| `figures/` | Organized location for publication-ready outputs |
| `analysis/` | Intermediate analysis files |
| `methods/` | Scripts, protocols, parameter files |
| `manuscript/` | Draft manuscripts, supplementary materials |

> **📣 INPUT NEEDED:** Is this folder structure useful, or do researchers prefer flat organization?

---

## 3. Naming Conventions

### 3.1 Publication ID

**Pattern:**
```
PUB-<NNNN>
```

| Component | Description | Example |
|-----------|-------------|---------|
| `PUB` | Fixed prefix | `PUB` |
| `<NNNN>` | Sequential number (4 digits) | `0001`, `0042` |

**Example:** `PUB-0001`

The PUB-ID is used in the registry. The folder uses a **short name** for human readability.

### 3.2 Folder Short Name

**Requirements:**
- Unique across all publication folders
- Human-readable (describes the publication)
- Filesystem-safe: lowercase, hyphens, no spaces
- Ideally stable (chosen before the official title is finalized)

**Pattern suggestion:**
```
<topic>-<distinguisher>-<year>
```

**Examples:**
- `lung-fibrosis-markers-2026`
- `tumor-margin-quantification-2026`
- `pet-mri-fusion-methods-2026`

---

## 4. Publication Lifecycle

```
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│   Created     │ ──▶ │  In Progress  │ ──▶ │    Closed     │
│   (PUB-ID)    │     │   (active)    │     │  (published)  │
└───────────────┘     └───────────────┘     └───────────────┘
       │                     │                      │
  Folder created       Work ongoing            Read-only
  Template files       Provenance logged       DOI recorded
  Registered           Raw data linked         Repository linked
```

### 4.1 Creation

1. **Decide short name** based on expected publication topic
2. **Run creation script** (or manual setup):
   - Creates folder with template structure
   - Creates empty `provenance.csv` with headers
   - Creates `_publication.yaml` template
   - Adds entry to `registry_publications.csv`
3. **Complete metadata** in `_publication.yaml`

### 4.2 In Progress

- **Link raw data:** Add Windows `.lnk` shortcuts to source acquisitions in `raw_linked/` (see Section 5)
- **Log provenance:** Every derived file added to folder gets a provenance entry
- **Iterate freely:** Internal structure can change; update provenance as needed

### 4.3 Closure

Closure happens when the paper is published (or abandoned). Required steps:

1. **Verify provenance completeness:**
   - Every figure file has a provenance entry
   - All input references resolve to valid raw data or other logged files
2. **Update metadata:**
   - Final title
   - DOI (when available)
   - Repository link (Zenodo, etc.) if data deposited externally
   - Status → `published` or `abandoned`
   - Closed date
3. **Lock folder:** Set read-only permissions
4. **Update registry:** Final status and links

> **🔶 DRAFT:** Closure checklist and automation not yet defined.

---

## 5. Linking Raw Data

### 5.1 Purpose

The `raw_linked/` folder creates a clear connection between this publication and its source data without duplicating files.

### 5.2 Method — Windows `.lnk` shell shortcuts

> **✅ DECIDED — NTFS/SMB hard links (2026-06-02; supersedes the original Windows `.lnk` choice):** Links use **NTFS/SMB hard links** (the project copy is a real shared-inode file). Same convention as projects (see [05_PROJECTS](05_PROJECTS.md) and [10_TOOLS §2.1.1](10_TOOLS.md#211-project-linking--hard-links-current-over-lnk-shortcuts)); the original `.lnk` shell shortcuts remain the porting seam. This is a **pilot-specific** choice for the gjesus3 environment (Windows user base, no SSH-into-NAS); see the full rationale and porting guide in [10_TOOLS §2.1.1](10_TOOLS.md#211-project-linking--hard-links-current-over-lnk-shortcuts). (The publications linking tool is future work — `create_publication`; it will follow the same hard-link mechanism.)

For each linked acquisition, `raw_linked/` contains one `.lnk` file named with the original archive name (e.g. `LEONE_1.01.zip.lnk`), targeting the canonical archive on the NAS via UNC path. Windows users browsing via SMB see familiar names with the right icon and can double-click to open. Scripts and non-Windows tooling should consume the canonical paths via `registry_raw.csv` (or the per-publication provenance log) rather than following `.lnk` files.

---

## 6. Provenance Logging

> Full specification in [07_PROVENANCE](07_PROVENANCE.md).

### 6.1 Summary

Every file added to the publication folder (except boilerplate like `_publication.yaml`) should have a provenance entry documenting:

- What the file is (path, type)
- Where it came from (inputs — raw ACQ-IDs and/or other files)
- How it was created (process description, software, parameters)
- Who created it and when

### 6.2 Minimum at Closure

Before a publication can be closed:

- [ ] All files in `figures/` have provenance entries
- [ ] Provenance chains trace back to raw ACQ-IDs
- [ ] Process descriptions are sufficient to understand transformations

---

## 7. Metadata

### 7.1 Publication Metadata File

**File:** `_publication.yaml`

```yaml
pub_id: PUB-0001
short_name: lung-fibrosis-markers-2026
working_title: "Quantification of fibrotic markers in IPF lung tissue"
status: in_progress  # created | in_progress | submitted | published | abandoned

# Authorship
pi: Jesús Ruiz-Cabello
first_author: Marta Beraza
corresponding_author: Jesús Ruiz-Cabello

# Timeline
created_date: 2026-02-15
submitted_date: null
published_date: null
closed_date: null

# Publication details (filled when known)
journal: null
doi: null
pmid: null

# Data availability
repository: null  # e.g., https://zenodo.org/record/XXXXXX
repository_doi: null

# Notes
notes: |
  Initial work on IPF biomarker quantification.
  Collaboration with Hospital Universitario Donostia.
```

### 7.2 Registry Fields

See [06_REGISTRIES](06_REGISTRIES.md) for full schema. Key fields:

| Field | Type | Required |
|-------|------|----------|
| `pub_id` | String | Yes |
| `short_name` | String | Yes |
| `working_title` | String | Yes |
| `status` | Enum | Yes |
| `pi` | String | Yes |
| `first_author` | String | Yes |
| `created_date` | Date | Yes |
| `doi` | String | When published |
| `folder_location` | Path | Yes |

---

## 8. Long-Term Retention

### 8.1 On gjesus3

Publication folders remain on gjesus3 indefinitely (space permitting).

### 8.2 External Repository

> **✅ DECIDED:** Publication data should be deposited to an external repository (e.g., Zenodo) for:
> - Persistent access independent of lab infrastructure
> - DOI for citation
> - Compliance with journal data availability requirements

### 8.3 Offline Archival

If space becomes constrained:
1. Verify external repository contains complete data
2. Update registry with repository link
3. Move to offline storage (external drive, cold cloud)
4. Update `folder_location` in registry

---

## 9. Related Documents

- [06_REGISTRIES](06_REGISTRIES.md) — Publication registry schema
- [07_PROVENANCE](07_PROVENANCE.md) — Provenance logging specification
- [10_TOOLS](10_TOOLS.md) — Publication creation script

---

## Open Questions Summary

| ID | Question | Owner | Status |
|----|----------|-------|--------|
| PUB-01 | Is suggested folder structure useful or too prescriptive? | Users | 📣 Need input |
| PUB-02 | Closure checklist and automation | Data Mgmt Lead | 🔶 Draft |
| PUB-03 | Zenodo workflow integration | Data Mgmt Lead | 📋 Future |
| PUB-04 | How to handle publication packages that grow very large? | PI | 🔶 Draft |
| ~~PUB-05~~ | ~~Raw data linking method: symlinks, hard links, or text reference list?~~ | — | ✅ Resolved: **NTFS/SMB hard links** (2026-06-02; superseded the original `.lnk` pilot choice; see [10_TOOLS §2.1.1](10_TOOLS.md#211-project-linking--hard-links-current-over-lnk-shortcuts)) |
