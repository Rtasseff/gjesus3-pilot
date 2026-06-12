# Merge review — designer's `origin/main` ⨉ the correction pass

> **Status:** 2026-06-12, **review done, merge NOT executed** (awaiting the NI-LIVE-08
> design decision + go-ahead). My branch `fix/correction-pass-2026-06` (18 commits) is
> still **unpushed** (push hangs on the GCM dialog — push interactively). `origin/main`
> advanced to `5b20ffd` while the correction pass was in flight.

## 1. What the designer added (`origin/main`, 5 commits past `df84608`)

| Commit | What |
|---|---|
| `8b85734` | GUI builder: start from an existing saved recipe |
| `ec82c13` | GUI default NAS = SMB UNC; **harden cross-drive config relpath** |
| `d5dbe5f` | tasks triage: GUI launch checklist done; NI-live + tooling → BACKLOG |
| `23df602` | **Restart registry schema: add `sample_organism` + `subject_id` + `anatomical_entity`** |
| `5b20ffd` | **`equipment/nuclear-imaging/live_machine_data_layout_and_sync_rules.md`** (571 lines) — the NI live-machine layout + the multi-animal solution |

### The multi-animal NI solution (the new doc, §3B/§3C) — **Model 1**
- One NI scan physically holds **≤ 4 mice**. Decision: **1 scan = 1 acquisition row = 1 ACQ-ID**
  (honest 1:1 with the machine event; DICOMs stored once, no per-animal duplication / hard-link fan-out).
- The scan's **1–4 animals are recorded as a list**. The **authoritative one-to-many** lives in a NEW
  top-level **`registry_subjects.csv`** on the NAS — one row per `(acq_id, project, animal, facility_id,
  scan_position)`. Back-fillable/correctable (subject data is mutable; `/raw/` sidecars are immutable),
  survives DB outages.
- The acquisition registry row carries a **compact human-readable pointer** (`subject_ids` =
  semicolon-joined facility ids) — *"Semicolons are a pointer, not the primary key — the table is."*
- The sidecar carries a **minimal `subjects: [...]` array** (species / sex / age-at-acq + the
  `(project, animal, facility_id)` key + `scan_position`).
- Per-animal **image splitting (Model 2)** is **DEFERRED** (a downstream derivative step, mints new
  UIDs + references the original ACQ-ID — matches published preclinical-DICOM practice, PMC7934703 /
  JNM 61(2):292). Single- and multi-animal scans are the **same code path** (a list of length 1–4).

The user is **fine with the new subjects table**.

## 2. Overlap with the correction pass

| origin/main | correction-pass item | Resolution |
|---|---|---|
| `23df602` registry schema (3 AUTO cols; `build_row(subject=, anatomy=)`) | **S1** (`subject_id` only, via `cfg_single["subject_id"]` stash) | **Theirs supersedes mine** — it adds `sample_organism` + `anatomical_entity` too and projects them directly from the enrichment blocks in `build_row`. Adopt theirs; drop my single-column cfg-stash. My enrichment-at-Step-8.4 already leaves `subject_block`/`anatomy_block` in scope, so their `build_row(... subject=, anatomy=)` call drops in. **`subject_id` is the SAME column, same value, same AUTO class — conceptually aligned, just less complete on my side.** |
| `ec82c13` cross-drive relpath | **item 7** | **Functionally identical** (both wrap `os.path.relpath` in `try/except ValueError` → absolute fallback). Take one copy; behavior is the same. |
| `ec82c13` GUI NAS-UNC default + `8b85734` builder-from-recipe | **item 1** dry-run GUI (banner + default-ON + loud summary) | Both edit `index.html` / `app.js` / `app.py`. **No semantic conflict** — different features; reconcile the text so both survive (my `#r-dry-banner` + `updateDryState` + end-of-run summary; their default-NAS-UNC + builder start-from-recipe). |
| `d5dbe5f` tasks/BACKLOG triage | my `tasks.md §0` + `BACKLOG.md` adds | Text reconcile. Both moved things to BACKLOG; union the lists. |
| their `06_REGISTRIES.md` / `08_METADATA.md` / `00_INDEX.md` / `10_TOOLS.md` edits | my doc edits for S1/S2/8/9/D1–D4 | Text reconcile — same sections (the new columns, the version-history/header de-bloat). My S1 doc text should fold into their 3-column text. |

**My unique work (no overlap — carries forward intact):** registry lock + reservation (`locking.py`,
`acq_id.allocate_acq_id`), `csv_safe.py` (items 8+9), archive-rerun / crash-orphan / empty-folder fixes
(items 4/5/6), CELL+LSM9 recipes (3), `os.link` diagnostic (11), frozen-GUI path fix (2),
`START_HERE.md` / `GLOSSARY.md` / `CHANGELOG.md` + de-bloat (D1–D4), suggested vocabularies (S3).

## 3. Subject / sample data shape — **DECIDED 2026-06-12 (user)**

> NI-LIVE-08 (singular `subject_id` vs plural `subject_ids`) is **resolved: packed plural**. This is a
> **data-capture** decision; the **query layer is explicitly deferred** (flat tables / our own DB /
> XNAT / OMERO — undecided, revisit after we have data). Guiding principle (user): converge what the
> org has into one place, **stop expanding the model**, capture the right data for one small group (3–6
> people, 12–18 months back), *then* build access/query/retrieval.

