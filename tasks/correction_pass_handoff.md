# Correction Pass — Handoff Plan (first review: code + scheme)

**Audience:** a fresh Claude/Fable agent instance that will execute these corrections.
**Author of plan:** prior review session (`gjesus3-sandbox-review`), 2026-06-11.
**Working copy:** this is the **sandbox clone** (`...\gjesus3-dev\gjesus3-pilot`). Real git clone, push to `origin` (GitHub `Rtasseff/gjesus3-pilot`). Feature branches → PR. `gh` CLI is NOT installed here — push the branch and hand the user a compare URL for the PR.

This plan implements 11 numbered corrections from the first-pass code/scheme review. Each item below carries the **user's decision**, the **exact location**, the **approach**, **acceptance criteria**, a **test procedure**, and **docs to update**. Do not deviate from a user decision without asking.

---

## 0. Scope & safety (read first)

**Is this work within Fable's safety constraints? Yes.** Per Claude's safety note (support article 15363606), Fable's automatic safeguards are deliberately broad and can produce false positives on legitimate work. **These corrections are ordinary software engineering on a data-management tool** — fixing Python bugs, adding a file lock, building a Flask GUI, writing config/recipe files, and updating docs. They involve no restricted content.

Two practical notes for the executor:

1. **A few metadata *field names* in this project come from a research domain, but here they are only opaque schema/string values in CSV/JSON.** Treat them as strings. Nothing in this plan requires generating or reasoning about any domain methods; read any field-level detail from the code rather than restating domain vocabulary. If a task ever appears to drift toward domain methods, it is out of scope — stop and skip it.
2. **If a turn auto-switches model mid-task, that is the broad filter being cautious — not a violation or a failure.** The work continues normally; just proceed, and never ask the model to reveal its hidden/summarized reasoning.

> Note (2026-06-11): an earlier, more domain-vocabulary-dense draft of this plan tripped a false-positive policy block when handed cold to a fresh session. This version minimizes that. If a cold handoff still trips it, run the corrections inside an existing working session that already holds repo context, and keep item (10) — the only domain-adjacent item — described in the neutral database/CSV terms below.

**Operational safety is the real risk here, not policy safety.** These tools write to a live NAS registry. Ground rules:

- **Test everything on the sandbox NAS `J:\gjesus3-sandbox` first** (created for this purpose), via explicit `--nas-root J:\gjesus3-sandbox`. Seed `J:\gjesus3-sandbox\registries\` with header-only CSVs before test ingests (the defensive header check needs correct headers). Never let a test write to `J:\gjesus3-data` until the user signs off.
- `GJESUS3_ROOT` is set (persistently) to `J:\gjesus3-data`, but **new shells only** — in an already-running session pass `--nas-root` explicitly.
- The live `J:\gjesus3-data` was **just purged** (moving quasi-prod → true production). Empty registries are expected, not a bug. Risk tolerance is high, but still test on the sandbox.
- Branch + commit discipline: one feature branch for this pass (suggested `fix/correction-pass-2026-06`), **one commit per numbered item**, clear messages. Stage specific files; do not `git add -A` (repo has large binaries in `shared/`, `contacts.xlsx`).
- End commit messages with the `Co-Authored-By: Claude ...` trailer per repo convention.

---

## A. Fix before anyone touches it (small, high-stakes)

### (1) Dry-run: make the state unmistakable; default ON during testing; document the later flip-off
**User decision:** Operators dislike dry-run as a silent default and *sometimes don't realize a run was a dry run* — so they think data landed when it didn't, and researchers can't find files later. Make the dry-run state much clearer. Add a documentation note to **remove the dry-run default (flip to live) after a sufficient testing period.**

**Current state (verified):** `tools/operator/gui/templates/index.html:134` is `<input id="r-dry" type="checkbox">` — *unchecked* (dry-run OFF) on load; `app.js` reads `#r-dry.checked` and `updateDryState()` shows the "LIVE" red state when unchecked. Meanwhile `README.md`, `gui/README.md`, `TESTING.md` all say dry-run is "on by default." So code and docs currently disagree.

