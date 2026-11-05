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
| B4 | Repo path on Box A | ✅ `D:\gjesus3\gjesus3-pilot` (2026-11-04) |
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
| **The hard-link test:** `python tools\diagnostics\test_oslink.py J:\gjesus3-data\tmp` | Box A session, on Ryan's go |

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

1. Box A's `instance.local.ps1`, listing only that job so far.
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
| The account it writes with | **Ryan's call, pending (below):** D2 service account, D1 his account only as an interim |
| What the login fills | B2 a small people table; `creator` from the login, never editable; `owner` defaults to it; `researcher` and `operator` keep today's rules |
| Who pressed ingest | C2 the app's action log. No registry change |
| Where the engine runs | S1 Windows Python, Dicomifier through `wsl.exe` |
| Processes | G1 one web process, one job queue; scheduled work stays in WorkstationOps |
| Serving | H1 IIS and an IT name and certificate. H3 plain HTTP only for a first internal version, and only with A1 |
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
