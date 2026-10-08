# M. Jesús's drive: the raw images from instruments outside gjesus3's set — plan, gate and rehearsal

**Status:** 🔶 GATED; **Ryan's go 2026-10-08 (~19:25)** for the XMIC ingest with both label readings and researcher
`MJ`, and for part B of the placement; configs re-generated to that ruling, every check and dry run re-run;
**nothing written to production** · **Date:** 2026-10-08
**Branch:** `feat/drive3-foreign-raw` · worktree `gjesus3-dev\drive3-foreign-raw`
**Runs next:** the XMIC batches X01 (alone first), X02, X03; the placement's part A any time; part B after X03.
**Not while another registry writer runs** (the MRI archive ingest).
**Built on:** stream C's gate [`drive3_czi_gate.md`](drive3_czi_gate.md) (its tools, its rules, §1.7 lists these files in
[`drive3_czi_out_of_scope.csv`](drive3_czi_out_of_scope.csv)); stream P's later-batch path, as `biomaGUNE MJ` used it
([`drive3_biomagune_mj_gate.md`](drive3_biomagune_mj_gate.md)); the answers of 2026-10-08
([`drive3_questions_for_mjesus.md`](drive3_questions_for_mjesus.md), Q9 and Q10); the `XMIC` precedent
([`03_RAW_STORAGE.md`](../mfb-rdm-docs/03_RAW_STORAGE.md) §3.2, [`09_MODALITIES.md`](../mfb-rdm-docs/09_MODALITIES.md) §1.6).
**Evidence (regenerable, not backed up):** `D:\projects\gjesus3\drive3_streams\xmic\` (`catalog\`, `plan\`, `local\`, `farm\`,
`labels\`, `varL\`, `rehearsal_nas\`, `rehearsal_nas_ruled\`, `rehearsal_logs*\`, `placement\`).
**Read-only throughout:** `J:\gjesus3-data\` was only read (dry runs included); `J:\_staging_drive3_MJ\` was only read; the
animal-facility DB got SELECTs only. GB = 10⁹ bytes.

## Summary

1. **Biodonostia's Axioscan 7 (#4661000340) → `XMIC`: 83 acquisitions, 114.0 GB, in 3 batches:** X01 the pilot (7 files,
   4.0 GB), X02 with a project (69, 103.3 GB), X03 blank (7, 6.7 GB). From the drive's 144 copies (116 distinct contents,
   153.9 GB): **none is in production** (by SHA-256 against every live `checksums.json`, and no production microscopy
   acquisition carries this serial); 20 same-name re-saves and 1 interrupted copy are dropped; 12 pixel-identical copies
   under another name go to their parents' project folders as non-raw material after the ingest (§1.3).
2. **Values:** `instrument_model` `Axioscan 7`; **`data_source` `collaborator:Biodonostia`** (the field's vocabulary has two
   forms, `internal` and `collaborator:<origin>`; this is an external instrument; "no formal collaboration" is in the
   note); **`researcher` `MJ`** on all 83 (Ryan's ruling: production's token for M. Jesús on this drive); **`operator`
   blank**; every row's note: "Elena (a PhD student of the group co-supervised at Biodonostia; surname not recorded)
   scanned M. Jesus's slides, with no formal collaboration (Irene, 2026-10-08)" (§1.4).
3. **The slides decide the projects (Ryan, 2026-10-08).** The scanner photographs each slide's paper label and keeps the
   photo inside the `.czi`; all 116 were read. Readings **L1** (a blank file takes its label's protocol and animal) and
   **L2** (the 25 `0522 Biodonostia` scans, labelled `1422`, take `1422` over their folder's Confirmed `0522`; **the first
   reading to overrule a Confirmed claim**) are accepted. **Projects: `0424` 23, `1019` 15, `1422` 25, `0522` 11, each file
   with its animal (74 files, 45 animals); 9 blank** (labels without a protocol). By the claim rule alone they would have
   been `0424` 16, `1019` 5, `0522` 5 and 57 blank (20 of them a `0522`-vs-`1422` conflict) (§2).
4. **Same-acquisition groups, decided before ingest:** 32 groups, 65 members, 0 undecided. Stream C's pixel check refuses
   JPEG XR, so a new tool (`x_groups.py`) proves identity from the stored tile payloads (one set with a moved coordinate
   origin) and relates one interrupted copy by its subblocks (§1.3).
5. **Leica TCS SP8 (#8100000207), biomaGUNE's former confocal: not registered** (no `.lif` reader or code); its 26 files
   (6.72 GB) go to `AE-biomaGUNE-1121` as project material, beside the PNG exports batch 1 placed there, with a README
   note. **The `.czi` with no instrument metadata** (`m204lung.czi`, 2 copies) is **nowhere yet**; no claim, so holding.
   That is part A of the fourth placement batch; **part B** (accepted) places the 12 renamed copies after the ingest:
   `0424` 9, `1019` 3 (§5).
6. **Every check PASS** through the engine's own resolution (`ingest_check`, 12 checks, 83 cases), and the real dry runs
   against `J:` are clean: X01 7, X02 69, X03 7 cases, 0 SKIP, 0 refused names, 0 failed (§3).
7. **Rehearsed on D:** all three batches (before the ruling: 83/83, verified, validator unchanged, re-run adds nothing),
   and the final X01 again after it (7/7, verified, re-run `Total: 0`) (§4); the placement's parts A and B, every window
   VERIFY PASS, every re-run copies nothing (§5.3). **Suite 43/43.**

---

## 1. The XMIC batch

### 1.1 The instrument, and why these files are `XMIC`

A1 read every `.czi` of the drive; 144 carry the device serial **4661000340**, stand keys `Pollux;UprightFixedStage`,
stand `Axioscan 7`, ZEN 3.7: the same model as our `ZWSI` (#4661000718), told apart only by the serial. Irene (Q9):
scanned at Biodonostia, no formal collaboration; Elena, a PhD student of the group co-supervised there, scanned
M. Jesús's samples because biomaGUNE had no Axioscan in 2024. The reference gains the entry
`EXTERNAL:Axioscan7-Biodonostia` (`tools/reference/microscopy_instruments.yaml`, serial `4661000340`), which the profile
maps to `XMIC`, exactly as `EXTERNAL:AxioImagerZ2` → `XMIC` for the Charité batch. The reference is evaluated in order;
the new entry fires on nothing else (production's audit with it: 17,161 microscopy sidecars, **0 carry this serial**;
the only "disagreements" are the 338 Charité rows, `XMIC` vs `EXTERNAL:AxioImagerZ2`, as before).

A1's table predates the entry, so the profile re-fingerprints A1's own serials / stand keys / stand against the current
reference (`refingerprint`); a row A1 had already named must come out the same, or the plan stops.

### 1.2 From the drive to the plan

| Step | Files | GB | Where it is listed |
|---|---:|---:|---|
| copies with serial 4661000340 | 144 | | `a1\microscopy_files.csv` |
| **distinct contents** | **116** | 153.9 | |
| − in production by SHA-256 (the live index of 2026-10-08 17:13, 647,057 hashes; the registry unchanged since 2026-10-07 18:21) | 0 | | `excluded.csv` |
| − same-name, pixel-identical re-saves (the copies in `biomaGUNE MJ\Manosa and 2DG Male_Proyecto 1422\Raw data\Microscopio\Microscopio-biodonostia`, re-saved by M. Jesús on 2024-10-28; gate R2) | 20 | 12.3 | `resave-within-plan` |
| − an interrupted copy (`Histologia_ratones_viejos\HE\2025_02_14__5234.czi`, 1.46 of 2.31 GB) | 1 | 1.5 | `resave-within-plan` |
| − pixel-identical copies under another name → **non-raw, the project folder** (Ryan 2026-10-01; part B) | 12 | 26.1 | `nonraw_derived.csv`; [`drive3_xmic_nonraw_for_placement.csv`](drive3_xmic_nonraw_for_placement.csv) |
| = **the plan** | **83** | **114.0** | `expected.csv`; [`drive3_xmic_plan.csv`](drive3_xmic_plan.csv); configs `tools/configs/drives3x_2026-10/` |

Acquisitions 2024-10-24 → 2025-02-19 (2024: 42, 2025: 41). The dropped re-saves' paths go into the kept file's
`other_copies` and notes, as stream C did.

### 1.3 The same-acquisition groups (`x_groups.py`)

32 groups share an acquisition second (65 members). Stream C's pixel check (`c_groups.py`, `r4_groups.py`) compares
stored tile payloads **as pixels** and refuses compressed members; every one of these files is JPEG XR. What can be
proved without decoding: tiles at the same relative positions with **byte-identical stored payloads** are the same
pixels. `x_groups.py` reads every level-0 subblock of each member (no decoding) and classifies; `ingest_plan`'s
decision rules (`same_acquisition_actions`, stream C's, tested) act on the result exactly as on `c_groups.py`'s.

| Groups | Members | What the bytes show | Decision |
|---:|---|---|---|
| 20 | `0522 Biodonostia\2024_10_24__NNNN.czi` and the same name in the `1422` folder | every tile byte-identical; the `0522`-folder copy is the scanner's own save (user `zeiss`, the scan day) in 17, both are M. Jesús's re-saves in 3 | the `0522`-folder copy kept (stream C's canonical rule: outside `biomaGUNE MJ`), the `1422` copy dropped as a re-save |
| 11 | a Histologia file named for its animal (`ID2_0424_H+L 1.czi`, `ID169 II 3.czi` …) and an `escaner\…\2025_02_1x__NNNN.czi` | every tile byte-identical; the Histologia file is the scanner's save (`zeiss`, scan day), the escaner file a re-save of 2025-02-19 (`jguser` / `mjsanchez`) | the Histologia file kept; the escaner file → non-raw |
| 1 | `HE\ID1_0424_H+L.czi`, `escaner\H&E\2025_02_14__5234.czi`, `HE\2025_02_14__5234.czi` | the first two: the same 5,106 tiles, byte-identical, **every tile shifted by one offset** (ZEN moved the origin), saved at the same instant; the third cannot be opened (its directory, written last, is missing): **every one of its 7,833 whole subblocks is byte-identical to one of the escaner file's 12,590** | `ID1_0424_H+L.czi` kept (the tie broken by stream C's canonical rule); the escaner file → non-raw; the interrupted copy dropped |

Two refinements, each pinned by a test: tile sets are compared **up to one translation** (the moved origin), and rule
1b ("a truncated copy under the same name as its complete parent is dropped") also drops one named like **a complete
identical copy** of that parent (here `2025_02_14__5234.czi`), instead of sending a broken file to the project folder.
Stream C's own cases are unchanged (its tests pass as before). The decisions do not depend on the readings (re-run
after the ruling: `pixel_decisions.csv` byte-identical).

### 1.4 Per-file values, and why

| Field | Value | Why |
|---|---|---|
| `instrument` | `XMIC` | the file's own device serial (§1.1), never the folder |
| `instrument_model` | `Axioscan 7` | the stand name the file carries, written literally as the Charité batch did (`Axio Imager.Z2`); production's `ZWSI` rows say the same |
| `data_source` | **`collaborator:Biodonostia`** | 06_REGISTRIES: `internal` or `collaborator:<name>`. `internal` would say a gjesus3 instrument made the scan. Every external origin in production uses the second form (`Charite`, `CNIC`, `HPIC`, `LIONS`, `Uni-Madrid`), and 03 §3.2 / 09 §1.6 pair `XMIC` with it: it names where the acquisition was made, not a contract. That there was **no formal collaboration** is said in the note |
| `researcher` | **`MJ`** (all 83) | **Ryan, 2026-10-08**, on Irene's answer ("Elena performed these scans with MJ's samples"). `MJ` is the value production already uses for her as researcher on this drive: stream C's 3,719 Cell Observer rows (`Microscopio- MJesus Sanchez 2023\`, ruling G5) and stream N's PET/CT rows. (Drives 1+2 also carry `Maria Jesus`, 732 rows from the folder `Cell observer\Maria Jesus`; this drive's token was kept.) Profile key `people_all` |
| `operator` | blank | Ryan's ruling: Elena is named in the note only (no folder names her; her surname is not known, so none is written; production's researcher `elena`, 63 rows of PROJ-0041, is not known to be the same person) |
| `notes` | `Historical drive ingest 2026 (drive3_MJesus-MFB); external instrument: ZEISS Axioscan 7 #4661000340 at Biodonostia, where Elena (a PhD student of the group co-supervised at Biodonostia; surname not recorded) scanned M. Jesus's slides, with no formal collaboration (Irene, 2026-10-08); project / subject decided per file before ingest (tasks/drive3_foreign_raw_gate.md). Claim: …` — on a reading's rows the claim part ends `filled by reading L1` / `replaced by reading L2 (accepted 2026-10-08 Ryan …): the slide label in the file reads '…'` | the answer and the evidence, on every row and in every sidecar |
| `sample_id`, `sample_type`, subject | the file name; `tissue` with a subject; the subject from the claim (Confirmed) or the label (L1, L2), re-resolved in the facility DB | stream C's rules |

