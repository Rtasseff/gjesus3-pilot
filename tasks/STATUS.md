# gjesus3 RDM Pilot — Status

**Last Updated:** 2026-10-09

This is the **lean current-state** view: where the system is *right now* and the few
things genuinely in flight. It deliberately stays short.

- **Later improvements** (refinements, second-/third-stage features) live in
  [`BACKLOG.md`](BACKLOG.md) — that is the home for "this makes it better later."
- **Full dated history** (every design decision and ingest round) lives in
  [`../CHANGELOG.md`](../CHANGELOG.md) and the authoritative specs in
  [`../mfb-rdm-docs/`](../mfb-rdm-docs/) (start at
  [`00_INDEX.md`](../mfb-rdm-docs/00_INDEX.md)).
- **Detailed historical work trails** (the old 749-line task list and the
  per-pass handoff/plan notes) are archived under [`archive/`](archive/).

---

## 0. ⚠️ DECISIONS WAITING ON RYAN — read this first after a break

**Ryan ruled on every open item on 2026-10-05.** His rulings are recorded below in his words. He is
away **2026-10-12 → 10-18**, and **nothing here needs him before 10-19.** If carrying out a ruling
would need a new decision from him, it is written into this section and the work stops there.

### 0.1 Ryan's rulings of 2026-10-05 (each ✅ DECIDED 2026-10-05, Ryan)

| # | Ryan's ruling, in his words | Where it stands |
|---|---|---|
| **D1(a)** | "NOW. Replace the placeholder on the 10,314 MRI operator cells with a hold value meaning "awaiting claim". You choose the token, document it where the blank sentinel is documented, and make the validator accept it; no OK from me needed on the name. Done when the validator passes with 0 errors and only those 10,314 cells changed." | **✅ Done 2026-10-05.** The token is **`pending-claim`**. It is documented where blank = unknown is documented (06_REGISTRIES §2.3 and §2.3a-bis, 08_METADATA §4.7.2) and in the GLOSSARY. The validator accepts it in `operator` (one info line) and reports an ERROR when it is the whole value of any other column (merge `2b891d5`; 36/36 suites). **The write** (`tools/repair_operator_hold.py --apply --expect 10314`): **exactly 10,314 cells changed**, all MRI, `operator` only. The tool verified it, and so did an independent byte oracle; the other 8 registry files are byte-identical. **Validator: exit 0, 0 errors, 0 warnings; `operator awaiting claim (pending-claim): 10314`.** The full run, with the sidecar checks, also gives 0 errors (27,126 warnings, all the documented unknown sentinels). The sidecars keep the old text until (c), and the Finder shows the new value after its 03:00 rebuild. Backups: `C:\Users\rtasseff\temp\gjesus3_registry_backup_20261005_preD1a\` and `…\gjesus3_operator_hold_20261005\`. |
| **D1(b)** | "NOW, build only, do not send. A claim list for Jesús's group: one row per session or folder (not per acquisition) with project, date, session name and acquisition count, plus blank columns for who ran it. Make it similar to the projects xlsx we just did … You can put it in projects folder as well because more people will have some access to that. … I send it at the pilot re-launch and set the claim window then." | **✅ Built 2026-10-05, not sent:** `J:\gjesus3-data\projects\_MRI sessions - who ran them.xlsx`. **926 sessions** (one row per session folder on the scanner), **21 projects** (4 of them closed), 10,314 acquisitions, 2022-01-10 → 2026-06-05. Sheets: Read me (the claim window's end is left blank for Ryan), Sessions to claim (yellow: Who ran it, Notes, Answered by; a grey session key), Projects, Acquisitions. Ryan sends it at the pilot re-launch. |
| **D1(c)** | "LATER. After the claim window closes, blank whatever is still unclaimed. Record it in BACKLOG, dated to the window end; do nothing now." | In [`BACKLOG.md`](BACKLOG.md) (the 🔺 `operator` item), due when the claim window closes. Ryan sets the window at the pilot re-launch. |
| **D2** | "I am emailing Irene today. When her answer arrives: if 37, repair by the recovery-tool pattern in BACKLOG (HIGH, 2026-08-21), 19 sidecars and 19 registry rows, ACQ-IDs kept; if 39, record it and close." | Waiting on Irene's answer. No decision is left for Ryan. [`BACKLOG.md`](BACKLOG.md) HIGH (2026-08-21) |
| **D3** | "NOW. Make the ingest report every study folder that matches neither regex (code change on a branch, with tests), then re-scan the historical sources read-only and report the count. Reconcile it with the drives DICOM review §5 as it stands after the weekend." | **✅ Done 2026-10-05** (merge `188d737`, 37/37 suites). The CLI (a NOT PARSED section in BATCH SUMMARY, `--unparsed-report <csv>`), the GUI preview and `mri-ingest` now list every study folder whose name matches no rule, one line per study with its exam count. The deployed GUI exe does not, until it is rebuilt (§0.4 N3). **The count, re-scanned read-only: 1,481 study folders / 11,602 exam folders** match neither regex: the scanner 1,364 / 9,869, `K:` 9 / 165, the drives 108 / 1,568. Of these, 1,147 / 8,290 are other groups'. **§5 reconciles exactly:** of its 1,568 drive exams, 1,417 are now in production (stream B's eight configs), 109 are copies on the same drive, 24 are not registered under the 10-04 line, 18 were never acquired, and 0 are unexplained. **MFB data missing from gjesus3:** 59 study folders / 451 exam folders (51 on the scanner, 8 on `K:`). Review: [`mri_unparsed_rescan_review.md`](mri_unparsed_rescan_review.md). The decisions it raises are §0.4; none is urgent, since the platform archives what leaves the scanner (Ryan, 2026-10-06). |
| **D4, D5** | "SegBioMed's decisions, not mine. Move both to the SegBioMed memo/backlog and off §0. Apply nothing." | Moved to the SegBioMed memo (REPLY 7) and the [`BACKLOG.md`](BACKLOG.md) item "the curated-datasets pilot returned 19 spec gaps". Nothing applied. |
| **D6** | "Held until SegBioMed starts, after the leadership write-up. Off §0, into BACKLOG with that trigger." | Moved to [`BACKLOG.md`](BACKLOG.md) 🕗 "mint the `SegBioMed` project", with that trigger. |
| **D7** | "NOW. Flip the five header-only exams to terminal no-source." | **✅ Done 2026-10-05.** The five worklist rows went `pending` → `no-source` (`backfill_dicom_regen.py --apply --mark-no-source`, limited to the five ACQ-IDs). **Verified:** only those five rows changed, and only `status`; the worklist is now not-applicable 365, regenerated 164, no-source 99, pending 0; the invariant holds (`backfill_pending_dicom.py --dry-run`: 0 to add). **Checked first, read-only:** the scanner still holds the study, and its copy matches the staged one: none of the five has a `2dseq` or a `fid`. Exam 7 (a cine) holds only `rawdata.job0/1`, which Dicomifier cannot use; a ParaVision reconstruction on the scanner would still be possible. Backup: `C:\Users\rtasseff\temp\gjesus3_registry_backup_20261005_preD7\`. |
| **D8** | "Held until there is pull. Order: the cardiac MRI segmentation pipeline on the image servers first, then MILabs, then the SegBioMed project minted with a first fibrosis project. Into BACKLOG with that order." | Moved to [`BACKLOG.md`](BACKLOG.md) 🕗 "held until there is pull", in that order. |
| **D9** | "Closed. The mixed-now, converge-later assumption holds." | Closed. [`../mfb-rdm-docs/12_CURATED_DATASETS.md`](../mfb-rdm-docs/12_CURATED_DATASETS.md) CDS-03 is ✅ DECIDED. |

**The 10-04 close-out list** (Ryan, 2026-10-05). Two of these rulings arrived after the work was done:
- `roi_crops`: "I am handling it today." **✅ Done 2026-10-05:** run by the coordinator on Ryan's instruction that day; 81 retired and verified.
- The D: erase: "not before 10-19. I give the go myself." **⚠️ Already done on 2026-10-05,** on Ryan's approval earlier that day ("your plan is solid, you have my approval"). It cannot be undone, and nothing remains to do. The records are kept at `J:\gjesus3-data\staging\historical_drives_records\`.
- "The 209 link folders, the 2b worksheet (62 rows) and the smaller decisions: held until 10-19. Keep them in STATUS §0, ordered by cost of delay." **The 209 link folders were ✅ fixed on 2026-10-05** on Ryan's go (589 links made; the final audit shows 0 missing and 0 polluted). The rest is §0.2.

### 0.2 Held until 2026-10-19, ordered by cost of delay

| # | Item | Cost of delay | Detail |
|---|---|---|---|
| **H1** | **The 2b mapping:** which project each held group of drive files belongs to (the 62 `A` rows). It is with Jesús's group as the workbook `J:\gjesus3-data\projects\_Historical data - assign to projects.xlsx` (290 groups). New project names need Ryan's approval, and the registry part needs his go. | 54,721 files sit in `staging\historical_drives_unassigned\`, outside every project, where researchers do not look. The 61 derivatives and proposal (c) wait on it too. | [`BACKLOG.md`](BACKLOG.md) 🔺 2b; runbook `tasks/drives_nonraw_2b_2c_followup.md` |
| **H2** | **The five protocol-1025 MRI sessions of 2026-10-01/02** (m25–m29) are on the scanner only. The ask is that the operators (Irene) ingest them through the GUI. | MFB data on one machine, unregistered; who ran it gets harder to recall | [`BACKLOG.md`](BACKLOG.md) 🔸 "14 MFB animal sessions" |
| **H3** | **Claudia's `nrn01`/`nrn02`** (Q8): one external study whose folder says mouse 01 and whose subject file says 02. It keeps the subject file's value unless Claudia says otherwise. | A wrong mouse label looks like data | `tasks/drives_dicom_review.md` Q8 |
| **H4** | **Lucia, `AE-biomaGUNE-0118`:** the animal links of 147 files wait until Lucia (or Ainhize) confirms the animal numbers belong to `0118`. | Low: the files are in the right project; only the subject links are missing | [`BACKLOG.md`](BACKLOG.md) 🔹 small follow-ups |
| **H5** | **The CoS hub's stand-name reading** (its historical-drives `HANDOFF.md` §7.2/§8.6). | Low: a future session reading the hub could identify an instrument wrongly | [`BACKLOG.md`](BACKLOG.md) 🔹 small follow-ups |
| **H6** | **The 365 + 99 legacy MRI placeholders** (94, plus the five D7 rows since 2026-10-05) (empty rows from before the 2026-10-04 line): retire them, or leave them. | None: the state is consistent | [`BACKLOG.md`](BACKLOG.md) 🔸 "existing MRI rows that fall outside the 2026-10-04 line" |
| **H7** | **Another group's (`jl`) study nested in m3's folder** on the scanner: tell the `jl` group, or not. | None for gjesus3 | [`BACKLOG.md`](BACKLOG.md) 🔹 |

*(The holding-folder ACL is decided: no change, Ryan 2026-10-05.)*

### 0.3 While Ryan is away (asked for 2026-10-05, each reported as a verified result or a count)

- **Front doors:** one current registry figure plus a pointer to §1 as the single source. **✅ Done 2026-10-05 (`e86b31b`):** README, GLOSSARY, 00_INDEX, 01_OVERVIEW (twice) and 13 now say 27,034 acquisitions on 2026-10-05 and link §1. §1 was brought up to date first (64 projects, 1,288 subjects, per-instrument counts).
- **Merge `docs/ni-tunnel-live`** if it is docs-only and `main`'s checks pass. **✅ Merged 2026-10-05 (`4625f38`):** one commit, six `.md` files; `main` passed 35/35 test suites first. Two conflicts in the record files were resolved by hand. The worktree stays for its own session.
- **Feasibility only, no build:** can per-user access be logged on the gjesus3 share and the web apps (Finder, Project Manager)? What is possible, what it costs, and who would have to switch it on. **✅ Done 2026-10-05:** [`access_logging_feasibility.md`](access_logging_feasibility.md); nothing was switched on. **The NAS: yes.** QNAP's QuLog Center can log each user's SMB file access (user, PC, path, open/read/write/delete/rename) for the whole NAS, not one folder. QNAP warns of a slight slowdown; it keeps up to 5 million entries and can forward them. The NAS administrator (institute IT, to confirm) switches it on. **The Finder: no.** It is a static file, so only the file read is visible. **The Project Manager: not today.** It is a local program and records only provenance rows. A small audit log would take about a day, or it comes free with the planned server-era app. **First, for any of them:** the DPO's sign-off and notice to staff (GDPR; LOPDGDD art. 87).

### 0.4 New from D3 (2026-10-05): decisions for Ryan, ordered by cost of delay

The read-only re-scan (`tasks/mri_unparsed_rescan_review.md`) raised these. **None is urgent:** the platform clears the acquisition machine when its disk fills (it now keeps about two years) and moves the data to the platform's own archive first, with a deep-storage copy as well (Ryan, 2026-10-06).
So nothing that leaves the scanner is lost. *(Corrected 2026-10-06: the first version of this table called it a permanent loss.)*

| # | Decision | Cost of delay | Detail |
|---|---|---|---|
| **N3** | **Rebuild and redeploy the operator GUI exe**, so operators see the NOT PARSED list (a deploy). | Until then, the deployed exe still calls an unparsed study "housekeeping", so a new silent skip is possible | review §8 R8 |
| **N5** | **A durable queue, `registries\pending_unparsed.csv`**: a new registry convention, which the review recommends. | The June bulk load's skip list (145 studies) existed and still went nowhere | review §6; §8 R7 |
| **N1** | **Ingest the 51 MFB studies that the June upload skipped and that are still on the scanner** (310 exam folders, 305 images): 25 from 2024, 25 from 2025, and one phantom from 2026. Each would go through a scoped config, as for G1. All 51 were on the June list and marked skip: 28 with the information present but not parseable, 16 naming no project or animal, and 7 phantoms. | Low: if they leave the scanner they go to the platform's archive and can be pulled from there | review §5; §8 R1 |
| **N2** | **140 scanner study folders (1,125 images) with another group's initials but an MFB link** (protocol `0721`, whose facility-DB holder is Daniel Padró; LP-IONP; the Portugal phantom series): in, out, or per subgroup? | Low, as for N1 | review §3 (b?); §8 R2 |
| **N4** | **`jr250416_m1_0423_1`** (7 images, 2025). Its initials were typed `jr`, so the `jrc` pull filter missed it. Ingest it? | Low, as for N1 | review §7; §8 R6 |
| **N6** | **The 57 MFB study folders from 2022 that the June upload skipped** (23 animal sessions of `0619`, `0618`, `0721` and `0220`; 34 phantom and coil tests). They are off the acquisition machine and expected in the platform's archive. Ingest them from there with the platform manager's agreement, or leave them. | Low: the platform's archive keeps them | review §6; §8 R4 |
| **N7** | **Ermal's 8 `0118` sessions of 2021 on `K:`** (141 exam folders): ingest them? | Low: `K:` does not age off | review §3 (c); §8 R3 |

### 0.5 The M. Jesús drive: Ryan's rulings of 2026-10-06 (each ✅ DECIDED 2026-10-06, Ryan)

| # | Ryan's ruling, in his words | Where it stands |
|---|---|---|
| **M1** | "keep everything in AE-biomaGUNE-0118 and name both models in its description" | **Supersedes the 2026-09-30 two-project ruling** (the DB shows `0118` ran a hypoxia and a monocrotaline model side by side, crossing the drive's folders). No new project. The description is applied with the drive's other descriptions after the PET/CT write; the 1,760 held placement rows and the `0118` MRI go to `AE-biomaGUNE-0118`. |
| **M2** | "please ingest them if we have everything we need, otherwise make a note of them and the fact that we need to check them against the originals in a separate location we can ssh into later." | Stream M (to build): the 3,309 MRI image exams production lacks, from the drive's copies; every one is listed for a later check against the platform's originals ([`BACKLOG.md`](BACKLOG.md)). The 61 `1019` sessions of 2020 go to `AE-biomaGUNE-1019` (the default; not objected). |
| **M3** | "I will send what is in tasks/drive3_questions_for_mjesus.md to jesus or Irene but I don't know if anyone can answer these. It may not be detailed enough for someone that had only a high level view of her project." | **Rewritten as v2 on 2026-10-06:** 14 questions, each with its context and a default if nobody knows, so a blank answer is fine. Ryan sends it. |
| **Pigs** | "The pig pulmonary-artery masks come from a Philips 3T at CNIC in 2014, which isn't one of our instruments so I don't want to register them, but they should go into a project. We should log the reconstructed images with any metadata appropriate for a metadata sidecar as xmri ingests. those ingests and the segmentations need to be assigned a project. it will not have a biomagune protocol number so we can just make up a project name if it has not been done yet." | A new project **`CNIC-HEARDS`** (no animal protocol; "HEARDS" is the study label in the images): the reconstructed images registered as `XMRI` (external, `collaborator:CNIC`), the masks placed in the project, not curated. Part of stream M's build. |
| **Segmentations** | "I actually have access to older MRI data from the source … We will ingest it after this. then we may have a much better trace. so do not loose those segmentations." | Every label is placed in its project or the holding folder, and the staged copy is not cleared until `biomaGUNE MJ` (which holds more of them) is done. A3's trace is re-run after the platform-archive ingest ([`BACKLOG.md`](BACKLOG.md)). |
| **C, repair** | "You have my approval to start the Cell Observer batches if you think we are ready …" and "If stream C needs an in-place repair, then please do it." | Both run after the PET/CT write is verified (one registry writer at a time): the `ACQ-20230707-CELL-001` repair, then the C01 pilot, then C02–C05. |
| **Hold** | "the pending-claim hold was not something special for the 10,314 old placeholder rows. It is a known issue with loading historical data the way we are doing it now. in the future people will use the tools we have made for GJesus3 to ingest data, this will prompt them for the needed data like operator or researcher. however all hsitorical data is missing it for MRI. that is exactly why we have the workbook to claim the studies and all new hsitrical data shoudl follow the same paater of 'pneding-claim' and being listed in the work book." (Ryan, 2026-10-07) | **The rule:** historical internal MRI loaded without an operator gets `operator = pending-claim` and its sessions are listed in `_MRI sessions - who ran them.xlsx`. Applied to the drive-3 MRI (3,309) and to the earlier historical loads that carry a blank operator (drives 1+2 MRI 1,393; the 2021 `1019` recovery and G1 878; the July phantom/QC studies 69), 5,649 in all, after the drive-3 writes; external `XMRI` is out of scope. The workbooks lose the month in their names (Ryan, 2026-10-07; never sent under the old names) and are appended to, never rebuilt. |

**Still open for Ryan:** nothing; the `1521`/`0618` reopen was approved and done on 2026-10-06.

### 0.6 The MRI platform's archive: Ryan's rulings of 2026-10-07 (each ✅ DECIDED 2026-10-07, Ryan)

The archive (`mriuser@10.10.3.175:/share/homes/mriuser/backup_7T_olddata_260824`; read-only, **never written**, no
parallel reads 08:00–18:00 Mon–Fri; normal tools never point at it) was censused by listing only
([`mri_archive_census.md`](mri_archive_census.md), merge `f3dd43f`). Ryan: *"I am giving you the go and I agree with all
your recommendations."*

| # | Ruling | Where it stands |
|---|---|---|
| Q1 | **Go for the pull**: 780 archives, 219 GB (the 650 new MFB studies and the 130 for the drive-3 originals check), after hours, one connection; the platform manager is told as a courtesy | the download step is being built; first window tonight after 18:00 |
| Q2 | **The 77 MFB phantoms / QC are ingested**, as July's `jrc` phantoms were | in the ingest build |
| Q3 | **The 9 studies with other initials on the shared `1116` protocol stay out** for now (as §0.4 N2) | listed, not pulled |
| Q4 | **The 6 MFB studies whose code is no gjesus3 project are ingested with no project**, and listed in the assign workbook | in the ingest build |
| Q5 | **`AE-biomaGUNE-0220` is reopened** for its 3 studies of 2022 | at ingest time |
| Q6 | **The 25 archives with no `.sha1`** are checked by the compression's own checksum plus a full tar listing | in the download step |
| Q7 | **Ryan asks the platform manager** where July–August 2020, the missing June 2020 days, 2022-01-25, 2023 and the older 11.7 T data are | with Ryan; 41 of drive 3's 7 T studies have no archive copy; also two archive tarballs that are themselves short (`m21_1019`, `m3r7f2_Caff`; their `.sha1` was taken from the short file) |

**Progress (2026-10-08):**
- **Download:** night 1 verified 552 of 780 archives (175 GB, 0 bad; one connection, 3.6 MB/s, stopped itself at 07:36);
  the other 228 (≈ 44 GB) run tonight from 18:01.
- **Drive 3 against these originals** (`feat/mri-archive-ingest`, `tasks/drive3_mri_archive_check.md`): of the 3,309
  drive-3 exams, 2,346 have a study in the archive and **none differs**: 1,576 byte-identical, 340 pixel-identical
  re-exports, 63 converted exams whose `2dseq` matches; 367 have a reconstruction on one side only, each explained; 963 are
  not in the archive (267 from the 11.7 T, 696 on days the archive lacks). M. Jesús's copies are faithful.
- **The ingest plan:** all 650 new studies assigned to 17 batches (532 into 12 projects, 118 with no project); the 422
  local so far rehearsed (5,531 exams, 18/18 checks, 0 failed), every operator `pending-claim`. **The coordinator's calls,
  within the rulings:** projects from facility-DB procedure dates for the 128 code-less studies (the 2026-09-29 DB-date
  rule, consistent by series); 13 studies keep their claimed project without a subject id (as stream M's M09); the 3 typo
  suspects stay with no project (Q4); the one image exam the archive adds (`jrc210322_m131_0619/7`) is ingested.
- **✅ The DICOM-less MRI placeholders are retired (2026-10-09, 11:35–12:06; Ryan's go on the dry run `D:\projects\gjesus3\mri_placeholder_retire\prod_20261009_1104\`).** 464 rows (365 spectroscopy/calibration, 99 with no convertible reconstruction): 459 in projects (incl. `0220`'s 135) and 5 with no project (→ `staging\mri_not_registered\`), disposition `no-dicom`; their files hard-linked into `<project>\working\mri_not_registered\` with a README (the 10 drive-3 exams point at their placed k-space). Each list self-check OK, re-runs no-op; invariants ALL OK (447 empty link folders removed, the other 21,124 link entries unchanged); validator 0 errors; registry 42,954 rows; `pending-claim` 23,126; no placeholder left. Backups: `C:\Users\rtasseff\temp\gjesus3_retire_backup_20261009-113554-472\`, `…-115946-793\`. Also merged today: `feat/ni-live-hardening` (`3127ad0`, 50/50 suites; gated by the coordinator).
- **✅ The MRI archive ingest is complete (2026-10-09, 10:25).** Resumed on Ryan's instruction at 08:27 (`write --from AR08_1019`: AR08 re-verified 18/18 after the restored manifest row), then AR09–AR14: **all 18 batches written and verified, 7,627 exams** (650 studies + `jrc210322_m131_0619/7`); final validator OK, `pending-claim` 23,590 = 15,963 + 7,627; registry 43,418 rows. **Left: the claim-workbook append** (627 sessions, 7,626 acquisitions): its dry run refused because `_MRI sessions - who ran them.xlsx` is open in Excel (lock since 08:42); nothing written; run `python tools/claim_workbooks.py claims-append --nas-root J:\gjesus3-data --apply --backup-dir <dir>` once it is closed. Also left: the read-only `post` phase (full re-hash, idempotent dry runs; `ar_16_production.sh post`, 2–3 h).
- **(history) ⏸ The ingest is running, paused (2026-10-09, 04:06).** Ryan's go (10-08 ~22:45, conditional on a clean gate); gate clean (merged `f50ade4`: 650 studies + 1 exam, 7,627 exams, 18 batches; the coordinator re-checked names, studies and same-day sessions). `ar_16_production.sh write` from 02:12: 0220 reopened; **11 of 18 batches written and verified: AR03, AR01, AR02, AR02n, AR04, AR04n, AR05, AR05n, AR06, AR07, AR08 = 3,860 exams.** AR08's verify stopped on M1 (`ingest_manifest.csv` +1,280, expected +1,281): one append lost to a transient SMB error (`[WinError -2146893818] Invalid Signature`, 03:49:15, `ACQ-20210611-MRI-053`; registry row, files, sidecar, link complete). **The row was restored byte-exact at ~04:20** (backup `C:\Users\rtasseff\temp\gjesus3_mri_archive_20261009\ingest_manifest.before_row_fix.csv`). **Resume needs Ryan's instruction** (the auto-mode classifier stopped the coordinator here): from the worktree `gjesus3-dev\mri-archive-ingest`, `bash tools/drive_staging/mri_archive/ar_16_production.sh write --from AR08_1019` (AR08's committed exams are skipped, its verify re-run against the kept pre-batch backup; then AR09, AR09n, AR10, AR11, AR12, AR13, AR14 = 3,767 exams, the validator, the claim-workbook append; ≈ 1 h 45). The NI session holds its writes until the coordinator says the window is closed.
- **Next (was):** the last 228 by Fri 07:45, the same scripts over them, the coordinator's gate, then **Ryan's go for the ingest**
  (a registry write; `0220` is reopened right before its batch).

**Where the SegBioMed conversation lives:** the full exchange with the SegBioMed project is appended to
`projects\Imaging\SegBioMed\harvest\MEMO_for_gjesus3_agent.md` (REPLY 7 carries the 2026-10-05
rulings). Read it if D2's or the SegBioMed items' context is needed.

### 0.7 NI live sync: one decision (2026-10-09)

- **Recover 103 older `pending-db` animal records?** A read-only dry run on 2026-10-09 found 103 of
  the 291 non-NI rows in `pending_subject_metadata.csv` recoverable from the animal DB: 96 MRI and
  7 slide-scanner (ZWSI) acquisitions, all from 2026, **all single-animal** (the multi-animal shape
  behind the 2026-10-08 bug does not occur). On a go: tell the coordinator, back up the 103
  sidecars, `--apply` scoped with `--acq-ids`, check every animal block against its own DB record,
  then refresh the subjects table. The other 188 are not in the animal DB under their project and
  stay queued ([`BACKLOG.md`](BACKLOG.md), "292 `pending-db` subject rows").
- Irene's supervised first sync is Ryan's and Irene's to schedule; nothing waits on it.

### Re-verifying this page before you trust it

Every number above is measured, not remembered — but production moves, so **check before acting**.
All read-only, seconds to run:

```bash
# row count (compare against the §1 table)
python -c "import csv,io;print(sum(1 for _ in csv.DictReader(io.open(r'J:\gjesus3-data\registries\registry_raw.csv',encoding='utf-8-sig',newline=''))))"

