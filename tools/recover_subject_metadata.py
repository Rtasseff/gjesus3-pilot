#!/usr/bin/env python3
"""recover_subject_metadata.py — superuser deferred-recovery for subject metadata.

When a live ingest can't reach the animal-facility DB (DB lags the acquisition,
or the operator machine has no credentials), the acquisition still lands in
/raw/ with a placeholder `subject:` block (source="pending-db") and a row is
queued in `registries/pending_subject_metadata.csv` (08_METADATA §4.4.6). This
tool is run later, from a superuser machine that DOES hold ~/.my.cnf, to walk
that pending list, re-attempt the DB lookup, and — for hits — fill the real
subject fields into the immutable /raw sidecar IN PLACE.

WHAT IT DOES (per pending row with status=="pending")
    1. parse facility_animal_id -> (project_alias, animal_code)  [animal_db]
    2. animal_db.lookup(alias, code)
    3. if FOUND: open the /raw sidecar at row["sidecar_path"], fill ONLY blank/
       placeholder subject required fields (species/strain/sex/date_of_birth/
       procedures), set source="animal-facility-db", recompute
       age_at_acquisition from date_of_birth + the acquisition datetime found
       in the sidecar (user_supplied / ecosystem section / discovered / the
       ACQ-ID date prefix; leave "" if none), VERIFY-after-write by re-reading,
       then flip the pending row to status="recovered" + recovered_at=now(UTC).
    4. if not_found / unreachable: leave the row pending (never auto-mark
       "unresolvable" — that is a human judgement call).

SAFEGUARDS (mirror the project close-out controlled-write pattern)
    * DRY-RUN by default — reports what WOULD change and touches NOTHING.
      Writing requires an explicit --apply flag.
    * NEVER overwrite a subject field already populated with a real (non-
      placeholder) value — only blanks / sentinels are filled.
    * VERIFY-AFTER-WRITE: the sidecar is re-read from disk and the filled
      fields are confirmed before the pending row is marked recovered. If the
      verify fails, the row stays pending and the sidecar write is rolled back.
    * IDEMPOTENT: rows already status=="recovered" are skipped; re-running
      --apply after a successful recovery is a no-op.

Usage:
    # Preview (default; touches nothing):
    python tools/recover_subject_metadata.py --nas-root J:\\gjesus3-data
    python tools/recover_subject_metadata.py            # uses $GJESUS3_ROOT

    # Apply (writes sidecars + flips pending rows):
    python tools/recover_subject_metadata.py --nas-root J:\\gjesus3-data --apply

Run from a superuser machine (holds ~/.my.cnf, on-network/VPN). READ-ONLY
against the DB; controlled-write against /raw sidecars + the pending list only.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

# tools/ on sys.path so `from ingest import ...` and `import animal_db` work
# whether this is run from the repo root or from tools/ (mirrors the other CLIs).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ingest import pending  # noqa: E402
import animal_db  # noqa: E402


# Subject required fields we fill on a DB hit (08_METADATA §4.4). age is
# derived, not copied; source is set explicitly. facility_animal_id is the join
# key and already present in the placeholder, so it is not in this fill set.
SUBJECT_FILL_FIELDS = [
    "species", "strain", "sex", "date_of_birth", "procedures",
]

# Values that count as "blank / placeholder" for the corresponding field — a
# field holding one of these is safe to overwrite; anything else is a real
# operator/DB value and is left untouched (controlled-write safeguard).
_PLACEHOLDER_SENTINELS = {
    "species": ("", None),
    "strain": ("", None),
    "sex": ("", None, "unknown"),
    "date_of_birth": ("", None),
    "procedures": ("", None, []),
}

# Where an acquisition datetime might live inside a sidecar, in priority order.
# Each entry is a (section, key) path; section "" means the top level. We take
# the first non-empty hit. Matches the fields surfaced by the ecosystem
# extractors (paravision_metadata / czi_metadata / ni_metadata) + discovered.
_ACQ_DT_DISCOVERED_KEYS = [
    "acquisition_datetime",
    "mri_acquisition_datetime",
    "ni_acquisition_datetime",
    "czi_acquisition_datetime",
    "mri_study_datetime",
    "acquisition_date",
]


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {level}: {msg}", file=sys.stderr)


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_placeholder(field, value):
    """True if `value` for `field` is a blank/sentinel that may be overwritten."""
    sentinels = _PLACEHOLDER_SENTINELS.get(field, ("", None))
    if isinstance(value, str):
        return value.strip() in [s for s in sentinels if isinstance(s, str)] \
            or value.strip() == ""
    return value in [s for s in sentinels if not isinstance(s, str)]


def _date_from_acq_id(acq_id):
    """The YYYYMMDD prefix of an ACQ-YYYYMMDD-... id -> ISO date, else ''."""
    parts = (acq_id or "").split("-")
    if len(parts) >= 2 and len(parts[1]) == 8 and parts[1].isdigit():
        d = parts[1]
        return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    return ""


def find_acquisition_datetime(sidecar):
    """Best-effort acquisition datetime/date for age derivation.

    Search order (first non-empty wins):
      1. user_supplied.acquisition_datetime
      2. any ecosystem section's study/acquisition datetime
         (mri.study_datetime, mri.acquisition.creation_datetime,
          microscopy.*.acquisition_datetime, dicom.study_date, etc.)
      3. discovered.<known acq-datetime keys>
      4. the ACQ-ID YYYYMMDD prefix
    Returns a string (ISO-ish or YYYYMMDD) or "" when nothing is found. The
    downstream animal_db.age_iso8601 only needs the leading date, so partial /
    mixed forms are fine.
    """
    # 1. user_supplied
    us = sidecar.get("user_supplied") or {}
    if us.get("acquisition_datetime"):
        return str(us["acquisition_datetime"])

    # 2. ecosystem section (top-level keys other than the known fixed ones).
    fixed = {"acq_id", "generated", "generator", "user_supplied",
             "discovered", "subject", "condition", "anatomy"}
    for key, block in sidecar.items():
        if key in fixed or not isinstance(block, dict):
            continue
        # Common ecosystem datetime fields, in rough priority order.
        for path in (("study_datetime",), ("acquisition", "creation_datetime"),
                     ("study_date",), ("acquisition_datetime",)):
            cur = block
            ok = True
            for p in path:
                if isinstance(cur, dict) and cur.get(p):
                    cur = cur[p]
                else:
                    ok = False
                    break
            if ok and cur:
                return str(cur)
        # microscopy nests per-image; scan one level for an *_datetime.
        for v in block.values():
            if isinstance(v, dict) and v.get("acquisition_datetime"):
                return str(v["acquisition_datetime"])

    # 3. discovered
    disco = sidecar.get("discovered") or {}
    for k in _ACQ_DT_DISCOVERED_KEYS:
        if disco.get(k):
            return str(disco[k])

    # 4. ACQ-ID date prefix
    return _date_from_acq_id(sidecar.get("acq_id", ""))


def plan_subject_fill(subject, db_subject, acq_for_age):
    """Compute the fields that WOULD be written into `subject` from a DB hit.

    Pure: returns (updates: dict, skipped: list[(field, existing_value)]).
    Only blank/placeholder required fields are proposed for fill; populated
    real values are reported as skipped (controlled-write safeguard).
    age_at_acquisition is derived from the (filled-or-existing) date_of_birth.
    source is always proposed (placeholder -> animal-facility-db).
    """
    updates = {}
    skipped = []

    for field in SUBJECT_FILL_FIELDS:
        new_val = db_subject.get(field)
        if new_val is None:
            continue  # DB had nothing for this field; leave the sentinel as-is.
        existing = subject.get(field)
        if _is_placeholder(field, existing):
            if existing != new_val:
                updates[field] = new_val
        else:
            if existing != new_val:
                skipped.append((field, existing))

    # source: only flip to the authoritative DB source when we actually wrote a
    # DB-supplied data field, OR the existing source is itself a placeholder.
    # Otherwise a sidecar whose real subject was operator-entered (and KEPT
    # above as a skipped field) would get a false "animal-facility-db"
    # provenance even though its values disagree with the DB.
    existing_source = subject.get("source")
    wrote_db_field = any(f in updates for f in SUBJECT_FILL_FIELDS)
    if existing_source != "animal-facility-db" and (
        wrote_db_field or existing_source in ("", "pending-db", "unknown", None)
    ):
        updates["source"] = "animal-facility-db"

    # age_at_acquisition: derive if currently blank and we have a DOB + acq date.
    dob = updates.get("date_of_birth", subject.get("date_of_birth"))
    if not (subject.get("age_at_acquisition") or "").strip() and dob and acq_for_age:
        age = animal_db.age_iso8601(dob, acq_for_age)
        if age:
            updates["age_at_acquisition"] = age

    return updates, skipped


def _read_sidecar(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_sidecar(path, sidecar):
    """Write the sidecar back, preserving the 2-space indent + trailing \\n."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sidecar, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _verify_after_write(path, updates):
    """Re-read the sidecar from disk; confirm every update landed. Returns
    (ok: bool, detail: str)."""
    try:
        fresh = _read_sidecar(path)
    except Exception as e:
        return False, f"could not re-read sidecar: {e}"
    subj = fresh.get("subject") or {}
    for field, val in updates.items():
        if subj.get(field) != val:
            return False, f"field {field!r} = {subj.get(field)!r}, expected {val!r}"
    return True, "all fields confirmed"


