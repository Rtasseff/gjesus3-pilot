# Handoff — project naming: "project hint" → "project name" + folder normalization

**Branch:** `refactor/project-naming` · **Worktree:** `…/projects/gjesus3-dev/project-naming`
**Base:** `main` @ `7f0eba2`.
**Status:** not started — and **must wait for branch G** (`feat/gui-operator-polish`) to
merge first (see §0). This doc is self-contained.

⚠️ **This is a TRUE-PRODUCTION change.** `registry_raw.csv` has **13,582 live rows**, and
there are **43 live project folders** on `\\gjesus3\gjesus3\gjesus3-data\projects\`.
`project_hint` is a live registry column **and** an integrity-mirror column (spec ↔ code
must stay in lockstep). Nothing here is a quick edit. Back up first, dry-run everything,
do the data move in a no-ingest window, and keep a rollback.

---

## 0 · CRITICAL first step — rebase onto the latest `main` (with G)

This branch renames `project_hint`, which appears in files that branch **G**
(`feat/gui-operator-polish`) is also editing (`app.js`, `app.py`, `value_fields.py`) —
and G will *add* a `${project_hint}` token chip. So:

```
cd "…/projects/gjesus3-dev/project-naming"
git fetch origin          # (or just: the shared local repo already has main updated)
git merge main            # or: git rebase main  — bring in G's merged work
# resolve any conflicts, THEN start the sweep below so it covers G's additions.
```
If G has **not** merged yet when you start, stop and confirm with the data office —
running the rename before G lands means you'll miss G's new `project_hint` reference and
have to redo the sweep.

---

## 1 · What the data office wants (the end state)

From the 2026-07-17 operator test, two linked asks (issues "a" and "b"):

**(a) Rename the concept "project hint" → "project name".** The operator finds "project
hint" confusing; in practice it *is* the project's name. Change it everywhere it's
operator-visible, and — scope to confirm, see §2 — possibly the column/field name too.

**(b) Normalize the project folders so the folder name == the project name.** Today the
GUI shows e.g. `AE-biomeGUNE` but the folder is `proj-ae-biomegune-0525` (a `proj-`
prefix + forced lowercase). The ask:
- **drop the `proj-` prefix** on all existing project folders,
- **restore casing** (`ae-biomegune` → `AE-biomeGUNE`) on the AE-biomeGUNE folders,
- **make every recorded project's "project name" equal its new folder name**, and
- make new ingests produce that same name (no `proj-`, preserved casing) going forward.

Desired result: GUI field **"Project name" = the exact folder name** = e.g.
`AE-biomeGUNE-0525` (and person/topic projects become `claudia`, `laura-tholt`, … — just
the `proj-` dropped).

---

## 2 · Is "hint" wrong? — the current model, and the scope decision

**Why it's called "hint" today.** `project_hint` is a *loose operator-supplied pointer*
that the pipeline **resolves** to a concrete project: at ingest it's matched against a
project's `short_name` (or `project_id`) in `registry_projects.csv`, and if none matches
it **auto-creates** one. So historically it was a hint that gets resolved/normalized —
not a guaranteed canonical name. In practice, though, it functions as the project's name,
so the rename is defensible.

**The data model (verify before you touch it):**
- `registry_raw.csv` column **`project_hint`** — the per-acquisition value, e.g.
  `ae-biomegune-0525` (lowercased slug). 13,582 rows.
- `registry_projects.csv` columns: `project_id` (systematic `PROJ-000N`), **`short_name`**,
  `description`, `owner`, `start_date`, `status`, `last_activity`, **`folder_location`**,
  `notes`. There is **no** `project_hint` column here.
- Resolution: `project_hint` → matched to `short_name`/`project_id` → `folder_location`
  gives the folder (`ingest_raw.py:1271`, `gather_metadata.py:69-76`). On auto-create,
  `short_name_norm = project_hint.lower()` and folder = `proj-{short_name_norm}`
  (`ingest_raw.py:1286,1311`; `create_project.py:141`). So today
  **project_hint value ≈ short_name ≈ folder-minus-`proj-`, all lowercased.**

**Scope decision to confirm with the data office (recommend deciding before Phase B):**
- **Minimal** — relabel the GUI/docs terminology to "project name" but **keep the column
  name `project_hint`** internally, and keep stored values as-is (a lowercase internal
  key) with a display name. Lowest risk; satisfies the operator-facing confusion.
- **Full** (what the user described) — rename the **column** `project_hint` →
  `project_name`, and **re-case the stored values** so they equal the new folder names
  (`ae-biomegune-0525` → `AE-biomeGUNE-0525`). Cleanest end state; highest risk (live
  column-header migration on 13,582 rows + a value migration + the integrity mirror).

There is no separate "project name" field in use today that would collide, so the term is
free. But `project_id` (`PROJ-000N`) stays the systematic unique id — don't conflate the
human "project name" with it. **Get the data office to confirm minimal-vs-full before the
live migration** (per the repo rule, vocabulary/convention calls are Data Office calls —
the user is effectively making it, but pin down the column-rename scope explicitly).

---

## 3 · Blast radius (grounded)

- **`project_hint` = 277 occurrences across 106 files** (`git grep -c project_hint`).
- It's in the **integrity mirror** `06_REGISTRIES ↔ resolver.py/registry.py`
  (`CONTRIBUTING-docs.md#cross-reference-consistency`) — spec and code MUST change
  together. `resolver.py:83` lists it in `USER_CONTROLLABLE_COLUMNS`;
  `tools/ingest/registry.py` writes the column.
