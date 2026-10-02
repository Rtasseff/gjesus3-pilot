# ▶ RESUME HERE — NI live sync (read this first)

**Single entry point** for the `feat/ni-live-hardening` work. Written 2026-08-07 immediately
before migrating to a new worktree and restarting the session, so **assume the assistant has
zero memory of any of this** — everything needed is here or in the docs this points to.
**Updated 2026-10-01:** the NI Mac is now reachable from the Data Office (§0). §0 is the current
order of work and overrides anything older below that disagrees with it.

---

## 0. ▶ Start here — the order of work (2026-10-01)

**The goal (Ryan, 2026-10-01).** NI researchers operate the Molecubes scanner themselves. They
should ingest as close to acquisition as possible, with as few extra steps as possible. **The first
strategy is this branch:** a sync command they run on the acquisition Mac. The ultimate goal is
step 5: they leave the room when the experimental work is done and never come back for the data.

**What changed on 2026-10-01: the Mac can be operated from here.** A reverse SSH tunnel (Mac
LaunchAgent → workstation WSL) is live and hardened. From the workstation:

```powershell
wsl -d Ubuntu -- ssh -p 2222 molecubes@localhost      # no password; lands on molecubess-iMac.local
```

The full record (how it works, checks, removal, the visit, and the Box A move) is
`equipment/nuclear-imaging/live_machine_remote_access.md`. **That update is on branch
`docs/ni-tunnel-live`** (worktree `gjesus3-dev\ni-tunnel-live`, commit `9a98832`, off `main`
`48080b9`), **not on this branch**, to keep this branch's catch-up small. Merge it into `main`
first, and step 1 brings it here. Until then, the copy of that doc on this branch is stale (it
still says the box half is not installed).

**Do these in order:**

1. **Catch up with `main`.** This branch is **19 ahead / 111 behind** local `main` `48080b9`
   (2026-10-01). A dry run (`git merge-tree --write-tree main HEAD`, which writes nothing)
   conflicts in **7 files**:
   - **code:** `tools/ingest_raw.py`, `tools/ingest/metadata_sidecar.py` — resolve carefully,
     then run every test suite (§1);
   - **specs/docs:** `mfb-rdm-docs/08_METADATA.md`, `tasks/STATUS.md`,
     `equipment/historical_data_archives.md`;
   - **add/add** (both sides created the file):
     - `tasks/ni_gnuclear_active_space_plan.md` — `main`'s 550-line copy carries the finished
       historical pull (2026-08-12/13). Take `main`'s, then check whether this branch's 302-line
       copy holds anything `main` lacks.
     - `equipment/nuclear-imaging/gnuclear_active_workspace_layout.md` — both copies started from
       the same re-home on 2026-08-06. This branch then added the corrections-file content
       (`75c369a`). Take `main`'s and re-apply that addition.

   These merged cleanly in the dry run: `CHANGELOG.md`, `10_TOOLS.md`, `BACKLOG.md`,
   `tools/ingest/config.py`, `tools/operator/README.md`. Tag a backup first, as before. With 19
   commits replaying over code conflicts, consider `git merge main` (one resolution pass) instead
   of a rebase (possibly the same `ingest_raw.py` hunk several times) — Ryan's call. Either way,
   the push needs explicit permission.
2. **Get the Mac's `gjesus3` mount to stay up.** It is the sync's destination, and Ryan reports
   it drops (cause unknown). On 2026-10-01 16:32 it was mounted as
   `//rtasseff@GJESUS3._smb._tcp.local/gjesus3` on `/Volumes/gjesus3` (SMB 3.1.1). Both
   `gnuclear` mounts use an IP or DNS name instead — a lead, not a diagnosis. Diagnose over the
   tunnel, read-only first. **Also needs Ryan's decision:** the mount uses his personal
   credentials, a superuser under the permission model, so every researcher's sync would write
   with Full rights on `raw/` rather than an operator's write-but-not-modify.
3. **Run the on-box merge gates (§4) over the tunnel.** Stage a fresh copy of `tools/` on
   `gnuclear` first (§4). Gate 3 needs the `gjesus3` mount from step 2. A `--go` writes to
   production, so treat each run as a production operation. ✅ **The platform manager (Unai)
   has OK'd running the sync tests on the box remotely** (2026-10-02, asked by Ryan). The rest of
   §3 still applies. Schedule runs outside acquisitions, because the box is slow.
