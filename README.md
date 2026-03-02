# MFB gjesus3 Research Data Management — Pilot Project

## Overview

This repository contains the design documentation and planning materials for a lab-specific research data management (RDM) system for the MFB group at CIC biomaGUNE. The system provides long-term archival storage for microscopy and biomedical imaging data on a dedicated QNAP NAS (gjesus3, ~100 TB usable, RAID 5).

**This is a design project, not a software project.** The primary deliverables are specifications, conventions, and operational procedures. Supporting scripts live in `tools/`.

## Status

**Pilot development — NAS structure deployed, ingestion tooling implemented, first data ingestion next.**

- NAS directory structure created: `staging/`, `raw/`, `registries/`, `publications/`, `curated_datasets/`
- Raw storage organized by data ecosystem: `MICROSCOPY/`, `DICOM/`, `EM/`
- Centralized `registries/` directory holds all CSV registries (raw, publications, etc.)
- `ingest_raw.py` script implemented in `tools/` (batch, single-case, dry-run modes)
- Two collaborator DICOM datasets (~53 GB) in staging, backed up, awaiting extraction and ingestion
- Specifications largely drafted; remaining gaps tracked in [00_INDEX.md](mfb-rdm-docs/00_INDEX.md)

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
├── staging/                   # Temporary deposit area (no structure imposed)
├── raw/                       # Archival raw data (immutable after deposit)
│   ├── MICROSCOPY/            # Bio-Formats / OMERO ecosystem (.czi, .ome.tif, etc.)
│   ├── DICOM/                 # DICOM ecosystem (MRI, PET, SPECT, CT)
│   └── EM/                    # Electron microscopy (if included)
├── registries/                # All CSV registries (centralized)
├── publications/              # Publication data packages with provenance
├── curated_datasets/          # Curated derived datasets — segmentation, etc. (under evaluation)
└── tmp/                       # Temporary / scratch
```

See [02_INFRASTRUCTURE.md](mfb-rdm-docs/02_INFRASTRUCTURE.md) for hardware details and [03_RAW_STORAGE.md](mfb-rdm-docs/03_RAW_STORAGE.md) for the raw area specification.

## Repository Structure

```
gjesus3-pilot/
├── README.md                  # This file
├── CLAUDE.md                  # AI assistant instructions
├── mfb-rdm-docs/              # Primary design documentation
│   ├── 00_INDEX.md            # Documentation index and quick links
│   ├── 01_OVERVIEW.md         # System scope, constraints, design rationale
│   ├── 02_INFRASTRUCTURE.md   # Hardware, access, risk assessment
│   ├── 03_RAW_STORAGE.md      # Raw data area specification
│   ├── 04_PUBLICATIONS.md     # Publication archive specification
│   ├── 05_PROJECTS.md         # Project workspace specification (under evaluation)
│   ├── 06_REGISTRIES.md       # Registry schemas and workflows
│   ├── 07_PROVENANCE.md       # Provenance logging specification
│   ├── 08_METADATA.md         # Extended metadata (REMBI-based)
│   ├── 09_MODALITIES.md       # Supported data types and instruments
│   ├── 10_TOOLS.md            # Scripts and automation (ingest_raw implemented)
│   ├── 11_OPERATIONS.md       # Workflows, permissions, onboarding
│   ├── 12_CURATED_DATASETS.md # Curated derived datasets (under evaluation)
│   └── depricated/            # Historical drafts (preserved for context, not maintained)
│       ├── projectOutline.md
│       ├── RDM-system-specs_v0.1.md
│       └── RDM-system-specs_v0.2.md
├── tools/                     # Scripts and automation
│   ├── ingest_raw.py          # CLI for ingesting raw data from staging
│   ├── ingest/                # Supporting modules
│   ├── templates/             # README templates
│   └── requirements.txt       # Python dependencies
├── equipment/                 # Reference docs for in-scope imaging equipment
│   ├── INDEX.md               # Equipment index — start here for equipment info
│   └── ...                    # Instrument specs, platform descriptions
├── shared/                    # Documents shared with stakeholders
├── tasks/                     # Task tracking
└── contacts.xlsx              # Stakeholder contact information
```

## Key Entry Points

- **Start here:** [mfb-rdm-docs/00_INDEX.md](mfb-rdm-docs/00_INDEX.md) — full index with status of each module
- **Quick background:** [mfb-rdm-docs/01_OVERVIEW.md](mfb-rdm-docs/01_OVERVIEW.md) — why this system exists and what it does
- **Equipment:** [equipment/INDEX.md](equipment/INDEX.md) — all in-scope instruments and what "raw" means for each
- **Historical context:** [mfb-rdm-docs/depricated/](mfb-rdm-docs/depricated/) — earlier monolithic drafts showing design evolution

## People

| Role | Person |
|------|--------|
| System Owner / PI | Jesus Ruiz-Cabello (MFB) |
| Data Management Lead | Ryan Tasseff (Data Office, CIC biomaGUNE) |
| Platform Stakeholder | Irantzu Llarena (Platform Manager) |
