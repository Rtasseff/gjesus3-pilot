# The MRI platform's archive: the ingest of MFB's new studies (stream AR, gate document)

**Status:** 🔶 BUILT, DRY-RUN AND REHEARSED **for the 422 studies local on 2026-10-08**, for the coordinator's gate and
then Ryan's go. **Nothing was written to production.** The other 228 studies arrive by Fri 07:45 (§9 finishes them).
**Date:** 2026-10-08 · **Branch:** `feat/mri-archive-ingest` (worktree `gjesus3-dev\mri-archive-ingest`)
**Rulings:** STATUS §0.5 "Hold" (`operator = pending-claim`), §0.6 Q1–Q7 · **Census:** [`mri_archive_census.md`](mri_archive_census.md)
**Repeats:** stream M ([`drive3_mri_gate.md`](drive3_mri_gate.md)) for another source · **Part 1:** [`drive3_mri_archive_check.md`](drive3_mri_archive_check.md)
**Scripts:** [`tools/drive_staging/mri_archive/ar_*.py`](../tools/drive_staging/mri_archive/) · **Configs:** [`tools/configs/mri_archive/`](../tools/configs/mri_archive/)
**Outputs, extract tree, rehearsal (regenerable, not backed up):** `D:\projects\gjesus3\mri_archive\` (`out\`, `extract\`, `rehearsal_nas\`); the tarballs in `pull\` are never modified
**Units:** GB = 10⁹ bytes. "Exam" = one ParaVision examination folder = one production MRI acquisition.

---

## Summary

1. **The 650 new MFB studies (tiers A 561, A2 12, B 77) are planned in 14 batches; 422 of them (120.1 GB of archives) are
   local, extracted, converted, dry-run against live production and rehearsed.** The other 228 (42.7 GB: A 179, A2 12,
   B 37) arrive by Friday 07:45 and go through the same scripts (§9); the numbers below are for the 422.

   | Batch | Project | Studies (local / all) | Exams: scanner + Dicomifier | GB | Subject ids | Note |
   |---|---|---:|---:|---:|---:|---|
   | AR01_0118 | `AE-biomaGUNE-0118` | 35 / 41 | 451 + 47 = **498** | 0.58 | 26 rats | 5 by code, 36 by the DB (no code: `monocr`, `2DG`, `controlR47`, Ermal's `_ermal`) |
   | AR02_0219 | `AE-biomaGUNE-0219` | 19 / 35 | 101 + 0 = **101** | 0.46 | 8 | |
   | AR02n_0219 | `AE-biomaGUNE-0219` | 1 / 1 | 6 + 0 = **6** | 0.04 | none | `m8b` (no plain animal number) |
   | AR03_0220 | `AE-biomaGUNE-0220` ⚠️ closed | 0 / 3 | — | — | — | **the coordinator reopens the project first (Q5)**; Friday |
   | AR04_0320 | `AE-biomaGUNE-0320` | 17 / 19 | 230 + 94 = **324** | 0.44 | 15 | |
   | AR04n_0320 | `AE-biomaGUNE-0320` | 3 / 3 | 35 + 19 = **54** | 0.07 | none | `m1a`, `m8b`, `m11b` |
   | AR05_0618 | `AE-biomaGUNE-0618` | 21 / 74 | 256 + 22 = **278** | 0.31 | 21 | 6 A2 `_post` sessions on Friday; 3 by the DB (`apoe` 2019) |
   | AR05n_0618 | `AE-biomaGUNE-0618` | 1 / 1 | 13 + 0 = **13** | 0.03 | none | `jrc190514_0618ApoE1` |
   | AR06_0619 | `AE-biomaGUNE-0619` | 27 / 27 | 397 + 63 = **460** | 0.47 | 24 | 18 by the DB (`hypx`, 2020-01) |
   | AR07_0721 | `AE-biomaGUNE-0721` | 0 / 10 | — | — | — | 6 A2 `postadm`/`post`; Friday |
   | AR08_1019 | `AE-biomaGUNE-1019` | 62 / 135 | 644 + 148 = **792** | 1.73 | 48 | 13 by the DB (`london`, 2021-01) |
   | AR09_1116 | `AE-biomaGUNE-1116` | 60 / 80 | 686 + 215 = **901** | 1.92 | 40 | **57 by the DB** (`cnd`/`CND`, `lungHugo`, `m179_flow`, `Mndoped`) |
   | AR09n_1116 | `AE-biomaGUNE-1116` | 0 / 6 | — | — | — | `m200`, `m201`, `m242`–`m245`: not in the DB under 1116; Friday |
   | AR10_1319 | `AE-biomaGUNE-1319` | 5 / 5 | 0 + 40 = **40** | 0.08 | 5 | |
   | AR11_1321 | `AE-biomaGUNE-1321` | 0 / 1 | — | — | — | `jrc220622_m6_132` (the DB: 1321); Friday |
   | AR12_1519 | `AE-biomaGUNE-1519` | 89 / 89 | 1,339 + 0 = **1,339** | 2.04 | 25 | |
   | AR13_noproject | **none** | 40 / 41 | 275 + 80 = **355** | 0.93 | none | Q4 (`0917` ×4, `0116`, `1316`); no code and no unique DB answer (30 + 4); DB contradicts the claim (1) |
   | AR14_phantoms | **none** | 40 / 77 | 115 + 255 = **370** | 0.33 | none | Q2: phantoms / QC, as July's |
   | **Total today** | 12 projects + none | **422 / 650** | **4,548 + 983 = 5,531** | **9.41** | **212** (161 new) | 152,573 DICOM files, 404 sessions |

2. **Every exam registered has DICOM** (Ryan's 2026-10-04 rule): 4,548 the scanner's own, **983 made by Dicomifier
   before ingest** in the extract tree (990 tried; **7 failed**: not registered, listed). **Not registered: 173 exams** (117
   never acquired, 38 spectroscopy, 10 k-space without reconstruction, 7 failed conversions, 1 incomplete: a short archive),
   plus 5 `2dseq`-only reconstructions beside registered DICOM; all listed for a placement batch (plan only, §8).
3. **Fields as stream M, with the Hold:** `operator = pending-claim` (5,531 of 5,531 in the rehearsal), `researcher`
   blank, `original_name = <study>/<exam>`, dated by `VisuCreationDate` (5,531 of 5,531; equal to `ACQ_time`'s day for all
   but 2 exams of the whole inventory), the archive path and its SHA-1 in the notes. Link names use the 2026-10-05 form
   `MRI_<sample>_<YYYYMMDD>_<HHMM>_<exam>_<recons>`.
4. **Subject ids: 212 animals looked up in the facility DB now, 212 found, 0 `-None`** (0118 and 1116 hold a NULL alias;
   the caller's alias is used), none born after its first scan; 4 scan days with no logged procedure, all CLAIM-KEPT.
5. **Dedup proven against live production, five ways** (§4): 0 names; 0 sessions on the same day; **0 of 152,573 DICOM
   files in production by SHA-256** (against all 627,841 MRI/XMRI DICOM hashes production holds); the dedup proof (the 130
   stream-M studies extracted from the archive and dated the same way: **2,339 skipped as registered, 0 listed**; `m175`,
   `m178` included); and every dry run lists exactly its case table.
6. **Dry runs against production (14 batches): 5,531 listed = the case tables, 0 failed, 0 disagreements, 4,806 links
   free, 0 dated 2026, registries byte-identical before and after each.**
7. **Rehearsal** into a D: root built from production: **5,531 / 5,531 / 0 in 45 minutes; the independent verifier 18/18
   PASS** (all 152,573 DICOM re-hashed == `checksums.json` == the extracted file, and for the scanner's DICOM == the hash
   taken from the SHA-1-verified tarball); the validator: **0 findings on the new rows**, `pending-claim` 15,963 → 21,494
   (+5,531); **the re-run adds 0**; the dedup proof unchanged after the write; the claim workbook preview appends
   **404 sessions / 5,531 acquisitions**, every existing cell unchanged.
8. **Two decisions for the coordinator** (§10): the DB-resolved projects of the no-code studies (128 studies, 57 of them
   to `1116`), and claimed-but-not-in-the-DB studies kept in their project without a subject id (as M09).

---

## 1. Source: local copies only

- **Pulled** by `tools/mri_archive.py fetch` (not run here) to `D:\projects\gjesus3\mri_archive\pull\<year>\`; each
  verified against its `.sha1`. **552 of 780 local at 07:36 today** (A 382, B 40, C 130); the archive was never contacted
  by this work.
- **Extracted** (`ar_01_extract.py`, 12 workers, 45 min): each tarball read once as a stream; its SHA-1 recomputed in the
  same pass and **equal to the fetch manifest's for all 552**; every member checked by `tarfile.data_filter` and confined to
  `<study>/`; **k-space (`fid`, `ser`, `rawdata.job*`) not extracted** (listed with its size: the ingest keeps DICOM, and
  conversion needs `2dseq` and the parameter files); every extracted file's SHA-256 recorded
  (`extract\_manifests\<study>.csv`). The 552 tarballs (176.1 GB) gave **56.0 GB on `D:`**; the k-space left in the tarballs is 292.0 GB.
- **Two archive tarballs are short** (Part 1 finding 2): `20200615_115642_jrc200615_m21_1019_1_1` (tier C) and
  `20200302_143910_jrc200302_m3r7f2_Caff_1_1` (tier A, AR13). Their `.sha1` matches the short file: the archive was
  written short. Salvaged up to the cut; the exam being read (`m3r7f2_Caff/4`) is not registered (incomplete).
- **Layout:** `extract\C\<study>\` (the 130 stream-M studies: Part 1 and the dedup proof), and `extract\<batch>\<study>\`
  for the new ones (sorted by `ar_05_plan.py --sort`), so `original_name = <study>/<exam>` and each batch has its own
  `staging_dir`.

## 2. Decisions per study

### 2.1 Projects (`ar_04_db_evidence.py`, `ar_05_plan.py`)

The facility DB (SELECT only, one query per animal number) gives every protocol holding an animal of that number, its
species, birth date and logged procedures. **A check confirms a claim and never overrules it** (stream M, A1):

| Case | Studies (of 650) | Project | Subject id |
|---|---:|---|---|
| Code in the name, a gjesus3 project, animal CONFIRMED (procedure within 3 days) | 383 | the code's | yes |
| … CLAIM-KEPT (the animal is there, nothing logged within 3 days) | 8 | the code's | yes |
| … NOT-IN-DB (`1116`: `m200`, `m201`, `m242`–`m245`) | 6 | the code's | **no** (as M09) |
| … no plain animal number (`m8b`, `m1a`, `m11b`, `m7e`, `m7f`, `0618ApoE1`) | 7 | the code's | **no** (as M09) |
| … CONTRADICTED (`jrc211215_m74_0619_fat`: 0619's m74 born or dead against the scan) | 1 | **none** | no (as M08) |
| Code that is no gjesus3 project (Q4): `0917` ×4 (CONFIRMED in the DB), `0116`, `1316` | 6 | **none** | no |
| **No code; the DB answers uniquely** (one protocol holds the animal, alive, with MRI logged within 3 days, and it is a gjesus3 project): `1116` 57, `0118` 36, `0619` 18, `1019` 13, `0618` 3, `1321` 1 | **128** | **that protocol's** | yes |
| No code; the DB does not answer uniquely (0 or ≥ 2 protocols, or the one is not a gjesus3 project: `0614` `IONP_RGD` ×8, `0917` `LPS` ×6) | 30 | **none** | no |
| No code; no animal number (`m2r7f2_Caff` …) | 4 | **none** | no |
| Tier B, phantoms / QC (Q2) | 77 | **none** | no |
| **Total** | **650** | 532 with a project, 118 without | |

- **The no-code resolutions are consistent by series:** every `monocr`, `2DG` rat and `_ermal` study goes to `0118`;
  every `cnd`/`CND`, `lungHugo`, `m179_flow` to `1116`; every `hypx` to `0619`; every `london` to `1019`. The DB rejected
  the ambiguous ones (e.g. `m16_hypx`: 0518 and 0619 both log MRI that day) and one whose animal it records as perfused
  before the scan (`r79_2_DG`). DB placeholder dates (1970-01-01) are ignored.
- **`0220`** (3 studies, CONFIRMED) is **closed** today: its batch AR03 runs only after the coordinator reopens it (§7 step 5).
- **The A2 second sessions** (12, Friday) go to their projects (`0618` ×6 into AR05, `0721` ×6 into AR07) with their own
  `HHMM` link names.

### 2.2 Fields (case tables `tools/configs/mri_archive/cases_<batch>.csv`, from `ar_07_cases.py`)

| Field | Value |
|---|---|
| `acquisition_datetime` | exam `visu_pars` `VisuCreationDate` (production's rule), else `acqp` `ACQ_time`: **all 5,531 from `VisuCreationDate`**. 540 exams are dated on a later day than their study's name (multi-day studies that reuse one study folder: e.g. `m169_cnd` 2019-08-06/07/08/12); `VisuCreationDate` and `ACQ_time` agree on each |
| `instrument_model` | `Bruker BioSpec 7T` (every station `Biospec 70/30`; the archive is the 7 T's), set explicitly |
| `sample_id` | `<m/r><animal>_<code>` as production (`r47_0118`); no project: `<m/r><animal>` (`m16`); no animal: the study's core name; phantoms: the core name (`jrc190327_MOLLI_test`), as July's |
| `sample_type` | `organism`; tier B `phantom` (321), `tissue` (`exvivoAorta`, 14), `organism` where the name holds an animal (`m38_pruebaGalbumin`, `m3prueba`, …: 35) |
| `subject_ids` | the facility DB, `<animal>-AE-biomaGUNE-<code>` (subject batches only; `subject_from_db: false` elsewhere) |
| `session_id` | production's `jrc_id` where the animal-first regex parses; else the study name without date prefix and `_1_1` |
| `researcher`, `operator` | blank, **`pending-claim`** (the Hold rule) |
| `notes` | sequence, exam, recons; the animal and its DB verdict (or why no project); `MRI platform archive backup_7T_olddata_260824/<year>/<file> (SHA-1 …)`; how the DICOM was made; "operator pending claim" |
| link name | `MRI_<sample>_<YYYYMMDD>_<HHMM>_<exam>_<every pdata idx>`: **4,806 names, 0 duplicated, 0 taken in production** |

### 2.3 Convert-first (`tools/drive_staging/convert_staged_exams.py`, Dicomifier 2.5.3, WSL `dicomifier-pilot`)

Run on the extract tree (never `pull\`; script `out\convert_run.sh`): **983 of 990 converted**; failed (Dicomifier produced
no DICOM): AR14 4, AR02/AR02n 1 each, AR09 1. Results `out\convert_<batch>.csv`. The 15 scanner exams with some
reconstructions `2dseq`-only are registered with their DICOM reconstructions; the others are listed (as stream M §3.2).

## 3. Exams

**Inventory** (`ar_02_inventory.py`, all 552 local studies): 8,073 exams. Tiers A + B (422 studies): 5,704 exams: c 4,548,
d 990, e 166. Models: `Biospec 70/30` only. Zero-byte DICOM: 0.

## 4. Invariants and the dedup proofs

| Invariant | Result |
|---|---|
| Not in production by `original_name` (both forms) | 0 of 5,704 planned exams (live registry, 35,613 rows, read at plan time and by every dry run) |
| Not in production as the same session on the same day | 0 studies |
| Same sample on the same day in production (the census' key 4; another session) | 0 today; **the 12 A2 sessions (Friday) are expected here**, distinct data by design |
| **Not in production by bytes** (`ar_06_bytes.py`) | **0 of 152,573 DICOM files** (scanner's and Dicomifier's) among production's 627,841 MRI/XMRI DICOM SHA-256 (16,602 `checksums.json` read, 0 unreadable) |
| **The dedup proof** (`mri_archive_dedup_proof.yaml`, dry run, guarded copy strategy) | the 130 stream-M studies from the archive, staged and dated as the batches: **2,339 skipped "already in registry", 0 listed**, 30 skipped by name (not registered by stream M either). Every archive date's day equals production's (2,339 of 2,339). Includes Ermal's `m175`/`m178` (37 exams) |
| No duplicate within the stream | 5,531 distinct `original_name`s; 4,806 distinct link names |
| Subject ids valid (`ar_14_subject_check.py`) | 212 of 212 found; 0 `-None` |
| Every extracted file == the tarball's member | SHA-256 recorded while extracting; tarball SHA-1 == the fetch manifest's (552 of 552) |
| Nothing dated today | 0 rows dated 2026 in any dry run |

## 5. Dry runs against live production

Each bracketed by a fingerprint (size, mtime, SHA-256) of every file in `J:\gjesus3-data\registries\` (`ar_09_run.py`),
each log checked case by case (`ar_10_check_log.py`: every case-table row previewed once, its date, MRI, a free link under
the planned name; **and the exams skipped "no row in the case table" are exactly the planned not-registered ones**).

| Batch | Total / success / failed | Links free | Case check | Skipped by name (= planned not registered) | Registries |
|---|---|---:|---|---:|---|
| AR01_0118 | 498 / 498 / 0 | 498 | 0 disagreements | 29 | unchanged |
| AR02_0219 | 101 / 101 / 0 | 101 | 0 | 5 | unchanged |
| AR02n_0219 | 6 / 6 / 0 | 6 | 0 | 2 | unchanged |
| AR04_0320 | 324 / 324 / 0 | 324 | 0 | 2 | unchanged |
| AR04n_0320 | 54 / 54 / 0 | 54 | 0 | 0 | unchanged |
| AR05_0618 | 278 / 278 / 0 | 278 | 0 | 2 | unchanged |
| AR05n_0618 | 13 / 13 / 0 | 13 | 0 | 1 | unchanged |
| AR06_0619 | 460 / 460 / 0 | 460 | 0 | 2 | unchanged |
| AR08_1019 | 792 / 792 / 0 | 792 | 0 | 13 | unchanged |
| AR09_1116 | 901 / 901 / 0 | 901 | 0 | 52 | unchanged |
| AR10_1319 | 40 / 40 / 0 | 40 | 0 | 0 | unchanged |
| AR12_1519 | 1,339 / 1,339 / 0 | 1,339 | 0 | 5 | unchanged |
| AR13_noproject | 355 / 355 / 0 | — (no project) | 0 | 14 | unchanged |
| AR14_phantoms | 370 / 370 / 0 | — (no project) | 0 | 43 | unchanged |
| dedup proof | **0 listed**; 2,339 skipped as registered, 30 by name | — | — | — | unchanged |

Logs `out\dryrun_pre_*.log`; fingerprints `out\bracket_pre_*.json`. Production at the time: 35,613 rows.

---

## 6. Rehearsal

**The root** `D:\projects\gjesus3\mri_archive\rehearsal_nas\` (`ar_11_rehearsal_setup.py`, 09:04): byte copies of every
production registry file (35,613 rows), re-hashed; the 12 target projects with `_project.yaml`, `provenance.csv`, and
`raw_linked\` seeded with empty folders under every production name. Baseline: `mri_09_backup.py` → `out\reh_baseline1\`.
`ar_09_run.py --real` refuses any root but this one.

**The 14 batches for real** (the production configs, `--refresh-index projects`): **5,531 / 5,531 / 0** in 45 min (09:04 →
09:49, alongside the production dry runs): AR01 3 min 43 s, AR08 7 min 40 s, AR09 6 min 42 s, AR12 11 min 42 s, the rest
under 5 min each. 9.41 GB, 152,573 DICOM files. ACQ-IDs `ACQ-20190128-MRI-001` (AR01) … `ACQ-20210512-MRI-078` (AR04);
production gives the same IDs only if no other MRI row lands on these days first. Warnings: the documented
`condition.is_control` null sentinel on every row; on the no-subject batches "no subject_from_db flag … source=unknown" (by
design).

**Independent verification** (`ar_12_verify.py … all --rehash`): **18 of 18 PASS**: R1 35,613 → 41,144, old bytes a prefix,
exactly the 5,531 names; R2 0 disagreements (incl. operator `pending-claim`, sample type, notes with the archive path and
SHA-1); F1 152,573 files re-hashed == `checksums.json` == the extracted file (== the tarball hash for the scanner's);
S1; L1 4,806 exact hard-link folders (`0118` 498, `0219` 107, `0320` 378, `0618` 291, `0619` 460, `1019` 792, `1116` 901,
`1319` 40, `1519` 1,339), nothing lost; R3; P1; T1 subjects 1,456 → 1,617 (212 ids, 161 new), `pending_subject_metadata`
unchanged; M1 +5,531; O1 `registry_projects`, `retired_acquisitions`, `registry_datasets`, `pending_dicom_regen`
byte-identical.

**The validator** (`ar_13_validate_new.py`): **0 findings on the 5,531 new rows** (production's own rows fail only "folder
not found", by design); `pending-claim` **21,494 = 15,963 (production today) + 5,531**.
**The idempotent re-run** (the 14 configs for real again): every batch **Total 0**, each exam skipped "already in
registry". **The dedup proof after the write:** unchanged (0 listed, 2,339 skipped).
**The claim workbook** (`tools/claim_workbooks.py claims-append`, a copy of the shared workbook on `D:`, dry run against
the rehearsal): **404 sessions (5,531 acquisitions) to append, 0 into sessions already listed; every existing cell
unchanged.** Already listed: 1,288 sessions / 15,963 acquisitions.

Logs: `out\run_reh1_*.log`, `out\rehearsal_runs.txt`, `out\rehearsal_rerun.txt`, `out\reh_verify1.txt`,
`out\validate_reh1.txt`, `out\claims_preview\`.

---

## 7. Production: commands, verification, backup, rollback

**Who and when.** After Friday's completion (§9) and its re-rehearsal, the coordinator's gate and Ryan's go; **one
registry writer at a time** (no Cell Observer, drive or operator batch in the window). Run **from this worktree** in Git
Bash, `export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tools`. The `D:` extract tree is the source and must not be touched
until step 4 passes. **Time:** 5,531 exams / 9.4 GB took 45 min locally: plan 2–4 hours on the NAS for today's set
(about 1.4× that with Friday's), and as long again for the re-hash.

```bash
cd "/c/Users/rtasseff/OneDrive - CIC biomaGUNE/projects/DataInfra/gjesus3-archive/gjesus3-dev/mri-archive-ingest"
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tools
NAS="J:/gjesus3-data"; S=tools/drive_staging/mri_archive; C=tools/configs/mri_archive; O="D:/projects/gjesus3/mri_archive/out"
D=$(date +%Y%m%d); BK="C:/Users/rtasseff/temp/gjesus3_registry_backup_${D}_pre_mri_archive"     # fresh, dated; never re-use
P="AE-biomaGUNE-0118 AE-biomaGUNE-0219 AE-biomaGUNE-0220 AE-biomaGUNE-0320 AE-biomaGUNE-0618 AE-biomaGUNE-0619 AE-biomaGUNE-0721 AE-biomaGUNE-1019 AE-biomaGUNE-1116 AE-biomaGUNE-1319 AE-biomaGUNE-1321 AE-biomaGUNE-1519"
B1="AR01_0118 AR02_0219 AR02n_0219 AR04_0320 AR04n_0320 AR05_0618 AR05n_0618 AR06_0619 AR07_0721 AR08_1019 AR09_1116 AR09n_1116 AR10_1319 AR11_1321 AR12_1519 AR13_noproject AR14_phantoms"
cfgs() { for b in "$@"; do echo "$C/mri_archive_$b.yaml"; done; }

