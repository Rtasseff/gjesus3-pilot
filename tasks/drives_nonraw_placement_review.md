# Historical drives: the non-raw material — placement review (Phase 1, read-only)

**Status:** ✅ DONE (stream A, 2026-10-04) — placement, holding fill, the 1519 not-registered placement and the two raw one-offs done and verified (§9b); next is the 2b mapping round (runbook) · **Date:** 2026-10-02 ·
**Branch:** `feat/drives-nonraw-placement` (stream A of the weekend close-out, plan Step 5 items 2 / 2b / 2c)
**Tool:** [`tools/drive_staging/nonraw_placement.py`](../tools/drive_staging/nonraw_placement.py) · tests
[`tools/test_nonraw_placement.py`](../tools/test_nonraw_placement.py) · per-project summary
[`drives_nonraw_placement_per_project.csv`](drives_nonraw_placement_per_project.csv) · 2b worksheet
[`drives_nonraw_mapping_worksheet.csv`](drives_nonraw_mapping_worksheet.csv)
**Full per-file manifest (on D:):** `D:\projects\gjesus3\staging\_analysis\drives-nonraw-placement\placement_manifest.csv`

> **What is left after this placement, and how to do it, is in its own runbook:**
> [`drives_nonraw_2b_2c_followup.md`](drives_nonraw_2b_2c_followup.md).
> - **Part 0:** one decision for Ryan first, about *where the files come from*. It decides how long the D: staging must be kept.
> - **Part 1:** how Ryan fills in the worksheet, `tasks/drives_nonraw_mapping_worksheet.csv` (288 groups). **Only the 62 rows marked `A` matter much:** they hold 190 of 211 GB and 4,855 of 5,055 acquisitions, and blank rows simply go to the holding folder.
> - **Part 2:** every command the applying session runs, for a session that starts cold, possibly months later.

---

## Summary

1. **13,240 files, 228.6 GB, are ready to copy into 15 projects.** That is 10 existing projects plus 5 projects that are approved but not yet created (`AE-biomaGUNE-1116`, `-1420`, `-1520`, `-1319`, `Project-0521`). The copies only add files: nothing is deleted, no registry row changes, and nothing goes under `/raw/`. **The dry run passes:** none of the 13,240 destinations exists, and none of the content is already in `/raw/`.
2. **Two projects that would receive files are closed** (§5): `AE-biomaGUNE-1519` gets 8,667 files (8.3 GB), almost all stream B's non-raw MRI material from `Cardiac MRI.zip`; `AE-biomaGUNE-0320` gets 14 documents. **Ryan: reopen both.** The coordinator runs the reopen; a re-run of `copy` then places them.
3. **Path length is solved** (§6). Every destination is at most 240 characters (it was up to 402) under one shared rule: the study folder first, the high-level folders dropped, the fewest names shortened. A per-tree `_INDEX.csv`, `README.txt` and `_ORIGIN.txt` record every file's original path.
4. **Holding folder (2c), dry run only:** 53,762 files, 218.6 GB. That includes, per Ryan, NMR (21,186 small files), `.svs` and the damaged `.czi`. `Simu_2_V_XYZ.zip` is listed as not copied. README and manifest previews are on D:.
5. **2b worksheet:** 288 groups of files with no project, which also cover the 5,055 blank-project raw acquisitions. 62 of them are marked priority `A`. Applying Ryan's answers is fully tooled and was trial-run read-only (`remap`, `apply-raw`, `copy --from-holding`). The runbook is [`drives_nonraw_2b_2c_followup.md`](drives_nonraw_2b_2c_followup.md).
6. **Raw one-offs, ready to ingest on Ryan's go (§4):**
   - the hidden dot-file `.czi`;
   - **14 new `.czi` found inside a nested archive** (`Drive zuri 170823.zip` > `8583.zip`), which the main ingest never saw.

   Both dry runs are clean. The other 236 `.czi` inside nested archives are already in production.
7. **Two input bugs found and fixed in my own joins** (§7, so nobody repeats them):
   - Member claims of the `.7z` archive used backslashes and had lost their accents, so none of `Haizpea_2020-2022.7z`'s claims matched. Fixing it moved 2,703 files from holding into `AE-biomaGUNE-0420`. All 100,982 member claims now match.
   - Heredoc patches had inserted control bytes into the tool; the test suite caught it.

---

## 1. What was decided (applied, not reopened)

| Rule | Source |
|---|---|
| Raw (acquisition / reconstruction) → `/raw/`; derivatives and complements (exports, `.tif`, scale-bar copies, thumbnails, analysis, figures, slides, EM, video) → project folder | Ryan, 2026-10-01/02 |
| Destination `projects\<project folder>\working\historical_drives\<drive label>\<path below the drive root>` | Ryan, 2026-10-02 |
| `.lsm` (64) → holding folder | Ryan, 2026-10-02 |
| Excluded: software, system files, personal/admin heuristic hits, the ~277 `.czi` re-saves; zero-byte files counted, not placed | handoff §2 |
| `(B)` → `Project-0521`; the nested `Antiguo proyecto 0720` (claim `CL-0541`, verdict C) folds into it; no `Project-0720` | Ryan |
| Closed projects are listed, never reopened by this stream | handoff §2 |
| Stream B owns everything under its 31 imaging roots (`_analysis\drives-dicom\imaging_roots.csv`); B's own non-raw list (`nonraw_for_A.csv`, 15,856 rows) is placed by this tool with B's project | coordinator, 2026-10-02 |

