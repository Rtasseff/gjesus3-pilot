# Backlog — later improvements

This file is for **improvements that can be finished later** — refinements,
nice-to-haves, and second-/third-stage features that are *not* required to get
the pilot into users' and operators' hands.

It is deliberately **separate from [`STATUS.md`](STATUS.md)**, which tracks the
**work to get this to users** (the active path to a usable, hand-off-ready
pilot). Rule of thumb:

- *"Users/operators can't start, or start safely, without this"* → **`STATUS.md`**.
- *"This makes it better / cleaner / more automated later"* → **here**.

When a backlog item becomes a blocker for delivery, promote it to `STATUS.md`.

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
- [ ] **Refresh `gui/README.md` + `TESTING.md` + `gjesus3_ingest.spec` comment**
  for the rebuilt Builder + token widget + the `operator` column + **recipes now
  saved as YAML to a configurable folder defaulting to `<NAS>/recipes`** (was JSON
  in the repo `tools/operator/recipes/`; that dir is now only a read-only seed
  source) — held until the operator accepts the new GUI (avoid documenting a UI
  still in flux). (The *pre-launch* recipe steps — NAS `recipes/` permission grant
  + migrating the existing repo recipes — are in [`STATUS.md`](STATUS.md), not here.)
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

## Dedup identity — content-anchored, cross-ecosystem key (2026-07-17)

**Priority: MEDIUM (modest).** Surfaced during the AxioScan 7 operator test pass
(2026-07-17). The current dedup is **correct for the normal workflow** and blocks
nothing — this is a robustness improvement, deferred by the data office.

**How dedup works today.** `tools/ingest/config.py::_build_dedupe_index` builds a
set of `(acq_date, original_name)` keys from the **live** `registry_raw.csv`, and
`expand_batch` skips any case whose key is already present (idempotency check at
`config.py:367` / `:605`). `original_name` is the acquisition's path **relative to
the batch staging dir** (`expand_batch` sets `case["original_name"] = rel_match`,
~`config.py:422-435`). The mechanism is shared by all ecosystems (microscopy / MRI / NI).

**The gap.** Because the key is `(date, staging-relative-path)`, the *same physical
scan* re-ingested under a **different staging scope** gets a different
`original_name` → a different key → it is **not** recognised as a duplicate and is
ingested again. Reproduce: ingest a subset from a sub-folder, then ingest a larger
set from the parent folder that includes those same scans — the overlap is *not*
skipped. (Re-ingesting the same scans from the *same* folder selection **is**
correctly deduped — this was the original misread; the folder-relative key is fine
for the everyday operator workflow, which is why this is deferred rather than fixed now.)

**The improvement.** Anchor dedup identity to something **stable per acquisition**
rather than to the staging layout — e.g. for microscopy the `.czi` embedded scan id
or a content checksum; for MRI/NI an instrument-native exam/acquisition id — so
identity survives folder reshuffling. Do it **cross-ecosystem** (one key model, not
per-instrument) and **document the key** in the spec so users and developers know
what "already ingested" means as new instruments are added.

- [ ] Design a stable, content/instrument-anchored dedup key (cross-ecosystem).
- [ ] Report skips clearly to the operator ("N skipped — already ingested"). The
  preview already computes `n_already_ingested` (`/api/discovered`); surface the
  count in the GUI ingest result too — the completion-popup work on
  `feat/gui-operator-polish` is the natural place to show it.
- [ ] Document the dedup-key contract in `06_REGISTRIES` (or `10_TOOLS`) so identity
  is explicit for future instruments.
