# 10 — Tools and Automation

**Parent:** [Documentation Index](00_INDEX.md)  
**Status:** 🔶 Draft
**Last Updated:** 2026-06-03 (Phase 3 preclinical-metadata enrichment writer IMPLEMENTED: new `auto_discover.subject_from_db` + `auto_discover.subject_lookup` keys and new top-level `condition:` / `anatomy:` / `subject:` blocks (§2.1.6); five new standalone tools — `gather_metadata`, `validate_registries`, `verify_checksums`, `metadata_completeness`, `recover_subject_metadata` (§3))

---

## Purpose

This document specifies the scripts and tools needed to support the data management workflows, reducing manual effort and enforcing consistency.

---

## 1. Tool Priorities

| Priority | Tool | Purpose | Status |
|----------|------|---------|--------|
| **P1** | `ingest_raw` | Batch deposit from staging to raw | ✅ Implemented (`tools/ingest_raw.py`) |
| **P1** | `create_publication` | Create publication folder with templates | 📋 Requirements defined |
| **P2** | `log_activity` | Helper for provenance logging | 📋 Requirements defined |
| **P1** | `create_project` | Create project folder with templates | ✅ Implemented (`tools/create_project.py`) |
| **P1** | Metadata extraction | Auto-extract embedded metadata (integrated into full-mode ingest) | 🔶 Design decided; implementation pending |
| **P1** | Preclinical-metadata enrichment | Write `subject:` / `condition:` / `anatomy:` blocks at ingest (Phase 3, non-blocking) | ✅ Implemented (`tools/ingest/enrichment.py`; §2.1.6) |
| **P3** | Validation scripts | Verify registry integrity + fixity + enrichment gaps | ✅ Implemented (`validate_registries`, `verify_checksums`, `metadata_completeness`; §3) |
| **P3** | `recover_subject_metadata` | Superuser deferred-recovery of `pending-db` subject metadata | ✅ Implemented (`tools/recover_subject_metadata.py`; §3.7) |
| **P3** | `gather_metadata` | Merged raw + study metadata view | ✅ Implemented (`tools/gather_metadata.py`; §3.5) |

---

## 2. Core Scripts

### 2.1 `ingest_raw` — Raw Data Ingest

**Purpose:** Copy data from staging (or local source) to the structured raw area with proper naming, checksums, verification, and registry update.

**Location:** `tools/ingest_raw.py` (with supporting modules in `tools/ingest/`)

**Architecture:**
```
tools/
├── ingest_raw.py            # CLI entry point
├── ingest/
│   ├── __init__.py
│   ├── config.py            # YAML loading + validation; expand_batch (file/dir glob, filename_parse, filter, idempotency); FORMAT_SUMMARIZERS dispatch
│   ├── resolver.py          # Resolves the YAML registry: block — literal | discovered.<x> | ${...} interp | NA; also validate/resolve condition: / anatomy: / subject: + subject_lookup + to_tristate/to_number coercers (§2.1.6)
│   ├── enrichment.py        # Phase 3 orchestrator: builds subject/condition/anatomy blocks (non-blocking) for sample_type ∈ {organism,tissue} at Step 8.4 (§2.1.6)
│   ├── subject_id.py        # Short-code subject parser (m13→13, ID13B→13+organ) + project_alias_from_hint
│   ├── pending.py           # Deferred-recovery pending list (registries/pending_subject_metadata.csv) read/append/update (§2.1.6, 08_METADATA §4.4.6)
│   ├── acq_id.py            # ACQ-ID generation (date + inst + seq)
│   ├── checksum.py          # SHA-256 checksums → checksums.json
│   ├── registry.py          # Read/append registry_raw.csv (REGISTRY_FIELDS includes ingest_config)
│   ├── readme.py            # Generate README.txt from template
│   ├── dicom_utils.py       # DICOM header extraction (pydicom)
│   ├── microscopy_utils.py  # Single-file inventory (.czi, .tif) — sibling of dicom_utils
│   ├── filename_parser.py   # Positional filename → {field: value}
│   ├── metadata_sidecar.py  # metadata.json writer (cross-format; discovered + user_supplied)
│   ├── probe_czi.py         # Standalone read-only .czi metadata probe (utility)
│   └── linker.py            # Create project hard link (file / folder-of-links) + manifest CSV (see §2.1.1)
├── configs/                 # Committed ingest configs, one per batch / day folder
│   ├── axioscan7_20260422.yaml
│   └── axioscan7_20260506.yaml
├── templates/
│   ├── README_raw.txt       # README template (per-acquisition README content)
│   ├── ingest_template.yaml # Universal starter template for new batch configs
│   └── instruments/         # Per-instrument templates (conventions locked-in)
│       └── axioscan7.yaml   # Zeiss AxioScan 7 (.czi) — MFB filename convention
├── INGEST_CLI.md            # CLI reference (flags, schema cheat-sheet, templates layout)
└── requirements.txt         # pydicom, pyyaml, tqdm, czifile
```

### 2.1.1 Project Linking — Hard Links (current) over `.lnk` shortcuts

> **✅ DECIDED + IMPLEMENTED 2026-06-02 — NTFS/SMB hard links.** Project links are **hard links** to the raw primary, created by `linker.create_hardlink` via `os.link`. The project copy is a **real file identical to the raw primary** — same inode, **zero extra storage**, and it shares raw's single security descriptor, so a read-only raw file stays read-only through the project link even inside a read/write `projects` folder. This **supersedes** the original Windows `.lnk` shortcut mechanism (kept as `linker.create_lnk` for the porting seam; see "History" below). The driver is adoption: change-averse researchers trust a project copy that looks and behaves like a normal file far more than a shortcut.

When `ingest_raw.py` is run with `--project <PROJ-ID>` (or `project_hint` set in the YAML config), Step 12 of full-mode ingest creates the link at:

```
/projects/<project_folder>/raw_linked/<link_name>
```

…where `<link_name>` is the resolved `link_filename:` (§2.1.5), with **no extension** (the legacy `.lnk` suffix is gone). Links are idempotent — re-running skips any link that already exists.

#### File-primary vs folder-primary

NTFS/SMB allows hard-linking **files** but forbids hard-linking **directories**. Dispatch follows `primary_kind`:

| Primary shape | Examples | What `raw_linked/<link_name>` is |
|---|---|---|
| **File** | microscopy `.czi`, collaborator `.zip`/`.rar` | One hard link to the raw file — same inode, opens identically. |
| **Folder** (`<ACQ-ID>.data/`) | internal MRI + NI flat-DICOM bundles | A **real folder** filled with one hard link per file from the raw `.data/` tree (sub-dirs recreated, files hard-linked). A real flat folder of real DICOMs, zero extra storage, each file carrying raw's read-only lock. |

This unified model gives "real files" across every instrument and removes the directory-can't-be-hard-linked blocker. Validated on the live QNAP SMB share: identical Windows File IDs (same inode), zero data duplication (only directory-entry metadata), and identical ACLs (raw vs link).

#### Why hard links work here

| Property | Effect |
|---|---|
| **Same volume requirement** | `raw/` and `projects/` both live under the single `gjesus3-data` container on one NAS volume, so `os.link` (local paths) always succeeds — no cross-volume issue. |
| **Shared security descriptor** | A hard link and its raw file share ONE ACL. Linking into a read/write `projects` folder does **not** leak that folder's perms onto the file (tested with an `Everyone:(M)` marker — absent on the link). Set raw read-only → the project link is read-only too. This is the raw-immutability behaviour we want (see [11_OPERATIONS](11_OPERATIONS.md)). |
| **No server cooperation** | Pure filesystem operation over SMB; the NAS needs no symlink/SSH support. |

#### Tradeoffs we accepted

