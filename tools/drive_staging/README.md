# `tools/drive_staging/` — copy a one-copy source drive to local disk

For historical data that arrives on an **external drive that is the only copy**
and has to go back to its owner. The drive is read **once**, the SHA-256 is
computed from the same bytes as they are read, and the copy is then verified from
the local disk alone. So the drive can be unplugged and returned as soon as the
copy pass ends, before verification starts.

This is **pre-ingest staging**. It never touches the NAS. Once a drive is staged
and verified, its `files\` tree is a normal local staging source for
`ingest_raw.py` / the operator GUI.

*Adopted 2026-09-28 from `D:\projects\gjesus3\staging\_tools\` (`stage_copy` 1.1,
2026-09-22), where it was written for the historical microscopy drives. The
files here are byte-identical to that copy.*

| File | Admin? | What it does |
|------|--------|--------------|
| **`lock_usb.ps1`** | yes | Run **before** plugging the drive in. Turns off automatic mounting, waits for the drive, sets the whole disk read-only and checks that it took, and only then mounts it with a drive letter. Also logs model, serial, and SMART. `-Restore` turns automatic mounting back on after the last drive. |
| **`wait_for_drive.ps1`** | no | Waits for a newly plugged-in volume and reports what it is. Use it when you have no admin rights (the drive is then **not** locked read-only). |
| **`stage_copy.py`** | no | `inventory` → `copy` → `verify`, below. |

## Running it

Copy this folder onto the **local staging disk** and run it from there, not from
the repo. `lock_usb.ps1` writes `lock_usb.log` next to itself, and a staging run
has to keep going while the repo is being edited. Give each drive its own output
folder, for example `D:\projects\gjesus3\staging\drive1_<label>_<id>\`.

```
python stage_copy.py inventory E:\ D:\...\staging\drive1_<label>   # metadata only: inventory.csv + summary.txt
python stage_copy.py copy      E:\ D:\...\staging\drive1_<label>   # E:\ -> <out>\files, manifest.csv (resumable)
python stage_copy.py verify        D:\...\staging\drive1_<label>   # re-hash <out>\files against manifest.csv
```

- **`inventory`** reads metadata only. `summary.txt` says whether the drive fits
  on the destination and estimates the copy time. Run it first.
- **`copy`** is resumable. Re-running it copies only what is not yet in
  `manifest.csv` with the same size and mtime. It does **not** retry reads: a
  failing file goes to `errors.csv` and is skipped, so a weak drive is not
  hammered. Re-run to retry just those files.
- **`verify`** needs only the destination. Its last line is `VERIFY PASS` or
  `VERIFY FAIL`, and any problems are listed in `verify_problems.csv`.
- It keeps Windows awake while it runs (no admin needed).

## What to know before trusting a staged copy

- **Without `lock_usb.ps1` the drive is not write-protected.** Windows still
  updates last-access times as files are read. That is why `inventory` records
  the original times first.
- **Modification times are restored; creation times cannot be.** Both are
  recorded in `manifest.csv` (`mtime`, `birthtime`). An ingest that dates
  acquisitions from file times must read the manifest, not the copy.
- **`Unreadable entries` in `summary.txt` means the walk could not read
  something** (a folder or a file's metadata). Those entries are never copied.
  Check them in `inventory.csv` (type `E`) before the drive goes back.
- `lock_usb.ps1` treats **C: and D:** as the system disks it must never touch.
  On another workstation, check that line first.

## Per-file catalog (`catalog.py`)

*Added 2026-09-29.* Once a drive is staged and verified, `catalog.py` says what each file **is**, from its own
bytes, before anything is ingested. It reads the manifests (never the source drive) and writes to
`<staging>\_analysis\catalog\`; that folder is on the un-backed-up local disk, so everything in it is
regenerable from this script.

```
python catalog.py production   # NAS registry + every checksums.json -> production_hashes.csv, production_instrument_audit.csv
python catalog.py probe        # .czi / .tif / .lsm / .dcm headers -> probe.jsonl              (resumable)
python catalog.py archives     # list + stream-hash every archive member -> archive_*.jsonl   (resumable)
python catalog.py assemble     # files.csv archives.csv archive_members.csv dup_groups.csv summary.md
python catalog.py all
```

- **Read-only.** Nothing is written under a staged `files\` tree or to the NAS. Nothing is extracted, except one
  `.7z`/`.rar` at a time into `_analysis\catalog\_tmp\` (deleted after hashing). Zip members are stream-hashed.
- **The instrument comes from the device serial and stand keys, never the stand name or ZEN's `System` field or the
  folder.** The rules are data, in [`../reference/microscopy_instruments.yaml`](../reference/microscopy_instruments.yaml),
  with the evidence; `catalog.py` and the ingest read the same file.
- **One row per file** (`files.csv`, keyed `(drive, relpath)`) with class, sha256, `dup_n` (loose copies across both
  drives), `in_production` (ACQ-IDs whose `checksums.json` holds the same sha256 — never matched by name), the `.czi`
  fingerprint, TIFF/LSM tags and DICOM header fields. DICOM patient name / birth date are reduced to Y/N flags.
- `summary.md` is written **last**; its presence means `files.csv` is complete. It carries the error tally of
  every pass. `probe` and `archives` append as they go, so a stopped run resumes where it left off.
- The findings that came out of the first run are in [`../../tasks/drives_catalog_findings.md`](../../tasks/drives_catalog_findings.md).
- Tests (synthetic `.czi`, no disk or NAS needed): `python tools/test_drive_catalog.py`.

## Project claims (`project_claims.py`)

*Added 2026-09-29.* The companion to the catalog. The catalog says what each file **is**; this
says which project, researcher and animal its **path** claims. Every claim is checked against the
animal-facility DB (read-only) and sorted into **Confirmed**, **(A)** corrected typo, **(B)**
`Project-NNNN` or **(C)** uncertain, following the 2026-09-29 rule in
[`../../CHANGELOG.md`](../../CHANGELOG.md). Outputs go to `<staging>\_analysis\codes\`, keyed
`(drive, relpath)` like `files.csv`.

```
python tools/drive_staging/project_claims.py              # full run (~2 min once archives are cached)
python tools/drive_staging/project_claims.py --relist     # re-list archive members (slow: LEONE.zip)
python tools/drive_staging/project_claims.py --fresh-db   # ignore the DB lookup cache
```

- **A code that resolves in the DB is not enough.** The file's animals, and the DB's own birth and
  procedure dates, have to agree with it. Nested claims that disagree are decided by procedure
  dates, or they go to (C).
- **Every rejected number is logged** in `rejected_tokens.csv`: dates, animal numbers, counters and
  numbered series. Those are the misreads that produced 21 fabricated codes in the 2026-08 NI pull.
- **The drive label is spelled differently in the two tables:** `drive1`/`drive2` here, `D1`/`D2`
  in the catalog.
- The review document from the first run, with the approvals it needs, is
  [`../../tasks/drives_project_codes_findings.md`](../../tasks/drives_project_codes_findings.md).
- **Histology tie-break (2026-09-30, Ryan's approval of 2026-09-29).** When a file's animal is in two
  candidate protocols and neither rule above separates them, a microscopy file is settled by the one
  candidate whose animal had `Organ sampling` / `Perfusion` on or before the file date. The rule may
  only confirm the file's nearest claim, never overrule it, and it is not applied to in-vivo data.

## The `.czi` ingest (`ingest_plan.py`, `ingest_check.py`, `ingest_verify.py`)

*Added 2026-09-30.* Turns the catalog and the claims into a per-file ingest. One-time tools for the
historical-drives `.czi`; the procedure is
[`../../tasks/drives_microscopy_ingest_runbook.md`](../../tasks/drives_microscopy_ingest_runbook.md),
the dry-run evidence [`../../tasks/drives_ingest_dryrun_review.md`](../../tasks/drives_ingest_dryrun_review.md).

```
python tools/drive_staging/ingest_plan.py goptical --hash   # ZWSI already in S:\goptical's AxioScan archive?
python tools/drive_staging/ingest_plan.py plan              # -> _analysis\ingest\expected.csv, batches.csv, excluded.csv
python tools/drive_staging/ingest_plan.py extract           # archive-only .czi -> _extract\ (7-Zip, hash-verified)
python tools/drive_staging/ingest_plan.py farm              # hard-link farm -> _farm\<batch>\ (zero space, same volume)
python tools/drive_staging/ingest_plan.py configs           # -> tools/configs/drives_2026-09/ (YAML + case table per batch)
python tools/drive_staging/ingest_check.py                  # the dry-run review: engine resolution vs plan, file by file
python tools/drive_staging/ingest_verify.py --nas-root <root> --batch B01   # after a batch ran
```

- **One row per distinct content** (sha256), one canonical copy each; the other copies' paths are kept
  for the provenance. Content already in production, or (ZWSI) already on `S:\goptical`, is excluded.
- **The farm is the source.** Every file sits at `_farm\<batch>\<drive-label>\<its path on the drive>`,
  so the engine's `original_name` is the traceable source path, and the dedup key is stable across
  re-runs. It is built from hard links: the staged copy is never modified.
- **Per-file values** (project, researcher, operator, subject, sample, link name) reach the engine
  through `auto_discover.case_table` (10_TOOLS §2.1.3). Tests: `python tools/test_drives_ingest_plan.py`
  and `PYTHONPATH=tools python tools/ingest/test_case_table.py`.