# 0. Pre-flight, read-only. Stop on any difference.
python tools/validate_registries.py --nas-root "$NAS" --no-enrichment > "$O/validate_pre.txt" 2>&1; tail -4 "$O/validate_pre.txt"
#    expect: 0 errors, 0 warnings; WRITE DOWN the "pending-claim" info line (15,963 on 2026-10-08) -- step 3's baseline
python $S/ar_05_plan.py | grep "LIVE CHECK\|link names"      # expect: names 0; session+day 0; sample+day = the 12 A2 only; taken 0
python $S/ar_07_cases.py | tail -4; git status --short $C   # expect: problems 0; taken 0; git: nothing (case tables rebuilt identical)
python $S/ar_14_subject_check.py | head -1                  # expect: found == ok == the number of distinct (alias, animal)
python $S/ar_06_bytes.py | tail -1                          # expect: exams with any file production holds: 0
python $S/ar_09_run.py "$NAS" pre $C/mri_archive_dedup_proof.yaml $(cfgs $B1)
python $S/ar_10_check_log.py "$O/dryrun_pre_mri_archive_dedup_proof.log" DEDUP     # expect: previewed 0; not skipped 0
for b in $B1; do python $S/ar_10_check_log.py "$O/dryrun_pre_mri_archive_$b.log" $b; done
#    expect, each: "missing 0; twice 0; disagreements 0; ... differ 0"; every dry run "registries changed=False"
#    AR03_0220 is dry-run in step 5, after the reopen.

