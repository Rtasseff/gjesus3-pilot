# 11 — Operations

**Parent:** [Documentation Index](00_INDEX.md)  
**Status:** 📋 Planned  
**Last Updated:** 2026-05-11

---

## Purpose

This document covers operational aspects: roles, permissions, workflows, onboarding, and pilot management.

---

## 1. Roles and Responsibilities

### 1.1 Role Definitions

| Role | Responsibilities | Who |
|------|------------------|-----|
| **System Owner** | Strategic decisions; access authorization; escalation | Jesús Ruiz-Cabello (PI) |
| **Data Management Lead** | Define rules; implement system; support users; manage registries; admin writes to `/raw/` (corrections, project close-out merges) | Ryan Tasseff |
| **Operator** | Deposit data into `/raw/`; fill ingest-time metadata; maintain provenance; follow conventions | Trained lab technicians |
| **User** | Read raw data; work in own project folder under `/projects/`; **supply study-level metadata** under `/projects/<own>/metadata/`; contribute to publications | Researchers (e.g. PhD students, postdocs) |

The **Operator vs User** distinction is the writeability boundary on `/raw/` and on which area each role primarily inhabits. Operators bring data IN at ingest time; Users work WITH data after deposit. A single person can wear both hats — but the roles describe the *action*, not the person. The new `User` role is the home for **study-level metadata work** in `/projects/<own>/metadata/` (see [08_METADATA §1](08_METADATA.md)).

### 1.2 Authorized Users (Initial Pilot)

> **⚠️ Role designations below predate the User/Operator split (added 2026-05-12) and need PI review.** Several people listed as "Operator" likely fit the new "User" role (researchers contributing study metadata) rather than the technician-style Operator role (data deposit). The Owner/Lead designations are unchanged.

| Name | Role (pending review) | Notes |
|------|------|-------|
| Jesús Ruiz-Cabello | Owner | PI |
| Ryan Tasseff | Data Management Lead | Data Office |
| Marta Beraza Cabrerizo | Operator | |
| Ainhize Urkola Arsuaga | Operator | |
| Irene Fernández Folgueral | Operator | |
| Claudia Beatriz Miranda Pérez de Alejo | Operator | |
| Itziar Souto Riobo | Operator | |
| Ekine Olaizola Bárcena | Operator | |
| Tania Orosco Salinas | Operator | Clinical data safeguard |

---

## 2. Permissions Model

### 2.1 Area Permissions

> **✅ DECIDED (2026-05-12):** Permissions are folder-level, anchored on the [08_METADATA §1](08_METADATA.md) split between immutable acquisition-level metadata (in `/raw/`) and mutable study-level metadata (in `/projects/<proj>/metadata/`). `/raw/` is uniformly read-only post-deposit for everyone except the Data Mgmt Lead doing controlled admin writes (corrections, project close-out merges).

| Area | Data Mgmt Lead | Operators (technicians) | Users (researchers) | Others |
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
> **Registries change (2026-06-02):** operators were previously Read-only on registries; since operators run the ingest (which appends rows to `registry_raw.csv` / `ingest_manifest.csv` / `registry_projects.csv`), they now need Read/Write there. Registries are the mutable metadata ledger — not the protected raw *data*; raw immutability + per-acquisition `checksums.json` are what guarantee data traceability.

#### 2.1.1 Applied implementation — `J:\gjesus3-data\` (DECIDED + APPLIED 2026-06-02)

The conceptual model above is now applied on the live container. **IT will not create custom groups**, so the model uses the pre-existing `CICBIOMAGUNE\GJesus` group (which contains the lab — researchers, operators, PI) instead of the originally-planned `pilot-users` / `pilot-operators` groups:

