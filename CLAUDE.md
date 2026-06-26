# Claude Code Instructions — gjesus3 RDM

Agent operating rules: where to start, what to never edit, the must-obey conventions. The **full doc-governance detail** — the complete documentation-architecture table, status-marker definitions, cross-reference / integrity-mirror rules, and style conventions — lives in [`CONTRIBUTING-docs.md`](CONTRIBUTING-docs.md). Read it before adding or restructuring documentation.

## On Startup

1. Read [`tasks/STATUS.md`](tasks/STATUS.md) for current priorities and what to work on next — it's the lean current-state entry point. Later improvements live in [`tasks/BACKLOG.md`](tasks/BACKLOG.md); the dated history is in [`CHANGELOG.md`](CHANGELOG.md).
2. Update `tasks/STATUS.md` as work progresses — mark items done, add new items as they emerge.
3. For system design context, see [`mfb-rdm-docs/00_INDEX.md`](mfb-rdm-docs/00_INDEX.md) (master map), [`mfb-rdm-docs/01_OVERVIEW.md`](mfb-rdm-docs/01_OVERVIEW.md) (scope and rationale), and [`mfb-rdm-docs/13_GJESUS3_ROLE.md`](mfb-rdm-docs/13_GJESUS3_ROLE.md) (the research-facing-working-layer reframe — explains many downstream design choices).
4. For per-instrument workflows / systematic naming conventions, see [`equipment/INDEX.md`](equipment/INDEX.md) and the per-instrument folders.

## Project Type

A **design, documentation, and tooling project** for a research data management system — as much about documenting conventions, standards, schemas, and operational procedures as about writing code. Primary deliverables: specs in [`mfb-rdm-docs/`](mfb-rdm-docs/), per-instrument notes in [`equipment/`](equipment/), the current-state list in [`tasks/STATUS.md`](tasks/STATUS.md), and Python scripts in [`tools/`](tools/). See [`README.md`](README.md) for the 3-role overview.

## Project Context

