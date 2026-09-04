# Box A — moving gjesus3 RDM production off the dev workstation

> 🔶 **DRAFT — a plan for review. Nothing here has been executed.**
> **Raised:** 2026-09-04 · **Owner:** Ryan Tasseff (Data Office)
> **Companion satellite:** `projects\DataInfra\image-server\` owns the *box* (procurement,
> IT engagement, rack/power/network). This file owns the *port* — what moves off this
> workstation onto it, in what order, and how each step is verified.

> ⛔ **Timing gate.** `image-server\README.md` states that racking, provisioning, and
> migrating services off Ryan's workstation are **deliberately unscheduled until after the
> 10 September 2026 leadership meeting** — *"Do not start it earlier without Ryan saying
> so."* This plan is written to be ready on that date, not to pre-empt it. **Phase 0 is the
> exception**: it runs on the dev workstation, has no Box A dependency, and fixes a
> data-loss exposure that exists today.

---

## 1. What this port actually is

Box A is an **HP Z2 G1i SFF** (Core Ultra 7 265, no GPU, 1 GbE — €1,879 ex-IVA), delivered
2026-09-03. Its job, in Ryan's words: *"like an app the users can log into on a dedicated
box to do basic RDM."*

The port is **not** a data migration. All research data already lives on the QNAP
(`\\GJESUS3\gjesus3\gjesus3-data`, mapped `J:`) and stays there. What moves is the
**operational role**: the scheduled jobs, the tooling environment, and the credentials that
make this workstation the machine that runs gjesus3 RDM.

**Target end state:**

| | Runs the RDM system | Runs everything else |
|---|---|---|
| **Box A** (prod) | ✅ all of it | — |
| **This workstation** (dev) | ❌ none of it | ✅ backups, the OMERO + XNAT image-server trials |

**The dev box is not sandboxed, and shouldn't be.** It keeps `J:` mapped and keeps the
ability to run Data-Office operations (ingests, backfills, recovery tools) by hand, because
that is Ryan's actual job. What moves is everything **scheduled** and **serving**. The
guardrail is therefore not network isolation — it is making sure no job is *scheduled* on
two machines at once (§4.1).

---

## 2. Settled ground (confirmed 2026-09-04)

These were open questions; they are now answered and need no re-litigating.

| | Answer |
|---|---|
| **Account on Box A** | Ryan's own domain account. NAS ACLs (`CICBIOMAGUNE\GJesus` group, `J:` write paths) therefore carry over unchanged — no IT grant needed. |
| **Drive mappings** | Already mapped to the same letters and targets as here. |
| **Repo location on Box A** | **Plain local disk, NOT OneDrive** (see §4.3). |
| **Image-server trials** | **Stay on this workstation.** Box A is not sufficient to host OMERO + XNAT. ⚠️ This *contradicts* `image-server\README.md`, which still says the trials migrate off Ryan's workstation to Box A — see §8. |
| **Repo access** | Both repos are on GitHub: `git@github.com:Rtasseff/gjesus3-pilot.git` and `git@github.com:Rtasseff/WorkstationOps-PS.git`. |

---

## 3. What does NOT come down from git

Cloning the two repos gives you the code and the docs. It gives you none of the following,
and the port is almost entirely about this list.

| | What | Where it lives now | Size / note |
|---|---|---|---|
| **Memory** | Claude project memory — 46 files | `C:\Users\rtasseff\.claude\projects\C--Users-...-gjesus3-pilot\memory\` | 292 KB. **Outside OneDrive, not in git → one copy, zero backups.** Directory name is the repo's absolute path, mangled. See §4.2. |
| **Creds** | Animal-facility DB (read-only) | `C:\Users\rtasseff\.my.cnf` **and** WSL `~/.my.cnf` | 104 B each. Path overridable via `GJESUS3_MYCNF` (`tools/animal_db.py:81`). |
| | MRI scanner SFTP | `C:\Users\rtasseff\.ssh\gjesus3_mri.cred` | 69 B, INI `[mri]`. **Windows only — WSL does not have it.** A deliberate shared copy also sits on the NAS at `tools\docs\` (see the memory note; do not re-flag or move it). |
| | GitHub | `~\.ssh\id_ed25519` | **Mint a NEW key for Box A** — separately revocable. |
| | Molecubes tunnel | WSL `~/.ssh/id_ed25519_molecubes_tunnel` | Only if that op moves (§5). |
| | ReDIB VPS | `~\.ssh\id_ed25519_vps` | Not gjesus3. Stays here. |
| **Windows env** | Python **3.13.14** + the 7 packages in `tools/requirements.txt` | Store build here — **do not repeat that on Box A**, see §6 Phase 1 | pydicom, pyyaml, tqdm, czifile, pymysql, paramiko, flask |
| **WSL env** | Ubuntu 24.04.3 LTS, miniforge3, envs `dicomifier-pilot` + `xnatpic` | `dicomifier-pilot` rebuilds from the committed `tools/dicomifier-pilot.environment.yml` — that one is free. `xnatpic` is the XNAT trial and **stays here**. |
| **Mount** | WSL sees `J:` as `/mnt/gjesus3` (drvfs) | Needed by the WSL-side ingest and regen paths. |
| **Schedule** | Task Scheduler job `WorkstationOps-finder-refresh`, daily 03:00 | Registered in Windows, **independent of the repo** — see the trap in §4.1. |
| **Tool permissions** | `.claude\settings.local.json` (2.5 KB, gitignored) | Copying it saves re-approving a long permission list on Box A. |

---

## 4. The three problems this port creates — and the answers

### 4.1 WorkstationOps has to know which machine it is

**The problem.** All six op configs are **tracked in git** (`config/*.conf.ps1`) with **no
local-override mechanism**. `config/finder-refresh.conf.ps1` hard-codes this machine's paths
at line 12 (`$GJESUS3_REPO`) and line 20 (`$PYTHON`). Box A pulls that config and gets the
wrong paths; edit it on Box A and you have a permanently dirty tree and a recurring merge
conflict on every pull. And with the op set now genuinely *different* per machine — RDM ops
on Box A, backups and image-server forwards here — one shared config cannot express both.

**The answer (Ryan's shape, 2026-09-04): a gitignored per-instance file that declares which
operations this instance runs.**

```powershell
# config\instance.local.ps1   -- GITIGNORED, one per machine
$INSTANCE_NAME = "box-a-prod"          # printed in every `.\ops status` header
$INSTANCE_ROLE = "prod"                # dev | prod (informational)
$ENABLED_OPS   = @("finder-refresh", "wsl-backup", "memory-sync")

# per-op path overrides for THIS machine (dot-sourced AFTER the op's own conf, so it wins)
$GJESUS3_REPO  = "D:\gjesus3\gjesus3-pilot"
$PYTHON        = "C:\Program Files\Python313\python.exe"
```

Ship `config\instance.example.ps1` **tracked** as the template, and add `*.local.ps1` to
`.gitignore`.

Behaviour changes in `ops.ps1`:

- Load `instance.local.ps1` first. **If it is missing, fail closed** with a message pointing
  at the example — no op lists, runs, or schedules. This is the property that matters: a
  fresh clone on a new machine must never silently schedule the whole set.
- `status` shows only enabled ops, and prints `$INSTANCE_NAME` in the header so you always
  know which box you are looking at.
- `schedule` refuses a disabled op. `run` refuses unless `-Force`.
- `verify` checks that each **enabled** op's paths resolve on this machine.

> ⚠️ **The trap that will bite if it is missed.** Removing an op from `$ENABLED_OPS` does
> **not** stop an already-registered Windows scheduled task. Decommissioning `finder-refresh`
> on this workstation needs an explicit **`.\ops unschedule finder-refresh`** (the verb
> exists — `ops.ps1:307` help, `ops.ps1:331` dispatch, `Unregister-OpTask` at
> `lib/scheduled-task.ps1:95`). Get this wrong and both machines rebuild and write
> `registries\index.html` to the same NAS path at 03:00.

### 4.2 The memory has no backup, and it is keyed to the repo path

**The problem, restated because it is the sharpest thing in this document.** 46 files,
292 KB, at `C:\Users\rtasseff\.claude\projects\<slug>\memory\`. That path is **outside
OneDrive** and **not in git**. It exists in exactly one place, on one disk, and nothing
copies it anywhere. Separately, `<slug>` is the repo's absolute path with separators
replaced — so a repo at a different path on Box A produces a different slug, and the memory
is simply invisible there.

**Junction is OUT.** The obvious fix — junction the slug's `memory\` at a folder inside the
repo — is dead. **OneDrive silently stops syncing when it meets a reparse point in a synced
tree** (observed first-hand: sync stopped, took a long time to notice and longer to
diagnose; removing the junction restored it). The dev repo lives in OneDrive, so that
configuration is exactly the one that burned us. Not worth re-testing on the machine that
holds the only copy of the thing we are trying to protect.

**The answer: make `memory\` its own git working tree, in place. No reparse points anywhere.**

```
C:\Users\rtasseff\.claude\projects\<slug>\memory\   <-- git init here, this IS the working tree
    .git\                                            <-- inert to Claude Code
    MEMORY.md
    *.md  (45 memory files)
```

Push to a **new private** GitHub repo (`gjesus3-memory`).

Why this over the alternatives:

- **No OneDrive interaction at all.** `C:\Users\rtasseff\.claude\` is not in the synced tree,
  on either machine. The problem in §4.2 never arises because OneDrive never sees any of it.
- **No reparse point**, so nothing to silently break.
- **No copy-sync lag or conflict window** — unlike a mirror script, there is one copy of the
  truth and git is the transport, which is already how everything else here is backed up.
- **`.git` inside `memory\` is inert** — Claude Code reads and writes `*.md` there and does
  not care what else is in the directory.
- **Its own repo settles the sensitivity question.** The memory names people, animal protocol
  codes, DB structure, and the shared-credential situation. As a separate private repo it is
  private regardless of what `gjesus3-pilot`'s visibility is or later becomes.

Two details that are easy to get wrong:

- **Box A's slug is different, and that is fine.** Each machine has its own
  `<slug>\memory\` directory holding a checkout of the same branch.
- **Do not `git init` the slug's *parent*.** That directory also holds session transcript
  `.jsonl` files — large, and full of raw conversation. Only `memory\` goes in the repo.
- On Box A the target directory already exists (Claude Code creates it), so plain
  `git clone` into it fails. Use `git init` + `git remote add` + `git fetch` +
  `git checkout`.

**Make the backup automatic**, or it depends on someone remembering: a small
`memory-sync` op in WorkstationOps — commit if dirty, push, daily — enabled on both machines
under the §4.1 mechanism.

### 4.3 OneDrive must not follow the repo to Box A

Already decided, recorded here because the failure mode is severe and non-obvious. If Box A
signs into the same OneDrive account and syncs `projects\DataInfra\`, the two machines end up
holding **two live working copies of the same git repository — `.git` included — synced
byte-for-byte between them.** That corrupts git.

Box A puts the repo on plain local disk (`D:\gjesus3\gjesus3-pilot` or similar). Side
benefits: no ReadOnly+ReparsePoint worktree-delete lock, and no Files-On-Demand placeholders
silently defeating recursive greps.

---

## 5. Which operation runs where

| Op | Box A | Dev workstation | Why |
|---|---|---|---|
| `finder-refresh` | ✅ | ❌ **`.\ops unschedule`** | The one true RDM production job. Rebuilds the researcher Finder from the registry to the NAS, daily 03:00. |
| `memory-sync` *(new, §4.2)* | ✅ | ✅ | Small, wanted on both. |
| `wsl-backup` | ✅ (set up fresh) | ✅ keep | Per-machine by nature — each box backs up its own WSL. |
| `vps-backup` | ❌ | ✅ keep | ReDIB Portal, not gjesus3. Needs `X:` and the VPS key. |
| `omero-web-forward` | ❌ | ✅ keep | Image-server trial. **Box A is not sufficient to host it.** |
| `xnat-web-forward` | ❌ | ✅ keep | Same. |
| `molecubes-tunnel` | ❓ **decide** | ✅ for now | See below. |

**`molecubes-tunnel` is the one RDM op with a real cost to move.** The Molecubes PET/CT
acquisition box (`192.168.0.180`) is NAT'd and cannot be reached inbound — it **dials out to
this workstation** and the tunnel rides that connection backward. Moving it means
reconfiguring the acquisition box to dial Box A instead, and `README.md` notes that *physical
access to that box is rare and scheduled*. It is genuinely an RDM operation and by the
"none locally" rule it should move — but it should move **deliberately and second**, once
Box A is otherwise live, not as a line item inside this port. Until then it is the one
documented exception to "no RDM ops on the dev box."

---

## 6. Phases

Each phase ends with a verification that either passes or stops the port. Do not proceed on
a failed verification.

### Phase 0 — on the dev workstation, now (no Box A dependency)

Both items are prerequisites for a second machine, and 0.1 closes a live data-loss exposure.

- **0.1 Memory into git** (§4.2). Create the private `gjesus3-memory` repo; `git init` in
  `<slug>\memory\`; initial commit of all 46 files; push.
  - **Verify:** `git log --oneline` in that directory shows the commit, and the GitHub repo
    shows 46 files. The single-copy exposure is closed at this moment, independent of Box A.
- **0.2 WorkstationOps per-instance config** (§4.1). Add `instance.local.ps1` support +
  tracked example + `.gitignore` entry; make `ops.ps1` fail closed without it; write this
  machine's `instance.local.ps1` declaring its current op set.
  - **Verify:** `.\ops status` still reports every op it does today, now under the header
    `dev-workstation`; temporarily renaming `instance.local.ps1` makes `ops.ps1` refuse
    with the pointer message rather than doing anything.
- **0.3 `memory-sync` op** (optional but recommended) — commit-if-dirty + push, daily.

### Phase 1 — Box A base

WSL2 + Ubuntu (in flight), OpenSSH server (in flight), **Python from python.org — not the
Microsoft Store build.** Two reasons: the Store build virtualizes `%LOCALAPPDATA%`, so
source-mode and frozen-exe tooling read different state files (already bit us once), and it
is why `config/finder-refresh.conf.ps1:20` has to hard-code
`...WindowsApps\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\python.exe` — the Store
alias does not resolve reliably under Task Scheduler. A normal install gives a stable path.
Match the dev version (3.13.x). Then clone both repos to local disk.

**Verify — the one test that can sink the whole thing.** Everything in this system depends on
`os.link()` working over SMB against the QNAP:

```powershell
python -c "import os,pathlib; p=pathlib.Path(r'J:\gjesus3-data\tmp'); (p/'boxa_src.txt').write_text('boxa'); os.link(p/'boxa_src.txt', p/'boxa_link.txt'); print('hard link OK')"
# then remove both files
```

Expected to pass — same account, same share — but if it fails, Box A cannot ingest at all and
nothing further in this plan matters. Stop and take it to IT.

### Phase 2 — environment and code

`pip install -r tools/requirements.txt`; `conda env create -f
tools/dicomifier-pilot.environment.yml` in WSL; mount `J:` as `/mnt/gjesus3` in WSL; copy
`.claude\settings.local.json`.

**Verify:** run the validator and compare against this workstation —

```bash
PYTHONPATH=tools python tools/validate_registries.py --nas-root "J:\gjesus3-data" --no-enrichment
```

The pass condition is **the same result as dev, not a green one.** As of 2026-09-04 that is
`FAILED` with exactly **10,314** `operator`-placeholder errors (decision **D1** in
[`STATUS.md`](STATUS.md) §0). A *different* count means something about Box A's environment
is wrong — do not wave it off as "the known red."

### Phase 3 — credentials

`.my.cnf` on **both** the Windows and WSL sides; `gjesus3_mri.cred` (Windows side — or point
at the NAS copy); a **newly minted** GitHub key added to the account, not a copy of the dev
key.

**Verify:**

```bash
python -c "import sys; sys.path.insert(0,'tools'); import animal_db; print(animal_db.credentials_available())"
```

then a real lookup for a known animal (`tools/animal_db.py --help`). `True` plus a resolved
species/strain/sex/DOB means the enrichment path works from Box A.

### Phase 4 — memory onto Box A

Create `~\.claude\projects\<Box-A-slug>\memory\`, `git init`, add the `gjesus3-memory` remote,
fetch, check out. (Not `git clone` — the directory already exists.)

**Verify:** the 46 files are present, and a Claude Code session started in the Box A repo
recalls a known memory.

### Phase 5 — hand over the schedule

1. Write Box A's `config\instance.local.ps1` with `$ENABLED_OPS = @("finder-refresh", ...)`
   and its local `$GJESUS3_REPO` / `$PYTHON`.
2. `.\ops verify finder-refresh` on Box A — it must pass before scheduling.
3. `.\ops run finder-refresh` manually on Box A.
4. **Verify:** `.\ops status finder-refresh` reports a build time of *just now*, and the
   published `registries\index.html` on the NAS has moved.
5. `.\ops schedule finder-refresh` on Box A.
6. **Only then**, on this workstation: `.\ops unschedule finder-refresh` and drop it from the
   dev `$ENABLED_OPS`.
7. **Verify next morning:** the index's build time advanced overnight, and Task Scheduler on
   the dev box no longer holds `WorkstationOps-finder-refresh`.

### Phase 6 — `molecubes-tunnel`

Separate decision, separate visit (§5). Not part of the port.

---

## 7. Open decisions

| # | Decision | Note |
|---|---|---|
| **B1** | **Does the GUI exe keep being built on the dev box?** Recommendation: **yes.** PyInstaller, the throwaway-test-NAS verification loop, and the worktree flow are development. Box A pulls and at most deploys. Nothing about the frozen build needs the production box. |
| **B2** | **`molecubes-tunnel`** — move to Box A (needs the acquisition box reconfigured, rare physical access) or leave here as the documented exception? |
| **B3** | **Does Box A need a `dicomifier-pilot` env at all**, or is ParaVision→DICOM regeneration a Data-Office activity that stays on dev? Phase 2 assumes Box A gets it; dropping it removes a WSL/conda dependency from the production box. |
| **B4** | **Repo path on Box A** — `D:\gjesus3\gjesus3-pilot` is assumed throughout. Confirm, because it goes into `instance.local.ps1` and determines the memory slug. |

---

## 8. Corrections this raises in other documents

- **`image-server\README.md`** still says migrating the OMERO/XNAT trials off Ryan's
  workstation to Box A is pending work. **That is no longer the plan** — Box A is not
  sufficient for them and they stay on the dev workstation (§2). That satellite owns its own
  status; flagged here rather than edited from this repo.
- **`workstationops_finder_refresh` memory** records the cross-repo `$GJESUS3_REPO` coupling
  as a dev-box fact. It needs updating when Phase 5 completes.
