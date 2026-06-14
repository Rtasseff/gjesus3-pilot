# Operator runbook — anatomy back-fill (MRI + microscopy)

Fill the `anatomy.region` (UBERON) on **already-ingested** acquisitions whose
anatomy was left null, so the archive is searchable by body region. Two tools,
same safe shape. **Run the dry-run, eyeball it, then `--apply`.** Nothing is
written without `--apply`; runs are idempotent (only fill *unset* acqs), atomic
(temp-file + verify-after-write), and also patch the registry `anatomical_entity`
column. Future ingests auto-derive anatomy the same way — this is only for the
backlog of already-ingested data.

> Run these from the workstation that has the NAS mapped (`J:/gjesus3-data`).
> `--apply` writes to `/raw/` sidecars + the registry, so do the dry-run first.

---

## 1. MRI anatomy (Bruker / ParaVision)

Fills `anatomy.region` + `is_whole_body` from the **scan name** (SeriesDescription /
sequence). High-confidence mapping (`tools/ingest/anatomy_derive.py`): heart
(4-chamber / long-axis / short-axis / cardiac / ventricle), named vessels
(MPA→pulmonary artery, aorta, carotid), brain, abdomen. Setup/localizer scans,
bare cine, unnamed velocity-maps, FLASH/RARE → left null on purpose.

**The Jesús-group one-time override** (run it WITH the other back-fills): in that
group's cardiac-flow archive the bulk scan is a bare cine-FLASH (`Cine_IG_FLASH`)
that the high-confidence rule correctly leaves null. The one-time override file
`tools/configs/mri_anatomy_override_2026-06.yaml` maps it → heart (that group
only; not a permanent code rule). Use `--override` for the Jesús MRI back-fill:

```bash
# dry-run (preview only) — Jesús MRI:
python tools/backfill_mri_anatomy.py --nas-root J:/gjesus3-data \
    --override tools/configs/mri_anatomy_override_2026-06.yaml

# apply, once the dry-run looks right:
python tools/backfill_mri_anatomy.py --nas-root J:/gjesus3-data \
    --override tools/configs/mri_anatomy_override_2026-06.yaml --apply
```

For other groups' MRI, omit `--override` (high-confidence only). Latest dry-run
(Jesús MRI, ~10,300 acqs): **5,217 would fill** (heart 4,678, pulmonary artery
497, aorta 42), the rest left null. Scope with `--project PROJ-XXXX` or
`--acq-id ACQ-...` if you want to do it in batches.

---

## 2. Microscopy anatomy (AxioScan 7 / ZWSI; Cell Observer / LSM later)

Fills `anatomy.region` from the **sample-id organ code** in the `.czi` name
(`ID12Lu`→lung, `ID29H`→heart, `mPCLS`→lung). The vocabulary is
**operator-specific**, so the map is keyed by operator (AUA vs MBC) and lives in
an editable reference file — `tools/reference/microscopy_organ_map.yaml` (data,
not code; the SAME map the live ingest uses).

```bash
# dry-run (preview only):
python tools/backfill_microscopy_anatomy.py --nas-root J:/gjesus3-data

# apply, once the dry-run looks right:
python tools/backfill_microscopy_anatomy.py --nas-root J:/gjesus3-data --apply
```

Latest dry-run (~146 ZWSI acqs): **88 would fill** (heart 57, lung 31), 58 left
null (AUA `T`=tumor + bare-numeric ids — intentionally null: a tumor's host organ
varies). To add/correct a code (e.g. confirm a new operator's letters), **edit
`tools/reference/microscopy_organ_map.yaml`** and re-run — no code change.

---

## What "left null" means (both tools)
A null region is correct, not a failure: the code is ambiguous/unmapped, so we
record "unknown" rather than guess (a wrong label is worse than a missing one).
Add the mapping (edit the override / organ-map YAML) once an operator confirms,
then re-run `--apply` (idempotent — it only fills the still-null ones).

## Reference
- MRI mapping/code: `tools/ingest/anatomy_derive.py`; override: `tools/configs/mri_anatomy_override_2026-06.yaml`
- Microscopy map: `tools/reference/microscopy_organ_map.yaml`
- Spec: [`mfb-rdm-docs/08_METADATA.md` §4.6](../mfb-rdm-docs/08_METADATA.md)
- CLI reference: [`tools/INGEST_CLI.md`](INGEST_CLI.md)
