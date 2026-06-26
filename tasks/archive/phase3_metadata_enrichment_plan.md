# Phase 3 — Metadata Enrichment Writer: Implementation Plan (the one thread)

**Created:** 2026-06-03 · **Status:** 🟢 Ready to implement · **Owner:** Ryan + Claude

This is the single consolidated thread for the Phase 3 coding work — wiring the
three preclinical enrichment blocks into the ingest pipeline. Read this first
when picking up the metadata-writer work. Spec authority stays in
`mfb-rdm-docs/`; this doc is the build plan.

> **🤝 Handoff note.** Planning + specs are complete; **implementation is handed
> off to a separate session — nothing here is built yet** beyond `tools/animal_db.py`.
> The plan is grounded in a scan of the current pipeline (hook points in §5 are
> real), but the **open decisions in §10 (YAML field names, module placement,
> completeness-report timing) must be confirmed with Ryan at kickoff** before
> coding — they shape the schema. Nothing touches the live NAS until the staged
> dry-run in §8 step 7 passes. The non-blocking rule (§3.1) is non-negotiable:
> the writer must never raise on missing enrichment.

---

## 1. Where we are

| Piece | Status |
|---|---|
| **Phase 1** — animal-facility DB explored (`animal_facility` MariaDB; join + field map confirmed) | ✅ done |
| **Phase 2** — `tools/animal_db.py` read-only fetcher (verified live on Windows) | ✅ done |
| **Specs locked** — `subject:` (08_METADATA §4.4), `condition:` (§4.5), `anatomy:` (§4.6), **non-blocking model** (§4.7), Subject/Sample identity model (06_REGISTRIES §2.3) | ✅ done |
| **Phase 3** — wire the three blocks into ingest | ⬜ this plan |

Recent commits (all on `main`): `1bf206d` identity model · `928a032`/`4006da8`/`a01e3fe` animal_db.py · `b9bbbc1` anatomy block · `6b3499a` non-blocking model.

## 2. Goal

At ingest, write `subject:` + `condition:` + `anatomy:` into each acquisition's
`metadata.json` — auto-populating what we can, accepting what we can't, **never
blocking**. Operator supplies enrichment **once per batch/session**, not per scan.

## 3. Hard constraints (decisions the code must honour)

1. **Non-blocking (§4.7).** The writer NEVER raises on a missing enrichment field. Acquisition registers + sidecar writes regardless.
2. **Tri-state + sentinels.** `is_control` / `is_whole_body` ∈ `true | false | null` (null = unknown, the default). Free-text → `""`, `source` → `"unknown"`. Always written, never omitted. WARN when null/unknown.
3. **Set-once-per-batch, propagate down.** The per-batch YAML block applies to every acquisition the batch produces. Per-acq override only for genuinely mixed batches.
4. **Best-effort auto first:** `subject` from the DB (built); `condition.disease_model` seed from DB `projects.name` (weak — *future*); `anatomy.auto_hint` from MRI ProtocolName+FOV / NI bed-range (weak — *future*).
5. **Windows, single OS.** Fetch runs in-process on Windows; creds at `C:\Users\rtasseff\.my.cnf`. No-creds / off-network / animal-not-in-DB → `subject` deferred to the pending list (subject only); `condition`/`anatomy` just go `null` + WARN.
6. **Identity model (06 §2.3).** `subject.facility_animal_id` = reused `<animal_code>-AE-biomaGUNE-<NNNN>`; parse the instrument short code → `(project_alias, animal_code)`.

## 4. Already built — reuse, don't rebuild

`tools/animal_db.py`:
- `lookup(project_alias, animal_code) -> LookupResult` (`.status` found/not_found/unreachable; `.subject`; `.reason` db-miss/no-credentials). Fail-soft.
- Helpers: `normalize_species`/`normalize_sex`, `parse_subject_id`/`compose_subject_id`, **`age_iso8601(dob, acq)`** (the writer uses this to derive `age_at_acquisition`).

## 5. Pipeline hook points (confirmed by scan)

| File | Site | Role in Phase 3 |
|---|---|---|
| `tools/ingest_raw.py` | **Step 8.5** (~L941) `metadata_sidecar.build_sidecar(...)` → `write_sidecar(...)` | Orchestration: fetch subject, resolve condition/anatomy, pass dicts into `build_sidecar`. Keep DB calls HERE (ingest_raw already imports `animal_db` + `metadata_sidecar`). |
| `tools/ingest/metadata_sidecar.py` | `build_sidecar(...)` | Extend to accept `subject`/`condition`/`anatomy` dicts and nest them when present. **Stays DB-free** (pure assembler). |
| `tools/ingest/config.py` | `expand_batch` (~L322 case-stash) + `prep_single_case` (L538) | Parse + stash the new YAML (`subject_from_db`, top-level `condition:`/`anatomy:`/`subject:` blocks) onto each case — mirror how `auto_create_project` (`acp_block`) is carried. |
| `tools/ingest/resolver.py` | mirror `validate_auto_create_project_block` / `resolve_auto_create_project_block` (L155/L257) | Add `validate/resolve_condition_block` + `validate/resolve_anatomy_block` using the existing `resolve_value` engine (literal \| `discovered.X` \| `${...}` \| NA). |

