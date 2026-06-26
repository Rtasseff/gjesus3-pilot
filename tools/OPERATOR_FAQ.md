# Operator / Tech FAQ — ingesting data onto gjesus3

Short answers to the questions instrument operators and techs ask most. For the
one-page getting-started walkthrough see [`START_HERE.md`](../START_HERE.md); for
every CLI flag and the full config schema see
[`INGEST_CLI.md`](INGEST_CLI.md); for the click-by-click GUI guide see
[`operator/gui/README.md`](operator/gui/README.md).

> **Audience:** the person running an instrument (microscope, MRI, PET/CT) who
> needs to get its data onto the NAS. Plain language, no internals. A word you
> don't recognise → [`GLOSSARY.md`](../GLOSSARY.md).

> **One safety net throughout:** the source files on your instrument are **kept
> by default** — nothing is deleted unless you explicitly opt in. A run you
> aren't sure about can always be previewed first (see Q1) and re-run safely
> (the pipeline skips anything already ingested).

*Last Updated: 2026-06-26*

---

## 1. What is a dry-run, and why is it on by default?

A **dry-run** is a rehearsal: the tool reads your folder, works out exactly what
it *would* do — one row per acquisition (sample, project, link name, file count)
— and shows you that table, but **writes nothing** to the NAS. You read it,
confirm it looks right, then run for real.

It defaults **ON** during the current testing period so you learn the tool with
**zero risk of an accidental write**. A dry run ends with a clear
**"NOTHING was written"** summary.

- **Microscopy GUI:** a **Dry-run** checkbox, ticked by default; a banner shows
  while it's on. Do a dry run, check it, untick the box, then ingest for real.
- **Linux tools (`ni-ingest` / `mri-ingest`):** they preview and then ask
  `Proceed? [y/N]`. Add `--dry-run` any time you want a preview that writes
  nothing.
- **Data-office YAML path:** run with `--dry-run` (or `-n`) first — see Q2.

**Always dry-run first when in doubt.** It catches almost every mistake before
anything touches the NAS.

---

## 2. GUI (`gjesus3_ingest.exe`) vs the command line — which do I use?

Use the front-end for **your** instrument family. You only ever use one.

| Your instrument | Use | Where it runs |
|---|---|---|
| **Microscopy** — AxioScan 7 / Cell Observer / LSM 900 | the **GUI** `gjesus3_ingest.exe` (opens in your browser) | the Windows microscopy machine |
| **Nuclear Imaging** — Molecubes/MILabs PET/SPECT/CT | `ni-ingest` (one command) | the Linux acquisition machine |
| **MRI** — Bruker ParaVision | `mri-ingest` (one command) | the Linux acquisition machine |

All three run the **exact same validated pipeline** under the hood — they only
differ in how you drive them. None of them makes you write YAML.

- **`gjesus3_ingest.exe`** is a single frozen Windows executable (~95 MB) — no
  Python install, no admin rights. Double-click it; a browser tab opens at
  `http://127.0.0.1:5000`. Leave the small console window open while you work
  (closing it stops the app). It serves **two pages from the one exe**: a
  microscopy page (the default) and an MRI page (launched with
  `gjesus3_ingest.exe --mri`).
- **`ni-ingest` / `mri-ingest`** are dead-simple Linux commands the data office
  installs once on your acquisition machine: point at a folder, preview,
  confirm.

There is also a **data-office YAML path** (`python tools/ingest_raw.py -c
<config>.yaml`) for the people who maintain the system — you do **not** need it
for routine ingests. If you're hand-editing YAML, see
[`INGEST_CLI.md`](INGEST_CLI.md).

---

## 3. How do I pick and copy a per-instrument template?

For the GUI and the Linux tools you **don't** touch templates at all — each
front-end already knows its instrument and loads that instrument's locked-in
conventions (the per-instrument template) for you. In the GUI you just pick a
**recipe** (a ready-made convention the data office prepared) for ZWSI / CELL /
LSM9. That's the everyday path.

The rest of this answer is for the **data-office YAML path** only.

Per-instrument templates live in `tools/templates/instruments/`:

| Instrument | Template |
|---|---|
| AxioScan 7 (`ZWSI`, `.czi`) | `tools/templates/instruments/axioscan7.yaml` |
| Cell Observer cells-mode (`CELL`, `.czi`) | `tools/templates/instruments/cell_observer_cells.yaml` |
| Internal MRI / Bruker ParaVision (`MRI`) | `tools/templates/instruments/mri_bruker.yaml` |

