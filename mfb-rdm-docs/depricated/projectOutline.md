
## Capture Note: MFB gjesus3 Microscopy Data Organization Pilot (WSI-first)

### Current situation

* The MFB group historically accumulated **hundreds of GB** of microscopy/histology data on **external drives**, mixed with other files, organized primarily by **individual researcher folders**, with inconsistent naming and no reliable group-level provenance.
* A new **whole-slide / large-area microscopy instrument** (Zeiss Axiocam 7 workflow) will substantially increase data volume and urgency for a system.
* Institute policy expects platform-level responsibility for original raw imaging data retention (institutional effort ongoing), but the timeline and execution are uncertain; Jesús does not want to wait.

### Primary objective (near-term)

Establish a **lab-specific, enforceable storage and organization system** on **gjesus3** for **original raw microscopy acquisitions** and associated structured project work, starting with Zeiss WSI/large-area scans, to prevent uncontrolled dumping and to enable:

1. **Publication traceability:** ability to trace from figures / derived outputs back to raw acquisitions, including sufficient metadata to interpret and defend results.
2. **Internal collaboration:** ability for MFB members to find, share, and work on images within the group with consistent conventions (external sharing is a “nice-to-have,” internal sharing is a must).
3. **Future platform data management systems** at the institute level to adopt methods proven to work here on high-capacity / large volume data sources.

### Scope boundaries (explicitly stated in the thread)

* This is a **lab-specific solution** for MFB and **independent** of the institute/platform implementation.
* It must remain **compatible** with an eventual platform-level solution, given the overlap in responsibilities (especially long-term raw retention).

### Initial deployment approach (working concept)

* Use a well-defined directory structure and naming conventions on gjesus3.
  * (Option under discussion) High level branch of dir structure to maintain logical separation of original raw scan data (possibly with instrument metadata) and active project workspace (possibly dervied derived files).
* Start with a small set of “active members” who agree to follow rules; access is conditional.
* Implement a **scan registry** with minimal but adequate metadata for raw files.
* (Option under discussion) Maintain separate logical registries:

  * **Raw inventory registry** for authoritative raw files + acquisition metadata.
  * **Provenance registry/ledger** capturing inputs → process → outputs for derived files, enabling programmatic trace-back.

### Stakeholders and roles (current)

**Group owner / sponsor**

* **Jesús Ruiz-Cabello (PI, MFB)**

  * Sets expectations that only responsible users participate; access is conditional on compliance.

**Data management lead**

* **Ryan Tasseff (Data Office, CIC biomaGUNE)**

  * Defines rules/conventions; organizes stakeholder alignment meeting; implements the conventions with the initial user cohort.

**Primary user cohort (initial “active members”)**

* Marta Beraza Cabrerizo
* Ainhize Urkola Arsuaga
* Irene Fernández Folgueral
* Claudia Beatriz Miranda Pérez de Alejo
* Itziar Souto Riobo
* Ekine Olaizola Bárcena
* Tania Orosco Salinas (explicitly positioned as safeguard for certain human/clinical datasets)

**Platform stakeholder (added)**

* **Irantzu Llarena (Platform Manager)**

  * In contact with Jesús’s group regarding data management strategy for the WSI equipment; will monitor and update (“main users are Jesús’s group for this equipment”).
  * Relevance: although the platform solution is separate and more complex, it is a dependency/constraint for long-term alignment and potential migration.

**Operational/technical stakeholder (implicit, non-owner)**

* **IT** (configured the NAS/RAID and provides network access as `gjesus3`; not providing additional backup/recovery per your earlier description).

  * This constraint increases the importance of clear rules, integrity checks, and controlled access.

### Key coordination note

Irantzu’s email indicates the platform is already tracking “data management strategy” for this instrument and recognizes that Jesús’s group are the main users. This reinforces the need to:

* keep this pilot lightweight and implementable now, and
* design it so it can later align with / partially migrate to the platform-level approach without rework.
* design for later expansion to additional microscopy data sources (histology using more conventional instruments).
* Design for later use with OMERO microscopy image server.  


