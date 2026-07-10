# Architecture & Code Review — gjesus3 RDM

> **Immutable, point-in-time snapshot — do not edit.** This file records the
> system as it stood at one commit. Corrections or follow-through belong in
> [`../BACKLOG.md`](../BACKLOG.md) (actionable items) and the numbered specs
> (once a finding becomes a decision) — not here. A later review supersedes this
> one by adding a new dated file, never by rewriting this one.

| | |
|---|---|
| **Date** | 2026-07-08 |
| **Commit reviewed** | `a6de67d` (branch `main`) — *docs(infra): correct + source the DR cost table (§5.4)* |
| **Reviewer** | Claude (Opus), Claude Code session `main-opus-code-review` |
| **Scope** | Design specs `mfb-rdm-docs/00–13` + the `tools/` code surface (~21,400 LOC Python across 81 files; ~12,500 lines of Markdown across 57 files). Live state at review time: ~13,555 acquisitions, ~715 subjects, ~50 projects, one QNAP. |
| **Method** | Four parallel analysis passes (sprawl census, latent-bug hunt, spec↔code divergence, scaling/over-engineering) plus direct reading of the concurrency, commit-point, registry-schema, and infrastructure code/docs. The two starred HIGH bugs (§3.1) were independently confirmed against the code; the remaining code findings are from careful static analysis and warrant a verification pass before fixing. |
| **Triggered by** | Owner's two stated concerns: (1) over-engineering causing sprawl/divergence; (2) latent errors not yet surfaced — at either the design or code level. |

---

## 1. Bottom line

The review **partly rebuts the over-engineering worry and confirms the latent-error worry.**

- **The system is not broadly over-engineered.** For the real problem — 6 instruments across two structurally different data paradigms (optical `.czi` vs. DICOM-family), preclinical animal data that needs ARRIVE-grade metadata to be publishable, a traceability mandate, a "migrate to XNAT/OMERO later" constraint, and a no-server SMB-only environment — most of the complexity is *essential*. The core `ingest → registry → enrichment → finder` path is proportionate and unusually well-factored.
- **Sprawl is real but at the edges** — spent migration scripts and a heavy documentation-governance apparatus, not the pipeline.
- **The "divergence" feared in the schema is not present.** The load-bearing registry-schema mirror is fully consistent across spec, code, and the live NAS header. The real divergence is *documentation lag*.
- **The latent errors are real and concentrated** in the concurrent-write and partial-failure paths.
- **The single biggest risk is infrastructure, not code:** one NAS, RAID 5 on 20 TB drives, no off-array copy, in true production.

---

## 2. Concern 1 — over-engineering, sprawl, divergence

Three genuinely different things; only one warrants real effort.

### 2.1 Edge sprawl (real, low-risk to clean)

~9–10 **spent one-off migration scripts sit un-marked in `tools/` top-level**, beside genuinely-recurring tools — the `backfill_*` family, the `relink_*` family, `migrate_registry_columns.py`, `gen_microscopy_bestguess_configs.py`. Each already ran and is logged *DONE with concrete counts* in `BACKLOG.md`, but nothing marks them spent, so a newcomer can't tell live from dead.

More insidious: **duplication of correctness-critical plumbing.** The block "acquire registry lock → read all rows → rewrite via `DictWriter(REGISTRY_FIELDS)` → `os.replace`" exists **verbatim in 3–4 places** (`backfill_microscopy_anatomy.py:137`, `backfill_mri_anatomy.py:210`, `backfill_microscopy_bestguess.py:231`, plus a variant in `migrate_registry_columns.py`). Each is an independent copy that can drift from `REGISTRY_FIELDS` on its own. Root cause: `tools/ingest/` exposes *domain* logic but exposes **no shared I/O tier** — no atomic sidecar read/write/verify, no registry-rewrite-under-lock, no canonical-path→disk helper, no provenance-row builder. So every one-off re-copies that plumbing. `backfill_subjects_table.py` proves it's avoidable — it routes all writes through `ingest.subjects_table` with no parallel write path.

