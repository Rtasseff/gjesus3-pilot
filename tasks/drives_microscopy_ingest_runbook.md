# Runbook: the historical microscopy drives `.czi` ingest into TRUE PRODUCTION

**Status:** ✅ **CLEARED by the coordinator's gate (2026-09-30; `GATE_2026-09-30.md`, untracked at the worktree root), R1–R7 done.**
**The plan is FROZEN** at commit `c5f7fff` (see §1). **Branch:** `feat/drives-microscopy-ingest`, not
merged — the coordinator merges after the last batch is verified. The batch log is in
[`drives_ingest_dryrun_review.md`](drives_ingest_dryrun_review.md) §11.

This document says exactly which commands to run, in what order, what to check between them, and
when to stop. It is written so that a fresh session (possibly on a cheaper model) can run it without
the building session's context. **Read §0, §1 and §4 before running anything.**

| | |
|---|---|
| What | 8,790 distinct `.czi` acquisitions (3,849 GB): `CELL` 8,061 · `LSM9` 387 · `ZWSI` 4 · `XMIC` 338 |
| From | the hard-link farm `D:\projects\gjesus3\staging\_farm\B01…B16\` (links to the staged drives + `_extract\`) |
| Configs | `tools/configs/drives_2026-09/drives_B01.yaml … drives_B16.yaml` + `cases_Bxx.csv` (generated, committed, **frozen**) |
| Plan | `D:\projects\gjesus3\staging\_analysis\ingest\expected.csv` (one row per acquisition) |
| Creates | **exactly one project:** `AE-biomaGUNE-0118` (batch B02) |
| Tools | `tools/drive_staging/ingest_plan.py` (plan / farm / configs), `ingest_check.py` (dry-run review), `ingest_verify.py` (post-batch proof + provenance), `tools/reopen_project.py` |

---

## 0. The gate's decisions (2026-09-30, Ryan via the coordinator)

| # | Decision |
|---|---|
| **G1** | `AE-biomaGUNE-0219` (PROJ-0017) and `AE-biomaGUNE-1019` (PROJ-0006) are `closed` — **reopened with `tools/reopen_project.py` before B15/B16** (§1 step 7). Correction to the first draft: the folders were **not** gone. Both exist (ingests and the 2026-08 subfolder backfill re-created them; `1019` even got 18 new AxioScan sections on 2026-09-29); what the close-out removed was the status and the pre-close-out links. |
| **G2** | The 18 `ZWSI` "ROI lobulo" files are **not raw** (per-lobe crops of `ACQ-20260416-ZWSI-*`): excluded and handed to the non-raw session in `_analysis\ingest\nonraw_derived.csv`, with 4 `CELL` scale-bar copies. |
| **G3–G5** | Owner `Data-Office` for `0118`; `sample_type` `tissue` only where a subject id is recorded (and `ZWSI`); `XMIC` `data_source` `collaborator:Charite` — all confirmed. |
| **Tie-break guard** | Confirmed ("a good catch"). |
| **G6** | The building session runs B01–B04; **B05 onward goes to a fresh session** (see `HANDOFF_RUN.md` at the worktree root, untracked). |

---

## 1. Pre-flight

**The plan is frozen.** Do **not** run `ingest_plan.py plan` or `configs` again once B01 has run: a
re-plan drops the already-ingested files, re-cuts the batches, and `drives_B09.yaml` would then name a
different set of files (every registry row's `ingest_config` points at its config). Staleness is
handled per batch instead (§2 step 0).

**Once, before B01:**

```bash
cd "C:/Users/rtasseff/OneDrive - CIC biomaGUNE/projects/DataInfra/gjesus3-archive/gjesus3-dev/drives-microscopy-ingest"
git status                        # clean, on feat/drives-microscopy-ingest

# 1. Agree a window with the operators (they ingest daily -- 62 rows on 2026-09-29). GUI ingests
#    serialize on the registry lock, but the dedup snapshot is taken before the lock (BACKLOG
#    "Dedup identity"): two ingests of the SAME file at once can both land. Evenings / weekends
#    for the big CELL batches.

# 2. Extraction and farm present and exact (idempotent; they only fill gaps)
python tools/drive_staging/ingest_plan.py extract   # "extract: 346 members, 0 bad"
python tools/drive_staging/ingest_plan.py farm      # "0 errors, 0 stray files"

