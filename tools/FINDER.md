# The gjesus3 Finder — searchable index of the registry (MVP)

**Give researchers their data back, today, on the NAS you already have** — no
XNAT/OMERO, no server, no Python on their side. A generated, self-contained
`index.html` lives on the share; a researcher double-clicks it over SMB, types
`m17` / `MRI` / `2026-02` / `heart` / a project, and gets the matching
acquisitions with a one-click **Copy path** straight to their data.

Two pieces, one join (registry_raw + registry_projects):
- **`tools/find_acq.py`** — the join engine + a CLI (you / power users).
- **`tools/generate_index.py`** — writes the self-contained HTML Finder.

This is an **MVP to try and evaluate** — see *Scope & limitations* at the end.

---

## How a researcher uses it
1. Open the share, double-click `registries\index.html` (or their project's
   `index.html`). It opens in the browser already on the machine.
2. Type in the search box — it filters instantly across every visible column.
   The table columns are, in order: **Acq ID, Date, Instrument, Modality,
   Researcher, Operator, Sample, Subject, Organism, Sample type, Original name,
   Project** (the project `short_name`) and **Owner** (the project owner). Click a
   column header to sort; **drag a column's right edge to resize it** (columns have
   default widths and truncate long values with "…" — hover a cell to see the full
   text); click a row to open the detail panel for everything else.
3. The **detail panel** adds **File size (MB)** and **Project description** on top of
   the raw path, project link, metadata path, session, format, file count, original
   name and notes. It has **Copy path** buttons for the raw path, the project link,
   and the `metadata.json` path.
4. Click a **Copy path** button and paste into File Explorer's address bar to open
   that folder. Tip: paste the copied **metadata.json** path into a Chrome/Edge tab
   instead — the browser renders the JSON sidecar as a native collapsible tree, a
   zero-embed way to read an acquisition's metadata without any viewer.

> **Why "Copy path" and not a clickable link?** Browsers block opening a
> `file://` / UNC path *from* a `file://` page (security), so a plain link often
> silently does nothing. Copy-and-paste into Explorer works everywhere. (A future
> version can add a best-effort link once we confirm the deployed browser allows
> it — see *Next*.)

---

## Generating it (you / the data office)

**Preview locally first** (writes nothing to the share):
```
PYTHONPATH=tools python tools/generate_index.py --nas-root J:/gjesus3-data \
    --per-project --out ./_finder_preview
```
Open `_finder_preview/index.html` to check it, then publish for real:

**Global index** → `<nas>/registries/index.html`:
```
PYTHONPATH=tools python tools/generate_index.py --nas-root J:/gjesus3-data
```
**+ per-project** → a scoped `index.html` in each project folder:
```
PYTHONPATH=tools python tools/generate_index.py --nas-root J:/gjesus3-data --per-project
```
It only writes `index.html` files — it never touches `/raw/`, the registry CSVs,
or anything else. The page shows a "generated <timestamp>" line.

**You rarely need to run it for the global index by hand:** a successful
(non-dry-run) `ingest_raw.py` batch **auto-refreshes `registries/index.html`** at
the end of the run (non-fatally — a refresh failure logs a WARN but never fails the
ingest). Run the generator manually when you want the **per-project** indexes
(`--per-project`), a local preview, or to rebuild after a refresh WARN.

`--link-base` sets the share root prepended to the copyable paths. The default is
the portable container UNC `\\GJESUS3\gjesus3\gjesus3-data` — it works on any
machine regardless of drive-letter mapping, so every researcher's copy-path
resolves. (Use a drive-letter base like `J:\gjesus3-data` only if you know every
researcher maps the NAS to that same letter.) Note the `gjesus3-data` container
component: an earlier default omitted it and produced unresolvable paths.

## The CLI (power users / scripting)
```
PYTHONPATH=tools python tools/find_acq.py m17
PYTHONPATH=tools python tools/find_acq.py MRI --since 2026-02
PYTHONPATH=tools python tools/find_acq.py --instrument ZWSI --anatomy heart --project PROJ-0003
```
Filters: free-text positional + `--instrument --researcher --subject --anatomy
--project --since --until --limit`.

---

## Scope & limitations (MVP — by design)
- **Static snapshot.** The page embeds the registry data at generation time. The
  registry changes only on ingest, and each successful ingest auto-refreshes the
  global `index.html`; per-project indexes and any post-WARN rebuild are a manual
  generator run.
- **Size.** Self-contained means all rows are embedded — ~19 MB at 13.5k acqs.
  It opens fine, but for a much larger archive the next step is client-side
  virtualization / a fetched data file. The table shows the first 800 matches of
  any search (narrow your query); the count line tells you the true total.
- **Per-project = exposure.** A project's `index.html` lists that project's acqs
  to anyone who can read the folder; the global one lists everything to anyone who
  can read `/registries/`. Fine for one group; revisit per-project + ACLs for
  multi-group sharing.
- **No edit / no write-back.** Read-only view; it never modifies data.

## Next (not in this MVP)
Saved/shareable searches (URL hash); select-rows → export a CSV / methods-section
manifest; a small counts dashboard; and — when they exist — per-row "Open in
XNAT/OMERO" launch links (the Finder stays the front door; the heavy viewers plug
in later). (The detail panel now reaches the sidecar via the copyable
`metadata.json` path — a richer in-page sidecar view could come later.)
