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
    project_hint `ae-biomegune-<NNNN>` → `projects.projectAlias = <NNNN>`
    → `projects.id` → `animals.id_project`; the instrument animal short code
    (`m13`/`m14`/`ID13B`) → `animals.animal_code` (the leading integer).
    (project, animal_code) is the unique animal key. The subject id is the
    facility canonical `<animal_code>-AE-biomaGUNE-<NNNN>` (reused verbatim).

Usage:
    # Live lookup (prints the normalized subject block as JSON):
    python tools/animal_db.py 0525 13
    python tools/animal_db.py --id 13-AE-biomaGUNE-0525

    # Connectivity check (SELECT 1, touches no data):
    python tools/animal_db.py --check

    # Self-test against the known animal (0525, 13):
    python tools/animal_db.py --self-test

Programmatic:
    from animal_db import lookup
    res = lookup("0525", 13)
    if res.status == "found":
        subject_block = res.subject      # ready for the sidecar
    else:
        # res.reason in {"db-miss", "no-credentials"} → pending list
        ...
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

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
# Keyed by (project_alias_lower, animal_code_int). Only successful and
# confirmed-absent lookups are cached; "unreachable" results are not (retry).
_CACHE = {}


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
             None when found, "db-miss" when not_found, "no-credentials"
             when unreachable (covers missing creds, missing driver, auth
             failure, or network outage; precise cause is in `detail`).
    detail:  human-readable explanation for logging.
    """
    status: str
    subject: dict = None
    reason: str = None
    detail: str = ""


# ---- Normalization helpers ----------------------------------------------

def normalize_species(value):
    """DB common name ("Mouse"/"Rat") → scientific binomial. Passthrough unknown."""
    return _SPECIES_MAP.get((value or "").strip().lower(), value)


def normalize_sex(value):
    """DB "Male"/"Female" → "M"/"F". Anything else → "unknown"."""
    return _SEX_MAP.get((value or "").strip().lower(), "unknown")


def compose_subject_id(animal_code, project_alias):
    """Build the canonical subject id `<animal_code>-AE-biomaGUNE-<NNNN>`."""
    return f"{int(animal_code)}-{PROJECT_CODE_STEM}-{project_alias}"


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


# ---- Core lookup ---------------------------------------------------------

def _query_subject(conn, project_alias, animal_code):
    """Run the SELECTs against an open connection. Returns subject dict or None.

    None means the (project, animal) pair was not found.
    """
    with conn.cursor() as cur:
        # Resolve the project: prefer exact projectAlias, fall back to project_code.
        cur.execute(
            "SELECT id, project_code, projectAlias FROM projects WHERE projectAlias = %s LIMIT 1",
            (project_alias,),
        )
        proj = cur.fetchone()
        if not proj:
            cur.execute(
                "SELECT id, project_code, projectAlias FROM projects "
                "WHERE project_code LIKE %s LIMIT 1",
                (f"%{project_alias}",),
            )
            proj = cur.fetchone()
        if not proj:
            return None

        # Resolve the animal within that project.
        cur.execute(
            "SELECT a.id, a.animal_code, a.sex, a.date_of_birth, a.weight, "
            "       s.type AS specie_type, st.type AS strain_type, "
            "       st.aka AS strain_aka, st.tg AS strain_tg "
            "FROM animals a "
            "JOIN specie s  ON s.id  = a.id_specie "
            "JOIN strain st ON st.id = a.id_strain "
            "WHERE a.id_project = %s AND a.animal_code = %s LIMIT 1",
            (proj["id"], int(animal_code)),
        )
        animal = cur.fetchone()
        if not animal:
            return None

        # Procedures: structured controlled vocab (NOT free text), with dates.
        cur.execute(
            "SELECT p.type AS type, ap.date AS date "
            "FROM animal_procedures ap "
            "JOIN procedures p ON p.id = ap.id_procedure "
            "WHERE ap.id_animal = %s ORDER BY ap.date, p.type",
            (animal["id"],),
        )
        procedures = [
            {"type": r["type"], "date": _iso(r["date"])} for r in cur.fetchall()
        ]

    return {
        "facility_animal_id": compose_subject_id(animal["animal_code"], proj["projectAlias"]),
        "species": normalize_species(animal["specie_type"]),
        "strain": animal["strain_type"],
        "sex": normalize_sex(animal["sex"]),
        "date_of_birth": _iso(animal["date_of_birth"]),
        # age_at_acquisition is derived by the Phase 3 writer (needs acq datetime).
        "procedures": procedures,
        "source": "animal-facility-db",
    }


def lookup(project_alias, animal_code, conn=None, use_cache=True):
    """Look up one animal → LookupResult.

    Args:
        project_alias: the 4-char animal-protocol alias (e.g. "0525"), i.e.
            the NNNN from project_hint "ae-biomegune-NNNN".
        animal_code: the integer animal code (the leading number of the
            instrument short code; "m13" → 13).
        conn: optional open connection to reuse across a batch; if None, one
            is opened and closed per call.
        use_cache: memoize found/not_found results in-process.

    Never raises on DB problems — returns status="unreachable" instead, so a
    caller can WARN-and-defer rather than fail the ingest.
    """
    try:
        animal_code = int(str(animal_code).strip())
    except (TypeError, ValueError):
        return LookupResult("not_found", reason="db-miss",
                            detail=f"animal_code not an integer: {animal_code!r}")

    key = (str(project_alias).strip().lower(), animal_code)
    if use_cache and key in _CACHE:
        return _CACHE[key]

    own_conn = conn is None
    try:
        if own_conn:
            conn = get_connection()
    except RuntimeError as e:
        # Missing driver or creds file → can't reach the DB at all.
        return LookupResult("unreachable", reason="no-credentials", detail=str(e))
    except Exception as e:  # pymysql connection/auth/network errors
        return LookupResult("unreachable", reason="no-credentials",
                            detail=f"connection failed: {e}")

    try:
        subject = _query_subject(conn, str(project_alias).strip(), animal_code)
    except Exception as e:
        return LookupResult("unreachable", reason="no-credentials",
                            detail=f"query failed: {e}")
    finally:
        if own_conn:
            try:
                conn.close()
            except Exception:
                pass

    if subject is None:
        res = LookupResult("not_found", reason="db-miss",
                          detail=f"no animal {animal_code} in project {project_alias}")
    else:
        res = LookupResult("found", subject=subject,
                          detail=subject["facility_animal_id"])
    if use_cache:
        _CACHE[key] = res
    return res


def lookup_by_subject_id(subject_id, conn=None, use_cache=True):
    """Look up by the composite `<animal_code>-AE-biomaGUNE-<NNNN>` subject id."""
    try:
        alias, code = parse_subject_id(subject_id)
    except ValueError as e:
        return LookupResult("not_found", reason="db-miss", detail=str(e))
    return lookup(alias, code, conn=conn, use_cache=use_cache)


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
    """Live lookup of the known animal (0525, 13) with value assertions."""
    clear_cache()
    res = lookup("0525", 13)
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
                   help="live lookup of the known (0525, 13) with assertions")
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

    if args.subject_id:
        res = lookup_by_subject_id(args.subject_id)
    elif args.project_alias and args.animal_code:
        res = lookup(args.project_alias, args.animal_code)
    else:
        p.error("provide PROJECT_ALIAS ANIMAL_CODE, or --id, or --check/--self-test")

    if res.status == "found":
        json.dump(res.subject, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0
    log(f"{res.status} (reason={res.reason}): {res.detail}", "WARN")
    return 1 if res.status == "not_found" else 4


if __name__ == "__main__":
    sys.exit(main())
