# Drive 3 (M. Jesús): its segmentations as curated-dataset candidates (part A3)

**Status:** 🔶 DRAFT for the coordinator, 2026-10-06. Read-only throughout: nothing was written to `J:\` (production,
`curated_datasets\` or the staged copy) or to `K:\`. **Nothing promoted, nothing registered.** Not committed (the coordinator
commits).
**Brief:** `HANDOFF.md` §7 (part A3) in this worktree; the hub's brief §6.7 and §8 step 7. Specs read:
[`12_CURATED_DATASETS`](../mfb-rdm-docs/12_CURATED_DATASETS.md) §3/§5/§6/§8, [`06_REGISTRIES`](../mfb-rdm-docs/06_REGISTRIES.md) §5,
the four promoted datasets `DS-SEG-0001…0004` (their `_dataset.yaml`, `provenance.csv`, `slice_map.csv`), and the
[`BACKLOG`](BACKLOG.md) item "the curated-datasets pilot returned 19 spec gaps".
**Evidence (regenerable):** `D:\projects\gjesus3\drive3_analysis\a3\`. **Scripts:** `tools\drive_staging\drive3\a3_*.py`;
`a3_run_all.py` re-derives every number below in about 5 minutes (resume mode) or about 25 minutes from nothing (`--fresh`).
**Units:** GB = 10⁹ bytes (the hub's "35.3 GB" for `Segmentaciones ITK SNAP` is 35.3 GiB = 37.9 GB). A **label** is a file
that marks structures on an image (a mask, an ROI set, an annotation). **Distinct** = distinct SHA-256: the drive holds many
labels several times, and a copy is the same label.

---

## Summary

### The five numbers that matter

1. **8,617 distinct labels (12,090 files on the drive) in 12 sets, about 2.7 GB.** Almost everything else the hub counted
   as "segmentation" is image data: 84.5 GB of per-phase "split" volumes (`.mhd`/`.raw`), 52.0 GB of NIfTI/MHA/Interfile
   image volumes and 7.9 GB of pig source DICOM. Of `Otros\Segmentaciones ITK SNAP`'s 41,728 files only 1,329 are labels.
2. **3,859 distinct labels (44.8 %) trace to valid production ACQ-IDs**, the 12 §6.2 test. Of these, **3,003 are cine stacks
   resolved by direct pixel comparison** (each slice of the image the label was drawn on is identical, up to intensity
   scaling, to one production DICOM frame: 173 stacks, 1,905 stack members, no exception), 369 trace to one acquisition,
   298 to a stack identified by geometry only (slice order unverified, the level `DS-SEG-0001` was promoted at), 189 to a
   pair of exams sharing one slice. **No two copies of a label ever traced to different acquisitions.**
3. **Age decides it.** Every label cohort scanned **2022–2024 traces at 83–100 %**; the **2019–2021** cohorts trace at
   **0–7 %**, because production does not hold those studies (4,677 labels trace to nothing). **94 of those absent
   studies are on this drive with the scanner's own DICOM**: ingesting them would make **1,923 labels traceable**
   (1,522 hand-traced, 401 model output). That is A1's R1, seen from the label side.
4. **One strong candidate and four smaller ones.** **CAND-A: 3,234 hand-traced left/right-ventricle cine masks**
   (3,066 not already curated), 189 sessions, 161 animals, 2,073 production acquisitions, 8 protocols, 2021–2024, all
   traced. Then: Massventricles masks 167, great-vessel flow ROIs 200, PET/CT organ masks 142, a 1519 LV-only set 59, and
   a 4-class endo/epi set 15. Drafts of `_dataset.yaml` + `provenance.csv` for each are in `a3\drafts\`.
5. **Overlap with what is curated:** **all 178 human-reader files of `DS-SEG-0004`** are on this drive (its reader B files
   are named `MJ_Segmentation_…` here), and 39 of `DS-SEG-0002`'s PMOD VOIs. Nothing is byte-identical to `DS-SEG-0001`
   or `-0003`. But **this drive holds the split volumes `DS-SEG-0001` believed deleted**: its slice order (published as
   unverified) checks out by pixels on all 8 sessions, 7 identical and `jrc211209_m85_1019` with slices 2↔3 swapped,
   which independently confirms `DS-SEG-0004`'s correction.

Two findings change how anyone should read these masks (§3). **The label values were never documented, and they do not
mean the same thing everywhere.** Measured geometry shows that the 0/1/2 maps are **LV and RV blood pools** (the open
question in `DS-SEG-0001/0003/0004`) everywhere **except** the 1519 cohort, where the same values mean **LV cavity / LV
myocardium**. And the 0–4 maps come in **two incompatible orders** (the ITK-SNAP endo/epi palette, and "Massventricles").
A dataset built by value set alone would mislabel hundreds of files.

### Decisions for Ryan (each with a recommendation)

| # | Decision | Recommendation |
|---|---|---|
| **S1** | **Start the curated-dataset process for CAND-A** (LV/RV blood-pool cine masks, 2021–2024)? | **Yes, in two steps.** Now: nothing beyond A2's placement (the masks go to their project folders as work in progress, 12 §3.2; drives 1+2 already put 2,053 drive-3 labels there). Then **one question round with M. Jesús** (§7, ten lines: who traced what, which version is final, confirm the label meanings), and promote as **one new dataset with the cohort on every row**, starting with the single-reader, pixel-verified cohorts: `1422` 2023 (283), `1019` 2022 (255 new), `0424` 2024 (179), `0522` 2022 (91), `0522` 2024 (75), `1422` 2024 (271, all `MJ`). Hold the geometry-only `0320` stacks (146) until the order question is answered. |
| **S2** | **Several masks for the same stack and phase** (984 of CAND-A's files have another version): `0522` 2023 is read twice, by `IRE` and by `MJ` (191 pairs, median Dice 0.84); `1121` 2022 has `Inicial` and `Revision` folders (212 pairs, median 0.84, including `Revision\Jesus` and `Revision\Hago todo de nuevo`). | **Keep both readers of `0522` 2023 as readers**, as `DS-SEG-0004` did: this is a second inter-observer set, eight times larger than `DS-SEG-0004`'s 24 pairs. **For `1121`, take `Revision` as final** only if M. Jesús confirms; then `Inicial` is a superseded draft (kept in the project folder, not curated). Never pick by guess (§5). |
| **S3** | **Label meanings, measured here, also answer open items of the promoted datasets**: "blood pool or myocardium?" (`DS-SEG-0001/0003/0004`), "what do the Massventricles values 1–4 mean?" and "are the two excluded files mis-named Massventricles?" (`DS-SEG-0004`). | **Send the evidence (§3, `a3_topology_summary.csv`) to the SegBioMed project**: these are its datasets and its decisions (D4/D5, 2026-10-05). Ask M. Jesús to confirm in the same round as S1. Change nothing in `curated_datasets\` from here. |
| **S4** | **`DS-SEG-0001` slice order**: this drive's split volumes verify all 8 sessions by pixels; `m85` confirms the 2↔3 swap that the prepared, unapplied `DS-SEG-0001` v1.1 corrects. | **Give it to SegBioMed** as independent evidence for their v1.1 decision, and as the means to set `slice_order_verified` on the other 7 (`a3_slicemap_check.csv`). |
| **S5** | **The pig pulmonary-artery set** (199 ROIs, 3 pigs, CNIC Philips Achieva 3T, Feb–Jul 2014, project "HEARDS"): no gjesus3 instrument, not traceable (0 %). Its source DICOM is on this drive (A1 R6 holds it pending this answer). | **Do not curate.** Keep the ROIs with their source images as project material (A2's holding folder) and add one line to A1 R6's question for M. Jesús: whose study it is and whether gjesus3 may hold CNIC data. Only if both answers allow it, the DTS24 precedent (external data, own X-code) would make the set traceable. |
| **S6** | **Model output**: the Vicomtech "PH_segmentation_tool" predictions (150, 2020–21) and the 2019 rat `Pred_`/`Postprocessed_` volumes (441). | **Do not curate** (they are not ground truth, and all trace to nothing). Keep them beside the tool (A2 D8: `Otros\PH_analysis_Segmentation_tool`, holding). Record that the tool's `Reference.txt` names its training animals: any future benchmark built from CAND-A must exclude them (training-set leakage). |
| **S7** | **PET/CT organ masks (CAND-E, 142)**: traced 100 % for 2022–2024 by the SHA-256 of the DICOM beside each mask, but the values 1–3 are named nowhere; 103 sit on sessions `DS-SEG-0002` already covers (its VOIs). | **Hold** until the analyst names the values. Then ask SegBioMed whether they become `DS-SEG-0002` v1.1, whose stated plan is NIfTI masks for the same sessions. |
| **S8** | **The fat masks** (181, `MRI grasas Irati`), **histology annotations** (38 NDP + 3 QuPath), **rat 0118 respiration masks** (95), **Amira lung** (1): 0 % today. | **No dataset.** The fat masks are a threshold (fat fraction ≥ 50 %) with morphology, run in a Colab notebook: derived analysis, not ground truth, and their fat-water exams are not in production. The annotated slides come from an Axioscan that is not ours (A1 R6). The 0118 masks wait on A1 R2. Place all of it as project material (A2). |

---

## Method, in one screen

1. **Inventory** (`a3_inventory.py`). From the manifest: every file of `Otros\Segmentaciones ITK SNAP` (all 41,728), and
   anywhere on the drive every label-capable format (`.nii`, `.nii.gz`, `.mha`, `.mhd`/`.raw`, `.hdr`, `.voi`, `.voistat`,
   ITK-SNAP `.label`, Amira, meshes, `.ndpa`, QuPath, the model `.h5`): 105,603 files. **Label versus image is decided by
   the voxels, never the name** (`a3_headers.py`: header plus value census of each of the 26,223 distinct NIfTI /
   MetaImage / Interfile files; integer-valued with at most 64 distinct values = label). Names lie in both directions:
   `MPAflow_m203_0619.nii.gz` is a mask, `Time10_m160_0619.nii.gz` is a mask, and `Cine_IG_FLASH_20_Proc1.nii.gz` is an image.
2. **Sets** (`a3_trace.py`): by structure, species, modality, tool and value scheme (§2), then by **cohort** (protocol ×
   year).
3. **Trace to production** (`a3_trace.py`, `a3_ncc.py`, `a3_imgmatch.py`, `a3_geostack.py`), strongest evidence first.
   **Unresolved is recorded with its reason; nothing is guessed.**
   - **SHA-256 of the source beside the label** (`prod_raw_sha256.csv`): PET/CT masks sit beside the Molecubes DICOM they
     were drawn on; their bytes and names equal production files.
   - **Byte-identical to a promoted `DS-SEG` label**: takes that dataset's ACQ-IDs.
   - **Cine masks**: drawn in ITK-SNAP on per-phase *split* volumes (`Time_<phase>_rat_<study>.mhd`, one 3-D stack built
     from 9–12 single-slice cine acquisitions, no scanner coordinates). As in `DS-SEG-0003/0004`, each split slice is
     cross-correlated against frame *t* of **every** production acquisition of the study (every reconstruction kept,
     8 in-plane orientations), at phases 1, 8 and 15. A slice is decided when one acquisition matches **pixel-identically**
     (normalised cross-correlation, NCC, ≥ 0.9999) and no other does. **The weakest decided slice in all 173 stacks
     scored 1.0000.**
   - **Masks beside NIfTI exam conversions** (`Cine_IG_FLASH_20_Proc1`, `Velocity_map_21_Proc1`): the label's dims and
     affine equal one conversion's, whose name carries the exam number (production `original_name` = `<study>/<exam>`).
     Where the folder names no study, the conversion itself is pixel-matched against the animal's production frames.
     Of 201 such images, **126 matched one production frame pixel-identically, and in all 126 the exam number in the
     file name equals the matched production exam** (an independent confirmation). 17 matched nothing (their exams are
     not in production) and 58 belong to animals with no production MRI.
   - **Stacks whose split volumes are not on the drive**: from the production sidecars, the IgFLASH cine acquisitions of the
     study, grouped by slice orientation, form **one contiguous 0.8 mm series with as many members as the mask has
     slices** (22 stacks). Membership is established, order is not: `order_verified = no`, the `DS-SEG-0001` level.
4. **Meaning of the values** (`a3_label_topology.py`): per file and slice, does each value touch the outside background,
   lie inside another value's outline, and how round is it (solidity)? See §3.
5. **Copies and versions** (`a3_versions.py`): byte copies are folded by SHA-256; different files for the same stack and
   phase are compared voxel by voxel (Dice).
6. **Overlap** (`a3_overlap.py`, `a3_slicemap_check.py`): SHA-256 against the four datasets, the four harvest deposits in
   `curated_datasets\_incoming\`, production `/raw/`, and drives 1+2's placements and holding folder; the datasets'
   slice maps against this drive's verified stacks.
7. **Drafts** (`a3_drafts.py`): one `_dataset.yaml` + `provenance.csv` per candidate, in `DS-SEG-0004`'s shape, written to
   `a3\drafts\` only.

---

## 1. Inventory

### 1.1 What the "segmentation" bytes are

| Top folder | Labels | Image volumes (NIfTI/MHA/Interfile) | Split volumes (`.mhd`/`.raw`) | Other |
|---|---:|---:|---:|---:|
| `Pili y Mili` | **2.10 GB** (6,674 files; 1.38 GB is the uncompressed fat masks) | 12.71 GB | 22.39 GB | 0.02 GB |
| `biomaGUNE MJ` | 0.38 GB (2,626) | 21.84 GB | 16.47 GB | 0.00 |
| `PET` | 0.10 GB (79) | 12.17 GB | 0 | 0.09 GB |
| `Otros` | 0.09 GB (2,348) | 0.00 | 32.46 GB | 10.84 GB (pig DICOM 7.86, model weights 2.86) |
| `MRI` | 0.05 GB (321) | 5.32 GB | 13.18 GB | 0 |
| `Microscopio` | 42 annotation files | 0 | 0 | 0 |

So the hub's per-folder "segmentation" sizes (`Pili y Mili` 13.8, `biomaGUNE MJ` 20.7, `PET` 11.4, `MRI` 5.0 GB) are
about 95 % image volumes. **For A1:** every one of the drive's 21,203 `.raw` files (84.6 GB) has a same-named `.mhd` beside
it: they are MetaImage data, **not** Bruker raw, though the hub's class list counted them as raw Bruker.

### 1.2 `Otros\Segmentaciones ITK SNAP` in full (41,728 files, 37.9 GB)

| Subfolder | Labels | Split volumes | Source images | Other |
|---|---:|---:|---:|---:|
| `Segmentacion 2DG RATAS` (11 rat sessions, 2019) | 441 label volumes (`Pred_`, `Postprocessed_`, 1 `Modificated_`; + their 441 `.raw`, 94 MB) | 440 files, 0.37 GB | – | 16 (`prueba`) |
| `Segmentaciones Arteria Pulmonar cerdos` (pigs, 2014) | 206 (199 distinct ROIs) | 1,750 files, 27.8 GB | **35,189 Philips DICOM files, 7.9 GB** | 28 junk |
| `Segmentaciones ratones` (5 mouse cohorts, 2020) | 682 | 1,500 files, 1.7 GB | – | 1,034 junk, 1 ITK-SNAP label file |

### 1.3 The 12 sets

| Set | What | Distinct (files) | Traced | Rate | Why not, mostly |
|---|---|---:|---:|---:|---|
| `S-CINE-LVRV` | mouse cardiac cine ventricle masks, ITK-SNAP, one per phase | 6,685 (9,530) | 3,330 | 49.8 % | 2019–21 studies absent from production |
| `S-CINE-MASS` | mouse cine "Massventricles" masks | 220 (431) | 147 | 66.8 % | same |
| `S-FLOW-ROI` | mouse great-vessel ROIs on phase-contrast flow (238 pulmonary artery, 20 aorta, 20 unnamed) | 278 (450) | 201 (189 as exam pairs) | 72.3 % | 2020 / no-token folders |
| `S-PETCT-MASK` | organ masks on Molecubes PET/CT exports | 252 (358) | 142 | 56.3 % | `0619`, `0320`, `1019` and early `1422` PET are not in production |
| `S-PMOD-VOI` | PMOD VOI sets | 73 (121) | 39 | 53.4 % | traced ones are all `DS-SEG-0002` twins |
| `S-CINE-PRED-VICOMTECH` | Vicomtech model predictions (`Predict_Slicer\*.mha`) | 150 (195) | 0 | 0 % | 2020–21 studies; model output |
| `S-RAT-2DG-2019-PRED` | rat cine model predictions + post-processing (2019) | 441 (441) | 0 | 0 % | 2019 studies; model output |
| `S-RAT-0118-RESP` | rat (0118, MCT) cine masks, expiration vs inspiration, 2021 | 95 (128) | 0 | 0 % | studies not in production (A1 R2) |
| `S-FAT-1019` | mouse fat masks on fat-fraction maps (`MRI grasas Irati`) | 181 (185) | 0 | 0 % | algorithmic; fat-water exams not in production |
| `S-PIG-PA-FLOW` | pig pulmonary-artery ROIs, CNIC Philips 3T, 2014 | 199 (206) | 0 | 0 % | not a gjesus3 instrument |
| `S-HISTO-ANNOT` | NDP.view + QuPath annotations on `.czi` slides | 41 (42) | 0 | 0 % | slides from a foreign Axioscan (A1 R6) |
| `S-AMIRA-LUNG-CT` | one Amira lung label field (+ files) | 2 (3) | 0 | 0 % | animal not stated |
| **All** | | **8,617 (12,090)** | **3,859** | **44.8 %** | |

Per cohort (set × protocol × year): `a3_cohorts.csv`. Per label, with the reason when untraced: `a3_labels_distinct.csv`.

---

## 2. Traceability by cohort (the candidate sets)

**Cine LV/RV masks** (`S-CINE-LVRV`; distinct labels, traced / total):

| Protocol | 2020 | 2021 | 2022 | 2023 | 2024 |
|---|---|---|---|---|---|
| `0320` | – | – | **152 / 156** (geometry) | – | – |
| `0424` | – | – | – | – | **179 / 180** |
| `0522` | – | – | **91 / 91** | **599 / 599** | 75 / 90 |
| `0619` | 15 / 389 | 0 / 907 | 183 / 287 | – | – |
| `1019` | 0 / 939 | 313 / 339 | **328 / 328** | – | – |
| `1121` | – | – | **780 / 780** | – | – |
| `1422` | – | – | – | **283 / 283** | 271 / 286 |
| `1519` | 59 / 877 | – | 2 / 2 | – | – |

The untraced 2022–2024 labels are explained one by one: `0522` 2024's 15 belong to `jrc240702_m93_0522`, the 2024 study
production lacks (A1 R3). `1422` 2024's 15 are masks named for animal `m47` sitting in `m46`'s study folder, whose stack they
do not fit (misfiled; A2 should not place them under `m46`). `0619` 2022's 88 belong to six studies of 2022-01-25 that
the scanner named without the `m` (`jrc220125_191_0619` … `_200_0619`): the silently-skipped pattern of 2026-10-05,
absent from production, exactly A1 R3's six. Its other 16 are a stack whose offsets repeat (a re-acquired slice), so
geometry cannot settle it.

**Flow ROIs** (`S-FLOW-ROI`): 2022–2024 cohorts of `0320`, `0424`, `0522`, `0619`, `0721`, `1019`, `1123` trace at
89–100 %. A flow ROI lies on one slice shared by the magnitude cine and the velocity map (two exams), so 189 trace to that
exam pair (`acquisition-group`).
**PET/CT masks** (`S-PETCT-MASK`): `0424` 2024, `0522` 2022–24, `1122` 2022, `1123` 2024, `1422` 2024 at 100 %; the
others are not in production (production's PET/CT starts 2022-11 for `0522` and holds none for `0619`, `0320`, `1019`).

---

## 3. What the label values mean: measured, not named

No label file records its value meanings, and no NIfTI header records a tool or version (`descrip` is empty on 8,028 of
them). There are two kinds of evidence.

**Names.** An ITK-SNAP label description, `Segmentation Labels.label`, is on the drive three times (same SHA-256, in
`Segmentaciones London Procedimiento 4` and two `1019` raw-data folders): `1 LV Endo, 2 LV Epi, 3 RV Endo, 4 RV Epi`.
The group's Vicomtech Slicer module (`Otros\PH_analysis_Segmentation_tool`, contributor "Maialen (Vicomtech)") predicts 5
classes and was trained on 375 manual volumes whose values were 1–4 (`Seg_models\Description.txt`); `Reference.txt`
names its reference animals (`m26_BE` … `m51_0619`).

**Geometry** (`a3_label_topology.py`, every distinct cine mask, per slice). *Exterior contact* = the share of a label's
boundary that touches the background outside all labels. A cavity inside a myocardial ring scores 0; two separate
cavities score about 1. *Solidity* = area / convex-hull area: a round LV cavity is about 0.95, an RV crescent about 0.75.

| Schema (distinct files) | Values | Exterior contact (median) | Enclosure | Solidity | Reading |
|---|---|---|---|---|---|
| **LV/RV pools** (4,069) | 0/1/2 | 1: 1.00 · 2: 1.00 | none, and 1 and 2 never touch | 1: 0.95 · 2: 0.75 | **1 = LV blood pool, 2 = RV blood pool** (myocardium unlabelled) |
| **LV endo/epi** (833, all `1519` 2020) | 0/1/2 | 1: 0.00 · 2: 0.6 | 1 inside 2 | 1: 0.96 · 2: 0.55–0.75 | **1 = LV cavity, 2 = LV myocardium**. Same values, different meaning |
| **ITK-SNAP palette** (1,600) | 0–4 | 1: 0.00 · 2: 0.42 · 3: 0.02 · 4: 0.55 | 1 inside 2 (median 1.000) | 1: 0.95 · 2: 0.63 · 3: 0.71 · 4: 0.38 | 1 LV cavity, 2 LV myocardium ring, 3 RV cavity, 4 RV wall: the label file's order |
| **Massventricles** (251) | 0–4 | 1: 0.00 · 2: 0.08 · 3: 0.49 · 4: 0.56 | **1 inside 3** (median 0.955) | 1: 0.94 · 2: 0.79 · 3: 0.74 · 4: 0.45 | 1 LV cavity, **2 RV cavity, 3 LV myocardium**, 4 RV wall: a different order |
| pools as 1/3 (221) | 0/1/3 | both ~1.0 | none | – | LV and RV pools painted with the palette's "Endo" values |

On this drive's byte-identical copies of `DS-SEG-0004`: its 168 two-class files read as LV/RV pools (solidity 0.955 / 0.758);
its 8 Massventricles files read as the Massventricles order. The **two files `DS-SEG-0004` excluded** as "almost certainly
mis-named Massventricles" (`jrc220207_m65` phase 15, `jrc220207_m67` phase 1, both on this drive) show the Massventricles
pattern exactly (1 inside 3: 0.81 and 1.0), not the palette's.

**Consequence:** a curated set must carry a per-file schema, decided from the voxels. The value set alone mislabels the
1519 masks (833) and confuses the two 0–4 orders (1,851 files). The drafts do this (`schema_check` column).

---

## 4. Overlap with `DS-SEG-0001…0004`

| Dataset | Byte-identical on this drive | Same sessions, different files | Pixel check of its slice map |
|---|---|---|---|
| `DS-SEG-0001` (8 sessions, Mes 10) | 0 | **79** new tracings of `m62`, `m65`, `m66`, `m67` (20 named `MJ_…`), all pixel-verified | **all 8 sessions on the drive: 7 identical, `m85` differs at slices 2↔3** = `DS-SEG-0004`'s correction |
| `DS-SEG-0002` (PMOD VOIs) | 39 `.voi` (40 files) + 20 `.voistat` | 103 NIfTI PET/CT masks on its sessions (CAND-E) | – |
| `DS-SEG-0003` (2025 cohorts) | 0 | 0 | none of its sessions is on the drive |
| `DS-SEG-0004` (inter-observer) | **all 178 human-reader files** (153 A + 25 B; 176 distinct, its own 2 duplicate pairs) | the 2 files it excluded | all 10 sessions: **identical** |

Also byte-identical: 480 files with the `seg-harvest-2026-08-21-irene\paper-irati-1019` deposit (300 split volumes, 180
masks) and 60 with `seg-harvest-2026-08-20`. **What this drive adds for those datasets:** reader B's `MJ_` filenames
(attribution evidence, still unconfirmed), the Mes 10 split volumes, and 79 + 2 further readings of curated stacks.
`DS-SEG-0001`'s verification is evidence only; it was not changed (S4).

---

## 5. Copies, versions and readers

Byte copies: 12,090 label files are 8,617 distinct; one label exists up to 8 times (`a3_labels_distinct.csv`, `copies`).
Different files for the same thing (traced cine and flow labels grouped by study, dims, phase and value scheme): **3,079
groups, 502 with more than one file, 784 pairs.** **None is a voxel-identical re-save**, 24 are small edits (Dice ≥ 0.98),
and **760 differ** (Dice below 0.98: independent readings or real corrections).

| Where | Pairs | Median Dice | What it is |
|---|---:|---:|---|
| `1121` 2022, `…\Inicial` vs `…\Revision` | 212 | 0.84 | a **revision pass**, including `Revision\Jesus` (19) and `Revision\Hago todo de nuevo` ("I redo it all", 20). The only review evidence on the drive |
| `0522` 2023, `IRE` (`m#_0522_segm_IRE_Time#`) vs `MJ` (`Análisis MJ\Time # - m#`) | 191 | 0.84 | **two readers** on the same stacks |
| `0522`/`0619` males, `Splits Machos Proyecto 0619` vs `Splits-Male PAH` | 104 | 0.85 | the same stacks traced twice in two folders |
| `1019` 2021 Mes 10 sessions | 125 | 0.72 | several readings of `DS-SEG-0001`'s stacks |
| flow ROIs: aorta vs pulmonary artery on one slice | 11 | 0.00 (all 11) | **not a conflict**: two vessels on the same slice |

