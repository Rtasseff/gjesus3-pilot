# NI live-sync — run the test on the Molecubes Mac

Everything to test the live-box NI sync is in this folder. The code is in `tools/`.
**Nothing here touches the real production NAS unless YOU point it there.**

Refreshed 2026-06-30 from branch `feat/ni-live-hardening`. Questions → Ryan / the data office.

> **What changed since the June 25 run (read this).** The tool is now a **one-command,
> no-YAML** operator script — you no longer edit `ni_live_irene.yaml`. Three real changes
> to confirm:
> 1. **One acquisition per reconstruction.** Each `recon_<idx>/` of a scan is now its own
>    acquisition. A reconstruction you run *later* is picked up automatically on the next
>    sync; a scan whose reconstruction isn't finished yet (no DICOMs) is **skipped, not
>    failed** (this is what caused the 5 failures last time).
> 2. **Hard-links on the Mac.** Last time every project link failed (`Operation not
>    supported` — macOS over SMB has no hard-links). That's now handled gracefully: the
>    scan still fully ingests, and the missing link is **recorded** in a worklist
>    (`pending_links.csv`) to be made later from a Windows machine. So link errors are
>    expected and harmless now.
> 3. **Fix REMI mistakes + add the tracer.** A new *worksheet* lets you correct a wrong
>    project code / mouse id and add the per-session tracer — without breaking the sync.

---

## The whole test in one glance

```
mount NAS → Step 0 (hard-link check) → Step 1 (review names)
          → Step 2 (--plan: write worksheet) → Step 3 (edit worksheet)
          → Step 4 (--dry-run preview) → Step 5 (real, to a LOCAL folder)
          → Step 6 (real, to the SANDBOX on the NAS)
```

Steps 1–5 need NO NAS (local throwaway). Steps 0 and 6 use the NAS mount.

---

## Prerequisites (one-time, on the Mac)

- **Python 3.8+** — check: `python3 --version`
- **Packages**: `python3 -m pip install --user pyyaml pydicom pymysql`
  - `pyyaml` = read the template · `pydicom` = read DICOMs · `pymysql` = animal-DB lookup
  - `pymysql` is OPTIONAL: without DB credentials the subjects just queue to a pending
    list (non-blocking) and the test still runs.
- **(Optional) animal-DB credentials** at `~/.my.cnf` on the Mac, for species/sex/strain
  auto-fill. Not required.
- **Copy this whole `ni-live-test` folder to the Mac's local disk first** (most robust),
  e.g. `~/ni-live-test`, then `cd ~/ni-live-test`.

> Every command below is run **from this folder** and starts with `PYTHONPATH=tools` so
> Python finds the code. Copy-paste them; adjust the paths in quotes.

> **⚠️ Always pass `--nas-root` exactly as written.** If you drop it, the tool falls back
> to the *real production NAS* and will wrongly report "nothing new" (it dedups against
> production). Every command below sets it explicitly — keep it.

---

## Mount the gjesus3 NAS on the Mac (needed for Steps 0 and 6)

The NAS is a QNAP on the lab network. On Windows it's the mapped drive `J:`; on the Mac
you mount it by hand over SMB. Steps 1–5 do NOT need it.

**Coordinates:** server **`GJESUS3.cicbiomagune.int`** (IP **`10.10.1.73`** if the name
doesn't resolve) · share **`gjesus3`** (contains `gjesus3-data` = production and
`gjesus3-sandbox` = the test target).

### Easiest — Finder
1. Finder → **⌘K** (Go → Connect to Server…).
2. Enter `smb://GJESUS3.cicbiomagune.int/gjesus3` (or `smb://10.10.1.73/gjesus3`), **Connect**.
3. Sign in with your **CIC biomaGUNE network account** (same as Windows `J:`). If it wants a
   domain, use `CICBIOMAGUNE\yourusername`. Choose "Registered User", not "Guest".
4. It mounts at **`/Volumes/gjesus3`**; the sandbox is **`/Volumes/gjesus3/gjesus3-sandbox`**.

### Verify (Terminal)
```bash
ls /Volumes/gjesus3        # expect: gjesus3-data   gjesus3-sandbox   README.txt
```
**Gotcha:** if `/Volumes/gjesus3` was already taken, macOS appends a suffix (e.g.
`/Volumes/gjesus3-1`). Use whatever name `ls /Volumes` shows in the Step 0/6 commands.

---

## STEP 0 — the hard-link check (do this FIRST)