4. **Merge; operators start using it** (`tools/operator/NI_LIVE_RUNBOOK.md`).
5. **Then, not now:** the Box A port, which takes the tunnel along, make-before-break through the
   live tunnel with no visit (B2, decided 2026-10-01). After it, **one ingest web app on Box A**
   for every instrument: microscopy via network drives, MRI via SFTP, NI pulled through the
   tunnel. Users behind the firewall log in, and the server works with the system's setup and
   permissions on their behalf. A workstation-hosted version would work today, but it cannot
   serve everyone, because a tunnel cannot be set up on every user's machine. Details: `main`'s
   `tasks/BACKLOG.md` "Ingest from one place" and `tasks/box_a_production_migration_plan.md`
   (both on `docs/ni-tunnel-live` until it is merged).

**Tunnel do's and don'ts:**
- Don't run `WorkstationOps\setup\test-tunnel-path.sh` while the Mac is connected. Step 6 fails,
  because the Mac holds port 2222, and step 7 passes for the wrong reason. To check the live
  tunnel, run `wsl -d Ubuntu -- bash -c 'nc -w 4 localhost 2222 </dev/null | head -1'`, which
  should print `SSH-2.0-OpenSSH_8.1`.
- When scripting remote commands through `wsl.exe -- ssh … '…'`, `$(…)` expands on the
  workstation, not the Mac. Use a script with `ssh … 'bash -s' <<'EOF'`.
- After a Mac reboot, the tunnel returns only once someone logs into `molecubes`: there is no
  auto-login.

---

## 1. Where things stand

- **Branch `feat/ni-live-hardening`** — ⚠️ **as of 2026-10-01: 19 commits ahead of `main`, 111
  behind** (it drifted again; the catch-up is step 1 of §0). Last rebased onto **local** `main`
  `85af9d6` on 2026-08-12; before that `origin/main` `6b2ef41` on 2026-08-07 and `dde99fc` on
  2026-08-06 — we had silently drifted 69 commits behind once, don't let that happen again.
- **⚠️ REBASE ONTO LOCAL `main`, NOT `origin/main`.** As of 2026-08-12 local `main`
  (`85af9d6`) is **3 commits ahead of `origin/main`** (`b882e4a`) and is the only one that
  has the pending-links adoption. Rebasing onto `origin/main` silently misses it and
  reintroduces a second deferred-link queue. Check both: `git rev-parse main origin/main`.
- **`origin/feat/ni-live-hardening` still points at the OLD pre-rebase commits.** The next
  push needs `--force-with-lease`, and **pushing requires explicit permission.**
- **NOT merged, deliberately.** Merge waits on the on-box test (§4).
- All 20 test suites green, NI ones included: `tools/test_ni_corrections.py` (48 checks),
  `test_ni_per_recon.py`, `test_pending_links.py`, `test_ni_live_discover.py`,
  `tools/ingest/test_registry_fields.py`.
- Backup tags: `backup/ni-live-hardening-pre-rebase` = `f2ee114` (pre-2026-08-06);
  `backup/ni-live-pre-rebase-20260807` = `2909b31`; `backup/ni-live-pre-rebase-20260812`
  = `988e237`.
- **Rebasing in this worktree leaves a `rebase-merge` dir git can't delete** — OneDrive marks
  it ReadOnly, so git reports "currently rebasing" after a *successful* rebase. Clear ReadOnly
  and remove `…/.git/worktrees/ni-live-hardening/rebase-merge`; do **not** `git rebase --abort`,
  which would throw the rebase away.

**Run the tests as `PYTHONPATH=tools python tools/<name>.py`** — they are hand-rolled scripts,
not pytest.

## 2. The plan, in order

### (a) Finish the NI live sync so it works exactly how operators need — CODE COMPLETE
Keep using the current approach: code lives in this repo, runs from the shared NAS
(`gnuclear`), writes to `gjesus3`. **It has been running on the Mac fine.** Do not start
simplifying yet — get it correct first, then trim.

**✅ The last open design item — where the corrections CSV lives — is BUILT (2026-08-07).**
One file per researcher,
`<gnuclear>/<year>/<group>/<researcher>/ni_corrections_<researcher>.csv`, off gjesus3 and
onto the share the code already runs from. `resolve_path` derives the root/year/group
**from the running code's own path**, so it works unchanged on the Mac (a `/Volumes/…`
mount) with no env var and no flag, and the resolved path is logged every run. An existing
file is reused wherever it already sits, so a correction never expires at year-end.
The two files collapsed into one: `--plan` (now a bare flag) appends only unseen sessions
and never touches an existing row; every run reads the file; nothing merges or rewrites it.
The blank-cell rule is gone with the merge that required it. Full rationale:
`tasks/ni_live_operator_flow_plan.md` §3.7.

