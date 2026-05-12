# 05 — Projects Area

**Parent:** [Documentation Index](00_INDEX.md)
**Status:** 🔶 Draft
**Last Updated:** 2026-05-12

---

## Purpose

This document specifies the Projects storage area — a temporary, documented workspace for organized research work that doesn't yet belong to a specific publication.

---

## 1. Scope and Constraints

The Projects area provides semi-structured workspaces on gjesus3 for ongoing research. It bridges the gap between raw data deposits and formal publication packages.

**What Projects are for:**
- Organizing work that spans multiple potential publications
- Working on data before it becomes publication-ready
- Holding researcher-supplied **study-level metadata** (the experimental context that isn't captured at ingest — see [08_METADATA §1](08_METADATA.md))
- Tracking provenance for work-in-progress
- Shared workspace within the group

> **⚠️ Important — projects are ephemeral.** `/projects/` is **temporary working space**, not permanent archive. Projects are created, used, and then closed and **deleted**. Only `/raw/` and `/publications/` are permanent archives. Anything in a project folder that needs to survive long-term (most importantly the **study-level metadata** in `metadata/`) must be preserved into the permanent archive at close-out — see §4 and [08_METADATA §1.3](08_METADATA.md). The Data Mgmt Lead is responsible for the preservation step.

**Known limitations:**
- gjesus3 is accessible only from specific hardwired on-site machines (not laptops)
- RAID 5 write performance is not optimized for heavy interactive analysis
- This is archival-grade storage, not a primary working drive

Researchers who do most of their analysis on local machines or other drives can still benefit from Projects as a place to organize and document results that will eventually feed into Publications.

---

## 2. Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Temporary workspace** | Projects have defined lifespans; not permanent storage |
| **Documented but flexible** | Provenance logged; internal structure is researcher-discretion |
| **Leads somewhere** | Projects should culminate in Publications, exports, or explicit closure |

---

## 3. Directory Structure

```
/gjesus3/
├── registries/
│   └── registry_projects.csv           # Projects registry (see 06_REGISTRIES)
│
└── projects/
    └── proj-ipf-biomarkers/
        ├── _project.yaml
        ├── provenance.csv
        ├── raw_linked/                 # Windows .lnk shortcuts to raw acquisitions
        │   └── ...                     # (created by ingest_raw.py when project_hint set — see 10_TOOLS §2.1.1)
        ├── metadata/                   # Study-level metadata (researcher-supplied)
        │   ├── study.json              #   study aim, hypothesis, principal contact
        │   ├── biosamples.json         #   biosample-level details (strain, age, sex, treatment)
        │   └── <acq_id>.json           #   optional per-acquisition supplements
        └── ... (researcher-organized analysis output, notes, working files)
```

`metadata/` is **the only place researchers should edit study-level metadata.** It is the writeable counterpart to the read-only `/raw/<ACQ-ID>/metadata.json` sidecars. Architecture rationale in [08_METADATA §1](08_METADATA.md). The file shapes (`study.json`, `biosamples.json`, per-acq supplements) are deferred to the Excel-import tool spec — see `tasks/tasks.md` §3.2.

---

## 4. Project Lifecycle

```
Created ──▶ Active ──▶ Paused ──▶ Closed ──▶ DELETED
                  │
                  └──▶ Promoted to Publication
```

**Closure options:**
- **Promoted:** Work moved to a Publication folder; project archived or deleted
- **Exported:** Data copied out to external storage; project deleted
- **Abandoned:** No further work; project deleted after retention period

### 4.x Close-out: preserving study-level metadata

Whatever the closure path, **`/projects/<proj>/metadata/` does not get to disappear with the project folder.** The study-level metadata in there is critical for long-term archive value of the raw acquisitions (without it, future analysts won't know what experiment the imaging belonged to).

Mechanism (intended; tracked in `tasks/tasks.md` §3.2):

1. The Data Mgmt Lead runs a close-out tool against the project before deletion.
2. The tool reads `/projects/<proj>/metadata/` and merges its contents into the corresponding `/raw/<ACQ-ID>/metadata.json` files (per the architecture in [08_METADATA §1.3](08_METADATA.md)) — a controlled, one-time admin write to `/raw/`. The merge is additive only; nothing in the existing acquisition-level metadata is overwritten.
3. If the project produced a publication, the close-out tool also stages a copy of the study metadata into the publication folder for the publication record.
4. After both writes verify, the project folder is deleted.

Until this tool exists, projects should not be deleted — pause them indefinitely if needed, and flag the Data Mgmt Lead.

---

## 5. Retention

> **✅ DECIDED:** Projects are temporary and **deleted** at close-out — they are not part of the permanent archive.
> - Active: No limit
> - Paused: 6-month maximum
> - After 6 months paused: Require decision (promote, export, or delete)
>
> Project deletion is **blocked** until close-out preserves the study-level metadata into `/raw/` (and, where applicable, `/publications/`). See §4.x.

---

## 6. Provenance

> **✅ DECIDED:** Provenance is recommended but not required.

Same format as Publications (see [07_PROVENANCE](07_PROVENANCE.md)), but:
- Less strict enforcement during active work
- Required for any file intended for publication or external sharing

An empty `provenance.csv` with headers is created at project setup.

---

## 7. Project Metadata File

**File:** `_project.yaml`

```yaml
project_id: PROJ-0001
short_name: ipf-biomarkers
description: "IPF biomarker quantification study"
status: active  # active | paused | closed
owner: MBC

# Timeline
start_date: 2026-03-01
last_activity: 2026-03-01
closed_date: null

# Outcome (filled at closure)
outcome: null  # promoted | exported | abandoned
promoted_to: null  # e.g., PUB-0003

# Notes
notes: |
  Initial exploratory analysis of IPF biomarker data.
```

---

## 8. Registry Fields

See [06_REGISTRIES](06_REGISTRIES.md) Section 4 for full schema. Key fields:

| Field | Type | Required |
|-------|------|----------|
| `project_id` | String | Yes |
| `short_name` | String | Yes |
| `description` | Text | Yes |
| `owner` | String | Yes |
| `start_date` | Date | Yes |
| `status` | Enum | Yes |
| `last_activity` | Date | Auto |
| `folder_location` | String | Yes |
| `notes` | String | Optional |

---

## 9. Naming Conventions

### 9.1 Project ID

**Pattern:**
```
PROJ-<NNNN>
```

| Component | Description | Example |
|-----------|-------------|---------|
| `PROJ` | Fixed prefix | `PROJ` |
| `<NNNN>` | Sequential number (4 digits) | `0001`, `0042` |

**Example:** `PROJ-0001`

The PROJ-ID is used in the registry. The folder uses a **short name** for human readability.

### 9.2 Folder Short Name

**Requirements:**
- Unique across all project folders
- Human-readable (describes the project)
- Filesystem-safe: lowercase, hyphens, no spaces
- Prefixed with `proj-` in the folder name

**Pattern:**
```
proj-<short_name>
```

**Examples:**
- `proj-ipf-biomarkers`
- `proj-tumor-segmentation-eval`
- `proj-pet-mri-fusion`

---

## 10. Tooling

**Script:** `tools/create_project.py`

Creates a new project folder with required structure and registry entry. See [10_TOOLS](10_TOOLS.md) for full specification.

**Usage:**
```bash
python tools/create_project.py \
  --name "ipf-biomarkers" \
  --description "IPF biomarker quantification study" \
  --owner MBC

python tools/create_project.py --interactive
```

---

## 11. Related Documents

- [01_OVERVIEW](01_OVERVIEW.md) — System scope decisions
- [04_PUBLICATIONS](04_PUBLICATIONS.md) — Where finished work goes
- [06_REGISTRIES](06_REGISTRIES.md) — Projects registry schema
- [07_PROVENANCE](07_PROVENANCE.md) — Provenance format
- [10_TOOLS](10_TOOLS.md) — Project creation script

---

## Open Questions Summary

| ID | Question | Owner | Status |
|----|----------|-------|--------|
| PROJ-01 | Include Projects area in pilot? | PI + Data Mgmt Lead | ✅ Resolved — included |
| PROJ-02 | What retention policy? | PI | ✅ Resolved — 6-month paused review |
| PROJ-03 | How strict on provenance? | Data Mgmt Lead | ✅ Resolved — recommended, not required |
| PROJ-04 | Where do researchers actually work now? | Users | 📣 Need input |
