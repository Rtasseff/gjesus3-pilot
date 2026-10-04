# Review: the retire tool v2 — re-identify, and content-equivalent duplicates (branch `feat/retire-v2`)

**Date:** 2026-10-02 · **Stream E** of the historical-drives close-out (Step 5 item 7) · **Status:** 🔶
designed first (§1–2), then **built (§3), 30/30 test suites green, rehearsed on copies of the real files by
two routes with an independent byte-level verification (§4: 163 + 241 checks, 0 failures), and every
production list dry-run read-only against `J:` (§5).** **No production write.** Ryan decides the open
questions in §2.5 before any production use; §6 lists what worried me; §7 is the proposed wording for the
coordinator's files.

Builds on v1 (`tools/retire_acquisition.py`, merged `361387f`; first production use 2026-10-02: the 32
SHA-256 twins). Read `tasks/retire_acquisition_review.md` for v1's design; this file only covers what v2
adds and why.

---

## 1. What production actually needs (measured first, read-only)

### 1.1 The "15 mis-coded rows" are two different things

The production instrument audit (`D:\projects\gjesus3\staging\_analysis\catalog\production_instrument_audit.csv`,
refreshed 2026-10-02 07:32) lists 25 disagreeing rows: 23 `CELL` whose device serial is the AxioScan 7's
(`4661000718`) and 2 `LSM9` with the Cell Observer's fingerprint (no serial, stand key `Inverted` only).
The other 338 disagreements are `XMIC`, the external Axio Imager, by design. 10 of the 23 `CELL` rows are
the twins retired today (`ACQ-20260507-CELL-001…010`), leaving 15.

**Joining the 15 against the live registry by acquisition timestamp, and reading their sidecars
(`discovered` + `microscopy.document_info`), splits them in two:**

| Rows | What they are | Evidence |
|---|---|---|
| `ACQ-20240625-LSM9-001`, `-002` | **Two genuine Cell Observer acquisitions**, coded `LSM9` because they sat in the LSM 900 folder | No other live row shares their timestamp. 2448×2052 px, 3 channels, uncompressed, no ZEN subset/audit marker. |
| `ACQ-20260422-CELL-001…003` (`1022 MANON FIGURAS PB_Axioscan/1022_ID58T_PB_20x.czi` …, 53 MB each) | **ZEN subset crops ("figures") of live AxioScan scans** `ACQ-20260422-ZWSI-001…003` | Same acquisition timestamp **and** the same `creation_date` to 100 ns as the `ZWSI` scan; 3968×2992 px of a 55,740×55,697 px scan (same 0.17172 µm pixel); custom attribute `SubsetString` (ZEN "Create Image Subset"); the folder is named `FIGURAS`. |
| `ACQ-20260507-CELL-011…020` (`…/escenas separadas/…-Split Scenes-07.czi` …, 1.5–2.6 GB each) | **Single-scene splits of live 2-scene AxioScan scans** `ACQ-20260507-ZWSI-001…010` | Same acquisition timestamp as the `ZWSI` scan; 1 scene of the scan's 2, same 0.69103 µm pixel; `SubsetString` + `AuditTrail`; all ten written in ZEN at 14:33–14:35 that afternoon. |

So **only 2 rows are mis-coded acquisitions.** The other 13 are derivatives of acquisitions that are already
in `/raw/` under the right code. That matters for three reasons:

1. **Ryan's raw-vs-derivative principle (2026-10-01):** the acquisition goes in `/raw/`; derivatives and
   exports go to the project folder. Re-identifying the 13 would keep exports in `/raw/` under a corrected
   code.
2. **v1's no-chain rule.** A re-identified id is the `superseded_by` of its own tombstone, and v1 refuses
   to retire any id a tombstone names. Re-identify the 13 now, decide later that they are derivatives, and
   the tool refuses to retire them (it would need a rule change). **Classification has to come first.**
3. **They are same-timestamp retirements, which need Ryan's own go** (close-out plan, approval rule).

Recommendation (Q1 in §2.5): retire the 13 as v1 `derivative`s of their `ZWSI` scans, into the project
where the researcher has them (`claudia`), and re-identify only the 2 `LSM9` rows. Both lists are prepared
and dry-run (§5); the 15-row re-identify list is prepared too, as the handoff asked, in case Ryan prefers it.

### 1.2 The `LSM9` re-save pair, re-measured on production (read-only, czifile 2026.4.30)

`ACQ-20250915-LSM9-016` (`Prueba/24h_1.czi`, 2,731,104 B, no project link) vs `-001` (`24h_1.czi`,
3,676,480 B, linked as `irene-transfeccion\raw_linked\LSM9_24h_1.czi`):

