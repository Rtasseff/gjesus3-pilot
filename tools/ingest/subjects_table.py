"""subjects_table.py — the one-row-per-SUBJECT registry (registry_subjects.csv).

Spec: NI-LIVE-08 · 06_REGISTRIES.md §2.3.2 ·
equipment/nuclear-imaging/live_machine_data_layout_and_sync_rules.md §3C.

This is the static per-animal record that completes the multi-animal data model.
Each acquisition row in ``registry_raw.csv`` carries a packed, ``;``-joined
``subject_ids`` list (1–4 facility ids for an NI scan; a length-1 list for every
other instrument). THIS table holds exactly ONE row per distinct subject, keyed
by that same facility id. The acquisition×subject relationship is recovered by
joining ``subject_ids`` against this table — it is deliberately **not** a
``(acq_id, animal)`` junction/mapping table (that shape was explicitly vetoed;
a query/junction layer is a deferred concern, not built here).

Only STATIC per-animal facts live here (species / strain / sex / date_of_birth /
genotype / cohort + provenance). Per-(scan, animal) facts — ``scan_position`` and
``age_at_acquisition`` — stay in the per-acquisition sidecar ``subjects:[…]``
array, never in this table.

The table is UPDATABLE: an animal seen in N scans is upserted to ONE row, and a
later higher-confidence read (a DB hit after an earlier ``pending-db`` stub, or
an operator correction) fills gaps / upgrades the record without losing good data
(see :func:`_merge`). Writes go through an atomic temp-file replace under the
shared registry lock; the header is BOM-tolerant (``csv_safe``) and a header
mismatch fails loud rather than silently rewriting a differently-shaped file,
mirroring ``registry.append_row``.

When wired into ingest the caller wraps the upsert so a subjects-table failure
can NEVER break an acquisition ingest (same non-blocking rule as enrichment).
"""

import csv
import os
from datetime import datetime, timezone

from . import csv_safe, locking

# animal_db is a top-level tools/ module (like create_project); imported the same
# way enrichment.py does. Used here only for parse_subject_id — NO DB connection.
import animal_db


SUBJECTS_FILENAME = "registry_subjects.csv"

# On-disk schema. A header mismatch fails loud (assert_header_compatible).
# `facility_id` == the subject's `facility_animal_id` == the value(s) packed into
# registry_raw.subject_ids — that string equality IS the join key.
SUBJECT_FIELDS = [
    "facility_id",       # PK — canonical <animal_code>-AE-biomaGUNE-<NNNN>
    "animal_code",       # the leading integer, e.g. "13"
    "project_alias",     # the NNNN animal-protocol alias, e.g. "0525"
    "species",           # binomial, e.g. "Mus musculus"
    "strain",
    "sex",               # M | F | unknown
    "date_of_birth",     # ISO date, or "" when unknown
    "genotype",          # static; usually blank for DB-sourced NI (not in the DB query)
    "cohort_id",         # static grouping; usually blank unless operator-entered
    "source",            # provenance: animal-facility-db | operator-entered | pending-db | unknown
    "first_registered",  # ISO timestamp the row was first written
    "last_updated",      # ISO timestamp the row last changed
]

# Static descriptor fields that participate in the merge (everything except the
# PK, the provenance source label, and the two timestamps).
_VALUE_FIELDS = ["animal_code", "project_alias", "species", "strain", "sex",
                 "date_of_birth", "genotype", "cohort_id"]

# Provenance confidence. A strictly higher-ranked source may overwrite a real
# value; a lower-or-equal source only fills gaps. Equal rank keeps the existing
# value (stable; deliberate corrections are the recovery tool's job, not churn).
_SOURCE_RANK = {
    "animal-facility-db": 3,
    "operator-entered": 2,
    "pending-db": 1,
    "unknown": 0,
    "": 0,
}


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_empty(field, value):
    """True when a field carries no real information.

    sex's documented sentinel is the literal "unknown", so it counts as empty
    for merge purposes — a real "M"/"F" from any source fills over it.
    """
    if value is None:
        return True
    v = str(value).strip()
    if v == "":
        return True
    if field == "sex" and v.lower() == "unknown":
        return True
    return False


def _rank(source):
    return _SOURCE_RANK.get((source or "").strip(), 0)


def subjects_path(registries_dir):
    return os.path.join(registries_dir, SUBJECTS_FILENAME)


def row_from_subject_block(block):
    """Project an enrichment subject block (08_METADATA §4.4) onto a subjects-
    table row dict, or return None when there is no usable subject id.

    Pulls only the STATIC fields; scan_position / age_at_acquisition / weight /
    procedures are per-(scan, animal) and intentionally dropped (they live in
    the sidecar). animal_code / project_alias are recovered from the canonical
    facility id when it parses; a non-canonical id leaves them blank (still a
    valid row, keyed by the id we have).
    """
    if not block:
        return None
    fa = (block.get("facility_animal_id") or "").strip()
    if not fa:
        return None
    alias, code = "", ""
    try:
        alias, code_int = animal_db.parse_subject_id(fa)
        code = str(code_int)
    except Exception:
        pass  # non-canonical id — keep the PK, leave the parsed parts blank
    dob = block.get("date_of_birth")
    return {
        "facility_id": fa,
        "animal_code": code,
        "project_alias": alias,
        "species": block.get("species", "") or "",
        "strain": block.get("strain", "") or "",
        "sex": block.get("sex", "") or "",
        "date_of_birth": "" if dob is None else str(dob),
        "genotype": block.get("genotype", "") or "",
        "cohort_id": block.get("cohort_id", "") or "",
        "source": (block.get("source") or "unknown").strip() or "unknown",
    }