# 3. DB reachable (a miss would write subject = pending-db)
python tools/animal_db.py --check                  # "OK"

# 4. Baseline: record, do not trust a number written here
python tools/validate_registries.py --nas-root "J:\gjesus3-data" --no-enrichment > baseline_validate.txt
#    expected on 2026-09-30: 10,314 errors, ALL "column 'operator' still contains unsubstituted
#    template syntax '<REQUIRED - set via mri-ingest ...>'" (STATUS §0 D1); 0 warnings.
```

**Once, before B15 / B16 (G1):** reopen the two closed projects. Dry-run both first; the dry run may
show only **(a)** the two projects' rows changing (`status`, `notes`, dates), **(b)** links (and
`_project.yaml`, provenance rows, `index.html`) created **inside those two folders**, **(c)** no
deletion anywhere. Anything else: stop and report.

```bash
python tools/reopen_project.py --nas-root "J:\gjesus3-data" --project AE-biomaGUNE-0219 --dry-run
python tools/reopen_project.py --nas-root "J:\gjesus3-data" --project AE-biomaGUNE-1019 --dry-run
python tools/reopen_project.py --nas-root "J:\gjesus3-data" --project AE-biomaGUNE-0219 --reason "historical drives ingest"
python tools/reopen_project.py --nas-root "J:\gjesus3-data" --project AE-biomaGUNE-1019 --reason "historical drives ingest"
```

(Expected 2026-09-30: `0219` 80 links recreated, 4 collisions reported — two MRI sessions of animal
m23 on 2022-01-24 share link names, and a no-date placeholder; `1019` 421 links recreated,
`last_activity` 2022-09-28 → 2026-09-29.)

---

## 2. One batch (repeat for each row of §3, in order)

**`bash tools/drive_staging/run_drives_batch.sh Bxx` runs exactly the steps below** (0 and a–f) and
**stops at the first failed condition** — before the run whenever it can (step 0, the backup, the dry
run, a still-closed target project). It was used for B01–B04. Read every line of its output against the
pass conditions; the validator stop assumes the baseline 10,314 (if the MRI placeholder is fixed in the
meantime it stops by design — re-baseline, don't bypass). The commands, for reference:

```bash
B=B01                         # the batch
D=$(date +%Y%m%d)

# 0. Is the frozen plan still right for THIS batch? Operators ingest daily: a file of this batch may
#    have reached production since (same bytes = check 3; a re-save = 3b; a derivative = 3c).
python tools/drive_staging/catalog.py production              # fresh production hash index (~4 min)
python tools/drive_staging/ingest_check.py --batch $B         # every check PASS, 0 engine SKIPs
#    A FAIL here: stop and report. Do not re-plan; the fix is a reviewed edit of this batch only.