# the validator -- green since 2026-10-05 (D1(a)); ANY error now is new, so read it
PYTHONPATH=tools python tools/validate_registries.py --nas-root "J:\gjesus3-data" --no-enrichment
#   expected: validation OK, 0 errors, 0 warnings, and the info line
#   "operator awaiting claim (pending-claim): 10314" (until D1(c) blanks the unclaimed).

# D7 -- what is still queued for DICOM regeneration
python -c "import csv,io,collections;print(collections.Counter(r['status'] for r in csv.DictReader(io.open(r'J:\gjesus3-data\registries\pending_dicom_regen.csv',encoding='utf-8-sig',newline=''))))"
#   expected: not-applicable 365, regenerated 164, no-source 99, pending 0 (the five D7 exams were flipped 2026-10-05)

# curated datasets -- should be 4 rows
python -c "import csv,io;print(len(list(csv.DictReader(io.open(r'J:\gjesus3-data\registries\registry_datasets.csv',encoding='utf-8-sig',newline='')))))"
```

**Registry backups taken before the 2026-08-21 production writes** (sha256-verified byte-identical
at the time, off-NAS):

| Path | State captured |
|---|---|
| `C:\Users\rtasseff\temp\gjesus3_registry_backup_20260821_preG1\` | after the 854-acquisition 1019 ingest, **before** G1 |
| `C:\Users\rtasseff\temp\gjesus3_registry_backup_20260821_1019_ingest\` | **name is misleading** — it was overwritten by a re-run and holds the *post*-1019 state, not the pre-1019 one |
| `C:\Users\rtasseff\temp\gjesus3_registry_backup_20260820_mri_model\` | before the `instrument_model` repair |

> ⚠️ **There is no off-NAS snapshot of the pre-1019 registry** — the directory named for it was
> overwritten by a re-run of the backup script. Nothing is unrecoverable (all 854 rows carry
> `ingest_config: tools/configs/mri_1019_kgjesus_2021_*.yaml`, so they are identifiable and
> removable), but the tidy rollback artifact is gone. **Use a fresh, dated directory per write.**

---

## 1. Current state — TRUE PRODUCTION

gjesus3 has been in **true production since the 2026-06-10 restart**. The earlier
quasi-production pilot (per-instrument test → purge → accept, then a whole-system
purge after the team exhibition) is **complete and historical** — that purge already
happened on 2026-06-10. **There is no future exhibition / purge / restart pending.**
All data is real and retained long-term; treat the registry and `/raw/` with
production care.

**Scale (live `J:\gjesus3-data`):**

| | |
|---|---|
| Acquisitions in `/raw/` | **35,613 on 2026-10-07 (evening)**, after the M. Jesús drive's Cell Observer C02–C05 (+4,913; all 4,955 of stream C in). Before that, **30,700 on 2026-10-07 (midday)**, after the M. Jesús drive's MRI (+3,309) and the CNIC pig series (+27), with Cell Observer C02–C05 being written (§2). Before that, **27,364 on 2026-10-06 (night)**, after the M. Jesús drive's Cell Observer pilot C01 (+42; §2). Before that, **27,322**, after its PET/CT (+202: CT 115, PET 87). Before that, **27,120 on 2026-10-06**, after a routine operator AxioScan ingest that morning (+86 `ZWSI`, operator MBC, into `0619`, `0522`, `0424` and `1019`). Before that, **27,034 on 2026-10-05**, after the last same-timestamp list (−81 ROI crops). Before that, **27,115 on 2026-10-04, at the end of the weekend close-out.** The steps: −72 same-timestamp derivatives retired (stream D); +526 from the drives' last DICOM batches (stream B); +15 raw stragglers (stream A: the dot-file `.czi` and 14 nested `.czi`). Before that, **26,646** after retire v2's first operations (−1 equivalent, −13 derivatives; 2 re-identified in place). Before that, **26,660**: **+660** from the drives' `1519` MRI (stream B), and **+210** from the July protocol-1125 MRI series and the `jrc` phantoms, from the scanner (stream F). Before that, **25,790 on 2026-10-04**: **+578** from the drives' MRI/PET-CT (stream B: `0619`, `0420`, `1319`; §2). Before that, **25,212 on 2026-10-02**: **+17** from the re-ingested 2026-07-10 MRI session (§2), after the first retirements (**−32** duplicate registrations, §2) had taken it to 25,195. Before that: **25,227**, after **+8,790** historical `.czi` from the operators' external drives (§2); then: 16,437 on 2026-09-30, after +62 operator AxioScan on 2026-09-29. Earlier history: **16,375** (all checksummed + `metadata.json` sidecar'd) — 15,474 until 2026-08-21, then **+854** from the 2021 `Proyecto 1019` recovery, **+24** from the G1 session, and **+23** from a routine operator AxioScan ingest on 2026-08-26 (`PROJ-0059`). Also — includes the **75 human** cardiac-MRI acquisitions of `DTS24` (§2) and the **1,508** from the `S:\gnuclear` NI backfill (§3) |
| Projects | **65 registered on 2026-10-07**: 64 active and 1 `closed`, after `CNIC-HEARDS` (PROJ-0066, external pig MRI, no animal protocol) was created. On 2026-10-06: 64, 63 active and 1 `closed`, after `AE-biomaGUNE-1121`, `-1521` and `-0618` were reopened for the M. Jesús drive (§2). On 2026-10-05: 60 active and 4 `closed` (63 folders). The historical-drives work added `PROJ-0062`…`0065` and reopened two. Earlier: 58 registered, 50 active + 8 `closed` (3 folders deleted 2026-07-14). Every live folder carries the four subfolders since the 2026-08-12 backfill. **Folder name == project name** since 2026-08-02 (no `proj-` prefix) — see §2. |
| Subjects (`registry_subjects.csv`) | **1,288 on 2026-10-05** (one row per subject). Earlier: **1,165** (1,124 until the 2026-08-21 ingests added the 2021 animals) — was 1,146 until the 2026-08-16 `-None` subject-id repair, which dropped 65 ambiguous rows and added back 43 real ones (see 2). The 2026-08-19 PROJ-0056 repair left the total unchanged (3 rows dropped, 3 added). |
| Curated datasets (`registry_datasets.csv`) | **4** — `DS-SEG-0001`…`0004`, segmentation, DICOM ecosystem. Area deployed 2026-08-21 as a pilot (`CDS-01` decided). Provenance traceability verified **100% on all four**. |
| Publications | empty — deferred (PLANNED) |

**Two registry facts changed on 2026-07-14** (see [`../CHANGELOG.md`](../CHANGELOG.md)):

- **`researcher` was backfilled onto 2,049 of the 13,557 acquisitions then in `/raw/`**
  (from the project name where it named a person; lowercase first name). The rest were
  left blank — their project names name no person, so there was nothing to recover from,
  and anything better needs a new source rather than another pass over the same data.
  The count is now **3,966 of 15,474**, the difference being later ingests that carry a
  researcher of their own (the `S:\gnuclear` NI backfill takes it from the researcher's
  own folder name).
- **`registry_projects.csv` `start_date` / `last_activity` mean *acquisition* dates**,
  not ingest dates (they were previously a uniform 2026-06-1x ingest stamp). Projects
  are closed — folder deleted, row kept with `status=closed` — once the newest linked
  acquisition is **older than 3 years**. Project links are hard links, so a close-out
  never touches `/raw/`.

**Instruments live (all in scope, operational):**

- **Microscopy** — AxioScan 7 (`ZWSI`), Cell Observer (`CELL`), LSM 900 confocal (`LSM9`)
- **MRI** — Bruker ParaVision (`MRI`)
- **Nuclear Imaging** — Molecubes / MILabs PET / SPECT / CT (`PET`, `SPECT`, `CT`)

All on-network historical imaging is ingested. Per-instrument counts (live, 2026-10-06):
MRI 12,828 + 438 `XMRI` (external), Cell Observer 9,683, LSM 900 1,189, **Nuclear Imaging 1,850**
(CT 1,268 + PET 582), AxioScan 7 1,038, and 338 external microscopy (`XMIC`). Total 27,364.
(Before the historical drives, on 2026-08-13: MRI 10,330 + 75 `XMRI`, Cell Observer 1,739,
Nuclear Imaging 1,640, AxioScan 7 885, LSM 900 805.) (Durable per-instrument record:
[`../equipment/historical_data_archives.md`](../equipment/historical_data_archives.md).)

**Tooling deployed:**

- **Operator GUI — `gjesus3_ingest.exe`** (one frozen Windows executable, ~95 MB,
  microscopy + MRI pages) is **live on the NAS** at
  `\\GJESUS3\gjesus3\gjesus3-data\tools\` (deployed 2026-06-24), with two UNC
  shortcuts and in-app HTML guides. The MRI page pulls **read-only** from the
  scanner over SFTP. See [`../mfb-rdm-docs/10_TOOLS.md`](../mfb-rdm-docs/10_TOOLS.md) §5.2
  and [`../tools/OPERATOR_FAQ.md`](../tools/OPERATOR_FAQ.md).
- **Researcher Finder — `registries/index.html`** (self-contained searchable index
  of the registry, ~19 MB) is **live since 2026-06-23** — a global index plus a
  per-project `index.html` in each project folder. Researchers double-click it over
  SMB; no server. **Refresh reworked 2026-07-20:** a scheduled global rebuild + a
  targeted per-project refresh when an ingest writes into a project (CLI opt-in via
  `--refresh-index`), replacing the old wholesale-rebuild-on-every-ingest. Both
  paths are live; the daily **global** rebuild now runs via the `WorkstationOps`
  `finder-refresh` op (03:00) — see §2.
  See [`../tools/FINDER.md`](../tools/FINDER.md).
- **Command-line ingest** (`tools/ingest_raw.py` + per-instrument configs) is the
  data-office path for bulk / historical ingest. See
  [`../tools/INGEST_CLI.md`](../tools/INGEST_CLI.md).

The system is **ready for operator hand-off across all instruments** and for batch
historical ingest. Nothing is mid-ingest; it is safe to restart at any time.

---

## 2. Active / Up next

The genuinely in-flight items (kept tight — everything else is in
[`BACKLOG.md`](BACKLOG.md)):

- **The M. Jesús drive (third historical drive): 🔶 ASSESSED 2026-10-06 (read-only; merge `d659270`). Production work is next.**
  - **What it is:** M. Jesús's own working drive (`MJesus-MFB-biomaGUNE`, WD serial `WX22D623YP29`), on loan on 2026-09-29 and since returned to her. The CoS hub staged it to `J:\_staging_drive3_MJ\drive3_MJesus_WX22D623YP29\`, outside `gjesus3-data`: **621,969 files, 1,681 GB (1,565.8 GiB), 0 read errors, and a clean verify.** The 7 verify failures are AppleDouble `._.DS_Store` files that the NAS rewrites; each was re-read from the drive and matched. The hub's brief and evidence are in `...\DataInfra\gjesus3-archive\historical-mjesus-drive\` (`HANDOFF.md`, `records\`); a snapshot is on `D:\projects\gjesus3\drive3_analysis\hub_records_snapshot_20261006\`. The staged copy is one of two copies (the owner has the drive), so it stays until ingest checksums match its manifest.
  - **Ryan's rulings of 2026-09-30, made with the hub** (recorded here so that they outlive its brief):
    - material goes inside the matching existing project, and that project's description gains the drive's own wording (e.g. `AE-biomaGUNE-0525` ← `Proyecto 0525 2DG y manosa`);
    - a new project only after its code is confirmed in the animal-facility DB, never guessed;
    - identify what is already in `/raw/`, dedup by SHA-256 only, and ingest only raw that is genuinely absent ("anything that genuinely should be in `/raw/` and is not, may be ingested");
    - **reopen `AE-biomaGUNE-1519` and `-1121`** and redo their links. 1519 was reopened on 2026-10-04 by stream B; **1121 remains**;
    - **`0118` is one protocol with two projects**, `Proyecto-0118-rats-hipoxia` and `Proyecto-0118-Monocrotalina`: now §0.5 M1, because the animals cross the folders. The name form `Proyecto-XXXX-abc` is for a second project under a real protocol; `Project-NNNN` stays for codes that are not protocols (05_PROJECTS §2a.7);
    - the **331 Bruker studies** the hub found missing from production are a note for Ryan, not an action: now §0.5 M2;
    - exclude junk (`desktop.ini`, `Thumbs.db`, AppleDouble) and two WD installers;
    - closed projects should be **moved, not deleted** (`projects_closed\`), with a "close a project" action in the Project Manager. This is a proposal for Ryan ([`BACKLOG.md`](BACKLOG.md)); A2 §7 has the smallest change and its open questions.
  - **The hub's brief predates the drives 1+2 work:** `0118`, `0521`, `1319` and `1420` now have projects (PROJ-0060…0065), and `1519`, `1019` and `0320` are reopened.
  - **✅ `stage_copy.py` v1.5 adopted (merge `82d4e97`, 38/38 suites).** The repo had v1.1. The hub's v1.5 master on D: went with the 2026-10-05 erase; its NAS record (`J:\gjesus3-data\staging\historical_drives_records\_tools\`) is byte-identical to what is now committed, and **the repo is the master copy from now on.** A new test (74 checks, mutation-tested) shows the source is only read and each file opened once. The README carries a release check (`copy` exits 0 even when files failed) and four known limits ([`BACKLOG.md`](BACKLOG.md) 🔹).
  - **The assessment:** three read-only parts, each reviewed and spot-checked by the coordinator.
    - **A1, the raw imaging** ([`drive3_raw_coverage.md`](drive3_raw_coverage.md)): 117,212 files (67.4 GB) are byte-identical to production. Counted by acquisition, production already holds 3,965 of the drive's 7,345 MRI exams (192 of them as pixel-identical re-exports), 290 of 492 PET/CT reconstructions, and 836 of 6,094 microscopy files.
      - **MRI not in production:** 3,380 exams in 198 studies. 3,132 have the scanner's DICOM, 177 can be converted, 71 cannot. Nearly all are from 2019–2021; adding them is +5.3 GB.
      - **PET/CT not in production:** 202 reconstructions, 201 of them DB-confirmed. 100 of these were held back in the `S:\gnuclear` snapshot, although their own paths carry a valid code.
      - **Microscopy not in production:** 5,258 files, 803 GB. 5,115 are Cell Observer files; 116 come from a second Axioscan 7 and 26 from a Leica SP8, neither of them gjesus3's.
      - The hub's "331 missing studies" are 190. *Coordinator check:* all 190 are absent from the registry by study name.
    - **A2, projects and placement** ([`drive3_projects_and_placement.md`](drive3_projects_and_placement.md)): every protocol code on the drive is already a gjesus3 project. The non-raw material is 89,640 files (208.7 GB), not the hub's 124 GB, because the hub counted 84.6 GB of `Splits` MetaImage volumes as raw. 19,599 of those files are already placed by the drives 1+2 work.
      - **To place:** 29,794 files (75.5 GB) in 15 projects now, and 3,975 more after the 1121 reopen. Every path is at most 240 characters.
      - **`AE-biomaGUNE-1121` reopens cleanly:** 546 links, 0 collisions.
      - **The `0118` folders cross the protocol's two PAH models** (§0.5 M1). *Coordinator check:* re-queried in the DB.
    - **A3, the segmentations** ([`drive3_segmentations_cds.md`](drive3_segmentations_cds.md)): 8,617 distinct labels in 12 sets; most of the "segmentation" bytes are images. **3,859 labels (44.8 %) trace to production ACQ-IDs**, 3,003 of them by direct pixel comparison.
      - **By age:** the cohorts of 2022–2024 trace at 83–100 %, those of 2019–2021 at 0–7 %, because their MRI is not in production (§0.5 M2 would make 1,923 more traceable).
      - **The candidate:** CAND-A, 3,234 LV/RV cine masks from 189 sessions and 161 animals (§0.5 M3).
      - **Two open SegBioMed questions answered:** the 0/1/2 labels are blood pools, and DS-SEG-0001's slice order checks out by pixels (confirming DS-SEG-0004's `m85` correction).
      - *Coordinator checks:* DS-SEG-0004's 178 reader files were re-hashed and found on the drive, and one CAND-A stack was re-traced with an independent loader (11 of 11 slices at NCC 1.0000).
  - **Going ahead within the rulings** (the plan and its streams: [`drive3_production_plan.md`](drive3_production_plan.md)). Each production write is serialised and verified by the coordinator. As for drives 1+2 (Ryan, 2026-10-02), copies into project folders are the coordinator's to approve, while **each ingest, and the reopens of `1521` and `0618`, take Ryan's go after the coordinator has gated the dry run**:
    - **✅ `AE-biomaGUNE-1121` reopened 2026-10-06** (ruled), with `tools/reopen_project.py`, after a dry run. **Verified independently:** only `registry_projects.csv` changed, and in it only PROJ-0009's `status` (closed → active) and `notes`; its format is unchanged; all 546 link folders hold exactly their acquisition's `.dcm` files, and all 12,867 are hard links of `/raw/` (0 problems); the validator is unchanged (0 errors, 0 warnings, the 10,314 `pending-claim` info line). Backups: `C:\Users\rtasseff\temp\gjesus3_registry_backup_20261006_pre1121reopen\` and the tool's own `…\gjesus3_reopen_backup_20261006_115911_AE-biomaGUNE-1121\`. `-1521` and `-0618` reopen at placement, for their 19 documents (05 §4.y: reopened case by case when new data turns up);
    - **the non-raw placement**, on A2's plan:
      - one study folder per content;
      - A2's four evidence readings, which fill blank projects and overrule no claim;
      - the 25 files drives 1+2 placed under another project also go into drive 3's;
      - holding for the pig set, the group's 3D Slicer tool and the model outputs.
      - The placement code first has to learn a third drive (`historical_paths.py` and the READMEs know two);
    - the PET/CT reconstructions not in production (202): stream N, built and dry-run. **Gate cleared by the coordinator 2026-10-06** (its read-only pre-flight re-run matched exactly; 6 random cases checked against header and DB). **✅ Ryan's go, 2026-10-06:** run by a fresh session (Sonnet, medium) from `gjesus3-dev\drive3-petct\HANDOFF_RUN.md`; the window is open (no other registry writer);
    - **✅ Ryan's go, 2026-10-06, for stream C's in-place repair of `ACQ-20230707-CELL-001`** (production holds a 0.5 MB preview of `ID187_10x.czi`; drive 3 holds the 360 MB original). Runs after the PET/CT write is verified (one registry writer at a time);
    - the Cell Observer files (5,115, 643 GB): stream C, through the drives' gate (re-saves, same-timestamp groups, claims), then Ryan's go;
    - the descriptions (17, with the drive's wording first), once M1 is answered;
    - **✅ the label-meaning and slice-order evidence went to SegBioMed** (their D4/D5) on 2026-10-06, as REPLY 8 in `projects\Imaging\SegBioMed\harvest\MEMO_for_gjesus3_agent.md`. Nothing was applied.
    - **Streams P, N and C are cut and building** (2026-10-06; worktrees `drive3-placement`, `drive3-petct`, `drive3-czi`). Each ends in a gate document; nothing reaches production before the coordinator's gate, and the ingests not before Ryan's go.
  - **Ryan ruled on M1–M3 on 2026-10-06** (§0.5), and approved the `1521`/`0618` reopen.
  - **✅ Written to production and verified, 2026-10-06 (evening):**
    - **PET/CT (stream N), +202** (merge `33cfe94`): run by the coordinator on Ryan's go (gate §7 steps 2–3). Registry 27,120 → 27,322; `petct_16_verify` 18/18 PASS (every file re-hashed equal to `checksums.json` and to the drive or snapshot manifest; links, sidecars, subjects, provenance); validator unchanged; idempotent re-runs 0. **The discovery fix also releases 160 more of August's held-back NI acquisitions; the `ni_gnuclear_prod_*.yaml` configs must not be run for real until that is decided** ([`BACKLOG.md`](BACKLOG.md)).
    - **`ACQ-20230707-CELL-001` repaired in place** (Ryan's go): production held a 0.5 MB preview; it now holds the 360 MB scan (SHA-256 `71973934…` = the drive manifest = `checksums.json`; 48 of 48 subblocks readable; `file_size_mb` 0.5 → 360.5). The sidecar already described the full image. Backup `C:\Users\rtasseff\temp\gjesus3_repair_backup_20261006_173228_ACQ-20230707-CELL-001\`.
    - **`AE-biomaGUNE-1521` and `-0618` reopened** (Ryan's go; 73 and 48 links recreated, 0 collisions).
    - **18 project descriptions** (the drive's own wording, and `0118` naming both models, M1): exactly 18 `description` cells changed, format kept. Validator after all of it: 0 errors, 0 warnings, the 10,314 `pending-claim` line.
  - **✅ Stream P (placement) done and verified, 2026-10-06** (merge `d7ee770`; copy-only; a Sonnet runner from the gate's command list). **37,339 files, 124.5 GB:** 31,003 into 17 project folders (`working\historical_drives\MJesus-MFB\`), 4,576 into the holding folder (`staging\historical_drives_unassigned\MJesus-MFB\`: the pig set, the group's Slicer tool, model outputs, (C) material), and the 1,760 `0118` files into `AE-biomaGUNE-0118` (M1). Re-gated once: the 20 `1521`/`0618` rows moved from held to place after their reopen (coordinator's diff: only those rows). Every window verified (walk, manifest, indexes kept, provenance, re-hash samples 0 mismatches, ACLs inherited); 0 files already in `/raw/`.
  - **✅ Stream C's pilot C01 written and verified, 2026-10-06:** 42 Cell Observer `.czi`, every gate check PASS, manifest check PASS, validator unchanged; registry **27,364**. **C02–C05 (4,913 files, ~636 GB) wait:** the runner's auto-mode permission check refused the C02 batch command as relayed by the coordinator, so it needs Ryan's direct authorisation (in the coordinator's session, a permission rule, or his own run session).
  - **✅ The M. Jesús drive is closed out (2026-10-08, night).** **Biodonostia's Axioscan as `XMIC`** (Ryan's go ~19:25 with readings L1 + L2: the slide labels decide, `1422` 25 / `0424` 23 / `1019` 15 / `0522` 11 / 9 blank; `researcher` `MJ`, the note names Elena): X01 7 + X02 69 + X03 7 = **83 rows**, every batch's 12 checks, verify, manifest check and re-run PASS, validator 0 errors before and after (`tasks/drive3_foreign_raw_gate.md`). The close-out handover (121 placed, 72 held), the Leica files (26 → `AE-biomaGUNE-1121`), 2 stray `.czi` (holding) and the 12 renamed scan copies (`0424` 9, `1019` 3) copied and verified (the `0424` tree check flagged only `registry_subjects.csv`, changed by the NI session's 12 `1025` rows, confirmed against its backup). **Final reconciliation `READY TO DELETE`** (`final_20261008_2317`: 0 blockers, 0 kept files without a good NAS copy, 0 unlisted files). **Evidence** copied to `staging\historical_drives_records\drive3_MJesus_WX22D623YP29\` (3,554 files, `RECORDS VERIFY PASS`; `records_manifest.csv` +3,554, README section). **The staged copy deleted** on Ryan's go (robocopy list-only 621,980 = 621,969 + 11 records, then removed, exit 2); one 56 KB `copy.log` is delete-pending behind an open handle (its copy is in the evidence). Space returns after the QTS recycle bin is emptied and the snapshots since 2026-10-02 expire. Under the DICOM-only rule the drive's ParaVision originals went with it (75.4 GB for the 963 exams the platform archive lacks). Next: `D:` scratch clean-up (standing approval), worktree removal.
  - **Drive-3 close-out (2026-10-08, `8b3c256`):** the reconciliation (`tasks/drive3_closeout.md`, `tools/drive_staging/drive3/closeout.py`) gives every one of the 621,969 files one fate by SHA-256: **`BLOCKED: 380`** on 10-08 = 172 outside-instrument files (cleared by `feat/drive3-foreign-raw`) + 82 files no batch had placed (78 Cell Observer derivatives handed from stream C to stream P and never placed, 3 study files of `m152`, one 2dseq-only reconstruction) + 126 drive files of the 10 DICOM-less placeholder exams (Ryan's retire ruling: kept in their projects). **The 259-row copy-only handover runs 2026-10-08 evening** (121 placed, 72 held, 66 duplicate copies). Then the re-run must say `READY TO DELETE`, the evidence copy (3,255 files, 3.44 GB), the deletion (Ryan's go; ParaVision originals of the 963 exams the archive lacks, 75.4 GB, go with it under the DICOM-only rule unless Ryan says otherwise; the share's recycle bin and snapshots keep the space until they clear). SegBioMed warned and remapped (memo REPLY 10).
  - **✅ Final system check after the three drives, 2026-10-08 (coordinator, read-only): clean.** `validate_registries.py`: **0 errors** (36,657 WARNs, all the known kinds: `is_control` / `is_whole_body` unknown, 292 subjects `pending-db` from before August, 284 sidecars without a subject/condition block). Registry 35,613 rows, unique ACQ-IDs, the ACQ-ID counter never behind; **no SHA-256 in more than one acquisition** (647,057 `/raw/` files). Counts per batch = the gates (drive 3: MRI 3,309, CNIC 27, CELL 4,955, PET/CT 202; drives 1+2: CELL 8,061 − 153 retired derivatives = 7,908 + 15 nested, LSM9 387, ZWSI 4, XMIC 338). **Links** (`repair_link_collisions.py audit`): of 27,620 acquisitions with a project, 26,902 OK, 0 missing / polluted / partial, 392 `0220` (closed), 2 researcher-pruned, 324 the known DICOM-less MRI placeholders (BACKLOG "existing MRI rows that fall outside the 2026-10-04 line", Ryan's decision). **Placement trees and holding** = their indexes (76,220 + 59,481 files, 0 missing, 0 size mismatch; the only unindexed files are the 77 `README_not_registered.txt` notes). MRI archive ingest: its branch merges onto `main` without conflict; no stale locks; the workbooks untouched since 2026-10-07.
  - **Answers from Irene (2026-10-08)** to the drive-3 questions (recorded in `drive3_questions_for_mjesus.md`): the `0522`/`0619`/`0424` masks were revised and **the revised set is in a shared OneDrive folder** (the drive holds drafts); `0522` 2023 `IRE` = the correction; the second Axioscan is **Biodonostia's** (MFB samples scanned as a favour); the Leica SP8 is **biomaGUNE's own** former microscope. The two instruments' data are decided after `biomaGUNE MJ`.
  - **✅ `biomaGUNE MJ` (the drive's last part) placed, 2026-10-08** (Ryan's go; gate re-checked live first: hashes identical, 21 invariants hold). W1 1,617 / W2 2,238 / W3 128 files copied, every window `VERIFY PASS` (0 missing / extra / mismatched, every earlier index, provenance and holding-manifest row kept, `registries\` unchanged); `0619`'s README now carries the drafts note. Run log: `D:\projects\gjesus3\drive3_streams\bmj\runs\`. **Every file of the drive now has a decision.** **Ryan, 2026-10-08:** the 4 possibly personal files are ignored (batch 1's 3 copies stay); the outside-instrument raw is decided now on what we know (Biodonostia's Axioscan → `XMIC`, as the Charité precedent; the Leica `.lif` → its project as material; `feat/drive3-foreign-raw`), changed by hand if answers come (BACKLOG); **the close-out has his go** (`feat/drive3-closeout`: the reconciliation that must say `READY TO DELETE` before the staged copy goes). Plan: `tasks/drive3_biomagune_mj_gate.md`: each of the 26,410 deferred rows decided once: **3,855 files placed into `0424` 849, `0522` 580, `1019` 188, `1123` 1,915, `1422` 323, and 128 into holding (13.30 GB)**; 19,897 already placed, 2,443 covered by a twin, 62 already in holding, 20 duplicate copies, 0 in `/raw/`. Readings TWO / R5 / R3b / C5 confirmed by the coordinator (each within A2's or stream P's precedents); 21 invariants and an independent coordinator check pass. **4 possibly personal files** (by name; not opened) are neither placed nor held; 3 of them already have identical copies placed by batch 1 in `0619` (2) and `0522` (1): Ryan to judge (removing those copies is a production delete). The `0522`/`0619`/`0424` trees' README says the masks are pre-revision drafts.
  - **✅ Stream C (Cell Observer) complete, 2026-10-07** (merge `4d5eae6`): C02–C05 run by the coordinator on Ryan's direct go, after C01; 4,955 `.czi` in all, every batch's gated checks and the coordinator's manifest check PASS. C03 first stopped at a pre-check: check 3d did not recognise siblings C02 had just ingested; verified, fixed with a test, 11 exemptions (exactly those).
  - **✅ The `pending-claim` hold on historical MRI, 2026-10-07** (Ryan's ruling, §0.5 "Hold"): 5,649 rows (drives 1+2 MRI 1,393, the 2021 `1019` recovery 854 + G1 24, the July phantoms 69, drive 3 3,309), MRI only; verified against the backup (only `operator`, blank → `pending-claim`); validator clean; **15,963** rows now await a claim.
  - **✅ The two workbooks, 2026-10-07:** the assign workbook's 254 cells with a wrong holding path (`\\GJESUS3\gjesus3\staging\…`, missing `gjesus3-data`) corrected; then both appended (`tools/claim_workbooks.py`, every existing cell verified unchanged): the claim list +362 sessions / 5,649 acquisitions, the assign list +79 groups / 1,515 acquisitions with no project. **Ready for the email to Jesús's group.** The archive's sessions are appended after its ingest.
  - **The MRI archive pull** (§0.6) started 2026-10-07 18:01: one connection, every archive SHA-1-checked, local only; 3.6 MB/s, so about two nights for the 219 GB.
  - **✅ Stream M written and verified, 2026-10-07** (merge `4f4c72f`; run by the coordinator on Ryan's go). **Part 1:** 3,309 MRI exams (189 studies, M01–M09) into six existing projects; 18/18 checks, 90,080 DICOM re-hashed; validator clean. **Part 2:** `CNIC-HEARDS` = PROJ-0066 with 27 pig series as `XMRI` (`collaborator:CNIC`); 14/14. **P2 (copies):** 2,393 / 440 / 86 MRI files into `0118` / `0619` / `1019`, 56 to holding, and 31 loose files plus 1,791 masks into `CNIC-HEARDS`, every window verified. A tool bug found on the way: `copy --from-holding` recomputed holding paths instead of reading the holding manifest, so it would have found none of the files, here and in drives 1+2's 2b route; fixed with tests. `tasks/drive3_mri_for_archive_check.csv` lists every exam for the later check against the platform's originals.
  - *(Was:)* **Stream M: gated by the coordinator 2026-10-06** (3,309 MRI exams in M01–M09 into six existing projects; the CNIC pigs as 27 `XMRI` rows in a new `CNIC-HEARDS`; my check: 0 of the planned exams or studies in live production). **✅ Ryan's go, 2026-10-07: "run M and C02–C05"**, run by the coordinator from its own session in the order M §7 Part 1, Part 2, P2's copies, then C02–C05 (one registry writer at a time).
  - **At close-out:** every ingested file is checked against the drive manifest, and the evidence is copied to `J:\gjesus3-data\staging\historical_drives_records\`. Then the staged copy is deleted, on Ryan's go.
- **Historical microscopy on external drives: ✅ `.czi` INGEST DONE IN TRUE PRODUCTION, verified and merged (2026-10-02, `0f052d5`).**
  - **8,790 acquisitions, 3.85 TB:** `CELL` 8,061, `LSM9` 387, `ZWSI` 4, `XMIC` 338. The registry went 16,437 → **25,227**.
  - **Projects:** one created (`AE-biomaGUNE-0118` = PROJ-0060); `0219` and `1019` reopened. **5,055 acquisitions have a blank project:** Ryan's list, `tasks/drives_blank_project_list.csv`.
  - **The coordinator's verification:**
    - no new duplicate content (only the known 32) and no new re-save (only the known 23 groups);
    - all 8,791 provenance rows match production's `checksums.json`, and a sample of 50 matches the drive manifests;
    - the repaired `ACQ-20251031-CELL-003` and its project link re-hash to the drive copy;
    - the validator is at the known 10,314 errors, with no new class.
  - **✅ The first retirements are done in production (2026-10-02, close-out Step 3).** The 32 duplicate registrations are retired with `tools/retire_acquisition.py`: the 22 `ZWSI` twins (`ACQ-20260304-ZWSI-023…044`), then the 10 `CELL` copies of `ZWSI` scans (`ACQ-20260507-CELL-001…010`). That also fixes 10 of the 25 mis-coded rows. Claudia's 10 links were re-pointed at the surviving `ZWSI` acquisitions under the same names. Each full dry run showed every pair byte-identical. Independently verified: 32 tombstones, the rows and folders gone, the survivors and links intact, and the registry format unchanged. The registry is now **25,195** rows.
  - **2026-10-04, Ryan's decisions and the day's writes:** see the close-out plan's "Decisions of 2026-10-04".
    - **Written and verified:** +578 drives MRI/PET-CT rows; 4 paperwork projects (`PROJ-0062`…`0065`); `1519` and `0320` reopened; retire v2 merged.
    - **Approved and queued:** the non-raw copies (short-path layout with an index), the holding folder, `LEONE`'s new content into `DTS24`'s folder, D's 153 retirements, and the dot-file plus 14 nested `.czi`.
  - **✅ Project link collisions fixed and repaired (2026-10-05).**
    - The linker refuses a taken name, and MRI link names carry the study time.
    - 589 missing links were created and 7 polluted folders cleaned; the final audit shows 0 missing and 0 polluted.
    - The operator GUI exe has been rebuilt with the fix and redeployed (2026-10-05, hash-verified, the old exe backed up).
    - Record: `tasks/link_collision_fix_review.md`.
  - **✅ The same-timestamp clean-up (gate rule R4, stream D) is done: all 4 approved lists, 153 acquisitions (2026-10-04/05).** The last list, `roi_crops` (81, 184 GB), ran on 2026-10-05 on Ryan's instruction. Its run is `RET-20261005-104956-623`; every check passed, and all 81 files hash identical to the drive copies. *(History of the line below:)*
  - **🔶 The same-timestamp clean-up (gate rule R4, stream D): 3 of the 4 approved lists are done (2026-10-04).** Review: `tasks/drives_r4_cleanup_review.md`.
    - **The analysis:** of the 819 files in 247 groups, 469 are derivatives (251.8 GB) and 350 stay in `/raw/`. `ID65_PB_lung_20x_scale.czi` also stays: it is the only record of its acquisition.
    - **Done:** scale bars 3, re-saves 9 and exports 60 were retired as derivatives into their originals' projects, using stream A's short-path layout, with each project's `_INDEX.csv` merged.
      - All 114 checks passed and the validator is unchanged.
      - The coordinator verified them independently.
      - 27 of the 90 `raw_linked` links are gone.
    - **⚠️ On hold:** `roi_crops` (81 acquisitions, 184 GB). The permission system refused its `--execute`. Ryan's go stands; he allows it, or runs the six steps in review §14c.
    - **Waiting, with no list:** 61 derivatives whose original has no project (item 2b), and 255 scene splits, stitched copies and one rendering (proposal (c), 39.4 GB).
  - **✅ The drives' non-raw material is done (stream A, 2026-10-03/04).** Record: `tasks/drives_nonraw_placement_review.md`; the runbook for the mapping round is `tasks/drives_nonraw_2b_2c_followup.md`.
    - **Placed:** 27,547 files (237.73 GB) in 17 projects, under `<project>\working\historical_drives\<FRIO-X6|MFB-Disco-2>\<study folder>\…`. Every path is at most 240 characters (the rule in `tools/drive_staging/historical_paths.py`), and each tree has `_INDEX.csv`, `README.txt`, `_ORIGIN.txt` and `_PATHMAP.csv`.
    - **Created:** `AE-biomaGUNE-1116`, `-1420`, `-1520` and `Project-0521` (`PROJ-0062`…`0065`).
    - **Holding:** 54,721 unassigned files (218.89 GB) in `staging\historical_drives_unassigned\`, with `README.txt` and `manifest.csv`.
    - **Raw one-offs:** the dot-file `.czi` is `ACQ-20240125-CELL-050`, and the 14 nested `.czi` are `ACQ-20230503-CELL-001`…`014` (blank project).
    - **Verified:** every file was re-hashed at copy time, and the coordinator re-verified every step independently.
    - **Waiting on Ryan:** the 2b mapping worksheet (`tasks/drives_nonraw_mapping_worksheet.csv`; the 62 `A` rows cover nearly everything), and whether the holding folder should be read-only for the group.
  - **✅ The drives' DICOM stream is done in true production (stream B, 2026-10-02/04): +1,764 acquisitions.** Record: `tasks/drives_dicom_review.md`.
    - **By project:** `0619` 2020 +234 (`PROJ-0004`); `0420` 2021 +338 (`PROJ-0012`); `1519` 2020 and 2022 +661 (`PROJ-0008`, reopened); `1319` PET/CT +8 (`PROJ-0061`, created).
    - **With no project:** phantoms and collaborations 2022–23 (+123); the Madrid ICON exams of 2024 (+363, as `XMRI`, `collaborator:Uni-Madrid`); and the 2021 `1019` MRS-session image exams (+37, D6).
    - **Already in production before, so left untouched:** 605 MRI exams and 177 NI reconstructions on the drives.
    - **Ryan's rule (2026-10-04):** an MRI exam is registered only with DICOM, or with DICOM produced before ingest. The 24 exams with no reconstructed image are kept as other data with a README, in the holding area or in `1519`.
  - **✅ The July protocol-1125 series is in production, ingested from the scanner (2026-10-04, stream F).**
    - 9 sessions (m2, m3, m4–m8 including m6, the first m12 study, m19): 141 acquisitions, all native DICOM, in `PROJ-0021`, operator `Irene`.
    - The five `jrc` phantom/QC studies: 69 acquisitions with a blank project (`phantom` ×64, `material` ×5).
    - Verified end to end, by the stream and independently by the coordinator.
    - The protocol-1025 sessions of 10-01/02 stay with the operators.
    - The first m12 study needed its own link names: see the BACKLOG 🔺 item on link collisions.
  - **✅ `LEONE` done (2026-10-04, stream C).** `LEONE.zip` was compared with `DTS24` member by member: 553,241 of its 560,402 DICOM instances are already in `DTS24`, as a pixel-identical re-export of the LIONS cohort.
    - Per Ryan, nothing duplicate is ingested, and there is no new project or registry row.
    - The new content is 36 echocardiography exams, 5,063 MR supplement instances and 72 derived objects: 7,161 files, 59.15 GB.
    - It is copied to `projects\DTS24\working\historical_drives\FRIO-X6\LEONE\{echo,mr_supplements,derived}\`, with an index that gives each file's original path and header case id.
    - Verified by the stream and checked independently by the coordinator. Record: `tasks/leone_ingest_review.md`.
  - **Six streams run over the weekend of 2026-10-03/04** (the close-out plan's weekend section; Ryan away, reachable by Remote Control): non-raw placement, the drives' DICOM, `LEONE`, the same-timestamp clean-up, retire v2, and the July MRI session.
  - **Still open:** the non-raw placement, the no-project mapping and holding folder, `LEONE`, the drives' DICOM stream, and the missing July MRI session. **All of it is in [`historical_drives_closeout_plan.md`](historical_drives_closeout_plan.md) (Steps 3–5); resume from there.** The record below is the history up to now.
  **✅ The staged data on D: is ERASED (2026-10-05).** The records are kept at `J:\gjesus3-data\staging\historical_drives_records\` (5.1 GB, SHA-256-verified), and the patient-identifier extracts were deleted. *(Was:)* **Staged data on D: (Ryan, 2026-10-02):** it is **erased once everything from these drives is in production and verified** against the drive manifests. It is a temporary working copy on Ryan's own drive, not a backup. The owners keep their external drives and the data on them, and the lab knows gjesus3 has no off-site backup yet (INFRA-06).
  *(Original heading, 2026-09-29:)* **🔶 STAGED + VERIFIED + ASSESSED, nothing ingested yet.** Both one-copy drives are on `D:\projects\gjesus3\staging\drive<N>_<label>_<id>\` (copied with [`tools/drive_staging/`](../tools/drive_staging/README.md)): **drive 1 `FRIO X6`** 43,121 files / 3,776 GB and **drive 2 `MFB Disco 2`** 35,718 files / 2,445 GB, both copied with 0 errors and `VERIFY PASS` on every checksum (drive 2's 11 unreadable entries are other users' `$RECYCLE.BIN`, no data). The drives are back with their owners, who were asked not to wipe them. **D: is not backed up**, so until ingest the staged copy plus the owners' SSDs are the only copies. The hub's brief, with Ryan's decisions of 2026-09-28/29 folded in, is `...\DataInfra\gjesus3-archive\historical-microscopy-drives\HANDOFF.md` (outside this repo).
  **Measured here 2026-09-29, and it changes that brief** (read-only, scripts not kept):
  - **The microscope's stand name does not identify the instrument.** All 805 production `LSM9` acquisitions read `Axio Observer.Z1 / 7`, the same as the Cell Observer, and about 60% of them are widefield camera images. **The device serial does identify it:** LSM 900 = `03761880` (stand keys include `LSM`, present even on its widefield images), AxioScan 7 = `4661000718`, Cell Observer = no device serial and stand key `Inverted` only. The brief's "80% Cell Observer" figure is a stand-name count, so it includes LSM 900 files (drive 1 holds a `Cell observer\AINHIZE\CONFOCAL LSM 900` tree).
  - **The "LSM 800" is our LSM 900.** The brief's one "LSM 800" file (`…\CONFOCAL LSM 900\ITZIAR_Lipofectamine mCherry\24h\CS_2.czi`) carries serial `03761880`. ZEN writes `LSM 800` in its `System` field on some LSM 900 files, and 112 files from that same folder are already in production as `LSM9`.
  - **The Axio Imager.Z2 is one microscope, serial `784053`: 338 `.czi`, all under `…\Proyectos_Laboratorio_Laura\Ferritas\Charité\`, acquired 2024-09-27 to 11-07** (corrected 2026-09-30 from every file's own date: `Test-1` in September, `4.10.24-test-1-FeMn` in October, `Fibronectin` in November; the earlier "to 10-11" came from a sample). The same project's local histology (`Ferritas\BiomaGUNE\`) is on the Cell Observer. This looks like a microscope at Charité (Berlin), i.e. external data, not a local instrument. Ryan's 2026-09-29 "onboard both" decision was made on the stand-name sample, so both halves go back to him.
  - **About 1,470 of the 11,294 `.czi` copies (~380 GB) are already in production** (AxioScan via `axioscan7_mfb_20260614.yaml` and the `mbc`/`aua` recipes, plus the 2026-06-15 K: best-guess Cell Observer / LSM 900 ingests). So roughly 4 TB is new. **Dedup has to be by checksum:** production already holds 32 `.czi` registered twice, which is exactly the name-based dedup gap (see [`BACKLOG.md`](BACKLOG.md) "Dedup identity").
  - **Decided by Ryan the same day** (see [`../CHANGELOG.md`](../CHANGELOG.md) 2026-09-29):
    - **LSM 800:** the onboarding is void unless the full scan finds another LSM serial.
    - **Axio Imager.Z2:** enters as **external data with its own `X`-code** (like `XMRI`). Ryan confirmed it was Charité's microscope. The code's name is still open (`XMIC` suggested), to settle before the ingest session.
    - **`Project-NNNN` naming** (code as written) confirmed by Ryan; the resemblance to `PROJ-NNNN` machine ids is accepted.
    - **Project claims are classified before ingest:** confirmed in the animal DB; **(A)** a typo with a corroborated DB match, corrected and ingested as normal; **(B)** clearly not an animal protocol, ingested with no animal-DB link into a new project `Project-NNNN`; **(C)** uncertain, ingested with a blank project and listed with the project each file claimed.
    - **Non-raw material** clearly tied to a defined project is copied into that project's folder.
  - **✅ Pre-ingest analysis done and merged (2026-09-29).** Both read-only sessions landed, were reviewed by the coordinator (numbers re-derived, every proposed protocol code re-validated against a fresh DB query), and were merged to `main`. Findings: [`drives_catalog_findings.md`](drives_catalog_findings.md) and [`drives_project_codes_findings.md`](drives_project_codes_findings.md). Tools: `tools/drive_staging/catalog.py` and `project_claims.py`. Outputs (regenerable) are on `D:\projects\gjesus3\staging\_analysis\`.
    - **New to gjesus3 ≈ 4 TB of `.czi`:** Cell Observer 3,932 GB, AxioScan 35 GB, LSM 900 5 GB, external Axio Imager.Z2 4 GB. **No second LSM exists**, so the LSM 800 onboarding stays void.
    - **Claims:** 19,019 files Confirmed against 20 existing projects; 147 files in (A) (`118 LUCIA` → `0118`); 180 files in (C); 59,490 files (1.9 TB) with no claim. The only (B) is `Project-0521`, 26 documents. **No fabricated code.**
    - **Two more mis-coded production rows** (`ACQ-20240625-LSM9-001/-002` are Cell Observer files), which makes 25 in total; see BACKLOG "Dedup identity".
    - **The drives also carry a lot of MRI and PET/CT** (Laura's backup, `Cardiac MRI.zip`, Haizpea's `project0420`, Peio's `1319`). Pre-2022 MRI there exists nowhere else. That is a separate DICOM stream, after the microscopy.
  - **Approved by Ryan the same day** (see [`../CHANGELOG.md`](../CHANGELOG.md)):
    - `AINHIZE`/`Marta` top folders give the operator, not the researcher.
    - `118 LUCIA` → `0118` is approved, with its animal links held until Lucia confirms.
    - Six new projects: `AE-biomaGUNE-0118`, `-1319`, `-1116`, `-1420`, `-1520` and `Project-0521`.
    - DB-date readings are applied to the clear shared-animal cases.
    - The Charité code is `XMIC`.
  - **✅ Dry run passed the coordinator's gate (2026-09-30), with required changes before production.** The build is on `feat/drives-microscopy-ingest`: 9,090 `.czi` / 4.0 TB in 16 batches, an engine resolution matching the plan on every file, and an idempotent scratch rehearsal. Review: `tasks/drives_ingest_dryrun_review.md` on the branch. The gate re-derived the invariants and ran all 28 test suites (green). It also found what SHA-256 dedup misses:
    - **206 planned files are re-saved copies of production acquisitions** (same instrument, acquisition time and name, and for 202 of them the same size; different bytes), which would have become duplicate registrations;
    - **84 re-save groups within the plan**;
    - **the 18 AxioScan "ROI lobulo" files are crops of production scans** `ACQ-20260416-ZWSI-001…-020`, sharing their acquisition times to the second.

    Required fixes: drop the re-saves, collapse the in-plan groups, route the crops to project `1123` as non-raw material, and flag the remaining same-timestamp groups (ZEN scene splits and stitching). All are in the worktree's `GATE_2026-09-30.md`.
  - **Closed projects (G1):** `AE-biomaGUNE-0219` and `-1019` are to be **reopened** (Ryan), with a reusable `tools/reopen_project.py` built on the ingest branch. Status goes back to active, the dates are recomputed, and hard links are recreated for every production acquisition. Their folders were never actually gone: 6 of the 8 closed projects still have folders, and **an operator ingested 18 new AxioScan sections into `1019` on 2026-09-29**, because the ingest ignores `closed`.
  - **🔶 IN PRODUCTION, PART-WAY (2026-09-30 / 10-01).** The gate changes are done: the 205 re-saves of production were dropped, 65 in-plan re-save groups collapsed, and 22 crops and scale-bar copies routed to non-raw. The plan is now **8,790 files, 3.85 TB**, frozen at `c5f7fff`.
    - `0219` and `1019` were **reopened** with `tools/reopen_project.py`: 80 and 421 links recreated, no file lost, a re-run was a no-op.
    - **B01–B04 are in production and verified: 869 acquisitions** (`XMIC` 338; `AE-biomaGUNE-0118` created as **PROJ-0060** with 140; `LSM9` 387; `ZWSI` 4). The registry is **17,306 rows**, and the validator is unchanged (the 10,314 known placeholders).
    - **Next: B05–B16** (7,921 `CELL` files, ~3.8 TB, ~30–35 h at 31–39 MB/s), run by a Sonnet session from the worktree's `HANDOFF_RUN.md`. No ingest window is needed: no operator has ever ingested `CELL` or `LSM9` data.
    - **Progress 2026-10-01:** B05–B07 are in production and verified (+3,777, so the registry is 21,083 rows). **B08 stopped at its pre-check, having written nothing.** Check 3c flagged 7 files whose planned same-timestamp siblings B05 had just ingested. This is a batch-order false positive: 58 of the plan's 247 timestamp groups span batches. The answer (`ANSWER_B08_STOP.md` in the worktree) is a reviewed edit to the check, not to the plan: a planned sibling from an earlier batch of this run is expected, and anything else still stops the run. Then the run continues.
    - **A truncated production primary was found:** `ACQ-20251031-CELL-003` (the drive copy is complete). Its repair was approved on 2026-10-01, in place, so that project hard links keep pointing at it. See BACKLOG "audit production `.czi` for truncated primaries".
  - **Retire tool: ✅ merged to `main` 2026-10-02 (`361387f`); in production use since the same day** (the 32 twins and the 17 orphans, below). *(Below: as approved on 2026-10-01; the subject change is made.)* `tools/retire_acquisition.py` (`feat/retire-acquisition`) handles duplicates, derivatives and orphan folders. It writes the tombstone file `registries/retired_acquisitions.csv`, takes a backup first, refuses during an ingest, and is crash-resumable. It has been rehearsed on copies of real data. **One change before the coordinator merges it:** it must never delete a subject row (the ✅ 06 §2.8.3 rule stands).
    - **Approved first uses: ✅ all done 2026-10-02.** The 22 duplicate AxioScan pairs and the 10 `CELL` copies of AxioScan files (see the Step 3 bullet above); then the 17 empty orphan folders, after their session was re-ingested (next point).
    - **✅ The missing 2026-07-10 MRI session is in production (2026-10-02).** `jrc20260710_m12_1125_bis` (animal 12 of protocol 1125, 17 exams) was re-ingested **from the scanner's current copy** as `ACQ-20260710-MRI-018…034` (recons `1,3`, 393 native Bruker DICOMs, project `AE-biomaGUNE-1125`, `researcher` = `operator` = `Irene`). The NAS staging pull of 2026-07-16 is **a week older** than the researcher's finished session (her `/3` reconstruction and DICOM export date from 2026-07-23), so it was not used. **The 17 empty orphan folders `-001…-017` were then retired the same day:** 17 tombstones with disposition `orphan`; the ids stay reserved, and the folders are backed up whole off-NAS. Both writes were verified independently by the coordinator. Record: [`mri_0710_reingest_review.md`](mri_0710_reingest_review.md).
    - **A read-only scanner-vs-registry reconciliation (2026-10-02) found more unregistered MFB sessions.** Of 419 study folders on the scanner dated 2026-06-01 or later, 34 are registered. For MFB (`jrc`, the only group in the registry) **19 are not: 14 animal sessions (232 exams) and 5 phantom/QC studies (70 exams).**
      - **The animal sessions:** protocol 1125, 9 sessions (m2 and m3 on 07-03; m4–m8 on 07-06, **including m6**; the first m12 study and m19 on 07-10); protocol 1025, 5 sessions (m25–m29, 2026-10-01/02).
      - Since the 2026-06-13/14 bulk load, only m1 and the m12 `_bis` session were ingested. The data is safe on the scanner.
      - **Ryan decides** how they are ingested and who the operator is. m6's operator is not established; the best-supported answer is `Irene`. See BACKLOG "14 MFB animal sessions on the scanner".
      - Other groups' studies on the shared scanner (362 studies, from `jl`, `pr`, `sp`, `dan`, `fer` and `aka`) are out of MFB scope.
  - **Later, separate sessions will handle:**
    - placing the non-raw material into project folders, including the four paperwork-only projects;
    - the DICOM stream (MRI and PET/CT on the drives);
    - `.tif`/`.lsm`;
    - the 25 mis-coded production rows.
- **SegBioMed segmentation harvest + the 2021 MRI recovery — ✅ DONE IN PRODUCTION 2026-08-21.** A long exchange with the SegBioMed project (full thread: `projects\Imaging\SegBioMed\harvest\MEMO_for_gjesus3_agent.md`, six replies each way) that turned into four production changes. **Everything below is finished and verified; what remains are the decisions in §0.**
  - **854 acquisitions recovered from 2021** (`Proyecto 1019`, `K:\gjesus\MRI`) — registry 15,474 → 16,328, 0 duplicates, 0 blank acquisition timestamps, `subject_ids` 854/854 from the facility DB, `checksum_present` Y on all, and the 9 DICOM-less exams regenerated to completion. **Ingested with NO project, deliberately** — the first end-to-end exercise of that path. **Cause of the gap, established not guessed:** the 2026-06 bulk pull read the *scanner host* (`kenia`) with no cutoff, and its earliest acquisition anywhere is 2022-01-10 — that floor is the **scanner's own retention horizon**. Consequence: **any internal MRI older than ~2022-01 survives only on researcher shares**, unsurveyed.
  - **`curated_datasets/` deployed** (§10 steps 1–3; `CDS-01` decided → include, as a pilot): `README_START_HERE.txt`, `segmentation/{MICROSCOPY,DICOM}/`, and `registry_datasets.csv` initialised with its 14-column header. **`CDS-02` answered** — curator set is the Data Management Lead plus delegated agents; no backup; one approval gate.
  - **Four datasets promoted by SegBioMed and independently verified here** — `DS-SEG-0001` (8 cardiac cine stacks), `DS-SEG-0002` (144 PMOD VOI sets), `DS-SEG-0003` (28 stacks), `DS-SEG-0004` (10 inter-observer stacks). All 14 registry columns match `06_REGISTRIES §5.2`; **provenance traceability is 100% on all four** (821/821, 89/89, 308/308, 111/111 ACQ-IDs resolve). The pilot also returned **19 spec gaps** — see §0 D4.
  - **G1 — one session recovered that the pull had dropped silently** (`jrc250526_145_0522`, 24 acqs, registry → **16,352**). Its folder token omits the `m`, so it matched neither ingest regex and was skipped with no error and no worklist row. **That silent-skip class is §0 D3 and is the most important thing to come out of this work.**
  - **A trap worth knowing before any similar ingest:** `staging_dir` sets `original_name`, which is *half the dedup key*. Pointed at a tree root instead of the level the existing rows used, 149 already-ingested exams re-entered as duplicate ACQ-IDs (caught in dry run: 0 skips vs 149). Always dry-run a batch you know is already ingested — it is the cheapest possible dedup test. The six `mri_1019_kgjesus_2021_*.yaml` configs carry the reasoning inline.
  - **`11_OPERATIONS §5.5` corrected from actually running it:** `conda activate dicomifier-pilot` **fails silently** in a non-interactive WSL shell, after which the backfill logs a soft SKIP — a run that regenerated nothing looks like a success. Needs `source ~/miniforge3/etc/profile.d/conda.sh` first. Also: when sources are already reachable (`K:` = `/mnt/k`), build the expected layout from **symlinks and copy nothing**; and step 5 (relink) does not apply to project-less acquisitions.

- **MRI `instrument_model` template placeholder — ✅ REPAIRED IN PRODUCTION 2026-08-20; root cause fixed and **merged to `main` 2026-08-20 (`18c788b`, pushed)**.** 10,314 of 10,330 MRI acquisitions carried the literal unsubstituted `Bruker BioSpec <7T|11.7T>` in `registry_raw.instrument_model` — the five bulk historical configs (`tools/configs/mri_jrc_*.yaml`) hardcoded it behind an `# EDIT:` comment nobody ever actioned, while the operator template had already moved to auto-deriving the field for ingests since 2026-07. **Fully recoverable:** every affected sidecar's `mri._raw_metadata.acqp.ACQ_station` reads `"Biospec 70/30"` (0 exceptions, 0 missing) → `Bruker BioSpec 7T` per `paravision_metadata.py::_scanner_model`; no 11.7T anywhere in the set. Repaired at the byte level in `registry_raw.csv` (10,314 occurrences of `,Bruker BioSpec <7T|11.7T>,` → `,Bruker BioSpec 7T,`, size 8,182,709 → 8,100,197 bytes, BOM-free pure-CRLF preserved) and verified row-by-row against a pre-edit backup: exactly 10,314 rows changed, every one differing in `instrument_model` only. `instrument_model` is now `Bruker BioSpec 7T` × 10,330 for MRI, every non-MRI value unchanged. `validate_registries --no-enrichment`: **0 errors, 0 warnings**, same as baseline. **Root-cause fix (merged):** all five configs plus the `mri_bruker.yaml` template's own stale header bullet now read/describe `instrument_model: "${discovered.mri_scanner_model}"`; `validate_registries.py` gained a new ERROR-level, column-agnostic check for unsubstituted template residue (`${...}` / `{{...}}` / `<...>`), closing the detection gap. **That check also (correctly) flags a second, separate, NOT-fixed defect** — the same 10,314 rows carry `<REQUIRED - set via mri-ingest --operator, or replace here>` in the `operator` column, left alone pending a Data Office decision. Narrative in [`../CHANGELOG.md`](../CHANGELOG.md) 2026-08-20.

