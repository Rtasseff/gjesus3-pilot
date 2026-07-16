# Handoff — the frozen GUI `.exe` cannot generate `README.txt` (packaging / resource-path bug)

**Branch:** `fix/gui-frozen-exe-resources` · **Worktree:** `…/projects/gjesus3-dev/gui-frozen-exe-fix`
**Base:** `main` @ `6ded455` · **Author of this brief:** prior session (permissions-issue investigation, 2026-07-16)
**Status of the fix:** NOT started — this document is the design + context. Implement, rebuild the exe, redistribute.

---

## 0. TL;DR — what to do

The packaged operator GUI (`gjesus3_ingest.exe`, both the microscopy `/` and MRI `/mri` pages)
**crashes on every real ingest** at the README-generation step, because a template file it needs
(`tools/templates/README_raw.txt`) is not bundled into the exe **and** the code that loads it is not
PyInstaller-aware. This has been true since the exe was first frozen (2026-06-24) — it has never
worked from the frozen build; it only ever worked when run from a source checkout. It surfaced now
because 2026-07-16 was the first genuine committed ingest pushed through the `.exe` against the live NAS.

Ordered work:

1. **Add a frozen-aware resource resolver** to the `ingest/` layer (mirroring the one that already
   exists in `tools/operator/templates.py`) and route the two naive template loaders through it —
   `tools/ingest/readme.py` (the hard crash) and `tools/create_project.py` (a latent, currently-silent
   second instance). §4.1–4.2.
