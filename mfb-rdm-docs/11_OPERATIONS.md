# 11 — Operations

**Parent:** [Documentation Index](00_INDEX.md)  
**Status:** ✅ In use (true production)  
**Last Updated:** 2026-06-26

---

## Purpose

This document covers operational aspects: roles, permissions, workflows, onboarding, and steady-state production operations.

---

## 1. Roles and Responsibilities

### 1.1 Role Definitions

| Role | Responsibilities | Who |
|------|------------------|-----|
| **System Owner** | Strategic decisions; access authorization; escalation | Jesús Ruiz-Cabello (PI) |
| **Data Management Lead** | Define rules; implement system; support users; manage registries; admin writes to `/raw/` (corrections, project close-out merges) | Ryan Tasseff |
| **Tech** | Deposit data into `/raw/`; fill ingest-time metadata; maintain provenance; follow conventions | Trained lab technicians (RENAMED from "Operator" 2026-06-09) |
| **Researcher** | Read raw data; work in own project folder under `/projects/`; **supply study-level metadata** under `/projects/<own>/metadata/`; contribute to publications | Researchers (e.g. PhD students, postdocs) — RENAMED from "User" 2026-06-09 |

> **Permission-role vocabulary (DECIDED 2026-06-09).** Renamed **Operator → Tech** and **User → Researcher** to fix the global naming mess (the MRI/NI platforms call *researchers* "users", microscopy calls *the tech* the "operator"). "**user**" is now reserved for "a person using the software". Note the distinction from the *metadata* roles in [06_REGISTRIES §2.3a-bis](06_REGISTRIES.md): there, **researcher** = who set up the experiment (registry) and **operator** = who ran the equipment (sidecar). Here, **Tech** is the *permission* class for instrument staff who deposit data, and **Researcher** the class for data owners. A person can be both.

The **Tech vs Researcher** distinction is the writeability boundary on `/raw/` and on which area each role primarily inhabits. Techs bring data IN at ingest time; Researchers work WITH data after deposit. A single person can wear both hats — the roles describe the *action*, not the person. The `Researcher` role is the home for **study-level metadata work** in `/projects/<own>/metadata/` (see [08_METADATA §1](08_METADATA.md)).

> **MRI / NI ingest runs as the data office or a shared platform login (2026-06-09).** Preclinical MRI and Nuclear Imaging acquisitions are always ingested either by the Data Office or **directly on the platform acquisition machine**, which uses its own login. That platform/data-office login is granted write access to `raw/` so that whoever is at the machine can deposit — the per-person Tech write-but-not-modify model below is the microscopy / workstation path.

### 1.2 Authorized People

> **Note on role labels.** The labels below use the **current permission-role vocabulary** (DECIDED 2026-06-09, §1.1): **Tech** = instrument staff who deposit data into `/raw/`; **Researcher** = data owners who work in their project folder and supply study-level metadata. The same person can hold both roles. The "Tech (provisional)" tag marks people who appear here from the original instrument-staff roster but whose primary day-to-day role may in practice be Researcher — the label describes the *action* (deposit vs. work-with), not a fixed title, and is refined as each person's actual usage settles. Owner / Data Management Lead are fixed.

| Name | Role | Notes |
|------|------|-------|
| Jesús Ruiz-Cabello | Owner | PI |
| Ryan Tasseff | Data Management Lead | Data Office |
| Marta Beraza Cabrerizo | Tech (provisional) | |
| Ainhize Urkola Arsuaga | Tech | Cell Observer + LSM 900 confocal operator |
| Irene Fernández Folgueral | Tech (provisional) | |
| Claudia Beatriz Miranda Pérez de Alejo | Tech (provisional) | |
| Itziar Souto Riobo | Tech (provisional) | |
| Ekine Olaizola Bárcena | Tech (provisional) | |
| Tania Orosco Salinas | Tech (provisional) | Clinical data safeguard |

---

## 2. Permissions Model

### 2.1 Area Permissions

> **✅ DECIDED (2026-05-12):** Permissions are folder-level, anchored on the [08_METADATA §1](08_METADATA.md) split between immutable acquisition-level metadata (in `/raw/`) and mutable study-level metadata (in `/projects/<proj>/metadata/`). `/raw/` is uniformly read-only post-deposit for everyone except the Data Mgmt Lead doing controlled admin writes (corrections, project close-out merges).