- **Same-volume only.** Hard links cannot cross volumes; this is fine inside the container but means the linker is not a general cross-filesystem reference. The CSV manifest at `registries/ingest_manifest.csv` remains the volume-independent, script-friendly record and is always written.
- **`st_nlink` reads 1 over SMB** — a cosmetic QNAP-SMB quirk; the link is a true shared-inode hard link (proven via `fsutil file queryfileid`). Don't rely on `st_nlink` to detect links over this share.
- **Deleting one name doesn't free space** until all hard links to the inode are gone — expected hard-link semantics; the raw copy and every project link must be removed before the bytes are reclaimed.

#### Migration of existing links

`tools/relink_projects.py` converts pre-existing `.lnk` shortcuts to hard links in place **without re-ingesting** — it maps each `.lnk` to its acquisition via the project `provenance.csv` + `registry_raw.csv`, creates the hard link (file or folder-of-links), verifies it, removes the `.lnk`, and logs a provenance row. Idempotent; supports `--dry-run`, `--keep-lnk`, and `--project`.

#### History / porting seam

The pilot originally used **Windows `.lnk` shell shortcuts** (`linker.create_lnk`, PowerShell `WScript.Shell`) — chosen because WSL→SMB symlinks didn't work cleanly and IT couldn't provide SSH for server-side POSIX symlinks. That mechanism is retained as the porting seam for future deployments that can't use hard links (e.g. links that must cross volumes, or a non-Windows browse experience):

| Target environment | Likely method | Implementation note |
|--------------------|---------------|---------------------|
| Same-volume container, Windows | **Hard links** (current) | `linker.create_hardlink` — `os.link` for files, folder-of-links for `.data`. |
| Links must cross volumes / shares | `.lnk` shortcut **or** POSIX symlink | Hard links can't cross volumes; fall back to `linker.create_lnk` (Windows) or `os.symlink` (POSIX, ext4/ZFS NAS). |
| Mixed user base, NAS supports SSH | Server-side POSIX symlinks via SSH | `ln -s` on the NAS; visible filesystem-canonically to every client. |
| Constrained / no link support | Manifest-only | The always-written CSV manifest is the portable, link-free reference. |

The choice should be made consciously at the start of any future deployment — it affects what users browse, link durability across renames/volumes, and which OSes can run the pipeline.

### 2.1.2 Microscopy metadata extraction — library choice and deferred work

> **✅ DECIDED (2026-05-06):** Embedded metadata is extracted from `.czi` files via the **`czifile`** Python package. The extractor (`tools/ingest/czi_metadata.py`) parses the embedded XML directly into a curated `discovered.czi_*` subset (referenceable from YAML `registry:` blocks) and a structured `microscopy:` sidecar block. Pylibczirw, AICSImageIO, and Bio-Formats were considered and **deferred**.

#### Why czifile (now)

| Reason | Detail |
|--------|--------|
| **No new dependency surface** | czifile is pure Python; already in `requirements.txt`. Bio-Formats requires a JVM; pylibCZIrw requires a native binary; AICSImageIO pulls a heavier transitive set. |
| **Metadata-only access is cheap** | We never read pixel data — JPEG-XR / proprietary compression of pixels is irrelevant to us. czifile happily exposes the metadata XML even for compression formats it can't decode. |
| **Direct XML is auditable** | Our extractor walks the XML tree and the field-source mapping is visible (see `09_MODALITIES.md §1.1` "Auto-discovered fields" table). No hidden normalization layer between the file and what we record. |
| **Cross-instrument reuse** | The same code path works for Cell Observer (`CELL`) and LSM 900 (`LSM9`) since they share `.czi`. |

#### What we get / what we lose

We get every field surfaced in `09_MODALITIES.md §1.1` plus the full structured `microscopy:` block in the sidecar. We do not get an OME-XML mapping, OMERO-ready exports, or pixel access. Those are the deferred items below.

#### Deferred (revisit when there's a concrete need)

| Tool | When it'd matter | What it adds |
|------|------------------|--------------|
| **Bio-Formats CLI (`showinf -nopix -omexml`)** | Ad-hoc metadata inspection; cross-format normalization. | OME-XML output for ~181 standardized CZI fields. Useful as an interactive checking tool on a dev workstation; not in the pipeline. |
| **pylibCZIrw** (ZEISS-native) | When we need pixel access alongside metadata, raw XML editing, or `read_custom_key_value()` exposed natively. | Convenience helpers (`read_general_document_info()`, `read_scaling_info()`, etc.); ZEISS-maintained. |
| **AICSImageIO** | If we move toward analysis-friendly Python access to image data with metadata attached. | Unified API across vendor formats; dims/shape/physical sizes; OME-converted metadata. |
| **OMERO export** | Once researchers want a browsable image server for the ingested data. | Server-side image database; uses Bio-Formats internally. The `microscopy:` sidecar should be most of what's needed to populate OMERO annotations later. |

The extractor is the natural seam to swap libraries: today it's `czi_metadata.extract(czi_path)` calling `czifile`; tomorrow that function can wrap pylibCZIrw or call out to Bio-Formats without touching the rest of the pipeline.

### 2.1.2b Bruker ParaVision metadata extraction (round 6, 2026-05-20)

> **🔶 IN PROGRESS:** Internal MRI ingest uses **JCAMP-DX text aux files** (`subject`, `acqp`, `method`, `visu_pars`, per-recon `visu_pars`/`reco`) as the canonical metadata source — *not* the embedded DICOM headers. ParaVision aux files carry pulse sequence parameters, gating values, reconstruction index, animal subject info that the DICOM headers strip. Pure-DICOM-header extraction (for collaborator XMRI) stays deferred as an independent stream.

| Module | Role |
|---|---|
| `tools/ingest/jcampdx.py` | Minimal pure-Python JCAMP-DX parser. `parse_file(path) -> dict`. Handles `##KEY=value` scalars, `##KEY=( N )` arrays spanning multiple lines, `<...>` strings, `$$` comments. Used by `paravision_metadata.py`; no third-party dependency. |
| `tools/ingest/paravision_metadata.py` | Mirrors `czi_metadata.py` shape. `load_paravision_exam(exam_path) -> dict`, `build_mri_section() -> dict` (4 curated buckets: `subject`, `acquisition`, `geometry`, `reconstruction` + `_raw_metadata`), `EXPOSED_FIELDS` (~15 curated `discovered.mri_*` fields), `extract(exam_path) -> (discovered_subset, mri_section)`. |
| `tools/ingest/probe_paravision.py` | Standalone read-only probe utility, mirrors `probe_czi.py`. Dumps parsed JCAMP-DX + the curated subset to `_probes/`. |

**Dispatcher.** `FORMAT_EMBEDDED_EXTRACTORS["DICOM"]` runs a content-based detector: if `acqp` + `method` files are present alongside the source, it dispatches to `paravision_metadata.extract`. If not (collaborator XMRI shape — a zip), it returns `({}, {})` (current behaviour preserved). This keeps the MRI → DICOM ecosystem mapping intact while supporting two very different internal data shapes under the same bucket.

#### Why JCAMP-DX text parsing (and not nmrglue / bruker2nifti)

| Reason | Detail |
|---|---|
| **Minimal dependency surface** | A small text parser (~80 LOC) is cheaper than pulling in `nmrglue` or `bruker2nifti`, which carry NMR/MR-image conversion logic we don't need at ingest. |
| **Auditable** | Walking JCAMP-DX is straightforward; the field-source mapping is visible in `paravision_metadata.EXPOSED_FIELDS` (and mirrored in `09_MODALITIES.md` MRI section). |
| **Library deps stay future** | If we later add raw → NIfTI conversion as a project-level tool (see §2.6 below), pulling in `dcm2niix` or `bruker2nifti` happens *there*, not in the ingest pipeline. |

### 2.1.3 Auto-discovery: `filename_parse`, `path_parse`, `regex_extract`

Two parallel mechanisms in the `auto_discover:` block extract metadata from where it already sits in the source layout. Both produce values in the per-case `discovered.<name>` namespace, available everywhere the resolver runs (`registry:`, `auto_create_project:`).

