# Review: the July protocol-1125 MRI sessions and the five `jrc` phantom studies, ingested from the scanner (branch `feat/mri-july-1125`)

**Date:** 2026-10-04 · **Stream F, second task** (the first was [`mri_0710_reingest_review.md`](mri_0710_reingest_review.md)) ·
**Status:** ✅ **done and verified in production, 2026-10-04.** **210 acquisitions are in** (the nine sessions = 141, the five
phantom studies = 69), written in the coordinator's window 12:52 to 13:33; every check in §6 is clean (0 failed, 0 exceptions) and the
validator's baseline did not move. The read-only phase (§§1 to 5), the coordinator's six answers (§8) and the dress rehearsal came
first. **Open housekeeping:** my seven rehearsal roots under `D:\projects\gjesus3\scratch_mri-july-1125_rehearsal\` (about 800 MB) are
not deleted, because the permission system denied the delete command; I did not retry or work around it. The pulls stay until the
coordinator releases them.

**Scope (Ryan's go, 2026-10-04, relayed by the coordinator).** The Data Office ingests, from the scanner, **9 unregistered
protocol-1125 sessions** (operator `Irene`) and **5 `jrc` phantom/QC studies** (blank project). **Not** the 5
protocol-1025 sessions of 10-01/02: the operators ingest those normally.
**Ryan's line of 2026-10-04:** gjesus3 registers MRI only as reconstructed images. An exam with no reconstructed image of
any kind (spectroscopy, calibration) is not registered.

Evidence (all regenerable): `D:\projects\gjesus3\staging\_analysis\mri-july-1125\`. The pulls: `D:\projects\gjesus3\scratch_mri-july-1125\`.

---

## 1. The dry-run lines, one per study

Sessions: `mri_ingest.py <study> --nas-root J:\gjesus3-data --operator Irene --model 7T --no-prompt --dry-run`, from Windows,
against production. Every exam says `ACQ_station` = `Biospec 70/30`, so `7T` is right. Each table lists exactly the exam
folders on disk and nothing else; the six non-exam siblings (`AdjResult`, `AdjStatePerStudy`, `NIFTI`, `ResultState`,
`ScanProgram.scanProgram`, `subject`) are listed as skipped, so the silent skip (STATUS §0 D3) is not hit. No ID is dated
today, no link name repeats within a study, 0 per-case warnings. **The preview ignores `.acq_id_seq.json`** (it shows
`-001…`); the real IDs below continue the counters, and are exact per exam in `predicted_ids_<label>.csv`.

| Study | Exams on the scanner = listed | DICOM | Project | **Real IDs** | Note |
|---|---|---|---|---|---|
| **m2** `20260703_114524_…` | 15 = 15 (exams 2–16) | native ×15 | `PROJ-0021` | `ACQ-20260703-MRI-017…031` | |
| **m3** `20260703_124547_…` | 16 = 16 (1–16) | native ×16 | `PROJ-0021` | `ACQ-20260703-MRI-032…047` | another group's study nested inside (§7) |
| **m4** `20260706_084340_…` | 14 = 14 (1–14) | native ×14 | `PROJ-0021` | `ACQ-20260706-MRI-031…044` | |
| **m5** `20260706_095523_…` | 14 = 14 (1–14) | native ×14 | `PROJ-0021` | `ACQ-20260706-MRI-045…058` | |
| **m6** `20260706_111010_…` | 15 = 15 (1–5, 7–16) | native ×15 | `PROJ-0021` | `ACQ-20260706-MRI-059…073` | NAS staging copies identical (§3) |
| **m7** `20260706_120902_…` | 16 = 16 (3–18) | native ×16 | `PROJ-0021` | `ACQ-20260706-MRI-074…089` | |
| **m8** `20260706_140324_…` | 16 = 16 (1–16) | native ×16 | `PROJ-0021` | `ACQ-20260706-MRI-090…105` | |
| **m19** `20260710_090835_…` | 18 = 18 (7–9, 15, 19–32) | native ×18 | `PROJ-0021` | `ACQ-20260710-MRI-035…052` | |
| **m12, first study** `20260710_114705_…` | 17 = 17 (1–17) | native ×17 | `PROJ-0021` | `ACQ-20260710-MRI-053…069` | **needs its own link names (§2.1)** |

Phantoms: five scoped configs (§5), previewed with the operator-core `preview_batch` and dry-run from WSL
(`ingest_raw.py --config tools/configs/mri_july_1125/<file> --nas-root /mnt/gjesus3/gjesus3-data --dry-run`), all against
production. `sample_type` by stream B's B07 rule (**`phantom` for four, `material` for `jrc260611.SPION`**, §2.2), blank
project, `researcher` and `operator` `NA` (stored blank, as for G1), 7T.

| Study | Exam folders → listed | DICOM | **Real IDs** | Note |
|---|---|---|---|---|
| `jrc260611.SPION` `20260611_190513_…` | 5 → 5 | **none**: regenerated at ingest | `ACQ-20260611-MRI-001…005` | `sample_type` **material** (§2.2) |
| `jrc-260612_phantom_SPION_RGD` `20260612_141006_…` | 7 → 7 | **none**: regenerated at ingest | `ACQ-20260612-MRI-001…007` | |
| `jrc260708_phantom` `20260708_184152_…` | 42 → **41** (+1 excluded) | native ×41 | `ACQ-20260708-MRI-001…033` and `ACQ-20260709-MRI-001…008` | the run crosses midnight; **exam 66 excluded** (§2.3) |
| `jrc260709-phantom` `20260709_151028_…` | 10 → 10 | native ×10 | `ACQ-20260709-MRI-009…018` | after the 07-08 study's eight 07-09 IDs |
| `jrc260818_Phantom_MnACC` `20260818_112746_…` | 6 → 6 | **none**: regenerated at ingest | `ACQ-20260818-MRI-001…006` | |

**Totals: 210 acquisitions (141 + 69), 3,659 DICOM files, 238 MB; 18 exams regenerated.** Order matters for the IDs: m19
before m12's first study (09:08 before 11:47), and the 07-08 phantom before the 07-09 one.

**Spectroscopy and calibration exams (addendum): none.** All 211 exams are imaging methods: IgFLASH 104, FLASH 50,
FcFLASH 37, MSME 10, UTE 4, RAREVTR 3, B1Map 2, RARE 1. **One exam has no reconstructed image of any kind** (exam 66 of the
07-08 phantom, §2.3) and is excluded. The scanner keeps it.

## 2. The findings behind the decisions (all decided by the coordinator, 2026-10-04)

### 2.1 The first m12 study collides with the `_bis` session's project links, and the hazard is old

The shared link name is `MRI_<sample>_<date>_<exam>_<recons>`. The first m12 study and the `_bis` session already in
`PROJ-0021` are the **same animal, the same day**, with overlapping exam numbers. **9 of the first study's 17 names are
identical to links that exist in production now** (exams 2, 3, 4, 5, 7, 8, 9, 10, 11). The other 132 predicted names, across
all nine sessions, are clear (checked against the live `raw_linked`).

`linker.create_hardlink` does `os.makedirs(dest, exist_ok=True)` and then links only files that do not exist yet. A second
acquisition with the same name therefore **silently ends up with the first one's files** while the registry and provenance say
otherwise. Reproduced on a scratch copy that holds production's `_bis` state (its 17 raw folders and 17 link folders):

| Path | Link folders with wrong or missing content | `_bis` link folders polluted |
|---|---|---|
| standard operator CLI | **9 of 17**: eight hold only `_bis` files, one is a mix | **1 of 17** (gained the first study's files) |
| scoped config, `link_filename` + `_study1147` | **0 of 17** | 0 of 17 |

**Decided (coordinator, 2026-10-04): yes.** It prevents the silent merge into the `_bis` links. This one study runs through
`tools/configs/mri_july_1125/mri_m12_first_irene.yaml`. It is the operator template
with the same overrides the CLI applies (`--operator Irene --model 7T`), written out, with **one deliberate change**: the link
name gets the suffix `_study1147` (the study's start time), and one precaution (`auto_create_projects: false`). Compared with
the CLI path on the same input, every registry column and sidecar field is identical except `ingest_config`,
`registration_datetime` and `generated`. The shared template is not touched.

**The hazard is not new.** On 44 animal-days that have more than one ParaVision study (483 acquisitions), **209 have no link
folder of their own (43.3%)**, against 2.65% (260 of 9,796) on single-study animal-days, where researcher deletions are the
only explanation. By project: `AE-biomaGUNE-0721` 153 of 294, `-1022` 53 of 179, `-0219` 3 of 10. One animal-day has 96
acquisitions from 6 studies and 21 link folders. At file level, for `PROJ-0017`, `m23_0219`, 2022-01-24: 10 acquisitions, 7
link folders, and only 5 of the 10 acquisitions have any file in any of them. **`/raw/` and the registry are intact; the damage
is the project links, which researchers browse.** (Provenance cannot show it: its append is idempotent on `output_path`, so a
second acquisition on a shared path leaves no row.) **The coordinator takes this to Ryan**; the BACKLOG HIGH item and the
evidence paths are in §9. **No repair is proposed or attempted here.**

### 2.2 Phantom `sample_type`: stream B's B07 rule (decided)

**Decided (coordinator, 2026-10-04): follow stream B's rule, so the precedent is consistent.** `phantom` for an imaging test
object (named or built as a phantom); `material` for a bare sample of a material under study (06_REGISTRIES §2.4). Applied:

| Study | `sample_type` |
|---|---|
| `jrc260611.SPION` | **`material`**: a bare nanoparticle sample (its name does not say phantom), scanned with the same protocol as the next day's study |
| `jrc-260612_phantom_SPION_RGD` | `phantom` |
| `jrc260708_phantom`, `jrc260709-phantom` | `phantom` |
| `jrc260818_Phantom_MnACC` | `phantom` |

(I had first used `phantom` for all five as asked, and flagged the one case; the five configs now carry the rule in their
headers, and their `notes` say "material sample" or "phantom sample", as B07's do.) **No `phantom` or `material` row exists in
production yet, so these ingests and stream B's B07 set the precedent together, and they agree.**

### 2.3 Exam 66 of the 07-08 phantom is excluded

`66` ("MSME TR 20 TE 2.2 ms") started and never produced data: it has `acqp`, `method` and `configscan`, and `pdata/1` holds only
`id`, `methreco`, `reco`. There is no `fid`, no `2dseq`, no `visu_pars` and no `ACQ_time`. **It has no reconstructed image, and
no acquisition date, so the ingest would register it with today's date** (`ACQ-20261004-MRI-…`), the soft fallback stream B hit
on its B06 setup scans. The config carries an allow-list case table (`cases_mri_phantom_0708.csv`, 41 rows) with
`on_missing: skip`; the exclusion is recorded in `excluded_mri_phantom_0708.csv`. It was the only such exam in the 14 studies.
**Decided (coordinator, 2026-10-04): excluded**, the same as stream B's never-acquired exclusions.

## 3. The pulls

14 studies from `kenia:/opt/PV-7.0.0/data/nmr`, to `D:\projects\gjesus3\scratch_mri-july-1125\<study>`, with
`tools/ftp_mirror.py` (download only). **8,423 files, 6.57 GB. Every file verified against the scanner by size and mtime (0
differ, 0 extra), and a SHA-256 manifest per study** in `manifests\<study>.csv`. All 14 still exist on the scanner with the exam
counts of the 10-02 reconciliation.

| | files | MB | | files | MB |
|---|---:|---:|---|---:|---:|
| m2 | 701 | 626.5 | `jrc260611.SPION` | 120 | 72.6 |
| m3 | 1,048 | 1,104.4 | `jrc-260612_phantom_SPION_RGD` | 156 | 75.2 |
| m4 | 649 | 569.4 | `jrc260708_phantom` | 858 | 14.9 |
| m5 | 650 | 570.1 | `jrc260709-phantom` | 235 | 5.5 |
| m6 | 706 | 626.3 | `jrc260818_Phantom_MnACC` | 128 | 57.2 |
| m7 | 757 | 683.6 | | | |
| m8 | 761 | 683.3 | | | |
| m19 | 837 | 741.3 | | | |
| m12 first | 817 | 740.6 | | | |

**m6 against the NAS staging copies** (`sftp_20260716_112028` and `_122729`, never touched): 706 files each. **681 are
byte-identical**; the 25 that differ are all `NIFTI\*.nii.gz` (gzip carries a timestamp), the same result as on 10-02. Every
exam file, DICOM and `2dseq` is identical, so the NAS copies would have served as a source; the fresh pull is used for all 14
so that there is one source.

## 4. The sessions

- **DICOM:** all 141 exams have native Bruker DICOMs in every reconstruction, so **nothing needs regenerating**. Recon sets:
  `1` (5 or 6 exams per session: localizers and planning), `1,3` (the cines).
- **Dates:** every exam has an exam-level `visu_pars` with `VisuCreationDate`; the date matches its study day. 0 exams without.
- **Subjects:** all 141 resolved from the animal-facility DB in the rehearsal (`animal-facility-db`, none `pending-db`).
  Seven of the nine sessions have a DB `MRI 7T` entry on the study date; m19 and m12's first study (both 07-10) do not (for m12
  the DB logs Organ sampling and Perfusion that day instead).
- **Operator:** `Irene`, per Ryan. ParaVision records only the shared login `nmr` for every exam.
- **Rehearsal** (a real committed ingest, all nine in order, into a scratch root holding a byte-exact registry snapshot and
  the project's `provenance.csv`; `GJESUS3_ROOT` pointed at scratch): **141 / 141, 0 failed; 3,150 DICOM files; IDs exactly as
  predicted for every exam; fields, `checksums.json` == disk, SHA-256 == the pull manifests; 141 / 141 link folders by file
  identity; counters `…0703` 16 → 47, `…0706` 30 → 105, `…0710` 34 → 69; `registry_raw` and `ingest_manifest` append-only (+141
  CRLF lines each), every other registry file byte-identical.** (m12's first study ran through its scoped config in a second
  scratch root; §2.1.)

## 5. The phantoms

**Why scoped configs.** A phantom's study name carries no `m<animal>_<protocol>`, so the shared regex parses nothing and the
study would be dropped with no error and no worklist row (D3). The shared regex is **not** relaxed. Each phantom has its own
config (`tools/configs/mri_july_1125/mri_phantom_<study>.yaml`), scoped by a study-specific `pattern`, and, like stream B's B07,
takes its identity from ParaVision's own `SUBJECT_id`, so **no filename regex is needed at all**.

- `sample_id` = `session_id` = the `SUBJECT_id`, verbatim: `jrc260611.SPION`, `jrc-260612_phantom_SPION_RGD`,
  `jrc260708_phantom`, `jrc260709-phantom`, `jrc260818_Phantom_MnACC` (one has a `.`, two have `-`). **Decided (coordinator,
  2026-10-04): keep the typed `SUBJECT_id`; we record what the scanner says and never normalise it.**
- `sample_type`: `material` for `jrc260611.SPION`, `phantom` for the other four (§2.2).
- `project_name` blank, `auto_create_projects: false`, `subject_from_db: false` (no animal), `researcher` and `operator` `NA`
  (**nothing in the data names an operator**: `ACQ_operator`, `OWNER` and `SUBJECT_referral` are `nmr`, remarks empty),
  `instrument_model` derived (`Biospec 70/30` → 7T).
- `staging_dir` is in **WSL form** in the repo files, because they run from WSL. The registry's `ingest_config` column then
  records `tools/configs/mri_july_1125/<file>` (checked: the WSL dry run prints exactly that). A first rehearsal with a temp copy
  recorded a meaningless `../../../tmp/…` path, which is why the repo file is run itself.

**Route for the 18 exams with no DICOM (addendum, b): regenerate at ingest, in WSL with Dicomifier.**
- *Why:* a blank project means no hard links, so the WSL hard-link limit over CIFS does not matter. Regeneration at ingest
  leaves **no empty placeholder, no worklist row, and no later in-place fill of an immutable `/raw/` folder.**
- *Rehearsed:* 5 / 5, 7 / 7 and 6 / 6 regenerated (`source ~/miniforge3/etc/profile.d/conda.sh` then `conda activate
  dicomifier-pilot`, Dicomifier 2.5.3). **Every regenerated exam has as many DICOMs as its frame count** (3, 1, 128 for
  multi-echo MSME, 12 for variable-TR RARE), with no warning.
- *If one fails in the real run:* it would fall back to a placeholder and a worklist row. The same-window backfill from the same
  pull (the B04b procedure) closes it, so nothing is left for later.
- The sessions go the other way: **Windows**, because their native DICOMs need no regeneration and their links, DB lookups and
  registry writes are all done in one pass there.

**Rehearsal** (the five configs from WSL, chronological, into a scratch root on D:): **69 / 69, 0 failed; 509 DICOM files (51
native, 18 regenerated); IDs equal to the oracle per exam; `sample_type` `material` ×5 and `phantom` ×64, no project, `researcher`
blank, no today-dated row; counters `…0611` 0 → 5, `…0612` 0 → 7, `…0708` 0 → 33, `…0709` 0 → 18, `…0818` 0 → 6; `registry_raw` and `ingest_manifest`
append-only (+69 each); the worklist, subjects, projects and tombstones byte-identical; no link, no `pending_links.csv`.**

## 6. The production write: result, and the order and checks it followed

**Production result (2026-10-04, window 12:52 to 13:33): 210 / 210 written and verified, 0 failed checks anywhere.**

| Step | Result |
|---|---|
| Full preflight, 12:52:54 | **PASS.** No lock; registry quiet (last write 11:16:13, 95 minutes before; 26,450 rows, stream B's included); counters 16 / 30 / 34 and 0 for the five phantom prefixes; none of the 141 link names in `raw_linked`; no unregistered MRI folder; 8,423 pulled files at manifest size, 3,527 DICOM and `2dseq` files re-hashed, 0 differ |
| Backup, 12:53:03 | `C:\Users\rtasseff\temp\gjesus3_registry_backup_20261004_1253_mri_july_1125`: 11 files (the registries, `.acq_id_seq.json`, PROJ-0021's `_project.yaml` and `provenance.csv`), SHA-256 verified, 0 mismatches |
| Sessions, Windows, 12:53 to 12:58 | m2 15, m3 16, m4 14, m5 14, m6 15, m7 16, m8 16, m19 18, m12 first study 17 (scoped config): **141 / 141, `Failed: 0` in every step**, 27 to 46 s each |
| Phantoms, WSL + Dicomifier, 12:58 to 13:29 | 0611 5 / 5 (5 regenerated), 0612 7 / 7 (7), 0708 41 / 41, 0709 10 / 10, 0818 6 / 6 (6): **69 / 69, 18 regenerated at ingest, none fell back**, no warning, no worklist row. **31 minutes** (§7) |
| `verify_sessions` | 141 / 141: rows and fields, DICOM counts, `checksums.json` == disk, every DICOM's SHA-256 in the pull manifest, **141 / 141 link folders by file identity**, subjects from the animal DB; 3,150 files hashed; 0 failed, 0 exceptions |
| `verify_phantoms` | 69 / 69 (51 native, 18 regenerated), 509 files hashed; `sample_type` `material` ×5 and `phantom` ×64, blank project, `researcher` and `operator` blank, `ingest_config` the repo config path, no placeholder, no today-dated id, regenerated DICOMs are new bytes; 0 failed, 0 exceptions |
| `check_counters` | exactly the eight predicted changes (`…0703` 16 → 47, `…0706` 30 → 105, `…0710` 34 → 69, `…0611` 0 → 5, `…0612` 0 → 7, `…0708` 0 → 33, `…0709` 0 → 18, `…0818` 0 → 6); 896 → 901 keys; nothing else moved |
| `check_link_owners` (by inode) | 34 m12 link folders = 17 `_bis` (unpolluted, no suffix) + 17 first-study (`_study1147`), each owned by exactly one acquisition and holding all its files |
| Append-only | `registry_raw` +100,453 bytes and `ingest_manifest` +27,069 bytes, **210 lines each, all CRLF, none bare-LF** (the same byte counts as the dress rehearsal); the other six registry CSVs byte-identical; `provenance.csv` an exact prefix, 318 → 459 rows (+141); `_project.yaml` identical |
| `check_raw_vs_registry` | registry 26,450 → 26,660 rows; the 210 new ids are exactly the predicted set; 603 MRI folders on disk in 2026-06 to 08, none without a row, none missing; no `pending_links.csv`; `pending_dicom_regen.csv` byte-identical (nothing queued) |
| `generate_index --project PROJ-0021` | only the project's `index.html` rewritten (456,375 → 643,959 bytes); the global `registries\index.html` untouched (last rebuilt 03:00 today, outside this repo; it will list the 210 at its next rebuild) |
| Validator `--no-enrichment` | 26,660 rows, **10,314 errors, all the `operator` placeholder** (the unchanged baseline), 0 warnings, none on our 210 ids; no new class |

Evidence: `preflight_window.txt`, `backup_prod_manifest_stdout.txt`, `prod_sessions_run.txt`, `prod_phantoms_run.txt` and the per-step
`prod_*.log`, `verify_prod_*.txt`, `check_*_prod.txt`, `append_only_check_prod.txt`, `generate_index_prod.txt`,
`validator_production_after_write.txt`, all in `D:\projects\gjesus3\staging\_analysis\mri-july-1125\`.

The plan it followed, with the dress rehearsal that preceded it:

**Dress rehearsal of the write itself (2026-10-04, 10:14 to 10:22, scratch only).** The scratch root held production's registry
snapshot of that minute (25,925 rows, stream B's rows included), PROJ-0021's `provenance.csv` and `_project.yaml`, and the 17 `_bis` raw
and link folders. The two write drivers then ran exactly as they will in production: `write_sessions.py` (Windows: the eight sessions
through `mri_ingest.py`, then the first m12 study through its scoped config, stopping at the first step that is not clean) and
`write_phantoms_wsl.sh` (WSL + Dicomifier: the five configs, stopping at the first one whose exit code, `DONE` count, regenerated
count or `Failed:` line differs). Both refuse a live root unless given `--go-production`. **Result: 210 / 210, 0 failed checks.**
`verify_sessions.py` and `verify_phantoms.py` both clean on the cumulative root; `registry_raw` and `ingest_manifest` +210 lines each,
all CRLF, none bare-LF, though Windows wrote 141 and WSL wrote 69; `provenance.csv` an exact prefix plus 141 lines, `_project.yaml`
identical; **all eight counter changes exactly as predicted and no other key** (`check_counters.py`); **34 m12 link folders, 17 `_bis`
(no suffix) and 17 first-study (`_study1147`), each owned by exactly one acquisition and holding all its files**
(`check_link_owners.py`, by device and inode; on the earlier standard-CLI reproduction the same check finds 16 of 17 `_bis` folders
intact, one polluted, as the audit did); the validator names none of the 141 session ids; `generate_index.py --project PROJ-0021`
writes only that project's `index.html` (1 s) and lists all 141. Mixed Windows and WSL writers on one registry therefore leave no
line-ending or counter anomaly. Output: `dress_*.txt`, `verify_dress_*.txt`, `check_*_dress.txt`.

**Production baseline, read-only, 10:19:** the validator (`--no-enrichment`) reports **10,314 errors, all the `operator` placeholder**
(25,925 rows, stream B's and A's writes included): the baseline did not move.

1. **Preflight** (`prod_preflight_july.py`, read-only; passed 09:42, and at 10:14 in `--quick` mode with one expected red, "registry
   written 0.6 minutes ago", because stream B was writing; counters, link names and unregistered folders unchanged; **rerun in full at
   12:52 inside the window: PASS**): no lock, registry quiet; counters at 16 / 30 / 34 and
   0 for the five phantom prefixes; none of the 14 studies registered; `PROJ-0021` active; **none of the 141 link names exists
   in `raw_linked`**; no unregistered MRI folder on disk; all 8,423 pulled files at their manifest size and all 3,527 DICOM and
   `2dseq` files re-hashed. **Rerun immediately before the write** (counters, link names, unregistered folders and "registry quiet"
   are all re-read).
2. **Backup** to a fresh dated folder under `C:\Users\rtasseff\temp\` (registries, `.acq_id_seq.json`, `PROJ-0021`'s
   `_project.yaml` and `provenance.csv`), SHA-256-verified.
3. **Sessions, Windows,** in this order, via `write_sessions.py --nas-root J:\gjesus3-data --go-production`, which runs from the repo root
   `python tools\operator\mri_ingest.py "D:\projects\gjesus3\scratch_mri-july-1125\<study>" --nas-root J:\gjesus3-data --operator Irene --model 7T --no-prompt --go`
   for m2, m3, m4, m5, m6, m7, m8, m19; **then**
   `python tools\ingest_raw.py --config tools\configs\mri_july_1125\mri_m12_first_irene.yaml --nas-root J:\gjesus3-data`.
4. **Phantoms, WSL,** in this order, via `write_phantoms_wsl.sh /mnt/gjesus3/gjesus3-data <log dir> prod --go-production`: `mri_phantom_0611_spion`,
   `_0612_spion_rgd`, `_0708_phantom`, `_0709_phantom`, `_0818_mnacc`. For each it does
   `source ~/miniforge3/etc/profile.d/conda.sh && conda activate dicomifier-pilot`, then from the repo root
   `python tools/ingest_raw.py --config tools/configs/mri_july_1125/<file> --nas-root /mnt/gjesus3/gjesus3-data`.
   (Writing to the live share from WSL has precedent: the 2026-07-16 regeneration backfill and today's B04b regeneration.)
5. **Verify:** `verify_sessions.py` (rows == the predicted exam → ID map, fields, DICOM counts, `checksums.json` == disk,
   SHA-256 == manifests, link identity, DB subjects, counters, append-only registries) and `verify_phantoms.py` (same, plus
   sample_type, no project, no placeholder, regenerated counts), `check_counters.py` (the eight counter changes and nothing else),
   `check_link_owners.py` (the 34 m12 link folders, 17 + 17, one owner each), `append_only_check.py` (`registry_raw` +210; its only
   "problem" is `.acq_id_seq.json`, which is a counter file and is meant to change), all against the backup. Then
   `generate_index.py --project PROJ-0021`, and the validator (expect the same 10,314 errors, one class, none on our ids).

## 7. Surprises recorded

- **m12's first study and the `_bis` session are two real, distinct acquisitions.** Zero of 29 `2dseq` files and zero of 393
  DICOMs are shared; the exam times do not overlap (first study 11:58–12:55, `_bis` 13:19–14:33); it is the same full cardiac
  protocol (localizer, axial, 4-chamber, long axis, cine 4-chamber, cine slices) repeated on the same animal. The DB logs
  Organ sampling and Perfusion for animal 12 on that day, and no MRI. **Both studies get the same `session_id`**
  (`jrc20260710_m12_1125`: the shared regex drops `_bis`); `original_name` keeps them apart.
- **m3's folder holds another group's whole study:** `20260707_094320_jl260707_1225_m26_…` (13 exams, 274 files, 358 MB, protocol
  1225, started 2026-07-07 09:43), **nested inside it, and not present anywhere else on the scanner.** The `<study>/*` scope lists
  it as a skipped non-scan folder and does not descend, so nothing of it is ingested. **Decided (coordinator, 2026-10-04): not
  ours, not ingested; the coordinator passes it to Ryan as an FYI for the `jl` group.**
- **A live write from WSL is about 20 times slower than a scratch one.** The five phantom configs took 84 s on D: scratch and
  **31 minutes** on the live share: the WSL-to-SMB path costs roughly 2 s per small file (the 128-file multi-echo exam alone took
  over 3 min), so the writes took 36 minutes (5 for the sessions, 31 for the phantoms) where the whole scratch rehearsal had taken 3.
  The Windows sessions took 5 minutes for 141. Nothing failed; plan the window by the file count, and note that the 51 native-DICOM phantom exams
  (0708, 0709) could have been written from Windows as well, which was not rehearsed and so not used.
- **The 07-08 phantom crosses midnight** (18:51 → 08:29), so its IDs span two date prefixes.
- **`researcher: "NA"` is stored blank**, in the registry and the sidecar (as for G1); `modalities_in_study` comes out `MR`.
- **`NIFTI\` folders** sit in 13 of the 14 studies (all but the 08-18 phantom; the researchers' own conversions) and are skipped as
  non-scan siblings, as decided on 10-02. The 07-09 phantom also has a `Mapshim` folder; skipped the same way.

## 8. Decisions (all answered by the coordinator, 2026-10-04) and what is open

1. **The `_study1147` suffix for m12's first study: yes** (§2.1). Recorded.
2. **`sample_type` follows stream B's rule: `jrc260611.SPION` = `material`, the other four `phantom`** (§2.2). Recorded in the configs.
3. **Exam 66 (never acquired): excluded** (§2.3).
4. **Phantom sample ids keep the typed `SUBJECT_id`; never normalised** (§5).
5. **The nested `jl` study in m3 is not ours:** passed to Ryan as an FYI; not ingested (§7).
6. **The window:** granted by the coordinator after stream B's B03 → B02 ingest into `1519`, used 12:52 to 13:33 (41 minutes
   including the preflight, the backup, the verification and the index), exactly per §6.

**Open, for Ryan (the coordinator carries it):** the production link-collision hazard, and whether and how to repair the 209
acquisitions that have no link folder of their own (§2.1, §9). It is not part of this write.

**Open, housekeeping:** (1) the seven rehearsal roots under `D:\projects\gjesus3\scratch_mri-july-1125_rehearsal\` (`dress_S`,
`dress_S_before`, `nas_C_cli`, `nas_C_yaml`, `nas_P`, `nas_P_before`, `nas_S`; about 800 MB) were to be deleted after verification, but
the permission system denied the command, so they stay until someone with the authority removes them or grants it; (2) the pulls in
`D:\projects\gjesus3\scratch_mri-july-1125\` (6.2 GB) stay until the coordinator confirms; (3) the backup folder above stays.

## 9. Proposed wording for STATUS, CHANGELOG, BACKLOG and the plan

*Filled in after the writes (2026-10-04). I have not touched these four files; the coordinator applies them.*

### `tasks/BACKLOG.md`

> ## 🔺 HIGH — a second acquisition with an existing link name silently gets the first one's files (2026-10-04)
> Found while previewing the first m12 study of 2026-07-10. `linker.create_hardlink` (folder primary) does `os.makedirs(dest,
> exist_ok=True)` and links only files that do not exist yet, so two acquisitions with the same link name (same animal, same
> day, same exam number and recons) end up sharing one link folder: the second gets none of its own files, or a mix. The
> standard MRI link name `MRI_<sample>_<date>_<exam>_<recons>` has no per-study part. **It has already happened:** on 44
> multi-study animal-days (483 acquisitions) **209 have no link folder of their own (43.3%, against 2.65% on single-study
> days)**: `AE-biomaGUNE-0721` 153 of 294, `-1022` 53 of 179, `-0219` 3 of 10. `/raw/` and the registry are intact. Provenance
> cannot show it (idempotent on `output_path`). **Evidence:** `tasks/mri_july_1125_review.md` §2.1; the scripts and their output in
> `D:\projects\gjesus3\staging\_analysis\mri-july-1125\`: `audit_link_folders.txt` (the 209 of 483 and the single-study baseline),
> `collision_A_result.txt` and `collision_B_result.txt` (the reproduction, standard path vs scoped config), `audit_link_collisions.txt`
> (the provenance view, which cannot see it), and `scripts\audit_link_folders.py`, `scripts\collision_check.py`. Taken to Ryan by the
> coordinator.
> - [ ] **Code:** `create_hardlink` must refuse (raise) when an existing file in the destination is not the same file
>   (`os.path.samefile`), instead of skipping it. Test with two acquisitions of one name.
> - [ ] **Template:** give the MRI `link_filename` a per-study part (the study start time, or the ACQ-ID), so a same-day repeat cannot collide.
> - [ ] **Audit and repair:** list the affected acquisitions (inode check of each link folder), then add the missing links under
>   distinct names (additive only: project folders are researcher-owned, 05_PROJECTS §3a). Ryan's decision.
> - [x] The first m12 study of 2026-07-10 avoids it with a scoped config (`_study1147` suffix).

> ## 🔹 LOW — an exam that produced no data is registered with today's date (2026-10-04)
> An aborted exam has no `visu_pars`, so `mri_acquisition_datetime` is empty and the preview shows today's date
> (`ACQ-20261004-MRI-…`); stream B hit it on its B06 setup scans and it recurs on exam 66 of the 2026-07-08 phantom. `expand_batch`
> should skip (or stop on) an MRI exam with no reconstructed image, as Ryan's rule of 2026-10-04 says. Both cases are handled by an
> allow-list case table today.

> ## 🔹 LOW — phantom and QC studies need a scoped config until the regex has a phantom branch (2026-10-04)
> Names without `m<animal>_<protocol>` match neither shared regex (D3). The five `jrc` phantom studies are ingested through
> `tools/configs/mri_july_1125/mri_phantom_*.yaml`, which take the sample label from ParaVision's `SUBJECT_id`. A durable fix is
> an explicit phantom path in the MRI template. The `phantom` / `material` rule is decided (2026-10-04): `phantom` for an imaging
> test object, `material` for a bare sample of a material under study.

> ## 🔹 LOW — another group's study lives inside m3's folder on the scanner (2026-10-04)
> `20260707_094320_jl260707_1225_m26_…` (13 exams, 358 MB) exists only nested in `…_m3_1125_…`. Not MFB; not ingested. Someone
> may want to tell the `jl` group.

> ## 🔹 LOW — a live WSL write to the share is about 20 times slower than local (2026-10-04)
> The five phantom configs (69 acquisitions, 509 files) took 31 minutes from WSL to `/mnt/gjesus3` against 84 s on D: scratch: roughly
> 2 s per small file over the 9p/SMB path (11_OPERATIONS §5.5 already notes that WSL cannot hard-link there). Plan a window by file
> count; a native-DICOM study with no project could be written from Windows instead.

**Update the item "14 MFB animal sessions on the scanner are registered nowhere":** tick the 9 protocol-1125 sessions (141
acquisitions) and the 5 phantom studies (69); done 2026-10-04. The 5 protocol-1025 sessions of 10-01/02 stay with the operators.

### `tasks/STATUS.md` (§2 drives bullet and §1 counts)

> - **✅ The July protocol-1125 series is in production, ingested from the scanner (2026-10-04).** 9 sessions
>   (m2, m3, m4–m8 including m6, the first m12 study, m19), 141 acquisitions, `ACQ-20260703-MRI-017…047`,
>   `ACQ-20260706-MRI-031…105`, `ACQ-20260710-MRI-035…069`, all native DICOMs, `PROJ-0021`, `Irene`. The five `jrc` phantom/QC
>   studies, 69 acquisitions with a blank project (`ACQ-20260611-MRI-001…005`, `ACQ-20260612-MRI-001…007`, `ACQ-20260708-MRI-001…033`,
>   `ACQ-20260709-MRI-001…018`, `ACQ-20260818-MRI-001…006`), `sample_type` `phantom` ×64 and `material` ×5 (stream B's rule; 18
>   regenerated at ingest; exam 66 of the 07-08 phantom excluded as never acquired). Registry 26,450 → 26,660 rows; verified end to end
>   (0 failed checks; validator unchanged at 10,314, all the `operator` placeholder). The protocol-1025 sessions of 10-01/02 stay with
>   the operators. The m12 first study needed its own link names (BACKLOG HIGH: link collisions).

### `CHANGELOG.md` (one dated row, newest first)

> | 2026-10-04 | R. Tasseff | **The July protocol-1125 MRI sessions and the five `jrc` phantom studies are ingested from the scanner: 210 acquisitions.** The nine sessions (m2, m3, m4–m8 including m6, m19, the first m12 study; `Irene`, `PROJ-0021`; 141 acquisitions, all native DICOM; `ACQ-20260703-MRI-017…047`, `ACQ-20260706-MRI-031…105`, `ACQ-20260710-MRI-035…069`) and the five phantom/QC studies (blank project; 69 acquisitions; `sample_type` `phantom` ×64 and `material` ×5 by stream B's rule; 18 regenerated at ingest with Dicomifier from WSL; exam 66 of the 07-08 phantom excluded as never acquired). Registry 26,450 → 26,660 rows. Verified end to end: rows and fields, DICOM counts, `checksums.json` == disk, SHA-256 against the scanner pulls, 141 / 141 link folders by inode, the eight counter changes exactly as predicted, registries append-only (+210 CRLF lines), validator unchanged at 10,314 errors (all the `operator` placeholder). **Found on the way:** the shared MRI link name has no per-study part and `create_hardlink` silently merges two acquisitions that share it: 9 of the first m12 study's 17 links would have been wrong, and **209 of 483 acquisitions on multi-study animal-days already have no link folder of their own** (`AE-biomaGUNE-0721`, `-1022`, `-0219`); `/raw/` is intact. The first m12 study uses a scoped config with a `_study1147` suffix. |

### `tasks/historical_drives_closeout_plan.md`

Step 5: mark the unregistered MFB sessions **[done 2026-10-04]** for the nine 1125 sessions and the five phantoms; the 1025 sessions
are the operators'. Add the link-collision audit and repair as a Step 5 item (Ryan's decision).
