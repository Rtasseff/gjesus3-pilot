# MFB gjesus3 Research Data Management — Pilot Project

## Overview

This repository contains the design documentation, specifications, conventions, and supporting tooling for a lab-specific research data management (RDM) system for the MFB group at CIC biomaGUNE. The system runs on a dedicated QNAP NAS (gjesus3 — TS-864eU, 6 × 20 TB in RAID 5, ~63 TB user-available after snapshot reservation) and serves the group's microscopy and biomedical imaging data.

**This is as much a documentation / standards / conventions project as it is a tooling project.** The primary deliverables are the specs in [`mfb-rdm-docs/`](mfb-rdm-docs/), the per-instrument workflow notes in [`equipment/`](equipment/), and the operating procedures in [`tasks/tasks.md`](tasks/tasks.md). Supporting scripts live in [`tools/`](tools/).

### What gjesus3 is — the reframe (2026-05-20)

gjesus3 is the **research-facing working layer** for MFB imaging data in the 5-year active window: organised, searchable, directly viewable. It is **not** the deep-time archive of every raw byte — the instrument platforms (MRI, Nuclear Imaging, microscopy facilities) maintain their own raw archives, and gjesus3 complements rather than replaces them. See [`13_GJESUS3_ROLE`](mfb-rdm-docs/13_GJESUS3_ROLE.md) for the full two-tier framing and design implications.

## Status

**Pilot — four ingest rounds complete in quasi-production state; one operator example pending (LSM 900) and one platform-manager question pending (Nuclear Imaging) before further rounds.**

> **All current ingests are quasi-production.** Each instrument is iterated test → purge → accept-as-quasi-production. After a team exhibition, **everything will be purged** and true production restarts incorporating exhibition feedback. The "TEST" tagging in config filenames + registry notes is intentional and stays.

### Rounds completed

| Round | Instrument | Code | Outcome on NAS |
|-------|-----------|------|----------------|
| 1–2 | Collaborator DICOM | `XMRI` | 75 acqs across PROJ-0001 (LIONS, 42) + PROJ-0002 (HPIC, 33). Legacy zipped-archive shape. |
| 4 | AxioScan 7 WSI | `ZWSI` | 28 acqs across PROJ-0003/0004/0005 (`ae-biomegune-{0423,0424,0525}`). Single-file `.czi` shape. |
| 5 | Cell Observer cells-mode | `CELL` | 165 acqs across PROJ-0006/0007/0008 (`itziar-*`). Exhibits both filename- and path-focused metadata extraction on real data. |
| 6 | Internal MRI (Bruker ParaVision) | `MRI` | 97 acqs across PROJ-0003 + PROJ-0004 (cross-modality reuse with round 4). **New no-zip folder-as-primary layout**; ParaVision JCAMP-DX metadata in `metadata.json.mri`; unique human-meaningful `.lnk` names via the new `link_filename:` field. |

### Key recent decisions

- **2026-05-22 — `link_filename:` YAML field** controls the `.lnk` shortcut name per acquisition. Resolver-evaluated; per-instrument templates ship recommended defaults. Fixes the round-6 first-ingest `.lnk` collision bug. See [10_TOOLS §2.1.5](mfb-rdm-docs/10_TOOLS.md).
- **2026-05-20 — gjesus3 role reframed** as a research-facing working layer ([13_GJESUS3_ROLE](mfb-rdm-docs/13_GJESUS3_ROLE.md)). ISA terminology adopted (investigation/study/assay → project/session/acquisition). New DRAFT registry columns `session_id` + `primary_kind`. Per-ecosystem primary-entity shapes documented in [03_RAW_STORAGE §4](mfb-rdm-docs/03_RAW_STORAGE.md).
- **2026-05-20 — No-zip folder-as-primary** layout for internal MRI. New `acquisition_layout: folder` + `reconstructions:` YAML flags. ParaVision JCAMP-DX aux files (`subject`/`acqp`/`method`/`visu_pars`) are the canonical metadata source — not DICOM headers. New `tools/ingest/{jcampdx,paravision_metadata,probe_paravision}.py` modules. See [10_TOOLS §2.1.2b](mfb-rdm-docs/10_TOOLS.md).
- **2026-05-14 — Round 5 architectural prep:** `path_parse:` YAML feature + `auto_create_project:` block. Cell Observer round 5 then exercised both end-to-end (165 acqs).
- **2026-05-12 — Metadata-location split:** acquisition-level metadata in `/raw/` (immutable); study-level in `/projects/<proj>/metadata/` (mutable). Researchers contribute REMBI study + biosample context to project workspaces; close-out tool merges into `/raw/` before project deletion. See [08_METADATA §1](mfb-rdm-docs/08_METADATA.md).
- **2026-05-06 — Three-block YAML ingest schema** (`ingest:` / `auto_discover:` / `registry:`); per-column registry mapping explicit in YAML; `ingest_config` registry column.
- **2026-05-05 — Project link method:** Windows `.lnk` shell shortcuts (Windows-first, pilot-specific; see [10_TOOLS §2.1.1](mfb-rdm-docs/10_TOOLS.md)).
- **2026-03-06 — DICOM stored as compressed archives** (collaborator DICOM only — legacy shape). Internal modalities now use folder-as-primary per the 2026-05-20 reframe.