2. **Bundle the two missing template files** in the PyInstaller spec so they exist inside the exe. §4.3.
3. **Rebuild the exe, redistribute** to the operator machines, and **smoke-test through the exe** (a unit
   test can't exercise `sys._MEIPASS`; only running the frozen build proves it). §5.
4. **Out of scope / tabled by Ryan:** the rollback-needs-*modify*-permission design question. §6. Do not
   change the ACL model or the rollback logic under this branch.

The 15 orphaned `/raw/` folders from the failed session are **already cleaned up** — see §7. Nothing to do there.

---

## 1. The symptom the operator saw

User `ifernandez` ran the **MRI GUI** ingest (15 exams). Her machine has the correct animal-facility + MRI
credentials, Read on all of `\\gjesus3\gjesus3\gjesus3-data\`, **write-but-not-modify** on `raw\`, and
write+modify on `projects\`. Every one of the 15 exams failed **identically**. Representative tail:

```
[INFO] MRI slim copy complete: 30 DICOM(s) under ACQ-20260706-MRI-015.data/
[INFO] Copied + verified 30 files
[INFO] Wrote checksums.json (30 files)
[INFO] subject: DB hit 6-AE-biomaGUNE-1125
[INFO] Wrote metadata.json
[ERROR] Ingest failed after copy, before the registry commit (ACQ-20260706-MRI-015):
        [Errno 2] No such file or directory:
        'C:\Users\IFERNA~1\AppData\Local\Temp\_MEI259042\templates\README_raw.txt'
[WARN] Could not roll back \\gjesus3\...\ACQ-20260706-MRI-015:
        [WinError 5] Access is denied: '...\ACQ-20260706-MRI-015.data\recon1_frame01.dcm'
```

**There are two distinct failures here, and only the first is this branch's job:**

- **`[ERROR]` — the crash (THIS branch).** A `FileNotFoundError` opening `…\_MEI259042\templates\README_raw.txt`.
  `_MEI259042` is the PyInstaller onefile unpack dir (`sys._MEIPASS`). This is a **packaging / resource-path
  bug**, wholly independent of permissions — it fails for any user on the frozen exe.
- **`[WARN]` — the rollback (TABLED, see §6).** After the crash, the pipeline tried to delete the partial
  `/raw/` folder it had just written. Deleting requires the *Delete* right (part of *Modify*); `ifernandez`
  has write-but-not-*modify* on `raw\`, so cleanup was refused. This is a real design tension but Ryan has
  explicitly parked it. **Do not touch it under this branch.**

Note the log prints `Wrote metadata.json` (Step 8) but never `Wrote README.txt` (Step 9) — the failure lands
exactly on the README step.

---

## 2. Root cause

### 2.1 The crash path
- `tools/ingest_raw.py:1258` (Step 9 of `ingest_single`) calls `readme.generate_readme(...)` unconditionally
  for **every** ecosystem — microscopy and MRI both hit it.
- `tools/ingest/readme.py:7-13` resolves the template with a naive path:
  ```python
  def get_template_path():
      return os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "README_raw.txt")
  ```
  It then does an **unguarded** `open(template_path)` (`readme.py:25-27`).
- In a source checkout, `__file__` is the real repo path → resolves to `…/tools/templates/README_raw.txt` → works.
- In the frozen exe, the `ingest` package is unpacked under `sys._MEIPASS`, so `__file__` is
  `<_MEIPASS>\ingest\readme.py`; `dirname(dirname(__file__))` is `<_MEIPASS>`; the loader looks for
  `<_MEIPASS>\templates\README_raw.txt`. That file **is not in the bundle** → `FileNotFoundError` → the
  `ingest_single` try/except (`ingest_raw.py:1374`) reports "Ingest failed after copy, before the registry commit".

### 2.2 Two compounding facts, both verified in git
- **`README_raw.txt` has never been in the PyInstaller spec.** `git log -S "README_raw" -- tools/operator/gui/gjesus3_ingest.spec`
  returns nothing across all history. The spec's `datas` bundles `templates/instruments/` and
  `templates/ingest_template.yaml`, but not `README_raw.txt` (nor `project.yaml`). (`gjesus3_ingest.spec:47-62`.)
- **The spec was first created 2026-06-24** (`61c9f2c build(gui): freeze spec for BOTH pages`). Before that
  there was no frozen exe. So the frozen build has been broken for README generation since day one.

### 2.3 Why microscopy "seemed to work" (Ryan's confirmation)
Because `readme.generate_readme` is shared and unconditional, the frozen exe fails **identically for
microscopy and MRI**. Ryan confirmed: his earlier microscopy validation was **run from the source checkout**
(where the naive path resolves) and at most a **dry-run on the frozen build** (dry-run/preview never reaches
Step 9's copy-then-commit). The 2026-07-16 MRI run was the **first real committed ingest through the frozen
exe**, which is why the latent bug first bit then. There is no microscopy-vs-MRI code difference here.

### 2.4 The precedent that shows the correct shape
`tools/operator/templates.py` already solves exactly this problem for the per-instrument YAML templates —
which is why `mri_bruker.yaml` loads fine inside the exe. Its `_candidate_dirs()` (`templates.py:54-71`) is
`sys._MEIPASS`-aware: it tries `<_MEIPASS>/tools/…`, then `<_MEIPASS>/…`, then the source-checkout dir. The
`ingest/` layer simply never got the same treatment. **Follow this precedent** rather than inventing a new mechanism.

### 2.5 The full inventory of frozen-unaware resource reads
A sweep of `tools/` for naive `dirname(__file__)`-relative resource loads found exactly two, both reading from
`tools/templates/`:

| File / line | Loads | Behaviour in frozen exe | Severity |
|---|---|---|---|
| `tools/ingest/readme.py:7-27` | `templates/README_raw.txt` | **unguarded `open()` → hard crash** | the bug ifernandez hit |
| `tools/create_project.py:163-174` | `templates/project.yaml` | **guarded** (`if os.path.exists(): … else: inline fallback`) → no crash, but writes a **non-templated `_project.yaml`** | latent fidelity gap |

`create_project.py` is reached during ingest only when `ingest.auto_create_projects: true` and the project is
new (`ingest_raw.py:1285-1317`). It doesn't crash today, but it silently produces a degraded `_project.yaml`
in the exe. Fix both in one pass so the next person doesn't rediscover this.

`tools/templates/` contains exactly three files: `README_raw.txt`, `project.yaml`, `ingest_template.yaml`
(the last is already bundled). So bundling the first two closes the set.

---

## 3. Recommended solution

Fix the **class** (frozen-unawareness in `ingest/`), not just the one crash — the second instance is already
sitting there.

### 3.1 Add a shared frozen-aware resolver
New helper, mirroring `templates._candidate_dirs`. Place it where **both** the top-level
`tools/create_project.py` and the `tools/ingest/` package can import it — e.g. a new `tools/ingest/resources.py`,
which `create_project.py` imports as `from ingest import resources` (`tools/` is already on `sys.path` in both
the CLI and the frozen exe; see the `sys.path.append(_TOOLS_DIR)` note in `templates.py:24-37`):

```python
# tools/ingest/resources.py  (new)
"""Resolve bundled data files both from a source checkout and a frozen PyInstaller exe.
The ingest/ layer was not _MEIPASS-aware; operator/templates.py already is. This gives
ingest/ (and create_project.py) the same dual-mode resolution.
Args are relative to the repo `tools/` dir, e.g. resource_path("templates", "README_raw.txt")."""
import os
import sys

def resource_path(*relparts):
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(os.path.join(meipass, "tools", *relparts))  # spec maps -> tools/…
        candidates.append(os.path.join(meipass, *relparts))           # or stripped
    tools_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # tools/
    candidates.append(os.path.join(tools_dir, *relparts))
    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[-1]  # source path so a caller error names the dev-facing location
