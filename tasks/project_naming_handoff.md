# Handoff — Project reference model: honest names everywhere + folder normalization

**Branch:** `refactor/project-naming` · **Worktree:** `…/projects/gjesus3-dev/project-naming`
**Version:** v4 — **FINAL, model-down** (supersedes the v1–v3 drafts in this file's git
history; those were diff-driven and were twice rewritten because the misnamed
`project_hint` column caused us to mis-model our own system — which is itself part of the
rationale below). **Status: DECIDED** — the model and every scope question below were
settled by the Data Office (Ryan) 2026-08-01/02. Do not re-open them; execute.

⚠️ **TRUE-PRODUCTION change.** Live surface: `registry_raw.csv` **header only** (13,582
rows — values untouched), `registry_projects.csv` (51 rows), **48 on-disk project
folders**, 48 `_project.yaml`, the 6 saved NAS recipes (deleted), and the operator exe.
`/raw/` is **never touched** (verified: sidecars/READMEs carry no project reference;
provenance paths are relative). Backup → dry-run → apply → verify → rollback-ready, in a
**no-ingest window**.

---

## 0 · Decisions (LOCKED — Data Office 2026-08-01/02)

1. **The "hint" concept is retired everywhere.** Operators refer to a project by its
   **name** — the thing a project naturally has. Full rename, not a label bandaid.
2. **Folder == name, verbatim.** No `proj-` prefix, no forced lowercase. What you type is
   the name is the folder researchers open.
3. **Spaces → hyphen.** Names are OS-safe; the GUI live-converts a typed space to `-` and
   shows the result. (Existing names already use hyphens.)
4. **Hard cut on the old key.** `registry.project_hint` stops being accepted — the
   resolver's unknown-key error (resolver.py:139) makes any stale config fail loudly and
   list the allowed keys. **No deprecated alias.**
5. **All 6 saved NAS recipes are DELETED** (`J:\gjesus3-data\recipes\*.yaml`), not
   migrated. Operators recreate recipes in the builder. Rationale: better to rebuild a
   recipe than to ever load one that errors.
