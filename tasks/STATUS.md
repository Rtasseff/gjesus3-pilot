# gjesus3 RDM Pilot — Status

**Last Updated:** 2026-10-02

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

**Nothing below is blocked on work. Each item is blocked on a decision.** The evidence is gathered,
written down, and linked; none of it needs re-deriving. Ordered by cost-of-getting-it-wrong, not by
effort.

**The one rule that covers all of them:** where a value is unknown, it has been left **blank or
`pending`** rather than guessed. Every item below is safe to leave alone indefinitely — the system
is internally consistent as it stands.

| # | Decision | Cost of delay | Detail |
|---|---|---|---|
| **D1** | **`operator` on 10,314 MRI rows** still holds the literal `<REQUIRED - set via mri-ingest --operator, or replace here>`. **This makes `validate_registries` exit FAILED with 10,314 errors** — so the validator cannot gate anything until it is settled. **Recommendation: blank them** (the documented unknown sentinel, already on 1,583 rows). Do **not** derive from `acqp.ACQ_operator` — it reads `nmr`, a shared login, not a person. | The validator is red, so a *real* new error would hide in the noise | [`BACKLOG.md`](BACKLOG.md) HIGH (2026-08-20) |
| **D2** | **`jrc260224_m39_0525` is probably animal 37, not 39** — 19 production acquisitions (`ACQ-20260224-MRI-020`…`-038`). The facility DB logs MRI 7T on 2026-02-24 for `31,32,`**`37`**`,38,43,44`; five of six match the registry and the sole mismatch is this session. Animal 39's MRI is logged 02-25, where a separate session already exists. Irene's own copy says `m37`. **Ask Irene — one sentence settles it.** | A wrong subject id resolves cleanly and looks like data (the PROJ-0056 lesson) | [`BACKLOG.md`](BACKLOG.md) HIGH (2026-08-21) |
| **D3** | **Unparsed ParaVision studies are dropped silently.** A folder token that matches neither ingest regex is globbed, parsed to nothing, and skipped with **no error and no worklist row**. One instance found (recovered as G1); **how many the kenia pull dropped is unknown because nothing recorded them.** Needs (a) a code change to report unparseable matches, then (b) a re-glob to quantify the historical damage. **Measured on the historical drives (2026-10-02):** 1,568 exams sit in studies that match neither ingest regex, and **0 of them are in production**. They include 526 post-horizon `1519` `_weekN` exams, now ingested from the drives, and nine May 2023 `0721` `_biod` sessions, which are on the drives only as NIfTI (the raw is probably still on kenia). See `tasks/drives_dicom_review.md` §5. | Until (b) runs, "the historical MRI pull is complete" is an assumption | [`BACKLOG.md`](BACKLOG.md) HIGH (2026-08-21) |
| **D4** | **19 schema gaps from the curated-datasets pilot** — `sample_unit`, plural `label_formats`, `file_role`, `label_origin`/`review_status`, ordered multi-ACQ reference, `recon_index`, `spatial_reference`, a verification enum, a `corrects` cross-reference. All change documented schema, so none were applied. | The four promoted datasets encode workarounds that a settled schema would replace | [`BACKLOG.md`](BACKLOG.md) MODERATE + `projects\Imaging\SegBioMed\harvest\DS-SEG_definitions_draft.md` §C/§E/§F |
| **D5** | **`DS-SEG-0001` v1.1 is prepared and NOT applied.** It corrects a slice-order swap on `jrc211209_m85_1019` found by `DS-SEG-0004`'s pixel evidence. Overwriting an already-promoted dataset is a §7 revision; both agents stopped at that gate. **Production v1.0 is internally consistent and the defect is documented in three places.** Mask files are unchanged either way. | Low — v1.0 is consistent, just known-imperfect | `projects\Imaging\SegBioMed\harvest\DS-SEG-0001_v1.1_proposed\` (v1.0-vs-v1.1 diff + one-command apply) |
| **D6** | **Mint the `SegBioMed` project** and attach the **854** project-less 2021 acquisitions + the 5 Dec-2021 `1019` sessions the datasets cite. Deliberately not done — protocol→project is a convention, not a rule, and this is the call that decides where segmentation-supporting imaging lives. | None — ACQ-IDs are the durable identity; provenance already resolves 100% without a project | SegBioMed memo §G9 / D11 |
| **D7** | **5 header-only G1 exams** (`ACQ-20260821-MRI-001…004` + `ACQ-20250526-MRI-094`) have **no `2dseq` and no `fid`** — un-regenerable. Flipping them to terminal `no-source` is human-gated in [`../mfb-rdm-docs/11_OPERATIONS.md`](../mfb-rdm-docs/11_OPERATIONS.md) §5.5 step 6. Left `pending`, which is the honest state. | None | [`BACKLOG.md`](BACKLOG.md) |
| **D8** | **MILabs VECTor onboarding** — an in-service instrument with **zero acquisitions** in the registry. Blocks the 2026 Imalytics lung study. Real integration work (no instrument code, no ingest path, no extractor, no `OI` code). SegBioMed has been told to expect a long wait. | The instrument keeps generating unarchived data | [`BACKLOG.md`](BACKLOG.md) MODERATE (2026-08-21) |
| **D9** | **`CDS-03` — label formats per ecosystem.** SegBioMed's recommendation: `.nii.gz` labelmap + JSON sidecar as the working format, DICOM-SEG for interchange, vendor originals kept authoritative. `.voi`→NIfTI is convertible but **not lossless as one file**. Working assumption is mixed-now-converge-later. | None — mixed is already the working assumption | [`../mfb-rdm-docs/12_CURATED_DATASETS.md`](../mfb-rdm-docs/12_CURATED_DATASETS.md) §CDS-03 |