| Area | Data Mgmt Lead | Techs (technicians) | Researchers | Others |
|------|----------------|-------------------------|---------------------|--------|
| `/staging/` ¹ | Read/Write | Read/Write | — | — |
| `/raw/` (pre-deposit) | Read/Write | Create/Write | — | — |
| `/raw/` (post-deposit) — incl. `metadata.json` sidecars | Read/Write (admin corrections + close-out merges) | Read | Read | Read (if granted) |
| `/projects/<own>/` (incl. `metadata/`) | Read/Write | Read | Read/Write | — |
| `/projects/<other>/` | Read/Write | Read | Read (if granted) | — |
| `/publications/<own>/` | Read/Write | Read/Write | Read/Write | Read (if granted) |
| Registries | Read/Write | **Read/Write** (append rows on ingest) | Read | — |

> ¹ NAS `staging/` is a **secondary convenience dump**. The recommended ingest path uses fast local or network storage as the primary source (see [03_RAW_STORAGE](03_RAW_STORAGE.md) Section 5.2).
>
> **Registries change (2026-06-02):** techs (the role formerly called "operators") were previously Read-only on registries; since they run the ingest (which appends rows to `registry_raw.csv` / `ingest_manifest.csv` / `registry_projects.csv`), they now need Read/Write there. Registries are the mutable metadata ledger — not the protected raw *data*; raw immutability + per-acquisition `checksums.json` are what guarantee data traceability.

#### 2.1.1 Applied implementation — `J:\gjesus3-data\` (DECIDED + APPLIED 2026-06-02)

The conceptual model above is now applied on the live container. **IT will not create custom groups**, so the model uses the pre-existing `CICBIOMAGUNE\GJesus` group (which contains the lab — researchers, techs, PI) instead of the originally-planned `pilot-users` / `pilot-operators` groups:

