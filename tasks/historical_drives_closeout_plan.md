# Historical microscopy drives: the close-out plan (coordinator)

**Written 2026-10-02 by the coordinating session,** so that the end of this effort survives a
context compaction or a change of session. **Status:** 🔶 in progress.
**Owner:** the coordinator (Opus, max effort), with Ryan's approvals.

**Start here when resuming.** Read `tasks/STATUS.md` §2's drives bullet first. Then work down this
file, marking steps done in place.

---

## Where things are (2026-10-02)

| Stream | Branch / worktree | State |
|---|---|---|
| `.czi` ingest | `feat/drives-microscopy-ingest` · `gjesus3-dev\drives-microscopy-ingest` | B01–B04 by Opus (2026-09-30); **B05–B16 by a Sonnet session from `HANDOFF_RUN.md`**, nearly done. Plan frozen at `c5f7fff`: **8,790 files, 3.85 TB.** Not merged. |
| Retire tool | `feat/retire-acquisition` · `gjesus3-dev\retire-acquisition` | Built and approved. Its session is applying the one change: **never delete subject rows** (`ANSWERS_2026-10-01.md`). Not merged; never run on production. |
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

## Step 1: verify the finished `.czi` ingest

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

## Step 2: merge both branches

The order is either, but the conflicts are known.

- **Retire tool:** first review the session's subject change. It is small: the tool, test 6, the
  revert of the 06 §2.8.3 row, and 10_TOOLS inventory row #5. Then run all tests, merge
  `--no-ff`, and push.
  - Safe even mid-ingest: shared-code changes do nothing until `retired_acquisitions.csv` exists,
    and the tool refuses to run while the registry is changing.
- **Ingest branch,** after Step 1 passes: merge `--no-ff`. **Expect conflicts:**
  - `tools/ingest/config.py`: both branches touch it. **Keep both** the `case_table` block and the
    retired-rows dedup.
  - Docs: `10_TOOLS.md` (§2.1.3 `case_table` vs §2.1 inventory and §3.9), `00_INDEX.md` (Last
    Updated: write one combined line), `GLOSSARY.md`, `INGEST_CLI.md`, `tools/INDEX.md`,
    `tasks/BACKLOG.md`.
  - Then run all tests on `main`, and apply the review doc's proposed STATUS and CHANGELOG
    wording.
  - Push.

## Step 3: the first retirements in production

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
  - remove `drives-catalog`, `drives-project-codes`, `drives-microscopy-ingest` and
    `retire-acquisition`;
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
  - **Until erased, it feeds the work still to come** (Step 5): the non-raw placement, the DICOM
    stream and the `.tif`/`.lsm` decision read their sources from it. If D: space is needed before
    those are done, the alternative is to re-stage only what they need from the owners' drives
    later. That is Ryan's call.

## Step 5: the remaining work, each its own worktree and fresh session later

In rough order:

1. **Re-ingest the missing MRI session** `jrc20260710_m12_1125_bis` (17 exams, animal 12 of
   protocol 1125) from the scanner, through the normal MRI path. Its no-DICOM exams go on the
   regen worklist. **Then** retire the 17 empty `ACQ-20260710-MRI-*` orphans (`--orphan`, list in
   `tasks/retire_lists/`).
2. **Non-raw placement into project folders:**
   - the 22 R3 derivatives in `_analysis\ingest\nonraw_derived.csv` (the 18 ROI crops go to `1123`);
   - analysis outputs, figures and presentations under each claim root;
   - **create** the paperwork projects `AE-biomaGUNE-1116`, `-1420`, `-1520` and `Project-0521`
     (with the `0720` documents);
   - exclude software and the personal/admin hits.
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
5. **`LEONE.zip`:** human clinical data. The META-12 privacy policy comes first.
6. **The `.tif`/`.lsm` decision:** raw or export.
7. **Backlog leftovers this effort produced:**
   - the project-date recompute and its engine fix;
   - the production `.czi` truncation audit;
   - v2 re-identify for the remaining 15 mis-coded rows;
   - v2 content-equivalent duplicates (the `LSM9` re-save);
   - reconsidering a status column (MEDIUM) and quarantine-and-purge (LOW).
