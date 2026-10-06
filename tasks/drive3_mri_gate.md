# The M. Jesús drive, stream M: the MRI production lacks, and the CNIC pig images (gate document)

**Status:** 🔶 BUILT, DRY-RUN AND REHEARSED, for the coordinator's gate and then Ryan's go. Nothing was written to
production. · **Date:** 2026-10-06 · **Branch:** `feat/drive3-mri` (worktree `gjesus3-dev\drive3-mri`)
**Plan:** [`drive3_production_plan.md`](drive3_production_plan.md) stream M · **Rulings:** STATUS §0.5 (M1, M2, "Pigs") ·
**Assessment:** [`drive3_raw_coverage.md`](drive3_raw_coverage.md) (A1 §2, §3, §6, §7), [`drive3_segmentations_cds.md`](drive3_segmentations_cds.md) (A3)
**Scripts:** [`tools/drive_staging/drive3/mri_*.py`](../tools/drive_staging/drive3/) · **Configs:** [`tools/configs/drive3_mri/`](../tools/configs/drive3_mri/)
**Outputs, staging, rehearsal (regenerable, not backed up):** `D:\projects\gjesus3\drive3_streams\mri\` (`out\`, `stage\`, `rehearsal_nas\`)
**For the later check against the platform's archive:** [`drive3_mri_for_archive_check.csv`](drive3_mri_for_archive_check.csv)
**Units:** GB = 10⁹ bytes. "Exam" = one ParaVision examination folder = one production MRI acquisition.

---

## Summary

1. **Part 1: 3,309 MRI exams in 190 studies, into six existing active projects; nothing is created or reopened.** Every
   exam has DICOM: 3,132 the scanner's own, 177 made by Dicomifier before ingest (Ryan's convert-first rule, 2026-10-04;
   **177 of 177 converted**). 3,042 from the 7 T, 267 from the 11.7 T (model set per exam, never derived).

   | Batch | What | Exams (scanner / Dicomifier) | Studies | Project |
   |---|---|---:|---:|---|
   | M01 | protocol `0118`, rats, 2019-09 / 2020-06 / 2021-09 (incl. Ermal's m175, m178) | 506 (506 / 0) | 27 | `AE-biomaGUNE-0118` (M1) |
   | M02 | `0619`, 2020 | 455 (393 / 62) | 25 | `AE-biomaGUNE-0619` |
   | M03 | `0619`, 2021 (10 studies on the 11.7 T) | 1,056 (949 / 107) | 59 | `AE-biomaGUNE-0619` |
   | M04 | `0619`, 2022-01-25, animals 191–200 (STATUS §0.4 N6) | 87 (87 / 0) | 6 | `AE-biomaGUNE-0619` |
   | M05 | `1019`, 2020 | 1,020 (1,012 / 8) | 61 | `AE-biomaGUNE-1019` (M2) |
   | M06 | `0320`, 2022-03 (Usp11 KO), all 11.7 T | 110 (110 / 0) | 7 | `AE-biomaGUNE-0320` |
   | M07 | `JRC191107_1116_m179_flow` (11.7 T) and `jrc240702_m93_0522` | 40 (40 / 0) | 2 | `AE-biomaGUNE-1116`, `-0522` |
   | M08 | `jrc191015_m174_flow`: the claim is contradicted | 13 (13 / 0) | 1 | **none**, no subject id |
   | M09 | `jrc210726_m145b_0619`: the animal is not confirmed (§3.3) | 22 (22 / 0) | 1 | `AE-biomaGUNE-0619`, **no subject id** |
   | **Total** | | **3,309 (3,132 / 177)** | **189** | 3,296 with a project, 3,274 with a subject id |

   (A1's "190 studies" counts `m152` of `0118`, whose 2 exams were never acquired: 189 studies have an exam to register.)
2. **Not registered: 71 exams** (29 spectroscopy, 3 k-space with no reconstruction, 39 never acquired), **45
   reconstructions** that exist as `2dseq` only beside registered DICOM ones, and the **other copies** of m175/m178 (the
   second reconstruction) and of `jrc200305_m34_flow/4`. They are listed for stream P's second batch,
   `out\for_stream_P.csv` (§8 M-c): 3,773 of those 3,830 files are in no stream's plan today. **They are now planned
   and dry-run as the second placement batch P2 (§12)**, with the pig masks from holding into `CNIC-HEARDS`.
3. **The identity of every exam was proven against live production, three ways.** (a) None of the 3,309 `original_name`s
   (`<study>/<exam>`, or X1's `<study>__<exam>`) is in the registry today. (b) **The dedup proof:** every exam of the
   drive that production already holds (3,965 in 232 studies), staged and dated exactly as the batches are, was
   dry-run against production: **3,958 skipped as already registered, 0 listed**; the other 7 are production's own
   undated placeholders (never acquired), skipped by name. So the batches cannot register a study twice, and the
   platform-archive ingest Ryan plans next will skip these 3,309 in turn, provided it stages `<study>/<exam>` and dates
   by `VisuCreationDate` (§2.3). (c) Every exam's date is its scan day (`VisuCreationDate`, the value production uses,
   equal to `acqp.ACQ_time`'s date for all 3,309).
4. **Subject ids: 141 animals looked up in the facility DB now, 141 found**, every id `<n>-AE-biomaGUNE-<alias>`, **0
   `-None`** (the 27 `0118` rats included: `0118` has a NULL alias in the DB, and `animal_db` composes from the caller's
   alias), none born after its first scan, every scan day backed by a logged procedure or a kept claim.
5. **Two attributions corrected from A1** (§3.3): `m174_flow` (contradicted; no project, no subject) as A1 said, and
   **`m145b`**, which A1 read as animal 145. Animal 145 has its own session that day, and the DB logs MRI on 2021-07-26
   for 145, 146, 152 and 153 while the drive holds m145b, m145, m152, m153. So m145b is probably 146: unconfirmed, so it
   goes in with its project and no subject id, and the question goes to M. Jesús (§8 M-a).
6. **Dry runs against live production, every one bracketed** (the registries byte-identical before and after): the nine
   batches list exactly **3,309**, case by case equal to the case tables (date, instrument, a **free** project link under
   the planned name for all 3,296 with a project), 0 failed, 0 dated 2026; P01 lists its 27.
7. **Rehearsal** into a NAS root on `D:` built from production: **3,309 / 3,309 / 0 in 25 minutes; the independent
   verifier 18/18 PASS** (all 90,080 DICOM files re-hashed equal to `checksums.json`, the staged file and the drive
   manifest; 3,296 exact hard-link folders; 106 new subjects; `pending_dicom_regen` untouched); 0 validator findings on
   the new rows; **the re-run adds 0**; the dedup proof unchanged. Part 2: `CNIC-HEARDS` created, **27 / 27 / 0, verifier
   14/14 PASS**, re-run 0 (§6).
8. **Part 2, the CNIC pig images: 27 rows, one per Philips series, 35,157 DICOM instances (7.62 GB stored), into a new project
   `CNIC-HEARDS`** as `XMRI`, `collaborator:CNIC`, *Sus scrofa*, no subject id. Every header was read: **no sign of
   human data** (patient name and id are the pig codes). The row unit is settled (§9.2). The masks are placed by stream P's
   2b tool after the project exists (§9.6, planned, not run).
9. **Suite: 39/39 suites pass** (on `main` merged in; the one shared-code change is P2's opt-in `keep_despite_name` in `p_plan.py`, with its test).

---

## 1. Scope and sources

- **Input:** A1's per-exam tables (`D:\projects\gjesus3\drive3_analysis\a1\`): 3,380 exams of 198 studies not in
  production (classes c, d, e). `mri_01_plan.py` re-reads the live registry and projects and writes the per-exam plan.
- **The drive copy staged** is A1's canonical copy of each exam (the copy with the most distinct content), except
  m175 / m178, staged from the copy byte-identical to Ermal's on `K:\gjesus\MRI\Proyecto 0118` (A1 R2): m175 from
  `respiracion\inspiracion`, m178 from `respiracion\expiración`. **`mri_06_kcheck.py` re-hashed every staged file of the two
  studies against K:: 1,356 + 1,353 identical, 0 differ, 0 missing (PASS).**
- **Staging** (`mri_02_stage.py`): the staged drive copy is on the NAS and read `rb` only. Each exam's files except k-space
  (`fid`, `ser`, `rawdata.job*`), plus the study's `subject`, are copied to `D:\…\mri\stage\<batch>\<study>\<exam>\`,
  each file's SHA-256 computed in the same pass and compared with the drive manifest: **152,986 files, 10.93 GB, all
  matched; re-run later, all 152,986 re-hashed and kept.** Flat `<study>\<exam>` gives `original_name = <study>/<exam>`,
  the production shape (the `staging_dir` trap). The copy, not a symlink tree, is because `convert_staged_exams.py`
  writes into the exam it converts.
- **Ermal's other 6 `K:` sessions are out of scope** (STATUS §0.4 N7 stays open).

## 2. Decisions per exam

### 2.1 Projects (Ryan's rulings, the DB's verdicts)

All `0118` → `AE-biomaGUNE-0118` (M1); `1019` 2020 → `AE-biomaGUNE-1019` (M2); `JRC191107_1116_m179_flow` →
`AE-biomaGUNE-1116` (the DB decides between the folder's `0619` and the name's `1116`); `m174_flow` → none; the rest by
their DB-confirmed code. **The six target projects are active** (checked live; `1521`, `0618`, `0220`, the closed ones, are
not targets). A1's verdicts: 187 CONFIRMED, 9 CLAIM-KEPT, 1 CONFIRMED-NAME, 1 C; M09 is A1's CONFIRMED corrected (§3.3).

### 2.2 Fields

Every per-exam value comes from a **case table** (`tools/configs/drive3_mri/cases_M0N.csv`, `on_missing: error`), built
from the staged exam by `mri_04_cases.py`; no regex decides anything (57 of the studies parse with neither production
regex). The configs are generated from one template by `mri_05_configs.py`.

| Field | Value |
|---|---|
| `acquisition_datetime` | exam `visu_pars` `VisuCreationDate` (production's rule), else `acqp` `ACQ_time`: **all 3,309 from `VisuCreationDate`** |
| `instrument_model` | `Bruker BioSpec 7T` (`Biospec 70/30`) or `Bruker BioSpec 11.7T` (`BIOSPEC 500`), explicit: `_scanner_model` turns `BIOSPEC 500` into "50T" |
| `sample_id` | `<prefix><animal>_<code>` as production (`m17_0619`); the rats keep their own prefix (`r111_0118`; `m152`, `m175`, `m178` are rats named `m`); M08 `m174`; M09 `m145b_0619` |
| `subject_ids` | facility DB, `<animal>-AE-biomaGUNE-<alias>`; none for M08 and M09 |
| `session_id` | production's `jrc_id` capture where the animal-first regex parses; else the study name without its date prefix and `_1_1` |
| `researcher`, `operator` | `NA` → blank, as stream B (the `pending-claim` hold is for the June scanner load only) |
| `notes` | sequence, exam, recons; the animal and its DB verdict; the drive copy's path; how the DICOM was made; "to be checked against the MRI platform's archive" |
| link name | the production template `MRI_<sample>_<YYYYMMDD>_<exam>_<every pdata idx>`; **3,296 names (M08 has none), 0 duplicated, 0 taken in production** |

### 2.3 The date rule, and why it matters for the later archive ingest

The dedup key is `(acquisition date, original_name)`. `VisuCreationDate` is when the reconstruction ran; on this drive it is
the scan day for all 3,309 (and for the 3,958 dated exams production already holds, it equals production's date for every
one). **The platform-archive ingest must stage `<study>/<exam>` (not `staging_dir`-relative deeper paths) and date by the
same field**, or it will register these exams twice. A re-reconstruction on a later day would also change the date: the
archive check (`drive3_mri_for_archive_check.csv`) lists every exam's date and a digest of its DICOM set for that compare.

## 3. The exams one by one: what is not straightforward

### 3.1 Convert-first (177 exams)

`convert_staged_exams.py` (Dicomifier 2.5.3 through `ingest/paravision_regen.py`, WSL env `dicomifier-pilot`) on the
staged copies: **M02 62/62, M03 107/107, M05 8/8 converted; 0 failed**, so no exam joins the not-registered list.
Each row's note says "DICOM regenerated by Dicomifier 2.5.3 (+ gjesus3 workarounds) from the ParaVision 2dseq before
ingest". Results: `out\convert_M0N.csv`.

### 3.2 Reconstructions without DICOM (45 exams, 6 studies)

The flow studies of `m37`, `m39`, `m40`, `m41` (2020-03) and two more have reconstruction 4 as `2dseq` only beside DICOM
reconstructions 1–3. The ingest stores the DICOM ones (as for every production exam); the link name still lists every
`pdata` index. The `2dseq` folders go to stream P (§8 M-c). Converting reconstruction 4 alone would mix scanner and
Dicomifier DICOM in one acquisition; not done.

### 3.3 Animals: M08 and M09

- **M08 `jrc191015_m174_flow_1_1`** (13 exams): the folder claims `0619`, but animal 174 of `0619` was born 2021-07-29
  (A1). No project, no subject id, `subject_from_db: false`; the row's note says why.
- **M09 `jrc210726_m145b_0619_1_1`** (22 exams). The name claims "145b"; the DB holds no such animal. A1 confirmed it as
  145, but 145 has its own session that day (`jrc210726_m145_0619`, 10:47, in M03), and both would have taken the same 13
  link names: the collision check found it. The DB (SELECT, read-only) logs **MRI 7T on 2021-07-26 for 145, 146, 152,
  153**, and the drive holds sessions m145b (08:55), m145, m152, m153: m145b is probably **146**. A check confirms a claim
  and never overrules it, and "probably" is not an attribution, so: project `AE-biomaGUNE-0619` (the folder's claim, and
  every candidate is `0619`), sample `m145b_0619`, no subject id. If M. Jesús confirms 146, the subject id is a one-row-set
  repair later (the recovery-tool pattern).

### 3.4 Other edges checked

- `jrc200305_m34_flow/4`: its two drive copies differ only in `rawdata.job1` (k-space); the DICOM is identical. Not stored.
- Subject files: where a study's exams come from two copies, the two `subject` files are byte-identical (0 differ).
- Zero-byte DICOM among the 3,309: none.

## 4. Invariants (all checked)

| Invariant | Result |
|---|---|
| Not in production by `original_name` (both forms) | 0 of 3,309 (live registry, read at plan time and again by every dry run) |
| Not in production by bytes | the dedup proof (3,958 skipped) and the date check; A1 showed 0 SHA-256 matches for these exams, and a hash mismatch alone is not "missing" (A1 §2.2: 192 re-exports) |
| No duplicate within the stream | 3,309 distinct `original_name`s; 3,296 distinct link names |
| Link names free in production | 3,296 of 3,296 free (`mri_04_cases.py` against the live `raw_linked\`, and every dry run's pre-flight) |
| Subject ids valid | 141 of 141 found; 0 `-None` (`mri_13_subject_check.py`) |
| Every staged file = the drive manifest | 152,986 of 152,986 (and 35,188 pig files) |
| m175 / m178 = K: | 2,709 of 2,709 |
| Nothing dated today | 0 rows dated 2026 in any dry run |

## 5. Dry runs against live production

Each bracketed by a fingerprint (size, mtime, SHA-256) of every file in `J:\gjesus3-data\registries\`
(`mri_07_dryruns.py`), and each log checked case by case against its case table (`mri_14_check_log.py`: previewed once,
date, instrument, a free link under the planned name).

| Config | Total / success / failed | Links free | Case check | Registries |
|---|---|---:|---|---|
| M01 | 506 / 506 / 0 | 506 | 506 of 506, 0 disagreements | unchanged |
| M02 | 455 / 455 / 0 | 455 | 455, 0 | unchanged |
| M03 | 1,056 / 1,056 / 0 | 1,056 | 1,056, 0 | unchanged (re-run; the first run's window held stream C's C01 write, 42 rows at 17:xx UTC) |
| M04 | 87 / 87 / 0 | 87 | 87, 0 | unchanged |
| M05 | 1,020 / 1,020 / 0 | 1,020 | 1,020, 0 | unchanged |
| M06 | 110 / 110 / 0 | 110 | 110, 0 | unchanged |
| M07 | 40 / 40 / 0 | 40 | 40, 0 | unchanged |
| M08 | 13 / 13 / 0 | — (no project) | 13, 0 | unchanged |
| M09 | 22 / 22 / 0 | 22 | 22, 0 | unchanged |
| dedup proof | **0 listed**; 3,958 skipped as registered, 7 by name | — | — | unchanged |
| P01 (pigs) | 27 / 27 / 0 | 0: `CNIC-HEARDS` does not exist yet ("no project link") | 27 previewed | unchanged |

Logs `out\dryrun_prod*_*.log`; fingerprints `out\bracket_prod*.json`. Production on 2026-10-06 evening: 27,364 rows
(after stream N's 202 and stream C's 42).

---

## 6. Rehearsal

**The root.** `D:\projects\gjesus3\drive3_streams\mri\rehearsal_nas\`, built at 19:37 by `mri_08_rehearsal_setup.py`:
byte copies of every file of production's `registries\` (27,364 rows: after stream N's 202 and stream C's C01), each
re-hashed against its source; the six target projects with `_project.yaml`, `provenance.csv`, and `raw_linked\` seeded
with **empty folders under every name production has there** (so a taken name is refused here exactly as there); an empty
`raw\`. Hard links on NTFS behave as on the NAS. The verifier's baseline is `mri_09_backup.py` of that root. Production
was never the target: `mri_07_dryruns.py --real` refuses any root but this one.

**Part 1, the nine batches** (the production configs, with `--refresh-index projects`), on local disk:

| Batch | Total / success / failed | Time | Rows · GB · DICOM files | ACQ-IDs in the rehearsal | Subjects |
|---|---|---|---|---|---|
| M01 | 506 / 506 / 0 | 2 min 39 s | 506 · 0.61 · 14,140 | `ACQ-20190909-MRI-001` … `ACQ-20210902-MRI-037` (8 days) | 27 rats |
| M02 | 455 / 455 / 0 | 3 min 32 s | 455 · 0.76 · 16,279 | 2020-03-05 … 2020-12-10 (7 days) | 25 |
| M03 | 1,056 / 1,056 / 0 | 7 min 41 s | 1,056 · 1.63 · 25,080 | 2021-03-12 … 2021-10-20 (14 days) | 57 |
| M04 | 87 / 87 / 0 | 45 s | 87 · 0.14 · 2,118 | `ACQ-20220125-MRI-001` … `-087` | 6 |
| M05 | 1,020 / 1,020 / 0 | 8 min 53 s | 1,020 · 1.92 · 28,794 | 2020-04-21 … 2020-10-14 (12 days) | 17 |
| M06 | 110 / 110 / 0 | 40 s | 110 · 0.16 · 2,425 | 2022-03-03/04, after production's own rows of those days | 7 |
| M07 | 40 / 40 / 0 | 15 s | 40 · 0.04 · 619 | `ACQ-20191107-MRI-001` …; `ACQ-20240702-MRI-066` … `-085` | 2 |
| M08 | 13 / 13 / 0 | 3 s | 13 · 0.01 · 112 | `ACQ-20191015-MRI-001` … `-013` | none (by design) |
| M09 | 22 / 22 / 0 | 10 s | 22 · 0.03 · 513 | `ACQ-20210726-MRI-069` … `-090` | none (by design) |
| **Total** | **3,309 / 3,309 / 0** | **24 min 38 s** | **3,309 · 5.30 GB · 90,080** | 0 dated 2026 | **141 (106 new to the subjects table)** |

Production gives the same ACQ-IDs only if no other MRI row lands on these dates first (each day continues after
production's highest number for that day). Warnings: on every row, the documented `condition.is_control` null sentinel;
on M08 and M09 also "no subject_from_db flag and no operator subject: block; writing source=unknown" (by design).

**Independent verification, Part 1** (`mri_10_verify.py … --rehash`, 12 min): **18 of 18 PASS.**

| Check | Result |
|---|---|
| R1 | `registry_raw.csv` 27,364 → 30,673, the old bytes an exact prefix; the new rows are exactly the 3,309 names |
| R2 | every row equals its case table: 0 disagreements |
| F1 | every folder as specified; **all 90,080 DICOM files re-hashed: == `checksums.json` == the staged file == the drive manifest** (the scanner's own) |
| S1 | the DB-sourced subject on 3,274 sidecars; no facility id on M08's and M09's 35 |
| L1 | 3,296 link folders (`0118` 506, `0619` 1,620, `1019` 1,020, `0320` 110, `1116` 20, `0522` 20), each an exact `samefile` set; `raw_linked\` gained exactly these and lost nothing |
| R3 | no duplicate `acq_id` or `(date, original_name)`; no new row shares its name with any row |
| P1 | each project's `provenance.csv` append-only, one row per link |
| T1 | `registry_subjects.csv` 1,339 → 1,445: the 141 ids each once (106 new); `pending_subject_metadata.csv` unchanged (no DB miss) |
| M1 | `ingest_manifest.csv` +3,309, append-only |
| O1 | `registry_projects`, `retired_acquisitions`, `registry_datasets`, **`pending_dicom_regen`** byte-identical (no empty placeholder) |

**The validator** (`mri_15_validate_new.py`): with `--no-enrichment`, **0 findings on the 3,309 new rows** (the root's other
27,364 rows fail only "acquisition folder not found", by design: their `/raw/` is not here); `pending-claim` 10,314,
unchanged. The full run adds only the documented unknown sentinels on the new rows: `condition.is_control` null (3,309)
and `anatomy.is_whole_body` null (2,695, where the scan name gives no region): **the same shape as stream B's production
rows** (a sample of 71 of its 1,753).

**The idempotent re-run** (the nine configs for real, again): **every batch Total 0**, each exam skipped "already in
registry" (506, 455, 1,056, 87, 1,020, 110, 40, 13, 22). **The dedup proof after the write:** unchanged (3,958 + 7, 0 listed).

**Part 2** in the same root, after Part 1:

1. `create_project.py --dry-run`, then for real: **`PROJ-0066` `CNIC-HEARDS`** (production gives the next free id), the
   folder with its four subfolders, `_project.yaml`, `provenance.csv`.
2. Backup (`reh_baseline2`), then P01's dry run: **27 / 27 / 0, 27 links free**, the case check 0 disagreements.
3. P01 for real: **27 / 27 / 0 in 1 min 11 s**: 27 rows, **7.62 GB, 35,157 files**, `ACQ-20140221-XMRI-001` …
   `ACQ-20140716-XMRI-005` (6 days), organism *Sus scrofa*.
4. `mri_22_pig_verify.py --rehash`: **14 of 14 PASS**: every instance re-hashed == `checksums.json` == the drive manifest;
   27 exact `samefile` link folders; the `dicom` block holds the pig code as patient id, sex F, age `P2Y`, a weight, and
   no key holding a name or a birth date; `registry_subjects.csv` and the pending lists unchanged. (A first run failed S1
   on the extractor's own policy note, which names the denied tags in prose; the check now reads keys.)
5. The validator: 0 findings on the new rows. The re-run: **Total 0** (27 skipped).

Logs: `out\run_reh*_*.log`, `out\rehearsal_runs.txt`, `out\rehearsal_post.txt`, `out\reh_verify1.txt`,
`out\reh_verify2.txt`, `out\validate_reh_*.txt`.

---

## 7. Production: commands, verification, backup, rollback

**Who and when.** Ryan's go after the coordinator's gate; the coordinator opens the write window (**one registry writer
at a time**: stream C's batches must not run in it) and runs or supervises it. Run **from this worktree** (the branch is
merged after the write is verified, as for drives 1+2 and stream N), in Git Bash, with
`export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tools`. The `D:` staging (`stage\M01`…`M09`, `stage\P01`, `stage\PIG`) is
the source and must not be touched until step 7 passes.

**Time** (from the rehearsal, §6, scaled for SMB): Part 1 writes 3,309 acquisitions, 5.30 GB and 90,080 DICOM
files to the NAS (25 minutes on local disk): **plan 2–4 hours**. Part 2 writes 27 acquisitions and 35,157 files (7.62 GB;
71 s locally): **about 1 hour**. The
verification re-hashes everything it wrote (step 3 and 6): about as long again. The batches can be run in separate
sittings: each batch commits its own rows, and the verifier takes the list of batches written so far.

```bash
cd "/c/Users/rtasseff/OneDrive - CIC biomaGUNE/projects/DataInfra/gjesus3-archive/gjesus3-dev/drive3-mri"
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tools
NAS="J:/gjesus3-data"; S=tools/drive_staging/drive3; C=tools/configs/drive3_mri; O="D:/projects/gjesus3/drive3_streams/mri/out"
D=$(date +%Y%m%d)
BK="C:/Users/rtasseff/temp/gjesus3_registry_backup_${D}_pre_drive3_mri"           # fresh, dated; never re-use
BK2="C:/Users/rtasseff/temp/gjesus3_registry_backup_${D}_pre_drive3_mri_P01"
ALL="M01,M02,M03,M04,M05,M06,M07,M08,M09"
CFGS="$C/drive3_mri_M01_0118.yaml $C/drive3_mri_M02_0619_2020.yaml $C/drive3_mri_M03_0619_2021.yaml $C/drive3_mri_M04_0619_2022.yaml $C/drive3_mri_M05_1019_2020.yaml $C/drive3_mri_M06_0320_2022.yaml $C/drive3_mri_M07_1116_0522.yaml $C/drive3_mri_M08_noproject.yaml $C/drive3_mri_M09_0619_m145b.yaml"

