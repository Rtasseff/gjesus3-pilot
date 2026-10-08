# `biomaGUNE MJ` — the M. Jesús drive's last part: placement plan, rehearsal and production commands (for the gate)

**Status:** 🔶 READY FOR THE COORDINATOR'S GATE (copies only; nothing written to production) · **Date:** 2026-10-08 ·
**Branch:** `feat/drive3-biomagune-mj` · **Batch:** the third of stream P's tool, through its later-batch path
(`p_plan.py handover`, as stream M's P2 used) · **Precedents:** [`drive3_placement_gate.md`](drive3_placement_gate.md)
(stream P, batch 1), [`drive3_mri_gate.md`](drive3_mri_gate.md) §12 (P2) · **A2's inventory of this folder:**
[`drive3_projects_and_placement.md`](drive3_projects_and_placement.md) §6

**Read-only on production.** Nothing under `J:\gjesus3-data\` was created, changed or deleted, and nothing was written
under `J:\_staging_drive3_MJ\` (both were only read). The rehearsal ran on `D:`. Outputs:
`D:\projects\gjesus3\drive3_streams\bmj\`.

---

## Summary

1. **The input:** the 26,410 rows (52.14 GB) that stream P's executed manifest marked `deferred`, all under
   `biomaGUNE MJ\`. Every one is decided exactly once (§1).
2. **To copy: 3,983 files, 13.30 GB, in 3 windows** (§9):

   | Tree | Files | GB | How the project was decided |
   |---|---:|---:|---|
   | `AE-biomaGUNE-1123` | 1,915 | 3.73 | the engine (all Confirmed) |
   | `AE-biomaGUNE-0424` | 849 | 1.86 | 787 by reading **R5**, 62 the engine |
   | `AE-biomaGUNE-0522` | 580 | 0.58 | 458 the engine, 104 **R5**, 18 **R3b** |
   | `AE-biomaGUNE-1422` | 323 | 4.04 | the engine |
   | `AE-biomaGUNE-1019` | 188 | 3.03 | 181 the engine, 7 **R5** |
   | `AE-biomaGUNE-0619` | 0 | — | everything of it is already placed or a model output; only its `README.txt` gets the note (§5) |
   | **holding folder** | 128 | 0.06 | no project: 127 (C), 1 no claim |
   | **total** | **3,983** | **13.30** | |

3. **Not copied, by SHA-256 (§3):** 19,898 files (36.95 GB) are already in the very project they belong to (placed by
   batch 1, P2 or drives 1+2; each of those 19,897 tree copies was stat'ed on the NAS: present, same size); 2,443 files
   (1.79 GB) with no project have their bytes in a project already (most of `Proteomica`); 62 are already in the holding
   folder; 20 are duplicate copies in a second study folder. **0 are in `/raw/`** (live index of 35,613 acquisitions,
   647,057 files).
4. **Personal or administrative: 4 files in 3 folders, by name only (never opened), neither placed nor held** (§4).
   **3 of the 4 already have an identical copy in a project folder**, placed by batch 1 from `Pili y Mili`
   (`AE-biomaGUNE-0619` 2, `AE-biomaGUNE-0522` 1): if Ryan judges them personal, those copies need removing too.
5. **The 20 Biodonostia Axioscan files are untouched:** none of the 26,410 rows is in their folder (they are raw `.czi`,
   not in this input), and an invariant checks it (§8).
6. **Two readings, for the coordinator to confirm (§2):** the folders whose name gives two protocols (`PAH aged_Proyecto
   0424 & 1019`, `PAH diets_Proyecto 0619 & 0522`, `PAH female and male_(Proyecto 0522 & 0619)`) make no claim of their
   own (**TWO**, A2's precedent); a nearer single-code claim inside one stands when that folder is its only
   "disagreement" (**R5**), and a date folder reads the next claim out (**R3b**, A2's R3). Without them, about 916 files
   (1.82 GB) would go to holding instead. Evidence for R5: 1,456 of its 2,389 files already sit, byte for byte, in the
   project R5 names (placed from cleanly claimed copies elsewhere on the drive).
7. **The masks are drafts:** the `README.txt` of `AE-biomaGUNE-0522`, `-0619` and `-0424` gains the researchers'
   2026-10-08 answer (revised versions are in their shared OneDrive; in 0522's 2023 masks `IRE` marks Irene's corrections)
   (§5).
8. **Every invariant holds (§8); rehearsed on D: in full (§7):** all 3,983 files copied, re-hashed and verified, every
   earlier index row kept, re-runs copy nothing and write no document. The manifest is deterministic (built twice,
   byte-identical). **Suite: 42/42** (`main` 41/41 + `test_drive3_bmj.py`).

**The gated manifest:** `D:\projects\gjesus3\drive3_streams\bmj\batch3_v2\placement_manifest.csv`, SHA-256
`f3b3ff7a26cd467cf0864af012774cef411cbcb3347c6b616f12f0fe0367500b` (23,962 rows: the handed-over ones; the other 2,448
are decided in `lists_v2\bmj_decisions.csv`, SHA-256 `4b219e9d…`; the joined view is `batch3_v2\bmj_final.csv`).

---

## 1. Every one of the 26,410, by final decision

| Decision | Files | GB | Copied? |
|---|---:|---:|---|
| `place` | 3,855 | 13.24 | yes, windows W1–W2 |
| `holding` | 128 | 0.06 | yes, window W3 |
| `already-placed` (same project's tree; 1 is the `.zip` twin, below) | 19,898 | 36.95 | no |
| `covered-by-twin` (no project; the bytes are in a project's tree) | 2,443 | 1.79 | no |
| `already-in-holding` (45 are model outputs, §2.4) | 62 | 0.10 | no |
| `duplicate-copy` (one study folder per content, A2 D3) | 20 | 0.00 | no |
| `personal` (§4) | 4 | 0.01 | no, and not held |
| `in-raw` · `untouched` (Biodonostia) · zero-byte · junk | 0 | — | — |
| **total** | **26,410** | **52.14** | |

By `biomaGUNE MJ` subfolder (files copied / not copied): `Bleomicina Mice_Proyecto 1123` 1,916 / 40; `PAH aged_Proyecto
0424 & 1019` 1,147 / 3,190; `Metformina Male PAH_Proyecto 0522` 458 / 1,303; `Manosa and 2DG Male_Proyecto 1422` 323 /
1,728; `PAH diets_Proyecto 0619 & 0522` 80 / 6,914; `PAH female and male_(Proyecto 0522 & 0619)` 58 / 4,307;
`PAH 2DG_Proyecto 0619` 0 / 2,977; `Proteomica` 0 / 1,968; the loose `Experimentos MJ.xlsx` 1 (holding). This matches A2
§6: the unique non-raw content is the recent `1123`, `1422` and aged `0424`/`1019` cohorts; the rest are copies.

**Junk** never reached this input: stream P excluded it from the manifest (A2's rules); `handover` refuses it again by
name (0 refused).

---

## 2. Claims per file

The project of each file is the claims engine's per-file verdict (Ryan's rule of 2026-09-29), from A2's run
(`D:\projects\gjesus3\drive3_analysis\a2\claims\`), unchanged. Before this batch the engine gave, for the 26,410:
Confirmed 21,365, (C) 3,076, no claim 1,969. Then four rules, each applied by code (`bmj_plan.project_of`) and pinned by
a test:

### 2.1 TWO: a folder that names two protocols makes no claim of its own

Three folders give two gjesus3 protocols in their name. The engine read **one** code out of each:
`PAH aged_Proyecto 0424 & 1019` as 1019 (Confirmed), `PAH female and male_(Proyecto 0522 & 0619)` as 0619 (Confirmed),
`PAH diets_Proyecto 0619 & 0522` as 0522 ((C): its cross-check failed). Following A2's precedent for
`Pili y Mili\Proyecto 1019 + 1121` (all (C)), a file whose deciding claim **is** such a folder has no project. That
overrides the engine's Confirmed for **6 files** (all six are `covered-by-twin`: their bytes are already in `0619`), and
leaves 549 files the engine already called (C) without a project.

### 2.2 R5: the nearer single-code claim stands — *a reading, for confirmation*

Inside those folders sit single-code folders and file names (`PAH aged Female_Proyecto 0424`, `Machos KD
diet-2303-0522`, `SUV-m45-0522.nii`). The engine confirmed them, then compared them with the outer folder it had read as
one code, saw a "disagreement" and fell back to (C). But the outer folder names **both** codes, so it agrees. This is
A2's R2 case (an identical outer code counted as a disagreement). R5 reads the nearer code when **all** of:
- the nearer claim is Confirmed, single-code, and its code is one the two-code folder gives;
- every other code in the engine's disagreement is either the folder's other code or a token the engine never confirmed
  as a protocol anywhere on the drive (the YYMM dates `2302`, `2303`, `2305`, `2311`);
- the file's own evidence is inconclusive, never contrary: the engine's words are "no animal number to decide between
  them", or "animal N is found in BOTH … and the DB dates do not separate them". In 303 of the `0424` files it adds
  "terminal procedure only on the outer 1019's animal N by <file date>": that is, 1019's animal of the same number was
  already dead when the file was written (1019's procedures end 2022-09-30; these are the 2024 `0424` cohort's files, such as
  `NIFTI_jrc241127_m12_0424`). That speaks against 1019, not for it, and the engine itself says "the rule never
  overrules the nearest claim".

**2,389 files** qualify (0424 1,181; 0522 879; 0619 228; 1019 101). After dedup: **898 placed** (1.82 GB), 1,471
already placed, 20 duplicate copies. **Corroboration:** 1,456 of the 2,389 already sit, byte for byte, in the very
project R5 names (copies elsewhere on the drive with a clean claim), 15 more sit there and in another project too, 2 only in
another project (one each in `0522` and `0619`); 916 nowhere yet.

A file whose nearer code is **not** one of the folder's, or is itself unresolved (`SUV-m4-0422.nii` in the `0424 & 1019`
folder; 17 files named for `0522` in `1019`'s procedure 3, such as `SUV-m163-0522.nii`), stays (C): conflicting, so
holding or covered.

### 2.3 R3b: a date folder reads the next claim out — *a reading, for confirmation*

A2's R3 for the two-code folders: the nearest "code" is a YYMM date the engine itself "reads as a date"
(`2305-Machos KD diet SuHx Segunda tanda`, `2302-PAH male`). R3b reads the next single-code claim outward (both
`…-2303-0522` → 0522), when the two-code folder also gives that code. **71 files**, 18 placed, 53 already placed in
`0522`. The `Machos HCH diet-2311` folder has no claim between its date and the two-code folder: its 47 dated files stay
(C).

### 2.4 C5: the model outputs go to holding (stream P's call)

The 45 Vicomtech predictions in `Predict_Slicer` folders (A3 S6; exactly A3's 45 model-output labels inside
`biomaGUNE MJ`) follow stream P's call C5: holding, beside the group's tool, not the project. All 45 are already in the
holding folder (batch 1 put their twins there), so none is copied.

### 2.5 What goes to holding (128 files, 0.06 GB)

| Group | Files | Why |
|---|---:|---|
| `PAH aged_Proyecto 0424 & 1019\PAH gathered aged` (graphs, figures, documents across both cohorts) | 110 | its only claim is the two-code folder (TWO) |
| `PAH diets_Proyecto 0619 & 0522\…` (`RAW DATA\PET\230613-PAH Male KD` text files, `1 - Diets merged`, one `Normoxia` file) | 13 | the two-code folder, or a 0522 claim whose cross-check failed |
| `PAH female and male_(Proyecto 0522 & 0619)\…` | 3 | the two-code folder |
| `Bleomicina Mice_Proyecto 1123\Raw data\PET\241008\FDG_m29_1124.png` | 1 | a `1124` in a `1123` folder: (C), not guessed |
| `Experimentos MJ.xlsx` (loose in `biomaGUNE MJ\`) | 1 | no claim |

Their reason stays `(C) claim` / `no claim`, so a later 2b round (the assign workbook) can map them.

---

## 3. Dedup, by SHA-256 only

| Against | How | Result |
|---|---|---|
| `/raw/`, **live** | `p_verify.py raw-dedup --write-index`, 2026-10-08 12:35–12:42: every acquisition's `checksums.json` (35,613 acquisitions, 647,057 files, none hashed directly, none missing) | **0** of the 26,410 |
| each target tree, **live** | `handover` reads the tree's `_INDEX.csv` on the NAS (all drives, all batches) | 19,897 `already-placed` |
| every project tree and the holding folder, **live** | `bmj_plan.py` reads every registered project's `_INDEX.csv` (72,365 placed files) and the holding `manifest.csv` | 2,443 `covered-by-twin` (no project, bytes in a project), 62 `already-in-holding` |
| batch 1's expanded archive | the `.zip` in `PAH aged Female_Proyecto 0424\Documentos\OH` has the same SHA-256 as the one batch 1 expanded (P1) | 1 `already-placed` (its 2 members are in `0424`) |
| within this batch | `handover`'s "one study folder per content" (A2 D3) | 20 `duplicate-copy` in `0522` (`RAW DATA\PET\0522\<n>` twins of `Machos HCH diet-2311\PET\PET-0522\<n>`) |

Already placed, per tree (files · GB): `0522` 7,796 · 13.02; `0619` 7,149 · 11.58; `1422` 1,727 · 2.20; `1019` 1,594 ·
2.14; `0424` 1,592 · 8.00; `1123` 40 · 0.01. Covered by a twin: 2,077 in `0522` (most of them the 1,966 `Proteomica` files, as A2 §6
found), 363 in `0619`, 3 others. **Five files are placed although the same bytes also sit in another project's tree**
(`0424` 2, `1123` 3): their own claim names this project, the A2 D5 / C4 precedent ("the same document in two projects
is harmless").

---

## 4. Personal and administrative files

**Never into a shared project folder; neither placed nor held; listed for Ryan.** The screen reads **names only**: a
broad keyword pattern (CV, curriculum, contract, payslip, ID document, passport, invoice, bank, insurance, letter,
personal, private, photo, picture, absence, medical, leave, receipt, admin, request, e-mail, `.msg`/`.eml`, every
`.jpg`/`.jpeg`/`.heic`, …) over all 26,410 paths. **18 hits**, each judged by an explicit table in `bmj_plan.py`
(a hit the table does not know stops the run):

- **14 judged project material:** 8 CEEA / OH animal-protocol forms, a qPCR instrument export (the instrument's account
  is called `admin`), a service request to the microscopy unit, 2 PET image exports named by animal and tracer, a paper
  figure, an analysis legend.
- **4 flagged as possibly personal, in 3 folders** (counts and folders only; the files were not opened):

  | Folder (below `biomaGUNE MJ\`) | Files | What the name suggests |
  |---|---:|---|
  | `Proteomica\Proteomica Female\Muestras enviadas a bioGUNE` | 2 | phone-camera photos |
  | `Metformina Male PAH_Proyecto 0522` | 1 | a note about the owner's absence |
  | `Manosa and 2DG Male_Proyecto 1422\Raw data\PET\1422\240529\59` | 1 | a picture named after a person |

  Their sample-shipment and PET-exam folders suggest project material, but a name cannot tell. **3 of the 4 already
  have an identical copy in a project folder**, placed by batch 1 from `Pili y Mili` (2 under
  `AE-biomaGUNE-0619\…\MJesus-MFB\Proyecto 0619 Ratones PAH`, 1 under `AE-biomaGUNE-0522\…\MJesus-MFB\Proyecto 0522
  PAH`). The per-file list, with those copies' paths, is on D: only:
  `D:\projects\gjesus3\drive3_streams\bmj\lists_v2\bmj_personal_files.csv`.

---

## 5. The masks are drafts: the README note

The researchers answered on 2026-10-08 that the `0522`, `0619` and `0424` masks were revised by Jesús and Irene, and the
revised versions are in a shared OneDrive folder, not on this drive; and that in `0522`'s 2023 masks, `IRE` marks Irene's
corrections of M. Jesús's. So the masks here are placed as work in progress, and the README of those three trees says so
(appended to the shared text; every other tree keeps it byte for byte):

```
Segmentation masks under MJesus-MFB\ are drafts
  The segmentation masks of protocol 0522 under MJesus-MFB\ are working
  drafts from the drive. Jesus Ruiz-Cabello and Irene Fernandez later revised
  them; the revised versions are in their shared OneDrive folder, not here.
  Use the masks here as work in progress, not as final results.
  In the 2023 masks, the files labelled IRE are Irene's corrections of the
  drive owner's masks (not a second, independent reading).
```

(`0619` and `0424`: the first paragraph with their code, no IRE line.) It covers batch 1's masks in those trees as well.
`copy` publishes it for `0522` and `0424` in W1; `0619` gets no file in this batch, so `bmj_plan.py readme` writes its
README alone (the same bytes `copy` would write; its provenance row already exists). Names are written without accents,
as the rest of the README.

The rest of the answers do not change placement: `IF` = Irene Fernández and `Unai` = the NI platform manager matter for
A3's dataset; the 15 `m47` masks in `m46`'s folder (`1422`, question 6) are placed where they are.

---

## 6. What changed in the code, and why

| File | Change | Why |
|---|---|---|
| `tools/drive_staging/drive3/bmj_plan.py` (new) | `lists`: decides each deferred row (§1–§4) and writes the hand-over list, the decisions file and the personal list; `check`: the invariants and the gate's tables (`--stat-twins` stats every already-placed copy); `readme`: a README-only tree (`0619`). | The batch's input and its proof. |
| `tools/drive_staging/drive3/p_plan.py` `handover` | (1) a row an earlier manifest marks `deferred` is that later batch's input, not "already decided"; (2) optional `class` / `claim_id` / `verdict` columns are carried into the manifest, the index and provenance; (3) a holding row whose reason is exactly `no claim` / `(C) claim` keeps it (the stream goes to `note`), so a later 2b round can map it. | (1) Without it every row is refused. (2) Batch 1's rows carry them; P2's rows had `other` as class. (3) `nonraw_placement.mappable` needs the exact reason. Behaviour for stream M's lists is unchanged (no such columns; their holding reasons are not mappable ones). |
| `tools/drive_staging/historical_paths.py` | `PROJECT_README_NOTES` and `project_readme(base)`: a note for one project's tree. | §5. |
| `nonraw_placement.py` (`tree_documents`), `p_verify.py` (`verify`) | use `project_readme(base)` | publish and verify agree on every tree's README. |
| `tools/test_drive3_bmj.py` (new) | the screen (an unjudged hit stops), TWO / R5 / R3b and their refusals, the handover changes, the README note published by `copy` and expected by `p_verify` (a README without it is caught), the `readme` command, C5. | |
| `tools/INDEX.md` | the placement row names this batch. | |

**Suite: 42/42 suites pass** (the coordinator's runner on this worktree; `main` 41/41).

---

## 7. Rehearsal (D:, in full)

**Setup.** `p_verify.py snapshot` of the live NAS (every tree batch 3 touches: 5 projects and the holding folder, plus
`0619`'s documents for the README step) became the rehearsal root `D:\…\bmj\rehearsal\nas`. Every command was §9's,
with `--nas` = the rehearsal root; the **source was the real staged copy on `J:`** (read-only). Logs:
`D:\…\bmj\rehearsal_W1.log`, `_W2.log`, `_W3.log`, `rehearsal_final_verify.log`.

| Window | Copied | Whole window (snapshot, copy, both verifies, re-run) | `p_verify` (re-hash all) | Index rows before → after (all before rows kept, column by column) | Re-run |
|---|---:|---|---|---|---|
| W1 `0424` `0522` `1019` | 1,617 · 5.48 GB | 4 min | **PASS**, 1,617 re-hashed | `0424` 1,092 → 1,941; `0522` 7,801 → 8,381; `1019` 13,076 → 13,264 | 1,617 `skipped-identical`, 0 documents written |
| W2 `1123` `1422` | 2,238 · 7.77 GB | 4 min 40 s | **PASS**, 2,238 re-hashed | `1123` 353 → 2,268; `1422` 2,254 → 2,577 | 2,238 `skipped-identical`, 0 written |
| W3 holding | 128 · 0.06 GB | 17 s | **PASS**, 128 re-hashed | `manifest.csv` 59,355 → 59,483; `_PATHMAP.csv` 7,521 kept | 128 `skipped-identical`, 0 written |
| README `0619` | 1 document | — | its diff against the live README is exactly the note | — | "already carries the note" |

W1 and W2 also passed `nonraw_placement.py verify` (counts and bytes per project, a re-hash sample, 0 mismatches), and
`_PATHMAP.csv`, `_ORIGIN.txt`, provenance (one row per file, earlier rows unchanged) and `registries\` (unchanged) in
`p_verify`. `README.txt` came out with the note in `0522` and `0424`, unchanged in the other trees.

**Not rehearsed here:** a kill and resume. The copy routine and `p_verify` are batch 1's, whose rehearsal killed and
resumed `0320` (stream P §4.3); nothing on that path changed. On the NAS, a window also writes to `J:` (here it wrote to
D:), so expect it slower than the times above.

---

## 8. Invariants

All PASS (`bmj_plan.py check --stat-twins`, on the gated manifest; `check_v2_stat_twins.log`):

| Invariant | Result |
|---|---|
| every deferred row of batch 1 decided exactly once | 26,410 of 26,410 |
| the batch manifest holds exactly the handed-over rows | 23,962; `handover` refused 0 |
| every row's (size, SHA-256) = batch 1's = the drive manifest | yes (`handover` also re-checks the staged manifest: identical) |
| no file copied is in `/raw/` (live) | 0 of 3,983 |
| nothing under the Biodonostia Axioscan folder is in the batch | 0 rows (its 20 files untouched) |
| no personal file is placed or held | 4 listed, 0 in the batch |
| no junk or zero-byte file copied | yes |
| every destination ≤ 240 characters, no component > 255, unique (case-insensitive), under `MJesus-MFB\` | longest 240; 3,983 |
| no destination exists on the NAS | 3,983 stat'ed, 0 present |
| every place row targets an active project, the one its claim or listed reading gives | yes |
| no file placed into a tree that already holds its bytes | yes |
| every already-placed file's copy is on the NAS, same size | 19,897 of 19,897 stat'ed |
| a file placed from inside a two-code folder lands in one of its two projects | 0 do not |
| C5: no model output placed in a project | 45 A3 labels, 45 selected, 0 placed |
| nothing goes to holding whose bytes are already in holding or a project | yes |
| every duplicate copy's canonical copy is copied | 0 orphans |
| deterministic | `lists` and `handover` built twice: byte-identical (`f3b3ff7a…`) |

---

## 9. Production commands, window by window

Copies only; nothing deleted; no registry row changed. From the repo root (after the merge), in PowerShell. **One
window at a time, and not while a registry writer (the MRI archive ingest) runs:** the windows append to the provenance
of `0424`, `0522`, `1019`, `1123` and `1422`, which an ingest into the same projects may also write.

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$B   = 'D:\projects\gjesus3\drive3_streams\bmj'
$M   = "$B\batch3_v2\placement_manifest.csv"
$NAS = 'J:\gjesus3-data'
$RUN = "$B\runs"
$SCR = "$B\scratch"
$NP  = 'tools\drive_staging\nonraw_placement.py'
$PV  = 'tools\drive_staging\drive3\p_verify.py'
$PP  = 'tools\drive_staging\drive3\p_plan.py'
$BP  = 'tools\drive_staging\drive3\bmj_plan.py'
$S   = 'D:\projects\gjesus3\drive3_streams'     # every earlier batch's manifest lives under it (9.0)
$W1 = 'AE-biomaGUNE-0424','AE-biomaGUNE-0522','AE-biomaGUNE-1019'
$W2 = 'AE-biomaGUNE-1123','AE-biomaGUNE-1422'
```

| Window | Trees | Files | GB |
|---|---|---:|---:|
| W1 | `0424` 849, `0522` 580, `1019` 188 (+ the `0619` README) | 1,617 | 5.48 |
| W2 | `1123` 1,915, `1422` 323 | 2,238 | 7.77 |
| W3 | the holding folder | 128 | 0.06 |

### 9.0 Once, before W1 (read-only) — the manifest is still the gated one

Production may have moved (another placement, the 2b round, an ingest). Rebuild into new folders and compare; **do not
run this after W1** (by design it then finds batch 3's files and calls them already placed).

```powershell
$D = Get-Date -Format yyyyMMdd
python $PV raw-dedup --manifest $M --nas $NAS --write-index "$B\live_raw_index_$D.csv"
#   expect: RAW-DEDUP PASS: 0 of the 3983 rows copied now or held are in /raw/ (all 23962 manifest rows checked)
python $BP lists --raw-index "$B\live_raw_index_$D.csv" --out "$B\lists_check_$D"
python $PP --nas $NAS handover `
    --manifest "$S\placement\manifest_check2_20261006\placement_manifest.csv" `
    --manifest "$S\placement\release_M1_20261006\placement_manifest.csv" `
    --manifest "$S\mri\out\p2\P2a_20261007_1053\placement_manifest.csv" `
    --manifest "$S\mri\out\p2\P2b_20261007_1053\placement_manifest.csv" `
    --manifest "$S\mri\out\p2\P2b_masks_20261007_1053\placement_manifest.csv" `
    --csv "$B\lists_check_$D\bmj_handover.csv" --stream BMJ --raw-index "$B\live_raw_index_$D.csv" --out "$B\batch3_check_$D"
#   expect: handover (BMJ): 23962 files {'already-placed': 19897, 'place': 3855, 'already-in-holding': 62, 'holding': 128,
#           'duplicate-copy': 20}; refused 0; destinations already present: 0
Get-FileHash "$B\lists_check_$D\bmj_handover.csv", "$B\batch3_check_$D\placement_manifest.csv"
#   expect: 5F339FE8190E8BD9… and F3B3FF7A26CD467C… (= the gated ones)
python $BP check --lists "$B\lists_v2" --batch $M --raw-index "$B\live_raw_index_$D.csv"
#   expect: ALL INVARIANTS HOLD
```

**Stop** if a hash differs, `handover` refuses a row, or any invariant fails: re-gate on the new build
(`bmj_final.csv` and `check.log` beside it show what moved).

### 9.1 W1 and W2 (project windows)

For window `Wk` with its list `$Wk` (W1 shown):

1. **Backup and before-state** (fresh, dated, off-NAS):
   `python $PV snapshot --manifest $M --nas $NAS --project $W1 --to C:\Users\rtasseff\temp\gjesus3_placement_backup_YYYYMMDD_HHMM_drive3_B3W1`
   → `snapshot: 3 projects; saved {…}; absent 0; already under MJesus-MFB\: <n> files` (`n` = batch 1's files there;
   W2: `2 projects`).
2. **Dry run:** `python $NP --out $RUN\W1 --nas $NAS copy --manifest $M --scratch $SCR --project $W1`
   → W1: `1617 files, 5.48 GB, 3 projects` (`0522` 580 + 8 index documents, `1019` 188 + 4, `0424` 849 + 4);
   W2: `2238 files, 7.77 GB, 2 projects` (`1422` 323, `1123` 1915, + 4 each); and in both `destinations already present: 0`,
   `over budget: 0`, longest 237 (W1) / 240 (W2).
3. **Copy:** the same command plus `--execute` → `finished: {'copied': 1617}` (W2: `2238`), exit 0.
4. **Verify:**
   - `python $NP --out $RUN\W1 --nas $NAS verify --manifest $M --project $W1` → every project `OK`, `0 mismatches`;
   - `python $PV verify --manifest $M --nas $NAS --snapshot <step-1 folder> --project $W1 --rehash sample` → `VERIFY PASS`:
     walk 0 missing / 0 extra / 0 temp (batch 1's files are "there before", not extra); index rows before → after
     `0424` 1,092 → 1,941, `0522` 7,801 → 8,381, `1019` 13,076 → 13,264 (W2: `1123` 353 → 2,268, `1422` 2,254 → 2,577),
     plus whatever another writer added since 2026-10-08 (the check is "every before row kept, the new rows once");
     README current (the note in `0522` and `0424`); one provenance row per file; `registries\` unchanged (if another
     writer ran meanwhile, the line names its files: confirm they are that writer's).
   - ACL spot check: `icacls "J:\gjesus3-data\projects\AE-biomaGUNE-0424\working\historical_drives\MJesus-MFB"` shows
     only inherited entries.
5. **W1 only — the `0619` README:** first `python $PV snapshot --manifest $M --nas $NAS --project AE-biomaGUNE-0619 --to
   C:\Users\rtasseff\temp\gjesus3_placement_backup_YYYYMMDD_HHMM_drive3_B3_0619readme` (keeps today's README), then
   `python $BP --nas $NAS readme --project AE-biomaGUNE-0619 AE-biomaGUNE-0522 AE-biomaGUNE-0424` → `0619: would be
   rewritten`, `0522` / `0424`: `already carries the note`; then the same with `--execute` → `0619: README.txt written`.
   A second run says `unchanged` for all three.

### 9.2 W3, the holding folder (last)

1. `python $PV snapshot --manifest $M --nas $NAS --holding --to C:\Users\rtasseff\temp\gjesus3_placement_backup_YYYYMMDD_HHMM_drive3_B3W3`
2. `python $NP --out $RUN\W3 --nas $NAS holding --manifest $M --scratch $SCR` → `DRY RUN: 128 files, 0.06 GB`, longest 231,
   `by reason: {'no claim': 1, '(C) claim': 127}`.
3. The same plus `--execute` → `{'copied': 128}`, `documents published: 2 written` (README unchanged).
4. `python $PV verify --manifest $M --nas $NAS --snapshot <step-1 folder> --holding --rehash sample` → `VERIFY PASS`
   (`manifest.csv` 59,355 → 59,483, every earlier row kept). `icacls` as for batch 1.

### 9.3 If something goes wrong

- **Stopped half-way** (crash, network, a killed window): **re-run step 3 unchanged.** Files already in place are
  re-hashed and skipped, an interrupted `.~nonraw-*.part` is overwritten, missing provenance rows are added once, and the
  tree's documents are published after its last file. Then step 4.
- **`COLLISION`** (a destination holds different bytes): nothing is overwritten and that project's documents are not
  published. **Stop and report; delete nothing.**
- **Lock timeout** on `projects\<project>\.registry.lock`: if no other copy of this tool or an ingest is running, delete
  that lock file and re-run.
- **To abandon a window** (not expected): unlike batch 1, the `MJesus-MFB\` folders already hold batch 1's files, so
  **never remove the folder.** Remove only the files the window copied (the rows with result `copied` in its
  `$RUN\Wk\copy_NONRAW-*.csv`), and restore the four documents per tree (`_INDEX.csv`, `_PATHMAP.csv`, `README.txt`,
  `provenance.csv`) and any `_ORIGIN.txt` from the step-1 snapshot.

### 9.4 After the last window

Keep `D:\projects\gjesus3\drive3_streams\bmj\` (the lists, the manifest, `runs\`) — and its inputs, A2's
`D:\projects\gjesus3\drive3_analysis\` and the earlier batches' manifests under `drive3_streams\` (9.0 re-reads them) —
until the drive's close-out copies the evidence to `J:\gjesus3-data\staging\historical_drives_records\drive3_MJesus_WX22D623YP29\`. With this batch every
non-raw file of the drive has a decision, so the staged copy's non-raw side is done; the close-out's manifest check
decides when the staged copy can go (Ryan's go).

---

## 10. For the coordinator: calls to confirm, and what is unsettled

**To confirm:**
1. **The readings TWO, R5 and R3b (§2).** Without R5/R3b, 916 files (1.82 GB; `0424` 787, `0522` 122, `1019` 7) go to
   holding instead, mappable later. Without TWO, 6 files would count as `0619`'s (all 6 are covered by twins anyway).
2. **The 4 personal flags (§4)** and, if Ryan confirms any, the removal of batch 1's identical copies in `0619` (2) and
   `0522` (1): a production delete, not planned here.
3. **C5 applied here too (§2.4)**: the 45 Vicomtech predictions stay with the tool in holding (all already there).

**Unsettled:**
- **The personal screen reads names.** Opening the 4 flagged files to classify them was refused by this session's
  permission check (privacy), so the judgement is by name and folder only; and a file whose name gives no hint is not
  caught. The 14 judged-project hits are listed in the table in `bmj_plan.py` (`JUDGED`).
- **The study folder of `0424` and `1019` is the two-code folder's own name** (`PAH aged_Proyecto 0424 & 1019 (female
  and male)`, shortened to `PAH aged_Proyecto 0424 &~0ce6`), because the shared rule takes the outermost claim root and
  the engine left a claim for each code there. It is the drive's name; the README and `_ORIGIN.txt` explain the cut.
- **A `0522` folder named just `0522`** (`RAW DATA\PET\0522`) lands as `0522 (2)`, beside batch 1's `0522`
  (`PET\0522`): the rule's suffix for a second root of the same name.
- **The masks' final versions are not on gjesus3** (§5): A3's trace and any curated dataset should use the OneDrive
  revisions, not these drafts.
