# Backlog triage — 2026-10-10

**Why:** production moves to a dedicated box (Box A) soon, and the system goes from pilot to a
fully functioning system for one group. Before that, Ryan wants a big chunk of the backlog worked
through. This triage orders [`BACKLOG.md`](BACKLOG.md), groups items that belong in the same
branch, and posts each group as a **GitHub issue** with labels and a milestone. From here on:

- **GitHub issues are the working list for the push** (one issue per branch-sized unit of work;
  its checklist is the scope). <https://github.com/Rtasseff/gjesus3-pilot/issues>
- **`BACKLOG.md` keeps the detail** (the evidence, the measurements, the reasoning); each issue
  names the sections it draws on. When an issue closes, tick or strike its items in `BACKLOG.md`
  and add the CHANGELOG row as usual. Nothing in `BACKLOG.md` was rewritten by this triage.
- **The handoff rule still applies:** a session starting an issue cuts the worktree named in the
  issue's "Proposed branch" line and writes `HANDOFF.md` per `CLAUDE.md`.

## The scheme

| Milestone | Meaning |
|---|---|
| **M1 — Before the port: the big chunk** | Correctness gaps, prerequisites for a second machine, anything cheaper while one box runs everything. |
| **M2 — The Box A port** | Executing [`box_a_production_migration_plan.md`](box_a_production_migration_plan.md). |
| **M3 — After the port: single-group production** | The web app, the metadata database, researcher-facing features. |
| **Held — waiting for a trigger** | Parked by ruling; each issue names its trigger. |

