# Internal Nuclear Imaging — **live-machine** remote access (reverse SSH tunnel)

**Status:** 🔶 DRAFT — the workstation half is built and verified; the acquisition-box half is
prepared but **not yet installed** (installing it needs physical access, which is the scarce thing
this document exists to conserve).
**Last updated:** 2026-08-06 — first version. Workstation landing pad verified end to end; the
LaunchAgent and the operator field card are staged on the NAS awaiting the next access window. The
box's key is generated **on the box** during that visit — no private key is staged anywhere (§7).
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

Two pieces of NI work require running commands **on the acquisition box itself**, not on a copy of
its data:

- **Gate-0 for live-box sync** ([`tasks/STATUS.md`](../../tasks/STATUS.md)) — confirming `os.link`
  (hard-link) behaviour on the box's CIFS mount. This is the single remaining gate before the
  live-machine NI ingest can go live, and it cannot be answered from anywhere else.
- **Refreshing the evidence base** — `live_machine_data_layout_and_sync_rules.md` rests entirely on
  `S:\gnuclear\2026\Jesus\Ryan\datapath.txt`, a 295,538-line recursive dump of the box's data root
  captured during a physical visit. Every re-check of that layout currently costs another visit.

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

To use it from the workstation:

```powershell
ssh -p 2222 molecubes@localhost
```

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
| Enabling **Remote Login** (macOS SSH) | ✅ survives reboot | The only lasting change, and unavoidable — the tunnel cannot work without it. Record whether it was already on, so it can be restored. |
| Installing the **SSH key + LaunchAgent** | ✅ survives reboot | Deliberate, so the tunnel reconnects unattended. Removal is two `rm` commands plus one `launchctl` call (§6). |
| The `ssh -N` tunnel process | ❌ process-scoped | An idle TCP connection. Negligible CPU and network. |
| `caffeinate` | ❌ process-scoped | **Not used.** `pmset -g` on the box reports `sleep 0` — it already never idle-sleeps, so the assertion was redundant and was dropped rather than added. |

**Nothing about acquisition, storage, or the box's own software is touched.** The tunnel provides a
shell; it does not install dependencies, change power settings, or run anything on a schedule beyond
maintaining its own connection.

---

## 4. What is proven, and what is not

Verified from the Data Office workstation on 2026-08-05/06:

| Link | State |
|---|---|
| Firewall + routing: box → workstation on 2200 | ✅ verified from the box (`nc` succeeded) |
| SSH banner through the forwarder | ✅ verified |
| Password authentication through the forwarder | ✅ verified (interactive login reaches a WSL shell) |
| `-R` reverse forwarding through the forwarder | ✅ verified by rehearsal, with WSL standing in for the box |
| Riding the tunnel back from Windows | ✅ verified (both `wsl -d Ubuntu -- ssh …` and plain `ssh …` forms) |
| Idle survival (45 s with no traffic) | ✅ verified after the forwarder fix below |
| **The box actually running the tunnel** | 🕗 **not yet** — needs the next access window |
| Unattended reconnect via LaunchAgent | 🕗 **not yet** — installed during the same window |

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

Both are encoded in the field card and in the WorkstationOps health check, which probes the
workstation's LAN address (never loopback — `wslrelay.exe` mirrors WSL's sshd onto `127.0.0.1:2200`
and would report a healthy path when every forwarder is dead).

---

## 5. Operator procedure

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
   Last full run: **9/9 PASS, 2026-08-06**.
2. **At the box:** confirm the username and Remote Login; read a banner from the workstation
   (**not** `nc -vz`); generate a key **on the box**; push its public half with `ssh-copy-id`.
3. **Establish the proven tunnel first** (a detached `nohup ssh -N -R`), and verify it.
4. **Only then attempt the LaunchAgent**, rolling back to step 3 at the first sign of trouble.
5. **Back at the workstation:** harden the pushed key
   (`WorkstationOps\setup\harden-tunnel-key.sh`), re-confirm, then use it:
   `ssh -p 2222 molecubes@localhost`.

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
nothing at the box can fix that, and the visit is lost. This is why `setup\test-tunnel-path.sh` must
be run immediately before travelling, and why NI-RA-04 (auto-start at logon) matters more than it
first appeared.

### An easy mistake, worth stating plainly

In the `-R` option the target is **`localhost:22`** — port 22, the *box's* own sshd. The workstation's
sshd is on 2200, and that number leaks into `-R` arguments very easily (it did during drafting). A
tunnel built with `-R 2222:localhost:2200` **establishes cleanly and looks correct**, then fails only
when someone tries to come back through it — by which time the operator has left the room.

**Known and unavoidable:** enabling Remote Login needs macOS admin. If it is already on, nothing
changes.

---

## 6. Removing it

Leaves no residue beyond the two files and the Remote Login setting:

```bash
launchctl unload ~/Library/LaunchAgents/eus.biomagune.mfb.tunnel.plist
rm ~/Library/LaunchAgents/eus.biomagune.mfb.tunnel.plist
rm ~/.ssh/id_ed25519_gjesus3_tunnel
```

Then, on the workstation, drop the matching line from WSL's `~/.ssh/authorized_keys` — after which
the key is dead everywhere even if a copy survives. Turn Remote Login back off only if it was off
before (§3).

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
  the box is NAT'd, so the useful allow-list entry is its router's egress address (NI-RA-03).
- A second, **workstation-local rehearsal key** (`~/.ssh/id_ed25519_molecubes_tunnel` inside WSL,
  comment `molecubes-tunnel-2026-08-06`) exists deliberately: it lets the full tunnel path be
  re-tested from the workstation alone, without the acquisition box. It carries the same
  restrictions. Remove it with `rm ~/.ssh/id_ed25519_molecubes_tunnel*` and drop its
  `authorized_keys` line if that capability is no longer wanted.

---

## 8. Open questions

| ID | Question | Status |
|----|----------|--------|
| NI-RA-01 | Does the LaunchAgent work at all? It is **untested** and is the only part of the kit that has never run. The procedure treats it as an optional upgrade behind a proven manual tunnel for exactly this reason. | 🕗 First attempt at the next visit |
| NI-RA-01b | Does the tunnel survive a full reboot of the box, and does user `molecubes` log in automatically? A LaunchAgent starts at login, not at the login window. | 🕗 Cannot be answered until installed |
| NI-RA-02 | Was Remote Login already enabled on the box, or did we enable it? | ⚠️ Record during the next visit |
| NI-RA-03 | What is the box's egress address as seen by the workstation? Needed before any forwarder allow-list. | ⚠️ Capture from `sshd` logs on first real connection |
| NI-RA-04 | Should the workstation landing pad auto-start at logon? Requires a `Logon` trigger that `WorkstationOps\lib\scheduled-task.ps1` does not yet support. **Raised in priority:** arriving to find the landing pad down is the one failure with no recovery from inside the restricted room, and it costs the whole visit. | ❓ Deferred, but revisit before the visit after next |
| NI-RA-05 | Does Gate-0 (`os.link` on the box's CIFS mount) pass once remote access is available? | 🕗 The first real task for this tunnel |
