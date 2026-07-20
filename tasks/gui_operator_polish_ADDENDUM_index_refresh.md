# ADDENDUM to the operator-GUI-polish handoff — per-project Finder refresh on ingest

**Branch:** `feat/gui-operator-polish` · **Added:** 2026-07-20 · **By:** the index-refresh
(issue 1) session.

> Read [`gui_operator_polish_handoff.md`](gui_operator_polish_handoff.md) first — that is
> the original brief (issues 2/3/4), already implemented + verified from source; its only
> remaining step is the production exe rebuild/redeploy. **This addendum adds ONE more
> code item to fold in BEFORE that rebuild, so a single rebuild ships everything.** It does
> not change anything in the original doc.

---

## Why this is here

Separately from the GUI polish, we reworked how the researcher **Finder** stays fresh
(issue 1 from the same operator test). Root cause: the auto-refresh lived only in
`ingest_raw.main()`, but the GUI calls the ingest functions directly and bypasses it — so
**GUI ingests never refreshed the index at all** (that's why a researcher saw their upload
missing from the project index). Rebuilding the whole ~18 MB global index on every ingest
is also too heavy and race-prone, so we split it:

- **Global index** → a **scheduled job** (already built + documented on `main`).
- **CLI ingest** → opt-in via `--refresh-index` (already on `main`).
- **Per-project index** → refreshed on ingest, targeted to just the touched project. **The
  GUI half of that is this addendum.**

The foundation is already on `main` (merge it in — see step 0):
- `generate_index.py` gained a **targeted `--project ID`** mode: regenerates only that
  project's `index.html`, skipping the global rebuild. `ID` matches a PROJ-id, short_name,
  or folder name. (Verified against the live registry.)
- `ingest_raw.py` gained `--refresh-index {none,projects,full}` (default `none`) and a
  helper `_touched_project_hints(acq_ids, nas_root)` that maps a run's acq_ids → their
  project `PROJ-ids` from the registry.
- `tools/scheduled_finder_refresh.bat` + `tools/FINDER.md` → "Keeping it fresh" describe
  the model and the scheduled job.

Note the key fact: the registry's **`project_hint` column stores the resolved `PROJ-XXXX`
id** (not a slug), so the targeted refresh keys on the PROJ-id.

---

## The work (one item)

### 0. Merge `main` first
This branch was cut before the foundation landed. Bring it in so `generate_index.py`'s
`--project` mode and `find_acq.py` are present:
```
git merge main
```

### 1. After a successful GUI ingest, refresh the touched project's index
Both GUI ingest paths (microscopy `/api/ingest` and MRI `/api/mri/ingest`) funnel through
`_ingest_sse_response(...)` → its inner `worker()` in `tools/operator/gui/app.py`. There,
`results = runner.run(...)` returns a list of `(acq_id, ok)` tuples and `ok`/`total` are
computed. Add a **best-effort, non-fatal** per-project refresh right after a successful
non-dry-run ingest (before or after the `done` event — just not on the failure path):

```python
# after: ok = sum(1 for _aid, good in results if good) ; total = len(results)
if not dry_run and ok > 0:
    try:
        import ingest_raw, generate_index
        aids = [aid for aid, good in results if good and aid]
        hints = ingest_raw._touched_project_hints(aids, nas_root)  # distinct PROJ-ids
        for h in hints:
            generate_index.main(["--nas-root", nas_root, "--project", h])
        if hints:
            cb(f"Refreshed Finder index for project(s): {', '.join(hints)}")
    except Exception as e:  # never fail an ingest over an index refresh
        cb(f"Project index refresh failed (non-fatal): {e}", "WARN")
```

Notes:
- Reusing `ingest_raw._touched_project_hints` keeps the "which project(s)?" logic in one
  place and correctly handles a batch that spans **multiple** projects and an ingest that
  **auto-creates** a new project (the new PROJ-id is in the registry by the time this runs).
  If you'd rather not import the big `ingest_raw` module here, inline the same ~10-line
  registry lookup — but keep the behavior identical.
