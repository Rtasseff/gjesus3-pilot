# The M. Jesús drive, stream N: the PET/CT production lacks (gate document)

**Status:** 🔶 BUILT, DRY-RUN AND REHEARSED, for the coordinator's gate and then Ryan's go. Nothing was written to
production. · **Date:** 2026-10-06 · **Branch:** `feat/drive3-petct` (worktree `gjesus3-dev\drive3-petct`)
**Plan:** [`drive3_production_plan.md`](drive3_production_plan.md) stream N · **Assessment:** [`drive3_raw_coverage.md`](drive3_raw_coverage.md) §4 (A1)
**Scripts:** [`tools/drive_staging/drive3/petct_*.py`](../tools/drive_staging/drive3/) · **Configs:** [`tools/configs/drive3_petct/`](../tools/configs/drive3_petct/)
**Outputs and logs (regenerable, not backed up):** `D:\projects\gjesus3\drive3_streams\petct\` (`out\`, `stage\`, `rehearsal_nas\`)
**Units:** GB = 10⁹ bytes. "Acquisition" = one Molecubes reconstruction, the production unit (§2).

---

## Summary

1. **202 acquisitions, 8.03 GB, into five existing active projects; nothing is created or reopened.** 201 are animal
   PET/CT scans of 117 animals, every one confirmed in the facility DB (the animal is in the protocol and logs a procedure
   within 3 days of the scan). **One is not an animal**: an 18F phantom the NI platform scanned, filed in animal 201's
   folder (§3); it goes in as a phantom with no project.

   | Project | From the snapshot | From the drive | Total |
   |---|---:|---:|---:|
   | `AE-biomaGUNE-0619` (`PROJ-0004`) | 57 | 64 | 121 |
   | `AE-biomaGUNE-0320` (`PROJ-0007`) | 15 | 14 | 29 |
   | `AE-biomaGUNE-1422` (`PROJ-0013`) | 0 | 24 | 24 |
   | `AE-biomaGUNE-1019` (`PROJ-0006`) | 16 | 0 | 16 |
   | `AE-biomaGUNE-1123` (`PROJ-0014`) | 11 | 0 | 11 |
   | no project (the phantom) | 1 | 0 | 1 |
   | **Total** (CT 115, PET 87; 2021 95, 2022 72, 2023 24, 2024 11) | **100** (3.21 GB) | **102** (4.82 GB) | **202** |

2. **Source.** The 100 that the 2026-08-12 `S:\gnuclear` snapshot holds are ingested **from the snapshot**, through the
   fixed discovery, so they look like the 1,508 backfilled acquisitions; all 100 snapshot files were re-hashed today and are
   byte-identical to the drive manifest and to the snapshot's own manifest. The 102 found nowhere else come **from the
   drive**, staged to `D:` by a copy checked against the drive manifest (492/492 staged files match).
3. **Identity** is the machine key `(timestamp, modality, algorithm, recon index)`, the same from either source; the
   cross-source dedup on `(timestamp, modality)` makes the source irrelevant to what a later run skips.
4. **The code fix:** `ni_gnuclear_discover.analyse()` now looks further up the path when the parser found **no** protocol
   code, not only a wrong one (`project-recovered:none-><code>`). 17 new test checks (`test_ni_flat.py` 31 → 48, all
   pass), 4 of 4 mutants killed, 0 differences on the 2,485 snapshot files outside the released acquisitions.
   **Suite: 38/38 suites pass** (as on `main`).
5. **What the fix releases among the other 573 held back** (count only; releasing them is a separate decision):
   **160** become ingestable on a re-run of the backfill configs (`1121` 78, `0522` 59, `1019` 16, `1321` 7; 150
   DB-confirmed, 10 parse no animal), **20** get a project but stay skipped by the `(timestamp, modality)` dedup, **393**
   stay held back.
6. **Dry runs against live production** (each bracketed: the registries byte-identical before and after): the two batches
   list exactly **100 + 102**, case by case equal to the plan, every project link free; the **census** of all 492 drive
   reconstructions lists **exactly the 202** and skips the **290** production holds; the **dedup proof** over those 290
   lists **0**. **0 duplicates:** none of the 202 is registered by key or by `(timestamp, modality)`, and no two of them
   share either.
7. **Rehearsal** into a NAS root on `D:` built from production's registries (byte-identical to what the dry runs saw):
   **100/100/0 and 102/102/0; the independent verifier 18/18 PASS** (every file re-hashed equal to `checksums.json`, the
   drive manifest and, for the 100, the snapshot manifest; rows, sidecars, 201 hard links, provenance, subjects); the
   validator finds nothing on the new rows but the documented `condition` sentinel; **the re-run adds 0**; afterwards
   the census lists 0 and **the snapshot backfill re-run lists only the 160 others: the 100 are skipped as registered.**
   Production's registries and the snapshot sources were unchanged throughout.
8. **For the coordinator** (§8): the phantom (in, as a phantom, or out), the 160 released acquisitions, **49 PMOD DICOM
   export files (31 distinct) that no stream plans** (derivatives; stream P), a fifth DICOM-vs-folder animal conflict
   for the BACKLOG item, and 03 §3.3's wording against NI practice.

---

## 1. Decision 1: source and identity

### 1.1 The 100 also in the `S:\gnuclear` snapshot: from the snapshot

| | Evidence |
|---|---|
| **Byte-identical** | All 100 snapshot files re-hashed today (`petct_07b_verify_snapshot.py`): 100 equal to the drive manifest **and** to the snapshot's `_manifest.jsonl`. |
| **Same members** | Every one of the 100 is one file in each copy (one file per key on the drive and in the snapshot; no per-frame split), so the acquisition is the same set of bytes whichever copy is read. |
| **Same shape as the backfill** | Through the fixed discovery and the same snapshot they get the 1,508's researcher (the snapshot's folder: `IAZ_MJ` 88, `MJ` 11), notes (the snapshot path), `original_name` (the machine key) and `.data/` naming. Read from the drive they would carry another researcher token and a drive path, for no gain in bytes. |
| **Why they were held back** | Their subject folder and its parent carry no code (`IAZ_MJ/0619/Dieta cetogenica/174/`, `MJ/1123/241009/23/Gated/`); `analyse()` walked up only for a **wrong** code. With the fix all 100 get the code of their own path: `0619` 58, `1019` 16, `0320` 15, `1123` 11 (the phantom's path gives `0619`, which the case table overrides, §3). |
| **Scope** | The fix also releases 153 other acquisitions in the same two researcher folders. The batch's case table (`on_missing: skip`) admits exactly the 100; the dry run shows the 153 dropped by name. |

### 1.2 The 102 found nowhere else: from the drive

The drive copy is the only one. `J:\_staging_drive3_MJ\` cannot hold hard links to `D:`, so each file is **copied** to
`D:\projects\gjesus3\drive3_streams\petct\stage\new102\<year>\Jesus\MJ\<drive path>` (the snapshot's own layout, as drives
1+2 did for `1319`), its SHA-256 computed in the same pass and compared with the drive manifest before it is renamed into
place (`petct_07_stage.py`, `stage\_STAGED.csv`). Only the drive copy is read, `rb`.

- `researcher = MJ`: M. Jesús, whose drive and PET folder this is, and production's token for her `S:\gnuclear` folder
  (216 rows; her own 2024 console sessions are typed `mjesus`/`MJesus`).
- **Two files were renamed on the drive** (`CT.dcm.dcm`, `PET.dcm.dcm` of `0619` animal 160, three copies each). Their
  scanner names are rebuilt from the header: the timestamp is `AcquisitionDateTime` (equal to the file-name timestamp in all
  490 other reconstructions), the algorithm the tail of `SeriesDescription` (`OSEM`, `ISRA`), the recon index `0` from the
  session's 14 other reconstructions: `20210928094404_PET_OSEM_0`, `20210928095623_CT_ISRA_0`. The index is an inference
  (the header does not record it) and is said so in their notes; the cross-source dedup keys on `(timestamp, modality)`,
  so a wrong index could not make a duplicate.
- The 24 of `1422` sit under `Pili y Mili\Proyecto 1422 Metformin\…`, which the whole-segment grammar does not read as a
  code (by design: it must not pull codes out of names). The batch's case table states the project of every row
  (`on_missing: error`) and `require_project` is off for this batch only.

### 1.3 The dedup proof

| Dry run against live production | Result |
|---|---|
| **Dedup proof** (`drive3_petct_dedup_proof.yaml`): the drive's **290** reconstructions production already holds, staged from the same folders in the same layout, through the N-D batch config unchanged but for `staging_dir` | **0 cases; 290 of 290 skipped** "already in the registry" (cross-source dedup on `(timestamp, modality)`); the case table is never reached |
| **Census** (`drive3_petct_census.yaml`): all **492** distinct reconstructions on the drive, no case table, no project requirement | **202 listed, exactly the plan's 202 keys; 290 skipped** |
| **A later re-run of the snapshot backfill**, today (the seven `ni_gnuclear_prod_*.yaml`, unchanged, with the fixed code) | **260 listed = these 100 + 160 others**: `IAZ_MJ` 183 (89 + 94), `MJ` 70 (11 + 59), `Marina` 7; `Irene`, `Itziar`, `Ermal`, `CarlottaS` 0 |
| The same re-run **after** the rehearsal (the rehearsal root, which then holds the 202) | **160 listed, exactly the 160 others, none of the 202**: `IAZ_MJ` 94 (222 skipped = 133 + our 89), `MJ` 59 (227 = 216 + our 11), `Marina` 7. **The 100 are skipped as registered.** The census lists 0 (492 skipped) and the dedup proof 0 |

Within the 202, no two acquisitions share `(timestamp, modality)` and none shares it with production, so the known resume
trap of the coarse dedup (an interrupted batch silently skipping a second reconstruction of the same scan,
`ni_gnuclear_production_runbook.md` §4) cannot drop anything here.

### 1.4 What the fix releases among the other 573 held back (count only)

Re-running discovery on the whole snapshot with `main`'s and this branch's `analyse()` (`petct_05_fix_effect.py`, against
the registry and the DB code set) reproduces August exactly (1,639 skipped as registered, 673 held back) and gives, under
the fix:

| Of the 673 held back | Count | |
|---|---:|---|
| stream N's 100 | 100 | all released |
| **released and ingestable on a re-run** | **160** | `IAZ_MJ` `1121` 78 (FDG 2022-03/07/09, Altanserina), `IAZ_MJ` `1019` 16 (Procedimiento 2), `MJ` `0522` 59 (FTHA, FDG, Flurpiridaz 2024-06), `Marina` `1321` 7 |
| released, but another reconstruction of the same scan is registered | 20 | `Irene` `0324` 3, `Marina` `1321` 17: skipped by the `(timestamp, modality)` dedup, by design |
| still held back | 393 | no valid code anywhere above the subject folder |

Of the 160: **150** are DB-confirmed (animal in the recovered protocol, a procedure within 3 days); **10** parse no animal
(`Respiratory gated` ×6, `recongated` ×2, `FDK`, `NEW` subfolders) and would be registered with no subject, like the 7
production rows of that kind. List: `out\fix_released_others.csv`. **A path claim is not enough**: one of this stream's
own 100 shows it (the phantom, which its path files under `0619`/201). Releasing them needs the header check of §3 too.
**Until that decision, do not re-run the `ni_gnuclear_prod_*.yaml` configs** after this branch merges: they would now
ingest the 160.

---

## 2. Decision 2: what one acquisition is

**One acquisition per Molecubes reconstruction, PET and CT separate, `session_id` grouping the animal visit: production's
model, unchanged.**

- **Production.** All 1,648 NI rows (the 132 archive rows, the 1,508 backfilled, drives 1+2's 8) are one row per
  reconstruction; the 290 drive reconstructions already in production are registered that way.
- **What the DICOM says.** The Molecubes cubes write the PET and CT of one visit into **one DICOM Study** (a shared
  `StudyInstanceUID`): the 492 drive reconstructions form 256 Studies, 206 of them exactly one CT and one PET (the others:
  28 CT only, 7 PET only, 11 CT+CT+PT, 4 CT+PT+PT). That is the "one DICOM Study bundle" of 03 §3.3.
- **Production already honours that grouping at the session level.** Of the drive's Studies with at least two
  reconstructions in production (139), production's `session_id` groups exactly the Study's reconstructions in **137**;
  the 2 splits are two of the four known DICOM-vs-folder animal conflicts (BACKLOG, 2026-08-19: `ACQ-20221121-PET-006`,
  `ACQ-20241008-PET-002`). The plan does the same for the 202: 81 of 82 Studies get
  one `session_id`; the split is the conflict of §3.
- **Why nothing else is possible here.** Folding PET and CT into one row would register one `(timestamp, modality)`
  where the scanner wrote two, and a later run of the snapshot discovery would ingest the other reconstruction again.
- **03 §3.3's wording** ("keep the entire output together as one acquisition") does not describe the NI practice. That is a
  documentation question for the coordinator and Ryan; this stream follows production and changes no rule.

**The Molecubes companion files: confirmed non-raw, for stream P.** Production's NI acquisitions hold only the DICOM
(`<ACQ-ID>.data\recon<n>[_frame<f>].dcm`, plus `metadata.json`, `checksums.json`, `README.txt`: checked on 60 of the 1,648),
and the backfill pulled only `.dcm`. The 298 folders that hold a copy of the 202 contain 1,679 other files: 287
`reconparams.txt`, 283 `protocol.txt`, 134 `desktop.ini` (junk), and derivatives (360 `.nii` SUV maps, 213 `.xlsx`, 180
`.mat`, 138 `.gz`, 79 `.voi`). **Every non-junk one is in A2's placement plan** (place 610, deferred with `biomaGUNE MJ`
551, duplicate copies 352, covered by a twin 29, holding 3). Nothing raw is missed: the only other DICOM in those folders
are **PMOD exports** (below), which are derivatives.

⚠️ **A gap for the coordinator: 49 PMOD DICOM export files (31 distinct, 1.33 GB; 2.06 GB with the copies) are in no
stream's plan.** `m121-corregPETCTbody.dcm`,
`SUV 187`, `matrizcoreg`, `m48_PETCTbrain` and the like (co-registered or SUV-scaled volumes, `Manufacturer` PMOD). A1 owns
them as DICOM, so A2's placement plan leaves them out; they are derivatives, so this stream does not ingest them. List:
`a1\pet_files.csv`, `kind = pmod-export`. They belong to stream P (into their project folders).

---

## 3. Decision 3: subject ids and dates

**Dates.** `acquisition_datetime` is the file-name timestamp, as in the backfill. It equals the header's
`AcquisitionDateTime` (and `StudyDate`+`StudyTime`) for all 490 named reconstructions; for the two renamed files it is
taken from there.

**Subjects.** As the backfill did: the animal is the folder's (the shared grammar), the protocol the folder's code, and the
subject id `<animal>-AE-biomaGUNE-<protocol>` comes from the facility DB at ingest (`subject_from_db`). Each row was also
checked against the header (`PatientID`, the head of `SeriesDescription`, the protocol typed at the console) and the DB
(`petct_06_plan.py`, `out\plan_202.csv`). **201 of 201 animal rows: the animal is in the protocol and logs a procedure
within 3 days of the scan** (`PET CUBES-1`/`-2` on the day; `Admin RT +Pet` for the gated CTs). The case tables
(`cases_drive3_petct_*.csv`) carry every decided value explicitly, with a note where it is not the obvious one:

| Acquisition(s) | Folder / header | Decision |
|---|---|---|
| the 11 respiratory-gated CTs of `1123`, 2024-10-09 (`MJ/1123/241009/<n>/Gated/`) | subject folder `Gated`; header `PatientID 1123_<n>` | animal = the folder above (`<n>`), as the header says |
| `20211019091843_PET_OSEM_0`, folder `0619\Dieta cetogenica\173 FALTA` (*falta*, "missing": the folder holds no CT, and neither the snapshot nor production has one) | header `PatientID 173`, but protocol typed `1019` at the console | **`0619`/173**: the DB logs `PET CUBES-1` on 2021-10-19 for `0619`/173 and nothing in 2021 for `1019`/173 |
| `20220217093136_PET_OSEM_1`, folder `CAV1 Enero 2022\29` | header `PatientID 30`, in animal 30's DICOM Study | **the folder's 29**, noted. The DB logs a PET for both 29 and 30 that day, so it cannot break the tie; the folder keeps its `29/30` order and animal 30 has its own PET at 09:33. This is the BACKLOG item's pattern (a neighbour in the same session): **a fifth case for it** |
| `20220518123914_PET_OSEM_0`, folder `0619\BrEt PAH\220518\201` | header `PatientID 20ml`, `StudyDescription 18f phantom`, console user `unai` (the platform manager), weight 0.001 kg, 12:39 after the session | **not an animal**: `sample_type phantom`, `sample_id phantom_18F_20ml`, no project, no subject, researcher blank (stream F's precedent for MRI phantoms). A1 had counted it confirmed through its folder |
| `20231128121027_CT_ISRA_0` (`1422` animal 1) | console fields typed `234628` / `1422` | `1422`/1, as folder, `PatientID` and DB agree; noted |

`operator` stays blank, as in the backfill (REVIEW_FINDINGS_2026-08-13 §5.3); the console user the header records is in
each row's notes (irati 189, mjesus 11, garazi 1, unai 1).

---

## 4. The code change

| File | Change |
|---|---|
| `tools/ni_gnuclear_discover.py` | `analyse()`: when the parser found **no** code and the DB code set is given, walk up whole segments for the first valid code, **only over the levels between the researcher folder and the subject folder** (an animal number must never become a protocol; the year, group and researcher levels are never protocols); phantoms stay without a project; the flag is `project-recovered:none-><code>`. `subject_index()` is factored out of `find_subject()` so the walk is computed once; `find_subject()` returns the same values. |
| `tools/ingest/ni_flat.py` | prints the found-higher count apart from the wrong-code recoveries (message only). |
| `tools/templates/instruments/molecubes_ni_gnuclear.yaml` | comment only: the template that exercises the walk-up now describes the fallback and what it releases. |
| `tools/test_ni_flat.py` | 17 new checks (31 → 48): the fallback, the flag, the facility keys, no recovery without the DB code set, `Gated`, an animal folder `1019` never taken as protocol `1019`, the walk starting above the subject folder, the researcher level, phantoms, no valid code → still held back, the wrong-code walk-up unchanged, `discover()` publishing the recovered code and skipping it once registered, `find_subject()` unchanged. |

- **Regression, measured:** `main`'s and this branch's `analyse()` over all 2,485 snapshot files: **0 field differences**
  outside the released acquisitions, whose only changes are `project`, `flags` (`+project-recovered:none->…`) and
  `facility_keys`.
- **Mutation test** (`petct_11_mutation_test.py`): no fallback; the walk including the subject folder; the walk including
  the year/group/researcher levels; phantoms recovered: **4 of 4 killed**, the file restored byte-for-byte.
- **Suite:** `run_all_tests.py` on the branch's final state: **38/38 suites pass in 36 s** (`main`: 38/38).

---

## 5. Dry runs against live production

Every dry run ran against `J:\gjesus3-data` (the registry of 27,120 rows, which includes the 86 AxioScan acquisitions MBC
ingested at 11:03–11:21 today), with the registries fingerprinted (size, mtime, SHA-256) before and after: **byte-identical
every time.** The coordinator's 10:30 SHA index (which predates those 86) was not used for any dry run or proof. The
validator on production today (read-only, `--no-enrichment`): **27,120 rows, 0 errors, 0 warnings, `pending-claim`
10,314**, none of the 202 present: the baseline step 0 of §7 expects.

| Config | Total / success / failed | Discovery | Checked against the plan (`petct_13_check_log.py`) |
|---|---|---|---|
| `drive3_petct_snapshot.yaml` (N-S) | **100 / 100 / 0** | 2,485 files; 349 skipped as registered (`IAZ_MJ` 133 + `MJ` 216); 253 found by the fallback, of which 153 dropped by the case table | 100 of 100 cases: instrument, date, ACQ-ID prefix, project link; 0 disagreements; 99 links free, the phantom none |
| `drive3_petct_drive.yaml` (N-D) | **102 / 102 / 0** | 102 files, 102 cases | 102 of 102, 0 disagreements; 102 links free |
| `drive3_petct_dedup_proof.yaml` | 0 / 0 / 0 | 290 files, **290 skipped** as registered | — |
| `drive3_petct_census.yaml` | 202 / 202 / 0 | 492 files, 290 skipped, **202 listed = the plan's keys** | — |
| `ni_gnuclear_prod_*.yaml` ×7 (fixed code) | 260 / 260 / 0 | `IAZ_MJ` 183, `MJ` 70, `Marina` 7, others 0 | = the 100 + the 160 of §1.4 |

The link pre-flight read production's `raw_linked\` folders: all 201 names are free. Logs: `out\dryrun_prod_*.log`;
fingerprints: `out\bracket_prod_*.json`. The census and the dedup proof are dry-run tools only. The census sets no project
and no subject, so it carries a guard: its `copy_strategy` does not exist, which a dry run never reaches and a real run
fails on for every case before any file is copied or any row written. The dedup proof, run for real, would find nothing
to do.

---

## 6. Rehearsal

**The root.** `D:\projects\gjesus3\drive3_streams\petct\rehearsal_nas\`, built at 13:24 by `petct_14_rehearsal_setup.py`:
production's registry files, byte-identical to the state every production dry run saw (`registry_raw.csv` 27,120 rows,
SHA-256 `633bb7ac…`); the five target projects with their `_project.yaml` and `provenance.csv`; an empty `raw\`. Each
project's `raw_linked\` starts empty (production's own was checked by the dry runs' link pre-flight). Hard links on NTFS
behave as on the NAS (which has used them since 2026-06-02), and no path the ingest opens or creates exceeds 180
characters (`petct_20_path_lengths.py`), so no SMB behaviour needed `J:\gjesus3-sandbox`.

**The run** (`petct_15_rehearse.py first`: the production commands with the rehearsal root as `--nas-root`):

| Batch | Total / success / failed | Done in the run | Time | Subjects table |
|---|---|---|---|---|
| N-S (snapshot) | **100 / 100 / 0** | 99 DB-sourced subjects, 99 link folders, 99 provenance rows; the phantom with neither | 1 min 44 s | 11 new, 88 already there |
| N-D (drive) | **102 / 102 / 0** | 102 DB-sourced subjects, 102 link folders, 102 provenance rows | 21 min (`D:` was busy with stream C's copies) | 27 new, 75 already there |

The only warning, on each of the 201 animal rows: `condition.is_control is null`, the documented unknown sentinel that
every backfilled NI row carries too.

**The ACQ-IDs** (production allocates the same if no other NI row lands on these dates first): 28 date/modality runs, each
from `-001`, except `ACQ-20241009-CT-014…024` (production already holds 13 CTs of that day):
`ACQ-20210322-CT/PET-001…016`, `ACQ-20210601-CT/PET-001…007`, `ACQ-20210727-CT/PET-001…004`,
`ACQ-20210728-CT/PET-001…004`, `ACQ-20210928-CT/PET-001…008`, `ACQ-20211019-CT-001…003`, `ACQ-20211019-PET-001…004`,
`ACQ-20211020-CT/PET-001…005`, `ACQ-20220125-CT/PET-001…008`, `ACQ-20220217-CT-001…007`, `ACQ-20220217-PET-001…008`,
`ACQ-20220518-CT-001…006`, `ACQ-20220518-PET-001…007` (the phantom is `-007`), `ACQ-20220524-CT/PET-001…006`,
`ACQ-20220927-CT/PET-001…008`, `ACQ-20231005-CT/PET-001…002`, `ACQ-20231128-CT-001…020`, `ACQ-20241009-CT-014…024`.

**Independent verification** (`petct_16_verify.py` against the pre-write baseline): **18 of 18 PASS.**

| Check | Result |
|---|---|
| R1 | `registry_raw.csv` 27,120 → 27,322, the old bytes an exact prefix; the new rows are exactly the plan's 202 keys |
| R2 | every new row equals the plan: 0 disagreements |
| R3 | no duplicate `acq_id`, `(date, original_name)`, or new NI `(timestamp, modality)` (NI rows 1,648 → 1,850) |
| F1 | every acquisition folder exactly as specified; each of the 202 DICOMs re-hashed equal to its `checksums.json`, to the drive manifest for **every** drive copy, and (the 100) to the snapshot manifest |
| S1 | sidecars: the project, the DB-sourced subject, whole-body; the phantom with no subject or anatomy |
| L1 | 201 link folders (`0619` 121, `0320` 29, `1422` 24, `1019` 16, `1123` 11), each file `os.path.samefile` with `/raw/`; `raw_linked\` gained exactly these |
| P1 | each project's `provenance.csv` append-only, one row per link |
| T1 | `registry_subjects.csv` 1,300 → 1,338: the rows' 117 subject ids each once (79 were there already, 38 new); `pending_subject_metadata.csv` unchanged (no DB miss) |
| M1 | `ingest_manifest.csv` +202, append-only |
| O1 | `registry_projects`, `retired_acquisitions`, `registry_datasets`, `pending_dicom_regen` byte-identical |

**The validator** (`petct_19_validate_classify.py`): 27,322 rows; 27,120 errors, all of one expected class (production's
rows, whose `/raw/` folders the rehearsal root does not hold); **0 errors and 0 warnings on the 202** with
`--no-enrichment`; the full run adds only the 201 `condition` sentinels; `pending-claim` 10,314, unchanged.

**The idempotent re-run** (`petct_15_rehearse.py rerun`): N-S **Total 0** (449 skipped as registered, the 153 others
dropped by the case table), N-D **Total 0** (102 skipped as registered).

**After the write**, against the rehearsal root: the census lists **0** (492 skipped), the dedup proof **0**, and the
snapshot backfill re-run **only the 160 others** (§1.3).

**Production untouched:** `J:\gjesus3-data\registries\` fingerprinted before and after each rehearsal run, byte-identical;
the 100 snapshot source files unchanged (size, mtime). Logs: `out\rehearsal_*.log`, `out\post_rehearsal.txt`,
`out\validate_reh_*.txt`.

---

## 7. Production: commands, verification, backup, rollback

**Who and when.** Ryan's go after the coordinator's gate; the coordinator opens the write window (one registry writer at a
time) and runs or supervises it. From the `main` working copy once `feat/drive3-petct` is merged, in Git Bash, with
`export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tools`. About 30–45 minutes in all: 8 GB are read, written over SMB and read
back, and the drive batch reads `D:`, which other streams were saturating during the rehearsal (N-D took 21 minutes there).
Stream P's copies into the same five projects may run beside it (copy-only, disjoint folders), but if they add
`provenance.csv` rows to those projects in the window, P1 reports the excess: look at its rows' `input_refs`.

```bash
cd "/c/Users/rtasseff/OneDrive - CIC biomaGUNE/projects/DataInfra/gjesus3-archive/gjesus3-pilot"
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tools
D=$(date +%Y%m%d)
BK="C:/Users/rtasseff/temp/gjesus3_registry_backup_${D}_pre_drive3_petct"     # fresh, dated; never re-use