# 0. Pre-flight, read-only. Stop on any difference.
python tools/validate_registries.py --nas-root "$NAS" --no-enrichment > "$O/validate_pre.txt" 2>&1; tail -5 "$O/validate_pre.txt"
#    expect: 0 errors, 0 warnings; WRITE DOWN the pending-claim info line (it is the baseline of step 3)
python $S/mri_02_stage.py | tail -1                     # expect: DONE {'kept': 152986}   (every staged file re-hashed = drive manifest)
python $S/mri_02_stage.py "$O/plan_stage_files_pig.csv" | tail -1    # expect: DONE {'kept': 35188}
python $S/mri_06_kcheck.py | tail -1                    # expect: RESULT: PASS
python $S/mri_04_cases.py | tail -6                     # (about 20 min) expect: link names 3309; duplicated 0; already taken 0; problems 0
git status --short tools/configs/drive3_mri/            # expect: nothing (the case tables rebuilt identical)
python $S/mri_13_subject_check.py | head -1             # expect: distinct (alias, animal): 141; found 141; ok 141
python $S/mri_07_dryruns.py "$NAS" pre $CFGS $C/drive3_mri_dedup_proof.yaml
#    expect, per batch: total = success = 506 / 455 / 1056 / 87 / 1020 / 110 / 40 / 13 / 22, failed 0, link_free equal to
#    the total (M08: 0), today 0, "registries changed=False"; dedup proof: total 0, skip_registered 3958, skip_case_table 7
for b in M01_0118 M02_0619_2020 M03_0619_2021 M04_0619_2022 M05_1019_2020 M06_0320_2022 M07_1116_0522 M08_noproject M09_0619_m145b; do
  python $S/mri_14_check_log.py "$O/dryrun_pre_drive3_mri_$b.log" ${b%%_*}; done
