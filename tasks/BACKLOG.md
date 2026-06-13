# Backlog — later improvements

This file is for **improvements that can be finished later** — refinements,
nice-to-haves, and second-/third-stage features that are *not* required to get
the pilot into users' and operators' hands.

It is deliberately **separate from [`tasks.md`](tasks.md)**, which tracks the
**work to get this to users** (the active path to a usable, hand-off-ready
pilot). Rule of thumb:

- *"Users/operators can't start, or start safely, without this"* → **`tasks.md`**.
- *"This makes it better / cleaner / more automated later"* → **here**.

When a backlog item becomes a blocker for delivery, promote it to `tasks.md`.

---

## Operator person/PI metadata (NI + MRI)

Context: 2026-06-09 review of `ni_ingest` / `mri_ingest` output. The **correctness
fix is already done** — NI no longer records the wrong PI (the Molecubes platform
writes the operator's *username* into `protocol.txt`'s "Principal Investigator";
the curated `ni.study.principal_investigator` + `discovered.ni_pi` are now empty,
raw value preserved in `_raw_metadata`). What's left are the *entry* mechanisms:

- [ ] **Stage 1 — `--pi` (NI) / `--user` (MRI) operator entry.** Let a single-folder
  import set the PI (NI) or acquiring user (MRI) from a CLI flag. **Blocked on a
  home:** person metadata has no clean destination today — the registry has only
  the muddy `operator` column (REG-01 person-split is unresolved), and the curated
  `ni:` ecosystem section is built by the extractor, which doesn't see the config.
  *Design when unblocked:* either (a) a config-driven `people:`/operator block
  carried through `config_builder` → `expand_batch` case → `metadata_sidecar`
  (inject into `ni.study.principal_investigator` / a new `mri` user field), or
  (b) dedicated registry person columns at the true-prod schema refresh (REG-01).
- [ ] **Stage 2 — NI second-level batch (PI-first-name dir).** NI archive layout is
  `<year>/<PI first name>/<user>/<session>`. The NI batch scope today is
  *first*-level (`<user>/<session>`); add a mode that points one level up and
  captures the `<PI first name>` dir into `discovered` (so the PI comes from the
  tree, no manual entry). Needs a `scope.py` NI branch + a discovered field.
- [ ] **Stage 3 — per-group default settings + `--group`.** A `--group MFB` flag
  that loads group-specific defaults (PI, owner, etc.) from a YAML, so operators
  set one option instead of many. Builds on
  [`tools/reference/pi_group_lookup.yaml`](../tools/reference/pi_group_lookup.yaml).

## Cross-instrument identity / naming

- [ ] **Wire `pi_group_lookup.yaml` into the tools.** Auto-map
  `discovered.pi_initials` (MRI "jrc") / PI first name (NI "Jesus") → group
  initials ("MFB") and surface it in `discovered` / the sidecar. Today the table
  is reference data only.
- [ ] **Normalize the curated `mri.subject.id`.** The ecosystem-section
  `mri.subject.id` is the raw ParaVision `SUBJECT_id` ("jrc_251016_m17_0424"). The
  registry `sample_id` is already aligned to NI's form ("m17_0424" ↔ "m13_0525",
  2026-06-09) and the canonical cross-instrument id is `subject.facility_animal_id`
  (DB), but a normalized *curated* `mri.subject.id` would need the filename-parse
  `discovered.*` fields, which the ParaVision extractor doesn't currently receive.
  (Order convention chosen: `m<animal>_<project>` to match NI + the facility id;
  flip to `<project>_<animal>` if preferred.)

## Microscopy GUI

- [ ] **Let the GUI operator set the tissue anatomical `region`.** The AxioScan
  tissue `anatomy.region` (UBERON organ) is config / per-acq-override only today;
  a GUI field — ideally auto-mapped from the `sample_short` organ letter (the "B"
  in "ID13B") via a lab letter→UBERON table — would let operators set it inline.

### GUI operator-feedback rework (2026-06-09/10) — follow-ups

The first operator test pass drove a 3-phase rework (runner polish + the
skip-vs-already-ingested fix; the atomic token widget; the rebuilt Builder).
Landed on branch `operator-ingest-tooling`. Deferred from it:

- [ ] **Filter OR support.** The new Builder filter section (label = value rows)
  is **AND-only**, because the backend `auto_discover.filter` is an exact-match
  dict (implicit AND). The operator asked for OR/AND with `+` (#15). Adding OR
  needs `expand_batch`'s filter logic to accept a list-of-conditions / per-field
  value sets — a pipeline change, not just GUI. Until then the GUI offers AND only.
- [ ] **Make the runner Researcher box REQUIRED for AxioScan** (see the parallel
  role-rename item below). The Builder now stars Researcher as high-priority, but
  the **runner** still lets a blank through to the template placeholder. For
  AxioScan tissue the researcher isn't in the filename, so the runner should block
  Ingest until it's set.
- [x] ~~Bundle `tkinter` in the PyInstaller freeze.~~ **Obsolete** — the tkinter
  folder-only OS dialog confused operators (every folder looked empty, since it
  hides files), so it was replaced by an **in-page folder browser** (`/api/listdir`
  + a modal) that shows folders AND greyed files for context. No extra freeze deps.
- [ ] **Refresh `gui/README.md` + `TESTING.md` + `microscopy_ingest.spec` comment**
  for the rebuilt Builder + token widget + the `operator` column + **recipes now
  saved as YAML to a configurable folder defaulting to `<NAS>/recipes`** (was JSON
  in the repo `tools/operator/recipes/`; that dir is now only a read-only seed
  source) — held until the operator accepts the new GUI (avoid documenting a UI
  still in flux). (The *pre-launch* recipe steps — NAS `recipes/` permission grant
  + migrating the existing repo recipes — are in [`tasks.md §0`](tasks.md), not here.)
- [x] ~~Builder `is_control` as a recipe default.~~ **Resolved 2026-06-10** —
  removed the study-metadata trio (Animal role / `is_control`, `disease_model`,
  `disease_state`) from the **Builder** entirely. A recipe describes a stable
  naming convention; `is_control` is per-animal study design, so a recipe-level
  value is wrong for any mixed cohort. Clean split now: **Builder = how to read
  the files; Runner = this batch's study metadata.** Per-run capture stays in the
  Runner (homogeneous-per-run assumption noted in its panel; scope each group as
  a separate run for a mixed cohort). Superseded by the derive-from-label rule:

- [ ] **Per-acquisition condition derivation — "derive `is_control` (and disease
  fields) from a metadata label" (next-revision feature).** The real fix for a
  **mixed cohort in one ingest**: a filter-like rule that sets condition fields
  *per acquisition* from a discovered metadata label, instead of one value for the
  whole run.
  - *Why it's not just a GUI change:* today `condition.is_control` is resolved as
    a literal tri-state (`resolver.to_tristate(b.get("is_control"))`,
    [`tools/ingest/resolver.py`](../tools/ingest/resolver.py)). Derivation needs
    the resolver/enrichment writer ([`tools/ingest/enrichment.py`](../tools/ingest/enrichment.py))
    to evaluate a **value-map against `discovered.*` per acquisition**.
  - *Proposed config shape* (a new optional block, resolver-evaluated per case):
    ```yaml
    condition:
      is_control:
        from: ${discovered.group}      # the metadata label to read
        control_values: [CTRL, WT, sham]
        case_values:    [EAE, KO]      # anything else -> null (unknown), non-blocking
      disease_model:
        from: ${discovered.group}
        map: { EAE: "EAE", KO: "Cx43-KO" }   # value -> label; unmatched -> ""
    ```
    Keep the literal form working (back-compat); a `dict` value means "derive".
  - *Generalises* to `disease_state` / `treatment` / `study_arm` as value-maps,
    and the same idea could drive `anatomy.region` from an organ-letter label.
  - *GUI:* a "condition rule" builder mirroring the Filter UI (pick a metadata
    label, list which values are control vs case, map values to disease labels),
    with a live preview of how the example files would be classified.
  - *Note:* the animal-facility DB can't supply `is_control` (study design, not an
    animal property — `animals.exp_group` is unpopulated), so an operator-defined
    rule is the only path. Stays non-blocking: unmatched values -> `null` + WARN,
    backfilled later. New META open question when picked up.

