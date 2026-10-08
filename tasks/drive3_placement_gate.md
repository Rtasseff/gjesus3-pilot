# Stream P — the M. Jesús drive's non-raw material: placement manifest, rehearsal and production commands (for the gate)

**Status:** 🔶 READY FOR THE COORDINATOR'S GATE (copies only; nothing written to production) · **Date:** 2026-10-06 ·
**Branch:** `feat/drive3-placement` · **Plan it implements:** [`drive3_production_plan.md`](drive3_production_plan.md) stream P,
on A2's plan [`drive3_projects_and_placement.md`](drive3_projects_and_placement.md) ·
**Precedent extended:** [`drives_nonraw_placement_review.md`](drives_nonraw_placement_review.md) (drives 1+2, stream A)

**Read-only on production.** Nothing under `J:\gjesus3-data\` was created, changed or deleted, nothing was written under
`J:\_staging_drive3_MJ\`, and `J:\gjesus3-sandbox\` was not needed (§4.7). Outputs are under
`D:\projects\gjesus3\drive3_streams\placement\`.

---

## Summary

1. **To copy now, in 5 windows (projects first, holding last): 35,559 files, 122.69 GB.**
   - **30,983 files, 82.49 GB into 15 projects**, `AE-biomaGUNE-1121` included (3,996 files, 8.39 GB; reopened today).
     This includes **stream N's PMOD DICOM exports** (the coordinator's instruction of 2026-10-06): of the 49, 11 are placed (0.53 GB: 10 in `0619`,
     1 in `0522`), 7 are duplicate copies, and 31 sit in `biomaGUNE MJ` (deferred) (§2, N1).
   - **4,576 files, 40.20 GB into the holding folder**, under a new `MJesus-MFB\` beside `FRIO-X6\` and `MFB-Disco-2\`, in the
     drive's own structure; the shared `README.txt` and `manifest.csv` are merged, not rebuilt.
2. **HELD, planned but never copied by these windows: 1,780 files, 1.83 GB.**
   - 1,760 files of protocol `0118` (hold `M1-0118`, STATUS §0.5 M1), planned under `AE-biomaGUNE-0118`. Under answer E only
     the base folder changes for 1,514 of them; 246 get a shorter path under U (§2.4).
   - 10 documents for `AE-biomaGUNE-1521` and 10 for `-0618` (holds `reopen-…`): A2's 19, plus the one D5 document that
     belongs to `1521`.
3. **Every invariant holds** (§3), including two run against live production after the 11:03–11:21 AxioScan ingest:
   - no file copied or held is an acquisition file in `/raw/`: 27,120 acquisitions' `checksums.json` read live,
     516,663 files;
   - no destination exists, and no target tree has a `MJesus-MFB\` folder yet.
4. **The gated manifest is v2** (`manifest_v2\placement_manifest.csv`, SHA-256
   `de03b2b1a06fdb76d91a2addd9a1f98040ab8f47d51cda0108562528b168038f`): v1 plus the 49 N1 rows, and **no v1 row changed**
   (decision, project, hold, destination, size, SHA-256). The build is deterministic: v1 was built three times and v2
   twice, byte-identical each time.
5. **Rehearsed on D:** with the production commands, against a copy of the real tree documents (§4). The NAS was shared
   with streams C and N (about 2.5 s per file), so:
   - W1 and `0320` were copied in full (`0320` through a deliberate kill and a resume);
   - W3–W5 on their riskiest 1,158 rows: all 775 long-source files, up to 299 characters;
   - the later batches: two reopen releases, the M1 release plan, a second batch and the N1 delta.
   - **Every tree verified PASS. Every drives 1+2 index row was kept**: e.g. `1019` 7,289, `0619` 3,324, `1519` 8,680,
     and holding 54,723. Every re-run copied nothing and rewrote no document.
6. **Code:** the placement tools now know a third drive, map (B) claims per code, and have a `held` decision that is never
   copied. New: `p_plan.py` builds the manifest and later batches; `p_verify.py` does the before/after checks.
   **Suite: 39/39** (main 38/38 + the new `test_drive3_placement.py`).
7. **Four calls of mine for you to confirm** (§6): the scope of "the model outputs"; expanding the one `.zip`;
   not excluding 7 "personal/admin" heuristic hits (all false positives); the drive label `MJesus-MFB` (kept).

---

## 1. What changed in the code, and why

| File | Change | Why |
|---|---|---|
| `tools/drive_staging/historical_paths.py` | `TAGS` / `DRIVE_LABELS` gain `D3` → `MJesus-MFB` / `drive3_MJesus-MFB`. `PROJECT_README` names the three drives (serials, WD My Passport) and the classes drive 3 brings (segmentations, NIfTI/MetaImage volumes). | A2 §8 trap: the rule knew two drives. A2 had registered `D3` in memory only. |
| `tools/drive_staging/nonraw_placement.py` | `DRIVES["D3"]` = the staged copy on `J:\_staging_drive3_MJ\…` (read-only). `CLAIMS_DRIVE["drive3"]`. | The copy source. |
| | **`project_for`: (B) mapped per code** (`B_PROJECTS`: `Project-0521` and `Project-0720` → `Project-0521`; any other (B) → holding). | It sent every (B) to `Project-0521`; drive 3's `0924` (2 CEEA documents) would have been misfiled. Drives 1+2 are unaffected: all their (B) were 0521/0720, and their claims inputs are gone, so no stored manifest is re-decided. |
| | **Decision `held`** and a `hold` manifest column. `copy`, `holding` and `verify` never copy or expect a held row; `copy` prints how many it left. | M1 and the `1521`/`0618` reopen. |
| | Holding `README_TXT` names the three drives, says the model predictions sit with the group's tool, and that `biomaGUNE MJ` is not included. `notreg_text` names the group's own drive (the drives 1+2 text is byte-identical). Provenance names the drive and its staging dates (`DRIVE_DESC`; drives 1+2 wording byte-identical). | A2 §8 trap: the READMEs named two drives. |
| `tools/drive_staging/project_claims.py` | The run summary lists every drive in `DRIVES` (`drive1 N, drive2 M` exactly as before). | A2 §8 trap: it indexed `manifests['drive1']`/`['drive2']`, so a drive-3 wrapper had to fake empty manifests. |
| `tools/drive_staging/drive3/p_plan.py` (new) | `plan`: A2's `placement_plan.csv` → `nonraw_placement`'s manifest format, the coordinator's calls applied, A2's content-level step and dedup re-run, destinations through `nonraw_placement.assign_destinations` (the shared rule) against the live NAS, held rows planned after the copied ones, the M1 answer-E variant, the invariants, a row-by-row comparison with A2. N1: stream N's PMOD exports added by A2's own rules (`pmod_rows`). `release`: a held group → a new manifest of only those rows, re-planned. `handover`: a later batch from another stream (§5.8); refuses junk (A2's rules) and zero-byte files; reads `/raw/` live. | The brief: "convert it, or re-plan with the extended tool and show the two agree" — done both ways (§2.6). |
| `tools/drive_staging/drive3/p_verify.py` (new) | `snapshot` before a window (the dated off-NAS backup of every document the window may rewrite, and the "before" state); `verify` after it; `raw-dedup` against live `/raw/`. | Independent proof that drives 1+2 rows survive every merge, and the coordinator's dedup requirement. |
| `tools/test_historical_paths.py`, `tools/test_nonraw_placement.py` | Extended: D3 tag/label/README; (B) per code; held never copied (an end-to-end `copy` / `holding` / `verify` on a temp NAS); drive-3 rows merged into a drives 1+2 tree with the older 9-column header (the `0118` case). | |
| `tools/test_drive3_placement.py` (new) | The calls one by one; `decide` on a synthetic A2 plan; N1 rows; `release`; `handover` as a second batch (lands in batch 1's frozen folder, refuses what it must, junk included); `raw-dedup` (live, with and without `checksums.json`); `p_verify` catching a lost index row, a leftover temp file and a vanished earlier-batch file, over one tree and two. | |
| `tools/INDEX.md` | One row for the placement tools. | |

**Suite:** `39/39 suites pass` (the coordinator's runner, on this worktree; main is 38/38). The tests and the rehearsal
caught three bugs in the new verifier before it was gated, each now pinned by a test: a crash on a missing file instead
of a report; an earlier batch's files reported as "extra" in a later batch's window; and one tree's state leaking into
the next tree's check (found by the rehearsal's 7-tree run).

---

## 2. The manifest

**Where:** `D:\projects\gjesus3\drive3_streams\placement\manifest_v2\placement_manifest.csv` (89,691 rows: one per A2 file
or archive member, plus the 49 N1 rows), with `trees\` (the per-tree `_INDEX.csv` / `_PATHMAP.csv` / `_ORIGINS.csv`
previews that `copy` publishes, merged) beside it. `manifest\` beside it is v1, the version the rehearsal ran (§4). `per_project.csv` gives files, bytes and a list hash per tree; `compare_a2.csv` every row that differs
from A2; `m1_U_vs_E.csv` the M1 variant; `held_U\` / `held_E\` the held rows' previews; `plan.log` everything.
**Keep the folder as it is:** `copy` reads the previews next to the manifest.

**Built from:** A2's plan (recommended scenario: readings R1–R4, one study folder per content), the drive manifest
(the D: copy is byte-identical to the staged one, checked by SHA-256 on every run), the live registry and every target
tree's documents on the NAS.

**The coordinator's calls, as applied** (each row's `reason` names its call):

| Call | Effect |
|---|---|
| C1 `1121` reopened | A2's 3,975 `place-after-reopen` → `place`. |
| C2 `0118` waits on M1 | Everything A2 planned under Ryan's 09-30 names is planned under `AE-biomaGUNE-0118` (answer U). The 3 new Monocrotalina documents are placed now; the other 1,760 are `held` (`M1-0118`). The 19 already in `AE-biomaGUNE-0118` stay `already-placed`. |
| C3 `1521` / `0618` closed | A2's 19 `closed-project` → `held` (`reopen-AE-biomaGUNE-1521` / `-0618`). |
| C4 A2 D5 | The 25 `placed-elsewhere` files are also placed in drive 3's project: 21 + 3 now (`1121`, `0721`), 1 held (`1521`). Each gets the study folder of its project's claim root. |
| C5 the model outputs → holding | All 1,062 non-deferred files A3 S6 calls model output: the Vicomtech `Predict_Slicer` folders (135 in `1019`, 45 in `0619`) and the 2019 rat `Pred_` / `Postprocessed_` / `Modificated_` volumes of `Segmentacion 2DG RATAS` (882, which R4b had sent to `0118`). Checked against A3's own sets: every A3 S6 label outside `biomaGUNE MJ` is selected, and nothing else but their `.raw` companions and other `Predict_Slicer` files. |
| D8 | The group's tool `Otros\PH_analysis_Segmentation_tool` → holding (A2 had it there). |
| P1 (mine) | The one `.zip` A2 placed whole (`0424`'s `Re_ Informe pendiente de modificación AE-biomaGUNE-0424.zip`, 2 Word documents) is expanded like every drives 1+2 archive; the zip's own bytes are checked against the drive manifest first. |
| N1 (coordinator, from stream N) | The 49 PMOD DICOM exports (A1's `pet_files.csv`, `kind = pmod-export`: co-registered and SUV-scaled volumes; DICOM by content, Manufacturer PMOD), which no stream had planned, are added as A2-style rows by A2's own rules (its claims, its readings, its first decision with `/raw/` read live, its study folders). Then they follow every call above and the dedup: **11 placed** (0.53 GB: `0619` 10, under `Proyecto 0619 Ratones PAH` and `0619`; `0522` 1, `CorregPETCT` under `0522`), **7 duplicate copies** (`PET\0619\…` twins of `Pili y Mili` copies), **31 deferred** (`biomaGUNE MJ`, among them all 20 of `1422`'s). None is in `/raw/`, held, or already placed. Class `pmod-dicom`. |

### 2.1 What is copied now, per tree

| Project | Place now (files · GB) | Already placed by drives 1+2 | Twins not placed (one study folder per content) |
|---|---:|---:|---:|
| `AE-biomaGUNE-0619` (incl. 10 N1) | 7,313 · 31.41 | 4,997 · 6.50 | 1,766 · 5.61 |
| `AE-biomaGUNE-0522` (incl. 1 N1) | 7,801 · 16.29 | — | 2,519 · 4.34 |
| `AE-biomaGUNE-1019` | 5,701 · 10.57 | 9,087 · 9.36 | 916 · 1.11 |
| `AE-biomaGUNE-1121` | 3,996 · 8.39 | — | — |
| `AE-biomaGUNE-0424` | 1,092 · 6.16 | — | — |
| `AE-biomaGUNE-1122` (R4a) | 195 · 3.25 | — | — |
| `AE-biomaGUNE-1422` | 2,254 · 3.16 | — | — |
| `AE-biomaGUNE-0320` | 2,272 · 3.07 | 375 · 0.30 | 467 · 0.97 |
| `AE-biomaGUNE-1519` | 228 · 0.10 | 4,055 · 4.38 | — |
| `AE-biomaGUNE-0721` | 54 · 0.06 | — | 23 · 0.01 |
| `AE-biomaGUNE-1123` | 40 · 0.01 | — | — |
| `AE-biomaGUNE-0525` | 20 · 0.02 | — | — |
| `AE-biomaGUNE-1420` | 13 · 0.01 | 6 · 0.00 | — |
| `AE-biomaGUNE-0118` | 3 · 0.00 | 19 · 0.01 | 213 · 0.31 (held twins) |
| `AE-biomaGUNE-1321` | 1 · 0.00 | — | — |
| **15 projects** | **30,983 · 82.49** | 18,994 · 20.99 (incl. 426 with no project here) | 5,904 · 12.35 |

Study folders per tree (below `MJesus-MFB\`) are A2's: e.g. `0619` 10, `1019` 11 (`Proyecto 1019 Envejecimi~c3e8`, the
same short name drive 1 got), `1519` 2 (`Proyecto 1519 Santander` and `… (2)`). Every destination is at most 240
characters; the longest source path read is 299 characters (345 copied files have sources of 260+).

### 2.2 The holding folder

`staging\historical_drives_unassigned\MJesus-MFB\<the drive's own path>` — **4,576 files, 40.20 GB:**

