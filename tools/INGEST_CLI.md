# `ingest_raw.py` — CLI Reference

One-page reference for the raw-data ingest tool. For the operational ("when do I run this, what do I do next") view, see [`mfb-rdm-docs/11_OPERATIONS.md §3.2`](../mfb-rdm-docs/11_OPERATIONS.md). For the full config-schema specification, see [`mfb-rdm-docs/10_TOOLS.md §2.1`](../mfb-rdm-docs/10_TOOLS.md).

---

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
| `--nas-unc <unc>` | — | `$GJESUS3_UNC` or `\\GJESUS3\gjesus3` | UNC path used as the target for project `.lnk` shortcuts. Pass `""` to disable `.lnk` creation. |
| `--project <PROJ-NNNN>` | — | — | Project ID stamped on every row this run; recorded as `project_hint`. Overrides any value the YAML sets. |
| `--delete-source` | — | off | Remove the source file/folder after copy + verify succeed. Parent day folder is never touched. Default OFF for safety; opt in per batch. |

---

## Config schema cheat-sheet

Every config has three top-level blocks. Full spec in [`10_TOOLS.md §2.1`](../mfb-rdm-docs/10_TOOLS.md); starter template at [`tools/templates/ingest_template.yaml`](templates/ingest_template.yaml).

| Block | Purpose |
|-------|---------|
| `ingest:` | Pipeline control flags. Not registry columns. Example keys: `delete_source_after_ingest`, `auto_create_projects`. |
| `auto_discover:` | How to find cases inside `staging_dir` and what variables to extract. Each case's parsed values land in `discovered.<name>`. |
| `registry:` | Explicit per-column mapping. Values are: literal (`MFB`), bare reference (`discovered.operator`), interpolation (`"${discovered.stain} at ${discovered.czi_objective_mag}x"`), or `NA`. |

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

The pipeline fills these itself: `acq_id`, `registration_datetime`, `primary_file_name`, `original_name`, `file_format`, `file_size_mb`, `file_count`, `canonical_path`, `checksum_present`, `extended_metadata_present`, `ingest_config`.

---

## Per-instrument configs

Live, version-controlled configs ship in `tools/configs/`. Copy the nearest match for your instrument, edit `staging_dir` and any per-batch overrides, save under a new filename, and run. The path of the config you used is recorded in the `ingest_config` column of every row it produced.

| Instrument | Example config |
|------------|----------------|
| AxioScan 7 (`ZWSI`, `.czi`) | `tools/configs/axioscan7_20260506.yaml` |
| HPIC XMRI (collaborator DICOM) | `tools/configs/hpic_*.yaml` |

---

## If something goes wrong

1. **Run with `--dry-run` first.** It catches most config errors before any NAS write.
2. **Read the log.** Every line is prefixed with a step number (1–12). The failure point tells you where to look.
3. **The script is idempotent.** Re-running with the same config will not duplicate rows; previously-ingested acquisitions are skipped with a log line explaining why.
4. **Don't hand-edit registries.** If a row is wrong, contact the Data Mgmt Lead — corrections need to land cleanly so the audit chain stays intact.
5. **The source is preserved by default.** `--delete-source` is opt-in. If you didn't pass it, your source files are still on the instrument share.
