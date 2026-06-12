# NI live-machine sync — handoff (fresh-session resumable)

**Status:** 2026-06-12. **Step 1 is DONE, tested, and reviewed by both the agent and the data office.**
The remaining work is two external gates and **Step 2** (the build), split so two people don't edit the
shared registry code. This file is the single entry point to resume in a fresh session and pick up the
designer's input.
**Audience:** a fresh Claude/Fable session continuing the live-machine NI sync.

## Read these first (in order)
1. **`equipment/nuclear-imaging/live_machine_data_layout_and_sync_rules.md`** — the design of record.
   §0 (MVP-first), §2A (roster), §3A (subject grammar + DB-as-validator), §3B (one-entry-per-scan,
   Model 1), §3C (subjects table + minimal sidecar), §7 (the plan + the "Path forward" block), §8
   (open questions NI-LIVE-01…13).
2. **This file** — what's done, what's left, who does what, how to resume.
3. **`git log origin/main`** — pick up the designer's latest. As of this handoff the designer is
   landing the **Step-2 schema reshape** (see below); check what actually landed before wiring onto it.

## What is DONE (do not rebuild)
- **Step 1 — `tools/ni_live_discover.py`** (read-only discovery dry-run): roster→folder, recursive
  anchor walk (`<YYYYMMDDhhmmss>_<MODALITY>`), subject parse → (project, 1–4 animals, timepoint),
  date-mismatch flag, would-be facility key, review table + `--csv`. **Writes nothing.** Validated on
  the snapshot: **254/262 (97%) of MFB NI scans DB-keyable; 102/262 multi-animal; rats parse.**
- **`tools/test_ni_live_discover.py`** — 30 checks, green (pins the §3A example table, the
  `project-conflict` flag, and the `facility_id`↔`animal_db.compose_subject_id` contract).
- **`project-conflict:<parent>` flag** (NI-LIVE-09 partial) — flags only typo-shaped near-misses
  (`1015` vs `1025`); 12 acqs on the snapshot. Does NOT decide which code wins.
- **Shared infra already on `main` (reuse, don't rebuild):** `tools/ingest/locking.py` (registry lock +
  durable ACQ-ID reservation), `csv_safe.py` (BOM/newline-safe appends), archive re-run idempotency,
  crash-orphan rollback (registry append = commit point), empty-folder fail-loud, cross-drive relpath,
  `tools/diagnostics/test_oslink.py`, single-animal DB lookup (`subject_id.py`/`animal_db.py`/
  `enrichment.py`) + `pending_subject_metadata.csv` + `recover_subject_metadata.py`.
- **Decisions:** NI-LIVE-08 (packed `subject_ids` + true `registry_subjects.csv` + minimal sidecar; no
  mapping table; query deferred) and NI-LIVE-12 (our own NAS subjects table) — **RESOLVED**.

## What is LEFT — Step 2 (build) + Step 3 (ingest), with the division of labor

### Gate 0 — external, the real unblock (USER; deferred — user is remote)
- [ ] Run `python3 tools/diagnostics/test_oslink.py <scratch-on-the-mounted-share>` **on the Mac /
      Molecubes box** → hard-link feasibility for push-from-Mac. If it FAILS, the fallback is to run the
      *ingest* from a Windows box (hard-links proven) or the `.lnk` path. **Gates a real ingest (Step 3),
      NOT Step-2 coding.** *(User will do this on return.)*
- [ ] Confirm with **Unai**: canonical layout for all MFB NI users + MILabs VECTor? script-on-Mac vs
      Linux NI server? the forward naming standard (NI-LIVE-13).

### Two decisions Step 2 needs (small — user/Unai)
- [ ] **NI-LIVE-09 resolution:** on a `project-conflict` flag, which code wins? *Proposed:* keep the
      subject prefix (§3A) but route the 12 flagged acqs through `pending_subject_metadata.csv` for human
      confirm before the DB key is trusted ("flag, don't guess").