A curator has to choose per (session, phase), or keep readers apart. That is a decision, not a measurement (S2).

---

## 6. Drafts (in `D:\projects\gjesus3\drive3_analysis\a3\drafts\`)

Each candidate has a `_dataset.yaml` and a `provenance.csv` in `DS-SEG-0004`'s column shape (plus `copies_on_drive`,
`schema_check`, `other_versions`, `quality_flag`, `drives12_placed_or_held`). Only traced labels are in a draft.

| Draft | Labels (new) | Sessions | Animals | Acquisitions | Verification | Main flags |
|---|---:|---:|---:|---:|---|---|
| **CAND-A** LV/RV blood pools | **3,234 (3,066)** | 189 | 161 | 2,073 | 2,798 pixel, 268 geometry, 168 `DS-SEG` twin | 984 with other versions; 1,139 dated on a bulk-copy day |
| CAND-C Massventricles | 167 (159) | 84 | 82 | 930 | 129 pixel, 30 geometry, 8 twin | meanings measured, not named |
| CAND-D flow ROIs | 200 | 133 | 127 | 310 | 60 pixel (image match), 140 dims+affine | 188 valid on 2 exams; 116 with other versions |
| CAND-E PET/CT masks | 142 | 134 | 118 | 175 | SHA-256 of the DICOM beside | **values 1–3 unnamed** |
| CAND-F 1519 LV-only | 59 | 4 | 4 | 36 | pixel | 774 more of this schema untraced |
| CAND-B 4-class palette | 15 | 1 | 1 | 10 | pixel | the rest is 2020, untraced |