```

### 3.2 Route the two loaders through it
- `readme.py`: `get_template_path()` → `return resources.resource_path("templates", "README_raw.txt")`.
  Keep the `open()` but consider a clear error if the returned path still doesn't exist (so a future bundling
  regression fails legibly, not with a bare Errno 2).
- `create_project.py:163-164`: build `template_path` via `resources.resource_path("templates", "project.yaml")`.
  The existing `os.path.exists` guard + inline fallback can stay as a belt-and-braces safety net.

### 3.3 Bundle the two files in the spec
In `tools/operator/gui/gjesus3_ingest.spec`, extend `datas` (both files confirmed to exist):
```python
(os.path.join(TOOLS, "templates", "README_raw.txt"), os.path.join("tools", "templates")),
(os.path.join(TOOLS, "templates", "project.yaml"),   os.path.join("tools", "templates")),
```
These land at `<_MEIPASS>/tools/templates/…`, matched by the resolver's first candidate.

### 3.4 Minimal alternative (if you want the smallest possible diff)
Make **only** `readme.py` frozen-aware and bundle **only** `README_raw.txt`. Fixes the crash ifernandez hit;
leaves `create_project.py`'s silent fidelity gap for later. Not recommended — it's barely smaller and leaves a
known second instance of the identical bug.

---

## 4. Why this directly unblocks the write-but-not-modify user

Once README generation succeeds, the ingest **completes normally** — it reaches the registry commit, so the
rollback path is never entered. Therefore a **write-but-not-modify** operator (ifernandez) needs **no modify
right** for the happy path. Fixing this packaging bug is what actually unblocks her; it is not a permissions
change. (Modify only becomes relevant if some *other* pre-commit failure occurs and triggers rollback — see §6.)

---

## 5. Verification / release

1. Unit-ish: assert `resources.resource_path("templates", "README_raw.txt")` returns an existing file in a
   source checkout, and that `readme.get_template_path()` uses it.
2. **The real proof is the frozen build.** Rebuild the exe from `tools/operator/gui/gjesus3_ingest.spec`
   (PyInstaller). Then run one MRI exam **and** one microscopy item end-to-end **through the rebuilt `.exe`**
   to a scratch target, and confirm: `README.txt` is written in the acq folder, the registry row commits, and
   (for an `auto_create_projects` batch) `_project.yaml` is the templated form, not the inline fallback.
3. Redistribute the rebuilt exe to the operator machines. Note the build/redistribute steps in
   `tools/operator/gui/README.md`.

---

## 6. Out of scope — the rollback vs. immutability ACL (Ryan is tabling this)

When a pre-commit failure fires, `_rollback_uncommitted` (`ingest_raw.py:129-147`, invoked at `:1383-1389`)
does `shutil.rmtree(dest_dir)` to remove the partial `/raw/` write. Under write-but-not-modify that deletion is
denied, stranding an orphan folder that only a superuser can remove. **This is working as designed** — the
2026-07-08 architecture review deliberately *strengthened* this rollback to clean up partial folders at more
failure points (commit `911f69e`), and the immutability ACL deliberately withholds modify/delete on `raw\`.
The two are in tension. Ryan wants to think about the resolution separately (options include: a superuser-run
cleanup tool for pre-commit orphans; granting operators delete-only on their own just-written files; a
staging-then-promote ingest so `/raw/` is only ever written once atomically). **Do not implement any of these
here.** This branch only needs to stop the crash so the rollback path stops being exercised in normal use.

---

## 7. Already done (no action needed)

- The **15 orphaned `/raw/` folders** (`ACQ-20260706-MRI-001` … `-015`) from ifernandez's failed session were
  deleted and verified gone on 2026-07-16 (each safety-checked against `registry_raw.csv` first — none were
  registered, since the failures were all pre-commit). `/raw/DICOM/2026/2026-07/` is clean.
- The source MRI data for those exams is the same kenia data already staged for the separate DICOM-regen
  backfill work; nothing to re-pull for this fix.

---

## 8. File / line reference

| Path | Lines | Role |
|---|---|---|
| `tools/ingest/readme.py` | 7-13, 25-27 | naive template path + unguarded `open()` — **the crash** |
| `tools/ingest_raw.py` | 1258 | Step 9 `readme.generate_readme(...)` call site |
| `tools/ingest_raw.py` | 1374-1382 | the try/except that reports the failure |
| `tools/ingest_raw.py` | 129-147, 1383-1389 | `_rollback_uncommitted` + its `finally` — the **tabled** rollback (§6) |
| `tools/create_project.py` | 163-174 | second naive read (`project.yaml`), guarded fallback |
| `tools/ingest_raw.py` | 1285-1317 | where ingest reaches `create_project` (auto-create) |
| `tools/operator/templates.py` | 54-71 | `_candidate_dirs` — the frozen-aware **precedent to mirror** |
| `tools/operator/gui/gjesus3_ingest.spec` | 47-62 | `datas` — where the two files must be added |

Git evidence: spec born `61c9f2c` (2026-06-24, "freeze spec for BOTH pages"); `README_raw.txt` never appears
in the spec's history; `readme.py` unchanged in behaviour since `a30820d`/`34ac961`. The strengthened rollback
is `911f69e` (2026-07-08 review follow-through, already merged to `main`).