def _new_row(incoming, now):
    """A fresh table row from an incoming dict, with provenance timestamps set."""
    row = {f: "" for f in SUBJECT_FIELDS}
    for f in SUBJECT_FIELDS:
        v = incoming.get(f)
        row[f] = "" if v is None else v
    row["source"] = (incoming.get("source") or "unknown").strip() or "unknown"
    row["first_registered"] = now
    row["last_updated"] = now
    return row


def _merge(existing, incoming, now):
    """Merge an incoming row into an existing one. Returns (row, changed).

    The "never lose good data" invariant:
      - an empty/sentinel incoming value never overwrites anything;
      - an empty/sentinel existing value is filled by any real incoming value;
      - when both are real, a strictly higher-confidence source wins; equal or
        lower confidence keeps the existing value.
    The row's `source` becomes the higher-confidence of the two; first_registered
    is preserved; last_updated is bumped to `now` only when something changed.
    """
    merged = dict(existing)
    changed = False
    in_rank = _rank(incoming.get("source"))
    ex_rank = _rank(existing.get("source"))
    for f in _VALUE_FIELDS:
        nv = incoming.get(f, "")
        if _is_empty(f, nv):
            continue
        ov = merged.get(f, "")
        if _is_empty(f, ov):
            merged[f] = nv
            changed = True
        elif in_rank > ex_rank and str(nv) != str(ov):
            merged[f] = nv
            changed = True
    if in_rank > ex_rank and merged.get("source") != incoming.get("source"):
        merged["source"] = (incoming.get("source") or "").strip() or merged.get("source")
        changed = True
    if changed:
        merged["last_updated"] = now
    return merged, changed


def assert_header_compatible(path):
    """Raise RuntimeError if an existing table's header != SUBJECT_FIELDS.

    No-op when the file is absent (a fresh write creates the correct header).
    BOM-tolerant via csv_safe.read_header so an Excel "Save As CSV UTF-8" BOM
    can't make every rewrite refuse.
    """
    if not os.path.exists(path):
        return
    existing = csv_safe.read_header(path)
    if existing != SUBJECT_FIELDS:
        raise RuntimeError(
            f"registry_subjects header mismatch in {path}\n"
            f"  file has {len(existing)} columns: {existing}\n"
            f"  code expects {len(SUBJECT_FIELDS)}: {SUBJECT_FIELDS}\n"
            f"  refusing to rewrite (would corrupt column alignment)."
        )


def read_subjects(path):
    """Return {facility_id: row} from the table (empty dict when absent).

    Insertion order is preserved (dict order) so rewrites produce stable diffs.
    Tolerant decode (utf-8-sig then latin-1) mirrors registry.read_registry.
    """
    if not os.path.exists(path):
        return {}
    assert_header_compatible(path)
    for enc in ("utf-8-sig", "latin-1"):
        out = {}
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                for r in csv.DictReader(f):
                    fid = (r.get("facility_id") or "").strip()
                    if fid:
                        out[fid] = {k: (r.get(k) or "") for k in SUBJECT_FIELDS}
            return out
        except UnicodeDecodeError:
            continue
    return {}


def write_subjects(path, rows_by_id):
    """Atomically (re)write the whole table from {facility_id: row}.

    Temp-file + os.replace so a crash mid-write can't leave a half-written table
    over SMB; a full rewrite also sidesteps the BOM-append / torn-line hazards
    that csv_safe guards for append-mode writers. The CALLER must hold the
    registry lock (write is read-modify-write — see upsert_subjects).
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if os.path.exists(path):
        assert_header_compatible(path)
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SUBJECT_FIELDS, extrasaction="ignore")
        w.writeheader()
        for fid in rows_by_id:
            w.writerow({k: rows_by_id[fid].get(k, "") for k in SUBJECT_FIELDS})
    os.replace(tmp, path)


def upsert_subjects(registries_dir, rows, now=None, log=None, _hold_lock=True):
    """Upsert subject rows into registry_subjects.csv (insert-or-merge by id).

    Handles one row (single-animal ingest), 1–4 (a multi-animal NI scan), or
    thousands (the historical back-fill) in a single read-modify-write. `now` is
    an ISO string (injected for testability + so a whole batch shares one
    timestamp); defaults to the current UTC time.

    Acquires the shared registry lock unless ``_hold_lock=False`` — set that
    only when the caller already holds it (e.g. ingest_raw Step 10), because the
    lock is not reentrant and re-acquiring would deadlock.

    The file is only (re)written when something actually changed, so a re-run is
    a true no-op (idempotency rule R7). Returns {inserted, updated, unchanged}.
    """
    log = log or (lambda m, level="INFO": None)
    now = now or _now_iso()
    path = subjects_path(registries_dir)

    def _do():
        table = read_subjects(path)
        stats = {"inserted": 0, "updated": 0, "unchanged": 0}
        for incoming in rows:
            fid = (incoming.get("facility_id") or "").strip()
            if not fid:
                continue
            if fid not in table:
                table[fid] = _new_row(incoming, now)
                stats["inserted"] += 1
            else:
                table[fid], changed = _merge(table[fid], incoming, now)
                stats["updated" if changed else "unchanged"] += 1
        if stats["inserted"] or stats["updated"]:
            write_subjects(path, table)
        return stats

    if _hold_lock:
        with locking.registry_lock(registries_dir):
            stats = _do()
    else:
        stats = _do()
    log(f"subjects table: {stats['inserted']} inserted, {stats['updated']} "
        f"updated, {stats['unchanged']} unchanged ({path})")
    return stats
