# 06 — Registries

**Parent:** [Documentation Index](00_INDEX.md)
**Status:** 🔶 Draft
**Last Updated:** 2026-05-20 (DRAFT `session_id` + `primary_kind` columns for ISA grouping + per-ecosystem layout shapes; ISA terminology mapping added in §2.3a)

---

## Purpose

This document specifies the top-level registries that index and document the contents of the storage areas.

---

## 1. Overview

### 1.1 What Are Registries?

Registries are **CSV files** that serve as indexes (manifests) for each storage area. When data is added to the system, an entry is "registered" by adding a row to the appropriate registry.

### 1.2 Registry Locations

> **✅ DECIDED:** All registries live in a single top-level `registries/` directory — centralized, not distributed within each storage area.

| Registry | Location | Purpose |
|----------|----------|---------|
| Raw Registry | `/gjesus3/registries/registry_raw.csv` | Indexes all raw acquisitions |
| Publications Registry | `/gjesus3/registries/registry_publications.csv` | Indexes all publication folders |
| Projects Registry | `/gjesus3/registries/registry_projects.csv` | Indexes all project folders |
| Curated Datasets Registry | `/gjesus3/registries/registry_datasets.csv` | Indexes all curated datasets (if used) |

### 1.3 Why CSV?

| Consideration | CSV Advantage |
|---------------|---------------|
| Human-readable | Can open in any text editor or spreadsheet |
| Tool-friendly | Easy to parse, query, update with scripts |
| Version control | Works well with git if we version registries |
| No dependencies | No database setup or special software |
| Recovery | Even if corrupted, partial data is recoverable |

**Limitation:** Concurrent writes need care (but our low-volume use case makes this manageable).

---

## 2. Raw Registry

**File:** `/gjesus3/registries/registry_raw.csv`

### 2.1 Purpose

Authoritative record of all raw acquisitions deposited in the system.

### 2.2 Schema

> **✅ DECIDED:** Fields are classified by **Population** method — how they get filled during ingest. This enables lightweight mode to produce sparse-but-valid registry entries.

