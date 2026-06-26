# 02 — Infrastructure

**Parent:** [Documentation Index](00_INDEX.md)  
**Status:** ⚠️ Some IT details still open (filesystem type, snapshot retention, offsite backup); access + permission model APPLIED.
**Last Updated:** 2026-06-26

---

## Purpose

This document describes the hardware infrastructure, access model, and data-protection (risk) assessment for the gjesus3 storage system. gjesus3 has been in **true production** since the 2026-06-10 restart — the data is real and retained long-term — so the protection gaps flagged here (no offsite backup; snapshot retention unverified) matter operationally, not just on paper.

---

## 1. Hardware Specification

### 1.1 Device

| Attribute | Value |
|-----------|-------|
| **Model** | QNAP TS-864eU |
| **Form factor** | 2U rackmount, short depth |
| **Drive bays** | 8 × 3.5"/2.5" SATA |
| **Processor** | Intel Celeron N5095 quad-core (2.0 GHz, burst 2.9 GHz) |
| **Memory** | 8 GB DDR4 (expandable to 16 GB) |
| **Network** | 2 × 2.5 GbE (port trunking capable for 5 Gbps) |
| **Expansion** | 1 × PCIe Gen 3 x2 slot |
| **USB** | 2 × USB 3.2 Gen 2 (10 Gbps), 2 × USB 2.0 |
| **Power** | Single 300W PSU (RP model has redundant PSU) |

### 1.2 Storage Configuration

| Attribute | Value | Status |
|-----------|-------|--------|
| **RAID level** | RAID 5 | ✅ Confirmed |
| **Drive count** | 6 (of 8 bays populated) | ✅ Confirmed |
| **Drive capacity** | 20 TB each | ✅ Confirmed |
| **Raw capacity** | 120 TB (6 × 20 TB) | ✅ Confirmed |
| **System usable capacity** | ~100 TB (after RAID 5 parity) | ✅ Confirmed |
| **User-available capacity** | ~63 TB (after snapshot reservation) | ✅ Confirmed |
| **Filesystem** | ext4 or ZFS | ⚠️ Needs confirmation |

> **Note:** A portion of the ~100 TB system-usable space is reserved for the snapshot policy, leaving ~63 TB available for user data. Plan capacity against the 63 TB figure, not 100 TB.
>
> **Snapshot scope ≠ backup.** Snapshots are **on-device, same-array** point-in-time copies — they protect against accidental deletion / overwrite and let recent state be rolled back, but they live on the *same six drives* as the live data. They do **not** protect against multi-drive/array loss, controller/enclosure failure, ransomware that reaches the share, or site disaster. There is **no offsite backup configured** (see §3, §4.2). Daily snapshots are confirmed active (visible via the `@Recently-Snapshot` view); the retention window and restore timeline are still unverified.
>
> **TODO (Ryan):** Log into the QNAP admin UI directly to inspect how snapshot reservation is configured (size of reserved pool, retention schedule, which volumes/shares it covers). IT confirmed verbally that the ~37 TB gap is the snapshot reservation, but the exact configuration has not yet been verified at the source.

### 1.3 Operating System

| Attribute | Value |
|-----------|-------|
| **OS** | QNAP QTS 5.x (or QuTS hero if ZFS) |
| **Capabilities** | SMB/NFS shares, user management, app ecosystem |

---

## 2. Network and Access

### 2.1 Network Configuration

| Attribute | Value |
|-----------|-------|
| **Share path** | `\\GJESUS3\gjesus3` (SMB) |
| **Drive mapping** | Can be mapped to a drive letter, e.g., `net use J: \\GJESUS3\gjesus3` |
| **Authorized machines** | Specific hardwired on-site machines only (includes instruments and some researcher workstations) |
| **Laptops** | ❌ Not authorized — most researcher laptops cannot connect |
| **External/remote access** | Not available |
| **VPN access** | ⚠️ Unknown — needs IT clarification |

> **⚠️ GAP:** Need to clarify VPN options. Current access is limited to hardwired on-site machines, which is inconvenient but workable since many instruments and some researcher workstations are included.

### 2.2 Access Implications

Access is restricted to specific hardwired on-site machines. This is annoying but not unusable — many instruments and researcher workstations do have access. The main gap is that researcher laptops (the most common personal device) cannot connect.

**Practical impact:**

1. **Daily work should not depend on gjesus3** — use local storage or other network drives for active analysis
2. **Deposits are feasible** — instruments and many workstations have access, so deposits can happen from those machines
3. **Laptop users need a workaround** — transfer data via an authorized workstation or instrument machine

---

## 3. Data Protection Assessment

### 3.1 What RAID 5 Protects Against

| Scenario | Protected? |
|----------|------------|
| Single drive failure | ✅ Yes — array remains operational; rebuild after replacement |
| Read errors during normal operation | ✅ Yes — parity allows reconstruction |
| Silent bit rot (if scrubbing enabled) | ✅ Partial — depends on scrub schedule |

