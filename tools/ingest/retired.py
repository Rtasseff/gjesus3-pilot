"""retired.py — the tombstone registry of retired ACQ-IDs (retired_acquisitions.csv).

Spec: 06_REGISTRIES §2.9 (this module is that schema's integrity mirror) and
10_TOOLS §2.1 / §3.9 (`tools/retire_acquisition.py`, the only writer).

A RETIRED acquisition is one the Data Office has taken out of the live registry
(Ryan, 2026-10-01): a byte-identical DUPLICATE registration of another
acquisition, a DERIVATIVE (scale-bar copy, thumbnail, export) that is not an
acquisition and moved to its original's project folder, or an ORPHAN `/raw/`
folder whose registry row was never written. v2 (2026-10-02) adds an
EQUIVALENT duplicate (a .czi re-save: same information, different container)
and a REIDENTIFIED acquisition (a wrong instrument code, so a wrong ACQ-ID: the
same file re-registered in place under a new id, which is its superseded_by).
Its row LEAVES registry_raw.csv and is appended here, verbatim, with the reason
and what happened to the bytes.

Rules this file carries:
  - ACQ-IDs are NEVER reused. A tombstoned id still counts toward the ACQ-ID
    high-water (acq_id._max_seq_in_registry reads this file too), so the rule
    does not depend on `.acq_id_seq.json` alone.
  - One row per retired id. An id is live (in registry_raw.csv) or retired
    (here), never both; validate_registries reports both-at-once as an ERROR
    (it is also the signature of a retire run that crashed mid-commit — re-run
    the tool to finish it).
  - `superseded_by` names a LIVE acquisition (the surviving duplicate, or the
    derivative's original). Blank only for an orphan.
  - Rows are permanent. Nothing deletes or edits a tombstone.

Ryan expects to revisit a `status` column in registry_raw.csv instead (BACKLOG,
MEDIUM), so this schema is a SUPERSET of what that would need: the original
row verbatim, plus every other registry row the retirement removed.
"""

import csv
import json
import os
import re

from . import csv_safe


RETIRED_FILENAME = "retired_acquisitions.csv"

# Column order is the contract (06_REGISTRIES §2.9). A header mismatch makes the
# appender refuse rather than corrupt the alignment.
RETIRED_FIELDS = [
    "acq_id",            # the retired id (unique key)
    "retired_at",        # ISO-8601 UTC of the commit
    "disposition",       # duplicate | derivative | orphan | equivalent | reidentified
    "superseded_by",     # the live acquisition it duplicates / derives from / was re-identified
                         #   as ("" for orphan)
    "reason",            # free text, required; v2 appends " || evidence: {json}" (EVIDENCE_SEP)
    "bytes_fate",        # deleted | moved  (what happened to the /raw/ bytes)
    "moved_to",          # NAS-relative path of the bytes' new home (derivative), else ""
    "sha256",            # SHA-256 of the primary, hashed fresh from disk at retirement
                         #   (folder primary: SHA-256 of the sorted "relpath<TAB>sha256\n" list)
    "original_canonical_path",  # where the acquisition lived in /raw/
    "retired_by",        # who ran the retirement (Data Office) -- NOT the equipment operator
    "run_id",            # the retire run that wrote this row (links to its report + backup)
    "backup_dir",        # the off-NAS backup taken before the run
    "registry_raw_row",  # the removed registry_raw.csv record, VERBATIM (no line terminator);
                         #   "" for an orphan (it never had one)
    "other_rows_removed",  # JSON {file name: [verbatim records]} -- the ingest_manifest
                           #   and pending_* queue rows. Never a registry_subjects row:
                           #   subjects are never deleted (06 §2.8.3).
]

DISPOSITIONS = ("duplicate", "derivative", "orphan",
                # v2 (2026-10-02): a .czi re-save that is information-identical to the survivor but
                # not byte-identical; and a mis-coded acquisition re-registered in place under the
                # right instrument code (superseded_by = its new id). 06_REGISTRIES §2.9.
                "equivalent", "reidentified")
BYTES_FATES = ("deleted", "moved")

# v2: the tool's own evidence is appended to the operator's `reason`, after this separator, as one
# compact JSON object (no schema change: the tombstone file's header stays as v1 created it).
EVIDENCE_SEP = " || evidence: "


def with_evidence(reason, evidence):
    """The `reason` cell: the operator's reason, then the tool's evidence as compact JSON."""
    if not evidence:
        return reason
    return reason + EVIDENCE_SEP + json.dumps(evidence, sort_keys=True, separators=(",", ":"),
                                              ensure_ascii=False)


def split_evidence(reason):
    """(the operator's reason, evidence dict or None) from a tombstone's `reason` cell."""
    reason = reason or ""
    if EVIDENCE_SEP not in reason:
        return reason, None
    head, _sep, tail = reason.rpartition(EVIDENCE_SEP)
    try:
        ev = json.loads(tail)
    except ValueError:
        return reason, None
    return (head, ev) if isinstance(ev, dict) else (reason, None)

ACQ_ID_RE = re.compile(r"ACQ-\d{8}-[A-Z0-9]+-\d{3}(?!\d)")


def retired_path(registries_dir):
    """Absolute path of the tombstone file under a registries/ directory."""
    return os.path.join(registries_dir, RETIRED_FILENAME)


