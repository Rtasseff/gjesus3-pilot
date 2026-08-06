# NI `S:\gnuclear` — active-workspace layout finding

**Status:** REFERENCE — a read-only inventory of the **active working space** `S:\gnuclear` (the third,
least-standardized NI tier in [`equipment/historical_data_archives.md`](../historical_data_archives.md)).
**Captured:** 2026-06-25 (read-only, wrote nothing). **By:** Data Office.
**Why this exists:** the layout here is **materially different** from both the Molecubes live box and
the `gnuclear2$` `.tgz` archive — different enough that **neither existing NI ingest pipeline fits it**.
This file is the durable record of *what is actually on disk*, so the ingest plan
([`tasks/ni_gnuclear_active_space_plan.md`](../../tasks/ni_gnuclear_active_space_plan.md)) doesn't have
to be re-derived from scratch.

> **One-line takeaway.** `S:\gnuclear\<YYYY>\Jesus\<user>\…` is the **researchers' flattened
> analysis workspace**: **loose single-reconstruction DICOM *files*** named
> `<14digit>_<MODALITY>_<recon>.dcm`, intermixed with analysis derivatives (`.nii`, `.voi`, `.mat`,
> PMOD `.xlsx`, segmentations). There are **no `<14digit>_<MODALITY>/` anchor folders, no `recon_N/`
> subfolders, and no `.tgz`** — so `copy_ni_acquisition()` (which requires `recon_<idx>/`) cannot
> ingest it. A **new file-as-primary DICOM path** is required (see the plan).

---

## 1. Top structure (verified)

