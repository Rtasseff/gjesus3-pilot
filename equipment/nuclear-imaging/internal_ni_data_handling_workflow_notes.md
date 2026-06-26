# Internal Nuclear Imaging — data-handling workflow notes

**Status:** ✅ Round-8 ingest landed on the v2.1 slim shape 2026-05-27 (DICOMs only, flat-renamed under `<ACQ-ID>.data/`; parsed aux content in sidecar; no aux files duplicated to disk; multi-frame DICOMs kept alongside per-frame as `recon<X>_frameMULTI.dcm`). Live-machine workflow still future.
**Last updated:** 2026-05-27 (v2.1: multi-frame DICOMs now included)

> This document captures the systematic naming and archive structure of the **internal Nuclear Imaging (NI) platform** at CIC biomaGUNE. Two ingest paths are documented separately below:
>
> - **Archive mode** (round 8, 2026-05-22 — IMPLEMENTED): pull pre-archived `.tgz` files from `\\cicmgsp02\gnuclear2$\<year>\<PI>\`, extract locally, and ingest as folder-as-primary acquisitions. Per-instrument template at [`tools/templates/instruments/molecubes_ni.yaml`](../../tools/templates/instruments/molecubes_ni.yaml).
> - **Live-machine mode** (future): direct ingest from the acquisition box (Molecubes / MILabs VECTor). Different source shape (a folder, not a .tgz) — will get its own per-instrument template when the workflow + access conversation with the platform manager closes.
>
> Companion docs: [`nuclear_imaging_platform_description.md`](nuclear_imaging_platform_description.md) (platform / equipment), [`equipment/mri-platform/internal_mri_data_handling_workflow_notes.md`](../mri-platform/internal_mri_data_handling_workflow_notes.md) (analogous MRI workflow).

## Round 8 — archive-mode design (2026-05-22)

The user / Data Mgmt Lead requested in round 8: ingest "everything available for Jesus's lab in the archive under `\\cicmgsp02\gnuclear2$\2025\Jesus\`" as a Phase A test against the framework — knowing the eventual live-machine workflow will look different.

**Why archive mode first:** access to the live acquisition machine is still pending (Platform Manager Unai owes us an answer on the workflow + a naming-convention question — see `tasks/tasks.md §4.7`). The archive is reachable + readable today, and exercising the framework against it is enough to validate the ingest pipeline + register a representative cohort for the team exhibition. All round-8 data is quasi-production (purged after the exhibition).

**Round-8 pipeline (orchestrated by the operator):**

1. **Extract** with [`tools/extract_ni_archives.py`](../../tools/extract_ni_archives.py) — walks the SMB archive, pulls each `.tgz`, extracts to `D:/projects/Nuke/test_data/<archive_basename>/` with `--strip-components=6` so the staged folder contains the acquisition's files directly (protocol.xml, recon_<idx>/, etc.). Idempotent: skips already-extracted archives via a `.extracted` sentinel.
2. **Ingest** with `tools/ingest_raw.py` using [`tools/configs/ni_jesus_archive_2025_TEST.yaml`](../../tools/configs/ni_jesus_archive_2025_TEST.yaml). The config's `filename_parse.regex:` parses the staged folder basename (= the `.tgz` name without extension) into 7 `discovered.*` fields (user / series_id / acq_date_short / short_project / short_sample / acq_datetime_full / modality). `acquisition_layout: folder` lands each acquisition as a folder-bundle under `/raw/DICOM/<year>/<year-month>/ACQ-<date>-<modality>-NNN/`.

**Scope of round 8 (Jesus's 2025 archive):**

| Series ID | Date(s) | Animals | PET archives | CT archives | Notes |
|---|---|---|---|---|---|
| 0525 | 251029 | m13–m22 | 12 | 12 | All from one session date |
| 1207 | 251021 + 3 follow-up dates | various | 30 | 30 | Multi-visit study |
| **Total** | | | **42** | **42** | **84 .tgz archives, ~298 GB compressed** |

All from operator `irene` (the only user under `2025/Jesus/`). All Molecubes (PET + CT modalities).

## Archive location and path structure

NI data lives on a Windows network share:

```
\\cicmgsp02\gnuclear2$\<YYYY>\<PI first name>\<user>\<series id>\<YYMMDD>\<archive name>.tgz
```

Each acquisition session lands as a `.tgz` archive in a date-stamped folder under a hierarchical user/series tree.

| Level | Meaning | Example |
|---|---|---|
| `<YYYY>` | Four-digit year of acquisition | `2025` |
| `<PI first name>` | First name of the group's PI (the data-owning group) | `Jesus` |
| `<user>` | Username of the researcher who ran the session | `Irene` (lowercase `irene` inside the archive name) |
| `<series id>` | Multi-digit (often 4-digit) **funded project id** — the grant or funded-project the work is billed against. **Different from MRI's animal-protocol short id**; see "Terminology" below. | `0525` or `1207` |
| `<YYMMDD>` | Six-digit acquisition date | `251029` |
| `<archive name>.tgz` | The session archive; structure broken down below | (see below) |

> **⚠️ The PI is in the directory tree, NOT in the session/archive name (2026-06-09).** The true PI is the `<PI first name>` directory level (e.g. `Jesus`) — it is **not** recoverable from a single session/archive name. So a single-folder ingest cannot know the PI from the archive name alone; it comes from traversing up to the `<PI first name>` dir (a higher-level batch import — NI "stage 2", on [`tasks/BACKLOG.md`](../../tasks/BACKLOG.md)) or from operator entry.
>
> **`protocol.txt` "Principal Investigator" is wrong — it holds the *operator's username*.** The Molecubes platform writes the username (e.g. `irene`) into the protocol.txt "Principal Investigator" field — a platform-labelling bug (under investigation 2026-06-09, likely affecting much historical data). The ingest therefore **does not** use it: the curated `ni.study.principal_investigator` and `discovered.ni_pi` are left **empty** (`ni_metadata.py`), while the raw (wrong) value is preserved verbatim in `ni._raw_metadata.protocol_txt` (raw readings are captured as-is even when the source is wrong). **PHASE-OUT:** once the platform records the PI correctly, restore reading `protocol.txt` for new files. `discovered.user` (e.g. `irene`) is parsed from the archive name and IS correct — it's the user/operator, not the PI.

### `<archive name>` structure (Molecubes archive)

The archive's filename itself encodes everything we need at the registry level — 7 fields parseable by regex:

```
<user>_<series_id>_<YYMMDD>_<short_project>_<short_sample>_<YYYYMMDDhhmmss>_<modality>.tgz
```

Per-component breakdown:

| Component | Meaning | Example |
|---|---|---|
| `<user>` | Username (same as the path level), lowercase. | `irene` |
| `<series_id>` | Funded-project id (same as path level). | `0525` |
| `<YYMMDD>` | Acquisition date (six-digit). Redundant with path; kept for archive self-identification. | `251029` |
| `<short_project>` | **Animal-protocol short id** (4-digit). For some animal sessions matches `<series_id>`; for others (e.g. 1207 series with `<short_project>=0424`) they differ. The animal protocol is a regulatory artifact; the series_id is a financial-administrative one. | `0525` or `0424` |
| `<short_sample>` | Sample identifier. For animal work: `<animal type><short animal id>` (e.g. `m17`). For QC/QA: free-text label (may contain underscores — handled by the regex's alternation between the animal pattern and a `phantom` prefix). | `m17`, `m22`, or `phantom_xyz` |
| `<YYYYMMDDhhmmss>` | Full timestamp of the acquisition (machine-issued). | `20251029100641` |
| `<modality>` | Imaging modality: `PET` / `CT` / `SPECT` / `OI`. Drives the per-case instrument code via `discovered.modality`. | `PET` |

Round-8 regex (the staged folder basename = archive basename without `.tgz`):

```
^(?P<user>[a-z]+)_(?P<series_id>\d+)_(?P<acq_date_short>\d{6})_(?P<short_project>\d+)_(?P<short_sample>[A-Za-z]+\d+|phantom[_a-z0-9]*)_(?P<acq_datetime_full>\d{14})_(?P<modality>PET|CT|SPECT|OI)$
```

### Inside the `.tgz` (real structure, observed 2026-05-22, revised 2026-05-26)

The archive unpacks to a 6-level nested tree before the acquisition's actual files. `tools/extract_ni_archives.py --strip-components=6` strips that nesting, leaving the staged folder with the acquisition's content directly. The leaf structure differs **per modality**:

**CT acquisition** (e.g. `irene_0525_251029_0525_m13_20251029101558_CT/`):

```
<staged_folder>/
├── .extracted           (sentinel — extract_ni_archives.py)
│
│   --- ACQUISITION-LEVEL FILES ---
├── protocol.txt         (human-readable acquisition protocol)   << KEEP — into acquisition_aux/
├── protocol.xml         (XML form)                              << KEEP
├── acqparams.xml        (acquisition parameters)                << KEEP
├── recontemplate.xml    (reconstruction template)               << KEEP
├── acquisition.log      (small operational log)                 << KEEP (audit)
│
├── data.raw             (~6 GB raw detector data)               << DROP — platform owns
├── bright.raw, dark.raw, badpixels.map     (calibration)        << DROP
├── attmap.amap          (attenuation map)                       << DROP
├── monitoring.csv, sequence.csv            (operational logs)   << DROP
├── xrayserver.log                                               << DROP
├── ACQSTATUS, DOWNLOADED, REMIDOWNLOADED   (status files)       << DROP
├── calibrationParameters.xml                                    << DROP
├── reconstructionParameters{ATTMAP,HR,LR,UHR}.xml               << DROP (recon templates, not per-recon)
│
│   --- PER-RECONSTRUCTION FOLDERS ---
├── recon_0/             (CT ISRA standard reconstruction)
│   ├── 20251029101558_CT_ISRA_0.dcm     (THE primary image)    << KEEP
│   ├── 20251029101558_CT_ISRA_0.img     (binary mirror)         << DROP — .dcm has the data
│   ├── reconparams.txt, reconparams.xml                         << KEEP
│   ├── reconstruction.log                                       << KEEP
│   ├── RECONSTATUS, preview.res                                 << DROP
├── recon_1/             (CT ISRA variant)                        ← same structure as recon_0
└── recon_2/             (ATTMAP — for PET attenuation correction)
    ├── ATTMAP.dcm                                                << KEEP
    └── ... (same shape as recon_0)