# 1. Backup: every registry file, the 12 projects' provenance.csv and raw_linked listings, each re-hashed.
python tools/drive_staging/drive3/mri_09_backup.py "$NAS" "$BK" $P

# 2. The write, one batch at a time, in this order (AR03 waits for step 5). After EACH: Total = Success = the batch's
#    dry-run total, Failed 0. Otherwise STOP (see "If it stops half-way").
for b in $B1; do
  python tools/ingest_raw.py --config $C/mri_archive_$b.yaml --nas-root "$NAS" --refresh-index projects > "$BK/run_$b.log" 2>&1
  echo "$b: $(grep -E '^\s*(Total|Success|Failed):' "$BK/run_$b.log" | tr -s ' ' | tr '\n' ' ')"
done

# 3. Verify (independent of the ingest).
python $S/ar_12_verify.py "$NAS" "$BK" $(echo $B1 | tr ' ' ',') --rehash > "$BK/verify.txt" 2>&1; tail -20 "$BK/verify.txt"
#    expect: "18/18 checks PASS"
python $S/ar_13_validate_new.py "$NAS" post        # expect: findings on the new rows 0; pending-claim = step 0's + the rows written
python $S/ar_09_run.py "$NAS" post $(cfgs $B1) $C/mri_archive_dedup_proof.yaml   # expect: every total 0; dedup proof unchanged

