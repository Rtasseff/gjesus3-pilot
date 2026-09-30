# Runbook: the historical microscopy drives `.czi` ingest into TRUE PRODUCTION

**Status:** 🔶 **PROPOSED — nothing has been written to production.** This waits on the
coordinator's review of [`drives_ingest_dryrun_review.md`](drives_ingest_dryrun_review.md) and on the
gate decisions in §0. **Branch:** `feat/drives-microscopy-ingest` · **Written:** 2026-09-30.

This document says exactly which commands to run, in what order, what to check between them, and
when to stop. It is written so that a fresh session (possibly on a cheaper model) can run it without
the building session's context. **Read §0 and §4 before running anything.**

| | |
|---|---|
| What | 9,090 distinct `.czi` contents (4.02 TB): `CELL` 8,333 · `LSM9` 397 · `ZWSI` 22 · `XMIC` 338 |
| From | the hard-link farm `D:\projects\gjesus3\staging\_farm\B01…B16\` (links to the staged drives + `_extract\`) |
| Configs | `tools/configs/drives_2026-09/drives_B01.yaml … drives_B16.yaml` + `cases_Bxx.csv` (generated, committed) |
| Plan | `D:\projects\gjesus3\staging\_analysis\ingest\expected.csv` (one row per acquisition) |
| Creates | **exactly one project:** `AE-biomaGUNE-0118` (batch B02) |
| Tools | `tools/drive_staging/ingest_plan.py` (plan / farm / configs), `ingest_check.py` (dry-run review), `ingest_verify.py` (post-batch proof + provenance) |

---

## 0. Decisions needed at the gate (the run does not start without them)

| # | Question | Default in the plan | Effect if changed |
|---|---|---|---|
| **G1** | `AE-biomaGUNE-0219` (PROJ-0017) and `AE-biomaGUNE-1019` (PROJ-0006) are **closed**; their folders were deleted on 2026-07-14. B15 (260 files, 28.1 GB) and B16 (139 files, 228.7 GB) target them. Step 12 would re-create `projects/<name>/raw_linked/` holding only these links (no `_project.yaml`). | B15/B16 run **last** and are marked `needs_decision`. | **(a)** reopen both projects first (status → `active`, restore the folder skeleton from `gjesus3_backfill_backup_20260714/deleted_projects/`, or `create_project`'s skeleton), then run; **(b)** re-plan them with a blank project (they join Ryan's list); **(c)** hold them back. |
| **G2** | 18 of the 22 `ZWSI` are `MFB_AUA_1123_ID2xxLu_TM_10x_ROI lobulo N.czi` (2026-04-16). They look like ZEN region-of-interest extracts from whole-slide scans, but they carry the AxioScan's hardware metadata (catalog class `czi-raw`) and are **not** on `S:\goptical` under any name or size. | Included (handoff §4.4: "if not there, include"). | Drop B04's 18 rows (re-plan) if ROI extracts should wait for the AxioScan route. |
| **G3** | The new project's owner. | `Data-Office` (placeholder; edit `_project.yaml`). | Any name; it is first-write-wins. |
| **G4** | `sample_type`. The handoff does not set it. | `tissue` where a subject id is recorded (histology of a DB animal) and for `ZWSI` (AxioScan convention); **blank** elsewhere (unknown — the best-guess back-fill can fill it later). | A literal per batch. |
| **G5** | `XMIC` `data_source`. | `collaborator:Charite` (06_REGISTRIES vocabulary is `internal` or `collaborator:<name>`; ASCII like `LIONS`/`HPIC`). | Any `collaborator:<name>`. |
| **G6** | Who runs it. | The coordinator decides; this runbook is written for a fresh session. | — |

---

## 1. Pre-flight (once, before B01)

```bash
cd "C:/Users/rtasseff/OneDrive - CIC biomaGUNE/projects/DataInfra/gjesus3-archive/gjesus3-dev/drives-microscopy-ingest"
git status                        # clean, on feat/drives-microscopy-ingest (or main once merged)

# 1. Nobody else ingesting. Agree a window with the operators (GUI ingests serialize on the registry
#    lock, but the dedup snapshot is taken before the lock -- BACKLOG "Dedup identity"). Evenings /
#    weekends for the big CELL batches.

