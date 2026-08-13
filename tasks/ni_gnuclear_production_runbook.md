# Runbook — ingesting the `S:\gnuclear` historical NI into TRUE PRODUCTION

**Status:** 📋 **PROPOSED — FOR RYAN'S REVIEW. Nothing in §3 has been run.**
**Written:** 2026-08-13 · **Branch:** `feat/ni-gnuclear-historical` (8 commits, not pushed)
**Plan + measured evidence:** [`ni_gnuclear_active_space_plan.md`](ni_gnuclear_active_space_plan.md) (start at §-2)

This document says exactly which commands I propose to run, in what order, what I check
between them, and when I stop. **Production writes wait on your explicit go-ahead.**

---

## 1. What is already done (no approval needed — it happened)

| | Evidence |
|---|---|
| **286.3 GB staged** off `S:\gnuclear` to `J:\gjesus3-data\staging\ni_gnuclear_20260812\` | 2,485 files, 0 failures; `--verify` re-read → **2,485 ok / 0 corrupt / 0 missing** |
| Source untouched | tool opens `S:\` paths `"rb"` only; no writes/renames/deletes |
| **Ingest built + unit-tested** | `tools/test_ni_flat.py` **20/20**; all **19** pre-existing suites green |
| **Phase-3 scale run PASSED** | 227/227 (`Itziar`) into `J:\gjesus3-sandbox-ni20260812`, `validate_registries` **0 errors**, idempotent re-run = 0 new |
| **Production untouched** | NI rows still **132** — unchanged all day |

Everything below §3 is the part that changes production.

---

## 2. What gets ingested, and what does not

Of **2,312** acquisitions in the snapshot:

| | Count | Why |
|---|---|---|
| **Ingest now** | **1,508** | protocol code present in the path **and validated against the animal-facility DB** |
| Skipped automatically | **131** | that scan is already in production (archive round 8) — cross-source dedup on `(timestamp, modality)` |
| **Held back** | **673** | no *valid* protocol code anywhere in the path. **D-G** — an AE code is a regulatory identifier and I will not invent one. Ingesting them later costs nothing; dedup is on the machine timestamp. |

**Protocol codes are validated, not trusted** (`REVIEW_FINDINGS_2026-08-13.md` §1). The first
version of this run would have created **25 new projects, 21 of them fabricated** — `2302` is the
date folder `230217`, `245` and `100` are animal numbers. That contradicted this pull's own rule.
Now the path-derived code is checked against the facility DB and, when wrong, the real code is
recovered by walking up whole path segments: **99 recovered, 15 rejected outright** (they join the
held-back set). **New projects created drops from 25 to 4** — `0324`, `0421`, `1024`, `1122`, all
DB-verified. Independent confirmation: 93 of 93 recovered `(project, animal)` pairs resolve in the
facility DB.

**Unit = one acquisition per *reconstruction*** — `(timestamp, modality, algo, recon_idx)` — matching
what `feat/ni-live-hardening` landed, so rows from both sources have the same shape.

---

## 3. The proposed production run

### 3.0 Pre-flight (once, before the first batch)

```bash
cd "C:/Users/rtasseff/OneDrive - CIC biomaGUNE/projects/DataInfra/gjesus3-archive/gjesus3-dev/ni-gnuclear-historical"