# 0. Pre-flight, read-only. Stop on any difference.
python tools/validate_registries.py --nas-root "J:/gjesus3-data" --no-enrichment
#    expect: 0 errors, 0 warnings, "operator awaiting claim (pending-claim): 10314"
python tools/drive_staging/drive3/petct_07_stage.py
#    expect: "kept" for all 492 (each staged file re-hashed against the drive manifest)
python tools/drive_staging/drive3/petct_12_dryruns.py "J:/gjesus3-data" pre \
    tools/configs/drive3_petct/drive3_petct_snapshot.yaml tools/configs/drive3_petct/drive3_petct_drive.yaml \
    tools/configs/drive3_petct/drive3_petct_census.yaml
#    expect: 100/100/0, 102/102/0, census 202 listed + 290 skipped; "registries changed=False" each
python tools/drive_staging/drive3/petct_13_check_log.py "D:/projects/gjesus3/drive3_streams/petct/out/dryrun_pre_drive3_petct_snapshot.log" snapshot
python tools/drive_staging/drive3/petct_13_check_log.py "D:/projects/gjesus3/drive3_streams/petct/out/dryrun_pre_drive3_petct_drive.log" drive
#    expect: cases 100 of 100 / 102 of 102, missing 0, disagreements 0

# 1. Backup: every registry file, the five projects' provenance.csv and their raw_linked listings, each re-hashed.
python tools/drive_staging/drive3/petct_17_backup.py "J:/gjesus3-data" "$BK"