`S:\gnuclear` is reachable from the workstation (`/s/gnuclear` in Git Bash; **PowerShell is deny-ruled**
in the agent harness — use Git Bash POSIX paths). Years **2022–2026** each contain a **`Jesus\`** folder.

**User folders under each `…\Jesus\`:**

| Year | User folders under `Jesus\` |
|---|---|
| 2022 | `MOLECUBES\` — an **extra nesting level**, then `211217`, `Ana`, `IAZ_MJ`, `Libe`, `Marina` |
| 2023 | `Aitor_Herraiz`, `Ermal`, `Irati`, `Kepa`, `Libe`, `MJ`, `Marina` — **plus loose `*_CT_ISRA_0.dcm` files at the `Jesus\` root** |
| 2024 | `Alba`, `CarlottaS`, `Claire`, `Ermal`, `Irati`, `Irene`, `Itziar`, `MJ`, `Marina` |
| 2025 | `Carlotta`, `Claudia`, `Irene`, `Itziar` |
| 2026 | `Ekine`, `Itziar`, `Jordi`, `Ryan`, `irene` (lowercase) |

Notes:
- **Folder names are Capitalized and broader** than the box roster (which used lowercase
  `irene/claudia/ermal/aitor/itziar/carlotta/laura`). Case varies even within (`Irene` vs `irene`).
- Some users here (`Irati`, `Marina`, `Libe`, `Kepa`, `MJ`) were listed **out-of-MFB** in the live-box
  roster ([`live_machine_data_layout_and_sync_rules.md`](live_machine_data_layout_and_sync_rules.md) §2A),
  yet sit under `Jesus\` here → **scope rule needs confirmation** (everything-under-`Jesus\` vs allow-list).
- **Variable depth:** the 2022 `MOLECUBES\` extra level + loose-at-root `.dcm` in 2023 mean discovery
  must match by **recursive filename**, never a fixed depth.

## 2. What a leaf (subject) folder contains — the decisive finding

Example `…/2025/Jesus/Irene/0525/251028_FDG/0525_m1/`:

```
20251028101344_PET_OSEM_0.dcm        <- reconstructed PET volume (a loose FILE, not a folder)
20251028103111_CT_ISRA_0.dcm         <- reconstructed CT volume  (a loose FILE)
0525_m1_fdg.nii / 0525_m1_fdg_SEGM.nii / 0525_m2_fdg_SEGM.nii   <- analysis outputs (note: m2 leaks into m1's folder)
ID 1_pmod_cps_to_suv.xlsx, 0525_m1_correg.mat                   <- PMOD SUV table, coregistration
protocol.txt, reconparams.txt, monitoring.csv                  <- text aux (parseable for the sidecar)
```

Example `…/2024/Jesus/Ermal/240614/311/` — same shape, bare-number subject (`311`), plus `.voi`/`.xlsx`.

**Verified across all of 2024+2025 `Jesus\`:** `0` anchor directories matching
`[0-9]{14}_(PET|CT|SPECT|OI)`, `0` `recon_*` directories, `0` `.tgz`. The structure is uniformly flat.

This is the **curated working copy** — the one reconstruction the researcher actually used, flattened,
alongside their downstream analysis. It is **NOT** the acquisition-folder tree the box exposes nor the
`.tgz`-per-acquisition the archive holds (those keep all recons + raw event data + XML aux).

## 3. DICOM filename grammar (consistent)

```
^<14-digit timestamp YYYYMMDDhhmmss>_<MODALITY>_<recon>(_<idx>)?(_frameMULTI_iter30)?\.dcm$
```

Real examples: `20240115133604_PET_OSEM_0.dcm`, `20240115133604_PET_OSEM_1.dcm` (**two recons of one
scan**), `20240115134253_PET_OSEM_0_frameMULTI_iter30.dcm` (**dynamic PET**), `…_CT_ISRA_0.dcm`.

- The canonical **`(acq_datetime_full, modality)`** is recoverable **from each filename** → it is the
  acquisition key and the dedup identity.
- **One scan can have multiple recon `.dcm` files** (`_0`, `_1`, `frameMULTI`) → an ingest must **group
  them into one acquisition**, not one-acq-per-file (mirrors the box's one-anchor-many-recons).
- Modalities seen: **PET + CT only** (no SPECT/OI in the 2024+2025 sample).

## 4. Volume (distinct `(timestamp, modality)` acquisitions under `Jesus\`)

| Year | Distinct acqs | Note |
|---|---|---|
| 2022 | 449 | net-new |
| 2023 | 449 | net-new |
| 2024 | 483 | net-new |
| 2025 | 551 | **~132 overlap** the loaded `gnuclear2$` Irene/0525+1207 slice; Carlotta/Claudia/Itziar net-new |
| 2026 | 192 | net-new |
| **Total** | **~2,124** | **vs 132 currently in production → ≈ 2,000 net-new reachable now** |

(Raw `.dcm` counts are higher — 699 CT + 617 PET in 2024+25 alone — because of multiple recons per scan;
the table already collapses those to distinct acquisitions.)

## 5. Implications for ingest (summary — full plan separate)

1. **Neither existing NI pipeline fits.** `molecubes_ni_live.yaml` (live) and `molecubes_ni.yaml`
   (archive) both rely on `copy_ni_acquisition()` → needs `recon_N/`. Absent here.
2. **New file-as-primary DICOM path needed:** discover `*.dcm` by the filename anchor → **group by
   `(timestamp, modality)`** → new `copy_strategy` → lighter DICOM-header + `protocol.txt`/`reconparams.txt`
   extractor. **Downstream reused unchanged** (registry, packed `subject_ids`, subjects table, project
   link, `subject_parse`, per-animal DB lookup, locking, csv_safe).
3. **Canonical `(timestamp, modality)` dedup is mandatory** — both to reconcile with the 132 archive
   rows (the `(acq_date, original_name)` key in `tools/ingest/config.py` misses across sources) and to
   collapse multi-recon files into one acquisition.
4. **Fidelity is "working-layer", and that is on-role** ([`13_GJESUS3_ROLE`](../../mfb-rdm-docs/13_GJESUS3_ROLE.md)):
   gjesus3 wants the analysis-ready reconstruction; the platform archive (`gnuclear2$`/`gnuclear3`)
   stays the full source of truth (all recons + raw). Provenance records read source = `S:\gnuclear`.
5. **Open scope questions:** the `Jesus\`-as-scope vs allow-list question (§1), and whether to also
   capture the co-located analysis **derivatives** into the project workspace (a fast-follow).

## 6. How this was measured (reproducible, read-only)

From Git Bash on the workstation (`S:\` = `/s`):
- top + per-year + per-`Jesus\` directory listings (`ls -1`);
- layout probe: `find …/Jesus -maxdepth 6 -type d | grep -E '/[0-9]{14}_(PET|CT|SPECT|OI)$'` → none;
  `find … -iname 'recon_*'` → none; `find … -name '*.tgz'` → none;
- volume: `find …/<YYYY>/Jesus -name '*.dcm' | sed 's#.*/##' | grep -oE '^[0-9]{14}_(PET|CT|SPECT|OI)' | sort -u | wc -l`.

## 7. Related
- [`tasks/ni_gnuclear_active_space_plan.md`](../../tasks/ni_gnuclear_active_space_plan.md) — the ingest plan (PLAN status; execute after Ryan's review).
- [`equipment/historical_data_archives.md`](../historical_data_archives.md) — the source-location catalogue (the `S:\gnuclear` row points here).
- [`live_machine_data_layout_and_sync_rules.md`](live_machine_data_layout_and_sync_rules.md) — the box layout + §3A subject grammar + §2A roster (this workspace's subject folders parse with the SAME grammar).
- [`internal_ni_data_handling_workflow_notes.md`](internal_ni_data_handling_workflow_notes.md) — archive-mode (`gnuclear2$` `.tgz`) reality.
- `tools/ni_live_discover.py::parse_subject` — reusable subject parser; `tools/ingest/config.py::_build_dedupe_index` — the dedup key to extend.