- [ ] **NI-LIVE-07:** confirm "dashes are explicit lists; flag gap>1 (`possible-range`)" as the rule
      (the tool already does this) — and whether the species prefix (m/r/none) is trusted or species is
      always taken from the DB.

### Step 2a — schema reshape — **DESIGNER owns** (their `23df602`/`build_row` territory)
- [ ] Rename singular `subject_id` → **packed `subject_ids`** in `tools/ingest/registry.py`
      (`REGISTRY_FIELDS`), `build_row` (project `subject.facility_animal_id` as a `;`-joined length-1+
      list), `resolver.py` (`AUTO_COLUMNS`), `test_registry_fields.py`, and `06_REGISTRIES.md` §2.2.
      The code comment at `registry.py:45` already marks this as pending. **Do this on the fresh/empty
      production registry BEFORE bulk ingest** (cheap; avoids migrating populated rows).
- [ ] Add the **`registry_subjects.csv` writer** — one row per `(acq_id, project, animal,
      facility_id, scan_position)`; updatable/back-fillable; goes through `csv_safe`. Document in
      `06_REGISTRIES.md` (new table) + `08_METADATA.md` (sidecar `subjects:[…]` minimal subset).

### Step 2b — live-NI glue — **separable; the fresh session does this** (no shared-registry edits)
- [ ] **`tools/templates/instruments/molecubes_ni_live.yaml`** — copy `molecubes_ni.yaml`, drop the
      archive-name regex; source = a folder tree on the box; fields come from the §3A path-walk, not a
      filename. (`molecubes_ni.yaml` stays archive-mode.)
- [ ] **Discovery→ingest wiring:** promote `ni_live_discover.py`'s walk+parse from preview to ingest:
      for each scan, assemble the 1–4 animal list, call the **existing** per-animal `animal_db` lookup
      (iterate; misses queue to `pending_subject_metadata.csv`), emit the packed `subject_ids` +
      sidecar `subjects:[…]`. Reuse `copy_ni_acquisition` + `ni_metadata.py` + the project hard-link
      (one per scan) + `locking` + `csv_safe` **unchanged**. Idempotency key stays `(timestamp,
      modality)` (Model 1 — one entry per scan).
- [ ] Per-animal **scan_position**: record when known; historical = flag unknown (NI-LIVE-11).

### Step 3 — vetted one-shot (after Gate 0 + Step 2)
- [ ] Run the discovery dry-run → **human reviews the table** (esp. the `no-project` + `project-conflict`
      + `possible-range` rows) → ingest to **`J:\gjesus3-sandbox`** first → verify idempotent re-run,
      empty-folder guard, the `os.link` result, packed `subject_ids` + subjects-table correctness →
      then the live NAS.

### Parked (per "stop expanding the model")
Program B forward-standard sync; the per-`(acq,subject)` mapping/junction table; per-animal image
splitting (Model 2 — the deferred derivative); the query layer (XNAT/OMERO/own DB).

## Resume checklist (fresh session)
1. `git pull`; read the design doc §7 + this file; `git log` for the designer's schema-reshape commits.
2. Confirm whether **Step 2a (packed `subject_ids` + `registry_subjects.csv`)** landed; if yes, do
   **Step 2b** (live-NI glue) onto it; if not, coordinate.
3. Check the two decisions (NI-LIVE-09/07) and Gate 0 status before any real ingest.
4. Re-run `tools/test_ni_live_discover.py` (must stay green) after any parser change.

## Does this block adding HISTORICAL data to the production NAS? — Mostly NO

The open questions above are **specific to the NI live-box (REMIW11) path**. They do **not** block the
other historical sources, which use the existing tested pipeline and are single-subject (so the
singular→packed `subject_ids` change is a trivial length-1 case):

