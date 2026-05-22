# Internal Nuclear Imaging — data-handling workflow notes

**Status:** 📋 Future-round prep (round 7 or later). NOT YET IMPLEMENTED.
**Last updated:** 2026-05-22

> This document captures the systematic naming and archive structure of the **internal Nuclear Imaging (NI) platform** at CIC biomaGUNE so the round when we ingest NI data can be planned cleanly. **No NI data is ingested into gjesus3 yet.** Companion doc: [`nuclearImaging_platform_description.md`](nuclearImaging_platform_description.md) (platform / equipment).
>
> Round-6 (Internal MRI) shipped the naming-convention auto-discovery framework that NI ingest will reuse. See [`equipment/mri-platform/internal_mri_data_handling_workflow_notes.md`](../mri-platform/internal_mri_data_handling_workflow_notes.md) "Systematic naming convention" section for the analogous MRI breakdown.

## Why this doc exists now

The NI ingest round is **blocked on the platform manager Unai answering a question about naming-convention discrepancies** (tracked in `tasks/tasks.md` §0 + §4.7). While that conversation pauses, we still know enough about the existing archive structure to document the convention now and lock in the parser design.

When the round starts: copy `tools/templates/instruments/mri_bruker.yaml` as a starting point, swap the regex + per-instrument extractor stub + `link_filename` pattern, and ingest.

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

### Inside the `.tgz`

The archive unpacks (gzip → tar → directory tree) to a nested structure with redundant prefix levels:

```
<archive name>.tgz
└── <archive name>.tar
    └── <user>/
        └── <series id>/
            └── <YYMMDD>/
                └── <short project id>_<short sample id>/
                    └── <date and time>_<modality>/
                        └── <date and time>_<modality>/
                            └── recon_<reconstruction number>/
                                └── frame_<frame number>iter_30/
                                    └── <machine-given name>.dcm
```

What's at each level (the levels that aren't just redundancy):

| Level | What it represents |
|---|---|
| `<date and time>_<modality>` | Per-session prefix; `<modality>` is the actual imaging modality code (PET, SPECT, CT, OI). The duplicated `_<modality>` level appears to be a Molecubes/MILabs convention quirk. |
| `recon_<reconstruction number>` | **One reconstruction = one ACQ-ID** (ISA "assay"). This is the parser's target level. |
| `frame_<frame number>iter_30` | One time-point or iteration within the reconstruction. The `iter_30` suffix is the iterative-recon iteration count. |
| `<machine-given name>.dcm` | The actual DICOM frame file. |

**Implementation note (future round):** the ingest pipeline will need to walk the tgz contents to identify the `recon_<n>/` levels per acquisition. This implies either (a) extracting the tgz to a local staging area before running `expand_batch`, or (b) extending the ingest with a tgz-aware glob — option (a) is simpler and matches the existing "ftp_mirror.py to local staging, then ingest" pattern. Tracked in `tasks/tasks.md` §3.1 as the "NI tgz nested-archive parsing" item.

## Terminology: series id (NI) ≠ animal protocol short id (MRI)

This is the most important conceptual clarification:

- **NI's `<series id>`** = **funded-project id**. A financial-administrative number. Identifies the grant or funded project the work charges against.
- **MRI's `<short project id>`** = **animal-protocol short id**. A regulatory artifact identifying the approved animal-use protocol.

These are *different numbers*. Users sometimes conflate them — both feel like "the project number" — but they live in different administrative systems.

