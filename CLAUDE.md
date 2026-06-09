# Claude Code Instructions — gjesus3 RDM Pilot

## On Startup

1. Read [`tasks/tasks.md`](tasks/tasks.md) to understand current priorities and what to work on next. §0 "Active Pass / Up Next" is the entry point.
2. Update `tasks/tasks.md` as work progresses — mark items done, add new items as they emerge.
3. For system design context, see [`mfb-rdm-docs/00_INDEX.md`](mfb-rdm-docs/00_INDEX.md) (master map), [`mfb-rdm-docs/01_OVERVIEW.md`](mfb-rdm-docs/01_OVERVIEW.md) (scope and rationale), and [`mfb-rdm-docs/13_GJESUS3_ROLE.md`](mfb-rdm-docs/13_GJESUS3_ROLE.md) (the research-facing-working-layer reframe — explains many downstream design choices).
4. For per-instrument workflows / systematic naming conventions, see [`equipment/INDEX.md`](equipment/INDEX.md) and the per-instrument folders.

## Project Type

This is a **design, documentation, and tooling project** for a research data management system — **as much about documenting conventions, standards, schemas, and operational procedures as it is about writing code.** The primary deliverables are specifications in `mfb-rdm-docs/`, per-instrument workflow notes in `equipment/`, the operational task list in `tasks/tasks.md`, and Python scripts in `tools/`. See [README.md](README.md) for project overview.

## Project Context

- **Organization:** CIC biomaGUNE (research institute, Spain)
- **Group:** MFB (led by PI Jesus Ruiz-Cabello)
- **Data Management Lead:** Ryan Tasseff (Data Office)
- **Infrastructure:** QNAP NAS "gjesus3" (TS-864eU, 6 × 20 TB, RAID 5, ~63 TB user-available after snapshot reservation), SMB share `\\GJESUS3\gjesus3`
- **Access:** Hardwired on-site machines only (no laptops)
- **Status:** Pilot in **quasi-production state** — four ingest rounds complete (collaborator DICOM 75 acqs, AxioScan 7 28 acqs, Cell Observer 165 acqs, internal MRI 97 acqs). Will be purged after team exhibition and restarted as true production with feedback incorporated. "Done" in this project means "done in quasi-production" unless explicitly noted.

## Documentation architecture — what belongs where

This repo deliberately separates **rules** (specs / conventions / schemas) from **state** (current work / open questions) from **instrument-specific reality** (per-platform workflows). Respect the boundaries when adding new content:

| Location | Role | Don't put here |
|---|---|---|
| `README.md` | Newcomer orientation only — one-glance "what is this, where do I go." | Detailed decisions or specs (those belong in `mfb-rdm-docs/`). |
| `CLAUDE.md` (this file) | Agent-facing operating rules: where to start, cross-ref rules, status markers, doc-architecture. | The actual specs themselves; only pointers to them. |
| `mfb-rdm-docs/` (00–13) | **Authoritative design specs** — decisions, conventions, schemas, principles. Numbered modules. `00_INDEX.md` is the master map + version history. | Operational state ("what's done this week"), per-instrument quirks, code implementation details. |
| `tasks/tasks.md` | Operational state — the **work to get the pilot to users/operators** (active delivery path), open questions, per-round detail trails. | Permanent rules (those belong in `mfb-rdm-docs/`); per-instrument workflow notes (those belong in `equipment/`); **later improvements** (those belong in `tasks/BACKLOG.md`). |
| `tasks/BACKLOG.md` | **Later improvements** — refinements and second-/third-stage features not required for the hand-off. Promote to `tasks.md` when an item becomes a delivery blocker. | Anything required for users/operators to start (that's `tasks.md`). |
| `equipment/<instrument>/` | Per-instrument workflow notes, platform descriptions, observed user behaviour, systematic naming conventions. The bridge between abstract specs and concrete instrument reality. `equipment/INDEX.md` is the map. | System-wide specs / schemas (those belong in `mfb-rdm-docs/`). |
| `tools/` | Implementation. Top-level CLIs (`ingest_raw.py`, `create_project.py`) + `ingest/` modules + `templates/` + `configs/` + standalone utilities. `tools/INGEST_CLI.md` is the CLI reference. | Spec documentation (point at `mfb-rdm-docs/` from inline docstrings instead). |
| `mfb-rdm-docs/depricated/` | Historical drafts preserved for context. | **Never edit.** Add a new doc and link/contrast with the old if needed. |

When you're about to write something, ask which of the above it most closely matches. If it's a permanent rule about how the system works → `mfb-rdm-docs/`. If it's a "this is what happens at Instrument X" → `equipment/`. If it's "we should do this later" → `tasks/tasks.md`. If it's "what does this YAML field do" → either `10_TOOLS.md` (spec) or `tools/INGEST_CLI.md` (operator-facing CLI ref) — most often both.

## Development Environment

- **Scripting/development:** Use WSL (Ubuntu) for building scripts, extraction, checksums, etc.
- **NAS mount:** On Ryan's workstation, the NAS is mapped at `J:\` (Windows) and `/mnt/gjesus3` in WSL. Always mounted at boot. Use the J:\ paths from Bash/Git Bash on Windows.
- **User-facing tools:** Write in Python (cross-platform) so Windows users can run them without WSL.
- **User handles:** `sudo` commands for WSL setup.

## Key Rules

### Documentation discipline

- Core deliverables live in `mfb-rdm-docs/`. Use `00_INDEX.md` as the map. Per-instrument context lives in `equipment/<instrument>/`.
- Always read relevant docs before suggesting changes.
- When updating one document, check for cross-reference impacts on others (see Cross-reference consistency below).
- **Never edit** files in `mfb-rdm-docs/depricated/` — they are historical records.
- When a new convention or schema is added, update **all** of: the spec doc (in `mfb-rdm-docs/`), any per-instrument templates that exercise it (`tools/templates/instruments/*.yaml`), the CLI reference (`tools/INGEST_CLI.md` if operator-visible), and the master map (`00_INDEX.md` version history).

### Status markers

Respect these throughout the documentation:

- `DECIDED` — Do not change without explicit user instruction
- `DRAFT` — Can be refined, but flag substantive changes
- `GAP` — Information or decision needed; don't invent answers
- `EVALUATING` — Under active consideration; present options rather than making choices
- `INPUT NEEDED` — Waiting on stakeholder feedback; don't fill in assumptions

### Cross-reference consistency

When updating one document, check for impacts on others:

- `00_INDEX.md` — Key Decisions table, Key Gaps, and Version History; bump Last Updated.
- `13_GJESUS3_ROLE.md` — the reframe rationale that drives many downstream choices (research-facing working layer, ISA terminology, derivatives-belong-in-projects). If you're changing scope or design principles, check here first.
- `01_OVERVIEW.md` — system purpose and design principles; should stay aligned with `13_GJESUS3_ROLE`.
- `03_RAW_STORAGE.md` — per-ecosystem primary-entity shapes (file / archive / folder) live in §4. Instrument codes here must match `09_MODALITIES.md` and `equipment/INDEX.md`.
- `06_REGISTRIES.md` — registry schemas must match field references elsewhere. `session_id` + `primary_kind` are DRAFT columns. The `USER_CONTROLLABLE_COLUMNS` set in `tools/ingest/resolver.py` and the `REGISTRY_FIELDS` list in `tools/ingest/registry.py` must match the documented schema; the defensive header check in `append_row` enforces this at runtime.
- `07_PROVENANCE.md` — referenced by `04_PUBLICATIONS.md` and `05_PROJECTS.md`.
- `08_METADATA.md` — `metadata.json` sidecar shape; the file written by `tools/ingest/metadata_sidecar.py` must match what's documented here. The `mri:` block shape comes from `tools/ingest/paravision_metadata.py::build_mri_section`; the `microscopy:` block from `tools/ingest/czi_metadata.py::build_microscopy_section`. Section name overrides (e.g. ParaVision data → `mri:` not `dicom:`) flow through the 3-tuple extractor return form documented in §4.3.
- `09_MODALITIES.md` — per-instrument "Auto-discovered fields" subsection MUST mirror `EXPOSED_FIELDS` in the matching `tools/ingest/<eco>_metadata.py` module (currently `czi_metadata.py` and `paravision_metadata.py`). When you add or rename a field, update both.
- `10_TOOLS.md` — YAML ingest schema. If you add/rename a `registry:` column or `discovered.*` source, update `06_REGISTRIES.md` (schema), `08_METADATA.md` (sidecar), `tools/templates/ingest_template.yaml` (universal), AND every `tools/templates/instruments/*.yaml` (per-instrument) together. The `link_filename:` field's context dict (resolved registry fields + `discovered.*` + `acq_id` + `acq_date`) is documented in §2.1.5.
- `equipment/<instrument>/` — when an instrument's naming convention or workflow changes, update the per-instrument workflow notes there AND any per-instrument template under `tools/templates/instruments/`.

### Ingest configs

- **Per-instrument templates** live in `tools/templates/instruments/` (e.g. `axioscan7.yaml`, `cell_observer_cells.yaml`, `mri_bruker.yaml`) — they lock in the instrument-specific patterns (filename parse, registry mapping, project_hint convention, `link_filename:` default). Each template's **header comments must list every `discovered.*` field auto-populated for that instrument** as the operator's reference card. Copy and edit; never edit in place. Add a new template when bringing a new instrument online.
- **Universal starter** at `tools/templates/ingest_template.yaml` — fallback for instruments not yet onboarded.
- **Per-batch configs** live in `tools/configs/` (under git, version-locked with the scripts) — produced by copying the matching per-instrument template, editing `staging_dir` + `notes`, saving as `<instrument>_<batch>.yaml`. Each row's `ingest_config` column records the relative path of the config that produced it.

### Quasi-production lifecycle

The pilot operates in a deliberate two-phase setup: each instrument iterates **test → purge → accept-as-quasi-production**, and after the team exhibition **all of it gets purged** for a true production restart. Implications for ongoing work:

- Configs and registry rows can carry a "TEST INGEST — purge after review" tag indefinitely without being a problem; the tag *is* what makes the eventual purge unambiguous. Don't strip TEST tags from configs/rows that are technically "done."
- Treat the existing 365+ NAS acquisitions as quasi-production data: real enough to verify against, ephemeral enough that the user's risk tolerance permits experimental ingests against the live registry (annoying-but-not-damaging if it goes wrong).
- The `tools/migrate_registry_columns.py` pattern (back up → migrate → register the .bak path) is the right shape when the schema needs to evolve; the defensive header check in `registry.append_row` enforces correct migration order.

### Equipment reference

- `equipment/INDEX.md` is the starting point for in-scope imaging instruments.
- Two categories: **microscopes** (raw = direct instrument output) and **platform instruments** (raw = reconstructed images provided by the platform).
- Each instrument's folder may include a `*_data_handling_workflow_notes.md` describing the operator workflow + systematic naming convention. These notes are the source of truth for what `discovered.*` fields a per-instrument template can expose.

## Git Usage

- Write clear commit messages describing what changed and why.
- Stage specific files rather than using `git add -A`.
- Repo contains large binary files (xlsx, docx) in `shared/` and `contacts.xlsx` — avoid staging these unless asked.
- One commit per logical unit of work; multiple small commits over one giant atomic dump.

## Style and Conventions

- Documentation is written in Markdown.
- Use existing document conventions (status markers, cross-references, open questions tables).
- Keep language precise but accessible — end users are researchers, not IT professionals.
- When in doubt about a design choice, present options rather than picking one.
- Per-instrument template comments must be **operator-readable** — list every `discovered.*` they can reference and what the default `link_filename:` produces.