def recover_one(row, *, apply, lookup_fn, log=log):
    """Process a single pending row. Pure w.r.t. the pending list (returns a
    status dict; the caller mutates + persists the list).

    Returns a dict:
        {
          "acq_id", "facility_animal_id",
          "outcome": "recovered" | "would-recover" | "still-pending"
                     | "already-recovered" | "skipped-status" | "error",
          "updates": {...},      # fields that were / would be written
          "skipped": [...],      # populated fields left untouched
          "detail": "...",       # human note
        }
    The pending row is only ever flipped to "recovered" by the caller when
    outcome == "recovered" (i.e. apply=True AND a verified write).
    """
    acq_id = row.get("acq_id", "")
    fa_id = row.get("facility_animal_id", "")
    sidecar_path = row.get("sidecar_path", "")
    status = (row.get("status") or "").strip().lower()
    result = {"acq_id": acq_id, "facility_animal_id": fa_id,
              "outcome": "", "updates": {}, "skipped": [], "detail": ""}

    if status == "recovered":
        result["outcome"] = "already-recovered"
        result["detail"] = "row already recovered; skipping (idempotent)"
        return result
    if status != "pending":
        result["outcome"] = "skipped-status"
        result["detail"] = f"status={status!r} (not 'pending'); skipping"
        return result

    # Parse the facility animal id into the DB join key.
    try:
        alias, code = animal_db.parse_subject_id(fa_id)
    except ValueError as e:
        result["outcome"] = "still-pending"
        result["detail"] = f"unparseable facility_animal_id: {e}"
        return result

    res = lookup_fn(alias, code)
    if res.status != "found":
        result["outcome"] = "still-pending"
        result["detail"] = (f"DB {res.status} (reason={res.reason}): "
                            f"{res.detail} — left pending")
        return result

    # Load the /raw sidecar.
    if not sidecar_path or not os.path.isfile(sidecar_path):
        result["outcome"] = "error"
        result["detail"] = f"sidecar not found at {sidecar_path!r}"
        return result
    try:
        sidecar = _read_sidecar(sidecar_path)
    except Exception as e:
        result["outcome"] = "error"
        result["detail"] = f"could not read sidecar: {e}"
        return result

    subject = sidecar.get("subject")
    if not isinstance(subject, dict):
        result["outcome"] = "error"
        result["detail"] = "sidecar has no subject block to fill"
        return result

    acq_for_age = find_acquisition_datetime(sidecar)
    updates, skipped = plan_subject_fill(subject, res.subject, acq_for_age)
    result["updates"] = updates
    result["skipped"] = skipped

    if not updates:
        # Nothing to do — already complete (e.g. recovered out-of-band). Treat
        # as idempotent already-recovered so the caller can flip the stale row.
        result["outcome"] = "already-recovered" if apply else "would-recover"
        result["detail"] = "subject already fully populated; nothing to write"
        return result

    if not apply:
        result["outcome"] = "would-recover"
        result["detail"] = (f"would fill {sorted(updates)} "
                            f"(acq_date_for_age={acq_for_age or 'none'})")
        return result

    # --- controlled write ---
    backup = dict(subject)  # shallow snapshot for rollback on verify failure.
    for field, val in updates.items():
        subject[field] = val
    try:
        _write_sidecar(sidecar_path, sidecar)
    except Exception as e:
        result["outcome"] = "error"
        result["detail"] = f"write failed: {e}"
        return result

    ok, vdetail = _verify_after_write(sidecar_path, updates)
    if not ok:
        # Roll back the in-file change and leave the row pending.
        sidecar["subject"] = backup
        try:
            _write_sidecar(sidecar_path, sidecar)
        except Exception:
            pass
        result["outcome"] = "error"
        result["detail"] = f"verify-after-write FAILED ({vdetail}); rolled back"
        return result

    result["outcome"] = "recovered"
    result["detail"] = f"filled {sorted(updates)}; verify OK"
    return result