| Field | Type | Required | Population | Description |
|-------|------|----------|------------|-------------|
| `acq_id` | String | ✅ Yes | Auto | Unique acquisition ID (e.g., `ACQ-20260215-ZWSI-001`) |
| `registration_datetime` | ISO DateTime | ✅ Yes | Auto | When this entry was added |
| `acquisition_datetime` | ISO DateTime | 🔶 Recommended | User | When the data was actually acquired. User-supplied via the YAML `registry:` block — either a literal, a `discovered.<field>` reference (e.g. `discovered.acquisition_date` for AxioScan day folders), or `NA` to backfill later. Future: auto-extract from DICOM/.czi headers via the `discovered` namespace. |
| `data_ecosystem` | String | ✅ Yes | User | `MICROSCOPY`, `DICOM`, or `EM`. Determines the top-level folder. |
| `instrument` | String | ✅ Yes | User | Instrument code (e.g., `ZWSI`, `LSM9`, `PET`). |
| `instrument_model` | String | 🔶 Recommended | User | Full instrument name (e.g., `Bruker BioSpec 11.7T`). |
| `modalities_in_study` | String | Optional | User (or auto fallback) | For multi-modal acquisitions: semicolon-separated DICOM modality codes (e.g., `PT;CT`). If left empty/NA, falls back to the source summarizer's `modality` field. |
| `operator` | String | ✅ Yes | User | Person who collected the data. |
| `data_source` | String | ✅ Yes | User | `internal` or `collaborator:<name>`. |
| `sample_id` | String | 🔶 Recommended | User | Sample or animal identifier. See §2.3 for the recommended composite format. |
| `sample_type` | String | 🔶 Recommended | User | Category of biological material. Use the controlled vocabulary in §2.4 (DRAFT). |
| `session_id` | String | 🔶 Recommended (DRAFT) | User | DRAFT 2026-05-20. Groups acquisitions that share a session (one animal session, one MR study, one microscopy slide-loading round, etc.). Maps to the ISA "study" level — see §2.3a. For MRI, value is typically the JRC study identifier (`jrc251016_m17_0424`). For microscopy where acquisitions don't share a meaningful session, may be empty / NA. Status open (REG-08) pending PI sign-off. |
| `primary_kind` | String | ✅ Yes (DRAFT) | Auto | DRAFT 2026-05-20. One of `file` \| `archive` \| `folder` — the shape of the primary entity on disk. `file` = single canonical file (microscopy `.czi`). `archive` = compressed archive (legacy collaborator DICOM `.zip`). `folder` = the acquisition folder itself is the unit (internal MRI ParaVision bundle). See [03_RAW_STORAGE §4.2](03_RAW_STORAGE.md). |
| `primary_file_name` | String | ✅ Yes | Auto | Canonical name of the primary entity. When `primary_kind` = `file` or `archive`, this is a filename (`<ACQ-ID>.czi`, `<ACQ-ID>.zip`). When `primary_kind` = `folder`, this is the folder name (`<ACQ-ID>`) — the unit IS the folder, see [03_RAW_STORAGE §4.3](03_RAW_STORAGE.md). |
| `original_name` | String | ✅ Yes | Auto | Source filename / folder name before ingestion. |
| `file_format` | String | ✅ Yes | Auto | File extension/format (e.g., `.czi`, `.zip`). |
| `file_size_mb` | Number | ✅ Yes | Auto | Size of primary file/folder in **decimal MB** (bytes ÷ 1,000,000), rounded to 1 decimal. Convention adopted 2026-05-12; pre-cutover rows hold the binary value (bytes ÷ 1,048,576) and are not being backfilled. Windows Explorer uses its own hybrid (bytes ÷ 1024 ÷ 1000) and will not match either form exactly. |
| `file_count` | Number | ✅ Yes | Auto | Number of **primary-data files** in the acquisition — not auxiliary or bookkeeping artifacts (`metadata.json`, `checksums.json`, `README.txt`). DICOM: count of `.dcm` (or extensionless DICOM) files. Microscopy: `1` for single-file (`.czi`) acquisitions; for folder-mode batches, count of primary-format files (`.czi`/`.tif`/`.tiff`). Convention adopted 2026-05-12; pre-cutover DICOM rows hold an uninformative count (4 = destination-folder file count) and are not being backfilled. Once DICOM compress-on-ingest ships, the count should come from the archive's central directory rather than the source walk. |
| `canonical_path` | String | ✅ Yes | Auto | Full path to acquisition folder. |
| `checksum_present` | String (Y/N) | ✅ Yes | Auto | `Y` or `N` — is checksums.json present? |
| `extended_metadata_present` | String (Y/N) | ✅ Yes | Auto | `Y` (full mode) or `N` (lightweight mode). |
| `project_hint` | String | Optional | User | Associated project ID if known at deposit. Triggers `.lnk` creation when set. |
| `ingest_config` | String | 🔶 Recommended | Auto | Path (relative to repo root) of the YAML config that produced this row. Empty for interactive ingests or pre-2026-05-06 rows. Used for auditability and reproducibility. |
| `notes` | String | Optional | User | Free-text notes. Supports `${discovered.<field>}` interpolation. |

**Population key:**
- **Auto** — set by the ingest pipeline; user must NOT put it in the YAML `registry:` block.
- **User** — set in the YAML `registry:` block (literal, `discovered.<field>`, or `NA`). See [10_TOOLS §2.1](10_TOOLS.md).

### 2.3a ISA Terminology Mapping (DRAFT)

> **🔶 DRAFT pilot guidance (2026-05-20).** The MFB workflow maps cleanly onto **ISA** (Investigation / Study / Assay) terminology. Adopting that vocabulary in the registry makes the data more compatible with REMBI-style metadata standards and any future migration to XNAT / OMERO / institutional platforms. Status open (REG-09) pending PI sign-off.

| ISA term | gjesus3 equivalent | Where recorded | Example |
|---|---|---|---|
| **Investigation** | Project | `registry_projects.csv` → `project_id` + `short_name` | `PROJ-0007` / `itziar-alphasma` (or for MRI, an animal-protocol-coded project like `PROJ-NNNN` with short_name `ae-biomegune-0525`) |
| **Study** | Session — a coherent acquisition session (one animal session, one slide-loading round) | `registry_raw.csv` → new `session_id` column (DRAFT, see §2.2) | `jrc251016_m17_0424` for an internal MRI session |
| **Assay** | Acquisition — one scan with a distinct protocol | `registry_raw.csv` → `acq_id` (one row) | `ACQ-20251016-MRI-029` |

