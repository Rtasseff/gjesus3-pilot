# Internal Nuclear Imaging — **live-machine** remote access (reverse SSH tunnel)

**Status:** ✅ **IN USE since 2026-10-01** — both halves are installed. The box dials out through its
LaunchAgent, and the Data Office logs into it from the workstation without a password (§2,
"Operating the box from here"). Individual sections keep their own markers.
**Last updated:** 2026-10-01 — box half installed in one visit: the manual tunnel was proven from the
box first, then replaced by the LaunchAgent, also proven from the box. Afterwards, from the
workstation, the box's key was hardened and a Data Office key was added to the box. Visit record
§9; moving the landing pad to Box A without a visit §10. (First version 2026-08-06; the box's key
was generated **on the box** — no private key was ever staged anywhere, §7.)
**Companion documents:** [`live_machine_data_layout_and_sync_rules.md`](live_machine_data_layout_and_sync_rules.md)
(what is *on* the box and how we would sync it) and
[`internal_ni_data_handling_workflow_notes.md`](internal_ni_data_handling_workflow_notes.md)
(the already-implemented archive mode). This document covers only **how we reach the box at all**.

> **One-line takeaway.** The Molecubes acquisition box cannot be reached inbound — it sits behind its
> own router. So it **dials out** to the Data Office workstation and we ride that connection
> backward. Everything else here is consequence: no admin on the workstation forces the landing pad
> into WSL, and the box being a live acquisition machine forces every change on it to be minimal,
> reversible, and written down.

---

## 1. Why this exists

NI work that requires running commands **on the acquisition box itself**, not on a copy of its
data:

