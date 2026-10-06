# Drives catalog — findings (2026-09-29)

*Branch `feat/drives-catalog`. Produced by [`tools/drive_staging/catalog.py`](../tools/drive_staging/catalog.py) from the two staged drives; regenerable. Facts about **content** only — which project / animal / researcher a path claims is the parallel `feat/drives-project-codes` table; join on `(drive, relpath)`. Rules for the instrument fingerprint: [`tools/reference/microscopy_instruments.yaml`](../tools/reference/microscopy_instruments.yaml).*

## Summary

- **Reconciles exactly:** `files.csv` has **78,839** rows = both manifests, every `(drive, relpath)` once, **6,221,440,791,811 bytes** (the brief's "6,221.5 GB" is 3,776.4 + 2,445.1 rounded). **35 archives** read, **782,339** members catalogued.
- **Duplicates reproduce the hub's numbers:** 62,004 distinct contents / 5,011.1 GB; redundant **1,210.3 GB (19.5%)**, of which 1,041.2 GB is content present on *both* drives.
- **The instrument fingerprint holds on every `.czi`.** 11,293 non-preview `.czi`: **9,587 CELL, 716 ZWSI, 636 LSM9, 338 EXTERNAL:AxioImagerZ2**, 12 `czi-processed` (no hardware metadata at all), 4 unreadable. No fingerprint conflicts, no unknown cluster except those 12.
- **LSM-serial check: no other LSM exists.** All 636 files carrying stand key `LSM` carry serial `03761880`; none lack it. The LSM 800 onboarding stays void.
- **Genuinely new to gjesus3:** ≈ **3,932 GB CELL + 35 GB ZWSI + 5 GB LSM9** (+4.3 GB external). By sha256, 1,472 `.czi` copies plus 850 `.dcm` (2,322 files, 388 GB together) are already in production.
- **Production audit reproduces the 23 known `CELL`→`ZWSI` rows — and finds 2 more, both `LSM9`→`CELL`:** `ACQ-20240625-LSM9-001` and `-002` are Cell Observer files (`…\190624\48h\CS_fijadas_cell obs_1/2.czi`) that were ingested as LSM 900 because they sit in the LSM 900 folder. See "Surprising".
- **716 AxioScan 7 files sit in `CELL OBSERVER 2\` on drive 2** (`Marta` 488, `AINHIZE` 228, all acquired 2026). Folder names are not evidence of instrument.
- **All 880 loose `.dcm` carry a patient name** (Y/N flag only; 620 also a birth date). They are rodent MR/CT/PET; 850 are already in production. **`LEONE.zip` = 671,805 members, 671,410 of them DICOM: stream-hashed only, never extracted.**
- **Two archives cannot be fully read:** `Simu_2_V_XYZ.zip` (truncated at source, as expected) and four multi-volume RAR *part-2* files (unreadable alone). One RAR is password-protected.

## Reconciliation

| | D1 | D2 | total |
|---|---:|---:|---:|
| files (`files.csv` = manifest, last row per path) | 43,121 | 35,718 | **78,839** |
| bytes | 3,776.4 GB | 2,445.1 GB | 6,221.44 GB |

Archives: 35 read — **29 ok, 1 encrypted, 4 unreadable, 1 truncated**. Registry at the `production` pass: **16,437 rows** (the brief said 16,375; ingest has continued since — production moves under this catalog, so re-run `production` + `assemble` before the ingest session relies on `in_production`).

Error tally of every pass (all explained):

| pass | result |
|---|---|
| `production` | 0 errors: 16,437 `checksums.json` (431,128 hashes) and 3,514 microscopy `metadata.json` all read |
| `probe` | 11,293 `.czi`, 11,597 `.tif/.tiff/.lsm`, 880 `.dcm`: **12 flagged**. 3 `.czi` with no `ZISRAWFILE` header and 1 with no metadata segment (→ `czi-unreadable`; the one with no metadata segment is `Ekine\HE_10x_Brain\ID7B_0423_HE10x.czi`, 1.5 GB); 7 TIFF `IndexError` (tifffile logs "contains no pages") and 1 `TiffFileError` (bad tag 40100 offset); the TIFF rows keep their class, with `probe-error` in `flag` |
| `archives` | 29 ok · 4 unreadable · 1 truncated · 1 encrypted, see Archives |

## Class by drive (files, GB)

| class | D1 files | D1 GB | D2 files | D2 GB |
|---|---:|---:|---:|---:|
| czi-raw | 7,240 | 3,325.0 | 4,037 | 2,128.4 |
| czi-processed | 12 | 0.1 | 0 | 0 |
| czi-preview | 0 | 0 | 1 | 0 |
| czi-unreadable | 1 | 1.5 | 3 | 0.1 |
| lsm | 64 | 1.0 | 0 | 0 |
| tif | 3,266 | 130.1 | 8,262 | 172.0 |
| volume | 2,383 | 5.2 | 4,326 | 24.6 |
| bruker | 15,059 | 1.6 | 9,167 | 58.2 |
| em | 0 | 0 | 1,106 | 19.2 |
| nmr | 7 | 0 | 0 | 0 |
| analysis | 730 | 0.5 | 1,177 | 0.6 |
| figure | 4,629 | 8.0 | 3,722 | 20.3 |
| document | 2,459 | 2.8 | 786 | 8.4 |
| video | 9 | 0 | 55 | 0.9 |
| software | 2 | 0 | 952 | 2.6 |
| archive | 20 | 300.0 | 13 | 9.3 |
| system | 504 | 0 | 470 | 0.3 |
| other | 6,736 | 0.5 | 1,641 | 0.1 |

**Final rules** are the handoff's §5.3, first match wins, with these changes:

- **New class `bruker`:** extension-less ParaVision/TopSpin files (`fid`, `acqp`, `method`, `visu_pars`, `reco`, `procs`, `pulseprogram`, `spnam*`, …; a fixed name list). Otherwise 24,226 files would be `other`. `2dseq` stays `volume` as the brief said.
- **`volume` also takes** any extension-less file that starts with the `DICM` preamble (1,190 files are `2dseq`; LEONE's 671k members are DICOM found this way).
- **`analysis` extended** with `.mat .pzfx .fcs .sciprj .qpproj .itksnap .voistat .ipynb .job1 .refscan .rpt .rnk .gmt .cls .dts .jws`; **`document`** with `.ods`; **`software`** with `.dmg`.
- Everything left in `other` is generated/text output (`.xml` 1,733, `.par` 1,481, `.info` 1,478, `.html` 926, `.tsv` 901, `.temp`, `.output`, …) and rarer Bruker/TopSpin names (`acqu2`, `2rr`, …). Left as `other` deliberately.
- `czi-raw` also covers a file with `Experiment` but no hardware section (flag `experiment-only`; none occurred).
- **`personal-admin-heuristic`** matches whole word tokens (so `cv` does not fire inside `covid`).

## `.czi`: instrument by class

| class | instrument | files | GB | acq. years |
|---|---|---:|---:|---|
| czi-raw | CELL | 9,587 | 5,226.1 | 2020–2026 (2022: 1,050 · 2023: 3,433 · 2024: 3,878 · 2025: 1,175) |
| czi-raw | ZWSI | 716 | 209.9 | 2026 |
| czi-raw | LSM9 | 636 | 13.1 | 2023–2025 |
| czi-raw | EXTERNAL:AxioImagerZ2 | 338 | 4.3 | 2024 |
| czi-processed | unknown | 12 | 0.1 | (no date) |
| czi-unreadable | — | 4 | 1.6 | — |

- **Unknown fingerprints: exactly one cluster** — the 12 `czi-processed` files, which have *no* serials, *no* stand keys, *no* stand name, no `HardwareSetting`, no `Experiment`. Likely ZEN exports/re-saves. They sit under `Cell observer\Lucia-Lorena Garayoa` (5), `Former students\Lydia…` (2), and `Former students\Nicola\…Calcein+PI` (5). The ingest decides.
- **LSM-serial check:** serials on `LSM`-key files are `03761880` (×636, the instrument), plus **component serials that always ride along** (`22-12_150651_0312`, `22-12_150651_0348`, `7767-10-21-2109`, `7767-05-21-2034`, and the stand's `2902000209`). **No LSM-keyed file lacks `03761880`; no second LSM serial exists.**
- **External Axio Imager.Z2 (`784053`): 338 files**, all under `2025-10-02 - Toshiba EXT (Backup)\Proyectos_Laboratorio_Laura\Ferritas\Charité\`: `Fluorescence\4.10.24-test-1-FeMn` 170, `Fluorescence\Test-1` 120, `Fibronectin` 48; acquired **2024-09-27 to 2024-11-07** (`Test-1` September, `4.10.24-test-1-FeMn` October, `Fibronectin` November). *Corrected 2026-09-30 by the coordinator from the ingest plan's per-file dates; this line first said "to 2024-10-11", carried over from a sample.* None is in production.
- **What "an LSM 900" file looks like, so nobody re-derives it:** stand `Axio Observer.Z1 / 7` (same as CELL), stand keys `InvertedFixedStage`+`LSM`+`SampleFinder`, serial `03761880`. Loose LSM9: `Former students\Zuriñe` 364, `Cell observer\AINHIZE` 272.

**Loose `.czi` by folder tree (instrument by fingerprint):** D1 `Cell observer\` 6,582 CELL · 272 LSM9; D1 `Former students\` 364 LSM9 · 22 CELL; D2 `…Toshiba EXT (Backup)\` 2,325 CELL · 338 external; D2 `CELL OBSERVER 2\` **716 ZWSI** · 658 CELL.

**New vs already in production (distinct contents):**

| instrument | files | distinct | distinct GB | already in production | **new GB** |
|---|---:|---:|---:|---:|---:|
| CELL | 9,587 | 8,444 | 4,070.4 | 451 (138.2 GB) | **3,932.2** |
| ZWSI | 716 | 716 | 209.9 | 680 (175.3 GB) | **34.6** |
| LSM9 | 636 | 636 | 13.1 | 245 (7.9 GB) | **5.2** |
| EXTERNAL:AxioImagerZ2 | 338 | 338 | 4.3 | 0 | 4.3 |

## Duplicates (loose files, by sha256)

- Distinct content **62,004** files / 5,011.1 GB; redundant **1,210.3 GB = 19.5%** of the two drives (matches the hub's `assess_dupes.py`).
- Repeated on D1 only: 1,476 contents (70.5 GB redundant). On D2 only: 2,382 (98.6 GB). **On both drives: 1,010 contents (1,041.2 GB redundant)** — that is the drive-2 backup of drive-1 material.
- `dup_groups.csv`: **16,462 groups** over loose files *and* archive members, one row per location, **no canonical copy chosen**.
- 702 files are zero bytes (479 `bruker`, 195 `figure`, …), so they all share one sha256 and form one giant "duplicate" group; ignore that group when picking copies.

## Already in production

- **Files whose bytes are already in production: 2,322 (388.1 GB):** `czi-raw` 1,472 (ZWSI 680 · CELL 547 · LSM9 245) and `volume` 850 (all `.dcm`).
- By top folder: `D2:…Toshiba EXT (Backup)` 977, `D2:CELL OBSERVER 2` 770, `D1:Cell observer` 575.
- **Validation 1 — production audit** (registry instrument vs fingerprint, all 3,514 microscopy acquisitions, read from `metadata.json` only): 3,489 agree. **25 disagree: 23 `CELL`→`ZWSI` (the known set) and 2 `LSM9`→`CELL` (news)**, files listed in `production_instrument_audit.csv` (`agree = N`).
- **Validation 2 — drive fingerprint vs the production row holding the same bytes:** 1,472 compared; **2 disagree**, and they are the same two `LSM9`→`CELL` acquisitions (`validation_drive_vs_production.csv`). The 23 `CELL`→`ZWSI` rows do not appear because those bytes are not on the drives.
- **Archive members already in production: 3,950** — 3,919 in `Cardiac MRI.zip` (all match `MRI` acquisitions) and 31 in `Ferritas 1.zip` (all match `CT`). Their contents on the drives also exist as loose files (see below).

## Archives

35 archives; nested archives (recorded as members, not recursed): `LEONE.zip` 4, `Drive zuri 170823.zip` 8, `Cardiac MRI.zip` 1, `Manon.zip` 1.

| archive | status | members | size | notes |
|---|---|---:|---:|---|
| `Simu_2_V_XYZ.zip` (D1 root) | **truncated** | — | 97.0 GB | no central directory; not repaired, not listed |
| `LEONE.zip` | ok | 671,805 | 140.8 GB | 671,410 DICOM-magic, 348 other, 22 document; stream-hashed only. Only 1 member has a loose copy on the drives |
| `Cardiac MRI.zip` | ok | 65,738 | 94.5 GB | 38,736 volume + 19,378 bruker; **3,919 already in production, 2,444 also loose** |
| `Haizpea_2020-2022.7z` | ok | 19,048 | 72.1 GB | extracted to temp and deleted; 9,075 volume, 5,408 bruker, 1,237 tif, **82 `.czi` (CELL)**; 1,566 loose copies |
| `Drive zuri 170823.zip` | ok | 7,039 | 36.9 GB | **617 `.czi`: 364 LSM9 + 253 CELL** (confirms the brief's 617); 3,124 loose copies |
| `Drive Maria Jesus and Irati 20211209.zip` | ok | 15,264 | 14.3 GB | 343 loose copies |
| `Fotos confocales cdh5 jagged2.zip` | ok | 778 | 3.6 GB | **177 `.czi` (all LSM9)**; 766 loose copies |
| `Alizarin 10x.zip` | ok | 168 | 2.8 GB | 9 CELL + 1 `czi-processed`; all 168 loose |
| `Infartos Ruben_PR.zip` | ok | 6 | 2.5 GB | 6 `.czi` CELL |
| `PR-0721-Biod-May23.zip`, `Ferritas 1.zip`, `Manon.zip`, 14 small zips/7z | ok | | | almost all members also loose on the drives (except `Manon.zip`, 4 of 334) |
| `Datos-exportados-citometro-charité.zip` | ok | 96 | 0.1 GB | 95 `analysis`, **no loose copy** |
| 4 × multi-volume RAR **part 2** (`OriginPro_2018/2019b/2021/2022 …part2`) | **unreadable** | 1–7 each | ~1.0–1.7 GB | a part-2 volume cannot extract without its part 1 (`7z` "Data Error"); the listing is Origin installer software |
| 5 × RAR part-1 / SR0 / SR2 (OriginPro) | ok | 1–18 | | installers (`software`) |
| `OriginPro_2019b_Crack_Downloadly.ir.rar` | **encrypted** | 3 | | password-protected; `Crack` folder; all-software, so listed only |
| 2 × `ok.dll.zip` | ok | 0 | 22 B | empty |

Loose-copy counts are members whose sha256 also exists as a loose file; the raw imaging inside archives is mostly **also loose on the drives**, so the ingest can skip the archives except for what has *no* loose copy: `LEONE.zip`, most of `Cardiac MRI.zip`'s content that is not in production, `Haizpea_2020-2022.7z` (82 `.czi` + 17k others), the citometry zip and `Manon.zip`.

## DICOM and volume files (counts only)

- **880 `.dcm` loose**, all readable: **620 MR** (Bruker BioSpin), **254 CT** and **6 PT** (Molecubes); all rodent; study dates 2019-02-13 to 2024-10-21. **All 880 carry a patient name; 620 (the MR) also carry a birth date.** Only the presence flags are stored. 850 are already in production; 30 are not.
- `volume` class also holds 2,298 `.jcamp`, 2,214 `.nii.gz`, 1,190 `2dseq`, 127 `.nii`. None of those is in production.
- `LEONE.zip`: human clinical cardiac MRI, 671,410 DICOM members. **Member paths may contain identifiers — `archive_members.csv` on D: must not leave that disk unreviewed.** No DICOM field was read from members (only their sha256 and the `DICM` magic).

## Personal/admin heuristic hits (report-only)

78 files: `admin` 27, `factura(s)` 19, `cv` 15, `certificado(s)` 14, `contratos` 1, `nomina…` 1, `dni` 1. Top folders: `Former students\Piotr` 27, D2 `…Toshiba EXT\Congresos` 26, `…\Papeleo` 19. No contents inspected. 26 archive members also hit (`Drive zuri` 11, `Drive Maria Jesus and Irati` 10, `Haizpea` 5).

## Surprising, with evidence

1. **Two more mis-registered LSM9 rows.** `ACQ-20240625-LSM9-001/-002` have fingerprint `no serial, keys = {Inverted}, stand Axio Observer.Z1 / 7` (Cell Observer); the file names say "cell obs"; they came from `lsm900_bestguess_itziar-lipofectamine-mcherry.yaml`. Together with the 23 `CELL` rows that are AxioScan, production has **25 rows with the wrong instrument code**.
2. **Folder names mislead.** `CELL OBSERVER 2\Marta` and `\AINHIZE` hold 716 AxioScan files (2026); `Cell observer\AINHIZE\CONFOCAL LSM 900\` holds LSM 900 files; `Former students\Zuriñe` holds 364 LSM 900 files. Anything that maps folder → instrument is wrong.
3. **The fingerprint needs the union of all `<HardwareSetting>` elements.** The first one in document order is a preset inside `HardwareSettingsPool` with no `<Device>` children; a first-match `find()` returned no serials for real LSM 900 files (caught on the first sample, now covered by a test).
4. **All 880 loose DICOM carry a patient name** (animal names/IDs, since they are rodents) — worth remembering when the DICOM stream is ingested.

## For the coordinator

- **Nothing here needs a decision except:** (a) the 2 extra `LSM9` rows to fix alongside the 23 (Ryan/DataOffice — a production write); (b) what to do with 12 `czi-processed` and 4 unreadable `.czi`; (c) whether the 4 part-2 RAR volumes and the encrypted `…Crack….rar` matter (they are Origin installer software; I would drop them).
- **Not settled:** the *researcher's* confirmation that the Axio Imager.Z2 is Charité's; whether `czi-processed` files are worth ingesting; `Simu_2_V_XYZ.zip` content (97 GB, truncated; `7z` was not run against it here).
- **Caveats:** `in_production` is a snapshot of the registry at 2026-09-29 15:20 (16,437 rows) — re-run `python tools/drive_staging/catalog.py production` then `assemble` immediately before ingest. `dup_n` counts loose files only; `archive_copies` counts archive members separately. Loose files inside a folder that is *also* archived appear in both tables by design.
- **Outputs** (all regenerable, on the un-backed-up `D:`), in `D:\projects\gjesus3\staging\_analysis\catalog\`:
  `files.csv` (78,839) · `archives.csv` (35) · `archive_members.csv` (782,339) · `dup_groups.csv` (16,462 groups) · `production_hashes.csv` (431,128) · `production_instrument_audit.csv` (3,514) · `validation_drive_vs_production.csv` · `summary.md` · `stats.json` · `catalog.log` · caches `probe.jsonl`, `archive_members.jsonl`, `archives_done.jsonl`.
- Verification done: 78,839/78,839 keys reconcile; 20 random `.czi` rows re-derived by an independent regex over the raw XML (**20/20 match**); 5 random archive members re-hashed (**5/5 match**); production audit and validation 2 as above; unit tests `python tools/test_drive_catalog.py` pass.
- Not done, deliberately: no project/animal parsing, no ingest, no edits to `STATUS.md`/`CHANGELOG.md`.