**Why this matters:**

- For MRI: one ParaVision study folder contains many numbered exams (assays). Each exam is its own ACQ-ID; they share a `session_id` (the JRC study identifier) so the session can be reconstructed via simple registry query.
- For collaborator DICOM (rounds 1-2): the existing zip-per-session model maps onto session=assay (one row, no separate `session_id` populated). Legacy; not retrofitting.
- For microscopy: typically session and assay collapse (one `.czi` = one slide = one session = one assay). `session_id` may be empty/NA; sample_id carries the grouping.

**Implementation:** `session_id` is User-populated via the YAML `registry:` block (literal, `discovered.<field>`, or NA). Existing rows are not backfilled; pre-cutover acquisitions hold empty `session_id`.

### 2.3 Subject and Sample Identity (DRAFT — refines REG-01)

> **🔶 DRAFT pilot guidance, re-grounded 2026-06-03 in FAIR / ISA / REMBI / BIDS / XNAT.** Status open (REG-01) pending PI sign-off. Supersedes the earlier bare `<short_project>_<short_sample>` recommendation. Per **Option B**: the model below is adopted now and carried in the `metadata.json` sidecar; the dedicated registry `subject_id` column is **deferred to the post-exhibition true-production restart** (no quasi-prod migration).

**Two distinct entities, two identifiers.** Every standard we align to models the **subject** (the animal) and the **sample** (the physical thing imaged) as *separate* entities, each with its own identifier, joined by an explicit reference — never collapsed into one overloaded string:

| Standard | Subject entity | Sample entity | Key rule |
|---|---|---|---|
| **ISA** | Source (organism) | Sample | one Source *splits* into ≥1 Samples; "all nodes MUST be uniquely identifiable" |
| **REMBI** | Biosample (organism: species, strain, background) | Specimen (the prepared sample) | organism-level vs preparation-level separated |
| **BIDS** | `participant_id` (species/strain/sex in `participants.tsv`) | `sample_id` (`samples.tsv`) | a sample is "a specimen extracted from a subject"; only the **pair `(participant_id, sample_id)` must be unique** |
| **XNAT** (interop target) | Subject | Session → Scan | Subject is first-class; one Subject → many sessions |

