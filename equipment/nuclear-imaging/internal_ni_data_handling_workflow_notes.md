# Internal Nuclear Imaging — data-handling workflow notes

**Status:** 🔶 Round 8 active in **archive mode** (2026-05-22). Live-machine workflow still future.
**Last updated:** 2026-05-22

> This document captures the systematic naming and archive structure of the **internal Nuclear Imaging (NI) platform** at CIC biomaGUNE. Two ingest paths are documented separately below:
>
> - **Archive mode** (round 8, 2026-05-22 — IMPLEMENTED): pull pre-archived `.tgz` files from `\\cicmgsp02\gnuclear2$\<year>\<PI>\`, extract locally, and ingest as folder-as-primary acquisitions. Per-instrument template at [`tools/templates/instruments/molecubes_ni.yaml`](../../tools/templates/instruments/molecubes_ni.yaml).
> - **Live-machine mode** (future): direct ingest from the acquisition box (Molecubes / MILabs VECTor). Different source shape (a folder, not a .tgz) — will get its own per-instrument template when the workflow + access conversation with the platform manager closes.
>
> Companion docs: [`nuclearImaging_platform_description.md`](nuclearImaging_platform_description.md) (platform / equipment), [`equipment/mri-platform/internal_mri_data_handling_workflow_notes.md`](../mri-platform/internal_mri_data_handling_workflow_notes.md) (analogous MRI workflow).

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

### Inside the `.tgz` (real structure as of 2026-05-22)

The archive unpacks to a 6-level nested tree before the acquisition's actual files. `tools/extract_ni_archives.py --strip-components=6` strips that nesting, leaving the staged folder with the acquisition's content directly:

```
<staged_folder>/         (= D:/projects/Nuke/test_data/<archive_basename>/)
├── .extracted           (sentinel marker — extract_ni_archives.py)
├── protocol.xml         (acquisition protocol — XML, machine-issued)
├── protocol.txt         (human-readable version)
├── acqparams.xml        (acquisition parameters)
├── recontemplate.xml    (reconstruction template)
├── recon.ini            (reconstruction config)
├── acquisition.log
├── monitoring.csv
├── sequence.csv
├── eventdata_0.list, .dt, .header
├── singles.stat
├── spectrum.bin
├── attmap.amap          (attenuation map; PET only)
├── ACQSTATUS
├── REMIDOWNLOADED
├── registration.matrix
└── recon_<idx>/         (the reconstruction subfolder — Molecubes labels
                           PET reconstructions `recon_0/` and CT `recon_1/`
                           in this data, but it varies; we keep what's
                           in the archive)
    ├── reconattcorr_iter30_192x192x384.bin    (PET) / reco_<...>.bin (CT)
    ├── scatter_*.bin                          (PET corrections)
    └── frame_0/                               (PET dynamic frames — has
                                                 iter_30/ inside; CT
                                                 typically has no frame
                                                 subdivision)
        └── iter_30/
            └── <machine-given name>           (binary recon volume)
```

**Important correction from earlier draft of this doc** (pre-round-8): the leaf-level files in Molecubes Nuclear Imaging archives are **`.bin` reconstruction binaries + XML aux**, NOT DICOM `.dcm`. The PI was likely conflating with a different NI workflow (perhaps MILabs VECTor, which exports DICOM + NIfTI per its description in `nuclearImaging_platform_description.md`). Going forward, **assume Molecubes-native (.bin + XML) for round 8 archives**, and revisit DICOM/NIfTI specifics when live-machine ingest lands.

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

- [`nuclearImaging_platform_description.md`](nuclearImaging_platform_description.md) — equipment / vendor spec
- [`../mri-platform/internal_mri_data_handling_workflow_notes.md`](../mri-platform/internal_mri_data_handling_workflow_notes.md) — analogous MRI walkthrough
- `mfb-rdm-docs/13_GJESUS3_ROLE.md` — research-facing reframe (motivates the no-zip folder layout for internal modalities, archive-mode as a pragmatic Phase A)
- `tools/templates/instruments/molecubes_ni.yaml` — per-instrument template (archive mode)
- `tools/configs/ni_jesus_archive_2025_TEST.yaml` — round-8 batch config (Jesus's 2025 archive)
- `tools/extract_ni_archives.py` — pre-ingest extraction utility
- `tasks/tasks.md §4.7` — round-8 task detail trail

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
| `<user>` | Username of the researcher who ran the session | `ana_garcia` |
| `<series id>` | Multi-digit (often 4-digit) **funded project id** — the grant or funded-project the work is billed against. **Different from MRI's animal-protocol short id**; see "Terminology" below. | `2231` |
| `<YYMMDD>` | Six-digit acquisition date | `250612` |
| `<archive name>.tgz` | The session archive; structure broken down below | (see below) |

### `<archive name>` structure

The archive's filename itself encodes useful metadata:

```
<user>_<series id>_<YYMMDD>_<short project id>_<short sample id>.tgz
```

Per-component breakdown:

| Component | Meaning | Note |
|---|---|---|
| `<user>` | Username (same as the path level) | |
| `<series id>` | Funded-project id (same as path level) | |
| `<YYMMDD>` | Acquisition date (same as path level) | Redundant with path; kept for archive self-identification |
| `<short project id>` | **Animal-protocol short id** (in animal work) OR an arbitrary label for QA/QC | Same shape as MRI's `<short project id>` |
| `<short sample id>` | Sample identifier. For animal work: `<animal type><short animal id>` (e.g. `m17`). For QC/QA: free-text label. **Sub-parsing inside may use underscore** — see ambiguity note below. | Same shape as MRI's `<short sample id>` |


