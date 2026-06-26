# Phase 4 backfill inventory — `subject:` + `condition:` block coverage

**Generated:** 2026-05-31
**Source:** `J:/raw/` walked by `tools/phase4_backfill_inventory.py`
**Total acquisitions:** 462

## Purpose

This inventory scopes the Phase 4 work in `tasks/tasks.md §3.2`: how many existing acquisitions need `subject:` + `condition:` block backfill once the Phase 3 sidecar writer ships. Per the spec:
- `subject:` block is REQUIRED for `sample_type ∈ {organism, tissue}` (see [08_METADATA §4.4](../mfb-rdm-docs/08_METADATA.md))
- `condition:` block is REQUIRED for the same trigger (see [08_METADATA §4.5](../mfb-rdm-docs/08_METADATA.md))
- For `sample_type = cells`: required when animal-origin (operator judgement until vocab clarifies)
- Not required for `material` / `phantom`

## Coverage today

- Acquisitions with a populated `subject:` block: **0 / 462**
- Acquisitions with a populated `condition:` block: **0 / 462**

(Phase 3 writer hasn't shipped yet, so both should currently be 0 — anything above zero is forward-compatible operator-entered data.)

## Backfill scope by category

| Category | Count | Action |
|---|---|---|
| required | 181 | **MUST** backfill `subject:` + `condition:` (operator recall from notebooks) |
| conditional | 178 | Operator judgement: backfill if cell line is animal-origin |
| not-required | 0 | No action — non-biological sample |
| unset | 103 | Audit — `sample_type` was empty at ingest; revisit before backfill |

## By instrument

| Instrument | Total | Required-backfill | Conditional | Not-required | Unset |
|---|---|---|---|---|---|
| CELL | 165 | 0 | 165 | 0 | 0 |
| CT | 42 | 42 | 0 | 0 | 0 |
| LSM9 | 13 | 0 | 13 | 0 | 0 |
| MRI | 97 | 97 | 0 | 0 | 0 |
| PET | 42 | 42 | 0 | 0 | 0 |
| XMRI | 75 | 0 | 0 | 0 | 75 |
| ZWSI | 28 | 0 | 0 | 0 | 28 |

## Raw distribution by `sample_type`

| sample_type | Count |
|---|---|
| `organism` | 181 |
| `cells` | 178 |
| `cardiac mri study` | 75 |
| `unset` | 28 |

## Raw distribution per (instrument, sample_type)

| Instrument | sample_type | Count |
|---|---|---|
| CELL | `cells` | 165 |
| CT | `organism` | 42 |
| LSM9 | `cells` | 13 |
| MRI | `organism` | 97 |
| PET | `organism` | 42 |
| XMRI | `cardiac mri study` | 75 |
| ZWSI | `unset` | 28 |

---

## Interpreting this report

The **Required-backfill** column is the headline number. For each of those acquisitions, Phase 4 must:
1. Reconstruct disease/control state from study notebooks (operator + researcher recall)
2. Reconstruct subject demographics from the animal-facility-DB (once Phase 1 access lands) OR from researcher recall
3. Re-write the sidecar with populated `subject:` + `condition:` blocks (either via idempotent re-ingest if staging is available, or via standalone `subject_condition_backfill.py`)

The **Conditional** column needs operator judgement per cell-line whether the underlying organism context warrants the blocks.

The **Unset** column flags rows where `sample_type` itself wasn't populated at ingest — those need a sample_type audit before they can be classified for backfill.

---

## Data-quality findings (surfaced by this walk, 2026-05-31)

Two pre-existing data-quality issues surfaced — both predate the `subject:`/`condition:` spec and should be cleaned up before Phase 4 backfill runs (otherwise the backfill will skip these rows for the wrong reason):

### Finding 1: 28 AxioScan ZWSI acqs have `sample_type` empty

All 28 round-4 AxioScan acquisitions show `sample_type = ""`. The AxioScan per-instrument template (`tools/templates/instruments/axioscan7.yaml` line 119) defaults `sample_type: tissue` — but that default was added in the round-4 fixes commit (2026-05-12), AFTER these 28 acqs had already been ingested. They were never updated.

**Fix:** they should all be `sample_type: tissue` per the established AxioScan convention (H&E / WGA fluorescence sections from mouse organs). One-time backfill: rewrite the `sample_type` column in the 28 registry rows + update each sidecar's `user_supplied.sample_type`. Idempotent re-ingest would also do it.

**Phase-4 implication:** once fixed, these 28 will move from "unset" → "required" (tissue is in the trigger set).

### Finding 2: 75 collaborator XMRI acqs have non-controlled-vocab `sample_type`

All 75 round-1/2 collaborator XMRI acquisitions show `sample_type = "cardiac mri study"` — a freeform string from before REG-07's controlled vocabulary (`tissue` / `organism` / `cells` / `material` / `phantom`) was DRAFTed (2026-05-12).

**Fix:** all 75 should be `sample_type: organism` per REG-07 ([06_REGISTRIES §2.4](../mfb-rdm-docs/06_REGISTRIES.md)). The "cardiac mri study" string carries study-purpose info that should migrate into `condition:` block fields (`disease_model: "cardiac"`, etc.) during Phase 4 backfill.

**Phase-4 implication:** once `sample_type` is normalized, these 75 will move from "unset" → "required".

### Revised Phase-4 scope (post-fix)

If both data-quality fixes land first, the required-backfill total becomes **181 + 28 + 75 = 284** (62% of all acquisitions). The 178 cells acqs (CELL + LSM9) stay in the "conditional" bucket — operator judgement per cell line.

Both findings tracked in `tasks/tasks.md §3.2` Phase-4 prep.
