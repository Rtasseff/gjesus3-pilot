# Cell Observer workflow notes

**Last updated:** 2026-06-26 · **Instrument code:** `CELL` · **Ecosystem:** `MICROSCOPY`

> **Audience:** operator- and developer-oriented (acquisition + post-scan data
> handling, so the ingest template can parse it). Researchers who only need to
> *find and use* their data should start at
> [`RESEARCHER_GUIDE.md`](../../RESEARCHER_GUIDE.md). The part that matters most to
> a researcher here: for cells-mode work the **folder structure carries most of the
> context**, so organise your folders well — file names are lighter than on the
> AxioScan.

## Scope
These notes summarize the current observed workflow for use of the **Cell Observer** at CIC biomaGUNE, with emphasis on **data handling and storage** rather than imaging technique, training, or scientific interpretation.

**Source basis:**
- instrument walkthrough / discussion with operator
- rough transcript of the discussion

**Important note on transcript quality:**
The transcript is poor in places. This document reflects the most likely meaning of the conversation, with uncertain points left visible rather than forced into false precision.

**Relationship to other instruments:**
This workflow appears to be **very similar to the confocal workflow**, and the operator indicated that the **confocal is handled the same way** from the data-handling perspective. The **file format is also the same as the Axio Scan 7**, i.e. Zeiss **.czi**.

---

## Purpose of this note
Capture, in a simple and updateable form, how Cell Observer data are:
- acquired
- selected for retention
- manually saved out of the acquisition environment
- organized in operator-controlled folders
- handed off to researchers

No conclusions are drawn here beyond documenting the workflow and identifying open questions.

---

## Main distinguishing feature vs. Axio Scan 7
The biggest difference from the **Axio Scan 7** workflow is the **save location and handoff model**.

For Axio Scan 7:
- scans are saved directly to a platform/network location

For Cell Observer:
- images are first acquired on the **local computer attached to the instrument**
- the operator then chooses which images to keep
- those retained images are then **manually saved or transferred** into a folder location chosen by the operator
- in the observed case, this was the operator’s **own user folder in the group network drive**

This matters because there is **no clear platform-wide storage standard** at this stage. The operator appears to have a personal working convention, but it was only partly explicit and may not represent a formal standard.

At present, this operator-controlled location functions as a **staging point** from which the researcher is expected to retrieve the data. In future, this staging logic may instead be redirected toward **gjesus3**.

---

## High-level workflow

### 1. Image acquisition on the local instrument computer
Images are acquired on the **local computer attached to the Cell Observer**.

Unlike the Axio Scan 7 workflow, files are **not automatically written directly to a platform network drive during acquisition**.

Instead, the operator acquires images locally, reviews them, and then decides which ones to save.

---

### 2. Selection of images for retention
The operator does **not necessarily save everything acquired**.

Observed / stated practice:
- the operator may collect multiple images during the session
- after acquisition, the operator selects the images worth keeping
- only those selected images are then saved onward into the folder structure

This appears especially important for:
- trial runs
- optimization runs
- small or preliminary assays
- quick checks before later doing a more final acquisition on the Axio Scan 7

This means the Cell Observer is sometimes used as:
- a normal imaging microscope
- a trial / exploratory imaging system
- a live-cell or incubated imaging system

but the **data-handling pattern** remains: acquire locally first, then selectively save.

---

### 3. Save destination after acquisition
After choosing what to keep, the operator manually saves/transfers the retained files into a folder location.

In the observed case, this was:
- the operator’s **own folder** on the **group network drive**

This appears to be done because:
- the operator performed imaging on behalf of other researchers
- the files are initially under the operator’s control because the operator acquired them
- the operator then organizes them in a way that allows the researcher to find and retrieve them later

This folder location is not described as a permanent archive.

Rather, it functions as a **temporary or provisional location**.

Because group network drives are small, this location should be treated as a **staging area**, not a true long-term home for the data.

---

### 4. Operator-controlled folder organization
The operator appears to use a folder structure inside her own area to make the saved images findable for the relevant researcher.