We already expect this to **FAIL** on the Mac's SMB mount — that's fine, the tool now
handles it (see change #2 above). Run it to confirm + capture the exact errno:

```bash
mkdir -p "/Volumes/gjesus3/gjesus3-sandbox/_oslink_scratch"
PYTHONPATH=tools python3 tools/diagnostics/test_oslink.py "/Volumes/gjesus3/gjesus3-sandbox/_oslink_scratch"
```

- **FAIL (expected)** → the sync will still ingest everything; project links are recorded in
  `pending_links.csv` and made later from Windows. **Send me the FAIL line** (it prints the
  errno). Does NOT block anything below.
- **PASS** → even better; the links get made directly. Either way, continue.

---

## STEP 1 — review the names (read-only, writes nothing)

See what's on the box for a researcher and which names are messy/ambiguous. **Note: here
`--root` is the PARENT `data` folder and `irene` is a separate argument** (different from
Step 2 below):

```bash
PYTHONPATH=tools python3 tools/ni_live_discover.py \
    --root "/Users/molecubes/Documents/volumes/remiW11/data" irene --csv review_irene.csv
```

- Prints one row per scan + a SUMMARY with counts and **flags**: `project-conflict` = a
  likely typo (e.g. 1015 vs 1025), `possible-range` = an ambiguous `m10-15`,
  `species-unknown` = no m/r prefix (the DB fills it), etc.
- **Eyeball the flagged few.** Note any session whose project code or mouse id is wrong —
  you'll fix those in the Step 3 worksheet.

---

## STEP 2 — write the corrections worksheet (`--plan`, read-only)

This is the new tool. **Point it straight at irene's folder** (`.../data/irene` — NOT the
parent). It writes one row per *new* scan-session and stops; nothing is ingested:

```bash
mkdir -p ~/ni-test-nas/registries        # a fresh LOCAL throwaway NAS (has the registries/ it needs)
PYTHONPATH=tools python3 tools/operator/ni_ingest.py \
    "/Users/molecubes/Documents/volumes/remiW11/data/irene" \
    --live --operator irene --nas-root ~/ni-test-nas --plan corrections_irene.csv
```

Open `corrections_irene.csv` — columns: `session_path` (the key — **do not edit**),
`project`, `animal_codes`, `session_id`, `sample_id`, `extra_metadata`.

---

## STEP 3 — edit the worksheet (fix mistakes + add the tracer)

In `corrections_irene.csv`, for any session you want to change:
- **Fix a wrong project code** → edit the `project` cell.
- **Fix a wrong mouse id** → edit the `animal_codes` cell (`;`-separate multiples, e.g. `59;60`).
- **Add the tracer / any per-session note** → put it in `extra_metadata` as
  `key=value;key=value`, e.g. `tracer=FDG; dose=10 MBq`.
- Leave a cell blank to keep the parsed value. **Never change `session_path`.**

(If you don't need any corrections, you can skip Steps 2–3 and just run `--live` without
`--corrections` — but please test the worksheet on at least one session so we know it works.)

---

## STEP 4 — preview with your edits (`--dry-run`, still writes nothing)

```bash
PYTHONPATH=tools python3 tools/operator/ni_ingest.py \
    "/Users/molecubes/Documents/volumes/remiW11/data/irene" \
    --live --operator irene --nas-root ~/ni-test-nas \
    --corrections corrections_irene.csv --dry-run
```

The preview table shows one row **per reconstruction** (so a CT with 3 recons = 3 rows, link
names ending `…_recon0/1/2`). Check that a session you corrected shows the fixed project.
`[expand_batch] ... no DICOMs yet - skipped` lines are NORMAL (reconstructions still running).

---

## STEP 5 — real run to a LOCAL throwaway folder

Drop `--dry-run` to actually ingest into `~/ni-test-nas` (a local folder — does NOT touch
the real NAS):

```bash
PYTHONPATH=tools python3 tools/operator/ni_ingest.py \
    "/Users/molecubes/Documents/volumes/remiW11/data/irene" \
    --live --operator irene --nas-root ~/ni-test-nas \
    --corrections corrections_irene.csv --go
```