## 6. Proposed YAML schema (CONFIRM before coding)

```yaml
auto_discover:
  subject_from_db: true                       # default false
  subject_lookup:                             # how to build the DB key
    project_alias: "${discovered.short_project}"   # else derive from project_hint ae-biomegune-NNNN
    animal_code:   "${discovered.short_sample}"    # parsed: m14->14, m13->13, ID13B->13 (+organ B)

# top-level peers to registry: / auto_create_project: — resolver-evaluated, set once per batch
condition:
  is_control:    true            # tri-state; omit -> null=unknown
  disease_model: "wild_type"
  disease_state: "baseline"

anatomy:                          # only meaningful for sample_type=organism
  is_whole_body: false           # tri-state; omit -> null
  region: { label: "brain", ontology: "UBERON", id: "UBERON:0000955" }

subject:                          # OPTIONAL operator override (overrides DB; source=operator-entered)
  species: "Mus musculus"
  # ...
```

**Animal short-code parser** (new small helper — propose `tools/ingest/subject_id.py`):
`parse_animal_short_code("ID13B") -> (animal_code=13, organ="B")`; strips instrument decoration
(`m`/`ID` prefix, trailing organ letters); `project_alias` from `short_project` or by stripping
`ae-biomegune-` off `project_hint`; then `animal_db.compose_subject_id`.

## 7. Writer logic (per block, all WARN-not-raise)

- **subject** (when `subject_from_db` and `sample_type ∈ {organism, tissue}`):
  1. Operator `subject:` YAML block present → use it (`source: "operator-entered"`).
  2. Else parse short code → `animal_db.lookup()`:
     - `found` → subject block, derive `age_at_acquisition = age_iso8601(dob, acq_datetime)`, `source: "animal-facility-db"`.
     - `not_found`/`unreachable` → **placeholder** block (`source: "pending-db"`, required fields blank) + **append `registries/pending_subject_metadata.csv`** + WARN. Ingest continues.
- **condition** (when `sample_type ∈ {organism, tissue}`): resolve `condition:` block → `is_control` tri-state (default `null` + WARN), free-text default `""`. `source` per origin.
- **anatomy** (when `sample_type = organism`): resolve `anatomy:` block → `is_whole_body` tri-state (default `null` + WARN), `region` optional.

## 8. Work breakdown (sequenced)

1. [ ] **Short-code parser** `tools/ingest/subject_id.py` (+ inline self-checks): `m14→14`, `ID13B→13,B`, alias from project_hint. Reuse `animal_db.compose_subject_id`.
2. [ ] **YAML parse/stash** in `config.py` (`subject_from_db`+`subject_lookup`; top-level `condition:`/`anatomy:`/`subject:`) — both `expand_batch` and `prep_single_case`.
3. [ ] **Resolvers** in `resolver.py` (`condition`/`anatomy` block resolve+validate, mirror acp).
4. [ ] **`build_sidecar` extension** (metadata_sidecar.py) — accept + nest the three dicts.
5. [ ] **Step 8.5 orchestration** (ingest_raw.py) — fetch/resolve/write, WARN-not-raise, sentinels, `age_iso8601`.
6. [ ] **Pending-list writer** `tools/ingest/pending.py` (or in `registry.py`) — append `pending_subject_metadata.csv`, idempotent on `acq_id`, defensive header.
7. [ ] **Dry-run + real test** on a STAGED batch (e.g. `D:\projects\gjesus3\data_test\`), NOT the live NAS: verify three blocks present; miss-path → pending-db + pending row + WARN + ingest still succeeds; null sentinels correct.
8. [ ] **Templates + 10_TOOLS** — add the blocks to `mri_bruker.yaml` / `molecubes_ni.yaml` (+ `axioscan7.yaml` subject-only); document the schema in `10_TOOLS §2.1`.

## 9. Out of scope for Phase 3 (tracked, deferred)

- **Auto-hints** — `condition.disease_model` seed from `projects.name`; `anatomy.auto_hint` from FOV/bed-range. Fast follow.
- **`tools/recover_subject_metadata.py`** (superuser retro-update into `/raw/`). Phase 3.5.
- **Metadata-completeness report** (`tools/metadata_completeness.py`) — read-only gap list. Ship near Phase 3 but separable.
- **Excel → study-metadata importer** — the bulk-fill tool. Separate stream.
- **Registry `subject_id` / `anatomical_entity` columns** — deferred to the true-production restart.
- **Phase 4 backfill** of the existing 365+ acqs.

## 10. Open decisions to confirm before coding

1. The **YAML field names** in §6 (esp. `subject_lookup.project_alias` / `animal_code` and the parser's strip rules).
2. **Module placement:** `subject_id.py` parser + `pending.py` writer as new `tools/ingest/` modules (recommended) vs folding into `resolver.py` / `registry.py`.
3. Whether to include the **completeness report** in this phase or immediately after.
