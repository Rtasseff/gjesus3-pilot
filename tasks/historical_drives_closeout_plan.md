# Historical microscopy drives: the close-out plan (coordinator)

**Written 2026-10-02 by the coordinating session,** so that the end of this effort survives a
context compaction or a change of session. **Status:** 🔶 in progress.
**Owner:** the coordinator (Opus, max effort), with Ryan's approvals.

**Start here when resuming.** Read `tasks/STATUS.md` §2's drives bullet first. Then work down this
file, marking steps done in place.

---

## The weekend of 2026-10-03/04: who runs what (Ryan out of office, reachable by Remote Control)

Decided by Ryan on 2026-10-02. Six streams, each in its own worktree with a `HANDOFF.md`. The
coordinator is this effort's planning session (named `gj3-handoff`). It reviews every dry run,
serialises production writes, verifies each write, and keeps this file, STATUS, CHANGELOG and
BACKLOG current.

| # | Stream (Step 5 item) | Branch · worktree under `gjesus3-dev\` | Run by | Model |
|---|---|---|---|---|
| A | Non-raw placement into project folders, plus prep for 2b/2c, plus the dot-file `.czi` (items 2, 2b, 2c) | `feat/drives-nonraw-placement` · `drives-nonraw-placement` | a session Ryan opens | Opus |
| B | The drives' MRI/PET-CT (DICOM) stream (item 4) | `feat/drives-dicom` · `drives-dicom` | a session Ryan opens | Opus |
| C | `LEONE` (item 5) | `feat/leone-ingest` · `leone-ingest` | a session Ryan opens | Opus |
| D | Same-timestamp group clean-up: scale bars, thumbnails, then scene splits (item 3) | `feat/drives-r4-cleanup` · `drives-r4-cleanup` | coordinator's subagent | Sonnet |
| E | Retire tool v2: re-identify (15 mis-coded rows) and content-equivalent duplicates (item 7) | `feat/retire-v2` · `retire-v2` | coordinator's subagent | Opus |
| F | The 2026-07-10 MRI session, then its 17 orphans (item 1) | `feat/mri-0710-reingest` · `mri-0710-reingest` | coordinator's subagent | Sonnet |

**Who may approve a production write (Ryan, 2026-10-02).**

- **The coordinator may approve, without waiting for Ryan, a write whose dry run matches what Ryan
  has already decided:**
  - the 32 twin retirements (Step 3);
  - the 2026-07-10 MRI session's re-ingest, then its 17 orphan retirements;
  - creating the already-approved projects (`AE-biomaGUNE-1116`, `-1420`, `-1520`, `Project-0521`,
    `AE-biomaGUNE-1319`);
  - copying non-raw files into project folders: copies only, nothing deleted, no registry row
    changed.
- **Everything else waits for Ryan's go over Remote Control:**
  - the `LEONE` ingest;
  - the drives' DICOM ingest;
  - the same-timestamp retirements (scale bars, thumbnails);
  - setting projects on blank rows (2b);
  - anything that departs from this plan.
- **One writer at a time.** A stream asks the coordinator for the write window, writes, verifies
  and reports back. Read-only work (analysis, dry runs) runs in parallel.

**Two placement decisions (Ryan, 2026-10-02).**

