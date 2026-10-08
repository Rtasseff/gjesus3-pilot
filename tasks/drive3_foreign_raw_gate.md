# M. Jesús's drive: the raw images from instruments outside gjesus3's set — plan, gate and rehearsal

**Status:** 🔶 BUILT, DRY-RUN AND REHEARSED, for the coordinator's gate; **nothing written to production** · **Date:** 2026-10-08
**Branch:** `feat/drive3-foreign-raw` · worktree `gjesus3-dev\drive3-foreign-raw`
**Needs before production:** the coordinator's gate and rulings (§7), then **Ryan's go for each XMIC batch** (an ingest);
the placement windows are copies, the coordinator's to approve. **Not while another registry writer runs** (the MRI
archive ingest).
**Built on:** stream C's gate [`drive3_czi_gate.md`](drive3_czi_gate.md) (its tools, its rules, §1.7 lists these files in
[`drive3_czi_out_of_scope.csv`](drive3_czi_out_of_scope.csv)); stream P's later-batch path, as `biomaGUNE MJ` used it
([`drive3_biomagune_mj_gate.md`](drive3_biomagune_mj_gate.md)); the answers of 2026-10-08
([`drive3_questions_for_mjesus.md`](drive3_questions_for_mjesus.md), Q9 and Q10); the `XMIC` precedent
([`03_RAW_STORAGE.md`](../mfb-rdm-docs/03_RAW_STORAGE.md) §3.2, [`09_MODALITIES.md`](../mfb-rdm-docs/09_MODALITIES.md) §1.6).
**Evidence (regenerable, not backed up):** `D:\projects\gjesus3\drive3_streams\xmic\` (`catalog\`, `plan\`, `local\`, `farm\`,
`labels\`, `varL\`, `rehearsal_nas\`, `rehearsal_logs\`, `placement\`).
**Read-only throughout:** `J:\gjesus3-data\` was only read (dry runs included); `J:\_staging_drive3_MJ\` was only read; the
animal-facility DB got SELECTs only. GB = 10⁹ bytes.

## Summary

1. **Biodonostia's Axioscan 7 (#4661000340) → `XMIC`: 83 acquisitions, 114.0 GB, in 3 batches** (X01, a 5-file pilot;
   X02 23 files with a project; X03 55 blank). From the drive's 144 copies (116 distinct contents, 153.9 GB): **none is in
   production** (by SHA-256 against every live `checksums.json`, and no production microscopy acquisition carries this
   serial); 20 same-name re-saves and 1 interrupted copy are dropped; 12 pixel-identical copies under another name go to
   the project folder as non-raw material (§1.3).
2. **Values:** `instrument_model` `Axioscan 7`; **`data_source` `collaborator:Biodonostia`** (the field's vocabulary has
   two forms, `internal` and `collaborator:<origin>`; this is an external instrument; "no formal collaboration" is in
   the note); **`operator` blank, `researcher` blank**, stream C's practice (a person only from a folder that names
   one); **every row's note** says who scanned it: "Elena (a PhD student of the group co-supervised at Biodonostia;
   surname not recorded) scanned M. Jesus's slides, with no formal collaboration (Irene, 2026-10-08)" (§1.4).
3. **Projects, by the claim rule alone (as committed):** `0424` 16 (each with its animal), `1019` 5 (with animal),
   `0522` 5 (no animal), **blank 57**: 37 no claim, and **20 conflicts**: the same 20 scans sit in `Microscopio
   biodonostia\0522 Biodonostia` (claim 0522) and in `biomaGUNE MJ\Manosa and 2DG Male_Proyecto 1422\…` (claim 1422).
4. **The slides say which project they are.** The scanner photographs each slide's paper label and keeps the photo
   inside the `.czi`. Read for all 116 contents: **the 25 `0522 Biodonostia` scans are labelled `1422`** (animals ID43–62,
   `HL`, H&E; production's own `1422` microscopy holds exactly these 20 animals, 182 files named `IDnnHL-1422_…`), and 74
   of the 83 planned files name a protocol and an animal. **Two readings are proposed, not applied (§2):** L1 fills a blank
   file from its label; L2 replaces the `0522` folder claim of those 25 by the label's `1422`. With both: `0424` 23,
   `1019` 15, `1422` 25, `0522` 11, blank 9, conflicts 0, every subject re-resolved in the DB (built and checked, §2.3).
   **Recommended: accept both.**
5. **Same-acquisition groups, decided before ingest:** 32 groups, 65 members, 0 undecided. Stream C's pixel check
   refuses JPEG XR, so a new tool (`x_groups.py`) proves identity from the stored tile payloads; it found 32 identical
   pairs or sets (one with a moved coordinate origin) and one interrupted copy (§1.3).
6. **Leica TCS SP8 (#8100000207), biomaGUNE's former confocal: not registered** (no `.lif` reader or code); **its 26
   files (6.72 GB) go to `AE-biomaGUNE-1121`** as project material (active; the claim `Proyecto 1121 London`), beside the
   PNG exports batch 1 placed there, with a README note (§5): the fourth placement batch, part A. **The `.czi` with no
   instrument metadata** (`m204lung.czi`, 2 copies) is **nowhere yet** (not registered, in no earlier placement
   manifest); it has no claim, so part A puts it in the holding folder. Part B, after the ingest, places the 12 copies.
7. **Invariants all PASS** through the engine's own resolution (`ingest_check`, 12 checks, 83 cases), and the real dry
   runs against `J:` are clean (5 / 23 / 55 cases, 0 SKIP, 0 refused names, 0 failed) (§3).
8. **Rehearsed in full on D:** all three XMIC batches, 83 of 83 ingested, verified, the validator unchanged, the re-run
   adds nothing (§4); the placement's part A (2 windows) and part B (2 windows, parents from the XMIC rehearsal), every
   window VERIFY PASS, every re-run copies nothing (§5.3).
9. **Suite 43/43** (`main` 42/42 + `test_drive3_foreign_raw.py`). Commit on the branch; nothing merged or pushed.

---

## 1. The XMIC batch

### 1.1 The instrument, and why these files are `XMIC`

A1 read every `.czi` of the drive; 144 carry the device serial **4661000340**, stand keys `Pollux;UprightFixedStage`,
stand `Axioscan 7`, ZEN 3.7: the same model as our `ZWSI` (#4661000718), told apart only by the serial. Irene (Q9):
scanned at Biodonostia, no formal collaboration; Elena, a PhD student of the group co-supervised there, scanned
M. Jesús's slides because biomaGUNE had no Axioscan in 2024. The reference gains the entry
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
| − pixel-identical copies under another name → **non-raw, the project folder** (Ryan 2026-10-01) | 12 | 26.1 | `nonraw_derived.csv`; [`drive3_xmic_nonraw_for_placement.csv`](drive3_xmic_nonraw_for_placement.csv) |
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
| 20 | `0522 Biodonostia\2024_10_24__NNNN.czi` and the same name in the `1422` folder | every tile byte-identical; the `0522` copy is the scanner's own save (user `zeiss`, the scan day) in 17, both are M. Jesús's re-saves in 3 | the `0522`-folder copy kept (stream C's canonical rule: outside `biomaGUNE MJ`), the `1422` copy dropped as a re-save |
| 11 | a Histologia file named for its animal (`ID2_0424_H+L 1.czi`, `ID169 II 3.czi` …) and an `escaner\…\2025_02_1x__NNNN.czi` | every tile byte-identical; the Histologia file is the scanner's save (`zeiss`, scan day), the escaner file a re-save of 2025-02-19 (`jguser` / `mjsanchez`) | the Histologia file kept; the escaner file → non-raw |
| 1 | `HE\ID1_0424_H+L.czi`, `escaner\H&E\2025_02_14__5234.czi`, `HE\2025_02_14__5234.czi` | the first two: the same 5,106 tiles, byte-identical, **every tile shifted by one offset** (ZEN moved the origin), saved at the same instant; the third cannot be opened (its directory, written last, is missing): **every one of its 7,833 whole subblocks is byte-identical to one of the escaner file's 12,590** | `ID1_0424_H+L.czi` kept (the tie broken by stream C's canonical rule: it carries the claim); the escaner file → non-raw; the interrupted copy dropped |

Two refinements, each pinned by a test: tile sets are compared **up to one translation** (the moved origin), and rule
1b ("a truncated copy under the same name as its complete parent is dropped") also drops one named like **a complete
identical copy** of that parent (here `2025_02_14__5234.czi`), instead of sending a broken file to the project folder.
Stream C's own cases are unchanged (its tests pass as before).

### 1.4 Per-file values, and why

| Field | Value | Why |
|---|---|---|
| `instrument` | `XMIC` | the file's own device serial (§1.1), never the folder |
| `instrument_model` | `Axioscan 7` | the stand name the file carries, written literally as the Charité batch did (`Axio Imager.Z2`); production's `ZWSI` rows say the same |
| `data_source` | **`collaborator:Biodonostia`** | 06_REGISTRIES: `internal` or `collaborator:<name>`. `internal` would say a gjesus3 instrument made the scan. Every external origin in production uses the second form (`Charite`, `CNIC`, `HPIC`, `LIONS`, `Uni-Madrid`), and 03 §3.2 / 09 §1.6 pair `XMIC` with it: it names where the acquisition was made, not a contract. That there was **no formal collaboration** is said in the note. Not chosen: a new form (`external:`, `collaborator:Biodonostia-informal`), which would extend a vocabulary the specs fix |
| `operator` | blank | stream C's practice for historical microscopy (G5): a person only from a folder that names one; no folder names Elena. A first name alone could also be confused: production already has a researcher `elena` (63 Cell Observer rows of PROJ-0041, mPCLS, 2025), not known to be the same person. Her surname is not known, so none is written. |
| `researcher` | blank | the same practice: `Microscopio- MJesus Sanchez 2023\` gave `MJ` in stream C; these folders do not name her. Irene's answer does ("M. Jesús's samples"): §7 G4 |
| `notes` | `Historical drive ingest 2026 (drive3_MJesus-MFB); external instrument: ZEISS Axioscan 7 #4661000340 at Biodonostia, where Elena (a PhD student of the group co-supervised at Biodonostia; surname not recorded) scanned M. Jesus's slides, with no formal collaboration (Irene, 2026-10-08); project / subject decided per file before ingest (tasks/drive3_foreign_raw_gate.md). Claim: …` | the answer, on every row and in every sidecar |
| `sample_id`, `sample_type`, subject | the file name; `tissue` where a subject is recorded; the claim engine's subject on Confirmed rows | stream C's rules |