To make a config for a batch: **copy** the matching template into
`tools/configs/`, edit `staging_dir` + `notes`, save as
`<instrument>_<batch>.yaml`, then run it (see Q5). **Never edit a template in
place** — it's the locked convention; you copy and edit the copy. If your
instrument has no template yet, fall back to
`tools/templates/ingest_template.yaml` and **ask the Data Management Lead before
running**.

Each template's header comment block lists every `discovered.*` field you can
reference for that instrument — that's your reference card.

---

## 4. What does `link_filename:` control?

It controls the **name of the project link** for an acquisition. When an
acquisition belongs to a project, the system places a link to it under
`/projects/<proj>/raw_linked/` so the data appears inside the project folder.
That link is a **hard link** (it looks and behaves like a real file/folder, takes
no extra space, and stays byte-identical to the original in `/raw/`). The older
Windows shortcut (`.lnk`) method is **retired** — links are hard links now.

`link_filename:` is the template for what that link is called. The per-instrument
templates ship a sensible default, so you rarely set it yourself:

- **Microscopy** default: `${instrument}_${original_name}` (e.g.
  `ZWSI_MFB_MBC_0525_ID26H_WGA_10x.czi`).
- **MRI** default:
  `MRI_${sample_id}_${acq_date}_${discovered.mri_exam_number}_${discovered.mri_recon_indices}`
  — because the MRI source identifier is a folder path plus a numeric position, a
  plain filename would collide when several animals share an exam number, so the
  link name is built to be unique per (animal, exam, reconstruction).

You override it (in the YAML path) only when the default would collide. The
context you can use is every `discovered.*` field, every resolved registry field
(`${sample_id}`, `${instrument}`, …), plus `${acq_id}` and `${acq_date}`. Full
detail in [`INGEST_CLI.md`](INGEST_CLI.md) and
[`mfb-rdm-docs/10_TOOLS.md §2.1.5`](../mfb-rdm-docs/10_TOOLS.md).

---

## 5. Where do per-batch configs go? (data-office YAML path)

In `tools/configs/`, named `<instrument>_<batch>.yaml`, under git so the script
and its config stay version-locked together. Each one is **one ingest run**:
copy the matching template, edit `staging_dir` + `notes`, run it. The relative
path of the config is stamped into every registry row's `ingest_config` column,
so any row can be traced back to the exact config that produced it.

```bash
# Dry-run first (always):
python tools/ingest_raw.py -c tools/configs/<instrument>_<batch>.yaml --dry-run
# Then for real:
python tools/ingest_raw.py -c tools/configs/<instrument>_<batch>.yaml
```

(GUI and Linux-tool operators never create these files — the front-end builds the
config in memory for you.)

---

## 6. I hit an error — what are the common ones and their fixes?

| Message / symptom | What it means | Fix |
|---|---|---|
| **"NAS root does not look valid"** | The path you gave (or `GJESUS3_ROOT`) isn't a real NAS root. | Point it at the mounted NAS folder that contains a `registries/` subfolder (e.g. `J:\gjesus3-data`). See Q on the NAS root in [`START_HERE.md`](../START_HERE.md). |
| **"no files in that folder match this instrument"** | Wrong folder, or NI archives still need extracting. | Check the path; for NI, extract first (next row). |
| **"extract first" (Nuclear Imaging)** | You pointed `ni-ingest` at a `.tgz` archive. | Run `python tools/extract_ni_archives.py` on the `.tgz`, then point `ni-ingest` at the extracted folder. |
| **Live-machine NI folder "not wired up yet"** | The on-the-machine (non-archive) NI layout isn't templated yet. | Use archive mode for now (extract, then ingest), and tell the Data Management Lead. |
| **A field shows red / unresolved `${…}` (GUI builder)** | That field references a value not found in your files. | Fix the parse rule or the mapping until the live example resolves. |
| **No-DICOM MRI exam → empty placeholder** | The exam had no DICOMs and Dicomifier wasn't detected on this machine, so it ingested as an empty placeholder (this never blocks the batch). | Fine to leave — a later re-ingest from a Dicomifier-equipped machine fills it. The MRI tool prints whether Dicomifier was detected *before* the preview. |
| **Header / schema migration error (YAML path)** | The registry schema changed and the file needs migrating. | Don't hand-fix it — contact the Data Management Lead. |

Two rules that fix most "did I break something?" worries:

- **The pipeline is idempotent.** Re-running the same folder/config does **not**
  duplicate rows — already-ingested acquisitions are skipped with a log line
  saying why. Safe to re-run after a partial failure.
