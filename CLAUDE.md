# Claude Code Instructions — gjesus3 RDM Pilot

## Project Type

This is a **design and documentation project**, not a software project. The primary work is writing, reviewing, and refining specifications for a research data management system. See [README.md](README.md) for project overview.

## Key Rules

### Documentation is the deliverable
- The core deliverables live in `mfb-rdm-docs/`. Treat these documents with care — they represent the current state of design decisions, open questions, and stakeholder agreements.
- Always read relevant documentation before suggesting changes. Understand existing decisions and their rationale.
- When making changes, update all affected documents — decisions and conventions often span multiple files. Use `mfb-rdm-docs/00_INDEX.md` as the map.

### Do not modify deprecated files
- Files in `mfb-rdm-docs/depricated/` are historical records. **Never edit them.** They exist to show how the design evolved and provide context for current decisions.

### Respect decision status markers
The documentation uses explicit status markers. Respect them:
- `DECIDED` — Do not change without explicit user instruction
- `DRAFT` — Can be refined, but flag substantive changes
- `GAP` — Information or decision needed; don't invent answers
- `EVALUATING` — Under active consideration; present options rather than making choices
- `INPUT NEEDED` — Waiting on stakeholder feedback; don't fill in assumptions

### Cross-reference consistency
When updating one document, check for impacts on others. Common cross-cutting concerns:
- `00_INDEX.md` — Key Decisions table and Key Gaps section
- Registry schemas in `06_REGISTRIES.md` must match field references elsewhere
- Provenance format in `07_PROVENANCE.md` is referenced by `04_PUBLICATIONS.md` and `05_PROJECTS.md`
- Instrument codes in `03_RAW_STORAGE.md` must match `09_MODALITIES.md`

## Git Usage

This project uses a local git repository. When asked to commit:
- Write clear commit messages describing what changed and why
- Stage specific files rather than using `git add -A`
- The repo may contain large binary files (xlsx, docx) in `shared/` and `contacts.xlsx` — be aware of this when staging

## Project Context

- **Organization:** CIC biomaGUNE (research institute, Spain)
- **Group:** MFB (led by PI Jesus Ruiz-Cabello)
- **Data Management Lead:** Ryan Tasseff (Data Office)
- **Infrastructure:** QNAP NAS "gjesus3" (~100 TB, RAID 5)
- **Access:** Hardwired on-site machines only (no laptops); includes instruments and some workstations
- **Scope:** Archival storage for microscopy and biomedical imaging data
- **Status:** Pilot design phase — system not yet deployed

## Style and Conventions

- Documentation is written in Markdown
- Use the existing document conventions (status markers, cross-references, open questions tables)
- Keep language precise but accessible — end users are researchers, not IT professionals
- Avoid over-specifying things that are still under discussion
- When in doubt about a design choice, present options rather than picking one
