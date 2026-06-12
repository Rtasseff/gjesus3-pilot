# NI live-machine ingest — path-forward plan (Step 2 → 3)

**Status:** PROPOSAL — 2026-06-12, data-office review. **No code was changed** (documentation only).
Builds on the designer's §7 "Path forward" (commit `7cc0773`) and the Step-1 review (`50aac67`).

> **✅ D1 APPLIED 2026-06-12 (user-directed):** the junction-table contradiction is **fixed in the
> spec** — §3B/§3C/§7 of the equipment doc + `06_REGISTRIES §2.3/§2.3.2` now say `registry_subjects.csv`
> = **one row per subject**, no `(acq_id, animal)` junction table. Done *before* any historical-data
> ingest could build the wrong shape (no such writer exists in code yet — verified). **D2–D4 are
> deferred** (they only affect the live ingest) and remain open below. The rest of this plan still
> **awaits go-ahead before any implementation.**

Design source of truth: [`equipment/nuclear-imaging/live_machine_data_layout_and_sync_rules.md`](../equipment/nuclear-imaging/live_machine_data_layout_and_sync_rules.md).

---

## 1. Where we are (verified)

- **Step 1 is DONE + tested + reviewed by both sides.** `tools/ni_live_discover.py` (read-only discovery
  dry-run) + `tools/test_ni_live_discover.py` (30 checks, green). Re-run against the real 262-acq snapshot:
  **254/262 DB-keyable, 102 multi-animal, 1 phantom**; the `project-conflict` flag surfaces the **12** typo
  near-misses (10 `1015`-vs-`1025` + 2 `0324`-vs-`0314`) that previously passed as confident unflagged keys.
- **The infra Step 2/3 reuse already exists on `main`** (correction pass): registry lock + durable ACQ-ID
  reservation (`tools/ingest/locking.py`, `acq_id.allocate_acq_id`), BOM/newline-safe CSV appends
  (`csv_safe.py`), crash-orphan rollback (registry append = commit point), empty-folder fail-loud, the
  `os.link` diagnostic (`tools/diagnostics/test_oslink.py`), and the single-animal DB-lookup +
  `pending_subject_metadata.csv` → `recover_subject_metadata.py` recovery chain.
- **HEAD = `origin/main` = `7cc0773`.**

**The designer's §7 Gate-0 / two-decisions / Step-2-split framing is sound — I endorse it.** The items below
are the gaps that framing does not yet cover, plus a sharper interface contract and sequencing.

---

## 2. ✅ FIXED (D1, 2026-06-12) — the doc contradiction that would have built the *wrong* table

**Applied to the spec on 2026-06-12** (equipment §3B/§3C/§7 + `06_REGISTRIES`). Recorded here as the rationale.
`registry_subjects.csv` had been described two incompatible ways in the same document:

| Source | Says | Shape |
|---|---|---|
| §3B (l.312-313) + §3C (l.343) — **2026-06-11 text** | "one row per `(acq_id, animal, scan_position)`" | **junction / mapping table** (the same animal recurs once per scan) |
| NI-LIVE-08 — **2026-06-12 DECIDED** | "a **true one-row-per-subject** table"; "**no** mapping/junction table now" | **one row per animal**, ever |

A `(acq_id, animal)` key is *exactly* the mapping table the user vetoed. §3B/§3C predate the NI-LIVE-08
decision and were never reconciled to it. **An implementer following §3C literally builds the rejected table.**

### Recommended resolution (D1) — a static-vs-acq-relative split (simpler, not more machinery)

This also closes the lingering NI-LIVE-12 question ("which fields are the minimal sidecar subset"):

| Fact | Cardinality | Home |
|---|---|---|
| `facility_id`, `project_alias`, `animal_code`, `species`, `sex`, `strain`, `date_of_birth` | **static per animal** | `registry_subjects.csv` — **one row per animal** (PK = `facility_id`), upsert |
| which animals were in THIS scan (the link) | per acquisition | `registry_raw.csv` **`subject_ids`** (packed, `;`-joined) — *user-decided* |
| `scan_position`, `age_at_acquisition` | per **(acq, animal)** | sidecar **`subjects:[{facility_id, scan_position, age_at_acq}]`** |

**Why:** `scan_position` and age-at-acq are per-acquisition facts — they *cannot* live in a one-row-per-animal
table without dragging it back into a junction. The per-acq sidecar already exists and is their natural home.
`registry_subjects.csv` then holds only truly static facts and stays a real subject table. The scan→animal link
stays in `subject_ids` exactly as the user decided.

This is **aligning stale text to an already-made decision + drawing the minimal-sidecar line** — not new scope —
but it edits the authoritative §3B/§3C, so it wants the **user's nod** first.

---

## 3. Decisions needed before coding (small, but real)

