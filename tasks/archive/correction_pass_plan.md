# Correction Pass + Schema/Docs Improvements — Implementation Plan

> **Status:** APPROVED 2026-06-11, not yet executed. Master plan for the post-first-review correction pass.
> Detailed, filter-safe execution spec for the 11 code items lives in the companion **[`correction_pass_handoff.md`](correction_pass_handoff.md)**; this file is the full plan (code corrections + schema + docs + over-engineering decisions).

## Context

A first-pass review of the gjesus3 RDM pilot found three classes of issue: code correctness/integrity bugs, schema-marker and identity gaps, and documentation-clarity problems. The user reviewed the findings and gave concrete decisions (this plan encodes them). The driver: **as soon as the correctness/integrity fixes land, the team starts drawing in historical data from old drives** — so those fixes gate the next milestone. Alongside them, the user wants the now-stable schema promoted from DRAFT to DECIDED, a queryable `subject_id` column added, free-text fields nudged toward standard vocabularies (without blocking adoption), and a documentation-clarity pass so a non-technical tech can self-onboard.

## Scope & ground rules

- **Sandbox-first.** Test every write against `J:\gjesus3-sandbox` (explicit `--nas-root J:\gjesus3-sandbox`); seed its `registries/` with header-only CSVs first. The live `J:\gjesus3-data` was just purged (near-empty, moving to true production) — touch it only after sandbox verification and user sign-off.
- **Branch/commit:** one branch `fix/correction-pass-2026-06`, one commit per item, stage specific files (never `git add -A`), `Co-Authored-By` trailer. `gh` not installed → push + hand the user a compare URL.
- **Filter note:** an earlier cold handoff tripped a false-positive policy block on domain vocabulary. Keep any life-sciences field *names* as inert schema strings; if a fresh executor session trips the filter, run the corrections in a warm session that already holds repo context.

---

## Part 1 — The 11 code corrections (full detail in `correction_pass_handoff.md`)

| # | Fix | Key location |
|---|-----|--------------|
| 1 | Dry-run: default ON during testing, **unmistakable** state + end-of-run "nothing was written" summary; documented note to flip default OFF after the testing period | `tools/operator/gui/templates/index.html:134`, `app.js` |
| 2 | Build & verify the microscopy GUI `.exe` (needs a real `.czi` for the final read-check) | `tools/operator/gui/microscopy_ingest.spec` |
| 3 | Seed recipes for CELL + LSM9 from the exhibit configs | `tools/configs/cell_observer_*`, `lsm900_laura_uptake_TEST.yaml` → `tools/operator/recipes/` |
| 4 | Archive re-run idempotency: stop overloading `original_name` (dedup key never matches) | `tools/ingest_raw.py:731`, `tools/ingest/config.py` |
| 5 | Crash-after-copy orphan: make registry append the commit point; move `--delete-source` to the end | `tools/ingest_raw.py` `ingest_single` |
| 6 | Empty/junk folder must fail loudly, write nothing | `tools/ingest_raw.py` generic/unknown paths |
| 7 | Cross-drive `relpath` ValueError → try/except, fall back to absolute | `tools/ingest_raw.py:43,46` |
| 8 | **Registry lock** + concurrency test + docs (new `tools/ingest/locking.py`, lockfile mutex around generate-ID→append) | `tools/ingest/acq_id.py`, `registry.py`, `ingest_raw.py` |
| 9 | CSV append safety: BOM-tolerant header read + trailing-newline guard, shared helper across all appenders, documented | `tools/ingest/registry.py:89,103` + `linker.py:35`, `provenance.py`, `pending.py`, `create_project.py` |
| 10 | External reference DB: fix stale "blocked on IT" docs; document the optional `~/.my.cnf` / `GJESUS3_MYCNF` credential install; **keep** the deferred-recovery queue (it is the intended design) | `mfb-rdm-docs/09_MODALITIES.md`, `08_METADATA.md`, `tools/operator/README.md` |
| 11 | `os.link` diagnostic for the Linux (MRI) + Mac-fronted (NI) machines; Windows SMB already verified working; document fallbacks | new `tools/diagnostics/test_oslink.py` |

