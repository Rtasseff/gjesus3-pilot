# 01 — System Overview

**Parent:** [Documentation Index](00_INDEX.md)  
**Status:** ✅ Current  
**Last Updated:** 2026-02-02

---

## Purpose

This document describes the purpose, scope, and constraints of the MFB gjesus3 research data management system.

---

## 1. Background

### 1.1 The Problem

The MFB group has historically accumulated hundreds of GB of microscopy and biomedical imaging data across external drives and individual researcher folders. This data suffers from:

- Inconsistent naming and organization
- No reliable group-level provenance tracking
- Difficulty tracing published figures back to source data
- Risk of data loss from scattered, unmanaged storage

### 1.2 The Trigger

A new whole-slide imaging instrument (Zeiss Axiocam 7) will substantially increase data volume, making the need for organized storage urgent. The PI (Jesús Ruiz-Cabello) does not want to wait for uncertain institutional platform timelines.

### 1.3 The Opportunity

The group has access to a dedicated 100 TB NAS (gjesus3) that can serve as a structured archival repository, independent of but compatible with future platform-level solutions.

---

## 2. System Purpose

> **✅ DECIDED:** gjesus3 is an **archival storage system** for original imaging data, not a primary working drive.

### 2.1 What the System Does

1. **Preserves raw acquisitions** in an organized, immutable structure organized by data ecosystem and date
2. **Archives publication data packages** with complete provenance documentation
3. **Enables traceability** from published outputs back to source data
4. **Maintains registries** documenting what data exists and where it came from

### 2.2 What the System Does Not Do

| Not This | Because |
|----------|---------|
| Primary working drive for active analysis | Access limited to specific hardwired on-site machines (excludes most laptops); RAID 5 write performance not optimized for heavy I/O |
| General file share | Requires enforced conventions; not open for unstructured dumping |
| Backup/disaster recovery | RAID 5 protects single-drive failure only; no offsite backup configured |
| Platform raw data store | Platform-originated raw data (e.g., PET listmode) maintained by platforms; we store derived/reconstructed files |

---

## 3. Scope Boundaries

### 3.1 In Scope

| Category | Details |
|----------|---------|
| **Microscopes** (direct raw) | Zeiss Axiocam 7 (WSI), Zeiss Axio Observer (Cell Observer), Zeiss LSM 900 (confocal) — instrument output (.czi) deposited directly |
| **Platform imaging** (reconstructed) | MRI (Bruker BioSpec 11.7T and 7T), Nuclear Imaging (Molecubes PET/SPECT/CT, MILabs VECTor PET/SPECT/CT/OI) — reconstructed images (DICOM, possibly NIfTI; TBC) from platforms; platforms archive true raw data |
| **Storage areas** | Raw archive, Publication archive, Staging (temporary) |
| **Users** | MFB group members with approved access |
| **Timeline** | Indefinite long-term retention for raw and publication data |

> For detailed equipment specs, see [equipment/INDEX.md](../equipment/INDEX.md).

### 3.2 Under Evaluation

| Category | Details | Status |
|----------|---------|--------|
| Electron microscopy (SEM/TEM) | Need to confirm use case fit for nanomaterial characterization | ❓ Awaiting input |
| Project workspaces | Uncertain value given access constraints | ❓ May defer |

### 3.3 Out of Scope

| Category | Reason |
|----------|--------|
| Non-imaging data | Current focus; may expand in future |
| Platform-maintained raw data | Separate responsibility; we take derived exports |
| Active analysis workflows | Access constraints make this impractical |

---

## 4. Constraints

### 4.1 Infrastructure Constraints