- **Live data:** the `project_hint` column in `registry_raw.csv` (13,582 rows) and the
  `folder_location`/`short_name` in `registry_projects.csv` (51 rows, 43 active + 8 closed).
- **Folder-name construction sites** (every place `proj-`/lowercasing is baked in — all
  must change in lockstep with the folder migration, or new ingests recreate old names):
  - `tools/create_project.py:141` `folder_name = f"proj-{name}"` (+ `:143` canonical_path,
    `:221` folder_location). **The canonical site.**
  - `tools/ingest_raw.py:1286` `short_name_norm = project_hint.lower()` (the lowercasing),
    `:1311` `projects/proj-{short_name_norm}/…`, `:1271` resolve-by-short_name log.
  - `tools/operator/collisions.py:86-94` `_project_folder` builds `projects/proj-<hint>/raw_linked`.
  - `tools/ingest/linker.py` — the project hard-link path (`raw_linked/`) construction;
    confirm it takes the folder from resolved `folder_location`, not a rebuilt `proj-` string.
- **Consumers of the value / folder:**
  - `tools/generate_index.py:296-316` groups per-project by `project_hint` and writes each
    per-project `index.html` under `folder_location`.
  - `tools/find_acq.py:45-46` (`folder_location`, `short_name`) + the payload `project_hint`.
  - `tools/gather_metadata.py:69-76` resolves project by `short_name`/`project_id`.
  - `tools/operator/value_fields.py:53` — the GUI field `{"key":"registry.project_hint",
    "label":"Project hint", …}`. Relabel (and re-key if full-scope).
  - GUI: `app.py`, `static/app.js`, `static/mri.js` (+ `collisions.py` via the MRI page).
  - **All `tools/configs/*.yaml`** and `tools/templates/instruments/*.yaml` set
    `project_hint:` in their `registry:` blocks (many files).
  - Docs: `05_PROJECTS`, `06_REGISTRIES`, `08_METADATA`, `09_MODALITIES`, `10_TOOLS`,
    `tools/INGEST_CLI.md`, `OPERATOR_FAQ.md`, etc.
  - Tests: `test_find_acq.py`, `test_collisions.py`, `test_registry_fields.py` hard-code
    `project_hint` and `proj-…` folder names.
  - `rebuild_baseline/registry_*.csv` — snapshot copies (note: known stale header; don't
    let a rename make it look authoritative).
- **`validate_registries`** does an (unenforced) `project_hint ↔ projects` string join
  (BACKLOG "Automate the existing validators"). If you re-case values, update both sides
  together so the join still matches.

---

## 4 · Phase A — terminology / column rename (code + docs + GUI + configs)

Do this as a coherent, reviewable unit **before** the folder migration. If the data
office chose *minimal* scope, this is mostly relabeling; if *full*, it includes the live
column-header rename.

