# ▶ RESUME HERE — NI live sync (read this first)

**Single entry point** for the `feat/ni-live-hardening` work. Written 2026-08-07 immediately
before migrating to a new worktree and restarting the session, so **assume the assistant has
zero memory of any of this** — everything needed is here or in the docs this points to.
**Updated 2026-10-01:** the NI Mac is now reachable from the Data Office (§0). §0 is the current
order of work and overrides anything older below that disagrees with it.
**Updated 2026-10-06:** caught up with `main`. **All four merge gates pass ON THE MAC** against a
scratch NAS with synthetic data. What is left is the gjesus3 mount and the real-data runs (§0).

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

Why: the Mac is the platform manager's (§3). Erasing, overwriting or a slow box costs us equipment access, and getting access back took a month. His 2026-10-02 OK covers the remote *sync tests* only.

**Python on the Mac:** non-interactive ssh finds `/usr/bin/python3` (3.8.9). The 3.10 the tools ran with (pyyaml etc.) is `/usr/local/bin/python3`, which a login Terminal, i.e. what operators use, finds first. Over the tunnel, call `/usr/local/bin/python3` explicitly or use `bash -l`.

---

## 0. ▶ Start here — the order of work (2026-10-01)

**The goal (Ryan, 2026-10-01).** NI researchers operate the Molecubes scanner themselves. They
should ingest as close to acquisition as possible, with as few extra steps as possible. **The first
strategy is this branch:** a sync command they run on the acquisition Mac. The ultimate goal is
step 5: they leave the room when the experimental work is done and never come back for the data.

**What changed on 2026-10-01: the Mac can be operated from here.** A reverse SSH tunnel (Mac
LaunchAgent → workstation WSL) is live and hardened. From the workstation:

```powershell
wsl -d Ubuntu -- ssh -p 2222 molecubes@localhost      # no password; lands on molecubess-iMac.local
```

The full record (how it works, checks, removal, the visit, and the Box A move) is
`equipment/nuclear-imaging/live_machine_remote_access.md` (on `main` since `4625f38`, and here since
the 2026-10-06 merge).

**Do these in order:**

1. ✅ **DONE 2026-10-06: caught up with `main`** by merge `df3874a` (303 commits, 7 conflicts resolved
   by hand; see the commit message). 40 test suites pass, plus the new end-to-end
   `tools/test_ni_live_e2e.py` (the real operator command, as a subprocess, from a copy staged the
   way gnuclear has it, against a scratch NAS; it simulates gate 3 by making `os.link` raise
   ENOTSUP). Backup tag `backup/ni-live-pre-merge-20261006`. The original plan, kept for history:
   This branch was **19 ahead / 111 behind** local `main` `48080b9`
   (2026-10-01). A dry run (`git merge-tree --write-tree main HEAD`, which writes nothing)
   conflicts in **7 files**:
   - **code:** `tools/ingest_raw.py`, `tools/ingest/metadata_sidecar.py` — resolve carefully,
     then run every test suite (§1);
   - **specs/docs:** `mfb-rdm-docs/08_METADATA.md`, `tasks/STATUS.md`,
     `equipment/historical_data_archives.md`;
   - **add/add** (both sides created the file):
     - `tasks/ni_gnuclear_active_space_plan.md` — `main`'s 550-line copy carries the finished
       historical pull (2026-08-12/13). Take `main`'s, then check whether this branch's 302-line
       copy holds anything `main` lacks.
     - `equipment/nuclear-imaging/gnuclear_active_workspace_layout.md` — both copies started from
       the same re-home on 2026-08-06. This branch then added the corrections-file content
       (`75c369a`). Take `main`'s and re-apply that addition.

   These merged cleanly in the dry run: `CHANGELOG.md`, `10_TOOLS.md`, `BACKLOG.md`,
   `tools/ingest/config.py`, `tools/operator/README.md`. Tag a backup first, as before. With 19
   commits replaying over code conflicts, consider `git merge main` (one resolution pass) instead
   of a rebase (possibly the same `ingest_raw.py` hunk several times) — Ryan's call. Either way,
   the push needs explicit permission.
