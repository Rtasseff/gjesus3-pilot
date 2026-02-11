## A. Confirm storage “zones” and their intent (decisions → operational definitions)

1. **Define the four zones (1–2 sentences each)**

   * Staging / intake (temporary, messy, controlled promotion)
   * Raw archive (structured, long-term, immutable-by-policy, modality/instrument substructure)
   * Publication archive (structured, long-term, flexible per paper)
   * Projects workspace (temporary, active work; still needs provenance rules)

2. **Decide what “long-term” and “temporary” mean**

   * Raw: retention expectation (years) and cold-storage migration trigger
   * Publications: retention expectation and what qualifies as “publication package”
   * Projects: how long project workspaces live; when/how they are “closed” or migrated/archived

3. **Decide where registries live (single top-level `REGISTRY/` vs embedded)**

   * You can keep it open for now, but you need an initial default to implement.

Deliverable: a short “zone definitions” note (internal) that you can paste into future spec updates.

---

## B. Registry design (three registries + minimal viable schemas)

4. **Raw registry: decide the minimum metadata fields**

   * Unit of registration: “scan session / acquisition bundle” (recommended)
   * Required fields (propose now): ScanID, acquisition datetime, instrument/modality, operator, project pointer, sample/animal pointers, file format, canonical path, file count, checksum manifest present (Y/N)

5. **Publication registry: decide what it registers**

   * Unit: “publication package” (PaperID + package version)
   * Required fields: PaperID (internal), citation/DOI (when available), corresponding author/PI, related ProjectIDs, related ScanIDs (or query-based linkage), package path, package version/date, README present (Y/N)

6. **Project registry (provenance): decide the minimum provenance rules**

   * Unit: “activity record” (inputs → process → outputs)
   * Required fields: ActivityID, date, operator, tool/software+version, input references (ScanIDs/FileIDs), output paths, parameters reference (file path or short JSON)

7. **Choose the “ID strategy” that ties registries together**

   * ScanID format (simple counter is easiest)
   * Optional FileID (SHA256) for raw and publication-critical outputs
   * ActivityID for provenance steps

Deliverable: three draft schemas (even as CSV column headers + one example row each).

---

## C. Data types inventory + “volunteer deep dive” process

8. **Create a data-types sign-up sheet**

   * Columns: Data type label, instrument/source, typical file formats, typical size/unit, typical users, typical downstream tool (QuPath, ZEN, etc.), “volunteer owner”
   * Ask each initial user to list what they generate (not just WSI)

9. **Assign a “volunteer owner” per data type**

   * For each data type, require a 15–20 min walkthrough:

     * where the files come from (instrument/export path)
     * example file(s)
     * what software people use to open/analyze
     * what metadata is embedded vs external

10. **Collect one representative example dataset per type**

* Small enough to share internally (or a pointer to a real dataset)
* This becomes test input for scripts and registry fields

Deliverable: completed sheet + one “example dataset” pointer per type.

---

## D. Extended metadata selection (REMBI-based, but pared down)

11. **Decide “core vs extended” metadata approach**

* Core = must be in the registry (fast to fill, enforceable)
* Extended = captured elsewhere (machine metadata export, ELN link, forms/spreadsheet)

12. **Build the REMBI field review mechanism**

* Option A: Microsoft Forms (vote Yes/No + comment per field)
* Option B: shared spreadsheet (recommended for easier bulk review)
* Seed it with REMBI fields grouped by category (Sample, Specimen prep, Acquisition, Data)

13. **Run a short review cycle**

* Each pilot user votes/comment
* You curate into:

  * “Core registry fields”
  * “Extended but required”
  * “Nice-to-have”

Deliverable: “REMBI-to-MFB minimal set” decision list.

---

## E. Scripts and automation (batch ingest, naming, registry, metadata extraction)

14. **Define the minimum script set for pilot (don’t overbuild)**

* `ingest_raw_batch`:

  * takes a folder of newly acquired files
  * assigns ScanIDs
  * moves into raw zone structure
  * generates checksum manifest
  * appends raw registry entry
* `create_publication_package`:

  * creates publication folder structure + README stub
  * pulls referenced ScanIDs/derived outputs into an export bundle (copy or link strategy)
  * writes/updates publication registry entry
* `log_activity` (provenance helper):

  * simple CLI to append an activity record for derived outputs

15. **Decide what metadata can be parsed from filenames**

* Identify current naming patterns in legacy data
* Define a minimal “supported filename pattern” (even if optional)
* Build parser rules incrementally (start with a few reliable tokens)

16. **Decide what metadata can be extracted from files**

* For CZI and common formats: identify extractable fields (pixel size, channels, objective, acquisition date)
* Decide: store extracted fields in (a) raw registry, (b) sidecar JSON per scan, or (c) both

17. **Choose where scripts run**

* On a designated workstation? On the acquisition PC? On a shared “operator” machine?
* Decide how credentials/access will work (especially if enforcing immutability)

Deliverable: a one-page “automation plan” listing scripts, inputs/outputs, and what they write.

---

## F. Operational rules for “projects are temporary but still traceable”

18. **Define project lifecycle rules**

* What creates a project workspace?
* When is a project considered “closed”?
* What must be migrated into publication archive vs left behind?

19. **Define minimum provenance compliance for projects**

* Rule proposal (pilot-friendly): provenance required for:

  * any conversion (e.g., CZI→OME-TIFF)
  * any analysis that produces publication-bound outputs
  * any dataset shared outside MFB

20. **Define what happens to derived artifacts when projects close**

* Archive into publication folder (if relevant)
* Or archive project as a snapshot (if storage allows)
* Or delete with explicit approval (if truly temporary)

Deliverable: a short “project lifecycle + provenance minimums” note.

---

## G. Practical coordination / ownership

21. **Confirm stakeholder responsibilities**

* Who can promote from staging → raw?
* Who can create publication packages?
* Who can change conventions (change control)?

22. **Set the near-term cadence**

* 1x kickoff meeting to confirm schemas + first data types
* 1x review meeting after first real ingest (what broke / what’s annoying)
* 1x decision meeting for REMBI-minimal set

Deliverable: a simple owner matrix (task → owner → due).

---

## Suggested execution order (so you’re not blocked)

1. Data types sign-up + volunteers (C)
2. Registry schemas (B)
3. Zone definitions + directory skeleton (A)
4. REMBI vote sheet (D)
5. Minimum ingest script + checksum + raw registry append (E14)
6. Project provenance minimum + helper logging (F)
7. Publication package automation (E + publication registry)