### 1.5 Projects, by the claim rule (as committed)

The rule (Ryan, 2026-09-29), applied by the drives claims engine, unchanged, over A2's per-file claims:

| Project | | Files | GB | With a subject | Animals | Claim |
|---|---|---:|---:|---:|---:|---|
| `AE-biomaGUNE-0424` | PROJ-0002 | 16 | 33.7 | 16 | 8 | Confirmed: `IDn_0424_…` in `Histologia_ratones_viejos\HE` and `\Tricrómico` |
| `AE-biomaGUNE-1019` | PROJ-0006 | 5 | 6.9 | 5 | 5 | Confirmed: `ID16n_1019_II …` in `\HE` |
| `AE-biomaGUNE-0522` | PROJ-0011 | 5 | 3.0 | 0 | 0 | Confirmed by the folder `0522 Biodonostia` (CL-0741: "confirmed WITHOUT animal-level evidence (dates only)") |
| **blank** | | 57 | 70.4 | | | 37 no claim (`SR` 13, `Tricrómico` 6, `HE` 1, `BIOMAGUNE` 17); **20 conflict**: the same scans claim `0522` and `1422` |
| **all** | | **83** | **114.0** | 21 | 13 | every target exists and is active; no project created or reopened |

The 20 conflicts and the 5 `0522` files are where the rule and the files themselves disagree: §2.