- **Developing and testing the NI live sync on the box** — the sync command researchers will run
  there (branch `feat/ni-live-hardening`, not yet merged; its on-box merge gates are listed in that
  branch's `tasks/RESUME_ni_live.md` §4). Before 2026-10-01 every such run cost a physical visit.
- **Refreshing the evidence base** — `live_machine_data_layout_and_sync_rules.md` rests entirely on
  `S:\gnuclear\2026\Jesus\Ryan\datapath.txt`, a 295,538-line recursive dump of the box's data root
  captured during a physical visit. Until the tunnel, every re-check of that layout cost another visit.
- **Later: the server pulls NI data itself.** The planned single ingest app on Box A reaches the box
  through this tunnel, so operators can leave the room as soon as the scan is done (§10;
  [`tasks/BACKLOG.md`](../../tasks/BACKLOG.md) "Ingest from one place").

**Gate-0 was answered without the tunnel.** This document was first motivated by Gate-0: whether
`os.link` (hard links) works on the box's SMB mount. The answer is **no**: `os.link` returns `ENOTSUP`,
proven on the box on 2026-06-25 and again on 2026-08-05. The ingest handles it by deferring those
links to `registries/pending_links.csv`, which `tools/relink_pending.py` drains from Windows
(NI-RA-05).

Access to the box is **rare, short, and scheduled around imaging sessions**. Before this, each of
those questions cost a slot; a failed attempt cost the whole slot and a week's wait. The tunnel
converts a scarce physical resource into an ordinary remote login.

**Scope note.** This is an *access* mechanism, not an ingest mechanism. It changes nothing about how
NI data is registered, named, or stored — those live in the companion documents above.

---

## 2. Architecture

```
  Molecubes box  192.168.0.180                Data Office workstation  10.10.2.195
  (behind its own router, NAT'd)              (no admin rights)
        |                                              |
        |  (1) outbound:  ssh -N -R 2222:localhost:22 -p 2200
        +--------------------------------------------->|  0.0.0.0:2200
                                                       |     tcp_forward.py (userspace, Windows)
                                                       |          |  relays
                                                       |          v
                                                       |  <WSL IP>:2200
                                                       |     sshd (WSL2 / Ubuntu 24.04)
                                                       |          |
  box sshd :22  <------------------------------------------- localhost:2222
        (2) the reverse channel, created by the -R flag
```

Two directions over **one** TCP connection:

1. The box dials **out** to the workstation and authenticates to sshd running inside WSL.
2. `-R 2222:localhost:22` makes that session open a listener on **`localhost:2222` inside WSL**.
   Anything connecting there emerges at the box's own `localhost:22`.

### Operating the box from here ✅ (since 2026-10-01)

```powershell
wsl -d Ubuntu -- ssh -p 2222 molecubes@localhost     # from PowerShell
ssh -p 2222 molecubes@localhost                      # from a WSL shell
```

| | |
|---|---|
| **Login** | No password. The WSL key `~/.ssh/id_ed25519` (comment `rtasseff@gmail.com`) is in the box's `~/.ssh/authorized_keys`. Plain Windows `ssh` also reaches the box (see the loopback mirroring below), but it asks for the Mac's password, because the key lives in WSL. |
| **The box** | `molecubess-iMac.local`, user `molecubes`, macOS 11.6.5. Host key ED25519 `SHA256:EAfNEV4TsBCUK22crq2CtMdZuZ1OvAw6H02A+2DKZrw`, saved in WSL's `known_hosts` as `[localhost]:2222`. |
| **Is it up?** | `wsl -d Ubuntu -- bash -c 'nc -w 4 localhost 2222 </dev/null \| head -1'` prints `SSH-2.0-OpenSSH_8.1`. That is the **box's** sshd; WSL's own reports 9.6. On the box, `launchctl list \| grep eus.biomagune` shows the agent with a PID. |
| **Mounts on the box** (2026-10-01) | `/Volumes/gnuclear` = `//nuclearuser@10.10.1.92/gnuclear` · `/Volumes/gnuclear2$` = `//nuclearuser@cicmgsp02/gnuclear2$` · `/Volumes/gjesus3` = `//rtasseff@GJESUS3._smb._tcp.local/gjesus3` (SMB 3.1.1). Ryan reports that the `gjesus3` mount does not stay up. It is the sync's destination, so that is tracked as a sync prerequisite in [`tasks/STATUS.md`](../../tasks/STATUS.md), not here. **Cause found 2026-10-06:** no password is saved for it, so nothing re-mounts it. The interim fix (2026-10-08) is in §7. |

**The rules of §3 apply to remote work too.** The box is slow and runs live acquisitions. Keep what
runs over the tunnel light and short, and never write into its acquisition folders.

**Quoting trap when scripting it from Git Bash or PowerShell.** `wsl.exe -- ssh … '<remote
command>'` re-parses the line inside WSL, so `$(…)` in the "remote" command expands **on the
workstation**: `$(hostname)` reported `bmg-rtasseff` while the commands around it ran on the box.
For anything beyond a single plain command, put the ssh call in a script and feed the remote side
through `ssh … 'bash -s' <<'EOF'`.

### Why the landing pad is inside WSL

The workstation account has **no administrator rights**, so no Windows SSH server can be installed.
sshd therefore runs inside WSL, and a small userspace Python forwarder
(`WorkstationOps\lib\tcp_forward.py`) republishes it on `0.0.0.0` so the box can reach it. Neither
piece needs elevation.

Two consequences worth knowing before debugging anything:

- **sshd inside WSL listens on 2200, not 22.** Ubuntu 24.04 ships `sshd-socket-generator`, which
  reads `Port` from `sshd_config` and rewrites the socket unit. On older Ubuntu that `Port` line
  would have been inert under socket activation; here it is not.
- **The reverse listener binds on WSL's loopback**, because `GatewayPorts` is `no`. Reaching it from
  native Windows works anyway (WSL mirrors it onto Windows loopback), and that has been verified —
  but `wsl -d Ubuntu -- ssh -p 2222 molecubes@localhost` is the guaranteed form if the mirror ever
  misses.

### Where each half is owned

| Half | Repo | Contents |
|---|---|---|
| Workstation (WSL keepalive, forwarder, ports, health, logs) | `WorkstationOps` | operation `molecubes-tunnel` — run `.\ops status molecubes-tunnel` |
| Domain (what the box is, why we reach it, the operator procedure) | this repo | this document + `S:\gnuclear\2026\Jesus\Ryan\tunnel.txt` (field card) |

This mirrors the `finder-refresh` split, where the generator lives here and the schedule/health live
in WorkstationOps.

---

## 3. Safety on a live acquisition machine ✅ DECIDED

The box runs live acquisitions; a disruption can ruin experiments in progress. Every action is
therefore classified by **whether it persists**, and the persistent ones are minimised and recorded.

| Action | Persists? | Assessment |
|---|---|---|
| Enabling **Remote Login** (macOS SSH) | ✅ survives reboot | Unavoidable — the tunnel cannot work without it. **It was already on (2026-10-01, NI-RA-02), so nothing changed.** |
| Installing the **SSH key + LaunchAgent** | ✅ survives reboot | Deliberate, so the tunnel reconnects unattended. **Installed 2026-10-01.** Removal is two `rm` commands plus one `launchctl` call (§6). |
| A **Data Office key** in the box's `~/.ssh/authorized_keys` | ✅ survives reboot | **Added 2026-10-01**, so the box can be operated from the workstation without a password. One line, comment `rtasseff@gmail.com`; removal in §6. |
| The `ssh -N` tunnel process | ❌ process-scoped | An idle TCP connection. Negligible CPU and network. |
| `caffeinate` | ❌ process-scoped | **Not used.** `pmset -g` on the box reports `sleep 0` — it already never idle-sleeps, so the assertion was redundant and was dropped rather than added. |

**Nothing about acquisition, storage, or the box's own software is touched.** The tunnel provides a
shell; it does not install dependencies, change power settings, or run anything on a schedule beyond
maintaining its own connection.

---

## 4. What is proven, and what is not

Verified from the Data Office workstation on 2026-08-05/06, and at the box on 2026-10-01:

| Link | State |
|---|---|
| Firewall + routing: box → workstation on 2200 | ✅ verified from the box (`nc` succeeded) |
| SSH banner through the forwarder | ✅ verified |
| Password authentication through the forwarder | ✅ verified (interactive login reaches a WSL shell) |
| `-R` reverse forwarding through the forwarder | ✅ verified by rehearsal, with WSL standing in for the box |
| Riding the tunnel back from Windows | ✅ verified (both `wsl -d Ubuntu -- ssh …` and plain `ssh …` forms) |
| Idle survival (45 s with no traffic) | ✅ verified after the forwarder fix below |
| **The box actually running the tunnel** | ✅ **2026-10-01** — the manual tunnel was proven from the box (STEP 6c), then replaced by the LaunchAgent |
| Unattended reconnect via LaunchAgent | ✅ **installed and proven from the box 2026-10-01** (STEP 7d). Not yet seen recovering from a real drop or reboot (NI-RA-01b). |
| The **hardened** box key carrying the tunnel | 🔶 Restrictions applied 2026-10-01 at 16:03. The live connection authenticated at 15:52, before that, and is unaffected (re-checked after). The first login under the restricted key is the next reconnect. The same option set does carry `-R 2222` for the rehearsal key (acceptance test steps 6–8), and the LaunchAgent runs `ssh -N`, so the forced command never fires. |

### The failure that cost the first attempt ⚠️ read before debugging

`tcp_forward.py` passed `timeout=5` to `socket.create_connection`, intending a *connect* timeout.
That call leaves the socket in timeout mode, so the same 5 seconds applied to every `recv()` in the
relay loop: **any connection idle for 5 seconds was torn down.**

A human takes longer than 5 seconds to type a password, so the connection was already dead by the
time the password was submitted — which presented as an authentication problem and sent the first
diagnosis in the wrong direction. It also would have killed the tunnel itself, since `ssh -N -R` is
idle by definition.

Two lessons worth carrying:

- **A wrong password and a broken transport looked identical from the box.** The observation that
  cracked it was that a *deliberately wrong* password produced the *same* error as the right one.
- **`nc -vz` is not a valid readiness test against this forwarder.** It reports success whenever
  something accepts a socket, including when the far side is dead. Always read a banner:
  `nc -w 3 10.10.2.195 2200 < /dev/null | head -1`.
- **…but on the box itself that banner read gives false negatives** (found 2026-10-01). At the box
  it printed nothing on both 2200 and 8000, yet the landing pad was healthy: the acceptance test
  had passed 9/9 that morning, and `ssh-copy-id` over 2200 succeeded a minute later. A browser
  pointed at those ports reported an "HTTP/0.9" response. That is the SSH banner, i.e. proof that
  sshd *was* answering. (Port 8000 is the tunnel's fallback forwarder, not an image server.)
  **From the box, test with ssh itself:**
  `ssh -o BatchMode=yes -o ConnectTimeout=5 -p 2200 rtasseff@10.10.2.195 true`.
  `Permission denied (…)` means a live sshd answered. `Connection reset` is the 2026-08-05 "half up"
  failure. A refusal or timeout means nothing is listening. The field card still carries the `nc`
  form (§9).

Both are encoded in the field card and in the WorkstationOps health check, which probes the
workstation's LAN address (never loopback — `wslrelay.exe` mirrors WSL's sshd onto `127.0.0.1:2200`
and would report a healthy path when every forwarder is dead).

---

## 5. Operator procedure

**The box half was installed with this procedure on 2026-10-01 (§9).** It is now needed only to
re-install from scratch. Moving the landing pad to Box A does **not** need it, or a visit (§10).

The authoritative, self-contained field card is **`S:\gnuclear\2026\Jesus\Ryan\tunnel.txt`** — kept
on the NAS deliberately, because it is reachable from the box when nothing else is. Take that, not
this document, to the machine.

Shape of the visit:

1. **Before leaving the workstation:** start the landing pad and run the acceptance test. A failure
   found here costs minutes; the same failure found at the box costs the access slot and a week.
   ```powershell
   cd "C:\Users\rtasseff\OneDrive - CIC biomaGUNE\WorkstationOps"
   .\ops run molecubes-tunnel        # leave running
   wsl -d Ubuntu -- bash "/mnt/c/Users/rtasseff/OneDrive - CIC biomaGUNE/WorkstationOps/setup/test-tunnel-path.sh"
   ```
   The test stands a workstation-local rehearsal key in for the box and checks all nine links,
   including that the key **cannot** obtain a shell or bind an unpermitted port, and that an idle
   tunnel survives (the regression guard for §4's 5-second bug). Exit 0 means safe to travel.
   Last full run: **9/9 PASS, 2026-10-01**, the morning of the install.
   ⚠️ **While the box is connected, this test cannot reach 9/9.** The box holds `localhost:2222`,
   so step 6's rehearsal `-R 2222` is refused ("tunnel did not start"). Step 7 then reads the
   *box's* banner and passes for the wrong reason. Expect 8/9: it is a pre-install test, not a
   health check of the live tunnel. Use the checks in §2 for that.
2. **At the box:** confirm the username and Remote Login; read a banner from the workstation
   (**not** `nc -vz`); generate a key **on the box**; push its public half with `ssh-copy-id`.
3. **Establish the proven tunnel first** (a detached `nohup ssh -N -R`), and verify it.
4. **Only then attempt the LaunchAgent**, rolling back to step 3 at the first sign of trouble.
5. **Back at the workstation:** harden the pushed key
   (`WorkstationOps\setup\harden-tunnel-key.sh`), re-confirm, then use it:
   `ssh -p 2222 molecubes@localhost`. Done 2026-10-01, plus a Data Office key for passwordless
   login (§2).

### The single-operator constraint ✅ DECIDED — this shapes the whole procedure

The box is in a **restricted-access room, entered once per visit**. The operator cannot step out and
return, and there is **nobody at the workstation end** to confirm anything. Three consequences, all
of them load-bearing:

- **Every check is performed from the box itself.** The full loop is proved without leaving the
  keyboard: SSH from the box into WSL on the workstation, then from that WSL prompt back into the box
  through the tunnel (`ssh -p 2222 molecubes@localhost hostname`). If it prints the box's own
  hostname, the tunnel demonstrably carries traffic. A running `ssh` process is *not* proof.
- **The key is deliberately left unrestricted during the visit**, because the hop above needs a
  shell. It is hardened afterwards from the workstation — which also means that if the restrictions
  break something, that is fixable without another visit.
- **The proven method goes first, the convenient one second.** The manual `nohup ssh -N -R` tunnel is
  established and verified *before* the LaunchAgent is attempted, so the operator never leaves
  without working access. The LaunchAgent is an untested upgrade; the documented response to any
  trouble is to roll back to the manual tunnel rather than debug in the room. A live manual tunnel is
  itself the means to debug the LaunchAgent remotely before the next visit.

⚠️ **The one unrecoverable failure** is arriving to find the workstation landing pad not running —
nothing at the box can fix that, and the visit is lost. Two things now guard against it:

- The landing pad is **scheduled at logon** (`WorkstationOps-MolecubesTunnel`), so it is up whenever
  the workstation is, without anyone remembering to start it (NI-RA-04, done 2026-08-06).
- `setup\test-tunnel-path.sh` should still be run immediately before travelling. The schedule makes
  the pad *usually* up; the test is what makes it *known* up.

A workstation reboot is **not** a lost visit: the box's LaunchAgent retries every 30s indefinitely,
so once the pad returns the tunnel re-establishes itself with no trip to the box.

### An easy mistake, worth stating plainly

In the `-R` option the target is **`localhost:22`** — port 22, the *box's* own sshd. The workstation's
sshd is on 2200, and that number leaks into `-R` arguments very easily (it did during drafting). A
tunnel built with `-R 2222:localhost:2200` **establishes cleanly and looks correct**, then fails only
when someone tries to come back through it — by which time the operator has left the room.

**Known and unavoidable:** enabling Remote Login needs macOS admin. If it is already on, nothing
changes.

---

## 6. Removing it

Leaves no residue beyond these files, one `authorized_keys` line, and the Remote Login setting. On
the box:

```bash
launchctl unload ~/Library/LaunchAgents/eus.biomagune.mfb.tunnel.plist
rm ~/Library/LaunchAgents/eus.biomagune.mfb.tunnel.plist
rm ~/.ssh/id_ed25519_molecubes_tunnel ~/.ssh/id_ed25519_molecubes_tunnel.pub
# then delete the Data Office line (comment rtasseff@gmail.com) from ~/.ssh/authorized_keys
```

(Until 2026-10-01 this block named the key `id_ed25519_gjesus3_tunnel`, which never existed. The
field card and the LaunchAgent both use `id_ed25519_molecubes_tunnel`.)

Then, on the workstation, drop the `molecubes-box` line from WSL's `~/.ssh/authorized_keys` — after
which the box's key is dead everywhere even if a copy survives. **Leave Remote Login on**: it was
already on before we arrived (NI-RA-02).

---

## 7. Security posture 🔶 DRAFT

**No private key ever leaves the acquisition box.** The key is generated *on* the box and only its
public half is pushed, with `ssh-copy-id`, over the already-authenticated session. An earlier plan
staged a private key on the NAS share to carry it over; that was dropped once password
authentication was proven working, because generating in place is strictly safer and costs one extra
command. Nothing secret is written to a shared drive at any point.

**The key is restricted in `authorized_keys`** — applied by
`WorkstationOps\setup\harden-tunnel-key.sh` after the push, because `ssh-copy-id` always appends a
bare, unrestricted entry:

```
restrict,port-forwarding,permitlisten="localhost:2222",permitlisten="localhost:2333",command="/bin/false"
```

⚠️ **`restrict` alone is not enough, and this is easy to get wrong.** `restrict` disables PTY
allocation, X11, agent forwarding, user-rc and port forwarding — but **not command execution**.
Verified on 2026-08-06: with `restrict,port-forwarding` only, `ssh <host> hostname` still ran and
returned the hostname. The forced `command="/bin/false"` closes that. It does not affect the tunnel,
because `ssh -N` opens no session channel and so never triggers the forced command. Both the
restriction and the `permitlisten` bound were tested by attempting to violate them.

Other posture notes:

- The key grants access to the **WSL sandbox** on the workstation — not to Windows, not to the NAS.
- The key has **no passphrase**, which is unavoidable for an unattended LaunchAgent. That is the
  reason the option set above matters: a stolen key yields a port-forward to a sandbox, not a login.
- Port 2200 is exposed on the institute LAN, with password authentication still enabled for
  interactive use. Restricting callers (`--allow` on the forwarder) is available but not applied —
  the box is NAT'd, so the useful allow-list entry is its router's egress address, **`10.10.3.168`**
  (NI-RA-03, captured 2026-10-01).
- **The reverse direction is not restricted, deliberately.** The Data Office key added to the box
  on 2026-10-01 (WSL `~/.ssh/id_ed25519`, no passphrase) is an ordinary login: whoever can use the
  WSL account on the workstation can open a shell on the acquisition iMac as `molecubes`. That is
  its purpose — operating the box from here — and why it is recorded rather than restricted.
- The box's `authorized_keys` also holds an older RSA key, comment `molecubes@molecubess-iMac.local`.
  The Data Office did not add it, and left it alone.
- A second, **workstation-local rehearsal key** (`~/.ssh/id_ed25519_molecubes_tunnel` inside WSL,
  comment `molecubes-tunnel-2026-08-06`) exists deliberately: it lets the full tunnel path be
  re-tested from the workstation alone, without the acquisition box. It carries the same
  restrictions. Remove it with `rm ~/.ssh/id_ed25519_molecubes_tunnel*` and drop its
  `authorized_keys` line if that capability is no longer wanted.
- **Interim: gjesus3 mounted with the Data Office login (✅ decided by Ryan, 2026-10-08; IT will
  not provide an account).**
  - **What it is:** the NI sync writes to gjesus3 from this box, so until Box A pulls the data
    through the tunnel (§10, and `tasks/BACKLOG.md` "Ingest from one place"), gjesus3 is kept
    mounted at `~/.gjesus3`. It uses `nobrowse`, so it is hidden from Finder.
  - **How it stays up:** Ryan's password is in the molecubes login keychain, and MacMounter's
    entry `~/.macmounter/gjesus3.conf` re-mounts the share when it drops.
  - **Accepted trade-off, interim only:** anyone using the shared `molecubes` account has Ryan's
    full gjesus3 rights while it is mounted, and his password sits in a shared account's keychain.
  - **Install / remove:** `tools/operator/ni_mac/gjesus3_mount_setup.sh` /
    `gjesus3_mount_undo.sh`, which Ryan runs himself. Run the undo when Box A takes over.

---

## 8. Open questions

| ID | Question | Status |
|----|----------|--------|
| NI-RA-01 | Does the LaunchAgent work at all? It is **untested** and is the only part of the kit that has never run. The procedure treats it as an optional upgrade behind a proven manual tunnel for exactly this reason. | ✅ **YES (2026-10-01).** Installed by STEP 7 after the manual tunnel was proven, then proven itself by STEP 7d (workstation → box through it). Running as the agent's PID, log empty. |
| NI-RA-01b | Does the tunnel survive a full reboot of the box, and does user `molecubes` log in automatically? A LaunchAgent starts at login, not at the login window. | 🔶 **Half answered.** The box does **not** log in automatically (`autoLoginUser` unset, read 2026-10-01). After a reboot the tunnel stays down until someone logs into `molecubes` — in practice the next operator. A real reboot has not been observed yet (box uptime 20 days on 2026-10-01). |
| NI-RA-02 | Was Remote Login already enabled on the box, or did we enable it? | ✅ **Already on** (2026-10-01, STEP 2). Nothing was changed. |
| NI-RA-03 | What is the box's egress address as seen by the workstation? Needed before any forwarder allow-list. | ✅ **`10.10.3.168`** — the remote end of the box's connection to the forwarder, 2026-10-01. Allow-list still not applied (§7). |
| NI-RA-04 | Should the workstation landing pad auto-start at logon? | ✅ **DONE 2026-08-06.** A `Logon` trigger was added to `WorkstationOps\lib\scheduled-task.ps1` and the op is registered as `WorkstationOps-MolecubesTunnel` (user-scoped, 1-min delay, `ExecutionTimeLimit=PT0S`). Verified by starting the task and running the full acceptance test against it: 9/9. Arriving to find the landing pad down was the one failure with no recovery from inside the restricted room. |
| NI-RA-05 | Does Gate-0 (`os.link` on the box's CIFS mount) pass once remote access is available? | ✅ **Closed — answered without the tunnel.** `os.link` returns `ENOTSUP` there (proven on the box 2026-06-25 and 2026-08-05); handled by `pending_links.csv` + `relink_pending.py` (§1). |

---

## 9. Install visit — 2026-10-01

Ryan, in the acquisition room, following field card rev4. His step-by-step notes are on the NAS
next to the card (`S:\gnuclear\2026\Jesus\Ryan\tunnel_notes.txt`, which also records the failed
2026-08-05 attempt).

| Step | Result |
|---|---|
| 1 `whoami` | `molecubes` ✅ |
| 2 Remote Login | already on ✅ (NI-RA-02) |
| 3 banner from the workstation | ⚠️ printed **nothing** on 2200 and 8000 — a false negative (§4). Ryan carried on, which was right. |
| 4 key generated on the box | ✅ `id_ed25519_molecubes_tunnel`, comment `molecubes-box`, `SHA256:AWKNXDQaryGKDthfAxzyq2N88BcBPUmT5/d7QGh55jQ` |
| 5 `ssh-copy-id` with the WSL password, then key-only login | ✅ returned `bmg-rtasseff` with no password |
| 6 manual tunnel; 6c ride it back | ✅ after one snag: 6c first failed with `REMOTE HOST IDENTIFICATION HAS CHANGED` for `[localhost]:2222`. It was a **stale** WSL `known_hosts` entry, almost certainly left by the August rehearsal, in which WSL's own sshd stood in for the box on that port (§4). Ryan removed it with `ssh-keygen -R '[localhost]:2222'`, and the re-run printed the box's hostname. |
| 7 LaunchAgent; 7d ride it back | ✅ |
| 8 before leaving | ✅ exactly one `ssh -N`, the LaunchAgent's (`… -R 2222:localhost:22 -p 2200 rtasseff@10.10.2.195`) |

**Afterwards, from the workstation, the same day:**

- Box key hardened with `WorkstationOps\setup\harden-tunnel-key.sh` at 16:03. A backup of the
  previous file is at WSL `~/.ssh/authorized_keys.bak.20261001160305`. Re-checked afterwards: the
  tunnel still carried the box's banner.
- Box egress address read from the forwarder's open connection: `10.10.3.168` (NI-RA-03).
- Data Office key added to the box. Ryan ran `ssh-copy-id -i ~/.ssh/id_ed25519.pub -p 2222
  molecubes@localhost` in WSL, typing the Mac's password once. Passwordless login was then verified
  (`molecubess-iMac.local`, `molecubes`, macOS 11.6.5).
- Read-only checks on the box: the LaunchAgent is loaded with a PID; its log is empty; there is no
  auto-login (NI-RA-01b); the three SMB mounts are as listed in §2.

**Field card follow-ups for its next revision (rev5).** Not urgent while the box half stays
installed. Due before the card is next used:

- STEP 3: replace the `nc` banner read with the ssh check from §4.
- STEP 6c: say that `REMOTE HOST IDENTIFICATION HAS CHANGED` for `[localhost]:2222` is expected
  after a rehearsal, and give the `ssh-keygen -R` line. Or clear that entry before the trip.
- REMOVING: add the Data Office line in the box's `authorized_keys` (§6).

---

## 10. Moving the landing pad to Box A (✅ decided 2026-10-01 · procedure 🔶 DRAFT)

**Decision (Ryan, 2026-10-01):** the tunnel moves to Box A with the rest of gjesus3 RDM. This
settles **B2** in [`tasks/box_a_production_migration_plan.md`](../../tasks/box_a_production_migration_plan.md),
which asked whether to move it or leave it on this workstation as the documented exception. Box A
will also host the single ingest web app that pulls NI data through it
([`tasks/BACKLOG.md`](../../tasks/BACKLOG.md) "Ingest from one place").

**It needs no visit.** B2 assumed that re-pointing the box would cost another physical access slot.
Now that the tunnel is live, the box can be reconfigured **through the tunnel itself**. The order
below keeps a working tunnel at every step, so whatever fails, the old tunnel is still up to undo
it:

1. **Stand up a landing pad on Box A** and prove it from Box A's side, as the acceptance test does
   here (§5 step 1). Port, where sshd runs, and whether Box A has admin rights are settled then.
2. **From the box, through the current tunnel, prove that Box A is reachable** on that port, using
   the ssh check from §4 (not `nc`). The box reaches this workstation through its router; the path
   to Box A is untested.
3. **Authorize the box's existing key on Box A.** Copy the `molecubes-box` line from this
   workstation's WSL `authorized_keys`, restrictions included. No new key on the box; no private
   key moves.
4. **Install a second LaunchAgent on the box** (its own label and plist) that dials Box A. Prove it
   the way STEP 7d does — from Box A, `ssh -p 2222 molecubes@localhost hostname`. That login needs
   a Box A key in the box's `authorized_keys`: generate it **on Box A** and add its public half
   through the current tunnel. Do not copy this workstation's private key.
5. **Only then** unload and remove the agent that dials this workstation, and run
   `.\ops unschedule molecubes-tunnel` here. Removing an op from the enabled list does not remove
   its scheduled task (Box A plan §4.1).
6. **Update this document** (§2's addresses, a §9-style record) **and the field card**, whose FACTS
   block names this workstation.
