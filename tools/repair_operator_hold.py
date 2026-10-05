#!/usr/bin/env python3
"""repair_operator_hold.py -- change `operator` cells of registry_raw.csv from one exact value
to another, edited in BYTES, touching nothing else. Dry run unless --apply. Data Office only.

    python tools/repair_operator_hold.py --nas-root "J:\\gjesus3-data"                     (dry run)
    python tools/repair_operator_hold.py --nas-root "J:\\gjesus3-data" --apply --expect 10314 \\
        --backup-dir "C:\\Users\\rtasseff\\temp\\gjesus3_operator_hold_20261005"

WHY. 10,314 MRI rows of the 2026-06 bulk load carry a template instruction in `operator`
(`<REQUIRED - set via mri-ingest --operator, or replace here>`), and the operator is not
recoverable (ParaVision records only `nmr`, a shared login). Ryan ruled on 2026-10-05
(STATUS section 0, D1) that the cells become the HOLD VALUE `pending-claim` ("awaiting
claim") now, and that whatever is still unclaimed when the claim window closes is blanked
later. Blank means "unknown" and is final; `pending-claim` means a claim is still open.
The value is `ingest.registry.OPERATOR_HOLD`; it is set by the Data Office with THIS tool,
never by an ingest. 06_REGISTRIES section 2.3a-bis. Defaults are part (a):

    --from "<REQUIRED - set via mri-ingest --operator, or replace here>"   --to pending-claim

Part (c), once the claim window closes, reuses the tool: `--from pending-claim --to-blank`
(`--to ""` does the same; Windows PowerShell 5.1 drops an empty argument, hence --to-blank).

WHAT IT CHANGES. Only `operator` cells whose value equals --from EXACTLY (no trimming, no
case folding), in registry_raw.csv, and nothing else: not another column, not another row,
not a sidecar (`user_supplied.operator` in /raw/<ACQ-ID>/metadata.json keeps its text until
its own final value is known). A --from that is blank is refused: blank means "unknown" and
must never be bulk-filled.

HOW. The file is edited as bytes, never through a csv round-trip (it has no BOM and CRLF line
endings; a csv.writer would reformat quoting across 15 MB). Records are split with
ingest.csv_safe.split_records, a cell is read with the csv module from its own record, and its
exact byte span is located by a strict RFC 4180 scanner that must agree with the csv module.
NOTE that the placeholder contains a comma, so csv.writer stored all 10,314 cells QUOTED:
`,"<REQUIRED - ..., or replace here>",`. The span replaced is the whole field, quotes included,
and the new value is written bare (so each such cell shrinks by len(from) + 2 - len(to)
bytes; the dry run prints the exact expected delta). A record the scanner cannot parse
exactly is refused, not guessed at.

SAFETY. --apply requires --expect N and refuses unless exactly N cells match. It requires
--backup-dir, which must not exist (a re-used backup folder once destroyed a snapshot here)
and must be off the NAS; registry_raw.csv is copied there and the copy's SHA-256 checked
against the source BEFORE anything is written. The registry lock (ingest.locking) is held
from the read to the end of the verification, so no ingest can append between them. The
new file is written beside the registry and swapped in with os.replace. It is then re-read
and compared with the backup record by record: exactly N records differ, each in `operator`
only, each old value equal to --from and each new value equal to --to, every other byte
identical, line terminators unchanged, and the size changed by exactly the expected delta.
On any mismatch the backup is restored and the exit code is non-zero.

Exit codes: 0 done / dry run / nothing to do with --expect 0; 1 refused, or verification
failed and the backup was restored; 2 bad arguments or NAS root; 3 verification failed AND
the restore failed (restore by hand from the backup folder).

On success --apply prints key=value lines: rows_changed, size_before, size_after,
sha256_before, sha256_after, backup, sha256_backup.
"""

import argparse
import csv
import hashlib
import os
import shutil
import sys
from collections import Counter, namedtuple
from datetime import datetime

# Make `from ingest import ...` work whether the script is launched from the repo
# root or from tools/ (mirrors validate_registries.py).
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from ingest import csv_safe, locking, registry  # noqa: E402

REGISTRY_FILENAME = "registry_raw.csv"
# What the 2026-06 MRI bulk configs left in `operator` on 10,314 rows (BACKLOG, the
# `operator` item). Part (a) of STATUS section 0 D1 replaces it with the hold value.
PLACEHOLDER = "<REQUIRED - set via mri-ingest --operator, or replace here>"
EXAMPLES_SHOWN = 3