### 1.5 Projects (as committed: the claim rule plus the accepted readings)

| Project | | Files | GB | With a subject | Animals | From |
|---|---|---:|---:|---:|---:|---|
| `AE-biomaGUNE-0424` | PROJ-0002 | 23 | 51.5 | 23 | 8 | 16 Confirmed (`IDn_0424_…`), 7 L1 (`SR\IDn H + L 3`) |
| `AE-biomaGUNE-1019` | PROJ-0006 | 15 | 20.1 | 15 | 6 | 5 Confirmed (`ID16n_1019_II …`), 10 L1 (`ID162_1019II`, `SR` and `Tricrómico` `ID16n II`) |
| `AE-biomaGUNE-1422` | PROJ-0013 | 25 | 15.3 | 25 | 20 | 25 L2 (`0522 Biodonostia`) |
| `AE-biomaGUNE-0522` | PROJ-0011 | 11 | 19.7 | 11 | 11 | 11 L1 (`BIOMAGUNE`, labelled `0522`) |
| **blank** | | 9 | 7.3 | | | the label names no protocol: `BIOMAGUNE` `202–209 II` (6), `SR` `160–162 II` (3) |
| **all** | | **83** | **114.0** | **74** | **45** | Confirmed 21, READING-L1 28, READING-L2 25, no claim 9; 0 conflicts |

