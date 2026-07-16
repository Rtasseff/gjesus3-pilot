# Handoff — MRI no-DICOM regeneration: backfill the DICOMs, then make the procedure official

**Created:** 2026-07-16 · **Branch:** `feat/dicom-regen-backfill` · **Worktree:**
`…/projects/gjesus3-dev/dicom-regen-backfill` (a worktree of the main repo at
`…/RDM/highCap/gjesus3-pilot`, branched from `main` @ `6ded455`).

**Status:** Investigation + staging done; **no fix started**. This document is the
brief. Read it end-to-end before touching code — the first work item is a design
question, not a code change, and getting it wrong writes duplicate rows to true
production.

---

## 0. TL;DR — what needs to happen, in order

1. **Settle the dedup design first** (§4.1). Decide *what the ingest dedup keys on
   and why*, and *where a "fill an already-registered acquisition" operation
   belongs*. This is the blocker; everything else depends on the answer. It is **not**
   a documentation fix (that was an early mis-framing — see §3).
2. **Build the backfill CLI** (§4.2) — the thing everyone assumed already existed and
   does not. Worklist-driven, RDM-team-run, updates in place, dry-run by default.
   Model it on `tools/recover_subject_metadata.py` (the established precedent, §2.2).
3. **Run it** against the 153 regenerable exams already staged on `D:` (§2.4).
4. **Decide the 94 no-source rows and the classifier gap** (§4.3, §4.4).
5. **Make the runbook official policy** (§4.5): integrate the right parts into
   `mfb-rdm-docs/10_TOOLS.md` + `11_OPERATIONS.md` and the `tools/` CLI docs, **fix the
   false idempotency claim**, then move the runbook to `tasks/archive/` and repoint
   every inbound link at the new official homes (not at the archive path).

A terminology note before anything else: earlier work used the word **"drain"** for
"work the pending list and fill the missing DICOMs." That term is not used anywhere in
this project and should be dropped. The correct word is **backfill** — the same word
the subject-metadata precedent uses.

---

## 1. The one-paragraph problem

Some historical MRI (ParaVision) exams were ingested **without DICOM images** — the
researcher never ran Bruker's exporter, and Dicomifier (which can regenerate the DICOMs
from `2dseq` + JCAMP-DX) was not available on the machine that ran the ingest. Each such
acquisition is **registered and findable** with a full `metadata.json`, but its
`<ACQ-ID>.data/` folder is **empty** — a placeholder. There are **612** of these. They
must be filled in later by the Research Data Management team. That "fill it later" step —
the tool and the procedure — is what is missing.

This is the **same shape** as the existing subject-metadata recovery (§2.2): register
with a placeholder at ingest, queue it, let the RDM team fill it afterwards from a
machine that has what the ingest lacked. It differs in one way that matters (§4.2): the
DICOM fill must also **update the registry row**, which the metadata precedent never does.

---

## 2. Context — how we got here, and what already exists

### 2.1 The discovery chain (2026-07-14 → 07-16)
A production-data pass turned up a bug that unravelled into this:

1. **The age bug.** 92 no-DICOM MRI acquisitions carried an `age_at_acquisition`
   computed against their *ingest* date (the ingest fell back to `datetime.now()` for
   the ACQ-ID prefix when `acquisition_datetime` was blank, and the enrichment writer
   treated that placeholder as real). Fixed at the call site; the 92 sidecars were
   blanked. (Commit `f567fae`; `CHANGELOG.md` 2026-07-15.)
2. **The bigger gap.** Chasing those 92 revealed **612** DICOM-less acquisitions, and
   that the worklist meant to track them — `registries/pending_dicom_regen.csv` — **had
   never been created**. Not a leak: the auto-queue code landed 2026-06-24 (`6dce5f9`),
   but every placeholder was ingested 2026-06-13/14, ten days earlier, and no MRI has
   been ingested since. So they were registered nowhere. `tools/backfill_pending_dicom.py`
   was written to enrol them retroactively. (Commit `38f1dfd`.)