- *Related but distinct:* the concurrency dedup-**snapshot** risk (see "Architecture
  & code review follow-through", §3.1 #1) is a different concern — a pre-lock
  snapshot under concurrent ingest. This item is about the *key's* content-stability,
  not locking.

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

Supersedes the live-mode items previously tracked in `STATUS.md` §0 / §4.7
(`molecubes_ni_live.yaml`, the Unai naming-convention question). Archive-vs-live
design context: `equipment/nuclear-imaging/internal_ni_data_handling_workflow_notes.md`.

## Independent / second-stage tooling (moved from tasks.md 2026-06-10)

Tooling that improves the system but is **not** required for the operator
hand-off or the true-production restart. Detailed descriptions remain at their
original `STATUS.md` locations (§3.1 / §3.2) as history; this is the active home.

- [ ] **`create_publication`** — formal publication-folder creation tool
  (requirements defined; not implemented). `STATUS.md` §3.2.
- [ ] **`log_activity`** — provenance helper (requirements defined; not
  implemented). `STATUS.md` §3.2.
- [ ] **Excel → study-metadata importer** (researcher-facing) — reads a
  per-project `study.xlsx` (study + biosamples + optional per-acq sheets),
  validates against a schema, writes `/projects/<proj>/metadata/*.json`. Unblocks
  researchers contributing REMBI study/biosample context. Schema needs design.
  `STATUS.md` §3.2.
- [ ] **Project-level NIfTI generation tool** — `dcm2niix` / `bruker2nifti` per
  acquisition into `/projects/<proj>/derived_nifti/` (derivatives live in
  projects, not `/raw/`, per [13_GJESUS3_ROLE](../mfb-rdm-docs/13_GJESUS3_ROLE.md)).
  `STATUS.md` §3.2.
- [ ] **DICOM full-mode metadata extraction for collaborator XMRI** — curated
  `discovered.dicom_*` + structured `dicom:` sidecar block + full `pydicom` dump,
  mirroring the `.czi` pattern. Prototype against the 75 existing XMRI acqs.
  `STATUS.md` §3.1 / §3.2.
- [ ] **`--lightweight` ingest mode + `backfill_metadata` utility** — sparse
  registry entry (`extended_metadata_present=N`, no sidecar) for a fast first
  pass; `backfill_metadata` later upgrades a lightweight ingest to full. `STATUS.md`
  §3.1.
- [ ] **NIfTI handling at ingest** (only if the NI/MRI platforms actually emit
  NIfTI we want at `/raw/`) — single file, no archive, limited header metadata.
  `STATUS.md` §3.1 / §4.8.

## Doc placement — where is the line for `equipment/`? (2026-07-16)

- [ ] **Write the `equipment/` boundary rule down, then audit against it.** The rule
  as stated by the data office 2026-07-16: **`equipment/` is for the platform's own
  reality — the equipment itself, and the processes the *platforms* follow. Things
  outside our control, that persist regardless of what we build.** Our RDM's own
  procedures do not belong there, however much they are *about* an instrument's data.
  The rule currently exists nowhere: [`CONTRIBUTING-docs.md`](../CONTRIBUTING-docs.md)
  is the doc-governance home (`CLAUDE.md` defers to it for
  "documentation-architecture … boundary rules") and only says `equipment/` is
  "per-instrument workflow notes + platform reality" — which is exactly the ambiguity
  that let the runbook land there. **Write the test, then apply it.**
  **Audit candidates** (the answer is not always "move" — several look like *one doc
  doing two jobs*, and may need splitting rather than relocating):
  - `mri-platform/mri_no_dicom_regeneration_runbook.md` — clearest case; already
    tracked separately below (→ `tasks/archive/`).
  - `mri-platform/mri_data_access_strategy.md` — "how **we** reach the platform" is
    our strategy; the platform's access constraints (read-only, SFTP-only) are theirs.
  - `nuclear-imaging/live_machine_data_layout_and_sync_rules.md` — the **layout** half
    is platform reality and belongs; the **sync rules** half is ours.
  - `mri-platform/internal_mri_data_handling_workflow_notes.md` — self-describes as
    "the full MRI workflow **+ gjesus3 integration**", i.e. explicitly both.
  - `historical_data_archives.md` — borderline: *where the platforms keep their data*
    is arguably their reality; *our plan to ingest it* is not.
  Deciding the rule first is what makes the rest mechanical. Note `equipment/INDEX.md`
  is the map and will need to follow whatever moves.

## Doc placement — the no-DICOM regen runbook is in the wrong layer (2026-07-16)

- [x] **DONE 2026-07-16** — the backfill work finished the same day; the runbook's
  durable content was integrated into `10_TOOLS.md` (§2.1 flag row + new §3.8) and
  `11_OPERATIONS.md` (new §5.5), its false idempotency claims were corrected in
  place (⚠️ CORRECTED markers), and it was moved to
  `tasks/archive/mri_no_dicom_regeneration_runbook.md`. All inbound links repointed
  at the new official homes; the append-only `CHANGELOG.md` (2026-06-12) reference
  was left stale by decision (the 2026-07-16 entry records the move). Original
  rationale kept below for the `equipment/` boundary audit above.
- ~~Move `equipment/mri-platform/mri_no_dicom_regeneration_runbook.md` →
  `tasks/archive/` once the no-DICOM regen work is finished.~~ **Do it when we're
  done, not before** — it is still the only written procedure today.
  **Why:** `equipment/` is for the *platform's* own reality — the hardware and the
  processes the platforms follow, which are outside our control and persist
  regardless of what we build. This runbook is the opposite: it documents *our*
  RDM tooling (`auto_regenerate_dicom`, `paravision_regen.py`, our WSL/conda env,
  our validate step). It only lives under `equipment/` by accident of being about
  the MRI platform's data. Once the drain tool supersedes its step-by-step it is a
  historical work trail, which is what `tasks/archive/` is for.
  **Carries with it (don't move it blind):**
  - **~10 inbound links** to fix across `equipment/INDEX.md`,
    `internal_mri_data_handling_workflow_notes.md` (×4), `mri_data_access_strategy.md`
    (×2), `mri_platform_description.md`, `tools/INGEST_CLI.md`, `tasks/STATUS.md`.
  - **`CHANGELOG.md` (2026-06-12) references it** — the CHANGELOG is append-only, so
    that link cannot be rewritten. Decide: accept the stale link (it points at the
    archived path's history) or leave a stub.
  - **`tools/INGEST_CLI.md` calls it "▶ Full operator procedure"** — archiving it
    removes the live procedure's home. The replacement (drain tool usage) belongs in
    `tools/` (tool docs) and/or `10_TOOLS.md` (spec), not in `equipment/` again.
  - It is ✅ DECIDED and **contains a false claim** (§2/§6: a re-run "fills the
    `.data/`" — it does not; see `STATUS.md` §2). Fix or excise that before it is
    frozen into `archive/`, since archived material is never edited afterwards.
  **Worth the same test while we're here:** `mri_data_access_strategy.md` ("how *we*
  reach the platform") and the sync-rules half of
  `nuclear-imaging/live_machine_data_layout_and_sync_rules.md` also look like our
  process rather than platform reality. The layout/hardware halves clearly belong.

## Repo / git hygiene (2026-07-16)

- [ ] **Delete the spent branches.** All verified `git branch --merged main` /
  `rev-list --count main..<b> == 0` on 2026-07-16 — stale labels pointing into main's
  history, nothing unique in any of them. Precedent: `fix/integrity-cluster-2026-07`
  deleted 2026-07-16 the same way (`git branch -d`, which refuses if not merged — use
  `-d`, never `-D`).
  - local: `docs-refactor` (`5625403`), `gjesus3-data-rebuild` (`1296c16`),
    `phase3-metadata-enrichment` (`a2e2ec6`), `feat/finder-mvp` (`86ff89b`)
  - remote: `origin/feat/finder-mvp`, `origin/feat/ni-live-sync` (both 0 not-in-main)
  - Note `feat/finder-mvp` reads "ahead 2" only because its *remote* is 2 behind the
    local; both are fully contained in main. Nothing is stranded by deleting either.
- [ ] **⚠️ DO NOT delete `origin/feat/ni-live-hardening` — it is real unmerged work.**
  **8 commits / ~1,631 insertions NOT in main** (per-recon incremental model,
  `ni-ingest --live` no-YAML operator sync, per-session corrections + tracer metadata,
  `pending_links.py` deferred hard links, `relink_pending.py`, 3 new test files). Its
  tip `f2ee114` (2026-07-03) is literally a **"RESUME-HERE checkpoint — on-box test
  deferred to wk of 2026-07-07"**, so it is parked mid-flight and now ~2 weeks stale.
  It needs a decision — land it or consciously park it — not cleanup. Relates to the
  NI live-sync go-live item in `STATUS.md` §2.
- [ ] **Decide what to do about `contacts.xlsx`.** Tracked, not ignored, and
  perpetually dirty in the working tree — it has shown up as modified in every session
  and is deliberately never staged (`CLAUDE.md`: don't stage the binaries). There is a
  commit on `feat/finder-mvp` literally titled *"chore: commit a stale manual edit to
  contacts.xlsx"*, so this recurs. Options: `.gitignore` it (+ `git rm --cached`),
  keep tracking and accept the noise, or move it out of the repo entirely. Right now
  it is permanent noise in every `git status`, which is how real changes get missed.

## Misc

- [ ] **Symmetric override flags:** MRI `--pi` (override the parsed `pi_initials`)
  and NI `--user` (override the parsed user), once the person-home above exists.
- [ ] **`dicom_utils.summarize_source` opens every file in the source tree
  (measured 2026-08-12).** `find_dicom_files` has no limit in the `file_count`
  path, and for extensionless DICOM it must open each file to check the `DICM`
  magic at byte 128 — so a collaborator case of ~21,000 instances costs ~21,000
  opens, plus a second `os.walk` doing `getsize` on each for the total. Measured
  **29–75 s per case** on local disk; the DTS24 batch of 75 cases is ~880,000
  file opens and dominates its ingest wall-clock entirely (the actual archive
  copy is one file per acquisition). Tolerable only because staging is local —
  the same walk over SMB is the exact "thousands of tiny files" cost that made
  the original collaborator round painful, and is why
  `extract_xmri_archives.py` now warns against a NAS `--dest`.
  The fix is already sketched in a TODO in that function: for
  `acquisition_layout: archive`, count entries in the produced archive's central
  directory instead of walking the source. That is both faster and *more*
  correct — `file_count` is meant to describe the acquisition as stored. Cheap
  win: `detect_modality` / `extract_study_date` already pass `limit=20`; only
  the `file_count` call is unbounded.

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

## Metadata model — what `user_provided_metadata` is standing in for (2026-08-12)

> Raised by Ryan at the moment the block was designed, and deliberately **not**
> solved then: DTS24 needed the collaborator tables captured, and over-fitting
> the schema to one dataset would have been worse than a recorded stand-in.
> The block that shipped ([08_METADATA §4.9](../mfb-rdm-docs/08_METADATA.md)) is
> flat and per-acquisition; both items below are cases where that is the wrong
> shape and we know it. **Priority: medium** — revisit before a second or third
> dataset makes the stand-in load-bearing.

- [ ] **META-10 — Study-level metadata and the ISA hierarchy (investigation /
  study / assay).** Study data describes *what is being done*, one level above
  an acquisition, so copying it into every acquisition's sidecar is duplication
  with no join. We have already leaned this way twice: the animal-facility
  `procedures` block ([§4.4.7](../mfb-rdm-docs/08_METADATA.md)) and the
  `session_id` registry column (already annotated "ISA study grouping" in
  `resolver.USER_CONTROLLABLE_COLUMNS`). DTS24's `source_project` block —
  the originating grant, identical on all 42/33 acquisitions of a cohort — is a
  third. Design question: does gjesus3 adopt an explicit ISA-style layer
  (investigation → study → assay), and if so does it live in
  `/projects/<proj>/metadata/` (the study-level location already specified in
  §1.1 but built on 0 of 52 projects) rather than in the per-acquisition
  sidecar? Ties to the deferred study-level metadata work and to the
  metadata-only search DB item above.
- [ ] **META-11 — A clinical/derived *measurement* is a new data type, not
  metadata.** DTS24's cardiac hemodynamics (28 columns of pressures, cardiac
  index, Fick) is currently attached to the MRI acquisition as
  `user_provided_metadata.hemodynamics`. That is expedient and wrong in
  principle: it is its **own measurement**, of its **own data type**, related to
  the MRI only because it came from the **same subject**. The model that
  captures it properly is subject-linked acquisitions of differing types — which
  is also what would let a non-imaging assay (bloods, histology scores, clinical
  scores) enter the system at all. Today `raw/` is organized by imaging
  ecosystem (MICROSCOPY / DICOM / EM) with no home for a tabular clinical
  measurement. Design question: a new ecosystem/data-type for non-image
  measurements, keyed by `subject_ids`, versus keeping such tables as
  acquisition metadata. **Do not add more measurement tables via `user_metadata:`
  before deciding** — that is how the stand-in becomes permanent.

## Human-subject data — policy beyond the ingest (2026-08-12)

- [ ] **META-12 — Human/clinical data policy.** DTS24 is the first human data in
  a system designed end to end for preclinical animal work. The ingest side is
  settled ([08_METADATA §4.10](../mfb-rdm-docs/08_METADATA.md)): the DICOM
  extractor is a privacy allow-list, no date of birth is propagated into the
  sidecars or `registry_subjects.csv`, and human cohorts use an operator
  `subject:` block with a pseudonymous id so the animal-facility DB is never
  consulted. **What is NOT settled:** (a) the archived source `.zip`/`.rar`
  files still contain full DICOM headers with DOB and patient name — should
  sources be de-identified on ingest, or is "identifiers stay in the immutable
  archive, never in the searchable layer" the standing rule? (b) access control
  for human data on the share — the current model is a single `GJesus` group
  with Read baseline ([permission model](../mfb-rdm-docs/02_INFRASTRUCTURE.md)),
  which does not distinguish human from animal data; (c) retention, and the
  legal basis / data-sharing agreement covering reuse of collaborator clinical
  data for DTS24; (d) whether `subject:`'s animal-facility field names
  (`facility_animal_id`, `strain`, `cohort_id`) should gain a human-appropriate
  alias. Also note the `subject:` block schema currently has no way to say
  "this subject is human" other than `species: Homo sapiens`.

## ✅ Finder — "Select-in-Finder → assemble a project" (2026-06-23) — **DONE 2026-08-12, differently**

> **Delivered by the Project Manager GUI** ([`10_TOOLS §5.3`](../mfb-rdm-docs/10_TOOLS.md)),
> not by the Finder page. This item named its own blocker exactly right — a static page over
> `file://` cannot touch the filesystem, so this "requires a helper / CLI / back-end beyond
> the browser page". The Project Manager **is** that back-end: it has a server, so it reads
> `registry_raw.csv` server-side, offers the same filters (through `find_acq`, the same join
> engine this item pointed at), takes a tick-list, and creates the links. Its design rule is
> the one written here — it drives the **existing** `linker.create_hardlink` + the ingest
> provenance step rather than a parallel path, so the links and provenance rows are identical
> to ingest-time ones (same inode, same shape). What differs from the sketch below: the
> selection happens in the tool's own served page rather than in the generated
> `index.html`, and no selection-manifest hand-off was needed. The original text is kept
> below for the reasoning.

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
  in the ingest project-linking step when an ingest's project resolves. This makes the
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

## Finder — provenance-driven project index (a possibly-better project-level index) (2026-06-23)

Context: we now publish a **registry-driven per-project `index.html`** (the global Finder,
filtered by `project_id`, refreshed when an ingest writes into the project — see [`tools/FINDER.md`](../tools/FINDER.md)).
This item explores a **different, possibly better** way to build the project-level index: drive
it from the **project's own provenance file** instead of the registry. Raised by the data office
2026-06-23 — **shape still open, discuss before building.**

> **Still open after 2026-08-12, and partly vindicated.** This item predicted precisely the
> problem the Project Manager had to solve — `project_id` *"stamped once at ingest"* while
> researchers *"later reorganize / re-home acqs"*. Making `project_id` a semicolon list
> ([`06_REGISTRIES §2.3b`](../mfb-rdm-docs/06_REGISTRIES.md)) fixes the **recording**: an
> acquisition can now honestly belong to two projects. This item is about the **view**, and
> nothing above is superseded. The Project Manager keeps provenance complete and accurate on
> every import — a row per link, a row per copied file — precisely so it stays the credible
> source of truth if this lands.

- [ ] **Build the project `index.html` from the project's provenance file, not from `project_id`.**
  At ingest, every raw acquisition hard-linked into a project is recorded in that project's
  **provenance** (see [`07_PROVENANCE`](../mfb-rdm-docs/07_PROVENANCE.md) + the ingest
  provenance-writing step). A provenance-driven index would list **the files actually present in
  the project's linked `raw/` folder** and use the provenance to link each hard-linked file back
  to its **source acquisition** → its `metadata.json` sidecar and its registry row (so the
  researcher still gets full acquisition + registry info, reached *through* the provenance rather
  than via a `project_id` match).
  - *Why it may beat the registry-driven version:*
    - **Reflects what's actually in the project, now.** `project_id` is stamped once at ingest;
      provenance reflects the project's real current contents. Not every ingest even puts raw
      files into a project, and the **initial project is often vague** — researchers later
      **reorganize / re-home** acqs into projects meaningful to them. A provenance-driven index
      tracks that reality; a `project_id` filter goes stale.
    - **Shows non-acquisition files too.** Project folders accumulate files that aren't raw
      acquisitions (analyses, notes, derived outputs) with **no registry row** — the
      registry-driven index can't show them, but a provenance/folder-driven index can list them
      with whatever partial info exists (name, size, any provenance recorded).
    - **Could strengthen provenance itself.** Building the view from provenance surfaces gaps (a
      linked file with no provenance entry, or an entry whose source acq is gone), so it doubles
      as a **provenance completeness / tracking** check.
  - *Open questions (for the later discussion):* exact shape (does it **replace** or **complement**
    the registry-driven per-project index?); what provenance records today vs what this needs (may
    require enriching the provenance schema); how to render rows with full registry info vs
    partial-only; performance (per-project provenance reads vs one registry pass); and whether the
    "select-in-Finder → assemble a project" item above should *write* into this same
    provenance-driven model.

## Server-era identity — logged-in user drives ownership + edit rights (2026-08-11)

Context: a **dedicated RDM server for gjesus3 is expected in ~2 months (≈ Oct 2026)**. All
the tool code goes live there and the current per-tool `.exe`s are **redesigned as one web
app** — the ingest front-ends and the Project Manager GUI stop being separate downloads.
Until then, tools are built to be *as similar as possible* so combining them later is
cheap (see [`10_TOOLS §5.3`](../mfb-rdm-docs/10_TOOLS.md)).

The single capability the exe era cannot have: **an exe on a shared workstation does not
know who is sitting at it.** A server does.

- [ ] **Use the logged-in user for project ownership and edit rights.** Once there is a
  server with real sessions:
  - **`owner` on create becomes automatic** — stamped from the logged-in user instead of
    typed by hand. (Today it is free text, and the live registry shows the cost: `jguser`
    and `Jguser` are the same person recorded two ways, alongside `NMR-platform`,
    `NI-platform`, `MBC`, `AUA`, `zeiss` — a mix of people, platforms and accounts in one
    column.) Keep `owner` an ordinary editable field until then, so this needs no
    migration — just a better default.
  - **Who may edit which project** becomes checkable: owner (and the Data Office) can edit;
    others read. Today the Project Manager GUI can only offer *"anyone with access may
    edit anything"*, which is acceptable for a small trusted group and will not scale.
  - **Provenance `creator` stops being a prompt.** Every import currently has to *ask* who
    is doing it (handoff §4.3); with a session it is known. This is the field most likely
    to be filled in carelessly, so it is the one that benefits most.
  - Consider whether the same identity should feed the registry `researcher` / `operator`
    columns at ingest, rather than the config's `operator:` key.
  - *Depends on:* the server actually landing, and a decision on the auth source (AD /
    institute SSO / local accounts). Related: the internal-web-serving capability already
    proven on this workstation, and `02_INFRASTRUCTURE` for where the server sits.

## Project Manager GUI — deferred scope (2026-08-11)

Context: the **Project Manager GUI** (built 2026-08-12; see
[`10_TOOLS §5.3`](../mfb-rdm-docs/10_TOOLS.md)) gives researchers a front-end to edit
project fields, create projects, and import data into them. Two capabilities were
**deliberately left out** of that tool and parked here.

- [ ] **🔽 LOW — Rename a project.** The GUI can edit `description` / `owner` / `status` /
  `notes`, but **not `name`**, because since 2026-08-02 the project's `name` **is its
  folder name, verbatim** (see [`05_PROJECTS §2a`](../mfb-rdm-docs/05_PROJECTS.md) —
  ✅ DECIDED). A rename is therefore not a cell edit; it is a migration touching at least:
  the folder on the NAS; `registry_projects.csv` (`name` **and** `folder_location`);
  every `registry_raw.csv` row whose `project_id` points at it (the id is stable, so this
  may be zero work — confirm); the project's `provenance.csv` (`output_path` values are
  project-relative, so probably safe — confirm); the per-project `index.html`; and any
  `.lnk` / documentation referencing the old path. Hard links themselves survive a parent
  rename (they are directory entries, not paths), so `raw_linked/` should be fine — but
  that must be **verified on the live SMB share**, not assumed. There is a precedent to
  copy: `tools/migrate_project_naming.py` renamed 48 folders during the 2026-08-02 cut.
  *Why low:* renames are rare, the Data Office can do one by hand with that script, and a
  half-correct self-service rename is far worse than no rename.

- [ ] **🔸 MEDIUM — Define what `status = closed` actually does.** The GUI exposes a status
  dropdown (`active` / `paused` / `closed` per the
  [`05_PROJECTS §4`](../mfb-rdm-docs/05_PROJECTS.md) lifecycle), but today setting
  `closed` **only changes a string in the registry** — nothing else happens. That is a gap
  with real consequences, because §4.x and §5 already say deletion is **blocked** until
  close-out preserves study-level metadata into `/raw/`, and §5 is ✅ DECIDED. Open
  questions, all needing a Data Office answer before anything is built:
  - Does closing **freeze** the project (read-only ACLs, no further imports), or is it
    just a label? A student flipping a dropdown should probably not be able to freeze a
    shared folder.
  - What does closing do about the **close-out preservation step** (§4.x) — block the
    status change until it has run, warn, or queue the project for the Data Mgmt Lead?
    The close-out tool itself does not exist yet.
  - Is `closed` reversible in the GUI, or one-way once close-out has run?
  - Should closing set a `closed_date` / `outcome`? `_project.yaml` already has both
    fields (`closed_date`, `outcome`, `promoted_to`); `registry_projects.csv` has
    **neither** — so recording them means either a projects-registry schema change or
    accepting that the YAML is the only home.
  - **Live precedent to respect:** 8 projects are already `closed`, and 3 of them
    (`PROJ-0003`, `PROJ-0008`, `PROJ-0009`) have had their folders **deleted** — closed
    with no folder is a normal end state, and any tooling must not treat it as corruption.
  *Why medium:* the dropdown ships before this is answered, so the gap is live the moment
  the tool is in researchers' hands.

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
  the project name) when composing `facility_animal_id`, instead of emitting `-None`.
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
  there is no rush. **Input set = the `not-applicable` rows of
  `registries/pending_dicom_regen.csv`** (365: STEAM 286 / PRESS 74 / WOBBLE 5;
  the `nonimage_marker` column says which is which).
  **2026-07-16 backfill finding:** the marker set (STEAM/PRESS/WOBBLE) was
  re-checked against every staged pending exam during the backfill and needs
  **no widening** — all remaining DICOM-less exams are ordinary image sequences
  (FLASH/FcFLASH/FISP/MSME/RARE/UTE3D/DTI/FLOWMAP); the `specpar`/
  `AdjStatePerScan` files seen in some exam folders coexist with plain image
  exams and are NOT non-image signals. Also note the 14 `fid`-only rows now
  marked `no-source` — if a ParaVision-reconstruction path is ever built, those
  are its candidate input (they have raw k-space but no `2dseq`).

## MRI project link-name collisions — same-animal/same-day multi-session (2026-06-14)

**Priority: LOW (data-safe; near-term MRI template fix).** Found
during the no-DICOM regen relink (`tools/relink_mri_regen.py`, 2026-06-14): the MRI
`link_filename` —
`MRI_${sample_id}_${acq_date}_${discovered.mri_exam_number}_${discovered.mri_recon_indices}`
— is **not unique** when the same animal is scanned in **multiple separate study
sessions on the same calendar day** (timepoint series `_t0h_`/`_t6h_`, repeat
sessions `_2_1_1`, or date-typo'd folder names e.g. `jrc240122` vs `jrc220124`).
Such acqs resolve to the same link name and collide.

**2026-07-16 addition (from the backfill relink):** two concrete pairs among the
backfilled exams' studies remain link-less because of exactly this collision —
`MRI_m23_0219_20220124_1_1` (ACQ-20220124-MRI-001 vs -006) and
`MRI_m23_0219_20220124_3_1` (ACQ-20220124-MRI-003 vs -008); in each pair the
second acquisition has no project link of its own (the relink correctly skipped
rather than merged — frame counts matched, so no data was mixed). Fix these two
when the link-name template fix lands. Same run also found and repaired **510
pre-existing empty link shells** the 2026-06-14 relink had left behind.

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
  `project_name` in a **per-folder config** — also keeps the K: copy to one folder at a time, since
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
  those to the `AE-biomaGUNE-NNNN` projects (shared with MRI/NI/AxioScan) instead of a folder slug.
- [ ] **Project re-organization via researcher feedback (the real fix — post-hoc).** Per-folder
  projects — and especially Cell Observer's per-PERSON projects (`Claudia`, `Laura`, …) — are a
  DELIBERATE STOPGAP, not the long-term shape (data-office does NOT want per-user/researcher project
  folders). Plan (Ryan, 2026-06-15): use this best-guess ingest as the concrete artifact to (a) get the
  MFB researchers to propose corrected project names + organization for their historical microscopy, then
  **re-project in post** (cheap — `original_name` preserves the full source path, so any acq can be
  re-homed without re-copying), and (b) get them to adopt better project definitions in their naming
  GOING FORWARD so it doesn't recur. Feeds the still-provisional project-naming convention (05_PROJECTS
  §9 / PROJ-05).

## NI (Molecubes) — tracer compound NOT in the data; richer `reconparams.txt` source (2026-06-19)

Investigated whether the **radiotracer** is recoverable from the NI data (manager thought it lived in a
reconstruction-parameter file). Pulled + extracted a source PET `.tgz` from `\\cicmgsp02\gnuclear2$` and
searched every parameter file (`recon_0/reconparams.txt` + `.xml`, `acqparams.xml`, `protocol.txt` + `.xml`,
`recon.ini`, `reconstruction.log`) — plus the DICOM header.

- **Finding: the tracer COMPOUND is not recorded by the Molecubes platform anywhere.** The only
  radio-chemistry field is the **isotope** (`Acquisition/isotope = F-18`, `Reconstruction/isotope = F-18`;
  the DICOM `RadiopharmaceuticalCodeSequence` likewise codes only `^18^Fluorine`). Nothing names the
  compound (FDG vs NaF vs FET …). The platform stores what it needs for decay correction (isotope, 511 keV,
  half-life, activity), not the chemistry.
- **We already capture the isotope** (`ni_isotope` from `protocol.txt`). So nothing more is extractable for
  the tracer — **the compound is study-level knowledge and must come from the researchers / study records**,
  not from the instrument data. (No tooling action; record-keeping decision.)
- [ ] **(optional enrichment) `reconparams.txt` is a richer NI source than `protocol.txt`.** It carries
  fields we don't currently extract — `principalinvestigator`, `bedtype` (mouse), scan `duration`, `FOV`,
  recon `iterations`/voxel size, energy window, the **attenuation-correction CT reference** (links PET↔CT),
  scanner serial. BUT the NI slim copy retains only the reconstructed DICOM, so `reconparams.txt` is **not
  on the NAS** — capturing these would mean extending the NI extractor (`ni_metadata.py`) to read
  `recon_<idx>/reconparams.txt` at ingest + a back-fill from the intact source `.tgz` on gnuclear2$. Defer
  unless the team wants the PET↔CT link or per-scan acquisition params surfaced.

## Server-side raw ingest + a downstream Windows tool (architecture, 2026-06-24)

**The idea (user, 2026-06-24).** Instead of pushing the full ingest (with all its
credentials, network access, and tools) onto every operator's Windows machine,
run the **raw ingest centrally on a Linux server people log into**, and give
researchers a **lightweight Windows tool only for the downstream work** (find
their uploads, assemble them into project folders, post-process). The split:

- **Server (Linux, the "ingest host")** — has *everything* in one place: SSH
  access to the MRI console (`kenia`), the animal-facility DB creds (`~/.my.cnf`),
  **Dicomifier installed** (so no-DICOM ParaVision exams regenerate at ingest —
  no Windows gap), the NAS mounted with hard-link semantics, and the repo
  checkout with all paths/tools. Operators/researchers log in (SSH/web) and run
  the raw ingest there. One trusted, fully-provisioned environment.
- **Windows tool (downstream only)** — a small app researchers run on their own
  machines to **search the registry for their acquisitions, pull/organize them
  into project folders, and do post-processing** — no credentials, no scanner
  access, no regen. (The Researcher Finder is already a step in this direction.)

**Why it's compelling.** It dissolves three current operator-machine pain points
at once: (1) the **Dicomifier-can't-run-on-Windows** gap — the server has it, so
the `pending_dicom_regen.csv` deferral (added 2026-06-24) becomes unnecessary for
server-ingested data; (2) **per-machine credential sprawl** — the MRI `.ssh` cred
and optional `.my.cnf` live once on the server, not on N workstations; (3)
**environment drift** — one Linux box vs. many Windows boxes with different states.

**Why it's NOT the pilot path (deferred, not chosen now).** The current
operator-self-service GUI (the frozen `gjesus3_ingest.exe`) is the *adoption*
play — a one-click tool a non-technical researcher runs without logging into a
server or touching a terminal. The server model trades that low-friction
self-service for centralization. Revisit when: the no-DICOM volume makes the
deferred-regen sweep painful; credential management across machines gets heavy;
or we want a single audited ingest chokepoint. The hard-link requirement means
the server still ingests onto the Windows/QNAP NAS over a mount that preserves
SMB hard-link semantics (the linker is the platform-sensitive piece — see the
2026-06-24 note that hard links are a Windows/QNAP-verified path, not a generic
Linux one; confirm `os.link` behaviour on the server's NAS mount first).

**Relationship to other backlog items.** Subsumes part of "Independent /
second-stage tooling" and complements the Finder's "assemble a project" item —
the downstream Windows tool IS that post-ingest project-assembly surface.

## No-DICOM regeneration on Windows — research finding (2026-06-24)

**Q (user): is there literally no way to run Dicomifier or similar on Windows?**
Researched 2026-06-24:

- **Dicomifier is not PACKAGED for Windows — but that's a packaging gap, not a
  proven impossibility (CORRECTED 2026-06-25).** The conda-forge dicomifier recipe
  carries `skip: true  # [win or osx]` (Linux-only) and dicomifier is not on PyPI,
  so there is no off-the-shelf install. My first pass wrongly blamed its C++ DICOM
  dependency **`odil`** — in fact **`odil` is fully Windows-supported**: conda-forge
  `odil` builds win-64 (py3.10–3.14, no skip) and odil documents source builds on
  Windows (CMake/Visual Studio + Boost/ICU/JsonCpp/DCMTK). So the dicomifier Windows
  skip is a maintainer CI/packaging choice (reason not documented), NOT a hard block
  from odil. Ways to run it on Windows TODAY: **WSL** (the historical approach) or
  **Docker** (the Linux build in a container) — neither bundleable into the exe nor
  fit for a novice operator's machine. A native-Windows dicomifier (enable the conda
  recipe for win, or build from source against the Windows `odil`) is **plausibly
  feasible but unverified** — someone has to attempt the build to learn whether a
  second, non-odil blocker exists.
- **Pure-Python Bruker readers DO run on Windows** — `brkraw`, `bruker2nifti`,
  `brukerapi-python` — but they all output **NIfTI, not DICOM**. They solve the
  *reading* of `2dseq`+JCAMP-DX, not the DICOM *writing*.
- **Therefore the only Windows-native path to DICOMs would be to BUILD one:** read
  with `brukerapi`/`brkraw` (pure Python) + write with `pydicom` (pure Python) — a
  bundleable, exe-friendly `2dseq → DICOM` generator. Feasible, but a real project:
  the hard part is the correct DICOM tag/geometry mapping that `odil`/Dicomifier
  already encode (the team earlier estimated ~2-4 weeks for a from-scratch DICOM
  generator, which is why Dicomifier was adopted instead).

**Conclusion.** There is **no off-the-shelf / one-click way to regenerate DICOMs
on a Windows operator box that fits inside the frozen exe** — but "impossible" is
too strong (odil is Windows-capable; a native build is plausibly feasible, just
unverified and not worth it now). The real options: (a) **Linux** (WSL, Docker,
or the
server-side ingest host above) runs Dicomifier — current approach, and what the
`pending_dicom_regen.csv` worklist defers to; (b) **build a pure-Python
`2dseq`→`pydicom` writer** if Windows-native regen ever becomes worth ~weeks of
work; (c) accept **NIfTI** (via `brkraw` on Windows) for no-DICOM exams — but that
changes the stored format away from the DICOM standard the MRI `.data/` uses.
This finding reinforces both the worklist (defer to Linux) and the server-side
ingest architecture (the server has Dicomifier). Sources: conda-forge
dicomifier-feedstock `recipe/meta.yaml`; brkraw.github.io; bruker2nifti docs.

## Enrichment `condition:` block — verify it writes for tissue/cells (doc-audit finding 2026-06-26)

**Finding (doc-refactor verification pass, 2026-06-26).** A live tissue acquisition
`ACQ-20250319-CELL-001` (`sample_type = tissue`) has an `anatomy:` block in its
`metadata.json` but **no `condition:` block** — while
[`08_METADATA.md`](../mfb-rdm-docs/08_METADATA.md) §4.5/§4.7 and
[`09_MODALITIES.md`](../mfb-rdm-docs/09_MODALITIES.md) §1 state the `condition:`
block is written for **every** acquisition with `sample_type ∈ {organism, tissue,
cells}` (non-blocking, 2026-06-09).

**To do — code check, not a doc edit:** inspect `tools/ingest/enrichment.py` — is the
`condition:`-block writer actually firing for `tissue` (and `cells`), or only for
`organism`?
- If it's an implementation gap → write the `condition:` block (null/sentinel values
  when not provided) for all of `{organism, tissue, cells}`, consistent with the
  non-blocking model (unknowns → sentinels + WARN, never a failure).
- If `condition:` is intentionally organism-only in practice → correct the docs
  (08_METADATA §4.1/§4.5 + 09_MODALITIES §1) to state the real applicability.

Surfaced by the verification pass; parked here so it isn't lost.

## Architecture & code review follow-through (2026-07-08)

Source: **[`archive/2026-07-08_architecture_code_review.md`](archive/2026-07-08_architecture_code_review.md)**
— a full, immutable review at commit `a6de67d` (branch `main`). That file holds
the reasoning, file:line references, and the "what's right, don't touch" list;
the items below are the actionable extract. **Nothing here is settled** — the
first task is to triage it.

- [x] **Triage this review (done 2026-07-11).** Every load-bearing finding was
  re-verified against the code at HEAD `b721817` (which only added the review doc;
  no code changed since the reviewed `a6de67d`), so the "warrants a verification
  pass" caveat on findings #2–#3, #5–#11 is now discharged — **all hold.** Triage
  outcome below; the safe-operation subset was promoted to
  [`STATUS.md`](STATUS.md) §2.1.

**Triage outcome (2026-07-11, verified against code):**

*Promoted to [`STATUS.md`](STATUS.md) §2.1 — act now:*
- **DR / off-site backup (§3.2.1)** — the only item that can cause *total,
  unrecoverable* loss; unmitigated; plan already written. #1 priority.
- **Concurrency / partial-failure integrity fixes (§3.1 #1–#4).** Do **#2 first**:
  `pending.py` truncate-in-place write is a *durability* bug that needs no
  concurrency — a single interrupted ingest can zero the (live, 250-row) recovery
  queue; the fix is a 3-line copy of the sibling `pending_dicom.py` temp+replace,
  plus taking the lock. Then #1 (dedup snapshot) + #3 (orphan folders on verify
  failure), currently mitigated only by the single-operator manual workflow — must
  land before any concurrent/automated ingest. #4 is a 1-line freebie (move
  `committed=True` to immediately after `append_row`, the true commit point).