Every target exists and is active; no project is created or reopened. Every planned row's project and subject equal its
slide label's (74), or its label names no protocol (9) (`plan\label_check.csv`).

### 1.6 Batches and time

| Batch | What | Files | GB | Projects | Subject rows | Time at 31–39 MB/s |
|---|---|---:|---:|---|---:|---:|
| **X01** | the pilot: per project a file with its subject (`0424`, `1019`, `0522`, and two `1422` L2 files of animal 49), two blank files | 7 | 4.0 | `0424` 1, `1019` 1, `1422` 2, `0522` 1, blank 2 | 5 | 2–3 min |
| X02 | with a project | 69 | 103.3 | `0424` 22, `1019` 14, `1422` 23, `0522` 10 | 69 | 45–57 min |
| X03 | blank project | 7 | 6.7 | — | 0 | 3–4 min |

The deepest farm path is 142 characters. No batch creates or reopens a project.

---

## 2. The slide labels, and the two readings (accepted: Ryan, 2026-10-08)

### 2.1 What the labels say

A whole-slide scanner photographs the slide's paper label; ZEN stores the photo in the `.czi` (attachment `Label`). Each
of the 116 contents' label was extracted read-only from the staged copy and read by eye from contact sheets
(`D:\…\xmic\labels\sheet_01.png` … `sheet_10.png`, index `label_index.csv`); the readings are committed in
[`tools/configs/drives3x_2026-10/label_readings.csv`](../tools/configs/drives3x_2026-10/label_readings.csv) (label text,
protocol, animal, and the reading that uses it). One file has no readable label (the interrupted copy, dropped). The
coordinator checked sheets 1 and 4 against the transcription before the ruling.

| Folder | Label (as read) | Facility DB |
|---|---|---|
| `0522 Biodonostia` (25) and its 20 copies in the `1422` folder | `IDnn HL` / H&E / **`1422`**, nn = 43–62 | 1422's animals 43–62 exist, all male ("Manosa and 2DG **Male**"); 0522 also has animals with these numbers (of those looked up, 46–50, 55, 56 and 62 are female), so the number alone cannot decide |
| `BIOMAGUNE` (17) | 11: `ID15/16/20/21/25/26 H` / `0522 H&E` (`3mo`) and `ID46/48/49/55/56 0522` / `lung heart` / H&E; 6: `202/203/204/207/208/209 II` / `HE` / `NMX` or `SuHx`, **no protocol** | the 11 exist in 0522 |
| `Histologia_ratones_viejos\HE`, `\Tricrómico` and their escaner copies | `IDn H+L` / H&E or Masson / `0424`; `ID16n II` / `P1019-3` / H&E or Masson / `04/23` | 0424's 1–4, 10, 12–14 and 1019's 160–162, 167–169 exist |
| `Histologia_ratones_viejos\SR` | `IDn H+L` / PR / `0424`; `ID167/168/169 II` / `1019-3` / `18mo`; `160/161/162 II` / PR, **no protocol** | as above |

**Every Confirmed claim that has a label agrees with it on protocol and animal (21 of 21), except the 5 `0522`-only
files, whose labels read `1422`.** Corroboration for `1422`: production's `AE-biomaGUNE-1422` microscopy already holds
slides of exactly animals 43–62 (182 files named `IDnnHL-1422_…`, the same `HL` heart-and-lung slides); M. Jesús filed
20 of these scans under `Manosa and 2DG Male_Proyecto 1422`; the `0522` claim (CL-0741) is a folder name "confirmed
WITHOUT animal-level evidence (dates only)".

### 2.2 The readings (`tools/configs/drives3x_2026-10/readings.csv`: `accepted`, `2026-10-08 Ryan`)