3. **The classifier gap.** Of the 612, **365 are non-image** (spectroscopy/calibration:
   STEAM 286, PRESS 74, WOBBLE 5) which `paravision_regen` refuses by design — DICOM
   regeneration can never apply to them. They were being filed `pending`, which made the
   worklist look undrainable. Now filed `not-applicable` with a `nonimage_marker`
   column. (Commit `9ace495`.) **But the classifier may be too narrow — see §4.4.**
4. **The pull.** The 247 `pending` rows span 121 ParaVision study folders on the
   platform host `kenia`. Staged to local scratch overnight (§2.4).
5. **The reality check.** Verifying the staged data showed only **153** of the 247 have a
   `pdata/<idx>/2dseq` — the input Dicomifier actually converts. The other **94 cannot
   be regenerated from kenia at all** (§4.3). So the real backfill set is **153**, not 612.

Net: of 612 DICOM-less acquisitions → **365 not-applicable · 94 no source · 153 backfillable.**

### 2.2 The precedent that already works — `tools/recover_subject_metadata.py`
When a live ingest can't reach the animal-facility DB (no credentials on the operator's
machine, or the DB lags the acquisition), the acquisition **still ingests** with a
placeholder `subject:` block (`source="pending-db"`), and a row is queued to
`registries/pending_subject_metadata.csv`. Later, an RDM-team member on a machine that
*does* hold credentials runs this tool, which:

1. walks the pending list for `status == "pending"`;
2. re-attempts the resolution (the DB lookup);
3. on success, **writes into the immutable `/raw` sidecar in place** — filling only
   blank/placeholder fields, never overwriting a real value;
4. **verifies after write** (re-reads from disk; rolls back + stays pending on failure);
5. flips the row to `status="recovered"` + `recovered_at`.
Safeguards: **dry-run by default** (`--apply` to write), idempotent, never auto-marks
"unresolvable" (a human call). **This is the pattern to copy for DICOMs.**

⚠️ **One critical difference:** `recover_subject_metadata` touches **only the sidecar +
the pending list — never `registry_raw.csv`** (verified: no registry writes in the file).
The DICOM backfill *must* update the registry row (§4.2). That is the one genuinely new
capability; do not assume the precedent covers it.

### 2.3 What exists today (inventory — do not rebuild these)
| File | Role | State |
|---|---|---|
| `tools/ingest/paravision_regen.py` | The conversion engine: Dicomifier subprocess + the two PV-7 image fixes (PixelSpacing axis-swap, invalid Window tags) + non-image refusal (`is_nonimage_exam`). | **Works; visually validated 2026-06-01.** |
| `tools/ingest/pending_dicom.py` | The worklist module: read/write `pending_dicom_regen.csv`, the `status` domain (`pending`/`not-applicable`/`regenerated`), `nonimage_marker`. | Current. |
| `tools/backfill_pending_dicom.py` | **Enrols** placeholders into the worklist (one-time catch-up + invariant checker). Does **not** regenerate. | Current. |
| `tools/pull_pending_dicom_sources.py` | **Stages** the source studies from `kenia` to local scratch (read-only). Does **not** regenerate. | Current; already run (§2.4). |
| `tools/relink_mri_regen.py` | Rebuilds project hard-links after a WSL regen (`os.link` is refused over the CIFS mount from WSL). | Current. |
| `tools/validate_dicomifier_pixelspacing.py` | Post-regen sanity check on an `<ACQ-ID>.data/`. | Current. |
| `tools/recover_subject_metadata.py` | The **pattern to follow** (§2.2). | Current. |
| `equipment/mri-platform/mri_no_dicom_regeneration_runbook.md` | The operator runbook (✅ DECIDED). Describes the **inline** flow only, and **contains a false idempotency claim** (§4.1). | Needs §4.5. |