| Feature | What it parses | Where it lives in YAML |
|---------|---------------|------------------------|
| `filename_parse:` | The filename, split on a separator into named positional chunks | `auto_discover.filename_parse` |
| `path_parse:` | The path components **between `staging_dir` and the file**, top-down, one named level per component | `auto_discover.path_parse` |

Both are **fully free-form on the level/chunk names** — they are labels the operator picks to describe the layout, not a fixed vocabulary. The pipeline never inspects the names; only the `registry:` and `auto_create_project:` references (`discovered.<name>` and `${discovered.<name>}`) consume them. Pick names that read clearly for the instrument and convention you're documenting.

**`filename_parse`** — positional split:

```yaml
auto_discover:
  filename_parse:
    separator: "_"
    fields: [cell_line, experiment, magnification, condition, image_num]
```

For `HLF_alphasma_10x_CC-miR-29a_1.czi` this populates `discovered.cell_line = "HLF"`, `discovered.experiment = "alphasma"`, etc. Mismatched-chunk-count files are skipped with a WARN.

**`path_parse`** — top-down path levels between `staging_dir` and the file:

```yaml
auto_discover:
  staging_dir: "G:/Lab/CellObserver/MBC"
  pattern:     "**/*.czi"          # recursive glob — required when path_parse is in use
  path_parse:
    levels:
      - researcher
      - cell_line
      - experiment
```

For a file at `G:/Lab/CellObserver/MBC/Itziar/HLF/alphasma/HLF_alphasma_10x_CC-miR-29a_1.czi`, the three levels (`Itziar`, `HLF`, `alphasma`) become `discovered.researcher`, `discovered.cell_line`, `discovered.experiment`. Mismatched-depth files (too few or too many levels) are skipped with a WARN — same pattern as `filename_parse`.

Both can be used together; if a value is parsed from both sides (e.g. both filename and path carry `cell_line`), `path_parse` runs first and the filename value **overwrites** it — so `filename_parse` wins on collision. Same-value collisions are silent (redundant but harmless). **Different-value collisions emit a per-key WARN** that names the file, the key, both values, and reminds the operator the filename wins by design — a misfiled-file signal. The cleaner approach when you don't actually want the redundancy is to give parallel chunks distinct names (e.g. `path_cell_line` vs `filename_cell_line`) and let the `registry:` block decide which to record.

**`regex_extract`** — optional named-group extraction for messy names (new 2026-05-20):

When positional `separator + fields` splitting doesn't fit (e.g. FTP server names that mix timestamps + duplicated study IDs + serials), add a `regex:` block to `filename_parse` with a Python regex that uses named groups. Each named group becomes a `discovered.<name>`.

```yaml
auto_discover:
  filename_parse:
    regex: '(?P<jrc_id>jrc_?\d{6,8}_m\d+_\d{4})'
```

For a folder name like `20251016_083822_jrc_251016_m17_0424_jrc_251016_m17_0424_1_1`, the regex pulls `discovered.jrc_id = "jrc_251016_m17_0424"` and ignores the surrounding noise. Use cases: Bruker ParaVision FTP folder names (round 6); any future instrument that produces noisy filenames.

**`separator`/`fields` vs `regex` choice:**

- Use `separator` + `fields` when every chunk of the name is meaningful in a stable positional order — works for AxioScan and Cell Observer.
- Use `regex` when you want to extract a few named values from a name with extra positional noise — works for the MRI FTP folder convention.
- Mixing is allowed: a `regex:` block runs first; any `discovered.<name>` it sets overrides defaults. Then `separator` + `fields` runs on the same input (if both are present) and applies normal collision rules.
- WARN on regex non-match (no name groups extracted) — file is still ingested with whatever other discovery sources populate `discovered`.

### 2.1.4 `auto_create_project:` block

When `ingest.auto_create_projects: true` and a new project is about to be created during an ingest, the optional `auto_create_project:` block supplies the project's metadata. Values resolve through the same mechanism as `registry:` — literal text, `discovered.<field>`, `${...}` interpolation, or `NA`.

```yaml
auto_create_project:
  owner:       "${discovered.researcher}"
  description: "${discovered.experiment} (auto-created from ${discovered.researcher} folder)"
  notes:       ""
```

**Recognized fields:** `owner`, `description`, `notes`. Any field omitted is left empty in `_project.yaml` and `registry_projects.csv`; the project can be edited manually afterward.

**First-write-wins.** The block is read **only** when the project does not already exist. On subsequent ingests that resolve `project_hint` to the same existing project, the block is ignored and an INFO line is logged (`"Project proj-<name> already exists; auto_create_project block ignored."`). This is deliberate — auto-create sets initial defaults, and the source of truth after that is `_project.yaml` (manually editable). No silent updates from later ingests.

**Empty resolved values.** If `${discovered.<x>}` resolves to empty (the discovered field is missing on a given file), the resulting metadata field is empty and the ingest logs a WARN. Project creation proceeds; the field can be filled in by hand later via `_project.yaml`.

**Project naming caveat.** The `short_name` of the auto-created project comes from `registry.project_hint`, not from this block. Any expression in `project_hint` (literal, `discovered.X`, interpolation) is allowed. **Provisional name patterns** like `${researcher}-${experiment}` should be documented as such in the YAML comments — see the Cell Observer example below. [05_PROJECTS §9](05_PROJECTS.md) elaborates on the requirement that the group converge on a durable, meaning-bearing naming convention; auto-create is not a substitute for that conversation.

When `auto_create_projects: false` (the default) or when the project already exists, the `auto_create_project:` block is ignored entirely.

### 2.1.5 `link_filename:` field (round 6, 2026-05-22)

> **✅ DECIDED:** The project link name placed under `/projects/<proj>/raw_linked/` is operator-controlled via a top-level YAML field `link_filename:`. Each per-instrument template ships a meaningful default; per-batch configs may override. Resolver-evaluated at link-creation time. (Since 2026-06-02 the link is a **hard link** with no extension — §2.1.1; the resolved value is used verbatim as the link name, where the legacy `.lnk` form appended `.lnk`.)

Why this exists: round 6 (internal MRI) exposed a real failure mode of the previous default (link named after `original_name`). For one-file-per-acquisition formats (`.czi`, collaborator zips) the original filename is already long and unique enough to avoid collisions inside a project. For systematic-naming environments (internal MRI, future internal NI) the *source* identifier is a folder path + numeric position — and naming the link after the position alone collides when multiple sessions land in the same project (e.g. four animals under `proj-ae-biomegune-0424` all having an exam `27`). The first-ingest of round 6 silently lost 35 of 97 links to such collisions. `link_filename:` lets the per-instrument template specify a name pattern that's both human-meaningful AND globally unique.

**Syntax:** top-level field, sibling of `ingest:` / `auto_discover:` / `registry:` / `auto_create_project:`. Value is a string template with `${X}` references.

```yaml
# Per-instrument template default for internal MRI:
link_filename: "MRI_${sample_id}_${acq_date}_${discovered.mri_exam_number}_${discovered.mri_recon_indices}"

# Per-instrument template default for microscopy / external:
link_filename: "${instrument}_${original_name}"
```

**Context dict** — `${X}` references resolve against this merged context (built per acquisition at link-creation time, after registry resolution + ACQ-ID generation):

| `${X}` | Source | Example |
|---|---|---|
| `${discovered.<key>}` | The auto-discovered namespace — every entry from `auto_discover` (filename chunks, path levels, parent-folder date, embedded-extractor output like `discovered.czi_*` / `discovered.mri_*`). The full set per instrument is documented in each per-instrument template's header comments. | `${discovered.mri_exam_number}` → `"29"` |
| `${sample_id}`, `${session_id}`, `${instrument}`, `${instrument_model}`, `${operator}`, `${data_source}`, `${sample_type}`, `${acquisition_datetime}`, `${project_hint}`, `${original_name}`, `${data_ecosystem}`, `${notes}` | Resolved registry-block fields | `${sample_id}` → `"jrc_251016_m17_0424"` |
| `${acq_id}` | The generated ACQ-ID for this case | `"ACQ-20251016-MRI-029"` |
| `${acq_date}` | YYYYMMDD form of the acquisition date | `"20251016"` |

