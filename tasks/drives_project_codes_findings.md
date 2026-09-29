# Historical-microscopy drives: project claims, classified before ingest

**Status:** 🔶 DRAFT for Ryan's review · **Date:** 2026-09-29 · **Branch:** `feat/drives-project-codes` (not merged)
**Produced by:** [`tools/drive_staging/project_claims.py`](../tools/drive_staging/project_claims.py), read-only.
**Machine-readable:** [`drives_project_claims.csv`](drives_project_claims.csv) (one row per claim). The
per-file tables are on D: in `D:\projects\gjesus3\staging\_analysis\codes\`, listed in
[§ Outputs](#outputs).

The rule being applied is Ryan's rule of 2026-09-29 (`tasks/STATUS.md` §2 and `CHANGELOG.md`):

- **Confirmed:** the code is in the animal DB and the cross-checks pass.
- **(A):** a typo with exactly one corroborated DB match.
- **(B):** clearly not an animal protocol, so it becomes a new `Project-NNNN` with no animal link.
- **(C):** uncertain, so the files are ingested with a blank project and listed.

---

## Summary

**The paths are more trustworthy than feared.** Almost every code written on these drives is a
real protocol, and the animals and dates behind it agree. Most of the classifier's real work was
*rejecting* numbers that look like codes but aren't.

| Verdict | Files on the drives | `.czi` | Size | Archive members (listed, not extracted) |
|---|---:|---:|---:|---:|
| **Confirmed** | **19,019** | 4,710 | **4,026.5 GB** | 99,451 (179.5 GB uncompressed) |
| **(A)** corrected | 147 | 141 | 6.8 GB | — |
| **(B)** `Project-NNNN` | — | — | — | 26 (documents only) |
| **(C)** blank project, listed | 180 | 159 | 186.3 GB | 51 |
| **No claim** (default: treated like C) | 59,490 | 6,284 | 1,915.9 GB | 1,454 |
| Archives holding several claims (see below) | 3 | — | 86.0 GB | (counted in the member column) |
| **Total** | **78,839** | 11,294 | 6,221.5 GB | 100,982 of 782,594 listed |

The ingest needs three things from Ryan:

1. **Approve 5 new `AE-biomaGUNE-NNNN` projects** ([§1.2](#12-new-ae-biomagune-projects--for-approval)):
   `0118`, `1116`, `1319`, `1420`, `1520`. All are real protocols. Four of them hold only CEEA
   paperwork from one archive, and `1319` also holds Peio's PET/CT.
2. **Approve 1 correction:** `118 LUCIA` → `AE-biomaGUNE-0118`
   ([§2](#2-a-corrections--for-approval)). It is corroborated by rat species and by animal
   numbers, but the animal numbers carry little weight on their own. Please read the caveat.
3. **Decide about `Project-0521`** ([§3](#3-b-new-project-nnnn-projects)). The rule makes it (B),
   and it is 26 documents. But the folder holds a CEEA report titled `AE-biomaGUNE-0521`, so it is
   plainly an animal protocol that the facility DB does not have. Calling it "not a protocol" would
   be the wrong message.

Also in this document:

- **180 files in (C)** ([§4](#4-c--uncertain-blank-project)), 186 GB. For 68 of them the DB's
  procedure dates point clearly one way. That is presented as a recommendation, not applied.
- **59,490 unclaimed files** ([§5](#5-files-with-no-claim)) in 291 `(researcher, series)`
  groups, 1.9 TB. They include `Lucia-Lorena Garayoa` (169 GB), `LYDIA` (145 GB) and
  `MANON Biodistribution` (87 GB).
- **Corrections to the hub brief** ([§9](#9-for-the-coordinator)). `Cardiac MRI.zip` holds `0619`
  and `1519` only; `Proyecto 0320` is in the Maria Jesus/Irati archive. And the drives carry a lot
  of **MRI and PET/CT**, not just microscopy.

**Dates used:** the manifest `mtime` (the source drive's modification time), archive-member
timestamps, and, in one tie-breaker, the `YYYYMMDD` inside Bruker study names. The catalog's
`czi_acq_datetime` was not used: `_analysis\catalog\summary.md` did not exist at the final run.

---

## How each verdict was reached

1. **Claims were found** in folder names, filenames, archive names and archive members.
   - Where they sit:
     - `Proyecto NNNN` and `projectNNNN`;
     - a folder named exactly the code, or starting with it (`1022 TUMORES`);
     - a code chunk inside a folder name (`Irene_0522_Metfor`, `230620-TOM20-MTCOI-0522`);
     - the AxioScan slot `MFB_<initials>_<code>_`;
     - a code next to an animal (`ID10_1123_TM`, `0219_ctrl_ID29_…`, Bruker `jrc220622_m1_1321`);
     - `AE-biomaGUNE-NNNN`, matched without regard to case.
   - Archives were listed with `zipfile` or `7z l`; **nothing was extracted.** The OriginPro
     installer and crack archives were not even listed.
2. **Non-claims were rejected and logged** in `rejected_tokens.csv`
   ([§8](#8-rejected-tokens)). Dates are masked before any token is read, so `230519` can never
   yield `2305`.
3. **A code that resolves is still not enough.** For each claim:
   - (i) the animal numbers in its files must exist in that protocol (`animal_db.lookup`);
   - (ii) no raw imaging file may predate the protocol's first animal or its start date, and no
     file may predate the birth of its own animal;
   - (iii) no other claim may contradict it.

   Protocol paperwork, photos and videos are exempt from (ii), because CEEA submissions naturally
   predate the animals.
4. **Files are decided one by one, too.** A file inherits its nearest claim. If *that file's*
   animal is not in the protocol, or the file predates its animal's birth, the file alone drops
   to (C). This is how the PROJ-0056 pattern gets caught: a well-formed number that resolves to a
   real but wrong animal.
5. **Typo candidates** are: one digit changed, two adjacent digits swapped, a missing leading
   zero, or a slip between 3 and 4 digits. A correction is accepted only if **exactly one**
   candidate passes the strict checks: animals found (≥ 80%), and no date contradiction.
6. **When nested claims disagree,** the facility DB's own dates decide.
   - The winner is the protocol that logs a procedure on that animal within 3 days of the
     acquisition, or else the only protocol whose animal was already born by then.
   - If neither test separates them, the file goes to (C).

> ⚠️ **A "found" animal is weak evidence on its own.** A protocol with 190 animals will "find"
> almost any number up to 190. Every such claim carries a *weak discrimination* note in its
> `evidence`. The dates, the species and the folder name carry the weight.

---

## 1. Confirmed

### 1.1 Existing production projects

Each row counts files on the drives plus archive members. **Animals** is the number of distinct
subject ids the DB resolved. **Demoted** is the number of that code's files that dropped to (C)
one by one ([§4.2](#42-files-demoted-one-by-one)).

| Project | Registry | Files (`.czi`, GB) | Archive members | Dates | Animals | Researchers (files) | Demoted |
|---|---|---:|---:|---|---:|---|---:|
| `AE-biomaGUNE-0219` | PROJ-0017 | 394 (148, 243.6) | 3 | 2021-05 → 2024-06 | 18 | Laura 212, MARINA 156, AINHIZE 26 | 33 |
| `AE-biomaGUNE-0320` | PROJ-0007 | — | 387 (MRI NIfTI) | 2021 | 8 | (Maria Jesus/Irati archive) | — |
| `AE-biomaGUNE-0324` | PROJ-0055 | 5 (5, 0.8) | — | 2026-08 | 5 | Ekine | — |
| `AE-biomaGUNE-0420` | PROJ-0012 | — | 19,048 (83 `.czi`, 72.1 GB) | 2016-12 → 2022-01 | 18 | Haizpea | — |
| `AE-biomaGUNE-0423` | PROJ-0020 | 79 (78, 41.5) | — | 2025-05 → 2026-08 | 51 | Ekine | — |
| `AE-biomaGUNE-0424` | PROJ-0002 | 175 (175, 127.5) | — | 2025-08 → 2026-07 | 17 | Irene | — |
| `AE-biomaGUNE-0522` | PROJ-0011 | 959 (954, 106.2) | — | 2023-04 → 2026-03 | 80 | Maria Jesus 407, Irene 323, Marta 227 | 43 |
| `AE-biomaGUNE-0525` | PROJ-0001 | 92 (92, 13.7) | — | 2026-03 → 2026-05 | 23 | Irene | — |
| `AE-biomaGUNE-0619` | PROJ-0004 | 38 (37, 3.3) | 20,468 (51.5 GB, MRI) | 2020-03 → 2026-02 | 84 | Maria Jesus 32, AINHIZE 6 | 41 |
| `AE-biomaGUNE-0721` | PROJ-0010 | 12,877 (534, 320.5) | 932 | 2022-08 → 2024-08 | 37 | Laura 12,310 (mostly MRI), Claudia 1,180, MARINA 195 | 13 |
| `AE-biomaGUNE-1019` | PROJ-0006 | 265 (260, 28.1) | 9,919 (7.6 GB) | 2019-12 → 2026-02 | 105 | Maria Jesus 233, Marta 32 | 2 |
| `AE-biomaGUNE-1022` | PROJ-0019 | 1,215 (831, 437.9) | — | 2024-02 → 2026-05 | 28 | AINHIZE 754, Claudia 438, HUGO 23 | — |
| `AE-biomaGUNE-1025` | PROJ-0015 | 95 (95, 21.3) | — | 2026-07 | 24 | Irene | — |
| `AE-biomaGUNE-1123` | PROJ-0014 | 952 (687, 1,081.2) | — | 2024-10 → 2026-09 | 88 | AINHIZE 851, Laura 101 | — |
| `AE-biomaGUNE-1125` | PROJ-0021 | 12 (12, 1.1) | — | 2026-07 | 12 | Irene | — |
| `AE-biomaGUNE-1321` | PROJ-0018 | 1,681 (653, 1,592.8) | — | 2022-07 → 2025-01 | 58 | Laura 1,174, MARINA 305, LAURA 185 | 59 |
| `AE-biomaGUNE-1325` | PROJ-0059 | 7 (7, 1.9) | — | 2026-08 | 7 | Amanda | — |
| `AE-biomaGUNE-1422` | PROJ-0013 | 141 (140, 4.5) | — | 2024-06 → 2024-08 | 16 | Marta | — |
| `AE-biomaGUNE-1519` | PROJ-0008 | — | 48,654 (46.4 GB, MRI) | 2020-07 → 2022-06 | 35 | (`Cardiac MRI.zip`) | 3 |
| `AE-biomaGUNE-1525` | PROJ-0053 | 2 (2, 0.2) | — | 2026-07 | 2 | Ekine | — |

`AE-biomaGUNE-1121` (PROJ-0009) is also a valid claim. Its only file is a CEEA document inside
`Proyecto 1019 …\Nuevo proyecto`, a nested disagreement with no animal to decide it, so it went to
(C).

**Sanity check (handoff §6).** The codes behind existing production projects come out Confirmed:
`0424` (14 claims), `0522` (23), `0525` (5), `1022` (28) and `1123` (43), with no (C) claim among
them.

### 1.2 New `AE-biomaGUNE-NNNN` projects: for approval

All five are valid protocols in the facility DB (fresh check, [§11](#11-verification)).

| Proposed | Evidence | What would go in it |
|---|---|---|
| `AE-biomaGUNE-0118` | `Proyecto 0118 Monocrotalina` inside `Drive Maria Jesus and Irati 20211209.zip`; dates 2021-06 → 2021-12 fall within the protocol (animals born 2018-05 → 2021-07). Rats (*Rattus norvegicus*), which fits monocrotaline, a rat model of pulmonary hypertension. | 24 archive members (animal lists, documents), **plus** the 147 files of the (A) correction ([§2](#2-a-corrections--for-approval)), 6.8 GB of Cell Observer histology, if Ryan accepts it. |
| `AE-biomaGUNE-1116` | `Proyecto 1116 Contraste`, and its own `MRI Database Proyecto 1116.xlsx` (same archive). | 5 archive members. |
| `AE-biomaGUNE-1319` | `Proyecto 1319 Biodonostia` (same archive), **and** `Former students\Peio\Projects Peio\Hígado\1319\…\1319_ID29_corregPETCT_SUV.nii`. The DB logs `PET CUBES-1` on animals 29–32 on **2021-05-14**, the scan's own date ([example 16](#10-worked-examples)). | 30 files on the drive (PET/CT, 0.5 GB; 16 carry subject ids), and 4 archive members. |
| `AE-biomaGUNE-1420` | `Proyecto 1420 miRNA`, with `AE-biomaGUNE-1420v03.pdf` (same archive). | 4 archive members (documents). |
| `AE-biomaGUNE-1520` | `Proyecto 1520 Fumadores`, with `ae-biomagune-1520v04.pdf` (same archive). | 3 archive members (documents). |

Apart from `1319`, these are **projects made of paperwork**: the CEEA submissions of the
Maria Jesus/Irati "Pili y Mili" archive. Creating a project folder for 3 to 24 documents is Ryan's
call. The alternative is to keep them only as non-raw material under a group-level folder.

---

## 2. (A) corrections: for approval

There is exactly one.

| From | To | Where | Files |
|---|---|---|---|
| `118` (in `118 LUCIA`) | **`0118`** (missing leading zero) | `drive1: Cell observer\AINHIZE\118 LUCIA\Lucia Lungs 118\…` | 147 (141 `.czi`, 6.8 GB), dated 2022-11 → 2024-05 |

**Evidence for it:**

- `0118` is the **only** valid candidate among all the 3→4 digit corrections of `118`.
- All 6 animal numbers in the filenames exist in `0118` (`131L`, `132L`, `136`, `137`, `144`,
  `145`; `L` is lung).
- They are all ***Rattus norvegicus***. That matches this person's other folders, `Lucia Rata AP`
  (rat) and `Lucia_Azul de Prussia`, and the rat monocrotaline project `Proyecto 0118
  Monocrotalina` found elsewhere.
- Animal 131 of `0118` was perfused on 2020-02-04, and the slides are dated 2022-11 onward, which
  is consistent.

**The caveat.** `0118` has 186 animals with codes up to 190, so *any* number up to 190 would have
been "found". The animal check therefore adds little. The weight rests on the species, the
uniqueness of the candidate, and the `Proyecto 0118` folder. Treat this as medium confidence.
**One sentence to Lucia settles it.**

These files are **Cell Observer** histology. The folder sits under `AINHIZE`, and the researcher
recorded is `AINHIZE` by rule ([§7](#7-researchers)). The person, Lucia, is named only inside the
folder name, so she is flagged but not assigned.

There are 12 subject ids on these rows (`ID`-form tokens only). The `131L`-style lead numbers get
no subject id: they are used for the cross-check, but they are not safe enough to assign.

---

## 3. (B) new `Project-NNNN` projects

Both sit inside `drive1: Drive Maria Jesus and Irati 20211209.zip!…\Pili y Mili\`. Neither
contains imaging.

| Proposed | Claim | Why it is "clearly not in the animal DB" | Content |
|---|---|---|---|
| `Project-0521` | `Proyecto 0521 iNO`, and inside it `RE__Informe_CEEA_condicionado_subsanación_AE-biomaGUNE-0521\AE-biomaGUNE-0521v02.docx` | `0521` is absent from the facility DB. None of the 12 typo candidates has any animal evidence: the folder holds no animal numbers. | 26 members, 0.0 GB, all documents (CEEA correspondence, dated 2020-06 → 2021-12) |
| `Project-0720` | `Proyecto 0521 iNO\Antiguo proyecto 0720` ("old project 0720") | Absent from the DB. | 4 members. These **went to (C)**, not to `Project-0720`, because they are nested inside `0521`, and the rule sends an unresolved nested disagreement to (C). |

> ⚠️ **This is where the rule reads awkwardly, as the handoff anticipated.** `0521` is not a
> group project id that merely looks like a protocol. It **is** an animal protocol application: a
> CEEA report conditionally approved `AE-biomaGUNE-0521`, and the old number was `0720`. The
> facility DB simply does not have it. The likely reasons are that it was never started, or that
> it runs under another number (`0521` "iNO" might have become one of the valid `05xx`/`xx21`
> codes, but nothing on the drive says which).
>
> **Recommendation:** do not create a project for 26 documents on this evidence. Either:
>
> - (a) ask the animal facility whether `0521` exists under another code, then re-run; or
> - (b) accept `Project-0521` as specified, and put the 4 `0720` documents inside it (they are
>   the same study's history), rather than creating `Project-0720`.
>
> The stakes are near zero either way: there is no imaging.

**No other (B) exists.** Every other folder or keyword claim resolved, apart from `2503`, which is
a date ([§4.1](#41-claim-level-c)).

---

## 4. (C): uncertain, blank project

### 4.1 Claim-level (C)

| Claim | Files | Why uncertain |
|---|---:|---|
| `drive1: Cell observer\AINHIZE\Claudia\Uptake MDA-MB-231 ccMn-doxo\2503` | 32 (30 `.czi`, 0.1 GB) | `2503` is not a protocol and has no valid typo candidate. It **reads as the date 25-03**, and the files are dated 2024-03-25. The content is cell-line uptake (MDA-MB-231), with no animals. Almost certainly a date folder, not a project. |

### 4.2 Files demoted one by one

These files sit under a valid claim, but their *own* evidence contradicts it.

| Files | Under claim | Why | Recommended reading (NOT applied) |
|---:|---|---|---|
| 59 | `1321_ID61…` and similar, inside `AINHIZE\1123\ID 135-153\{HE,PR,TM}` and drive 2's `1123\{HE,PR} ITZIAR todos (paper miR29a + controles Asier)`, `1123\…\1321 controles` | The filename says 1321, the folder says 1123. Animals 61–65, 70 and 98–101 exist in **both**, and neither has a procedure on the file date. | **1321 for animals 61, 62, 70:** 1321's animals had "Organ sampling" and "Perfusion" on 2023-08-28/29, while 1123's animals of those numbers have only a tattoo logged. The name also says "controles" (controls). **Still ambiguous for 63–65 and 98–101:** 1123's animals of those numbers also had organ sampling, in 2025-01 and 2025-04. |
| 33 | `AINHIZE\LAURA\1321\Immunos tiles Marina\ID19_0219_alphasma_10x tiles.czi` and similar | The filename says 0219, the folder says 1321. Animals 19, 22 and 26 are in both. | **0219 for animals 19 and 22:** they were organ-sampled on 2021-09-20, while 1321's animals 19, 22 and 26 were born in 2022-08 with no sampling logged. Animal 26 is ambiguous. |
| 24 | `Maria Jesus\MJS_IF\…\Proyecto 0522 8OHdG\230519-ID137-…` and `230518-Alphasma-8ohdg-0522\…ID137…` | The files are dated 2023-05; animal 137 of 0522 was born **2025-01-16**. | This `ID137` is not 0522's animal 137. Ask Maria Jesus which protocol it came from. |
| 19 | `Maria Jesus\230620-TOM20-MTCOI-0522\ID187_10x.czi` and IDs 202–209 | These animals are not in 0522 (it has 161 animals). | They belong to another protocol, probably the older-mouse studies (1019 has up to 173, which is still too few). Ask Maria Jesus. |
| 39 | `…Proyecto 0619 Ratones PAH\Pruebas flujo\…NIFTI_m198_flow…` (archive) | Dated 2021-03; animal 198 of 0619 was born 2021-09. | These are flow **test** scans ("Pruebas flujo"). `m198` is probably not a 0619 animal. |
| 11 | `LYDIA\Lydia 0721_CNDs_HEx40\ID238Corazon_HEx40_*.czi` | Dated 2022-09; animal 238 of 0721 was born 2025-01. | `ID238` belongs to another protocol. The rest of the folder (IDs 17–19) is Confirmed 0721. |
| 2 | `Irene_0522_Metfor\Axioscan_0522_PAPER\…\Males_0522_HE\MFB_MBC_0619_ID75H/76H_HE_10x.czi` | The filename says 0619, the folder says 0522. Both protocols contain animals 75 and 76. | **0619:** its animals 75 and 76 were organ-sampled 2020-12-16, while 0522's were born 2024-03 with no sampling. These are older reference slides filed with the 0522 paper. |
| 3 | `Cardiac MRI.zip!…1519…jrc200924_m23…`, `…m26…Segmentation…m29…` | A segmentation file whose own animal number is not in 1519, or which predates that animal's birth. | Segmentations copied between animals. The study folder itself is Confirmed. |
| 4 | `Antiguo proyecto 0720` | Nested inside `0521` ([§3](#3-b-new-project-nnnn-projects)). | Fold into whatever `0521` becomes. |
| 2 + 2 + 1 | CEEA documents: `AE-biomagune-0721_v3.docx` in `Proyecto 1116`, `AE-biomaGUNE-1019v04.pdf` in Haizpea's `project0420`, and a `1121` document in `Proyecto 1019\…\Nuevo proyecto` | A document for one protocol filed inside another's folder, with no animal to decide between them. | Paperwork. Either project folder is fine. |

The "recommended reading" column is evidence for Ryan, not a verdict. Applying it would mean
teaching the tie-breaker that organ sampling on a protocol's animal counts as evidence for
histology. That is reasonable, but it is a new rule, so it is left to Ryan.

---

## 5. Files with no claim

**Default applied (pending Ryan's confirmation):** 59,490 files, 1,915.9 GB and 6,284 `.czi`, with
no claim anywhere on their path, get a **blank project**. They are grouped by
`(researcher, series)` into **291 groups**, and all 291 are in
`D:\…\codes\noclaim_groups.csv`. Here are the 40 largest:

| Drive | Researcher | Series | Files | `.czi` | GB | Dates |
|---|---|---|---:|---:|---:|---|
| drive2 | Laura | Proyectos_Laboratorio_Laura\Lung-surfactant | 2,622 | 591 | 493.5 | 2022-05..2025-02 |
| drive1 | — | (drive root: `LEONE.zip`, `Simu_2_V_XYZ.zip`, …) | 4 | 0 | 178.9 | 2020-12..2024-10 |
| drive1 | Lucia-Lorena Garayoa | (loose files in the person folder) | 120 | 119 | 168.6 | 2022-03..2022-05 |
| drive1 | Laura | Cell observer | 1,721 | 490 | 162.0 | 2023-09..2024-03 |
| drive1 | LYDIA | (loose files in the person folder) | 287 | 139 | 145.2 | 2021-12..2022-07 |
| drive2 | Laura | Proyectos_Laboratorio_Laura\Ferritas | 1,613 | 336 | 100.5 | 2024-07..2025-02 |
| drive1 | AINHIZE | MANON Biodistribution | 109 | 86 | 87.0 | 2022-11..2023-05 |
| drive1 | Lucia | (loose files in the person folder) | 32 | 26 | 46.4 | 2022-06..2022-12 |
| drive1 | HUGO | (loose files in the person folder) | 72 | 63 | 44.0 | 2022-05 |
| drive1 | LAURA | ID81 + ID83 Biodistribución | 68 | 66 | 42.9 | 2023-01..2023-02 |
| drive1 | MARINA | COLOCALIZACION F4.80 + PB | 202 | 129 | 37.5 | 2023-06..2024-04 |
| drive1 | Lydia | Tumores | 69 | 69 | 31.6 | 2023-11 |
| drive1 | LYDIA | APx20_Gabriela | 16 | 16 | 30.2 | 2022-05 |
| drive1 | zuri | (drive root: `Drive zuri 170823.zip`) | 1 | 0 | 29.0 | 2024-01 |
| drive2 | Laura | CELL OBSERVER\Herida | 629 | 72 | 28.0 | 2024-08 |
| drive2 | Laura | TEM-Laura\Imagenes TEM | 2,096 | 0 | 19.6 | 2021-10..2023-08 |
| drive1 | AINHIZE | COLOCALIZACION F4.80 + PB | 120 | 89 | 18.4 | 2023-06..2023-07 |
| drive1 | LYDIA | Picrosirius Red | 40 | 40 | 17.4 | 2022-06 |
| drive1 | LYDIA | Alizarin | 39 | 38 | 16.0 | 2022-06..2022-08 |
| drive2 | Laura | Proyectos_Laboratorio_Laura\MRI | 1,711 | 0 | 14.8 | 2022-10..2023-07 |
| drive2 | Laura | Colaboraciones\Colaboracion-Susana-muestras-MnEquiva | 919 | 0 | 13.3 | 2024-08 |
| drive1 | AINHIZE | (loose files in the person folder) | 9 | 8 | 13.1 | 2024-01..2024-10 |
| drive2 | Amanda | Cerdos | 33 | 33 | 11.9 | 2026-07 |
| drive1 | Lydia | Grupo 1-Prussian Blue | 22 | 22 | 11.6 | 2023-12 |
| drive1 | Zuriñe | 0 IMAGEN CONFOCAL | 2,038 | 364 | 10.3 | 2023-03..2023-07 |
| drive1 | Maria Jesus | MJS Corazon HEx40 | 90 | 90 | 8.9 | 2022-08 |
| drive1 | AINHIZE | CONFOCAL LSM 900 | 329 | 261 | 8.4 | 2023-07..2024-09 |
| drive1 | Maria Jesus | MJS_IF | 119 | 116 | 8.3 | 2023-05..2023-06 |
| drive1 | Itziar | Lipofectamine | 127 | 125 | 7.6 | 2024-05 |
| drive1 | Maria Jesus | MJS_HEx40 | 60 | 60 | 7.6 | 2022-10 |
| drive1 | Lydia | Alizarin_Imágenes Marta | 593 | 10 | 6.3 | 2022-01..2022-09 |
| drive2 | Laura | Origin | 9 | 0 | 6.3 | 2024-12 |
| drive1 | Lydia | (loose files in the person folder) | 46 | 34 | 5.9 | 2021-03..2024-04 |
| drive1 | AINHIZE | MITOSOX | 107 | 92 | 5.8 | 2024-09 |
| drive2 | Laura | CELL OBSERVER | 4 | 2 | 4.2 | 2024-08 |
| drive2 | Laura | CELL OBSERVER\ROS | 209 | 52 | 4.1 | 2024-08 |
| drive1 | AINHIZE | Aortas | 68 | 62 | 3.9 | 2022-09..2022-10 |
| drive1 | AINHIZE | Aorta_Gabriela | 7 | 3 | 3.2 | 2024-02 |
| drive1 | AINHIZE | Colocalización F4.80 + PB 40x | 114 | 52 | 3.2 | 2024-06 |
| drive1 | AINHIZE | PCLS | 78 | 41 | 3.1 | 2024-07..2024-10 |

**Hints, NOT applied.** A human mapping these groups may want the following. None of it is strong
enough for the rule.

- **`AINHIZE\MANON Biodistribution` (87 GB).** Its subfolder `0721 ID 159-161` is Confirmed 0721,
  and `Organ weight_biodistribución Manon_0721_211222.xlsx` names 0721. The rest of the group
  (`ID102 + ID103`) is probably 0721 too.
- **`Marta\PR_MJS\R1057_20-1019-1_PR.czi` (4 files).** These sit beside confirmed
  `ID167II-1019-3_PR_18m.czi`. `1019-1` follows Maria Jesus's `1019-N` sub-series naming, but
  without an animal id the claim position is too weak for the rule.
- **`Proyectos_Laboratorio_Laura\MRI` (1,711 files).** These are Bruker studies named
  `pr230515_m113_biod` and similar, with the protocol dropped from the study name. The
  `PR-0721-Biod-May23` archive (Confirmed 0721) covers animals m113 to m117 of the same
  experiment.
- **Unclaimed files with a real code in a free filename position.** These were rejected on
  purpose and are listed in `safety_net.csv`:
  - TEM frame counters (`LS-IONP__20kX__0114.dm4`);
  - analysis spreadsheets (`Tibiae results 1121 FDG Libe.xlsx`, `voistatcuantificacion1024estatico.xlsx`);
  - a bibliography PDF (`cia-12-1419.pdf`);
  - `1321_IF93-96_COLOCALIZACIÓN PB + F4,80.pptx`.

---

## 6. Conflicts

There are **22 conflict groups**, all *nested* claims that disagree. Every one was decided on the
DB's evidence, or sent to (C):

- **Decided by procedure date.** Four Bruker studies `jrc220622_m{1,2,3,4}_1321` sit inside
  `Cursosurf_0219` (Laura's backup). 1321's animals 1–4 have procedures in June 2022, while 0219's
  animals 1–4 were perfused in 2019 ([example 6](#10-worked-examples)). **→ 1321.**
- **Decided by procedure date, for the OUTER claim.**
  `…Proyecto 0619…\20210927_…_jrc210927_m167_0619_1_1\Segmentation_time*_m167_1019.nii.gz`.
  The filename says 1019, but 0619's animal 167 has a procedure logged on the scan date,
  2021-09-27, and 1019's animal 167 has nothing until 2022 ([example 7](#10-worked-examples)).
  **→ 0619.** These segmentations were copied from a 1019 template and never renamed.
- **Decided by date of birth.** `AINHIZE\1022\HIF1A + VEGFA\PRUEBAS\…` holds `0619`-named test
  stains (6 files) inside the 1022 tree. 1022's animals 112 and 113 were **not yet born** on the
  slide date (2025-09-19), so the slides cannot be theirs. **→ 0619.**
- **Decided because the outer claim is not a protocol.** `1022\iNOS\nuvo protocolo 2210\…` is a
  single file whose own name says 1022, and `2210` resolves to nothing. **→ 1022.**
- **(C):**
  - the rows in [§4.2](#42-files-demoted-one-by-one) marked "both";
  - the three CEEA documents filed in another protocol's folder;
  - `Antiguo proyecto 0720`.

In `file_claims.csv`, the `conflict` column carries the full decision for each file. The run's
`run_summary.txt` lists all 22 groups.

---

## 7. Researchers

**Rule applied (hub brief §8.7):** the innermost **whole-segment** person-named folder is the
researcher, recorded as written. A name buried in a longer folder name is **flagged, never
assigned** (105 distinct folders). Operator initials (`AUA`, `MBC`, `MJS`, `MJ`, `IAZ`, `EO`) are
never mapped to a person.

**The Toshiba backup is Laura's.** Everything under `2025-10-02 - Toshiba EXT (Backup)\` defaults
to `Laura`. The evidence is `Proyectos_Laboratorio_Laura`, `TEM-Laura`, `Papeleo\Admisión
doctorado\Training_Laura-2023`, `TESIS`, `CV`, visa and padrón paperwork, and one person's
congresses and abstracts. Whole-segment person folders inside it still take precedence (see
nesting below).

**Nested person folders, all flagged** (researcher = the innermost):

| Nesting | Files | GB |
|---|---:|---:|
| `AINHIZE > MARINA` | 1,608 | 1,058.8 |
| `AINHIZE > LAURA` | 901 | 553.8 |
| `Marta > Irene` | 699 | 243.5 |
| `AINHIZE > Claudia` | 653 | 41.6 |
| `AINHIZE > Itziar` | 337 | 7.9 |
| `Laura > Claudia` (backup) | 165 | 3.6 |
| `Nicola > Naiara` | 157 | 0.0 |
| `Laura > Marina` (backup) | 126 | 35.1 |
| `Marta > Ekine` | 86 | 42.5 |
| `Liuda > Lucia` | 73 | 0.6 |
| `Marta > Amanda` | 40 | 13.8 |
| `Laura > Susana` (backup) | 26 | 0.1 |
| `AINHIZE > HUGO` | 23 | 0.7 |
| `AINHIZE > MANON` | 15 | 0.3 |
| `Nicola > Marina`, `Laura > Lucía`, `Laura > Julen`, `Laura > HUGO` | 5, 5, 2, 2 | ~0 |

**Person-level folders whose names are mixed** (researcher = the leading name, flagged):

- `Liuda-Ukr 2022` → Liuda (779 files)
- `Lydia TAX LEASE_Marta` → Lydia (126; it also names Marta)
- `HUGO HE` and `HUGO_Azul de Prussia` → HUGO (72)
- `Lucia Rata AP` and `Lucia_Azul de Prussia (Ainhize)` → Lucia (27)

**Two-person archive.** `Drive Maria Jesus and Irati 20211209.zip` is left **blank** and
flagged. It covers 13,810 claimed members, and its own inner folder is called `Pili y Mili`.

> ⚠️ **`AINHIZE` as researcher: please look.** 3,085 files (1.6 TB) have `AINHIZE` as their
> innermost person folder. Project memory records Ainhize Urkola as the **Cell Observer and
> LSM 900 operator**, and her tree holds other people's work (`LAURA`, `MARINA`, `Claudia`,
> `Itziar`, and embedded names such as `ASIER ID205-239`, `MANON Biodistribution`, `118 LUCIA`).
> Rule 8.7 makes her the researcher wherever no inner person folder exists. That may record the
> operator as the researcher on, for example, all of `AINHIZE\1123` (851 files).
>
> The same question applies to `Marta` (570 files), whose tree nests `Irene`, `Ekine` and `Amanda`.
> This is Ryan's call; nothing was changed.

`CELL OBSERVER\Laura` in the backup and `Cell observer\Laura` on drive 1 are the same person
spelled the same way. `LAURA` and `LYDIA`/`Lydia`, and `MARINA`/`Marina`, are recorded **as
written**, because the researcher naming convention is with the group (BACKLOG).

---

## 8. Rejected tokens

`rejected_tokens.csv` holds 57,487 rows. Each row is a distinct `(token, reason, source)` with its
occurrence count and one example. 7+ digit runs are logged by length, because as 539k distinct
DICOM instance numbers they made the file unreadable, and they can never be a 3–4 digit code.

| Reason | Distinct | Occurrences | Example |
|---|---:|---:|---|
| short number (index, replicate, group) | 215 | 3,339,365 | `_1_1` |
| long number (5+ digits) | 21 lengths | 1,459,445 | DICOM instance numbers |
| date or time, 6 digits (`YYMMDD`, `hhmmss`) | 3,441 | 569,248 | `230519` |
| digits inside a name | 47,478 | 237,483 | `2dseq`, `ki67`, `8OHdG`, `TOM20`, `CD206` |
| LEONE case numbering (context rule) | 197 | 156,795 | `LEONE 304`, `S69460` |
| animal `m<n>` | 290 | 19,426 | `m21` |
| magnification | 88 | 18,259 | `20x` |
| date, 8 digits | 281 | 15,276 | `20231227` |
| animal `ID<n>` | 752 | 12,821 | `ID62C` |
| DICOM UID or system id | 2,877 | 4,311 | `2.16.756.5.5.100…` |
| **Zuriñe's mouse numbers (context rule)** | 131 | 4,177 | `7822`, `8170 y 8171`, `8244 y 45` |
| time point | 65 | 4,007 | `24h` |
| 3-digit number outside a project-id position | 231 | 3,383 | `231` (from MDA-MB-231) |
| size unit | 45 | 3,250 | `20kX` |
| **leading-00 counter** | 99 | 2,527 | `.cine_id22_.0001.jpg` |
| analysis output (GSEA/GO, context rule) | 632 | 1,408 | gene-set sizes |
| date `d.m.y` | 233 | 710 | `17.03.22`, `4.10.24` |
| animal id range | 70 | 487 | `ID 135-153` |
| free filename position (not a claim position) | 157 | 340 | `LS-IONP__20kX__0114.dm4` |
| date `YYYY-MM-DD` | 88 | 215 | `2024-04-04` |
| year | 22 | 200 | `2021`, `2022` |
| **numbered sibling series** | 19 | 28 | **`1024 1025 1026 1027`** (Ana B, `mapas T2\Basales`) |
| AxioScan auto-name counter | 18 | 18 | `2026_01_12__10_33__0024` |
| fluorophore wavelength | 15 | 87 | `488`, `555`, `647` |
| Bruker `pdata` procno | 2 | 16 | `pdata\1000` |
| 3-digit number inside an already-claimed tree | 1 | 1 | `1123\…\PB\102-40x` |

These are the traps that would have become fabricated codes, the direct parallels to the 21 in
August:

- **`1024 1025 1026 1027`**: consecutive folders under Ana B's `mapas T2\Basales`, dated 2019.
  `1024` and `1025` *are* real protocols, but from 2024 and 2025 (`AE-biomaGUNE-1024` is
  PROJ-0058). They are rejected as a numbered series ([example 13](#10-worked-examples)).
- **`0001`–`0015`** in `.cine_id22_.0001.jpg`, … Before the `00` guard existed, `0012` produced a
  "correction" to `0612` (a 2015 protocol), and `0013`–`0015` each had 4–7 passing candidates.
- **Zuriñe's `7822`**: a one-digit change gives `0822`, a real protocol.
- **`2503`** reads as the date 25-03 ([§4.1](#41-claim-level-c)).
- **`102` in `102-40x`**: an animal number under a 1123 folder.

**Handoff check "no project is built from a rejected token".** It holds per occurrence. Rejection
is decided per occurrence, so the same *string* can be rejected in one place and claimed in
another. For example, `1025` is rejected in Ana B's 2019 numbered folders but Confirmed in Irene's
2026 `Irene_1025_Met_2DG_Males` (95 animals found, all born 2026). `0619`, `1019` and `1519`
appear in free filename positions *inside* their own claimed trees. And the 3-digit `118` is
rejected in `Lucia Lungs 118` (a second chunk), yet it is the (A) claim at the head of `118 LUCIA`.

**Safety net.** For every rejected occurrence of a valid code in a filename, the project the file
actually received was compared with the code (`safety_net.csv`). Every unclaimed or different case
was read by hand and is explained in [§5](#5-files-with-no-claim), [§6](#6-conflicts) or
[§4.2](#42-files-demoted-one-by-one). Two genuine misses found this way were **fixed**:

- `0219_ctrl_ID29_…czi` (9 files) and `ID6B_2_0423_HE10x.czi` now count: a code in the same
  filename as an animal id is a claim.
- `AE-biomagune-0721_v3.docx` is now caught: the AE match ignores case.

---

## 9. For the coordinator

1. **Nothing here is ingested, created or written to `J:\`.** Every new project in [§1.2](#12-new-ae-biomagune-projects--for-approval)
   and [§3](#3-b-new-project-nnnn-projects), and the (A) correction, needs Ryan's approval first.
2. **Corrections to the hub brief (§7.4):**
   - `Cardiac MRI.zip` holds **only** `Proyecto 0619 (Ratones Hipoxia)` and `Proyecto 1519
     Santander`. `Proyecto 0320` is inside `Drive Maria Jesus and Irati 20211209.zip`, together
     with `0118`, `0219`, `0420`, `0521`/`0720`, `0619`, `1019`, `1116`, `1319`, `1420` and `1520`.
   - That archive is the Maria Jesus/Irati group's **project library**: CEEA paperwork, MRI
     NIfTI/segmentations and analysis.
3. **The claimed data is far from microscopy-only.** The ingest sessions need an ecosystem
   decision here:
   - **MRI (Bruker and NIfTI):**
     - Laura's backup `Proyectos_Laboratorio_Laura\{MRI,Lung-surfactant}` (the `jrc…_0721` and
       `…_1321` studies, about 11,500 files);
     - `Cardiac MRI.zip` (1519 and 0619);
     - Haizpea's `project0420` MRI;
     - `Claudia\Biodistribution 3D images` (0721, 2024).

     All of it predates or overlaps the internal MRI pull, whose earliest date is 2022-01-10.
     **Anything before 2022 here exists only on these drives.**
   - **PET/CT:** Peio's `1319` (2021-05, Molecubes) belongs to the NI archive's era. Check it
     against production NI before treating it as new.
4. **Subject ids.** `file_claims.csv` and `archive_member_claims.csv` carry 723 distinct ids, all
   re-resolved against a fresh DB connection ([§11](#11-verification)). They are assigned only to
   `ID<n>`/`m<n>` tokens on Confirmed/(A) rows. AxioScan suffixes (`…__0024_30H`) and lead numbers
   (`131L_…`) are used for cross-checks but get no id.
   - The **null-alias protocols** `0219`, `0618`, `0619`, `1521` compose correctly, because
     `compose_subject_id` receives the code from the path, so the guard never fires. **No id reads
     `-None`.**
   - The 12 ids on the (A) rows are valid only if Ryan approves the correction.
5. **Facility-DB anomalies seen in passing** (not ours to fix, for the facility-DB ask):
   - `AE-biomaGUNE-1519`: `end_date 2019-03-01` is earlier than `start_date 2020-03-01`.
   - 1321's animal 61 has a procedure dated `0023-08-07`.
   - `0126` and `0821` contain `1970-01-01` dates of birth. The date check ignores dates of birth
     before 1990.
6. **Dedup is not done here.** The same claim appears on both drives (for example `AINHIZE\1123`
   on drive 1 and drive 2), and 80 claims (13,941 files) sit inside the Toshiba **backup copy**.
   Choosing a canonical path per checksum belongs to the ingest and catalog sessions.
7. **Reproducing the run.** `python tools/drive_staging/project_claims.py` takes about 2 minutes
   once `archive_members.json` is cached; the first run lists the archives, and `Simu_2_V_XYZ.zip`
   alone is a 97 GB scan. The only listing error is that zip: it is truncated at source, and 7-Zip
   still lists its 318 members.
8. **Not decided here, left to Ryan:**
   - the `AINHIZE`/`Marta` researcher question ([§7](#7-researchers));
   - the procedure-date readings in [§4.2](#42-files-demoted-one-by-one);
   - `Project-0521` ([§3](#3-b-new-project-nnnn-projects));
   - whether paperwork-only projects deserve folders ([§1.2](#12-new-ae-biomagune-projects--for-approval)).

---

## 10. Worked examples

These were hand-checked end to end against a **fresh** DB connection with no cache: path → token →
verdict → the DB rows.

| # | Path (abridged) | Token and source | Verdict | DB rows that decide it |
|---|---|---|---|---|
| 1 | d2 `CELL OBSERVER 2\AINHIZE\AXIOSCAN\…\ID239\MFB_AUA_1123_ID239Lu_TM_10x_ROI lobulo 1.czi` | `1123`, MFB slot, AUA | **Confirmed** `AE-biomaGUNE-1123`, `239-AE-biomaGUNE-1123` | project 135, 2024-05-14 → 2029-05-14. Animal 239: male mouse, born 2025-11-27, CT and intratracheal administration 2026-01/02. File dated 2026-06-29. |
| 2 | d2 `…Irene_1125_Santander\Axioscan_1125_TM_260724\MFB_MBC_1125_ID10H_TM_10X.czi` | `1125`, MFB slot, MBC | **Confirmed**, `10-AE-biomaGUNE-1125` | animal 10: born 2026-03-19, MRI 7T 2026-06/07. File dated 2026-07-24. All 12 animals in the folder found. |
| 3 | d2 `…Irene_0424_Viejos machos\Axioscan_0424\Axioscan_0424_HE\2026_01_12__10_33__0024_30H.czi` | `0424`, folder chunk. `0024` rejected as an AxioScan counter. | **Confirmed**, no subject id (suffix animal) | animal 30 of 0424: born 2024-01-04, procedures to 2025-07. All 13 suffix animals in the folder found. |
| 4 | d1 `Cell observer\AINHIZE\MARINA\PR REPETICIÓN\Grupo D\0219_ID39_PR_10x.czi` | `0219`, next to an animal | **Confirmed**, `39-AE-biomaGUNE-0219` | **null alias** (`projectAlias` NULL; resolves through `project_code`). Animal 39: born 2021-12-30, MRI 7T 2022-02/03. |
| 5 | d1 `Cell observer\Marta\WGA_1422_MJS\ID49HL-1422_20x_VD-1.czi` | `1422`, next to an animal | **Confirmed**, `49-AE-biomaGUNE-1422` | animal 49: born 2024-02-29, PET 2024-05-27. File dated 2024-08. |
| 6 | d2 `…Toshiba…\In vivo\Cursosurf_0219\20220622_090338_jrc220622_m1_1321_1_1\9\pdata\1\2dseq` | `1321` (Bruker study) nested in `0219` | **Confirmed 1321** (conflict decided) | 1321's animal 1: born 2022-04-07, CT and intratracheal administration 2022-06-06 → 06-20. 0219's animal 1: born 2019, **perfused 2019-12-18**. |
| 7 | d1 `Drive Maria Jesus and Irati…zip!…Proyecto 0619…\20210927_135508_jrc210927_m167_0619_1_1\Segmentation_time10_m167_1019.nii.gz` | `1019` in the filename, nested in `0619` | **Confirmed 0619** (the outer claim wins) | 0619's animal 167: female, born 2021-07-08, **fasting 2021-09-27**, the scan date. 1019's animal 167: male, first procedure 2022-09. |
| 8 | d1 `Cell observer\AINHIZE\118 LUCIA\Lucia Lungs 118\COLOCALIZACION\131L_MPO_20X_1.czi` | `118`, folder head | **(A)** → `AE-biomaGUNE-0118` | `0118` (null alias): rats. Animal 131: female *Rattus norvegicus*, born 2019-12-09, **perfused 2020-02-04**. Slides dated 2022-11 onward. |
| 9 | d1 `Drive Maria Jesus and Irati…zip!…Pili y Mili\Proyecto 0521 iNO\…` | `0521`, keyword `Proyecto` | **(B)** `Project-0521` | no row for `0521` in `projects` at all. |
| 10 | d1 `Cell observer\AINHIZE\Claudia\Uptake MDA-MB-231 ccMn-doxo\2503\24h_ctrl_1.czi` | `2503`, whole folder | **(C)** | no row for `2503`, and no valid typo candidate. Reads as 25-03; the files are dated 2024-03-25. |
| 11 | d1 `Cell observer\Maria Jesus\230620-TOM20-MTCOI-0522\ID187_10x.czi` | `0522`, folder chunk. `230620` masked as a date. | **(C)** for this file; the claim is Confirmed | 0522 has 161 animals, and the lookup for 187 returns `not_found`. |
| 12 | d1 `…MJS_IF\230518-Alphasma-8ohdg\Proyecto 0522 8OHdG\230519-ID137-alphasma8OHdG-lungs-20x-1.czi` | `0522`, keyword | **(C)** for this file | 0522's animal 137 was **born 2025-01-16**. The file is dated 2023-05-24. |
| 13 | d1 `Former students\Ana B\Ga-IONP RGD peptide\MRI\…\mapas T2\Basales\1024_basal.avi` | `1024` | **rejected** (numbered sibling series) | `1024` *is* a protocol (project 142, **started 2024-10-24**). The files are from 2019, next to `1025 1026 1027`. |
| 14 | d1 `Cardiac MRI.zip!…Proyecto 1519 Santander\Basal\Segmentaciones\20200831_081827_jrc200831_m1_1519_1_1\…` | `1519` (Bruker study) | **Confirmed**, `1-AE-biomaGUNE-1519` | animal 1: born 2020-07-02, **MRI 7T 2020-08-31**, the study date. |
| 15 | d1 `Cell observer\AINHIZE\1123\ID 135-153\TM\1321_ID61_lung_TM_10x tiles.czi` | `1321` in the filename, nested in `1123` | **(C)**, ambiguous | 1321's animal 61: born 2023-06-08, **organ sampling 2023-08-29**. 1123's animal 61: born 2024-08-01, tattoo only. File dated 2025-07-28. |
| 16 | d1 `Former students\Peio\Projects Peio\Hígado\1319\210514\29\1319_ID29_corregPETCT_SUV.nii` | `1319`, next to an animal | **Confirmed**, `29-AE-biomaGUNE-1319` (**NEW**) | animal 29: born 2020-10-17, MRI 11.7T 2021-05-13, **PET CUBES-1 2021-05-14**, the scan date. |
| 17 | d1 `Cell observer\Maria Jesus\MJS-Proyecto 1019-3 Viejos 8OHdG\230519-ID160-alphasma8OHdG-lungs-20x-1.czi` | `1019`, keyword (`-3` is a sub-series) | **Confirmed**, `160-AE-biomaGUNE-1019` | animal 160: born 2021-03-18, aged cohort (procedures 2022-09). Slides 2023-05, consistent with "Viejos" (old mice). |

---

## 11. Verification

These are the checks from handoff §6, run against the final outputs and a fresh DB connection. **All
passed.**

| Check | Result |
|---|---|
| `file_claims.csv` has exactly 78,839 rows, and every manifest path appears once | 78,839 rows, 78,839 distinct, 0 missing, 0 extra |
| Every Confirmed/(A) claim names an animal the DB found, or says why it is confirmed without one | 1,116 name a found animal; 120 say "confirmed WITHOUT animal-level evidence (dates only)"; 0 violations |
| No proposed project is built from a rejected token | holds per occurrence; string overlaps explained in [§8](#8-rejected-tokens) |
| Every Confirmed/(A) code passes a fresh `valid_protocol_codes()` check | 26 codes, all in the fresh set of 140 |
| Every subject id re-resolves fresh to itself, on a Confirmed/(A) row of the same project | 723 distinct ids (110,931 rows), 0 failures, 0 misplaced |
| The codes behind existing production projects come out Confirmed | `0424`, `0522`, `0525`, `1022`, `1123`: all Confirmed |
| Hand-check at least 15 claims end to end | 17, in [§10](#10-worked-examples) |

`python tools/animal_db.py --check` printed `OK` at 16:19 on 2026-09-29. No lookup returned
`unreachable`; the script aborts on one rather than reading an outage as "not found".

---

## Outputs

All regenerable, in `D:\projects\gjesus3\staging\_analysis\codes\`:

| File | Rows | What |
|---|---:|---|
| `claims.csv` | 1,347 | One row per claim: 1,241 active, plus 106 *shadowed* claims, whose every file has a nearer claim. Columns as in the handoff, plus `phrasing` and `segment`. Also committed as [`tasks/drives_project_claims.csv`](drives_project_claims.csv). |
| `file_claims.csv` | 78,839 | One row per manifest file. `verdict` is one of CONFIRMED, A, B, C, NO-CLAIM, or ARCHIVE; ARCHIVE means an archive whose members carry claims, resolved in the next file. |
| `archive_member_claims.csv` | 100,982 | One row per member of the **4** archives that hold a claim: `Cardiac MRI.zip`, `Drive Maria Jesus and Irati 20211209.zip`, `Haizpea_2020-2022.7z` and `PR-0721-Biod-May23.zip`. Same columns, plus size and member date. `LEONE.zip`, `Simu_2_V_XYZ.zip`, `Drive zuri 170823.zip`, `Manon.zip` and the small tree archives hold no claim. |
| `noclaim_groups.csv` | 291 | The `(researcher, series)` groups of [§5](#5-files-with-no-claim). |
| `rejected_tokens.csv` | 57,487 | [§8](#8-rejected-tokens). |
| `safety_net.csv` | 29 | Rejected occurrences whose value is a valid code, for review. |
| `archive_members.json`, `db_cache.json` | — | Caches: archive listings keyed by sha256, and DB lookups, `found`/`not_found` only. |
| `run_summary.txt` | — | Counts, the conflict groups, listing errors. |
