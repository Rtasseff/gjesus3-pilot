# 01 — System Overview

**Parent:** [Documentation Index](00_INDEX.md)
**Status:** ✅ Current
**Last Updated:** 2026-06-26

---

## Purpose

This document describes the purpose, scope, and constraints of the MFB gjesus3 research data management system.

---

> ## ✅ Status: TRUE PRODUCTION
>
> **gjesus3 is live and holding real, retained research data.** The system has been in **true production since the 2026-06-10 restart**. As of 2026-06-26 it holds **~13,555 registered acquisitions** across microscopy, MRI, and nuclear imaging, organised into **~50 projects** and covering **~715 subjects** (see [06_REGISTRIES](06_REGISTRIES.md)).
>
> **The pilot phase is complete and historical.** During the pilot, each instrument iterated *test → purge → accept*, and after the team exhibition the whole quasi-production dataset was **purged on 2026-06-10** and the container restarted as true production. **That purge has already happened. There is no future exhibition, purge, or restart pending.** All data deposited now is real and kept for the long term — treat the registry and `/raw/` with production care. ("Done" in this system means "done in true production.")
>
> For where the project stands today, see [tasks/STATUS.md](../tasks/STATUS.md).

---

## 1. Background

### 1.1 The Problem

The MFB group has historically accumulated hundreds of GB of microscopy and biomedical imaging data across external drives and individual researcher folders. This data suffers from:

- Inconsistent naming and organization
- No reliable group-level provenance tracking
- Difficulty tracing published figures back to source data
- Risk of data loss from scattered, unmanaged storage

### 1.2 The Trigger

A new whole-slide imaging instrument (Zeiss Axio Scan 7) substantially increased data volume, making the need for organized storage urgent. The PI (Jesús Ruiz-Cabello) did not want to wait for uncertain institutional platform timelines. (The AxioScan is now one of the highest-volume contributors in production.)

### 1.3 The Opportunity

The group has access to a dedicated NAS (gjesus3 — QNAP TS-864eU, 6 × 20 TB in RAID 5, ~63 TB user-available after snapshot reservation) that can serve as a structured archival repository, independent of but compatible with future platform-level solutions.

---

## 2. System Purpose

> **✅ DECIDED (reframed 2026-05-20):** gjesus3 is the **research-facing working layer** for MFB imaging data in the 5-year active window — organised, searchable, directly viewable. It is **not** the deep-time archive of every raw byte; the instrument platforms already serve that role. See [13_GJESUS3_ROLE](13_GJESUS3_ROLE.md) for the full two-tier framing and the design implications.

### 2.1 What the System Does

1. **Registers raw acquisitions** from approved modalities in a structured registry (`registry_raw.csv`) with rich JSON metadata sidecars (REMBI-aligned where practical)
2. **Provides project workspaces** with shortcuts back to raw + space for project-level derivatives (e.g. NIfTI generated from MR raw, splits, segmentations) and project-level metadata that supplements the raw sidecar
3. **Archives publication-ready data packages** with complete provenance documentation
4. **Enables traceability** from published outputs back to raw source data
5. **Operates in two-tier complement** with the instrument platforms' own raw archives — gjesus3 optimises for active use; the platforms handle deep-time preservation

### 2.2 What the System Does Not Do

| Not This | Because |
|----------|---------|
| Deep-time archive of every raw byte | Platforms (MRI, Nuclear Imaging, microscopy facilities) already maintain their own raw archives — awkward to access but reliable as a last resort. gjesus3's "raw" is research-facing: organised, registered, sometimes lightly normalised (per-ecosystem format choices in [03_RAW_STORAGE](03_RAW_STORAGE.md)). The 1% case needing forensic access to original bytes falls back to the platform. |
| Primary working drive for heavy active analysis | Access limited to specific hardwired on-site machines (excludes most laptops); RAID 5 write performance not optimised for high-volume I/O. Researchers analyse on their workstations and check derivatives back into `/projects/`. |
| General file share | Structured storage with enforced conventions; not open for unstructured dumping. |
| Backup/disaster recovery | RAID 5 protects single-drive failure only; no offsite backup currently configured. |
| Platform raw acquisition store | Platform-originated raw artifacts (PET listmode, ParaVision `2dseq` originals not chosen for ingest, k-space) stay with the platforms; gjesus3 ingests the research-facing slice. |

---

## 3. Scope Boundaries

### 3.1 In Scope

| Category | Details |
|----------|---------|
| **Microscopes** (direct raw) | Zeiss Axio Scan 7 (WSI, code ZWSI), Zeiss Axio Observer (Cell Observer, CELL), Zeiss LSM 900 (confocal, LSM9) — instrument output (.czi) deposited directly |
| **Platform imaging** (reconstructed) | MRI (Bruker ParaVision — BioSpec 11.7T and 7T, code MRI), Nuclear Imaging (Molecubes PET/SPECT/CT, MILabs VECTor PET/SPECT/CT/OI — codes PET, SPECT, CT) — reconstructed images (DICOM) from platforms; platforms archive true raw data |
| **Storage areas** | Raw archive, Publication archive, Project workspaces, Staging (temporary) |
| **Users** | MFB group members with approved access |
| **Timeline** | Indefinite long-term retention for raw and publication data (in true production since 2026-06-10 — data is real and kept) |

> For detailed equipment specs, see [equipment/INDEX.md](../equipment/INDEX.md).

### 3.2 Under Evaluation