```

**PET / SPECT acquisition** (e.g. `irene_0525_251029_0525_m13_20251029100311_PET/`):

```
<staged_folder>/
│   --- ACQUISITION-LEVEL FILES ---  (same set as CT — KEEP rules identical)
├── protocol.txt, protocol.xml, acqparams.xml, recontemplate.xml, acquisition.log     << KEEP
├── eventdata_0.list, eventdata_0.dt, eventdata_0.header     (PET event lists)      << DROP — platform owns
├── attmap.amap, singles.stat, spectrum.bin                                          << DROP
├── monitoring.csv, sequence.csv, ACQSTATUS, REMIDOWNLOADED                          << DROP
├── recon.ini, recontemplate.xml                                                     << DROP at acq root (only per-recon copy kept)
│
│   --- PER-RECONSTRUCTION FOLDER (typically just recon_0) ---
└── recon_0/
    ├── reconparams.txt, reconparams.xml                          << KEEP
    ├── reconstruction.log                                        << KEEP
    ├── recon.ini                                                 << KEEP (small per-recon config)
    ├── RECONSTATUS                                               << DROP
    ├── atten_192x192x384.bin            (attenuation binary)     << DROP
    ├── reconattcorr_iter30_192x192x384.bin   (recon binary)      << DROP — .dcm in frame_0/iter_30 is the analysis copy
    ├── bed0_counts.stat                                          << DROP
    └── frame_<n>/             (one per time-frame; static PET has just frame_0)
        └── iter_30/           (iteration count fixed at 30 in current Molecubes setup)
            └── 20251029100311_PET_OSEM_0.dcm    (THE primary image for this frame)    << KEEP