# a. OFF-NAS registry backup, fresh, dated, per batch -- NEVER re-use a directory
#    (a re-run once overwrote a backup and destroyed the rollback artifact, STATUS §0)
BK="C:/Users/rtasseff/temp/gjesus3_registry_backup_${D}_drives_${B}"
test -e "$BK" && { echo "backup dir exists -- pick a new one"; exit 1; }
mkdir -p "$BK" && cp -p /j/gjesus3-data/registries/*.csv /j/gjesus3-data/registries/.acq_id_seq.json "$BK/"
( cd /j/gjesus3-data/registries && sha256sum *.csv .acq_id_seq.json ) > "$BK/SHA256SUMS.src"
( cd "$BK" && sha256sum -c SHA256SUMS.src )          # every line OK, or stop

# b. confirm the target: the config must point at the farm, the run at J:
grep -n "staging_dir\|auto_create_projects\|instrument:" tools/configs/drives_2026-09/drives_$B.yaml

# c. dry run: "Batch: N cases", N == the batch's `files` in batches.csv, 0 SKIP lines
python tools/ingest_raw.py -c tools/configs/drives_2026-09/drives_$B.yaml --nas-root "J:\gjesus3-data" --dry-run > "$BK/dryrun.log" 2>&1
grep -c "SKIP" "$BK/dryrun.log"; grep "Batch:" "$BK/dryrun.log"

# d. the run (background it; big batches take hours -- see §3)
python tools/ingest_raw.py -c tools/configs/drives_2026-09/drives_$B.yaml --nas-root "J:\gjesus3-data" \
    --refresh-index projects > "$BK/run.log" 2>&1

# e. verify (all PASS), and record provenance
tail -12 "$BK/run.log"                                 # BATCH SUMMARY: Success N, Failed 0
python tools/drive_staging/ingest_verify.py --nas-root "J:\gjesus3-data" --batch $B \
    --provenance tasks/drives_ingest_provenance.csv
python tools/validate_registries.py --nas-root "J:\gjesus3-data" --no-enrichment > "$BK/validate_after.txt"
#    error count == the baseline's, and every error is still the MRI operator placeholder

# f. idempotency: the same command again must add nothing
python tools/ingest_raw.py -c tools/configs/drives_2026-09/drives_$B.yaml --nas-root "J:\gjesus3-data" > "$BK/rerun.log" 2>&1
grep "Total:" "$BK/rerun.log"                          # Total: 0

# g. log it: one line in the batch log table of the review doc (§3 below has the template)
```

**Pass conditions (all of them, every batch):** `Failed: 0`; `Success` == the batch's `files`;
`ingest_verify` all PASS (rows, fields, checksum = manifest sha256, sidecar, link is the raw primary,
no duplicate `acq_id`/`original_name`); validator error count unchanged and all of them the known
MRI placeholder; the re-run adds 0; the touched projects' `index.html` regenerated (the run log shows
the refresh; a refresh failure is a WARN — then run
`python tools/generate_index.py --nas-root "J:\gjesus3-data" --project <PROJ-ID>` by hand).

---

## 3. Batches, in order

Small and new-path batches first: `XMIC` (new code), `0118` (the one project created), `LSM9`
(archive members + subjects), `ZWSI`; then `CELL` ascending; the two reopened-project batches last.

| Batch | What | Files | GB | Projects | Est. time¹ |
|---|---|---:|---:|---|---:|
| B01 | XMIC, Charité | 338 | 4.3 | — | 20 min |
| B02 | CELL, `118 LUCIA` → **creates `AE-biomaGUNE-0118`** | 140 | 6.8 | 0118 (NEW) | 15 min |
| B03 | LSM9 (5 from `Fotos confocales cdh5 jagged2.zip`) | 387 | 5.2 | 1123 | 25 min |
| B04 | ZWSI (the 4 auto-named `0424` scans; the 18 ROI crops are out, G2) | 4 | 3.0 | 0424 | 5 min |
| B05 | CELL, no project (253 from `Drive zuri`, 6 from `Infartos Ruben_PR.zip`) | 2,023 | 129.3 | — | 2 h |
| B06 | CELL | 235 | 257.0 | 1321, 1422 | 3 h |
| B07 | CELL, no project | 1,519 | 393.2 | — | 4.5 h |
| B08 | CELL | 1,050 | 398.1 | 0721, 1022, 1123 | 4.5 h |
| B09 | CELL | 221 | 398.8 | 1321 | 4 h |
| B10 | CELL | 147 | 398.9 | 1123 | 4 h |
| B11 | CELL | 153 | 398.9 | 1123, 1321 | 4 h |
| B12 | CELL | 138 | 399.1 | 1321 | 4 h |
| B13 | CELL (82 from `Haizpea_2020-2022.7z`) | 1,235 | 399.7 | 0420 0423 0424 0522 0619 0721 | 4.5 h |
| B14 | CELL, no project | 801 | 400.0 | — | 4.5 h |
| B15 | CELL — `AE-biomaGUNE-1019`, **after its reopen (§1)** | 260 | 28.1 | 1019 | 20 min |
| B16 | CELL — `AE-biomaGUNE-0219`, **after its reopen (§1)** | 139 | 228.7 | 0219 | 2.5 h |
| | **Total** | **8,790** | **3,849** | | **≈ 30–35 h** |

¹ **Measured on B01–B04: 31–39 MB/s effective** (≈ 3–3.5 h per 400 GB). Each file is read once locally (source hash), written over SMB, and read back over SMB (verify):
2× bytes over the link at the 55–65 MB/s the NI pull sustained (`ni_gnuclear_production_runbook.md`)
≈ 35 s/GB, plus the per-acquisition registry/sidecar/link work (0.2–0.3 s on local disk in the
rehearsal; allow 1–2 s over SMB). The table is `tools/configs/drives_2026-09/batches.csv` of the frozen plan.

---

## 4. Stop conditions — stop, do not start the next batch, report

- `Failed` > 0, or `Success` ≠ the batch's `files`, or the dry run shows any `SKIP`.
- Any `ingest_verify` FAIL. In particular a **link** FAIL (a name collision would leave the new
  acquisition without a project link — silent in the engine) or a **checksum** FAIL.
- The validator's error count moves, or a new error class appears.
- Any `acquisition_datetime` blank, or an ACQ-ID dated today (`ingest_verify` fields).
- A project other than `AE-biomaGUNE-0118` appears in `registry_projects.csv` (compare row count to
  the backup: +1 after B02, +0 after every other batch).
- The re-run adds anything.
- Free space on the NAS below 1 TB (`df -h /j`), or D: disk errors.
- The animal DB turns unreachable (`pending_subject_metadata.csv` grows): stop, fix, the pending
  rows can be recovered with `tools/recover_subject_metadata.py`.

---

## 5. Rolling back one batch

There is deliberately no delete tool (10_TOOLS §2.1, *Side-effect inventory*). Reversal is a
Data-Office manual, backup-first operation. For batch `$B`, the rows are exactly those whose
`ingest_config` is `tools/configs/drives_2026-09/drives_$B.yaml`.

| # | Side effect | Reverse by |
|---|---|---|
| 1 | `raw/MICROSCOPY/<YYYY>/<YYYY-MM>/<ACQ-ID>/` per row | delete each folder (the `canonical_path` of each row) |
| 2 | `registries/.acq_id_seq.json` high-water | **leave it** (ids are never reused; the gap is by design) |
| 3 | `registries/registry_raw.csv` rows | remove the rows, byte-exact (keep line endings; `csv_safe`), or — if **no other writer** touched the file since (row count = backup + batch size) — restore the backup copy |
| 4 | `registries/ingest_manifest.csv` rows | remove the rows for those `acq_id`s (or restore, same condition) |
| 5 | `registries/registry_subjects.csv` upserts | remove only subjects **new** in this batch (diff against the backup); a shared subject stays |
| 6 | `registries/pending_subject_metadata.csv` | remove rows for those `acq_id`s (only on a DB miss) |
| 7 | project hard links `projects/<name>/raw_linked/<link_name>` | delete them (the plan's `link_name`) |
| 8 | `projects/<name>/provenance.csv` rows (`input_refs = <acq_id>`) | remove those rows |
| 9 | `projects/<name>/index.html` | `generate_index.py --project <PROJ-ID>` after the removal |
| 10 | B02 only: `projects/AE-biomaGUNE-0118/` + its `registry_projects.csv` row | remove both |

Then run `ingest_verify.py --batch $B` (every row now "missing"), the validator (baseline count),
and re-run the batch when fixed: the farm and configs are unchanged, so the re-run is the same run.

---

## 6. After the last batch

1. `python tools/drive_staging/ingest_verify.py --nas-root "J:\gjesus3-data" --batch B01 … --batch B16 --provenance tasks/drives_ingest_provenance.csv` — all PASS; commit the provenance CSV.
2. **Ryan's list:** every new ACQ-ID with a blank project and the project its path claimed —
   `expected.csv` rows with `verdict` ∈ {C, NO-CLAIM} joined to the provenance on sha256
   (the `claimed` column carries the (C) claim; the full claim text is in `file_claims.csv`).
3. `python tools/validate_registries.py --nas-root "J:\gjesus3-data"` (full, with enrichment) and
   `python tools/metadata_completeness.py --nas-root "J:\gjesus3-data"`.
4. `equipment/historical_data_archives.md`: the Cell Observer / LSM 900 history is ingested from the
   drives. STATUS / CHANGELOG wording goes to the coordinator (review doc §9), who applies it at merge.
5. **Keep** `_extract\` and `_farm\` until Ryan confirms the ingest; **never** touch the staged drive
   trees or the owners' drives.