- `--go` skips the "Proceed? [y/N]" prompt. Re-running is safe — it ingests ONLY new
  reconstructions (skips what's already there).

---

## STEP 6 — the real combined test (to the SANDBOX on the NAS)

Now point `--nas-root` at the **sandbox** to exercise the real SMB write together with the
hard-link fallback (NOT production — the sandbox). Re-`--plan` first so the worksheet matches
what's new in the sandbox:

```bash
PYTHONPATH=tools python3 tools/operator/ni_ingest.py \
    "/Users/molecubes/Documents/volumes/remiW11/data/irene" \
    --live --operator irene --nas-root "/Volumes/gjesus3/gjesus3-sandbox" \
    --plan corrections_irene_sandbox.csv          # edit it the same way as Step 3, then:

PYTHONPATH=tools python3 tools/operator/ni_ingest.py \
    "/Users/molecubes/Documents/volumes/remiW11/data/irene" \
    --live --operator irene --nas-root "/Volumes/gjesus3/gjesus3-sandbox" \
    --corrections corrections_irene_sandbox.csv --go
```

(Adjust `/Volumes/gjesus3` to the Mac's actual mount of the sandbox.)

---

## Verify the output (Step 5 local, or Step 6 sandbox — swap the path)

```bash
NAS=~/ni-test-nas        # or: NAS=/Volumes/gjesus3/gjesus3-sandbox

# ONE ACQUISITION PER RECONSTRUCTION — original_name ends /recon_<idx>:
cut -d, -f1-3 "$NAS/registries/registry_raw.csv" | head -6

# the slim DICOMs, one folder per acquisition:
ls "$NAS"/raw/DICOM/*/*/

# a multi-mouse scan still packs subject_ids (';'):
grep ';' "$NAS/registries/registry_raw.csv" | head -3

# a corrected session: the tracer landed in the sidecar as session_extra:
grep -rl session_extra "$NAS"/raw/DICOM/ | head -1 | xargs -I{} sh -c 'echo {}; cat {}' | head -40

# the hard-link fallback worklist (only if Step 0 FAILED, i.e. the sandbox run):
[ -f "$NAS/registries/pending_links.csv" ] && head -3 "$NAS/registries/pending_links.csv" || echo "(no pending_links.csv — links were made directly)"
```

You should see: **multiple ACQ-IDs per scan** (`…/recon_0`, `…/recon_1`, …); a corrected
session routed to the fixed project with `session_extra` (tracer) in its `metadata.json`; and
(after Step 6) a `pending_links.csv` listing the links to make later.

---

## What to send me back

1. **Step 0** — the hard-link PASS/FAIL line (with the errno).
2. **Step 1** — the discover SUMMARY (counts + flags).
3. **Steps 5 / 6** — the final `BATCH SUMMARY` (Total / Success / Failed) and any errors.
4. A few `registry_raw.csv` rows — especially a multi-recon scan (several `…/recon_N` rows)
   and a multi-mouse one.
5. One `metadata.json` of a session you corrected (so I can confirm the fix + `session_extra`).
6. `pending_links.csv` head, if it exists.

That tells me everything to green-light a real sync.

---

## Sync a different researcher

Just change the folder you point at and `--operator`:
```bash
PYTHONPATH=tools python3 tools/operator/ni_ingest.py \
    "/Users/molecubes/Documents/volumes/remiW11/data/<name>" \
    --live --operator <name> --nas-root ~/ni-test-nas --plan corrections_<name>.csv
```
Confirmed MFB researchers with NI data: `irene`, `claudia`, `ermal`, `aitor`, `itziar`,
`carlotta`, `laura`. (`--researcher` defaults to the folder name; pass it only to override.)

---

## Troubleshooting

- **`ModuleNotFoundError`** → you forgot `PYTHONPATH=tools`, or you're not in this folder.
- **"NAS root does not look valid … expected a `registries/` subfolder"** → for the local
  test, run `mkdir -p ~/ni-test-nas/registries` first (Step 2 does this).
- **"nothing new to sync" when you expect scans** → you almost certainly dropped `--nas-root`
  (it fell back to production and dedup'd everything). Re-add it exactly as written.
- **Everything skips "path_parse expects 3 level(s)"** → this researcher nests folders at a
  different depth than `series/date/subject`. Send me their layout (from Step 1) — a one-line
  template change.
- **`subject: DB … pending-db` WARNs** → no DB creds on the Mac. Non-blocking; the scan
  ingests and the subject back-fills later.
- **`… no DICOMs yet - skipped`** → expected: that scan's reconstruction isn't finished. It'll
  be picked up automatically on a later sync.

---

## Note on the old files in this folder

- `ni_live_irene.yaml` — the **old** hand-edited config. The `--live` CLI replaces it; you no
  longer need it (kept only for the data-office YAML path).
- `p_5_output.txt` — output from the **June 25** run (the one with the 5 failures + the
  hard-link errors). Superseded by this test.