| | `-001` | `-016` |
|---|---|---|
| Metadata XML | 467,077 chars, identical | identical |
| Subblocks (2: C0, C1, 816×684, uint16, uncompressed) | decoded pixels identical | identical |
| Attachments `EventList`, `TimeStamps`, `Thumbnail` | payloads identical (the Thumbnail's GUID differs) | identical |
| Container | metadata segment **moved to the end and double-allocated** (946,048 B for 473,015 used) + a **472,288 B `DELETED` segment** where it was — ZEN rewrote the metadata in place | compact: metadata at offset 1696 |
| File GUID | `f333a5b6-…` | `d3b7d6c5-…` |

Information-identical; only the container differs. v1 refuses it (not byte-identical), correctly.

---

## 2. Design

Both features are new **dispositions** of the same tool, `tools/retire_acquisition.py`, so they inherit v1's
run discipline unchanged: dry run by default, `--execute` to write; the window check (refuse while
`registries\.registry.lock` exists or `registry_raw.csv` changed in the last 15 minutes); a list is
all-or-nothing; backup first (fresh dated off-NAS folder, every copy SHA-256-verified); tombstone-first
write-ahead; byte-exact row removal; crash-resumable at every step; a re-run after success is a no-op; exit
codes 0/2/3/4/5; report + log in the backup folder.

### 2.1 Re-identify — `--reidentify-as <CODE>` (tombstone disposition `reidentified`)

**In place, not a re-ingest.** The bytes never move and are never copied: the new acquisition folder gets a
**hard link** to the same file, so the primary keeps its file id (inode) and **every project hard link stays
valid with no action at all**. Then the old folder (its own directory entry and three sidecars) is removed.

*Why not retire + re-ingest through `ingest_raw.py`:* a re-ingest copies the bytes (a second inode — every
project link would then have to be re-pointed), needs the original config's context to reproduce the row
(best-guess path parsing, operator, sample id), regenerates the sidecar with today's code (unrelated
changes), and is the only reason the dedup bypass would be needed. **In place, the dedup index is never
consulted, so "must not be blocked by its own tombstone" holds by construction**; and afterwards the source
stays blocked from re-ingest by both the tombstone's row and the new live row (same `original_name` and
date). If a future variant ever re-ingests (e.g. an MRI exam that needs fresh extraction), the bypass belongs
in `config._build_dedupe_index` as an explicit exclusion of exactly that one id; it is not built now.

