# NI live sync — the operator flow a researcher will actually use (item 6)

> **Status: §3.1–3.5 BUILT 2026-08-06** on branch `feat/ni-live-hardening` (rebased onto
> `main` `dde99fc`). All NI suites green. **What remains before merge is not more code —
> it is running the thing on the box** (§5 gates).
>
> | § | What | State |
> |---|---|---|
> | 3.1 | Review step retired from the operator path | ✅ `6fda90f` |
> | 3.2 | `--root` accepts either form; fails loudly on neither | ✅ `6fda90f` |
> | 3.3 | `--plan` no longer walks the tree twice | ⚠️ `a7be9d8` — **structural fix only, NOT measured on the box.** If still slow, profile ON the box before changing anything else. Do not add a cache. |
> | 3.4 | Persistent corrections store (D6 reversal) | ✅ `1137561` |
> | 3.5 | Operator runbook replacing RUN_THE_TEST.md | ✅ `6fda90f` — `tools/operator/NI_LIVE_RUNBOOK.md` |
>
> Earlier: items 4 + 5 (drop derived columns, kill read-only prompts) `0fb84db`.
>
> **Not done and deliberately so:** the §5 merge gates. No `--go` ingest has ever run on
> the box, so `pending_links.csv` still does not exist on any NAS and no `.../recon_N` row
> or `session_extra` block exists outside a synthetic tree.
>
> **Context that must not be lost:** this branch's whole purpose is a tool researchers use
> at the NI box to sync their own data. Everything else on it is plumbing. The 2026-08-05
> on-box test proved the plumbing runs on the Mac and proved the flow is unusable.

## 0. The standing constraint — read this first

**Do not increase complexity.** The user's words, 2026-08-06: *"I keep trying to avoid
over engineering but that is all we seem to do here. The tool and system is barely used
because it is so complex."* Reducing complexity overall is a separate, larger job. **Here
the bar is: do not add to it.** Every change below is a removal or a merge of existing
steps. If a step in this plan turns into "add a new mode/flag/file", stop and re-think it.

## 1. What is wrong today (all observed, 2026-08-05, not theorised)

The operator ran `RUN_THE_TEST.md` — a **6-step developer test script**. It was never
written as operator instructions, but nothing simpler exists. The user's verdict:

> *"If that crazy list of things I was doing to test the code we wrote is the final
> instructions for the researchers and operators, then we can go home right now and stop
> because they are not going to do all that."*

Concretely:

