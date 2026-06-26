# MFB gjesus3 Research Data Management System

## Overview

This repository holds the design specifications, conventions, schemas, operating procedures, and supporting tooling for a lab-specific research data management (RDM) system for the MFB group at CIC biomaGUNE. The system runs on a dedicated QNAP NAS (gjesus3 — TS-864eU, 6 × 20 TB in RAID 5, ~63 TB user-available after snapshot reservation) and serves the group's microscopy and biomedical imaging data. It is **as much a documentation / standards / conventions project as it is a tooling project**: the primary deliverables are the specs in [`mfb-rdm-docs/`](mfb-rdm-docs/) and the procedures and tools that put them into practice.

### What gjesus3 is — the reframe

gjesus3 is the **research-facing working layer** for MFB imaging data in the 5-year active window: organised, searchable, directly viewable. It is **not** the deep-time archive of every raw byte — the instrument platforms (MRI, Nuclear Imaging, microscopy facilities) maintain their own raw archives, and gjesus3 complements rather than replaces them. See [`13_GJESUS3_ROLE`](mfb-rdm-docs/13_GJESUS3_ROLE.md) for the full two-tier framing and the design implications it drives.

## Status

> **✅ TRUE PRODUCTION since 2026-06-10.** All data is real and retained long-term.
>
> **~13,555 acquisitions** in `/raw/` · **~50 projects** (each hard-linked to its raw data) · **~715 subjects** in the subject registry · **all instruments live** (microscopy, MRI, Nuclear Imaging) · **operator GUI** (`gjesus3_ingest.exe`) and the **Finder** (`registries/index.html`) deployed.

The dated history of how the system got here — the earlier pilot, the per-instrument test rounds, and the 2026-06-10 production restart — lives in [`CHANGELOG.md`](CHANGELOG.md).

---

## Where to go — by role

### For Researchers

You have data on gjesus3 and want to find it, view it, or understand a project.

| Go to | Why |
|---|---|
| [`RESEARCHER_GUIDE.md`](RESEARCHER_GUIDE.md) | Your entry point — what gjesus3 holds, how to find your data, how projects work. |
| [The Finder](tools/FINDER.md) (`registries/index.html`) | Open the share, double-click the index, search by mouse/date/instrument/region/project, one-click **Copy path** to your data. |
| [`tools/FAQ.md`](tools/FAQ.md) | Plain-language answers to common researcher questions. |

### For Operators / Techs

You run an instrument and need to get its data onto the NAS.

| Go to | Why |
|---|---|
| [`START_HERE.md`](START_HERE.md) | One page — pick your front-end, set `GJESUS3_ROOT`, dry-run first. |
| [`tools/OPERATOR_FAQ.md`](tools/OPERATOR_FAQ.md) | Quick answers for the ingest front-ends (GUI + Linux scripts). |
| [`tools/INGEST_CLI.md`](tools/INGEST_CLI.md) | Full CLI reference + YAML ingest-config cheat-sheet (data-office path). |

### For Developers / Coding Agents

You are extending the specs, the tooling, or the conventions.

| Go to | Why |
|---|---|
| [`mfb-rdm-docs/00_INDEX.md`](mfb-rdm-docs/00_INDEX.md) | Master map of the authoritative specs (modules 00–13) + key-decisions table. |
| [`CLAUDE.md`](CLAUDE.md) | Agent operating rules: where to start, what to never edit, must-obey conventions. |
| [`CONTRIBUTING-docs.md`](CONTRIBUTING-docs.md) | Documentation architecture, status markers, cross-reference mirror rules, and style. |

---

## NAS Access

| Attribute | Value |
|-----------|-------|
| **Share** | `\\GJESUS3\gjesus3` |
| **Container** | `J:\gjesus3-data` (drive map) · `\\GJESUS3\gjesus3\gjesus3-data` (UNC) |
| **Protocol** | SMB (Windows file sharing) |
| **Access** | Hardwired on-site machines only (instruments + some workstations; laptops excluded) |
| **Drive mapping** | Map to a drive letter, e.g. `net use J: \\GJESUS3\gjesus3` |

