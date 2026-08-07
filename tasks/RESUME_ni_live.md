# ▶ RESUME HERE — NI live sync (read this first)

**Single entry point** for the `feat/ni-live-hardening` work. Written 2026-08-07 immediately
before migrating to a new worktree and restarting the session, so **assume the assistant has
zero memory of any of this** — everything needed is here or in the docs this points to.

---

## 1. Where things stand

- **Branch `feat/ni-live-hardening`**, pushed to origin, **16 commits ahead of `main`, 0 behind**
  (rebased onto `main` `dde99fc` on 2026-08-06 — we had silently drifted 69 commits behind,
  don't let that happen again).
- **NOT merged, deliberately.** Merge waits on the on-box test (§4).
- All NI test suites green: `tools/test_ni_corrections.py`, `test_ni_per_recon.py`,
  `test_pending_links.py`, `test_ni_live_discover.py`, `tools/ingest/test_registry_fields.py`.
- Backup tag `backup/ni-live-hardening-pre-rebase` = the pre-rebase tip `f2ee114`.

**Run the tests as `PYTHONPATH=tools python tools/<name>.py`** — they are hand-rolled scripts,
not pytest.

## 2. The plan, in order

### (a) Finish the NI live sync so it works exactly how operators need — CURRENT PHASE
Keep using the current approach: code lives in this repo, runs from the shared NAS
(`gnuclear`), writes to `gjesus3`. **It has been running on the Mac fine.** Do not start
simplifying yet — get it correct first, then trim.

**The one open design item — where the corrections CSV lives.** Decided in principle
2026-08-06, not yet built:

- Move it **off** `J:\gjesus3-data\registries\` and **next to the code on the shared
  `gnuclear` NAS** — the errors are Mac-local reality (messy folder names on that box), the
  code runs there, and keeping it off the Mac's local disk also helps the audit story (§3).
- **`gnuclear` already stores things in a `year/group/user` layout, and the group + user
  naming matches the Mac's.** Ryan flagged this as the natural home — work out the exact
  path against that convention before implementing.
- **One file per researcher** (e.g. `ni_corrections_irene.csv`). A single shared file gets
  big and messy.
- **Collapse two files into one.** Today `--plan` writes a new CSV which is then merged into
  a separate stored copy — that merge is the *only* reason there is a rule about what a blank
  cell means, and Ryan (rightly) called that needless complexity. Target: **one file the
  operator owns and edits forever** — `--plan` appends rows for sessions it has never seen and
  never touches existing rows; the operator edits in place; the ingest reads it. No merge, no
  store-vs-worksheet distinction, no blank-cell rule.

Everything else in phase (a) is built — see §5 for what landed.

### (b) Simplify what runs on the NI acquisition Mac — NEXT, NOT NOW
The idea to explore (Ryan's): copy a temporary dataset to a **gjesus3 staging location** and
automate the processing from there. The Mac-side then only needs to *find new reconstructions
and copy them* — realistically ~100 readable lines — while the heavy machinery runs off his
equipment entirely. Hard links work on the Windows side, so the deferred-link handling would
stop mattering too.

**This is not the "users run it from the Windows workstation" idea — that was rejected**
(extra step, users won't adopt it). The user still runs one command on the Mac; only the
*location of the code* changes.

Longer term this is all expected to be superseded by a dedicated box everyone can reach
(plus a tunnel, or an ethernet cable between the two machines).

## 3. The platform-manager constraint (important, easy to lose)

The NI Mac belongs to a platform manager whose job is keeping the equipment running. He is
not a CS person; to him the box is where numbers come out of the PET hardware.

- **He does not mind what Ryan runs while physically present.** His concern is **what we leave
  behind and ask operators to run.**
- He has **expressly asked to read the code.** Platform managers here generally want "a few
  lines plus references to well-accepted dependency packages."
- **He cannot read what exists**: the five main files are **4,633 lines**
  (`ingest_raw.py` alone is 1,943). No framing fixes that — it is why phase (b) exists.
- He is not worried about a few small files being written. He is worried about (i) code too
  big to understand, (ii) anything that erases or overwrites, (iii) anything long-running —
  **that box is slow**.
- **`pydicom` is NOT required.** `tools/ingest/ni_metadata.py:32` — it is optional and
  degrades gracefully (headers skipped, ingest still works). Nothing had to be installed on
  the Mac; the staged `tools/` on the NAS just ran.
- **Verified: the ingest never writes to the source folder.** `delete_source_after_ingest:
  false` is hard-set in `molecubes_ni_live.yaml`, and no code path writes into `staging_dir`
  (the only reference is a relative-path computation in `config.py`).
- **Decision made 2026-08-06:** do **not** present the tooling as "just processing code that
  doesn't save anything" to get past an audit. It does save things; if he discovers that, the
  loss is permanent equipment access, not an argument. The better answer is **demonstrable
  rather than readable** — a mode that prints every path it will read and write and touches
  nothing, which he can run himself. Stronger than reading code, since code doesn't prove
  runtime behaviour.

## 4. Merge gates — none of these exist yet

No `--go` ingest has **ever** run on the box. The 2026-08-05 session stopped at the read-only
`--plan` step. Before merging, prove on the box:

1. A real `--go` producing `.../recon_N` registry rows (one acquisition per reconstruction).
2. A corrected session showing a `session_extra` block in its `metadata.json`.
3. `registries/pending_links.csv` written with `ENOTSUP` / `darwin` rows. **This file exists
   on neither NAS today** — the deferred-link feature has never written a row for real.
4. A second sync: idempotent (0 new), and a **late reconstruction registering into an
   already-corrected session with the correction still applied.**

Gate 4 is the acceptance test for the persistent-corrections change and is the one most
likely to be got wrong.

**Operator instructions are `tools/operator/NI_LIVE_RUNBOOK.md`** — two commands. The old
`RUN_THE_TEST.md` staged at `S:\gnuclear\2026\Jesus\Ryan\ni-live-test\` is a *developer* test
script, is from 2026-06-30, and predates everything below. **Stage a fresh copy of `tools/`
there before the next box session.**

## 5. What landed on this branch (why, not just what)

| Commit | Change |
|---|---|
| `0fb84db` | Dropped `session_id` / `sample_id` from the corrections CSV — both are **derived** for NI, so offering them as editable columns created a competing source of truth. Real damage: a project correction re-derived `project_hint` while a hand-set `sample_id` went stale. Also stopped prompting for condition/anatomy on read-only passes (`--plan` / `--dry-run`), and locked `anatomy.is_whole_body: true` in the live template — Molecubes scans the whole animal every time, so it was never a per-batch question. `condition:` is deliberately NOT defaulted. |
| `1137561` | **Corrections persist** instead of living in a throwaway per-run file. NI reconstructions arrive late and land in sessions that were already corrected, so the old design silently re-applied the *uncorrected* values to those new acquisitions. Currently stored at `registries/ni_session_corrections.csv` — **§2(a) moves this**. |
| `6fda90f` | `--root` accepts either the parent of the researcher folder or the folder itself, and **raises** when it matches neither (it used to walk nothing, exit 0, and write a header-only CSV that read as "this researcher has no data" — that cost a slot at the box). Added `NI_LIVE_RUNBOOK.md`. Marked `ni_live_discover.py` a data-office diagnostic, not an operator step. |
| `a7be9d8` | `--plan` no longer walks the source tree twice (`preview_batch` was re-running the identical recursive glob just to display a count `--plan` never prints). **Structural fix, NOT measured on the box** — if `--plan` is still slow there, profile ON the box first. **Do not add a cache.** |
| `46e2120` | Gate-0 closed (see §6), operator-flow plan, on-box test review, production-cleanup list. |

Earlier commits (rebased): deferred project links → `pending_links.csv`, one acquisition per
reconstruction, `--live` mode (no per-batch YAML), corrections + tracer metadata.

## 6. Facts established, don't re-litigate

- **Gate-0 is CLOSED and the answer is NO.** `os.link` on the NI Mac's SMB mount returns
  `ENOTSUP` (tested on the box 2026-08-05, python 3.10.5 darwin). macOS over SMB has no hard
  links. Already handled by deferring to `pending_links.csv`, drained from Windows by
  `tools/relink_pending.py`. This needed no access slot and is **not** a task for the SSH
  tunnel — `NI-RA-05` in `equipment/nuclear-imaging/live_machine_remote_access.md` can close
  against it.
- **Remote access to the box is NOT established.** The workstation half is verified; the box
  half has never run and needs a physical access slot. Do not plan around having it.
- **Reconstruction indices are append-only** on the box — a new reconstruction always lands in
  a new, higher-numbered `recon_<idx>/`, and an existing one is never overwritten. This is why
  `<anchor>/recon_<idx>` is a safe dedup key and why no content hashing is needed.
- **Counts from the 2026-08-05 run are correct, not a bug**: 141 scans → 78 sessions → 75
  planned. `review_irene.csv` is one row per acquisition; the corrections CSV is one row per
  session.
- **ISA / vocabulary question is OPEN and does not block merge.** What is `1207`? Documented
  only as `series_id` (a positional name we invented) in
  `equipment/nuclear-imaging/internal_ni_data_handling_workflow_notes.md:29`. Ryan has since
  confirmed with a source: **NI calls it the Series ID, and it is also the internal
  biomaGUNE funded-project ID, recorded because it is reportable to granting agencies.** The
  AE protocol code (e.g. `0522`) legitimately serves three roles — animal-ethics protocol,
  animal-facility DB key, and (by researcher preference, not enforced) the project name. None
  of that should change. Needs documenting; the "which is the ISA Investigation" choice is a
  backlog item.
- **`session_id` needs re-thinking (backlog, high priority).** It was created for DICOM
  organisation and was mapped to the ISA "study" level — **that mapping is wrong.** A session
  is one animal in one sitting; an ISA study involves many animals. Also worth asking whether
  it belongs at registry level at all, since not every data source has one. Ryan's call,
  2026-08-06.

## 7. Open items NOT on this branch

- **Two synthetic acquisitions are in TRUE PRODUCTION** (`ACQ-20260212-CT-001` / `-002`) from a
  2026-06-29 verification run that pointed `--nas-root` at `J:\gjesus3-data` instead of a
  throwaway NAS. **Removal list ready and handed off: `tasks/ni_prod_testdata_removal.md`.
  Do not execute it from this branch.**
- **Backlog, high priority — `pending_dicom_regen.csv` header drift.** The live file has 9
  columns (`nonimage_marker`), the code expects 8, `_assert_header` raises, and
  `ingest_raw.py:1034` swallows it — so the DICOM regeneration queue is **write-broken in true
  production right now**. Evidence favours adopting the column. Deliberately deferred: we were
  too far behind main to take it on.
- **Backlog** — a unified checker for the three partial-ingest worklists (DICOM regen, hard
  links, DB subjects), run on a schedule from the Windows workstation; the `new recon/` folder
  depth mismatch; a guard so `--nas-root` can't silently point at production.
- The historical `S:\gnuclear` pull is paused and prioritised behind this work. See
  `tasks/NOTE_to_historical_pull_work.md`.

## 8. Working agreements

- **Do not increase complexity.** Ryan, repeatedly: the system is barely used *because* it is
  complex. Every change in phase (a) should be a removal or a merge of existing steps. If a
  proposal turns into "add a new mode/flag/file", stop and re-think.
- **Commit freely; never push without explicit permission** (per `CLAUDE.md`).
- **Stay current with `main`** — check `git rev-list --count HEAD..origin/main` at the start of
  a session. We hit 69 behind once; the rebase was clean but it cost real time.
- Plans and handoffs go in `tasks/`. Wait for explicit go-ahead before executing them.
- `tasks/STATUS.md` is the current-state entry point (**not** `tasks/tasks.md`, which was
  archived to `tasks/archive/tasks.md` — never edit archived files).

## 9. Related docs

| File | What it holds |
|---|---|
| `tasks/ni_live_operator_flow_plan.md` | The operator-flow design + what landed against each section |
| `tasks/ni_live_operator_plan.md` | The older, larger design + history doc (per-recon model, decisions D1–D6) |
| `tasks/ni_live_onbox_test_review.md` | Full findings from the 2026-08-05 on-box run |
| `tasks/ni_prod_testdata_removal.md` | Production cleanup hand-off list |
| `tools/operator/NI_LIVE_RUNBOOK.md` | Operator-facing instructions (two commands) |
| `equipment/nuclear-imaging/live_machine_data_layout_and_sync_rules.md` | The box's actual folder layout, from a 295k-line path dump |