- **`-AE-biomaGUNE-None` subject identifiers — ✅ DONE IN PRODUCTION 2026-08-16.** Four
  animal protocols have a NULL alias in the facility DB, so 444 acquisitions carried an
  **ambiguous** subject id that merged two different animals into one subjects row. Source
  fixed (`animal_db` refuses to compose one), detector shipped (`validate_registries`
  ERRORs on one), and the 444 sidecars + registry rows repaired; `registry_subjects.csv`
  1,146 → **1,124**. `validate_registries --no-enrichment` reports **0 errors, 0 warnings**
  across all 15,474 rows. The full run (which adds the Phase 3 sidecar checks) is
  also **0 errors**, with 18,744 warnings that are all pre-existing `unknown
  sentinel` classes and none of them from this repair — `condition.is_control`
  (12,925), `anatomy.is_whole_body` (5,242), `pending-db` subjects (292), missing
  `subject:` / `condition:` blocks (146 / 138). Re-measured 2026-08-19. Narrative in [`../CHANGELOG.md`](../CHANGELOG.md) 2026-08-16.
  **Still open (does not block):** ask the animal facility to populate the aliases for
  `0219` / `0618` / `0619` / `1521` — the code no longer depends on it. Also raised:
  `ingest/metadata_sidecar.py` writes platform-dependent line endings
  ([`BACKLOG.md`](BACKLOG.md)).