Duplication clusters found: (A) anatomy/enrichment back-fills — 3 near-identical clones; (B) the relink family — 3 scripts each reimplementing the projects/registry CSV loader, the canonical→disk resolver, and the 11-key provenance row; (C) the extract family — 2 scripts sharing the whole idempotent-extract skeleton. The smallest recurring copy (`_sidecar_path`) appears ~5×.

Tests: 13 hand-rolled, un-collectable `test_*.py` scattered across three directories (no `tests/`, no `pytest`), including date-stamped regression files (`test_review_fixes_2026_06.py`) that will keep accreting. Fine at 10 people; friction as it grows.

**Cleanup (low-risk):** archive the spent one-offs; lift ~5 shared helpers (atomic sidecar write+verify, registry-rewrite-under-lock, canonical→path, provenance-row builder, idempotent-extract) into `ingest/`. That collapses clusters A–C.

### 2.2 The documentation-governance apparatus (the heaviest over-engineering)

This is where "over-engineering creating sprawl" is most real — and it's in the *docs*, not the code. ~12,500 lines of Markdown across 57 files (14 numbered specs ≈ 5,900 lines) against ~21,400 lines of Python. The **integrity-mirror rule** (06↔`resolver`/`registry`, 08↔the builders, 09↔`EXPOSED_FIELDS`, 10↔templates) means every schema change must be *manually mirrored* across spec + code + templates + CLI ref + the index. That maintenance tax is real, ongoing, and falls on one person.

The discipline is admirable and it's *why* the schema mirror is currently consistent — but it's a lot of ceremony for a single-maintainer system, and it's the mechanism by which future divergence creeps in the moment attention lapses. Right-sizing (not tearing down): reduce the number of authoritative surfaces — the schema is authored in exactly one place (`REGISTRY_FIELDS`), and the spec table could be *generated from* it rather than hand-mirrored.

### 2.3 Speculative specs and wrong-time-binding (park these)

- **`EM/` as a first-class ecosystem** — zero data, no builder, "may never." A third of the core taxonomy carrying nothing. Demote to "add when it arrives."
- **Curated-datasets** — a complete registry spec (`12_CURATED_DATASETS.md`, `registry_datasets.csv` schema, `DS-TYPE-NNNN` IDs) for a feature that is `❓ EVALUATING` with zero instances. Park it.
- **Lightweight mode + `backfill_metadata`** — a whole second ingest mode plus its upgrade tool, both `🕗 PLANNED`, possibly obsoleted now that the GUI + non-blocking enrichment exist. Don't build until a real constrained-deposit case appears.
- **Enrichment taken *inline at ingest*** — the *feature* is core value (it makes the data publishable), but binding it at ingest time forced ~1,700 LOC of deferred-recovery machinery (`pending.py`, the `pending-db` sentinel, `recover_subject_metadata.py`, the pending queue) that exists **solely to paper over the animal-facility DB being unreachable at ingest**. A post-ingest batch enrichment pass, run from the data-office machine that always has DB access, would delete most of that subsystem. Right feature, wrong time-of-binding. (See design finding §3.2.3.)

### 2.4 Divergence — the schema holds; docs lag

The load-bearing mirror is in good shape. Verified consistent across all four surfaces (spec §2.2 table, spec §2.5 example, `registry.py:REGISTRY_FIELDS`, and the **live NAS header**): 28 columns, identical order, no append-order bug (`append_row` pins on-disk order to `REGISTRY_FIELDS` via `DictWriter` + the `assert_header_compatible` guard). Mirrors 08 (sidecar shape) and 09 (`EXPOSED_FIELDS`: 21 CZI / 22 MRI / 15 NI) also pass on content.

The only real drift is documentation lag:

