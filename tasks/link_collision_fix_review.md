# Review: project link names are never merged into; the repair of what the old merge left (branch `feat/link-collision-fix`)

**Date:** 2026-10-05 · **Stream:** link-collision fix, a subagent of the coordinator (`gj3-handoff`) ·
**Status:** ✅ **code, convention and tests merged to `main` (70c5023, 2026-10-05) after the coordinator's review.**
**Ryan's answers (2026-10-05), all approved:** (1) the MRI link-name form `MRI_<sample>_<date>_<HHMM>_<exam>_<recons>` is
**confirmed**; (2) **add the 389 microscopy links too**, with the drives naming rule (`--include-file-primaries`); (3)
**remove the foreign links from the 7 polluted folders**, foreign names only; (4) rebuild, smoke-test and redeploy the GUI
exe (a separate phase, C). The coordinator granted the write window for phases A (the repair) and B (the polluted folders);
their results are in §11.

**In one paragraph.** The linker now refuses a taken project link name instead of merging into it, and the ingest checks the
name before copying, so a collision fails the case cleanly. The MRI link name gains the study start time. A file-id audit of
every project found **589 acquisitions without their own link**: **200 MRI** (reconciling with stream F's 209: the other 9
have empty raw folders) and **389 Cell Observer / LSM 900** that F's MRI-only audit could not see. It also found **7 polluted
MRI link folders** and only 2 links pruned by researchers. The 200 MRI links are planned and dry-run clean; the 389 and the 7
need Ryan. 35 of 35 test suites pass.

**Ryan's approval (2026-10-05):** "Fix code + repair". The option he chose: *"The ingest refuses a taken link name, MRI link
names get a per-study part, and the 209 missing link folders are added under distinct names. Additive only; nothing is
removed."*

---

## 1. The defect

`tools/ingest/linker.py` `create_hardlink` (before this branch, lines 134-209):

- **Folder primary:** `os.makedirs(dest, exist_ok=True)`, then it linked only the files where `not os.path.exists(dst_f)`.
- **File primary:** `if not os.path.exists(dest): os.link(...)`.

So when two acquisitions resolved to one link name, the second **silently merged** into the first: if its file names
matched the first's it got none of its own files; if not, its files were added to the first's folder, polluting it. No
error, and provenance could not show it (`provenance.append_entry` is idempotent on `output_path`, so the second
acquisition got no row). The trigger was the internal-MRI link name
`MRI_${sample_id}_${acq_date}_${discovered.mri_exam_number}_${discovered.mri_recon_indices}`, which has no per-study part:
two studies of one animal on one day (a repeat session, a `_bis` study, a time-point series) collide on every exam number
they share. Stream F found it on 2026-10-04 (`tasks/mri_july_1125_review.md` §2.1). `/raw/` and the registry were never
affected.

## 2. The code fix

### 2.1 The rule, in one place (`tools/ingest/linker.py`)

- **`inspect_link_target(project_folder, link_name, raw_primary=None)`**, read-only, returns `free` / `own` / `partial` /
  `taken` by **file identity** (`os.path.samefile`, file by file):
  - `own`: a file primary's name is the very file; a folder primary's folder holds every one of its files, each the same
    file as the raw file at the same relative path, **and nothing else**.
  - `partial` (folder primary only): only its own files but not all of them, or an empty folder. Completing it adds only
    its own files, so nothing is merged. This keeps the two legitimate repair cases working: an interrupted run, and the
    empty shells a mount without hard-link support leaves (the WSL `EPERM` shells, the NI Mac).
  - `taken`: anything else, including its own folder with one extra foreign file. Strict on purpose.
  - **`raw_primary=None` is the pre-copy check** a new acquisition makes: nothing at the name can be its own, so anything
    there (even an empty folder, or the `<name>.PENDING-LINK.txt` stand-in of a link still queued for another acquisition)
    is `taken`.
- **`create_hardlink`** runs it first. `own` is a no-op (the idempotent re-run), `partial` is completed, `free` is created,
  and **`taken` raises `LinkCollisionError`** with nothing written. `dry_run=True` runs the same check.
- **`LinkCollisionError` is deliberately not an `OSError`.** Ingest Step 12 and `manager/raw_import` queue an `OSError` to
  `registries/pending_links.csv`; a relink of a taken name would only collide again, and a collision needs a person to
  choose a name.

### 2.2 The ingest refuses before the copy (`tools/ingest_raw.py`)

