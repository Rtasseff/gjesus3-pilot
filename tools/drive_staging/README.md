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