# 1. Back up the production registries OFF-NAS first.
mkdir -p "C:/Users/rtasseff/temp/gjesus3_pre_ni_gnuclear_20260813"
cp /j/gjesus3-data/registries/*.csv "C:/Users/rtasseff/temp/gjesus3_pre_ni_gnuclear_20260813/"

# 2. Record the baseline so every delta is checkable.
PYTHONPATH=tools python tools/validate_registries.py --nas-root J:/gjesus3-data
```

**Record whatever that prints — do not trust a number written here.** Production is live and
other work writes to it: the total went from 13,938 to **13,966 rows during the day I was
building this**, with NI unchanged at 132. So the only baseline that means anything is the one
measured immediately before batch 1, and the delta checks in §3.3 count **NI rows**
(`instrument in PET/CT/SPECT/OI`) rather than total rows, precisely so that unrelated
concurrent ingests cannot make this run look wrong.

Expected at that moment: **132 NI rows, 0 validator errors.**

### 3.1 One batch = one researcher

For each batch I create a config from the template, changing **one line**, then run it.

```bash
# create the batch config (only `researchers:` differs between batches)
python - <<'PY'
src = "tools/templates/instruments/molecubes_ni_gnuclear.yaml"
out = "tools/configs/ni_gnuclear_prod_<WHO>.yaml"
t = open(src, encoding="utf-8").read()
n = t.replace('  # researchers: [Irene, Itziar]', '  researchers: [<WHO>]')
# A non-matching str.replace returns the original SILENTLY, and a config with no
# researchers: key ingests ALL 1,508 in one go. Make that structural, not advisory.
assert n != t, "researchers: substitution did not match — refusing to write a config that would ingest EVERYTHING"
open(out, "w", encoding="utf-8").write(n)
PY

# ⚠️ CONFIRM THE TARGET BEFORE EVERY SINGLE RUN — there is still no test-vs-prod guard,
# and a dev run once left synthetic acqs in production by pointing this at J:\gjesus3-data.
grep -n "staging_dir\|researchers:" tools/configs/ni_gnuclear_prod_<WHO>.yaml

# the run
PYTHONPATH=tools python tools/ingest_raw.py \
  --config tools/configs/ni_gnuclear_prod_<WHO>.yaml \
  --nas-root J:/gjesus3-data
```

`--nas-unc` is deliberately omitted — `tools/INGEST_CLI.md` documents it as the legacy `.lnk`
porting seam, unused by the hard-link linker.

### 3.2 Batch order — smallest and cleanest first

Escalating, so a surprise shows up on 1 acquisition rather than 503. **Itziar is the cohort
already proven end-to-end in the sandbox**, which is why it sits mid-list rather than first.

Batches `211217`, `Kepa` and `Alba` **disappear entirely** — every one of their acquisitions was
under a fabricated code, so all 15 join the held-back set. Ten batches become seven.

| # | `researchers:` | Acqs | GB | ~min | Note |
|---|---|---:|---:|---:|---|
| 1 | `[CarlottaS]` | 20 | 8.9 | 8 | new smoke test — see below |
| 2 | `[Ermal]` | 25 | 15.2 | 14 | |
| 3 | `[IAZ_MJ]` | 133 | 4.5 | 4 | 2022 `MOLECUBES\` extra level |
| 4 | `[MJ]` | 216 | 9.0 | 8 | **66 recovered → `0522`**; sandbox-proven |
| 5 | `[Itziar]` | 227 | 19.9 | 18 | sandbox-proven |
| 6 | `[Irene]` | 384 | 22.9 | 21 | 12 recovered → `0324`. **Case-insensitive → `Irene` + `irene`, 2024/2025/2026 together** |
| 7 | `[Marina]` | 503 | 111.7 | 102 | 6 recovered → `1321`; biggest, run last |
| | **TOTAL** | **1,508** | **192.0** | **~3 h** | |

> **⚠️ These rows are re-derived from the code, and they differ from the table in
> `REVIEW_FINDINGS_2026-08-13.md` §4** (which gave MJ 282, Irene 396, Marina 509). Those rows sum
> to **1,592** against the review's own stated total of 1,508 — the recovered acquisitions were
> *already inside* those researchers' counts, since a bogus code still passed `require_project`.
> Recovery changes **which project** they land in, not **whether** they are ingested. The review
> anticipated exactly this and said to re-derive rather than copy; §3.3's batch-size pass
> condition depends on these being right.

**On the smoke test.** The 1-acquisition batch (`211217`) was itself one of the fabricated codes,
so it is gone. `CarlottaS` (20 acqs, 8.9 GB, ~8 min) is the new batch 1 and the smoke step is
**not** skipped: after it, everything in §3.3 is checked before batch 2 starts.

`~min` assumes 3× bytes over SMB per acquisition (read source, write dest, read back to verify)
at the 55–65 MB/s this link actually sustained during the pull.

### 3.3 Checks after EVERY batch — before starting the next

```bash
# a. the batch's own summary must read N success / 0 failed
# b. registry integrity
PYTHONPATH=tools python tools/validate_registries.py --nas-root J:/gjesus3-data

# c. the delta is exactly what was expected, and no duplicates crept in
PYTHONPATH=tools python -c "
import csv,collections
rows=list(csv.DictReader(open(r'J:\gjesus3-data\registries\registry_raw.csv',encoding='utf-8-sig')))
ni=[r for r in rows if r['instrument'] in ('PET','CT','SPECT','OI')]
print('total rows :',len(rows))
print('NI rows    :',len(ni))
print('dup acq_id :',len(ni)-len({r['acq_id'] for r in ni}))
print('dup orig   :',len(ni)-len({r['original_name'] for r in ni}))
print('blank adt  :',sum(1 for r in ni if not r['acquisition_datetime'].strip()))
"

# d. idempotency — re-running the SAME batch must add nothing
PYTHONPATH=tools python tools/ingest_raw.py --config tools/configs/ni_gnuclear_prod_<WHO>.yaml --nas-root J:/gjesus3-data
#    expected: Total: 0 / Success: 0 / Failed: 0
```

**Pass conditions:** `0 failed`, **0 validator errors**, `dup acq_id = 0`, `dup orig = 0`,
`blank adt = 0`, NI row count up by exactly the batch size, and the re-run adds nothing.

**A shortfall in the NI count is the check that matters most.** Cross-source dedup is on
`(timestamp, modality)` while the ingest unit is per-reconstruction, and **142 scans in this set
have more than one reconstruction (290 acqs)**. If a batch dies between two reconstructions of the
same scan, the re-run skips the surviving sibling *silently* — it looks like a clean resume. A
count below the batch size is how that shows up. If it happens, find the gap with:

```bash
PYTHONPATH=tools python -c "
import sys; sys.path.insert(0,'tools')
from ingest import ni_flat
m,idx,n = ni_flat.discover(r'J:\gjesus3-data\staging\ni_gnuclear_20260812',
    registry_path=r'J:\gjesus3-data\registries\registry_raw.csv')
print(len(m),'still outstanding')"
```

**I stop and report — I do not continue to the next batch — if any of those fail.**

### 3.4 After the last batch

```bash
PYTHONPATH=tools python tools/verify_checksums.py --nas-root J:/gjesus3-data   # sample-verify deposited files
PYTHONPATH=tools python tools/metadata_completeness.py --nas-root J:/gjesus3-data
```

Then update `tasks/STATUS.md`, `CHANGELOG.md` and
`equipment/historical_data_archives.md` (mark `S:\gnuclear` *partially ingested*, with coverage),
and commit.

---

## 4. If something goes wrong

- **A batch fails partway.** Acquisitions already committed stay; the failed one rolls back its
  own folder (`_rollback_uncommitted`). Fix, then **re-run the same command** — dedup prevents
  duplicates, verified in the sandbox. **But the resume is only complete for single-reconstruction
  scans.** Cross-source dedup keys on `(timestamp, modality)`, so once *any* reconstruction of a
  scan is registered, the re-run skips its siblings too — for the **142 multi-recon scans (290
  acqs)** an interrupted batch can leave a sibling permanently unignested and look clean doing it.
  §3.3's NI-count check is what catches it; the outstanding-count command there names the gap.
- **Wrong rows land.** They are removable: `tasks/ni_prod_testdata_removal.md` documents the
  exact procedure used in August to pull 2 synthetic acquisitions out of production (registry
  rows across 5 CSVs, raw folders, auto-created project + subject).
- **Worst case.** All NI in production is 132 old rows + whatever this adds, all identifiable by
  `instrument in (PET,CT,SPECT,OI)` and `ingest_config` — so a full NI reset is possible, per
  your "worst case we strip NI and start that data type over."
- **The staged snapshot is the safety net.** It is checksummed and independent of `S:\gnuclear`;
  re-ingesting never needs the network pull again.

---

## 5. Explicitly NOT in this run

- The **658 held-back** acquisitions (D-G, needs protocol codes).
- **Derivatives** — `.nii`, `.voi`, PMOD `.xlsx`, `.mat`, segmentations sitting beside the DICOMs
  (D-E: primary DICOM only; these belong in project workspaces, a separate pass).
- Anything on `feat/ni-live-hardening`. Untouched.
- **Deleting the staging snapshot.** It stays until you say otherwise.
- Migrating the stale shared `J:\gjesus3-sandbox` registry (`project_hint` → `project_id`).
  Flagged in `STATUS.md`; not mine to change mid-flight.

---

## 6. What I need from you

1. **Go / no-go on §3**, and whether to run all ten batches or stop after a specific one for review.
2. **Off-hours?** Batch 10 (Marina, 112 GB, ~1.7 h) is the only one heavy enough to care.
3. **D-G, whenever convenient** — protocol codes for the **673**. Full list:

   ```bash
   PYTHONPATH=tools python tools/ni_gnuclear_discover.py \
     --root J:/gjesus3-data/staging/ni_gnuclear_20260812 --csv review.csv
   ```
   then filter to rows with an empty `project` column. (`--root`, not `--from-plan` — `_plan.csv`
   is only written by `pull_ni_gnuclear.py --plan` and is not in the snapshot.)

   Note the 673 now include 15 acquisitions whose path-derived code was **rejected** as not a real
   protocol, flagged `project-rejected:<code>`. The same walk-up recovery would likely rescue some
   of the original 658 too; that was deliberately left alone so the measured numbers here stay
   valid, and it belongs with the researcher mapping.

---

## 7. Command reference (the three tools)

| Tool | Purpose | Writes? |
|---|---|---|
| `tools/pull_ni_gnuclear.py` | stage DICOMs off `S:\gnuclear`; `--plan` / `--go` / `--verify` | staging only; **never** the source |
| `tools/ni_gnuclear_discover.py` | review table — subject, project, animals, flags | **nothing** |
| `tools/ingest_raw.py --config <batch> --nas-root <root>` | the ingest | `/raw/`, `/projects/`, `/registries/` |