**The new ACQ-ID** comes from the normal allocator (`acq_id.allocate_acq_id`, under the registry lock, so the
reservation file and the tombstones keep it unique): same date as the old id, the new instrument code. Same
date means the new folder is a sibling in the same `raw\<eco>\YYYY\YYYY-MM\` folder. The dry run shows a
preview id; the real one is allocated at execute and reported.

**What changes** (and nothing else):

| Where | Change |
|---|---|
| `registry_raw.csv` | A **new row** = the old row with `acq_id`, `instrument`, `primary_file_name`, `canonical_path` (and `instrument_model` only if `--instrument-model` is given) changed. The old row moves verbatim to the tombstone. **Kept as they were:** `registration_datetime`, `ingest_config`, `original_name`, `project_id`, `notes`, every other column (Q6). |
| `/raw/` | `…\ACQ-new\ACQ-new.czi` = a hard link to the old primary (same file id, verified with `os.path.samefile`); then `…\ACQ-old\` is removed. The primary's own attributes are never touched (they are shared by every link). |
| `metadata.json` | `acq_id` and `user_supplied.instrument` (every string holding the old id is rewritten to the new one). **Byte-exact elsewhere**: a targeted text substitution, verified by parsing the result and comparing it with the expected object. Line endings kept. |
| `checksums.json` | The file key `ACQ-old.czi` → `ACQ-new.czi`; hashes unchanged (same bytes). |
| `README.txt` | The id and the `Instrument` line rewritten; one line appended saying when and from which id it was re-identified, and why. Line endings kept. |
| `ingest_manifest.csv` | The old row moves to the tombstone; a new row for the new id is appended (as an ingest would). |
| `pending_*` queues | Any row for the old id moves to the tombstone and is carried over to the new id (id rewritten). None of today's candidates has one. |
| Project folders | **Nothing changes on disk** (Q5: link names keep their `CELL_`/`LSM9_` prefix, as the 10 twins' re-pointed links did). Each project `provenance.csv` with a link to the old id gets one appended event row: `input_refs` = the new id, so the link is found under its new id by every later tool. |
| `retired_acquisitions.csv` | The old id's tombstone: `disposition=reidentified`, `superseded_by` = the new id, `bytes_fate=moved`, `moved_to` = the new primary's path, `sha256` = the primary (hashed fresh), plus the evidence (§2.3). |

**Order (each step resumable):** plan → backup → a **probe** (a hard link made and removed in a dot-folder
beside the new folder: if the share refuses links inside `/raw/`, stop here with nothing committed; added
after rehearsal B) → **commit A** under the lock (allocate the id; append the
tombstone — the durable record of the new id; the old row stays live) → **build** the new folder (link +
the three rewritten sidecars, each written to a temp file and renamed, then read back) → **commit B** under
the lock (append the new row, its manifest row and any carried-over queue rows; then remove the old rows
byte-exact) → provenance events → remove the old folder → per-project `index.html` → self-check.
Between commit A and commit B the old row is still live and still points at its intact folder, and
`validate_registries` reports the half-done state as an ERROR (id both live and retired) until a re-run
finishes it; after commit B, an old folder that still exists is the existing "retired, but its /raw/ folder
still exists" ERROR. **The registry never points a live row at a folder that does not exist.**
A re-run reads the new id from the tombstone ("a tombstoned id follows its tombstone, not the arguments"),
and the exact field changes from the tombstone's evidence, so a resume never re-derives anything from
the command line.

**Preconditions (any failure refuses the whole list before a write):**

- the new code is different, well-formed, and already used by live rows of the same `data_ecosystem` (typo
  guard);
- **the file's own device fingerprint names the new code** (`tools/reference/microscopy_instruments.yaml`
  rules, applied to the `.czi`'s own metadata XML, reusing `tools/drive_staging/catalog.py`); unknown,
  external or conflicting → refused. v2 re-identifies single-file `.czi` acquisitions only (the only need
  today); anything else is refused with that message;
- the primary's fresh SHA-256 matches its `checksums.json` (the truncation lesson: never re-register bytes
  that are not the bytes that were checked in);
- the `/raw/` folder holds only the primary and the three sidecars;
- every project link found through provenance is the same file as the primary, or is reported (`absent` /
  `foreign`) and left alone, as in v1;
- v1's rules: not cited by a curated dataset; not the `superseded_by` of a tombstone; nothing else in the
  run targets it.

### 2.2 Content-equivalent duplicate — `--equivalent-of <ACQ-ID>` (disposition `equivalent`)

For `.czi` only. A retiree whose bytes differ from a live survivor's, but whose **information is
identical**:

- the metadata XML is identical (exact string equality);
- the subblocks are identical as a multiset — for each: pixel type, pyramid type, mosaic index, dimensions,
  start, shape and stored shape; the **decoded** pixels (SHA-256 of the array); the subblock's own
  metadata XML and attachments. Compression is not compared (a lossless re-encode is the same
  information), but it is recorded;
- the attachments are identical as a multiset of (name, content type, payload SHA-256). Attachment GUIDs
  are recorded, not compared.

Then it is retired exactly like a v1 duplicate: the tombstone first, rows removed byte-exact, any project
link to the retiree **re-pointed at the survivor** under the same name (or removed if the survivor is already
linked there), and the retiree's `/raw/` folder deleted after a re-check. **Refused** when any of the above
differs (the first differences are listed), when the two are byte-identical (use `--duplicate-of`), when
either primary is not a single `.czi`, when the retiree's folder holds anything else, or when the
survivor's bytes do not match its own `checksums.json` (as for `duplicate`). The tombstone's `sha256` is the
retiree's own file hash; a distinct disposition keeps v1's meaning of `duplicate` (the survivor holds these
exact bytes) intact.

### 2.3 Evidence in the tombstone

The tombstone's columns are not changed (the production file exists since today with the v1 header, and
the validator requires it exactly). The tool appends its evidence to `reason`, after a fixed separator:
`<the operator's reason> || evidence: {compact JSON}`. Machine-readable (split on the separator), durable,
next to the row it explains. For `equivalent`: the method (`czi-content/1`), the metadata XML hash, the
subblock and attachment counts and digests, each side's size, SHA-256, file GUID, segment inventory and
`DELETED` bytes. For `reidentified`: the method (`reidentify/1`), the device fingerprint (rule, serials,
stand keys, stand name) and the exact field changes `{field: [old, new]}` (which the resume uses).
A full copy of each evidence object also goes to the run's report. (Q4: a dedicated `evidence` column
instead.)

### 2.4 Other changes

- `ingest/retired.py`: `DISPOSITIONS` += `reidentified`, `equivalent`.
- `validate_registries.py`: ERROR on an unknown `disposition` or `bytes_fate`; for `reidentified`, ERROR
  if the live `superseded_by` row does not share the retired row's `original_name` and acquisition
  timestamp or still has the same instrument (a wrong `superseded_by`).
