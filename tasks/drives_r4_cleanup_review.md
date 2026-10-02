# The drives' same-timestamp groups (gate rule R4): pixel check, classes, retire lists

**Status:** 🔶 analysis done 2026-10-02, **four retire lists written and dry-run, none executed.** Waiting for Ryan's go.
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

- **The four lists are 153 acquisitions, 200.1 GB, into six active projects** (`1321` 90, `1123` 35, `0721` 13, `0219` 12,
  `0420` 2, `1019` 1). **Nothing is deleted: a derivative is hard-linked into the original's project under
  `working\historical_drives\…`** and only then its ACQ-ID is retired (§6). Every list passed `verify-lists`
  against production (0 problems) and a `--quick` dry run (exit 0, nothing written).
  Every list also passed a **full** dry run (the file to be moved is hashed over SMB and checked against its
  `checksums.json`): 153 of 153 items with work, 0 already done, no warning, refusal or error; the ROI list took 28 minutes.
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
- **Ten questions for Ryan are in §11**, each with a recommendation. The ones that change what runs: where the file lands
  (Q1), whether the 184 GB ROI list goes with the others (Q3), proposal (c) (Q5), and 5 paths past 259 characters (Q8).

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
the class, the original and the pixel evidence; `subfolder` is
`working\historical_drives\<drive label>\<the file's own folder on the drive>` (labels `drive1_FRIO-X6`,
`drive2_MFB-Disco-2`; an archive member keeps the archive's own name as a folder); `dest_name` is the file's own name.

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
check was made on the bytes that are in production. **153 rows, 306 SHA-256 matches, 0 problems.** Across the four lists
the 153 ACQ-IDs are distinct, no retiree is another row's original (no chain), and no two rows share a destination
(case-insensitive).

**Dry runs** (read-only, logs in `D:\projects\gjesus3\staging\_analysis\drives-r4-cleanup\dryruns\`, one list at a time):

| list | `--quick` | full |
|---|---|---|
| scalebars | 3 items with work, exit 0 | 3 items with work, exit 0 (5 s) |
| resaves | 9 items with work, exit 0 | 9 items with work, exit 0 (133 s) |
| exports | 60 items with work, exit 0 | 60 items with work, exit 0 (33 s) |
| roi_crops | 81 items with work, exit 0 | 81 items with work, exit 0 (1,667 s; 184 GB hashed) |

No warning, refusal or error in any log. The lists' SHA-256 (first 16 hex): scalebars `e2b1b5748a681a82`, resaves
`a23430f7f0ec8071`, exports `2d9f6a6d92d6f947`, roi_crops `5d5b506313d4c534`.

**The side effects to know before the go:**

1. **90 `raw_linked` links go.** The 90 derivatives that have their own project (the same as the original's) are linked in
   that project's `raw_linked\` today; after the move they are under `working\historical_drives\…` instead. That follows
   the principle (they are not acquisitions), but it is a visible change in six projects.
2. **The destination subtree is shared with stream A's non-raw placement**, which writes
   `<project>\working\historical_drives\<drive label>\<folder>\` as well. The two write different files (a `.czi` raw
   member here, non-raw files there) and the retire tool refuses to overwrite, so no collision is expected; the
   coordinator may want to check when both are done.
3. **Each affected project's `index.html` is regenerated** by the tool (the dry run lists it per project); the global
   Finder page is left to the 03:00 job, as in Step 3.

**List a2 is the one that touches content most:** 9 identical re-saves (14.3 GB) whose bytes are **kept** (`derivative`
mode), not dropped. Retire v2's `equivalent` mode (stream E) is for a re-save whose pixels **and metadata XML** are
identical to the original's. The metadata of the 9 was compared with their originals' (read-only): **8 differ** in a few
lines (the `CreationDate`, display colours and ranges, an empty `<Layers />`; `ROI-ID59_lung_PR_10x.czi` records a
"Create Image Subset" operation), which are the researcher's own edits, so they are not `equivalent` and `derivative` is
the right mode. **One, `103-40x-2.czi` (project `1123`, 7.9 MB), has identical metadata XML to `102-40x-1.czi`:** the only
candidate for `equivalent` (Q2). The 3 scale-bar copies differ from their originals by the added scale-bar layer, as expected.

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

## 11. Questions for Ryan

Each has a recommendation. None blocks the others, and none is a stakeholder sign-off: these are Data Office calls
informed by what the data shows.

1. **Where the file lands: its own folder or the original's?** The lists use the **derivative's own folder on the drive**
   (`working\historical_drives\<label>\<its folder>`), assumed from "the original folder path" of the placement decision.
   They differ from the original's folder in 58 of 60 (list b), 52 of 81 (b2), 2 of 3 (a) and 1 of 9 (a2). **Recommendation:
   its own folder** (it shows where the file lived, and matches stream A's non-raw placement). A change to the original's
   folder is a one-line edit to `list_rows`.
2. **List a2 (9 identical re-saves, 14.3 GB): move as derivatives now, or wait for retire v2's `equivalent` mode?**
   **Recommendation: now,** as derivatives: nothing is dropped. Only 1 of the 9 (`103-40x-2.czi`, 7.9 MB) has metadata
   identical to its original's and so qualifies for `equivalent`; the other 8 carry the researcher's own display edits.
   Dropping the re-save's bytes would be a separate decision about content, not about placement.
3. **List b2 (81 ROI crops and subsets, 184.3 GB, 0.46 to 3.7 GB each, median 75% of the original's size) with the others,
   or on its own?** It is a separate file so it can be approved separately. **Recommendation: approve it with the rest.**
   They are derivatives under the principle, the hard link copies nothing, and they stay reachable under the project's
   `working\` folder. Know that 63 of them have a `raw_linked` link today that goes, and that these are substantial files
   a researcher may have worked from, not thumbnails.
4. **`ID65` stays in `/raw/`** (§9). A deviation from the BACKLOG; please confirm.
5. **Proposal (c): scene splits 182, stitched copies 72, rendering 1 (39.4 GB).** **Recommendation: retire as derivatives.**
   Only the 22 stitched copies with a project (16.5 GB) could be listed now; the rest follow the mapping round.
6. **The 90 `raw_linked` links** that the move removes (§6): acceptable?
7. **Which no-project groups to map first:** the six "Herida" / "ROS" plate groups of 2024 (211 of the 294 waiting
   derivatives, §8).
8. **Path length: 5 destination paths pass 259 characters** (262 to 266 on `J:\gjesus3-data\…`, 280 as UNC), all in list b2
   and in one folder (`…\Lung-surfactant\InVivos-Biodistribuciones_y_TT\Histologias-TT-Octubre23\alphaSMA\`, project `1321`):
   `ROI-ID76`, `Lobulo1-ID79`, `Lobulo2-ID79`, `ROI1-ID79`, `ROI2-ID79`. The retire tool uses long-path forms, so it can
   write them; Explorer and Office on the lab's machines may not open them. This is the same decision as stream A's
   path-length blocker. **Recommendation: follow whatever is decided for stream A.**
9. **`prueba`/`prueba2` and `MedioCompleto-Stitching-01`** stay `distinct` (§5). For information only.
10. **The ambiguous pair `id15_normal`** stays flagged (§5). A person who opens both in ZEN could settle it; nothing else can.

---

## 12. Files and how to reproduce

| what | where |
|---|---|
| the tool | `tools/drive_staging/r4_groups.py` (read-only on D: and production; writes only under `--out` and the lists it is told to) |
| its tests | `tools/test_drives_r4_groups.py` (`python tools/test_drives_r4_groups.py`) |
| classification of every file | `tasks/drives_r4_classification.csv` (819 rows + ID65; method and result per member) |
| groups waiting for a project | `tasks/drives_r4_waiting_groups.csv` (81 groups) |
| the four lists | `tasks/retire_lists/2026-10_r4_{scalebars,resaves,exports,roi_crops}.csv` |
| working data (regenerable) | `D:\projects\gjesus3\staging\_analysis\drives-r4-cleanup\` (`members.csv`, `features.csv`, `pieces\`, `relations\`, `classified.csv`, `dryruns\`) |

```
python tools\drive_staging\r4_groups.py table         # members.csv: ACQ-ID, project, size, ... (819 rows)
python tools\drive_staging\r4_groups.py features      # XML features per member: scale-bar overlay, stage positions, ...
python tools\drive_staging\r4_groups.py pieces        # the tile cache: reads each staged file once (731 GB)
python tools\drive_staging\r4_groups.py check         # cache consistency
python tools\drive_staging\r4_groups.py relations     # pairwise tests per group (gated); the retile / restitch / retrim / region
                                                       # commands add each later test to relation files made before it existed
python tools\drive_staging\r4_groups.py validate      # the gate sample (exhaustive tests on gated-out groups)
python tools\drive_staging\r4_groups.py classify      # classified.csv
python tools\drive_staging\r4_groups.py lists         # tasks\retire_lists\2026-10_r4_*.csv
python tools\drive_staging\r4_groups.py verify-lists  # against production (read-only)
python tools\drive_staging\r4_groups.py report        # the tables in this review, and waiting_groups.csv
```

A dry run of one list (never `--execute` without Ryan's go, the coordinator's window, and one writer on `J:`):

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
"**Six streams run over the weekend of 2026-10-03/04**", and add "the same-timestamp retirements (Ryan's go on the four
lists)" to the "**Still open:**" bullet's list.

```markdown
  - **🔶 Same-timestamp clean-up (gate rule R4), stream D, 2026-10-02: analysed by pixel check, four retire lists written and dry-run, nothing executed. Waiting for Ryan's go.** Review: [`drives_r4_cleanup_review.md`](drives_r4_cleanup_review.md); the evidence per file is in `drives_r4_classification.csv`.
    - **Of the 819 files in 247 groups, 469 are derivatives (251.8 GB) and 350 stay in `/raw/`:** 195 originals, 153 sibling scenes whose master is not on the drive, 2 ambiguous. The 469: 17 scale-bar copies, 51 identical re-saves, 136 crops, 10 subsets, 182 scene splits, 72 stitched copies, 1 rendering.
    - **Four lists, 153 acquisitions, 200.1 GB, into six active projects** (`1321` 90, `1123` 35, `0721` 13, `0219` 12, `0420` 2, `1019` 1): `2026-10_r4_scalebars.csv` (3), `2026-10_r4_resaves.csv` (9), `2026-10_r4_exports.csv` (60, under 5% of the original), `2026-10_r4_roi_crops.csv` (81, 184 GB of ROI re-saves, a separate decision). Each passed `verify-lists` and a full dry run. 90 `raw_linked` links would go.
    - **Waiting:** 61 more derivatives (12.3 GB) whose original has no project; proposal (c), 255 files (182 scene splits, 72 stitched copies, 1 rendering, 39.4 GB), is Ryan's call. 81 groups hold 294 derivatives that need the project mapping (item 2b); six plate groups hold 211 of them.
    - **`ID65_PB_lung_20x_scale.czi` stays:** it is the only record of its acquisition, not a copy (a deviation from the BACKLOG).
```

### 13b. `CHANGELOG.md`

**Where:** a new row at the top of the table (newest first).

```markdown
| 2026-10-02 | R. Tasseff | **Historical drives: the 247 same-timestamp groups (819 files, gate rule R4) are classified by pixel check; four retire lists are written and dry-run, none executed.** Every file is uncompressed, so the stored tile bytes are the pixels: each file's tiles were cached once (`tools/drive_staging/r4_groups.py`) and every pair inside a group was related by exact tests (identical tiles, cut tiles, region, re-placed or trimmed tiles, sampled stitched interiors), after a stage-position gate that was validated three ways with 0 false negatives. **Result:** 469 derivatives (251.8 GB) and 350 files that stay (195 originals, 153 sibling scenes whose master is not on the drive, 2 ambiguous), plus `ID65`. **Four lists, 153 acquisitions, 200.1 GB:** 3 scale-bar copies, 9 identical re-saves, 60 small exports and 81 ROI crops of 0.46 to 3.7 GB, each to its original's project under `working\historical_drives\<drive>\<folder>`, with 90 `raw_linked` links to be removed. Every list passed `verify-lists` against production and a full dry run. **Not listed:** 61 derivatives whose original has no project, and 255 scene splits, stitched copies and one rendering (Ryan's call, 39.4 GB). **Corrections to the BACKLOG's estimates:** `ID65_PB_lung_20x_scale.czi` is the only record of its acquisition, not a copy, and stays; of 31 "scale" names only 13 are scale-bar copies; the "18 small exports" are 60, and the "550 splits and stitched copies (320 GB)" are 254 (39.4 GB). A composite-image comparison was rejected: it depends on the paste order in the tile overlaps. Review: `tasks/drives_r4_cleanup_review.md`. |
```

### 13c. `tasks/BACKLOG.md`

**Where:** the item "Clean up the drives ingest's same-timestamp groups after the run (2026-10-01)". Keep Ryan's principle and the
"Original framing" paragraph as history. Replace the bullet "**Measured from the frozen plan (2026-10-01):**" and its
first four sub-bullets (31 scale names, ~18 small exports, ~550 splits and stitched copies, ID65 has no group) with the
block below, **keep the last sub-bullet** ("Out of `/raw/` already: the gate's R3 derivatives ..."), and change the item's
lead-in to the first line.

```markdown
- [ ] **Clean up the drives ingest's same-timestamp groups after the run (2026-10-01). 🔶 Analysed and listed 2026-10-02 (stream D); the retirements wait for Ryan's go.**
  - **Measured by pixel check 2026-10-02** (replaces "Measured from the frozen plan"; review `tasks/drives_r4_cleanup_review.md`, evidence per file in `tasks/drives_r4_classification.csv`): of 819 files in 247 groups, 195 originals, 153 sibling scenes (master not on the drive) and 2 ambiguous stay; **469 are derivatives (251.8 GB):** 17 scale-bar copies, 51 identical re-saves, 136 crops, 10 subsets, 182 scene splits, 72 stitched copies, 1 rendering.
  - **The estimates corrected:** of the 31 "scale" names (3.4 GB), 13 are scale-bar copies, 14 are crops, 2 scene splits, 1 a stitched copy, 1 an original (ID65). **60** crops are under 5% of their original (not ~18). **254** scene splits and stitched copies are **39.4 GB** (not ~550 / ~320 GB). 81 crops and subsets are ROI re-saves of 0.46 to 3.7 GB (184 GB).
  - **`ID65_PB_lung_20x_scale.czi` is not a copy:** it is the only record of its acquisition, so it stays in `/raw/`.
  - **Retire lists written** (`tasks/retire_lists/2026-10_r4_*.csv`, 153 acquisitions, 200.1 GB, each to the original's project under `working\historical_drives\<drive>\<the file's own folder>`): `scalebars` 3, `resaves` 9, `exports` 60, `roi_crops` 81. Each passed `verify-lists` and a full dry run; **none executed.** 90 `raw_linked` links would be removed.
  - **Left to do:**
    - Ryan's go on each list (the ROI list on its own, if he prefers), then the run: one writer, the coordinator's window, a verification after each.
    - **61 derivatives (12.3 GB) wait** for their original to get a project (item 2b); list them then. Six plate groups hold 211 of the 294 derivatives (including proposal (c)) that wait.
    - **Proposal (c)** (182 scene splits, 72 stitched copies, 1 rendering; 39.4 GB) is Ryan's decision; the recommendation is to retire them as derivatives. Only 22 stitched copies (16.5 GB) have an original with a project today.
    - **5 destination paths pass 259 characters** (all in one `alphaSMA` folder of `1321`): decide with stream A's path-length blocker.
    - 🔸 LOW, after the retirements: the survivors' registry `notes` and sidecars still say "shares its acquisition timestamp with N other file(s)". Decide whether to leave them as provenance or correct them.
```

### 13d. `tasks/historical_drives_closeout_plan.md`

**Where:** (1) Step 5 item 3; (2) a new item at the end of "Open questions for Ryan"; (3) in the weekend table, row D, nothing changes.

**(1) Replace Step 5 item 3** ("Clean up the same-timestamp groups") with:

```markdown
3. **Clean up the same-timestamp groups:** BACKLOG "Clean up the drives ingest's same-timestamp groups". **🔶 Analysed 2026-10-02 (stream D); four lists dry-run, none executed.** Review: `tasks/drives_r4_cleanup_review.md` (branch `feat/drives-r4-cleanup`).
   - Of the 819 files in 247 groups, **469 are derivatives (251.8 GB)** and 350 stay in `/raw/`.
   - **The lists** (`tasks/retire_lists/2026-10_r4_*.csv`): `scalebars` 3, `resaves` 9, `exports` 60, `roi_crops` 81 (184 GB); 153 acquisitions, 200.1 GB. `subfolder` is `working\historical_drives\<drive>\<the file's own folder>`. **For each:** `--quick`, then a full dry run, then Ryan's go, then `--execute`, then verify. The ROI list can be approved on its own.
   - **Verify after each write:** the rows and `/raw/` folders are gone and the tombstones are appended (one per row); each destination file exists and its SHA-256 equals the staged drive copy's (`tasks/drives_ingest_provenance.csv`); the originals are untouched; the project `raw_linked` links are gone (90 across the four lists); `registry_raw` is down by the list's row count; the validator is at 10,314 errors with no new class.
   - **Not done:** 61 derivatives wait for a project (item 2b); proposal (c), 255 files (39.4 GB), is Ryan's call.
   - **`ID65_PB_lung_20x_scale.czi` has no group flag and is not a copy:** it is the only record of its acquisition, and stays.
```

**(2) Add to "Open questions for Ryan"** (the newest go last):

```markdown
7. **Stream D's questions** (the same-timestamp clean-up; review `tasks/drives_r4_cleanup_review.md` §11 on `feat/drives-r4-cleanup`). Each has a recommendation.
   - **Q1:** the lists put each derivative under its **own** drive folder, `working\historical_drives\<drive>\<its folder>`; it differs from the original's folder in most rows. **Its own folder.**
   - **Q2:** the 9 identical re-saves (14.3 GB): move as derivatives now, or wait for retire v2's `equivalent` mode? **Now:** nothing is dropped.
   - **Q3:** the 81 ROI crops (184 GB, median 75% of the original's size) are a separate list. **Approve with the rest.** 63 of them lose a `raw_linked` link.
   - **Q4:** `ID65` stays in `/raw/`. **Confirm** (a deviation from the BACKLOG).
   - **Q5:** proposal (c), 255 files (39.4 GB). **Retire as derivatives;** 22 can go now, the rest after the mapping.
   - **Q6:** the 90 `raw_linked` links removed. **Acceptable?**
   - **Q7:** map first the six "Herida" / "ROS" plate groups of 2024 (211 of the 294 waiting derivatives).
   - **Q8:** 5 destination paths pass 259 characters (one `alphaSMA` folder, `1321`). **Follow stream A's path-length decision.**
   - **Q9, Q10:** `prueba`/`prueba2`, `MedioCompleto-Stitching-01` (distinct) and the `id15_normal` pair (ambiguous) stay. For information.
```
