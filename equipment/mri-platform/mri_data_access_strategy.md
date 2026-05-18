# Internal MRI — data access and ingestion strategy

**Status:** 🔶 In progress — pending platform manager input
**Last updated:** 2026-05-15

## Why this doc exists

The Internal MRI platform is the **only in-scope instrument that isn't directly reachable on the network** the way the microscopes and the Nuclear Imaging platform are. That makes the ingest workflow design a bigger question than for the other instruments — it requires negotiating access with the platform manager and is gated on his policy preferences, not just on technical feasibility. This file captures what we know, the architectural options we've considered, and the questions we still need answered, so the work can pause and resume cleanly while sample-data + access conversations are in flight.

Companion files:
- [`mri_platform_description.md`](mri_platform_description.md) — vendor specs (Bruker BioSpec 11.7T and 7T)
- `tasks/tasks.md` §4.5 — task-level pickup context for the MRI ingestion round

## What we know about the acquisition environment

Observed (2026-05-15 walkthrough; treat as best-current-understanding, not gospel):

- **Acquisition machine:** local box next to the scanner, running Bruker **ParaVision**. Multiple versions coexist on the platform: **v3.6**, **v6**, **v7** — the operator stated v3.6 is the *newest* (numbering does not appear to be linear; clarify with manager).
- **Inside an "experiment":** ParaVision produces a deep, nested directory tree per experiment / study / assay set. Many files. Always the same acquisition data shape per scan; multiple scans per experiment are common.
- **Export options (researcher-driven):**
  - **Manual DICOM export** for an experiment (one experiment → many scans → DICOM series).
  - **Custom local script** that exports to **NIfTI** instead.
  - Either way, the exported files land in **the same relative path** for every experiment (the path layout is stable; the format choice is the variable).
