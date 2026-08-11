# Handoff — Project Manager GUI

**Branch:** `feat/project-manager-gui` · **Worktree:** `gjesus3-archive\gjesus3-dev\project-manager-gui`
**Status:** 🔶 DRAFT — scoped, not implemented. You are the implementing agent.
**Scoped by:** Claude (session 2026-08-11), against live NAS state and the code as of `b882e4a`.

---

## 0. Read this first

This is a **scoping** document, not a design you should follow blindly. It records what
the requester asked for, what the code and the live NAS actually look like today, and
**four decisions that must be settled before you write the first line** (§2). Several
things the request assumes to exist do **not** exist; several things it asks you to
create **already** exist. Those are called out in §1.4 and §3 — read them before
estimating.

Delete this file as part of the landing commit, the same way
`gui_browse_sort_and_reload_handoff.md` was retired when its work merged.

---

## 1. What was asked for

A GUI for **students / researchers** to manage projects, in the same idiom as the ingest
tools now on the NAS at `\\GJESUS3\gjesus3\gjesus3-data\tools\`. Five capabilities:

1. **Update project** — list all projects from `registry_projects.csv`, select one, show
   all fields, allow editing a subset: `description`, `owner`, `status` (dropdown),
   `notes`.
2. **Create new project** — write the registry row **and** create the project folder.
3. **Import data from `raw`** — present something like the Finder (`registries/index.html`)
   to filter/search acquisitions, select them with checkboxes, and import: create the
   hard links in `raw_linked/`, and record the new project association.
4. **Import data from `local`** (including mounted drives) — folder browser in the same
   style as the other tools, tick files, copy them into the project (with a choice of
   destination subfolder).
5. **Encourage a project subfolder convention** — `working/`, `outputs/`, `metadata/`,
   `raw_linked/` — documented as *recommended* in the researcher-facing docs,
   auto-created by any tool that makes projects, and **backfilled** onto existing
   projects that lack them.

In both import paths the project's `provenance.csv` must be updated, automated as far as
possible, prompting the user only for what genuinely can't be derived.

**Explicitly out of scope, backlogged instead** (both items are already written into
`tasks/BACKLOG.md` on this branch — do not re-add them):
- **Project rename** — low priority. Touches the folder, `folder_location`, every
  `raw_linked` path, per-project `index.html`, and the `name`↔folder identity rule.
- **`status` → `closed` semantics** — medium priority. What actually happens on close.

---

### 1.4 Corrections to the request's assumptions

Four things worth knowing before you plan. Each is verified against the live system.

**(a) The pending-hard-links queue EXISTS — on another branch. Do not write a second one.**
It was built on `feat/ni-live-hardening` (worktree `gjesus3-dev\ni-live-hardening`) to
solve the same problem from the other end: the NI acquisition console is a **Mac**, and
macOS over SMB refuses `os.link` with `ENOTSUP [Errno 45]`, so an on-box ingest registers
the acquisition perfectly but cannot create the `raw_linked/` link.

| Piece | File | Role |
|---|---|---|
| Writer | `tools/ingest/pending_links.py` | queued from the `except` in `ingest_raw.py` when `create_hardlink` raises |
| Worklist | `registries/pending_links.csv` | one row per acquisition still needing its link |
| Drainer | `tools/relink_pending.py` | run from Windows: `--nas-root J:/gjesus3-data` |

**Do not copy it into this branch and do not reimplement it.** Two implementations of one
deferred-link queue is exactly the outcome to avoid. See §1.6 for how it gets to `main`
and what you must adapt — this is settled, but there is a real trap in it.

Worth knowing: it records the full recovery payload (`project_id`, `link_name`,
`raw_primary_canonical`, `primary_kind`, `reason`, `host_os`) so the drain pass can
reconstruct the exact `create_hardlink` call, and the ingest drops a visible
`<link_name>.PENDING-LINK.txt` stand-in in `raw_linked/` so the researcher sees that
something is coming rather than an empty folder. **Reuse that stand-in idea** — a student
who imports 20 acquisitions on a machine that can't link needs to see 20 somethings.

**(b) Multi-project is a semicolon list in `project_id` — ✅ DECIDED 2026-08-11.**
An acquisition can belong to more than one project. **Record that as a
semicolon-separated list in the existing `project_id` column** —
`PROJ-0001;PROJ-0007`. Not a mapping table, not the `notes` column.

This is the **house convention, already used for exactly this**, so you are following a
pattern rather than inventing one:

| Column | Packed by | Documented |
|---|---|---|
| `modalities_in_study` | ingest | 06_REGISTRIES §"semicolon-separated DICOM modality codes (e.g. `PT;CT`)" |
| `subject_ids` (note the plural) | `ingest/registry.py:281` — `";".join(...)` | 08_METADATA |
| `discovered.animal_codes` | `ingest/config.py:576` | — |

A separate many-to-one mapping table was considered and **rejected as
over-engineering**: this is a simple registry, and converting it to a real DB schema is
a future endeavour, not this tool's job.

**What you must fix for it to work.** `project_id` is single-valued *in the readers*
today; five sites join or group on the whole cell and must learn to split. They fail
**silently**, which is why they are listed individually:

| Site | What happens with `A;B` today | Needed |
|---|---|---|
| `generate_index.py:309` (per-project grouping) | forms a bogus `"PROJ-0001;PROJ-0007"` group → the acq appears in **neither** project's index | split; emit into each |
| `generate_index.py:66` (payload) | shows the raw joined string | split; Finder may carry the list (see below) |
| `find_acq.py:42,74` (project join) | `proj_idx.get("A;B")` misses → the record silently loses its project folder / name / owner | split; join each |
| `validate_registries.py:289` | `PROJ_ID_RE.match` fails on the list, so the existence check is **skipped, not failed** | split; validate each id |
| `find_acq.py:103` (filter) | substring test — accidentally still matches | make it deliberate, not accidental |

The `generate_index.py` grouping one is not optional: without it, the first acquisition
your tool adds to a second project **vanishes from the index of the project it was
already in.** That is a visible regression, introduced by this work.

Ryan's call on the Finder: carrying a semicolon list for project and owner in the index
is fine, **or** the Finder may show only the first project — but either way **the
registry must record all of them.** Prefer carrying the list; the split is done by then
anyway.

Doc consequence: `project_id` is an **integrity mirror** (06_REGISTRIES ↔
`ingest/registry.py`), so 06_REGISTRIES' column definition must be updated to say the
column is a semicolon-separated list, in the same words `modalities_in_study` uses.
This is a Data Office decision and it has been made — record it, don't re-litigate it.

Related but **not** superseded: the *"provenance-driven project index"* backlog item
(§1.5). It predicted precisely this — `project_id` *"stamped once at ingest"*,
researchers *"later reorganize / re-home acqs"*. The semicolon list fixes the
**recording**; that item is about the **view**. Leave it open.

**(c) `create_project.py` already exists and already does most of "Create new project".**
`tools/create_project.py` mints the `PROJ-NNNN` id, validates + normalizes the name via
`ingest/project_naming.py`, creates the folder and `raw_linked/`, writes `_project.yaml`
from the bundled template, writes an empty `provenance.csv`, and appends the registry
row. **Do not reimplement any of that.** Import it, or refactor its `create_project()`
into something callable, and let the GUI be a front-end over it — exactly as the ingest
GUI is a thin front-end over the operator core. The one change it needs is §4.5 (the new
subfolders).

**(d) `05_PROJECTS §3` already specifies a folder structure, and `metadata/` in it is
🕗 PLANNED/DEFERRED.** This is not a blank slate. §3's tree already has `raw_linked/`,
already has `metadata/` with `study.json` / `biosamples.json` / `<acq_id>.json`, and
carries an explicit deferral note saying the layer *"exists on none of the live
projects."* `RESEARCHER_GUIDE.md:110` repeats that deferral. So your doc edit is **not**
"add a new convention" — it is "add `working/` and `outputs/`, and change `metadata/`
from *not created* to *created empty, contents still deferred*." Keep the two ideas
apart: creating the directory is now done; the study-metadata **layer** (writers, file
shapes, close-out merge) stays deferred. Do not delete the 🕗 marker — narrow it.

---

### 1.5 Prior art — two backlog items already cover half of this

Read both before designing. They are in `tasks/BACKLOG.md`, both raised 2026-06-23.

**"Finder — Select-in-Finder → assemble a project"** *is* the import-from-raw feature
(§4.3), already scoped. It even names the blocker: the Finder is a static page over
`file://`, so *"by browser security it cannot touch the filesystem"* — actually creating
hard links *"requires a helper / CLI / back-end beyond the browser page."* **Your tool
has a server, so that blocker dissolves.** The item's design rule stands and is repeated
in §4.3: drive it through the existing linker + provenance step *"rather than a parallel
path, so project links and provenance stay identical to ingest-time links."* When this
lands, mark that item done or superseded — don't leave it looking open.

