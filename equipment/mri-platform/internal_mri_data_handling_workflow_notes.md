# Internal MRI workflow notes

## Scope

These notes summarize the current observed and documented workflow for use of the **internal MRI** facility at CIC biomaGUNE, with emphasis on **data handling and storage** rather than imaging technique, anesthesia, animal handling, or scientific interpretation.

**Source basis:**

- written protocol (in Spanish) shared by an organized user from Jesús's group (cardiac/flow MRI, Bruker BioSpin Cardiac_Flow_Mice)
- walkthrough discussion with that user (rough notes poor in some places)
- contextual notes about the platform manager's stated preferences for where acquisition and pre-processing should happen
- forward-looking strategy discussed regarding scripted ingestion to **gjesus3**


**Relationship to other instruments:**
This is a different class of instrument from the Axio Scan 7 and Cell Observer (preclinical MRI rather than optical/histology microscopy), but the **data management problem is the same**: getting raw and pre-processed acquisition data off an instrument-controlled environment into a useful, organized, retainable form. The pattern here has interesting similarities to the **Cell Observer** in that data lives first on an instrument-local computer and is transferred manually, but the platform-control model is much stronger.

---

## Purpose of this note

Capture, in a simple and updateable form, how internal MRI data are:

- acquired
- pre-processed locally (reconstruction, DICOM export, NIfTI conversion)
- transferred off the instrument via FTP
- named
- organized by the receiving researcher
- further processed (splits, segmentation) downstream

It also documents the **forward strategy** for inserting a scripted ingestion step that pushes pre-processed data toward **gjesus3** under platform-manager review.

No conclusions are drawn here beyond documenting the workflow, the strategy, and identifying open questions.

---

## Main distinguishing features vs. Axio Scan 7 and Cell Observer

The biggest differences from the optical microscopy workflows are:

1. **Two physical instruments**, one user-facing computer for the 7 T system and **two** user-facing computers for the 11.7 T system (a separate acquisition computer and a separate processing computer).
2. **Multiple ParaVision versions** in concurrent use: **v6, v7, and v3.6** (where v3.6 is, despite the lower version number, actually the newest line). The data-handling steps are generally similar across versions, but folder layouts and exact behaviors may differ.
3. **Strong platform-manager control** over where data live. The platform manager **actively discourages network use by end users**. Network drives are deliberately **not mounted** on the local instrument machines, and users are not taught how to mount them. This is intentional: it forces data to remain on the local machines under the platform manager's control.
4. **FTP-based retrieval**. To get data off, users must connect from a separate work computer using an FTP client, typically **FileZilla**, with credentials provided by the platform. The acquisition machines themselves are not used as transfer endpoints by the user.
5. **Local pre-processing is encouraged**. The platform manager prefers acquisition and initial processing to happen on the local machines, again so the data and the intermediate steps stay under platform-manager-controlled environments.
6. **Output is multi-format**. The pipeline goes from native ParaVision datasets → reconstructed images → exported **DICOM** → converted **NIfTI** (.nii / .nii.gz). The user-facing end products are typically DICOM and NIfTI, not the native ParaVision format.

These differences also create a **natural insertion point** for a future managed-ingestion script (see Forward strategy section).

---

## High-level workflow

### 1. Booking, animal preparation, and instrument startup

Users book the instrument via the standard mechanism (not the focus of these notes).

Before acquisition, users perform:

- isoflurane anesthesia induction
- placement of the animal on the heated MRI bed
- antenna / coil placement and tuning (Wobble adjustment)
- placement of cardiac and respiratory gating electrodes (for cardiac / flow work)
- verification that ECG and respiration gating are sufficiently in sync before scanning

These are operational rather than data-handling steps, but they affect what acquisition metadata will be captured (gating, BPM, etc.).

The user starts the relevant **ParaVision** software (v6, v7, or v3.6 depending on machine and configuration) on the dedicated local computer.

---

### 2. Study creation and study naming

In ParaVision, the user creates a **new study** and enters an identifier that is required to appear **three times** in the study registration form:

- **Animal ID**
- **Animal Name**
- **Study Name**

The platform-wide identifier structure observed is:

