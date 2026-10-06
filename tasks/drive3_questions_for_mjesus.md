# Questions about M. Jesús's drive, for Jesús or Irene

**Status:** 🔶 DRAFT v2, 2026-10-06 (v1 was too terse for someone who only knew the projects at a high level).
**For:** Ryan to send to Jesús Ruiz-Cabello and/or Irene. M. Jesús has left the group, so each question carries its own
context. **Nobody has to answer everything.** Every question states what we will do if nobody knows (the default), so
a blank answer is a valid answer. The most useful answers are marked ★.

**Background, in one paragraph.** M. Jesús lent us her external working drive in September (621,969 files, 1.7 TB). We
copied it in full and checked it against gjesus3. Most of the raw imaging is already in gjesus3 or is being added now.
The open points are about **her cardiac segmentations** (which we would like to turn into an official, citable dataset of
the group) and about **a few groups of files whose origin the files themselves cannot tell us**. Paths below are folders
on her drive; counts are files.

**How to answer:** reply with the question number and a few words ("1: IRE is Irene; nobody reviewed them"). If it is
easier, Ryan can go through them with you in 15 minutes.

---

## A. The cardiac segmentations (★ the curated dataset depends on these)

The drive holds about **8,600 distinct segmentation masks**. We matched them pixel by pixel to the MRI scans in gjesus3:
**3,859 of them correspond exactly to scans we hold**, so they can become a dataset. The largest group is about 3,200
masks of the **left and right ventricle on mouse cardiac cine MRI** (2021–2024, 189 imaging sessions, 161 animals, 8
protocols). Most were drawn in ITK-SNAP. Before we publish them as a dataset we need to say **who drew them, whether
anyone reviewed them, and which version is final**: the files do not record any of this.

**1. ★ Who drew each set?** The folder and file names carry initials. Our best guesses are in brackets; please correct:
- `Análisis MJ`, `MJ 2024`, and files named `MJ_Segmentation_…`: [M. Jesús]
- files ending `_IRE` (e.g. `m12_0522_segm_IRE_Time3`): [Irene]
- `IAZ_…`: [Irati]
- `Analisis Unai`: [Unai, the NI platform manager?]
- `Segmentation by JRC`: [Jesús]
- files marked `_IF`: [unknown: who is IF?]

*If nobody knows:* we name the creator as "unconfirmed: M. Jesús's drive" and say so in the dataset.

**2. ★ Were the masks reviewed by anyone after they were drawn?** The only sign of a review on the drive is in
`Proyecto 1121` (2022): the masks exist twice, in a folder `Inicial` and a folder `Revision` (212 pairs; the revised
masks differ noticeably from the first ones). Inside `Revision` there are subfolders `Jesus` (19 masks) and
`Hago todo de nuevo` ("I redo it all", 20 masks).
- Is `Revision` the final version? Was `Revision\Jesus` your review, Jesús?
- For the other projects (`0522`, `0619`, `1019`, `1422`, `0424`), was there any review, or are the masks as first drawn?

*If nobody knows:* we keep both `1121` versions, mark neither as final, and label all other masks "not reviewed".

**3. `Proyecto 0522`, 2023: two people traced the same images.** For 191 image stacks there is one set of masks labelled
`IRE` and one in `Análisis MJ`. They agree about as well as two independent readers usually do. **Were these meant as two
independent readings** (useful for measuring how much readers differ), or was one a correction of the other?

*If nobody knows:* we keep both, as two readers.

**4. ★ What do the label numbers mean?** No file says. We measured the shapes, and found:
- in most masks, value 1 is the **left-ventricle blood pool** and 2 the **right-ventricle blood pool** (the heart muscle
  is not labelled);
- in the `1519` (Santander, 2020) masks, the same values mean **left-ventricle cavity (1)** and **left-ventricle muscle (2)**;
- the masks with four labels come in two orders: the ITK-SNAP palette `1 LV endo, 2 LV epi, 3 RV endo, 4 RV epi`, and a
  set called "Massventricles" with 1 LV cavity, **2 RV cavity, 3 LV muscle**, 4 RV wall.

Is that right? *If nobody knows:* we publish our measured meanings, marked "measured from the masks, not confirmed".

**5. The PET/CT organ masks** (in `PET\…`, 252 masks on Molecubes PET/CT images of `0619`, `0320`, `1019` and `1422`):
**what organs or regions are values 1, 2 and 3?** *If nobody knows:* these masks are kept with their projects but not
published as a dataset.