## Person/role rename — residual cleanup (core done 2026-06-09)

The global researcher/operator/tech/user rename ([06_REGISTRIES §2.3a-bis](../mfb-rdm-docs/06_REGISTRIES.md)) landed in the code, schema, templates, configs, CLIs, GUI, and the authoritative docs. Residual, non-blocking:

- [ ] **Reclassify the people roster** in [`11_OPERATIONS`](../mfb-rdm-docs/11_OPERATIONS.md) (the table still lists individuals as "Operator") into **Tech** vs **Researcher** — needs the user's input on who is which.
- [ ] **Exhaustive prose sweep** of remaining "operator" mentions that mean the *role* (e.g. "Operator model" rows in `09_MODALITIES`, scattered "operators may…" lines) — the schema/authoritative docs are done; these are descriptive prose.
- [ ] **`source: "operator-entered"` enum** (in `condition:`/`anatomy:` provenance) — a *different* sense of "operator" (a human supplied the value at ingest). Decide whether to rename it (e.g. `manually-entered`) for consistency, or keep.
- [ ] **Project owner = researcher.** `auto_create_project.owner` still resolves to the filename/operator person for microscopy; consider making the auto-created project owner the `researcher`.
- [ ] **Reject the unreplaced MRI researcher placeholder on the data-office YAML path.** `mri-ingest --operator` is required (CLI path enforced), but a direct `ingest_raw.py --config` run that forgets to replace `researcher: "<REQUIRED ...>"` would still write the placeholder. Add a validation that errors when `researcher`/`operator` looks like the placeholder.
- [ ] **AxioScan researcher REQUIRED in the GUI** (parallel to MRI `--operator`). Today the GUI Researcher box is optional (blank → template placeholder for AxioScan). For AxioScan tissue the researcher isn't in the filename, so the GUI should require it before Ingest. (Handle during the GUI test pass.)
- [ ] **Normalize the NI curated `animal_id`.** `ni.subject.animal_id` is the raw protocol.txt value `0525_m13` (project_animal); the registry `sample_id` is `m13_0525` (animal_project). Optionally derive a consistent curated `animal_id` while keeping the raw value in `_raw_metadata`.

## Nuclear Imaging — live-machine import (Unai + Irene, 2026-06-10)

Archive-mode NI ingest is done and accepted (round 8 — 84 acqs from `.tgz`). The
**live-machine** path is the remaining gap, and is **post-launch** (archive mode
covers the exhibition data). Intel gathered 2026-06-10:

- [ ] **Access strategy for the live machine.** Saw it with Platform Manager
  **Unai** — the acquisition console is a **Mac** (the import tooling would run /
  be driven from a Mac, not Windows/WSL). It is **heavily in use for scans**, so
  hands-on access is hard; we need a low-impact way in (a scheduled window, a
  read-only pull off the machine, or a network/SMB path to its output folder)
  rather than occupying the console.
- [ ] **Characterize + handle the live folder structure.** The live output
  layout **differs from the archive `.tgz`** shape round 8 ingests. Capture the
  real on-machine structure (likely per-session DICOM/NIfTI exports, not a
  pre-made `.tgz`), then author **`molecubes_ni_live.yaml`** + one detector
  branch in `ni_ingest.py` (the live branch is already scaffolded, pending this
  template). Decide tgz-aware vs live-folder staging.
- [ ] **Fold in Irene's early-adopter notes.** Irene (NI operator, our first
  early-adopter user) gave Ryan notes on the live NI import workflow — *Ryan to
  paste the specifics here*; address them as part of the live-mode design.

Supersedes the live-mode items previously tracked in `tasks.md` §0 / §4.7
(`molecubes_ni_live.yaml`, the Unai naming-convention question). Archive-vs-live
design context: `equipment/nuclear-imaging/internal_ni_data_handling_workflow_notes.md`.

## Independent / second-stage tooling (moved from tasks.md 2026-06-10)