**Resolution rules:**

- Empty / missing `link_filename:` → fall back to `original_name` (current behaviour for rounds 1-2, 4, 5 — backward compatible).
- Unresolved `${X}` (key not in context dict) → log WARN, leave the literal `${X}` in the output. Safer than silently producing a half-formed name; the operator sees the broken-template indicator and fixes it.
- Resolved-to-empty substitutions go through quietly — operator's choice if they reference a key that may be empty (e.g. `${discovered.mri_recon_indices}` could be empty for an exam where no reconstructions were kept).
- Trailing `/` in the resolved value is stripped (operator may use it as a visual "this links to a folder" hint; the resolved name is used verbatim as the hard-link name by `linker.create_hardlink` — no extension is appended).
- `${original_name}` resolves to the **basename** of the registry's `original_name`. This matters when staging is nested (microscopy folders store `original_name` as a staging-relative path like `Itziar/HLF/Colageno/x.czi`); a link name can't contain path separators, so the directory part is dropped (→ `x.czi`). The registry keeps the full `original_name`; only the link-name context is reduced. (Fixes the silent microscopy link-creation failure where the slash-containing name couldn't be written.)
- No other Windows-unsafe-character sanitisation is applied — the documented `discovered.*` fields don't contain unsafe characters in practice. Add a sanitisation pass later if a real case requires it.

**Per-instrument defaults (recommended patterns):**

| Instrument | Default `link_filename:` | Example resolved |
|---|---|---|
| AxioScan 7 (ZWSI) | `${instrument}_${original_name}` | `ZWSI_MFB_MBC_0423_ID13B_WGA_10x.czi` |
| Cell Observer (CELL) | `${instrument}_${original_name}` | `CELL_HLF_alphasma_10x_CC-miR-29a_1.czi` |
| Internal MRI (Bruker) | `MRI_${sample_id}_${acq_date}_${discovered.mri_exam_number}_${discovered.mri_recon_indices}` | `MRI_jrc_251016_m17_0424_20251016_29_3` |
| Internal NI (future) | `${discovered.modality}_${sample_id}_${acq_date}_${discovered.recon_number}` | `PET_0424_m17_20250612_3` |

See each per-instrument template under `tools/templates/instruments/` for the in-context comment block listing every `discovered.*` field that instrument exposes.

### 2.1.6 Preclinical-metadata enrichment — `subject:` / `condition:` / `anatomy:` + `subject_from_db` (Phase 3, 2026-06-03)

> **✅ IMPLEMENTED (Phase 3 of `tasks/tasks.md §3.2`).** For acquisitions with `sample_type ∈ {organism, tissue}`, full-mode ingest writes a `subject:` + `condition:` block (and, for `organism` only, an `anatomy:` block) into `metadata.json`. The writer is **NON-BLOCKING** ([08_METADATA §4.7](08_METADATA.md), DECIDED): it never raises on missing data — unknowns are written as explicit sentinels (`is_control` / `is_whole_body` `null`, free-text `""`, `source` `"unknown"` / `"pending-db"`) and a WARN is logged. The orchestrator is `tools/ingest/enrichment.py`, invoked at **Step 8.4** of full-mode ingest. The field contract for each block lives in [08_METADATA §4.4 (`subject:`)](08_METADATA.md) / [§4.5 (`condition:`)](08_METADATA.md) / [§4.6 (`anatomy:`)](08_METADATA.md); this section documents only the YAML surface that drives them. The `subject:` source enum + the `condition:` / `anatomy:` field sets are **DRAFT**; the registry `subject_id` / `anatomical_entity` **columns remain DEFERRED** to the true-production restart — the blocks live in the sidecar only, not in `registry_raw.csv`.

#### `auto_discover.subject_from_db` + `auto_discover.subject_lookup`

Two keys inside the `auto_discover:` block drive the automatic `subject:` lookup against the animal-facility DB (`tools/animal_db.py`):

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `subject_from_db` | boolean | `false` | When `true`, the ingest looks each subject up in the animal-facility MariaDB and writes the resolved `subject:` block (species / strain / sex / DOB → derived `age_at_acquisition` / structured `procedures`). Needs DB credentials at `~/.my.cnf` on the ingest machine + on-network. |
| `subject_lookup` | mapping | (none) | How to build the DB key from `discovered.*` fields. Resolver-evaluated `${discovered.X}` references. Two recognized fields: `project_alias` (the `NNNN` protocol code) and `animal_code` (the bare animal number, e.g. `m13`→`13`). |

```yaml
auto_discover:
  subject_from_db: true
  subject_lookup:
    project_alias: "${discovered.project_code}"   # e.g. "0424"
    animal_code:   "${discovered.animal_num}"     # e.g. "17"
```

On a **DB miss / no-credentials** the acquisition still ingests: the `subject:` block is written with `source: "pending-db"` and a row is appended to `registries/pending_subject_metadata.csv` for later superuser recovery via `recover_subject_metadata.py` (§3.6; [08_METADATA §4.4.6](08_METADATA.md)). This is the non-blocking contract — an unreachable DB never aborts the batch.

#### Top-level `condition:` / `anatomy:` / `subject:` blocks

Three new top-level blocks, peers of `registry:` / `auto_create_project:`. They are **resolver-evaluated** (literal | `discovered.<field>` | `${...}` interpolation, same engine as `registry:`) and **set once per batch** — the resolved values apply to **every acquisition the batch produces**. For a mixed-condition session, override per-acquisition at `/projects/<proj>/metadata/<acq_id>.json`.

- `condition:` — fields: `is_control` (tri-state `true`/`false`/`null`), `disease_model`, `disease_state`, `control_type`, `treatment`, `timepoint_days`, `study_arm`, `source`.
- `anatomy:` (organism-only) — fields: `is_whole_body` (tri-state), `region` (`{label, ontology (UBERON), id}`), `additional_regions[]`, `source`, `auto_hint`.
- `subject:` (optional override) — supplied only to override the `subject_from_db` lookup or when the animal isn't in the DB. Recognized fields: `facility_animal_id`, `species`, `strain`, `sex`, `date_of_birth`, `age_at_acquisition`, `genotype`, `weight_at_acquisition_g`, `cohort_id`, `procedures`, `source` (`age_at_acquisition` is derived from `date_of_birth` when present).

```yaml
condition:
  is_control:    null            # tri-state: true=control, false=case, null=unknown (WARN)
  disease_model: ""              # e.g. "MI_LAD_ligation"; "" -> WARN
  disease_state: ""              # e.g. "day_7_post_MI"
  source:        "operator-entered"

anatomy:                         # organism only
  is_whole_body: null            # tri-state; null=unknown (WARN)
  # region:                      # required only when is_whole_body=false
  #   label:    "brain"
  #   ontology: "UBERON"
  #   id:       "UBERON:0000955"
  source:        "operator-entered"
```

**Validation vs data.** Structural config errors (unknown keys, wrong types) fail fast at config-load time via `resolver.validate_condition_block` / `validate_anatomy_block` / `validate_subject_block` / `validate_subject_lookup` / `validate_subject_from_db`. Missing or empty *data* never raises — `resolver.resolve_condition_block` / `resolve_anatomy_block` (with the `to_tristate` / `to_number` coercers) emit the sentinels above and the orchestrator WARNs. This is the [§4.7](08_METADATA.md) non-blocking model in code.

**Sidecar nesting.** `metadata_sidecar.build_sidecar` nests the resolved blocks in this key order: `acq_id`, `generated`, `generator`, `user_supplied`, `discovered`, `subject`, `condition`, `anatomy`, `<ecosystem_section>` (e.g. `mri:` / `microscopy:` / `ni:`).

**Worked example:** [`tools/templates/instruments/mri_bruker.yaml`](../tools/templates/instruments/mri_bruker.yaml) ships all three blocks live (with `subject_from_db: true` + `subject_lookup`); `molecubes_ni.yaml` likewise; `axioscan7.yaml` carries `subject` + `condition` only (ex-vivo — no `anatomy`); `cell_observer_cells.yaml` + `lsm900.yaml` carry none (cells); the universal `ingest_template.yaml` carries commented examples.

---

**Two Ingest Modes:**

> **✅ DECIDED:** Full mode (default) extracts metadata and compresses DICOM before archiving. Lightweight mode copies as-is for constrained environments.

**Full Mode (default) — per acquisition:**
1. Load + validate config (YAML or interactive)
2. Analyze source data (DICOM headers: modality, StudyDate, file count, size)
3. Extract embedded metadata → `metadata.json` sidecar (Step 8.4: for `sample_type ∈ {organism, tissue}`, the enrichment writer nests `subject:` + `condition:` (+ `anatomy:` for organism) blocks — non-blocking, see §2.1.6)
4. Compress DICOM (if applicable) → `.zip` or `.tar.gz` archive
5. Generate ACQ-ID (read registry for next sequence number)
6. Create folder: `raw/<ECOSYSTEM>/<YYYY>/<YYYY-MM>/<ACQ-ID>/`
7. Copy files to destination (archive + metadata.json + README.txt, with progress bar)
8. Generate `checksums.json` (SHA-256, all files in acquisition folder)
9. Verify copy — recompute checksums on destination, compare
10. Generate `README.txt`
11. Append row to `registry_raw.csv` (all fields populated, including `original_name`)
12. Append entry to `registries/ingest_manifest.csv` (always); if `--project` is set (or `project_hint` resolves), also create a hard link in `<project>/raw_linked/` to the raw primary — a single hard link for a file primary, or a real folder of per-file hard links for a `<ACQ-ID>.data` folder primary (see §2.1.1)
13. Report summary

> **Registry integrity (2026-06-11).** Step 5 (ACQ-ID allocation) and step 11 (registry append) are each serialized by an atomic lockfile mutex (`tools/ingest/locking.py`; `registries/.registry.lock` + the `.acq_id_seq.json` high-water reservation) so concurrent ingests can't mint a duplicate ACQ-ID or tear a CSV line — the lock is held briefly, **never across the copy**. The **registry append is the commit point**: any failure between the copy and the append rolls back the partially-written acquisition folder so a re-run starts clean, and `--delete-source` runs only *after* the append succeeds. Every CSV append (registry, manifest, provenance, pending) routes through the BOM-tolerant, trailing-newline-safe `tools/ingest/csv_safe.py`. See [06_REGISTRIES §2.7](06_REGISTRIES.md).

**Lightweight Mode (`--lightweight`) — per acquisition:**
1. Load + validate config (fewer required fields)
2. Generate ACQ-ID
3. Create folder: `raw/<ECOSYSTEM>/<YYYY>/<YYYY-MM>/<ACQ-ID>/`
4. Copy archive as-is to destination (user provides pre-compressed archive or files)
5. Generate `checksums.json`
6. Generate `README.txt`
7. Append row to `registry_raw.csv` (auto fields only; `extended_metadata_present` = `N`)
8. Report summary

**Configuration schema (since 2026-05-06):**

Three required top-level blocks plus one optional. `defaults:` is gone — non-registry control flags moved to `ingest:`, and the per-column registry mapping is explicit in `registry:`.

| Block                   | Required? | Purpose |
|-------------------------|-----------|---------|
| `ingest:`               | Yes       | Pipeline control flags (`delete_source_after_ingest`, `auto_create_projects`, ...). Not registry columns. |
| `auto_discover:`        | Yes       | How to discover cases and what variables to extract per case. Each case's discovered fields land in a `discovered` namespace, referenceable below. Supports `filename_parse:` and `path_parse:` (see §2.1.3). |
| `registry:`             | Yes       | Explicit per-column registry mapping. Three value forms: literal text/number, `discovered.<field>` (bare reference), or `"...${discovered.<field>}..."` (interpolation). Use `NA` to leave a column intentionally empty. |
| `auto_create_project:`  | Optional  | Project-creation metadata used only when `ingest.auto_create_projects: true` and a new project is being created. Resolver-evaluated like `registry:`. First-write-wins (see §2.1.4). |
| `condition:`            | Optional  | Preclinical disease-state / study-role block (Phase 3). Resolver-evaluated, set-once-per-batch, non-blocking. Written to `metadata.json` for `sample_type ∈ {organism, tissue}`. See §2.1.6 + [08_METADATA §4.5](08_METADATA.md). |
| `anatomy:`              | Optional  | Anatomical-coverage block (Phase 3, organism-only). Resolver-evaluated, set-once-per-batch, non-blocking. See §2.1.6 + [08_METADATA §4.6](08_METADATA.md). |
| `subject:`              | Optional  | Subject-metadata override (Phase 3) — supplied only to override the `auto_discover.subject_from_db` lookup or when the animal isn't in the DB. See §2.1.6 + [08_METADATA §4.4](08_METADATA.md). |

`ingest:` flags currently honored:

| Flag | Default | Effect |
|------|---------|--------|
| `delete_source_after_ingest` | `false` | Remove the source file/folder after a successful copy + verify. CLI `--delete-source` overrides. |
| `auto_create_projects` | `false` | When `registry.project_hint` resolves to a value that isn't an existing `project_id` or `short_name`, auto-create a project with that value as the `short_name`. First ingest creates; subsequent ingests with the same hint reuse via `short_name` lookup. Useful when the project key comes from a parsed filename chunk (e.g. `project_hint: discovered.project`). Default `false` to prevent typos from silently creating rogue projects. When enabled, the optional `auto_create_project:` block (§2.1.4) supplies the new project's `owner` / `description` / `notes`. |
| `acquisition_layout` | `file` | New 2026-05-20. One of `file` (single primary file: microscopy `.czi`), `archive` (archive-as-primary: collaborator/external DICOM — store the original source archive renamed to `<ACQ-ID><ext>`, one fast SMB transfer; **implemented 2026-06-01**, requires `archive_primary_from` below), or `folder` (folder-as-primary: internal MRI ParaVision bundle — no zip). Drives the file-copy step and the `primary_kind` registry column. Per-instrument templates set this; per-batch configs rarely override. See [03_RAW_STORAGE §4.2](03_RAW_STORAGE.md). |
| `archive_primary_from` | (none) | New 2026-06-01. Required with `acquisition_layout: archive`. Directory holding the original source archives; the ingest stores `<archive_primary_from>/<case>.<ext>` (matched by `discovered.folder_name`, any of `.zip/.rar/.7z/.tgz/.tar/.gz`) as the acquisition's primary. Metadata (date / modality / instance count) is still read from the extracted `staging_dir` case dir; only the compact archive is copied to the NAS. Avoids the small-file SMB latency of copying an extracted DICOM tree (~20k loose files/case). |
| `reconstructions` | (none) | New 2026-05-20 (MRI-specific). Selects which reconstruction indices to retain from a ParaVision exam. Values: `all` \| an integer (e.g. `3`) \| a list of integers (e.g. `[3]` or `[1, 3]`). The platform convention is `/3` user-trusted, but the user explicitly decides per-batch; there is no implicit default. Indices not listed stay only on the platform's deep-archive. The registry's `discovered.mri_recon_indices` column records what was kept. |
| `copy_strategy` | `paravision_exam` | New 2026-05-27 (round-6 v2). Per-instrument selector for the folder-as-primary copy function when `acquisition_layout: folder`. Values: `mri_paravision_v2` (slim DICOM-only layout for internal MRI; v2 fix to v1's piggyback bug), `ni_molecubes` (Molecubes NI archive-mode), `paravision_exam` (legacy v1 path; preserved for back-compat — should not be selected for new batches). See per-instrument templates under `tools/templates/instruments/`. |
| `auto_regenerate_dicom` | `false` | New 2026-06-01 (MRI-specific, Phase 2 of `tasks/tasks.md §3.1`). When `true` AND `copy_strategy: mri_paravision_v2` AND the source has no DICOMs in any selected `pdata/<idx>/` recon, invoke `tools/ingest/paravision_regen.py` to call Dicomifier 2.5.3 + apply the two confirmed PV-7 workarounds (PixelSpacing axis-swap; Window-tag fix) per generated DICOM. Output lands in `<ACQ-ID>.data/` with the standard `recon<idx>_frame<NN>.dcm` naming. **Requires `dicomifier` on PATH** at ingest time (`conda activate dicomifier-pilot` before running). If unavailable or regeneration fails, the ingest falls through to the existing empty-`.data/` placeholder behaviour with a clear WARN — does NOT abort the batch. Default `false` to keep the Dicomifier dependency optional. See [equipment/mri-platform/internal_mri_data_handling_workflow_notes.md](../equipment/mri-platform/internal_mri_data_handling_workflow_notes.md) "ParaVision → DICOM regeneration" section for operator setup. |

The user-controllable `registry:` columns are: `instrument`, `data_ecosystem`, `instrument_model`, `modalities_in_study`, `operator`, `data_source`, `sample_id`, `sample_type`, `session_id` (DRAFT — see [06_REGISTRIES §2.2 + §2.3a](06_REGISTRIES.md)), `acquisition_datetime`, `project_hint`, `notes`. Of these, **`instrument`, `data_ecosystem`, `operator`, `data_source` must be present** (NA allowed where intentional); the rest are optional. Auto-populated columns (`acq_id`, `registration_datetime`, `primary_kind` (DRAFT), `primary_file_name`, `file_format`, `file_size_mb`, `file_count`, `canonical_path`, `checksum_present`, `extended_metadata_present`, `original_name`, `ingest_config`) must NOT appear in `registry:`.

**`acquisition_datetime` resolution** (updated 2026-06-01). A literal (ISO `YYYY-MM-DD…` or `YYYYMMDD`) or `discovered.<field>` value sets both the ACQ-ID date prefix and the registry column. When `acquisition_datetime` resolves empty / `NA`, the ingest first falls back to the **DICOM `StudyDate`** the summarizer reads from the headers — collaborator / external DICOM carries the real acquisition date in the data, not the filename, so its configs can legitimately set `acquisition_datetime: NA` — and backfills the registry column from it. Only if no usable StudyDate is found does it default to today's date with a WARN. Caveat: a batch relying on this fallback is not strictly idempotent on re-run (the stored row keys off the discovered date while `expand_batch` keys off the empty config value); supply an explicit `acquisition_datetime` when strict idempotency matters. Microscopy and other ecosystems with no DICOM headers are unaffected (no StudyDate → today, as before).

**Templates layout** — start from the per-instrument template under [`tools/templates/instruments/`](../tools/templates/instruments/) (currently: `axioscan7.yaml`); the universal starter [`tools/templates/ingest_template.yaml`](../tools/templates/ingest_template.yaml) is the fallback for instruments not yet onboarded. Edited copies are saved under [`tools/configs/`](../tools/configs/) (under git, version-locked with the script — the relative path is stamped into each registry row's `ingest_config` column). See [`tools/INGEST_CLI.md`](../tools/INGEST_CLI.md) for the full templates/configs layout table.

**Batch configuration — file-mode with filename parsing (AxioScan and similar):**

```yaml
ingest:
  delete_source_after_ingest: false

auto_discover:
  staging_dir: "S:/goptical/GOpticalUsers data/AxioScan/20260422"
  pattern: "*.czi"
  filename_parse:
    separator: "_"
    fields: [group_code, operator, project, sample_id, stain, magnification]
  filter:
    group_code: MFB
  acquisition_date_from: parent_folder_name

registry:
  instrument:           ZWSI
  data_ecosystem:       MICROSCOPY
  instrument_model:     "Zeiss Axio Scan 7"
  modalities_in_study:  NA
  researcher:           "<set per batch / GUI>"   # registry person column (renamed from operator 2026-06-09)
  data_source:          internal
  sample_id:            discovered.sample_id
  sample_type:          NA
  acquisition_datetime: discovered.acquisition_date
  project_hint:         NA
  notes:                "Routine WSI; ${discovered.stain} @ ${discovered.magnification}"
```

**Batch configuration — directory-mode (DICOM):**

```yaml
ingest:
  delete_source_after_ingest: false

auto_discover:
  staging_dir: /data/local_staging/HPIC_33cases/
  pattern: "HPIC*/"           # trailing / matches directories
  # acquisition_date_from: parent_folder_name  # if applicable

registry:
  instrument:           XMRI
  data_ecosystem:       DICOM
  instrument_model:     NA
  modalities_in_study:  NA
  operator:             RT
  data_source:          "collaborator:HPIC"
  sample_id:            discovered.folder_name
  sample_type:          NA
  acquisition_datetime: NA             # external DICOM: NA -> derived from DICOM StudyDate (see resolution note above)
  project_hint:         NA
  notes:                "HPIC batch ingest"
```

**Batch configuration — file-mode with `path_parse` + `auto_create_project` (Cell Observer cells-mode):**

```yaml
ingest:
  delete_source_after_ingest: false
  auto_create_projects:       true   # see auto_create_project: block below

auto_discover:
  staging_dir: "G:/Lab/CellObserver/Ainhize"
  pattern:     "**/*.czi"           # recursive — required when path_parse is in use
  path_parse:
    levels:                          # FREE-FORM LABELS — names below are example only
      - researcher
      - cell_line
      - experiment
  filename_parse:
    separator: "_"
    fields:    [cell_line, experiment, magnification, condition, image_num]
  acquisition_date_from: parent_folder_name   # if applicable; otherwise rely on .czi internal

registry:
  instrument:           CELL
  data_ecosystem:       MICROSCOPY
  instrument_model:     "Zeiss Axio Observer (Cell Observer)"
  researcher:           discovered.researcher   # registry person column (RENAMED from operator 2026-06-09)
  data_source:          internal
  sample_id:            "${discovered.cell_line}_${discovered.condition}"
  sample_type:          cells
  acquisition_datetime: discovered.czi_acquisition_datetime
  project_hint:         "${discovered.researcher}-${discovered.experiment}"
  notes:                "${discovered.experiment} cells at ${discovered.magnification}, condition ${discovered.condition}, image ${discovered.image_num}"

# operator = the tech who ran the scope. A TOP-LEVEL key (NOT in the registry:
# block) that is written to BOTH the registry `operator` column AND the sidecar
# (06_REGISTRIES §2.3a-bis, decision #4.2 2026-06-09). Often != researcher.
operator: "${discovered.czi_user}"

# ⚠️ PROVISIONAL PROJECT NAMING — the ${researcher}-${experiment} pattern is a stopgap.
# Experiments are metadata, not projects. A real project name should map to a unit of
# funded/owned work (funded project name, animal-project approval ID, or an explicit
# internal name the group agrees on). See 05_PROJECTS §9 for the warning + open
# question; the group must converge on a real naming convention.
auto_create_project:
  owner:       "${discovered.researcher}"
  description: "Auto-created from ${discovered.researcher} Cell Observer folder; experiment chunk = ${discovered.experiment}"
  notes:       "Provisional auto-created project — edit owner/description as needed."
```

**Single-case configuration:**

```yaml
source_path: /data/local_staging/user_dump/
ingest:
  delete_source_after_ingest: false
registry:
  instrument:           ZWSI
  data_ecosystem:       MICROSCOPY
  operator:             MBC
  data_source:          internal
  sample_id:            MOUSE-2024-042
  sample_type:          "mouse lung section"
  acquisition_datetime: "2026-02-15"
  notes:                "First test of ingest workflow"
```

**Usage:**

> The script needs a valid NAS root. Set `GJESUS3_ROOT` once per shell (PowerShell: `$env:GJESUS3_ROOT = "J:\"`; bash/WSL: `export GJESUS3_ROOT=/mnt/gjesus3`) or pass `--nas-root <path>` on every command. The script fails fast if the configured path doesn't exist or doesn't contain a `registries/` subfolder. End-user-facing walkthrough: [`11_OPERATIONS.md §3.2`](11_OPERATIONS.md); flag reference: [`tools/INGEST_CLI.md`](../tools/INGEST_CLI.md).

```bash
python tools/ingest_raw.py --config batch_hpic.yaml --dry-run    # preview (full mode)
python tools/ingest_raw.py --config batch_hpic.yaml               # execute (full mode)
python tools/ingest_raw.py --interactive                           # single case (full mode)
python tools/ingest_raw.py --config quick.yaml --lightweight       # lightweight mode
python tools/ingest_raw.py --config batch.yaml --delete-source     # remove source after verify (default OFF)
python tools/ingest_raw.py --interactive --lightweight             # lightweight interactive
```

**Key features:**
- Three required top-level blocks plus one optional: `ingest:` (control), `auto_discover:` (extract `discovered.*` via `filename_parse` and/or `path_parse` — see §2.1.3), `registry:` (explicit per-column mapping with literal | `discovered.X` | `${...}` interp | NA), and optional `auto_create_project:` (owner/description/notes for first-time project auto-creation — see §2.1.4). Universal starter at `tools/templates/ingest_template.yaml`; per-instrument templates under `tools/templates/instruments/`.
- Auto-populated columns (`acq_id`, `registration_datetime`, `primary_file_name`, `file_format`, `file_size_mb`, `file_count`, `canonical_path`, `checksum_present`, `extended_metadata_present`, `original_name`, `ingest_config`) — script-controlled, not user-editable.
- **Enrichment-projection columns (added 2026-06-10): `sample_organism`, `subject_id`, `anatomical_entity`** — also auto-populated, but sourced from the non-blocking enrichment blocks rather than the analysis step: `registry.build_row` projects them from the Step 8.4 `subject:` / `anatomy:` blocks (`subject.species` → `sample_organism`, `subject.facility_animal_id` → `subject_id`, `anatomy.region.label` → `anatomical_entity`). Set the upstream values via `auto_discover.subject_from_db` / `subject_lookup:` (DB) and the `anatomy:` block — **never as `registry:` keys** (the resolver rejects them there). Blank for non-animal samples. See [06_REGISTRIES §2](06_REGISTRIES.md), [08_METADATA §4.4/§4.6](08_METADATA.md).
- `ingest_config` registry column records the relative path of the YAML config that produced the row, for auditability + reproducibility.
- Two ingest modes: full (default) and lightweight (`--lightweight`, planned)
- DICOM header auto-detection (modality, StudyDate via pydicom) — full mode
- DICOM archive creation (compress to .zip or .tar.gz) — full mode (planned)
- Microscopy single-file ingest (`.czi` etc.) with rename to canonical `{acq_id}{ext}`
- `metadata.json` sidecar (cross-format; `user_supplied` + `discovered`; ecosystem-specific section reserved for embedded-metadata extraction)
- Filename parser (positional) for instruments that encode metadata in filenames
- Collaborator instrument codes: X-prefix (e.g., `XMRI` for external MRI)
- Copy verification: SHA-256 source→dest comparison
- **Idempotent re-runs**: `expand_batch` checks the registry by `(acquisition_date, original_name)` and skips already-ingested files
- `--delete-source` flag removes the source file/folder after a successful verify (cross-instrument; default OFF; never touches the parent of `source_path`)
- Project link creation: hard link (file) or folder-of-hard-links (`<ACQ-ID>.data`) placed in `<project>/raw_linked/` when `--project` is set (same-volume; see §2.1.1)
- `--dry-run` mode for previewing without changes
- Batch auto-discovery for processing many cases at once (file or directory globs)

### 2.2 `create_publication` — Publication Package Setup

**Purpose:** Create a new publication folder with required structure and registry entry.

**Inputs:**
- Short name (folder name)
- Working title
- PI, first author
- Optional: description, linked raw data

**Actions:**
1. Validate short name is unique
2. Generate PUB-ID
3. Create folder structure:
   - `_publication.yaml` (from template)
   - `provenance.csv` (empty with headers)
   - `raw_linked/` folder
   - Optional: `figures/`, `analysis/`, `methods/`
4. Append entry to registry_publications.csv
5. Report success with folder path

**Usage:**
```bash
create_publication \
  --name "lung-fibrosis-markers-2026" \
  --title "Quantification of fibrotic markers in IPF lung tissue" \
  --pi "Jesús Ruiz-Cabello" \
  --first-author "Marta Beraza"
```

### 2.3 `log_activity` — Provenance Helper

**Purpose:** Simplify adding entries to the provenance log.

**Inputs:**
- Output file path
- Input references (ACQ-IDs, FILE-IDs, or paths)
- Process description
- Creator
- Optional: software version, parameter file, notebook reference

**Actions:**
1. Determine which provenance.csv to update (from output path)
2. Generate next FILE-ID
3. Validate input references exist
4. Append entry to provenance.csv
5. Confirm entry

**Usage:**
```bash
log_activity \
  --output figures/fig1_panel_a.tiff \
  --inputs "ACQ-20260115-ZWSI-001" \
  --process "ROI extraction and contrast adjustment" \
  --creator MBC \
  --software "ImageJ 1.54f"
```

---

## 3. Utility Scripts

### 3.1 `create_project` — Project Workspace Setup

**Purpose:** Create a new project folder with required structure and registry entry.

**Location:** `tools/create_project.py`

**Inputs:**
- Short name (folder name)
- Description
- Owner (initials)

**Actions:**
1. Validate short name is unique (scan `registry_projects.csv`)
2. Generate PROJ-ID (`PROJ-NNNN`, next available)
3. Create folder: `/projects/proj-<short_name>/`
4. Write `_project.yaml` from template
5. Create empty `provenance.csv` with headers
6. Create `raw_linked/` directory
7. Append entry to `registries/registry_projects.csv`
8. Print summary

**Usage:**
```bash
python tools/create_project.py \
  --name "ipf-biomarkers" \
  --description "IPF biomarker quantification study" \
  --owner MBC

python tools/create_project.py --interactive
python tools/create_project.py --name test --description "test" --owner RT --dry-run
```

### 3.2 `validate_registries`

**Purpose:** Read-only consistency checker for the registry area (REG-04). **Location:** `tools/validate_registries.py`. **Read-only** — never writes; the NAS can be mounted read-only.

**Checks (ERROR-level — exit nonzero):**
- `registry_raw.csv` header EXACTLY equals `ingest.registry.REGISTRY_FIELDS` (schema imported, never hardcoded — `06_REGISTRIES` is the contract).
- No duplicate `acq_id`; `acq_id` matches `ACQ-YYYYMMDD-<CODE>-NNN`.
- Required columns non-empty per row (`acq_id`, `registration_datetime`, `data_ecosystem`, `instrument`, `canonical_path`).
- `sample_type`, when set, is in the controlled vocab `{tissue, organism, cells, material, phantom}`.
- `canonical_path` starts with `/raw/` and the acquisition folder exists on disk.
- `project_hint`, when set and matching `PROJ-XXXX`, exists in `registries/registry_projects.csv`.

**Phase 3 enrichment checks (WARN-level — never affect exit code):** for `sample_type ∈ {organism, tissue}`, the sidecar must carry a `subject:` + `condition:` block (and `anatomy:` for organism); the explicit "unknown" sentinels (`subject.source == "pending-db"`, `condition.is_control == null`, `anatomy.is_whole_body == null`) are WARNs, legitimate under the non-blocking model ([08_METADATA §4.7](08_METADATA.md)). `--no-enrichment` skips these.

```bash
python tools/validate_registries.py --nas-root J:\gjesus3-data
python tools/validate_registries.py --no-enrichment   # skip Phase 3 WARNs
```

### 3.3 `verify_checksums`

**Purpose:** Read-only fixity / bit-rot re-check for the `/raw/` area. **Location:** `tools/verify_checksums.py`. **Read-only** — re-hashes data only, never writes. Re-verifies the SHA-256 digests recorded in each acquisition's `checksums.json` against the current on-disk bytes (ingest verified source-vs-dest at copy time; this answers the later "are the bytes still what we stored?"). Extra files not in `checksums.json` (e.g. a later-written sidecar) are reported as INFO, not a mismatch.

```bash
python tools/verify_checksums.py --acq ACQ-20251016-MRI-029 --nas-root J:\gjesus3-data   # single acquisition
python tools/verify_checksums.py --scope /raw/MICROSCOPY/2026/                            # specific path
```

### 3.4 Metadata Extraction and Backfill

> **✅ DECIDED:** Auto-extraction of embedded metadata is integrated into full-mode ingest — not a separate standalone tool. The DICOM archive format decision is resolved (compressed archives); extraction happens before compression during full-mode ingest.

**Metadata extraction (integrated into `ingest_raw` full mode):**
- Reads embedded metadata from raw files (DICOM headers via pydicom, .czi metadata, etc.)
- Writes `metadata.json` sidecar in the acquisition folder
- Sets `extended_metadata_present` = `Y` in registry

**`backfill_metadata` — upgrade lightweight ingests:**

**Purpose:** Retroactively extract metadata from acquisitions that were ingested in lightweight mode. Decompresses the archive to a temp directory, extracts metadata, writes `metadata.json`, updates registry.

**Usage:**
```bash
python tools/backfill_metadata.py --acq-id ACQ-20260301-XMRI-001   # single
python tools/backfill_metadata.py --scope /raw/DICOM/2026/          # batch
python tools/backfill_metadata.py --dry-run --scope /raw/DICOM/     # preview
```

**Supported formats:** DICOM (.dcm via pydicom), .czi (via aicspylibczi or czifile), others TBD

> **Note:** User-supplied metadata (sample context, experimental notes via CSVs/Excel) remains deferred.

### 3.5 `gather_metadata`

**Purpose:** Read-only merged "single source of truth" view. **Location:** `tools/gather_metadata.py`. **Read-only** — never writes. Joins the acquisition-level `/raw/<…>/<ACQ-ID>/metadata.json` sidecar with the study-level `/projects/<proj>/metadata/<acq_id>.json` supplement (plus project-wide `study.json` + `biosamples.json` when present) on `acq_id`, and emits ONE merged JSON document to stdout. The merge is additive and non-destructive: the raw sidecar is the base document (never overwritten); study-level data nests under a `study` key. See [08_METADATA §1.4](08_METADATA.md).

```bash
python tools/gather_metadata.py --acq ACQ-20251016-MRI-029 --nas-root J:\gjesus3-data
python tools/gather_metadata.py --project ae-biomegune-0424
```

### 3.6 `metadata_completeness`

**Purpose:** Read-only enrichment-gap report — the gap-focused companion to `validate_registries`. **Location:** `tools/metadata_completeness.py`. **Read-only**. Walks `/raw/` sidecars and surfaces the *non-blocking* enrichment gaps (the explicit "unknown" sentinels of [08_METADATA §4.7](08_METADATA.md)) so a superuser can bulk-fill them. Counts as a gap (organism/tissue only): `condition.is_control == null`, `anatomy.is_whole_body == null` (organism), `subject.source == "pending-db"`, or an expected block missing entirely. Also lists the `registries/pending_subject_metadata.csv` recovery backlog. Optional `--project` filter matches the registry `project_hint`.

```bash
python tools/metadata_completeness.py --nas-root J:\gjesus3-data
python tools/metadata_completeness.py --project ae-biomegune-0525
```

### 3.7 `recover_subject_metadata`

**Purpose:** Superuser deferred-recovery for `subject:` metadata that was queued `pending-db` at ingest time ([08_METADATA §4.4.6](08_METADATA.md)). **Location:** `tools/recover_subject_metadata.py`. Run from a superuser machine that holds `~/.my.cnf` (on-network). Read-only against the DB; **controlled-write** against `/raw` sidecars + the pending list — **DRY-RUN by default** (touches nothing; reports what would change). Writing requires explicit `--apply`. For each pending row it re-attempts the animal-DB lookup and, on a hit, fills ONLY blank / placeholder `subject:` required fields in place (recomputing `age_at_acquisition`), VERIFIES-after-write, then flips the pending row to `recovered`. Never overwrites a real value; idempotent; non-hits stay pending.

```bash
python tools/recover_subject_metadata.py --nas-root J:\gjesus3-data            # preview (dry-run, default)
python tools/recover_subject_metadata.py --nas-root J:\gjesus3-data --apply    # write sidecars + flip pending rows
```

---

## 4. Implementation Decisions

### 4.1 Language

> **🔶 RECOMMENDATION:** Python 3.10+

Rationale:
- Good library support for file handling, CSV, JSON
- Libraries for format-specific metadata extraction
- Familiar to scientific computing community

### 4.2 Where Scripts Run

> **⚠️ GAP:** Need to decide execution environment.

| Option | Pros | Cons |
|--------|------|------|
| **Designated workstation** | Controlled environment; consistent | Requires access to that machine |
| **User machines** | Convenient; work where you are | Dependency management; consistency |
| **NAS (QNAP apps)** | Runs where data is | Limited environment; complexity |

**Tentative:** Designated workstation with network access to NAS

### 4.3 Distribution and Versioning

> **⚠️ GAP:** Need to establish script management.

| Approach | Description |
|----------|-------------|
| Git repository | Version controlled; users pull updates |
| Shared folder | Scripts on network drive; single source |
| Package | pip-installable package (more overhead) |

**Tentative:** Git repository with periodic releases copied to shared folder

---

## 5. User Interface Options

### 5.1 Command Line (Primary)

All tools available as CLI scripts. Suitable for power users and scripting.

### 5.2 Simple GUI Wrappers (Future)

For less technical users, consider:
- Tkinter-based simple dialogs
- Web interface (Flask/FastAPI)
- Jupyter notebooks with widgets

> **📋 Future consideration:** GUI wrappers based on user feedback during pilot.

---

## 6. Dependencies

**Python packages likely needed:**
- `pyyaml` — Configuration files
- `python-dateutil` — Date parsing
- `tqdm` — Progress bars
- `hashlib` (stdlib) — Checksums
- `pydicom` — DICOM metadata
- `tifffile` — TIFF metadata
- `czifile` or `aicspylibczi` — Zeiss CZI metadata

---

## 7. Development Roadmap

| Phase | Tools | Timeline |
|-------|-------|----------|
| **Pilot** | `ingest_raw` (full + lightweight modes), `create_publication`, `create_project` | Before pilot start |
| **Pilot** | Metadata extractors (integrated into full-mode ingest) | Before first batch ingest |
| **Pilot+** | `backfill_metadata` (upgrade lightweight ingests) | During pilot |
| **Pilot+** | `log_activity`, `validate_registries` | During pilot |
| **Post-pilot** | GUI wrappers, user-supplied metadata workflows | Based on demand |

---

## 8. Related Documents

- [03_RAW_STORAGE](03_RAW_STORAGE.md) — Ingest workflow
- [04_PUBLICATIONS](04_PUBLICATIONS.md) — Publication creation
- [05_PROJECTS](05_PROJECTS.md) — Project creation
- [07_PROVENANCE](07_PROVENANCE.md) — Provenance logging
- [11_OPERATIONS](11_OPERATIONS.md) — Who uses which tools

---

## Open Questions

| ID | Question | Owner | Status |
|----|----------|-------|--------|
| TOOL-01 | Where will scripts run? | Data Mgmt Lead + IT | ⚠️ Needs decision |
| TOOL-02 | Git repo location and access | Data Mgmt Lead | ⚠️ Needs setup |
| TOOL-03 | User training on CLI tools | Data Mgmt Lead | 📋 Planned |
| TOOL-04 | GUI wrapper priority | Users | 📣 Need feedback |
