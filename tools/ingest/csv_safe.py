"""csv_safe.py — shared BOM-tolerant / trailing-newline-safe CSV helpers.

Every append-mode CSV writer in the toolset (registry_raw, ingest_manifest,
provenance, pending, registry_projects) routes through these so two
Excel-introduced hazards can't silently corrupt a registry:

  1. BOM. Excel "Save As CSV UTF-8" prepends a UTF-8 byte-order mark. A header
     read with plain utf-8 then sees '\\ufeffacq_id' != 'acq_id', so the
     defensive header check refuses every subsequent append (registry.append_row,
     pending._assert_header); a csv.DictReader mis-keys the first column.
     read_header() decodes utf-8-sig, which strips the BOM.

  2. Trailing newline. If a file's last line lacks a trailing '\\n' (Excel
     round-trip, hand edit), csv.writer opened in 'a' mode concatenates the new
     row onto the previous last row, silently corrupting two rows at once.
     ensure_trailing_newline() appends one '\\n' first when the file doesn't
     already end in a newline.

New CSV appenders MUST call ensure_trailing_newline(path) before opening the
file in 'a' mode, and read any existing header via read_header(). See
06_REGISTRIES.md (Concurrency / CSV-append safety) and 10_TOOLS.md.
"""

import csv
import os


def read_header(path):
    """Return the first CSV row (the header) as a list, BOM-tolerant.

    Returns [] when the file is absent or empty. Decodes with utf-8-sig so a
    leading UTF-8 BOM is stripped from the first field before comparison.
    """
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return next(csv.reader(f), [])


def ensure_trailing_newline(path):
    """Guarantee the file ends in a newline before an append is made.

    No-op when the file is absent or empty (csv.writer will write a fresh
    header). Otherwise, if the final byte is not '\\n', append one so the
    next appended row starts on its own line instead of being concatenated
    onto the existing last row. Byte-level check — encoding-agnostic.
    """
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return
    with open(path, "rb") as f:
        f.seek(-1, os.SEEK_END)
        last_byte = f.read(1)
    if last_byte != b"\n":
        with open(path, "ab") as f:
            f.write(b"\n")


# ---- Byte-exact record removal (retire_acquisition, 2026-10-01) ------------
#
# A registry rewrite through csv.DictWriter re-serializes EVERY row: quoting,
# line endings and any legacy byte the reader decoded tolerantly can all come
# back different. Removing a row must not do that. These helpers split a CSV
# into its raw records (bytes, terminator included) and drop whole records, so
# every byte that is not part of a removed record is written back unchanged.
#
# Splitting works on BYTES: '"' (0x22) and '\n' (0x0A) never occur inside a
# multi-byte UTF-8 sequence (or in latin-1 text as anything but themselves), so
# a quote-parity scan is encoding-agnostic. A newline inside a quoted field
# does not end a record.


def split_records(data):
    """Split CSV bytes into a list of raw records, each keeping its terminator.

    ``b"".join(split_records(data)) == data`` always holds. A final record with
    no trailing newline is returned as-is.

    A newline ends a record when the record so far holds an even number of '"'
    (each quote toggles "inside a quoted field"; an escaped "" toggles twice).
    Counted per newline with bytes.find / bytes.count rather than byte by byte:
    the same records, about 40 times faster on the 20 MB registry (2026-10-08,
    the retire tool splits it twice per retired id).
    """
    records = []
    start = pos = quotes = 0
    while True:
        nl = data.find(b"\n", pos)
        if nl < 0:
            break
        quotes += data.count(b'"', pos, nl)
        if quotes % 2 == 0:
            records.append(data[start:nl + 1])
            start, quotes = nl + 1, 0
        pos = nl + 1
    if start < len(data):
        records.append(data[start:])
    return records


def record_fields(record):
    """Parse one raw record (bytes) into its list of field strings.

    Decodes UTF-8 (BOM stripped), falling back to latin-1 -- the same tolerant
    chain the registry readers use. Used only to READ the key; the bytes that
    are written back are never re-encoded.
    """
    try:
        text = record.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = record.decode("latin-1")
    return next(csv.reader([text.rstrip("\r\n")]), [])


def record_terminator(path):
    """The line terminator of a CSV file's header record (b"\\r\\n" or b"\\n"; CRLF if unknown)."""
    if not os.path.exists(path):
        return b"\r\n"
    with open(path, "rb") as f:
        head = f.read(65536)
    recs = split_records(head)
    if recs and recs[0].endswith(b"\r\n"):
        return b"\r\n"
    if recs and recs[0].endswith(b"\n"):
        return b"\n"
    return b"\r\n"


def append_record(path, record):
    """Append one raw record (bytes) to an existing CSV, byte-exactly (retire tool v2, 2026-10-02).

    The record is written as given; one without a terminator gets the file's own (record_terminator).
    The trailing-newline guard runs first. The CALLER must hold ``locking.registry_lock`` when the
    file is a registry.
    """
    if not os.path.exists(path):
        raise RuntimeError(f"{path}: append_record needs an existing file (with its header)")
    if not record.endswith(b"\n"):
        record += record_terminator(path)
    ensure_trailing_newline(path)
    with open(path, "ab") as f:
        f.write(record)
        f.flush()
        os.fsync(f.fileno())


def remove_records(path, key_field, keys, dry_run=False):
    """Remove every record whose ``key_field`` value is in ``keys``, byte-exactly.

    Returns the list of removed records (bytes, terminator included) in file
    order. The header and every kept record are written back byte-for-byte
    (BOM, line endings, quoting all as found), through a temp file +
    ``os.replace`` so a crash can never leave a truncated file. Nothing is
    written when nothing matches, or when ``dry_run`` is set.

    The CALLER must hold ``locking.registry_lock`` across this call when the
    file is a registry (it is a read-modify-write).

    Raises RuntimeError if ``key_field`` is not in the header.
    """
    keys = {k for k in keys if k}
    if not keys or not os.path.exists(path):
        return []
    with open(path, "rb") as f:
        data = f.read()
    records = split_records(data)
    if not records:
        return []
    header = record_fields(records[0])
    if key_field not in header:
        raise RuntimeError(f"{path}: no '{key_field}' column in header {header}")
    col = header.index(key_field)
    kept, removed = [records[0]], []
    for rec in records[1:]:
        fields = record_fields(rec)
        val = fields[col].strip() if len(fields) > col else ""
        (removed if val in keys else kept).append(rec)
    if removed and not dry_run:
        tmp = f"{path}.tmp.{os.getpid()}"
        with open(tmp, "wb") as f:
            f.write(b"".join(kept))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    return removed
