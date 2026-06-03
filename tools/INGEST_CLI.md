# `ingest_raw.py` — CLI Reference

One-page reference for the raw-data ingest tool. For the operational ("when do I run this, what do I do next") view, see [`mfb-rdm-docs/11_OPERATIONS.md §3.2`](../mfb-rdm-docs/11_OPERATIONS.md). For the full config-schema specification, see [`mfb-rdm-docs/10_TOOLS.md §2.1`](../mfb-rdm-docs/10_TOOLS.md).

---

## Set the NAS root first (one-time per shell)

The script needs to know where the NAS is mounted. **PowerShell on Windows** — set it once per session (or add the line to your `$PROFILE` to make it permanent):

```powershell
$env:GJESUS3_ROOT = "J:\"   # adjust to your NAS drive letter
```

**WSL / Linux** — the default `/mnt/gjesus3` usually already works; set explicitly if your mount is elsewhere.

Alternatively, pass `--nas-root <path>` on every command (e.g. `--nas-root "J:\"`). The script now fails fast with a clear message if the configured NAS root doesn't exist or doesn't contain a `registries/` subfolder — it will no longer silently write into a phantom path.

## Quick commands

```bash
# Batch ingest, dry-run first (always do this).
python tools/ingest_raw.py -c tools/configs/<your_config>.yaml --dry-run

# Same config, for real.
python tools/ingest_raw.py -c tools/configs/<your_config>.yaml

# Interactive single-case ingest (no YAML — answer prompts).
python tools/ingest_raw.py -i
```

The script is idempotent: re-running the same config skips acquisitions already in the registry (matched by `acquisition_date` + `original_name`). Safe to re-run after a partial failure.

---

## CLI flags

| Flag | Short | Default | Purpose |
|------|-------|---------|---------|
| `--config <path>` | `-c` | — | YAML config file (batch or single-case). Required unless `-i`. |
| `--interactive` | `-i` | off | Single-case mode; tool prompts for each field. |
| `--dry-run` | `-n` | off | Log what would happen; touch nothing on NAS. **Use first.** |
| `--nas-root <path>` | — | `$GJESUS3_ROOT` or `/mnt/gjesus3` | NAS mount point on this host. |
| `--nas-unc <unc>` | — | `$GJESUS3_UNC` or `\\GJESUS3\gjesus3` | Legacy `.lnk` porting-seam only — **not used by the current hard-link linker** (hard links use local NAS-volume paths). Retained for backward compatibility; safe to omit. |
| `--project <PROJ-NNNN>` | — | — | Project ID stamped on every row this run; recorded as `project_hint`. Overrides any value the YAML sets. |
| `--delete-source` | — | off | Remove the source file/folder after copy + verify succeed. Parent day folder is never touched. Default OFF for safety; opt in per batch. |

---

## Config schema cheat-sheet

Every config has up to four top-level blocks (three required + one optional, plus a top-level `link_filename:` string). Full spec in [`10_TOOLS.md §2.1`](../mfb-rdm-docs/10_TOOLS.md). Start from the **per-instrument template** at [`tools/templates/instruments/<instrument>.yaml`](templates/instruments/). For instruments without a per-instrument template, fall back to the universal [`tools/templates/ingest_template.yaml`](templates/ingest_template.yaml) and ask the Data Mgmt Lead before running.