- **PROJ-0056 `rN` subject identifiers — ✅ DONE IN PRODUCTION 2026-08-19.** 15 acquisitions
  from the 2023-10-26/27 rat sessions were attributed to **three uninvolved rats**: the
  researcher's tree is `<protocol>/<yymmdd>/<animal_code>/r<N>/` where `rN` is a
  *reconstruction*, and the recipe read that level as the subject (`r1` → animal `1` →
  `1-AE-biomaGUNE-0421`). **Unlike the `-None` defect above, these ids were well formed and
  they resolved** — animals 1/2/3 of `0421` are real rats born two years earlier — so the
  sidecars carried the wrong `date_of_birth`, `procedures` and an age of ~120 weeks for a
  4-month cohort. **Found by the XNAT image-server trial**, not by our own checks. Corrected
  attribution rests on three independent sources agreeing (researcher folder, facility-DB
  procedure dates, DICOM `PatientID`); repaired with `tools/recover_subject_ids_proj0056.py`
  after an end-to-end scratch rehearsal. `registry_subjects.csv` **unchanged at 1,124** (3 `rN`
  rows dropped, 3 real animals added). Narrative in [`../CHANGELOG.md`](../CHANGELOG.md)
  2026-08-19. `validate_registries` re-run against production afterwards: **0 errors**
  across all 15,474 rows, warnings unchanged in kind and count from before the repair.
  **Still open (does not block):** the root cause — subject-id derivation trusts
  any leading integer with no plausibility gate (HIGH) — plus plausibility checks for
  `validate_registries`, **4 PET acquisitions whose DICOM `PatientID` names the adjacent
  animal** (genuinely unresolvable from the data; needs a researcher who was there), and 5
  acquisitions dated before their subject's date of birth. All four in
  [`BACKLOG.md`](BACKLOG.md).