# One planned edit: the absolute byte span [start, end) of the operator field in the file
# (surrounding quotes included, when it is quoted), the row it is on, and its form.
Match = namedtuple("Match", "start end acq_id instrument quoted")


class RepairError(Exception):
    """A refusal: the run stops, and (unless it says otherwise) nothing was written."""


def log(msg, level="INFO"):
    """Timestamped log line to stderr; ASCII only for the Windows console."""
    print(f"[{datetime.now():%H:%M:%S}] {level}: {msg}", file=sys.stderr)


# ---- Arguments -----------------------------------------------------------

def check_values(from_value, to_value):
    """Refuse values this tool cannot edit safely. Raises RepairError."""
    if from_value == "":
        raise RepairError(
            "--from is blank. Blank means 'unknown' and is final; this tool never bulk-fills it.")
    if from_value == to_value:
        raise RepairError("--from and --to are identical: nothing to change.")
    for flag, value, banned in (("--from", from_value, '"\r\n'), ("--to", to_value, ',"\r\n')):
        bad = sorted({c for c in value if c in banned})
        if bad:
            raise RepairError(
                f"{flag} may not contain {' '.join(repr(c) for c in bad)}: the new value is written "
                f"bare (and --from is matched as plain text), so such a value is not supported.")


# ---- Reading the registry as bytes ---------------------------------------

def _split_terminator(record):
    """(body, terminator) of one raw record; the final record may have no terminator."""
    if record.endswith(b"\r\n"):
        return record[:-2], b"\r\n"
    if record.endswith(b"\n"):
        return record[:-1], b"\n"
    return record, b""


def field_spans(body):
    """[(start, end)] of every field in one record body (terminator already removed).

    Strict RFC 4180: a quoted field runs to its closing quote (a doubled quote inside it is an
    escaped quote), which must be followed by a comma or the end; a quote inside an unquoted
    field is refused. The spans cover the raw bytes, quotes included, and are separated by
    exactly one comma each. Raises ValueError for anything else.
    """
    spans = []
    n = len(body)
    i = 0
    while True:
        start = i
        if i < n and body[i] == 0x22:                      # '"'
            i += 1
            while True:
                j = body.find(b'"', i)
                if j < 0:
                    raise ValueError("unterminated quoted field")
                if j + 1 < n and body[j + 1] == 0x22:       # "" -- an escaped quote
                    i = j + 2
                    continue
                i = j + 1                                  # the closing quote
                break
            if i < n and body[i] != 0x2C:                  # ','
                raise ValueError("text after a closing quote")
            end = i
        else:
            j = body.find(b",", i)
            end = n if j < 0 else j
            if b'"' in body[i:end]:
                raise ValueError("a quote inside an unquoted field")
            i = end
        spans.append((start, end))
        if i >= n:
            return spans
        i += 1                                             # step over the comma


def _unquote(raw):
    """The value bytes of one raw field (as field_spans delimits it)."""
    if raw.startswith(b'"'):
        return raw[1:-1].replace(b'""', b'"')
    return raw


def _record_fields(record):
    """csv_safe.record_fields (the csv module on one raw record), its own refusal made a ValueError."""
    try:
        return csv_safe.record_fields(record)
    except csv.Error as exc:
        raise ValueError(f"the csv module cannot parse it: {exc}")


def _label(record, number):
    """A record's first cell and number, for a message about a record that cannot be parsed."""
    return f"{record.split(b',', 1)[0].decode('utf-8', 'replace')[:40]!r} (record {number})"


class Plan:
    """What a run would change. Built by find_matches; never touches the file."""

    def __init__(self, size, n_records, from_value, to_value):
        self.size = size
        self.n_records = n_records                 # header included
        self.from_value = from_value
        self.to_value = to_value
        self.matches = []                          # Match, in file order
        self.elsewhere = []                        # acq_ids: the --from text sits outside a matching cell
        self.by_instrument = Counter()

    @property
    def quoted(self):
        return sum(1 for m in self.matches if m.quoted)

    @property
    def delta(self):
        """The expected change of the file size in bytes."""
        to_len = len(self.to_value.encode("utf-8"))
        return sum(to_len - (m.end - m.start) for m in self.matches)