```
jrcYYMMDD_mXX_PROJECT
```

Where:

- `jrc` = the group/PI code (Jesús Ruiz-Cabello / MFB group)
- `YYMMDD` = the acquisition date in year-month-day
- `mXX` = the animal number (typically two digits; can be one)
- `PROJECT` = a project code, often a 4-digit number such as `0525`, which is the **official approved project number** (e.g. an animal ethics / regulatory project ID)

Underscores are the field separator.

Examples observed: `jrc250527_m150_0522`, `jrc241001_m105_0522`, `jrc20231108_m1_1422`.

Some observed identifiers use a 4-digit year (`YYYYMMDD`) instead of `YYMMDD`. Both forms appear in real folders.

This naming was reinforced by the platform manager via email after a recent platform meeting, and users have been asked to apply it consistently across their archives. The same convention is used **for storage** as well as for the in-software study name, i.e. the folder and the study name reflect the same identifier.

---

### 3. Acquisition

Acquisition proceeds through a structured cardiac-flow protocol (for the documented case) involving:

- Localizer
- Axial pure
- 4-chamber
- Long axis LV
- Cine 4-chamber
- Cine slices (multiple, stepping through the heart at 0.8 mm slice offsets)
- Localizer for the pulmonary artery
- Cine MPA (pulmonary artery)
- Velocity map (flow, with VENC setting)

