# LSM 900 confocal — data handling workflow notes

**Status:** 🔶 Round 7 active (2026-05-22)
**Last updated:** 2026-05-22

> Per-instrument workflow notes for the **Zeiss LSM 900 confocal microscope** (instrument code `LSM9`). This file captures the operator-supplied data-handling pattern + the parsable naming convention used by the round-7 per-instrument template at [`tools/templates/instruments/lsm900.yaml`](../../tools/templates/instruments/lsm900.yaml).
>
> The LSM 900 is the **third Zeiss `.czi`-producing microscope** in scope (after AxioScan 7 and Cell Observer). It reuses the same `tools/ingest/czi_metadata.py` extractor — the round-7 ingest needed no new code, only a new per-instrument template + per-batch config.

## Operator directions (Ainhize Urkola Arsuaga, 2026-05-22)

Captured verbatim from the operator note that drove round 7:

> **Address:** `gJesus\Ainhize\CONFOCAL LSM 900\LAURA_UPTAKE_LP-IONP-doxo_MDA`
>
> I organize it, inside my GJesus folder:
> - **Confocal LSM 900**: the name of the team
> - **LAURA_UPTAKE_LP-IONP-doxo_MDA:**
>   - LAURA: For the person who are the images
>   - UPTAKE_LP-IONP-doxo: Experiment
>   - MDA: Cell Line
>
> The name of the files, for example: `Z-stack_LP_IONP-doxo_20x_6h_2`
> Means: `Replica condición_número imágen_condición_magnificación_tiempo Type`

Same operator + same K: share + same parent folder (`Ainhize/`) as the Cell Observer workflow ([`../cell-observer/cell_observer_data_handling_workflow_notes.md`](../cell-observer/cell_observer_data_handling_workflow_notes.md)). The two confocal/cells-mode workflows are operationally parallel: data lives on the instrument-local PC, the operator manually saves retained files to their own group-drive folder. The naming convention differs between Cell Observer and LSM 900 — see below.

## Systematic naming convention (parsable)

### Path structure

```
K:/gjesus/Ainhize/CONFOCAL LSM 900/<batch_folder>/<filename>.czi
```

