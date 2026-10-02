# Historical drives: the MRI, PET/CT and other DICOM data (stream B review)

**Status:** 🔶 **Phase 1 (read-only) complete, proposal below; nothing written to production.**
**Branch:** `feat/drives-dicom` · **Date:** 2026-10-02 · **Plan:** [`historical_drives_closeout_plan.md`](historical_drives_closeout_plan.md) Step 5 item 4
**Evidence (regenerable, not backed up):** `D:\projects\gjesus3\staging\_analysis\drives-dicom\`

| File | What it is |
|---|---|
| `inventory.csv` | **One row per exam** (2,866 rows): ParaVision exam, Molecubes reconstruction, or DICOM-only exam folder. It has the columns the handoff asks for, plus `group`, `canonical` / `duplicate_of` (within-drive copies), `disposition`, `proposed_project` and `question`. |
| `imaging_roots.csv` | The 31 path prefixes stream B owns (v1, sent to A 2026-10-02). |
| `nonraw_for_A.csv` | 15,856 files / 42.4 GB of derived material under those roots, each with the project its claim carries (blank where no claim was CONFIRMED). |
| `nmr_list.csv` | 671 TopSpin NMR experiments (1.15 GB). Not imaging: listed, not ingested. |
| `nested_listings_drive_zuri.csv` | The member listings of the 8 nested zips in `Drive zuri 170823.zip`, which the catalog never opened (routed to A by the coordinator). |

## Summary (10 lines)

1. **2,574 ParaVision exams in 190 studies, 291 Molecubes DICOM files, and 671 NMR experiments** sit under the scope. All other imaging-like files (NIfTI, MHD splits, segmentations) are derivatives, and they go to A.
2. **Already in production: 663 MRI exams (605 distinct) and 261 NI files.** These are Laura's `0721`/`1321` Bruker MRI, Claudia's 2024 3D set, `1519` *Basal* 2022, and every Laura/Itziar/Marina Molecubes CT. **Every match is by identity:** study folder, exam number and subject, then the exam datetime to the ms (§2).
3. **New and only here: 1,306 distinct MRI exams of five lab protocols** (`1519`, `0619`, `0420`, `1019`), 64 GB of source, all claims **confirmed by facility-DB procedure dates** (§4).
4. **⚠️ 526 of them are post-horizon `1519` exams that the 2026-06 scanner pull silently dropped** (STATUS D3). The token `_week1` … `_week4` in the study name matches neither ingest regex, so they were skipped with no error. The same gap took the 2022–23 phantom sessions and nine May 2023 `0721` sessions (§5).
5. **`1519` (`PROJ-0008`) is closed.** Two of the five groups go there, so **reopening it is question Q1.**
6. **Peio's `1319`: 8 PET/CT reconstructions (4 animals, 2021-05-14).** None are in NI production or in the `S:\gnuclear` snapshot. Create `AE-biomaGUNE-1319` (pre-approved) and ingest (needs Ryan's go).
7. **Needs Ryan:**
   - 133 phantom/collaboration exams (Q3);
   - 363 exams from an **external Bruker ICON in Madrid** (Q4);
   - 3 untagged 2019 PET/CT files (Q5);
   - 19 Molecubes FDK reconstructions that are in the `S:\gnuclear` snapshot but not in production (Q6).
8. **The 2020 `1519` rat study is mostly lost.** About 93 sessions survive only as derivatives; the raw exists on neither the drives nor production. One week (10 sessions) is here (§6).
9. **A code bug to fix before any 11.7T ingest:** `paravision_metadata._scanner_model` turns the station `BIOSPEC 500` into **"Bruker BioSpec 50T"**. Production has 0 such rows (all 11,208 MRI rows are 7T); ingest 11.7T exams with an explicit model (§7).
10. **Space:** the ingests store DICOMs only, so the expected `/raw/` growth is **~10–15 GB** for the 1,306 exams. Extracts needed on D: are ≤ 40 GB at a time.

---

## 1. What was looked at, and how

- **Units.** A ParaVision exam is a folder holding `acqp` or `method`, and its study is the parent. A TopSpin experiment holds `acqus` and no `acqp`. A Molecubes reconstruction is a `<ts14>_<MOD>_<ALGO>_<n>.dcm` file. Everything else under the roots is either study-level ParaVision metadata (`subject`, `AdjResult`, `ResultState`) or a derivative.
- **Sources read, all read-only:**
  - loose files from the staged `files\` trees;
  - zip members through `zipfile`, without extracting;
  - the Haizpea `.7z` through a parameter-files-only 7z extract to `D:\projects\gjesus3\scratch_drives-dicom\`;
  - the nested `BrEt/OneDrive_1_29-1-2021.zip`, extracted whole to the same scratch folder (14.2 GB) so that it can be listed. **Both extracts are deleted when Phase 1 closes.**
- **Headers:**
  - **ParaVision:** `subject`, `acqp`, `method` and `pdata/1/visu_pars`, parsed with the repo's `ingest/jcampdx.py`; scanner model from `paravision_metadata._scanner_model`. 2,231 of 2,574 exams read, 0 errors. **Haizpea's 343 are pending the 7z extract:** their prod-match is by name, and their claims are DB-confirmed already.
  - **Molecubes:** `pydicom` headers of all 321 standalone DICOMs, 0 errors.
- **Production index:** registry copies taken 2026-10-02 (11,208 MRI rows, 1,640 NI rows), plus the `S:\gnuclear` snapshot manifest (`J:\gjesus3-data\staging\ni_gnuclear_20260812\_manifest.jsonl`) and `_analysis\catalog\production_hashes.csv`.
- **Facility DB:** a read-only `tools/animal_db.py` lookup of 88 `(protocol, animal, scan date)` claims, **88/88 found** (§4).

## 2. Already in production (no action)

| Group | Exams (distinct) | Production | Match |
|---|---:|---|---|
| **B01** Laura `0721` biodistribution Aug/Oct/Nov/Dec 2022, `1321`/`0219` Cursosurf Jun 2022, Claudia `0721` 2024-04-16, `1519` *Basal* Feb–Mar 2022 + 2 *Semana 1* sessions (m29, m30) | 663 (605) | `PROJ-0010`, `-0018`, `-0017`, `-0008` | 581 datetime-equal; **76 differ by ~2.6 s** (same study, exam and animal: the copy on the drive was re-reconstructed, which changes `VisuCreationDate`); 6 have no `visu_pars` on the drive copy, so are matched on study + exam + subject |
| **N01** Molecubes CT: Laura `1321` Aug/Oct 2023 and IPF controls, Itziar/Marina `1123` *Ferritas* Sep–Oct 2024 (loose **and** in `Ferritas 1.zip`) | 261 files (177) | `PROJ-0018`, `-0014`, `-0017` | filename stem == production `original_name`, **and** SHA-256 in production |

**The 58 + 84 extra rows are copies on the drives** (`Biodistribucion Noviembre22` exists in two folders; the CTs sit both under `1321_august_CT` and `CT\Agosto23`). Each cites its canonical copy in `duplicate_of`.

**Surprise:** the *Ferritas* CTs in Laura's folders are **`1123` animals**, scanned by itziar/marina (patient `1480_1123_<n>`). They are already in `PROJ-0014`, so nothing is lost. But the folder name would have put them in the wrong project.

## 3. Proposed dispositions

| Group | What | Distinct exams | Source GB | DICOM? | Disposition | Project |
|---|---|---:|---:|---|---|---|
| **B02** | `1519` Santander *Segunda tanda* weeks 1–4, 2022-03-10…30, rats 29–36, 7T | 526 (+34 `_bad` copy) | 20.2 | 520 | **ingest** | `AE-biomaGUNE-1519` (closed) → **Q1** |
| **B03** | `1519` post-surgery week 2, 2020-09-23/24, rats 14–26, 7T (incl. 1 DICOM-only exam) | 136 | 10.3 | all | **ingest** | `AE-biomaGUNE-1519` (closed) → **Q1** |
| **B04** | `0619` hypoxia + ethidium-bromide (*BrEt*), 2020-02-24 (11.7T) and 2020-03-03/04 (7T), mice 17–32 | 236 (+64 copies) | 20.1 | 232 | **ingest** | `AE-biomaGUNE-0619` (`PROJ-0004`, active) |
| **B05** | Haizpea `0420` sessions 2.1/2.2, 2021-06-10…12-20, rats 11–23, 7T | 343 | 13.5 | 338 | **ingest** | `AE-biomaGUNE-0420` (`PROJ-0012`, active) |
| **B06** | `1019` MRS, brain + liver, 2021-01-28…03-02, mice 50–58, **11.7T** | 66 | 0.3 | 0 (spectroscopy) | **ingest** | **Q2** |
| **B07** | Phantoms + nanoparticle collaborations (`prc`/`pr`/`jrc` phantom), 2022-10…2023-07, 7T (1 study 11.7T) | 133 (+11 copies) | 21.9 | 0 | **unclear** | **Q3** |
| **B08** | Claudia *Madrid 29-04-2024*: Bruker **ICON** (PV 6.0.1pl3_ICON), 4 mice, study "nanoparticulas" | 363 | 0.5 | 0 | **unclear** | **Q4** |
| **N02** | Molecubes `FDK` recons of Marina `1321` CTs, Aug 2023 | 18 (+1) | 2.2 | yes | **not a drives ingest** (in the `S:\gnuclear` snapshot) | **Q6** |
| **N03** | Peio `1319` liver PET + CT, 2021-05-14, animals 29–32 (operator irati) | 8 | 0.3 | yes | **ingest** | `AE-biomaGUNE-1319` (create, pre-approved) |
| **N04** | Ana B / Hugo "native heparin" PET + CT, 2019-02-13/15 (operator krishna), no protocol code | 3 | 0.2 | yes | **unclear** | **Q5** |
| NMR | TopSpin experiments (Chem Lab, NOVA-MRI, Peio's lactate assay, the hospital-clinic samples, Lydia, Amaia, Ana B, 1019 HR-MAS) | 671 | 1.1 | — | **not imaging**: listed | — |
| Non-raw | NIfTI exports, MHD *Splits*, *Segmentaciones*, figures, analysis, meshes | 15,856 files | 42.4 | — | **to A** (`nonraw_for_A.csv`) | per claim |

**Within-drive duplicates are resolved per exam**, not per folder:
- *BrEt* m22 has 18 exams in `BrEt\` but 15 in `BrEt\DICOM\`, so the union is kept.
- `…_m35_week3_1519_1_1_bad` has the same 34 exams with **identical acquisition and reconstruction times**. It is the same session, so the copy without `_bad` is canonical.

**Ingest mechanics (Phase 2, configs not yet written):**
- **Copy strategy:** `mri_paravision_v2`, which stores DICOMs only. `instrument_model` is set explicitly: `7T`, `11.7T`, or `NA`, never the template placeholder.
- **People:** `researcher`/`operator` `NA`, as in the 1019 recovery.
- **Exams with no DICOM** (B06 MRS, B07, B08, the four in B04/B05) go to the DICOM-regen worklist or Dicomifier in WSL. B06 is spectroscopy, so expect `not-applicable`.
- **Study names that don't parse** (B02, B03, B04, B06): each needs a **per-study `pattern` plus a scoped regex**, as in `mri_0522_m145_irene.yaml`. The shared regex is not relaxed.
- **Staging:** each study folder is staged **flattened by hard link on D:** (0 bytes), so that `original_name` is `<study>/<exam>`, the same shape as production. That also defuses the `staging_dir` trap.
- **Dedup rehearsal:** each batch is first dry-run with a known-ingested sibling (B01 `1519` *Basal*), to prove dedup skips it.

## 4. Claims checked in the facility DB (88 of 88 found)

The check confirms; it never overrules a file's own claim.

- **`0619`:**
  - 2020-02-24, mice 17/18/19/22: DB "MRI 11.7T" on the day, matching `ACQ_station` `BIOSPEC 500`.
  - 2020-03-03/04, mice 20/21/23–25/27–32: "MRI 7T", matching `Biospec 70/30`.
- **`1519`:**
  - 2020-09-23/24, rats 14–26: "MRI 7T" on the day (rat 20 the next day; its session started 20:31).
  - 2022-03-10/16/22/30: "MRI 7T" on the day.
  - **2022-03-15 (rats 29, 30) and 2022-03-23 (rats 33–36) have no MRI logged.** The study folders say week 2/week 3, and the scanner wrote the date. **Kept on the folder's own claim.**
- **`0420`:** all 21 sessions "MRI 7T" on the day.
- **`1019`:** all 8 MRS sessions "MRI 11.7T" on the day.
- **`1319`:** animals 29–32 "PET CUBES-1" on 2021-05-14 (and "MRI 11.7T" on 05-13, which is not on these drives).

## 5. The silent skip, measured (STATUS D3)

Applied to every study on the drives, the two production ingest regexes (`mri_jrc_animalfirst` / `mri_jrc_projfirst`) give:

| | Exams | In production |
|---|---:|---:|
| match animal-first | 957 | 614 |
| match project-first | 49 | 49 |
| **match neither** | **1,568** | **0** |

Every unmatched study is missing from production, whatever its date. Among them are **post-horizon** sessions, which the kenia pull must have seen and dropped:

- **B02** `jrc220310_m31_week1_1519` …: 526 exams (2022-03);
- **B07** phantoms `prc230302_phantom_LFM_…`: 133 exams (2022-10…2023-07);
- **nine May 2023 `0721` sessions**, `pr230515_m113_biod_0721` …, present here **only as NIfTI exports** (`LP+IONP\Biodistribucion-LP-IONP-Mayo23`, `PR-0721-Biod-May23.zip`). Their raw is not on the drives, **but at 2023 it is probably still on kenia.**

**This is direct evidence for D3(b):** the scanner pull lost real `1519` and `0721` animal data, not only phantoms. Kenia's retention horizon was 2022-01-10 in June 2026, and it moves forward. The March 2022 sessions may be ageing off the scanner now, which makes **the drive copy possibly the last copy of B02**.

## 6. Raw that is nowhere

`Cardiac MRI.zip` carries *Splits* and *Segmentaciones* for **~93 `1519` sessions of 2020**: baseline 2020-08-31…09-08, then post-surgery weeks 1–4 to 2020-10-08. The raw ParaVision is on the drives for **week 2 only (10 sessions, B03)**. The other ~83 have their raw neither here nor in production (pre-horizon). Unless they are on `K:\gjesus\MRI` or another researcher share, **only their derivatives survive.** Those derivatives go to A as non-raw for `1519`. Recorded, not chased: surveying `K:` is out of scope and it is in daily use.

## 7. Code finding: the "50T" scanner model

`tools/ingest/paravision_metadata.py::_scanner_model` reads the leading number of `ACQ_station` as field ×10. That holds for `Biospec 70/30` (7.0 T), but this scanner writes **`BIOSPEC 500`**, a 500 MHz ¹H frequency, which is 11.7 T. **The code turns it into "Bruker BioSpec 50T".** On the drives this is 64 exams of B04, all 66 of B06 and 13 of B07. Production is unaffected: all 11,208 MRI rows are `Bruker BioSpec 7T`, and **11.7T has never been ingested.**

**Proposed:** the ingest configs set `instrument_model` explicitly, so no code change is needed for this stream. A one-line fix goes to the BACKLOG: treat a station number ≥ 200 as MHz, or prefer the `PVM_FrqRef` path. It touches shared ingest code, so it is a separate, reviewed change.

## 7a. Phase 2: configs and dry runs (read-only, approved by the coordinator 2026-10-02)

**Configs:** `tools/configs/drives_2026-09/dicom/` (one per batch, plus a `*_sibling_dedup.yaml` per family, plus `cases_<config>.csv`).

- **Every MRI exam gets an explicit datetime.** The case table supplies `drv_acq_datetime`: `visu_pars.VisuCreationDate`, the value production uses, else the scanner-written `acqp.ACQ_time`. **Why:** B06's first dry run gave 8 exams with no `visu_pars` **today's** date (`ACQ-20261002-MRI-*`), the soft fallback the handoff warns about. With the table, `on_missing: error` stops a batch on any exam without a row.
- **Every dry run is bracketed by a size+mtime check of `registry_raw.csv`.** All so far: unchanged.

**One line per batch.** Format: expected / listed / skipped-with-reason · dedup rehearsal · IDs · project · model.

| Batch | Dry-run result |
|---|---|
| **N03** `1319` PET/CT | **8 / 8 / 0** · sibling `ACQ-20230808-CT-001` staged the same way: **skipped (already in registry)**, 0 listed · `ACQ-20210514-PET-*` ×4, `-CT-*` ×4 (the dry run previews `-001` for every case because it reserves nothing; a real run allocates `-001`…`-004`) · `AE-biomaGUNE-1319`, auto-created (pre-approved) · `Molecubes (PET/SPECT/CT)` · DB subject keys `29…32-AE-biomaGUNE-1319` |
| **B06** `1019` MRS | **66 / 58 / 8**. The 8 are never-acquired `2_Localized_shim` setup scans (no `ACQ_time`, no `fid`, empty `pdata`), listed in `excluded_dicom_B06_1019_mrs_2021.csv` · sibling: the shared MRI mechanism, proven by the B04/B05 siblings below · `ACQ-20210128…20210302-MRI-*`, **0 dated today** · blank project (Q2) · `Bruker BioSpec 11.7T` |
| **B04a** `0619` BrEt 11.7T | **67 / 67 / 0** · sibling: see next rows · `ACQ-20200224-MRI-*`, 0 dated today · `AE-biomaGUNE-0619` (`PROJ-0004`, active) · `Bruker BioSpec 11.7T` |
| **B04b** `0619` BrEt 7T | **169 / 165 / 4**: 2 never-acquired setup scans (`m27/3`, `m32/5`: 3 files, no data), and ⚠️ **2 real scans that the detector skips because the drive copy has no `acqp`**: `20200304_101934_jrc200304_m27_BE_1_1/4` (15 files) and `20200304_134107_jrc200304_m31_BE_1_1/4` (long-axis LV, 7 files). They have `2dseq` + DICOM, and this is their only copy (`excluded_dicom_B04b_0619_bret_7T.csv`). They need a one-off decision, as B03's DICOM-only exam does · `ACQ-20200303/04-MRI-*`, 0 dated today · `AE-biomaGUNE-0619` · `Bruker BioSpec 7T` |
| **B05a** `0420` s2.1 | **165 / 165 / 0** (the 9 `Splits/` derivative folders skipped as non-scan, as intended) · `ACQ-20210610/30-MRI-*`, 0 dated today · `AE-biomaGUNE-0420` (`PROJ-0012`, active) · `Bruker BioSpec 7T` |
| **B05b** `0420` s2.2 | **178 / 173 / 5**: the 5 are never-acquired setup scans (no `fid`, no `2dseq`, no `ACQ_time`), listed in `excluded_dicom_B05b_0420_haizpea_s22.csv`; the `Splits*/` derivative folders are skipped as non-scan · `ACQ-20211117/18, 20211220-MRI-*`, 0 dated today · `AE-biomaGUNE-0420` · `Bruker BioSpec 7T` |
| **Siblings** (MRI) | `dicom_B04_sibling_dedup` and `dicom_B05_sibling_dedup` (each batch family's own regex, pointed at production study `20220221_092531_jrc220221_m29_1519_1_1`, staged the same flat way): **0 listed, 18/18 skipped "already in registry"**. This proves that this staging gives `original_name` the production shape |
| B02 / B03 `1519` | configs written; staging waits on the coordinator (it would take my scratch past 50 GB) and on Q1 |

**Nested `BrEt/OneDrive_1_29-1-2021.zip` (14.2 GB): a byte-identical copy.** Its 4 studies / 67 exams are the same as `BrEt\` (4,269/4,269 common members CRC-32 equal; the only differences are a renamed NIfTI folder and `.DS_Store`). It is the OneDrive download that `BrEt\` was unpacked from, so **nothing new**. Listing: `_analysis\drives-dicom\nested_listings_cardiac_mri.csv`.

## 8. Questions for Ryan

| # | Question | Recommendation | Why it matters |
|---|---|---|---|
| **Q1** | **Reopen `AE-biomaGUNE-1519` (`PROJ-0008`, closed)** for B02 (526 exams, 2022) and B03 (136 exams, 2020)? | **Reopen** (`tools/reopen_project.py`), as was done for `0219`/`1019`. Every claim is the study's own name, and the DB confirms the animals and dates | Without a reopen they ingest with a blank project, and the protocol's own data is split from its 187 production rows |
| **Q2** | **B06 `1019` MRS 2021 (66 exams): which project?** | **Blank, like the 854 other 2021 `1019` exams** (decision D6, the `SegBioMed` question), so all 2021 `1019` MRI moves together when D6 is decided | `PROJ-0006` holds the 2022 `1019` rows; the 2021 recovery was deliberately left project-less |
| **Q3** | **B07 phantoms/collaborations (133 exams, 2022-10…2023-07), owner initials `prc`/`pr`:** ingest? Who is `prc`? | Ingest with **blank project**, `sample_type` phantom/material, `researcher` `NA`. My unconfirmed guess for `prc` is Pedro Ramos-Cabrer (MRI platform), so I'd ask him | They are raw acquisitions on our scanner, missing only because of the regex. But they are partly external collaborations (CIDETEC, Portugal, Susana) |
| **Q4** | **B08 ICON Madrid 2024 (363 exams, 4 mice, an external scanner):** ingest as an external instrument, or leave? | Ask Claudia what it is. If it is collaborator data we hold for the lab: `XMRI` + `collaborator:` data source, the DTS24 pattern, blank project | No instrument code exists for an ICON. The animals are not in our facility DB |
| **Q5** | **N04: 3 PET/CT files of 2019 (operator krishna, "hugo native heparin"), no protocol code** | Ingest with **blank project** under the NI flat path, or hold with the 673 `S:\gnuclear` acquisitions awaiting AE codes (D-G) | An AE code is a regulatory identifier and must not be guessed |
| **Q6** | **N02: 18 Molecubes `FDK` reconstructions of Marina's `1321` CTs (Aug 2023)** are in the `S:\gnuclear` snapshot but not in production, while their `ISRA` siblings are | **Not a drives ingest.** Ask the `S:\gnuclear` owner why `ni_flat` dropped them. Most likely the coarse `(timestamp, modality)` cross-source guard declined a second reconstruction of an already-loaded scan (`ni_flat.py` docstring) | If intended, nothing to do. If not, ingest them from the snapshot, not from the drives |
| Q7 | **Proceed with B04, B05, N03** (active or pre-approved projects) once the dry runs are clean? | Yes | Needs Ryan's go: "the drives' DICOM ingest" |

## 9. What surprised me

- **`_extract\` was not what the handoff said.** It holds only the 82 + 253 `.czi` members, not Haizpea's or Drive zuri's MRI.
- **The catalog never opened nested archives.** That hid a 14.2 GB OneDrive zip inside `Cardiac MRI.zip`, plus `.czi` and `.svs` inside Drive zuri (reported to the coordinator, routed to A).
- **The scanner pull's silent skip is large and hits real animal data** (§5).
- **The facility DB records which scanner was used**, and it agrees with `ACQ_station` exactly: 11.7T vs 7T.
- **"Laura's Bruker MRI" is fully in production already.** What is new on her drive is the phantoms, and none of her CTs.
- **Folder names lie about projects:** the Ferritas CTs are `1123`.

## 10. Proposed wording for the shared files (the coordinator applies at merge)

**`tasks/STATUS.md` §2, drives bullet:**
> - **Drives' DICOM stream (stream B):** Phase 1 done 2026-10-02 (`tasks/drives_dicom_review.md`).
>   - Already in production: 605 distinct MRI exams and 177 NI reconstructions.
>   - New: 1,306 lab MRI exams (`1519`, `0619`, `0420`, `1019`) and 8 `1319` PET/CT, awaiting Ryan's go.
>   - Questions: reopen `1519`, plus the phantom, ICON, 2019 PET and FDK groups.
>   - Found 526 post-horizon `1519` exams the scanner pull silently dropped (evidence for D3).

**`tasks/STATUS.md` §0 D3, append to Detail:**
> Measured on the drives 2026-10-02: 1,568 exams in studies matching neither regex, **0 in production**, including 526 post-horizon `1519` (`_weekN`) and nine May 2023 `0721` `_biod` sessions (`tasks/drives_dicom_review.md` §5).

**`tasks/BACKLOG.md`:**
> - 🔸 **`_scanner_model` maps `BIOSPEC 500` to "50T"** (`tools/ingest/paravision_metadata.py`). Should be 11.7T. No production row is affected yet (no 11.7T ingested); fix before any 11.7T ingest relies on auto-derivation.
> - 🔺 **Re-pull from kenia the sessions the regex skipped**, before the retention horizon passes them: `1519` `_weekN` (Mar 2022, if not taken from the drives), `0721` `_biod` (May 2023), and the phantoms. It depends on D3(a).
> - 🔸 **Ask the `S:\gnuclear` owner about 18 `FDK` reconstructions** in the snapshot but not in production (`drives_dicom_review.md` Q6).
> - Low: **~83 `1519` 2020 sessions survive only as derivatives.** Check `K:\gjesus\MRI` once, off-peak.

**`CHANGELOG.md`** (on the ingest, not now):
> 2026-10-0x — Drives' DICOM stream: …

**`historical_drives_closeout_plan.md` Step 5 item 4:**
> Phase 1 ✅ 2026-10-02 (`drives_dicom_review.md`); Q1–Q7 to Ryan.
