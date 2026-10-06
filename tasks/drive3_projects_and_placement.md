# Drive 3 (M. Jesús): projects, descriptions and the non-raw placement plan (part A2)

**Status:** 🔶 DRAFT for the coordinator and Ryan · **Date:** 2026-10-06 · **Branch:** `review/drive3-mjesus-assessment` (not committed)
**Read-only:** nothing was written to `J:\` or `K:\`; the animal-facility DB got `SELECT`s only; `reopen_project.py` and the placement tools were **not run**.
**Scripts:** [`tools/drive_staging/drive3/a2_*.py`](../tools/drive_staging/drive3/) · **Outputs (regenerable):** `D:\projects\gjesus3\drive3_analysis\a2\`
**Units:** GB = 10⁹ bytes. The hub's brief divides by 1024³ and calls it GB, so its figures read about 7 % lower.

---

## Summary

### The five numbers that matter

1. **The non-raw material is 89,640 files, 208.7 GB, not the hub's 124 GB.** The difference is 42,407 `Splits` MetaImage volumes (`.mhd` + `.raw`, 84.6 GB) that the hub counted as raw Bruker. They are derived volumes cut from MRI exams, so they are non-raw (Ryan, 2026-10-01). The raw imaging (part A1's) is 525,935 files, 1,472 GB; junk is 6,394 files, 0.26 GB.
2. **Already in production, by SHA-256: 19,599 non-raw files, 21.1 GB.**
   - 18,994 of them are already in the **same** project, placed from drives 1+2. By the source each index records: 14,916 came from drive 1's `Drive Maria Jesus and Irati 20211209.zip` (an older copy of `Pili y Mili`), 4,054 from `Cardiac MRI.zip`, 20 from `Haizpea_2020-2022.7z`, and 4 were loose files on drive 2.
   - 605 are in the drives 1+2 holding folder.
   - None of them is in `/raw/`.
   - I checked every one of the 17,346 NAS copies they match: each exists, with the same size.
3. **To place (recommended reading, below):**
   - **now:** 29,794 files, 75.5 GB, into 15 projects (13 that exist, plus the 2 new projects the 0118 ruling would create);
   - **after `AE-biomaGUNE-1121` is reopened:** 3,975 files, 8.4 GB;
   - **if `1521` and `0618` are reopened:** 19 documents (D4);
   - **holding folder:** 3,514 files, 40.1 GB, of which 27.8 GB is the pig pulmonary-artery segmentation folder (1,956 files);
   - **deferred:** `biomaGUNE MJ`, 26,379 files, 50.9 GB.
4. **Every protocol code on the drive is already a gjesus3 project.**
   - The engine that classified drives 1+2 made 4,225 claims: 4,165 Confirmed, 1 (A), 5 (B), 54 (C).
   - Per file, that is 564,360 Confirmed, 46,072 (C), 26 (B) and 11,511 with no claim.
   - No new `AE-biomaGUNE-NNNN` project is needed. The only codes the DB does not hold are `0720`, already folded into `Project-0521`, and `0924`, which is 2 CEEA documents.
5. **`AE-biomaGUNE-1121` can be reopened cleanly.**
   - It has 546 MRI acquisitions, dated 2022-03-29 to 2022-09-22, and every one is in `/raw/`.
   - All 546 links come back under the names they had before the 2026-07-14 close-out, which match that close-out's listing exactly.
   - Nothing collides and nothing stops the tool.

### Decisions for Ryan, each with a recommendation

| # | Decision | Recommendation |
|---|---|---|
| **D1** | **0118: the split you ruled on does not match the animals.** The DB logs two rat PAH models under 0118: a subcutaneous dose plus "Hipoxia", and "I.P. Administration". The drive's folders mix them:<br>• the 2021 `respiracion` rats inside `MRI\Proyecto 0118 (Ratas hipoxia)` are the `Rata MCT` animals (I.P. administration, no hypoxia);<br>• Lucia's slides, already in `AE-biomaGUNE-0118` (described as "Monocrotalina"), are 4 I.P. animals and 2 hypoxia animals from one Jan–Feb 2020 experiment.<br>Details in §4.6. | **Option U:** keep all of protocol 0118 in the existing `AE-biomaGUNE-0118`, and have its description name both models. If you keep a split, use **option E**: `AE-biomaGUNE-0118` is Monocrotalina, and only `Proyecto-0118-rats-hipoxia` is created. Option R would create a `Proyecto-0118-Monocrotalina` that receives **3** new files, because 19 of its 22 already sit in `AE-biomaGUNE-0118`. |
| **D2** | **Approve four readings** (R1–R4, §4.3): 4,285 files, 8.8 GB that the engine left blank and the evidence ties to a project. The biggest is R1, the `Pili y Mili\Proyecto 0522  PAH` folder (2,301 files): the engine failed it as a whole because of one subfolder. | Approve all four. Each one only fills a blank; none overrules a claim. |
| **D3** | **Duplicate copies within one project.**<br>• All copies: 43,199 files, 136.1 GB. This is the drives 1+2 precedent.<br>• One study folder per content, with every copy inside that folder kept: 37,302 files, 124.0 GB.<br>• One copy per project: 35,299 files, 122.2 GB. | **One study folder per content.** It removes 12 GB of twin folders (for example the numbered folders that duplicate `PET\0320\CAV1 Enero 2022`) and leaves every placed folder complete. |
| **D4** | **Two closed projects, with no ruling, would receive files:**<br>• `AE-biomaGUNE-1521` (Fumadores): 9 documents;<br>• `AE-biomaGUNE-0618` (Ratas PAH): 10 documents. | Reopen both, case by case under 05_PROJECTS §4.y. Both folders still exist (closed, with 44 and 63 links). |
| **D5** | **25 files are already placed by drives 1+2 under a different project from the one drive 3 files them under.**<br>• 21 are the 1121 CEEA application documents, which drive 1 placed in `1019`.<br>• 3 are `0721`/`1116` paperwork.<br>• 1 is `1521`/`1520` paperwork. | Also place them in drive 3's project. The same document in two projects is harmless (the drives 1+2 precedent). |
| **D6** | **Descriptions:** 17 proposals in one format (§2). | Apply them once D1 is settled. |
| **D7** | **197 histology exports in `Proyecto 0522  PAH\IFs and histologies` stay (C).** Their animal numbers cannot be 0522's, and every one of them exists in 0619, with organ sampling or perfusion before the slide date (§4.3). | Ask M. Jesús in one line. The rule does not let a DB check overrule the 0522 folder. |
| **D8** | **`Otros\PH_analysis_Segmentation_tool`** is the group's own 3D Slicer module with trained models (2.9 GB). It belongs to no project. | Put it in holding now. Decide whether in-house tools get a home of their own. |
| **D9** | **`projects_closed\`**: the spec and tool change (§7). | Settle the open questions in §7 first, Q1 (retention) above all. |

---

## 1. The drive's project folders against today's registry (HANDOFF §6.1)

**Method.** I ran the same engine that classified drives 1+2 (`tools/drive_staging/project_claims.py`, Ryan's rule of 2026-09-29) over the whole drive-3 manifest, without changing it ([`a2_claims.py`](../tools/drive_staging/drive3/a2_claims.py)). It worked on all 621,969 files and the 2 small zips. The DB held 140 valid protocol codes, and the run made 759 fresh lookups with 0 errors.

[`a2_project_map.py`](../tools/drive_staging/drive3/a2_project_map.py) then maps every claim to today's registry (`claims_today.csv`, 4,663 rows), and lists **119 outermost folders** whose own name carries a code (`project_map.csv`). These are the 29 `Proyecto` folders the hub found, plus `PET\XXXX`, the `biomaGUNE MJ` folders, and the codes deeper down in `Microscopio` and `Otros`.

**Today's projects (§1 table of the HANDOFF):**
- `0118` is `PROJ-0060`, `1319` is `PROJ-0061`, `1420` is `PROJ-0063`, `Project-0521` is `PROJ-0065`.
- `1019`, `0320` and `1519` have been reopened.
- **`1121` (`PROJ-0009`) is closed and has no folder.**
- `1521` (`PROJ-0003`) and `0618` (`PROJ-0005`) are closed, but their folders exist.

### 1.1 The hub's 29 `Proyecto` folders, plus PET

Columns: all files on the drive, then the non-raw ones (mine); the project today; and what each file's own claim resolves to.

| Folder on the drive | Engine at the folder | Files / non-raw | Project today | Per-file outcome |
|---|---|---:|---|---|
| `Pili y Mili\Proyecto 0118 Monocrotalina` | Confirmed | 28 / 22 | `AE-biomaGUNE-0118` PROJ-0060 active | all 0118 |
| `Pili y Mili\Proyecto 0219 Fibrosis` | Confirmed | 3 / 2 | PROJ-0017 active | all 0219 |
| `Pili y Mili\Proyecto 0320 PAH KO` | Confirmed | 1,143 / 1,077 | PROJ-0007 active | 1,141 0320; 2 C |
| `Pili y Mili\Proyecto 0420 Infarto` | Confirmed | 2 / 1 | PROJ-0012 active | all 0420 |
| `Pili y Mili\Proyecto 0424 Envejecimiento y PAH` | Confirmed | 927 / 837 | PROJ-0002 active | all 0424 |
| `Pili y Mili\Proyecto 0521 iNO` | (B) | 30 / 23 | `Project-0521` PROJ-0065 active | 26 Project-0521 (the `0720` fold included); 4 C |
| `Pili y Mili\Proyecto 0522  PAH` | **(C)**, cross-check failed (§4.3 R1) | 6,855 / 6,415 | PROJ-0011 active | 3,833 0522 (deeper claims); 3,022 C |
| `Pili y Mili\Proyecto 0525 2DG y manosa` | Confirmed | 23 / 20 | PROJ-0001 active | all 0525 |
| `Pili y Mili\Proyecto 0619 Ratones PAH` | Confirmed | 7,734 / 7,279 | PROJ-0004 active | 7,278 0619; **348 0522; 23 0721; 14 1019**; 71 C |
| `Pili y Mili\Proyecto 0721 Contraste` | Confirmed | 10 / 7 | PROJ-0010 active | 9 0721; 1 C (a `1116` document) |
| `Pili y Mili\Proyecto 1019 + 1121` | two codes | 100 / 87 | — | **all 100 (C)**: the folder names two protocols |
| `Pili y Mili\Proyecto 1019 Envejecimiento y dieta` | Confirmed | 26,205 / 11,829 | PROJ-0006 active (reopened 09-30) | 26,203 1019; 2 C |
| `Pili y Mili\Proyecto 1121 London` | Confirmed | 4,483 / 4,049 | PROJ-0009 **closed, no folder** | 4,412 1121; 71 C |
| `Pili y Mili\Proyecto 1123 Bleomicina model` | Confirmed | 45 / 40 | PROJ-0014 active | all 1123 |
| `Pili y Mili\Proyecto 1319 Biodonostia` | Confirmed | 4 / 3 | PROJ-0061 active | all 1319 |
| `Pili y Mili\Proyecto 1321 Fibrosis` | Confirmed | 2 / 1 | PROJ-0018 active | all 1321 |
| `Pili y Mili\Proyecto 1420 miRNA` | Confirmed | 26 / 21 | PROJ-0063 active | 24 1420; 2 C (a `0924` document) |
| `Pili y Mili\Proyecto 1422 Metformin` | Confirmed | 2,414 / 2,255 | PROJ-0013 active | 2,413 1422; 1 C |
| `Pili y Mili\Proyecto 1519 Santander` | Confirmed | 1,304 / 1,253 | PROJ-0008 active (reopened) | all 1519 |
| `Pili y Mili\Proyecto 1521 Fumadores` | Confirmed | 18 / 12 | PROJ-0003 **closed** (folder exists) | 16 1521; 2 C (a `1520` and a `1122` document) |
| `MRI\Proyecto 0118 (Ratas hipoxia)` | Confirmed | 29,534 / 1,179 | PROJ-0060 active | all 0118 (D1) |
| `MRI\Proyecto 0320` | Confirmed | 35,513 / 1,973 | PROJ-0007 active | all 0320 |
| `MRI\Proyecto 0522` | Confirmed | 59,169 / 3,826 | PROJ-0011 active | all 0522 |
| `MRI\Proyecto 0619` | Confirmed | 114,222 / 5,499 | PROJ-0004 active | 113,446 0619; **540 1116** (`Flujo\…\20191107_094322_JRC191107_1116_m179_flow_1_1`); 236 C |
| `MRI\Proyecto 1019` | (outer folder; every file has a nearer claim) | 67,589 / 1,914 | PROJ-0006 active | all 1019 |
| `Otros\Proyecto 0618 Ratas PAH` | Confirmed | 15 / 10 | PROJ-0005 **closed** (folder exists) | all 0618 |
| `Otros\Proyecto 1519 Santander` | Confirmed | 3,141 / 3,032 | PROJ-0008 active | 3,139 1519; 2 C |
| `biomaGUNE MJ\…\Proyecto 1123 Bleomicina model` | Confirmed | 786 | PROJ-0014 | (deferred, §6) |
| `biomaGUNE MJ\Proyecto 0522-PAH metformina male.pptx` | a file, not a folder | 1 | PROJ-0011 | (deferred) |
| `PET\0320` | Confirmed | 88 / 58 | PROJ-0007 | 87 0320; 1 C |
| `PET\0522` | Confirmed | 192 / 118 | PROJ-0011 | 113 0522; **79 C**: the date folder `2302-PAH male` (§4.3 R3) |
| `PET\0619` | Confirmed | 503 / 364 | PROJ-0004 | all 0619 |

**The rest of the 119** are in `project_map.csv`:
- the 5 `biomaGUNE MJ` project folders (§6);
- 35 `Microscopio` folders named for `0424`, `0522`, `0619` or `1019`;
- 4 `Otros\Segmentaciones ITK SNAP` folders named for `Proyecto 0619` or `Proyecto 1019`;
- 3 study-level `1019` folders under `MRI\Comparasion expiration vs inspiraiton`;
- **36 pig folders, where the engine read a DICOM series number as a code** (`HEARDSMRI2327P_1_2200`, giving `2200`). Every one of these is (C). They are not protocol claims; see §5.

### 1.2 Codes that name a different protocol inside a project folder

`foreign_codes.csv` lists them, as resolved by the engine per file:
- `MRI\Proyecto 0619` holds a `1116` flow study from 2019-11 (540 files).
- `Pili y Mili\Proyecto 0619 Ratones PAH` holds:
  - `0522` material (348 files: `1-Female vs Male\MRI\Cardiac MRI`, `Varios\MJ_Curvas Presion\0522-Normoxia HCH-MJS`, and the CEEA continuation `Varios\Proyecto animalario\Continuación proyecto`. **0522 is filed as 0619's continuation**);
  - `0721` flow tests (23 files);
  - `1019` pressure curves (14 files).
- `Microscopio\CELL OBS MARTA\PR_0522_MJS_Paper aging` holds 8 `1019` `.czi`.

The CEEA paperwork also cross-files between related protocols (`1116` in `0721 Contraste`; `1520` and `1122` in `1521 Fumadores`; `1121` in `1019`'s `Modificación proyecto`; `1019` in `1121`'s `Informacion proyecto`). The engine sends such nested documents to (C).

### 1.3 Codes not in the registry, checked against the animal DB

**Every Confirmed or (A) code is a project today:** 0118, 0219, 0320, 0420, 0424, 0522, 0525, 0618, 0619, 0721, 1019, 1116, 1121, 1122, 1123, 1319, 1321, 1420, 1422, 1519, 1520, 1521.

The (B) claims, which the DB does not hold:
- **`0521`** is `Project-0521`.
- **`0720`** is `Pili y Mili\Proyecto 0521 iNO\Antiguo proyecto 0720`, 4 documents. It folds into `Project-0521` under Ryan's ruling of 2026-10-02.
- **`0924`** is `Pili y Mili\Proyecto 1420 miRNA\OH\AE-biomaGUNE-0924v02.docx` and one more document. The DB has no `0924`, and none of its 10 one-digit-off candidates passes. Its files drop to (C) because they are nested inside `1420`. **No project for it:** 2 documents do not justify one, so they go to holding.

**One trap for anyone reusing `nonraw_placement.py`:** its `project_for()` sends **every** (B) to `Project-0521`. That was right for drives 1+2, but it would wrongly send `0924` there. [`a2_placement.py`](../tools/drive_staging/drive3/a2_placement.py) maps (B) explicitly.

---

## 2. Descriptions (HANDOFF §6.2)

**The format, one rule for every row:** `<drive wording>[ (also named <w2>; <w3>)]. <today's description, unchanged>`.

