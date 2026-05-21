"""Minimal JCAMP-DX parser for Bruker ParaVision aux files.

Handles the dialect found in `subject`, `acqp`, `method`, `visu_pars`,
`reco` files: `##KEY=value` headers, `##$KEY=value` parameters, `( N )`
sized arrays spanning multiple lines, `<...>` strings, `$$` comments,
inline `(a, b, c)` tuples.

`parse_file(path)` returns a flat dict keyed by parameter name (the
`##$` or `##` prefix is stripped). Values are coerced where confident
(int, float, list, tuple) and left as strings otherwise.
"""

import re
from pathlib import Path


# ##KEY= or ##$KEY= starts a new entry; rest of line is the initial value.
_ENTRY = re.compile(r"^##(\$?)([A-Za-z_][A-Za-z0-9_]*)=(.*)$")

# `( N )` or `( N, M )` sizing prefix at the start of a parameter value
# signals that the actual content follows on subsequent lines.
_SIZED = re.compile(r"^\(\s*(\d+(?:\s*,\s*\d+)*)\s*\)\s*$")

# Standalone integer / float (with optional sign, exponent).
_INT = re.compile(r"^-?\d+$")
_FLOAT = re.compile(r"^-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?$")


def _coerce_scalar(s):
    """Coerce a single token to int / float / string."""
    s = s.strip()
    if _INT.match(s):
        return int(s)
    if _FLOAT.match(s):
        return float(s)
    if len(s) >= 2 and s[0] == "<" and s[-1] == ">":
        return s[1:-1]
    return s


def _split_angle_strings(body):
    """Split a body like '<a> <b> <c>' into ['a', 'b', 'c']. Returns None
    if the body doesn't appear to be a sequence of angle-bracketed strings.
    """
    body = body.strip()
    if not body.startswith("<"):
        return None
    out = []
    depth = 0
    cur = []
    for ch in body:
        if ch == "<":
            if depth == 0:
                cur = []
            else:
                cur.append(ch)
            depth += 1
        elif ch == ">":
            depth -= 1
            if depth == 0:
                out.append("".join(cur))
            else:
                cur.append(ch)
        elif depth > 0:
            cur.append(ch)
        # whitespace between strings is ignored at depth 0
    if depth != 0:
        return None
    return out


def _split_tuples(body):
    """Split a body like '(a, b, c) (d, e, f)' into a list of tuples.
    Returns None if not tuple-shaped at the top level.
    """
    body = body.strip()
    if not body.startswith("("):
        return None
    out = []
    depth = 0
    cur = []
    for ch in body:
        if ch == "(":
            if depth == 0:
                cur = []
            else:
                cur.append(ch)
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                out.append(_parse_tuple_body("".join(cur)))
            else:
                cur.append(ch)
        elif depth > 0:
            cur.append(ch)
    if depth != 0:
        return None
    return out


def _parse_tuple_body(body):
    """Parse the inside of a `(...)` — comma-separated, with nested
    `<...>` strings preserved as units."""
    parts = []
    depth = 0
    cur = []
    for ch in body:
        if ch == "<":
            depth += 1
            cur.append(ch)
        elif ch == ">":
            depth -= 1
            cur.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur).strip())
    return tuple(_coerce_scalar(p) for p in parts)


def _parse_value(raw, sized):
    """Best-effort coerce a collected raw value to a typed value.

    `sized` is True when a `( N )` prefix was seen — that signals the
    content is a buffer of N items (split on whitespace into a list,
    or `<...>` strings). When `sized` is False, the value is an inline
    scalar — kept as a single string when it contains spaces.
    """
    s = raw.strip()
    if not s:
        return ""
    # Sequence of angle-bracketed strings (always — these are
    # self-delimited regardless of sized).
    angle = _split_angle_strings(s)
    if angle is not None:
        return angle[0] if len(angle) == 1 else angle
    # Tuple(s) — also self-delimited.
    if s.startswith("("):
        tuples = _split_tuples(s)
        if tuples is not None:
            return tuples[0] if len(tuples) == 1 else tuples
    # Whitespace-separated array — only when a sized prefix was seen.
    if sized:
        tokens = s.split()
        if len(tokens) > 1:
            return [_coerce_scalar(t) for t in tokens]
        if len(tokens) == 1:
            return _coerce_scalar(tokens[0])
        return ""
    # Inline scalar — keep as a single string if it has spaces.
    return _coerce_scalar(s) if " " not in s else s


def parse_file(path):
    """Parse a JCAMP-DX file and return a flat dict of parameters.

    Comments (`$$ ...`) are dropped. Both `##KEY=` and `##$KEY=` are
    captured; the `##` or `##$` prefix is stripped from the key. Values
    are coerced to int / float / str / list / tuple where confident.
    Returns `{}` if the file doesn't exist or is empty.
    """
    p = Path(path)
    if not p.is_file():
        return {}

    out = {}
    pending_key = None
    pending_lines = []

    def flush():
        nonlocal pending_key, pending_lines
        if pending_key is None:
            return
        sized = False
        lines = pending_lines
        # If the first line is a `( N )` sized prefix on its own, strip
        # it and mark sized=True so the remainder is parsed as a buffer.
        if pending_lines:
            first = pending_lines[0].strip()
            m = _SIZED.match(first)
            if m:
                sized = True
                lines = pending_lines[1:]
        raw = "\n".join(lines).strip()
        out[pending_key] = _parse_value(raw, sized) if raw else ""
        pending_key = None
        pending_lines = []

    with p.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            # Comment line.
            if line.startswith("$$"):
                continue
            # New entry.
            m = _ENTRY.match(line)
            if m:
                flush()
                _, key, init_val = m.groups()
                pending_key = key
                pending_lines = [init_val] if init_val.strip() else []
                # Inline value forms (e.g. `##$KEY=value`) are captured in
                # init_val; multi-line continuations are appended below.
                continue
            # ##END= marker (special — no continuation).
            if line.startswith("##END"):
                flush()
                pending_key = None
                continue
            # Continuation line for the current entry.
            if pending_key is not None and line.strip():
                pending_lines.append(line)
    flush()

    return out
