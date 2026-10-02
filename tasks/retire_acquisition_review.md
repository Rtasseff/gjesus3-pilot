# Review: `retire_acquisition.py` — retiring an ACQ-ID (branch `feat/retire-acquisition`)

**Date:** 2026-10-01 · **Status:** built, unit-tested and rehearsed on a scratch copy. **Not merged, and
never run against production** (not even a dry run: the drives ingest is using the NAS).
**Coordinator review 2026-10-01: approved with one change — a retirement never deletes a subject row —
now made (2026-10-02, §2.7). Ryan's decisions are recorded in §7.** The coordinator merges.

Decisions implemented: CHANGELOG 2026-10-01 (Ryan) — tombstone file, delete once verified, v1 =
duplicate + derivative, Data Office only. Specs: [06_REGISTRIES §2.9](../mfb-rdm-docs/06_REGISTRIES.md),
[10_TOOLS §3.9](../mfb-rdm-docs/10_TOOLS.md), [11_OPERATIONS §5.7](../mfb-rdm-docs/11_OPERATIONS.md).

---

## 1. What was built

| File | What |
|---|---|
| `tools/retire_acquisition.py` | The CLI. Dry run by default; `--execute` writes. Single id or `--list`. Dispositions `duplicate`, `derivative`, `orphan`. |
| `tools/ingest/retired.py` | **New registry module**: the tombstone schema `RETIRED_FIELDS` + appender (mirror of 06 §2.9), `original_row()`, and `curated_citations()` (shared by the tool and the validator). |
| `tools/ingest/csv_safe.py` | `split_records` / `record_fields` / `remove_records`: **byte-exact**, atomic record removal (temp + `os.replace`, fsync). Splits on bytes with quote parity, so a quoted newline never ends a record and no other byte is re-encoded. |
| `tools/ingest/registry.py` | `resolve_acq_id()` — the live row, or the tombstone with `superseded_by` followed to the live id; `unknown` otherwise. |
| `tools/ingest/acq_id.py` | The allocator **counts tombstoned ids** (see §2.4). |
| `tools/ingest/config.py` | The ingest dedup index **includes retired rows** (see §2.5 — a policy point for Ryan). |
| `tools/ingest/provenance.py` | `append_entry(..., unique_on=...)`: an event row on an existing path (re-pointed / removed link) needs a wider idempotency key than `output_path`. Default unchanged. |
| `tools/validate_registries.py` | Four tombstone ERRORs (§2.6). A no-op when the tombstone file does not exist, so production output is unchanged today. |
| `tools/find_acq.py` | `find_acq.py ACQ-…` on a retired id prints what replaced it (via `resolve_acq_id`). |
| `tools/test_retire_acquisition.py` | 14 test groups, no NAS/network (§3). |
| `tasks/retire_lists/*.csv` | The proposed first production lists (§6). |
| Docs | 06 §1.2/§2.6/§2.8.3/**§2.9**/§7.1 · 10 §2.1 (paragraph amended, inventory) + §3.2 + **§3.9** · 11 **§5.7** · 00 Last Updated · `INGEST_CLI.md` · `tools/INDEX.md` · `GLOSSARY.md`. |

## 2. Design, and where it departs from the handoff

### 2.1 Order of operations (crash-resumable, idempotent)

0. **Window:** refuse while `registries\.registry.lock` exists or `registry_raw.csv` changed in the last
   15 min. The tool's own last commit does not count (the tombstone is written just before `registry_raw`;
   if it is at least as new, the last write was a retire run). A dry run only warns.
1. **Plan (read-only):** classify each id from disk — `fresh`, `commit-interrupted` (live **and**
   tombstoned), `committed` (tombstoned only), or an orphan candidate; check every precondition; hash;
   work out every row, link and file action. **Any refusal stops the whole run before a write** (a list is
   all-or-nothing). A tombstoned id follows its tombstone, not the arguments.