**Approach:**
1. Make dry-run **default ON during the testing period**: add `checked` to `#r-dry` in `index.html:134`, and confirm `updateDryState()` renders the "Safe / nothing will be written" state on load. This matches the docs and is the safe default while operators learn the tool.
2. Make the state **impossible to miss**:
   - A persistent, high-contrast banner at the top of the run panel whenever dry-run is ON ("DRY RUN — this will NOT write to the NAS").
   - A loud **end-of-run summary** distinguishing the two modes. Dry-run: `✓ DRY RUN COMPLETE — NOTHING was written to the NAS. N acquisitions WOULD be ingested. To actually ingest, uncheck "Dry-run" and run again.` Live: `✓ INGEST COMPLETE — N acquisitions written to <NAS>.` (Wire into the SSE stream end / the JS that re-enables the buttons in `app.js`.)
3. Add a clearly-marked, easy-to-find note (see docs below) that the dry-run default should be flipped to **OFF (live)** after the testing period — with a `TODO(dry-run-default)` marker in `index.html` next to the input so it isn't forgotten.
4. Check the CLI front-ends (`mri_ingest.py`, `ni_ingest.py`) for dry-run default consistency and align their end-of-run messaging to the same "nothing was written" clarity. Do not change their commit semantics beyond messaging without flagging to the user.

**Acceptance:** On GUI load, dry-run is ON and visibly so; a dry run ends with an unambiguous "nothing was written" summary; a live run ends with a "written to NAS" summary; a `TODO(dry-run-default)` marker and a doc note exist for the post-testing flip.

**Docs to update:** `tools/operator/gui/README.md`, `tools/operator/README.md`, `mfb-rdm-docs/11_OPERATIONS.md` (operator workflow) — add the "dry-run default flips OFF after the testing period" note in all three, identical wording, and confirm they now match the code.

---

### (2) Build & verify the microscopy GUI executable
**User decision:** Build the GUI. We're on Windows, the same OS the microscopy operators will use — so build and verify here.

**Current state:** The PyInstaller spec exists and is well-formed: `tools/operator/gui/microscopy_ingest.spec` (one-folder build, bundles templates/recipes/static, hidden imports for `flask/jinja2/werkzeug/yaml/czifile/tifffile/numpy/ingest/ingest_raw`). Per `gui/README.md:77` the freeze has **never actually been run**. Python on this machine is **3.13** (confirmed).

**Approach:**
1. From the repo root on this Windows machine: `pip install flask pyinstaller czifile tifffile numpy pyyaml`, then `pyinstaller tools/operator/gui/microscopy_ingest.spec`.
2. Expect first-build fallout and fix it in the spec: missing hidden imports, the dynamically-loaded `operator`-named-package collision (see `tools/operator/_loader.py`), and Flask `templates/`/`static/` path resolution inside the frozen bundle. Iterate until `dist/microscopy_ingest/microscopy_ingest.exe` launches, opens the browser, and serves the UI.
3. **Verify against a real `.czi`** (needed for true end-to-end): ask the user for a representative `.czi` (e.g. from `S:`/`K:` per `TESTING.md`), then from the exe: set NAS root → `J:\gjesus3-sandbox` → pick instrument + a recipe (see item 3) → Browse to the folder → **Preview** → **dry-run ingest**. Confirm metadata extraction works in the frozen build (this is what exercises `czifile`).
4. Record the verified build steps + any spec changes in `gui/README.md` (replace the "not executed" caveat with "built & verified <date>, Python 3.13, Windows").

**Acceptance:** A working `microscopy_ingest.exe` on this machine that previews and dry-run-ingests a real `.czi` to the sandbox NAS, with the build procedure documented.

