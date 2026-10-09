# ▶ RESUME HERE — NI live sync (current state)

**Updated 2026-10-09.** The NI live sync is **in production**. It was merged into `main` on
2026-10-09 (`3127ad0`), and researchers run a copy staged on gnuclear from `main`. This page is
the short current state.
- **History:** the full working history (the design, the merge gates, every decision with its
  date and reason) is archived verbatim at
  [`archive/RESUME_ni_live_2026-10-09.md`](archive/RESUME_ni_live_2026-10-09.md).
- **Narrative:** the dated story is in [`../CHANGELOG.md`](../CHANGELOG.md).
- **Overview for the team:** [`reports/NI_live_sync_report_2026-10-09.pdf`](reports/NI_live_sync_report_2026-10-09.pdf).

---

## ⛔ Rules for working on the Molecubes Mac (Ryan, 2026-10-06), before ANY ssh to it

These apply to every command and script that touches the Mac, including side effects of programs we run there.

1. **One free write zone: `gnuclear\2026\Jesus\Ryan`.**
   - It is `S:\gnuclear\2026\Jesus\Ryan` on the workstation and `/Volumes/gnuclear/2026/Jesus/Ryan` on the Mac (share `//nuclearuser@10.10.1.92/gnuclear`, checked 2026-10-06).
   - Writing there needs no approval. Prefer writing it from the workstation through `S:`, which costs the Mac nothing.
2. **Every other write by the Mac needs Ryan's approval first, or Ryan runs it himself in his own ssh terminal.**
   - That covers:
     - the local disk;
     - `~`, including `~/.ssh` and `~/Library/LaunchAgents`;
     - pip installs;
     - other gnuclear / gnuclear2$ folders;
     - settings;
     - logs, caches, `__pycache__` and temp files a tool creates.
   - Check where a tool writes before running it.
   - A `--go` to production gjesus3 needs a go-ahead for each run.
3. **Never delete, move, rename or overwrite anything on the Mac that we did not write.** Even for our own files, remove only what we can prove we created.
4. **Read anywhere, but keep the footprint small.**
   - No recursive walks over big trees, and no bulk copies or hashing.
   - Read one session or folder at a time, and copy at most a few small files.
   - Keep commands short. Leave no background or long-running processes.
   - Run heavier steps only outside acquisitions, after checking the load, under `nice -n 19` / `taskpolicy -b`.
   - Develop and test off-box. The Mac is for the final checks only.

Why: the Mac is the platform manager's (§5). Erasing, overwriting or a slow box costs us equipment access, and getting access back took a month. His 2026-10-02 OK covers the remote *sync tests* only.

**Python on the Mac:** non-interactive ssh finds `/usr/bin/python3` (3.8.9). The 3.10 the tools ran with (pyyaml etc.) is `/usr/local/bin/python3`, which a login Terminal, i.e. what operators use, finds first. Over the tunnel, call `/usr/local/bin/python3` explicitly or use `bash -l`.

---

## 1. Where it stands

- **First production sync, 2026-10-08:** Irene's whole box folder.
  - 95/95 reconstructions ingested (6.07 GB).
  - 75 skipped as already registered from the August `S:\gnuclear` pull.
  - 52 CT attenuation maps filed as derived files.
  - Verified: checksums 95/95, validator 0 errors, 95 true hard links, and 145 animal blocks
    equal to their own DB records.
- **Researchers' copy:** `S:\gnuclear\2026\Jesus\_gjesus3_sync\`
  (`/Volumes/gnuclear/2026/Jesus/_gjesus3_sync/` on the Mac).
  - Its `VERSION.txt` names the commit.
  - The `ni-ingest` alias in the `molecubes` account's `.bash_profile` points there.
- **Researcher guide:** `tools/operator/NI_SYNC_GUIDE.html`, with a copy in the code home.
  **Data Office runbook:** [`../tools/operator/NI_LIVE_RUNBOOK.md`](../tools/operator/NI_LIVE_RUNBOOK.md).
- **Access:** the reverse SSH tunnel, in use since 2026-10-01
  ([`live_machine_remote_access.md`](../equipment/nuclear-imaging/live_machine_remote_access.md)).
  From the workstation: `wsl -d Ubuntu -- ssh -p 2222 molecubes@localhost`.

## 2. Operating it

- **A researcher runs two commands at the Mac:** `ni-ingest <folder> --plan`, then fixes codes
  and adds the tracer in their corrections file, then runs `ni-ingest <folder>`. The guide shows
  this with pictures.
- **One registry writer at a time.**
  - Before any NI production write the Data Office runs, tell the coordinator session.
  - Researchers sync outside announced Data Office batch windows. A published "batch running"
    flag is a moderate BACKLOG item.
- **After each researcher sync,** finish the hard links and the animal records from Windows. The
  steps are in the runbook, under "For the data office". This is manual for now; a scheduled
  checker for all the partial-ingest queues is in the BACKLOG.
- **After every merge into `main` that touches `tools/`,** restage the researchers' copy:
  `python tools/operator/stage_ni_gnuclear.py production`.
- **Testing on the Mac never touches production.**
  - `stage_ni_gnuclear.py test-kit` stages a kit whose launcher is pinned to a scratch NAS.
  - Off the box, `tools/test_ni_live_e2e.py` covers plan, dry-run, go, re-sync, the Mac's
    `ENOTSUP`, a person at a terminal, cross-source dedup, derived files and the project rule.

## 3. The gjesus3 mount on the Mac (interim)

- **The mount:** Ryan's own gjesus3 login, with the password in the `molecubes` keychain,
  mounted at `~/.gjesus3`, hidden from Finder. Decided 2026-10-08, because IT won't provide an
  account.