- **New Step 5.5, `_preflight_project_link`:** after the ACQ-ID and the destination are known and before anything is
  copied, it resolves the project the way Step 9.5 will (read-only, no auto-create) and the link name the way Step 12 will,
  then checks the name with `inspect_link_target(..., None)`. **A taken name fails the case: nothing copied, nothing
  registered;** the log names the taken link, and the batch summary prints the reason under *Failed cases*. The ACQ-ID
  reserved a moment earlier stays reserved, an ordinary gap (ids are never reused, 10_TOOLS side-effect row #2).
- **It runs in `--dry-run` too**, and `run_batch` shares a dict across a dry run's cases, so two cases of one batch that
  would take one name are also reported, although a dry run creates neither link. (Keyed by the case's source path: a dry
  run reserves no ACQ-ID, so two cases preview the same id.)
- **Step 12** links exactly the name the pre-flight checked (`cfg_single["_link_plan"]`), unless the project was
  auto-created in between, when it re-resolves. If the name became taken after the pre-flight (a concurrent writer: the
  only remaining path), `LinkCollisionError` is caught **before** the `OSError` handler: ERROR line, **not** queued to
  `pending_links.csv`, no stand-in; the acquisition stays registered without a link, and the batch summary lists it under
  *Registered WITHOUT a project link (name taken)*.
- Step 12's raw-primary dispatch and link-name resolution moved into two helpers (`_raw_primary_path`, `_link_name_for`)
  shared with the pre-flight; behaviour unchanged.

### 2.3 Every caller, and what a refusal means there

| Caller | Before | After |
|---|---|---|
| `ingest_raw.py` (CLI, and the operator GUI through `operator/runner.py`) | Step 12, after the commit: merged / skipped silently | **Fail the case before the copy** (Step 5.5, also in `--dry-run`). Race only: registered, no link, listed in the summary, not queued |
| `relink_pending.py` | merged into whatever held the name | `COLLISION`, the row stays `pending`, counted as failed (exit 1); the dry run shows it |
| `relink_projects.py` `.lnk` migration | merged | `COLLISION`, the `.lnk` is kept |
| `relink_projects.py --create-missing` | `exists(dest)` → skipped silently (hid the missing link) | own → skipped; taken → `COLLISION`, counted, exit 1 |
| `reopen_project.py` | a folder that was "not the same" passed through as "a partial folder-of-links … completed additively", which merged a foreign folder | `inspect_link_target`: own-partial → completed; taken → `COLLISION`, left alone (05_PROJECTS §4.y point 3 already promised this) |
| `relink_mri_regen.py` (one-off, done) | "complete" judged by DICOM count, which counted a partner's files | by file identity; taken → `COLLISION` |
| `relink_axioscan_collisions.py` (one-off, done) | an existing dated name counted as done | only if it is that acquisition's file; else `COLLISION` and the date-less link is kept |
| `manager/raw_import.py` (Project Manager import; also `nonraw_placement apply-raw`) | `plan()` already reported a taken name; only a race reached the linker | unchanged plan; a race → outcome `failed` (not `queued`, since the error is not an `OSError`) |
| `retire_acquisition.py` re-point / place | its own primitives | **no change needed:** it acts only on a link whose files are exactly the retiree's (`tree_identity == "same"`), calls anything else `foreign` and leaves it, and re-verifies after |
| `operator/collisions.py` (GUI preview) | in-batch check case-sensitive on the link name; on-NAS check `os.path.exists` | case-insensitive (Windows/SMB); the on-NAS check is the engine's own `inspect_link_target(…, None)`, so an empty shell or a queued stand-in shows too. GUI message text corrected (it said "one would overwrite the other") |
| `drive_staging/ingest_plan.py` farm | staging farm on D:, not a project link | no change (already refuses a non-`samefile` target) |

## 3. The MRI link-name convention — ✅ confirmed by Ryan (2026-10-05)

**Proposed form:** `MRI_${sample_id}_${acq_date}_${discovered.study_time}_${discovered.mri_exam_number}_${discovered.mri_recon_indices}`

**Example:** `MRI_m12_1125_20260710_1147_2_1` (the first m12 study of 2026-07-10, exam 2, recon 1). The `_bis` study of the
same animal-day becomes `MRI_m12_1125_20260710_1308_2_1`.

- **`study_time`** is `HHMM` of the ParaVision study folder's leading `YYYYMMDD_HHMMSS_` (the study start). It is an
  optional named group added to the template's existing `filename_parse.regex`
  (`^(?:\d{8}_(?P<study_time>\d{4})\d{2}_)?.*?(?P<jrc_id>…)`), so it rides the parse that already runs.
- **Checked against production (read-only):** all 12,825 MRI acquisitions with a study folder carry the prefix. The new
  regex gives the **same** `jrc_id` / `pi_initials` / `animal_num` / `project_code` as the old one on all 804 production
  study names the old one matched, the right `study_time` on all of them, and matches no name the old one did not (309
  others, ingested through case tables, match neither). The prefix equals the `subject` file's `SUBJECT_date` in 92 of 92
  sampled studies.
- **Why not `SUBJECT_date`** (already exposed as `discovered.mri_study_datetime`): it is empty wherever the pull did not
  carry the study's `subject` file (whole regen batches, e.g. `ACQ-20260604-MRI-017`). The folder name is always there.
- **Why `HHMM`, not `HHMMSS`:** readable, and enough: two studies of one animal starting in the same minute is not a real
  scanner workflow. If it ever happens, the new refusal stops the second study loudly instead of merging it.
- **Alternatives considered:** the ACQ-ID's sequence number (unique by construction, but meaningless to a researcher and
  different after a re-ingest); a suffix only on collision (the name would depend on ingest order, so the same study could
  get different names in different runs: not recommended, as the handoff said); `HHMMSS` (longer for no practical gain).