### 1.6 Batches and time

| Batch | What | Files | GB | Projects | Time at 31–39 MB/s |
|---|---|---:|---:|---|---:|
| **X01** | the pilot: a project file with a subject (`0424`, `1019`), a project file without one (`0522`), a conflict-blank group keep, a no-claim file | 5 | 2.8 | 0424 0522 1019 | 2 min |
| X02 | with a project | 23 | 41.3 | 0424 0522 1019 | 18–23 min |
| X03 | blank project | 55 | 69.8 | — | 31–39 min |

(With L1 and L2 accepted the batches become X01 7 / 4.0 GB, X02 69 / 103.3 GB, X03 7 / 6.7 GB: §2.3.) The deepest farm path
is 142 characters. No batch creates or reopens a project.

---

## 2. The slide labels, and two proposed readings

### 2.1 What the labels say

A whole-slide scanner photographs the slide's paper label; ZEN stores the photo in the `.czi` (attachment `Label`). Each
of the 116 contents' label was extracted read-only from the staged copy and read by eye from contact sheets
(`D:\…\xmic\labels\sheet_01.png` … `sheet_10.png`, index `label_index.csv`); the readings are committed in
[`tools/configs/drives3x_2026-10/label_readings.csv`](../tools/configs/drives3x_2026-10/label_readings.csv) (label text,
protocol, animal, and the reading that would use it). One file has no readable label (the interrupted copy, dropped).

| Folder | Label (as read) | Facility DB |
|---|---|---|
| `0522 Biodonostia` (25) and its 20 copies in the `1422` folder | `IDnn HL` / H&E / **`1422`**, nn = 43–62 | 1422's animals 43–62 exist, all male ("Manosa and 2DG **Male**"); 0522 also has animals with these numbers (of those looked up, 46–50, 55, 56 and 62 are female), so the number alone cannot decide |
| `BIOMAGUNE` (17) | 11: `ID15/16/20/21/25/26 H` / `0522 H&E` and `ID46/48/49/55/56 0522` / `lung heart` / H&E; 6: `202/203/204/207/208/209 II` / `HE` / `NMX` or `SuHx`, **no protocol** | the 11 exist in 0522 |
| `Histologia_ratones_viejos\HE`, `\Tricrómico` and their escaner copies | `IDn H+L` / H&E or Masson / `0424`; `ID16n II` / `P1019-3` / H&E or Masson / `04/23` | 0424's 1–4, 10, 12–14 and 1019's 160–162, 167–169 exist |
| `Histologia_ratones_viejos\SR` | `IDn H+L` / PR / `0424`; `ID167/168/169 II` / `1019-3` / `18mo`; `160/161/162 II` / PR, **no protocol** | as above |

**Every Confirmed claim that has a label agrees with it on protocol and animal (21 of 21), except the 5 `0522`
files, whose labels read `1422`.** Corroboration for `1422`: production's `AE-biomaGUNE-1422` microscopy already holds
slides of exactly animals 43–62 (182 files named `IDnnHL-1422_…`, the same `HL` heart-and-lung slides); M. Jesús filed
20 of these scans under `Manosa and 2DG Male_Proyecto 1422`; the `0522` claim is a folder name confirmed by dates
only. Irene's "`0522` is ours; `1422` unknown" answered the question's folder names; the slides name `1422`.

### 2.2 The readings (in `tools/configs/drives3x_2026-10/readings.csv`, status `proposed`)

- **L1 (`label`): a blank file (no claim or (C)) takes its label's protocol and animal.** Only where the label names
  both; a label without a protocol (9 planned files) is never used; a Confirmed claim is never touched.
- **L2 (`label-overrule`): the 25 `0522 Biodonostia` scans take `1422` and the label's animal**, replacing the folder's
  Confirmed `0522`. A reading has not overruled a Confirmed claim before (R5 filled (C) files): this is the reason it is
  separate from L1. Without it, 20 scans stay blank as conflicts and 5 go to `0522` against their own labels.