---

## Part 2 — Schema & metadata (per user decisions)

### S1 — Add the `subject_id` registry column now (auto-populated; best-guess to meet goals)

**Decision (documented):** `subject_id` holds the **canonical reused facility animal id** (`<animal_code>-AE-biomaGUNE-<NNNN>`) — the same value as the sidecar `subject.facility_animal_id`, which is already the documented subject identity and the future XNAT/OMERO join key. It is **empty** for non-animal samples (cells/material/phantom) and best-effort (may be empty when the DB lookup misses — non-blocking, consistent with the enrichment model). This makes the registry answer "all acquisitions of animal X" without opening sidecars (the current gap, because `sample_id` is overloaded and changes meaning per sample type).

**Wiring (validated against the code):**
1. `tools/ingest/registry.py` — insert `"subject_id"` into `REGISTRY_FIELDS` between `sample_type` and `session_id` (line ~35); add `"subject_id": cfg.get("subject_id", "")` to the `build_row` return dict.
2. `tools/ingest/resolver.py` — add `"subject_id"` to `AUTO_COLUMNS` (line ~96), so it's correctly rejected if a user puts it in a YAML `registry:` block. Do **not** add to `USER_CONTROLLABLE_COLUMNS`.
3. `tools/ingest_raw.py` — after the Step-8.5 enrichment call returns `subject_block` (line ~966), before the Step-10 `build_row` (line ~1077), stash: `cfg_single["subject_id"] = (subject_block or {}).get("facility_animal_id", "")`. Enrichment already runs before the append, so the value is in-memory; this is the only new data-flow line.
4. **Migration:** run `python tools/migrate_registry_columns.py --dry-run` then live — it auto-detects the new column, backs up to `.bak.<ts>`, pads existing rows, rewrites in field order. Update that script's docstring (currently names only `session_id`/`primary_kind`) to be generic. Run on sandbox first; live is near-empty post-purge.
5. **Docs:** document the column in `mfb-rdm-docs/06_REGISTRIES.md` §2.2 (population method = Auto; value = facility id; empty for non-animal) and record the identity decision; update `00_INDEX.md` schema/version-history; align `08_METADATA.md` (it already produces `facility_animal_id`).

### S2 — Promote the in-use schema from DRAFT → DECIDED

**Decision:** The implemented, in-production conventions are no longer drafts. Flip their markers (both the emoji `🔶 → ✅` and the word `DRAFT → DECIDED` forms) for: the `subject:` / `condition:` / `anatomy:` blocks; `primary_kind` + `primary_file_name`; `session_id`; the `sample_type` 5-value vocabulary; the Subject/Sample identity model; and the ISA terminology mapping.

**Locations (pattern — flip the in-use markers, representative spots):** `mfb-rdm-docs/06_REGISTRIES.md` (header status line ~4; `REGISTRY_FIELDS` comments ~36–37; schema table rows ~72–73; §2.3/§2.3a/§2.4 section headers ~106, 124, 169; linked-requirements intro ~191), `08_METADATA.md` (the §4.4/§4.5/§4.6 subject/condition/anatomy headers), `09_MODALITIES.md` (any DRAFT on these blocks), and the `00_INDEX.md` Key Decisions table + Quick-Links status. **Leave untouched** genuine open items (GAP/EVALUATING/INPUT NEEDED): SEM/TEM inclusion, MRI 7T-vs-11.7T codes, REMBI field-selection vote, backup strategy. Add a dated DECIDED note rather than silently deleting DRAFT history.

### S3 — Free-text fields: suggest standard vocabularies, don't enforce (yet)

**Decision:** People won't fill controlled vocab if forced without help, and forcing kills adoption. So **for now: free entry stays**, but the docs (and per-instrument template comments) *suggest* the domain-standard vocabulary per field and link real resources. If enforcement is added later it must come with assistance (autocomplete/suggest-list) — that pairing is a backlog item.