Tooling that improves the system but is **not** required for the operator
hand-off or the true-production restart. Detailed descriptions remain at their
original `tasks.md` locations (§3.1 / §3.2) as history; this is the active home.

- [ ] **`create_publication`** — formal publication-folder creation tool
  (requirements defined; not implemented). `tasks.md` §3.2.
- [ ] **`log_activity`** — provenance helper (requirements defined; not
  implemented). `tasks.md` §3.2.
- [ ] **Excel → study-metadata importer** (researcher-facing) — reads a
  per-project `study.xlsx` (study + biosamples + optional per-acq sheets),
  validates against a schema, writes `/projects/<proj>/metadata/*.json`. Unblocks
  researchers contributing REMBI study/biosample context. Schema needs design.
  `tasks.md` §3.2.
- [ ] **Project-level NIfTI generation tool** — `dcm2niix` / `bruker2nifti` per
  acquisition into `/projects/<proj>/derived_nifti/` (derivatives live in
  projects, not `/raw/`, per [13_GJESUS3_ROLE](../mfb-rdm-docs/13_GJESUS3_ROLE.md)).
  `tasks.md` §3.2.
- [ ] **DICOM full-mode metadata extraction for collaborator XMRI** — curated
  `discovered.dicom_*` + structured `dicom:` sidecar block + full `pydicom` dump,
  mirroring the `.czi` pattern. Prototype against the 75 existing XMRI acqs.
  `tasks.md` §3.1 / §3.2.
- [ ] **`--lightweight` ingest mode + `backfill_metadata` utility** — sparse
  registry entry (`extended_metadata_present=N`, no sidecar) for a fast first
  pass; `backfill_metadata` later upgrades a lightweight ingest to full. `tasks.md`
  §3.1.
- [ ] **NIfTI handling at ingest** (only if the NI/MRI platforms actually emit
  NIfTI we want at `/raw/`) — single file, no archive, limited header metadata.
  `tasks.md` §3.1 / §4.8.

## Misc

- [ ] **Symmetric override flags:** MRI `--pi` (override the parsed `pi_initials`)
  and NI `--user` (override the parsed user), once the person-home above exists.

## Metadata vocabularies & search (correction pass 2026-06-11)

- [ ] **Assisted controlled-vocab entry (suggest-list / autocomplete at point of
  capture).** S3 (2026-06-11) decided free-text enrichment fields stay free entry
  *for now* — forcing a controlled vocabulary without help kills adoption. The
  suggested standards are documented ([08_METADATA §4.8](../mfb-rdm-docs/08_METADATA.md)).
  The improvement: offer the vocabulary **at the point of capture** — autocomplete /
  suggest-list in the CLI prompts (`tools/operator/metadata_prompt.py`) and the
  microscopy GUI Study-metadata panel — so a future *soft* enforcement doesn't add
  friction. Pair any later enforcement with this assistance, never enforce bare.
  Per-field targets: species → NCBI Taxonomy, strain → IMSR/MGI/RGD, disease →
  MONDO, cell_line → Cellosaurus, anatomy → UBERON (already in use).
- [ ] **Metadata-only search DB (intermediate / stepping-stone to OMERO/XNAT).** A
  small read-only index (e.g. SQLite + Datasette, or similar) over the flat
  registries + the nested JSON sidecars, pointing at the images on the NAS. Two
  wins: (a) the **searchable face** on the NAS *now*, before any platform
  migration (the cheap "get value out" win — ties to the value-loop finding); and
  (b) it accommodates the **nested** sidecar JSON better than the flat key-value
  import XNAT/OMERO expect. Evaluate as an intermediate; **XNAT (DICOM) and OMERO
  (microscopy) remain the lead destinations** ([13_GJESUS3_ROLE](../mfb-rdm-docs/13_GJESUS3_ROLE.md)).
  Prep is already in place: keep the flat registry clean and keep DICOM UIDs
  captured (done) — that's what makes the eventual platform import frictionless.

## True-production restart — subsystem review (correction pass 2026-06-11)

