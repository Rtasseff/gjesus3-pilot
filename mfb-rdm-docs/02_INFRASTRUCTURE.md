# 02 — Infrastructure

**Parent:** [Documentation Index](00_INDEX.md)  
**Status:** ⚠️ Gaps identified
**Last Updated:** 2026-02-26

---

## Purpose

This document describes the hardware infrastructure, access model, and risk assessment for the gjesus3 storage system.

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

> **⚠️ GAP:** Exact drive configuration and usable capacity need confirmation from IT.

| Attribute | Expected Value | Status |
|-----------|----------------|--------|
| **RAID level** | RAID 5 | ✅ Confirmed |
| **Drive count** | 8 | ⚠️ Needs confirmation |
| **Drive capacity** | ~14-16 TB each (est.) | ⚠️ Needs confirmation |
| **Usable capacity** | ~100 TB | 🔶 Approximate |
| **Filesystem** | ext4 or ZFS | ⚠️ Needs confirmation |

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
| Accidental deletion | 🔶 Partial | Daily snapshots are active; read-only permissions after deposit |
| Ransomware/malware | ❌ No | Snapshots; offsite backup; access controls |
| Controller/enclosure failure | ❌ No | Offsite backup |
| Site disaster (fire, flood) | ❌ No | Offsite backup |
| User error (overwrite, corruption) | ❌ No | Snapshots; checksums for detection |

### 3.3 Risk Rating

| Risk | Likelihood | Impact | Mitigation Status |
|------|------------|--------|-------------------|
| Single drive failure | Medium | Low (recoverable) | ✅ RAID 5 handles |
| Multi-drive failure | Low | Critical | ⚠️ No mitigation |
| Accidental deletion | Medium | High | 🔶 Snapshots active + permissions planned |
| Ransomware | Low | Critical | ⚠️ No mitigation |
| Site disaster | Very Low | Critical | ⚠️ No mitigation |

---

## 4. Gaps and Required IT Information

> **⚠️ GAP:** The following information is needed from IT to finalize risk assessment and mitigation strategies.

### 4.1 Technical Factsheet Request

| Question | Why It Matters |
|----------|----------------|
| Exact drive configuration (count, model, capacity) | Confirm usable space; assess URE risk |
| Filesystem (ext4, ZFS, other) | ZFS offers better integrity checking |
| Snapshot capability and configuration | Key mitigation for accidental deletion |
| Snapshot retention policy (if any) | How far back can we recover? |
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
| **Checksums on deposit** | SHA-256 for all raw files; verify periodically | 🔶 Planned |
| **Read-only after deposit** | chmod or ACL on raw acquisition folders | 🔶 Planned |
| **Minimal write access** | Only operators can deposit; no delete permissions | 🔶 Planned |
| **Registry as manifest** | Registries serve as inventory for verification | 🔶 Planned |

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

### 6.1 Proposed Tiers

| Tier | Access | Typical Users |
|------|--------|---------------|
| **Admin** | Full read/write everywhere; registry management | Data Management Lead, PI |
| **Operator** | Write to staging; deposit to raw (via workflow); read/write to publications/projects | Trained group members |
| **Viewer** | Read-only to specified areas | Collaborators (if needed) |

### 6.2 Area-Specific Permissions

| Area | Admin | Operator | Viewer |
|------|-------|----------|--------|
| `/staging/` | RW | RW | — |
| `/raw/` (before deposit) | RW | Create folder, write files | — |
| `/raw/` (after deposit) | RO | RO | RO |
| `/publications/` | RW | RW (own) | RO |
| `/projects/` | RW | RW (own) | RO |
| `/registries/` | RW | RO | RO |

> **🔶 DRAFT:** Exact implementation depends on NAS permissions model capabilities.

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
- [11_OPERATIONS](11_OPERATIONS.md) — Operational workflows including access requests

---

## Open Questions Summary

| ID | Question | Owner | Status |
|----|----------|-------|--------|
| INFRA-01 | Confirm drive configuration and usable capacity | IT | ⚠️ Open |
| INFRA-02 | Confirm filesystem (ext4/ZFS) | IT | ⚠️ Open |
| INFRA-03 | ~~Confirm snapshot capability~~ Snapshots confirmed active (daily). Still need: retention policy details, restore procedure | IT | 🔶 Partially resolved |
| INFRA-04 | Clarify remote/VPN access options | IT | ⚠️ Open |
| INFRA-05 | Decide backup scope (all raw / pubs only / critical) | PI | ⚠️ Open |
| INFRA-06 | Decide backup method | PI + IT | ⚠️ Open |