| Constraint | Impact | Mitigation |
|------------|--------|------------|
| **RAID 5 only** | Single-drive failure protection; no protection against multi-drive failure, ransomware, accidental deletion | Checksums for corruption detection; consider offsite backup for critical data |
| **No confirmed snapshots** | Cannot easily recover from accidental changes | Enforce read-only on raw after deposit; minimize write access |
| **Access restrictions** | Only specific hardwired on-site machines can connect (includes instruments and some researcher workstations, but excludes laptops); inconvenient but not unusable | Position as archival, not working storage; batch deposits from accessible machines |
| **2.5 GbE networking** | Adequate for archival; not optimized for real-time analysis | Acceptable for intended use case |

> **⚠️ GAP:** Need IT consultation to confirm snapshot capabilities and discuss backup options.

### 4.2 Organizational Constraints

| Constraint | Impact | Mitigation |
|------------|--------|------------|
| **Researcher engagement** | Limited response to metadata input requests | Simplify requirements; focus on must-haves |
| **Technical comfort** | Variable command-line skills | Provide scripts/tools; minimize manual steps |
| **Time availability** | Researchers focused on research, not data management | Make compliance as low-friction as possible |

### 4.3 External Dependencies

| Dependency | Status | Risk |
|------------|--------|------|
| Platform-level solutions | Timeline uncertain | Design for compatibility; don't depend on it |
| OMERO deployment | Not yet available | Ensure metadata/structure can migrate |
| IT support | Limited scope (NAS setup only) | Self-sufficient within group |

---

## 5. Design Principles

These principles guide decisions throughout the specification:

### 5.1 Raw Data is Sacred

Original acquisition files are **never modified, renamed, or moved** after registration. Any processing produces new files; originals remain untouched.

### 5.2 Traceability is Non-Negotiable

Every derived output used in publications **must be traceable** back to its raw source(s). This is achieved through provenance logging, not folder structure alone.

### 5.3 Archival First, Convenience Second

The system prioritizes long-term preservation and discoverability over ease of daily use. This is intentional given the infrastructure constraints.

### 5.4 Minimum Viable Compliance

Requirements are set at the minimum level needed for traceability and organization. Additional metadata and documentation are encouraged but not mandated beyond essentials.

### 5.5 Automation Where Possible

Manual data entry is error-prone and resisted by users. Scripts should handle as much as possible: renaming, organizing, checksum generation, registry updates.

### 5.6 Platform Compatibility

Decisions should not preclude future integration with institutional platforms or OMERO. Use established standards (REMBI, OME) where practical.

---

## 6. Success Criteria

The pilot is successful if:

1. **All new acquisitions** from covered modalities are deposited and registered within defined timelines
2. **Publication archives** can demonstrate complete provenance for all included outputs
3. **Any published figure** can be traced to its source raw data within 15 minutes
4. **Researchers comply** without significant resistance or workarounds
5. **The system survives** handoff to new group members

---

## 7. Stakeholders

| Role | Person | Responsibility |
|------|--------|----------------|
| **Sponsor/Owner** | Jesús Ruiz-Cabello (PI) | Sets expectations; authorizes access |
| **Data Management Lead** | Ryan Tasseff (Data Office) | Defines rules; implements system; supports users |
| **Initial Users** | MFB group members (see full list in [11_OPERATIONS](11_OPERATIONS.md)) | Follow conventions; provide feedback |
| **Platform Stakeholder** | Irantzu Llarena (Platform Manager) | Coordinates on WSI equipment; monitors for alignment |
| **IT** | Institute IT | NAS configuration; network access |

---

## 8. Related Documents

- [02_INFRASTRUCTURE](02_INFRASTRUCTURE.md) — Hardware details, risk assessment
- [03_RAW_STORAGE](03_RAW_STORAGE.md) — Raw data area specification
- [04_PUBLICATIONS](04_PUBLICATIONS.md) — Publication archive specification
- [06_REGISTRIES](06_REGISTRIES.md) — Registry schemas
- [09_MODALITIES](09_MODALITIES.md) — Supported data types

---

## Open Questions

None at this level — scope decisions have been made. See individual module documents for specific gaps.