The workflow described was approximately:
- operator’s own folder
- subfolder for the relevant researcher
- within that, folders named by experiment / assay / project context

The exact structure varies depending on the type of work.

#### For cell / assay work
The operator seemed to describe a structure such as:
- researcher name
- experiment / assay name
- condition

The operator indicated that, for these kinds of smaller or faster experiments, she often relies more on:
- the **folder structure**
- the **date**
- simple condition naming

rather than a rich, highly standardized file naming convention.

This appears to be partly for practical reasons:
- speed during acquisition
- many images per session
- repeated conditions / replicates
- plate-based work (for example, many wells)
- live-cell imaging where fast handling matters

#### For animal / histology-type work
The operator described a more normalized structure when the work is more like histology or animal-derived imaging.

In that case, the metadata elements used seem more likely to include:
- animal project ID
- organ
n- stain
- magnification

In one part of the discussion, the operator indicated that for animal-related work she may use the **animal project ID** as the project folder name.

So, in practice, folder naming may become more structured when the work is more clearly tied to a tracked animal project.

---

### 5. File naming
The operator indicated that there is **not currently a strong, explicit file naming convention** in routine use for all cases.

This is an important contrast with the Axio Scan 7 workflow, where naming is more clearly emphasized.

Observed / inferred practice:
- for some routine cell assay work, the operator may rely mainly on folder structure plus date
- the file names themselves may carry only a limited amount of additional information
- the operator suggested that the folders often provide more useful context than the file names

Possible metadata used in file or folder names for cell assay work:
- assay / experiment identity
- condition
- timepoint or duration
- replicate / well context in some reduced form

Possible metadata used in more structured animal / histology-related work:
- animal project ID
- organ
- stain
- magnification

The operator also indicated that when handling many images quickly, especially in plate-based or repeated live-cell workflows, rich file naming becomes impractical during acquisition.

So the current practical model appears to be:
- **folders carry much of the context**
- **file names may be relatively light**
- **date is used as an implicit anchor**

This is important for future automation, because it means metadata may need to be reconstructed from a combination of:
- folder path
- file name
- file metadata

rather than file name alone.

---

### 6. Output file format
The operator indicated that the **output format is the same as for the Axio Scan 7**, i.e. Zeiss **.czi**.

This implies that the Cell Observer data likely share the same broad metadata potential as other Zeiss microscopy workflows:
- multi-dimensional image data
- embedded acquisition metadata
- possible channel, scale, and acquisition settings metadata

However, this note does **not** yet confirm which metadata fields are actually populated in this specific workflow.

---

### 7. Researcher handoff
Once the operator has saved the retained images into the operator-controlled folder structure, the researcher is expected to retrieve them.

Observed / described practice:
- the researcher knows that the images will be in the operator’s folder area
- the operator uses a recognizable folder structure so the researcher can find the images
- after the researcher takes the files and moves them elsewhere, they effectively leave the operator’s active area

The operator’s description suggested that this is a known social/working convention rather than a formal tracked handoff system.

---

### 8. Retention and removal from the operator staging area
The operator indicated that after some time the files should be removed from this provisional location.

This reinforces that the operator’s group-drive area is functioning as:
- a working area
- a researcher pickup area
- a temporary holding location

and **not** as permanent storage.

At present, there does not appear to be a formal or automated retention rule documented in this workflow.

---

### 9. Confocal similarity
The operator indicated that the **confocal follows the same data-handling model**.

So, unless later observation shows otherwise, the confocal should currently be assumed to share these workflow characteristics:
- acquisition on the instrument-local computer
- manual selection of files for retention
- manual save/transfer into operator-controlled group-drive folders
- reliance on folder structure for context
- handoff to the researcher
- eventual removal from the staging location

---

## Current best interpretation of the operator’s organization logic
The operator’s organization system appears to be pragmatic rather than formalized.