**"Finder — provenance-driven project index"** is the reason §1.4b is acceptable rather
than a design flaw. Shape still open — *"discuss before building"* — so **do not build it
here.** Just don't contradict it: keep provenance complete and accurate on every import,
because it is the intended source of truth for what a project actually contains.

---

### 1.6 How `pending_links` reaches `main` — and the trap in it

**Decision: cherry-pick the single commit `0418ca6`; do NOT merge
`feat/ni-live-hardening`.** That branch is 14 ahead / 19 behind `main` and carries
~3,800 lines of NI live-sync work (live mode, per-recon model, corrections files) that
is **untested**. Merging it to obtain one module would be a bad trade.

`0418ca6` *"feat(ni): defer un-makeable project hard links to pending_links.csv"* is the
**first commit on that branch**, sitting directly on merge-base `6b2ef41`, which is an
ancestor of `main`. Verified: of the seven files it touches, the only one `main` has
also changed since the merge-base is `CHANGELOG.md` — a one-line append. So the pick is
clean apart from a trivial CHANGELOG resolution.

It is also **not** untested in the way the rest of the branch is: it ships
`tools/test_pending_links.py`, which **passes** (run 2026-08-11 — 10 checks: idempotency,
status preserved across re-ingest, header mismatch raises, missing file → `[]`).