# 4. (nothing to do on D: until the coordinator has verified)

# 5. AR03_0220: the coordinator reopens the project (Q5), then the batch.
python tools/reopen_project.py --nas-root "$NAS" --project AE-biomaGUNE-0220 --dry-run
python tools/reopen_project.py --nas-root "$NAS" --project AE-biomaGUNE-0220 --reason "the MRI platform's archive: 3 studies of 2022 (Q5, Ryan 2026-10-07)"
python -c "import csv,io;[print(p['name'],p['status']) for p in csv.DictReader(io.open(r'J:\gjesus3-data\registries\registry_projects.csv',encoding='utf-8-sig')) if p['name']=='AE-biomaGUNE-0220']"
#    expect: AE-biomaGUNE-0220 active. Otherwise STOP (the ingest ignores `closed`: it would link into a closed project).
BK3="${BK}_AR03"; python tools/drive_staging/drive3/mri_09_backup.py "$NAS" "$BK3" AE-biomaGUNE-0220
python $S/ar_09_run.py "$NAS" pre3 $C/mri_archive_AR03_0220.yaml && python $S/ar_10_check_log.py "$O/dryrun_pre3_mri_archive_AR03_0220.log" AR03_0220
python tools/ingest_raw.py --config $C/mri_archive_AR03_0220.yaml --nas-root "$NAS" --refresh-index projects > "$BK3/run_AR03_0220.log" 2>&1
python $S/ar_12_verify.py "$NAS" "$BK3" AR03_0220 --rehash | tail -3     # expect: all PASS (O1 registry_projects too: the reopen came before BK3)