A likely interpretation is:
- files live first on the instrument computer
- retained files are manually saved into the operator’s network-drive space
- top-level organization may be by researcher
- next-level organization may be by experiment / assay / animal project
- lower-level organization may include conditions or specific experiment descriptors
- the exact amount of detail may vary depending on whether the work is:
  - exploratory / provisional
  - routine cell assay work
  - animal / histology-related work

This suggests that the operator’s folder structure is carrying a large part of the practical metadata burden.

---

## Documented standard vs. observed practice
At present, no clear platform-wide documented standard was described for this Cell Observer save/transfer stage.

So the important distinction here is not between a formal documented rule and a violation, as with the Axio Scan 7 case.

Instead, the distinction is between:
- what the operator currently does in practice
- what a future standard **could** be made to require

This is important because this workflow appears to present a real opportunity to define a better staging convention before ingestion to a more permanent destination such as **gjesus3**.

---

## Main data-handling points identified so far
- Initial acquisition occurs on the **local instrument computer**.
- Only selected images are retained; not everything acquired is necessarily saved onward.
- Retained files are manually moved or saved into the operator’s **own folder area** on a group network drive.
- That location functions as a **temporary staging area**, not permanent storage.
- Current organization appears to rely heavily on **folder structure**.
- File naming appears to be lighter and less standardized than in the Axio Scan 7 workflow.
- Folder structure may vary by work type, especially between:
  - cell assay / live-cell / exploratory work
  - animal / histology-related work
- The file format is **.czi**, shared with Axio Scan 7 and likely with confocal workflows.
- The confocal appears to use the same practical save/handoff model.
- Researcher pickup and later relocation of files appear to be manual.

---

## Risks / weaknesses visible from the workflow record
These are not deep analysis points, but they are practical features that should remain visible:
- no clear platform-wide standard for the staging structure
- strong dependence on operator-specific folder organization
- weaker or inconsistent file naming conventions
- metadata may be split across folder path, file name, and embedded file metadata
- manual researcher handoff rather than tracked ingestion
- staging location on small group network storage
- temporary files may be removed after some time without a formal ingestion step
- possible inconsistency between operators if different people use different folder logic

---

## Open questions / items to update later
1. Exact save/export path used from the local instrument computer to the group drive
2. Whether the operator’s folder structure is consistent enough to document formally
3. Whether other operators use the same or a different structure
4. Whether the confocal truly follows the same structure in practice
5. Which metadata fields are actually embedded in the `.czi` files from this workflow
6. Whether there are recognizable repeated folder-name patterns for cell assay work
7. Whether a minimal file naming convention already exists informally but was only partly described
8. Whether plate/well information is preserved mainly in files, folders, or embedded metadata
9. How long files usually remain in the operator-controlled staging area
10. At what point researchers move the data elsewhere, and where
11. What the best future standard should be for pre-ingestion staging before movement to **gjesus3**

---

## Current best summary of the workflow
1. Images are acquired on the **local computer attached to the Cell Observer**.
2. The operator reviews the acquired images and selects which ones are worth keeping.
3. The retained images are manually saved or transferred into the operator’s own folder area on a **group network drive**.
4. The operator organizes those files using a manual folder structure that appears to be designed to help the relevant researcher find them.
5. For cell assay work, the folder structure may emphasize researcher, experiment/assay, and condition, with relatively light file naming.
6. For animal / histology-related work, the organization may be more structured and may include items like animal project ID, organ, stain, and magnification.
7. The files are saved in **Zeiss `.czi` format**.
8. The researcher later retrieves and moves the files elsewhere.
9. The operator-controlled network-drive location is treated as a **temporary staging area** rather than a permanent archive.
10. The operator indicated that the **confocal follows the same practical data-handling model**.

---

## Integration with gjesus3

Cell Observer is **live in gjesus3 true production** (instrument code `CELL`,
ecosystem `MICROSCOPY`). The `.czi` files share the same extractor as the other
two Zeiss microscopes; the path from the operator's staging folder to a
searchable, project-linked acquisition is:

