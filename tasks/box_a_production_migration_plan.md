# Box A: the port plan, both stages

**Status:** 🔶 DRAFT, being executed · **Rewritten:** 2026-11-05 · **Issues:** #3, #14 (guard only), #21 (decision), #26,
#27, #28 · **Owner:** Ryan Tasseff (Data Office)

**The commitment (Ryan, 2026-11-05):** "our last commitment is to port to Box A to have the same functionality as the
current version has here (that includes running all the processes that are regularly run by workstationops so a version
of workstationops, specific to gjesus3 ... needs to move there too) and to make a single unified web app for the ingests
and the project manager that runs on a single login to do work but has accounts for users." No date gate: "as soon as
possible with the least work from me."

**Done means:**
- **Stage 1:** Box A does everything this workstation does for gjesus3, on schedule, and this workstation no longer runs
  those jobs. The next-morning check passes. The validator matches dev: 0 errors, plus the 284 known warnings on a full run.
- **Stage 2:** from one URL, a signed-in person can ingest (microscopy, MRI, NI) and use the Project Manager. All work runs
  on the single login, each action is attributed to the person's account, and the exes can retire.

**Who does what.** **Agent** = the session running the port. **Box A session** = Claude Code on Box A, working from a brief
(Ryan's item 1, below). **Ryan** = by hand. No agent changes security settings (firewall, authentication, accounts, ACLs):
the agent writes one short script and Ryan runs it. Production writes (anything under the data root, scheduling or
unscheduling a job, anything on the Mac) need Ryan's direct go in the session doing them, against a matching dry run,
bundled by phase. Before each one, the agent sends the coordinator session one line; other production work on this
workstation has priority.

## What the port is

Not a data migration. The data stays on the QNAP (`\\GJESUS3\gjesus3\gjesus3-data`, mapped `J:`), and **the paths researchers
read from don't move** (B5). What moves is the operational role. This workstation becomes dev: it keeps `J:`, `/mnt/gjesus3`
and the by-hand Data Office tools, and **neither mapping changes here**, because other jobs read them daily. The guardrail is
that **no job is ever scheduled on two machines at once**: start on Box A, verify, and only then unschedule here.

Box A is an HP Z2 G1i SFF (Core Ultra 7 265, no GPU, 1 GbE). Ryan's domain account runs it, so it has the same NAS access as
here, and he has full admin on the box.

## Decided, not reopened

| # | Decision | Ruling |
|---|---|---|
| B1 | Exes keep building on the dev box | ✅ yes (2026-11-04) |
| B2 | `molecubes-tunnel` moves, re-pointed through the live tunnel | ✅ yes (2026-10-01) |
| B3 | Box A gets the `dicomifier-pilot` env | ✅ yes (2026-11-04) |
| B4 | Repo path on Box A | ✅ `C:\Users\rtasseff\projects\RDM_MFB\rdm`, with `RDM_MFB\WorkstationOps` beside it (Ryan, 2026-11-06). It replaces `D:\gjesus3\gjesus3-pilot` (2026-11-04): Box A has no D: drive, and Ryan doesn't want the gjesus3 name spread further. Outside OneDrive. |
| B5 | Paths researchers read from | ✅ don't move (2026-11-04) |

## Which job runs where

| Op | Box A | This workstation |
|---|---|---|
| `gjesus3-relink` (02:30) | ✅ moves | unschedule after Box A verifies |
| `finder-refresh` (03:00) | ✅ moves | unschedule after Box A verifies |
| `molecubes-tunnel` | ✅ moves, last | unschedule after the box dials Box A |
| `memory-sync` (new) | ✅ | ✅ |
| `wsl-backup` | ✅ set up fresh; only Ryan starts a real run | ✅ stays |
| `vps-backup`, `omero-web-forward`, `xnat-web-forward`, `oadata-web-forward` | ❌ never | ✅ stay: **don't stop, restart or break** |

**The WorkstationOps jobs only run while their user is signed in** (interactive logon, `lib\scheduled-task.ps1`). So Box A
stays signed in as Ryan, locked is fine, and after a restart someone signs in again before the jobs resume.

**`verify_checksums` is left out of Stage 1.** It was to join only if small, and it isn't. It re-reads every file: 5.26 TB
registered today, so at least 15 hours of continuous reads at the full 1 GbE, and it is new, not "same functionality". It
stays with #4.

## What git does not carry (re-read 2026-11-05)

| What | Here | On Box A | Who |
|---|---|---|---|
| Project memory, 66 files, ~390 KB, no backup today | `<slug>\memory\` under `~\.claude\projects\` | checkout of the private repo; the slug differs by path, which is fine | Agent, then Box A session |
| Animal-facility DB | `~\.my.cnf`, Windows and WSL | both sides | Ryan |
| MRI scanner and MRI archive, sections `[mri]` and `[mri_archive]` | `~\.ssh\gjesus3_mri.cred`, Windows only | same | Ryan |
| GitHub | `~\.ssh\id_ed25519` | a **new** key, separately revocable | Ryan |
| Tunnel | the box's public key in WSL `authorized_keys`; a Data Office key in WSL | the same public line; a **new** key minted on Box A, authorized through the tunnel. No private key moves | Box A session, Ryan's go |
| Python 3.13 and `tools\requirements.txt` | Store build | **python.org**, a stable path. The Store build virtualizes `%LOCALAPPDATA%` and its alias fails under Task Scheduler | Box A session |
| WSL Ubuntu, miniforge, `dicomifier-pilot` | yes, plus `xnatpic`, which stays | from `tools\dicomifier-pilot.environment.yml` | Box A session |
| `/mnt/gjesus3` in WSL | drvfs mount of `J:` | same, on Box A only | Box A session |
| `.claude\settings.local.json` | a permissions file | **Ryan copies it by hand** | Ryan |

**The repo stays off OneDrive on Box A.** Two synced working copies of one repository, `.git` included, would corrupt it.

## Stage 1: the jobs

### Phase 0: this workstation, no Box A needed

| Step | Who | Check |
|---|---|---|
| 0.1 Memory into a private repo `gjesus3-memory`: `git init` in `memory\` only, never its parent (transcripts). Secret scan done 2026-11-05: none found | Agent, on Ryan's go | GitHub shows the files |
| 0.2 WorkstationOps instance config (below) | Agent | `.\ops status` lists every op as before, under `dev-workstation`; without the file, `ops.ps1` refuses |
| 0.3 `memory-sync` op: commit if dirty, push, daily | Agent | a run pushes |
| 0.4 Production guard (#14, decision 16): `registries\.production` marker, `ingest_raw.py main()` refuses a real run against it without `--production`. Own branch | Agent; marker on Ryan's go | tests for the CLI path, and that the GUI path is unaffected |

**WorkstationOps: one repo with a per-instance file, not a gjesus3 fork.** It's the least work: the ops already share `lib\`, a
fork would double every future fix, and Box A only needs a different list. `config\instance.local.ps1` (gitignored) sets
`$INSTANCE_NAME`, `$ENABLED_OPS` and the path overrides (`$GJESUS3_REPO`, `$PYTHON`), dot-sourced after each op's config, with
a tracked `instance.example.ps1`. `ops.ps1` fails closed without it, so a fresh clone can never schedule anything; `schedule`
refuses a disabled op, and `run` refuses unless forced. Box A's list holds gjesus3's jobs only, which is the "version specific
to gjesus3" Ryan asked for.

**The order that protects the live jobs.** Tasks here run `ops.ps1` from the working tree, and a fail-closed `ops.ps1` with no
local file would stop every one of them. So: develop in a separate clone; write this machine's `instance.local.ps1` **first**,
listing every current op; check `.\ops status` in the clone; only then pull the change here. Removing an op from the list does
**not** stop its task: decommissioning always needs `.\ops unschedule <op>`.

### Phase 1: Box A base

| Step | Who |
|---|---|
| Install Claude Code, sign in at the desktop as Ryan, start Remote Control | Ryan, once |
| Python from python.org, Git, clone both repos to `D:\gjesus3\`; WSL and Ubuntu if not already there | Box A session |
| **The hard-link test:** `python tools\diagnostics\test_oslink.py \\GJESUS3\gjesus3\gjesus3-data\tmp` | Box A session, on Ryan's go |

**This test can sink the port.** Everything rests on `os.link` over SMB against the QNAP. It works in a private temporary folder
under `tmp\`: makes a file and a hard link, checks they share an inode and that edits show through both, and removes everything it
made. If it fails, stop and take it to IT. It is expected to pass: same account, same share. Run it once from WSL too, as information
only: the engine runs on Windows Python (S1).

### Phase 2: environment and code

**Who:** Box A session. `pip install -r tools\requirements.txt`; `conda env create -f tools\dicomifier-pilot.environment.yml`; the
WSL mount.

**Check:** the validator gives **the same result as a run on dev the same day**: 0 errors, and on a full run the 284 known
warnings. A different count means Box A's environment is wrong. Read-only.

### Phase 3: credentials

**Who:** Ryan copies the three files and adds the new GitHub key. Agents never print them.

**Check (Box A session):** `animal_db.credentials_available()` and a real lookup of a known animal; a read-only SFTP listing on the
scanner. **Never write to the MRI archive, and no parallel reads 08:00–18:00 Mon–Fri.**

### Phase 4: memory on Box A

**Who:** Box A session. `git init`, add the remote, fetch, check out (the directory already exists, so `clone` fails).

**Check:** a session started in the Box A repo recalls a known memory.

### Phase 5: hand over the schedule

One job at a time: `gjesus3-relink`, then `finder-refresh`. Ryan gives one go, for the phase. The standing go for the nightly relink
covers this workstation only.

1. Box A's `instance.local.ps1`, listing only that job so far. For `gjesus3-relink`, also remove the hold
   `$SCHEDULE_CONFIRMED = $false` set there on 2026-11-06. While it is false, `.\ops schedule` treats the op as manual, and
   `verify` softens two FAILs to WARNs ("checkout not on main", "tool lacks the locked re-read"). Re-run `verify` after removing
   it.
2. `.\ops verify <op>` on Box A passes.
3. `.\ops run <op>` on Box A by hand. Check the result on the NAS (the index's build time; the relink's log).
4. `.\ops schedule <op>` on Box A.
5. **Only then,** here: `.\ops unschedule <op>`, and drop it from this machine's list.
6. **Next morning:** Box A ran it, and this workstation's task is gone.

### Phase 6: the tunnel

**Who:** Box A session, with Ryan's go for each Mac write, following `equipment/nuclear-imaging/live_machine_remote_access.md` §10:
a landing pad on Box A; prove the box can reach it through the current tunnel; authorize its key; a second LaunchAgent; prove it;
only then remove the old one and `.\ops unschedule molecubes-tunnel` here. The firewall rule for the landing pad is Ryan's script.
Read the Mac rules first: free writes only in the agreed folder, and never delete what we didn't write.

### Phase 7: Stage 1 done

The next-morning checks pass; the validator matches; `02_INFRASTRUCTURE` and `11_OPERATIONS` describe the two boxes; #3 and #26
close. The agent reports to the coordinator.

## Stage 2: the web app

**Choices, from [`web_app_design_options.md`](web_app_design_options.md), taken as recommended unless Ryan says otherwise:**

| Question | Choice |
|---|---|
| Sign-in | A1 Windows sign-in; test on Box A. A1b or A3 if it stalls |
| The account it writes with | ✅ **Ryan's account (D1), the same practice as the services already running here** (Ryan, 2026-11-06): "The eventual web app we build will work just like the existing services we have on the workstationops here, we already run something for OA data archiving and the pilots, IT has been fine with all this so I want to use the same practice. It's behind the centre's firewall." The risk he was told: an app bug could change raw data his account can change. So the app's own code never modifies or deletes anything in `raw\`, and tests check that |
| How it is served | ✅ A long-running WorkstationOps service op on Box A, like the existing web forwards, inside the firewall (Ryan, 2026-11-06). No IIS and no IT certificate needed for that |
| What the login fills | B2 a small people table; `creator` from the login, never editable; `owner` defaults to it; `researcher` and `operator` keep today's rules |
| Who pressed ingest | C2 the app's action log. No registry change |
| Where the engine runs | S1 Windows Python, Dicomifier through `wsl.exe` |
| Processes | G1 one web process, one job queue; scheduled work stays in WorkstationOps |
| Serving | Superseded by the row above: a WorkstationOps service op. **Open for 2.2:** how users sign in to their accounts without IIS (Windows sign-in through the app, a directory login over HTTPS, or app accounts). A recommendation comes then |
| NI pull | P3 a nightly sweep plus "pull now", behind a review gate; unreviewed sessions get a reminder, then ingest as-is after 7 days |
| NI corrections | F2 today's CSV format, moved into gjesus3, written only by the app |
| "Add files from my computer" | "Put them in `staging\` first, then pick them here" |
| Exes | E2 overlap for one month of real use, then retire. The CLI stays for the Data Office |
| Logging | L1 write actions as counts without names until the DPO agrees; no read or search logging |

| Step | Who | Check |
|---|---|---|
| 2.1 One app: merge the microscopy/MRI GUI and the Project Manager into one Flask app, blueprints per tool, one settings function, a job queue. Runs on `127.0.0.1` against a scratch NAS; the exes keep working | Agent | every existing GUI and manager suite passes |
| 2.2 Accounts: the sign-in layer, the people table, attribution, the action log | Agent; Ryan's script for any security setting | the login shows in `creator` and the action log |
| 2.3 NI page, corrections form (the server enforces the sync-safety invariant), Box A's pull through the tunnel (#27) | Agent, Box A session; Ryan's go for Mac and production steps | a new session appears without anyone touching the Mac |
| 2.4 Serve on Box A under the chosen account; re-run the hard-link test under that account; a `web-app` op with a health page; a test instance on a scratch NAS | Box A session; Ryan's script for IIS and accounts | the URL works and a test ingest lands on the scratch NAS |
| 2.5 Cut over: operators use the URL, exes labelled fallback; undo the Mac mount (#27); confirm each instrument PC keeps its exports long enough, and that Box A can read each export share | Agent, Ryan | an operator ingests from one URL |
| 2.6 Retire the exes at the end of the overlap | Ryan's call | #27 and #28 close |

**Open, from 2.1 (on `main` as `9df2e96`):** the next exe rebuild must smoke-test the built exes themselves, not just
the rendered pages: both GUIs' templates and JS changed (base path, server mode). Until then the deployed exes are the
pre-2.1 build, which is fine. **The combined app listens on loopback only until sign-in (2.2) exists.**

## Progress

- **2026-11-05:** Ryan: "do what ever needs to be done to finish this port", and to work with the coordinator to avoid
  conflicts. The recommendations below are taken as his answers unless he says otherwise. #21: the purge is deferred
  to 2027-01-15.
- **0.4 done:** the production guard is merged (`c4b4217`), and the marker `registries\.production` was written 2026-11-05
  20:24. A real CLI run against the root without `--production` is refused (tested).
- **0.2 done:** WorkstationOps instance config (`bb3ad7f` in that repo), live on this workstation from 20:25, after the
  image-server owner agreed the time. `status --brief` was identical before and after; `verify` passes for `gjesus3-relink`
  and `finder-refresh`; the OMERO and XNAT pilots return 200. Tonight's 02:30 and 03:00 runs are the first on the new code.
- **0.1 blocked:** the agent's permission classifier refuses to upload the memory to GitHub. Ryan runs a ready script
  instead, kept outside the repo.
- **2.1 built** on `feat/web-app` (`4c8a534`), with Box A offline. `tools/webapp/app.py` mounts both GUIs unchanged in one
  process (`/ingest/`, `/ingest/mri`, `/projects/`) behind a landing page. One server-side root, refused when missing; the
  production root also needs `--production`. Tried against a scratch root only: a preview and a real ingest, and the Project
  Manager's list, create, link and copy. 63/63 suites. Sent for merge. **For 2.2:** sign-in goes in front of the whole process,
  so both apps see one `REMOTE_USER`. `creator`, `owner` and the MRI `operator` are still typed by hand. The folder browser and
  the MRI staging folder are open to anyone who can reach the server, so a non-loopback host is refused until sign-in exists.
  Behind a proxy, the redirect needs `ProxyFix`. The exes need an in-frozen smoke test at their next rebuild.
- **2026-11-06: Phase 3, the animal DB passes; WSL's Dicomifier works.**
  - Ryan copied the three credential files at 13:20; sizes match dev's, and WSL's copy is mode 600. `credentials_available()` is
    True, and the dated lookup `0525` #37 on 2026-02-24 finds DB id 17325.
  - Miniforge 26.9.4 in Box A's WSL (Ryan ran the install script; the session's permission check refused it); the
    `dicomifier-pilot` env builds on Ubuntu 26.04 with Dicomifier 2.5.3, the same as dev. `dicomifier --help` runs.
  - **The scanner passes too (13:31, read-only):** one SFTP connection with the `[mri]` credentials, guarded so it would refuse
    the archive host; it listed `/opt/PV-7.0.0/data/nmr` (3,101 entries) and `/opt/PV6.0.1/data/nmr` (154). **Phase 3 passes.**
  - Still to do: Box A's GitHub sign-in for the memory checkout (Phase 4).
- **2026-11-06: Phase 0.1 done.** Ryan ran the prepared script: the project memory (68 files) is in the private repo
  `Rtasseff/gjesus3-memory` (`2d1edde`), committed byte-exact (`core.autocrlf false`). The single-copy exposure is closed.
  Phase 4 (Box A's checkout, in the memory directory of `gj3-boxa`'s `RDM_MFB` folder) is sent to `gj3-boxa`. Syncing both ways
  waits for the `memory-sync` op (0.3).
- **2026-11-06: Phases 1 and 2 pass.**
  - **The hard-link test passes on Box A** (`test_oslink.py` on `\\GJESUS3\gjesus3\gjesus3-data\tmp`, Ryan's go, 12:5x): shared
    inode, edits both ways, and the link survives deleting the original; `tmp` is empty again.
  - **The validator matches dev exactly** (`--no-enrichment`, both started 12:52): 43,327 rows, 0 errors, 0 warnings,
    `pending-claim` 23,126, 31,662 age pairs, `/raw/` 43,327 folders and 682 tombstones.
  - Box A's WSL is Ubuntu 26.04 (dev: 24.04). Miniforge and `dicomifier-pilot` are with Ryan: the session's permission check
    refused to download and run the installer.
- **2026-11-06: the Box A session `gj3-boxa`** (Claude Code at Ryan's desktop login, Remote Control on) runs the Box A side; this
  session sends it briefs. Step 1 done: Python 3.13.17 from python.org (per-user), both repos cloned under `RDM_MFB`, the NAS
  reachable by UNC, WSL Ubuntu present. `J:` isn't mapped on Box A. Nothing needs it: the jobs and the tests use
  `\\GJESUS3\gjesus3\gjesus3-data`. A key-based SSH session from dev cannot reach the NAS (no network credentials), so NAS
  work runs in `gj3-boxa`.
- **2026-11-06: reachable, with a fixed address.** It had been switched off because it was never in the data centre. IT moves
  it there next week, and work goes ahead this weekend. Ryan set the static address IT gave: **10.10.3.195**, mask
  255.255.0.0, gateway 10.10.1.4, DNS 10.10.1.84 and 10.10.1.85. DNS name `bmg-wks-ryan.cicbiomagune.int`; "Box A" stays the
  role name. The dev workstation reaches it by SSH with a dedicated key (`ssh boxa`, password logins off for it); the key is in
  `C:\ProgramData\ssh\administrators_authorized_keys`, because Ryan is in Administrators there. Lesson: switching the adapter to
  manual clears its DNS servers, and without them domain logins fail (SSH was reset) until they are set again.
- **On hold (Ryan, 2026-11-05):** Box A is unreachable; IT may have cut its power. Ryan asked them; nothing on Box A until they
  answer. Making it reliably reachable is now a BACKLOG HIGH item, and moving the jobs (Phase 5) waits on it.
- **Phase 1 blocked:** Box A (`BMG-WKS-RYAN`, 10.10.2.161) doesn't answer on the network: no ARP reply from this workstation
  on the same subnet, so it is off, asleep or unplugged. SSH, with Ryan's domain account, is the planned route.

## What's needed from Ryan: the running list

1. **How sessions reach Box A.** Recommended: Claude Code on Box A at the desktop, with Remote Control. As far as we know, a key-based
   SSH login on Windows has no network credentials, so it couldn't reach the NAS.
2. **Go for the private memory repo** (0.1).
3. **#21, `contacts.xlsx`:** recommended, defer the purge to 2027-01-15. Box A's clone holds no local work, so re-cloning later costs
   a minute.
4. **Decision 16, the production guard** (0.4): recommended, accept.
5. **The app's single login.** Recommended: a service account from IT, with Ryan's own account only as an interim. Under his account
   a bug in the app could overwrite raw data; a service account with Tech grants physically can't. This doesn't affect Stage 1.
6. **Go for the hard-link test** (Phase 1).