- **Organization:** CIC biomaGUNE (research institute, Spain)
- **Group:** MFB (led by PI Jesus Ruiz-Cabello)
- **Data Management Lead:** Ryan Tasseff (Data Office)
- **Infrastructure:** QNAP NAS "gjesus3" (TS-864eU, 6 × 20 TB, RAID 5, ~63 TB user-available after snapshot reservation), SMB share `\\GJESUS3\gjesus3`. On Ryan's workstation: mapped at `J:\gjesus3-data` (Windows) / `/mnt/gjesus3` in WSL, always mounted at boot. Read live state from the NAS before trusting docs.
- **Access:** Hardwired on-site machines only (no laptops).
- **Status:** **TRUE PRODUCTION since the 2026-06-10 restart.** All data is real and retained long-term — treat the registry and `/raw/` with production care. **The quasi-production pilot (per-instrument test → purge → accept, then a whole-system purge after the team exhibition) is COMPLETE and HISTORICAL — that purge already happened on 2026-06-10; there is NO future exhibition / purge / restart pending.** "Done" in this project means "done in true production" unless explicitly noted. Lifecycle context: [`CONTRIBUTING-docs.md`](CONTRIBUTING-docs.md#production-lifecycle-context-for-ongoing-work); dated history: [`CHANGELOG.md`](CHANGELOG.md).

## Development Environment

- **Scripting/development:** Use WSL (Ubuntu) for building scripts, extraction, checksums, etc.
- **User-facing tools:** Write in Python (cross-platform) so Windows users can run them without WSL.
- **User handles:** `sudo` commands for WSL setup.

## Status markers

Respect these throughout the documentation (full definitions in [`CONTRIBUTING-docs.md`](CONTRIBUTING-docs.md#status-markers)):

- ✅ `DECIDED` — do not change without explicit user instruction
- 🔶 `DRAFT` — can be refined, but flag substantive changes
- ⚠️ `GAP` — information or decision needed; don't invent answers
- ❓ `EVALUATING` — under active consideration; present options rather than choosing
- 📋 `INPUT NEEDED` — waiting on stakeholder feedback; don't fill in assumptions
- 🕗 `PLANNED / DEFERRED` — intended but not built/deployed yet; document as planned, point to [`tasks/BACKLOG.md`](tasks/BACKLOG.md)

## Documentation architecture — pointer

This repo separates **rules** (specs / schemas) from **state** (current work) from **instrument reality** (per-platform workflows) from **audience entry points** (role gateways). Quick map — **full table + the boundary rules are in [`CONTRIBUTING-docs.md`](CONTRIBUTING-docs.md#documentation-architecture--what-belongs-where):**

| Location | Role |
|---|---|
| [`README.md`](README.md) | 3-role gateway (Researcher / Operator / Developer). |
| [`RESEARCHER_GUIDE.md`](RESEARCHER_GUIDE.md) · [`START_HERE.md`](START_HERE.md) · [`GLOSSARY.md`](GLOSSARY.md) | Researcher entry point · operator one-pager · term definitions. |
| [`CLAUDE.md`](CLAUDE.md) (this file) · [`CONTRIBUTING-docs.md`](CONTRIBUTING-docs.md) | Agent must-obey rules · full doc-governance detail. |
| [`mfb-rdm-docs/`](mfb-rdm-docs/) (00–13) | **Authoritative design specs.** [`00_INDEX.md`](mfb-rdm-docs/00_INDEX.md) is the master map. |
| [`equipment/<instrument>/`](equipment/) | Per-instrument workflow notes + platform reality. [`INDEX.md`](equipment/INDEX.md) is the map. |
| [`tools/`](tools/) | Implementation + tool docs ([`INDEX.md`](tools/INDEX.md), [`INGEST_CLI.md`](tools/INGEST_CLI.md), [`FINDER.md`](tools/FINDER.md), [`FAQ.md`](tools/FAQ.md), [`OPERATOR_FAQ.md`](tools/OPERATOR_FAQ.md)). |
| [`tasks/STATUS.md`](tasks/STATUS.md) · [`tasks/BACKLOG.md`](tasks/BACKLOG.md) | Lean current-state · later improvements. |
| [`CHANGELOG.md`](CHANGELOG.md) | Single dated narrative of decisions. |

When you're about to write something, ask which row it matches: a permanent rule → `mfb-rdm-docs/`; "what happens at Instrument X" → `equipment/`; "do this later" → `tasks/BACKLOG.md`; current work → `tasks/STATUS.md`; a YAML field's meaning → `10_TOOLS.md` (spec) and/or `tools/INGEST_CLI.md` (CLI ref).

## Must-obey rules

- **Respect status markers** (above) — never silently change a ✅ `DECIDED` item.
- **Never edit historical / archived material:** files in `tasks/archive/`, and the dated history in [`CHANGELOG.md`](CHANGELOG.md) (append new entries; do not rewrite past ones). The numbered specs carry the *current* state; the CHANGELOG carries the narrative of how we got there.
- **On the numbered specs (00–13),** change STATUS / dates / wording surgically; **preserve all schema / field / logic content exactly.** If a real logic change seems needed, raise it rather than slipping it into a doc edit.
- **Always read the relevant docs before suggesting changes.** When updating one document, check cross-reference impacts on others — especially the **integrity mirrors** where spec and code MUST agree (06↔`resolver.py`/`registry.py`, 08↔`metadata_sidecar.py` + the per-eco builders, 09↔`<eco>_metadata.py` `EXPOSED_FIELDS`, 10↔the templates). Full rules: [`CONTRIBUTING-docs.md`](CONTRIBUTING-docs.md#cross-reference-consistency).
- **When a new convention or schema is added,** update all of: the spec doc (`mfb-rdm-docs/`), the per-instrument templates that exercise it (`tools/templates/instruments/*.yaml`), the CLI reference ([`tools/INGEST_CLI.md`](tools/INGEST_CLI.md) if operator-visible), and the master map ([`00_INDEX.md`](mfb-rdm-docs/00_INDEX.md) — bump **Last Updated**; the dated narrative goes in [`CHANGELOG.md`](CHANGELOG.md)).
- **Vocabulary / convention decisions are Data Office calls** informed by user input — never write "pending PI sign-off" or treat them as blocked-on-stakeholder.

## Git

- Write clear commit messages (what changed and why). **Stage specific files**, not `git add -A`. The repo holds large binaries (xlsx, docx) and `contacts.xlsx` — **don't stage these unless asked.** One commit per logical unit of work.

## Style

- Markdown; use existing conventions (status markers, cross-references, open-questions tables). Keep language **precise but accessible** — end users are researchers, not IT professionals. When in doubt about a design choice, **present options rather than picking one.** Windows path examples use backslash style (`J:\`). Full style guide: [`CONTRIBUTING-docs.md`](CONTRIBUTING-docs.md#style-conventions).
