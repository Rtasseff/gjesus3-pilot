# MFB gjesus3 Research Data Management — Documentation Index

**System Purpose:** Long-term archival storage for MFB group microscopy and biomedical imaging data  
**Infrastructure:** QNAP TS-864eU NAS (RAID 5, ~100 TB usable)  
**Status:** Pilot development  
**Last Updated:** 2026-02-02

---

## Quick Links

| Document | Purpose | Status |
|----------|---------|--------|
| [01_OVERVIEW](01_OVERVIEW.md) | System scope, constraints, and design rationale | ✅ Current |
| [02_INFRASTRUCTURE](02_INFRASTRUCTURE.md) | Hardware, access, risk assessment | ⚠️ Gaps identified |
| [03_RAW_STORAGE](03_RAW_STORAGE.md) | Raw data area specification | 🔶 Draft |
| [04_PUBLICATIONS](04_PUBLICATIONS.md) | Publication archive specification | 🔶 Draft |
| [05_PROJECTS](05_PROJECTS.md) | Project workspace specification | ❓ Under evaluation |
| [06_REGISTRIES](06_REGISTRIES.md) | Registry schemas and workflows | 🔶 Draft |
| [07_PROVENANCE](07_PROVENANCE.md) | Provenance logging specification | 🔶 Draft |
| [08_METADATA](08_METADATA.md) | Extended metadata (REMBI-based) | 🔶 Draft |
| [09_MODALITIES](09_MODALITIES.md) | Supported data types and instruments | ⚠️ Needs input |
| [10_TOOLS](10_TOOLS.md) | Scripts and automation | 📋 Planned |
| [11_OPERATIONS](11_OPERATIONS.md) | Workflows, permissions, onboarding | 📋 Planned |

**Legend:** ✅ Current | 🔶 Draft | ⚠️ Gaps identified | ❓ Under evaluation | 📋 Planned

---

## What This System Is

An **archival storage system** for original imaging data that:

1. Preserves raw acquisitions from approved modalities in an organized, immutable structure
2. Maintains publication-ready data packages with full provenance
3. Supports traceability from published figures back to source data
4. Operates independently of (but compatible with) future platform-level solutions

## What This System Is NOT

- **Not a primary working drive** — access limited to specific hardwired on-site machines (not laptops), and RAID 5 performance is not optimized for active analysis workflows
- **Not a general file share** — structured storage with enforced conventions, not open dumping
- **Not a backup solution** — RAID protects against single-drive failure only; no offsite backup currently configured

---

## Current Scope

### Confirmed Modalities (Initial Pilot)

| Modality | Instrument/Source | Primary Format | Status |
|----------|-------------------|----------------|--------|
| Optical microscopy (histology) | Various light microscopes | .tif, .czi | ✅ Confirmed |
| Whole-slide imaging | Zeiss Axiocam 7 | .czi | ✅ Confirmed |
| Reconstructed biomedical imaging | PET, SPECT, CT, MRI (DICOM exports) | .dcm, DICOM dirs | ✅ Confirmed |

### Under Evaluation

| Modality | Instrument/Source | Notes |
|----------|-------------------|-------|
| Electron microscopy (SEM/TEM) | EM platform | Mainly nanomaterial characterization; need confirmation of use case fit |

### Deferred / Out of Scope

| Item | Reason |
|------|--------|
| Active project workspaces | Uncertain value given access constraints; may revisit |
| Platform-originated raw data | Maintained by platforms; we store reconstructed/exported files only |
| Non-imaging data | Current focus is imaging; may expand later |

---

## Key Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Storage areas | Raw + Publications (+ staging) | Projects area deferred |
| Registry location | Top-level centralized | Simpler management; single source of truth |
| Raw structure | Instrument → Year → Month → Acquisition (likely, under discussion) | Concrete for users; supports multiple modalities |
| One primary file rule | Yes (with documented exceptions) | Simplifies registry; exceptions handled case-by-case |
| Provenance location | Per-publication/project folder | Local to context; enables independent archiving |
| Extended metadata | REMBI-based subset | Community standard; pruned to essential fields |

---

## Key Gaps / Open Questions

### Infrastructure (see [02_INFRASTRUCTURE](02_INFRASTRUCTURE.md))
- [ ] Backup strategy undefined — RAID 5 only, no snapshots confirmed, no offsite
- [ ] Access limited to specific hardwired on-site machines (instruments + some workstations); laptops excluded — workable but inconvenient
- [ ] Snapshot/restore capabilities — need IT confirmation
- [ ] Filesystem type confirmation needed — affects linking method options (symlinks, hard links)

### Raw Storage (see [03_RAW_STORAGE](03_RAW_STORAGE.md))
- [ ] Organization by instrument vs. abstract modality — likely instrument-based but needs discussion

### Publications (see [04_PUBLICATIONS](04_PUBLICATIONS.md))
- [ ] Raw data linking method undecided — symlinks, hard links, or text reference list? Depends on filesystem and OS

### Modalities (see [09_MODALITIES](09_MODALITIES.md))
- [ ] SEM/TEM inclusion decision pending
- [ ] Data type sign-up sheet incomplete — need volunteer owners per type
- [ ] Embedded metadata audit incomplete — which instruments embed what?

### Metadata (see [08_METADATA](08_METADATA.md))
- [ ] REMBI field selection not finalized — user voting incomplete
- [ ] ISA-TAB-Nano applicability for nanomaterial imaging unclear

### Tools (see [10_TOOLS](10_TOOLS.md))
- [ ] Ingest script requirements defined but not implemented
- [ ] Where scripts will run (designated workstation vs. user machines) undecided
- [ ] Script versioning/distribution approach undefined

### Operations (see [11_OPERATIONS](11_OPERATIONS.md))
- [ ] Who can promote staging → raw (intake roles)
- [ ] Permissions model details
- [ ] Quick Start guide not written
- [ ] Pilot review cadence not scheduled

---

## How to Use This Documentation

**For specific topics:** Navigate directly to the relevant module document.

**For stakeholder discussions:** Share only the relevant module(s) rather than the full specification.

**For gap tracking:** Each module has its own "Open Questions" section; this index summarizes cross-cutting gaps.

**For iteration:** Update individual modules as decisions are made; update this index to reflect status changes.

---

## Document Conventions

### Status Markers

Throughout these documents:

> **✅ DECIDED:** Finalized decision — implement as specified

> **🔶 DRAFT:** Proposed approach — feedback welcome, may change

> **⚠️ GAP:** Information or decision needed — cannot proceed without resolution

> **❓ EVALUATING:** Under active consideration — may be included, deferred, or dropped

### Cross-References

Documents reference each other by filename: `(see [06_REGISTRIES](06_REGISTRIES.md))`.

### Feedback Requests

Explicit calls for input are marked:

> **📣 INPUT NEEDED:** *[specific question or request]*

---

## Version History

| Date | Author | Changes |
|------|--------|---------|
| 2026-02-02 | R. Tasseff | Restructured from monolithic spec to modular documents; refocused on archival scope |
| 2025-01-22 | R. Tasseff | v0.2 — Added discussion flags for stakeholder meeting |
| 2025-01-22 | R. Tasseff | v0.1 — Initial comprehensive draft |
