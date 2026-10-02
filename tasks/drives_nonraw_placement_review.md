# Historical drives: the non-raw material — placement review (Phase 1, read-only)

**Status:** 🔶 DRAFT — Phase 1 done, **no production write yet** · **Date:** 2026-10-02 ·
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
2. **Two projects that would receive files are closed** (§5): `AE-biomaGUNE-1519` gets 8,667 files (8.3 GB), almost all stream B's non-raw MRI material from `Cardiac MRI.zip`; `AE-biomaGUNE-0320` gets 14 documents. They are listed, not copied. Reopening them is Ryan's call.
3. **Decision needed before copying: path length** (§6). 9,522 of the 13,240 destinations would sit at a full network path over 259 characters (the longest is 402). They come from three archives whose own folders nest deeply.
4. **Holding folder (2c), dry run only:** 32,558 files, 211.6 GB. The README and manifest previews are on D:.
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

```
loose file      drive1  Cell observer\AINHIZE\1123\Biodistribución 1123 FeMn\HE\ID 110_HE_lung_20x.tif
            ->  \\GJESUS3\gjesus3\projects\AE-biomaGUNE-1123\working\historical_drives\drive1_FRIO-X6\Cell observer\AINHIZE\1123\Biodistribución 1123 FeMn\HE\ID 110_HE_lung_20x.tif

archive member  drive1  Drive Maria Jesus and Irati 20211209.zip ! Drive Maria Jesus and Irati 20211209/Pili y Mili/Proyecto 0521 iNO/Antiguo proyecto 0720/0720MNS01-21.doc
            ->  \\GJESUS3\gjesus3\projects\Project-0521\working\historical_drives\drive1_FRIO-X6\Drive Maria Jesus and Irati 20211209_zip\Drive Maria Jesus and Irati 20211209\Pili y Mili\Proyecto 0521 iNO\Antiguo proyecto 0720\0720MNS01-21.doc

R3 derivative   drive2  CELL OBSERVER 2\AINHIZE\AXIOSCAN\AINHIZE-ITZIAR TM\Prueba jpeg\ID205\MFB_AUA_1123_ID205Lu_TM_10x_ROI lobulo 1.czi   (ROI crop of ACQ-20260416-ZWSI-…)
            ->  \\GJESUS3\gjesus3\projects\AE-biomaGUNE-1123\working\historical_drives\drive2_MFB-Disco-2\CELL OBSERVER 2\AINHIZE\AXIOSCAN\AINHIZE-ITZIAR TM\Prueba jpeg\ID205\MFB_AUA_1123_ID205Lu_TM_10x_ROI lobulo 1.czi
```

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

## 6. ⚠️ Decision needed before copying: path length

