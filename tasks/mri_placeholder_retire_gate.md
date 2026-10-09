# Retiring the DICOM-less MRI placeholders (`no-dicom`) — the set, the change, the rehearsal and the production commands (for the gate)

**Status:** 🔶 READY FOR THE COORDINATOR'S GATE (nothing written to production) · **Date:** 2026-10-08 ·
**Branch:** `feat/mri-placeholder-retire` · **Ruling:** Ryan, 2026-10-08: *"retire them. If they are attached to
projects we can move the images and sidecars to the project folder."* (BACKLOG "🔸 MODERATE — existing MRI rows that
fall outside the 2026-10-04 line") · **Precedents:** the retire tool's first uses (CHANGELOG 2026-10-02, 10-04, 10-04/05)

**Read-only on production.** Nothing under `J:\gjesus3-data\` was created, changed or deleted: the census, the lists,
the dry runs and the snapshot only read it. The rehearsal ran on a `D:` copy. Working folder (scripts, lists, logs):
`D:\projects\gjesus3\mri_placeholder_retire\`. **Run after the MRI archive ingest and the drive-3 `XMIC` batch** (one
registry writer at a time), and after the drive-3 close-out has placed the 10 exams' k-space (§3.4).

---

## Summary

1. **The set: 464 live MRI rows, exactly** (§1): `pending_dicom_regen` 365 `not-applicable` (STEAM 286, PRESS 74,
   WOBBLE 5) + 99 `no-source`. Three independent counts agree: the worklist (464 terminal no-image rows, all live), the
   registry (464 MRI rows with `file_count` 0, and no other), and the disk (464 empty `.data\`; the other 16,138 live
   MRI/XMRI primaries all hold files). Each folder holds exactly `metadata.json`, `checksums.json`, `README.txt`
   (85.9 MB in all).
2. **Where they are:** 324 in 16 active projects, **135 in `AE-biomaGUNE-0220` (closed)**, **5 with no project** (the
   G1 session `jrc250526_145_0522`, all of whose 24 exams have no project by the standing decision).
3. **The change:** a sixth retire disposition, **`no-dicom`** (§2), in `tools/retire_acquisition.py` (+ its mirror
   `tools/ingest/retired.py`, the validator, 06 / 09 / 10 / 11 and `tools/INDEX.md`). The row moves to the tombstone
   file; every file of the `/raw/` folder is hard-linked into `<project>\working\mri_not_registered\<study>\<exam>\`
   beside a `README_not_registered.txt`, verified by SHA-256, and only then does the `/raw/` folder go. The empty
   project link folder is removed; a link name that holds files (another acquisition's) is left alone.
   `pending_dicom_regen`: the rows leave the worklist with the registry row (kept verbatim in the tombstone), the
   tool's convention; afterwards the worklist holds only `regenerated` rows.
4. **Dry runs on production (read-only):** `open` 324 items, rc 0, links 312 `remove` + 3 `foreign`; `no_project` 5,
   rc 0; `closed` 135 refused (`AE-biomaGUNE-0220` is closed) — by design.
5. **Rehearsal on a `D:` copy** (registries, the 464 folders, the 17 projects' link entries and provenance, taken from
   production at 19:40): all 464 retired in the production order (reopen `0220` → `open` with an injected crash →
   resume → `closed` → `no_project`), every re-run a no-op, **`INVARIANTS: ALL OK`** (§5), validator 0 errors before
   and after, the lists empty afterwards. 1,392 files moved, each SHA-256-identical; 447 empty link folders removed and
   the other 260 link entries untouched; registry rows −464 exactly, every other record byte-identical.
6. **Live ingest (§6): written up for BACKLOG, not changed.** The skip touches `ingest_raw.run_batch`, which the operator
   exe runs, needs a third outcome in its results, and has two questions for Ryan. The re-ingest block on `no-dicom`
   tombstones stays until that change lands.
7. **For Ryan (§8):** the holding folder for the 5 no-project exams (proposed `staging\mri_not_registered\`);
   `AE-biomaGUNE-0220`'s 135 wait for its reopening (the archive ingest reopens it); 27 `no-source` exams whose study
   the platform's archive holds were never checked there for a reconstruction.

---

## 1. The set

**Counted afresh on 2026-10-08 19:07** (`--build-no-dicom-lists`, and `census.py` for the disk side):

| Check | Result |
|---|---|
| `pending_dicom_regen.csv` | 628 rows: 164 `regenerated`, **365 `not-applicable`**, **99 `no-source`**; all 464 terminal no-image rows are live, none tombstoned |
| `registry_raw.csv`: MRI rows with `file_count` 0 | **464**, exactly the worklist's 464 (no other row of any instrument has `file_count` 0) |
| `/raw/` on disk | the 464 `.data\` folders are empty; **the other 16,138 live MRI/XMRI primaries all hold files** (scan of every one) |
| What each folder holds | exactly `README.txt`, `checksums.json`, `metadata.json` (464 × 3 files, 85,877,551 bytes) |
| Ingest configs | `mri_jrc_animalfirst_regen.yaml` 431, `mri_jrc_projfirst_regen.yaml` 28 (the June ingest), `mri_0522_m145_irene.yaml` 5 (G1) |
| ACQ-ID date ≠ the exam's date | 96 (the "registered with today's date" class: an aborted exam has no `visu_pars`); the destination folder is named by the exam, so this does not carry over |

**By class and destination:**

| Class (`pending_dicom_regen`) | Active project | `AE-biomaGUNE-0220` (closed) | No project | Total |
|---|---:|---:|---:|---:|
| `not-applicable` STEAM (spectroscopy) | 226 | 60 | — | 286 |
| `not-applicable` PRESS (spectroscopy) | — | 74 | — | 74 |
| `not-applicable` WOBBLE (calibration) | 5 | — | — | 5 |
| `no-source` (no reconstruction to convert) | 93 | 1 | 5 | 99 |
| **Total** | **324** | **135** | **5** | **464** |

Per project: `0721` 166 (STEAM 144, no-source 21, WOBBLE 1) · `0220` 135 · `0219` 82 (STEAM 69, no-source 12, WOBBLE 1)
· `0423` 27 · `0522` 16 (no-source 14, WOBBLE 2) · `1321` 11 · `1123` 6 · `0618` 4 · `1022` 4 · and one each in `0320`,
`0420`, `0424`, `0525`, `1019`, `1025`, `1422`, `1521` · no project 5.

**Project links** (found, as the tool does, through each project's `provenance.csv`):

- **312** placeholders have a link entry that is an **empty folder** → removed (an event row each).
- **3** have a provenance row whose link name now holds **another acquisition's files** (the name was taken; the
  2026-10-05 link-collision repair). Left alone, reported `foreign`:
  `ACQ-20221222-MRI-007` → `AE-biomaGUNE-0721\raw_linked\MRI_m78_0721_20221222_4_1` (9 files) ·
  `ACQ-20240422-MRI-011` → `…\MRI_m201_0721_20240422_4_1` (3 files) · `ACQ-20240422-MRI-029` → `…\MRI_m201_0721_20240422_6_1` (22 files).
- **9** in active projects have no link entry at all (the coordinator's audit's "planned name held by another
  acquisition" cases are among these and the 3 above). Nothing to remove; their files still move.
- **135** in `0220`: no entry today (the project's folder was emptied by the 2026-07-14 close-out). **`reopen_project.py`
  recreates one empty link folder for each** (rehearsed: 392 links created, 135 of them empty); the retirement then
  removes those 135.
- The tool removes a link folder only if it is **empty at the moment of removal** and no other *live* acquisition's
  provenance names the same entry; anything else is reported and left.

**Not cited** by any curated dataset (the dry run checks every id against `registry_datasets.csv` and every text
file under `curated_datasets\`).

**The 10 drive-3 exams.** The drive-3 close-out found k-space (no reconstruction) for 10 of these placeholders on
M. Jesús's staged drive and places it in the projects now (its handover, kind `notregistered:no-recon`):
`ACQ-20241001-MRI-099`, `ACQ-20241001-MRI-100`, `ACQ-20260613-MRI-028`, `ACQ-20260613-MRI-029`, `ACQ-20260614-MRI-002`,
`ACQ-20260614-MRI-048` (`AE-biomaGUNE-0522`), `ACQ-20241010-MRI-104`, `ACQ-20260614-MRI-007` (`-1123`),
`ACQ-20260613-MRI-007` (`-0320`), `ACQ-20260613-MRI-039` (`-1422`). The list builder finds every placed copy of an
exam in the projects' `working\historical_drives\_INDEX.csv` (and the holding manifest) and writes it as `see_also`;
the README and the tombstone's evidence then point at it (§3.4). At 19:07 only 1 was found (an `audita.txt` of `-099`,
placed by an earlier batch); **by 19:40 the close-out had placed them, and the lists built on the rehearsal copy
point all 10 at their exam folders** (e.g. `ACQ-20260613-MRI-007` →
`projects\AE-biomaGUNE-0320\working\historical_drives\MJesus-MFB\Proyecto 0320\CAV1 Female 2022\20220214_092942_jrc220214_m44_0320_1_1\33`).

**27 of the 99 `no-source` exams belong to studies the platform's archive holds** (census of 2026-10-07: "in
production (name)", so not pulled). `no-source` was established on the scanner host (`kenia`); the archive's copies of
those studies were never opened to look for a reconstruction. Drive 3's check against the archive found 0
differences, so a different result is unlikely. Listed in `D:\…\mri_placeholder_retire\archive_overlap.csv`. §8.

---

## 2. The disposition and the spec change

**`no-dicom`** — a Data Office vocabulary call, made (HANDOFF). Integrity mirror kept: `tools/ingest/retired.py`
(`DISPOSITIONS` + new `NO_SUPERSEDER = ("orphan", "no-dicom")`), `tools/validate_registries.py` (blank
`superseded_by` allowed for both), [06_REGISTRIES §2.6 / §2.9 / §2.9.1 / §2.9.2](../mfb-rdm-docs/06_REGISTRIES.md).
**Columns unchanged.**

| Tombstone field | `no-dicom` |
|---|---|
| `superseded_by` | blank (nothing supersedes it) |
| `bytes_fate` | `moved` |
| `moved_to` | the folder the files went to, e.g. `/projects/AE-biomaGUNE-1521/working/mri_not_registered/20220119_081642_jrc220119_m10_1521_1_1/3/` |
| `sha256` | over the moved files (`relpath<TAB>sha256` list; the primary is empty) |
| `reason` | the reason (spectroscopy / calibration with its marker, or no convertible reconstruction; the 2026-10-04 line; Ryan's ruling) + ` \|\| evidence: {"method":"no-dicom/1","pending_dicom_status":…,"nonimage_marker":…,"files":{name: sha256},"see_also":[…]}` |
| `other_rows_removed` | the `ingest_manifest` and `pending_dicom_regen` rows (one item also a `pending_subject_metadata` row), verbatim |

**Preconditions (refused otherwise, the whole list stops before a write):** live; `pending_dicom_regen` status
`not-applicable` or `no-source` (a `pending` exam can still get its DICOM; `regenerated` has it); the registry records
an empty folder primary (`file_count` 0) **and the primary holds no file on disk**; the project is active and its
folder exists (closed → `reopen_project.py` first); with no project, the destination is under `staging\`; every
`see_also` exists; the destination holds nothing else; not cited by a curated dataset; not inside an ingest's window.

**Docs changed (surgical):** 06 §2.6 row, §2.9 text + schema rows + the re-ingest rule; 09 §1 the 🔶 open point → ✅
decided; 10 §3.9 (status, usage, list columns, the table row, order, the re-ingest note), §3.8 (the worklist after
the batch), §3.2 (validator line); 11 §5.7 (`no-dicom` paragraph, restore); `tools/INDEX.md`; 00_INDEX Last Updated.
**Re-ingest stays blocked** for `no-dicom` like every tombstone (the dedup index holds its `(date, original_name)`): a
DICOM made later for a `no-source` exam is registered by the Data Office. Lifting the block belongs with §6.

**Code** (`tools/retire_acquisition.py`, extended, no new framework): `plan_no_dicom`, `place_no_dicom`,
`notreg_readme`, the `no-dicom` branches of the link plan / events / bytes / backup (the whole folder) / tombstone /
self-check, and `--build-no-dicom-lists` (read-only). Plus one shared speed-up: `ingest/csv_safe.split_records` now
finds newlines and counts quotes with `bytes.find` / `bytes.count` — the same records (checked against the old
byte-by-byte loop on 3,008 inputs and on the 20 MB registry), about 40 times faster; the tool splits the registry twice
per id. Tests: new `tools/test_retire_no_dicom.py` (list builder, refusals, execute, holding, crash-resume at all six
injection points, validator, dedup block); the v1 / v2 suites unchanged and green.

## 3. Where the files go

### 3.1 In a project: `<project>\working\mri_not_registered\<study>\<exam>\`

- `<study>\<exam>` is the exam's own ParaVision identity (its `original_name`), unique by construction, readable,
  and the same layout the historical-drives placements use for not-registered exams (`working\historical_drives\…\<study>\<exam>\`).
  *Alternative considered:* folders named like the old link (`MRI_m10_1521_20220119_3_1`): not unique (5 exams share
  `MRI_m201_0721_20240422_4_1`), and 96 carry the wrong (registration) date. The README names the old link instead.
- `working\` follows the drives precedent for Data-Office-placed other data. The files are **hard links** of the
  `/raw/` files (no copy), verified by SHA-256 before the `/raw/` name goes.
- One `README_not_registered.txt` per exam folder, plain language, e.g. (rehearsal output):

```
NOT REGISTERED IN gjesus3 -- KEPT HERE AS OTHER DATA
====================================================