- If **full scope**: rename the column `project_hint` → `project_name` in
  `registry.py` (the `REGISTRY_FIELDS`/header), `resolver.py` (`USER_CONTROLLABLE_COLUMNS`
  + any references), `06_REGISTRIES` (the mirror — keep spec+code identical), and migrate
  the **live** `registry_raw.csv` header (precedent: the 2026-06-09 operator→researcher
  header migration to 25 cols — same technique, back up first). Update every `.yaml` config
  key `project_hint:` → `project_name:` and every doc mention.
- If **minimal scope**: leave the column/key `project_hint`; change only the GUI label
  (`value_fields.py:53` `"label":"Project name"`), the operator-facing help/docs wording,
  and the `hint:"link to a project"` gloss.
- Either way: update the GUI field label to **"Project name"**; sweep operator-facing docs
  and help pages; keep `project_id` (PROJ-000N) distinct.
- Respect status markers: don't silently alter ✅ DECIDED schema items — if the column
  rename touches a DECIDED registry decision, note it in the CHANGELOG (append-only) and
  keep the spec/code mirror exact.

**Land Phase A, verify (run the test_* files + `validate_registries` dry-run), commit.**

---

## 5 · Phase B — folder + value migration (the risky live-data move)

Only after Phase A. This renames real production folders and (full scope) re-cases
13,582 stored values. Treat it like the DICOM-regen / registry migrations: **backup →
dry-run → apply → verify → rollback-ready**, in a **no-ingest window**.

