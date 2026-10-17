# Dedup identity: a content-anchored key (issue #5)

**Status:** ❓ EVALUATING. A design note for Ryan, written 2026-10-17 on branch `feat/dedup-key` while he is
away. The build follows it on the same branch (Stage 2); nothing here has touched production. Every number
below is quoted from `tasks/BACKLOG.md` ("Dedup identity", 2026-07-17 → 2026-10-04); none is new.

**Read this first if you have five minutes.** Today an acquisition counts as "already ingested" only when its
`(acquisition date, path relative to the staging folder)` is in the registry. The path changes with where
the operator points the ingest, so the same `.czi` comes in twice from two staging roots. It happened 22
times (plus 1 in `LSM9`). The proposal keeps that key and **adds a second one for `.czi` files:
`(instrument, acquisition timestamp to the second, file name)`**, the exact key the drives gate used on
2026-09-30/10-01 to find the 22 twins and the 206 re-saves. A case is a duplicate when either key is in the
registry or the tombstones. MRI and NI are not exposed today and keep their keys unchanged. What needs your
call is in §7; the dry run that proves it on production is in §8.

---

## 1. The key today, and where it lives

| What | Where |
|---|---|
| Index built: `(YYYYMMDD of acquisition_datetime, original_name)` for every live row **and every tombstone** (retired rows keep blocking, 06 §2.9.2). Blank `original_name` rows are skipped. | `tools/ingest/config.py:247` `_build_dedupe_index` |
| `original_name` set to the match's path relative to `staging_dir` (forward slashes). | `config.py:693-694` (`rel_match`) |
| NI flat pull: `original_name` replaced by the machine-issued acquisition key, so the same key is path-independent there. | `config.py:705-711` |
| Index read once per batch, before any copy. | `config.py:575-580` |
| Check, ordinary path: `(adt, rel_match) in existing_keys` → `SKIP … already in registry (idempotent re-run)`. | `config.py:963-973` |
| Check, NI per-recon path: the same key per reconstruction, then the cross-source guard `ni_flat.registered_recons` on `(timestamp14, modality[, recon])` → `SKIP … already in registry (from another source: …)`. | `config.py:937-960`; `ingest/ni_flat.py:90` |
| Preview counts both as "already ingested" by the substring `already in registry`. | `tools/operator/preview.py:241` `_categorize_skips` |
| Pending (`fix/ingest-write-guards`, #14): the same key re-read under the registry lock right before `append_row`. | `ingest_raw.py::_refuse_if_registered_meanwhile` on that branch |

The registry stores the acquisition timestamp in full: the templates take `acquisition_datetime` from
`discovered.czi_acquisition_datetime` (`axioscan7.yaml:179`; `axioscan7_mfb_20260614.yaml:70`), and
`resolver.normalize_acquisition_datetime` passes an ISO value through unchanged. So the timestamp the new key
needs is already in every `.czi` row; nothing has to be back-filled.

## 2. Why `(acq_date, staging-relative original_name)` fails

The path is a property of the staging layout, not of the acquisition. Production evidence (2026-09-29):

- **22 AxioScan files registered twice as `ZWSI`**, every pair one row from the 2026-06-14 bulk config
  `tools/configs/axioscan7_mfb_20260614.yaml` (staging root `…\AxioScan`, pattern `[0-9]*/*.czi`, so
  `original_name = 20260304/MFB_AUA_1123_ID12_PR_10x.czi`) and one from the operator recipe `recipes/aua.yaml`
  (staged at the date folder, so `original_name = MFB_AUA_1123_ID12_PR_10x.czi`). Same bytes, same date, two
  keys. Example: `ACQ-20260304-ZWSI-001` and `-023`.
- **10 more as both `CELL` and `ZWSI`** (the mis-coded best-guess rows), and **1 in `LSM9`** found later by the
  timestamp key.
- All 32 were retired on 2026-10-02; every bulk ingest since has had to dedup by hand before running.

The old key is still right for what it was built for: re-running the *same* folder selection is skipped. It
stays (§4).

## 3. Why SHA-256 fails too

The 2026-09-30 drives gate found **206 planned `.czi` that are re-saves of production acquisitions**: same
instrument, same acquisition timestamp to the second, same file name, 202 of them the same size, **different
bytes**. ZEN rewrites the container when display settings, annotations (a scale bar) or pyramids are saved.
There were also 84 such re-save groups among the drive files themselves. A checksum dedup lets all of them
through as new. The acquisition timestamp is written at acquisition and survives a re-save; the bytes do not.

## 4. The proposed key model

One rule for every ecosystem: **a case is already ingested when ANY of its keys is in the index**, and the
index is the union of the keys of every live row and every retired row. One function computes the keys,
`config.dedupe_keys_for(row_or_case) -> set`, and the same function builds the index and checks the case.
Because the old key is always one of the keys, **nothing that dedups today stops dedupping**.

| Ecosystem | Keys | Exposed today? |
|---|---|---|
| **All** | `(YYYYMMDD, original_name)`: the current key, unchanged, as a plain 2-tuple. | — |
| **Microscopy `.czi`** | + `("czi", instrument, timestamp[:19], file name lower-cased)` | **Yes**: the 22+1 twins, and every bulk/historical ingest. |
| **MRI (ParaVision)** | the current key only. `original_name` is already the instrument's own `<study folder>/<exam>` (pattern `*/*`). | **No**, in practice: the GUI pulls by SFTP into its own staging and always globs `*/*` at the study level; the CLI configs do the same. A deeper staging root would change it (§7 Q6). |
| **NI live box** | the current per-recon key, plus the existing cross-source guard on `(timestamp14, modality, recon)` (`registered_recons`). Untouched. | **No**: the guard already anchors on the machine-issued key (28 of irene's 54 box sessions were caught that way on 2026-10-08). |
| **NI flat (`S:\gnuclear`)** | the current key, whose `original_name` is already the machine-issued acquisition key. Untouched. | **No**. |

### The microscopy key in detail

Field choices are the drives gate's `resave_key` (`tools/drive_staging/ingest_plan.py:435`), which found
exactly the 22 known twins plus 1 on production:

- **Instrument.** The registry's instrument code, as the gate used. For an incoming case the key is made with
  the configured code **and**, when the file's device serial (`Metadata/HardwareSetting//Device/@SerialNumber`)
  names exactly one in-house instrument in `tools/reference/microscopy_instruments.yaml`, with that code too.
  So a ZWSI file run through the wrong template (the 23 `CELL` rows of 2026-09-29) still meets its `ZWSI`
  twin. The serial is read from the already-parsed `microscopy._raw_metadata`; no extra file read. The Cell
  Observer writes no serial, so for it only the configured code counts. External serials (`EXTERNAL:*`) are
  ignored: those rows are registered under `XMIC`, not the label.
- **Timestamp.** `acquisition_datetime[:19]` (`YYYY-MM-DDTHH:MM:SS`), the `.czi`'s `AcquisitionDateAndTime`
  to the second. **A timestamp of exactly `00:00:00` makes no content key**: that is what a folder-dated row
  looks like (`normalize_acquisition_datetime("20240625")` → `…T00:00:00Z`), and two different files named
  `Image 1.czi` on one day would otherwise collide. Such rows keep the old key only.
- **File name.** The last path component of `original_name`, lower-cased (the share is case-insensitive; the
  gate lower-cased too). Not the staging path: that is the whole point.
- **Only for `.czi` in the `MICROSCOPY` ecosystem.** `.tif` and other exports carry no timestamp the
  extractor reads; they keep the old key.

### What it catches, and what it deliberately does not

| Shape | Old key | New key | Result |
|---|---|---|---|
| Same `.czi`, second staging root (the 22 twins) | miss | hit | **skipped** |
| ZEN re-save: same instrument, second, name; other bytes (the 206) | miss (unless the same path) | hit | **skipped** |
| Re-run of the same folder | hit | hit | skipped (as today) |
| Scene split / stitched copy / region extract: same second, **different name** | miss | miss | **ingested** (see §7 Q1) |
| Retired duplicate's source re-run | hit (tombstone) | hit (tombstone) | skipped (as today) |

## 5. "Already ingested", precisely

A case is already ingested when at least one of `dedupe_keys_for(case)` is in
`⋃ dedupe_keys_for(row)` over every row of `registry_raw.csv` and every tombstone of
`retired_acquisitions.csv`. The skip prints:

- `SKIP <name>: already in registry (idempotent re-run)` when the old key hits. **Byte-identical to today**
  (the GUI preview and the drives tooling key on it).
- `SKIP <name>: already in registry (same acquisition: <instrument>, .czi timestamp <ts>, file name <name>)`
  when only the content key hits. It contains `already in registry`, so `_categorize_skips` counts it as
  already ingested without a change, as the NI cross-source line already does.

## 6. Retired rows

Tombstones take part exactly as live rows do (Ryan, 2026-10-01; 06 §2.9.2): `retired.original_row` gives the
row back verbatim and `dedupe_keys_for` keys it. A **re-identified** acquisition keeps both: the tombstone
keys the old instrument code and the new row the new one, with the same timestamp and name, so the source
stays blocked under either code. A re-identify never goes through the ingest, so its own tombstone cannot
block it (unchanged).

## 7. Open questions, with a recommendation each

| # | Question | Recommendation |
|---|---|---|
| Q1 | A scene split / stitched copy (same instrument and second, **another name**) is ingested as new. Should the ingest warn, as the drives gate flagged them with `drv_acq_group`? | **Yes, later, as a non-blocking note, with #11** (the same-timestamp clean-up). Not built here: a WARN would need a second index by `(instrument, second)` and a wording the drives tooling does not count as a failure; the pixel check (2026-10-04: 469 derivatives, 350 kept) shows these are often real scenes, so a skip would lose data. |
| Q2 | When the device serial names a different instrument than the template (the 25-row defect), should the ingest refuse or warn? | **Warn at preview** in a separate change. This note only uses the serial to widen the dedup match; it never changes the instrument recorded. |
| Q3 | No content key for a `00:00:00` timestamp (folder-dated rows). Right? | **Yes.** The cost is that a folder-dated row and a later `.czi`-dated ingest of the same file do not meet; the old key still catches a same-folder re-run. A genuine acquisition started at midnight to the second loses only the content key. |
| Q4 | File name compared case-insensitively. | **Yes**, as the gate did; the share is case-insensitive. |
| Q5 | Should a content-key hit name the ACQ-ID it matched? | **Nice to have; not built.** The index is a `set` today and the pending #14 re-check uses `in` on it; making it a `dict` (key → ACQ-ID) is a small follow-up once #14 is merged. |
| Q6 | MRI: add a tail key `(instrument, timestamp, last two components of original_name)` so a deeper staging root still dedups? | **Not now.** No MRI path stages deeper today. Add it when a bulk MRI ingest from another root is planned (#19 / #40). It would slot into `dedupe_keys_for` without touching anything else. |
| Q7 | Priority (issue asks to re-rate). | **HIGH**, as #5 proposes: the bulk ingests are the reason it bites, and Box A will run more of them. |

## 8. Production dry run (for Ryan, read-only)

The real case: files the 2026-06-14 bulk config registered from `S:\goptical\GOpticalUsers data\AxioScan` with
`original_name = <YYYYMMDD>/<file>.czi`, seen again from a date folder as the operator recipe does.

1. **Pick a date folder** under `S:\goptical\GOpticalUsers data\AxioScan\` that the bulk config ingested and
   the AUA recipe has **not** (any date other than the 22 twins' dates; their recipe rows are retired and
   would hit the old key through the tombstones, which proves less). Note how many `MFB_*.czi` it holds.
2. **Before (on `main`):** open the operator GUI, instrument AxioScan, recipe `aua.yaml`, folder = that date
   folder, **Preview**. Expected today: the files show as *new*, `0 already-ingested` (this is the bug).
   Do **not** ingest.
3. **After (this branch):** same Preview from a build of this branch (or the CLI, below). Expected: **every**
   file reported already ingested, each with a `SKIP … already in registry (same acquisition: ZWSI, .czi
   timestamp …)` line, and `0` new.
4. **CLI equivalent (no GUI build needed):** copy `tools/configs/axioscan7_mfb_20260614.yaml` to a scratch
   file, set `staging_dir` to the date folder and `pattern: "*.czi"`, then
   `python tools/ingest_raw.py -c <scratch>.yaml --nas-root J:\gjesus3-data --dry-run`. Expected: `No new
   cases to ingest`, one content-key SKIP line per file. (Dry run stops before any write.)
5. **Control:** re-run the same scratch config with `staging_dir` back at `…\AxioScan` and `pattern:
   "<YYYYMMDD>/*.czi"`. Expected: every file skipped with the *old* `(idempotent re-run)` line, unchanged.
6. **Pass:** step 3/4 report N of N already ingested; step 5 unchanged. Any file that comes out *new* in
   step 3/4 is either folder-dated (`00:00:00`; check its `acquisition_datetime`) or genuinely not in
   production; look before ingesting.

## 9. What the build changes (Stage 2)

- `config.dedupe_keys_for(row_or_case)`; `_build_dedupe_index` = the union over live and retired rows;
  `expand_batch`'s ordinary check uses `keys & index`. The NI per-recon guard is untouched.
- `run_batch(..., stats=None)` reports `n_already_ingested`; `runner.run` passes it through; the GUI's `done`
  event and both result lines (microscopy and MRI pages) show it.
- 06_REGISTRIES gains a 🔶 DRAFT subsection with this contract; 10_TOOLS' idempotency bullet updated.
- `tools/test_dedup_key.py`.
- **For the merger of #14:** `_refuse_if_registered_meanwhile` keeps working unchanged (the old key is still a
  plain 2-tuple in the index). To make it check the content key too, change its body to
  `hit = config.dedupe_keys_for(row) & config._build_dedupe_index(registry_path)` with the `row` built just
  above its call site.
