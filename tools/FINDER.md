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
2. Type in the search box — it filters instantly (id, sample, subject, instrument,
   modality, date, region, project, researcher). Click a column to sort; click a
   row for full details (paths, metadata link, original name, …).
3. Click **Copy path** on a row and paste into File Explorer's address bar to open
   that acquisition's folder.

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
or anything else. Re-run it whenever you want to refresh (e.g. after an ingest);
the page shows a "generated <timestamp>" line.

`--link-base` sets the share root prepended to the copyable paths (default
`\\GJESUS3\gjesus3`, which works on any machine regardless of drive-letter
mapping; use this rather than `J:` so every researcher's copy-path resolves).

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
- **Static snapshot.** The page embeds the registry data at generation time;
  re-run to refresh. (Acceptable: the registry changes only on ingest.)
- **Size.** Self-contained means all rows are embedded — ~15 MB at 13.5k acqs.
  It opens fine, but for a much larger archive the next step is client-side
  virtualization / a fetched data file. The table shows the first 800 matches of
  any search (narrow your query); the count line tells you the true total.
- **Per-project = exposure.** A project's `index.html` lists that project's acqs
  to anyone who can read the folder; the global one lists everything to anyone who
  can read `/registries/`. Fine for one group; revisit per-project + ACLs for
  multi-group sharing.
- **No edit / no write-back.** Read-only view; it never modifies data.

## Next (not in this MVP)
Richer per-acquisition detail panel from the sidecar; saved/shareable searches
(URL hash); select-rows → export a CSV / methods-section manifest; a small
counts dashboard; and — when they exist — per-row "Open in XNAT/OMERO" launch
links (the Finder stays the front door; the heavy viewers plug in later).