- **`10_TOOLS.md §2.1` still documents the pre-rename `operator:` inside the `registry:` block** (≈ lines 450, 502, 568), which `resolver.py` now rejects with a hard `ResolverError`. An operator copying those examples verbatim hits a wall. **Highest-impact drift** — worth fixing promptly. The doc is even internally inconsistent (the AxioScan/Cell examples were updated; two others weren't).
- **Undocumented multi-animal `subjects:[]` sidecar key** (`metadata_sidecar.py:87`) that `08_METADATA` §4.3 doesn't list.
- **Undocumented `auto_discover.subject_parse:` block** exercised by `molecubes_ni_live.yaml`.
- Minor: `rebuild_baseline/registry_raw.csv` is a stale 24-column pre-purge header — worth a note so it isn't mistaken for current.

All are docs catching up to code, not code contradicting a decided schema. No code change needed for the divergence findings — only doc edits.

---

## 3. Concern 2 — latent errors

### 3.1 Code-level (concurrent-write & partial-failure paths)

Ranked most-severe first. ★ = independently confirmed against the code during this review; the rest warrant a verification pass before fixing.

| # | Sev | Bug | Failure scenario | Location |
|---|-----|-----|------------------|----------|
| 1 ★ | HIGH | **Dedup is a pre-lock snapshot** | Two operators (or a double-launched batch) run the same config within a minute; both build the dedup index from the same registry state, both see everything as new → **every acquisition lands twice** under two ACQ-IDs. The lock serializes the writes but never re-checks the dedup decision. | `config.py:367` + `:610` vs lock at `ingest_raw.py:809` |
| 2 | HIGH | **`pending.py` rewrites the recovery queue non-atomically, unlocked** | Uses `open(path,"w")` (truncate-in-place), unlike sibling `pending_dicom.py` which does temp+`os.replace`. A crash mid-write **wipes the entire recovery queue**; concurrent DB-misses lose-update each other. This is the only record that an animal still needs metadata recovery. | `pending.py:70-76`, reached outside the lock at Step 8.4 |
| 3 | HIGH | **Post-copy early returns leave orphan folders the rollback never touches** | A transient SMB glitch trips verify *after* the folder is copied but *before* the `try/finally` rollback window opens; the half-copied folder lingers forever, invisible to dedup (no registry row). This already happened once (the 178-microscopy no-link cleanup). | returns at `ingest_raw.py:986/1069/1102/1139`, before `try` at `:1148` |
| 4 ★ | MED | **`committed=True` set *after* the lock block closes** | A Ctrl-C in the gap between lock release (`:1324`) and `committed=True` (`:1325`) makes `finally` roll back an acquisition **whose registry row was already written** — a dangling pointer to deleted data. Move the flag inside the locked section. | `ingest_raw.py:1305-1325` |
| 5 | MED | **Hard-link failure is swallowed → ingest "succeeds" with a phantom link** | Cross-volume, permissions, Windows `MAX_PATH`, or the case-collision (#6) → WARN + continue to DONE. Registry says `project_hint=PROJ-X`; project folder has nothing. This is the recurring class — `relink_projects.py --create-missing` exists *because* this happened. | `ingest_raw.py:1453-1456` |
| 6 | MED | **Case-only-different link names silently dropped** | On the case-insensitive NAS, `os.path.exists("Heart_01")` returns true when `heart_01` exists; the second link is skipped with no error. | `linker.py:192,197` |
| 7 | MED | **Lock timeout discards verified work** | A 60 s `LockTimeout` at the append (inside the `try`) rolls back a fully-copied multi-GB acquisition as a "failure"; at allocation (outside any `try`) it aborts the whole remaining batch. | `ingest_raw.py:1305` / `:809` |
| 8 | MED | **Locked sections are O(N)** — contention time-bomb, feeds #7 | Every animal ingest rewrites all of `registry_subjects.csv` and every allocation full-scans `registry_raw.csv`, *under the global lock*. As the tables fill, the locked window stretches toward the 60 s timeout, at which point #7 starts firing under normal load. | `subjects_table.py:232`, `acq_id.py:21` |
| 9 | LOW/MED | `checksum_present` hardcoded `"Y"` even for the empty MRI placeholder (no checksummed files). | audit that trusts the column is misled. | `registry.py:230` |
| 10 | LOW/MED | DICOM `StudyDate` fallback breaks idempotency — re-runs of any `acquisition_datetime: NA` config duplicate rows (written key ≠ recomputed key). Documented in-code but live. | | `ingest_raw.py:764-782` |
| 11 | LOW | `latin-1` decode fallback can mojibake genuine cp1252 rows (accented `researcher`/`notes`), then round-trip the corruption out. | | `registry.py:80-86` |

**The three HIGH items produce silent, permanent divergence between the registry and what's on the NAS — fix first.**

**Sound and verified NOT broken:** SHA-256 streams in 64 KB chunks (no whole-file-into-memory); CSV quoting via `DictWriter` is safe; the header-drift guard genuinely prevents column-shift; ACQ-ID collision across concurrent live ingests is correctly prevented by the durable `.acq_id_seq.json` reservation; `locking.py`'s rename-then-recheck stale-break correctly avoids the classic TOCTOU double-unlink; the archive path deliberately preserves `original_name` as the dedup key (a prior bug, correctly fixed). The concurrency *primitives* are good — the bugs are in the *orchestration around them* (dedup outside the lock, non-fatal steps after the commit, the pending list not using the lock at all).

### 3.2 Design-level (the errors that will actually bite)

#### 3.2.1 No disaster recovery — the #1 error

One NAS, RAID 5 on 20 TB drives, no copy off the six disks (snapshots are same-array, `02 §3.2`), in true production with ~13.5 k acquisitions heading to ~50 TB. A 20 TB rebuild reads the whole array over ~a day; a second URE during rebuild = total loss. **For microscopy `.czi` this NAS is the *only* copy** — no platform fallback (`13 §5.6`). `02 §3.3` already calls DR "the single largest open mitigation," and it's unmitigated.

The error is that it's still framed as a *PI decision* while data accumulates. **Fix:** reframe as a *purchase* and execute the already-designed 3-2-1 plan (`02 §5.4`): EU-sovereign S3 archive (Scaleway Glacier / OVHcloud Cold Archive, ~€1,200–1,500/yr at 50 TB) via OCRE, pushed by QNAP HBS 3 with Object Lock, + rotating offline HDDs. Robust even if the OCRE egress-cap question is never answered. This is the one item where inaction, not design, is the error.

#### 3.2.2 The searchable index doesn't scale

`generate_index.py` inlines every registry row into a self-contained `index.html` (~19 MB today, linear to ~140 MB at 100 k, caps at 800 matches, regenerated wholesale at the tail of *every* ingest). CSV-as-*system-of-record* is the right call; CSV-as-*query-substrate* is the latent error.

**Fix:** a derived, disposable SQLite index (source of truth stays CSV), served from it. Already proposed in `13 §4.1`. **Refinement (2026-07 owner note):** the "no-server" constraint is softer than the code assumes — the owner *can* serve a dynamic web app to on-site machines via a no-admin WSL+Windows port-forward (memory: `internal_web_serving_capability.md`). So the Datasette / dynamic-Finder path is not merely "a container on the QNAP" but genuinely reachable for real on-site users, and worth a spike ahead of the 100 k ceiling.

#### 3.2.3 External MariaDB coupled at ingest time

`animal_db.py` joins on a *constructed composite key* (`projects.projectAlias` + `animals.animal_code`) against a MariaDB owned by another team — which the docs note has no single unique-ID column and a near-duplicate in 18 k rows (`06 §2.3.1`). Any schema/credential/network drift silently degrades every new ingest to `pending-db`, growing the queue unbounded until someone runs the manual recovery tool.

**Fix:** decouple — cache the facility mapping as a periodically-synced reference table and enrich in a resilient post-ingest batch from the machine that always has DB access. This *also* deletes most of the deferred-recovery subsystem flagged in §2.3.

#### 3.2.4 Bus factor

All real CLI ingest runs from one repo checkout on one machine with `J:\` mapped, `~/.my.cnf` present, Dicomifier on PATH (WSL/Linux only), and the frozen-exe build steps in one person's head. `01 §6`'s "survives handoff" success criterion is explicitly unproven. **Fix:** containerize the ingest environment (not machine-specific), write the operational runbook, and put a second operator through a full real ingest before scaling.

#### 3.2.5 Referential integrity is advisory, validators never scheduled

`subject_ids ↔ registry_subjects` and `project_hint ↔ registry_projects` are unenforced string joins; projects are *deleted* at close-out (`05 §4`), so dangling hints are by-design possible. `validate_registries`, `verify_checksums`, `metadata_completeness` all exist but nothing runs them on a schedule. **Fix (near-zero cost):** a weekly scheduled task on the data-office machine + an integrity check in the project close-out step.

### 3.3 Scaling 10 → 100 — what breaks first

1. **Ingest throughput** — the single lockfile + wholesale index regen, exercised 10× more often (and by researcher-driven NI live-sync). SMB lockfile atomicity gets stressed; the wholesale regen becomes a multi-minute serial tail on every ingest. *Bites first — not about CSV row count.*
2. **The single-shared-group ACL model IT won't maintain** — per-project access, onboarding/offboarding churn, and the `index.html` leaks everything to anyone who can read the folder. *Bites when the 2nd group joins.*
3. **Single-workstation / single-maintainer coupling** (§3.2.4).
4. **Project-naming debt** (`05 §9`, unresolved) — retrofittable at 10 people, permanent fragmentation at 100.
5. **Only then: search-substrate size** (§3.2.2) — the most-discussed limit bites *after* the operational ones.

---

## 4. What the design gets RIGHT (do not "fix" these)

- **The two-tier reframe (`13_GJESUS3_ROLE`)** — declaring gjesus3 the *research-facing working layer* and the instrument platforms the *deep archive* right-sizes everything downstream and pre-empts a much worse over-engineering (trying to be the institutional deep archive). The single best decision in the project.
- **CSV as the durable system of record** — correct for a no-server, SMB-only, must-survive-handoff environment (human-readable, Excel-openable, git-diffable, recoverable, zero-dependency, portable to XNAT/OMERO).
- **Hard links over `.lnk`** — real-file UX, read-only ACL carry-through, zero extra storage, no server cooperation needed.
- **Non-blocking enrichment** — "never fail an ingest on missing metadata" is the right instinct for low-compliance researchers.
- **Concurrency hygiene** — the lockfile mutex + high-water reservation + BOM/newline-safe CSV append + rename-based stale-break is *more* defensive than most CSV systems bother with, and the "registry append is the commit point" model is sound. (The bugs are in the orchestration around these primitives, not the primitives.)
- **The two-ecosystem metadata builders** — essential complexity (CZI XML vs. Bruker JCAMP-DX vs. Molecubes XML); the callable-registry seam (not OO inheritance) is the right amount of abstraction.

---

## 5. Recommended action order

1. **Commit the DR backup now** (§3.2.1) — the only item where inaction, not design, is the risk. Plan already written.
2. **Fix the HIGH code bugs** (§3.1 #1–3) + the cheap #4 — they cause silent registry-vs-disk divergence.
3. **Fix the `10_TOOLS.md` `operator:` doc trap** (§2.4) — small, but actively breaks anyone following the docs.
4. **Spike the SQLite/Datasette (or dynamic-Finder) search index** (§3.2.2) — dissolves the biggest scaling wall.
5. **Archive the ~10 spent one-off scripts; lift shared I/O helpers into `ingest/`** (§2.1) — kills the duplication that will otherwise drift.
6. **Decouple enrichment from the live DB** (§3.2.3) — deletes a subsystem and removes a fragile dependency.
7. **Automate the existing validators + integrity check at close-out** (§3.2.5) — near-zero cost.
8. **De-risk the bus factor** (§3.2.4) — containerize + a second-operator dry run before scaling.

The net: a disciplined, right-sized core. The work here is mostly *subtraction* (retire debris, park speculative specs, decouple the DB) plus a handful of targeted concurrency fixes — not a redesign.