| Principal | `raw\` | `registries\` | `projects\`, `publications\`, `staging\`, `curated_datasets\` |
|---|---|---|---|
| `GJesus` group (everyone) | **Read** (inherited from top) | Read | Read everywhere; **Modify** on projects/publications/staging |
| Techs (individual accounts) — and the MRI/NI platform/data-office login | **write-but-not-modify** ("create files" scoped to folders only + read-only on files → can deposit new acqs, cannot edit/delete existing) | Modify (append) | (Modify via the group) |
| Superusers (rtasseff = Lead, jruizcabello = PI) | Full | Full | Full |

- **Read baseline:** `GJesus` = Read at the top of `gjesus3-data`, inherited down — no per-folder read work.
- **Build UP with grants only — NEVER DENY.** Windows ALLOW grants are cumulative (union); a group-Read floor does NOT cap a member's individual Full. A DENY would override everyone in the group (techs + superusers are all in `GJesus`) and is sticky enough to block its own cleanup — so deny is forbidden here.
- **Raw is writable only by superusers + operator-create.** Careless users cannot modify a raw file directly (read-only) nor through a project hard link (the link shares raw's single ACL — proven; a RW projects folder does not leak write onto the linked file). This closes the silent-untraceable-edit hole.
- **Defense in depth:** ACL (prevent) + per-acq `checksums.json` (detect any raw change) + `@Recently-Snapshot` (recover).
- **Tech (operator-account) immutability is a future-verify item** — see §2.3 and [`tasks/STATUS.md`](../tasks/STATUS.md). The fine-grained "create-but-not-modify" must be tested with a real Tech (operator) account on the QNAP filesystem; superusers can't test it (their Full masks the restriction). If it doesn't translate over SMB, fall back to a tool-applied read-only lock at end-of-ingest, or an operator drop-box → superuser-move path. Filesystem (ext4 vs ZFS) still unconfirmed; ZFS/NFSv4-ACL honors the fine grain better than ext4/POSIX-ACL.

**Key consequences of this model:**

- After ingest finishes, even the Tech (operator) who ran it loses write access to that acquisition. Corrections route through the Data Mgmt Lead. (See §4.2 Exception Handling.)
- Researchers can never modify raw data or its sidecar — but they have a clean writeable area for study-level metadata in `/projects/<own>/metadata/` (study-level metadata is PLANNED/DEFERRED — Phase 4; see [`tasks/BACKLOG.md`](../tasks/BACKLOG.md)). This is the home for the eventual Excel-import metadata tool.
- The only writes to `/raw/` post-deposit are by the Data Mgmt Lead, in two situations: (a) ad-hoc correction of an error caught after ingest; (b) project close-out — merging the study-level metadata from `/projects/<proj>/metadata/` into the corresponding `/raw/<ACQ-ID>/metadata.json` sidecars before the project folder is deleted (see [05_PROJECTS §4.x](05_PROJECTS.md)).

### 2.2 Intake Roles

> **✅ DECIDED — who promotes staging → raw.** Any **trained Tech** (and the MRI/NI platform / Data-Office login) runs the ingest themselves and thereby promotes into `/raw/`; the Data Mgmt Lead reviews periodically rather than gating every deposit. This is the *balance* option below, and it is what the applied ACL model in §2.1.1 enforces in practice: a Tech can **create** new acquisitions under `/raw/` but cannot modify or delete existing ones, so self-service deposit cannot silently damage retained data. Genuinely new conventions / batch ingests still route through the Data-Office YAML path (§3.2).

| Option | Description | Trade-off |
|--------|-------------|-----------|
| Any Tech | Self-service deposit | More errors possible |
| Data Mgmt Lead only | Centralized control | Bottleneck |
| **Designated/trained Techs** ✅ | Trained subset; Lead reviews periodically | Balance — **adopted** |

The write-but-not-modify ACL (§2.1.1) is what makes self-service safe: errors are *additive* (a duplicate or a mis-named new folder, fixable via §4.2), never destructive to existing raw data.

### 2.3 Permission Enforcement

| Mechanism | Description | Status |
|-----------|-------------|--------|
| NAS user groups | Existing `CICBIOMAGUNE\GJesus` group = Read baseline; per-operator + superuser grants layered on (no custom groups — IT won't create them) | ✅ Applied 2026-06-02 on `gjesus3-data` (§2.1.1) |
| Post-deposit lockdown | Techs (operator accounts) get "create files (folders-scope) + read-only on files" on `raw\` → write-but-not-modify | ✅ Applied via ACL; ⏳ **fine-grain translation over SMB pending verification with a real Tech (operator) account** (superusers can't test it) — [`tasks/STATUS.md`](../tasks/STATUS.md) |
| Registry protection | Operators Read/Write (append on ingest); structure guarded by `registry.append_row` defensive header check; `rebuild_baseline/` snapshot for recovery | ✅ Applied |
| Defense in depth | ACL (prevent) + `checksums.json` (detect) + `@Recently-Snapshot` (recover) | ✅ In place |

---

## 3. Onboarding Process

### 3.1 Steps for New Users

1. **Request access** from PI (verbal or email)
2. **Receive documentation** link to this documentation set
3. **Read core documents:**
   - 01_OVERVIEW
   - 03_RAW_STORAGE (if depositing raw data)
   - 04_PUBLICATIONS (if working on publications)
   - 05_PROJECTS (if working on projects)
   - 07_PROVENANCE
4. **Attend orientation** (30-60 min with Data Mgmt Lead)
   - System walkthrough
   - Tool demonstration
   - Q&A
5. **Supervised test deposit** (for Techs depositing raw data)
6. **Access granted** (NAS credentials)

### 3.2 Quick Start Guide

> **Most operators want [§3.3 Operator self-service ingest (no-YAML path)](#33-operator-self-service-ingest-no-yaml-path) instead** — no config files. As of 2026-06-24 the GUI ships as a one-click Windows app, **`gjesus3_ingest.exe`**, on the NAS at **`\\GJESUS3\gjesus3\gjesus3-data\tools\`** with two shortcuts: **Microscopy Ingest** (ZWSI/CELL/LSM9) and **MRI Ingest** (the `/mri` page — pull from the scanner, preview, ingest; needs the per-machine `~/.ssh/gjesus3_mri.cred`). Each page has a "? Help" link to its HTML guide (also in `tools\docs\`). The `ni-ingest` / `mri-ingest` CLI scripts remain for the Data-Office / on-platform path. Start there (and at the one-page [`START_HERE.md`](../START_HERE.md)). §3.2 below is the YAML / Data-Office path for batch ingests and new conventions. Full GUI design: [10_TOOLS §5.2](10_TOOLS.md).

Daily flow for depositing a new acquisition. This is the operational view — what to do and in what order. For the underlying command syntax and flags, see [`tools/INGEST_CLI.md`](../tools/INGEST_CLI.md).

The workflow is **the same four beats for every instrument** — only the share path, the expected filename/folder pattern, and the template you copy differ. Section A is the instrument-agnostic flow; Section B is the per-instrument cheat-sheet you read alongside it.

#### A. Common workflow (all instruments)

> **One-time per shell session (PowerShell on Windows):** point the script at the NAS once. Either add the line to your PowerShell profile or run it before each session:
>
> ```powershell
> $env:GJESUS3_ROOT = "J:\"   # adjust to your NAS drive letter
> ```
>
> If you forget, the script will now error out clearly rather than silently writing into a phantom path on your C: drive. The flag form `--nas-root "J:\"` on each command also works.

