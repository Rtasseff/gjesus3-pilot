# Drive 3 (M. Jesús): raw imaging on the drive, against production (part A1)

**Status:** 🔶 DRAFT for the coordinator, 2026-10-06. Read-only throughout: nothing was written to `J:\` (production or the
staged copy) or to `K:\`; the facility DB was asked `SELECT`s only. Not committed (the coordinator commits).
**Brief:** `HANDOFF.md` §5 (part A1) in this worktree; the hub's brief `…\historical-mjesus-drive\HANDOFF.md` §6.3, §6.4, §6.5, §7.
**Evidence (regenerable, not backed up):** `D:\projects\gjesus3\drive3_analysis\a1\`. **Scripts:** `tools\drive_staging\drive3\a1_*.py` (§9).
**Units:** GB = 10⁹ bytes. The hub's brief printed GiB under the label "GB"; where a number is compared with the hub's, both are given.
"Exam" = one ParaVision examination folder = one production MRI acquisition (`original_name` = `<study>/<exam>`).

---

## Summary

### The numbers that matter

| | On the drive | Already in production | **Not in production** | Would add to `/raw/` |
|---|---:|---:|---:|---:|
| **MRI** (Bruker exams) | 7,345 exams in 422 studies | **3,965** (3,618 byte-identical; 347 the same acquisition in another form) | **3,380** exams in 198 studies: 3,132 with the scanner's own DICOM, 177 convertible, 71 not convertible | **5.1 GB** of DICOM (+ about 0.25 GB once the 177 are converted) |
| **PET/CT** (Molecubes reconstructions) | 492 distinct (909 files) | **290** | **202**: 102 nowhere else, 100 only in the `S:\gnuclear` snapshot (held back in August) | 8.0 GB |
| **Microscopy** (`.czi`, `.lif`) | 6,094 distinct files (6,993) | **836** (717 byte-identical; 119 re-saves of a production acquisition) | **5,258** files, 803 GB: 5,115 Cell Observer (643 GB), 116 from an Axioscan 7 that is not ours (154 GB), 26 Leica (6.8 GB), 1 unreadable | 803 GB |
| **Other DICOM** | 35,184 extension-less files (pig cardiac MRI, an external Philips scanner, 2014) | 0 | 35,184 (7.6 GB) | external: not decided |

1. **By bytes, 117,212 of the drive's 621,969 files (67.4 of 1,681 GB) are already in production `/raw/`.** This reproduces
   the coordinator's first cut exactly (MRI\ `.dcm` 53,217 of 153,150; Microscopio\ `.czi` 448 of 5,834). It understates
   coverage: production stores an MRI exam as DICOM only, so the drive's `fid`/`rawdata.job*` (444 GB) can never match. **By
   acquisition, production already holds 3,965 of the drive's 7,345 MRI exams (54 %)**, 290 of its 492 PET/CT
   reconstructions and 836 of its 6,094 distinct microscopy files.
2. **3,380 MRI exams (198 studies) are not in production, 3,309 of them images.** They are MFB sessions of 2019–2021 (3,163
   exams), 197 exams of 2022 and 20 of 2024, all under the PI's console account (`jrc`; once `JRC`). **Every study's protocol claim checks
   out in the facility DB except one**: 187 confirmed (183 with an MRI logged within 3 days of the scan), 9 with the animal in
   the protocol but nothing logged, 1 decided by the DB between two claimed protocols (`1116`), and **1 contradicted**
   (`jrc191015_m174_flow`: animal 174 of `0619` was born in 2021, two years after the scan).
3. **The hub's "331 missing studies" are 190 studies.** 133 of its 331 names are folders *named* after a study that hold no
   scan (Splits volumes, NIfTI exports, segmentations; `Otros\` holds no exam folder at all, so its "118 Bruker studies" are
   all of this kind), and 8 were ingested by stream B on 2026-10-04. Re-run today with the hub's own method: **353 in
   production / 286 not** (production has gone from 984 to 1,113 MRI study names).
4. **Protocol `0118`: 28 studies, 526 exams, 48.9 GB on the drive, 0.60 GB as DICOM.** Every animal is a `0118` rat in the
   facility DB with an MRI logged on the scan day (the `m`-prefixed ones too). Two of Ermal's eight 2021 sessions on
   `K:\gjesus\MRI\Proyecto 0118` are here (`m175`, `m178`); each exists twice on the drive as two different
   reconstructions, one of them byte-identical to the K: copy. The other six are on K: only.
5. **Three things production does not know yet**: six of the 57 study folders the D3 re-scan "found nowhere" are on this drive
   with native DICOM (`0619` animals 191–200, 2022-01-25; STATUS §0.4 N6); one 2024 study (`jrc240702_m93_0522`, 20 exams) is in
   neither production nor today's scanner listing nor June's; and **100 held-back `S:\gnuclear` reconstructions each carry a
   valid protocol code in their own snapshot path**, missed because the pull's parser looks further up only when it found a
   *wrong* code, not when it found none (§4).

### Decisions this raises for Ryan (each with a recommendation)

| # | Decision | Recommendation |
|---|---|---|
| **R1** | **The 3,309 MRI image exams production lacks** (3,132 native DICOM, 177 convertible, in 190 studies). Ryan's 2026-09-30 line made the hub's 331 "a note, not an action"; this is that note, measured. | **Ingest them**, the way stream B did drives 1+2: one scoped config per batch (57 studies parse with neither production regex), convert first for the 177 (Ryan's 2026-10-04 rule), `instrument_model` set explicitly for the **296 exams from the 11.7T** (the `BIOSPEC 500` → "50T" bug, drives review §7), project = the DB-confirmed claim. Leave `jrc191015_m174_flow` blank (C). `/raw/` grows by about 5.3 GB. The 2019–2021 sessions may also sit in the MRI platform's archive (Ryan, 2026-10-06); this drive is the copy we already hold. |
| **R2** | **Protocol `0118`** (the coordinator is taking the project question to Ryan). The MRI side of either answer: 506 exams with native DICOM, 0.60 GB; subject ids are `<n>-AE-biomaGUNE-0118` either way. With `AE-biomaGUNE-0118` (`PROJ-0060`), its links land beside Lucia's Cell Observer histology and drive 1's `Proyecto 0118 Monocrotalina` material, and its description must cover both studies; with a new `Proyecto-0118-rats-hipoxia`, `PROJ-0060` stays Monocrotalina. | **Decide all `0118` MRI at once**: the drive's 26 rat studies of 2019–2020 **and** Ermal's 8 sessions of 2021 (STATUS N7). Take Ermal's from `K:` (it has all 8; the drive has 2), and for `m175`/`m178` register the reconstruction that is byte-identical to K:; the drive's other reconstruction goes to the project folder as the researcher's re-reconstruction (§3). |
| **R3** | **STATUS N6 shrinks**: 6 of the 57 "found nowhere" 2022 studies (87 exams, DB-confirmed `0619`) are on this drive; and `jrc240702_m93_0522` (2024, 20 exams, DB-confirmed `0522`) is nowhere else we know. | **Ingest these 7 studies from the drive** in R1's first batch, and take the 6 off any request to the platform's archive. |
| **R4** | **PET/CT: 202 reconstructions** production lacks: 102 nowhere else (`0619` 2-DG 2021, `0320` 2021-06-01, `1422` 2023), 100 in the `S:\gnuclear` snapshot (`0619` diets and BrEt 2021–22, `0320` CAV1 2022, `1019` 2022, `1123` gated CT 2024). 201 of 202 are DB-confirmed (the animal is in the claimed protocol and logs a PET/CT that day). | **Ingest both sets** (the 100 from the snapshot need no bytes from this drive). And **record in BACKLOG** that `ni_gnuclear_discover.analyse()` should walk up for a valid code when it found none: re-running it would likely release more of the 673 held back. |
| **R5** | **Microscopy: 5,115 Cell Observer files (643 GB)** not in production, mostly `Microscopio\Microscopio- MJesus Sanchez 2023` (2021–2023 histology). | **Ingest after the same two gates drives 1+2 went through**: the drives' same-timestamp pixel check (gate rule "R4" of stream D, `r4_groups.py`) on the 266 groups (541 files) that share an instrument and an acquisition second, then the project claims (A2): 1,438 files claim no protocol and would go blank (C). About 1 % of the NAS. |
| **R6** | **Three instruments gjesus3 does not have**: an **Axioscan 7, serial 4661000340** (ours, `ZWSI`, is 4661000718): 116 files, 154 GB, 2024-10-24 → 2025-02-19, in `Microscopio biodonostia\…`, `Histologia_ratones_viejos\…` and `biomaGUNE MJ\…\Proyecto 1422`; a **Leica TCS SP8, serial 8100000207**: 17 `.lif` + 9 `.lifext`, 6.8 GB, in `Pili y Mili\Proyecto 1121 London\…`; a **Philips Achieva at CNIC**: 35,184 pig cardiac MRI files of 2014 (§6). | **Ask M. Jesús where each was acquired**, then follow the Charité precedent (Ryan, 2026-09-29: external data with its own X-code) for the two microscopes. Hold the pig MRI until A3's segmentation decision, since it is their source image set. |
| **R7** | **`1019` consistency.** Under the drives rule the drive's 61 `1019` sessions of 2020 go to `PROJ-0006` (DB-confirmed). The 854 rows of 2021 from `K:` were registered with a **blank** project by Ryan's 2026-08-21 ruling, when `1019` was closed; it is active again. | Register the drive's under `PROJ-0006`, and ask Ryan whether the 854 should now follow (their folder on `K:` and their study names claim `1019`). |

---

## Method, in one screen

- **Inputs** (§3 of the handoff): the drive manifest (621,969 rows, SHA-256 per file); the production SHA-256 index built from
  every `checksums.json` (516,577 files of 27,034 acquisitions); dated copies of the live registries taken at 10:40 by
  `a1_00_snapshot.py` (`a1\_inputs\SNAPSHOT.txt` records each file's SHA-256); the drives 1+2 placement indexes (18), holding
  manifest and loose-file + archive-member manifests; `K:\gjesus\MRI\Proyecto 0118`; the `S:\gnuclear` snapshot manifest.
- **Files opened on `J:\`**, all read-only: ParaVision `acqp`, `method`, `subject` of every canonical exam (7,345); the first
  132 bytes of every extension-less file outside Bruker folders (35,244); the header of every standalone DICOM (958); the
  metadata segment of every `.czi` (6,967) and the XML header of every `.lif`/`.lifext` (26); and, to establish §2.2, 9
  production DICOMs re-hashed and 4,342 drive/production DICOM pairs opened with pydicom.
- **Dedup is SHA-256 only.** Acquisition identity is decided by the acquisition's own record (study + exam folder, ACQ time,
  CZI `AcquisitionDateAndTime` + device serial, Molecubes timestamp), never by name and size.
- **No attribution is guessed.** A project is proposed only for a claim the facility DB confirms or does not contradict; the
  rest is C, with the evidence.

---

## 1. The whole drive, by SHA-256

**Per top-level folder** (all files / of which raw imaging; "in production" = SHA-256 in a production `checksums.json`):

| Folder | Files | GB | In production: files | GB | Raw imaging: files | GB | of which in production (GB) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `MRI` | 308,204 | 302.9 | 53,217 | 3.3 | 292,916 | 284.4 | 3.3 |
| `biomaGUNE MJ` | 206,839 | 285.4 | 57,967 | 21.6 | 179,708 | 234.5 | 21.6 |
| `Pili y Mili` | 53,729 | 87.8 | 5,445 | 3.6 | 12,008 | 29.7 | 3.6 |
| `Otros` | 44,916 | 43.4 | 0 | 0 | 35,184 | 7.6 | 0 |
| `PET` | 1,099 | 24.9 | 135 | 6.2 | 312 | 12.4 | 6.2 |
| `Microscopio` | 7,180 | 936.8 | 448 | 32.6 | 5,834 | 903.6 | 32.6 |
| 2 loose files | 2 | 0.0 | 0 | 0 | 0 | 0 | 0 |
| **Drive** | **621,969** | **1,681.2** | **117,212** | **67.4** | **525,962** | **1,472.3** | **67.4** |

In the wider sense of the handoff ("in `/raw/`, or placed in a project by drives 1+2, or in their holding folder"), 170,077
files (96.8 GB) are already there; but for raw imaging the extra matches are almost all small ParaVision parameter files that
are byte-identical across scans (`uxnmr.par`, `specpar`, …: 0.4 GB). The one real case is §2.4's 21 spectroscopy exams.

**Per A1 class, whole drive** (`a1\coverage_by_class.csv`; per folder × class in `coverage_by_top_class.csv`):

| Class | Files | GB | In production: files | GB | What it is |
|---|---:|---:|---:|---:|---|
| `mri-dicom` | 245,553 | 14.9 | 116,020 | 7.2 | `pdata\<n>\dicom\MRIm<NN>.dcm` inside an exam folder |
| `mri-2dseq` | 17,820 | 15.2 | 0 | 0 | reconstructed image, ParaVision format (production does not store it) |
| `mri-kspace` | 17,555 | 443.8 | 0 | 0 | `fid`, `rawdata.job0/1` (production does not store it) |
| `mri-params`, `mri-study-params` | 201,899 | 2.2 | 0 | 0 | `acqp`, `method`, `visu_pars`, `uxnmr.par`, `subject`, `result.jcamp`, … |
| `dicom-standalone` | 927 | 36.7 | 444 | 18.4 | Molecubes PET/CT reconstructions (909) and PMOD exports (18) (§4) |
| `dicom-noext` | 35,215 | 9.0 | 0 | 0 | DICOM without an extension: the pig MRI (35,184) and 31 PMOD exports (§6) |
| `microscopy-czi` / `-lif` | 6,993 | 950.4 | 748 | 41.7 | §5 |
| *raw imaging, all* | *525,962* | *1,472.3* | *117,212* | *67.4* | |
| `volume-mhd` | 39,797 | 80.9 | 0 | 0 | MetaImage `.mhd` + `.raw` pairs: `Splits` volumes **derived** from exams |
| `volume-nifti`, `volume-other` | 20,699 | 49.1 | 0 | 0 | NIfTI exports and label maps, PMOD `.voi`, ECAT `.v`, Amira `.am` |
| `mri-study-foreign`, `mri-exam-foreign` | 9,018 | 9.5 | 0 | 0 | non-ParaVision files *inside* study folders: `NIFTI\` exports (6,064 `.nii.gz`), `Splits\` (1,305 pairs) |
| `image-tif`, `figure`, `document`, `analysis`, `video`, `archive`, `software`, `nmr-topspin`, `microscopy-annotation`, `other` | 20,099 | 69.2 | 0 | 0 | non-raw material (A2); `.tif` alone is 5,296 files, 53.9 GB |
| `junk` | 6,394 | 0.3 | 0 | 0 | `desktop.ini`, `Thumbs.db`, `.DS_Store`, `._*`, `~$*` |

**Corrections to the hub's classes** (`records\content_classes.py`; crosswalk in `a1\hub_class_crosswalk.csv`):
- **`.raw` and `.mhd` are not Bruker raw.** All 21,608 `.raw` files with a sibling `.mhd` are MetaImage volumes, almost all in
  `Splits\` folders: derived. The hub counted them as `raw-bruker` (39,797 files, 80.9 GB = 75.3 GiB), plus 2,610 more
  (3.7 GB) of the same kind inside study folders.
- **Bruker raw is k-space + 2dseq + parameters, and production keeps none of it**, only DICOM. So "raw Bruker 508.4 (GiB)" is
  real data that production will never hold by design, not data missing from production.
- **35,215 DICOM files have no extension** and were `other` for the hub: the pig cardiac MRI and PMOD exports.
- `.par`/`.info`/`.jcamp` are ParaVision's own `uxnmr.par`, `uxnmr.info`, `result.jcamp`: the hub was right to call them Bruker.
- With these corrections, raw imaging is **1,472.3 GB (1,371 GiB, 87.6 %)**, not the hub's 1,441.6 GiB (92.1 %).
- Damage worth knowing: **5 raw files are zero bytes** on the drive: `rawdata.job0/1` of `jrc241001_m104_0522/17` (both copies;
  production already calls that exam `no-source`) and `pdata\1\dicom\MRIm7.dcm` of `jrc220303_m80_0320/3` (production holds the
  good file).

## 2. MRI: every Bruker study and exam

### 2.1 What is on the drive, and the canonical copy

- **10,569 exam folders** (a folder holding `acqp` and `method`; every one holds both): `MRI\` 6,147, `biomaGUNE MJ\` 4,134,
  `Pili y Mili\` 288, **`Otros\` none**. They are **7,345 distinct exams in 422 studies** (599 study folders).
- **177 studies exist twice** (none three times): 162 in both `MRI\` and `biomaGUNE MJ\`, 13 twice inside `MRI\`, 2 twice inside
  `biomaGUNE MJ\`. The hub's "355 of 639 exist more than once" counts derived folders too (§2.5).
- **Canonical copy of an exam** = the copy with the most distinct SHA-256 values, then the most bytes, then the preferred top
  folder (`MRI`, `Otros`, `Pili y Mili`, `biomaGUNE MJ`), then the shortest path. Every other copy was compared with it file by
  file (inner path → SHA-256): **3,103 identical, 83 a subset, 38 divergent**.
- **The 38 divergent copies are 3 studies.** `m175` and `m178` of `0118` (2021-09-02) each sit in `respiracion\expiración\` and
  `respiracion\inspiracion\`: the same acquisitions (every exam's `acqp` and every k-space file identical in both copies)
  reconstructed twice, with different `2dseq` and DICOM (§3). And exam 4 of `jrc200305_m34_flow` (2020-03-05) has a **different `rawdata.job1`** in its two copies, which
  should not happen; its DICOM is identical. No two exam keys share `acqp` bytes, so no study was renamed between copies.

### 2.2 How production's `recon<idx>_frame<NN>.dcm` relate to the scanner's `MRIm<NN>.dcm`

- **Renamed verbatim, not rewritten.** The ingest (`tools\ingest_raw.py`, copy strategy `mri_paravision_v2`) copies
  `pdata\<idx>\dicom\MRIm<NN>.dcm` with `shutil.copyfile` to `<ACQ-ID>.data\recon<idx>_frame<NN>.dcm` (`NN` zero-padded to 2,
  `paravision_metadata._plan_dcm_target`). Measured: **3,618 exams match file for file under that mapping**, across three
  ingests (the June scanner load: 3,343 animal-first + 202 project-first; the 2021 `1019` recovery from `K:`: 73), and **9
  production files re-hashed from `J:\gjesus3-data\raw\`** (3 per ingest) equal the drive's manifest hash.
- **Same name, different bytes = a later re-export, not a different scan.** For 192 exams (11 studies: `0320` Feb–Mar 2022,
  `0619` May 2022, `0522` Nov 2022 and Jul 2024) production's file of the same name has other bytes. **All 4,342 such pairs were
  opened: 4,341 have identical pixel data and differ only in `InstanceCreationDate`/`InstanceCreationTime`** (for example the
  drive's copy was exported on 2022-02-16, production's on 2022-02-22). The remaining pair is the drive's zero-byte
  `MRIm7.dcm`. So a SHA-256 mismatch on MRI DICOM does **not** mean the scan is missing (`a1\dicom_relation_sample.csv`).
- Dicomifier-generated DICOM (the `*_regen` ingests, `pending_dicom_regen.csv` `regenerated`) cannot match any drive file.

### 2.3 Matching by name, by session, by bytes

| Match | Exams | Notes |
|---|---:|---|
| `original_name` = `<study>/<exam>` (or X1's `<study>__<exam>`) | **3,965** | every exam production holds |
| `session_id` + exam number, when the name did not match | 0 | no study folder was renamed in production |
| SHA-256 of the exam's DICOM, when neither matched | 0 | |

**No disagreement changes a match.** Every byte match points at the same acquisition as the name. The 10 disagreements listed
(`a1\mri_disagreements.csv`) are production **session ids that are not unique**: `jrc221115_m7_0522` is also the session id of
the next day's flow study (`20221116_092859_jrc221115_m7_0522_flow`, the console id typed a day late), and
`jrc241009_m21_1123` also belongs to a second study folder of that day whose placeholder row is dated by its ingest day
(`ACQ-20260614-MRI-003`, blank acquisition time). Session is a fallback, never a key. Retired acquisitions: no MRI exam on the
drive matches one by name.

### 2.4 Classes

| Class | Exams | Studies | Meaning |
|---|---:|---:|---|
| **(a)** in production, byte-identical | **3,618** | 205 | the drive's DICOM and the production acquisition's files are the same set, byte for byte |
| **(b)** in production, other form | **347** | 37 | **191** re-exported (identical pixels, §2.2) + **1** of those with the zero-byte file; **145** the drive copy has no DICOM, production has DICOM made by Dicomifier at ingest (107, `*_regen`), by stream B's convert-first (37, the `1019` MRS sessions of 2021) or from the scanner (1); **10** production holds an empty placeholder (8 `no-source`, 2 `WOBBLE`) and the drive cannot fill them: none has a `2dseq` (3 have k-space only, one of those zero bytes) |
| **(c)** not in production, native DICOM | **3,132** | 179 | the scanner's own export is on the drive. In 45 of them (the flow studies of `m37`, `m39`, `m40`, `m41`, 2020-03, and 2 more) a reconstruction exists as `2dseq` only: an ingest stores the DICOM ones, and the rest would need a conversion the convert-first tool does not do (it converts only exams with no DICOM at all) |
| **(d)** not in production, convertible | **177** | 11 | no DICOM, a `2dseq`, an image method: `convert_staged_exams.py` (Dicomifier). Their `2dseq` total 0.25 GB. Not run here (§8) |
| **(e)** not in production, not convertible | **71** | 22 | 29 spectroscopy (21 PRESS, 8 STEAM); the 21 of them that carry k-space data are **already in the drives 1+2 holding folder**, byte for byte (stream B's not-registered `1019` MRS exams). 3 k-space but no reconstruction; 39 never acquired (no k-space, no `2dseq`) |
| **(f)** not an exam | — | — | 217 folders named after a study with no exam in them (9.1 GB distinct: `.mhd/.raw` 7,589 files, NIfTI 2,988), and 9,018 non-ParaVision files inside study folders (9.5 GB). Derived; A2's |

Per study: 195 studies are entirely (a); 37 hold some (b) (18 no DICOM on the drive, 8 of which are the `1019` MRS sessions that
also hold (e); 10 re-exports; 8 with an empty placeholder; 1 mixed); 190 have nothing in production. Files: `a1\mri_exams.csv` (one row per
exam: class, the three matches, recon sets, method, scan name, ACQ time, station), `a1\mri_studies.csv`, `a1\mri_exam_copies.csv`.

### 2.5 The hub's 308 / 331, re-derived

| | Hub, 2026-09-30 | **Hub's method, today** |
|---|---:|---:|
| Production MRI study names | 984 | **1,113** |
| Study-shaped names on the drive | 639 | 639 (355 in more than one place) |
| … in production by name | 308 (156.9 GiB) | **353** (158.6 GiB) |
| … not in production | 331 (188.0 GiB) | **286** (186.4 GiB) |

**What the 639 names are:** 422 real ParaVision studies (232 in production, 190 not) and **217 folders named after a study
that hold no exam** (121 of them named after a study production holds, 96 not). The hub's unit was "a path segment shaped
`YYYYMMDD_HHMMSS_…`", which also catches `Splits\<study>\`, `Segmentaciones…\<study>\` and `NIFTI` export folders. `Otros\`
holds no exam folder: its 118 "Bruker studies" are segmentation and volume folders named after a study (for 19 of them the
study's scans sit elsewhere on the drive; 99 are named after studies the drive does not hold).

**The hub's own 331 rows today:** 190 real studies still not in production; 8 real studies ingested since (the `1019` MRS
sessions, stream B `dicom_B06`); 37 derived folders whose source study was ingested since (stream B `B02`/`B03`/`B04b`); 96
derived folders whose name is not in production. `a1\study_names.csv` has every name, its kind and its locations.

### 2.6 What is missing: by year, protocol, initials, regex, researcher, project

198 studies with any exam not in production (190 + the 8 MRS sessions): **3,380 exams; 187.5 GB of source (all copies,
SHA-256-dedup); 5.08 GB of native DICOM**. Projects follow §3 of the handoff: the claim is the nearest folder above the study
(`MRI\Proyecto 0619\…`), checked with the animal in the study name against the facility DB (`a1\mri_missing_studies.csv`).

| Protocol (verdict) | Year | Studies | Exams | (c) | (d) | (e) | GB source | GB DICOM | Proposed project |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `0619` | 2020 | 25 | 464 | 393 | 62 | 9 | 14.4 | 0.68 | `AE-biomaGUNE-0619` = `PROJ-0004` (active) |
| `0619` | 2021 | 60 | 1,080 | 971 | 107 | 2 | 60.1 | 1.51 | 〃 |
| `0619` | 2022 | 6 | 87 | 87 | 0 | 0 | 3.7 | 0.14 | 〃 (the 6 of N6, R3) |
| `1019` | 2020 | 61 | 1,031 | 1,012 | 8 | 11 | 42.7 | 1.93 | `AE-biomaGUNE-1019` = `PROJ-0006` (active; R7) |
| `1019` | 2021 | 8 | 29 | 0 | 0 | 29 | 0.0 | 0 | the MRS exams: nothing to register |
| `0118` | 2019 / 2020 / 2021 | 7 / 19 / 2 | 141 / 348 / 37 | 506 in all | 0 | 20 | 48.8 | 0.60 | R2 |
| `0320` | 2022 | 7 | 110 | 110 | 0 | 0 | 16.7 | 0.17 | `AE-biomaGUNE-0320` = `PROJ-0007` (active) |
| `1116` (decided by the DB) | 2019 | 1 | 20 | 20 | 0 | 0 | 0.1 | 0.01 | `AE-biomaGUNE-1116` = `PROJ-0062` |
| `0522` | 2024 | 1 | 20 | 20 | 0 | 0 | 0.7 | 0.03 | `AE-biomaGUNE-0522` = `PROJ-0011` (`m93`, R3) |
| **C**: claim contradicted | 2019 | 1 | 13 | 13 | 0 | 0 | 0.0 | 0.01 | blank (`jrc191015_m174_flow`, below) |
| **All** | | **198** | **3,380** | **3,132** | **177** | **71** | **187.5** | **5.08** | |

- **By year:** 2019: 9 studies / 174 exams; 2020: 105 / 1,843; 2021: 70 / 1,146; 2022: 13 / 197; 2024: 1 / 20. The June 2026
  scanner load reached back only to 2022-01-10 (the scanner's retention), which is why 2019–2021 is the bulk.
- **Production regexes:** 141 studies (2,449 exams) parse with the animal-first regex; **57 (931 exams) parse with neither**
  (`r157_2DG`, `m174_flow`, `191_0619`, `m175_ermal`, `m50MBmrs`, …): each needs a scoped config, as for G1 and stream B.
- **Console initials:** `jrc` (the PI's account, used by the whole group) on 197 studies, `JRC` on 1. **Researcher named in the
  path:** "MJ" 40 studies (699 exams), "Lucía" 24 (433), Ermal 2 (37, in the study name), none 132.
- **Scanner:** 7T (`Biospec 70/30`) 172 studies / 3,084 exams; **11.7T (`BIOSPEC 500`) 26 / 296**: `0320` Usp11 KO 2022-03-03/04
  (7), `0619` 2-DG females in hypoxia 2021-09-27/28 (10), `1116` flow 2019-11-07 (1), the `1019` MRS sessions (8).
- **Facility DB:** 187 CONFIRMED (183 with an MRI logged within 3 days, 4 with another procedure that week); 9 CLAIM-KEPT
  (animal in the protocol, nothing logged within 3 days: kept on the folder's claim, as in drives review §4); 1 CONFIRMED-NAME
  (`JRC191107_1116_m179_flow` sits in a `0619` folder, its name says `1116`, and the DB logs its MRI under `1116` that day);
  **1 C**: `20191015_153156_jrc191015_m174_flow_1_1` sits in the same `0619` folder, but animal 174 of `0619` was born on
  2021-07-29. Evidence only, not a verdict: animal 174 of `1116` logs an MRI on 2019-10-16.
- **Not checked against the DB: none.** No terminal procedure is logged before any scan.

## 3. Protocol `0118` (`MRI\Proyecto 0118 (Ratas hipoxia)`)

**28 studies, 526 exams; 48.9 GB distinct (45.6 GiB; the hub: 46.14); 0.60 GB of DICOM.** All on the 7T, ParaVision 6.0.1.
506 exams carry native DICOM (c); 18 were never acquired and 2 have k-space but no reconstruction (e). None is in production.
The study names carry `2DG` in the code slot, which is a treatment, not the protocol (handoff §3): the project comes from the
folder, and the DB confirms it.

| Date | Animals (study name) | Studies | Exams (c / e) | Methods | Facility DB |
|---|---|---:|---:|---|---|
| 2019-09-09/10/11 | `r111`–`r121` (7 rats) | 7 | 141 (140 / 1) | `IgUTE` (lung UTE), `FcFLASH`, `FLOWMAP` | rats of `0118`, MRI logged on each scan day; perfusion, lavage or organ sampling the same day or up to 3 days later |
| 2020-06-08/10/12/19 | `r153`–`r173`, `m152` (19) | 19 | 348 (329 / 19) | `IgFLASH` cines, `FcFLASH` | rats of `0118`, "MRI 7T" logged on the scan day (`m152`: a rat, nothing logged; its 2 exams were never acquired); `r163`/`r164` also log PET on 06-16/18 |
| 2021-09-02 | `m175`, `m178` (Ermal) | 2 | 37 (37 / 0) | `IgFLASH` cines | rats of `0118` (despite the `m`), MRI 7T + PET logged 09-01/02 |

Per study and per exam: `a1\p0118_studies.csv`, `a1\p0118_exams.csv`.

**Against `K:\gjesus\MRI\Proyecto 0118`** (read-only: listed, every file of the two shared studies SHA-256-hashed, and
every exam's `acqp` of the others): K: holds Ermal's 8 sessions of 2021-09-01/02 (`m175`–`m182`) and a `Splits` folder.

| K: study | On the drive? | By SHA-256 |
|---|---|---|
| `20210902_082356_jrc210902_m175_ermal_1_1` | yes, twice | the `inspiracion` copy holds **all 1,412 K: files, byte-identical** (+63 `NIFTI\` exports); the `expiración` copy shares 490, differs in 628 and lacks 294 (a different reconstruction: its exam 10 has recons 1/3/4, K:'s has 1/3/4/5) |
| `20210902_115741_jrc210902_m178_ermal_1_1` | yes, twice | the `expiración` copy holds **all 1,411 K: files, byte-identical** (+64); the `inspiracion` copy differs in 631 |
| `m176`, `m177` (09-02), `m179`–`m182` (09-01) | no | none of their `acqp` is on the drive: not here under another name |

So: **the 26 rat studies of 2019–2020 are not on `K:`, not in production, and older than what the scanner keeps** (the
platform's archive may hold them); **Ermal's 2021 sessions are complete on `K:`** and two of them are here, each in two
reconstructions. Also on the drive, as segmentation folders only (no scan; A3's): four more rats of the same series
(`r115`, `r116`, `r117`, `r119`, 2019-09-10/11). The DB has all four in `0118` with an MRI on that day; their scans are
neither on this drive nor in production (`a1\p0118_segmentation_only.csv`).

## 4. PET and PET/CT

**What the files are.** `PET\` (1,099 files, 24.9 GB) holds **Molecubes reconstructions** as DICOM (`<YYYYMMDDhhmmss>_<PET|CT>_
<OSEM|ISRA>_<n>[_frame…_iter…].dcm`; headers: `Molecubes NV`, `X-CUBE` for CT, `Beta-CUBE` for PET), each animal folder with the
Molecubes `reconparams.txt` and `protocol.txt` (150 + 147); **PMOD** derived files (49 DICOM exports such as `corregPETCT`,
`SUV 187`, `matrizcoreg`, and 38 `.voi`); 245 NIfTI volumes (12.2 GB, SUV maps and similar); Amira files; spreadsheets and
`.mat`. **No list-mode data.** Outside `PET\`: 429 standalone DICOMs in `biomaGUNE MJ\…\Raw data\PET` and 190 in
`Pili y Mili\…\PET` (reconstructions and PMOD exports). Six files are Molecubes reconstructions saved under another name
(`CT.dcm.dcm`, `PET.dcm.dcm` of `0619` animal 160, three copies of two files); they were recognised by their header.

**Coverage**, per distinct reconstruction (909 files = 492 distinct; `a1\pet_files.csv`): by SHA-256, by name (production
`original_name` `<ts>_<MOD>_<ALGO>_<n>`), by time (`acquisition_datetime` = the timestamp; also checked at ±3 h for time
zones), and against the `S:\gnuclear` snapshot (`J:\gjesus3-data\staging\ni_gnuclear_20260812\_manifest.jsonl`). **No
reconstruction matches production by name or time with different bytes**: there are no re-saves on the NI side.

| | Distinct | GB | Where |
|---|---:|---:|---|
| **In production** (bytes) | **290** | 11.5 | `PET\0522` (all), `PET\FDG-ratonesfumadores` (all: in `PROJ-0057` = `AE-biomaGUNE-1122`, from the `S:\gnuclear` pull), and the 2022–2024 `0522`, `0424`, `1123`, `1422` sessions in `biomaGUNE MJ\`/`Pili y Mili\` |
| **Only in the `S:\gnuclear` snapshot** | **100** | 3.2 | `PET\0619\Dieta cetogenica` and `Dieta alta en carbohidratos` (2021-10-19/20, 2022-01-25), `PET\0619\BrEt PAH` (2022-05-18/24), `PET\0320\CAV1 Enero 2022` = `PET\CAV1 Enero 2022` (2022-02-17), `1019` Procedimiento 3 (2022-09-27), `1123` gated CT (2024-10-09) |
| **Nowhere else** | **102** | 4.82 | `PET\0619\0619 2DG` males 2021-03-22 (32) and females 2021-07-27/28 and 2021-09-28 (32, with animal 160's two renamed files); `PET\0320\14…28` (2021-06-01, 14); `Pili y Mili\Proyecto 1422 Metformin`: Flurpiridaz test 2023-10-05 (4, 1.34 GB) and `MJ-FDG` 2023-11-28 (20 CT; the DB logs PET that day too, but no PET file is on the drive) |

- **The hub was right that `0619` and `0320` PET are absent**: production holds no PET/CT for either protocol.
- **Claims, checked in the facility DB** (`a1\pet_claims.csv`): **201 of 202 CONFIRMED**: the animal of the folder (`PET\0320\14\`
  → animal 14) is in the claimed protocol and logs a PET (`PET CUBES-1`/`-2`) that day. The other is `Dieta cetogenica\173 FALTA`
  (protocol valid, folder name not an animal number). So **`CAV1 Enero 2022` is `0320`** (the copy under `PET\0320\` says so,
  and animals 29–32 and 44–47 log PET on 2022-02-17); `FDG-ratonesfumadores` is already in `PROJ-0057` (`1122`) in production.
- **Why the 100 were held back** (`a1\pet_heldback_reanalysis.csv`): re-running the pull's own `ni_gnuclear_discover.analyse()`
  (a pure function of the path) on their snapshot paths gives project `(none)`, flag `no-project`, for all 100, **although every
  one of those paths carries a DB-valid code** (`…/IAZ_MJ/0619/Dieta cetogenica/174/…`: `0619` 58, `1019` 16, `0320` 15, `1123`
  11). `recover_project()` walks up the path only when the parser returned a code that fails validation, not when it returned
  none.

## 5. Microscopy (`.czi`, `.lif`)

6,993 files (6,967 `.czi`, 17 `.lif`, 9 `.lifext`), 950.4 GB; **6,094 distinct** (855.3 GB). Every header read; 0 unreadable
`.czi` (1 has no instrument metadata). `a1\microscopy_files.csv` has one row per file.

| Distinct files | Count | Meaning |
|---|---:|---|
| byte-identical to production | **717** | |
| **re-save of a production acquisition** | **119** | same instrument, same `AcquisitionDateAndTime` to the second, same file name, other bytes: `biomaGUNE MJ\…\Proyecto 1422` 61, `Male Diets` 30, `PR_1019-2_MJS-IAZ` 13, `Machos viejos-1019-3` 8, `Machos vs Hembras` 5, `Female Diets` 2 |
| same instrument and second, other name | 1 | counted as new |
| not in production in any form | **5,257** | |

**Instrument, by device serial** (the catalog's own fingerprint, `tools\reference\microscopy_instruments.yaml`), new files:

| Instrument | Files | GB | Acquired | Where |
|---|---:|---:|---|---|
| **Cell Observer** (`CELL`: no serial, stand key `Inverted`) | **5,115** | **642.8** | 2021-06 → 2025-03 | `Microscopio- MJesus Sanchez 2023\` (Male Diets 834, Female Diets 1,041, Machos vs Hembras 1,584, Machos viejos-1019-3 418), `CELL OBS MARTA\` (844), `biomaGUNE MJ\…\Raw data` (327), `Pili y Mili\Proyecto 1019…\Procedimiento 2` (67) |
| **Axioscan 7, serial 4661000340** (not `ZWSI`'s 4661000718; stand keys `Pollux`, `UprightFixedStage`; ZEN 3.7) | **116** | **153.9** | 2024-10-24 → 2025-02-19 | `Microscopio biodonostia\` (`escaner`, `BIOMAGUNE`, `0522 Biodonostia`: 54), `Histologia_ratones_viejos\` (HE, SR, Tricrómico: 42), `biomaGUNE MJ\…\Proyecto 1422` (20) |
| **Leica TCS SP8, serial 8100000207** (stand `DM6000B-CS`) | 17 `.lif` + 9 `.lifext` | 6.8 | (LIF headers carry no plain date) | `Pili y Mili\Proyecto 1121 London\Experimentos\Histologia\…` (`Confocal`, `ki67`, `Training confocal`) |
| no instrument metadata | 1 | 0.0 | | `Machos vs Hembras` |

- **gjesus3 knows neither the Leica nor this Axioscan 7.** The registry's microscopes are `CELL`, `LSM9`, `ZWSI` and `XMIC` (the
  external Charité Axio Imager). The folder names suggest Biodonostia for the Axioscan and London (protocol `1121`) for the
  Leica; that is a folder name, not evidence (R6).
- **Derivative signals** (no hardware/experiment block = an export, a `scale`/`export`/`Untitled`/`crop` name, < 5 MB): only 8 of
  the files not byte-identical to production show one. **Same-timestamp groups:** 266 groups of 2+ distinct files share an instrument and acquisition second
  (541 files, 536 not in production): heart and lung of one animal saved from one acquisition (`R286_PR_heart.czi` /
  `R286_PR_lung.czi`), scene splits, stitching. These need the drives' same-timestamp pixel check before ingest (R5).
- **Project claims by path** (nearest folder or file-name chunk with a DB-valid code; the animal `ID12`/`m12` looked up in it):
  of the 5,258 new files, 3,368 have their animal in the claimed protocol, 263 claim a valid protocol with no animal id, **139
  name an animal the claimed protocol does not have** (most are file-name claims that disagree with their folder, e.g.
  `ID190-1019-Lung-HE-20X-1.czi` inside `3-KD female 0619\`, where `0619` holds animal 190), and **1,488 claim nothing**
  (`Machos vs Hembras\F4-80_20x-Female and Male`, `231114_TOM20_MTCO1_20x`, `231201_a-sma 8oHDG`, …). Under the rules these are
  confirmed, A-candidates and C; the full A/B/C call is A2's (`tools\drive_staging\project_claims.py` logic), not made here.
- **For the 748 drive files byte-identical to production** (717 distinct), production's project and the drive's folder claim
  agree for 616; 60 sit in a drive folder claiming `0619` while production's row has a **blank** project, and 6 sit in a
  `0522` folder while production says `0619`: evidence for the 2b mapping (STATUS H1), not a correction.

## 6. Other DICOM

The drive holds 246,480 `.dcm` (51.6 GB) and 35,215 DICOM files without an extension (9.0 GB):

| What | Files | GB | In production |
|---|---:|---:|---|
| `MRIm<NN>.dcm` inside Bruker exam folders | 245,553 | 14.9 | §2 (116,020 byte-identical) |
| Molecubes PET/CT reconstructions (standalone) | 909 | 36.0 | §4 |
| PMOD exports (18 `.dcm`, 31 extension-less; `Manufacturer` "PMOD Technologies") | 49 | 2.1 | no: derived, A2's |
| **Pig cardiac MRI** (extension-less), `Otros\Segmentaciones ITK SNAP\Segmentaciones Arteria Pulmonar cerdos\Imágenes\` | **35,184** | **7.6** | no |

The pig series are **Philips Achieva, institution CNIC, 2014**: 27 study folders (one `DICOMDIR` each), body part HEART, series
described `RL` (34,086) or `AP` (1,046). It is **not a gjesus3 instrument**. The patient name, id and birth-date elements are populated (the
folder calls the subjects pigs; species is not recorded). **Counted only; no identifier is written in any A1 output**
(`a1\noext_dicom_probe.csv` keeps presence flags). They are the source images of A3's pig pulmonary-artery segmentations.

No clinical DICOM was found anywhere else on the drive.

## 7. The bottom line

Genuinely new raw imaging: not in production `/raw/` in any form (an MRI exam in production as a re-export or as Dicomifier
DICOM is not new). Each distinct file / exam once. Long form: `a1\bottom_line.csv`.

| Domain | Class | Project (claim) | Units | GB on the drive | GB to `/raw/` | What ingesting it needs |
|---|---|---|---:|---:|---:|---|
| MRI | (c) native DICOM | `0619` (`PROJ-0004`) | 1,451 exams | 72.5 | 2.3 | scoped configs (DB-confirmed claims), 11.7T model for 137 |
| MRI | (c) | `0118` (R2) | 506 | 48.8 | 0.6 | project decision first |
| MRI | (c) | `1019` (`PROJ-0006`) | 1,012 | 42.5 | 1.9 | R7 |
| MRI | (c) | `0320` (`PROJ-0007`) | 110 | 16.7 | 0.2 | 11.7T model |
| MRI | (c) | `0522`, `1116` | 20 + 20 | 0.8 | 0.04 | 11.7T model for `1116`'s 20 |
| MRI | (c) | blank (C) | 13 | 0.0 | 0.01 | stays blank unless the researcher says otherwise |
| MRI | (d) convertible | `0619` 169, `1019` 8 | 177 | 6.1 | ≈ 0.25 | convert first (WSL, Dicomifier), then ingest |
| MRI | (e) | `0118` 20, `1019` 40, `0619` 11 | 71 | 0.1 | 0 | nothing to register; 21 already held as other data |
| PET/CT | new | `0619` 64, `1422` 24, `0320` 14 | 102 recons | 4.82 | 4.82 | NI ingest from the staged copy; codes DB-confirmed; 2 renamed files need their name rebuilt from the header |
| PET/CT | `S:\gnuclear` snapshot only | `0619` 58, `1019` 16, `0320` 15, `1123` 11 | 100 recons | 3.2 | 3.2 | ingest from the snapshot; codes from its own paths |
| Microscopy | Cell Observer | `0619` 1,208, `0522` 1,234, `1019` 596, `0424` 492, `1123` 75, `1422` 72, none 1,438 | 5,115 files | 642.8 | 642.8 | same-timestamp pixel check, then claims (A2) |
| Microscopy | Axioscan 7 #4661000340 | `0424` 16, `0522` 25, `1422` 20, `1019` 6, none 49 | 116 | 153.9 | 153.9 | external: X-code decision (R6) |
| Microscopy | Leica TCS SP8 #8100000207 | `1121` (`PROJ-0009`, closed) | 26 | 6.8 | 6.8 | external: X-code decision (R6) |
| Other DICOM | pig MRI, Philips Achieva, CNIC | none | 35,184 files | 7.6 | 7.6 | external; A3 |

**By year** — MRI exams: 2019 174, 2020 1,843, 2021 1,146, 2022 197, 2024 20. PET/CT: 2021 95, 2022 72, 2023 24, 2024 11.
Microscopy files: 2021 95, 2022 443, 2023 3,617, 2024 393, 2025 683, unknown 27.

## 8. What A1 could not establish, and traps for the next session

**Not established (and why):**
- **Whether the 2019–2021 MRI also sits in the MRI platform's archive.** Only the platform manager can say; this drive is the
  copy we hold.
- **Whether the 177 (d) exams convert.** `convert_staged_exams.py` writes Dicomifier output *into* the staged exam, which the
  read-only rule forbids; it runs in WSL.
- **Which reconstruction of `m175`/`m178` is the one to register** (expiration vs inspiration). Only Ermal or M. Jesús can say;
  R2 proposes the K:-identical one.
- **Where the Axioscan 7 #4661000340 and the Leica TCS SP8 #8100000207 are.** Only folder names point anywhere.
- **The project of 1,488 microscopy files that claim nothing and of 139 whose animal is not in the claimed protocol.** That is
  the claims analysis (A2), not a guess here.
- **Whether the 266 same-timestamp microscopy groups are scene splits, stitched copies or separate acquisitions.** Needs the
  tile-level pixel check (`r4_groups.py`), which was not run.
- **The species of the CNIC series.** The headers do not record it; the folder says pigs.

**Traps:**
1. **An MRI DICOM hash mismatch is not a missing scan.** Production's June scanner load holds later re-exports for 192 exams:
   same pixels, other `InstanceCreationDate/Time`. Decide MRI coverage by exam, never by file hash alone.
2. **The hub's "study" is any folder named like one.** 217 of its 639 hold no exam; `Otros\` holds no exam at all.
3. **"GB" in the hub's brief is GiB** (`Microscopio` 872.5 "GB" = 936.8 GB).
4. **A study-name prefix is not a species.** `0118`'s `m152`, `m175`, `m178` are rats in the facility DB.
5. **Production `session_id` repeats** (two cases here). Match exams by `original_name`; use the session only as a fallback.
6. **`ni_gnuclear_discover.analyse()` misses codes higher up the path when its parser finds none** (§4): 100 reconstructions
   here, and possibly more of the 673 held back.
7. **Divergent copies:** `m175`/`m178` (two reconstructions) and `jrc200305_m34_flow/4` (`rawdata.job1` differs between copies).
   The canonical-copy rule picks one; for these, check before ingesting.
8. **Zero-byte raw files:** 5 (§1). Both exams are already in production, so nothing to ingest is affected; but a byte
   comparison must not read an empty file as a match or as a new version.
9. **The 21 spectroscopy exams of `1019` (2021) are already in `staging\historical_drives_unassigned\`** byte for byte (stream
   B's not-registered exams). Do not place them twice.
10. **When a Python one-liner needs backslashes, write a script file** (here-documents mangled them in this session).

## 9. Reproducing every number

All read-only; run from `tools\drive_staging\drive3\` with `PYTHONDONTWRITEBYTECODE=1` (the scripts also set it), in order.
Every script writes only under `D:\projects\gjesus3\drive3_analysis\a1\` (`a1_common.out_path()` refuses anything else).

| Script | Reads | Writes (in `a1\`) | Time |
|---|---|---|---|
| `a1_00_snapshot.py` | the live registries, drives 1+2 indexes/holding manifest, the hub's duplicates list | `_inputs\` + `SNAPSHOT.txt` | seconds |
| `a1_05_probe_noext.py` | 132 bytes of 35,244 extension-less files | `noext_dicom_probe.csv` | 8 min |
| `a1_10_files.py` | manifest, production index, `_inputs\`, the drives 1+2 manifests and archive-member list (`J:\gjesus3-data\staging\historical_drives_records\`) | `a1_files.csv.gz` (one row per drive file), `coverage_by_*.csv`, `hub_class_crosswalk.csv` | 40 s |
| `a1_20_mri_inventory.py` | the file table | `mri_exam_copies.csv` | seconds |
| `a1_21_mri_headers.py` | `acqp`, `method`, `subject` | `mri_exam_headers.csv` | 3.5 min |
| `a1_22_mri_match.py` | registry snapshot, production index | `mri_exams.csv`, `mri_studies.csv`, `mri_disagreements.csv`, `mri_match_summary.txt` | seconds |
| `a1_23_dicom_relation.py` | 9 production DICOMs, 4,342 drive/production pairs | `dicom_relation_sample.csv`, `dicom_relation_summary.txt` | 45 s |
| `a1_24_mri_projects.py` | facility DB (`SELECT`) | `mri_missing_studies.csv`, `_cache\db_lookups.json` | seconds |
| `a1_25_study_names.py` | the hub's `mri_missing_studies.csv`, D3's 57 | `study_names.csv`, `study_names_summary.txt` | seconds |
| `a1_30_0118.py` | `K:\gjesus\MRI\Proyecto 0118` (listing; 2 studies hashed, 1.6 GB), facility DB | `p0118_*.csv` (incl. `p0118_segmentation_only.csv`), `p0118_summary.txt` | 1–2 min |
| `a1_40_pet.py` | 958 DICOM headers, the `S:\gnuclear` snapshot manifest | `pet_files.csv`, `pet_summary.txt` | 4 min |
| `a1_41_gnuclear_heldback.py` | facility DB (protocol list) | `pet_heldback_reanalysis.csv` | seconds |
| `a1_42_pet_claims.py` | facility DB | `pet_claims.csv` | seconds |
| `a1_50_microscopy.py` | `.czi` metadata segments, `.lif` headers, facility DB | `microscopy_files.csv`, `microscopy_summary.txt` | 5 min (first run) |
| `a1_70_bottom_line.py` | the above | `bottom_line.csv`, `bottom_line_summary.txt` | seconds |
| `a1_80_report_tables.py` | the above | `report_tables.txt` (the side checks and every table here) | seconds |

`a1\_cache\` holds regenerable pickles; delete it to recompute from scratch.