A reading changes nothing until its row says `accepted` (the R5 mechanism: `ingest_plan.apply_readings`, tested).
Its effect is recorded in each row's note: "Claim: CONFIRMED AE-biomaGUNE-0522, replaced by reading L2 (accepted …):
the slide label in the file reads 'ID43 HL / H&E / 1422'."

### 2.3 With L1 and L2 accepted (built and checked beside the plan, `D:\…\xmic\varL\`, never in the repo)

| Project | Files | GB | With a subject | Animals |
|---|---:|---:|---:|---:|
| `AE-biomaGUNE-0424` | 23 | 51.5 | 23 | 8 |
| `AE-biomaGUNE-1019` | 15 | 20.1 | 15 | 6 |
| `AE-biomaGUNE-1422` | 25 | 15.3 | 25 | 20 |
| `AE-biomaGUNE-0522` | 11 | 19.7 | 11 | 11 |
| blank (labels without a protocol: `BIOMAGUNE` 202–209 II, `SR` 160–162 II) | 9 | 7.3 | | |
| **all** | **83** | **114.0** | 74 | 45 |

Verdicts: Confirmed 21, READING-L1 28, READING-L2 25, no claim 9; conflicts 0; every planned row's project and subject
equal its label's (74) or its label names no protocol (9). `ingest_check` on the variant: **all 12 checks PASS**
(check 6 re-resolved every subject in the facility DB with fresh SELECTs); the real dry runs against `J:`: X01 7, X02 69,
X03 7 cases, 0 SKIP, 0 refused, 0 failed. `AE-biomaGUNE-1422` (PROJ-0013) is active. The non-raw copies follow their
parents: `0424` 9, `1019` 3 (instead of `0424` 8 and holding 4).

---

## 3. The invariants (the plan as committed)

`ingest_check.py --profile drive3x_2026-10` runs the engine's own dry-run resolution (`config.expand_batch`) on every
generated config against the live registry and compares every case with the plan, file by file
(`plan\check_report.json`, `plan\check_cases.csv`). **All PASS, 83 cases, 0 engine skips, 0 warnings, 0 extraction
failures.**

| # | Invariant | Result |
|---|---|---|
| 1 | the planned set = A1's serial-4661000340 contents (re-fingerprinted) minus production minus the listed exclusions; engine cases == plan rows | PASS: 83 = 83 (114.0 GB) |
| 2 | per file: instrument, project, researcher, operator, subject, data source, model, sample, link name, group, notes, date | PASS: 0 mismatches over 83 |
| 3 | no SHA-256 in production; the index newer than the registry | PASS: 0; index 17:13 today, registry last written 2026-10-07 18:21. Re-checked against the live index of 19:19 (§5.2): **0 of all 172 out-of-scope copies** (Axioscan, Leica, processed) are in `/raw/` |
| 3b / 3c | no re-save of a production acquisition, no two planned files the same acquisition, no production row at a planned file's instrument and second | PASS: 0 / 0 / 0 |
| 3d | every same-second group decided for exactly its membership | PASS: 32 groups |
| 3e | no planned file truncated; farm paths fit MAX_PATH | PASS: 83 directories read, deepest 142 |
| 4 | dates | PASS: 2024 42, 2025 41; none blank or today |
| 5 | projects | PASS: none created; `0424`, `0522`, `1019` exist and are active |
| 6 | subjects only where the claim settles them, each re-resolving in the DB to itself | PASS: 21 rows, 13 animals |
| 7 | XMIC: 83 rows, model `Axioscan 7`, source `collaborator:Biodonostia` | PASS |
| 8 | link names unique and free in each project's live `raw_linked\` | PASS: 26 planned, 0 taken |
| 9 | the local mirror is the drive's bytes | every file hashed as read from `J:` and kept only on a drive-manifest match: 116 of 116, 153.9 GB, 0 bad; **§6.1 re-hashes the 83 from disk before X01** |

**The real dry runs** (`ingest_raw.py --dry-run --nas-root J:\gjesus3-data`, read-only): X01 5 cases, X02 23, X03 55; 0
SKIP, 0 refused link names, `Failed: 0` (`plan\dryrun_Xnn.log`).

---

## 4. The rehearsal and its idempotent re-run

