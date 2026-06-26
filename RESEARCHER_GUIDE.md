# Researcher Guide — finding and using your data on gjesus3

> **Who this is for:** MFB researchers who have imaging data on the **gjesus3**
> NAS and want to find it, understand how it's organised, and use it. Plain
> language, no code. One page — follow the section that matches your task.
>
> New to the vocabulary? Every bolded term is defined in [`GLOSSARY.md`](GLOSSARY.md).
> Questions not answered here? See the researcher FAQ at [`tools/FAQ.md`](tools/FAQ.md).

**What gjesus3 is, in one line:** the group's **research-facing working layer**
for imaging data — an organised, searchable copy of your acquisitions in their
roughly 5-year active window. It complements the instrument platforms' own raw
archives rather than replacing them. The full rationale is in
[`13_GJESUS3_ROLE`](mfb-rdm-docs/13_GJESUS3_ROLE.md); you don't need it to use the system.

---

## 1. Find your data — the Finder

The fastest way to locate an acquisition is the **Finder**: a single searchable
web page that lives on the share. You don't need any software, login, or Python —
just a hardwired on-site machine that can reach the NAS.

1. **Open the share** in File Explorer: `\\GJESUS3\gjesus3\gjesus3-data` (often
   mapped to a drive letter such as `J:\gjesus3-data`).
2. **Double-click** `registries\index.html` for the **global** Finder (every
   acquisition), or open the `index.html` inside **your project's** folder
   (`projects\<your-project>\index.html`) for just that project's data. It opens
   in the browser already on the machine.
3. **Type in the search box.** It filters instantly across every column — try a
   sample (`m13`), an animal (`13-AE-biomaGUNE-0525`), an instrument (`MRI`,
   `PET`), a date (`2025-10`), an organ (`heart`), or a project name. Click a
   column header to sort; click a row to open the **detail panel**.
4. **Click "Copy path"** in the detail panel and paste it into File Explorer's
   address bar to open that folder. There are separate Copy-path buttons for the
   **raw data**, the **project link**, and the acquisition's **metadata.json**.
   *Tip:* paste the copied `metadata.json` path into a Chrome/Edge tab instead —
   the browser renders the metadata as a tidy collapsible tree, no viewer needed.

The Finder columns are: Acq ID, Date, Instrument, Modality, Researcher, Operator,
Sample, Subject, Organism, Sample type, Original name, Project, Owner. The page is
a snapshot of the registry and refreshes automatically after each new ingest.

> Power users / scripting: there is also a command-line search (`find_acq.py`).
> Full Finder reference — filters, generation, limitations — in
> [`tools/FINDER.md`](tools/FINDER.md).

---

## 2. Understand the layout

A few concepts make everything else click into place:

- **Acquisition / ACQ-ID** — one scan or assay (one microscopy slide, one MRI
  exam, one PET scan) is one **acquisition**, identified by an **ACQ-ID** like
  `ACQ-20251029-PET-001`: the acquisition date, the instrument code, and a
  per-day sequence number. One ACQ-ID = one row in the registry.