**Do now (docs only):** Add a "Suggested vocabularies (optional)" subsection in `08_METADATA.md` (and reference from `06_REGISTRIES.md`) mapping each free-text field to its standard + link, and add a one-line pointer in the comment header of the per-instrument templates (`tools/templates/instruments/*.yaml`):
- species → **NCBI Taxonomy** (docs already normalize to `Mus musculus` / `Rattus norvegicus`)
- strain → **IMSR/MGI** (mouse), **RGD** (rat)
- disease_model / disease_state → **MONDO** (disease ontology; DOID/EFO as alternates)
- cell_line → **Cellosaurus**
- anatomy → **UBERON** (already in use — the model to follow)
- sample_type → already a controlled 5-value REMBI-aligned vocab (note it as the existing example)
- imaging method → REMBI "imaging method" / **FBbi** (biological imaging methods)

**Backlog:** "Assisted controlled-vocab entry (suggest-list / autocomplete at point of capture in the CLI prompts + GUI) so a future soft-enforcement doesn't add friction."

### S4 — Migration prep + the metadata-DB-intermediate idea (backlog + docs)

**Decision:** XNAT (preclinical DICOM) and OMERO (microscopy) remain the lead targets, **and are very-near-future** — document them as such. But the user is rightly weighing a lighter intermediate first.

- **Backlog item:** "Metadata-only database that indexes the registries + JSON sidecars and points to the images on the NAS — e.g. a small SQLite/Datasette (or similar) index. Could (a) be the *searchable face* on the NAS now, before any platform migration, and (b) accommodate the **nested** sidecar JSON better than the flat key-value import that XNAT/OMERO expect. Evaluate as an intermediate or stepping-stone; XNAT/OMERO stay the lead destinations." (Ties directly to the earlier value-loop/search finding — the cheap "get value out" win.)
- **Docs:** add a short "Very-near-future: image servers" note (in `13_GJESUS3_ROLE.md` and/or `00_INDEX.md`) stating microscopy→OMERO, DICOM→XNAT, both via flat key-value import, both imminent.
- **Simple prep now (no new code):** keep the flat registry clean and keep DICOM UIDs captured (already done) — these are what make the eventual import frictionless. No projector code in this pass (not "simple").

---

## Part 3 — Over-engineering: keep everything for now (explicit decision)

**Decision:** Nothing is removed in this pass. The enrichment + deferred-recovery machinery (and the rest) was built iteratively to handle genuinely different source systems, it works, and historical-data ingest starts right after these fixes — so pulling parts now adds risk for no near-term gain. The earlier "trim the recovery apparatus" suggestion is **withdrawn** (item 10 already establishes the queue is the intended design).

**Do:** add one short note (in `tasks/BACKLOG.md`) — "At the true-production restart, review which pilot subsystems carry forward vs. are replaced by platform-native equivalents (e.g. XNAT prearchive/custom-variable tooling) — decide then, not now." No code change.

---

## Part 4 — Documentation clarity

### D1 — Kill the changelog-in-the-header blobs
Create top-level **`CHANGELOG.md`** as the single narrative history. Replace the bloated `**Last Updated:**` paragraphs with a one-line `date — short summary — see CHANGELOG.md` in: `mfb-rdm-docs/00_INDEX.md:6`, `08_METADATA.md:5`, `09_MODALITIES.md:5`, `tasks/tasks.md:2-3`. Move the existing `00_INDEX.md` Version History table (lines ~209–249) into `CHANGELOG.md` (or keep it there and link) and trim its longest cells to one sentence + a doc pointer.

### D2 — A "start here" front door for a tech
Add top-level **`START_HERE.md`** (≤1 screen): the three no-YAML front-ends first, "set `GJESUS3_ROOT`", "dry-run first", and a link onward to `mfb-rdm-docs/11_OPERATIONS.md` §3.2/§3.3. Link it first from `README.md`. Also: flip `11_OPERATIONS.md` status (line ~4) from "📋 Planned" to "🔶 Draft / In use" (the workflow it documents is live), bump its stale `Last Updated` (line ~5), and signpost the no-YAML §3.3 ahead of the YAML §3.2 for the common case.