The layout puts the whole original path below `historical_drives\<drive label>\`. For three archives that is very deep:

| Source | Placed files over 259 chars |
|---|---:|
| `Drive Maria Jesus and Irati 20211209.zip` (1019, 0320, …) | 5,144 |
| `Haizpea_2020-2022.7z` (0420) | 2,285 |
| `PR-0721-Biod-May23.zip` (0721) | 932 |
| loose files | 1,146 |
| `Cardiac MRI.zip` | 15 |
| **total** | **9,522 of 13,240** (longest 402) |

The holding folder has 2,489 such paths, out of 32,558.

**Why it matters:**
- **SMB and the NAS are fine** with these paths, and the copy tool writes with `\\?\` long-path prefixes.
- **Windows Explorer and many applications** fail to open, copy or delete files past 260 characters unless long-path support is enabled on the researcher's machine.

**Options (Ryan's call):**
- **(a) Keep the agreed layout.** Accept long paths, and tell researchers that deep files may need 7-Zip or an Explorer with long paths enabled.
- **(b) Drop the archive's repeated top folder** (`…20211209_zip\…20211209\…` → `…20211209_zip\…`). This keeps the structure, and **9,522 → 6,998** paths stay over 259 characters.
- **(c) Short labels:** `D1`/`D2` for the drive label, `A1`… for archive folders (dropping the repeated top folder too), plus a `README.txt` mapping in `historical_drives\`. **9,522 → 4,039** stay over 259. The folder names become less self-explanatory, and the deep folders inside the archives remain.
- **(d) Keep the three deep archives whole.** Copy the `.zip`/`.7z` file itself into each project that has claims in it, instead of extracting. This needs no extraction, but the multi-project archive would be copied whole into several projects (8.4 GB + 37 GB).

**Recommendation: (a) for this weekend.** No relabelling removes the problem, because the depth is in the researchers' own folders inside the archives. A later move to (b) or (c) is a rename on the NAS; nothing has to be re-copied.

## 7. Oddities and how they were handled

- **The claims pass's `.7z` member paths** used backslashes and stored accents as `�`, so the catalog's members never matched (all 19,048 of `Haizpea_2020-2022.7z`). The tool now joins on a normalised key (`member_key`). All 100,982 member claims match, and the plan logs the match count so this cannot recur silently.
- **The catalog never opened nested archives** (9 outside LEONE and Cardiac). The tool lists them: each nested zip is copied once to D: scratch, because reading a zip inside a zip stream is quadratic and stalled on a 2.3 GB member. In total that is 7,993 members.
- **The same content in two projects (3 files):** two CEEA modification `.doc` files and an 890-byte `Segmentation Labels.label` template, each in both `0420` (Haizpea) and `1019` (Maria Jesus/Irati). They are placed in both projects, which is harmless.
- **`.raw` time series in `Draft papers\Analisis cardiacMRI`** (`1019`, Maria Jesus/Irati): these are analysis exports from cardiac MRI, not acquisitions, so they are placed as non-raw. B's roots do not cover them.
- **5,885 imaging-class files lie outside B's roots** (`B?`), mostly NIfTI inside the Maria Jesus/Irati archive. They are not placed, and are listed for B in `D:\…\drives-nonraw-placement\for_B_imaging_outside_roots.csv`.
- **Stream B's NMR list** (`nmr_list.csv`) covers 671 TopSpin experiments: 18,539 files, 1.15 GB, mainly Nicola's chem lab (207), Ana B's NMR (94 + 24), Peio (90), Amaia (59) and `Proyecto 1019` HR-MAS (23). Not placed this weekend; the default pending Ryan is the holding folder, or project material where the files sit under a claim.
- **Finder:** `tools/generate_index.py` lists only `raw_linked\` entries, so `index.html` does not need regenerating after this copy (handoff step 9: skip).

## 8. Open questions (for the coordinator / Ryan)

1. **Path length** (§6): which option?
2. **Reopen `AE-biomaGUNE-1519`** (8,667 files, shared with stream B) **and `AE-biomaGUNE-0320`** (14 documents)?
3. **`AE-biomaGUNE-1319`:** who creates it, me or stream B, and when?
4. **15 Aperio `.svs` whole-slide scans** (4.15 GB, `Drive zuri 170823.zip` > `PAPERS/TUNEL 230123 CDH5 JAGGED2/TUNEL 230123-…-001/-002.zip`, animals 7846–8237): the instrument is not onboarded. The default by analogy with `.lsm` is the holding folder; they have no claim.
5. **`Simu_2_V_XYZ.zip`** (97 GB, drive 1 root): it cannot be opened as a zip (truncated or not a zip). Nothing is listed, so nothing is placed. Is it a simulation output to keep or drop?
6. **Three `.czi` that are unreadable but not empty:**
   - `Cell observer\Marta\Ekine\HE_10x_Brain\ID7B_0423_HE10x.czi` (1.5 GB, no metadata segment);
   - `CELL OBSERVER 2\Marta\Irene\…\MFB_MBC_0525_ID38H_WGA_10x.czi` (106 MB, no ZISRAW header);
   - `Haizpea…/20211025_picosirius/id4_normal.czi` (21 KB).

   They are probably damaged acquisitions. Leave them on the drives (the default), or keep them as non-raw in their projects (0423, 0525, 0420)?
7. **CEEA documents filed in another protocol's folder** (findings §4.2, the "2 + 2 + 1" row) are (C) and go to holding. The findings doc says either project folder is fine; should they follow their containing folder instead?

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
5. **Verify:**
   - run `verify`: per-project count and bytes from the NAS, plus a 2% random re-hash;
   - compare one placed file's ACL with an ingest-made file's in the same project;
   - check that `registry_raw.csv` and `/raw/` are unchanged.
6. Report to the coordinator.

The copy reads about 229 GB from D:: loose files directly, and archive members via `zipfile` or one `7z` call per `.7z`, extracting only the listed members to D: scratch (3,919 Haizpea members, 14.0 GB, deleted after the copy). At roughly 60 MB/s to the NAS that is **about 1–1.5 h of transfer**.

## 10. Proposed wording for STATUS / CHANGELOG / BACKLOG (the coordinator applies it at merge)

**STATUS §2, drives bullet — add:**
> Non-raw placement (stream A): <N> files / <GB> copied into <P> projects under `working\historical_drives\` (verified: counts + 2% re-hash); projects `AE-biomaGUNE-1116/-1420/-1520`, `Project-0521` created. **Waiting on Ryan:**
> - the 2b mapping: `tasks/drives_nonraw_mapping_worksheet.csv`, 288 groups, **62 marked A cover nearly everything**;
> - **first, Part 0 of `tasks/drives_nonraw_2b_2c_followup.md`**: fill the holding folder now (D: can then be erased early) or after the mapping;
> - the path-length option;
> - reopening `1519`/`0320`;
> - the raw one-offs: the dot-file and the 14 nested `.czi`, both dry-run clean.
>
> **Runbook for whoever applies the mapping: `tasks/drives_nonraw_2b_2c_followup.md`.** Record: `tasks/drives_nonraw_placement_review.md`.

**CHANGELOG (new entry, dated the day of the write):**
> **Historical drives — non-raw material placed into project folders.** <N> files (<GB>) of exports, figures, analysis, documents, EM and stream B's non-raw MRI material copied, byte-verified, into <P> projects under `<project>\working\historical_drives\<drive label>\<original path>` (Ryan, 2026-10-02), with a provenance row each. Four paperwork projects created (`AE-biomaGUNE-1116`, `-1420`, `-1520`, `Project-0521` incl. the old `0720` documents). Found on the way: nested archives were never catalogued (9; 250 `.czi`, of which 14 are new → raw one-off), and the claims pass's `.7z` member paths did not join to the catalog (fixed by a normalised key). Tool: `tools/drive_staging/nonraw_placement.py`; record: `tasks/drives_nonraw_placement_review.md`.

**BACKLOG (new items):**
> - 🔺 **2b mapping + 2c holding folder (historical drives)**: Ryan fills `tasks/drives_nonraw_mapping_worksheet.csv` (do the 62 `A` rows; blank = holding); a session applies it with `tasks/drives_nonraw_2b_2c_followup.md` (fully tooled: `remap` → `apply-raw` → `copy`, then `holding`). **Decide Part 0 first:** whether the D: staging must be kept until the mapping is done (option A) or the holding folder is filled now so D: can go (option B).
> - 🔸 **Long paths under `historical_drives\`** (9,522 placed files > 259 chars, all from three deep archives): decide shorten (labels / drop the repeated archive top folder) vs. accept; it is a rename either way.
> - 🔸 **Aperio `.svs` (15, Drive zuri TUNEL)**: instrument not onboarded; holding by default.
> - 🔹 **`catalog.py` does not open nested archives**; `nonraw_placement.py nested` is the stopgap. Fold it in if the catalog is reused for another drive.
