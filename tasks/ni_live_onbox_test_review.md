# NI live-sync — on-box test review (2026-08-05, Mac at the NI instrument)

**What was tested:** `feat/ni-live-hardening` (HEAD `f2ee114`), run by Ryan on the Molecubes
Mac (`molecubess-iMac`, python 3.10.5, darwin) against the researcher tree
`/Users/molecubes/Documents/volumes/remiW11/data/irene`, following
`S:\gnuclear\2026\Jesus\Ryan\ni-live-test\RUN_THE_TEST.md` (Steps 0–6).
**Returned artefacts:** `review_irene.csv` (141 rows), `corrections_irene.csv` (75),
`corrections_irene_sandbox.csv` (75, byte-identical to the previous — sha1
`e19b1563ddb2f1993cdf210e2a3d228335c981ae`), `notes.txt`. No run log was returned.
**Provenance check:** `diff -rq -x __pycache__ -x '*.pyc' S:\...\ni-live-test\tools <repo>\tools`
→ no output. The operator ran exactly this branch's code, so every `tools/…:NN` cite below is
valid for what actually ran.

> ## 🔴 BOTTOM LINE — DO NOT MERGE YET
>
> The run stopped at the read-only `--plan` step. Steps 3 (edit the worksheet), 5 (`--go` to a
> local NAS) and the second half of Step 6 (`--corrections --go` to the sandbox) were all
> skipped, so **none of the three artefacts the merge is gated on exist**: there are zero
> `…/recon_N` registry rows, zero `session_extra` blocks in 202 sidecars, and no
> `pending_links.csv` anywhere on any NAS. `J:\gjesus3-sandbox` is mtime-frozen at the
> 2026-06-25 state — the only object under it newer than 2026-08-01 is the empty
> `_oslink_scratch/` directory from Step 0. What the run *did* prove is real but narrow (the
> branch loads and runs on the Mac; `os.link` → `ENOTSUP` as predicted; the worksheet writes
> cleanly over SMB). Separately, the review turned up **two things that must be fixed before
> anything else**: two synthetic test acquisitions from the 2026-06-29 §3.2/§3.3 verification
> are sitting in **true production** (the plan doc still says they went to a throwaway NAS),
> and the shared `molecubes` Mac account is currently mounting production with **Ryan's own
> full-permission credentials**. The code itself looks sound; the *evidence* is missing.

---

## 1. What the test PROVED

| # | Proved | Evidence |
|---|---|---|
| P1 | The branch's `tools/` tree runs unmodified on the Mac (py 3.10.5 / darwin) | `notes.txt`; byte-identical staged copy (diff above) |
| P2 | Hard links are impossible on the Mac's SMB mount — the premise of §1 | `notes.txt` Step 0: `[FAIL] os.link -> OSError ENOTSUP` on `/Volumes/gjesus3/gjesus3-sandbox/_oslink_scratch` |
| P3 | Discovery works over the real tree | `review_irene.csv` = 141 scan anchors (PET 72 / CT 69), all `researcher=irene` |
| P4 | `--plan` against a fresh empty local NAS writes a clean worksheet | `corrections_irene.csv`, 75 rows / 75 distinct `session_path` |
| P5 | Local `--dry-run` (Step 4) ran without error | `notes.txt` ("I did the local dry run and it ran fine") |
| P6 | `--plan` works over the SMB mount against a real NAS registry, at usable speed | Step 6 log: `16:41:45 building preview (read-only)` → `16:43:46 wrote 75 session row(s)` (~2 min for 141 anchors) |
| P7 | The registry *is* consulted in `--plan` mode (dedup is wired, not skipped) | `tools/operator/preview.py:106-128` reads `<nas_root>/registries/registry_raw.csv` and calls `config.expand_batch` |

## 2. What the test did NOT prove

