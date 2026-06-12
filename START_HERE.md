# Start here — ingesting data onto gjesus3

> The first link in [README.md](README.md). If you run an instrument and need to
> get its data onto the NAS, you're in the right place. Plain-language, one page.

**What this is:** a quick, safe way to put your instrument's data onto the
**gjesus3 NAS** in a structured, searchable layout — so it can be found, viewed,
and linked to projects later. You point a tool at your data folder; the tool
knows the rest. No file-by-file copying, no editing config files.

---

## 1. Pick your front-end

Three ready-to-go tools, one per instrument family. **You only use the one for
your instrument** — find your row and use that command:

| Your instrument | Use | Where |
|---|---|---|
| **Microscopy** — AxioScan 7 / Cell Observer / LSM 900 | the **microscopy GUI** (opens in your browser) | Windows |
| **Nuclear Imaging** — Molecubes PET/CT | `ni-ingest` (one command) | Linux acquisition machine |
| **MRI** — Bruker ParaVision | `mri-ingest` (one command) | Linux acquisition machine |

**Microscopy (Windows):** double-click **`microscopy_ingest.exe`**. A browser tab
opens automatically. Leave the small console window open while you work. Then:
pick your **recipe** → point at your **folder** → **Preview** → **Ingest**.

**Nuclear Imaging (Linux):**

```sh
python tools/operator/ni_ingest.py /path/to/folder
```

**MRI (Linux):**

```sh
python tools/operator/mri_ingest.py /path/to/study --operator "Your Name"
```

> Each tool shows you what it will do *before* it writes anything, and asks you
> to confirm. Pointing it at the same folder twice is safe — already-ingested
> data is skipped, not duplicated.

---

## 2. Tell the tool where the NAS is — `GJESUS3_ROOT`

The tools find the NAS via, in order: `--nas-root` (a path you pass) → the
**`GJESUS3_ROOT`** environment variable → the Linux default `/mnt/gjesus3`. Set
it once so you don't have to think about it:

```powershell
# Windows PowerShell — set once per session (or add to your $PROFILE):
$env:GJESUS3_ROOT = "J:\gjesus3-data"   # adjust to your NAS drive letter
```

```sh
# Linux — set once per shell (or add to your ~/.bashrc to make it stick):
export GJESUS3_ROOT=/mnt/gjesus3
```

The microscopy GUI has a **NAS-root box** instead — set it once and it remembers.
If the path isn't a real NAS root, the tool stops with one clear message rather
than writing into the wrong place.

---

## 3. Dry-run first — always

Every front-end previews before it writes. **Preview, read the table** (one row
per acquisition — sample, project, link name, file count), make sure it looks
right, *then* ingest for real.

- **Microscopy GUI:** there's a **Dry-run** checkbox. During the testing period
  it is **ON by default** (a banner shows while it's on); a dry run ends with a
  clear **"NOTHING was written"** summary. Do a dry run, check it, then turn the
  checkbox off and ingest for real.
- **Linux tools (`ni-ingest` / `mri-ingest`):** they preview and then ask
  `Proceed? [y/N]`. Add **`--dry-run`** any time you want a preview that writes
  nothing.

Nothing on your instrument is deleted — source files are kept by default.

---

## Where to go next

| If you want… | Go to |
|---|---|
| The full operator guide (all options, troubleshooting) | [`tools/operator/README.md`](tools/operator/README.md) |
| The self-service ingest overview, then the data-office YAML path | [`mfb-rdm-docs/11_OPERATIONS.md`](mfb-rdm-docs/11_OPERATIONS.md) §3.3, then §3.2 |
| A word you don't recognise | [`GLOSSARY.md`](GLOSSARY.md) |

**Stuck?** Contact the Data Management Lead (Ryan Tasseff, Data Office).