Sources: [ISA model](https://isa-specs.readthedocs.io/en/latest/isamodel.html) · [REMBI (Nat. Methods 2021)](https://www.nature.com/articles/s41592-021-01166-8) · [BIDS data-summary files](https://bids-specification.readthedocs.io/en/stable/modality-agnostic-files/data-summary-files.html) · [XNAT data model](https://wiki.xnat.org/documentation/how-to-use-xnat/understanding-the-xnat-data-model).

#### 2.3.1 Subject identifier — reuse the animal-facility ID

The **subject** of any animal acquisition is identified by the **animal-facility canonical animal ID, reused verbatim**:

```
<animal_code>-AE-biomaGUNE-<NNNN>          e.g. 13-AE-biomaGUNE-0525
```

We **reuse** the facility's own identifier rather than mint a parallel one (FAIR F1 "reuse existing identifiers" — [GO-FAIR F1](https://www.go-fair.org/fair-principles/f1-meta-data-assigned-globally-unique-persistent-identifiers/); the [FAIR Cookbook](https://faircookbook.elixir-europe.org/content/recipes/findability/identifiers.html) treats this as a *local accession* made globally unique by namespacing — `prefix:accession` — which is the future-globalization path, **not** a reason to bake meaning into the string today). This composite is also the **DB lookup key** (`projects.projectAlias = NNNN` + `animals.animal_code` = the leading number; verified 2026-06-02). The DB has **no single stored unique-ID column** — the composite is constructed (`animals.id` PK is the only single-column unique, internal-only) and has one near-duplicate in 18,353; treat as effectively unique and flag any exact collision.

#### 2.3.2 Where the subject ID lives (Option B)

The subject ID is carried in the per-acquisition `metadata.json` **`subject:` block** as `facility_animal_id` ([08_METADATA §4.4](08_METADATA.md)). A dedicated **registry `subject_id` column is DEFERRED to the true-production restart** — the restart is the natural point to add it without migrating quasi-prod rows. Until then, registry-level grouping rides on `sample_id` + the sidecar.

#### 2.3.3 `sample_id` rules

| Acquisition kind | `sample_id` | Rationale |
|---|---|---|
| **`organism`** (in-vivo MRI / PET / SPECT) | = the subject ID `<animal_code>-AE-biomaGUNE-<NNNN>` | the animal *is* the sample (ISA Source ≡ Sample for in-vivo; DICOM has only a Patient, no separate specimen) |
| **`tissue`** (organ sections) | the specimen's own label, **unique within the subject** (BIDS `(subject, sample)` rule) — e.g. an organ/replicate label | one animal yields several Specimens; the animal link is the `facility_animal_id` reference, **not** concatenation |

- **Organ/anatomy is a structured field, not part of the ID.** The organ-letter in legacy short IDs (`B` in `ID13B`) becomes a dedicated **`anatomical_entity`** value (REMBI "Location within biosample") — in the sidecar now, promoted to a registry column at the restart (converges with the REG-07 `sample_organism` + `anatomical_entity` split, §2.4).
- **Don't overload the ID with meaning** (FAIR Cookbook: prefer semantically-free identifiers; meaning belongs in fields). A readable label MAY be rendered for display, but the *identifying* fields are `facility_animal_id` (subject) + `sample_id` + `anatomical_entity`.
- Official single-string IDs that already exist are used verbatim. Pre-cutover rows keep their `<short_project>_<short_sample>` `sample_id` (e.g. `0525_ID26H`); not retrofitted in quasi-prod. Raw filename chunks always remain in the sidecar `discovered` block, so nothing is lost.

#### 2.3.4 Ingest-tool implication (parse the animal short code)

The instrument short code embeds `animal_code` with instrument-specific decoration: NI `m14`→`14`, MRI `m13`→`13`, AxioScan `ID13B`→`13` + organ `B`. The ingest tools must parse it into `animal_code` (+ `anatomical_entity` for tissue), derive the project alias from `project_hint` (`ae-biomegune-NNNN` → `NNNN`), and compose the canonical subject ID / DB lookup key. Tracked in `tasks/tasks.md §3.2`. Current per-instrument templates carry an illustrative `facility_animal_id` that predates this and is corrected to the canonical form.

### 2.4 Sample Type Vocabulary (DRAFT)

> **🔶 DRAFT pilot guidance.** `sample_type` is the category of biological material in REMBI terms — *not* the species and *not* the anatomy. Status open (REG-07) pending PI sign-off.

REMBI separates concerns: **sample type** (the kind of biological material), **organism/species**, **anatomical entity**, **preparation**, and **imaging mode**. In the current registry only one of these has its own column (`sample_type`); the others ride along in `sample_id` / `notes` for now (see future split tracked in `tasks/tasks.md` §3.1).

**Controlled vocabulary** — small enough to remember, broad enough to cover everything in scope:

| Value | Means | Examples in this project |
|-------|-------|--------------------------|
| `tissue` | Excised biological material (sections, slices, biopsies, fixed/unfixed) | All AxioScan / Cell Observer / LSM 900 WSI of mouse organ sections |
| `organism` | Whole live or post-mortem animal | In vivo MRI, PET/CT, SPECT of mice |
| `cells` | Cultured or isolated cell preparations | Future Cell Observer cell-culture work (if it lands in scope) |
| `material` | Non-biological samples (nanoparticles, contrast agents, synthetic constructs) | Future SEM/TEM nanomaterial characterization |
| `phantom` | Imaging calibration objects | Platform commissioning / QA scans, if archived |

**Notes:**

- Use lowercase, one of the five values verbatim. If a future sample doesn't fit, flag for vocab extension before ingest rather than inventing a value on the fly.
- Species/anatomy details that today appear as freeform `"mouse lung section"`-style strings in pre-cutover example rows should migrate to dedicated columns once REG-07 closes (proposed `sample_organism` + `anatomical_entity`; tracked in `tasks/tasks.md` §3.1).
- For batches where every acquisition shares the same type, set the value at the YAML template level rather than per-row. The AxioScan 7 per-instrument template pre-fills `sample_type: tissue` for this reason.

> **🔶 Linked requirements (DRAFT 2026-05-29):** For `sample_type ∈ {organism, tissue}`, the per-acquisition `metadata.json` MUST include two blocks:
>
> **`subject:` block** — species / strain / sex / date_of_birth → derived age_at_acquisition (the ARRIVE-aligned required fields, DECIDED; DOB added 2026-06-02) + `facility_animal_id` (the canonical **subject ID** `<animal_code>-AE-biomaGUNE-<NNNN>`, reused verbatim — see the identity model in §2.3) + optional genotype / weight / cohort_id / procedures (a **structured** `[{type, date}]` list from the DB's controlled vocab, **not** free text — DB explored 2026-06-02). Schema in [08_METADATA §4.4](08_METADATA.md). Auto-populated from the **animal-facility DB** (`animal_facility` schema, access obtained 2026-06-02); an ingest-time DB miss / no-credentials queues the acquisition for superuser recovery rather than failing (§4.4.6). Integration tracked in `tasks/tasks.md §3.2`.
>
> **`condition:` block** — `is_control` (**highly-recommended, non-blocking** tri-state `true`/`false`/`null=unknown` — the healthy-vs-case flag; WARN if null, never blocks ingest) + recommended `disease_model` + `disease_state` + optional `control_type` / `treatment` / `timepoint_days` / `study_arm`. Schema in [08_METADATA §4.5](08_METADATA.md); the non-blocking model is [§4.7](08_METADATA.md). Operator-entered, set once per batch/session (`disease_model` auto-seeds from DB `projects.name`). `is_control == true`/`false` is the primary cohort filter; `null` surfaces in the completeness report.
>
> **`anatomy:` block** (in-vivo `organism` scans) — `is_whole_body` (**highly-recommended, non-blocking** tri-state — the dead-simple full-body-vs-ROI flag; WARN if null) + UBERON-coded `region` when not whole-body. Schema in [08_METADATA §4.6](08_METADATA.md).
>
> Both blocks always required for internal MRI + Nuclear Imaging (sample is always an organism); required for microscopy when the sample is animal-derived (typical case).

### 2.5 Example

> **Note:** The CSV example below shows the schema **including** the DRAFT `session_id` and `primary_kind` columns. Production registry rows pre-2026-05-20 do not have these columns; the schema grows column-by-column with a defensive header check (see [10_TOOLS](10_TOOLS.md)) preventing silent shift.

```csv
acq_id,registration_datetime,acquisition_datetime,data_ecosystem,instrument,instrument_model,modalities_in_study,operator,data_source,sample_id,sample_type,session_id,primary_kind,primary_file_name,original_name,file_format,file_size_mb,file_count,canonical_path,checksum_present,extended_metadata_present,project_hint,ingest_config,notes
ACQ-20260215-ZWSI-001,2026-02-15T16:30:00Z,2026-02-15T14:00:00Z,MICROSCOPY,ZWSI,Zeiss Axio Scan 7,,MBC,internal,MOUSE-2024-042,tissue,,file,ACQ-20260215-ZWSI-001.czi,MFB_MBC_PROJ-0003_MOUSE-2024-042_HE_20x.czi,.czi,2450,1,/raw/MICROSCOPY/2026/2026-02/ACQ-20260215-ZWSI-001/,Y,Y,PROJ-0003,tools/configs/axioscan7_20260215.yaml,Microscopy single-file
ACQ-20251016-MRI-029,2025-10-16T17:00:00Z,2025-10-16T08:38:22Z,DICOM,MRI,Bruker BioSpec 7T,,IFF,internal,jrc251016_m17_0424_heart,organism,jrc251016_m17_0424,folder,ACQ-20251016-MRI-029,29,folder,150,17,/raw/DICOM/2025/2025-10/ACQ-20251016-MRI-029/,Y,Y,PROJ-0009,tools/configs/mri_bruker_20251016_TEST.yaml,Internal MRI ParaVision exam 29 (cine cardiac)
ACQ-20260220-PET-001,2026-02-20T11:00:00Z,2026-02-20T09:00:00Z,DICOM,PET,Molecubes beta-CUBE,PT;CT,CLM,internal,MOUSE-2024-042,organism,,archive,ACQ-20260220-PET-001.zip,,.zip,2100,4,/raw/DICOM/2026/2026-02/ACQ-20260220-PET-001/,Y,Y,,tools/configs/pet_20260220.yaml,Legacy PET/CT zip-per-session (pre-folder-bundle)
ACQ-20260301-XMRI-001,2026-03-01T09:00:00Z,,DICOM,XMRI,,,RT,collaborator:HPIC,HPIC-case-01,,,archive,ACQ-20260301-XMRI-001.zip,case_01.zip,.zip,450,3,/raw/DICOM/2026/2026-03/ACQ-20260301-XMRI-001/,Y,N,,,Lightweight collaborator zip
```

### 2.6 Update Rules

| Action | Allowed | Who | When |
|--------|---------|-----|------|
| Add new entry | ✅ Yes | Operator (via deposit) | At deposit time |
| Correct metadata | ✅ Yes | Admin | If error discovered (log correction) |
| Delete entry | ❌ No | — | Entries are permanent |
| Modify after deposit | ⚠️ Limited | Admin | Only to fix errors, not change facts |

---

## 3. Publications Registry

**File:** `/gjesus3/registries/registry_publications.csv`

### 3.1 Purpose

Index of all publication folders with status tracking and bibliographic information.

### 3.2 Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `pub_id` | String | ✅ Yes | Unique ID (e.g., `PUB-0001`) |
| `short_name` | String | ✅ Yes | Folder name (e.g., `lung-fibrosis-markers-2026`) |
| `working_title` | String | ✅ Yes | Current/working title |
| `status` | Enum | ✅ Yes | `created`, `in_progress`, `submitted`, `published`, `abandoned` |
| `pi` | String | ✅ Yes | Principal investigator |
| `first_author` | String | ✅ Yes | First author |
| `corresponding_author` | String | 🔶 Recommended | Corresponding author (if different) |
| `created_date` | Date | ✅ Yes | When folder was created |
| `submitted_date` | Date | Optional | When manuscript was submitted |
| `published_date` | Date | Optional | When paper was published |
| `closed_date` | Date | Optional | When folder was locked |
| `journal` | String | Optional | Target/actual journal |
| `doi` | String | Optional | Publication DOI |
| `repository_link` | String | Optional | Link to data repository (Zenodo, etc.) |
| `folder_location` | String | ✅ Yes | Current path to folder |
| `notes` | String | Optional | Free-text notes |

### 3.3 Example

```csv
pub_id,short_name,working_title,status,pi,first_author,corresponding_author,created_date,submitted_date,published_date,closed_date,journal,doi,repository_link,folder_location,notes
PUB-0001,lung-fibrosis-markers-2026,Quantification of fibrotic markers in IPF lung tissue,in_progress,Jesús Ruiz-Cabello,Marta Beraza,Jesús Ruiz-Cabello,2026-02-15,,,,,,/publications/lung-fibrosis-markers-2026/,Initial pilot publication
PUB-0002,pet-mri-fusion-2025,Multimodal PET-MRI fusion for tumor characterization,published,Jesús Ruiz-Cabello,Claudia Miranda,Jesús Ruiz-Cabello,2025-06-01,2025-09-15,2025-12-20,2025-12-22,J Nuclear Med,10.1234/jnm.2025.12345,https://zenodo.org/record/1234567,/publications/pet-mri-fusion-2025/,Archived and closed
```

### 3.4 Update Rules

| Action | Allowed | Who | When |
|--------|---------|-----|------|
| Add new entry | ✅ Yes | Operator | At folder creation |
| Update status | ✅ Yes | Operator/Admin | As publication progresses |
| Add DOI/links | ✅ Yes | Operator/Admin | When published |
| Close entry | ✅ Yes | Admin | At folder lock |
| Delete entry | ❌ No | — | Entries are permanent |

---

## 4. Projects Registry

**File:** `/gjesus3/registries/registry_projects.csv`

### 4.1 Purpose

Index of project workspaces with ownership and status tracking.

### 4.2 Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `project_id` | String | ✅ Yes | Unique ID (e.g., `PROJ-0001`) |
| `short_name` | String | ✅ Yes | Folder name. **See [05_PROJECTS §9](05_PROJECTS.md) for the open-question warning on naming conventions — group consensus required.** |
| `description` | String | ✅ Yes | Brief description of project scope. May be auto-populated at ingest-time creation; see `owner` note. |
| `owner` | String | ✅ Yes | Primary owner/SPOC. When the project is auto-created by `ingest_raw.py` (via `auto_create_projects: true` and the `auto_create_project:` block — see [10_TOOLS §2.1.4](10_TOOLS.md)), the initial value can be supplied by literal or `${discovered.<field>}` interpolation. **First-write-wins:** subsequent ingests touching the same project never update this column. The source of truth after creation is `_project.yaml` (manually editable). |
| `start_date` | Date | ✅ Yes | When project started |
| `status` | Enum | ✅ Yes | `active`, `paused`, `closed` |
| `last_activity` | Date | 🔶 Recommended | Last modification (for retention tracking) |
| `folder_location` | String | ✅ Yes | Path to folder |
| `notes` | String | Optional | Free-text notes. Like `description`, can be auto-populated at first creation. |

### 4.3 Example

```csv
project_id,short_name,description,owner,start_date,status,last_activity,folder_location,notes
PROJ-0001,ipf-biomarkers,IPF biomarker quantification study,MBC,2026-01-15,active,2026-02-10,/projects/proj-ipf-biomarkers/,May lead to PUB-0001
```

---

## 5. Curated Datasets Registry

**File:** `/gjesus3/registries/registry_datasets.csv`

> **❓ EVALUATING:** Curated datasets area is under evaluation. See [12_CURATED_DATASETS](12_CURATED_DATASETS.md) for full specification.

### 5.1 Purpose

Index of curated, versioned datasets (e.g., segmentation ground truth, benchmark sets) that accumulate across projects and are intended for long-term reuse.

### 5.2 Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `dataset_id` | String | ✅ Yes | Unique ID (e.g., `DS-SEG-0001`) |
| `short_name` | String | ✅ Yes | Human-readable folder name |
| `description` | String | ✅ Yes | What this dataset contains and its purpose |
| `dataset_type` | String | ✅ Yes | Category: `segmentation`, `registration`, `benchmark`, etc. |
| `data_ecosystem` | String | ✅ Yes | Which RAW ecosystem this relates to: `MICROSCOPY`, `DICOM`, or `EM` |
| `owner` | String | ✅ Yes | Dataset curator / responsible person |
| `created_date` | Date | ✅ Yes | When dataset was created |
| `version` | String | ✅ Yes | Version identifier (e.g., `v1.0`) |
| `status` | Enum | ✅ Yes | `active`, `superseded`, `archived` |
| `sample_count` | Number | 🔶 Recommended | Number of labeled samples / items |
| `source_acq_ids` | String | ✅ Yes | Semicolon-separated list of RAW ACQ-IDs this dataset derives from |
| `folder_location` | String | ✅ Yes | Path to dataset folder |
| `provenance_present` | Boolean | ✅ Yes | `Y` or `N` — does the dataset include provenance documentation? |
| `notes` | String | Optional | Free-text notes |

### 5.3 Example

```csv
dataset_id,short_name,description,dataset_type,data_ecosystem,owner,created_date,version,status,sample_count,source_acq_ids,folder_location,provenance_present,notes
DS-SEG-0001,lung-fibrosis-gt-v1,Manual segmentation masks for IPF lung tissue (H&E WSI),segmentation,MICROSCOPY,RT,2026-03-15,v1.0,active,24,ACQ-20260215-ZWSI-001;ACQ-20260216-ZWSI-002;ACQ-20260217-ZWSI-003,/curated_datasets/segmentation/MICROSCOPY/DS-SEG-0001/,Y,Initial training set for fibrosis segmentation model
```

### 5.4 Update Rules

| Action | Allowed | Who | When |
|--------|---------|-----|------|
| Add new entry | ✅ Yes | Dataset curator | At dataset promotion |
| Update sample count | ✅ Yes | Dataset curator | As dataset grows |
| Create new version | ✅ Yes | Dataset curator | Material changes → new version or new ID |
| Mark superseded | ✅ Yes | Dataset curator | When new version replaces old |
| Delete entry | ❌ No | — | Entries are permanent |

### 5.5 ID Generation

**Pattern:** `DS-<TYPE>-<NNNN>`

| Component | Description | Examples |
|-----------|-------------|----------|
| `DS` | Fixed prefix | `DS` |
| `<TYPE>` | Short dataset type code | `SEG` (segmentation), `REG` (registration), `BEN` (benchmark) |
| `<NNNN>` | Sequential number (4 digits) | `0001`, `0002` |

---

## 6. Registry Management

### 6.1 Access Control

| Registry | Read | Write |
|----------|------|-------|
| Raw | All operators | Admin (or via deposit script) |
| Publications | All operators | Operator for own entries; Admin for all |
| Projects | All operators | Operator for own entries; Admin for all |
| Curated Datasets | All operators | Dataset curator or Admin only |

### 6.2 Backup

Registries are critical metadata. Consider:
- Git versioning (if repository set up)
- Periodic backup copies
- Include in any system backup

### 6.3 Validation

> **📋 Planned:** Scripts to validate registry integrity:
> - All paths resolve to actual folders
> - Required fields are populated
> - IDs are unique
> - Dates are valid format
> - `data_ecosystem` values match actual folder locations

---

## 7. ID Generation

### 7.1 Acquisition IDs

Pattern: `ACQ-<YYYYMMDD>-<INST>-<SEQ>`

Generation: Scripted (preferred) or manual with lookup of current day's highest sequence.

### 7.2 Publication IDs

Pattern: `PUB-<NNNN>`

Generation: Next available number (scan registry for highest, increment).

### 7.3 Project IDs

Pattern: `PROJ-<NNNN>`

Generation: Next available number.

### 7.4 Dataset IDs

Pattern: `DS-<TYPE>-<NNNN>`

Generation: Next available number within each type.

---

## 8. Related Documents

- [03_RAW_STORAGE](03_RAW_STORAGE.md) — Raw area using this registry
- [04_PUBLICATIONS](04_PUBLICATIONS.md) — Publications area using this registry
- [05_PROJECTS](05_PROJECTS.md) — Projects area using this registry
- [12_CURATED_DATASETS](12_CURATED_DATASETS.md) — Curated datasets area using this registry

---

## Open Questions Summary

| ID | Question | Owner | Status |
|----|----------|-------|--------|
| REG-01 | Include sample_id in raw registry as required or recommended? Composite format `<short_project>_<short_sample>` recommended (§2.3); PI sign-off pending. | Users / PI | 🔶 Draft |
| REG-02 | What additional fields needed for REMBI/ISA alignment? | Data Mgmt Lead | 🔶 See [08_METADATA](08_METADATA.md) |
| REG-03 | Git versioning for registries? | Data Mgmt Lead | 📋 Future consideration |
| REG-04 | Validation script requirements | Data Mgmt Lead | 📋 Planned |
| REG-05 | Curated datasets registry: finalize schema after pilot experience | Data Mgmt Lead | ❓ Evaluating |
| REG-06 | Track DICOM instance count (.dcm files) in registry or only in extended metadata? | Data Mgmt Lead | 🔶 Draft |
| REG-07 | Sample type controlled vocabulary (`tissue`/`organism`/`cells`/`material`/`phantom`) DRAFT in §2.4; PI sign-off + first round of cross-instrument application pending. Future split of species/anatomy into dedicated columns. | Users / PI | 🔶 Draft |
| REG-08 | DRAFT `session_id` column (§2.2) — groups acquisitions that share an ISA "study" (one animal session, one MR study, etc.). For MRI typically the JRC study identifier; for microscopy may be empty/NA. | Users / PI | 🔶 Draft — pending PI sign-off |
| REG-09 | DRAFT ISA terminology mapping (§2.3a) — Investigation=Project / Study=Session / Assay=Acquisition. Adopting ISA vocabulary improves REMBI compatibility + future XNAT/OMERO portability. | Users / PI | 🔶 Draft — pending PI sign-off |
