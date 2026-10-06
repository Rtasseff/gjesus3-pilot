"""reidentify.py -- the pure parts of re-identifying an acquisition (retire tool v2, 2026-10-02).

A mis-coded acquisition (wrong instrument code, so a wrong ACQ-ID) is re-identified IN PLACE by
tools/retire_acquisition.py: a new ACQ-ID from the normal allocator, a hard link to the same file in the
new /raw/ folder, its three sidecars rewritten, the old id tombstoned with disposition `reidentified`
(06_REGISTRIES §2.9, 10_TOOLS §3.9). Nothing here touches the disk: these functions compute the new
registry row and the new sidecar bytes, and they refuse (ValueError) rather than guess.

Every rewrite is a TARGETED substitution ON BYTES, so every other byte of a sidecar -- key order,
indentation, escapes, CRLF or LF line endings, and any legacy non-UTF-8 byte -- is kept exactly. (Real
production READMEs mix encodings: a UTF-8 header and a cp1252 0x97 dash in the notes, 2026-10-02.) Each
JSON rewrite is then verified by parsing the result and comparing it with the expected object.
"""
import json
import re

# The fields a re-identify changes in registry_raw.csv. Everything else is kept as it was (Q6 in
# tasks/retire_v2_review.md): the bytes were registered on their original date by their original config.
IDENTITY_FIELDS = ("acq_id", "instrument", "primary_file_name", "canonical_path")


def replace_id(text, old_id, new_id):
    """Replace the old ACQ-ID as a whole id (never a prefix of a longer sequence number). str or bytes."""
    if isinstance(text, bytes):
        return re.sub(re.escape(old_id.encode("ascii")) + rb"(?!\d)", new_id.encode("ascii"), text)
    return re.sub(re.escape(old_id) + r"(?!\d)", new_id, text)


def instrument_of(acq_id):
    """The instrument code inside an ACQ-ID (ACQ-YYYYMMDD-<CODE>-NNN)."""
    parts = (acq_id or "").split("-")
    if len(parts) != 4 or parts[0] != "ACQ":
        raise ValueError(f"not an ACQ-ID: {acq_id!r}")
    return parts[2]


def changes_for(row, new_id, instrument_model=None):
    """{field: [old, new]} for re-identifying `row` as `new_id`.

    `instrument_model` changes only when given and different from the row's value.
    """
    old_id = row["acq_id"]
    new_code = instrument_of(new_id)
    if old_id.split("-")[1] != new_id.split("-")[1]:
        raise ValueError(f"{new_id} does not keep the date of {old_id}")
    changes = {
        "acq_id": [old_id, new_id],
        "instrument": [row.get("instrument", ""), new_code],
        "primary_file_name": [row.get("primary_file_name", ""),
                              replace_id(row.get("primary_file_name", ""), old_id, new_id)],
        "canonical_path": [row.get("canonical_path", ""),
                           replace_id(row.get("canonical_path", ""), old_id, new_id)],
    }
    for f in ("primary_file_name", "canonical_path"):
        if old_id not in changes[f][0]:
            raise ValueError(f"{old_id}: {f} {changes[f][0]!r} does not contain the ACQ-ID")
    if instrument_model is not None and instrument_model != row.get("instrument_model", ""):
        changes["instrument_model"] = [row.get("instrument_model", ""), instrument_model]
    return changes


def new_row(row, changes):
    """The re-identified registry row: `row` with `changes` applied (each old value must match)."""
    out = dict(row)
    for field, (old, new) in changes.items():
        if out.get(field, "") != old:
            raise ValueError(f"{field}: row has {out.get(field)!r}, the change expects {old!r}")
        out[field] = new
    return out


def _replace_in_obj(obj, old_id, new_id):
    if isinstance(obj, dict):
        return {replace_id(k, old_id, new_id) if isinstance(k, str) else k:
                _replace_in_obj(v, old_id, new_id) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_replace_in_obj(v, old_id, new_id) for v in obj]
    if isinstance(obj, str):
        return replace_id(obj, old_id, new_id)
    return obj


def _no_bom(data, name):
    if data.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"{name} starts with a BOM; not rewriting it")