def find_matches(data, from_value, to_value):
    """Plan the edit: every record whose `operator` equals from_value. Raises RepairError.

    Only records that contain the --from bytes are examined closely; every other record is
    never parsed and is carried over untouched.
    """
    from_b = from_value.encode("utf-8")
    records = csv_safe.split_records(data)
    if not records:
        raise RepairError(f"{REGISTRY_FILENAME} is empty")
    try:
        header = _record_fields(records[0])
    except ValueError as exc:
        raise RepairError(f"the header of {REGISTRY_FILENAME} cannot be parsed ({exc}): refusing to edit.")
    if header != registry.REGISTRY_FIELDS:
        raise RepairError(
            f"{REGISTRY_FILENAME} header does not match ingest.registry.REGISTRY_FIELDS "
            f"({len(header)} columns found, {len(registry.REGISTRY_FIELDS)} expected): refusing to edit.")
    op = header.index("operator")
    ins = header.index("instrument")
    plan = Plan(len(data), len(records), from_value, to_value)
    offset = len(records[0])
    for number, rec in enumerate(records[1:], start=2):    # the header is record 1
        rec_start = offset
        offset += len(rec)
        if from_b not in rec:
            continue
        body, _term = _split_terminator(rec)
        try:
            fields = _record_fields(rec)
            spans = field_spans(body)
        except ValueError as exc:
            raise RepairError(f"{_label(rec, number)}: cannot locate its fields exactly ({exc}); "
                              f"refusing to guess.")
        acq = fields[0] if fields else _label(rec, number)
        if len(spans) != len(header) or len(fields) != len(header):
            raise RepairError(
                f"{acq} (record {number}): {len(fields)} fields by the csv module and {len(spans)} "
                f"by the byte scanner, {len(header)} expected; refusing to guess.")
        s, e = spans[op]
        raw = body[s:e]
        by_scanner = _unquote(raw) == from_b
        by_csv = fields[op] == from_value
        if by_scanner != by_csv:
            raise RepairError(f"{acq} (record {number}): the csv module and the byte scanner disagree "
                              f"about the operator cell {raw!r}; refusing to guess.")
        if not by_csv:
            plan.elsewhere.append(acq)                      # the text is in another column / part of a longer value
            continue
        plan.matches.append(Match(rec_start + s, rec_start + e, acq, fields[ins], raw.startswith(b'"')))
        plan.by_instrument[fields[ins]] += 1
        if from_b in body[:s] + body[e:]:
            plan.elsewhere.append(acq)                      # also elsewhere on the same row
    return plan


def splice(data, matches, to_value):
    """The new file: data with every matched span replaced by the bare to_value."""
    to_b = to_value.encode("utf-8")
    parts, prev = [], 0
    for m in matches:
        parts.append(data[prev:m.start])
        parts.append(to_b)
        prev = m.end
    parts.append(data[prev:])
    return b"".join(parts)


# ---- Files ---------------------------------------------------------------

def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def write_atomic(path, data):
    """Write data beside path, flush it to disk, then swap it in with os.replace."""
    tmp = f"{path}.tmp.{os.getpid()}"
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def _is_inside(child, parent):
    child = os.path.normcase(os.path.abspath(child))
    parent = os.path.normcase(os.path.abspath(parent))
    try:
        return os.path.commonpath([child, parent]) == parent
    except ValueError:                                     # different drives
        return False


# ---- Verification --------------------------------------------------------

def _diff_record(old, new, op, from_value, to_value):
    """None when two records differ in the operator cell only, as intended; else a reason."""
    old_body, old_term = _split_terminator(old)
    new_body, new_term = _split_terminator(new)
    if old_term != new_term:
        return "the line terminator changed"
    try:
        old_spans, new_spans = field_spans(old_body), field_spans(new_body)
        old_f, new_f = _record_fields(old), _record_fields(new)
    except ValueError as exc:
        return f"a record is not parseable ({exc})"
    if len(old_spans) != len(new_spans) or len(old_spans) <= op:
        return "the number of fields changed"
    for k, (a, b) in enumerate(zip(old_spans, new_spans)):
        if k != op and old_body[a[0]:a[1]] != new_body[b[0]:b[1]]:
            return f"column {k} changed"
    if _unquote(old_body[old_spans[op][0]:old_spans[op][1]]) != from_value.encode("utf-8"):
        return "the old operator cell is not the --from value"
    if new_body[new_spans[op][0]:new_spans[op][1]] != to_value.encode("utf-8"):
        return "the new operator cell is not the bare --to value"
    if [k for k in range(min(len(old_f), len(new_f))) if old_f[k] != new_f[k]] != [op] \
            or old_f[op] != from_value or new_f[op] != to_value:
        return "the csv module sees a change other than operator: from -> to"
    return None