def read_retired(path):
    """Return {acq_id: row} from the tombstone file ({} when absent).

    Tolerant decode (utf-8-sig, then latin-1) mirrors registry.read_registry.
    """
    if not os.path.exists(path):
        return {}
    for enc in ("utf-8-sig", "latin-1"):
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                out = {}
                for r in csv.DictReader(f):
                    aid = (r.get("acq_id") or "").strip()
                    if aid:
                        out[aid] = r
                return out
        except UnicodeDecodeError:
            continue
    return {}


def assert_header_compatible(path):
    """Raise RuntimeError if an existing tombstone file's header != RETIRED_FIELDS."""
    if not os.path.exists(path):
        return
    existing = csv_safe.read_header(path)
    if existing and existing != RETIRED_FIELDS:
        raise RuntimeError(
            f"retired_acquisitions header mismatch in {path}\n"
            f"  file has {len(existing)} columns: {existing}\n"
            f"  code expects {len(RETIRED_FIELDS)}: {RETIRED_FIELDS}\n"
            f"  refusing to append (would corrupt column alignment).")


def append_retired(path, row):
    """Append one tombstone row. The CALLER must hold the registry lock.

    Validates the row first: a known disposition and bytes fate, a reason, and a
    superseded_by for every disposition except orphan. Creates the file (with
    its header) on first use. CRLF line endings and no BOM, like every other
    registry file (csv.writer's default terminator is CRLF).
    """
    missing = [k for k in row if k not in RETIRED_FIELDS]
    if missing:
        raise RuntimeError(f"append_retired: unknown field(s) {missing}")
    if row.get("disposition") not in DISPOSITIONS:
        raise RuntimeError(f"append_retired: disposition {row.get('disposition')!r} "
                           f"not in {DISPOSITIONS}")
    if row.get("bytes_fate") not in BYTES_FATES:
        raise RuntimeError(f"append_retired: bytes_fate {row.get('bytes_fate')!r} "
                           f"not in {BYTES_FATES}")
    if not (row.get("reason") or "").strip():
        raise RuntimeError("append_retired: a reason is required")
    if row["disposition"] != "orphan" and not (row.get("superseded_by") or "").strip():
        raise RuntimeError("append_retired: superseded_by is required for "
                           f"disposition {row['disposition']!r}")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    file_exists = os.path.exists(path) and os.path.getsize(path) > 0
    if file_exists:
        assert_header_compatible(path)
    csv_safe.ensure_trailing_newline(path)
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=RETIRED_FIELDS)
        if not file_exists:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in RETIRED_FIELDS})


def other_rows(row):
    """The tombstone's other_rows_removed JSON, decoded ({} when blank/invalid)."""
    try:
        val = json.loads(row.get("other_rows_removed") or "{}")
        return val if isinstance(val, dict) else {}
    except ValueError:
        return {}


# ---- Curated-dataset citations (shared by the retire tool and the validator) ----

# Text files a dataset folder may cite an ACQ-ID in. Label data (masks, NIfTI,
# TIFF) is binary and is never opened.
_CITATION_EXTS = {".csv", ".tsv", ".yaml", ".yml", ".txt", ".md", ".json"}


def curated_citations(nas_root):
    """Map every ACQ-ID a curated dataset cites -> sorted list of "DS-ID (where)".

    Scans registries/registry_datasets.csv (every column: `source_acq_ids` may
    say "see provenance.csv") and every text file under curated_datasets/ (the
    dataset's provenance.csv, _dataset.yaml, registry_row.csv, slice maps, ...).
    A file is attributed to the DS-* folder it sits under. Read-only.
    """
    hits = {}

    def add(acq, where):
        hits.setdefault(acq, set()).add(where)

    ds_csv = os.path.join(nas_root, "registries", "registry_datasets.csv")
    if os.path.exists(ds_csv):
        with open(ds_csv, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
            for r in csv.DictReader(f):
                ds = (r.get("dataset_id") or "").strip() or "?"
                for acq in ACQ_ID_RE.findall(" ".join(str(v) for v in r.values())):
                    add(acq, f"{ds} (registry_datasets.csv)")

    root = os.path.join(nas_root, "curated_datasets")
    for dirpath, _dirs, files in os.walk(root):
        rel_parts = os.path.relpath(dirpath, root).split(os.sep)
        ds = next((p for p in rel_parts if p.startswith("DS-")), None) or "?"
        for fn in files:
            if os.path.splitext(fn)[1].lower() not in _CITATION_EXTS:
                continue
            p = os.path.join(dirpath, fn)
            try:
                with open(p, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except OSError:
                continue
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            for acq in set(ACQ_ID_RE.findall(text)):
                add(acq, f"{ds} ({rel})")
    return {k: sorted(v) for k, v in hits.items()}


def original_row(tomb_row, fields):
    """The tombstone's verbatim registry_raw record parsed into a dict.

    ``fields`` is the registry column list to zip against (pass
    registry.REGISTRY_FIELDS). Returns {} for an orphan (no row) or when the
    record's column count no longer matches -- a registry migration since the
    retirement; the verbatim text is still in the tombstone for a human.
    """
    text = (tomb_row.get("registry_raw_row") or "").strip("\r\n")
    if not text:
        return {}
    vals = next(csv.reader([text]), [])
    if len(vals) != len(fields):
        return {}
    return dict(zip(fields, vals))
