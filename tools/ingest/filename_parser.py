"""Filename / folder-name parser for ingest auto-discovery.

Two complementary parsers:

  - `parse(name, separator, fields)` — positional split (AxioScan-style,
    where every chunk in the name is a meaningful piece in a stable
    position).
  - `parse_regex(name, pattern)` — named-group regex extraction (for
    messy names like Bruker ParaVision FTP folder names where only
    parts of the name are meaningful).

Both return a `{field: value}` dict on success. Both can be used
together in a config; the caller decides precedence (see
`config.expand_batch`).
"""

import os
import re


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


def parse_regex(name, pattern):
    """Extract named-group values from a name via regex.

    Args:
        name: file or folder basename. Extension is NOT stripped — the
            caller's regex can match or ignore it. (This differs from
            `parse()`, which strips the extension; regex use is opt-in
            and the operator usually wants control over the full name.)
        pattern: a Python regex string containing named groups
            `(?P<name>...)`. Searched (not anchored — use `^`/`$` in the
            pattern if you want anchoring).

    Returns:
        dict mapping each named group to its matched value (empty
        string for groups that didn't participate in the match).

    Raises:
        FilenameParseError when the pattern doesn't match anywhere in
        the name, or when the pattern has no named groups.
    """
    if not pattern:
        raise ValueError("pattern must be non-empty")

    try:
        rx = re.compile(pattern)
    except re.error as e:
        raise ValueError(f"Invalid regex pattern {pattern!r}: {e}")

    if not rx.groupindex:
        raise ValueError(
            f"Regex pattern {pattern!r} has no named groups — "
            f"use `(?P<name>...)` to extract values"
        )

    base = os.path.basename(name)
    m = rx.search(base)
    if not m:
        raise FilenameParseError(
            f"Regex {pattern!r} did not match name {base!r}"
        )
    return {k: (v if v is not None else "") for k, v in m.groupdict().items()}
