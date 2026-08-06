# Removal list — synthetic NI test data in true production (2026-06-29)

**Status:** HAND-OFF. Prepared 2026-08-06 by the `feat/ni-live-hardening` work; **not executed here**
because that branch is 69 commits behind `origin/main` and does not carry the side-effect inventory.
Execute from a machine on current `main`.

**Reference:** [`mfb-rdm-docs/10_TOOLS.md` §2.1 — *Side-effect inventory: everything an ingest writes
(audit and reversal reference)*](../mfb-rdm-docs/10_TOOLS.md) (10_TOOLS.md:424, on `main`). Row numbers
below map to that table.

---

## What this is

Two synthetic acquisitions written into `J:\gjesus3-data` (true production) on **2026-06-29T16:05:51Z**
by the end-to-end verification run for commit `53b022b` ("per-session corrections + tracer metadata").
The run used a synthetic source tree but passed `--nas-root J:\gjesus3-data` instead of a throwaway NAS.
`tasks/ni_live_operator_plan.md:39-43` records it as "throwaway nas" — that write-up is wrong, which is
why it went unnoticed for five weeks.

**Both ACQ-IDs:** `ACQ-20260212-CT-001`, `ACQ-20260212-CT-002`
**Identifying marks:** `original_name` = `1207/260212/0324_m61/20260212130722_CT/recon_0` (and `recon_1`);
`registration_datetime` = `2026-06-29T16:05:51Z` / `…:52Z`; `ingest_config` =
`tools/templates/instruments/molecubes_ni_live.yaml`; `notes` begins `Live-box NI sync: CT of`.
Payload is a **5-byte stub** `recon0.dcm` — no real image data. Total footprint ~64 KB.

**Not real data.** The `1207/260212/0324_m61` path does not correspond to a real scan; `file_size_mb` is
`0.0` and `file_count` is `1`.

---

## Removal steps

Take a registry backup first (`.bak.<timestamp>`, per the `migrate_registry_columns.py` pattern).
Every CSV edit must go through the BOM-tolerant / trailing-newline-safe helper
(`tools/ingest/csv_safe.py`) — do **not** hand-edit in Excel.

| # | Inventory row | Location | Action |
|---|---|---|---|
| 1 | #1 | `raw/DICOM/2026/2026-02/ACQ-20260212-CT-001/`<br>`raw/DICOM/2026/2026-02/ACQ-20260212-CT-002/` | Delete both folders (32 KB each; each holds `<ACQ-ID>.data/recon0.dcm`, `metadata.json`, `checksums.json`, `README.txt`) |
| 2 | #3 **commit point** | `registries/registry_raw.csv` | Remove the 2 rows keyed by the two `acq_id`s |
| 3 | #4 | `registries/ingest_manifest.csv` | Remove the 2 rows keyed by the two `acq_id`s |
| 4 | #5 | `registries/registry_subjects.csv` | Remove subject `61-AE-biomaGUNE-0325`. **Verified safe:** referenced by exactly these 2 acqs and no others; `created == last_updated == 2026-06-29T16:05:51Z`, so it was newly created, never gap-merged into an existing subject |
| 5 | #6 | `registries/pending_subject_metadata.csv` | Remove the 2 rows keyed by the two `acq_id`s (queued `pending-db` on a DB miss) |
| 6 | #7 | `projects/AE-biomaGUNE-0325/raw_linked/CT_0324_m61_20260212_20260212130722_recon0`<br>`…_recon1` | Delete both hard links |
| 7 | **not in the inventory — see gap below** | `registries/registry_projects.csv` | Remove `PROJ-0051` (`AE-biomaGUNE-0325`, *"Auto-created during live-box NI sync; animal protocol 0325. PROVISIONAL."*). **Verified safe:** referenced by exactly these 2 acqs and no others. Also remove the now-empty `projects/AE-biomaGUNE-0325/` folder **if** nothing else lives under it |
| 8 | #2 | `registries/.acq_id_seq.json` | Key `"ACQ-20260212-CT-": 2`. Per inventory row #2 ids are **never reused by design** — leaving the reservation is the default and is correct. Delete the key by hand **only** if you want the ids reusable, and only after steps 1–7 are complete |

---

## Two findings for the doc owner

1. **The side-effect inventory does not cover project auto-creation.** Row #7 of the inventory is
   conditioned on the project resolving to an **existing** project. This ingest **created** `PROJ-0051` +
   its `projects/<name>/` folder and appended to `registry_projects.csv` — a write path the audit/reversal
   reference does not list. Either the inventory needs an eighth row, or auto-create needs to be scoped so
   it cannot fire unannounced. Worth deciding before the next audit relies on that table.

2. **A `--nas-root` pointing at production is silently accepted for a synthetic source tree.** Nothing
   distinguished this run from a real one. A guard (confirmation prompt, or a `--i-know-this-is-production`
   style gate when `--nas-root` resolves to `J:\gjesus3-data`) would have prevented it. Suggest filing to
   `tasks/BACKLOG.md`.

---

## Verification after removal

```
grep -c "ACQ-20260212-CT-00" J:/gjesus3-data/registries/*.csv     # expect 0 everywhere
ls J:/gjesus3-data/raw/DICOM/2026/2026-02/ | grep 20260212-CT     # expect nothing
```
Then run `tools/validate_registries.py` to confirm referential integrity across the registry family.