def verify_repair(backup_path, registry_path, plan):
    """Re-read both files from disk and diff them. Returns a list of problems (empty = verified)."""
    problems = []
    old, cur = read_bytes(backup_path), read_bytes(registry_path)
    n = len(plan.matches)
    if len(cur) - len(old) != plan.delta:
        problems.append(f"the file size changed by {len(cur) - len(old)} bytes, expected {plan.delta}")
    if (cur.count(b"\r\n"), cur.count(b"\n"), cur[:3] == b"\xef\xbb\xbf") != \
            (old.count(b"\r\n"), old.count(b"\n"), old[:3] == b"\xef\xbb\xbf"):
        problems.append("the line terminators or the byte-order mark changed")
    old_recs, new_recs = csv_safe.split_records(old), csv_safe.split_records(cur)
    if len(old_recs) != len(new_recs):
        problems.append(f"the record count changed: {len(old_recs)} -> {len(new_recs)}")
        return problems
    op = registry.REGISTRY_FIELDS.index("operator")      # the header was checked against it in find_matches
    changed = 0
    for number, (a, b) in enumerate(zip(old_recs, new_recs), start=1):
        if a == b:
            continue
        why = _diff_record(a, b, op, plan.from_value, plan.to_value)
        if why:
            problems.append(f"record {number}: {why}")
            if len(problems) >= 10:
                problems.append("... (more)")
                return problems
        changed += 1
    if changed != n:
        problems.append(f"{changed} records differ from the backup, expected {n}")
    return problems


def restore_backup(backup_path, registry_path, expected_sha):
    """Put the backup back. True when the registry then hashes to expected_sha."""
    write_atomic(registry_path, read_bytes(backup_path))
    return sha256_file(registry_path) == expected_sha


# ---- Reporting -----------------------------------------------------------

def print_plan(plan, path):
    n = len(plan.matches)
    print(f"registry:      {path}")
    print(f"size:          {plan.size} bytes, {plan.n_records} records (header + {plan.n_records - 1} rows)")
    print(f"from:          {plan.from_value!r}")
    print(f"to:            {plan.to_value!r}")
    print(f"operator cells matching: {n}")
    if n:
        print("by instrument: " + ", ".join(f"{k or '(blank)'}={v}" for k, v in sorted(plan.by_instrument.items())))
        first = ", ".join(m.acq_id for m in plan.matches[:EXAMPLES_SHOWN])
        print(f"examples:      {first}" + (f" ... {plan.matches[-1].acq_id}" if n > EXAMPLES_SHOWN else ""))
        print(f"cells in file: {plan.quoted} quoted (the whole field, quotes included, is replaced), "
              f"{n - plan.quoted} bare")
        print(f"expected size after: {plan.size + plan.delta} bytes ({plan.delta:+d})")
    if plan.elsewhere:
        log(f"{len(plan.elsewhere)} record(s) hold the --from text outside a matching operator cell "
            f"(left untouched), e.g. {', '.join(plan.elsewhere[:EXAMPLES_SHOWN])}", "WARN")


# ---- Run -----------------------------------------------------------------