The exact set of acquisitions varies with the study. The relevant data-handling consequence is that **a single study contains many sub-acquisitions** (E1, E2, ... E16, etc., in ParaVision's "Examination Entry" numbering), and these will all live together in the ParaVision dataset for that study.

---

### 4. Local pre-processing on the instrument computer

Once acquisition is complete, the user performs several pre-processing steps **on the local machine**, encouraged by the platform manager.

#### 4a. Reconstruction (manual, user-controlled)

ParaVision behavior observed:

- The **original** acquisition is reconstruction `/1`.
- ParaVision automatically creates a duplicate / auto-reconstructed version as `/2`.
- The user then manually performs their own reconstruction, which becomes `/3`.
- The user typically **uses `/3`** and **deletes `/2`** (and sometimes the `/1` auto-products they don't need).
- If there is a mistake in the user-controlled reconstruction, the used version may end up as `/4` or `/5`.

So, in practice, **the user-trusted reconstructions are typically the `/3` series**, and the other indices are intermediate or duplicate states that the user is willing to discard. This is an important pattern: the "real" data is not always the first reconstruction; it is the user-curated one.

For Cines and Cine MPA, the user also re-runs reconstruction with heart-rate (BPM) and respiration-rate values matched to that animal, to improve image quality. The mean BPM across cines may be entered for the Cine MPA reconstruction.

#### 4b. Export to DICOM

After reconstruction:

- The user right-clicks the selected study/animal in ParaVision and selects **Export to DICOM**.
- The DICOM files land in a known structured location on the local machine. The observed path involves the platform user's directory (`nmr > jump2data` on the 7 T machine, with subfolders per ID).

#### 4c. Conversion to NIfTI

From the DICOM folder for a given animal:

- The user opens a terminal in that folder.
- The user runs the shell script `tools.all2nifti.sh`.
- This produces **NIfTI** files (`.nii` / `.nii.gz`) in the same folder.

NIfTI is the format the user actually analyzes downstream. **DICOM is generated as an intermediate**, not as a long-term analysis target — though it is retained alongside the NIfTI.

Open question: it is **not yet confirmed** whether `tools.all2nifti.sh` is identical on the 7 T and 11.7 T machines, and across ParaVision v6 / v7 / v3.6. The user spoken to mostly works on the 7 T (ParaVision 7), but most of Jesús's older data is in **ParaVision 6**. Differences should be expected.

---

### 5. Transfer off the instrument via FTP

The user goes to a separate work computer on the network. Network drives are **not mounted** on the local instrument machine for the user. Instead:

- The user opens **FileZilla**.
- Connects to the relevant MRI server (the 7 T host has a stored site with the credentials already configured; protocol is SFTP).
- Navigates to the project's folder on the server: `/<group-folder>/MRI/<user-folder>/...`.
- Inside the user folder, datasets are listed by an internal naming scheme that includes timestamps and the JRC study identifier, for example: `20250528_164715_jrc250528_m161_0522_1_1`.
- The user selects the dataset(s) of interest and downloads them as complete folders to their work computer.

Note on credentials: the FTP credentials are documented in the user-facing protocol (server, user, password). This is the standard mechanism the platform expects.

Observed practical detail: ParaVision 6 and ParaVision 7 each have their own top-level folder on the server, because the two versions store data differently. Most of Jesús's group's **historical MRI data is under the ParaVision 6 folder**; the user spoken to now works **from the ParaVision 7 folder onward**. ParaVision 3.6 (newest) has not been characterized here yet.

---

### 6. Researcher-side folder organization (observed practice)

On the receiving side (the user's work environment, currently a group drive accessed from her desktop as something like `Y:\MRI\...`), the documented user organizes downloaded data by **project, then by month, then by animal**.

The general pattern:

```
MRI/
  Proyecto_<PROJECT>_<OptionalContext>/        e.g. Proyecto_0525_London
    <Month_Year_or_YYYYMM>/                    e.g. 2025-02 or "Feb_2025"
      <jrcYYMMDD_mXX_PROJECT>/                 the animal-specific folder
        ...downloaded ParaVision dataset...
        NiFTi_jrcXXXX/                         NIfTI outputs
        ...DICOM exports...
        Splits_Proyecto_<PROJECT>/             generated by Split_rat_executable.exe
          <jrcYYMMDD_mXX_PROJECT>/             per-animal splits
            Time_1_..._jrcXXXX_m_PROJECT_1_1.mhd
            Time_1_..._jrcXXXX_m_PROJECT_1_1.raw
            ...
            Segmentation_time1_m1_<PROJECT>.nii.gz   ITK-SNAP segmentations
            ...
```

Observed and confirmed elements:

- **Project as top-level folder.** The 4-digit project code is the anchor. The user pointed out that not everyone (including the PI) remembers the project number, so it can be useful to include the more human-recognizable animal/group context alongside the project number in the folder name.
- **Month grouping below project.** This is used because the user's experiments typically run on a roughly monthly cadence — animals are imaged, the experiment finishes, and there is a natural calendar boundary. It is therefore an experiment-cycle anchor more than a pure calendar tool.
- **Per-animal folder named by the full JRC identifier.** This matches the in-software study name and the file naming convention.
- **NIfTI in its own subfolder per animal**, often named `NiFTi_jrcXXXX`. If the splits step fails because the NIfTI folder is not named in the expected way, the user renames it.
- **A `Splits` folder is generated by a local executable** (`Split_rat_executable.exe`) run from `Y:\MRI\` (the user's group-drive view). The executable consumes the NIfTI folder for an animal and produces a per-time-point set of `.mhd`/`.raw` files used for cardiac segmentation. If the Split step fails, a documented workaround is to copy the Split folder to the desktop and regenerate it.
- **Segmentations live next to the images they describe.** The user stores ITK-SNAP segmentations (`.nii.gz`) in the same animal folder alongside the image data. This is a deliberate choice: "if you have to look for the segmentations, the images, they are all in the same place."

Notes / interpretations:

- The user does this organization manually. It is **not the result of a platform-wide rule** — it is one well-organized researcher's personal convention. Whether other group members organize the same way is **not confirmed**.
- The user does not consider all of the dataset content important. After download, **only a small subset of the acquisitions is actually used** downstream (typically a small number of cines and the Cine MPA + Velocity Map, plus possibly the localizer/4-chamber as positioning references). The `PData` subfolders are typically erased. The user is interested in **image files specifically**.

---

### 7. Downstream analysis (out of scope for ingestion, but documented for context)

For completeness:

- **Cardiac volume analysis** uses the Split outputs (`.mhd`/`.raw`) opened in ITK-SNAP. The user segments LV (Label 1) and RV (Label 2) on each time point, exports volumes, and tracks them in Excel. A sanity check is applied: LV vs RV stroke-volume difference should be < 10%.
- **Flow analysis** uses the NIfTI Cine MPA loaded in ITK-SNAP, with the Velocity Map loaded as an additional image. Segmentations are saved as `.nii.gz` next to the images.

This downstream analysis is not the target of the ingestion design, but it is worth knowing because:

- the segmentations are user-generated derived data and live alongside raw/pre-processed data, and
- the Splits/segmentations folder is part of what a researcher would expect to keep findable long-term.

---

## Systematic naming convention (parsable)

> **Added 2026-05-22 as the framework for `discovered.*` auto-discovery and `link_filename:` templating.** The MRI workflow uses a much more systematic naming convention than microscopy — folders and filenames are largely set by the instrument or by platform-wide rules rather than by individual operator preference. That systematic structure lets us *parse* a lot of metadata directly from paths, which then becomes available to ingest YAML configs.

### The full path structure (server side)

```
<data dir>/<project folder>/<protocol number>/pdata/<reconstruction number>/
```

| Level | What it represents |
|---|---|
| `<data dir>` | The platform's data root on the acquisition machine (e.g. `/opt/PV-7.0.0/data/nmr/`). Mirrored verbatim by FileZilla pulls. |
| `<project folder>` | One animal session (ISA "study"). Full structure broken down below. |
| `<protocol number>` | One ParaVision examination — a scan with a distinct protocol. ACQ-ID maps here (ISA "assay"). |
| `pdata/<reconstruction number>` | One reconstruction of that protocol. The user-trusted recon is typically `/3` (see §4a above). |

### `<project folder>` structure

The project folder name is set by the platform / instrument software:

```
<YYYYMMDD>_<time code>_<group and date>_<short sample id>_<short project id>_<group and date>_<short sample id>_<short project id>_1_1
```

The first `<YYYYMMDD>_<time code>` prefix is the *FTP server-side* timestamp of when the folder was created. The remaining components are duplicated (`_<group and date>_<short sample id>_<short project id>` appears twice) plus a trailing `_1_1` — that's a quirk of how the platform writes the folder name, not a meaningful pattern.

Per-component breakdown:

| Component | Meaning | Example |
|---|---|---|
| `<group and date>` | Compound: `<group PI initials><YYYYMMDD>`. *Expected to be no underscore between them.* See ambiguity note below. | `jrc251016` or — observed — `jrc_251016` |
| `<short sample id>` | Either `<animal type><short animal id>` for animal work, OR an arbitrary free-text label like `phantom xyz` for QC/QA. `<animal type>` is `m` (mouse) or `r` (rat); `<short animal id>` is a numeric inside the protocol. | `m17` (mouse #17), `r5`, or `phantom_xyz` |
| `<short project id>` | Four-digit **animal-protocol code**. This is *not* the funded-project id. The protocol is required for animal-use compliance. Sometimes arbitrary (for QC/QA when no animals are used). | `0424` |
| `<group PI initials>` | Lowercase initials of the group's PI. For MFB: `jrc` (Jesús Ruiz-Cabello). | `jrc` |

The **true unique animal id** is the composite: `<short project id>_<short animal id>` — e.g. `0424_17` means "animal #17 under protocol 0424." Two different protocols can both have an animal #17; only the composite is unique.

### The `jrc` vs `jrc_` ambiguity

Observed in real data: sometimes the folder name has `jrc251016_m17_0424` (no underscore between PI initials and date — the intended convention) and sometimes `jrc_251016_m17_0424` (with an underscore). The latter breaks naive split-on-underscore parsing.

**Round 6 handles both forms** via the `regex:` extractor in `filename_parse` (see `tools/templates/instruments/mri_bruker.yaml`):

```
(?P<jrc_id>jrc_?\d{6,8}_m(?P<animal_num>\d+)_(?P<project_code>\d{4}))
```

The `jrc_?` matches `jrc` or `jrc_`; `\d{6,8}` covers 6-digit (`YYMMDD`) or 8-digit (`YYYYMMDD`) dates. The named groups `jrc_id`, `animal_num`, `project_code` become `discovered.*` for use elsewhere in the YAML config.

A **long-term fix** is to ask the platform manager to standardise the convention; that's tracked as future work in `tasks/tasks.md`.

### Terminology confusion: "project" in MRI vs Nuclear Imaging

The word "project" is overloaded across the institute:

- **In internal MRI**: the four-digit `<short project id>` in the folder name is the **animal-protocol short id** — a regulatory artifact (the approved animal protocol the work is being done under).
- **In internal Nuclear Imaging**: the `<series id>` in the folder structure is the **funded-project id** — a financial-administrative artifact (the grant or funded project the work charges against).

These are different numbers, and users sometimes conflate them in conversation. The animal-protocol id often *relates to* a funded project (work under a grant is usually approved as one animal protocol per project), but the numbers don't align.

For gjesus3 round 6 we use the **animal-protocol short id** as the project `short_name` (`ae-biomegune-NNNN`). For the future NI round, the funded-project id will play a similar role. The terminology distinction is captured in [`equipment/nuclear-imaging/internal_ni_data_handling_workflow_notes.md`](../nuclear-imaging/internal_ni_data_handling_workflow_notes.md).

### What's parsed today

The round-6 ingest config exposes these `discovered.*` fields per acquisition (from the path + regex + ParaVision JCAMP-DX extractor):

- From `filename_parse` regex on the study folder name: `discovered.jrc_id`, `discovered.animal_num`, `discovered.project_code`.
- From standard auto-discovery: `discovered.folder_name` (the exam folder basename, i.e. the protocol number).
- From `paravision_metadata.py` parsing of `subject` + `acqp` + `method` + `visu_pars`: ~20 `discovered.mri_*` fields including `mri_exam_number`, `mri_recon_indices`, `mri_sequence_name`, `mri_acquisition_datetime`. See [`mri_bruker.yaml`](../../tools/templates/instruments/mri_bruker.yaml) for the full reference card.

---

## Round-6 v2 reshape (2026-05-27)

Following round-6 v1 (2026-05-22) and the NI v2/v2.1 work, the on-disk MRI layout was reshaped to mirror NI's slim convention. The v1 design had the same problems v1 NI did: aux files duplicated to disk under `acquisition_aux/`, DICOMs buried in `reconstructions/pdata_<idx>/dicom/MRIm<NN>.dcm`, and the default `reconstructions: [3]` silently dropped image data for exams that lacked pdata/3.

### What changed in v2

| Aspect | v1 (2026-05-22) | v2 (2026-05-27) |
|---|---|---|
| Aux file storage | `acquisition_aux/{acqp, method, visu_pars, fid, pulseprogram, specpar, uxnmr.*}` on disk | Parsed JCAMP-DX content lives only in `metadata.json.mri._raw_metadata`; source files stay on the platform acquisition machine |
| Per-recon non-DICOM | `reconstructions/pdata_<idx>/{2dseq, visu_pars, reco}` on disk | Parsed `visu_pars` + `reco` content in `metadata.json.mri._raw_metadata.pdata.<idx>`; `2dseq` (binary image) NOT copied (DICOMs derive from it; the platform retains the binary) |
| Data folder name | `reconstructions/pdata_<idx>/dicom/` | `<ACQ-ID>.data/` (flat — mirrors NI's `<ACQ-ID>.data/` and microscopy's `<ACQ-ID>.czi`) |
| DICOM names | Source `MRIm01.dcm`...`MRIm15.dcm` per pdata/<idx>/dicom/ | Renamed flat across recons: `recon<idx>_frame<NN>.dcm` (e.g. `recon1_frame01.dcm` ... `recon3_frame15.dcm`) |
| Default `reconstructions:` | `[3]` (user-trusted cardiac-flow recon) | `all` — DICOMs are tiny under v2; preserve everything by default. Operator can override to `[3]` for cardiac-flow workflows |
| DICOM UIDs in sidecar | Not captured | `StudyInstanceUID` / `SeriesInstanceUID` / `SOPInstanceUID` first in per-DICOM `headers` (critical for XNAT/PACS interop) |
| .lnk shortcut target | The ACQ folder itself | The `<ACQ-ID>.data/` subfolder — Explorer opens directly to the DICOMs, matching the microscopy `.lnk → .czi` semantics |
| Sidecar `reconstruction.by_index.<idx>` | High-level summary (`methods`, `frame_labels`) | Per-DICOM `dicoms[]` list with `dst_basename` + `src_relpath` + full curated headers (UIDs + MRI-specific tags `MagneticFieldStrength`/`EchoTime`/`RepetitionTime`/`FlipAngle`) |

### No-DICOM acquisition handling

A real-world gap surfaced during the v2 source-data inventory: **3 of 7 round-6 source projects had ZERO DICOMs** because their researchers (students working under Jesús) hadn't run Bruker's ParaVision DICOM exporter before the data was FTP'd off. The raw `fid` files and `2dseq` binaries were present, but the per-frame `.dcm` files in `pdata/<idx>/dicom/` were missing entirely.

**Round-6 v2 decision:** ingest these acquisitions anyway, with empty `<ACQ-ID>.data/` folders. The `metadata.json.mri:` block is fully populated from the parsed JCAMP-DX (subject, acquisition parameters, geometry, per-recon `visu_pars`/`reco`) — researchers can still query the acquisition metadata. The `mri.reconstruction.by_index.<idx>.dicoms[]` list is empty.

**Recovery path:** the operator (Data Mgmt Lead) flags the no-DICOM acquisitions in the round-6 report and either (a) asks the originating researcher to re-run Bruker's exporter, then re-runs the ingest (idempotency dedup means only the freshly-available DICOMs get copied; placeholder gets converted in place), or (b) waits for the future FID→DICOM regeneration capability (tracked in `tasks/tasks.md §3.1`).

**Why not skip the exam outright?** The acquisition is still real — the animal was scanned, the parameters were captured. Registering it preserves the audit trail and lets a later DICOM conversion fill in the image data without needing to re-acquire registry information. Empty `.data/` is honest about the gap.

**Detection in the ingest pipeline:** `copy_mri_paravision` enumerates `pdata/<idx>/dicom/*.dcm` for each selected recon. If no `.dcm` files are found anywhere across all selected recons, the function emits a clear log line ("no DICOMs — student didn't run Bruker exporter") and proceeds with the empty-`.data/` placeholder.

### FID→DICOM regeneration future-work

Bruker's GUI-based ParaVision DICOM exporter is closed-source; there is currently no open-source Python library that converts raw `fid` (k-space) data directly to DICOM. (Tools like `bruker2nifti` and `brkraw` go to NIfTI, not DICOM. `dcm2niix` runs the opposite direction.) The future-work item in `tasks/tasks.md §3.1` is a 2-4 week research project: read the binary `fid` format, perform Fourier reconstruction, build DICOM headers from the JCAMP-DX aux files, serialize using pydicom. Until that lands, no-DICOM acquisitions remain placeholders requiring researcher action.

The architecture supports this transition with no further changes — when the FID→DICOM capability ships, it would write `recon<X>_frame<NN>.dcm` files into the existing empty `.data/` folder; re-run the ingest to pick them up via idempotent dedup.

---

## Documented workflow vs. observed workflow

### Documented platform expectations (from protocol + email reminders + walkthrough)

- Acquisition and initial processing happen on the **local instrument computer**.
- Network drives are **not mounted** on the instrument computer; users must FTP off.
- Data identifiers follow the `jrcYYMMDD_mXX_PROJECT` convention.
- The user-controlled reconstruction (typically `/3`) is the trusted version.
- Export proceeds through DICOM, then NIfTI via `tools.all2nifti.sh`.
- Retrieval is via FileZilla using documented credentials.

### Observed practice (in one organized user's workflow)

- Matches the documented expectations for acquisition, reconstruction discipline, DICOM/NIfTI conversion, and FTP retrieval.
- **Adds** a personal organization scheme on the receiving side: project → month → animal, with NIfTI, DICOM, splits, and segmentations all kept together per animal.
- **Adds** the `Split_rat_executable.exe` step locally, which generates the segmentation-ready dataset for cardiac volume analysis.

### Important caveat

This is **one researcher's practice**. It is well-organized, but it is not necessarily representative of how other group members handle their data. The user explicitly said she does not know how others organize their MRI data.

---

## Forward strategy (not current practice, but in scope to document)

The medium-term aim is to insert a **managed ingestion step** that:

1. Runs the existing pre-processing locally (reconstruction discipline, DICOM export, NIfTI conversion).
2. Pushes the resulting structured output (NIfTI, DICOM, identifier-conformant folder layout) to **gjesus3**.
3. Does this under the **platform manager's review and guidance**, so it remains compatible with platform control of the source environment.

The platform manager has indicated that, with his guidance and review, **a script of this kind can run from the local machine** for the users. This is what makes a managed ingest realistic here — unlike a fully user-driven approach, it does not break the platform-manager-control model.

### Phased plan

Phase 1 — **Understand from notes** (current).
Document the existing workflow as fully as possible from the protocol and discussions, including ParaVision-version differences.

Phase 2 — **FTP example folders for offline testing.**
Use the existing FileZilla credentials to pull representative example datasets to a controlled location. Examine the actual on-disk structure, including for ParaVision 6, ParaVision 7, and (if accessible) ParaVision 3.6.

Phase 3 — **Script-controlled FTP retrieval.**
Test programmatic / scripted use of the FTP connection to retrieve folders, mirroring what FileZilla does. This avoids touching the local machine until the retrieval logic is well understood.

Phase 4 — **Local ingest script.**
Only once Phases 1–3 check out: under platform-manager review, write a script that runs locally on the instrument machine, performs (or wraps) the existing DICOM and NIfTI conversion steps, applies the naming/structural conventions, and pushes the curated output to **gjesus3**.

This is explicitly **not** about replacing or bypassing the platform manager's control. It is about adding a controlled bridge from the local-controlled environment to a longer-term, group-controlled archive.

---

## Main data-handling points identified so far

- The internal MRI generates **multiple file formats per study**: native ParaVision data, reconstructed datasets (multiple reconstruction indices), exported **DICOM**, and converted **NIfTI**.
- The **user-trusted reconstruction is typically `/3`**, not the first one ParaVision produces. Automated ingestion must respect this — picking up the wrong reconstruction would silently capture data the researcher does not actually use.
- **DICOM is intermediate**; **NIfTI is the analysis target**.
- The conversion script is `tools.all2nifti.sh`, run in a terminal at the DICOM folder.
- **Network drives are not mounted on the local machine**; data movement off the instrument depends on **FTP from a separate computer** (FileZilla).
- Two physical systems (**7 T** and **11.7 T**), with **three ParaVision versions** (v6, v7, v3.6) in use. Folder conventions and export behaviors may differ.
- Naming convention is platform-wide: **`jrcYYMMDD_mXX_PROJECT`**, used both as study name in ParaVision and as folder name.
- The project code is the **official approved project number**, but it is also useful organizationally for the researcher. Pairing the project number with a more human-recognizable context (e.g. animal cohort name) is sometimes done to help others (including the PI) recognize the project.
- On the receiving side, organization is **manual** and currently **not standardized across the group**. The observed pattern is project → month → animal, with NIfTI, DICOM, Splits, and segmentations together per animal.
- The Splits/segmentation pipeline produces additional derived files that the researcher expects to find **alongside** the imaging data.
- Most of Jesús's group's **historical MRI data lives under the ParaVision 6 folder** on the server; newer data is under ParaVision 7.

---

## Risks / weaknesses visible from the workflow record

These are not deep analysis points, but they are practical features that should remain visible:

- Heavy reliance on **manual steps** for reconstruction selection, DICOM export, NIfTI conversion, and download.
- **Reconstruction-index ambiguity**: the "real" data is the user-curated `/3`, but automated tools that assume `/1` or "latest" would pick up the wrong thing.
- **ParaVision version drift**: v6, v7, and v3.6 may export differently; a script written against one will not automatically work for the others.
- **No standardized receiving-side folder structure** across the group.
- **Single source of truth on the local machine** until FTP'd off, with no formal redundancy step.
- Derived analysis outputs (Splits, segmentations) live alongside images, which is good for findability but means archival ingestion needs to handle a mixed set of file types per animal folder.
- **One small subset of acquisitions is actually used** by the researcher (typically a few cines and the Cine MPA + Velocity Map). Without explicit user marking, an ingest script would have to either take everything or learn which sub-acquisitions matter.
- Platform-control model means users **cannot easily move data themselves to a network-mounted archive**. Any solution that requires user mounting will not work.

---

## Open questions / items to update later

1. Exact differences in folder layout and export behavior between **ParaVision 6, 7, and 3.6**.
2. Whether `tools.all2nifti.sh` is identical across the 7 T and 11.7 T machines and across ParaVision versions.
3. Where exactly DICOM exports land on each machine (the 7 T case mentions `nmr > jump2data`; 11.7 T not yet verified).
4. Whether other users in Jesús's group follow the same receiving-side organization (project → month → animal) or use a different pattern.
5. Whether the `Split_rat_executable.exe` workflow is in use beyond this one researcher.
6. Whether the segmentations-next-to-images convention is general practice or specific to this user.
7. Whether ParaVision metadata can be reliably extracted programmatically (heart rate, respiration rate, sequence parameters, gating, slice geometry, VENC) to populate an ingest manifest, rather than relying on filenames.
8. What proportion of users routinely delete `/1` and `/2` reconstructions before exporting, vs. leaving them.
9. Whether non-cardiac MRI workflows (anatomy, perfusion, diffusion, spectroscopy, etc.) follow a similar pattern or diverge meaningfully.
10. How long users typically keep data on the instrument server before relying on their own copies, and whether the platform manager has a retention policy on the local machines.
11. What credential / access model is acceptable for a script running locally under platform-manager review (read-only? push-only? what target paths on gjesus3?).
12. Whether the ParaVision 3.6 line has its own server folder structure and FTP target.

---

## Current best summary of the workflow

1. The user prepares the animal and starts **ParaVision** on the relevant local instrument computer (7 T or 11.7 T; ParaVision v6, v7, or v3.6).
2. The user creates a study with the convention **`jrcYYMMDD_mXX_PROJECT`** entered three times (Animal ID, Animal Name, Study Name).
3. Acquisition proceeds through a structured protocol (e.g. cardiac flow: localizer → axial → 4-chamber → long axis → cines → Cine MPA → velocity map).
4. The user performs **manual reconstruction** in ParaVision. Auto-generated reconstructions (`/1`, `/2`) are typically discarded; the user-trusted reconstruction is typically **`/3`**.
5. The user **exports to DICOM** via right-click → Export to DICOM.
6. The user opens a terminal in the DICOM folder and runs **`tools.all2nifti.sh`** to produce NIfTI outputs in the same folder.
7. From a separate work computer, the user opens **FileZilla**, connects to the MRI server using stored credentials, navigates to their user folder under the appropriate ParaVision-version directory, and **downloads** the animal folders of interest.
8. On the receiving side, the user organizes the downloaded data **manually** under a project / month / animal hierarchy on her group-drive view.
9. For cardiac volume work, **`Split_rat_executable.exe`** is run locally to produce per-time-point split datasets (`.mhd`/`.raw`) in a `Splits` subfolder.
10. The user performs segmentation in **ITK-SNAP** (LV/RV for cardiac, flow ROIs on Cine MPA + Velocity Map for flow), saving segmentations **next to the images** in the same animal folder.

---

## Next steps

The next useful steps are:

1. **FTP some example folders** off the 7 T (and ideally the 11.7 T) using the existing FileZilla credentials, to characterize the on-disk structure under each ParaVision version directly.
2. **Inspect ParaVision metadata** (reconstruction indices, sequence parameters, gating values) on those example folders to see what can be extracted automatically and used to populate an ingest manifest.
3. **Confirm the receiving-side conventions** with at least one or two more group members to understand whether the project → month → animal pattern is general or specific to this one researcher.
4. **Design the managed-ingest script behavior on paper** before writing it: target file types (NIfTI + DICOM + Splits + segmentations?), naming, folder layout on **gjesus3**, what gets dropped (e.g. `/1`, `/2` reconstructions; `PData`), and what gets preserved as authoritative raw.
5. **Coordinate with the platform manager** on the script's permissions, run conditions, and review process before any code runs on a local instrument machine.
