# 05 — Projects Area

**Parent:** [Documentation Index](00_INDEX.md)  
**Status:** ❓ Under Evaluation  
**Last Updated:** 2026-02-02

---

## Purpose

This document describes the *potential* Projects storage area — a temporary workspace for organized research work that doesn't yet belong to a specific publication.

> **❓ EVALUATING:** Given infrastructure constraints (firewall, RAID 5 performance), the value of a Projects area on gjesus3 is uncertain. This may be deferred or dropped from the pilot.

---

## 1. The Question

### 1.1 Original Intent

The Projects area was envisioned as:
- A semi-structured workspace for ongoing research
- A place to work on data before it becomes publication-ready
- A way to organize work that spans multiple potential publications
- A location with provenance tracking but less rigidity than Publications

### 1.2 The Concern

Given that gjesus3 is:
- Accessible only from specific hardwired on-site machines (not laptops)
- RAID 5 with write penalties
- Positioned as archival, not working storage

**Is a Projects area on gjesus3 actually useful?**

If researchers work locally or on other drives for daily analysis, a Projects area here may be:
- Rarely used
- A compliance burden with no benefit
- Confusing about what goes where

### 1.3 Alternatives

| Alternative | Description | Trade-offs |
|-------------|-------------|------------|
| **Skip Projects area entirely** | Only Raw and Publications on gjesus3 | Simpler; researchers manage working storage separately |
| **Projects as staging for Publications** | Temporary area that graduates to Publication when ready | Similar to Publications but looser |
| **External project management** | Projects exist on local/network drives; only finished work comes to gjesus3 | Provenance happens elsewhere; archives are clean |

---

## 2. If We Include Projects

*This section describes the specification IF the Projects area is included.*

### 2.1 Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Temporary workspace** | Projects have defined lifespans; not permanent storage |
| **Documented but flexible** | Provenance logged; internal structure is researcher-discretion |
| **Leads somewhere** | Projects should culminate in Publications, exports, or explicit closure |

### 2.2 Directory Structure

```
/gjesus3/
├── registries/
│   └── registry_projects.csv           # Projects registry (see 06_REGISTRIES)
│
└── projects/
    └── proj-ipf-biomarkers/
        ├── _project.yaml
        ├── provenance.csv
        ├── raw_linked/
        │   └── ... (links or references to raw acquisitions; method TBD)
        └── ... (researcher-organized content)
```

### 2.3 Project Lifecycle

```
Created ──▶ Active ──▶ Paused ──▶ Closed
                  │
                  └──▶ Promoted to Publication
```

**Closure options:**
- **Promoted:** Work moved to a Publication folder; project archived or deleted
- **Exported:** Data copied out to external storage; project deleted
- **Abandoned:** No further work; project deleted after retention period

### 2.4 Retention

> **🔶 DRAFT:** Projects are temporary. Suggested:
> - Active: No limit
> - Paused: 6 months maximum
> - After 6 months paused: Require decision (promote, export, or delete)

### 2.5 Provenance

Same format as Publications (see [07_PROVENANCE](07_PROVENANCE.md)), but:
- Less strict enforcement during active work
- Required for any file intended for publication or external sharing

### 2.6 Registry Fields

| Field | Type | Required |
|-------|------|----------|
| `project_id` | String | Yes |
| `short_name` | String | Yes |
| `description` | Text | Yes |
| `owner` | String | Yes |
| `start_date` | Date | Yes |
| `status` | Enum | Yes |
| `last_activity` | Date | Auto |

---

## 3. Decision Framework

### 3.1 Questions to Answer

Before deciding on Projects area inclusion:

1. **Where do researchers currently work?**
   - Local machines?
   - Other network drives?
   - Cloud storage?

2. **Would they use gjesus3 for active work?**
   - Given access constraints?
   - Given that it's positioned as archival?

3. **What problem does Projects solve?**
   - Organization before publication?
   - Provenance for work-in-progress?
   - Shared workspace within group?

4. **Is the overhead justified?**
   - Additional registry to maintain
   - Provenance logging burden
   - Lifecycle management

### 3.2 Recommendation

> **🔶 RECOMMENDATION:** Defer Projects area to Phase 2.
> 
> For the pilot, focus on:
> - Raw: Where acquisitions go
> - Publications: Where finished work goes
> 
> Let researchers work where they work. When work is publication-ready, it comes to gjesus3.
> 
> Revisit Projects after pilot if there's clear demand.

---

## 4. If We Skip Projects

### 4.1 What Happens to Work-in-Progress?

| Scenario | Approach |
|----------|----------|
| Working on analysis | Work locally or on preferred storage; not on gjesus3 |
| Need to share with group | Use existing collaboration tools (network drives, cloud) |
| Ready to archive | Create a Publication folder when work reaches publication stage |
| Need raw data | Read from Raw area; work on copies elsewhere |

### 4.2 Provenance Before Publication

If provenance is important for work-in-progress:
- Researchers maintain their own notes/logs during work
- Formalize into `provenance.csv` when creating Publication folder

---

## 5. Related Documents

- [01_OVERVIEW](01_OVERVIEW.md) — System scope decisions
- [04_PUBLICATIONS](04_PUBLICATIONS.md) — Where finished work goes
- [07_PROVENANCE](07_PROVENANCE.md) — Provenance format (if used)

---

## Open Questions Summary

| ID | Question | Owner | Status |
|----|----------|-------|--------|
| PROJ-01 | Include Projects area in pilot? | PI + Data Mgmt Lead | ❓ Evaluating |
| PROJ-02 | If yes: What retention policy? | PI | ❓ Depends on PROJ-01 |
| PROJ-03 | If yes: How strict on provenance? | Data Mgmt Lead | ❓ Depends on PROJ-01 |
| PROJ-04 | Where do researchers actually work now? | Users | 📣 Need input |