- This regenerates ONLY the touched project(s)' `index.html`. It must **never** rebuild the
  global index (that's the scheduled job's job) — do not pass `--per-project` or a bare
  global run.
- `cb(...)` is the existing SSE log callback in `worker()`; use it so the operator sees the
  refresh line in the live log.

### 2. Bundle the two modules in the PyInstaller spec
The frozen exe currently does NOT bundle `generate_index.py` / `find_acq.py`, so the import
in step 1 would fail in the packaged build (silently caught → no refresh). In
`tools/operator/gui/gjesus3_ingest.spec`, mirror how `ingest_raw.py` is bundled:
- add to `datas`: `(os.path.join(TOOLS, "generate_index.py"), "tools")` and
  `(os.path.join(TOOLS, "find_acq.py"), "tools")`;
- add to `hiddenimports`: `"generate_index"`, `"find_acq"`.
(`ingest_raw` and the `ingest` package are already bundled/hidden-imported.)

### 3. Rebuild ONCE — covering issues 2/3/4 AND this
Do the single `pyinstaller tools/operator/gui/gjesus3_ingest.spec` rebuild + backup-first
redeploy + frozen smoke-test that the original handoff §5 describes, **after** this item is
in. Add to that smoke-test: a real GUI ingest into a project → confirm **that project's**
`index.html` on the NAS updates (fresh "generated" timestamp + the new acq is searchable in
it), and that the **global** `registries/index.html` is left alone by the GUI.

---

## Out of scope
- The scheduled global refresh and the CLI `--refresh-index` flag are already on `main` —
  nothing to do here for them. (The data office registers the Task Scheduler job separately;
  `tools/FINDER.md` → "Keeping it fresh" has the `schtasks` command.)
- Do not touch `project_hint` naming — that's branch `refactor/project-naming` (P), which
  rebases after this branch merges.

## Done when
- [x] `main` merged in; `generate_index.py --project` available on the branch.
      *(Merged `main` @ `12d7aa0`; one conflict in `GLOSSARY.md` resolved — kept the new
      RDM-System bullet + main's reworded `ingest`/Finder bullet.)*
- [x] GUI worker refreshes the touched project(s)' index after a real ingest (both `/` and
      `/mri`), non-fatally, never rebuilding the global index. *(One edit in
      `_ingest_sse_response`'s `worker()` — both pages funnel through it. `if not dry_run and
      ok > 0`, reuses `ingest_raw._touched_project_hints`, targeted `--project` only, wrapped
      so a refresh failure only WARNs.)*
- [x] Spec bundles `generate_index.py` + `find_acq.py`; hiddenimports updated.
- [ ] One rebuild ships issues 2/3/4 + this; frozen smoke-test confirms the project index
      updates on a GUI ingest. *(Ryan — the single production rebuild/redeploy per §3.)*

---

## Implementation note (2026-07-20 session)

Folded into `feat/gui-operator-polish` on top of the issue-2/3/4 work; **not yet merged/deployed**.
Verified from source (no frozen build, no live NAS):
- `app.py` imports cleanly post-merge; `ingest_raw._touched_project_hints`,
  `generate_index.main`, and `find_acq.build_records` all resolve in the app's runtime
  `sys.path` context.
- **End-to-end against a throwaway NAS** (minimal `registry_raw.csv` + `registry_projects.csv`
  + a project folder): `_touched_project_hints(['ACQ-TEST-001','ACQ-NOPE'], nas)` →
  `['PROJ-9001']`; `generate_index.main(['--nas-root', nas, '--project', 'PROJ-9001'])` wrote
  **only** the project's `index.html` (acq present), left the **global**
  `registries/index.html` untouched, rc 0.
- Issues 2/3/4 unregressed after the merge (14 link tokens; both pages render with zero
  operator-visible "NAS" + the completion modal wired).
- **Still needs the frozen smoke-test** (§3): confirm the packaged build's import path finds
  the two newly-bundled modules, and that a real GUI ingest updates the touched project's
  `index.html` on the NAS while leaving the global index to the scheduled job.
