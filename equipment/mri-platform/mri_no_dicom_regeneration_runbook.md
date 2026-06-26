# Runbook — MRI sessions with NO DICOM files (ParaVision → DICOM regeneration)

> **Runbook** (this file): the step-by-step operator procedure for the specific case of a ParaVision MRI
> exam that arrives **without DICOMs**. For the broader picture, see the sibling docs in this folder:
> [`internal_mri_data_handling_workflow_notes.md`](internal_mri_data_handling_workflow_notes.md)
> (**workflow notes** — the full MRI workflow + gjesus3 integration),
> [`mri_data_access_strategy.md`](mri_data_access_strategy.md) (**strategy** — how we reach the platform),
> and [`mri_platform_description.md`](mri_platform_description.md) (**platform description** — hardware).

**Status:** ✅ Official operator procedure (DECIDED 2026-06-01; validated visually against Bruker GUI export). This is
the canonical "how to" for the historical MRI pull. The design trail + bug analysis is summarized in
[`tasks/STATUS.md`](../../tasks/STATUS.md); the in-context workflow note is in
[`internal_mri_data_handling_workflow_notes.md`](internal_mri_data_handling_workflow_notes.md) (§ "ParaVision → DICOM
regeneration via Dicomifier").

> **One-line:** when a Bruker/ParaVision MRI exam reaches us **without DICOMs** (the researcher never ran Bruker's GUI
> exporter), the ingest **regenerates the DICOMs from the raw `2dseq` + JCAMP-DX files using Dicomifier**, applies two
> mandatory image-correctness fixes, and deposits them into `/raw/<ACQ-ID>.data/` exactly like a normal MRI ingest.
> You turn it on with **one YAML flag** and run the ingest **from WSL with one conda env active**.

---

## 1. When you need this

A ParaVision exam folder that has **no `pdata/<idx>/dicom/*.dcm`** anywhere — only the raw `fid`, `2dseq`, and the
JCAMP-DX aux files (`acqp` / `method` / `visu_pars` / `subject`). This happens when the researcher skipped Bruker's
ParaVision GUI DICOM exporter before FTP'ing the data off. In the round-6 inventory, **3 of 7 source projects** were in
this state (m13/m14 protocol 0423 + m29 protocol 0423).

You do **not** need this for normally-exported exams — those already have DICOMs and ingest unchanged. The regeneration
**only fires when DICOMs are absent** and the flag is on; the same config handles both cases in one batch.

---

## 2. What the procedure does (overview)

```
source exam with no DICOMs
   └─ ingest detects "no pdata/<idx>/dicom/*.dcm"  (ingest_raw.copy_mri_paravision)
       └─ paravision_regen.prepare_virtual_exam():
            • runs Dicomifier 2.5.3  (2dseq + JCAMP-DX → per-frame DICOMs)
            • applies the two PV-7 image fixes (§4) to every regenerated DICOM
            • builds a "virtual exam" in a temp dir that looks like a normal Bruker-GUI export
       └─ normal slim copy proceeds → DICOMs land in /raw/<ACQ-ID>.data/ as recon<X>_frame<NN>.dcm
       └─ checksums + registry row + project hard-link, same as any MRI acquisition
```

Idempotent: re-running skips already-populated acquisitions and only fills in the ones still missing DICOMs. Temp scratch
is auto-cleaned. If Dicomifier is unavailable or a regen fails, the ingest logs a WARN and falls through to the existing
**empty `.data/` placeholder** (no batch abort) — you can re-run later once the env is in place.

---

## 3. The two image fixes — why the regenerated images display correctly

Dicomifier on ParaVision 7.0.0 has two confirmed bugs. Both are worked around **per file** inside
[`tools/ingest/paravision_regen.py`](../../tools/ingest/paravision_regen.py); you don't do anything by hand — this
section is so you understand and trust the output.

| # | Bug (raw Dicomifier output) | Symptom in a viewer | Fix applied |
|---|---|---|---|
| 1 | **PixelSpacing axis-order** — emits `[col, row]` instead of DICOM Part 3's `[row, col]` | image **stretched horizontally / squished vertically** (real geometric distortion) | **swap** `PixelSpacing[0]`↔`[1]` (deterministic; no-op for square matrices). Confirmed on 16/16 anisotropic m17 series. |
| 2 | **Invalid Window tags** — emits `WindowWidth=0` (PS3.3 requires width > 0) | **gray cast**, low contrast (viewer shows the full int16 range) | **delete** the bogus `WindowCenter`/`WindowWidth`; set `SmallestImagePixelValue` + `LargestImagePixelValue` from the pixel array min/max (Bruker's convention) → high-contrast B&W |

A third, cosmetic quirk is also handled: Dicomifier **transposes `SeriesDescription` ↔ `ProtocolName`** vs Bruker. The
sidecar extractor (`_DICOM_CURATED_TAGS`) carries **both** fields, so nothing is lost.

**Pixel data is identical** to Bruker (verified same int16 min/max/mean/std) — these are metadata-only fixes.
**Visually verified 2026-06-01:** both fixes applied renders identically to the Bruker GUI export (m17 exam 29 / pdata/3
cardiac CINE). The canonical `StudyInstanceUID` / `SeriesInstanceUID` round-trip **exactly** — XNAT/PACS/OMERO treat a
regenerated study as the same study a Bruker export would produce.

---

## 4. One-time setup — Dicomifier in WSL

**Why WSL?** Dicomifier is a Linux/conda tool. Even though our ingest is normally run on Windows, the **conversion
subprocess** needs a Linux conda env. This is expected — running the regen ingest from WSL (Ubuntu) with the env active is
the intended workflow. Everything except the `dicomifier` call is the same cross-platform Python.

In WSL (Ubuntu), with conda/miniforge on PATH:

```bash
# Create the env from the committed spec (one time)
conda env create -f tools/dicomifier-pilot.environment.yml
#   (equivalent to the original manual: conda create -n dicomifier-pilot -c conda-forge dicomifier pydicom)

# Verify
conda activate dicomifier-pilot
dicomifier --version            # expect 2.5.3 or later
```

Env spec: [`tools/dicomifier-pilot.environment.yml`](../../tools/dicomifier-pilot.environment.yml). The NAS is reached at
`/mnt/gjesus3` inside WSL (the same `J:\` mapped drive).

### 4a. WSL environment notes (read before a large run)

These are the WSL-specific gotchas the historical pull surfaced:

1. **Animal-DB credentials AND the `pymysql` driver must be visible to WSL.** Subject
   enrichment reads MariaDB credentials from `GJESUS3_MYCNF` (else `~/.my.cnf`) and
   connects via **`pymysql`**. `animal_db.credentials_available()` returns True only when
   **both** are present. Two ways this silently breaks in WSL, each sending **every
   subject to `source: "pending-db"`** (recoverable later, but you back-fill thousands):
   - **Missing driver.** `pymysql` is **not** in the base `dicomifier` conda env. It is now
     pinned in [`tools/dicomifier-pilot.environment.yml`](../../tools/dicomifier-pilot.environment.yml)
     (added 2026-06-14 after the historical MRI regen pilot wrote ~thousands of pending-db
     rows for this exact reason). If you built the env before that, run once:
     `conda activate dicomifier-pilot && pip install 'pymysql>=1.1'`.
   - **Creds file not found.** Inside WSL, `~/.my.cnf` is the **WSL** home, not your Windows
     home — if it's not there, export the path before the run:
     ```bash
     export GJESUS3_MYCNF=/mnt/c/Users/<you>/.my.cnf   # or wherever your .my.cnf lives
     ```
   The ingest prints a one-time **WARN** at batch start if credentials/driver aren't found
   and the batch needs them — heed it before letting a big run proceed. Verify quickly with
   `python -c "from ingest import animal_db; print(animal_db.credentials_available())"` (run
   from `tools/`, env active) → must print `True`.

2b. **Project hard-links must be created from Windows afterward.** `os.link` is refused
   (`EPERM`) over the CIFS NAS mount from WSL, so a regen run deposits `/raw/` correctly but
   leaves **empty project link-folder shells**. After the WSL run, from **Windows** (`J:\`,
   where `os.link` works) run [`tools/relink_mri_regen.py`](../../tools/relink_mri_regen.py)
   `--nas-root J:/gjesus3-data` (dry-run first) to fill them — it is idempotent and rebuilds
   the discovered-dependent link names from the registry + sidecar.

2. **NAS copy is timestamp-tolerant (no action needed).** WSL mounts the NAS as a CIFS
   share that disallows setting file timestamps; the ingest copies file bytes and
   preserves timestamps *best-effort* (integrity is still guaranteed by the sha256
   verify). This previously crashed the copy mid-run — it no longer does.

3. **Spectroscopy / calibration scans are auto-skipped, not regenerated.** Acquisitions
   whose method is **STEAM / PRESS** (MR spectroscopy) or **Wobble** (tuning) are *not*
   image data, so DICOM regeneration does not apply. The ingest detects them, logs a
   **WARN**, writes the empty `.data/` placeholder, and moves on (no crash). These need
   a **separate ingest path** (tracked in `tasks/BACKLOG.md`) — they are expected to
   show up as skipped, not as failures.

---

## 5. Step-by-step

1. **Stage the source data.** Pull the ParaVision study folders into a staging directory (e.g. via `tools/ftp_mirror.py`
   or the historical-pull staging path). Each exam keeps its native ParaVision shape (`acqp`/`method`/`visu_pars`/`subject`
   + `pdata/<idx>/2dseq`); the missing piece is just `pdata/<idx>/dicom/`.

2. **Make the batch config.** Copy the per-instrument template
   [`tools/templates/instruments/mri_bruker.yaml`](../../tools/templates/instruments/mri_bruker.yaml) to
   `tools/configs/mri_bruker_<batch>.yaml`, set `auto_discover.staging_dir` + `notes`, and **turn the flag on** in the
   `ingest:` block:

   ```yaml
   ingest:
     # ... existing MRI settings (acquisition_layout: folder, copy_strategy: mri_paravision_v2, reconstructions: all) ...
     auto_regenerate_dicom: true     # regenerate DICOMs for any no-DICOM exam in this batch
   ```

   (See `tools/configs/mri_bruker_20251016_TEST.yaml` for a worked example.)

3. **Activate the env (WSL).**
   ```bash
   conda activate dicomifier-pilot
   ```

4. **Dry-run first** (writes nothing; shows which exams will regenerate vs. already have DICOMs vs. will dedupe-skip):
   ```bash
   python tools/ingest_raw.py --config tools/configs/mri_bruker_<batch>.yaml --nas-root /mnt/gjesus3 --dry-run
   ```
   Look for the per-exam line `auto_regenerate_dicom: true (no-DICOM exams will be regenerated)` and confirm the count of
   exams to regenerate matches what you expect.

5. **Run it live** (drop `--dry-run`):
   ```bash
   python tools/ingest_raw.py --config tools/configs/mri_bruker_<batch>.yaml --nas-root /mnt/gjesus3
   ```

6. **Verify the output** (the post-ingest sanity check):
   ```bash
   python tools/validate_dicomifier_pixelspacing.py \
       /mnt/gjesus3/raw/DICOM/<year>/<year-month>/<ACQ-ID>/<ACQ-ID>.data
   ```
   **PASS** = every anisotropic series reads `matches_unswapped` (Bruker-correct `[row, col]`) and **none** read
   `matches_swapped`. Then spot-check one acquisition in a viewer (3D Slicer / ITK-SNAP): correct proportions + high-contrast
   B&W = both fixes worked.

---

## 6. Behaviour reference

| Situation | What happens |
|---|---|
| Exam already has DICOMs | Ingested normally — regen never fires (the flag is a no-op for it). |
| Exam has no DICOMs, flag **on**, Dicomifier present | DICOMs regenerated + fixed + deposited. |
| Exam has no DICOMs, flag **on**, Dicomifier **missing or regen fails** | WARN logged; **empty `.data/` placeholder** written; **no abort**. Re-run later once the env is fixed. |
| Exam has no DICOMs, flag **off** | Empty `.data/` placeholder (the default round-6 behaviour). |
| Re-running the same config | Idempotent — already-populated acquisitions dedupe-skip; only still-empty placeholders get filled. |

---

## 7. Files & references

- **Conversion module:** [`tools/ingest/paravision_regen.py`](../../tools/ingest/paravision_regen.py) — Dicomifier wrapper + the two PV-7 workarounds + flat→`pdata` mapping.
- **Ingest wiring:** `tools/ingest_raw.py::copy_mri_paravision` (the `auto_regenerate_dicom` kwarg; detection at the `_has_any_dicoms` check).
- **Verify tool:** [`tools/validate_dicomifier_pixelspacing.py`](../../tools/validate_dicomifier_pixelspacing.py) — pass it the ingested `<ACQ-ID>.data/` folder(s).
- **Env spec:** [`tools/dicomifier-pilot.environment.yml`](../../tools/dicomifier-pilot.environment.yml).
- **Template / config:** `tools/templates/instruments/mri_bruker.yaml` (commented opt-in block) · `tools/configs/mri_bruker_20251016_TEST.yaml` (worked example).
- **Metadata extractor:** `tools/ingest/paravision_metadata.py` (builds the `metadata.json.mri` block from JCAMP-DX).
- **Design trail + full bug analysis:** [`tasks/STATUS.md`](../../tasks/STATUS.md) (the no-DICOM/regeneration line; findings 1 / 1b / 2; the 16/16 validation; commit log `0e9d61b` → `5b02ef2`).
- **CLI setup notes:** [`tools/INGEST_CLI.md`](../../tools/INGEST_CLI.md).