#    expect: each "missing 0; twice 0; disagreements 0"

# 1. Backup: every registry file, the six projects' provenance.csv and raw_linked listings, each re-hashed.
python $S/mri_09_backup.py "$NAS" "$BK"

# 2. Part 1, the write: one batch at a time, in this order. After EACH: the summary line must be
#    Total = Success = the batch's number above, Failed 0. Otherwise STOP (see "If it stops half-way").
for c in $CFGS; do
  b=$(basename $c .yaml)
  python tools/ingest_raw.py --config $c --nas-root "$NAS" --refresh-index projects > "$BK/run_$b.log" 2>&1
  echo "$b: $(grep -E '^\s*(Total|Success|Failed):' "$BK/run_$b.log" | tr -s ' ' | tr '\n' ' ')"
done

# 3. Verify Part 1 (independent of the ingest).
python $S/mri_10_verify.py "$NAS" "$BK" $ALL --rehash > "$BK/verify_part1.txt" 2>&1; tail -25 "$BK/verify_part1.txt"
#    expect: every check PASS (the list below), "N/N checks PASS"
python $S/mri_15_validate_new.py "$NAS" post_part1
#    expect: findings on the new rows 0; the pending-claim line unchanged from step 0
python $S/mri_07_dryruns.py "$NAS" post $CFGS $C/drive3_mri_dedup_proof.yaml
#    expect: every batch total 0 (all skipped "already in registry"); dedup proof unchanged (0 / 3958 / 7)