| Group | Files | GB |
|---|---:|---:|
| The pig pulmonary-artery set (`Otros\Segmentaciones ITK SNAP\Segmentaciones Arteria Pulmonar cerdos`) | 1,956 | 27.82 |
| `Microscopio` exports with no code (`Female Diets`, `Male Diets`, `Machos vs Hembras`, `Histologia_ratones_viejos`, …) | 424 | 4.45 |
| `Pili y Mili\Draft papers` | 718 | 2.94 |
| D8: the group's 3D Slicer tool and trained models | 27 | 2.86 |
| `0522\IFs and histologies` (A2 D7, (C)) | 100 | 1.43 |
| C5: the 2019 rat model predictions (`Segmentacion 2DG RATAS`) | 882 | 0.09 |
| `Proyecto 1019 + 1121` (two codes) | 85 | 0.27 |
| C5: the Vicomtech predictions (`Predict_Slicer`) | 180 | 0.05 |
| `0924`'s 2 CEEA documents ((B), no project) | 2 | 0.00 |
| Other (C) or no claim (date-named `0522` folders where the engine found no animal to decide, `1121\Experimentos` with animal IDs not in 1121, `0619\PAH Female`, …) | 202 | 0.28 |

The (C) and no-claim rows keep the reasons `(C) claim` / `no claim`, so a later mapping round (the 2b worksheet route) can
map them; the decided ones (C5, D8) cannot. One side effect of C5: with the rat predictions in holding, the rule's fewest
cuts is to shorten their shared parent, so `Otros\Segmentaciones ITK SNAP` renders as `Segmentacion~738e` for the pig set
too (1,958 holding paths differ from A2's plan for this reason alone; `_INDEX`-style `manifest.csv` keeps every original).

### 2.3 HELD: planned, never copied by the windows below

| Hold | Project | Files · GB | What it waits on |
|---|---|---:|---|
| `M1-0118` | `AE-biomaGUNE-0118` (answer U) | 1,760 · 1.82 | STATUS §0.5 M1. Study folders `Proyecto 0118 (Ratas hipoxia)` (1,179), `Segmentacion 2DG RATAS` (456: the split volumes; their predictions are C5), `Rata MCT` (125). |
| `reopen-AE-biomaGUNE-1521` | `AE-biomaGUNE-1521` (closed) | 10 · 0.00 | Ryan's go for the reopen (A2's 9 + the D5 document `Hoja 2 - Propuesta de proyecto o actividad (DocA).docx`). |
| `reopen-AE-biomaGUNE-0618` | `AE-biomaGUNE-0618` (closed) | 10 · 0.01 | Ryan's go for the reopen. |

