# 13 — The Role of gjesus3 (vs. Platform Archives)

**Parent:** [Documentation Index](00_INDEX.md)
**Status:** 🔶 Draft (reframe captured 2026-05-20; §5.6/§5.7 added 2026-05-26 after round-8 NI redo)
**Last Updated:** 2026-05-26

---

## Purpose

This doc captures **what gjesus3 is and is not**, in relation to the existing platform-managed archives at CIC biomaGUNE. It was written after a system-level reframe that emerged while planning the internal MRI ingest (round 6) and resolves a tension between the original "archival first" framing and the desire to make gjesus3 actively useful to researchers.

The reframe affects design choices everywhere — see the **Implications for design** section at the end.

---

## 1. The two-tier model

The MFB group's imaging data sits in **two distinct storage tiers**, each with a different purpose, a different owner, and a different design optimisation. They are complementary, not redundant.

### Tier 1 — Platform archives (the deep freeze)

**Owned by:** The instrument platforms (MRI, Nuclear Imaging, optical microscopy - moving in this direction).

**What they store:** Raw original acquisition data, mostly as the instrument wrote it, often zipped and orginized into larger annual archives. After ~5 years a study typically moves to external hard-drive cold storage.

**How researchers access it:** Awkwardly. FTP-only in the MRI case; through the platform manager only for the older external drives. No registry. Minimal standards on metadata/file-naming. No project, no publication structure. No optimized search.

**What it's good for:** Long-term preservation of original raw data. If you know exactly what study you need and someone is willing to fish for it, the platform can produce the bytes.

**What it's bad for:** Active project work. Cross-cohort search. Reuse. Anything time-sensitive. Anyone who isn't the person who originally produced the data.

This tier exists, it works (clear limitations but reliably), and **gjesus3 does not aim to replace it**.

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

### 4.1 Very-near-future: image servers (sharpened 2026-06-11, S4)

The image-server step is no longer just an aspiration — it is the **lead, imminent** next destination, split by data type:

- **Microscopy → OMERO** (OME ecosystem; vendor image files like `.czi`).
- **DICOM (preclinical MRI + Nuclear Imaging) → XNAT** (Subject → Session → Scan).

Both ingest metadata as a **flat key-value import**. gjesus3 already keeps what makes that frictionless: a clean flat registry and captured DICOM UIDs. One wrinkle the platforms share — they expect flat key-value metadata, whereas the gjesus3 sidecar is **nested** JSON; a lighter **metadata-only index** (e.g. SQLite/Datasette over the registries + sidecars) is being weighed as an intermediate that is both the searchable face on the NAS *now* and a better fit for the nested sidecar (backlog: `tasks/BACKLOG.md` → "Metadata vocabularies & search"). XNAT/OMERO stay the lead destinations regardless.

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

### 5.6 What we keep, by acquisition class

**gjesus3 is NOT the long-term archive of original instrument bytes — the platforms are.** The original group ambition was to make gjesus3 both the long-term archive AND the active project workspace; this was abandoned (NAS too slow for many concurrent users, no remote access, no need to duplicate platform archives). What remains is the **research-facing surface**: the small set of files that researchers actually open during analysis, sharing, and publishing.

Per-platform reliability of the upstream archive (drives how much we lean on it as a fallback):

| Platform | Long-term raw archive | Confidence level | Implication for gjesus3 |
|---|---|---|---|
| **Nuclear Imaging** (Molecubes / MILabs) | Original `.tgz` archives kept indefinitely on `\\cicmgsp02\gnuclear2$`, never altered after acquisition | **High** — trusted to be byte-perfect originals | We can be aggressive about dropping raw event data; the 1% case routes back to the platform easily |
| **MRI** (Bruker ParaVision) | Originals retained by the platform but not byte-locked; alterations possible in principle | **Medium** — generally reliable, no formal guarantee | Lean on the platform for forensic recovery, but with eyes open |
| **Optical microscopy** (Zeiss .czi) | Operator-managed on instrument-local PCs / group drives; no platform-level guarantee | **Low** — the platform doesn't centrally archive | The `.czi` we ingest IS effectively the long-term copy. We can't drop fidelity. |

**What we keep on gjesus3, by acquisition class:**

| Class | What lives at `/raw/<ACQ-ID>/` | What stays only on the platform |
|---|---|---|
| **Biomedical imaging (NI, MRI — "DICOM ecosystem")** | The reconstructed DICOM files (the analysis-ready images) + a curated `metadata.json` sidecar pulling key acquisition / reconstruction / instrument-side subject context from aux files; plus (DRAFT 2026-05-29) a top-level `subject:` block carrying the ARRIVE-required preclinical fields (species / strain / sex / DOB→age — auto-filled from the animal-facility DB, see [08_METADATA §4.4](08_METADATA.md)), a top-level `condition:` block carrying the disease/control state (`is_control` highly-recommended tri-state boolean + `disease_model` / `disease_state` — see [08_METADATA §4.5](08_METADATA.md)), and an `anatomy:` block (`is_whole_body` + UBERON `region` — §4.6). All three are **non-blocking** ([08_METADATA §4.7](08_METADATA.md)): recommended, WARN-if-missing, never refuse the ingest. | Raw detector data (event lists, k-space, sinograms, attenuation maps, calibration logs). Useless to 99% of analysis; voluminous; the platform owns this. |
| **Optical microscopy (.czi)** | The `.czi` container as-deposited (one acquisition = one file natively) + `metadata.json` sidecar; for animal-derived samples (the typical case), the same `subject:` + `condition:` blocks as above. | (nothing — gjesus3 IS the primary copy for microscopy) |

