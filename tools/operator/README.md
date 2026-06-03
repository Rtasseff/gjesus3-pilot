# Operator self-service ingest — `tools/operator/`

This is the **no-YAML** way for operators to ingest their own data, running the
exact validated pipeline the data office uses. Three thin front-ends sit over
one shared core; none of them reimplements ingest logic.

| You are... | Use | Platform |
|---|---|---|
| an **MRI** (Bruker ParaVision) operator | `mri-ingest` (command line) | Linux acquisition machine |
| a **Nuclear Imaging** (Molecubes PET/CT) operator | `ni-ingest` (command line) | Linux acquisition machine |
| a **microscopy** operator (AxioScan 7 / Cell Observer / LSM 900) | the **microscopy GUI** (`.exe`, opens in your browser) | Windows |

If you would rather hand-edit a YAML config (the data-office path), that still
works — see [`mfb-rdm-docs/11_OPERATIONS.md §3.2`](../../mfb-rdm-docs/11_OPERATIONS.md)
and [`tools/INGEST_CLI.md`](../INGEST_CLI.md). This page is the simpler
point-at-a-folder path.

Design and build plan: [`tasks/operator_ingest_tooling_plan.md`](../../tasks/operator_ingest_tooling_plan.md).

---

## What is the same for everyone

- **Always preview first.** Every front-end shows you a "what will happen" table
  (one row per acquisition: the ACQ-ID, sample, project, link name, file count)
  *before* anything is written. Look it over, then confirm.
- **Safe to re-run.** The pipeline is idempotent — if you point it at the same
  folder twice, acquisitions already in the registry are skipped, not
  duplicated. A re-run after a hiccup is fine.
- **You point at a folder, the tool knows the rest.** Each front-end already
  knows which instrument it is and loads that instrument's locked-in conventions
  (the per-instrument template). You do not write any YAML.
- **The NAS must be mounted, and the tool must know where.** See the next
  section.

### Tell the tool where the NAS is — `GJESUS3_ROOT`

The tools need to know where the NAS is mounted. They look, in order, at:

1. an explicit `--nas-root <path>` you pass on the command (GUI: the NAS-root box),
2. the environment variable **`GJESUS3_ROOT`**,
3. the Linux default `/mnt/gjesus3`.

The chosen path must be a real NAS root — a folder that contains a `registries/`
subfolder. If it is not, the tool stops with one clear message instead of
silently writing into a phantom folder.

```sh
# Linux / WSL — set once per shell (or add to your ~/.bashrc to make it stick):
export GJESUS3_ROOT=/mnt/gjesus3
```

```powershell
# Windows PowerShell — set once per session (or add to your $PROFILE):
$env:GJESUS3_ROOT = "J:\gjesus3-data"   # adjust to your NAS drive letter
```

(The microscopy GUI remembers the NAS root for you after the first time.)

---

## MRI / Nuclear Imaging operators (Linux command line)

The data office installs the tools once on your acquisition machine (a checkout
of this repo in a Python virtual environment; the operator account just runs the
commands). Python 3 with `pyyaml`, `pydicom`, `tqdm`, and — for the MRI FTP pull
— `paramiko` must be present (see [`tools/requirements.txt`](../requirements.txt)).

### Nuclear Imaging — `ni-ingest`

```sh
python tools/operator/ni_ingest.py /path/to/folder            # preview, then asks Proceed? [y/N]
python tools/operator/ni_ingest.py /path/to/folder --dry-run  # preview only, never writes
python tools/operator/ni_ingest.py /path/to/folder --go       # skip the prompt and commit
```

- Point it at **one extracted acquisition folder**, or at a **parent folder of
  many** — it auto-detects which and previews every acquisition it finds.
- **Archive (`.tgz`) data must be extracted first.** If you point `ni-ingest` at
  a `.tgz` (or a folder of `.tgz`), it tells you to run
  [`tools/extract_ni_archives.py`](../extract_ni_archives.py) first rather than
  guessing. Extract, then point `ni-ingest` at the extracted folder.
- **Live-machine (non-archive) folders are not wired up yet.** The on-the-machine
  folder layout still needs to be captured in a template
  (`molecubes_ni_live.yaml`). If you point at a live folder, the tool says so and
  asks you to use archive mode for now. *(Deployment itself is unblocked — the NI
  server runs Linux and a script can be installed there, confirmed 2026-06-03;
  only the live-layout template remains.)*

### MRI (Bruker ParaVision) — `mri-ingest`

```sh
python tools/operator/mri_ingest.py /path/to/study                              # preview, then asks Proceed? [y/N]
python tools/operator/mri_ingest.py /path/to/study --reconstructions 3 --model 7T
python tools/operator/mri_ingest.py /path/to/study --dry-run                    # preview only, never writes
python tools/operator/mri_ingest.py /path/to/study --go                         # skip the prompt and commit
```

- Point it at **one exam**, a **study folder**, or a **batch root** — it
  auto-detects the scope and previews every exam.