Labels: `priority: high / medium / low`; `area: *` (ingest-engine, registry, validator, operator-gui,
project-manager, finder-search, ni, mri, microscopy, external-data, privacy, metadata-model,
projects, curated-datasets, docs, infra, repo, web-app); `status: needs-decision` (Ryan),
`status: needs-external` (platform / facility / researcher / IT), `status: production-write`
(dry run + Ryan's go), `status: exe-rebuild`, `status: held`. Issue types: Task / Bug / Feature.

## M1 — Before the port, in suggested order

The ingest-engine branches (#7 → #6 → #5 → #14 → #15) touch the same files, so run them **one at a
time**, in that order, and rebuild the exes once at the end (#23). Everything else can run beside
them.

| # | Issue | Branch | Why this position |
|---|---|---|---|
| [#3](https://github.com/Rtasseff/gjesus3-pilot/issues/3) | Box A Phase 0: memory into git; WorkstationOps per-instance config | (other repos) | Hours of work; closes a live single-copy exposure; a prerequisite for a second machine. |
| [#4](https://github.com/Rtasseff/gjesus3-pilot/issues/4) | Off-site backup / DR; schedule `verify_checksums` weekly | none / WorkstationOps | The #1 unmitigated risk; a purchase decision plus one small op. |
| [#12](https://github.com/Rtasseff/gjesus3-pilot/issues/12) | Recover the 103 `pending-db` rows | none | One operation with the fixed tool; needs Ryan's go only. |
| [#7](https://github.com/Rtasseff/gjesus3-pilot/issues/7) | Ingest engine small fixes (silent today's-date fallback, …) | `fix/ingest-small-fixes` | First of the engine chain; the date bug has corrupted production once. |
| [#6](https://github.com/Rtasseff/gjesus3-pilot/issues/6) | Ingest reports what it did not register (non-image skip, `pending_unparsed.csv`, unseen files, phantom branch) | `feat/ingest-skip-reporting` | A spectroscopy exam from the scanner is still registered as a placeholder today. |
| [#5](https://github.com/Rtasseff/gjesus3-pilot/issues/5) | Dedup identity: content/instrument-anchored key | `feat/dedup-key` | Production evidence (32 duplicates) says the key is wrong; every bulk ingest works around it by hand. |
| [#8](https://github.com/Rtasseff/gjesus3-pilot/issues/8) | Validator signal: collapse, coverage lines, orphan + plausibility checks, scheduled runs | `feat/validator-signal` | The validator is the gate for every write; today its warnings are unread. Independent of the engine chain. |
| [#2](https://github.com/Rtasseff/gjesus3-pilot/issues/2) | Human data: `privacy_restricted` flag + DPA record | `feat/human-data-handling` | Ryan's top priority of 2026-10-02; decisions first, then one branch. |
| [#10](https://github.com/Rtasseff/gjesus3-pilot/issues/10) | Project lifecycle (`projects_closed\`, what `closed` does, dates maintained, owner = researcher, UTF-8) | `feat/project-lifecycle` | The spec contradicts itself and eight projects have been closed-then-reopened; settle before handing the system to the group. |
| [#9](https://github.com/Rtasseff/gjesus3-pilot/issues/9) | NI subject naming standard: rule, enforce by refusing | `feat/ni-subject-standard` | Was to ship with the live sync; the live sync shipped 2026-10-09. |
| [#14](https://github.com/Rtasseff/gjesus3-pilot/issues/14) | Ingest write guards (pre-lock dedup, production `--nas-root` guard, batch-window flag, linker residuals) | `fix/ingest-write-guards` | Must land before any concurrent or automated ingest; Box A schedules jobs. |
| [#15](https://github.com/Rtasseff/gjesus3-pilot/issues/15) | Person attribution in the tools | `feat/person-attribution` | "The tools will prompt for operator or researcher" (Ryan) — they do not yet enforce it. |
| [#23](https://github.com/Rtasseff/gjesus3-pilot/issues/23) | Rebuild + redeploy both exes | none (deploy) | One deploy after the engine chain; operators still cannot see NOT PARSED (N3). |
| [#11](https://github.com/Rtasseff/gjesus3-pilot/issues/11) | Historical drives: the 2b round, holding, `.mhd` headers, pig remap, workbook appends | `feat/drives-2b-round` | 54,721 files sit outside every project; waits on the group's workbook answers. |
| [#13](https://github.com/Rtasseff/gjesus3-pilot/issues/13) | Operator claim window close-out (D1c) | none | Dated to the window's end, which Ryan sets. |
| [#16](https://github.com/Rtasseff/gjesus3-pilot/issues/16) | `researcher` name convention | `feat/researcher-convention` | Waits on the group's answer; then one migration. |
| [#18](https://github.com/Rtasseff/gjesus3-pilot/issues/18) | Subject-identity questions needing a person | none | One round of asks while the sessions are in living memory. |
| [#19](https://github.com/Rtasseff/gjesus3-pilot/issues/19) | MFB data still not in gjesus3 (N1/N2/N4/N6/N7, H2, 160 NI, 233 archive exams, …) | none | Rulings; none urgent (the platform archives what leaves the scanner). |
| [#17](https://github.com/Rtasseff/gjesus3-pilot/issues/17) | Audit production `.czi` for truncated primaries | `feat/czi-truncation-audit` | Two known cases; complete copies get harder to find with time. |
| [#20](https://github.com/Rtasseff/gjesus3-pilot/issues/20) | Docs pre-port sweep | `docs/pre-port-sweep` | A new box and new users should meet docs that match the code. |
| [#21](https://github.com/Rtasseff/gjesus3-pilot/issues/21) | Repo hygiene: spent branches; the `contacts.xlsx` purge decision | none | The purge's window is "before Box A clones". |
| [#22](https://github.com/Rtasseff/gjesus3-pilot/issues/22) | Tools consolidation: archive spent scripts, lift helpers, one test suite | `refactor/tools-consolidation` | Do the test-suite half first (cheap, helps every branch) and the helper lift **after** the engine chain merges, to avoid conflicts. |
| [#24](https://github.com/Rtasseff/gjesus3-pilot/issues/24) | Enrichment follow-ups | `feat/enrichment-followups` | Small; whenever a session is in `enrichment.py`. |
| [#25](https://github.com/Rtasseff/gjesus3-pilot/issues/25) | Odds and ends for Ryan | none | One-line rulings. |

## M2 — The Box A port

| # | Issue | Branch |
|---|---|---|
| [#26](https://github.com/Rtasseff/gjesus3-pilot/issues/26) | Execute the migration plan, Phases 1–6; decide B1, B3, B4 first | none (operations) + small doc branches |
| [#27](https://github.com/Rtasseff/gjesus3-pilot/issues/27) | NI after Box A: pull through the tunnel; the Mac stops mounting gjesus3 | `feat/ni-boxa-pull` |

## M3 — After the port: single-group production

| # | Issue | Branch |
|---|---|---|
| [#28](https://github.com/Rtasseff/gjesus3-pilot/issues/28) | One web app on Box A (design first) | design note, then `feat/web-app` |
| [#29](https://github.com/Rtasseff/gjesus3-pilot/issues/29) | Metadata database; a `status` column for retired acquisitions | design note, then `feat/metadata-db` |
| [#30](https://github.com/Rtasseff/gjesus3-pilot/issues/30) | Finder and search: index spike; provenance-driven project index | `feat/search-index-spike` |
| [#31](https://github.com/Rtasseff/gjesus3-pilot/issues/31) | Condition rules per acquisition, filter OR, GUI region field, assisted vocabulary | `feat/condition-rules` |
| [#32](https://github.com/Rtasseff/gjesus3-pilot/issues/32) | External collaborator archives: unit, container, DICOM full-mode, LEONE, echo code | `feat/external-archives` |
| [#33](https://github.com/Rtasseff/gjesus3-pilot/issues/33) | Study-level metadata / ISA (META-10, META-11), Excel importer | design note, then `feat/study-metadata` |
| [#34](https://github.com/Rtasseff/gjesus3-pilot/issues/34) | Second-stage tools: NIfTI derivatives ([#1](https://github.com/Rtasseff/gjesus3-pilot/issues/1)), `create_publication`, `log_activity`, `--lightweight`, spectroscopy | one per tool |
| [#35](https://github.com/Rtasseff/gjesus3-pilot/issues/35) | Decouple enrichment from the live animal-facility DB | `feat/enrichment-decouple` |
| [#36](https://github.com/Rtasseff/gjesus3-pilot/issues/36) | Curated datasets after the pilot: re-trace (CAND-A), lung-lobe ROI, spec gaps with SegBioMed | none / `docs/cds-spec-gaps` |
| [#37](https://github.com/Rtasseff/gjesus3-pilot/issues/37) | Conversations with IT and the DPO: `projects/` mirror, the cap in writing, access logging | none |
| [#38](https://github.com/Rtasseff/gjesus3-pilot/issues/38) | `stage_copy.py` 1.5's four known limits | `fix/stage-copy-limits` |

## Held — waiting for a trigger

| # | Issue | Trigger |
|---|---|---|
| [#39](https://github.com/Rtasseff/gjesus3-pilot/issues/39) | MILabs VECTor onboarding + the 2026 lung study identities | D8: pull, after the cardiac pipeline |
| [#40](https://github.com/Rtasseff/gjesus3-pilot/issues/40) | The cardiac MRI segmentation pipeline; mint `SegBioMed` | D8 / D6 |

## Where every `BACKLOG.md` section went

| `BACKLOG.md` section | Issue(s) | Note |
|---|---|---|
| 🔺 a registry flag for human, privacy-restricted data | #2 | |
| 🔺 record the DPA for every external dataset | #2 | |
| 🔺 292 `pending-db` subject rows | #12 (the 103), #18 (the 188), #24 (`append_pending`) | |
| 🔺 a second acquisition with an existing link name | #14, #23 | Core done 2026-10-05; two LOW tails. |
| 🔺 port gjesus3 RDM production onto Box A | #3, #26 | |
| Ingest from one place — one web app on Box A | #27, #28 | |
| Operator person/PI metadata (NI + MRI) | #15 | |
| Cross-instrument identity / naming | #15 | |
| Microscopy GUI; GUI operator-feedback follow-ups | #31 (rules, OR, region), #15 (researcher required), #20 (README refresh) | |
| Dedup identity | #5; the same-timestamp tail → #11 | Retirements done. |
| Person/role rename — residual cleanup | #10 (owner), #15 (placeholder, AxioScan, `animal_id`), #20 (roster, prose, enum) | |
| Nuclear Imaging — live-machine import (2026-06-10) | — | **Superseded** by the live sync (in production 2026-10-09). Candidate to strike. |
| NI live-sync — Mac-compiled GUI | #27, #28 | **Superseded** by the web app / Box A pull; Ryan to confirm. |
| Independent / second-stage tooling | #34, #32 (DICOM full-mode), #33 (Excel importer) | |
| Doc placement — the `equipment/` line | #20 | |
| Doc placement — no-DICOM runbook | — | Done 2026-07-16. |
| Repo / git hygiene | #21 | |
| Misc (`extract_study_date`, `summarize_source`, override flags) | #7, #15 | |
| Metadata vocabularies & search | #31 (vocabulary), #30 (search DB) | |
| Metadata model — `user_provided_metadata` (META-10/11) | #33 | |
| Human-subject data — policy beyond the ingest (META-12) | #2 | |
| 🔸 batch window flag | #14 | |
| 🔸 closed projects MOVED, not deleted | #10 | |
| 🔸 `status` column for retired acquisitions; 🔽 quarantine | #29 | |
| 🔸 no ingest maintains `start_date` / `last_activity` | #10 | |
| 🔸 audit production `.czi` for truncated primaries | #17 | |
| 🔸 `researcher` name convention | #16 | |
| ✅ MRI GUI project tokens | — | Done 2026-09-04. |
| 🔺 external archives one row per EXAM; 🔸 one container | #32 | |
| 🕗 HELD three builds; 🕗 mint `SegBioMed`; 🔸 MILabs | #40, #39 | |
| 🔺 ParaVision study dropped silently | #6 (tails), #19 (re-pulls) | Core done 2026-10-05 (D3). |
| 🔺 `m39` is probably `m37` | #18 | |
| 🔸 curated-datasets pilot: 19 spec gaps | #36 | |
| 🔺 2026 NI lung study identities | #39 | |
| 🔸 internal MRI older than ~2022-01 | #19, #40 | Largely answered by the drives and the archive ingest. |
| 🔸 curated datasets: CDS-01 decided | #36 | |
| 🔺 `operator` column (c) | #13; validator collapse → #8; docstrings → #20 | |
| 🔺 NI subject label has no format | #9 | |
| 🔸 plausibility checks | #8 | |
| 🔸 4 PET PatientID conflicts | #18; console norm → #9 | |
| 🔽 5 acquisitions before DOB | #18 | |
| 🔸 validator warning channel saturated | #8 | |
| 🔽 what we owe the XNAT trial | #18 | |
| 🔸 OPTIONAL move/mirror `projects/` to IT `gjesus` | #37 | |
| ✅ Finder select → assemble | — | Done 2026-08-12 (Project Manager). |
| Finder — provenance-driven project index | #30 | |
| sidecars carry platform-dependent line endings | #7 | |
| Multi-value cell hygiene | #8 | |
| 🔸 17 orphan folders (the rule) | #8 | The 17 were retired 2026-10-02. |
| 🔸 14 MFB sessions on the scanner | #19 (H2), #8 (scheduled reconciliation) | |
| 🔹 keep `staging\sftp_20260716_110906` | #19 | |
| 🔹 preview ignores `.acq_id_seq.json` | #7 | |
| 🔹 anatomy rule on Dicomifier DICOMs | #24 | |
| 🔹 NIfTI folders next to studies | #25 | |
| 🔸 MRI rows outside the 2026-10-04 line | #6 (the live skip) | The 464 were retired 2026-10-09. |
| 🔹 exam with no data gets today's date | #7 | |
| 🔹 phantom/QC need a scoped config | #6 | |
| 🔹 another group's study inside m3's folder | #25 | |
| 🔹 WSL write 20× slower | — | No action; 11_OPERATIONS §5.5 already carries the constraint. Plan windows by file count. |
| 🔹 `stage_copy.py` four limits | #38 | |
| 🔸 drive-3 vs originals; re-trace | #36 | The originals check was done 2026-10-08 (none differs). |
| 🔸 `S:\gnuclear` discovery fallback | #19 (the 160) | Fix merged 2026-10-06. |
| 🔹 a home for in-house tools and models | #25 | |
| 🔹 10 `_project.yaml` not UTF-8 | #10 | |
| 🔹 165 pig files in holding | #11 | |
| 🔹 claim workbook lists retired placeholders | #11, #13 | |
| 🔹 the archive's 233 unregistered exams | #19 | |
| 🔸 231 `.mhd` headers | #11 | |
| 🔹 M. Jesús drive late answers | #25 | |
| 🔹 106 converted DICOM vs the scanner's | #19 | |
| 🔹 assign workbook's append | #11 | |
| 🔸 drives' DICOM stream follow-ups | #7 (`_scanner_model`), #19, #18 (Claudia), #32 (X1 shape) | |
| 🔺 historical drives: the 2b round | #11 | |
| 🔸 holding-folder access, held material | #11 | |
| 🔹 small follow-ups from the drives | #18 (Lucia), #25 (CoS hub) | |
| Metadata database — retire the CSV registries | #29 | |
| 🔹 per-user access logging | #37, #28 | |
| Server-era identity | #28 | |
| Project Manager GUI — deferred scope | #10 | |
| True-production restart — subsystem review | #20 | Re-scope to the port, or close. |
| MRI anatomy back-fill + auto-derive | #24 (optional guess) | Done 2026-06-14 otherwise. |
| Microscopy anatomy from the organ suffix | #24 (confirmations) | Done 2026-06-14 otherwise. |
| AxioScan MFB ingest — Phase 2 follow-ups | — | All done 2026-06-15. |
| Facility-DB null project alias | #18 (the external ask) | gjesus3 side closed 2026-08-17. |
| Spectroscopy / non-image MRI | #34 | |
| MRI link-name collisions (2026-06-14) | — | Superseded 2026-10-05. |
| Legacy Zeiss best-guess ingest | #10 (re-projection via the project review), #7 (`.czi` strip) | The K: ingests ran 2026-06-15 and the drives since. |
| NI tracer compound; `reconparams.txt` | #24 (optional) | No action on the tracer: study-level knowledge. |
| Server-side raw ingest + downstream Windows tool | #28 | |
| No-DICOM regeneration on Windows — research finding | — | Reference; informs B3 (#26) and #28. |
| Enrichment `condition:` block for tissue/cells | #24 | |
| Architecture & code review follow-through | #4 (DR, schedule), #14 (§3.1 #1, #5–#8), #22 (§2.1), #26 (§3.2.4), #30 (§3.2.2), #35 (§3.2.3), #20 (§2.2–2.4) | |
| Ingest safety + audit-table clarity | #14 (guard), #20 (inventory pointer) | |
