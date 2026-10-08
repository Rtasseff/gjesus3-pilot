# Syncing your nuclear-imaging data to gjesus3

For researchers and operators at the Molecubes box. **Two commands. Usually one.**

Your data stays where it is — the sync only ever **reads** your folder.

---

## The short version

```
ni-ingest <your folder> --live --plan     # 1. what's new?
ni-ingest <your folder> --live --go       # 2. sync it
```

`<your folder>` is your own data folder on the box, e.g.
`/Users/molecubes/Documents/volumes/remiW11/data/irene`.

`ni-ingest` is a small launcher on the shared `gnuclear` drive. Type its full path (the
data office gives it to you), e.g. `/Volumes/gnuclear/…/ni-ingest`. Nothing is installed
on the Mac. `gjesus3` must be connected in Finder.

Step 1 writes nothing to gjesus3 and changes nothing on your box. If it says
**"nothing new to review"**, skip straight to step 2 — that is the normal case once
you've synced before.

---

## Step 1 — see what's new

```
ni-ingest <your folder> --live --plan
```

This looks for scans that aren't on gjesus3 yet and adds **one row per session** to
**your corrections file**, with what we read off the folder names already filled in.

You don't have to name that file or remember where it is — the tool finds it and
**prints its full path every time it runs**. It is called
`ni_corrections_<your name>.csv` and it lives in your own folder on the shared
`gnuclear` drive, alongside your other nuclear-imaging files.

Open it in Excel **on the Mac**. From a Windows PC the file is read-only for you (the Mac
creates it, and `gnuclear` lets the group read but not change it). It looks like:

| session_path | project | animal_codes | extra_metadata |
|---|---|---|---|
| `1207/260212/0324_m61` | 0324 | 61;62 | |

- **`session_path`** — don't change this. It's how we find your folder.
- **`project`** — the animal-protocol number.
- **`animal_codes`** — the mouse numbers, separated by `;`.
- **`extra_metadata`** — anything else worth recording, as `key=value`. Most usefully
  the tracer: `tracer=FDG`. Several: `tracer=FDG;dose=10 MBq`.

**Only change what's wrong.** If the folder name had a typo — the wrong protocol number,
the wrong mouse id — fix it here. This is the place to correct things you couldn't fix in
REMI.

If everything is right, just close the file. You don't have to edit anything.

**The file is yours.** Step 1 only ever *adds* rows for sessions it has never seen. It
never rewrites, reorders or clears anything you typed.

## Step 2 — sync

```
ni-ingest <your folder> --live --go
```

That's it — no filename, no extra flag. Your corrections file is read automatically. It
copies each reconstruction to gjesus3, records the metadata, and registers it.

---

## Things worth knowing

**You fix a session once, ever.** The correction lives in your file, so when a new
reconstruction of that same scan turns up weeks later it gets your corrected values
automatically. That's also why step 1 gets quieter over time — it only shows you sessions
that have never been reviewed.

**Re-running is safe.** The sync skips anything already on gjesus3, including scans that got
there another way, e.g. ones you copied to `gnuclear` that the data office already loaded. Run it
as often as you like — after every session, or once a week. Nothing is ever copied twice.

**Reconstructions that aren't finished yet are skipped, not lost.** If you sync while a
reconstruction is still running, that scan is skipped with a note and picked up on your
next sync. You don't have to wait or remember.

**Each reconstruction is its own entry.** One scan with three reconstructions becomes three
entries on gjesus3. A reconstruction you add later becomes a new entry — it never
overwrites the old one.

**CT attenuation maps go to your project folder, not to the raw data.** Some CT scans have a
reconstruction folder holding only `ATTMAP.dcm`, the CT converted for the PET's attenuation
correction. It is derived from the scan rather than acquired, so the sync copies it into the
project's `outputs\derived\`. Its name says which scan it came from, e.g.
`CT_1025_m1_20260522_20260522095612_recon2_ATTMAP.dcm`, and the project's `provenance.csv`
records the exact raw entries. It is not listed in the table of new acquisitions.

**Project folder links are made later, not now.** The Mac can't create the file links
gjesus3 uses inside project folders (a macOS-over-network limitation, nothing you did).
Your data is fully copied, checksummed and registered — only the shortcut into the project
folder is deferred. It's recorded automatically and the data office creates it from a
Windows machine. **Nothing is missing and nothing is lost.**

---

## If something goes wrong

**"not a directory"** — point at your own data folder, the one with your name on it.

**It asks "Proceed? [y/N]"** — that's the confirmation before writing. `y` to go ahead.
Use `--go` to skip it.

**A scan you expected isn't listed** — it's most likely already synced (run without
`--plan` to see the full table), or its reconstruction hasn't finished yet.

**You can't find your corrections file** — read the `corrections file:` line the tool
prints at the start of every run. That is always the file it is using.

**Anything else** — stop and send the output to the data office. Don't re-run it repeatedly
to try to clear an error; a stuck sync is safe to leave alone.

---

## For the data office

- **The launcher** is `tools/operator/ni-ingest.sh`, staged as `<dir>/ni-ingest` beside
  `<dir>/tools/`. It runs `/usr/local/bin/python3` (3.10; a non-interactive ssh shell
  finds the system 3.8 first), sets `PYTHONPATH`, writes no `__pycache__`, and defaults
  the NAS root to `/Volumes/gjesus3/gjesus3-data` unless `GJESUS3_ROOT` is set. Not mounted
  means a clean "NAS root does not look valid" exit with nothing written.
- **Test runs:** `--plan` writes the corrections file into the *researcher's* gnuclear
  folder. For a test that must stay out of it, pass `--corrections` with an **absolute**
  path (a relative one lands in the shell's current directory).
- Live sync builds its config in memory from
  `tools/templates/instruments/molecubes_ni_live.yaml`. **There is no per-batch YAML.**
- **Corrections: one file per researcher, on `gnuclear`, kept forever.**
  `<gnuclear>/<year>/<group>/<researcher>/ni_corrections_<researcher>.csv`, keyed on the
  raw `<series>/<date>/<subject>` relpath. `ingest/ni_corrections.py::resolve_path`
  derives the share root, year and group **from the running code's own path** — the code
  is staged on `gnuclear`, so this resolves correctly on the Mac (a `/Volumes/…` mount)
  with no env var and no flag. An existing file is reused wherever it already sits, so a
  correction does not expire when the year rolls over. Off `gnuclear` (dev checkout) it
  falls back to sitting next to the code. `--plan` appends unseen sessions and touches
  nothing else; every `--live` run reads the file; **nothing merges or rewrites it.**
- Deferred project links: `registries/pending_links.csv`, drained by
  `tools/relink_pending.py` from Windows.
- `tools/ni_live_discover.py` is the read-only per-acquisition survey — a **diagnostic
  tool, not an operator step**. It answers "what does the whole tree look like", which the
  corrections file deliberately doesn't.
- Design + rationale: `tasks/ni_live_operator_flow_plan.md`.