This folder holds what gjesus3 kept of one MRI exam. The exam was registered as
ACQ-20220119-MRI-039 with no image, before the Data Office rule of 2026-10-04: an MRI scan
is registered only with a reconstructed image stored as DICOM. It was then
retired from the registry (registries\retired_acquisitions.csv); nothing was deleted.

  Exam (ParaVision study\exam):  20220119_081642_jrc220119_m10_1521_1_1\3
  Registered as (now retired):  ACQ-20220119-MRI-039
  Its project link raw_linked\MRI_m10_1521_20220119_3_1 was an empty folder and was removed.

Why it is not registered:
  - it is spectroscopy or calibration (STEAM), not an image.

The files here are byte-for-byte the ones gjesus3 held for it:
  metadata.json    the exam's parameters, as gjesus3 read them from the scanner's files
  checksums.json, README.txt    the registration's own records (they name the retired id)

Spectroscopy and calibration scans are not registered in gjesus3; the MRI
platform keeps its own records of them.
```

  A `no-source` exam says instead: *"the scanner kept no reconstructed image of it that could be converted to DICOM
  (only its parameters, or raw scanner data) … If someone later produces DICOM images from this exam, it CAN be
  registered then: ask the Data Office."* A `see_also` adds *"Other files of this exam, copied from the lab's
  historical drives, are in: projects\…"*.
- **Provenance:** one `moved-to` row per exam folder (`file_type` `folder`, `input_refs` the retired id), one
  `link-removed` row per removed link; written before the action (the tool's write-ahead rule).

### 3.2 `AE-biomaGUNE-0220` (closed): 135

The tool refuses a closed project (as for derivatives). The MRI archive ingest's gate has the coordinator reopen
`0220` (STATUS §0.6 Q5); this batch runs after it. Rehearsed in that order: `reopen_project.py` on the copy (392 links,
135 of them the placeholders' empty folders), then the `closed` list: 135 retired, 135 empty links removed. If `0220`
is still closed at run time, run the `open` and `no_project` lists and hold this one (§8).

### 3.3 No project: 5 → proposed `staging\mri_not_registered\<study>\<exam>\`

The G1 session (`jrc250526_145_0522`, animal 145 of protocol 0522): its 19 DICOM exams have no project either. Same
layout and README, no provenance (no project). A separate folder, not `staging\historical_drives_unassigned\`: that one
is indexed by the placement tool's `manifest.csv`, which these files would not be in. **Ryan's call** (§8); the tombstone
keeps the record either way, and nothing is deleted.

### 3.4 The 10 drive-3 exams

`see_also` per exam = every placed folder of the same `<study>\<exam>` (projects' `working\historical_drives\_INDEX.csv`,
the holding `manifest.csv`), resolved at list-building time and checked to exist at plan time. Build the lists **after**
the close-out's placement; the summary line `with see_also N` shows it (expect 10; the rehearsal copy, taken after the
placement, has 10). The README then ends: *"Other files of this exam, copied from the lab's historical drives, are
in: projects\AE-biomaGUNE-0320\working\historical_drives\MJesus-MFB\…\33"*; the tombstone's evidence carries the same
path.

## 4. Production dry runs (read-only, 2026-10-08 19:07–19:13)

`python tools\retire_acquisition.py --nas-root J:\gjesus3-data --list <list>` (logs:
`D:\…\mri_placeholder_retire\lists_prod_20261008\dryrun_*.log`):

| List | rc | Result |
|---|---|---|
| `no_dicom_open.csv` | 0 | `324 item(s): 324 with work`; each "hard-link 3 file(s) … write README_not_registered.txt", "delete /raw/ folder (its primary is empty)", rows `registry_raw` 1 + `ingest_manifest` 1 + `pending_dicom_regen` 1 (one item + `pending_subject_metadata` 1); links **312 `remove` + 3 `foreign`**; 0 WARN |
| `no_dicom_closed.csv` | 2 | 135 × "project AE-biomaGUNE-0220 is closed … reopen_project.py" — nothing written, as designed |
| `no_dicom_no_project.csv` | 0 | `5 item(s): 5 with work`, to `/staging/mri_not_registered/20250526_105636_jrc250526_145_0522_1_1/<exam>/` |

## 5. Rehearsal on a `D:` copy

**The copy** (`rehearsal_setup.py`, production only read): `registries\` (every CSV and `.acq_id_seq.json`, mtimes
kept), the 464 `/raw/` folders whole, an empty skeleton folder for every other live row (35,157, so the validator's
"folder exists" check runs), and for the 17 projects their `provenance.csv`, `_project.yaml`, the 315 link entries the
placeholders' provenance names (312 empty folders, the 3 foreign ones with their files), `working\historical_drives\_INDEX.csv`
and the 10 `see_also` folders. Taken at ~19:40, after the drive-3 close-out had placed the 10 exams and the NI live sync
had added 8 rows (35,621 live). Curated datasets were not copied (the production dry run checks citations).

**The run** (`rehearse.py`; logs `D:\…\mri_placeholder_retire\rehearsal2_run2\NN_*.log`, summary `rehearsal_summary.txt`):

| # | Step | Result |
|---|---|---|
| 1 | `--build-no-dicom-lists` on the copy | the same items, destinations and reasons as production's 19:07 lists; `see_also` on 10 (9 more than at 19:07: placed since) |
| 2 | validator | 0 errors, 0 warnings (`--no-enrichment`) |
| 3 | dry runs `open` / `closed` / `no_project` | rc 0 / 2 (135 × "closed") / 0; **the copy byte-identical before and after** (full snapshots equal) |
| 4 | `reopen_project.py AE-biomaGUNE-0220` (as the archive ingest will) | 392 links created from the close-out backup's names, 135 of them the placeholders' (empty); status active |
| 5 | dry run `closed` again | rc 0, 135 with work, 135 `remove` |
| 6 | execute `open` with `RETIRE_FAIL_AFTER=links` | **refused first: `registry_raw.csv changed 8.2 min ago`** — the copy keeps production's mtime and the NI sync had just written; the window check did its job. Re-run with `--allow-recent-registry-writes` (nobody writes the copy): rc 4 after the first item, as injected |
| 7 | execute `open` (resume) | rc 0, `self-check: OK for 324 item(s)`, 519 s (1.6 s per id) |
| 8 | re-run `open` | `324 item(s): 0 with work` — no-op |
| 9 | execute `closed`, re-run | rc 0, OK for 135, 198 s; no-op |
| 10 | execute `no_project`, re-run | rc 0, OK for 5; no-op |
| 11 | `invariants.py check` S1 → S2 | **ALL OK** (below) |
| 12 | validator; lists again | 0 errors; 0 / 0 / 0; `pending_dicom_regen` 164 rows, all `regenerated` |

**Invariants (S1 = after the reopen, before any retirement; S2 = after):**
- `registry_raw.csv` 35,621 → 35,157: **the removed rows are exactly the 464**, every other record byte-identical;
  `ingest_manifest.csv` −464, `pending_dicom_regen.csv` 628 → 164, `pending_subject_metadata.csv` −1 (the one item's),
  `pending_links.csv` unchanged, each with every other record byte-identical; `registry_subjects.csv`,
  `registry_datasets.csv`, `.acq_id_seq.json` unchanged.
- `retired_acquisitions.csv` append-only; 464 new tombstones = the set, each `no-dicom` / `moved` / a folder.
- **1,392 moved files SHA-256-identical** to their `/raw/` source; a README and the evidence for each; the 464 `/raw/`
  folders gone.
- **447 link entries removed (312 + 135), every one an empty folder; the other 260 link entries unchanged** (the 3
  foreign ones among them, byte-identical).
- every `provenance.csv` append-only, every new row this retirement's; no other file under `raw\`, `projects\`,
  `staging\` changed; no other directory removed.

**Speed.** `split_records` made the per-id commit about twice as fast (3.5 s → 1.6 s per id on `D:`). Over the share
the registry is rewritten and read back twice per id, so expect the 464 to take roughly 30–60 minutes in production
(open ~20–40, `0220` ~10–15, no project ~1).

## 6. Live ingest: written up for BACKLOG (not changed)

The ingest still registers a spectroscopy / calibration exam as an empty placeholder (`ingest_raw.ingest_single`,
`copy_strategy: mri_paravision_v2`, the block after `copy_mri_paravision` returns no file, ~L1181–1230: it queues
`pending_dicom_regen` `not-applicable`). **Not changed here, because:** `ingest_raw.run_batch` is what the operator exe
runs (`tools/operator/runner.py`), so the change needs an exe rebuild and redeploy; "skipped, not registered" is a third
outcome the batch summary and the GUI's `(acq_id, ok)` results do not have; and two questions are Ryan's. **Text for
the coordinator to put under the existing BACKLOG item (its third box):**

> - [ ] **Live ingest: skip non-image exams (written up 2026-10-08, `feat/mri-placeholder-retire`).** Before the ACQ-ID
>   is allocated, when `copy_strategy` is `mri_paravision_v2` and `paravision_regen.is_nonimage_exam(source)` matches
>   (STEAM / PRESS / WOBBLE), report the exam as NOT REGISTERED (spectroscopy / calibration, the 2026-10-04 line) in the
>   log and in a BATCH SUMMARY section like NOT PARSED, and do not register it; optional `--not-registered-report <csv>`.
>   Needs: a third result state through `operator/runner.py` and the GUI, an exe rebuild + redeploy, tests. **Questions
>   (Ryan):** (a) a spectroscopy exam that carries an exported MRS DICOM: skip too? (the line says no reconstructed image
>   of any kind is registered); (b) an aborted exam with no data (BACKLOG LOW "an exam that produced no data is
>   registered with today's date"): the same skip? (c) the exam's own parameter files: leave them on the platform, or
>   place them in the project like the retired ones? **With it:** exempt `no-dicom` tombstones from the dedup index
>   (`ingest/config._build_dedupe_index`), so a DICOM made later registers by a normal ingest; only safe once the skip
>   exists, or a re-run would register a spectroscopy placeholder again.

## 7. Production commands (the coordinator)

PowerShell, from `gjesus3-pilot` after the merge. **One list per run**, each its own go.

```powershell
cd "C:\Users\rtasseff\OneDrive - CIC biomaGUNE\projects\DataInfra\gjesus3-archive\gjesus3-pilot"
$env:PYTHONDONTWRITEBYTECODE = 1
$NAS = "J:\gjesus3-data"
$W   = "D:\projects\gjesus3\mri_placeholder_retire"
$O   = "$W\prod_$(Get-Date -Format yyyyMMdd_HHmm)"
$RA  = "tools\retire_acquisition.py"
$INV = "$W\invariants.py"
```

**0. Preconditions — stop if any fails.**

```powershell
git log -1 --oneline                                                # the merge of feat/mri-placeholder-retire
Test-Path "$NAS\registries\.registry.lock"                          # False
python tools\validate_registries.py --nas-root $NAS --no-enrichment # "validation OK: 0 errors"
Select-String -Path "$NAS\registries\registry_projects.csv" -Pattern "^PROJ-0016," | % Line   # active or closed?
```

- The MRI archive ingest and the drive-3 `XMIC` batch are **finished**, and nobody else is writing the registry (the
  tool cannot see an ingest between its batches; 11 §5.7). **That includes the NI live-box sync:** it registered 8
  CT/PET rows at 19:40 on 2026-10-08 while this gate was being prepared (`molecubes_ni_live.yaml`), so make sure it is
  not due during the run.
- The drive-3 close-out's placement of the 10 exams is done and verified (or decide to run without their pointers).

**1. Lists, from the live registry (read-only).**

```powershell
python $RA --nas-root $NAS --build-no-dicom-lists "$O\lists"
```

Expected (if nothing moved since 2026-10-08): `not-applicable / no-source live: 464`; `not live: 0`;
`open: 324 … with see_also 10` (459 if `0220` is reopened, and `closed: 0`); `closed: 135`; `no_project: 5`; **no
`PROBLEM` line** (exit 0). **Stop if** the total is not 464 (find out why: the archive ingest should register no
placeholder), there is a `PROBLEM`, or `with see_also` < 10.

**2. Snapshot before (read-only; writes only under `$O\before\`).**

```powershell
python $INV snapshot --nas $NAS --out "$O\before\snap.json" --light --lists "$O\lists" --tools tools
```

It hashes the registries and the 464 `/raw/` folders, copies the registries and the touched `provenance.csv`, and
records every `raw_linked\` entry of the 17 projects (name, file count, bytes). Tried on production at 19:30 (read-only):
2 minutes, 1,420 files hashed, 18,490 link entries.

**3. Dry runs (read-only).** Read every line.

```powershell
python $RA --nas-root $NAS --list "$O\lists\no_dicom_open.csv"       > "$O\dry_open.log";       $LASTEXITCODE
python $RA --nas-root $NAS --list "$O\lists\no_dicom_closed.csv"     > "$O\dry_closed.log";     $LASTEXITCODE
python $RA --nas-root $NAS --list "$O\lists\no_dicom_no_project.csv" > "$O\dry_no_project.log"; $LASTEXITCODE
Select-String -Path "$O\dry_*.log" -Pattern "REFUSED|WARN|item\(s\)"
(Select-String -Path "$O\dry_open.log" -Pattern "link: remove").Count    # 312
(Select-String -Path "$O\dry_open.log" -Pattern "link: foreign").Count   # 3 (the three of §1)
```

Expected: `open` rc 0, `324 item(s): 324 with work, 0 already done`, 312 `remove`, 3 `foreign`, no REFUSED / WARN;
`closed` rc 2 with 135 "is closed" refusals — or, once `0220` is reopened, rc 0, `135 … with work`, 135 `remove`;
`no_project` rc 0, `5 item(s)`. A `WARN: registry_raw.csv changed … min ago` means a writer was active: wait and
confirm, never override blindly.

**4. Ryan's go** on exactly that dry-run output. `no_project` needs his yes on the holding folder (§8).

**5. Execute, one list at a time; each re-run must be a no-op.**

```powershell
python $RA --nas-root $NAS --list "$O\lists\no_dicom_open.csv" --execute > "$O\exec_open.log"; $LASTEXITCODE   # 0
Select-String -Path "$O\exec_open.log" -Pattern "self-check|report:"      # "self-check: OK for 324 item(s)"
python $RA --nas-root $NAS --list "$O\lists\no_dicom_open.csv" --execute                                       # "no-op"
# then the same two commands for no_dicom_closed.csv (after 0220's reopening) and no_dicom_no_project.csv
```

Expected time: about 30–60 minutes for all three (the rehearsal took about 13 on `D:`; §5). Each run takes its own backup first: `C:\Users\rtasseff\temp\gjesus3_retire_backup_<run>\`
(registries, `.acq_id_seq.json`, each placeholder's whole folder, every touched `provenance.csv`, SHA-256-verified; the
report and log are written there). **Exit codes:** 0 done / no-op · 2 refused, nothing written (read the REFUSED lines) ·
3 the backup failed, nothing written · **4 stopped mid-run: re-run the same command** (every step resumes from disk;
the validator shows the half-done id as an ERROR until then) · 5 self-check failed: stop, read the report.

**6. Verify.**

```powershell
python $INV snapshot --nas $NAS --out "$O\after\snap.json" --light --lists "$O\lists" --tools tools
python $INV check --nas $NAS --before "$O\before\snap.json" --after "$O\after\snap.json" --lists "$O\lists" `
    --tools tools --expect-link-removals 312        # 447 once the 135 of 0220 have run; --groups open,no_project if they wait
python tools\validate_registries.py --nas-root $NAS --no-enrichment        # 0 errors
python $RA --nas-root $NAS --build-no-dicom-lists "$O\lists_after"         # 0 / 0 / 0 (or the 135 still waiting)
python tools\repair_link_collisions.py audit --nas-root $NAS --out "$O\link_audit_after"   # EMPTY-PRIMARY 0
python tools\generate_index.py --nas-root $NAS                             # the global Finder page, or the 03:00 job
```