What the drafts fill from evidence: ACQ-IDs (primary and full stack in slice order), session, subject (facility id from
the registry), production project, dims, values, schema, tool (inferred as **ITK-SNAP, version unknown**: the uint16 /
qform-1 save signature, the ITK-SNAP label file and the folder name), and `date_created` = the earliest modification time
among the copies (`file-mtime`). **Caution:** label dates cluster on a few days (2020-01-24/27: 438 labels;
2025-01-17/31: 230) that look like bulk copies; such rows are flagged.

**Missing before any promotion** (12 §6.2; per draft in its `missing_before_promotion`): the **creator** (only folder or
file-name hints: `MJ`, `IRE`, `IF`, `IAZ`, `Irati`, `Unai`, `Ermal`), the **final version** where there are several, any
**quality review** record, the analyst's **confirmation of the meanings** (CAND-E has none at all), **timepoints**
(folder hints only), and the **slice order** of the 268 + 30 geometry-only files. 313 of CAND-A's labels trace to the 2021
`Proyecto 1019` acquisitions that still carry **no `project_id`** in `registry_raw.csv` (the gap `DS-SEG-0001` recorded).

**Smallest path:** (1) now, A2's placement only (the masks go to project folders as work in progress, 12 §3.2; drives 1+2
already did this for 2,053 drive-3 labels: `1019` 855, `1519` 718, `0619` 476, `0320` 4, plus 276 in holding); (2) one
question round with M. Jesús (§7); (3) promote CAND-A cohort by cohort; CAND-C and CAND-D after it; CAND-E after the values
are named.

