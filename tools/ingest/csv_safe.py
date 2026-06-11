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