- **Network posture:** The platform manager **does not expose the acquisition machine on the network in the same way** the other instruments are. Researchers cannot push from the acquisition machine directly to a network drive (e.g. the group's `K:` share or to `gjesus3`).
- **Researcher workflow today:** Researchers go back to *their own* machines and use **FTP** to pull files from the acquisition machine. (Some kind of FTP server is therefore running on the acq machine — the manager allows pull-style access from researcher workstations, just not push-style writes outward from the acq machine.)
- **Unknown:** whether the FTP path is reachable over the internal biomaGUNE network, over VPN, over the open internet, or some combination. The acq machine is "connected to something," and at minimum FTP traffic flows.

## Constraints to design around

These are the platform-manager preferences we should respect *until we explicitly negotiate otherwise*:

1. **No outbound writes from the acquisition machine to network drives.** (Confirmed in walkthrough.)
2. **No expectation that arbitrary software runs on the acquisition machine.** (Implied — the manager is described as protective; this is the conservative read.)
3. **FTP-from-researcher-workstation is the current sanctioned access path.** Anything we build today should work within that model.

What the manager *might* allow (worth asking, but don't presume):

- FTP credentials for our group's archival use (we read, not write).
- A future on-acq-machine helper script, on-demand only, no daemons — *if* we earn the trust by handling the FTP flow well first.

## Three viable architectures

Captured here as a tradeoff table so future-us (or a successor) understands why we chose what we chose.

|                         | Option A — Pull-from-FTP via our ingest | Option B — Push agent on the acq machine | Option C — Hybrid: agent triggers, gjesus3 pulls |
|-------------------------|-----------------------------------------|------------------------------------------|--------------------------------------------------|
| Where the code runs     | Researcher's workstation (gjesus3 mapped via SMB) | The Bruker acq machine itself            | Small agent on acq machine + worker on gjesus3 side |
| Researcher action       | One command: `python tools/ingest_raw.py -c mri_<exp>.yaml --ftp-source <host>/<path>` | One button/script after acquisition. Done. | One button/script after acquisition. Done. |
| Manager install burden  | None — FTP server already exists        | Install our small script; ensure outbound network reach to NAS | Install agent; queue/triggering infrastructure |
| Our code burden         | Extend ingest with FTP-mirror prelude (~80 LOC) or separate `ftp_mirror.py` that drops into staging, then run normal ingest. Stdlib `ftplib` covers it. | Above plus: agent for the acq machine, ParaVision-export automation, SMB-write credentials | All of A and B plus: queue/trigger system |
| Political/trust ask     | Low — just FTP creds (likely already exists for researchers) | High — software on protected equipment, outbound writes | Highest — agent plus shared queue |
| Researcher friction     | Two-step in their head (acquire → ingest), one command to run | Truly one-step | Truly one-step |

### Recommended pacing

1. **Phase 1 (now):** Pursue **Option A**. It's the smallest ask, gets us example data, and proves we handle the FTP flow well. The same architecture covers most of the MRI ingest need for the pilot.
2. **Phase 2 (later, if needed):** Propose **Option B** *only* if Phase 1 friction proves unacceptable at scale and *only* after we've earned trust with Phase 1. Frame it as "this reduces the burden on researchers; on-demand only, no daemons; you tell us what authentication / authorization you want."
3. **Option C is parked.** It's the cleanest from a workflow standpoint but the highest install + ops cost. Only reach for it if we end up with many platforms following this pattern and the queue infrastructure becomes worth it as a shared asset.

## Questions for the platform manager

Two clusters: **technical** (what we need to know to build) and **forward-looking** (gauging openness for Phase 2).

### Technical — needed for Phase 1

1. **FTP access:**
   - Hostname or IP of the FTP server on the acquisition machine
   - Username/password — same for all researchers, or per-researcher accounts?
   - Reachable from inside the biomaGUNE network (internal IP), via VPN only, or via external route?
   - Read-only mode is fine — we don't need write
   - Any rate/concurrency limits we should respect
2. **Folder layout:**
   - Typical directory structure inside an "experiment" folder — always the ParaVision pattern (`<study>/<subject>/<session>/<scan>/<pdata>/<reco>/...`) or do operators reshape before exporting?
   - Are DICOM exports and NIfTI exports placed in predictable subfolders, or alongside the raw ParaVision data?
   - Filename naming — any enforced convention, or researcher-discretion?
3. **Export mechanics:**
   - DICOM export — always manual, or can ParaVision auto-export on study completion?
   - The custom NIfTI export script — can we see a copy? (Helps us understand what metadata gets preserved/lost.)
   - Does either export produce a sidecar with original-acquisition metadata, or do we need to extract from the raw ParaVision files separately?
4. **ParaVision versions:**
   - v3.6 / v6 / v7 coexistence — all three actively used? Does the file layout / export shape differ meaningfully between versions? (We may need version-specific extraction.)

### Forward-looking — signal, don't push

5. **Future on-acq-machine helper:** Would it be acceptable, eventually, to install a small read-only script on the acq machine that helps researchers package their study for gjesus3 — purely on-demand (researcher invokes it), no auto-uploads, no daemons? Framing: "to reduce the burden of FTP+ingest into one step, *eventually*." Make clear this is gauging openness, not asking today.
6. **Outbound network access from the acq machine** — is the machine permitted any outbound network access today (e.g. to a software vendor for updates)? This determines whether Option B is network-feasible at all without policy changes.

## What Phase 1 unblocks (when FTP access lands)

Pull 2–3 representative experiment folders into local staging (ideally a mix of DICOM-exported and NIfTI-exported, ideally one from each ParaVision version if convenient). From there:

1. **Probe DICOM headers** (separate audit from collaborator XMRI; this is the internal `MRI` code path).
2. **Build `tools/ingest/dicom_metadata.py`** — DICOM full-mode metadata extractor, mirroring `tools/ingest/czi_metadata.py`. Curated `discovered.dicom_*` subset + structured `dicom:` sidecar block + full `_raw_metadata` dump. **Prerequisite for both Internal MRI and Internal Nuclear Imaging.** Tracked in `tasks/tasks.md` §3.1.
3. **Build compress-on-ingest** (.zip archive of source `.dcm` collection); `file_count` from archive central directory per the registry convention. Same prerequisite. Also §3.1.
4. **Author first `mri_bruker_*.yaml` per-instrument template** under `tools/templates/instruments/`. Likely needs path_parse to capture experiment/subject context from the deep ParaVision dir tree. May need separate templates per ParaVision version if export shapes differ.
5. **Author first per-batch config + Phase A test** under `tools/configs/`. Same rhythm as round-4 (AxioScan) and round-5 (Cell Observer).
6. **Resolve open question on instrument code:** do the 7T and 11.7T systems share `MRI` or need separate codes (e.g. `MRI7` / `MRI11`)? Tracked in `09_MODALITIES.md`.

Until FTP access lands, none of the above is blocked at the code level — we can prototype `dicom_metadata.py` against the collaborator XMRI data we already have ingested (75 acqs in production). Doing so means the extractor is in hand when sample data shows up.

## Open questions (things we don't know yet)

| ID | Question | Owner | Status |
|----|----------|-------|--------|
| MRI-ACC-01 | FTP credentials + connection details (hostname, network reach) | Platform manager | 📣 Need to ask |
| MRI-ACC-02 | Folder layout conventions inside an experiment, DICOM vs NIfTI export locations | Platform manager | 📣 Need to ask |
| MRI-ACC-03 | Custom NIfTI export script — can we see a copy? | Platform manager | 📣 Need to ask |
| MRI-ACC-04 | ParaVision version layout/export differences (v3.6 / v6 / v7) | Platform manager | 📣 Need to ask |
| MRI-ACC-05 | Future openness to on-acq-machine helper (Option B signal) | Platform manager | 📣 Gauge, don't push |
| MRI-ACC-06 | Outbound network access from acq machine — currently permitted? | Platform manager | 📣 Gauge, don't push |
| MRI-ACC-07 | Stability of FTP server (always-on? on-request? versus when machine is rebooted) | Platform manager | 📣 Need to ask |

## Meta-framing for the manager conversation

Worth saying explicitly to the manager (if the tone fits): the gjesus3 RDM system is designed so the *acquisition* environment doesn't need to change. Researchers can keep doing what they're doing today; the archival/registration steps happen on our side. We're asking for **read access** to what they already produce, not asking them to alter their workflow. That framing de-risks the conversation and signals respect for the platform's autonomy.

If a Phase 2 conversation ever happens, the same framing extends: on-demand-only helper, no daemons, no surveillance, no schedule.

## Email template (working draft)

*Not finalized — adapt before sending. Probably bilingual or whichever language fits the manager.*

> Subject: gjesus3 RDM pilot — requesting read access to MRI acquisition data
>
> Hi [name],
>
> Following on our walkthrough of the MRI acquisition workflow, I'm reaching out to request **read-only FTP access** to the acquisition machine, for the purposes of the MFB group's research data management pilot (gjesus3 RDM system).
>
> What we'd like to do, in stages:
>
> 1. Pull 2–3 representative experiment folders into our archival system as test cases, so we can build the metadata extraction and registration tools for MRI data.
> 2. Eventually, build a one-command researcher workflow ("acquire → ingest into gjesus3") that uses the same FTP path the researchers already use today. **Nothing changes on the acquisition machine.**
>
> To plan that work, a few questions:
>
> - **FTP connection details:** hostname / IP, credentials (same for everyone or per-researcher?), reachable from inside the biomaGUNE network or external only.
> - **Folder layout:** typical structure inside an experiment folder; where do the DICOM and NIfTI exports land relative to the raw ParaVision data.
> - **Export specifics:** is DICOM export always manual? Could we see a copy of the custom NIfTI export script?
> - **ParaVision versions:** v3.6 / v6 / v7 — all actively used, and do the exports differ meaningfully between them?
>
> Forward-looking, lower priority — just gauging:
>
> - Is the acquisition machine permitted any outbound network access today (e.g. for updates)?
> - Eventually, would it be acceptable to add a small read-only script on the acquisition machine that helps researchers package a study for gjesus3 in one step, on-demand only, no daemons? Just gauging openness, not asking today.
>
> Happy to discuss in person or in writing, whichever works better for you.
>
> Best,
> Ryan
