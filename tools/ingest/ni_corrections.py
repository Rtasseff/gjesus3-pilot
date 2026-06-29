"""Operator corrections + per-session metadata for the NI live sync (one row per session).

Researchers sometimes enter the wrong project code or mouse id in REMI and can only
fix it on the way OUT (when moving data off the box). They also carry per-session
knowledge — the tracer/compound — that isn't in the acquisition files at all. Both
are handled here, WITHOUT corrupting the sync:

  plan  ->  edit  ->  ingest
  1. `ni-ingest <folder> --live --plan out.csv`  writes ONE ROW PER SESSION
     (the subject-folder source path) for the acquisitions that are NEW this run:
     the read-only `session_path` key + the parsed values + a blank extra-metadata cell.
  2. The operator fixes wrong values and adds `tracer=FDG`-style pairs. They never
     touch `session_path`.
  3. `ni-ingest <folder> --live --corrections out.csv`  applies each session's row.

THE SYNC-SAFETY INVARIANT: corrections change only the METADATA VALUES, never the
identity. The dedup key stays `(acq_date, original_name)` where `original_name` is the
uncorrected REMI path (`<series>/<date>/<subject>/<ts>_<MOD>/recon_<idx>`), so a later
sync still recognises an already-synced acquisition and never re-ingests it. The
SESSION KEY is likewise the RAW `<series>/<date>/<subject>` path (computed before any
override), so a correction binds to the messy on-box location, not to the fixed values.

Correctable fields (v1):
  - project       -> overrides discovered.project  (BEFORE resolution; fixes project_hint
                     routing, the animal-facility DB lookup, and the packed subject_ids)
  - animal_codes  -> overrides discovered.animal_codes (`;`-joined mouse numbers; same)
  - session_id    -> overrides the RESOLVED session_id (the ISA visit grouping)
  - sample_id     -> overrides the RESOLVED sample_id (the subject label)
  - extra_metadata-> free-form `key=value;key=value` -> a `session_extra` sidecar block
                     (the home for tracer/compound — see 08_METADATA)

Persistence is the per-run file (operator passes `--corrections` each sync). KNOWN
LIMITATION: a NEW reconstruction of a previously-corrected session, ingested on a later
run WITHOUT re-passing that session's row, gets the uncorrected values. Mitigation: run
the `--plan` step each sync (it lists what's new) and re-enter that session's fix.
"""

import csv
import os

from . import csv_safe

NI_CORRECTIONS_FILENAME_HINT = "ni_corrections.csv"  # suggested name; operator-chosen

# Columns of the plan/corrections CSV. session_path is the READ-ONLY key.
NI_CORRECTION_FIELDS = [
    "session_path",    # READ-ONLY key: raw <series>/<date>/<subject> source relpath
    "project",         # -> discovered.project (pre-resolution)
    "animal_codes",    # -> discovered.animal_codes (pre-resolution; ;-joined)
    "session_id",      # -> resolved session_id (post-resolution)
    "sample_id",       # -> resolved sample_id (post-resolution)
    "extra_metadata",  # free-form key=value;key=value -> session_extra sidecar block
]

# Fields applied to discovered BEFORE registry resolution (so project_hint /
# subject DB lookup / subject_ids all re-derive from the corrected value).
_PRE_FIELDS = {"project": "project", "animal_codes": "animal_codes"}
# Fields applied to the RESOLVED case AFTER registry resolution.
_POST_FIELDS = {"session_id": "session_id", "sample_id": "sample_id"}


def session_key(discovered):
    """The RAW session identity: `<series>/<date>/<subject>` from path_parse.

    Computed from the uncorrected discovered values (corrections never touch
    series/date/subject), so a correction binds to the messy on-box location.
    Returns None if any component is missing (can't key it).
    """
    parts = [str((discovered or {}).get(k, "")).strip()
             for k in ("series", "date", "subject")]
    if not all(parts):
        return None
    return "/".join(parts)


def parse_extra(raw):
    """`'tracer=FDG; dose=10 MBq'` -> {'tracer': 'FDG', 'dose': '10 MBq'}.

    Splits on ';', each piece on the FIRST '='. Blank/keyless pieces are skipped.
    Returns {} for empty/None input.
    """
    out = {}
    if not raw:
        return out
    for piece in str(raw).split(";"):
        piece = piece.strip()
        if not piece or "=" not in piece:
            continue
        k, _, v = piece.partition("=")
        k = k.strip()
        if k:
            out[k] = v.strip()
    return out


def read_corrections(path):
    """Load a corrections CSV -> {session_path: rowdict}. BOM-tolerant.

    Returns {} if the file doesn't exist. Rows with a blank session_path are
    skipped (can't bind them). A later duplicate session_path wins (last edit).
    """
    if not path or not os.path.isfile(path):
        return {}
    out = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            key = (row.get("session_path") or "").strip()
            if key:
                out[key] = row
    return out


def write_plan(path, rows):
    """Write the plan/corrections CSV (one row per session). Atomic temp+replace.

    `rows` is a list of dicts with at least `session_path`; missing columns are
    written blank. Existing rows the operator already filled are the caller's to
    preserve/merge — this writer just emits what it's given.
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=NI_CORRECTION_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in NI_CORRECTION_FIELDS})
    os.replace(tmp, path)


def assert_header(path):
    """Raise if an existing CSV's header isn't a subset-compatible match.

    The operator may delete columns they don't use, but every present column must
    be a known field (catches a typo'd header before it silently does nothing).
    """
    if not path or not os.path.isfile(path):
        return
    header = csv_safe.read_header(path)
    if not header:
        return
    unknown = [h for h in header if h not in NI_CORRECTION_FIELDS]
    if unknown:
        raise RuntimeError(
            f"{os.path.basename(path)} has unknown column(s) {unknown}; "
            f"known columns are {NI_CORRECTION_FIELDS}. Fix the header."
        )
    if "session_path" not in header:
        raise RuntimeError(
            f"{os.path.basename(path)} is missing the required 'session_path' "
            f"key column."
        )


def apply_pre(case, corrections):
    """Override discovered.{project,animal_codes} from the matching session row.

    Call in expand_batch AFTER subject_parse and BEFORE apply_registry_block, so
    the corrected values flow into project_hint, the subject DB lookup, and the
    packed subject_ids. No-op if `corrections` is empty or this case's session
    isn't in it. Returns the matched row (or None) so the caller can apply_post.
    """
    if not corrections:
        return None
    discovered = case.get("discovered") or {}
    key = session_key(discovered)
    if not key or key not in corrections:
        return None
    row = corrections[key]
    for col, dkey in _PRE_FIELDS.items():
        val = (row.get(col) or "").strip()
        if val:
            discovered[dkey] = val
    case["discovered"] = discovered
    return row


def apply_post(case, row):
    """Override the RESOLVED session_id/sample_id and stash session_extra.

    Call in expand_batch AFTER apply_registry_block, with the row returned by
    apply_pre (so the lookup happens once). No-op if `row` is None.
    """
    if not row:
        return
    for col, ckey in _POST_FIELDS.items():
        val = (row.get(col) or "").strip()
        if val:
            case[ckey] = val
    extra = parse_extra(row.get("extra_metadata"))
    if extra:
        case["session_extra"] = extra
