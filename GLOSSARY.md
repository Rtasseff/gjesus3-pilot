# Glossary — gjesus3 RDM Pilot

Plain-language definitions of terms a newcomer (or a chatbot answering on this repo's behalf) hits undefined across the project. Linked from [README.md](README.md) and [mfb-rdm-docs/00_INDEX.md](mfb-rdm-docs/00_INDEX.md). Where a term has a deeper specification, the relevant `mfb-rdm-docs/NN_*.md` module is linked.

_Last Updated: 2026-06-26_

---

## gjesus3 concepts

- **gjesus3** — The dedicated QNAP NAS (and the research-data-management system built on it) for the MFB group at CIC biomaGUNE. Positioned as the **research-facing working layer** for imaging data in a project's ~5-year active window, *complementing* (not replacing) the instrument platforms' own deep-time raw archives — see [13_GJESUS3_ROLE](mfb-rdm-docs/13_GJESUS3_ROLE.md).
- **ingest** — The act of bringing one acquisition onto gjesus3: the tooling copies the data into `/raw/`, allocates an [ACQ-ID](#id-schemes), appends a registry row, writes the **sidecar**, **hard-links** it into the relevant project(s), and refreshes the **Finder** (all defined below). One ingest = one new acquisition.
- **acquisition** — One scan / assay = one [ACQ-ID](#id-schemes) = one row in `registry_raw.csv`. The atomic unit gjesus3 tracks. There are ~13,555 acquisitions in `/raw/`.
- **sidecar** — The per-acquisition `metadata.json` file written next to each acquisition in `/raw/<ACQ-ID>/`. It is the searchable face of an acquisition, holding `user_supplied` fields, the `discovered.*` namespace (below), optional `subject:`/`condition:`/`anatomy:` blocks, and an ecosystem-specific embedded-metadata block. **Immutable after ingest.** Specified in [08_METADATA §4.3](mfb-rdm-docs/08_METADATA.md).
- **hard link** — How a [project](#id-schemes) references its raw acquisition data: a second directory entry pointing at the *same bytes on disk* as the file in `/raw/`. The project copy looks and opens like a real file but uses **zero extra storage**, and it inherits raw's read-only protection (one shared ACL). **DECIDED + APPLIED 2026-06-02.** This **replaced** the older Windows `.lnk` shortcut method (283 links migrated; `.lnk` is **retired** — never describe it as current). See [10_TOOLS §2.1.1](mfb-rdm-docs/10_TOOLS.md).
- **`discovered.*`** — The auto-discovered field namespace. Each value is extracted automatically at ingest from the filename, the folder path, or the file's embedded metadata (e.g. `discovered.czi_objective_mag`, `discovered.mri_echo_time_ms`), and can be referenced from a YAML config. The per-instrument fields are listed in [09_MODALITIES](mfb-rdm-docs/09_MODALITIES.md).
- **resolver** — The small ingest component that turns the YAML config's `registry:` and `link_filename:` templates into concrete values for one acquisition. It supports three value forms — a literal (`internal`), a bare `discovered.<field>` reference, or `${…}` interpolation inside a string — substituting in the `discovered.*` fields (above) gathered for that case. Implemented in `tools/ingest/resolver.py`; see [10_TOOLS §2.1](mfb-rdm-docs/10_TOOLS.md).
- **researcher** vs **operator** — Two distinct people recorded per acquisition (vocabulary fixed 2026-06-09). The **researcher** is who *set up / ran the study* (the data owner); the **operator** is who *ran the equipment* for this acquisition. For MRI and Nuclear Imaging they are usually the same person; for microscopy usually different (a technician operates, a researcher owns). Both are registry columns. ("Tech" is the related *permission* role — staff who deposit data; "user" means software users only.) See [06_REGISTRIES §2.3a-bis](mfb-rdm-docs/06_REGISTRIES.md).
- **ecosystem** / **data_ecosystem** — The tooling/standard family that handles the data, used as the top-level `/raw/` folder: `MICROSCOPY` (Zeiss `.czi`), `DICOM` (MRI + Nuclear Imaging), or `EM` (electron microscopy — reserved, not deployed). Organising by ecosystem rather than per-instrument keeps the folder tree stable when new instruments arrive — see [03_RAW_STORAGE §2](mfb-rdm-docs/03_RAW_STORAGE.md).
- **instrument code** — The short code identifying which instrument produced an acquisition; it appears in the [ACQ-ID](#id-schemes) and the registry. In-scope codes: **`ZWSI`** (Zeiss AxioScan 7 whole-slide imager), **`CELL`** (Zeiss Cell Observer), **`LSM9`** (Zeiss LSM 900 confocal), **`MRI`** (Bruker ParaVision MRI), **`PET`** / **`SPECT`** / **`CT`** (Molecubes / MILabs nuclear imaging). See [09_MODALITIES](mfb-rdm-docs/09_MODALITIES.md) and [equipment/INDEX.md](equipment/INDEX.md).
- **primary_kind** — A registry/sidecar field naming the on-disk shape of an acquisition's single primary entity: `file` (one canonical file, e.g. microscopy `.czi`), `archive` (a compressed bundle, e.g. legacy collaborator DICOM `.zip`), or `folder` (the acquisition folder itself is the unit, e.g. an internal MRI ParaVision bundle). See [06_REGISTRIES §2.2](mfb-rdm-docs/06_REGISTRIES.md) and [03_RAW_STORAGE §4](mfb-rdm-docs/03_RAW_STORAGE.md).
- **Finder** — The self-contained searchable index of the registry: a generated `registries/index.html` (plus a per-project `index.html` in each project folder) that a researcher double-clicks over SMB — no server, no Python on their side. Type a sample id / instrument / date / organ / project and get matching acquisitions with a one-click **Copy path** to the data. Auto-refreshed at the end of every successful ingest. See [tools/FINDER.md](tools/FINDER.md).
- **registry** — A top-level CSV that indexes one storage area. The four are `registry_raw.csv` (28 columns — the source of truth for everything on gjesus3), `registry_projects.csv`, `registry_subjects.csv` (one row per subject), and `registry_publications.csv` (planned/empty). Adding data means appending a row. See [06_REGISTRIES](mfb-rdm-docs/06_REGISTRIES.md).
- **quasi-production** *(HISTORICAL)* — The pilot's earlier lifecycle: each instrument iterated **test → purge → accept-as-quasi-production**, and after the team exhibition the **whole quasi-production dataset was purged**. That purge **happened on 2026-06-10** and is **complete** — `J:\gjesus3-data` is now the live **true-production** system, and there is **no future purge/restart pending**. The term survives only in pre-purge notes and `TEST`-tagged config names; for current work, gjesus3 is true production.

## ID schemes

See [06_REGISTRIES §7](mfb-rdm-docs/06_REGISTRIES.md) for generation rules.

- **ACQ-ID** — Acquisition identifier, format `ACQ-<YYYYMMDD>-<INST>-<SEQ>` (e.g. `ACQ-20251016-MRI-029`): the acquisition date, an [instrument code](#gjesus3-concepts) (`ZWSI`, `MRI`, `PET`, …), and a per-day sequence number. One ACQ-ID = one scan/assay = one registry row.
- **session_id** — A registry column grouping acquisitions that share one session — one animal session, one MR study, one microscopy slide-loading round. Maps to the ISA "study" level (see Standards below). For MRI it is typically the JRC study identifier (e.g. `jrc251016_m17_0424`); for microscopy where acquisitions don't share a meaningful session it may be empty/NA. ✅ DECIDED 2026-06-11; see [06_REGISTRIES §2.2 / §2.3a](mfb-rdm-docs/06_REGISTRIES.md).
- **subject_ids** — A registry column holding the facility animal id(s) for an acquisition, `;`-joined and always treated as a list (multi-animal-aware). Auto-populated from the enrichment subject block; renamed from `subject_id` on 2026-06-12. See [06_REGISTRIES](mfb-rdm-docs/06_REGISTRIES.md).
- **PROJ** — Project (workspace) identifier, format `PROJ-<NNNN>` (e.g. `PROJ-0007`), with a sequential 4-digit number. Maps to the ISA "Investigation" level (see Standards below). There are ~50 projects.
- **PUB** — Publication identifier, format `PUB-<NNNN>` (e.g. `PUB-0001`), sequential. Indexes a publication-ready data package in the publications registry (currently planned/empty).
- **DS** — Curated-dataset identifier, format `DS-<TYPE>-<NNNN>` (e.g. `DS-SEG-0001`), where `<TYPE>` is a short dataset-type code (`SEG` segmentation, `REG` registration, `BEN` benchmark) and `<NNNN>` is sequential within each type. The curated-datasets area is still under evaluation — see [12_CURATED_DATASETS](mfb-rdm-docs/12_CURATED_DATASETS.md).

## Standards, ontologies & external systems

- **REMBI** (Recommended Metadata for Biological Images) — The community standard for biological-imaging metadata, hierarchical (Study → Biosample → Image Acquisition → Image). gjesus3 adopts a pruned subset as the basis for its extended metadata — see [08_METADATA §3](mfb-rdm-docs/08_METADATA.md).
- **ISA** (Investigation / Study / Assay) — A general experiment-metadata model. gjesus3 maps it as **Investigation = Project**, **Study = Session** (a coherent acquisition session, grouped by [`session_id`](#id-schemes)), **Assay = Acquisition** (one scan, one [ACQ-ID](#id-schemes)); adopting the vocabulary improves REMBI compatibility and future XNAT/OMERO portability — see [06_REGISTRIES §2.3a](mfb-rdm-docs/06_REGISTRIES.md).
- **UBERON** — A cross-species anatomy ontology. gjesus3 uses UBERON codes for the `anatomy.region` field (the organ a scan covers or a tissue section was cut from), keeping anatomy queryable uniformly across mouse and rat — see [08_METADATA §4.6](mfb-rdm-docs/08_METADATA.md).
- **JCAMP-DX** — A plain-text key-value file format (originating in spectroscopy). Bruker ParaVision stores its MRI acquisition parameters in JCAMP-DX auxiliary files (`subject`/`acqp`/`method`/`visu_pars`), which the ingest parses into the sidecar's `mri:` block — see [09_MODALITIES §1.4](mfb-rdm-docs/09_MODALITIES.md).
- **ARRIVE** (ARRIVE 2.0 — Animal Research: Reporting of In Vivo Experiments) — Reporting guidelines for animal studies. Its "Essential 10" (species, strain, sex, age, …) define the required fields of the preclinical `subject:` block — see [08_METADATA §4.4](mfb-rdm-docs/08_METADATA.md).
- **FAIR** — The principle that data should be Findable, Accessible, Interoperable, and Reusable. Cited throughout for choices like reusing existing identifiers rather than minting new ones and not overloading IDs with meaning.
- **XNAT** — An open-source imaging-informatics platform (DICOM-centric, browser-based, with a Subject → Session → Scan data model). A future migration/interoperability target that gjesus3's structure is kept portable to — see [13_GJESUS3_ROLE §4](mfb-rdm-docs/13_GJESUS3_ROLE.md).
- **OMERO** — An open-source image-data-management platform for microscopy (OME ecosystem). The intended downstream home for the group's microscopy data; gjesus3 keeps metadata/structure migratable to it — see [13_GJESUS3_ROLE](mfb-rdm-docs/13_GJESUS3_ROLE.md).

## Status markers

The same status concept is shown two ways in the repo, and they are equivalent. The **emoji legend in [00_INDEX.md](mfb-rdm-docs/00_INDEX.md) is canonical**; the word set in [CLAUDE.md](CLAUDE.md) is its prose form.

| Emoji | Word | Meaning |
|---|---|---|
| ✅ | `DECIDED` | Settled; do not change without explicit user instruction. |
| 🔶 | `DRAFT` | Can be refined, but flag substantive changes. |
| ⚠️ | `GAP` | Information or decision needed; don't invent the answer. |
| ❓ | `EVALUATING` | Under active consideration; present options rather than choosing. |
| 📋 | `INPUT NEEDED` | Waiting on stakeholder feedback; don't fill in assumptions. |
| 🕗 | `PLANNED / DEFERRED` | Designed but not yet deployed; tracked for a later stage. |