### 6.1 Spec gaps this drive adds (to the 19 of the SegBioMed pilot; nothing edited)

- **One value set, several meanings** (§3): the dataset needs a per-file `label_schema`, not one `label_classes` block.
- **Versions of the same tracing** (`Inicial` → `Revision`): there is no field for "supersedes / revision of".
- **Unreliable file dates** (bulk-copy stamps): `date_created_precision` needs a value for that case.
- **A label valid on several exams of one slice** (flow): the spec's single `acq_id` per label does not fit (a cousin of CAND-04).

---

## 7. Questions for M. Jesús (one round serves S1, S2, S3, S5, S7)

1. Who traced `Análisis MJ`, `MJ_Segmentation_…`, `MJ 2024`, `_IRE`, `_IF`, `IAZ_…`, `Analisis Unai`, `Segmentation by JRC`?
2. `1121`: is `Revision` final? Who is `Revision\Jesus`?
3. `0522` 2023: were the `IRE` and `MJ` masks meant as two independent readings?
4. 0/1/2 = LV and RV **blood pools**? The `1519` 0/1/2 = LV cavity and LV myocardium? Massventricles 1 LV cavity, 2 RV
   cavity, 3 LV myocardium, 4 RV wall?
5. PET/CT masks: what are values 1, 2, 3?
6. Pigs: whose study was HEARDS (CNIC, 2014), and may gjesus3 keep it?
7. The `m47` masks in `m46`'s folder (`biomaGUNE MJ\…\MJ 2024\Splits\20240527_164422_jrc240527_m46_1422_1_1\`).