**Phase (a) is now code complete. What remains before merge is not code — it is running
it on the box (§4).**

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
(plus a tunnel, or an ethernet cable between the two machines). **Now concrete (2026-10-01):**
that box is Box A, the tunnel exists and moves there, and the plan is one ingest web app on it
(§0 step 5). Once a server can pull through the tunnel, nothing needs to run on the Mac at all. So
revisit (b) only if (a)'s footprint on the Mac becomes the blocker before Box A is ready.

## 3. The platform-manager constraint (important, easy to lose)

The NI Mac belongs to a platform manager whose job is keeping the equipment running. He is
not a CS person; to him the box is where numbers come out of the PET hardware.

- **He does not mind what Ryan runs while physically present.** His concern is **what we leave
  behind and ask operators to run.**
- ✅ **2026-10-02: he OK'd running the sync tests on the box remotely**, over the tunnel (asked by
  Ryan). This covers remote runs of the sync tests, not anything else; the concerns below still
  stand.
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

## 3a. The deferred-link queue now belongs to `main` — do not re-own it

**2026-08-12, Ryan.** The first commit of this branch (`0418ca6`, `pending_links.csv` +
`relink_pending.py`) was **cherry-picked onto `main`** so the Project Manager GUI could use
the same queue instead of growing a second one. Merged as `85af9d6`. Consequences:

- **`0418ca6` is redundant here.** On the 2026-08-12 rebase git dropped it automatically
  (*"skipped previously applied commit"*). If a future rebase conflicts on it instead,
  **`git rebase --skip` is the right answer.** Everything after it replays normally.
- **One line differs from this branch's original, deliberately — do NOT revert it.**
  `ingest_raw.py` now queues with `project_id=project_id`, not `proj_id or project_hint`.
  `project_hint` was retired repo-wide on 2026-08-02 and `proj_id` is only bound inside the
  earlier resolve block, so the original was a latent `NameError` on the deferred-link path
  (it survived only because `or` short-circuits when `proj_id` is truthy). Ryan's fix is
  `6276a81`; verified present after the rebase.
- **`pending_links.py` hardening is assigned to `feat/project-manager-gui` — do not
  duplicate it.** It takes no `registry_lock` and uses a non-pid temp name (it mirrors
  `pending_dicom.py`). Fine for one operator, unsafe behind a multi-user GUI. **Coordinate
  before touching that file**; the same concern is logged here as the S7 backlog item.

## 4. Merge gates — still ON THE BOX, but no longer unproven

No `--go` ingest has **ever** run on the box. The 2026-08-05 session stopped at the read-only
`--plan` step. Before merging, prove **on the box**:

| # | Gate | Off-box status |
|---|---|---|
| 1 | A real `--go` producing `.../recon_N` registry rows (one acquisition per reconstruction). | ✅ passes locally (2026-08-07) |
| 2 | A corrected session showing a `session_extra` block in its `metadata.json`. | ✅ passes locally |
| 3 | `registries/pending_links.csv` written with `ENOTSUP` / `darwin` rows. **This file exists on neither NAS today.** | ❌ **box only** — hard links succeed on Windows, so this can only fail-and-queue on the Mac. Runnable **over the tunnel** since 2026-10-01; needs the Mac's `gjesus3` mount up (§0 step 2). |
| 4 | A second sync: idempotent (0 new), and a **late reconstruction registering into an already-corrected session with the correction still applied.** | ✅ passes locally |

Gate 4 is the acceptance test for the persistent-corrections change and is the one most
likely to be got wrong. **It now passes** against a synthetic tree + throwaway NAS
(2026-08-07): `recon_1` added after the fact became `ACQ-20260212-CT-002`, routed to the
*corrected* `AE-biomaGUNE-0325` with `session_extra={tracer,dose}` inherited and **nothing
re-entered**, while `original_name` kept the uncorrected REMI path and the corrections file
was not modified by three `--go` runs.

**A local pass is not a box pass.** What the box still has to prove is everything the Mac
does differently — SMB latency, `ENOTSUP` on `os.link` (gate 3), the real 141-scan tree, and
`resolve_path` landing on the real `gnuclear` mount rather than a fake one. Do not treat
gates 1/2/4 as closed; treat them as *no longer the risky part*.

