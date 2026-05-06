# Claude Code Instructions — gjesus3 RDM Pilot

## On Startup

1. Read [`tasks/tasks.md`](tasks/tasks.md) to understand current priorities and what to work on next
2. Update `tasks/tasks.md` as work progresses — mark items done, add new items as they emerge
3. For system design context, see [`mfb-rdm-docs/00_INDEX.md`](mfb-rdm-docs/00_INDEX.md) (master map) and [`mfb-rdm-docs/01_OVERVIEW.md`](mfb-rdm-docs/01_OVERVIEW.md) (scope and rationale)

## Project Type

This is a **design, documentation, and tooling project** for a research data management system. The primary deliverables are specifications in `mfb-rdm-docs/` and Python scripts in `tools/`. See [README.md](README.md) for project overview.

## Project Context

- **Organization:** CIC biomaGUNE (research institute, Spain)
- **Group:** MFB (led by PI Jesus Ruiz-Cabello)
- **Data Management Lead:** Ryan Tasseff (Data Office)
- **Infrastructure:** QNAP NAS "gjesus3" (TS-864eU, 6 × 20 TB, RAID 5, ~63 TB user-available after snapshot reservation), SMB share `\\GJESUS3\gjesus3`
- **Access:** Hardwired on-site machines only (no laptops)
- **Status:** Pilot — NAS structure deployed; collaborator DICOM (75 acqs) and Zeiss AxioScan 7 (.czi, 3 acqs) ingest pipelines running; YAML-driven config schema in `tools/configs/`

## Development Environment

- **Scripting/development:** Use WSL (Ubuntu) for building scripts, extraction, checksums, etc.
- **NAS mount in WSL:** `/mnt/gjesus3` via fstab drvfs (through Windows-mapped drive letter)
- **User-facing tools:** Write in Python (cross-platform) so Windows users can run them without WSL
- **User handles:** `sudo` commands for WSL setup

## Key Rules

### Documentation
- Core deliverables live in `mfb-rdm-docs/`. Use `00_INDEX.md` as the map.
- Always read relevant docs before suggesting changes.
- When updating one document, check for cross-reference impacts on others (see Cross-reference consistency below).
- **Never edit** files in `mfb-rdm-docs/depricated/` — they are historical records.

### Status markers
Respect these throughout the documentation:
- `DECIDED` — Do not change without explicit user instruction
- `DRAFT` — Can be refined, but flag substantive changes
- `GAP` — Information or decision needed; don't invent answers
- `EVALUATING` — Under active consideration; present options rather than making choices
- `INPUT NEEDED` — Waiting on stakeholder feedback; don't fill in assumptions

### Cross-reference consistency
When updating one document, check for impacts on others:
- `00_INDEX.md` — Key Decisions table and Key Gaps section
- `06_REGISTRIES.md` — registry schemas must match field references elsewhere
- `07_PROVENANCE.md` — referenced by `04_PUBLICATIONS.md` and `05_PROJECTS.md`
- `03_RAW_STORAGE.md` — instrument codes must match `09_MODALITIES.md` and `equipment/INDEX.md`
- `10_TOOLS.md` — YAML ingest schema; if you add/rename a `registry:` column or `discovered.*` source, update `06_REGISTRIES.md` (schema), `08_METADATA.md` (sidecar), and `tools/templates/ingest_template.yaml` together
- `08_METADATA.md` — `metadata.json` sidecar shape; the file written by `tools/ingest/metadata_sidecar.py` must match what's documented here

### Ingest configs
- Per-batch YAML configs live in `tools/configs/` (under git, version-locked with the scripts). Each row's `ingest_config` column records the relative path of the config that produced it.
- Starter template: `tools/templates/ingest_template.yaml` — copy and edit; never edit in place.

### Equipment reference
- `equipment/INDEX.md` is the starting point for in-scope imaging instruments.
- Two categories: **microscopes** (raw = direct instrument output) and **platform instruments** (raw = reconstructed images provided by the platform).

## Git Usage

- Write clear commit messages describing what changed and why
- Stage specific files rather than using `git add -A`
- Repo contains large binary files (xlsx, docx) in `shared/` and `contacts.xlsx` — avoid staging these unless asked

## Style and Conventions

- Documentation is written in Markdown
- Use existing document conventions (status markers, cross-references, open questions tables)
- Keep language precise but accessible — end users are researchers, not IT professionals
- When in doubt about a design choice, present options rather than picking one