| # | Problem | Evidence |
|---|---|---|
| 1 | **Two discovery artifacts, overlapping.** `ni_live_discover.py` writes `review_irene.csv` (141 rows, one per *acquisition*, read-only, not editable) and `ni_ingest --live --plan` writes `corrections_irene.csv` (75 rows, one per *new session*, editable). The operator asked what the review step is even for. | Both files in `S:\gnuclear\2026\Jesus\Ryan\ni-live-test\` |
| 2 | **Inconsistent path argument.** `ni_live_discover.py --root` wants the **parent** of the researcher folder (it appends `who`); `ni_ingest --live` is pointed **at** the researcher folder. Worse, the wrong form **exits 0 with a header-only CSV** instead of erroring — and `molecubes_ni_live.yaml:12` documents the broken form. | Logged as §0.3 in `ni_live_operator_plan.md`, still unfixed |
| 3 | **`--plan` is slow** (~2 min: `16:41:45` → `16:43:46`) for a read-only pass that writes one small CSV. | Operator's `notes.txt` |
| 4 | **Corrections do not persist.** Locked decision **D6** chose a per-run file passed via `--corrections`. But NI reconstructions arrive late and land in **already-corrected sessions**, so a later sync silently re-applies the *uncorrected* REMI values. The old plan documented this as a "known wrinkle"; the user has now **reversed D6** — see §2. | `ni_live_operator_plan.md` §3.2/3.3 (D6) |
| 5 | **Commands are not cheap.** The operator wants something close to "just the researcher name". | User, 2026-08-06 |

## 2. DECISION REVERSED — D6: corrections must persist (user, 2026-08-06)

> *"the corrections are saved from one run to another right? we did a whole thing about how
> if new reconstruction files are added (new acquisitions we need) to existing sessions we
> can sync them to the existing session, which means the corrections for that session need
> to be somewhere?"*

**D6 (per-run correction file) is dead. Corrections live on the NAS, keyed by
`session_path`, and are applied automatically.**

This is both more correct *and* simpler for the operator — they never re-enter a fix, and
the `--corrections` flag disappears from the everyday command. It is a removal, not an
addition.

Rationale to preserve: recon indices are **append-only** on the box (confirmed NI
behaviour), so `<anchor>/recon_<idx>` is a stable dedup key and a late reconstruction is
automatically a *new* acquisition in an *existing* session. That session's correction must
therefore outlive the run that made it.

## 3. Target flow — two commands, then one

**Today (6 steps).** discover → review CSV → plan CSV → edit → dry-run → ingest.

**Target (2 steps, steady state 1):**

```
ni-ingest <my-folder> --plan          # read-only: what's new + a worksheet of anything unfixed
#   ... operator edits the worksheet only if something is wrong ...
ni-ingest <my-folder> --go            # ingests; stored corrections apply automatically
```

In steady state — nothing new to correct — it is **one command**. The worksheet is only
touched when the parse got something wrong or a tracer needs recording.

### 3.1 Retire the separate review step (removal)
`ni_live_discover.py` becomes a **developer/diagnostic** tool, not an operator step. Its
per-acquisition survey is genuinely useful for us (it is how we saw the 141/75 split and
the transposed-date sessions) but it is not a researcher artifact. **Do not delete it** —
drop it from the operator path and say so in its `--help` and in the runbook.

The `--plan` worksheet becomes the single operator-facing artifact.

### 3.2 One path argument, and make the wrong one fail loudly (fix)
Accept **either** the researcher folder or its parent, in **both** tools, by detecting
which one was given. Never exit 0 with a header-only CSV. Fix the documented-broken form
at `molecubes_ni_live.yaml:12`.

### 3.3 Make `--plan` fast (investigate before optimising)
Unmeasured — **profile first, do not guess.** `--plan` currently calls the full
`preview.preview_batch(cfg, nas_root)`, which does discovery + registry dedup + full
registry resolution for every case, then `_write_plan` throws nearly all of it away and
keeps one row per *session*. Likely candidates: per-case sidecar reads, and the registry
dedup check re-reading `registry_raw.csv`. **Acceptance: `--plan` on Irene's ~141-scan tree
finishes in well under 30 s.** If it turns out to be dominated by an unavoidable SMB walk,
say so and stop — do not add a cache.

### 3.4 Persistent corrections store (the D6 reversal)
- **Where:** on the NAS beside the other worklists — `registries/ni_session_corrections.csv`.
- **Key:** `session_path` (the raw `<series>/<date>/<subject>` relpath) — the same key
  already used, and deliberately the *uncorrected* REMI path so identity never moves.
- **Columns:** exactly today's post-item-4 set — `session_path`, `project`,
  `animal_codes`, `extra_metadata`. **Do not re-add `session_id` / `sample_id`**; they are
  derived and were removed in `0fb84db` for causing stale values in production.
- **Write path:** `--plan` emits only sessions **not already in the store**; on ingest, an
  edited worksheet is **merged into** the store (upsert on `session_path`).
- **Read path:** every `--live` run loads the store and applies it automatically. The
  explicit `--corrections <file>` flag stays as an override for one-off use, but is no
  longer part of the normal flow.
- **Reuse, do not reinvent:** follow `tools/ingest/pending_links.py` / `pending_dicom.py`
  exactly — BOM-tolerant via `tools/ingest/csv_safe.py`, header-checked, atomic
  temp+replace, idempotent on key, status preserved. Serialize with
  `tools/ingest/locking.py` if it is written during an ingest.

### 3.5 A real operator runbook (replaces RUN_THE_TEST.md)
One page, two commands, written for a researcher. `RUN_THE_TEST.md` stays where it is as a
developer artifact. If the SSH tunnel lands, this gets much easier to iterate on — but it
is **not** a prerequisite.

## 4. Explicitly NOT in scope here
- **The GUI (§3.6 of the old plan).** Still last, still backlogged. Do the CLI first.
- **The ID/ISA vocabulary question** (what `1207` is). Documentation + backlog, tracked
  separately — it does not block this flow.
- **`pending_dicom_regen` header drift**, **`new recon/` folder depth**, **the unified
  backfill checker.** All backlog (user, 2026-08-06: *"we are too far behind"*).
- **Re-ingesting the sandbox 122.** Test data; not a merge gate.

## 5. Merge gates — what must be true before `feat/ni-live-hardening` lands
None of these exist yet (the on-box run stopped at `--plan`):

1. A real `--go` ingest on the box producing `.../recon_N` rows (per-recon, Tier B).
2. A corrected session showing `session_extra` in its `metadata.json` sidecar.
3. `registries/pending_links.csv` written with `ENOTSUP` / `darwin` rows — the §1 feature
   doing its job where hard links cannot exist. *(This file does not currently exist on
   either NAS — the feature has never written a row in a real environment.)*
4. A second sync proving idempotency (0 new) and a late reconstruction registering as a
   new acquisition in an already-corrected session **with the correction still applied** —
   this is the D6 reversal's acceptance test.

## 6. Working state (2026-08-06)
- Branch `feat/ni-live-hardening`, rebased onto `main` `dde99fc`. **0 behind / 8 ahead.**
- Backup tag `backup/ni-live-hardening-pre-rebase` = pre-rebase `f2ee114`.
  **`origin/feat/ni-live-hardening` still points at the OLD pre-rebase commits** — the next
  push needs `--force-with-lease`, and pushing requires explicit user permission.
- All NI suites green after rebase: `test_ni_corrections`, `test_ni_per_recon`,
  `test_pending_links`, `test_ni_live_discover`, `ingest/test_registry_fields`.
- Uncommitted in the tree and **not ours** — the paused historical-pull work
  (`equipment/historical_data_archives.md`, `tasks/archive/tasks.md`,
  `equipment/nuclear-imaging/gnuclear_active_workspace_layout.md`,
  `tasks/ni_gnuclear_active_space_plan.md`). **Do not stage or commit these.**
- Two synthetic acquisitions are in **true production** from a 2026-06-29 verification run;
  removal list ready at [`ni_prod_testdata_removal.md`](ni_prod_testdata_removal.md),
  **handed off, not executed here.**
