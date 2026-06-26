# Axio Scan 7 workflow notes

**Last updated:** 2026-06-26 · **Instrument code:** `ZWSI` · **Ecosystem:** `MICROSCOPY`

> **Researchers — 2-line summary:** Name your slide files at the scanner with the
> `<group>_<operator>_<project>_<sample>_<stain>_<magnification>` convention (see
> [§4 Data identification / naming](#4-data-identification--naming)); a good name lets gjesus3 auto-extract your
> sample, source animal, and project. Then it's ingested into gjesus3 and you find
> it in the [Finder](../../RESEARCHER_GUIDE.md). Everything below is the operator /
> developer detail.

> **Audience:** operator- and developer-oriented. These notes capture the
> acquisition + post-scan data-handling reality of the Axio Scan 7 so the
> per-instrument ingest template ([`tools/templates/instruments/axioscan7.yaml`](../../tools/templates/instruments/axioscan7.yaml))
> can parse it correctly. Researchers who only need to *find and use* their data
> should start at [`RESEARCHER_GUIDE.md`](../../RESEARCHER_GUIDE.md); the
> naming convention in §4 is the part that matters to them.

## Scope

These notes summarize the current observed and documented workflow for use of the **Axio Scan 7** at CIC biomaGUNE, with emphasis on **data handling and storage** rather than user training or imaging technique details.

**Source basis:**

- walkthrough with Marta from Jesús’s group
- platform instructions for Axio Scan 7 use
- follow-up discussion on what happens after scans are completed

**Current boundary of understanding:**
This version now includes the initial post-scan handling observed in practice. Some technical details still remain open until direct access to the platform drive is available for testing.

**Broader relevance:**
This appears to be a workflow similar to other optical microscopy / histology bioimage processes in the platform, including the **Cell Observer**, and is therefore relevant to the **gjesus3 pilot**.

---

## Purpose of this note

Capture, in a simple and updateable form, how data are:

- named
- initially stored
- reviewed and reduced
- transferred onward
- re-organized after scanning

No conclusions are drawn here beyond documenting the workflow and identifying open questions.

---

## High-level workflow

### 1. Booking and pre-use administrative steps

Users book the equipment through the booking calendar on the intranet.

At the time of booking, the user should provide a **brief description of the sample**.

Relevant usage constraints from the platform instructions:

- booking normally up to **2 weeks in advance**
- maximum **4 hours per day**
- maximum **3 bookings per week**
- after-hours and weekend restrictions are more flexible
- longer bookings during working hours require advance contact with the responsible person

These are mainly operational rules, but the sample description in the booking system may also represent a small amount of contextual metadata relevant to later tracing of use.

---

### 2. Startup and software

The user starts the machine and opens the associated Axio Scan 7 software on the dedicated computer.

---

### 3. Selecting the save location

Data are saved to the **goptical** network location on the IT-managed network.

The save location is:

`\\goptical\GOpticalUsers data\AxioScan\<YYYYMMDD>\` 

According to the platform instructions:

- data should be saved **directly into the day’s folder in goptical**
- the **first user of the day** creates the folder for that day

The date folder uses the form:

`<YYYYMMDD>`

Older folders may be \<DDMMYYYY>.

Observed / clarified structure:

- each scan produces **one file**
- that file is saved **directly into the day’s folder**
- there is **no additional folder structure** created by the scanner within goptical for the scan outputs

This means the main structure at this stage is:

- the **day folder**
- the **file name itself**

---

### 4. Data identification / naming

The platform instructions define the required identification structure as:

1. **Group 3-letter code** (examples given: MFB, PRC)
2. **User name in capitals** using name/surname format (noted in the instructions as 2 or 3 elements)
3. **Brief sample description**

These fields are separated by underscores:

**GroupCode\_UserName\_SampleDescription**

In practice, the third section is not necessarily a single field. It can contain **multiple additional fields**, each also separated by underscores.

So the practical structure is better understood as:

**standardized field 1** + **standardized field 2** + **one or more user-defined fields**

The user-defined fields may include information such as:

- sample or animal ID
- stain
- magnification
- labels
- technique
- other details useful for rapid identification

Observed example from Jesús’s group workflow:

- an additional ID (likely an animal ID)
- the stain used
- the magnification

At present, this naming convention appears to be the **primary explicit metadata mechanism controlled by users during acquisition**.

There is **no known platform-wide standard** for how the user-defined fields should be structured beyond the general instruction. It would be useful to determine whether individual groups have their own internal naming conventions.

---

### 5. Loading and configuring slides

The scanner can support up to **25 slots**, with **4 slides per slot**, for a total of **100 slides**.

Users specify which slide positions are active, load the slides, and then adjust the automatically generated default names to match the required naming format.

---

### 6. Scan setup relevant to data content

For each slide, the user selects a **scan profile** from a drop-down menu.

This likely corresponds to preconfigured acquisition settings.

The user then performs a preview and defines what regions will actually be scanned by:

- selecting automatically detected objects
- manually defining regions of interest
- merging or splitting detected objects
- placing focus points when needed for high-resolution scans

These steps affect the content of the final output and may also generate metadata.

---

### 7. Scan execution and output generation

The user starts the scan, and the data are written to the selected location in **Gopticals**.

The output is generated by default as a **Zeiss native .czi file** (**Carl Zeiss Image** format).

Clarified characteristics of this format:

- proprietary Zeiss format
- can store multiple dimensions
- can store tiled images
- can store z-stacks
- can store multiple channels
- can store time series
- can store rich metadata

At present, it is not yet locally confirmed exactly which metadata fields are populated in this workflow, though the format is known to support metadata and web documentation suggests this is likely.

Each scan produces **one .czi file** saved directly into the day’s folder in Gopticals.

---

### 8. Immediate review and deletion on Gopticals

The platform instructions state that once the work is finished, the user should:

- check which data are worth saving
- delete the rest

Observed reality appears to be more variable.

Current understanding:

- this behavior is **user- or group-dependent**
- some users appear to move files elsewhere and then delete them from Gopticals
- some users may leave files in place
- the practical rule seems to be at least that clearly unneeded files should be deleted (we also understand that future rules may make all files temporary, we should not assume this is a permanent location for files).

Observed example from Jesús’s group support workflow:

- the technician scans slides for researchers
- later, she moves the files off the network drive to another storage location
- after transfer, she deletes the files from the IT-supported platform network drive

Historical context appears relevant here: platform network drives like Gopticals have had limited storage, which likely shaped this behavior.

So, in practice, Gopticals currently appears to function partly as a **temporary acquisition location**, even if there is not yet a consistent platform-wide plan for retention.

---

### 9. Transfer after scanning: observed practice

This stage is now partially documented.

According to the platform instructions:

- later, the user can transfer the data **from their PC to their group server**
- **external units for data storage are forbidden**

Observed practice in the documented case differs from the written rule.

#### Observed workflow in Jesús’s group support case

The technician handling scans for multiple researchers performs the following steps:

1. identify the relevant files manually based on file names
2. move/copy those files off Gopticals
3. place them onto an **external drive** because the **group server does not have enough space**
4. organize them on the external drive using an additional manual folder structure
5. hand off the external drive / files to the researcher
6. delete the files from Gopticals

#### Observed organizational structure after transfer

On the external drive, the technician uses an additional project-oriented folder structure.

In the observed example:

- project folders were created
- within a project folder, there were additional folders for different **stains**

This is noteworthy because the stain may already be present in the file name, so there may be redundant organization between:

- file names
- folder structure

It is not yet known whether this organization is specific to the technician’s workflow, common across Jesús’s group, or used by other groups.

---

## Documented workflow vs. observed workflow

### Documented platform expectation

- save directly into the day’s folder in Gopticals
- identify files using the required naming convention
- review data and delete what is not worth keeping
- later transfer data onward
- do **not** use external storage units

### Observed practice in at least one case

- save directly into the day’s folder in Gopticals
- use the naming convention as the main identifier
- manually select files for retention
- move retained files to **external drives** because the group server is too small
- use an additional manual folder structure outside the scanner environment
- delete files from Gopticals after transfer

This distinction is important and should remain explicit in future versions.

---

## Main data-handling points identified so far

- Initial storage occurs in **Gopticals**.
- Each scan produces a single **.czi** file.
- There is **no additional scanner-generated folder structure** beyond the day folder.
- File naming is the main first-level organizational and identification mechanism.
- The first two naming components are standardized; the third section may contain **multiple user-defined fields separated by underscores**.
- The .czi format likely contains rich metadata, but this still needs local confirmation.
- Retention and deletion behavior on Gopticals is currently inconsistent or at least not yet clearly standardized in practice.
- In observed practice, onward transfer may rely on **manual copying to external drives**, which introduces both management and security risks.
- No README, ELN entry, or additional structured metadata capture is currently part of the observed workflow.

---

## Risks / weaknesses visible from the workflow record

These are not deep analysis points, but they are practical features of the current workflow that should be kept visible:

- heavy dependence on file naming for identification
- inconsistent retention behavior on Gopticals
- manual file selection and transfer
- use of many small external drives
- likely existence of single-copy situations after transfer
- no structured metadata capture beyond file name + embedded file metadata
- no standardized secondary folder structure known across users/groups

---

## Open questions / items to update later

1. Direct confirmation of .czi metadata contents for this workflow
2. Whether scan profile and acquisition settings are reliably extractable from .czi outputs
3. Whether groups have internal naming conventions beyond the platform rule
4. What proportion of users leave files in Gopticals versus move and delete them
5. Whether all of Jesús’s group follows the same post-scan organization as the observed technician
6. How other groups using the scanner handle storage and transfer
7. Whether researchers later rename, export, convert, or further reorganize the files
8. Whether there is any common conversion/export step worth automating

## Current best summary of the workflow

1. User books the instrument and briefly describes the sample.
2. User starts the software on the dedicated computer.
3. Data are saved directly into the **day’s folder in Gopticals**.
4. Each scan is named using a convention built from two standardized fields plus one or more user-defined fields, all separated by underscores.
5. User configures the scan and runs acquisition.
6. Each scan produces a single **.czi** file in the day folder.
7. Files are reviewed after scanning; some may be deleted immediately or later depending on user/group practice.
8. In at least one observed workflow, retained files are manually copied from Gopticals to an **external drive** because the group server is too small.
9. On the receiving storage, files may be reorganized into a separate manual project folder structure.
10. Files are then deleted from Gopticals.

---

## Integration with gjesus3

AxioScan 7 is **live in gjesus3 true production** (instrument code `ZWSI`,
ecosystem `MICROSCOPY`). The `.czi` files described above are ingested with the
AxioScan-7 per-instrument template; the path from the scanner to a searchable,
project-linked acquisition is:

1. **Stage.** Slides are scanned to the `goptical` day folder
   (`\\goptical\GOpticalUsers data\AxioScan\<YYYYMMDD>\`) as described above. That
   day folder (or a copy of it) is the ingest **staging_dir**. Historical batches
   are pulled from the archived `goptical` source catalogued in
   [`../historical_data_archives.md`](../historical_data_archives.md).
2. **Ingest.** Run `tools/ingest_raw.py` with a per-batch config copied from the
   AxioScan template
   [`tools/templates/instruments/axioscan7.yaml`](../../tools/templates/instruments/axioscan7.yaml)
   (set `staging_dir` + `notes`, set the researcher), **or** use the frozen GUI
   **`gjesus3_ingest.exe`** (microscopy page). The template parses the §4 filename
   convention into `discovered.*` chunks (`group_code` / `operator` / `project` /
   `sample_short` / `stain` / `magnification`) and pulls the 21 `czi_*` fields from
   each file. **The template header lists every `discovered.*` field available —
   it is the operator's reference card; this note does not duplicate it.**
3. **Land in `/raw/` + registry.** Each `.czi` is deposited under
   `/raw/MICROSCOPY/`, gets an immutable `metadata.json` sidecar (including the
   auto-filled `subject:` block — for a tissue slide the *source animal* is looked
   up in the animal-facility DB from the `project` + `sample_short` chunks — plus a
   per-batch `condition:` block), and one row per acquisition is appended to
   `registries/registry_raw.csv`. The subject lookup is **non-blocking**: a DB miss
   queues to `registries/pending_subject_metadata.csv` and the acquisition still
   ingests.
4. **Hard-link into a project.** The acquisition is hard-linked into its project
   under `/projects/<proj>/raw_linked/` (project named from the
   `AE-biomeGUNE-<project>` animal-project code). A hard link opens like the real
   file but takes no extra space.
5. **Finder.** The Finder (`registries/index.html` global + the project's own
   `index.html`) auto-refreshes, so the slide is immediately searchable by sample,
   source animal, stain, project, etc.

This is the system path that addresses the **risks/weaknesses** flagged above
(single-copy external drives, manual handoff, no structured metadata): once
ingested, the slide has a durable home in `/raw/`, a registry row, structured
metadata, and a project link. The naming convention in §4 is what makes the
auto-extraction work — it is the highest-leverage thing the operator controls.

For the full operator workflow see [`START_HERE.md`](../../START_HERE.md) and
[`tools/INGEST_CLI.md`](../../tools/INGEST_CLI.md); for the system-wide rationale
see [`equipment/INDEX.md`](../INDEX.md) and
[`13_GJESUS3_ROLE`](../../mfb-rdm-docs/13_GJESUS3_ROLE.md).

> 🕗 The few filename-only fields that the `.czi` doesn't carry (e.g. per-slide
> cohort overrides) are intended for the **study-level** project metadata area
> (`/projects/<proj>/metadata/<acq_id>.json`), which is **planned, not yet
> deployed** (Phase 4 — see [05_PROJECTS §3](../../mfb-rdm-docs/05_PROJECTS.md) and
> [`tasks/BACKLOG.md`](../../tasks/BACKLOG.md)).

---

## Next step

**Get access to the Gopticals drive and directly inspect/test the workflow.**

That should answer the remaining technical questions, especially:

- exact path structure (identified RT 20260506)
- actual .czi metadata contents
- what can be extracted or automated

This will support the next practical goal:

- helping semi-automate the process
- moving storage and organization toward **gjesus3**
- aligning this data source with similar optical microscopy / histology workflows, including the **Cell Observer**