| Principal | `raw\` | `registries\` | `projects\`, `publications\`, `staging\`, `curated_datasets\` |
|---|---|---|---|
| `GJesus` group (everyone) | **Read** (inherited from top) | Read | Read everywhere; **Modify** on projects/publications/staging |
| Operators (individual accounts) | **write-but-not-modify** ("create files" scoped to folders only + read-only on files → can deposit new acqs, cannot edit/delete existing) | Modify (append) | (Modify via the group) |
| Superusers (rtasseff = Lead, jruizcabello = PI) | Full | Full | Full |

- **Read baseline:** `GJesus` = Read at the top of `gjesus3-data`, inherited down — no per-folder read work.
- **Build UP with grants only — NEVER DENY.** Windows ALLOW grants are cumulative (union); a group-Read floor does NOT cap a member's individual Full. A DENY would override everyone in the group (operators + superusers are all in `GJesus`) and is sticky enough to block its own cleanup — so deny is forbidden here.
- **Raw is writable only by superusers + operator-create.** Careless users cannot modify a raw file directly (read-only) nor through a project hard link (the link shares raw's single ACL — proven; a RW projects folder does not leak write onto the linked file). This closes the silent-untraceable-edit hole.
- **Defense in depth:** ACL (prevent) + per-acq `checksums.json` (detect any raw change) + `@Recently-Snapshot` (recover).
- **Operator immutability is a future-verify item** — see §2.3 and `tasks/tasks.md §4.3`. The fine-grained "create-but-not-modify" must be tested with a real operator account on the QNAP filesystem; superusers can't test it (their Full masks the restriction). If it doesn't translate over SMB, fall back to a tool-applied read-only lock at end-of-ingest, or an operator drop-box → superuser-move path. Filesystem (ext4 vs ZFS) still unconfirmed; ZFS/NFSv4-ACL honors the fine grain better than ext4/POSIX-ACL.

**Key consequences of this model:**

- After ingest finishes, even the Operator who ran it loses write access to that acquisition. Corrections route through the Data Mgmt Lead. (See §4.2 Exception Handling.)
- Users (researchers) can never modify raw data or its sidecar — but they have a clean writeable area for study-level metadata in `/projects/<own>/metadata/`. This is the home for the eventual Excel-import metadata tool (see `tasks/tasks.md`).
- The only writes to `/raw/` post-deposit are by the Data Mgmt Lead, in two situations: (a) ad-hoc correction of an error caught after ingest; (b) project close-out — merging the study-level metadata from `/projects/<proj>/metadata/` into the corresponding `/raw/<ACQ-ID>/metadata.json` sidecars before the project folder is deleted (see [05_PROJECTS §4.x](05_PROJECTS.md)).

### 2.2 Intake Roles

> **⚠️ GAP:** Who can promote staging → raw?

| Option | Description | Trade-off |
|--------|-------------|-----------|
| **Any operator** | Self-service deposit | More errors possible |
| **Data Mgmt Lead only** | Centralized control | Bottleneck |
| **Designated operators** | Trained subset | Balance |

**Tentative:** Any trained operator can deposit; Data Mgmt Lead reviews periodically.

### 2.3 Permission Enforcement

| Mechanism | Description | Status |
|-----------|-------------|--------|
| NAS user groups | Existing `CICBIOMAGUNE\GJesus` group = Read baseline; per-operator + superuser grants layered on (no custom groups — IT won't create them) | ✅ Applied 2026-06-02 on `gjesus3-data` (§2.1.1) |
| Post-deposit lockdown | Operators get "create files (folders-scope) + read-only on files" on `raw\` → write-but-not-modify | ✅ Applied via ACL; ⏳ **fine-grain translation over SMB pending verification with a real operator account** (superusers can't test it) — `tasks/tasks.md §4.3` |
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
5. **Supervised test deposit** (for operators)
6. **Access granted** (NAS credentials)

### 3.2 Quick Start Guide

Daily flow for depositing a new acquisition. This is the operational view — what to do and in what order. For the underlying command syntax and flags, see [`tools/INGEST_CLI.md`](../tools/INGEST_CLI.md).

> **🔶 Pilot scope (2026-05):** The example paths, config name, and filename conventions below are written from the **AxioScan 7** perspective — that's the only instrument validated end-to-end so far. The *structure* of the workflow (find/write YAML config → dry-run → real run → verify) is intended to generalize. As more instruments come online (Cell Observer, LSM 900, MRI, Nuclear Imaging), this section will be refactored to separate the common steps from the per-instrument specifics (share path, expected filename pattern, project-hint convention). For now, treat the AxioScan 7 examples as the working template and ask the Data Mgmt Lead before applying them to a different instrument.

> **One-time per shell session (PowerShell on Windows):** point the script at the NAS once. Either add the line to your PowerShell profile or run it before each session:
>
> ```powershell
> $env:GJESUS3_ROOT = "J:\"   # adjust to your NAS drive letter
> ```
>
> If you forget, the script will now error out clearly rather than silently writing into a phantom path on your C: drive. The flag form `--nas-root "J:\"` on each command also works.