`biomaGUNE MJ` (26,379 files, 50.89 GB) is `deferred`, out of this stream; nothing under it is placed, held or held back
in holding.

### 2.4 M1: what changes under answer E (`Proyecto-0118-rats-hipoxia`)

Planned both ways (`held_U\`, `held_E\`, `m1_U_vs_E.csv`). **For 1,514 of the 1,760, only the base folder changes.**
For 246, the paths below `historical_drives\` differ only in shortening: `AE-biomaGUNE-0118` is 9 characters shorter, so
under U fewer names are cut. Both plans fit the 240 budget. Whichever answer comes, `release` plans the rows again
against the NAS at that time (§5.7).

### 2.5 Listed, not copied

| Decision | Files · GB | |
|---|---:|---|
| `already-placed` | 18,994 · 20.99 | same bytes already in the same project (drives 1+2); 17,346 NAS copies stat'ed by A2 |
| `already-in-holding` | 605 · 0.10 | in the drives 1+2 holding folder |
| `duplicate-copy` | 5,904 · 12.35 | one study folder per content (A2 D3); each points at its canonical copy, which is placed, held or in holding (7 are N1) |
| `covered-by-twin` | 257 · 0.69 | no project, same bytes placed through a claimed copy |
| `deferred` | 26,410 · 52.14 | `biomaGUNE MJ` (31 are N1) |
| `exclude` | 181 · 0.00 | zero-byte, counted |
| `expanded` | 1 · 0.00 | the `.zip` (P1); its 2 members are `place` rows |

**Excluded junk, never in the manifest** (6,394 files, 0.26 GB, from A2's per-file classification): `desktop.ini` 5,048;
AppleDouble `._*` 1,032; `Thumbs.db` 106; `.DS_Store` 99 (Ryan's list); Office temp files 60, image-viewer caches 25,
macOS `Icon<CR>` 22 (A2's additions); the 2 WD installers. The drive's 621,969 files reconcile exactly: A2's 89,640 +
the 49 N1 rows + the rest of A1's raw imaging 525,886 + junk 6,394.

### 2.6 Against A2's plan (converted and re-planned: the two agree)

Every one of A2's 89,640 rows is compared (`compare_a2.csv`):

| | Files |
|---|---:|
| **Same decision, project and destination** | 80,732 (place 26,863; holding 1,556; already-placed 18,994; duplicate-copy 5,897; deferred 26,379; covered 257; already-in-holding 605; zero-byte 181) |
| C1 `1121` place-after-reopen → place, same destination | 3,967 (+ 8 whose folder `Informacion proyecto` is now cut, because C4 added long CEEA paths to the tree) |
| C2 `0118` held, same path below `historical_drives\` | 1,514 (+ 246 shorter, §2.4); 3 Monocrotalina placed, same path |
| C3 held | 19 |
| C4 placed in drive 3's project | 24 (+ 1 held) |
| C5 model outputs → holding | 1,062 |
| P1 | 1 zip expanded; 2 member rows added |
| N1 (not in A2's plan) | 49 rows added (11 place, 7 duplicate-copy, 31 deferred); no other row changed |
| Re-planned shortening (the tree's file set changed) | 105 in `1019` (its `MRI 8 MONTHS…` folders no longer need cutting once `Predict_Slicer` left) and 1,958 in holding (§2.2) |

No difference is unexplained, and no decision changed except by a call.

---

## 3. Invariants checked

All PASS. From `p_plan.py plan` on v2 (and on v1, three builds) unless stated:

| Invariant | Result |
|---|---|
| Every row's (size, SHA-256) equals the drive manifest | 89,691 of 89,691; the zip's own bytes too; its 2 members hashed from it |
| Every copied file's bytes are re-checked against the manifest at copy time | `copy_one` hashes the source as it reads and refuses a mismatch; it re-reads the destination before the rename (rehearsal: §4) |
| Each file has exactly one decision; no file both copied now and held | 89,691 distinct; 35,559 copied, 1,780 held, overlap 0 |
| No destination over 240 characters on `\\GJESUS3\gjesus3\`, no component over 255 | longest 240 (37,339 destinations, held ones included) |
| Destinations unique, case-insensitive | yes |
| No collision with an existing file | no target tree has a `MJesus-MFB\` folder (18 trees); on v1 each of the 37,328 destinations was stat'ed on the NAS: none exists. On v2 the per-file stat was stopped (hours on the shared NAS); the structural check covers the 11 new destinations (each lies under a tree's `MJesus-MFB\`, and no tree has one), and §5.0 step 1 re-runs the full stat before W1 |
| **No file copied or held is already in `/raw/`, against live production** (`p_verify.py raw-dedup`) | v1 (13:26–13:32): **0 of 37,328**; 27,120 acquisitions read from their own `checksums.json` (516,663 files; the 86 ZWSI registered 11:03–11:21 included); none of the 89,642 rows matches. v2: its 49 new rows were checked inside the build against that same live index (none in `/raw/`). The full live re-run on v2, started 14:58, was still reading production when this was committed (NAS load); it finishes into `D:\projects\gjesus3\drive3_streams\placement\raw_dedup_live_v2.log`, and §5.0 step 2 runs it again before W1 |
| Every place row targets an active project in the live registry | yes (`1121` active since its reopen) |
| None of the staged copy's 7 verify problems (AppleDouble rewritten by the NAS) is copied | yes |
| Nothing under `biomaGUNE MJ` is copied or held | yes |
| Every duplicate-copy's canonical copy is placed, held or in holding | 0 orphans |
| C5 selects exactly A3's model outputs (and their companions) | yes: 591 A3 labels outside `biomaGUNE MJ` + their 471 `.raw` / `Predict_Slicer` companions = 1,062 |
| **The drives 1+2 index rows are preserved after a merge** | rehearsal, §4 (`p_verify.py verify`: every before row, column by column) |
| The manifest is reproducible | v1 built three times, byte-identical (`8b265ba9…`); v2 built twice, byte-identical (`de03b2b1…`), = v1 + 49 rows with no v1 row changed |
| Junk is never placed, now or by a later batch | 6,394 junk files excluded; `handover`'s junk rule agrees with A2's on all 621,969 drive files |

---

## 4. Rehearsal

**Setup.** At 12:43 `p_verify.py snapshot` copied, from the live NAS, every document the windows may rewrite (the 15
target trees' `_INDEX.csv` / `_PATHMAP.csv` / `README.txt` / `_ORIGIN.txt`, the holding folder's three documents, the 15
projects' `provenance.csv`) and hashed `registries\`. That snapshot, copied, is the **rehearsal root**
`D:\projects\gjesus3\drive3_streams\placement\rehearsal\nas` (the registries copied in full and checked equal to the
snapshot's hashes). Every command below is §5's, with `--nas` pointing at the rehearsal root; the **source is the real
staged copy on `J:`** (read-only). Logs: `rehearsal\logs\`.

**The NAS was shared.** From 12:44, streams C and N read the staged copy hard. A file then took about 2.5 s instead of
0.1 s (W1 at 12:43: 359 files in 35 s; afterwards 0.3–0.4 files/s). So the rehearsal copied W1 in full, `0320` in full
(through a kill and a resume), and the riskiest rows of W3–W5 (§4.5), and planned rather than copied the bulk of the
rest (§4.7).

### 4.1 W1: the 7 small trees, in full — PASS

- `copy --execute`: 359 files, 0.20 GB, `{'copied': 359}` in 35 s; `nonraw_placement.py verify` all `OK`.
- `p_verify.py verify --rehash all`: **VERIFY PASS**, 359/359 re-hashed. Every drives 1+2 index row kept, column by column:
  `0118` 21 (the older 9-column header), `0721` 2,885, `1123` 313, `1321` 390, `1420` 3, `1519` 8,680; `0525` a new tree.
  Every `_PATHMAP.csv` entry and `_ORIGIN.txt` line kept; one provenance row per file and one per new document;
  `README.txt` the three-drive text; `registries\` unchanged.

### 4.2 The idempotent re-run — PASS

- W1 again: `{'skipped-identical': 359}`, **0 documents written**; `p_verify` again: PASS, 359/359 re-hashed, provenance
  unchanged (the re-run added no row).
- Every later window below was also run twice: the second run always `skipped-identical` for all, 0 documents written.

### 4.3 Stopped half-way, then resumed (W2, `0320`) — PASS

- **Killed** at 12:54:43, after 424 of `0320`'s 2,272 files. It left exactly the hard case: 424 files, one complete-sized
  `.~nonraw-f9b376b1.part` not yet renamed, **no documents published**, and 400 of the 424 provenance rows (the last
  batch was still in memory).
- `p_verify.py verify` on that state **FAILED on every count**: walk (1,848 missing, 1 temp file), index (0/2,272 new rows),
  `_PATHMAP.csv` (no `MJesus-MFB` folder), `README.txt` (old text), provenance (400/2,272).
- The dry run then reported `destinations already present: 424`. **The same `--execute` command, unchanged**, resumed at
  13:34: `skipped-identical` 424, then copied the other 1,848 (the stale `.part` replaced by the real file), and
  published the tree's 6 documents after the last file.
- `p_verify.py verify --rehash all` then: walk 2,272 files, 0 missing / extra / temp; `_INDEX.csv` 375 drives 1+2 rows kept
  + 2,272; `_PATHMAP.csv`, `_ORIGIN.txt`, `README.txt` correct; **every file has exactly one provenance row** (the 24 lost
  ones added once); 2,272/2,272 re-hashed. The only flag was `registries\registry_projects.csv`, which the rehearsal itself
  changed at 13:44 (the simulated reopens of §4.6: exactly two `status` cells) — the check doing its job.
- W2's other three trees were not copied (§4.7).

### 4.4 The `.zip` members (P1)

Both members of `0424`'s zip were read out of the staged zip on `J:` by the production routine, verified, and skipped on a
re-run; they land in `…\Documentos\OH\Re_ Informe pendiente de~9e64\`.

### 4.5 W3–W5 on their riskiest rows — PASS (5 of 5)

W1 and W2 have no source path over 235 characters; W3–W5 hold all 345 copied files whose staged source path is 260–299
characters. For each of `1019`, `1121`, `0522`, `0619` and the holding folder, the production copy routine
(`copy_one`) copied every file with a source of 255+ characters, the 20 longest destinations, one file per shortened
folder and a 0.5 % sample; then the tree's full documents were published (the real merge) and checked against the
snapshot; then both were re-run.

| Tree | Copied (of) | Sources of 255+ | Longest source · destination | Index before → after (all before rows unchanged) | Re-run |
|---|---:|---:|---|---|---|
| `1019` | 119 (5,701) | 27 | 299 · 240 | 7,289 → 12,990 | 119 skipped, 0 documents written |
| `1121` (reopened, new tree) | 96 (3,996) | 1 | 272 · 240 | 0 → 3,996 | 96 skipped, 0 written |
| `0522` | 176 (7,800) | 113 | 272 · 240 | 0 → 7,800 | 176 skipped, 0 written |
| `0619` | 710 (7,303) | 630 | 269 · 240 | 3,324 → 10,627 | 710 skipped, 0 written |
| holding (`manifest.csv`) | 57 (4,576) | 4 | 268 · 240 | 54,723 → 59,299 (`_PATHMAP.csv` 6,798 kept) | 57 skipped, 0 written |

Each publish wrote the full merged index (every row of the tree, copied or not), so the rehearsal root's `_INDEX.csv`
for these trees lists files it does not hold: a property of this targeted test only.

**N1, the PMOD exports, on v2:** the 11 placed rows copied into the rehearsal root, `0619` and `0522` re-published from
v2's previews over the v1 documents already there: 10,627 → 10,637 and 7,800 → 7,801 rows, every earlier row kept;
re-run 11 skipped, 0 written; 11/11 re-hashed.

### 4.6 Later batches — PASS

- **Releases.** `release --hold reopen-AE-biomaGUNE-1521` (and `-0618`) **refused** while the project was closed. After a
  simulated reopen (the rehearsal registry only): release → snapshot → copy (10 / 10 files) → **VERIFY PASS** → re-run
  `skipped-identical`, 0 documents written.
- **M1 (answer U), planned against the rehearsal root after W1:** all **1,760 destinations equal the batch manifest's
  prediction** for the held rows. (Not copied: 1.82 GB on today's NAS.)
- **A second batch** (`handover`, stream M style, real drive-3 data): the 1019 PRESS spectroscopy exam folder
  `20210128_090809_jrc210128_m50MBmrs_1_1\11` (28 files) and one `.czi` given a synthetic "derivative" label and parent
  `ACQ-REHEARSAL-ONLY` (rehearsal only). The first attempt **stopped** with "cannot bring under 240": the list had swept in
  a `desktop.ini` whose name could not fit inside batch 1's frozen folders, and the planner refused rather than rename
  them, as designed. `handover` now refuses junk by A2's rules (checked against A2 on all 621,969 drive files: 0
  disagreements) and zero-byte files. Then: 29 planned, 3 `desktop.ini` refused; they landed **inside batch 1's study
  folder** `Proyecto 1019 Envejecimi~c3e8\…`; a `README_not_registered.txt` naming `MJesus-MFB` one level up (the
  budget); **VERIFY PASS**: the 119 batch-1 files already there recognised, 12,990 index rows kept (7,289 drive 1 +
  5,701 batch 1) + 29, provenance + 31; re-run `skipped-identical`.

### 4.7 Not covered, and why

- **Copied in full: W1 and `0320`.** Not copied: `0424` (except its zip members), `1122` and `1422` of W2, and W3–W5
  beyond the rows of §4.5, because of the NAS load (§ above). Production copies every file through the same routine,
  which hashes each source as it reads it against the drive manifest and re-reads the destination before the rename;
  `p_verify.py verify` then walks every tree.
- **`J:\gjesus3-sandbox\` was not needed.** The destination side on the NAS (SMB create and rename, 240-character
  destinations, accented names) is the same code path drives 1+2's production ran on 2026-10-04 (82,268 files with the
  holding folder); the source side is the staged copy the rehearsal read; nothing here uses hard links, and every
  AppleDouble `._*` file is excluded junk.
- **Timing.** On a quiet NAS, W1 took 35 s for 359 files. Under today's shared load a file took about 2.5 s, which would
  make W4 alone several hours. **Run W2–W5 when no other stream is reading the staged copy**; on a quiet NAS expect
  roughly one to two hours for all of them (122 GB read, written and re-read through the workstation).

---

## 5. Production commands, window by window

Copies only; nothing deleted; no registry row changed. Run from the repo root (`gjesus3-pilot`, after the merge), in
PowerShell. **One copy window at a time**, and preferably not while another stream reads the staged copy hard (§4.5).

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$M   = 'D:\projects\gjesus3\drive3_streams\placement\manifest_v2\placement_manifest.csv'
$NAS = 'J:\gjesus3-data'
$RUN = 'D:\projects\gjesus3\drive3_streams\placement\runs'
$SCR = 'D:\projects\gjesus3\drive3_streams\placement\scratch_copy'
$NP  = 'tools\drive_staging\nonraw_placement.py'
$PV  = 'tools\drive_staging\drive3\p_verify.py'
$W1 = 'AE-biomaGUNE-0118','AE-biomaGUNE-0525','AE-biomaGUNE-0721','AE-biomaGUNE-1123','AE-biomaGUNE-1321','AE-biomaGUNE-1420','AE-biomaGUNE-1519'
$W2 = 'AE-biomaGUNE-0320','AE-biomaGUNE-0424','AE-biomaGUNE-1122','AE-biomaGUNE-1422'
$W3 = 'AE-biomaGUNE-1019','AE-biomaGUNE-1121'
$W4 = 'AE-biomaGUNE-0522','AE-biomaGUNE-0619'
```

| Window | Projects | Files | GB |
|---|---|---:|---:|
| W1 | the 7 small trees (`0118` 3, `0525` 20, `0721` 54, `1123` 40, `1321` 1, `1420` 13, `1519` 228) | 359 | 0.20 |
| W2 | `0320`, `0424`, `1122`, `1422` | 5,813 | 15.64 |
| W3 | `1019`, `1121` | 9,697 | 18.96 |
| W4 | `0522`, `0619` (incl. the 11 N1 files) | 15,114 | 47.70 |
| W5 | the holding folder | 4,576 | 40.20 |

### 5.0 Once, before W1 (read-only)

1. **The manifest is still the gated one** (production may have moved): rebuild it into a new folder and compare.
   ```powershell
   python tools\drive_staging\drive3\p_plan.py plan --out D:\projects\gjesus3\drive3_streams\placement\manifest_check_YYYYMMDD
   Get-FileHash $M, D:\projects\gjesus3\drive3_streams\placement\manifest_check_YYYYMMDD\placement_manifest.csv
   ```
   Expect `ALL INVARIANTS HOLD` and the same SHA-256 (`de03b2b1a06fdb76…`). **If it differs, stop** and re-gate on the new
   one (`compare_a2.csv` / `per_project.csv` show what moved). Do not re-run this after W1: by design it then finds
   `MJesus-MFB\` folders.
2. **Nothing copied is in `/raw/`, live:**
   `python $PV raw-dedup --manifest $M --nas $NAS` → `RAW-DEDUP PASS: 0 of the 37339 rows…` (about 6 minutes).

### 5.1–5.4 Each project window (W1, then W2, W3, W4)

For window `Wk` with project list `$Wk` (example for W1):

1. **Backup and before-state** (fresh, dated, off-NAS):
   `python $PV snapshot --manifest $M --nas $NAS --project $W1 --to C:\Users\rtasseff\temp\gjesus3_placement_backup_YYYYMMDD_HHMM_drive3_W1`
   → `snapshot: 7 projects; saved {…}`.
2. **Dry run:** `python $NP --out $RUN\W1 --nas $NAS copy --manifest $M --scratch $SCR --project $W1`
   → the files and GB of the table above, `destinations already present: 0`, `longest UNC path` ≤ 240,
   `over budget: 0`. In W1 it also prints `held, not copied by this run: 1760 files {'M1-0118': 1760}` (`0118`).
3. **Copy:** the same command plus `--execute` → `finished: {'copied': N}` with N = the window's files, exit 0.
4. **Verify:**
   - `python $NP --out $RUN\W1 --nas $NAS verify --manifest $M --project $W1` → every project `OK`, `re-hash sample: …, 0 mismatches`;
   - `python $PV verify --manifest $M --nas $NAS --snapshot <the folder of step 1> --project $W1 --rehash sample`
     → `VERIFY PASS` (walk 0 missing / 0 extra / 0 temp files; every drives 1+2 index row, `_PATHMAP.csv` entry and
     `_ORIGIN.txt` line kept; one provenance row per file; README current; `registries\` unchanged). If another
     stream's registry writer ran during the window, the registries line names its files: confirm they are that
     writer's, not this window's (this tool opens no registry file for writing).
   - ACL spot check, as for drives 1+2: `icacls "J:\gjesus3-data\projects\AE-biomaGUNE-0118\working\historical_drives\MJesus-MFB"`
     shows only inherited entries (`GJesus` Modify plus the admins).

**If it stops half-way** (crash, network, a killed window): **re-run step 3, unchanged.** It re-hashes each file already
in place and skips it, overwrites an interrupted `.~nonraw-*.part`, adds each missing provenance row once (they are
idempotent on `output_path`) and publishes the tree's documents after the project's last file. Then step 4. This
exact case was rehearsed (§4.3). Two things can need a hand:
- a `COLLISION` line: a destination holds different bytes. Nothing is overwritten and that project's documents are not
  published. Stop and report; do not delete anything;
- a lock timeout on `projects\<project>\.registry.lock`: if no other copy of this tool is running, delete that lock file
  and re-run.

To abandon a window instead of finishing it (not expected): everything it wrote is `…\historical_drives\MJesus-MFB\` of
its trees (new folders) plus three documents and `provenance.csv` per project. Restore those four from the step-1
snapshot and remove the `MJesus-MFB\` folder; nothing of drives 1+2 lives under it.

### 5.5 W5, the holding folder (last)

1. `python $PV snapshot --manifest $M --nas $NAS --holding --to C:\Users\rtasseff\temp\gjesus3_placement_backup_YYYYMMDD_HHMM_drive3_W5`
2. `python $NP --out $RUN\W5 --nas $NAS holding --manifest $M --scratch $SCR` → `DRY RUN: 4576 files, 40.20 GB`, longest ≤ 240;
   it writes the README and manifest previews to `$RUN\W5\holding_preview__*` — read the README there.
3. The same plus `--execute` → `{'copied': 4576}`, `documents published: 3 written`.
4. `python $PV verify --manifest $M --nas $NAS --snapshot <step 1 folder> --holding --rehash sample` → `VERIFY PASS`
   (the 54,723 drives 1+2 rows of `manifest.csv` kept, the 2 not-copied rows included; 4,576 added).
   `icacls` on `staging\historical_drives_unassigned\MJesus-MFB` should match its parent (no ACL change, Ryan 2026-10-05).

If it stops half-way: re-run step 3 (as above; holding writes no provenance).

### 5.6 After the last window

- Keep `D:\projects\gjesus3\drive3_streams\placement\` (manifest, previews, `runs\` logs) until the close-out copies the
  evidence to `J:\gjesus3-data\staging\historical_drives_records\drive3_MJesus_WX22D623YP29\` (production plan, close-out
  step 2): the manifest folder, the `copy_*.csv` logs, `live_raw_index_20261006.csv` and this record.
- Keep A2's inputs, `D:\projects\gjesus3\drive3_analysis\` (its plan, `files.csv`, `claims\`) and A3's labels, until the
  last release and hand-over: `p_plan.py plan` re-reads them, and `handover` uses A2's claim roots.
- The Data Office's global index (`tasks/drives_nonraw_index.csv`, `index-from-nas`) is not refreshed by these commands;
  that is a separate, optional step for whoever keeps it.

**A trap:** always give `nonraw_placement.py` an explicit `--out`. Its default is the drives 1+2 analysis folder on
`D:\projects\gjesus3\staging\…`, erased on 2026-10-05, and the tool would recreate it.

### 5.7 Later: releasing the held rows

Each release is a new, small manifest, planned against the NAS at that time; then the same window procedure.

| When | Commands |
|---|---|
| **M1 answered U** | `python tools\drive_staging\drive3\p_plan.py release --manifest $M --hold M1-0118 --out $R` (with `$R = 'D:\projects\gjesus3\drive3_streams\placement\release_M1_YYYYMMDD'`), then the window procedure with `$R\placement_manifest.csv` and `--project AE-biomaGUNE-0118`: snapshot; `python $NP --out $RUN\release_M1 --nas $NAS copy --manifest $R\placement_manifest.csv --scratch $SCR --project AE-biomaGUNE-0118` (then `--execute`); `p_verify.py verify` |
| **M1 answered E** | first `create_project.py` for `Proyecto-0118-rats-hipoxia` (Ryan's approval), then `release … --hold M1-0118 --project Proyecto-0118-rats-hipoxia`, then the same with that project |
| **Ryan's go for `1521` / `0618`** | the coordinator reopens them (`reopen_project.py`), then `release … --hold reopen-AE-biomaGUNE-1521` and `… --hold reopen-AE-biomaGUNE-0618`, then the same |

`release` refuses a project that does not exist or is not active.

### 5.8 Later: other streams' material for the same trees

Stream C's `.czi` derivatives, stream N's PET companions and stream M's not-registered exam folders land in the same
trees as a **second batch**:
```powershell
python tools\drive_staging\drive3\p_plan.py handover --manifest $M --csv <the stream's list> --stream C --out D:\…\placement\handover_C_YYYYMMDD
```
CSV columns: `relpath, kind, project, reason, parent_acq_ids, sha256` — `kind` is `derivative` (needs `parent_acq_ids`;
its provenance then starts with them), `notregistered:<no-recon|non-image|conversion-failed>` (a
`README_not_registered.txt` per exam folder), `companion` or `other`; a blank `project` means holding. It refuses a path
not in the drive manifest, a SHA-256 that differs from it, a file an earlier batch already decided (pass every earlier
manifest with `--manifest`), and bytes already in `/raw/`: read live, every acquisition's `checksums.json` (about 6
minutes), or `--raw-index` with an index saved the same day by `p_verify.py raw-dedup --write-index`. Bytes already in
the tree become `already-placed`. Rows for `0118` before M1 is answered take `--hold M1-0118`. Then the window procedure
with the new manifest. Rehearsed on real drive-3 data (§4.6).

---

## 6. Calls of mine, and what I could not settle

**For the coordinator to confirm:**
1. **The scope of "the model outputs" (C5).** I took A3 S6 literally: the Vicomtech predictions (`Predict_Slicer`) and the
   2019 rat `Pred_` / `Postprocessed_` / `Modificated_` volumes, 1,062 files, all to holding. Consequences: 180 files
   leave the `1019` and `0619` project trees, and `Segmentacion 2DG RATAS` is split (its 456 split volumes stay with the
   held `0118` material, their predictions go to holding). If you meant only the tool's own folder, drop C5 in
   `p_plan.py` (one rule, `model_output`) and re-plan: 1,062 rows move back, nothing else changes.
2. **Expanding the `.zip` (P1).** Ryan's "no zips" and the drives 1+2 precedent; the zip is 2 Word documents. The
   expanded folder name is cut to `Re_ Informe pendiente de~9e64`.
3. **The personal/admin heuristic is not applied.** A2 imported it but did not use it. On this drive it hits 7 files, all
   project material (2 sample-shipping certificates, a qPCR export named `admin_…`, a TEM billing sheet
   `Datos de facturación.xlsx`, a paper on drug "administration"). Excluding them would lose project files.
4. **The drive label `MJesus-MFB`:** kept (A2's reasons hold: the volume label shortened like the other two, no accents,
   10 characters fewer than the full label on every path).

**Not settled:**
- **If Ryan refuses a reopen** (`1521` or `0618`), its 10 documents have no home: `release` only targets an active
  project. They could go to the holding folder through a one-off `handover` with a blank project; not built.
- **A later batch can stop on the budget.** A file that lands deep inside batch 1's frozen folders may not fit under
  240 if its name is longer than its neighbours'; the planner then stops and writes nothing (§4.6). Rare for real data
  (the rehearsal's real exam folder fitted once the junk was refused), but a stream's list should expect it: the fix is
  a human choice (a different study folder, or holding).
- **The full data volume of W2's other three trees and of W3–W5** was not rehearsed (§4.7).
- **The holding README's two new paragraphs** (the model outputs; `biomaGUNE MJ` not included) are my wording.
- **(C) rows A2 left to holding** (202 "other" plus the named groups) are not re-read: the readings are A2's four, as
  accepted.
- **An observation for the registry:** 5 rows of `registry_raw.csv` say `checksum_present = N`, but every acquisition
  folder has a `checksums.json` (the live read found one for all 27,120).
