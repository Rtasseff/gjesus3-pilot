# NI live-sync — operator hardening plan (link fallback, sync corrections, per-session metadata)

**Branch:** `feat/ni-live-hardening` (off `main`, which already carries all NI live-sync code).
**ALL of §1 + §2 + §3 land on THIS one branch** (user directive 2026-06-25 — not split).
**Status:** §1 DONE. §2 + §3.5 (per-recon, **Tier B**) DONE + verified. §3.1 (no-YAML operator
CLI) DONE + verified. Next: §3.2 (pre-run corrections CSV) + §3.3 (per-session tracer
metadata), GUI (§3.6) last.

**SCOPE NOTE (creep check, user 2026-06-25):** chose **Tier B** — per-recon acquisitions with
NO registry mutation. Empty recons (reconstruction pending) are **skipped + logged**, picked up
on a later sync; they are NOT registered as placeholders. The "register-before-DICOMs + in-place
fill" option (**Tier C**) is **deferred** — its `pending_ni_recon.csv` scaffold was removed
(revivable from commit `3e0896d`). The functional change is NI-only and opt-in (the
`ingest.per_recon_acquisitions` flag lives in `molecubes_ni_live.yaml` alone); microscopy/MRI/
archive-NI are untouched.
**Origin:** Irene live-sync test run, 2026-06-25. Outputs reviewed:
`S:\gnuclear\2026\Jesus\Ryan\p0_p2_outputs.txt` (Steps 0–2) and
`S:\gnuclear\2026\Jesus\Ryan\ni-live-test\p_5_output.txt` (Step 5, full ingest into `J:\gjesus3-sandbox`).

---

## 0. Test review — what the run actually showed

**Step 5 batch summary: 127 cases, 122 success, 5 failed.** The pipeline works end-to-end
into the sandbox — discovery, multi-animal subject parse, subjects-table upsert, metadata
sidecars, registry append, project resolution all fired correctly on the 122.

Two distinct problems surfaced. They are **not** the same issue:

### 0.1 Hard links failed on ALL 127 (the headline pain)
Every project link failed with:
```
WARN: Could not create hard link: [Errno 45] Operation not supported:
  /Volumes/gjesus3/gjesus3-sandbox/raw/.../ACQ-...data/recon0.dcm ->
  /Volumes/gjesus3/gjesus3-sandbox/projects/proj-.../raw_linked/.../recon0.dcm
```
Confirmed by Step 0's pre-flight: `os.link → OSError ENOTSUP` on the Mac's SMB mount
(`/Volumes/gjesus3/...`). **macOS over SMB/CIFS does not support hard links.** This is a
filesystem-capability fact, not a bug in our code.

Current behaviour (`tools/ingest_raw.py:1453` `except OSError: log(..., "WARN")`): the
acquisition still **fully registers** — `/raw/` copy, checksums, metadata, subjects,
registry row all written — and only the `projects/<proj>/raw_linked/` entry is skipped.
The data is safe and findable; it just isn't linked into the project folder. **But there is
currently NO record of which acqs are missing their link** — the WARN scrolls past and is
lost. That gap is what §1 fixes.

### 0.2 Five cases failed: "NI slim copy plan is empty"
```
ERROR: NI slim copy plan is empty for .../irene/1207/250407/0522_141/20250408173151_CT/.
        Expected at least one per-frame or direct .dcm under recon_<idx>/.
```
All 5 are in the **`1207` series, dates 250407 / 250408** (2025-era), subjects `0522_141`
/ `0522_142`:
- Case 110 `1207/250407/0522_141/20250408173151_CT`
- Case 112 `1207/250407/0522_142/20250408170406_PET`
- Case 113 `1207/250408/0522_141/20250408171004_PET`
- Case 114 `1207/250408/0522_141/20250408173151_CT`
- Case 115 `1207/250408/0522_142/20250408170406_PET`

These all **errored before commit**, so they did not register — a re-run after a fix picks
them up (ingest is idempotent).