How it is applied:
- **The wording** is the drive's own project-folder name. A `Pili y Mili\Proyecto XXXX …` name is preferred, because that is the group's own convention. After it come `MRI`, `Otros`, `PET` and `Microscopio`, then the `biomaGUNE MJ` names.
- **Only names that add words count.** `Proyecto 0619` and `0619` do not. Neither does a name that names two protocols: `PAH diets_Proyecto 0619 & 0522` describes neither of them alone.
- **Unchanged where the wording is already there:** the projects PROJ-0060…0065 already follow this style (`Animal protocol AE-biomaGUNE-1420 (Proyecto 1420 miRNA). …`).

The full text is in `descriptions.csv`, UTF-8 with a BOM.

| Project | Drive's wording(s) | Proposal (today's text follows unchanged) |
|---|---|---|
| `AE-biomaGUNE-0118` | `Proyecto 0118 Monocrotalina`; `Proyecto 0118 (Ratas hipoxia)` | **pending D1** |
| `AE-biomaGUNE-0219` | `Proyecto 0219 Fibrosis` | `Proyecto 0219 Fibrosis. Auto-created from internal MRI ingest; …` |
| `AE-biomaGUNE-0320` | `Proyecto 0320 PAH KO` | `Proyecto 0320 PAH KO. …` |
| `AE-biomaGUNE-0420` | `Proyecto 0420 Infarto` | `Proyecto 0420 Infarto. …` |
| `AE-biomaGUNE-0424` | `Proyecto 0424 Envejecimiento y PAH` | `Proyecto 0424 Envejecimiento y PAH. Auto-created during NI archive-mode ingest; … (funded project 1207). …` |
| `AE-biomaGUNE-0522` | `Proyecto 0522 PAH`; `Metformina Male PAH_Proyecto 0522` | `Proyecto 0522 PAH (also named Metformina Male PAH_Proyecto 0522). …` |
| `AE-biomaGUNE-0525` | `Proyecto 0525 2DG y manosa` | `Proyecto 0525 2DG y manosa. …` (the hub's own example) |
| `AE-biomaGUNE-0618` (closed) | `Proyecto 0618 Ratas PAH` | `Proyecto 0618 Ratas PAH. …` |
| `AE-biomaGUNE-0619` | `Proyecto 0619 Ratones PAH`; `PAH 2DG_Proyecto 0619 (female and male)` | `Proyecto 0619 Ratones PAH (also named PAH 2DG_Proyecto 0619 (female and male)). …` |
| `AE-biomaGUNE-0721` | `Proyecto 0721 Contraste` | `Proyecto 0721 Contraste. …` |
| `AE-biomaGUNE-1019` | `Proyecto 1019 Envejecimiento y dieta` | `Proyecto 1019 Envejecimiento y dieta. …` |
| `AE-biomaGUNE-1121` (closed) | `Proyecto 1121 London` | `Proyecto 1121 London. …` (apply at the reopen) |
| `AE-biomaGUNE-1123` | `Proyecto 1123 Bleomicina model`; `Bleomicina Mice_Proyecto 1123` | `Proyecto 1123 Bleomicina model (also named Bleomicina Mice_Proyecto 1123). …` |
| `AE-biomaGUNE-1319` | `Proyecto 1319 Biodonostia` | `Proyecto 1319 Biodonostia. Animal protocol 1319. Created during the historical-drives DICOM ingest (Peio's liver PET/CT, 2021). PROVISIONAL.` |
| `AE-biomaGUNE-1321` | `Proyecto 1321 Fibrosis` | `Proyecto 1321 Fibrosis. …` |
| `AE-biomaGUNE-1422` | `Proyecto 1422 Metformin`; `Manosa and 2DG Male_Proyecto 1422` | `Proyecto 1422 Metformin (also named Manosa and 2DG Male_Proyecto 1422). …` |
| `AE-biomaGUNE-1519` | `Proyecto 1519 Santander` | `Proyecto 1519 Santander. …` |
| `AE-biomaGUNE-1521` (closed) | `Proyecto 1521 Fumadores` | `Proyecto 1521 Fumadores. …` |
| `AE-biomaGUNE-1116`, `-1420`, `Project-0521` | — / already present | no change |

**`1422` has two descriptions on the drive:** `Metformin` in the shared folder, `Manosa and 2DG` in the researcher's own. The "also named" clause keeps both, so neither is lost. Whether the descriptions should also record where they came from (the M. Jesús drive, 2026-09) is a style choice; I left it to the CHANGELOG.

---

## 3. `AE-biomaGUNE-1121`: what the ruled reopen would do (HANDOFF §6.3)

[`a2_reopen_1121.py`](../tools/drive_staging/drive3/a2_reopen_1121.py) replays `reopen_project.py`'s decisions, read-only.

**`reopen_project.py` was not run.** Its own `--dry-run` writes nothing: every write sits behind `if not dry` (backup, skeleton, `_project.yaml`, links, the registry lock and row, `index.html`). But the instruction was not to run it, so instead the script imports only the tool's read-only helpers and replays steps 4 and 5:
- `link_names_from_provenance`, `closeout_backup_dir`, `sidecar_discovered`;
- `relink_projects.load_registry_index`, `raw_primary_path`, `load_link_template`;
- `resolver.resolve_link_filename` and `linker.inspect_link_target`, whose docstring says "Read-only".

| | |
|---|---|
| Acquisitions in `registry_raw.csv` with `PROJ-0009` | **546**, all MRI, 2022-03-29 → 2022-09-22, none shared with another project |
| In `/raw/` | **546 / 546** raw primaries exist; the coordinator's index has all 546 `ok` (12,867 files hashed); no tombstone names 1121 |
| Link names | **546 / 546 from provenance** (the 2026-07-14 close-out backup, `C:\Users\rtasseff\temp\gjesus3_backfill_backup_20260714\deleted_projects\proj-ae-biomegune-1121\`) |
| Against the close-out listing (`raw_linked.listing.txt`) | **546 / 546 identical**: every link the close-out removed comes back under its old name, and nothing more |
| Collisions / missing raw / unnamed | **0 / 0 / 0**: nothing would stop the tool |
| Registry row (step 5) | `status` closed → active; `start_date` 2022-03-29; `last_activity` 2022-09-22; `notes` += `Reopened <date> (<reason>).` |
| `_project.yaml` | from the close-out backup, migrated (`short_name:` → `name:`) |

**Then the drive's 1121 material can be placed:** 3,975 files, 8.4 GB, and the 21 CEEA documents of D5.

**A trap I hit:** MRI link names contain commas (`MRI_m1_1121_20220329_10_1,3`). Never split the close-out listing on commas.

---

## 4. The non-raw placement plan (HANDOFF §6.4)

### 4.1 The rules applied

Each one cites its source.

**Where the A1 / A2 line falls, per file** ([`a2_common.classify`](../tools/drive_staging/drive3/a2_common.py)). **A1 owns:**
- `.czi`, `.lif`, `.lifext`, `.lsm`, `.nd2`;
- every DICOM: `.dcm`, plus 35,184 extension-less `IM_####`/`XX_####`/`PS_####`/`DICOMDIR` files and 31 extension-less PMOD exports such as `m62_PETCTbrain`. All of these were confirmed by reading their `DICM` preamble ([`a2_dicom_magic.py`](../tools/drive_staging/drive3/a2_dicom_magic.py)); 17 extension-less files are not DICOM;
- every ParaVision scan file (`fid`, `2dseq`, `acqp`, `uxnmr.par/.info`, `.job0/1`, `AdjResult\…`).

**I own the rest.** That includes:
- **9,045 non-raw files, 9.5 GB, that sit inside ParaVision study folders:** `Splits\Predict_Slicer`, `Análisis MJ\…`, NIfTI exports. A1 should not count them as exam content.
- **TopSpin HR-MAS NMR**, which is not ParaVision. All 393 non-empty files are already in the drives 1+2 holding folder, under Ryan's NMR rule of 2026-10-02.
- **PET/CT companions** (`.txt`, `.nii`, `.mat`, `.voi`, `.xlsx`). A production PET/CT acquisition stores only `.dcm` (checked in the coordinator's index), so these are non-raw.

**Excluded, 6,394 files:**
- Ryan's ruled list: `desktop.ini` 5,048; AppleDouble `._*` 1,032; `Thumbs.db` 106; `.DS_Store` 99; the 2 WD installers.
- My additions, marked as such:
  - 60 Office temp files (`~$…`, `~WRL*.tmp`), which `catalog.py`'s "system" class already excludes;
  - 25 image-viewer caches (`folders.cache` / `thumbs.cache`, 217 MB, one of them 212 MB);
  - 22 macOS `Icon<CR>` files.
- 181 zero-byte non-raw files are counted, not placed (the drives 1+2 rule).

**Project per file:** the engine's verdict (Confirmed / A, or B as in §1.3). In the recommended column, a reading (§4.3) may fill a blank.

**Already in production** (HANDOFF §1: in `/raw/`, or placed by drives 1+2, or in their holding folder), by SHA-256 only:
- the coordinator's `prod_raw_sha256.csv`;
- every project's `working\historical_drives\_INDEX.csv` on the NAS (34,861 rows in 18 trees);
- the holding folder's `manifest.csv` (54,723 rows).

**A file with no project whose exact bytes sit elsewhere under a claim** is not placed again (`covered-by-twin`). The claimed copy carries the evidence. No inference about the unclaimed path is needed.

**Destinations** come from the shared rule `historical_paths.Planner`, unchanged:
- `<project>\working\historical_drives\MJesus-MFB\<study folder>\…`, at most 240 characters;
- the NAS `_PATHMAP.csv` and `_INDEX.csv` of each tree are loaded, so frozen names stay as they are;
- Ryan's "group under the parent" applies to `0721`, `1019`, `1123` and `1321`.

**Two adaptations, both stated:**
1. **`historical_paths` knows only drives `D1` and `D2`.** [`a2_common.py`](../tools/drive_staging/drive3/a2_common.py) registers `D3` → `MJesus-MFB` / `drive3_MJesus-MFB` in memory; the file is untouched.
2. **The rule says the study folder is "the outermost claim root".** `load_claim_roots` meant to count SHADOWED outer folders, but on drives 1+2 that branch never fired: the engine writes shadowed claims with an empty project (all 106 there). I count a shadowed folder for its own code when that code is Confirmed elsewhere on the drive (432 folders). The only effect is on `0619`: 10 study folders instead of 13.

**The drive label.** I would keep `MJesus-MFB`, as proposed. It is the volume label `MJesus-MFB-biomaGUNE` shortened, the same way `FRIO-X6` and `MFB-Disco-2` were made, and it has no accents. The full label would add 10 characters to every path, so more names would be cut.

### 4.2 The numbers

`placement\plan.log`, `per_project.csv`, `per_class.csv`. The recommended column uses D2 (readings) and D3 (one study folder per content).

| Decision | Engine only | **Recommended** |
|---|---:|---:|
| **place** (an active project) | 25,722 · 67.04 GB | **29,794 · 75.54 GB** |
| **place-after-reopen** (`1121`) | 3,975 · 8.38 | 3,975 · 8.38 |
| closed-project (`1521` 9, `0618` 10) | 19 · 0.01 | 19 · 0.01 |
| already-placed (same project, drives 1+2) | 18,994 · 20.99 | 18,994 · 20.99 |
| already-in-holding (drives 1+2) | 999 · 0.49 | 605 · 0.10 |
| placed-elsewhere (D5) | 25 · 0.01 | 25 · 0.01 |
| duplicate-copy (D3) | 5,684 · 11.76 | 5,897 · 12.07 |
| covered-by-twin | 220 · 0.56 | 257 · 0.69 |
| **holding** (new, no project) | 7,442 · 48.60 | **3,514 · 40.05** |
| deferred (`biomaGUNE MJ`) | 26,379 · 50.89 | 26,379 · 50.89 |
| exclude-zero-byte | 181 · 0.00 | 181 · 0.00 |
| in `/raw/` | 0 | 0 |
| **total** | 89,640 · 208.73 | 89,640 · 208.73 |

**Volume per project** (recommended scenario):

| Project | Place now | Already placed | Twins not placed (D3) | Deferred in `biomaGUNE MJ` |
|---|---:|---:|---:|---:|
| `AE-biomaGUNE-0619` | 7,348 · 31.02 GB | 4,997 · 6.50 | 1,759 · 5.33 | 6,963 · 10.96 |
| `AE-biomaGUNE-0522` | 7,800 · 16.16 | — | 2,519 · 4.34 | 7,447 · 10.02 |
| `AE-biomaGUNE-1019` | 5,836 · 10.61 | 9,087 · 9.36 (+393 HR-MAS in holding) | 916 · 1.11 | 1,681 · 5.08 |
| `AE-biomaGUNE-1121` (after reopen) | 3,975 · 8.38 | — | — | — |
| `AE-biomaGUNE-0424` | 1,091 · 6.16 | — | — | 1,259 · 2.56 |
| `AE-biomaGUNE-1122` (R4a) | 195 · 3.25 | — | — | — |
| `AE-biomaGUNE-1422` | 2,254 · 3.16 | — | — | 2,031 · 5.43 |
| `AE-biomaGUNE-0320` | 2,272 · 3.07 | 375 · 0.30 | 467 · 0.97 | — |
| `Proyecto-0118-rats-hipoxia` (D1) | 2,642 · 1.92 | — | 213 · 0.31 | — |
| `AE-biomaGUNE-1519` | 228 · 0.10 | 4,055 · 4.38 | — | — |
| `AE-biomaGUNE-0721` | 51 · 0.06 | — | 23 · 0.01 | — |
| `AE-biomaGUNE-0525` | 20 · 0.02 | — | — | — |
| `AE-biomaGUNE-1123` | 40 · 0.01 | — | — | 1,955 · 3.74 |
| `AE-biomaGUNE-1420` | 13 · 0.01 | 6 | — | — |
| `AE-biomaGUNE-0618` (closed, D4) | 10 · 0.01 | — | — | — |
| `AE-biomaGUNE-1521` (closed, D4) | 9 · 0.00 | — | — | — |
| `Proyecto-0118-Monocrotalina` (D1) | 3 · 0.00 | 19 (in `AE-biomaGUNE-0118`) | — | — |
| `AE-biomaGUNE-1321` | 1 · 0.00 | — | — | — |
| `AE-biomaGUNE-0219`, `-0420`, `-1319`, `Project-0521` | — | 2, 1, 3, 23 | — | — |

### 4.3 Readings (D2): evidence-based, for approval, never overruling a claim

[`a2_placement.py`](../tools/drive_staging/drive3/a2_placement.py) applies them only in the recommended column.

| Reading | What and why | Files · GB |
|---|---|---:|
| **R1** | **`Pili y Mili\Proyecto 0522  PAH`.** The engine's claim-level cross-check failed (`CL-1344`): of the 2,641 files that take the folder as their nearest claim, 197 have animal numbers 0522 cannot own. All 197 are in `IFs and histologies\{WGA, Elastic staining}`: IDs 121–161 were born in 0522 only in 2024–25, after the 2022–23 slides, and IDs 168–212 do not exist in 0522. **The other 2,444 files have no contrary evidence**: 1,971 `Proteomica`, plus PET/MRI/histology of `Machos PAH metformina Junio 2024`, documents and so on. Reading: 0522 for every file whose own evidence does not contradict it (the engine's own per-file test); the 197 stay (C). [`a2_db_evidence.py`](../tools/drive_staging/drive3/a2_db_evidence.py) shows **every** one of those animal numbers exists in **0619**, with organ sampling or perfusion before the slide date: they look like 0619's male-and-female cohort (D7). | 2,301 · 2.21 |
| **R2** | **`1010-3 MTCOI and TOM20`** is the engine's own (A) correction 1010 → 1019 (6/6 animals found), inside `Machos viejos-1019-3`. The engine treated the **identical** outer `1019` as a disagreement, and all 24 files dropped to (C). Read as 1019. | 24 · 2.32 |
| **R3** | **Date folders.** `2302-PAH male`, `2305-…`, `2306-…`, `Machos HCH diet-2311` are YYMM dates: the engine itself prints "reads as a date close to its files' dates". As a (C) claim, each such date shadows the valid outer `0522`. Read the outer claim. | 89 · 0.16 |
| **R4a** | **`PET\FDG-ratonesfumadores`** (no code) goes to **`AE-biomaGUNE-1122`**. **Production registers all 69 of its PET/CT acquisitions to PROJ-0057** (from the 2026-08 `S:\gnuclear` pull). The drive also holds `Animal list Proyecto 1122 Fumadores FJD.xlsx` in `Proyecto 1521 Fumadores\3ª tanda`. Its SUV volumes, segmentations and VOIs belong with those acquisitions. | 195 · 3.25 |
| **R4b** | **`Otros\Segmentaciones ITK SNAP\Segmentacion 2DG RATAS`** (no code) goes to the 0118 rats. 7 of its 11 study names are study folders under `MRI\Proyecto 0118 (Ratas hipoxia)`. The other 4 (`r115`, `r116`, `r117`, `r119`) are not on the drive's MRI tree, but **the DB logs an MRI for each on the study's own date in 0118, and in no other protocol** ([`a2_db_0118.py`](../tools/drive_staging/drive3/a2_db_0118.py)). | 1,338 · 0.48 |
| **R4c** | **`MRI\Comparasion expiration vs inspiraiton\Rata MCT`** (no code) goes to the 0118 rats. 213 files are byte-identical to `MRI\Proyecto 0118 (Ratas hipoxia)\respiracion\Segmentaciones splits`. Its 3 studies (`m175`, `m177`, `m178`, 2021-09-02) are logged in 0118 only, MRI on that date. | 338 · 0.38 |

The DB cross-check behind R4b and R4c covered 33 (subject, scan date) pairs in 0118-related study names. 32 are logged by 0118 only on that date; 1 (`m152`, inside the 0118 MRI folder itself) by no protocol.

### 4.4 Duplicates within the drive (D3)

The same bytes often sit in several places:
- 22,233 files duplicate drives 1+2, per the hub;
- inside drive 3, the same analysis sits under `Pili y Mili`, `MRI`, `PET` and `biomaGUNE MJ`.

Measured for what one project would receive:
- **all copies:** 43,199 files, 136.05 GB (the drives 1+2 precedent);
- **one study folder per content, every copy inside it kept:** 37,302 files, 123.98 GB (recommended);
- **one copy per project:** 35,299 files, 122.17 GB.

The canonical copy is chosen by: (1) the outermost study folder, so a project folder beats a file-name claim's own folder; then (2) the shared group folders before `biomaGUNE MJ` (`Pili y Mili`, `MRI`, `PET`, `Otros`, `Microscopio`); then (3) the shallower path.

Example: the `PET\CAV1 Enero 2022\<n>` folders are 51 of 52 files byte-identical to `PET\0320\CAV1 Enero 2022\<n>`. Under "all copies" they would become 6 extra study folders named `29`, `30`, … in `0320`; under the recommended rule they are recorded and not placed. Every not-placed copy keeps a `canonical_rec` column pointing at the copy that is placed.

### 4.5 Paths

`placement\path_stats.csv`, `study_folders.csv`.
- **37,302 destinations** (placed plus holding). The longest is **240**, and **0** are over the budget.
- **3,171 drive-3 folders, of which 166 (5 %) are shortened**, plus 61 file names.
- The longest paths are `1121 London\Experimentos\MRI\Septiembre 2022\Resultados\<study>\Time_10_rat_<study>.mhd`.

Study folders per tree:

| Project | Study folders | Notes |
|---|---:|---|
| `0619` | 10 | `Proyecto 0619 Ratones PAH`, `Proyecto 0619`, `0619`, plus the Microscopio folders such as `2DG Male 0619` |
| `1019` | 11 | `Proyecto 1019 Envejecimi~c3e8` (the same deterministic short name drive 1 got), `Machos viejos-1019-3`, `Masson_1019_MJS`, three `Splits_*` |
| `0522` | 4 | |
| `0320`, `0424` | 3 each | |
| everything else | 1–3 | |

`Otros\Proyecto 1519 Santander` and `Pili y Mili\Proyecto 1519 Santander` both land in `1519`; the second gets ` (2)`, as the rule requires.

**Before any of this is run**, these code changes are needed, each a small one:
- **`historical_paths.TAGS` / `DRIVE_LABELS`** gain `D3`.
- **`historical_paths.PROJECT_README` describes "two operator external drives"** and must name the third: WD My Passport, serial `WX22D623YP29`, a researcher's working drive. The holding README and the not-registered README text say the same.
- **`nonraw_placement.py`** needs `D3` in `DRIVES`. Its source is the staged copy on `J:\_staging_drive3_MJ\…\files\`, not D:. The copy would read and write through the workstation, about 84 GB.
- **`placement_plan.csv` is not in `nonraw_placement`'s manifest format.** The applying session either converts it or re-plans with the tool extended for `D3`, after Ryan's answers. That is the same `remap`/`plan` step as 2b.
- **A1's not-registered MRI exam folders** (spectroscopy, no `2dseq`, failed conversions; Ryan 2026-10-04: kept as other data with a README) will land in these same trees. Plan both together, so a study folder is not shortened twice.
- **The 18,297 segmentation-class files** (A3's subject) are placed like any other non-raw material: 6,907 now, 849 after the reopen, 5,762 already placed, and 1,989 pig files (27.8 GB) in holding. Placing them now as work in progress does not stop A3's later promotion into `curated_datasets\` (12 §3.2).

### 4.6 Protocol 0118: what each answer would mean (D1)

The facts:

**The DB (`SELECT` only).** `AE-biomaGUNE-0118` runs 2018-06-14 → 2023-06-13 and has 186 animals, all rats. The procedure log shows **two PAH models used side by side**:
- **`Admon. SC` + `Hipoxia`** (some with `Tratamiento en agua`):
  - the 2019-09 rats 111–117 (with 118–121 as no-hypoxia controls), the drive's `_2DG_` studies;
  - the 2020-01 rats 136–137;
  - the 2020-05 rats 152–156 and 169–173.
- **`I.P. Administration`** (no hypoxia):
  - the 2020-01 rats 131, 132, 144, 145;
  - the 2021-08 rats 175–178.

**The drive's folders do not follow the models:**
- `MRI\Proyecto 0118 (Ratas hipoxia)\respiracion` holds the 2021 I.P. rats `m175` and `m178`. They are the `Rata MCT` (monocrotaline) animals of `MRI\Comparasion…`.
- **Lucia's histology in `AE-biomaGUNE-0118`** (140 acquisitions, the (A) `118 LUCIA`; the project is described as "`Proyecto 0118 Monocrotalina`") is animals 131, 132, 144, 145 (I.P.) **and** 136, 137 (hypoxia), all perfused 2020-02-04/06.
- `Pili y Mili\Proyecto 0118 Monocrotalina` holds 28 files: CEEA paperwork and animal lists. **19 of its 22 non-raw files are already placed in `AE-biomaGUNE-0118`** (drive 1). 3 are new.

| Option | Projects | What the drive's 0118 non-raw material becomes |
|---|---|---|
| **R** (as ruled 2026-09-30) | new `Proyecto-0118-rats-hipoxia` + new `Proyecto-0118-Monocrotalina`; `AE-biomaGUNE-0118` stays | 2,642 files (1.92 GB) in rats-hipoxia, **including MCT rats**; 3 files in a near-empty Monocrotalina project whose other 19 already sit in `AE-biomaGUNE-0118`. **Three projects for one protocol**, and the split cuts across the animals. A1's 28 missing studies (2019–2021) would register to rats-hipoxia, although some are I.P. animals. |
| **E** | `AE-biomaGUNE-0118` = Monocrotalina (as described today) + new `Proyecto-0118-rats-hipoxia` | as R, but the 3 Monocrotalina files join `AE-biomaGUNE-0118`. The folder-versus-animal mismatch remains. |
| **U** (recommended) | `AE-biomaGUNE-0118` only; description names both models (for example `Proyecto 0118: ratas hipoxia y monocrotalina`) | everything in one project, 2,645 files, with study folders `Proyecto 0118 (Ratas hipoxia)`, `Proyecto 0118 Monocrotalina`, `Segmentacion 2DG RATAS`, `Rata MCT`; the raw ingest has one target |

Whichever option is chosen, the paths below `historical_drives\` are identical; only the base project folder changes. The plan was computed with R's names, so that the ruling is visible.

---

## 5. Folders with no code (HANDOFF §6.5)

[`a2_nocode.py`](../tools/drive_staging/drive3/a2_nocode.py) → `nocode_groups.csv`: 109 groups, 46,698 files, outside `biomaGUNE MJ`.

The evidence is measured, not read from names:
- production's own registration of any raw file in the group;
- byte-identical claimed copies;
- study names that match claimed study folders;
- the DB.

| Folder | Evidence | Verdict |
|---|---|---|
| `PET\FDG-ratonesfumadores` (264 files, 5.6 GB; 195 non-raw) | all 69 PET/CT `.dcm` already in `/raw/`, **registered to `AE-biomaGUNE-1122`**; `Animal list Proyecto 1122 Fumadores FJD.xlsx` | **corroborated → 1122** (R4a). Not 1520 or 1521: those have no acquisitions here, and production's registration decides. |
| `PET\CAV1 Enero 2022` (52 files) | 51 / 52 byte-identical to `PET\0320\CAV1 Enero 2022` (Confirmed 0320; also `Pili y Mili\Proyecto 0320 PAH KO\CAV1 KO Enero 2022`) | **same bytes as a 0320 copy**: placed through it, nothing to decide. The 52nd, `30\SUV-m30-0619.nii`, is (C) in both copies (named 0619, filed in 0320). |
| `Otros\Segmentaciones ITK SNAP\Segmentacion 2DG RATAS` (1,338) | 7/11 study names under `MRI\Proyecto 0118`; all 11 subject-date pairs logged in 0118 only | **corroborated → 0118** (R4b) |
| `MRI\Comparasion expiration vs inspiraiton\Rata MCT` (338) | 213 byte-identical to `…0118 (Ratas hipoxia)\respiracion\…`; 3 studies logged in 0118 only | **corroborated → 0118** (R4c); `…\Splits\…` in the same folder is 1019 by its own study claims |
| `Otros\Segmentaciones ITK SNAP\Segmentaciones Arteria Pulmonar cerdos` (37,140 files, 35.5 GB; 1,956 non-raw, 27.8 GB, all to holding) | pig MRI exports (`HEARDSMRI####P`, a clinical-scanner naming); no protocol code, only DICOM series numbers; `AE-biomaGUNE-CERDOS` (PROJ-0052) exists, but it holds Amanda's 2026 pig histology, and nothing ties the two | **(C) → holding**; A3 assesses it as a curated-dataset candidate |
| `Otros\PH_analysis_Segmentation_tool` (28 files, 2.9 GB) | in-house 3D Slicer module and trained `.h5` models; no project content | **not project data → holding** (D8) |
| `Pili y Mili\Draft papers` (2,373 files, 4.3 GB) | papers across projects: 904 files already placed in 1019 by drive 1, 902 twins of claimed files. Hints only: `Mpv17` ≈ 1121 London (Mpv17 knockout); `5-2DG` and `Publicados\2-DG` ≈ 1019; `1-PAH male vs female` ≈ 0619/0522; `3-PAH Dietas` ≈ 0522/0619; `4-PAH aging` ≈ 0424/1019 | **(C) → holding**. One 2b-style worksheet row per paper would let M. Jesús map them. |
| `Pili y Mili\Proyecto 1019 + 1121` (100) | the folder names two protocols; the DB does not separate them (shared animal numbers); content is `KO_ID…` cardiac MRI figures (Mpv17 knockout is 1121's model) | **(C) → holding**, hint 1121 |
| `Microscopio\…\{Machos vs Hembras, Male Diets, Female Diets}`, `Histologia_ratones_viejos`, `Microscopio biodonostia\{escaner, BIOMAGUNE}`, dated `CELL OBS MARTA` folders | mostly A1's `.czi`. **Production already holds 66 of the `Machos vs Hembras` `.czi` with a blank project** (the drives 1+2 ingest). The non-raw part is the `.tif` exports beside them (349 files, 4.4 GB in holding) | **(C) → holding**; map them with the `.czi` in the 2b round |

---

## 6. `biomaGUNE MJ`: inventory only (HANDOFF §6.6)

[`a2_biomagune_mj.py`](../tools/drive_staging/drive3/a2_biomagune_mj.py) → `biomagune_mj_inventory.csv`, at levels 2 and 3. Totals: **206,839 files, 285.4 GB**.

**87.0 GB of it exists nowhere else**: not elsewhere on the drive, not in `/raw/`, not placed or held by drives 1+2. **Only 12.5 GB of that is non-raw.**

| Subfolder | Files · GB | Main classes | Codes claimed (files) | Unique (non-raw) |
|---|---:|---|---|---:|
| `PAH 2DG_Proyecto 0619 (female and male)` | 44,896 · 65.6 | ParaVision 55.7, volumes 5.9, DICOM 3.9 | 0619 | **0.0** (100 % elsewhere on the drive) |
| `PAH diets_Proyecto 0619 & 0522 (female and male)` | 68,725 · 64.3 | ParaVision 47.6, volumes 10.1, DICOM 6.4 | 0522 48,013; 0619 15,046; C 5,666 | 0.01 |
| `PAH aged_Proyecto 0424 & 1019 (female and male)` | 31,099 · 51.6 | ParaVision 20.0, `.czi` 12.8, exports 8.7, volumes 6.3 | 0424 15,546; 1019 13,452; C 2,101 | 18.8 (4.9) |
| `Manosa and 2DG Male_Proyecto 1422` | 16,758 · 37.7 | `.czi` 17.2, ParaVision 12.4, volumes 3.8 | 1422 | **29.5** (3.2) |
| `Bleomicina Mice_Proyecto 1123` | 13,075 · 30.2 | ParaVision 24.0, volumes 2.9 | 1123 | **28.4** (3.7) |
| `Metformina Male PAH_Proyecto 0522` | 14,378 · 19.8 | ParaVision 9.5, `.czi` 5.2, volumes 3.2 | 0522 | 10.3 (0.5) |
| `PAH female and male_(Proyecto 0522 & 0619)` | 15,863 · 16.0 | ParaVision 7.6, volumes 6.1 | 0522 13,067; 0619 2,235; C 561 | 0.01 |
| `Proteomica` | 2,044 · 0.3 | documents, figures | none | 0.0 (identical to `Pili y Mili\Proyecto 0522  PAH\Proteomica`) |

**What this means for later:**
- Three subfolders are entirely copies of `Pili y Mili`, `MRI` and `PET`, and can be skipped.
- The unique part is the recent raw imaging of `1422`, `1123` and the `0424`/`1019` aged cohort, plus 12.5 GB of non-raw. **The raw is A1's question**: `Raw data\` subfolders, 2024–25 studies.
- Its project folders name two protocols at once (`0424 & 1019`, `0619 & 0522`, `0522 & 0619`), so the engine resolves it per file. **This is the least clean part of the drive for attribution.**

---

## 7. `projects_closed\`: what the spec says, the smallest change, open questions (HANDOFF §6.7)

**No spec edits were made.** This is a proposal.

### What the spec says today

`mfb-rdm-docs/05_PROJECTS.md`, read 2026-10-06:
- **§1** (warning) and **§2**: projects are "temporary working space … created, used, and then closed and **deleted**". Only `/raw/` and `/publications/` are permanent.
- **§4** ends the lifecycle at `DELETED`. All three closure options (promoted, exported, abandoned) end in deletion.
- **§4.x**: the close-out must first preserve `metadata\` into `/raw/`, and "**until this tool exists, projects should not be deleted** — pause them indefinitely".
- **§5 ✅ DECIDED**: "Projects are temporary and **deleted** at close-out". Deletion is blocked until the close-out tool exists.
- **§4.y ✅ DECIDED** (2026-09-30): reopen case by case (`reopen_project.py`).
- **§3a ✅ DECIDED**: folder contents are researcher-owned; `/raw/` + `registries\` are the system of record.

**The contradiction the hub noted is real.** §1, §4 and §5 say delete; §4.x says do not, yet. The 2026-07-14 retention close-out deleted 8 folders anyway (CHANGELOG), which is why `1121` has no folder today.

### What the code does today

- **"Closing" is only a status edit.** In the Project Manager (`tools/manager/projects.py update_project`), `status` is one of the four editable fields, with vocabulary `active | paused | closed`. Nothing happens to the folder.
- **`generate_index.py` skips closed projects**, so their Finder pages go stale.
- **The ingest ignores `status`.** Measured today: closed `1521`, `0618` and `0220` have folders recreated by later ingests, with 44, 63 and 245 entries in `raw_linked\`. Closed `1121` has none.
- **The Project Manager's import refuses a project without a folder.**
- **There is no `projects_closed\` on `J:\gjesus3-data\`.**

### The smallest change

**Spec.** §5 is ✅ DECIDED, so Ryan has to change it explicitly.
1. **05 §1, §2, §4, §5: closing a project MOVES its folder to `projects_closed\<name>\`, on the same share, and never deletes it.** The lifecycle becomes Created → Active → (Paused) → Closed (moved) → later, separately, cold storage (a separate device, compression optional).
2. **05 §4.x: preserving study metadata at close stays good practice but no longer blocks the close**, because nothing is lost by a move.
3. **06 §4: while closed, `folder_location` = `/projects_closed/<name>/`.** The stored location stays the single source (05 §2a: one construction site), so every tool that reads it keeps working.
4. **05 §4.y: reopening moves the folder back.**

**Tool.**
5. **A "Close project" action in the Project Manager, plus `tools/close_project.py`**, the mirror of `reopen_project.py`, dry run first:
   - set `status: closed`;
   - rename `projects\<name>` → `projects_closed\<name>`. A same-volume rename copies nothing, and the hard links in `raw_linked\` survive, because they are directory entries pointing at the same files;
   - update `folder_location` and `_project.yaml` under the registry lock;
   - write a provenance row.
6. **`reopen_project.py`: if the folder sits in `projects_closed\`, move it back** instead of rebuilding links.
7. **The ingest's behaviour for a closed target**, Q3 below.

### Open questions for Ryan

- **Q1. Retention.** Does "closed" now mean "moved and kept indefinitely", with cold storage as a separate, later step? This changes the ✅ §5.
- **Q2. Access.** Should `projects_closed\` be group read-only (like `/raw/`), or keep each project's ACL?
- **Q3. Data for a closed project.** Today an ingest silently recreates the folder in `projects\` (that is how `1521`, `0618` and `0220` came back). Options: refuse with a message, link into `projects_closed\`, or reopen.
- **Q4. Who may close a project?** Anyone, through the Project Manager, as for creating one (05 §10), or the Data Office only?
- **Q5. The 2026-07-14 casualties.** `1121` is being reopened. Should the partial folders of `1521`, `0618` and `0220` move into `projects_closed\` once it exists?
- **Q6. Finder.** Should closed projects get a read-only page?
- **Q7. Rights.** The move runs as the user at a shared workstation, and renaming a folder in `projects\` needs Delete rights there. The 2026-07-14 close-out hit `WinError 5` on an `rmdir`. Test the move under the real ACLs before promising the feature.

---

## 8. Method, reproducibility, and what I could not establish

**Order of the scripts.** They live in `tools/drive_staging/drive3/`. Run them with `PYTHONDONTWRITEBYTECODE=1`; the worktree has no `__pycache__`.
1. `a2_dicom_magic`: reads 132 bytes of 35,232 extension-less files on `J:`, about 7 minutes.
2. `a2_claims`: the engine, about 3 minutes, with DB `SELECT`s.
3. `a2_files`: `files.csv`, one row per file.
4. `a2_project_map`.
5. `a2_reopen_1121`.
6. `a2_placement`.
7. `a2_verify_placed`: stats 17,346 NAS files, about 3 minutes.
8. `a2_nocode`.
9. `a2_db_evidence` and `a2_db_0118`, both DB `SELECT`s.
10. `a2_biomagune_mj`.
11. `a2_numbers`, which writes `report_numbers.txt` with every figure above.

**Inputs.**
- The coordinator's `drive3_manifest.csv`, `prod_raw_sha256.csv` and `prod_raw_acqs.csv`.
- On the NAS: the live registries, each project tree's `_INDEX.csv` / `_PATHMAP.csv`, and the holding `manifest.csv`.
- The 2026-07-14 close-out backup.
- The animal DB.

**Not established, and why:**
- **The researcher who made each file.** Not attempted, because it was not asked. The claims engine's `researcher` column is in `claims\file_claims.csv`, under the drives 1+2 rule.
- **The project of the 197 `IFs and histologies` exports, the `Draft papers`, the `Proyecto 1019 + 1121` folder and the Microscopio `.tif` exports with no code.** The evidence gives hints, not a single answer, and the rule forbids guessing. All stay (C), and are listed.
- **The pig scans' source and protocol.** Nothing on the drive or in the DB ties them to a protocol. The scanner naming looks clinical; the DICOM headers were not read (A1/A3).
- **I did not open documents** (`.docx`, `.xlsx`, `.pptx`) to infer projects from their contents. Every attribution comes from paths, bytes, production's registry and the DB.
- **A1's view of PET companions.** If A1 judges the Molecubes `.txt`/`reconparams.txt` beside the DICOM to be part of the acquisition, they move from my plan to A1's. Production's PET/CT acquisitions hold `.dcm` only, which is why I placed them as non-raw.

**Traps the next session must know.** Each of these happened in this work.
- **Bash heredocs mangle backslashes**, even quoted ones: the `\\?\` prefix and `\\P` paths came out broken. Write scripts with the editor.
- **The session scratchpad is shared with another live session.** One of my scratch files was overwritten mid-run. Prefix scratch files, or keep them in `D:\…\a2\`.
- **`project_claims.main()` indexes `manifests['drive1']` / `['drive2']`** in its run summary. A wrapper for another drive must give them empty manifests ([`a2_claims.py`](../tools/drive_staging/drive3/a2_claims.py)).
- **`nonraw_placement.project_for` maps every (B) to `Project-0521`.** This drive's `0924` would be misfiled.
- **`nonraw_placement.load_claim_roots`' SHADOWED branch is dead.** The engine writes shadowed claims with no project.
- **`historical_paths` and the READMEs know two drives only** (§4.5).
- **Extension-less DICOM exists without a DICOM-like name** (31 PMOD exports). Classify by the `DICM` preamble, not by name.
- **The engine reads YYMM folder prefixes as (C) claims, and they shadow the outer claim.** It also turns an (A) correction that equals its outer claim into a "disagreement". These are R2 and R3, and they will recur on any drive with this group's naming.
- **MRI link names contain commas** (§3).
- **For 0118, study names carry a treatment (`_2DG_`), not the protocol** (HANDOFF §3). In 2021 the rat studies use an `m` prefix and the operator's name (`m175_ermal`). The folder name `(Ratas hipoxia)` does not describe all of its rats (§4.6).

**Suggested model for whoever applies this:** a strong model. Turning D1–D5 into a re-plan, extending `nonraw_placement` for `D3`, and merging with A1's not-registered exam folders all need judgement about which rows are safe.