- **DTS24 collaborator re-ingest — ✅ DONE IN PRODUCTION 2026-08-13; merged to
  `main` (`def282c`, `--no-ff`), branch + worktree retired.** **The data went live
  independently of the branch: the branch held the code/config/doc changes, not the
  acquisitions.**
  - **75 acquisitions in `PROJ-0054` / `DTS24`** (LIONS 42 + HPIC 33), the external
    cardiac-MRI cohorts that the 2026-06-10 purge removed. Verified after the run:
    75 unique ACQ-IDs, every source archive accounted for, 75 sidecars, 75 hard
    links, `sample_organism: Homo sapiens` ×75, `anatomical_entity: heart` ×75,
    checksums `Y` ×75, acquisition dates spanning 2018–2025, **0 sidecars carrying a
    date of birth**, 75/75 carrying a derived age.
  - Two capabilities shipped for it, both default-off so nothing else changed: the
    `user_provided_metadata` sidecar block
    ([`08_METADATA §4.9`](../mfb-rdm-docs/08_METADATA.md) ·
    [`10_TOOLS §2.1.7`](../mfb-rdm-docs/10_TOOLS.md)) and opt-in curated DICOM-header
    extraction ([`§4.10`](../mfb-rdm-docs/08_METADATA.md) ·
    [`§2.1.8`](../mfb-rdm-docs/10_TOOLS.md)).
  - ⚠️ **First human clinical data in the system.** The ingest-side privacy line is
    decided and held in production ([`§4.10`](../mfb-rdm-docs/08_METADATA.md)); the
    wider policy — de-identifying the archived sources, access control for human
    data, retention, legal basis — is **open** as backlog **META-12**. Also open:
    **META-10** (ISA study level) and **META-11** (a clinical measurement is its own
    data type, not metadata — the attached hemodynamics table is a stand-in).
  - `condition.is_control` is `null` on all 75 **by decision**, not by omission:
    neither cohort has a healthy-control arm. `disease_state` / `disease_model` are
    quoted from each collaborator's own study title. Pulmonary-hypertension status
    is deliberately **not** recorded — it is derivable from the attached
    hemodynamics, but the count swings 12 vs 4 of 38 between the 2022 and 2015
    ESC/ERS thresholds, so it stays as data rather than a frozen label.
  - **A silent-date bug was found and fixed mid-run** — see backlog, and
    [`../CHANGELOG.md`](../CHANGELOG.md) 2026-08-13. Two HPIC acquisitions were
    committed with *today's* date and had to be deleted and re-ingested. **17
    pre-existing orphan `ACQ-20260710-MRI-0xx` folders** under
    `raw/DICOM/2026/2026-07/` (on disk, absent from the registry) were noticed
    during that cleanup — unrelated to DTS24, left untouched, worth a look.