| Level | Meaning | Example |
|---|---|---|
| `K:/gjesus/` | Group drive root (same as Cell Observer + AxioScan) | — |
| `Ainhize/` | Operator's parent folder (Ainhize Urkola Arsuaga manages the confocal data). Other operators MAY use parallel parent folders in future. | `Ainhize` |
| `CONFOCAL LSM 900/` | Team / instrument folder ("the name of the team" per the operator's note) | — |
| `<batch_folder>/` | One batch — see batch-folder structure below | `LAURA_UPTAKE_LP-IONP-doxo_MDA` |
| `<filename>.czi` | The acquisition file — see filename structure below | `Z-stack_LP_IONP-doxo_20x_6h_2.czi` |

### Batch folder structure

```
<researcher>_<experiment-w/-internal-underscores>_<cell_line>
```

| Component | Meaning | Example |
|---|---|---|
| `<researcher>` | Person who owns the images (first name in uppercase) | `LAURA` |
| `<experiment>` | Free-form experiment label. **May contain internal underscores** — naive split-on-underscore would mis-parse it. | `UPTAKE_LP-IONP-doxo` |
| `<cell_line>` | Cell line / sample type | `MDA` |

**Round 7's per-instrument template handles the internal-underscore ambiguity** via a greedy-middle regex in `filename_parse` (`source: parent_name`):

```
^(?P<researcher>[^_]+)_(?P<experiment>.+)_(?P<cell_line>[^_]+)$
```

The leading `[^_]+` and trailing `_[^_]+$` anchors pin researcher and cell_line to the first and last underscore-delimited chunks; the greedy `.+` middle captures everything in between as the experiment label. The technique is the same pattern used by the MRI round-6 template for the `jrc_?\d{6,8}_m\d+_\d{4}` extraction from messy FTP folder names.

### Filename structure (operator's intended convention)

Per the operator: `<replica_type>_<image_label>_<condition>_<magnification>_<timepoint>_<type>.czi`

| Component | Meaning | Example |
|---|---|---|
| `<replica_type>` | Acquisition type / replica descriptor (often `Z-stack`; sometimes omitted) | `Z-stack` |
| `<image_label>` | Image label ("número imágen" per the operator — actually a label, not always numeric) | `LP` |
| `<condition>` | Imaging condition | `IONP-doxo` |
| `<magnification>` | Magnification | `20x` |
| `<timepoint>` | Time point — or `ctrl` for control samples | `6h`, `24h`, `ctrl` |
| `<type>` | Replicate / type number (often omitted on the first of a series) | `2` |

### Filename variability — why round 7 doesn't positionally parse it

Real data in the LAURA_UPTAKE_LP-IONP-doxo_MDA batch shows **variable chunk count** across files:

| Filename | Chunks (split by `_`) | Notes |
|---|---|---|
| `Z-stack_LP_IONP-doxo_20x_6h_2.czi` | 6 | The operator's example — fully populated |
| `Z-stack_LP_IONP-doxo_20x_24h.czi` | 5 | Trailing `<type>` omitted |
| `Z-stack_LP_IONP-doxo_20x_ctrl.czi` | 5 | `ctrl` instead of timepoint |
| `Z-stack_LP_IONP-doxo_20x_ctrl_2.czi` | 6 | `ctrl` + replicate |
| `LP_IONP-doxo_20x_48h.czi` | 4 | `Z-stack` prefix omitted entirely |

Positional `filename_parse` with `fields: [...]` requires a stable chunk count. With 4 / 5 / 6 chunks mixing in the same batch, a positional spec would reject half the files (the parser raises `FilenameParseError` when chunks < fields).

**Round 7 keeps the filename unparsed in the YAML:**
- The full filename is available as `${discovered.filename}` (includes `.czi`) and via `${original_name}`.
- The `.czi`-embedded metadata (`discovered.czi_*`) provides the canonical truth for objective, magnification (`czi_objective_mag`), pixel size, channels, Z-stack depth (`czi_size_z`), acquisition datetime, ZEN version, etc. — much richer than what the filename encodes anyway.
- For the few filename-only fields (condition / timepoint / replicate), the operator can add them to project-level metadata after ingest (the `/projects/<proj>/metadata/<acq_id>.json` pattern from the 2026-05-12 metadata-location-split decision — see [`08_METADATA §1`](../../mfb-rdm-docs/08_METADATA.md)).

**Future enhancement** (queued in [`tasks/tasks.md §3.1`](../../tasks/tasks.md)): a per-component `source:` for `filename_parse` so the regex can target `parent_name` (batch folder) while a separate positional spec OR a more permissive regex targets the filename itself. Worth doing when an operator asks for filename-chunk metadata at registry-row level rather than via the project-level metadata tool.

## Cross-reference: Cell Observer

The LSM 900 and Cell Observer share:
- Same K: share + same `Ainhize/` parent folder.
- Same operator (Ainhize Urkola Arsuaga; Marta also operates Cell Observer).
- Same `.czi` format → same extractor (`tools/ingest/czi_metadata.py`).
- Same researcher-as-data-owner registry convention (`operator: discovered.researcher`).
- Same project_hint stopgap (researcher-name only — see PROJ-05).

They differ in:
- LSM 900 has **simpler path depth**: one batch folder per researcher's experiment (vs Cell Observer's three-level `<researcher>/<cell_line>/<experiment>/` hierarchy).
- LSM 900 batch folder encodes researcher + experiment + cell_line in one underscore-delimited string (vs Cell Observer's per-level folders).
- LSM 900 batches commonly include Z-stacks (`czi_size_z > 1`); Cell Observer cells-mode is typically single-plane.
- `czi_acquisition_mode` distinguishes them: `LaserScanningConfocalMicroscopy` (LSM 900) vs `WideField` (Cell Observer). Both report `czi_microscope_name = "Axio Observer.Z1 / 7"` because the LSM 900 sits on an Axio Observer stage — so the name alone isn't a reliable fingerprint.

## Reference materials

- [`confocal_microscopelsm900description.pdf`](confocal_microscopelsm900description.pdf) — vendor / platform description
- [`tools/templates/instruments/lsm900.yaml`](../../tools/templates/instruments/lsm900.yaml) — per-instrument template (the operator's daily reference card)
- [`tools/configs/lsm900_laura_uptake_TEST.yaml`](../../tools/configs/lsm900_laura_uptake_TEST.yaml) — round-7 first batch config (LAURA_UPTAKE_LP-IONP-doxo_MDA)
- [`../cell-observer/cell_observer_data_handling_workflow_notes.md`](../cell-observer/cell_observer_data_handling_workflow_notes.md) — sister-instrument workflow (same operator, same data drive, same .czi format)
- [`../../mfb-rdm-docs/09_MODALITIES.md`](../../mfb-rdm-docs/09_MODALITIES.md) §1.3 — LSM 900 spec entry
- [`../../mfb-rdm-docs/13_GJESUS3_ROLE.md`](../../mfb-rdm-docs/13_GJESUS3_ROLE.md) — the reframe (motivates why we surface .czi-embedded metadata as the canonical source)