# 4. Part 2: create the project (tools/create_project.py, the Project Manager's path).
python tools/create_project.py --nas-root "$NAS" --name "CNIC-HEARDS" --owner "Data-Office" \
  --description "External pig pulmonary-artery MRI (study label HEARDS): Philips Achieva 3T at CNIC (Madrid), 2014, and its segmentation masks, from M. Jesús's drive (MJesus-MFB). No biomaGUNE animal protocol. The images are registered as XMRI collaborator data (collaborator:CNIC); the masks are project material, not curated." \
  --notes "Created for the M. Jesus drive (stream M, tasks/drive3_mri_gate.md); Ryan's ruling of 2026-10-06 (STATUS 0.5, Pigs)." --dry-run
#    expect: the next PROJ-ID, folder projects\CNIC-HEARDS, no error. Then the same command without --dry-run.
python -c "import csv,io;[print(p['project_id'],p['name'],p['status'],p['folder_location']) for p in csv.DictReader(io.open(r'J:\gjesus3-data\registries\registry_projects.csv',encoding='utf-8-sig')) if p['name']=='CNIC-HEARDS']"
#    expect: one line, status active, /projects/CNIC-HEARDS/

# 5. Part 2, the write.
python $S/mri_09_backup.py "$NAS" "$BK2" CNIC-HEARDS
python $S/mri_07_dryruns.py "$NAS" preP01 $C/drive3_mri_P01_cnic_heards.yaml
python $S/mri_14_check_log.py "$O/dryrun_preP01_drive3_mri_P01_cnic_heards.log" P01
#    expect: 27 / 27 / 0, link_free 27, "disagreements 0". If the links say "project 'CNIC-HEARDS' not found": STOP
#    (a real run would register the 27 rows with NO project).
python tools/ingest_raw.py --config $C/drive3_mri_P01_cnic_heards.yaml --nas-root "$NAS" --refresh-index projects > "$BK2/run_P01.log" 2>&1
grep -E '^\s*(Total|Success|Failed):' "$BK2/run_P01.log"        # Total 27, Success 27, Failed 0