# 2. Fresh production hash index, then re-plan. Operators keep ingesting; a content ingested since
#    2026-09-30 must drop out of the plan.
python tools/drive_staging/catalog.py production
python tools/drive_staging/catalog.py assemble
python tools/drive_staging/ingest_plan.py plan
git diff --stat tools/configs/drives_2026-09/     # after the next line
python tools/drive_staging/ingest_plan.py configs
#    If the configs changed, a content left or the batches re-cut: READ the diff, re-run step 4, commit.

# 3. Extraction and farm are present and exact (idempotent; they only fill gaps)
python tools/drive_staging/ingest_plan.py extract   # "extract: 347 members, 0 bad"
python tools/drive_staging/ingest_plan.py farm      # "0 errors, 0 stray files"

# 4. The dry-run review, again, against the fresh registry. Must end with every check PASS.
python tools/drive_staging/ingest_check.py

# 5. DB reachable (a miss would write subject = pending-db)
python tools/animal_db.py --check                  # "OK"

# 6. Baseline: record, do not trust a number written here
python tools/validate_registries.py --nas-root "J:\gjesus3-data" --no-enrichment > baseline_validate.txt
#    expected on 2026-09-30: 10,314 errors, ALL "column 'operator' still contains unsubstituted
#    template syntax '<REQUIRED - set via mri-ingest ...>'" (STATUS §0 D1); 0 warnings.
```

---

## 2. One batch (repeat for each row of §3, in order)

```bash
B=B01                         # the batch
D=$(date +%Y%m%d)

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
(archive members + subjects), `ZWSI`; then `CELL` ascending; the two closed-project batches last,
only after G1.

| Batch | What | Files | GB | Projects | Est. time¹ |
|---|---|---:|---:|---|---:|
| B01 | XMIC, Charité | 338 | 4.3 | — | 20 min |
| B02 | CELL, `118 LUCIA` → **creates `AE-biomaGUNE-0118`** | 141 | 6.8 | 0118 (NEW) | 15 min |
| B03 | LSM9 (6 from `Fotos confocales cdh5 jagged2.zip`) | 397 | 5.3 | 1123 | 25 min |
| B04 | ZWSI (G2) | 22 | 22.1 | 0424, 1123 | 15 min |
| B05 | CELL, no project (259 from `Drive zuri`, 6 from `Infartos Ruben_PR.zip`) | 2,187 | 216.6 | — | 3 h |
| B06 | CELL | 274 | 327.6 | 1321, 1422 | 3.5 h |
| B07 | CELL, no project | 1,584 | 393.4 | — | 4.5 h |
| B08 | CELL (82 from `Haizpea_2020-2022.7z`) | 1,232 | 396.9 | 0420 0423 0424 0522 0619 0721 | 4.5 h |
| B09 | CELL | 142 | 397.2 | 1321 | 4 h |
| B10 | CELL | 149 | 398.2 | 1123, 1321 | 4 h |
| B11 | CELL | 940 | 398.6 | 0721, 1022, 1123 | 4.5 h |
| B12 | CELL, no project | 816 | 398.9 | — | 4.5 h |
| B13 | CELL | 260 | 399.5 | 1123 | 4 h |
| B14 | CELL | 209 | 399.7 | 1321 | 4 h |
| B15 | CELL — **closed project, G1** | 260 | 28.1 | 1019 (closed) | 20 min |
| B16 | CELL — **closed project, G1** | 139 | 228.7 | 0219 (closed) | 2.5 h |
| | **Total** | **9,090** | **4,022** | | **≈ 45 h** |

¹ Each file is read once locally (source hash), written over SMB, and read back over SMB (verify):
2× bytes over the link at the 55–65 MB/s the NI pull sustained (`ni_gnuclear_production_runbook.md`)
≈ 35 s/GB, plus the per-acquisition registry/sidecar/link work (0.2–0.3 s on local disk in the
rehearsal; allow 1–2 s over SMB). The batch list is regenerated by `ingest_plan.py`; if it changes at
pre-flight, this table must be re-read from `tools/configs/drives_2026-09/batches.csv`.

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