**The missing piece:** a worklist-driven **backfill CLI** — read `pending_dicom_regen.csv`,
regenerate each `pending` exam from the staged source, write into the existing
`<ACQ-ID>.data/`, update the registry row, flip to `regenerated`. **This is §4.2.** It was
believed to exist as a one-line SOP; it does not (see §3).

### 2.4 The staged source data (already pulled)
- **Location:** `D:\temp\mri_regen_20260715\PV<version>\<study>\` (log:
  `D:\temp\mri_regen_20260715_pull.log`). **D: is NOT backed up** — this is disposable
  scratch (primary is `kenia`); re-pull with `pull_pending_dicom_sources.py` if lost.
- **What it is:** 121/121 study folders, 33,308 files, **43.11 GB**, pulled read-only in
  15.4 min on 2026-07-15. All 121 study-level `subject` files present; 0 corrupt/partial.
- **Readiness (verified per-exam):** of the 247 `pending`, **153 have `pdata/<idx>/2dseq`
  (backfillable)**; 94 do not (80 header-only, 14 `fid`-only — §4.3).
- **Note:** 40% of the 43 GB is `fid`, which Dicomifier never reads. Whole-study mirroring
  was the correct call (the study-level `subject` is required and lives one level up from
  the exam), but a `fid` exclude would cut the transfer ~40% if repeated.

### 2.5 Environment for regeneration (from the runbook — still accurate)
Dicomifier is a Linux/conda tool: run the regen from **WSL** with
`conda env create -f tools/dicomifier-pilot.environment.yml` then
`conda activate dicomifier-pilot` (Dicomifier 2.5.3+). Two gotchas the historical run hit:
`pymysql` + DB creds must be visible to WSL (else every subject goes `pending-db`), and
**`os.link` is refused over the CIFS NAS mount from WSL** — so after a WSL regen, project
hard-links must be rebuilt from **Windows** via `relink_mri_regen.py`. The NAS is at
`/mnt/gjesus3` in WSL (= `J:\` on Windows).

---

## 3. Correcting two early mis-framings (so they are not repeated)

**Mis-framing A — "the runbook is just wrong; fix the doc."** The runbook *does* contain a
false claim (§4.1), but the claim is a symptom. The real issue is a **design question about
the dedup** — what it keys on and whether a fill-in-place operation should go through the
ingest at all. Fixing the sentence without settling the design would paper over it. Treat
§4.1 as design-first.

**Mis-framing B — "the pipeline has no update path, this needs new architecture."** Wrong,
and it wasted a cycle. The RDM system *does* have an established "fill part of an
already-registered acquisition later" pattern — it is `recover_subject_metadata.py` (§2.2).
The in-place-update machinery lives in the **recovery tools**, not in `ingest_raw`. Start
from that pattern. The only real new work is that the DICOM case must also update the
**registry row** (§4.2), which the metadata precedent doesn't do.

**On the "one-line SOP we thought existed":** it does not exist, and never did. Git history
confirms DICOM regeneration has **only ever run inline** via the `auto_regenerate_dicom`
ingest flag (wired in `5b02ef2`; runbook entry `CHANGELOG.md` 2026-06-12: *"the conversion
code + the auto_regenerate_dicom ingest flag already existed"*). The round-6 "backfill" was
regeneration happening **during** the ingest (in WSL, where Dicomifier was present), not a
separate worklist-driven pass. A standalone SOP was reasonably assumed but was either never
built or dropped — either way, building it is §4.2.

---

## 4. The work items

### 4.1 ⛔ FIRST: settle the dedup design (blocker for everything else)

**The question:** the ingest's idempotency dedup (`tools/ingest/config.py`) keys a
would-be ingest as "already done" on **`(acq_date, original_name)` being present in
`registry_raw.csv`**. It **never checks whether the acquisition's `.data/` is empty.**
Because the no-DICOM path *registers* the placeholder row, a plain re-run of the same
config **skips all of them** — empirically verified: **612 of 612 would dedupe-skip.** So
the runbook's promise (§4.5) that a re-run "fills the `.data/`" is false.

**History (answers the "did it change?" question).** The dedup key changed in **`f5fefa5`
(2026-05-28)** — the *same commit* as "Round-6 MRI v2". But not toward emptiness-awareness:
it **removed** a `("", original_name)` "name-alone" safety key because that caused
false-positive dedups when exam-number basenames repeated across sessions. It was keyed on
registry-presence of `(acq_date, original_name)` both before and after — **`.data/`
emptiness was never part of the key.** So the intuition that "it may have keyed on empty
`.data/` during the MRI work and then changed" is worth stating plainly: **the git record
shows it never did.** Confirm independently (`git show f5fefa5 -- tools/ingest/config.py`,
and `_build_dedupe_index` / `existing_keys` in `config.py`) before relying on this.

**The decision to make — where does "fill an already-registered acquisition" belong?**
Three shapes, with the trade-off:
- **(a) A separate backfill tool that does not go through the ingest dedup at all**
  (the `recover_subject_metadata` shape). It reads the worklist, regenerates, and updates
  the existing acquisition in place — keeping its ACQ-ID. **Recommended** (§4.2): it
  matches the established precedent and sidesteps the dedup entirely. Cost: it needs the
  new registry-row-update capability.
- **(b) Make the ingest dedup `.data/`-aware** — let a re-run through when the registered
  acquisition's `.data/` is empty. Keeps one code path, but re-running the *ingest* to
  *update* an existing row is a bigger behavioural change than it looks: see the ACQ-ID
  trap below, plus it changes semantics for every ecosystem, not just MRI.
- **(c) A `--force` / `--refill` flag on the ingest.** ⚠️ **The dangerous one.** The
  ACQ-ID is allocated **inside `ingest_single`**, *downstream* of the dedup. So merely
  bypassing the dedup mints a **new** ACQ-ID, creates a **second** `/raw/` folder, and
  appends a **duplicate** registry row for the same exam — silently, on true production.
  This is the "worse mistake" to avoid; document *why* it's wrong so nobody reaches for it.

**Recommendation:** (a). But this is the data office's design call — it is why this item is
first and why nothing else should start until it's answered.

### 4.2 Build the backfill CLI (the missing piece)
Model on `recover_subject_metadata.py`. Proposed shape (`tools/backfill_dicom_regen.py`,
name open):
- Read `registries/pending_dicom_regen.csv`; take `status == "pending"`.
- For each, locate its staged source (`D:\temp\mri_regen_20260715\PV<pv>\<study>\<exam>`,
  from `original_name` + `paravision_version`), regenerate via
  `paravision_regen.prepare_virtual_exam` / `regenerate_exam_dicoms`, applying the two
  PV-7 fixes (already in that module).
- Write the DICOMs into the **existing** `<ACQ-ID>.data/` (keep the ACQ-ID — §4.1).
- **Update the registry row** (the new capability `recover_subject_metadata` lacks):
  `file_count`, `file_size_mb`, `checksum_present`, and — importantly — a **real
  `acquisition_datetime`** now discoverable from the regenerated DICOM's StudyDate. That
  in turn lets `age_at_acquisition` be recomputed correctly (closing the last of the age
  bug). Refresh `checksums.json`. `registry.py` currently has only `append_row`; an
  update-a-row capability must be added, under the registry lock, atomically.
- Flip the worklist row to `status="regenerated"`.
- **Mandatory guardrails (copy from the precedent):** dry-run by default (`--apply` to
  write); verify-after-write (re-read the `.data/`, run
  `validate_dicomifier_pixelspacing`); idempotent (a `regenerated` row is skipped);
  non-image rows skipped; never touch a row whose `.data/` is already populated.
- After a WSL run, rebuild project hard-links from Windows via `relink_mri_regen.py`.
- **153** exams are ready to run against right now (§2.4).

### 4.3 Decide the 94 exams with no regenerable source
Of the 247 `pending`, **94 cannot be regenerated from kenia**: **80** have neither `2dseq`
nor `fid` (only headers — `acqp`/`method`/`reco`; aborted or never-reconstructed scans),
**14** have `fid` only (raw k-space, never reconstructed — Dicomifier can't use it; would
need ParaVision reconstruction first). They are not "pending" in any real sense — nothing
will ever fill them. **They need an honest status** (e.g. a new `unrecoverable` /
`no-source` value, with the reason). Do not leave them `pending` — that makes the worklist
permanently non-empty and hides the real 153. **Data-office call on the status name +
whether the 14 fid-only are worth a ParaVision-reconstruction path.**

### 4.4 Widen the non-image classifier (probably)
`paravision_regen._NONIMAGE_METHOD_MARKERS = ("STEAM", "PRESS", "WOBBLE")`. Several of the
94 no-source exams contain `specpar`, `b0`, `AdjStatePerScan` — signatures of spectroscopy
and adjustment/calibration scans that the current three markers don't catch. If the
classifier is too narrow, some of those 94 are really §4.3-non-image and, more importantly,
**future ingests will keep mis-filing them** as regenerable. Review the real method/protocol
names across the 94 and decide whether to extend the marker set. This affects the live
ingest path (`ingest_raw.py` queue site), not just the backlog.

### 4.5 Make the runbook official policy, then archive it
Once §4.1–4.2 land and the procedure is real:
1. **Integrate the durable parts into official docs** (not `equipment/`):
   - **`mfb-rdm-docs/10_TOOLS.md`** — the tool/spec reference (the backfill CLI, the
     worklist schema + status domain, `paravision_regen`).
   - **`mfb-rdm-docs/11_OPERATIONS.md`** — the operational procedure (when/who/how the RDM
     team runs the backfill; the WSL env; the relink-from-Windows step).
   - **`tools/` docs** (e.g. `INGEST_CLI.md` / a tool doc) — how the CLI is actually called.
2. **Fix the false idempotency claim** in the runbook §2/§6 **before** it is archived —
   `tasks/archive/` is never-edited, so a wrong claim frozen there is permanent.
3. **Move** `equipment/mri-platform/mri_no_dicom_regeneration_runbook.md` →
   `tasks/archive/` (it documents *our* tooling, not platform reality — see the
   `equipment/` boundary item in `tasks/BACKLOG.md`).
4. **Repoint inbound links** (≈10, listed in the BACKLOG note): each should point at the
   **new official home** for that content, **not** at the archived runbook path. The
   `CHANGELOG.md` (2026-06-12) reference is append-only and cannot be rewritten — decide
   whether to accept the stale link or leave a stub. `tools/INGEST_CLI.md` currently calls
   the runbook "▶ Full operator procedure"; that home moves to `11_OPERATIONS.md`/`tools/`.

---

## 5. Pointers
- **Current state / open items:** `tasks/STATUS.md` §2 (the no-DICOM-regen item records
  §4.1's blocker and the age-bug follow-through).
- **Backlog items this supersedes/relates to:** `tasks/BACKLOG.md` — "Spectroscopy /
  non-image MRI … separate ingest path" (the 365 + §4.3/§4.4), the `equipment/` boundary
  item, and the git-hygiene item (2026-07-16).
- **Narrative history:** `CHANGELOG.md` rows 2026-07-15, 2026-07-14, 2026-06-12.
- **The runbook:** `equipment/mri-platform/mri_no_dicom_regeneration_runbook.md`.
- **Verified numbers this doc relies on** (re-derive before acting; scripts used are in the
  session scratchpad but easy to reproduce): 612 DICOM-less total; 365 `not-applicable`
  (STEAM 286/PRESS 74/WOBBLE 5); 247 `pending`; of those 153 have `2dseq`, 94 do not
  (80 header-only + 14 fid-only); PV split 6.0.1 × 277 / 7.0.0 × 335.

---
*Prepared as a handoff. Facts are marked as verified where checked against the live
registry/git; everything under "Recommendation"/"proposed" is a suggestion for the person
taking this on, not a decision.*