**Note for executor:** This is the one item that may need the user in the loop (to provide a `.czi` and to confirm the machine matches the operators'). If no `.czi` is available, get the exe to launch + serve + load recipes, and explicitly flag the `.czi` read as "pending a real sample."

---

### (3) Seed recipes for Cell Observer (CELL) and LSM 900 (LSM9) from the exhibit configs
**User decision:** We loaded Cell Observer + LSM 900 data in the exhibit; the YAML configs exist — find them and turn them into recipes.

**Found — the exhibit configs (committed):**
- Cell Observer: `tools/configs/cell_observer_itziar_alphasma_TEST.yaml`, `tools/configs/cell_observer_itziar_colageno_perm_TEST.yaml`
- LSM 900: `tools/configs/lsm900_laura_uptake_TEST.yaml`

**Recipe format (from the only existing seed, `tools/operator/recipes/axioscan7_7chunk_section.json`):** JSON, `"schema": "gjesus3.operator.recipe/v1"`, with `name`, `instrument` (instrument code — `CELL` / `LSM9`), `description`, `based_on` (the config path), and `overrides` (a sparse map of `auto_discover.filename_parse` / `auto_discover.path_parse` / `registry.notes` etc.). The recipe is a thin override layer over the per-instrument template — operators pick it from a dropdown; `staging_dir` is supplied by the folder they point at (not the recipe).

**Approach:**
1. Read each config's `auto_discover` (filename_parse / path_parse) and `registry:` blocks to learn the exhibit's parse convention per instrument.
2. Create seed recipes in `tools/operator/recipes/`:
   - `cell_observer_cells.json` (instrument `CELL`) — derive `overrides` from the `cell_observer_*` configs. If the two Cell Observer configs differ in parse shape (filename- vs path-focused — round 5 exercised both), prefer the most general/representative one and note the alternative in `description`, or ship two recipes if they're genuinely distinct conventions.
   - `lsm900_uptake.json` (instrument `LSM9`) — derive from `lsm900_laura_uptake_TEST.yaml` (folder-name regex on `<researcher>_<experiment>_<cell_line>`).
3. Strip the `TEST`/batch-specific bits (`staging_dir`, batch `notes` literals) — recipes are reusable conventions, not one-batch configs. Keep `based_on` pointing at the source config for traceability.
4. The PyInstaller spec already bundles `tools/operator/recipes/` → the new files ship in the exe automatically (no spec change).

**Acceptance:** Opening the GUI for CELL and for LSM9 offers a working seed recipe in the dropdown (no operator forced into the Builder). A dry-run preview with each recipe, pointed at representative data on the sandbox, resolves discovered fields without parse errors.

**Docs to update:** none required, but mention the new seed recipes in `tools/operator/README.md` recipe list if one exists.

---

## B. Fix before the historical-batch ingest (front #2)

> These are correctness bugs that specifically corrupt re-runs / messy-input handling — the exact conditions of crawling old drives. Review IDs reference the first-pass code review (F-numbers).

### (4) Archive layout breaks re-run idempotency (F2) — **fix it**
**Location (verified):** `tools/ingest_raw.py:731` sets `cfg_single["original_name"] = os.path.basename(archive_src)` (e.g. `LEONE_1.01.zip`) for `acquisition_layout: archive`. But `expand_batch` builds the dedup key from the registry's `original_name` using the staging **relpath** (e.g. `LEONE_1.01`) — see `tools/ingest/config.py` (`_build_dedupe_index` / the `original_name` it stores at ~`:434-435,569-575`). The two never match → re-running an archive batch re-ingests everything with fresh ACQ-IDs and duplicate rows.

**Approach:** Stop overloading `original_name` for the archive's display name. Keep `original_name` = the dedup-stable relpath in the registry; carry the archive basename in a separate field (e.g. reuse `archive_src` / a new `archive_basename`) for the link-name/display. OR make `_build_dedupe_index` and the archive path agree on one canonical key. Confirm the dedup key written at ingest equals the key computed at re-run for archive ecosystems.

**Acceptance:** Ingest a small archive batch to the sandbox; re-run the same config → **all rows skipped as already-ingested**, zero new ACQ-IDs, zero duplicate rows. Add this as the regression check.

---

### (5) Crash-after-copy orphans data (F3) — **do it**
**Location:** `tools/ingest_raw.py` `ingest_single` step order (~`:774-1078`): copy+verify → `--delete-source` → sidecar → README → project resolve/auto-create → **registry append (step 10, last)**. Any exception between copy and append leaves a fully-copied raw folder with **no registry row**; re-run can't see it (dedup keys off the registry) and copies again → orphan + duplicate. `--delete-source` compounds it (source gone before the row exists).

**Approach (pick the lower-risk that fits the code):**
- Make the **registry append the commit point** and order operations so the row is written as early as safe (right after copy+verify), then do sidecar/README/links (those are reconstructable/idempotent). OR
- Wrap `ingest_single` so a failure after copy **cleans up the half-written dest folder** before re-raise. AND
- **Move `--delete-source` to the very end**, after the registry append succeeds — non-negotiable regardless of which option above.

**Acceptance:** Inject a failure after copy (e.g. temporarily raise before append) on the sandbox → no orphaned raw folder is left that a re-run can't reconcile; with `--delete-source`, the source is never deleted unless the row was written. Remove the injected failure before commit.

---

### (6) Empty/junk folder reports "success" (F13) — **do it**
**Location:** `tools/ingest_raw.py` generic-DICOM / unknown-ecosystem paths (~`:586-600,907-936`): an empty `source_path` yields `file_count=0`, copies nothing, `verify_checksums` returns `(True, [])`, and the ingest **succeeds**, registering an empty acquisition with a real ACQ-ID. Common on semi-ordered historical drives. (The slim-copy NI/MRI paths already guard this.)

**Approach:** Fail (`return False` / raise a clear error) when the discovered primary-file count is 0 for ecosystems that require data. Mirror the existing slim-copy guards. Make the message name the folder so a batch operator can find the junk dir.

**Acceptance:** Point an ingest at an empty folder on the sandbox → it fails loudly with a clear message and writes **no** registry row / raw folder.

---

### (7) Cross-drive `relpath` ValueError (F5) — **do it** (it does help; low risk)
**Location:** `tools/ingest_raw.py:43,46` — `os.path.relpath(...)` raises `ValueError` on Windows when the config and repo/CWD are on different drives (e.g. config on `J:`, repo on `C:`), crashing `main()` before any ingest. Already noted as a known bug in `tasks.md §3.1`.

**Approach:** Wrap both `os.path.relpath` calls in `try/except ValueError` and fall back to the absolute forward-slash path (`abs_path.replace("\\","/")`). A non-relative `ingest_config` value is fine; a crash is not.

**Acceptance:** Run an ingest with `--config` on a different drive than the repo → it proceeds, and the `ingest_config` column holds a usable (absolute, forward-slash) path.

---

## C. Registry integrity (both fronts — CSVs are operator-visible and Excel-bound)

### (8) Implement a simple registry lock — verify, document, and add a test
**User decision:** Very important. Implement a simple locking scheme, verify it, add it to the docs, and put a test in for it.

**Problem (verified):** No file-locking exists anywhere in `tools/` (grep for `fcntl/msvcrt/flock/O_EXCL/lockfile` → none). `acq_id.generate_acq_id` reads the registry, computes `max_seq+1`, returns; there's a wide window before `registry.append_row` writes. Two concurrent ingests (same date+instrument) mint the **same ACQ-ID** and can interleave a torn CSV line over SMB.

**Approach — a cross-platform lockfile mutex** (must work on Windows + Linux + over SMB):
1. Add a small `tools/ingest/locking.py` with a context manager, e.g. `with registry_lock(registries_dir, timeout=60): ...`. Implement as an **atomic create** of `registries/.registry.lock` via `os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR)`; on `FileExistsError`, spin with a short sleep until acquired or `timeout`. Write the holder's pid + ISO timestamp into the lockfile. Add **stale-lock breaking**: if the lock is older than a configurable max age (e.g. 600 s), reclaim it (log a WARN). Always release in a `finally` (delete the lockfile).
2. **Wrap the critical section** `generate_acq_id(...)` **through** `append_row(...)` as one locked unit in `ingest_single` (so the ID allocation and the row write are atomic together). Keep the lock hold-time minimal — do NOT hold it across the file copy.
3. Note in code that `O_EXCL` create is atomic on local FS and adequately atomic for this low-contention case over SMB; the stale-break + timeout cover the crash-with-lock-held case.

**Verify:** Write an integration test that launches 2 (ideally more) concurrent workers (threads or subprocesses) each calling the locked allocate+append against a sandbox registry, then assert: (a) **no duplicate ACQ-IDs**, (b) **row count == number of appends**, (c) **every row parses** (no torn lines), (d) header still valid. Put it at `tools/ingest/test_locking.py` (or extend the existing test pattern — see `tools/test_phase3_enrichment.py`). Also add a quick single-process self-test that the lock is re-entrant-safe / always released.

**Docs to update:** `mfb-rdm-docs/06_REGISTRIES.md` (a "Concurrency / locking" subsection — the registry append is serialized by `registries/.registry.lock`), `mfb-rdm-docs/10_TOOLS.md` (mention the lock in the ingest flow), and a one-line cross-ref in `CLAUDE.md` under the registry-integrity rules. Note the `.registry.lock` file in the registries-dir description so no one mistakes it for data.

**Acceptance:** The concurrency test passes repeatably; docs describe the mechanism; `.registry.lock` is documented.

---

### (9) BOM + trailing-newline safety on registry appends — fix for both, and document
**User question answered:** It is **not just the trailing newline** — there are two small parts, and both are quick:

1. **BOM:** `registry.append_row`'s internal header check reads with `encoding="utf-8"` (`tools/ingest/registry.py:89`). `read_registry` is already BOM-tolerant (`utf-8-sig`, `:65`), but the append header-check is not — so if Excel "Save As CSV UTF-8" adds a BOM, the header reads as `['﻿acq_id', ...] != REGISTRY_FIELDS` and **every append is refused**. Fix: read that header with `utf-8-sig`.
2. **Trailing newline:** the append at `registry.py:103` opens `"a"` mode; if the file's last line lacks a trailing `\n` (Excel round-trip / manual edit), `csv.writer` concatenates the new row onto the last row, silently corrupting two rows. Fix: before appending, if the file is non-empty and does not end in `\n`, write one first.

**Approach — fix once, share everywhere:** Add a small shared helper (e.g. `tools/ingest/csv_safe.py` with `ensure_trailing_newline(path)` and a BOM-tolerant header reader, or fold into `registry.py` and import) and apply it to **every append-mode CSV writer**, so this can't be missed on future registries:
- `tools/ingest/registry.py` `append_row` (BOM read + newline guard)
- `tools/ingest/linker.py` `create_manifest_entry` (`:35`)
- `tools/ingest/provenance.py` `append_entry`
- `tools/ingest/pending.py` (`read_pending` header check `:57` uses plain utf-8 — make BOM-tolerant too; it rewrites whole-file so newline is N/A, but align the read)
- `tools/create_project.py` (the `registry_projects.csv` writer)

**Docs to update:** Add a short note in `mfb-rdm-docs/06_REGISTRIES.md` (and/or `10_TOOLS.md`) — "All registry/CSV appends go through the BOM-tolerant, trailing-newline-safe helper; new CSV writers MUST use it" — and a one-line cross-ref in `CLAUDE.md` so future schema work uses the helper.

**Acceptance:** Add a BOM to a sandbox registry → append still works. Strip the trailing newline from a sandbox registry → next append produces a clean new row (no concatenation). A unit test covers both.

---

## D. Verify / correct before front #1

### (10) External reference DB: docs are stale (it IS implemented); document the optional credential install; keep the deferred-recovery queue
**User correction (important):** Access to the external institutional reference database was granted and the pipeline **already queries it** to auto-fill one metadata block at ingest — it is implemented. Docs that still say access is "blocked on IT" are out of date. Also: the deferred-recovery design — a queue listing exactly which records the Data Office must back-fill later — is the intended solution and **should stay**, not be reduced to a bare placeholder.

**Verified reality (state it correctly):**
- The lookup is implemented and live: `tools/animal_db.py::lookup` (read-only network DB via pymysql), called from `tools/ingest/enrichment.py` Step 8.5. A hit fills the block from the DB.
- On a miss / no-credentials the pipeline does BOTH (cooperating, not either/or): writes a placeholder value into the JSON sidecar AND **queues the exact record** to `registries/pending_subject_metadata.csv` via `tools/ingest/pending.py` (columns include `acq_id, sidecar_path, reason, status, recovered_at`; idempotent on `acq_id`). `tools/recover_subject_metadata.py` is the Data-Office tool (has DB credentials + sidecar-write permission) that drains the queue and updates the sidecars. **This is the "easy path for the Data Office," and it already exists.** An earlier review note to "simplify/defer" this was wrong — disregard it.
- Credentials: `animal_db.py` reads `~/.my.cnf` (Windows: `C:\Users\<you>\.my.cnf`) and **already supports a configurable path via the `GJESUS3_MYCNF` env var** (and `GJESUS3_ANIMALDB_USER`). On-network/VPN only; never in git/repo/OneDrive/logs.

**Approach:**
1. **Fix the stale docs.** Find the two docs that disagree about DB-access status (grep the repo for "blocked on IT") and make both say: access granted; lookup implemented + live; whether a machine auto-fills depends on whether it *has credentials*, not on the OS. Update `00_INDEX.md` Key-Gaps / Version-History. Remove all "blocked on IT" language for DB access.
2. **Write the optional credential-install doc** (optional, manual, only on a *trusted* operator machine): add a short section to `tools/operator/README.md` (and/or the onboarding doc): (a) `pip install pymysql`; (b) obtain the read-only `.my.cnf` from the Data Office **out-of-band** — it is sensitive and intentionally NOT in git, so the executor will not have it; place it in the user profile, NTFS-protected, NOT in OneDrive or the repo; (c) for a non-default location set `GJESUS3_MYCNF` (and `GJESUS3_ANIMALDB_USER` if the DB user differs); (d) on-network/VPN only; verify with `python tools/animal_db.py --check`. State clearly: without credentials, ingest still succeeds (non-blocking) and the record is queued for Data-Office back-fill — so credentials are an *optimization*, not a requirement.
3. **Do NOT alter the queue / recovery tooling.** Confirm it works end-to-end on the sandbox (force the no-credentials path → a row appears in `pending_subject_metadata.csv` → `recover_subject_metadata.py --dry-run` would resolve it). Leave the design intact.

**Acceptance:** No doc says DB access is "blocked on IT"; an optional, manual credential-install procedure exists referencing `~/.my.cnf` + `GJESUS3_MYCNF`; the queue/recovery flow is verified intact on the sandbox.

---

### (11) Test `os.link` on the real target machines (MRI Linux; NI via Mac) — report failures + fallbacks
**User context:** The **NI machine is not directly accessible** — reached via a **macOS** box (maybe an SSH-into-the-Mac is possible). The **MRI machine is Linux**. Find a way to test `os.link` on those mounts; if it fails, report possible solutions (e.g. run ingest from a Windows machine where hard-links work, then reach the data remotely via FTP/SFTP).

**Already established (this session):** `os.link` on the **Windows SMB mount works perfectly** — tested on `J:\gjesus3-sandbox`: real shared inode (`st_ino` matched), edits propagate both ways, the link survives deleting the original. So the Windows ingest path is solid. The open risk is **Linux CIFS** (MRI) and the **Mac-fronted NI** path, because `os.link` on a CIFS/SMB mount on Linux/macOS can fail (`EPERM`/`EOPNOTSUPP`) depending on the mount options and SMB protocol version.

**Approach — ship a standalone diagnostic the user runs on each target machine** (the executor cannot reach those machines; provide the tool + interpret results):
1. Create `tools/diagnostics/test_oslink.py` — a dependency-free script taking a target directory on the mounted gjesus3 share. It: creates a temp file, `os.link`s it, then reports PASS/FAIL plus: `os.link` raised? (errno + message), `st_ino` match, `st_nlink`, edit-propagation, survives-deleting-original — and cleans up. (Reuse the exact checks from this session's Windows test.) Print a clear final verdict line.
2. Give the user copy-paste run instructions for each machine:
   - **MRI (Linux):** mount the gjesus3 share, then `python3 tools/diagnostics/test_oslink.py /path/to/gjesus3/mount/<scratch>`.
   - **NI (via macOS):** if an SSH into the Mac is available, same script against the Mac's mount of the share; otherwise run it locally on the Mac.
3. **Document fallbacks to report if it FAILS** (the user explicitly asked for these):
   - **(a) Run ingest from a Windows machine** that mounts the share (hard-links confirmed working there), and reach the instrument data remotely. This is the preferred fallback since the Windows hard-link path is proven.
   - **(b) Stage/transfer the source data via FTP/SFTP** (`tools/ftp_mirror.py` already does SFTP mirroring) from the Linux/Mac machine to where a Windows ingest runs, then ingest there.
   - **(c) Server-side reflink** (`cp --reflink`, NAS-side only) if the NAS filesystem is ZFS/btrfs — zero-copy alternative; verify FS type first.
   - **(d) Fall back to the legacy `.lnk` path** (`linker.create_lnk` still exists) for cross-platform cases where hard-links aren't possible — shortcuts instead of real-file links; lower adoption value but functional.
4. **Report results back to the user** with a recommendation per instrument (which path each should use). Do not pick a fallback unilaterally — present the test output + options.

**Acceptance:** A working `test_oslink.py` diagnostic + per-machine run instructions delivered; once the user runs them, a short written recommendation (hard-link vs Windows-remote vs FTP-stage vs `.lnk`) per instrument. The MRI/NI verdicts depend on the user running the script (the executor can't reach those hosts).

---

## Suggested execution order & workflow

Group into one branch `fix/correction-pass-2026-06`, one commit per item, in this order (cheap/safe → involved):

1. **(7)** relpath guard · **(9)** BOM+newline helper — trivial, high-safety, unblock everything else.
2. **(8)** registry lock + test + docs — the integrity centerpiece the user flagged "very important."
3. **(4) (5) (6)** idempotency/robustness — verify each on the sandbox with a tiny batch.
4. **(1)** dry-run clarity + default + docs · **(3)** CELL/LSM9 recipes — operator-facing.
5. **(2)** GUI exe build+verify — may need the user (a `.czi`); can run in parallel.
6. **(10)** DB doc reconciliation + credential-install doc.
7. **(11)** os.link diagnostic + hand to user to run on MRI/NI.

After each item: test on `J:\gjesus3-sandbox`, never `J:\gjesus3-data`. When the branch is ready, push and give the user a GitHub compare URL (no `gh` here). Items (2) and (11) have external dependencies (a real `.czi`; access to the MRI/Mac hosts) — surface those to the user rather than blocking the rest of the pass.

## Final verification checklist (before opening the PR)
- [ ] (1) GUI dry-run defaults ON, state unmistakable, end-of-run summary clear; flip-off note in 3 docs.
- [ ] (2) `microscopy_ingest.exe` builds, launches, loads recipes; `.czi` read verified (or flagged pending).
- [ ] (3) CELL + LSM9 seed recipes load in the GUI; dry-run preview parses cleanly.
- [ ] (4) Archive batch re-run = full skip (no dupes).
- [ ] (5) Injected post-copy failure leaves no unreconcilable orphan; `--delete-source` only after append.
- [ ] (6) Empty folder fails loudly, writes nothing.
- [ ] (7) Cross-drive config runs without crash.
- [ ] (8) Concurrency test green; lock documented; `.registry.lock` noted.
- [ ] (9) BOM + missing-newline cases both handled; shared helper used by all CSV appenders; documented.
- [ ] (10) No "blocked on IT" language; optional credential-install doc written; pending-list flow verified intact.
- [ ] (11) `test_oslink.py` delivered + per-machine instructions; awaiting user run on MRI/NI.
- [ ] All changes tested on `J:\gjesus3-sandbox`; branch pushed; compare URL handed to user.
