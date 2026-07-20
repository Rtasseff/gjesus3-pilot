# Handoff — project naming: "project hint" → "project name" + folder normalization

**Branch:** `refactor/project-naming` · **Worktree:** `…/projects/gjesus3-dev/project-naming`
**Base:** `main` @ `7f0eba2`.
**Status:** not started — and **must wait for branch G** (`feat/gui-operator-polish`) to
merge first (see §0). This doc is self-contained.

> **Data model corrected 2026-07-20.** An earlier draft of this handoff assumed the
> `registry_raw.csv` `project_hint` column stores the folder *slug* and would need
> re-casing across 13,582 rows. **That is wrong.** Verified against the live registry:
> the stored `project_hint` value is the resolved **`PROJ-XXXX` id** (all 51 distinct
> values are PROJ-ids; zero are slugs). Consequence — **the folder rename does NOT touch
> `registry_raw` at all.** The live-data change is confined to `registry_projects.csv`
> (51 rows) + the 43 folders + the folder-construction code. Read §2 carefully.

⚠️ **Still a TRUE-PRODUCTION change** — 43 live project folders on
`\\gjesus3\gjesus3\gjesus3-data\projects\`, plus `registry_projects.csv`. And `project_hint`
sits in the **integrity mirror** (`06_REGISTRIES ↔ resolver.py/registry.py`), so any schema
touch must keep spec and code in lockstep. Back up first, dry-run everything, do the folder
move in a no-ingest window, keep a rollback.

---

## 0 · CRITICAL first step — rebase onto the latest `main` (with G)

This branch changes `project_hint`, which appears in files branch **G**
(`feat/gui-operator-polish`) also edits (`app.js`, `app.py`, `value_fields.py`) — and G
*adds* a `${project_hint}` token chip, and (via its addendum) wiring that calls
`generate_index --project`. So:

```
cd "…/projects/gjesus3-dev/project-naming"
git merge main            # bring in G's merged work (and the 2026-07-20 index-refresh changes)
# resolve any conflicts, THEN start the sweep so it covers G's additions.
```
If G has **not** merged yet, stop and confirm with the data office — running the rename
first means you miss G's new references and redo the sweep.

Note: `main` also now has the **index-refresh** changes (`generate_index.py --project`,
`ingest_raw.py --refresh-index`, `_touched_project_hints`, the GUI per-project refresh from
G's addendum). Your rename must cover the new `--project`-mode uses of the project key too.

---

## 1 · What the data office wants (the end state)

Two linked asks from the 2026-07-17 operator test:

**(a) Rename the operator-facing concept "project hint" → "project name".** Operators find
"hint" confusing; what they type *is* the project's name. Change the GUI field label, the
help/docs wording, and (scope decision — §2) possibly the config/GUI input key.

**(b) Normalize the project folders so the folder name == the project name.** Today the GUI
shows e.g. `AE-biomeGUNE` but the folder is `proj-ae-biomegune-0525` (a `proj-` prefix +
forced lowercase). The ask:
- **drop the `proj-` prefix** on all project folders,
- **restore casing** (`ae-biomegune` → `AE-biomeGUNE`) where it applies,
- **make each project's "project name" equal its new folder name**, and
- make new ingests produce that name (no `proj-`, preserved casing) going forward.

Desired result: GUI field **"Project name" = the exact folder name** = e.g.
`AE-biomeGUNE-0525` (person/topic projects become `claudia`, `laura-tholt`, … — just the
`proj-` dropped). **`project_id` (`PROJ-000N`) stays the systematic unique id** and is what
`registry_raw` actually stores — don't conflate the human name with it.

---

## 2 · The current model (VERIFIED) — and the scope decision

**"project_hint" means two different things at two stages — this is the crux:**

1. **As operator input** (`registry.project_hint:` in a YAML/GUI recipe) it's a *loose
   pointer* to a project — a `short_name` or a `PROJ-id`. At ingest the pipeline **resolves**
   it against `registry_projects.csv` (`ingest_raw.py:1271`, by `short_name`/`project_id`),
   **auto-creating** a project if nothing matches. Hence "hint".
2. **As the stored `registry_raw.csv` column** it is the **resolved `PROJ-XXXX` id** — NOT a
   name, NOT a slug. (Verified 2026-07-20: 13,582 rows, 51 distinct values, all `PROJ-XXXX`.)
   `find_acq`/`generate_index` then join that id → `registry_projects` for the folder.

`registry_projects.csv` columns: `project_id` (`PROJ-000N`), `short_name`, `description`,
`owner`, `start_date`, `status`, `last_activity`, `folder_location`, `notes`. Folder =
`proj-` + `short_name.lower()` on auto-create (`create_project.py:141`; the lowercasing is
`ingest_raw.py:1286`). So **the folder-slug tracks `short_name` (lowercased) — the human
name lives in `registry_projects`, while `registry_raw.project_hint` holds the id.**

**Why this matters:** renaming the *column* `project_hint` → `project_name` would put
`PROJ-0011` values in a column called "name" — a misnomer. And re-casing those values is
pointless: they're ids, and the *folder name* lives in `registry_projects`, not here.

**Scope decision to confirm with the data office (before Phase B):**
- **Minimal (recommended, lowest risk).** Relabel only the operator-facing **display**:
  GUI field label `Project hint` → `Project name`, plus help/docs wording. Keep the config
  key and the stored column named `project_hint`. **Zero schema change, zero data migration.**
  Fully satisfies the operator confusion.
- **Rename the input key too.** Also rename the operator-facing **input** key
  `registry.project_hint` → `registry.project_name` (`resolver.USER_CONTROLLABLE_COLUMNS`,
  `value_fields.py:53` key, every `tools/configs/*.yaml` + `templates/instruments/*.yaml`,
  the resolver/registry mirror + `06_REGISTRIES`). If you do this, decide what the **stored
  column** is called: keep `project_hint`, or rename it to something accurate for "a resolved
  PROJ-id" (e.g. `project_id`/`project_ref`) — **do not** name it `project_name` while it
  holds ids. Either way the stored **values stay `PROJ-XXXX` — no value migration.**
- **Avoid:** a `project_name` column full of `PROJ-XXXX`, and any re-casing of the 13,582
  `registry_raw` rows. Neither is needed and both add risk.

Per the repo rule, vocabulary decisions are Data Office calls; the user is effectively
choosing "project name" as the term — pin down minimal-vs-input-key before the schema touch.

---

## 3 · Blast radius (grounded)

- **`project_hint` = 277 occurrences across 106 files** (`git grep -c project_hint`) — but
  most are docs/configs/tests; the *live-data* surface is small (see below).
- **Integrity mirror:** `06_REGISTRIES ↔ resolver.py/registry.py`
  (`CONTRIBUTING-docs.md#cross-reference-consistency`). `resolver.py:83` lists `project_hint`
  in `USER_CONTROLLABLE_COLUMNS`; `registry.py` writes the column. Any key/column rename
  changes spec + code together.
- **Live data actually touched by (b):** `registry_projects.csv` (51 rows — `folder_location`
  + `short_name`) and the **43 active folders**. **`registry_raw.csv` is NOT touched** — its
  `project_hint` column holds `PROJ-ids`, stable across the folder rename.
- **Folder-name construction sites** (change in lockstep with the folder move, or new ingests
  recreate `proj-…` names):
  - `tools/create_project.py:141` `folder_name = f"proj-{name}"` (+ `:143`, `:221`). **Canonical.**
  - `tools/ingest_raw.py:1286` `short_name_norm = project_hint.lower()` (the lowercasing),
    `:1311` path, `:1271` resolve-by-short_name.
  - `tools/operator/collisions.py:86-94` `_project_folder` builds `projects/proj-<hint>/raw_linked`
    (here `hint` is the operator's short_name at preview time, not the stored PROJ-id).
  - `tools/ingest/linker.py` — project hard-link path; confirm it takes the folder from the
    resolved `folder_location`, not a rebuilt `proj-` string.
- **Consumers (join by id / read the folder):**
  - `tools/generate_index.py` groups per-project by the stored `project_hint` (PROJ-id) and
    writes each per-project `index.html` under `folder_location` (`_write_per_project`, and
    the new `--project` targeted mode added 2026-07-20 — matches PROJ-id/short_name/folder).
  - `tools/find_acq.py:45-46,74` — joins `registry_raw.project_hint` (PROJ-id) → `project_id`.
  - `tools/gather_metadata.py:69-76` — resolves project by `short_name`/`project_id`.
  - `tools/operator/value_fields.py:53` — GUI field `{"key":"registry.project_hint","label":"Project hint"}`.
  - GUI: `app.py`, `static/app.js`, `static/mri.js`.
  - **All `tools/configs/*.yaml` + `templates/instruments/*.yaml`** set `project_hint:` (input key).
  - Docs: `05_PROJECTS`, `06_REGISTRIES`, `08_METADATA`, `09_MODALITIES`, `10_TOOLS`,
    `tools/INGEST_CLI.md`, `OPERATOR_FAQ.md`.
  - Tests: `test_find_acq.py`, `test_collisions.py`, `test_registry_fields.py` hard-code
    `project_hint` + `proj-…` folder names.
- **`validate_registries`** does an (unenforced) `project_hint ↔ projects` string join — it
  joins the stored PROJ-id to `project_id`, so it keeps working through the folder rename (no
  value change). If you rename the stored column, update both sides.

---

## 4 · Phase A — the rename (terminology / input key), no folder move

A coherent, reviewable unit **before** the folder migration.

- **Always:** GUI field label → **"Project name"** (`value_fields.py:53` label + the
  `hint:"link to a project"` gloss); sweep operator-facing docs/help wording; keep
  `project_id` distinct.
- **If renaming the input key** (per §2 option 2): `registry.project_hint` →
  `registry.project_name` across `resolver.USER_CONTROLLABLE_COLUMNS`, `value_fields.py`
  key, every config + instrument template, and the `06_REGISTRIES ↔ resolver/registry`
  mirror. Decide the **stored** column name (keep `project_hint` or → `project_id`/`project_ref`;
  never `project_name`-holding-ids). A live header migration only if you rename the stored
  column — precedent: the 2026-06-09 operator→researcher header migration (back up first);
  **values are unchanged (still `PROJ-ids`).**
- Respect status markers — a schema touch on a ✅ DECIDED registry item goes in the
  append-only `CHANGELOG.md` with the spec/code mirror kept exact.

**Land Phase A, verify (`test_*` + `validate_registries` dry-run), commit.**

---

## 5 · Phase B — folder normalization (the live-data move)

Only after Phase A. **This does not touch `registry_raw`** — it renames folders and updates
`registry_projects.csv` + the construction code. Still: **backup → dry-run → apply → verify
→ rollback-ready**, in a **no-ingest window**.

1. **Back up off-NAS first:** `registry_projects.csv` (byte-copy, dated dir — the established
   pattern) and a listing of the current project folders. (`registry_raw.csv` is untouched,
   but back it up too — cheap insurance.) Confirm no operator is ingesting.
2. **Build an explicit old→new folder mapping** (43 entries) — do **not** assume one regex.
   `proj-ae-biomegune-0525` → `AE-biomeGUNE-0525`; `proj-claudia` → `claudia`;
   `proj-laura-tholt` → `laura-tholt`. Casing is only restored where it applies (AE-biomeGUNE);
   person/topic slugs just drop `proj-`. Note the FS is **case-insensitive** (Windows/QNAP),
   so the case change is cosmetic to the FS — the `proj-` drop is the real rename.
3. **Hard links survive a folder rename** (renaming the parent dir doesn't touch the
   `raw_linked/` inodes into `/raw`). Update in the same migration:
   - `registry_projects.csv` `folder_location` **and `short_name`** (so `short_name` == the
     new folder name == the "project name"). This is the only registry write.
   - the **construction sites in §3** so *new* ingests write the new names: `create_project.py:141`
     `f"proj-{name}"` → `name`; drop the `ingest_raw.py:1286` `.lower()`; fix `collisions.py`.
   - **verify** whether per-project `provenance.csv` / `_project.yaml` store the folder path
     (check `07_PROVENANCE` + `linker.py`); migrate if so.
   - per-project `index.html` regenerates from `folder_location` — just re-run
     `generate_index.py --per-project` after (or `--project <id>` per project).
4. **Apply** the folder renames (`os.rename`) per the mapping; write `registry_projects.csv`
   atomically (temp+replace under the registry lock — see `recover_subject_metadata.py`).
5. **Verify:** every folder exists under its new name; `folder_location` points at it; hard
   links still resolve (same inode; `relink_projects.py` reconciles any slips);
   `registry_raw` join still resolves (PROJ-id → new folder); `validate_registries` clean;
   regenerate the Finder and confirm per-project counts unchanged; one throwaway dry-run
   ingest into a renamed project confirms it links into the new folder (no `proj-` recreated).
6. **Rollback:** keep the pre-move `registry_projects.csv` backup + the mapping; a reverse
   script restores names + the CSV.

Write this as a **dedicated migration script** with `--dry-run` default, not ad-hoc edits.

---

## 6 · Interactions & cautions (read before Phase B)

- **An adjacent semantic re-projecting effort is already planned.** BACKLOG → "Legacy Zeiss
  microscopy … BEST-GUESS ingest" + "Project re-organization via researcher feedback"
  (05_PROJECTS §9 / PROJ-05): the data office does **not** want per-user project folders
  long-term and plans to **re-home/re-name** historical microscopy projects from researcher
  feedback. Your Phase B is **mechanical normalization** (drop `proj-`, fix case) — separate
  from that **semantic** re-projecting, but the same folders. **Flag ordering to the data
  office:** if projects are about to be re-named anyway, a mechanical rename now may be partly
  redundant or should fold into that migration. Don't silently do both.
- **Integrity mirror + DECIDED items:** keep `06_REGISTRIES ↔ resolver/registry` in lockstep;
  record any schema touch in the append-only `CHANGELOG.md`.
- **Closed projects (8):** folders deleted at close-out; registry rows survive. Update their
  `registry_projects` records **without** moving a non-existent folder (skip the move, migrate
  the record). `generate_index` already skips `status=closed` for per-project pages.
- **Single-operator concurrency safety:** do the move when no ingest is running.

---

## 7 · Sequencing summary
1. Wait for **G** to merge to `main`; `git merge main` here (§0).
2. **Phase A** (label + optional input-key rename) — one commit/PR; `test_*` +
   `validate_registries` pass; land.
3. Confirm scope (minimal vs input-key) + the re-projecting ordering with the data office.
4. **Phase B** (folder normalization) — dedicated dry-run script, backup, no-ingest window,
   verify, rollback-ready — separate commit/PR. `registry_raw` untouched.
5. If the input key / GUI changed, rebuild + redeploy the operator exe — coordinate with G's
   rebuild so operators get one consistent build.
6. CHANGELOG (append) + `tasks/STATUS.md` + `00_INDEX.md` Last-Updated bump.

## 8 · File / reference
| Concern | File | Anchor |
|---|---|---|
| Folder name construction (canonical) | `tools/create_project.py` | 141 `proj-{name}`, 143, 221 |
| project_hint→folder + lowercasing | `tools/ingest_raw.py` | 1271, 1286, 1311 |
| MRI/collision folder path | `tools/operator/collisions.py` | 86-94 |
| Project hard-link path | `tools/ingest/linker.py` | `raw_linked` construction |
| User-controllable input key (mirror) | `tools/ingest/resolver.py` | 83 |
| Registry writer / header (stored column) | `tools/ingest/registry.py` | `REGISTRY_FIELDS` |
| GUI field label/key | `tools/operator/value_fields.py` | 53 |
| Per-project index + `--project` mode | `tools/generate_index.py` | `_write_per_project`, `--project` |
| Project resolve by short_name | `tools/gather_metadata.py` | 69-76 |
| Finder join (id → project) | `tools/find_acq.py` | 45-46, 74 |
| Spec (mirror) | `mfb-rdm-docs/06_REGISTRIES.md` | project_hint rows |
| Project spec / naming convention | `mfb-rdm-docs/05_PROJECTS.md` | §9 / PROJ-05 |
| Configs setting the input key | `tools/configs/*.yaml`, `templates/instruments/*.yaml` | `git grep -n 'project_hint:'` |
| Live data touched by (b) | `…/registries/registry_projects.csv` (51) + 43 folders | (registry_raw NOT touched) |

## 9 · Definition of done
- [ ] Rebased onto `main` (with G + the index-refresh changes); G's additions covered.
- [ ] Scope confirmed with the data office; term = "project name"; `project_id` kept distinct.
- [ ] Phase A landed: label (+ optional input-key) rename consistent across code, spec-mirror,
      GUI, configs, docs; stored values remain `PROJ-ids` (no value migration); tests +
      `validate_registries` pass.
- [ ] Phase B landed via a dry-run-first script: 43 folders renamed (closed projects handled
      as records only), `registry_projects` `folder_location`/`short_name` migrated,
      construction sites drop `proj-`/lowercasing, hard links + the registry_raw join verified
      intact, Finder regenerated, a test ingest lands in the new folder name.
- [ ] Backups off-NAS; rollback verified; done in a no-ingest window.
- [ ] Exe rebuilt/redeployed if the input key/GUI changed (coordinated with G); CHANGELOG +
      STATUS + INDEX updated.