### 3.2 What RAID 5 Does NOT Protect Against

| Scenario | Protected? | Mitigation |
|----------|------------|------------|
| Multiple simultaneous drive failures | ❌ No | Consider RAID 6 for critical data (trades 1 drive of capacity) |
| Failure during rebuild | ❌ No | Rebuild stresses remaining drives; URE risk on large drives |
| Accidental deletion | 🔶 Partial | Daily snapshots active **(applied)**; read-only-after-deposit ACLs on `/raw/` **(applied 2026-06-02, see §6)** |
| Ransomware/malware | ❌ No | Snapshots are same-array (no defence against share-reachable ransomware); needs offsite backup + access controls |
| Controller/enclosure failure | ❌ No | Offsite backup (none configured) |
| Site disaster (fire, flood) | ❌ No | Offsite backup (none configured) |
| User error (overwrite, corruption) | 🔶 Partial | Snapshots for rollback; per-acquisition `checksums.json` for detection **(applied)** |

### 3.3 Risk Rating

| Risk | Likelihood | Impact | Mitigation Status |
|------|------------|--------|-------------------|
| Single drive failure | Medium | Low (recoverable) | ✅ RAID 5 handles |
| Multi-drive failure | Low | Critical | ⚠️ No mitigation (no offsite backup) |
| Accidental deletion | Medium | High | 🔶 Snapshots active + read-only ACLs **applied** (§6) |
| Ransomware | Low | Critical | ⚠️ No mitigation (snapshots are same-array) |
| Site disaster | Very Low | Critical | ⚠️ No mitigation (no offsite backup) |

> **Now that gjesus3 is in true production, the Critical-impact rows are live exposures, not pilot-phase abstractions.** The single largest open mitigation is **offsite backup**, which remains a PI decision (§4.2, §5.3). The applied snapshot + read-only-ACL combination covers the *common* failure (someone deletes or overwrites a file) but nothing array-wide or offsite.

---

## 4. Gaps and Required IT Information

> **⚠️ GAP:** The following information is needed from IT to finalize risk assessment and mitigation strategies.

### 4.1 Technical Factsheet Request

| Question | Why It Matters |
|----------|----------------|
| ~~Exact drive configuration (count, model, capacity)~~ Resolved: 6 × 20 TB | Confirm usable space; assess URE risk |
| Drive model/manufacturer | URE risk assessment for 20 TB drives |
| Filesystem (ext4, ZFS, other) | ZFS offers better integrity checking |
| Snapshot reservation size | Confirm the ~37 TB gap between system-usable (~100 TB) and user-available (~63 TB) |
| ~~Snapshot capability~~ Confirmed active (daily) | Key mitigation for accidental deletion — capability resolved; configuration detail still needed |
| Snapshot retention policy (if any) | How far back can we recover? (still unverified) |
| Restore procedure and timeline | How long to recover from snapshot? |
| Current permissions model | Inform access control design |
| Monitoring/alerting for drive failures | Ensure timely replacement |
| Scrubbing schedule (if configured) | Bit rot detection |

### 4.2 Backup Options Discussion

| Option | Description | Questions for IT/PI |
|--------|-------------|---------------------|
| QNAP cloud backup | QNAP offers myQNAPcloud storage | Cost? Capacity limits? Acceptable for research data? |
| Institutional backup | Does IT offer backup for NAS? | Available? Cost? Retention? |
| Manual offsite | Periodic export to external drives stored off-site | Acceptable for critical data? Who manages? |
| Cloud (Zenodo/institutional repo) | For publication packages only | Already planned for publications |

---

## 5. Recommended Mitigations

### 5.1 Immediate (No IT Dependency)

| Mitigation | Implementation | Status |
|------------|----------------|--------|
| **Checksums on deposit** | SHA-256 for all files, written to per-acquisition `checksums.json` at ingest; verify periodically | ✅ Applied (write); periodic re-verify still manual |
| **Read-only after deposit** | NTFS/SMB ACLs on raw acquisition folders (operators write-but-not-modify; see §6) | ✅ Applied 2026-06-02 |
| **Minimal write access** | Operators deposit only (create-but-not-modify on `/raw/`); superusers retain Full for corrections | ✅ Applied 2026-06-02 |
| **Registry as manifest** | `registries/registry_raw.csv` is the inventory of record; the generated `registries/index.html` Finder makes it searchable for verification | ✅ Applied |

### 5.2 Dependent on IT Confirmation

| Mitigation | Implementation | Status |
|------------|----------------|--------|
| **Enable snapshots** | Daily snapshots confirmed running (visible via `@Recently-Snapshot`; retention policy TBD) | ✅ Active (retention details needed) |
| **Scrubbing schedule** | If not configured, request monthly scrub | ⚠️ Awaiting IT |
| **Monitoring alerts** | Ensure drive failure alerts go to responsible person | ⚠️ Awaiting IT |

### 5.3 Requires PI Decision

