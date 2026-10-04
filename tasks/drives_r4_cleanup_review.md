# The drives' same-timestamp groups (gate rule R4): pixel check, classes, retire lists

**Status:** 🔶 analysis done 2026-10-02. **Ryan approved all four lists on 2026-10-04**, and the destination layout became
stream A's short-path rule the same day. The lists are regenerated and dry-run (quick and full), **none executed**: they
wait for the coordinator's write window.
**Author:** stream D of the weekend close-out (Sonnet), branch `feat/drives-r4-cleanup`, for the coordinator (`gj3-handoff`).
**What this is:** close-out plan Step 5 item 3, "Clean up the same-timestamp groups". Read-only throughout: the staged
copies on D: and production were only read; nothing was written to the NAS.

---

## 0. The result in one screen

**819 files in 247 groups (731.4 GB) were checked against the other members of their group, tile by tile, byte for byte.**
(The 49 groups whose members sit at different stage positions, 135 files, got the identical-tile test only: §10.)
Ryan's principle (2026-10-01) is the rule: the acquisition stays in `/raw/`; scale-bar copies, thumbnails and exports go to
the original's project folder; a file stays flagged only when it is genuinely ambiguous.

| | files | GB | what happens |
|---|---:|---:|---|
| **Stay in `/raw/`** | **350** (+ ID65) | 479.5 (+ 2.95) | 195 originals, 153 `distinct` sibling scenes whose master is not on the drive, 2 ambiguous |
| **List a** `2026-10_r4_scalebars.csv` | 3 | 0.1 | scale-bar copies of an original that has a project |
| **List a2** `2026-10_r4_resaves.csv` | 9 | 14.3 | identical re-saves of an original that has a project |
| **List b** `2026-10_r4_exports.csv` | 60 | 1.4 | crops and subsets under 5% of the original's size (thumbnails, `-scale` crops) |
| **List b2** `2026-10_r4_roi_crops.csv` | 81 | 184.3 | larger crops and subsets: **ROI re-saves of 0.46 to 3.7 GB each** (median 75% of their original's size), a separate file for a separate decision |
| Waiting (original has no project) | 61 | 12.3 | scale-bar copies 14, re-saves 42, crops 4, subset 1: listed once the mapping round (2b) gives the original a project |
| Proposal (c), Ryan decides | 255 | 39.4 | 182 scene splits, 72 stitched copies, 1 rendering. No list (§7) |
| **Derivatives in all** | **469** | **251.8** | 57% of the files, 34% of the bytes |

- **Ryan's decisions, 2026-10-04:** all four lists are approved (153); `ID65` stays in `/raw/`; the 90 `raw_linked` links
  may go; proposal (c) and the 61 no-project derivatives wait, with no list. **One change before any write: the
  destination layout.** Ryan rejected long paths and zips, so every destination now comes from stream A's short-path rule
  (§6): `<project>\working\historical_drives\<FRIO-X6 | MFB-Disco-2>\<study folder>\<path below>`, at most 240 characters on
  `\\GJESUS3\gjesus3\`. The five ROI paths that were over 259 are now 236 to 240.
- **The four lists are 153 acquisitions, 200.1 GB, into six active projects** (`1321` 90, `1123` 35, `0721` 13, `0219` 12,
  `0420` 2, `1019` 1). **Nothing is deleted: a derivative is hard-linked into the original's project under
  `working\historical_drives\…`** and only then its ACQ-ID is retired (§6). Every list passed `verify-lists`
  against production (0 problems, destinations included) and a `--quick` dry run (exit 0, nothing written).
  Every list also passed a **full** dry run (the file to be moved is hashed over SMB and checked against its
  `checksums.json`), with the retire tool as it is on `main` (v2): 153 of 153 items with work, 0 already done, no warning,
  refusal or error, "nothing written", and **the tool's own plan equals every list row (153 of 153 destinations)**. The ROI
  list took 28 minutes.
- **The conflict and closed-project cases are empty:** no derivative has a project different from its original's (0), and
  no original's project is closed (0).
- **`ID65_PB_lung_20x_scale.czi` is not a scale-bar copy and stays** (§9). The BACKLOG expected it to be listed by name;
  it is the only record of its acquisition. This deviates from the BACKLOG, on evidence.
- **Surprises, each with its section:**
  1. A name with "scale" is a poor guide: of the 31 such names, **13** are scale-bar copies, 14 are crops, 2 scene splits,
     1 a stitched copy, 1 an original (ID65). And 160 files carry the scale-bar overlay without "scale" in the name (§1).
  2. **Crops and subsets are mostly not thumbnails**: of the 146, 81 are ROI re-saves of 0.46 to 3.7 GB (184 GB, median 75%
     of the original's size), 72 of them in `1321` and `1123`. 63 of those 81 have a `raw_linked` link today that the move
     removes (§6).
  3. A stitched copy often **keeps the original's tiles verbatim** and only re-places them (33 of 72); one new test
     (`region`) was needed for a crop that ZEN re-blocked from its own origin (1 file, §4 example C).
  4. A composite-image comparison would have been wrong: it depends on the paste order in the tile overlaps (§4 example A).
  5. Six plate groups (the "Herida" and "ROS" series of June and July 2024, on drive 2) hold **211 of the 294 derivatives**
     that wait for a project (§8). Mapping those six groups unblocks most of the rest.
- **§11 has the ten questions of 2026-10-02 with Ryan's answers, and the one that is left:** 50 `1321` files have no study
  folder near them, so they keep their drive path (shortened where needed) instead of a study folder.
- **After the retire run, one more step:** `r4_groups.py index` merges a row per retired derivative into each project's
  `_INDEX.csv` (§6). It is prepared and dry-run; it refuses to write until the files are at their destinations.

---

## 1. Reconciling the numbers

### 1a. 869 versus 819

The handoff mentions "869 flagged sidecars" against 819 group members. **There is no discrepancy.** The 869 is the number
of acquisitions in batches B01-B04 (`XMIC` 338 + `AE-biomaGUNE-0118` 140 + `LSM9` 387 + `ZWSI` 4), of which only 53 carry
the R4 flag (`tasks/drives_ingest_dryrun_review.md` §7). Across all 16 batches the flagged population is exactly **819
acquisitions in 247 groups**:

- 819 registry rows (`ingest_config` `drives_2026-09`) carry the clause "shares its acquisition timestamp with N other
  file(s)" in `notes`, and no other registry row does;
- those 819 ACQ-IDs are exactly the 819 `acq_group` rows of the frozen plan (`expected.csv`), each joined to its ACQ-ID
  through `tasks/drives_ingest_provenance.csv` on `sha256` and checked on `relpath` / `archive` + `member`, and each one's
  registry `original_name` and project equal the plan's (0 mismatches);
- a random sample of 40 sidecars all carry `discovered.drv_acq_group` and a matching `drv_acq_group_n`.

### 1b. The BACKLOG's three measurements, against the pixel check

The BACKLOG item ("Clean up the drives ingest's same-timestamp groups") measured from file names and sizes. The pixel check
changes each figure:

| BACKLOG (2026-10-01, from the frozen plan) | Measured (2026-10-02, pixel check) |
|---|---|
| **31 files have `scale` in the name (3.4 GB).** Scale bars are overlays, so the pixels match the original. | 31 names, 3.35 GB, but **only 13 are scale-bar copies** (0.26 GB). The others: 14 crops (0.12 GB, a crop with the bar added), 2 scene splits, 1 stitched copy, and 1 original: ID65, 2.95 GB, 88% of the 3.4 GB. In all, 17 files are scale-bar copies; 4 of them have no "scale" in the name (two say `escala`, two say nothing: `ID162_Corazon2_PR_POL`, `56_cayado_10x_b`). A scale-bar overlay is in the XML of 189 files (160.9 GB); only 29 of those have "scale" in the name. |
| **About 18 small export-named files** under 5% of their group's original (e.g. `Untitled5`). | **60 crops** are under 5% of their original (1.4 GB; 46 have no "scale" in the name). `Untitled5.czi` (21 MB) is one: a crop. Another 152 files under 5% are the per-well scene splits of the plate groups, and 1 is a stitched copy. |
| **About 550 more are scene splits and stitched copies (~320 GB).** | **254 are** (182 scene splits 11.6 GB + 72 stitched copies 27.8 GB = **39.4 GB**). The other members that are not originals are 136 crops and 10 subsets (191 GB), 51 identical re-saves (20.7 GB), and 155 that are not derivatives (153 distinct, 2 ambiguous). The "~320 GB" is the size of the 195 originals (320.7 GB), not of the splits and stitched copies. |
| All are flagged except **ID65**, which has no group, so a clean-up has to list it by name. | Confirmed: it is the only file with no group flag. **It is not a copy of anything** (§9). |

The BACKLOG example is also refined: `0721-M113-Liver-PB-20X.czi` (2.9 GB) is not a second original next to
`-Original` (3.2 GB), it is a stitched copy of it; the five 6 to 15 MB "scale" files are four crops of the original and
one crop of the stitched copy (§4 example B).

---

## 2. The rule and the method

**Ryan's principle (2026-10-01):** the acquisition (or reconstruction) goes in `/raw/`; derivatives and complements go in the
project folder; a file stays in `/raw/` flagged only when it is genuinely ambiguous. A derivative leaves `/raw/` through
`tools/retire_acquisition.py` in `derivative` mode (§6). The bytes move to the project; nothing is dropped.

**What the pixel check is.** All 819 members are UNCOMPRESSED `.czi` (Cell Observer, LSM 900 and the Charité Axio
Imager: no JPEG XR, no zstd), so the stored bytes of a subblock ("tile") are its pixels. The staged copy on D: is
byte-identical to production (SHA-256 checked at ingest, and checked again for every listed file by `verify-lists`).
`tools/drive_staging/r4_groups.py pieces` caches, for every file, the position, shape and SHA-256 of every level-0 tile
(819 of 819 caches verified, 0 bad). Pairs inside one group are then related by exact tests; **a hit is exact equality of
every value compared, never a tolerance:**

| test | what it proves | what it finds |
|---|---|---|
| **identical tiles** | every tile of A is byte-identical to a tile of B, all at ONE constant offset (a scene offset counts) | scale-bar copy, renamed re-save, scene split, whole-tile subset |
| **cut tiles** | every tile of A is a byte-exact sub-rectangle of a tile of B, ONE offset | a ZEN crop ("ROI"): ZEN cuts the border tiles |
| **region** | the whole image of A equals a region of B's image at ONE offset, although A's blocks are its own | a crop ZEN re-blocked from its own origin (1 file) |
| **re-placed tiles** | A holds the same tile payloads as B at positions no single offset explains | a stitched copy that kept its tiles (33 files) |
| **trimmed pieces** | each tile of A is a sub-rectangle of some tile of B, each at its own offset | a fused stitched copy (2 files) |
| **stitched interiors** | the central 30% x 30% of 16 sampled tiles of the tiled B is found, byte for byte, in A | a stitched copy that blended the tiles (36 files) |
| **rendering** | rank correlation of the image planes (0.98 or more with a lower bit depth) | an 8-bit rendering of a 16-bit image (1 file) |

**Why tiles and not a composite image** (a worked number is in §4, example A): pasting the tiles of a crop's original into
one image gives a different image depending on the paste order wherever tiles overlap. The Kidney crop equals its original
exactly in the original's mosaic order and differs in 12.5% of its pixels, all of them in the tile overlaps, in reverse
order, although every tile is byte-exact. Comparing tiles has no such artefact.

**What it does not prove.** It proves that the pixels of A are in B. It says nothing about the metadata (annotation layers
such as the scale bar, display settings, the file name); those travel with the moved file, which is kept.

**The "original" of a group** is the member that no other member contains. Members that contain each other (identical
pixels) are one set, and its original is chosen by a fixed rule: not copy-like (no scale-bar overlay in the XML, no
`scale`/`escala` in the name), then a file with a project, then the earliest `CreationDate`, then the shorter name. A group
with several unrelated roots is a set of sibling scenes whose master file is not on the drive: each one is `distinct`
and stays in `/raw/`.

**Which pairs were read.** Pairs inside a group only, and only when cheap gates say a copy is possible: the candidate
copy's canvas is smaller (crops, ...), the pixel size is the same, and the two share a **stage position**
(`CenterPosition` of the scene, from the XML). The 49 groups (135 files, 150 GB) whose members all have different stage
positions were not compared by the expensive tests. Section 10 shows the gate holds.

---

## 3. What the 819 files are

| class | files | GB | groups | with a project | where it goes |
|---|---:|---:|---:|---:|---|
| original | 195 | 320.7 | 195 | 114 | stays |
| distinct (sibling scene, master not on the drive) | 153 | 157.8 | 54 | 0 | stays |
| ambiguous | 2 | 1.1 | 1 | 2 | stays, flagged (§5) |
| scale-bar copy | 17 | 0.7 | 16 | 1 | list a (3) / waiting (14) |
| identical re-save | 51 | 20.7 | 48 | 8 | list a2 (9) / waiting (42) |
| export: crop | 136 | 174.6 | 82 | 77 | list b (60) / list b2 (72) / waiting (4) |
| export: subset | 10 | 16.4 | 6 | 4 | list b2 (9) / waiting (1) |
| scene split | 182 | 11.6 | 6 | 0 | proposal (c) |
| stitched copy | 72 | 27.8 | 45 | 21 | proposal (c) |
| export: rendering | 1 | 0.0 | 1 | 0 | proposal (c) |
| **all** | **819** | **731.4** | **247** | **227** | |

"With a project" is the file's own project in the registry. The evidence for every member (the method and the result) is in
[`drives_r4_classification.csv`](drives_r4_classification.csv): one row per file, with the original, the relation and a
plain-language `evidence` string, plus ID65.

**By instrument:** `CELL` 170 originals, 152 distinct, 136 crops, 182 splits, 72 stitched copies, 25 re-saves, 17 scale-bar
copies, 10 subsets, 2 ambiguous; `LSM9` 19 originals, 20 re-saves, 1 distinct, 1 rendering; `XMIC` 6 originals, 6 re-saves.
The 26 `LSM9` / `XMIC` re-saves are tiny renamed duplicates (2 to 11 MB) and none has a project.

**What a class proves.** Scale-bar copies, re-saves, scene splits, subsets and crops are proved tile for tile or pixel for
pixel. Of the 72 stitched copies, 35 are proved tile for tile (33 kept the original's tiles and re-placed them, 2 are
trimmed pieces of them) and 1 is a crop of a stitched copy (exact against that copy); **36 are proved by sampled
interiors** (34 of them with 16 of 16 found, one 11 of 16, one 9 of 16). The rendering is proved by correlation only
(1.00) and is the one derivative that is not byte-exact.

---

## 4. Worked examples

### A. Kidney: a plain case, and why we compare tiles

Group `CELL|2023-06-02T07:11:34`, drive 2 `…\LP+IONP\Histologias`, project `0721`.

| file | size | what it is | evidence |
|---|---|---|---|
| `0721-M113-Kidney-PB-20X.czi` | 944 MB, 13,382 x 10,578 px, 110 tiles | **original** | contained in no other member |
| `Kidney-PB.czi` | 12.2 MB, 1,302 x 1,302 px, 4 tiles | crop | 4/4 tiles byte-exact sub-rectangles of the original's, one offset (5323, 3573) |
| `Kidney-PB-scale.czi` | 13.5 MB, 1,492 x 1,326 px | crop | 4/4 at (5335, 3426). **No scale-bar overlay, despite the name** |
| `prussian-blue-Kidney-scale.czi` | 13.5 MB | crop | the same region and offset; overlay present |
| `prussian-blue-Kidney-scale2.czi` | 6.3 MB | crop | 4/4 at (5605, 3642); overlay present |

The four crops go to list b (project `0721`). The original stays.
**The composite trap.** Pasting the original's 110 tiles into one image over the crop's area gives 0.00% differing pixels in
the original's mosaic order, and **12.50% in reverse order, 100% of them inside the tile overlaps** (the overlaps are
12% of the crop's area). Every tile of the crop is byte-exact either way. The Liver crops (example B) differ in 22.5%.
A composite comparison would have called a true crop unequal for a reason that has nothing to do with the data.

### B. Liver: the BACKLOG's own example

Group `CELL|2023-06-07T06:56:48`, project `0721`.

| file | size | class | evidence |
|---|---|---|---|
| `0721-M113-Liver-PB-20X-Original.czi` | 3,194 MB, 16,755 x 20,458 px, 330 tiles | **original** | |
| `0721-M113-Liver-PB-20X.czi` | 2,872 MB, 18,940 x 22,411 px, 99 tiles | **stitched copy** | 9 of 16 sampled tile interiors of the original found byte for byte in it |
| `Liver-PB-Scale.czi`, `Liver-PB.czi`, `prussian-blue-liver-scale.czi` | 15.1 MB each, 6 tiles | crops | 6/6 cut tiles of the original, one offset (5690, 8234). `Liver-PB-Scale` has **no** overlay |
| `prussian-blue-liver-scale2.czi` | 6.6 MB, 4 tiles | crop | 4/4 at (5960, 8450) |
| `Liver-scale-PB.czi` | 8.6 MB, 1 tile | crop **of the stitched copy** | 1/1 tile of `…-20X.czi` at (7469, 9560); that file is in turn the stitched copy of `-Original` |

The four crops of the original go to list b. The stitched copy (2.9 GB, linked in `0721` today) and `Liver-scale-PB.czi`
(a crop of it, so not byte-exact against the original) are in proposal (c). The BACKLOG's "two big files and five scale
copies" is one original, one stitched copy and five crops.

### C. `0219_ID39`: ROI crops, one of them re-blocked

Group `CELL|2023-03-24T12:04:11`, drive 1 `…\MARINA\PR REPETICIÓN\Grupo D`, project `0219`.

| file | size | class | evidence |
|---|---|---|---|
| `0219_ID39_PR_10x.czi` | 4,864 MB, 25,135 x 28,598 px, 156 tiles | **original** | |
| `0219_ID39_PR_10x_1.czi` | 2,191 MB, 21,222 x 15,259 px, 77 tiles | crop (ROI) | 77/77 tiles are byte-exact sub-rectangles, one offset (1,333, 11,428) |
| `0219_ID39_PR_10x_2.czi` | 823 MB, 12,864 x 10,658 px, 30 blocks | crop (ROI) | **no block is a piece of one original tile**, yet all of its pixels equal the original's at one offset (8,141, 2,132) |

`_2` was missed by every other test (it showed no relation to anything and was `distinct`). ZEN re-blocked it
from its own origin, so each of its 2,236-px blocks straddles several of the original's. The `region` test finds one
distinctive row segment of its blocks in the original's tiles, takes the offset, and then compares every pixel (100% equal
over 30 of 30 informative blocks). The `pol` twin of the group, `…_pol_2.czi`, is a cut-tile crop of its own original at
the **same** offset (8,141, 2,132), which corroborates it. Both crops are in list b2 (project `0219`). This is the only
member the `region` test moved.

### D. The LauraFM plate: scene splits and stitched copies, with no project

Group `CELL|2024-06-26T14:35:58`, drive 2 `…\CELL OBSERVER\Herida`, 30 files, **no project on any of them**.

- `LauraFM.czi` (4,333 MB, 14 scenes, 10,640 tiles = 14 x 760): the **original**.
- 14 scene splits (`Medio-sin-FBS-1.czi`, `x1.4-0.01ug-.czi`, ..., 4.28 GB): each file's 760 tiles are byte-identical to one
  scene of the master (760/760).
- 14 stitched copies (`…-Stitching-03.czi` etc., 4.19 GB): 13 hold the **same 760 tiles verbatim, re-placed**. Only 19 of
  the 760 stay where they were, so no single offset explains the file, but every tile payload is the scene file's. The
  14th, `MedioCompleto-Stitching-02.czi` (19 blocks), re-blended its tiles and is proved by sampled interiors (16 of 16).
- `MedioCompleto-Stitching-01.czi` (210 MB): related to nothing by bytes; kept as `distinct` and flagged (§5).

All 28 derivatives are proposal (c) **and** wait for a project. Six groups of this kind (the "Herida" and "ROS" plate
series, June and July 2024) hold 211 of the 294 derivatives that wait (§8).

### E. Names mislead, both ways

- `ROI-ID59_lung_PR_10x.czi` (2,488 MB): named "ROI" but 81/81 tiles are byte-identical to the whole
  `ID59_lung_PR_10x.czi` (project `1321`). An identical re-save, list a2.
- `ID68_lung_HE_10x-Change Scaling-01.czi` (3,643 MB): 120/120 tiles identical to `ID68_lung_HE_10x.czi`. The pixels are
  the same, so whatever "Change Scaling" did is in the metadata. List a2.
- `ID19_0219_alphasma_10x tiles.czi1.czi` (1,889 MB): 180/180 identical to `…tiles.czi`. Four such files in `0219` (7.6 GB).
- `Kidney-PB-scale.czi` has no scale bar; `Kidney-PB.czi` has one. 160 files carry the overlay and no "scale" in the name
  (many are multi-GB whole-slide scans the operator annotated).

### F. The one ambiguous pair

Group `CELL|2021-11-05T12:12:57`, project `0420`: `id15_normal.czi` and `id15_normal-Stitching-18.czi`, 552 MB and 20
tiles each. Both hold the **same 20 tile payloads at positions that differ by about a pixel** (7,767 x 9,733 and 7,768 x
9,733 px), so each is "contained" in the other and no offset explains it. The usual tie-break is how regular the tile
positions are (an acquisition's own grid is regular; a stitched file's tiles were each shifted). **Here both score 2.0:
every one of the 20 tiles sits at its own x and y in both files.** The evidence cannot say which is the acquisition's own,
so **both are `ambiguous` and both stay**. Both already have project `0420`.

---

## 5. Ambiguous and flagged members

| member | why it is flagged | what happens |
|---|---|---|
| `id15_normal.czi` (`ACQ-20211105-CELL-016`), `id15_normal-Stitching-18.czi` (`-015`) | the same tile payloads at positions that differ; the grids do not say which is the acquisition's own (example F) | both stay in `/raw/`, flagged; project `0420` |
| `8170 10x-1 tiles DEF.czi` (`ACQ-20230418-LSM9-053`), 3 MB | an 8-bit RGB **rendering** of `8170 10x-1 tiles.czi` (16-bit): same dimensions, rank correlation of the planes 1.00, not byte-equal | derived, but never byte-exact: proposal (c); no project |
| `prueba.czi` and `prueba2.czi` (`ACQ-20220324-CELL-001/-002`), 940 MB and 650 MB | the same stage position, pixel size and creation second, **no byte relation**. A low-resolution correlation of the two (aligned by FFT) is 0.20: different images | `distinct`, stay |
| `MedioCompleto-Stitching-01.czi` (`ACQ-20240626-CELL-010`), 210 MB | the same stage position as `MedioCompleto-Stitching-02` and the master scene, no byte relation; correlation with `-02` is 0.34 at half resolution | `distinct`, stay |

The `ID162_Hig1/Hig2` pairs also share a stage-position string, but only because both files carry the XML of the same
two-scene acquisition; they are two scenes of it whose master is not on the drive (correlation 0.12), exactly what
`distinct` means.

---

## 6. The retire lists

Row format (`tools/retire_acquisition.py --list`): `acq_id,disposition,target_acq_id,to_project,reason,subfolder,dest_name`.
`disposition` is `derivative`; `target_acq_id` is the original; `to_project` is **the original's project**; `reason` names
the class, the original and the pixel evidence; `subfolder` and `dest_name` are where the file lands (next subsection).

### Where each file lands: stream A's short-path rule (Ryan, 2026-10-04)

Ryan rejected long paths and zips. Stream A built one rule for every file from the drives
(`tools/drive_staging/historical_paths.py`, branch `feat/drives-nonraw-placement`) and has copied non-raw material into all
six target projects, so each has a frozen `_PATHMAP.csv` and an `_INDEX.csv`. `tools/drive_staging/r4_destinations.py` only
calls A's functions (A's worktree is imported read-only, without writing bytecode):

```
<project>\working\historical_drives\<FRIO-X6 | MFB-Disco-2>\<study folder>\<path below>\<file>
```

- **The study folder** is the outermost claim root of the file's project on its drive path (A's `row_root`, with A's "group
  under the parent" for session and animal folders in `0721`, `1019`, `1123`, `1321`). Everything above it is dropped; an archive
  becomes a folder `<stem>_<ext>`.
- **The budget** is 240 characters on `\\GJESUS3\gjesus3\`. Only where needed, the fewest folders are cut to 24 or 12
  characters plus `~` and 4 hex of a hash (for everything in the folder); a file name is cut only after the folders.
  **Frozen folders are never renamed, so a derivative lands in the same folder A used for the other files of its drive
  folder: for the 78 rows whose drive folder A has already placed, all 78 agree and 0 differ.**
- **Result for the 153:** longest 240 (238 in the `J:\gjesus3-data\` form), none over; 38 with a shortened folder (all in
  `1321`, below); no file name cut; all destinations unique (case-insensitive), none on the NAS yet and none in a tree's
  `_INDEX.csv`. **The five ROI paths that were 262 to 266 characters in the first layout are now 236 to 240.**
- **61 of the 153 have no claim of their project on their own path** (50 in `1321`, 11 in `0721`), so no study folder of
  their own. **The 11 in `0721`** sit in the very folder (`…\LP+IONP\Histologias`) that is the (promoted) study folder of
  two of their siblings, so all 13 `0721` files share `MFB-Disco-2\Histologias\…`. **The 50 in `1321`** have no study
  folder near them, so A's rule keeps their drive path, as the holding folder does; 38 of them had to be shortened
  (`MFB-Disco-2\2025-10-02 - Toshiba EXT~c41f\Proyectos_La~46dc\Lung-surfactant\…\Histologias-~21ee\alphaSMA\…`). That is
  the one choice left to Ryan (§11, Q11).
- **A weakness of A's `load_claim_roots`, worked around:** it keeps ONE project per claimed folder (the last), so a folder
  claimed by two projects (each from a file-name token) looks root-less to the other. The `0219` files of
  `PR REPETICIÓN\Grupo B` and `Grupo D` are such. `r4_destinations.py` keeps every project's claim and then calls A's
  `row_root` unchanged; those files land in the folders A already froze for them.
- **A weakness of A's planner for a derivative, worked around, and why it matters for the write window:** A renders a folder
  once per file that walks through it, and the last file wins in `_PATHMAP.csv`. A file with no study folder can sit in
  the folder that is another file's study folder (the `0721` case above), and then that folder is rendered two ways, and a
  re-plan after the folders are frozen **moves** files (found in the rehearsal below: 2 of 153). `plan_destinations`
  therefore (1) renders a folder that is the study folder of any file as a study folder for everything in it, and (2)
  re-plans with every decision frozen until nothing changes (a fixed point). **Re-planning after any of the index merges gives
  the 153 listed destinations again** (checked against the real trees and against the rehearsal's merged copy: 0 differ), and
  the index step freezes the folders of the whole plan at its first run. (A's own `Planner.load_index`, which pins files
  already placed and which A added at 11:16 on 2026-10-04 for the same kind of drift, is used too, so a re-plan after the
  merge returns each merged file's recorded path exactly.)

| list | rows | GB | originals | projects | links removed |
|---|---:|---:|---:|---|---:|
| `2026-10_r4_scalebars.csv` | 3 | 0.1 | 3 | `0721` 2, `1123` 1 | 1 |
| `2026-10_r4_resaves.csv` | 9 | 14.3 | 9 | `0219` 4, `1321` 2, `0420` 1, `1019` 1, `1123` 1 | 8 |
| `2026-10_r4_exports.csv` | 60 | 1.4 | 20 | `1321` 31, `1123` 18, `0721` 11 | 18 |
| `2026-10_r4_roi_crops.csv` | 81 | 184.3 | 64 | `1321` 57, `1123` 15, `0219` 8, `0420` 1 | 63 |
| **all** | **153** | **200.1** | 94 | `1321` 90, `1123` 35, `0721` 13, `0219` 12, `0420` 2, `1019` 1 | **90** |

**What `derivative` mode does** (`tasks/retire_acquisition_review.md`): hard-links the primary file into the original's
project folder, verifies it, removes the `/raw/` folder and the registry rows, writes a tombstone and a provenance event
(and a backup first), and **removes the derivative's own `raw_linked` link** where it has one. A list is all-or-nothing,
a dry run is the default, `--quick` compares sizes only, a full dry run hashes the file to be moved over SMB and checks it
against its `checksums.json`, and the tool refuses a closed project, a `/raw/` folder that holds anything besides the
primary and the sidecars, and a destination that exists and is a different file. The hard link is inside the NAS volume,
so nothing is copied.

**Checks before any dry run** (`r4_groups.py verify-lists`): every retiree and original is live in `registry_raw`; the
original's registry project is the row's `to_project` and is active; the retiree's own project is blank or the same; no
id is both a retiree and an original; and each acquisition's `checksums.json` SHA-256 equals the staged file's, so the pixel
check was made on the bytes that are in production. **153 rows, 306 SHA-256 matches, 0 problems.** It also **re-plans the
destinations against the NAS as it is now** and requires them to equal the lists, to fit 240, to be unique, free, and in the
folder A used (0 problems). Across the four lists the 153 ACQ-IDs are distinct, no retiree is another row's original (no
chain), and no two rows share a destination (case-insensitive).

**Dry runs** (2026-10-04, read-only, one list at a time, with the retire tool as it is on `main` at `7f5e8b5`, i.e. v2, which
is what will run; logs in `D:\projects\gjesus3\staging\_analysis\drives-r4-cleanup\dryruns\`):

| list | `--quick` | full |
|---|---|---|
| scalebars | 3 items with work, exit 0 (26 s) | 3 items with work, exit 0 (5 s) |
| resaves | 9 items with work, exit 0 (6 s) | 9 items with work, exit 0 (138 s) |
| exports | 60 items with work, exit 0 (22 s) | 60 items with work, exit 0 (52 s) |
| roi_crops | 81 items with work, exit 0 (38 s) | 81 items with work, exit 0 (1,693 s; 184 GB hashed) |

Each log has the same ACQ-IDs as its list, plans a hard link, a `/raw/` deletion and the registry rows for every item
(1 + 8 + 18 + 63 = 90 `raw_linked` links to remove), warns nothing, refuses nothing, and ends "nothing written". The
hard-link target in the tool's own text equals the list's project, subfolder and name for all 153. (The earlier runs, with
the first layout and with the v1 copy of the tool in this branch, are kept in `dryruns_layout1_2026-10-02\` and
`dryruns_tool_v1_layout2\`; they are superseded.) The lists' SHA-256 (first 16 hex): scalebars `8b969cc648f798c2`, resaves
`e3397b026f80fc45`, exports `4f558950ec680edd`, roi_crops `0f8d6521f719e733`.

**The side effects to know before the go:**

1. **90 `raw_linked` links go** (Ryan: they may). The 90 derivatives that have their own project (the same as the
   original's) are linked in that project's `raw_linked\` today; after the move they are under `working\historical_drives\…`.
2. **The destination trees are shared with stream A's non-raw placement.** A's frozen `_PATHMAP.csv` and `_INDEX.csv` were
   read, and no destination exists or is in an index. A's folder names are frozen only once A has published them: **run
   `verify-lists` right before each `--execute`** (it re-plans), and regenerate the lists if A has placed more material in
   between (a different name for the same folder would split it in two).
3. **Each affected project's `index.html` is regenerated** by the tool (the dry run lists it per project); the global
   Finder page is left to the 03:00 job, as in Step 3.
4. **The tool refuses `--execute` while `registry_raw.csv` is being written** (each dry run now prints a `WARN`: it changed
   minutes ago, an ingest may be mid-batch). That is the write-window rule; `--allow-recent-registry-writes` overrides it
   once the coordinator has confirmed no ingest is running.

**List a2 is the one that touches content most:** 9 identical re-saves (14.3 GB) whose bytes are **kept** (`derivative`
mode), not dropped. Retire v2's `equivalent` mode (stream E) is for a re-save whose pixels **and metadata XML** are
identical to the original's. The metadata of the 9 was compared with their originals' (read-only): **8 differ** in a few
lines (the `CreationDate`, display colours and ranges, an empty `<Layers />`; `ROI-ID59_lung_PR_10x.czi` records a
"Create Image Subset" operation), which are the researcher's own edits, so they are not `equivalent` and `derivative` is
the right mode. **One, `103-40x-2.czi` (project `1123`, 7.9 MB), has identical metadata XML to `102-40x-1.czi`:** the only
candidate for `equivalent` (Q2). The 3 scale-bar copies differ from their originals by the added scale-bar layer, as expected.

### The index step, after the retire run

Ryan's layout comes with an index so that nothing is lost: each project tree has an `_INDEX.csv` (new path, full original
path, size, SHA-256), a `_PATHMAP.csv` (every folder's original and rendered name) and an `_ORIGIN.txt` in each study folder.
A wrote them for what it copied; **the retired derivatives must be in them too.** `r4_groups.py index` merges them. It is a
dry run unless `--execute` (previews go to `D:\projects\gjesus3\staging\_analysis\drives-r4-cleanup\index_preview\`):

- **`_INDEX.csv`:** one row per retired derivative: the new path, the drive, the archive, the full original drive path, the
  size and SHA-256, `shortened`, and the note `retired derivative of <original ACQ-ID>, formerly <retired ACQ-ID>`. The 153
  rows are in [`drives_r4_index_rows.csv`](drives_r4_index_rows.csv). They are inserted in path order; **every existing row
  stays as it is, in its place** (checked on the previews: 0 changed, 0 moved).
- **`_PATHMAP.csv`:** the 32 new folders of the whole plan (`1321` 24, `0721` 5, `1123` 2, `1019` 1), so that their
  (shortened) names are frozen for A's later runs and for a re-plan. They are frozen at the first run, whichever list it
  merges, so that a later list cannot drift.
- **`_ORIGIN.txt`:** only for a new study folder that has something dropped above it (2: `1019`, and `0721`'s
  `Histologias`). A folder whose path here is its drive path says nothing, so it gets none.

| tree | `_INDEX.csv` rows now | new rows | `_PATHMAP.csv` rows now | new folders |
|---|---:|---:|---:|---:|
| `0219` | 61 | 12 | 14 | 0 |
| `0420` | 3,920 | 2 | 149 | 0 |
| `0721` | 2,872 | 13 | 257 | 5 |
| `1019` | 7,288 | 1 | 560 | 1 |
| `1123` | 278 | 35 | 37 | 2 |
| `1321` | 300 | 90 | 79 | 24 |

**Safety.** A's existing documents must re-serialise byte for byte before anything is merged (`0219` and `0420` were written
under A's earlier 9-column header, without `why`, so they are merged under their own header). A row whose path is already in
the index with other bytes is a conflict: nothing is written. `--execute` refuses unless every selected file is at its
destination with the expected size. It writes with A's `write_if_changed` (temp file, then replace) in A's format (UTF-8
with a BOM, CRLF) and re-reads every new row from the NAS. `--lists scalebars,resaves,exports,roi_crops` selects which rows
(default all), so it can follow each retire run. **If A re-publishes one of these trees it rewrites `_INDEX.csv` from its own
previews and would drop these rows, unless it passes them as `extra_index_rows`.**

**Rehearsal** (`tools/drive_staging/r4_index_rehearsal.py`, re-runnable in about a minute). `--execute` was run on a
**scratch copy** of the six trees (under `…\drives-r4-cleanup\rehearsal_nas\`, never production), with the destination files
created at their exact sizes, through `r4_groups.py --nas <scratch> index`: the dry run
(0 files present) and `--execute` both refuse while the files are missing; `--execute` on `scalebars` adds exactly their 3 rows
and leaves every row of A untouched, in order; a second run changes nothing (byte-identical); `exports` on top adds 60 more
(63 in all); a tampered row is a conflict and nothing is written; a missing file is refused; no temp file is left. The
rehearsal also found, and the fixed-point plan now prevents, a drift between the planned and the re-planned destinations of
2 files (§6).

**The order in the write window:** (1) `verify-lists`, (2) for each list `retire_acquisition.py --list … --execute` (after the
coordinator's checks), (3) `r4_groups.py index --execute`, (4) the verification listed in the plan's Step 5 item 3 (§13d).

---

## 7. Proposal (c): scene splits, stitched copies and the rendering (no list)

**255 files, 39.4 GB.** They are derivatives by the same principle, and the pixel check is done, so **the recommendation
is to retire them as derivatives**. They are not in any list because the brief makes them Ryan's call.

| class | files | GB | original has a project | evidence |
|---|---:|---:|---|---|
| scene split | 182 | 11.6 | 0 | tiles byte-identical to one scene of a multi-scene master (182/182 complete) |
| stitched copy | 72 | 27.8 | 22 (16.5 GB): `0420` 19, `0721` 3 | tiles kept verbatim and re-placed 33; trimmed pieces 2; sampled interiors 36; a crop of a stitched copy 1 |
| rendering | 1 | 0.0 | 0 | rank correlation 1.00, 8-bit rendering of a 16-bit image |

- **All 182 scene splits** are in 6 plate groups (the "Herida" and "ROS" series). **None has a project, and neither has
  the master.** They wait for the mapping round whichever way (c) is decided.
- **If Ryan approves (c) now, only the 22 stitched copies whose original has a project could be listed** (16.5 GB, `0420`
  and `0721`); the other 233 follow the mapping round. Writing that list is one line in `r4_groups.py lists` (a new entry
  in its `names` dict), done after the decision.
- **The weakest evidence in (c)** is the 36 stitched copies proved by sampled interiors, and the two at 11/16 and 9/16
  (`0721-M113-Liver-PB-20X.czi` is the 9/16). A tile interior found byte for byte cannot happen by chance, but those
  files are proved less completely than the 33 that kept their tiles.

---

## 8. The derivatives that wait for a project

**61 derivatives (12.3 GB) have an original with no project** (scale-bar copies 14, re-saves 42, crops 4, subset 1): the
retire tool needs a `to_project`, and `registry_raw.project_id` is write-once, so they wait for item 2b's mapping round and
are listed once it gives the original a project. **Including proposal (c), 81 groups hold 294 derivatives (35.2 GB) whose
original has no project.** [`drives_r4_waiting_groups.csv`](drives_r4_waiting_groups.csv) has one row per group (the
original, its folder, how many derivatives of what kind, and how many GB), as input to that round.

| where (the original's folder) | groups | derivatives | GB |
|---|---:|---:|---:|
| drive 2 `…\Toshiba EXT (Backup)\CELL OBSERVER` (the "Herida" / "ROS" plate series, 2024) | 31 | 238 | 19.5 |
| drive 1 `Former students\Zuriñe` (`LSM9`, tiny re-saves) | 19 | 21 | 0.2 |
| drive 2 `…\Proyectos_Laboratorio_Laura` (includes the 6 Charité `XMIC` re-saves) | 19 | 20 | 2.6 |
| drive 1 `Cell observer\AINHIZE` | 4 | 6 | 9.3 |
| drive 1 `Cell observer\Lucia-Lorena Garayoa` | 4 | 4 | 3.2 |
| drive 1 `Cell observer\Laura`, `\LYDIA` | 4 | 5 | 0.4 |

**Which to map first:** six groups (`LauraFM-02` 53 splits, `ROS` 52, `LauraFM` 28, `LauraFM-14` 28, `LauraFM-03` 26,
`LauraFM` of 2024-07-18 24) hold **211 of the 294**. They look like one family of experiments (plate series, June and July
2024); whoever knows them can map the six in one go.

---

## 9. `ID65_PB_lung_20x_scale.czi` is not a copy

The BACKLOG expected this 2.95 GB file to be a scale-bar copy to list by name. It is not:

- it is the **only record of its acquisition**: its timestamp (`2025-04-15T09:31:54`) is unique in the frozen plan and in
  production (one registry row, `ACQ-20250415-CELL-041`, under any instrument); no file called `ID65_PB_lung_20x.czi`
  exists on either drive or in production;
- it is a complete 90-tile scan (19,637 x 22,198 px) written at the end of the scan (`CreationDate` 14 minutes after the
  start), by the instrument's own `Jguser` account. The scale bar is an annotation in the XML
  (`Layers/Layer/Elements/ScaleBar`) on the only copy; the name records that the operator added it before saving. Next to
  it on the drive sits `ID65_PB_lung_20x_scale-Image Export-01.tif` (1.4 GB), an export of it.

Retiring it as a derivative would remove the acquisition's only record from `/raw/`. **It stays, unchanged, and is in no
list.** This deviates from the BACKLOG's expectation, on evidence. The same holds for every file with a scale bar in its
XML but no sibling to be a copy of: 189 files carry the overlay (188 group members and ID65), and only 29 have "scale" in
the name.

---

## 10. How far to trust it

- **Exactness.** Identical tiles, cut tiles, region, re-placed tiles and trimmed pieces are all exact equalities of every
  value compared (all files are uncompressed). Stitched interiors are sampled (§3). The rendering is correlation.
  Informative-tile guards stop blank (all-black) tiles from matching anything: a match needs content. **An independent
  check by another route:** the 9 smallest crops (11 relations, under 700 MB, with their originals under 4 GB), pasted into
  one image in the original's mosaic order, equal their originals' pixels with **0.00% differing pixels in all 11**.
- **The cache** (819 files): offsets and sizes are re-checked against the staged files (`check`: 819 checked, 0 bad).
- **The stage-position gate** skipped 49 groups (135 files, 150 GB). It was checked three ways: (1) the expensive tests
  were run **exhaustively** (every pair, no gate) on 14 of the 35 such groups up to 3.2 GB: 0 relations found; (2) the
  identical-tile test, which needs only the cache, was run on **all 348 ordered pairs of the 135 files**: 0 complete,
  0 partial, and **not one tile payload shared by two members of a group** (`classify` repeats this check on every run and
  stops, naming the group, if it ever finds a shared payload); (3) **every one of the 634 complete relations
  found shares a stage position** (0 exceptions), which is the property the gate relies on.
- **A bug found and fixed on the way:** the stage-centre list in `features.csv` was cut at 400 characters (10 files, 6 plate
  groups). All 6 groups were recomputed; the classification did not change.
- **Unit tests:** `tools/test_drives_r4_groups.py` (synthetic tiles written the way a `.czi` stores them: no `.czi`, no NAS,
  no D: needed) covers the byte search, every pixel test above, the classification (many scenarios, chains included), the
  original rule, and the list rows. All pass.
- **What it does not cover.** A derivative that is neither byte-exact nor a near-exact rendering (resampled, re-processed)
  would be `distinct`. The four same-position cases that looked like candidates were checked by correlation (0.12 to 0.34:
  different images, §5). Relations to files **outside the group** and to production were not searched (the production
  duplicate and re-save checks were done in close-out Step 1).

---

## 11. Questions for Ryan: asked 2026-10-02, answered 2026-10-04

None was a stakeholder sign-off: these are Data Office calls informed by what the data shows. Ryan's answers came through the
coordinator on 2026-10-04.

| # | Question (2026-10-02) | Recommendation | Decision (2026-10-04) |
|---|---|---|---|
| 1 | Where the file lands: its own drive folder or the original's? | its own folder | **Settled by stream A's rule:** the derivative lands under its own drive path, as a study-folder layout, in the folder A used for its neighbours (§6) |
| 2 | List a2, 9 identical re-saves (14.3 GB): move as derivatives now, or wait for retire v2's `equivalent`? | now (8 of 9 carry the researcher's own edits; only `103-40x-2.czi` qualifies for `equivalent`) | **Approved** (all four lists) |
| 3 | List b2, 81 ROI crops (184.3 GB): with the others? | approve with the rest | **Approved** |
| 4 | `ID65` stays in `/raw/` | confirm | **Stays** |
| 5 | Proposal (c), 255 files (39.4 GB) | retire as derivatives, 22 now, the rest after the mapping | **Waits, with no list** |
| 6 | The 90 `raw_linked` links removed | acceptable? | **They may go** |
| 7 | Which no-project groups to map first | the six "Herida" / "ROS" plate groups (211 of 294) | the 61 no-project derivatives **wait, with no list** |
| 8 | 5 destination paths past 259 characters | follow stream A's decision | **Solved:** 236 to 240 under the short-path rule |
| 9 | `prueba` / `prueba2`, `MedioCompleto-Stitching-01` stay `distinct` | information | none needed |
| 10 | The ambiguous `id15_normal` pair stays flagged | information | none needed |

**11. The one question left: the 50 `1321` files with no study folder near them.** A's rule gives them their drive path,
shortened where it must be (§6). That keeps everything and matches the holding folder, and the index records each one's
original path. (The 11 other files with no claim of their own, in `0721`, join their neighbours' study folder, so there
is nothing to ask.) The alternative for the 50 would be to file them under the study folder of their *original*
acquisition (a different drive folder from the derivative's own). **Recommendation: leave it as the rule gives it;** the 2b
mapping round can regroup later, because the index and `_PATHMAP.csv` say where everything was.

---

## 12. Files and how to reproduce

| what | where |
|---|---|
| the tool | `tools/drive_staging/r4_groups.py` (read-only on D: and production, except `index --execute`; writes only under `--out` and the lists it is told to) |
| the destinations | `tools/drive_staging/r4_destinations.py`: calls stream A's `historical_paths.py` and `nonraw_placement.py` read-only (found in A's worktree until A merges; `R4_STREAM_A_DIR` overrides) |
| its tests | `tools/test_drives_r4_groups.py` (`python tools/test_drives_r4_groups.py`; the destination tests are skipped, with a message, if A's modules are not found) |
| the index rehearsal | `tools/drive_staging/r4_index_rehearsal.py`: `index --execute` on a scratch copy of the six trees, with the refusals; run it again just before the window |
| classification of every file | `tasks/drives_r4_classification.csv` (819 rows + ID65; method and result per member) |
| groups waiting for a project | `tasks/drives_r4_waiting_groups.csv` (81 groups) |
| the four lists | `tasks/retire_lists/2026-10_r4_{scalebars,resaves,exports,roi_crops}.csv` |
| the index rows (153) | `tasks/drives_r4_index_rows.csv`: what the `index` step merges into each project's `_INDEX.csv` |
| working data (regenerable) | `D:\projects\gjesus3\staging\_analysis\drives-r4-cleanup\` (`members.csv`, `features.csv`, `pieces\`, `relations\`, `classified.csv`, `dryruns\`, `index_preview\`) |

```
python tools\drive_staging\r4_groups.py table         # members.csv: ACQ-ID, project, size, ... (819 rows)
python tools\drive_staging\r4_groups.py features      # XML features per member: scale-bar overlay, stage positions, ...
python tools\drive_staging\r4_groups.py pieces        # the tile cache: reads each staged file once (731 GB)
python tools\drive_staging\r4_groups.py check         # cache consistency
python tools\drive_staging\r4_groups.py relations     # pairwise tests per group (gated); the retile / restitch / retrim / region
                                                       # commands add each later test to relation files made before it existed
python tools\drive_staging\r4_groups.py validate      # the gate sample (exhaustive tests on gated-out groups)
python tools\drive_staging\r4_groups.py classify      # classified.csv
python tools\drive_staging\r4_groups.py lists         # the four lists + tasks\drives_r4_index_rows.csv; run BEFORE the retire run
python tools\drive_staging\r4_groups.py verify-lists  # against production, destinations re-planned (read-only)
python tools\drive_staging\r4_groups.py index         # AFTER the retire run: merge the index rows; a dry run unless --execute
python tools\drive_staging\r4_groups.py report        # the tables in this review, and waiting_groups.csv
```

A dry run of one list (never `--execute` without the coordinator's window and one writer on `J:`):

```
python tools\retire_acquisition.py --nas-root J:\gjesus3-data --list tasks\retire_lists\2026-10_r4_exports.csv --quick
python tools\retire_acquisition.py --nas-root J:\gjesus3-data --list tasks\retire_lists\2026-10_r4_exports.csv
```

---

## 13. Proposed wording for the records

*For the coordinator to apply. This stream did not edit `tasks/STATUS.md`, `CHANGELOG.md`, `tasks/BACKLOG.md` or
`tasks/historical_drives_closeout_plan.md`. Anchors are by heading or bullet text, because those files move.*

### 13a. `tasks/STATUS.md`

**Where:** §2 "Active / Up next", the bullet "Historical microscopy on external drives". Add this sub-bullet after
"**Six streams run over the weekend of 2026-10-03/04**", and add "the same-timestamp retirements (the four approved
lists) and their index step" to the "**Still open:**" bullet's list. Replace it with a done line once the lists have run.

```markdown
  - **🔶 Same-timestamp clean-up (gate rule R4), stream D: analysed 2026-10-02; all four lists approved by Ryan 2026-10-04 and dry-run clean; NOT yet executed (waiting for the write window).** Review: [`drives_r4_cleanup_review.md`](drives_r4_cleanup_review.md); the evidence per file is in `drives_r4_classification.csv`.
    - **Of the 819 files in 247 groups, 469 are derivatives (251.8 GB) and 350 stay in `/raw/`:** 195 originals, 153 sibling scenes whose master is not on the drive, 2 ambiguous. The 469: 17 scale-bar copies, 51 identical re-saves, 136 crops, 10 subsets, 182 scene splits, 72 stitched copies, 1 rendering.
    - **Four approved lists, 153 acquisitions, 200.1 GB, into six active projects** (`1321` 90, `1123` 35, `0721` 13, `0219` 12, `0420` 2, `1019` 1): `2026-10_r4_scalebars.csv` (3), `2026-10_r4_resaves.csv` (9), `2026-10_r4_exports.csv` (60), `2026-10_r4_roi_crops.csv` (81, 184 GB of ROI re-saves). Each passed `verify-lists` and a `--quick` and a full dry run against production. 90 `raw_linked` links go (Ryan: they may).
    - **Destinations follow stream A's short-path rule** (Ryan rejected long paths): `<project>\working\historical_drives\<FRIO-X6 | MFB-Disco-2>\<study folder>\<path below>`, at most 240 characters (the longest is 240), each file in the folder A already used for the others of its drive folder. After the retire run, `r4_groups.py index` merges one row per derivative into each project's `_INDEX.csv` and freezes the new folders in `_PATHMAP.csv`; it is prepared and dry-run.
    - **Waiting, with no list (Ryan):** 61 derivatives whose original has no project, and proposal (c): 182 scene splits, 72 stitched copies and 1 rendering (255 files, 39.4 GB). 81 groups hold 294 derivatives that need the project mapping (item 2b); six plate groups hold 211 of them.
    - **`ID65_PB_lung_20x_scale.czi` stays** (Ryan): it is the only record of its acquisition, not a copy.
```

### 13b. `CHANGELOG.md`

**Where:** a new row at the top of the table (newest first).

```markdown
| 2026-10-04 | R. Tasseff | **Historical drives: the four same-timestamp retire lists are approved and use the short-path layout; nothing is executed yet.** On 2026-10-02 the 247 same-timestamp groups (819 files, gate rule R4) were classified by tile-level pixel check (`tools/drive_staging/r4_groups.py`; every file is uncompressed, so the stored bytes are the pixels): 469 derivatives (251.8 GB) and 350 files that stay (195 originals, 153 sibling scenes whose master is not on the drive, 2 ambiguous), plus `ID65`. **On 2026-10-04 Ryan approved all four lists** (153 acquisitions, 200.1 GB: 3 scale-bar copies, 9 identical re-saves, 60 small exports, 81 ROI crops of 0.46 to 3.7 GB), confirmed that `ID65_PB_lung_20x_scale.czi` stays in `/raw/` (the only record of its acquisition, not a copy) and that the 90 `raw_linked` links may go, and put proposal (c) (255 scene splits, stitched copies and one rendering, 39.4 GB) and the 61 derivatives of originals with no project on hold, with no list. **He rejected long paths and zips,** so the lists were regenerated with stream A's shared rule (`tools/drive_staging/historical_paths.py`): `<project>\working\historical_drives\<FRIO-X6 \| MFB-Disco-2>\<study folder>\<path below>`, at most 240 characters on `\\GJESUS3\gjesus3\` (the five ROI paths that were over 259 are now 236 to 240), each derivative in the folder A already used for the other files of its drive folder (78 of 78 checked agree), and the plan is a fixed point (re-planning after the folders are frozen gives the same destinations). Every list passed `verify-lists` and a `--quick` and a full dry run against production, with the retire tool as it is on `main` (v2). **Prepared:** `r4_groups.py index` merges a row per retired derivative (original drive path, new path, SHA-256, "retired derivative of <original>, formerly <retired id>") into each project's `_INDEX.csv` and freezes the new folders in `_PATHMAP.csv`; it refuses to write until the files are at their destinations, is dry-run on all six trees (153 rows, 32 new folders), and was rehearsed with `--execute` on a scratch copy. **Corrections to the BACKLOG's estimates:** of 31 "scale" names only 13 are scale-bar copies; the "18 small exports" are 60; the "550 splits and stitched copies (320 GB)" are 254 (39.4 GB). Review: `tasks/drives_r4_cleanup_review.md`. |
```

### 13c. `tasks/BACKLOG.md`

**Where:** the item "Clean up the drives ingest's same-timestamp groups after the run (2026-10-01)". Keep Ryan's principle and the
"Original framing" paragraph as history. Replace the bullet "**Measured from the frozen plan (2026-10-01):**" and its
first four sub-bullets (31 scale names, ~18 small exports, ~550 splits and stitched copies, ID65 has no group) with the
block below, **keep the last sub-bullet** ("Out of `/raw/` already: the gate's R3 derivatives ..."), and change the item's
lead-in to the first line.

```markdown
- [ ] **Clean up the drives ingest's same-timestamp groups after the run (2026-10-01). 🔶 Analysed 2026-10-02 (stream D); the four lists are approved (Ryan, 2026-10-04) and dry-run; not yet executed.**
  - **Measured by pixel check 2026-10-02** (replaces "Measured from the frozen plan"; review `tasks/drives_r4_cleanup_review.md`, evidence per file in `tasks/drives_r4_classification.csv`): of 819 files in 247 groups, 195 originals, 153 sibling scenes (master not on the drive) and 2 ambiguous stay; **469 are derivatives (251.8 GB):** 17 scale-bar copies, 51 identical re-saves, 136 crops, 10 subsets, 182 scene splits, 72 stitched copies, 1 rendering.
  - **The estimates corrected:** of the 31 "scale" names (3.4 GB), 13 are scale-bar copies, 14 are crops, 2 scene splits, 1 a stitched copy, 1 an original (ID65). **60** crops are under 5% of their original (not ~18). **254** scene splits and stitched copies are **39.4 GB** (not ~550 / ~320 GB). 81 crops and subsets are ROI re-saves of 0.46 to 3.7 GB (184 GB).
  - **`ID65_PB_lung_20x_scale.czi` is not a copy:** it is the only record of its acquisition, so it stays in `/raw/` (Ryan confirmed).
  - **Retire lists, approved** (`tasks/retire_lists/2026-10_r4_*.csv`, 153 acquisitions, 200.1 GB): `scalebars` 3, `resaves` 9, `exports` 60, `roi_crops` 81. Each goes to the original's project under stream A's short-path layout (`<project>\working\historical_drives\<FRIO-X6 | MFB-Disco-2>\<study folder>\…`, at most 240 characters, in the folders A already uses). 90 `raw_linked` links go (Ryan: they may).
  - **Left to do:**
    - **The run:** in the coordinator's write window (one writer): `verify-lists` right before each `--execute` (it re-plans, and catches A having placed more material), then each list through `retire_acquisition.py`, then `r4_groups.py index --execute` (it merges a row per derivative into each project's `_INDEX.csv`, freezes the new folders in `_PATHMAP.csv`, and refuses until the files are at their destinations), then the checks listed in the close-out plan's Step 5 item 3.
    - **61 derivatives (12.3 GB) wait** for their original to get a project (item 2b); list them then. Six plate groups hold 211 of the 294 derivatives (including proposal (c)) that wait.
    - **Proposal (c)** (182 scene splits, 72 stitched copies, 1 rendering; 39.4 GB) is on hold (Ryan, 2026-10-04); the recommendation stands to retire them as derivatives. Only 22 stitched copies (16.5 GB) have an original with a project today.
    - **50 of the 153 files (all in `1321`) have no study folder near them,** so they keep their drive path, shortened where needed; the 2b mapping round can regroup them.
    - 🔸 LOW, after the retirements: the survivors' registry `notes` and sidecars still say "shares its acquisition timestamp with N other file(s)". Decide whether to leave them as provenance or correct them.