**Operator instructions are `tools/operator/NI_LIVE_RUNBOOK.md`** — two commands. The old
`RUN_THE_TEST.md` staged at `S:\gnuclear\2026\Jesus\Ryan\ni-live-test\` is a *developer* test
script, is from 2026-06-30, and predates everything below. **Stage a fresh copy of `tools/`
there before the next box session.**

## 5. What landed on this branch (why, not just what)

| Commit | Change |
|---|---|
| `0fb84db` | Dropped `session_id` / `sample_id` from the corrections CSV — both are **derived** for NI, so offering them as editable columns created a competing source of truth. Real damage: a project correction re-derived `project_hint` while a hand-set `sample_id` went stale. Also stopped prompting for condition/anatomy on read-only passes (`--plan` / `--dry-run`), and locked `anatomy.is_whole_body: true` in the live template — Molecubes scans the whole animal every time, so it was never a per-batch question. `condition:` is deliberately NOT defaulted. |
| `1137561` | **Corrections persist** instead of living in a throwaway per-run file. NI reconstructions arrive late and land in sessions that were already corrected, so the old design silently re-applied the *uncorrected* values to those new acquisitions. Stored at `registries/ni_session_corrections.csv` — **superseded below.** |
| (2026-08-07) | **One corrections file per researcher, on `gnuclear`, append-only.** Moved off `gjesus3/registries/` to `<gnuclear>/<year>/<group>/<researcher>/ni_corrections_<researcher>.csv`, and the two-file worksheet→store merge collapsed into a single file the operator owns and edits forever. The merge was the only thing that needed a blank-cell rule; both are gone. `--plan` is now a bare flag that appends unseen sessions and touches nothing else. Path is derived from the running code's own location (no env var, no flag, works on the Mac's `/Volumes/…` mount) and logged every run; an existing file is reused across years so a correction never expires. |
| `6fda90f` | `--root` accepts either the parent of the researcher folder or the folder itself, and **raises** when it matches neither (it used to walk nothing, exit 0, and write a header-only CSV that read as "this researcher has no data" — that cost a slot at the box). Added `NI_LIVE_RUNBOOK.md`. Marked `ni_live_discover.py` a data-office diagnostic, not an operator step. |
| `a7be9d8` | `--plan` no longer walks the source tree twice (`preview_batch` was re-running the identical recursive glob just to display a count `--plan` never prints). **Structural fix, NOT measured on the box** — if `--plan` is still slow there, profile ON the box first. **Do not add a cache.** |
| `46e2120` | Gate-0 closed (see §6), operator-flow plan, on-box test review, production-cleanup list. |

Earlier commits (rebased): one acquisition per reconstruction, `--live` mode (no per-batch
YAML), corrections + tracer metadata. **The deferred-project-links commit is no longer one
of them** — it was cherry-picked onto `main` and is now upstream of this branch (§3a).

## 6. Facts established, don't re-litigate

- **Gate-0 is CLOSED and the answer is NO.** `os.link` on the NI Mac's SMB mount returns
  `ENOTSUP` (tested on the box 2026-08-05, python 3.10.5 darwin). macOS over SMB has no hard
  links. Already handled by deferring to `pending_links.csv`, drained from Windows by
  `tools/relink_pending.py`. This needed no access slot and is **not** a task for the SSH
  tunnel — `NI-RA-05` in `equipment/nuclear-imaging/live_machine_remote_access.md` can close
  against it.
- ~~**Remote access to the box is NOT established.**~~ **Superseded 2026-10-01: it is
  established** — the tunnel is live and the Mac can be operated from the workstation (§0).
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

- ✅ **DONE — the two synthetic production acquisitions are gone.** `ACQ-20260212-CT-001` /
  `-002` (from the 2026-06-29 verification run that pointed `--nas-root` at `J:\gjesus3-data`
  instead of a throwaway NAS) were removed and verified against production on 2026-08-06:
  8 rows across 5 registry CSVs, both raw folders, and the auto-created `PROJ-0051` /
  `AE-biomaGUNE-0325` in full; 0 residual references, 0 `validate_registries` errors; backup
  off-NAS at `C:\Users\rtasseff\temp\gjesus3_ni_testdata_removal_20260806\`. Recorded on `main`
  in `c92a60f`, which this branch now contains. `tasks/ni_prod_testdata_removal.md` is history.
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