# 6. The claim workbook (append only; Excel closed on every machine).
python tools/claim_workbooks.py claims-append --nas-root "$NAS"          # dry run; expect: to append = the sessions of §1's table, 0 into listed sessions
python tools/claim_workbooks.py claims-append --nas-root "$NAS" --apply --backup-dir "C:/Users/rtasseff/temp/gjesus3_claims_append_${D}_mri_archive"

# 7. The lists, with the ACQ-IDs now given.
python $S/ar_15_lists.py "$NAS"      # out/for_assign_workbook.csv, for_claim_workbook.csv, for_placement.csv
```

**`ar_12_verify.py` checks:** R1 append-only and exactly the case tables' names; R2 every row equal to the plan (ACQ-ID
date, datetime, MRI, model, `researcher` blank, `operator` `pending-claim`, `internal`, sample, sample type, subject id,
session, `.data` primary, `file_count`, checksum flag, project, config, the archive path and SHA-1 in the notes); R3 no
duplicate `acq_id`, `(date, original_name)` or name; F1 each folder and every file re-hashed == `checksums.json` == the
extracted file (== the tarball-time hash for the scanner's DICOM); S1 the sidecar subject (or none); L1 one exact hard-link
folder per row with a project under the HHMM name, `raw_linked` gaining exactly these; P1 `provenance.csv` append-only; T1
subjects once, `pending_subject_metadata.csv` unchanged; M1 `ingest_manifest.csv` append-only; O1 the other registries
byte-identical.

**Stop conditions** (stop, do not start the next step, report): any pre-flight difference; `Failed` > 0 or a total other
than the dry run's; any verify FAIL; a validator finding on the new rows, or a `pending-claim` line other than baseline +
rows written; a post-write dry run listing anything; `pending_subject_metadata.csv` growing (the DB unreachable);
`0220` not `active` before AR03; the claim-workbook dry run touching a listed session.

**If it stops half-way.** Each acquisition commits on its own (the registry append is the commit point; a failure before it
removes that acquisition's partial folder). Fix the cause and **re-run the same batch**: the dedup skips what is committed
(proven in the rehearsal). Then step 3 for the batches written. **Another writer in the window** shows up as R1 failing
(the registry grew by more than ours): stop and report; do not "fix".

**Rolling back** (no delete tool; Data Office, backup first). Stream AR's rows are exactly those whose `ingest_config`
starts `tools/configs/mri_archive/`.

| # | Side effect | Reverse by |
|---|---|---|
| 1 | `raw\DICOM\<YYYY>\<YYYY-MM>\<ACQ-ID>\` per row | delete each folder (the row's `canonical_path`) |
| 2 | `registries\.acq_id_seq.json` high-water | leave it (ids are never reused) |
| 3 | `registry_raw.csv` rows | if no other writer touched it (rows = backup + ours), restore the backup copy; else remove the rows byte-exact (no BOM, CRLF; the 2026-08-16 rule) |
| 4 | `ingest_manifest.csv` rows | the same rule |
| 5 | `registry_subjects.csv` upserts | remove only the subjects new in this write (diff against the backup) |
| 6 | `projects\<name>\raw_linked\<link name>\` | delete them (the backup's `raw_linked\<project>.txt` shows what was there) |
| 7 | `projects\<name>\provenance.csv` rows | restore under the no-other-writer rule, else remove the rows |
| 8 | `projects\<name>\index.html` | `python tools/generate_index.py --nas-root "J:/gjesus3-data" --project <PROJ-ID>` |
| 9 | `0220` reopened | leave it active (Q5); the close-out route if Ryan wants it closed again |
| 10 | the claim workbook rows | restore the `--backup-dir` copy if nobody has typed since; else delete the appended rows (they carry the `Added` date) |

Then `ar_12_verify.py` (every row now missing) and the validator (the baseline).

---

## 8. The lists (plan only; `ar_15_lists.py`)

| File (`D:\…\out\`) | Rows today | For |
|---|---:|---|
| `for_claim_workbook.csv` | 404 sessions (5,531 acquisitions) | what `claims-append` adds after the write (the session key is the study folder) |
| `for_assign_workbook.csv` | 71 studies (725 acquisitions): AR13 39, AR14 32 | the no-project studies with their claim and DB evidence (Q4). **`claim_workbooks.py assign-append` covers drive 3 only** (its grouping reads drive-3 paths): §10 AR-c |
| `for_placement.csv` | 178 rows: 173 exams + 5 reconstruction sets; 2,161 files, 0.28 GB (k-space 0.09 GB) | a placement batch: the not-registered exams and `2dseq`-only reconstructions, with their tarball and member prefix, to the study's project (121) or holding (57). The files are in the tarballs (k-space was not extracted) |

## 9. Friday: the other 228 studies (when `fetch` reports 780 verified)

Every script is resumable and re-reads live production; the order:

```bash
python $S/ar_01_extract.py --workers 12          # the 228 new tarballs only (.done skips the rest); a short tarball is salvaged
python $S/ar_02_inventory.py
python $S/ar_04_db_evidence.py                   # unchanged inputs (it already covers all 573 A/A2 studies); re-read for the record
python $S/ar_05_plan.py --sort                   # LIVE CHECK lines; expect sample+day = the 12 A2
bash   "D:/projects/gjesus3/mri_archive/out/convert_run.sh" <batches with a new convert_input_*.csv>   # in WSL, MSYS_NO_PATHCONV=1 wsl -d Ubuntu -- bash /mnt/d/...
python $S/ar_06_bytes.py; python $S/ar_07_cases.py; python $S/ar_08_configs.py; python $S/ar_14_subject_check.py
python $S/ar_09_run.py "J:/gjesus3-data" pre $(ls $C/mri_archive_AR*.yaml) $C/mri_archive_dedup_proof.yaml   # + ar_10 per batch
python $S/ar_11_rehearsal_setup.py --fresh; python tools/drive_staging/drive3/mri_09_backup.py <rehearsal root> <fresh baseline> $P
#   rehearse: reopen 0220 in the rehearsal root first (reopen_project.py --nas-root <rehearsal root>), then every batch
#   --real, ar_12_verify.py all --rehash, ar_13_validate_new.py, the re-run (Total 0), claims-append preview, ar_15_lists.py
```

Then this document's numbers are replaced by the full set's (the summary table's "all" column shows what to expect).

## 10. What I could not settle (for the coordinator)

| # | Item | Recommendation |
|---|---|---|
| **AR-a** | **128 no-code studies get their project from the DB alone** (unique protocol holding the animal with MRI logged within 3 days; the census' approved route). The largest group: **57 into `1116`** (the shared platform protocol; MFB's `cnd`/`CND`, `lungHugo`, `m179_flow`, `Mndoped` series). | Accept: every series resolves to one protocol consistently, the ambiguous ones stay unresolved, and the subject ids are then DB-sourced. **Alternative:** register the 128 with no project and list them for the assign workbook (it moves AR batches' studies into AR13; one re-plan). |
| **AR-b** | **13 claimed studies kept in their project without a subject id** (6 `1116` NOT-IN-DB, 7 with no plain animal number), as stream M's M09. The 2026-09-29 class (C) would give them no project. | Keep (a check confirms a claim and never overrules it; nothing contradicts these). |
| **AR-c** | **The assign workbook** (Q4: the no-project studies "listed in the assign workbook"). `assign-append` reads drive-3 paths only. | A small `assign-append` extension (an archive source with its own group key: the study's series) on a later branch; until then `for_assign_workbook.csv` is the list. Phantoms (AR14) need not go in (as July's). |
| **AR-d** | **The DB's hints on the Q4 codes:** `jrc200915_m194_0116` — 1116's m194 logs MRI 7T that day (likely a typo for 1116); `jrc200924_m7ii_1316` — 1319's m7 logs MRI that day (siblings `m7e`/`m7f_1319`). `jrc211215_m74_0619_fat` (CONTRADICTED) — 1019's m74 logs MRI that day. | Q4 rules them out of a project as ingested; the (A)-typo route (2026-09-29) would put them in `1116`, `1319`, `1019`. For Ryan, if he wants it; one-row-set repairs later. |
| **AR-e** | **Tier B with an animal**: `m38_pruebaGalbumin` ×2, `m3prueba_postcirugw2_1519`, `m198`/`m199_1116_prueba` (35 exams), `organism` with no project per Q2; `jrc200302_mr7g5_Caff` (census "unknown") is typed `phantom`. | As built (Q2 says no project). The `prueba` animals could join their protocols later (`1519`, `1116`) like AR-d. |
| **AR-f** | **Part 1's extra exam** `jrc210322_m131_0619/7` (in production's absence; P1-a) and the 106 Dicomifier exams with the scanner's DICOM in the archive (P1-b). | See `drive3_mri_archive_check.md`. |
| **AR-g** | **Project dates** (`start_date` / `last_activity`): the ingest does not recompute them; these acquisitions predate several projects' recorded `start_date`. | The existing BACKLOG item (project-date recompute) covers it. |
| **AR-h** | **Space on `D:`**: `extract\` (56 GB today, plus Dicomifier's output) and `rehearsal_nas\` (~10 GB). `pull\` (219 GB) is the source of record until the write is verified. | Keep all until the coordinator has verified the write; then `extract\` and `rehearsal_nas\` can go (and `pull\` per the staging rule). |

**Not done, by design:** nothing written to `J:` (dry runs bracketed, reads only); the archive never contacted; `pull\`
never modified; the facility DB asked `SELECT`s only; no shared code changed; STATUS / BACKLOG / CHANGELOG not edited.

## 11. Reproducing every number

All under `D:\projects\gjesus3\mri_archive\`; read-only on `J:`; from the worktree root with `PYTHONDONTWRITEBYTECODE=1`.

| Script | What it does | Output (`out\` unless said) |
|---|---|---|
| `ar_common.py` | paths, the write guard (only under `mri_archive\`, never `pull\`), the fast JCAMP reader, the DICOM-set digest | — |
| `ar_01_extract.py` | extraction, verified and hashed; resumable; salvages a short tarball | `extract\`, `extract\_manifests\`, `extract_*.log` |
| `ar_02_inventory.py` | every exam classed (c / d / e); `--check-parser` vs `jcampdx` | `inventory_exams.csv`, `inventory_studies.csv` |
| `ar_03_archive_check.py` | Part 1 | `tasks\drive3_mri_archive_check.csv`, `archive_check_*` |
| `ar_04_db_evidence.py` | the facility-DB verdict per study | `db_evidence.csv` |
| `ar_05_plan.py` | the plan, live checks; `--sort` | `plan_studies.csv`, `plan_exams.csv`, `not_registered.csv`, `convert_input_*.csv` |
| `convert_staged_exams.py` (WSL, `convert_run.sh`) | Dicomifier on the d-exams | `convert_<batch>.csv` |
| `ar_06_bytes.py` | the byte dedup against production | `bytes_check.txt`, `prod_mri_dicom_sha256.csv` |
| `ar_07_cases.py`, `ar_08_configs.py` | case tables, link names, the dedup set; the configs | `tools\configs\mri_archive\` |
| `ar_09_run.py`, `ar_10_check_log.py` | bracketed (dry) runs; each log checked | `dryrun_*.log`, `run_*.log`, `bracket_*.json` |
| `ar_11_rehearsal_setup.py` (+ `drive3\mri_09_backup.py`) | the rehearsal root; backups | `rehearsal_nas\`, `reh_baseline1\` |
| `ar_12_verify.py`, `ar_13_validate_new.py` | the independent verifier; the validator, new rows apart | stdout, `validate_*.txt` |
| `ar_14_subject_check.py` | every subject id, looked up now | `subject_check.csv` |
| `ar_15_lists.py` | the claim / assign / placement lists | `for_*.csv` |
| `test_ar_extract.py` | the write guard, the JCAMP reader, extraction (k-space, SHA-1, outside members, a short tarball) | in the suite |
