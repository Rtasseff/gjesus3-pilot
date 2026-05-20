# 13 — The Role of gjesus3 (vs. Platform Archives)

**Parent:** [Documentation Index](00_INDEX.md)
**Status:** 🔶 Draft (reframe captured 2026-05-20)
**Last Updated:** 2026-05-20

---

## Purpose

This doc captures **what gjesus3 is and is not**, in relation to the existing platform-managed archives at CIC biomaGUNE. It was written after a system-level reframe that emerged while planning the internal MRI ingest (round 6) and resolves a tension between the original "archival first" framing and the desire to make gjesus3 actively useful to researchers.

The reframe affects design choices everywhere — see the **Implications for design** section at the end.

---

## 1. The two-tier model

The MFB group's imaging data sits in **two distinct storage tiers**, each with a different purpose, a different owner, and a different design optimisation. They are complementary, not redundant.

### Tier 1 — Platform archives (the deep freeze)

**Owned by:** The instrument platforms (MRI, Nuclear Imaging, optical microscopy facilities).

**What they store:** Raw original acquisition data, mostly as the instrument wrote it, often zipped and rolled up into larger annual archives. After ~5 years a study typically moves to external hard-drive cold storage.

**How researchers access it:** Awkwardly. FTP-only in the MRI case; through the platform manager for the older external drives. No registry. No standardised metadata. No project / publication structure. No search.

**What it's good for:** Long-term preservation. If you know exactly what study you need and you're willing to fish for it, the platform can produce the bytes.

**What it's bad for:** Active project work. Cross-cohort search. Reuse. Anything time-sensitive. Anyone who isn't the person who originally produced the data.

This tier exists, it works (poorly but reliably), and **gjesus3 does not aim to replace it**.

### Tier 2 — gjesus3 (the research-facing working layer)

**Owned by:** The MFB group, run via the Data Office.

**What it stores:** A research-facing organised view of imaging data — acquisitions registered in a structured registry, metadata in JSON sidecars, project workspaces with raw shortcuts, publication packages with provenance.

**How researchers access it:** SMB share, hardwired on-site machines. Files are directly viewable, listable, searchable. Acquisitions don't have to be unzipped to be opened.

**What it's good for:** The 5-year-and-beyond active window of a project's life. Finding data. Reusing data. Sharing data within the group. Publishing data with proper provenance. Migration to richer systems (XNAT, OMERO, a future institutional platform) when those arrive.

**What it does NOT aim to be:** A deep-time archive of every byte ever produced by the instruments. The platform handles that.

---

## 2. The 99% / 1% rule

A simple framing for what gjesus3 needs to optimise:

- **99% of researcher interactions** with imaging data are with **derived, analysis-ready formats** — NIfTI for MR, single `.czi` files for microscopy, analysis Excel sheets, segmentations. Researchers rarely look at raw instrument bytes (Bruker `2dseq`, `.fid`, raw DICOM frames, scanner aux files).
- **1% of interactions** need the original raw + original metadata for forensic / QC / reproduction purposes.

**Implication:**
- gjesus3 optimises for the 99%: organised, easy to find, easy to open, easy to share.
- For the 1%: gjesus3 *can* preserve sufficient raw artifacts (or metadata pointers) to enable a fallback — and the platform's deep-freeze is the ultimate fallback if more is needed.

This is not a license to be sloppy with raw — it just means we don't have to be a byte-perfect archive of every instrument artifact ever produced. The platform already does that job.

---

## 3. The 5-year active window

Most of the value of gjesus3 lives in roughly the **first 5 years** of a project's life — the period in which:

- The project is open (or recently closed)
- The original researcher is still actively engaged
- Reuse / extension / cross-cohort analysis is most likely
- Publications referencing the data are still emerging

After that, the value tapers. Projects close out, researchers move on, derivative work becomes its own project. gjesus3 doesn't have to actively serve the 5+-year case — the platform's archive does.

**Implications for retention:**
- Active projects stay on gjesus3 indefinitely while open
- Closed projects can be cleaned up over time when storage pressure exists (see [05_PROJECTS](05_PROJECTS.md) on project ephemerality + close-out)
- The raw `registry_raw.csv` rows stay even when project workspaces are pruned (registry is the source of truth)
- Heavily-derived data (NIfTI generated from raw, splits, segmentations stored in project workspaces) is **expected to be regenerated from raw on demand** rather than preserved indefinitely

---

## 4. The XNAT-future aspiration

The longer-term vision is that gjesus3 evolves toward (or feeds into) a richer system like **XNAT** — searchable metadata in consistent form, browser-based access, integrated viewers, project-level dashboards.

The constraints today:
- XNAT typically wants to ingest data itself, on its own terms
- Institutional XNAT availability is uncertain
- We're in pilot

The design principle this drives:
- gjesus3's organisational structure (raw registry + JSON sidecars + project workspaces) should be **migratable** to XNAT-style systems
- Use established standards (REMBI, OME, DICOM/NIfTI) where practical
- Don't lock into gjesus3-specific schemas — keep things tool-portable