- **L1 (`label`): a blank file (no claim or (C)) takes its label's protocol and animal.** Only where the label names
  both; a label without a protocol (9 planned files) is never used; a Confirmed claim is never touched. 28 planned files.
- **L2 (`label-overrule`): the 25 `0522 Biodonostia` scans take `1422` and the label's animal**, replacing the folder's
  Confirmed `0522`. **This is the first reading to overrule a Confirmed claim** (R5 and A2's readings filled (C) or
  no-claim files only), which is why it is a reading of its own. Without it, 20 scans would have stayed blank as
  conflicts and 5 would have gone to `0522` against their own labels.

The mechanism is R5's (`ingest_plan.apply_readings`, tested), applied before the same-acquisition groups, so the kept
copy of each `0522`/`1422` pair carries `1422` and no conflict arises. Each row's note records it, e.g.
"Claim: CONFIRMED AE-biomaGUNE-0522, replaced by reading L2 (accepted 2026-10-08 Ryan (via the coordinator, who checked
contact sheets 1 and 4)): the slide label in the file reads 'ID49 HL * / H&E / 1422'."

### 2.3 Before and after the ruling

| | Claim rule alone (the gate's first build) | As committed (L1 + L2, researcher `MJ`) |
|---|---|---|
| `0424` / `1019` / `1422` / `0522` | 16 / 5 / 0 / 5 | 23 / 15 / 25 / 11 |
| blank | 57 (37 no claim, 20 conflicts) | 9 (no claim; the label names no protocol) |
| rows with a subject / animals | 21 / 13 | 74 / 45 |
| batches X01 / X02 / X03 | 5 / 23 / 55 | 7 / 69 / 7 |
| researcher | blank | `MJ` |
| part B destinations | `0424` 8, holding 4 | `0424` 9, `1019` 3 |

The claim rule's own verdict and project of every row stay listed beside the final ones in
[`drive3_xmic_plan.csv`](drive3_xmic_plan.csv) (`claim_rule_verdict`, `claim_rule_project`).

---

## 3. The invariants (the committed configs)

`ingest_check.py --profile drive3x_2026-10` runs the engine's own dry-run resolution (`config.expand_batch`) on every
generated config against the live registry and compares every case with the plan, file by file
(`plan\check_report.json`, `plan\check_cases.csv`; log `plan\check_ruled.log`). **All PASS, 83 cases, 0 engine skips,
0 warnings, 0 extraction failures.**

| # | Invariant | Result |
|---|---|---|
| 1 | the planned set = A1's serial-4661000340 contents (re-fingerprinted) minus production minus the listed exclusions; engine cases == plan rows | PASS: 83 = 83 (114.0 GB) |
| 2 | per file: instrument, project, researcher, operator, subject, data source, model, sample, link name, group, notes, date | PASS: 0 mismatches over 83 |
| 3 | no SHA-256 in production; the index newer than the registry | PASS: 0; index 17:13 today, registry last written 2026-10-07 18:21. Re-checked against the live index of 19:19 (§5.2): **0 of all 172 out-of-scope copies** (Axioscan, Leica, processed) are in `/raw/` |
| 3b / 3c | no re-save of a production acquisition, no two planned files the same acquisition, no production row at a planned file's instrument and second | PASS: 0 / 0 / 0 |
| 3d | every same-second group decided for exactly its membership | PASS: 32 groups |
| 3e | no planned file truncated; farm paths fit MAX_PATH | PASS: 83 directories read, deepest 142 |
| 4 | dates | PASS: 2024 42, 2025 41; none blank or today |
| 5 | projects | PASS: none created; `0424` 23, `0522` 11, `1019` 15, `1422` 25, each existing and active |
| 6 | subjects only where the claim or an accepted reading settles them, in the row's own protocol, each re-resolving in the facility DB (fresh SELECTs) to itself | PASS: 74 rows, 45 animals |
| 7 | XMIC: 83 rows, model `Axioscan 7`, source `collaborator:Biodonostia` | PASS |
| 8 | link names unique and free in each project's live `raw_linked\` | PASS: 74 planned, 0 taken |
| 9 | the local mirror is the drive's bytes | every file hashed as read from `J:` and kept only on a drive-manifest match: 116 of 116, 153.9 GB, 0 bad; **§6.1 re-hashes the 83 from disk before X01** |

**The real dry runs** (`ingest_raw.py --dry-run --nas-root J:\gjesus3-data`, read-only, 2026-10-08 19:26): X01 `Batch: 7
cases`, X02 69, X03 7; 0 SKIP, 0 refused link names, `Total` = `Success` = the case count, `Failed: 0`
(`plan\dryrun_ruled_Xnn.log`).

---

## 4. The rehearsal and its idempotent re-run

**Where:** scratch NAS roots on D:, made by `ingest_plan.py --profile drive3x_2026-10 scratch`: production's registries
copied read-only (35,613 rows), and for each target project a `raw_linked\` with a zero-byte stand-in for each of
production's link names, so a collision would be real. **What:** the real engine and the generated configs, exactly as
production runs them.

**Before the ruling, all three batches in order** (the claim-rule configs: the same code paths; `…\xmic\rehearsal_nas\`,
drivers `scratch\rehearse.sh X01 X02` then `rehearse_more.sh X03 -- X01 X02 X03`, logs `rehearsal_logs\`):

| Step | X01 (5 files) | X02 (23) | X03 (55) |
|---|---|---|---|
| pass 1 (`--refresh-index projects`) | exit 0, 68 s; `Success: 5`, `Failed: 0`; 0 SKIP | exit 0, 970 s; `Success: 23`, `Failed: 0`; 0 SKIP | exit 0, 1,510 s; `Success: 55`, `Failed: 0`; 0 SKIP |
| WARN lines | 4 = the two sidecar sentinels (`condition.is_control` null, `anatomy.region` empty) × 2 subject rows | 38 = × 19 | 0 (no subject) |
| `ingest_verify` (all three) | **83 planned, 83 registry rows from these configs; `rows`, `fields`, `checksum`, `sidecar`, `link`, `registry`: all PASS (0)** | | |
| `c_manifest_check` (from the drive manifest, without the plan) | **83 rows against the 621,969-row manifest; `rows`, `manifest`, `link`, `orphans`: all PASS (0)** | | |
| the validator | the same 35,613 `ERROR:` lines before X01 and after X03, line for line (each a production acquisition whose folder the scratch root does not have): **the new rows add none** | | |
| pass 2 (the same commands) | `Total: 0` (5 already in the registry) | `Total: 0` (23) | `Total: 0` (55) |

**After the ruling, the final X01** (`…\xmic\rehearsal_nas_ruled\`, `scratch\rehearse_ruled_X01.sh`, logs
`rehearsal_logs_ruled\`): `Success: 7`, `Failed: 0`, 0 SKIP, **10 WARN** (the two sentinels × 5 subject rows);
`ingest_verify` and `c_manifest_check` all PASS; validator `ERROR:` lines unchanged; re-run `Total: 0`. Its rows, for
instance: `ACQ-20241025-XMIC-001` = `0522 Biodonostia\2024_10_24__4469-1.czi` → `PROJ-0013`, subject
`49-AE-biomaGUNE-1422`, researcher `MJ`, operator blank, note ending with reading L2 and the label;
`ACQ-20241111-XMIC-001` (`BIOMAGUNE\…4569`) → `PROJ-0011`, `25-AE-biomaGUNE-0522` by L1; `ACQ-20250214-XMIC-001`
(`ID13_0424_H+L 1.czi`) → `PROJ-0002`, `13-AE-biomaGUNE-0424` (Confirmed), its sidecar with the facility-DB subject block
(`Mus musculus`, F, born 2023-05-25) and `user_supplied.data_source` `collaborator:Biodonostia`.

**Not rehearsed:** the SMB side (the engine and runner are the ones drives 1+2 and stream C ran into `J:`); the final
X02 and X03 (the same configs as X01 and as the pre-ruling run, other values). The scratch roots (≈ 118 GB) can be
deleted.

---

## 5. The placement batch (the fourth of stream P's tool)

### 5.1 What it places

| Part | Files | GB | Destination | Why |
|---|---:|---:|---|---|
| **A, any time** | 26 Leica (`.lif` 17, `.lifext` 9) | 6.72 | `AE-biomaGUNE-1121\working\historical_drives\MJesus-MFB\Proyecto 1121 London\Experimentos\Histologia\…` | Irene (Q10): biomaGUNE's own former Leica TCS SP8, "the microscope that we used to use"; gjesus3 has no `.lif` reader or instrument code, so not registered. The claim `Proyecto 1121 London` (CL-2441, Confirmed); 1121 active since its 2026-10-06 reopen. The files land in batch 1's folders, beside the PNG exports made from them (`Project.lif - Series020.png` …) |
| **A, any time** | 2 copies of `m204lung.czi` (the `czi-processed` file) | 0.00 | the holding folder, in the drive's structure | **Where it was:** nowhere. Stream C left it out of scope (no hardware or experiment block: not an acquisition record), A2 classed it raw and left it to A1, and no placement manifest (batch 1, M1 release, P2a/P2b, batch 3, the close-out of 19:02) has it. No claim (`Machos vs Hembras\…`): the holding folder, reason `no claim` (mappable in the 2b round); its sibling `m204lungPOL.czi` is `ACQ-20220711-CELL-007` (no project) |
| **B, after X01–X03** (accepted 2026-10-08) | 12 pixel-identical copies under another name (§1.3) | 26.14 | beside their parents: `AE-biomaGUNE-0424` 9 (22.38 GB), `AE-biomaGUNE-1019` 3 (3.76 GB) | Ryan's rule (2026-10-01): a renamed re-save goes to the project folder; each is tied to its parent's new ACQ-ID, which exists only after the ingest |

The 1121 tree's `README.txt` gains a note (appended; every other tree keeps its text byte for byte):

```
Raw Leica confocal files under MJesus-MFB\ (not registered)
  The .lif and .lifext files under MJesus-MFB\Proyecto 1121 London\
  Experimentos\Histologia\ are raw confocal images from biomaGUNE's former
  Leica TCS SP8 microscope (serial 8100000207). They are kept here, byte for
  byte, as project material: gjesus3 does not register them, because it has
  no reader for Leica .lif files and no instrument code for that microscope.
  The .png files named after a .lif are exports made from it.
```

### 5.2 Dedup and invariants

`x_placement.py lists` builds part A's hand-over list from stream C's out-of-scope list and A2's table (each row's
bytes equal both); `p_plan.py handover` checks every row against the drive manifest (the D: copy is byte-identical to the
staged one), refuses a path an earlier batch decided (every earlier manifest given, **including the close-out handover
of 19:02**, written to production at 19:23), refuses bytes in `/raw/` and plans destinations with the shared rule against
the live trees: **28 rows: `place` 26, `holding` 2; refused 0; destinations already present 0; longest UNC path 219**
(13 files land in folders batch 1 shortened, e.g. `ki67 and som~8108`). Built with and without the close-out manifest,
and twice: byte-identical every time (`placement\batch4a\placement_manifest.csv`, SHA-256
`18e966cee9ea171b0449ca714a701e2c361cb51c181d396107f40de34cb75baf`; the list `89e291e2…`; the close-out touched holding,
`0522`, `1123`, `0320`, `1422`, `0619` and `0118`, none of part A's files). Against **live** `/raw/` (`p_verify.py
raw-dedup`, 2026-10-08 19:06–19:19, every acquisition's `checksums.json`: 35,613 acquisitions, 647,057 files, none hashed
directly, none missing): `RAW-DEDUP PASS: 0 of the 28 rows copied now or held are in /raw/`.

Part B planned against the live trees with the committed plan (parents from the XMIC rehearsal's registry, every earlier
manifest incl. part A's and the close-out's): `handover (X): 12 files {'place': 12}; refused 0; destinations already
present: 0` (`placement\batch4b_ruled_dry\`).

### 5.3 Rehearsal (D:, source the real staged copy on J:)

Rehearsal roots: `p_verify.py snapshot` of the live trees; each window snapshotted again as its before-state, then the
§6 commands with `--nas` = the root (logs `placement\rehearsal_batch4a.log`, `rehearsal_batch4b.log`).

| Window | Copied | `p_verify verify` (re-hash all) | Index before → after | Re-run |
|---|---:|---|---|---|
| A W1 `AE-biomaGUNE-1121` | 26 · 6.72 GB | **VERIFY PASS**: walk 0 missing / 0 extra; `_PATHMAP` 372 kept; provenance 4,546 kept, 26 added; README = the current text (its diff to the live one is exactly the note) | 3,996 → 4,022 | `skipped-identical` 26, 0 documents written |
| A W2 holding | 2 | **VERIFY PASS** | `manifest.csv` 59,483 → 59,485 (before the close-out) | `skipped-identical` 2 |
| B W `0424` (pre-ruling plan) | 8 · 19.79 GB | **VERIFY PASS** | 1,941 → 1,949; provenance 3,474 kept + 8 | `skipped-identical` 8 |
| B W holding (pre-ruling plan) | 4 · 6.35 GB | **VERIFY PASS** | 59,483 → 59,487 | `skipped-identical` 4 |

Part B was rehearsed with the claim-rule plan (8 to `0424`, 4 to holding); the ruled plan sends those 4 to `1019`
beside their parents, through the same `copy` path as the `0424` window.

---

## 6. Production: the exact commands

From the repo root (after the merge), Git Bash, `export PYTHONDONTWRITEBYTECODE=1`. **One registry writer at a time:**
not while the MRI archive ingest runs; evenings or weekends (operators ingest by day). Placement windows also append
to project provenance files: not during an ingest into the same projects. (§6.0 of the first build, the regeneration
for the readings, is done: the committed configs are the ruled ones.)

### 6.1 Once, before X01 (read-only)

```bash
python tools/drive_staging/ingest_plan.py --profile drive3x_2026-10 verify-local
#   verify-local: 83 files, 114.0 GB re-hashed from D:\...\xmic\local against ...\drive3_manifest.csv: 83 match, 0 bad
python tools/drive_staging/ingest_plan.py --profile drive3x_2026-10 farm
#   farm: 0 linked, 83 already linked, 0 errors, 0 stray files
python tools/animal_db.py --check        # OK
df -h /j                                 # stop below 1 TB free
```

### 6.2 Each XMIC batch: X01 (the pilot) alone first, then X02, then X03

```bash
bash tools/drive_staging/run_drives_batch.sh drive3x_2026-10 X01
python tools/drive_staging/drive3/c_manifest_check.py --profile drive3x_2026-10 --nas-root "J:\gjesus3-data" --batch X01
```

The runner (stream C's, unchanged; the profile gives the config, the catalog folder, the tag `drive3x` and the
provenance file `tasks/drive3_foreign_raw_ingest_provenance.csv`) stops at the first failure. The lines to see, X01
(X02 / X03 in the table below):

```
profile drive3x_2026-10, batch X01: 7 files, config tools/configs/drives3x_2026-10/drives3x_X01.yaml
PASS  1 reconciliation  (0 failures)   ... and the 11 other checks: PASS, (0 failures)
a. backup C:/Users/rtasseff/temp/gjesus3_registry_backup_<YYYYMMDD>_drive3x_X01 verified
b. target projects: AE-biomaGUNE-0424;AE-biomaGUNE-0522;AE-biomaGUNE-1019;AE-biomaGUNE-1422 | not active: none
c. dry run: Batch: 7 cases (planned 7), SKIP lines 0, refused link names 0
d. run exit=0 secs=<n>
  Total:    7
  Success:  7
  Failed:   0
PASS  rows / fields / checksum / sidecar / link / registry  (0)          (ingest_verify)
provenance: 7 rows for ['X01'] -> tasks/drive3_foreign_raw_ingest_provenance.csv
e. validator errors before <n>, after <n>                               (the same n; the ERROR lines compared too)
f. re-run: Total:    0
WARN lines in run: 10
BATCH X01 DONE
```

| Batch | `c.` dry run | `d.` run | WARN lines in run | Projects (`b.`) | Time |
|---|---|---|---:|---|---|
| X01 | `Batch: 7 cases (planned 7)` | `Total: 7`, `Success: 7`, `Failed: 0` | 10 | 0424; 0522; 1019; 1422 | 2–3 min |
| X02 | `Batch: 69 cases (planned 69)` | `Total: 69`, `Success: 69`, `Failed: 0` | 138 | 0424; 0522; 1019; 1422 | 45–57 min |
| X03 | `Batch: 7 cases (planned 7)` | `Total: 7`, `Success: 7`, `Failed: 0` | 0 | `(none)` | 3–4 min |

The WARN lines are the two sidecar sentinels on each row with a subject (5 / 69 / 0). `c_manifest_check` after each:
`batches ['Xnn']: N registry rows checked against …drive3_manifest.csv (621,969 manifest rows)`, then `PASS rows`,
`PASS manifest`, `PASS link`, `PASS orphans`. After X03, `c_manifest_check … --batch X01 --batch X02 --batch X03`:
83 rows, all PASS.

**Stop and report** on any failure; on an ACQ-ID dated today; on a project created or changed (`registry_projects.csv`
byte-identical to the backup); on `pending_subject_metadata.csv` growing (the DB went away;
`tools/recover_subject_metadata.py`); below 1 TB free.

**Half-way, resume, rollback:** exactly stream C's §4.3 (`drive3_czi_gate.md`): every landed row is a complete
acquisition; `ingest_verify --batch` lists what is missing; re-run step d unchanged (the engine skips what is in);
an orphan folder is retired with `tools/retire_acquisition.py` on approval; a whole-batch rollback removes the rows
whose `ingest_config` is the batch's config (byte-exact, or restore step a's backup if no other writer touched the
registry), their folders, links, subjects and provenance rows, then regenerate the touched `index.html`.

### 6.3 The placement, part A (any time; windows one at a time)

```bash
B='D:\projects\gjesus3\drive3_streams\xmic\placement'; M="$B\batch4a\placement_manifest.csv"; NAS='J:\gjesus3-data'
S='D:\projects\gjesus3\drive3_streams'
NP=tools/drive_staging/nonraw_placement.py; PV=tools/drive_staging/drive3/p_verify.py; PP=tools/drive_staging/drive3/p_plan.py
D=$(date +%Y%m%d)
EARLIER=(--manifest "$S\placement\manifest_check2_20261006\placement_manifest.csv"
         --manifest "$S\placement\release_M1_20261006\placement_manifest.csv"
         --manifest "$S\mri\out\p2\P2a_20261007_1053\placement_manifest.csv"
         --manifest "$S\mri\out\p2\P2b_20261007_1053\placement_manifest.csv"
         --manifest "$S\mri\out\p2\P2b_masks_20261007_1053\placement_manifest.csv"
         --manifest "$S\bmj\batch3_v2\placement_manifest.csv"
         --manifest "$S\closeout\handover_20261008_1902\placement_manifest.csv")   # + any batch written since
# 0. the manifest is still the gated one (read-only)
python $PV raw-dedup --manifest "$M" --nas "$NAS" --write-index "$B\live_raw_index_$D.csv"
#   RAW-DEDUP PASS: 0 of the 28 rows copied now or held are in /raw/ (all 28 manifest rows checked)   (≈ 14 min)
python tools/drive_staging/drive3/x_placement.py lists --out "$B\lists_check_$D"
#   foreign_handover.csv: 28 rows, 6.73 GB; {('(holding)', 'czi-processed'): 2, ('AE-biomaGUNE-1121', 'raw-microscopy'): 26}
python $PP --nas "$NAS" handover "${EARLIER[@]}" --csv "$B\lists_check_$D\foreign_handover.csv" --stream X \
    --raw-index "$B\live_raw_index_$D.csv" --out "$B\batch4a_check_$D"
#   handover (X): 28 files {'holding': 2, 'place': 26}; refused 0; destinations already present: 0
sha256sum "$B\batch4a_check_$D\placement_manifest.csv"   # 18e966ce…75baf (= the gated one), or stop and re-gate
# W1: the 1121 tree
python $PV snapshot --manifest "$M" --nas "$NAS" --project AE-biomaGUNE-1121 --to "C:\Users\rtasseff\temp\gjesus3_placement_backup_${D}_drive3_B4W1"
python $NP --out "$B\runs\W1" --nas "$NAS" copy --manifest "$M" --scratch "$B\scratch" --project AE-biomaGUNE-1121
#   DRY RUN: 26 files, 6.72 GB, 1 projects (+ 4 index documents); destinations already present: 0; longest UNC path 219
python $NP --out "$B\runs\W1" --nas "$NAS" copy --manifest "$M" --scratch "$B\scratch" --project AE-biomaGUNE-1121 --execute
#   finished: {'copied': 26}
python $NP --out "$B\runs\W1" --nas "$NAS" verify --manifest "$M" --project AE-biomaGUNE-1121      # OK, 0 mismatches
python $PV verify --manifest "$M" --nas "$NAS" --snapshot "C:\Users\rtasseff\temp\gjesus3_placement_backup_${D}_drive3_B4W1" \
    --project AE-biomaGUNE-1121 --rehash all
#   VERIFY PASS: 1 trees, 26 files; _INDEX 3,996 -> 4,022 (plus anything another writer added); README the current text
# W2: the holding folder
python $PV snapshot --manifest "$M" --nas "$NAS" --holding --to "C:\Users\rtasseff\temp\gjesus3_placement_backup_${D}_drive3_B4W2"
python $NP --out "$B\runs\W2" --nas "$NAS" holding --manifest "$M" --scratch "$B\scratch"            # DRY RUN: 2 files; 'no claim': 2
python $NP --out "$B\runs\W2" --nas "$NAS" holding --manifest "$M" --scratch "$B\scratch" --execute  # {'copied': 2}
python $PV verify --manifest "$M" --nas "$NAS" --snapshot "C:\Users\rtasseff\temp\gjesus3_placement_backup_${D}_drive3_B4W2" --holding --rehash all
#   VERIFY PASS (manifest.csv 59,555 -> 59,557: the live count after the close-out, read 19:30)
```

**If something goes wrong:** batch 3's §9.3 applies unchanged: re-run the copy (in-place files are re-hashed and
skipped); a `COLLISION` is a stop (nothing is overwritten); to abandon a window remove only its `copied` files and
restore the four documents per tree from the step's snapshot; never remove a `MJesus-MFB\` folder.

### 6.4 The placement, part B (after X01–X03 are in and verified)

```bash
python tools/drive_staging/drive3/x_placement.py nonraw --out "$B\listsB_$D"
#   xmic_nonraw_handover.csv: 12 rows {'AE-biomaGUNE-0424': 9, 'AE-biomaGUNE-1019': 3}
python $PP --nas "$NAS" handover "${EARLIER[@]}" --manifest "$M" --csv "$B\listsB_$D\xmic_nonraw_handover.csv" \
    --stream X --raw-index "$B\live_raw_index_$D.csv" --out "$B\batch4b_$D"
#   handover (X): 12 files {'place': 12}; refused 0; destinations already present: 0
```

`nonraw` refuses to run before every parent is registered. Then the window procedure of 6.3 with
`M="$B\batch4b_$D\placement_manifest.csv"`, one window per tree: `AE-biomaGUNE-0424` (`copy` dry run: 9 files, 22.38 GB;
`_INDEX` 1,941 → 1,950) and `AE-biomaGUNE-1019` (3 files, 3.76 GB; `_INDEX` 13,264 → 13,267); no holding window.

---

## 7. Rulings, and what is not settled

| # | What | Ruling |
|---|---|---|
| G1 | Ryan's go for the XMIC ingest | **Given 2026-10-08 (~19:25)**; X01 alone first |
| G2 | L1 and L2 (§2) | **Accepted (Ryan, 2026-10-08)**; the coordinator checked contact sheets 1 and 4. L2 is the first reading to overrule a Confirmed claim |
| G3 | `data_source` `collaborator:Biodonostia` for an informal arrangement | kept: the field names the acquisition's origin; the note says "no formal collaboration" |
| G4 | People | **`researcher` `MJ` on all 83; `operator` blank; the note names Elena (Ryan, 2026-10-08)**. A surname for Elena, if it arrives, is a by-hand change later |
| G5 | The 12 pixel-identical copies under another name (26.1 GB) | **Part B accepted (Ryan, 2026-10-08)**: placed beside their parents after the ingest |
| G6 | The 9 files whose label names no protocol: `BIOMAGUNE` `202/203/204/207/208/209 II` (production names these animals `ID202II_0619` …, in `0619`) and `SR` `160/161/162 II` (the same animals' H&E and Masson slides read `P1019-3`) | blank, listed in [`drive3_xmic_plan.csv`](drive3_xmic_plan.csv) for the assign workbook |
| G7 | Irene offered to say which `0522` images are worth keeping ("some were also imaged by Marta at biomaGUNE") | everything raw is registered regardless; her review can mark duplicates later |

**Not settled here:**
- **The label readings are a person's reading of handwriting** (contact sheets on `D:\…\xmic\labels\`); each row's note
  quotes the label it used, so a misread one can be found and changed by hand.
- **Some slides were scanned twice:** `ID43` twice on 2024-10-24 (`4445`, `4465`), and 46, 47, 49 and 57 again the next
  morning (the `-1` scans). Each scan is its own acquisition (another second, other pixels), so each is registered.
- **`UserName` `zeiss`** in the scanner's saves is the scanner's account, not a person.

---

## 8. What changed in the code

| File | Change | Why |
|---|---|---|
| `tools/reference/microscopy_instruments.yaml` | entry `EXTERNAL:Axioscan7-Biodonostia`, serial `4661000340` | the instrument, by its serial (§1.1) |
| `tools/drive_staging/ingest_plan.py` | profile **`drive3x_2026-10`**; `XMIC_MODEL` / `XMIC_SOURCE` and the pilot's size per profile (drives 1+2 keep theirs); `a1_instrument` (re-fingerprint, `refingerprint`); `people_all` (a ruling for every file: researcher `MJ`); bucket names from the instrument (stream C's stay `CELL-…`); YAML header per profile and an `XMIC` paragraph; label readings (`label`, `label-overrule`, `label_readings.csv`) beside the folder kinds; `label_check.csv`; rule 1b's extension (§1.3); `plan --config-dir`, `--farm` (a variant's check) | §1–§2 |
| `tools/drive_staging/ingest_check.py` | check 1 re-derives with `a1_instrument`; check 7 text | |
| `tools/drive_staging/drive3/x_groups.py` (new) | the same-acquisition facts for compressed `.czi`: stored payloads, translation, the interrupted-copy walk | §1.3 |
| `tools/drive_staging/drive3/c_manifest_check.py` | `--profile` (default stream C's) | the independent check for the XMIC batches |
| `tools/drive_staging/drive3/x_placement.py` (new) | the hand-over lists of the fourth placement batch (part A; part B from the registry) | §5 |
| `tools/drive_staging/historical_paths.py` | the `AE-biomaGUNE-1121` README note | §5.1 |
| `tools/configs/drives3x_2026-10/` (new) | `drives3x_Xnn.yaml`, `cases_Xnn.csv`, `batches.csv` (generated, the ruled plan); `readings.csv` (L1, L2 accepted 2026-10-08), `label_readings.csv` (the labels as read) | |
| `tools/test_drive3_foreign_raw.py` (new); `tools/test_drive_catalog.py` | the profile (incl. `people_all`), re-fingerprint, `x_groups` classification (incl. the measured triple), rule 1b, label readings, the placement lists, the README note; the fingerprint of the new serial | |
| `tasks/drive3_xmic_plan.csv`, `tasks/drive3_xmic_nonraw_for_placement.csv` (new) | the 83 planned rows (final values, the label, and the claim rule's own verdict and project) and the 12 non-raw copies | the record; the blank rows feed the assign workbook |
| `mfb-rdm-docs/09_MODALITIES.md` §1.6; `tools/INDEX.md` | `XMIC`'s second instance (🔶, gated, not ingested) and how it is recognised; the tools rows | the spec names the reference entries the ingest relies on |

Stream C's frozen profile is untouched in behaviour (`refingerprint` off, no `people_all`; its suite passes unchanged).

## 9. Reproducing it

From the worktree root, `PYTHONDONTWRITEBYTECODE=1`; read-only on `J:`; writes under `D:\…\xmic\` and, for the configs
and lists, the repo.

```bash
P="--profile drive3x_2026-10"
python tools/drive_staging/catalog.py production --out "D:\projects\gjesus3\drive3_streams\xmic\catalog"
python tools/drive_staging/ingest_plan.py $P plan                  # pass 1: 116 candidates, 32 groups to check
python tools/drive_staging/ingest_plan.py $P localize              # 116 files, 153.9 GB, J: -> D:, hashed (≈ 28 min)
python tools/drive_staging/drive3/x_groups.py all                  # facts (≈ 18 min), the interrupted-copy walk, classify
python tools/drive_staging/ingest_plan.py $P plan                  # pass 2: 83 planned; readings_applied {'L1': 40, 'L2': 25}
python tools/drive_staging/ingest_plan.py $P configs
python tools/drive_staging/ingest_plan.py $P farm --prune
python tools/drive_staging/ingest_check.py $P
bash D:/projects/gjesus3/drive3_streams/xmic/scratch/rehearse_ruled_X01.sh       # §4 (the pre-ruling run: rehearse.sh, rehearse_more.sh)
bash D:/projects/gjesus3/drive3_streams/xmic/placement/build_batch4a.sh          # §5.2 (with a suffix: the determinism check)
bash D:/projects/gjesus3/drive3_streams/xmic/placement/rehearse_batch4a.sh       # §5.3; rehearse_batch4b.sh after an XMIC rehearsal
```

The labels: scripts extracted each content's `Label` attachment from the staged copy and tiled the contact sheets into
`D:\…\xmic\labels\`; `label_readings.csv` holds what was read from them.
