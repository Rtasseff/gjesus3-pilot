# Plan — ingest historical NI from the **active working space** `S:\gnuclear`

**Status:** **PHASES 0–2 DONE, PHASE 1 BUILT + TESTED, 2026-08-12.** Branch
`feat/ni-gnuclear-historical` (worktree `gjesus3-dev\ni-gnuclear-historical`, off **`main`
`5e9ab44`**). D-A/D-B/D-D/D-E/D-F are **decided — see §-2**; only **D-G** (§0.6) is open, and
it gates just the 655 held-back acquisitions. **Next gate: a scale run into
`J:\gjesus3-sandbox` (Phase 3) before any production batch.**
**High priority — we WILL do this in some capacity** (Ryan, 2026-06-25); deferred only so it doesn't
block the in-flight **documentation refactor** and to allow more review of the details. Do **not** drop
it. **Created:** 2026-06-25. **Author:** Data Office (Ryan + agent).
**Layout finding (durable):** [`equipment/nuclear-imaging/gnuclear_active_workspace_layout.md`](../equipment/nuclear-imaging/gnuclear_active_workspace_layout.md).
**Goal:** fill in *more* historical Nuclear-Imaging data by reading the messy active working space
`S:\gnuclear` (years → `Jesus\` → user folders), beyond the single `gnuclear2$\2025\Jesus\Irene`
slice already in production (132 acqs).

---

## §-2. WHERE IT ACTUALLY STANDS (2026-08-12 evening) — read this first

**The data is staged and the ingest is built and tested. Nothing has been written to
production.**

| | |
|---|---|
| **Snapshot** | `J:\gjesus3-data\staging\ni_gnuclear_20260812\` — **2,485 files / 286.3 GB**, pulled read-only off `S:\gnuclear`, **0 failures**, per-file sha256 in `_manifest.jsonl`, `--verify` re-read in progress |
| **Ready to ingest** | **1,526** acquisitions (2,312 total − 131 already in production − 655 held back) |
| **Proven** | full ingest end-to-end on a throwaway NAS: 3 acquisitions incl. a 4-frame dynamic PET → correct `.data/`, registry rows, packed multi-animal `subject_ids`, **live animal-DB hits**, project auto-create, hard links, provenance |
| **Idempotency** | re-run = 0 cases, exit 0, registry unchanged |
| **Tests** | `tools/test_ni_flat.py` **20/20**, plus all **19** pre-existing suites green |
| **✅ PHASE 3 PASSED** | **227/227** (`Itziar`, 2024+2025, 19.9 GB) into `J:\gjesus3-sandbox-ni20260812` — see below |
| **Not done** | **Phase 4 production, batch by batch — needs Ryan's explicit go-ahead** |

### Phase 3 scale run — PASSED 2026-08-12

Cohort `Itziar` (227 acquisitions, 19.9 GB, project `1123`, spanning 2024 **and** 2025 — so it
exercises the cross-year case).

| Check | Result |
|---|---|
| batch | **227 success / 0 failed / 0 ERROR** |
| registry | 227 rows, **227 distinct `acq_id`, 227 distinct `original_name`** — no duplicates |
| on disk | 227 acquisition folders + 227 `.data/`, box-compatible `recon<N>.dcm` naming |
| checksums | `checksum_present=Y` on all 227 |
| subjects | 70 rows in `registry_subjects.csv`; **1** acquisition flagged `source=unknown` (its path has no subject folder — flagged, not guessed) |
| project links | **227 hard links** under `AE-biomaGUNE-1123/raw_linked/` |
| pending queues | **none created** — every DB lookup and every hard link succeeded |
| `validate_registries` | **0 errors**, 227 warnings, all the intended `condition.is_control` null sentinel |
| idempotency | re-run → **0 cases, exit 0, still 227 rows** |

⚠️ **The shared `J:\gjesus3-sandbox` is unusable until migrated.** Its `registry_raw.csv` header
still carries `project_hint` (renamed to `project_id` on 2026-08-02), so
`registry.assert_header_compatible` refuses to append. It failed at the *first* case having
written nothing — the guard working correctly. This run used a clean
`J:\gjesus3-sandbox-ni20260812\` rather than mutating a sandbox another session may own.

### Decisions taken (Ryan, 2026-08-12: "stop deciding, move it forward")

- **D-A proceed** with `S:\gnuclear`. **D-D** everything under `…\Jesus\` in scope, no allow-list.
  **D-E** primary DICOM only; derivatives are a later pass.
- **D-B/D-F → per-recon**, conforming to what `feat/ni-live-hardening` landed. Explicitly **not**
  an override of that branch: where the shared grammar needed widening (`RAT63`), it was
  normalised in the new tool instead of editing `ni_live_discover.ANIMAL_RE`.
- **D-G is the only one left** and it is not blocking — see §0.6.

### The three new pieces

| File | Role |
|---|---|
| `tools/pull_ni_gnuclear.py` | read-only, resumable, checksummed staging of the DICOMs |
| `tools/ni_gnuclear_discover.py` | read-only review table (Phase 2 vetting) |
| `tools/ingest/ni_flat.py` + `copy_ni_flat` + `molecubes_ni_gnuclear.yaml` | the ingest path |

Surgery in shared code is deliberately tiny and opt-in: ~20 lines in `expand_batch` behind
`ni_gnuclear_flat`, one `elif` in the copy dispatch. **`_build_dedupe_index` is untouched** — the
canonical dedup comes from setting `original_name` to the acquisition key — so the merge conflict
surface against `feat/ni-live-hardening` is close to nil (§-1c).

---

## §-1. UNPARKED 2026-08-12 — read this before §0 (it supersedes "wait for the live branch")

This plan was parked behind `feat/ni-live-hardening`, which has been stuck at its **on-box
merge gate** for ~5 weeks and is now waiting on summer availability. **We stopped waiting.**
Four things established on 2026-08-12:

### (a) There was never a technical dependency

The live branch's open gate is **Gate 3, and it is Mac-only**: `registries/pending_links.csv`
carrying `ENOTSUP` / `darwin` rows, which *can only be produced on the NI Mac* because
`os.link` fails over its SMB mount. **This pull runs Windows `S:\gnuclear` → `J:\`, where hard
links are proven** (already noted in the 2026-08-06 update, point 3). Gates 1/2/4 all pass
locally. Nothing this plan needs is gated on a person returning from vacation.

Everything §1 lists as "reuse, do not rebuild" is **already on `main`**: `ingest_raw.py`'s
downstream half (registry, packed `subject_ids`, subjects table, project hard-link),
`ni_live_discover.parse_subject` (the live branch only added `resolve_root` — `parse_subject`
is untouched), `ingest/locking.py`, `ingest/csv_safe.py`.

### (b) Branch off `main`, NOT off `feat/ni-live-hardening`

`main` had moved **17 commits** past the live branch's last rebase base, and three of them
matter to a ~2,000-acquisition bulk ingest:

| Commit | Why it matters here |
|---|---|
| `83fa170` | **`project_id` became a semicolon-separated list** in the registry |
| `680b96a` | one project per acquisition; project folders are researcher-owned |
| `253ac0d` / `be932b9` | the Project Manager GUI merged (new `tools/manager/`) |

Phase 1 must be written against **that** registry schema. Branching off the live branch would
also have made this work un-mergeable until the box test happens — importing exactly the
dependency we set out to shed.

**This branch therefore does NOT contain** the live-sync hardening: `--live` mode, the
per-researcher corrections CSV, `fanout_ni_recons`, `NI_LIVE_RUNBOOK.md`. Do not assume they
are here. `tasks/RESUME_ni_live.md` is on `feat/ni-live-hardening` only.

### (c) One shared construction site — `tools/ingest/config.py`

Phase 1 item 4 (canonical dedup) edits `_build_dedupe_index` and `expand_batch`.
`feat/ni-live-hardening` **already** inserted `fanout_ni_recons` immediately after
`_build_dedupe_index` and edited `expand_batch` in two places. A textual conflict when the
second of the two branches merges is likely. It is small and resolvable — but **whoever merges
second owns it**, and neither branch should refactor that file beyond what it needs.

### (d) ⚠️ D-F — a design conflict the plan below does not know about (settle before Phase 1 code)

**§0.5 point 3 and Phase 1 item 1 below say: group all recon `.dcm` of one
`(timestamp, modality)` into ONE acquisition.** `feat/ni-live-hardening` landed the
**opposite** for live NI: **one acquisition per reconstruction**
(`config.fanout_ni_recons`, `original_name = <anchor>/recon_<idx>`, commit `fdc9448`,
docstring: *"decided 2026-06-25"*). The two decisions were made the same day and never saw
each other.

**Why this is not cosmetic.** The whole point of the canonical
`(acquisition_datetime, instrument)` key is that the *same physical scan* read from
`S:\gnuclear`, from `gnuclear2$`, or from the live box **reconciles to one row**. If live
fans out to N per-recon rows and this pull emits 1 grouped row, that key collapses N against
1 — it breaks the exact reconciliation it was built for.

**Recommendation: this pull follows the per-recon model.** The filename's `_0` / `_1` suffix
(`20240115133604_PET_OSEM_0.dcm`, `..._1.dcm`) **is** the reconstruction index — grouping and
fanning-out cost the same to write. Then:

- one acquisition per `(timestamp, modality, recon_idx)`, `.data/` holding that one `.dcm`;
- the canonical dedup key becomes `(acquisition_datetime, instrument, recon_idx)`;
- **this also resolves D-B** (§6) — the "MVP one-`.dcm`-per-scan shortcut" stops being a
  shortcut and becomes the wrong shape.

Open question inside D-F: the 132 archive rows already in production were ingested
*pre-per-recon* — confirm what their `recon_idx` is (probably absent) before relying on the
3-tuple key to dedup against them. **Verify in Phase 3 against a seeded copy, not in prod.**

---

> ## ⓘ UPDATE 2026-08-06 — what moved underneath this plan (read before resuming)
> A doc refactor + the NI live-hardening work landed while this was parked. **None of the
> analysis below is invalidated;** four pointers changed (source: `tasks/NOTE_to_historical_pull_work.md`):
> 1. **`tasks/tasks.md` no longer exists — archived to `tasks/archive/tasks.md`, which `CLAUDE.md`
>    now forbids editing.** Current entry point is **`tasks/STATUS.md`** (later improvements →
>    `tasks/BACKLOG.md`; dated history → `CHANGELOG.md`). The queued pointer for this work now
>    lives in `STATUS.md` §2, and Phase 4 below writes there, not to `tasks.md`.
> 2. **Two NI docs now postdate this plan** — read before re-planning:
>    `equipment/nuclear-imaging/live_machine_data_layout_and_sync_rules.md` (now backed by a
>    ~295k-line dump of the box's real paths) and
>    `equipment/nuclear-imaging/live_machine_remote_access.md` (reverse-SSH tunnel to the box;
>    workstation half verified, box half not yet run).
> 3. **The Mac hard-link wall does NOT affect this pull.** `os.link` → `ENOTSUP` on the NI Mac's
>    SMB mount, so the *live box* defers `raw_linked/` links to `registries/pending_links.csv`.
>    **This plan's route is Windows `S:\gnuclear` → `J:\`, where hard links are proven** (§1) —
>    just confirm that holds for the run machine.
> 4. **`--nas-root` has no test-vs-prod guard.** A dev run once pointed it at `J:\gjesus3-data`
>    and left two synthetic acqs in true production (removal list:
>    `tasks/ni_prod_testdata_removal.md`). For a bulk pull, **verify `--nas-root` before every
>    run** (Phase 3 → `J:\gjesus3-sandbox`, Phase 4 → `J:\gjesus3-data`).
>
> **One-line takeaway (REVISED after Phase 0).** `S:\gnuclear` is reachable and holds a **large
> net-new haul (~2,000 acquisitions)** — but its layout is **NOT** the box/archive structure the
> existing pipelines expect. It is a **flattened researcher analysis workspace**: loose single-recon
> DICOM *files* (`<14digit>_<MODALITY>_<recon>.dcm`) intermixed with analysis derivatives (`.nii`,
> `.voi`, `.mat`, PMOD `.xlsx`). There are **no `<14digit>_<MODALITY>/` anchor folders and no
> `recon_N/` subfolders**, so neither `molecubes_ni_live.yaml` nor `molecubes_ni.yaml` fits as-is
> (both rely on `copy_ni_acquisition()`, which requires `recon_<idx>/`). **The real work is a new
> file-as-primary DICOM ingest path** for this flat layout — plus the canonical dedup fix. See
> **§0.5 PHASE 0 RESULTS** below; the assumptions in §1–§4 are updated there.

---

## 0. Context & the strategic question (read first)

`equipment/historical_data_archives.md` records three NI tiers, and the **DECIDED 2026-06-12** stance
is **"source of truth = the ARCHIVE"** (`gnuclear2$` now, `gnuclear3` later), with `S:\gnuclear`
flagged **"likely redundant."** So before any bytes move, settle the *why*:

- **`gnuclear3`** (the standardized long-term store, the intended source of truth) — **access not yet
  granted.** Blocked.
- **`gnuclear2$`** (intermediate `.tgz` archive) — reachable, proven pipeline (round 8), but only
  contains **what has been archived**. Today that gave us only `2025\Jesus\Irene` (132 acqs). Coverage
  of other years/users is **unconfirmed**.
- **`S:\gnuclear`** (active working space) — reachable **today**, and (per the user) laid out
  `S:\gnuclear\<YYYY>\Jesus\<user>\…`. Potentially the **most complete reachable source right now**
  (more years, more users than the one archived slice).

**Reconciliation (the position this plan takes):** using `S:\gnuclear` does **not** overturn the
source-of-truth decision. The archive (`gnuclear2$`/`gnuclear3`) remains the durable store of original
bytes — we still don't double-archive. `S:\gnuclear` is used only as a **convenient read source** to
populate gjesus3's research-facing working layer *now*, while `gnuclear3` access is pending. As long as
dedup is canonical (§Phase 1), an acq read from `S:\gnuclear` and the same acq later confirmed in
`gnuclear3` **reconcile to one row**. Provenance (`ingest_config` + `notes`) records the read source.

→ **Decision D-A for the user:** proceed reading from `S:\gnuclear` now, OR first chase `gnuclear3`
access / a wider `gnuclear2$` pull? (Recommendation: **proceed with `S:\gnuclear`** for reach-today
coverage, *and* still request `gnuclear3` access in parallel — they're not mutually exclusive.)

---

## 0.5 PHASE 0 RESULTS (2026-06-25) — read-only inventory, reality check

Ran read-only from the workstation (`S:\` = `/s` in Git Bash; PowerShell is deny-ruled). **Wrote nothing.**

**Reachability & shape.** `S:\gnuclear` is reachable. Years **2022–2026** each contain a **`Jesus\`**
folder. User folders under `…\Jesus\`:

| Year | User folders under `Jesus\` |
|---|---|
| 2022 | `MOLECUBES\` (an extra level → then `211217`, `Ana`, `IAZ_MJ`, `Libe`, `Marina`) |
| 2023 | `Aitor_Herraiz`, `Ermal`, `Irati`, `Kepa`, `Libe`, `MJ`, `Marina` (+ loose `*_CT_ISRA_0.dcm` at the `Jesus\` root) |
| 2024 | `Alba`, `CarlottaS`, `Claire`, `Ermal`, `Irati`, `Irene`, `Itziar`, `MJ`, `Marina` |
| 2025 | `Carlotta`, `Claudia`, `Irene`, `Itziar` |
| 2026 | `Ekine`, `Itziar`, `Jordi`, `Ryan`, `irene` |

**⛔ The decisive finding — layout is NOT box/archive-shaped.** A subject folder
(e.g. `…/Irene/0525/251028_FDG/0525_m1/`) directly contains **loose files**:
reconstructed DICOMs `20251028101344_PET_OSEM_0.dcm` + `20251028103111_CT_ISRA_0.dcm`, **plus**
analysis derivatives `0525_m1_fdg.nii`, `..._SEGM.nii`, `.mat`, PMOD `ID 1_..._suv.xlsx`, `.voi`,
`protocol.txt`, `reconparams.txt`, `monitoring.csv`. Verified across all of 2024+2025 `Jesus\`:
**zero `<14digit>_<MODALITY>/` anchor directories, zero `recon_N/` subfolders, zero `.tgz`.** This is
the researcher's **curated working/analysis space** — one chosen reconstruction per modality,
flattened, intermixed with downstream outputs and even other animals' files (an `m2` SEGM sits in the
`m1` folder). It is **NOT** a copy of the acquisition-folder tree the box/archive expose.

**Filename grammar (consistent):** `^<14-digit timestamp>_<MODALITY>_<recon>(_<idx>)?(_frameMULTI_iter30)?.dcm`
— e.g. `20240115133604_PET_OSEM_0.dcm`, `20240115133604_PET_OSEM_1.dcm` (two recons, same scan),
`..._frameMULTI_iter30.dcm` (dynamic PET), `..._CT_ISRA_0.dcm`. The canonical
`(acq_datetime_full, modality)` is recoverable **from each filename**. Only **PET + CT** seen (no
SPECT/OI in the 2024+2025 sample).

**Volume (distinct `(timestamp, modality)` acquisitions under `Jesus\`):**

| Year | Distinct acqs | Note |
|---|---|---|
| 2022 | 449 | net-new |
| 2023 | 449 | net-new |
| 2024 | 483 | net-new |
| 2025 | 551 | **~132 overlap** the loaded `gnuclear2$` Irene/0525+1207 slice; rest (Carlotta/Claudia/Itziar) net-new |
| 2026 | 192 | net-new |
| **Total** | **~2,124** | **vs 132 currently in production → ≈ 2,000 net-new reachable now** |

(Raw `.dcm` counts are higher — 699 CT + 617 PET in 2024+25 alone — because one scan keeps multiple
recon files; the distinct-acquisition count above already collapses them.)

### What this means for the plan
1. **The existing live/archive NI pipeline does NOT fit.** Both need `recon_N/` via
   `copy_ni_acquisition()`. So the "reuse `molecubes_ni_live.yaml`, near-zero new code" premise is
   **wrong for this source.**
2. **A new file-as-primary DICOM ingest path is the real work** (see revised §4): discover `*.dcm` by
   the filename anchor → **group by `(timestamp, modality)`** into one acquisition (its recon `.dcm`s
   go to `<ACQ-ID>.data/`) → subject from the containing folder (`parse_subject` still applies) →
   light metadata from the DICOM header + co-located `protocol.txt`/`reconparams.txt`. New
   `copy_strategy` + extractor + per-instrument template; **everything downstream** (registry, packed
   `subject_ids`, subjects table, project link, locking, csv_safe) **reuses unchanged.**
3. **Canonical `(timestamp, modality)` dedup is now doubly required** — it both (a) reconciles
   cross-source with the 132 archive rows AND (b) collapses the multiple recon `.dcm` of one scan into
   one acquisition (if we instead keyed per-file it would mis-split, and the existing `(acq_date,
   original_name)` key would treat each recon file as its own acq).
4. **Fidelity is "working-layer", not archival — and that is on-role.** Per `13_GJESUS3_ROLE`, gjesus3
   wants the analysis-ready reconstruction, not raw bytes; the flat `.dcm` IS that. The platform
   archive (`gnuclear2$`/`gnuclear3`) stays the full source of truth (all recons + raw event data).
   Provenance records the read source = `S:\gnuclear`.
5. **Two new questions surfaced:**
   - **Derivatives (`.nii`/`.voi`/PMOD `.xlsx`/`.mat`/segmentations)** co-located with each scan — capture
     them into the **project workspace** (research output, belongs in projects per `13_GJESUS3_ROLE`),
     or ignore for now and ingest only the primary DICOM? (Recommend: primary DICOM first; derivatives a
     fast-follow.)
   - **User-folder roster** under `Jesus\` is **capitalized and broader** than the box roster
     (`Irene/Itziar/Ermal/Claudia/Carlotta/CarlottaS/Ekine/Aitor_Herraiz/MJ/Alba/Claire/…`). Some
     (`Irati`, `Marina`, `Libe`, `Kepa`) the live-box doc §2A listed **out-of-MFB** — yet here they sit
     under `Jesus\`. Confirm scope: is everything under `…\Jesus\` in-scope by construction, or do we
     still allow-list? Also loose `.dcm` at the 2023 `Jesus\` root + the 2022 extra `MOLECUBES\` level
     need handling (variable depth — discover by recursive filename match, not fixed depth).

---

## 0.6 PHASE 0 RE-RUN + PHASE 2 RESULTS (2026-08-12) — measured, not estimated

Re-walked the whole share and ran the new review tool over every acquisition. **The answer to
"can we get this data" is YES.** Numbers below are measured against the live share on
2026-08-12, and they *confirm* §0.5's headline (2,124 distinct scans) while correcting three
of its structural claims.

### Volume (final)

| | |
|---|---|
| `.dcm` under `<year>/Jesus/` | **2,700** |
| matching the reconstruction grammar | **2,690** (the 10 rejects are derivatives — `ATTMAP`, `CT_PET_coreg`, `-suv`) |
| distinct **scans** `(timestamp, modality)` | **2,124** — exactly §0.5's figure, independently reproduced |
| distinct **acquisitions** `(timestamp, modality, algo, recon_idx)` | **2,312** ← the per-recon unit (D-F) |
| files to stage after dedup | **2,485** |
| bytes | **286.3 GB** |
| already in production | **132 NI rows, 131 of which overlap** — gnuclear is a near-superset |

### Three corrections to §0.5

1. **`recon_N/` folders DO exist here.** §0.5 concluded "zero anchor directories, zero
   `recon_N/`" from a 2024+2025 sample. 2022–2023 contain 13 box-shaped
   `<14digit>_<MOD>/recon_N/frame_N/iter_30/` trees (135 files). The flat layout is still
   overwhelmingly dominant (2,565 of 2,700), and **one rule covers both**: discover by
   *filename*, not by folder shape.
2. **The same reconstruction is copied into many folders** — 47 acquisitions appear in more
   than one directory, one of them in **48**. Keying identity on the directory would have
   produced ~370 duplicate rows *from this source alone*, before any cross-source concern.
   Six acquisitions are duplicated across two different **year** folders, so per-year batching
   cannot dedup independently — identity must be global and directory-independent.
3. **`frameMULTI` must not be skipped unconditionally.** The box copy always drops those
   bundles because per-frame DICOMs sit beside them. Here **63 reconstructions have a
   `frameMULTI` file and nothing else** — a blanket skip would have silently lost that dynamic
   PET. Rule adopted: drop the bundle only when per-frame siblings exist (9 dropped, 65 kept).

### Phase 2 — how well does the messy tree parse?

`tools/ni_gnuclear_discover.py` (read-only) over all 2,312:

| Outcome | Count | Read |
|---|---|---|
| **project code resolved automatically** | **1,657 (72%)** | ready to ingest |
| no project code in the path | **655 (28%)** | needs input — see below |
| `species-unknown` | 1,802 | **benign** — folder says `15`, not `m15`; the facility DB carries species |
| `project<-parent` | 1,140 | **benign** — this is the designed recovery path, not a defect |
| `unparsed` token | 307 | descriptive folder words (`68Ga`, `Gated`, `highres`) |
| `no-animals` | 167 | no animal number in the subject folder |
| date disagreement | 13 | genuine typed-date-vs-machine-date mismatches |
| loose at `<year>/Jesus/` root | 3 | no researcher folder at all |

**The 655 are not malformed.** Those researchers filed by **study/tracer name instead of
animal-protocol code** — `FDG`, `Starget`, `cancer`, `metalak`, `ionp`, `Flurpiridaz`, `FTHA`,
`fapi`, `nanoclusters`, `Dieta cetogenica` — across **73 `(researcher, series)` groups**, and
**75% of them still parse their animal numbers**. One mapping line per group closes it; the top
12 groups alone cover 55%.

→ **D-G (new, blocks the second half only).** AE protocol codes are **regulatory identifiers
and must not be invented**, so this needs real values from the researchers or the Data Office.
Ingest the **1,657** now and hold the 655 pending that table — nothing about ingesting the
clean set makes the rest harder later, because dedup is on the machine timestamp.

---

## 1. What we already have (reuse, do not rebuild)

| Capability | Where | Note |
|---|---|---|
| Read-only **discovery dry-run** (anchor walk + subject parse + review table) | `tools/ni_live_discover.py` | works against a live tree (`--root`) or a listing (`--from-listing`); handles variable depth + the §3A messy subject grammar; **writes nothing** |
| **Live-box ingest** ​— ⚠️ **does NOT fit this source** (see §0.5): it expects `<anchor>/recon_N/` folders; `S:\gnuclear` is flat `.dcm`. Reuse its *downstream* only. | `tools/ingest_raw.py` + `molecubes_ni_live.yaml` | the **discovery + copy** front half must be replaced (Phase 1); registry / packed `subject_ids` / `subjects_table` / project hard-link / `subject_parse` / per-animal DB lookup all **reuse unchanged** |
| Registry integrity | `tools/ingest/{locking,csv_safe}.py` | lock + durable ACQ-ID reservation + BOM/newline-safe appends |
| Subjects table writer | `tools/ingest/subjects_table.py` | upsert, one row per animal |
| **Hard-links proven on the J:\ SMB mount** (Windows) | round-8 / MRI ingests | so `S:\gnuclear`→`J:\` linking needs **no** Gate-0 (that gate is Mac-only) |

**The live path is design-of-record in** `equipment/nuclear-imaging/live_machine_data_layout_and_sync_rules.md`
(§2A roster, §3A subject grammar, §3B one-entry-per-scan, §4 R1–R10 rules). `S:\gnuclear` *is* the
tree that doc was reverse-engineered from (its evidence snapshot
`S:\gnuclear\2026\Jesus\Ryan\datapath.txt` is a dump of the box `/data/` root).

---

## 2. Unknowns / feasibility gates (the "if")

| # | Unknown | Why it matters | Status |
|---|---|---|---|
| **U1** | Actual on-disk layout under `…\Jesus\<user>\` | Decides the pipeline | ✅ **RESOLVED (§0.5): flat single-recon `.dcm` files**, no anchor folders / no `recon_N` / no `.tgz` → **neither existing pipeline fits**; new file-as-primary DICOM path (Phase 1) |
| **U2** | User-folder **naming** under `Jesus\` | discovery roster + `researcher`/`operator` fields | ✅ **RESOLVED (§0.5): capitalized + broader** than the box roster; see the year×user table |
| **U3** | **Overlap** with the 132 loaded from `gnuclear2$` | dedup miss → **duplicate rows** | ✅ confirmed risk (`config.py:163`) + **quantified** (§0.5: ~132 in 2025/Irene overlap) → Phase 1 canonical dedup |
| **U4** | **Coverage / volume** | sizes the opportunity | ✅ **RESOLVED (§0.5): ~2,124 distinct acqs, ≈2,000 net-new** |
| **U5** | Path **depth variability** (2022 `MOLECUBES\` level, loose-at-root `.dcm`, varying subject depth) | a fixed-depth parse would miss/misalign | ✅ confirmed present → Phase 1 discovers by **recursive filename match**, not fixed depth; vet in Phase 2 |

---

## 3. The one real code change (Phase 1) — canonical cross-source dedup

**Problem (confirmed in code).** `tools/ingest/config.py::_build_dedupe_index` builds keys from
`(acq_date, original_name)`. `original_name` = path relative to `staging_dir`:
- archive-mode rows (the 132 in production): `original_name` = the `.tgz` folder basename
  (e.g. `PET_m14_…`).
- a `S:\gnuclear` live read: `original_name` = a directory relpath (e.g. `0525/251029/0525_m14/2025…_PET`).

Same physical scan, **different `original_name`** → dedup **misses** → **duplicate ingest**.

**Fix (small, but in shared registry-adjacent code → test hard).** Add a **second, canonical** dedup
key `(acquisition_datetime, instrument)` (the bare machine timestamp + modality is globally unique per
Molecubes scan) and skip if **either** key matches. Both fields are already registry columns. This:
- makes `S:\gnuclear` ingest a **safe no-op** for anything already loaded from `gnuclear2$`;
- future-proofs the live-box ↔ archive **reconciliation** (handoff item #1 — same fix);
- if MILabs **VECTor** is ever in scope, extend the key with `instrument_model` (same-second
  cross-machine collision guard).

**Alternative if we want zero code change first:** scope Phase 4 to the **gap only** (exclude
`2025\Jesus\irene` series 0525/1207) using the Phase-0 inventory. Workable, but fragile and doesn't
help the live-box future. **Recommendation: do the canonical-dedup fix** — it's the blessed item and
removes a whole class of footguns.

→ **Decision D-B for the user:** canonical-dedup fix (recommended) vs. scope-around-overlap-only.

---

## 4. Phased plan

### Phase 0 — Read-only inventory + decision ✅ DONE 2026-06-25 (see §0.5)
Reachability, year×user matrix, layout verdict (flat single-recon DICOMs), filename grammar, and
volume (~2,124 distinct acqs, ≈2,000 net-new) are captured in §0.5. **Go/No-Go (D-A, D-B, D-C) is now
the open decision.** Remaining read-only confirmations folded into Phase 2.

### Phase 1 — Build the flat-DICOM ingest path (the real work; code + tests, no ingest)
This source needs a **new file-as-primary DICOM path**. Concretely:
1. **Discovery that groups files.** New discovery for `acquisition_layout: file`-of-DICOM that walks
   the user subtree recursively, matches `*.dcm` on the filename anchor
   `^(?P<acq_datetime_full>\d{14})_(?P<modality>PET|CT|SPECT|OI)_`, and **groups all recon `.dcm` of
   one `(timestamp, modality)` into a single acquisition** (its `.data/` holds the 1–N recon files).
   The containing folder is the subject folder → reuse `ni_live_discover.parse_subject` for project +
   1–4 animals. Variable depth + the 2022 `MOLECUBES\` level + loose-at-root files → match by
   recursive filename, never fixed depth.
2. **New `copy_strategy: ni_molecubes_flat`** — copy the grouped recon `.dcm`s into `<ACQ-ID>.data/`
   (mirror the box naming `recon<X>.dcm` / `recon<X>_frame…`), checksum, drop everything else.
3. **Light metadata extractor** — DICOM header (incl. `StudyInstanceUID`/`SeriesInstanceUID`/
   `SOPInstanceUID`) + co-located `protocol.txt`/`reconparams.txt` → the `ni:` sidecar block. (Thinner
   than archive mode — no XML aux / raw event data here; that's fine for the working layer.)
4. **Canonical `(acquisition_datetime, instrument)` dedup** in `_build_dedupe_index` + the
   `expand_batch` skip — keep the existing `(acq_date, original_name)` key too. **Required** both to
   reconcile with the 132 archive rows and to keep the per-file grouping from re-splitting on re-run.
5. **New template** `tools/templates/instruments/molecubes_ni_gnuclear.yaml` (file-as-primary; subject
   from path; provenance note "read source = S:\\gnuclear").
6. **Tests** (`tools/test_*`): grouping (2 recon files → 1 acq), canonical dedup (same scan from two
   `original_name`s → 1 row; archive row + gnuclear row → 1 row), multi-animal subject parse, the
   empty/partial guard. Reuse the `ni_live_discover` parser tests.

*MVP shortcut if speed matters:* ingest **one `.dcm` per `(timestamp, modality)`** (pick the primary
recon, e.g. `_0`) and defer multi-recon grouping — smaller build, but diverges from the box's
one-acq-many-recons shape. Decide in D-B.

### Phase 2 — Per-(year,user) discovery vetting (read-only review tables)
- Point the new discovery at each in-scope `…\Jesus\<user>` in **dry-run**, emit the review table
  (subject parse, project, 1–4 animals, would-be facility key, flags), **human-review** the flagged
  rows. Confirm the **scope question** (everything under `Jesus\` vs allow-list; `Irati`/`Marina`/
  `Libe`/`Kepa`/`MJ` in or out) and the capitalized folder names.

### Phase 3 — Vetted one-shot to the **sandbox** (`J:\gjesus3-sandbox`)
- Copy the new template → `tools/configs/ni_gnuclear_<YYYY>_<user>.yaml`; edit `staging_dir`
  (= `S:\gnuclear\<YYYY>\Jesus\<user>`), `researcher`, `operator`, provenance `notes`.
- `ingest_raw.py --config … --nas-root J:/gjesus3-sandbox` → verify against §0.5 counts; **idempotent
  re-run = no-op**; empty/partial guard; packed `subject_ids` + `registry_subjects.csv` correct;
  project hard-links land; **no duplicates vs a seeded copy of the production 132** (the canonical-dedup
  fix in action). Start with one clean net-new cohort (D-C).

### Phase 4 — Production ingest, batch by batch
- Run per `<YYYY>\<user>` against `J:\gjesus3-data`, smallest/cleanest net-new cohort first, reviewing
  the registry delta after each batch before the next. Leave the 2025/Irene overlap for last (dedup
  proves itself there).
- Record each batch's config in `ingest_config` (automatic). Update `tasks/STATUS.md` §2 +
  `equipment/historical_data_archives.md` (mark `S:\gnuclear` *partially ingested*, with coverage).
- **(Optional fast-follow)** capture the co-located analysis derivatives into the matching project
  workspace (per `13_GJESUS3_ROLE` derivatives-in-projects) — separate pass, not raw ingest.

---

## 5. Risks & mitigations

| Risk | Mitigation |
|---|---|
| **Duplicate rows** vs the 132 archived acqs (U3) | Phase 1 canonical dedup **and** Phase-0 overlap quantification; sandbox-verify against a seeded copy before prod |
| `S:\gnuclear` is **messy/incomplete** (the doc calls it "likely redundant") | Read-only Phase 0 first; treat as a *read source*, not source of truth; archive remains durable store |
| **Depth variability** misaligns positional `path_parse` (U5) | Discovery tool is depth-robust → vet with it first; scope out depth-6 pockets; rely on flags, never silent guesses |
| **Multi-animal** scans | Already handled (NI-LIVE-08): `subject_parse` packs 1–4 `subject_ids`; `S:\gnuclear` (uncompressed) *exposes the full animal list*, so it's actually **better** than the round-8 `.tgz` here |
| **DB lag / misses** | Designed-for: misses queue to `pending_subject_metadata.csv`; `recover_subject_metadata.py` back-fills; ingest still succeeds |
| **Non-Jesus data** | Scoping by the `\Jesus\` level already restricts to the MFB group — cleaner than the box (which needed a roster allow-list) |
| `S:\` not reachable from the ingest machine | Confirm in Phase 0 step 1 before anything else |

---

## 6. Open decisions for the user (post-Phase-0)
- **D-A — proceed?** `S:\gnuclear` has ≈2,000 net-new acqs reachable now, but as **curated
  working-layer DICOMs** (one recon, no raw, thinner metadata), needing a **new ingest path** (Phase 1).
  Worth building vs. wait on `gnuclear3` access (full fidelity, blocked) / a wider `gnuclear2$` pull?
  *Recommendation: build it* — it's on-role for the working layer, the archive stays source of truth,
  and ~2,000 acqs is the bulk of the group's history; pursue `gnuclear3` in parallel for the durable copy.
- **D-B — full grouping vs MVP?** Group all recon `.dcm` of a scan into one acquisition (matches the box;
  recommended) **vs** the MVP one-`.dcm`-per-`(timestamp,modality)` shortcut. Either way the canonical
  dedup is required. ⚠️ **Largely superseded by D-F** — "matches the box" is no longer true; the box
  path now fans out one acquisition per reconstruction.
- **D-F — grouping vs per-recon (NEW 2026-08-12, blocks Phase 1).** `feat/ni-live-hardening`
  landed **one acquisition per reconstruction** for live NI, contradicting §0.5 pt 3 / Phase 1 pt 1
  here. Mixed granularity breaks the canonical dedup key that is supposed to reconcile the two
  sources. *Recommendation: follow per-recon; key on `(acquisition_datetime, instrument, recon_idx)`.*
  Full reasoning in **§-1(d)**.
- **D-C — first cohort?** Recommend one clean **net-new** year/user (e.g. `2024\Jesus\Ermal` or
  `2025\Jesus\Claudia`) to prove value without touching the 2025/Irene overlap.
- **D-D — scope rule?** Everything under `…\Jesus\` in-scope by construction, or keep an allow-list
  (and are `Irati`/`Marina`/`Libe`/`Kepa`/`MJ` MFB)? Drives the discovery roster.
- **D-E — derivatives?** Capture co-located `.nii`/`.voi`/PMOD `.xlsx`/`.mat` into the project workspace
  (fast-follow), or primary DICOM only for now? *Recommendation: primary DICOM first.*

## 7. Related
- `equipment/historical_data_archives.md` — the source-location catalogue (S:\gnuclear is here).
- `equipment/nuclear-imaging/live_machine_data_layout_and_sync_rules.md` — design of record (built
  from an `S:\gnuclear` snapshot).
- `tasks/ni_live_sync_handoff.md` — the live-box handoff (note: its "Step 2 not built" status is
  **stale** — live ingest landed 2026-06-20; see `tasks/STATUS.md` §2).
- `tools/ni_live_discover.py`, `tools/templates/instruments/molecubes_ni_live.yaml`,
  `tools/ingest/config.py::_build_dedupe_index`.
