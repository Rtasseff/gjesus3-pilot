# MRI anatomy mapping — candidate rules for data-office review (2026-06-13)

> **✅ RESOLVED 2026-06-14** with the MRI lead's (J. Ruiz-Cabello) email answers + Ryan's
> "high-confidence-only, null-if-doubt" rule. Outcome now LIVE in
> `tools/ingest/anatomy_derive.py` (`ANATOMY_RULES`) and documented in 08_METADATA §4.6.4:
> heart (4-chamber / long-axis / short-axis / cardiac / ventricle); large vessels **only
> when named** — MPA → pulmonary artery (UBERON:0002012), aorta (UBERON:0000947), carotid
> (UBERON:0005396); brain; abdomen. Setup/planning scans **skip**. Flow scans are **large
> vessels, not heart** (per the lead) so a bare "velocity map" with no named vessel → null;
> bare "cine", FLASH/RARE, and FOV are **not** organ-determinant → null. No group-specific
> assumptions baked in (the system will expand beyond Jesús's cardiac work). The text below
> is the original proposal, kept for the decision record.

**Status: PROPOSAL — INPUT NEEDED (superseded by the RESOLVED note above).** These are
candidate `ANATOMY_RULES` for
`tools/ingest/anatomy_derive.py`, drawn from the verbatim protocol names in
[`equipment/mri-platform/internal_mri_data_handling_workflow_notes.md`](../equipment/mri-platform/internal_mri_data_handling_workflow_notes.md) §3.
Nothing here is wired in yet — review/edit, then say the word and I'll fold the
approved rows into the live mapping and (optionally) run the back-fill dry-run.

## How the signal works (important for reading these)

Each **ACQ-ID = one ParaVision examination** = one protocol/series (the notes:
"a single study contains many sub-acquisitions E1…E16", and "ACQ-ID maps here"
at the exam level). So the per-acquisition scan-name signal is essentially **one
series name** (e.g. `Localizer`, `Cine 4-chamber`, `Cine MPA`), plus the Bruker
sequence (`mri_sequence_name`, e.g. `Bruker:IgFLASH`) and study name. Rules match
case-insensitively against that combined text.

**Conservative principle (unchanged):** a rule fires only on a confident match;
anything unmatched stays `is_whole_body: null` + WARN (never a guess). Operator-set
anatomy always wins. So over-narrow rules are *safe* (just leave more nulls);
over-broad rules are the risk to watch.

## Verbatim protocol names found (the evidence)

From §3 (the documented Cardiac_Flow_Mice workflow): `Localizer`, `Axial pure`,
`4-chamber`, `Long axis LV`, `Cine 4-chamber`, `Cine slices`, `Localizer for the
pulmonary artery`, `Cine MPA` (main pulmonary artery), `Velocity map` (flow/VENC).
From the PV-7 verification: `cardiac CINE`, `Localizer`, `Planning`, `T1_FLASH`,
`T2_TurboRARE`. The MFB MRI is overwhelmingly **cardiac/flow** (`Cardiac_Flow_Mice`).

## Candidate rules (review each)

| # | Match keywords (case-insensitive) | → region | UBERON id | is_whole_body | Confidence | Your call |
|---|---|---|---|---|---|---|
| **A** *(LIVE)* | `cardiac`, `cine`, `4 chamber`, `long axis`, `short axis`, `mpa`, `velocity map`, `flow mice` | heart | `UBERON:0000948` ✓ | false | **High** — dominant cardiac-flow workflow | keep / edit |
| **B** *(LIVE)* | `brain`, `cerebr`, `head` | brain | `UBERON:0000955` ✓ | false | High (if brain MRI exists) | keep / drop |
| **C** *(LIVE)* | `localis`/`localiz`, `tripilot`, `scout`, `planning`, `pilot` | *(none — SKIP)* | — | — | High — setup scans, no diagnostic anatomy | keep / edit |
| **D** *(new?)* | `axial pure` | *(SKIP)* | — | — | Medium — positioning/orientation reference, not diagnostic | add to SKIP? |
| **E** *(new?)* | `pulmonary artery`, `\bmpa\b`, `velocity map` | pulmonary artery | `UBERON:0002012` ⚠️ verify | false | Medium — MPA flow is great-vessel, not myocardium | **split from A, or fold into A as heart?** |
| **F** *(new?)* | study/protocol contains `cardiac_flow` / `cardiac flow` | heart | `UBERON:0000948` ✓ | false | Medium — would also tag the cardiac study's *localizers* (currently null under C) | enable study-level cardiac tag? |

✓ = UBERON id already verified in the repo starter set (08_METADATA §4.6.2 /
templates). ⚠️ = needs an OLS check before use.

## Decisions I need from you

1. **MPA / Velocity map → heart or pulmonary artery?** Today (rule A) they fall
   under `heart`. Rule **E** would instead tag those specific exams
   `pulmonary artery` (UBERON:0002012). Cleaner anatomically, but adds a UBERON id
   and splits the cardiac-flow study across two regions. **Fold into heart (simpler)
   or split out (more precise)?**
2. **Localizers in a cardiac study (rules C vs F).** A standalone `Localizer` exam
   currently derives nothing (stays null). If you want every exam in a
   `Cardiac_Flow_Mice` study tagged `heart` (including its localizers/axial-pure),
   enable rule **F** — but that needs the original Bruker study/protocol name to be
   in the signal. NB: `mri_study_name` is the *renamed* `jrc_<date>_<animal>_<proto>`
   form, which doesn't contain "cardiac". **Is the original `Cardiac_Flow_Mice`
   string captured anywhere in the sidecar (e.g. a SeriesDescription/StudyDescription)?**
   If not, F can't fire and we keep localizers null.
3. **`T1_FLASH` / `T2_TurboRARE` deliberately NOT mapped.** These are generic
   sequences that can image any organ, so I left them out — they'd be guesses.
   Confirm that's right, or tell me the organ if your FLASH/RARE are always one region.
4. **FOV whole-body heuristic.** `PVM_Fov` is captured but unused. If there's a FOV
   threshold above which a mouse scan is effectively whole-body, give me the cutoff
   and I'll add an `is_whole_body=true` rule. Otherwise it stays out.
5. **Any non-cardiac regions** (abdomen `UBERON:0000916`, lung `UBERON:0002048`,
   thoracic cavity `UBERON:0002224` — all already verified in the repo) — add rules
   only if those protocols exist in your data.

## To apply (once approved)

Tell me which rows/edits to take. I'll: (a) update `ANATOMY_RULES` in
`tools/ingest/anatomy_derive.py` + the tests, (b) run
`python tools/backfill_mri_anatomy.py --nas-root J:/gjesus3-data` **dry-run** so you
can eyeball the proposed fills before any `--apply`.