| Block | Required? | Purpose |
|-------|-----------|---------|
| `ingest:` | Yes | Pipeline control flags. Not registry columns. Keys: `delete_source_after_ingest`, `auto_create_projects`, `acquisition_layout` (`file` \| `archive` \| `folder`; round-6 added — `archive` implemented 2026-06-02 to store the source `.zip`/`.rar` as the primary), `archive_primary_from` (directory of source archives; required with `acquisition_layout: archive`; 2026-06-02), `reconstructions` (`all` \| int \| list; MRI-specific), `copy_strategy` (`mri_paravision_v2` \| `ni_molecubes` \| legacy `paravision_exam`; round-6 v2 added), `auto_regenerate_dicom` (`true` \| `false`, MRI-specific Phase 2 2026-06-01 — see [Dicomifier opt-in](#dicomifier-opt-in-for-no-dicom-mri-exams) below). |
| `auto_discover:` | Yes | How to find cases inside `staging_dir` and what variables to extract. Supports `filename_parse:` (positional `separator:` + `fields:` OR named-group `regex:`; optional `source: name \| parent_name`) and `path_parse:` (named path levels between staging_dir and the match). Each case's parsed values land in `discovered.<name>`. |
| `registry:` | Yes | Explicit per-column mapping. Values: literal (`MFB`), bare reference (`discovered.operator`), interpolation (`"${discovered.stain} at ${discovered.czi_objective_mag}x"`), or `NA`. New DRAFT columns since round 6: `session_id` (ISA "study" grouping) and `primary_kind` (auto, set by pipeline). |
| `auto_create_project:` | Optional | First-time project-creation metadata (owner / description / notes), resolver-evaluated. First-write-wins. |
| `link_filename:` (top-level string, NEW 2026-05-22) | Optional | Template for the project link name placed under `/projects/<proj>/raw_linked/` (a hard link since 2026-06-02 — used verbatim, no extension). Context = `discovered.*` + resolved registry fields + `${acq_id}` + `${acq_date}`. Per-instrument templates ship recommended defaults. Falls back to `original_name` when unset (backward-compatible with rounds 1-2/4/5). See [10_TOOLS §2.1.5](../mfb-rdm-docs/10_TOOLS.md). |

### Filename chunks are free-form labels

In `auto_discover.filename_parse.fields` you list the names you want the chunks to carry. They become `discovered.<chunk_name>`. There is **no auto-promotion** to any registry column — the mapping is always explicit in the `registry:` block. A chunk name can coincide with a registry column name (e.g. both `sample_id`) without conflict; the resolver only reads from the `discovered` namespace. Pick names that read clearly in the `${discovered.x}` references you'll use downstream.

Example: filename `MFB_MBC_0525_ID26H_WGA_10x.czi` with

```yaml
filename_parse:
  separator: "_"
  fields: [group_code, operator, project, sample_short, stain, magnification]
registry:
  sample_id:    "${discovered.project}_${discovered.sample_short}"   # -> "0525_ID26H"
  project_hint: "AE-biomeGUNE-${discovered.project}"                  # -> "AE-biomeGUNE-0525"
  operator:     discovered.operator                                   # -> "MBC"
```

### Auto-populated columns (do NOT list in `registry:`)

The pipeline fills these itself: `acq_id`, `registration_datetime`, `primary_kind`, `primary_file_name`, `original_name`, `file_format`, `file_size_mb`, `file_count`, `canonical_path`, `checksum_present`, `extended_metadata_present`, `ingest_config`.

### `link_filename:` — control the project link name (NEW 2026-05-22)

By default, the project link placed under `/projects/<proj>/raw_linked/` is named after `original_name` (e.g. the `.czi` filename or the collaborator zip name). For systematic-naming environments (internal MRI, future internal NI) where the *source* identifier is a folder path + numeric position, the default would collide when multiple sessions land in the same project (e.g. four animals with the same exam number). Set `link_filename:` at the top level of the YAML to override. (The link is a hard link since 2026-06-02 — the resolved value is the link name verbatim, with no extension; see [10_TOOLS §2.1.1](../mfb-rdm-docs/10_TOOLS.md).)

```yaml
# Internal MRI default — unique per (animal, exam, reconstruction):
link_filename: "MRI_${sample_id}_${acq_date}_${discovered.mri_exam_number}_${discovered.mri_recon_indices}"
# Resolved example: MRI_jrc_251016_m17_0424_20251016_29_3
```

The resolver context includes every `discovered.*` field (see the per-instrument template header for the full reference card per instrument), every resolved registry field (`${sample_id}`, `${instrument}`, etc.), and the computed `${acq_id}` + `${acq_date}` (YYYYMMDD). Unresolved `${X}` references log a WARN and leave the literal in place — better than silently producing a broken name.

### Preclinical metadata surface — `subject:` / `condition:` / `anatomy:` (Phase 3)

For in-vivo acquisitions (`sample_type` = `organism` or `tissue`) the config gains four optional knobs that write the preclinical-metadata blocks into `metadata.json`. All of it is **non-blocking**: an unknown value gets a sentinel (`null` / `""`) plus a WARN, never a refused ingest. The worked example is [`tools/templates/instruments/mri_bruker.yaml`](templates/instruments/mri_bruker.yaml); the full field contract lives in [`08_METADATA §4.4–4.7`](../mfb-rdm-docs/08_METADATA.md).

**1. Auto-fill `subject:` from the animal-facility DB** — under `auto_discover:`:

```yaml
auto_discover:
  # ... existing staging_dir / filename_parse ...
  subject_from_db: true              # look each animal up in the animal-facility DB
  subject_lookup:                    # how to build the DB key from discovered.* fields
    project_alias: "${discovered.project_code}"   # the NNNN protocol code, e.g. "0424"
    animal_code:   "${discovered.animal_num}"     # the bare animal number, e.g. "17"
```

- `subject_from_db` (bool, default off): when true, the ingest queries the animal-facility DB and writes the `subject:` block (species / strain / sex / DOB→age / procedures) automatically.
- `subject_lookup.project_alias` + `subject_lookup.animal_code`: the two resolver-evaluated keys that form the lookup. Needs DB credentials at `~/.my.cnf` on the ingest machine and on-network access.
- On a miss / no-creds it stays non-blocking: the acq ingests with a `source: "pending-db"` placeholder `subject:` block and is queued to `registries/pending_subject_metadata.csv` for later recovery (08_METADATA §4.4.6). Uses `tools/animal_db.py` under the hood.

**2. Top-level `condition:` / `anatomy:` / `subject:` blocks** — set once per batch, inherited by every acquisition the batch produces:

```yaml
condition:                 # disease/control state (08_METADATA §4.5)
  is_control:    null      # true=control, false=case, null=unknown (WARN, still ingests)
  disease_model: ""        # e.g. "MI_LAD_ligation"; "" -> WARN
  disease_state: ""        # e.g. "day_7_post_MI"
  source:        "operator-entered"

anatomy:                   # whole-body vs region of interest (08_METADATA §4.6)
  is_whole_body: null      # true=whole-body, false=ROI, null=unknown (WARN, still ingests)
  # region: { label, ontology, id }   # UBERON-coded region when is_whole_body=false
  source:        "operator-entered"

# subject: only when OVERRIDING the DB lookup, or when the animal isn't in the DB
# (08_METADATA §4.4). Otherwise leave it out and let subject_from_db fill it.
```

For a mixed-condition session, override a single acquisition at `/projects/<proj>/metadata/<acq_id>.json` rather than splitting the batch. These blocks are additive to the existing `ingest:` / `auto_discover:` / `registry:` blocks and load through the same YAML loader.

### Sister utilities (standalone tools)

| Tool | Purpose |
|------|---------|
| [`tools/ftp_mirror.py`](ftp_mirror.py) | SFTP mirror — pulls a remote directory tree from a platform server into a local staging dir. Used for MRI (round 6) and the future NI round. Decoupled from `ingest_raw.py`: fetch first, then run ingest against the local copy. |
| [`tools/migrate_registry_columns.py`](migrate_registry_columns.py) | One-shot schema migration for `registry_raw.csv` when `REGISTRY_FIELDS` gains new columns. The defensive header check in `registry.append_row` blocks ingests until this runs. Backs up the original to `.bak.<timestamp>` before overwriting. |
| [`tools/ingest/probe_czi.py`](ingest/probe_czi.py), [`tools/ingest/probe_paravision.py`](ingest/probe_paravision.py) | Read-only embedded-metadata probes for `.czi` and Bruker ParaVision exam folders. Dump parsed metadata + the curated `discovered.<eco>_*` subset to `_probes/` for review before a real ingest. |

---

## Templates and configs — the layout

```
tools/templates/
├── ingest_template.yaml          # universal generic starter
└── instruments/
    └── axioscan7.yaml            # per-instrument template (locked-in conventions)
                                   # — more added as instruments come online —

tools/configs/
└── <instrument>_<batch>.yaml     # the live, version-controlled, per-batch
                                   # configs produced by editing a template
```

| Where | What lives there | When to touch |
|-------|------------------|---------------|
| `tools/templates/instruments/` | Per-instrument starters with all the instrument-specific patterns (filename parse, registry mapping, project_hint convention) locked in. Edit only when the convention itself changes. | Add a new file when bringing a new instrument online. |
| `tools/templates/ingest_template.yaml` | Universal generic starter — fallback for instruments without their own template yet. | Edit only when the YAML schema itself changes. |
| `tools/configs/` | Live, version-controlled per-batch configs (one per ingest run). Their relative path is stamped into every registry row's `ingest_config` column for auditability. | Add a new file every batch — copy the matching template, edit `staging_dir` + `notes`, run. |

**Per-instrument templates currently available:**

| Instrument | Template | Notes |
|------------|----------|-------|
| Zeiss AxioScan 7 (`ZWSI`, `.czi`) | [`tools/templates/instruments/axioscan7.yaml`](templates/instruments/axioscan7.yaml) | MFB filename convention; auto-create projects from filename's `<project>` chunk; default `link_filename: ${instrument}_${original_name}` |
| Zeiss Cell Observer cells-mode (`CELL`, `.czi`) | [`tools/templates/instruments/cell_observer_cells.yaml`](templates/instruments/cell_observer_cells.yaml) | Path-and-filename parse for live-cell / cell-assay workflows (Ainhize-acquired); default `link_filename: ${instrument}_${original_name}` |
| Internal MRI / Bruker ParaVision (`MRI`, folder bundle) | [`tools/templates/instruments/mri_bruker.yaml`](templates/instruments/mri_bruker.yaml) | Folder-as-primary layout, `regex:` extract on the messy FTP folder name, `reconstructions:` flag, default `link_filename: MRI_${sample_id}_${acq_date}_${discovered.mri_exam_number}_${discovered.mri_recon_indices}` |

Each template's **header comment block lists every `discovered.*` field** the operator can reference in resolver-evaluated YAML fields — the per-instrument reference card.

---

## Dicomifier opt-in for no-DICOM MRI exams

**When:** internal MRI ingests where some source exams have **no `pdata/<idx>/dicom/` subfolders** because the researcher didn't run Bruker's GUI DICOM exporter. Round-6 v2 (2026-05-27) had 3 of 7 source projects in this state (m13/m14/m29 protocol 0423) — they currently sit on `/raw/` as empty `<ACQ-ID>.data/` placeholders + populated JCAMP-DX sidecars. With this opt-in, ingest auto-regenerates the missing DICOMs via Dicomifier 2.5.3 (and applies two confirmed PV-7 workarounds — see [`tasks/tasks.md §3.1`](../tasks/tasks.md)).

**Pre-flight (one-time setup on the workstation):**

```bash
# WSL Ubuntu (or any shell where conda + miniforge are on PATH)
conda install -c conda-forge dicomifier pydicom
conda activate dicomifier-pilot
dicomifier --version    # should print 2.5.3 or later
```

**Enable in the YAML config:**

```yaml
ingest:
  # ... existing flags ...
  copy_strategy: mri_paravision_v2   # required (legacy paravision_exam doesn't support regen)
  auto_regenerate_dicom: true
```

**Per-batch runtime:** activate the env BEFORE running `ingest_raw.py` (the script invokes `dicomifier` via subprocess, so it needs to be on PATH at exec time):

```bash
conda activate dicomifier-pilot
python tools/ingest_raw.py --config tools/configs/<batch>.yaml --nas-root /mnt/gjesus3 --dry-run
# review, then real run
python tools/ingest_raw.py --config tools/configs/<batch>.yaml --nas-root /mnt/gjesus3
```

**Fall-through behaviour:**

- If `dicomifier` is **not on PATH** → ingest logs a clear ERROR and falls through to the existing empty-`.data/` placeholder behaviour. **Does NOT abort the batch.** Other exams in the same batch continue normally.
- If Dicomifier **fails on a specific exam** (malformed source, unsupported sequence) → same fall-through: WARN + empty placeholder.
- If the source **already has DICOMs** → flag is a no-op; normal slim copy proceeds as if the flag weren't set.

**Verification after a re-ingest:**

```bash
python tools/validate_dicomifier_pixelspacing.py
```

Walks the m13 + m17 staged source against the newly-populated `/raw/` and confirms the PixelSpacing-swap workaround is producing Bruker-equivalent output. Run after any Dicomifier-backed ingest or after a Dicomifier upgrade.

---

## If something goes wrong

1. **Run with `--dry-run` first.** It catches most config errors before any NAS write.
2. **Read the log.** Every line is prefixed with a step number (1–12). The failure point tells you where to look.
3. **The script is idempotent.** Re-running with the same config will not duplicate rows; previously-ingested acquisitions are skipped with a log line explaining why.
4. **Don't hand-edit registries.** If a row is wrong, contact the Data Mgmt Lead — corrections need to land cleanly so the audit chain stays intact.
5. **The source is preserved by default.** `--delete-source` is opt-in. If you didn't pass it, your source files are still on the instrument share.
