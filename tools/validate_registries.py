#!/usr/bin/env python3
"""validate_registries.py — READ-ONLY consistency checker for the registry area.

Walks `registries/` + the `/raw/` tree under a NAS root and reports problems.
Implements REG-04 (tasks.md §3.2). NEVER writes anything; the NAS can be
mounted read-only. Exits nonzero (1) if any ERROR-level issue is found, 0
otherwise. WARN-level findings (Phase 3 enrichment gaps under the non-blocking
metadata model, and the hygiene checks below) never affect the exit code.

HOW IT REPORTS (since 2026-10-10, issue #8)
  A finding CLASS is reported once, with its row count and a few example rows
  (`--examples N`, default 5; `--examples all` lists every row, the old
  per-row dump). Ten thousand rows with one defect used to be ten thousand
  lines, which is a report nobody reads; the ~580 lines that were actionable
  were invisible among 36,000 sentinel warnings.
  The documented "unknown" sentinels are no longer warnings at all: they are
  reported as COVERAGE ("`condition.is_control` known on N of M"), because an
  optional field nobody has supplied yet is one design choice multiplied by
  the archive, not M problems. Likewise `subject.source == "pending-db"`: it
  is a queue with its own drain tool (`recover_subject_metadata.py`) and its
  own registry, so it is an info line, not a warning.

WHAT IT CHECKS
  registry_raw.csv structure
    - header EXACTLY equals ingest.registry.REGISTRY_FIELDS (the schema is
      imported, never hardcoded — 06_REGISTRIES is the contract).
    - no duplicate acq_id.
    - acq_id matches ACQ-YYYYMMDD-<CODE>-NNN.
    - required columns non-empty per row: acq_id, registration_datetime,
      data_ecosystem, instrument, canonical_path.
    - no registry cell (any column) contains unsubstituted template residue:
      `${...}` / `{{...}}` resolver expressions, or a `<...>` angle-bracket
      placeholder. ERROR — this is what let a literal "Bruker BioSpec
      <7T|11.7T>" sit in 10,314 production instrument_model cells through
      repeated clean validator runs (fixed 2026-08-20; see CHANGELOG).
    - the operator hold value `pending-claim` (ingest.registry.OPERATOR_HOLD,
      "awaiting claim"; 06_REGISTRIES §2.3a-bis) is accepted in the `operator`
      column -- neither an ERROR nor a WARN; the rows are counted and reported
      as one info line -- and is an ERROR when it is the WHOLE value of any
      OTHER column (stripped, case-insensitive): the token means one thing
      only. A note that merely mentions it in running text is documentation,
      not drift, and is not reported. The template-residue check above is not
      relaxed for it (the token carries no template syntax, so it passes that
      check on its own).
    - sample_type, when set, is in the controlled vocab
      {tissue, organism, cells, material, phantom}.
    - canonical_path starts with /raw/ and the acquisition folder exists on
      disk (canonical_path joined to nas_root).
    - project_id, when set and matching PROJ-XXXX, exists in
      registries/registry_projects.csv.
    - subject_ids carries no null-alias facility id (`<n>-AE-biomaGUNE-None`,
      or a bare `<n>-AE-biomaGUNE-` with nothing after the stem). ERROR, not
      WARN: the alias is what makes the id UNIQUE, so a null one is ambiguous
      — every null-alias protocol collapses onto the same id and the subjects
      table then merges two different animals into one row.
    - WARN (hygiene, 2026-10-10): the `;`-packed cells `subject_ids`,
      `modalities_in_study` and `project_id` carry no empty segment (`A;;B`),
      no leading/trailing separator and no duplicate member (`A;A`). The
      writers (ingest/project_ids.py, ingest/registry.py) normalize on write,
      so a violation means a hand edit in Excel. WARN for now; the Data Office
      can promote it to ERROR once production is known to be clean.
    - WARN (plausibility, 2026-10-10): an acquisition dated BEFORE its
      subject's date_of_birth (registry_subjects.csv). Age alone is a weak
      signal (a naive ">550 days" rule flags 1,332 legitimate ageing-study
      rows), so only the impossible case is reported, never "implausible".
      The facility procedure cross-check (does the animal have any logged
      procedure near the acquisition date?) needs the live DB and is NOT
      built here (BACKLOG "plausibility checks in validate_registries").

  the /raw/ tree (2026-10-10)
    - WARN: an acquisition folder `raw/<ECO>/<YYYY>/<YYYY-MM>/<ACQ-ID>/` with
      no registry row and no tombstone -- the partial-ingest signature (ids
      allocated, folders written, the registry commit never landed; 17 such
      folders sat unnoticed for a month in 2026-07/08). /raw/ is system-owned,
      so unlike project folders (05_PROJECTS §3a) this IS an integrity
      question. WARN rather than ERROR until the Data Office decides the rule
      (BACKLOG "17 orphan acquisition folders").

  retired_acquisitions.csv (the tombstone file; 06_REGISTRIES §2.9) -- only when it exists
    - header EXACTLY equals ingest.retired.RETIRED_FIELDS.
    - disposition and bytes_fate are known values (ingest.retired.DISPOSITIONS / BYTES_FATES). ERROR.
    - a `reidentified` id's superseded_by is the same acquisition under another instrument code
      (same original_name and acquisition_datetime, a different instrument). ERROR.
    - no id is both live (registry_raw) and retired. ERROR -- also the signature of a
      retire run that crashed mid-commit: re-run retire_acquisition.py to finish it.
    - every superseded_by (blank only for an orphan or a no-dicom placeholder,
      ingest.retired.NO_SUPERSEDER) names a LIVE acquisition. ERROR.
    - no curated dataset (registry_datasets.csv + the text files under
      curated_datasets/) cites a retired id. ERROR.
    - a retired id's /raw/ folder no longer exists. ERROR -- a retire run that
      stopped before its bytes step; re-run it.
    The /raw/ "folder exists" check above only walks LIVE rows, so retired ids
    are never reported as missing folders.

  registry_subjects.csv
    - project_alias is never the literal "None"/"null", and never blank for a
      facility_id that IS a canonical `<n>-AE-biomaGUNE-<NNNN>` id. A blank
      alias on a NON-canonical id (the DTS24 human subjects, facility ids like
      "LEONE_1.01" with source=dicom-header) is legitimate and not reported.

  Phase 3 enrichment (WARN-level + coverage, non-blocking model — 08_METADATA §4.3-4.7)
    For rows whose sample_type is organism or tissue, the sidecar
    metadata.json must carry a subject: block AND a condition: block (and an
    anatomy: block for organism). Missing blocks are WARNs. The explicit
    unknown sentinels (subject.source == "pending-db", condition.is_control ==
    null, anatomy.is_whole_body == null) are legitimate (never-block) states
    and are reported as coverage / info, not as warnings.

Usage:
    python tools/validate_registries.py --nas-root J:\\gjesus3-data
    python tools/validate_registries.py            # uses $GJESUS3_ROOT
    python tools/validate_registries.py --no-enrichment   # skip Phase 3 sidecar checks
    python tools/validate_registries.py --examples all    # every row of every class
"""