Risk to `main` is near zero because **the code is dormant on Windows.** The whole hook
lives inside the `except` branches of the Step-12 link block; `create_hardlink` succeeds
on NTFS/SMB from Windows, so the success path is untouched.

> **⚠️ THE TRAP — it applies cleanly and then breaks at runtime.** The commit is dated
> **2026-06-25**, *before* the 2026-08-02 project-reference-model cut, and it contains:
>
> ```python
> project_id=(proj_id or project_hint),
> ```
>
> **`project_hint` no longer exists on `main`** — the vocabulary was retired
> repo-wide, zero occurrences left. `proj_id` is also the wrong name here: it is
> assigned inside an earlier `if project_name:` block, while the Step-12 link block
> uses **`project_id`** (see `ingest_raw.py:1438`). Git will not flag any of this,
> because `main` never touched `ingest_raw.py` since the merge-base.
>
> **Whoever picks it must change that line to `project_id=project_id`** and confirm the
> name is in scope at the call site. Left alone it is a latent `NameError` on the exact
> path that only ever runs when something has already gone wrong.

**One quality gap to close, and it is yours to close because your tool is what makes it
matter.** `pending_links.py` mirrors `pending_dicom.py`: BOM-tolerant, header-checked,
atomic temp+replace, idempotent on `acq_id` — but **no locking**, and a bare
`path + ".tmp"` temp name. The other sibling, `pending.py`, does it properly: the whole
read-modify-write runs under `locking.registry_lock(registries_dir)` and the temp is
pid-suffixed (`f"{path}.tmp.{os.getpid()}"`) precisely so two processes can't collide.