- **Where non-raw material goes in a project:**
  `<project>\working\historical_drives\<drive label>\<original folder path>\`. It goes under
  `working\`, not `outputs\`. The drive labels are `drive1_FRIO-X6` and `drive2_MFB-Disco-2`, the
  same as in the holding folder.
  - *Coordinator's reading:* derivatives of a specific acquisition go to the same place. That
    covers the 22 R3 files and the retire tool's `derivative` mode in item 3: pass `--subfolder`
    with that path instead of the tool's default `outputs\derived`.
- **The 63 `.lsm` files go to the holding folder** (item 2c), not to `/raw/`.

**Open questions for Ryan.** The coordinator keeps this list current; the newest are last.

1. **Unregistered MFB MRI sessions: who ingests them, and the go.** Stream F's read-only
   reconciliation of 2026-10-02 found 14 animal sessions (232 exams) and 5 phantom/QC studies
   (70 exams) on the scanner, in no registry (BACKLOG "14 MFB animal sessions on the scanner").
   - The 14 animal sessions: protocol 1125 in July, 9 sessions including m6; protocol 1025 this
     week, 5 sessions.
   - Since the 2026-06 bulk load, only two sessions were ingested.
   - **Recommendation:** the Data Office ingests the July 1125 series from the scanner, as `m12`
     was, once the operator is confirmed (likely Irene). The fresh 1025 sessions belong to the
     operators' normal workflow, but someone should ask them to ingest.
   - **The phantoms:** are they in scope?

   *The first finding, kept for the record:* **A second missing July MRI session: ingest it?** The session is
   `20260706_111010_jrc20260703_m6_1125`: 15 exams of animal 6 of protocol 1125
   (`PROJ-0021`), from 2026-07-06.
   - It is in no registry and has no `/raw/` folder. The counter `ACQ-20260706-MRI-` stands at 30,
     from two failed GUI attempts on 2026-07-16.
   - It is outside the pre-approval, which covers only `m12`.
   - **Its operator is not in the data.** ParaVision records only the shared login `nmr`. The
     evidence points to Irene: the same scan protocol, the same day's pulls, and the failed GUI
     attempt recorded as `ifernandez`.
   - **Recommendation:** ingest it from the scanner, as `m12` was, with operator Irene.
2. **15 Aperio `.svs` whole-slide scans** (~4.1 GB), in two nested zips under
   `PAPERS\TUNEL 230123 CDH5 JAGGED2\` in `Drive zuri 170823.zip`. The instrument is not onboarded.
   **Default,** by analogy with the `.lsm` decision: the holding folder, or project material if they
   sit under a project claim.
3. **671 TopSpin NMR experiments** (1.15 GB of chem-lab spectrometer data, not imaging), listed by
   stream B. **Default:** the same as question 2.
4. **Stream B's questions** (Phase 1 done 2026-10-02; review `tasks/drives_dicom_review.md` on
   `feat/drives-dicom`). Each has the coordinator's recommendation.
   - **Q1:** reopen `1519` (`PROJ-0008`, closed) for B02 (526 exams, March 2022) and B03 (136 exams,
     September 2020)? **Yes.**
   - **Q2:** B06, the 1019 MRS 2021 exams on the 11.7T (66): leave the project blank, like the 854
     other 2021 1019 exams (STATUS §0 D6)? **Yes, blank.**
   - **Q3:** 133 phantom and collaboration exams from 2022–23 (initials `prc`/`pr`): ingest with a
     blank project? **Yes.**
   - **Q4:** 363 exams from an external Bruker ICON in Madrid (Claudia, 4 mice, 2024): ingest as
     `XMRI` collaborator data, as was done for Charité's `XMIC`? **Yes.**
   - **Q5:** 3 PET/CT files from 2019 with no AE code: **hold them** with the `S:\gnuclear` set that
     is waiting for AE codes.
   - **Q6:** 18 Molecubes FDK reconstructions (Marina, `1321`) are in the `S:\gnuclear` snapshot but
     not in production. That is a gnuclear question, **not a drives ingest.**
   - **Q7:** go for B04 (`0619`, 236 exams), B05 (`0420`, 343) and N03 (`1319` PET/CT, 8, with the
     project created), once their dry runs are clean? **Yes.**
5. **Stream E's questions** (retire tool v2, built and unmerged on `feat/retire-v2`; review
   `tasks/retire_v2_review.md` §2.5). The coordinator reviewed it, and 30/30 test suites pass.
   - **Its finding:** of the 15 rows left to re-code, **only 2 are mis-coded acquisitions**
     (`ACQ-20240625-LSM9-001/-002` are Cell Observer files). **The other 13 `CELL` rows are ZEN
     exports of AxioScan scans already coded correctly:** 3 crops of `ZWSI-001…003` (2026-04-22) and
     10 single-scene splits of the two-scene scans `ZWSI-001…010` (2026-05-07). Each shares its
     scan's acquisition timestamp.
   - **E-Q1 (decide first):** retire the 13 as **derivatives** into their own project, `claudia`, at
     `working\<original folder>`, rather than re-coding them. **Yes.** This is your principle:
     exports are not acquisitions. It is a same-timestamp retirement, so it needs your go.
     - The rule the coordinator proposes: a derivative goes to its own registered project if it has
       one; otherwise, to the original's project.
   - **E-Q2 to E-Q8 (the design):** accept E's defaults as a package. **Yes.**
     - Re-identify in place: a hard link to the same file, so nothing is copied and every project
       link stays valid.
     - New dispositions `reidentified` and `equivalent`, so that `duplicate` still means
       byte-identical.
     - The evidence goes in `reason`, so the schema doesn't change.
     - Link names are unchanged; only the identity fields change; `bytes_fate` = `moved`; the
       no-chain rule stays.
   - **E-Q9:** retire `ACQ-20250915-LSM9-016` as `equivalent` of `-001`. You had said to leave the
     pair until this mode exists; it now exists. **Yes.**
   - **The go,** once the questions are answered:
     - re-identify the 2 `LSM9` rows as `CELL` (their dry run gives `ACQ-20240625-CELL-008/-009`);
     - the `equivalent` retirement;
     - the 13 derivative retirements.
6. **Stream A's interim report** (2026-10-02). Its session hit its usage limit, so Phase 1 is
   unfinished. Its branch is at `ebe9f8d`, and it has later edits that are not committed. It left a
   list for a fresh session; see the review on its branch once it is written.
   - **A blocker, for Ryan: path length.** 5,083 of the 6,206 files to place would get a UNC path
     longer than 259 characters (the longest is 402). All of them come from
     `Drive Maria Jesus and Irati 20211209.zip`. The options are:
     - shorter labels in the destination;
     - keeping that zip whole, as one file;
     - accepting long paths.
   - **250 `.czi` sit in nested archives,** most of them `LSM9` and most inside
     `Fotos confocales cdh5 jagged2.zip` within `Drive zuri`. That contradicts stream B's note. They
     include `8583.zip`'s 14. **They need deduplicating** against production, by SHA-256 and by
     (instrument, timestamp, name), before any raw one-off.
   - **Closed projects** would receive material: `0320` 14 documents, and `1519` 6, plus about
     10,110 of stream B's rows. That links to B-Q1.
   - **Unclear:** `Simu_2_V_XYZ.zip` (97 GB, which cannot be opened as a zip) and 2 unreadable
     `.czi` that have bytes.
   - **The dot-file `.czi`:** its dry run is clean (it would become `ACQ-20240125-CELL-050`). It needs
     Ryan's go.

**A gap found on 2026-10-02: the catalog never opened nested archives** (archives inside
archives).
- Stream B listed the 8 inside `Drive zuri 170823.zip`. One of them, `8583.zip`, holds **14 `.czi`
  that the ingest never saw**. Stream A takes them as raw stragglers, together with the dot-file.
- Stream A covers the remaining nested archives; `LEONE.zip` and `Cardiac MRI.zip` stay with their
  own streams.
- **This must be closed before the D: erase.** The test for the erase is that everything from the
  drives is accounted for.

**Decisions of 2026-10-04 (Ryan).** These answer questions 1–6 above.

- **Every recommendation in questions 1–5 is accepted as written**, and so is "go on the dot-file".
- **Long paths: neither long paths that throw errors, nor zips.** Researchers have to be able to
  browse. His words: "combine dropping high level dirs, putting info in an index or registry to
  help them find what info was dropped".
  - **Built by stream A:** `tools/drive_staging/historical_paths.py`.
  - **The layout:** `<project>\working\historical_drives\<FRIO-X6|MFB-Disco-2>\<study folder>\<path
    below>`.
  - **The budget** is 240 characters on `\\GJESUS3\gjesus3\`. The fewest folders needed are
    shortened deterministically (24 or 12 characters, then `~` and a 4-hex hash).
  - **Each project gets** `_INDEX.csv` (the full original path of every file), `README.txt`,
    `_PATHMAP.csv` and `_ORIGIN.txt`. A global index goes in `tasks/`.
  - **The result:** 0 of 75,683 destinations over the budget.
- **Fill the holding folder now** (A's Part 0, option B). It changes the earlier rule of filling it
  only when the mapping round closes. D: can then be erased once the streams finish.
- **LEONE is part of `DTS24`.** "Do not ingest any of the DICOM images that we already have. No
  duplicates." The new content goes into `DTS24`'s project folder as files:
  - 36 echo exams, MR supplements and 72 derived objects: 7,161 files, 59 GB;
  - at `working\historical_drives\FRIO-X6\LEONE\`;
  - with no new project, code or registry row.

  C's review doc and its scripts go into git.
- **Stream D's four lists are approved:** 153 retirements (3 scale-bar copies, 9 re-saves, 60
  exports, 81 ROI crops). `ID65_PB_lung_20x_scale.czi` stays in `/raw/`.
- **The 14 new nested `.czi`** (`8583.zip`) are ingested with a blank project.
- **Deletions on D:** stream B's and stream A's refused scratch deletions were approved and done by
  the coordinator.

**Production writes of 2026-10-04, each verified by its stream and checked independently by the
coordinator:**

- **Stream B ingested five batches,** 578 rows: B04a/b `0619` (232), B05a/b `0420` (338), and N03
  `1319` PET/CT (8). `AE-biomaGUNE-1319` (`PROJ-0061`) was created.
  - The registry went 25,212 → **25,790**, with 0 duplicates and 0 rows dated 2026.
  - 25 of 25 sampled files re-hash to their checksums, and 25 of 25 links are the same file.
- **Stream A created 4 projects:** `PROJ-0062` `AE-biomaGUNE-1116`, `PROJ-0063` `-1420`,
  `PROJ-0064` `-1520`, `PROJ-0065` `Project-0521`.
- **The coordinator reopened** `1519` (187 links) and `0320` (653), using `tools/reopen_project.py`.
- **Retire v2 is merged** (`8b0514c`), its statuses are updated (`867612c`), and 30 of 30 test suites
  pass.

---

## Where things are (2026-10-02)

| Stream | Branch / worktree | State |
|---|---|---|
| `.czi` ingest | `feat/drives-microscopy-ingest` · `gjesus3-dev\drives-microscopy-ingest` | B01–B04 by Opus (2026-09-30); **B05–B16 by a Sonnet session from `HANDOFF_RUN.md`**, nearly done. Plan frozen at `c5f7fff`: **8,790 files, 3.85 TB.** Not merged. |
| Retire tool | `feat/retire-acquisition` · `gjesus3-dev\retire-acquisition` | **✅ Merged to `main` 2026-10-02** (`361387f`), with the subject change made (subject rows are never deleted). Never run on production yet; its first uses are Step 3. |
| Analysis branches | `feat/drives-catalog`, `feat/drives-project-codes` | Merged 2026-09-29. Their worktrees are safe to remove. |

**The key files** are all on the ingest branch unless noted:

- `tasks/drives_ingest_dryrun_review.md`: the gate changes, and §11, the per-batch log;
- `tasks/drives_microscopy_ingest_runbook.md`: §6 is the after-the-last-batch list;
- `tasks/drives_ingest_provenance.csv`: one row per new ACQ-ID, plus 1 repair row;
- the worktree's `GATE_2026-09-30.md`, `ANSWERS_2026-10-01.md` and `ANSWER_B08_STOP.md`;
- on the retire branch: `tasks/retire_acquisition_review.md` and `tasks/retire_lists/`.

**Outputs on D: (not backed up, all regenerable):** `D:\projects\gjesus3\staging\` holds `_analysis\`
(`catalog`, `codes`, `ingest`), `_farm\` (hard links), `_extract\` (58 GB), `_repair\` (the
truncated original, 3.4 GB), `scratch_nas\` and `scratch_retire\`. The staged drives are in
`drive1_…\` and `drive2_…\`, 6.2 TB.

**Off-NAS backups:** `C:\Users\rtasseff\temp\`:

- `gjesus3_registry_backup_<date>_drives_B01…B16\`, one per batch;
- `gjesus3_reopen_backup_20260930_*\`;
- `gjesus3_drives_ingest_20260930\baseline_validate.txt`, which records 10,314 errors, all of them
  the known MRI `operator` placeholder.

---

## Step 1: verify the finished `.czi` ingest (✅ DONE 2026-10-02)

**Result: every check passed.**

- **Rows:** 8,790 drives rows; 0 blank dates; 5,055 blank project, matching Ryan's list.
- **Duplicates:** 12,304 microscopy `checksums.json` read. Duplicate content is only the known
  32 pairs, and re-saves only the known 23 groups; none touches a new row.
- **The integrity chain:** 8,791 of 8,791 provenance rows are in production's `checksums.json`,
  and 50 of 50 sampled rows match the drive manifests.
- **The repair:** `ACQ-20251031-CELL-003` and its `claudia` link both re-hash to the drive
  copy, and they are the same file.
- **The validator** (from `main`) is at 10,314 errors, all the known placeholder.

*The checklist that was used:*

Do this when Ryan says B16 is done. Read before writing.

1. **The run's own report.**
   - Review §11 has a row for every batch, B01–B16, with all checks passing, and every stop is
     explained. The known stop is B08 at 3c, resolved by the reviewed check edit.
   - Runbook §6 is done: `ingest_verify` over all 16 batches with `--provenance`, Ryan's list,
     the full validator, `metadata_completeness.py`, and the `historical_data_archives.md` update.
2. **Counts.**
   - `registry_raw` = 17,306 + 7,921 + whatever operators ingested meanwhile. Check the ingest
     rows by `ingest_config` (`drives_2026-09`): there should be **8,790**.
   - Projects: one created by this ingest (`0118` = `PROJ-0060`). `0219` and `1019` are active.
3. **Independent duplicate scan, read-only.** Use every microscopy `checksums.json`, plus the
   registry for the second check.
   - **(a)** No SHA-256 may sit under two ACQ-IDs, apart from the known **32** (22 `ZWSI`↔`ZWSI`,
     10 `CELL`↔`ZWSI`).
   - **(b)** The (instrument, acquisition timestamp to the second, lower-cased filename) key may
     find only the known **23** groups (22 `ZWSI`, plus `LSM9` `-001`/`-016`).
   - Anything new is a defect introduced by the run, so investigate it before merging.
4. **The integrity chain, from drive to production.**
   - Every `drives_ingest_provenance.csv` row has `manifest_verified` = Y, and its `sha256` equals
     the acquisition's `checksums.json` entry. Spot-check 50 rows against the staging
     `manifest.csv`.
   - The repair row for `ACQ-20251031-CELL-003`: re-hash the production primary **and** its
     `PROJ-0039` link from the NAS. Both must equal the drive manifest's
     `dc8e8fe75a7356ee8ad229d3b329ed5ebff72dfcaca6bf7555f1bea0dd2bc497`. Expect about 2 minutes
     over SMB; run it when the NAS is quiet.
5. **The validator** is at the 10,314 known errors and shows no new class.
6. **Ryan's list** exists: blank-project ACQ-IDs (about 5,055) with the claim each path carried.
   Hand it to Ryan.

## Step 2: merge both branches (✅ DONE 2026-10-02)

The ingest was merged in `0f052d5`. Only the two "Last Updated" lines (`00_INDEX`, `10_TOOLS`)
conflicted, and they were combined, newest first. `config.py` auto-merged with both changes
kept. 29 of 29 test suites pass on the merged tree.

The order is either, but the conflicts are known.

- **Retire tool: ✅ MERGED 2026-10-02** (`361387f`, pushed; backlog duplicates consolidated in
  `516b3b8`).
  - The subject change was reviewed: `registry_subjects.csv` is never touched, and the ✅ §2.8.3
    table is identical to `main`. The twin list is split into `…_zwsi.csv` (22) and `…_cell.csv`
    (10).
  - 27/27 test suites pass at the branch tip and on the merged `main`.
  - The scratch rehearsal was not re-run, because the change only removed a behaviour.
  - The tool is not yet used in production.
  - Its worktree `gjesus3-dev\retire-acquisition` is done, and goes in the Step 4 clean-up.
- **Ingest branch,** after Step 1 passes: merge `--no-ff`. **Expect conflicts:**
  - `tools/ingest/config.py`: both branches touch it. **Keep both** the `case_table` block and the
    retired-rows dedup.
  - Docs: `10_TOOLS.md` (§2.1.3 `case_table` vs §2.1 inventory and §3.9), `00_INDEX.md` (Last
    Updated: write one combined line), `GLOSSARY.md`, `INGEST_CLI.md`, `tools/INDEX.md`,
    `tasks/BACKLOG.md`.
  - Then run all tests on `main`, and apply the review doc's proposed STATUS and CHANGELOG
    wording.
  - Push.

## Step 3: the first retirements in production (✅ DONE 2026-10-02)

**Result: both operations ran, and both were verified independently.** Under Ryan's pre-approval,
each full dry run had to show every pair byte-identical and match the approved list exactly; both
did.

- **The 22 `ZWSI` twins:** run `RET-20261002-115731-642`. Backup:
  `C:\Users\rtasseff\temp\gjesus3_retire_backup_20261002-115731-642\`.
  - The registry went 25,227 → 25,205 and stayed BOM-free with CRLF line endings.
  - 22 tombstones were written, the rows and folders are gone, and the survivors are intact.
  - The validator shows 10,314 errors, all the known placeholder, with no new class.
- **The 10 `CELL` copies:** run `RET-20261002-121520-505`. Backup:
  `…\gjesus3_retire_backup_20261002-121520-505\`.
  - The registry went 25,205 → 25,195, with 32 tombstones in all.
  - **All 10 of Claudia's links are the same file as their `ZWSI` survivor** (`os.path.samefile`),
    under the same names.
  - This also fixes 10 of the 25 mis-coded rows; the other 15 wait for retire v2 (stream E).
  - The validator checked 25,195 rows: 10,314 errors, all the known placeholder, and warnings
    unchanged at 23,859. There is no new class.
- The global Finder page is left to the 03:00 job.

*The procedure, as it was planned:*

Do this after Step 2, with nothing ingesting. **Each operation is its own dry run, then Ryan's go,
then `--execute`, then verify.**

1. Split `tasks/retire_lists/2026-10_sha256_twins.csv` into `…_zwsi.csv` (22) and `…_cell.csv`
   (10), if the session hasn't already.
2. **The 22 `ZWSI` pairs.**
   - Keep `ACQ-20260304-ZWSI-001…022`; retire `-023…044`.
   - No project folder changes, because the twins never got links.
   - Run with `--quick`, then a full dry run (about 45 GB of SMB reads), then `--execute`.
   - Verify: 22 tombstones, the rows are gone, the folders are gone, and the validator is clean.
3. **The 10 `CELL` copies.**
   - Keep `ACQ-20260507-ZWSI-001…010`; retire `CELL-001…010`.
   - Claudia's 10 `raw_linked` links are re-pointed under the same names.
   - Verify by file identity. **This also fixes 10 of the 25 mis-coded rows.**
4. Afterwards, regenerate the global Finder page, or let the 03:00 job do it.

## Step 4: clean-up

Do these after Steps 2–3. Read `memory/onedrive_worktree_delete_lock.md` before removing anything:
OneDrive marks the directories read-only.

- **Worktrees:**
  - ✅ **Done 2026-10-02:** all four effort worktrees are gone (`drives-catalog`,
    `drives-project-codes`, `retire-acquisition`, `drives-microscopy-ingest`), and their branches
    are deleted locally and on GitHub;
  - ✅ **D: scratch done 2026-10-02:** `_farm\` (hard links only, verified on a sample of 40),
    `_repair\`, `catalog_smoke*`, `scratch_nas\` and `scratch_retire\` are deleted, reclaiming
    ~40 GB. The staged trees are untouched: 43,121 / 35,718 / 347 files before and after.
  - delete the merged branches, local and remote;
  - **never** touch `ni-live-hardening` or `code-review-2026-08`, which belong to other sessions;
  - update `gjesus3-dev\README.md`.
- **D: scratch:** `scratch_nas\`, `scratch_retire\`, `_analysis\catalog_smoke*` and `_repair\`
  can be deleted after Step 1. `_farm\` holds hard links only, so deleting it frees nothing; delete
  it after the merge.
- **The staged drive data on D: is erased once we are satisfied that everything from these
  drives is in gjesus3 production** (Ryan, 2026-10-02). That covers `drive1_…\`, `drive2_…\`,
  `_extract\`, `_analysis\` and `_farm\`, and the test is that every ingested file has been
  verified against its drive manifest.
  - **It is a temporary working copy on Ryan's own drive, not a backup.** D: is not shared lab
    storage, and this work is for a single lab.
  - **The owners keep their external drives and the data on them;** they have no intention of
    removing it.
  - The lab knows gjesus3 has no off-site backup yet (INFRA-06; Ryan is working on it). gjesus3 is
    already an improvement on two SSDs.
  - **Until erased, it feeds the work still to come** (Step 5): the non-raw placement, the
    mapping of the no-project groups, the holding folder, the DICOM stream and `LEONE` all read
    their sources from it.
  - **Timing (Ryan, 2026-10-02):** there is no fixed week limit. The point is **not an
    indefinite hold**. Holding D: is fine as long as we are working through this plan towards an
    end. The erase comes after Step 5's items 2–5 (below) are done.

## Step 5: the remaining work, each its own worktree and fresh session later

In rough order:

1. **✅ DONE 2026-10-02 (stream F, merged `fba7e76`).** The session was re-ingested as
   `ACQ-20260710-MRI-018…034`, from the scanner's current copy. The 17 orphans were then retired
   (run `RET-20261002-133115-491`, 17 tombstones, backed up whole). The coordinator verified both
   writes. Record: `tasks/mri_0710_reingest_review.md`. *The plan as written:* **Re-ingest the
   missing MRI session** `jrc20260710_m12_1125_bis` (17 exams, animal 12 of
   protocol 1125) from the scanner, through the normal MRI path. Its no-DICOM exams go on the
   regen worklist. **Then** retire the 17 empty `ACQ-20260710-MRI-*` orphans (`--orphan`, list in
   `tasks/retire_lists/`).
2. **Non-raw placement into project folders** (Ryan, 2026-10-02):
   - **What goes in:**
     - the 22 R3 derivatives in `_analysis\ingest\nonraw_derived.csv`, each tied to its parent
       ACQ-ID (the 18 ROI crops go to `1123`);
     - every non-raw file under a claim root: analysis outputs, figures and presentations.
   - **The `.tif`/`.lsm` files are non-raw here.** About 476 distinct sit under a project claim
     (155 GB). Most are ZEN exports (the TIFF `Software` tag says ZEN). The TEM camera (`ImageSP`)
     and gel-imager (`ChemoStar`) images go with the project material, as decided for `.dm4`/EM.
   - **Create** the paperwork projects `AE-biomaGUNE-1116`, `-1420`, `-1520` and `Project-0521`
     (with the `0720` documents).
   - **Excluded:**
     - installed software, system files and the personal/admin heuristic hits;
     - **the ~277 `.czi` re-saves.** They are the same acquisition as something already in
       `/raw/` and linked into its project. Their paths stay in the provenance file (Ryan,
       2026-10-02: skip them).
   - **One raw one-off:** the hidden dot-file `.czi` (`Cell observer\Laura\Cell observer\Interaccion-LS-SPN\.LS-SPN-20x-8.czi`)
     is a real acquisition. It goes into **`/raw/`**, renamed in a copy or as a single-case
     config, because the engine's glob skips dot-files.
2b. **Map the no-project groups** (Ryan, 2026-10-02).
   - **Input:** Ryan's list (blank-project ACQ-IDs with the claim each path carried, from the
     ingest's runbook §6) plus `_analysis\codes\noclaim_groups.csv` (291 groups).
   - **Work:** a human maps groups to projects, existing or new (new ones need Ryan's approval).
   - **For each mapped group:**
     - set `project_id` on its blank raw rows. This is write-once-if-blank (`set_project_id_if_blank`).
     - create the project links;
     - place its non-raw material in the project folder, as in item 2.
2c. **The holding folder for whatever is still unmapped** (Ryan, 2026-10-02).
   - **When:** the mapping round closes.
   - **What:** the remaining non-raw material moves to **`J:\gjesus3-data\staging\historical_drives_unassigned\`**,
     **in the same directory structure as on the drives** (`drive1_FRIO-X6\…`, `drive2_MFB-Disco-2\…`).
     The folders themselves may tell people which project something came from.
   - **Its `README.txt` says plainly:**
     - where the files came from (the two operator drives, their labels and serials, staged
       2026-09-22/28);
     - that they are **not in gjesus3**, because they are not raw data and have not been assigned
       to a project;
     - that the originals remain on the owners' external drives;
     - how to have something placed into a project (ask the Data Office).
   - **Also include** a manifest CSV (relative path, size, SHA-256, taken from the drive
     manifests).
   - **Same exclusions as item 2:** software, system files and personal/admin hits. The holding
     folder is group-readable.
3. **Clean up the same-timestamp groups:** BACKLOG "Clean up the drives ingest's same-timestamp
   groups".
   - Scale-bar copies and thumbnails move to the original's project folder through the retire
     tool's `derivative` mode.
   - Scene splits and stitched copies get a per-group pixel check first.
   - `ID65_PB_lung_20x_scale.czi` has no group flag.
4. **The drives' DICOM stream:**
   - `Cardiac MRI.zip` (`1519`, `0619`; **`1519` is closed**, so reopen it case by case);
   - Laura's Bruker MRI (`0721`, `1321`);
   - Haizpea's `project0420`;
   - Peio's `1319` PET/CT. **Create** `AE-biomaGUNE-1319` (approved) and check it against NI
     production first;
   - the loose `.dcm`/`.nii` files;
   - pre-2022 internal MRI that exists only here.
5. **`LEONE.zip` → a new project `LEONE` (Ryan, 2026-10-02: in scope, and approved).**
   - **The data:** human clinical cardiac MRI. 82 GB zipped, 141 GB uncompressed, 671,410 DICOM
     members; 17 case folders (`LEONE1.01`, `LEONE 1.13`, `LEONE 304`, `CNIC`, `ExportLeone`,
     nested `Leone-*.zip`).
   - **Approval:** storage at biomaGUNE is covered by the collaboration agreements with the people
     who collected it, and the institute has no additional policies (BACKLOG META-12).
   - **Before ingesting, compare against `DTS24` (`PROJ-0054`):** it already holds the LIONS cohort
     as 42 cases, stored as **zip primaries**, so the comparison has to be member by member.
     LEONE looks like a related working set, not a clean duplicate.
   - **Follow `DTS24`'s pattern:**
     - instrument `XMRI`;
     - a `collaborator:` `data_source`;
     - the 08_METADATA §4.10 privacy allow-list: no date of birth in sidecars;
     - a pseudonymous operator `subject:` block, so the animal DB is never consulted.
   - **Read first:** BACKLOG 🔺 "external collaborator archives are one row per EXAM, not per
     series" and 🔸 "pick ONE archive container"; both decide its shape.
   - **Sequencing (Ryan, 2026-10-02):** copy LEONE **now**, within this effort and while the
     staged data is still on D:, and don't wait for anything. The two 🔺 HIGH (top) items, the
     human/privacy flag and the DPA reference, come **later**. They are then **back-filled in
     place** on LEONE, the `DTS24` acquisitions (both cohorts) and the Charité `XMIC` files.
     Nothing is deleted, re-ingested or reloaded from source.
6. **`.tif`/`.lsm`: settled as non-raw** (items 2 and 2c). The 63 `.lsm` files are LSM 5-series
   confocal acquisitions from an instrument that is not onboarded, and none has a project.
   **✅ Decided (Ryan, 2026-10-02): they go to the holding folder,** not to `/raw/`.
7. **Backlog leftovers this effort produced:**
   - the project-date recompute and its engine fix;
   - the production `.czi` truncation audit;
   - v2 re-identify for the remaining 15 mis-coded rows;
   - v2 content-equivalent duplicates (the `LSM9` re-save);
   - reconsidering a status column (MEDIUM) and quarantine-and-purge (LOW).
