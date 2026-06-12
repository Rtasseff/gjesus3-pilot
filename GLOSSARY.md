# Glossary — gjesus3 RDM Pilot

Plain-language definitions of terms a newcomer hits undefined across this repo. Linked from [README.md](README.md) and [mfb-rdm-docs/00_INDEX.md](mfb-rdm-docs/00_INDEX.md). Where a term has a deeper specification, the relevant `mfb-rdm-docs/NN_*.md` module is linked.

---

## gjesus3 concepts

- **gjesus3** — The dedicated QNAP NAS (and the RDM system built on it) for the MFB group at CIC biomaGUNE. Positioned as the **research-facing working layer** for imaging data in a project's ~5-year active window, *complementing* (not replacing) the instrument platforms' own deep-time raw archives — see [13_GJESUS3_ROLE](mfb-rdm-docs/13_GJESUS3_ROLE.md).
- **sidecar** — The per-acquisition `metadata.json` file written next to each acquisition in `/raw/<ACQ-ID>/`. It is the searchable face of an acquisition, holding `user_supplied` fields, the `discovered.*` namespace, optional `subject:`/`condition:`/`anatomy:` blocks, and an ecosystem-specific embedded-metadata block. Immutable after ingest; specified in [08_METADATA §4.3](mfb-rdm-docs/08_METADATA.md).
- **`discovered.*`** — The auto-discovered field namespace. Each value is extracted automatically at ingest from the filename, the folder path, or the file's embedded metadata (e.g. `discovered.czi_objective_mag`, `discovered.mri_echo_time_ms`), and can be referenced from a YAML config. The per-instrument fields are listed in [09_MODALITIES](mfb-rdm-docs/09_MODALITIES.md).
- **ecosystem** / **data_ecosystem** — The tooling/standard family that handles the data, used as the top-level `/raw/` folder: `MICROSCOPY` (Zeiss `.czi`), `DICOM` (MRI + Nuclear Imaging), or `EM` (electron microscopy, under evaluation). Organising by ecosystem rather than per-instrument keeps the folder tree stable when new instruments arrive — see [03_RAW_STORAGE §2](mfb-rdm-docs/03_RAW_STORAGE.md).
- **primary_kind** — A registry/sidecar field naming the on-disk shape of an acquisition's single primary entity: `file` (one canonical file, e.g. microscopy `.czi`), `archive` (a compressed bundle, e.g. legacy collaborator DICOM `.zip`), or `folder` (the acquisition folder itself is the unit, e.g. an internal MRI ParaVision bundle). See [06_REGISTRIES §2.2](mfb-rdm-docs/06_REGISTRIES.md) and [03_RAW_STORAGE §4](mfb-rdm-docs/03_RAW_STORAGE.md).
- **quasi-production** — The pilot's deliberate lifecycle: each instrument iterates **test → purge → accept-as-quasi-production**, and after the team exhibition **everything gets purged** and restarted as true production with feedback folded in. "Done" means "done in quasi-production"; the `TEST` tags in config names and registry notes are intentional and stay.
- **registry** — A top-level CSV that indexes one storage area (raw, publications, projects, curated datasets). Adding data means appending a row. The raw registry `registry_raw.csv` is the source of truth for everything on gjesus3 — see [06_REGISTRIES](mfb-rdm-docs/06_REGISTRIES.md).

## ID schemes

See [06_REGISTRIES §7](mfb-rdm-docs/06_REGISTRIES.md) for generation rules.

