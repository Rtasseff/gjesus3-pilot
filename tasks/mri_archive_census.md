# The MRI platform's archive: a census against production (READ-ONLY), and a pull proposal

**Status:** 🔶 DRAFT for the coordinator, 2026-10-07. **Read-only throughout.** The archive was **listed only**:
7 remote calls, 2.2 s, Wednesday 14:51, one connection, no file contents read. Production (`J:\`) was read
only. Nothing has been downloaded or decided. Branch `feat/mri-archive-census`.
**The archive:** `mriuser@10.10.3.175`, `/share/homes/mriuser/backup_7T_olddata_260824`, host key ssh-ed25519
`SHA256:O4IOYEcsJPHeYnTIrBWqlDT5a9vvRvnRJftbeHk9hmI`. Rules and layout:
[`equipment/historical_data_archives.md`](../equipment/historical_data_archives.md).
**Evidence (regenerable, not backed up):** `D:\projects\gjesus3\mri_archive\census\`, listed in §7.
**Units:** GB = 10⁹ bytes, compressed (tarball) size unless marked "extracted". A **study** is one ParaVision study
folder, which is one archive. Studies held in more than one year folder are counted once.

## Summary (numbers first)

1. **The archive holds 2,555 distinct studies from 2019–2022** in 3,048 archives (617.7 GB; 485 studies are stored
   two or three times). By class:

   | Class | Studies | GB |
   |---|---:|---:|
   | **MFB** (`jrc`, plus 2 typed `jrcc`) | **1,263** | 347.5 |
   | MFB-linked, other initials (protocol `1116`, a shared platform protocol) | 9 | 4.1 |
   | Other groups (`pr` 715, `abh` 152, `sp` 142, `jl` 107, `dan` 85, 12 others) | 1,276 | 150.4 |
   | No initials or platform QC (`test`, `qa`, `0820` without initials) | 7 | 0.1 |

2. **MFB against production: 599 are in production, and 650 are new with data (162.8 GB).**

   | MFB studies (1,263) | Studies | GB |
   |---|---:|---:|
   | In production (by `original_name`'s study part) | 599 | 184.7 |
   | Aborted starts: production holds the same session (same `session_id` and day) under the next folder | 6 | 0.0 |
   | Empty archives (< 1 KB, no image data) not in production | 8 | 0.0 |
   | **New: animal sessions** | **561** | **158.9** |
   | **New: a second session of an animal production holds that day** (`_post`, `postadm`) | **12** | **1.3** |
   | **New: phantoms / QC / unclear** | **77** | **2.6** |

   The 650 new studies are 2019: 103, 2020: 222, 2021: 276 and 2022: 49 (§2).

3. **Stream M's 189 studies (3,309 exams): 130 are in the archive (2,346 exams, 56.0 GB), and 59 are not.**
   Of those 59, 18 are 11.7 T studies (the archive is the 7 T's). The other 41 are 7 T studies (696 exams) on days
   that the archive lacks entirely: 2020-06-15/16/18/19, 2020-08-03/04/05, 2022-01-25, plus one 2024 study (§3).
4. **D3's open items.** **N6:** 49 of the 57 studies are in the archive. Production already holds 6 (stream M, M04)
   and 2 are found nowhere. **N7:** all 8 of Ermal's `0118` sessions are in the archive; 2 are in production, so 6
   are new. N1, N2 and N4 are studies from 2024–2026, outside the archive's years (§4).
5. **Proposed pull: 780 archives, 218.8 GB** (about 446 GB extracted). That is the 650 new MFB studies (162.8 GB)
   plus stream M's 130 for the originals check (56.0 GB). **Not in the pull until ruled:** the 9 MFB-linked studies
   (4.1 GB). **Schedule:** after hours only, one connection. Night 1: the checksum files, a 2-archive layout probe
   and the 130 check studies. Night 2, or one weekend: the 650. At 20 MB/s the 650 take about 2.3 h; the first
   night measures the real rate. **Production growth after ingest:** about 13 GB, because production keeps
   only the DICOM, about 8 % of the compressed size (measured on 595 MFB studies held in both) (§5).
6. **Found on the way:**
   - **The archive is not complete.** July and August 2020 are missing entirely, and so are several other days.
     There is no 2023 folder, and the 11.7 T is not there.
   - Stored copies differ: 101 studies have two copies with the same compression but different sizes.
   - 646 archives have no `.sha1` or `.sha256` beside them: 502 of them are `2022_pv6`'s `.tar.gz` of 2026-08.
   - 32 archives are under 1 KB, five of them 0 bytes.
   - One interrupted upload (`.filepart`) sits beside its complete twin.
   - **292 other groups' studies match a production regex**, so the pull must go by explicit list, never by regex (§6).

---

## 1. The census (every archive, classified)

**How.** `python tools\mri_archive.py list` listed the root and the six year folders. That is 7 calls, 5,632 entries,
and one sub-folder (`2021_pv6/configurations`) that was left unlisted. Every `<study>.tar.gz` / `.tar.xz` / `.zip` is
one study archive. Each study name was then parsed:
- **the production rules**: the two regexes read from `tools/configs/mri_jrc_animalfirst.yaml` and
  `mri_jrc_projfirst.yaml`, applied with the ingest's own `filename_parser.parse_regex`, exactly as D3 did;
- **the console initials**: the first letters after `YYYYMMDD_HHMMSS_`;
- **the protocol code**: a 4-digit token that is a gjesus3 `AE-biomaGUNE-NNNN` project. A token after a letter
  (`m1024`) is an animal number, not a code;
- **the animal**: `m<n>` or `r<n>`.

Then the classes:
- **MFB**: initials `jrc`, and the typo `jrcc` (2 studies, `0320`, 2020-11-11).
- **MFB-linked**: other initials with a gjesus3 protocol code or LP-IONP in the name (D3's N2 rule).
- **Other group**: everything else with initials.
- **Phantom / QC**: keyword based (phantom, fantom, test, prueba, coil, array, Palmira, pv-tests, Manon, MOLLI…).
- **Empty**: every copy under 1 KB.

| Year folder | Archives | GB | Compression | `.sha1` beside | Archive dates |
|---|---:|---:|---|---:|---|
| `2019_pv6` | 423 | 79.7 | tar.gz | 423 | 2019-02 → 2019-12 |
| `2020_pv6` | 540 | 131.1 | 516 tar.gz + 24 zip (duplicates of tar.gz) | 516 | 2020-02 → 2021-02 |
| `2021_pv6` | 815 | 150.7 | tar.gz | 814 | 2021-02 → 2026-08 |
| `2022_PV6_PV7` | 486 | 97.6 | 366 tar.xz + 120 tar.gz | 366 | 2022-03 → 2023-01 |
| `2022_pv6` | 585 | 115.0 | 502 tar.gz + 83 tar.xz | 83 | 2022-07 → **2026-08 (502)** |
| `2022_pv7` | 199 | 43.6 | 175 tar.xz + 24 tar.gz | 175 (+24 `.sha256`) | 2022-07 → 2026-08 |
| **Total** | **3,048** | **617.7** | | **2,377** (+25 `.sha256`) | |

**Studies by year and class:**

| Year | MFB | MFB-linked | Other groups | No initials / QC |
|---|---:|---:|---:|---:|
| 2019 | 111 | 0 | 310 | 2 |
| 2020 | 318 | 0 | 196 | 2 |
| 2021 | 407 | 9 | 398 | 0 |
| 2022 | 427 | 0 | 372 | 3 |
| **Total** | **1,263** | **9** | **1,276** | **7** |

- **MFB by production regex:** 782 animal-first, 33 project-first, **448 neither**. The 2019 names never carry a
  code, and many 2020 ones do not either.
- **MFB by kind:** 1,170 animal, 75 phantom/QC (with 1 "phantom, mouse?"), 2 unclear, 16 empty.
- **MFB-linked, 9 (all 2021, protocol `1116`):**
  - `sp210211_ABH_m220…m222_1116` (3);
  - `AR2104xx_R228…R233biodistr_1116` (6).

  The facility DB names **Pedro Ramos Cabrer** as the holder of `1116`. It is a shared platform protocol, as `0721`
  is (D3 N2). MFB's own `jrc…_1116` studies are counted under MFB.
- **No initials / QC, 7:**
  - `test03` and `test190226` (2019);
  - `qa201223_82volcoil` ×2 (2020);
  - `220531_0820_m185/m186/m190` (2022). Protocol `0820` belongs to Jordi Llop (facility DB) and is not a gjesus3
    project.

## 2. Against production (live `registry_raw.csv`, 33,243 rows; MRI 16,137 in 1,299 study folders)

**Keys, in order:**
1. the study part of `original_name` (`<study>/<exam>`, or X1's `<study>__<exam>`);
2. the same session start (`YYYYMMDD_HHMMSS`) under another folder name;
3. the same `session_id` on the same day (the regex's `jrc_id`, or stream M's "name without date and `_1_1`", or the
   first half of a PV 7 doubled name);
4. the same animal, day and protocol code (from `sample_id` and the project).

Retired tombstones were checked too (none is MRI).

- **599 MFB studies are in production by name.** The ingests that put them there: the June bulk load (342), stream M
  (130), stream B (71, `dicom_B0*`) and the 2021 `1019` recovery (56). Note that 4 of the 599 are the **0-byte**
  archives of `jrc220303_m66/m67/m78/m79_0320`, which production loaded from the scanner in June.
- **6 are aborted starts.** The same `session_id` and day are in production under the next folder, minutes later:
  - `jrc211118_m22_0420` ×2: 13 KB and 125 KB;
  - `jrc220622_m1_1321` ×2: under 1 KB;
  - `jrc221003_0721_m45`: under 1 KB;
  - `jrc221114_m1_0522`: under 1 KB.

  Not pulled.
- **12 are second sessions of an animal production holds that day:**
  - `0618` `m153…m162_post` (2022-01/02);
  - `0721` `m13…m18postadm` (2022-04) and `m27post` (2022-07).

  They are later sessions (post-administration), so they are distinct data, not duplicates. The MRI link name
  carries the study start time (`HHMM`, since 2026-10-05), so their links do not collide with the earlier session.
- **Other groups:** 1 is in production, `prc221214_LFM_phantom_Cells`, through stream B's B07 (Ryan's Q3 ruling).

**The 650 new MFB studies, per protocol and year (studies / GB; the last column counts animals):**

| Protocol (gjesus3 project) | 2019 | 2020 | 2021 | 2022 | **Total** | Animals |
|---|---|---|---|---|---|---:|
| `0118` | 5 / 6.5 | | | | **5 / 6.5** | 5 |
| `0219` | | | 36 / 15.0 | | **36 / 15.0** | 17 |
| `0220` ⚠️ closed project | | | | 3 / 0.1 | **3 / 0.1** | 3 |
| `0320` | | 14 / 4.1 | 8 / 4.1 | | **22 / 8.2** | 21 |
| `0618` | 1 / 0.2 | 14 / 3.1 | 51 / 11.6 | 6 / 0.7 | **72 / 15.6** | 70 |
| `0619` | | 8 / 2.6 | 2 / 0.1 | | **10 / 2.7** | 10 |
| `0721` | | | 2 / 0.2 | 8 / 0.8 | **10 / 1.0** | 8 |
| `1019` | | 9 / 2.4 | 113 / 24.1 | | **122 / 26.5** | 46 |
| `1116` | 1 / 0.0 | | 28 / 6.7 | | **29 / 6.7** | 19 |
| `1319` | | 7 / 0.2 | | | **7 / 0.2** | 7 |
| `1519` | | 89 / 35.7 | | | **89 / 35.7** | 25 |
| **No code in the name** (incl. Ermal's 6 `…_ermal`) | 80 / 25.8 | 58 / 8.8 | 23 / 6.4 | 1 / 0.3 | **162 / 41.4** | 109 |
| Code that is no gjesus3 project: `0917` (Vanessa Gómez, PET lung ventilation), `0116`, `1316` (not in the facility DB) | 4 / 0.3 | 2 / 0.1 | | | **6 / 0.4** | 6 |
| Phantom / QC / unclear | 12 / 0.8 | 21 / 0.5 | 13 / 0.5 | 31 / 0.7 | **77 / 2.6** | — |
| **Total** | **103 / 33.8** | **222 / 57.5** | **276 / 68.8** | **49 / 2.6** | **650 / 162.8** | |

Per-animal lists: `mfb_new_by_year_protocol_20261007.csv`. Per study: `pull_plan_20261007.csv`.

## 3. Stream M's originals check (BACKLOG "after the platform-archive MRI ingest")

| Stream M batch | In the archive (studies) | Not in it | Why not |
|---|---:|---:|---|
| M01 `0118` | 23 | 4 | 7 T: 2020-06-19 (`r163…r167_2DG`), a day the archive lacks |
| M02 `0619` 2020 | 25 | 0 | |
| M03 `0619` 2021 | 49 | 10 | 11.7 T |
| M04 `0619` 2022-01-25 | 0 | 6 | 7 T: the archive has other studies of that day, but not these 6 (they are also N6) |
| M05 `1019` 2020 | 31 | 30 | 7 T: 2020-06-15/16/18 and 2020-08-03/04/05 (the archive has no 2020-07 or 2020-08 at all) |
| M06 `0320` 2022-03 | 0 | 7 | 11.7 T |
| M07 | 0 | 2 | `JRC191107_1116_m179_flow` (11.7 T); `jrc240702_m93_0522` (2024) |
| M08, M09 | 1, 1 | 0 | |
| **Total** | **130 (2,346 exams, 56.0 GB, all `.sha1`)** | **59 (963 exams)** | 18 on the 11.7 T, 41 on the 7 T |

Of the 130, 120 studies have scanner DICOM only, 8 were converted by Dicomifier, and 2 are mixed.

**The planned comparison (needs the archives, so it runs after hours; not run):**
1. Extract each of the 130 locally and recompute each exam's **DICOM-set digest by `mri_11_archive_check.py`'s
   exact rule**: SHA-256 over the sorted `recon<idx>_frame<NN>.dcm <sha256>` lines from `pdata/<idx>/dicom/MRIm<NN>.dcm`.
2. **Equal** → `bytes equal`. **Not equal** → compare the pixel data and geometry per instance (pydicom; the A1 §2.2
   re-export case) → `pixels equal (re-export)`, or `different` (stop and look).
3. **Dicomifier exams** (the 8 studies, plus the converted exams of the 2 mixed ones): compare the ParaVision
   sources (`2dseq`, `visu_pars`, `reco`, `method`, `acqp`) by SHA-256 with stream M's staged copy. The staged
   copy is still at `D:\projects\gjesus3\drive3_streams\mri\stage\`, with hashes in `out\stage_result.csv`.
   Equal → `source equal`.
4. Write the result per exam into a copy of `drive3_mri_for_archive_check.csv` (its `archive_result` column). The 59
   absent studies get `not in the archive (11.7 T)` or `not in the archive (7 T gap)`. The coordinator records it.
5. The same 130 archives also give **the dedup proof for the archive ingest**: staged as `<study>\<exam>` and dated by
   `VisuCreationDate`, a dry run against production must skip all 2,346 exams as already registered (stream M gate §2.3).

## 4. D3's open items (STATUS §0.4)

| Item | What the archive answers |
|---|---|
| **N6**, the 57 June-skipped studies of 2022 | **49 are in the archive.** Of those: the 12 second sessions (§2); 5 animal sessions (`0220` `m165`, `m171`; `0721_74`, `0721_75`; `m6_132`); 31 phantoms and coil tests (with `fluor_supcuad` and `19F_FDG_mouse_array`); 1 empty (`Palmira_BRK_array`, 500 B). **6 are in production** (`0619` animals 191–200 of 2022-01-25, from the drive through stream M's M04; they are not in the archive). **2 are found nowhere:** `jrc221014_PALM_brukerarray` (2022-10-14) and `jrc230620_Phantom_Claudia_3K` (2023: the archive has no 2023). |
| **N7**, Ermal's 8 `0118` sessions of 2021 | **All 8 are in the archive.** `m175` and `m178` are in production (stream M, from the `K:` copy). `m176`, `m177` and `m179`–`m182` are new (in §2's "no code" row; stream M put their siblings in `AE-biomaGUNE-0118` after a facility-DB check). |
| N1, N2, N4 (2024–2026, on the scanner) | Outside the archive's years. Still on `kenia` as of D3. |
| N3, N5 | Not archive questions. |
| D3 §5, "nothing that leaves the scanner is lost" | **Only partly true for this folder.** There is no 2023 folder, although 2023 left `kenia` between June and October 2026. July–August 2020 and several other days are missing. The 11.7 T is not here. Production holds the 2023 MFB studies that the June load ingested (1,494 MRI rows dated 2023). The open part is the June skip list's 2023 studies and the gaps. **Question for the platform manager** (§6, Q7). |

## 5. The pull plan (proposed; nothing decided)

**What** (`pull_plan_20261007.csv`, one row per study; the copy is chosen in this order: one with data, then one
with a `.sha1`, then a `.sha256`, then tar over zip):

| Tier | Studies | GB | Checksum beside | Note |
|---|---:|---:|---|---|
| A. MFB animal sessions, new | 561 | 158.9 | `.sha1` 561 | |
| A2. MFB second sessions (`_post`, `postadm`) | 12 | 1.3 | `.sha1` 5, none 7 | 2 have a differing duplicate |
| B. MFB phantoms / QC / unclear | 77 | 2.6 | `.sha1` 57, `.sha256` 2, none 18 | 6 have a differing duplicate; **needs a ruling (Q2)** |
| C. Stream M originals check (no ingest) | 130 | 56.0 | `.sha1` 130 | |
| **Proposed pull (A + A2 + B + C)** | **780** | **218.8** (≈ 446 extracted) | | 758 tar.gz, 22 tar.xz; the largest 1.6 GB; median 218 MB |
| *Not pulled:* E. MFB-linked `1116` | 9 | 4.1 | `.sha1` 9 | **needs a ruling (Q3)** |
| *Not pulled:* D. aborted starts; X. empty archives | 2; 16 | 0.0 | | |

**The extracted size is estimated, not measured.** The 194 drive studies that are also in the archive give
extracted / compressed = 2.04 (median; quartiles 1.88–2.07). `D:` has 5.7 TB free.

**Prerequisites:**
- Ryan's go (and the platform manager's agreement, as N6 frames it).
- A **`fetch` step added to `tools/mri_archive.py`** on a branch, with tests. It streams one archive through the
  wrapper's `open("rb")` to a **local** `D:\projects\gjesus3\mri_archive\tarballs\<year folder>\<file>.part`, computes
  SHA-1 in the same pass, checks it against the `.sha1` (or the `.sha256`), and renames the file locally.
  - It is resumable: verified files are skipped.
  - It is sequential on one connection.
  - On weekdays it starts no new file after 07:30 and aborts a running one at 07:55 (removing the local `.part`). The
    module already refuses `open` from 08:00.
  - Speed: paramiko reads one 32 KB block per round trip unless the file is prefetched. A read-only `prefetch()` on
    the wrapper's file (pipelined reads on the one connection, at night only) is the likely speed-up. Decide when
    building it.

**Schedule (after hours only; one connection; no parallel reads):**

| Window | What | Size |
|---|---|---|
| Night 1 (a weekday, 18:00 → 07:30) | Read the 4 `00_LOGFILE_sha1.txt` and the 780 chosen archives' `.sha1` / `.sha256` (under 1 MB). Download 2 small archives and list them (`tar -t`) to settle the layout (is the top folder the study name, and are the paths relative?). Measure the rate. Then tier C. | 56.0 GB |
| Night 2, or one weekend (Fri 18:00 → Mon 07:30) | Tiers A, A2, B, oldest first | 162.8 GB |
| Any time (local) | Integrity: SHA-1 where given; for the 25 without a checksum, the compression CRC (`gzip -t` / `xz -t`) plus the `tar` listing; where two copies differ, download both and keep the one with the complete exam set. Extract to `D:\projects\gjesus3\mri_archive\extracted\<study>\<exam>\` with Python `tarfile` `filter="data"` (no absolute paths, no `..`, no links out). | ≈ 446 GB |

At 20 MB/s the whole 218.8 GB takes about 3 h; at 10 MB/s about 6 h. One weekday night covers either part, and
a weekend covers both.

**How the ingest would then run** (stream M's pattern; a gate document per batch, rehearsed, then Ryan's go):
1. **Scoped configs with case tables, never the shared regexes.** 448 MFB names match neither regex, and 292
   other-group names do match one. Each batch is one year × protocol (e.g. `1519` 2020: 89; `1019` 2020–21: 122;
   `0618`: 72; `0219`: 36; `1116`: 29; `0320`: 22). Values come from `cases_*.csv` (`on_missing: error`).
2. **Naming and dating as stream M:** staged flat `<batch>\<study>\<exam>`, so `original_name = <study>/<exam>`;
   `acquisition_datetime` from `VisuCreationDate`. A dry run against production must list exactly the case tables,
   and the dedup proof of §3 step 5 must hold first.
3. **DICOM first:** the scanner's DICOM where present (95 % in stream M). Otherwise Dicomifier converts before
   ingest (the convert-first rule). Spectroscopy and exams without a reconstruction are not registered: they are
   kept as other data (the 2026-10-04 line).
4. **Fields:**
   - `operator = pending-claim`, with the sessions appended to `_MRI sessions - who ran them.xlsx` (`tools/claim_workbooks.py`; Ryan's Hold rule, STATUS §0.5);
   - `researcher` blank;
   - subject ids from the facility DB (`<n>-AE-biomaGUNE-<alias>`);
   - notes name the archive path and its SHA-1.
5. **Projects:**
   - the code's gjesus3 project where the name carries one;
   - **the 162 without a code:** a facility-DB lookup (animal × MRI date), as A1 and stream M did. If unresolved,
     no project (a check confirms a claim and never invents one);
   - **`0220` is closed** (3 studies): the reopen route (`tools/reopen_project.py`), case by case;
   - `0917` / `0116` / `1316` (Q4).
6. Rehearse into a `D:` NAS root, run the independent verifier, then write to production with backups, one
   registry writer at a time (stream M gate §7).
7. **Afterwards:** re-run A3's segmentation trace (BACKLOG). Today its 2019–2021 cohorts trace at 0–7 % because
   their MRI is missing.

## 6. Needs Ryan (named, not decided)

| # | Question | Why it matters |
|---|---|---|
| Q1 | **Go for the pull** (780 archives, 218.8 GB, after hours), and does the platform manager need to agree first? | Nothing moves without it |
| Q2 | **Tier B, 77 MFB phantoms / QC** (2.6 GB): ingest them, as the July `1125` phantoms and B07 were, or leave them in the archive? | 31 of them are N6 |
| Q3 | **Tier E, 9 studies on the shared `1116` protocol** with other initials (`sp…ABH` 3, `AR…biodistr` 6; 2021): in or out? (The same question as N2 for `0721`) | Holder: Pedro Ramos Cabrer |
| Q4 | **MFB studies whose code is no gjesus3 project:** `0917` ×4 (2019; Vanessa Gómez's protocol), `0116` ×1, `1316` ×1 (neither is in the facility DB): a new project, or none? | 6 studies |
| Q5 | **Reopen `AE-biomaGUNE-0220`** for its 3 studies of 2022 (`m165`, `m171`, `m173`)? | The project is closed |
| Q6 | **The 25 pulled archives without a checksum** (`2022_pv6`, `2022_PV6_PV7`): accept the compression CRC plus the tar listing as their integrity check? | No `.sha1` exists for them |
| Q7 | **Ask the platform manager:** where are July–August 2020, the missing June 2020 days, 2022-01-25, the 2023 studies (no folder here) and the 11.7 T's older studies? Is there a deep-storage copy we may read? | 41 of stream M's 7 T studies (696 exams) have no archive copy here. The drive copy may be the only one we know of |

## 7. Evidence and reproduction

All read-only. Run from `D:\projects\gjesus3\mri_archive\census\`. Listing during working hours is allowed but
must be gentle. Nothing reads file contents.

```
python "<worktree>\tools\mri_archive.py" list --out archive_listing_20261007.csv --max-depth 2   # 7 calls, ~2 s
python census_analyze.py > census_run.log      # registry + D3 + A1 + stream M's list; seconds
```

| File | What it is |
|---|---|
| `archive_listing_20261007.csv` | Every entry under the archive root (path, kind, size, mtime, mode), to depth 2 |
| `archive_files_20261007.csv` | One row per study archive: folder, compression, size, mtime, `.sha1` / `.sha256` beside it |
| `archive_studies_20261007.csv` | One row per distinct study: class, kind, regex class, `jrc_id`, protocol, animal, copies (and whether they differ), the chosen copy, production status and the matching production study, stream M, N6, the `K:` list, the June manifest |
| `mfb_new_by_year_protocol_20261007.csv` | §2's table, with the animal lists |
| `drive3_vs_archive_20261007.csv` | §3, per stream M study |
| `d3_items_vs_archive_20261007.csv` | §4, N6 and N7 per study |
| `pull_plan_20261007.csv` | §5, per study, with its tier |
| `census_summary_20261007.txt` | Every number above, as printed |
| `census_analyze.py` | The analysis (imports this worktree's `tools/` for the regexes and the tombstone reader) |

**The code (on the branch).**
- `tools/mri_archive.py` is the only access path. It provides:
  - `ReadOnlyArchive` (list, stat, open `rb`; `__slots__`; no client held; paths confined to the root; contents
    refused 08:00–18:00 Mon–Fri; calls paced in those hours);
  - `connect()` (SFTP only, one connection per process, `[mri_archive]` only);
  - `walk()` and `write_listing()`;
  - the `list` CLI.
- `tools/test_mri_archive.py` runs 68 checks. Every remote-write and shell attribute is absent. A non-`rb` open is
  refused before the remote is touched. The hours gate is tested at its edges. Paths outside the root are
  refused. A file holding only `[mri]` is refused. The password never appears in a message. A second connection is
  refused. An AST scan finds no remote-write call in the module.
