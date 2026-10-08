# The M. Jesús drive: close-out — every file's fate before the staged copy is deleted

**Status:** 🔶 READY FOR THE COORDINATOR · **Date:** 2026-10-08 · **Branch:** `feat/drive3-closeout`
**Read-only:** production (`J:\gjesus3-data\`) and the staged copy (`J:\_staging_drive3_MJ\`) were only read; nothing
was copied, written or deleted on either. Outputs went to `D:\projects\gjesus3\drive3_streams\closeout\`, and
SegBioMed's beside their manifest on D: (§6).
**Plan:** [`drive3_production_plan.md`](drive3_production_plan.md) "Close-out" (its four steps). **Tools:**
`tools/drive_staging/drive3/closeout.py` (the reconciliation), `closeout_records.py` (the evidence copy), tested by
`tools/test_drive3_closeout.py`.

---

## Verdict

**`BLOCKED: 380 files`** (210.9 GB), on 2026-10-08 against live production (a fresh `/raw/` index, `--stat`, `--walk`,
which said `BLOCKED: 254 files`; then re-run on the same index after **Ryan's ruling of 2026-10-08 on the DICOM-less
placeholders**, which turns their 126 drive files from "not kept" into blockers until placed). Every other file of the
drive (621,589 of 621,969) is kept in gjesus3 or ruled out by a category Ryan ruled or a gate decided.

| Blocker | Files | GB | Clears when | Expected? |
|---|---:|---:|---|---|
| **Outside-instrument raw:** Biodonostia's Axioscan 7 #4661000340 (144 copies of 116 `.czi`), biomaGUNE's former Leica SP8 (26 `.lif` / `.lifext`), and the one `.czi` with no instrument metadata (2 copies) | 172 | 208.35 | the foreign-raw batch is written (`feat/drive3-foreign-raw`: `XMIC` ingest, Leica placement, the stray `.czi`) | yes |
| **Stream C's `.czi` derivatives** (crops, renamed re-saves, scale-bar copies) that stream C handed to stream P in `tasks/drive3_czi_nonraw_for_stream_p.csv` (gate §5) and **no batch ever placed** | 78 | 2.46 | placed (5 into `0619` / `0522`, 72 into holding) | **no: a gap** |
| **`m152`'s three study-level ParaVision files** (`subject`, `AdjStatePerStudy`, `ScanProgram.scanProgram`): P2 placed the study's exam folders (never acquired) in `AE-biomaGUNE-0118`, not these | 3 | 0.00 | placed beside them | **no: a gap** |
| **A `2dseq`-only reconstruction of an exam production already held:** `20220309_111235_jrc220309_m53_0320_1_1/14` (`ACQ-20220309-MRI-070`, `AE-biomaGUNE-0320`) holds reconstruction 1 as DICOM; the drive also has reconstruction 3, as `2dseq` only. Stream M placed the 45 such reconstructions of its own exams (gate §3.2, P2); this exam was in production before stream M, so nobody did | 1 | 0.00 | placed with its `pdata\3\` (6 files), as P2 did | **no: a gap** |
| **The 10 DICOM-less placeholder exams** (A1 `b-empty-prod`; listed in §2): production registered them without DICOM (`pending_dicom_regen` `no-source` 8, `not-applicable` / WOBBLE 2). **Ryan, 2026-10-08: the placeholders are retired, their files kept** (the retirement is built on another branch and runs later), so their drive files, k-space and parameters, their only data, must not go with the staged copy | 126 | 0.10 | placed into the exam's project, as P2 placed unregistered exams | **ruled after the first run** |

**So the foreign raw is not the only blocker: 208 more files need a placement.** They are ready as one handover list,
[`drive3_closeout_handover.csv`](drive3_closeout_handover.csv) (§2), for stream P's later-batch path. Once the
foreign-raw batch and that list are written, the re-run (§4) should end `READY TO DELETE`.

**MRI originals not kept (§3), said plainly:** for the **963 drive-3 exams the platform's archive does not hold**,
gjesus3 keeps the DICOM only, and their ParaVision originals, **75.4 GB (73.8 GB of it k-space)**, go with the staged
copy. The only other copy gjesus3 knows of is the drive itself, returned to M. Jesús. 267 of the 963 are 11.7 T exams
(42.0 GB), 696 are 7 T exams of days the archive lacks (33.4 GB); where the platform keeps those is Ryan's question Q7
to the platform manager (STATUS §0.6). This follows Ryan's DICOM-only rule (2026-10-04); Ryan should see it before
the deletion.

**Also ready:** the evidence copy is planned (3,255 files, 3.44 GB, with tested copy and verify commands; §5).
SegBioMed's test-case manifest is remapped to production, outside the repo: 0 paths without a production location,
and 6 split volumes whose `.raw` the placement renamed (§6). On D:, about 781 GB of image copies and rehearsal roots
can go; the evidence folders follow after the copy (§7). §8 gives the deletion command and what to check first: the
NAS's recycle bin and snapshots keep the 1.68 TB in use after the delete, until QTS releases it.

---

## 1. Every file, one category

`closeout.py` gives each of the 621,969 rows of the staged copy's own `manifest.csv` one category: the first rule
that applies, in this order. **Kept** is decided by SHA-256 against live production; **not kept** only by a rule Ryan
ruled or a gate decided; anything else is a **blocker**.

| Fate | Category | Files | GB | Distinct contents | GB distinct | The rule |
|---|---|---:|---:|---:|---:|---|
| kept | `in-raw` | 282,129 | 782.67 | 209,287 | 714.57 | the bytes are a file of a registered acquisition (every live acquisition's `checksums.json`) |
| kept | `placed` | 127,339 | 199.97 | 51,590 | 135.42 | the bytes are listed in a project's `working\historical_drives\_INDEX.csv` (27 trees, every drive and batch) |
| kept | `holding` | 5,233 | 15.05 | 3,648 | 14.73 | the bytes are listed in the holding folder's `manifest.csv` |
| kept | `archive-expanded` | 2 | 0.00 | 1 | 0.00 | the `.zip` stream P expanded (P1; Ryan 2026-10-02: no zips): both members placed in `AE-biomaGUNE-0424` (the second file is its twin in `biomaGUNE MJ`) |
| not kept | `zero-byte` | 213 | 0.00 | 1 | 0.00 | no content (stream P: counted, never placed) |
| not kept | `junk` | 6,363 | 0.05 | 260 | 0.03 | Ryan's list of 2026-09-30 and A2's accepted additions (below) |
| not kept | `personal` | 1 | 0.00 | 1 | 0.00 | the `biomaGUNE MJ` gate's personal screen (§4 there); Ryan 2026-10-08: ignore |
| not kept | `mri-kspace` | 17,349 | 440.64 | 12,095 | 318.07 | Ryan 2026-10-04: MRI is registered with DICOM only; k-space (`fid`, `rawdata.job*`) of a registered exam (never of a DICOM-less placeholder: Ryan 2026-10-08) |
| not kept | `mri-2dseq` | 17,559 | 15.01 | 12,278 | 10.45 | the same rule: a `2dseq` whose reconstruction `/raw/` holds as DICOM |
| not kept | `mri-params` | 160,429 | 1.59 | 109,187 | 1.00 | the same rule: ParaVision parameter files of a registered exam (not a placeholder), or of a study with a registered exam |
| not kept | `mri-dicom-reexport` | 4,771 | 0.29 | 4,341 | 0.26 | DICOM of a registered exam that A1 found re-exported: the same instances with other bytes (A1 §2.2, 191 exams) |
| not kept | `czi-resave-of-production` | 119 | 12.48 | 118 | 12.45 | stream C gate §1.4: a re-save of a production acquisition (same instrument, second and name); each parent ACQ-ID checked live |
| not kept | `czi-resave-within-drive` | 82 | 2.57 | 82 | 2.57 | stream C gate §1.4 / R2: a same-name, pixel-identical re-save whose twin was ingested; each twin checked in `/raw/` |
| **BLOCKER** | | **380** | **210.92** | 298 | 163.14 | in no category (the Verdict table) |
| | **kept** | **414,703** | **997.70** | | | |
| | **not kept** | **206,886** | **472.62** | | | |
| | **total** | **621,969** | **1,681.24** | | | = `run_info.json` (1,681,243,787,145 bytes) |

(The table is the re-run after Ryan's placeholder ruling, `D:\…\closeout\run_20261008b\`, on the full run's `/raw/`
index; it differs from the full run, `run_20261008\`, only by the 126 placeholder files moved from `mri-kspace` 6 /
`mri-params` 120 to BLOCKER. The stat and walk below are the full run's.)

**The inputs, as the run read them:**
- **The manifest:** the staged copy's own `manifest.csv` (SHA-256 `0309adae…94bcf7d4`), byte-identical to A1's D: copy;
  its totals equal the copy run's `run_info.json`. No file of the drive was re-hashed.
- **`/raw/`:** built live at the run (`p_verify.live_raw_index`): 35,613 acquisitions, 647,057 files; 464 acquisitions
  list no file (MRI placeholders: `pending_dicom_regen` `not-applicable` 365 + `no-source` 99).
- **Placed:** every registered project's `_INDEX.csv` (27 trees; 76,220 rows) and the holding `manifest.csv` (59,481
  rows), all drives. A placed file points at **its own copy** when the index lists this very drive file (41,357), else at
  a copy with the same bytes (85,982: the drive holds most of its material twice, `MRI\` and `biomaGUNE MJ\`).
- **The NAS check (`--stat`):** for every kept content, one location was stat'ed on the NAS (the acquisition file, the
  placed copy or the held copy; the two `.zip` members too): **264,525 of 264,525 found, with the size the manifest
  gives; 0 missing.** The SHA-256 is the index's or `checksums.json`'s, written when each copy was verified.
- **The staged tree (`--walk`):** names and sizes of every file under `…\files\`: **621,969 files = the manifest; 0 the
  manifest does not list, 0 missing**; 7 differ in size, all junk: the 7 AppleDouble `._.DS_Store` of the pig folder
  that the NAS rewrites (the copy run's `verify_problems.csv`). So nothing would be deleted unreconciled.
- A1's per-file classes (`a1_files.csv.gz`, `mri_exams.csv`) for the MRI rules; stream C's `excluded.csv` and
  `out_of_scope.csv` for the `.czi` rules.

**The not-kept categories, in detail:**
- **Zero-byte (213):** 165 hidden temporary files (`.Cine_*.jpg-XXXX`) in `Pili y Mili\Draft papers\…\2-DG\MRI`, 22
  `Icon<CR>`, 10 HR-MAS `title` files, 5 Office owner files, 5 text files, 1 `.gitkeep`, and the 5 damaged raw MRI files
  A1 found (`rawdata.job0/1` of `jrc241001_m104_0522/17`, both copies, production calls the exam `no-source`; `MRIm7.dcm`
  of `jrc220303_m80_0320/3`, production holds the good file).
- **Junk (6,363):** `desktop.ini` 5,048; AppleDouble `._*` 1,032; `Thumbs.db` 106; `.DS_Store` 99 (all Ryan's list);
  the 2 WD installers (ruled); Office temporary files 55 and image-viewer caches 21 (A2's additions). **The 21
  `folders.cache` / `thumbs.cache` were opened (read-only):** each is a MATLAB 5.0 MAT file written 2019-11-11 holding a
  folder listing (`f`: name, folder, date, bytes, isdir) or `thumbinfo` (preview thumbnails, series description, path,
  slice position): a MATLAB image browser's cache of the DICOM `/raw/` holds, as A2's addition says. (Stream M kept the
  4 such files of the pig folder by path, as a precaution; these 21 hold no data of their own.)
- **Personal (1):** of the `biomaGUNE MJ` gate's 4 possibly personal files (names only, never opened), **3 are already in
  project folders by their bytes** (batch 1 placed their `Pili y Mili` copies in `AE-biomaGUNE-0619` 2 and `-0522` 1) and
  count as `placed`; the 4th is the one not kept. With Ryan's "ignore" (2026-10-08) nothing more is done.
- **MRI originals (195,337 files, 457.2 GB):** the k-space, `2dseq` and parameter files of **7,254 registered exams**:
  3,299 of the 3,309 stream M registered (the other 10 have every ParaVision file kept by its bytes; among them
  `m175` / `m178`, whose second copies P2 placed) and 3,955 production held before (by `<study>/<exam>` =
  `original_name`, read live), plus their studies' study-level files. A `2dseq` counts only when `/raw/` holds its
  reconstruction as DICOM (the acquisition's `recon<n>_*.dcm`); the one that is not is a blocker. **A DICOM-less
  placeholder (an exam whose acquisitions hold no file in `/raw/`) is never ruled out** (Ryan 2026-10-08): its drive
  files block until placed. §3 says how much of the rest the platform's archive holds.
- **DICOM re-exports (4,771):** the 191 exams of A1 class `b-export` (and the one `b-mixed`): production holds the same
  instances exported on another day (4,341 of 4,342 pairs pixel-identical; the last is the zero-byte file).
- **`.czi` re-saves (201):** stream C's 118 re-saves of production acquisitions (parent ACQ-IDs live today) and its 82
  same-name re-saves whose kept twin is in `/raw/`.

**Where the kept files are, by the drive's top folders** (files / GB): `MRI\` 191,086 / 31.05 kept, 117,061 / 271.85 not
kept (its originals); `Microscopio\` 6,774 / 730.34 kept; `biomaGUNE MJ\` 127,669 / 96.04 kept, 79,077 / 177.00 not kept
(the second copy of most MRI studies); `Pili y Mili\` 44,352 / 71.97 kept; `Otros\` 43,736 / 43.40 kept; `PET\` 1,084 /
24.91 kept. Placed files sit in 25 project trees (most: `0118` 35,720, `0619` 24,802, `0522` 20,969, `1019` 17,972).

---

## 2. The blockers, and the handover list that clears 208 of them

The per-file list is `D:\…\closeout\run_20261008b\blockers.csv` (with each file's folder and hint), and
`blockers_by_folder.csv`.

**The 172 outside-instrument files** are exactly stream C's out-of-scope list (`tasks/drive3_czi_out_of_scope.csv`, gate
§1.7): 144 Axioscan copies (201.63 GB) in `Microscopio\Microscopio biodonostia\…`, `Microscopio\Histologia_ratones_viejos\…`
and `biomaGUNE MJ\…\Microscopio-biodonostia`; 26 Leica files (6.72 GB) in `Pili y Mili\Proyecto 1121 London\Experimentos\
Histologia\…`; 2 copies of `m204lung.czi`. The foreign-raw batch covers all three (its HANDOFF, jobs 1–3).

**The other 208 are placement gaps**, all on stream P's own later-batch path (`p_plan.py handover`, as P2 and the
`biomaGUNE MJ` batch ran). [`drive3_closeout_handover.csv`](drive3_closeout_handover.csv) holds them, 259 rows:

| Rows | Kind | Project | What |
|---:|---|---|---|
| 77 | `derivative` (parent ACQ-IDs given) | holding 72, `AE-biomaGUNE-0619` 3, `-0522` 2 | stream C's list less the one already kept (`230530-ID161-alphasma8OHdG-lungs-20x-2.czi`, whose bytes drives 1+2 placed in `1019`); the 78th blocking file is the second copy of `ID 203 ROI masson`, kept by its bytes once the first is placed |
| 3 | `other` | `AE-biomaGUNE-0118` | `m152`'s study-level files, beside its exam folders |
| 6 | `other` | `AE-biomaGUNE-0320` | `jrc220309_m53_0320/14\pdata\3\`: the `2dseq` and its 5 parameter files, P2's "reconstruction without DICOM (2dseq only) of registered exam" |
| 173 | `notregistered:no-recon` 154, `notregistered:non-image` 19 | the exam's project (below) | **the 10 placeholder exams**: every drive file of each exam folder, every copy, as P2 handed over unregistered exams (so each folder gets `README_not_registered.txt`); less 4 zero-byte files (`m104_0522/17`'s `rawdata.job0/1`, both copies: refused by the tool, no content) and 2 `audita.txt` that batch 1 and the `biomaGUNE MJ` batch already decided (placed). 47 of the 173 are already kept by their bytes elsewhere; the folder is placed whole |

**The 10 placeholder exams** (Ryan 2026-10-08: retired, files kept). Each goes to
`projects\<project>\working\historical_drives\MJesus-MFB\…\<study>\<exam>\`; where the drive holds a second copy of
the folder (`MRI\` and `biomaGUNE MJ\`), it is a `duplicate-copy` (one study folder per content, A2 D3), kept by its
bytes:

| ACQ-ID (placeholder) | Exam | Regen state | Project | Placed / duplicate copies | Destination below `…\historical_drives\MJesus-MFB\` |
|---|---|---|---|---:|---|
| `ACQ-20260613-MRI-007` | `20220214_092942_jrc220214_m44_0320_1_1/33` | `no-source` | `AE-biomaGUNE-0320` | 6 / 0 | `Proyecto 0320\CAV1 Female 2022\…\33\` |
| `ACQ-20260613-MRI-028` | `20221128_115338_jrc221128_m10_0522_1_1/1` | `no-source` | `AE-biomaGUNE-0522` | 12 / 12 | `Proyecto 0522\Male HCH\…\1\` |
| `ACQ-20260613-MRI-029` | `20221128_115338_jrc221128_m10_0522_1_1/2` | `no-source` | `AE-biomaGUNE-0522` | 12 / 12 | `Proyecto 0522\Male HCH\…\2\` |
| `ACQ-20260614-MRI-048` | `20230614_123505_jrc230614_0522_m47_1_1/900000` | `not-applicable` (WOBBLE) | `AE-biomaGUNE-0522` | 5 / 5 | `Proyecto 0522\Female PAH\…\900000\` |
| `ACQ-20260613-MRI-039` | `20240530_082205_jrc240530_m43_1422_1_1/2` | `no-source` | `AE-biomaGUNE-1422` | 12 / 0 | `Manosa and 2DG Male_Proyecto 1422\Raw data\MRI\MJ 2024\…\2\` |
| `ACQ-20241001-MRI-099` | `20241001_100924_jrc241001_m104_0522_1_1/17` | `no-source` | `AE-biomaGUNE-0522` | 12 / 12 | `Proyecto 0522\MRI dietas females\…\17\` (its k-space is zero bytes on the drive: parameters only) |
| `ACQ-20260614-MRI-002` | `20241001_141059_jrc241001_m106_0522_1_1/5` | `no-source` | `AE-biomaGUNE-0522` | 11 / 11 | `Proyecto 0522\MRI dietas females\…\5\` |
| `ACQ-20241001-MRI-100` | `20241001_141059_jrc241001_m106_0522_1_1/8` | `no-source` | `AE-biomaGUNE-0522` | 14 / 14 | `Proyecto 0522\MRI dietas females\…\8\` (with its k-space, 3.3 MB) |
| `ACQ-20241010-MRI-104` | `20241010_092822_jrc241010_m29_1123_1_1/8` | `no-source` | `AE-biomaGUNE-1123` | 14 / 0 | `Bleomicina Mice_Proyecto 1123\Raw data\MRI\…\8\` (with its k-space, 93 MB) |
| `ACQ-20260614-MRI-007` | `20241011_093242_jrc241011_m24_1123_1_1/900000` | `not-applicable` (WOBBLE) | `AE-biomaGUNE-1123` | 9 / 0 | `Bleomicina Mice_Proyecto 1123\Raw data\MRI\…\900000\` |

All ten have a project (none goes to holding); every study keeps other exams with DICOM in `/raw/`, so the studies'
own files stay as ruled. Kinds: `no-recon` for the 8 `no-source` exams, `non-image` for the 2 WOBBLE adjustment scans.
After the retirement removes the placeholder rows, these files stay `placed` (the reconciliation decides by bytes).

**Dry-planned here, read-only** (stream P's tool against live production, every earlier manifest passed, today's
`/raw/` index): `handover (CO): 259 files {'holding': 72, 'place': 121, 'duplicate-copy': 66}; refused 0; destinations
already present: 0`; 2.56 GB copied (holding 2.37, `1123` 0.09, `0619` 0.05, `0522` 0.04); longest path 199 characters,
nothing shortened. Manifest: `D:\projects\gjesus3\drive3_streams\closeout\handover_plan_20261008c\placement_manifest.csv`
(the first plan, without the placeholders, is `handover_plan_20261008\`).

**The production commands** (copies only; the window procedure of `drive3_placement_gate.md` §5, as P2a ran it). Re-plan
first, because the foreign-raw batch may run before; then one window per tree:

```powershell
cd "C:\Users\rtasseff\OneDrive - CIC biomaGUNE\projects\DataInfra\gjesus3-archive\gjesus3-pilot"
$env:PYTHONDONTWRITEBYTECODE = 1
$S = "D:\projects\gjesus3\drive3_streams"; $NAS = "J:\gjesus3-data"; $D = Get-Date -Format yyyyMMdd_HHmm
$PP = "tools\drive_staging\drive3\p_plan.py"; $PV = "tools\drive_staging\drive3\p_verify.py"; $NP = "tools\drive_staging\nonraw_placement.py"
$M1 = "$S\placement\manifest_check2_20261006\placement_manifest.csv"
# 0. Re-plan against today's production (read-only). Add --manifest for any batch placed since (e.g. the Leica files).
python $PV raw-dedup --manifest $M1 --nas $NAS --write-index "$S\closeout\live_raw_index_$D.csv"
python $PP --nas $NAS handover --manifest $M1 --manifest "$S\placement\release_M1_20261006\placement_manifest.csv" `
    --manifest "$S\mri\out\p2\P2a_20261007_1053\placement_manifest.csv" --manifest "$S\mri\out\p2\P2b_20261007_1053\placement_manifest.csv" `
    --manifest "$S\mri\out\p2\P2b_masks_20261007_1053\placement_manifest.csv" --manifest "$S\bmj\batch3_v2\placement_manifest.csv" `
    --csv tasks\drive3_closeout_handover.csv --stream CO --raw-index "$S\closeout\live_raw_index_$D.csv" --out "$S\closeout\handover_$D"
#   expect: handover (CO): 259 files {'holding': 72, 'place': 121, 'duplicate-copy': 66}; refused 0;
#           destinations already present: 0
$A = "$S\closeout\handover_$D\placement_manifest.csv"; $SCR = "$S\closeout\scratch"
# 1. the six project windows: snapshot, dry run, execute, verify
#    (files copied: 0118 3, 0320 12, 0522 68, 0619 3, 1123 23, 1422 12)
foreach ($p in 'AE-biomaGUNE-0118','AE-biomaGUNE-0320','AE-biomaGUNE-0522','AE-biomaGUNE-0619','AE-biomaGUNE-1123','AE-biomaGUNE-1422') {
  python $PV snapshot --manifest $A --nas $NAS --project $p --to "C:\Users\rtasseff\temp\gjesus3_placement_backup_${D}_drive3_CO_$p"
  python $NP --out "$S\closeout\runs_CO" --nas $NAS copy --manifest $A --scratch $SCR --project $p
  python $NP --out "$S\closeout\runs_CO" --nas $NAS copy --manifest $A --scratch $SCR --project $p --execute
  python $NP --out "$S\closeout\runs_CO" --nas $NAS verify --manifest $A --project $p
  python $PV verify --manifest $A --nas $NAS --snapshot "C:\Users\rtasseff\temp\gjesus3_placement_backup_${D}_drive3_CO_$p" --project $p --rehash all
}
# 2. the holding window (72 files, 2.37 GB)
python $PV snapshot --manifest $A --nas $NAS --holding --to "C:\Users\rtasseff\temp\gjesus3_placement_backup_${D}_drive3_CO_holding"
python $NP --out "$S\closeout\runs_CO" --nas $NAS holding --manifest $A --scratch $SCR
python $NP --out "$S\closeout\runs_CO" --nas $NAS holding --manifest $A --scratch $SCR --execute
python $PV verify --manifest $A --nas $NAS --snapshot "C:\Users\rtasseff\temp\gjesus3_placement_backup_${D}_drive3_CO_holding" --holding --rehash all
#   expect after each window: VERIFY PASS
```

**Stop** if step 0 refuses a row or finds a destination present, or a window's verify fails. Each derivative's
provenance starts with its parent ACQ-ID (`kind = derivative`); the six `pdata\3\` files and `m152`'s three carry
P2's reasons; each placeholder file's reason names its ACQ-ID, its regen state and Ryan's ruling. The windows must run
before the staged copy is deleted (they copy from it); their order with the placeholder retirement does not matter for
the close-out, which decides by bytes.

**The foreign-raw session's Leica placement is a fourth placement batch on the same tool**; the coordinator can run this
list as part of it or as its own window (copies only: the coordinator's to approve under the drives' model).

---

## 3. MRI originals not kept: what goes with the staged copy

Ryan's rule (2026-10-04): MRI enters `/raw/` as DICOM only. So the ParaVision originals of every registered exam (k-space,
`2dseq`, parameters) are **not kept in gjesus3**, here as for every MRI ingest. Whether they survive elsewhere depends on
the MRI platform's own archive (`backup_7T_olddata_260824`; census of 2026-10-07; the originals check of stream M's exams
on `feat/mri-archive-ingest`, `tasks/drive3_mri_archive_check.md`).

| Exams | Count | Files (all copies) | GB, all copies | **GB, distinct** | of it k-space |
|---|---:|---:|---:|---:|---:|
| **Stream M's exams the archive does NOT hold** | **963** | 21,397 | 104.97 | **75.37** | **73.76** |
| … 11.7 T exams (the archive is the 7 T's) | 267 | | | 41.99 | 41.47 |
| … 7 T exams of days the archive lacks | 696 | | | 33.39 | 32.30 |
| Stream M's exams the archive holds (compared: none differs) | 2,336 | 64,133 | 149.26 | 105.03 | 101.13 |
| Exams production held before stream M, study **in** the archive listing (by name) | 1,168 | 24,252 | 49.58 | 40.48 | 38.75 |
| Exams production held before stream M, study **not** in the archive listing | 2,787 | 69,664 | 152.96 | 108.46 | 104.42 |
| Study-level parameter files (no exam) | 421 studies | 15,891 | 0.48 | 0.34 | 0 |

**Plainly:** deleting the staged copy removes the only copy gjesus3 has seen of **75.4 GB of ParaVision originals
(73.8 GB k-space) for the 963 drive-3 exams the platform's archive does not hold**. Their images stay in `/raw/` as DICOM
(the scanner's own for 3,132 of stream M's exams; Dicomifier's, made from the drive's `2dseq`, for 177). The drive
itself is M. Jesús's and was returned to her, so it remains a copy outside gjesus3, not under the Data Office's control.

Two more things Ryan should see with it (a third, the placeholders, he has ruled):
- **`jrc200615_m21_1019`:** the archive's tarball of this study is short (its `.sha1` was taken from the short file), so
  **the drive is the only complete copy known** (19 of its exams partly or wholly absent from the archive). Its originals
  on the drive: 20 exams, 0.87 GB distinct (0.81 GB k-space).
- **The earlier exams whose study is not in the archive listing (2,787, 108.5 GB distinct)** are mostly recent: by scan
  year 2021 0.07 GB, **2022 21.2 GB, 2023 25.9 GB, 2024 61.3 GB**. The archive covers 2019–2022; the scanner keeps about
  two years, so the 2024 ones may still be on it; where 2023 (and the missing 2022 days) went is Ryan's question Q7 to
  the platform manager (STATUS §0.6). Not a loss known today; not checked here exam by exam.
- **The 10 exams production holds as DICOM-less placeholders** (A1 `b-empty-prod`: 8 `no-source`, 2 WOBBLE): their
  drive files (k-space and parameters, 0.10 GB of k-space in all copies) are their only data. **Ryan, 2026-10-08: the
  placeholders are retired and their files kept.** So they are not in the table above: they are placed by the handover
  (§2), and the reconciliation never rules a placeholder's files out.

**If Ryan wants the 963 exams' originals kept after all,** the smallest step is to place their distinct non-DICOM files
(75.4 GB, about 21,000 files) in the projects or the holding folder with the same handover tool before the deletion.
Per-exam figures: `D:\…\closeout\run_20261008b\mri_originals.csv` (one row per exam: archive result, year, k-space /
`2dseq` / parameter bytes, distinct bytes).

---

## 4. Re-running the reconciliation (the coordinator, after the foreign-raw batch and the handover)

Read-only; about 40 minutes (2026-10-08: the live `/raw/` index 27 min, the stat of 264,525 kept contents 8 min, the
walk 3 min). Outputs: `closeout_summary.txt` (the report), `categories.csv`, `blockers.csv`, `blockers_by_folder.csv`,
`mri_originals.csv`, `closeout_files.csv.gz` (every file: category, where it is kept, the rule's detail),
`live_raw_index.csv`, `walk_differences.csv`.

```powershell
cd "C:\Users\rtasseff\OneDrive - CIC biomaGUNE\projects\DataInfra\gjesus3-archive\gjesus3-pilot"
$env:PYTHONDONTWRITEBYTECODE = 1
$D = Get-Date -Format yyyyMMdd_HHmm
python tools\drive_staging\drive3\closeout.py --out "D:\projects\gjesus3\drive3_streams\closeout\final_$D" --stat --walk
#   expect, last line:  READY TO DELETE   (exit code 0)
#   expect in the table: BLOCKER 0; in-raw grows by the XMIC copies (144), placed / holding by the Leica files (26),
#   the stray .czi (2) and the handover's blockers (82 + the placeholders' 126); every not-kept category unchanged.
```

- `--archive-check` defaults to `tasks/drive3_mri_archive_check.csv`, which arrives on `main` with `feat/mri-archive-ingest`;
  until then pass `--archive-check` a copy of it (`git show feat/mri-archive-ingest:tasks/drive3_mri_archive_check.csv`),
  or the §3 statement shows the stream M exams as "earlier". The verdict does not depend on it.
- `--raw-index <csv>` reuses an index saved the same day (`p_verify.py raw-dedup --write-index`); the run refuses one
  older than the registry (an input problem blocks the verdict).
- **If the foreign-raw batch drops some Axioscan copies as re-saves** (stream C's rules: same instrument, second and
  name, other bytes), pass its `excluded.csv` after stream C's: `--czi-excluded <stream C's> <the foreign raw's>`.
  Byte-identical copies need nothing: they are kept by their bytes.
- **Stop** on anything but `READY TO DELETE`. A new blocker is listed in `blockers.csv` with its folder and a hint.

---

## 5. The evidence copy (plan only; the coordinator runs it)

To `J:\gjesus3-data\staging\historical_drives_records\drive3_MJesus_WX22D623YP29\`, beside drives 1+2's records, in the
same form: files copied and SHA-256-verified, listed in the folder's `records_manifest.csv`, with a section in its
`README.txt`.

The plan as built on 2026-10-08 (`closeout_records.py plan`, read-only; `D:\…\closeout\records_plan_20261008\`):

| What | Files | GB | Source |
|---|---:|---:|---|
| the staging run's own records: `manifest.csv` (the SHA-256 of all 621,969 files), `copy.log`, `console.log`, `verify.log`, `verify_console.log`, `verify_problems.csv`, `errors.csv`, `drive_info.txt`, `run_info.json`, `run_copy.cmd`, `run_verify.cmd` | 11 | 0.17 | the top of `J:\_staging_drive3_MJ\drive3_MJesus_WX22D623YP29\` |
| the assessment: A1, A2, A3 (with SegBioMed's `a3\manifests\` and the remap), the production index of 2026-10-06, the hub's records snapshot, the 2026-10-08 answers | 168 | 0.81 | `D:\projects\gjesus3\drive3_analysis\` → `drive3_analysis\` |
| the streams' evidence: `placement\` (manifests, runs, the M1 release), `bmj\` (lists, batches, checks, runs), `czi\` (catalog, plan, logs), `mri\out\` (plans, case tables, dry runs, verifications, P2), `petct\` (out, scripts), the workbook backups, `xmic\` (the foreign-raw batch, in flight), `closeout\` (this run, the handover plan) | 3,076 | 2.46 | `D:\projects\gjesus3\drive3_streams\` → `drive3_streams\` |
| **total** | **3,255** | **3.44** | longest destination path 224 characters; no duplicate destination |

**Left out, on purpose (551,341 files; image data or regenerable bulk, not evidence):** the local copies of drive images
(`czi\local\` 645.4 GB, `xmic\local\` 153.9 GB) and their hard-link farms (`czi\farm\`, `xmic\farm\`, `xmic\varL\`: no
space of their own); the streams' staging copies (`mri\stage\` 26.9 GB, `petct\stage\` 39.1 GB); the rehearsal NAS roots
(`xmic` 116.0, `mri` 26.7, `petct` 16.1, `bmj` 13.5, `czi` 8.4, `placement` 5.7 GB); A1's pickle caches (0.77 GB);
`xmic\labels\` (127 slide-label `.png`); scratch folders; a few non-documents (registry backup copies, a `.bak`). The D:
copy of the drive manifest is left out because it is byte-identical to the staged one, which is copied. The full list
with sizes: the plan's `excluded.csv`.

**Commands** (after the final close-out run of §4, so that its output folder is part of the copy):

```powershell
$R = "D:\projects\gjesus3\drive3_streams\closeout\records_plan_$(Get-Date -Format yyyyMMdd)"
python tools\drive_staging\drive3\closeout_records.py plan --out $R      # about 30 min: it also sizes the left-out folders
#   expect: about the files and GB of the table above (plus the final run's folder and the foreign-raw batch's last
#   records); "duplicate destinations 0"; the longest destination path well under 260 characters (224 today)
python tools\drive_staging\drive3\closeout_records.py copy --plan "$R\records_plan.csv"             # dry run
#   expect: "to copy <n>, already there and identical 0, conflicts 0"
python tools\drive_staging\drive3\closeout_records.py copy --plan "$R\records_plan.csv" --execute
#   expect: "COPY DONE: <n> copied and re-hashed; records_manifest.csv +<n> rows; README.txt gained the drive-3 section"
python tools\drive_staging\drive3\closeout_records.py verify --plan "$R\records_plan.csv"
#   expect: RECORDS VERIFY PASS (every file re-hashed from the NAS)
```

`copy` never writes over another file (an identical one is skipped, a different one stops the run), hashes each source
as it reads it (a source changed since the plan stops the run) and re-hashes each copy; `records_manifest.csv` keeps its
BOM, CRLF and every existing row, and gains one row per new file; `README.txt` gains the drive-3 section once
(the text: `README_SECTION` in `closeout_records.py`; it says what is there, what is deliberately not, and where the data
went). Re-running `copy` copies nothing and changes neither document.

---

## 6. SegBioMed's coupling

Their R1 test-case manifest (`D:\projects\gjesus3\drive3_analysis\a3\manifests\r1_testcases.csv`, 1,198 rows) pointed
`mask_path` / `split_path` at the staged copy. **Beside it, outside the repo,** `remap_r1_to_production.py` (read-only)
wrote **`r1_testcases_production.csv`**: the same columns in the same order with every staged path replaced by its
production location, plus six columns at the end (the old staged path, how the copy was found, and the `.raw` check).
Log: `remap_r1.log`. Their memo is untouched; the coordinator replies.

- **Every staged path has a production location: 0 without one.** Masks: the 660 CAND-A masks were staged, all remapped
  to their own placed copy; the other 538 already pointed at production (`curated_datasets\…`: DS-SEG-0001's 120,
  DS-SEG-0003's 418). Splits: 780 staged (CAND-A 660, DS-SEG-0001 120), 765 remapped to their own copy and 15 to a
  byte-identical copy (the drive's second copy of the folder); DS-SEG-0003's 418 already pointed at production. Each
  chosen file was stat'ed on the NAS (present, the index's size). Longest path 238 characters, no non-ASCII path.
- **`jrc240530_m43_1422`** (placed by the `biomaGUNE MJ` batch): its 15 rows now have both paths in production.
- **⚠️ 6 split volumes do not open as placed:** `jrc_210809_m62_1019`, phases 10–15. The placement shortened both the
  `.mhd` and its `.raw` file names (the 240-character rule), but the `.mhd` header's `ElementDataFile` still names the
  original `.raw`. The new `split_raw_path` column gives the real `.raw` (`split_raw_check` = `N` on those 6 rows; `Y`
  on the other 774 remapped splits, whose `.raw` is beside them under the name the header gives; blank on DS-SEG-0003's
  418). A reader opens those 6 with the `.raw` path given, or from a local copy of the pair under the original names.
  **The same break affects 225 placed MetaImage pairs from drive 1 in `AE-biomaGUNE-1019`** (§9).

---

## 7. `D:\projects\gjesus3\` scratch

Listed 2026-10-08 (sizes as Windows reports them; `czi\farm\` is hard links into `czi\local\`, so it takes no space of
its own). **Nothing was deleted.**

| Folder | Files | Size | What it is | Safe to delete? |
|---|---:|---:|---|---|
| `drive3_analysis\` | 180 | 1.75 GB | the assessment (A1–A3), the D: copy of the drive manifest, the production index of 2026-10-06, the hub's records snapshot, SegBioMed's `a3\manifests\` | **after the evidence copy** (§5); keep `a3\manifests\` until SegBioMed has taken `r1_testcases_production.csv` (their memo points there) |
| `drive3_streams\`: the evidence (plans, manifests, run logs, `closeout\`) | 3,076 | 2.46 GB | what §5 copies | **after the evidence copy and the last two batches**: the handover (§2) and the foreign-raw placement read stream P's earlier manifests here |
| `drive3_streams\xmic\` (local copies 153.9 GB, rehearsal root 116.0 GB, hard-link farms, placement 6.8 GB) | ≈ 8,900 | ≈ 277 GB listed | **the foreign-raw batch's work, in flight** (it appeared during this session) | **no, not yet**: once that batch is written and verified, its bulk goes like stream C's and its records with §5 |
| `drive3_streams\czi\local\` (+ `farm\`) | 5,123 | 645.4 GB | local copies of the drive's Cell Observer `.czi` | **yes**, once the handover (§2) is placed: matched to the close-out by path and size, 4,956 are in `/raw/` by their bytes, 89 are ruled-out re-saves, 1 is placed, and 77 are the derivatives the handover places (it copies from the staged copy, not from here); the foreign raw is not among them |
| `drive3_streams\mri\stage\`, `petct\stage\` | 252,275 / 985 | 26.9 / 39.1 GB | streams M and N's staging copies (drive files and Dicomifier's conversions) | **yes**: both streams written and verified |
| the rehearsal NAS roots: `mri\`, `petct\`, `czi\rehearsal_nas\`; `bmj\rehearsal\`; `placement\rehearsal\` | ≈ 279,000 | 26.7 / 16.0 / 8.4 / 13.5 / 5.5 GB | copies of production files and drive data for the rehearsals | **yes** |
| `mri_archive\` | | ≈ 219 GB pulled, plus its extraction | the platform-archive pull and ingest | **no: live work**, keep |
| `scratch_mri-unparsed-report\` | 41 | 3 MB | the 2026-10-05 MRI unparsed-rescan report (not drive 3) | not this close-out's call |
| `_p3test\`, `data_test\`, `dicomifier_pilot\`, `home\` | 52 / 4,144 / 584 / 1 | 0.00 / 2.76 / 0.04 / 0.00 GB | older work outside the historical drives (drives 1+2's erase left them too) | not this close-out's call |

Freed by the "yes" rows: about 781 GB of D:. The `drive3_streams\` evidence and `drive3_analysis\` (about 5 GB) follow
once their conditions hold.

---

## 8. The deletion

**What:** `J:\_staging_drive3_MJ\` — the staged copy (`drive3_MJesus_WX22D623YP29\files\`, 621,969 files, 1,681 GB) and
its 11 record files, which the evidence copy keeps. **On Ryan's go** (production plan, close-out step 4). The owner keeps
her drive; staging is not a backup.

**Check first, in this order:**
1. **The final close-out run (§4) ends `READY TO DELETE`** with `--stat --walk`, after the foreign-raw batch and the
   handover list are written and verified.
2. **The evidence copy (§5) is done and `verify` says `RECORDS VERIFY PASS`** (the final run's folder included).
3. **Ryan has seen §3** (the MRI originals not kept) and gives the go.
4. **SegBioMed has its production manifest** (§6; the coordinator's reply), since their R1 manifest pointed at the staged copy.
5. **Nothing reads the staged copy any more:** no open session works from it (the foreign-raw batch, any MRI check);
   `convert_staged_exams.py` and the stream stagings worked from copies on D:.
6. **Know what the deletion frees, and when.** The share keeps a **Network Recycle Bin** (`J:\@Recycle`) and **snapshots**
   (`J:\@Recently-Snapshot`: daily for the last week, weekly, monthly back to 2026-03-02). A delete over SMB moves the files
   into the recycle bin, and every snapshot since 2026-10-02 still holds the staged copy's blocks: **the 1.68 TB comes back
   only when the recycle bin is emptied (QTS) and the last snapshot holding it expires or is removed (QTS Storage &
   Snapshots).** Both are QTS administrator actions, for Ryan to decide; the gjesus3 data itself is untouched by either.

**The command** (long paths: 951 files have 260–277 characters, so `robocopy`, which handles them, mirrors an empty
folder onto the staged copy; it logs what it removes):

```powershell
$E = "C:\Users\rtasseff\temp\empty_for_drive3_delete"; New-Item -ItemType Directory -Force $E | Out-Null
$T = "J:\_staging_drive3_MJ\drive3_MJesus_WX22D623YP29"
$L = "C:\Users\rtasseff\temp\drive3_staging_delete_$(Get-Date -Format yyyyMMdd_HHmm).log"
robocopy $E $T /MIR /L /NFL /NDL /NP /R:1 /W:1 /LOG:"$L.dryrun"      # list only: deletes nothing
#   expect in the summary: Files ... Extras 621,980 (621,969 + the 11 records); Copied 0. Any other count: stop and look.
robocopy $E $T /MIR /NFL /NDL /NP /R:1 /W:1 /LOG:$L                    # the deletion
#   robocopy exit code 2 (extras removed) is success; 8 or more is a failure: read $L
Remove-Item -LiteralPath "J:\_staging_drive3_MJ" -Recurse -Force      # the emptied folders
Test-Path "J:\_staging_drive3_MJ"                                       # expect: False
```

Then record it (STATUS, CHANGELOG: date, files, the robocopy summary) and, if Ryan wants the space now, empty the recycle
bin's `_staging_drive3_MJ` entry in QTS File Station and review the snapshot schedule.

---

## 9. For the coordinator: unsettled, and findings

1. **208 files to place (§2).** Stream C's derivative handover never ran; P2 left `m152`'s study files out; a 2dseq-only
   reconstruction of a pre-existing exam had no owner; and the 10 placeholder exams' files (Ryan, 2026-10-08). The
   handover list is ready (259 rows, dry-planned: refused 0); it is a copy-only batch.
2. **MRI originals (§3)** need Ryan's eyes before the go: 75.4 GB for the 963 exams the archive lacks; the `m21_1019` short
   tarball. Proposed: as ruled (DICOM only), unless Ryan says keep. (The placeholders' files are kept, as ruled.)
3. **231 placed MetaImage volumes do not open as placed (a placement-tool finding, not a close-out blocker):** the
   240-character rule shortened their `.raw` file names but not the `ElementDataFile` line inside the `.mhd`; checked by
   reading every affected `.mhd`: 225 from drive 1 (`FRIO-X6`) and 6 from drive 3, all in `AE-biomaGUNE-1019`. The bytes are
   all kept (`_INDEX.csv` maps every name). Options for BACKLOG: rewrite those `.mhd` headers to the shortened names (the
   index's SHA-256 of each `.mhd` then changes, so with a recorded repair), or shorten such pairs by a shared stem in
   `historical_paths.py` for future batches.
4. **The 21 MATLAB viewer caches** are junk by A2's addition and by their content (§1); stream M kept 4 such files of the
   pig folder by path. Consistent enough; noted so nobody re-opens it.
5. **`ACQ-20220309-MRI-070`'s notes say "recons kept: 1,3"** but the acquisition holds reconstruction 1 only (15 files);
   reconstruction 3 never had DICOM. The handover places its `2dseq`; the note is the June scanner load's and is left as is.
6. **D: scratch (§7):** delete only after the evidence copy, and keep `drive3_streams\` until the foreign-raw batch and
   the handover batch are done (their tools read the earlier manifests there).
7. **The recycle bin and the snapshots (§8, check 6)** decide when the 1.68 TB is really free: a QTS decision for Ryan.

**Proposed record lines** (the coordinator applies them; I edited none):
- STATUS §2, "The M. Jesús drive": *Close-out reconciliation 2026-10-08 (`feat/drive3-closeout`): of 621,969 files,
  414,703 kept (997.7 GB: `/raw/`, projects, holding), 206,886 ruled out (472.6 GB: MRI originals by the DICOM-only rule,
  junk, zero-byte, re-saves, re-exports, 1 personal), 380 blocking: the 172 outside-instrument files (foreign-raw batch) and
  208 to place (handover list ready: stream C's 78 derivatives, `m152`'s 3, one 2dseq-only reconstruction, and the 10
  DICOM-less placeholder exams' 126 files, Ryan 2026-10-08). MRI originals of the 963 exams the archive lacks: 75.4 GB,
  not kept.*
- BACKLOG: the 231 placed MetaImage pairs whose `.mhd` names a renamed `.raw` (§9.3).