### What's next

| Pass | Section | Blocked on |
|------|---------|-----------|
| LSM 900 confocal (`LSM9`) | [§4.6.C](tasks/tasks.md) | Ainhize Urkola Arsuaga to provide a detailed example. Should reuse the Cell Observer cells-mode template + the new `link_filename:` pattern. |
| Nuclear Imaging (`PET`/`SPECT`/`CT`) | [§4.7](tasks/tasks.md) | Platform Manager **Unai** to answer one outstanding question on the naming convention. Convention + archive structure already documented in [`equipment/nuclear-imaging/internal_ni_data_handling_workflow_notes.md`](equipment/nuclear-imaging/internal_ni_data_handling_workflow_notes.md) for the future round. |
| Project-level NIfTI generator | [tasks §3.2](tasks/tasks.md) | Decision deferred; joins the existing project-level tool family (`gather_metadata`, Excel importer, close-out tool). |

See [`tasks/tasks.md`](tasks/tasks.md) for the full task list including future-work items (raw→DICOM regeneration assessment, Enhanced MR Multi-Frame DICOM evaluation, user-as-operator permissions for internal modalities, NI tgz-aware staging, MRI naming-convention stakeholder follow-up).

## NAS Access

| Attribute | Value |
|-----------|-------|
| **Share** | `\\GJESUS3\gjesus3` |
| **Protocol** | SMB (Windows file sharing) |
| **Access** | Hardwired on-site machines only (instruments + some workstations; laptops excluded) |
| **Drive mapping** | Can be mapped to a drive letter (e.g., `net use J: \\GJESUS3\gjesus3`) |

### Current NAS directory layout

```
\\GJESUS3\gjesus3\
├── staging/                   # Secondary deposit area (convenience dump; primary staging is off-NAS)
├── raw/                       # Archival raw data (immutable after deposit)
│   ├── MICROSCOPY/            # Bio-Formats ecosystem (.czi, .ome.tif, etc.) — single-file primary
│   ├── DICOM/                 # DICOM ecosystem — per-ecosystem shape: zipped archive (legacy
│   │                          # collaborator XMRI) OR folder-as-primary (internal MRI). See
│   │                          # 03_RAW_STORAGE §4.
│   └── EM/                    # Electron microscopy (if included)
├── registries/                # All CSV registries (centralized)
├── publications/              # Publication data packages with provenance
├── projects/                  # Project workspaces (ephemeral — deleted at close-out)
└── curated_datasets/          # Curated derived datasets (under evaluation)
```

See [02_INFRASTRUCTURE.md](mfb-rdm-docs/02_INFRASTRUCTURE.md) for hardware details and [03_RAW_STORAGE.md](mfb-rdm-docs/03_RAW_STORAGE.md) for the raw area specification.

## Documentation Architecture — where things live

This project is as much about documenting conventions and standards as it is about code. The repo is organised so that **each location has a clear role**:

| Location | Role | When to update |
|---|---|---|
| `README.md` (this file) | Newcomer orientation. One-glance "what is this, where do I go." | High-level posture changes (new round complete, major reframe). |
| `CLAUDE.md` | Agent-facing operating rules. Where to start, what to never edit, cross-reference consistency, doc-architecture. | When agent discipline / cross-ref rules change. |
| `mfb-rdm-docs/` | **Authoritative design specs** — decisions, conventions, schemas, principles. The "rules of the system." Numbered 00–13. `00_INDEX.md` is the master map. | Whenever a design call is made or refined. Tracked in `00_INDEX.md` version history. |
| `tasks/tasks.md` | Operational state — what's done, what's in progress, open questions, future work. Per-round detail trails. | Constantly during active work. |
| `equipment/` | **Per-instrument workflow notes + platform descriptions.** The bridge between abstract specs and concrete instrument behaviour. Each instrument has its own folder; `INDEX.md` is the map. | When a new instrument comes online or a workflow detail / naming convention changes. |
| `tools/` | Implementation. `ingest_raw.py` + `create_project.py` + `ingest/` modules + `templates/` + `configs/` + standalone utilities (`ftp_mirror.py`, `migrate_registry_columns.py`). [`tools/INGEST_CLI.md`](tools/INGEST_CLI.md) is the CLI reference. | When code or templates change. |
| `mfb-rdm-docs/depricated/` | Historical drafts preserved for context. **Never edited.** | Never. |

## Repository Structure