| # | Not proved | Why |
|---|---|---|
| N1 | **Per-recon acquisitions (§3.5 / Tier B)** | 0 of 122 sandbox NI rows have `original_name` matching `/recon_\d+$`; the payloads are still June's bundled shape (`ACQ-20260212-CT-001.data/` holds `recon0-3.dcm` in one acquisition) |
| N2 | **`session_extra` / the correction cycle (§3.2/§3.3)** | Step 3 was never done. Both worksheets are 100 % unedited: 0/75 rows have `extra_metadata`, `session_id` or `sample_id` set, and 0/75 `project`/`animal_codes` differ from the raw parse. 0 of 202 sandbox sidecars contain `session_extra` |
| N3 | **`pending_links.csv` (§1 — the reason this branch exists)** | The file does not exist on `J:\gjesus3-sandbox\registries\` **or** `J:\gjesus3-data\registries\`; 0 `*.PENDING-LINK.txt` files anywhere; every `raw_linked/` subfolder under the sandbox is an empty directory (June's silent-failure state, pre-§1) |
| N4 | **`relink_pending.py` (the other half of §1)** | Its input has never existed, so the drain path has never run end-to-end either |
| N5 | **Why 2 of the 3 dropped sessions dropped** | No stdout was captured. The `[expand_batch] SKIP …` lines that carry the reason were not returned — and `tools/ingest/config.py:678-682` catches *any* `build_case` exception and prints an identically-shaped SKIP line, so absence-from-plan cannot distinguish "recon not ready" from "still erroring" |

**Sandbox state, verified read-only:** `registry_raw.csv` 202 rows, max
`registration_datetime` `2026-06-25T15:07:44Z`, `.acq_id_seq.json` untouched since Jun 25
17:07 (no ACQ-ID could have been allocated without touching it). `find J:/gjesus3-sandbox
-newermt 2026-08-01` → exactly one hit, the empty `_oslink_scratch/`.

---

## 3. Ryan's questions, answered

### 3.0 "It is not safe to login with my account which has full permissions on gjesus3."

**This is the most operationally significant line in `notes.txt` and it is not a
`feat/ni-live-hardening` question — it outranks the branch.** The shared instrument-room
account `molecubes` on the NI Mac now has a cached SMB credential for `rtasseff`, which holds
full write permissions on **production** `J:\gjesus3-data` — not just the sandbox. Anyone
sitting at that Mac can reach production.

**Recommendation:** treat as a **blocker for routine live sync** (not for the merge itself, but
for using it). Ask IT for a scoped NI service account with write access to
`gjesus3/gjesus3-data/raw` + `registries` only, and clear the cached credential on the Mac
before the next visit. File in `tasks/tasks.md`, not here.

---

### 3.1 "Why does it have 45 scans showing but the review csv has like 145?"

**Answer in your framing:** the review file lists **scans**; the worksheet lists **sessions**.
A session is one subject folder (`<series>/<date>/<subject>`) and usually holds a PET *and* a
CT, sometimes more. 141 scans → 78 sessions → 75 planned. Nothing was lost.

**Evidence (all recounted directly from the two CSVs):**

- `review_irene.csv` = **141** rows, one per machine anchor `<14-digit-ts>_<MOD>`, with **no
  filtering at all** — no registry check, no DICOM check, no depth check
  (`tools/ni_live_discover.py:49` `ANCHOR_RE`, `:204-213` `iter_from_root` walks the whole tree
  and yields anchors at *any* depth, `:241` one row per anchor).
- `corrections_irene.csv` = **75** rows, one per session that contributes ≥1 **new** ingestable
  acquisition (`tools/operator/ni_ingest.py:344-373` `_write_plan` dedups on
  `ni_corrections.session_key`; `tools/ingest/ni_corrections.py:62-73` key = `series/date/subject`).
- Set arithmetic: review → **78** distinct sessions; corrections → 75; difference = exactly
  `1207/250408/0522_141`, `1207/250408/0522_142`, `1207/250408/0522_143`; reverse difference = **0**.
- Cause of the three drops, split:
  - `0522_143` — **confirmed, and it is a real bug** (see §3.1a). Its only scan sits under a
    hand-made `new recon/` level: `irene/1207/250408/0522_143/new recon/20250408172344_PET`.
  - `0522_141` / `0522_142` (250408) — **most likely "reconstruction folders exist but hold no
    DICOMs yet"** (`tools/ingest/config.py:224-237` `fanout_ni_recons` returns `[]`), which is
    exactly the §3.5 skip that replaced June's `NI slim copy plan is empty` failures. **Marked
    medium confidence, not confirmed** — no stdout was captured, and the tidy story that "the
    3 missing sessions are June's 5 failures" does **not** hold: June's five failures spanned
    *four* sessions including `1207/250407/0522_141` and `_142`, and both of those **are** in
    the 75-row worksheet.

**On "45":** the worksheet has 75 rows, not 45 — and no quantity in it equals 45 (checked rows,
distinct sessions 75, subject folders 68, animal_codes 61, projects 6, series 7, dates 14,
summed animals 100). The likely source is **Step 1's own on-screen summary**:
`tools/ni_live_discover.py:268` prints `multi-animal scans (>1): 45` directly under `:267`'s
`acquisitions : 141`. 45 is exactly the count of 2-animal rows in `review_irene.csv`
(`n_animals` = {1: 96, 2: 45}). You also wrote "145", so these are recalled numbers, not read ones.

**Recommendation:** don't "fix" 141 → 75 — it is correct behaviour. Do add a one-line
reconciliation to `--plan`: `N scans → M sessions → K planned (X dropped)`. **Do not** simply
print `result.dropped`: in `--plan` mode the template's `pattern: "**/"`
(`tools/templates/instruments/molecubes_ni_live.yaml:36`) makes `config.py:483-489` reject every
directory that isn't exactly 3 levels deep — in the one run whose stderr we have
(`p_5_output.txt`) that fires **876 times** (`SKIP recon_0`, `SKIP frame_0`, `SKIP iter_30`, …).
A useful reconciliation must first filter dropped names to anchor-shaped basenames, and the SKIP
line prints only `match_basename` with no path (`config.py:484-488`), so it cannot name the
session as-is. That filtering is the real work item, and it is small but not free.

#### 3.1a REAL BUG — a `new recon/` folder makes scans invisible to the sync

`tools/ni_live_discover.py:56` (`INTERMEDIATE_NOISE_RE`, applied at `:159-163`) deliberately
**steps over** hand-made levels named `new recon` / `reconstructed` / `recon_N`. The ingest path
does the opposite: `molecubes_ni_live.yaml:37-38` sets `path_parse.levels: [series, date, subject]`
and `config.py:483-489` hard-skips anything not exactly 3 deep. Result: the review tool **shows**
those scans and the sync **silently discards** them. 2 of 141 rows are affected, and session
`1207/250408/0522_143` has *only* such a scan — it can never sync, and the only trace is a SKIP
line nobody captured.

**Collision hazard that constrains the fix:** the deep path
`…/0522_141/new recon/20250408173151_CT` carries the **same timestamp and modality** as the
normal-depth `…/0522_141/20250408173151_CT`. If `path_parse` were simply taught to absorb an
extra level, the two would get *different* dedup keys (`original_name` differs) but the *same*
`link_filename` (the template is `${modality}_${subject}_${acq_date}_${acq_datetime_full}_recon${ni_recon_idx}`
— every field identical), so two acquisitions would silently merge their hard links into one
`raw_linked/` directory. Any fix must disambiguate the link name too. **Decision needed** (§5, ONBOX-03).

---

### 3.2 "The session_id was not captured… what is sample_id supposed to be?"

**Answer in your framing:** `session_id` *is* captured, for every NI acquisition — it's just
blank on the worksheet. It is not vestigial, and yes, it is the DICOM/XNAT Session level. `1207`
is **not** the session; you corrected yourself in the same paragraph and the correction is right —
it is the funded-project / investigation-level id. And no, subject == sample is **not** yet true
in the registry column, though it is the documented end state.

**Evidence:**

- **`session_id` is populated.** `molecubes_ni_live.yaml:56`
  `session_id: "${discovered.series}_${discovered.date}_${discovered.subject}"`, resolved at
  `tools/ingest/resolver.py:148-155`, written at `tools/ingest/registry.py:222`. Sandbox:
  **0 of 202 rows blank**, 69 distinct session_ids over 122 NI acquisitions (e.g.
  `1207_250304_0522_120`, shared by that visit's PET and CT). Production: 0 blanks on 134 NI +
  10,330 MRI rows; blanks occur only on microscopy, exactly as `06_REGISTRIES.md:134` says.
- **It corresponds to the DICOM Study.** Across all 122 sandbox NI sidecars: 69 session_ids ↔
  69 `StudyInstanceUID`s, zero crossover either way; of the 69, **51 contain both a PET and a
  CT** and in every one of those the two share the UID. *Caveat:* all 122 UIDs share the root
  `1.2.3` (a placeholder OID), and the study-identifying headers are the same console entries
  that build the folder tree (`StudyDescription="1207"`, `PatientName="irene^/ 1207 / 250304"`,
  `PatientID="0522_120"`). So the honest claim is **"the Molecubes console groups one animal
  visit as one DICOM Study, and our `session_id` reproduces that grouping"** — not that an
  independent machine identifier corroborates the schema.
- **Consequence worth writing down:** `08_METADATA.md:398` states that PET and the corresponding
  CT are *separate* studies on Molecubes ("verify per case"). Measured over 51 PET+CT sessions,
  they share the UID. The doc line should be corrected.
- **The blank cells are a `_write_plan` defect.** `tools/operator/ni_ingest.py:361-362` hard-codes
  `"session_id": ""`, `"sample_id": ""`, contradicting this branch's own locked decision D5
  (`tasks/ni_live_operator_plan.md:228` — parsed-value columns "prefilled"). Blank means "no
  override" (`ni_corrections.py:185-188` applies non-empty values only), but nothing on the sheet
  or in `tools/operator/README.md:97-118` says so — that block names only `project` /
  `animal_codes` / `extra_metadata`, i.e. **the two columns you flagged are the exact two the only
  operator-facing doc omits.**
- **D5 drift is wider than the blanks.** The plan specifies prefilled `project`, `session_id`,
  `animal_codes`, **`timepoint`**; `NI_CORRECTION_FIELDS` (`ni_corrections.py:46-53`) is
  `session_path, project, animal_codes, session_id, sample_id, extra_metadata` — `timepoint` is
  absent (so a mis-typed timepoint can't be corrected, and real sessions carry it:
  `0314/260212/0324_m61_m62_2h`) and `sample_id` was never specified.
- **A real bug behind the blanks — staleness.** `_PRE_FIELDS` (`ni_corrections.py:57`) overrides
  only `discovered.project` and `discovered.animal_codes`; `discovered.subject` is deliberately
  left raw (asserted by this branch's own test, `tools/test_ni_corrections.py:79`). But
  `sample_id` and `session_id` resolve from `${discovered.subject}` (`molecubes_ni_live.yaml:52,56`).
  So correcting project `0324→0325` reroutes `project_hint` and `subject_ids` correctly while
  **leaving `sample_id=0324_m61` and `session_id=…_0324_m61` carrying the wrong project code.**
  That is precisely why the post-resolution `sample_id`/`session_id` overrides exist — they are
  the only repair path. Do **not** delete them, and note that naively prefilling from
  `case.registry_resolved` (set once at `config.py:276`, never updated by `apply_post`) would
  make the staleness *invisible* rather than fix it: on a re-plan with `--corrections` the
  operator would see their own fix silently reverted.
- **`1207` is the funded-project id, and it is documented.**
  `equipment/nuclear-imaging/internal_ni_data_handling_workflow_notes.md:70,72` — `<series_id>` =
  "Funded-project id"; `<short_project>` = animal-protocol id; "the animal protocol is a
  regulatory artifact; the series_id is a financial-administrative one" (with `1207`/`0424` as the
  worked example). Machine side: `discovered.ni_study_name` = protocol.txt `Study name`
  (`tools/ingest/ni_metadata.py:501-503`, `09_MODALITIES.md:255`). It cannot *be* the session —
  in the sandbox, series `1207` spans **16** distinct sessions / 26 acquisitions.
- **Which code is the ISA Investigation is a genuinely open question, logged as NI-LIVE-09**
  (`equipment/nuclear-imaging/live_machine_data_layout_and_sync_rules.md:633`). Today the code
  routes on the **AE animal-protocol code** (`molecubes_ni_live.yaml:58`
  `project_hint: "ae-biomegune-${discovered.project}"`, where `discovered.project` is the *subject*
  folder prefix), and 134 NI + 10,330 MRI production rows are keyed to it. Switching to the funded
  id would re-key every NI project folder and break alignment with MRI. **This is §5 ONBOX-01.**
- **`sample_id` for in-vivo — you are right about the end state, but not about today.**
  `06_REGISTRIES.md:171` (§2.3.3, DECIDED 2026-06-11) does say the animal *is* the sample. But the
  same DECIDED section, at `:177`, documents that the **registry column** carries the short
  `m<animal>_<project>` form, with the canonical facility id in the sidecar
  `subject.facility_animal_id`, and that the column "MAY carry the facility id directly at the
  true-prod schema refresh (REG-01)" — REG-01 is still 🔶 Draft at `:455`. So the column not
  holding the facility id is **current convention, not a violation**. The narrow real defect is
  that NI-live emits the **raw folder text** — `0522_120`, or `0324_m59_m60` for a multi-animal
  folder — which matches *neither* the facility form *nor* the production `m13_0525` / `m1_1521`
  form used by NI-archive and MRI rows.
- **Why you doubted it exists:** `session_id`'s status is contradictory in the repo. DECIDED at
  `06_REGISTRIES.md:86` and `:120-122`; still "DRAFT" at `06_REGISTRIES.md:127`, `:217`, `:462`
  (REG-08), `:463` (REG-09), `CLAUDE.md:75`, `tools/ingest/registry.py:51`,
  `tools/ingest/resolver.py:82`, `tools/INGEST_CLI.md:62`, `README.md:31`. The S2 marker flip
  (`tasks/correction_pass_plan.md:53-55`) hit the section bodies but not the summary table or the
  code comments.
- **Spec-layer gap:** the NI corrections worksheet and the `auto_discover.subject_parse:` key
  (implemented `config.py:638-652`, used `molecubes_ni_live.yaml:42-43`) appear **nowhere** in
  `mfb-rdm-docs/10_TOOLS.md` — which has zero hits for `corrections` / `--plan` / `--live` /
  `ni-ingest` — even though `08_METADATA.md:240` cites 10_TOOLS for exactly that. (`INGEST_CLI.md`
  does mention `ni-ingest` at `:5` and "corrections" at `:239`, but documents neither flag nor any
  worksheet column.)

**A silent identity problem the worksheet surfaced.** 5 of the 75 rows have **series and date
inverted**: `260302/0525/0525_m31` … `_m35`. `path_parse` assigns levels positionally
(`config.py:490-491`), so these get `discovered.series="260302"`, `discovered.date="0525"` — and
that inversion is baked into `session_key`, into `session_id` (9 sandbox rows already carry
`260302_0525_0525_m31`-shaped ids), and into `original_name`, i.e. into the **permanent dedup
identity**. Sibling rows for the same animals appear correctly as `0525/260302/0525_m34`, so
`0525_m34` exists under **both** shapes in the same worksheet (rows 16 and 74). Project routing
survived only by luck (`parse_subject` reads the *subject* prefix). Nothing flags it.

**Also unflagged in the plan path:** 25 of the 141 review rows carry `date_flag` `d365!`/`d366!` —
the hand-typed folder date is a **full year** off the machine timestamp (e.g.
`irene/1025/250526/1025_m11-12/20260526162633_PET`). All 25 sit inside sessions that **are** in
the 75-row worksheet, so they will ingest with a 2026 `acq_date` under a 2025-named `session_path`.
The review tool flags this; the worksheet does not carry the signal.

**Recommendations (in order):** (1) prefill `session_id`/`sample_id` from the **post-correction**
top-level case keys, not `registry_resolved`; (2) fix `apply_pre` to re-derive `discovered.subject`
(or explicitly document that the post-override is the repair path); (3) align
`molecubes_ni_live.yaml:52`'s `sample_id` with the in-production `m<animal>_<project>` form —
do **not** attempt the facility-id end state on this branch (it would move `sample_id` from
`USER_CONTROLLABLE_COLUMNS` to `AUTO_COLUMNS` in `resolver.py`, touch `registry.py`,
`enrichment.py`, `metadata_sidecar.py`, `readme.py` and every per-instrument template, and create
mixed semantics against 13,582 live rows); (4) close the doc gaps listed above; (5) take ONBOX-01
as a spec decision, separately from the merge.

---

### 3.3 "is_control / is_whole_body … a user would not need to enter values in a workflow designed specifically for NI"

**Answer:** you're right, and it's worse than you saw — the prompt fires in **read-only** modes
*and* it is **not** suppressed by `--go`.

**Evidence:**
- The prompts come from the shared operator module, not from anything NI-specific:
  `tools/operator/metadata_prompt.py:144` (`is_control (true=control / false=case): `) and `:151-155`
  (`is_whole_body (true=whole-body / false=region of interest): `), gated at `:131-137`.
- `tools/operator/ni_ingest.py:404` sets `interactive = (not args.no_prompt) and sys.stdin.isatty()`
  and calls `collect_overrides` at `:405` — **46 lines before** the `--plan` early return at
  `:450-451` and **56 before** the `--dry-run` gate at `:460-461`. Same shape in archive mode
  (`:624`/`:662`).
- **`--go` does not help.** `--go` is gated only against the `Proceed? [y/N]` input at `:462-463`;
  its help text (`:533-534`) and `tools/operator/README.md:75` advertise it as "skip the prompt"
  (singular). So the *real-write* steps stop for the same two questions. A fix that only adds
  `not args.plan and not args.dry_run` leaves that untouched.
- Across the documented 6 steps the prompt fires **three** times: Step 2 (`--plan`), Step 4
  (`--dry-run`), Step 6's first command (`--plan` to the sandbox).
- In `--plan` mode the answers are **discarded**: they are merged into cfg at `:423`, the only
  consumer before the plan return is `preview.preview_batch` (`:442`), and `tools/operator/preview.py`
  contains no reference to `condition` / `anatomy` / `enrichment`. `_write_plan` writes six columns.
- **Nothing was lost.** Neither field is a registry column (`tools/ingest/registry.py:19-64`;
  `resolver.py:71-84`). Unanswered → explicit `null` sentinels + a WARN, which is the DECIDED
  non-blocking behaviour (`08_METADATA.md:723`, `:735`; `molecubes_ni_live.yaml:73-75` deliberately
  omits both blocks).
- `--no-prompt` exists (`ni_ingest.py:566-569`) but appears **zero** times in `RUN_THE_TEST.md`,
  so you had no documented escape hatch.
- Your "these become kinda useless on a live sync" is already the documented guidance:
  `metadata_prompt.py:45-48` and `README.md:189-190` both say to skip them when a folder mixes
  controls and cases. (That the *irene* batch is in fact mixed is your assertion, not something the
  returned CSVs record — they carry no control/case column.)

**On "is_whole_body may actually apply to all things from NI":** plausible, but **no document
supports it.** `09_MODALITIES.md:225` offers only the protocol.txt `Scan bed position from X to Y`
range as an explicitly **non-authoritative** hint; `grep -rin "whole.body" equipment/` returns zero
hits; even the archive template (`molecubes_ni.yaml:352-357`) says whole-body is "common for static
PET/CT" while still shipping `is_whole_body: null`. **Do not hard-code it** — either assert it as a
platform fact (then it's a one-line `anatomy:` block) or derive an auto-hint from the bed-position
fields already parsed at `ni_metadata.py:98-105`. §5 ONBOX-04.

**Recommendation:** minimal fix = suppress the prompt whenever the run cannot write —
`ni_ingest.py:404` → `interactive = (not args.no_prompt) and not args.plan and not args.dry_run
and sys.stdin.isatty()` (`args.plan` exists in both modes; it's declared on the top-level parser at
`:513`). Better for `--live`: set `interactive = False` in `_run_live` outright and rely on the
`--is-control` / `--is-whole-body` flags. **Note the doc cost:** `08_METADATA.md:615` — inside a
section marked DECIDED — currently tells operators they may "omit them and answer the interactive
prompts the tool shows before ingest", and it points at `tools/INGEST_CLI.md`, which documents
none of those flags. Going flags-only on `--live` requires updating `08_METADATA.md` §4.5.4 +
`tools/operator/README.md` + `INGEST_CLI.md` together.

**Your "a wrapper will help":** that's §3.6 (Mac GUI), already backlogged. It is **not** a
prerequisite — fix the boolean now.

---

### 3.4 "Step 2 is messy… what's the point of the review… why call the full ingest script just to make the corrections csv?"

**(a) The `--root` split is real, and worse than the plan says.** `tasks/ni_live_operator_plan.md:113-116`
records it as "failed". It doesn't fail: `ni_live_discover.py:206` does `base = os.path.join(root, folder)`
and `:207-208` silently `continue`s when that path doesn't exist, so the wrong form prints
`acquisitions : 0` and **exits 0** — and with `--csv` it writes a header-only file
(`:278` falls back to `fieldnames=["relpath"]`) that looks like a real survey. Verified by running
the read-only tool: `--root tools irene` → empty table, `EXIT=0`. Meanwhile
`ni_ingest.py:387/:419` takes the researcher folder *itself*.
The repo contradicts itself about which form is right: `molecubes_ni_live.yaml:12` documents the
**broken** one; `ni_live_discover.py:28` documents the correct one; `RUN_THE_TEST.md:103-105`
warns you explicitly that Step 1 and Step 2 differ. Last touch on the file is `34ac961` (the June
correction pass) — nothing on this branch fixed it.
**Fix:** accept either form in `iter_from_root` (fall back to `base = root` when
`basename(root) == folder`), and make a zero-row `--root` run print an error naming both accepted
forms and return non-zero. Also fix `molecubes_ni_live.yaml:12`.
**Second, independent composition failure:** `ni_live_discover.py:45` hardcodes `MFB_FOLDERS` and
`:231-234` exits 2 for anything not in it, while `ni_ingest.py --live` accepts any folder and infers
the researcher from its basename (`:394-395`). A new NI researcher can run Step 2 but is refused by
Step 1 until someone edits the source.

**(b) The two files are genuinely different artefacts — but the corrections CSV really does need
the ingest script.** Two things only the ingest path knows: (1) **registry dedup** — "only NEW
sessions" is computed by reading `<nas>/registries/registry_raw.csv` (`config.py:181`, applied at
`:698-704` / `:712-717`); `ni_live_discover.py` imports only argparse/csv/datetime/os/re/sys and
opens no registry at all. (2) **Reconstruction readiness** — `fanout_ni_recons` (`config.py:193-237`)
reads which `recon_<idx>/` actually hold DICOMs; the discovery tool stops at the anchor
(`:213 dirnames[:] = []`). What is *not* a reason for two tools is the parse: `config.py:640-648`
literally `import ni_live_discover` and calls its `parse_subject`.

**(c) "Should we not be able to edit the review?"** Editing it is a no-op today — nothing in the
codebase reads a review CSV back (`grep -rn ni_live_discover tools/` → only the parser import, the
unit test, and comments). Per-scan editing would also be the wrong grain: a correction must bind to
a session so it applies across a visit's recons and its PET/CT pair (decision D5,
`ni_live_operator_plan.md:213-216`).

**(d) So: fold Step 1 into `--plan` and drop it from the operator flow — but not before porting
three things**, or you lose real signal:
- `subject_flags` — already computed at `config.py:649-650`, simply not written to the worksheet
  (irene: species-unknown ×30, possible-range ×12). *(It does survive into `metadata.json` via the
  `discovered` block, `metadata_sidecar.py:77,83` — what's missing is pre-ingest visibility.)*
- `date_flag` — exists **only** in `ni_live_discover.py:142-151`; nothing in `tools/ingest/` computes
  it. 25 of 141 rows flagged (§3.2).
- The deep-path scans of §3.1a — today the review table is the **only** artefact that shows they
  exist.

Keep `ni_live_discover.py` in the repo as a data-office/offline tool (its `--from-listing` mode
works with no box and no NAS), just stop putting it in front of operators. Target flow: **4
commands, one path string, one tool** — `--plan` → edit → `--corrections --dry-run` →
`--corrections --go`.

---

### 3.5 "Something more organised … a script on a cron/scheduler to check for these backfill jobs"

**Answer:** your instinct about the pattern is right; the payoff from *unifying the queues* is not.
Build the **read-only reporter**, not a shared base class.

**What genuinely is shared (a contract, worth documenting):** one CSV under `<NAS>/registries/`
(operators hold Modify there, write-once on `raw/` — `pending.py:7-9`); `acq_id` key with
refresh-fields-but-preserve-`status` idempotency (`pending.py:96-113`, `pending_dicom.py:109-129`,
`pending_links.py:109-131`); queued from a non-blocking `except` at the failure site so a worklist
hiccup can never fail a good ingest (`enrichment.py:141-144`, `ingest_raw.py:1034-1036`,
`ingest_raw.py:1488-1489`); a `pending` → terminal lifecycle; a BOM-tolerant defensive header check.

**What is irreducibly different (why one queue would be wrong):** payloads are 7 / 8 / 9 columns
with near-zero overlap past `acq_id`+timestamp+status, because each row carries exactly the argument
list its drainer needs to reconstruct the deferred call; the timestamp columns differ in name *and*
format (`logged_at`, UTC `Z` vs `queued_datetime`, local ISO with offset); terminal states aren't
interchangeable; and the three write targets sit in three permission tiers (`projects/` vs
`/raw/<ACQ>.data/` vs an in-place `/raw/` sidecar rewrite).

**Two things must be fixed before anything runs on a schedule:**

1. **The live `pending_dicom_regen.csv` is write-broken in true production.** Its header has drifted
   to **9** columns including `nonimage_marker`; the code expects 8 (`tools/ingest/pending_dicom.py:39-48`).
   Running `pending_dicom._assert_header()` against the live file raises
   `RuntimeError: header mismatch`, and `ingest_raw.py:1034` swallows it as a WARN — so the next
   no-DICOM MRI ingest against live **silently fails to queue**, the exact failure mode §1 exists to
   end. All 612 rows share one `queued_datetime` (`2026-07-15T19:09:23+02:00`) and the status
   vocabulary is now `{not-applicable: 365, no-source: 94, regenerated: 153}` with **zero**
   `pending`, versus the code comment's `pending | regenerated`.
   **Evidence points at ADOPT, not revert:** the marker values are exactly
   `_NONIMAGE_METHOD_MARKERS = ("STEAM", "PRESS", "WOBBLE")` (`tools/ingest/paravision_regen.py:84`,
   `is_nonimage_exam()` at `:102-110`, used at `:221`), the 365 `not-applicable` rows are precisely
   the 365 rows carrying a marker, and `not-applicable` is verbatim the semantics
   `paravision_regen.py:222-227` states. Only the **literal column name** is uncommitted
   (`git log --all -S"nonimage_marker"` → 0 commits). Someone ran repo logic from an uncommitted
   script. *(Note: the file's mtime is Jul 16 13:29 — "2026-07-15" is a value that same pass wrote.)*
   Also: `pending | regenerated` is documented **nowhere** in `mfb-rdm-docs/` — it exists only as an
   inline comment at `pending_dicom.py:47`. `06_REGISTRIES.md:39` describes the queue's purpose, not
   its schema (unlike `pending_links.csv`, whose full schema *is* at `:40`).
2. **None of the three modules take the registry lock**, yet each does a whole-file
   read-modify-write. Only `provenance.py:19,94` and `subjects_table.py:36,302` use
   `locking.registry_lock`; the two lock sites in `ingest_raw.py` (`:822`, `:1321`) are narrowly
   scoped around ACQ-ID allocation and `registry.append_row`, and the pending writes at `:1019`/`:1450`
   sit outside both. A scheduled drainer racing a Mac ingest is last-writer-wins on the whole CSV.
   Also `tools/ingest/pending.py:70-76` is a plain truncate-and-rewrite; both siblings do
   temp+`os.replace` (`pending_dicom.py:81-90`, `pending_links.py:81-90`).

**Live worklist state (read-only, 2026-08-05):** `pending_subject_metadata.csv` 257 rows, **all
pending** (250 `db-miss` + 7 `no-credentials`, untouched since 2026-07-17);
`pending_dicom_regen.csv` 612 rows, 0 pending; `pending_links.csv` absent.

**Two hazards for a scheduler:** the drainers have **inconsistent** safety defaults —
`relink_pending.py:41` and `relink_mri_regen.py:95` both **apply by default** (`--dry-run` opt-in),
while `recover_subject_metadata.py` is **dry-run by default** (`--apply` required). And
`pending_dicom_regen.csv` has **no drainer at all**: `relink_mri_regen.py` is not it — it filters
`registry_raw.csv` on two hard-coded config-name substrings (`:44`, `:101-105`) and never opens the
worklist (`grep -n pending tools/relink_mri_regen.py` → 0 lines).

**The drafted BACKLOG entry is below, unedited.** Three known errors to fix before filing:
(i) it claims `grep -rn nonimage` returns 0 hits across the tree — **false**, see the ADOPT evidence
above; (ii) it labels Step 5 "the real sandbox ingest" — Step 5 is the **local throwaway** run
(`RUN_THE_TEST.md:166-179`); the sandbox ingest is Step 6's **second** command (`:183-199`);
(iii) it cites `06_REGISTRIES.md:39` for a status vocabulary that line does not contain.
Also worth folding in: `06_REGISTRIES.md:241` (§2.7) already lists which files route through
`csv_safe` and names only one of the three worklists — the new §2.8 should fix that line, not just
sit beside it; and `tools/INGEST_CLI.md` mentions `pending` exactly once (`:116`), covering only
`pending_subject_metadata.csv`.

```markdown
## Deferred-recovery worklists — one status reporter + scheduled drain (2026-08-05)

