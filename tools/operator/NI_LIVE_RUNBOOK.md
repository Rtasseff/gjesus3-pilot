# Syncing your nuclear-imaging data to gjesus3

For researchers and operators at the Molecubes box. **Two commands. Usually one.**

Your data stays where it is — the sync only ever **reads** your folder.

---

## The short version

```
ni-ingest <your folder> --live --plan check.csv     # 1. what's new?
ni-ingest <your folder> --live --go                 # 2. sync it
```

`<your folder>` is your own data folder on the box, e.g.
`/Users/molecubes/Documents/volumes/remiW11/data/irene`.

Step 1 writes nothing and changes nothing. If it says **"nothing to review"**, skip
straight to step 2 — that is the normal case once you've synced before.

---

## Step 1 — see what's new

```
ni-ingest <your folder> --live --plan check.csv
```

This lists the scans that aren't on gjesus3 yet and writes `check.csv`: **one row per
session**, with what we read off the folder names already filled in.

Open it in Excel. It looks like:

| session_path | project | animal_codes | extra_metadata |
|---|---|---|---|
| `1207/260212/0324_m61_m62` | 0324 | 61;62 | |

- **`session_path`** — don't change this. It's how we find your folder.
- **`project`** — the animal-protocol number.
- **`animal_codes`** — the mouse numbers, separated by `;`.
- **`extra_metadata`** — anything else worth recording, as `key=value`. Most usefully
  the tracer: `tracer=FDG`. Several: `tracer=FDG;dose=10 MBq`.

**Only change what's wrong.** If the folder name had a typo — the wrong protocol number,
the wrong mouse id — fix it here. This is the place to correct things you couldn't fix in
REMI.

If everything is right, just close the file. You don't have to edit anything.

## Step 2 — sync

```
ni-ingest <your folder> --live --corrections check.csv --go
```

Or, if you didn't need to change anything:

```
ni-ingest <your folder> --live --go
```

That's it. It copies each reconstruction to gjesus3, records the metadata, and registers
it.

---

## Things worth knowing

**Your corrections are remembered.** Once you fix a session, you never fix it again. The
correction is saved on gjesus3 against that session, so when a new reconstruction of the
same scan turns up weeks later, it gets your corrected values automatically. That's also
why step 1 gets quieter over time — it only shows you sessions nobody has reviewed yet.

**Re-running is safe.** The sync skips anything already on gjesus3. Run it as often as you
like — after every session, or once a week. Nothing is ever copied twice.

**Reconstructions that aren't finished yet are skipped, not lost.** If you sync while a
reconstruction is still running, that scan is skipped with a note and picked up on your
next sync. You don't have to wait or remember.

**Each reconstruction is its own entry.** One scan with three reconstructions becomes three
entries on gjesus3. A reconstruction you add later becomes a new entry — it never
overwrites the old one.

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

**Anything else** — stop and send the output to the data office. Don't re-run it repeatedly
to try to clear an error; a stuck sync is safe to leave alone.

---

## For the data office

- Live sync builds its config in memory from
  `tools/templates/instruments/molecubes_ni_live.yaml`. **There is no per-batch YAML.**
- Corrections store: `registries/ni_session_corrections.csv`, keyed on the raw
  `<series>/<date>/<subject>` relpath. Loaded on every `--live` run; an edited worksheet
  merges into it after a successful commit.
- Deferred project links: `registries/pending_links.csv`, drained by
  `tools/relink_pending.py` from Windows.
- `tools/ni_live_discover.py` is the read-only per-acquisition survey — a **diagnostic
  tool, not an operator step**. It answers "what does the whole tree look like", which the
  worksheet deliberately doesn't.
- Design + rationale: `tasks/ni_live_operator_flow_plan.md`.