- **Read the log.** Each line is prefixed with a step number (1–12); the failure
  point tells you where to look.

If it still looks wrong, re-run with `--dry-run` (or the GUI Dry-run checkbox)
and escalate (Q10). **Never hand-edit the registry CSVs** — corrections must land
cleanly so the audit chain stays intact.

---

## 7. How do I check the registries are healthy after an ingest?

Run the read-only validator. It walks `registries/` and the `/raw/` tree and
reports problems; it **never writes anything**, so it's always safe to run.

```bash
python tools/validate_registries.py --nas-root J:\gjesus3-data
#   (or, with GJESUS3_ROOT already set:)
python tools/validate_registries.py
```

It exits non-zero only on an **ERROR** (a real structural problem — bad header,
duplicate `acq_id`, a `canonical_path` that doesn't exist on disk, a `project_hint`
that isn't a known project, …). **WARN** lines are expected and do **not** mean
failure: they flag open enrichment gaps under the **non-blocking** metadata model
— e.g. a `subject:` block still queued for the animal-facility DB
(`source: "pending-db"`), or an `is_control` / `is_whole_body` left unknown.
Those are legitimate "fill-in-later" states, not breakage.

If you get an ERROR, don't try to fix the CSV by hand — send the output to the
Data Management Lead (Q10).

---

## 8. What happens if two filenames collide?

A collision matters only for the **project link name** — two acquisitions can't
both claim the same link under one project's `raw_linked/` folder. That's exactly
what `link_filename:` exists to prevent (Q4): the per-instrument templates build
link names that are unique per acquisition (MRI, for instance, keys on
animal + exam + reconstruction precisely because the bare source name would
collide).

In practice:

- **Same acquisition pointed at twice** is *not* a collision — the pipeline is
  idempotent and skips it (it matches on acquisition date + original name). No
  duplicate, no error.
- **Two genuinely different acquisitions resolving to the same link name** — if
  you're on the YAML path, adjust `link_filename:` to include a distinguishing
  field (`${acq_id}` always makes it unique). If you're on the GUI/Linux tools
  and you see this, the preview/log will show it — stop and contact the Data
  Management Lead rather than forcing it.

(Each acquisition's own folder in `/raw/` is always unique — its ACQ-ID is
generated and never reused — so the underlying data never overwrites anything.)

---

## 9. How does the Finder get updated — do I have to do anything?

No. The **Finder** is the searchable `registries/index.html` page researchers
double-click over SMB (plus a per-project `index.html` in each project folder).
**Every successful (non-dry-run) ingest auto-refreshes it** — the global index
*and* every per-project index — at the end of the run. You don't run anything.

This refresh is **non-fatal**: if it fails for any reason it logs a **WARN** but
does **not** fail your ingest (your data is already safely in `/raw/` and the
registry). If you see that WARN, the data office can rebuild the page by hand with
`tools/generate_index.py` — no re-ingest needed. More in
[`FINDER.md`](FINDER.md).

A dry-run does **not** refresh the Finder (it writes nothing) — that's expected.

---

## 10. Something's wrong and I'm stuck — who do I escalate to?

**Contact the Data Management Lead — Ryan Tasseff, Data Office.**

Before you do, the safe things to try yourself:

1. Re-run with **`--dry-run`** (or the GUI Dry-run checkbox) — it writes nothing
   and the preview/log usually shows the problem.
2. **Read the log** — the step number (1–12) on the failing line tells you where
   it stopped.
3. Remember **your source data is untouched** (deletion is opt-in) and the
   pipeline is **idempotent** (re-running won't duplicate anything).

When you escalate, include the **command you ran**, the **config name** (YAML
path) or **recipe + instrument** (GUI), and the **log output** (especially the
failing step). **Do not edit the registry CSVs by hand** to "fix" a row — let the
Data Management Lead correct it so the audit chain stays clean.

---

## See also

- [`START_HERE.md`](../START_HERE.md) — the one-page getting-started walkthrough.
- [`operator/gui/README.md`](operator/gui/README.md) — the microscopy/MRI GUI, page by page.
- [`operator/README.md`](operator/README.md) — the Linux `ni-ingest` / `mri-ingest` tools in depth.
- [`INGEST_CLI.md`](INGEST_CLI.md) — every CLI flag and the full YAML config schema (data-office path).
- [`FINDER.md`](FINDER.md) — the searchable `index.html` Finder.
- [`GLOSSARY.md`](../GLOSSARY.md) — terms used here.