1. **Finish the acquisition.** Confirm the file(s)/folder are on the instrument's usual share (Section B, "Where data lives"). For instruments whose data must first be pulled or extracted to local staging (MRI via `ftp_mirror.py`, Nuclear Imaging via `extract_ni_archives.py`), do that step first — see the per-instrument template header. Do not move the source by hand.
2. **Copy and edit the per-instrument template.** Start from the **per-instrument template** for your instrument (Section B, "starter template"). If your instrument doesn't have one yet, start from the universal [`tools/templates/ingest_template.yaml`](../tools/templates/ingest_template.yaml) and ask the Data Mgmt Lead first — the per-instrument template captures conventions that aren't obvious. Save your copy as `tools/configs/<instrument>_<batch>.yaml` (Section B, "example per-batch config"). At minimum, edit `auto_discover.staging_dir` to point at your batch folder and update `registry.notes` with a short batch description. The configs folder is under git and the relative path of the config you ran is stamped into every registry row it produces (`ingest_config` column). The full schema is documented in [`10_TOOLS.md §2.1`](10_TOOLS.md).
3. **Dry-run.** Always first. Inspect the log: file count, parsed values, project resolution, any warnings.

   ```powershell
   python tools/ingest_raw.py -c tools/configs/<your_config>.yaml --dry-run
   ```

4. **Run for real.** Same command without `--dry-run`. Wait for it to finish.
5. **Verify.** Four checks, the same regardless of instrument:
   - **Registry:** open `registry_raw.csv`; confirm **one new row per acquisition**.
   - **Destination:** the folder under `/raw/<ECOSYSTEM>/<YYYY>/<YYYY-MM>/<ACQ-ID>/` contains `metadata.json`, `checksums.json`, and `README.txt`.
   - **Project link:** if a project was linked, a **hard link** appeared under `/projects/<proj-short-name>/raw_linked/`, named per the config's `link_filename:` (Section B, "link name example"). Since 2026-06-02 this is a real NTFS/SMB **hard link**, not a `.lnk` shortcut — it shows up as an ordinary file (or, for folder-primary acquisitions like MRI/NI, a real folder of per-file hard links) carrying the resolved name, with no extension added.
   - **No surprises:** scan the log for any `WARN`/`ERROR` lines and confirm the parsed values look right.

**What NOT to do:**

- Don't edit, rename, or delete anything under `/raw/` after deposit. Raw is immutable. Mistakes get fixed by the Data Mgmt Lead via documented corrections, not by hand.
- Don't hand-edit registry CSVs. Same reason.
- Don't pass `--delete-source` until you have confirmed the dry-run output is correct *and* you have verified the destination after a real run. The default is OFF and that is the right default.
- Don't re-run an interrupted ingest from a different machine assuming the registry is corrupted — the script is idempotent and will skip already-ingested acquisitions cleanly.

**Where to get help:** Data Mgmt Lead (see §7.1).

**Key folder locations:**

