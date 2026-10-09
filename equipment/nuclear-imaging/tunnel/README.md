# The Molecubes Mac's half of the reverse SSH tunnel: source files

*Last Updated: 2026-10-09*

These are the files used at the Molecubes Mac to install the box half of the tunnel. The design,
the security posture and the history are in
[`../live_machine_remote_access.md`](../live_machine_remote_access.md). The workstation half (the
landing pad) is in WorkstationOps (`molecubes-tunnel`).

| File | What it is |
|---|---|
| `tunnel.txt` | **The field card, rev4 (2026-08-06).** Step-by-step instructions at the box, self-contained, to install the tunnel from scratch. Used on 2026-10-01. The rev5 follow-ups are listed in §9 of the remote-access doc. |
| `eus.biomagune.mfb.tunnel.plist` | The LaunchAgent that the card's step 7 installs on the Mac (`~/Library/LaunchAgents/`). It keeps the tunnel up and redials after a drop. |
| `visit_notes_2026-10-01.txt` | The notes from the install visit of 2026-10-01, verbatim, including the failed attempts. They are summarised in §9 of the remote-access doc. |

**At the Mac, use the staged copy, not this folder.** The Mac cannot reach the repo, so the card
and the plist are staged on gnuclear at `S:\gnuclear\2026\Jesus\Ryan\tunnel\`
(`/Volumes/gnuclear/2026/Jesus/Ryan/tunnel/` on the Mac). Keep the two files together: step 7b
copies the plist from the folder the card is in. To restage after editing either file here:

```
python tools/operator/stage_ni_gnuclear.py tunnel-card
```

Box A takes over the landing pad through the live tunnel, with no visit (B2, decided 2026-10-01).
The card is needed again only to re-install the box half from scratch.