For biomedical, the **DICOM + sidecar pair gives a researcher ~99% of their value** (open in 3D Slicer / PMOD / ITK-SNAP / pydicom; metadata browsable without opening a viewer). The remaining 1% (raw event detection, hyper-detailed instrument logs) routes back through the platform — slower, messier, with some loss of control, but the platform is the right owner.

**Subject + condition metadata as reliability axes (independent of platform archive trust):** the per-platform archive reliability above describes the *upstream* fallback. Separately, an acquisition's *captured-on-gjesus3* value depends heavily on whether its `subject:` AND `condition:` blocks are populated.

- ARRIVE-grade `subject:` (species/strain/sex/age) turns a `.dcm` blob from "some MRI of some mouse" into "the cardiac scan of female C57BL/6J P12W animal MFB-2025-0420-m17" — searchable, reusable, publishable.
- The `condition:` block adds the experimental dimension: `is_control` (boolean) + `disease_model` + `disease_state` turn the same acquisition into "the cardiac scan of a wild-type baseline control" vs. "the cardiac scan of MI day-7 post-surgery case" — the *what was being studied* axis that makes cross-cohort and case-vs-control queries trivial. Without it, "give me all healthy controls" requires manually reading every study notebook.

Until the animal-facility-DB integration lands for `subject:` (`tasks/tasks.md §3.2`) AND the Phase 3 sidecar-writer + bulk-enrichment tools fill `condition.is_control` / `anatomy.is_whole_body` (non-blocking — recommended, not enforced; see [08_METADATA §4.7](08_METADATA.md)), these are the most consequential metadata gaps on gjesus3 for preclinical work.

**Implications for ingest design:**
- Folder-as-primary acquisitions for biomedical imaging use **selective inclusion** — explicit allowlists of what to copy, not "copy everything." Cf. internal NI `copy_ni_acquisition` and internal MRI `copy_mri_paravision` (v2 slim-folder; the v1 `copy_paravision_exam` was retired 2026-05-27).
- Curated metadata extraction (parsing instrument-specific aux files: ParaVision JCAMP-DX, Molecubes `protocol.txt` + XMLs, DICOM headers) goes into the sidecar's `<ecosystem>:` block at the level of richness a researcher would actually browse.
- We do not hoard the raw bytes "just in case" — when the platform archive is trustworthy, the cost of preserving its contents twice is real (storage, NAS-write time, scanability) and the benefit is essentially zero.

The XNAT-future framing (§4) directly captures this principle: XNAT works with DICOM + metadata, not raw detector outputs; OMERO works with vendor image files, not raw camera streams. gjesus3 is shaped the same way today, knowing one of those systems may absorb it eventually.

### 5.7 Acquisition file-shape paradigms (biomedical vs. optical)

The instruments in scope fall into two structurally distinct paradigms — visible in dir structure, filename discipline, and where metadata lives. The pilot's per-ecosystem layout choices follow from this distinction.

| Paradigm | Optical microscopy (Zeiss `.czi`) | Biomedical imaging (DICOM family — MRI, NI) |
|---|---|---|
| **Directory structure** | Loose; sometimes meaningful (researcher/cell-line/experiment), sometimes not; varies per operator | Well-defined, instrument-imposed: study / exam / reconstruction / frame / iteration |
| **Filename discipline** | Use-case-specific or operator-arbitrary (`Z-stack_LP_IONP-doxo_20x_6h_2.czi`) — the `.czi` is the deliverable, the name is a label | Instrument-imposed (`20251029100311_PET_OSEM_0.dcm`, ParaVision `2dseq` per pdata index) — the filename carries machine-issued identifiers |
| **Where metadata lives** | **Inside the single `.czi` container** — every image, channel, timepoint, mosaic tile, Z-slice, thumbnail, plus the full instrument-state XML, in one file | **Across many small files** — one DICOM per image (a 1990s standard choice, not a conceptual mismatch), aux files at each level (`acqp` / `method` / `visu_pars` for MRI; `protocol.txt` / `acqparams.xml` for NI) |
| **One acquisition =** | One `.czi` file | A folder bundle (many `.dcm` + small aux files) |
| **gjesus3 primary entity shape** | `primary_kind: file` — `<ACQ-ID>.czi` | `primary_kind: folder` — selective inclusion of DICOMs + curated aux metadata |
| **Sidecar shape** | One `microscopy:` block (the `.czi` metadata is already concentrated in one place) | Per-bucket structured block (`mri:` subject/acquisition/geometry/reconstruction; `ni:` study/subject/acquisition/reconstruction) that aggregates across the source aux files |

**Why this matters for ingest:**
- Microscopy ingest is trivially clean: one file in, one file out. The complexity is in the metadata extraction (XML parsing inside the `.czi`).
- Biomedical ingest needs selective folder copy + multi-source metadata aggregation. The `mri:` and `ni:` sidecar blocks effectively re-concentrate metadata that the instrument scattered.

This is also the reason internal MRI and NI on gjesus3 use folder-as-primary (no zip): the per-frame-DICOM packaging is a legacy 1990s format choice (one image per file), not a fundamental limit. A modern Enhanced MR / Multi-Frame DICOM could collapse that back to one file (tracked as future work in `tasks/tasks.md §3.1`). Until then, the folder bundle IS the unit and the sidecar carries the aggregated metadata.

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
