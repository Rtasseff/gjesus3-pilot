# The MRI platform's archive: the ingest of MFB's new studies (stream AR, gate document)

**Status:** 🔶 BUILT, DRY-RUN AND REHEARSED **for all 650 new studies** (all 780 archives local since 2026-10-08 21:32),
for the coordinator's gate and then Ryan's go. **Nothing was written to production.**
**Date:** 2026-10-08 (night) · **Branch:** `feat/mri-archive-ingest` (main merged in at `97fd045`)
**Rulings:** STATUS §0.5 "Hold" (`operator = pending-claim`), §0.6 Q1–Q7; the coordinator's calls of 2026-10-08 (§9)
**Census:** [`mri_archive_census.md`](mri_archive_census.md) · **Repeats:** stream M ([`drive3_mri_gate.md`](drive3_mri_gate.md)) · **Part 1:** [`drive3_mri_archive_check.md`](drive3_mri_archive_check.md)
**Run it:** [`tools/drive_staging/mri_archive/ar_16_production.sh`](../tools/drive_staging/mri_archive/ar_16_production.sh) (§7) · **Scripts:** `tools/drive_staging/mri_archive/ar_*.py` · **Configs:** [`tools/configs/mri_archive/`](../tools/configs/mri_archive/)
**Outputs, extract tree, rehearsal (regenerable, not backed up):** `D:\projects\gjesus3\mri_archive\` (`out\`, `extract\`, `rehearsal_nas\`); the tarballs in `pull\` are never modified
**Units:** GB = 10⁹ bytes. "Exam" = one ParaVision examination folder = one production MRI acquisition. "Session" = one study folder.

---

## Summary

1. **650 new MFB studies** (tiers A 561, A2 12, B 77) **plus 1 exam of a stream-M study** (`jrc210322_m131_0619/7`, Part 1:
   only the archive holds it; the coordinator's call) → **7,627 exams in 628 sessions, 18 batches, 12 projects + 118
   studies with no project.** 23 studies have nothing to register (aborted starts, spectroscopy only). 14.59 GB, 212,098 DICOM
   files, 313 subject ids.

   | Batch | Project | Studies | Sessions | Exams: scanner + Dicomifier | GB | Animals (subject ids) | Note |
   |---|---|---:|---:|---:|---:|---:|---|
   | AR03_0220 | `AE-biomaGUNE-0220` (closed: **reopened first**, Q5) | 3 | 3 | 0 + 22 = **22** | 0.06 | 3 | written FIRST, right after the reopen |
   | AR01_0118 | `AE-biomaGUNE-0118` | 41 | 37 | 555 + 47 = **602** | 0.74 | 32 rats | 36 studies by the DB (no code: `monocr`, `2DG`, `controlR47`, Ermal's `_ermal`) |
   | AR02_0219 | `AE-biomaGUNE-0219` | 35 | 34 | 101 + 88 = **189** | 0.72 | 16 | |
   | AR02n_0219 | `AE-biomaGUNE-0219` | 1 | 1 | 6 + 0 = **6** | 0.04 | — | `m8b`: no plain animal number |
   | AR04_0320 | `AE-biomaGUNE-0320` | 19 | 17 | 282 + 94 = **376** | 0.51 | 17 | |
   | AR04n_0320 | `AE-biomaGUNE-0320` | 3 | 3 | 35 + 19 = **54** | 0.07 | — | `m1a`, `m8b`, `m11b` |
   | AR05_0618 | `AE-biomaGUNE-0618` | 74 | 73 | 529 + 261 = **790** | 1.11 | 73 | incl. the 6 A2 `_post` sessions; 3 by the DB (`apoe` 2019) |
   | AR05n_0618 | `AE-biomaGUNE-0618` | 1 | 1 | 13 + 0 = **13** | 0.03 | — | `jrc190514_0618ApoE1` |
   | AR06_0619 | `AE-biomaGUNE-0619` | 27 + 1 | 28 | 398 + 63 = **461** | 0.48 | 25 | 18 by the DB (`hypx`); **+ `m131_0619/7`** |
   | AR07_0721 | `AE-biomaGUNE-0721` | 10 | 10 | 24 + 42 = **66** | 0.28 | 10 | incl. the 6 A2 `postadm`/`post` sessions |
   | AR08_1019 | `AE-biomaGUNE-1019` | 135 | 135 | 901 + 380 = **1,281** | 4.11 | 55 | 13 by the DB (`london`) |
   | AR09_1116 | `AE-biomaGUNE-1116` | 80 | 78 | 702 + 343 = **1,045** | 2.77 | 51 | **57 by the DB** (`cnd`/`CND`, `lungHugo`, `m179_flow`, `Mndoped`) |
   | AR09n_1116 | `AE-biomaGUNE-1116` | 6 | 6 | 16 + 16 = **32** | 0.06 | — | `m200`, `m201`, `m242`–`m245`: not in the DB under 1116 |
   | AR10_1319 | `AE-biomaGUNE-1319` | 5 | 5 | 0 + 40 = **40** | 0.08 | 5 | |
   | AR11_1321 | `AE-biomaGUNE-1321` | 1 | 1 | 0 + 4 = **4** | 0.02 | 1 | `jrc220622_m6_132` (the DB: 1321) |
   | AR12_1519 | `AE-biomaGUNE-1519` | 89 | 89 | 1,339 + 0 = **1,339** | 2.04 | 25 | |
   | AR13_noproject | **none** | 41 | 40 | 275 + 84 = **359** | 0.96 | — | Q4 (`0917` ×4, `0116`, `1316`); no code and no unique DB answer (30 + 4); DB contradicts the claim (1) |
   | AR14_phantoms | **none** | 77 | 67 | 157 + 791 = **948** | 0.53 | — | Q2: phantoms / QC, as July's |
   | *(no batch)* | `AE-biomaGUNE-1319` | *2* | *0* | *0* | | | *`m7e`, `m7f`: never acquired* |
   | **Total** | **12 projects + none** | **650 + 1** | **628** | **5,333 + 2,294 = 7,627** | **14.59** | **313** | |

2. **Every exam registered has DICOM** (Ryan's 2026-10-04 rule): 5,333 the scanner's own, **2,294 made by Dicomifier before
   ingest** in the extract tree (2,310 tried; **16 failed**: not registered, listed). **Not registered: 233 exams** (144
   never acquired, 61 spectroscopy, 11 k-space without a reconstruction, 16 failed conversions, 1 incomplete: a short
   archive), plus the `2dseq`-only reconstructions beside registered DICOM; all listed for a placement batch (plan only, §8).
3. **Fields as stream M, with the Hold:** `operator = pending-claim`, `researcher` blank, `original_name = <study>/<exam>`,
   dated by `VisuCreationDate` (7,627 of 7,627), the archive path and its SHA-1 in the notes; link names
   `MRI_<sample>_<YYYYMMDD>_<HHMM>_<exam>_<recons>` (the 2026-10-05 form): **6,320, 0 duplicated, 0 taken**.
4. **Subject ids: 313 animals looked up in the facility DB, 313 found, 0 `-None`** (0118, 1116, 0219, 0618, 0619 hold a NULL
   alias; the caller's alias is used), none born after its first scan; 7 scan days with no logged procedure, all CLAIM-KEPT.
5. **Dedup proven against live production** (registry 35,791 rows: after the NI sync's PET/CT and the drive-3 `XMIC`
   batches, quiet since 21:57), five ways (§4): 0 names; 0 sessions on the same day; the same animal on the same day only for
   the 12 A2 second sessions (by design); **0 of 212,098 DICOM files in production by SHA-256** (against 627,841); the dedup
   proof (stream M's 130 studies extracted from the archive and dated the same way: **2,339 skipped as registered, 0
   listed**, `m175`/`m178` included); every dry run lists exactly its case table.
6. **The production pre-flight already ran against live production** (`ar_16_production.sh preflight`, read-only, 2026-10-08 23:04 → 2026-10-09 00:48):
   validator green (`pending-claim` 15,963), the six live checks, case tables identical to the commit, 313 subject ids,
   bytes 0, **18 + 1 dry runs: 7,627 listed = the case tables, 0 failed, 0 disagreements, registries unchanged**. Its
   snapshot lets the morning's `write` start without re-running it (§7).
7. **Rehearsal of the script itself** on a D: root built from production at 35,791 rows: ⟨REH⟩.
8. **Run time on the NAS: about 3 to 3.5 hours** for `write` (§7). It fits 07:00–10:30 only if it starts on time; it can start as soon
   as the go comes.

---

## 1. Source: local copies only

- **Pulled** by `tools/mri_archive.py fetch` (not run here) to `D:\projects\gjesus3\mri_archive\pull\<year>\`, each verified
  against its `.sha1`: **780 of 780** (A 561, A2 12, B 77, C 130). The archive was never contacted by this work.
- **Extracted** (`ar_01_extract.py`): each tarball read once as a stream; its SHA-1 recomputed in the same pass and **equal to
  the fetch manifest's for all 780**; every member checked by `tarfile.data_filter` and confined to `<study>/`; k-space not
  extracted (listed with its size); every extracted file's SHA-256 recorded (`extract\_manifests\<study>.csv`).
- **Two archive tarballs are short** (Part 1 finding 2): `20200615_115642_jrc200615_m21_1019_1_1` (tier C) and
  `20200302_143910_jrc200302_m3r7f2_Caff_1_1` (AR13). Their `.sha1` matches the short file: the archive was written short.
  Salvaged up to the cut; the exam being read (`m3r7f2_Caff/4`) is not registered.
- **Layout:** `extract\C\<study>\` (the 130 stream-M studies: Part 1 and the dedup proof); `extract\<batch>\<study>\` for the
  new ones (`ar_05_plan.py --sort`), so `original_name = <study>/<exam>` and each batch has its own `staging_dir`. The extra
  exam `m131_0619/7` is **copied** into `extract\AR06_0619\<study>\7` (its study's folder in `extract\C\` stays the proof's).

## 2. Decisions per study

### 2.1 Projects (`ar_04_db_evidence.py`, `ar_05_plan.py`)

The facility DB (SELECT only) gives every protocol holding an animal of the study's number, its species, birth date and
logged procedures. **A check confirms a claim and never overrules it** (stream M, A1):

| Case | Studies | Project | Subject id |
|---|---:|---|---|
| Code in the name, a gjesus3 project, CONFIRMED (procedure within 3 days) | 383 | the code's | yes |
| … CLAIM-KEPT (the animal is there, nothing logged within 3 days) | 8 | the code's | yes |
| … NOT-IN-DB (`1116`: `m200`, `m201`, `m242`–`m245`) | 6 | the code's | **no** (as M09) |
| … no plain animal number (`m8b` ×2, `m1a`, `m11b`, `m7e`, `m7f`, `0618ApoE1`) | 7 | the code's | **no** (as M09) |
| … CONTRADICTED (`jrc211215_m74_0619_fat`) | 1 | **none** | no (as M08) |
| Code that is no gjesus3 project (Q4): `0917` ×4, `0116`, `1316` | 6 | **none** | no |
| **No code; the DB answers uniquely** (one protocol holds the animal, alive, MRI logged within 3 days, and it is a gjesus3 project): `1116` 57, `0118` 36, `0619` 18, `1019` 13, `0618` 3, `1321` 1 | **128** | **that protocol's** | yes |
| No code; no unique DB answer (incl. `0614` `IONP_RGD` ×8, `0917` `LPS` ×6) | 30 | **none** | no |
| No code; no animal number (`m2r7f2_Caff` …) | 4 | **none** | no |
| Tier B, phantoms / QC (Q2) | 77 | **none** | no |
| **Total** | **650** | 532 with a project, 118 without | |

The no-code resolutions are consistent by series (every `monocr`, `2DG` rat and `_ermal` → `0118`; every `cnd`/`CND`,
`lungHugo`, `m179_flow` → `1116`; every `hypx` → `0619`; every `london` → `1019`); ambiguous ones stay unresolved (e.g.
`m16_hypx`: 0518 and 0619 both log MRI that day), as does one the DB records as perfused before the scan (`r79_2_DG`).

### 2.2 Fields (case tables `tools/configs/mri_archive/cases_<batch>.csv`, `ar_07_cases.py`)

| Field | Value |
|---|---|
| `acquisition_datetime` | exam `visu_pars` `VisuCreationDate` (production's rule): **7,627 of 7,627**. 690 exams are dated later than their study name's day: multi-day studies reusing one study folder; `VisuCreationDate` and `ACQ_time` agree on all but 3 exams of the whole inventory |
| `instrument_model` | `Bruker BioSpec 7T` (every station `Biospec 70/30`), set explicitly |
| `sample_id` | `<m/r><animal>_<code>` as production; no project: `<m/r><animal>`; no animal: the study's core name; phantoms: the core name, as July's |
| `sample_type` | `organism`; tier B `phantom`, `tissue` (`exvivoAorta`), `organism` where the name holds an animal (`m38_pruebaGalbumin`, `m3prueba`, `m198`/`m199_1116_prueba`) |
| `subject_ids` | the facility DB, `<animal>-AE-biomaGUNE-<code>` (subject batches only; `subject_from_db: false` elsewhere) |
| `session_id` | production's `jrc_id` where the animal-first regex parses; else the study name without date prefix and `_1_1` |
| `researcher`, `operator` | blank, **`pending-claim`** (the Hold rule) |
| `notes` | sequence, exam, recons; the animal and its DB verdict (or why no project); `MRI platform archive backup_7T_olddata_260824/<year>/<file> (SHA-1 …)`; how the DICOM was made |

### 2.3 Convert-first (`tools/drive_staging/convert_staged_exams.py`, Dicomifier 2.5.3, WSL `dicomifier-pilot`)

On the extract tree (never `pull\`), in two rounds (`out\convert_run.sh`, `convert_run2.sh`): **2,294 of 2,310 converted**; 16
failed (Dicomifier produced no DICOM: AR14 13; AR02, AR02n, AR09 1 each). Results `out\convert_<batch>.csv`.

## 3. Exams

Inventory (`ar_02_inventory.py`, 780 studies): 10,228 exams. The plan (650 + 1): **7,860 exams: 5,333 scanner DICOM, 2,310
to convert, 217 not registrable** (+16 failed conversions = 233 not registered). Station `Biospec 70/30` only; zero-byte DICOM 0.

## 4. Invariants and the dedup proofs (live registry 35,791 rows)

| Invariant | Result |
|---|---|
| Not in production by `original_name` (both forms) | 0 of 7,860 planned exams |
| Not in production as the same session on the same day | 0 studies |
| Same animal on the same day in production (another session) | exactly the 12 A2 second sessions, by design (their links carry `HHMM`) |
| **Not in production by bytes** (`ar_06_bytes.py`) | **0 of 212,098 DICOM files** (scanner's and Dicomifier's) among production's 627,841 MRI/XMRI DICOM SHA-256 |
| **The dedup proof** (`mri_archive_dedup_proof.yaml`, dry run, guarded copy strategy) | stream M's 130 studies from the archive, staged and dated as the batches: **2,339 skipped "already in registry", 0 listed**; 30 by name (not registered by stream M either); every archive date's day == production's |
| No duplicate within the stream | 7,627 distinct `original_name`s; 6,320 distinct link names; 0 taken in production |
| Subject ids (`ar_14_subject_check.py`) | 313 of 313 found; 0 `-None` |
| Every extracted file == the tarball's member | SHA-256 recorded while extracting; tarball SHA-1 == the fetch manifest's (780 of 780) |
| Nothing dated today | 0 |

**Why the night's other writes do not matter, and how the morning knows:** the NI sync's PET/CT and the `XMIC` rows are other
instruments: ACQ-IDs are numbered per instrument and day, the dedup key is `(date, original_name)` of MRI studies, and their
link names cannot take an `MRI_…_<HHMM>_…` name. All proofs above were run after they finished (35,791 rows). The `write`
phase re-checks that **no other MRI row** has arrived since the pre-flight (else STOP and re-run the pre-flight), and re-runs
the live plan checks against the registry of that moment. The `0220` reopen adds 147 links of `0220`'s own acquisitions, all
in the old name form (no `HHMM`), so none can take an AR03 name.

## 5. The production pre-flight (read-only, already run)

`bash tools/drive_staging/mri_archive/ar_16_production.sh preflight`, 2026-10-08 23:04 → 2026-10-09 00:48, against live
production (35,791 rows, quiet since the `XMIC` batches ended at 21:57). Run folder
`C:\Users\rtasseff\temp\gjesus3_mri_archive_20261009\preflight\` (`PASS`, `snapshot.txt`, every step's output).

| Step | Result | Time |
|---|---|---|
| P1 validator | `validation OK: 0 errors, 0 warnings`; `pending-claim` **15,963** (saved as the baseline) | 13 min |
| P2 the plan, live | names 0; session + day 0; same animal + day = the 12 A2 only; links taken 0; duplicated 0; dated 2026 0 (**6 of 6**) | 4 s |
| P3 case tables rebuilt | problems 0; identical to the commit (`git status` clean) | 10 s |
| P4 subject ids | 313 found, 313 ok | 3 s |
| P5 bytes | 0 of 212,098 DICOM files in production | 8 min |
| P6 dry runs (18 batches + the dedup proof), each bracketed and checked case by case | **7,627 listed = the case tables**, 0 failed, 0 disagreements, every link free (6,320), the skipped-by-name sets equal the planned not-registered ones, **registries changed=False ×19**; dedup proof 0 listed, 2,339 skipped as registered | 82 min |
| P7 snapshot | 35,791 rows, 16,602 MRI/XMRI | — |

Per batch (listed / skipped by name): AR03 22/8, AR01 602/29, AR02 189/19, AR02n 6/2, AR04 376/2, AR04n 54/0, AR05 790/9,
AR05n 13/1, AR06 461/2, AR07 66/1, AR08 1,281/17, AR09 1,045/55, AR09n 32/0, AR10 40/0, AR11 4/1, AR12 1,339/5, AR13 359/14,
AR14 948/65. Logs `D:\projects\gjesus3\mri_archive\out\dryrun_prod_pre_*.log`.

## 6. Rehearsal of the script (D: root `D:\projects\gjesus3\mri_archive\rehearsal_nas\`, built from production at 35,791 rows)

`NAS=<the D: root> REHEARSAL=1 RUN=D:\…\out\script_rehearsal2 bash ar_16_production.sh preflight && … write`. REHEARSAL
skips the root-independent pre-flight steps already run against production, and sets `0220` active directly: the real
`reopen_project.py` relinks production's 392 `0220` acquisitions, whose `/raw/` the D: root does not hold. Its production dry
run (read-only, 2026-10-08): links `present 245, created 147, collision 0, no_raw 0, error 0`, status `closed → active`.

⟨REHT⟩

---

## 7. Production: `tools/drive_staging/mri_archive/ar_16_production.sh`

**Who and when.** The coordinator's gate, then Ryan's go. **One registry writer at a time**: no Cell Observer, drive or
operator batch, and no NI sync, during `write`. Git Bash, **from this branch's worktree** (the script is LF; a CRLF checkout
breaks bash). Off-NAS run folder `C:\Users\rtasseff\temp\gjesus3_mri_archive_20261009\` (override `RUN=…`).

```bash
bash tools/drive_staging/mri_archive/ar_16_production.sh preflight   # DONE tonight (§5); re-run only if W0 says so
bash tools/drive_staging/mri_archive/ar_16_production.sh write       # the window
bash tools/drive_staging/mri_archive/ar_16_production.sh post        # read-only, after the window
```

**`write`, step by step** (each step prints its expectation and what it got, and STOPs at the first difference):

| Step | What | Expected |
|---|---|---|
| W0 | no other MRI/XMRI row since the pre-flight; the validator (skipped only if every registry file is byte-identical to the pre-flight's, whose validator passed); the six live plan checks | `MRI added 0, removed 0`; `validator OK`; `6 of 6` |
| W1 | backup `bk0`: every registry file and the 12 projects' provenance / link lists | (silent) |
| W2 | **reopen `AE-biomaGUNE-0220`** (`tools/reopen_project.py`, dry run then real), immediately before its batch | dry run `links: {'present': 245, 'created': 147, 'collision': 0, 'no_raw': 0, 'error': 0}`; then `status ['active']` |
| W3 | backup `bk1` after the reopen (the `post` phase's baseline) | (silent) |
| each batch, in order AR03, AR01, AR02, AR02n, AR04, AR04n, AR05, AR05n, AR06, AR07, AR08, AR09, AR09n, AR10, AR11, AR12, AR13, AR14 | backup `bk_<batch>` (registries + the batch's project); `ingest_raw.py`; its totals; this config's rows in the registry; `ar_12_verify.py` against `bk_<batch>` | `Total = Success =` 22, 602, 189, 6, 376, 54, 790, 13, 461, 66, 1,281, 1,045, 32, 40, 4, 1,339, 359, 948; `Failed 0`; `rows of this config … (expected N)` equal; `18/18 checks PASS` |
| W4 | every batch's rows == its case table | `rows written by this stream: 7627` |
| W5 | validator after (~13 min on the NAS); the new rows apart | `pending-claim 23590 == 15963 + 7627`; `findings on them: 0` |
| W6 | claim workbook, dry run | `to append 627 sessions (7626 acquisitions)`; `every existing cell unchanged` |
| W7 | **claim workbook, append** (only now: every batch passed) | `APPENDED (claims)`; the workbook's copy in `claims_backup\` |

W6's numbers are one lower than the totals because `m131_0619/7` joins a session the workbook already lists (stream M's).

**Stop conditions** (the script stops; nothing after the stop runs): another writer's MRI row; the validator not green, or
not baseline + rows; the reopen dry run with a collision, `no_raw` or error, or `0220` not active after it; a batch with
`Failed` > 0, or its config's rows ≠ its case table; any verify FAIL (an R1 failure with more rows than the batch = another
writer); findings on the new rows; the claim preview's numbers; an Excel lock on the workbook (`claims-append` refuses).

**Resume after a STOP:** fix the cause, then `write --from <batch>`: the dedup skips what that batch committed (proven in the
rehearsal), its baseline `bk_<batch>` is reused, and its verify covers the whole batch. `finish` alone re-runs W4–W7.

**Rollback, per batch** (no delete tool; Data Office, backup first). The batch's rows are exactly those whose
`ingest_config` is `tools/configs/mri_archive/mri_archive_<batch>.yaml`:

| # | Side effect | Reverse by |
|---|---|---|
| 1 | `raw\DICOM\<YYYY>\<YYYY-MM>\<ACQ-ID>\` per row | delete each folder (the row's `canonical_path`) |
| 2 | `registries\.acq_id_seq.json` high-water | leave it (ids are never reused) |
| 3 | `registry_raw.csv`, `ingest_manifest.csv` rows | if no other writer touched them since `bk_<batch>` (rows = backup + the batch's), restore the backup copies; else remove the rows byte-exact (no BOM, CRLF; the 2026-08-16 rule) |
| 4 | `registry_subjects.csv` upserts | remove only the subjects new in the batch (diff against `bk_<batch>`) |
| 5 | `projects\<p>\raw_linked\<link>\` | delete them (`bk_<batch>\raw_linked\<p>.txt` lists what was there) |
| 6 | `projects\<p>\provenance.csv` rows | restore `bk_<batch>\provenance\<p>.csv` under the same rule, else remove the rows |
| 7 | `projects\<p>\index.html` | `python tools/generate_index.py --nas-root "J:/gjesus3-data" --project <PROJ-ID>` |
| 8 | the `0220` reopen | leave it active (Q5); to undo: `bk0\registry_projects.csv`'s row and the reopen's own backup |
| 9 | the claim workbook rows (W7) | `claims_backup\` holds the workbook before the append: restore it if nobody has typed since; else delete the appended rows (they carry the `Added` date) |

The whole run: the same, every batch, against `bk0`.

**`post`** (read-only, after the window): `ar_12_verify.py` of every batch against `bk1` with every file re-hashed; the
idempotent dry runs (every total 0; the dedup proof unchanged); `ar_15_lists.py` with the ACQ-IDs.

## 8. The lists (plan only; `ar_15_lists.py`)

| File (`D:\…\out\`) | For |
|---|---|
| `for_claim_workbook.csv` | what `claims-append` adds (W6/W7): 628 sessions, 7,627 acquisitions (the `m131` session is listed already) |
| `for_assign_workbook.csv` | the 107 no-project studies with an exam (AR13 40, AR14 67), with their claim and DB evidence (Q4). `claim_workbooks.py assign-append` reads drive-3 paths only (§9 AR-c) |
| `for_placement.csv` | a placement batch: the not-registered exams and `2dseq`-only reconstructions, with tarball and member prefix (k-space is in the tarballs), to the study's project or holding |

## 9. Decided, and still open

**Decided by the coordinator (2026-10-08), as built:**
- the **128 code-less studies** mapped to a project by the facility DB's dates (unique protocol, MRI within 3 days);
- the **13 claimed studies kept in their project without a subject id** (6 `1116` NOT-IN-DB, 7 without a plain animal
  number), as M09;
- the **3 typo suspects with no project**: `jrc200915_m194_0116` (1116's m194 logs MRI that day), `jrc200924_m7ii_1316`
  (1319's m7), `jrc211215_m74_0619_fat` (CONTRADICTED; 1019's m74 logs MRI that day);
- **`jrc210322_m131_0619/7` ingested** (into AR06, subject `131-AE-biomaGUNE-0619`, link `MRI_m131_0619_20210322_0832_7_1,6`).

**Still open (none blocks the run):**

| # | Item | Recommendation |
|---|---|---|
| AR-c | **The assign workbook** (Q4: no-project studies "listed in the assign workbook"): `assign-append` reads drive-3 paths only | a small extension on a later branch; until then `for_assign_workbook.csv`; phantoms need not go in (as July's) |
| AR-e | **Tier B with an animal** (`m38_pruebaGalbumin` ×2, `m3prueba_postcirugw2_1519`, `m198`/`m199_1116_prueba`): `organism`, no project per Q2; `jrc200302_mr7g5_Caff` (census "unknown") typed `phantom` | as built; a one-row-set repair later if Ryan wants them in `1519` / `1116` |
| P1-b | 106 Dicomifier exams (stream M) whose scanner DICOM is in the archive | a later in-place replacement, if wanted (Part 1) |
| P1-c | the short `m21_1019` archive (Part 1 finding 2) | tell the platform manager with Q7 |
| AR-g | project `start_date` / `last_activity` not recomputed by the ingest | the existing BACKLOG item |
| AR-h | `D:` space: `extract\` and `rehearsal_nas\` | keep until the write is verified; then both can go (and `pull\` per the staging rule) |

**Not done, by design:** nothing written to `J:` (the pre-flight and every dry run are read-only, bracketed); the archive
never contacted; `pull\` never modified; the facility DB asked `SELECT`s only; no shared code changed; STATUS / BACKLOG /
CHANGELOG not edited.

## 10. Reproducing every number

All under `D:\projects\gjesus3\mri_archive\`; read-only on `J:`; from the worktree root with `PYTHONDONTWRITEBYTECODE=1`.

| Script | What it does | Output (`out\` unless said) |
|---|---|---|
| `ar_common.py` | paths, the write guard (only under `mri_archive\`, never `pull\`), the fast JCAMP reader, the DICOM-set digest | — |
| `ar_01_extract.py` | extraction, verified and hashed; resumable; salvages a short tarball | `extract\`, `extract\_manifests\` |
| `ar_02_inventory.py` | every exam classed (c / d / e); `--check-parser` vs `jcampdx` (400 exams, 0 disagreements) | `inventory_*.csv` |
| `ar_03_archive_check.py` | Part 1 | `tasks\drive3_mri_archive_check.csv` |
| `ar_04_db_evidence.py` | the facility-DB verdict per study | `db_evidence.csv` |
| `ar_05_plan.py` | the plan, live checks; `--sort`; the extra tier-C exam | `plan_*.csv`, `convert_input_*.csv` |
| `convert_staged_exams.py` (WSL) | Dicomifier on the d-exams | `convert_<batch>.csv` |
| `ar_06_bytes.py` | the byte dedup against production | `bytes_check.txt` |
| `ar_07_cases.py`, `ar_08_configs.py` | case tables, link names, the dedup set; configs | `tools\configs\mri_archive\` |
| `ar_09_run.py`, `ar_10_check_log.py` | bracketed (dry) runs; each log checked case by case, skips included | `dryrun_*.log`, `bracket_*.json` |
| `ar_11_rehearsal_setup.py` | the rehearsal root | `rehearsal_nas\` |
| `ar_12_verify.py`, `ar_13_validate_new.py` | the independent verifier; the validator, new rows apart | stdout, `validate_*.txt` |
| `ar_14_subject_check.py` | every subject id, looked up now | `subject_check.csv` |
| `ar_15_lists.py` | the claim / assign / placement lists | `for_*.csv` |
| `ar_16_production.sh`, `ar_16_checks.py` | the production run (§7) and its checks | the run folder |
| `test_ar_extract.py` | the write guard, the JCAMP reader, extraction | in the suite |