| Source | Path | Ingest path | Blocked by NI-live Qs? |
|---|---|---|---|
| **MRI** | `kenia` SFTP (`/opt/PV-*/data/nmr`) | built + tested (round 6); creds set | **No** |
| **Microscopy — AxioScan 7** | `S:\goptical\…\AxioScan` | built (GUI + recipe) | **No** |
| **Microscopy — Cell / Confocal** | `K:\gjesus\Ainhize\…` | built (GUI + recipes) | **No** |
| **NI — archive mode** | `\\cicmgsp02\gnuclear2$` (.tgz) | built + tested (round 8) | **No** (single-animal per .tgz) |
| **NI — live box** | Mac `/data/<researcher>` | Step 1 only | **YES** (Gate 0 + Step 2) |

**NI source-of-truth = the ARCHIVE — DECIDED 2026-06-12 (user).** Users cannot alter the live box, and a
**systematic script pulls box→archive**, so the archive is authoritative and complete: **`gnuclear2$`
now, `gnuclear3` (needs access) in future.** **Preload all historical NI from the archive** via the
already-built, tested archive-mode pipeline (round 8). The archive handles the **historical preload**;
the **live-box sync is the forward path for active project data and is ESSENTIAL — not optional.**
gjesus3 is an active repository for *live project data* (≈30% of the job, ≈90% of what gets researchers
invested) — "if we cannot sync live data we are done" (user, 2026-06-12). Archive = durable
source-of-truth + historical loader; live sync = the current, researcher-facing path. Both stay. The
single source of truth removes the duplication worry, and the historical NI preload is **not** blocked
by the live-box build (it uses the proven archive pipeline).

**Multi-animal data model — SETTLED, do NOT reopen (NI-LIVE-08).** One acquisition = **one row** in the
raw-acquisition table; the per-animal id field is a **semicolon-separated list** (`subject_ids`); the
subject table has **one row per subject**; **no mapping/junction table.** That is the whole model. The
discovery script already parses the 1–4 animal list from the live-box subject folder. Nothing about
multi-animal is open.

**Two implementation items before the bulk NI preload (not the data model):**
1. **Canonical dedup identity = `(acq_datetime_full, modality)`** — make **both** the archive and the
   live ingest key on it so the same scan from either source reconciles and never double-ingests.
   ⚠️ Today archive-mode dedups on the `.tgz` basename (not the bare 14-digit timestamp), so this needs
   *aligning*. If **MILabs VECTor** is in scope (a second NI machine), add `instrument_model` to the key
   to avoid a same-second cross-machine collision.
2. **Archive `.tgz` for a multi-animal scan — confirm it exposes the animal list.** The live-box subject
   folder lists all animals (`0124_2-4-5-6`) and the script parses it; the archive `.tgz` name carries a
   single `short_sample` per the round-8 convention (and round 8 was single-animal). So when *preloading
   from the archive*, confirm a multi-animal scan's `.tgz` still recovers all animals — else the
   **live-box path is the authoritative source for the animal list**. A parsing detail, not the model.

**Later (user, 2026-06-12):** the `subject_id`→`subject_ids` rename can be done later (migrate with the
existing `migrate_registry_columns.py` pattern) — not a preload gate.

**Bottom line:** MRI + microscopy + **NI archive-mode** historical preload into the production NAS can
start now (existing tested pipeline), once the dedup key is aligned (#1) and the archive multi-animal
`.tgz` naming is confirmed (#2). The NI **live-box** sync is a required deliverable (forward project
data) that waits on Gate 0 + Step 2 — it is essential, not shelvable.

## Related
- `equipment/nuclear-imaging/live_machine_data_layout_and_sync_rules.md` — design of record.
- `equipment/historical_data_archives.md` — the source locations (NI/MRI/microscopy) + MRI creds.
- `tools/ni_live_discover.py` / `tools/test_ni_live_discover.py` — Step 1 + its test.
- `tasks/tasks.md` §0 — NI-live is in BACKLOG; the true-prod restart (purge → re-ingest) is the trigger.
- Memory: `[[ni_live_machine_layout]]`, `[[ni-historical-archives]]`.
