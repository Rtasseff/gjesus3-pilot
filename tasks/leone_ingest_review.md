# `LEONE.zip` → project `LEONE`: comparison with `DTS24` and ingest proposal

**Stream C of the 2026-10-03/04 close-out weekend** (branch `feat/leone-ingest`; coordinator
`gj3-handoff`; plan [`historical_drives_closeout_plan.md`](historical_drives_closeout_plan.md)
Step 5 item 5).

**Status: ✅ Ryan has ruled (2026-10-02). Placement manifest built; the copy waits on stream A's
destination function and the coordinator's write window.** Nothing has been written to
`J:\gjesus3-data`.

> **✅ DECIDED — Ryan, 2026-10-02 (relayed word for word by the coordinator):** *"Do not ingest any
> of the DICOM images that we already have. No duplicates for this. This is clearly part of dts24.
> All the other data goes in the dts project folder under an appropriate subfolder. If there is not
> one, create a sub folder for other data."*
>
> **This supersedes the proposal in §6** (kept below as the record of what was weighed):
> - **No** new project `LEONE`, **no** `XUS` code, **no** new registry rows, **no** `raw_linked`
>   links. Nothing that duplicates `DTS24` is copied anywhere.
> - The **new content is copied as files** into
>   `projects\DTS24\working\historical_drives\<drive tag>\LEONE\` with a header-driven second level:
>   `echo\` (36 exams, 2,026 files, 57.36 GB), `mr_supplements\` (28 exams, 5,063 files, 1.75 GB:
>   the 3.02 `3D QFlow` series, the 1,062 raw-data objects, one other image) and `derived\`
>   (13 cases, 72 files, 0.05 GB). **7,161 files, 59.15 GB.** Path compaction, `_INDEX.csv` and
>   `README.txt` follow stream A's drives-material rule.
> - Layout under `LEONE\`: `<category>\<case>\<studydate>_<modality>\[S<n>_<series>\]<file>`, with
>   `<case>` from the DICOM header (so `LEONE 1.16/` → `LEONE_1.10`). 36 Philips basenames that repeat
>   across series (`I10`, `I20` …) get a SOP-UID suffix. The index records each file's full original
>   path inside `LEONE.zip` and its header identity. No names or DOBs go into either.
> - The files keep their DICOM identifiers, as `DTS24`'s primaries do. Same exposure; flagged for the
>   privacy back-fill (§10).
> - Manifest: `placement_manifest.csv` in the evidence folder (built by
>   [`leone_ingest_scripts/s11_placement_manifest.py`](leone_ingest_scripts/s11_placement_manifest.py)).
>
> **Copy dry run, 2026-10-04** ([`s12_place.py`](leone_ingest_scripts/s12_place.py) `--dry-run`,
> using stream A's `historical_paths.py` at `f256a1f` for the budget and the publishing format;
> the coordinator accepted the header-driven layout as is):
> - Destination `projects\DTS24\working\historical_drives\FRIO-X6\LEONE\` (does not exist yet;
>   `DTS24\working\` is empty).
> - **7,161 files, 59.15 GB**: `echo` 2,026 / 57.36 GB / 36 cases; `mr_supplements` 5,063 /
>   1.75 GB / 28 cases; `derived` 72 / 0.05 GB / 13 cases.
> - Longest UNC path **204** (budget 240). 0 budget, component or duplicate errors; 0 destination
>   files already present.
> - `_INDEX.csv`: 7,161 rows, with each file's full original path in `LEONE.zip` and
>   `case … (from DICOM PatientID); <category>; study <date> <modality>` in `note`.
> - `_PATHMAP.csv`: 1,160 folder rows, keyed `D1:LEONE.zip|layout:…`, so they can never collide
>   with A's original-path keys.
> - Any existing `_INDEX.csv`/`_PATHMAP.csv` is merged; a key clash is an error, never an overwrite.
> - Published files: `README.txt` (A's `PROJECT_README`, only if absent) at the base, plus a
>   LEONE-specific `README.txt` and `_ORIGIN.txt` in `LEONE\`.
> - Execute copies each member from the verified SSD copy, checks its SHA-256 before and after the
>   write, never overwrites, and writes the index last.
>
> **✅ DONE — copied and verified 2026-10-04**, in the coordinator's write window (stream A was
> writing to other projects; no registry writer ran).
> - **The copy** (`s12_place.py --execute --window`): **7,161 / 7,161 copied, each SHA-256-verified
>   before and after the write, 0 errors**, 2,177 s.
> - **Verification** ([`s15_verify.py`](leone_ingest_scripts/s15_verify.py)): **PASS**.
>   - *Per category on the NAS vs the manifest*, all exact: derived 72 files / 52,229,718 B;
>     echo 2,026 / 57,356,498,928 B; mr_supplements 5,063 / 1,745,992,806 B. 0 missing, 0 wrong
>     size, 0 unexpected files.
>   - *Fresh re-hash from the NAS*: all 72 derived + 300 random files, 0 mismatches.
>   - *Published files*: `_INDEX.csv` 7,161 rows, all matching the manifest; `_PATHMAP.csv` 1,160
>     rows; both READMEs and `_ORIGIN.txt` present.
>   - *Unchanged*: `registry_raw.csv` 25,790 → 25,790 rows; all 8 registry CSVs byte-identical
>     (SHA-256, before/after snapshot via [`s14_snapshot.py`](leone_ingest_scripts/s14_snapshot.py));
>     the 75 `DTS24` `/raw/` folders unchanged (names, sizes, mtimes).
> - **DOB grep on every published text file** (the 5 in the tree: `_INDEX.csv`, `_PATHMAP.csv`,
>   both `README.txt`, `_ORIGIN.txt`): **CLEAN, 0 hits**.
> - Evidence: `s12_execute.out`, `s15_verify.out`, `s13_published_grep.out`,
>   `snapshot_before.json` / `snapshot_after.json` in the evidence folder.

**Evidence folder:** `D:\projects\gjesus3\staging\_analysis\leone-ingest\` (scripts, scans, tables;
paths below are relative to it). The one-off analysis scripts are also committed beside this file
in [`leone_ingest_scripts/`](leone_ingest_scripts/) as the record.

---

## 1. The answer in one paragraph

`LEONE.zip` is **a 2021–2023 working set of the same LIONS cohort that `DTS24` already holds** — a
re-export from a different Philips workstation, not new imaging. Of its **560,402 distinct DICOM
instances, 553,241 (98.7 %) are already in `DTS24`**, matched by `SOPInstanceUID`, and a 507-instance
sample confirms the pixel data is **identical** (the bytes differ only because the header was
re-serialised by another tool). What is genuinely new is **7,161 instances, ~59 GB**, and almost all
of it is one thing: **echocardiography (US) — 36 exams, 2,026 instances, 57.4 GB — for 36 LIONS
patients, 8 of whom have no MRI in `DTS24` at all.** Beyond that: one extra 4,000-image `3D QFlow`
series that `DTS24`'s copy of case 3.02 lacks, 1,062 Philips raw-data objects (1.5 GB) that `DTS24`'s
export left out, and 72 small derived objects (analysis screenshots, key images, reports).
**Recommendation: do not ingest LEONE wholesale.** Create project `LEONE`, ingest only the new
content, and hard-link the 27 overlapping `DTS24` MR exams into it so the project shows the whole
working set without a second copy of ~60 GB.

## 2. What is in `LEONE.zip`

- **Archive:** `D:\projects\gjesus3\staging\drive1_FRIO-X6_2322E4A111E7\files\LEONE.zip`,
  81,907,898,175 bytes, SHA-256 `88b4eb46…f0eb8b897` (drive manifest), archive mtime 2024-02-21.
- **Members:** 671,805 top-level files, plus **64,326** inside the four nested `Leone-*.zip` (the
  catalog's 671,805 does not count those) → **736,131 members scanned, 0 read errors.**
  735,409 parse as DICOM; 722 do not (§5).
- **Layout** (headers, not folder names, decide identity — see the trap in §4.3):

| Source group in the zip | Files | GB | What it is |
|---|---:|---:|---|
| `ExportLeone/` | 560,306 | 118.3 | 1,234 export folders (`LEONE_<yyyymmdd>_<time>/`, one per series, plus one `2023…` exam folder). **Holds 560,301 of the 560,402 distinct instances** — every other group is (almost) a subset of it. Exported 2023-12-27/28. |
| `CNIC/MR/` | 6,491 | 1.1 | MR for cases 1.01 and 1.05 — all already in `DTS24`. |
| `CNIC/ECO/` | 311 | 4.9 | **Echo (US)** for cases 1.01–1.04, 1.06 — new vs `DTS24`, but every instance is also in `ExportLeone`. |
| Case folders `LEONE1.01`, `LEONE 1.13`, `LEONE 1.16`, `LEONE 304`, `LEONE10`, `LEONE15`, `LEONE17`, `LEONE18`, `LEONE3.03`, `leone109`, `LEONE1.04` | 104,689 | 14.3 | Per-case MR exports (Philips `DICOM/`+`DICOMDIR`); `LEONE1.04` is echo. (Totals include the 11 course files listed below.) |
| Nested `Leone-109.zip`, `Leone-15.zip`, `Leone-17.zip`, `Leone1-16.zip` | 4 (+64,326 inside) | 2.3 | One MR exam each, 16,000-image subsets — **not byte-identical to any `DTS24` primary** (checked by SHA-256 against `production_hashes.csv`). |
| Course material in `LEONE 1.13/MASTER HF2021 SEC/` | 11 | 0.07 | A clinician's heart-failure course: PDFs, slides, a questionnaire. Not data. |

## 3. Method

1. **`DTS24` side.** Every `.zip` primary in `PROJ-0054` (42 LIONS + 3 HPIC zips) read member by
   member over SMB, one archive at a time: SHA-256 and DICOM UIDs of each member. **928,782 members,
   926,765 DICOM, 926,765 distinct `SOPInstanceUID`s, 0 errors; exactly one `StudyInstanceUID` per
   acquisition** (`scan/dts24_ACQ-*.csv`, `dts24_sop_index.csv`, `dts24_exams.csv`). The 30 HPIC
   `.rar` primaries were **not** opened: HPIC is a different hospital cohort (`HPICnn` ids,
   2018–2021) and no LEONE patient id or study UID points at it.
2. **LEONE side.** Full member scan (SHA-256 + UIDs, nested zips recursed) of a byte-verified SSD copy
   (`scan/leone.csv`). *Why a copy:* `D:` is a shared HDD that the other streams' 7-Zip jobs had
   saturated; per-member reads there ran at ~10 members/s (~19 h). The copy is approved by the
   coordinator (2026-10-02) on three conditions — not under OneDrive, verified by SHA-256 against the
   drive manifest (**MATCH**, `C:\Users\rtasseff\temp\scratch_leone-ingest\verify.log`), deleted at
   stream close (§9).
3. **Comparison** by `SOPInstanceUID` first, SHA-256 second (`compare_by_group_case_study.csv`,
   `case_table.csv`, `dts24_missing_from_leone.csv`).
4. **Same image or not?** For the 27 overlapping `DTS24` acquisitions, 20 random shared instances
   each were re-read from both sides and `PixelData` compared (`pixel_verify_sample.csv`):
   **507 / 507 pixel-identical**, 1 with no pixel data. The only header differences are the export
   tool (`ISCV 4.1` in LEONE vs `AVW_15.0` in `DTS24`), a few vendor-private tags, and
   floating-point re-serialisation of `ImageOrientationPatient` / `ImagePositionPatient` at the
   ~8th decimal (186 of the sample). 32 sample draws errored on a bug in the verify script (it
   could not address members of the nested zips) — not a data issue; those instances also exist
   un-nested and were sampled there.
5. **Every member assigned one disposition** (`leone_member_disposition.csv`, §5).

## 4. The comparison

### 4.1 Per source group (distinct instances in that group)

| Source group | Distinct instances | Already in `DTS24` | New | Note |
|---|---:|---:|---:|---|
| `ExportLeone` | 560,301 | 553,241 | 7,060 | the superset |
| **LIONS case folders** (`LEONE1.01`, `LEONE 1.13`, `LEONE 1.16`, `LEONE 304`, `LEONE10`, `LEONE15`, `LEONE17`, `LEONE18`, `LEONE3.03`, `leone109`) | 104,251 | 103,956 | 295 | summed per folder; 97 of the new ones exist **only** here, not in `ExportLeone` (mostly `LEONE17`/`LEONE18` derived objects; the other 4 ExportLeone-less ones are in `Leone-17.zip`) |
| `LEONE1.04` (echo) | 46 | 0 | 46 | US; also in `ExportLeone` |
| **`CNIC/MR`** | 6,490 | 6,490 | 0 | |
| **`CNIC/ECO`** (echo) | 306 | 0 | 306 | US; also in `ExportLeone` |
| **Nested `Leone-109.zip`** (case 1.09) | 16,004 | 16,000 | 4 | |
| **Nested `Leone-15.zip`** (case 1.15) | 16,000 | 16,000 | 0 | |
| **Nested `Leone-17.zip`** (case 1.17) | 16,004 | 16,000 | 4 | |
| **Nested `Leone1-16.zip`** (case **1.10** — see §4.3) | 16,004 | 16,000 | 4 | |
| **All of LEONE** | **560,402** | **553,241** | **7,161** | |

### 4.2 Per case (patient) — 50 cases

`DTS24` LIONS = 42 cases; LEONE adds 8 echo-only patients. Classification per the handoff's terms:

| Class | Cases | What it means |
|---|---|---|
| **MR: same exam, near-identical** + **US: new exam, same patient** | 26 — 1.01–1.10, 1.12, 1.13, 1.15–1.18, 2.05, 2.07, 2.10, 2.11, 3.03–3.06, 3.08, 3.09 | Same `StudyInstanceUID` as the `DTS24` acquisition. LEONE adds 26–51 Philips raw-data objects per exam (+ a few derived objects); `DTS24` holds 0–4 instances LEONE lacks. The echo is a **separate study**, usually the same day. |
| **MR: same exam, LEONE superset** + US new | 1 — **3.02** | LEONE has a whole `3D QFlow` series (4,000 images, SeriesNumber 3601) that `ACQ-20220124-XMRI-002` lacks (`DTS24` 17,783 vs LEONE 21,822 instances). |
| **MR: LEONE holds a fragment** + US new | 1 — **2.12** | `DTS24` has the full exam (20,881); LEONE has one raw-data object of it (new). |
| **US: new exam, patient has no MR in `DTS24`** | 8 — 2.01, 2.02, 2.03, 2.04, 2.06, 2.08, 2.09, 3.01 | Echo only. All 8 ids are in the LIONS cohort sheet (`dataset_information_lions.xlsx`, 58 cases), so this is the same cohort, not a new collaborator. |
| **`DTS24` only — exam not in LEONE** | 14 — 1.21–1.24, 2.14, 2.16–2.20, 3.07, 3.11–3.13 | All acquired 2024-01 → 2025-01, after LEONE was assembled (Dec 2023). **LEONE is a subset** for these. |

Full per-case numbers: `case_table.csv`. Per (group, case, study): `compare_by_group_case_study.csv`.

### 4.3 Traps found

- **Folder names lie; headers decide.** `LEONE 1.16/` and nested `Leone1-16.zip` contain **case
  1.10** (study 2022-06-09 = `ACQ-20220609-XMRI-001`), not 1.16. `LEONE1.04/` carries the patient id
  `LEONE-1.04` (hyphen) in its own copy. Any shape that keys on folder names would mis-file these.
- **SHA-256 alone would have called everything "new".** 0 of 553,241 shared instances is
  byte-identical, because the header was re-serialised on export.
- **DTS24 3.02 is incomplete** relative to LEONE (the `3D QFlow` series). Worth a line in the
  `DTS24` record whatever is decided here.

## 5. Every member accounted for

`leone_member_disposition.csv` — one row per member, **0 unclassified**:

| Disposition | Members | GB |
|---|---:|---:|
| Already in `DTS24` (first LEONE copy of each shared instance) | 553,241 | 59.28 |
| Duplicate copy **within** LEONE (same instance in a second/third LEONE folder) | 175,007 | 23.74 |
| **NEW raw: echo (US)** — 36 exams, 36 patients | 2,026 | 57.36 |
| **NEW raw: MR images** — 4,000 = 3.02 `3D QFlow`; 1 other | 4,001 | 0.24 |
| **NEW raw: MR Philips Raw Data Storage objects** (`1.2.840.10008.5.1.4.1.1.66`) across 28 exams | 1,062 | 1.50 |
| **NEW derivative**: secondary captures (`CardiacMRAnalysis results…`, `Key Images – Para informe`), SR, PR, KO | 72 | 0.05 |
| Container: the 4 nested zips (their members are counted individually above) | 4 | 2.25 |
| Excluded: macOS AppleDouble `._*` | 672 | 0.00 |
| Excluded: macOS `.DS_Store` | 19 | 0.00 |
| Excluded: `DICOMDIR` index files (path indices, regenerable) | 13 | 0.19 |
| Excluded: unrelated course material (`LEONE 1.13/MASTER HF2021 SEC/`) | 11 | 0.07 |
| Excluded: personal notebook `ExportLeone/decompress_dicom.ipynb` (+ checkpoint) | 2 | 0.00 |
| Excluded: 0-byte file `LEONE18/Export/DICOM/S69470/S35010/I32620` | 1 | 0.00 |
| **Total** | **736,131** | **144.7** |

The notebook is worth a sentence: it was written to decompress the export, but its filter
(`file.endswith("*.*")`) never matches, so it changed nothing.

## 6. Proposal — 📋 Ryan's go and four decisions needed

### 6.1 What to write

| # | Action | Size | Registry effect |
|---|---|---|---|
| A | **Create project `LEONE`** (`create_project.py`) — owner `JRC`, description mirroring `DTS24` (proposed text in §6.3). | — | +1 `registry_projects` row |
| B | **Ingest the 36 echo exams** as 36 new acquisitions (one per `StudyInstanceUID`), `data_source: collaborator:LIONS`, project `LEONE`. | 2,026 instances, 57.4 GB | +36 `registry_raw` rows |
| C | **Ingest the new MR raw content** as supplements to the `DTS24` exams: the 3.02 `3D QFlow` series and the 1,062 raw-data objects (decision D3). | 5,063 instances, 1.7 GB | +1 to +28 rows (D3) |
| D | **Hard-link the 27 overlapping `DTS24` MR acquisitions** into `projects\LEONE\raw_linked\` (Project Manager import path, 10_TOOLS §5.3) so the project shows the whole working set. | 0 bytes | **none** — per 06_REGISTRIES §2.3b `project_id` stays `PROJ-0054`; the share is a link + a `LEONE` provenance row |
| E | **Copy the 72 derived objects** into `projects\LEONE\outputs\` (raw-vs-derivative rule: they are analysis outputs, not acquisitions). | 0.05 GB | none |
| — | Not written: the 553,241 already-in-`DTS24` instances, the 175,007 internal duplicates, and the 722 excluded files. | | |

### 6.2 Decisions for Ryan

- **D1 — Go / no-go on the shape above** (new content only + links), versus ingesting LEONE whole
  (≈ +553k duplicate instances / ~60 GB of a second copy of `DTS24`, which I do not recommend).
- **D2 — An instrument code for external echo.** No `X`-code covers ultrasound today
  (`XMRI`/`XCT`/`XPET`/`XSPECT`/`XMIC`). **Recommend `XUS`** (ecosystem `DICOM`), following the
  `X`-prefix rule in [03_RAW_STORAGE §3.2](../mfb-rdm-docs/03_RAW_STORAGE.md). This is a small code
  change (`tools/ingest/config.py` code list + ecosystem map) and a spec row in 03 §3.2 / 09 —
  Data Office vocabulary call, so I have not made it.
- **D3 — How to store the MR supplements.** They belong to exams that already exist as `DTS24`
  acquisitions, and acquisitions are immutable.
  - **(a) Recommended:** one `XMRI` acquisition **per exam** holding that exam's new members
    (28 rows: 27 raw-data bundles, 3.02's bundle also carrying the `3D QFlow` series, plus 2.12's
    single object), in project `LEONE`, `notes` naming the `DTS24` ACQ-ID it supplements. Nothing
    lost, nothing duplicated.
  - (b) Only the 3.02 `3D QFlow` series (1 row); leave the 1,062 raw-data objects out with a
    recorded reason. They are Philips vendor-private, non-image objects, and `DTS24`'s own export
    omitted them — but they *are* scanner output, so I lean against dropping them.
  - (c) Defer C entirely to the per-series re-shape in BACKLOG 🔺 "one row per EXAM, not per
    series", which will touch these exams anyway.
- **D4 — Echo metadata.** `subject:`/`condition:`/`anatomy:` can mirror `DTS24` exactly (same
  cohort, same transplant population). Of the two attached tables: `source_project` (grant
  PI20/01389, PI Juan Delgado) applies as-is; **`dataset_information` describes the MRI scan**
  (`instrument/modality = PHILIPS MRI`), so attaching it to an echo row would misdescribe it —
  **recommend not attaching it to the US rows** (attach it to the MR supplements only).
  The hemodynamics workbook used for `DTS24` (`C:\Users\rtasseff\temp\LIONS_42cases\…ESTUDIO
  HD.xlsx`) **no longer exists** (that folder was found deleted 2026-09-28), so it cannot be
  attached to anything new. Its content survives in the 42 `DTS24` sidecars.

### 6.3 Shape, and why it matches `DTS24`

Per the handoff, LEONE should match `DTS24` unless a BACKLOG item says otherwise, so that one
backfill later covers both:

- **Unit = one exam (`StudyInstanceUID`) per acquisition**, as `DTS24`. The 🔺 HIGH item says this
  is the wrong unit long-term (series is), but it also says the fix is a re-shape of *all* external
  archives — matching now means the same re-shape covers LEONE's 36–64 rows rather than inventing a
  second convention. The echo exams are small (1–5 series each), so the cost of the exam unit is low
  here.
- **Container = `.zip`, `acquisition_layout: archive`**, as `DTS24`. LEONE does not arrive as one
  archive per exam, so the per-exam zip has to be **assembled**: the exam's as-received member files,
  byte-for-byte, under their original LEONE paths, in a standard `.zip` (Deflate). This is the
  "normalise to `.zip`" outcome of the 🔸 "pick ONE archive container" item, so it does not create a
  third format. It is **not** verbatim-as-received at the archive level (there is no such archive to
  keep); member-level SHA-256s from the scan are kept in the evidence folder, so every member can be
  traced back to `LEONE.zip`. **Flagging this as the one place LEONE deviates from `DTS24`'s
  "store the collaborator's own archive" rule.** If Ryan prefers, the alternative is
  `acquisition_layout`-less loose DICOM under `series/` (2,026 files for all the echo — small), which
  avoids building archives but breaks the one-archive-per-exam match.
- **Identity from headers only:** `sample_id` / subject = `PatientID` (normalising `LEONE-1.04` →
  `LEONE_1.04`), exam = `StudyInstanceUID`, `acquisition_datetime: "${discovered.dicom_study_date}"`
  (the `DTS24` wrong-date trap).
- **Privacy:** the `DTS24` pattern unchanged — `dicom_headers: true` (curated allow-list; no
  `PatientName` / `PatientBirthDate` in any sidecar or `registry_subjects.csv`), age in whole years,
  the operator `subject:` block so the animal DB is never consulted.

**Proposed project text (A):** owner `JRC`; description *"MFB working set LEONE: the LIONS cohort's
2021–2023 cardiac MRI and echocardiography as assembled by the collaborators (LEONE.zip, historical
drive 1). New content (echo, MR supplements) is ingested here; the MR exams already archived under
DTS24 are linked, not copied."*

### 6.4 After the go — runbook

1. Back up the registries off-NAS to a **fresh** dated folder `C:\Users\rtasseff\temp\gjesus3_registry_backup_<yyyymmdd_hhmm>_leone\`.
2. (D2) add `XUS` in code + spec on this branch; tests.
3. Build the per-exam staging on the SSD scratch from `new_members.csv`: extract each exam's members
   to `<case>_<US|MRsupp>_<studydate>\` and zip them to the `archive_primary_from` folder; verify
   every member's SHA-256 against the scan.
4. `create_project.py` → `LEONE`.
5. Write `tools/configs/leone_echo.yaml` (+ `leone_mr_supplement.yaml` per D3) modelled on
   `dts24_lions_cardiac_mri.yaml`; **dry run** and check: 36 (+D3) rows; every date in 2021-10 →
   2023-12 and equal to the exam's `StudyDate`; `sample_id` = header `PatientID`; counts per exam vs
   `new_content_by_exam.csv`; no `DTS24` SOP in any staged exam.
6. In the coordinator's write window: ingest; link the 27 `DTS24` acquisitions (D); copy the 72
   derived objects (E).
7. Verify: row counts; each `checksums.json` against the staged zip; unzip-and-hash every member
   against `new_members.csv`; `validate_registries` (expect the known 10,314 `operator` errors and
   nothing new); **privacy grep** of every new sidecar and `registry_subjects.csv` for every
   `PatientName` and `PatientBirthDate` value in `scan/leone_identifiers.csv`; `samefile` on the
   links.
8. Report to the coordinator; then delete the SSD scratch (§9).

## 7. Privacy observations

- **`PatientName` is not a person's name.** Measured 2026-10-04 (counts only, no values printed):
  in LEONE it is the literal cohort label `LEONE` on 735,364 instances and a 9-character `LEONE…`
  label on the other 45; in all 926,765 scanned `DTS24` instances it is likewise a LEONE/HPIC
  label. The collaborators pseudonymised names before sending.
- **The real direct identifier is `PatientBirthDate`.** It is present on ~91 % of instances in both
  (668,599 / 860,838; 26 distinct dates in LEONE). It stays in the files' headers, as in `DTS24`'s
  primaries, by Ryan's ruling. `OtherPatientIDs` and `AccessionNumber` are empty everywhere.
- **Privacy grep** (`leone_ingest_scripts/s13_privacy_grep.py`, counts only; it treats the cohort
  label as not-a-needle): **CLEAN, 0 DOB hits** across the would-be `_INDEX.csv` / `_PATHMAP.csv`,
  the placement manifest, this doc and the scripts. Re-run on the published files after the copy.
- LEONE's export adds a `(0010,2154) PatientTelephoneNumbers` element; in a sample of 132 new
  instances it, `PatientAddress` and `ReferringPhysicianName` are all **empty**.
- All 60 sampled echo instances declare `BurnedInAnnotation = NO`. That is the header's claim; the
  pixels have not been inspected, and US frames often carry on-screen text. **Recommend the later
  privacy backfill (BACKLOG 🔺 human/privacy flag) treat echo pixels as possibly identifying.**
- The identifier values themselves live only in `scan/leone_identifiers.csv` and
  `scan/dts24_*_identifiers.csv` on `D:` (not synced, never committed), kept solely as needles for
  the post-ingest privacy grep.

## 8. Open questions for the coordinator / Ryan

| # | Question | Why it matters |
|---|---|---|
| Q1 | D1–D4 above. | They decide what is written. |
| Q2 | Should the `DTS24` record note that `ACQ-20220124-XMRI-002` (case 3.02) lacks the `3D QFlow` series LEONE has? | A `DTS24` user would otherwise not know a fuller copy exists. |
| Q3 | Is a LEONE-scoped `metadata/README` wanted explaining that the MR lives under `DTS24`? | The project would otherwise look MR-less in `/raw/` terms. |

## 9. Scratch and deletions (to complete at stream close)

| Item | Location | Status |
|---|---|---|
| SSD copy of `LEONE.zip` (82 GB, verified) | `C:\Users\rtasseff\temp\scratch_leone-ingest\LEONE.zip` | **⚠️ NOT YET DELETED.** The copy is verified (2026-10-04), so it is no longer needed. My `rm -rf` of the folder was denied by the session's permission check; Ryan to delete or approve. |
| SSD working copies of the scan tables | same folder (`leone.csv`, `dts24_sop_index.csv`, `s05`–`s11` script copies) | **⚠️ not yet deleted** (same folder, same reason); the scripts are in `leone_ingest_scripts/` |
| Per-exam extracts / assembled zips | — | **none were ever made** (Ryan's ruling removed the ingest; the copy reads members straight from the zip) |
| Evidence folder incl. identifier needles | `D:\projects\gjesus3\staging\_analysis\leone-ingest\` | keep until the privacy grep is done; then delete `scan/*_identifiers.csv` |

## 10. Proposed wording for the shared files (coordinator applies at merge)

**`tasks/STATUS.md`** (drives bullet / §2): *"`LEONE.zip` (drive 1) compared member-by-member with
`DTS24`: 553,241 of its 560,402 DICOM instances are already in `DTS24` (pixel-identical re-export).
New content = 36 LIONS echocardiography exams (57.4 GB, 8 patients with no MRI in DTS24) + 5,063 MR
supplement instances + 72 derived objects. Ryan's ruling (2026-10-02): no duplicates, no new project
or registry rows. The 7,161 new files (59.15 GB) are copied to
`projects\DTS24\working\historical_drives\<drive tag>\LEONE\{echo,mr_supplements,derived}\`
<done / pending>."*

**`CHANGELOG.md`** (new row, dated at ingest): *"`LEONE.zip` → project `LEONE`. Member-level
comparison with `DTS24` by `SOPInstanceUID` (SHA-256 alone would have called every instance new —
the export re-serialises headers; a 507-instance sample is pixel-identical). LEONE is a 2021–23
working set of the LIONS cohort; only the echo, the MR supplements and the derived objects are new.
Ryan: "clearly part of dts24", so no duplicates, no new project, no registry rows. The new content
goes into DTS24's project folder as files (`working\historical_drives\…\LEONE\`), with an index
carrying each file's original path and header case id. Folder names in LEONE do not match case ids (`LEONE 1.16/` holds case
1.10); identity taken from headers only."*

**`tasks/BACKLOG.md`:**
- Under 🔺 **human/privacy flag** and 🔺 **DPA reference**: add
  **`projects\DTS24\working\historical_drives\…\LEONE\`** (7,161 files with full DICOM identifiers
  in their headers) to the back-fill scope, beside the `DTS24` acquisitions (both cohorts) and the
  Charité `XMIC` files. Note that **echo pixels may carry burned-in identifiers** despite
  `BurnedInAnnotation = NO`. These are project-folder files, not acquisitions, so a registry-level
  flag will not reach them on its own.
- Under 🔺 **"one row per EXAM, not per series"**: when the re-shape runs, consider promoting the
  `LEONE\mr_supplements\` series (3.02 `3D QFlow`, the raw-data objects) into the matching `DTS24`
  exams, and the 36 echo exams into `/raw/` once an external-echo instrument code exists. Ryan's
  2026-10-02 ruling placed them as files for now.