**Where the conversation lives:** the full exchange with the SegBioMed project — six replies each
way, including every correction and its evidence — is appended to
`projects\Imaging\SegBioMed\harvest\MEMO_for_gjesus3_agent.md`. Read it if any of D2/D4/D5/D6/D9
needs context.

### Re-verifying this page before you trust it

Every number above is measured, not remembered — but production moves, so **check before acting**.
All read-only, seconds to run:

```bash
# row count (compare against the §1 table)
python -c "import csv,io;print(sum(1 for _ in csv.DictReader(io.open(r'J:\gjesus3-data\registries\registry_raw.csv',encoding='utf-8-sig',newline=''))))"

# D1 -- is the validator still red, and red ONLY for `operator`?
PYTHONPATH=tools python tools/validate_registries.py --nas-root "J:\gjesus3-data" --no-enrichment
#   expected today: FAILED, exactly 10,314 errors, ALL of them the `operator` placeholder.
#   A DIFFERENT count means something new happened -- do not wave it off as "the known red".

# D7 -- what is still queued for DICOM regeneration
python -c "import csv,io,collections;print(collections.Counter(r['status'] for r in csv.DictReader(io.open(r'J:\gjesus3-data\registries\pending_dicom_regen.csv',encoding='utf-8-sig',newline=''))))"
#   expected: not-applicable 365, regenerated 162, no-source 94, pending 5 (the D7 header-only exams)

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
| Acquisitions in `/raw/` | **27,034 on 2026-10-05**, after the last same-timestamp list (−81 ROI crops). Before that, **27,115 on 2026-10-04, at the end of the weekend close-out.** The steps: −72 same-timestamp derivatives retired (stream D); +526 from the drives' last DICOM batches (stream B); +15 raw stragglers (stream A: the dot-file `.czi` and 14 nested `.czi`). Before that, **26,646** after retire v2's first operations (−1 equivalent, −13 derivatives; 2 re-identified in place). Before that, **26,660**: **+660** from the drives' `1519` MRI (stream B), and **+210** from the July protocol-1125 MRI series and the `jrc` phantoms, from the scanner (stream F). Before that, **25,790 on 2026-10-04**: **+578** from the drives' MRI/PET-CT (stream B: `0619`, `0420`, `1319`; §2). Before that, **25,212 on 2026-10-02**: **+17** from the re-ingested 2026-07-10 MRI session (§2), after the first retirements (**−32** duplicate registrations, §2) had taken it to 25,195. Before that: **25,227**, after **+8,790** historical `.czi` from the operators' external drives (§2); then: 16,437 on 2026-09-30, after +62 operator AxioScan on 2026-09-29. Earlier history: **16,375** (all checksummed + `metadata.json` sidecar'd) — 15,474 until 2026-08-21, then **+854** from the 2021 `Proyecto 1019` recovery, **+24** from the G1 session, and **+23** from a routine operator AxioScan ingest on 2026-08-26 (`PROJ-0059`). Also — includes the **75 human** cardiac-MRI acquisitions of `DTS24` (§2) and the **1,508** from the `S:\gnuclear` NI backfill (§3) |
| Projects | **58 registered** — 50 active + **8 `closed`** (rows retained; 3 folders deleted 2026-07-14, 5 still present). Every live folder carries the four subfolders since the 2026-08-12 backfill. **Folder name == project name** since 2026-08-02 (no `proj-` prefix) — see §2. |
| Subjects (`registry_subjects.csv`) | **1,165** (one row per subject; 1,124 until the 2026-08-21 ingests added the 2021 animals) — was 1,146 until the 2026-08-16 `-None` subject-id repair, which dropped 65 ambiguous rows and added back 43 real ones (see 2). The 2026-08-19 PROJ-0056 repair left the total unchanged (3 rows dropped, 3 added). |
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

All on-network historical imaging is ingested. Per-instrument counts (live, 2026-08-13):
MRI 10,330 + 75 `XMRI` (external), Cell Observer 1,739, **Nuclear Imaging 1,640**
(CT 1,149 + PET 491), AxioScan 7 885, LSM 900 805. (Durable per-instrument record:
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
- **NI live-box sync — go-live.** The live-machine sync code is built and verified
  end-to-end in a sandbox (it is a config, not a new orchestrator — the existing
  `ingest_raw` does the walk). The remaining gate is **Gate-0**: confirm `os.link`
  (hard-link) behaviour on the live NI Mac's CIFS mount, then a vetted one-shot
  ingest per researcher. Archive-mode NI is already done and is the durable
  source-of-truth; live sync is the forward path for active project data.
  **Remote access to the box is being established** so Gate-0 no longer needs a
  physical access slot — reverse SSH tunnel, workstation half verified 2026-08-06,
  box half installed at the next access window. See
  [`../equipment/nuclear-imaging/live_machine_remote_access.md`](../equipment/nuclear-imaging/live_machine_remote_access.md).
  Gate-0 is the first real task for that tunnel (NI-RA-05).
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