### Current NAS directory layout

```
J:\gjesus3-data\
├── raw\                        # Archival raw data (immutable after deposit), by ecosystem:
│   ├── MICROSCOPY\             #   Bio-Formats ecosystem (.czi, .ome.tif, …) — single-file primary
│   └── DICOM\                  #   DICOM ecosystem — zipped archive (legacy collaborator) OR
│                               #   folder-as-primary (internal MRI / NI). See 03_RAW_STORAGE §4.
│                               #   (EM\ is reserved but not deployed.¹)
├── projects\                   # Project workspaces (each hard-links back to its raw data)
├── registries\                 # All CSV registries + the generated Finder (index.html)
├── publications\               # Publication data packages (planned — empty today)
├── staging\                    # Secondary deposit area (convenience dump; primary staging is off-NAS)
├── recipes\                    # Saved ingest recipes used by the operator GUI
├── tools\                      # Deployed operator tooling (gjesus3_ingest.exe + guides)
└── tmp\                        # Scratch
```

¹ EM (electron microscopy) is a reserved ecosystem code; no EM data is on the NAS today.

See [`02_INFRASTRUCTURE.md`](mfb-rdm-docs/02_INFRASTRUCTURE.md) for hardware details and [`03_RAW_STORAGE.md`](mfb-rdm-docs/03_RAW_STORAGE.md) for the raw-area specification.

---

## Documentation Architecture — where things live

This repo deliberately separates **rules** (specs / conventions / schemas) from **state** (current work / open questions) from **instrument-specific reality** (per-platform workflows). Each location has a clear role:

| Location | Role | When to update |
|---|---|---|
| [`README.md`](README.md) (this file) | Role gateway — one-glance "what is this, where do I go." | High-level posture changes. |
| [`RESEARCHER_GUIDE.md`](RESEARCHER_GUIDE.md) | Researcher entry point — find and understand your data, in plain language. | When the researcher-facing experience changes. |
| [`START_HERE.md`](START_HERE.md) | Operator one-pager — pick a front-end, dry-run, ingest. | When the operator front-ends change. |
| [`GLOSSARY.md`](GLOSSARY.md) | Definitions — REMBI / ISA / UBERON / sidecar / `discovered.*` / ACQ-ID and other terms. | When a new term enters the docs. |
| [`CLAUDE.md`](CLAUDE.md) | Agent operating rules — where to start, what to never edit, must-obey conventions. | When agent discipline changes. |
| [`CONTRIBUTING-docs.md`](CONTRIBUTING-docs.md) | Documentation architecture, status markers, cross-reference mirror rules, style. | When the doc-discipline rules change. |
| [`mfb-rdm-docs/`](mfb-rdm-docs/) | **Authoritative design specs** — decisions, conventions, schemas, principles. Numbered 00–13; [`00_INDEX.md`](mfb-rdm-docs/00_INDEX.md) is the master map. | Whenever a design call is made or refined. |
| [`equipment/`](equipment/) | **Per-instrument workflow notes + platform descriptions** — the bridge between abstract specs and concrete instrument behaviour. [`INDEX.md`](equipment/INDEX.md) is the map. | When an instrument comes online or a workflow / naming convention changes. |
| [`tools/`](tools/) | Implementation + tool docs. [`INDEX.md`](tools/INDEX.md) is the master tool map; [`INGEST_CLI.md`](tools/INGEST_CLI.md), [`FINDER.md`](tools/FINDER.md), [`FAQ.md`](tools/FAQ.md), [`OPERATOR_FAQ.md`](tools/OPERATOR_FAQ.md). | When code, templates, or tool docs change. |
| [`tasks/STATUS.md`](tasks/STATUS.md) | Lean current-state snapshot — what's live, what's in flight, open questions. | During active work. |
| [`tasks/BACKLOG.md`](tasks/BACKLOG.md) | Later improvements — refinements not required for the current hand-off. | When a future improvement is identified or promoted. |
| [`tasks/archive/`](tasks/archive/) | Superseded handoffs + old planning notes — historical record only. | When preserving a past iteration for context. |
| [`CHANGELOG.md`](CHANGELOG.md) | The single narrative history of design + tooling decisions. | When a decision lands. |

