"""Operator corrections + per-session metadata for the NI live sync (one row per session).

Researchers sometimes enter the wrong project code or mouse id in REMI and can only
fix it on the way OUT (when moving data off the box). They also carry per-session
knowledge — the tracer/compound — that isn't in the acquisition files at all. Both
are handled here, WITHOUT corrupting the sync.

ONE FILE, OWNED BY THE OPERATOR, KEPT FOREVER (2026-08-07). There is exactly one
corrections CSV per researcher — `ni_corrections_<researcher>.csv`, living on the
shared `gnuclear` NAS beside the code (`resolve_path` below). Three rules, no others:

  1. `ni-ingest <folder> --live --plan` APPENDS a row for every session it has never
     seen, and touches nothing already in the file. Read-only otherwise.
  2. The operator edits the file in place — fixes wrong values, adds `tracer=FDG`-style
     pairs. They never touch `session_path` (the read-only key).
  3. Every `--live` run reads that same file and applies it.

This replaces the earlier two-file design (a throwaway per-run worksheet merged into a
separate NAS-side store). The merge was the ONLY reason there had to be a rule about
what a blank cell means — "I didn't touch this" vs "clear the stored value" — and that
rule was needless complexity. With one file a blank cell just means an empty cell: no
override for that column. No merge, no store-vs-worksheet distinction, nothing to
re-enter, and a correction made once applies to reconstructions that arrive months
later (NI recon indices are append-only, so late recons land in existing sessions).

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
  - extra_metadata-> free-form `key=value;key=value` -> a `session_extra` sidecar block
                     (the home for tracer/compound — see 08_METADATA)

NOT correctable, deliberately (dropped 2026-08-06): `session_id` and `sample_id` are
DERIVED for NI — `session_id` from `<series>_<date>_<subject>` and `sample_id` from
`<project>_<subject-folder>`, i.e. entirely from the two fields above. Offering them as
editable columns made them a second, competing source of truth: they were written blank
into every plan, and a project correction (0324->0325) re-derived `project_hint` but left
a hand-set `sample_id` reading `0324_m61` — stale and wrong. Correct `project` /
`animal_codes` and both re-derive correctly. Fewer columns, fewer questions.

Correctable fields are deliberately few — see NI_CORRECTION_FIELDS.
"""

import csv
import os
import re

from . import csv_safe

# Columns of the plan/corrections CSV. session_path is the READ-ONLY key.
NI_CORRECTION_FIELDS = [
    "session_path",    # READ-ONLY key: raw <series>/<date>/<subject> source relpath
    "project",         # -> discovered.project (pre-resolution)
    "animal_codes",    # -> discovered.animal_codes (pre-resolution; ;-joined)
    "extra_metadata",  # free-form key=value;key=value -> session_extra sidecar block
]

# Fields applied to discovered BEFORE registry resolution (so project_hint /
# subject DB lookup / subject_ids all re-derive from the corrected value).
_PRE_FIELDS = {"project": "project", "animal_codes": "animal_codes"}
# No post-resolution value overrides: session_id / sample_id are DERIVED from the
# pre-resolution fields above (see the module docstring). apply_post now carries
# only the session_extra sidecar block.
_POST_FIELDS = {}


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


