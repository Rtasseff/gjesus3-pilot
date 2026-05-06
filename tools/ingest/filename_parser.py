"""Positional filename parser for ingest auto-discovery.

Used by AxioScan 7 (and similar) where filenames carry metadata chunks
separated by a known character. The parser is pure: given a filename,
a separator, and an ordered list of field names, it returns a dict.

Special meaning (e.g. promoting `sample_id` into a registry column) is
handled separately in registry.apply_special_fields — this module only
splits.
"""

import os


class FilenameParseError(ValueError):
    """Raised when a filename cannot be parsed against the expected fields."""


def parse(filename, separator, fields):
    """Parse a filename's stem into a {field: value} dict.

    Args:
        filename: bare filename (extension is stripped) or any path-like.
        separator: chunk separator (typically '_').
        fields: ordered list of field names matching positional chunks.

    Returns:
        dict mapping each field name to its parsed value. Extra chunks
        beyond len(fields) are silently dropped (caller may warn).
        Missing chunks raise FilenameParseError.

    Raises:
        FilenameParseError when the filename has fewer chunks than `fields`.
    """
    if not fields:
        raise ValueError("fields list must be non-empty")

    stem = os.path.splitext(os.path.basename(filename))[0]
    chunks = stem.split(separator)

    if len(chunks) < len(fields):
        raise FilenameParseError(
            f"Filename '{filename}' produced {len(chunks)} chunks "
            f"(separator='{separator}'); expected at least {len(fields)} "
            f"for fields={fields}"
        )

    return {name: chunks[i] for i, name in enumerate(fields)}


def count_extra_chunks(filename, separator, fields):
    """How many chunks remain after the named fields are filled.

    Useful for callers that want to log a WARN when files have unexpected
    extra trailing data.
    """
    stem = os.path.splitext(os.path.basename(filename))[0]
    chunks = stem.split(separator)
    return max(0, len(chunks) - len(fields))
