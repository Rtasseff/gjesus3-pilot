# Review: the July protocol-1125 MRI sessions and the five `jrc` phantom studies, ingested from the scanner (branch `feat/mri-july-1125`)

**Date:** 2026-10-04 · **Stream F, second task** (the first was [`mri_0710_reingest_review.md`](mri_0710_reingest_review.md)) ·
**Status:** 🔶 the read-only phase is done: every study pulled and hashed, every dry run read, every ingest rehearsed on
scratch copies. **No production write has happened.** The writes wait for the coordinator's window (streams A and C are
copying).

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
production. `sample_type` `phantom`, blank project, `researcher` and `operator` `NA` (stored blank, as for G1), 7T.

| Study | Exam folders → listed | DICOM | **Real IDs** | Note |
|---|---|---|---|---|
| `jrc260611.SPION` `20260611_190513_…` | 5 → 5 | **none**: regenerated at ingest | `ACQ-20260611-MRI-001…005` | |
| `jrc-260612_phantom_SPION_RGD` `20260612_141006_…` | 7 → 7 | **none**: regenerated at ingest | `ACQ-20260612-MRI-001…007` | |
| `jrc260708_phantom` `20260708_184152_…` | 42 → **41** (+1 excluded) | native ×41 | `ACQ-20260708-MRI-001…033` and `ACQ-20260709-MRI-001…008` | the run crosses midnight; **exam 66 excluded** (§2.3) |
| `jrc260709-phantom` `20260709_151028_…` | 10 → 10 | native ×10 | `ACQ-20260709-MRI-009…018` | after the 07-08 study's eight 07-09 IDs |
| `jrc260818_Phantom_MnACC` `20260818_112746_…` | 6 → 6 | **none**: regenerated at ingest | `ACQ-20260818-MRI-001…006` | |

**Totals: 210 acquisitions (141 + 69), 3,659 DICOM files, 238 MB; 18 exams regenerated.** Order matters for the IDs: m19
before m12's first study (09:08 before 11:47), and the 07-08 phantom before the 07-09 one.

**Spectroscopy and calibration exams (addendum): none.** All 211 exams are imaging methods: IgFLASH 104, FLASH 50,
FcFLASH 37, MSME 10, UTE 4, RAREVTR 3, B1Map 2, RARE 1. **One exam has no reconstructed image of any kind** (exam 66 of the
07-08 phantom, §2.3) and is excluded. The scanner keeps it.

## 2. Read this first: three things that need a decision

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

**Proposed:** run this one study through `tools/configs/mri_july_1125/mri_m12_first_irene.yaml`. It is the operator template
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
second acquisition on a shared path leaves no row.) A BACKLOG item is proposed in §9. **No repair is proposed here.**

### 2.2 Phantom `sample_type`: `phantom` for all five, or B07's split?

You asked for `phantom`, and I used it for all five. **Stream B's B07 rule** is `phantom` when the study name says phantom,
else `material` (bare nanoparticle samples). Under that rule four of mine are `phantom` and `jrc260611.SPION` (no "phantom"
in its name) would be `material`. Its scans are the same protocol as the two other nanoparticle studies (localizers, T1_FLASH,
T2map_MSME, T1map_RARE), and the same material series continues the next day as `phantom_SPION_RGD`, which is why I kept `phantom`. **No `phantom` or
`material` row exists in production yet, so whichever stream writes first sets the precedent.**

### 2.3 Exam 66 of the 07-08 phantom is excluded

`66` ("MSME TR 20 TE 2.2 ms") started and never produced data: it has `acqp`, `method` and `configscan`, and `pdata/1` holds only
`id`, `methreco`, `reco`. There is no `fid`, no `2dseq`, no `visu_pars` and no `ACQ_time`. **It has no reconstructed image, and
no acquisition date, so the ingest would register it with today's date** (`ACQ-20261004-MRI-…`), the soft fallback stream B hit
on its B06 setup scans. The config carries an allow-list case table (`cases_mri_phantom_0708.csv`, 41 rows) with
`on_missing: skip`; the exclusion is recorded in `excluded_mri_phantom_0708.csv`. It was the only such exam in the 14 studies.

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
  `jrc260708_phantom`, `jrc260709-phantom`, `jrc260818_Phantom_MnACC` (one has a `.`, two have `-`; B07 also used the label as typed).
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
native, 18 regenerated); IDs equal to the oracle per exam; `sample_type` phantom, no project, `researcher` blank, no today-dated
row; counters `…0611` 0 → 5, `…0612` 0 → 7, `…0708` 0 → 33, `…0709` 0 → 18, `…0818` 0 → 6; `registry_raw` and `ingest_manifest`
append-only (+69 each); the worklist, subjects, projects and tombstones byte-identical; no link, no `pending_links.csv`.**

