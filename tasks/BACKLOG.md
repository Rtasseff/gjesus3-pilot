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

## Finder — "Select-in-Finder → assemble a project" (2026-06-23)

Context: the registry **Finder** ([`tools/FINDER.md`](../tools/FINDER.md)) today is a
read-only locator — a generated, self-contained `registries/index.html` a researcher
double-clicks over SMB to search the registry and **Copy path** to their data. It never
touches the filesystem. This item is the next step up: turn it from a read-only *finder*
into a *build-a-working-set* front-end. (Extends the "select-rows" idea already noted in
`tools/FINDER.md` *Next* — that one only exports a CSV/methods manifest; this one actually
assembles a project on the NAS.)

- [ ] **Select acquisition rows → create the hard links + provenance into a chosen
  project.** Let a user **tick/select** acquisition rows in the Finder `index.html` view,
  pick a target project folder, and have the system **create the project hard links for the
  selected acqs AND write the corresponding provenance entries** — i.e. the *same* hard-link +
  provenance machinery that [`tools/ingest_raw.py`](../tools/ingest_raw.py) and the linker
  ([`tools/ingest/linker.py`](../tools/ingest/linker.py), `create_hardlink`) already perform
  in the ingest project-linking step when an ingest's `project_hint` resolves. This makes the
  Finder a "build a working set / assemble a project" tool, not just a locator.
  - *Why it's not a page-only change (the hard constraint):* the current Finder is a
    **static, sandboxed HTML page running over `file://`** — by browser security it **cannot
    touch the filesystem** (it can't even open a `file://` path directly, which is why it
    offers Copy-path instead of a link; see `tools/FINDER.md`). Actually creating hard links
    and writing provenance therefore **requires a helper / CLI / back-end beyond the browser
    page** — e.g. the page emits a selection manifest that a small local CLI consumes (reusing
    the `linker` + provenance code), or a thin local service the page calls. The browser page
    alone can never do this.
  - *Reuse, don't reinvent:* drive it through the existing linker + the ingest
    provenance-writing step rather than a parallel path, so project links and provenance stay
    identical to ingest-time links (same inode hard links, same provenance shape). Pairs
    naturally with the existing `find_acq.py` join engine (the Finder's data source) for
    resolving the selected rows to their `/raw/` acquisitions.

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

- [x] **Auto-derive at ingest — DONE 2026-06-14.** `tools/ingest/anatomy_derive.py`
  maps the **scan name** → UBERON `region` + `is_whole_body`, wired into
  `enrichment._build_anatomy` (`ingest_raw.py` Step 8.4); fills only when the operator
  left anatomy unset (operator wins). Reviewed with the MRI lead (J. Ruiz-Cabello):
  **high-confidence literal terms only, null if any doubt** — heart, named large
  vessels (MPA/aorta/carotid), brain, abdomen; setup scans skip; bare cine / unnamed
  velocity-map / FLASH-RARE / FOV → null. Pulse-sequence + FOV deliberately NOT used
  (not organ-determinant). No group-specific assumptions baked in.
- [x] **Back-fill tool — DONE 2026-06-14.** `tools/backfill_mri_anatomy.py` applies the
  SAME mapping to already-ingested MRI sidecars + the registry `anatomical_entity`
  column (dry-run default; atomic + verify; only fills unset acqs). **Run it `--apply`
  against the ingested MRI once a dry-run is eyeballed.**
- [ ] **(optional, low priority) Liberal historical guess** for Jesús-group scans whose
  names are too generic for the high-confidence rules (e.g. bare "Velocity map" / "Cine
  slices" that are cardiac-flow in context). If wanted, do it as a **one-off back-fill
  override list — NOT a permanent code rule** (keeps low-confidence, group-specific
  guesses out of the shared mapping that other groups will inherit).

---

## Microscopy anatomy from the sample-id organ suffix — back-fill + auto-derive (2026-06-14)

> **✅ DONE 2026-06-14.** Auto-derive + back-fill shipped to `main`, mirroring the MRI work.
> Operator-keyed map `tools/reference/microscopy_organ_map.yaml` (data, not code; AUA `Lu/Li/K`,
> MBC `H/B/L/HL` — `L`=lung confirmed with MBC, AUA `T`=tumor intentionally null). Shared by
> `anatomy_derive.derive_microscopy_anatomy` (wired into `enrichment._build_anatomy`, tissue path,
> operator-set wins) + `tools/backfill_microscopy_anatomy.py`. Operator runbook:
> [`tools/ANATOMY_BACKFILL.md`](../tools/ANATOMY_BACKFILL.md). Dry-run on the live ZWSI set fills
> ~88/146 (heart 57, lung 31); AUA `T` (tumor) + bare-numeric stay null by design. Remaining
> open item: confirm AUA's `mPCLS`→lung + whether `T` has a consistent host organ (edit the YAML
> if so). Original analysis kept below for the record.

**Priority: MEDIUM (non-blocking, but the info is present per-file so it's recoverable and
worth doing).** Surfaced during the AxioScan 7 MFB production ingest.

**The issue.** AxioScan `.czi` filenames encode the organ in the sample-id suffix
(`ID103T`, `ID12Lu`, `ID145H`, `ID249Li`, …), so anatomy is known **per acquisition** — but
the ingest **throws it away**: `tools/ingest/enrichment.py` line 150 does
`code, _organ = subject_id.parse_animal_short_code(...)` and never uses `_organ`, and
`_build_anatomy` only reads the operator-entered config `anatomy:` block. So every AxioScan
acq lands `anatomy.region = null` (non-blocking WARN) even though the organ is right there in
the name. (Contrast the MRI anatomy item above — for MRI the organ genuinely isn't in the data;
for microscopy it is.)

**The suffix vocabulary is OPERATOR-SPECIFIC and partly ambiguous** (measured across the 565 MFB files):
- **AUA** — unambiguous/verbose: `Lu`=lung (105), `Li`=liver (12), `K`=kidney (12), `T`=tumor (104).
- **MBC** — single-letter: `H`=heart (102), `B`=brain (17), `HL`=heart+lung (53), `L`=?? (111).
  **`L` is used only by MBC** (AUA writes `Lu`/`Li`), so its meaning (liver vs lung) must be
  confirmed with **MBC**, not AUA.
- ~49 bare-numeric ids carry no organ at all.

**What needs to be done.**
1. **Define an operator→organ→UBERON map.** Confirm the ambiguous codes with the operators
   (AUA's are clear; ask MBC about `L`/`H`/`B`/`HL`). Decide handling for combos (`HL` →
   `anatomy.additional_regions`), `T` (tumor — anatomical site varies; likely leave the host-organ
   region or mark unknown), and bare/none (leave null). UBERON starter ids in 08_METADATA §4.6.2
   (heart `UBERON:0000948`, lung `UBERON:0002048`, brain `UBERON:0000955`; add liver/kidney).
2. **Back-fill the already-ingested AxioScan acqs.** Read `sample_short` from the registry/sidecar,
   map organ→UBERON, write `anatomy.region` + registry `anatomical_entity` via the controlled
   `/raw/` sidecar-update path (same pattern as `tools/recover_subject_metadata.py`). Idempotent,
   non-blocking.
3. **Forward fix — assessment in line with future ingests.** Wire `enrichment.py` to consume the
   currently-discarded `_organ` → `anatomy.region` using the **same** map, so future microscopy
   ingests auto-populate anatomy. One mapping shared by back-fill + live ingest.

**Suggestions.**
- Keep the operator→organ→UBERON map as a small **reference YAML** (cf.
  `tools/reference/pi_group_lookup.yaml`) — data, not code — so researchers can extend/correct it.
- Likely **microscopy-wide**: Cell Observer / Confocal LSM 900 may share the suffix convention —
  design the map + wiring cross-microscopy, not AxioScan-only.
- Both steps (back-fill script + the `enrichment.py` wiring) are tooling changes → need Ryan's
  authorization before implementing.

## AxioScan MFB ingest — Phase 2 follow-ups (2026-06-15)

The AxioScan MFB historical ingest landed in true production on 2026-06-15: **565 acqs**
(configs `tools/configs/axioscan7_mfb_20260614.yaml` + `axioscan7_mfb_mpcls_20260614.yaml`),
0 failures, 563 subjects live (2 `-None` from the `0619` null-alias project; 5 mPCLS carry
no subject by design). Three deferred items:

- [x] **`is_control: true` for the 4 `CTRL`-tagged slides — DONE 2026-06-15.** Set
  `condition.is_control: true` in the 4 `/raw/` sidecars (`ACQ-20260306-ZWSI-003/005/007/009`,
  `MFB_AUA_1022_ID{59,60,70,72}T_KI67_CTRL_10X`), `source=derived-from-filename-CTRL-tag`.
- [x] **Anatomy back-fill — DONE 2026-06-15** via the designer's
  `tools/backfill_microscopy_anatomy.py --apply` (412/565 filled: heart 155, lung 216, kidney 12,
  liver 12, brain 17; 153 left null = `T`-tumor + bare-numeric). Registry `anatomical_entity` +
  sidecars patched. (See "Microscopy anatomy from the sample-id organ suffix" above — auto-derive
  also live for future ingests.)
- [x] **Link-name collisions — DONE 2026-06-15** via `tools/relink_axioscan_collisions.py`
  (16 groups incl. one `10X`/`10x` case-variant; 38 date-stamped links `ZWSI_..._<YYYYMMDD>.czi`,
  date-less links removed → 565 distinct project links). Detail below was the original finding:
  **Link-name collisions — same slide re-scanned across date folders.** The AxioScan
  `link_filename` is `ZWSI_<original-basename>` and the filename carries NO scan date (the date
  is the parent folder), so the SAME slide scanned/exported on multiple days collides on one
  link name — only the first gets a distinct project hard link. Measured: 15 slide-filenames
  appear in 2–3 date folders each → 565 acqs but 544 distinct link names → **21 acqs without a
  distinct project link**. These are **genuine separate acquisitions** (different sizes + czi
  timestamps, e.g. `ID29H` = 490/405/123 MB on 2026-02-19/-12/-06), not byte-dups — data-safe
  (each has its own ACQ-ID/raw/checksum/registry row). Fix: add `acq_date` to the AxioScan
  `link_filename` (e.g. `ZWSI_${acq_date}_${original_name}`) and relink the 21 (same class as
  the MRI link-name-collision item). Also (data-quality): confirm with the operators that the
  multi-date re-scans are intentional vs accidental re-exports.

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

---

## Spectroscopy / non-image MRI (STEAM, PRESS, Wobble) — separate ingest path (2026-06-13)

**Priority: VERY LOW (deferred).** Not needed for the current imaging recovery —
revisit only if/when the spectroscopy data is actually wanted downstream.

Scope (from the historical MRI pull): ~360 spectroscopy (STEAM / PRESS) + ~5
Wobble (tuning) acquisitions are **not image data**, so DICOM image regeneration
does not apply. As of `fix/dicomifier-wsl-2026-06-13` the ingest **auto-detects
and skips** these (`paravision_regen.is_nonimage_exam` → WARN + empty `.data/`
placeholder + no crash), so they no longer block or derail an imaging batch —
they simply land as skipped placeholders.

- [ ] **(very low priority) Separate ingest path for MR spectroscopy.** Decide
  the primary/sidecar shape for spectroscopy (raw FID / processed spectra, not
  image DICOMs) and how/whether to store the STEAM/PRESS results + the Wobble
  tuning scans. The ~365 acquisitions are safely skipped until this is built;
  there is no rush.

## MRI project link-name collisions — same-animal/same-day multi-session (2026-06-14)

**Priority: LOW (data-safe; near-term MRI template fix).** Found
during the no-DICOM regen relink (`tools/relink_mri_regen.py`, 2026-06-14): the MRI
`link_filename` —
`MRI_${sample_id}_${acq_date}_${discovered.mri_exam_number}_${discovered.mri_recon_indices}`
— is **not unique** when the same animal is scanned in **multiple separate study
sessions on the same calendar day** (timepoint series `_t0h_`/`_t6h_`, repeat
sessions `_2_1_1`, or date-typo'd folder names e.g. `jrc240122` vs `jrc220124`).
Such acqs resolve to the same link name and collide.

Measured on the 3,297-acq imaging regen batch: **3,097 distinct names → 144
colliding names → ~200 acqs** left without a distinct project link (the relink
creates the first of each group and skips the rest — it does **not** merge). This
is **pre-existing** (the same template drove the earlier 6,405-acq DICOM-bearing
run, so the same collisions exist there) and **data-safe**: every colliding acq
keeps its own ACQ-ID, `/raw/` folder, sidecar, checksums, and registry row — only
the project `raw_linked/` convenience layer can't distinguish them.

- [ ] **Add a session/time discriminator to the MRI `link_filename`** (e.g. the
  source study `HHMMSS` from the folder name, unique per session, or the timepoint
  token) in the MRI template + configs. Caveat: changing the convention now would
  make new acqs inconsistent with the ~9,500 MRI acqs already linked under the
  current scheme (6,405 DICOM-bearing + 3,104 regen), so do it as a deliberate
  template change with a coordinated relink of the affected acqs, not an ad-hoc patch.
- [ ] (optional) Once the template is fixed, a targeted relink of the ~200
  colliding acqs under the new unique names.

## Legacy Zeiss microscopy (Cell Observer / Confocal LSM 900) — BEST-GUESS ingest (2026-06-15)

These two instruments had **no historical naming standard** (they were the tissue-histology
workhorses before the AxioScan 7). Source = the messy `K:\gjesus\Ainhize\{CELL OBSERVER,
CONFOCAL LSM 900}` trees (MFB group): Cell Observer **1,739 .czi / 205 GB**, Confocal **806 .czi
/ 10 GB**; thousands of `.tif`/`.jpg`/`.qpdata` are derivatives we skip (ingest `.czi` only).
Same model planned for the **future external-drive microscopy** (also no standard).

**Best-guess system (built + smoke-tested 2026-06-15, all LOW CONFIDENCE, `source: "auto-guess"`):**
- Reliable fields come from the `.czi` itself (timestamp, objective, channels, ZEN operator `czi_user`).
- **Project** = the source top-folder, slugged → one provisional project per folder (literal
  `project_hint` in a **per-folder config** — also keeps the K: copy to one folder at a time, since
  K: is in daily use; single-threaded, never the whole tree at once).
- **sample_type / anatomy / is_control** are GUESSED off-NAS afterward by
  `tools/backfill_microscopy_bestguess.py` (reads each acq's `original_name`, zero source-drive
  access) against `tools/reference/microscopy_bestguess_map.yaml`: cell-line name → cells (wins);
  organ word → tissue + UBERON region; else null (never defaulted to cells); ctrl/control/neg → is_control.
- Smoke test: `tools/configs/lsm900_mfb_bestguess_claudia_uptake_2026-06.yaml` (Confocal folder
  `Claudia Uptake CCMn-doxo`, 8 acqs) → all `cells`, 3 `is_control`, project `PROJ-0023`. ✅

- [ ] **Bulk ingest** — per-folder, throttled, K:-conservative (Confocal ~10 GB first, then Cell
  Observer ~205 GB in chunks). Generate the per-folder configs; run one folder at a time; then the
  best-guess pass over all. **Plan: load it, then gather researcher feedback before the external drives.**
- [ ] Minor: strip the `.czi` extension from the best-guess `sample_id`.
- [ ] Optional refinement: some folders embed a project code (`0721 HUGO`, `1022 RGD`) — could map
  those to the `ae-biomegune-NNNN` projects (shared with MRI/NI/AxioScan) instead of a folder slug.
- [ ] **Project re-organization via researcher feedback (the real fix — post-hoc).** Per-folder
  projects — and especially Cell Observer's per-PERSON projects (`Claudia`, `Laura`, …) — are a
  DELIBERATE STOPGAP, not the long-term shape (data-office does NOT want per-user/researcher project
  folders). Plan (Ryan, 2026-06-15): use this best-guess ingest as the concrete artifact to (a) get the
  MFB researchers to propose corrected project names + organization for their historical microscopy, then
  **re-project in post** (cheap — `original_name` preserves the full source path, so any acq can be
  re-homed without re-copying), and (b) get them to adopt better project definitions in their naming
  GOING FORWARD so it doesn't recur. Feeds the still-provisional project-naming convention (05_PROJECTS
  §9 / PROJ-05).