- `find_acq.py`: says "re-identified as …" / "content-equivalent duplicate of …".
- `tools/ingest/czi_compare.py` (new): the content signature and comparison, testable on its own.
- Window check: commit B rewrites `registry_raw.csv` after the build, so the tool refreshes the tombstone
  file's mtime at the end of commit B; the "our own last write" rule then still recognises it.

### 2.5 Open questions for Ryan (each built against the recommended default; easy to change)

| # | Question | Options | Recommendation (built as default) |
|---|---|---|---|
| **Q1** | **The 13 `CELL` rows are ZEN derivatives (3 subset crops, 10 scene splits) of live `ZWSI` scans (§1.1). Re-identify them, or retire them as derivatives?** | (a) retire as `derivative` of each `ZWSI` scan (v1 mode, nothing deleted: the file moves to the project folder); (b) re-identify as `ZWSI` and keep them in `/raw/`; (c) leave them until stream D's same-timestamp clean-up | **(a)**. They are exports by their own metadata. A pixel check is not needed to move them (moving loses nothing). (b) is irreversible in practice: the no-chain rule then blocks retiring them later. |
| Q1b | If (a): into which project, and where? | `claudia` (where they are registered and Claudia has them linked) vs `AE-biomaGUNE-1022` (the scans' project; 06 §2.9's wording "the original's project folder"); subfolder `working\<original folder path>\` (mirrors your 2026-10-02 placement rule for drives material) vs v1's default `outputs\derived` | **`claudia`, `working\<original folder path>\`**, e.g. `claudia\working\1022 MANON FIGURAS PB_Axioscan\1022_ID58T_PB_20x.czi`. Moving them to `1022` would take them out of Claudia's folder. The tool warns that `claudia` is not the scans' project; that warning is expected. |
| Q2 | Re-identify mechanism | (a) in place: hard link + rewritten sidecars, no copy (§2.1); (b) retire + re-ingest with a dedup bypass for exactly the replaced id | **(a)**. Keeps every project link valid by identity, copies nothing, changes only the identity fields; the bypass is unnecessary. |
| Q3 | Disposition names | `reidentified` + `equivalent` (new values) vs `duplicate` + evidence for the re-save | **New values.** `duplicate` keeps meaning "byte-identical". Added to 06 §2.9 and the validator. |
| Q4 | Where the evidence goes | in `reason` after ` \|\| evidence: ` (no schema change) vs a new `evidence` column (cleaner; needs a one-time, byte-exact header migration of the live tombstone file) | **In `reason`.** One function formats it, so moving it to a column later is small. |
| Q5 | Project link names after a re-identify (`LSM9_CS_fijadas_cell obs_1.czi`) | keep vs rename to the new code (`CELL_…`) | **Keep**, consistent with the 10 twins' links; project folders are researcher-owned (05_PROJECTS §3a). Not built: a rename would be a small opt-in later. |
| Q6 | Which row fields change | identity only (`acq_id`, `instrument`, `primary_file_name`, `canonical_path`) vs also `registration_datetime` = now, a note appended to `notes` | **Identity only.** The bytes were registered on their original date by their original config; the tombstone records when and why the id changed, and `find_acq.py` resolves the old id. |
| Q7 | `bytes_fate` for a re-identify | `moved` (+ `moved_to` = the new primary) vs a new value `renamed` | **`moved`** (no new vocabulary). |
| Q8 | The no-chain rule | keep vs allow a chain through a `reidentified` tombstone (the validator would then follow chains) | **Keep.** Re-identify only what stays in `/raw/`; decide derivatives and duplicates first. |
| Q9 | The `LSM9` re-save | retire `-016` as `equivalent` of `-001` (keep `-001`: older, linked, not in a test folder) | As you decided on 2026-10-01; the list is prepared and dry-run (§5). |

---

## 3. What was built, and the tests

| File | What |
|---|---|
| `tools/retire_acquisition.py` | Two dispositions: `--equivalent-of` and `--reidentify-as <CODE> [--instrument-model …]` (list columns `new_instrument`, `instrument_model`). Re-identify = commit A → build → commit B (§2.1). One name of a shared file is removed without clearing its attributes on the other names (`remove_link_name`). New files are written through a temp file + rename and read back. The report gains an `evidence` column. **Every v1 path is unchanged:** v1's 14 test groups pass without an edit. |
| `tools/ingest/czi_compare.py` (new) | The content signature of a `.czi`, the comparison and the evidence object (§2.2). |
| `tools/ingest/reidentify.py` (new) | Pure functions: the field changes, the new row, and the byte-level sidecar rewrites, each verified by re-parsing; a carried-over bookkeeping record. |
| `tools/ingest/retired.py` | `DISPOSITIONS` += `equivalent`, `reidentified`; `with_evidence` / `split_evidence` (the ` \|\| evidence: ` separator). |
| `tools/ingest/csv_safe.py` | `append_record` (a raw record appended byte-exactly, with the file's own terminator). |
| `tools/validate_registries.py` | ERRORs: an unknown `disposition` or `bytes_fate`; a `reidentified` id whose `superseded_by` is not the same acquisition under another code. |
| `tools/find_acq.py` | "re-identified as …" / "content-equivalent duplicate of …", and the human part of the reason only. |
| `tools/test_retire_acquisition_v2.py` (new) | 13 test groups (below). |
| Docs | 06 §2.6 + §2.9 (intro, column descriptions, rules) · 10 §3.9 · 11 §5.7 · 00 Last Updated · `GLOSSARY.md` · `tools/INDEX.md`. All v2 text is marked 🔶; no column, field or v1 rule changed. |
| Lists | `tasks/retire_lists/2026-10_reidentify_15.csv` (as asked), `…_reidentify_2_lsm9.csv` + `…_derivatives_13_cell.csv` (the recommended split, Q1), `…_content_equiv_lsm9.csv`. |

**Two traps found while building, both handled:**

- **Production READMEs are not valid UTF-8.** `ACQ-20240625-LSM9-001\README.txt` has a UTF-8 em dash in its
  header and a cp1252 `0x97` dash in its notes. A decode/re-encode rewrite would fail or change bytes, so
  every sidecar rewrite works on bytes (tested with that exact mix).
- **Attributes are per file, shared by every hard link.** v1's delete clears a read-only attribute when a
  delete needs it; for a re-identify that would un-protect the file under its new id and in every project.
  The old name is removed by `remove_link_name`, which restores the attribute on the surviving name (tested).

**Tests.** `python tools/test_retire_acquisition_v2.py` — **ALL PASSED**. Synthetic `.czi` files built by a
small CZI writer in the test (czifile reads and decodes them), a fake NAS with real hard links:

1. `czi_compare`: a ZEN-style re-save (a `DELETED` segment, metadata moved to the end, segments reordered, a
   new Thumbnail GUID) is equivalent; one changed pixel, a metadata change, an attachment change and a
   missing subblock are each caught and named.
2. `reidentify` + `csv_safe.append_record`: metadata.json changes on exactly 2 lines and keeps CRLF; the
   README keeps its cp1252 byte; refusals (wrong id, an unexpected second `instrument` value, two
   Instrument lines, another date); the id never matches a longer number.
3. Dry run: fingerprint, preview id, link kept; **nothing written**.
4. Refusals, none of which writes: a real LSM 900 file (`fingerprint says LSM9`), the same code, an unknown
   code, a curated-dataset citation, a primary that no longer matches its `checksums.json`, an extra file in
   the folder, a `target_acq_id` on a re-identify.
5. Execute: the end state; every other `registry_raw.csv` record byte-identical and in order; the new row =
   the old one with only the 4 identity fields changed; the tombstone holds the old row verbatim; the
   manifest row carried over; **the new primary is the project link's file (file id)**; 2/1/4+1 lines
   changed in the three sidecars; the link keeps its name; the backup.
6. Idempotent re-run (no write, no backup); the window check sees the last write as the tool's own;
   `resolve_acq_id` and `find_acq` resolve the old id; **the allocator reserved the new id and never reuses
   the old one; the dedup index still blocks the source.**
7. A mixed list (re-identify with two project links and a pending row + an equivalent with a link) **run
   with the ingest's dedup index replaced by a function that raises** — it completes: a re-identify
   cannot be blocked by its own tombstone, and the dedup index is identical before and after. The pending
   row is carried over with its sidecar path rewritten; the equivalent's link is re-pointed at the survivor.
8. Equivalent refusals: a changed pixel, changed metadata, byte-identical, a different image.
9. Validator: an unknown disposition, and a re-identify pointing at an unrelated live id, are ERRORs.
10. **A crash after every step** of a re-identify (`tombstone`, `built`, `commit`, `links`, `bytes`,
    `provenance`): exit 4 → re-run 0 → re-run no-op, the same end state, one event per link. Meanwhile the
    validator shows the half-done state (after commit A: the id is both live and retired, and its new id is
    not live yet; after commit B: the old folder still exists).
11. A run stopped **inside** the old folder's delete (the primary's old name, or a sidecar, already gone):
    the re-run finishes it.
12. A crash after every step of an `equivalent`: the same end state, the link is the survivor, one event.
13. Removing one name of a read-only file leaves the other name read-only.

**The whole suite: 30/30 test files pass** (the 29 on `main` + the new one; `tools/diagnostics/test_oslink.py`
is a diagnostic that needs arguments, as before).

---

## 4. Rehearsal on real data (scratch only, `D:\projects\gjesus3\scratch_retire-v2\`)

**The pristine store** (`pristine\`), copied read-only from `J:` at 12:23–12:55: every registry CSV and
`.acq_id_seq.json` (after today's 32 twin retirements: 32 tombstones); the `/raw/` folders of the 15, the
`LSM9` pair and the 13 `ZWSI` scans (172 files, 25.70 GB; **every primary verified against its production
`checksums.json`**, 0 errors); the four projects' `provenance.csv` / `_project.yaml`; the curated-dataset
text files. Each run builds its own NAS from it (`runA\nas`, `runB\nas`): small files copied, the `.czi`
primaries hard-linked from the pristine store (the tool never changes a primary's content), and the 39
project links recreated as hard links (each confirmed same-file in production, stat only). Nothing points
at `J:`. Log: `rehearsal_log.txt`; the driver, setup and verifier scripts are in the session scratchpad.

**The independent verifier** uses the standard library only (not the tool's code) and compares the run with
the pristine store: every registry file record by record (everything not retired byte-identical and in
order; only the new ids added; no BOM; no bare-LF line ending introduced; `.acq_id_seq.json` changed only
for the re-identify prefixes); per item, the tombstone, the row moved verbatim, the folders, **file identity
(`os.path.samefile`) between the new primary or the moved file and the pristine file**, the three rewritten
sidecars against the old ones, the project links and their provenance events; and the validator's error
classes before and after.

### Run B — the recommended route (Q1 a): re-identify 2, derivative 13, equivalent 1

| Step | Result |
|---|---|
| Dry runs | 0 / 0 / 0 (the 13 derivatives hash 19.3 GB: 560 s) |
| `reidentify_2` with a crash injected after `built` | exit 4; the validator then shows exactly the 3 designed ERRORs (`LSM9-001` both live and retired; its new id `CELL-008` not live yet; the old folder still there) on top of the scratch baseline |
| re-run | 0: finished from the tombstone (`CELL-008`, then `CELL-009`); re-run again: no-op |
| `derivatives_13` | 0 (1,284 s: v1 hashes each file at plan and again at placement); re-run: no-op |
| `content_equiv` | 0; re-run: no-op |
| **Verifier** | **163 checks passed, 0 failed.** Validator: no new error class; 35,479 → 35,479 errors (the 10,314 known placeholders + 25,165 "folder not found", expected on a scratch copy that holds 30 folders) |

End state (scratch): `raw\…\2024-06\` holds `ACQ-20240625-CELL-008\` and `-009\` and no `LSM9` folder; each README ends with the
re-identify line; the tombstones carry the evidence (e.g. `{"changes": {"acq_id": ["…LSM9-001", "…CELL-008"],
"canonical_path": …, "instrument": ["LSM9", "CELL"], "primary_file_name": …}, "fingerprint": {"instrument":
"CELL", "rule": "no-serial+keys=Inverted+stand", …}, "method": "reidentify/1", "sha256": "f8e55cd8…"}`);
`claudia\working\` holds the 13 files under their original folders (`1022 MANON FIGURAS PB_Axioscan\…`,
`1022\Hif1A + VEGFA\escenas separadas\HIF1A\…`), each the same file as before; `claudia\provenance.csv`
gained 26 events (13 `moved-to`, 13 `link-removed`).

### Run A — the handoff's literal route (Q1 b): re-identify all 15, equivalent 1 (with the probe)

| Step | Result |
|---|---|
| Dry runs | 0 / 0 (the 15 hash 19.5 GB: 623 s) |
| `reidentify_15` | 0 (908 s: 11 min of hashing at plan, then 15 items with the probe before each commit A); re-run: no-op |
| `content_equiv` | 0; re-run: no-op |
| **Verifier** | **241 checks passed, 0 failed.** Validator: no new error class; 35,479 → 35,479 |

The new ids are exactly the dry run's previews: `ACQ-20240625-CELL-008/-009`, `ACQ-20260422-ZWSI-004…006`,
`ACQ-20260507-ZWSI-011…020`; 15 `reidentified-as` events (13 in `claudia`, 2 in `itziar-lipofectamine-mcherry`);
no probe folder left anywhere under `raw\`.

---

## 5. Production lists and dry runs (read-only against `J:\gjesus3-data`, 2026-10-02 13:08)

Log: `D:\projects\gjesus3\staging\_analysis\retire-v2\prod_dryruns_20261002-130807.log`. Every run: exit 0,
**nothing written**, no window warning.

| List | Mode | Result |
|---|---|---|
| `2026-10_reidentify_2_lsm9.csv` | full (hashes) | 2 items: fingerprint **CELL** (`no-serial+keys=Inverted+stand`) on both; primary SHA-256 matches `checksums.json`; previews **`ACQ-20240625-CELL-008`, `-009`**; each keeps its one link in `itziar-lipofectamine-mcherry`; adds/removes 1 `registry_raw` + 1 `ingest_manifest` row each; 9 s. |
| `2026-10_content_equiv_lsm9.csv` | full | `ACQ-20250915-LSM9-016` content-equivalent to `-001`: metadata XML (467,077 chars), 2 subblocks decoded and 3 attachments identical; container 2,731,104 vs 3,676,480 bytes, `DELETED` 0 vs 472,288 bytes. No project link (as measured on 2026-10-01). 3 s. |
| `2026-10_derivatives_13_cell.csv` (recommended for the 13, Q1) | `--quick` (sizes only; the execute hashes) | 13 items, each into `claudia\working\<original folder>\<original name>`; each removes its `claudia\raw_linked\CELL_…` entry; the expected WARN on each: `PROJ-0039` is not the scans' project (`PROJ-0019`). 6 s. |
| `2026-10_reidentify_15.csv` (as the handoff asked) | full | 15 items, all preconditions pass: the 2 `LSM9` → `CELL` as above; the 13 `CELL` → fingerprint **ZWSI** (`serial:4661000718`), checksums match, previews `ACQ-20260422-ZWSI-004…006` and `ACQ-20260507-ZWSI-011…020`; 15 links kept. 217 s (19.5 GB over SMB, ~90 MB/s). |

**Commands for the coordinator** (each a separate approved operation; **none has Ryan's go yet**):

```
:: the 2 LSM9 rows -> CELL (re-identify; v2)
python tools\retire_acquisition.py --nas-root J:\gjesus3-data --list tasks\retire_lists\2026-10_reidentify_2_lsm9.csv
python tools\retire_acquisition.py --nas-root J:\gjesus3-data --list tasks\retire_lists\2026-10_reidentify_2_lsm9.csv --execute