| Category | Details | Status |
|----------|---------|--------|
| Electron microscopy (SEM/TEM) | Need to confirm use case fit for nanomaterial characterization | ❓ Awaiting input |

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
| **Daily snapshots active, no offsite backup** | Snapshots help with accidental changes; still no protection against site disaster or multi-drive failure | Enforce read-only on raw after deposit; define retention policy; consider offsite backup for critical data |
| **Access restrictions** | Only specific hardwired on-site machines can connect (includes instruments and some researcher workstations, but excludes laptops); inconvenient but not unusable | Position as archival, not working storage; batch deposits from accessible machines |
| **2.5 GbE networking** | Adequate for archival; not optimized for real-time analysis | Acceptable for intended use case |

> **⚠️ GAP:** Daily snapshots are confirmed active (✅ DECIDED). Retention policy and offsite backup strategy are still TBD — see [02_INFRASTRUCTURE](02_INFRASTRUCTURE.md).

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

### 5.3 Two-tier Complement, Not Replacement

gjesus3 is the research-facing working layer; the instrument platforms own the deep-time raw archive. These are complementary tiers, not competitors — gjesus3 does not aim to byte-perfect-preserve every artifact, and the platforms do not aim to be searchable or research-facing. Design choices on gjesus3 (per-ecosystem format normalisation, opinionated `reconstructions:` selection, project-scoped derivatives) are licensed by the fact that the platform tier exists. See [13_GJESUS3_ROLE](13_GJESUS3_ROLE.md).

### 5.3a Research-Facing First in the 5-Year Window

Most of a project's reuse / extension / publication-traceability value lives in roughly its first 5 years on gjesus3. Designs optimise that window: organised, viewable without unzipping, searchable by metadata, fast to find. Beyond ~5 years, value tapers — projects close, derivatives can be cleaned up, the registry retains the row. The platform's deep-freeze remains the ultimate fallback for the rare older-than-5-year case.

### 5.3b Derivatives Belong in Projects

Research-facing derivatives (NIfTI generated from MR raw, splits, segmentations, project-level metadata) live in `/projects/<proj>/`, not in `/raw/`. They're regenerable from raw, kept while the project is active, and removed at project close-out. This applies the metadata-location-split decision (2026-05-12, see [08_METADATA §1](08_METADATA.md)) to image derivatives too.

### 5.4 Minimum Viable Compliance

Requirements are set at the minimum level needed for traceability and organization. Additional metadata and documentation are encouraged but not mandated beyond essentials.

### 5.5 Automation Where Possible

Manual data entry is error-prone and resisted by users. Scripts should handle as much as possible: renaming, organizing, checksum generation, registry updates.

### 5.6 Platform Compatibility

Decisions should not preclude future integration with institutional platforms or OMERO. Use established standards (REMBI, OME) where practical.

---

## 6. Success Criteria

These were the original design-intent criteria. With the system now in true production, this section records both the **intent** and the **status as of 2026-06-26**.

| # | Design-intent criterion | Status |
|---|-------------------------|--------|
| 1 | **All new acquisitions** from covered modalities are deposited and registered within defined timelines | ✅ **Achieved** — all six in-scope instruments (AxioScan 7, Cell Observer, LSM 900, Bruker ParaVision MRI, Molecubes/MILabs PET·SPECT·CT) are operational; **~13,555 acquisitions** registered in `registry_raw.csv`, each with a JSON metadata sidecar. |
| 2 | **Publication archives** can demonstrate complete provenance for all included outputs | 🕗 **Deferred** — the provenance + project-link machinery is live (hard links, registry, enrichment writer); the `publications/` area itself is intentionally empty/planned until the first package is assembled (see [04_PUBLICATIONS](04_PUBLICATIONS.md)). |
| 3 | **Any published figure** can be traced to its source raw data within 15 minutes | ✅ **Achieved** — the [registries/index.html Finder](../tools/FINDER.md) (live since 2026-06-23; a global index plus a per-project `index.html`, auto-refreshed after every successful ingest) makes any acquisition searchable in seconds, and project folders hold hard links straight back to `/raw/`. |
| 4 | **Researchers comply** without significant resistance or workarounds | ✅ **Largely achieved** — a single frozen Windows operator GUI, `gjesus3_ingest.exe` (microscopy + MRI pages), was deployed to the NAS on 2026-06-24, reducing deposit to a few clicks; the non-blocking enrichment model means missing metadata never blocks an ingest. |
| 5 | **The system survives** handoff to new group members | 🔶 **In progress** — the public documentation refactor (3-role gateway, [RESEARCHER_GUIDE.md](../RESEARCHER_GUIDE.md), [START_HERE.md](../START_HERE.md) for operators, [GLOSSARY.md](../GLOSSARY.md)) is the handoff vehicle; survivability is proven only once the next owner runs it. |

Beyond the original list, true production has also delivered **cross-modality projects** — single project workspaces holding hard-linked raw from microscopy, MRI, and nuclear imaging side by side — which was the core promise of the research-facing working layer (see [13_GJESUS3_ROLE](13_GJESUS3_ROLE.md)).

> Current operational state lives in [tasks/STATUS.md](../tasks/STATUS.md); later refinements in [tasks/BACKLOG.md](../tasks/BACKLOG.md).

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
- [05_PROJECTS](05_PROJECTS.md) — Project workspace specification
- [06_REGISTRIES](06_REGISTRIES.md) — Registry schemas
- [09_MODALITIES](09_MODALITIES.md) — Supported data types

---

## Open Questions

None at this level — scope decisions have been made and the system is in true production. See individual module documents for specific gaps, and [tasks/STATUS.md](../tasks/STATUS.md) for current operational state.