```

### What gjesus3 keeps vs what stays on the platform (v2 — 2026-05-27)

**Principle:** gjesus3 is the research-facing working layer; the Nuclear Imaging platform archive on `\\cicmgsp02\gnuclear2$` IS the long-term store for original bytes — Molecubes keeps the original `.tgz` archives indefinitely without alteration, the highest trust tier of the three platform classes ([13_GJESUS3_ROLE §5.6](../../mfb-rdm-docs/13_GJESUS3_ROLE.md)). We don't double-archive; we extract the researcher-essential surface.

**Keep on gjesus3 at `/raw/DICOM/<year>/<year-month>/ACQ-<date>-<modality>-NNN/`:**

```
ACQ-<YYYYMMDD>-<MODALITY>-NNN/
  metadata.json              <-- parsed protocol.txt + 3 XMLs + per-DICOM headers (with UIDs)
  checksums.json
  README.txt
  <ACQ-ID>.data/             <-- the data bundle (parallels microscopy <ACQ-ID>.czi)
    recon<X>.dcm             (CT — one per reconstruction)
    recon<X>_frame<Y>.dcm    (PET/SPECT — one per time frame)
```

That's it on disk. NO `acquisition_aux/`, NO `reconstructions/recon_<idx>/`, NO per-recon `reconparams.txt`, NO `reconstruction.log`, NO `recon.ini`. Their *contents* are in `metadata.json.ni._raw_metadata` (parsed dicts), so no information is lost — just no on-disk duplication.

**Stays only on the Molecubes archive** (lives indefinitely there; the 1% case routes back through the platform):
- **All acquisition-root aux files**: `protocol.txt`, `protocol.xml`, `acqparams.xml`, `recontemplate.xml`, `acquisition.log` (parsed forms in sidecar)
- Raw event/detector data: `data.raw`, `bright.raw`, `dark.raw`, `eventdata_*`
- Calibration: `attmap.amap`, `badpixels.map`, `calibrationParameters.xml`
- Operational logs: `monitoring.csv`, `sequence.csv`, `xrayserver.log`
- Status files: `ACQSTATUS`, `DOWNLOADED`, `REMIDOWNLOADED`, `registration.matrix`
- Per-recon non-DICOM (parsed where useful, source not copied): `reconparams.txt`/`reconparams.xml`, `reconstruction.log`, `recon.ini`
- Per-recon binary mirrors of the DICOM: `.img` (CT), `reconattcorr_iter30_*.bin` (PET), `atten_*.bin`, `bed0_counts.stat`, scatter binaries
- (v2.1: multi-frame DICOMs are now KEPT — see "Multi-frame DICOM" section below for the v2 → v2.1 history)

**Storage delta:** ~6 GB per acquisition source archive → **a few MB** on gjesus3 (just the DICOMs). Across the 84-acq round-8 cohort: ~358 GB → ~6.5 GB.

### Multi-frame DICOM (frameMULTI files)

The Molecubes reconstruction engine generates two parallel DICOM representations for **dynamic PET/SPECT studies** (those with multiple time frames):

1. **Per-frame DICOMs** — one DICOM per frame, deep inside `recon_<X>/frame_<Y>/iter_30/`. Each carries a 3D volume (e.g. 192×192×384). Widely supported by viewers; unambiguous (one file = one time point).
2. **A multi-frame DICOM at recon root** — a single file (filename contains `frameMULTI`, e.g. `<basename>_frameMULTI_iter30.dcm`) that bundles ALL frames into one DICOM with `ImageType=DYNAMIC` and `NumberOfFrames` spanning all frames (e.g. 768 for a 2-frame study with 384 slices each). Closer to the "one file per acquisition" ideal.

**For static scans (1 frame), neither file is multi-frame in the time sense** — the per-frame DICOM is the only one and there's no `frameMULTI` file. The multi-frame phenomenon only appears for genuinely dynamic studies.

**Round-8 v2.1 decision (2026-05-27 update):** keep BOTH representations alongside each other on gjesus3. The multi-frame DICOM is named `recon<X>_frameMULTI.dcm` inside `<ACQ-ID>.data/`, sibling to the per-frame `recon<X>_frame<Y>.dcm` files. Reasoning:
- The multi-frame DICOM's advanced metadata (per-frame functional groups, frame time vectors, temporal positions) hasn't been fully validated — some viewers misrender it — but the file IS the canonical "single file per acquisition" form the platform exports, and downstream tools may prefer it.
- Disk cost is small (~55 MB per multi-frame DICOM; only a handful of acquisitions affected in any cohort).
- Researchers can pick either representation per their tool's preference. Per-frame DICOMs remain the safe default; multi-frame is available when wanted.

**Sidecar shape:** all DICOMs (per-frame AND multi-frame) appear in `metadata.json.ni.reconstruction.by_index.<idx>.dicoms[]`, each with `dst_basename` (gjesus3 filename), `src_relpath` (original location in the upstream archive), and curated DICOM headers (StudyInstanceUID / SeriesInstanceUID / SOPInstanceUID + ImageType, NumberOfFrames, etc.). Distinguishing characteristic: multi-frame DICOMs have `ImageType` ending `'DYNAMIC'` (per-frame have `'VOLUME'`) and `NumberOfFrames` equal to per-frame `NumberOfFrames × n_frames`.

**Round-8 v2 → v2.1 history:** v2 (initial decision) skipped the multi-frame DICOMs entirely and recorded their existence in a separate `multi_frame_dicoms_on_platform` sidecar field. After review the user requested keeping them inline (this section's current behaviour); v2.1 landed via a one-acquisition spot-fix (only m17 PET, `ACQ-20251022-PET-001` → re-ingested as `ACQ-20251022-PET-007`). The `multi_frame_dicoms_on_platform` sidecar field was retired.

**Future-work:** validate the multi-frame DICOM's advanced metadata (per-frame timing tags, frame reference time, dose history vector). If clean, consider making it the canonical single primary file and dropping the per-frame copies. Sidecar shape supports the transition without code changes. Tracked in `tasks/tasks.md` §3.1.

### Round-8 v2 (2026-05-27)

Following round-8 v1 (2026-05-26, which fixed the original 2026-05-22 piggyback-on-ParaVision bug), v2 reshaped the on-disk layout per operator feedback:

| Change | v1 (2026-05-26) | v2 (2026-05-27) |
|---|---|---|
| Aux file storage | `acquisition_aux/protocol.txt` + 4 more files on disk | Parsed into `metadata.json.ni._raw_metadata` only |
| Per-recon non-DICOM | `reconstructions/recon_<X>/{reconparams.txt, reconparams.xml, reconstruction.log, recon.ini}` on disk | Parsed `reconparams.xml` content into `_raw_metadata.reconparams_by_idx`; others dropped |
| Data folder name | `reconstructions/recon_<X>/` | `<ACQ-ID>.data/` (flat, mirrors microscopy `<ACQ-ID>.czi`) |
| DICOM names | Original from source | Renamed flat: `recon<X>.dcm` (CT) or `recon<X>_frame<Y>.dcm` (PET/SPECT) |
| protocol.txt in sidecar | Verbatim string | Parsed dict (every line, no allowlist) |
| DICOM UIDs in sidecar | Not captured | `StudyInstanceUID` / `SeriesInstanceUID` / `SOPInstanceUID` first in curated headers |
| Multi-frame DICOMs | Copied to disk (mixed into `reconstructions/`) | Not copied; existence + headers recorded in sidecar |
| .lnk shortcut target | The ACQ folder | The `.data` subfolder (direct to DICOMs) |

### Round-8 retrospective (the original bug fixed 2026-05-26)

The original round-8 ingest (2026-05-22) was wrong in a specific way worth recording: the YAML config piggybacked on `tools/ingest_raw.py::copy_paravision_exam`, which was built for Bruker ParaVision (looks for `pdata/<idx>/` for reconstructions). Molecubes archives have `recon_<idx>/` instead — different name, different inner structure. The function found no `pdata/`, fell back to its other behaviour ("copy every file at source root into `acquisition_aux/`"), and dumped 6 GB of `data.raw` + raw event data per acquisition into `acquisition_aux/` while **never copying any of the `.dcm` files** (which live inside `recon_<idx>/` and were ignored).

Fix (2026-05-26): new dedicated `copy_ni_acquisition()` function in `tools/ingest_raw.py` (selective allowlist of researcher-essential files only) + new `tools/ingest/ni_metadata.py` extractor (parses `protocol.txt` + XML aux + DICOM headers into the `ni:` sidecar block). Round-8 fully purged and re-ingested with the slim shape — then refined again on 2026-05-27 (v2) per the table above.

The error itself is documented for future understanding: **shared functions across instruments quietly fail when the source structure doesn't match the function's assumed structure.** Per-instrument copy strategies (selected via `copy_strategy:` in YAML) avoid this class of bug.

## Terminology: series id (NI) ≠ animal protocol short id (MRI)

This is the most important conceptual clarification (now empirically verified by round-8 archives):

- **NI `<series_id>`** = **funded-project id**. A financial-administrative number. Identifies the grant or funded project the work charges against. Example: `0525` (funded project) or `1207` (different funded project).
- **NI `<short_project>`** = **animal-protocol short id** (same shape as MRI's `<short project id>`). A regulatory artifact identifying the approved animal-use protocol. Example: `0525` (animal protocol) or `0424` (different animal protocol).

Round-8 archives show that `series_id` and `short_project` are often the same number (when a funded project has a 1:1 animal protocol), but not always — the 1207 series uses animal protocol `0424` (different number). Some users conflate them in conversation — both feel like "the project number" — but they live in different administrative systems.

**For gjesus3 project workspaces**, we use `<short_project>` (the animal-protocol short id) as the project `short_name` — same convention as MRI + AxioScan: `ae-biomegune-<short_project>`. This means round-8 NI cross-modally reuses `proj-ae-biomegune-{0424, 0525}` workspaces from rounds 4 + 6 when the protocol matches.

## Reconstruction handling (archive mode)

Each `.tgz` contains ONE reconstruction (`recon_0/` for PET, `recon_1/` for CT in the round-8 data). Unlike MRI (where one acquisition may have multiple reconstructions and the operator selects which to keep via the `reconstructions:` YAML flag), Molecubes archives are inherently single-recon — what's in the archive is what we ingest. The `reconstructions:` flag is therefore not used in the round-8 NI template.

**Frame semantics:** PET archives have a `recon_<idx>/frame_<n>/iter_30/` deep structure carrying time-resolved iterative-reconstruction outputs; CT archives have a simpler `recon_<idx>/` flat structure. Round-8 archive-mode ingest preserves whatever's in the archive as-is — we don't sub-select frames or iterations.

## Future-mode preview (live-machine workflow)

When live-machine ingest lands (blocked on Unai answering the workflow question), the source will be a folder on the acquisition machine, not a .tgz on the archive. Expected differences from archive mode:

- Source path on the acquisition box, not the SMB archive.
- No tgz extraction step (folder is already a folder).
- Possibly different inner structure (the platform may pre-organise differently from what's archived).
- Possibly DICOM/NIfTI exports alongside (if researchers have run conversion steps locally before ingest).

A separate per-instrument template (`molecubes_ni_live.yaml` or similar) will be added then, alongside the round-8 archive-mode template (which stays in service for any further archive-mode batches).

## Auto-discovered fields (archive mode)

Round-8 ingest exposes these `discovered.*` fields per acquisition:

- `discovered.user` — NI user (e.g. `irene`)
- `discovered.series_id` — funded-project id (e.g. `0525`, `1207`)
- `discovered.acq_date_short` — YYMMDD form (e.g. `251029`)
- `discovered.short_project` — animal-protocol short id (e.g. `0525`, `0424`)
- `discovered.short_sample` — sample identifier (animal pattern or `phantom_*` free-text)
- `discovered.acq_datetime_full` — full YYYYMMDDhhmmss timestamp (e.g. `20251029100641`)
- `discovered.modality` — `PET` / `CT` / `SPECT` / `OI` — drives the per-case `instrument` registry column
- `discovered.folder_name` — standard auto-discovery, same as the archive basename

DICOM-header / XML-aux extraction (analogous to ParaVision's `discovered.mri_*`) is **deferred** — Molecubes archives are .bin + XML, not .dcm, so a future-work extractor would target the XML files instead. Queued in `tasks/tasks.md §3.1`.

## Default `link_filename` pattern (round 8)

```yaml
link_filename: "${discovered.modality}_${discovered.short_sample}_${acq_date}_${discovered.acq_datetime_full}"
```

Example resolved: `PET_m14_20251029_20251029100641` (PET acquisition of mouse m14 under protocol 0525 on 2025-10-29 at 10:06:41). Unique per (modality, animal, exact timestamp) — no collisions even when the same animal is scanned in PET + CT in the same session.

## What's deferred / open

- **Live-machine NI ingest** — blocked on Unai answering the workflow question. Round-8 archive mode is the only NI path operational today.
- **XML-aux metadata extraction** (analogous to ParaVision's JCAMP-DX extractor) — `discovered.ni_*` fields from `protocol.xml`, `acqparams.xml`, etc. Queued in `tasks.md §3.1`. Currently the YAML regex gives us most of what we need at registry level.
- **Multi-modality project reconciliation** (funded-project id from NI vs animal-protocol short id from MRI → same researcher, same gjesus3 project?). Current convention uses the animal-protocol id (`short_project`) for project `short_name` — cross-modality demos work when the protocol matches.
- **User-as-operator permissions:** NI is run directly by researchers (no dedicated technician); same model gap as internal MRI. Tracked in `tasks/tasks.md §3.3`.

## Related documents

- [`nuclear_imaging_platform_description.md`](nuclear_imaging_platform_description.md) — equipment / vendor spec
- [`../mri-platform/internal_mri_data_handling_workflow_notes.md`](../mri-platform/internal_mri_data_handling_workflow_notes.md) — analogous MRI walkthrough
- `mfb-rdm-docs/13_GJESUS3_ROLE.md` — research-facing reframe (motivates the no-zip folder layout for internal modalities, archive-mode as a pragmatic Phase A)
- `tools/templates/instruments/molecubes_ni.yaml` — per-instrument template (archive mode)
- `tools/configs/ni_jesus_archive_2025_TEST.yaml` — round-8 batch config (Jesus's 2025 archive)
- `tools/extract_ni_archives.py` — pre-ingest extraction utility
- `tasks/tasks.md §4.7` — round-8 task detail trail


