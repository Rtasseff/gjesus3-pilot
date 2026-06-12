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
| **Active working space (messy)** | `S:\gnuclear` | reachable today | Some order — dated by year; **MFB group is always under `Jesus\`** at the dir level beneath the year. Messy. **Likely redundant**: if we combine the two archives above with the **live-machine sync** of the acquisition box (`REMIW11`), this active space should not be needed — but captured here for completeness. |

The live-machine box (`REMIW11` / the Molecubes `…/remiW11/data/` tree) and its sync rules are in
[`nuclear-imaging/live_machine_data_layout_and_sync_rules.md`](nuclear-imaging/live_machine_data_layout_and_sync_rules.md).

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

---

## Microscopy

### Axio Scan 7 (WSI) — `ZWSI`

First **semi-official** microscopy archive (the device is new — not very historical, but the first
standardization attempt):

```
S:\goptical\GOpticalUsers data\AxioScan
```

### Cell Observer (`CELL`) and Confocal LSM 900 (`LSM9`)

**No network historical archives.** These will need to be pulled off the operators' **external
drives** — planned *after* the microscopy GUI is released (operators do the pull). MFB (Jesus's lab)
does, however, have plenty of **intermediate / current** data not yet moved to external drives:

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
- **Microscopy external-drive pull** — sequenced after the GUI release; capture per-operator drive
  locations as they surface.
- Add a pointer to this file from `equipment/INDEX.md` once the in-flight migration settles.