def append_new_rows(path, rows):
    """Append a row for each session_path NOT already in the file. Returns the count.

    The append-only half of the one-file model: an existing row is never
    rewritten, reordered or re-read-and-dumped, because that row is the
    operator's own edit and this tool has no business touching it. Creates the
    file (with a header) when it doesn't exist yet.

    Uses the file's OWN header order, not NI_CORRECTION_FIELDS — `assert_header`
    lets the operator delete columns they don't use, so honouring what is
    actually on disk is what keeps that promise. Goes through `csv_safe` for the
    two Excel hazards: a BOM on the header (read side) and a missing final
    newline that would otherwise concatenate the first appended row onto the
    operator's last one.
    """
    seen = set(read_corrections(path))
    new = []
    for r in (rows or []):
        key = (r.get("session_path") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        new.append(r)
    if not new:
        return 0

    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    header = csv_safe.read_header(path) or list(NI_CORRECTION_FIELDS)
    write_header = not os.path.exists(path) or os.path.getsize(path) == 0
    csv_safe.ensure_trailing_newline(path)
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        if write_header:
            w.writeheader()
        for r in new:
            w.writerow({k: (r.get(k) or "") for k in header})
    return len(new)


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


# --------------------------------------------------- where the file lives (gnuclear)
#
# The corrections file is NOT on gjesus3. The errors it records are the NI Mac's
# local reality — messy hand-typed folder names on that box — and the code that
# reads it runs from the shared `gnuclear` NAS, so it belongs there too. Keeping
# it off the Mac's local disk also matters for the platform-manager audit story:
# everything we leave behind sits in one visible place on a share he already owns.

FILENAME_PREFIX = "ni_corrections_"

# gnuclear's layout is <root>/<YYYY>/<group>/<user>/… — the group and user names
# match the Mac's researcher folders (case aside). A 4-digit year folder is the
# marker we anchor on.
_YEAR_RE = re.compile(r"^(19|20)\d{2}$")


def corrections_filename(researcher):
    """`irene` -> `ni_corrections_irene.csv`. One file per researcher.

    A single shared file across researchers gets big and messy, and every
    operator would be editing rows that are not theirs.
    """
    slug = re.sub(r"[^a-z0-9_-]+", "-", (researcher or "").strip().lower()).strip("-")
    return FILENAME_PREFIX + (slug or "unknown") + ".csv"


def code_dir():
    """The directory holding `tools/` — i.e. where this code is staged."""
    here = os.path.dirname(os.path.abspath(__file__))          # …/tools/ingest
    return os.path.dirname(os.path.dirname(here))              # …/


def gnuclear_anchor(start_dir):
    """Split a staged-code path at gnuclear's `<YYYY>/<group>/` marker.

    Returns `(root, year, group)` or None. Derived from the running code's own
    location, which is why nothing has to be configured: on Windows the share is
    `S:\\gnuclear`, on the NI Mac it is some `/Volumes/…` mount, and both resolve
    correctly without an env var or a flag.

    Scans from the code outwards (nearest year folder wins) so a deeply staged
    copy still anchors on its own year rather than an unrelated one higher up.
    """
    norm = os.path.abspath(start_dir).replace("\\", "/").rstrip("/")
    parts = norm.split("/")
    # Need at least one segment after the year to read the group from.
    for i in range(len(parts) - 2, 0, -1):
        if _YEAR_RE.match(parts[i]):
            root = "/".join(parts[:i])
            if root and root.endswith(":"):      # bare Windows drive, e.g. "S:"
                root += "/"
            return (os.path.normpath(root), parts[i], parts[i + 1])
    return None


def _match_folder(parent, name):
    """Find `name` under `parent` case-insensitively; fall back to `name` itself.

    gnuclear spells users inconsistently (`irene` lowercase, `Claudia`/`Itziar`
    capitalised) while the Mac's researcher folders are all lowercase — so an
    exact match would silently create a second folder for the same person.
    """
    try:
        for entry in os.listdir(parent):
            if entry.lower() == name.lower() and os.path.isdir(
                    os.path.join(parent, entry)):
                return entry
    except OSError:
        pass
    return name


def resolve_path(researcher, start_dir=None):
    """The corrections file for `researcher`. No flag, no env var, no prompt.

    On gnuclear: `<root>/<year>/<group>/<researcher>/ni_corrections_<name>.csv`,
    with the year and group read off the staged code's own path.

    ONCE THE FILE EXISTS IT STAYS PUT. Later years are searched newest-first and
    an existing file is reused wherever it is found, so a correction never
    expires and `--plan` never re-lists a reviewed session just because the
    calendar turned over. A brand-new researcher's file is created under the
    year the code is staged in.

    When the code is NOT running from gnuclear (a dev checkout, or a copy on the
    Mac's local disk) there is no year/group to read, so the file falls back to
    sitting next to the code. Callers log the resolved path either way — that is
    the operator's answer to "where did my corrections go".
    """
    filename = corrections_filename(researcher)
    start = start_dir or code_dir()
    anchor = gnuclear_anchor(start)
    if not anchor:
        return os.path.join(start, filename)

    root, year, group = anchor
    try:
        years = sorted((d for d in os.listdir(root) if _YEAR_RE.match(d)),
                       reverse=True)
    except OSError:
        years = []
    for y in years:
        group_dir = os.path.join(root, y, _match_folder(os.path.join(root, y), group))
        candidate = os.path.join(
            group_dir, _match_folder(group_dir, researcher), filename)
        if os.path.isfile(candidate):
            return candidate

    year_dir = os.path.join(root, year)
    group_dir = os.path.join(year_dir, _match_folder(year_dir, group))
    return os.path.join(group_dir, _match_folder(group_dir, researcher), filename)


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
    """Stash the session_extra sidecar block on the RESOLVED case.

    Call in expand_batch AFTER apply_registry_block, with the row returned by
    apply_pre (so the lookup happens once). No-op if `row` is None.

    Nothing resolved is overridden here any more — session_id / sample_id derive
    from the corrected pre-resolution fields (see the module docstring).
    """
    if not row:
        return
    extra = parse_extra(row.get("extra_metadata"))
    if extra:
        case["session_extra"] = extra
