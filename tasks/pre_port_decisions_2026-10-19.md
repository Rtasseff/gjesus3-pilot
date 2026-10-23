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

## Still to rule

- **Decisions 7–17** (#10 project dates, #5 the dedup key, #14 the production guard, #28/#29 the design notes).
- **Decision 1's follow-up:** its own issue, or folded into another? (BACKLOG MODERATE "an acquisition with an unknown
  date", 2026-10-23.)
- **18. The curated datasets' `provenance.csv` does not follow 07_PROVENANCE's ✅ schema.** 07 §3.4 (12 columns:
  `file_id`, `output_path`, `input_refs`, …) is what every project's `provenance.csv` uses, and 12 §5.2 says a dataset
  follows the same format. The four live datasets (read-only, 2026-10-23) each have their own, richer header, of 24 to
  28 columns: `file_path`, `file_role`, `acq_id` + `acq_ids_all`, `subject_id`, `review_status`, `sha256`, … with no
  `file_id`, `output_path` or `input_refs`, and the four headers differ from each other. A schema call on a ✅ spec.
- **The subject-lookup fix:** its own GitHub issue, or folded into #12 / #18? (BACKLOG HIGH "Subject records from the
  wrong animal".)