For a single operator running one ingest, unlocked read-all/write-all is survivable. For
a GUI several students can open at once it is a lost-update waiting to happen — two
imports queue links, both read the same rows, the second write drops the first's. **Bring
`pending_links.py` up to `pending.py`'s standard** (lock + pid temp) as part of this work.
Do it on `main` after the pick, or on this branch — but coordinate, because
`feat/ni-live-hardening` also owns that file.

**Coordination:** that worktree belongs to another live session. Read from it freely;
**never** merge, rebase, delete, or `worktree remove` it. The cherry-pick is Ryan's to
authorise and sequence.

---

## 2. Decisions to settle before writing code

Take these to Ryan if you are unsure. Recommendations given, but they are his call.

### 2.1 Separate `.exe` — ✅ DECIDED (2026-08-11). Build for the merge that's coming.

**A separate app and a separate exe.** Different audience (researchers vs. operators) and,
decisively, a different release cadence: folding this into `gjesus3_ingest.exe` means
every project-manager tweak forces a redeploy of the production ingest exe — the artifact
just replaced under a backup-and-rollback procedure.

**But build it knowing the exes are temporary.** In roughly **2 months (≈ Oct 2026)** a
dedicated RDM server is expected for gjesus3. All of this code goes live there, and the
tools get **redesigned as one web app** — no more exes, no more per-tool shortcuts. So the
goal right now is *not* clever integration; it is **maximum similarity**, for two reasons:
familiar for the operator today, and cheap to fold together later.