| # | Decision | Recommendation | Owner |
|---|---|---|---|
| **D1** | §3B/§3C reconciliation (above) | ✅ **APPLIED 2026-06-12** — adopted the static-vs-acq-relative split | done |
| **D2** | NI-LIVE-09: on a `project-conflict` flag, which code wins? | keep the subject prefix per §3A **but route the 12 flagged acqs through `pending_subject_metadata.csv`** before the DB key is trusted (flag-don't-guess; reuses existing machinery). *Designer's proposal — endorse.* | user — ratify |
| **D3** | NI-LIVE-07: range rule | confirm "dashes = explicit list; flag `gap>1` as `possible-range`" — *already what the code does* | user / Unai |
| **D4** | **Gate 0 (external)** — `os.link` on the Mac CIFS mount + host/layout + forward standard | run `test_oslink.py` on the Mac; if it fails, ingest from a Windows-remote or use the `.lnk` fallback (Mac only stages/pushes) | user / Unai |

**D1–D3 gate Step-2 *coding*. D4 gates a *real ingest* (Step 3), not the coding** — so Step 2 can proceed in
parallel with chasing Unai.

---

## 4. Step 2 — the split + the interface contract (so two lanes don't collide on shared registry code)

### Lane A — shared schema reshape (designer; touches the correction-pass integrity code → follow its rules)
- **A1. Rename the AUTO column `subject_id` → `subject_ids`** across `REGISTRY_FIELDS` (`registry.py`),
  `AUTO_COLUMNS` (`resolver.py`), the defensive header check, `06_REGISTRIES §2.2`, `08_METADATA`, and **every**
  per-instrument template. For the 97% single-animal instruments (DICOM/MRI/microscopy) `subject_ids` is just the
  1-element value (no semicolon) — **existing values stay valid**, so this is a pure header rename of data.
- **A2. Evolve `build_row` to take a LIST of subjects** → `subject_ids = ";".join(facility_animal_id)`;
  `sample_organism` = the common species; `anatomical_entity` unchanged (one FOV). Single-subject callers pass a
  1-element list. **This signature is Lane B's only dependency on Lane A.**
- **A3. `registry_subjects.csv` writer = UPSERT keyed by `facility_id`** (read-modify-write under the **same**
  `registry_lock`; write via `csv_safe` — new CSV writers MUST use it, per `06_REGISTRIES §2.7`). Holds only the
  static fields (D1). An animal seen in N scans → still **one** row.
- **A4. Migration (lockstep with A1).** Use the `migrate_registry_columns.py` pattern (back up → migrate →
  register the `.bak`) to rename the header on **every existing registry** (live + sandbox). This MUST run with
  A1 because `registry.append_row`'s **defensive header check rejects appends the instant `REGISTRY_FIELDS`
  changes** and the on-disk header still says `subject_id`.

### Lane B — live-NI glue (separable; depends only on A2's signature)
- **B1. `molecubes_ni_live.yaml`** — live variant of `molecubes_ni.yaml`: source = folder tree (no archive-name
  regex); fields from the path-walk; `link_filename` per-scan.
- **B2. discovery → ingest wiring:** `ni_live_discover` parse → per-animal `animal_db` lookup (MISS **or**
  `project-conflict` ⇒ queue via `pending_subject_metadata.csv`, never fail) → assemble the 1–4 subject list →
  `build_row(subjects=[…])` → emit packed `subject_ids` + sidecar `subjects:[]`. Reuse
  `copy_ni_acquisition()` + `ni_metadata.py` **unchanged**.
- **B3. sidecar `subjects:[]` shape** documented in `08_METADATA` + implemented in the NI metadata path.

### Critical path
```
D1–D3  →  A1+A4 (rename + migrate, lockstep; unblocks B)  →  B1–B3  →  Step 3
                              A3 (subjects-table writer) runs in parallel with B
```
**A3 is NOT on B's critical path** — the subjects table can be populated/back-filled by
`recover_subject_metadata.py`, so the glue can ingest (link + sidecar) before the table writer lands.

---

## 5. Step 3 — vetted one-shot to the sandbox (after Gate 0 / D4 clears)

Human reviews the discovery `--csv` table → ingest the in-scope MFB folders to **`J:\gjesus3-sandbox`** with the
§3B one-entry-per-scan shape. **Verify:** idempotent re-run (R7 — no new ACQ-IDs / no dup rows), empty-folder
guard (R9), `os.link` on the **real** mount (R10), `subject_ids` packed correctly, `registry_subjects` upserted
(no duplicate per animal), sidecar `subjects:[]` present, and the **12 conflict acqs land in the pending queue —
not silently keyed.**

---

## 6. Acceptance criteria / tests (extend the existing convention)

- **Extend `test_registry_fields.py`:** `build_row(subjects=[a,b])` → `subject_ids == "a;b"`; single → `"a"` (no
  `;`); header carries `subject_ids`, not `subject_id`.
- **New `test_registry_subjects.py`:** upsert same `facility_id` twice → 1 row; two ids → 2 rows; writer uses
  `csv_safe` + `registry_lock`.
- **Migration dry-run** on a copy of the sandbox registry: header renamed, row values intact, `.bak` registered.
- **e2e on the sandbox** (Step 3) as the integration gate.

---

## 7. Parked (unchanged)

Program B forward naming standard + who enforces it (NI-LIVE-13); per-animal image splitting (Model 2); the
mapping/junction table + query layer; the position-numbering standard going forward (NI-LIVE-11).

---

## 8. Footprint of this review

Code: **none.** **D1 applied 2026-06-12** (user-directed) — equipment §3A/§3B/§3C/§7 + `06_REGISTRIES §2.3/§2.3.2`
now mandate one-row-per-subject, no junction table. **D2–D4 deferred** (they only affect the live ingest).