**Root cause — CONFIRMED (user diagnosis + code, 2026-06-25).** The error fires at
`ingest_raw.py:296` (`plan is empty`), **not** `:278` (`No recon_<idx>/ subfolders`). So the
`recon_<idx>/` folders **exist** — there are just **no DICOMs inside them yet**. This is the
NI reality the user described: **reconstruction is incremental and lags acquisition.** A scan
runs → the session folder and `recon_<idx>/` dirs are created → the user often copies the
initial files over **before reconstruction finishes** (NI recon can take far longer than MRI)
→ they come back later and the DICOMs appear → and **sometimes they run additional
reconstructions later still**, which show up as yet more DICOMs on an even later sync.

This means problem 0.2 and the "new-reconstruction pickup" work (old §3.4) are **the same
issue** — handled by one **incremental-reconstruction model** (now §3 below). It is NOT a
parser bug and NOT a failure: an empty-recon anchor should register a placeholder, not abort.

### 0.3 Minor friction noted in Steps 0–2 (not blocking)
- `ni_live_discover.py --root .../data/irene irene` failed; `--root .../data irene` worked —
  the `--root` must be the **parent** of the researcher folder, not the folder itself
  (the tool appends `who`). Worth a one-line usage fix or clearer help text.
- `--nas-root ~/ni-test-nas` correctly rejected (no `registries/`); the real
  `/Volumes/gjesus3/gjesus3-sandbox/` worked. Validation behaved as designed.

---

## 1. MINIMUM FIX (this branch, do first) — pending-links worklist + stand-in link

**The user's "at a minimum":** when a hard link can't be made, *record it* so we know where to
go back and create the real link later — exactly like `pending_dicom_regen.csv` (no-DICOM MRI)
and `pending_subject_metadata.csv` (no-DB subjects). Optionally drop a visible stand-in link in
the project folder so it isn't empty.

### 1.1 New worklist module `tools/ingest/pending_links.py`
Mirror `tools/ingest/pending_dicom.py` exactly (BOM-tolerant, header-checked, atomic
temp+replace, idempotent on key, status preserved across re-runs). Writes
`registries/pending_links.csv`. Proposed fields — the recovery payload needed to recreate the
real hard link later from a hard-link-capable machine (Windows is proven):

| field | meaning |
|---|---|
| `acq_id` | the registered acquisition |
| `project_id` | resolved PROJ-XXXX the link belongs in |
| `link_name` | the resolved `link_filename:` (what `raw_linked/<name>` is called) |
| `raw_primary_canonical` | `/raw/...` path to the acq primary (the link source) |
| `primary_kind` | `file` \| `folder` (folder ⇒ folder-of-per-file-links) |
| `reason` | the OSError text + errno (e.g. `ENOTSUP [Errno 45]`) |
| `host_os` | platform that hit the failure (so we know it was the Mac) |
| `queued_datetime` | |
| `status` | `pending` \| (data office sets `linked`) |

### 1.2 Wire into `ingest_raw.py` at the link failure site (`:1453-1456`)
In the `except OSError` / `except Exception` blocks, after the existing WARN, call
`pending_links.append_pending_link(...)` (non-blocking try/except, same pattern as the
no-DICOM queue at `:1001`). The acq is already registered at this point, so this only adds the
worklist row. Idempotent on `acq_id` so re-runs refresh, never duplicate.

### 1.3 Stand-in link in the project folder (DESIGN CHOICE — see Open Decisions)
The user said "create these shortcut links." On macOS-over-SMB a Windows `.lnk` is meaningless
and a byte-copy of multi-GB sessions would balloon NAS usage (one Step-5 CT was 3.5 GB).
**Recommended:** write a tiny **pointer file** `raw_linked/<link_name>.PENDING-LINK.txt`
containing the canonical `/raw/...` path + "real hard link to be created later (see
pending_links.csv)". Zero storage, cross-platform readable, and clearly marked so it's never
mistaken for the real data. The pending-list is the durable mechanism; the pointer is cosmetic.
(Alternatives weighed in Open Decisions.)