import argparse
import csv
import json
import os
import re
import sys
from collections import OrderedDict
from datetime import datetime

# Make `from ingest import ...` / `import animal_db` work whether the script
# is launched from the repo root or from tools/ (mirrors ingest_raw.py).
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from ingest import registry  # noqa: E402  (after sys.path tweak)
from ingest import retired  # noqa: E402
# Aliased: the local variable `project_ids` in check_registry_raw is the SET of
# known ids, and would shadow the module.
from ingest import project_ids as proj_id_cell  # noqa: E402
# Imported for the ONE constant, not for the DB: the subject-id stem must be
# read from the module that composes the ids, so the detector and the composer
# can never drift apart. animal_db imports cleanly with no pymysql/credentials.
from animal_db import PROJECT_CODE_STEM  # noqa: E402


def log(msg, level="INFO"):
    """Timestamped log line to stderr; ASCII only for the Windows console."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {level}: {msg}", file=sys.stderr)


# ---- Constants -----------------------------------------------------------

# acq_id grammar: ACQ-YYYYMMDD-<CODE>-NNN (CODE = uppercase alnum instrument
# code, NNN = zero-padded sequence). 06_REGISTRIES §2.2.
ACQ_ID_RE = re.compile(r"^ACQ-\d{8}-[A-Z0-9]+-\d{3}$")
PROJ_ID_RE = re.compile(r"^PROJ-\d{4}$")

REQUIRED_COLUMNS = [
    "acq_id",
    "registration_datetime",
    "data_ecosystem",
    "instrument",
    "canonical_path",
]

# Controlled vocab for sample_type (06_REGISTRIES / data contract). Blank is
# allowed; any other non-blank value is an ERROR.
SAMPLE_TYPE_VOCAB = {"tissue", "organism", "cells", "material", "phantom"}

# sample_types that require Phase 3 preclinical enrichment blocks.
ENRICH_SAMPLE_TYPES = {"organism", "tissue"}

# The `;`-packed list columns of registry_raw.csv (06_REGISTRIES §2.3b and
# NI-LIVE-08). Their writers normalize on write; the hygiene check reports what
# a hand edit left behind.
MULTI_VALUE_COLUMNS = ("subject_ids", "modalities_in_study", "project_id")
MULTI_VALUE_SEP = ";"

# How many example rows a finding class shows by default (`--examples`).
DEFAULT_EXAMPLES = 5

# Canonical facility subject id: <animal_code>-AE-biomaGUNE-<NNNN>. Mirrors
# animal_db.SUBJECT_ID_RE but is deliberately LOOSER on the alias — it must
# also match the broken forms we are hunting, which the strict `\w+` version
# would either reject (empty alias) or silently accept (the literal "None").
SUBJECT_ID_STEM_RE = re.compile(
    r"^(?P<animal_code>\d+)-" + re.escape(PROJECT_CODE_STEM) + r"-(?P<alias>.*)$",
    re.IGNORECASE)

# Alias values that carry no information. "none"/"null" are the SQL-NULL leak:
# a facility project row with a populated project_code and a NULL projectAlias
# used to format straight into the id string. See tasks/BACKLOG.md
# "Facility-DB null project alias" and tasks/SUBJECT_ID_NULL_ALIAS_HANDOFF.md.
NULL_ALIASES = {"", "none", "null"}

SUBJECTS_REGISTRY = "registry_subjects.csv"


# ---- Issue collection ----------------------------------------------------

class Issues:
    """Accumulates ERROR/WARN findings with optional row context.

    `errors` / `warnings` stay lists of ``(acq_id, msg)`` 2-tuples (every
    caller and test reads them that way). The finding CLASS each belongs to
    -- what the report groups on -- is kept in the parallel ``error_cls`` /
    ``warn_cls`` lists; it defaults to the message itself, so a check whose
    message varies per row passes an explicit ``cls``.
    """

    def __init__(self):
        self.errors = []
        self.warnings = []
        self.error_cls = []
        self.warn_cls = []
        # Rows whose `operator` is the hold value. A count for print_report's one
        # info line -- deliberately NOT a warning (that channel is saturated).
        self.operator_hold = 0
        # Coverage of the optional enrichment fields: label -> {"known": n,
        # "unknown": n}. Reported once each, never per row.
        self.coverage = OrderedDict()
        # Free-form info lines (counts, queue sizes). Neither errors nor warnings.
        self.notes = []

    def error(self, msg, acq_id=None, cls=None):
        self.errors.append((acq_id, msg))
        self.error_cls.append(cls or msg)

    def warn(self, msg, acq_id=None, cls=None):
        self.warnings.append((acq_id, msg))
        self.warn_cls.append(cls or msg)

    def cover(self, label, known):
        """Count one observation of an optional field: known (True) or the
        documented unknown sentinel (False)."""
        c = self.coverage.setdefault(label, {"known": 0, "unknown": 0})
        c["known" if known else "unknown"] += 1

    def note(self, msg):
        self.notes.append(msg)


# ---- Helpers -------------------------------------------------------------

def _read_csv_rows(path):
    """Read a CSV into (header, list-of-row-dicts).

    Tolerant of legacy non-UTF-8 bytes in older registries (e.g. accented
    project descriptions written with a cp1252 console): falls back to
    latin-1, which never raises on byte input. Returns (None, []) if absent.
    """
    if not os.path.exists(path):
        return None, []
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                f.seek(0)
                dreader = csv.DictReader(f)
                rows = list(dreader)
            return header, rows
        except UnicodeDecodeError:
            continue
    return None, []


def _acq_folder_on_disk(nas_root, canonical_path):
    """Join a /raw/-rooted canonical_path to nas_root -> local filesystem path.

    canonical_path is a POSIX-style, leading-slash path (e.g.
    "/raw/DICOM/2021/2021-10/ACQ-.../"); strip the leading slash and any
    trailing slash, split on "/" so it resolves correctly on Windows too.
    """
    rel = canonical_path.strip().lstrip("/").rstrip("/")
    parts = [p for p in rel.split("/") if p]
    return os.path.join(nas_root, *parts)


def _load_project_ids(registries_dir, issues):
    """Return the set of project_id values in registry_projects.csv.

    A missing projects registry is a WARN (project_id cross-checks are then
    skipped), not a hard ERROR — the file may legitimately not exist yet on a
    fresh NAS.
    """
    path = os.path.join(registries_dir, "registry_projects.csv")
    header, rows = _read_csv_rows(path)
    if header is None:
        issues.warn(
            "registry_projects.csv not found; project_id existence checks "
            "skipped."
        )
        return None
    return {(r.get("project_id") or "").strip() for r in rows}


# ---- Null-alias subject-id checks (ERROR-level) --------------------------

def is_facility_id(subject_id):
    """True when the id claims to name an animal under an AE-biomaGUNE protocol.

    This is the line between IN scope and OUT: a DTS24 human subject id
    ("LEONE_1.01", source=dicom-header) has no animal protocol, so a blank
    alias on it is correct and must never be reported (handoff §7).
    """
    return PROJECT_CODE_STEM.lower() in (subject_id or "").lower()


def null_alias_of(subject_id):
    """The broken alias in a facility subject id, else None.

    Returns the offending alias string ("" / "None" / "null") when `subject_id`
    is a `<animal_code>-AE-biomaGUNE-<alias>` id whose alias carries no
    information; returns None when the id is fine, or is not a facility id at
    all.
    """
    s = (subject_id or "").strip()
    m = SUBJECT_ID_STEM_RE.match(s)
    if m:
        alias = m.group("alias").strip()
        return alias if alias.lower() in NULL_ALIASES else None

    # Belt and braces. A malformed id that still ENDS in the broken stem (no
    # animal code, a stray prefix) fails the grammar above and would slip past
    # a grammar-only detector — which is precisely how a backfill declares
    # victory over rows it never touched. Under-report nothing here.
    low = s.lower()
    for null in ("none", "null"):
        if low.endswith(f"-{PROJECT_CODE_STEM.lower()}-{null}"):
            return s[-len(null):]
    if low.endswith(f"-{PROJECT_CODE_STEM.lower()}-"):
        return ""
    return None


def check_subject_ids(cell, label, issues):
    """ERROR for every null-alias id packed into one registry_raw.subject_ids cell.

    The cell is a `;`-joined 1..N list (NI-LIVE-08); check it id-by-id so a
    multi-animal scan reports the bad member, not the whole cell.
    """
    for part in (cell or "").split(";"):
        sid = part.strip()
        if not sid:
            continue
        alias = null_alias_of(sid)
        if alias is not None:
            issues.error(
                f"subject_ids carries the null-alias facility id '{sid}' "
                f"(alias {alias!r}) - ambiguous: every null-alias protocol "
                f"collapses onto this id", label,
                cls="subject_ids carries a null-alias facility id")


# ---- Multi-value cell hygiene (WARN-level) -------------------------------

def check_multivalue_cells(row, label, issues):
    """WARN for a `;`-packed cell that a hand edit left malformed.

    Three shapes, each its own class: an empty segment (`A;;B`), a leading or
    trailing separator (`A;`), a duplicate member (`A;A`). Whitespace around a
    separator is NOT reported: every reader tolerates it
    (ingest/project_ids.split_project_ids), and Excel leaves it routinely.
    The existence half of `project_id` (does each id exist?) is check 8 below.
    """
    for col in MULTI_VALUE_COLUMNS:
        cell = row.get(col)
        if not isinstance(cell, str) or MULTI_VALUE_SEP not in cell:
            continue
        parts = cell.split(MULTI_VALUE_SEP)
        if not parts[0].strip() or not parts[-1].strip():
            issues.warn(
                f"column '{col}' starts or ends with the separator "
                f"(value: {cell!r})", label,
                cls=f"column '{col}' starts or ends with the separator")
        if any(not p.strip() for p in parts[1:-1]):
            issues.warn(
                f"column '{col}' has an empty segment (value: {cell!r})", label,
                cls=f"column '{col}' has an empty segment")
        members = [p.strip() for p in parts if p.strip()]
        dupes = sorted({m for m in members if members.count(m) > 1})
        if dupes:
            issues.warn(
                f"column '{col}' repeats {dupes} (value: {cell!r})", label,
                cls=f"column '{col}' repeats a member")


# ---- Unsubstituted template-residue checks (ERROR-level) -----------------

# Unsubstituted template syntax left in a registry cell means an `# EDIT:`
# manual step was described but never performed before a config was run.
# This is the detection gap that let a literal "Bruker BioSpec <7T|11.7T>"
# placeholder sit in 10,314 production instrument_model cells through
# repeated clean validator runs (fixed 2026-08-20; see CHANGELOG). Three
# forms recognized: `${...}` / `{{...}}` unresolved resolver expressions,
# and a `<...>` angle-bracket placeholder (e.g. the example above, or
# "<REQUIRED - set via mri-ingest --operator, or replace here>").
TEMPLATE_RESIDUE_RE = re.compile(r"\$\{[^}]*\}|\{\{[^}]*\}\}|<[^<>\n]*>")


def check_template_residue(row, label, issues):
    """ERROR for any registry cell that still contains unsubstituted template
    syntax.

    Deliberately column-agnostic: it does not matter which column broke —
    that is exactly what let the MRI instrument_model incident above go
    undetected for as long as it did. Scans every cell in the row rather
    than special-casing a known-risky column.
    """
    for col, value in row.items():
        val = value or ""
        if not val:
            continue
        m = TEMPLATE_RESIDUE_RE.search(val)
        if m:
            issues.error(
                f"column '{col}' still contains unsubstituted template "
                f"syntax {m.group()!r} (full value: {val!r})", label,
                cls=f"column '{col}' still contains unsubstituted template syntax")


# ---- The `operator` hold value (ERROR outside `operator`) ----------------

def check_operator_hold(row, label, issues):
    """The hold value `pending-claim` (registry.OPERATOR_HOLD) means ONE thing: this
    acquisition's operator is not known yet and a claim is open (06_REGISTRIES
    §2.3a-bis). Blank is the other, final, state: unknown.

    In `operator` it is ACCEPTED -- explicitly, not merely because it happens to
    carry no template syntax -- and counted in issues.operator_hold for
    print_report's info line. In any OTHER column it is an ERROR when the WHOLE
    cell, stripped and compared case-insensitively, is the token: the token used
    as a value in `researcher`, `notes`, ... is drift, and a token that means one
    thing only must not be able to drift. A cell that merely MENTIONS it in running
    text ("claimed by Irene 2026-11; was pending-claim") is documentation, not a
    defect, and is not reported.
    """
    hold = registry.OPERATOR_HOLD
    for col, value in row.items():
        # A DictReader row with surplus fields carries a list under the key None.
        if not isinstance(value, str) or not value:
            continue
        if col == "operator":
            if value == hold:
                issues.operator_hold += 1
        elif value.strip().lower() == hold.lower():
            issues.error(
                f"column '{col}' holds the operator hold value {hold!r}, which is "
                f"valid in the 'operator' column only (full value: {value!r})", label,
                cls=f"column '{col}' holds the operator hold value")


def check_subjects_registry(registries_dir, issues):
    """ERROR-level scan of registry_subjects.csv for null project aliases.

    Two ways the same defect shows up: the alias column literally reading
    "None"/"null", and a canonical facility_id whose own alias segment is
    broken. A blank alias on a NON-canonical facility_id is legitimate (the
    DTS24 human subjects have no animal protocol) and is NOT reported.

    A missing table is a WARN, mirroring _load_project_ids — the file need not
    exist on a fresh NAS.
    """
    path = os.path.join(registries_dir, SUBJECTS_REGISTRY)
    header, rows = _read_csv_rows(path)
    if header is None:
        issues.warn(
            f"{SUBJECTS_REGISTRY} not found; subject null-alias checks skipped.")
        return 0

    for i, row in enumerate(rows, start=2):  # +2: header is line 1
        fid = (row.get("facility_id") or "").strip()
        label = fid or f"<{SUBJECTS_REGISTRY} row {i}>"
        alias = (row.get("project_alias") or "").strip()

        bad_in_id = null_alias_of(fid)
        if bad_in_id is not None:
            issues.error(
                f"{SUBJECTS_REGISTRY}: facility_id '{fid}' has a null project "
                f"alias ({bad_in_id!r}) - two different animals can share it",
                label, cls=f"{SUBJECTS_REGISTRY}: facility_id has a null project alias")

        if alias.lower() in ("none", "null"):
            issues.error(
                f"{SUBJECTS_REGISTRY}: project_alias is the literal "
                f"{alias!r}", label,
                cls=f"{SUBJECTS_REGISTRY}: project_alias is the literal None/null")
        elif not alias and is_facility_id(fid):
            # Blank alias is only wrong when the id itself claims to be a
            # facility animal id; blank on LEONE_1.01-style human ids is fine.
            issues.error(
                f"{SUBJECTS_REGISTRY}: project_alias is empty for the "
                f"facility id '{fid}'", label,
                cls=f"{SUBJECTS_REGISTRY}: project_alias is empty for a facility id")

    return len(rows)


# ---- Age sanity (WARN-level) ---------------------------------------------

def _iso_date(value):
    """'YYYY-MM-DD' from an ISO date/datetime string, or '' when it has none."""
    s = (value or "").strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-" and s[:4].isdigit():
        return s[:10]
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return ""


def check_age_sanity(rows, registries_dir, issues):
    """WARN for an acquisition dated BEFORE its subject's date of birth.

    Joins registry_raw.subject_ids (`;`-packed) to registry_subjects.csv by
    facility_id. Only the impossible case is reported: age alone is too weak a
    signal for an "implausible" rule (see the module docstring). Returns the
    number of (acquisition, subject) pairs that could be checked; the report
    shows it as an info line so a silent zero is visible.
    """
    header, subj_rows = _read_csv_rows(os.path.join(registries_dir, SUBJECTS_REGISTRY))
    if header is None:
        return 0
    dob = {}
    for r in subj_rows:
        fid = (r.get("facility_id") or "").strip()
        d = _iso_date(r.get("date_of_birth"))
        if fid and d:
            dob[fid] = d
    checked = 0
    for row in rows:
        acq = (row.get("acq_id") or "").strip()
        acq_date = _iso_date(row.get("acquisition_datetime"))
        if not acq_date:
            continue
        for part in (row.get("subject_ids") or "").split(MULTI_VALUE_SEP):
            sid = part.strip()
            if not sid or sid not in dob:
                continue
            checked += 1
            if acq_date < dob[sid]:
                issues.warn(
                    f"acquired {acq_date}, before subject {sid}'s date of birth "
                    f"{dob[sid]} (a facility-DB entry error, or the wrong animal)",
                    acq or "<row>",
                    cls="acquisition dated before the subject's date of birth")
    return checked


# ---- Unregistered /raw/ folders (WARN-level) ------------------------------

def check_raw_orphans(nas_root, live_ids, tomb_ids, issues):
    """WARN for an ACQ-ID-named folder under /raw/ that no registry row and no
    tombstone accounts for.

    Walks the fixed layout `raw/<ECO>/<YYYY>/<YYYY-MM>/<ACQ-ID>/`
    (03_RAW_STORAGE §3): four directory listings deep, no file reads, so it is
    cheap even over SMB. A folder whose name is not an ACQ-ID is ignored (the
    layout holds nothing else; anything else is a human's doing, outside this
    check). A retired id's surviving folder is check_retired's ERROR, not an
    orphan. Returns the number of acquisition folders seen.
    """
    raw = os.path.join(nas_root, "raw")
    if not os.path.isdir(raw):
        return 0
    seen = 0
    for eco in sorted(os.listdir(raw)):
        eco_dir = os.path.join(raw, eco)
        if not os.path.isdir(eco_dir):
            continue
        for year in sorted(os.listdir(eco_dir)):
            year_dir = os.path.join(eco_dir, year)
            if not os.path.isdir(year_dir):
                continue
            for month in sorted(os.listdir(year_dir)):
                month_dir = os.path.join(year_dir, month)
                if not os.path.isdir(month_dir):
                    continue
                for name in sorted(os.listdir(month_dir)):
                    if not ACQ_ID_RE.match(name):
                        continue
                    if not os.path.isdir(os.path.join(month_dir, name)):
                        continue
                    seen += 1
                    if name in live_ids or name in tomb_ids:
                        continue
                    issues.warn(
                        f"/raw/ folder with no registry row and no tombstone: "
                        f"/raw/{eco}/{year}/{month}/{name}/ (a partial ingest "
                        f"that never committed?)", name,
                        cls="/raw/ folder with no registry row and no tombstone")
    return seen


# ---- Retired-acquisition (tombstone) checks (ERROR-level) ----------------

def check_retired(nas_root, registries_dir, live_ids, issues, live_rows=None):
    """ERROR-level checks of registries/retired_acquisitions.csv against the live registry.

    A no-op when the file does not exist (nothing has ever been retired), so the
    validator's output on a registry without retirements is unchanged.
    ``live_rows`` ({acq_id: row}) enables the `reidentified` consistency check.
    Returns the tombstone map ({acq_id: row}; empty when there is no file) so
    the /raw/ orphan walk can exclude retired ids.
    """
    path = retired.retired_path(registries_dir)
    if not os.path.exists(path):
        return {}
    header, _rows = _read_csv_rows(path)
    if header != retired.RETIRED_FIELDS:
        issues.error(f"{retired.RETIRED_FILENAME} header does not match RETIRED_FIELDS: {header}")
        return {}
    tombs = retired.read_retired(path)
    for acq, t in tombs.items():
        disp = (t.get("disposition") or "").strip()
        if disp not in retired.DISPOSITIONS:
            issues.error(f"retired with an unknown disposition {disp!r} (known: {retired.DISPOSITIONS})", acq,
                         cls="retired with an unknown disposition")
        if (t.get("bytes_fate") or "").strip() not in retired.BYTES_FATES:
            issues.error(f"retired with an unknown bytes_fate {t.get('bytes_fate')!r}", acq,
                         cls="retired with an unknown bytes_fate")
        if acq in live_ids:
            issues.error("is both live (registry_raw.csv) and retired "
                         f"({retired.RETIRED_FILENAME}) -- a retire run stopped mid-commit? "
                         "re-run retire_acquisition.py to finish it", acq,
                         cls="is both live and retired")
        sup = (t.get("superseded_by") or "").strip()
        if sup and sup not in live_ids:
            issues.error(f"retired, superseded_by {sup}, which is not a live acquisition"
                         + (" (it is retired too)" if sup in tombs else ""), acq,
                         cls="retired, superseded_by an acquisition that is not live")
        elif not sup and disp not in retired.NO_SUPERSEDER:
            issues.error(f"retired as {t.get('disposition')!r} with no superseded_by", acq,
                         cls="retired with no superseded_by")
        elif disp == "reidentified" and live_rows is not None and sup in live_rows:
            # A re-identified id's superseded_by is the SAME acquisition under another instrument code.
            old = retired.original_row(t, registry.REGISTRY_FIELDS)
            new = live_rows[sup]
            if old and (old.get("original_name") != new.get("original_name")
                        or old.get("acquisition_datetime") != new.get("acquisition_datetime")
                        or old.get("instrument") == new.get("instrument")):
                issues.error(f"re-identified as {sup}, but {sup} is not this acquisition under another "
                             f"instrument code (original_name / acquisition_datetime / instrument)", acq,
                             cls="re-identified as an acquisition that is not this one")
        old = (t.get("original_canonical_path") or "").strip()
        if old.startswith("/raw/") and os.path.isdir(_acq_folder_on_disk(nas_root, old)):
            issues.error(f"retired, but its /raw/ folder still exists ({old}) -- a retire run "
                         "stopped before deleting it; re-run retire_acquisition.py", acq,
                         cls="retired, but its /raw/ folder still exists")
    if tombs:
        cites = retired.curated_citations(nas_root)
        for acq in sorted(set(cites) & set(tombs)):
            issues.error(f"retired, but cited by curated dataset(s): {'; '.join(cites[acq])}", acq,
                         cls="retired, but cited by a curated dataset")
    return tombs


# ---- Sidecar enrichment check (Phase 3, WARN-level + coverage) -----------

def check_enrichment(acq_id, sample_type, folder, issues):
    """Inspect the acquisition's metadata.json for Phase 3 enrichment blocks.

    All findings here are WARN-level by design: the non-blocking metadata model
    (08_METADATA §4.3-4.7) treats unknown as an explicit, legitimate sentinel
    that must never block ingest — so a missing/placeholder block is a gap to
    chase, not a structural error. The sentinels themselves are COUNTED
    (issues.cover / issues.notes), not warned about: see the module docstring.
    """
    sidecar = os.path.join(folder, "metadata.json")
    if not os.path.isfile(sidecar):
        issues.warn(
            f"sample_type={sample_type} but no metadata.json sidecar at "
            f"{sidecar}", acq_id, cls="no metadata.json sidecar")
        return
    try:
        with open(sidecar, "r", encoding="utf-8") as f:
            md = json.load(f)
    except (OSError, ValueError) as exc:
        issues.warn(f"could not parse sidecar {sidecar}: {exc}", acq_id,
                    cls="could not parse the sidecar")
        return
    # A valid-JSON-but-wrong-shape sidecar (e.g. a hand-edited block that ended
    # up a string/list, or a top-level array) must WARN, never crash the run
    # (non-blocking contract). Guard every .get with an isinstance(dict) check.
    if not isinstance(md, dict):
        issues.warn(f"sidecar {sidecar} is not a JSON object", acq_id,
                    cls="sidecar is not a JSON object")
        return

    subject = md.get("subject")
    condition = md.get("condition")
    anatomy = md.get("anatomy")

    if subject is None:
        issues.warn("sidecar missing subject: block", acq_id)
    elif not isinstance(subject, dict):
        issues.warn("subject: block is not a JSON object", acq_id)
    else:
        # pending-db is a queue with its own drain tool and registry: an info
        # count, not a warning per row.
        issues.cover("subject recovered (not `pending-db`)",
                     subject.get("source") != "pending-db")

    if condition is None:
        issues.warn("sidecar missing condition: block", acq_id)
    elif not isinstance(condition, dict):
        issues.warn("condition: block is not a JSON object", acq_id)
    else:
        issues.cover("condition.is_control known (not null)",
                     condition.get("is_control", "MISSING") is not None)

    if sample_type == "organism":
        if anatomy is None:
            issues.warn("sidecar missing anatomy: block (organism)", acq_id)
        elif not isinstance(anatomy, dict):
            issues.warn("anatomy: block is not a JSON object", acq_id)
        else:
            issues.cover("anatomy.is_whole_body known (not null; organism rows)",
                         anatomy.get("is_whole_body", "MISSING") is not None)


# ---- Main registry walk --------------------------------------------------

def validate(nas_root, check_enrich=True):
    """Run all checks. Returns (Issues, n_rows)."""
    issues = Issues()
    registries_dir = os.path.join(nas_root, "registries")
    registry_path = os.path.join(registries_dir, "registry_raw.csv")

    header, rows = _read_csv_rows(registry_path)
    if header is None:
        issues.error(f"registry_raw.csv not found at {registry_path}")
        return issues, 0

    # 1. Header EXACTLY matches the imported schema.
    if header != registry.REGISTRY_FIELDS:
        issues.error(
            "registry_raw.csv header does not match REGISTRY_FIELDS.\n"
            f"    file has {len(header)} columns: {header}\n"
            f"    schema expects {len(registry.REGISTRY_FIELDS)}: "
            f"{registry.REGISTRY_FIELDS}"
        )
        # Header is the contract for every per-row check below; if it is wrong,
        # column->value alignment is unreliable. Report and stop here.
        return issues, len(rows)

    project_ids = _load_project_ids(registries_dir, issues)

    seen_acq = {}
    for i, row in enumerate(rows, start=2):  # +2: header is line 1
        acq = (row.get("acq_id") or "").strip()
        label = acq or f"<row {i}>"

        # 2. duplicate acq_id
        if acq:
            if acq in seen_acq:
                issues.error(
                    f"duplicate acq_id (first seen on line {seen_acq[acq]})",
                    acq, cls="duplicate acq_id")
            else:
                seen_acq[acq] = i

        # 3. acq_id format
        if acq and not ACQ_ID_RE.match(acq):
            issues.error(
                "acq_id does not match ACQ-YYYYMMDD-<CODE>-NNN", label)

        # 4. required columns non-empty
        for col in REQUIRED_COLUMNS:
            if not (row.get(col) or "").strip():
                issues.error(f"required column '{col}' is empty", label)

        # 5. no unsubstituted template residue in any cell (${...} / {{...}}
        # / <...>) — independent of every other check: it does not need a
        # resolvable folder or a known column, so it still runs when
        # --no-enrichment is set.
        check_template_residue(row, label, issues)

        # 5b. the operator hold value: accepted (and counted) in `operator`, an
        # ERROR as the whole value of any other column. Registry-cell only, like
        # step 5.
        check_operator_hold(row, label, issues)

        # 5c. the `;`-packed cells are well formed (WARN; hygiene).
        check_multivalue_cells(row, label, issues)

        # 6. sample_type controlled vocab (blank allowed)
        sample_type = (row.get("sample_type") or "").strip()
        if sample_type and sample_type not in SAMPLE_TYPE_VOCAB:
            issues.error(
                f"sample_type '{sample_type}' not in controlled vocab "
                f"{sorted(SAMPLE_TYPE_VOCAB)}", label,
                cls="sample_type not in the controlled vocab")

        # 7. canonical_path /raw/-rooted + folder exists on disk
        canonical = (row.get("canonical_path") or "").strip()
        folder = None
        if canonical:
            if not canonical.startswith("/raw/"):
                issues.error(
                    f"canonical_path '{canonical}' does not start with /raw/",
                    label, cls="canonical_path does not start with /raw/")
            else:
                folder = _acq_folder_on_disk(nas_root, canonical)
                if not os.path.isdir(folder):
                    issues.error(
                        f"acquisition folder not found on disk: {folder} "
                        f"(from canonical_path '{canonical}')", label,
                        cls="acquisition folder not found on disk")
                    folder = None  # don't chase a sidecar we can't reach

        # 8. project_id existence (only PROJ-XXXX form, only if we have a set).
        # Since 2026-08-12 no tool writes more than one id (write-once —
        # 06_REGISTRIES §2.3b), but this stays split-based on purpose: a legacy
        # or hand-edited `;` cell is then still checked id-by-id. Testing the
        # whole cell would make PROJ_ID_RE fail on such a value, which SKIPS the
        # existence check rather than failing it — a dangling id would go
        # unreported, which is the silent-failure mode this whole area exists
        # to avoid.
        for proj in proj_id_cell.split_project_ids(row.get("project_id")):
            if PROJ_ID_RE.match(proj) and project_ids is not None:
                if proj not in project_ids:
                    issues.error(
                        f"project_id '{proj}' not found in "
                        f"registry_projects.csv", label,
                        cls="project_id not found in registry_projects.csv")

        # 9. subject_ids null-alias detector (ERROR). Independent of the
        # sidecar walk: it reads the registry cell only, so it still runs when
        # --no-enrichment is set or the acquisition folder is unreachable.
        check_subject_ids(row.get("subject_ids"), label, issues)

        # 10. Phase 3 enrichment (WARN + coverage) — needs a resolvable folder
        if (check_enrich and sample_type in ENRICH_SAMPLE_TYPES
                and folder is not None):
            check_enrichment(acq or label, sample_type, folder, issues)

    # 11. registry_subjects.csv null-alias detector (ERROR).
    check_subjects_registry(registries_dir, issues)

    # 11b. an acquisition dated before its subject's date of birth (WARN).
    checked_pairs = check_age_sanity(rows, registries_dir, issues)
    issues.note(f"age sanity: {checked_pairs} (acquisition, subject) pair(s) "
                f"checked against registry_subjects.csv date_of_birth")

    # 12. the tombstone file (ERROR) -- only when it exists.
    tombs = check_retired(nas_root, registries_dir, set(seen_acq), issues,
                          live_rows={(r.get("acq_id") or "").strip(): r for r in rows})

    # 13. /raw/ folders that nothing accounts for (WARN).
    seen_folders = check_raw_orphans(nas_root, set(seen_acq), set(tombs), issues)
    issues.note(f"/raw/ walk: {seen_folders} acquisition folder(s) seen, "
                f"{len(seen_acq)} live row(s), {len(tombs)} tombstone(s)")

    return issues, len(rows)


# ---- Reporting -----------------------------------------------------------

def _group(findings, classes):
    """[(cls, [(acq, msg), ...])] in first-seen order."""
    grouped = OrderedDict()
    for (acq, msg), cls in zip(findings, classes):
        grouped.setdefault(cls, []).append((acq, msg))
    return list(grouped.items())


def _print_classes(level, findings, classes, examples):
    """One block per finding class: the count, then up to `examples` rows
    (every row when `examples` is None). A class with ONE row prints that
    row alone, as the old per-row report did."""
    for cls, rows in _group(findings, classes):
        if len(rows) == 1:
            acq, msg = rows[0]
            prefix = f"[{acq}] " if acq else ""
            print(f"  {level}: {prefix}{msg}")
            continue
        print(f"  {level}: {cls} -- {len(rows)} row(s)")
        shown = rows if examples is None else rows[:examples]
        for acq, msg in shown:
            prefix = f"[{acq}] " if acq else ""
            print(f"      {prefix}{msg}")
        if examples is not None and len(rows) > examples:
            print(f"      ... and {len(rows) - examples} more "
                  f"(--examples all lists every row)")


def print_report(issues, n_rows, examples=DEFAULT_EXAMPLES):
    """Print summary + findings grouped by class to stdout.

    `examples` is the number of rows shown per class; None shows them all.
    """
    print("=" * 64)
    print("registry validation report")
    print("=" * 64)
    print(f"rows checked: {n_rows}")
    print(f"errors:       {len(issues.errors)}")
    print(f"warnings:     {len(issues.warnings)}")
    # Informational only: not an error, not a warning (06_REGISTRIES §2.3a-bis).
    print(f"operator awaiting claim ({registry.OPERATOR_HOLD}): "
          f"{issues.operator_hold}")
    print()

    if issues.errors:
        print(f"-- ERRORS ({len(issues.errors)}) " + "-" * 40)
        _print_classes("ERROR", issues.errors, issues.error_cls, examples)
        print()

    if issues.warnings:
        print(f"-- WARNINGS ({len(issues.warnings)}) " + "-" * 38)
        _print_classes("WARN", issues.warnings, issues.warn_cls, examples)
        print()

    if issues.coverage:
        print("-- COVERAGE (optional fields; unknown is a documented sentinel, not a defect) " + "-" * 4)
        for label, c in issues.coverage.items():
            total = c["known"] + c["unknown"]
            print(f"  {label}: {c['known']} of {total} ({c['unknown']} unknown)")
        print()

    if issues.notes:
        print("-- INFO " + "-" * 56)
        for msg in issues.notes:
            print(f"  {msg}")
        print()

    if not issues.errors and not issues.warnings:
        print("No issues found.")


# ---- CLI -----------------------------------------------------------------

def _parse_examples(value):
    v = (value or "").strip().lower()
    if v == "all":
        return None
    try:
        n = int(v)
    except ValueError:
        raise argparse.ArgumentTypeError("--examples takes a number or 'all'")
    if n < 0:
        raise argparse.ArgumentTypeError("--examples takes a number >= 0 or 'all'")
    return n


def main(argv=None):
    # Keep accented values (e.g. legacy project descriptions) legible on the
    # Windows console; output is otherwise ASCII.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser(
        description="Read-only validator for the gjesus3 registry area (REG-04)."
    )
    parser.add_argument(
        "--nas-root",
        default=os.environ.get("GJESUS3_ROOT", "/mnt/gjesus3"),
        help="Path to NAS root (default: $GJESUS3_ROOT or /mnt/gjesus3).",
    )
    parser.add_argument(
        "--no-enrichment",
        action="store_true",
        help="Skip the Phase 3 enrichment (sidecar) checks.",
    )
    parser.add_argument(
        "--examples",
        type=_parse_examples,
        default=DEFAULT_EXAMPLES,
        metavar="N|all",
        help=f"Rows shown per finding class (default {DEFAULT_EXAMPLES}; "
             f"'all' lists every row of every class).",
    )
    args = parser.parse_args(argv)

    nas_root = args.nas_root
    log(f"NAS root: {nas_root}")

    # Fail fast if nas_root doesn't look real (mirror ingest_raw.py): without
    # this, os.path.join silently builds a phantom tree and every row "fails".
    registries_dir = os.path.join(nas_root, "registries")
    if not os.path.isdir(nas_root) or not os.path.isdir(registries_dir):
        log(
            f"NAS root does not look valid: '{nas_root}' (expected a "
            f"directory containing a 'registries/' subfolder).", "ERROR")
        log(
            "Pass --nas-root <path> explicitly, or set GJESUS3_ROOT. On "
            "Windows PowerShell: $env:GJESUS3_ROOT = 'J:\\gjesus3-data'.",
            "ERROR")
        return 2

    issues, n_rows = validate(nas_root, check_enrich=not args.no_enrichment)
    print_report(issues, n_rows, examples=args.examples)

    if issues.errors:
        log(f"validation FAILED: {len(issues.errors)} error(s).", "ERROR")
        return 1
    log(f"validation OK: 0 errors, {len(issues.warnings)} warning(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