# 6. Verify Part 2.
python $S/mri_22_pig_verify.py "$NAS" "$BK2" --rehash > "$BK2/verify_P01.txt" 2>&1; tail -16 "$BK2/verify_P01.txt"
#    expect: every check PASS
python $S/mri_15_validate_new.py "$NAS" post_part2      # expect: findings on the new rows 0
python $S/mri_07_dryruns.py "$NAS" postP01 $C/drive3_mri_P01_cnic_heards.yaml    # expect: total 0 (27 skipped)

# 7. The list for the later archive check, with the ACQ-IDs now given.
python $S/mri_11_archive_check.py "$NAS"                # expect: 3309 exams in 189 studies; with an ACQ-ID: 3309
```

**`mri_10_verify.py` checks** (each PASS/FAIL, against the backup): R1 `registry_raw.csv` append-only (the old bytes are
a prefix) and exactly +3,309 rows, the case tables' names; R2 every row equal to the plan (ACQ-ID date, datetime to the
second, MRI, model, blank researcher and operator, `internal`, sample, organism, subject id, session, `.data` primary,
`file_count` = the staged DICOMs, checksum flag, project, config, the drive path in the notes); R3 no duplicate `acq_id`
or `(date, original_name)`, and no new row sharing its name with any row; F1 each folder holds `metadata.json`,
`checksums.json`, `README.txt` and `<ACQ-ID>.data\` with exactly the staged DICOMs under their production names, each
re-hashed **== `checksums.json` == the staged file == the drive manifest** (the scanner's DICOM; Dicomifier's has no
manifest entry); S1 the sidecar's subject (DB-sourced id, or none for M08/M09); L1 one link folder per row with a
project, named by the template, holding exactly the `.data` files, each `os.path.samefile`, and each project's
`raw_linked\` gaining exactly these and losing nothing; P1 `provenance.csv` append-only, one row per link; T1 every new
subject id once in `registry_subjects.csv`, `pending_subject_metadata.csv` unchanged; M1 `ingest_manifest.csv` +3,309,
append-only; O1 `registry_projects`, `retired_acquisitions`, `registry_datasets` and `pending_dicom_regen` byte-identical
(no empty placeholder is ever queued: every exam has DICOM).

**Stop conditions** (stop, do not start the next step, report): any pre-flight difference; `Failed` > 0 or a total other
than the batch's; any verify FAIL; a validator finding on the new rows, or a change in the `pending-claim` line; a
post-write dry run listing anything; `pending_subject_metadata.csv` growing (the DB unreachable); P01's links not free.

**If it stops half-way.** Each acquisition commits on its own (the registry append is the commit point; a failure before
it removes that acquisition's partial folder). Fix the cause and **re-run the same batch**: the dedup skips what is
committed (proven in the rehearsal, §6). Then run step 3 for the batches written. **Another writer in the window** shows
up as R1 failing (the registry grew by more than ours): stop and report; do not "fix".

**Rolling back** (no delete tool; a Data-Office manual, backup-first operation). Stream M's rows are exactly those whose
`ingest_config` starts `tools/configs/drive3_mri/`.

| # | Side effect | Reverse by |
|---|---|---|
| 1 | `raw\DICOM\<YYYY>\<YYYY-MM>\<ACQ-ID>\` per row | delete each folder (the row's `canonical_path`) |
| 2 | `registries\.acq_id_seq.json` high-water | leave it (ids are never reused; the gap is by design) |
| 3 | `registry_raw.csv` rows | if no other writer touched it since (rows = backup + ours), restore the backup copy; else remove the rows byte-exact (no BOM, CRLF; the 2026-08-16 rule) |
| 4 | `ingest_manifest.csv` rows | the same rule |
| 5 | `registry_subjects.csv` upserts | remove only the subjects new in this write (diff against the backup) |
| 6 | `projects\<name>\raw_linked\<link name>\` | delete them (the backup's `raw_linked\<project>.txt` shows what was there before) |
| 7 | `projects\<name>\provenance.csv` rows (`input_refs` = the ACQ-ID) | restore the backup copy under the same no-other-writer rule, else remove the rows |
| 8 | `projects\<name>\index.html` | `python tools/generate_index.py --nas-root "J:/gjesus3-data" --project <PROJ-ID>` |
| 9 | Part 2: the `CNIC-HEARDS` project (row in `registry_projects.csv`, folder) | only if Part 2 is abandoned: the close-a-project route (BACKLOG); an empty project is harmless |

Then `mri_10_verify.py` / `mri_22_pig_verify.py` (every row now missing) and the validator (the baseline).

---

## 8. What I could not settle, and what the coordinator should decide

| # | Item | Recommendation |
|---|---|---|
| **M-a** | **`m145b` (M09, 22 exams)**: probably animal 146 (§3.3), unconfirmed. | Register as built (project, no subject id). Add one line to `drive3_questions_for_mjesus.md` (v3): "On 2021-07-26 the scanner has a session named `m145b` at 08:55 and `m145` at 10:47; the facility DB logs MRI that day for 145, 146, 152, 153. Is `m145b` animal 146?" Default if nobody knows: stays without a subject id. |
| **M-b** | **`CNIC-HEARDS`'s owner.** The handoff names the project and its description, not the owner. | `Data-Office`, as `Project-0521` (created by the Data Office for the historical drives). **Alternative:** `JRC`, as `DTS24` (MFB's reuse of external MRI). Change step 4's `--owner` before the write. |
| **M-c** | **Raw MRI not registered** (`out\for_stream_P.csv`, 3,830 files, 2.09 GB): the 71 exams of class (e) (every copy), the 45 `2dseq`-only reconstructions, the other copies of m175/m178 (the second reconstruction) and of `m34_flow/4`, and the pig folder's 27 `DICOMDIR`s and 4 MATLAB files. **3,773 of them are in no stream's plan** (stream P's manifest holds 57). | Route to stream P's second batch (production plan, close-out 3: "the MRI exams that cannot be converted copied to the holding folder"), `0118`'s into `AE-biomaGUNE-0118`, `0619`'s and `1019`'s into their projects, the pig files into `CNIC-HEARDS`, each with a README. 742 files are already in the drives 1+2 holding folder by bytes (the `1019` MRS exams, A1 trap 9): P decides whether to place them twice. |
| **M-d** | **Four MATLAB files named `thumbs.cache` / `folders.cache`** in the pig folder (one is 212 MB, inside a `DICOM\`). | A junk filter that drops `thumbs.cache` by name (A1's `JUNK_NAMES` has it) would lose them. Stream P must take them by path, not by name (M-c). |
| **M-e** | **The platform-archive ingest** (Ryan's next step, BACKLOG). | Its configs must stage `<study>/<exam>` flat and date by `VisuCreationDate` (§2.3), or it registers these 3,309 again. Add one line to the BACKLOG item. Its first dry run should be bracketed by a run of `drive3_mri_dedup_proof.yaml`-style proof over these studies. |
| **M-f** | **Project dates.** The ingest does not recompute `start_date` / `last_activity`; acquisitions here predate several projects' recorded `start_date` (e.g. `0619`'s, `0320`'s, `0118`'s). | The existing BACKLOG item (project-date recompute) covers it. |
| **M-g** | **Space on `D:`** (`D:\projects\gjesus3\drive3_streams\mri\`: `stage\` 11 GB + 7.9 GB + parameter files, `rehearsal_nas\` about 13 GB). | `stage\` is the write's source: keep it until step 7 passes and the coordinator has verified. Then all of it can go (the drive copy on `J:` stays until close-out). |

**Not done, by design:** no shared code changed; nothing written to `J:` or `K:`; the facility DB was asked `SELECT`s
only; the masks were not moved (§9.6); `STATUS`, `BACKLOG`, `CHANGELOG` not edited.

---

## 9. Part 2: the CNIC pig images (project `CNIC-HEARDS`)

### 9.1 What they are

`Otros\Segmentaciones ITK SNAP\Segmentaciones Arteria Pulmonar cerdos\Imágenes\RL\` holds **27 folders**
`HEARDSMRI<pig>P_<session>_<series>`, each with a `DICOMDIR`, `DICOM\IM_*` and `Split\` (MetaImage volumes made from the
series). Staged to `D:` (`stage\PIG\`, every file except `Split\`, 35,188 files, each matched to the drive manifest), then
**every header read** (`mri_20_pig_probe.py`, and a per-series census):

- **Philips Medical Systems Achieva, 3 T, institution CNIC**; 6 pigs (2327, 2444, 2459, 2487, 2502, 2672), 13 scanner
  studies (pig × session), 2014-02-21 … 2014-07-16; body part HEART; protocols `WIP DTI_MEDIO SENSE` (21), `WIP RL SENSE`
  (3), `WIP ANATOMICO SENSE`, `WIP sT1W_3D_TFE SENSE` (2); series descriptions `RL` (26) and `AP` (1).
- **Each folder is one image series**: one `SeriesInstanceUID` of MR Image Storage whose `SeriesNumber` is the folder's
  last number, holding magnitude (`M_FFE`) and velocity-map (`VELOCITY MAP\P\PCA`) images: phase-contrast flow, 35,105
  images in all. Beside it, the scanner exported **52 companion objects**: in each folder, an instance of its study's
  **Raw Data Storage** object (SOP `…1.1.66`, series 0, one per study, a different instance per folder), one more object
  of the image series without an image type, and in `2459P_1_2303` two **presentation states**.
- **No file is shared between folders** (by SHA-256); no SOP Instance UID repeats.
- **Identity, without writing any value:** patient name and patient id are the pig codes in all 27; sex F; a birth date is
  present; no species tag. **Nothing suggests human data.**
- **Not DICOM:** the 27 `DICOMDIR`s are the export's index; **four files named `folders.cache` / `thumbs.cache` are MATLAB
  5.0 files** (242 MB in all with the `DICOMDIR`s), one of them inside a `DICOM\` folder.

### 9.2 The row unit (BACKLOG 🔺 "external collaborator archives are one row per EXAM, not per series")

**One row per series folder = one row per image series** (27 rows), `session_id` = the scanner study
(`HEARDSMRI<pig>P_<session>`): the internal-MRI unit, so a series is addressable and `file_count` means DICOM files on
disk, as on every MRI row. The companion objects stay with the series they were exported with (they are the scanner's own
DICOM, 52 files); splitting them into rows of their own would make 13 "series 0" rows that hold no image. The `DICOMDIR`
is not registered: it indexes a folder layout that `/raw/` does not keep, and it is regenerable; it goes to the project
folder with the masks. **Not an archive per session** (the DTS24 shape the BACKLOG item wants to undo).

### 9.3 The fields (`drive3_mri_P01_cnic_heards.yaml`, `cases_P01.csv` from `mri_21_pig_rows.py`)

| Field | Value |
|---|---|
| instrument, model | `XMRI`, `Philips Achieva 3T` (from the header) |
| `data_source` | `collaborator:CNIC` (the header's institution) |
| `sample_id`, `session_id` | `HEARDSMRI<pig>P` (the pig code the header carries), `HEARDSMRI<pig>P_<session>` |
| organism, subject | *Sus scrofa*; **no facility id** (not our animals); sex from the header; `source dicom-header` |
| `acquisition_datetime` | the series' `SeriesDate` + `SeriesTime` |
| anatomy | heart (`UBERON:0000948`; `BodyPartExamined` HEART); the masks segment the pulmonary artery |
| shape | the generic DICOM shape (as X1): `<ACQ-ID>\series\IM_*`, `primary_kind archive`, and the curated `dicom` sidecar block, whose allow-list never copies `PatientName` or `PatientBirthDate` (`ingest/dicom_headers.py`) |
| project, link | `CNIC-HEARDS`; `XMRI_<session>_<series>` |
| staging | `stage\P01\<folder>\IM_*`: **hard links** of `stage\PIG\` (0 bytes; 35,157 instances) |

### 9.4 Dry run and rehearsal

Dry run against production: 27 / 27 / 0, dated 2014, registries unchanged, and "no project link: project 'CNIC-HEARDS'
not found" for each: **the ingest would register the rows without a project** if the project were missing, which is why
§7 step 5 stops unless the dry run after the project's creation shows 27 free links. Rehearsal (§6): project created, 27 / 27 / 0, verifier 14/14 PASS, re-run 0.

### 9.5 Project creation

`tools/create_project.py` (§7 step 4), the path the Project Manager uses: next `PROJ-` id, folder `projects\CNIC-HEARDS\`
with the four subfolders, `_project.yaml`, `provenance.csv`. Name `CNIC-HEARDS` passes `validate_project_name`; no
project of that name exists. Owner: §8 M-b.

### 9.6 The masks (planned, not run)

Stream P's W5 copies the pig folder's **1,956 non-image files** (the 199 distinct ROI masks and `Split\` volumes, 27.82 GB)
to the holding folder `staging\historical_drives_unassigned\MJesus-MFB\…`. Once `CNIC-HEARDS` exists:

1. In stream P's manifest (`D:\projects\gjesus3\drive3_streams\placement\manifest_v2\placement_manifest.csv` or its
   successor), map the 1,956 rows of `Otros\Segmentaciones ITK SNAP\Segmentaciones Arteria Pulmonar cerdos\` to
   `CNIC-HEARDS` (the 2b route: `nonraw_placement.py remap --manifest <P's record manifest> --mapping <a one-group
   mapping>`, `tasks/drives_nonraw_2b_2c_followup.md` §2.2), with P's drive-3 code merged.
2. `nonraw_placement.py copy --manifest <remap out>\placement_manifest.csv --project CNIC-HEARDS` (dry run), then
   `--execute --from-holding` (§2.5): each file read from its holding copy, checked against the drive manifest's SHA-256,
   placed under `CNIC-HEARDS\working\historical_drives\MJesus-MFB\…` (≤ 240 characters, `_INDEX.csv`, README); holding
   keeps its copy. Then `verify`.
3. Add the 31 files of §8 M-c/M-d (the `DICOMDIR`s and the four MATLAB files) to the same placement: they are in no
   manifest today.

A copy-only window; the coordinator approves it (production plan, "Who may approve").

---

## 10. Proposed record lines (the coordinator applies them at merge; I edited none)

- **STATUS §2, the M. Jesús drive, stream M:** "Built, dry-run and rehearsed on `feat/drive3-mri`: 3,309 MRI exams
  production lacks (177 converted first), 189 studies, into `0118`, `0619`, `1019`, `0320`, `1116`, `0522` (M08's 13 with
  no project; M08's and M09's 35 with no subject id); and the 27 CNIC pig series as `XMRI` into a new `CNIC-HEARDS`. Waiting
  on the gate and Ryan's go. Gate: `tasks/drive3_mri_gate.md`."
- **STATUS §0.5 M2:** "Stream M built; every exam listed in `tasks/drive3_mri_for_archive_check.csv`."
- **BACKLOG 🔸 "after the platform-archive MRI ingest":** add §8 M-e (stage `<study>/<exam>`, date by `VisuCreationDate`).
- **BACKLOG 🔺 "external collaborator archives are one row per EXAM":** note that `CNIC-HEARDS` went in one row per series
  from the start (§9.2), as a worked example of the target shape.
- **`drive3_questions_for_mjesus.md`:** §8 M-a (`m145b`).
- **CHANGELOG** at the write, with the ACQ-ID ranges the write actually takes.

---

## 11. Reproducing every number

All under `D:\projects\gjesus3\drive3_streams\mri\`; read-only on `J:` and `K:` (the facility DB: `SELECT` only); run with
`PYTHONDONTWRITEBYTECODE=1` from the worktree root.

| Script | What it does | Output (`out\` unless said) |
|---|---|---|
| `mri_common.py` | paths, the write guard (nothing outside `…\drive3_streams\mri\`), helpers | — |
| `mri_01_plan.py` | A1's 3,380 exams → the per-exam plan, against the live registry; the files to stage; convert inputs | `plan_exams.csv`, `plan_studies.csv`, `plan_stage_files.csv`, `not_registered.csv`, `recon_no_dicom.csv`, `convert_input_*.csv`, `plan_summary.txt` |
| `mri_02_stage.py` | copies to `D:` verified against the drive manifest (re-run: re-hashes and keeps) | `stage\`, `stage_result*.csv` |
| `mri_03_dedup_plan.py` | the 3,965 exams production holds → their parameter files to stage | `plan_dedup_exams.csv`, `plan_stage_files_dedup.csv` |
| `convert_staged_exams.py` (WSL, `out\convert_run.sh`) | Dicomifier on the 177 | `convert_M02/M03/M05.csv` |
| `mri_04_cases.py` | the case tables from the staged exams; link names; the DEDUP date check | `tools\configs\drive3_mri\cases_*.csv`, `link_names.csv`, `dedup_date_check.csv`, `cases_check.txt` |
| `mri_05_configs.py` | the ten configs from one template | `tools\configs\drive3_mri\*.yaml` (P01 written by hand) |
| `mri_06_kcheck.py` | m175 / m178 against `K:` | `kcheck.txt` |
| `mri_07_dryruns.py`, `mri_14_check_log.py` | bracketed (dry) runs; each log checked case by case | `dryrun_*.log`, `run_*.log`, `bracket_*.json` |
| `mri_08_rehearsal_setup.py`, `mri_09_backup.py` | the rehearsal root; the backup / verifier baseline | `rehearsal_nas\`, `reh_baseline*\` |
| `mri_10_verify.py`, `mri_22_pig_verify.py` | the independent verifiers (Part 1, Part 2) | stdout |
| `mri_11_archive_check.py` | the list for the archive check | `tasks\drive3_mri_for_archive_check.csv` |
| `mri_12_for_stream_p.py` | the raw MRI not registered, for stream P | `for_stream_P.csv` |
| `mri_13_subject_check.py` | every subject id, looked up now | `subject_check.csv` |
| `mri_15_validate_new.py` | the validator, findings on the new rows apart | `validate_*.txt` |
| `mri_20_pig_probe.py`, `mri_21_pig_rows.py` | the pig headers; the row staging and case table | `pig_series.csv`, `pig_probe.txt`, `pig_rows.csv`, `pig_not_registered.csv` |
| `mri_16_p2_lists.py` | P2's input lists for stream P's tool (§12) | `out\p2\p2a_handover.csv`, `p2b_handover.csv`, `p2b_mapping.csv`, `p2b_unmapped_pig.csv` |

---

## 12. The second placement batch, P2 (planned and dry-run; nothing copied)

Asked by the coordinator on 2026-10-06 (§8 M-c, M-d): the raw MRI stream M does not register, the pig folder's 31 loose
files, and the pig masks from the holding folder into `CNIC-HEARDS`, through **stream P's tool as merged on `main`**
(`d7ee770`; merged into this branch). Copy-only; the coordinator approves the windows (production plan, "Who may
approve"). Inputs: `out\p2\` from `mri_16_p2_lists.py`, built from `out\for_stream_P.csv` (3,830 files).

### 12.1 What goes where

| Part | Files | Route | Result of the plan (dry runs) |
|---|---:|---|---|
| **P2a** the MRI files | 3,754 | `p_plan.py handover` (stream M) → `nonraw_placement.py copy` / `holding` | **2,919 to place** in `AE-biomaGUNE-0118` (2,393), `-0619` (440), `-1019` (86), 1.83 GB; **56 to holding** (the 2021 `1019` MRS exams, project-less as their image exams, STATUS D6); 602 `already-in-holding` and 33 `duplicate-copy` (bytes already there; not copied); **144 refused, all by design**: 57 already decided by stream P's first batch, 87 `desktop.ini`. Longest path 193 (holding 240), 0 over budget, 0 destinations present. Planned twice: byte-identical manifests |
| **P2b** the 31 pig files | 31 | `handover` with project `CNIC-HEARDS` | **31 to place** (27 `DICOMDIR`, and the 4 MATLAB files **kept by path**, below), 0.24 GB, longest 197, 0 refused |
| **P2b** the masks | 1,791 | 2b `remap` (36 group keys → `CNIC-HEARDS`) → `copy --from-holding` | **1,791 to place**, 25.40 GB, longest 208; all 1,791 holding copies checked on `J:` (present, the manifest's size) |
| left in holding | 165 | — | §12.3 |

- **Left out of P2a on purpose: 45 files** of the divergent m175/m178 copies whose bytes equal DICOM that Part 1 registers;
  after the write they are in `/raw/`, and raw is never placed. (`/raw/` keeps DICOM only, so the copies' parameter
  files, `2dseq` and k-space are placed.)
- **The four MATLAB files named `thumbs.cache` / `folders.cache`:** `handover` refuses those names as junk (A2's rule).
  **One change to stream P's tool** (`p_plan.py`): a handover row may carry `keep_despite_name=Y` with a reason; it lifts
  only the junk-NAME rule for that one path (AppleDouble, installers and Office temp files stay refused) and prints
  `KEPT DESPITE ITS NAME`. Test: `tools/test_drive3_placement.py` `test_handover_keep_despite_name` (kept with a reason;
  refused without one; AppleDouble refused even when flagged); the file passes ("all passed").
- **P2b can be dry-run against production only once `CNIC-HEARDS` exists** (`handover` and `remap` refuse a project not
  in the registry). Its plan above ran against the rehearsal root, where §6 created the project; the holding copies the
  masks are read from were checked on `J:` directly.

### 12.2 Production commands (copy-only; the window procedure of `drive3_placement_gate.md` §5)

**Order and windows (✅ the coordinator, 2026-10-06).** **P2a after §7 step 3**; **P2b after §7 step 6** (the project
exists and P01's links are in). Both copy-only. P2a writes `provenance.csv` and the index documents of `0118`, `0619`,
`1019`: **neither batch may run during Part 1, nor while a Cell Observer batch is writing provenance into `0619` or
`1019`.** PowerShell, from this worktree (or `main` once merged), `$env:PYTHONDONTWRITEBYTECODE=1`,
`$env:PYTHONPATH='tools'`:

```powershell
$NAS = 'J:\gjesus3-data'; $NP = 'tools\drive_staging\nonraw_placement.py'; $PV = 'tools\drive_staging\drive3\p_verify.py'
$PP  = 'tools\drive_staging\drive3\p_plan.py'; $O = 'D:\projects\gjesus3\drive3_streams\mri\out\p2'
$M1  = 'D:\projects\gjesus3\drive3_streams\placement\manifest_check2_20261006\placement_manifest.csv'
$M2  = 'D:\projects\gjesus3\drive3_streams\placement\release_M1_20261006\placement_manifest.csv'
$SCR = "$O\scratch"; $D = Get-Date -Format yyyyMMdd_HHmm

