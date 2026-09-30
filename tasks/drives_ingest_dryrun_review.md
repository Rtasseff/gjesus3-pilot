# Historical microscopy drives — the `.czi` ingest: dry run, rehearsal and review package

**Status:** ✅ **Gate PASSED 2026-09-30 with required changes R1–R7, all done — see [Gate changes](#gate-changes-2026-09-30).** §1–§10 are the pre-gate dry run, kept as the record; **the current plan is the one in Gate changes.**
**Branch:** `feat/drives-microscopy-ingest` · **Date:** 2026-09-30 · **Procedure:** [`drives_microscopy_ingest_runbook.md`](drives_microscopy_ingest_runbook.md)

## Summary (10 lines)

1. **9,090 acquisitions, 4,022 GB are ready:** `CELL` 8,333 (3,990 GB) · `LSM9` 397 · `ZWSI` 22 · `XMIC` 338, in 16 batches (≤ 400 GB each).
2. **The engine's own dry-run resolution matches the per-file plan on all 9,090 files: checks 1–7 PASS, 0 mismatches** (§5).
3. **Exactly one project is created, `AE-biomaGUNE-0118`** (141 files, subjects held). 12 existing projects receive 3,640 files; **5,309 files get a blank project** (§6 = Ryan's list).
4. **Subjects: 3,477 rows / 344 animals**, all Confirmed, all re-resolved in the facility DB to themselves; none on (A), (C) or no-claim rows.
5. **Tie-break implemented and re-run:** (C) 180 → 131; the 49 movers are exactly the approved readings (29 `.czi` enter this ingest). One guard added: the rule may confirm, never overrule, the file's own nearest claim (§2).
6. **Rehearsal on a scratch NAS (4 batches, 898 acquisitions): PASS**, and the re-run added **0** rows (§7).
7. **The dry run caught one silent skip:** a `.czi` whose name starts with `.` is invisible to the engine's glob. Excluded and listed (§3).
8. **Gate item G1: two target projects are CLOSED** (`0219`, `1019`). *Corrected at the gate:* their folders were not gone; the close-out left the status and removed the older links. Both are reopened with `tools/reopen_project.py` before B15/B16.
9. **New code/doc:** `XMIC` code; `auto_discover.case_table` (per-file values, default off); `Project-NNNN` documented; tools `ingest_plan/check/verify.py`.
10. **Runtime ≈ 45 h** of transfer over SMB (2× bytes at ~60 MB/s), in evening/weekend windows (§8).


---

## Gate changes (2026-09-30)

The coordinator's gate passed the plan with required changes R1–R7 (`GATE_2026-09-30.md`). All are
done; **every check passes** on the new plan (now 9 checks: 3b and 3c are new).

**R1–R4 — the same acquisition under different bytes.** ZEN rewrites a `.czi` when display settings, a
scale bar or pyramids are saved, so its sha256 changes and content dedup lets it through. The key
**(instrument, acquisition timestamp to the second, lower-cased filename)** identifies the acquisition.

| Rule | Gate expected | Found | Action |
|---|---|---|---|
| **R1** re-save of a production acquisition | 206 files, 3.8 GB (`CELL` 200, `LSM9` 6); 202 same size, 4 differing by up to 152 MB | **206 files, 3.8 GB** (`CELL` 200, `LSM9` 6). On the production primaries' **exact** bytes: **204** within 0.15 MB, **2** differ (0.5 MB and 5.1 MB). The gate's 202 / 4 split came from the registry's rounded `file_size_mb` | 205 dropped (`resave-of-production:<ACQ-ID>` in `excluded.csv`); **1 held** (below) |
| **R2** re-saves within the plan | 84 groups, 91 extra files, ~147 GB; 21 same size; 29 with copies in different projects | 84 groups: **19 were wholly re-saves of production** (gone by R1); **65 collapse** to one canonical each (**72 files, 149.7 GB** dropped, their paths in `other_copies`). The 29 mixed a project with blank, and rule 1 kept the project. **0 groups claim two different real projects.** | `resave-within-plan` in `excluded.csv` |
| **R3** same instrument + timestamp as a production acquisition, other name | 22 (18 `ZWSI`, 4 `CELL`) | **22**: the 18 `…_ROI lobulo N.czi` (crops of `ACQ-20260416-ZWSI-*`, folder `Prueba jpeg`) and 4 `CELL` — `COL-PBS-20x-SCALE.czi`, `24h_HepG2_LP-IONP_20X_7_Scale.czi`, `…_Scale-sinrojo.czi`, `Ctrl-_HepG2_LP-IONP_20X_2-Scale-50um.czi` — whose **pixels are identical** to their production parent: scale-bar annotation re-saves, not separate scenes | all 22 out of `/raw/`; **`_analysis\ingest\nonraw_derived.csv`** lists each with its parent ACQ-ID(s) and destination project, for the non-raw session |
| **R4** distinct files sharing instrument + full timestamp | ~226 groups | **247 groups, 819 files** (≥ 2 differently named files after R1–R3; 253 before them) | kept; case-table columns `drv_acq_group` / `drv_acq_group_n` and a `notes` clause |

**Inspected by hand** (tile-by-tile pixel comparison with `czifile`; recorded in `ingest_plan.py`
`RESAVE_DECISIONS` / `DERIVED_DECISIONS`, so a new unexplained case stops the plan):

- `4h_HepG2_LP-IONP_20X_6.czi` vs `ACQ-20230726-CELL-037`: identical pixels (3×520×692); production is
  0.5 MB *larger* (extra metadata). A re-save: dropped.
- ⚠️ **`ID59_1022_tumor_CD206.czi` vs `ACQ-20251031-CELL-003`: the PRODUCTION copy is truncated.** It is
  5.1 MB short and its last tile (108 of 108) cannot be read ("failed to read 9,348,144 bytes, got
  4,267,924"). The drive copy (`D2\CELL OBSERVER 2\AINHIZE\1022\CD206\def\`) is complete, and its other
  107 tiles are identical. It is the same acquisition, so it must not become a second ACQ-ID: **held**
  (`production-copy-truncated` in `excluded.csv`) and **reported as a production repair** — replace the
  primary of `ACQ-20251031-CELL-003` from the drive copy (the recovery pattern; a separate, approved
  write). **Done 2026-10-01 (Ryan's approval): repaired in place — see §11.** Most likely the production file was copied while ZEN was still writing it.

**R5 — before → after:**

| Instrument | Files before | GB before | Files after | GB after |
|---|---:|---:|---:|---:|
| `CELL` | 8,333 | 3,990.0 | **8,061** | **3,836.6** |
| `LSM9` | 397 | 5.3 | **387** | **5.2** |
| `ZWSI` | 22 | 22.1 | **4** | **3.0** |
| `XMIC` | 338 | 4.3 | 338 | 4.3 |
| **Total** | 9,090 | 4,021.7 | **8,790** | **3,849.1** |

| Batch | Before (files / GB) | After (files / GB) | After: projects |
|---|---|---|---|
| B01 | 338 / 4.3 | 338 / 4.3 | — (`XMIC`) |
| B02 | 141 / 6.8 | 140 / 6.8 | `0118` (created) |
| B03 | 397 / 5.3 | 387 / 5.2 | 1123 |
| B04 | 22 / 22.1 | 4 / 3.0 | 0424 |
| B05 | 2,187 / 216.6 | 2,023 / 129.3 | — |
| B06 `CELL` 1321, 1422 | 2026-09-30 16:29–18:19 | 235 / 235 | 6,490 s | all PASS | 10,314 | 0 | `…_drives_B06` (registry 19,329 → 19,564; projects unchanged at 59; WARNs only the is_control / region sentinels) |
| B07 `CELL` no project | 2026-09-30 18:28–21:18 | 1,519 / 1,519 | 10,193 s | all PASS | 10,314 | 0 | `…_drives_B07` (registry 19,564 → 21,083; projects unchanged at 59; 0 WARN lines. The harness reported the task "killed" at its 2 h background limit mid-run; the detached python and wrapper kept running and completed, every check passed) |
| B06 | 274 / 327.6 | 235 / 257.0 | 1321, 1422 |
| B07 | 1,584 / 393.4 | 1,519 / 393.2 | — |
| B08 | 1,232 / 396.9 | 1,050 / 398.1 | 0721, 1022, 1123 |
| B09 | 142 / 397.2 | 221 / 398.8 | 1321 |
| B10 | 149 / 398.2 | 147 / 398.9 | 1123 |
| B11 | 940 / 398.6 | 153 / 398.9 | 1123, 1321 |
| B12 | 816 / 398.9 | 138 / 399.1 | 1321 |
| B13 | 260 / 399.5 | 1,235 / 399.7 | 0420 0423 0424 0522 0619 0721 |
| B14 | 209 / 399.7 | 801 / 400.0 | — |
| B15 | 260 / 28.1 | 260 / 28.1 | 1019 (reopened first) |
| B16 | 139 / 228.7 | 139 / 228.7 | 0219 (reopened first) |

From B05 on, the batches were **re-cut** (the 400 GB cut points moved), so B05–B14 now hold different
files. The farm was pruned (4,041 links moved or dropped, each first checked to be a second link to its
staged file) and rebuilt: 8,790 links, 0 errors, 0 stray.

- **Projects:** still exactly one created (`0118`, 140 files). 12 existing: `0522` 719 · `1022` 664 ·
  `1123` 498 · `1321` 478 · `0721` 437 · `1019` 260 · `1422` 140 · `0219` 139 · `0424` 105 · `0420` 82 ·
  `0619` 37 · `0423` 36. **Blank project: 5,055** (Ryan's list). Subjects: 3,432 rows, 337 animals, all
  re-resolved in the facility DB.
- **Checks** (`ingest_check.py`, all 16 configs, the engine's own resolution): **1, 2, 3, 3b, 3c, 4, 5, 6,
  7 all PASS**; 0 per-file mismatches over 8,790 files, now including `drv_acq_group` and the notes.
  3b: no planned file is a re-save of a production acquisition or of another planned file. 3c: no planned
  file shares instrument + timestamp with a production acquisition.
- **Frozen plan.** The plan and configs are not regenerated once production starts: a re-plan would re-cut
  the batches and reuse config names for other files. Instead `ingest_check.py --batch Bxx` checks one
  batch against the live registry and a fresh hash index — step 0 of each batch in the runbook.

**R6 — `tools/reopen_project.py`.** Proven on a scratch subset of `0219` (63 acquisitions, their real
`/raw/` folders, 41 links present): the dry run wrote nothing (a hash of every file matched before and
after); the run backed up and verified, restored `_project.yaml` from the close-out backup (migrated
`short_name` → `name`), created the 3 missing subfolders, recreated **19** links with provenance rows,
reported **3** collisions, set `active` and regenerated `index.html`; **a re-run changed nothing.**
Production dry runs (read-only):

| | `AE-biomaGUNE-0219` (PROJ-0017) | `AE-biomaGUNE-1019` (PROJ-0006) |
|---|---|---|
| acquisitions | 335 (10 without a date) | 479 (1 without a date) |
| links present / to create | 251 / **80** | 58 / **421** |
| collisions (reported, left alone) | **4.** Animal m23 had **two MRI sessions on 2022-01-24** (`…083002…`, `…092931…`) whose link names coincide, so `ACQ-20220124-MRI-006/007/008` never had links; `ACQ-20260613-MRI-015` is a no-date placeholder named after its ingest date | 0 |
| registry row | `status` closed → active; `notes` + "Reopened …"; dates unchanged (2022-01-24 … 2022-06-22) | `status` → active; **`last_activity` 2022-09-28 → 2026-09-29**; `notes` + "Reopened …" |
| other | `_project.yaml` restored; no subfolder missing; **no deletion** | the same |

Both show only the gate's (a)–(c). **G1 premise corrected:** the folders were never gone. `0219` has 251
links (the NI pull and later ingests re-created `raw_linked\`), and `1019` has 58, including the 18
AxioScan sections an operator ingested on 2026-09-29. What the close-out left behind was a wrong status
and the loss of the older links. Procedure: `05_PROJECTS §4.y`, plus a `tools/INDEX.md` row.

**R7:** the Charité (`XMIC`) files run **2024-09-27 → 2024-11-07** (fixed in `09_MODALITIES §1.6`). The
hidden dot-file stays listed for a later one-off.

**R5 rehearsal re-run:** see §7b.

---

## 1. What was built (commits on the branch)

| Commit | What |
|---|---|
| `project_claims: approved DB-date tie-break …` | §2 below |
| `ingest: XMIC instrument code + default-off auto_discover.case_table …` | `tools/ingest/config.py` + `tools/ingest/test_case_table.py` (19 checks) |
| `docs: XMIC …, case_table …, Project-NNNN …` | 03 §3.2, 09 §1.6 (new), 10 §2.1.3, 05 §2a.7 (new), `INGEST_CLI.md`, `GLOSSARY.md`, `equipment/INDEX.md`, 00 |
| `drive_staging: per-file ingest plan, hard-link farm, dry-run review and post-batch verifier` | `ingest_plan.py`, `ingest_check.py`, `ingest_verify.py`, `tools/test_drives_ingest_plan.py` (18 checks) |
| `drives ingest: exclude the one hidden dot-file …; generated batch configs B01-B16` | `tools/configs/drives_2026-09/` — 16 YAML + 16 case tables + `batches.csv` (**committed**: every registry row's `ingest_config` must resolve to what produced it, and the YAML alone no longer says which file got which value) |

All pre-existing suites that touch `config.py` still pass (`test_user_tables`, `test_registry_fields`,
`test_review_fixes_2026_06`, `test_project_naming`, `test_wsl_ingest_fixes`, `operator/test_mri_project_name`).

### The mechanism, and why

- **Per-file values → `auto_discover.case_table`** (handoff §4.4, option "a minimal per-case override").
  A CSV keyed on `original_name`; every other column becomes `discovered.<column>`, used by
  `registry:`, `operator:`, `subject_lookup:` and `link_filename:`. **Why not the template's own
  parse:** the claims' subject ids come from a whole-path analysis with DB cross-checks and conflict
  rules; a filename regex could only approximate it, and a well-formed wrong subject is the costly
  error (PROJ-0056). **Why not blank + back-fill:** it doubles the production writes and leaves a
  window where rows are incomplete. The table is exact by construction, and test 2 proves the engine
  reads it back file by file. Default off; a file with no row aborts the batch.
- **Hard-link farm** `D:\projects\gjesus3\staging\_farm\B01…B16\<drive-label>\<source path>` (zero
  space, same volume), so `original_name` = `drive1_FRIO-X6/Cell observer/AINHIZE/1123/…/x.czi`:
  traceable, re-homeable, and a stable dedup key on re-run.
- **Batches** = instrument × project class, cut at 400 GB. Researcher/operator/subject no longer need
  their own batches (they are per file). `0118` has its own batch (the only `auto_create_projects: true`);
  the closed-project files have their own (G1).

---

## 2. The DB-date tie-break (`project_claims.py`)

Implemented as approved: for a **histology** file (`czi lsm tif tiff png jpg jpeg bmp`) whose animal is
in two candidate protocols and which the existing rules (procedure within 3 days; only one animal born)
do not separate, the candidate whose animal had **`Organ sampling` or `Perfusion` on or before the file
date** wins. Not applied to in-vivo data (there a prior perfusion is evidence *against* an animal —
it is how the four `jrc220622_m*_1321` studies in `Cursosurf_0219` were decided). Procedure dates before
1990 are ignored (the DB holds `0023-08-07`). A disagreement with the born-by-date rule stays (C).

**One guard beyond the handoff — please confirm.** The first re-run also moved
`AINHIZE\1123\Biodistribución 1123 FeMn\PB\Liver\1321 controles\ID101_1321_PB_liver_20x.czi` to
**1123**, against both its filename and its folder, because 1123's animal 101 was sampled
(2025-04-01) and 1321's animal 101 has no sampling logged. But **1321's animals 98–101 have no
sampling logged at all** while their liver slides exist on the drive, so a *missing* terminal
procedure is not evidence. The rule now **only confirms the file's nearest claim, never overrules
it**. That leaves exactly the approved movers and keeps 98–101 in (C), as the handoff expected.

| | Before | After |
|---|---:|---:|
| (C) files | 180 | **131** |
| Movers (all C → Confirmed) | | **49**: animals 61/62/70 → `1321` (27 `.czi`); 19/22 → `0219` (8 `.czi` + 12 `.tif`); 75H/76H → `0619` (2 `.czi`) |
| Stay (C) | | 63–65, 98–101 (both sampled, or the rule would overrule the name), 26 (neither sampled), `ID137`, 187, 202–209, `ID238`, `2503`, the paperwork |

The analysis's "about 68" counted the whole 1123/1321 group; the exact number is 49. **`.czi` that
actually enter this ingest: 29** (21 → `1321`, 8 → `0219`); the other 8 movers' bytes are already in
production, and the 12 `.tif` are out of scope. Archive-member claims: unchanged (0 of 100,982).

---

## 3. Scope and reconciliation (check 1, re-derived from the catalog)

Catalog refreshed 2026-09-30 08:40–08:46 (`production` + `assemble`); registry 16,437 rows, unchanged
since 2026-09-29 15:20, so `files.csv` came out byte-for-byte the same.

| Instrument | Distinct `czi-raw` contents (loose + member) | − in production | − on `S:\goptical` | − hidden dot-file | **= plan** | of which archive-only | GB |
|---|---:|---:|---:|---:|---:|---:|---:|
| `CELL` | 8,785 | 451 | — | 1 | **8,333** ¹ | 341 | 3,990.0 |
| `LSM9` | 642 | 245 | — | — | **397** | 6 | 5.3 |
| `ZWSI` | 716 | 680 | 14 | — | **22** | 0 | 22.1 |
| `XMIC` (`EXTERNAL:AxioImagerZ2`) | 338 | 0 | — | — | **338** | 0 | 4.3 |
| **Total** | | | | | **9,090** | 347 | **4,022** |

¹ Loose distinct new 7,993 (= the catalog's 8,444 − 451) − 1 dot-file + 341 archive-only (`Drive zuri
170823.zip` 253, `Haizpea_2020-2022.7z` 82, `Infartos Ruben_PR.zip` 6).

- **One canonical copy per sha256** (handoff §4.2 rules 1–6). 1,243 contents have more than one copy;
  every other copy's path is kept (`other_copies`) for the provenance. `dup_groups.csv` agrees with
  the grouping exactly (0 mismatches). **No content has copies claiming different projects** (0
  conflicts), and none whose copies name different subjects. One refinement: within rule 2, a loose
  backup copy beats an archive member (avoids an extraction); it changed **0** picks.
- **The 14 `ZWSI` on `S:\goptical`** (`2026_01_12__14_32__0033_29H.czi` … `15_51__0048_34L_ES.czi`) match
  by name, size **and sha256**: they belong to the AxioScan route, which has not ingested them yet.
  The other **22 are not on S: under any name or size** and are included (G2).
- **Archive-only extraction:** only the 347 needed members, one archive at a time, into
  `D:\projects\gjesus3\staging\_extract\`; every one re-hashed against the catalog: **347 / 0 bad**.
  `LEONE.zip` and `Cardiac MRI.zip` are refused by the tool.
- **Farm:** 9,090 links, 0 errors, 0 stray files; every loose canonical copy's manifest sha256 and size
  equal the catalog's (8,743 / 0 bad).
- **Excluded, listed:** `Cell observer\Laura\Cell observer\Interaccion-LS-SPN\.LS-SPN-20x-8.czi`
  (2024-01-25, 61 MB, no other copy). Python's `glob` never matches a leading-dot name, so it would
  have sat in the farm and **silently not ingested** — the dry run found it (and the `case_table`'s
  "row matched no file" WARN flagged it too). Making the engine see hidden files would also pull
  macOS `._*` files into other ingests, so it is left for a one-off (rename in a farm copy, or a
  single-case config).

---

## 4. The per-file rules as implemented

| Field | Rule (handoff §2) | Result |
|---|---|---|
| `instrument` | the catalog fingerprint; `EXTERNAL:AxioImagerZ2` → `XMIC` | 0 mismatches |
| project | Confirmed / (A) → the claim's `AE-biomaGUNE-NNNN`; (C) / no-claim → blank | 12 existing + `0118` (§6) |
| `researcher` / `operator` | innermost person folder as written; **under `Cell observer\AINHIZE`, `…\Marta` (D1) and `CELL OBSERVER 2\AINHIZE`, `…\Marta` (D2) the folder is the operator**, the researcher is the inner person or blank; elsewhere the operator is blank. `ZWSI`: the filename's initials (`AUA`), falling back to the folder rule for the 4 auto-named files (`Marta`) | CELL operators: AINHIZE 3,643 · Marta 908 · blank 3,782 |
| subject id | the claims tables' id, Confirmed only; blank on `0118`, (C), no-claim | 3,477 rows, 344 animals |
| `acquisition_datetime` | the `.czi`'s own | engine = catalog on all 9,090; 0 blank; years 2020–2026 |
| `data_source` | `internal`; `XMIC` → **`collaborator:Charite`** (G5) | |
| `instrument_model` | the `.czi`'s microscope name (`Axio Observer.Z1 / 7`, `Axioscan 7`); `XMIC` → `Axio Imager.Z2` | engine = catalog stand wherever the catalog has one |
| `original_name` | `<drive-label>/<source path>` (members: `<drive-label>/<archive path>/<member path>`) | by construction of the farm |
| `sample_id` | the filename (the best-guess precedent); `ZWSI`: `<project>_<sample>` from the MFB name | |
| `sample_type` | **`tissue`** where a subject id is recorded, and all `ZWSI`; **blank** otherwise (G4) | tissue 3,481 |
| link name | `<INST>_<filename>`; if that name is already taken in the project's `raw_linked\` (production listing) or by another new file: `<INST>_<stem>_<YYYYMMDD><ext>`, then `…_<sha8>` | 45 renamed |
| `notes` | "Historical drive ingest 2026 (<label>); … Claim: <verdict>" — (C) rows name the claimed code | |

The case table's `drv_*` columns also land in each sidecar's `discovered` block, including
`drv_sha256` and `drv_claim` — the per-acquisition record of why it got its values.

---

## 5. The dry run (checks 1–7)

`python tools/drive_staging/ingest_check.py` runs **`config.expand_batch` — exactly what
`ingest_raw.py --dry-run` runs before its early return** — on all 16 configs against production
(read-only), reading every `.czi`'s own metadata, and compares each resolved case with the plan.
Report: `D:\projects\gjesus3\staging\_analysis\ingest\check_report.json` + `check_cases.csv`.

| # | Check | Result |
|---|---|---|
| 1 | Reconciliation: each content in exactly one batch; engine cases = plan rows; counts/GB re-derived from the catalog (§3); nothing out of scope | **PASS** — 9,090 = 9,090; 0 engine SKIPs, 0 extraction failures |
| 2 | Per file: instrument, project, researcher, operator, subject, `acquisition_datetime`, `data_source`, `original_name` (+ model, sample, link name) | **PASS — 0 mismatches / 9,090** |
| 3 | No in-scope sha256 in the fresh production index; index newer than the registry | **PASS** (index 2026-09-30 08:43; registry 2026-09-29 15:20; the 464 registry rows absent from the index are MRI placeholders with `file_count` 0) |
| 4 | No blank date; no ACQ-ID dated today | **PASS** |
| 5 | Exactly one project created: `AE-biomaGUNE-0118`; all others exist | **PASS** — table below |
| 6 | Subjects only on Confirmed rows; each re-resolves in its own protocol | **PASS** — 344 / 344 re-resolve to themselves (fresh connection) |
| 7 | `XMIC`: 338 rows, `Axio Imager.Z2`, `collaborator:Charite` | **PASS** |

**Projects (check 5):**

| Project | Registry | Status | Files |
|---|---|---|---:|
| `AE-biomaGUNE-0118` | **NEW** (B02) | — | 141 |
| `AE-biomaGUNE-0522` | PROJ-0011 | active | 719 |
| `AE-biomaGUNE-1022` | PROJ-0019 | active | 665 |
| `AE-biomaGUNE-1123` | PROJ-0014 | active | 516 |
| `AE-biomaGUNE-1321` | PROJ-0018 | active | 501 |
| `AE-biomaGUNE-0721` | PROJ-0010 | active | 440 |
| `AE-biomaGUNE-1019` | PROJ-0006 | **closed** (G1) | 260 |
| `AE-biomaGUNE-1422` | PROJ-0013 | active | 140 |
| `AE-biomaGUNE-0219` | PROJ-0017 | **closed** (G1) | 139 |
| `AE-biomaGUNE-0424` | PROJ-0002 | active | 105 |
| `AE-biomaGUNE-0420` | PROJ-0012 | active | 82 |
| `AE-biomaGUNE-0619` | PROJ-0004 | active | 37 |
| `AE-biomaGUNE-0423` | PROJ-0020 | active | 36 |

The real CLI (`ingest_raw.py --dry-run`, B02 against J:) also ran clean: 141 / 141, 0 failed. (Its
printed ACQ-IDs repeat — a dry run does not reserve ids; the real run allocates under the lock.)

---

## 6. Ryan's list (blank project) — preview

5,309 files will be ingested with a blank project. After the run, the list is every such new ACQ-ID with
the project its path claimed (runbook §6). By verdict:

| | Files | Path claimed |
|---|---:|---|
| (C) | 103 | `0522` 31 (`ID137`, IDs 187/202–209) · `2503` 30 (a date folder) · `1321` 25 (animals 63–65, 98–101 in 1123's tree) · `0721` 11 (`ID238`) · `0219` 6 (animal 26) |
| no claim, `CELL` | 4,484 | nothing (largest groups: `Proyectos_Laboratorio_Laura\Lung-surfactant`, `Cell observer\Laura`, `Lucia-Lorena Garayoa`, `LYDIA`, `Drive zuri`) |
| no claim, `LSM9` | 384 | nothing (`Former students\Zuriñe` 364 …) |
| no claim, `XMIC` | 338 | nothing (`Ferritas\Charité`) |

---

## 7. The scratch rehearsal

`python tools/drive_staging/ingest_plan.py scratch --batch B01 --batch B02 --batch B03 --batch B04`
built `D:\projects\gjesus3\scratch_nas\` from copies of production's registries (read-only on J:), with
the two existing target projects' folders and a **zero-byte stand-in for every link name production
already uses** in them (928 in `0424`, 865 in `1123`), so a name collision would be real and caught.
Then the real write path, `ingest_raw.py -c drives_Bxx.yaml --nas-root D:\projects\gjesus3\scratch_nas
--refresh-index projects`, for four batches, and the same four again.

| Batch | What it exercises | Result | Time (local disk) | Re-run |
|---|---|---|---:|---|
| B01 | `XMIC` (new code), 338 files, no project | 338 / 0 failed, 0 WARN | 89 s | **Total: 0** |
| B02 | the **only project created** (`AE-biomaGUNE-0118`), 141 links, subjects held | 141 / 0 failed, 0 WARN | 75 s | **Total: 0** |
| B03 | `LSM9`, 6 archive-extracted members, 13 subjects + links into `1123` | 397 / 0 failed | 113 s | **Total: 0** |
| B04 | `ZWSI`, initials operator, 18 subjects, links into `0424` + `1123` next to 1,793 stand-ins | 22 / 0 failed | 280 s (22 GB) | **Total: 0** |

**Checked after the run** (`ingest_verify.py --nas-root <scratch> --batch B01 … B04`): **all PASS** —
898 rows = the 898 planned, each once; every field as planned; every `checksums.json` holds exactly
the plan's sha256 (= the staging manifest's) and the primary has the planned size; every sidecar names
its acquisition and carries `discovered.drv_sha256`; every planned project link exists and **is the raw
primary** (same file, not a stand-in); no duplicate `acq_id` / `original_name` in the registry.

- `AE-biomaGUNE-0118` was created as the next id (PROJ-0060 in scratch) with the full skeleton
  (`_project.yaml`, `raw_linked\` with 141 links, `working\`, `outputs\`, `metadata\`,
  `provenance.csv`, `index.html`), owner `Data-Office`, the description and notes from the config.
  `registry_projects.csv` +1, and only that.
- Subjects: every recorded subject's sidecar block reads `source: animal-facility-db` (e.g.
  `117-AE-biomaGUNE-1123`: *Mus musculus*, M, born 2025-03-06, `P11W` at acquisition);
  `registry_subjects.csv` +3 new animals (the rest already existed); `pending_subject_metadata.csv`
  unchanged (**0 DB misses**).
- Registry `+898`, `ingest_manifest.csv` `+898`; the validator's error count is **unchanged** (26,751 on
  scratch = the 10,314 known MRI placeholders + one "acquisition folder not found" per production row,
  because the scratch holds no `/raw/`), and no new error class.
- The per-project Finder index was regenerated for each touched project (`0060`, `0014`, `0002`).
- WARNs were only the documented non-blocking sentinels: `condition.is_control` null and `anatomy.region`
  empty on `tissue` rows (35 each), and 4 × "could not parse an animal code from ''" on the auto-named
  `0424` `ZWSI` files, which are `tissue` without a subject id (`source: unknown`).
- **Idempotency:** the second run of every batch discovered all its files and skipped each as
  "already in registry" — **0 rows added**.
- Per-acquisition overhead on local disk: 0.2–0.3 s (B01: 338 in 89 s). Byte throughput on one
  spinning disk (hash + copy + verify): ~80 MB/s (B04).

### 7b. Rehearsal re-run after the gate (R5)

B02–B04 changed (B01's 338 files did not; re-run anyway). A fresh scratch root
(`D:\projects\gjesus3\scratch_nas_gate\`, same construction as §7), the same four batches, then again:

| Batch | Result | Time | Re-run |
|---|---|---:|---|
| B01 `XMIC` | 338 / 0 failed | 86 s | Total: 0 |
| B02 `0118` (created) | 140 / 0 failed | 76 s | Total: 0 |
| B03 `LSM9` | 387 / 0 failed | 127 s | Total: 0 |
| B04 `ZWSI` | 4 / 0 failed | 45 s | Total: 0 |
| B05 `CELL` no project | 2026-09-30 15:06–16:20 | 2,023 / 2,023 | 4,054 s | all PASS | 10,314 | 0 | `…_drives_B05` (registry 17,306 → 19,329; projects unchanged at 59; 0 WARN lines) |

`ingest_verify`: **all PASS** (869 rows = 869 planned; fields, checksums = manifest sha256, sidecars, links
are the raw primary, no duplicates). Validator count unchanged (26,751 on scratch, as in §7). 53 of the
869 carry the R4 flag: `discovered.drv_acq_group` / `drv_acq_group_n` in the sidecar and the notes clause
(e.g. `ACQ-20240930-XMIC-011`: `XMIC|2024-09-30T10:15:57.972561Z`, 2 files). B05–B16 changed only in
which files they hold, not in any code path the rehearsal exercised; their per-file values are proven by
check 2.

---

## 8. The production plan

Batches, order, per-batch procedure, stop conditions and rollback: the runbook. **Runtime:** each
file is read locally once (hash), written over SMB and read back over SMB (verify): 2× 4,022 GB at the
55–65 MB/s the NI pull sustained ≈ **37 h**, plus the per-acquisition registry / sidecar / link work
(0.2–0.3 s on local disk in the rehearsal; allow 1–2 s over SMB ≈ 3–5 h), plus the per-batch checks ≈ **45 h** in all.
The 400 GB `CELL` batches are ~4.5 h each: evening / weekend windows (operators ingest through the GUI
by day; the dedup snapshot is taken before the registry lock).

---

## 9. Gate items and proposed wording

**Decisions (runbook §0):** G1 closed projects `0219`/`1019` (B15/B16) · G2 the 18 `ZWSI` "ROI lobulo"
files · G3 the `0118` owner placeholder · G4 `sample_type` · G5 `collaborator:Charite` · G6 who runs it ·
and **confirm the tie-break guard** (§2).

**Out of scope, numbers as asked (handoff §1):**

| | Files | Distinct | GB |
|---|---:|---:|---:|
| `.tif` / `.tiff` loose | 11,528 | 10,404 | 302.0 |
| `.lsm` loose | 64 | 63 | 1.0 |
| `.tif` inside archives | 3,078 | 2,685 | 16.5 |
| `.czi` `czi-processed` / `czi-unreadable` / `czi-preview` | 12 (+1 member) / 4 (+1 member) / 1 | | |

**Proposed `tasks/STATUS.md` wording** (replace the "In flight" sub-bullet of the drives item):

> - **`.czi` ingest built and dry-run — 🔶 awaiting the coordinator's gate (2026-09-30).** 9,090 distinct `.czi` (4.0 TB; `CELL` 8,333 · `LSM9` 397 · `ZWSI` 22 · `XMIC` 338) in 16 batches; the engine's dry-run resolution matches the per-file plan on every file, and a 4-batch scratch rehearsal passed with an idempotent re-run. One project is created (`AE-biomaGUNE-0118`); 5,309 files get a blank project (Ryan's list). **Blocked on G1:** `0219`/`1019` are closed projects. Review: [`drives_ingest_dryrun_review.md`](drives_ingest_dryrun_review.md); procedure: [`drives_microscopy_ingest_runbook.md`](drives_microscopy_ingest_runbook.md).

**Proposed `CHANGELOG.md` row** (2026-09-30):

> **Historical microscopy drives: the `.czi` ingest is built, dry-run and rehearsed; nothing written to production.** **(1) The approved DB-date tie-break** is in `project_claims.py`: a histology file whose animal is in two protocols goes to the one whose animal was organ-sampled or perfused by the file date; (C) 180 → 131, the 49 movers exactly the approved readings. A guard was added: the rule confirms, never overrules, the file's own nearest claim, because the DB logs sampling unevenly (1321's animals 98–101 have slides but no sampling). **(2) New instrument code `XMIC`** for an external microscope's `.czi` (first: the Charité Axio Imager.Z2, `collaborator:Charite`). **(3) New ingest option `auto_discover.case_table`** (default off): a CSV keyed on `original_name` that sets values per file, so project / researcher / operator / subject decided file by file reach the engine exactly; the dry run proved the engine reads them back on all 9,090 files. **(4) `Project-NNNN` documented** (05_PROJECTS §2a.7). **(5) The plan:** one canonical copy per sha256 of every new `czi-raw` (9,090 files, 4.0 TB, 347 of them only inside archives, extracted and hash-verified), laid out in a hard-link farm so `original_name` is the drive path; 14 `ZWSI` excluded as already on `S:\goptical`; one `.czi` excluded because its name starts with a dot and the engine's glob cannot see it — a silent skip the dry run caught. **(6) After the gate (2026-09-30/10-01):** re-saves of production acquisitions (206) and within the plan (72) dropped, 22 derivatives (ROI crops, scale-bar copies) handed to the non-raw session, 247 same-timestamp groups flagged; the plan is 8,790 files / 3.85 TB in 16 batches. `AE-biomaGUNE-0219` and `-1019` reopened with the new `tools/reopen_project.py` (closed projects keep receiving data; 501 links restored). **The production primary of `ACQ-20251031-CELL-003` was found truncated** (5.1 MB short, last of 108 tiles unreadable) and **repaired in place** from the drive copy with the new `tools/repair_primary_inplace.py` (same file, so its project link sees the repair; `checksums.json`, `file_size_mb` and a notes clause updated; `verify_checksums` passes). B01–B04 (869 acquisitions, incl. the new project `AE-biomaGUNE-0118` = PROJ-0060) ingested and verified; B05–B16 follow.

---

## 10. Reproducing it

```
python tools/drive_staging/project_claims.py                  # claims, with the tie-break
python tools/drive_staging/catalog.py production && python tools/drive_staging/catalog.py assemble
python tools/drive_staging/ingest_plan.py goptical --hash
python tools/drive_staging/ingest_plan.py plan
python tools/drive_staging/ingest_plan.py extract
python tools/drive_staging/ingest_plan.py farm
python tools/drive_staging/ingest_plan.py configs
python tools/drive_staging/ingest_check.py                    # checks 1-7
python tools/drive_staging/ingest_plan.py scratch --batch B01 --batch B02 --batch B03 --batch B04
```

Outputs (regenerable, on the un-backed-up D:): `D:\projects\gjesus3\staging\_analysis\ingest\`
(`expected.csv`, `excluded.csv`, `conflicts.csv`, `batches.csv`, `plan_summary.json`,
`check_report.json`, `check_cases.csv`, `rehearsal\`), the pre-tie-break claims in
`…\_analysis\codes\_pre_tiebreak_20260930\`, the pre-refresh catalog in
`…\_analysis\catalog\_pre_refresh_20260930\`, the farm `…\staging\_farm\`, the extractions
`…\staging\_extract\` (58 GB; keep until the ingest is verified), the scratch NAS
`D:\projects\gjesus3\scratch_nas\` (delete after the review).

---

## 11. Production batch log

**Pre-flight 2026-09-30 11:05:**

- **Extraction:** 346 members, 0 bad (one of the original 347 left with R2).
- **Farm:** 8,790 links, 0 errors.
- **Animal DB:** OK.
- **Baseline validator:** 10,314 errors, all the known MRI `operator` placeholder, and 0 warnings. File: `C:\Users\rtasseff\temp\gjesus3_drives_ingest_20260930\baseline_validate.txt`.
- **Registry:** 16,437 rows.

**Reopened 2026-09-30 11:07–11:12** with `tools/reopen_project.py`; the logs are in the same folder.

- **`AE-biomaGUNE-0219`:** 80 links recreated, 4 collisions reported (see §Gate changes), status active.
- **`AE-biomaGUNE-1019`:** 421 links recreated, `last_activity` → 2026-09-29, status active.
- **Verified afterwards:**
  - Before/after file lists of both folders: **0 files missing**; the only new top-level files are `_project.yaml` and `index.html`.
  - `registry_projects.csv` changed in those two rows only.
  - A re-run of both is a no-op.
- **Backups:** `C:\Users\rtasseff\temp\gjesus3_reopen_backup_20260930_110743_AE-biomaGUNE-0219\` and `…_110926_AE-biomaGUNE-1019\`.

| Batch | When (2026-09-30) | Rows | Run | `ingest_verify` | Validator | Re-run | Backup (`C:\Users\rtasseff\temp\`) |
|---|---|---:|---:|---|---|---|---|
| B01 `XMIC` | 11:15–11:20 | 338 / 338 | 220 s | all PASS | 10,314 (unchanged) | 0 | `gjesus3_registry_backup_20260930_drives_B01` |
| B02 `0118` | 11:22–11:27 | 140 / 140 | 222 s | all PASS | 10,314 | 0 | `…_drives_B02` — **`AE-biomaGUNE-0118` = PROJ-0060** (projects 58 → 59 rows) |
| B03 `LSM9` | 11:30–11:36 | 387 / 387 | 284 s | all PASS | 10,314 | 0 | `…_drives_B03` |
| B04 `ZWSI` | 11:38–11:41 | 4 / 4 | 76 s | all PASS | 10,314 | 0 | `…_drives_B04` |

**Every batch went through the same steps:**

1. **Step 0:** a fresh `catalog.py production`, then `ingest_check.py --batch`; all 9 checks passed, with 0 SKIPs.
2. A verified off-NAS registry backup.
3. A dry run that matched the plan.
4. The run itself.
5. `ingest_verify`: rows, fields, checksums equal to the manifest sha256, sidecars, and links that are the raw primary.
6. The validator.
7. An idempotent re-run.

**After B04:**

- **Registry:** **17,306 rows** (+869), with 0 duplicate `acq_id`, 0 duplicate `original_name` and 0 blank dates.
- **Pending list:** `pending_subject_metadata.csv` is unchanged, so there were 0 DB misses.
- **Warnings:** only the documented sentinels.
- **Provenance:** `tasks/drives_ingest_provenance.csv` holds 869 rows so far, all `manifest_verified` Y.

**Repair of `ACQ-20251031-CELL-003` (approved by Ryan; coordinator's answers 2026-10-01; run 14:57, workstation clock 2026-09-30).**
The production primary (PROJ-0039 `claudia`, from `cellobs_bestguess_claudia.yaml`) was truncated. It is
now **repaired in place** from the drive copy
`D2\CELL OBSERVER 2\AINHIZE\1022\CD206\def\ID59_1022_tumor_CD206.czi`, using `tools/repair_primary_inplace.py`.

- **Links.** A scan of all 399,018 files under `projects\` found **one** link to the primary:
  `claudia\raw_linked\CELL_ID59_1022_tumor_CD206.czi`, which is the same file as the primary.
- **Backup.** Taken first and SHA-256-verified: all registry CSVs, `.acq_id_seq.json`, and the
  acquisition's `checksums.json` and `metadata.json`, in
  `C:\Users\rtasseff\temp\gjesus3_repair_backup_20260930_145741_ACQ-20251031-CELL-003\`.
- **The damaged primary** is kept for the record, verified, at
  `D:\projects\gjesus3\staging\_repair\ACQ-20251031-CELL-003\ACQ-20251031-CELL-003.czi.truncated`.
- **The write.** The existing file was opened `r+b`, written from offset 0, then `truncate`, flush and
  `fsync`. There was no `os.replace`, so every hard link sees the repair.
- **Checks after the write:**
  - the primary's SHA-256 is `dc8e8fe7…`, equal to the drive manifest's (it was `fcc7e287…`);
  - all **108 / 108** subblocks read with `czifile`;
  - the `claudia` link hashes the same as the primary.
- **Records:**
  - `checksums.json`: only the hash string changed; CRLF line endings kept, same length.
  - `registry_raw`: `file_size_mb` 3391.9 → **3397.0**, and the notes clause added, through
    `registry.update_row` under the lock. That is exactly one line changed; every other byte is identical.
  - The sidecar is untouched. Its size-like fields are image dimensions, identical in both copies.
- **Verification:** `verify_checksums --acq ACQ-20251031-CELL-003` passes (0 fail, 0 error). The validator
  holds at **10,314**, all the known placeholder.
- **Paper trail:** a provenance row (`batch` = `repair`, `manifest_verified` Y, note "repair, not a new
  acquisition"), and `excluded.csv` now reads `repaired-production`.

**Measured throughput to the NAS:** 31–39 MB/s effective (B02: 6.8 GB in 222 s; B04: 3.0 GB in 76 s),
including the source hash and the read-back verify. At that rate a 400 GB batch takes about 3–3.5 h, and
the remaining B05–B16 (3,830 GB) about **30–35 h**.

**Next: B05**, handed to a fresh session (`HANDOFF_RUN.md` at the worktree root).
