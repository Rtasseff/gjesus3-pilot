# MRI study folders that match no ingest regex: the report, the re-scan and the reconciliation (STATUS §0 D3)

**Status:** 🔶 DRAFT for the coordinator, 2026-10-05. The code is on branch `feat/mri-unparsed-report`; the re-scan was **read-only** (nothing ingested, nothing written to any source).
**Ruling (✅ Ryan, 2026-10-05, D3):** "NOW. Make the ingest report every study folder that matches neither regex (code change on a branch, with tests), then re-scan the historical sources read-only and report the count. Reconcile it with the drives DICOM review §5 as it stands after the weekend."
**Evidence (regenerable, not backed up):** `D:\projects\gjesus3\scratch_mri-unparsed-report\` — the scripts, their logs and the per-study CSVs listed in §10.

## Summary

1. **The ingest now reports every study folder whose name matches no `filename_parse` rule**: one record per study folder with its exam-folder count, a NOT PARSED section in the BATCH SUMMARY, `--unparsed-report <file.csv>`, and the same list on the GUI's MRI page and in `mri-ingest` (§9). No regex was relaxed. 36/36 test suites pass.
2. **The count: 1,481 study folders holding 11,602 exam folders match neither production regex** across the three sources (1,472 distinct names; G1 is on both kenia and K:).
   - kenia: 1,364 / 9,869;
   - K:: 9 / 165;
   - the two drives: 108 / 1,568.
3. **Most are other groups' studies** on the shared scanner: 1,147 study folders (8,290 exam folders), class (b).
4. **Class (c), MFB data not in production with the raw present: 59 study folders, 451 exam folders.**
   - 51 on kenia (310 exam folders, 305 of them reconstructed images), all from 2024–2026;
   - 8 on K:, Ermal's 2021 `0118` sessions (141).
5. ⚠️ **The scanner's horizon jumped two years.** It starts at 2024-01-05 (PV 7) and 2024-01-11 (PV 6) today; in June it reached 2022-01-10. The oldest class-(c) sessions (rats R177–R179 of `0721`, 2024-02-07/08, 45 image exams) are one month inside it (§5).
6. ⚠️ **Damage already done: 57 MFB study folders are gone.** The June bulk load listed and skipped them as unparsable, they are no longer on kenia, and no copy was found in production, on the drives (raw or derivative) or on `K:\gjesus\MRI` / `K:\gjesus\Irene`. They include animal sessions of `0619`, `0618`, `0721` and `0220` (§6).
7. **§5 reconciles exactly.** Of the 1,568 drive exams:
   - 1,417 are in production through stream B's 8 configs;
   - 109 are copies on the same drive (107 of them copies of a production exam);
   - 24 are not registered under the convert-first rule (21 spectroscopy, 3 no reconstruction);
   - 18 were never acquired;
   - 0 are unexplained.
8. **140 kenia study folders (1,125 image exams) carry another group's initials but an MFB link**: protocol `0721`, LP-IONP material, or the Portugal phantom series stream B ingested. Class (b?); Ryan's call (§8).

---

## 1. Method

**The same test the ingest applies.** The two production regexes are read from the production config files (`tools/configs/mri_jrc_animalfirst.yaml`, `mri_jrc_projfirst.yaml`, both `source: parent_name`). Each candidate study-folder name goes through the ingest's own `ingest.filename_parser.parse_regex`. A name is "neither" when both raise `FilenameParseError`, which is exactly what the new report would list under both configs.

**Units.**
- A **study folder** is the parse target: the parent of the exam folders.
- An **exam folder** holds `acqp` and `method`, the ingest's own `_is_paravision_exam`.
- On the drives the unit is §5's: a folder holding `acqp` **or** `method`. 4 of the 2,574 hold only one of the two, all in B04's `BrEt\DICOM\`: the X1 pair (`m27/4`, `m31/4`) and the never-acquired `m27/3` and `m32/5`. All 4 are accounted for in §4.

**Classes** (per study folder):

| Class | Meaning | How it was decided |
|---|---|---|
| (a) | In production anyway | ≥1 exam joins `registry_raw.original_name` = `<study>/<exam>` (X1's `<study>__<exam>` on the drives) |
| (b) | Another group's study | Console initials other than `jrc` (the MFB PI's; every one of the 10,314 bulk-load rows is `jrc`), and no MFB link |
| (b?) | Another group's initials **with** an MFB link | A protocol code that is a gjesus3 project, LP-IONP in the name, or the Portugal phantom series; listed for Ryan, not decided |
| (c) | MFB, not in production, raw present | `jrc` initials, ≥1 exam folder, none registered, ≥1 reconstructed image |
| (d) | Not imaging, or no raw | No exam folder at all, or (MFB) exam folders without any reconstructed image |

**Sources (all read-only):**

| Source | How it was read | Errors |
|---|---|---|
| **kenia**: `/opt/PV-7.0.0/data/nmr`, `/opt/PV6.0.1/data/nmr` | SFTP listings only (paramiko, credentials from `ftp_mirror.cred_file_defaults`, never printed). Every top-level folder was classified. Each unmatched one was listed together with each of its child folders. Its `subject` file was read (≤64 KB) to identify it. For the (c)/(b?) candidates: one listing of each exam's `pdata/<n>/` and a 4 KB read of `method` (scan type) | 0 |
| kenia: the two `nmrsu` (superuser) folders | Listed for the record; they were never a bulk-load source | 0 |
| **K:**: `K:\gjesus\MRI`, `K:\gjesus\Irene` | Directory walk, listing only: a study is a folder holding a `subject` file; its exams are child folders holding `acqp` + `method` (one more level for Irene's `<study>\Other data\<exam>`); no exam folder was descended into. 799 folders listed. The SegBioMed census was used as a cross-check, not as the source: Irene's share has changed since 2026-08-21 | 0 |
| **The drives** (staged copy erased 2026-10-05) | The records on the NAS: both `manifest.csv` (78,839 loose files), the catalog's `archive_members.csv` (782,339 members) and the nested-archive listings. Study folders were derived from the paths alone. This **reproduces stream B's `inventory.csv` exactly: 2,574 exams, 0 differences** | — |
| Registry | `registry_raw.csv` (27,034 rows, read 2026-10-05), plus the retired tombstones | — |
| Facility DB | `SELECT` on `projects` and `responsable`, for the holders of protocols `0721`, `0118`, `1022`, `0423`, `0525` and `1519` | — |
| The June bulk load's own selection | `D:\projects\mri\mri_jrc_manifest.csv` (2026-06-12, 1,080 `jrc` studies with a status) and `_pull_batch1.log` | — |

## 2. The count, per source

| Source | Study folders there | Exam folders there | **Matching neither regex: study folders** | **…exam folders** |
|---|---:|---:|---:|---:|
| kenia, PV 7 `nmr` | 3,051 | — | **1,327** | **9,693** |
| kenia, PV 6 `nmr` | 151 (+2 files, 1 link) | — | **37** | **176** |
| `K:\gjesus\MRI` | 122 | 1,970 | **8** | **141** |
| `K:\gjesus\Irene` | 83 | 1,557 | **1** | **24** |
| Drive 1 (FRIO-X6) | 111 | 1,987 | **77** | **1,424** |
| Drive 2 (MFB-Disco-2) | 79 | 587 | **31** | **144** |
| Drives, together | 190 | 2,574 | 108 | 1,568 |
| **Total** | | | **1,481** | **11,602** |

- The kenia exam count was taken only for the unmatched folders. The other 1,838 folders match a regex: 1,083 project-first and 755 animal-first.
- The drives' nested OneDrive zip (4 study folders, 67 exams) is excluded, as in §5. It is a byte-identical copy of `BrEt\`.
- **Distinct study names: 1,472.** `jrc250526_145_0522` (G1) is on both kenia (PV 6) and K:, and `~TEMP` is on both kenia roots. No drive study is on kenia or K:.

## 3. Classification

| Class | kenia | K: | Drives | **Total** |
|---|---:|---:|---:|---:|
| (a) in production anyway | 6 / 94 | 1 / 24 | 108 / 1,568 ¹ | **115 / 1,686** |
| (b) another group | 1,147 / 8,290 | 0 | 0 | **1,147 / 8,290** |
| (b?) another group's initials, MFB link | 140 / 1,170 | 0 | 0 | **140 / 1,170** |
| (c) **MFB, not in production, raw present** | 51 / 310 | 8 / 141 | 0 | **59 / 451** |
| (d) not imaging, or no raw | 20 / 5 | 0 | 0 | **20 / 5** |
| **Total** (study folders / exam folders) | 1,364 / 9,869 | 9 / 165 | 108 / 1,568 | **1,481 / 11,602** |

¹ Every drive study folder holds at least one exam now in production, except B02's `…_m35_week3_1519_1_1_bad`, whose 34 exams are all copies. Not every exam of these folders is in production; §4 has the per-exam account.

**(a) In production anyway.**
- **kenia, 6:**
  - G1 `jrc250526_145_0522`: 24 of 24, via `tools/configs/mri_0522_m145_irene.yaml` (from the K: copy, staged flat, so the names join);
  - the 5 June–August 2026 phantoms: 69 of 70 exam folders, via `tools/configs/mri_july_1125/mri_phantom_*.yaml`. Exam 66 of `jrc260708_phantom` was never acquired (no data).
- **K:, 1:** G1.
- **Drives, 108:** stream B (§4).

**(b) Another group, 1,147 kenia study folders.** Initials:

| `jl` | `pr` | `aka` | `abh` | `dan` | `sp` | `prc` | `fer` | `mp` | `ak` | `sptest` |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 523 | 455 | 34 | 34 | 28 | 25 | 20 | 14 | 9 | 3 | 2 |

- **`pr` is checked, not assumed** (the handoff's ⚠️): the facility DB names Pedro Ramos Cabrer (lab 14) as the holder of protocol `0423`, and none of the protocol codes in these 455 `pr` names (`0524`, `0254`, `0823`, `0920`…) is a gjesus3 project.
- The `pr` studies that do carry an MFB link are in (b?), not here.

**(b?) Another group's initials, with an MFB link: 140 kenia study folders, 1,170 exam folders (1,125 reconstructed images).** For Ryan:

| Subgroup | Folders | Evidence |
|---|---:|---|
| Protocol `0721` in the name (`pr` 120, `aka` 3, `ak` 2) | 125 | `0721` is a gjesus3 project (`AE-biomaGUNE-0721`, which holds MFB's own `jrc…_0721` studies). But the facility DB names **Daniel Padró**, not Jesús Ruiz-Cabello, as its holder ("Biodistribución de agentes de contraste mediante imagen por RM"): a shared platform protocol. Jesús holds `0118`, `1022`, `0525` and `1519` |
| `0721` **and** LP-IONP (`pr…_MBbiodist_0721_LPIONP…`) | 4 | LP-IONP is the material of Laura's (MFB) biodistribution work. Its 2022–23 exports sit on her drive (drives review §5) |
| LP-IONP only (`prc…_Cells_LP_IONP`) | 1 | as above |
| The Portugal phantom series (`prc` 8, no initials 2), 2024-01/02 | 10 | It continues stream B's B07 `prc` phantoms, which Ryan ruled to ingest with a blank project (drives review Q3) |

The oldest is 2024-01-08 (`pr240108_NP_M162_0721`), 3 days inside the scanner's horizon.

**(c) MFB, not in production, raw present: 59 study folders, 451 exam folders.**

| Where | Group | Folders | Exam folders | Notes |
|---|---|---:|---:|---|
| kenia | `0721` rats R177–R179 (`R`, not `m`), 2024-02-07/08 | 6 | 45 | all images |
| kenia | IONP cFLFLF, 2024-02-20 | 1 | 3 | |
| kenia | `1022` m13RE / m15RE, 2024-03-12/13 | 2 | 18 | |
| kenia | `phantomflujo` (name dated `050224`), 2024-05-02 | 1 | 33 | |
| kenia | `testTrigger`, 2024-09-12 | 1 | 5 | 2 images |
| kenia | `1022` m39–m46 `t3h` / `t24h` / `POST_…`, 2024-11-20…22 | 14 | 51 | |
| kenia | `0721` IONP m244–m247 (`3h`, `POST_24H`), 2025-03-27/28 | 12 | 57 | |
| kenia | `EB_R195`, 2025-06-11 | 1 | 6 | 4 images |
| kenia | `0423` m9b / m10b / m19b / m20b, 2025-06…11 | 4 | 26 | |
| kenia | `4dflow`, 2025-08-27 | 1 | 5 | |
| kenia | phantoms, 2025-08 … 2026-04 (Gadovist, phantom1/2, Phantom, AS ferritasphan ×2, Claudia nanos sunana3) | 8 | 61 | |
| **kenia, total** | | **51** | **310** | 305 images, 3 without a reconstruction, 2 spectroscopy/calibration |
| K: `MRI\Proyecto 0118` | Ermal, `jrc2109xx_m175…m182_ermal` (no protocol code in the name), 2021-09-01/02 | 8 | 141 | `0118` is Jesús's protocol (facility DB). Pre-horizon: never on kenia in June, only on K: |

**(d) Not imaging, or no raw: 20 kenia folders, 5 exam folders.**
- 5 are not studies: `~TEMP` ×2, `m100t0`, `m100t1`, `nmr`.
- 12 are other groups' empty study folders.
- 3 are MFB-named, with only never-acquired exams (5 exam folders between them): `jrc250919_phantom1` (14:15), `jrc251104_m20b_0423` and `jrc260416_…sunana2`.

## 4. Reconciliation with `drives_dicom_review.md` §5, after the weekend

**4a. The §5 table, then and now.** §5 counted an exam "in production" when its exam was, so copies of a production exam counted. Here each exam is counted once, and copies are separate.

| §5 row | Exams | In production, §5 (10-02) | **In production now** | Copies on the same drive ² | Not registered | Never acquired | Check |
|---|---:|---:|---:|---:|---:|---:|---|
| Match animal-first | 957 | 614 | **894** | 58 | 0 | 5 | 894 + 58 + 5 = 957 |
| Match project-first | 49 | 49 | **49** | 0 | 0 | 0 | |
| **Match neither** | **1,568** | **0** | **1,417** | 109 | 24 | 18 | 1,417 + 109 + 24 + 18 = 1,568 |
| Total | 2,574 | 663 | 2,360 | 167 | 24 | 23 | 2,360 + 167 + 24 + 23 = 2,574 |

² Copies of an exam elsewhere on the same drive. 165 of the 167 are copies of an exam now in production; 2 (in B02 and B07) are copies of an exam not registered for lack of a reconstruction.

**4b. The 1,568 by batch: what went in, through which ingest, and what remains.**

| Batch | Study folders | Exams | **In production** (config, `tools/configs/drives_2026-09/dicom/`) | Copies on the drive | Not registered (convert-first) | Never acquired |
|---|---:|---:|---|---:|---:|---:|
| B02 `1519` weeks 1–4, 2022 | 31 | 560 | **525** `dicom_B02_1519_weekN_2022` | 34 (33 of production exams + 1 of the no-recon one) | 1 (no reconstruction: `m35_week3/35`) | 0 |
| B03 `1519` week 2, 2020 | 10 | 135 | **135** `dicom_B03_1519_semana2_2020` | 0 | 0 | 0 |
| B04 `0619` BrEt, 2020 | 19 | 300 | **234**: 67 `dicom_B04a_0619_bret_117T`, 165 `dicom_B04b_0619_bret_7T`, 2 `dicom_X1_oneoff_acqpless` | 64 | 0 | 2 |
| B06 `1019` MRS sessions, 2021 | 8 | 66 | **37** `dicom_B06_1019_mrs_2021` (the image exams) | 0 | 21 (spectroscopy) | 8 |
| B07 phantoms / collaborations, 2022–23 | 31 | 144 | **123** `dicom_B07_phantoms_collab_2022_23` | 11 (10 + 1 of a no-recon one) | 2 (no reconstruction) | 8 |
| B08 Madrid ICON, 2024 | 9 | 363 | **363** `dicom_B08_icon_madrid_2024`, as `XMRI` | 0 | 0 | 0 |
| **Total** | **108** (101 names) | **1,568** | **1,417** (1,054 `MRI` + 363 `XMRI`) | **109** | **24** | **18** |

**By class, what remains of the 1,568:**
- (a) **1,417 in production**.
- 109 copies (none of them a distinct acquisition).
- (d) 42 not imaging or no raw: 21 spectroscopy, 3 without a reconstruction, 18 never acquired.
- (b), (b?), (c): **0**.

Notes:
- B07's `prc`/`pr` studies and B08's external ones are other people's by name, but they are in production by Ryan's rulings (Q3, Q4), so they count as (a).
- The 24 not-registered exams are kept as other data (`notregistered_exams.csv`, stream A).
- The 18 never-acquired exams come from stream B's `excluded_dicom_*.csv` lists.

**The same breakdown for kenia and K:** (from §3)
- **kenia:** 9,869 exam folders.
  - (a) 93 in production + 1 never acquired;
  - (c) 310 not in production: 305 images, 3 without a reconstruction, 2 spectroscopy;
  - (b?) 1,170: 1,125 images, 33 never acquired, 12 without a reconstruction (as found on the scanner);
  - (b) 8,290;
  - (d) 5.
- **K::** 165 exam folders.
  - (a) 24 in production (G1);
  - (c) 141 not in production (Ermal, `0118`). The image/spectroscopy split is unknown: K: was listed, not read.

## 5. ⚠️ The horizon: the urgent part

**It moved two years in four months.**
- **Today:**
  - PV 7: 3,050 dated studies, 2024-01-05 → 2026-10-05.
  - PV 6: 147 dated studies, 2024-01-11 → 2025-09-26.
- **In June:** the bulk load's manifest listed `jrc` studies back to 2022-01-10 (PV 6) and 2022-03-24 (PV 7).
  - In 2022–23 that was 496 PV 6 and 86 PV 7 `jrc` studies.
  - **None of them is on either root today.** The parents (`/opt/PV-7.0.0/data`, `/opt/PV6.0.1/data`) hold only `nmr` and `nmrsu`, so nothing was moved to an archive folder beside them.
  - PV 6's `nmr` folder was last modified **2026-08-26**, eleven months after its newest study. That fits a deletion on that day.
- **This is a cut, not a drift.** Whether a next cut is planned is the question for the platform manager (BACKLOG MODERATE 2026-08-21).

**Class (c) on kenia, by date:**

| Period | Folders | Exam folders (images) |
|---|---:|---:|
| 2024 H1 | 10 | 99 (99) |
| 2024 H2 | 15 | 56 (53) |
| 2025 H1 | 15 | 76 (74) |
| 2025 H2 | 10 | 75 (75) |
| 2026 H1 | 1 | 4 (4) |
| **Total** | **51** | **310 (305)** |

**If the next cut is like the last one, all 25 studies of 2024 go: 155 exam folders, 152 of them images.** Most urgent, oldest first:
- `jrc240207/08_0721_R177…R179` (6 folders, 45 images), one month inside the horizon;
- `jrc20240220_IONP_cFLFLF` (3);
- `jrc240312/13_m13RE/m15RE_1022` (18);
- `jrc050224_phantomflujo` (2024-05-02, 33).

**(b?) is older still:** 41 of its 140 folders are from 2024 H1, and its oldest is 2024-01-08. If Ryan wants any of them, they come first.

## 6. ⚠️ Damage already done: the June skip list

- **The June bulk load knew.** Its selection file (`D:\projects\mri\mri_jrc_manifest.csv`, 2026-06-12) lists 1,080 `jrc` study folders on kenia:
  - 935 marked to ingest;
  - **145 marked `skip`**: 73 "info-present-unparsed (recoverable)", 53 "no-project-or-animal", 19 "phantom".
- All 145 match neither regex. The load pulled only the 935 (`_pull_batch1.log`: "935 folders"), and **the skip list never reached the system**: no queue, no registry trace, no STATUS line.
- **Today:**
  - 57 are still on kenia: 3 now in production (G1 and the two June 2026 phantoms), 51 are class (c) above, 3 are class (d).
  - **88 are gone.** Of those, 31 are in production, all from the drives: 30 of B02's `1519` weeks and one B07 phantom (`jrc230620_Phantom_Claudia_10K`).
  - **57 are found nowhere:** not in production, not on the drives (neither raw nor any derivative, across all 78,839 files and 782,339 archive members), not on `K:\gjesus\MRI` or `K:\gjesus\Irene`.
- Their exam counts are unknown: the June file did not list exams. Per study: `D3_lost_studies_derivatives_20261005.csv` and `D3_june_manifest_vs_now_20261005.csv`.

| The 57 | Folders |
|---|---:|
| Animal sessions: `0619` animals 191–200 without the `m` (2022-01-25); `0618` `m153…m162_post` (2022-01/02); `0721` `m13…m18postadm` (2022-04) + `m27post` (2022-07); `0220` `m165__0220`, `m171__0220` (2022-07); `0721_74`, `0721_75` (2022-12); `m6_132` (2022-06) | 23 |
| Phantoms and coil / sequence tests: Palmira arrays, `fantomFH`/`fantomFlow`, 19F, `pv*` tests, Manon IONP, LFM, Claudia 3K. One of them, `jrc220327_19F_FDG_mouse_array`, may be an animal scan | 34 |

## 7. Outside the count, found on the way

- **The pull filter, not the regex, is what decided the bulk load's scope.** The June selection kept names containing `jrc`, and the GUI's SFTP list defaults to the same filter (`MRI_SFTP_FILTER = "jrc"` in `tools/operator/gui/app.py`).
  - So `20250416_091725_jr250416_m1_0423_1_jr250416_m1_0423_1_1` was never pulled. It holds **7 image exams**, its name matches the animal-first regex, its initials are typed `jr`, and there is no registry row for `m1_0423` on that day. Of the other three, two `jr` folders are empty, and the `jcr` one names a session that is in production under `jrc`.
  - Conversely, **1,380 other groups' study folders match a production regex** (`jl` 1,301, `mp` 40, `pr` 19, `aka` 15, `sp` 4, `prc` 1). Pulled without the `jrc` filter, they would ingest as MFB data.
  - The NOT PARSED report sees only what is in the staging, so it catches neither case.
- **9 June "ingest" studies have no registry row.** None is a loss as far as can be checked:
  - the 3 still on kenia hold 0 exam folders;
  - each of the 6 gone has a same-day study of the same animal in production (aborted starts).
- **`nmrsu`** (the superuser area, never a bulk source): 36 folders, 262 exam folders. They are platform QA, operational qualification (2023, 2024), the PV 7 upgrade (2021) and PV 6 tests (2016–2021). **None is MFB.**
- **K:**
  - Irene's `0525\Feb26\MRI\20260224_105131_jrc260224_m37_0525…` matches the regex but is not in production: it is her renamed copy of the `m39` session (STATUS §0 D2).
  - Her 15 studies nested as `<study>\Other data\<exam>` are all in production under their real names (300 exam folders), so the `grandparent_name` gap has cost nothing so far.
  - With the new report, such a nesting shows as NOT PARSED "Other data" instead of vanishing.

## 8. Needs Ryan (named, not decided)

| # | Question | Why now |
|---|---|---|
| R1 | **Re-pull and ingest the 51 kenia (c) studies** (305 images), 2024 first, each through a scoped config (pattern names the study; no shared-regex change), as was done for G1 and the phantoms. A pull plus ingests: needs Ryan's go | §5: the next cut could take all of 2024 |
| R2 | **The (b?) bucket** (140 folders, 1,125 images): the `pr`/`aka`/`ak` studies on the shared `0721` protocol, the LP-IONP ones, and the Portugal phantoms. In or out, and per subgroup? | The oldest is 3 days inside the horizon |
| R3 | **Ermal's 8 `0118` studies of 2021 on K:** (141 exam folders): ingest? | Not ageing off (K:), but MFB data missing from gjesus3 |
| R4 | **The 57 lost studies:** search the other researcher shares on K: by name (out of scope here; K: is in daily use), or record them as lost | Some are animal data |
| R5 | **Ask the platform manager about the 2026 deletion** (PV 6's folder changed 2026-08-26; PV 7's date is unknown) and any next cut (BACKLOG MODERATE 2026-08-21, already open) | It decides R1's deadline |
| R6 | **`jr250416_m1_0423_1`** (7 images, outside the count): ingest? | MFB-named apart from the typo |
| R7 | **A durable queue, `registries\pending_unparsed.csv`?** Not built (a new registry file is a new convention). **Recommended:** the June skip list existed and still went nowhere. A per-run CSV that someone must keep is the same failure waiting to recur; a queue beside `pending_dicom_regen.csv` would make "unparsed" a tracked worklist that STATUS can count | Durable trace for the next bulk load |
| R8 | **Rebuild and redeploy the operator GUI exe** so operators see the new list (a deploy). Not done | Until then, the exe still labels an unparsed study "housekeeping" |

## 9. The code (on the branch)

| Where | What |
|---|---|
| `tools/ingest/unparsed.py` (new) | The one construction site: the record (one per parse target: study folder, path, exam-folder count, dropped matches, rule, reason, config), the summary wording, the CSV |
| `tools/ingest/config.py::expand_batch` | **Optional `unparsed=` list collector.** The return type is unchanged, so callers that don't pass it behave as before (`drive_staging/ingest_check.py`, `ingest/test_case_table.py`). The per-exam `SKIP` lines keep their format, which the GUI preview parses. Every caller also gets one `[expand_batch] NOT PARSED: …` line, worded without SKIP/WARN because `ingest_check.py` counts those words. Exam folders are counted with the ingest's own detector, on the failure path only. *Why a collector argument rather than a result object:* explicit, no hidden state, and nothing changes for the existing callers |
| `tools/ingest_raw.py` | A WARN after discovery, the **NOT PARSED section in BATCH SUMMARY**, and **`--unparsed-report <csv>`**. It is written right after discovery (it survives a later crash) and in `--dry-run`. There is no default location; it is never a registry |
| `tools/operator/preview.py` | `PreviewResult.unparsed`: one entry per study, from the collector, not by re-parsing stdout. Each per-exam drop is tagged `unparsed`. `dropped` / `n_dropped` are unchanged |
| GUI: `app.py`, `static/mri.js` | `/api/preview` and `/api/mri/preview` return `unparsed`. The MRI page lists the study folders loudly with their exam counts, and calls only the untagged drops "housekeeping". *Why the page changed:* grouping could be done in `preview.py`, but the page labelled **every** drop "normal ParaVision housekeeping", which was the silent skip on screen |
| `tools/operator/mri_ingest.py` | The same block, printed last, at the confirm prompt |
| `tools/test_unparsed_report.py` (new) | 57 checks; temp dirs only. Suite: **36/36 pass** |
| Docs | `tools/INGEST_CLI.md` (the flag and a NOT PARSED section); `mfb-rdm-docs/10_TOOLS.md` §2.1.3. Its bullet said a regex non-match "is still ingested"; the code never did that, and the bullet is corrected |

Example, from `ingest_raw.py --dry-run --unparsed-report …` on the test tree:

```
  NOT PARSED: 4 study folder(s) (10 exam folders) matched no filename_parse rule
  NOTHING under them was ingested:
    jl260707_1225_m26   1 exam folder
    jrc221003_0721_m45  3 exam folders
    jrc250526_145_0522  4 exam folders + 1 other entry
    jrc260709_phantom   2 exam folders
  Full list (paths, reasons): <tmp>\unparsed_demo.csv