**Where:** a scratch NAS root on D: (`…\xmic\rehearsal_nas\`), made by `ingest_plan.py --profile drive3x_2026-10 scratch`:
production's registries copied read-only (35,613 rows), and for `0424`, `0522` and `1019` a `raw_linked\` with a
zero-byte stand-in for each of production's link names (1,521 / 4,152 / 2,325), so a collision would be real. **What:**
the real engine and the generated configs, exactly as production runs them, **all three batches in order**, then the
same commands again. Drivers: `…\xmic\scratch\rehearse.sh X01 X02`, then `rehearse_more.sh X03 -- X01 X02 X03`; logs in
`…\xmic\rehearsal_logs\`.

| Step | X01 (5 files) | X02 (23) | X03 (55) |
|---|---|---|---|
| pass 1 (`--refresh-index projects`) | exit 0, 68 s; `Success: 5`, `Failed: 0`; 0 SKIP | exit 0, 970 s; `Success: 23`, `Failed: 0`; 0 SKIP | exit 0, 1,510 s; `Success: 55`, `Failed: 0`; 0 SKIP |
| WARN lines | 4 = the two sidecar sentinels (`condition.is_control` null, `anatomy.region` empty) on each of the 2 rows with a subject | 38 = the same on its 19 | 0 (no subject) |
| `ingest_verify --profile drive3x_2026-10` (all three) | **83 planned, 83 registry rows from these configs; `rows`, `fields`, `checksum`, `sidecar`, `link`, `registry`: all PASS (0)** | | |
| `c_manifest_check --profile drive3x_2026-10` (from the drive manifest, without the plan) | **83 rows against the 621,969-row manifest; `rows`, `manifest`, `link`, `orphans` (3 month folders): all PASS (0)** | | |
| the validator | the same 35,613 `ERROR:` lines before X01 and after X03, line for line (each a production acquisition whose folder the scratch root does not have): **the 83 new rows add none** | | |
| pass 2 (the same commands) | `Total: 0`, 5 "already in registry" | `Total: 0`, 23 | `Total: 0`, 55 |

What an ingested row looks like (`ACQ-20250214-XMIC-001`, X01): `XMIC`, `Axioscan 7`, `collaborator:Biodonostia`,
`PROJ-0002`, subject `13-AE-biomaGUNE-0424`, `sample_type` `tissue`, researcher and operator blank, `original_name`
`drive3_MJesus-MFB/Microscopio/Histologia_ratones_viejos/HE/ID13_0424_H+L 1.czi`, `checksum_present` `Y`, the note of
§1.4 ending `Claim: CONFIRMED.`; its sidecar carries `user_supplied.data_source` `collaborator:Biodonostia` and the
facility-DB subject block (`Mus musculus`, F, born 2023-05-25). A conflict-blank row (`ACQ-20241025-XMIC-001`,
`0522 Biodonostia\2024_10_24__4469-1.czi`): no project or subject; its note ends `Claim: conflict (its pixel-identical
twins claim AE-biomaGUNE-0522 and AE-biomaGUNE-1422); left blank.`

**Not rehearsed:** the SMB side (the engine and runner are the ones drives 1+2 and stream C ran into `J:`); the L1/L2
variant's run (the same code paths and configs, other strings; §2.3 checked it through the engine's resolution and the
real dry runs). The scratch root (≈ 114 GB) can be deleted after the gate.

---

## 5. The placement batch (the fourth of stream P's tool)

### 5.1 What it places

| Part | Files | GB | Destination | Why |
|---|---:|---:|---|---|
| **A, now** | 26 Leica (`.lif` 17, `.lifext` 9) | 6.72 | `AE-biomaGUNE-1121\working\historical_drives\MJesus-MFB\Proyecto 1121 London\Experimentos\Histologia\…` | Irene (Q10): biomaGUNE's own former Leica TCS SP8, "the microscope that we used to use"; gjesus3 has no `.lif` reader or instrument code, so not registered. The claim `Proyecto 1121 London` (CL-2441, Confirmed); 1121 active since its 2026-10-06 reopen. The files land in batch 1's folders, beside the PNG exports made from them (`Project.lif - Series020.png` …) |
| **A, now** | 2 copies of `m204lung.czi` (the `czi-processed` file) | 0.00 | the holding folder, in the drive's structure | **Where it was:** nowhere. Stream C left it out of scope (no hardware or experiment block: not an acquisition record), A2 classed it raw and left it to A1, and no placement manifest (batch 1, M1 release, P2a/P2b, batch 3) has it. Its claim: none (`Machos vs Hembras\…`), so the holding folder with reason `no claim` (mappable in the 2b round); its sibling `m204lungPOL.czi` is `ACQ-20220711-CELL-007` (no project) |
| **B, after the XMIC ingest** | 12 pixel-identical copies under another name (§1.3) | 26.14 | as committed: `0424` 8, holding 4; with L1 + L2: `0424` 9, `1019` 3 | Ryan's rule (2026-10-01): a renamed re-save goes to the project folder; each is tied to its parent's new ACQ-ID, which exists only after the ingest |

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

### 5.2 Dedup and invariants (part A)

`x_placement.py lists` builds the hand-over list from stream C's out-of-scope list and A2's table (each row's bytes
equal both); `p_plan.py handover` checks every row against the drive manifest (the D: copy is byte-identical to the
staged one), refuses a path an earlier batch decided (every earlier manifest given), refuses bytes in `/raw/` (the live
index of today) and plans destinations with the shared rule against the live trees: **28 rows: `place` 26, `holding`
2; refused 0; destinations already present 0; longest UNC path 219** (budget 240; 13 files land in folders batch 1
shortened, e.g. `ki67 and som~8108`). Built twice: byte-identical
(`placement\batch4a\placement_manifest.csv`, SHA-256 `18e966cee9ea171b0449ca714a701e2c361cb51c181d396107f40de34cb75baf`;
the list `89e291e2…`). Against **live** `/raw/` (`p_verify.py raw-dedup`, 2026-10-08 19:06–19:19, every acquisition's
`checksums.json`: 35,613 acquisitions, 647,057 files, none hashed directly, none missing): `RAW-DEDUP PASS: 0 of the 28
rows copied now or held are in /raw/`.

### 5.3 Rehearsal (part A, D:, source the real staged copy on J:)

Rehearsal root: `p_verify.py snapshot` of the live `1121` tree and the holding folder (`…\xmic\placement\rehearsal\nas`);
each window snapshotted again as its before-state, then the §6.3 commands with `--nas` = the root; log
`placement\rehearsal_batch4a.log`.

| Window | Copied | `p_verify verify` (re-hash all) | Index before → after | Re-run |
|---|---:|---|---|---|
| W1 `AE-biomaGUNE-1121` | 26 · 6.72 GB | **VERIFY PASS**: walk 0 missing / 0 extra; `_PATHMAP` 372 kept; provenance 4,546 kept, 26 added; README = the current text (its diff to the live one is exactly the note) | 3,996 → 4,022 | `skipped-identical` 26, 0 documents written |
| W2 holding | 2 | **VERIFY PASS** | `manifest.csv` 59,483 → 59,485 | `skipped-identical` 2, 0 written |

**Part B** was rehearsed after the XMIC rehearsal (`placement\rehearse_batch4b.sh`, log `rehearsal_batch4b.log`), with
that rehearsal's ACQ-IDs as the parents, the hand-over planned against the LIVE trees (read-only), and the windows
copying into a fresh snapshot root (`placement\rehearsalB\nas`): `x_placement nonraw` 12 rows; `handover (X): 12 files
{'place': 8, 'holding': 4}; refused 0; destinations already present: 0`; W `0424` copied 8 (19.79 GB), **VERIFY PASS**
(`_INDEX` 1,941 → 1,949, provenance 3,474 kept + 8); W holding copied 4 (6.35 GB), **VERIFY PASS** (`manifest.csv`
59,483 → 59,487); both re-runs `skipped-identical`. In holding, their reason is the derivative's own (`R3 derivative of
<ACQ-ID>`), not the mappable `no claim`: when the parent later gets a project, moving them is a by-hand step (with L1
accepted none goes to holding).

---

## 6. Production: the exact commands

From the repo root (after the merge), Git Bash, `export PYTHONDONTWRITEBYTECODE=1`. **One registry writer at a time:**
not while the MRI archive ingest runs; evenings or weekends (operators ingest by day). Placement windows also append
to project provenance files: not during an ingest into the same projects.

### 6.0 Only if the coordinator accepts L1 and/or L2 (before anything else)

Edit `tools/configs/drives3x_2026-10/readings.csv`: `status` `accepted`, `decided` `<date> <who>` on the accepted rows. Then:

```bash
P="--profile drive3x_2026-10"
python tools/drive_staging/ingest_plan.py $P plan          # readings_applied {'L1': 40, 'L2': 25}; conflicts 0; verdicts
                                                           #   CONFIRMED 21, READING-L1 28, READING-L2 25, NO-CLAIM 9
python tools/drive_staging/ingest_plan.py $P configs       # 3 configs; batches X01 7 / 4.0, X02 69 / 103.3, X03 7 / 6.7 GB
python tools/drive_staging/ingest_plan.py $P farm --prune  # "prune: removed 49 farm links ..."; "farm: 49 linked,
                                                           #   34 already linked, 0 errors, 0 stray files" (49 change batch)
python tools/drive_staging/ingest_check.py $P              # every line PASS, 'skips': 0 (83 cases)
git add tools/configs/drives3x_2026-10/ && git commit      # the configs every registry row's ingest_config names
```

(Accepting only L1: 20 conflicts stay blank and 5 files go to `0522`, as committed; L2 alone fills only the 25.)

### 6.1 Once, before X01 (read-only)

```bash
python tools/drive_staging/ingest_plan.py --profile drive3x_2026-10 verify-local   # "83 files, 114.0 GB ... 83 match, 0 bad"
python tools/drive_staging/ingest_plan.py --profile drive3x_2026-10 farm           # "0 linked, 83 already linked, 0 errors, 0 stray files"
python tools/animal_db.py --check                                                  # OK
df -h /j                                                                           # stop below 1 TB free
```

### 6.2 Each XMIC batch: X01 (the pilot) alone first, then X02, then X03, each on Ryan's go

```bash
bash tools/drive_staging/run_drives_batch.sh drive3x_2026-10 X01
python tools/drive_staging/drive3/c_manifest_check.py --profile drive3x_2026-10 --nas-root "J:\gjesus3-data" --batch X01
```

The runner (stream C's, unchanged; the profile gives the config, the catalog folder and the provenance file
`tasks/drive3_foreign_raw_ingest_provenance.csv`) does, and stops at the first failure: **0** a fresh production index
and every §3 check on the batch (every line PASS, `'skips': 0`); **a** a dated off-NAS backup of the registries,
verified, and the validator; **b** every target project active; **c** the real dry run (`Batch: N cases`, 0 SKIP,
0 `Refusing`, `Failed: 0`); **d** the run (`Success: N`, `Failed: 0`); **e** `ingest_verify` (rows, fields, checksum,
sidecar, link, registry: PASS) and the validator's `ERROR:` lines unchanged; **f** the re-run `Total: 0`.

| Batch | Expected (as committed) | Time |
|---|---|---|
| X01 | `Batch: 5 cases`; `Success: 5`; 4 WARN lines (the two sentinels × 2 subject rows) | ≈ 2 min |
| X02 | 23 cases; `Success: 23`; 38 WARN | ≈ 20 min |
| X03 | 55 cases; `Success: 55`; 0 WARN | ≈ 35 min |

`c_manifest_check`: `rows`, `manifest`, `link`, `orphans` all PASS. **Stop and report** on any failure; on an ACQ-ID
dated today; on a project created or changed (`registry_projects.csv` byte-identical to the backup); on
`pending_subject_metadata.csv` growing (the DB went away; `tools/recover_subject_metadata.py`); below 1 TB free.

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
# 0. the manifest is still the gated one (read-only)
python $PV raw-dedup --manifest "$M" --nas "$NAS" --write-index "$B\live_raw_index_$D.csv"
#   RAW-DEDUP PASS: 0 of the 28 rows copied now or held are in /raw/ (all 28 manifest rows checked)   (≈ 14 min)
python tools/drive_staging/drive3/x_placement.py lists --out "$B\lists_check_$D"
python $PP --nas "$NAS" handover \
    --manifest "$S\placement\manifest_check2_20261006\placement_manifest.csv" \
    --manifest "$S\placement\release_M1_20261006\placement_manifest.csv" \
    --manifest "$S\mri\out\p2\P2a_20261007_1053\placement_manifest.csv" \
    --manifest "$S\mri\out\p2\P2b_20261007_1053\placement_manifest.csv" \
    --manifest "$S\mri\out\p2\P2b_masks_20261007_1053\placement_manifest.csv" \
    --manifest "$S\bmj\batch3_v2\placement_manifest.csv" \
    --csv "$B\lists_check_$D\foreign_handover.csv" --stream X --raw-index "$B\live_raw_index_$D.csv" --out "$B\batch4a_check_$D"
#   handover (X): 28 files {'holding': 2, 'place': 26}; refused 0; destinations already present: 0
sha256sum "$B\batch4a_check_$D\placement_manifest.csv"   # 18e966ce…75baf (= the gated one), or stop and re-gate
# W1: the 1121 tree
python $PV snapshot --manifest "$M" --nas "$NAS" --project AE-biomaGUNE-1121 --to "C:\Users\rtasseff\temp\gjesus3_placement_backup_${D}_drive3_B4W1"
python $NP --out "$B\runs\W1" --nas "$NAS" copy --manifest "$M" --scratch "$B\scratch" --project AE-biomaGUNE-1121
#   DRY RUN: 26 files, 6.72 GB, 1 projects (+ 4 index documents); destinations already present: 0; longest 219
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
#   VERIFY PASS (manifest.csv 59,483 -> 59,485)
```

**If something goes wrong:** batch 3's §9.3 applies unchanged: re-run the copy (in-place files are re-hashed and
skipped); a `COLLISION` is a stop (nothing is overwritten); to abandon a window remove only its `copied` files and
restore the four documents per tree from the step's snapshot; never remove a `MJesus-MFB\` folder.

