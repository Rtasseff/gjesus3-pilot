# Testing the operator front-ends before handing them to users

This is the data-office rehearsal guide: how to exercise the three operator
front-ends (`ni-ingest`, `mri-ingest`, microscopy GUI) on *your own* machine
before installing them on the real instrument machines. Every step here was run
and verified on Ryan's Windows workstation (2026-06-08).

The golden rule: **commit-tests go into a throwaway "test NAS", never the live
registry.** A dry-run is read-only and safe anywhere; a real `--go` commit
writes raw files, project hard links, and registry rows, so point it at a
disposable NAS root you can inspect and `rm -rf`.

---

## 0. Prerequisites (what must be installed)

| Front-end | Needs | On this workstation |
|---|---|---|
| `ni-ingest`, `mri-ingest` | `pyyaml`, `pydicom`, `tqdm` | already present |
| `mri-ingest --ftp-remote` (optional console pull) | `paramiko` | **not installed** — only needed for the FTP pull; local-path testing doesn't need it |
| microscopy GUI | `flask`, `czifile`, `tifffile`, `numpy` | already present |

Quick check:

```sh
python -c "import yaml, pydicom, tqdm; print('NI/MRI core OK')"
python -c "import flask, czifile, tifffile; print('GUI OK')"
```

To install anything missing: `pip install -r tools/requirements.txt`
(paramiko is listed there; the GUI/PyInstaller extras are commented build-only).

---

## 1. Build a throwaway test NAS (one command)

```sh
python tools/operator/make_test_nas.py --dest C:\Users\<you>\temp\testnas
```

This creates a NAS root with the standard folders, an **empty** `registry_raw.csv`
(header only, so every acquisition you point at is "new" and a full commit is
exercised), and a **copy of the live `registry_projects.csv`** (so a
`project_hint` like `ae-biomegune-0424` resolves to the real `PROJ-XXXX`, just
like production). Add `--force` to reset an existing test NAS.

Tell the tools where it is (or pass `--nas-root` each time):

```powershell
$env:GJESUS3_ROOT = "C:\Users\<you>\temp\testnas"   # PowerShell
```
```sh
export GJESUS3_ROOT="/c/Users/<you>/temp/testnas"   # Git Bash / WSL
```

When you're done: `rm -rf C:\Users\<you>\temp\testnas` and rebuild any time.

---

## 2. Recommended order: preview on live, commit on test

1. **Dry-run against the LIVE NAS** (`--nas-root J:\gjesus3-data --dry-run`).
   Read-only. Confirms the tool reads the real registry, scopes your folder, and
   that already-ingested acquisitions show as *skipped* (idempotency). Because
   the exhibition data is already on the live registry, this typically reports
   "0 new" — that's the point.
2. **Dry-run against the TEST NAS** (`--nas-root <testnas> --dry-run`). Empty
   registry → every acquisition shows as new, so you see the full preview table
   (ACQ-IDs, sample, project, link names).
3. **Real commit against the TEST NAS** (`--go`). Inspect the result, re-run to
   confirm it now skips, then `rm -rf` and move on.
4. Only once you trust it: the real run on the instrument machine against the
   live NAS.

---

## 3. Per-front-end commands (with real local sample data)

Sample data on this workstation:
- MRI ParaVision studies: `D:\projects\gjesus3\data_test` (7 studies, m13–m29)
- NI extracted acquisitions: `D:\projects\Nuke\test_data` (PET/CT folders)
- microscopy `.czi`: **not local** — lives on the `S:`/`K:` shares; point the GUI
  at a mapped-drive `.czi` batch.

### MRI (`mri-ingest`)

```sh
# full batch-root preview against the test NAS (37+ exams across studies)
python tools/operator/mri_ingest.py D:\projects\gjesus3\data_test \
    --nas-root C:\Users\<you>\temp\testnas --model 7T --dry-run

# single study, real commit
python tools/operator/mri_ingest.py D:\projects\gjesus3\data_test\20251016_083822_jrc_251016_m17_0424_jrc_251016_m17_0424_1_1 \
    --nas-root C:\Users\<you>\temp\testnas --model 7T --go
```

Scope auto-detects single exam / study folder / batch root. The two per-run
knobs are `--model 7T|11.7T` and `--reconstructions all|3|1,3`. Verified: a study
folder ingests every exam with distinct ACQ-IDs even when exam numbers repeat
across studies (the dedup key keeps `<study>/<exam>`).

### Nuclear Imaging (`ni-ingest`)

```sh
# single acquisition, real commit (fast — small payload)
python tools/operator/ni_ingest.py D:\projects\Nuke\test_data\irene_0525_251029_0525_m13_20251029100311_PET \
    --nas-root C:\Users\<you>\temp\testnas --go

# whole batch root, preview only
python tools/operator/ni_ingest.py D:\projects\Nuke\test_data \
    --nas-root C:\Users\<you>\temp\testnas --dry-run
```

Point at one extracted acquisition or a batch root. `.tgz` archives must be
extracted first (`tools/extract_ni_archives.py`); the tool says so if you point
at one. Live (non-extracted) folders are not wired up yet — archive mode only.

A successful commit shows, per acquisition: a `subject: DB hit ...` line (the
animal-facility lookup), `condition`/`anatomy` WARN lines (null sentinels — they
warn but never block), the registry append, and the project hard-link creation.

### Microscopy GUI

```sh
python tools/operator/gui/app.py            # opens http://127.0.0.1:5000 in your browser
python tools/operator/gui/app.py --no-browser --port 5057   # headless (for a smoke test)
```

In the browser: set the NAS-root box to your **test NAS**, pick an instrument +
recipe (the AxioScan 7 recipe ships seeded), point the folder box at a `.czi`
batch, **Preview**, then **Ingest** (leave the Dry-run checkbox on for a no-write
rehearsal first). Verified headless: the app boots, serves the page, and returns
the instrument list + seeded recipe. The full preview/ingest needs a real `.czi`
batch on a mapped drive. (The packaged `.exe` is built separately — see
[`gui/README.md`](gui/README.md).)

---

## 4. Windows vs WSL — which to use

The two command-line tools are **pure Python and cross-platform**, so testing
them under Windows Python (as above) validates all the logic, scoping, preview,
and commit behaviour quickly. Their real deployment target is **Linux**, so
before installing on an instrument machine it's worth one **WSL pass** to catch
anything platform-specific:

```sh
# in WSL, with the deps installed there too:
export GJESUS3_ROOT=/mnt/c/Users/<you>/temp/testnas
python3 tools/operator/ni_ingest.py /mnt/d/projects/Nuke/test_data/<acq> --dry-run
```

The thing a WSL pass catches that Windows can't: **hard-link creation onto the
mounted NAS**. `os.link` behaves differently on a Linux CIFS/SMB mount than on
Windows-native `J:\`; if project links fail on the real Linux machine, that's
where it shows up. (On the instrument machines the NAS is mounted at
`/mnt/gjesus3`.)

The microscopy GUI's target is **Windows** — test it on Windows.

---

## 5. Cleanup

```sh
rm -rf C:\Users\<you>\temp\testnas
```

Nothing here touches the live `J:\gjesus3-data` registry as long as every `--go`
used a `--nas-root` pointing at the test NAS. If you ever do want a real commit
into the live (currently non-production) NAS, just point `--nas-root` at
`J:\gjesus3-data` — but do that deliberately, not as part of a test loop.