---

## 8. What could not be established, and why

- **Creators and review**: no file, header or sidecar records them. Folder and file-name hints are listed per row and
  marked unconfirmed.
- **The meaning of CAND-E's values** and of the Vicomtech outputs' extra values 5–7: no evidence on the drive.
- **The slice order of 298 geometry-only labels**: their split volumes are not on the drive. Two more stacks were refused
  because an offset repeats (a re-acquired slice: the `DS-SEG-0001` `m85` case that only pixels could settle), and two
  because production holds fewer acquisitions than the mask has slices.
- **Which exam a flow ROI was drawn on**: magnitude and velocity map share the slice.
- **4,677 untraced labels**: their studies are not in production. 1,923 would become traceable by ingesting raw that is on
  this drive (A1 R1; `a3_unlock_studies.csv`); the others name studies whose raw is not on this drive (86 studies), or
  no study at all.
- **Software versions**: not recorded (Amira 2022.2 and PMOD 3.409 appear only in the Amira and Interfile files).
- **Grid of each PET/CT mask** (CT or PET): the exports are on the CT grid; not checked per file.

## 9. Traps the next session must know

1. **Long paths.** 951 staged files have full paths of 260–277 characters: a plain Windows path raises
   `FileNotFoundError`. **SimpleITK fails on non-ASCII paths** (`Imágenes`, `Lucía`). **nibabel rewrites `\\?\` to `//?/`
   and fails.** What works: Python's own `open()` with the `\\?\` prefix, then parsing in memory (`a3_common.load_nifti`,
   `read_metaimage`).