| What | Where |
|------|-------|
| YAML configs (version-controlled) | `tools/configs/` |
| Per-instrument config templates | `tools/templates/instruments/` |
| Universal config template (fallback) | `tools/templates/ingest_template.yaml` |
| CLI reference | `tools/INGEST_CLI.md` |
| Full config schema | [`10_TOOLS.md §2.1`](10_TOOLS.md) |
| Registries on NAS | `\\GJESUS3\gjesus3\registries\` |
| Raw area | `\\GJESUS3\gjesus3\raw\` |
| Projects area | `\\GJESUS3\gjesus3\projects\` |

#### B. Per-instrument cheat-sheet

Read this row alongside Section A. "Where data lives" is the source share you copy *from*; "starter template" is the file you copy in step 2; "link name example" is what the verify step (A.5) should show under `/projects/<proj>/raw_linked/`. Cells marked **GAP** are not yet confirmed — ask the Data Mgmt Lead before assuming a value.

| Instrument | Code | Where data lives / share | filename-or-folder pattern | starter template | example per-batch config | link name example |
|---|---|---|---|---|---|---|
| AxioScan 7 WSI | `ZWSI` | `\\goptical\GOpticalUsers data\AxioScan\<YYYYMMDD>\` (one `.czi` per scan; Ryan maps `S:`) | filename, `_`-separated: `MFB_<operator>_<project>_<sample_short>_<section>_<stain>_<mag>.czi` | `tools/templates/instruments/axioscan7.yaml` | `tools/configs/axioscan7_20260522.yaml` | `ZWSI_MFB_AUA_1022_ID58T_1_Hif1A_10x.czi` |
| Cell Observer | `CELL` | group drive, operator folder (Ryan maps `K:`); path carries most context | path `<researcher>/<cell_line>/<experiment>/` + light filename | `tools/templates/instruments/cell_observer_cells.yaml` | `tools/configs/cell_observer_itziar_alphasma_TEST.yaml` | `CELL_<original>.czi` (template default) |
| LSM 900 confocal | `LSM9` | same group drive (`K:`) | batch-folder regex `<researcher>_<experiment>_<cell_line>` | `tools/templates/instruments/lsm900.yaml` | `tools/configs/lsm900_laura_uptake_TEST.yaml` | `LSM9_<original>.czi` |
| Internal MRI (Bruker ParaVision 7T/11.7T) | `MRI` | acq machine `/opt/PV-7.0.0/data/nmr/`, SFTP-pulled to local staging (`tools/ftp_mirror.py`); production NAS-side staging path = **GAP** | folder-as-primary; study-folder regex `jrc[_]?YYMMDD_m<animal>_<project_code>` | `tools/templates/instruments/mri_bruker.yaml` | `tools/configs/mri_bruker_20251016_TEST.yaml` | `MRI_jrc_251016_m17_0424_20251016_29_3` |
| Nuclear Imaging (Molecubes PET/CT, archive mode) | `PET`/`CT`/`SPECT`/`OI` | archive on `\\cicmgsp02\gnuclear2$\<YYYY>\... .tgz`, pre-extracted by `tools/extract_ni_archives.py` to local staging | folder basename regex `user_series_date_proj_sample_datetime_modality` | `tools/templates/instruments/molecubes_ni.yaml` | `tools/configs/ni_jesus_archive_2025_TEST.yaml` | `PET_m14_20251029_20251029100641` |

> Where a link name example shows `<original>`, the template's default `link_filename:` resolves to `original_name` — i.e. the source filename with the instrument code prepended. Where it shows a fully-resolved string (MRI, NI), the template ships a systematic `link_filename:` pattern to guarantee uniqueness within a project. See [`tools/INGEST_CLI.md`](../tools/INGEST_CLI.md) for the `link_filename:` resolver context.

### 3.3 Operator self-service ingest (no-YAML path)

> **Status:** ✅ Built and deployed. Operator front-ends sit over the shared `tools/operator/` core (design + build plan: [`tasks/operator_ingest_tooling_plan.md`](../tasks/operator_ingest_tooling_plan.md)). The microscopy + MRI GUI ships as one frozen Windows executable, **`gjesus3_ingest.exe`**, deployed to the NAS at **`\\GJESUS3\gjesus3\gjesus3-data\tools\`** on **2026-06-24** (see [10_TOOLS §5.2](10_TOOLS.md)). §3.2 above remains the YAML / Data-Office path; this subsection is the simpler **point-at-a-folder** path for operators who do not want to edit YAML. Both run the **same validated pipeline** — the front-ends only build the config in memory and never reimplement ingest.

For operators running ingest themselves on the acquisition machines there is now a no-YAML front-end per lane. They all **preview first** (a read-only "what will happen" table — one row per acquisition: ACQ-ID, sample, project, link name, file count) then ask to confirm, and they are idempotent (safe to re-run). The full operator-facing guide is [`tools/operator/README.md`](../tools/operator/README.md).

| Lane | Front-end | Platform | How to run |
|---|---|---|---|
| Nuclear Imaging (Molecubes PET/CT) | `ni-ingest` (`tools/operator/ni_ingest.py`) | Linux acquisition machine | `python tools/operator/ni_ingest.py /path/to/folder [--dry-run] [--go]` |
| Internal MRI (Bruker ParaVision) | `mri-ingest` (`tools/operator/mri_ingest.py`) | Linux acquisition machine | `python tools/operator/mri_ingest.py /path/to/study [--reconstructions all\|3\|1,3] [--model 7T\|11.7T] [--dry-run] [--go] [--ftp-remote …]` |
| Microscopy (AxioScan 7 / Cell Observer / LSM 900) | GUI — Microscopy page (`tools/operator/gui/`) | Windows | run the deployed **`gjesus3_ingest.exe`** (Microscopy Ingest shortcut; opens in the browser) — pick a recipe → point at folder → preview → ingest |
| Internal MRI (Bruker ParaVision) — GUI alternative | GUI — MRI page (`/mri`) | Windows | run the same **`gjesus3_ingest.exe`** (MRI Ingest shortcut) — pull from the scanner → preview → ingest. Equivalent to the `mri-ingest` CLI above for operators who prefer the GUI. |

- The Linux scripts and the GUI find the NAS the same way `ingest_raw.py` does — `--nas-root` > `$GJESUS3_ROOT` > `/mnt/gjesus3`, validated for a `registries/` subfolder (the GUI persists the choice). MRI's optional `--ftp-remote` SFTP-pull uses the `GJESUS3_FTP_*` env vars (same as [`tools/ftp_mirror.py`](../tools/ftp_mirror.py)).
- The microscopy GUI is **recipes + builder**: operators normally pick a saved recipe; the builder is for defining a new naming convention with a live `discovered.*` preview. It freezes to a single PyInstaller `.exe` so the locked-down Windows microscopy machine needs no Python install (build step in [`tools/operator/gui/README.md`](../tools/operator/gui/README.md)).
- **Dry-run default (testing period).** Every front-end previews before it writes. The microscopy GUI's *Dry-run* checkbox defaults **ON** during the testing period (a high-contrast banner shows while it is on; a dry run ends with a clear "NOTHING was written" summary); the Linux scripts preview-then-prompt and their `--dry-run` likewise ends with "nothing was written". **Once the testing period is over, flip the GUI default to OFF** — remove `checked` from `#r-dry` in `gui/templates/index.html` (the `TODO(dry-run-default)` marker flags the spot). This is deliberately a testing-period safety default, not the permanent one.
- **NI live-machine note:** archive-mode NI ingest works today (extract the `.tgz` first with [`tools/extract_ni_archives.py`](../tools/extract_ni_archives.py)). Live (on-the-machine, non-archive) ingest is not wired up yet — only the live-folder-layout template (`molecubes_ni_live.yaml`) remains; deployment itself is unblocked (the NI server runs Linux and a script can be installed there — confirmed by Platform Manager Unai 2026-06-03).