# P2a. 0. Re-plan against today's /raw/ (refuses bytes already in /raw/; expect the counts of 12.1)
python $PV raw-dedup --manifest $M1 --nas $NAS --write-index "$O\live_raw_index_$D.csv"
python $PP --nas $NAS handover --manifest $M1 --manifest $M2 --csv "$O\p2a_handover.csv" --stream M --raw-index "$O\live_raw_index_$D.csv" --out "$O\P2a_$D"
#    expect: "handover (M): 3610 files {'already-in-holding': 602, 'holding': 56, 'place': 2919, 'duplicate-copy': 33}; refused 144"
#    (57 "already decided in an earlier batch", 87 desktop.ini); exit code 1 because of the refusals, by design.
#    After Part 1 is written: the 45 left-out files are already absent; any OTHER new refusal "in /raw/" is a STOP.
$A = "$O\P2a_$D\placement_manifest.csv"
# 1. per project (AE-biomaGUNE-0118, -0619, -1019): snapshot, dry run, execute, verify
foreach ($p in 'AE-biomaGUNE-0118','AE-biomaGUNE-0619','AE-biomaGUNE-1019') {
  python $PV snapshot --manifest $A --nas $NAS --project $p --to "C:\Users\rtasseff\temp\gjesus3_placement_backup_${D}_drive3_P2a_$p"
  python $NP --out "$O\runs_P2a" --nas $NAS copy --manifest $A --scratch $SCR --project $p            # dry: 2393 / 440 / 86 files
  python $NP --out "$O\runs_P2a" --nas $NAS copy --manifest $A --scratch $SCR --project $p --execute
  python $NP --out "$O\runs_P2a" --nas $NAS verify --manifest $A --project $p
  python $PV verify --manifest $A --nas $NAS --snapshot "C:\Users\rtasseff\temp\gjesus3_placement_backup_${D}_drive3_P2a_$p" --project $p --rehash sample
}
# 2. holding (56 files)
python $PV snapshot --manifest $A --nas $NAS --holding --to "C:\Users\rtasseff\temp\gjesus3_placement_backup_${D}_drive3_P2a_holding"
python $NP --out "$O\runs_P2a" --nas $NAS holding --manifest $A --scratch $SCR             # dry: 56 files, longest <= 240
python $NP --out "$O\runs_P2a" --nas $NAS holding --manifest $A --scratch $SCR --execute
python $PV verify --manifest $A --nas $NAS --snapshot "C:\Users\rtasseff\temp\gjesus3_placement_backup_${D}_drive3_P2a_holding" --holding --rehash sample