def recover_all(registries_dir, *, apply=False, lookup_fn=None, log=log):
    """Walk the pending list and recover what we can.

    Args:
        registries_dir: the NAS registries/ directory holding the pending list.
        apply: write changes (default False = dry-run, touches nothing).
        lookup_fn: injectable animal lookup (defaults to animal_db.lookup);
            takes (project_alias, animal_code) -> LookupResult.

    Returns a summary dict with per-row results + counts.
    """
    if lookup_fn is None:
        lookup_fn = animal_db.lookup

    path = pending.pending_path(registries_dir)
    rows = pending.read_pending(path)
    results = []
    any_recovered = False

    for row in rows:
        try:
            r = recover_one(row, apply=apply, lookup_fn=lookup_fn, log=log)
        except Exception as e:
            # Defense-in-depth: a single unexpected row error must never abort
            # the whole walk — that would leave sidecars already written this
            # run desynced from the pending list (which is persisted at the
            # end). Record it as an error row and continue.
            r = {"acq_id": row.get("acq_id", ""),
                 "facility_animal_id": row.get("facility_animal_id", ""),
                 "outcome": "error", "updates": {}, "skipped": [],
                 "detail": f"unexpected error: {e}"}
        results.append(r)

        # Per-row reporting.
        tag = r["outcome"].upper()
        log(f"[{tag}] {r['acq_id'] or '(no acq_id)'} "
            f"({r['facility_animal_id'] or 'no id'}): {r['detail']}")
        for field, existing in r["skipped"]:
            log(f"    SKIP field {field!r}: keeping existing real value "
                f"{existing!r} (controlled-write: never overwrite).", "WARN")

        if r["outcome"] in ("recovered", "already-recovered") and apply:
            # Flip the in-memory row; persisted once at the end.
            if (row.get("status") or "").lower() != "recovered":
                row["status"] = "recovered"
                row["recovered_at"] = _now_iso()
                any_recovered = True

    if apply and any_recovered:
        pending._assert_header(path)
        pending._write_all(path, rows)
        log(f"pending list updated: {path}")

    counts = {}
    for r in results:
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1

    return {"path": path, "results": results, "counts": counts,
            "total": len(rows), "applied": apply}