def rewrite_metadata_json(data, old_id, new_id, old_code, new_code):
    """metadata.json: every occurrence of the old id -> the new id; user_supplied.instrument -> new_code."""
    _no_bom(data, "metadata.json")
    obj = json.loads(data)
    if not isinstance(obj, dict) or obj.get("acq_id") != old_id:
        raise ValueError(f"metadata.json: acq_id is {obj.get('acq_id') if isinstance(obj, dict) else None!r}, "
                         f"not {old_id}")
    us = obj.get("user_supplied")
    if not isinstance(us, dict) or us.get("instrument") != old_code:
        raise ValueError(f"metadata.json: user_supplied.instrument is "
                         f"{us.get('instrument') if isinstance(us, dict) else None!r}, not {old_code!r}")
    expected = _replace_in_obj(obj, old_id, new_id)
    expected["user_supplied"] = dict(expected["user_supplied"], instrument=new_code)
    out = replace_id(data, old_id, new_id)
    out, n = re.subn(rb'("instrument"\s*:\s*)"' + re.escape(old_code.encode("ascii")) + rb'"',
                     lambda m: m.group(1) + json.dumps(new_code).encode("ascii"), out)
    if n < 1 or json.loads(out) != expected:
        raise ValueError("metadata.json: the targeted rewrite does not give the expected sidecar "
                         f"({n} 'instrument' value(s) replaced); not rewriting it")
    return out


def rewrite_checksums_json(data, old_id, new_id, primary_name_new, sha256=None):
    """checksums.json: the file key (and any other occurrence) of the old id -> the new id."""
    _no_bom(data, "checksums.json")
    obj = json.loads(data)
    expected = _replace_in_obj(obj, old_id, new_id)
    out = replace_id(data, old_id, new_id)
    if json.loads(out) != expected:
        raise ValueError("checksums.json: the targeted rewrite does not give the expected object")
    files = expected.get("files") if isinstance(expected, dict) else None
    if not isinstance(files, dict) or primary_name_new not in files:
        raise ValueError(f"checksums.json: no entry for {primary_name_new} after the rewrite")
    if sha256 and files[primary_name_new] != sha256:
        raise ValueError(f"checksums.json: {primary_name_new} is {files[primary_name_new]}, the file hashes "
                         f"{sha256}")
    return out


def rewrite_readme(data, old_id, new_id, old_code, new_code, note, old_model=None, new_model=None):
    """README.txt: the id and the `Instrument : <code>` line rewritten; `note` (ASCII) appended as a last line.

    Works on bytes (READMEs can mix encodings). Keeps the file's own line ending. Refuses unless exactly
    one Instrument line carries old_code.
    """
    _no_bom(data, "README.txt")
    nl = b"\r\n" if b"\r\n" in data else b"\n"
    out = replace_id(data, old_id, new_id)
    out, n = re.subn(rb"(?m)^(Instrument[ \t]*:[ \t]*)" + re.escape(old_code.encode("ascii")) + rb"(?=[ \t]*\r?$)",
                     lambda m: m.group(1) + new_code.encode("ascii"), out)
    if n != 1:
        raise ValueError(f"README.txt: expected exactly one 'Instrument : {old_code}' line, found {n}")
    if new_model is not None and old_model is not None and new_model != old_model:
        out, n = re.subn(rb"(?m)^(Instrument Model[ \t]*:[ \t]*)" + re.escape(old_model.encode("utf-8"))
                         + rb"(?=[ \t]*\r?$)", lambda m: m.group(1) + new_model.encode("utf-8"), out)
        if n != 1:
            raise ValueError(f"README.txt: expected exactly one 'Instrument Model : {old_model}' line")
    if not out.endswith(nl):
        out += nl
    return out + note.encode("ascii") + nl


def readme_note(old_id, old_code, new_code, date, rule):
    """The line appended to a re-identified README (ASCII only: READMEs can mix encodings)."""
    return (f"Re-identified by retire_acquisition.py on {date}: this acquisition was registered as "
            f"{old_id}; its instrument code was corrected {old_code} -> {new_code} from the file's own "
            f"device metadata ({rule}). The old ID resolves here (find_acq.py).")


def carry_record(record, old_id, new_id):
    """A bookkeeping CSV record (bytes, terminator included) with the old id rewritten to the new one."""
    out = replace_id(record, old_id, new_id)
    if out == record:
        raise ValueError(f"record does not name {old_id}: {record[:80]!r}")
    return out


def sidecar_identity(sidecars):
    """(acq_id, instrument, files map) read back from sidecar bytes -- for verification."""
    md = json.loads(sidecars["metadata.json"])
    cs = json.loads(sidecars["checksums.json"])
    return md.get("acq_id"), (md.get("user_supplied") or {}).get("instrument"), cs.get("files")