# P2b (after §7 step 6). 3. Plan against production now that CNIC-HEARDS exists
python $PP --nas $NAS handover --manifest $M1 --manifest $M2 --manifest $A --csv "$O\p2b_handover.csv" --stream M --out "$O\P2b_$D"
#    expect: 4 "KEPT DESPITE ITS NAME" lines; "31 files {'place': 31}; refused 0"
python $NP --out "$O\P2b_masks_$D" --nas $NAS remap --manifest $M1 --mapping "$O\p2b_mapping.csv"
#    expect: "36 mapped groups; 1791 holding files re-decided {'place': 1791}; 0 mapped groups matched no holding file"
$B = "$O\P2b_$D\placement_manifest.csv"; $K = "$O\P2b_masks_$D\placement_manifest.csv"
# 4. CNIC-HEARDS, window 1: the 31 files
python $PV snapshot --manifest $B --nas $NAS --project CNIC-HEARDS --to "C:\Users\rtasseff\temp\gjesus3_placement_backup_${D}_drive3_P2b_files"
python $NP --out "$O\runs_P2b" --nas $NAS copy --manifest $B --scratch $SCR --project CNIC-HEARDS           # dry: 31 files, 0.24 GB
python $NP --out "$O\runs_P2b" --nas $NAS copy --manifest $B --scratch $SCR --project CNIC-HEARDS --execute
python $NP --out "$O\runs_P2b" --nas $NAS verify --manifest $B --project CNIC-HEARDS
python $PV verify --manifest $B --nas $NAS --snapshot "C:\Users\rtasseff\temp\gjesus3_placement_backup_${D}_drive3_P2b_files" --project CNIC-HEARDS --rehash all
# 5. CNIC-HEARDS, window 2: the masks from holding (a new snapshot: window 1's files are then "before", not extra)
python $PV snapshot --manifest $K --nas $NAS --project CNIC-HEARDS --to "C:\Users\rtasseff\temp\gjesus3_placement_backup_${D}_drive3_P2b_masks"
python $NP --out "$O\runs_P2b" --nas $NAS copy --manifest $K --scratch $SCR --project CNIC-HEARDS --from-holding   # dry: 1791 files, 25.40 GB, 0 "NOT there"
python $NP --out "$O\runs_P2b" --nas $NAS copy --manifest $K --scratch $SCR --project CNIC-HEARDS --from-holding --execute
python $NP --out "$O\runs_P2b" --nas $NAS verify --manifest $K --project CNIC-HEARDS
python $PV verify --manifest $K --nas $NAS --snapshot "C:\Users\rtasseff\temp\gjesus3_placement_backup_${D}_drive3_P2b_masks" --project CNIC-HEARDS --rehash sample
# 6. The README for the 165 pig files left in holding (§12.3 P2-a), outside the placement tree (metadata\)
Copy-Item 'tools\configs\drive3_mri\README_CNIC-HEARDS_pig_files_in_holding.txt' "$NAS\projects\CNIC-HEARDS\metadata\"
(Get-FileHash "$NAS\projects\CNIC-HEARDS\metadata\README_CNIC-HEARDS_pig_files_in_holding.txt").Hash -eq (Get-FileHash 'tools\configs\drive3_mri\README_CNIC-HEARDS_pig_files_in_holding.txt').Hash   # True
```

**Stop conditions:** a plan count other than 12.1's; a refusal of a new kind; a dry run with destinations already present
or a path over 240; `--from-holding` reporting any file "NOT there"; any verify not PASS. **Rollback:** copies only; the
snapshot of each window lists what was there before (`p_verify.py`); the holding copy of the masks stays in holding
(holding is never trimmed), so the masks exist twice after P2b, as stream P's option B accepted for mapped groups.

### 12.3 Left for the coordinator

| # | Item | Recommendation |
|---|---|---|
| **P2-a** ✅ **decided (coordinator, 2026-10-06): they stay in holding**; `CNIC-HEARDS\metadata\README_CNIC-HEARDS_pig_files_in_holding.txt` says so (§12.2 step 6); a path-level remap goes to the BACKLOG. | **165 pig files (2.43 GB) stay in holding**: 148 `Split` volumes (`.mhd` + `.raw`) and 17 masks of `HEARDSMRI2444P_1_2000`. Their 2b group key `D3||Otros\Segmentaciones ITK SNAP` (no claim) also holds two mouse London segmentations (`Segmentaciones ratones\…\jrc200708_m53_london_1_1\Segmentation_time11/12_m53.nii.gz`), and a 2b mapping moves whole groups. | Leave them in holding for now (`out\p2\p2b_unmapped_pig.csv` lists them), and say so in `CNIC-HEARDS`'s README. The clean fix is a path-level mapping in `remap` (a small change to stream P's tool, with a test): not built here, by the coordinator's "no new analysis". Mapping the whole group would put the two mouse files into a pig project: not recommended. |
| **P2-b** ✅ reviewed and accepted (coordinator, 2026-10-06) | The tool change (`keep_despite_name`) is in stream P's shared tool. | Opt-in per row; cannot affect batch 1. |