def _print_summary(summary):
    c = summary["counts"]
    mode = "APPLY" if summary["applied"] else "DRY-RUN"
    log("---- summary ----")
    log(f"mode:               {mode}")
    log(f"pending list:       {summary['path']}")
    log(f"rows examined:      {summary['total']}")
    for outcome in ("recovered", "would-recover", "still-pending",
                    "already-recovered", "skipped-status", "error"):
        if c.get(outcome):
            log(f"  {outcome:<18} {c[outcome]}")
    if not summary["applied"] and c.get("would-recover"):
        log("re-run with --apply to write these changes.")


def main(argv=None):
    p = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="DRY-RUN by default. Run from a superuser machine (holds "
               "~/.my.cnf, on-network/VPN). READ-ONLY against the DB.",
    )
    p.add_argument(
        "--nas-root",
        default=os.environ.get("GJESUS3_ROOT", "/mnt/gjesus3"),
        help="Path to NAS root (default: $GJESUS3_ROOT or /mnt/gjesus3). "
             "Must contain a 'registries/' subfolder.",
    )
    p.add_argument(
        "--apply",
        action="store_true",
        help="Write changes. Without this flag the tool is a no-op preview.",
    )
    args = p.parse_args(argv)

    # Keep accented procedure / strain names legible on the Windows console;
    # sidecars are always written UTF-8.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    nas_root = args.nas_root
    log(f"NAS root: {nas_root}")

    # Fail fast if nas_root doesn't look like a real NAS root (mirror
    # ingest_raw.py): without this, a bad path silently yields an empty walk.
    registries_dir = os.path.join(nas_root, "registries")
    if not os.path.isdir(nas_root) or not os.path.isdir(registries_dir):
        log(f"NAS root does not look valid: '{nas_root}' (expected a directory "
            f"containing a 'registries/' subfolder).", "ERROR")
        log("Pass --nas-root <path> explicitly, or set GJESUS3_ROOT. On Windows "
            "PowerShell: $env:GJESUS3_ROOT = 'J:\\gjesus3-data'.", "ERROR")
        return 2

    if not args.apply:
        log("*** DRY-RUN MODE — no changes will be made (use --apply to write) ***")

    summary = recover_all(registries_dir, apply=args.apply)
    _print_summary(summary)

    # Non-zero exit only on hard errors (sidecar missing / verify failure),
    # so an operator can spot a real problem in a wrapper script. Still-pending
    # rows (DB miss / unreachable) are normal and exit 0.
    return 1 if summary["counts"].get("error") else 0


if __name__ == "__main__":
    sys.exit(main())