```

## 10. Reproducing it

All read-only. The scripts are in the evidence folder. They import this worktree's `tools/` (`rescan_common.WT`; after the merge, point it at a checkout of `main`).

```
cd D:\projects\gjesus3\scratch_mri-unparsed-report
python rescan_kenia.py .                       # kenia: SFTP listings + subject reads, ~30 s
python rescan_kenia_exams.py kenia_unmatched_studies_20261005.csv kenia_candidate_exams_20261005.csv
python rescan_kenia_exams.py kenia_unmatched_studies_20261005.csv kenia_candidate_exams_prc_20261005.csv bq_not_detailed.txt
python rescan_k.py .                           # K: walk, ~10 s
python rescan_drives.py .                      # drive records on J:, ~10 s; compares with inventory.csv
python analyze_rescan.py 20261005              # classes, the §5 reconciliation, the June manifest (log: analyze_rescan.log)
python side_checks.py                          # §7: drive copies, June 'ingest' studies with no row, typo'd initials
python side_checks2.py                         # §7: the same animal on the same day in the registry
python side_checks_kenia.py                    # §7: exam content of the matched-but-unregistered folders
python lost_derivative_search.py               # §6: derivatives of the 57 on the drives
python db_protocols.py 0721 0118 1022 0423 0525 1519   # facility DB, SELECT only
python db_responsables.py 11 17 23
```

| File (`…\scratch_mri-unparsed-report\`) | What it is |
|---|---|
| `kenia_toplevel_20261005.csv` | Every top-level entry of the four kenia folders, with its regex class |
| `kenia_unmatched_studies_20261005.csv` | Every unmatched folder: exam/acqp-only counts, `subject` id, registry join |
| `kenia_candidate_exams_20261005.csv`, `kenia_candidate_exams_prc_20261005.csv` | Per exam of the (a)/(c)/(b?) candidates: recons, 2dseq, DICOM, method, kind |
| `k_studies_20261005.csv` | Every K: study folder (205), layout, regex class, registry join |
| `drives_studies_from_paths_20261005.csv` | Every drive study folder derived from the records (194, nested zip included) |
| `D3_kenia_unmatched_classified_20261005.csv`, `D3_k_unmatched_classified_20261005.csv` | The classification (§3) |
| `D3_drives_exams_reconciled_20261005.csv`, `D3_drives_unmatched_studies_20261005.csv` | The §4 reconciliation, per exam and per study folder |
| `D3_june_manifest_vs_now_20261005.csv`, `D3_lost_studies_derivatives_20261005.csv` | §6 |
