# gjesus3 RDM Pilot — Status

**Last Updated:** 2026-08-16

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
| Acquisitions in `/raw/` | **15,474** (all checksummed + `metadata.json` sidecar'd) — includes the **75 human** cardiac-MRI acquisitions of `DTS24` (§2) and the **1,508** from the `S:\gnuclear` NI backfill (§3) |
| Projects | **57 registered** — 49 active + **8 `closed`** (rows retained; 3 folders deleted 2026-07-14, 5 still present). Every live folder carries the four subfolders since the 2026-08-12 backfill. **Folder name == project name** since 2026-08-02 (no `proj-` prefix) — see §2. |
| Subjects (`registry_subjects.csv`) | **1,124** (one row per subject) — was 1,146 until the 2026-08-16 `-None` subject-id repair, which dropped 65 ambiguous rows and added back 43 real ones (see 2). The 2026-08-19 PROJ-0056 repair left the total unchanged (3 rows dropped, 3 added). |
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