```

### 13d. `tasks/historical_drives_closeout_plan.md`

**Where:** (1) Step 5 item 3; (2) the "Open questions for Ryan" block of stream D, if the coordinator added one from the first
report: replace it with the "answered" line below; (3) in "Who may approve a production write", nothing changes: the
same-timestamp retirements are now approved by Ryan, so the coordinator may run them.

**(1) Replace Step 5 item 3** ("Clean up the same-timestamp groups") with:

```markdown
3. **Clean up the same-timestamp groups:** BACKLOG "Clean up the drives ingest's same-timestamp groups". **🔶 Analysed 2026-10-02 (stream D); the four lists approved by Ryan 2026-10-04 and dry-run clean; not yet executed.** Review: `tasks/drives_r4_cleanup_review.md` (branch `feat/drives-r4-cleanup`).
   - Of the 819 files in 247 groups, **469 are derivatives (251.8 GB)** and 350 stay in `/raw/`.
   - **The lists** (`tasks/retire_lists/2026-10_r4_*.csv`): `scalebars` 3, `resaves` 9, `exports` 60, `roi_crops` 81 (184 GB); 153 acquisitions, 200.1 GB. `subfolder` and `dest_name` come from stream A's short-path rule (`<project>\working\historical_drives\<FRIO-X6 | MFB-Disco-2>\<study folder>\…`, at most 240 characters, in the folders A already uses).
   - **The run, in the write window, one writer:** (a) `python tools/drive_staging/r4_groups.py verify-lists` right before each `--execute` (it re-plans the destinations against the NAS as it is now; if A has placed more material, regenerate the lists with `lists`); (b) each list through `retire_acquisition.py --list … --execute` after its `--quick` and full dry run; the tool refuses while `registry_raw.csv` was written in the last 15 minutes; (c) **then** `python tools/drive_staging/r4_groups.py index --execute` (`--lists` selects which): it merges one row per derivative into each project's `_INDEX.csv`, freezes the new folders of the whole plan in `_PATHMAP.csv`, writes the 2 new `_ORIGIN.txt`, and refuses unless every selected file is at its destination.
   - **Verify after each write:** the rows and `/raw/` folders are gone and the tombstones are appended (one per row); each destination file exists and its SHA-256 equals the staged drive copy's (`tasks/drives_ingest_provenance.csv`); the originals are untouched; the project `raw_linked` links are gone (90 across the four lists); `registry_raw` is down by the list's row count; the validator is at 10,314 errors with no new class; after the index step, every derivative has its row in the project's `_INDEX.csv` and no existing row changed.
   - **On hold (Ryan, 2026-10-04):** 61 derivatives wait for a project (item 2b); proposal (c), 255 files (39.4 GB), waits too. No list for either.
   - **`ID65_PB_lung_20x_scale.czi` has no group flag and is not a copy:** it is the only record of its acquisition, and stays.
```

**(2) Replace stream D's open questions** (if present) with:

```markdown
   - **Stream D's questions: answered 2026-10-04 (Ryan).** All four lists approved (153); `ID65` stays; the 90 `raw_linked` links may go; proposal (c) and the 61 no-project derivatives wait, with no list; destinations use stream A's short-path layout (the five over-259 paths are now at most 240). One small question is left, in the review's §11 (Q11): 50 `1321` files with no study folder near them keep their drive path; recommendation: leave it.
```
