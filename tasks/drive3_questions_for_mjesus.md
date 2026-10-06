# Questions for M. Jesús about her drive (one round)

**Status:** 🔶 DRAFT, written 2026-10-06 for Ryan to send when convenient (STATUS §0.5 M3) · **From:** the read-only
assessment of the third historical drive (`drive3_raw_coverage.md` A1, `drive3_projects_and_placement.md` A2,
`drive3_segmentations_cds.md` A3).

**Why one round:** her answers unlock two things. **(1) The curated segmentation dataset:** 3,234 cardiac cine masks
from her drive trace pixel-for-pixel to acquisitions in gjesus3, but promotion (`12_CURATED_DATASETS` §6.2) needs to
know who drew them, whether they were reviewed, and which version is final. **(2) Data from instruments that are not
gjesus3's**, which can only be kept and labelled correctly once we know where they come from. Nothing waits on her in
the meantime: the material is being placed in its project folders as work in progress.

Paths are relative to her drive (`MJesus-MFB-biomaGUNE`).

---

## A. The segmentations (questions 1–7)

1. **Who drew each set?** The folders and file names suggest several people: `Análisis MJ`, `MJ_Segmentation_…`,
   `MJ 2024`, `…_IRE`, `…_IF`, `IAZ_…`, `Analisis Unai`, `Segmentation by JRC`. Which initials are whom, and were the
   masks reviewed by anyone after drawing?
2. **`Proyecto 1121`:** the masks exist in an `Inicial` and a `Revision` version (212 pairs). Is `Revision` the final
   one? Who is `Revision\Jesus`?
3. **`Proyecto 0522`, 2023:** most stacks have one mask set labelled `IRE` and one labelled `MJ` (191 pairs). Were these
   meant as two independent readings of the same images?
4. **What the label values mean.** We measured them; please confirm:
   - In the 0/1/2 masks, 1 and 2 are the **LV and RV blood pools** (not the myocardium).
   - In the `1519` (Santander) masks, the same values mean **LV cavity and LV myocardium**.
   - In the "Massventricles" masks, 1 = LV cavity, 2 = RV cavity, 3 = LV myocardium, 4 = RV wall.
5. **The PET/CT organ masks** (`PET\…`): what do values 1, 2 and 3 stand for?
6. **The pig pulmonary-artery images and masks** (`Otros\Segmentaciones ITK SNAP\Segmentaciones Arteria Pulmonar
   cerdos\`): the images come from a Philips Achieva 3T at CNIC (2014). Whose study was "HEARDS", and may gjesus3 keep
   a copy?
7. **Fifteen masks named for mouse `m47`** sit in mouse `m46`'s folder
   (`biomaGUNE MJ\…\MJ 2024\Splits\20240527_164422_jrc240527_m46_1422_1_1\`) and do not fit that stack. Are they `m47`'s,
   misfiled?

## B. Data from other instruments (questions 8–9)

8. **An Axioscan 7 slide scanner that is not the biomaGUNE one** (116 slide scans, 154 GB, October 2024 to February
   2025), in `Microscopio biodonostia\…`, `Histologia_ratones_viejos\…` and the `Proyecto 1422` histology. Were these
   scanned at **Biodonostia**? Under which collaboration?
9. **A Leica TCS SP8 confocal** (26 files, 6.8 GB), in `Pili y Mili\Proyecto 1121 London\Experimentos\Histologia\…`
   (`Confocal`, `ki67`, `Training confocal`). Was this the **London** partner's microscope?

## C. A few attributions the files cannot settle (questions 10–12)

10. **`Pili y Mili\Proyecto 0522  PAH\IFs and histologies`** (197 histology exports): the animal numbers in the file
    names belong to protocol **`0619`**, not `0522` (the animal facility's records show those animals sampled before the
    slide dates). Which project are they?
11. **`Pili y Mili\Proyecto 1019 + 1121`** and the **`Draft papers`** folder: which project should each be filed under?
12. **An MRI flow study of 2019-10-15 named for animal `m174` of `0619`** (`jrc191015_m174_flow`): the animal facility
    has `0619`'s animal 174 born in 2021. Which animal, or which protocol, was this?

---

*For the Data Office: answers go back into the three reports' open items (A3 S1/S2/S5/S7, A1 R6, A2 D7). No answer changes
anything already in production.*