2. **Backup** (`<backup-root>\gjesus3_retire_backup_<run>\`): every `registries\*.csv` + `.acq_id_seq.json`,
   each retiree's three sidecars, each touched project's `provenance.csv`, an orphan's whole folder; every
   copy SHA-256-verified; `backup_manifest.csv`. **No backup on a no-op run.**
3. **Derivative:** hard-link into the project subfolder; verify identity + SHA-256; append the `moved-to`
   provenance event.
4. **Commit, under the registry lock:** read the live state again; compute every row to remove; append the
   tombstone **first** (carrying all of them, verbatim); then remove the `registry_raw`, `ingest_manifest`,
   `pending_subject_metadata`, `pending_dicom_regen`, `pending_links` rows. **`registry_subjects.csv` is
   never touched** (§2.7). Header-checked; byte-exact; read back.
5. **Links, then bytes.** Each link's provenance event is appended **before** its action (write-ahead —
   see 2.3); a duplicate is re-hashed against the survivor right before its folder is deleted unless this
   run already hashed both; a derivative's placement is re-verified before `/raw/` is deleted.
6. **Provenance:** any remaining events (e.g. `retired` for a link a researcher already removed).
7. **`index.html`** for each touched project (`generate_index.py --project …`).
8. **Self-check + report:** tombstoned, absent from `registry_raw`, `/raw/` folder gone, every link as
   reported, derivative bytes at `moved_to` with the tombstoned SHA-256, no event missing.
   `<backup>\RET-…_report.csv` + `.log`.

Exit codes: 0 done/no-op · 2 refused · 3 backup failed · 4 stopped mid-run (re-run) · 5 self-check failed.

### 2.2 Link identity: file id, not only hashes (deviation, stronger)

The handoff says link counts can't be read over SMB, so verify by hashing. Link **counts** can't
(`st_nlink` reads 1), but **file ids** can: on the live share `os.path.samefile` is True for
`claudia\raw_linked\CELL_…_ID58T_HIF1A_10x.czi` vs `ACQ-20260507-CELL-001.czi` and **False** vs its
byte-identical twin `ACQ-20260507-ZWSI-001.czi` (checked read-only, stat only). That matters: for a
duplicate, **hashes cannot tell the two twins apart**; only identity says whether a project link holds the
retiree's inode (which would keep its bytes alive as an unregistered copy) or the survivor's.
`reopen_project.py` already relies on `samefile` in production. The tool uses identity for "which file"
and SHA-256 for "same content", and hashes each re-pointed link after the change as the handoff asked.

### 2.3 Provenance events are write-ahead (found by the crash sweep)

First version wrote events at the end. A crash between removing a link and writing its event made the
re-run find the link gone and record *"already deleted or renamed (researcher)"* — false. Now each event is
appended before its action; a re-run that finds the link gone **and** the tool's own event treats it as done.
The sweep in test 13/14 crashes after every step and checks the end state and the exact event list.

### 2.4 Never-reuse no longer rests on `.acq_id_seq.json` alone (code change outside the tool)

`allocate_acq_id` takes `max(registry_raw, .acq_id_seq.json) + 1`. With the row moved out, a retired id
that was its prefix's high-water mark would be **re-minted** if the reservation file lacked it — and
06 §2.7 says a purge of `registries/` resets that file; `generate_acq_id` (dry-run / operator preview)
ignores it entirely. Today the file covers all 754 prefixes (checked against the snapshot), so nothing is
at risk now. `_max_seq_in_registry` now also counts `retired_acquisitions.csv` (test 11 deletes the
reservation file and confirms `-029` retired → next is `-030`).

### 2.5 Retired rows keep blocking re-ingest (code change; **policy point for Ryan**)

`config._build_dedupe_index` keys on `(date, original_name)` of **live** rows. After `ACQ-20260304-ZWSI-023`
leaves, re-running `recipes/aua.yaml` on the same staging would ingest that file **a third time**. The index
now includes the tombstones' original rows. That is the conservative choice (a retired duplicate or
derivative should not come back), but it means a retired source can only be re-ingested after its
tombstone is dealt with. **Confirm or reverse.**

### 2.6 Validator: four ERRORs, not three

The three asked for — an id both live and retired (also the signature of a crash mid-commit); a
`superseded_by` that is not live (blank only for `orphan`); a curated dataset citing a retired id — plus
**a retired id whose `/raw/` folder still exists** (a run that stopped before its bytes step; otherwise an
unregistered folder in `/raw/` would go unreported). Header check too. There is **no orphan-folder logic**
in the validator to adjust: the folder-exists check walks live rows only, and nothing looks for
unregistered folders (BACKLOG 2026-08-13 still open).

### 2.7 Other deliberate choices

- **`retired_by`, not `operator`.** In this repo `operator` means who ran the equipment (06 §2.3a-bis), and
  the verbatim original row carries that column. A tombstone column of the same name meaning "Data Office
  person" would be the exact confusion the 2026-06-09 rename removed.
- **Tombstone superset:** besides the handoff's columns, `moved_to`, `original_canonical_path`,
  `backup_dir`, and `other_rows_removed` (JSON of every other removed record, verbatim) — so a retirement
  is fully reversible from the tombstone alone, and a future status-column migration has everything.
- **`sha256` of a folder primary** = SHA-256 of its sorted `relpath<TAB>sha256` lines (documented in 06).
- **Survivor sanity:** a duplicate is refused if the **survivor's** fresh bytes don't match its own
  `checksums.json` (the 2026-09-30 truncation lesson: investigate before retiring a twin into it).
- **Derivative safety:** refused if the `/raw/` folder holds anything besides the primary and the three
  sidecars (it would be lost). Destination name = basename of `original_name` (`--dest-name` overrides);
  an existing different file at that name → refused.
- **Links found through provenance** (`input_refs`, across every project). A link created and never
  recorded can't be found — but the ingest always records one when it creates one. Notably the 22 operator
  twins **never got a link at all** (their link names were already taken, so `create_hardlink` skipped and
  `append_entry` was a no-op) — confirmed in production provenance: 0 rows for `ZWSI-023…044`.
- **A file at a link path that is not the acquisition's bytes** (`foreign`) is left alone and reported.
  For a folder-of-links, any extra file a researcher put inside makes it `foreign` too — never deleted.
- **Inventory gap fixed:** 10_TOOLS §2.1's "everything an ingest writes" table was missing
  `pending_dicom_regen.csv` and `pending_links.csv` (both keyed by `acq_id`, written by `ingest_raw.py`
  L1073 / L1569). Added as rows #11–#12; the tool removes those rows too.
- **Subjects are never deleted** (✅ 06 §2.8.3 — Ryan, 2026-10-01: *an animal existed whether or not
  gjesus3 keeps its acquisition*). The first version removed a subject row no other live acquisition
  referenced, as the handoff and the 10_TOOLS inventory row #5 said; the coordinator's review reversed
  that. A retirement now **never** touches `registry_subjects.csv`. The additive row I had put in
  06 §2.8.3 is reverted (the table is exactly as on `main`), and the contradiction is fixed where it
  lived: inventory row #5's *Reverse by* now reads *"never: subjects are never deleted"*.

### 2.8 Things the tool does not do (flag for the procedure)

- The **global** Finder page is rebuilt by the 03:00 job; until then it lists the retired id (procedure
  step 6 says regenerate it after a batch).
- A **derivative's ACL**: a hard link shares raw's security descriptor, so the moved file stays read-only
  for researchers inside their project. Probably fine (it is still the instrument's output); if it should
  be researcher-editable, it needs a copy instead of a link. **Ryan's call.**
- Project `start_date` / `last_activity` are not recomputed (no ingest maintains them either — BACKLOG).
- **Permissions on the NAS:** deleting from `/raw/` needs Delete rights on the folder. Untested on the live
  share (the rehearsal was on local disk). The first production run's dry run won't show it; the execute's
  first delete will — and it fails safe (exit 4, re-run after fixing).

## 3. Tests

`python tools/test_retire_acquisition.py` — **ALL PASSED**. A fake NAS with real hard links:

1. byte-exact removal (quoted multi-line field, `""`, UTF-8, missing final newline); 2. dry run writes
nothing; 3. refusals: re-save bytes, curated citation (dataset named), closed project (reopen hint),
unknown id, survivor retired in the same list (whole list refused), a held registry lock — none writes;
4. duplicate with a project link re-pointed (same name, now the survivor's inode), byte diff of
`registry_raw.csv` / `ingest_manifest.csv`, tombstone verbatim + no BOM + CRLF, shared subject kept,
backup contents (no duplicate bytes); 5. idempotent re-run (no write, no backup) and the chain refusal;
6. duplicate whose survivor is already linked there (link removed), a subject **only the retiree
referenced is kept** and `registry_subjects.csv` is byte-identical, pending row removed and kept verbatim; 7. derivative; 8. crash after the tombstone (validator flags it, re-run finishes, one
tombstone); 9. crash after links (validator flags the folder, re-run re-hashes and deletes, one event);
10. orphan; 11. `resolve_acq_id`, allocator without `.acq_id_seq.json`, dedup; 12. validator ERRORs;
13–14. **crash after every step** (`placed`, `tombstone`, `commit`, `links`, `bytes`, `provenance`) for a
derivative and a duplicate: exit 4 → re-run 0 → re-run no-op, identical end state, exact event list.

**All 25 test suites in the repo pass** (the shared modules changed: `csv_safe`, `registry`, `acq_id`,
`config`, `provenance`, the validator).

## 4. Rehearsal on real data (scratch only)

`D:\projects\gjesus3\scratch_retire\nas\` — **copies** of production's registries (snapshot 2026-10-01
09:53, mid-B08), of 8 real acquisition folders and 1 orphan, the 4 projects' `provenance.csv` /
`_project.yaml`, the curated datasets' text files, and the 6 project links **recreated inside scratch**
(each confirmed, stat-only, to be the same file as raw in production). No hard link points at `J:`. Log:
`D:\projects\gjesus3\scratch_retire\rehearsal\rehearsal_log.txt`; driver kept in the session scratchpad.

| # | Case | Result |
|---|---|---|
| — | Baseline | every registry file BOM-free CRLF ✅ |
| 1 | `ZWSI-031` duplicate of `ZWSI-009` (operator twin, no link, shared subject `146-AE-biomaGUNE-1123`) | dry run → hashes identical; execute 0; subject kept ✅ |
| 2 | `CELL-010` duplicate of `ZWSI-010`: fake `DS-SEG-9999` citing it | refused, dataset named ✅ |
| 2 | … crash injected after the commit | exit 4; validator: "retired, but its /raw/ folder still exists" ✅ |
| 2 | … re-run | 0; `claudia\raw_linked\CELL_MFB_AUA_1022_ID72T_VEGFA_10x.czi` keeps its name, **is** `ZWSI-010` ✅ |
| 3 | `LSM9-016` duplicate of `LSM9-001` (re-save) | refused: 2.7 vs 3.7 MB, not byte-identical ✅ |
| 4 | derivative → closed `AE-biomaGUNE-1521` | refused, reopen hint ✅ |
| 4 | `CELL-006` derivative of `CELL-007` → `AE-biomaGUNE-1123` (mechanics only) | `outputs\derived\ID118_lung_1.czi`; raw_linked link gone; project `index.html` regenerated without it ✅ |
| 5 | orphan `ACQ-20260710-MRI-001` | backed up whole, tombstoned without a row, deleted ✅ |
| 6 | all four again as a list | no-op, no registry byte changed, no backup ✅ |
| 7 | byte diff, every registry file | only the retirees' records gone; all others byte-identical, in order ✅ |
| 8 | validator before/after | 21,784 → 21,781 rows; **no new error class** (only the scratch-expected "folder not found" and the known 10,314 `operator` placeholders) ✅ |

## 5. Readers of `registry_raw.csv` — the "definable set" for a status column (BACKLOG MEDIUM)

If a `status` column replaced the tombstone file, these would have to change. Almost everything goes
through `ingest/registry.py::read_registry` — the natural single switch (`include_retired=False`).

| Group | Reader | Uses rows for | Under a status column |
|---|---|---|---|
| Researcher-facing | `find_acq.build_records` | the search engine behind the CLI, the Finder (`generate_index.py`) and the Project Manager (`manager/acq_search.py`, `manager/gui/app.py`) | **skip** — one filter here covers all four |
| | `manager/raw_import._record_project_when_unassigned` | locked read-modify-write of `project_id` | **special:** never assign to a retired row; write it back unchanged |
| | `operator/gui/app.py` (via `ingest_raw._touched_project_ids`) | which project indexes to refresh | no (new ids only) |
| Ingest | `ingest/acq_id._max_seq_in_registry` / `generate_acq_id` / `allocate_acq_id` | ACQ-ID high-water | **special: must COUNT retired rows** (done now for the tombstone) |
| | `ingest/config._build_dedupe_index` (+ `operator/preview.py`) | "already ingested" | **special/policy** (§2.5) |
| | `ingest/registry.update_row` | in-place field update | special: refuse a retired row |
| Validators | `validate_registries.validate` | all checks | special: keep id/format checks, skip folder/enrichment for retired, validate `status` |
| | `verify_checksums.find_acq_folder` | `--acq` lookup | special: say "retired" |
| | `gather_metadata`, `metadata_completeness` | `--project` / `--acq` filters | skip (say "retired" for `--acq`) |
| Backfills (reusable) | `backfill_dicom_regen`, `backfill_microscopy_anatomy`, `backfill_mri_anatomy` | target selection + full rewrite | skip for targets; **keep rows on rewrite** |
| One-off / done | `backfill_microscopy_bestguess`, `backfill_pending_dicom`, `backfill_subjects_table`, `recover_subject_ids*`, `relink_projects`, `relink_mri_regen`, `relink_axioscan_collisions`, `migrate_project_naming` | historical | skip; `recover_subject_ids_proj0056.fix_subjects` must still count retired references |
| Schema | `migrate_registry_columns` | adding columns | **the tool that would add `status`** |
| Campaign | `drive_staging/catalog.production` | production hashes to dedup against | special: a retired id has no folder |

Other findings: every full rewrite (`update_row`, `raw_import`, the backfills' `_update_registry`,
`recover`'s byte rewrite) would need `status` in `REGISTRY_FIELDS` first; `manager/acq_search._stamp`
watches only `registry_raw.csv` / `registry_projects.csv` mtimes (fine today — a retirement also rewrites
`registry_raw.csv`); `ingest_manifest.csv` has **no reader** anywhere; the only `registries/*.csv` globs are
backups (`recover_subject_ids*`), so the new file is picked up harmlessly. Test fixtures built from
`REGISTRY_FIELDS` (≈10 files) would change with a new column.

## 6. Proposals for the first production uses (each its own approved operation)

**Preconditions for all three:** the drives ingest is finished and merged; nothing else is ingesting; this
branch is merged. Run from the repo root on the workstation. Full dry runs hash over SMB — run them when
the NAS is quiet. `--quick` (sizes only) is a cheap first look.

### (a) The 32 SHA-256 twins — ✅ APPROVED, two operations: `tasks/retire_lists/2026-10_sha256_twins_zwsi.csv` (22) then `…_cell.csv` (10)

**Proposed keep/retire rule: keep the registration that the project already uses; on a tie, the older
one.** Here every criterion points the same way for all 32 pairs:

- **22 `ZWSI`↔`ZWSI` (`PROJ-0014` / `PROJ-0018`):** keep `ZWSI-001…022` (2026-06-14, the committed bulk
  config `tools/configs/axioscan7_mfb_20260614.yaml`; each has the project link and its provenance row);
  retire `ZWSI-023…044` (2026-08-12, the NAS operator recipe `recipes/aua.yaml`). The twins **have no
  project link and no provenance row** (their link names were taken), same project, same subject and
  sample. **Nothing in any project folder changes.**
- **10 `CELL`↔`ZWSI`:** keep `ZWSI-001…010` of 2026-05-07 (`PROJ-0019` `AE-biomaGUNE-1022`): the device
  metadata says AxioScan 7, the filename says protocol 1022, the subject ids are resolved, and it is the
  older registration. Retire `CELL-001…010` (`PROJ-0039` `claudia`, blank subject, wrong instrument code).
  Their 10 `claudia\raw_linked\CELL_…` links are **re-pointed at the ZWSI survivors under the same names**,
  so Claudia's folder looks exactly as before. **This also fixes 10 of the 25 mis-coded rows** (BACKLOG
  "Dedup identity").

Checked read-only against the 2026-10-01 snapshot and live provenance: all 32 survivors are older and
linked; no retiree or survivor is cited by a curated dataset; no subject row is touched (none ever is);
each retiree has exactly one other row
(`ingest_manifest.csv`). Size: 22.2 GB + 4.5 GB per side → a full dry run reads ≈ 53 GB over SMB; the
execute reads it again plus the 10 re-pointed links (4.5 GB). Frees ≈ 26.7 GB.

| # | Retire | Keep (survivor) | Kind | MB | Retiree project | Survivor project | Retiree's project link | Subject |
|---|---|---|---|---|---|---|---|---|
| 1 | `ACQ-20260304-ZWSI-023` | `ACQ-20260304-ZWSI-001` | ZWSI↔ZWSI | 276.0 | PROJ-0014 | PROJ-0014 | none | 12-AE-biomaGUNE-1123 (kept) |
| 2 | `ACQ-20260304-ZWSI-024` | `ACQ-20260304-ZWSI-002` | ZWSI↔ZWSI | 306.1 | PROJ-0014 | PROJ-0014 | none | 135-AE-biomaGUNE-1123 (kept) |
| 3 | `ACQ-20260304-ZWSI-025` | `ACQ-20260304-ZWSI-003` | ZWSI↔ZWSI | 281.2 | PROJ-0014 | PROJ-0014 | none | 136-AE-biomaGUNE-1123 (kept) |
| 4 | `ACQ-20260304-ZWSI-026` | `ACQ-20260304-ZWSI-004` | ZWSI↔ZWSI | 277.1 | PROJ-0014 | PROJ-0014 | none | 137-AE-biomaGUNE-1123 (kept) |
| 5 | `ACQ-20260304-ZWSI-027` | `ACQ-20260304-ZWSI-005` | ZWSI↔ZWSI | 8144.6 | PROJ-0014 | PROJ-0014 | none | 138-AE-biomaGUNE-1123 (kept) |
| 6 | `ACQ-20260304-ZWSI-028` | `ACQ-20260304-ZWSI-006` | ZWSI↔ZWSI | 286.2 | PROJ-0014 | PROJ-0014 | none | 139-AE-biomaGUNE-1123 (kept) |
| 7 | `ACQ-20260304-ZWSI-029` | `ACQ-20260304-ZWSI-007` | ZWSI↔ZWSI | 343.5 | PROJ-0014 | PROJ-0014 | none | 140-AE-biomaGUNE-1123 (kept) |
| 8 | `ACQ-20260304-ZWSI-030` | `ACQ-20260304-ZWSI-008` | ZWSI↔ZWSI | 253.4 | PROJ-0014 | PROJ-0014 | none | 145-AE-biomaGUNE-1123 (kept) |
| 9 | `ACQ-20260304-ZWSI-031` | `ACQ-20260304-ZWSI-009` | ZWSI↔ZWSI | 242.2 | PROJ-0014 | PROJ-0014 | none | 146-AE-biomaGUNE-1123 (kept) |
| 10 | `ACQ-20260304-ZWSI-032` | `ACQ-20260304-ZWSI-010` | ZWSI↔ZWSI | 284.5 | PROJ-0014 | PROJ-0014 | none | 147-AE-biomaGUNE-1123 (kept) |
| 11 | `ACQ-20260304-ZWSI-033` | `ACQ-20260304-ZWSI-011` | ZWSI↔ZWSI | 323.2 | PROJ-0014 | PROJ-0014 | none | 14-AE-biomaGUNE-1123 (kept) |
| 12 | `ACQ-20260304-ZWSI-034` | `ACQ-20260304-ZWSI-012` | ZWSI↔ZWSI | 252.2 | PROJ-0014 | PROJ-0014 | none | 152-AE-biomaGUNE-1123 (kept) |
| 13 | `ACQ-20260304-ZWSI-035` | `ACQ-20260304-ZWSI-013` | ZWSI↔ZWSI | 293.8 | PROJ-0014 | PROJ-0014 | none | 153-AE-biomaGUNE-1123 (kept) |
| 14 | `ACQ-20260304-ZWSI-036` | `ACQ-20260304-ZWSI-014` | ZWSI↔ZWSI | 335.2 | PROJ-0014 | PROJ-0014 | none | 16-AE-biomaGUNE-1123 (kept) |
| 15 | `ACQ-20260304-ZWSI-037` | `ACQ-20260304-ZWSI-015` | ZWSI↔ZWSI | 305.5 | PROJ-0014 | PROJ-0014 | none | 41-AE-biomaGUNE-1123 (kept) |
| 16 | `ACQ-20260304-ZWSI-038` | `ACQ-20260304-ZWSI-016` | ZWSI↔ZWSI | 323.9 | PROJ-0018 | PROJ-0018 | none | 61-AE-biomaGUNE-1321 (kept) |
| 17 | `ACQ-20260304-ZWSI-039` | `ACQ-20260304-ZWSI-017` | ZWSI↔ZWSI | 279.7 | PROJ-0018 | PROJ-0018 | none | 62-AE-biomaGUNE-1321 (kept) |
| 18 | `ACQ-20260304-ZWSI-040` | `ACQ-20260304-ZWSI-018` | ZWSI↔ZWSI | 274.1 | PROJ-0018 | PROJ-0018 | none | 63-AE-biomaGUNE-1321 (kept) |
| 19 | `ACQ-20260304-ZWSI-041` | `ACQ-20260304-ZWSI-019` | ZWSI↔ZWSI | 3335.2 | PROJ-0018 | PROJ-0018 | none | 64-AE-biomaGUNE-1321 (kept) |
| 20 | `ACQ-20260304-ZWSI-042` | `ACQ-20260304-ZWSI-020` | ZWSI↔ZWSI | 5161.2 | PROJ-0018 | PROJ-0018 | none | 64-AE-biomaGUNE-1321 (kept) |
| 21 | `ACQ-20260304-ZWSI-043` | `ACQ-20260304-ZWSI-021` | ZWSI↔ZWSI | 316.6 | PROJ-0018 | PROJ-0018 | none | 65-AE-biomaGUNE-1321 (kept) |
| 22 | `ACQ-20260304-ZWSI-044` | `ACQ-20260304-ZWSI-022` | ZWSI↔ZWSI | 283.9 | PROJ-0018 | PROJ-0018 | none | 70-AE-biomaGUNE-1321 (kept) |
| 23 | `ACQ-20260507-CELL-001` | `ACQ-20260507-ZWSI-001` | CELL↔ZWSI | 576.3 | PROJ-0039 | PROJ-0019 | `claudia\raw_linked\CELL_MFB_AUA_1022_ID58T_HIF1A_10x.czi` → re-point | – |
| 24 | `ACQ-20260507-CELL-002` | `ACQ-20260507-ZWSI-002` | CELL↔ZWSI | 437.9 | PROJ-0039 | PROJ-0019 | `…\CELL_MFB_AUA_1022_ID58T_VEGFA_10x.czi` → re-point | – |
| 25 | `ACQ-20260507-CELL-003` | `ACQ-20260507-ZWSI-003` | CELL↔ZWSI | 482.8 | PROJ-0039 | PROJ-0019 | `…\CELL_MFB_AUA_1022_ID59T_HIF1A_10X.czi` → re-point | – |
| 26 | `ACQ-20260507-CELL-004` | `ACQ-20260507-ZWSI-004` | CELL↔ZWSI | 396.9 | PROJ-0039 | PROJ-0019 | `…\CELL_MFB_AUA_1022_ID59T_VEGFA_10x.czi` → re-point | – |
| 27 | `ACQ-20260507-CELL-005` | `ACQ-20260507-ZWSI-005` | CELL↔ZWSI | 368.3 | PROJ-0039 | PROJ-0019 | `…\CELL_MFB_AUA_1022_ID60T_HIF1A_10x.czi` → re-point | – |
| 28 | `ACQ-20260507-CELL-006` | `ACQ-20260507-ZWSI-006` | CELL↔ZWSI | 476.6 | PROJ-0039 | PROJ-0019 | `…\CELL_MFB_AUA_1022_ID60T_VEGFA_10x.czi` → re-point | – |
| 29 | `ACQ-20260507-CELL-007` | `ACQ-20260507-ZWSI-007` | CELL↔ZWSI | 511.5 | PROJ-0039 | PROJ-0019 | `…\CELL_MFB_AUA_1022_ID70T_HIF1A_10X.czi` → re-point | – |
| 30 | `ACQ-20260507-CELL-008` | `ACQ-20260507-ZWSI-008` | CELL↔ZWSI | 472.0 | PROJ-0039 | PROJ-0019 | `…\CELL_MFB_AUA_1022_ID70T_VEGFA_10x.czi` → re-point | – |
| 31 | `ACQ-20260507-CELL-009` | `ACQ-20260507-ZWSI-009` | CELL↔ZWSI | 421.6 | PROJ-0039 | PROJ-0019 | `…\CELL_MFB_AUA_1022_ID72T_HIF1A_10x.czi` → re-point | – |
| 32 | `ACQ-20260507-CELL-010` | `ACQ-20260507-ZWSI-010` | CELL↔ZWSI | 354.4 | PROJ-0039 | PROJ-0019 | `…\CELL_MFB_AUA_1022_ID72T_VEGFA_10x.czi` → re-point | – |

**Two operations (Ryan, 2026-10-01), each dry first and then `--execute`, after the drives ingest is
merged.** The 22 `ZWSI` twins first (they touch no project folder), then the 10 `CELL`:

```
:: operation 1 -- the 22 ZWSI twins
python tools\retire_acquisition.py --nas-root J:\gjesus3-data --list tasks\retire_lists\2026-10_sha256_twins_zwsi.csv --quick
python tools\retire_acquisition.py --nas-root J:\gjesus3-data --list tasks\retire_lists\2026-10_sha256_twins_zwsi.csv
python tools\retire_acquisition.py --nas-root J:\gjesus3-data --list tasks\retire_lists\2026-10_sha256_twins_zwsi.csv --execute

:: operation 2 -- the 10 CELL rows (re-points 10 claudia links)
python tools\retire_acquisition.py --nas-root J:\gjesus3-data --list tasks\retire_lists\2026-10_sha256_twins_cell.csv
python tools\retire_acquisition.py --nas-root J:\gjesus3-data --list tasks\retire_lists\2026-10_sha256_twins_cell.csv --execute
```

### (b) The `LSM9` re-save — `ACQ-20250915-LSM9-016` vs `-001`: ✅ **leave it** (Ryan); v2 mode backlogged

Measured on the scratch copies (local, read-only):

| | `-001` | `-016` |
|---|---|---|
| `original_name` | `24h_1.czi` | `Prueba/24h_1.czi` ("Prueba" = test) |
| Registered | 2026-06-15 11:23:11 | 11:23:26 (same best-guess config) |
| Bytes | 3,676,480 | 2,731,104 |
| Project link | `PROJ-0025\raw_linked\LSM9_24h_1.czi` | **none** (name taken), no provenance row |
| Decoded pixels (both subblocks) | identical | identical |
| Metadata XML | identical (0 diff lines) | identical |
| Attachments (EventList, TimeStamps, Thumbnail) | identical payloads | identical payloads |
| Container | 1 `DELETED` segment (472 KB) + metadata double-allocated — ZEN rewrote its metadata **in place** | compact rewrite, no dead space |

So it is **information-identical; only the container layout differs**, and it carries **no** extra
annotation. v1 correctly refuses it (rehearsal case 3). Options:

1. **Leave both** (recommended now): 2.7 MB, no project impact; record it in the BACKLOG item.
2. **v2 "content-equivalent duplicate"** (recommended next): for `.czi`, a duplicate may be retired when
   decoded subblocks, metadata XML and attachment payloads are all identical — the evidence recorded in the
   tombstone. Keep `-001` (older, linked, not in a test folder).
3. Retire `-016` as a `derivative` of `-001` today — possible, nothing is deleted, but it misnames a re-save
   as a derivative and puts a second copy of the same image into the researcher's folder. Not recommended.

Dry run if Ryan picks 3 (or to see the refusal): `python tools\retire_acquisition.py --nas-root J:\gjesus3-data --acq-id ACQ-20250915-LSM9-016 --duplicate-of ACQ-20250915-LSM9-001 --reason "re-save of -001 (Prueba copy)"`

### (c) The 17 orphans — `tasks/retire_lists/2026-10_orphans_20260710_MRI.csv` (`--orphan` mode built)

> ✅ **Retire them (Ryan), but only after the 2026-07-10 session is re-ingested properly.** Facts the
> coordinator established: the folders were created 2026-07-16 09:16 UTC by `ingest_raw.py`; each has an
> empty `.data` folder, a `checksums.json` with no files and no `README.txt` — the no-DICOM placeholder
> shape; the run stopped before the registry append, cause not established. Their session
> `jrc20260710_m12_1125_bis` (animal 12 of protocol 1125, 17 exams) is **not in gjesus3 under any ID**.
> **Agreed order:** (1) a normal MRI ingest of that session from the scanner host — its no-DICOM exams go
> to the DICOM-regen worklist (11_OPERATIONS §5.5) and get fresh IDs (the reservation already holds
> `ACQ-20260710-MRI-` = 17, so they start at `-018`); (2) then `--orphan` retires the 17 empty IDs.

`ACQ-20260710-MRI-001…017`: no registry row, no manifest/pending/provenance row (checked against the
snapshot and live provenance), 108–160 KB each, `.acq_id_seq.json` already holds `ACQ-20260710-MRI- = 17`.
Each folder is backed up whole off-NAS, tombstoned (`disposition=orphan`, no `superseded_by`, no row) and
deleted. The sidecars carry full subject metadata (m12, protocol 1125), which survives in the backup.

```
python tools\retire_acquisition.py --nas-root J:\gjesus3-data --list tasks\retire_lists\2026-10_orphans_20260710_MRI.csv
python tools\retire_acquisition.py --nas-root J:\gjesus3-data --list tasks\retire_lists\2026-10_orphans_20260710_MRI.csv --execute
```

## 7. Ryan's decisions (coordinator review, 2026-10-01 — `ANSWERS_2026-10-01.md`)

| # | Question | Decision |
|---|---|---|
| 1 | The 32 twins (§6a) | ✅ Rule approved: keep what the project uses; tie → the older. **Two operations**: the 22 `ZWSI` pairs, then the 10 `CELL`; each dry then `--execute`, **after the drives ingest is merged**. Lists split (`…_zwsi.csv`, `…_cell.csv`). |
| 2 | Subjects (§2.7) | ✅ **Never delete subject rows** — 06 §2.8.3 stands. Done 2026-10-02: code, tests, docs. |
| 3 | The 17 orphans (§6c) | ✅ Retire, **after** the 2026-07-10 session (`jrc20260710_m12_1125_bis`) is re-ingested. |
| 4 | Dedup blocks re-ingest of a retired source (§2.5) | ✅ Confirmed. **Note for v2's re-identify:** it must not be blocked by its own tombstone. |
| 5 | The `LSM9` re-save (§6b) | ✅ Leave it. The v2 content-equivalent duplicate mode goes to BACKLOG (first user `ACQ-20250915-LSM9-016`). |
| 6 | A derivative's ACL (§2.8) | ✅ Fine as is: read-only via the shared inode. |

## 8. Proposed wording for the coordinator (not applied here)

**`tasks/STATUS.md`** (a line under the historical-drives bullet or §0):

> **ACQ-ID retire tool built, not yet used** (branch `feat/retire-acquisition`, 2026-10-01).
> `tools/retire_acquisition.py` retires duplicates, derivatives and orphan `/raw/` folders into
> `registries/retired_acquisitions.csv` (06 §2.9). Rehearsed on scratch; proposals for the first three
> production uses (32 twins in two operations, approved; the `LSM9` re-save left; 17 orphans after the 2026-07-10
> session is re-ingested) in `tasks/retire_acquisition_review.md` §6 — all after the drives ingest is merged.

**`CHANGELOG.md`** (new top row):

> | 2026-10-01 | R. Tasseff | **The ACQ-ID retire tool is built and rehearsed (not used in production).**
> `tools/retire_acquisition.py` (Data Office only; dry run by default; backup first; refuses during an
> ingest; crash-resumable at every step; a re-run is a no-op) retires a byte-identical **duplicate** (bytes
> deleted only after a fresh SHA-256 match with the survivor; project links re-pointed at it), a
> **derivative** (hard-linked into its original's project folder, verified, then out of `/raw/`) or an
> **orphan** `/raw/` folder. The row moves verbatim to the new tombstone file
> `registries/retired_acquisitions.csv` (06 §2.9); removals from every other registry are byte-exact.
> **Never-reuse no longer rests on `.acq_id_seq.json` alone:** the allocator counts tombstoned ids, and the
> ingest dedup keeps blocking a retired source. `validate_registries` gains four tombstone ERRORs;
> `registry.resolve_acq_id()` and `find_acq.py` resolve a retired id to its replacement. 10_TOOLS §2.1's
> side-effect inventory gained the two rows it was missing (`pending_dicom_regen`, `pending_links`).
> Rehearsed on copies of real data: duplicate, derivative, orphan, crash-resume, idempotent re-run, a
> byte-exact diff of every registry file, no new validator error class. The `LSM9` re-save is
> information-identical (pixels, metadata, attachments) with a different container; v1 refuses it. |

**`tasks/BACKLOG.md`** — applied on this branch (2026-10-02): under "Dedup identity", the retire tool, the
approved twin lists and the v2 items (content-equivalent duplicate mode; re-identify not blocked by its
own tombstone); under the orphan item, the agreed order.
