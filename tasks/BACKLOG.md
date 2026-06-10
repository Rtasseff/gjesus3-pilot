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
- [ ] **Bundle `tkinter` in the PyInstaller freeze.** The new native "Browse…"
  folder picker (`/api/browse_folder`) uses `tkinter`; the frozen `.exe`
  (`microscopy_ingest.spec`) must include it (hiddenimports / collect) or Browse
  silently degrades to type-it-yourself. Verify when the freeze is next built.
- [ ] **Refresh `gui/README.md` + `TESTING.md` for the rebuilt Builder + token
  widget + the `operator` column** — held until the operator accepts the new GUI
  (avoid documenting a UI still in flux).
- [ ] **Builder `is_control` as a recipe default.** "Animal role" can be baked
  into a recipe (e.g. a controls-only folder), but it's usually per-run. Consider
  a clearer "default (set per run)" affordance vs a baked value, and confirm the
  runner's per-run panel always wins on overlap (it does today — runner overrides
  apply after recipe overrides).

## Person/role rename — residual cleanup (core done 2026-06-09)

The global researcher/operator/tech/user rename ([06_REGISTRIES §2.3a-bis](../mfb-rdm-docs/06_REGISTRIES.md)) landed in the code, schema, templates, configs, CLIs, GUI, and the authoritative docs. Residual, non-blocking:

- [ ] **Reclassify the people roster** in [`11_OPERATIONS`](../mfb-rdm-docs/11_OPERATIONS.md) (the table still lists individuals as "Operator") into **Tech** vs **Researcher** — needs the user's input on who is which.
- [ ] **Exhaustive prose sweep** of remaining "operator" mentions that mean the *role* (e.g. "Operator model" rows in `09_MODALITIES`, scattered "operators may…" lines) — the schema/authoritative docs are done; these are descriptive prose.
- [ ] **`source: "operator-entered"` enum** (in `condition:`/`anatomy:` provenance) — a *different* sense of "operator" (a human supplied the value at ingest). Decide whether to rename it (e.g. `manually-entered`) for consistency, or keep.
- [ ] **Project owner = researcher.** `auto_create_project.owner` still resolves to the filename/operator person for microscopy; consider making the auto-created project owner the `researcher`.
- [ ] **Reject the unreplaced MRI researcher placeholder on the data-office YAML path.** `mri-ingest --operator` is required (CLI path enforced), but a direct `ingest_raw.py --config` run that forgets to replace `researcher: "<REQUIRED ...>"` would still write the placeholder. Add a validation that errors when `researcher`/`operator` looks like the placeholder.
- [ ] **AxioScan researcher REQUIRED in the GUI** (parallel to MRI `--operator`). Today the GUI Researcher box is optional (blank → template placeholder for AxioScan). For AxioScan tissue the researcher isn't in the filename, so the GUI should require it before Ingest. (Handle during the GUI test pass.)
- [ ] **Normalize the NI curated `animal_id`.** `ni.subject.animal_id` is the raw protocol.txt value `0525_m13` (project_animal); the registry `sample_id` is `m13_0525` (animal_project). Optionally derive a consistent curated `animal_id` while keeping the raw value in `_raw_metadata`.

## Misc

- [ ] **Symmetric override flags:** MRI `--pi` (override the parsed `pi_initials`)
  and NI `--user` (override the parsed user), once the person-home above exists.