- **Schedule weekly `verify_checksums` (slice of §3.2.5).** With no DR, scheduled
  checksum verification is the *only* current tripwire for silent corruption /
  RAID bit-rot — cheapest partial mitigation for the durability gap.

**Implemented so far** — branch `fix/integrity-cluster-2026-07` (2026-07-12, *pending
review/merge*; unit-tested in isolation, no live-NAS ops): the atomic + locked
`pending.py` queue write (§3.1 #2), the copy-phase orphan rollback (§3.1 #3), the
`committed`-inside-lock move (§3.1 #4), the accurate `checksum_present` (§3.1 #9),
and the §2.4 doc catch-ups (the `10_TOOLS.md operator:` trap, `subject_parse` +
`subjects:[]` docs, `rebuild_baseline` stale-header note). **Still open** from the
promoted set: the DR purchase, scheduling `verify_checksums`, and the pre-lock
dedup snapshot (§3.1 #1 — deferred as a design pick; not firing under today's
single-operator workflow). See [`CHANGELOG.md`](../CHANGELOG.md) 2026-07-12.

*Kept here (verified real; later / lower-risk):*
- **#5 hard-link failure swallowed / #6 case-only link collision** — real, but
  *recoverable*: links are a derived convenience, `relink_projects.py
  --create-missing` reconciles them, and the registry (system of record) is
  intact. MED. Bundle as "linker robustness"; ideally emit a per-batch WARN
  summary or a reconcile worklist so missing links are discoverable.
- **#7 lock-timeout discards verified work / #8 O(N) locked sections** — do not
  fire under today's low contention (ms-scale locked windows at 13.5k rows); they
  are *scaling* risks. Cheap win when touched: allocation can trust the
  `.acq_id_seq.json` reservation high-water and skip the full registry scan (O(N)→O(1)).
- **#9 `checksum_present` hardcoded "Y" / #10 StudyDate-fallback idempotency /
  #11 latin-1 mojibake** — all LOW, bounded, and #10 is already documented in-code
  as an accepted edge for one-time deposits.
- **Decouple enrichment from the live DB (§3.2.3)** — *high-value, near the top:*
  the 250 live `pending-db` rows prove the coupling is already degrading ingests,
  and decoupling deletes the ~1,700-LOC subsystem that *contains bug #2*. Fixing #2
  is the urgent patch; this is the strategic fix that subsumes it.
- Everything else below (SQLite Finder §3.2.2, bus factor §3.2.4, close-out
  integrity check §3.2.5, spent-script cleanup §2.1, doc-governance right-sizing
  §2.2, park speculative specs §2.3, the `10_TOOLS.md` doc trap §2.4, test
  consolidation) — confirmed real, correctly scoped as later improvements. The
  `10_TOOLS.md operator:` doc trap is trivial and actively misleads operators, so
  it is the one "later" item worth doing on the next docs pass. *(Precision note:
  the config is rejected by `validate_registry_block` as "not a known column," not
  by a `ResolverError` as the review states — same net effect, config fails.)*

**Promote-to-STATUS candidates (pending triage) — safe-operation, not "later":**

- [ ] **Commit the DR / off-site backup (§3.2.1).** The #1 risk: single NAS, RAID 5
  on 20 TB drives, no off-array copy, true production. The 3-2-1 plan is already
  written in [`02_INFRASTRUCTURE §5.4`](../mfb-rdm-docs/02_INFRASTRUCTURE.md).
  Reframe from "PI decision" to purchase; robust even without the OCRE egress-cap
  answer. **This is inaction, not a design gap.**
- [ ] **Fix the three HIGH latent bugs (§3.1).** All cause silent registry-vs-NAS
  divergence: (1) dedup is a pre-lock snapshot → concurrent/double-launched batch
  double-ingests everything (`config.py:367`/`:610` vs lock at `ingest_raw.py:809`);
  (2) `pending.py` rewrites the recovery queue non-atomically + unlocked → a crash
  wipes the whole queue (`pending.py:70-76`); (3) post-copy early returns leave
  orphan folders the rollback never touches (`ingest_raw.py:986/1069/1102/1139`).
- [ ] **Cheap MED fix: move `committed=True` inside the lock block** (`ingest_raw.py:1325`)
  — a Ctrl-C in the current gap rolls back an acquisition whose registry row was
  already written (dangling pointer to deleted data). Verify against the code first.

**Later improvements (this file's normal remit):**

- [ ] **Fix the `10_TOOLS.md §2.1` `operator:` doc trap (§2.4).** Two examples
  (≈ lines 502, 568) still put `operator:` inside the `registry:` block, which
  `resolver.py` now rejects with a hard `ResolverError`. Small edit; actively
  breaks anyone copying the docs. (Also: doc the multi-animal `subjects:[]` sidecar
  key and the `auto_discover.subject_parse:` block; note `rebuild_baseline/registry_raw.csv`
  is a stale 24-col header.)
- [ ] **Spike a SQLite/Datasette (or dynamic-Finder) search index (§3.2.2).** The
  embedded-HTML Finder is ~19 MB now, linear to ~140 MB at 100 k rows, and still
  rebuilt **wholesale** by the scheduled global refresh (2026-07-20 moved it off
  every-ingest to a schedule + targeted per-project, which caps the per-ingest cost
  but not the full-rebuild size). Keep CSV as source of truth; derive a disposable index.
  Already proposed in [`13 §4.1`](../mfb-rdm-docs/13_GJESUS3_ROLE.md); the
  internal-web-serving capability makes a *dynamic* Finder reachable, not just a
  container.
- [ ] **Archive the ~9–10 spent one-off scripts + lift shared I/O helpers into
  `ingest/` (§2.1).** Move spent `backfill_*`/`relink_*`/`migrate_*`/`gen_*` out of
  `tools/` top-level; lift the 5 duplicated helpers (atomic sidecar write+verify,
  registry-rewrite-under-lock, canonical→path, provenance-row builder,
  idempotent-extract) into the library so the 3–4 verbatim copies of the
  registry-rewrite block can't drift from `REGISTRY_FIELDS`.
- [ ] **Decouple enrichment from the live animal-facility DB (§3.2.3).** Cache the
  facility mapping as a periodically-synced reference table + enrich in a
  post-ingest batch. Also deletes most of the ~1,700-LOC deferred-recovery
  subsystem (`pending.py`, `pending-db` sentinel, `recover_subject_metadata.py`).
- [ ] **Automate the existing validators (§3.2.5).** `validate_registries`,
  `verify_checksums`, `metadata_completeness` all exist but nothing schedules them;
  `subject_ids↔subjects` and `project_id↔projects` are unenforced string joins.
  Weekly scheduled task + an integrity check at project close-out.
- [ ] **De-risk the bus factor (§3.2.4).** Containerize the ingest environment
  (today it's one machine with `J:\` mapped + `~/.my.cnf` + Dicomifier on PATH);
  write the operational runbook; put a second operator through a full real ingest
  (`01 §6` handoff criterion is unproven).
- [ ] **Right-size doc governance + park speculative specs (§2.2/§2.3).** Consider
  generating the registry-schema doc table *from* `REGISTRY_FIELDS` instead of
  hand-mirroring; demote `EM/` to "add when it arrives"; park curated-datasets and
  lightweight-mode until a real case appears.
- [ ] **Consolidate the scattered `test_*.py` into a collectable suite (§2.1).**
  13 hand-rolled un-collectable tests across three dirs; date-stamped regression
  files keep accreting.

## Ingest safety + audit-table clarity (from the NI test-data removal, 2026-08-06)

Source: the removal of two synthetic NI acquisitions that a verification run wrote
into true production on 2026-06-29 and that went unnoticed for five weeks
(narrative in [`../CHANGELOG.md`](../CHANGELOG.md) 2026-08-06). Two items, one of
which matters much more than the other.

- [ ] **A `--nas-root` pointing at true production is silently accepted — add a
  guard.** This is the item worth acting on. The 2026-06-29 run used a synthetic
  source tree (a 5-byte `DCM-0` stub per acquisition) but passed
  `--nas-root J:\gjesus3-data`; **nothing in the run distinguished it from a real
  ingest**, and it auto-created a project on the way in. Options: a confirmation
  prompt, or an explicit gate (`--i-know-this-is-production` or similar) when
  `--nas-root` resolves to the live root. Note the ordinary operator path does not
  need this — the GUI targets the live root by design — so the gate should key on
  *interactive CLI use*, not on the path alone, or it becomes noise that gets
  auto-answered. Related: the `ingest.auto_create_projects` flag defaults to
  `false` precisely to stop typos creating rogue projects, and this run had it on.

- [ ] **Make the auto-create path discoverable in the side-effect inventory
  ([`10_TOOLS §2.1`](../mfb-rdm-docs/10_TOOLS.md)) — a clarity fix, not a missing
  row.** The removal hand-off reported that the inventory "does not cover project
  auto-creation." **That is not correct** — row **#10** covers it (the
  `projects/<name>/` folder + `_project.yaml` + the `registry_projects.csv` row,
  conditioned on `auto_create_projects` and a non-existent name), and it has been
  there since the inventory was written (`ed62eca`, 2026-07-20). The reversal
  performed on 2026-08-06 used rows #1/#3/#4/#5/#6/#7/#8/#9/#10 and found **nothing
  missing**. The real defect is discoverability: an auto-created project's side
  effects are spread across rows #7–#10, and #7 leads with the condition "resolves
  to an **existing** project", which reads as though auto-creation is out of scope
  — a careful reader concluded exactly that. Consider a one-line pointer from #7 to
  #10, or grouping the four project-related rows under a sub-heading. Low priority;
  the table is complete and worked in practice.
