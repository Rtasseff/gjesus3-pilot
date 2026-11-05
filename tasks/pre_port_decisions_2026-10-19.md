# Pre-port decisions: Ryan's rulings on the integration branch

**Branch:** `integration/pre-port-2026-10-17` · **Asked:** from 2026-10-19 · **Ruled:** 2026-10-23 onward ·
**Source of the questions:** the pre-port review's §2 (17 decisions, each with a recommendation), kept outside the repo.
The triage behind the branch is [`backlog_triage_2026-10-10.md`](backlog_triage_2026-10-10.md).

Each entry gives the call, the recommendation, and Ryan's ruling in his words, then what follows from it.

| # | Issue | The call | Recommendation | Ruling |
|---|---|---|---|---|
| 1 | #7 | A case with no known acquisition date is refused, not dated to today; `ingest.allow_unknown_acquisition_date: true` keeps the old way | Accept | **Accepted at the system level, with a follow-up for the tools** (2026-10-23, below) |
| 2 | #8 | The three new validator classes are WARN, not ERROR | Accept | **Flipped: ERROR** (2026-10-23) |
| 3 | #8 | Unknown sentinels and `pending-db` become coverage lines | Accept | **Accepted** (2026-10-23) |
| 4 | #8 | The 146 + 138 pre-Phase-3 sidecars still WARN "missing block" | Leave as WARN | **Left as WARN** (2026-10-23) |
| 5 | #6 | NOT SEEN reports only the dot-named entries the pattern would have matched | Accept | **Accepted** (2026-10-23) |
| 6 | #6 | An unknown `filename_parse.source` is a `ValueError`, not a silent fall-back to `name` | Accept | **Accepted** (2026-10-23) |
| 7 | #10 | Only an acquisition registered to a project widens its dates, not one shared into it | Accept | **Flipped: no ingest or import moves a project's dates at all** (2026-11-03, below) |
| 8 | #10 | `_project.yaml` dates are set at creation only | Accept | **Accepted** (2026-11-03) |
| 9 | #10 | An auto-created project with no real acquisition date gets today | Accept | **Accepted** (2026-11-03) |
| 10 | #10 | A cp1252 `_project.yaml` edited in the Project Manager is saved back as UTF-8 | Accept | **Accepted** (2026-11-03) |
| 11 | #5 | 06 §2.10: a case is already ingested when any of its keys is in the registry or the tombstones; a `.czi` adds `(instrument, timestamp to the second, file name, case-insensitive)` | Accept; mark §2.10 ✅ | **Accepted** (2026-11-03) |
| 12 | #5 | Q3: no content key for a `00:00:00` timestamp. Q4: file names compared case-insensitively | Accept both | **Accepted** (2026-11-03) |
| 13 | #5 | Q1, Q2, Q5, Q6 deferred | Accept the deferrals | **Accepted** (2026-11-03) |
| 14 | #5 | Q7: re-rate the priority | Merge the core now; the follow-ups MEDIUM | **Accepted** (2026-11-03) |
| 15 | #5 + #14 | The commit-time re-check refuses a case when any of its dedup keys appeared since the snapshot (`d627780`) | Accept | **Accepted** (2026-11-03) |

## 1. Undated cases (#7)

**Ryan, 2026-10-23:** "I am not 100% ok with a hard refusal. Sometimes we may not know the date. The ingest should
supply something though and the registry should refuse to enter anything without a date for acquisition. I guess at
that stage if a guess is given to the registry then the user should describe it in notes, but that is all on the
user's side, from a system pov I suppose I am agreeing that it should reject. But for our scripts and tools, we should
offer the user a way to put in an acquisition with an unknown date, we should offer either a manual entry or today's
date and fill in the notes for them. So I guess it depends on what level we are denying at."

**What follows:**
- **The system rule (accepted):** nothing reaches the registry without an acquisition date. The branch's refusal stands.
- **The tools (a follow-up, not in this merge):** the operator tools offer, for a case with no known date, either a
  date typed by the user or today's date, and in both cases fill `notes` to say the date is a stand-in. Today the
  opt-in `allow_unknown_acquisition_date` puts today's date in the ACQ-ID but leaves the registry's
  `acquisition_datetime` **blank**, with a log WARN only: no note, no GUI prompt, and a blank date the registry accepts.
  The follow-up writes the stand-in date into `acquisition_datetime`, adds the note, and makes the registry writer
  (and the validator) refuse a blank date.

## 2. The validator's new classes (#8)

**Ryan, 2026-10-23:** "they should be errors and we should address this."