# 2. The write (confirm --nas-root on every line).
python tools/ingest_raw.py --config tools/configs/drive3_petct/drive3_petct_snapshot.yaml --nas-root "J:/gjesus3-data" \
    --refresh-index projects > "$BK/run_snapshot.log" 2>&1
tail -8 "$BK/run_snapshot.log"        # BATCH SUMMARY: Total 100, Success 100, Failed 0
python tools/ingest_raw.py --config tools/configs/drive3_petct/drive3_petct_drive.yaml --nas-root "J:/gjesus3-data" \
    --refresh-index projects > "$BK/run_drive.log" 2>&1
tail -8 "$BK/run_drive.log"           # BATCH SUMMARY: Total 102, Success 102, Failed 0

# 3. Verify (independent of the ingest's own checks).
python tools/drive_staging/drive3/petct_16_verify.py "J:/gjesus3-data" "$BK"
#    expect: every check PASS (the list below)
python tools/validate_registries.py --nas-root "J:/gjesus3-data" --no-enrichment
#    expect: unchanged from step 0 (0 errors, 0 warnings, the same pending-claim line)
python tools/ingest_raw.py --config tools/configs/drive3_petct/drive3_petct_snapshot.yaml --nas-root "J:/gjesus3-data" > "$BK/rerun_snapshot.log" 2>&1
python tools/ingest_raw.py --config tools/configs/drive3_petct/drive3_petct_drive.yaml --nas-root "J:/gjesus3-data" > "$BK/rerun_drive.log" 2>&1
grep "Total:" "$BK"/rerun_*.log          # Total: 0, twice (idempotent)
python tools/drive_staging/drive3/petct_12_dryruns.py "J:/gjesus3-data" post \
    tools/configs/drive3_petct/drive3_petct_census.yaml tools/configs/drive3_petct/drive3_petct_dedup_proof.yaml \
    tools/configs/ni_gnuclear_prod_IAZ_MJ.yaml tools/configs/ni_gnuclear_prod_MJ.yaml tools/configs/ni_gnuclear_prod_Marina.yaml