For gjesus3, both end up in `registry.project_hint` (and eventually as the project workspace's `short_name`), but they parametrise *different identifiers*. The chosen convention for project `short_name`:

- MRI: `ae-biomegune-<animal protocol short id>` (e.g. `ae-biomegune-0424`).
- NI: TBD when the round starts — likely `<funded project id>` directly or with a similar prefix.

The **same researcher** working under the **same animal protocol** might bill the data to **different funded projects** across NI vs MRI. Multi-modality projects on gjesus3 will need a way to reconcile these — possibly a many-to-many `project_aliases` future field, or a hand-curated registry table. Tracked as a future open question.

## `<short sample id>` underscore ambiguity

For animal sessions, `<short sample id>` is typically `<animal type><short animal id>` — short, no internal underscore (`m17`, `r5`).

For QC/QA or non-standard work, users sometimes write free-text identifiers that DO contain underscores (e.g. `phantom_xyz_v2`). Since underscores are also the convention separator in `<archive name>`, naive split-on-underscore parsing of the archive name can mis-extract `<short sample id>` for non-standard cases.

**Mitigation (future round):** use the same `regex:` extractor pattern in `filename_parse` as MRI does — pull `<series id>`, `<YYMMDD>`, `<short project id>` from positional anchors, then take whatever remains as `<short sample id>` (allowing internal underscores).

## Reconstruction and frame semantics

For NI workflows:

- **Reconstruction** (`recon_<n>/`) corresponds to one ACQ-ID. Like MRI, the same acquisition may have multiple reconstructions (different algorithms, parameters); the user-trusted one will be operator-selected per batch via `reconstructions:` YAML flag.
- **Frame** (`frame_<n>iter_30/`) is a finer time-resolved (or iterative) unit. The whole set of frames in a reconstruction makes up the analytical dataset. Frames stay together inside the ACQ folder.

The naming-convention parallel with MRI's `pdata/<idx>/` is intentional: both use a numeric index to differentiate auto vs user-controlled reconstructions, and both produce per-frame DICOM in the deepest level.

## Auto-discovered fields (proposed for the future round)

When the NI ingest round lands, the YAML config should expose:

- `discovered.user` — NI user (from path / archive name)
- `discovered.series_id` — funded-project id (from path / archive name)
- `discovered.acquisition_date_short` — YYMMDD form (from path / archive name)
- `discovered.short_project_id` — animal-protocol short id when applicable
- `discovered.short_sample_id` — sample identifier (free text — may contain underscores)
- `discovered.modality` — PET / SPECT / CT / OI from the inner `<date-time>_<modality>` folder
- `discovered.recon_number` — reconstruction index from `recon_<n>/`
- `discovered.frame_count` — number of `frame_*iter_30/` subfolders
- `discovered.dicom_*` — DICOM-header extracted curated subset (still deferred — see §3.1 in tasks.md)

## Default `link_filename` pattern (for the future round)

Analogous to MRI's pattern:

```yaml
link_filename: "${discovered.modality}_${sample_id}_${acq_date}_${discovered.recon_number}"
```

Example resolved: `PET_0424_m17_20250612_3` (PET acquisition of mouse 17 under protocol 0424, recon /3, dated 2025-06-12).

## What's deferred / open

- Implementation of the NI ingest itself — blocked on Unai answering the naming-convention question.
- Whether reconstruction selection should be on `recon_<n>` indices or always-keep-all (the MRI `reconstructions:` flag is the precedent — keep it consistent).
- The `<short sample id>`-with-underscores edge case — handled via regex; needs real-data validation.
- DICOM-header extraction for NI — independent of NI ingest; same code path as the future collaborator-XMRI extractor.
- Multi-modality project reconciliation (funded-project id from NI vs animal-protocol short id from MRI → same researcher, same gjesus3 project?).
- User-as-operator permissions: NI is run directly by researchers (no dedicated technician); same model gap as internal MRI. Tracked in `tasks/tasks.md` §3.3.

## Related documents

- [`nuclearImaging_platform_description.md`](nuclearImaging_platform_description.md) — equipment / vendor spec
- [`../mri-platform/internal_mri_data_handling_workflow_notes.md`](../mri-platform/internal_mri_data_handling_workflow_notes.md) — analogous MRI walkthrough
- `mfb-rdm-docs/13_GJESUS3_ROLE.md` — research-facing reframe (motivates the no-zip folder layout for internal modalities)
- `tasks/tasks.md` §4.7 — round 7 NI ingest task