---

## Repository Structure

```
gjesus3-pilot/
├── README.md                  # This file — role gateway
├── RESEARCHER_GUIDE.md        # Researcher entry point
├── START_HERE.md              # Operator one-pager
├── GLOSSARY.md                # Term definitions
├── CLAUDE.md                  # Agent operating rules + must-obey conventions
├── CONTRIBUTING-docs.md       # Doc architecture, status markers, cross-ref rules, style
├── CHANGELOG.md               # Single narrative history of decisions
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
│   ├── 10_TOOLS.md            # Tooling spec (YAML schema, link_filename, GUI, …)
│   ├── 11_OPERATIONS.md       # Workflows, permissions, onboarding
│   ├── 12_CURATED_DATASETS.md # Curated derived datasets (under evaluation)
│   └── 13_GJESUS3_ROLE.md     # The reframe — research-facing working layer
├── tools/                     # Scripts + automation + tool docs
│   ├── INDEX.md               # Master tool map — start here for tooling
│   ├── INGEST_CLI.md          # CLI reference + YAML schema cheat-sheet
│   ├── FINDER.md              # The searchable registry index (index.html)
│   ├── FAQ.md                 # Researcher FAQ
│   ├── OPERATOR_FAQ.md        # Operator FAQ
│   ├── ingest_raw.py          # CLI for ingesting raw data from staging
│   ├── create_project.py      # CLI for creating project workspaces
│   ├── find_acq.py            # Registry join engine + CLI (powers the Finder)
│   ├── generate_index.py      # Writes the self-contained HTML Finder
│   ├── ftp_mirror.py          # Standalone SFTP mirror utility (MRI / NI)
│   ├── ingest/                # Supporting modules (config, resolver, registry,
│   │                          #  sidecar, jcampdx, paravision_metadata, czi_metadata, …)
│   ├── operator/              # Operator front-ends (GUI + ni_ingest / mri_ingest)
│   ├── configs/               # Committed per-batch ingest configs (one per run)
│   ├── templates/
│   │   ├── ingest_template.yaml      # Universal starter
│   │   └── instruments/              # Per-instrument templates (locked-in conventions)
│   └── requirements.txt       # Python dependencies
├── equipment/                 # Per-instrument reference docs + workflow notes
│   ├── INDEX.md               # Equipment map — start here for instrument info
│   ├── axioscan7-wsi/         # AxioScan 7 vendor specs + data-handling notes
│   ├── cell-observer/         # Cell Observer vendor specs + operator workflow
│   ├── lsm900/                # LSM 900 vendor specs
│   ├── mri-platform/          # MRI Bruker BioSpec specs + access + workflow + naming convention
│   └── nuclear-imaging/       # Nuclear Imaging platform specs + naming + archive convention
├── tasks/
│   ├── STATUS.md              # Lean current-state snapshot
│   ├── BACKLOG.md             # Later improvements
│   └── archive/               # Superseded handoffs (historical)
└── contacts.xlsx              # Stakeholder contact information
```

---

## People

| Role | Person |
|------|--------|
| System Owner / PI | Jesus Ruiz-Cabello (MFB) |
| Data Management Lead | Ryan Tasseff (Data Office, CIC biomaGUNE) |
| Platform Stakeholder (Microscopy) | Irantzu Llarena (Platform Manager) |
| Operator (Cell Observer / AxioScan / LSM 900) | Ainhize Urkola Arsuaga, Marta |
| Platform Manager (Nuclear Imaging) | Unai |
</content>
</invoke>
