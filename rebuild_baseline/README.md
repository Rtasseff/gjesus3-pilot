# `rebuild_baseline/` — HISTORICAL snapshot, not current state

> ⚠️ **These CSVs are a point-in-time backup from the 2026-06-02 exhibit-dataset
> rebuild. They are NOT the live registry and their schema is out of date — do
> not treat them as current or feed them to tooling that expects the current
> header.**

- **`registry_raw.csv`** here has the **pre-restart 24-column header**. The live
  schema is **28 columns** (`sample_organism` / `subject_ids` / `anatomical_entity`
  added at the 2026-06-10 true-production restart, plus the `operator` re-add and
  the `researcher` rename). `assert_header_compatible` will (correctly) refuse to
  append to a file with this old header — that is the guard working, not a bug.
- The authoritative current registry lives on the NAS at
  `\\GJESUS3\gjesus3\gjesus3-data\registries\registry_raw.csv`; the current schema
  is defined by `REGISTRY_FIELDS` in [`tools/ingest/registry.py`](../tools/ingest/registry.py)
  and documented in [`mfb-rdm-docs/06_REGISTRIES.md`](../mfb-rdm-docs/06_REGISTRIES.md).

Kept only as a recovery/reference artifact of the rebuild. See
[`CHANGELOG.md`](../CHANGELOG.md) (2026-06-02) for context.
