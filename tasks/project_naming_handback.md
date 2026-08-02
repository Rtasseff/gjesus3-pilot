# Handback — project naming (branch P) → coordinating developer

**Status:** ✅ **COMPLETE.** Phases A + B + C all executed, including the live
production migration and the operator-exe redeploy.
**Branch:** `refactor/project-naming` → **merged to `main` as `9be7ada`**.
**⚠️ NOT PUSHED** — pushing needs Ryan's explicit OK (see §3.1).
**Supersedes** `tasks/project_naming_handoff.md` (v4), deleted on landing per the
drop-temp-handoffs precedent.

Full record: [`CHANGELOG.md`](../CHANGELOG.md) 2026-08-02 · current state:
[`STATUS.md`](STATUS.md) §2 · the model itself:
[`05_PROJECTS §2a`](../mfb-rdm-docs/05_PROJECTS.md).

This file exists for the **three things that need a human**, plus the leftovers.
Delete it once §3 is drained.

---

## 1 · Where reality differed from the handoff

The handoff's §2 said to stop and re-verify if live state didn't match. Two
things didn't. Neither blocked the migration; both are recorded because they
change what a future reader should believe.

**1.1 There are 43 `_project.yaml`, not 48.** The 5 closed-but-still-present
folders (`ae-biomegune-{0219,0220,0320,0618,1019}`) have only `provenance.csv`
+ `raw_linked/` — their `_project.yaml` was removed at the 2026-07-14 close-out.
The migration script is data-driven and skipped them; no action needed. But any
future count that assumes "one `_project.yaml` per folder" is wrong by 5.

**1.2 Hard links CANNOT be verified by link count on this NAS.** Over the
gjesus3 SMB share, `os.stat().st_nlink` always reports `1` and
`fsutil hardlink list` returns `Error 50: The request is not supported`. The
first verification run therefore reported `0/29 links intact` — a **false
alarm**; the links were fine. The check now compares **file identity**
(`os.path.samefile` + file index), pairing each link to its acquisition through
the project's `provenance.csv`. Pairing by directory order instead — the
obvious shortcut — silently compares one acquisition's raw file against a
*different* acquisition's link and produces convincing nonsense.

> **Carry this forward:** any future tool that wants to assert "this is still a
> hard link" on gjesus3 must use identity, not `st_nlink`, not `fsutil`. This is
> the single most reusable finding from the migration.

Actual result after migration: **134/134 acquisition/link pairs across all 51
projects confirmed to be the same file.**

---

## 2 · A safety bug the sandbox caught before production

The migration script was exercised against a sandbox built from a **copy of the
real registries** and the real 48-folder tree with genuine hard links, before it
was pointed at production. That run found a bug worth knowing about:

> Re-running `--apply` after a partial failure backed up the **half-migrated**
> state over the only pre-migration copy — destroying the rollback at exactly
> the moment it would be needed.

Fixed before any live run: `make_backup` now refuses to overwrite an existing
backup and says so loudly. The sandbox also asserts a second `--apply` is a
clean no-op and that `--reverse` restores both CSVs byte-for-byte and all 48
folder names.

**Why it matters beyond this task:** "dry-run first" was not sufficient — the
dry run was clean and the bug lived only in the *re-run* path. A rehearsal on
real-shaped data caught what a dry run structurally could not.

---

## 3 · Leftovers — things still to do

### 3.1 Push to `origin` — NOT DONE, needs Ryan's OK
`main` is at `9be7ada` locally, unpushed. Everything else (production data,
deployed exe) is already live, so **the repo is currently behind the running
system** — worth closing promptly so `main` and reality agree.

### 3.2 Operator comms — REQUIRED before the next operator ingest
Two changes operators will notice, both already written up in
[`STATUS.md`](STATUS.md) §2:

- **The 6 saved recipes on the NAS were deleted** (`J:\gjesus3-data\recipes\`).
  They carried the retired `registry.project_hint` key and would now fail to
  load. Operators recreate them in the builder — a minute's work, and a
  deliberate decision (a recipe that errors on load is worse than one rebuilt).
  Backed up at the path in §3.3 if any need to be read back.
- **Project folders were renamed.** `proj-ae-biomegune-0525` →
  `AE-biomaGUNE-0525`; `proj-claudia` → `claudia`. **Any saved shortcut or
  bookmark into a project folder needs re-pointing.** `/raw/` was not touched
  and no data moved — the hard links are intact.

### 3.3 Rollback assets — keep until first real operator ingest
`C:\Users\rtasseff\temp\gjesus3_projectnaming_backup_20260802\`
(both registry CSVs, all 43 `_project.yaml`, the 6 recipes, a folder listing,
and `mapping.json`). Restore with:

```
python tools/migrate_project_naming.py --nas-root "J:\gjesus3-data" \
    --reverse --from-backup "C:\Users\rtasseff\temp\gjesus3_projectnaming_backup_20260802"
```

Safe to delete once a real operator ingest has succeeded through the new exe.

### 3.4 Disk leftovers on this workstation
| Path | What | Action |
|---|---|---|
| `D:\_dist_pn\gjesus3_ingest.exe` | the build that is now deployed (sha256 `ca2bd1c7…`) | keep until §3.3 is cleared, then delete |
| `D:\_build_pn`, `D:\_smoke_pn` | PyInstaller work dir + smoke-test scratch NAS | **delete** (an automated `rm -rf` was denied; needs a manual removal) |
| `D:\_idxcheck` | throwaway Finder output from a post-merge check | delete |
| `J:\...\tools\gjesus3_ingest.exe.old_20260802` | previous deployed exe | keep one cycle, then delete |
| `J:\...\tools\gjesus3_ingest.exe.old_20260720` | the cycle before that | safe to delete now |

---

## 4 · Explicitly NOT done (unchanged from the handoff's non-goals)

- **Deleting the 5 closed-but-present folders** — a separate, deliberate
  close-out action; Ryan's call.
- **Semantic re-projecting of person/topic projects** (PROJ-05 /
  [`BACKLOG.md`](BACKLOG.md)). This migration was **mechanical normalization
  only** — drop the prefix, fix the casing. The question of whether `claudia`
  and `laura` *should be* projects is untouched and still open.
- **`registry_publications` / `registry_datasets`** keep their own unrelated
  `short_name` columns — deliberately out of scope.
- Tightening `validate_registries`' project check to a hard failure.

---

## 5 · Verification evidence (for the record)

| Check | Result |
|---|---|
| Test suite (repo) | 17/17 files pass, incl. new `test_project_naming.py` |
| `registry_raw` data | byte-identical; header-only change; 13,582 rows |
| Project join | all 13,582 rows resolve to a project |
| Folders | 48 renamed; **0** `proj-*` remaining |
| Hard links | 134/134 pairs same-file (by identity — see §1.2) |
| `validate_registries` | **0 errors** (16,819 warnings are pre-existing enrichment sentinels) |
| Finder | regenerated — 13,582 acqs, 43 per-project indexes, 8 closed skipped |
| Deployed exe | checksum matches build; serves "Project name" + `${project_name}`/`${project_id}` |
| Production smoke test | real non-dry-run ingest resolved `ae-biomagune-1123` → `PROJ-0014 (AE-biomaGUNE-1123)`, appended to the new header, linked into the new folder, hit the animal-facility DB — run against a **scratch NAS seeded with the migrated live registries**, so production `/raw` was never written to |