### 1.4 A recovery tool `tools/relink_pending.py` (small)
Reads `registries/pending_links.csv`, and for each `pending` row calls
`linker.create_hardlink(project_folder_abs, link_name, raw_primary_abs)` — run from a
hard-link-capable machine (the Windows workstation, **proven** by the historical
`tools/relink_mri_regen.py` pass). On success, removes the `.PENDING-LINK.txt` stand-in and
flips `status → linked`. This is the NI analogue of the existing MRI relink pass. Until the
researcher grab-tool / server-side host exists (§4 backlogs), this is how the links get made.

### 1.5 Docs + tests
- `tools/test_pending_links.py` mirroring `tools/test_pending_dicom.py` (no NAS, no network).
- `mfb-rdm-docs/06_REGISTRIES.md` (§2.7 registry-integrity family) — document
  `pending_links.csv` alongside the other two pending worklists.
- `mfb-rdm-docs/00_INDEX.md` version history; `CHANGELOG.md`.
- `equipment/nuclear-imaging/...workflow_notes.md` — note that links defer on the Mac.

---

## 2. The 5 "slim copy plan empty" cases = the incremental-recon model (see §3.5)

Root cause confirmed above: recon dirs exist, DICOMs not generated yet. The fix is **not** a
separate investigation — it is the placeholder→fill behaviour in §3.5. An empty-recon anchor
must register a **placeholder acquisition** (metadata, empty `.data/`, queued), not abort.
(Optional read-only `ls -R` on the box can confirm the 5 are empty-recon vs. anything exotic,
but the placeholder behaviour is correct either way and unblocks them.)

---

## 3. Operator-flow redesign — no YAML, pre-run readout, corrections that don't break sync,
per-session metadata, new-recon pickup. (The larger build — "get the script running first,"
then the Mac GUI **last**.)

> The user's framing: the original tool needed no YAML; the live sync currently requires a
> hand-edited per-batch YAML. Operators also need (a) a readout of what WILL happen with a
> chance to fix REMI data-entry mistakes (session id / project code / mouse id they can't fix
> in REMI), (b) per-session extra metadata (tracer) captured to the JSON, (c) correct handling
> of new reconstructions added to already-synced sessions — all **without confusing the sync**.

### 3.1 Phase A — kill the YAML: a `--live` mode on `tools/operator/ni_ingest.py` — DONE
Implemented as a **`--live` mode added to the existing `ni_ingest.py`** (not a new tool — the
file was already scaffolded for live mode: its docstring + `_explain_live_mode` pointed here).
`--live` bypasses the archive `.tgz`/scope path and builds the config **in memory** from the
locked `molecubes_ni_live.yaml` (new templates key `NI_LIVE`): the operator points at their
researcher data folder, `--operator`/`--researcher` (defaults to the folder name) are the only
inputs, and it runs the same validated `runner.run → ingest_raw.run_batch`. No YAML. Archive
mode is byte-for-byte unchanged. **Verified:** `--live --dry-run` and a real `--live --go`
against the synthetic tree → CT-001(/recon_0) + CT-002(/recon_1), per-recon hard links,
researcher=irene, Failed 0; archive mode still parses. Operator command:
`ni-ingest <my folder> --live --operator <name>`.

### 3.2 Phase B — pre-run readout the operator can correct (CSV-intermediary, recommended)
The sync identity is **`(acq_date, original_name)`** where `original_name` is the relpath from
the source root = **the REMI path** (`config._build_dedupe_index`, `expand_batch`). This is the
lever that makes the user's design work:

- **Step 1 — preview/plan:** emit a CSV (extends today's `ni_live_discover --csv`) with one row
  per acquisition: the REMI `original_name` (identity, **read-only** — operator must not edit
  it), plus the *editable value* columns (`project`, `session_id`, animal/`subject` ids,
  `timepoint`, …) prefilled with the parsed values, plus blank `add_meta_*` columns for
  per-session extras.
- **Step 2 — operator edits** the value columns to fix REMI mistakes and adds tracer field/value
  pairs. They do **not** touch `original_name`.
- **Step 3 — ingest consumes the corrections CSV:** corrected values populate the **registry +
  metadata.json fields only**; `original_name` (the dedup key) stays the *uncorrected* REMI
  path. Result: a later sync sees the same identity → not "new"; the corrected metadata is
  reproduced from the persisted corrections, not re-derived from the bad folder name.

**Corrections persistence (the anti-drift core).** Store corrections durably in
`registries/ni_corrections.csv` keyed on `(acq_date, original_name)`. Every sync loads it and
re-applies matching corrections automatically, so the human fixes a given session **once**.
This is the mechanism that prevents the "REMI stays wrong → re-correct every time / sync thinks
it's new" failure the user called out.

*Why CSV-intermediary over one-at-a-time interactive:* scales to a 127-case first load, is
reviewable/auditable, doubles as the persistence store, and matches the "pre-run report →
correct → run" model the user described. The interactive one-Enter-at-a-time mode is a fine
*future* convenience for the steady-state "a few new sessions" case (Open Decision).

### 3.3 Phase C — per-session additional metadata (tracer)
The `add_meta_*` (or a `key=value;key=value`) column(s) from the corrections CSV flow into a
new free-form block in `metadata.json` (e.g. `session_extra: {tracer: "...", ...}`), captured
at the same time as the corrections. Aligns with the existing NI backlog item "tracer compound
NOT in the data — must come from researchers/study records" (BACKLOG §"NI (Molecubes) — tracer
compound…"). Document the block shape in `mfb-rdm-docs/08_METADATA.md`.

### 3.5 Phase D — INCREMENTAL RECONSTRUCTION (the core; absorbs problem 0.2 + old new-recon)
NI data arrives in stages: **scan → folder + `recon_<idx>/` dirs created → DICOMs appear after
reconstruction finishes (much later) → sometimes MORE reconstructions are added later still.**
The sync must tolerate every stage. The lifecycle (user's words, 2026-06-25):

**Stage T0 — anchor present, recon dirs empty of DICOMs ("create the entry with metadata").**
Today this aborts (`ingest_raw.py:296`). Change: register a **placeholder acquisition** —
real registry row + `metadata.json` (session/subject parse) + empty `<ACQ-ID>.data/`,
`file_count=0` — and queue it to a new `registries/pending_ni_recon.csv` worklist. **Mirrors
the no-DICOM MRI placeholder pattern** (`pending_dicom.py` + the empty-`.data/` branch). Never
fails. Captures the session metadata immediately (while the operator is present to correct it).

**Stage T1 — DICOMs now present ("in the next sync add the actual acquisition").** A later sync
finds the placeholder's recon dirs now hold DICOMs. It **fills the same `<ACQ-ID>.data/`** with
the recons present (bundled into the one acquisition, exactly as today's working 122), updates
`checksums.json` + the registry `file_count`/size, records which recon indices were captured,
and dequeues from `pending_ni_recon.csv`. This is "the actual acquisition" (singular) — the
first real data for that anchor is ONE acquisition.

**Stage T2+ — NEW reconstruction appears later ("count as new acquisitions, nearly identical
metadata").** A still-later sync finds recon indices under the anchor that were **not** in the
captured set. Each genuinely-new recon registers as a **NEW acquisition** (new ACQ-ID) with
metadata copied from the sibling (same scan/subject/session/date) — only the recon identity
differs. It does **not** mutate the already-committed acquisition (acqs stay immutable once
filled).

**D4 RESOLVED (user, 2026-06-25): ONE ACQUISITION PER RECONSTRUCTION (uniform).** Each
`recon_<idx>/` is its own acquisition with its own ACQ-ID — from the first sync, not just
late-added ones. This is cleaner and makes "new recon = new acquisition" fall straight out of
normal discovery + dedup (no "diff present-vs-captured" logic). Cost: the **122 sandbox** cases
(currently bundling recons) must be re-ingested to match — cheap, they're test data in
`J:\gjesus3-sandbox`, not production. (The 132 NI **archive** preload already in production
stays as-is; only future/live ingests use per-recon. Mixed granularity old-vs-new is a minor,
acceptable wart.)

**Two NI-behaviour facts CONFIRMED (user, 2026-06-25) — they pin the design:**
- **Recon indices are append-only / never reused.** A new reconstruction always lands in a
  new, higher-numbered `recon_<idx>/`; an existing recon folder is never overwritten with
  different content. ⇒ `<anchor>/recon_<idx>` is a **stable per-recon dedup key**; dedup-by-path
  is fully correct (NO content-hashing), and a later recon is automatically a new acquisition.
  A filled recon stays correct — re-syncs skip it.
- **The anchor may have NO `recon_<idx>/` dirs yet** at sync time (reconstruction not started).
  ⇒ when an anchor has zero recon dirs, register NOTHING — skip with a clean message; the
  session is captured when the first recon dir appears. (Only the recon-dirs-exist-but-empty
  case — the 5 failures — makes a placeholder.)

**Implementation (per-recon) — the 7 pieces, build incrementally + test hard:**

1. **Discovery fan-out (NI-specific).** Today `expand_batch` matches the anchor
   `<ts>_<MODALITY>` folder (one case) via `pattern:"**/"` + the anchor regex. Add an
   NI-only fan-out (guard on `copy_strategy: ni_molecubes`): expand each matched anchor case
   into one case **per `recon_<idx>/`**, each carrying `discovered.ni_recon_idx` and
   `original_name = <anchor-relpath>/recon_<idx>` (the per-recon dedup key — `(acq_date,
   original_name)` is now per-recon, so a later recon is a *new* key = a new acquisition,
   automatically). Each recon-case then flows through the **unchanged** single-acquisition
   pipeline (its own ACQ-ID, registry row, copy).
2. **Copy scoping.** `copy_ni_acquisition(..., recon_idx=X)` copies only recon X's DICOMs into
   that acquisition's `<ACQ-ID>.data/` (default `None` = all recons = current behaviour, kept
   working until the fan-out is wired).
3. **Empty recon → SKIP (Tier B; fixes the 5).** DONE in the fan-out: a recon dir that exists
   but has **no DICOMs yet** is skipped with a clear log line ("reconstruction pending; will
   pick up on a later sync") — NOT registered, NOT a failure. An anchor with no recon dirs at
   all is likewise skipped. The fan-out reads the already-parsed sidecar to decide, so no extra
   disk I/O. (Tier C's register-a-placeholder-now option is deferred — see scope note.)
4. **Sidecar scoping.** `ni.reconstruction` reflects the single recon this acquisition
   represents (anchor-level study/subject/acquisition buckets unchanged — they're shared).
5. **Template.** `molecubes_ni_live.yaml`: add the recon to `link_filename` (today
   `${...acq_datetime_full}` is identical across an anchor's recons → would collide) and expose
   `ni_recon_idx`. `session_id` unchanged (PET+CT+all-recons of one visit still group).
6. **Placeholder-fill on re-sync — DEFERRED (Tier C).** Not built. In Tier B there is nothing to
   fill: an empty recon is simply skipped and, once its DICOMs appear, ingested fresh as its own
   acquisition by the normal per-recon discovery (recon indices are append-only, so the
   `<anchor>/recon_<idx>` key is stable). The early-register-then-fill option — which would need
   an in-place registry row update under the lock — is the only part that touches the registry
   integrity layer; deferred unless specifically wanted (scaffold removed, revivable from
   `3e0896d`).

**VERIFIED end-to-end (2026-06-25, synthetic NI tree → throwaway nas-root):** a CT scan with
recon_0 + recon_1 filled and recon_2 empty → two acquisitions (CT-001=`/recon_0`,
CT-002=`/recon_1`), each `.data/` holding only its own recon; the empty recon_2 + a no-recon PET
both skipped (Total 2, **Failed 0** — the 5 fails are gone). Re-run = idempotent (0 new). Adding
recon_2's DICOMs then re-running → exactly one new acquisition CT-003=`/recon_2`. Unit test
`tools/test_ni_per_recon.py` (12 checks) + full suite (10 suites) green.
7. **Tests + end-to-end:** per-recon discovery, recon-scoped copy, empty-recon placeholder,
   placeholder→fill, new-recon→new-acquisition, idempotent re-sync. Then a sandbox re-ingest
   of Irene's batch.

### 3.5a `pending_ni_recon.py` placeholder worklist — REMOVED (Tier C only)
Built then removed once Tier B was chosen (Tier B skips empty recons rather than registering
placeholders, so there is nothing to queue/fill). Revivable from commit `3e0896d` if the
register-before-DICOMs option is ever wanted.

### 3.6 Phase E — Mac-compiled GUI (LAST, explicitly deferred)
Once the CLI flow (A–D) is solid, build the NI analogue of the HTML ingest tools, **compiled on
the Mac** (PyInstaller on macOS). Same "simple page" philosophy as the MRI GUI. Do not start
until A–D are proven on the box.

---

## 4. Backlogs to file (drafts ready; file into `tasks/BACKLOG.md` on go-ahead)

1. **NEW — Hard links from other OSes / non-SMB paths to project links.** macOS (and likely
   Linux) over SMB/CIFS return `ENOTSUP` on `os.link` (proven on the NI Mac, 2026-06-25). The
   `raw_linked/` hard-link model assumes hard-link-capable access (true on the Windows
   workstation). Research options: NFS or AFP mounts that preserve hard links; QNAP
   `cp --reflink` if the volume is btrfs/ZFS; SMB protocol/`nsmb.conf` tuning; an SSH-to-NAS
   path that runs `ln` server-side; symlink semantics (and why they're fragile across the
   J:\ vs /Volumes mount-path split). Cross-link the §1 worklist + §4.2/§4.3 below.
2. **REFINE existing** — *Finder "Select → assemble a project"* (`BACKLOG.md` §"Finder — Select-in-Finder
   → assemble a project") and *server-side ingest + downstream Windows tool* (§"Server-side raw
   ingest…"): both already describe the **researcher grab-tool** (search uploads → assemble
   into a project, **create the hard links + provenance + project files**) that the user
   re-raised. Add the NI Mac hard-link failure as fresh motivation and cross-link to
   `pending_links.csv` (that worklist is exactly what such a tool would drain).
3. **REFINE existing** — *server-side Linux ingest host* (`BACKLOG.md` §"Server-side raw ingest…")
   already captures "a server people log into to run ingests + post-processing." Add the NI
   hard-link failure as another reason (a Linux box on a hard-link-capable mount makes
   `raw_linked/` links at ingest, dissolving the worklist for server-ingested data) and
   cross-link §1.

---

## 5. Open decisions (flag at approval)

- **D1 — Correction UX:** CSV-intermediary (recommended, §3.2) vs interactive one-at-a-time vs
  both (CSV for bulk first-load, interactive for steady-state). Recommend: build CSV first;
  add interactive later.
- **D2 — Stand-in link form (§1.3):** pointer `.PENDING-LINK.txt` (recommended) vs byte-copy
  (heavy, risks NAS fill) vs symlink (fragile across mount paths) vs nothing (rely on the
  worklist alone). Recommend pointer file.
- **D3 — Scope of THIS branch:** RESOLVED — user wants §1 + §2 + §3 **all on this one branch**
  (`feat/ni-live-hardening`). Not split.
- **D4 — Recon granularity (§3.5):** RESOLVED (user 2026-06-25) — **one acquisition per
  reconstruction** (uniform). Re-ingest the sandbox 122 to match; production archive 132 stays.

---

## 6. Sequencing (all on `feat/ni-live-hardening`)

1. **§1** link-fallback: `pending_links.csv` worklist + wire-in + stand-in pointer + `relink_pending.py`
   + tests + docs. (Independent of everything else — do first.)
2. **§3.5** incremental reconstruction (absorbs the 5 fails): placeholder→fill→new-recon, the
   `pending_ni_recon.csv` worklist, per-recon dedup key. The big one; design + tests carefully.
3. **§3.1–3.3** operator CLI (no YAML) + pre-run corrections CSV + per-session tracer metadata.
4. **§4** file the backlogs.
5. Re-run Irene's batch in the sandbox: 0 link errors lost (all queued), the 5 register as
   placeholders, idempotent re-run = no churn, a simulated late recon = a new acquisition.
6. **§3.6** Mac-compiled GUI — LAST.