1. **Finish the acquisition.** Confirm the file(s) are on the instrument's usual share (e.g. AxioScan 7 writes to `\\goptical\GOpticalUsers data\AxioScan\<YYYYMMDD>\`). Do not move them yet.
2. **Find or write the YAML config.** Start from the **per-instrument template** at [`tools/templates/instruments/<instrument>.yaml`](../tools/templates/instruments/) (currently: `axioscan7.yaml`). If your instrument doesn't have one yet, start from the universal [`tools/templates/ingest_template.yaml`](../tools/templates/ingest_template.yaml) and ask the Data Mgmt Lead before running — the per-instrument template captures conventions that aren't obvious. Save your copy as `tools/configs/<instrument>_<batch>.yaml` (e.g. `axioscan7_20260520.yaml`). The configs folder is under git and the relative path of the config you ran is stamped into every registry row it produces (`ingest_config` column).
3. **Edit the config for this batch.** At minimum, update `auto_discover.staging_dir` to your folder. Adjust per-batch fields (operator, project_hint pattern) as needed. The full schema is documented in [`10_TOOLS.md §2.1`](10_TOOLS.md).
4. **Dry-run.** Always first. Inspect the log: file count, parsed values, project resolution, any warnings.

   ```powershell
   python tools/ingest_raw.py -c tools/configs/<your_config>.yaml --dry-run
   ```

5. **Run for real.** Same command without `--dry-run`. Wait for it to finish.
6. **Verify.** Open `registry_raw.csv`; confirm one new row per acquisition. Confirm the destination folder under `/raw/<ECOSYSTEM>/<YYYY>/<YYYY-MM>/<ACQ-ID>/` contains `metadata.json`, `checksums.json`, `README.txt`. If a project was linked, confirm a `.lnk` shortcut appeared under `/projects/<proj-short-name>/raw_linked/`.

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
   - Created automatically by ingest_raw.py when --project is set (Windows .lnk; see 10_TOOLS §2.1.1)
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

## 5. Pilot Management

### 5.1 Pilot Parameters

| Parameter | Value |
|-----------|-------|
| **Duration** | 4-6 weeks initial |
| **Scope** | Microscopy (Axio Scan 7 WSI, Cell Observer, LSM 900) + DICOM (MRI, Nuclear Imaging) |
| **Participants** | Initial user cohort (see Section 1.2) |
| **Success criteria** | See [01_OVERVIEW](01_OVERVIEW.md) Section 6 |

### 5.2 Review Cadence

**Weekly check-ins during pilot:**
- What's working?
- What's confusing?
- What's being ignored/worked around?
- Any blocking issues?

**Format:** Short meeting or async survey

### 5.3 Feedback Collection

| Channel | Purpose |
|---------|---------|
| Weekly check-in | Ongoing issues |
| Email to Data Mgmt Lead | Specific questions |
| Shared document | Suggestions and ideas |
| Post-pilot survey | Overall assessment |

### 5.4 Iteration Process

1. Collect feedback weekly
2. Triage: urgent fix vs. improvement vs. defer
3. Implement urgent fixes immediately
4. Queue improvements for batch updates
5. Document changes in version history

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
User question
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

| ID | Question | Owner | Status |
|----|----------|-------|--------|
| OPS-01 | Who can promote staging → raw? | Data Mgmt Lead + PI | ⚠️ Needs decision |
| OPS-02 | NAS user/group configuration | Data Mgmt Lead + IT | 📋 To configure |
| OPS-03 | Quick Start Guide | Data Mgmt Lead | 📋 To write |
| OPS-04 | Pilot start date | PI | ⚠️ Needs scheduling |