### 6.4 The placement, part B (after X01–X03 are in and verified)

```bash
python tools/drive_staging/drive3/x_placement.py nonraw --out "$B\listsB_$D"          # 12 rows, each with its parent's ACQ-ID
python $PP --nas "$NAS" handover <the six --manifest lines above> --manifest "$M" \
    --csv "$B\listsB_$D\xmic_nonraw_handover.csv" --stream X --raw-index "$B\live_raw_index_$D.csv" --out "$B\batch4b_$D"
#   as committed: handover (X): 12 files {'place': 8, 'holding': 4}; with L1+L2: {'place': 12}; refused 0; present 0
```

Then the window procedure of 6.3 with `M="$B\batch4b_$D\placement_manifest.csv"`: W1 `AE-biomaGUNE-0424` (as committed
8 files, 19.79 GB; with L1 also `AE-biomaGUNE-1019`), W2 holding (as committed 4 files, 6.35 GB). `nonraw` refuses to
run before every parent is registered.

---

## 7. For the coordinator: rulings, and what is not settled

| # | What | Recommendation |
|---|---|---|
| G1 | **Ryan's go per XMIC batch**, X01 alone first | — |
| G2 | **L1 and L2** (§2): the files' own labels for 62 of the 83 projects | **Accept both.** L2 is the first reading to overrule a Confirmed claim; the claim is a folder name confirmed by dates only, and the labels, the 1422 folder and production's own 1422 slides all say `1422`. Then §6.0 |
| G3 | **`data_source` `collaborator:Biodonostia`** for an informal arrangement | Keep: the field names the acquisition's origin; the note says "no formal collaboration" |
| G4 | **People:** `operator` blank (Elena in the note), `researcher` blank | Keep blank, unless the coordinator prefers `researcher` = `MJ` on all 83 (Irene: "M. Jesús's samples"; stream C's token for her), a one-line profile change and re-generation. A surname for Elena, if it arrives, is a by-hand change later (Ryan's 2026-10-08 call) |
| G5 | **The 12 pixel-identical copies under another name** (26.1 GB, the `escaner` folder's re-saves of 2025-02-19) | Follow Ryan's 2026-10-01 rule (project folder, part B). They hold nothing the registered file lacks; if 26 GB of duplicates is unwanted, drop them as R2 drops same-name re-saves (one rule change in `same_acquisition_actions`, not built) |
| G6 | **The 9 files whose label names no protocol**: `BIOMAGUNE` `202/203/204/207/208/209 II` (production names these animals `ID202II_0619` …, in `0619`) and `SR` `160/161/162 II` (the same animals' H&E and Masson slides read `P1019-3`) | Blank, listed in [`drive3_xmic_plan.csv`](drive3_xmic_plan.csv) for the assign workbook; a third reading could take them, not proposed |
| G7 | Irene offered to say which `0522` images are worth keeping ("some were also imaged by Marta at biomaGUNE") | Everything raw is registered regardless; her review can mark duplicates later |

**Not settled here:**
- **The label readings are a person's reading of handwriting.** Each is on a contact sheet (`D:\…\xmic\labels\`);
  a spot check of a few by the coordinator before accepting L1/L2 is cheap (sheets 1–4 hold the 45 `1422` labels).
- **Some slides were scanned twice:** `ID43` twice on 2024-10-24 (`4445`, `4465`), and 46, 47, 49 and 57 again the next
  morning (the `-1` scans). Each scan is its own acquisition (another second, other pixels), so each is registered.
- **Who made the scans' Biodonostia-side metadata** (`UserName` `zeiss`): the scanner's account, not a person.

---

## 8. What changed in the code

| File | Change | Why |
|---|---|---|
| `tools/reference/microscopy_instruments.yaml` | entry `EXTERNAL:Axioscan7-Biodonostia`, serial `4661000340` | the instrument, by its serial (§1.1) |
| `tools/drive_staging/ingest_plan.py` | profile **`drive3x_2026-10`**; `XMIC_MODEL` / `XMIC_SOURCE` and the pilot's size per profile (drives 1+2 keep theirs); `a1_instrument` (re-fingerprint, `refingerprint`); bucket names from the instrument (stream C's stay `CELL-…`); YAML header per profile and an `XMIC` paragraph; label readings (`label`, `label-overrule`, `label_readings.csv`) beside the folder kinds; `label_check.csv`; rule 1b's extension (§1.3); `plan --config-dir`, `--farm` (the variant) | §1–§2 |
| `tools/drive_staging/ingest_check.py` | check 1 re-derives with `a1_instrument`; check 7 text | |
| `tools/drive_staging/drive3/x_groups.py` (new) | the same-acquisition facts for compressed `.czi`: stored payloads, translation, the interrupted-copy walk | §1.3 |
| `tools/drive_staging/drive3/c_manifest_check.py` | `--profile` (default stream C's) | the independent check for the XMIC batches |
| `tools/drive_staging/drive3/x_placement.py` (new) | the hand-over lists of the fourth placement batch (part A; part B from the registry) | §5 |
| `tools/drive_staging/historical_paths.py` | the `AE-biomaGUNE-1121` README note | §5.1 |
| `tools/configs/drives3x_2026-10/` (new) | `drives3x_Xnn.yaml`, `cases_Xnn.csv`, `batches.csv` (generated); `readings.csv` (L1, L2 proposed), `label_readings.csv` (the labels as read) | |
| `tools/test_drive3_foreign_raw.py` (new); `tools/test_drive_catalog.py` | the profile, re-fingerprint, `x_groups` classification (incl. the measured triple), rule 1b, label readings, the placement lists, the README note; the fingerprint of the new serial | |
| `tasks/drive3_xmic_plan.csv`, `tasks/drive3_xmic_nonraw_for_placement.csv` (new) | the 83 planned rows (with labels and the L1/L2 outcome) and the 12 non-raw copies | the record; the blank rows feed the assign workbook |
| `mfb-rdm-docs/09_MODALITIES.md` §1.6; `tools/INDEX.md` | `XMIC`'s second instance (🔶, gated, not ingested) and how it is recognised; the tools rows | the spec names the reference entries the ingest relies on |

Stream C's frozen profile is untouched in behaviour (`refingerprint` off; its suite passes unchanged).

## 9. Reproducing it

From the worktree root, `PYTHONDONTWRITEBYTECODE=1`; read-only on `J:`; writes under `D:\…\xmic\` and, for the configs
and lists, the repo.

```bash
P="--profile drive3x_2026-10"
python tools/drive_staging/catalog.py production --out "D:\projects\gjesus3\drive3_streams\xmic\catalog"
python tools/drive_staging/ingest_plan.py $P plan                  # pass 1: 116 candidates, 32 groups to check
python tools/drive_staging/ingest_plan.py $P localize              # 116 files, 153.9 GB, J: -> D:, hashed (≈ 28 min)
python tools/drive_staging/drive3/x_groups.py all                  # facts (≈ 18 min), the interrupted-copy walk, classify
python tools/drive_staging/ingest_plan.py $P plan                  # pass 2: 83 planned
python tools/drive_staging/ingest_plan.py $P configs
python tools/drive_staging/ingest_plan.py $P farm
python tools/drive_staging/ingest_check.py $P
bash D:/projects/gjesus3/drive3_streams/xmic/scratch/rehearse.sh X01 X02        # §4
bash D:/projects/gjesus3/drive3_streams/xmic/scratch/rehearse_more.sh X03 -- X01 X02 X03
bash D:/projects/gjesus3/drive3_streams/xmic/varL/run_variant.sh               # §2.3
bash D:/projects/gjesus3/drive3_streams/xmic/placement/build_batch4a.sh        # §5.2 (and with a suffix: the determinism check)
bash D:/projects/gjesus3/drive3_streams/xmic/placement/rehearse_batch4a.sh     # §5.3
```

The labels: `scratchpad` scripts extracted each content's `Label` attachment from the staged copy and tiled the contact
sheets into `D:\…\xmic\labels\`; `label_readings.csv` holds what was read from them.