- **One project per acquisition + the project-folder ownership boundary — ✅ DONE +
  DEPLOYED (2026-08-12). Merged to `main` (`be932b9`, `--no-ff`); branch + worktree
  retired.** Reverses the one-day-old semicolon-list decision and, more importantly, writes
  down the boundary that reversal exposed.
  **(1) `registry_raw.project_id` is write-once** — one project, the one ingest established
  ([`06_REGISTRIES §2.3b`](../mfb-rdm-docs/06_REGISTRIES.md)). Sharing an acquisition across
  projects still works: the link is made and the destination project's `provenance.csv`
  records it — it is just **not registered**. Searching the registry by project is rare and
  always means *where it was acquired*, which write-once preserves; against that the list
  cost eight readers that failed **silently** when they forgot to split. **The readers were
  kept** (a single value is a length-1 list) — only the writer changed, so nothing was
  reverted that didn't need to be. `add_project_id` survives, called by no tool, guarded by
  a `git grep` check in `test_project_ids.py` that fails if anything wires it back in.
  **(2) Project folders are researcher-owned** (new
  [`05_PROJECTS §3a`](../mfb-rdm-docs/05_PROJECTS.md), ✅ DECIDED): the system creates,
  populates, documents and teaches, but **mandates nothing** — researchers may delete
  anything in their project folder, hard links included. **So no system-of-record fact may
  be derived from a project folder's contents.** Written down because it had already been
  violated in scoping: a proposed validator check treated a missing link as an integrity
  error, which would have read 1,939 associations-without-provenance as defects. They are
  not. (Measured: of 11,053 links the system created, **35 — 0.3% — have since been
  deleted**. Small, but permission is the argument, not the number.) §3a also warns off the
  bulk "repair" that nearly followed, which for one project would have dumped **635**
  unwanted links into a folder its owner had been pruning.
  Full suite green (20 files). Also backlogged: the **metadata database** that models
  project↔acquisition properly.
  **✅ REDEPLOYED 2026-08-12.** `gjesus3_manager.exe` rebuilt and pushed to the NAS —
  **13,004,103 bytes, sha256 `fb5d6f3b…`** (was `d060d566…`), plus the researcher-facing
  `tools\README.txt` (`cf05692d…`). Built off-OneDrive, staged as `.exe.new` and atomically
  renamed, checksum-verified at every hop. **Verified the frozen bundle actually carries the
  change** rather than trusting the build: a raw string search fails (PyInstaller compresses
  the archive), so the exe was *run* and its served `/static/manager.js` checked for the new
  modal wording, and the extracted bundle checked for `set_project_id_if_blank` /
  `_record_project_when_unassigned` with **no** surviving `add_project_id` call. Then
  smoke-tested **from the share**, read-only, against live data: 52 projects, 49 with
  folders, 3 without — matching reality. **`gjesus3_ingest.exe` provably untouched**
  (`cde997ba…`); exactly two files on the share changed. Pre-deploy backup + a full checksum
  manifest at `C:\Users\rtasseff\temp\gjesus3_manager_redeploy_20260812b\`; **rollback =
  restore those two files.** No registry was written (last registry write 15:17 predates the
  deploy — that was the ongoing data load, see below).
- **Project Manager GUI — ✅ DONE (2026-08-12): built, verified by hand, exe DEPLOYED to
  the NAS, subfolder backfill run live. Merged to `main` (`253ac0d`, `--no-ff`); branch +
  worktree retired.** A researcher-facing
  counterpart to the operator ingest tools, `tools/manager/gui/` on port 5001: list
  projects and edit `description` / `owner` / `status` / `notes`, create a project, and
  **add data to a project** — from `/raw/` (search with the Finder's filters, tick, →
  hard links + provenance through the existing linker, no parallel path) or from
  local/mounted storage (tick files → copy → provenance). Spec:
  [`../mfb-rdm-docs/10_TOOLS.md`](../mfb-rdm-docs/10_TOOLS.md) §5.3; narrative in
  [`../CHANGELOG.md`](../CHANGELOG.md) (2026-08-12). It **answers** the *"Select-in-Finder
  → assemble a project"* backlog item (marked done there) — a served page can do what a
  `file://` page can't. **The four Data Office calls of 2026-08-11 are all implemented:**
  **(1) `registry_raw.project_id` is now a semicolon list** (`PROJ-0001;PROJ-0007`) —
  owning section [`06_REGISTRIES §2.3b`](../mfb-rdm-docs/06_REGISTRIES.md), one definition
  in `ingest/project_ids.py`. **Eight** silently-failing reader sites were fixed, not the
  five originally listed (a sweep found `ingest_raw._touched_project_ids`,
  `relink_projects` and `metadata_completeness` too); `tools/test_project_ids.py` pins that
  an acquisition in two projects appears in **both** per-project indexes.
  **(2) The deferred-link queue was adopted, not rebuilt** (cherry-pick, see the row
  below), and its missing `registry_lock` + pid temp are now in place.
  **(3) Separate exe, maximum similarity** — shared `style.css`, `folder_browser.js`
  (extended with a *file* multi-select mode in the shared copy), completion modal, `/api/*`
  shape and SSE stream; `/api/listdir`'s body moved to a shared `tools/filebrowse.py`.
  **(4) Anyone with access may create a project — through the system**;
  [`RESEARCHER_GUIDE.md`](../RESEARCHER_GUIDE.md) §4 rewritten.
  Also landed: the **subfolder convention** `raw_linked/` · `working/` · `outputs/` ·
  `metadata/` (created on every new project; `tools/backfill_project_subfolders.py` for the
  existing ones — **run live, see below**), and a **locked/atomic writer for
  `registry_projects.csv`** (`ingest/projects_registry.py`; `create_project.py` now holds
  the lock across its whole read-decide-write).
  **✅ DEPLOYED 2026-08-12.** `gjesus3_manager.exe` (**13,113,252 bytes, sha256
  `d060d566…`**) is live at `\\GJESUS3\gjesus3\gjesus3-data\tools\` with a
  `Project Manager.lnk`, verified by hand by Ryan first. Built off-OneDrive
  (`D:\_build_mgr` / `D:\_dist_mgr`), staged as `.exe.new` and atomically renamed, then
  checksum-verified. **`gjesus3_ingest.exe` is provably untouched** (sha256 `cde997ba…`) —
  the point of a second exe. `tools\README.txt` now covers both apps (mirrored from
  `tools/operator/gui/nas_tools_README.txt`). Pre-deploy backup + a checksum manifest of
  the whole `tools\` folder at `C:\Users\rtasseff\temp\gjesus3_manager_deploy_20260812\`;
  **rollback = delete the two new files, restore `README.txt`.**
  **✅ Subfolder backfill run live:** **147 directories** created across all 49 project
  folders (49 × 3 — `raw_linked/` already existed everywhere); the 3 folderless closed rows
  skipped and listed, the 5 `_project.yaml`-less folders reported. Every registry CSV kept
  its previous mtime; a re-run reports `created: 0 · already complete: 49`.
  **⚠️ One production cleanup, done:** verifying the exe was done against the **live**
  system, which created `PROJ-0054` / `99_test` and imported 6 acquisitions into it (the
  first real two-project cells). Removed backup-first by byte-exact line editing
  (`C:\Users\rtasseff\temp\gjesus3_99test_removal_20260812\`): 0 occurrences of PROJ-0054
  anywhere, only the two intended files changed, 13,737 raw rows and 52 project rows, all 6
  acquisitions back to their original single project, **0 multi-project rows**, id retired
  not reused. Cause: the manager falls back to the ingest GUI's saved RDM-System root when
  it has none of its own, so its first launch on a configured machine points at production.
  **Deliberately left as-is** (Ryan's call) — the convenience is worth it; just point it at
  a scratch root when testing.
  **What is left:** **merge this branch to `main`** — it is not merged, and that is the
  only outstanding step. Deferred by decision to [`BACKLOG.md`](BACKLOG.md): project
  **rename** (low), **`status = closed`** semantics (medium), and **server-era identity**
  (owner-on-create + per-project edit rights).
- **Operator-GUI: reversible browse order + one obvious "read the folder" — ✅ DONE
  (2026-08-10); exe rebuilt + REDEPLOYED to the NAS + validated through the deployed
  exe. Merged to `main` (`a679e6a`, `--no-ff`) and pushed; branch + worktree deleted.**
  Two usability complaints from the microscopy operator, both in the shared GUI layer,
  so **both pages** are fixed. **(A)** The Browse… list has a clickable `Name ▲/▼`
  header — day folders are named by date, so `▼` is newest-first; folders stay above
  files, the choice is remembered, and the order is applied **in the backend before**
  the 3000-entry cap (a client-side reverse would show the wrong end of a big folder).
  It also **reopens in the folder that button was last left in** (per target, across
  restarts; a vanished folder falls back to home silently). The modal is now one
  shared `static/folder_browser.js` instead of two drifting copies.
  **(B)** Five differently-worded buttons (two with the *identical* label, both buried
  in collapsed `<details>`) became **two verbs — "Read folder" and "Preview"** — and
  **picking a folder reads it automatically**, filling both palettes, the filter
  dropdown and every live example from one call; Preview refreshes the same surfaces
  from its own response. Retires the latent bug where the always-visible Filter panel
  depended on loaders inside panels that can be hidden. **(C)** Saving a recipe over an
  existing one now works — it was a dead-end warning, though the backend has always
  supported `overwrite`; the confirm names the file, warns that RDM-System recipes are
  **shared**, and says the old version is **not kept** (no `.bak`, by decision).
  Verified headlessly against the live app + real AxioScan folders (**105 checks**) plus
  a **dry run of a real 17-file batch with the registry byte-identical afterwards**.
  Detail in [`../CHANGELOG.md`](../CHANGELOG.md) (2026-08-10). **Exe rebuilt +
  REDEPLOYED with all three, and validated through the deployed exe** (105 checks +
  the real dry run). **Rollback is one step:** the backup kept at
  `C:\Users\rtasseff\temp\gjesus3_exe_backup_20260810\` is deliberately the *pre-branch*
  2026-08-02 exe (`ca2bd1c7…`), not the intermediate build — restoring it undoes the
  whole branch, not just the last increment.
- **Project reference model — ✅ LANDED + MIGRATED IN PRODUCTION, exe redeployed (2026-08-02).**
  The last two items from the 2026-07-17 operator test. **"Project hint" is retired**: a
  project now has just `project_id` (`PROJ-XXXX`, machine key) and a **`name`** — what the
  operator types, and **its folder name verbatim** (no `proj-` prefix, casing preserved).
  The GUI field is **"Project name"**, the config key is `registry.project_name`, and
  `registry_raw`'s column is now honestly called `project_id` (it always held ids).
  **Operators must know two things:** (1) the **6 saved recipes on the NAS were deleted**,
  not migrated — recreate them in the builder (a recipe carrying the old key would now
  error on load, which is worse); (2) **project folders were renamed** — `proj-ae-biomegune-0525`
  is now `AE-biomaGUNE-0525`, `proj-claudia` is now `claudia`. Any saved shortcut into a
  project folder needs re-pointing; `/raw/` was not touched and no data moved.
  Live migration done in a no-ingest window via `tools/migrate_project_naming.py`
  (dry-run-first, resumable, `--reverse`-able; kept as the paper trail): 51 registry rows,
  **48 folders renamed**, 43 `_project.yaml` rewritten, header-only change to `registry_raw`
  (values untouched — all 13,582 verified still joining). Hard links intact (134/134 pairs
  confirmed same-file), Finder regenerated, exe rebuilt + redeployed (checksum-verified,
  previous kept as `.old_20260802`) and smoke-tested against the migrated schema. Backup
  off-NAS at `C:\Users\rtasseff\temp\gjesus3_projectnaming_backup_20260802` — keep until
  the first operator ingest confirms good. Model + consumer table:
  [`../mfb-rdm-docs/05_PROJECTS.md`](../mfb-rdm-docs/05_PROJECTS.md) §2a; full record in
  [`../CHANGELOG.md`](../CHANGELOG.md). **Open follow-ups (push, operator comms,
  rollback-asset retention, disk leftovers) are tracked in
  [`project_naming_handback.md`](project_naming_handback.md) — delete it once drained.** **Still open (deliberately):** the *semantic*
  re-projecting of person/topic projects (PROJ-05 / [`BACKLOG.md`](BACKLOG.md)) — this was
  mechanical normalization only; and the 5 closed-but-present folders, whose deletion
  remains a separate Data-Office action.
- **Scheduled global Finder rebuild — ✅ MIGRATED to WorkstationOps + LIVE (2026-07-24).**
  The daily global rebuild is now owned by the separate **`WorkstationOps`** app
  (`C:\Users\rtasseff\OneDrive - CIC biomaGUNE\WorkstationOps`, its `finder-refresh` op,
  daily 03:00; that repo's commit `8759673`) — schedule, run log, health/overdue signal, and
  failure notification. This repo keeps only the generator (`tools/generate_index.py`).
  Cutover done: the interim `gjesus3 Finder refresh` 05:00 task was unregistered,
  `WorkstationOps-finder-refresh` scheduled at 03:00 (verified Ready, next run confirmed), and
  `tools/scheduled_finder_refresh.bat` deleted. Operational detail + the repo-move
  interdependency: [`../mfb-rdm-docs/11_OPERATIONS.md`](../mfb-rdm-docs/11_OPERATIONS.md) §5.6.
- **Operator-GUI polish — ✅ LANDED; merged to `main` (`97500cb`), exe rebuilt + REDEPLOYED + validated in production (2026-07-20).** Four GUI items
  from the 2026-07-17 microscopy operator test (issues 2/3/4 + the index-refresh addendum):
  (1) the metadata-token palette now offers the **full resolver token set**
  (`original_name`, `instrument`, …) in the builder + both runner palettes + the MRI
  page, sourced from one list in `resolver.py` (new `/api/link_tokens`) so it can't drift;
  (2) operator-visible **"NAS" → "RDM System"** across templates / JS / help / two `app.py`
  error strings, with a `GLOSSARY.md` definition (internal `nas_root*` identifiers untouched;
  one residual in the shared-core `env.NasRootError` message deliberately left — a
  Data-Office call);
  (3) a **completion modal** on real (non-dry-run) ingest, both pages, dismissible +
  accessible (new `static/completion_modal.js`);
  (4) **per-project Finder refresh on GUI ingest** — the GUI called the ingest functions
  directly and bypassed `ingest_raw.main`'s auto-refresh, so a GUI upload never updated
  any index; the ingest worker now regenerates just the touched project's `index.html`
  (targeted `--project`, never the global index — that's the scheduled job), on both pages,
  best-effort. Merged `main` (finder-refresh foundation) into the branch; spec bundles
  `generate_index.py` + `find_acq.py`.
  **Rebuilt + deployed:** `gjesus3_ingest.exe` rebuilt (off-OneDrive temp dir) and
  redeployed to `\\GJESUS3\…\tools\` backup-first (old exe + all registry CSVs backed up
  off-NAS; staged-copy + rename because a transient SMB lock blocked the in-place overwrite),
  checksum-verified byte-identical, temp build erased. **Validated in production** through the
  deployed exe by a real AxioScan ingest of one animal `.czi` into the existing PROJ-0014 —
  all four fixes confirmed live (tokens, no "NAS", completion modal, and the project
  `index.html` hash/mtime changed with the new acq present = the refresh fired in-frozen) —
  then **fully removed** backup-first, every count back to baseline. The removal surfaced the
  hidden `.acq_id_seq.json` ACQ-ID reservation (ids are never auto-reused), now documented.
  **Docs:** [`../mfb-rdm-docs/10_TOOLS.md`](../mfb-rdm-docs/10_TOOLS.md) §2.1 gained a
  **Side-effect inventory** — every file/row an ingest writes + how to reverse each
  (cross-linked from `INGEST_CLI.md`).
  Branch + worktree retired; `refactor/project-naming` (P) now builds on `main`. Narrative in
  [`../CHANGELOG.md`](../CHANGELOG.md); the temporary handoff + addendum notes were dropped on
  landing (per the 2026-07-17 precedent).
- **Operator-GUI fixes landed + VERIFIED IN PRODUCTION, exe redeployed (2026-07-17).**
  Both branches merged to `main`, the fixed `gjesus3_ingest.exe` rebuilt and
  **deployed to the NAS** (`\\gjesus3\…\tools\`; old exe + registries backed up
  off-NAS first), and validated end-to-end by a real 9-acquisition AxioScan ingest
  **through the deployed exe** — all 9 wrote `README.txt` (the former crash point) and
  auto-derived anatomy from the organ map, confirming both fixes work in-frozen. The
  smoke-test acqs were then removed (registry back to 13,557).
  - **Frozen-exe resource loads** (`fix/gui-frozen-exe-resources`): the exe had
    **never completed a real ingest** — README generation crashed because the
    `ingest/` layer wasn't `sys._MEIPASS`-aware and `README_raw.txt` (+ `project.yaml`,
    `tools/reference/`) was never bundled. Fixed via a frozen-aware
    `ingest/resources.py` resolver + bundling; two guarded siblings
    (`create_project.py`, `anatomy_derive.py` — silent microscopy-anatomy loss) closed too.
  - **Recipe override semantics** (`fix/microscopy-gui-filters-and-gaps`): a recipe
    could show one config in the GUI but ingest another. Independently reviewed
    ([`../tools/operator/gui/microscopy_gui_override_semantics_review.md`](../tools/operator/gui/microscopy_gui_override_semantics_review.md))
    and fixed — the builder writes structural keys explicitly (erasing the
    `group_code=MFB` filter now CLEARS it) and the runner shows/enforces the EFFECTIVE
    filter (narrow-only); blank-start builder kept; value-field catalogue unified.
  - **Remaining:** a quick live-GUI eyeball of the erase-filter WYSIWYG interaction
    (the ingest path is proven); the operator microscopy pilot can now run on the
    deployed exe. (The Finder `index.html` wasn't auto-refreshed by that GUI
    ingest — root-caused 2026-07-20: the GUI never called the CLI's refresh path.
    Fix in progress — a scheduled global rebuild + a targeted per-project refresh;
    the per-project GUI wiring ships with the next exe build. See
    [`../tools/FINDER.md`](../tools/FINDER.md).)
- **Operator pilot test of `gjesus3_ingest.exe`.** Run the frozen exe on a clean
  (no-Python) machine, then a 1–2 friendly-operator pilot per page. The MRI page
  needs, per operator machine: the SFTP credential file `~/.ssh/gjesus3_mri.cred`
  (data office, out-of-band — the one prerequisite that blocks MRI on a fresh
  machine), reachability of the scanner host, and the NAS mount.
- ✅ **NI live-box sync — IN TRUE PRODUCTION since 2026-10-08; merged into `main` 2026-10-09
  (`3127ad0`).** Researchers who run the Molecubes scanner sync from the acquisition Mac with two
  commands (`ni-ingest <folder> --plan`, then `ni-ingest <folder>`). Their copy of the code is staged
  from `main` at `S:\gnuclear\2026\Jesus\_gjesus3_sync\`, with an illustrated guide; the Data Office
  runbook is [`../tools/operator/NI_LIVE_RUNBOOK.md`](../tools/operator/NI_LIVE_RUNBOOK.md). Entry
  point: [`RESUME_ni_live.md`](RESUME_ni_live.md) (current state; the full history is archived).
  - **First sync, 2026-10-08:** Irene's whole box folder, 95/95 reconstructions (6.07 GB), 75
    skipped as already loaded by the August pull, 52 CT attenuation maps filed as derived files.
    Links and animal records were finished from Windows the same night; every check passed.
  - **The Mac is operated from the Data Office** through the reverse SSH tunnel (since
    2026-10-01; [`live_machine_remote_access.md`](../equipment/nuclear-imaging/live_machine_remote_access.md)).
    **Interim:** its gjesus3 mount uses Ryan's login until Box A pulls through the tunnel (IT
    declined an account).
  - **Clean-up phase done 2026-10-09:** the RESUME cut to a current-state page, the plans and the
    full RESUME archived, the tunnel field card, plist and visit notes moved into the repo, the
    staging scripts made one tool (`tools/operator/stage_ni_gnuclear.py`), and the test kits and
    scratch copies removed from Ryan's gnuclear folder after their evidence was archived.
  - **Waiting on Ryan:** the 103 recoverable older animal records (§0.7).
  - **After the sync (Ryan, 2026-10-01): one ingest web app on Box A** for every instrument. It
    pulls NI data through the tunnel, so operators can leave the room when the scan ends. The
    tunnel moves to Box A without a visit (B2 decided). See [`BACKLOG.md`](BACKLOG.md)
    "Ingest from one place".
- ✅ **NI historical pull from `S:\gnuclear` — DONE IN TRUE PRODUCTION 2026-08-13.**
  Branch `feat/ni-gnuclear-historical` (not pushed). **NI went from 132 to 1,640 rows** —
  **1,508 acquisitions / 192.0 GB** ingested in 7 researcher batches, **0 failed, 0 validator
  errors** across all 15,474 production rows, 0 duplicates, 0 blank timestamps.
  - **Source snapshot** (kept): `staging/ni_gnuclear_20260812/` — 2,485 files / 286.3 GB pulled
    read-only off `S:\gnuclear`, verified **2,485 ok / 0 corrupt / 0 missing**. `S:\gnuclear`
    itself was never written to.
  - **Unit = one acquisition per *reconstruction*** — `(timestamp, modality, algo, recon_idx)`,
    matching the live-box model so the sources reconcile.
  - **14 projects touched, 4 newly created** (`0324`, `0421`, `1024`, `1122`) — all verified
    against the animal-facility DB. 1,146 subject rows.
  - ⚠️ **673 acquisitions HELD BACK (D-G)** — no *valid* protocol code in their path; those
    researchers filed by study/tracer name. **They need a `(researcher, series)` → AE-code
    mapping before they can be ingested**; the snapshot is kept for exactly that. Dedup is on the
    machine timestamp, so adding them later is safe.
  - **The review that made this safe:** [`REVIEW_FINDINGS_2026-08-13.md`](REVIEW_FINDINGS_2026-08-13.md).
    Without it the run would have created **25 projects, 21 fabricated** from date folders and
    animal numbers. Protocol codes are now DB-validated with walk-up recovery (99 recovered,
    15 rejected). Runbook + evidence: [`ni_gnuclear_production_runbook.md`](ni_gnuclear_production_runbook.md).
  - ⚠️ **The shared `J:\gjesus3-sandbox` registry is STALE** — header still has `project_hint`
    where the code expects `project_id` (renamed 2026-08-02), so `assert_header_compatible`
    refuses to append. **Migrate it before anyone uses that sandbox again.**
  - Not to be confused with the NI *live-box* sync above — this was a one-time backfill.
- ✅ **No-DICOM MRI regeneration — DRAINED 2026-07-16** (branch
  `feat/dicom-regen-backfill`; full narrative in [`../CHANGELOG.md`](../CHANGELOG.md)).
  The worklist (`registries/pending_dicom_regen.csv`, 612 rows) is at **0 `pending`**:
  **153 `regenerated`** (17,122 DICOMs / 1.64 GB filled into the existing
  `<ACQ-ID>.data/` placeholders — ACQ-IDs kept, registry rows updated in place via the
  new `registry.update_row`, the 78 blank `acquisition_datetime` all real now, ages
  refilled wherever a `date_of_birth` exists), **365 `not-applicable`**
  (spectroscopy/calibration — the input set for the deferred spectroscopy path,
  `BACKLOG.md`), and **94 `no-source`** (image exams with no reconstructable source on
  the platform host — 80 header-only + 14 fid-only; a data-loss record, not a task).
  The blocker was closed as designed: a standalone backfill on the recovery pattern
  ([`tools/backfill_dicom_regen.py`](../tools/backfill_dicom_regen.py); spec
  [`10_TOOLS §3.8`](../mfb-rdm-docs/10_TOOLS.md), procedure
  [`11_OPERATIONS §5.5`](../mfb-rdm-docs/11_OPERATIONS.md)) — plus a **third Dicomifier
  workaround** ([`tools/ingest/dicomifier_driver.py`](../tools/ingest/dicomifier_driver.py)):
  stock Dicomifier crashes on all 153 (single 3D volumes stored reverse-slice-order)
  and its slice flip is a silent no-op; both fixed + pixel-level validated (upstream
  issue draft pending filing). Project hard-links rebuilt from Windows (663 created —
  incl. 510 pre-existing empty shells left by the 2026-06-14 relink; the 2 remaining
  candidates are the known link-name-collision pairs, `BACKLOG.md`). Invariant — **no
  DICOM-less acquisition without a worklist row** — holds
  ([`tools/backfill_pending_dicom.py --dry-run`](../tools/backfill_pending_dicom.py)
  → 0 to add). The operator runbook was corrected (false idempotency claim) and
  archived to `tasks/archive/`.
- ✅ **`age_at_acquisition` derived against the ingest date — FIXED 2026-07-15**
  (commit `f567fae`). 92 no-DICOM MRI acquisitions carried an age measured to their
  *ingest* date (`ACQ-20260613-MRI-001`: dob 2021-06-09 → `P1830D`, exactly its
  2026-06-13 registration date) — a plausible number in a DB-sourced field, not an
  obvious null. **Writer:** `ingest_raw.py` Step 3 falls back to `datetime.now()`
  for the ACQ-ID prefix and used to hand that placeholder to
  `enrichment.build_enrichment`; it now withholds it, so the age stays blank when
  there is no real date. Fixed at the call site deliberately — `_acq_for_age`'s
  ACQ-ID-prefix fallback is *correct* for the DICOM-StudyDate branch and only the
  caller can tell the two apart. Pinned by `test_age_needs_a_real_date`.
  **Data:** all 13,557 sidecars were rescanned (each age recomputed from its own dob
  against the registry date) — exactly 92 wrong, 0 disagreements among the 10,666
  with real dates; those 92 are now blanked on the NAS (age only; backup at
  `gjesus3_age_blank_backup_20260715`) and a rescan reports 0. **Closed 2026-07-16:**
  the backfill drain (item above) refilled ages from real regenerated-DICOM dates
  wherever a `date_of_birth` exists; rows without a dob stay blank (that gap is the
  `pending-db` subject-metadata lane, not this bug).

### 2.1 Safe-operation follow-ups from the 2026-07-08 review (triaged 2026-07-11)

The [architecture + code review](archive/2026-07-08_architecture_code_review.md) was
triaged and its findings re-verified against the code (see
[`BACKLOG.md`](BACKLOG.md#architecture--code-review-follow-through-2026-07-08) for
the full per-item outcome). Three items are safe-operation and promoted here; all
other findings are confirmed-real *later improvements* and stay in `BACKLOG.md`.

- ⚠️ **Off-site backup / disaster recovery — the #1 risk.** One NAS, RAID 5 on
  20 TB drives, no off-array copy, in true production; for microscopy `.czi` this
  is the *only* copy. It is the single item that can cause total, unrecoverable
  loss. The 3-2-1 plan is already written
  ([`02_INFRASTRUCTURE §5.4`](../mfb-rdm-docs/02_INFRASTRUCTURE.md)); reframe from
  "PI decision" to a purchase and execute. Inaction, not a design gap.
- ✅ **Concurrency / partial-failure integrity fixes — LANDED 2026-07-12** (merged to
  `main`, commit `911f69e`; unit-tested, no live-NAS operations). The `pending.py`
  recovery-queue write is now atomic (temp+`os.replace`) and serialized under the
  registry lock; copy-phase verify failures roll back their partial folder;
  `committed=True` moved inside the lock right after `append_row`; and
  `checksum_present` now reports "N" for the empty no-DICOM MRI placeholder instead
  of a hardcoded "Y". **Still open from this cluster:** the **pre-lock dedup
  snapshot** (`config.py` builds the dedup index before `ingest_raw.py` takes the
  lock, so a double-launched batch can double-ingest) — needs design input, tracked
  in [`BACKLOG.md`](BACKLOG.md). Currently mitigated by the single-operator manual
  workflow; land it before any concurrent or automated ingest.
- 🕗 **Schedule `verify_checksums` weekly.** The tool exists but nothing runs it.
  With no DR yet, scheduled checksum verification is the only current tripwire for
  silent corruption — the cheapest partial mitigation for the durability gap.

**Not blocking** (tracked in [`BACKLOG.md`](BACKLOG.md)): external-drive microscopy
ingest; researcher-feedback re-projection of the best-guess legacy microscopy;
study-level project metadata (Phase 4 — planned, deployed on 0 of 50 projects
today); the various link-naming and `-None`-subject refinements; spectroscopy /
non-image MRI; the server-side ingest-host architecture.
