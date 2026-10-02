# Review: the retire tool v2 — re-identify, and content-equivalent duplicates (branch `feat/retire-v2`)

**Date:** 2026-10-02 · **Stream E** of the historical-drives close-out (Step 5 item 7) · **Status:** 🔶 design
written first (this §1–2), then built, tested and rehearsed on scratch. **No production write.** Production
lists are dry-run only (read-only against `J:`). Ryan decides the open questions in §2.5 before any
production use.

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

**Order (each step resumable):** plan → backup → **commit A** under the lock (allocate the id; append the
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