#    expect: census 0 listed (492 skipped); dedup proof 0; backfill IAZ_MJ 94, MJ 59, Marina 7 listed (only the
#    160 others of §1.4); the 100 now skipped as registered. Dry runs only: do NOT run the backfill configs for real.
```

**`petct_16_verify.py` checks** (each PASS/FAIL, from the backup as the baseline): R1 `registry_raw.csv` append-only and
exactly +202 rows, the plan's keys; R2 every new row equal to the plan (instrument, datetime, researcher, operator blank,
sample, subject id, session, project, `.data` primary, file count 1, checksum flag, config, notes); R3 no duplicate
`acq_id`, `(date, original_name)` or NI `(timestamp, modality)`; F1 each acquisition folder holds exactly `metadata.json`,
`checksums.json`, `README.txt` and `<ACQ-ID>.data\` with the one expected DICOM, whose SHA-256 **re-hashed now equals
`checksums.json`, the drive manifest for every drive copy, and (for the 100) the snapshot manifest**; S1 sidecars
(project, DB-sourced subject, whole-body; the phantom bare); L1 one hard-link folder per animal acquisition
(`os.path.samefile` with `/raw/`), `raw_linked\` gaining exactly those and losing nothing; P1 `provenance.csv` append-only,
one row per link; T1 every new subject id once in `registry_subjects.csv`, `pending_subject_metadata.csv` unchanged; M1
`ingest_manifest.csv` +202, append-only; O1 `registry_projects`, `retired_acquisitions`, `registry_datasets`,
`pending_dicom_regen` byte-identical.

**Stop conditions** (stop, do not start the next step, report): `Failed` > 0 or a total other than 100 / 102; any verify
FAIL; a validator change; a re-run that adds anything; the census listing anything; the animal DB unreachable
(`pending_subject_metadata.csv` grows).

**If it stops half-way.** Each acquisition commits on its own (the registry append is the commit point; a failure before
it removes that acquisition's partial folder). Fix the cause and **re-run the same command**: the dedup skips what is
committed. The resume trap of the coarse dedup cannot bite (no shared `(timestamp, modality)`, §1.3). Then run step 3 in
full.

**Rolling back** (the drives' rule: no delete tool; a Data-Office manual, backup-first operation). The rows are exactly
those whose `ingest_config` is `tools/configs/drive3_petct/drive3_petct_snapshot.yaml` or `…_drive.yaml`.

| # | Side effect | Reverse by |
|---|---|---|
| 1 | `raw\DICOM\<YYYY>\<YYYY-MM>\<ACQ-ID>\` per row | delete each folder (the row's `canonical_path`) |
| 2 | `registries\.acq_id_seq.json` high-water | leave it (ids are never reused; the gap is by design) |
| 3 | `registry_raw.csv` rows | if no other writer touched it since (rows = backup + written), restore the backup copy; else remove the rows byte-exact (keep line endings) |
| 4 | `ingest_manifest.csv` rows | the same rule |
| 5 | `registry_subjects.csv` upserts | remove only the subjects new in this write (diff against the backup) |
| 6 | `pending_subject_metadata.csv` | only on a DB miss (none expected) |
| 7 | `projects\<name>\raw_linked\<link name>\` | delete them (the plan's link names; the backup's listing shows what was there before) |
| 8 | `projects\<name>\provenance.csv` rows (`input_refs` = the ACQ-ID) | restore the backup copy under the same no-other-writer rule, else remove the rows |
| 9 | `projects\<name>\index.html` | `python tools/generate_index.py --nas-root "J:/gjesus3-data" --project <PROJ-ID>` |

Then `petct_16_verify.py` (every row now missing), the validator (the baseline), and the same commands again once fixed.

**Records after the write** (the coordinator's, at merge): STATUS §2 (the M. Jesús drive), CHANGELOG, and the close-out's
manifest check (`drive3_production_plan.md`, "Close-out" 1): `petct_16_verify.py`'s F1 already compares every ingested
file with the drive manifest.

---

## 8. What I could not settle, and what the coordinator should decide

| # | Item | Recommendation |
|---|---|---|
| **N-a** | **The phantom** (`20220518123914_PET_OSEM_0`): the platform's 18F QC scan, filed in animal 201's folder. | Register it as built: `sample_type phantom`, no project, no subject (stream F's precedent for the MRI phantoms; it is raw, and filed with MFB data). **Alternative:** leave it out by deleting its row from `cases_drive3_petct_snapshot.csv` (`on_missing: skip` then drops it); the totals become 201. |
| **N-b** | **The 160 others the fix releases** (§1.4) | A separate decision (Ryan): the D-G mapping is no longer needed for them, but each needs the header check of §3 before it is ingested; 10 need a subject mapping. Until then, do not re-run the backfill configs for real. |
| **N-c** | **49 PMOD DICOM export files (31 distinct, 1.33 GB)** in no stream's plan (§2) | Add them to stream P as derivatives, into their project folders. |
| **N-d** | **CAV1 29/30** (§3) | Add it to the BACKLOG item "4 PET acquisitions where the DICOM PatientID contradicts the registry" as a fifth case, after the write. |
| **N-e** | **03 §3.3** says a hybrid PET/CT is one acquisition; NI practice is one row per reconstruction, grouped by `session_id` (§2) | A documentation question for Ryan; no rule is changed here. |
| **N-f** | **Project dates.** The ingest does not recompute `start_date`/`last_activity`; acquisitions here predate the recorded `start_date` of `0619` (2022-01-26; ours from 2021-03-22), `0320` (2022-02-14; ours from 2021-06-01) and `1422` (2023-11-08; ours from 2023-10-05). | The existing BACKLOG item (project-date recompute) covers it. |
| **N-g** | **`researcher = MJ`** for the drive rows is an inference (her drive; her `S:\gnuclear` folder `MJ`; console user `mjesus` in 2024). | Accept, or name another token before the write (one column of the drive case table). |

**Space on `D:`** (`D:\projects\gjesus3\drive3_streams\petct\`, about 28 GB): `stage\new102\` (4.82 GB) is the source of
the drive batch and stays until the write is verified; `stage\inprod290\`, `stage\snaponly100\` and `stage\all492\`
(hard links) exist for the proofs, and `rehearsal_nas\` (8 GB) for the rehearsal; all can go after the write.

---

## 9. Proposed record lines (the coordinator applies them at merge; I edited none)

- **STATUS §2, the M. Jesús drive, stream N:** "Built, dry-run and rehearsed on `feat/drive3-petct`: 202 PET/CT acquisitions
  production lacks (100 from the `S:\gnuclear` snapshot through the fixed discovery, 102 from the drive), 8.03 GB, into
  `0619`, `0320`, `1422`, `1019`, `1123`; 201 animals DB-confirmed and one platform phantom. Waiting on the gate and Ryan's
  go. Gate: `tasks/drive3_petct_gate.md`."
- **BACKLOG, 🔸 "the `S:\gnuclear` discovery gives up on a path whose first parse finds no code":** first box done on the
  branch (fallback + 17 checks; it releases 160 more of the 673, 20 go to the timestamp skip, 393 stay held back); second
  box at the write. New items from §8: N-b (the 160), N-c (the 49 PMOD exports, for stream P), N-d (the fifth
  PatientID case), N-e (03 §3.3's wording).
- **CHANGELOG** at the write, with the ACQ-ID ranges the write actually takes.

---

## 10. Reproducing every number

All under `D:\projects\gjesus3\drive3_streams\petct\`; read-only on `J:` (the facility DB: `SELECT` only); run with
`PYTHONDONTWRITEBYTECODE=1` from `tools\drive_staging\drive3\`.

| Script | What it does | Output (`out\` unless said) |
|---|---|---|
| `petct_01_snapshot_inputs.py` | dated copies of the live registries and the snapshot manifest, each SHA-256'd twice | `_inputs\<stamp>\` |
| `petct_02_inventory.py` | A1's 909 PET files → 492 acquisition keys; coverage cross-checked by name and time on the live registry | `acq_inventory.csv` |
| `petct_03_headers.py`, `petct_04_header_check.py` | the header facts of all 492; headers against names | `acq_headers.csv`, `acq_header_check.csv` |
| `petct_05_fix_effect.py` | `main` vs this branch's `analyse()` over the whole snapshot; the release, DB-checked | `fix_effect_acqs.csv`, `fix_released_others.csv` |
| `petct_06a_db_probe.py`, `petct_06_plan.py` | the DB probes of §3; the per-acquisition plan with its evidence | `plan_202.csv`, `plan_stage_all.csv` |
| `petct_07_stage.py`, `petct_07b_verify_snapshot.py` | the staged copies (verified); the 100 snapshot files re-hashed | `stage\`, `snapshot_100_rehash.csv` |
| `petct_08_companions.py`, `petct_18_hybrid.py` | the files beside the 202; DICOM Studies against `session_id` | `companions_202.csv` |
| `petct_09_case_tables.py` | the two case tables, from the plan | `tools\configs\drive3_petct\cases_*.csv` |
| `petct_10_bracket.py`, `petct_12_dryruns.py`, `petct_13_check_log.py` | fingerprints; dry runs; a log checked case by case | `bracket_*.json`, `dryrun_*.log` |
| `petct_11_mutation_test.py` | the four mutants | — |
| `petct_14_rehearsal_setup.py`, `petct_15_rehearse.py`, `petct_16_verify.py`, `petct_17_backup.py` | the rehearsal root; the rehearsal; the verifier; the backup | `rehearsal_nas\`, `rehearsal_*.log` |
| `petct_19_validate_classify.py`, `petct_20_path_lengths.py`, `petct_21_acq_ranges.py` | the validator's findings by class; the longest paths; the ACQ-IDs given | `validate_*.txt` |
| `petct_22_post_rehearsal.py` | verifier, validator, ranges, re-run and the post-write dry runs, in order | `post_rehearsal.txt` |