- **`/raw/` is immutable.** Your acquisitions live under
  `\\GJESUS3\gjesus3\gjesus3-data\raw\` (organised by data family —
  `MICROSCOPY` and `DICOM`). Once an acquisition is deposited, **its files never
  change.** Treat `/raw/` as read-only — open and copy from it, but never edit in
  place.
- **`/projects/` is your workspace.** A project folder
  (`\\GJESUS3\gjesus3\gjesus3-data\projects\<your-project>\`) is where you and
  the group organise work, analysis output, and notes. Inside it, `raw_linked\`
  holds **links** back to the raw acquisitions that belong to the project — a link
  looks and opens like the real file but takes no extra space and does not copy or
  move the original. (More in §4.)
- **metadata.json sidecar** — next to each acquisition in `/raw/` is a
  `metadata.json` file: the **searchable face** of that acquisition. It holds what
  you (or the operator) supplied, fields auto-extracted from the file and its
  embedded metadata, and — for animal-derived data — `subject` (species, strain,
  sex, age), `condition`, and `anatomy` blocks. It's read-only; open it in a
  browser tab to read it as a collapsible tree. Spec:
  [`08_METADATA`](mfb-rdm-docs/08_METADATA.md).

---

## 3. Standards that apply to you

Two things are genuinely in your hands as a researcher.

### 3.1 Name your files *before* acquisition

The single highest-leverage thing you can do is **follow your instrument's file /
folder naming convention at the instrument**, before the data ever reaches
gjesus3. A good name lets the ingest auto-extract sample, subject, and project
context; a bad one means that information is lost or has to be re-entered by hand.
Find your instrument and read its convention:

| Your instrument | Code(s) | Naming-convention note |
|---|---|---|
| AxioScan 7 (whole-slide) | `ZWSI` | [`equipment/axioscan7-wsi/axioscan7_data_handling_workflow_notes.md`](equipment/axioscan7-wsi/axioscan7_data_handling_workflow_notes.md) |
| Cell Observer | `CELL` | [`equipment/cell-observer/cell_observer_data_handling_workflow_notes.md`](equipment/cell-observer/cell_observer_data_handling_workflow_notes.md) |
| LSM 900 (confocal) | `LSM9` | [`equipment/lsm900/lsm900_data_handling_workflow_notes.md`](equipment/lsm900/lsm900_data_handling_workflow_notes.md) |
| Bruker MRI (ParaVision) | `MRI` | [`equipment/mri-platform/internal_mri_data_handling_workflow_notes.md`](equipment/mri-platform/internal_mri_data_handling_workflow_notes.md) |
| Nuclear Imaging (PET/SPECT/CT) | `PET` `SPECT` `CT` | [`equipment/nuclear-imaging/internal_ni_data_handling_workflow_notes.md`](equipment/nuclear-imaging/internal_ni_data_handling_workflow_notes.md) |

The map of all instruments is [`equipment/INDEX.md`](equipment/INDEX.md).

### 3.2 Study metadata you can supply

Some context isn't captured at the instrument — what the study was, whether an
animal was a control, what disease model applied. At ingest you (or the operator)
can supply the acquisition-level `subject` / `condition` / `anatomy` fields; these
are **recommended, never blocking** — if something is unknown the ingest records a
placeholder and a warning and continues, so your data is never held up. What each
field means: [`08_METADATA §4`](mfb-rdm-docs/08_METADATA.md).

> 🕗 **Study-level project metadata (planned, not yet live).** A richer,
> *study-level* metadata area inside each project (`projects/<proj>/metadata/`,
> for things like study aim and biosample sheets) is **designed but not deployed
> yet** — it exists on none of the live projects today. Until it lands, keep
> study context in your own notes and flag it to the Data Management Lead. Status
> and plan: [`tasks/BACKLOG.md`](tasks/BACKLOG.md); design:
> [`05_PROJECTS §3`](mfb-rdm-docs/05_PROJECTS.md).

---

## 4. Get and use a project workspace

A **project** (`PROJ-<NNNN>`, with a folder like `proj-ae-biomegune-0423`) is a
durable unit of work — typically a funded project or an animal-protocol scope, not
a single experiment. It is where the group's analysis and organisation happen.

- **To get a project workspace**, ask the **Data Management Lead** (Ryan Tasseff,
  Data Office) — projects are created centrally so the registry and links stay
  consistent.
- **Inside your project**, `raw_linked\` links the project to its raw
  acquisitions (created automatically when data is ingested for that project). The
  rest of the folder is yours to organise: analysis output, derived images, notes.
- **Derived data lives in the project, not in `/raw/`.** Anything you generate
  (e.g. NIfTI conversions, segmentations, figures) belongs under your project
  folder; raw stays untouched and is the thing everything traces back to.
- ⚠️ **Projects are temporary.** A project workspace is working space, not a
  permanent archive — it can be closed and deleted once work concludes (the raw
  acquisitions and their registry rows always remain). Don't keep the only copy of
  anything important loose in a project. Lifecycle and close-out:
  [`05_PROJECTS §4`](mfb-rdm-docs/05_PROJECTS.md).

---

## 5. Cite and export your data

- **Cite an acquisition** by its **ACQ-ID** (e.g. `ACQ-20251029-PET-001`) — it is
  stable and uniquely identifies the scan in the registry. For a methods section,
  use the Finder to pull the exact instrument, modality, subject, and date for
  each acquisition you used.
- **Export** by copying out of `/raw/` (for the source acquisition) or your
  project folder (for derived work) to your own analysis drive. Use **Copy path**
  in the Finder to jump straight to the folder, then copy. Remember laptops can't
  reach gjesus3 — export from a hardwired on-site machine.
- **Publications** get a dedicated, provenance-tracked package in
  `/publications/` so outputs trace back to their raw sources. That area is
  defined but not yet populated; when you're heading toward publication, contact
  the Data Management Lead. Spec:
  [`04_PUBLICATIONS`](mfb-rdm-docs/04_PUBLICATIONS.md);
  provenance: [`07_PROVENANCE`](mfb-rdm-docs/07_PROVENANCE.md).

---

## 6. Get help

| If you want… | Go to |
|---|---|
| Answers to common researcher questions | [`tools/FAQ.md`](tools/FAQ.md) |
| A word you don't recognise | [`GLOSSARY.md`](GLOSSARY.md) |
| Full Finder reference (search, limits) | [`tools/FINDER.md`](tools/FINDER.md) |
| What "raw" means for your instrument | [`equipment/INDEX.md`](equipment/INDEX.md) |
| The bigger design picture | [`README.md`](README.md) · [`mfb-rdm-docs/00_INDEX.md`](mfb-rdm-docs/00_INDEX.md) |

**Still stuck?** Contact the Data Management Lead — **Ryan Tasseff, Data Office, CIC biomaGUNE.**

---

*Are you here to **ingest** data from an instrument instead of find it? That's the
operator path — start at [`START_HERE.md`](START_HERE.md).*