Concretely, that means: same visual language (share `style.css`, don't fork it), same
interaction idioms (the folder browser, the Preview/Read-folder two-verb model, the
409-style overwrite confirm), same server shape (Flask, `/api/*` JSON endpoints, the same
`nas_root` resolution and saved-state mechanism). Where you must choose between "clever
and different" and "boring and identical to the ingest GUI", **choose identical.**

**Do not copy `folder_browser.js`.** The branch that just landed existed partly to
*delete* exactly that duplication between `app.js` and `mri.js`. Promote the shared
assets to a common directory served by both apps, or serve
`tools/operator/gui/static/` from the new app through a second route. Either way, both
PyInstaller specs must bundle it.

### 2.2 Who can create projects — ✅ DECIDED (2026-08-11). Open access, mediated path.

`RESEARCHER_GUIDE.md:126` currently says: *"To get a project workspace, ask the Data
Management Lead — projects are created centrally so the registry and links stay
consistent."* **That line changes.**

The distinction to write carefully, because it is the whole point: **anyone with access
may create a project — but only through the system.** What stays centralised is the
*mechanism*, not the *permission*. Nobody hand-creates folders in the top-level
`projects/` directory; creation goes through this tool so the registry row, the folder
name, the required subfolders, and `_project.yaml` are all correct and consistent.

This is a smaller change than it looks: **it is already true in practice.** Any operator
who can run an ingest can already create a project — `auto_create_project` mints one
whenever a config names a project that doesn't exist yet (`ingest_raw.py:1326-1335`).
This tool makes that capability explicit and gives it a front door, rather than granting
something new.

Rewrite §4's first bullet accordingly. Keep the *reason* — consistency of registry and
links — and drop the *gatekeeper*.

> **🕗 Not yet: who owns what.** Ownership is typed in by hand today, and there is no
> identity to check it against — an exe on a shared workstation doesn't know who is
> sitting at it. When the server lands it will, and owner-on-create plus per-project edit
> permissions become automatic. Backlogged (§1 → *"Server-era identity"* in
> `tasks/BACKLOG.md`); **do not try to solve it in the exe.** Do keep `owner` an ordinary
> editable field so the server-era version can populate it without a migration.

### 2.3 What stops two students corrupting the registry at once?

`registry_projects.csv` is a shared CSV on an SMB share. Every existing writer of a
registry takes `locking.registry_lock(registries_dir)` around read-modify-write and
writes atomically (temp + `os.replace`). `create_project.py` currently does **neither** —
it does a bare `csv_safe.ensure_trailing_newline` + append, which was tolerable when one
Data Office person ran it from a shell, and is **not** tolerable once a GUI puts it in
front of several students.

**This is a required fix, not an optional one.** Any edit path you build (update fields,
create project) must hold the lock across read-modify-write and rewrite atomically.
Model it on `ingest/registry.py::update_row` (`tools/ingest/registry.py:151`) — read the
docstring, it spells out the contract including that the **caller** holds the lock.
Note there is no `update_row` equivalent for the *projects* registry; you will be writing
it. Put it somewhere both the GUI and future tools can call, not inside the Flask layer.

### 2.4 How does the acquisition picker get its data?

The request suggests presenting "something like `registries/index.html`". Be aware what
that file is: a **19 MB self-contained HTML** with the entire registry inlined as JSON,
regenerated nightly at 03:00 (by the `finder-refresh` op in the separate WorkstationOps
repo — not this one). It is built to be opened directly over SMB with no server.

Your tool **has** a server. Reusing the file means either re-rendering it inside your
page or parsing 19 MB of embedded JSON. **Recommendation: don't reuse the artifact,
reuse the *idiom*.** Read `registry_raw.csv` server-side, filter server-side, return
pages of rows to a table that looks and filters like the Finder. Shared look via the
shared stylesheet; shared *code* via `find_acq.py`, which already implements the
filtering the Finder exposes. Keep checkbox selection client-side.

---

## 3. Live state you are building against

Verified 2026-08-11 on `J:\gjesus3-data`.

| Fact | Value |
|---|---|
| `registry_projects.csv` rows | **52** (9 columns) |
| Project folders on NAS | **49** |
| `status` values in use | `active` (44), `closed` (8) |
| Folders with `raw_linked/` + `provenance.csv` | 49 / 49 |
| Folders with `_project.yaml` + `index.html` | 44 / 49 |
| Folders with `working/`, `outputs/`, `metadata/` | **0 / 49** |
| `registry_raw.csv` | 28 columns, single `project_id` |

**Three registry rows have no folder** — `PROJ-0003`, `PROJ-0008`, `PROJ-0009`, all
`status=closed`. This is expected: 8 stale projects were closed and their folders deleted
on 2026-07-14/15. **The GUI must handle "project exists in the registry but has no
folder" gracefully** — it is a normal, correct state, not corruption. Do not offer
"import data" into one, and do not silently recreate the folder.

**Five folders are missing `_project.yaml` and `index.html`** — `AE-biomaGUNE-0219`,
`-0220`, `-0320`, `-0618`, `-1019`. These predate `create_project.py`. Decide whether the
backfill (§4.5) also repairs them; **recommendation: report them, don't auto-repair** —
writing a `_project.yaml` means inventing an owner and a start date. Surface the list.

**`status` vocabulary.** Live data has only `active` and `closed`, but `05_PROJECTS §4`
defines the lifecycle as `Created → Active → Paused → Closed → DELETED` and §5 sets
"Paused: 6-month maximum". So the dropdown is **`active` / `paused` / `closed`**. §5 is
✅ DECIDED — do not invent a fourth value.

---

## 4. Requirements

### 4.1 Update project

List all 52 rows. Select one. Show **all nine** columns; make exactly four editable:
`description`, `owner`, `status` (dropdown, §3), `notes`. The rest — `project_id`,
`name`, `start_date`, `folder_location`, `last_activity` — display-only.

- Writes go through the locked, atomic projects-registry updater from §2.3.
- **`last_activity`**: careful. Per the 2026-07-14/15 production update, `start_date` and
  `last_activity` mean **acquisition** dates, not ingest or edit dates. Editing a
  description must **not** stamp `last_activity` to today — that would silently corrupt
  the meaning across every project a student opens. Leave it alone.
- `_project.yaml` holds overlapping fields (`description`, `owner`, `status`, `notes`).
  Decide whether the GUI writes both and keeps them consistent, or the registry is
  authoritative and the YAML is left alone. **Recommendation: write both**, they are
  meant to agree, and a student who opens the folder will read the YAML. Say which is
  authoritative in `05_PROJECTS §7` if it isn't already stated.

### 4.2 Create new project

Front-end over `create_project.py` (§1.4c). Must additionally:
- create `working/`, `outputs/`, `metadata/` alongside `raw_linked/` (§4.5);
- go through the locked writer (§2.3);
- surface `validate_project_name` / `normalize_project_name` errors **in the form**,
  before submission where possible — the space→hyphen normalization especially, since
  the operator GUI already does this for its "Project name" field
  (`operator/value_fields.py`) and students will expect the same behaviour.
- Uniqueness is **case-insensitive** (`check_name_unique`) because the NAS filesystem is.

### 4.3 Import from `raw`

Filter/search acquisitions (§2.4), tick them, import into the selected project. Per
acquisition:

1. **Create the hard link** via `ingest.linker.create_hardlink(project_folder_abs,
   link_name, raw_primary_abs)`. Do **not** write your own `os.link` loop — that function
   already handles the file-primary vs. folder-primary split (`<ACQ-ID>.data` becomes a
   real folder of per-file hard links, because Windows cannot hard-link a directory) and
   is idempotent.
2. **Resolve the raw primary correctly.** The dispatch is `primary_kind` +
   `primary_file_name` and it has three branches, one of them a legacy layout where
   `primary_file_name == acq_id`. It is written out at `tools/ingest_raw.py:1456-1468` —
   **read it and reuse the logic**; getting it wrong links the wrong thing.
3. **Link name.** Ingest derives it from the recipe's `link_filename:` template via
   `resolver.resolve_link_filename`, falling back to `original_name`. You have no recipe.
   **Recommendation: use the registry row's `original_name`** (what the fallback does),
   and make the name visible + editable in the confirm step before writing. Collisions
   inside one `raw_linked/` are possible — check and report, don't overwrite.
4. **Append provenance** via `ingest.provenance.append_entry` — idempotent on
   `output_path`, auto-assigns `FILE-NNNN` under the lock. Mirror the entry shape at
   `tools/ingest_raw.py:1499-1516`: `file_type` is `hardlink` or `hardlink-folder`,
   `input_refs` is the ACQ-ID, `software_version` from
   `provenance.software_version_string("<your tool>.py")`, `process_description` says
   what happened. **`creator` is the field to prompt for** — ingest fills it from the
   recipe's `operator:`, which you don't have. That is the one genuinely
   user-supplied field; everything else derives.
5. **Record the association in `registry_raw.project_id`** as a semicolon list (§1.4b),
   via a locked `registry.update_row` call. Blank → set it. Already this project →
   no-op (idempotent; a re-import must not produce `PROJ-0001;PROJ-0001`). Already a
   *different* project → append, preserving the existing id **first** so the original
   association stays the primary one. Do **not** put the association in `notes` — those
   carry real provenance text (e.g. *"Archive-mode NI preload (gnuclear2$ …)"*) and are
   not machine-readable.
6. **On `OSError`** (cross-volume, or a mount with no hard-link support — this tool may
   well run somewhere the NAS is a UNC path rather than a mapped volume): **queue it via
   `ingest/pending_links.py`** (§1.4a / §1.6), drop the `.PENDING-LINK.txt` stand-in, and
   carry on with the rest of the batch. Then tell the user plainly, in the UI: how many
   were queued, that their data is safely registered, and that a data-office pass
   (`tools/relink_pending.py`) completes the links. A student must never be left thinking
   the import failed when it succeeded.

Refresh the project's `index.html` afterwards — `generate_index.py --project PROJ-NNNN`
is the cheap single-project path the ingest GUI already uses.

### 4.4 Import from `local`

Folder browser in the established idiom — **reuse `static/folder_browser.js`** (§2.1),
which already gives you drive listing, the reversible sort, and remembered
last-directory. It currently selects a *folder*; you need *file* multi-select, so it will
need extending — extend it in the shared copy so both tools stay on one component.

Copy (never move) selected files into a destination the user picks — default the choice
to `working/`, since that is what the new convention is for. Then append one provenance
row per file: `file_type` from the extension, `input_refs` = the source path,
`process_description` = "Copied from local storage", `creator` prompted as in §4.3.

Two things to get right:
- **Free space.** This *copies* — unlike the raw import, it consumes real NAS space.
  Check before starting and refuse a copy that would obviously not fit.
- **Overwrite.** If the destination file exists, ask; do not silently clobber. The recipe
  overwrite flow that just landed in `app.js` is the house pattern for this — a 409-style
  refusal the UI turns into an explicit "replace?" prompt naming the file.

### 4.5 The subfolder convention

**Create in every new project:** `working/`, `outputs/`, `metadata/`, `raw_linked/`.

Meanings to document — keep them one line each:
- `raw_linked/` — hard links to raw acquisitions. Tool-managed; don't hand-edit.
- `working/` — scratch and in-progress analysis.
- `outputs/` — results worth keeping: figures, derived images, reports.
- `metadata/` — study-level metadata. Directory created; **contents still deferred**
  (§1.4d).

**Backfill** existing projects that lack them. Write it as a standalone, idempotent,
`--dry-run`-first script under `tools/` — the house pattern (`relink_projects.py`,
`backfill_*.py`) — not as a hidden side effect of the GUI starting up. It must:
- skip the 3 registry rows with no folder (§3), and report them;
- create only what's missing, touch nothing else;
- **not** write provenance rows for empty directories (provenance tracks files);
- report the 5 folders missing `_project.yaml` rather than repairing them (§3).

**Docs to update** (per the "new convention" rule in `CLAUDE.md`):
- `mfb-rdm-docs/05_PROJECTS.md §3` — extend the existing tree; narrow the 🕗 note (§1.4d).
- `mfb-rdm-docs/06_REGISTRIES.md` — **`project_id` is now a semicolon-separated list**
  (§1.4b). Integrity mirror with `ingest/registry.py`; word it like
  `modalities_in_study`.
- `RESEARCHER_GUIDE.md §2`, **§3.2**, **§4** — the "recommended subfolders" statement;
  the §2.2 rewrite (anyone may create, only through the system); and §3.2's 🕗 note,
  which also says `metadata/` doesn't exist — narrow it the same way as §3.
- `mfb-rdm-docs/10_TOOLS.md` — the new tool + the backfill script.
- `mfb-rdm-docs/00_INDEX.md` — bump **Last Updated**.
- `CHANGELOG.md` — append one dated entry. **Append only; never rewrite a past row.**

---

## 5. Constraints and traps

- **`CLAUDE.md` governs.** Respect status markers; never edit `tasks/archive/`; append to
  the CHANGELOG, don't rewrite; stage specific files, never `git add -A`; **never
  `git push` without explicit permission**; **do not stage `contacts.xlsx`.**
- **Commit freely on this branch** as coherent units land. Stay in this worktree — do not
  `git checkout` elsewhere, and do not touch the other two worktrees
  (`code-review-2026-08`, `ni-live-hardening`); they are owned by other live sessions.
- **`/raw/` is immutable.** The only write this work makes anywhere near raw is the
  `registry_raw.notes` update (a registry file, not raw), and hard links *from* raw. Never
  write into a `/raw/` acquisition folder.
- **Never `import operator`** anywhere in this tree — the package dir `tools/operator/`
  collides with the stdlib module. See `tools/operator/IMPORT_CONTRACT.md`; the loader
  shim is `tools/operator/_loader.py`.
- **Test against a scratch NAS, not `J:`.** `tools/operator/make_test_nas.py` builds a
  throwaway tree. The previous branch's agent pointed the recipes dir at a scratch folder
  and restored it afterwards — do the same for the registries. **A bug in a locked
  read-modify-write on `registry_projects.csv` can lose all 52 rows.** Back that file up
  before any live test.
- **Hard links need a real volume.** They cannot cross volumes and may fail over a UNC
  path. `J:\gjesus3-data` (mapped) works; test the failure path deliberately (§4.3.6).
- **SMB gotcha:** on this share you **cannot verify a hard link by link count** — stat
  reports 1. Verify by inode/file-index or by content, as `relink_projects.py` does.
- **Excel BOM:** always read registry CSVs with `encoding="utf-8-sig"`. Every existing
  reader does; a plain `utf-8` read silently yields a `\ufeffproject_id` key and lookups
  miss.

---

## 6. Build + deploy

**Dev run** — from the worktree root:
```powershell
pip install flask
python tools/manager/gui/app.py     # or wherever §2.1 lands it
```

**Freeze** — PyInstaller, on this box. The repo lives under OneDrive, which **locks
build artifacts mid-build** (`PermissionError` on `PYZ-00.pyz`), so build and dist must
go to a non-synced path:
```powershell
pip install flask pyinstaller pyyaml
pyinstaller --workpath D:/_build --distpath D:/_dist tools/manager/gui/<your>.spec
```
Model the spec on `tools/operator/gui/gjesus3_ingest.spec`. It must bundle the shared
static assets (§2.1), `tools/templates/project.yaml` (`create_project.py` needs it — a
missing bundle silently falls through to an inline non-templated fallback, which is
exactly the class of bug the 2026-07-17 frozen-exe fix chased), and anything else reached
through `ingest/resources.py`. **`resources.resource_path` is `sys._MEIPASS`-aware; naive
`dirname(__file__)` is not.** Every path that resolves a bundled resource must go through
it.

**Deploy is outward-facing — ask Ryan before touching the NAS.** The established
procedure: back up the current `tools\` contents off-NAS first (the last one went to
`C:\Users\rtasseff\temp\gjesus3_exe_backup_<date>\`, deliberately kept as the
*pre-branch* build so restoring it undoes the whole branch), copy the new exe to
`\\GJESUS3\gjesus3\gjesus3-data\tools\`, add the `.lnk`, and update
`tools/operator/gui/nas_tools_README.txt` (it is mirrored to `tools\README.txt` on the
share and currently describes only the ingest tools).

---

## 7. Definition of done

- [ ] `pending_links` is on `main` via cherry-pick, with the `project_hint` line fixed
      (§1.6) — **not** reimplemented here.
- [ ] `pending_links.py` brought up to `pending.py`'s standard: `registry_lock` around
      the read-modify-write, pid-suffixed temp (§1.6).
- [ ] Multi-project semicolon list written by the tool **and** read by all five sites in
      the §1.4b table — verify an acq in two projects appears in **both** per-project
      indexes.
- [ ] §2.3 decision settled; projects-registry writes are locked + atomic — including
      `create_project.py`.
- [ ] Update / create / import-raw / import-local all work end to end against a scratch NAS.
- [ ] Hard-link failure is queued, stand-in written, and the UI says so plainly (§4.3.6).
- [ ] Backfill script run `--dry-run` then live; the 3 folderless and 5 yaml-less
      projects reported, not mangled.
- [ ] Docs updated: 05_PROJECTS §3, **06_REGISTRIES (`project_id` list)**,
      RESEARCHER_GUIDE §2/§3.2/§4, 10_TOOLS, 00_INDEX Last Updated, CHANGELOG appended.
- [ ] `tasks/STATUS.md` updated. **Check it at the end** — the last branch left a stale
      "not yet merged" claim on `main`, which is the first thing the next session reads.
- [ ] This handoff file deleted in the landing commit.
- [ ] Exe built and **manually verified by Ryan** before any NAS deploy.