### D3 — Glossary + one status vocabulary
Add top-level **`GLOSSARY.md`** defining the heavily-used terms a newcomer hits undefined: REMBI, ISA, UBERON, JCAMP-DX, ARRIVE, XNAT, OMERO, FAIR, "sidecar", "discovered.*", "ecosystem", `primary_kind`, ACQ/PROJ/PUB/DS ids, "quasi-production". Link from `README.md` + `00_INDEX.md`. Resolve the **dual status-marker vocabularies** by stating the mapping once (emoji legend in `00_INDEX.md:28` ↔ word set in `CLAUDE.md:59–65`) — put the equivalence in the glossary and have `CLAUDE.md` reference the emoji legend rather than define a parallel set.

### D4 — Fix stale cross-refs
In `mfb-rdm-docs/00_INDEX.md:125,132`: update the two links whose anchor is the old `#211-project-linking--windows-first-design-decision` to the current `10_TOOLS.md:72` heading anchor `#211-project-linking--hard-links-current-over-lnk-shortcuts`, and rewrite the stale "resolved by `.lnk` shortcuts / Windows-first" wording to reflect the 2026-06-02 hard-link decision. Quick scan for other `.lnk`-era anchors after the rename.

---

## Suggested sequencing

1. **Integrity/robustness first (unblocks historical ingest):** 7 → 9 → 8 → 4 → 5 → 6. Test each on the sandbox.
2. **Schema:** S1 (subject_id + migration on sandbox) → S2 (marker promotion) → S3 (vocab docs) → S4 (backlog + docs).
3. **Operator-facing:** 1 (dry-run) → 3 (recipes) → 2 (exe build; needs a `.czi`).
4. **Docs-clarity:** D1 → D2 → D3 → D4 (can run in parallel; mostly independent of code).
5. **External-dependent, hand to user:** 10 (credential install is out-of-band) + 11 (run `test_oslink.py` on MRI/NI).
6. **Over-engineering:** Part 3 note only.

## Verification

- **Per code item:** run the targeted sandbox test in the handoff doc (archive re-run = full skip; empty folder fails; cross-drive config runs; BOM + missing-newline both handled; concurrency test green).
- **S1:** on the sandbox, ingest an animal-sample acquisition → confirm `subject_id` in `registry_raw.csv` equals the sidecar `subject.facility_animal_id`; ingest a cells sample → `subject_id` empty; run the migration `--dry-run` then live and confirm `.bak` created + header has the new column in position. Add/extend a unit test for `build_row` populating `subject_id`.
- **S2–S4 / docs:** `grep` confirms no stray "blocked on IT" or old `.lnk` anchors remain; the four bloated headers are one-liners; `START_HERE.md`, `GLOSSARY.md`, `CHANGELOG.md` exist and are linked from `README.md`; cross-reference links resolve (anchor check).
- **End-to-end:** a fresh dry-run ingest through the GUI (and a CLI front-end) on the sandbox completes with the clear dry-run summary, writes the expected sidecar + registry row including `subject_id`, and the registry passes `tools/validate_registries.py`.
- Push `fix/correction-pass-2026-06`; provide the compare URL. Items 2 and 11 surface to the user (a `.czi`; access to the MRI/Mac hosts) rather than blocking the rest.

## Critical files (summary)
- Code: `tools/ingest/registry.py`, `resolver.py`, `acq_id.py`, `linker.py`, `provenance.py`, `pending.py`, `tools/ingest_raw.py`, `tools/ingest/config.py`, `tools/create_project.py`, `tools/migrate_registry_columns.py`; new `tools/ingest/locking.py`, `tools/diagnostics/test_oslink.py`; `tools/operator/gui/*`, `tools/operator/recipes/*`.
- Docs: `mfb-rdm-docs/{00_INDEX,06_REGISTRIES,08_METADATA,09_MODALITIES,11_OPERATIONS,13_GJESUS3_ROLE,10_TOOLS}.md`, `tasks/{tasks,BACKLOG}.md`, `tools/templates/instruments/*.yaml`; new top-level `START_HERE.md`, `GLOSSARY.md`, `CHANGELOG.md`.