**Origin: the operator, on the Mac, mid-test** (`S:\gnuclear\2026\Jesus\Ryan\ni-live-test\notes.txt`):
*"We will need to make something that looks for missing hard links to rerun those hard links at
another time… given the similar pattern I think there is something more organized that can be done
along with documentation… a script that runs from my RDM machine on a cron or other scheduler
(Windows) to periodically check for these backfill jobs on all these partial ingests with (right
now) three possible distinct causes: DICOM (no Linux or no software installed), hardlink (no
Windows), DB (bad creds)."*

**The three worklists today** — all under `<NAS>/registries/`, all keyed on `acq_id`, all queued
from a non-blocking `except` at the ingest failure site so a worklist hiccup can never fail an
otherwise-good ingest:

| cause | file | writer | drainer | capability the drain box needs |
|---|---|---|---|---|
| **DB** (bad/absent creds, or the DB lags the scan) | `pending_subject_metadata.csv` | [`ingest/pending.py`](../tools/ingest/pending.py) ← `enrichment.py:143` | [`recover_subject_metadata.py`](../tools/recover_subject_metadata.py) (**dry-run by default**, `--apply` writes) | `~/.my.cnf` + on-network + Full on `/raw/` |
| **DICOM** (no Linux / no Dicomifier) | `pending_dicom_regen.csv` | [`ingest/pending_dicom.py`](../tools/ingest/pending_dicom.py) ← `ingest_raw.py:1015` | **none — manual WSL Dicomifier pass + idempotent re-ingest** | WSL/Linux + Dicomifier + SSH to `kenia` |
| **hardlink** (no Windows — the NI Mac's SMB mount `ENOTSUP`) | `pending_links.csv` | [`ingest/pending_links.py`](../tools/ingest/pending_links.py) ← `ingest_raw.py:1434` | [`relink_pending.py`](../tools/relink_pending.py) (**applies by default**, `--dry-run` opt-in) | a hard-link-capable mount (`J:` from Windows) |

**Live state 2026-08-05** (read-only check of `J:\gjesus3-data\registries\`): subjects **257 rows,
all `pending`** (250 `db-miss` + 7 `no-credentials`, untouched since 2026-07-17); DICOM **612 rows,
0 pending** (triaged 2026-07-15); links **file does not exist** (never yet produced by a real
ingest — the 2026-08-05 on-box run stopped before step 5).

**What is genuinely shared** (→ a documented *contract*, not a base class): the `registries/`
location (operators hold Modify there, write-once on `raw/`), the `acq_id` key with
refresh-fields-but-preserve-`status` idempotency, the non-blocking queue-on-failure rule, the
`pending` → terminal lifecycle, and the BOM-tolerant defensive header check.
**What is irreducibly different** (→ why a merged CSV / shared class is the WRONG move): the
payloads are 7 / 8 / 9 columns with near-zero overlap past `acq_id`+timestamp+status, because each
row carries exactly the argument list its drainer needs to reconstruct the deferred call; the
timestamp columns differ in name *and* format (`logged_at` UTC-`Z` vs `queued_datetime`
local-with-offset); the terminal states are not interchangeable (subjects has
`pending|recovered|unresolvable` + a `recovered_at`, the others have two states and no completion
stamp); and the write targets sit in three different permission tiers (`projects/` vs
`/raw/<ACQ>.data/` vs an in-place `/raw/` sidecar rewrite).

### Blockers — fix these BEFORE anything runs on a schedule

- [ ] **Live `pending_dicom_regen.csv` header has DRIFTED and the queue is write-broken in true
  production.** The live file carries **9** columns including **`nonimage_marker`** — a column that
  exists in **no file on any branch** of this repo (`git log --all -S"nonimage_marker"` → 0
  commits). `pending_dicom._assert_header` raises on it, and `ingest_raw.py:1034` swallows the
  RuntimeError as a WARN — so **the next no-DICOM MRI ingest against live silently fails to queue**,
  exactly the failure mode §1 was written to end for hard links. The same out-of-band pass (all 612
  rows share one `queued_datetime` of `2026-07-15T19:09:23+02:00`) also invented two statuses:
  `not-applicable` (365 = the STEAM/PRESS/WOBBLE spectroscopy backlog) and `no-source` (94), versus
  the documented `pending | regenerated`. **Decide: adopt the column + the extended vocabulary into
  `PENDING_DICOM_FIELDS` and the spec, or migrate the file back** — but not both, and not neither.
- [ ] **Put the pending writes under the registry lock.** None of the three modules import
  `ingest/locking.py`, yet each does a whole-file read-modify-write. `subjects_table.py:301-303` and
  `provenance.py:94` already take `locking.registry_lock`. Scheduling a drainer is precisely what
  turns "a Mac ingest and a Windows relink at the same time" from theoretical into routine —
  last-writer-wins on the whole CSV loses rows.
- [ ] **Make `pending.py::_write_all` atomic.** It is a plain truncate-and-rewrite
  ([`pending.py:70-76`](../tools/ingest/pending.py)); its two siblings both do temp+`os.replace`.
  A dropped SMB connection mid-write truncates the live 257-row subject queue.

### The tool

- [ ] **`tools/pending_status.py` — one read-only status report across all three causes.** Sits
  beside the other top-level CLIs. Each worklist registers a small **descriptor** (module, filename,
  key, status column, done-statuses, timestamp column, cause label, required capability, drain
  command) — every field is already exposed as a module constant
  (`PENDING_FILENAME`/`PENDING_FIELDS`/`read_pending*`), so no new schema is invented and no writer
  is duplicated. Reports per worklist: **row count · open (non-terminal) count · status histogram ·
  age of the oldest open row · header-DRIFT flag**.
  - **The header-drift check is the highest-value line** — it is what would have caught
    `nonimage_marker` on 2026-07-15. Diff the on-disk header (via `csv_safe.read_header`) against the
    module's `*_FIELDS` and print a loud `DRIFT` row instead of letting ingest swallow it as a WARN.
  - **Capability probe on the host it runs on**, so the report says what *this box* can drain:
    `os.link` in a scratch dir (reuse [`tools/diagnostics/test_oslink.py`](../tools/diagnostics/test_oslink.py)),
    WSL/Dicomifier presence, `~/.my.cnf` + an `animal_db` connect test. This is the operator's
    three-causes framing made machine-checkable.
  - `--json` / `--out <path>` so a scheduled run drops a report next to `registries/`;
    `--max-age-days N` sets a non-zero exit code when an open row is older than N, so the scheduler
    can alert rather than the report going unread.
- [ ] **Opt-in, per-cause drain — never a blanket `--drain-all`.** `--drain links` shells to
  `relink_pending.py` (**the only one safe to auto-run unattended on the Windows RDM box**).
  `--drain subjects` must require an explicit extra flag and pass `--apply` (it rewrites `/raw/`
  sidecars in place and needs creds). `--drain dicom` **refuses on Windows and says why** (no
  Dicomifier — see the 2026-06-24 research finding above). Note the drainers' **opposite defaults**
  (`relink_pending.py` applies by default; `recover_subject_metadata.py` is dry-run by default) —
  the wrapper must be explicit per tool, not assume a house style. Consider flipping
  `relink_pending.py` to dry-run-by-default for consistency while it is still unproven.
- [ ] **Schedule via Windows Task Scheduler, not cron** (the RDM workstation is Windows):
  `schtasks /Create /SC DAILY /TN gjesus3-pending /TR "python <repo>\tools\pending_status.py --nas-root J:\gjesus3-data --drain links --out J:\gjesus3-data\registries\pending_status.json"`.
- [ ] **A drainer for `pending_dicom_regen.csv`.** It is the only cause with no tool —
  [`relink_mri_regen.py`](../tools/relink_mri_regen.py) is *not* it (it filters `registry_raw.csv` on
  two hard-coded config names and never opens the worklist). Even a WSL-side
  `drain_pending_dicom.py` that only *emits the re-ingest plan* would beat the by-hand pass that
  produced the 2026-07-15 drift.

### Documentation (do this part regardless — it is the operator's "at a minimum")

- [ ] **Write the family contract into [`06_REGISTRIES`](../mfb-rdm-docs/06_REGISTRIES.md)** as a new
  §2.8 "Deferred-recovery worklists". §1.2 already tables all three files; what is missing is the
  shared *rules*: `registries/` location + why, `acq_id` key, refresh-but-preserve-`status`, the
  non-blocking queue-on-failure rule, the defensive header check, **and (new) the requirement that
  every worklist write happens under `locking.registry_lock` with an atomic temp+replace**. Any
  fourth cause added later inherits the contract instead of re-deriving it.
- [ ] **One operator-facing runbook section in [`tools/INGEST_CLI.md`](../tools/INGEST_CLI.md)** —
  "my ingest said something was deferred, now what": the three causes, which machine drains each,
  the exact command, and the dry-run posture of each.

**Relationship to the rest of the backlog.** This is the *interim* answer to the operator's own
"eventually we will run from a new dedicated server so the single environment should allow us to fix
all these issues" — see **"Server-side raw ingest + a downstream Windows tool"** above, which
dissolves all three causes at once by putting Dicomifier, the DB creds, and a hard-link-capable
mount on one Linux host. Build the reporter because the server is not close; build it thin so it is
cheap to retire when the server lands.
```

---

### 3.6 "Since it is on the sandbox, I figure we can compare from here?"

**Answer: there is nothing to compare — the sandbox was never written to.** See §2 (N1–N3) for the
three missing artefacts and the frozen-state evidence.

**And re-running Step 6 as-is would not produce a clean comparison either.** `corrections_irene.csv`
(Step 2, against an *empty* local NAS) and `corrections_irene_sandbox.csv` (Step 6, against a sandbox
holding 122 NI acquisitions) are **byte-identical** — 2701 bytes, same sha1. Dedup ran and matched
**nothing**: all **69** sessions already in the sandbox registry were re-planned as new, 0 dropped.
Cause is structural and expected from decision D4: the dedup key is `(acq_date, original_name)`
(`config.py:698`, `:712`), and the new per-recon `original_name` (`config.py:242`,
`…/recon_<idx>`) can never equal an old anchor-level one — 0 of the 122 June rows contain `/recon_`.
A `--corrections --go` against the sandbox today would re-ingest ~14 GB of already-present NI data as
duplicate per-recon acquisitions and make the verification unreadable.

**Production is not exposed to this specific break**: its only two `molecubes_ni_live.yaml` rows
already carry `/recon_0` and `/recon_1`; the other 132 NI rows come from the flat archive config.

---

### 3.7 🔴 Incidental to your questions, but found during the review — synthetic test data in TRUE PRODUCTION

`tasks/ni_live_operator_plan.md:39-43` states that the §3.2/§3.3 verification ran "synthetic tree →
**throwaway nas**". It did not. The registry proves it went to `J:\gjesus3-data`:

- `registry_raw.csv`: `ACQ-20260212-CT-001` / `-002`, `registration_datetime`
  `2026-06-29T16:05:5{1,2}Z`, `ingest_config tools/templates/instruments/molecubes_ni_live.yaml`,
  `original_name 1207/260212/0324_m61/20260212130722_CT/recon_{0,1}`, `session_id 1207_260212_0324_m61`,
  `subject_ids 61-AE-biomaGUNE-0325`.
- Payload: `J:\gjesus3-data\raw\DICOM\2026\2026-02\ACQ-20260212-CT-001\ACQ-20260212-CT-001.data\recon0.dcm`
  is **5 bytes** containing the ASCII text `DCM-0`. Its `metadata.json` records
  `src_relpath recon_0/a.dcm` and `session_extra {tracer: FDG, dose: 10 MBq}` — the fixture described
  at `ni_live_operator_plan.md:39-43`.
- Also created: `PROJ-0051` / `AE-biomaGUNE-0325` in `registry_projects.csv` (description:
  "Auto-created during live-box NI sync; animal protocol 0325. PROVISIONAL."), the project folder
  `J:\gjesus3-data\projects\AE-biomaGUNE-0325\` (`_project.yaml`, `index.html`, `provenance.csv`),
  one `registry_subjects.csv` row (`61-AE-biomaGUNE-0325`), and `pending_subject_metadata.csv`
  lines 250-251.
- **The hard links succeeded** (Windows/SMB), so the 5-byte payloads are *also* linked into
  `…\projects\AE-biomaGUNE-0325\raw_linked\CT_0324_m61_20260212_20260212130722_recon0\recon0.dcm`
  and `…_recon1\recon1.dcm`. Any purge must cover those too.

Per `CLAUDE.md`'s production-lifecycle rules this is exactly what "done means done in true
production" is there to prevent. **The plan doc is on the branch about to merge and still asserts the
false premise** — it must be corrected alongside whatever is decided about the data (§5 ONBOX-02).

---

## 4. Action list

### 4.1 BLOCKERS — before merge

| # | What | Where | Why |
|---|---|---|---|
| B1 | Decide + execute on the two synthetic production acquisitions (purge vs document-and-keep) | `J:\gjesus3-data\registries\*`, `raw\DICOM\2026\2026-02\ACQ-20260212-CT-00{1,2}\`, `projects\AE-biomaGUNE-0325\` | A 5-byte `DCM-0` file is in true production, hard-linked into a project folder (§3.7) |
| B2 | Correct `tasks/ni_live_operator_plan.md:39-43` — the §3.2/§3.3 verification went to production, not a throwaway NAS | `tasks/ni_live_operator_plan.md` | The false premise is on the branch being merged; next reader re-inherits it |
| B3 | Re-run the on-box test with Steps 3, 5 and Step 6's **second** command, and `tee` the stdout | `S:\...\ni-live-test\RUN_THE_TEST.md` | The three merge gates (per-recon rows, `session_extra`, `pending_links.csv`) are all still unverified (§2) |
| B4 | Reset the sandbox NI state (or run the first two gates against a fresh empty local NAS) before B3 | `J:\gjesus3-sandbox\registries\`, `raw\DICOM\`, `projects\*\raw_linked\` | Its 122 pre-per-recon rows dedup against nothing; a `--go` would duplicate them (§3.6) |
| B5 | Suppress the metadata prompt when the run cannot write — **and** when `--go` is passed | `tools/operator/ni_ingest.py:404` (+ `:624`, `mri_ingest.py:517`) | It fired 3× on read-only steps and is not suppressed by `--go` (§3.3) |
| B6 | Prefill `session_id`/`sample_id` in `_write_plan` from the **post-correction** case keys | `tools/operator/ni_ingest.py:361-362` | Contradicts locked D5; reads to operators as data loss (§3.2) |
| B7 | Fix the `--root` silent-zero + the wrong invocation documented in the template | `tools/ni_live_discover.py:204-208`, `:278`; `tools/templates/instruments/molecubes_ni_live.yaml:12` | Wrong form exits 0 and can write a header-only CSV that looks real (§3.4a) |

### 4.2 SHOULD happen soon (not merge-blocking)

| # | What | Where | Why |
|---|---|---|---|
| S1 | Scoped NI service account for the Mac; clear the cached `rtasseff` credential | IT request + `tasks/tasks.md` | Shared account currently reaches production with full write (§3.0) |
| S2 | Decide + fix the `new recon/` depth mismatch, including link-name disambiguation | `molecubes_ni_live.yaml`, `tools/ingest/config.py:483-489` | One session can never sync; a naive fix creates a link collision (§3.1a) |
| S3 | Fix the stale `sample_id`/`session_id` after a project correction (re-derive `discovered.subject` in `apply_pre`, or document the post-override as the repair path) | `tools/ingest/ni_corrections.py:57` | A corrected session writes the *old* project code into two derived ids (§3.2) |
| S4 | Align NI-live `sample_id` with the production `m<animal>_<project>` form | `molecubes_ni_live.yaml:52` | Raw folder text matches neither the DECIDED form nor production convention (§3.2) |
| S5 | Add the `--plan` reconciliation line (`N scans → M sessions → K planned`) + an `n_recons` column, with an anchor-shaped filter on dropped names | `tools/operator/ni_ingest.py:344-373` | This whole question would not have been asked (§3.1) |
| S6 | Fix the live `pending_dicom_regen.csv` header drift (evidence favours ADOPT `nonimage_marker` + the extended vocabulary) | `tools/ingest/pending_dicom.py:39-48` + the spec | The DICOM queue is write-broken in true production (§3.5) |
| S7 | Put all three pending writes under `locking.registry_lock`; make `pending.py::_write_all` atomic | `tools/ingest/pending{,_dicom,_links}.py` | Prerequisite for any scheduled drainer (§3.5) |
| S8 | Doc pass: flip the stale `session_id` DRAFT markers; add the missing `10_TOOLS.md` section for `--plan`/`--corrections`/`subject_parse`; correct `08_METADATA.md:398` (PET+CT *do* share `StudyInstanceUID`); record `session_id` ≡ DICOM Study for NI | `mfb-rdm-docs/06,08,10`, `CLAUDE.md:75`, `tools/INGEST_CLI.md`, `tools/operator/README.md` | The docs are why a working column looked missing (§3.2) |
| S9 | Port `date_flag` + `subject_flags` into the worksheet, then drop Step 1 from the operator flow | `tools/operator/ni_ingest.py`, `tools/ni_live_discover.py:142-151` | 4-command flow, one path string — without losing real signal (§3.4d) |
| S10 | Add `timepoint` to `NI_CORRECTION_FIELDS` (or amend D5) | `tools/ingest/ni_corrections.py:46-53` | Spec says prefilled; the column doesn't exist, so a mis-typed timepoint can't be fixed (§3.2) |

### 4.3 BACKLOG

- **B-1** `tools/pending_status.py` + scheduled drain — the full drafted entry is in §3.5 (file into
  `tasks/BACKLOG.md` with the three corrections listed above it).
- **B-2** Flag transposed `series`/`date` path levels (5 sessions in this batch) and year-off folder
  dates (25 of 141 scans) as blocking-or-warning at plan time — both currently bake into permanent
  dedup identity unflagged (§3.2).
- **B-3** Let `ni_live_discover.py` accept researchers outside the hardcoded `MFB_FOLDERS`
  (`:45`, `:231-234`) — Step 1 refuses a researcher Step 2 accepts (§3.4a).
- **B-4** §3.6 Mac GUI wrapper — already backlogged; confirmed **not** a prerequisite (§3.3).

---

## 5. Open questions — decisions only Ryan can make

| ID | Question | Why it needs you | Status |
|---|---|---|---|
| **ONBOX-01** | **The ID/ISA semantics call.** Is the ISA **Investigation** the funded/project-office id (`1207`, the Molecubes "Study name") or the AE animal-protocol code (`0522`)? Today the code routes on the AE code and **134 NI + 10,330 MRI production rows** are keyed to it; switching re-keys every NI project folder and breaks MRI alignment. A third option nobody has costed: keep AE as the project and add the funded id as its **own column/field** (it's already captured twice — `discovered.series` and `discovered.ni_study_name` — and recorded nowhere), which loses nothing but needs a `migrate_registry_columns.py` pass over 13,582 rows. Logged as NI-LIVE-09. | Spec-level; affects XNAT mapping and all future NI routing | 🔶 OPEN — **do not let it block the merge** |
| **ONBOX-02** | Purge the two synthetic production acquisitions + `PROJ-0051` + the project folder + the subject row + `pending_subject_metadata.csv:250-251` + the two `raw_linked/` hard links — or keep and document? | True-production data hygiene; only you can authorise a production delete | 🔶 OPEN — blocker either way |
| **ONBOX-03** | `new recon/` folders: (a) teach `path_parse` to absorb an optional extra level *and* disambiguate the link name, (b) treat it as a distinct reconstruction, or (c) declare it an operator naming violation and have the NI platform stop creating it? | Bend the tool or bend the convention — a convention call | 🔶 OPEN |
| **ONBOX-04** | Is every Molecubes NI scan effectively whole-body? If you can assert it as a platform fact it's a one-line `anatomy:` block; if not, the honest option is a non-authoritative auto-hint from the bed-position fields (`ni_metadata.py:98-105`). **No document supports it today.** | Platform fact only you/the NI team can assert | 🔶 OPEN |
| **ONBOX-05** | Should `sample_id` become an AUTO projection of `subject.facility_animal_id` for all in-vivo work (closes REG-01, `06_REGISTRIES.md:455`)? Cross-instrument, mixed semantics against 13,582 rows. | Schema-refresh decision, not a branch fix | 🔶 OPEN — deliberately deferred |
| **ONBOX-06** | Sandbox reset before the re-run: purge its 122 NI rows + payloads, or migrate their `original_name` to the `/recon_<idx>` form? (Sandbox only — production is unaffected.) | Determines how B3/B4 are run | 🔶 OPEN |
| **ONBOX-07** | Is the merge gate strictly **all three** artefacts, or is a local-only Step 5 enough for per-recon + `session_extra`, with only `pending_links.csv` requiring the Mac? | Decides one on-box session or two | 🔶 OPEN |
| **ONBOX-08** | Should `--live` prompt at all, or be flags-only until the §3.6 GUI exists? (Flags-only contradicts `08_METADATA.md:615`, inside a DECIDED section — it needs a doc change, not just a code change.) | UX + spec call | 🔶 OPEN |
| **ONBOX-09** | Adopt `nonimage_marker` + `not-applicable`/`no-source` into `PENDING_DICOM_FIELDS` and the spec, or migrate the live file back to 8 columns? Evidence favours **adopt** — but only you know what the 2026-07-15 pass actually ran (it was an uncommitted script). | You ran it; nobody else can reconstruct it | 🔶 OPEN |
| **ONBOX-10** | Should `relink_pending.py` (and `relink_mri_regen.py`) flip to dry-run-by-default before either is put on a scheduler? Operator-facing behaviour change. | Safety posture call | 🔶 OPEN |
| **ONBOX-11** | Confirm "45": we can't find it in any artefact. Step 1's own summary prints `multi-animal scans (>1): 45` right under `acquisitions : 141` — is that what you were reading? | Only you saw the screen | 🔶 OPEN — low stakes, but unresolved |

---

*Written 2026-08-05 from a read-only review of the returned artefacts, the sandbox, and (read-only)
true production. Six parallel investigations, each adversarially verified; refuted claims have been
dropped or restated with their correction, and every remaining low-confidence item is marked as
such above.*