- **Kept up by MacMounter:** through `~/.macmounter/gjesus3.conf` and a locked helper,
  `gjesus3-mount.py`. Three MacMounter copies run (the platform's), so the helper takes a
  `flock` and allows one mount at a time.
- **Source:** [`../tools/operator/ni_mac/`](../tools/operator/ni_mac/), staged at
  `S:\gnuclear\2026\Jesus\Ryan\gjesus3-mount\`. Ryan runs `setup.sh` himself.
- **Traps:**
  - Never overwrite `~/.macmounter/*.conf` in place: that spawns duplicate threads. Remove the
    file, wait, then copy.
  - Do not unmount from ssh: a mount made in the GUI session refuses it.
  - One dead layer sits under the live mount. It is harmless, and a reboot clears it.
- **Retired at Box A:** once Box A pulls NI data through the tunnel, `undo.sh` removes the
  mount and the password from the Mac.

## 4. Next

1. **Irene's supervised first sync:** Ryan and Irene, at a date they choose (Ryan, 2026-10-09).
2. **Each new researcher:** run a read-only `--plan` of their folder first, and fix bad codes in
   their corrections file before their first sync.
3. **291 older `pending-db` animal records (MRI and microscopy):**
   - 103 can be recovered now, and all 103 are single-animal. They wait for Ryan's go.
   - The other 188 are not in the animal DB under their project.
   - Details are in the BACKLOG.
4. **Box A, later:**
   - the tunnel moves make-before-break, with no visit (B2);
   - one ingest web app pulls NI scans through the tunnel;
   - the corrections file becomes a web form, with `is_control` per session;
   - the Mac's gjesus3 mount is retired.

## 5. Settled — don't re-litigate

- **No hard links from the Mac.** macOS over SMB returns `ENOTSUP`.
  - Links are queued in `registries/pending_links.csv` and made from Windows by
    `tools/relink_pending.py`.
  - That queue belongs to `main` (cherry-picked 2026-08-12).
  - Hardening `pending_links.py` is assigned to the Project Manager GUI work. Coordinate before
    touching it.
- **One acquisition per reconstruction.** Reconstruction indices are append-only on the box, so
  `<anchor>/recon_<idx>` is a safe dedup key.
- **Corrections are one file per researcher on gnuclear, kept forever.** A late reconstruction
  inherits its session's corrections.
- **Cross-source dedup reuses `ni_flat.registered_recons`,** at reconstruction grain. A scan
  already loaded by another route is skipped with the standard SKIP line.
- **CT attenuation maps (`ATTMAP`) are derived files.** They go to the project's
  `outputs/derived/` with a provenance row naming their scan, and never to `raw/`.
- **Project names** (Ryan, 2026-10-08):
  - 4 digits in the code position give `AE-biomaGUNE-NNNN`;
  - anything else gives `Project-<code>`.
  - There is no DB check on the Mac; the later animal lookup surfaces bad codes.
- **Live mode asks nothing mid-sync.** One batch-wide answer cannot be right for many studies.
  `is_whole_body` is true for every Molecubes scan, and `is_control` stays unset.
- **The platform manager wants the sync demonstrable, not just readable.**
  - `--plan` and `--dry-run` show every path read and written, and touch nothing.
  - Never present the sync as "saving nothing".
  - The sync never writes into the source folder, and `pydicom` is optional.
- **Do not increase complexity.** The system is barely used *because* it is complex. A proposal
  that adds a mode, a flag or a file should be re-thought.

## 6. Open items (all in the BACKLOG)

- The two `new recon` folders in Irene's tree are not parsed. Every sync summary reports them.
- Researcher name casing (`Irene` / `irene`): the group decides the convention first.
- `session_id` and which level is the ISA investigation: a design review.
- A guard so `--nas-root` cannot silently point at production.
- The interim credential risk of Ryan's login on a shared Mac account, retired at Box A.

## 7. Related docs

| File | What it holds |
|---|---|
| [`../tools/operator/NI_LIVE_RUNBOOK.md`](../tools/operator/NI_LIVE_RUNBOOK.md) | The researcher steps and the Data Office section (staging, follow-ups) |
| [`../equipment/nuclear-imaging/live_machine_remote_access.md`](../equipment/nuclear-imaging/live_machine_remote_access.md) | The tunnel: design, security, install record |
| [`../equipment/nuclear-imaging/tunnel/`](../equipment/nuclear-imaging/tunnel/README.md) | The field card, the LaunchAgent plist, the visit notes |
| [`../equipment/nuclear-imaging/live_machine_data_layout_and_sync_rules.md`](../equipment/nuclear-imaging/live_machine_data_layout_and_sync_rules.md) | The box's folder layout and the sync rules |
| [`archive/RESUME_ni_live_2026-10-09.md`](archive/RESUME_ni_live_2026-10-09.md) | The full history of this work, verbatim |
| `archive/ni_live_operator_plan.md`, `archive/ni_live_operator_flow_plan.md`, `archive/ni_live_onbox_test_review.md` | The design plans and the 2026-08-05 on-box review (done; history) |
| `archive/ni_live_onbox_test_notes_ryan_2026-08-05.txt`, `archive/ni_live_RUN_THE_TEST_2026-06-30.md` | Ryan's notes from the August on-box test, and the June developer test script |
| `S:\gnuclear\2026\Jesus\Ryan\_archive_ni_live_2026\` | Evidence that holds real data, kept off git: the June box listing, Irene's reviewed CSVs from the on-box tests, the plan, dry-run and go logs of the first production sync |