- [ ] **Review which pilot subsystems carry forward vs. are replaced by
  platform-native equivalents.** At the post-exhibition true-production restart,
  decide per subsystem whether it stays or is superseded by an XNAT/OMERO-native
  capability (e.g. XNAT prearchive + custom-variable tooling vs. the local
  enrichment/deferred-recovery machinery; the metadata-DB above vs. the platforms'
  own search). Nothing is removed now — the enrichment + deferred-recovery
  apparatus was built for genuinely different source systems, works, and gates the
  imminent historical-data ingest (the earlier "trim the recovery apparatus"
  suggestion is withdrawn; the queue is the intended design). Decide at the
  restart, not before.

---

## MRI anatomy (`is_whole_body` / region) — back-fill + auto-derive (2026-06-13)

Context: the MRI jrc bulk historical ingest (`tools/configs/mri_jrc_animalfirst.yaml`
/ `mri_jrc_projfirst.yaml`) sets `anatomy.is_whole_body: null` (copied from the
template). But `is_whole_body` is a **highly-recommended, per-acquisition** field
(08_METADATA §4.6), and MRI is region-specific (cardiac / brain / abdominal). The
config sets `anatomy` **once per batch**, so a single value can't be right across the
~10,300 acqs / 21 mixed-anatomy projects → all would land `is_whole_body: null`
(non-blocking WARN). It is **not** currently auto-derived (verified in
`enrichment.py::_build_anatomy` — operator-entered only).

- [ ] **Back-fill the anatomy block** for the MRI ingest. Safe to ingest-now /
  enrich-later: each acq records `original_name = <study_folder>/<exam>` (registry +
  sidecar) → maps back to staging; **and** the deriving metadata (ParaVision
  `ProtocolName`/sequence + `PVM_Fov`) is already captured in the `mri:` sidecar, so
  the back-fill can read sidecars on the NAS (no staging needed). Use the controlled
  `/raw/` sidecar-update path (same pattern as `tools/recover_subject_metadata.py`).
- [ ] **Cleanest long-term fix — auto-derive at ingest.** Wire ProtocolName/sequence
  + FOV → `is_whole_body` + UBERON `region` in the enrichment/resolver path so anatomy
  fills per-acquisition automatically (the unimplemented "auto-hint" 08_METADATA §4.6
  already gestures at). Good candidate to fold into the designer's MRI work (alongside
  the DICOM-conversion / dicomifier piece).

---

## Facility-DB null project alias → `-None` subject ids (2026-06-13)

Found during the MRI ingest: `animal_db.lookup` returns `facility_animal_id =
"<animal>-AE-biomaGUNE-None"` for **projects whose facility-DB record has a null
project alias** (animals resolve fine — `status=found`, species/sex correct; only
the project's alias field is null). A full audit of all 21 MRI project codes found
**4 affected: 0219 / 0618 / 0619 / 1521** (the other 17 resolve correctly).
Examples (project, sample animal → DB return): `1521,m4 → 4-AE-biomaGUNE-None`;
`0619,m207 → 207-…-None`; `0618,m156 → 156-…-None`; `0219,m37 → 37-…-None`.

452 ingested MRI acqs (1521:72, 0619:336, 0618:44) were affected and **already
back-filled** (recomposed from `discovered.project_code`, which is correct).
**`0219` has 0 ingested acqs** (all its exams were no-DICOM/flagged) — so it will
surface during the **no-DICOM regeneration pass** unless fixed first. Ryan is
emailing the animal facility (2026-06-13) to populate the alias for those 4 project
records. The gap **recurs for any future ingest** touching null-alias projects.

- [ ] **Harden the ingest:** when the DB returns a project found but with a null
  alias, fall back to the operator/parse project (`discovered.project_code` via
  `project_hint`) when composing `facility_animal_id`, instead of emitting `-None`.
  One-line guard in `animal_db.compose_subject_id` callers / `enrichment.py`.
- [ ] **Fix the source:** ask the data office to populate the project alias for
  `1521` / `0619` / `0618` (and audit for other null-alias projects) in the facility DB.
- [ ] **Detector:** a quick `validate_registries` check for any `subject_ids`
  containing `-None` (catch future occurrences automatically).