def apply_repair(args, nas_root, registries_dir, path, from_value, to_value):
    """The write. Returns the exit code."""
    backup_dir = os.path.abspath(args.backup_dir)
    if os.path.exists(backup_dir):
        raise RepairError(f"--backup-dir {backup_dir} already exists. A re-used backup folder once "
                          f"destroyed a snapshot here; give a folder that does not exist yet.")
    if _is_inside(backup_dir, nas_root):
        raise RepairError(f"--backup-dir {backup_dir} is inside the NAS root; the backup must be off the NAS.")

    # The lock covers the read the new file is built from, the swap, and the verification: an
    # ingest appending in between would otherwise be lost.
    with locking.registry_lock(registries_dir, log=log):
        data = read_bytes(path)
        plan = find_matches(data, from_value, to_value)
        print_plan(plan, path)
        n = len(plan.matches)
        if n != args.expect:
            raise RepairError(f"found {n} matching operator cells but --expect is {args.expect}: refusing "
                              f"to write anything.")
        if n == 0:
            print("nothing to change.")
            return 0
        sha_before = sha256_bytes(data)

        try:
            os.makedirs(backup_dir)
        except OSError as exc:
            raise RepairError(f"cannot create --backup-dir {backup_dir}: {exc}")
        backup = os.path.join(backup_dir, REGISTRY_FILENAME)
        shutil.copy2(path, backup)
        sha_backup, sha_source = sha256_file(backup), sha256_file(path)
        if not (sha_backup == sha_source == sha_before):
            raise RepairError(f"the backup copy does not verify (source {sha_source}, copy {sha_backup}, "
                              f"as read {sha_before}); nothing was written. See {backup_dir}.")
        log(f"backup: {backup} ({len(data)} bytes, SHA-256 verified)")

        new = splice(data, plan.matches, to_value)
        try:
            write_atomic(path, new)
            problems = verify_repair(backup, path, plan)
            if not problems and read_bytes(path) != new:
                problems.append("the file on disk is not the bytes that were written")
        except Exception as exc:  # noqa: BLE001 -- any failure is handled the same way below
            problems = [f"{type(exc).__name__}: {exc}"]
        if problems:
            for p in problems:
                log(p, "ERROR")
            if sha256_file(path) == sha_before:
                log("the registry is unchanged.", "ERROR")
                return 1
            log("verification FAILED: restoring the backup.", "ERROR")
            try:
                restored = restore_backup(backup, path, sha_before)
            except Exception as exc:  # noqa: BLE001
                log(f"the restore itself failed ({type(exc).__name__}: {exc})", "ERROR")
                restored = False
            if restored:
                log("the backup is restored; the registry is byte-identical to before.", "ERROR")
                return 1
            log(f"RESTORE FAILED: copy {backup} over {path} by hand.", "ERROR")
            return 3
        sha_after = sha256_file(path)
        size_after = os.path.getsize(path)

    print()
    print("APPLIED")
    print(f"rows_changed={n}")
    print(f"size_before={len(data)}")
    print(f"size_after={size_after}")
    print(f"sha256_before={sha_before}")
    print(f"sha256_after={sha_after}")
    print(f"backup={backup}")
    print(f"sha256_backup={sha_backup}")
    return 0


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(
        description="Change `operator` cells of registry_raw.csv from one exact value to another, "
                    "in bytes. Dry run unless --apply.")
    parser.add_argument("--nas-root", default=os.environ.get("GJESUS3_ROOT", "/mnt/gjesus3"),
                        help="Path to the NAS root (default: $GJESUS3_ROOT or /mnt/gjesus3).")
    parser.add_argument("--from", dest="from_value", default=PLACEHOLDER,
                        help="the exact operator value to replace (default: the MRI template instruction)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--to", dest="to_value", default=registry.OPERATOR_HOLD,
                       help=f"the new operator value (default: {registry.OPERATOR_HOLD})")
    group.add_argument("--to-blank", action="store_true",
                       help="write a blank operator (the same as --to \"\")")
    parser.add_argument("--apply", action="store_true", help="write (default: dry run, touches nothing)")
    parser.add_argument("--expect", type=int, metavar="N",
                        help="the number of cells that must match; --apply refuses unless it is exactly N")
    parser.add_argument("--backup-dir", metavar="PATH",
                        help="--apply: a folder that does NOT exist yet, off the NAS; registry_raw.csv is "
                             "copied there (SHA-256 verified) before anything is written")
    args = parser.parse_args(argv)

    from_value = args.from_value
    to_value = "" if args.to_blank else args.to_value
    try:
        check_values(from_value, to_value)
    except RepairError as exc:
        log(str(exc), "ERROR")
        return 2
    if args.expect is not None and args.expect < 0:
        log("--expect must be 0 or more.", "ERROR")
        return 2
    if args.apply and (args.expect is None or not args.backup_dir):
        log("--apply needs --expect N (the number of cells you expect to change) and --backup-dir "
            "<a folder that does not exist yet>.", "ERROR")
        return 2

    nas_root = args.nas_root
    registries_dir = os.path.join(nas_root, "registries")
    path = os.path.join(registries_dir, REGISTRY_FILENAME)
    if not os.path.isdir(nas_root) or not os.path.isfile(path):
        log(f"{REGISTRY_FILENAME} not found under '{registries_dir}'. Pass --nas-root <path>, or set "
            f"GJESUS3_ROOT.", "ERROR")
        return 2

    try:
        if args.apply:
            return apply_repair(args, nas_root, registries_dir, path, from_value, to_value)
        plan = find_matches(read_bytes(path), from_value, to_value)
        print("DRY RUN - nothing is written.")
        print_plan(plan, path)
        if args.expect is not None and len(plan.matches) != args.expect:
            raise RepairError(f"found {len(plan.matches)} matching operator cells but --expect is "
                              f"{args.expect}.")
        print("To write: re-run with --apply --expect "
              f"{len(plan.matches)} --backup-dir <a folder that does not exist yet, off the NAS>.")
        return 0
    except RepairError as exc:
        log(str(exc), "ERROR")
        return 1
    except locking.LockTimeout as exc:
        log(str(exc), "ERROR")
        return 1


if __name__ == "__main__":
    sys.exit(main())