## 6. The production write: order and checks (not run)

1. **Preflight** (`prod_preflight_july.py`, read-only; passed today 09:42): no lock, registry quiet; counters at 16 / 30 / 34 and
   0 for the five phantom prefixes; none of the 14 studies registered; `PROJ-0021` active; **none of the 141 link names exists
   in `raw_linked`**; no unregistered MRI folder on disk; all 8,423 pulled files at their manifest size and all 3,527 DICOM and
   `2dseq` files re-hashed. Rerun immediately before the write.
2. **Backup** to a fresh dated folder under `C:\Users\rtasseff\temp\` (registries, `.acq_id_seq.json`, `PROJ-0021`'s
   `_project.yaml` and `provenance.csv`), SHA-256-verified.
3. **Sessions, Windows,** in this order, from the repo root:
   `python tools\operator\mri_ingest.py "D:\projects\gjesus3\scratch_mri-july-1125\<study>" --nas-root J:\gjesus3-data --operator Irene --model 7T --no-prompt --go`
   for m2, m3, m4, m5, m6, m7, m8, m19; **then**
   `python tools\ingest_raw.py --config tools\configs\mri_july_1125\mri_m12_first_irene.yaml --nas-root J:\gjesus3-data`.
4. **Phantoms, WSL,** in this order: `mri_phantom_0611_spion`, `_0612_spion_rgd`, `_0708_phantom`, `_0709_phantom`, `_0818_mnacc`:
   `source ~/miniforge3/etc/profile.d/conda.sh && conda activate dicomifier-pilot`, then from the repo root
   `python tools/ingest_raw.py --config tools/configs/mri_july_1125/<file> --nas-root /mnt/gjesus3/gjesus3-data`.
   (Writing to the live share from WSL has precedent: the 2026-07-16 regeneration backfill and today's B04b regeneration.)
5. **Verify:** `verify_sessions.py` (rows == the predicted exam → ID map, fields, DICOM counts, `checksums.json` == disk,
   SHA-256 == manifests, link identity, DB subjects, counters, append-only registries) and `verify_phantoms.py` (same, plus
   sample_type, no project, no placeholder, regenerated counts). Then `generate_index.py --project PROJ-0021`, and the validator
   (expect the known 10,314 errors, one class, and no new class).

## 7. Surprises recorded

- **m12's first study and the `_bis` session are two real, distinct acquisitions.** Zero of 29 `2dseq` files and zero of 393
  DICOMs are shared; the exam times do not overlap (first study 11:58–12:55, `_bis` 13:19–14:33); it is the same full cardiac
  protocol (localizer, axial, 4-chamber, long axis, cine 4-chamber, cine slices) repeated on the same animal. The DB logs
  Organ sampling and Perfusion for animal 12 on that day, and no MRI. **Both studies get the same `session_id`**
  (`jrc20260710_m12_1125`: the shared regex drops `_bis`); `original_name` keeps them apart.
- **m3's folder holds another group's whole study:** `20260707_094320_jl260707_1225_m26_…` (13 exams, 274 files, 358 MB, protocol
  1225, started 2026-07-07 09:43), **nested inside it, and not present anywhere else on the scanner.** The `<study>/*` scope lists
  it as a skipped non-scan folder and does not descend, so nothing of it is ingested. It is outside MFB scope.
- **The 07-08 phantom crosses midnight** (18:51 → 08:29), so its IDs span two date prefixes.
- **`researcher: "NA"` is stored blank**, in the registry and the sidecar (as for G1); `modalities_in_study` comes out `MR`.
- **`NIFTI\` folders** sit in 13 of the 14 studies (all but the 08-18 phantom; the researchers' own conversions) and are skipped as
  non-scan siblings, as decided on 10-02. The 07-09 phantom also has a `Mapshim` folder; skipped the same way.

## 8. Questions

1. **§2.1: the `_study1147` suffix for m12's first study.** Yes? (The alternative is no project links for its nine colliding
   exams, which loses their links.)
2. **§2.2: `phantom` for `jrc260611.SPION`, or `material` by B07's rule?** I recommend `phantom` for all five. Which stream
   writes first sets the precedent, so agree the rule with B.
3. **§2.3: exam 66 excluded.** Yes?
4. **Phantom sample ids** keep the `.` and `-` of the typed `SUBJECT_id`. Yes, or normalise?
5. **The nested `jl` study in m3** is the only copy of that `jl` data anywhere on the scanner. Out of scope here; should someone
   tell its group?
6. **The window:** about 25 minutes for the 210 acquisitions (the ingests are seconds each; the WSL phantoms about 3 minutes),
   plus verification.

## 9. Proposed wording for STATUS, CHANGELOG, BACKLOG and the plan

*Drafted now; the bracketed facts are filled in after the writes. I have not touched these four files.*

### `tasks/BACKLOG.md`

> ## 🔺 HIGH — a second acquisition with an existing link name silently gets the first one's files (2026-10-04)
> Found while previewing the first m12 study of 2026-07-10. `linker.create_hardlink` (folder primary) does `os.makedirs(dest,
> exist_ok=True)` and links only files that do not exist yet, so two acquisitions with the same link name (same animal, same
> day, same exam number and recons) end up sharing one link folder: the second gets none of its own files, or a mix. The
> standard MRI link name `MRI_<sample>_<date>_<exam>_<recons>` has no per-study part. **It has already happened:** on 44
> multi-study animal-days (483 acquisitions) **209 have no link folder of their own (43.3%, against 2.65% on single-study
> days)**: `AE-biomaGUNE-0721` 153 of 294, `-1022` 53 of 179, `-0219` 3 of 10. `/raw/` and the registry are intact. Provenance
> cannot show it (idempotent on `output_path`). Evidence: `tasks/mri_july_1125_review.md` §2.1.
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
> an explicit phantom path in the MRI template, decided together with stream B's B07 (`phantom` / `material` rule).

> ## 🔹 LOW — another group's study lives inside m3's folder on the scanner (2026-10-04)
> `20260707_094320_jl260707_1225_m26_…` (13 exams, 358 MB) exists only nested in `…_m3_1125_…`. Not MFB; not ingested. Someone
> may want to tell the `jl` group.

**Update the item "14 MFB animal sessions on the scanner are registered nowhere":** [after the writes: tick the 9 protocol-1125
sessions and the 5 phantom studies; the 5 protocol-1025 sessions stay with the operators].

### `tasks/STATUS.md` (§2 drives bullet and §1 counts)

> - **[✅ after the writes] The July protocol-1125 series is in production, ingested from the scanner (2026-10-04).** 9 sessions
>   (m2, m3, m4–m8 including m6, the first m12 study, m19), 141 acquisitions, `ACQ-20260703-MRI-017…047`,
>   `ACQ-20260706-MRI-031…105`, `ACQ-20260710-MRI-035…069`, all native DICOMs, `PROJ-0021`, `Irene`. The five `jrc` phantom/QC
>   studies, 69 acquisitions with a blank project and `sample_type` `phantom` (18 regenerated at ingest). The protocol-1025 sessions
>   of 10-01/02 stay with the operators. The m12 first study needed its own link names (BACKLOG HIGH: link collisions).

### `CHANGELOG.md` (one dated row, newest first)

> | 2026-10-04 | R. Tasseff | **The July protocol-1125 MRI sessions and the five `jrc` phantom studies are [ingested] from the scanner.** [Counts, IDs and verification after the writes.] **Found on the way:** the shared MRI link name has no per-study part and `create_hardlink` silently merges two acquisitions that share it: 9 of the first m12 study's 17 links would have been wrong, and **209 of 483 acquisitions on multi-study animal-days already have no link folder of their own** (`AE-biomaGUNE-0721`, `-1022`, `-0219`); `/raw/` is intact. The first m12 study uses a scoped config with a `_study1147` suffix. |

### `tasks/historical_drives_closeout_plan.md`

Step 5: mark the unregistered MFB sessions **[done]** for the nine 1125 sessions and the five phantoms; the 1025 sessions are the
operators'. Add the link-collision audit and repair as a Step 5 item (Ryan's decision).