`check` must end `INVARIANTS: ALL OK`: the row files lost exactly the listed ids' records and every other record is
byte-identical (`registry_raw`, `ingest_manifest`, `pending_dicom_regen`, `pending_subject_metadata`); subjects,
datasets and `.acq_id_seq.json` unchanged; the tombstone file append-only with exactly the listed ids, all `no-dicom`;
every moved file SHA-256-identical to its `/raw/` source, a README and the evidence for each; the `/raw/` folders gone;
only empty link entries removed, every other link entry of the 17 projects unchanged; each `provenance.csv`
append-only with only this retirement's rows. The link audit: `EMPTY-PRIMARY` 0 and the other columns as before
(after the archive ingest's own changes).

**Stop conditions, in one place:** a total other than 464 without an explanation · any `PROBLEM` / `REFUSED` you did
not expect · a dry-run `foreign` beyond the three of §1 · exit 3 or 5 · `check` not ALL OK · a validator error.

**Rollback.** Before a commit nothing is written (exit 2 / 3). A crash is finished, not undone (exit 4: re-run). To
undo a completed list (not automated; only safe if no other registry writer has run since):
1. restore `registries\*.csv` and `.acq_id_seq.json` from that run's backup (`…\gjesus3_retire_backup_<run>\registries\`)
   — this removes the tombstones and brings back the rows;
2. recreate each `/raw/` folder from `…\acquisitions\<ACQ-ID>\` (its three files) plus an empty `<ACQ-ID>.data\`, at the
   tombstone's `original_canonical_path`;
3. recreate each removed link as an empty folder (names: the `link-removed` provenance rows);
4. the `working\mri_not_registered\…` copies and the provenance rows can stay (provenance is append-only; add a note row).
To undo one id, the tombstone row holds its `registry_raw` record verbatim and its other rows in `other_rows_removed`
(11 §5.7 "Restoring a retirement").

## 8. Open points

| # | For | Question | Proposed |
|---|---|---|---|
| 1 | Ryan | The 5 no-project exams (G1): where do their files go? | `staging\mri_not_registered\<study>\<exam>\`, with the README (§3.3). Alternatives: the project `AE-biomaGUNE-0522` (animal 145 is a 0522 animal), or tombstone only (the backup keeps the files off-NAS). |
| 2 | coordinator | `0220`'s 135: run after its reopening (the archive ingest), or hold | Run right after the archive ingest reopens it; if it is closed again, leave the 135 for the next reopening (the tool refuses until then). |
| 3 | Ryan | 27 `no-source` exams whose studies the platform archive holds: look there for a reconstruction first? | Retire now (Ryan's ruling; drive 3 matched the archive with 0 differences). If a reconstruction turns up later, the Data Office registers it (the re-ingest block, §2). |
| 4 | Ryan | The live-ingest skip and its three questions | BACKLOG text in §6. |
| 5 | coordinator | The 10 drive-3 exams' pointers | Placed by the close-out by 19:40 on 2026-10-08 (the copy's lists find all 10); confirm `with see_also 10` at step 1 (§3.4). |

## 9. CHANGELOG-ready note

> **2026-10-08 — MRI placeholders retired as `no-dicom` (built and rehearsed; production run pending).** Ryan ruled the
> 464 empty MRI placeholders registered before the 2026-10-04 line (365 spectroscopy / calibration, 99 with no
> reconstruction to convert) are retired, their files kept in their projects. New retire disposition `no-dicom`
> (06 §2.9, 10 §3.9, 11 §5.7; mirror `ingest/retired.py`, validator): the row moves to the tombstone; each folder's
> `metadata.json`, `checksums.json`, `README.txt` move to `<project>\working\mri_not_registered\<study>\<exam>\` beside a
> `README_not_registered.txt`; the empty project link goes; the worklist rows leave with the row. `--build-no-dicom-lists`
> builds the lists read-only. `csv_safe.split_records` made ~40× faster (same records). Rehearsed on a `D:` copy
> (all 464; invariants all OK: rows −464 exactly, 1,392 files SHA-256-identical, 447 empty links removed, other
> links untouched, validator 0 errors). The live ingest's skip of non-image exams is written up for BACKLOG. Branch
> `feat/mri-placeholder-retire`; `tasks/mri_placeholder_retire_gate.md`.

## 10. Files

- In the repo: `tools/retire_acquisition.py`, `tools/ingest/retired.py`, `tools/ingest/csv_safe.py`,
  `tools/validate_registries.py`, `tools/test_retire_no_dicom.py`, `tools/INDEX.md`, `mfb-rdm-docs/00, 06, 09, 10, 11`, this file.
- Outside (`D:\projects\gjesus3\mri_placeholder_retire\`): `census.py` (the read-only census, with `--scan-all-mri`),
  `archive_overlap.py`, `placed_copies.py`, `drive3_ten.py`, `rehearsal_setup.py` (builds the `D:` copy from production,
  read-only), `rehearse.py`, `invariants.py` (snapshot + check; `--light` for production); outputs `census_prod_20261008*\`,
  `lists_prod_20261008\` (the lists and the production dry-run logs), `archive_overlap.csv`,
  `prod_snapshot_test_20261008\` (the read-only production snapshot of §7 step 2, timed), `rehearsal2_nas\` +
  `rehearsal2_run2\` (the rehearsal). `rehearsal_nas\`, `rehearsal_run\`, `rehearsal2_run\` and
  `invariants_v1_superseded.py` are earlier attempts (stopped to switch to the final scripts, and at the list check
  once the close-out had placed the 10) and can be deleted.
