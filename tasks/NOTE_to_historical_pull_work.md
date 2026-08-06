# Note to whoever picks up the S:\gnuclear historical pull

From the NI live-sync work on `feat/ni-live-hardening`, 2026-08-06. **Nothing of yours was
changed** — this is a heads-up about two things that moved underneath you.

## 1. Your uncommitted edit is now on an ARCHIVED file — re-target it

`tasks/tasks.md` no longer exists on `main`. It was **archived to
`tasks/archive/tasks.md`**, and the current entry point is **`tasks/STATUS.md`** (later
improvements go to `tasks/BACKLOG.md`, dated history to `CHANGELOG.md`).

Your working tree carries an uncommitted modification to that file. When I rebased this
branch onto `main`, git correctly followed the rename, so your edit now sits on
`tasks/archive/tasks.md`.

**That matters** because the updated `CLAUDE.md` adds a hard rule: *never edit historical /
archived material — files in `tasks/archive/`.* So committing it as-is would land your
change in exactly the place the rules say not to touch.

**What to do:** move the substance of that edit into `tasks/STATUS.md` (or
`tasks/BACKLOG.md` if it is a later improvement) and revert `tasks/archive/tasks.md`. Check
`git diff tasks/archive/tasks.md` to see what you had written.

Your other three files are unaffected:
- `equipment/historical_data_archives.md` (modified)
- `equipment/nuclear-imaging/gnuclear_active_workspace_layout.md` (untracked)
- `tasks/ni_gnuclear_active_space_plan.md` (untracked)

## 2. New NI equipment docs exist on `main` — read them before you re-plan

`main` gained substantial NI documentation while this work was parked. At least two are
directly relevant to a `S:\gnuclear` pull:

- `equipment/nuclear-imaging/live_machine_data_layout_and_sync_rules.md` — backed by a
  295,538-line dump of the box's actual paths. If your plan makes assumptions about the
  on-box folder structure, check them against this first.
- `equipment/nuclear-imaging/live_machine_remote_access.md` — a reverse SSH tunnel to the
  Molecubes box. **Workstation half verified; the box half has not run yet** and needs a
  physical access slot on the Mac.

Your `tasks/ni_gnuclear_active_space_plan.md` predates both.

## 3. Status of the thing you were waiting on

The historical pull was deprioritised in favour of getting live reads working, and that is
still where things stand. The live work is close but **not merged**: the operator flow is
the last substantive piece (see `tasks/ni_live_operator_flow_plan.md`), and the
2026-08-05 on-box test stopped at a read-only step, so no ingest has yet been proven on the
box.

One relevant finding, since your pull would hit the same wall: **hard links do not work
from the NI Mac.** `os.link` returns `ENOTSUP` over its SMB mount (confirmed on the box,
2026-08-05), so project `raw_linked/` links cannot be created from there — they are
deferred to `registries/pending_links.csv` and drained later from the Windows workstation.
A `S:\gnuclear` → `J:\` pull run **from Windows** does not have this problem (hard links are
proven there), which is worth confirming stays true for your route.

## 4. One caution

Two synthetic acquisitions from a development verification run are currently sitting in
**true production** (`ACQ-20260212-CT-001` / `-002`), because that run pointed `--nas-root`
at `J:\gjesus3-data` instead of a throwaway NAS. Removal list:
`tasks/ni_prod_testdata_removal.md`. Mentioned here only as a warning for a bulk pull —
**check `--nas-root` before every run**, and be aware there is currently no guard that
distinguishes a test run from a production one.