- Two optional per-run knobs (everything else is locked in by the template):
  - `--reconstructions all | 3 | 1,3` — which reconstruction images to copy
    (omit to keep the template default).
  - `--model 7T | 11.7T` — which BioSpec scanner produced the batch. If you omit
    it, the tool warns and leaves a placeholder; pass it to record the real
    scanner in the registry.
- **Pulling from the console over FTP (optional):** if the data is still on the
  MRI console, add `--ftp-remote /remote/path`. The tool SFTP-mirrors that remote
  folder into your local path first, then previews and ingests. This needs FTP
  credentials in the environment:

  ```sh
  export GJESUS3_FTP_HOST=<console-host>
  export GJESUS3_FTP_USER=<user>
  export GJESUS3_FTP_PASSWORD=<password>
  # export GJESUS3_FTP_PORT=22   # optional, defaults to 22
  ```

  Without `--ftp-remote`, the tool assumes the data is already on a local or
  mounted path (no network needed).

### The everyday flow (both Linux tools)

1. Finish the acquisition; make sure the data is on a folder the machine can see
   (extract `.tgz` first for NI; optionally `--ftp-remote` for MRI).
2. Run the command. Read the preview table — check the file counts, sample IDs,
   and projects look right.
3. Answer `y` at the prompt (or you passed `--go`). The streaming log shows
   progress; when it finishes, the acquisitions are on the NAS with their
   project hard links created.
4. To double-check, use `--dry-run` first any time you are unsure — it previews
   and writes nothing.

---

## Microscopy operators (Windows GUI)

The microscopy front-end is a small web app that opens in your browser. On a
locked-down Windows microscopy machine it ships as a **single `.exe`** — no
Python install, no admin rights needed.

### Running the GUI

1. **Double-click `microscopy_ingest.exe`.** A browser tab opens automatically
   (at `http://127.0.0.1:5000`). Leave the little console window open while you
   work — closing it stops the app.
2. **Set the NAS root once.** In the NAS-root box, enter where the NAS is mounted
   (e.g. `J:\gjesus3-data`) and save. The app remembers it next time.
3. **Run a recipe** (the everyday case):
   - Pick your instrument (ZWSI / CELL / LSM9) and a saved **recipe** (a
     ready-made convention the data office prepared).
   - Use the folder box to point at your day/batch folder.
   - Click **Preview** — a read-only table shows each acquisition's ACQ-ID,
     project, link name, the resolved registry row, and *X new / Y
     already-ingested*. Check it.
   - Click **Ingest**. A live log streams the progress. (A *Dry-run* checkbox,
     on by default, lets you do a no-write rehearsal first.)
4. **Build a recipe** (only when defining a brand-new naming convention): the
   builder tab lets you set how filenames/folders are parsed, see a live
   `discovered.*` grid over your real files, map those values into the registry
   fields / link name / project via clickable token chips (each field shows a
   live resolved example; anything unresolved flags red), then **Save recipe**.
   For routine ingests you will not need this — just pick an existing recipe.

### Building the `.exe` (data office, one-time per release)

The microscopy machine runs the `.exe` only. To produce it:

```sh
pip install flask pyinstaller czifile tifffile numpy pyyaml pydicom tqdm
pyinstaller tools/operator/gui/microscopy_ingest.spec
# -> dist/microscopy_ingest/microscopy_ingest.exe
```

The spec bundles the per-instrument templates and the seed recipes into the
`sys._MEIPASS`-aware locations the core looks in first. After freezing, verify
the exe by previewing **and** dry-run-ingesting a real `.czi` batch (the dry-run
exercises the bundled `czifile`/`numpy`/`tifffile`). Full detail and the
endpoint map are in [`gui/README.md`](gui/README.md).

---

## When something goes wrong (plain language)

- **"NAS root does not look valid"** — the path you gave (or `GJESUS3_ROOT`)
  isn't a real NAS root. Point it at the mounted NAS folder that contains
  `registries/`.
- **"no files in that folder match this instrument"** — you may be pointing at
  the wrong folder, or NI archives that still need extracting. Check the path.
- **"extract first" (NI)** — run `tools/extract_ni_archives.py` on the `.tgz`,
  then point `ni-ingest` at the extracted folder.
- **A field shows red / unresolved `${…}` (GUI builder)** — that field
  references a value not found in your files; fix the parse rule or the mapping.
- **Anything else** — re-run with `--dry-run` (or the GUI Dry-run checkbox) to
  preview safely, and if it still looks wrong, contact the Data Management Lead.
  The source files on the instrument are preserved by default; nothing is
  deleted unless you explicitly opt in.

---

## For maintainers

The shared core (`templates.py`, `config_builder.py`, `scope.py`, `preview.py`,
`runner.py`, `env.py`) is GUI-agnostic and cross-platform; all platform-specific
code lives in the three front-ends. Before adding a front-end, read
[`IMPORT_CONTRACT.md`](IMPORT_CONTRACT.md) — the directory is named `operator`
(it collides with the stdlib `operator` module), so the core is loaded through
`_loader.py` (alias `gj_op_core`), never via `import operator`.