---

## 4. Deposit Workflow (Operational)

### 4.1 Standard Flow

```
1. Complete acquisition
   ↓
2. Prepare data (same day)
   - Gather files from instrument
   - Note metadata (sample, purpose, etc.)
   ↓
3. Deposit to raw (same day)
   - Use ingest script OR manual process
   - Verify checksum generation
   - Confirm registry entry
   ↓
4. Notify Data Mgmt Lead (if manual)
   - Request folder lockdown
   ↓
5. Link to project/publication (when relevant)
   - Created automatically by ingest_raw.py when a project resolves; an NTFS/SMB hard link named per link_filename: under /projects/<proj>/raw_linked/ (hard links since 2026-06-02, superseding .lnk shortcuts; see 10_TOOLS §2.1.1)
   - Update provenance as work progresses
```

### 4.2 Exception Handling

| Exception | Action |
|-----------|--------|
| Forgot to deposit same day | Deposit ASAP; note delay in registry |
| Naming error discovered | Contact Data Mgmt Lead for correction |
| Duplicate deposit | Contact Data Mgmt Lead; one will be removed |
| Corrupt files detected | Do NOT delete; contact Data Mgmt Lead |

---

## 5. Production Operations

> **Status:** gjesus3 has been in **true production since the 2026-06-10 restart**. The quasi-production pilot (per-instrument test → purge → accept, then a whole-system purge after the team exhibition) is **complete and historical** — that purge already happened on 2026-06-10 and there is **no future purge / restart pending**. All data is real and retained long-term. This section is the steady-state operations view; the pilot-phase parameters it used to carry are retired.

### 5.1 Scope (operational)

