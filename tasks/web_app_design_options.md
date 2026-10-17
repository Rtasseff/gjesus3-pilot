# One web app on Box A: design options

> ❓ **EVALUATING throughout. Nothing here is decided.** Every section gives options, their costs in
> this system's terms, and a recommendation. Ryan decides; nothing in this note changes a numbered
> spec. When a shape is chosen, it goes into [`10_TOOLS`](../mfb-rdm-docs/10_TOOLS.md) §5 as ✅.
>
> **Raised:** issue [#28](https://github.com/Rtasseff/gjesus3-pilot/issues/28) · **Drafted:** 2026-10-17 ·
> **Milestone:** M3, ready before the Box A port lands ([`backlog_triage_2026-10-10.md`](backlog_triage_2026-10-10.md))
> **Adjacent work, interfaces only:** #27 (Box A pulls NI through the tunnel), #29 (metadata database),
> #30 (search index / dynamic Finder).

---

## What this is about, in plain words

Today each tool is a small program people start on their own PC: `gjesus3_ingest.exe` (microscopy
and MRI ingest), `gjesus3_manager.exe` (the Project Manager) and, on the Molecubes Mac, the
`ni-ingest` command. Each writes to gjesus3 with **the account of whoever is sitting at the PC**.

The plan (Ryan, 2026-10-01; [`BACKLOG`](BACKLOG.md) "Ingest from one place") is one web
application on Box A. People behind the firewall open it in a browser, log in, and the app does the
work **with the system's own setup and permissions on their behalf**. The aim behind it: NI
researchers leave the acquisition room when the experiment ends and never come back for the data.

Two things are already decided (Ryan) and are not reopened here:

- **NI corrections become a form in the app** (2026-10-07). It keeps the sync-safety invariant
  (a correction changes metadata values, never the session key or `original_name`) and is the home
  for per-session `is_control`.
- **Box A pulls NI data through the tunnel and the Mac stops mounting gjesus3** (2026-10-08; #27).

The questions below are what has to be settled before a first version is built.

### Facts every section leans on

| Fact | Source |
|---|---|
| Box A runs under **Ryan's own domain account**, so it has his superuser rights on the NAS. | [`box_a_production_migration_plan.md`](box_a_production_migration_plan.md) §2 |
| Techs deposit to `raw\` under **write-but-not-modify** (create new, cannot change or delete existing); everyone in `CICBIOMAGUNE\GJesus` reads; grants only, never DENY; IT will not create custom groups. The fine grain is **still unverified with a real Tech account**. | [`11_OPERATIONS`](../mfb-rdm-docs/11_OPERATIONS.md) §2.1.1, §2.3 |
| Hard links are the project-linking mechanism and are proven only for **Windows Python over SMB**; the Mac gets `ENOTSUP`; Box A's first test is `os.link` over `J:`. | [`10_TOOLS`](../mfb-rdm-docs/10_TOOLS.md) §2.1.1; Box A plan Phase 1; [`RESUME_ni_live.md`](RESUME_ni_live.md) §5 |
| `researcher` = who ran the study; `operator` = who ran the equipment; "user" is software lingo only. | [`06_REGISTRIES`](../mfb-rdm-docs/06_REGISTRIES.md) §2.3a-bis |
| Provenance `creator` is required and is **typed by hand** today (the Project Manager has a required box). | [`07_PROVENANCE`](../mfb-rdm-docs/07_PROVENANCE.md) §3.4; `tools/manager/gui/app.py` `/api/import_raw`, `/api/import_local` |
| Project `owner` is free text and already inconsistent (`jguser` / `Jguser`, platforms and people mixed). | [`BACKLOG`](BACKLOG.md) "Server-era identity" |
| Scheduling, health and alerts belong to **WorkstationOps**; this repo owns the code it calls. | [`11_OPERATIONS`](../mfb-rdm-docs/11_OPERATIONS.md) §5.6 |
| The Molecubes Mac belongs to the platform: small footprint, no recursive walks over big trees, nothing written without approval. | [`RESUME_ni_live.md`](RESUME_ni_live.md) "Rules for working on the Molecubes Mac" |
| "Do not increase complexity. The system is barely used *because* it is complex." | [`RESUME_ni_live.md`](RESUME_ni_live.md) §5 |

---

## 1. Who did this, when the app writes as one account

### Why it is a question

Today the NAS knows who wrote each file, because each person writes with their own account, and
the ACLs stop a Tech from changing what is already in `raw\`. If the app writes for everyone, the
NAS sees **one account**. "Who ingested this" then has to come from the app's login and be carried
into the registry (`researcher`, `operator`), provenance (`creator`) and projects (`owner`). And the
one account the app writes with decides whether the write-but-not-modify safety net still applies.

This splits into three smaller questions.

### 1a. Where the login comes from (the auth source)

| Option | What the person does | What the registry gets | Costs |
|---|---|---|---|
| **A1. Windows sign-in on Box A** (the browser passes the person's domain login; IIS or a Negotiate/Kerberos layer in front of the app) | Nothing: they are already logged into Windows. | A stable `CICBIOMAGUNE\account`. Membership of `GJesus` can be checked. | Box A must be domain-joined (it appears to be: it runs a domain account); the site must be in the browser's intranet zone; IT may need to register a host name for Kerberos. Works only from domain PCs, which is all that can reach gjesus3 today ([`02_INFRASTRUCTURE`](../mfb-rdm-docs/02_INFRASTRUCTURE.md) §2). |
| **A1b. A login form checked against the institute directory** (LDAP bind) | Types their usual Windows user and password. | The same account name as A1. | No browser setup, but the app handles passwords, so HTTPS becomes mandatory (§6). Still needs IT's directory address and permission to bind. |
| **A2. Institute single sign-on** (Microsoft Entra / SAML / OpenID, if the institute runs it) | Signs in with the institute's web login. | The institute identity (often an e-mail). | IT must register the app; heaviest IT dependency; buys access from non-domain devices, which the NAS rules do not allow anyway. |
| **A3. A user table inside the app** | Gets a separate gjesus3 password. | Whatever the Data Office types. | No IT dependency. The Data Office becomes a password keeper, people get one more password, and accounts drift from the real directory (leavers are not removed). |

**Recommendation: A1, with A1b as the fallback if Kerberos setup stalls.** It is the only option
that gives a trustworthy name with nothing for the person to do, and it matches what the
access-logging study found (IIS records the authenticated user;
[`access_logging_feasibility.md`](access_logging_feasibility.md) §2). A3 only as a short stop-gap,
never as the design. One question to IT settles A1 versus A1b: *"Can Box A serve an intranet site
with Windows Integrated Authentication under a DNS name you register?"*

### 1b. What the login fills in

A login gives an **account name** (`rtasseff`). The registry columns hold **person names** in a
convention the group is still choosing (#16, `researcher` naming; #15, person attribution). And the
person pressing the button is not always the `researcher` or the `operator`: a microscopy Tech
ingests a researcher's slides; the Data Office ingests on behalf of others.

| Option | How it works | Trade-off |
|---|---|---|
| **B1. Stamp the account name directly** | `creator = rtasseff`, `owner = rtasseff` | Simple, but adds a third spelling of each person to columns that already mix people, platforms and accounts. |
| **B2. A small people table: account → the name the registry uses** | One row per person: account, display name, the registry spelling (per #16), role (Tech / Researcher / Data Office). The app looks the login up. | One more small file to keep. It is also the natural place to fix `jguser` / `Jguser` once. The spelling rule is a Data Office call (#16), so the table waits on that, not the reverse. |
| **B3. Login only pre-fills; every field stays editable** | Today's forms, with a better default. | Keeps the careless-typing problem the change is meant to remove. |

Per field, under B2:

| Field | Recommended source | Why |
|---|---|---|
| Provenance `creator` | **The login, never editable.** | It means "who did this file operation". This is the field that benefits most ([`BACKLOG`](BACKLOG.md) "Server-era identity"). |
| Project `owner` on create | **The login by default**; the Data Office may set someone else (a student creating a project for their PI). | Ownership is a claim about a person, not about who clicked. |
| Registry `operator` | **Unchanged rules**: from the data for microscopy (`discovered.operator` / `czi_user`), the login pre-filled for MRI/NI where `operator == researcher` ([`06_REGISTRIES`](../mfb-rdm-docs/06_REGISTRIES.md) §2.3a-bis). | The login is who pressed the button, which is often not who ran the scope. |
| Registry `researcher` | **Still chosen per batch**, pre-filled from the login only on the MRI/NI pages. | Same reason. |
| "Who pressed ingest" | **New, recorded separately** (next row). | Today nothing records it: `registry_raw` holds the declared people and `ingest_config`, and the manifest has no person ([`access_logging_feasibility.md`](access_logging_feasibility.md) §3). |

Where "who pressed ingest" lives:

- **C1.** A new registry column (`ingested_by`). A schema change to `06_REGISTRIES`, with the usual
  mirrors; best done once, inside the metadata database (#29).
- **C2.** The app's own action log (§5), keyed by ACQ-ID. No schema change.
- **C3.** The sidecar's `generator` block. The sidecar is read-only after deposit, so it can only be
  set at ingest; fine for new data, never for corrections.

**Recommendation: B2, and C2 now with C1 when #29 lands.** The login must never silently become
`researcher` or `operator`.

**Edit rights on projects.** Under B2 the app can enforce "the owner and the Data Office edit, others
read" in its own pages. It cannot enforce it on the share: `GJesus` has Modify on `projects\`, so
anyone can still edit a project folder in Explorer. Per-project NTFS grants would close that, but
cost one grant per project per person with no groups available. **Recommendation:** enforce in the
app only, and say plainly in the guide that the share itself stays open to the group, as today.

### 1c. Which account the app writes with

| Option | The NAS sees | Safety net on `raw\` | Costs |
|---|---|---|---|
| **D1. Ryan's account, as Box A runs today** | Ryan, for every write. | **Gone.** Every app write is a superuser write: a bug or a misuse can change or delete existing raw data. | None to set up. The NAS log (if ever switched on) attributes all work to Ryan. |
| **D2. A dedicated service account with the Tech grants** (write-but-not-modify on `raw\`, Modify on `registries\`, Modify on `projects\` via `GJesus`) | The app. | **Kept**: the app physically cannot overwrite existing raw data. | IT must create one account (they refused one for the Mac; a server service account is a more ordinary request, but not certain). The hard-link test must pass under it. Data Office repairs (retire, re-identify, operator hold) cannot run through it, which is correct: they stay CLI tools under Ryan's account. |
| **D3. The app acts as each person** (Kerberos delegation) | The real person. | Each person's own grants apply. | IT must configure delegation; researchers have no write on `raw\`, so every depositor needs the Tech grant; the most moving parts. |

**Recommendation: D2, with D1 only as an interim while IT creates the account.** D2 also finally
answers the open check in [`11_OPERATIONS`](../mfb-rdm-docs/11_OPERATIONS.md) §2.3: the service
account *is* the real Tech account the create-but-not-modify test has been waiting for. If the fine
grain does not hold over SMB, that section already names the fallbacks (a read-only lock at the end of
ingest, or a drop-box moved by a superuser), and the app is the place to apply them once.

---

## 2. When the app pulls an NI session

### Why it is a question

"The scan ended" does not mean "the data is complete". Reconstructions finish late, and a new one
lands in a new, higher-numbered `recon_<idx>/` ([`BACKLOG`](BACKLOG.md) "Ingest from one place").
The live sync already absorbs this:

- **One acquisition per reconstruction**; `<anchor>/recon_<idx>` is a safe dedup key because
  indices are append-only ([`RESUME_ni_live.md`](RESUME_ni_live.md) §5).
- A reconstruction still being written (no DICOMs yet) is skipped and picked up next time
  (`tools/operator/ni_ingest.py` docstring).
- `ni_flat.registered_recons` skips any reconstruction already loaded by another route
  (`tools/ingest/ni_flat.py`).
- A correction binds to the raw session key, so a late reconstruction inherits its session's
  corrections (`tools/ingest/ni_corrections.py`).

**The catch the app changes:** corrections are applied **at sync time only**. Today the order is
plan → researcher edits → sync, so the researcher's fixes are in before anything is written. A
correction made *after* a reconstruction is registered does not change it: the sidecar is read-only
after deposit and corrections route through the Data Office ([`11_OPERATIONS`](../mfb-rdm-docs/11_OPERATIONS.md)
§2.1.1). If the app ingests on its own before the researcher has looked, a wrong project code
files the data into the wrong project and the animal lookup misses.

### Options

| Option | How it works | Good | Bad |
|---|---|---|---|
| **P1. Pull now only** | A button in the app: "fetch my new scans". | Today's cycle, from any computer. Nothing happens without the researcher. | Late reconstructions need the researcher to come back (to a browser, not the room). Forgotten sessions are never pulled. |
| **P2. Scheduled sweep only** | Box A fetches every researcher folder on a timer and ingests. | Nobody has to do anything. | Ingests before review, so every code error becomes a Data Office repair. |
| **P3. Sweep plus a review gate, with "pull now" too** | The sweep fetches and *plans*: new sessions appear in the researcher's corrections form. A session **somebody has reviewed** is ingested, and its later reconstructions flow in on later sweeps automatically. A session not reviewed is **held** (see below). "Pull now" runs the same thing at once. | The researcher reviews once, from any computer, and never thinks about late reconstructions again. Uses the existing model unchanged: the plan step already appends a row per new session, and "a row a human has looked at" is already the rule. | A held session needs a rule for when nobody reviews it. |

What happens to an unreviewed session under P3:

- **Hold forever** until reviewed: safe, but data can sit outside gjesus3 indefinitely.
- **Ingest after N days as-is**, with the default project rule (4 digits → `AE-biomaGUNE-NNNN`,
  anything else → `Project-<code>`); a wrong code becomes a Data Office repair, as today.
- **Remind, then ingest** after N days.

**Recommendation: P3, with "remind, then ingest as-is after a fixed hold" (for example 7 days).**
The researcher who reviews gets correct data; the one who forgets still gets their data in. The
hold length is a Data Office call.

**After ingest, the form shows a session read-only** with a "request a correction" action that
lands in a Data Office queue. That keeps the post-deposit rule intact rather than letting the form
rewrite `raw\`.

### Constraints the sweep must respect (interfaces for #27, not designed here)

- **The Mac's footprint rules.** A sweep is a listing of the researcher folders; it must stay
  incremental (newest `<series>/<date>` folders only, or a cheap change check), run outside
  acquisition hours, and stay small. Cadence: **nightly**, plus "pull now", rather than every few
  minutes.
- **A "reconstruction finished" signal.** Today "has DICOMs" means ready. A pull mid-write could take
  half a reconstruction; #27 should confirm whether a quiet period (files unchanged for some minutes)
  is needed.
- **One registry writer at a time.** The sweep, app ingests and Data Office CLI runs all go through
  the registry lock; the published "batch running" flag (#14) applies to the sweep too.
- **Through the Mac or past it** (ProxyJump to remiW11) is #27's open question; the app does not care
  which, as long as the fetched folder has the same layout.

---

## 3. Moving ingest onto Box A

### Why it is a question

The 2026-06-24 idea ([`BACKLOG`](BACKLOG.md) "Server-side raw ingest") was a Linux ingest host with
everything in one place: the scanner credentials, the animal-facility DB credentials, Dicomifier,
and the NAS mounted **with working hard links**. Box A is Windows with WSL. Hard links are proven
only from Windows Python over SMB; nobody has tested `os.link` from WSL's view of the share
(`/mnt/gjesus3`), and the Mac's SMB client refuses it outright.

### What moves to Box A

| Piece | Today | On Box A |
|---|---|---|
| The ingest engine (`ingest_raw`, the operator core, the NI live path) | Frozen inside each exe, and a copy on gnuclear for the Mac | One repo checkout, run by the app and by WorkstationOps |
| MRI scanner credentials (`gjesus3_mri.cred`) | Per machine | Once, on Box A (Phase 3) |
| Animal-facility DB credentials (`.my.cnf`) | Windows and WSL sides of the dev box | Once, both sides on Box A (Phase 3) |
| Dicomifier | WSL on the dev box only; missing on operator PCs, so no-DICOM exams queue to `pending_dicom_regen.csv` | WSL on Box A (this answers Box A plan **B3** with "yes", if MRI ingest moves) |
| NI access | The Mac mounts gjesus3 with Ryan's saved password | Box A's own key logs into the Mac through the tunnel; the Mac holds no NAS credential (#27) |
| Staging | NAS `staging\` (MRI pulls) or the source folder | A local folder on Box A, auto-cleaned as the MRI page already does |

### Where the engine runs

| Option | How | Trade-off |
|---|---|---|
| **S1. Engine on Windows Python; WSL only for Dicomifier** | The app (Windows) calls Dicomifier through `wsl.exe` on a local staging folder, then ingests the DICOMs as usual. | Hard links go through the one path already proven. Dicomifier is a subprocess, which is exactly how the graceful "regen if present" step already works. |
| **S2. The whole engine in WSL (the original Linux-server idea)** | The app and engine run in Ubuntu with the NAS mounted (drvfs or CIFS). | Hard links over that mount are unproven; if they fail, every link goes to `pending_links.csv`, as on the Mac, and someone drains it from Windows. |
| **S3. Native Windows Dicomifier** | Build it. | Plausible, unverified, weeks of work ([`BACKLOG`](BACKLOG.md) "No-DICOM regeneration on Windows"). Not needed if S1 works. |

**Recommendation: S1.** The one test in the port plan (Phase 1: `os.link` over `J:` on Box A) is
then the only hard-link test that matters, **run under the account the app will write with** (D2 in
§1c), not only under Ryan's. A WSL `os.link` probe is worth one extra minute in the same test, as
information, not as a dependency.

### Do the exes retire at once?

| Option | Trade-off |
|---|---|
| **E1. Retire at once** | One way in from day one; no risk of two versions of the engine writing differently. But no fallback if the app has teething problems. |
| **E2. Overlap for one release, then retire** | The exes stay in `tools\` on the share, labelled "fallback", for a fixed period (for example one month of real use). Both write through the same registry lock. Slightly more to support, and the exes must not lag the engine: no new engine change ships to the app alone during the overlap without an exe rebuild, or the two disagree. |
| **E3. Keep the exes indefinitely** as the "app is down" path | Two front-ends to maintain forever; cuts against "do not increase complexity". |

**Recommendation: E2.** Set the end date when the app goes live. The CLI stays permanently for the
Data Office. The NI command on gnuclear retires with the Mac mount (#27), not with the exes.

---

## 4. What carries over and what is new

### Why it is a question

The three Flask apps were built to be "as similar as possible" for this merge
([`10_TOOLS`](../mfb-rdm-docs/10_TOOLS.md) §5.3): the same `style.css`, `folder_browser.js`, completion
modal, `/api/*` JSON shape, SSE log stream and saved-state mechanism. But they were built for **one
person on their own PC** (`127.0.0.1`, ports 5000 and 5001), and a few things change meaning on a
server.

### Carries over largely as-is

| Piece | Note |
|---|---|
| The shared operator core (`tools/operator/`: templates, config builder, scope, preview, runner, collisions) | Already "the only place the operator core writes to the NAS" (`tools/operator/runner.py`). No change. |
| Microscopy recipe-runner and Builder | Recipes already live on the share. |
| MRI page (SFTP pull, token-valued destination project, preview, ingest) | The read-only SFTP pull and auto-deleted staging move unchanged. |
| Project Manager: My projects, New project, Add data from the RDM System | Thin front-ends over `tools/manager/`; built to "move to the server unchanged". |
| Shared assets, completion modal, SSE stream | Become one set instead of `/shared/<path>` served from the ingest GUI's folder. |

### Changes meaning on a server

| Today | On Box A | Why it matters |
|---|---|---|
| The folder browser shows **the operator's own PC** | It shows **Box A's** view: the NAS and whatever network drives Box A maps | Microscopy sources are on "ordinary network drives" and instrument PCs. **Box A must be able to read each instrument's export share**, with an account that has read on it. An inventory per instrument is needed before the microscopy page moves. |
| Project Manager **"Add files from my computer"** copies from local disks | The server cannot see a person's disk | Options: a browser upload (simple; slow and size-limited for large images), or "put them in `staging\` first, then pick them here". Recommend the second for v1: it reuses the existing page. |
| NAS root chosen and saved per PC | One server setting | Removes the "first launch opens production" trap noted in [`10_TOOLS`](../mfb-rdm-docs/10_TOOLS.md) §5.3. Testing then needs a separate test instance pointed at a scratch NAS. |
| Saved state in `%LOCALAPPDATA%` | Per user on the server | Keyed by the login. |
| One person, one ingest at a time, implicitly | Many people at once | Long jobs run in a queue (§6), not in the web request; each person sees their own jobs. |
| A typed operator / creator name | The login (§1b) | |

### New

1. **The NI page**: "my sessions" from the last sweep, "pull now", and the corrections form.
2. **The corrections form** (decided). Proposed shape:
   - One row per session, the columns of `NI_CORRECTION_FIELDS` (`project`, `animal_codes`,
     `extra_metadata` for the tracer), **plus `is_control`** as a three-way choice (control / not
     control / unknown), matching the tri-state in [`08_METADATA`](../mfb-rdm-docs/08_METADATA.md) §4.5.
   - **The invariant is enforced by the server, not just the page:** `session_path` is shown, never
     posted back; a save that would add, drop or rename a key is refused; the dedup key
     `(acq_date, original_name)` is never touched.
   - A session already ingested is read-only, with "request a correction" (§2).
   - **Where it is stored** (options):
     - **F1.** The same CSV files, left on gnuclear. The Mac creates them as `nuclearuser`, read-only
       from Windows; the app would need write there.
     - **F2.** The same CSV format, moved into gjesus3 (for example `registries\ni_corrections\`),
       written only by the app under the lock. The engine's reader (`read_corrections`) is unchanged.
     - **F3.** A table in the metadata database (#29).
   - **Recommendation: F2 now, F3 when #29 lands.** One-time copy of the existing per-researcher
     files from gnuclear; they are kept forever by rule.
3. **A single login** (§1a) and the people table (§1b).
4. **An action log** (§5).
5. **A job list**: what is queued, running, done or failed, and the leftovers the tools already
   queue (`pending_links`, `pending_dicom_regen`, `pending_subject_metadata`, `pending_unparsed`),
   so the Data Office's after-sync steps in the NI runbook stop being manual checks.
6. **Later, not v1:** a dynamic Finder (#30). The static `index.html` keeps working for researchers
   who double-click it.

---

## 5. Access logging

### Why it is a question

The feasibility study ([`access_logging_feasibility.md`](access_logging_feasibility.md)) found that
any per-user logging, NAS or app, needs **first** the DPO's sign-off, a retention limit and notice
to staff and their representatives (GDPR Arts. 5, 13, 30, 35; LOPDGDD art. 87; Estatuto de los
Trabajadores art. 64.5(f)). The app makes logging cheap. It does not make it lawful.

Three different things get called "logging" and should be kept apart:

| Kind | Example | Already done today? |
|---|---|---|
| **Attribution of work** | `creator` in provenance, `operator` / `researcher` in the registry, project `owner` | Yes, by typed names. It is the purpose of provenance ([`07_PROVENANCE`](../mfb-rdm-docs/07_PROVENANCE.md)). |
| **An action log** | "account X imported 12 acquisitions into project Y at 10:14" | No |
| **An access log** | Who searched for what, who opened which page or file | No (the static Finder makes no requests) |

### Options

| Option | What is recorded at launch | Lead time |
|---|---|---|
| **L1. Attribution plus an action log of write actions only**, the action log built but holding names only after the DPO agrees; until then counts without names. The web server's own request log kept short or without user names. | The same people fields as today, filled from the login; write actions as counts. | Short: the DPO conversation runs in parallel and does not block launch. |
| **L2. Full access logging from day one** (reads, searches, page views) | Everything | Long: DPO, likely an impact assessment, staff notice. Blocks launch. |
| **L3. Nothing beyond the people fields** | Today's level | None, but leaves the action log (cheap and useful for support) unbuilt. |

**Recommendation: L1, and open the DPO conversation now**, because the process is the long lead
time, not the code. Ask the DPO two things: whether filling `creator` / `owner` from a login changes
anything relative to typing them (it should not; confirm), and what retention fits a write-action log
with names. Searches and reads stay unlogged in v1; if the dynamic Finder comes (#30), its search
text is personal data to minimise. Store the action log on the NAS under `registries\`, written only
by the app account, so snapshots cover it and researchers cannot edit it.

---

## 6. How it runs on Box A

### Why it is a question

Box A is one desktop-class machine (HP Z2, no GPU, 1 GbE; Box A plan §1) that also runs the 03:00
Finder rebuild and the NI tunnel. An ingest can run for many minutes and must not die with a web
request. And if the app is down, people still need to get data in, or know that waiting is safe.

### Processes

| Option | Shape | Trade-off |
|---|---|---|
| **G1. One web process with a built-in job queue; scheduled work done by WorkstationOps** | One app (pages as blueprints), one worker thread taking jobs one at a time, the job list saved to a file. The nightly NI sweep is a **WorkstationOps op** calling a command-line entry point of the same code. | Simplest. Matches "one registry writer at a time" and the existing boundary (WorkstationOps schedules; this repo owns the code). A restart interrupts a running job; the saved list shows which, and the ingest's existing pending queues make it resumable. |
| **G2. Web process plus a separate worker service** | The worker survives web restarts. | One more service to supervise. Worth it only if restarts in the middle of jobs become a real problem. |
| **G3. Several apps as today**, each on its own port | Least change. | Several logins, several things to supervise; misses the point of "one place". |

**Recommendation: G1**, built so the worker can be split out later (G2) without changing the pages.

### Web server, address and certificate

| Option | Trade-off |
|---|---|
| **H1. IIS in front of the app, an IT-registered name** (for example `gjesus3-app.<institute domain>`) **and an institute certificate** | IIS does Windows sign-in natively (A1), runs the app pool **as the service account** (D2) and restarts the process if it dies. Needs IT for the name and the certificate. |
| **H2. A Python server (waitress) with a self-signed certificate** | No IT, but browsers warn on every visit, which teaches people to click through warnings. |
| **H3. Plain HTTP on the internal network for a first version** | Acceptable only with A1 (no passwords cross the network) and only for a pilot; never with A1b or A3. |

**Recommendation: H1.** Bundle the IT asks into one request: the host name, the certificate, the
Kerberos registration (A1) and the service account (D2).

### Supervision

- A `web-app` op in WorkstationOps, under the per-instance config (Box A plan §4.1): `status` calls
  a health page that reports the app version, the NAS reachable, the registry lock free or held, the
  queue length and the last sweep; `verify` checks the service account, the paths and the
  credentials; a failure raises the usual flag.
- The app's own state (people table, job list, action log, corrections) lives on the NAS, so it is
  covered by snapshots and the off-site backup (#4), not only on Box A's disk.
- Deploying a new version: pull on Box A, restart the app pool. **Gate it on the job list being
  empty.** The exes' "drop a new exe in `tools\`" step disappears.

### If the app is down

- **During the overlap (E2):** the exes in `tools\` still work.
- **After it:** data waits at the source until the app is back. That is safe where the source keeps
  it: the MRI scanner host and the NI box keep their data, and the platform archives are the tier
  below ([`13_GJESUS3_ROLE`](../mfb-rdm-docs/13_GJESUS3_ROLE.md) §1, §5.5). ⚠️ **Not confirmed for
  every microscopy instrument PC**: if any Tech clears exports soon after copying them, those
  instruments need either a longer local retention or a fallback. Check per instrument before the
  exes retire.
- **The Data Office CLI** works whatever the app's state, under Ryan's account, as today.

---

## Decisions Ryan has to make, in order

Each one unblocks the next.

1. **The auth source (§1a)**: A1 Windows sign-in, A1b directory login form, A2 SSO or A3 local
   users. Ask IT the one question in §1a.
2. **The account the app writes with (§1c)**: D2 service account, and D1 as an interim. Put it in
   the same IT request as the host name and certificate (§6, H1).
3. **The people table and what the login fills (§1b)**: B2, and where "who pressed ingest" goes
   (C2 now, C1 with #29). The registry spelling depends on #16.
4. **NI pull timing (§2)**: P3, the hold length, and what happens to an unreviewed session.
5. **Where corrections live (§4)**: F2 then F3.
6. **Retiring the exes (§3)**: E2 and its end date; and whether the microscopy instrument PCs keep
   their data long enough to make "wait for the app" safe (§6).
7. **Access logging scope (§5)**: L1. **Open the DPO conversation as early as possible,** whatever
   the choice, because it has the longest lead time.
8. **Deployment (§6)**: G1 and H1; mostly follows from 1 and 2.

Box A plan **B3** (Dicomifier on Box A) is answered by §3: yes, if MRI ingest moves to Box A.

## What can be built before any decision

None of these writes to production or changes a spec.

- **One app, locally.** Merge the microscopy/MRI GUI and the Project Manager into one Flask app with
  a page per tool, still runnable on `127.0.0.1` for testing, while the exes keep their current
  entry points. Move per-machine assumptions (NAS root, saved state) behind one settings function.
- **The NI corrections form** against today's CSV format, with tests that a save can never change
  `session_path`, add or drop a session, or touch `original_name`; `is_control` as a fourth column
  read by `ni_corrections` (unset stays null). Run it against a scratch NAS, as
  `tools/test_manager.py` does.
- **The job queue and job list**, with a saved job file and the pending-queue summary.
- **A health page** and the skeleton of the WorkstationOps `web-app` op.
- **The action-log helper**, writing counts only until it is switched to names (§5).
- **The Box A Phase 1 hard-link test, written to run as any account**, plus a WSL `os.link` probe.
  Running it is a NAS write and waits for Ryan's go.
- **The NI pull mode** (#27) is independent of every decision here except the review gate (§2), and
  can proceed on its own branch.
