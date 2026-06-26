# Researcher FAQ — finding and using your data on gjesus3

Plain-language answers to the questions researchers ask most. No code, no jargon —
where a term needs a fuller definition, follow the link to the
[Glossary](../GLOSSARY.md). For the bigger picture of how to work with your data,
start with the [Researcher Guide](../RESEARCHER_GUIDE.md).

> **gjesus3** is the group's shared imaging NAS (network drive) at CIC biomaGUNE.
> It keeps your microscopy and imaging data organised, searchable, and viewable for
> the active life of a project. It is the **working layer**, not a long-term archive —
> the instrument platforms keep their own deep raw archives.

**Last Updated:** 2026-06-26

---

### 1. Where is my data?

It's on the gjesus3 NAS, in two places that point at the **same files**:

- **`raw/`** — the permanent, never-changed copy of every acquisition, filed by
  ecosystem → year → month (for example `raw\MICROSCOPY\2026\2026-02\ACQ-…`).
- **`projects\<your-project>\`** — your project workspace, where the same scans
  appear grouped together for you to work with.

You almost never browse `raw/` by hand. Instead, use the **Finder** (next question)
to search, or open your **project folder**, which already gathers your scans in one
place. See *What is `/raw/` vs `/projects/`?* below for why there are two.

### 2. How do I find a scan from last month?

Open the **Finder** — a searchable index that lives on the NAS:

1. Open the share and double-click **`registries\index.html`** (the global index),
   or the **`index.html`** inside your own project folder (just your project's scans).
   It opens in the web browser already on the machine — nothing to install.
2. Type in the search box. It filters instantly across every column, so any of these
   work: a month like `2026-02`, an instrument code like `MRI`, an animal or sample
   id, a researcher name, an organ like `heart`, or your project name.
3. Click a row to open its detail panel, then use the **Copy path** button to jump
   straight to the data.

Full details (columns, sorting, limits) are in the [Finder guide](FINDER.md).

### 3. How do I open a "Copy path" link — why isn't it clickable?

The Finder gives you a **Copy path** button rather than a clickable link on purpose.
Web browsers block a page from *opening* a folder on a network drive for security, so
a plain link would often just silently do nothing. Instead:

1. Click **Copy path**.
2. Open **File Explorer**, click the address bar, and **paste** (Ctrl+V), then Enter.

That opens the folder every time, on any machine. **Tip:** if you copied the
**metadata.json** path, paste it into a new browser tab instead — the browser shows
the metadata as a tidy, collapsible tree.

### 4. What is `/raw/` vs `/projects/`?

Two views of the same data, for two different jobs:

| | `raw/` | `projects\<proj>\` |
|---|---|---|
| **Holds** | Every acquisition, permanently | The scans belonging to one project |
| **Changes?** | **Never** — read-only, immutable after ingest | Yes — your working space |
| **Organised by** | ecosystem → year → month | however the project groups them |
| **You** | rarely open it directly | this is where you work |

`raw/` is the single source of truth that nothing edits, so your original data can't
be accidentally changed. A project just **points at** those same raw files (see the
hard-link question), so grouping a scan into your project costs no extra disk space
and never copies or moves the original.

### 5. What's in a `metadata.json` sidecar?

Every acquisition has a small `metadata.json` file sitting next to it — the
searchable "label" for that scan. The Finder reads it, and you can open it yourself
(paste its path into a browser tab). It contains:

- **`user_supplied`** — what was entered at ingest: researcher, operator, sample id,
  notes, and so on.
- **`discovered`** — facts pulled automatically from the file and its name (objective
  magnification, pixel size, image dimensions, acquisition date/time, …).
- **an instrument block** — `microscopy`, `mri`, or `ni`: the rich technical metadata
  read straight from the file (microscope/objective details, MRI scan parameters, …).
- **`subject` / `condition` / `anatomy`** (for animal-derived scans) — *who* the
  animal is (species, strain, sex, age — looked up from the animal-facility database),
  *what study state* the scan is, and *what body part*. Anything not yet known is left
  blank rather than guessed.

The sidecar in `raw/` is **immutable** — it is never edited after ingest. (A separate,
study-level metadata area inside projects is **planned** but not yet deployed 🕗 — see
[tasks/BACKLOG.md](../tasks/BACKLOG.md).)

### 6. What does "hard link" mean for my files?

When a scan is added to your project, the system makes a **hard link**: your project
folder gets what looks and behaves like a normal copy of the file, but it's actually
the **same file on disk** as the one in `raw/`, under two names. Practically:

- It takes **no extra space** — there's still only one real copy.
- Opening it from your project opens the real data, fast, with no copying step.
- You can't accidentally edit the raw original, because `raw/` is read-only.

(Older versions used a Windows shortcut — a `.lnk` — but that is **retired**. Project
links are now real hard links.) More in the [Glossary](../GLOSSARY.md).

### 7. Can I copy data to my own machine?

Yes — it's your data; copy what you need for analysis. Use **Copy path** (or open your
project folder) and copy the files like any other network-drive files. Two things to
keep in mind:

- Work on **copies**; never edit files in `raw/` (you can't — it's read-only — and you
  shouldn't try to work around that).
- Some files are large (whole-slide images, MRI/PET folders run to tens or hundreds of
  MB each), so copy selectively. The Finder's detail panel shows each acquisition's
  **File size** so you know before you copy.

### 8. How do I cite an acquisition?

Every acquisition has a stable **ACQ-ID** — for example `ACQ-20251029-PET-001`. Use it
to refer to a specific scan in lab notes, a methods section, or when asking a
colleague to look at something: the ACQ-ID never changes and uniquely identifies one
scan. The Finder's detail panel shows the ACQ-ID, instrument, date, and key acquisition
parameters you'd put in a methods write-up. (A formal, citable **publication package**
with a DOI-style identifier is a separate, planned feature 🕗 — the `publications/` area
is reserved for it but not yet in use.)

### 9. Who can see my project?

Anyone in the MFB group with read access to the NAS can browse the shared areas — the
group is set up so members can find and reuse each other's imaging data, which is the
point of a shared working layer. Concretely: the **global Finder** (`registries\index.html`)
lists everything to anyone who can open `registries/`, and a **project's own
`index.html`** lists that project's scans to anyone who can open the project folder.
There is no per-person private space inside gjesus3. If you have data that genuinely
must be restricted, talk to the Data Management Lead before depositing it.

### 10. How do I get NAS access? (hardwired machines only)

Access to gjesus3 is from **hardwired, on-site machines only** — the instruments and
certain workstations are wired in; **laptops and Wi-Fi are not** (a deliberate
security choice). If you're on an approved wired machine, the NAS is the share
`\\GJESUS3\gjesus3` (often mapped to a drive letter such as `J:`). If you need access
from a machine that doesn't have it, contact the Data Management Lead — don't try to
reach it from a laptop or off-site.

### 11. What do the instrument codes mean?

The two- to five-letter code in every ACQ-ID (and the Finder's **Instrument** column)
tells you which instrument produced the scan:

| Code | Instrument | Type |
|---|---|---|
| `ZWSI` | Zeiss AxioScan 7 (whole-slide imaging) | Microscopy |
| `CELL` | Cell Observer | Microscopy |
| `LSM9` | LSM 900 confocal | Microscopy |
| `MRI` | Bruker ParaVision MRI | MRI |
| `PET` | Molecubes / MILabs PET | Nuclear Imaging |
| `SPECT` | Molecubes / MILabs SPECT | Nuclear Imaging |
| `CT` | Molecubes / MILabs CT | Nuclear Imaging |

For what each instrument's "raw" data actually is, see
[equipment/INDEX.md](../equipment/INDEX.md).

### 12. Who do I contact?

For anything about gjesus3 — access, finding data, depositing data, a scan that looks
wrong, or a question this FAQ doesn't answer — contact the **Data Management Lead,
Ryan Tasseff** (Data Office, CIC biomaGUNE).

---

**See also:** [Researcher Guide](../RESEARCHER_GUIDE.md) ·
[Finder guide](FINDER.md) · [Glossary](../GLOSSARY.md)