2. **Never decide label versus image by name**, and **never decide a label's meaning by its value set** (§3).
3. **Split volumes are named by study or by session** (`Time_1_rat_<study>.mhd`, `Time_1_rat_jrc220209_m139_1019.mhd`),
   and folder tokens keep ParaVision's `_1_1` counters. Both must be normalised before matching `session_id`.
4. **Two masks with Dice 0 on one slice can both be right**: `MPAflow` and `Aortaflow` are two vessels.
5. **One image file is truncated on the drive itself** (verified byte-identical to the drive):
   `biomaGUNE MJ\Bleomicina Mice_Proyecto 1123\Raw data\MRI\NIFTI\NIFTI_jrc241011_m24_1123\Cine_IG_FLASH_20_Proc1.nii.gz`.
6. **The scratchpad is shared** by the parallel analysts: another one overwrote a same-named script of mine. Use a
   subfolder.
7. `a3_headers.py` and `a3_ncc.py` **resume**: after an input changes, run `a3_run_all.py --fresh`.
8. As the brief warned: heredocs in Git Bash mangle backslashes; write Python to a file.

## 10. For the other parts

- **A1:** every `.raw` on the drive is MetaImage (21,203 files, 84.6 GB), not Bruker raw. The production MRI DICOM frames
  are pixel-identical (up to scaling) to the scanner reconstructions the researchers split (§method 3).