**6. Fifteen masks named for mouse `m47` are in mouse `m46`'s folder**
(`biomaGUNE MJ\…\MJ 2024\Splits\20240527_164422_jrc240527_m46_1422_1_1\`, protocol `1422`, 2024-05-27), and they do
not fit `m46`'s images. **Are they `m47`'s, filed in the wrong folder?** *If nobody knows:* they stay where they are,
flagged, and are left out of the dataset.

**7. Two scans of the same rats.** For rats `m175` and `m178` of protocol `0118` (2021, the monocrotaline study),
the drive holds **two different reconstructions** of the same MRI sessions; one of each matches the copy Ermal kept on
`K:`. **Which reconstruction did the analysis use?** *If nobody knows:* we register the one that matches Ermal's copy.

## B. Data from outside biomaGUNE (★ we need to know where it comes from to keep it properly)

**8. ★ Pig pulmonary-artery MRI from CNIC (Madrid), 2014.** Folder `Otros\Segmentaciones ITK SNAP\Segmentaciones
Arteria Pulmonar cerdos\`: the source images (7.9 GB; Philips Achieva 3T at CNIC, 2014; the study is labelled
"HEARDS" in the image headers) and 199 pulmonary-artery masks drawn on them. Ryan has decided to keep them in gjesus3 as
external data, in a project of their own. Please tell us:
- Whose study was HEARDS (the CNIC investigator), and what was the collaboration?
- Was there a data-sharing agreement, and does it allow the group to keep and reuse the images?
- Who drew the masks, and what for (a paper, a thesis)?

*If nobody knows:* we keep them as described, marked "external, agreement unknown", and do not share them outside the
group.

**9. Slide scans from another Axioscan, probably Biodonostia.** 116 whole-slide scans (154 GB, October 2024 to February
2025) come from a ZEISS Axioscan 7 that is **not** the biomaGUNE one (a different serial number). They are in
`Microscopio biodonostia\…` (`escaner`, `BIOMAGUNE`, `0522 Biodonostia`), `Histologia_ratones_viejos\…` (HE, Sirius Red,
trichrome) and the `Proyecto 1422` histology.
- Were they scanned at **Biodonostia**? Under which collaboration or protocol?
- Are the animals ours (which protocol)?

*If nobody knows:* they are kept (moved to the gjesus3 holding folder before our copy of the drive is cleared) and not
registered until we know.

**10. Confocal images from a Leica microscope, probably the London partner's.** 26 files (6.8 GB) from a Leica TCS SP8
in `Pili y Mili\Proyecto 1121 London\Experimentos\Histologia\` (`Confocal`, `ki67`, `Training confocal`).
**Was this the London partner's microscope** (which institution), and are these images of `1121` animals?
*If nobody knows:* as for question 9: kept in the holding folder, not registered until we know.

## C. Which project do these belong to?

**11. 197 histology images in the `0522` folder that look like `0619` animals.** Folder
`Pili y Mili\Proyecto 0522  PAH\IFs and histologies\`. The animal numbers in their file names do not exist in protocol
`0522`; all of them exist in `0619`, and the animal facility's records show those `0619` animals sampled before the dates
on the slides. **Are these `0619` images filed in the `0522` folder?** *If nobody knows:* they stay unassigned (stored, but
in no project).

**12. Two folders that name more than one project, or none:**
- `Pili y Mili\Proyecto 1019 + 1121` (100 files: documents and figures): `1019`, `1121`, or both?
- `Draft papers` (M. Jesús's manuscript drafts): which project or projects?

*If nobody knows:* both stay unassigned.

**13. An MRI study from 2019-10-15 named for mouse `m174` of `0619`** (`20191015_…_jrc191015_m174_flow`). The animal
facility has `0619`'s animal 174 born in **2021**, two years after the scan. **Which animal or protocol was this?**
*If nobody knows:* it is registered with no project.

**14. (Optional, larger) 1,443 Cell Observer images with no project in their folder names.** If someone can spend an
hour on it, we can send a short workbook (one row per folder, with dates and example file names) to assign them, as we
did for the operators' drives. *If not:* they are stored with no project, findable by date and name.

---

*For the Data Office: answers feed `drive3_segmentations_cds.md` (S1, S2, S5, S7), `drive3_raw_coverage.md` (R2, R6),
`drive3_projects_and_placement.md` (D7) and the CNIC project. No answer changes anything already in production.*
