# The M. Jesús drive (third historical drive): the production plan

**Status:** 🔶 IN PROGRESS · **Started:** 2026-10-06 · **Coordinator:** the planning session `gj3-handoff`
**Read first:** STATUS §2 ("The M. Jesús drive") and §0.5, then the three assessment reports this plan is built on:
[`drive3_raw_coverage.md`](drive3_raw_coverage.md) (A1), [`drive3_projects_and_placement.md`](drive3_projects_and_placement.md)
(A2), [`drive3_segmentations_cds.md`](drive3_segmentations_cds.md) (A3). The process copies the drives 1+2 close-out
([`historical_drives_closeout_plan.md`](historical_drives_closeout_plan.md)), which worked.

---

## Who may approve a production write

The drives 1+2 approval model (Ryan, 2026-10-02), applied to this drive:

- **The coordinator may approve, without waiting for Ryan, a write whose dry run matches what Ryan has already decided:**
  - copying non-raw files into project folders and the holding folder: copies only, nothing deleted, no registry row
    changed;
  - the reopen of `AE-biomaGUNE-1121` (ruled 2026-09-30; ✅ done 2026-10-06);
  - the project descriptions, once §0.5 M1 is answered (ruled 2026-09-30: the drive's own wording).
- **Everything else waits for Ryan's go**, given after the coordinator has gated the dry run:
  - each ingest (PET/CT, Cell Observer, MRI);
  - the reopens of `AE-biomaGUNE-1521` and `-0618` for their 19 documents (05 §4.y);
  - anything that departs from this plan.
- **One registry writer at a time.** A stream builds, dry-runs and rehearses; the coordinator reviews, opens the write
  window, runs or supervises the write, and verifies it independently. Copy-only windows on disjoint folders may run
  beside one registry writer. Each write takes a fresh, dated, off-NAS backup first.

## The streams

| # | Stream | Branch · worktree under `gjesus3-dev\` | Needs before production | State |
|---|---|---|---|---|
| **P** | Non-raw placement into project folders and the holding folder (A2's plan) | `feat/drive3-placement` · `drive3-placement` | the coordinator's gate (copies only) | building |
| **N** | PET/CT: the 202 reconstructions production lacks (A1 §4) | `feat/drive3-petct` · `drive3-petct` | gate, then Ryan's go | building |
| **C** | Cell Observer: the 5,115 `.czi` production lacks, 643 GB (A1 §5) | `feat/drive3-czi` · `drive3-czi` | gate, then Ryan's go | building |
| **M** | MRI: the 3,309 image exams production lacks (all `0118` to `AE-biomaGUNE-0118`), and the CNIC pig images as `XMRI` in a new project `CNIC-HEARDS` (A1 §2–3; Ryan's rulings of 2026-10-06) | `feat/drive3-mri` · `drive3-mri` | gate, then Ryan's go | to build |
| **P2** | A second placement batch: the 3,830 files stream M does not register (71 unconvertible exams, 45 `2dseq`-only reconstructions, the other `m175`/`m178` reconstructions, 31 pig-folder files taken BY PATH: four are MATLAB files named `thumbs.cache`/`folders.cache`), and the pig masks from holding into `CNIC-HEARDS` (2b `copy --from-holding`) | built by stream M's session with P's tool | the coordinator's gate (copies) | to build |
| **S** | The curated cine-mask dataset CAND-A (A3) | none yet | §0.5 M3 (M. Jesús's answers), then curator approval (12 §6.2) | waiting |

**Not in any stream yet:** `biomaGUNE MJ` (last, by Ryan's order; A2 §6 has its inventory); the data from the Axioscan
and the Leica that are not gjesus3's (A1 R6; waits on M. Jesús, then the Charité `XMIC` precedent).

## Rules every stream follows (decided; cite, do not re-open)

- **Dedup by SHA-256 only, and acquisition identity by (instrument, acquisition time, name):** a re-saved `.czi` has
  different bytes but is the same acquisition.
- **Raw vs derivative (Ryan, 2026-10-01):** `/raw/` holds the acquisition; derivatives go to the project folder.
- **MRI (Ryan, 2026-10-04):** registered only with DICOM, or with DICOM made before ingest from the staged copy.
- **Project claims (Ryan, 2026-09-29):** confirmed / (A) / (B) / (C); a check confirms a claim, never overrules it.
  **A2's four readings R1–R4 are accepted by the coordinator** (they fill blank projects with evidence; none overrules a
  claim), and so are **one study folder per content** (A2 D3) and **placing the 25 cross-project files in drive 3's
  project too** (A2 D5).
- **Placed drive material:** `<project>\working\historical_drives\<drive label>\…` through
  `tools/drive_staging/historical_paths.py` (≤ 240 characters, `_INDEX.csv`, `_PATHMAP.csv`, `README.txt`,
  `_ORIGIN.txt`). This drive's label: `MJesus-MFB`. Material with no project goes to
  `J:\gjesus3-data\staging\historical_drives_unassigned\` under its own drive folder, in its original structure, with a
  README.
- **Protocol `0118`'s material waits for §0.5 M1**, except what lands in `AE-biomaGUNE-0118` under either answer (the
  Monocrotalina documents).
- **The staged copy is read-only.** Never write under `J:\_staging_drive3_MJ\`. Tools that write beside their input
  (e.g. `convert_staged_exams.py`) work on a scratch copy or a symlink tree on `D:\`.
- **Environment traps:** Bash heredocs mangle backslashes (write scripts with the editor); 951 staged files have paths
  of 260–277 characters (use the `\\?\` prefix with Python's own `open()`); give each agent its own scratch folder.

## Close-out (after every stream)

1. Every ingested file's SHA-256 matched against the drive manifest; every placed file against it too.
2. The evidence copied to `J:\gjesus3-data\staging\historical_drives_records\drive3_MJesus_WX22D623YP29\` (manifest,
   inventory, copy and verify logs, `drive_info.txt`), SHA-256-verified.
3. **Before the staged copy goes:** `biomaGUNE MJ` triaged and placed (it holds more segmentations; Ryan, 2026-10-06:
   "do not loose those segmentations"), and the raw that is not registered (the foreign Axioscan and Leica files, the
   MRI exams that cannot be converted) copied to the holding folder.
4. The staged copy (`J:\_staging_drive3_MJ\`, 1,681 GB) deleted, **on Ryan's go**. The owner keeps her drive; staging
   is not a backup.

## Log

- **2026-10-06:** taken over; `stage_copy.py` v1.5 adopted (`82d4e97`); assessment merged (`d659270`);
  `AE-biomaGUNE-1121` reopened and verified; streams P, N and C cut.