**Choices made here (flag if you disagree):**
- **Archive folder name `<stem>_<ext>`** (`Manon.zip` → `Manon_zip\`). A folder called `Manon.zip` looks like a file in Explorer, and the bare stem could collide with a real sibling folder. A nested archive gets the same treatment inside its parent's folder.
- **macOS `._*` files** (1,394 "AppleDouble" stubs) are excluded as system files. The catalog had classed them by extension.
- **An archive that B hands over whole** is expanded, and its members take B's project. **An archive under a B root** stays B's. **The nested `OneDrive_1_29-1-2021.zip` in `Cardiac MRI.zip`** (14.2 GB), which B listed whole for `0619`, is held until B's v2 lists its contents. Placing it now would place the same material twice.
- **Redundant copies within one project are all placed** (the original structure matters more than the bytes saved): 2,595 extra copies, 5.84 GB. Most are in `0721` (1,115 files, 2.97 GB; the `PR-0721-Biod-May23.zip` contents duplicate the loose export folder) and `0420` (1,194 files, 0.50 GB).

## 2. Destination layout — three real examples

The rule and its effect are in §6. All three examples come from the final plan.

```
loose file      drive1  Cell observer\AINHIZE\1123\Biodistribución 1123 FeMn\HE\ID 110_HE_lung_20x.tif
            ->  \\GJESUS3\gjesus3\projects\AE-biomaGUNE-1123\working\historical_drives\FRIO-X6\1123\Biodistribución 1123 FeMn\HE\ID 110_HE_lung_20x.tif

archive member  drive1  Drive Maria Jesus and Irati 20211209.zip ! Drive Maria Jesus and Irati 20211209/Pili y Mili/Proyecto 0521 iNO/Antiguo proyecto 0720/0720MNS01-21.doc
            ->  \\GJESUS3\gjesus3\projects\Project-0521\working\historical_drives\FRIO-X6\Proyecto 0521 iNO\Antiguo proyecto 0720\0720MNS01-21.doc

R3 derivative   drive2  CELL OBSERVER 2\AINHIZE\AXIOSCAN\AINHIZE-ITZIAR TM\Prueba jpeg\ID205\MFB_AUA_1123_ID205Lu_TM_10x_ROI lobulo 1.czi   (ROI crop of ACQ-20260416-ZWSI-…)
            ->  \\GJESUS3\gjesus3\projects\AE-biomaGUNE-1123\working\historical_drives\MFB-Disco-2\ID205\MFB_AUA_1123_ID205Lu_TM_10x_ROI lobulo 1.czi
```

A file with no claim root keeps its full path below the drive tag. The 4 scale-bar copies in `laura` are an example: `MFB-Disco-2\2025-10-02 - Toshiba EXT (Backup)\CELL OBSERVER\Laura\…`.

Each placed file gets a row in its project's `provenance.csv` with these fields:
- `input_refs` = `<drive label>/<path>` (archive members as `archive!member`). The 22 R3 derivatives also carry their parent ACQ-ID.
- `notes` = `sha256:<hex>; claim CL-…`.

## 3. Numbers

### 3.1 Every candidate, by decision

| Decision | Files | GB |
|---|---:|---:|
| **place** (copy into a project) | **13,240** | **228.64** |
| closed-project (listed; needs a reopen) | 8,681 | 8.29 |
| holding (2c, later) | 32,558 | 211.62 |
| exclude | 21,525 | 5,528.95 |
| other-stream (B: 115,411 under its roots + 5,885 `B?`; C: `LEONE.zip`) | 121,297 | 244.85 |
| raw-oneoff (→ `/raw/`, Ryan's go) | 15 | 0.19 |
| unclear (questions, §8) | 20 | 117.00 |
| expanded (an archive; its members are the rows) | 27 | 132.70 |
| + `LEONE.zip` members, stream C, counted not listed | 671,805 | — |

### 3.2 Per project (place / closed)

| Project | ID | Status | Files | GB |
|---|---|---|---:|---:|
| AE-biomaGUNE-1019 | PROJ-0006 | active | 4,119 | 7.27 |
| AE-biomaGUNE-0420 | PROJ-0012 | active | 3,920 | 13.97 |
| AE-biomaGUNE-0721 | PROJ-0010 | active | 2,872 | 6.42 |
| AE-biomaGUNE-0619 | PROJ-0004 | active | 1,241 | 3.04 |
| AE-biomaGUNE-1022 | PROJ-0019 | active | 367 | 56.11 |
| AE-biomaGUNE-1321 | PROJ-0018 | active | 300 | 54.66 |
| AE-biomaGUNE-1123 | PROJ-0014 | active | 278 | 55.88 |
| AE-biomaGUNE-0219 | PROJ-0017 | active | 61 | 31.06 |
| AE-biomaGUNE-1319 | **NEW** | approved | 25 | 0.19 |
| Project-0521 | **NEW** | approved | 23 | 0.01 |
| AE-biomaGUNE-0118 | PROJ-0060 | active | 21 | 0.01 |
| AE-biomaGUNE-1116 | **NEW** | approved | 4 | 0.00 |
| laura | PROJ-0045 | active | 4 | 0.01 |
| AE-biomaGUNE-1420 | **NEW** | approved | 3 | 0.00 |
| AE-biomaGUNE-1520 | **NEW** | approved | 2 | 0.00 |
| **AE-biomaGUNE-1519** | PROJ-0008 | **closed** | 8,667 | 8.28 |
| **AE-biomaGUNE-0320** | PROJ-0007 | **closed** | 14 | 0.00 |

- **`AE-biomaGUNE-1319` must be created** for 25 files: 22 of Peio's PET/CT derivatives that B handed over (`.nii`, `.mat`, `.jpg`, protocol text) and 3 documents from the Maria Jesus/Irati archive. **It is the coordinator's to sequence with stream B,** which also needs it.
- **The 22 R3 derivatives** go to their parents' projects as decided: 18 per-lobe ROI crops to `AE-biomaGUNE-1123`, and 4 scale-bar copies to `laura`.

### 3.3 Placed, by class

| Class | Files | GB |
|---|---:|---:|
| other (`.xml`, `.par`, `.info`, `.raw` exports, …) | 5,116 | 10.56 |
| tif | 2,134 | 179.14 |
| volume (B's non-raw NIfTI etc.) | 2,117 | 4.96 |
| figure | 1,694 | 12.93 |
| analysis | 1,561 | 0.26 |
| document | 572 | 0.72 |
| video | 24 | 1.00 |
| czi-raw (the 22 R3 derivatives) | 22 | 19.08 |

10,268 of the placed files are archive members, extracted one at a time at copy time; 2,972 are loose files.

### 3.4 Exclusions

| Reason | Files | GB |
|---|---:|---:|
| `.czi` ingested by the main ingest | 8,791 | 3,852.42 |
| `.czi` with the same bytes as an ingested or in-production copy (other copies) | 1,964 | 1,315.55 |
| `.czi` already in production (incl. the 277 re-saves) | 1,376 | 321.45 |
| `.czi` inside nested archives, already in production | 236 | 7.91 |
| `.czi` in the AxioScan's own archive (`S:\goptical`) | 14 | 12.50 |
| software (incl. `fiji.app` in a nested zip) | 4,040 | 4.03 |
| installer archives (`Origin\…Downloadly`, cracks) and their members | 70 | 14.24 |
| system files | 2,375 | 0.32 |
| macOS `._` AppleDouble stubs | 1,394 | 0.01 |
| zero-byte | 1,162 | 0.00 |
| personal/admin heuristic | 97 | 0.53 |
| meal receipts (nested `Gastos Giessen\Meals cost original documents.zip`) | 6 | 0.00 |

Every `.czi` not placed is accounted for by SHA-256: either it is in production, or it was ingested or excluded this effort. None is lost.

## 4. Raw one-offs (prepared; the ingests wait for Ryan's go)

| What | Config | Farm on D: | Dry run against `J:` |
|---|---|---|---|
| the hidden dot-file `Cell observer\Laura\Cell observer\Interaccion-LS-SPN\.LS-SPN-20x-8.czi` (CELL, 61 MB, no claim, researcher `Laura`) | `tools/configs/drives_2026-10_dotfile/drives_dotfile.yaml` | a hard link named `LS-SPN-20x-8.czi`: it fills the gap in the folder's 1–13 series, and the true name is in `notes` | **1 case, 0 SKIP**; would become `ACQ-20240125-CELL-050` |
| **14 new `.czi`** in `Drive zuri 170823.zip` > `Proyecto Cav1 CNIC/8583.zip` (CELL, 2023-05-03, no claim, researcher `zuri` like its 253 batch-B05 siblings) | `…/drives_nested.yaml` + `cases_nested.csv` | byte copies (a member cannot be hard-linked), SHA-256 verified | **14 cases, 0 SKIP, 0 failed** |

**To run them (after Ryan's go)**, follow the drives ingest runbook's per-batch procedure ([`drives_microscopy_ingest_runbook.md`](drives_microscopy_ingest_runbook.md), steps a–f): a fresh dated registry backup, a dry run, the run, `validate_registries`, and a re-run that must add 0.

1. **Rebuild the farms if they are gone.** Both live in `D:\projects\gjesus3\scratch_drives-nonraw-placement\`:
   - `python tools\drive_staging\nonraw_placement.py dotfile-farm`
   - `python tools\drive_staging\nonraw_placement.py nested-farm` (this one needs `nested_members.csv`, `nested_czi_dedup.csv` and the staged Drive zuri zip).
2. **Ingest:**
   ```
   python tools\ingest_raw.py -c tools\configs\drives_2026-10_dotfile\drives_dotfile.yaml --nas-root "J:\gjesus3-data" --dry-run
   python tools\ingest_raw.py -c tools\configs\drives_2026-10_dotfile\drives_nested.yaml --nas-root "J:\gjesus3-data" --dry-run
   ```
   then the same without `--dry-run`.
3. **Verify and record by hand.** `ingest_verify.py` only knows the planned batches B01–B16, so it does not fit these one-offs.
   - **Verify:** select the `registry_raw.csv` rows whose `ingest_config` is one of these two YAMLs; check there are exactly 1 + 14 of them, and that each sidecar checksum equals `drv_sha256` in the case table.
   - **Record:** append one row each to `tasks/drives_ingest_provenance.csv`. Use the columns `acq_id,batch,drive,relpath,archive,member,sha256,manifest_verified,other_copies,notes`, with batch `DOTFILE` / `NESTED`. For the 14, `archive` = `Drive zuri 170823.zip` and `member` = `<nested zip>!<inner path>`.

   The farms must exist, and must be on D:, until both ingests are done: the engine reads them. Both ingests need the staged D: data, so **do them before the D: erase.**

**How the nested `.czi` were deduplicated** (`tools/drive_staging/nested_czi_dedup.py`; the tests below were applied in order):
1. by SHA-256 against production and the drives;
2. by (instrument, acquisition time to the second, lower-cased name) against `registry_raw.csv`.

Of the 250, **234 are in production by SHA-256** and **2 are the same acquisition under different bytes** (`ACQ-20230419-CELL-008`, `ACQ-20230419-LSM9-021`). **14 are new.** All 59 `.czi` in `KI67 cav1 190423.zip`, which nobody had inspected before, are already in production.

Correction to stream B's note: `Fotos confocales cdh5 jagged2.zip` nested inside `Drive zuri` **does** hold `.czi` (177 of them), but all are already in production.

## 5. Closed projects — need Ryan's case-by-case call

| Project | Files | What |
|---|---:|---|
| `AE-biomaGUNE-1519` (PROJ-0008) | 8,667 (8.28 GB) | 8,661 are stream B's non-raw MRI material from `Cardiac MRI.zip` (NIfTI, splits, segmentations); 6 are documents |
| `AE-biomaGUNE-0320` (PROJ-0007) | 14 | `Proyecto 0320 PAH KO` in the Maria Jesus/Irati archive: the CEEA PDF, animal list, MRI database spreadsheets, NIfTI info files, planning figure |

Stream B's DICOM ingest also needs `1519` reopened (close-out plan Step 5 item 4), so **one reopen would serve both streams.**

## 6. Path length — solved by the shared destination rule (Ryan, 2026-10-02)

**Ryan's decision:**
- **No:** paths that throw errors, and zips (researchers must browse).
- **Instead:** drop the high-level folders, shorten where needed, and keep an index so nothing is lost.

**The rule.** Built as one function for every stream, [`tools/drive_staging/historical_paths.py`](../tools/drive_staging/historical_paths.py) (tests: `tools/test_historical_paths.py`). It is also used by stream D (derivative retirements), stream C (LEONE into DTS24), 2b and 2c.

```
<project>\working\historical_drives\<FRIO-X6 | MFB-Disco-2>\<study folder>\<path below it>\<file>
```

- **The study folder** is the *outermost claim root of the file's own project* on its path, for example `Proyecto 1019 Envejecimiento y dieta`.
  - Everything above it is dropped: the drive's wrapper folders, the person folders, an archive's name and its repeated top folder.
  - Two different roots with the same name get ` (2)`.
  - The holding folder has no study folder: it keeps the drive's full structure.
- **Below the study folder,** an archive becomes a folder `<stem>_<ext>`.
- **Budget:** the full `\\GJESUS3\gjesus3\…` path is at most **240** characters (19 of headroom under Windows' 259), and no component is over 255.
- **Shortening, only where needed:** a global greedy that removes the most excess per cut.
  - Folders are cut to 24, then to 12 characters + `~` + 4 hex of a hash of the full name.
  - A study folder is cut only ever to 24, because its name carries the protocol number.
  - A folder is cut for everything in it, never file by file.
  - File names are cut only after folders.
  - Destinations are checked unique, case-insensitively.
- **Nothing is lost.** Each tree gets these documents, written UTF-8 with a BOM where Excel opens them:

  | Document | What it holds |
  |---|---|
  | `_INDEX.csv` | new path → full original path, size, SHA-256, claim, shortened Y/N |
  | `README.txt` | plain language: what the folder is, how names were shortened, how to find a file's origin |
  | `_ORIGIN.txt` | in every study folder: the full original path that was dropped above it |
  | `_PATHMAP.csv` | every folder's original → rendered name |

  A later run reads `_PATHMAP.csv` from the NAS, so **a folder already placed is never renamed** (it is frozen). The Data Office's global index is [`drives_nonraw_index.csv`](drives_nonraw_index.csv): a dated snapshot read from the NAS (`nonraw_placement.py index-from-nas`). On 2026-10-04 it had 34,720 rows in 18 projects: stream A's 27,547, plus stream C's LEONE in `DTS24` and stream D's first derivatives, tagged by `writer`. Re-run the command whenever another stream adds rows.

**Effect, on all 75,683 destinations** (placed + closed-project + holding):

| Rule | Longest | > 240 | > 259 |
|---|---:|---:|---:|
| R0, the first layout (full path, archive folders) | 402 | 24,515 | 18,396 |
| R1, study folder first, high-level folders dropped | 362 | 11,853 | 4,919 |
| **R2, + the fewest names shortened (final)** | **240** | **0** | **0** |

**What the shortening cost:**
- **Folders:** 759 of 8,347 were shortened: 337 kept 24 characters, 362 kept 12, 48 kept 11 and 12 kept 6.
- **Study folders:** all are kept whole except `Proyecto 1019 Envejecimi~c3e8` (it still shows the number). In holding, the two drive-root wrappers were cut (`Drive Maria Jesus and Ir~d7b8`, `2025-10-02 - Toshiba EXT~c41f`).
- **File names:** 363 placed and 141 holding file names were shortened (stem only, extension kept).

**Examples (before → after):**

```
[1019, the worst: 331 -> 228]
drive1_FRIO-X6\Drive Maria Jesus and Irati 20211209.zip!Drive Maria Jesus and Irati 20211209\Pili y Mili\Proyecto 1019 Envejecimiento y dieta\Modificación proyecto\Procedimiento 4\Nuevo proyecto\Documentos para presentar\Documentos para la1ª subsanacion\for-ep-10v04_formulario_uso_de_roedores_modificados_geneticamente_mpv17.docx
\\GJESUS3\gjesus3\projects\AE-biomaGUNE-1019\working\historical_drives\FRIO-X6\Proyecto 1019 Envejecimi~c3e8\Modificació~8033\Procedimiento 4\Nuevo proyecto\Documentos p~21d2\Documentos p~ef5f\for-ep-10v04_formulario_~a351.docx

[0619: 291 -> 240]
drive1_FRIO-X6\Drive Maria Jesus and Irati 20211209.zip!…\Pili y Mili\Proyecto 0619 Ratones PAH\PAH y 2-DG Marzo 2021  Machos\MRI\Splits Ratones 2-DG marzo 2021\20210312_122905_jrc210312_m110_0619_1_1\Time_10_rat_20210312_122905_jrc210312_m110_0619_1_1.raw
\\GJESUS3\gjesus3\projects\AE-biomaGUNE-0619\working\historical_drives\FRIO-X6\Proyecto 0619 Ratones PAH\PAH y 2-DG M~53b9\MRI\Splits Raton~c015\20210312_122905_jrc210312_m110_0619_1_1\Time_10_rat_20210312_122905_jrc210312_m110_0619_1_1.raw

[0420: 7z member, one folder cut]
drive1_FRIO-X6\Haizpea_2020-2022.7z!Haizpea_2020-2022\project0420\20210610_0420_2.1\20211025_picosirius\id15_patch20x_half-Stitching-20.tiff_files\id15_…tiff_metadata.xml
\\GJESUS3\gjesus3\projects\AE-biomaGUNE-0420\working\historical_drives\FRIO-X6\project0420\20210610_0420_2.1\20211025_picosirius\id15_patch20x_half-Stitc~14d6\id15_…tiff_metadata.xml

[1123: loose, nothing cut]
drive1_FRIO-X6\Cell observer\AINHIZE\1123\Biodistribución 1123 FeMn\HE\ID 110_HE_lung_20x.tif
\\GJESUS3\gjesus3\projects\AE-biomaGUNE-1123\working\historical_drives\FRIO-X6\1123\Biodistribución 1123 FeMn\HE\ID 110_HE_lung_20x.tif

[Project-0521: archive above the study folder dropped]
drive1_FRIO-X6\Drive Maria Jesus and Irati 20211209.zip!…\Pili y Mili\Proyecto 0521 iNO\Antiguo proyecto 0720\0720MNS01-21.doc
\\GJESUS3\gjesus3\projects\Project-0521\working\historical_drives\FRIO-X6\Proyecto 0521 iNO\Antiguo proyecto 0720\0720MNS01-21.doc
```

**One consequence to know about: scattering.** Where a project's claims sit at animal or session level, with no claim at the study level, each becomes its own top-level folder.

| Project | Top-level folders | Examples |
|---|---:|---|
| `0721` | 58 | ParaVision session folders |
| `1123` | 24 | `HE`, `ID205`, … |
| `1019` | 16 | `General`, `ID 22`, … |
| `1321` | 12 | — |
| most others | 1–6 | — |

Each one's `_ORIGIN.txt` says where it was. **An option, not applied** because it changes the agreed rule: when the outermost claim root is an animal- or session-level folder, use its parent as the study folder.

## 6b. Previews (what will be written)

- **Per tree,** under `D:\…\drives-nonraw-placement\trees\<tree>\`: `_INDEX.csv`, `_PATHMAP.csv`, `_ORIGINS.csv`, and `_ORIGIN_preview.txt` (every `_ORIGIN.txt` in one file).
- **Holding:** `D:\…\drives-nonraw-placement\holding_preview__README.txt` and `holding_preview__manifest.csv` (with the not-copied `Simu_2_V_XYZ.zip` row).
- **The project README** is `historical_paths.PROJECT_README`.
- **`copy --execute`** publishes exactly these files after a project's files are copied and verified (`publish_tree`; it writes only what changed and never touches a data file), and adds provenance rows for them.

## 7. Oddities and how they were handled

- **The claims pass's `.7z` member paths** used backslashes and stored accents as `�`, so the catalog's members never matched (all 19,048 of `Haizpea_2020-2022.7z`). The tool now joins on a normalised key (`member_key`). All 100,982 member claims match, and the plan logs the match count so this cannot recur silently.
- **The catalog never opened nested archives** (9 outside LEONE and Cardiac). The tool lists them: each nested zip is copied once to D: scratch, because reading a zip inside a zip stream is quadratic and stalled on a 2.3 GB member. In total that is 7,993 members.
- **The same content in two projects (3 files):** two CEEA modification `.doc` files and an 890-byte `Segmentation Labels.label` template, each in both `0420` (Haizpea) and `1019` (Maria Jesus/Irati). They are placed in both projects, which is harmless.
- **`.raw` time series in `Draft papers\Analisis cardiacMRI`** (`1019`, Maria Jesus/Irati): these are analysis exports from cardiac MRI, not acquisitions, so they are placed as non-raw. B's roots do not cover them.
- **5,885 imaging-class files lie outside B's roots** (`B?`), mostly NIfTI inside the Maria Jesus/Irati archive. They are not placed, and are listed for B in `D:\…\drives-nonraw-placement\for_B_imaging_outside_roots.csv`.
- **Stream B's NMR list** (`nmr_list.csv`) covers 671 TopSpin experiments: 18,539 files, 1.15 GB, mainly Nicola's chem lab (207), Ana B's NMR (94 + 24), Peio (90), Amaia (59) and `Proyecto 1019` HR-MAS (23). Not placed this weekend; the default pending Ryan is the holding folder, or project material where the files sit under a claim.
- **Finder:** `tools/generate_index.py` lists only `raw_linked\` entries, so `index.html` does not need regenerating after this copy (handoff step 9: skip).

## 8. Questions — Ryan's answers (2026-10-02, relayed by the coordinator)

| Question | Answer | Applied |
|---|---|---|
| Path length | Neither long paths nor zips: drop high-level folders, shorten, index | §6, the shared rule |
| Reopen `1519` / `0320` | Yes; the coordinator runs it after stream B's write window | the 8,681 rows wait as `closed-project`; a re-run of `copy` places them once reopened |
| `AE-biomaGUNE-1319` | Stream B's N03 ingest creates it | the 25 files are copied after B has created it |
| Aperio `.svs` (15, 4.15 GB) | Holding folder (2c, later) | `holding` |
| NMR, TopSpin (B's `nmr_list.csv`: 671 experiments; 21,186 files, 1.26 GB as matched here) | Holding folder (2c, later) | `holding`, not mappable in 2b |
| 3 unreadable `.czi` with bytes (1.62 GB) | Holding folder (2c, later) | `holding` |
| `Simu_2_V_XYZ.zip` (97 GB, truncated) | Not copied; listed in the holding README and manifest | `exclude`, plus a `not copied` row in the holding `manifest.csv` |
| AppleDouble `._` stubs | Excluding them is fine | `exclude` |
| Raw one-offs: the dot-file and the 14 nested `.czi` | Approved into `/raw/`, the 14 with a **blank** project | prepared and dry-run clean (§4) |
| CEEA documents filed in another protocol's folder (findings §4.2) | — | still (C) → holding; mappable in 2b |

**Still open:**
- the stream B v2 contents of the nested `OneDrive_1_29-1-2021.zip` (`Cardiac MRI.zip`, 14.2 GB);
- the scattering option in §6.

## 9. Phase 2 plan (after the go and inside the write window)

1. **Back up `registry_projects.csv`** to a new folder, `C:\Users\rtasseff\temp\gjesus3_registry_backup_<YYYYMMDD_HHMM>_nonraw\`, with SHA-256 sums.
2. **Create `AE-biomaGUNE-1116`, `-1420`, `-1520` and `Project-0521`** with `create_project.py`. Record their PROJ-IDs. Add `-1319` if the coordinator assigns it here.
   - **All four dry-ran clean on 2026-10-02.** The ID each shows in a dry run is only the next free one; the real IDs depend on which stream creates first.
   - **The exact commands** (from `tools\`; add `--dry-run` first):
   ```
   python create_project.py --nas-root "J:/gjesus3-data" --name "AE-biomaGUNE-1116" --owner Data-Office --description "Animal protocol AE-biomaGUNE-1116 (Proyecto 1116 Contraste). CEEA paperwork and the MRI database spreadsheet from the Maria Jesus/Irati archive on the historical drives." --notes "Created for the 2026 historical-drives non-raw placement (tasks/drives_nonraw_placement_review.md); approved by Ryan 2026-09-29/10-02. Owner is a placeholder: edit _project.yaml."
   python create_project.py --nas-root "J:/gjesus3-data" --name "AE-biomaGUNE-1420" --owner Data-Office --description "Animal protocol AE-biomaGUNE-1420 (Proyecto 1420 miRNA). CEEA paperwork from the Maria Jesus/Irati archive on the historical drives." --notes "<same as above>"
   python create_project.py --nas-root "J:/gjesus3-data" --name "AE-biomaGUNE-1520" --owner Data-Office --description "Animal protocol AE-biomaGUNE-1520 (Proyecto 1520 Fumadores). CEEA paperwork from the Maria Jesus/Irati archive on the historical drives." --notes "<same as above>"
   python create_project.py --nas-root "J:/gjesus3-data" --name "Project-0521" --owner Data-Office --description "Project 0521 iNO: a CEEA application (AE-biomaGUNE-0521) the animal-facility DB does not hold; includes the documents of its predecessor 'Antiguo proyecto 0720' (no Project-0720, Ryan 2026-10-02). From the Maria Jesus/Irati archive on the historical drives." --notes "<same as above>"
   ```
3. **Record the size and mtime** of `registry_raw.csv` and of a `/raw/` sample before the copy.
4. **Copy:** `python tools/drive_staging/nonraw_placement.py copy --execute [--project …]`.
   - It resumes, skips identical files and never overwrites.
   - A collision stops that project and is listed.
   - Provenance rows go in batches under the lock.
   - **After a project's files are in place, it publishes that tree's `_INDEX.csv`, `README.txt`, `_PATHMAP.csv` and every `_ORIGIN.txt`** (the previews, unchanged), with provenance rows.
   - **Order (the coordinator's):**
     1. the 4 projects;
     2. the copies, leaving out `AE-biomaGUNE-1319` until stream B's N03 has created it;
     3. `1519`/`0320` once the coordinator has reopened them: the same command, re-run;
     4. the two raw one-offs, each as its own step (§4).
5. **Verify:**
   - run `verify`: per-project count and bytes from the NAS, plus a 2% random re-hash;
   - check the **ACL**: a placed file inherits `working\`'s ACL. The baseline for `1123` is `GJesus` Modify plus the admin accounts, all inherited (saved in `D:\…\drives-nonraw-placement\acl_baseline_1123_working.txt`). A `raw_linked\` hard link carries `/raw/`'s read-only ACL by design, so it is *not* the comparison;
   - open one project's `_INDEX.csv` in Excel and check that the accents show;
   - check that `registry_raw.csv` and `/raw/` are unchanged (size and mtime before and after).
6. Report to the coordinator.

The copy reads about 229 GB from D:: loose files directly, and archive members via `zipfile` or one `7z` call per `.7z`, extracting only the listed members to D: scratch (3,919 Haizpea members, 14.0 GB, deleted after the copy). At roughly 60 MB/s to the NAS that is **about 1–1.5 h of transfer**.

## 9b. Production log (what was written, and how it was verified)

All the steps below ran inside a write window the coordinator (`gj3-handoff`) granted. Each was verified independently, and the coordinator re-verified it.

| Step | When | What | Result |
|---|---|---|---|
| 1 | 2026-10-04 08:31 | `create_project.py`: `AE-biomaGUNE-1116` **PROJ-0062**, `-1420` **PROJ-0063**, `-1520` **PROJ-0064**, `Project-0521` **PROJ-0065** (owner `Data-Office`, a placeholder) | registry append-only (+4 rows, BOM-free, CRLF); skeletons present; validator unchanged at 10,314, all the MRI placeholder. Backup: `C:\Users\rtasseff\temp\gjesus3_registry_backup_20261004_0831_nonraw_step1\` |
| 2a | 2026-10-04, run `NONRAW-20261004-084951` | 5,671 files / 104.42 GB into 11 projects | 5,671 copied, 0 collisions |
| 2c | 2026-10-04, run `NONRAW-20261004-094913` | 8,681 files / 8.29 GB into `1519` and `0320`, after the coordinator reopened them | 8,681 copied, 0 collisions |
| 2b + v2 top-up | 2026-10-04, run `NONRAW-20261004-100718` | the regrouped `0721` / `1019` / `1123` / `1321` (Ryan, "group under the parent") + stream B's v2 NIfTI for `0619` / `0320` | 13,182 copied + 1,255 skipped as identical, 0 collisions |
| 3 holding | 2026-10-04, detached process (log `…-v3b\holding_step3.out`) | 54,721 files / 218.89 GB into `staging\historical_drives_unassigned\` (B's v3; Ryan chose option B, fill now) + 26 documents | 54,721 copied, 0 collisions; list_sha256 `b64958a0…` reproduced from the NAS walk; 1,094/1,094 re-hash |
| 1519 not registered | 2026-10-04, run `NONRAW-20261004-142020` | 13 not-registered MRI files (`m35_week3/35`) + `README_not_registered.txt`; `_INDEX`/`_PATHMAP` republished as a merge | 13 copied (13/13 full re-hash), 8,667 skipped-identical |
| 4 raw one-offs | 2026-10-04 16:08, `ingest_raw.py` with `drives_dotfile.yaml` and `drives_nested.yaml` (the only registry writer) | the hidden dot-file `.czi` → **`ACQ-20240125-CELL-050`** (CELL, Laura, no claim → blank project, so no project link); the 14 `.czi` from `Drive zuri 170823.zip` > `8583.zip` → **`ACQ-20230503-CELL-001` … `-014`** (CELL, zuri, blank project) | 15/15 success; before: dedup by SHA-256 and by (instrument, time, name) against the live registry, 0 already present. After: `checksums.json` == the drive manifest SHA-256 on all 15; `registry_raw.csv` and `ingest_manifest.csv` append-only (+15 lines each, CRLF, no BOM), the other registries byte-identical; the re-run adds 0; validator still 10,314, all the MRI placeholder; provenance in `tasks/drives_ingest_provenance.csv` (batches `DOTFILE` / `NESTED`). Backup: `C:\Users\rtasseff\temp\gjesus3_registry_backup_20261004_1608_nonraw_step4\` |

**Placed in total: 27,547 files, 237.73 GB, in 17 projects; holding: 54,721 files, 218.89 GB.** The per-project counts, bytes and list hashes are in `D:\projects\gjesus3\staging\_analysis\drives-nonraw-placement\step2_expected_per_project.csv` and `…-v2b\step2b_expected_per_project.csv`.

**Verification, every step:**
- **The copy itself:** every file was re-hashed from the NAS before its rename.
- **An independent walk** of each project's `working\historical_drives\` against the expected list: 0 missing, 0 extra, 0 size mismatches, no temp files, plus a fresh 2% re-hash. Evidence: `verify_step2a.txt`, `verify_step2c.txt`, `-v2b\verify_step2b.txt`.
- **Provenance:** one row per file plus one per index document; no duplicate FILE ids.
- **ACL:** a placed file inherits `working\` (`GJesus` Modify plus the admins).
- **`/raw/` and `registry_raw.csv`:**
  - unchanged in 2a/2c (byte-identical registry; a sample of 40 `/raw/` month folders unchanged);
  - in 2b, stream B was ingesting in parallel, so the `/raw/` sample excluded B's month folders (unchanged), and the tool is audited to open no registry file for writing.

**The working manifests:**
- the record (v1): `D:\…\drives-nonraw-placement\placement_manifest.csv`;
- **the current one** (B's v2, regrouped, re-planned against the frozen NAS path maps): `D:\…\drives-nonraw-placement-v2b\placement_manifest.csv`.

**Use the current one for every later step** (holding, 2b mapping). Copy it off D: before the staging is erased (runbook §2.6).

**A `/raw/` check that fired (step 3), and why it was fine.** My before/after sample of 40 `/raw/` month folders (excluding stream B's) showed 3 MICROSCOPY month folders that lost acquisitions during the window: `2021-11` 22→21, `2025-04` 155→153, `2025-09` 215→214. Stream A writes nothing under `/raw/` (the tool has no `/raw/` path). **Verified against the tombstones** by the coordinator: all were approved retirements, namely `ACQ-20250915-LSM9-016` (the coordinator's content-equivalent retirement `RET-20261004-135015-801`), `ACQ-20250415-CELL-003` and `-010`, and `ACQ-20211105-CELL-021` (stream D's derivative retirements).

**Still to do (stream A):** nothing. What follows is the 2b round (Ryan's mapping), run from `tasks/drives_nonraw_2b_2c_followup.md`.

## 10. Proposed wording for STATUS / CHANGELOG / BACKLOG (the coordinator applies it at merge)

*Final for the stream, 2026-10-04 (step 4 included).*

**STATUS §2, drives bullet — add:**
> **Non-raw material (stream A, 2026-10-03/04): done.**
> - **Placed:** 27,547 files, 237.73 GB, into 17 projects under `<project>\working\historical_drives\<FRIO-X6|MFB-Disco-2>\<study folder>\…`. Every path is at most 240 characters (the shared rule `tools/drive_staging/historical_paths.py`), and each tree carries `_INDEX.csv`, `README.txt`, `_ORIGIN.txt` and `_PATHMAP.csv`.
> - **Created:** `AE-biomaGUNE-1116/-1420/-1520`, `Project-0521` (PROJ-0062..0065).
> - **Holding:** 54,721 unassigned files (218.89 GB) are in `staging\historical_drives_unassigned\`, with `README.txt` and `manifest.csv`. That includes the `.lsm`, `.svs`, NMR, unreadable `.czi` and not-registered MRI (each exam folder with a `README_not_registered.txt`).
> - **Verified:** every file was re-hashed at copy time, and an independent NAS walk found 0 missing and 0 extra; the coordinator re-verified it.
> - **Raw one-offs:** the dot-file `.czi` was ingested as `ACQ-20240125-CELL-050` and the 14 nested `.czi` as `ACQ-20230503-CELL-001`…`-014` (blank project, no claim; 2026-10-04).
> - **Waiting on Ryan:**
>   - the 2b mapping worksheet (`tasks/drives_nonraw_mapping_worksheet.csv`; the 62 `A` rows cover nearly everything);
>   - whether the holding folder should be group read-only (it inherits `staging\`'s Modify).
> - **Runbook for the 2b round:** `tasks/drives_nonraw_2b_2c_followup.md`. **Record:** `tasks/drives_nonraw_placement_review.md`.

**CHANGELOG (new entry, 2026-10-04):**
> **Historical drives — non-raw material placed in projects, the rest in a holding folder (stream A).**
> - **Placed:** 27,547 files (237.73 GB) of exports, figures, documents, analysis, EM, stream B's non-raw MRI and 13 not-registered MRI files. They are copied, byte-verified, into 17 projects under `<project>\working\historical_drives\` (Ryan, 2026-10-02), with a provenance row each.
> - **Projects created:** `AE-biomaGUNE-1116`, `-1420`, `-1520` and `Project-0521` (with the old `0720` documents), as PROJ-0062..0065. `1519` and `0320` were reopened by the coordinator for this.
> - **Path rule (Ryan):** no paths that throw errors and no zips. The answer is one shared rule, `historical_paths.py`:
>   - the study folder first, everything above it dropped;
>   - `<stem>_<ext>` folders for archives;
>   - every path at most 240 characters, the fewest names shortened (`…~3f2a`);
>   - an index so nothing is lost.
>
>   On 82,268 destinations the longest path went from 402 to 240. Folders and files already placed are frozen, so a later run never renames them, and republishing an index merges with other streams' rows (stream D).
> - **"Group under the parent" (Ryan):** in `0721`/`1019`/`1123`/`1321`, session- and animal-level folders sit under their parent: 58→10, 16→7, 24→4 and 12→6 top-level folders.
> - **Holding:** 54,721 files (218.89 GB) in `staging\historical_drives_unassigned\` (Ryan: fill now, map later), with `README.txt` and `manifest.csv` (original paths, a `why` column, and the two archives deliberately not copied).
> - **Not-registered MRI (Ryan):** spectroscopy or no reconstruction is kept as other data, beside a plain README whose wording was agreed with stream B.
> - **Found on the way:**
>   - nested archives were never catalogued (9 archives; 250 `.czi`, of which 14 are new);
>   - the claims pass's `.7z` member paths did not join the catalog (backslashes, lost accents);
>   - file-name shortenings are recorded only in `_INDEX.csv`, so placed files are now pinned to it.
> - **Tools:** `tools/drive_staging/nonraw_placement.py`, `historical_paths.py`. **Record:** `tasks/drives_nonraw_placement_review.md`.

**BACKLOG:**
> - 🔺 **2b mapping (historical drives).**
>   - Ryan fills `tasks/drives_nonraw_mapping_worksheet.csv` (the 62 `A` rows; blank = stays in holding).
>   - A session applies it with `tasks/drives_nonraw_2b_2c_followup.md`: `remap` → `apply-raw` (blank-project raw rows) → `copy --from-holding`. The holding folder is already filled (option B), so D: is not needed.
>   - Before the D: staging is erased, keep the record manifest off D: (runbook §2.6). The current manifest is `…\drives-nonraw-placement-v3b\placement_manifest.csv`.
> - 🔸 **Holding folder ACL** (passed to Ryan by the coordinator): it inherits `staging\` (`GJesus` Modify). Decide whether it should be group read-only.
> - 🔸 **Aperio `.svs` (15, Drive zuri TUNEL) and TopSpin NMR (671 experiments):** held, because the instruments are not onboarded / the data is not imaging. Revisit if either is ever registered.
> - 🔹 **`catalog.py` does not open nested archives**; `nonraw_placement.py nested` is the stopgap. Fold it in if the catalog is reused for another drive.
> - 🔹 **`historical_paths.py` is now the destination rule for any drive material placed on gjesus3** (streams A, C, D). Consider promoting it into `05_PROJECTS` (a spec change, so the Data Office decides).