Even if XNAT never arrives, the same principles make the data more usable today.

---

## 5. Implications for design

This reframe directly affects design decisions across the pilot. The most important ones:

### 5.1 Format normalisation at ingest is OK

The original framing ("Raw Data is Sacred — original acquisition files are never modified") came from an archival-first mindset. Under the reframe, **small format-normalisation steps at ingest are acceptable** when they make the data dramatically more usable to the 99%:

- Re-archiving (zip vs. folder vs. single file) per ecosystem is a design choice, not a violation
- DICOM-to-NIfTI conversion as a project-level step is a derivative, not a corruption
- Renaming files to canonical names (e.g. `<ACQ-ID>.czi`) is documented behaviour, not blasphemy

The platform archive is the byte-perfect store. gjesus3 is the research-facing layer; it can be opinionated about format.

### 5.2 Primary-file shape may vary by modality

The "one acquisition / one file / one registry line" rule survives in spirit but **the shape of "one file" can vary by ecosystem** based on what the underlying data naturally produces:

| Modality | "Primary" shape | Reasoning |
|---|---|---|
| Microscopy (`.czi`) | Single file `<ACQ-ID>.czi` | `.czi` is a modern container; one acquisition = one file natively |
| Collaborator DICOM | Single zip `<ACQ-ID>.zip` | Legacy; many `.dcm` files per session, zipped as deposited |
| Internal MRI (ParaVision) | Folder `<ACQ-ID>/` (no zip) | Many `.dcm` per acquisition (per-frame DICOM); no-zip per the research-facing reframe |

The registry's `primary_file_name` column (and an optional `primary_kind: file | folder | archive` flag) records which shape applies per acquisition. See [03_RAW_STORAGE](03_RAW_STORAGE.md) for the per-ecosystem layout details.

### 5.3 Derivatives belong in projects, not in raw

When a research-facing derivative is needed (e.g. NIfTI generated from ParaVision raw, splits from NIfTI, segmentations), the derivative lives in **`/projects/<proj>/`** — not in `/raw/`. The raw acquisition stays untouched; the derivative is generated by a project-level tool, used while the project is active, and removed when the project closes (it's regenerable from raw if needed later).

This applies the existing metadata-location-split decision (2026-05-12, see [08_METADATA §1](08_METADATA.md)) to image derivatives too: `/raw/` immutable + acquisition-scoped; `/projects/<proj>/` mutable + project-scoped + ephemeral.

### 5.4 Metadata extraction is canonical (because it's what the 99% search on)

The JSON sidecar at `/raw/<ACQ-ID>/metadata.json` is the **searchable face** of an acquisition. Investing in rich, structured metadata extraction at ingest is high-leverage — it's how a researcher (or a future XNAT) discovers data without opening files.

For raw-format-specific embedded metadata (Bruker JCAMP-DX aux files, `.czi` XML metadata, DICOM headers): extract aggressively, expose a curated `discovered.<eco>_*` subset for YAML reference + a structured `<eco>:` sidecar block for human review + a full `_raw_metadata` dump for forensic preservation. See [08_METADATA](08_METADATA.md).

### 5.5 The platform's archive is a real fallback — design for it

Because the platform deep-freeze exists, gjesus3 does not need to anxiously hoard every byte. Specifically:

- If raw-format intermediate files (e.g. ParaVision `pdata/1/`, `pdata/2/`) are typically discarded by users, we can mirror that judgement at ingest (per a config flag — see `reconstructions:` in [10_TOOLS](10_TOOLS.md))
- The platform retains the originals; the registry records what we chose to land on gjesus3
- The 1% case of "wait, we need `/1` for QC" routes back through the platform manager

This is not a license to be lossy without reason — it's permission to be opinionated when the user's actual workflow says certain artifacts are noise.

---

## 6. What this reframe does NOT change

A handful of original principles stay intact:

- **Traceability is non-negotiable.** Every publication output must trace back to its raw sources via provenance. See [07_PROVENANCE](07_PROVENANCE.md).
- **Raw is immutable.** Once an acquisition is registered in `/raw/`, the files don't change. The reframe permits *ingest-time* normalisation; post-deposit, raw is still locked down.
- **The registry is the source of truth.** `registry_raw.csv` records everything that exists on gjesus3.
- **Conventions over freelancing.** Researchers follow the structure; the structure does not bend to per-researcher preferences.
- **Platform compatibility.** Design choices should not preclude future XNAT / OMERO / REMBI integration.

The reframe is about **what gjesus3 optimises for**, not about loosening discipline.

---

## 7. Related documents

- [01_OVERVIEW](01_OVERVIEW.md) — System purpose (updated to reflect this reframe)
- [03_RAW_STORAGE](03_RAW_STORAGE.md) — Per-ecosystem layout details
- [05_PROJECTS](05_PROJECTS.md) — Project workspace structure + ephemerality
- [08_METADATA](08_METADATA.md) — Sidecar shape + metadata-location split
- [10_TOOLS](10_TOOLS.md) — Tooling that operationalises the design