1. **Acquisition registry (`registry_raw.csv`) → packed `subject_ids` column.** `;`-joined facility
   animal ids, **always a list** (length 1 in the ~99% single-animal case, so single- and multi- are one
   uniform shape). It is the scan→animal link **and** makes multiplicity visible to a registry-only
   reader (the filenames already set that expectation). It is a **human-readable summary**, not a join
   key — exact lookups use the subject table. **Replaces** the singular `subject_id` (designer's
   `23df602` + correction-pass S1). `sample_organism` / `anatomical_entity` stay singular (uniform across
   an all-organism scan). **`sample_type`, `sample_id`, and every GUI are UNTOUCHED** — many subjects ⇒
   many samples, but **one `sample_type`** (the category, e.g. `organism`), so nothing cascades.
2. **Sidecar (`metadata.json`) → minimal subject subset.** For an animal: facility animal id, species,
   sex, age-at-acquisition (+ a `subjects:[…]` array for a multi-animal scan). A deliberate **hedge** —
   if only the raw archives survive, minimal subject context travels with them. **Not** the full record.
3. **Subject table (`registry_subjects.csv`) → a TRUE subject table: one row per subject.** The subject
   facts we can grab now (facility id, species, sex, age-at-acq, …), brought into gjesus3 from the
   otherwise-isolated facility DB as needed. **Updatable / back-fillable** (subject data is mutable; the
   DB lags; only the data office has creds and access reliability is unknown). The **static-vs-dynamic**
   refinement (e.g. disease models — animals are *manipulated*, not born that way) is a **FUTURE** issue
   to take from ISA / other data models — **not now**. Now: grab-what-we-can, one entry per subject.
4. **Deferred recovery / the immutability "cheat" — ALREADY BUILT (Phase 3, 2026-06-03; confirmed).** A
   DB-miss / no-credentials ingest does not block: it writes `source:"pending-db"` and **queues the acq
   to `registries/pending_subject_metadata.csv`** (flags the data office). The data office later runs
   **`tools/recover_subject_metadata.py`** (creds + sidecar-write) to **update the JSON sidecars in
   place** — the controlled, data-office-only exception to `/raw/` immutability ([08_METADATA §4.4.6 /
   §4.7](../mfb-rdm-docs/08_METADATA.md)). This is *the* path; document it as such.
5. **NO mapping / junction table ("Acquisition registry", one row per `acq × subject`) now.** The
   multiplicity is already captured by the packed `subject_ids` column + the sidecar `subjects:[…]`. A
   per-`(acq, subject)` table is a **query-layer** optimization — **documented as a FUTURE option**, to
   revisit when we build access/query (it answers exact "all scans of animal X" without a substring
   filter; not needed to *capture* the data). Not built now.

## 4. Merge approach (after go-ahead; design now DECIDED in §3)

1. **Merge `origin/main` into `fix/correction-pass-2026-06`** (one integration pass; the overlap is
   concentrated, so resolving once beats an 18-commit rebase).
2. Conflict resolution, applying §3:
   - **Registry schema → adopt the designer's `build_row(subject=, anatomy=)` projection** and their
     `sample_organism` / `anatomical_entity` columns; **rename the singular `subject_id` → packed
     `subject_ids`** (both the designer's `23df602` column and the correction-pass S1 column collapse to
     the one packed column; `subject_ids` = `;`-joined `subject.facility_animal_id`, length-1 in the
     common case). Drop my S1 `cfg_single["subject_id"]` stash. `sample_type`/`sample_id`/GUIs untouched.
   - **relpath → keep one copy** (functionally identical). **GUI / tasks / docs → union** (both features;
     both backlog lists; fold my S1 doc text into the packed-`subject_ids` text).
   - Keep all my unique work (§2) intact.
3. **Re-run the full test suite + sandbox harnesses** (lock, csv_safe, archive-rerun, orphan,
   empty-folder). Update `test_registry_fields.py` to `subject_ids` (packed) + `sample_organism` +
   `anatomical_entity`.
4. **Review again** (the user's "review again" step) before the user pushes.
5. **Not in this merge** (the designer's NI-live Stage-A/B work; coordinate): the `registry_subjects.csv`
   **true subject table** writer (one row per subject — note this is a **reshape** from the designer's
   current mapping-shape table), the multi-animal `subject_ids` list assembly, and the minimal sidecar
   `subjects:[…]`. The merge only has to land the packed `subject_ids` column + keep §2 intact.

## 5. External deps still on the user (carried from the correction pass)

- [ ] Provide a representative **`.czi`** → verify the frozen microscopy GUI's end-to-end metadata read (item 2).
- [ ] Run `python3 tools/diagnostics/test_oslink.py <scratch>` on the **MRI (Linux)** + **NI (Mac-fronted)** mounts → report verdicts → choose hard-link vs fallback per instrument (item 11).
- [ ] Sign-off to run the `subject_id`/schema migration + a smoke ingest against the **live `J:\gjesus3-data`** registry.
- [ ] Optional: install `~/.my.cnf` on a trusted machine to enable animal-DB auto-fill (item 10 — an optimization, not required).
- [ ] **Push** `fix/correction-pass-2026-06` interactively (`git push -u origin fix/correction-pass-2026-06`) — the agent push hangs on the GCM dialog.

## 6. Status / next step

- **§3 design is DECIDED (user, 2026-06-12).** NI-LIVE-08 resolved: packed `subject_ids` + true
  one-row-per-subject table + minimal sidecar; no mapping table now; query layer deferred.
- **Coordinate with the designer** (they own `registry_subjects.csv` + the schema on `origin/main`): the
  table reshapes mapping → true subject table; the singular `subject_id` becomes packed `subject_ids`.
- **Open: who executes the consolidation** — (a) the agent runs the merge per §4 on the
  `fix/correction-pass-2026-06` branch now, or (b) hand these decisions to the designer to apply on
  `origin/main` first, then merge. Awaiting the user's call.
