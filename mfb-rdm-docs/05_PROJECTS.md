# 05 — Projects Area

**Parent:** [Documentation Index](00_INDEX.md)
**Status:** 🔶 Draft — except **§2a (Project Reference Model), which is ✅ DECIDED.**
**Last Updated:** 2026-08-12 (**§3** — the recommended subfolders `raw_linked/` · `working/` · `outputs/` · `metadata/` are now created by every tool that makes a project and were backfilled onto the existing ones; the 🕗 note is **narrowed** from "`metadata/` does not exist" to "the directory exists, its *contents* stay deferred". **§7** states which copy is authoritative. **§10** records the ✅ 2026-08-11 decision that anyone with access may create a project — through the system — and names the Project Manager GUI. Prior: 2026-08-02 (new **§2a Project Reference Model** — the owning section for how a project is referred to: `project_id` + `name`, case-insensitive resolution, **folder == name verbatim**, one construction site. Retires the "project hint" vocabulary and the `proj-` folder prefix; §9 now covers the naming *convention* only. Prior: 2026-06-26.)

---

## Purpose

This document specifies the Projects storage area — a temporary, documented workspace for organized research work that doesn't yet belong to a specific publication.

---

## 1. Scope and Constraints

The Projects area provides semi-structured workspaces on gjesus3 for ongoing research. It bridges the gap between raw data deposits and formal publication packages.

**What Projects are for:**
- Organizing work that spans multiple potential publications
- Working on data before it becomes publication-ready
- Reaching the project's raw acquisitions through hard links (see §3) — every project that was populated via `ingest_raw.py` carries a hard-linked copy of each acquisition it owns
- Holding researcher-supplied **study-level metadata** (the experimental context that isn't captured at ingest — see [08_METADATA §1](08_METADATA.md)) — 🕗 **PLANNED/DEFERRED** (Phase 4); see §3 and [tasks/BACKLOG.md](../tasks/BACKLOG.md)
- Tracking provenance for work-in-progress
- Shared workspace within the group

> **⚠️ Important — projects are ephemeral.** `/projects/` is **temporary working space**, not permanent archive. Projects are created, used, and then closed and **deleted**. Only `/raw/` and `/publications/` are permanent archives. Anything in a project folder that needs to survive long-term (most importantly the **study-level metadata** in `metadata/`, once that layer is in use) must be preserved into the permanent archive at close-out — see §4 and [08_METADATA §1.3](08_METADATA.md). The Data Mgmt Lead is responsible for the preservation step.

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

## 2a. Project Reference Model

> **✅ DECIDED 2026-08-02.** This section **owns** the concept "how a project is
> referred to" — its vocabulary, its resolution rule, and its consumers. Anything
> that names or locates a project cites this section. The concept previously had
> no owning section, which is how the vocabulary drifted into a different word
> per layer (see §2a.5).

### 2a.1 A project has exactly two identifiers

| Identifier | Form | Role |
|---|---|---|
| **`project_id`** | `PROJ-XXXX` | **Machine key.** Immutable, systematic, assigned at creation. This is what `registry_raw.csv` stores, and what every join uses. |
| **`name`** | human-readable, unique case-insensitively, OS-safe, hyphens not spaces | **Human key.** What operators type, what everyone says — **and the folder name, verbatim.** |

There is no third thing. In particular there is **no "hint"**: what an operator
supplies is the project's *name*, and the system resolves it to the *id*.

### 2a.2 Vocabulary by layer

| Layer | Name |
|---|---|
| GUI field label | **"Project name"** |
| Config / recipe key | **`registry.project_name`** |
| `registry_projects.csv` column | **`name`** |
| Folder under `/projects/` | **the name, verbatim** |
| `registry_raw.csv` column | **`project_id`** (holds the resolved `PROJ-XXXX`) |
| `link_filename:` tokens | **`${project_name}`** (human) · **`${project_id}`** (machine) |
| `_project.yaml` key | **`name:`** |

Note the deliberate asymmetry: the operator's **input** is a name; the **stored**
column is an id. Step 9.5 of the ingest is where one becomes the other. A column
called `project_name` holding `PROJ-0011` would be a lie — which is exactly the
mistake this model corrects.

### 2a.3 Resolution rule

Operator input under `registry.project_name` is matched against:

1. an existing project's **`name`**, **case-insensitively** (the NAS filesystem
   is case-insensitive, so two spellings can never be two folders), or
2. a literal **`PROJ-XXXX`** id.

On a match the pipeline attaches to that project. On no match, and with
`ingest.auto_create_projects: true`, it **auto-creates** a project named exactly
as typed (after space → hyphen), with a folder of the same name. With
auto-create off, the acquisition is registered with **no** project — a blank
`project_id` and no link — and the ingest logs a WARN saying so.

After resolution the pipeline carries **both** identifiers: `project_id` (the
resolved id, written to the registry) and `project_name` (the **canonical** name
read back from `registry_projects.csv`). Canonicalization matters: an operator
who typed `ae-biomagune-1123`, or who referenced the project by id, still gets
`AE-biomaGUNE-1123` in link names and logs.

**Name rules.** A name must be a legal single path component, because it *is* the
folder: no `\ / : * ? " < > |`, no control characters, no leading/trailing space
or dot, max 60 characters. Spaces are converted to hyphens — the GUI does this
live as the operator types, so what they see is what gets created.

### 2a.4 Invariants

- folder basename **==** `name`
- `folder_location` **==** `/projects/<name>/`
- `registry_raw.project_id` ∈ `registry_projects.project_id` (or blank)
- names are unique **case-insensitively**

**One construction site.** [`tools/ingest/project_naming.py`](../tools/ingest/project_naming.py)
is the only place that knows how a name becomes a path; `create_project.py` is
the only thing that creates a project. **Every other consumer reads the stored
`folder_location`** — never rebuilds a path from a name.

### 2a.5 Consumers

| Consumer | What it uses |
|---|---|
| [`ingest_raw.py`](../tools/ingest_raw.py) Step 9.5 | resolves `project_name` → `project_id` + canonical name; auto-creates |
| [`ingest/linker.py`](../tools/ingest/linker.py) | `resolve_project` → `(project_id, name, folder_location)`; `lookup_project_folder` for the link path |
| [`ingest/registry.py`](../tools/ingest/registry.py) | writes the `project_id` column (mirror: [06_REGISTRIES §2.2](06_REGISTRIES.md)) |
| [`ingest/resolver.py`](../tools/ingest/resolver.py) | accepts `registry.project_name`; offers both link tokens (mirror: 06_REGISTRIES) |
| [`create_project.py`](../tools/create_project.py) | validates the name, derives the folder, writes `name` + `folder_location` |
| [`operator/collisions.py`](../tools/operator/collisions.py) | groups by name (case-insensitively); reads the stored folder |
| [`operator/value_fields.py`](../tools/operator/value_fields.py) + the GUI | the "Project name" field and its space→hyphen conversion |
| [`generate_index.py`](../tools/generate_index.py) · [`find_acq.py`](../tools/find_acq.py) | group/join by `project_id`; `--project` accepts id **or** name |
| [`gather_metadata.py`](../tools/gather_metadata.py) · [`metadata_completeness.py`](../tools/metadata_completeness.py) | `--project` accepts id or name |
| [`validate_registries.py`](../tools/validate_registries.py) | checks `project_id` exists in the projects registry |

### 2a.6 What this replaced

Until 2026-08-02 the operator field was called a **"project hint"**, the stored
column was `project_hint` (though it held ids), the projects-registry column was
`short_name`, and the folder was `proj-` + `lower(short_name)` — so the folder an
operator opened never matched the name the GUI showed them. Three separate places
implemented the folder rule and drifted apart. The old key `registry.project_hint`
is **not accepted** (no deprecated alias): it raises the resolver's unknown-key
error listing the allowed keys, so a stale config fails loudly. Migration record:
[CHANGELOG.md](../CHANGELOG.md), 2026-08-02.

---

## 3. Directory Structure

```
/gjesus3/
├── registries/
│   └── registry_projects.csv           # Projects registry (see 06_REGISTRIES)
│
└── projects/
    └── ipf-biomarkers/                   # folder == the project name, verbatim (§2a)
        ├── _project.yaml
        ├── provenance.csv
        ├── index.html                  # per-project searchable finder (refreshed on ingest into this project — see tools/FINDER.md)
        ├── raw_linked/                 # hard links to raw acquisitions (NOT shortcuts)
        │   └── ...                     # (created by ingest_raw.py when a project resolves — see 10_TOOLS §2.1.1;
        │                               #  link filename comes from the per-instrument `link_filename:`
        │                               #  template — see 10_TOOLS §2.1.5)
        ├── working/                    # scratch and in-progress analysis
        ├── outputs/                    # results worth keeping: figures, derived images, reports
        ├── metadata/                   # study-level metadata — DIRECTORY CREATED; contents 🕗 PLANNED/DEFERRED
        │   ├── study.json              #   🕗 study aim, hypothesis, principal contact
        │   ├── biosamples.json         #   🕗 biosample-level details (strain, age, sex, treatment)
        │   └── <acq_id>.json           #   🕗 optional per-acquisition supplements
        └── ... (researcher-organized analysis output, notes, working files)
```

**The four subfolders are the recommended convention (2026-08-12).** Every tool that creates a project makes all four (`create_project.py` → `ingest/project_layout.py`, which is the one definition), and [`tools/backfill_project_subfolders.py`](../tools/backfill_project_subfolders.py) added them to the projects that predate the convention. One line each:

| Folder | What belongs in it |
|---|---|
| `raw_linked/` | Hard links to raw acquisitions. **Tool-managed** — don't hand-edit. |
| `working/` | Scratch and in-progress analysis. |
| `outputs/` | Results worth keeping: figures, derived images, reports. |
| `metadata/` | Study-level metadata. Directory created; **contents still deferred** (below). |

It is a *recommendation made real*, not a rule: nothing fails because a project has extra folders, and no tool deletes what a researcher put there.

> **🕗 PLANNED/DEFERRED — the study-metadata LAYER, not the directory.** Since 2026-08-12 `metadata/` itself **is** created (empty) on every project. What stays deferred is everything that would fill it: the writers (Excel → study-metadata importer, `gather_metadata.py`, close-out merge) and the file shapes (`study.json`, `biosamples.json`, per-acq supplements). As of the current state the layer's *contents* exist on **none** of the live projects. Architecture rationale in [08_METADATA §1](08_METADATA.md); the writer family and their status are in [08_METADATA §1.5a](08_METADATA.md); the file shapes are deferred to the Excel-import tool spec — see [tasks/BACKLOG.md](../tasks/BACKLOG.md). When the layer ships, `metadata/` will be **the only place researchers should edit study-level metadata.**

**`raw_linked/` uses hard links, not Windows shortcuts.** Each entry is a real filesystem hard link to the acquisition's primary entity in `/raw/` — to a researcher it looks and opens exactly like the original file (or folder, via a per-file-hard-linked `.data/`), with no extra disk space consumed and no broken-shortcut failure mode. This superseded the earlier `.lnk` shortcut method (DECIDED + APPLIED 2026-06-02). Mechanism in [10_TOOLS §2.1.1](10_TOOLS.md).

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

Whatever the closure path, **`/projects/<proj>/metadata/` does not get to disappear with the project folder.** The study-level metadata in there is critical for long-term archive value of the raw acquisitions (without it, future analysts won't know what experiment the imaging belonged to). (This applies once the `metadata/` layer is in use — see the 🕗 note in §3.)

Mechanism (intended; tracked in [tasks/BACKLOG.md](../tasks/BACKLOG.md)):

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

> **✅ DECIDED:** Provenance is recommended for manual analysis output; **required** for any file written into the project by a tool or script (see [07_PROVENANCE §2.1](07_PROVENANCE.md)).

Same format as Publications (see [07_PROVENANCE](07_PROVENANCE.md)):
- An empty `provenance.csv` with the canonical 12-field header is created at project setup by `create_project.py`.
- Any tool that adds/removes/changes files under the project (today: `ingest_raw.py` Step 12 writing **hard links** into `raw_linked/`; tomorrow: the Excel-to-metadata importer and the close-out tool) auto-appends a provenance row. The schema lives in `tools/ingest/provenance.py` so writers stay aligned.
- Manual analysis output: still strongly recommended; required for anything that will feed into a publication or external sharing.

---

## 7. Project Metadata File

**File:** `_project.yaml`

```yaml
project_id: PROJ-0001
name: ipf-biomarkers
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

**Which copy is authoritative — ✅ the registry row.** `description`, `owner`, `status` and `notes` live in **both** `registry_projects.csv` and this file; they are meant to agree. `registry_projects.csv` is the record the tools read (the Finder joins against it, `linker` resolves folders from it); `_project.yaml` is the copy a researcher sees when they open the folder. **Any tool that edits one edits both** — the Project Manager GUI writes the registry row first and then rewrites the matching keys here, preserving this file's comments. If a folder has no `_project.yaml` (five pre-`create_project.py` folders don't) the registry edit still applies and the tool says so. Where the two disagree, the registry row wins.

**Never stamped by an edit: `start_date` and `last_activity`.** Since the 2026-07-14/15 production update these mean **acquisition** dates — the project's first and newest acquisition — not ingest or edit dates. Editing a description must not move `last_activity`; no editing tool may write either field.

**Auto-population at ingest-time creation.** When a project is auto-created by `ingest_raw.py` (with `ingest.auto_create_projects: true`), the ingest config's optional `auto_create_project:` block supplies the initial values for `owner`, `description`, and `notes` — resolver-evaluated, so they can pull from `discovered.<field>` parsed from filenames or paths. See [10_TOOLS §2.1.4](10_TOOLS.md). **First-write-wins:** the block is read only on the project's initial creation; subsequent ingests touching the same project ignore it. The source of truth after creation is this `_project.yaml` file — edit it directly to correct or extend the auto-populated values.

---

## 8. Registry Fields

See [06_REGISTRIES](06_REGISTRIES.md) Section 4 for full schema. Key fields:

| Field | Type | Required |
|-------|------|----------|
| `project_id` | String | Yes |
| `name` | String | Yes |
| `description` | Text | Yes |
| `owner` | String | Yes |
| `start_date` | Date | Yes |
| `status` | Enum | Yes |
| `last_activity` | Date | Auto |
| `folder_location` | String | Yes |
| `notes` | String | Optional |

---

## 9. Naming Conventions

> **⚠️ OPEN — project naming requires group consensus.**
>
> A project's `name` (§2a) is the **human-meaningful** identifier the group will use every day — and it is the folder they open — so it should map to a durable unit of work that everyone recognizes. Candidates include funded project names, animal-project approval IDs (e.g. `AE-biomaGUNE-NNNN`), or explicit internal names the group agrees on.
>
> **This section is about the *convention* — which words make a good name. The *mechanics* of naming (the two identifiers, resolution, the folder rule) are settled in [§2a](#2a-project-reference-model).**
>
> **Experiments, assays, and studies are NOT projects.** A project typically *contains* many experiments, assays, or studies over its lifetime. Using an experiment label as the project name produces sprawling, low-value project folders that fragment work and obscure the actual scope.
>
> **Provisional patterns currently in use during the pilot:**
>
> | Instrument / batch | Provisional name pattern | Status |
> |--------------------|----------------------------------|--------|
> | AxioScan 7 (round-4) | `AE-biomaGUNE-NNNN` (animal-project code) | 🔶 Reasonable interim — animal-project codes are durable units |
> | Cell Observer (round-5 cells-mode) | `${researcher}-${experiment}` (e.g. `itziar-alphasma`) | ⚠️ **Stopgap only** — experiment is not a project |
>
> **Required next step:** Convene the relevant project-lead users to converge on a real naming convention before the pilot scales out. Only the project-lead users can decide what's meaningful for organizing *their* work; the data office cannot make this call for them. The system's value compounds once a consistent convention is in place — researchers will find their raw data, intermediates, and projects via these names, so the name needs to bear real meaning. Tracked as an open question in [00_INDEX.md](00_INDEX.md).

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

The PROJ-ID is the machine key stored in `registry_raw.csv`. The folder uses the project **name** — see [§2a](#2a-project-reference-model).

### 9.2 Folder Name

**The folder name IS the project name, verbatim** — no prefix, casing preserved
(✅ DECIDED 2026-08-02; the rule and its rationale are in [§2a](#2a-project-reference-model)).

**Requirements:**
- Unique across all project folders (case-insensitively — the NAS filesystem is)
- Human-readable (describes the project)
- Filesystem-safe: no `\ / : * ? " < > |`, no leading/trailing space or dot, max 60 chars
- Spaces are converted to hyphens (live, as the operator types)

**Pattern:**
```
<name>
```

**Examples:**
- `ipf-biomarkers`
- `AE-biomaGUNE-1123`
- `tumor-segmentation-eval`

---

## 10. Tooling

**Who may create a project — ✅ DECIDED 2026-08-11.** **Anyone with access to gjesus3 may create a project — but only through the system.** What is centralised is the *mechanism*, not the *permission*: nobody hand-makes a folder in `projects/`, because creation through a tool is what keeps the registry row, the folder name, the required subfolders and `_project.yaml` consistent with each other. This is a smaller change than it sounds — it was already true in practice, since any operator running an ingest with `auto_create_projects: true` could mint one. The front doors are the **Project Manager GUI** (researchers) and `create_project.py` (data office).

> **🕗 Ownership is typed in, not verified.** An exe on a shared workstation doesn't know who is sitting at it, so `owner` is an ordinary editable field. Owner-on-create and per-project edit rights arrive with the RDM server — tracked in [`tasks/BACKLOG.md`](../tasks/BACKLOG.md) ("Server-era identity"). Keep `owner` editable so that lands without a migration.

**Front-end:** `tools/manager/gui/` — the Project Manager GUI (researcher-facing; also updates a project, and imports data into one). See [10_TOOLS §5.3](10_TOOLS.md).

**Script:** `tools/create_project.py`

Creates a new project folder with the recommended structure (§3) and the registry entry. The whole read-decide-write runs under the registry lock, so two people creating a project at the same moment cannot mint the same `PROJ-NNNN` or both claim one name. See [10_TOOLS](10_TOOLS.md) for full specification.

**Usage:**
```bash
python tools/create_project.py \
  --name "ipf-biomarkers" \
  --description "IPF biomarker quantification study" \
  --owner MBC

python tools/create_project.py --interactive
```

**Auto-creation during ingest.** When `ingest_raw.py` runs with `ingest.auto_create_projects: true` and encounters a `registry.project_name` that doesn't match any existing project (§2a.3), `create_project` is invoked programmatically. The ingest config's optional `auto_create_project:` block (see [10_TOOLS §2.1.4](10_TOOLS.md)) supplies the new project's `owner`, `description`, and `notes` — values may be literal text or interpolate `discovered.<field>` parsed from the source data. First-write-wins: the block is read only on initial creation; subsequent ingests naming the same project reuse it and ignore the block.

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
| PROJ-05 | **Project naming convention** — group consensus needed. Experiments ≠ projects. Candidates: funded names, animal-project IDs, explicit internal names. Provisional patterns (`AE-biomaGUNE-NNNN`, `${researcher}-${experiment}`) are stopgaps. See §9 for the warning callout (naming *mechanics* are settled in §2a; only the convention is open). | Project-lead users + PI | ⚠️ Pilot blocker once cell-mode work scales beyond the test batch |