| Mitigation | Options | Status |
|------------|---------|--------|
| **Offsite backup scope** | All raw? Publications only? Critical projects? | ⚠️ Awaiting decision |
| **Backup method** | Cloud service? External drives? Institutional? | ⚠️ Awaiting decision |
| **Backup responsibility** | IT? Data Management Lead? Project leads? | ⚠️ Awaiting decision |

---

## 6. Access Control Model

> **✅ DECIDED + APPLIED 2026-06-02** on `J:\gjesus3-data\`. This section is the **conceptual summary**; the authoritative *applied* model — NTFS/SMB ACLs via the existing `CICBIOMAGUNE\GJesus` group (IT will not create custom QNAP groups), grant-only / never-DENY, with the per-role grants — lives in **[11_OPERATIONS §2.1.1 + §2.3](11_OPERATIONS.md)**. The tables below use the doc role names; the permission-role labels were renamed during the role-terminology pass (Operator→Tech, User→Researcher) — see [11_OPERATIONS](11_OPERATIONS.md) for the current labels.

### 6.1 Tiers

| Tier | Access | Typical Users |
|------|--------|---------------|
| **Admin (superuser)** | Full read/write everywhere; registry management; corrections / project close-out | Data Management Lead, PI |
| **Operator** | Write to staging; deposit to raw (create-but-not-modify, via the ingest workflow); Modify on registries; read/write to publications/projects | Trained group members |
| **Researcher (user)** | Read-only to `/raw/`; read/write to their own `/projects/` (incl. the `metadata/` subfolder) | Group researchers |
| **Viewer** | Read-only to specified areas | Collaborators (if needed) |

### 6.2 Area-Specific Permissions

| Area | Admin | Operator | Researcher | Viewer |
|------|-------|----------|------------|--------|
| `/staging/` | RW | RW | RW | — |
| `/raw/` (during deposit) | RW | Create files/folders | — | — |
| `/raw/` (after deposit) | RW (corrections) | RO | RO | RO |
| `/publications/` | RW | RW | RO | RO |
| `/projects/` | RW | RW | RW (own) | RO |
| `/registries/` | RW | Modify | RO | RO |

> **Hard links and the read-only carry-through.** Project workspaces reference raw data via **NTFS/SMB hard links** (DECIDED + APPLIED 2026-06-02; the older Windows `.lnk` shortcut method is retired). A hard-linked project copy is a *real directory entry sharing the raw file's inode*, so it inherits the same ACL — the read-only-after-deposit lock on `/raw/` carries through to the project copy automatically, and the link costs zero extra storage. This is why "Researcher RW on own `/projects/`" does **not** open a back door to mutate raw bytes: the shared inode is still read-only. See [10_TOOLS §2.1.1](10_TOOLS.md) for the linking mechanics and [03_RAW_STORAGE §8](03_RAW_STORAGE.md) for the raw→project linking rule.

---

## 7. Performance Considerations

### 7.1 Expected Use Patterns

| Use Case | Frequency | Data Volume | Performance Need |
|----------|-----------|-------------|------------------|
| Raw deposit | Weekly per user | 1-50 GB per session | Moderate |
| Publication packaging | Monthly | 1-10 GB | Low |
| Data retrieval for analysis | Occasional | Variable | Low (copy out, work locally) |
| Registry queries | Frequent | KB | Trivial |

### 7.2 Performance Notes

- **RAID 5 write penalty:** Parity calculations reduce write speed; acceptable for archival workload
- **2.5 GbE link:** ~300 MB/s theoretical max; adequate for expected volumes
- **Recommendation:** Large deposits should use wired connection, not WiFi

---

## 8. Related Documents

- [01_OVERVIEW](01_OVERVIEW.md) — System purpose and constraints
- [03_RAW_STORAGE](03_RAW_STORAGE.md) — Raw area structure + raw→project hard-link rule (§8)
- [10_TOOLS §2.1.1](10_TOOLS.md) — Project linking mechanics (NTFS/SMB hard links; `.lnk` retired)
- [11_OPERATIONS](11_OPERATIONS.md) — Operational workflows; authoritative *applied* permission model (§2.1.1 + §2.3)

---

## Open Questions Summary

| ID | Question | Owner | Status |
|----|----------|-------|--------|
| INFRA-01 | ~~Confirm drive configuration and usable capacity~~ Resolved: 6 × 20 TB, RAID 5, ~100 TB system / ~63 TB user-available | IT | ✅ Resolved |
| INFRA-02 | Confirm filesystem (ext4/ZFS) | IT | ⚠️ Open |
| INFRA-03 | ~~Confirm snapshot capability~~ Snapshots confirmed active (daily). Still need: retention policy details, restore procedure | IT | 🔶 Partially resolved |
| INFRA-04 | Clarify remote/VPN access options | IT | ⚠️ Open |
| INFRA-05 | Decide backup scope (all raw / pubs only / critical) | PI | ⚠️ Open |
| INFRA-06 | Decide backup method | PI + IT | ⚠️ Open |