1. **Stage.** The operator's group-drive folder (the staging area described in
   [§3](#3-save-destination-after-acquisition) / [§4](#4-operator-controlled-folder-organization)) is the ingest **staging_dir**.
   Because **folder structure carries most of the context** here, the template
   relies on the folder path, not the filename, for sample/experiment context.
   Source/historical locations are catalogued in
   [`../historical_data_archives.md`](../historical_data_archives.md).
2. **Ingest.** Run `tools/ingest_raw.py` with a per-batch config copied from the
   cells-mode template
   [`tools/templates/instruments/cell_observer_cells.yaml`](../../tools/templates/instruments/cell_observer_cells.yaml)
   (set `staging_dir` + `notes`), **or** use the frozen GUI
   **`gjesus3_ingest.exe`** (microscopy page). That template `path_parse`s the
   `<researcher>/<cell_line>/<experiment>/` folder levels and `filename_parse`s the
   lighter filename chunks into `discovered.*`, plus the 21 `czi_*` embedded
   fields. **The template header lists every `discovered.*` field available — it is
   the operator's reference card; this note does not duplicate it.** (A separate
   *animal / histology-mode* template is deferred until a real example folder is
   available — tracked in [`tasks/BACKLOG.md`](../../tasks/BACKLOG.md); historical
   tissue/histology work has largely moved to the AxioScan 7.)
3. **Land in `/raw/` + registry.** Each `.czi` is deposited under
   `/raw/MICROSCOPY/`, gets an immutable `metadata.json` sidecar, and one row per
   acquisition is appended to `registries/registry_raw.csv`. For `sample_type:
   cells` a per-batch `condition:` block (control-vs-case, treatment) is written;
   `subject:` / `anatomy:` are **not** written for cells (cell lines aren't in the
   animal-facility DB). The condition writer is **non-blocking** — unknowns become
   sentinels + a WARN, never a failure.
4. **Hard-link into a project.** The acquisition is hard-linked into its project
   under `/projects/<proj>/raw_linked/`. (Project naming is a provisional
   `<researcher>-<experiment>` stopgap — PROJ-05; the right durable handle comes
   from the group's project-naming consensus.) A hard link opens like the real file
   but takes no extra space.
5. **Finder.** The Finder (`registries/index.html` global + the project's own
   `index.html`) auto-refreshes, so the acquisition is immediately searchable.

This system path is exactly the **standardized staging → ingestion** that the
"Documented standard vs. observed practice" and "Risks / weaknesses" sections
above were pointing toward: an operator-organised staging folder becomes a durable
`/raw/` acquisition with a registry row, structured metadata, and a project link.

For the full operator workflow see [`START_HERE.md`](../../START_HERE.md) and
[`tools/INGEST_CLI.md`](../../tools/INGEST_CLI.md); the system map is
[`equipment/INDEX.md`](../INDEX.md). The confocal **LSM 900** (same operator, same
K: share, same `.czi` format) is documented in
[`../lsm900/lsm900_data_handling_workflow_notes.md`](../lsm900/lsm900_data_handling_workflow_notes.md).

> 🕗 Filename/folder context the `.czi` doesn't carry, and per-acquisition cohort
> overrides, are intended for the **study-level** project metadata area
> (`/projects/<proj>/metadata/<acq_id>.json`), which is **planned, not yet
> deployed** (Phase 4 — see [05_PROJECTS §3](../../mfb-rdm-docs/05_PROJECTS.md) and
> [`tasks/BACKLOG.md`](../../tasks/BACKLOG.md)).

---

## Next step
The next useful step is to define or infer a **standardized staging structure** for this workflow before movement into permanent storage.

This should consider:
- what metadata can reliably come from the `.czi` files
- what metadata must come from file names
- what metadata is currently only present in folder structure
- how to make the operator-controlled staging area suitable for later semi-automated ingestion into **gjesus3**

A second useful step would be to revisit the transcript and any real example folders to determine whether the operator’s structure is already more regular than it first appeared.