| Parameter | Value |
|-----------|-------|
| **Scope** | Microscopy (AxioScan 7 WSI · `ZWSI`, Cell Observer · `CELL`, LSM 900 confocal · `LSM9`) + DICOM ecosystem (Bruker ParaVision MRI · `MRI`, Nuclear Imaging Molecubes/MILabs PET/SPECT/CT · `PET`/`SPECT`/`CT`) |
| **Participants** | See [§1.2](#12-authorized-people) |
| **Success criteria** | See [01_OVERVIEW](01_OVERVIEW.md) Section 6 |

### 5.2 Review Cadence

**Ongoing check-ins with active operators / researchers:**
- What's working?
- What's confusing?
- What's being ignored/worked around?
- Any blocking issues?

**Format:** Short meeting or async survey, on an as-needed cadence (no fixed pilot calendar).

### 5.3 Feedback Collection

| Channel | Purpose |
|---------|---------|
| Direct check-in | Ongoing issues |
| Email to Data Mgmt Lead | Specific questions |
| Shared document | Suggestions and ideas |

### 5.4 Iteration Process

1. Collect feedback as it arrives
2. Triage: urgent fix vs. improvement vs. defer (defer → [`tasks/BACKLOG.md`](../tasks/BACKLOG.md))
3. Implement urgent fixes immediately
4. Queue improvements for batch updates
5. Document changes in [`CHANGELOG.md`](../CHANGELOG.md) / [`00_INDEX.md`](00_INDEX.md) version history

---

## 6. Compliance and Enforcement

### 6.1 Expectations

| Requirement | Enforcement |
|-------------|-------------|
| Deposit same-day | Periodic audit of registry dates |
| Complete required metadata | Script validation; spot checks |
| Don't modify raw after deposit | Permissions lockdown |
| Log provenance for publication outputs | Closure checklist |

### 6.2 Non-Compliance Response

| Severity | Example | Response |
|----------|---------|----------|
| **Minor** | Incomplete metadata | Reminder; assist with correction |
| **Moderate** | Repeated late deposits | Discussion; identify barriers |
| **Serious** | Modifying locked raw data | Escalate to PI; review access |

**Philosophy:** Focus on making compliance easy, not on punishment. Most non-compliance stems from confusion or friction, not malice.

---

## 7. Support and Escalation

### 7.1 Support Channels

| Issue Type | Contact | Response Time |
|------------|---------|---------------|
| How-to questions | Data Mgmt Lead | 1 business day |
| Tool problems | Data Mgmt Lead | Same day |
| Access issues | Data Mgmt Lead → IT | 1-2 days |
| Policy questions | Data Mgmt Lead | 1 business day |
| Strategic decisions | PI | As needed |

### 7.2 Escalation Path

```
Question (operator / researcher)
    ↓
Data Management Lead
    ↓ (if policy/strategic)
PI
    ↓ (if IT-related)
IT
```

---

## 8. Related Documents

- [01_OVERVIEW](01_OVERVIEW.md) — System scope and success criteria
- [03_RAW_STORAGE](03_RAW_STORAGE.md) — Deposit procedures
- [10_TOOLS](10_TOOLS.md) — Scripts and automation

---

## Open Questions

All operations open-questions are resolved as of the true-production restart; kept here as a resolution record.

| ID | Question | Owner | Status |
|----|----------|-------|--------|
| OPS-01 | Who can promote staging → raw? | Data Mgmt Lead | ✅ Decided — any trained Tech / platform-Data-Office login self-services; Lead reviews periodically. The write-but-not-modify ACL keeps it safe (§2.2, §2.1.1). |
| OPS-02 | NAS user/group configuration | Data Mgmt Lead + IT | ✅ Applied 2026-06-02 — `CICBIOMAGUNE\GJesus` Read baseline + per-Tech/superuser grants, no custom groups (§2.1.1, §2.3). |
| OPS-03 | Quick Start Guide | Data Mgmt Lead | ✅ Written — operator self-service (§3.3) + one-page [`START_HERE.md`](../START_HERE.md); YAML/Data-Office path (§3.2). |
| OPS-04 | Pilot start date | — | ✅ Moot — quasi-prod pilot complete; true production live since 2026-06-10. |

> **Remaining verify item (not an open question — tracked in [`tasks/STATUS.md`](../tasks/STATUS.md)):** the fine-grained "create-but-not-modify" ACL grain still needs confirmation over SMB with a real Tech account (superusers can't test it — their Full masks the restriction). Fallback paths are documented in §2.1.1.