1. **Back up off-NAS first:** both registry CSVs (byte-copy, dated dir — the established
   pattern, e.g. `C:\Users\rtasseff\temp\…_backup_<date>\`) and a listing of the current
   project folders. Confirm no other operator is ingesting.
2. **Build an explicit old→new folder mapping** (43 entries) — do **not** assume one
   regex. `proj-ae-biomegune-0525` → `AE-biomeGUNE-0525`; `proj-claudia` → `claudia`;
   `proj-laura-tholt` → `laura-tholt`; etc. Casing is only restored where it applies
   (AE-biomeGUNE); person/topic slugs just drop `proj-`. Note the FS is **case-insensitive**
   (Windows/QNAP SMB), so a pure-case change is cosmetic to the FS but matters for display
   and exact-match code — the `proj-` drop is the real rename.
3. **Hard links survive a folder rename** (renaming the parent dir doesn't touch the
   `raw_linked/` inodes that point into `/raw`) — but **every stored/constructed path
   string must update.** Update in the same migration:
   - `registry_projects.csv` `folder_location` (and `short_name` if it carries the slug).
   - the **construction sites in §3** (`create_project.py:141`, `ingest_raw.py:1286/1311`,
     `collisions.py:94`) so *new* ingests write the new names — change `f"proj-{name}"` →
     `name`, and drop the `.lower()` so operator casing is preserved.
   - **verify** whether per-project `provenance.csv` / `_project.yaml` store the project
     folder path (check `07_PROVENANCE` + `linker.py`); if so, migrate those too.
   - the per-project `index.html` is regenerated from `folder_location` — just re-run
     `generate_index.py --per-project` after, no manual edit.
4. **(Full scope) re-case the `project_hint`/`project_name` values** in `registry_raw.csv`
   (13,582 rows) to equal the new folder names, using the same old→new mapping. Keep the
   `validate_registries` `project_hint↔projects` join intact (update both sides atomically).
5. **Apply** the folder renames (`os.rename` / move) per the mapping; write the updated CSVs
   atomically (temp+replace, under the registry lock — see `pending_dicom.py` / the
   `recover_subject_metadata.py` controlled-write pattern).
6. **Verify:** every folder exists under its new name; `folder_location` points at it;
   hard links still resolve (same inode, `relink_projects.py` can reconcile if any slipped);
   `validate_registries` clean; regenerate the Finder indexes and confirm counts unchanged;
   do one throwaway dry-run ingest into a renamed project and confirm it links into the new
   folder (no `proj-` folder recreated).
7. **Rollback:** keep the pre-move CSV backups and the mapping; a reverse-mapping script
   restores names + CSVs if verify fails.

Write this as a **dedicated migration script** with `--dry-run` default (like the other
`tools/…migrate/relink` tools), not ad-hoc edits.

---

## 6 · Interactions & reasons for caution (read before committing to Phase B)

- **There is an adjacent, semantic re-projecting effort already planned.** BACKLOG →
  "Legacy Zeiss microscopy … BEST-GUESS ingest" and the "Project re-organization via
  researcher feedback" item (05_PROJECTS §9 / PROJ-05): the data office does **not** want
  per-user/researcher project folders long-term and plans to **re-home / re-name**
  historical microscopy projects from researcher feedback. Your Phase B is a **mechanical
  normalization** (drop `proj-`, fix case) — separate from that **semantic** re-projecting,
  but they touch the same folders. **Flag the ordering to the data office:** if projects
  are about to be re-named/re-homed anyway, a mechanical rename now may be partly redundant
  (or should be folded into the same migration). Don't silently do both.
- **Integrity mirror + DECIDED items:** `06_REGISTRIES ↔ resolver/registry` must stay in
  lockstep; a column rename is a schema change — record it in the append-only `CHANGELOG.md`
  and don't rewrite past entries.
- **True production, single-operator safety today:** the system's concurrency safety
  currently relies on a single manual operator (see the architecture-review items). Do the
  migration when no ingest is running.
- **Closed projects (8):** their folders were deleted at close-out; their registry rows
  survive (so acqs stay findable). The rename must update their `folder_location`/values in
  the registry **without** trying to move a non-existent folder — skip the move, migrate the
  record. (`generate_index` already skips `status=closed` for per-project pages.)

---

## 7 · Sequencing summary
1. Wait for **G** to merge to `main`; rebase this branch onto it (§0).
2. **Phase A** (terminology/column rename) — one commit/PR; verify; land.
3. Confirm minimal-vs-full scope + the re-projecting ordering with the data office (§2, §6).
4. **Phase B** (folder + value migration) — dedicated dry-run script, backup, no-ingest
   window, verify, rollback-ready — separate commit/PR.
5. Rebuild + redeploy the operator exe (the GUI now shows "Project name" == folder name);
   coordinate with G's rebuild so operators get one consistent build.
6. CHANGELOG (append) + `tasks/STATUS.md` + `00_INDEX.md` Last-Updated bump.

## 8 · File / reference
| Concern | File | Anchor |
|---|---|---|
| Folder name construction (canonical) | `tools/create_project.py` | 141 `proj-{name}`, 143, 221 |
| project_hint→folder + lowercasing | `tools/ingest_raw.py` | 1271, 1286, 1311 |
| MRI/collision folder path | `tools/operator/collisions.py` | 86-94 |
| Project hard-link path | `tools/ingest/linker.py` | `raw_linked` construction |
| User-controllable column (mirror) | `tools/ingest/resolver.py` | 83 |
| Registry writer / header | `tools/ingest/registry.py` | `REGISTRY_FIELDS` |
| GUI field label/key | `tools/operator/value_fields.py` | 53 |
| Per-project index grouping | `tools/generate_index.py` | 296-316 |
| Project resolve by short_name | `tools/gather_metadata.py` | 69-76 |
| Finder join fields | `tools/find_acq.py` | 45-46 |
| Spec (mirror) | `mfb-rdm-docs/06_REGISTRIES.md` | project_hint rows |
| Project spec / naming convention | `mfb-rdm-docs/05_PROJECTS.md` | §9 / PROJ-05 |
| Configs setting project_hint | `tools/configs/*.yaml`, `tools/templates/instruments/*.yaml` | `git grep -n 'project_hint:'` |
| Live data | `…/registries/registry_raw.csv` (13,582), `registry_projects.csv` (51) | — |

## 9 · Definition of done
- [ ] Rebased onto `main` (with G); G's `project_hint` additions included in the sweep.
- [ ] Scope (minimal vs full) confirmed with the data office; term = "project name".
- [ ] Phase A landed: terminology/(column) rename consistent across code, spec-mirror,
      GUI, configs, docs; tests + `validate_registries` pass.
- [ ] Phase B landed via a dry-run-first migration script: 43 folders renamed (closed
      projects handled as records only), `folder_location`/values migrated, construction
      sites drop `proj-`/lowercasing, hard links verified intact, Finder regenerated,
      a test ingest lands in the new folder name.
- [ ] Backups taken off-NAS; rollback verified available; done in a no-ingest window.
- [ ] Exe rebuilt/redeployed (coordinated with G); CHANGELOG + STATUS + INDEX updated.
