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

## 3. The `subject_id` (singular) ⨉ `subject_ids` (plural) tension — **NI-LIVE-08**

The designer flagged this themselves (NI-LIVE-08, §8 of the new doc): the registry has a **singular
`subject_id`** column (their `23df602`, and my S1), but a multi-animal scan references **1–4** subjects.
*How does the single column represent N>1 — a list? a primary + the others in the table?*

§3B/§3C already imply the answer; this just makes it explicit. **Recommended resolution (for the user /
designer to confirm):**

- **Keep `subject_id` SINGULAR as the registry column** = the **primary** subject (the single animal in
  the 99% case; `scan_position 1` for a multi-animal scan). It stays atomic, the queryable join key, and
  matches the post-restart schema + both implementations. → this is NI-LIVE-08's *"primary + others in
  the table"* option.
- **`registry_subjects.csv` (the new subjects table) is the authoritative N>1** — one row per
  `(acq_id, animal, position)`. This is where the *plural* relationship lives, **as rows**, not as a
  packed column. The sidecar `subjects: [...]` array mirrors the minimal subset.
- **Do NOT add a plural `subject_ids` registry COLUMN.** The `subject_ids` semicolon-string the doc
  mentions is a **denormalized human-readable convenience** (sidecar, or an optional non-key display
  field) — never the key. A packed plural column would break atomicity, the join, and the singular
  post-restart schema for the sake of the ≤1% multi-animal case the table already handles.

Net shape: `subject_id` (singular column = primary) **+** `registry_subjects.csv` (authoritative table)
**+** sidecar `subjects:[…]`. Singular naming is preserved; multi-animal fidelity lives in the table.
**Alternatives if the user prefers** (document the choice): (a) packed `subject_id` = `id1;id2;…` (atomic-breaking);
(b) rename the column to plural `subject_ids` always-a-list (breaks the singular join + restart schema).
Recommendation is to keep singular + table.

## 4. Proposed merge approach (after the NI-LIVE-08 decision + go-ahead)

1. **Merge `origin/main` into `fix/correction-pass-2026-06`** (one integration pass; the overlap is
   concentrated, so resolving once beats an 18-commit rebase).
2. Conflict resolution rules: **registry schema → take the designer's 3-column `build_row(subject=,
   anatomy=)`** and delete my single-column S1 wiring (the `cfg_single["subject_id"]` stash in
   `ingest_raw.py` + my `build_row` `subject_id` line); **relpath → keep one copy**; **GUI/tasks/docs →
   union** (keep both features / both backlog lists; fold my S1 doc text into their 3-column text).
   Keep all my unique work (§2) intact.
3. **Re-run the full test suite + the sandbox harnesses** (lock, csv_safe, archive-rerun, orphan,
   empty-folder, + a build_row test updated for the 3 columns). Update `test_registry_fields.py` to the
   3-column schema.
4. **Review again** (the user's "review again" step) before the user pushes.
5. The new `registry_subjects.csv` writer + the multi-animal list handling is **the designer's
   Stage-A/B NI-live work** (tracked in their doc / BACKLOG) — *not* part of this merge; the merge only
   has to not conflict with the singular `subject_id` column.

## 5. External deps still on the user (carried from the correction pass)

- [ ] Provide a representative **`.czi`** → verify the frozen microscopy GUI's end-to-end metadata read (item 2).
- [ ] Run `python3 tools/diagnostics/test_oslink.py <scratch>` on the **MRI (Linux)** + **NI (Mac-fronted)** mounts → report verdicts → choose hard-link vs fallback per instrument (item 11).
- [ ] Sign-off to run the `subject_id`/schema migration + a smoke ingest against the **live `J:\gjesus3-data`** registry.
- [ ] Optional: install `~/.my.cnf` on a trusted machine to enable animal-DB auto-fill (item 10 — an optimization, not required).
- [ ] **Push** `fix/correction-pass-2026-06` interactively (`git push -u origin fix/correction-pass-2026-06`) — the agent push hangs on the GCM dialog.

## 6. Decisions needed from the user

- **NI-LIVE-08** — confirm the §3 reconciliation: **singular `subject_id` column (primary) + `registry_subjects.csv` table + sidecar `subjects:[…]`**, no plural registry column. (Or pick alternative (a)/(b).)
- **Go-ahead to execute the merge** (§4) once NI-LIVE-08 is set.
