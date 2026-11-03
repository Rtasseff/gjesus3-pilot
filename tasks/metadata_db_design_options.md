# Metadata database: design options (issue #29)

**Status:** ❓ EVALUATING. Options for Ryan to choose from. Nothing here is decided, and nothing here has been written into the numbered specs.
**Date:** 2026-10-17
**Raised:** issue [#29](https://github.com/Rtasseff/gjesus3-pilot/issues/29) ("Metadata database: retire the CSV registries; a `status` column for retired acquisitions"). Milestone M3, after the port.
**Related:** [#28](https://github.com/Rtasseff/gjesus3-pilot/issues/28) (the web app on Box A that a database would serve), [#30](https://github.com/Rtasseff/gjesus3-pilot/issues/30) (the search-index spike; this note does not design it again), [#8](https://github.com/Rtasseff/gjesus3-pilot/issues/8) (the validator; its checks are the invariants a database has to keep), [#26](https://github.com/Rtasseff/gjesus3-pilot/issues/26) (the Box A port).

**How to read this.** There is one section per question. Each one gives the constraint (with its source), two or three options, the trade-offs in this system's terms, and a recommendation with the reason. The order of decisions and the work that can start before any decision are at the end (§7, §8).

---

## 0. Summary (one line per question)

| # | Question | Recommendation |
|---|---|---|
| 1 | Engine and placement | Target a **server database on Box A**, with every writer going through Box A (which is what #28 builds). Until then, keep the CSVs as the system of record and let #30's derived index give search. Lean PostgreSQL over a SQLite file local to Box A, because the dev workstation keeps writing by hand. Never put a SQLite file on the SMB share as the system of record. |
| 2 | The model | Acquisition, project, subject and dataset tables, plus **link tables** for acquisition↔project, acquisition↔subject, acquisition↔modality and dataset↔acquisition. Keep `session_id` as a column until #33 decides study-level metadata. Sidecars stay files. The CSV export keeps today's 28 columns, with the lists packed back into cells. |
| 3 | Retired acquisitions | In the database: **a `status` on the acquisition row, a lifecycle (event) table for its history, and a live-only view as the default** that every reader gets. Before the database: **keep the tombstone file.** Adding a `status` column to the CSV now buys the silent failure mode without the view that contains it. Quarantine stays a separate decision; the lifecycle table makes it cheap if wanted. |
| 4 | What the CSVs earned | Map each protection to a transaction, a constraint or a table. Two gains the CSV never had: a real **change history** (corrections overwrite cells today) and allocation without a hidden reservation file. Export contract: the same five files, same columns, same encoding, regenerated after each write and nightly, and **read-only** on the share. |
| 5 | Migration and reversibility | First a shadow phase (database rebuilt nightly from the CSVs and compared), then **one cut-over in a write-freeze window** once all writers go through Box A. Proof: row counts, a per-row hash set, a byte-identical round trip, a clean validator run and an identical Finder. Rollback: the export is format-identical, so turn it back into the system of record. |
| 6 | Timing | Ryan's line holds: decide before onboarding a second group; the Box A app (#28) is the trigger. **One access layer in front of the CSVs** is needed under every option and can start now. Honest size: the full database move is the largest item in M3, and about half of it is that access layer. |

---

## 0.1 Facts this note rests on

Measured or read on 2026-10-17. Re-check before acting.

- **Scale.** `registry_raw.csv` holds 43,000+ rows (issue #29; the "~13,555" in 06_REGISTRIES §1.2 is out of date). The Finder page was ~19 MB at 16k rows and grows in step with the registry (BACKLOG, "Architecture & code review follow-through", §3.2.2).
- **Who writes the registries today, and from where** (10_TOOLS; `tasks/box_a_production_migration_plan.md` §1–§2):
  - the operator GUI, a frozen `gjesus3_ingest.exe` run from the NAS on operators' PCs;
  - the Project Manager, `gjesus3_manager.exe`, on researchers' PCs (assigns a blank `project_id`, creates projects);
  - Data Office tools run by hand on the dev workstation ("that is Ryan's actual job", and it stays that way after the port);
  - the scheduled operations, which move to Box A in the port;
  - the NI live sync on the Mac, until #27 makes Box A pull through the tunnel.

  So there are **at least four machines writing over SMB**, held apart only by `registries/.registry.lock`. That is the single biggest constraint on engine choice.
- **Box A** is a Windows small-form-factor PC (HP Z2 G1i, 1 GbE) running under Ryan's domain account. All data stays on the QNAP. What moves to Box A is the scheduled and serving roles (migration plan §1).
- **Readers.** `grep -rln "registry_raw.csv" tools --include=*.py` finds **101 files**:
  - 35 are production or reusable tools;
  - 42 are `drive_staging/` campaign scripts, mostly one-off;
  - 24 are tests or fixtures.

  Of the 35, about 23 read through `ingest.registry.read_registry` (or `find_acq.build_records`, which calls it). About **ten open the CSV themselves**:
  - `validate_registries.py` (its own `_read_csv_rows`);
  - `ingest/ni_derived.py`, which is in the **live NI sync**;
  - `relink_projects.py`, `relink_mri_regen.py`, `relink_axioscan_collisions.py`;
  - `repair_link_collisions.py`, `recover_subject_ids.py`, `recover_subject_ids_proj0056.py`;
  - `migrate_registry_columns.py`, `migrate_project_naming.py`.

  The list of readers and what each does with a retired row is `tasks/retire_acquisition_review.md` §5.
- **Lists packed into one cell (`;`-joined) today:**
  - `registry_raw.subject_ids` (1–4 animals for an NI scan);
  - `registry_raw.modalities_in_study` (`PT;CT`);
  - `registry_raw.project_id` (one value by policy since 2026-08-12, but readers still accept a list: 06 §2.3b);
  - `registry_datasets.source_acq_ids`;
  - `provenance.csv` `input_refs`, which lives in project folders and is out of scope here.

---

## 1. Engine and placement

**Constraint.**
- **Today's choice.** 06_REGISTRIES §1.3 chose CSV for "no dependencies, human-readable, recoverable". The cost was named as concurrent writes.
- **The lock.** §2.7 is what makes concurrent writes over SMB safe: an `O_EXCL` lockfile (`tools/ingest/locking.py`), which "is adequately atomic for this low-contention case over SMB".
- **Researchers' access.** They double-click the Finder (`tools/generate_index.py`: "zero install, no server, no Python on their side") and open CSVs in Excel (BACKLOG, "Metadata database").
- **Many writers.** Writers run on several machines (§0.1).
- **What stays elsewhere.** XNAT and OMERO remain the lead destinations (13_GJESUS3_ROLE §4.1). A database here is gjesus3's own record, not a replacement for them.

### Option 1A: a SQLite file on the share as the system of record

- **Who can read it from a researcher's PC:** anyone with a SQLite viewer installed (DB Browser for SQLite). Excel cannot open it, so the Excel habit survives only through a CSV export. The Finder is generated from the file, as today.
- **Writers:** every machine in §0.1 would open the same file over SMB. **SQLite's own documentation warns that its file locking is unreliable on network filesystems,** and its WAL mode does not work across machines. A failure no longer means one torn CSV line, which `csv_safe` guards against today. It means a corrupted database file. It is also one writer at a time, which is no better than the lock.
- **What Box A must run:** nothing new. That is the attraction, and it is why "double-clickable" appears in the brief.
- **Verdict:** it gains query power and loses the robustness the CSV has. It is safe only if exactly one machine ever writes. Once that is true, the database can just as well live on that machine's local disk, which is Option 1B.

### Option 1B: a server database on Box A, with every writer going through Box A

There are two variants. The placement is the real decision and the engine is secondary:

- **1B-pg: PostgreSQL** as a service on Box A. Several clients can write at once with real transactions. The dev workstation's hand tools can connect over the network with their own login. It needs a service to install, patch and back up on Windows, and its credentials join the credentials phase of the port (migration plan, Phase 3).
- **1B-lite: a SQLite file on Box A's local disk**, opened only by programs running on Box A (the app, the scheduled operations). There is no service to run, and backup is one file. The same engine as #30's index. The catch is that the dev workstation cannot write to it directly: Data Office hand operations would either run on Box A (remote desktop) or go through the app's interface.

For both variants:
- **Who can read it from a researcher's PC:** through the app in a browser (#28), through the Finder (regenerated from the database), and through the CSV export on the share for Excel.
- **Writers:** every writer has to go through Box A. The operator and manager exes stop writing CSVs over SMB and call the app instead, which is exactly #28's "ingest from one place". **That couples this decision to #28:** the database cannot be the system of record while a frozen exe somewhere can still append to a CSV.
- **What Box A must run:** the database (1B-pg) or nothing extra (1B-lite), plus the app (#28), plus a scheduled dump of the database to the NAS. Box A's local disk is not covered by QNAP snapshots.
- **New risk:** Box A becomes a single point of failure for writes. Today any machine with `J:` mapped can ingest; afterwards, if Box A is down, nobody can. Reads survive through the export and the Finder.

### Option 1C: keep the CSVs as the system of record and add a derived read index

This is #30's spike: a disposable SQLite or Datasette index rebuilt from the CSVs and sidecars.
- **Who can read it:** everyone, as today, plus a faster or dynamic search. Excel and the Finder are untouched.
- **What Box A must run:** the build operation, and Datasette or the app if it is served.
- **What it does not fix:**
  - the many-to-many relations still have no home in the system of record;
  - Ryan's objection about retired acquisitions (§3) stands;
  - every new reader still has to know the CSV rules.

  It fixes search, not truth.
- **It is cheap, needs no decision from this note, and already has its own issue.** This note asks only one thing of it: build the index through the access layer (§6) so the same code later reads the database.

### Recommendation

**Choose 1B as the target placement, reached through 1C.** Let #30 run as scoped. Make "every writer through Box A" an explicit acceptance criterion of #28, because without it a server database cannot be the system of record.

On the engine, **lean 1B-pg (PostgreSQL)**:
- the dev workstation stays a writer by design (migration plan §1);
- during any transition, writers on several machines are a fact.

Choose 1B-lite instead if Ryan would rather run no service and accept that Data Office writes happen on Box A or through the app.

Decide the engine after #30's measurements, not before. At 43k rows both engines are fast enough. The real difference between them is administration, not speed.

**Do not choose 1A.**

---

## 2. The model

**Constraint.**
- **Projects.** 06 §2.3b (✅ DECIDED 2026-08-12) records one project per acquisition. The reason given is that a CSV list "cost eight reader sites that each failed silently". It names the metadata database as "the right home for a real many-to-many, not a CSV column". `ingest/project_ids.py` keeps `add_project_id` / `remove_project_id` "called by no tool" for exactly that migration.
- **Subjects.** 06 §2.8 (✅ DECIDED 2026-06-12) **explicitly vetoed** an acquisition×animal junction table. The link is the packed `subject_ids` cell joined against `registry_subjects.facility_id`. Per-(scan, animal) facts (`scan_position`, `age_at_acquisition`) stay in the sidecar.
- **Project folders.** 05_PROJECTS §3a (✅ DECIDED) says no system-of-record fact may be derived from a project folder's contents.
- **Curated datasets.** 12_CURATED_DATASETS: every label traces to a valid ACQ-ID; `registry_datasets.source_acq_ids` is `;`-packed.

### Tables (one shape, with options inside it)

| Table | One row per | From today's | Notes |
|---|---|---|---|
| `acquisition` | ACQ-ID, live **and** retired (§3) | `registry_raw.csv` minus its packed cells | The primary key over every ACQ-ID ever minted makes "never reused" (06 §7.1) a constraint instead of a rule spread over three files. |
| `project` | project | `registry_projects.csv` | Unchanged columns. `EDITABLE_FIELDS` (06 §4.4) becomes a rule in the access layer. |
| `acquisition_project` | (acquisition, project) | `registry_raw.project_id` + the Project Manager's link events | **The case that motivated the item.** See "Options for acquisition↔project" below. |
| `subject` | animal | `registry_subjects.csv` | Unchanged columns. `facility_id` is the key. |
| `acquisition_subject` | (acquisition, animal) | the packed `subject_ids` | Keeps the order the ids are packed in (`position`), so the export packs them back identically. **This reverses a ✅ veto (06 §2.8)**: Ryan has to lift it explicitly. Moving `scan_position` and `age_at_acquisition` in from the sidecar is optional, and a second decision. |
| `acquisition_modality` | (acquisition, modality code) | the packed `modalities_in_study` | Small, but it removes a whole class of the #8 multi-value hygiene checks (empty segments, trailing `;`, duplicates). Alternative: keep it as a text column with a CHECK constraint. Both work; the relation is cleaner for "every PET scan". |
| `dataset`, `dataset_acquisition` | dataset; (dataset, acquisition) | `registry_datasets.csv` (header-only today), its `source_acq_ids` | A foreign key into `acquisition` turns "a dataset cites an unknown id" into a refused write, and "a dataset cites a retired id" into a check (§3). |
| `acquisition_event` | lifecycle event | `retired_acquisitions.csv` | §3. |
| `change_log` | changed field | nothing today | §4. |
| `publication` | | `registry_publications.csv` | Planned and empty. Create it only when publications are. |

**Session.** `session_id` stays a verbatim column on `acquisition` (06 §2.2: "VERBATIM-from-folder, never normalised"). A `session` table would be the ISA "study" level, but what it carries is #33's question (study-level metadata). Leave it to #33 so it is not designed twice.

**What stays out of the database, at least at first:**
- **Sidecar JSON** (`metadata.json`) stays a file beside the data. It travels with the acquisition, it is what makes the store migratable to XNAT or OMERO (13 §4), and indexing its nested content is #30's job.
- **The pending queues** (`pending_subject_metadata`, `pending_dicom_regen`, `pending_links`) and `ingest_manifest.csv`. The manifest has no reader anywhere (`retire_acquisition_review.md` §5). Move them in a second slice; they have their own drain tools, and keeping them as CSVs in the first cut keeps it smaller.
- **`provenance.csv`** stays in each project folder (07_PROVENANCE §3.2: local by design).

### Options for acquisition↔project

The link table is agreed in the issue. **What a row means** is the open part, because of 05 §3a:

- **2-i. Acquired-for only.** One row per acquisition with `role = acquired-for`, unique per acquisition. This is exactly today's write-once `project_id`, moved to a table so that 2-ii or 2-iii can follow without changing the schema. No behaviour changes.
- **2-ii. Plus links the system made.** When the Project Manager shares an acquisition into a second project, it writes a `role = shared` row with who and when, in the same step that writes that project's `provenance.csv`. This answers "every project this acquisition was linked into". It does **not** answer "what this folder contains now", because a researcher may delete the link (§3a). The row is a fact about a system action, not about the folder, so §3a is respected as long as the row is described that way and never "repaired" against a directory listing.
- **2-iii. Plus importing past shares from `provenance.csv`.** This would backfill 2-ii. It derives registry facts from project folders, which §3a forbids, so it needs §3a to be revisited by agreement (issue #29's last bullet).

**Recommendation for the model:** use the tables above with **2-ii for projects**: it is cheap once the table exists, and the use case it answers is the one 06 §2.3b deferred to the database. Leave 2-iii to the §3a conversation.

For subjects, **lift the 06 §2.8 veto** for the database only. The veto's reason was a junction file next to a CSV, which is not the situation here. Leave `scan_position` and `age_at_acquisition` in the sidecar for now.

### What stays denormalised for the CSV export

`registry_raw.csv` is exported with **today's 28 columns in today's order** (`REGISTRY_FIELDS`):
- `project_id` = the acquired-for project;
- `subject_ids` = the subjects joined with `;` in their stored order;
- `modalities_in_study` = the modalities joined with `;`.

Every reader that exists today then keeps working against the export, and the validator's header check (`header EXACTLY equals REGISTRY_FIELDS`) still passes. Shared links, if 2-ii is chosen, go in a new export file (`acquisition_projects.csv`) and are never packed back into `project_id`. That keeps the silent-split hazard of 06 §2.3b out of the export.

---

## 3. Retired acquisitions

**Constraint.**
- **Ryan's brief** (BACKLOG, 2026-10-01): *"The registry really should be the main source of updated truth about the files. This makes it wrong. … every future thing that believes the registry will need to account for the fact that it could be wrong. Changing a lot of existing stuff is problematic, but we can at least define that set. Anticipating what new things will be built is not possible."*
- **The definable set:** `retire_acquisition_review.md` §5.
- **The invariants** (06 §2.9.2, enforced by `validate_registries.check_retired`):
  - never reused;
  - live or retired, never both;
  - `superseded_by` is live;
  - no curated dataset cites a retired id;
  - a retired id's `/raw/` folder is gone;
  - known `disposition` and `bytes_fate`;
  - a `reidentified` id's superseder is the same acquisition under another code;
  - no chains;
  - permanent tombstones.

### The failure modes, side by side

This is the heart of the question.

- **Tombstone (today):** a reader that forgets the second file **cannot see** a retired id. Asked about it, it says "unknown". That is loud-ish: a lookup fails, nothing is mislabelled. The live file stays correct about what is on disk, because retired bytes are deleted or moved. What is "wrong", in Ryan's sense, is that the registry no longer holds every ACQ-ID that ever existed, so every outside lookup (a dataset citation, a notebook, an old provenance row) needs `resolve_acq_id()` and both files.
- **`status` column:** a reader that forgets to filter **sees a retired row as live**. That is silent:
  - the Finder offers a path to bytes that were deleted;
  - `gather_metadata --project` counts it;
  - a backfill targets it.

  Some of these fail loudly later (the folder is missing), most do not. This is the same kind of failure that killed the `;` project list (06 §2.3b: "failed silently … just fewer rows"). Here it would be more rows instead of fewer.

**So the two designs fail in opposite directions.** The tombstone fails toward "missing", the column toward "present". A database can remove most of the column's risk with a default view. A CSV cannot.

### Option 3A: a `status` column on the acquisition row

Columns: `status` (`live` / `retired`), `disposition`, `superseded_by`, `retired_at`, plus the rest of today's tombstone (`reason`, `bytes_fate`, `moved_to`, `sha256`, `retired_by`, `run_id`, `backup_dir`), either as columns or in a side table.

- **Readers that must change** (§5): every "skip" row (the `find_acq.build_records` filter covers the CLI, the Finder and both Project Manager searches; then `gather_metadata`, `metadata_completeness`, the reusable backfills) and every "special" row:
  - `raw_import` must never assign to a retired row;
  - `acq_id` must count retired rows;
  - the dedup index (a policy question);
  - `update_row` must refuse a retired row;
  - `validate_registries` must skip folder and enrichment checks;
  - `verify_checksums` must say "retired";
  - `catalog.production`.

  Every full rewrite needs the new columns in `REGISTRY_FIELDS` first, and about 10 test fixtures change. **In CSV form this also has to reach the ~10 tools that open the file themselves (§0.1), including the live NI sync's `ingest/ni_derived.py`.**
- **Validator:** "live or retired, never both" becomes structurally impossible (one row, one status). The rest carry over as row checks.
- **Quarantine:** flipping a status back to `live` reverses a retirement, but the row's history is lost unless a history table exists.

### Option 3B: status on the row, a lifecycle (event) table, and a live-only view (database only)

- **`acquisition.status`** is the current state: one value, cheap to filter, and exported.
- **`acquisition_event`** is append-only: `(acq_id, at, event, disposition, superseded_by, bytes_fate, moved_to, sha256, by, run_id, backup_dir, evidence)`. Events: `registered`, `retired`, and later, if wanted, `quarantined`, `purged`, `restored`. Today's `retired_acquisitions.csv` rows map one-to-one onto `retired` events, with `registry_raw_row` no longer needed (the row is still there) and `other_rows_removed` kept as evidence.
- **The `live_acquisition` view** is what the access layer returns by default. A reader has to ask for retired rows by name (`include_retired=True`, as `retire_acquisition_review.md` §5 already suggested for `read_registry`).
- **Readers that must change:** the same "special" rows as 3A, now inside the access layer once rather than at each site. The "skip" rows change nothing, because the default view already skips. A reader that bypasses the access layer and queries the base table fails silently, as in 3A. That is why §6's access layer, and a database login for tools that can read only the view, matter.
- **Validator** (most checks become constraints):

  | Invariant (06 §2.9.2) | Becomes |
  |---|---|
  | never reused | the primary key over all rows |
  | known `disposition` / `bytes_fate` | CHECK constraints |
  | `superseded_by` is live | a foreign key plus a status check at write time |
  | a dataset cites a retired id | a check on `dataset_acquisition` (a refused write, or a validator ERROR; Ryan's choice) |
  | the folder is gone | stays a filesystem check in the validator |
  | a `reidentified` id's superseder is the same acquisition | stays a validator check |
  | no chains | stays the retire tool's refusal |

- **Quarantine:** it becomes two more event types and a `bytes_fate = quarantined`, and a retirement is reversible until a `purged` event. This changes 06 §2.9.2's "Nothing edits or deletes a tombstone row" into "nothing edits an event", which is a smaller promise kept just as strictly.

### Option 3C: keep the tombstone as a separate file or table

This is the decided v1 mechanism, carried into the database as its own table.
- **Readers that must change:** none beyond today's.
- **The cost** is Ryan's objection, unchanged: every new reader built later has to know about the second table. In a database the cost is smaller, because a `UNION` view of every ACQ-ID can live next to it. But that is 3B under another name.

### Quarantine-and-purge-later (BACKLOG 🔽 LOW: reconsider, not build)

What is decided for now is to delete once verified; derivatives move to the project. The alternative moves retired bytes to, for example, `raw\_retired\` and deletes them in a separate purge.

- **For:** a retirement can be undone until the purge. That matters more for `equivalent` and `reidentified` (v2), whose evidence is a comparison and not byte identity.
- **Against:** the disk space is held until the purge; a second step can be forgotten; and the validator invariant "a retired id's `/raw/` folder is gone" would split into "gone or under quarantine".

Under 3B it costs two event types. Under 3A or 3C it is awkward.

**Recommendation:** keep this decision separate from the database. Reconsider it when `equivalent` or `reidentified` is first used in production, not now.

### Recommendation for §3

- **3B in the database.**
- **Before the database, keep the tombstone (3C as it is)**, and **do not add a `status` column to the CSV.** In CSV form, 3A pays the whole cost (about 10 fixtures, every full rewrite, about 10 tools that open the file themselves) and gets the silent failure mode without a view to contain it. That is the trade 06 §2.3b refused for projects.
- **Export:** `registry_raw.csv` stays **live only** and `retired_acquisitions.csv` keeps its schema. Excel users and every existing CSV reader keep today's meaning. An optional third file, `acquisitions_all.csv` (`acq_id, status, superseded_by`), gives the "every id that ever existed" answer without touching the other two.

---

## 4. What the CSVs earned, and must be kept

**Constraint.**
- BACKLOG, "Metadata database": *"Preserve what the CSVs earned the hard way: append-only history, atomic writes, an advisory lock, and a schema that is imported rather than hardcoded (06_REGISTRIES is the contract)."*
- The integrity mirror 06_REGISTRIES ↔ `ingest/registry.py` (CLAUDE.md): any schema move updates both together.

| What it earned | How it works today | In the database | In the export |
|---|---|---|---|
| **Append-only history** | New rows are appended (`registry.append_row`). **Honest finding:** corrections are *not* append-only. `registry.update_row`, the repair tools and the backfills rewrite the whole file in place, and the previous value survives only in the off-NAS backup each repair tool takes and in the CHANGELOG. Tombstones keep removed rows verbatim. | **Better than today:** a `change_log` table (`table, key, field, old, new, at, by, run_id`), written by the access layer in the same transaction as the change. Nothing deletes from it. | Not exported by default. An optional `change_log.csv` for audits. |
| **Atomic writes** | Temp file plus `os.replace` (`registry.update_row`, `projects_registry.update_row`, `subjects_table.write_subjects`). | Transactions. A retire is one transaction instead of two commits plus "re-run it to finish" (06 §2.9.2). | Each export file is written to a temp file and renamed, as today. |
| **The advisory lock** | `.registry.lock` (an `O_EXCL` create, self-breaking after 600 s) around ACQ-ID allocation and the append. `.acq_id_seq.json` reserves an id across the file copy (06 §2.7). | Transactions plus a unique key on `acq_id`. **The reservation has to be kept:** allocation commits an `acquisition` row with `status = reserved` before the copy, and the ingest flips it to `live` afterwards. A failed ingest leaves a reserved row (today's "harmless gap", now visible and countable). `.acq_id_seq.json` retires. | Reserved rows are not exported. |
| **A schema imported from one place** | `REGISTRY_FIELDS`, `RETIRED_FIELDS`, `SUBJECT_FIELDS`, `PROJECT_REGISTRY_FIELDS`. The validator imports them and never hard-codes them. | One schema module holds the table definitions and the export column lists. The 06 ↔ `registry.py` mirror extends to it. The issue suggests generating 06's tables from the schema; that is worth doing, but it is a docs-tooling change of its own. | The export column lists *are* today's constants, so the header check keeps passing. |
| **BOM / CRLF tolerance** | `csv_safe` (BOM-tolerant header, trailing-newline guard); `read_registry` (`utf-8-sig`, then `latin-1`). | Irrelevant inside the database. **It still matters twice:** the migration must read the live files with exactly this tolerance (reuse `read_registry`), and the export must be written exactly as today (UTF-8, no BOM, CRLF: 06 §2.9.1). | Unchanged format. |
| **Excel opens it** | Researchers open the file, and someone *can* save an edit. | Edits go through the app (#28's forms) or a Data Office tool. | **Read-only on the share** (NAS ACL or file attribute). An edit saved to the export would otherwise be silently overwritten by the next export. A `registries\README` line says where corrections go. |
| **Scale (43k rows)** | Every `update_row` reads and rewrites all 43k rows, and the Finder embeds them all. | Trivial for either engine. | The full file, as today. |

### Export contract (proposed)

- **Files:**
  - `registry_raw.csv` (live only, 28 columns);
  - `registry_projects.csv`;
  - `registry_subjects.csv`;
  - `registry_datasets.csv`;
  - `retired_acquisitions.csv` (today's schema, generated from `retired` events);
  - new, optional: `acquisition_projects.csv` (if 2-ii), `acquisitions_all.csv` (§3).
- **Where:** `registries\`, the same paths, so every existing reader, the Finder build and anyone's Excel shortcut keep working.
- **When:** regenerated after each write that commits (batched, at most about once a minute) and in full nightly. Each run also writes `registries\EXPORT_STATUS.txt` with the time, row counts and a hash of each file, so a stale export can be detected. No comment lines go inside the CSVs, because they would break readers.
- **Regenerated, not written through.** The export is always rebuilt from the database, never patched row by row. A regenerated file cannot drift.

**Recommendation:** adopt the table and the contract above. The two items that need Ryan's yes are the `change_log` table (it adds a history the system never had) and making the export read-only.

---

## 5. Migration and reversibility

**Constraint.**
- Issue #29, "Done when": *"A migration from the live CSVs is rehearsed and reversible."*
- Production care: the registry is true production (CLAUDE.md). Every write needs a dry run and Ryan's go.
- The retire tools set the pattern: an off-NAS backup, a rehearsal on a scratch copy, then crash-resumable runs (`retire_acquisition_review.md` §2.1, §4).

### Rehearsal

1. Copy `registries\` off the NAS (the backup pattern of the repair tools).
2. Import the copy into a scratch database, reading the files with `read_registry` and `csv_safe`.
3. Export back and **diff byte for byte** against the copy. The only allowed difference is a documented, deliberate one: for example, the order of rows if the export sorts them, and in that case sort both sides before the diff.
4. Run `validate_registries` against the export: the same errors as against the source (0 today) and the same warning classes.
5. Run the test suite against the access layer's database backend.
6. Generate the Finder from both and diff the data embedded in the page.

### Proving no row was lost

- **Counts** per file and per table, including tombstones and the packed lists. For example: the total of `;`-segments in `subject_ids` must equal the number of `acquisition_subject` rows.
- **A per-row hash set:** the SHA-256 of each row's fields in `REGISTRY_FIELDS` order. The set from the source equals the set from the export.
- **For every retired id**, `resolve_acq_id()` gives the same answer from the source as from the database.
- **The ACQ-ID high-water mark** per (date, instrument) is identical, so the next id minted is identical.

### Dual-write or cut-over

- **5-i. Dual-write:** the access layer writes the CSV and the database, and a nightly comparison checks them. Then the primary is flipped. This is a familiar pattern, but here it would mean dual-writing from four machines over SMB, with the frozen exes on operators' PCs needing a rebuild just to take part. Two writes per change means two ways to fail, and the hardest case (one write succeeds, the other does not) is exactly the one the CSV lock was built to avoid.
- **5-ii. A shadow, then one cut-over:**
  - *Shadow:* the database is rebuilt from the CSVs nightly. That is #30's index plus the model above, and it gives weeks of the "no row lost" comparison at no risk.
  - *Cut-over:* once all writers go through Box A (#28), hold a short write-freeze window (no ingests). Run a final import with all the proofs above, switch the access layer's backend to the database, then make the first export.

**Recommendation: 5-ii.** It never asks the CSV and the database to agree inside one write, and it puts the risky moment in a window that can be watched.

**The trap to close before cut-over:** any old `gjesus3_ingest.exe` or `gjesus3_manager.exe` still run from a PC, or any script on the dev workstation that appends to `registry_raw.csv`, would write into the *export* and fork the record silently. Three measures together:
- rebuild and redistribute the exes, and retire the old ones from the NAS `tools\` folder;
- make the export read-only (§4);
- add a marker file (`registries\DB_IS_SYSTEM_OF_RECORD`) that the CSV backend refuses to write past.

### Rollback

The export is format-identical to today's files, so a rollback means:
1. stop writes;
2. take a final export;
3. make it writable again;
4. switch the access layer back to its CSV backend.

That is possible for as long as **the CSV backend is kept and tested**. Proposal: keep it until one full month after cut-over with no rollback, plus the first onboarding of another group. Changes made in the database that the CSV cannot hold (shared links under 2-ii, `change_log`, events beyond `retired`) would be lost in a rollback. Say this in the cut-over plan.

---

## 6. Timing

**Constraint.**
- Ryan: reconsider the tombstone **"before expanding to other groups"** (BACKLOG MEDIUM).
- The server is the trigger (BACKLOG, "Metadata database": "a server makes a database practical where a double-clickable CSV on an SMB share does not").
- The triage (`tasks/backlog_triage_2026-10-10.md`) puts #29 in **M3**, after the port (#26), alongside the app (#28) and the search index (#30).

### What can be built before any decision: one access layer

Every option needs it:
- the database needs it as the switch between backends;
- #30's index needs it to read the same way the database will later;
- even keeping the CSVs gains from it, because Ryan's "every future thing that believes the registry" problem is solved by making the future thing *call* the layer rather than *know* the rules.

**Shape (names illustrative):**
- one module in `tools/ingest/`;
- reads: `live_acquisitions()`, `all_acq_ids()` (live, retired and reserved: for allocation and dedup), `get(acq_id)` (today's `resolve_acq_id`), `projects_of(acq_id)`, `subjects_of(acq_id)`;
- writes: `register`, `update`, `retire`, `assign_project`;
- behind it, today's CSV code unchanged (`registry.py`, `retired.py`, `project_ids.py`, `subjects_table.py`, `projects_registry.py`, `locking.py`, `csv_safe.py`).

**Size, honestly:**
- the module itself is small, since it is mostly existing functions behind one door;
- moving the ~35 production and reusable tools onto it is the work. About 23 are already one call away (`read_registry`, `find_acq.build_records`). About 10 open the file themselves (§0.1); move the live ones first: `ingest/ni_derived.py` (live NI sync), `validate_registries.py`, `relink_projects.py`;
- the 42 `drive_staging/` campaign scripts stay as they are unless reused;
- the 24 test files mostly keep building fixtures from `REGISTRY_FIELDS`.

This is a code branch (`feat/registry-access-layer` or similar) and needs Ryan's go like any other. It does not need the engine decision.

### Other work that needs no decision

- **A round-trip harness:** CSV → in-memory model (the tables of §2) → CSV, byte-identical, run against a copy of the live files. It is the migration's proof (§5), written before there is a migration to prove.
- **#8's multi-value hygiene checks** on `subject_ids`, `modalities_in_study` and `project_id`. They clean the data the migration will split into tables, and they are in M1 anyway.
- **#30 as scoped**, built through the access layer.

### Size of each option (files and readers)

| Option | What changes | Rough size |
|---|---|---|
| **1C only** (CSVs plus #30's index) | A build operation; no reader changes | Small. Already its own issue. |
| **3A now, in the CSV** | `migrate_registry_columns` on production, `REGISTRY_FIELDS`, about 10 fixtures, the ~20 reader sites of the §5 table across about 35 files, the ~10 tools that open the CSV themselves, the validator, then the frozen exes rebuilt | Medium, with the silent-failure surface. **Not recommended.** |
| **1B + §2 + 3B** (the database) | The access layer (all ~35 tools); a schema module plus the export; the migration tool and harness; the writers moved behind Box A (#28); the database service or file plus a backup operation on Box A; the specs 06, 10, 11 and 12 rewritten where they describe CSV mechanics; the CLAUDE.md integrity-mirror line | **Large: the biggest item in M3.** About half of it is the access layer, which is worth building under every option. |

### Recommendation for timing

- **Now:** the access layer and the round-trip harness, plus #8 and #30 as already planned.
- **After the port:** settle the questions in §7.
- **The cut-over** goes after #28's app is the only writer and before a second group is onboarded. If a second group is coming before the app exists, the tombstone stays and the second group's onboarding should include "uses the access layer" as a rule for any new tool.

---

## 7. Decisions Ryan has to make, in order

1. **Placement (§1).** Is a server database on Box A the target, and is "every writer goes through Box A" an acceptance criterion of #28? Everything after this depends on it.
2. **Go for the access layer and the round-trip harness (§6).** This is independent of every choice below.
3. **The model (§2).** Lift the 06 §2.8 junction veto for the database; choose 2-i, 2-ii or 2-iii for acquisition↔project. 2-iii only with the 05 §3a conversation.
4. **Retired acquisitions (§3).** 3B in the database, with the tombstone kept until then. And whether a dataset citing a retired id is a refused write or a validator ERROR.
5. **Engine (§1).** PostgreSQL or SQLite on Box A, after #30's measurements.
6. **The CSV contract (§4).** Which files, regenerated after each write, export read-only, `change_log` yes or no.
7. **The cut-over (§5).** Shadow then cut-over, the length of the rollback window, and the plan for the old exes.
8. **Quarantine (§3).** Separate and LOW. Reconsider at the first production use of `equivalent` or `reidentified`.
9. **05 §3a (project-folder ownership).** By agreement with the group, not as part of a tool change, and only if 2-iii is wanted.

## 8. What can be built before any decision

- The **access layer** in front of today's CSVs (needs a code-branch go, not a design decision).
- The **round-trip harness** (CSV → model → CSV, byte-identical, on a copy).
- **#8's multi-value hygiene checks.**
- **#30's index spike**, built through the access layer.
- Correcting 06_REGISTRIES §1.2's row counts. This is a surgical STATUS-level edit, for the next docs pass; it is not made here.