- **A2:** `PET\FDG-ratonesfumadores` is protocol 1122 (two VOIs there are byte-identical to files harvested from
  `S:\gnuclear\2022\Jesus\MOLECUBES\IAZ_MJ\1122\221121|221122\`), consistent with A2 R4a. The `m47` masks in `m46`'s folder
  (S7). One PET mask, `Pili y Mili\Proyecto 0424 Envejecimiento y PAH\MRI\NIFTI_MPA flow data\NIFTI_jrc241127_m12_0424\Segmentation_SUV_m12_0424.nii.gz`,
  is filed under MRI.

---

## Files

**Scripts** (`tools\drive_staging\drive3\`), run in this order by `a3_run_all.py`: `a3_inventory.py`, `a3_headers.py`,
`a3_overlap.py`, `a3_trace.py`, `a3_ncc.py`, `a3_imgmatch.py`, `a3_geostack.py`, `a3_label_topology.py`,
`a3_topology_summary.py`, `a3_sets.py`, `a3_schema_by_cohort.py`, `a3_unlock.py`, `a3_versions.py`,
`a3_slicemap_check.py`, `a3_inventory_summary.py`, `a3_pig_check.py`, `a3_drafts.py`; shared helpers `a3_common.py`.

**Outputs** (`D:\projects\gjesus3\drive3_analysis\a3\`):

| File | What |
|---|---|
| `a3_inventory.csv` | 105,603 segmentation-relevant drive files, first role guess |
| `a3_headers.csv` | header + value census per distinct NIfTI/MetaImage/Interfile file (26,223) |
| `a3_overlap.csv` | SHA-256 matches with `DS-SEG`, harvests, `/raw/`, drives 1+2 |
| `a3_labels.csv`, `a3_labels_final.csv` | every label copy, with set, route, ACQ-IDs and evidence |
| `a3_labels_distinct.csv` | **one row per distinct label: the traceability table** |
| `a3_sets.csv`, `a3_cohorts.csv` | rates per set and per cohort |
| `a3_ncc_stacks.csv`, `a3_ncc_slices.csv` | the 175 cine stacks and every slice score |
| `a3_imgmatch.csv`, `a3_geostack.csv` | image pixel matches; geometry-only stacks |
| `a3_label_topology.csv`, `a3_topology_summary.csv`, `a3_schema_by_cohort.csv` | value meanings, measured |
| `a3_versions_pairs.csv`, `a3_versions_groups.csv` | different files for the same stack and phase |
| `a3_dsseg_session_overlap.csv`, `a3_slicemap_check.csv` | overlap with and checks of the promoted datasets |
| `a3_unlock_studies.csv` | absent studies named by untraced labels, and whether their raw is on this drive |
| `a3_pig_series.csv`, `a3_inventory_summary.csv`, `a3_itksnap_folder.csv`, `a3_label_dates.csv` | supporting roll-ups |
| `drafts\CAND-A…F\_dataset.yaml`, `provenance.csv`, `drafts\drafts_summary.csv` | the drafts |