**What follows:**
- The three classes (`;`-cell hygiene, acquired before the subject's birth, unregistered `/raw/` folder) are ERROR.
- The 2026-10-17 dry run found 0 `;`-cell rows and 0 orphan folders, but **57 before-birth rows**. So the validator
  reports **57 errors** until those rows are repaired. They are the label errors in the BACKLOG HIGH item "Subject
  records from the wrong animal", whose repairs Ryan ruled on 2026-10-21 (on `fix/subject-lookup-dates`, which merges
  after this branch).
- The STATUS "Re-verifying" baseline says so, until those repairs run.

## 3. Coverage lines (#8)

**Ryan, 2026-10-23:** "accept."

## 4. Pre-Phase-3 sidecars (#8)

**Ryan, 2026-10-23:** "leave as is." Decided with the enrichment backfill, not at this merge.

## 5 and 6. What the ingest reports (#6)

**Ryan, 2026-10-23:** "I accept the recorded recommendation for (5) and (6)."

**What follows:** the two 10_TOOLS lines already marked ✅ are now true; no marker changes.

## 7 to 10. Project dates (#10)

**Ryan, 2026-11-03:** "I want to be clear, that the date in a project is not super critical. It could be auto set when
the project is autocreated for the first time it is made by whatever script makes projects, that's fine. After that, it
really should be the project manager tool that lets people change dates. Something like when a project closes would be
autoset when the project manager tool is used to close a project. But there is certainly no need to touch the dates at
acquisition. I believe the recommendations you suggest above are aligned with this basic set of principles and I agree
with all your recommendations on this batch."

**What follows:** 8, 9 and 10 fit the principle and stand. **7 did not:** the branch widened `start_date` /
`last_activity` at every ingest (Step 11b) and raw import, which the principle says is not needed. Put back to Ryan the
same day:

**Ryan, 2026-11-03, on 7:** "Let's remove date changes at ingest."

**What follows from 7:**
- Step 11b and the raw import's widening are removed, with `widened` / `widen_dates`. A new project still gets its
  dates at creation: the acquisition's date when an ingest auto-creates it (decision 8), else today (decision 9).
- 05 §7 and 06 §4.2 / §4.4 no longer say these columns mean first and newest acquisition. Existing values stay.
- #10's done-when ("the recompute leaves no project with a creation-date `start_date`") is dropped: a creation date is
  now correct. The production run of `recompute_project_dates.py` (29 of 65 projects) is dropped; the tool stays, not
  routine, because its dry run reports each project's real acquisition span. `fix_project_yaml_encoding.py`'s run stays.
- `reopen_project.py` still sets a reopened project's dates from its acquisitions: a Data Office action, unchanged.
- **New BACKLOG item:** the Project Manager edits the dates and stamps one on close (a schema call: `closed_date` is
  not in the registry), and the retention close-out reads `registry_raw.csv`.

## 11 to 15. The dedup key (#5, #14)

**Ryan, 2026-11-03:** "I am also fine with your other recommendation including 'Merge the core now; follow-ups become
MEDIUM'."

**What follows:** 06 §2.10 and the 10_TOOLS bullet are ✅. Q1 goes with #11; Q2 and Q5 take one small new issue; Q6 is
noted on #19 / #40; all MEDIUM.

## Still to rule

- **Decision 17** (#28/#29 the design notes).

**Decision 16, the production guard: built 2026-11-05** on `fix/production-guard`, as recommended (a `registries\.production` marker; a real `ingest_raw.py` run against it needs `--production`). Ryan, 2026-11-05, on the Box A port: "do what ever needs to be done to finish this port". The port plan lists the guard in Phase 0, so it is taken as his go on the recommendation. Writing the marker on the live root is a production write, done after the merge.
- **Decision 1's follow-up:** its own issue, or folded into another? (BACKLOG MODERATE "an acquisition with an unknown
  date", 2026-10-23.)
- **18. The curated datasets' `provenance.csv` does not follow 07_PROVENANCE's ✅ schema.** 07 §3.4 (12 columns:
  `file_id`, `output_path`, `input_refs`, …) is what every project's `provenance.csv` uses, and 12 §5.2 says a dataset
  follows the same format. The four live datasets (read-only, 2026-10-23) each have their own, richer header, of 24 to
  28 columns: `file_path`, `file_role`, `acq_id` + `acq_ids_all`, `subject_id`, `review_status`, `sha256`, … with no
  `file_id`, `output_path` or `input_refs`, and the four headers differ from each other. A schema call on a ✅ spec.
- **The subject-lookup fix:** its own GitHub issue, or folded into #12 / #18? (BACKLOG HIGH "Subject records from the
  wrong animal".)