- **Edge:** a study folder without the prefix (none in production) gives an empty part, `…_20260710__2_1`; the refusal still
  guards it.
- **Scope:** forward only. Existing links keep their names; the repair (§6) uses the new form for the acquisitions it links.
  The per-batch configs under `tools/configs/` are historical records and are not edited.
- **GUI palette:** `study_time` is offered as a link-name chip on the MRI page (`MRI_LINK_PALETTE_KEYS`); it is withheld from
  the project-name palette (per-session, it would mint a project per session).
- ⏸ **The operator GUI's frozen exe bundles the templates and the engine.** Until it is rebuilt and redeployed, GUI ingests
  use the old template **and the old linker** (the silent merge). The redeploy is a separate step that needs Ryan's go; it
  is queued, not done.

## 4. Tests

- **New `tools/test_link_collisions.py`** (unit + end to end): two acquisitions on one name for folder primaries (with
  overlapping and with disjoint file names) and for file primaries — the second refused, the first untouched; idempotent
  re-runs (folder and file); an interrupted own folder and an empty shell completed; a **partial-merge state** (two
  acquisitions' files in one folder) refused for A, B and a third, and left exactly as it was; wrong kinds and foreign
  content; the pre-copy mode (empty folder and queued stand-in are taken); case-insensitivity on Windows; the error is not
  an `OSError`; `dry_run`. End to end through `ingest_raw.run_batch` on a scratch NAS: the second case of one name fails
  **before its copy** (one raw folder, one registry row, link untouched); a re-run is consistent; `--dry-run` reports a name
  taken on disk and an in-batch duplicate and writes nothing; a name taken after the pre-flight is refused at Step 12 and
  **not** queued to `pending_links.csv`.
- **New `tools/test_repair_link_collisions.py`**: a scratch NAS reproduces the old merge in each of its shapes and checks
  every audit class, the dry run (writes nothing), `--execute` (backup first, links verified by file id, provenance,
  nothing removed), the re-audit and an idempotent second run.
- **`tools/test_collisions.py`** extended (case-insensitive link names; empty shell and queued stand-in flagged).
- **Whole suite:** every `tools/**/test_*.py` except `tools/diagnostics`: **35 of 35 pass** (33 on `main` + the two new).

## 5. The re-audit (production, read-only)

**Method.** `python tools/repair_link_collisions.py audit --nas-root "J:\gjesus3-data" --out <scratch>`, 2026-10-05 ~13:00,
read-only (it opens directories for listing and reads CSVs and sidecars; its reports go off the NAS). **Every** live
registry row with a project (20,557 of 27,034) against **every** project's `raw_linked\`, by **file id**, not by name:
the file ids of all 27,034 live raw primaries form the owner map (so a file of an acquisition registered elsewhere still
counts as "another acquisition's"), and each link entry's files are matched against it. About 4 million file ids, read
with one directory query per folder (`FileIdBothDirectoryInfo`; the same id as `os.stat().st_ino`, checked on 1,333 of
1,333 files, at 0.11 ms instead of 2.56 ms per file over SMB). 285 s.

**How MISSING is told from RESEARCHER-PRUNED (05_PROJECTS §3a):** MISSING needs a same-name **partner**: either some of the
acquisition's files sit in a link folder together with another acquisition's files (the merge, folder primaries), or its
planned link name (its own ingest config's `link_filename:`, resolved with its sidecar's `discovered`) is held by another
acquisition and the project's provenance does not show that exact name being created for it. No files anywhere and no
partner is RESEARCHER-PRUNED, and is never "repaired".

**Totals:** OK **18,474** · MISSING **589** · POLLUTED **7** · RESEARCHER-PRUNED **2** · EMPTY-PRIMARY 319 (raw `.data`
holds no file: nothing to compare or link; 12 of them sit in a collision) · CLOSED-PROJECT 1,166 (`1521`, `0618`, `1121`,
`0220`: links removed by the 2026-07-14 close-out, not audited) · OK-EXTRA, PARTIAL-OWN, PENDING-LINK, NO-RAW, NO-FOLDER: 0.

| Project | OK | MISSING | POLLUTED | RESEARCHER-PRUNED | EMPTY-PRIMARY (in a collision) |
|---|---:|---:|---:|---:|---:|
| `AE-biomaGUNE-0721` | 1,819 | **145** | 6 | 0 | 166 (8) |
| `AE-biomaGUNE-1022` | 1,131 | **53** | 1 | 0 | 4 |
| `AE-biomaGUNE-0219` | 378 | **2** | 0 | 0 | 82 (2) |
| `AE-biomaGUNE-1321` | 861 | 0 | 0 | 2 | 11 |
| `itziar` | 307 | **107** | 0 | 0 | 0 |
| `claudia` | 596 | **88** | 0 | 0 | 0 |
| `ros-cc-mn` | 103 | **65** | 0 | 0 | 0 |
| `laura-tholt` | 102 | **50** | 0 | 0 | 0 |
| `itziar-lipofectamine-mcherry` | 105 | **33** | 0 | 0 | 0 |
| `elena` | 42 | **21** | 0 | 0 | 0 |
| `uptake-thp1` | 37 | **7** | 0 | 0 | 0 |
| `col-i-nuevo-hlf` | 40 | **6** | 0 | 0 | 0 |
| `marina-uptake-lung-fibroblast-lp1-lp2` | 11 | **6** | 0 | 0 | 0 |
| `uptake-a549-mrna` | 5 | **6** | 0 | 0 | 0 |
| the other 42 active projects | 12,937 | 0 | 0 | 0 | 56 (2) |

Every row that is not OK or closed (917) is in [`link_collision_audit/link_audit_exceptions.csv`](link_collision_audit/link_audit_exceptions.csv); the
per-project counts of every class are in [`link_collision_audit/link_audit_summary.txt`](link_collision_audit/link_audit_summary.txt).

**MRI: 200 MISSING, and it reconciles with stream F's 209.** F counted, per multi-study animal-day, acquisitions minus
link folders: 0721 153 = 145 MISSING + 8 empty-primary acquisitions in a collision; 1022 53 = 53; 0219 3 = 2 + 1. **All 200
come from the 2026-06-14 no-DICOM regeneration batches** (`mri_jrc_projfirst_regen.yaml` 189, `mri_jrc_animalfirst_regen.yaml`
11), whose links `relink_mri_regen.py` made later through the old linker. They include the two `0219` pairs the 2026-06-14
BACKLOG item named (`ACQ-20220124-MRI-006` and `-008`).

**New: 389 microscopy acquisitions are MISSING too** (`CELL` 222, `LSM9` 167), in ten researcher-named projects, all from the
2026-06-15 **best-guess** Cell Observer / LSM 900 ingests (`cellobs_bestguess_*`, `lsm900_bestguess_*`). Their link name is
`${instrument}_${original_name}` with the basename, and those source trees reuse file names across sub-folders
(`190624/24h/CS_1.czi` and `190624/48h/CS_1.czi`) and across case (`Lipofectamine_1.czi` and `lipofectamine_1.czi`), so the
later file primary was **skipped silently**: the file-primary half of the same defect. F's audit looked only at MRI
multi-study days, so it could not see them.

**Side finding: false provenance rows.** `provenance.has_entry_for_output` compares `output_path` case-sensitively while the
share is case-insensitive. So in a case-variant collision the skipped acquisition still got a row, recording a link that was
never made (16 such rows; they first read as "pruned" until the audit keyed provenance by the exact on-disk name). The new
linker closes the path: it refuses before any provenance row is written. `provenance.py` is unchanged; the 16 rows stay
(provenance is append-only) and each victim gets a true row under its new name if repaired.

**Independent cross-check** (plain `os.stat` / `os.path.samefile`, a different code path from the audit's directory listing):
40 sampled classifications, including all 7 POLLUTED and all 7 merge-evidence MISSING rows, 8 MRI and 8 microscopy
name-held MISSING rows and 10 OK rows: **0 disagreements**.

## 6. The repair — dry run

**Within Ryan's approval (MRI): 200 links to create, 0 blocked** — `AE-biomaGUNE-0721` 145, `-1022` 53, `-0219` 2. Each name is
the §3 convention with the acquisition's own study time, e.g. `MRI_m39_0721_20220811_1052_1_1`; every one is free on disk
and unique in the plan. Plan: [`link_collision_audit/link_repair_plan.csv`](link_collision_audit/link_repair_plan.csv) (its 389 non-MRI rows are `blocked`:
"no new link-name convention for this instrument").

**Option, needs a decision: the 389 microscopy acquisitions.** `--include-file-primaries` gives each the rule the
historical-drives ingest already uses in `raw_linked\` (`ingest_plan.py`, `nonraw_placement.link_names_for`, and
`relink_axioscan_collisions`' dated names): `<INSTR>_<stem>_<YYYYMMDD><ext>`, e.g. `LSM9_CS_1_20240619.czi`, else
`<INSTR>_<stem>_<ACQ-ID><ext>`. Dry run: **389 more, 0 blocked** (360 dated, 29 fall back to the ACQ-ID because a same-day
partner or another victim needs the dated name). Plan: [`link_collision_audit/link_repair_plan_with_file_primaries.csv`](link_collision_audit/link_repair_plan_with_file_primaries.csv) (all 589).

**Not linked: the 12 empty-primary acquisitions in a collision.** Their raw `.data` holds no file, so a link would be an empty
folder carrying nothing (and since 2026-10-04 such exams are not registered as empty rows at all).

**What `--execute` does, in order** (`tools/repair_link_collisions.py`): re-runs the audit (fresh state, not the CSV
reviewed here); plans one link per MISSING MRI acquisition under the §3 name, which must be free (`inspect_link_target`
against the acquisition's own raw primary) and unique within the plan; backs up every touched project's `provenance.csv`
and `index.html` to `C:\Users\rtasseff\temp\gjesus3_link_repair_backup_<stamp>\` and verifies each copy by SHA-256 **before
any write**; then per acquisition links with `linker.create_hardlink` (which itself refuses a taken name), checks the link
is exactly its files (`own`), and appends one provenance row; finally regenerates each touched project's `index.html`.
**It writes only inside those project folders** (new link folders, provenance rows, `index.html`); no registry, no
`/raw/`, nothing removed or renamed. A re-run is a no-op: a repaired acquisition audits as OK.

**The window, step by step** (for the coordinator):

1. No ingest or other link-writing tool running.
2. From this worktree: `python tools/repair_link_collisions.py repair --nas-root "J:\gjesus3-data" --out <fresh dir>` (dry
   run). Its `link_repair_plan.csv` must match the one reviewed here row for row (same acquisitions, same new names, same
   blocked rows); if production moved, stop and re-review.
3. The same command with `--execute --by "Data Office (link-collision repair)"`.
4. Verify: `python tools/repair_link_collisions.py audit --nas-root "J:\gjesus3-data" --out <another dir>`: MISSING drops to
   the blocked rows only, OK rises by the number created, POLLUTED is unchanged (nothing is removed).

## 7. POLLUTED link folders — the list for Ryan

**7 folders, all MRI:** [`link_collision_audit/link_polluted.csv`](link_collision_audit/link_polluted.csv). In each, the folder's own acquisition is complete
and another study's same-numbered exam added the frames whose names did not clash. That second acquisition is MISSING and
gets its own folder in the repair (§6).

| Project | Link folder | Its own acquisition (files) | Foreign files, from |
|---|---|---|---|
| `AE-biomaGUNE-0721` | `MRI_m201_0721_20240422_10_1` | `ACQ-20240422-MRI-001` (5) | **155** of `ACQ-20240422-MRI-017` |
| `AE-biomaGUNE-0721` | `MRI_m236_0721_20250306_4_1` | `ACQ-20250306-MRI-022` (112) | 308 of `ACQ-20250306-MRI-030` |
| `AE-biomaGUNE-0721` | `MRI_m262_0721_20250602_3_1` | `ACQ-20250602-MRI-007` (10) | 102 of `ACQ-20250602-MRI-024` |
| `AE-biomaGUNE-0721` | `MRI_m262_0721_20250602_4_1` | `ACQ-20250602-MRI-008` (112) | 308 of `ACQ-20250602-MRI-025` |
| `AE-biomaGUNE-0721` | `MRI_m268_0721_20250612_3_1` | `ACQ-20250612-MRI-023` (112) | 308 of `ACQ-20250612-MRI-030` |
| `AE-biomaGUNE-0721` | `MRI_m289_0721_20251117_4_1` | `ACQ-20251117-MRI-016` (112) | 308 of `ACQ-20251117-MRI-029` |
| `AE-biomaGUNE-1022` | `MRI_m113_1022_20251217_2_1` | `ACQ-20251217-MRI-008` (9) | **411** of `ACQ-20251217-MRI-021` |

Two of them are mostly the other study's data (5 own + 155 foreign; 9 own + 411 foreign).

**What a polluted folder is.** The first study's link folder for an exam that also received the frames of the second
study's same-numbered exam whose file names did not clash (e.g. frames 4 to 15 of a 15-frame recon added to a 3-frame
one). A researcher opening it sees **two studies' images mixed in one folder, with nothing to tell them apart**. After the
repair the second study also has its own, clean folder, so the extra names in the polluted folder are pure noise.

**Nothing is removed in this work.** The options, for Ryan:

- **(a) Leave them.** Zero risk to anything a researcher made; the misleading mix stays.
- **(b) Remove only the foreign names** — recommended. In each listed folder, delete the hard-link names whose file id
  belongs to the other acquisition (never the owner's), after the repair has given that acquisition its own link. No data
  is lost: each removed name is one extra name of a file that stays in `/raw/` and in its own new link. It is a deletion in
  a researcher-owned folder (05_PROJECTS §3a), but of names the system put there by mistake, not anything a researcher
  made. It would be a small separate step: dry run, backup listing, a provenance row per folder, and a check after that
  each folder holds exactly its owner's files.
- **(c) Rename the polluted folder** (e.g. a `_MIXED` suffix) so nobody trusts it. Not recommended: it changes a name
  researchers may already use, and leaves the mix.

## 8. Spec and template changes (flagged)

These record an **approved logic change** (Ryan, 2026-10-05), so they are more than wording; each is marked ✅ 2026-10-05.

- **`mfb-rdm-docs/10_TOOLS.md`** (✅ DECIDED doc): Last Updated; §2.1's commit-point paragraph (+1 sentence: the name is
  checked before the copy); **§2.1.1** "re-running skips any link that already exists" → the refusal rule
  (`inspect_link_target`, `LinkCollisionError`, not an `OSError`); **§2.1.5** the MRI default `link_filename:` (code block,
  defaults table, example), two new resolution-rule bullets (a taken name is refused; every link-making tool follows the
  rule), and a paragraph on the study time and the alternatives; full-mode **step 5** gains the pre-flight; side-effect
  inventory **row 7**'s condition gains "and the name is free". **No schema change:** no registry column, no sidecar field
  definition. New MRI sidecars' free-form `discovered` block gains `study_time` (template-defined, like `jrc_id`).
- **`mfb-rdm-docs/00_INDEX.md`**: Last Updated.
- **`tools/templates/instruments/mri_bruker.yaml`**: the regex's optional `study_time` group, the new `link_filename:`, and
  the header comments (the discovered-fields card, "what's pre-filled", the link-name block).
- **Docs:** `tools/INGEST_CLI.md` (operator-visible: the new default and "a taken name is refused"), `tools/OPERATOR_FAQ.md`,
  `tools/INDEX.md` (the new tool), `equipment/mri-platform/internal_mri_data_handling_workflow_notes.md` (the `<time code>`
  is the study start, now the link name's per-study part).
- **Deliberately unchanged:** `05_PROJECTS` (§3a: nothing bulk-repaired that a researcher removed, and the audit separates
  RESEARCHER-PRUNED for exactly that; §4.y point 3 already says collisions are reported and left alone, now enforced by
  the engine); `09_MODALITIES` and `paravision_metadata.EXPOSED_FIELDS` (`study_time` comes from the template's regex, so the
  09 ↔ code mirror is untouched); `06`/`08` (no schema change); the historical batch configs under `tools/configs/`.

## 9. Open points

1. ✅ **The MRI link-name form** (§3): confirmed by Ryan, 2026-10-05.
2. ✅ **The write window:** granted by the coordinator after the merge; phases A and B are in §11.
3. ✅ **The 389 microscopy acquisitions:** Ryan approved them, with the drives naming rule (`--include-file-primaries`); linked
   in phase A.
4. ✅ **The 7 polluted folders:** Ryan approved removing the foreign names only; done in phase B.
5. ⏸ **The operator GUI exe** (approved by Ryan: rebuild, smoke-test, redeploy): phase C, which starts only when the
   coordinator says so, after verifying A and B. Until then the deployed GUI still runs the **old linker (silent merge)** and
   the old MRI template, so a second same-day study ingested through the GUI can still merge; the audit tool finds that
   afterwards. The Project Manager exe also bundles the linker, but its import already refused a taken name
   (`raw_import.plan`), so only a race reaches the old behaviour there.
6. **The 12 empty-primary acquisitions in a collision** are not linked (§6). If the 2026-10-04 line ("never as empty rows")
   leads to retiring empty rows, they go with them.
7. **`provenance.has_entry_for_output` is case-sensitive** on a case-insensitive share (§5, 16 false rows). The linker
   closes the path for new links; making the check case-insensitive is a small, separate fix (LOW).
8. **`tools/drive_staging/check_link_collisions.py` and `verify_links_strict.py`** rebuild the old MRI name. That is right for
   the drives configs, which carry the old template; for new batches the engine's pre-flight replaces them.

## 10. Proposed wording for the record files

**`tasks/STATUS.md`** (a line in the current-work list):

> **Project link collisions: fixed and repaired (2026-10-05).** The linker refuses a taken project link name instead of
> silently merging, and the ingest checks the name before copying. MRI link names carry the study start time
> (`MRI_<sample>_<date>_<HHMM>_<exam>_<recons>`, confirmed by Ryan). The repair gave **589 acquisitions their own link**
> (200 MRI from the 2026-06-14 regen batches; 389 Cell Observer / LSM 900 from the 2026-06-15 best-guess ingests) and removed
> **1,900 foreign names from the 7 polluted MRI folders**; a re-audit by file id shows MISSING 0 and POLLUTED 0. **Next:**
> the operator GUI exe rebuild and redeploy (phase C, approved by Ryan), after which GUI ingests stop merging too. Review:
> `tasks/link_collision_fix_review.md`.

**`CHANGELOG.md`** (new row at the top):

> | 2026-10-05 | R. Tasseff | **A project link name is never merged into any more; MRI link names gain the study time;
> the old merges are repaired.** **Code** (merged, 70c5023): `linker.create_hardlink` refuses a name held by anything that
> is not exactly the acquisition's own files (`LinkCollisionError`, deliberately not an `OSError`, so it is never queued for a
> relink); the ingest checks the name before copying (new Step 5.5, also in `--dry-run`), so a taken name fails the case with
> nothing copied or registered; every link-making tool reports a taken name as a collision. **Convention** (confirmed by
> Ryan): the MRI default `link_filename` adds `${discovered.study_time}` (HHMM of the study folder's timestamp), so two
> studies of one animal on one day no longer share names. Forward only. **Audit** (every project, by file id): 589
> acquisitions without their own link (200 MRI, all from the 2026-06-14 regen batches, reconciling with stream F's 209; 389
> Cell Observer / LSM 900 from the 2026-06-15 best-guess ingests, where repeated file names were skipped silently) and 7
> polluted MRI folders. **Repair** (Ryan approved all of it): 589 links added (MRI under the new name, microscopy as
> `<INSTR>_<stem>_<YYYYMMDD><ext>`), 0 errors, verified file by file; 1,900 foreign names removed from the 7 folders, each now
> exactly its own acquisition's files; backups first, provenance for every link and removal. Re-audit: MISSING 0, POLLUTED 0.
> **Found:** provenance idempotence is case-sensitive on a case-insensitive share, so 16 skipped acquisitions carried a
> provenance row for a link that was never made. 35 of 35 test suites pass. |

**`tasks/BACKLOG.md`**, the 🔺 HIGH item "a second acquisition with an existing link name silently gets the first one's
files (2026-10-04)", can close, with one follow-up kept:

- [x] **Code:** `create_hardlink` refuses a taken name (`LinkCollisionError`); the ingest checks before copying; tests.
- [x] **Template:** the MRI `link_filename` gains `${discovered.study_time}` (form confirmed by Ryan, 2026-10-05).
- [x] **Audit:** `tools/repair_link_collisions.py audit`: 589 MISSING (200 MRI + 389 microscopy), 7 POLLUTED, 2 pruned.
- [x] **Repair:** 589 links added; 1,900 foreign names removed from the 7 polluted folders. MISSING 0, POLLUTED 0.
- [ ] **Redeploy:** the operator GUI exe (phase C, approved by Ryan), which still runs the old linker and template.
- [ ] (LOW) `provenance.has_entry_for_output`: compare `output_path` case-insensitively.

And the LOW item **"MRI project link-name collisions — same-animal/same-day multi-session (2026-06-14)"** is resolved by this
work: its two `0219` pairs (`ACQ-20220124-MRI-006` and `-008`) now have their own links.

## 11. The write window (2026-10-05): phases A and B

The coordinator granted the window after the merge (70c5023), for A and B only; I was the only production writer.

### Phase A — the repair (589 links)

- **The plan, checked before writing:** a fresh dry run matched the reviewed plan row for row (589 rows, all `create`, the
  same names), so production had not moved since the review.
- **Run from `main`'s code** (70c5023; my phase-B edits were stashed for the run):
  `repair --include-file-primaries --execute --by "Data Office (link-collision repair 2026-10-05)"`, 14:22 to 14:33.
- **Backup first:** `C:\Users\rtasseff\temp\gjesus3_link_repair_backup_20261005_142901\` holds the `provenance.csv` and
  `index.html` of the 13 touched projects, each verified by SHA-256 before any write.
- **Result: 589 links created, 0 errors.** 200 MRI (`0721` 145, `1022` 53, `0219` 2; 21,977 files) under the §3 name, and 389
  Cell Observer / LSM 900 (360 dated names, 29 ACQ-ID names). The tool checked each link as exactly its files right after
  making it, appended one provenance row per link, and regenerated the 13 projects' `index.html` (rc 0 for each).
- **Independent verification** (plain `os.path.samefile`, file by file, not the tool's code): all 589 links, 22,366 files.
  Every link holds exactly its acquisition's raw files (the same names, the same files, nothing else), every provenance row
  is present and correct, and every touched `index.html` was rewritten after the backup. **0 problems.**
- **Re-audit** (`main`'s code, every project, by file id): **MISSING 0** (was 589), OK **19,063** (was 18,474: + 589),
  POLLUTED 7 (unchanged, as expected), RESEARCHER-PRUNED 2, EMPTY-PRIMARY 319, CLOSED-PROJECT 1,166. No registry file was
  written: their modification times all predate the run.

### Phase B — the 7 polluted folders

- **The removal mode** (`repair_link_collisions.py prune-foreign`, branch commit 6dc3e98, tests in
  `test_repair_link_collisions.py`, 35/35 suites). A name is removed only if its file belongs to ANOTHER live acquisition
  **and** the very same file (`os.path.samefile`) is also in `/raw/` and in that acquisition's own complete link. It never
  removes an owner's file, a file of no acquisition, or the last name of anything. Every precondition is re-checked from disk
  right before each removal.
- **Provenance:** one write-ahead event per (folder, foreign acquisition): `output_path` the folder, `file_type`
  `hardlink-removed`, `input_refs` the acquisition whose names were removed (the retire tool's convention). That makes 7 events
  in all, not one per file; the per-name record is the manifest below. `reopen_project` now ignores `hardlink-removed` rows when
  it collects link names to restore, so these events never send it to a folder that is not the acquisition's.
- **Dry run first:** 1,900 names to remove, 0 to keep. Per folder this is exactly the audit's foreign count, every name belongs
  to the one listed partner, and that partner's own link is its phase-A link.
- **Run:** `prune-foreign --execute --by "Data Office (link-collision cleanup 2026-10-05)"`, 14:41 to 14:45. **Backup
  first:** `C:\Users\rtasseff\temp\gjesus3_link_prune_backup_20261005_144502\` holds `PROJ-0010` and `PROJ-0019`'s
  `provenance.csv` and `index.html`, plus `prune_manifest.csv` (every name removed, with its file id, owner and own link: the
  record needed to reverse it), all SHA-256 verified.
- **Result: 1,900 names removed, 0 errors; 7 of 7 folders now exactly their own acquisition's files** (`inspect_link_target`
  → `own`); `index.html` regenerated for both projects (rc 0).

| Folder | Its own acquisition | Names removed (of) | Files left |
|---|---|---:|---:|
| `0721` `MRI_m201_0721_20240422_10_1` | `ACQ-20240422-MRI-001` | 155 (`-017`) | 5 |
| `0721` `MRI_m236_0721_20250306_4_1` | `ACQ-20250306-MRI-022` | 308 (`-030`) | 112 |
| `0721` `MRI_m262_0721_20250602_3_1` | `ACQ-20250602-MRI-007` | 102 (`-024`) | 10 |
| `0721` `MRI_m262_0721_20250602_4_1` | `ACQ-20250602-MRI-008` | 308 (`-025`) | 112 |
| `0721` `MRI_m268_0721_20250612_3_1` | `ACQ-20250612-MRI-023` | 308 (`-030`) | 112 |
| `0721` `MRI_m289_0721_20251117_4_1` | `ACQ-20251117-MRI-016` | 308 (`-029`) | 112 |
| `1022` `MRI_m113_1022_20251217_2_1` | `ACQ-20251217-MRI-008` | 411 (`-021`) | 9 |

- **Independent verification** (plain `os.stat` / `os.path.samefile`): each of the 7 folders holds exactly its own
  acquisition's raw files (the same names, the same files, nothing else); every one of the 1,900 removed names is gone, and its
  file is still in `/raw/` and in its own acquisition's link (the same file, the same id); one event per folder. **0 problems.**
  No registry file was written.
- **Final re-audit** (every project, by file id): **POLLUTED 0, MISSING 0**, OK **19,070** (= 18,474 + 589 + 7), no link
  entry holds more than one acquisition's files; RESEARCHER-PRUNED 2, EMPTY-PRIMARY 319 and CLOSED-PROJECT 1,166 unchanged.

Records in [`link_collision_audit/`](link_collision_audit/): `executed_repair_plan.csv` (A), `after_repair_link_audit_summary.txt`
(after A), `link_prune_plan_dry_run.csv` and `executed_prune_manifest.csv` (B), `final_link_audit_summary.txt` (after B).
