#!/usr/bin/env python3
"""animal_db.py — Read-only fetcher for the animal-facility database.

Looks up an animal in CIC biomaGUNE's animal-facility colony-management
DB and returns a normalized `subject:` block ready for the metadata.json
sidecar (see mfb-rdm-docs/08_METADATA.md §4.4 + the Subject/Sample
identity model in 06_REGISTRIES §2.3).

WHAT IT CONNECTS TO
    MariaDB 5.5 `animal_facility` schema on intranet.cicbiomagune.es:3306
    (the same server as the `publications` DB). READ-ONLY (`SELECT` only) —
    this is a shared production database; never write to it.

WHERE IT RUNS / CREDENTIALS
    Runs on Windows alongside the rest of the ingest pipeline — single OS, no
    WSL split (pymysql is pure Python and installs fine on Windows; the DB is
    a network resource reachable from Windows). Credentials live ONLY in
    `~/.my.cnf` — on Windows that is `C:\\Users\\<you>\\.my.cnf`; keep it in the
    local user profile, NOT in OneDrive or this repo (it's protected by the
    profile's NTFS ACLs). Never put the password in the repo, env vars, or
    logs. On-network / VPN only. Override the path with GJESUS3_MYCNF.

    Whether a machine can auto-populate depends on whether IT HAS CREDS, not
    on the OS: the Data-Mgmt-Lead / superuser machines hold `~/.my.cnf`; a
    generic operator machine may not. With no creds (or off-network),
    `lookup()` returns status="unreachable" and the ingest pipeline (Phase 3)
    WARNs, writes a placeholder subject block, and queues the acquisition for
    a superuser to recover later (deferred-recovery, 08_METADATA §4.4.6).

THE JOIN (verified 2026-06-02)
    project name `AE-biomaGUNE-<NNNN>` → `projects.projectAlias = <NNNN>`
    → `projects.id` → `animals.id_project`; the instrument animal short code
    (`m13`/`m14`/`ID13B`) → `animals.animal_code` (the leading integer).
    The subject id is the facility canonical `<animal_code>-AE-biomaGUNE-<NNNN>`
    (reused verbatim).

(PROJECT, CODE) CAN MATCH MORE THAN ONE DB RECORD (verified 2026-10-19)
    The DB's only true key is `animals.id`. A facility animal ID is unique by
    law and is NEVER reused (Ryan, 2026-10-22). When an animal changes protocol
    the DB moves its row to the new (project, code) and keeps the old pair in
    `old_project` / `old_project_animal_code` / `project_change_date`; the DB
    can also hold a LATER record that carries, as its current code, the same
    (project, code) the earlier animal had before it moved (201 times since
    2018, never while the first one held it). That is a DB record or data-entry
    issue for the facility to explain. So the lookup asks: which animal HELD
    (project, code) on the acquisition date? Candidates are the current record
    (from its entry, or from its own change date when it moved in) and every
    earlier animal that moved out (from its entry to its change date). Exactly
    one must fit, else the lookup refuses (reason `db-date-conflict`). It also refuses
    an acquisition dated before the animal's birth: a label error no join can
    fix. The chosen animal's `animals.id` is returned as `facility_db_id`.

Usage:
    # Live lookup (prints the normalized subject block as JSON):
    python tools/animal_db.py 0525 13 --date 2026-01-15
    python tools/animal_db.py --id 13-AE-biomaGUNE-0525 --date 2026-01-15
    python tools/animal_db.py 1123 15 --date 2024-08-26 --ex-vivo

    # Connectivity check (SELECT 1, touches no data):
    python tools/animal_db.py --check

    # Self-test against the known animal (0525, 13):
    python tools/animal_db.py --self-test

Programmatic:
    from animal_db import lookup
    res = lookup("0525", 13, on_date="2026-01-15", in_vivo=True)
    if res.status == "found":
        subject_block = res.subject      # ready for the sidecar
    else:
        # res.reason in {"db-miss", "db-date-conflict", "no-credentials"}
        # → pending list
        ...

    # Bulk (an audit over every registry link): load the tables once.
    idx = HolderIndex.from_connection(get_connection())
    res = lookup("0525", 49, on_date="2026-05-21", index=idx)
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

try:
    import pymysql
    import pymysql.cursors
    HAS_PYMYSQL = True
except ImportError:
    HAS_PYMYSQL = False


# ---- Configuration -------------------------------------------------------

# Username is also present in ~/.my.cnf; passed explicitly per the proven
# connection pattern from the access handoff. NOT a secret (the password
# exists only in ~/.my.cnf). Override via env var for portability.
DB_USER = os.environ.get("GJESUS3_ANIMALDB_USER", "rtasseff")
DATABASE = "animal_facility"
CNF_PATH = os.environ.get("GJESUS3_MYCNF") or os.path.join(os.path.expanduser("~"), ".my.cnf")
CONNECT_TIMEOUT = 8

# The institute's animal-protocol code stem; the facility's project_code is
# "AE-biomaGUNE-<NNNN>" and the canonical subject id is "<code>-AE-biomaGUNE-<NNNN>".
PROJECT_CODE_STEM = "AE-biomaGUNE"
SUBJECT_ID_RE = re.compile(r"^(?P<animal_code>\d+)-AE-biomaGUNE-(?P<alias>\w+)$", re.IGNORECASE)

# DB value normalization (verified DB values → our controlled forms).
_SPECIES_MAP = {"mouse": "Mus musculus", "rat": "Rattus norvegicus"}
_SEX_MAP = {"male": "M", "female": "F"}

# In-process cache so a batch ingest doesn't re-query the same animal.
# Keyed by (project_alias_lower, animal_code_int, date, in_vivo). Only
# successful and confirmed-absent lookups are cached; "unreachable" results
# are not (retry).
_CACHE = {}

# Pending-list reasons (08_METADATA §4.4.6.2).
REASON_MISS = "db-miss"                    # no animal ever held (project, code)
REASON_DATE_CONFLICT = "db-date-conflict"  # animals held it, but none fits the date
REASON_NO_CREDS = "no-credentials"         # the DB could not be reached

# Tolerance on a holder's entry / change dates, in days. A scan logged the day
# before the DB's entry date, or the day after a move, still fits; an exact fit
# is always preferred over a tolerant one (choose_holder). The 2026-10-19
# registry-wide check used the same tolerance.
DATE_TOLERANCE_DAYS = 1


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {level}: {msg}", file=sys.stderr)


# ---- Result type ---------------------------------------------------------

@dataclass
class LookupResult:
    """Outcome of an animal lookup.

    status: "found" | "not_found" | "unreachable"
    subject: the normalized subject block (dict) when found, else None.
    reason:  pending-list reason for the caller (08_METADATA §4.4.6) —
             None when found; when not_found, "db-miss" (no animal ever held
             the code) or "db-date-conflict" (animals held it, but none fits
             the date, or the date precedes the animal's birth);
             "no-credentials" when unreachable (covers missing creds, missing
             driver, auth failure, or network outage; precise cause is in
             `detail`).
    detail:  human-readable explanation for logging.
    holder:  when found, which animal answered: {"facility_db_id", "kind"
             ("current" | "moved-out"), "start", "end", "current_facility_id"
             (the animal's id today; differs from the queried id after a
             transfer)}.
    warnings: soft signals on a found record, e.g. "after-exit" (an in-vivo
             scan dated after the animal's DB exit) or "tissue-before-exit"
             (a tissue specimen dated while the animal was still alive).
    """
    status: str
    subject: dict = None
    reason: str = None
    detail: str = ""
    holder: dict = None
    warnings: list = field(default_factory=list)


# ---- Normalization helpers ----------------------------------------------

def normalize_species(value):
    """DB common name ("Mouse"/"Rat") → scientific binomial. Passthrough unknown."""
    return _SPECIES_MAP.get((value or "").strip().lower(), value)


def normalize_sex(value):
    """DB "Male"/"Female" → "M"/"F". Anything else → "unknown"."""
    return _SEX_MAP.get((value or "").strip().lower(), "unknown")


def compose_subject_id(animal_code, project_alias):
    """Build the canonical subject id `<animal_code>-AE-biomaGUNE-<NNNN>`.

    Raises ValueError when the alias is missing or the literal string "None" /
    "null". Refusing is the point: a null alias formats as the plausible-looking
    `<n>-AE-biomaGUNE-None`, which is not merely ugly but AMBIGUOUS — every
    null-alias protocol collapses onto the same id, and the subjects-table
    upsert then merges two different animals into one row (444 acquisition rows
    reached production that way before this guard existed).
    """
    # ASCII only in the message: it is logged by ingest_raw, whose stdout is a
    # raw (often cp1252) Windows console — an em dash there would raise
    # UnicodeEncodeError and break the very ingest this guard protects.
    if project_alias is None or str(project_alias).strip().lower() in ("", "none", "null"):
        raise ValueError(
            f"refusing to compose a subject id with a null project alias "
            f"(animal {animal_code!r}) - see tasks/BACKLOG.md "
            f"'Facility-DB null project alias'"
        )
    return f"{int(animal_code)}-{PROJECT_CODE_STEM}-{str(project_alias).strip()}"


def parse_subject_id(subject_id):
    """Split `<animal_code>-AE-biomaGUNE-<NNNN>` → (project_alias, animal_code:int).

    Raises ValueError if the string isn't in canonical form.
    """
    m = SUBJECT_ID_RE.match((subject_id or "").strip())
    if not m:
        raise ValueError(
            f"Not a canonical subject id '<code>-AE-biomaGUNE-<NNNN>': {subject_id!r}"
        )
    return m.group("alias"), int(m.group("animal_code"))


def _iso(d):
    """date/datetime → ISO date string ('YYYY-MM-DD'); None → None."""
    if d is None:
        return None
    if isinstance(d, (date, datetime)):
        return d.isoformat()[:10]
    return str(d)


def as_day(x):
    """A date from a DB value or an acquisition date string, else None.

    Accepts date / datetime, 'YYYY-MM-DD...' (ISO date or datetime, any
    suffix), and 'YYYYMMDD' (the ACQ-ID prefix). MySQL zero dates
    ('0000-00-00', which pymysql returns as a string) and anything unparseable
    are None: an unknown date, never an error."""
    if x is None:
        return None
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    s = str(x).strip()
    if len(s) >= 10 and s[4] == "-":
        s = s[:10]
    elif len(s) == 8 and s.isdigit():
        s = f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def acq_id_day(acq_id):
    """The acquisition day of an `ACQ-YYYYMMDD-...` id, else None. In the
    registry this always equals the date of `acquisition_datetime` (checked
    over every subject-bearing row on 2026-10-20), so it is the scan date the
    lookup uses."""
    parts = (acq_id or "").split("-")
    return as_day(parts[1]) if len(parts) >= 2 else None


def age_iso8601(dob, acquisition):
    """ISO-8601 duration from date_of_birth to acquisition (writer helper).

    Phase 2's lookup returns date_of_birth only; the sidecar writer (Phase 3)
    derives `age_at_acquisition`. This helper is shared so both sides agree.

    Returns e.g. "P12W" for an exact multiple of 7 days, else "P85D". None if
    inputs are missing or acquisition precedes birth.
    """
    def _as_date(x):
        if x is None:
            return None
        if isinstance(x, datetime):
            return x.date()
        if isinstance(x, date):
            return x
        # Tolerate non-ISO / vendor-decorated strings (e.g. Bruker
        # "<2025-09-15T14:30:00,500+0200>", "2025/10/29") — return None rather
        # than raise, so callers (the Phase 3 writer + recovery tool) honour
        # the non-blocking contract and leave age_at_acquisition blank instead
        # of crashing the ingest/walk.
        try:
            return datetime.fromisoformat(str(x)[:19]).date()
        except ValueError:
            return None

    d0, d1 = _as_date(dob), _as_date(acquisition)
    if d0 is None or d1 is None:
        return None
    days = (d1 - d0).days
    if days < 0:
        return None
    weeks, rem = divmod(days, 7)
    return f"P{weeks}W" if weeks and rem == 0 else f"P{days}D"


# ---- Connection ----------------------------------------------------------

def get_connection(connect_timeout=CONNECT_TIMEOUT):
    """Open a READ-ONLY connection to `animal_facility` using ~/.my.cnf.

    Raises RuntimeError if pymysql is missing or ~/.my.cnf is absent, and
    propagates pymysql errors (caller wraps and fails soft).
    """
    if not HAS_PYMYSQL:
        raise RuntimeError("pymysql not installed (pip install 'pymysql>=1.1')")
    if not os.path.isfile(CNF_PATH):
        raise RuntimeError(f"credentials file not found: {CNF_PATH}")
    return pymysql.connect(
        read_default_file=CNF_PATH,
        user=DB_USER,
        database=DATABASE,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=connect_timeout,
    )


def credentials_available():
    """True if a DB lookup can even be ATTEMPTED — pymysql present AND a
    credentials file at CNF_PATH (env `GJESUS3_MYCNF`, else `~/.my.cnf`).

    When False, every DB-sourced subject is written as `source: "pending-db"`
    for later recovery. Useful as a one-time pre-flight check so an operator
    notices BEFORE a large batch run — especially in WSL, where `~/.my.cnf`
    resolves to the WSL home and `GJESUS3_MYCNF` is often unset.
    """
    return HAS_PYMYSQL and os.path.isfile(CNF_PATH)


# ---- Holders: which animal held (project, code) when --------------------

def _alias_of_project(proj):
    """A project row's alias: `projectAlias`, else the NNNN of an
    `AE-biomaGUNE-NNNN...` project_code (0219 / 0618 / 0619 / 1521 have a NULL
    alias), else ""."""
    alias = str(proj.get("projectAlias") or "").strip()
    code = str(proj.get("project_code") or "").strip()
    if not alias and code.startswith(PROJECT_CODE_STEM + "-"):
        alias = re.split(r"[-/]", code[len(PROJECT_CODE_STEM) + 1:], 1)[0].strip()
    return alias


def _old_code(row):
    """`old_project_animal_code` (a varchar) as an int, or None when it is not
    a plain number."""
    s = str(row.get("old_project_animal_code") or "").strip()
    return int(s) if s.isdigit() else None


def build_holders(rows, project_id, animal_code):
    """Every animal that has held (project_id, animal_code), with its tenure.

    `rows` are animal rows (dicts with id, id_project, animal_code,
    date_of_entry, old_project, old_project_animal_code, project_change_date,
    ...); rows that are not holders are ignored, so a caller may pass a superset.

      current   the row now carrying (project, code). It has held the code
                since its entry, or since its own change date when it moved
                in. Its tenure is open: nobody can hold the code after it
                without it moving out first.
      moved-out a row whose OLD pair is (project, code). It held the code from
                its entry until its change date. When the DB lost that date (a
                zero date), the tenure ends when the next holder began, else it
                stays open.

    Returns a list of {"row", "kind", "start", "end"} with dates as `date`
    (None when unknown).
    """
    holders, seen = [], set()
    for r in rows:
        if r.get("id") in seen:
            continue
        moved_in = bool(r.get("old_project"))
        if r.get("id_project") == project_id and int(r.get("animal_code")) == animal_code:
            start = (as_day(r.get("project_change_date")) if moved_in else None) \
                or as_day(r.get("date_of_entry"))
            holders.append({"row": r, "kind": "current", "start": start, "end": None})
            seen.add(r.get("id"))
        elif moved_in and r.get("old_project") == project_id and _old_code(r) == animal_code:
            holders.append({"row": r, "kind": "moved-out",
                            "start": as_day(r.get("date_of_entry")),
                            "end": as_day(r.get("project_change_date"))})
            seen.add(r.get("id"))
    for h in holders:
        if h["kind"] == "moved-out" and h["end"] is None and h["start"] is not None:
            later = [o["start"] for o in holders
                     if o is not h and o["start"] is not None and o["start"] > h["start"]]
            if later:
                h["end"] = min(later)
    return holders


def _describe(h):
    r = h["row"]
    return (f"id {r.get('id')} ({h['kind']}, {_iso(h['start']) or '?'}.."
            f"{_iso(h['end']) or ('now' if h['kind'] == 'current' else '?')}, "
            f"born {_iso(as_day(r.get('date_of_birth'))) or '?'})")


def choose_holder(holders, on_date, in_vivo=True, tolerance_days=DATE_TOLERANCE_DAYS):
    """Pick the one animal that held the code on `on_date`. Pure.

    Returns (holder, reason, detail): holder is one of `holders` or None; reason
    is None on success, else REASON_MISS (no holder ever) or
    REASON_DATE_CONFLICT (holders exist, but none fits, several fit, or the date
    precedes the chosen animal's birth).

    Fit: the date is on/after the holder's start. In vivo it must also be
    on/before the end of a closed tenure (a moved-out holder's change date);
    a tissue specimen is often prepared after the animal left, so for ex vivo
    only the start counts. An exact fit is tried first, then a fit within
    `tolerance_days`; each pass must yield exactly one holder.

    Without a date the code must have had a single holder ever: a date-blind
    answer is how a pre-move scan got the code's later DB record.
    """
    if not holders:
        return None, REASON_MISS, "no holder"
    d = as_day(on_date)
    if d is None:
        if len(holders) == 1:
            chosen = holders[0]
        else:
            return None, REASON_DATE_CONFLICT, (
                f"{len(holders)} animals have held this code "
                f"({'; '.join(_describe(h) for h in holders)}); "
                f"the acquisition date is needed to choose")
    else:
        def fits(h, tol):
            if h["start"] is None or d < h["start"] - tol:
                return False
            if in_vivo and h["end"] is not None and d > h["end"] + tol:
                return False
            return True

        chosen = None
        for tol in (0, tolerance_days):
            fit = [h for h in holders if fits(h, timedelta(days=tol))]
            if len(fit) > 1:
                return None, REASON_DATE_CONFLICT, (
                    f"{len(fit)} animals fit {d.isoformat()}: "
                    f"{'; '.join(_describe(h) for h in fit)}")
            if fit:
                chosen = fit[0]
                break
        if chosen is None:
            return None, REASON_DATE_CONFLICT, (
                f"no animal held the code on {d.isoformat()} "
                f"({'in vivo' if in_vivo else 'ex vivo'}); holders: "
                f"{'; '.join(_describe(h) for h in holders)}")
        dob = as_day(chosen["row"].get("date_of_birth"))
        if dob is not None and d < dob:
            return None, REASON_DATE_CONFLICT, (
                f"acquisition {d.isoformat()} precedes the birth of the animal "
                f"that held the code: {_describe(chosen)}")
    return chosen, None, _describe(chosen)


def holder_warnings(holder, on_date, in_vivo=True, tolerance_days=DATE_TOLERANCE_DAYS):
    """Soft signals on an accepted holder (never a refusal):
    "after-exit"          in vivo, dated after the animal's DB exit;
    "tissue-before-exit"  ex vivo, dated while the animal was still alive
                          (a specimen normally comes at the exit; a biopsy is
                          the exception, so this is a flag, not a refusal)."""
    d = as_day(on_date)
    exit_day = as_day(holder["row"].get("turn_date"))
    if d is None or exit_day is None:
        return []
    if in_vivo and d > exit_day + timedelta(days=tolerance_days):
        return ["after-exit"]
    if not in_vivo and d < exit_day:
        return ["tissue-before-exit"]
    return []


# ---- Data sources: live SQL per lookup, or everything loaded once ---------

_ANIMAL_COLUMNS = (
    "a.id, a.id_project, a.animal_code, a.sex, a.date_of_birth, a.date_of_entry, "
    "a.turn_date, a.id_turn, a.old_project, a.old_project_animal_code, "
    "a.project_change_date, s.type AS specie_type, st.type AS strain_type")
_ANIMAL_FROM = ("FROM animals a "
                "JOIN specie s  ON s.id  = a.id_specie "
                "JOIN strain st ON st.id = a.id_strain ")


class _SqlSource:
    """Per-lookup SELECTs on an open connection (the ingest and recovery path)."""

    def __init__(self, conn):
        self.conn = conn

    def project(self, alias):
        with self.conn.cursor() as cur:
            # Resolve the project: prefer exact projectAlias, fall back to project_code.
            cur.execute(
                "SELECT id, project_code, projectAlias FROM projects WHERE projectAlias = %s LIMIT 1",
                (alias,),
            )
            proj = cur.fetchone()
            if not proj:
                # ANCHORED on the AE-biomaGUNE- segment. The old form was
                # `LIKE '%<alias>'`, which matches any project_code ENDING in those
                # digits: a lookup for protocol 101 resolved to project 1317 via
                # `AE-biomaGUNE-1317/PRO-AE-SS-101`, and then returned THAT project's
                # animal — wrong species/strain/sex/DOB/procedures, reported as a
                # success. Wrong data with no error is the DTS24 failure shape.
                # The fallback itself is still needed: 0219 and 1521 have a NULL
                # projectAlias and resolve only through project_code.
                like = f"AE-biomaGUNE-{alias}"
                cur.execute(
                    "SELECT id, project_code, projectAlias FROM projects "
                    "WHERE project_code = %s OR project_code LIKE %s "
                    "   OR project_code LIKE %s LIMIT 1",
                    (like, like + "-%", like + "/%"),
                )
                proj = cur.fetchone()
        return proj

    def project_by_id(self, project_id):
        with self.conn.cursor() as cur:
            cur.execute("SELECT id, project_code, projectAlias FROM projects WHERE id = %s",
                        (project_id,))
            return cur.fetchone()

    def holder_rows(self, project_id, animal_code):
        # The current holder, plus every animal that moved OUT of this project
        # (build_holders keeps those whose old code matches: the column is a
        # varchar, so the number is compared in Python, not in SQL).
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT {_ANIMAL_COLUMNS} {_ANIMAL_FROM}"
                "WHERE (a.id_project = %s AND a.animal_code = %s) OR a.old_project = %s",
                (project_id, int(animal_code), project_id),
            )
            return list(cur.fetchall())

    def procedures(self, animal_id):
        # Procedures: structured controlled vocab (NOT free text), with dates.
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT p.type AS type, ap.date AS date "
                "FROM animal_procedures ap "
                "JOIN procedures p ON p.id = ap.id_procedure "
                "WHERE ap.id_animal = %s ORDER BY ap.date, p.type",
                (animal_id,),
            )
            return [{"type": r["type"], "date": _iso(r["date"])} for r in cur.fetchall()]


class HolderIndex:
    """Every project and animal, read once, for bulk read-only work (an audit or
    a back-fill over tens of thousands of links). The same resolution rules as
    the live path; procedures are NOT loaded, so a subject built from an index
    has no `procedures` key."""

    def __init__(self, projects, animals):
        self.projects = list(projects)
        self._by_id = {p["id"]: p for p in self.projects}
        self._current = {}
        self._moved_out = {}
        for a in animals:
            self._current.setdefault((a["id_project"], int(a["animal_code"])), []).append(a)
            if a.get("old_project"):
                self._moved_out.setdefault(a["old_project"], []).append(a)

    @classmethod
    def from_connection(cls, conn):
        with conn.cursor() as cur:
            cur.execute("SELECT id, project_code, projectAlias FROM projects")
            projects = list(cur.fetchall())
            cur.execute(f"SELECT {_ANIMAL_COLUMNS} {_ANIMAL_FROM}")
            animals = list(cur.fetchall())
        return cls(projects, animals)

    def project(self, alias):
        # As _SqlSource.project: an exact alias first, then the anchored
        # project_code. MariaDB compares case-insensitively and ignores
        # trailing spaces; so does this.
        a = str(alias).strip().lower()
        for p in sorted(self.projects, key=lambda p: p["id"]):
            if str(p.get("projectAlias") or "").strip().lower() == a:
                return p
        stem = f"ae-biomagune-{a}"
        for p in sorted(self.projects, key=lambda p: p["id"]):
            code = str(p.get("project_code") or "").strip().lower()
            if code == stem or code.startswith(stem + "-") or code.startswith(stem + "/"):
                return p
        return None

    def project_by_id(self, project_id):
        return self._by_id.get(project_id)

    def holder_rows(self, project_id, animal_code):
        return (self._current.get((project_id, int(animal_code)), [])
                + self._moved_out.get(project_id, []))

    def procedures(self, animal_id):
        return None


def _resolve(source, project_alias, animal_code, on_date, in_vivo):
    """The lookup proper, over either source. Returns a LookupResult."""
    proj = source.project(project_alias)
    if not proj:
        return LookupResult("not_found", reason=REASON_MISS,
                            detail=f"no animal {animal_code} in project {project_alias}")
    holders = build_holders(source.holder_rows(proj["id"], animal_code), proj["id"], animal_code)
    chosen, reason, why = choose_holder(holders, on_date, in_vivo)
    if chosen is None:
        if reason == REASON_MISS:
            why = f"no animal {animal_code} in project {project_alias}"
        else:
            why = f"{animal_code} in project {project_alias}: {why}"
        return LookupResult("not_found", reason=reason, detail=why)

    row = chosen["row"]
    # The project may have resolved through project_code, whose projectAlias
    # is NULL for some protocols (0219 / 0618 / 0619 / 1521). Composing the
    # identity from that field yields "<n>-AE-biomaGUNE-None", which is not
    # just ugly — it is AMBIGUOUS, because every null-alias protocol collapses
    # onto the same id and the subjects-table upsert then merges two different
    # animals into one row. Fall back to the alias the caller asked for.
    alias = str(proj["projectAlias"] or "").strip() or str(project_alias).strip()
    subject = {
        # The id the acquisition was labelled with (the code on that date),
        # and the DB's own key for the animal that held it.
        "facility_animal_id": compose_subject_id(animal_code, alias),
        "facility_db_id": int(row["id"]),
        "species": normalize_species(row["specie_type"]),
        "strain": row["strain_type"],
        "sex": normalize_sex(row["sex"]),
        "date_of_birth": _iso(as_day(row["date_of_birth"])),
        # age_at_acquisition is derived by the Phase 3 writer (needs acq datetime).
        "source": "animal-facility-db",
    }
    procedures = source.procedures(row["id"])
    if procedures is not None:
        subject["procedures"] = procedures
        # Keep the documented field order (procedures before source).
        subject["source"] = subject.pop("source")

    current_id = subject["facility_animal_id"]
    if chosen["kind"] != "current":
        cur_proj = source.project_by_id(row["id_project"]) or {}
        try:
            current_id = compose_subject_id(row["animal_code"], _alias_of_project(cur_proj))
        except ValueError:
            current_id = ""
    holder = {"facility_db_id": int(row["id"]), "kind": chosen["kind"],
              "start": _iso(chosen["start"]), "end": _iso(chosen["end"]),
              "current_facility_id": current_id}
    return LookupResult("found", subject=subject, detail=f"{subject['facility_animal_id']}: {why}",
                        holder=holder, warnings=holder_warnings(chosen, on_date, in_vivo))


# ---- Core lookup ---------------------------------------------------------

def lookup(project_alias, animal_code, conn=None, use_cache=True,
           on_date=None, in_vivo=True, index=None):
    """Look up the animal that held (project, code) on `on_date` → LookupResult.

    Args:
        project_alias: the 4-char animal-protocol alias (e.g. "0525"), i.e.
            the NNNN from the project name "AE-biomaGUNE-NNNN".
        animal_code: the integer animal code (the leading number of the
            instrument short code; "m13" → 13).
        conn: optional open connection to reuse across a batch; if None, one
            is opened and closed per call.
        use_cache: memoize found/not_found results in-process.
        on_date: the acquisition date (date, ISO string, or YYYYMMDD). Without
            it the lookup answers only when the code has had ONE holder ever.
        in_vivo: True for a living-animal scan (the date must fall inside the
            holder's tenure), False for a tissue specimen (on/after its start).
        index: a HolderIndex to answer from instead of the live DB (bulk,
            read-only work; no procedures).

    Never raises on DB problems — returns status="unreachable" instead, so a
    caller can WARN-and-defer rather than fail the ingest.
    """
    try:
        animal_code = int(str(animal_code).strip())
    except (TypeError, ValueError):
        return LookupResult("not_found", reason=REASON_MISS,
                            detail=f"animal_code not an integer: {animal_code!r}")
    alias = str(project_alias).strip()
    day = as_day(on_date)
    in_vivo = bool(in_vivo)

    if index is not None:
        return _resolve(index, alias, animal_code, day, in_vivo)

    key = (alias.lower(), animal_code, day, in_vivo)
    if use_cache and key in _CACHE:
        return _CACHE[key]

    own_conn = conn is None
    try:
        if own_conn:
            conn = get_connection()
    except RuntimeError as e:
        # Missing driver or creds file → can't reach the DB at all.
        return LookupResult("unreachable", reason=REASON_NO_CREDS, detail=str(e))
    except Exception as e:  # pymysql connection/auth/network errors
        return LookupResult("unreachable", reason=REASON_NO_CREDS,
                            detail=f"connection failed: {e}")

    try:
        res = _resolve(_SqlSource(conn), alias, animal_code, day, in_vivo)
    except Exception as e:
        return LookupResult("unreachable", reason=REASON_NO_CREDS,
                            detail=f"query failed: {e}")
    finally:
        if own_conn:
            try:
                conn.close()
            except Exception:
                pass

    if use_cache:
        _CACHE[key] = res
    return res


def lookup_by_subject_id(subject_id, conn=None, use_cache=True,
                         on_date=None, in_vivo=True, index=None):
    """Look up by the composite `<animal_code>-AE-biomaGUNE-<NNNN>` subject id."""
    try:
        alias, code = parse_subject_id(subject_id)
    except ValueError as e:
        return LookupResult("not_found", reason=REASON_MISS, detail=str(e))
    return lookup(alias, code, conn=conn, use_cache=use_cache,
                  on_date=on_date, in_vivo=in_vivo, index=index)


def clear_cache():
    """Drop the in-process lookup cache (e.g. between test runs)."""
    _CACHE.clear()


# ---- CLI -----------------------------------------------------------------

def _cmd_check():
    """SELECT 1 connectivity check; touches no data."""
    try:
        conn = get_connection()
    except Exception as e:
        log(f"cannot connect: {e}", "ERROR")
        return 2
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT VERSION() AS v, CURRENT_USER() AS u, DATABASE() AS d")
            row = cur.fetchone()
        log(f"OK - server {row['v']}, user {row['u']}, db {row['d']}")
        return 0
    finally:
        conn.close()


def _cmd_self_test():
    """Live lookups with value assertions: the known animal (0525, 13), and a
    transferred code read on two dates (0525 #49: before the 2026-05-21 move it
    was DB id 18522, now 1025 #1; a later record, DB id 19759, entered
    2026-09-10, also carries 0525 #49)."""
    clear_cache()
    res = lookup("0525", 13, on_date="2025-10-27")
    if res.status == "unreachable":
        log(f"SKIP (DB unreachable): {res.detail}", "WARN")
        return 3
    if res.status != "found":
        log(f"FAIL: expected to find (0525, 13); got {res.status} ({res.detail})", "ERROR")
        return 1
    expected = {
        "facility_animal_id": "13-AE-biomaGUNE-0525",
        "species": "Mus musculus",
        "sex": "M",
        "date_of_birth": "2025-07-31",
    }
    bad = {k: (res.subject.get(k), v) for k, v in expected.items() if res.subject.get(k) != v}
    if bad:
        log(f"FAIL: mismatches {bad}", "ERROR")
        return 1
    if not isinstance(res.subject.get("procedures"), list):
        log("FAIL: procedures is not a structured list", "ERROR")
        return 1
    log(f"PASS - {res.subject['facility_animal_id']}: {res.subject['species']}, "
        f"{res.subject['strain']}, {res.subject['sex']}, DOB {res.subject['date_of_birth']}, "
        f"{len(res.subject['procedures'])} procedure(s)")
    for day, want_id, want_now in (("2026-05-21", 18522, "1-AE-biomaGUNE-1025"),
                                   ("2026-09-12", 19759, "49-AE-biomaGUNE-0525")):
        r = lookup("0525", 49, on_date=day)
        got = ((r.subject or {}).get("facility_db_id"), (r.holder or {}).get("current_facility_id"))
        if got != (want_id, want_now):
            log(f"FAIL: (0525, 49) on {day}: expected {(want_id, want_now)}, got {got} "
                f"({r.status}: {r.detail})", "ERROR")
            return 1
        log(f"PASS - (0525, 49) on {day} -> DB id {want_id}, now {want_now}")
    return 0


def main():
    p = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="READ-ONLY. Credentials live only in ~/.my.cnf. Runs from WSL "
               "(where creds + pymysql live); on-network/VPN only.",
    )
    p.add_argument("project_alias", nargs="?",
                   help="animal-protocol alias NNNN (e.g. 0525)")
    p.add_argument("animal_code", nargs="?",
                   help="integer animal code (e.g. 13)")
    p.add_argument("--id", dest="subject_id",
                   help="look up by composite subject id (13-AE-biomaGUNE-0525)")
    p.add_argument("--check", action="store_true",
                   help="connectivity check (SELECT 1), no data touched")
    p.add_argument("--self-test", action="store_true",
                   help="live lookups of known animals with assertions")
    p.add_argument("--date", help="acquisition date YYYY-MM-DD: the animal that held "
                                  "the code that day (needed once a code has had "
                                  "more than one animal)")
    p.add_argument("--ex-vivo", action="store_true",
                   help="a tissue specimen (only the holder's start date counts)")
    args = p.parse_args()

    # DB values can carry accents (e.g. Spanish procedure names); keep them
    # legible on the Windows console. The sidecar file is always written UTF-8.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    if not HAS_PYMYSQL:
        log("pymysql not installed. In WSL: pip install 'pymysql>=1.1'", "ERROR")
        return 2

    if args.check:
        return _cmd_check()
    if args.self_test:
        return _cmd_self_test()

    kw = {"on_date": args.date, "in_vivo": not args.ex_vivo}
    if args.subject_id:
        res = lookup_by_subject_id(args.subject_id, **kw)
    elif args.project_alias and args.animal_code:
        res = lookup(args.project_alias, args.animal_code, **kw)
    else:
        p.error("provide PROJECT_ALIAS ANIMAL_CODE, or --id, or --check/--self-test")

    if res.status == "found":
        json.dump(res.subject, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        log(f"holder: {res.holder}" + (f"; warnings: {res.warnings}" if res.warnings else ""))
        return 0
    log(f"{res.status} (reason={res.reason}): {res.detail}", "WARN")
    return 1 if res.status == "not_found" else 4


if __name__ == "__main__":
    sys.exit(main())