- **ACQ-ID** — Acquisition identifier, format `ACQ-<YYYYMMDD>-<INST>-<SEQ>` (e.g. `ACQ-20251016-MRI-029`): the acquisition date, an instrument code (`ZWSI`, `MRI`, `PET`, …), and a per-day sequence number. One ACQ-ID = one scan/assay = one registry row.
- **PROJ** — Project (workspace) identifier, format `PROJ-<NNNN>` (e.g. `PROJ-0007`), with a sequential 4-digit number. Maps to the ISA "Investigation" level (see Standards below).
- **PUB** — Publication identifier, format `PUB-<NNNN>` (e.g. `PUB-0001`), sequential. Indexes a publication-ready data package in the publications registry.
- **DS** — Curated-dataset identifier, format `DS-<TYPE>-<NNNN>` (e.g. `DS-SEG-0001`), where `<TYPE>` is a short dataset-type code (`SEG` segmentation, `REG` registration, `BEN` benchmark) and `<NNNN>` is sequential within each type. The curated-datasets area is still under evaluation — see [12_CURATED_DATASETS](mfb-rdm-docs/12_CURATED_DATASETS.md).

## Standards, ontologies & external systems

- **REMBI** (Recommended Metadata for Biological Images) — The community standard for biological-imaging metadata, hierarchical (Study → Biosample → Image Acquisition → Image). gjesus3 adopts a pruned subset as the basis for its extended metadata — see [08_METADATA §3](mfb-rdm-docs/08_METADATA.md).
- **ISA** (Investigation / Study / Assay) — A general experiment-metadata model. gjesus3 maps it as **Investigation = Project**, **Study = Session** (a coherent acquisition session), **Assay = Acquisition** (one scan); adopting the vocabulary improves REMBI compatibility and future XNAT/OMERO portability — see [06_REGISTRIES §2.3a](mfb-rdm-docs/06_REGISTRIES.md).
- **UBERON** — A cross-species anatomy ontology. gjesus3 uses UBERON codes for the `anatomy.region` field (the organ a scan covers or a tissue section was cut from), keeping anatomy queryable uniformly across mouse and rat — see [08_METADATA §4.6](mfb-rdm-docs/08_METADATA.md).
- **JCAMP-DX** — A plain-text key-value file format (originating in spectroscopy). Bruker ParaVision stores its MRI acquisition parameters in JCAMP-DX auxiliary files (`subject`/`acqp`/`method`/`visu_pars`), which the ingest parses into the sidecar's `mri:` block — see [09_MODALITIES §1.4](mfb-rdm-docs/09_MODALITIES.md).
- **ARRIVE** (ARRIVE 2.0 — Animal Research: Reporting of In Vivo Experiments) — Reporting guidelines for animal studies. Its "Essential 10" (species, strain, sex, age, …) define the required fields of the preclinical `subject:` block — see [08_METADATA §4.4](mfb-rdm-docs/08_METADATA.md).
- **FAIR** — The principle that data should be Findable, Accessible, Interoperable, and Reusable. Cited throughout for choices like reusing existing identifiers rather than minting new ones and not overloading IDs with meaning.
- **XNAT** — An open-source imaging-informatics platform (DICOM-centric, browser-based, with a Subject → Session → Scan data model). A future migration/interoperability target that gjesus3's structure is kept portable to — see [13_GJESUS3_ROLE §4](mfb-rdm-docs/13_GJESUS3_ROLE.md).
- **OMERO** — An open-source image-data-management platform for microscopy (OME ecosystem). The intended downstream home for the group's microscopy data; gjesus3 keeps metadata/structure migratable to it — see [13_GJESUS3_ROLE](mfb-rdm-docs/13_GJESUS3_ROLE.md).

## Status markers

The same status concept is shown two ways in the repo, and they are equivalent. The **emoji legend in [00_INDEX.md](mfb-rdm-docs/00_INDEX.md) is canonical**; the word set in [CLAUDE.md](CLAUDE.md) is its prose form.

| Emoji (00_INDEX.md) | Word (CLAUDE.md) | Meaning |
|---|---|---|
| ✅ | `DECIDED` | Settled; do not change without explicit user instruction. |
| 🔶 | `DRAFT` | Can be refined, but flag substantive changes. |
| — | `GAP` | Information or decision needed; don't invent the answer. |
| — | `EVALUATING` | Under active consideration; present options rather than choosing. |
| — | `INPUT NEEDED` | Waiting on stakeholder feedback; don't fill in assumptions. |