2. **Get the Mac's `gjesus3` mount to stay up.** ⬅ **NEXT.**

   ✅ **DECIDED (Ryan, 2026-10-08, after talking with IT, who will not provide an account): a
   two-part solution.**
   - **(i) Now, until Box A:** mount gjesus3 with **Ryan's own login** and leave it mounted.
     - The kit is in `tools/operator/ni_mac/`, staged in `S:\gnuclear\2026\Jesus\Ryan\gjesus3-mount\`.
       Ryan runs `setup.sh` himself, because it needs his password, and `undo.sh` reverses it.
     - It saves the password in the molecubes login keychain, mounts gjesus3 at `~/.gjesus3`
       with `nobrowse` (hidden from Finder), and installs `~/.macmounter/gjesus3.conf`, so
       MacMounter re-mounts it every 120 s if it drops.
     - The launcher finds `~/.gjesus3/gjesus3-data` automatically.
     - This is the controlled Mac write Ryan approved on 2026-10-07, with his login as the
       credential.
     - **Accepted trade-offs**, stated to Ryan on 2026-10-08:
       - Anyone using the shared molecubes account has Ryan's full gjesus3 rights while it
         is mounted. The NAS logs every sync as `rtasseff`; the registry still records
         researcher and operator.
       - The password sits in a shared account's keychain.
   - **(ii) After Box A:** the Mac stops mounting gjesus3 at all.
     - Box A pulls each session through the reverse tunnel. The Mac dials Box A, and Box A's
       `localhost:2222` is the Mac's sshd.
     - Box A reads the researcher folders read-only (SFTP/rsync), runs the same ingest locally,
       and writes to gjesus3 with its own setup. Box A runs Windows, so hard links work and
       `pending_links.csv` stops filling.
     - Then `undo.sh` removes the mount and the password from the Mac. See `BACKLOG.md`,
       "Ingest from one place".

   - ✅ **INSTALLED 2026-10-08 by Ryan.**
     - **Verified from here:** `//rtasseff@10.10.1.73/gjesus3 on /Users/molecubes/.gjesus3
       (smbfs, …, nobrowse)`; `gjesus3-data/registries` is visible; `~/.macmounter/gjesus3.conf`
       matches the staged copy; the password appears in no process arguments.
     - **The launcher now resolves to `/Users/molecubes/.gjesus3/gjesus3-data`, which is
       PRODUCTION.** Every test from now on uses the kit's `ni-ingest` (pinned to `nas3`) or an
       explicit `--nas-root`.
     - **First attempt, for the record:** it failed with `Authentication error`, and the old
       script kept the saved password, so a typo could not be retried. The fix is `95f93bc`:
       setup always re-asks, and the mount reads the password from the keychain itself.
     - ✅ **Proven 2026-10-08, at Ryan's OK:**
       - **Re-mount works:** after an unmount, MacMounter re-mounted gjesus3 within 60 s with
         nobody at the Mac, reading the password from the keychain in the GUI session.
       - **Race found:** two of the three MacMounter copies mounted at the same time, stacking
         two layers.
       - **Race fixed** (deployed 17:31, the approved write): `~/.macmounter/gjesus3-mount.py`
         takes an exclusive `flock` on `/tmp/gjesus3-mount.lock`, re-checks, clears dead layers,
         then mounts. In the race test exactly **one** layer was added, and it stayed one
         through the next cycle.
       - **One dead layer remains** underneath the live mount. `umount` from ssh and from
         MacMounter both fail with "Operation not permitted". It is harmless, because the path
         resolves to the live top layer. A reboot clears it, as may an admin `umount -f`.
     - **Lessons:**
       - Do not unmount from ssh in tests: a mount made in the GUI session cannot be removed
         from ssh.
       - **Never overwrite `~/.macmounter/gjesus3.conf` in place.** MacMounter takes the
         newest file mtime in that folder as the folder's "mtime", and relaunches any `.conf`
         newer than its last look, which means duplicate threads. Remove it, wait, then copy.
         `setup.sh` now does exactly that.
   - **Things the setup relies on (checked 2026-10-08):**
     - MacMounter loads only *new* `.conf` files when `~/.macmounter/` changes, so the scanner
       mounts are untouched. Deleting the file stops its thread ("File … is gone!").
     - **Three MacMounter copies run** (PIDs from Sep 11, 15 and 21; the platform's, not ours).
       That is why the entry only force-unmounts a listed-but-dead mount.
     - Over ssh the login keychain is locked ("User interaction is not allowed"), so setup
       unlocks it with the molecubes password.
     - It is not yet proven that `mount_smbfs -N` takes the password from the keychain. Setup
       step 4 tests exactly that and stops if not. The fallback is a mode-600 password file read
       at mount time.

   **Findings, 2026-10-06** (read-only):
   - It was **not mounted** at 18:16. There was no reboot (uptime 25 days); `molecubes` is
     logged in at the console.
   - **No password is saved for it.** The keychain item for `GJESUS3._smb._tcp.local` has
     `acct = "No user account"`, so once it drops nothing can bring it back. The gnuclear mounts
     have keychain items for `nuclearuser`.
   - **MacMounter** (`/usr/local/bin/macmounter.py`, LaunchAgent `com.irouble.macmounter`, configs
     in `~/.macmounter/*.conf`) keeps only the **scanner PCs** mounted, over sshfs into
     `~/Documents/volumes/` (`remiW11` is where the researcher data lives). It manages neither
     gnuclear nor gjesus3.
   - `GJESUS3` resolves only through Bonjour (`GJESUS3.local` → 10.10.1.73), not through DNS.
     Port 445 on 10.10.1.73 is reachable from the Mac.
   - Sleep is off (`sleep 0`, `disksleep 0`).
   - **Credentials: Ryan's own call, recorded in his August notes**
     (`S:\gnuclear\2026\Jesus\Ryan\ni-live-test\notes.txt`): "I will need to get a login
     specifically for this account… It is not safe to login with my account which has full
     permissions on gjesus3." So the fix is a **dedicated gjesus3 account for the NI Mac**, with
     the operator permission profile plus registry write, and its password in the `molecubes`
     keychain.
   - The way to keep it up is Ryan's/Unai's call; both need writes on the Mac, so they need
     approval. Either (a) a MacMounter `.conf` like the existing ones, mounting
     `//<account>@10.10.1.73/gjesus3` with `mount_smbfs`, which is the platform's own pattern and
     retries forever; or (b) a Login Item, which only re-mounts at login.
   - **2026-10-07, Ryan:** he is arranging the dedicated account. **Once it exists, he approves
     one controlled write on the Mac for exactly this:** setting up the MacMounter entry, i.e.
     one `.conf` in `~/.macmounter/`, the mount folder, and the keychain item. Nothing else is
     covered.
   - Original note: Ryan reports
   it drops (cause unknown). On 2026-10-01 16:32 it was mounted as
   `//rtasseff@GJESUS3._smb._tcp.local/gjesus3` on `/Volumes/gjesus3` (SMB 3.1.1). Both
   `gnuclear` mounts use an IP or DNS name instead — a lead, not a diagnosis. Diagnose over the
   tunnel, read-only first. **Also needs Ryan's decision:** the mount uses his personal
   credentials, a superuser under the permission model, so every researcher's sync would write
   with Full rights on `raw/` rather than an operator's write-but-not-modify.
3. **Run the on-box merge gates (§4) over the tunnel.** ✅ **2026-10-06: gates 1–4 all PASS on
   the Mac**, against a scratch NAS in Ryan's gnuclear folder, using synthetic data.
   - **The test kit:** `S:\gnuclear\2026\Jesus\Ryan\ni-sync-test\`, containing `ni-ingest`,
     `tools/`, `box/ryan/` (synthetic), `nas/`, `nas2/`, `nas3/` (scratch), and `README.txt`.
     The corrections file is `Ryan\ni_corrections_ryan.csv`.
   - **The results:**
     - Gate 1: one row per recon.
     - Gate 2: the correction moved the session to 0325 with `session_extra`, while
       `original_name` stayed uncorrected.
     - Gate 3: real `Errno 45` from `os.link`, with 3 rows in `pending_links.csv`.
     - Gate 4: re-sync gave 0 new; a late `recon_2` landed in 0325 with the tracer; the
       corrections file was untouched.
   - **The footprint:** 6–35 s per run under `nice -n 19`; 1-minute load ≤2.5.
   - **Verified by snapshot:** every write landed in `Ryan\` (the kit, plus
     `ni_corrections_ryan.csv`).
   - **What is still box-only:**
     - (i) the merged code on the **real** researcher tree. A `--plan` on `irene` is a full
       recursive read over sshfs, so it needs a quiet slot; pass `--corrections` (absolute,
       into `Ryan\`) or `--plan` writes into `Jesus\irene\`.
     - (ii) a `--go` into **real** gjesus3, once step 2 is done. Each run needs Ryan's
       go-ahead.
     - In June the old code took **35 min for 127 cases** on the box, so the first real
       `--go` should cover one session (see §4).
   - **New facts:**
     - **The Mac has no `ni-ingest` command.** The new launcher `tools/operator/ni-ingest.sh`
       is staged as `<dir>/ni-ingest`.
     - **A corrections file the Mac creates is read-only from Windows.** Its owner is
       `nuclearuser`, and `GJesus` has RX on gnuclear. So researchers edit it **on the Mac**,
       where Excel and Numbers are installed. The runbook says so.
   - **❓ Open (Ryan, 2026-10-07): should researchers be able to edit their corrections file from
     other computers?** Options:
     - A. Keep it on the Mac. They run the sync there anyway, and Excel is installed.
     - B. Move the corrections files to a gjesus3 folder researchers can edit from Windows. That
       is a small `resolve_path` change plus one NAS permission, and needs the Mac's gjesus3
       account.
     - C. Ask NI/IT for group Modify on gnuclear user folders. Not ours to change.
     - D. Make corrections a form in the Box A web app, and retire the CSV.
     - Suggested: A now, D as the destination, and B only if the CLI phase runs long.
     - ✅ **Decided (Ryan, 2026-10-07): A now, D later.** D is logged in `BACKLOG.md` under
       "Ingest from one place".
   - ✅ **Real-tree `--plan` on `irene`: done 2026-10-08 17:37.**
     - **The run:** 90 s; `molecubes_gui` at 0% CPU; load unchanged. It wrote 54 session rows to
       `ni-sync-test\ni_corrections_irene_realplan.csv` (log `realplan_irene.log`) and nothing to
       gjesus3.
     - Series: 1025 ×32, 1125 ×6, 1207 ×16, including new scans from 2026-09-29 and 2026-10-07.
     - The older series (0314/0324/0525, 21 of August's 75 sessions) no longer produce
       sessions. Most likely the researcher moved them off the box to gnuclear. Unverified.
   - ✅ **The cross-source blocker below is FIXED (2026-10-08, Ryan chose per-reconstruction).**
     - **How:** the live preview reuses the existing `ni_flat` registry guard, one notch finer
       (`ni_flat.registered_recons`).
       - Skip a box reconstruction whose `(timestamp, modality, n)` is already registered by a
         row that names its reconstruction: flat pulls `_<ALGO>_<n>`, live `recon_<n>`.
       - Skip any reconstruction of a scan held by a platform-archive bundle, which has no `n`.
       - `_registered_scans`, the coarse guard the flat pulls use, is unchanged.
     - **Verified on the box:** the pull's `_<n>` is the box's `recon_<n>` (`recon_1/` holds
       `…_CT_ISRA_1.dcm`).
     - **On the real tree** (read-only dry run): **147 reconstructions to ingest, 75 already in
       production and skipped.** 4 sessions drop out entirely; the other 24 overlapping sessions
       keep their extra reconstructions.
     - **Preview count:** each skip prints the standard `SKIP … already in registry (from another
       source …)` line, so the preview counts it under "already ingested".
     - **Tests:** `test_ni_flat` covers the three production name shapes; `test_ni_live_e2e`'s
       x-source flow runs the real command. 41/41 suites pass.
   - ✅ **CT attenuation maps: DECIDED and BUILT 2026-10-08 (`ed1ba3c`).** Ryan: "if they are
     not like the reconstructions then they are not raw; they are new derived files."
     - **What it does:** a recon folder whose DICOMs are all `ATTMAP*.dcm` never becomes a
       case. After the commit, `ingest/ni_derived.py` copies it to
       `<project>/outputs/derived/CT_<subject>_<date>_<ts>_recon<n>_ATTMAP.dcm` (the retire
       tool's derivative location), SHA-256-verified and never overwriting.
     - **Provenance:** it appends one row: `input_refs` = the scan's ACQ-IDs, `parameters_ref` =
       the exact box path.
     - **It waits** until the scan has a registered reconstruction and its project exists.
     - **Light on the box:** an already-placed file is checked by size only, with no git call.
     - **Real tree** (read-only dry run): **95 reconstructions to ingest, 75 already in
       production (skipped), 52 attenuation maps to copy.**
     - **Docs:** 05 §3, 07 §2 (writer table), 10_TOOLS, the runbook, the sync rules.
     - **Tests:** the `derived` flow in `test_ni_live_e2e.py`. 41/41 pass.
   - (Was open:) **CT attenuation maps.** A box `recon_<n>/` can hold only
     `ATTMAP.dcm`, e.g. `irene/1025/260522/1025_m1/20260522095612_CT/recon_2/`.
     - **What it is:** the CT converted into PET attenuation coefficients on the PET grid, an
       input to the PET reconstruction. That is closer to a derivative than a reconstruction.
     - **Today:** the live sync registers it as its own acquisition. The flat pulls never took one.
     - **Options:** skip it (it stays on the box and in `gnuclear2$`, which is the recommendation),
       or copy it to the project folder as an associated file (new behaviour, better left to the
       Box A app).
     - Count them before the first real `--go`.
   - (Was:) ⛔ **BLOCKER for any real `--go` on a researcher folder, step 3 included: CROSS-SOURCE
     DUPLICATES.**
     - **28 of those 54 sessions are ALREADY IN PRODUCTION** from the 2026-08-13 `S:\gnuclear`
       pull (`ni_gnuclear_prod_Irene.yaml`; same subject + date, 1–3 rows each).
     - The live dedup key is `(acq_date, original_name)`, and the two sources name the same
       scan differently: live gives `<series>/<date>/<subject>/<ts>_<MOD>/recon_<idx>`, the pull
       gives `<ts>_<MOD>_<ALGO>_<idx>`. So a live `--go` would re-ingest them as new
       acquisitions.
     - **Fix before step 3:** make the live preview also skip a reconstruction already
       registered under the canonical `(timestamp, modality, recon index)`. The pull was
       built per reconstruction "to reconcile with the live box", and `ni_flat` already
       dedups by timestamp. First confirm that the pull's `_<idx>` equals the box's
       `recon_<idx>`; check one session on both sides, keeping the reads small.
     - **It does not block merging into `main`,** because merging deploys nothing.
   - Original note: Stage a fresh copy of `tools/` on
   `gnuclear` first (§4). Gate 3 needs the `gjesus3` mount from step 2. A `--go` writes to
   production, so treat each run as a production operation. ✅ **The platform manager (Unai)
   has OK'd running the sync tests on the box remotely** (2026-10-02, asked by Ryan). The rest of
   §3 still applies. Schedule runs outside acquisitions, because the box is slow.
3b. **🧹 CLEAN-UP PHASE (Ryan, 2026-10-08). Do it after step 3's first real sync, and do not
   skip it.**
   - **The rule:** lose nothing that works, especially setup steps Box A will repeat, but stop
     littering. Nothing is deleted until its content is preserved in a repo (this one or
     WorkstationOps). Deletions on gnuclear cover only files we wrote, listed group by group for
     Ryan's OK.
   - **Inventory of gnuclear `2026\Jesus\Ryan\` (2026-10-08):**
     - **Keep:**
       - `gjesus3-mount\`. Its `undo.sh` is needed until Box A; the source is
         `tools/operator/ni_mac/`.
     - **Preserve first, then remove:**
       - `tunnel.txt`, the field card rev4. Rev5 follow-ups are pending (§9 of the remote-access
         doc). It belongs in WorkstationOps or `equipment/`, because Box A repeats it.
       - `tunnel_notes.txt`, the visit notes, summarised in remote-access §9. Archive them
         verbatim.
       - `eus.biomagune.mfb.tunnel.plist`. Check that WorkstationOps holds the same file.
       - `ni-live-test\notes.txt`, Ryan's August notes. They hold the "dedicated account"
         reasoning and the unified partial-ingest checker idea, which is in BACKLOG.
     - **Check, then remove:**
       - `ni-live-test\` (249 files): the June kit, a stale `tools/` copy, `RUN_THE_TEST.md`
         (superseded by `NI_LIVE_RUNBOOK.md`), `ni_live_irene.yaml`, `p_5_output.txt`, and
         `corrections_irene*.csv` / `review_irene.csv`. **Those hold real reviewed Irene
         sessions; consider seeding her real corrections file from them before deleting.**
       - Top level: `review_irene.csv`, `p0_p2_output(s).txt`, and `datapath.txt` (38 MB from
         June; find out what it is first).
     - **Remove once the sync's production home exists:**
       - `ni-sync-test\` (550 files): the test kit, the scratch `nas\`, `nas2\` and `nas3\`, and
         the synthetic `box\`.
       - `ni_corrections_ryan.csv` (synthetic sessions).
   - **Elsewhere:**
     - **The Mac:** the interim mount (`~/.gjesus3`, `~/.macmounter/gjesus3.conf`, the keychain
       item) stays until Box A, then goes via `undo.sh`.
     - **Git:** prune the local `backup/ni-live-*` tags after the merge into `main`.
     - ✅ **The remote is done.** Ryan force-pushed on 2026-10-08 (`44512ec...ea2f68f`), so the
       August pre-rebase history is gone from origin. It survives locally in
       `backup/ni-live-pre-rebase-20260807`.
     - **The `ni-tunnel-live` worktree** is merged, but it belongs to its own session.
     - **`J:\gjesus3-sandbox`:** its shared registry is stale (§7, `project_hint` header). That
       is not ours to purge without asking.
   - **Docs:**
     - Shorten this RESUME (475 lines) to a current-state page. History goes to the CHANGELOG.
     - Move `ni_live_onbox_test_review.md` (661 lines), `ni_live_operator_plan.md` (397) and
       `ni_live_operator_flow_plan.md` (197) to `tasks/archive/` with pointers, now that the work
       they planned is done and verified. Nothing is deleted.
   - **❓ Decision needed before roll-out:** the sync code's **production home** on gnuclear,
     i.e. where researchers' `ni-ingest` lives.
     - It must sit under `<year>\<group>\`, so `resolve_path` puts each researcher's corrections
       file in their own folder. For example `2026\Jesus\_gjesus3-sync\`.
     - At year-end, staging under the new year changes nothing for existing files, which are
       found in any year.
4. **Merge; operators start using it** (`tools/operator/NI_LIVE_RUNBOOK.md`). The merge into
   `main` can come before 3b: merging deploys nothing, because researchers run the copy staged on
   gnuclear. Ryan is aiming for 2026-10-09, while `main` finishes its own work. Merge `main` into
   this branch again first; it was 37 behind `origin/main` on 2026-10-08.
5. **Then, not now:** the Box A port, which takes the tunnel along, make-before-break through the
   live tunnel with no visit (B2, decided 2026-10-01). After it, **one ingest web app on Box A**
   for every instrument: microscopy via network drives, MRI via SFTP, NI pulled through the
   tunnel. Users behind the firewall log in, and the server works with the system's setup and
   permissions on their behalf. A workstation-hosted version would work today, but it cannot
   serve everyone, because a tunnel cannot be set up on every user's machine. Details: `main`'s
   `tasks/BACKLOG.md` "Ingest from one place" and `tasks/box_a_production_migration_plan.md`
   (both on `docs/ni-tunnel-live` until it is merged).

**Tunnel do's and don'ts:**
- Don't run `WorkstationOps\setup\test-tunnel-path.sh` while the Mac is connected. Step 6 fails,
  because the Mac holds port 2222, and step 7 passes for the wrong reason. To check the live
  tunnel, run `wsl -d Ubuntu -- bash -c 'nc -w 4 localhost 2222 </dev/null | head -1'`, which
  should print `SSH-2.0-OpenSSH_8.1`.
- When scripting remote commands through `wsl.exe -- ssh … '…'`, `$(…)` expands on the
  workstation, not the Mac. Use a script with `ssh … 'bash -s' <<'EOF'`.
- After a Mac reboot, the tunnel returns only once someone logs into `molecubes`: there is no
  auto-login.

---

## 1. Where things stand

- **Branch `feat/ni-live-hardening`**: ✅ **0 behind `main` as of the 2026-10-06 merge `df3874a`**
  (main `2466e83`). It was 19 ahead / 111 behind on 2026-10-01. **Catch up again by merging `main`**
  (not by rebasing). The branch has a merge commit now, and a rebase would flatten it. Last rebased onto **local** `main`
  `85af9d6` on 2026-08-12; before that `origin/main` `6b2ef41` on 2026-08-07 and `dde99fc` on
  2026-08-06 — we had silently drifted 69 commits behind once, don't let that happen again.
- **⚠️ REBASE ONTO LOCAL `main`, NOT `origin/main`.** As of 2026-08-12 local `main`
  (`85af9d6`) is **3 commits ahead of `origin/main`** (`b882e4a`) and is the only one that
  has the pending-links adoption. Rebasing onto `origin/main` silently misses it and
  reintroduces a second deferred-link queue. Check both: `git rev-parse main origin/main`.
- **`origin/feat/ni-live-hardening` is current** (force-pushed by Ryan, 2026-10-08). Future
  pushes are ordinary fast-forwards, because the branch now catches up by merging, not by
  rebasing. **Pushing still requires explicit permission.**
- **NOT merged, deliberately.** Merge waits on the on-box test (§4).
- All 20 test suites green, NI ones included: `tools/test_ni_corrections.py` (48 checks),
  `test_ni_per_recon.py`, `test_pending_links.py`, `test_ni_live_discover.py`,
  `tools/ingest/test_registry_fields.py`.
- Backup tags: `backup/ni-live-hardening-pre-rebase` = `f2ee114` (pre-2026-08-06);
  `backup/ni-live-pre-rebase-20260807` = `2909b31`; `backup/ni-live-pre-rebase-20260812`
  = `988e237`.
- **Rebasing in this worktree leaves a `rebase-merge` dir git can't delete** — OneDrive marks
  it ReadOnly, so git reports "currently rebasing" after a *successful* rebase. Clear ReadOnly
  and remove `…/.git/worktrees/ni-live-hardening/rebase-merge`; do **not** `git rebase --abort`,
  which would throw the rebase away.

**Run the tests as `PYTHONPATH=tools python tools/<name>.py`** — they are hand-rolled scripts,
not pytest.

## 2. The plan, in order

### (a) Finish the NI live sync so it works exactly how operators need — CODE COMPLETE
Keep using the current approach: code lives in this repo, runs from the shared NAS
(`gnuclear`), writes to `gjesus3`. **It has been running on the Mac fine.** Do not start
simplifying yet — get it correct first, then trim.

**✅ The last open design item — where the corrections CSV lives — is BUILT (2026-08-07).**
One file per researcher,
`<gnuclear>/<year>/<group>/<researcher>/ni_corrections_<researcher>.csv`, off gjesus3 and
onto the share the code already runs from. `resolve_path` derives the root/year/group
**from the running code's own path**, so it works unchanged on the Mac (a `/Volumes/…`
mount) with no env var and no flag, and the resolved path is logged every run. An existing
file is reused wherever it already sits, so a correction never expires at year-end.
The two files collapsed into one: `--plan` (now a bare flag) appends only unseen sessions
and never touches an existing row; every run reads the file; nothing merges or rewrites it.
The blank-cell rule is gone with the merge that required it. Full rationale:
`tasks/ni_live_operator_flow_plan.md` §3.7.

**Phase (a) is now code complete. What remains before merge is not code — it is running
it on the box (§4).**

### (b) Simplify what runs on the NI acquisition Mac — NEXT, NOT NOW
The idea to explore (Ryan's): copy a temporary dataset to a **gjesus3 staging location** and
automate the processing from there. The Mac-side then only needs to *find new reconstructions
and copy them* — realistically ~100 readable lines — while the heavy machinery runs off his
equipment entirely. Hard links work on the Windows side, so the deferred-link handling would
stop mattering too.

**This is not the "users run it from the Windows workstation" idea — that was rejected**
(extra step, users won't adopt it). The user still runs one command on the Mac; only the
*location of the code* changes.

Longer term this is all expected to be superseded by a dedicated box everyone can reach
(plus a tunnel, or an ethernet cable between the two machines). **Now concrete (2026-10-01):**
that box is Box A, the tunnel exists and moves there, and the plan is one ingest web app on it
(§0 step 5). Once a server can pull through the tunnel, nothing needs to run on the Mac at all. So
revisit (b) only if (a)'s footprint on the Mac becomes the blocker before Box A is ready.

## 3. The platform-manager constraint (important, easy to lose)

The NI Mac belongs to a platform manager whose job is keeping the equipment running. He is
not a CS person; to him the box is where numbers come out of the PET hardware.

- **He does not mind what Ryan runs while physically present.** His concern is **what we leave
  behind and ask operators to run.**
- ✅ **2026-10-02: he OK'd running the sync tests on the box remotely**, over the tunnel (asked by
  Ryan). This covers remote runs of the sync tests, not anything else; the concerns below still
  stand.
- He has **expressly asked to read the code.** Platform managers here generally want "a few
  lines plus references to well-accepted dependency packages."
- **He cannot read what exists**: the five main files are **4,633 lines**
  (`ingest_raw.py` alone is 1,943). No framing fixes that — it is why phase (b) exists.
- He is not worried about a few small files being written. He is worried about (i) code too
  big to understand, (ii) anything that erases or overwrites, (iii) anything long-running —
  **that box is slow**.
- **`pydicom` is NOT required.** `tools/ingest/ni_metadata.py:32` — it is optional and
  degrades gracefully (headers skipped, ingest still works). Nothing had to be installed on
  the Mac; the staged `tools/` on the NAS just ran.
- **Verified: the ingest never writes to the source folder.** `delete_source_after_ingest:
  false` is hard-set in `molecubes_ni_live.yaml`, and no code path writes into `staging_dir`
  (the only reference is a relative-path computation in `config.py`).
- **Decision made 2026-08-06:** do **not** present the tooling as "just processing code that
  doesn't save anything" to get past an audit. It does save things; if he discovers that, the
  loss is permanent equipment access, not an argument. The better answer is **demonstrable
  rather than readable** — a mode that prints every path it will read and write and touches
  nothing, which he can run himself. Stronger than reading code, since code doesn't prove
  runtime behaviour.

## 3a. The deferred-link queue now belongs to `main` — do not re-own it

**2026-08-12, Ryan.** The first commit of this branch (`0418ca6`, `pending_links.csv` +
`relink_pending.py`) was **cherry-picked onto `main`** so the Project Manager GUI could use
the same queue instead of growing a second one. Merged as `85af9d6`. Consequences:

- **`0418ca6` is redundant here.** On the 2026-08-12 rebase git dropped it automatically
  (*"skipped previously applied commit"*). If a future rebase conflicts on it instead,
  **`git rebase --skip` is the right answer.** Everything after it replays normally.
- **One line differs from this branch's original, deliberately — do NOT revert it.**
  `ingest_raw.py` now queues with `project_id=project_id`, not `proj_id or project_hint`.
  `project_hint` was retired repo-wide on 2026-08-02 and `proj_id` is only bound inside the
  earlier resolve block, so the original was a latent `NameError` on the deferred-link path
  (it survived only because `or` short-circuits when `proj_id` is truthy). Ryan's fix is
  `6276a81`; verified present after the rebase.
- **`pending_links.py` hardening is assigned to `feat/project-manager-gui` — do not
  duplicate it.** It takes no `registry_lock` and uses a non-pid temp name (it mirrors
  `pending_dicom.py`). Fine for one operator, unsafe behind a multi-user GUI. **Coordinate
  before touching that file**; the same concern is logged here as the S7 backlog item.

## 4. Merge gates — still ON THE BOX, but no longer unproven

No `--go` ingest has **ever** run on the box. The 2026-08-05 session stopped at the read-only
`--plan` step. Before merging, prove **on the box**:

| # | Gate | Off-box status |
|---|---|---|
| 1 | A real `--go` producing `.../recon_N` registry rows (one acquisition per reconstruction). | ✅ passes locally (2026-08-07) |
| 2 | A corrected session showing a `session_extra` block in its `metadata.json`. | ✅ passes locally |
| 3 | `registries/pending_links.csv` written with `ENOTSUP` / `darwin` rows. **This file exists on neither NAS today.** | ✅ simulated off-box (`test_ni_live_e2e.py`), and ✅ **on the Mac 2026-10-06** with a real `Errno 45` against a scratch NAS on gnuclear. Still to see: the same on the gjesus3 mount (§0 step 2). |
| 4 | A second sync: idempotent (0 new), and a **late reconstruction registering into an already-corrected session with the correction still applied.** | ✅ passes locally |

Gate 4 is the acceptance test for the persistent-corrections change and is the one most
likely to be got wrong. **It now passes** against a synthetic tree + throwaway NAS
(2026-08-07): `recon_1` added after the fact became `ACQ-20260212-CT-002`, routed to the
*corrected* `AE-biomaGUNE-0325` with `session_extra={tracer,dose}` inherited and **nothing
re-entered**, while `original_name` kept the uncorrected REMI path and the corrections file
was not modified by three `--go` runs.

**A local pass is not a box pass.** What the box still has to prove is everything the Mac
does differently — SMB latency, `ENOTSUP` on `os.link` (gate 3), the real 141-scan tree, and
`resolve_path` landing on the real `gnuclear` mount rather than a fake one. Do not treat
gates 1/2/4 as closed; treat them as *no longer the risky part*.

**Operator instructions are `tools/operator/NI_LIVE_RUNBOOK.md`** — two commands. The old
`RUN_THE_TEST.md` staged at `S:\gnuclear\2026\Jesus\Ryan\ni-live-test\` is a *developer* test
script, is from 2026-06-30, and predates everything below. **Stage a fresh copy of `tools/`
there before the next box session.**

## 5. What landed on this branch (why, not just what)

| Commit | Change |
|---|---|
| `0fb84db` | Dropped `session_id` / `sample_id` from the corrections CSV — both are **derived** for NI, so offering them as editable columns created a competing source of truth. Real damage: a project correction re-derived `project_hint` while a hand-set `sample_id` went stale. Also stopped prompting for condition/anatomy on read-only passes (`--plan` / `--dry-run`), and locked `anatomy.is_whole_body: true` in the live template — Molecubes scans the whole animal every time, so it was never a per-batch question. `condition:` is deliberately NOT defaulted. |
| `1137561` | **Corrections persist** instead of living in a throwaway per-run file. NI reconstructions arrive late and land in sessions that were already corrected, so the old design silently re-applied the *uncorrected* values to those new acquisitions. Stored at `registries/ni_session_corrections.csv` — **superseded below.** |
| (2026-08-07) | **One corrections file per researcher, on `gnuclear`, append-only.** Moved off `gjesus3/registries/` to `<gnuclear>/<year>/<group>/<researcher>/ni_corrections_<researcher>.csv`, and the two-file worksheet→store merge collapsed into a single file the operator owns and edits forever. The merge was the only thing that needed a blank-cell rule; both are gone. `--plan` is now a bare flag that appends unseen sessions and touches nothing else. Path is derived from the running code's own location (no env var, no flag, works on the Mac's `/Volumes/…` mount) and logged every run; an existing file is reused across years so a correction never expires. |
| `6fda90f` | `--root` accepts either the parent of the researcher folder or the folder itself, and **raises** when it matches neither (it used to walk nothing, exit 0, and write a header-only CSV that read as "this researcher has no data" — that cost a slot at the box). Added `NI_LIVE_RUNBOOK.md`. Marked `ni_live_discover.py` a data-office diagnostic, not an operator step. |
| `a7be9d8` | `--plan` no longer walks the source tree twice (`preview_batch` was re-running the identical recursive glob just to display a count `--plan` never prints). **Structural fix, NOT measured on the box** — if `--plan` is still slow there, profile ON the box first. **Do not add a cache.** |
| `46e2120` | Gate-0 closed (see §6), operator-flow plan, on-box test review, production-cleanup list. |

Earlier commits (rebased): one acquisition per reconstruction, `--live` mode (no per-batch
YAML), corrections + tracer metadata. **The deferred-project-links commit is no longer one
of them** — it was cherry-picked onto `main` and is now upstream of this branch (§3a).

## 6. Facts established, don't re-litigate

- **Gate-0 is CLOSED and the answer is NO.** `os.link` on the NI Mac's SMB mount returns
  `ENOTSUP` (tested on the box 2026-08-05, python 3.10.5 darwin). macOS over SMB has no hard
  links. Already handled by deferring to `pending_links.csv`, drained from Windows by
  `tools/relink_pending.py`. This needed no access slot and is **not** a task for the SSH
  tunnel — `NI-RA-05` in `equipment/nuclear-imaging/live_machine_remote_access.md` can close
  against it.
- ~~**Remote access to the box is NOT established.**~~ **Superseded 2026-10-01: it is
  established** — the tunnel is live and the Mac can be operated from the workstation (§0).
- **Reconstruction indices are append-only** on the box — a new reconstruction always lands in
  a new, higher-numbered `recon_<idx>/`, and an existing one is never overwritten. This is why
  `<anchor>/recon_<idx>` is a safe dedup key and why no content hashing is needed.
- **Counts from the 2026-08-05 run are correct, not a bug**: 141 scans → 78 sessions → 75
  planned. `review_irene.csv` is one row per acquisition; the corrections CSV is one row per
  session.
- **ISA / vocabulary question is OPEN and does not block merge.** What is `1207`? Documented
  only as `series_id` (a positional name we invented) in
  `equipment/nuclear-imaging/internal_ni_data_handling_workflow_notes.md:29`. Ryan has since
  confirmed with a source: **NI calls it the Series ID, and it is also the internal
  biomaGUNE funded-project ID, recorded because it is reportable to granting agencies.** The
  AE protocol code (e.g. `0522`) legitimately serves three roles — animal-ethics protocol,
  animal-facility DB key, and (by researcher preference, not enforced) the project name. None
  of that should change. Needs documenting; the "which is the ISA Investigation" choice is a
  backlog item.
- **`session_id` needs re-thinking (backlog, high priority).** It was created for DICOM
  organisation and was mapped to the ISA "study" level — **that mapping is wrong.** A session
  is one animal in one sitting; an ISA study involves many animals. Also worth asking whether
  it belongs at registry level at all, since not every data source has one. Ryan's call,
  2026-08-06.

## 7. Open items NOT on this branch

- ✅ **DONE — the two synthetic production acquisitions are gone.** `ACQ-20260212-CT-001` /
  `-002` (from the 2026-06-29 verification run that pointed `--nas-root` at `J:\gjesus3-data`
  instead of a throwaway NAS) were removed and verified against production on 2026-08-06:
  8 rows across 5 registry CSVs, both raw folders, and the auto-created `PROJ-0051` /
  `AE-biomaGUNE-0325` in full; 0 residual references, 0 `validate_registries` errors; backup
  off-NAS at `C:\Users\rtasseff\temp\gjesus3_ni_testdata_removal_20260806\`. Recorded on `main`
  in `c92a60f`, which this branch now contains. `tasks/ni_prod_testdata_removal.md` is history.
- **Backlog, high priority — `pending_dicom_regen.csv` header drift.** The live file has 9
  columns (`nonimage_marker`), the code expects 8, `_assert_header` raises, and
  `ingest_raw.py:1034` swallows it — so the DICOM regeneration queue is **write-broken in true
  production right now**. Evidence favours adopting the column. Deliberately deferred: we were
  too far behind main to take it on.
- **Backlog** — a unified checker for the three partial-ingest worklists (DICOM regen, hard
  links, DB subjects), run on a schedule from the Windows workstation; the `new recon/` folder
  depth mismatch; a guard so `--nas-root` can't silently point at production.
- The historical `S:\gnuclear` pull is paused and prioritised behind this work. See
  `tasks/NOTE_to_historical_pull_work.md`.

## 8. Working agreements

- **Do not increase complexity.** Ryan, repeatedly: the system is barely used *because* it is
  complex. Every change in phase (a) should be a removal or a merge of existing steps. If a
  proposal turns into "add a new mode/flag/file", stop and re-think.
- **Commit freely; never push without explicit permission** (per `CLAUDE.md`).
- **Stay current with `main`** — check `git rev-list --count HEAD..origin/main` at the start of
  a session. We hit 69 behind once; the rebase was clean but it cost real time.
- Plans and handoffs go in `tasks/`. Wait for explicit go-ahead before executing them.
- `tasks/STATUS.md` is the current-state entry point (**not** `tasks/tasks.md`, which was
  archived to `tasks/archive/tasks.md` — never edit archived files).

## 9. Related docs

| File | What it holds |
|---|---|
| `tasks/ni_live_operator_flow_plan.md` | The operator-flow design + what landed against each section |
| `tasks/ni_live_operator_plan.md` | The older, larger design + history doc (per-recon model, decisions D1–D6) |
| `tasks/ni_live_onbox_test_review.md` | Full findings from the 2026-08-05 on-box run |
| `tasks/ni_prod_testdata_removal.md` | Production cleanup hand-off list |
| `tools/operator/NI_LIVE_RUNBOOK.md` | Operator-facing instructions (two commands) |
| `equipment/nuclear-imaging/live_machine_data_layout_and_sync_rules.md` | The box's actual folder layout, from a 295k-line path dump |