:: the LSM9 re-save (equivalent; v2)
python tools\retire_acquisition.py --nas-root J:\gjesus3-data --list tasks\retire_lists\2026-10_content_equiv_lsm9.csv
python tools\retire_acquisition.py --nas-root J:\gjesus3-data --list tasks\retire_lists\2026-10_content_equiv_lsm9.csv --execute

:: Q1 (a), recommended: the 13 CELL derivatives into claudia\working\ (v1 mode; a same-timestamp retirement, so Ryan's own go)
python tools\retire_acquisition.py --nas-root J:\gjesus3-data --list tasks\retire_lists\2026-10_derivatives_13_cell.csv
python tools\retire_acquisition.py --nas-root J:\gjesus3-data --list tasks\retire_lists\2026-10_derivatives_13_cell.csv --execute
::   or Q1 (b): re-identify all 15 instead (then never as derivatives later: no chains)
python tools\retire_acquisition.py --nas-root J:\gjesus3-data --list tasks\retire_lists\2026-10_reidentify_15.csv --execute
```

The `derivative` execute hashes each file twice (at plan, then the placed link), about 39 GB of SMB reads
for the 13; the re-identify execute hashes once (19.5 GB for the 15, 0.18 GB for the 2).

---

## 6. What worried me, and what stays open

- **Q1 is the real decision.** Re-identifying the 13 `CELL` rows would keep ZEN exports in `/raw/` as
  acquisitions, and the no-chain rule would then stop them from ever being retired as derivatives. The
  derivative route needs Ryan's own go (a same-timestamp retirement) and visibly changes Claudia's folder:
  13 `raw_linked\CELL_…` entries disappear and the same files appear under `working\…` (v1's derivative
  behaviour). Worth a line to Claudia when it runs.
- **A re-identify is not undone by the tool.** The old id is never reused, and the new id is the
  `superseded_by` of the old one's tombstone, so the tool refuses to touch it again. The guards are the
  device-fingerprint check and the dry run. A wrong one would be a manual repair from the run's backup
  (registries, the old sidecars) plus the new folder's hard link.
- **The probe** (added after rehearsal B): creating a hard link *inside* `/raw/` is the one operation an
  ingest never does. The tool now makes and removes one in a dot-folder before commit A, so a share that
  refuses it stops the run with nothing committed. Rehearsal A ran with it.
- **While a re-identify runs, the validator shows 3 ERRORs for that id** (both live and retired; the new
  id not live yet; the old folder still there) for the seconds between commit A and the old folder's
  removal. A stopped run is finished by re-running it (rehearsed: crash after `built`).
- **Stale status lines I did not touch** (production facts are the coordinator's): 06 §2.9 "🕗 Not deployed:
  the file is created by the first approved production retirement", 10 §3.9 "🕗 … no production use yet" and
  11 §5.7 "No production retirement has run" are out of date since today's 32 twin retirements.
- **The fingerprint rules live in `tools/drive_staging/catalog.py`**, an analysis module, now imported by a
  production tool (no import-time side effects; `test_drive_catalog.py` pins the rules). A later refactor of
  the catalog has to keep `czi_read_xml`, `parse_czi_xml`, `fingerprint` and `load_instruments`, or move them
  to `tools/ingest/` (proposed for the BACKLOG, LOW).
- **Kept as they were, by design (Q6):** the README's `Acquisition Date : unknown` (a best-guess-ingest
  quirk) and the `notes` text "legacy LSM9 / legacy CELL" on the re-identified rows. The README's new last
  line, the tombstone and `find_acq.py` carry the history.
- **D: scratch:** the rehearsal's `.czi` copies are deleted after the runs (25.7 GB); the logs and the
  small files stay under `D:\projects\gjesus3\scratch_retire-v2\`. The production dry-run log is in
  `D:\projects\gjesus3\staging\_analysis\retire-v2\`.

---

## 7. Proposed wording for the coordinator (not applied here)

**`tasks/STATUS.md`** (a sub-bullet under the drives bullet, after the retire-tool line):

> **Retire tool v2: built, tested and rehearsed on scratch (branch `feat/retire-v2`, 2026-10-02); not used in
> production.** Two new dispositions: `equivalent` (a `.czi` re-save whose metadata, decoded pixels and
> attachments are identical to a live survivor) and `reidentified` (a mis-coded acquisition re-registered in
> place under its correct instrument code: a new ACQ-ID, the same file hard-linked into the new folder, project
> links unchanged). **Finding: only 2 of the 15 rows left to re-code are mis-coded acquisitions**
> (`ACQ-20240625-LSM9-001/-002`, Cell Observer files). The 13 `CELL` rows are ZEN subset crops and scene
> splits of live AxioScan scans, so the recommendation is to retire them as derivatives into
> `claudia\working\` (Ryan's call). Questions, dry runs and commands: `tasks/retire_v2_review.md` §2.5 and §5.

**`CHANGELOG.md`** (new top row):

> | 2026-10-02 | R. Tasseff | **The retire tool v2 is built and rehearsed (not used in production).**
> `tools/retire_acquisition.py` gains two dispositions. **`equivalent`:** a `.czi` re-save is retired into its
> survivor when the metadata XML, every subblock's decoded pixels and every attachment's payload are identical
> although the bytes differ (`tools/ingest/czi_compare.py`); first candidate `ACQ-20250915-LSM9-016`, a compact
> re-save of `-001`. **`reidentified`:** a mis-coded acquisition is re-registered in place: a new ACQ-ID from
> the normal allocator, a hard link to the same file in the new `/raw/` folder (nothing copied; every project
> link stays valid), the sidecars rewritten on bytes changing only the id and the instrument, the old id
> tombstoned with `superseded_by` = the new one. The file's own device fingerprint must name the new code. It
> is not a re-ingest, so the ingest's dedup index is never consulted and the source stays blocked. The tool's
> evidence is appended to the tombstone's `reason` (no schema change). `validate_registries` gains two ERRORs.
> **Measured first: of the 15 rows left to re-code, only the 2 `LSM9` rows are mis-coded acquisitions; the 13
> `CELL` rows are ZEN subset crops (3) and scene splits (10) of live `ZWSI` scans.** Rehearsed on copies of
> the real files (two routes, a crash injected and resumed, an independent byte-level verification: 0
> failures); every list dry-run against production. 30/30 test suites pass. |

**`tasks/BACKLOG.md`** ("Dedup identity" section): mark the two v2 items **built, not yet used**
(`feat/retire-v2`, `tasks/retire_v2_review.md`); record that the 15 split into 2 re-identifies and 13
derivatives (Q1); add a 🔽 LOW item: *move the microscopy device fingerprint
(`czi_read_xml` / `parse_czi_xml` / `fingerprint` / `load_instruments`) out of `tools/drive_staging/catalog.py`
into `tools/ingest/`, now that a production tool uses it.*

**`tasks/historical_drives_closeout_plan.md`** (Step 5 item 7): "v2 re-identify for the remaining 15
mis-coded rows" and "v2 content-equivalent duplicates" → **built and rehearsed (stream E); production use
waits for Ryan's answers to `tasks/retire_v2_review.md` §2.5 Q1–Q9, then three operations: the 2 `LSM9`
re-identifies, the `LSM9` re-save, and the 13 `CELL` rows (as derivatives, or re-identified).**