```
gjesus3-pilot/
├── README.md                  # This file — orientation
├── CLAUDE.md                  # AI assistant instructions + cross-ref rules
├── mfb-rdm-docs/              # Authoritative design specs (master map: 00_INDEX.md)
│   ├── 00_INDEX.md            # Quick links + key decisions + version history
│   ├── 01_OVERVIEW.md         # Scope, constraints, design principles
│   ├── 02_INFRASTRUCTURE.md   # Hardware, access, risk assessment
│   ├── 03_RAW_STORAGE.md      # Raw zone spec — per-ecosystem primary-entity shapes
│   ├── 04_PUBLICATIONS.md     # Publication archive spec
│   ├── 05_PROJECTS.md         # Project workspace spec
│   ├── 06_REGISTRIES.md       # Registry schemas + ISA terminology
│   ├── 07_PROVENANCE.md       # Provenance logging spec
│   ├── 08_METADATA.md         # Metadata location split + sidecar shapes
│   ├── 09_MODALITIES.md       # Per-modality details + discovered.<eco>_* tables
│   ├── 10_TOOLS.md            # Tooling spec (YAML schema, link_filename, etc.)
│   ├── 11_OPERATIONS.md       # Workflows, permissions, onboarding
│   ├── 12_CURATED_DATASETS.md # Curated derived datasets (under evaluation)
│   ├── 13_GJESUS3_ROLE.md     # The reframe — research-facing working layer
│   └── depricated/            # Historical drafts (preserved, never edited)
├── tools/                     # Scripts + automation
│   ├── ingest_raw.py          # CLI for ingesting raw data from staging
│   ├── create_project.py      # CLI for creating project workspaces
│   ├── ftp_mirror.py          # Standalone SFTP mirror utility (MRI / NI)
│   ├── migrate_registry_columns.py   # One-shot schema-migration tool
│   ├── ingest/                # Supporting modules (config, resolver, registry, sidecar,
│   │                          #  jcampdx, paravision_metadata, czi_metadata, ...)
│   ├── configs/               # Committed per-batch ingest configs (one per run)
│   ├── templates/
│   │   ├── ingest_template.yaml      # Universal starter
│   │   └── instruments/              # Per-instrument templates (locked-in conventions)
│   ├── INGEST_CLI.md          # CLI reference
│   └── requirements.txt       # Python dependencies
├── equipment/                 # Per-instrument reference docs + workflow notes
│   ├── INDEX.md               # Equipment map — start here for instrument info
│   ├── axioscan7-wsi/         # AxioScan 7 vendor specs + data-handling notes
│   ├── cell-observer/         # Cell Observer vendor specs + operator workflow
│   ├── lsm900/                # LSM 900 vendor specs
│   ├── mri-platform/          # MRI Bruker BioSpec specs + access strategy + workflow + systematic naming convention
│   └── nuclear-imaging/       # Nuclear Imaging platform specs + (future-round) naming + archive convention
├── shared/                    # Documents shared with stakeholders
├── tasks/
│   └── tasks.md               # Consolidated task list with per-round detail trails
└── contacts.xlsx              # Stakeholder contact information
```

## Key Entry Points

- **▶ Operators / techs start here:** [`START_HERE.md`](START_HERE.md) — one page: pick your front-end, set `GJESUS3_ROOT`, dry-run first.
- **Glossary:** [`GLOSSARY.md`](GLOSSARY.md) — REMBI / ISA / UBERON / "sidecar" / `discovered.*` / ACQ-ID and the other terms a newcomer hits undefined.
- **Changelog:** [`CHANGELOG.md`](CHANGELOG.md) — the single narrative history of design + tooling decisions.
- **Reframe (why gjesus3 looks the way it does):** [`13_GJESUS3_ROLE`](mfb-rdm-docs/13_GJESUS3_ROLE.md)
- **Design docs:** [`mfb-rdm-docs/00_INDEX.md`](mfb-rdm-docs/00_INDEX.md) — full index with status of each module
- **Background:** [`01_OVERVIEW.md`](mfb-rdm-docs/01_OVERVIEW.md) — why this system exists and what it does
- **Equipment:** [`equipment/INDEX.md`](equipment/INDEX.md) — in-scope instruments and what "raw" means for each
- **Task list:** [`tasks/tasks.md`](tasks/tasks.md) — what's done, what's next
- **Tooling:** [`tools/INGEST_CLI.md`](tools/INGEST_CLI.md) — CLI reference + YAML schema cheat-sheet
- **Historical context:** [`mfb-rdm-docs/depricated/`](mfb-rdm-docs/depricated/) — earlier monolithic drafts showing design evolution

## People

| Role | Person |
|------|--------|
| System Owner / PI | Jesus Ruiz-Cabello (MFB) |
| Data Management Lead | Ryan Tasseff (Data Office, CIC biomaGUNE) |
| Platform Stakeholder (Microscopy) | Irantzu Llarena (Platform Manager) |
| Operator (Cell Observer / AxioScan / LSM 900) | Ainhize Urkola Arsuaga, Marta |
| Platform Manager (Nuclear Imaging) | Unai |
