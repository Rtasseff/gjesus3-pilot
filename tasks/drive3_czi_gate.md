# M. Jesús's drive: the Cell Observer `.czi` production lacks — plan, gate and rehearsal (stream C)

**Status:** 🔶 BUILT, DRY-RUN AND REHEARSED, gated by the coordinator, rulings G2/G3/G5 applied; **nothing written to production** · **Date:** 2026-10-06
**Branch:** `feat/drive3-czi` · worktree `gjesus3-dev\drive3-czi` · **Plan:** [`drive3_production_plan.md`](drive3_production_plan.md) (stream C)
**Needs before production:** the coordinator's gate, then **Ryan's go** for each batch (the drive-3 approval model).
**Built on:** A1 [`drive3_raw_coverage.md`](drive3_raw_coverage.md) §5 · A2 [`drive3_projects_and_placement.md`](drive3_projects_and_placement.md) §1, §4.3 ·
the drives 1+2 precedent: [`drives_ingest_dryrun_review.md`](drives_ingest_dryrun_review.md) (its gate and required fixes),
[`drives_r4_cleanup_review.md`](drives_r4_cleanup_review.md) (the pixel check), [`drives_microscopy_ingest_runbook.md`](drives_microscopy_ingest_runbook.md).
**Evidence (regenerable, not backed up):** `D:\projects\gjesus3\drive3_streams\czi\` (`plan\`, `catalog\`, `local\`, `farm\`, `rehearsal_nas\`, `rehearsal_logs\`).
**Read-only throughout:** `J:\gjesus3-data\` was only read (dry runs included); `J:\_staging_drive3_MJ\` was only read; the
animal-facility DB got SELECTs only. Units: GB = 10⁹ bytes.

> **Updated 2026-10-06, late afternoon: the coordinator's rulings are applied.** Configs and lists were re-generated;
> nothing else in the plan moved. A diff of the plan before and after changes only the fields named below; the same
> 4,955 files and the same batches.
> - **G3: R5 accepted.** The 151 files in `PAH aged Female_Proyecto 0424` go to `AE-biomaGUNE-0424` (PROJ-0002), each
>   with its subject (verdict `READING-R5`, all in C05).
> - **G5: people by folder.** Under `Microscopio\CELL OBS MARTA\`, `operator` = `Marta` (842 files; the token
>   production's 912 drives 1+2 rows use). Under `Microscopio\Microscopio- MJesus Sanchez 2023\`, `researcher` = `MJ`
>   (3,719 files; stream N's token). The other 394 files stay blank. The rule is the profile's `people_by_folder`,
>   applied to the canonical copy after it is chosen, so no canonical choice moved (tested).
> - **G2: C05 runs last,** after C01–C04 have all been run and verified.
>
> **New totals:** 3,453 files to projects (`0424` 480), 3,213 subject links to 182 animals, and 1,502 with a blank project
> (1,443 no claim, 59 (C)). Where an older count below differs, these totals stand.
>
> **Re-checked after the change:**
> - the case tables against the plan and the farm: PASS (every batch);
> - `ingest_check` on C01 + C05 (the R5 subjects, and check 8 over all 3,453 link names): every check PASS;
> - `tools/test_drives_ingest_plan.py`: ALL PASS.

## Summary

1. **The plan: 4,955 Cell Observer `.czi`, 637.8 GB, in 5 batches** (C01 a 42-file pilot, then 234 + 234 + 165 GB, then
   C05 `biomaGUNE MJ` 2.9 GB, kept apart for Ryan's "last"): **5.9–8.5 h** at the measured 31–39 MB/s. 3,302 files go to
   six existing, active projects (`0424` 329, `0522` 1,085, `0619` 1,197, `1019` 544, `1123` 75, `1422` 72) with **3,062
   subject links (181 animals)**; 1,653 get a blank project and are listed. No project is created or reopened.
2. **From A1's 5,115 to the plan's 4,955, every file accounted for:** 82 same-name pixel-identical re-saves within the
   drive dropped (gate R2) and **78 derivatives routed to the project folder** (the list for stream P, §5: 60 same-name
   scale-bar copies, 11 crops, 7 renamed re-saves). Of A1's 119 re-saves of production acquisitions, 118 are dropped
   (111 within 150 KB; 7 more proved pixel-identical, tile for tile) and **1 is held** (point 4). **None of the 5,115 is
   another re-save of production** (§2, rows 2–3).
3. **Every same-timestamp group decided before ingest, by the drives' pixel check:** 238 groups (470 planned files, 9
   production files), 0 undecided. 302 files kept, 89 dropped as re-saves, 78 non-raw, 1 held; **no scene splits,
   stitched copies or renderings** occur, so drives 1+2's open "proposal (c)" question does not arise here. Re-checked by
   another route (decoded images): 19 of 19 identical, 11 of 11 crops found.
4. **A production defect found: `ACQ-20230707-CELL-001` holds only a 310 × 235 px preview** of the 8,355 × 6,342, 3-channel
   scan `ID187_10x.czi`, which the drive holds complete. Held, not a second ACQ-ID; **proposed: repair the primary in place,
   on Ryan's go** (the `ACQ-20251031-CELL-003` precedent).
5. **The invariants hold** (§2): no planned SHA-256 is in production; no planned file is a re-save of a production
   acquisition or of another planned file; every group decided; every file has its claim's verdict; no link name is
   taken; no planned file is truncated; the engine resolves every file exactly as planned. Checked here with the engine's own resolution on **C01, C02 and C05 (2,026 files): every check PASS**, and by the real dry run against J: (C01 and C05 complete and clean; C02 clean so far, still running at wrap-up); C03 and C04 get the same at step 0 of their batch (their last 75 files were still being copied to D: at wrap-up).
6. **The production change of 11:03–11:21** (86 AxioScan acquisitions, MBC): proved covered, since this stream read live production
   throughout, and proved AxioScan (serial `4661000718` in each file's own header); it touches no planned file.
7. **Rehearsal**: C01 + C05 (369 files) into a scratch NAS root on D: with the real engine: **369 of 369 ingested, `ingest_verify` and the coordinator's `c_manifest_check` all PASS, the validator unchanged; the re-run added nothing** (`Total: 0`; 369 "already in registry").
8. **Claims, as the rule says, with A1 reconciled:** of A1's 1,488 no-claim files, 1,287 are planned blank, 80 dropped as
   re-saves, 71 routed to non-raw and 50 out of scope; of its 139 "animal not in the claimed protocol", the engine
   confirms 78 (its nearest claim folder holds the animal), leaves 43 (C) and 17 no-claim, and 1 is non-raw. A2's
   readings R1–R4 cover no `.czi`. **A new reading, R5, is accepted (2026-10-06) and applied:** 151 (C) files of the
   female `0424` cohort (the animal is female in `0424` and male in `1019` every time) go to `0424`.
9. **New tooling, generalised for a third drive, with tests:** `ingest_plan`/`ingest_check`/`ingest_verify`/
   `run_drives_batch.sh` take a `--profile`; drives 1+2's frozen behaviour is unchanged (their `ingest_verify` prints
   the same before and after); the local mirror, the pixel-check wrapper, the decision rules, the coordinator's
   independent check against the drive manifest. Full suite **38/38**.
10. **For the coordinator and Ryan (§6.2):** each batch's go; the `ACQ-20230707-CELL-001` repair. G2, G3 and G5
    were ruled on 2026-10-06 (see the update above).

---

## 0. How it was done, and three things that differ from drives 1+2

**Inputs** (read-only, regenerable, on D: unless said): the drive manifest (`D:\projects\gjesus3\drive3_analysis\drive3_manifest.csv`,
621,969 rows, SHA-256 per file, byte-identical to the NAS copy); part A1's per-file header table
(`a1\microscopy_files.csv`: the catalog's own `.czi` reader and device-serial fingerprint over every `.czi` of the
drive); part A2's per-file claims (`a2\claims\file_claims.csv`: the drives claims engine, unchanged, run over the drive,
with the DB-date tie-break); a **fresh production index built by this stream** from every LIVE `checksums.json`
(`catalog.py production --out D:\projects\gjesus3\drive3_streams\czi\catalog`, 12:25–12:28) and the LIVE
`registry_raw.csv`; read-only listings of each target project's `raw_linked\`.

**1. The staged copy is on the NAS, so each planned file is first copied once to D: and verified.** The drives 1+2
staged copies were on D:, and the farm hard-linked them. Drive 3 is staged on `J:\_staging_drive3_MJ\`, a hard link
cannot cross volumes, this account cannot create symbolic links (no privilege), and the engine reads every source
twice (hash, then copy): ingesting straight off the NAS would move each byte over SMB four times instead of two.
`ingest_plan.py localize` copies each planned file once from J: to the local mirror
`D:\projects\gjesus3\drive3_streams\czi\local\`, hashing the bytes as they are read and keeping the file only if the
hash and size equal the drive manifest's (measured: 105–113 MB/s). `verify-local` re-hashes the mirror FROM DISK
against the manifest, by a separate code path. The farm `...\czi\farm\Cxx\drive3_MJesus-MFB\<path on the drive>` is
hard links into the mirror, so `original_name` = `drive3_MJesus-MFB/<path on the drive>`, as drives 1+2.
`J:\_staging_drive3_MJ\` is only ever read.

**2. MAX_PATH.** `LongPathsEnabled` is 0 on the workstation and the engine opens sources without the `\\?\` prefix, so
every farm path must fit 259 characters. The deepest planned path is **255** (directory parts at most 210, under
CreateDirectory's 248). The plan refuses anything over 258, check 3e re-measures what the engine actually opened, and
the pilot batch C01 carries the two deepest paths (255) and four at the next depth (239), so that the rehearsal and
the first production window exercise them.

**3. Same-timestamp groups are decided before ingest, not flagged and cleaned up after.** Drives 1+2 kept every member
of a same-timestamp group in `/raw/` (gate rule R4) and retired the derivatives later (stream D, 153 retirements).
Here the drives' pixel check (`r4_groups.py`, unchanged, through `drive3\c_groups.py`) runs first, and Ryan's rule
(2026-10-01) is applied to its result: the acquisition goes to `/raw/`; a scale-bar copy, renamed re-save, crop,
subset, scene split, stitched copy or rendering goes to the project folder as non-raw (stream P's list, §5); a
same-name pixel-identical re-save is the same acquisition and is dropped (gate R2); what the evidence cannot place
is kept and flagged. A group is every planned file of one instrument and acquisition SECOND plus the production
acquisitions of that second, so the R1 re-saves with a size difference, the R3 same-second-other-name case and the
in-drive groups all go through the same tile-by-tile check. The wrapper adds a tolerant tile cache: a truncated file
is related to its complete twin by its readable tiles and reported `complete=N` instead of stopping the run.

## The production change of 11:03-11:21 (the coordinator's question)

The coordinator's index (`drive3_analysis\prod_raw_sha256.csv`, 10:30) predates an operator GUI ingest (MBC, 86
AxioScan acquisitions into PROJ-0004, -0011, -0002, -0006). **This stream never used that index**: its plan, its checks
and every batch's step 0 read a stream-built index of every LIVE `checksums.json` and the LIVE registry.
`tools/drive_staging/drive3/c_prod_delta.py` proves it (output `plan\prod_delta.txt`):

| | |
|---|---|
| live `registry_raw.csv` | 27,120 rows, last written 11:21:37 |
| rows the 10:30 index lacks | 550: **86** with checksummed files (`ZWSI`, `recipes/mbc.yaml`, registered 09:xx UTC = 11:xx local) and 464 MRI placeholders with an empty `checksums.json` (they never had a hash) |
| the stream's index (built 12:28:09, newer than the registry) | holds all 86; each one's `checksums.json`, re-read now, equals its rows there |
| instrument | all 86: registry `ZWSI`; **each primary's own `.czi` header names serial `4661000718`** (gjesus3's AxioScan 7); the catalog's sidecar audit agrees |
| drive 3 | 0 of their 86 SHA-256 are any drive-3 file's (the whole 621,969-file manifest); 0 share an (instrument, second) with a planned file; 0 share a second, or a (second, name), with any of the 6,967 drive-3 `.czi` |

Check 3 of every production batch re-asserts the index is newer than the registry, and step 0 rebuilds the index
from live production before each batch, so a later operator ingest is caught the same way.

---

## 1. The plan

### 1.1 From the drive to the plan

Each line is a count of distinct contents (SHA-256), except the first two.

| Step | Files | GB | Where it is listed |
|---|---:|---:|---|
| `.czi` on the drive (every copy; A1 read every header) | 6,967 | | `a1\microscopy_files.csv` |
| of which Cell Observer, `czi-raw` (device fingerprint: no serial, stand key `Inverted`) | 6,821 copies | | |
| **distinct Cell Observer contents** | **5,951** | 694.7 | |
| − byte-identical to production (live index) | 717 | 39.0 | `excluded.csv` `in-production` |
| = **not in production by SHA-256** (A1: 5,114 + 119 re-saves + 1 same-second) | **5,234** | 655.7 | |
| − **re-saves of a production acquisition** (same instrument, second and name): 111 within 150 KB, 7 more pixel-identical (pyramid levels added or removed) | 118 | 12.5 | `resave-of-production` |
| − **same-name re-saves within the drive** (pixel-identical twins, the canonical one kept; gate R2) | 82 | 2.6 | `resave-within-plan` |
| − **derivatives to the project folder** (crops, renamed re-saves, scale-bar copies: §5) | 78 | 2.5 | `derivative-nonraw` -> `nonraw_derived.csv` |
| − **held for a production repair** (`ID187_10x.czi`: §6) | 1 | 0.4 | `held-production-repair` -> `production_repairs.csv` |
| = **the plan** | **4,955** | **637.8** | `expected.csv`; configs `tools/configs/drives3_2026-10/` |

The handoff's 5,115 (643 GB) is A1's "not in production" count; the plan is 160 fewer, all with a reason above.
No planned file is in production by SHA-256 or is a re-save of a production acquisition (§2). The one A1 file that
"shares an instrument and second with production under another name" (`230530-ID161-alphasma8OHdG-lungs-20x-2.czi`)
is pixel-identical to production's `ACQ-20230530-CELL-011` (`…-20x-1.czi`): a renamed copy, so non-raw (§5).

### 1.2 Per project

| Project | | Files | GB | With a subject link | Animals |
|---|---|---:|---:|---:|---:|
| `AE-biomaGUNE-0424` | PROJ-0002 | 480 (329 + R5's 151) | 11.9 | 480 | 16 |
| `AE-biomaGUNE-0522` | PROJ-0011 | 1,085 | 135.2 | 1,074 | 64 |
| `AE-biomaGUNE-0619` | PROJ-0004 | 1,197 | 267.3 | 1,002 | 62 |
| `AE-biomaGUNE-1019` | PROJ-0006 | 544 | 57.8 | 510 | 16 |
| `AE-biomaGUNE-1123` | PROJ-0014 | 75 | 0.5 | 75 | 13 |
| `AE-biomaGUNE-1422` | PROJ-0013 | 72 | 0.4 | 72 | 11 |
| **blank** (1,443 no claim, 59 (C)) | | 1,502 | 164.7 | 0 | 0 |
| **all** | | **4,955** | **637.8** | **3,213** | **182** |

All six target projects exist and are **active**; **no project is created or reopened**. Every file is `CELL`,
`instrument_model` `Axio Observer.Z1 / 7` (the stand name the engine reads back from each file), `data_source`
`internal`; `sample_id` is the file name; `sample_type` `tissue` exactly where a subject is recorded (the drives 1+2
G4 rule). Acquisition years: 2021–2025.

### 1.3 Batches (at most 250 GB), in order, with the time at the measured 31–39 MB/s

| Batch | What | Files | GB | Projects | Time |
|---|---|---:|---:|---|---:|
| **C01** | **the pilot**: each project's smallest files with and without a subject, no-project files, the smallest same-second groups, the deepest paths | 42 | 2.2 | 0424 0522 0619 1019 (+14 blank) | 2–3 min |
| C02 | Cell Observer with a project | 1,657 | 234.1 | 0424 0522 0619 | 2.1–3.0 h |
| C03 | Cell Observer with a project | 1,441 | 234.0 | 0619 1019 | 2.1–2.9 h |
| C04 | Cell Observer, blank project | 1,488 | 164.6 | — | 1.6–2.3 h |
| **C05** | **`biomaGUNE MJ`** (the files whose only, or canonical, copy is in M. Jesús's own folder; Ryan's "last") | 327 | 2.9 | 0522 1123 1422 (+151 blank) | 6–12 min |
| | **all** | **4,955** | **637.8** | | **5.9–8.5 h** |

The time is the bytes at 31–39 MB/s (measured on drives 1+2 from a local source: the NAS write and read-back)
plus 1–2 s per file for the registry, sidecar and link work. **C05 runs only if the coordinator rules that Ryan's
"`biomaGUNE MJ` last" does not hold back its `.czi`.**

### 1.4 What was dropped, routed or held, and why

- **In production by SHA-256: 717** contents (39.0 GB); nothing to do.
- **Re-saves of a production acquisition: 118** (12.5 GB). A1's 119 less the held `ID187_10x.czi`. 111 differ by at most
  150 KB (the drives' rule: a plain re-save). The 7 with a larger difference (20–40 MB) went through the pixel check
  with their production twins: **every level-0 tile is byte-identical** (`202II_HEx10`, `208II_HEx10`, `209II_HEx10`,
  `TM_ID5H_10x`, `TM_ID209H_10x`, `ID128-1_1019-2_PR`, `ID128-1_1019-2_PR_POL`); the difference is the pyramid levels
  one side added. Dropped; production holds the acquisition.
- **Same-name re-saves within the drive: 82** (2.6 GB). Pixel-identical twins under one name and second, mostly
  `Machos vs Hembras` against `Female Diets` (one re-saved in 2025). The kept twin is a complete file; then the clean
  one when they differ only by a scale-bar layer; then the drives' canonical rule. Their paths go into the kept
  file's `other_copies` (and the registry notes), as drives 1+2 did.
- **To the project folder (stream P): 78** (2.5 GB): 11 crops, 7 renamed pixel-identical re-saves and **60 scale-bar
  copies under the same name** whose clean twin is the acquisition (§5).
- **Held: 1**, `ID187_10x.czi` (360 MB): production's `ACQ-20230707-CELL-001` has its name and second but holds only a
  downsampled preview of it (§6).
- **Out of scope: 172 files** (§1.7).

### 1.5 Projects and subjects: the rule applied to each group

**The rule (Ryan, 2026-09-29, and the coordinator's acceptances of 2026-10-06), and only it.** A planned file takes its
canonical copy's claim, as the drives claims engine (`project_claims.py`, unchanged, with the DB-date tie-break)
classified it over the whole drive (A2's `file_claims.csv`):
- **Confirmed** -> the claim's `AE-biomaGUNE-NNNN`, and the engine's subject id where it resolved the animal (`<n>-AE-biomaGUNE-NNNN`, re-resolved by check 6);
- **(A) / (B)** -> none among these files;
- **(C) and no claim** -> a **blank project and no subject**, listed: [`tasks/drive3_czi_blank_project_preview.csv`](drive3_czi_blank_project_preview.csv) (1,653 rows, each with the engine's reason and A1's own reading; after the ingest it becomes the list with ACQ-IDs, as drives 1+2's).

**A2's readings R1–R4 cover none of the drive's 6,967 `.czi`** (measured: `CL-1344` 0, `CL-0772` 0, date-token
shadowing 0, the three no-code folders 0), so none applies. Copies of one content never claim two projects (0
conflicts). A same-name twin that is dropped or routed to non-raw hands a single claim to the kept file (it is the same
acquisition); two different claims would blank it as a conflict (none occurs).

| Engine verdict | Planned files | Rule |
|---|---:|---|
| Confirmed | 3,302 | its project; a subject where the engine resolved the animal (3,062) |
| no claim | 1,443 | blank, listed |
| (C) | 210 | blank, listed |

**The 210 (C), by reason:**

| Folder | Files | The engine's reason | Evidence beyond the rule |
|---|---:|---|---|
| `biomaGUNE MJ\PAH aged_Proyecto 0424 & 1019 (female and male)\PAH aged Female_Proyecto 0424\Raw data\Microscopio\{0424-8ohdg, 0424-WGA, 0424-Elastic}` | 151 | nearest `0424` (Confirmed) against outer `1019`; the animal is in both, and the DB dates do not separate them | the outer folder names **both** codes; **in all 151 the animal is female in `0424` and male in `1019`**, and the folder is the female cohort's (`c_db_evidence.py`): **reading R5, accepted 2026-10-06: to `0424` with subjects** |
| `Male Diets\230512-MTCOI and TOM20 Male Diets 0522\230707-TOM20-MTCOI-10x` | 21 | the file's animal is not in `0522` | the A2 D7 pattern (animals that exist in `0619`); asked of M. Jesús with D7 |
| `Machos viejos-1019-3\1019-3 Elastic` | 19 | a nearest `0522` that does not resolve, inside `1019` | none |
| `CELL OBS MARTA\PR_0522_MJS_Paper aging` | 16 | nearest `0424` or `1019` against outer `0522`; the animal is in both | none decisive |
| `Machos vs Hembras\VDACand B8 Male and female` | 3 | the file's animal is not in `0619` | none |

**The 1,443 no claim** sit in `Microscopio- MJesus Sanchez 2023\Machos vs Hembras` (943), `…\Female Diets` (289) and
`CELL OBS MARTA` dated folders (211). 139 of them carry a `0522Male` / `0619Female` chunk in the file name, which A1
read as a claim and the engine does not (a chunk in that position is not a claim position: file-name chunks are free-form
labels). That is evidence for the mapping round, not a claim.

**A1's two counts, reconciled** (over A1's own population: the 5,258 distinct microscopy files it found not in production):

| A1's verdict (by path) | Here | Files |
|---|---|---:|
| **no claim: 1,488** | planned, no claim | 1,287 |
| | dropped as a same-name re-save | 80 |
| | routed to non-raw | 71 |
| | out of scope (Axioscan 7 #4661000340, Leica) | 50 |
| **animal not in the claimed protocol: 139** | planned, **Confirmed** by the engine (its nearest claim folder is another protocol, which holds the animal: e.g. `ID190-1019-…` inside `1- KD female 0619`) | 78 |
| | planned, (C) | 43 |
| | planned, no claim (the engine rejects A1's token) | 17 |
| | routed to non-raw | 1 |
| animal in the protocol: 3,368 | planned Confirmed 3,032, (C) 167 (151 are R5's), no claim 139; out of scope 22; non-raw 6; dropped 2 | |
| protocol, no animal number: 263 | planned Confirmed 192; out of scope 71 | |

**Subjects** (check 6): only on Confirmed rows, always in the row's own protocol, and every one re-resolves in the
facility DB, with fresh SELECTs, to itself. 3,062 files link to 181 animals; the 240 Confirmed files with no animal
number in their path get no subject (`0619` 195, `1019` 34, `0522` 11). No subject sits on a (C) or blank-project row.

### 1.6 Researcher and operator (assigned by the coordinator's G5 ruling of 2026-10-06; the analysis below is the reason it was needed)

The claims engine finds **no whole-segment person folder** above any of these files, so `researcher` is blank on all of
them; and drive 3 has **no operator top folder** of the kind Ryan named on 2026-09-29 (`Cell observer\AINHIZE|Marta`), so
`operator` is blank too. Two folder names *embed* a person and are, by the same rule ("names embedded in longer folder
names are flagged, not assigned; initials are never mapped to people"), **flagged here and not assigned**:
`Microscopio\Microscopio- MJesus Sanchez 2023\` (the researcher's own 2023 microscopy, 3,719 planned files) and
`Microscopio\CELL OBS MARTA\` (Cell Observer images from Marta's folder, 842 planned files: Marta is a Cell
Observer operator). Reading them as `researcher = M. Jesús` and `operator = Marta` would be an extension of the
2026-09-29 rule. **Ruled 2026-10-06 (G5):** `operator` = `Marta` for the 842 files and `researcher` = `MJ` for the
3,719; the other 394 files stay blank.

### 1.7 Out of scope, as the brief says (listed in `tasks/drive3_czi_out_of_scope.csv`)

| What | Copies | Distinct | GB | Why it is not this stream's |
|---|---:|---:|---:|---|
| Axioscan 7 **#4661000340** (`Pollux`, ZEN 3.7) | 144 | 116 | 153.9 | not gjesus3's `ZWSI` (#4661000718); waits on M. Jesús (§0.5 M3), then the Charité `XMIC` precedent. **20 of the 144 sit in `biomaGUNE MJ`.** |
| Leica TCS SP8 **#8100000207** (`.lif` 17, `.lifext` 9) | 26 | 26 | 6.7 | not gjesus3's; same route |
| a `.czi` with no instrument metadata (`czi-processed`) | 2 | 1 | 0.0 | no hardware or experiment block: not an acquisition record ("the 1 unreadable file") |

None of them is in production by SHA-256.

---

## 2. The invariants, re-derived

Every invariant is re-derived by a tool that does not trust the plan's own code path: `ingest_check.py --profile
drive3_2026-10` runs the engine's dry-run resolution (`config.expand_batch`, what `ingest_raw.py --dry-run` runs before it
returns) on every generated config, against the live registry, and compares every case with the plan file by file.
Report: `plan\check_report.json`, `plan\check_cases.csv`. **Run here on C01, C02 and C05 (2,026 files, 239.2 GB): every check PASS, 0 engine skips, 0 warnings, 0 extraction failures. The real dry run against `J:\gjesus3-data` (read-only): C01 and C05 complete, N cases, 0 SKIP, 0 refused link names, `Failed: 0`;** C02's (about 3 s a case over SMB) had reached 298 of 1,657 cases at wrap-up with 0 SKIP, 0 refused names and 0 errors, and was left running, read-only (`plan\dryrun_C02.log`); step c of the runner repeats it just before the run in any case. C03 and C04 (2,929 files) could not be resolved by the engine here: their last 75 files were still being copied to D: when the coordinator asked to wrap up. Their plan-level invariants hold (rows 1–5 and 9 are properties of the whole plan, built over all 4,955 files), and **step 0 of each batch runs every check and the dry run on it before anything is written** (§4.2), so neither can start unchecked.

| # | Invariant | How it is proved | Result |
|---|---|---|---|
| 1 | Every planned file is a distinct in-scope Cell Observer content not in production, in exactly one batch; the engine finds exactly the plan | check 1: the set re-derived from A1's header table, minus the stream's live production index and the plan's own listed exclusions, equals the plan; engine cases == plan rows | **PASS**: A1's set less production and the listed exclusions = the plan's 4,955 (637.8 GB) exactly |
| 2 | **No SHA-256 already in production** | check 3 against the stream's index of every LIVE `checksums.json` (newer than the registry); `c_prod_delta.py` for the 11:03 change | **PASS** (C01, C02, C05): 0 planned SHA-256 in production; the 86 new AxioScan acquisitions are in the index (§0) |
| 3 | **No re-save of a production acquisition** | the plan's R1 over every copy's name: the 119 A1 found (111 by size, 7 by pixels, and `ID187_10x.czi` held: §6.1); check 3b (same instrument, second and name as a live registry row) on the plan: 0; check 3c: no other same-second production row | **PASS** (C01, C02, C05): 0 |
| 4 | No two planned files are the same acquisition | check 3b: no (instrument, second, name) twice | **PASS** (C01, C02, C05): 0 |
| 5 | **Every same-timestamp group decided** | check 3d: every planned file sharing an instrument + second with another planned file or a production row sits in a group the pixel check decided for exactly the current membership (a production row added since fails it), as keep or keep-flag | **PASS** (C01, C02, C05); plan-wide: 238 groups, 0 undecided |
| 6 | No truncated file is ingested; every farm path fits MAX_PATH | check 3e: each planned (farm) file's last subblock ends inside it; the paths the engine opened are ≤ 258 | **PASS** (C01, C02, C05): 0 truncated; deepest path 255 |
| 7 | The engine resolves each file exactly as planned | check 2: instrument, project, researcher, operator, subject, date, data source, model, sample, link name, group and notes, file by file | **PASS** (C01, C02, C05): 0 mismatches over 2,026 cases |
| 8 | Dates | check 4: no blank acquisition time, no ACQ-ID dated today | **PASS** (C01, C02, C05): 2021–2025, no blank |
| 9 | **Every claim classified**; projects | every planned file has the engine's verdict (Confirmed / (C) / no claim; none blank, no conflict); check 5: no project created, every target exists and is active | **PASS** (C01, C02, C05); plan-wide: Confirmed 3,302, (C) 210, no claim 1,443, 0 conflicts; 6 target projects, all active, 0 created |
| 10 | Subjects only where the DB settles them | check 6: subject only on Confirmed rows, in its own protocol, and every one re-resolves in the facility DB (fresh SELECTs) to itself | **PASS** (C01, C02, C05): every subject re-resolved to itself |
| 11 | **No link-name collision** | check 8: every link name unique in its project and free in the live `raw_linked\`; and the engine's own 2026-10-05 pre-check in the real dry run of every batch against J: | **PASS, plan-wide** (check 8 reads every batch): 3,302 planned link names, unique, 0 taken; the real dry runs refused none |
| 12 | The local mirror is the drive's bytes | `verify-local`: every planned file re-hashed from D: against the drive manifest | each file was hashed as it was read from J: and kept only on a manifest match (4,500+ files, 0 bad); re-hashed from disk so far: the 470 pixel-check members and C01 + C05 (369 files), 0 bad. **§4.1 re-hashes every planned file from disk before the first batch** |

---

## 3. The rehearsal and its idempotent re-run

**Where:** a scratch NAS root on D:, `D:\projects\gjesus3\drive3_streams\czi\rehearsal_nas\` (never J:), made by
`ingest_plan.py --profile drive3_2026-10 scratch`: production's registries copied read-only from J:, and, for each of the
six target projects, a `raw_linked\` holding a **zero-byte stand-in for every link name production already uses** (1,041
to 3,047 per project, 7,643 in all), so a name collision would be real. **What:** the real engine
(`tools/ingest_raw.py`), the generated configs and the farm, exactly as production will run them, on **C01 (the pilot)
and C05 (`biomaGUNE MJ`)**: 369 files, 5.1 GB, which exercise every code path the other batches use (projects with and
without subject links, blank projects, same-second groups with their notes, the six deepest paths). Then the same two
commands again. Driver: `D:\projects\gjesus3\drive3_streams\czi\scratch\rehearse.sh`; logs in `…\czi\rehearsal_logs\`.

**Result: clean, and the re-run idempotent.** (14:37–14:55, 2026-10-06; the scratch registry started as production's
27,120 rows.)

| Step | C01 (42 files, 2.2 GB) | C05 (327 files, 2.9 GB) |
|---|---|---|
| **pass 1** (the real engine, `--refresh-index projects`) | exit 0, 88 s; `Success: 42`, `Failed: 0`; 42 "Verification PASSED"; 0 SKIP | exit 0, 288 s; `Success: 327`, `Failed: 0`; 0 SKIP |
| WARN lines | 32 = the two documented sidecar sentinels (`condition.is_control` null, `anatomy.region` empty) on each of the 16 rows with a subject | 352 = the same two on each of its 176 rows with a subject |
| `ingest_verify.py --profile drive3_2026-10` (both batches) | **369 planned, 369 registry rows from these configs; `rows`, `fields`, `checksum`, `sidecar`, `link`, `registry`: all PASS (0)** | |
| `c_manifest_check.py` (the coordinator's check, from the drive manifest, without the plan) | **369 rows checked against the 621,969-row manifest; `rows`, `manifest`, `link`, `orphans` (13 month folders scanned): all PASS (0)** | |
| the validator, before and after | the same 27,120 `ERROR:` lines before and after, line for line: each is a production acquisition whose folder the scratch root does not have; **the 369 new rows add none** | |
| **pass 2** (the same commands again) | exit 0, 29 s; `Total: 0`; 42 "already in registry (idempotent re-run)" | exit 0, 170 s; `Total: 0`; 327 the same |
| the scratch registry after both passes | **27,489 rows = 27,120 + 369** | |

What one ingested row looks like (`ACQ-20250123-CELL-003`, C01): `CELL`, `Axio Observer.Z1 / 7`, `PROJ-0002`, subject
`16-AE-biomaGUNE-0424`, `sample_id` the file name, `sample_type` `tissue`, `original_name`
`drive3_MJesus-MFB/Microscopio/CELL OBS MARTA/Elastic_0424_MJS/ID16L_0424_Elastic20x-8.czi`, `checksum_present` `Y`,
notes ending `Claim: CONFIRMED.`; its sidecar carries the facility-DB subject block (`Mus musculus`, F, born 2023-05-25,
`P87W` at acquisition) and the case-table fields. A blank-project row (`ACQ-20230505-CELL-001`) has no project, subject
or sample type and notes `Claim: NO-CLAIM.`; the 6 same-second keeps carry their group note ("the pixel check found no
copy relation (another scene of the acquisition)").

**Not rehearsed on the NAS:** the SMB side is the one drives 1+2's batches exercised (the same engine and runner,
measured at 31–39 MB/s into J:), so no sandbox on `J:\gjesus3-sandbox\drive3-czi\` was used. **Not rehearsed:**
C02–C04 (the same configs and code paths at a larger size; drives 1+2 ran batches of 400 GB through the same engine).
The scratch root (`rehearsal_nas\`, 5.1 GB) can be deleted.

---

## 4. Production: the exact commands, the checks after each batch, the backup, and a stop half-way

**Who and when.** Each batch is an ingest, so it runs only on **Ryan's go**, given after the coordinator has gated
this dry run (the drive-3 plan's approval model), in a write window the coordinator opens. **One registry writer at a
time:** no other stream writes `registry_raw.csv` while a batch runs. Evenings or weekends: operators ingest through
the GUI by day, and the engine's dedup snapshot is taken before the registry lock (BACKLOG "Dedup identity"). No
batch creates or reopens a project.

### 4.1 Once, before the first batch

```bash
cd "C:/Users/rtasseff/OneDrive - CIC biomaGUNE/projects/DataInfra/gjesus3-archive/gjesus3-dev/drive3-czi"  # or main, once merged
git status                                                         # clean, at the gated commit
export PYTHONDONTWRITEBYTECODE=1
python tools/drive_staging/ingest_plan.py --profile drive3_2026-10 verify-local   # "... N match, 0 bad" (every planned file, from disk)
python tools/drive_staging/ingest_plan.py --profile drive3_2026-10 farm           # "... 0 errors, 0 stray files"
python tools/animal_db.py --check                                                 # "OK" (a miss would write pending-db)
df -h /j                                                                          # stop below 1 TB free
```

### 4.2 One batch: C01 (the pilot) first, then C02, C03 ...; the `biomaGUNE MJ` batch last, only on the coordinator's word

**One command per batch, which stops at the first failed condition, before the run whenever it can:**

```bash
bash tools/drive_staging/run_drives_batch.sh drive3_2026-10 C01
```

It runs exactly these steps (for reference, and for a run by hand):

```bash
B=C01; D=$(date +%Y%m%d); NAS="J:\gjesus3-data"; CFG=tools/configs/drives3_2026-10/drives3_$B.yaml
# 0. is the frozen plan still right for THIS batch? A fresh production index from every LIVE checksums.json,
#    then every check of §2 on this batch, through the engine's own dry-run resolution (read-only):
python tools/drive_staging/catalog.py production --out "D:\projects\gjesus3\drive3_streams\czi\catalog"
python tools/drive_staging/ingest_check.py --profile drive3_2026-10 --batch $B   # every line PASS, 'skips': 0
# a. a fresh, dated, OFF-NAS backup of the registries (never re-use a folder), verified; the validator now
BK="C:/Users/rtasseff/temp/gjesus3_registry_backup_${D}_drive3_${B}"
mkdir -p "$BK" && cp -p /j/gjesus3-data/registries/*.csv /j/gjesus3-data/registries/.acq_id_seq.json "$BK/"
( cd /j/gjesus3-data/registries && sha256sum *.csv .acq_id_seq.json ) > "$BK/SHA256SUMS.src"
( cd "$BK" && sha256sum -c --quiet SHA256SUMS.src )                              # every line OK, or stop
python tools/validate_registries.py --nas-root "$NAS" --no-enrichment > "$BK/validate_before.txt" 2>&1
# b. the config points at the farm; every target project exists and is active (none may be created or closed)
grep -n "staging_dir\|auto_create_projects\|instrument:" "$CFG"
# c. the real dry run, read-only: "Batch: N cases" (N = batches.csv), 0 SKIP, 0 "Refusing" (a taken link name), Failed 0
python tools/ingest_raw.py -c "$CFG" --nas-root "$NAS" --dry-run > "$BK/dryrun.log" 2>&1
# d. the run
python tools/ingest_raw.py -c "$CFG" --nas-root "$NAS" --refresh-index projects > "$BK/run.log" 2>&1
#    BATCH SUMMARY: Success N, Failed 0
# e. the proof, the provenance rows, and the validator against step a
python tools/drive_staging/ingest_verify.py --profile drive3_2026-10 --nas-root "$NAS" --batch $B \
    --provenance tasks/drive3_czi_ingest_provenance.csv                          # rows fields checksum sidecar link registry: PASS
python tools/validate_registries.py --nas-root "$NAS" --no-enrichment > "$BK/validate_after.txt" 2>&1
#    the "  ERROR:" lines equal step a's, line for line (any new one is this batch's: stop)
# f. idempotency: the same command again adds nothing
python tools/ingest_raw.py -c "$CFG" --nas-root "$NAS" > "$BK/rerun.log" 2>&1      # Total: 0
```

**Then, the coordinator's own check, independent of the plan file:**

```bash
python tools/drive_staging/drive3/c_manifest_check.py --nas-root "J:\gjesus3-data" --batch C01
#   rows: the batch's registry rows (by ingest_config) == batches.csv; no acq_id / original_name twice
#   manifest: each row's original_name -> the DRIVE MANIFEST row; its live checksums.json holds exactly that
#             SHA-256 under the primary's name; the primary's size == the manifest's
#   link: the committed case table's link name in the project's raw_linked\ IS the primary (same file)
#   orphans: no ACQ-* folder in the touched months without a live or retired registry row
```

**Pass conditions (all, every batch):** step 0 all PASS with 0 engine SKIPs; the backup verifies; the dry run shows N
cases, 0 SKIP, 0 refused names; the run `Success: N`, `Failed: 0`; `ingest_verify` all PASS; the validator's ERROR
lines unchanged; the re-run `Total: 0`; `c_manifest_check` all PASS; the touched projects' `index.html` refreshed (a
refresh failure is only a WARN: then `python tools/generate_index.py --nas-root "J:\gjesus3-data" --project <PROJ-ID>`).

**Stop, do not start the next batch, and report** on: any of the above failing; any `acquisition_datetime` blank or an
ACQ-ID dated today; a project created or a project row changed (`registry_projects.csv` must be byte-identical to the
backup); `pending_subject_metadata.csv` growing (the DB went away: recoverable with `tools/recover_subject_metadata.py`);
less than 1 TB free on the NAS; disk errors on D:.

### 4.3 If a batch stops half-way

The engine registers a file only after it is copied, re-read and verified and its sidecar written, so **every row that
landed is a complete acquisition**; a handled failure removes its own half-copied folder (`_rollback_uncommitted`).
1. **Do not re-plan and do not edit the configs.** The plan is frozen (every row's `ingest_config` names its config).
2. `ingest_verify.py --profile drive3_2026-10 --batch Cxx` lists what is not in yet (`missing:`); everything else in it
   must still PASS.
3. `c_manifest_check.py --batch Cxx` lists any **orphan**: an `ACQ-*` folder with no registry row, which only a hard
   stop between the copy and the registry write can leave. Note its ACQ-ID; it stays reserved (ids are never reused).
4. **Resume:** run step d again, the same command. The engine skips every file already registered
   (`(date, original_name)`), so only the rest is ingested; then e and f as usual (compare the validator with step a's
   file). The resumed files get new ACQ-IDs; an orphan's id is simply skipped.
5. **An orphan folder** is retired afterwards with `tools/retire_acquisition.py` (`orphan`), as the 17 empty MRI
   folders were on 2026-10-02, on the coordinator's approval.
6. **A refused link name** (an operator took the name since the dry run) fails that file cleanly, with nothing copied.
   The fix is a reviewed edit of that batch's case table (`drv_link_name`), then step 0 again: as drives 1+2 did.

**Rolling back a whole batch** is the drives 1+2 procedure (runbook §5): there is no delete tool; the rows are exactly
those whose `ingest_config` is the batch's config; remove the `raw\MICROSCOPY\...\ACQ-*` folders, the registry and
manifest rows (byte-exact, or restore step a's backup if no other writer has touched the registry since), the new
subjects, the project links and provenance rows, then regenerate the touched `index.html`.

---

## 5. The non-raw list for stream P

**[`tasks/drive3_czi_nonraw_for_stream_p.csv`](drive3_czi_nonraw_for_stream_p.csv): 78 files, 2.47 GB.** Each row: the drive path
(`relpath`, the staged copy), SHA-256, size, the class and the pixel evidence, the original it derives from (a planned
file's path, or a production ACQ-ID), and the destination: **the original's project** (6), or, when the original has no
project, **the holding folder** (72; stream P's rule: `staging\historical_drives_unassigned\MJesus-MFB\…` in its original
structure). None of these 78 claims a project different from its original's.

| Class | Files | GB | Destination | Proof |
|---|---:|---:|---|---|
| scale-bar copy **under the same name** (a pixel-identical twin of the clean acquisition, with an annotation layer added) | 60 | 0.58 | holding (59 in `Machos vs Hembras\8oHDG Female and Male`; their clean twins, kept, have no project) | every tile byte-identical; the XML differs by a `ScaleBar` layer |
| crop (ROI) | 11 | 1.78 | holding (`Machos vs Hembras\heart- Masson and HE` and `\Masson`, `ID196_10x_2.czi`) | every tile a byte-exact sub-rectangle of the original's, one offset; **re-checked by decoding**: each crop found pixel for pixel in its original's image |
| renamed re-save (pixel-identical, another name) | 7 | 0.11 | `0619` 3, `0522` 2, `1019` 1, holding 1 | every tile byte-identical |

The `1019` one is `Machos viejos-1019-3\1019-3 8OHdG\230530-ID161-alphasma8OHdG-lungs-20x-2.czi`, a renamed copy of
production's `ACQ-20230530-CELL-011` (`…-20x-1.czi`, PROJ-0006): the only A1 file that shared a second with
production under another name. **One naming oddity, kept as the pixel check decided:**
`ID161ki67sma20x-220929-2 - Copy.czi` is kept as the acquisition and `ID161ki67sma20x-220929-2.czi` goes to `0619`'s
folder: the two are pixel-identical, and ZEN's own creation time says the `- Copy` file is the earlier save
(10:36:03 against 10:42:36).

**Not in the list, on purpose:** the 82 same-name re-saves dropped within the drive and the 118 re-saves of production
carry no pixel or annotation of their own (the drives 1+2 precedent drops them); and the drive's `.tif` exports beside
the `.czi` are A2's material, already in stream P's plan.

**Every member of every group, with its evidence:** [`tasks/drive3_czi_pixel_classification.csv`](drive3_czi_pixel_classification.csv)
(479 rows: group, member, class, parent, the relation and its evidence, completeness, and the plan's action).

---

## 6. Held for the coordinator, and what is not settled

### 6.1 `ID187_10x.czi`: production's `ACQ-20230707-CELL-001` holds only a preview of it (a production repair, like `ACQ-20251031-CELL-003`)

`Microscopio\Microscopio- MJesus Sanchez 2023\Male Diets\230512-MTCOI and TOM20 Male Diets 0522\230707-TOM20-MTCOI-10x\ID187_10x.czi`
(360,451,488 bytes, sha256 `7197393462578bc3…`) has the same name, instrument and acquisition time (to 100 ns) as production's
`ACQ-20230707-CELL-001` (from drive 1, `Cell observer\Maria Jesus\230620-TOM20-MTCOI-0522\`, blank project). Their XML is
the same acquisition: 8,355 × 6,342 px, 3 channels, a 16-tile mosaic, the same creation time and user. **But production's
file is 536,737 bytes and holds one subblock: a 310 × 235 px downsampled image of channel 0, with no full-resolution
tile at all.** The drive file holds the 48 level-0 tiles (16 × 3 channels) and its pyramid. Re-checked by another route:
production's preview against the drive file's channel 0 reduced to the same size by block means correlates at
**0.913 (rank) / 0.947 (Pearson)**, against 0.71 for the other channels: it is a preview of this very scan.

So the drive holds the complete acquisition that production registered as a preview. By the identity rule it is the
same acquisition, so it is **held, not ingested** (it would be a second ACQ-ID). **Proposed:** repair production's primary
in place from the drive file, with `tools/repair_primary_inplace.py`, exactly as `ACQ-20251031-CELL-003` was repaired on
2026-10-01 (Ryan's approval): the same ACQ-ID, `checksums.json`, `file_size_mb` and a notes clause updated, and the
project links (none today: blank project) see the repair. **This needs Ryan's go.** Listed in
[`tasks/drive3_czi_held.csv`](drive3_czi_held.csv). It also suggests an audit: production `.czi` primaries whose level-0
data is missing or downsampled (BACKLOG "audit production `.czi` for truncated primaries" covers truncation; this is
a second shape).

### 6.2 Decisions and open points

| # | What | Recommendation / state |
|---|---|---|
| G1 | **Each batch needs Ryan's go** after this gate (C01 first, alone) | — |
| G2 | **C05, `biomaGUNE MJ`** (327 files, 2.9 GB): does Ryan's "`biomaGUNE MJ` last" hold back its `.czi`? | **Ruled 2026-10-06:** C05 runs last, after C01–C04 have all been run and verified |
| G3 | **Reading R5** (151 (C) files in `PAH aged Female_Proyecto 0424`, all in C05): the female cohort's folder, and in all 151 the animal is female in `0424` and male in `1019` | **Accepted 2026-10-06 and applied:** they move from blank to `AE-biomaGUNE-0424` with their subject links (`readings.csv` `accepted`; `plan`, `configs` re-run; `ingest_check` C05 PASS) |
| G4 | **`ACQ-20230707-CELL-001`**: repair production's primary from `ID187_10x.czi` (§6.1) | Ryan's go; a separate, approved write after this ingest |
| G5 | **Researcher / operator** stay blank: `Microscopio- MJesus Sanchez 2023` (3,719 planned files) and `CELL OBS MARTA` (842) embed a person, which the 2026-09-29 rule flags and does not assign (§1.6) | **Ruled 2026-10-06:** operator `Marta` (842), researcher `MJ` (3,719); the rest blank |
| G6 | **The 1,502 blank-project files** ([`tasks/drive3_czi_blank_project_preview.csv`](drive3_czi_blank_project_preview.csv)): after the ingest, the list with ACQ-IDs, as drives 1+2 | Into the 2b-style mapping round; 139 of them carry `0522Male` / `0619Female` file-name chunks (the engine rejects a chunk in that position; filename chunks are free-form labels) |
| G7 | **`ID128-1_1019-2_PR.czi`: production holds the annotated twin.** Production's `ACQ-20241021-CELL-003` (PROJ-0006) carries a scale-bar layer; the drive's copy (`CELL OBS MARTA\PR_1019-2_MJS-IAZ\`) is the clean file, 16 of 16 tiles byte-identical. The plan drops the drive copy as a re-save of production (`excluded.csv`). | **Proposed: no action.** The pixels are identical and the scale bar is an overlay in the file's metadata. If Ryan wants the clean file as the record, it is the same in-place repair as §6.1 |
| G8 | **C03 and C04 not yet resolved by the engine here.** At wrap-up, the copy to D: still lacked 75 of their files (10 in C03, 65 in C04; 155 GB). | Finish the copy with `ingest_plan.py --profile drive3_2026-10 localize` (it skips files already verified), then run §4.1 (`verify-local`, `farm`). Step 0 of each batch runs every §2 check and the dry run before anything is written. Their plan-level invariants (§2 rows 1–5, 9 and 11) already hold. **2026-10-06, 15:17:** the copy to D: finished, 4,653 files, 539.6 GB, 0 bad (with the 302 copied before: all 4,955 on D:, each kept only on a drive-manifest SHA-256 match), and the farm is complete (4,955 links, 0 errors). The C02 dry run against J: finished: 1,657 cases, `Success: 1657`, `Failed: 0`, 0 SKIP, 0 refused link names, 0 errors. Every planned file is re-hashed from disk by §4.1 (`verify-local`) before C01 |
| G9 | **The D: working copies** (`local\` 638 GB, `farm\`, `rehearsal_nas\` 5 GB) | Delete them after the coordinator has verified every batch (`c_manifest_check.py`). They are working copies, not a backup. Delete `rehearsal_nas\` now |

**Not settled here, and why:**
- **The project of the 1,502 blank files**: by the rule they stay blank; the evidence for a mapping is in the preview
  list (A1's own reading, the engine's reason), not a decision.
- **Who made the 394 files with no person folder.**
- **`ID161ki67sma20x-220929-2 - Copy.czi`** is kept under its `- Copy` name (§5): the pixel check cannot say more, and
  nothing is lost either way.

---

## 7. What was built on the branch (the drives tooling generalised, with tests)

| File | What changed and why |
|---|---|
| `tools/drive_staging/ingest_plan.py` | **Profiles.** Everything drive-specific (inputs, output folders, drive labels, config folder and prefix, batch cap and prefix, the one project an ingest may create, the hand-recorded re-save decisions) moved into `PROFILES`; `use_profile()` rebinds the module constants. `drives_2026-09` is the default and behaves as before (its plan is frozen and cannot run again: its staged inputs were erased on 2026-10-05). `drive3_2026-10` adds: the drive-3 loader (A1's header table + A2's claims, checked against the drive manifest); R1 by size then by pixels; `same_acquisition_actions` (the decision rules, pure and tested); readings (`readings.csv`, applied only when `accepted`); a pilot batch and `cut_even` (batches under the cap, cut near equal); `localize` (copy once from J:, hash as read, keep only on a manifest match) and `verify-local` (re-hash the mirror from disk); a MAX_PATH guard. Canonical rule 2 and the drive order are profile data. |
| `tools/drive_staging/ingest_check.py` | `--profile`; check 1 re-derives drive 3's set from A1's table; check 5 allows no new project for drive 3 and requires active targets; check 7 only where the profile plans XMIC; **new** 3d (every same-second group decided for exactly the current membership), 3e (no planned file truncated: its last subblock ends inside the file; farm paths fit MAX_PATH), 8 (every link name unique and free in the live `raw_linked\`); 3c exempts a production row the pixel check compared the file with. |
| `tools/drive_staging/ingest_verify.py` | `--profile`; the batch's config name comes from the profile. |
| `tools/drive_staging/run_drives_batch.sh` | `run_drives_batch.sh [PROFILE] BATCH`; the checkout is where the script lives (the old one `cd`'d into a deleted worktree); settings come from `PROFILES`; every target project must be active; the dry run must also show 0 refused link names; **the validator is compared with its own run just before the batch** (the old fixed "10314" went stale on 2026-10-05, when D1(a) made it 0). |
| `tools/drive_staging/project_claims.py` | the run summary lists every drive it was given (it indexed `drive1`/`drive2` only; drives 1+2 print as before). |
| `tools/drive_staging/drive3/c_groups.py` | the pixel check wrapper: members, features (+ directory check), the tolerant tile cache, relations, classification (r4_groups.py's tests, unchanged). |
| `tools/drive_staging/drive3/c_prod_delta.py` | the proof of §0 (production since 10:30). |
| `tools/drive_staging/drive3/c_db_evidence.py` | the DB evidence for the (C) files of reading R5. |
| `tools/drive_staging/drive3/c_manifest_check.py` | the coordinator's independent post-batch check against the drive manifest (and close-out step 1). |
| `tools/drive_staging/drive3/c_report.py` | every number of this document, and the committed lists. |
| `tools/configs/drives3_2026-10/` | `drives3_Cxx.yaml` + `cases_Cxx.csv` per batch, `batches.csv`, `readings.csv` (generated, committed: every registry row's `ingest_config` must resolve to what produced it). |
| `tools/test_drives_ingest_plan.py` | +7 test groups: profiles, drive-3 canonical/people/MAX_PATH, the decision rules (scale-bar twins, truncated and preview production copies, crops, renamed re-saves, stale decisions), readings, `cut_even`, the verified copy, the 3c exemption. Full suite 38/38. |

**Left as they are, on purpose:** `historical_paths.py` and the placement code (`D3`, READMEs) are stream P's (A2 §4.5),
and `r4_groups.py` is used unchanged through the wrapper (its `D1`/`D2` helpers are not on drive 3's path). The
drives 1+2 regression: `ingest_verify` over B02 and B04 against production prints the same before and after.

---

## 8. Reproducing it

All commands from the worktree root, with `PYTHONDONTWRITEBYTECODE=1`. Every one is read-only on `J:\` (production and the
staged copy); they write under `D:\projects\gjesus3\drive3_streams\czi\` and, for the generated configs and lists, the repo.

```bash
P="--profile drive3_2026-10"
python tools/drive_staging/catalog.py production --staging "D:\projects\gjesus3\drive3_streams\czi" \
       --out "D:\projects\gjesus3\drive3_streams\czi\catalog"          # live production index (~4 min)
python tools/drive_staging/drive3/c_prod_delta.py                      # §0: production since 10:30, proved covered
python tools/drive_staging/ingest_plan.py $P plan                      # pass 1: candidates + the groups to check
python tools/drive_staging/ingest_plan.py $P localize --subset pixel   # the group members first (J: -> D:, hashed)
python tools/drive_staging/ingest_plan.py $P verify-local --subset pixel
python tools/drive_staging/drive3/c_groups.py all                      # the pixel check -> plan\pixel_decisions.csv
python tools/drive_staging/ingest_plan.py $P plan                      # pass 2: the decisions applied; batches
python tools/drive_staging/ingest_plan.py $P localize                  # every planned file (~1.5-2.5 h)
python tools/drive_staging/ingest_plan.py $P verify-local              # every planned file, from disk
python tools/drive_staging/ingest_plan.py $P farm
python tools/drive_staging/ingest_plan.py $P configs                   # -> tools/configs/drives3_2026-10/
python tools/drive_staging/ingest_check.py $P                          # §2, every batch (the engine's own resolution)
for B in C01 C02 C03 C04 C05; do python tools/ingest_raw.py -c tools/configs/drives3_2026-10/drives3_$B.yaml \
       --nas-root "J:\gjesus3-data" --dry-run > "D:\projects\gjesus3\drive3_streams\czi\plan\dryrun_$B.log"; done
python tools/drive_staging/drive3/c_db_evidence.py                     # the DB evidence for reading R5
python tools/drive_staging/drive3/c_report.py                          # every table here, and the tasks\drive3_czi_*.csv lists
bash D:/projects/gjesus3/drive3_streams/czi/scratch/rehearse.sh C01 C05   # §3 (scratch root on D:)
```

**Outputs** (`D:\projects\gjesus3\drive3_streams\czi\plan\`): `expected.csv` (one row per planned file), `excluded.csv`,
`nonraw_derived.csv`, `production_repairs.csv`, `out_of_scope.csv`, `conflicts.csv` (empty), `batches.csv`,
`plan_summary.json`, `pixel_candidates.csv`, `pixel_decisions.csv`, `groups\` (members, features, the tile caches,
relations), `localize_log.csv`, `check_report.json` + `check_cases.csv`, `dryrun_Cxx.log`, `db_evidence_c.csv`,
`prod_delta.txt`, `report_tables.txt`. **Committed:** the configs and case tables, `readings.csv`, and the lists
`tasks/drive3_czi_nonraw_for_stream_p.csv`, `drive3_czi_pixel_classification.csv`, `drive3_czi_blank_project_preview.csv`,
`drive3_czi_held.csv`, `drive3_czi_out_of_scope.csv`.

**After the ingest:** keep `local\` and `farm\` until the coordinator has verified every batch (close-out step 1 is
`c_manifest_check.py` over every batch); then delete them (643 GB on D:, a working copy, not a backup). The staged copy
on J: is deleted only on Ryan's go, at the drive's close-out.
