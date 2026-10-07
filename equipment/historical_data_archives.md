# Historical / source data archive locations

**Status:** REFERENCE — a catalogue of **where historical and current source data lives** per
instrument, for future ingest into gjesus3. This is the *source* side; gjesus3 is the *destination*.
Access status varies (some need to be granted / pulled off external drives) — noted per entry.
**Created:** 2026-06-12. **Maintained by:** Data Office (Ryan).

> Standalone on purpose — no pointers were added to `equipment/INDEX.md` or other index files yet (to
> avoid touching tracked files during an in-flight migration). Add an INDEX pointer later. A future
> session can find this via the `[[ni-historical-archives]]` memory note or by globbing
> `equipment/historical_data_archives.md`.

Paths are Windows network shares unless noted. On Ryan's workstation: `S:` = `\\…\` optical/nuclear
shares, `K:` = group shares (verify exact UNC per machine).

---

## Nuclear Imaging (NI)

Three tiers, most→least standardized:

| Tier | Location | Access | Notes |
|---|---|---|---|
| **Standardized long-term archive** | `gnuclear3` | **NEED ACCESS** (not yet granted) | The intended deep-time standardized store. Get access. |
| **Intermediate standardized** | `\\cicmgsp02\gnuclear2$` | reachable today | The `.tgz`-per-acquisition archive already used by **archive-mode** ingest (round 8). Layout/parse documented in [`nuclear-imaging/internal_ni_data_handling_workflow_notes.md`](nuclear-imaging/internal_ni_data_handling_workflow_notes.md). MFB group under `…\<year>\Jesus\`. |
| **Active working space (messy)** | `S:\gnuclear` | ✅ **PARTIALLY INGESTED 2026-08-13** | `S:\gnuclear\<YYYY>\Jesus\<user>\…`, years 2022–2026, **MFB group always under `Jesus\`**. **Not redundant** — it held **2,312 acquisitions** (one per *reconstruction*) against the 132 then loaded. **1,508 are now in true production** (192.0 GB, 14 projects); 131 were already present; **673 are HELD BACK** — no *valid* animal-protocol code appears in their path (those researchers filed by study/tracer name), and an AE code must never be guessed, so they await a `(researcher, series)` → code mapping. A **read-only checksummed snapshot is retained** at `J:\gjesus3-data\staging\ni_gnuclear_20260812\` (2,485 files / 286.3 GB), so ingesting the remainder needs no further network pull — and **`S:\gnuclear` itself was never written to**. Its layout is a flattened analysis workspace (loose `.dcm` at depth 0–8, one reconstruction copied into up to 48 folders, dynamic PET split per frame), so neither existing NI pipeline fit and it got its own fan-in path: `tools/ingest/ni_flat.py` + `molecubes_ni_gnuclear.yaml`. Layout finding: [`nuclear-imaging/gnuclear_active_workspace_layout.md`](nuclear-imaging/gnuclear_active_workspace_layout.md); plan, runbook, and the review that caught 21 fabricated protocol codes before they reached production: [`tasks/ni_gnuclear_active_space_plan.md`](../tasks/ni_gnuclear_active_space_plan.md), [`tasks/ni_gnuclear_production_runbook.md`](../tasks/ni_gnuclear_production_runbook.md), [`tasks/REVIEW_FINDINGS_2026-08-13.md`](../tasks/REVIEW_FINDINGS_2026-08-13.md). |

The live-machine box (`REMIW11` / the Molecubes `…/remiW11/data/` tree) and its sync rules are in
[`nuclear-imaging/live_machine_data_layout_and_sync_rules.md`](nuclear-imaging/live_machine_data_layout_and_sync_rules.md).

> **Source of truth = the ARCHIVE (DECIDED 2026-06-12).** Users cannot alter the live box and a
> systematic script pulls box→archive, so the archive (`gnuclear2$` now, `gnuclear3` future) is the
> authoritative, complete record — **preload all historical NI from it** (archive-mode pipeline,
> proven in round 8). The **live-box sync is the forward path for active project data — ESSENTIAL, not
> optional** (it's most of what gets researchers invested); the archive does the historical preload,
> the live sync keeps current. Dedup both on `(acq_datetime_full, modality)` so they reconcile. ⚠️
> When preloading from the archive, confirm the `.tgz` for a **multi-animal** scan exposes the full
> animal list (the live-box folder does; round 8 was single-animal). See
> [`tasks/archive/ni_live_sync_handoff.md`](../tasks/archive/ni_live_sync_handoff.md).

---

## MRI (Bruker ParaVision)

**Access:** SFTP / SSH to the acquisition host.

```
host:  kenia.cicbiomagune.int
user:  mriuser
```

| Dir | Path | ParaVision version |
|---|---|---|
| 1 | `/opt/PV-7.0.0/data/nmr` | PV 7.0.0 |
| 2 | `/opt/PV6.0.1/data/nmr` | PV 6.0.1 |

Each `…/data/nmr/<exam>` is a ParaVision exam folder (the per-exam layout + parse is documented in
[`mri-platform/internal_mri_data_handling_workflow_notes.md`](mri-platform/internal_mri_data_handling_workflow_notes.md)).
Round 6 used `tools/ftp_mirror.py` (SFTP) for the FTP-from-workstation pull.

### Credential handling — DECIDED 2026-06-12: simple password in a local file

The host is **behind the work firewall** (not the open internet) and the `mriuser` password is
short/widely-known on-site, so sensitivity is low. The sync runs on a **shared machine we do not
reconfigure**, so SSH keys / `authorized_keys` edits are out — we use a plain **password file**,
scoped to this project.

**Exact file** (user profile — NOT the repo, NOT OneDrive):

`C:\Users\<you>\.ssh\gjesus3_mri.cred`

**Exact contents** (INI — a future script reads it with one `configparser` call):

    [mri]
    host = kenia.cicbiomagune.int
    user = mriuser
    password = <the password>

**Why there, and not the obvious alternatives:**
- **Not `.my.cnf`** — that is the MySQL/animal-DB config (read by pymysql); different tool, keep
  separate so neither breaks.
- **Not inside the project folder** — the repo is pushed to GitHub *and* the folder is OneDrive-synced;
  even a trivial password must not land in either. `C:\Users\<you>\.ssh\` is local-profile only.
- `.ssh\` already exists and is user-protected; the `.cred` name + `[mri]` section make it clearly a
  credentials file, distinct from the SSH key files beside it.

Optional (low priority given low sensitivity) lock-down:
`icacls "%USERPROFILE%\.ssh\gjesus3_mri.cred" /inheritance:r /grant:r "%USERNAME%:R"`.
The agent does not have the password — it is pasted in out-of-band on the sync machine.

### The MRI platform's archive (older 7 T data) — READ-ONLY (added 2026-10-07)

When the 7 T acquisition machine's disk fills, the platform moves the oldest studies to its **own archive** (Ryan,
2026-10-06). We can reach that archive over SSH/SFTP. **It belongs to the platform, not to gjesus3.**

```
host:   10.10.3.175        (behind the institute firewall; password protected)
user:   mriuser
folder: /share/homes/mriuser/backup_7T_olddata_260824
```

**Layout** (listed 2026-10-07): the year folders `2019_pv6`, `2020_pv6`, `2021_pv6`, `2022_pv6`, `2022_pv7` and
`2022_PV6_PV7`. Each holds **one compressed archive per ParaVision study**, named after the study folder
(`<study>.tar.gz` or `<study>.tar.xz`, e.g. `20200107_145059_jrc200107_m6_hypx_1_1.tar.gz`). Most archives have a
`.sha1` file beside them, and a few have a `.sha256`. Four of the six folders also hold a `00_LOGFILE_sha1.txt` (not `2022_pv6` or `2022_pv7`), plus older
`MRI7_*.md5sums.Saved_*` lists. All groups' studies are there: `jrc` is MFB, and `pr`, `abh`, `sp`, `jl`, `dan`
and others are other groups. In all there are 3,048 archives (617.7 GB) holding 2,555 distinct studies from
2019–2022. 2022 studies appear in up to three folders, and the archive has **no 2023 folder**. The census is in
[`tasks/mri_archive_census.md`](../tasks/mri_archive_census.md).

**Credentials:** a separate **`[mri_archive]`** section in the same `%USERPROFILE%\.ssh\gjesus3_mri.cred`
(host, user, password, port). It is never printed.

**The three rules** (Ryan, 2026-10-07, "critical importance"):

1. **Never write, rename, chmod or delete anything there.** The account *can* write, so the rule is enforced in
   code. All access goes through `tools/mri_archive.py`. Its wrapper holds only "list a folder", "stat a path" and
   "open a file for reading (`rb`)". It has no write, delete, shell or command method, and it refuses any path
   outside the folder above. No `.part`, lock or temp file is ever created there: downloads write locally.
2. **One connection, one call at a time. No file contents between 08:00 and 18:00, Monday to Friday.** Listing
   is fine in those hours, done gently (the module paces its calls). Downloading archives is for nights and
   weekends only, and the module refuses to open a file in working hours.
3. **The normal tools never point at it.** The operator GUI, `mri-ingest` and `ftp_mirror.py` read only `[mri]`
   (the scanner, `kenia`). Only `tools/mri_archive.py` reads `[mri_archive]`, and it never falls back to `[mri]`.

**Listing (read-only):** `python tools\mri_archive.py list --out <local.csv>` writes one row per entry (path,
kind, size, modification time) to a local CSV. The census listing took 7 calls and about 2 s.

**Download (after hours only):** `python tools\mri_archive.py fetch --plan <pull_plan.csv> --dest
D:\projects\gjesus3\mri_archive\pull [--dry-run] [--max-gb N] [--stop-at HH:MM]` fetches the plan's pulled tiers
(C, A, A2, B: Ryan's rulings of 2026-10-07) to `<dest>\<year folder>\<archive>` on local disk, with the `.sha1` /
`.sha256` beside each. Each archive is read in chunks into a local `.part`, hashed while reading, and renamed
only when its checksum matches; a mismatch is kept as `.bad`. Archives with no checksum file are checked by the
compression's own check plus a full tar listing. `<dest>\fetch_manifest.csv` records every attempt, and a re-run
skips the verified ones. The run refuses to start in working hours, starts no file it cannot finish before 08:00
(or `--stop-at`), and stops mid-file at that time, leaving only the local `.part`. `--dry-run` lists only.

---

## Microscopy

### Axio Scan 7 (WSI) — `ZWSI`

First **semi-official** microscopy archive (the device is new — not very historical, but the first
standardization attempt):

```
S:\goptical\GOpticalUsers data\AxioScan
```

### Cell Observer (`CELL`) and Confocal LSM 900 (`LSM9`)

**No network historical archives; the history was ingested from the operators' external drives
(✅ 2026-09-30 to 2026-10-02).** Two one-copy drives (`drive1_FRIO-X6`, `drive2_MFB-Disco-2`) were staged to
`D:\projects\gjesus3\staging\` and their `.czi` files ingested into `/raw/` as **8,790 acquisitions**
(3,849 GB): `CELL` 8,061, `LSM9` 387, `ZWSI` 4 and `XMIC` 338, in 16 batches. Every row's `ingest_config` is
`tools/configs/drives_2026-09/drives_B<NN>.yaml`, and the per-file provenance (drive, path, archive member,
SHA-256) is in `tasks/drives_ingest_provenance.csv`. **5,055 of them have a blank project:** their paths
carried no project claim (4,952) or only a claim that was left blank (103, see
`tasks/drives_blank_project_list.csv`). The plan, rules and batch log are in
`tasks/drives_ingest_dryrun_review.md` (§11) and `tasks/drives_microscopy_ingest_runbook.md`. **Not part of
that ingest:** the loose `.tif` / `.lsm` files, derived exports, and the MRI and PET/CT data the drives also
hold (see the review's §9). MFB (Jesus's lab) does, however, have plenty of **intermediate / current** data
not yet moved to external drives:

| Instrument | Current MFB data location |
|---|---|
| Cell Observer | `K:\gjesus\Ainhize\CELL OBSERVER` |
| Confocal LSM 900 | `K:\gjesus\Ainhize\CONFOCAL LSM 900` |

(Operator/workflow context for these two is in
[`cell-observer/`](cell-observer/) and [`lsm900/`](lsm900/); `Ainhize` = Ainhize Urkola Arsuaga,
the CELL + LSM 900 operator.)

---

## Open items

- **NI `gnuclear3`** — request access (the intended standardized long-term store).
- **MRI credentials** — set up the SSH key (above) on the sync machine; decide key-vs-password.
- **MRI platform archive** — pulling from it (MFB studies production lacks, and stream M's originals check) is
  proposed in [`tasks/mri_archive_census.md`](../tasks/mri_archive_census.md) §5. Nothing has been decided or downloaded.
- **Microscopy external-drive pull** — the two staged drives' `.czi` are ingested (above); capture any
  further per-operator drive locations as they surface.
- Add a pointer to this file from `equipment/INDEX.md` once the in-flight migration settles.