6. **Spelling corrected to `AE-biomaGUNE`** (with the **a** — matches the animal
   facility's own `facility_id`s, 716/716 subject rows). The recipe/config typo
   `AE-biomeGUNE` is fixed at every live source in the same pass.
7. **All 48 on-disk folders rename** — including the 5 closed-but-still-present ones.
   Deleting those 5 (finishing the 2026-07-14 close-out) is a **separate, deliberate
   action**, not part of this migration.
8. **A new owning spec section** ("Project reference model", in `05_PROJECTS.md`) pins the
   concept, its vocabulary, and its consumer table — the fix for the root cause (naming
   drifted because no one section owned the concept).

---

## 1 · The model (the contract — implement this, and write it into 05_PROJECTS)

A project has exactly two identifiers:

| Identifier | Form | Role |
|---|---|---|
| **`project_id`** | `PROJ-XXXX` | Machine key. Immutable, systematic, what `registry_raw` stores. |
| **`name`** | human, unique (case-insensitively), OS-safe, hyphens not spaces | Human key. What operators type, what everyone says, **and the folder name, verbatim**. |

**Vocabulary by layer — the rename map:**

| Layer | Today (v3 world) | Target |
|---|---|---|
| GUI field label | "Project hint" | **"Project name"** (gloss: "the project's name — matches its folder") |
| Config/recipe key | `registry.project_hint` | **`registry.project_name`** (hard cut; old key = loud error) |
| `registry_projects` column | `short_name` (forced lowercase) | **`name`** (case-preserved) |
| Folder on disk | `proj-` + `lower(short_name)` | **`name`, verbatim** |
| `registry_raw` column | `project_hint` (holds PROJ-ids — the lie) | **`project_id`** (same values; header rename only) |
| Link-filename token | `${project_hint}` (yields the PROJ-id today) | **`${project_id}`** (same value, honest name) + **`${project_name}`** (the human name) |
| `_project.yaml` key | `short_name:` | **`name:`** |

**Resolution rule (state it once, in 05_PROJECTS; code cites the section):**
Operator input under `registry.project_name` matches an existing project's `name`
(**case-insensitively** — the FS is case-insensitive; linker.py:89 already does this) or a
`PROJ-XXXX` id → attach. No match, and `ingest.auto_create_projects` is on → auto-create a
project **named exactly as typed** (post space→hyphen), folder = name. After resolution
the pipeline carries **both**: `project_id` (resolved id → the registry column) and
`project_name` (the canonical name from `registry_projects` — canonicalize casing when the
input matched case-insensitively or by id).

**Invariants:** folder basename == `name`; `folder_location` == `/projects/<name>/`;
`registry_raw.project_id` ∈ `registry_projects.project_id`; names unique
case-insensitively. **One construction site:** `create_project.py` owns
name-validation + folder derivation (identity); every other consumer **reads** the stored
`folder_location` (the linker already does — linker.py:52-65; `collisions.py` is the one
offender to fix, see §3).

---

## 2 · Verified facts (live NAS + P-worktree code, 2026-08-01/02)

- `registry_raw`: **13,582 rows; `project_hint` = PROJ-id in 13,582/13,582** (51 distinct,
  0 slugs, 0 blanks). The rename is a **header-only** migration; values are already ids.
- `registry_projects`: 51 rows (43 active / 8 closed). **48 folders on disk** — 5 closed
  projects still have folders WITH live hard links (`proj-ae-biomegune-0219` 181 entries,
  `-0220` 245, `-1019` 40, `-0618` 63, `-0320` 18); 3 closed folders are absent
  (PROJ-0003/0008/0009). Every on-disk folder has a registry row; no orphans.
- `short_name` is lowercase in all 51 rows; the **only casing source is the operator
  recipes/configs** (`AE-biomeGUNE-${discovered.project}` — with the typo). 23 rows are
  AE-protocol projects (PROJ-0001–0022, PROJ-0051); numeric suffixes match the facility's
  `facility_id` codes exactly.
- The typo `biomegune`/`biomeGUNE` appears in **46 repo files** (mostly
  `tools/configs/`, plus 4 live AxioScan/MRI configs and comments) — sweep them all
  **except** `CHANGELOG.md` dated rows and `tasks/archive/` (append-only/never-edit).
- `resolver.py:83` `project_hint` in `USER_CONTROLLABLE_COLUMNS`; `:139-143` unknown
  `registry.*` key → hard error (this is what makes the hard cut safe);
  `:205` `project_hint` in `LINK_FILENAME_REGISTRY_FIELDS` (the token palette G added —
  post-resolve it yields the PROJ-id).
- `registry.py:18-61` `REGISTRY_FIELDS` (header, `project_hint` at line 61); **`:105`
  append HARD-FAILS on header mismatch** — after the header migration, the old deployed
  exe errors loudly instead of corrupting (good; but operators are blocked until the new
  exe is deployed — see §6 sequencing). `update_row` (`:167-222`) validates against the
  same shared constant, so the recovery/backfill tools inherit the rename automatically.
- `ingest_raw.py` **Step 9.5** (~line 1261): resolves via `linker.resolve_project`, logs,
  first-write-wins for `auto_create_project:` blocks, writes the resolved id back into
  cfg; the **lowercasing** (`short_name_norm = project_hint.lower()`) and a
  `projects/proj-…` string live here.
- `create_project.py`: `validate_short_name` (`:49`) already validates FS-safety — extend
  it, don't reinvent; `check_name_unique` (`:93`) is already case-insensitive; folder
  construction `f"proj-{name}"` at `:141` (+`:142-143`, `:215`, `:221`); `_project.yaml`
  written with `short_name:` (`:174`, `:182`).
- `collisions.py:86-94` `_project_folder` **re-derives** `proj-<hint>` instead of reading
  `folder_location` — the one derived-not-referenced offender.
- `linker.py:69-91` `resolve_project(hint)` → matches `project_id` exact then
  `short_name` case-insensitive; **returns the stored `folder_location`** — link paths
  are already reference-based. `provenance.csv` `output_path` is **relative**
  (`raw_linked/<link>`) — rename-safe, no migration.
- Consumers of the stored column (join by value — values don't change, only the key
  name): `find_acq.py:30,74,99` · `generate_index.py:66,278,301-307` (incl. the
  `--project` matcher: PROJ-id / short_name / folder basename) ·
  `gather_metadata.py:68-73,96,117,158-165` · `validate_registries.py:22,142-150,289`.
- **31 code files** contain `project_hint` (full list: `git grep -l project_hint --
  "tools/*.py"`), incl. `config.py`, `enrichment.py`, `subject_id.py`, `preview.py`,
  `templates.py`, `make_test_nas.py`, the three `relink_*.py`, the `backfill_*`
  tools, and tests (`test_find_acq`, `test_collisions`, `ingest/test_registry_fields`,
  `ingest/test_registry_update`, `operator/test_value_fields`, `test_phase3_enrichment`).
- `registry_subjects.project_alias` holds the bare NNNN code (joins the animal DB, spelled
  `AE-biomaGUNE` already via `animal_db.py:138`) — **independent of project naming;
  unaffected.** Sidecars (`metadata_sidecar.py`) carry no project field — `/raw` untouched.
- The 6 NAS recipes all carry `registry.project_hint:`; two also carry the typo.

**The three architecture findings this work fixes** (name them in the CHANGELOG):
(1) a column name that lied (`project_hint` holding ids — already cost two handoff
rewrites and nearly a wrong 13.5k-row migration); (2) the folder rule implemented in
three places (`create_project`, `ingest_raw` lowercase, `collisions` re-derivation)
instead of one; (3) no owning spec section, so vocabulary drifted per layer.
**Forward rule** (record in `CONTRIBUTING-docs.md`): every cross-layer concept gets one
name, one owning spec section (with a consumer table), and one construction site in code.

---

## 3 · Phase A — code + schema rename (branch work, no live data)

Order within the phase is free; land as one reviewed unit. Values in `registry_raw`
never change — **do not write a value migration.**

1. **Resolver** (`tools/ingest/resolver.py`): `USER_CONTROLLABLE_COLUMNS`
   `project_hint` → `project_name` (`:83`). In `LINK_FILENAME_REGISTRY_FIELDS` (`:205`)
   replace `project_hint` with `project_name` **and** add `project_id` (behavior-compat:
   today's `${project_hint}` yields the id; `${project_id}` preserves that, `${project_name}`
   adds the human name). Update the docstring at `:235`.
2. **Pipeline** (`tools/ingest_raw.py` Step 9.5): read `cfg["project_name"]`; after
   resolve set **both** `cfg["project_id"]` (→ registry row) and `cfg["project_name"]`
   (canonicalized name). Auto-create: **drop the `.lower()`**; pass the name verbatim
   (GUI has already hyphenated spaces; CLI path validates via `create_project`'s
   validator). Fix the `projects/proj-…` strings in the WARN messages.
3. **Registry** (`tools/ingest/registry.py`): `REGISTRY_FIELDS` `project_hint` →
   `project_id` (`:61`); row-builder maps `"project_id": cfg.get("project_id","")`
   (`:318`). **Note the deliberate asymmetry:** the *input* is `project_name`; the
   *stored column* is `project_id` — the resolve step joins them. Do NOT name the column
   `project_name`; it holds ids.
4. **Single construction site** (`tools/create_project.py`): rename
   `validate_short_name` → `validate_project_name` (keep/extend FS-safety: reject
   `\/:*?"<>|`, leading/trailing dots/spaces; hyphens/underscores/dots/alnum OK); folder
   = `name` verbatim (`:141-143`); `_project.yaml` writes `name:` (`:174,:182`); registry
   row writes `name` + `folder_location = /projects/<name>/` (`:215,:221`).
5. **Fix the re-derivation** (`tools/operator/collisions.py:86-94`): resolve the project
   and use its stored `folder_location`; only for a *not-yet-created* project (preview of
   an auto-create) fall back to `projects/<name>/raw_linked` via the same
   `create_project` helper. No `proj-` string survives.
6. **GUI** (`tools/operator/value_fields.py:53` key+label; `app.py`; `static/app.js`,
   `static/mri.js`; both help pages; `templates.py`, `preview.py`): key
   `registry.project_name`, label **"Project name"**, and the **space→hyphen live
   conversion** on that input (operator sees the converted value as they type). Token
   palette inherits the resolver change (single source — G's design).
7. **Consumers** (mechanical key rename, same join values): `find_acq.py`,
   `generate_index.py` (keep the `--project` matcher accepting PROJ-id / name / folder
   basename — under the new model the last two converge), `gather_metadata.py`,
   `validate_registries.py`, `relink_projects.py`, `relink_mri_regen.py`,
   `relink_axioscan_collisions.py`, `backfill_*`, `enrichment.py`, `subject_id.py`,
   `config.py`, `make_test_nas.py`.
8. **Configs + templates sweep**: `registry.project_hint:` → `registry.project_name:`
   across `tools/configs/*.yaml` (46 files) and `tools/templates/instruments/*.yaml`
   (7 files); fix `AE-biomeGUNE` → `AE-biomaGUNE` in the same pass (46 typo files;
   skip CHANGELOG dated rows + `tasks/archive/`).
9. **Tests**: update the hard-coded `project_hint` / `proj-…` fixtures
   (`test_find_acq`, `test_collisions`, `ingest/test_registry_fields`,
   `ingest/test_registry_update`, `operator/test_value_fields`,
   `test_phase3_enrichment`); add: name-validation cases (space→hyphen, unsafe chars),
   case-insensitive resolve, auto-create preserves casing, folder==name.
10. **Docs (the mirror)**: `06_REGISTRIES` column rename (mirror with
    resolver/registry — keep exact); **new "Project reference model" section in
    `05_PROJECTS`** (the §1 contract + consumer table; PROJ-05/§9 provisional-naming
    text updates to point at it); `10_TOOLS` (pipeline Step 9.5 text, side-effect
    inventory rows 3/7/9/10 wording); `INGEST_CLI.md`, `OPERATOR_FAQ.md`, `FAQ.md`,
    `GLOSSARY.md` ("Project name" entry; retire "hint"); equipment workflow notes if
    grep hits; `CONTRIBUTING-docs.md` gains the forward rule (§2 above).

**Phase A verify:** full test run; `validate_registries --dry-run` against a
`make_test_nas` fixture; a dry-run CLI ingest with `registry.project_name`; confirm a
config still carrying `registry.project_hint` fails with the loud unknown-key error.

---

## 4 · Phase B — the live migration (no-ingest window; Ryan supervising)

One **dedicated, resumable script** (`tools/migrate_project_naming.py`), `--dry-run`
default, generating a reviewable plan before `--apply`. Never ad-hoc edits.

1. **Freeze**: confirm no operator ingest running (window is the weekend); announce.
2. **Backups off-NAS** (dated dir, established `gjesus3_*_backup_YYYYMMDD` pattern):
   `registry_raw.csv`, `registry_projects.csv`, all 48 `_project.yaml`, the 6 recipes,
   and a full listing of `projects/`.
3. **Generate the mapping** (script, from the live registry — never hardcoded in docs):
   per row: old folder → new `name`/folder. Rules: drop `proj-`; the 23 AE rows become
   `AE-biomaGUNE-<code>` (typo corrected, casing restored); person/topic rows keep their
   slug minus the prefix (`proj-claudia` → `claudia`, `proj-laura-tholt` → `laura-tholt`).
   Expected: 51 rows total; 48 with an on-disk rename; 3 closed-absent rows get
   record-only updates (new `name`/`folder_location`, no move). **Human-review the
   printed table before `--apply`.**
4. **Apply, in this order** (each step verified before the next; script resumable —
   skip-if-already-done):
   a. `registry_raw.csv` **header** `project_hint` → `project_id` (atomic temp+replace
      under the registry lock; 2026-06-09 operator→researcher migration is the
      precedent). Values untouched.
   b. `registry_projects.csv`: header `short_name` → `name`; per-row `name` (new casing)
      + `folder_location` (`/projects/<name>/`). Atomic, locked.
   c. Folder renames: 48 × `os.rename` per the mapping (case-only components still get
      the `proj-` drop, so every rename is real; FS is case-insensitive — treat casing
      as cosmetic, never a conflict source). Hard links are untouched by a parent
      rename — `/raw` inodes never move.
   d. Rewrite the 48 `_project.yaml`: key `short_name:` → `name:`, value = new name
      (and `project_id` stays).
   e. **Delete the 6 NAS recipes** (backed up in step 2).
5. **Verify (script + eyes):** every active row's folder exists at `folder_location`;
   zero `proj-*` dirs remain under `projects/`; hard-link spot-checks (same inode as
   `/raw` — reuse the `relink_projects.py` verify pattern); `validate_registries` clean
   (its project check joins id↔id and now reads honestly); `find_acq` join resolves for
   all 13,582 rows; regenerate the Finder (`generate_index --per-project`) and confirm
   per-project counts are unchanged vs pre-migration.
6. **Rollback path** (keep until the smoke tests pass): the backups + the generated
   mapping; a `--reverse` mode restores folder names and both CSVs byte-for-byte.

---

## 5 · Phase C — exe + records (same window, immediately after §4)

1. **Merge to `main`** (Phase A+B code; the migration script stays in `tools/` as the
   paper trail). Merging before the nightly matters — see §6.
2. **Rebuild + redeploy `gjesus3_ingest.exe`** (label, key, JS, resolver all changed):
   off-OneDrive build dir, backup-first staged-copy deploy to
   `\\GJESUS3\…\tools\`, checksum-verify — the exact 2026-07-20 pattern.
3. **Production smoke test** through the deployed exe: one real ingest into a renamed
   project (e.g. `AE-biomaGUNE-1123`) — confirm the GUI shows "Project name", the link
   lands in the **new** folder, no `proj-` folder is created, the registry row's
   `project_id` is the PROJ-id; then remove the test acq (Data-Office manual,
   backup-first — follow the **Side-effect inventory**, `10_TOOLS` §2.1, incl. the
   `.acq_id_seq.json` note).
4. **Records:** CHANGELOG entry (append; name the three architecture findings + the
   forward rule); `tasks/STATUS.md` (close the item; note the recipes deletion so
   operators aren't surprised); `00_INDEX.md` Last-Updated; delete this handoff on
   landing (drop-temp-handoffs precedent).

---

## 6 · Sequencing & safety rails (read before starting Phase B)

- **The old exe is incompatible the moment §4.4a runs** — its bundled `registry.py`
  hard-fails the append on the new header (loud, not corrupting). Therefore: header
  migration and exe redeploy happen in the **same window**, and the window isn't over
  until the new exe is deployed and smoke-tested.
- **The WorkstationOps nightly Finder rebuild (03:00) uses the repo's `main`.** If the
  live data migrates but P isn't merged before 03:00, `generate_index` still reads
  `project_hint` → every per-project page comes up empty. **Merge to `main` before the
  data migration** (or regenerate manually right after and merge same-day — but merging
  first is the clean order).
- Registry writes: atomic temp+`os.replace` under `registries/.registry.lock`
  (`csv_safe`/`locking` conventions; `recover_subject_metadata.py` is the reference).
- Worktree/branch hygiene: work stays in THIS worktree; commit freely, **never push
  without Ryan's explicit OK**; stage specific files — **never `contacts.xlsx`**.
- If anything in §2's verified facts doesn't match what you observe live, **stop and
  re-verify before applying** — this document was written 2026-08-02; the NAS moves.

## 7 · Explicit non-goals (do not do these here)

- Deleting the 5 closed-but-present folders (separate close-out action, Ryan's call).
- The semantic re-projecting of person/topic projects (BACKLOG; this migration is
  mechanical normalization and deliberately independent of it).
- Renaming `registry_projects.project_id` / the `PROJ-XXXX` scheme (stays).
- Any `registry_raw` **value** rewrite (there is nothing to rewrite — they're ids).
- Tightening `validate_registries`' project check to a hard failure (optional later).

## 8 · Definition of done

- [ ] Phase A landed on the branch: rename map of §1 applied everywhere; single
      construction site; collisions re-derivation fixed; configs/templates/typo swept;
      tests green incl. new name-rule cases; stale `project_hint` config fails loudly.
- [ ] 05_PROJECTS owns the model; 06_REGISTRIES mirror exact; forward rule in
      CONTRIBUTING-docs.
- [ ] Phase B executed in the window: header + projects-registry migrations, 48 folders
      renamed, 48 `_project.yaml` rewritten, 6 recipes deleted; verification suite
      clean; rollback assets retained until smoke test passes.
- [ ] Phase C: merged to `main` (before the 03:00 nightly), exe rebuilt/redeployed/
      smoke-tested in production, Finder regenerated, records written, this file deleted.
