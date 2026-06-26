# Contributing to the gjesus3 Documentation

**Last Updated:** 2026-06-26

This is the **doc-governance reference** for the gjesus3 RDM repository: where each kind of content belongs, the status markers, the cross-reference / integrity-mirror rules that keep specs and code in sync, and the git + style conventions. Read it before adding or restructuring documentation.

[`CLAUDE.md`](CLAUDE.md) carries the slim must-obey rules and points here for the detail. [`README.md`](README.md) is the 3-role gateway. The authoritative design specs live in [`mfb-rdm-docs/`](mfb-rdm-docs/) (master map: [`00_INDEX.md`](mfb-rdm-docs/00_INDEX.md)); the dated narrative of decisions lives in [`CHANGELOG.md`](CHANGELOG.md).

---

## Documentation architecture — what belongs where

This repo deliberately separates **rules** (specs / conventions / schemas) from **state** (current work / open questions) from **instrument-specific reality** (per-platform workflows) from **audience entry points** (role gateways). Respect the boundaries when adding new content.

| Location | Role | Don't put here |
|---|---|---|
| [`README.md`](README.md) | 3-role gateway — one-glance "what is this, where do I go" for Researcher / Operator / Developer. | Detailed decisions or specs (those belong in `mfb-rdm-docs/`). |
| [`RESEARCHER_GUIDE.md`](RESEARCHER_GUIDE.md) | Researcher entry point — what gjesus3 holds, how to find and view your data, how projects work, in plain language. | Code internals, schemas, operator/ingest procedure. |
| [`START_HERE.md`](START_HERE.md) | Operator one-pager — pick a front-end, set `GJESUS3_ROOT`, dry-run, ingest. | Full CLI reference (that's `tools/INGEST_CLI.md`); design rationale. |
| [`GLOSSARY.md`](GLOSSARY.md) | Term definitions — REMBI / ISA / UBERON / sidecar / `discovered.*` / ACQ-ID and other vocabulary used across the docs. | Process or schema detail; only the definitions. |
| [`CLAUDE.md`](CLAUDE.md) | Agent-facing must-obey rules: where to start, what to never edit, status markers, a short doc-architecture pointer. | The verbose governance detail (it lives here); the specs themselves (only pointers). |
| [`CONTRIBUTING-docs.md`](CONTRIBUTING-docs.md) (this file) | The full doc-architecture table, status-marker definitions, cross-reference / integrity-mirror rules, git + style conventions. | The specs themselves; operational state. |
| [`mfb-rdm-docs/`](mfb-rdm-docs/) (00–13) | **Authoritative design specs** — decisions, conventions, schemas, principles. Numbered modules. [`00_INDEX.md`](mfb-rdm-docs/00_INDEX.md) is the master map. | Operational state ("what's done this week"), per-instrument quirks, code implementation details. |
| [`tasks/STATUS.md`](tasks/STATUS.md) | Operational state — a lean current-state snapshot: what's live, what's in flight, open questions, per-round detail trails. | Permanent rules (→ `mfb-rdm-docs/`); per-instrument workflow notes (→ `equipment/`); **later improvements** (→ `tasks/BACKLOG.md`). |
| [`tasks/BACKLOG.md`](tasks/BACKLOG.md) | **Later improvements** — refinements and second-/third-stage features not required for the hand-off. Promote to `STATUS.md` when an item becomes a delivery blocker. | Anything required for users/operators to start (that's `STATUS.md`). |
| `tasks/archive/` | Superseded handoffs and old planning notes, kept for historical context. | **Never edit** — these are a historical record. Write new state in `STATUS.md`. |
| [`equipment/`](equipment/) | Per-instrument workflow notes, platform descriptions, observed user behaviour, systematic naming conventions. The bridge between abstract specs and concrete instrument reality. [`equipment/INDEX.md`](equipment/INDEX.md) is the map. | System-wide specs / schemas (those belong in `mfb-rdm-docs/`). |
| [`tools/`](tools/) | Implementation + tool docs. Top-level CLIs (`ingest_raw.py`, `create_project.py`) + `ingest/` modules + `operator/` front-ends + `templates/` + `configs/` + standalone utilities. [`tools/INDEX.md`](tools/INDEX.md) is the master tool map; [`tools/INGEST_CLI.md`](tools/INGEST_CLI.md) the CLI reference; [`tools/FINDER.md`](tools/FINDER.md) the Finder; [`tools/FAQ.md`](tools/FAQ.md) the researcher FAQ; [`tools/OPERATOR_FAQ.md`](tools/OPERATOR_FAQ.md) the operator FAQ. | Spec documentation (point at `mfb-rdm-docs/` from inline docstrings instead). |
| [`CHANGELOG.md`](CHANGELOG.md) | The single narrative, dated history of design + tooling decisions. | Current-state snapshots (→ `tasks/STATUS.md`); permanent rules (→ `mfb-rdm-docs/`). **Append new entries only; never rewrite history.** |

**When you're about to write something, ask which row it matches:**

- A permanent rule about how the system works → `mfb-rdm-docs/`.
- "This is what happens at Instrument X" → `equipment/`.
- "We should do this later" → `tasks/BACKLOG.md`; "we're doing this now / it's blocking" → `tasks/STATUS.md`.
- "What does this YAML field do" → either [`10_TOOLS.md`](mfb-rdm-docs/10_TOOLS.md) (spec) or [`tools/INGEST_CLI.md`](tools/INGEST_CLI.md) (operator-facing CLI ref) — most often both.
- A plain-language answer for a researcher → [`RESEARCHER_GUIDE.md`](RESEARCHER_GUIDE.md) or [`tools/FAQ.md`](tools/FAQ.md).
- A quick answer for an operator running an ingest → [`tools/OPERATOR_FAQ.md`](tools/OPERATOR_FAQ.md).

---

## Status markers

Respect these throughout the documentation. Each spec section and decision should carry the marker that reflects its real state; do not silently change a settled (`✅`) item.

| Emoji | Marker | Meaning |
|---|---|---|
| ✅ | `DECIDED` | Settled. Do not change without explicit user instruction. |
| 🔶 | `DRAFT` | Working content; can be refined, but flag substantive changes. |
| ⚠️ | `GAP` | Information or decision needed; don't invent answers. |
| ❓ | `EVALUATING` | Under active consideration; present options rather than making the choice. |
| 📋 | `INPUT NEEDED` | Waiting on stakeholder feedback; don't fill in assumptions. |
| 🕗 | `PLANNED / DEFERRED` | Intended but not built/deployed yet; document as planned and point at [`tasks/BACKLOG.md`](tasks/BACKLOG.md). |

Vocabulary / convention decisions (e.g. registry column naming, ISA terminology) are **Data Office calls informed by user input** — never write "pending PI sign-off" or treat them as blocked-on-stakeholder.

---

## Documentation discipline

- Core deliverables live in `mfb-rdm-docs/`. Use [`00_INDEX.md`](mfb-rdm-docs/00_INDEX.md) as the map. Per-instrument context lives in `equipment/<instrument>/`.
- **Always read the relevant docs before suggesting changes.**
- When updating one document, check for cross-reference impacts on others (see **Cross-reference consistency** below).
- **Never edit historical / archived material:** `tasks/archive/`, and the dated history in [`CHANGELOG.md`](CHANGELOG.md) (append new entries; do not rewrite past ones). The numbered specs carry the *current* state; the CHANGELOG carries the *narrative of how we got there*.
- When a new convention or schema is added, update **all** of: the spec doc (in `mfb-rdm-docs/`), any per-instrument templates that exercise it (`tools/templates/instruments/*.yaml`), the CLI reference ([`tools/INGEST_CLI.md`](tools/INGEST_CLI.md) if operator-visible), and the master map ([`00_INDEX.md`](mfb-rdm-docs/00_INDEX.md) — bump **Last Updated**; the dated narrative goes in [`CHANGELOG.md`](CHANGELOG.md)).
- On the numbered specs (00–13), change STATUS / dates / wording surgically; **preserve all schema / field / logic content exactly.** If a real logic change seems needed, raise it rather than slipping it into a doc edit.

---

## Cross-reference consistency

When updating one document, check for impacts on these. The **integrity mirrors** (06↔code, 08↔code, 09↔code, 10↔templates) are the load-bearing ones: spec and code MUST agree, and several are enforced at runtime.

- **[`00_INDEX.md`](mfb-rdm-docs/00_INDEX.md)** — Key Decisions table and Key Gaps; bump **Last Updated**. The full dated Version History now lives in [`CHANGELOG.md`](CHANGELOG.md) (00_INDEX points to it) — add the narrative entry there.
- **[`13_GJESUS3_ROLE.md`](mfb-rdm-docs/13_GJESUS3_ROLE.md)** — the reframe rationale that drives many downstream choices (research-facing working layer, ISA terminology, derivatives-belong-in-projects). If you're changing scope or design principles, check here first.
- **[`01_OVERVIEW.md`](mfb-rdm-docs/01_OVERVIEW.md)** — system purpose and design principles; should stay aligned with `13_GJESUS3_ROLE`.
- **[`03_RAW_STORAGE.md`](mfb-rdm-docs/03_RAW_STORAGE.md)** — per-ecosystem primary-entity shapes (file / archive / folder) live in §4. Instrument codes here must match [`09_MODALITIES.md`](mfb-rdm-docs/09_MODALITIES.md) and [`equipment/INDEX.md`](equipment/INDEX.md).
- **[`06_REGISTRIES.md`](mfb-rdm-docs/06_REGISTRIES.md) ↔ `tools/ingest/resolver.py` + `registry.py` (INTEGRITY MIRROR).** Registry schemas must match field references elsewhere. `session_id` + `primary_kind` are DRAFT columns; `subject_ids` is an **Auto** column (added 2026-06-11 as `subject_id`, **renamed to packed `subject_ids` 2026-06-12, NI-LIVE-08** — the facility animal id(s) from the enrichment subject block, `;`-joined always-a-list; lives in `AUTO_COLUMNS`, never user-set). The `USER_CONTROLLABLE_COLUMNS` / `AUTO_COLUMNS` sets in `tools/ingest/resolver.py` and the `REGISTRY_FIELDS` list in `tools/ingest/registry.py` must match the documented schema (§2.2); the defensive header check in `registry.append_row` enforces this at runtime. **Registry-integrity (§2.7):** every CSV append goes through the BOM-tolerant, trailing-newline-safe helper `tools/ingest/csv_safe.py` (new CSV writers MUST use it); ACQ-ID allocation + the row append are serialized by `tools/ingest/locking.py` (`registries/.registry.lock` + the `.acq_id_seq.json` high-water reservation).
- **[`07_PROVENANCE.md`](mfb-rdm-docs/07_PROVENANCE.md)** — referenced by [`04_PUBLICATIONS.md`](mfb-rdm-docs/04_PUBLICATIONS.md) and [`05_PROJECTS.md`](mfb-rdm-docs/05_PROJECTS.md).
- **[`08_METADATA.md`](mfb-rdm-docs/08_METADATA.md) ↔ `tools/ingest/metadata_sidecar.py` + the per-eco builders (INTEGRITY MIRROR).** The `metadata.json` sidecar shape written by `tools/ingest/metadata_sidecar.py` must match what's documented here. The `mri:` block shape comes from `tools/ingest/paravision_metadata.py::build_mri_section`; the `microscopy:` block from `tools/ingest/czi_metadata.py::build_microscopy_section`; the `ni:` block from `tools/ingest/ni_metadata.py::build_ni_section`. Section-name overrides (e.g. ParaVision data → `mri:` not `dicom:`) flow through the 3-tuple extractor return form documented in §4.3.
- **[`09_MODALITIES.md`](mfb-rdm-docs/09_MODALITIES.md) ↔ `tools/ingest/<eco>_metadata.py` `EXPOSED_FIELDS` (INTEGRITY MIRROR).** Each instrument's "Auto-discovered fields" subsection MUST mirror `EXPOSED_FIELDS` in the matching `tools/ingest/<eco>_metadata.py` module (currently `czi_metadata.py`, `paravision_metadata.py`, and `ni_metadata.py`). When you add or rename a field, update both.
- **[`10_TOOLS.md`](mfb-rdm-docs/10_TOOLS.md) ↔ the templates (INTEGRITY MIRROR).** YAML ingest schema. If you add/rename a `registry:` column or `discovered.*` source, update [`06_REGISTRIES.md`](mfb-rdm-docs/06_REGISTRIES.md) (schema), [`08_METADATA.md`](mfb-rdm-docs/08_METADATA.md) (sidecar), `tools/templates/ingest_template.yaml` (universal), AND every `tools/templates/instruments/*.yaml` (per-instrument) together. The `link_filename:` field's context dict (resolved registry fields + `discovered.*` + `acq_id` + `acq_date`) is documented in §2.1.5.
- **[`equipment/<instrument>/`](equipment/)** — when an instrument's naming convention or workflow changes, update the per-instrument workflow notes there AND any per-instrument template under `tools/templates/instruments/`.

---

## Ingest configs

- **Per-instrument templates** live in `tools/templates/instruments/` (e.g. `axioscan7.yaml`, `cell_observer_cells.yaml`, `lsm900.yaml`, `mri_bruker.yaml`, `molecubes_ni.yaml`, `molecubes_ni_live.yaml`) — they lock in the instrument-specific patterns (filename parse, registry mapping, project_hint convention, `link_filename:` default). Each template's **header comments must list every `discovered.*` field auto-populated for that instrument** as the operator's reference card. Copy and edit; never edit in place. Add a new template when bringing a new instrument online.
- **Universal starter** at `tools/templates/ingest_template.yaml` — fallback for instruments not yet onboarded.
- **Per-batch configs** live in `tools/configs/` (under git, version-locked with the scripts) — produced by copying the matching per-instrument template, editing `staging_dir` + `notes`, saving as `<instrument>_<batch>.yaml`. Each registry row's `ingest_config` column records the relative path of the config that produced it.

---

## Production lifecycle (context for ongoing work)

The system is in **TRUE PRODUCTION** since the 2026-06-10 restart. The earlier quasi-production pilot — each instrument iterating **test → purge → accept**, then a **whole-system purge after the team exhibition** — is **complete and historical**; that purge already happened on 2026-06-10 and there is **no future exhibition / purge / restart pending**. The dated narrative is in [`CHANGELOG.md`](CHANGELOG.md). Implications:

- **The live data is real and retained long-term.** Treat the registry and `/raw/` with production care — an ingest that goes wrong is *damaging*, not ephemeral.
- **TEST tags are the exception, not the norm.** A genuinely experimental run may still carry a "TEST INGEST — purge after review" tag, but most ingests are real and retained. Don't read a TEST tag as "will be wiped at the next exhibition purge" — that lifecycle is over.
- The `tools/migrate_registry_columns.py` pattern (back up → migrate → register the `.bak` path) is the right shape when the schema must evolve; the defensive header check in `registry.append_row` enforces correct migration order. (The restart already applied a fresh-header schema — `sample_organism` + `subject_id`→packed `subject_ids` + `anatomical_entity` — so this pattern is for *future* evolution, not the restart itself.)

---

## Equipment reference

- [`equipment/INDEX.md`](equipment/INDEX.md) is the starting point for in-scope imaging instruments.
- Two categories: **microscopes** (raw = direct instrument output) and **platform instruments** (raw = reconstructed images provided by the platform).
- Each instrument's folder may include a `*_data_handling_workflow_notes.md` describing the operator workflow + systematic naming convention. These notes are the **source of truth** for what `discovered.*` fields a per-instrument template can expose.

---

## Git conventions

- Write clear commit messages describing **what** changed and **why**.
- **Stage specific files** rather than using `git add -A`.
- The repo contains large binary files (xlsx, docx) and `contacts.xlsx` — **avoid staging these unless asked.**
- One commit per logical unit of work; prefer multiple small commits over one giant atomic dump.

---

## Style conventions

- Documentation is written in **Markdown**.
- Use the existing document conventions (status markers, cross-references, open-questions tables).
- Keep language **precise but accessible** — end users are researchers, not IT professionals. Researcher-facing docs use plain language and avoid code internals; specs are precise and define or link [`GLOSSARY.md`](GLOSSARY.md) terms. Keep docs chatbot-answerable: clear headings, defined terms.
- When in doubt about a design choice, **present options rather than picking one.**
- In user-facing path examples for Windows, use **backslash style** (`J:\gjesus3-data`, `\\GJESUS3\gjesus3\gjesus3-data`), not POSIX slashes.
- Per-instrument template comments must be **operator-readable** — list every `discovered.*` they can reference and what the default `link_filename:` produces.
