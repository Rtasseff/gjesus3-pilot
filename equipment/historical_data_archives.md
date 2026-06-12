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

### Credential handling — how to save the password for scripts (recommended approach)

**Preferred: passwordless SSH key (no stored password at all).** Generate a key pair on the machine
that will run the sync, install the public key on the server, keep the private key local and
protected (never in the repo or OneDrive):

1. `ssh-keygen -t ed25519 -f ~/.ssh/kenia_mri -C "gjesus3 mri sync"` (set a passphrase or leave empty
   for unattended scripts).
2. Install the public key: `ssh-copy-id -i ~/.ssh/kenia_mri.pub mriuser@kenia.cicbiomagune.int`
   (or paste `kenia_mri.pub` into the server's `~/.ssh/authorized_keys`).
3. Scripts then authenticate with the key — `paramiko`/`pysftp` `key_filename=~/.ssh/kenia_mri`, or
   `sftp -i ~/.ssh/kenia_mri`, or `rsync -e "ssh -i ~/.ssh/kenia_mri"`. **No password in any file.**
4. Optionally pin it in `~/.ssh/config` so the host/user/key are implicit:
   ```
   Host kenia-mri
       HostName kenia.cicbiomagune.int
       User mriuser
       IdentityFile ~/.ssh/kenia_mri
   ```

**If the server only allows password auth** (no keys): store it **outside git and OneDrive** —
- Windows: **Windows Credential Manager**, retrieved in Python via the `keyring` library; or
- a permission-restricted file in the user profile (e.g. `C:\Users\<you>\.ssh\kenia_mri.cred` or a
  `~/.netrc` entry), referenced by an **env var** — the same philosophy as the existing animal-DB
  `~/.my.cnf` (`GJESUS3_MYCNF`): sensitive, not committed, machine-local, on-network only.

**Never** put the password in the repo, OneDrive-synced folders, or logs. (The executor/agent will not
have it — install it out-of-band on the sync machine.)

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
