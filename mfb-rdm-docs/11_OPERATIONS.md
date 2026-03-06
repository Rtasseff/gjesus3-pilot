# 11 — Operations

**Parent:** [Documentation Index](00_INDEX.md)  
**Status:** 📋 Planned  
**Last Updated:** 2026-03-06

---

## Purpose

This document covers operational aspects: roles, permissions, workflows, onboarding, and pilot management.

---

## 1. Roles and Responsibilities

### 1.1 Role Definitions

| Role | Responsibilities | Who |
|------|------------------|-----|
| **System Owner** | Strategic decisions; access authorization; escalation | Jesús Ruiz-Cabello (PI) |
| **Data Management Lead** | Define rules; implement system; support users; manage registries | Ryan Tasseff |
| **Operator** | Deposit data; maintain provenance; follow conventions | Trained group members |

### 1.2 Authorized Users (Initial Pilot)

| Name | Role | Notes |
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

| Area | Data Mgmt Lead | Operators | Others |
|------|----------------|-----------|--------|
| `/staging/` ¹ | Read/Write | Read/Write | None |
| `/raw/` (pre-deposit) | Read/Write | Create/Write | None |
| `/raw/` (post-deposit) | Read | Read | Read (if granted) |
| `/publications/` | Read/Write | Read/Write (own) | Read (if granted) |
| `/projects/` | Read/Write | Read/Write (own) | None |
| Registries | Read/Write | Read | None |

> ¹ NAS `staging/` is a **secondary convenience dump**. The recommended ingest path uses fast local or network storage as the primary source (see [03_RAW_STORAGE](03_RAW_STORAGE.md) Section 5.2).

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
| NAS user groups | QNAP user/group permissions | 📋 Configure |
| Post-deposit lockdown | chmod or ACL to read-only | 📋 Script or manual |
| Registry protection | Only admin writes to registry files | 📋 Configure |

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

> **📋 To write:** 1-page reference for daily operations.

**Contents:**
- After acquisition: what to do
- What NOT to do (don't edit raw, don't delete, etc.)
- Where to get help
- Key folder locations

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
   - Add references in raw_linked/ (linking method TBD)
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
| **Scope** | Zeiss WSI + histology + DICOM (confirmed modalities) |
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
