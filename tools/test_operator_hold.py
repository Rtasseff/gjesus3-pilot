#!/usr/bin/env python3
"""test_operator_hold.py -- the `operator` hold value `pending-claim`, both halves.

Covers STATUS section 0 D1(a) (Ryan, 2026-10-05): the 10,314 MRI `operator` cells that hold a
template instruction become the hold value "awaiting claim", the validator accepts it, and only
those cells change.

  1. validate_registries: `pending-claim` is accepted in `operator` (0 errors, 0 warnings, counted
     in one info line), is an ERROR when it is the whole value of any other column (stripped,
     any case; a note that merely mentions it is not reported), and the template-residue check
     still rejects the old placeholder.
  2. repair_operator_hold.py: dry run writes nothing; --apply changes exactly the matching
     `operator` cells (the placeholder is stored QUOTED, because it contains a comma), keeps
     no-BOM / CRLF and every other byte, verifies itself against a backup and restores it on a
     mismatch; and it refuses a count mismatch, an existing backup folder, a backup inside the
     NAS, a record it cannot parse exactly, and values it cannot edit safely.
  3. The row selectors (Ryan, 2026-10-07: historical internal MRI loaded without an operator gets
     the hold value): `--from-blank --instrument MRI --config-prefix P` changes a blank only inside
     the selectors (a CELL, PET or XMRI blank under the same prefix, and an MRI blank under another
     prefix, are untouched; `/` and `\\` are the same); a blank --from is refused without BOTH
     selectors; --expect still has to match; the verification rejects a change to an unselected
     record even when the count is right.

Temporary directories only: no NAS, no database, no pytest.

Run:  python tools/test_operator_hold.py      (exit 0 = pass)
"""

import contextlib
import csv
import hashlib
import io
import os
import subprocess
import sys
import tempfile

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import repair_operator_hold as rah  # noqa: E402
import validate_registries as vr  # noqa: E402
from ingest import locking, projects_registry, registry, subjects_table  # noqa: E402

HOLD = registry.OPERATOR_HOLD
PH = rah.PLACEHOLDER
PH_B = PH.encode()
TOOL = os.path.join(_THIS_DIR, "repair_operator_hold.py")

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok:   {msg}")


# ---- Builders -------------------------------------------------------------

def reg_row(acq, instrument="MRI", operator="", researcher="", notes="", **kw):
    """One registry row (a dict over REGISTRY_FIELDS) that passes the validator's other checks."""
    _, date, _code, _n = acq.split("-")
    row = dict.fromkeys(registry.REGISTRY_FIELDS, "")
    row.update({
        "acq_id": acq,
        "registration_datetime": "2026-06-13T07:05:18Z",
        "acquisition_datetime": f"{date[:4]}-{date[4:6]}-{date[6:]}T10:21:42.100+01:00",
        "data_ecosystem": "DICOM",
        "instrument": instrument,
        "instrument_model": "Bruker BioSpec 7T",
        "researcher": researcher,
        "operator": operator,
        "data_source": "internal",
        "canonical_path": f"/raw/DICOM/{date[:4]}/{date[:4]}-{date[4:6]}/{acq}/",
        "notes": notes,
    })
    row.update(kw)
    return row


def registry_bytes(rows, newline="\r\n", bom=False, final_newline=True):
    """registry_raw.csv bytes the way csv.writer produces them (as production's were)."""
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator=newline)
    w.writerow(registry.REGISTRY_FIELDS)
    for r in rows:
        w.writerow([r[f] for f in registry.REGISTRY_FIELDS])
    text = buf.getvalue()
    if not final_newline:
        text = text[:-len(newline)]
    data = text.encode("utf-8")
    return b"\xef\xbb\xbf" + data if bom else data


def write_nas(d, data, rows=None, name="nas"):
    """A minimal NAS root under d: registries/ with the three CSVs, and (when rows are given) the
    /raw/ folder of every row so the validator's folder check passes. Returns the root."""
    nas = os.path.join(d, name)
    reg = os.path.join(nas, "registries")
    os.makedirs(reg)
    with open(os.path.join(reg, "registry_raw.csv"), "wb") as f:
        f.write(data)
    for fn, fields in (("registry_projects.csv", projects_registry.PROJECT_REGISTRY_FIELDS),
                       ("registry_subjects.csv", subjects_table.SUBJECT_FIELDS)):
        with open(os.path.join(reg, fn), "w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow(fields)
    for r in rows or ():
        os.makedirs(os.path.join(nas, *r["canonical_path"].strip("/").split("/")), exist_ok=True)
    return nas


def reg_path(nas):
    return os.path.join(nas, "registries", "registry_raw.csv")


def read(path):
    with open(path, "rb") as f:
        return f.read()


def snapshot(root):
    """{relative path: sha256} of every file under root: proves nothing was added, removed or changed."""
    out = {}
    for base, _dirs, files in os.walk(root):
        for fn in files:
            p = os.path.join(base, fn)
            out[os.path.relpath(p, root)] = hashlib.sha256(read(p)).hexdigest()
    return out


def run_tool(*args):
    """rah.main in-process; returns (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            rc = rah.main(list(args))
        except SystemExit as exc:               # argparse's own refusals
            rc = exc.code
    return rc, out.getvalue(), err.getvalue()


def validate(nas):
    with contextlib.redirect_stderr(io.StringIO()):
        return vr.validate(nas, check_enrich=False)


def report(issues, n):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        vr.print_report(issues, n)
    return out.getvalue()


@contextlib.contextmanager
def patched(obj, name, value):
    old = getattr(obj, name)
    setattr(obj, name, value)
    try:
        yield
    finally:
        setattr(obj, name, old)


def main_rows():
    """The standard fixture: 5 placeholder rows among others, with the awkward cells of a real file."""
    return [
        reg_row("ACQ-20220118-MRI-001", operator=PH),
        reg_row("ACQ-20220118-MRI-002", operator="AINHIZE", researcher="AINHIZE"),
        reg_row("ACQ-20220118-MRI-003", operator=PH, notes='two lines\r\nwith a comma, and a "quote"'),
        reg_row("ACQ-20220119-MRI-001", operator=""),                              # blank = unknown
        reg_row("ACQ-20220119-MRI-002", operator=PH, notes="café / acentuación"),
        reg_row("ACQ-20220119-MRI-003", operator="Jguser", notes=f"mentions {PH} in free text"),
        reg_row("ACQ-20220120-MRI-001", operator=PH, notes=f"and also {PH} here"),
        reg_row("ACQ-20220120-MRI-002", instrument="MRI", operator="Marta"),
        reg_row("ACQ-20220120-MRI-003", operator=PH),
        reg_row("ACQ-20220121-ZWSI-001", instrument="ZWSI", data_ecosystem="MICROSCOPY", operator="AUA"),
    ]


N_MAIN = 5


def with_hold(rows):
    """The oracle: the same rows with every placeholder operator replaced by the hold value."""
    return [dict(r, operator=HOLD) if r["operator"] == PH else r for r in rows]


# ---- 1. the validator -------------------------------------------------------

def test_constant():
    print("the constant:")
    check(HOLD == "pending-claim", "registry.OPERATOR_HOLD is exactly 'pending-claim'")
    check(vr.TEMPLATE_RESIDUE_RE.search(HOLD) is None,
          "the token carries no template syntax (so the residue check needs no exception)")
    check(vr.TEMPLATE_RESIDUE_RE.search(PH) is not None, "the old placeholder is still template residue")


def test_validator_accepts_hold_in_operator():
    print("validate_registries accepts the hold value in `operator`:")
    rows = [reg_row("ACQ-20220118-MRI-001", operator=HOLD),
            reg_row("ACQ-20220118-MRI-002", operator=HOLD, researcher="AINHIZE"),
            reg_row("ACQ-20220118-MRI-003", operator="AINHIZE"),
            reg_row("ACQ-20220118-MRI-004", operator="")]
    with tempfile.TemporaryDirectory() as d:
        nas = write_nas(d, registry_bytes(rows), rows)
        issues, n = validate(nas)
        check(n == 4 and not issues.errors, f"0 errors (got {[m for _a, m in issues.errors]})")
        check(not issues.warnings, "0 warnings: the info count is not in the warning channel")
        check(issues.operator_hold == 2, "exactly the 2 hold rows are counted")
        text = report(issues, n)
        check(f"operator awaiting claim ({HOLD}): 2" in text.splitlines(),
              "print_report shows 'operator awaiting claim (pending-claim): 2'")
        check("WARN" not in text and "ERROR" not in text, "and it is not worded as a finding")

    rows = [reg_row("ACQ-20220118-MRI-001", operator="AINHIZE")]
    with tempfile.TemporaryDirectory() as d:
        nas = write_nas(d, registry_bytes(rows), rows)
        issues, n = validate(nas)
        check(not issues.errors and issues.operator_hold == 0, "no hold rows: count 0, 0 errors")
        check(f"operator awaiting claim ({HOLD}): 0" in report(issues, n).splitlines(),
              "the info line still prints, with 0")


def test_validator_errors_on_hold_elsewhere():
    print("validate_registries rejects the hold value as the whole value of another column:")
    rows = [reg_row("ACQ-20220118-MRI-001", operator=HOLD, researcher=HOLD),
            reg_row("ACQ-20220118-MRI-002", operator=HOLD, notes=" Pending-Claim "),
            reg_row("ACQ-20220118-MRI-003", operator=HOLD)]
    with tempfile.TemporaryDirectory() as d:
        nas = write_nas(d, registry_bytes(rows), rows)
        issues, _n = validate(nas)
        errs = [(a, m) for a, m in issues.errors]
        check(len(errs) == 2, f"exactly 2 ERRORs (got {len(errs)})")
        check(any(a == "ACQ-20220118-MRI-001" and "'researcher'" in m for a, m in errs),
              "an ERROR on a `researcher` cell that is the token, tagged with the acq id")
        check(any(a == "ACQ-20220118-MRI-002" and "'notes'" in m for a, m in errs),
              "an ERROR on a `notes` cell that is ' Pending-Claim ' (stripped, whatever the case)")
        check(not any(a == "ACQ-20220118-MRI-003" for a, _m in errs), "a clean hold row is not reported")
        check(issues.operator_hold == 3, "all 3 operator cells still count as hold rows")

    iss = vr.Issues()
    vr.check_operator_hold({"operator": HOLD, "researcher": "", "notes": None, None: ["x"]}, "A", iss)
    check(not iss.errors and iss.operator_hold == 1,
          "a blank cell, a None and surplus fields (a list under key None) do not crash it")


def test_validator_ignores_a_note_that_mentions_the_hold():
    print("validate_registries does not report a note that merely mentions the hold value:")
    rows = [reg_row("ACQ-20220118-MRI-001", operator="Irene", notes="claimed by Irene 2026-11; was pending-claim"),
            reg_row("ACQ-20220118-MRI-002", operator="Marta", notes=f"{HOLD.upper()} until the claim round ended"),
            reg_row("ACQ-20220118-MRI-003", operator=HOLD)]
    with tempfile.TemporaryDirectory() as d:
        nas = write_nas(d, registry_bytes(rows), rows)
        issues, _n = validate(nas)
        check(not issues.errors, f"0 errors (got {[m for _a, m in issues.errors]})")
        check(not issues.warnings, "0 warnings")
        check(issues.operator_hold == 1, "only the one operator cell is counted; the mentions are not")

    # The rule, cell by cell: a cell is reported only when, stripped, it IS the token.
    cases = ((HOLD, True), (" Pending-Claim ", True), (HOLD.upper(), True), ("\t" + HOLD + "\r\n", True),
             ("claimed by Irene 2026-11; was pending-claim", False), (HOLD + " and more", False),
             ("was " + HOLD, False), ("not-" + HOLD, False), (HOLD + "s", False), ("", False), ("   ", False))
    for value, flagged in cases:
        iss = vr.Issues()
        vr.check_operator_hold({"operator": "", "notes": value}, "A", iss)
        check(bool(iss.errors) == flagged,
              f"{value!r} in another column: {'an ERROR' if flagged else 'not reported'}")


def test_residue_check_unchanged():
    print("the template-residue check is not weakened:")
    iss = vr.Issues()
    vr.check_template_residue({"operator": PH}, "A", iss)
    check(len(iss.errors) == 1 and "'operator'" in iss.errors[0][1], "the placeholder is still an ERROR")
    iss = vr.Issues()
    vr.check_template_residue({"operator": HOLD, "notes": "a & b"}, "A", iss)
    check(not iss.errors, "the hold value passes it on its own merits")

    rows = [reg_row("ACQ-20220118-MRI-001", operator=PH), reg_row("ACQ-20220118-MRI-002", operator=HOLD)]
    with tempfile.TemporaryDirectory() as d:
        nas = write_nas(d, registry_bytes(rows), rows)
        issues, _n = validate(nas)
        check(len(issues.errors) == 1 and issues.errors[0][0] == "ACQ-20220118-MRI-001",
              "a registry with the placeholder and a hold row: only the placeholder is an ERROR")
        check(issues.operator_hold == 1, "and only the hold row is counted")


# ---- 2. the repair tool: the parser ---------------------------------------

def test_field_spans():
    print("field_spans (the strict byte scanner):")
    cases = {
        b"a,b,c": [b"a", b"b", b"c"],
        b"a,,c": [b"a", b"", b"c"],
        b"a,b,": [b"a", b"b", b""],
        b",": [b"", b""],
        b"": [b""],
        b'"x, y",b': [b'"x, y"', b"b"],
        b'a,"<REQUIRED - set via mri-ingest --operator, or replace here>",c':
            [b"a", b'"' + PH_B + b'"', b"c"],
        b'"a""b",c': [b'"a""b"', b"c"],
        b'"a""",c': [b'"a"""', b"c"],
        b'"",c': [b'""', b"c"],
        b'"one\r\ntwo",c': [b'"one\r\ntwo"', b"c"],
        b'a,"x"': [b"a", b'"x"'],
    }
    for body, want in cases.items():
        spans = rah.field_spans(body)
        got = [body[s:e] for s, e in spans]
        check(got == want, f"{body!r} -> {want!r}")
        if body:        # (the csv module reads an empty line as no fields at all)
            csv_fields = next(csv.reader([body.decode()]))
            check([rah._unquote(x).decode() for x in got] == csv_fields, f"  the csv module agrees on {body!r}")
    for bad, why in ((b'"abc"def,x', "text after a closing quote"), (b'a,"unterminated', "unterminated"),
                     (b'a,"x""', "unterminated (an escaped quote, then the end)"),
                     (b'a,5" thick,b', "a quote inside an unquoted field"),
                     (b'a, "b"', "a quote after a leading space")):
        try:
            rah.field_spans(bad)
            check(False, f"{bad!r} is refused ({why})")
        except ValueError:
            check(True, f"{bad!r} is refused ({why})")


# ---- 3. the repair tool: dry run ---------------------------------------------

def test_dry_run_writes_nothing():
    print("repair_operator_hold: the dry run writes nothing:")
    rows = main_rows()
    data = registry_bytes(rows)
    with tempfile.TemporaryDirectory() as d:
        nas = write_nas(d, data, rows)
        before, mtime = snapshot(d), os.stat(reg_path(nas)).st_mtime_ns
        entered = []
        orig = locking.registry_lock

        @contextlib.contextmanager
        def counting(*a, **k):
            entered.append(1)
            with orig(*a, **k) as p:
                yield p

        bk = os.path.join(d, "bk")
        with patched(locking, "registry_lock", counting):
            rc, out, err = run_tool("--nas-root", nas, "--backup-dir", bk)
        check(rc == 0, f"exit 0 (got {rc}; {err.strip()[-200:]})")
        check(f"operator cells matching: {N_MAIN}" in out, f"reports the count ({N_MAIN})")
        check("by instrument: MRI=5" in out, "reports the instruments (all MRI)")
        check("ACQ-20220118-MRI-001" in out and "ACQ-20220120-MRI-003" in out, "shows example ACQ-IDs")
        delta = N_MAIN * (len(HOLD) - (len(PH) + 2))
        check(f"expected size after: {len(data) + delta} bytes ({delta:+d})" in out,
              f"reports the expected byte delta ({delta:+d}: the cells are quoted, so len+2)")
        check(f"{N_MAIN} quoted" in out, "says the cells are quoted in the file")
        check("outside a matching operator cell" in err, "warns about the text found in other cells")
        check(snapshot(d) == before and os.stat(reg_path(nas)).st_mtime_ns == mtime,
              "no file added, removed or changed (not even the mtime)")
        check(not entered, "no lock was taken")
        check(not os.path.exists(bk), "--backup-dir was not created")
        rc, out, _err = run_tool("--nas-root", nas, "--expect", str(N_MAIN))
        check(rc == 0, "--expect with the right count: still fine")
        rc, out, _err = run_tool("--nas-root", nas, "--expect", "4")
        check(rc == 1 and snapshot(d) == before, "--expect with the wrong count: refused, nothing written")


def test_cli_subprocess():
    print("repair_operator_hold: as a command:")
    rows = main_rows()
    with tempfile.TemporaryDirectory() as d:
        nas = write_nas(d, registry_bytes(rows), rows)
        before = snapshot(d)
        r = subprocess.run([sys.executable, TOOL, "--nas-root", nas], cwd=d, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        check(r.returncode == 0 and f"operator cells matching: {N_MAIN}" in r.stdout,
              f"a dry run exits 0 and reports {N_MAIN} (rc {r.returncode})")
        r = subprocess.run([sys.executable, TOOL, "--nas-root", nas, "--apply"], cwd=d, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        check(r.returncode == 2 and snapshot(d) == before, "--apply without --expect: exit 2, nothing written")


# ---- 4. the repair tool: the write ---------------------------------------------

def test_apply_refusals():
    print("repair_operator_hold: --apply refuses before writing:")
    rows = main_rows()
    with tempfile.TemporaryDirectory() as d:
        nas = write_nas(d, registry_bytes(rows), rows)
        before = snapshot(d)
        bk = os.path.join(d, "bk")
        for args, why in ((["--apply"], "no --expect and no --backup-dir"),
                          (["--apply", "--expect", "5"], "no --backup-dir"),
                          (["--apply", "--backup-dir", bk], "no --expect")):
            rc, _o, _e = run_tool("--nas-root", nas, *args)
            check(rc == 2 and snapshot(d) == before and not os.path.exists(bk), f"{why}: exit 2, nothing written")
        for n in (4, 6, 0):
            rc, _o, err = run_tool("--nas-root", nas, "--apply", "--expect", str(n), "--backup-dir", bk)
            check(rc == 1 and snapshot(d) == before and not os.path.exists(bk),
                  f"--expect {n} but 5 found: refused, no backup made, nothing written")
        check("found 5 matching" in err, "and the message says what was found")

        os.makedirs(bk)
        with open(os.path.join(bk, "keep.txt"), "wb") as f:
            f.write(b"an earlier snapshot")
        before = snapshot(d)
        rc, _o, err = run_tool("--nas-root", nas, "--apply", "--expect", "5", "--backup-dir", bk)
        check(rc == 1 and snapshot(d) == before, "an existing --backup-dir: refused, nothing in it touched")
        check("already exists" in err, "and it says why")

        inside = os.path.join(nas, "backups")
        rc, _o, err = run_tool("--nas-root", nas, "--apply", "--expect", "5", "--backup-dir", inside)
        check(rc == 1 and not os.path.exists(inside) and "off the NAS" in err,
              "a --backup-dir inside the NAS root: refused")


def test_apply_happy_path():
    print("repair_operator_hold: --apply changes exactly the matching cells:")
    rows = main_rows()
    # A legacy non-UTF-8 byte in a row nobody edits must survive byte for byte.
    rows[7]["notes"] = "legacy @LATIN1@"
    data = registry_bytes(rows).replace(b"@LATIN1@", b"caf\xe9")
    expected = registry_bytes(with_hold(rows)).replace(b"@LATIN1@", b"caf\xe9")
    with tempfile.TemporaryDirectory() as d:
        nas = write_nas(d, data, rows)
        bk = os.path.join(d, "backups", "operator_hold")
        state = {"held": False, "writes": []}
        orig_lock, orig_write = locking.registry_lock, rah.write_atomic

        @contextlib.contextmanager
        def tracking(*a, **k):
            with orig_lock(*a, **k) as p:
                state["held"] = True
                try:
                    yield p
                finally:
                    state["held"] = False

        def tracking_write(path, buf):
            state["writes"].append(state["held"])
            return orig_write(path, buf)

        with patched(locking, "registry_lock", tracking), patched(rah, "write_atomic", tracking_write):
            rc, out, err = run_tool("--nas-root", nas, "--apply", "--expect", str(N_MAIN), "--backup-dir", bk)
        check(rc == 0, f"exit 0 (got {rc}; {err.strip()[-300:]})")
        new = read(reg_path(nas))
        check(new == expected, "the file is exactly the same rows with only those operator cells replaced "
                               "(compared with an independent csv.writer rebuild)")
        check(new[:3] != b"\xef\xbb\xbf" and data[:3] != b"\xef\xbb\xbf", "no BOM, before or after")
        crlf = new.count(b"\r\n")
        check(new.count(b"\n") == crlf == data.count(b"\r\n") == data.count(b"\n"),
              f"every line terminator is still CRLF ({crlf} of them, as before)")
        delta = N_MAIN * (len(HOLD) - (len(PH) + 2))
        check(len(new) - len(data) == delta, f"the size changed by exactly {delta} bytes")
        check(new.count(PH_B) == 2, "the placeholder text left in other cells (free text) is untouched: 2 left")
        check(b"caf\xe9" in new, "a non-UTF-8 byte elsewhere survived")
        check(os.path.isfile(os.path.join(bk, "registry_raw.csv")) and read(os.path.join(bk, "registry_raw.csv")) == data,
              "the backup is a byte-identical copy of the old registry")
        sha = {k: v for k, v in (ln.split("=", 1) for ln in out.splitlines() if "=" in ln
                                 and ln.split("=", 1)[0].isidentifier())}
        check(sha.get("rows_changed") == str(N_MAIN), "summary: rows_changed")
        check(sha.get("size_before") == str(len(data)) and sha.get("size_after") == str(len(new)),
              "summary: size_before / size_after")
        check(sha.get("sha256_before") == hashlib.sha256(data).hexdigest()
              and sha.get("sha256_after") == hashlib.sha256(new).hexdigest()
              and sha.get("sha256_backup") == hashlib.sha256(data).hexdigest(), "summary: the three SHA-256s")
        check(state["writes"] == [True], "the registry was written once, while the lock was held")
        check(not os.path.exists(os.path.join(nas, "registries", ".registry.lock")), "the lock is released")
        leftovers = [f for f in os.listdir(os.path.join(nas, "registries")) if ".tmp" in f]
        check(not leftovers, "no temp file is left behind")
        others = {k: v for k, v in snapshot(d).items() if k.startswith("nas") and "registry_raw.csv" not in k}
        check(set(others) == {os.path.join("nas", "registries", "registry_projects.csv"),
                              os.path.join("nas", "registries", "registry_subjects.csv")},
              "nothing else under the NAS root was added")

        # The repaired file validates: no residue left in `operator`, the hold counted.
        issues, _n = validate(nas)
        residue = [m for _a, m in issues.errors if m.startswith("column 'operator' still contains")]
        check(issues.operator_hold == N_MAIN and not residue,
              f"the validator counts {N_MAIN} hold rows and finds no residue in `operator`")

        # Idempotent: a second run finds nothing.
        before = snapshot(d)
        rc, _o, err = run_tool("--nas-root", nas, "--apply", "--expect", str(N_MAIN),
                               "--backup-dir", os.path.join(d, "backups", "again"))
        check(rc == 1 and snapshot(d) == before, "a second --apply --expect 5: refused (0 found), nothing written")
        rc, out, _e = run_tool("--nas-root", nas, "--apply", "--expect", "0",
                               "--backup-dir", os.path.join(d, "backups", "again"))
        check(rc == 0 and "nothing to change" in out and snapshot(d) == before
              and not os.path.exists(os.path.join(d, "backups", "again")),
              "--expect 0: nothing to change, exit 0, no backup folder made")


def test_apply_bare_cells_and_blank():
    print("repair_operator_hold: bare cells, --to-blank, BOM, LF files, a last record with no newline:")
    rows = [reg_row("ACQ-20220118-MRI-001", operator=HOLD),
            reg_row("ACQ-20220118-MRI-002", operator="AINHIZE"),
            reg_row("ACQ-20220118-MRI-003", operator="", notes="a, b"),
            reg_row("ACQ-20220118-MRI-004", operator=HOLD, notes="the last record")]
    blank = [dict(r, operator="") if r["operator"] == HOLD else r for r in rows]
    for label, kw in (("CRLF", {}), ("a BOM", {"bom": True}), ("LF line endings", {"newline": "\n"}),
                      ("no final newline", {"final_newline": False})):
        data = registry_bytes(rows, **kw)
        expected = registry_bytes(blank, **kw)
        with tempfile.TemporaryDirectory() as d:
            nas = write_nas(d, data, rows)
            bk = os.path.join(d, "bk")
            rc, out, err = run_tool("--nas-root", nas, "--from", HOLD, "--to-blank", "--apply",
                                    "--expect", "2", "--backup-dir", bk)
            new = read(reg_path(nas))
            check(rc == 0 and new == expected, f"{label}: {HOLD} -> blank in the 2 cells, every other byte as before "
                                                f"(rc {rc} {err.strip()[-160:]})")
            check(len(new) - len(data) == -2 * len(HOLD), f"{label}: the size changed by exactly {-2 * len(HOLD)}")
            check(read(os.path.join(bk, "registry_raw.csv")) == data, f"{label}: the backup is the old file")
    with tempfile.TemporaryDirectory() as d:
        nas = write_nas(d, registry_bytes(rows), rows)
        before = snapshot(d)
        rc, out, _e = run_tool("--nas-root", nas, "--from", HOLD, "--to", "")
        check(rc == 0 and "to:            ''" in out and "operator cells matching: 2" in out
              and "2 bare" in out, "--to \"\" is the same as --to-blank (dry run: 2 bare cells)")
        check(snapshot(d) == before, "and the dry run wrote nothing")


def test_unparseable_records_refused():
    print("repair_operator_hold: a record it cannot parse exactly is refused, not guessed at:")
    rows = [reg_row("ACQ-20220118-MRI-001", operator=PH, notes="plain"),
            reg_row("ACQ-20220118-MRI-002", operator=PH),
            reg_row("ACQ-20220118-MRI-003", operator="AINHIZE", notes="other")]
    data = registry_bytes(rows)
    quoted = b'"' + PH_B + b'",'
    damaged = {
        "text after the closing quote": data.replace(quoted, b'"' + PH_B + b'"x,', 1),
        "a short record (27 fields)": data.replace(b",internal,", b",", 1),
        "a stray quote in an unquoted cell": data.replace(b",plain\r\n", b',5" thick\r\n', 1),
    }
    for why, bad in damaged.items():
        check(bad != data, f"(fixture: {why})")
        with tempfile.TemporaryDirectory() as d:
            nas = write_nas(d, bad, rows)
            before = snapshot(d)
            bk = os.path.join(d, "bk")
            rc, _o, err = run_tool("--nas-root", nas)
            check(rc == 1 and "refusing" in err, f"{why}: the dry run refuses")
            rc, _o, err = run_tool("--nas-root", nas, "--apply", "--expect", "2", "--backup-dir", bk)
            check(rc == 1 and snapshot(d) == before and not os.path.exists(bk),
                  f"{why}: --apply refuses, no backup made, nothing written")

    # A header that is not the schema is never edited.
    with tempfile.TemporaryDirectory() as d:
        nas = write_nas(d, data.replace(b"researcher,operator,", b"researcher,operador,", 1), rows)
        before = snapshot(d)
        rc, _o, err = run_tool("--nas-root", nas, "--apply", "--expect", "2", "--backup-dir", os.path.join(d, "bk"))
        check(rc == 1 and "header does not match" in err and snapshot(d) == before,
              "a header that is not REGISTRY_FIELDS: refused")


def test_arguments_refused():
    print("repair_operator_hold: values it cannot edit safely are refused:")
    rows = main_rows()
    with tempfile.TemporaryDirectory() as d:
        nas = write_nas(d, registry_bytes(rows), rows)
        before = snapshot(d)
        for args, why in ((["--from", ""], "a blank --from (would bulk-fill 'unknown')"),
                          (["--to", "a,b"], "--to with a comma"),
                          (["--to", 'x"y'], "--to with a quote"),
                          (["--to", "x\ny"], "--to with a newline"),
                          (["--from", 'a"b'], "--from with a quote"),
                          (["--from", HOLD, "--to", HOLD], "--from == --to"),
                          (["--to", "x", "--to-blank"], "--to together with --to-blank"),
                          (["--expect", "-1"], "a negative --expect")):
            rc, _o, _e = run_tool("--nas-root", nas, *args)
            check(rc == 2 and snapshot(d) == before, f"{why}: exit 2")
        rc, _o, _e = run_tool("--nas-root", os.path.join(d, "no-such-nas"))
        check(rc == 2, "a NAS root without a registry: exit 2")


def test_verify_repair_catches_tampering():
    print("repair_operator_hold: the post-write verification is not vacuous:")
    rows = main_rows()
    data = registry_bytes(rows)
    plan = rah.find_matches(data, PH, HOLD)
    good = rah.splice(data, plan.matches, HOLD)

    def problems(new):
        with tempfile.TemporaryDirectory() as d:
            old_p, new_p = os.path.join(d, "old.csv"), os.path.join(d, "new.csv")
            for p, b in ((old_p, data), (new_p, new)):
                with open(p, "wb") as f:
                    f.write(b)
            return rah.verify_repair(old_p, new_p, plan)

    check(problems(good) == [], "the correct result verifies")
    first_end = data.index(b"\r\n") + 2
    tampered = {
        "a same-size change in another column": good.replace(b"internal", b"internaX", 1),
        "a wrong new operator value": good.replace(HOLD.encode(), b"pending-claiM", 1),
        "the operator of a row that should not change": good.replace(b"AINHIZE,AINHIZE", b"AINHIZE,AINHIZX", 1),
        "a line terminator turned into LF": good.replace(b"\r\n", b"\n", 1),
        "a byte-order mark added": b"\xef\xbb\xbf" + good,
        "the last record dropped": good[:good.rindex(b"\r\n", 0, len(good) - 2) + 2],
        "a record duplicated": good + good[first_end:good.index(b"\r\n", first_end) + 2],
        "one cell left unchanged": rah.splice(data, plan.matches[:-1], HOLD),
        "the placeholder blanked instead of replaced": rah.splice(data, plan.matches, ""),
    }
    for why, bad in tampered.items():
        check(bad != good and problems(bad) != [], f"caught: {why}")


def test_failed_verification_restores_the_backup():
    print("repair_operator_hold: a failed verification restores the backup:")
    rows = main_rows()
    data = registry_bytes(rows)
    orig_splice = rah.splice

    def damaging_splice(buf, matches, to_value):
        out = bytearray(orig_splice(buf, matches, to_value))
        out[-3] ^= 0x01                                    # one byte of the last record changes
        return bytes(out)

    def short_splice(buf, matches, to_value):             # the last match is silently skipped
        return orig_splice(buf, matches[:-1], to_value)

    for label, fake in (("an extra byte changed", damaging_splice), ("one cell left unchanged", short_splice)):
        with tempfile.TemporaryDirectory() as d:
            nas = write_nas(d, data, rows)
            bk = os.path.join(d, "bk")
            with patched(rah, "splice", fake):
                rc, _o, err = run_tool("--nas-root", nas, "--apply", "--expect", str(N_MAIN), "--backup-dir", bk)
            check(rc == 1, f"{label}: exit 1 (got {rc})")
            check(read(reg_path(nas)) == data, f"{label}: the registry is byte-identical to before (restored)")
            check("restoring the backup" in err, f"{label}: it says it restored")
            check(read(os.path.join(bk, "registry_raw.csv")) == data, f"{label}: the backup is kept")
            check(not os.path.exists(os.path.join(nas, "registries", ".registry.lock")), f"{label}: the lock is released")

    with tempfile.TemporaryDirectory() as d:                # a restore that fails too
        nas = write_nas(d, data, rows)

        def failing_restore(*_a, **_k):
            raise OSError("disk says no")

        with patched(rah, "splice", damaging_splice), patched(rah, "restore_backup", failing_restore):
            rc, _o, err = run_tool("--nas-root", nas, "--apply", "--expect", str(N_MAIN),
                                   "--backup-dir", os.path.join(d, "bk"))
        check(rc == 3 and "RESTORE FAILED" in err, "a failed restore: exit 3, with the manual instruction")

    with tempfile.TemporaryDirectory() as d:                # a write that fails outright
        nas = write_nas(d, data, rows)

        def refusing_write(*_a, **_k):
            raise PermissionError("file is open elsewhere")

        with patched(rah, "write_atomic", refusing_write):
            rc, _o, err = run_tool("--nas-root", nas, "--apply", "--expect", str(N_MAIN),
                                   "--backup-dir", os.path.join(d, "bk"))
        check(rc == 1 and read(reg_path(nas)) == data and "unchanged" in err,
              "a write that fails: exit 1, the registry untouched")


def test_backup_must_verify():
    print("repair_operator_hold: an unverified backup stops the run before anything is written:")
    rows = main_rows()
    data = registry_bytes(rows)
    orig_copy = rah.shutil.copy2

    def bad_copy(src, dst, **kw):
        orig_copy(src, dst, **kw)
        with open(dst, "ab") as f:
            f.write(b"x")
        return dst

    with tempfile.TemporaryDirectory() as d:
        nas = write_nas(d, data, rows)
        with patched(rah.shutil, "copy2", bad_copy):
            rc, _o, err = run_tool("--nas-root", nas, "--apply", "--expect", str(N_MAIN),
                                   "--backup-dir", os.path.join(d, "bk"))
        check(rc == 1 and read(reg_path(nas)) == data and "does not verify" in err,
              "a corrupt backup copy: refused, the registry untouched")


# ---- 5. row selectors: the general rule for historical MRI (Ryan, 2026-10-07) -----------

PFX_A = "tools/configs/drive3_mri/"
PFX_B = "tools/configs/mri_1019_kgjesus_2021_"


def selector_rows():
    """Blank operators of every kind; only the internal MRI ones under PFX_A / PFX_B are to change."""
    return [
        reg_row("ACQ-20190909-MRI-001", operator="", ingest_config=PFX_A + "drive3_mri_M01_0118.yaml"),   # yes
        reg_row("ACQ-20190909-MRI-002", operator="", notes="a, b",
                ingest_config="tools\\configs\\drive3_mri\\drive3_mri_M02.yaml"),                           # yes (backslashes)
        reg_row("ACQ-20210420-MRI-001", operator="", ingest_config=PFX_B + "mes02.yaml"),                 # yes
        reg_row("ACQ-20190909-MRI-003", operator="Irene", ingest_config=PFX_A + "x.yaml"),                # set: no
        reg_row("ACQ-20190909-MRI-004", operator=HOLD, ingest_config=PFX_A + "x.yaml"),                   # hold: no
        reg_row("ACQ-20190909-XMRI-001", instrument="XMRI", operator="", data_source="collaborator:CNIC",
                ingest_config=PFX_A + "drive3_mri_P01_cnic_heards.yaml"),                                  # XMRI: no
        reg_row("ACQ-20221024-CELL-001", instrument="CELL", data_ecosystem="MICROSCOPY", operator="",
                ingest_config=PFX_A + "odd.yaml"),                                                         # CELL: no
        reg_row("ACQ-20220518-PET-001", instrument="PET", operator="",
                ingest_config="tools/configs/drive3_petct/drive3_petct_snapshot.yaml"),                    # PET: no
        reg_row("ACQ-20200304-MRI-001", operator="", ingest_config="tools/configs/drives_2026-09/dicom/b.yaml"),  # other prefix: no
        reg_row("ACQ-20200304-MRI-002", operator="", ingest_config="tools/configs/mri_1019_other.yaml"),  # near-miss prefix: no
        reg_row("ACQ-20210420-MRI-002", operator="", ingest_config=PFX_B + "mes06.yaml"),                 # yes, the last record
    ]


N_SEL = 4
SEL_ARGS = ("--from-blank", "--instrument", "MRI", "--config-prefix", PFX_A, "--config-prefix", PFX_B)


def selected_oracle(rows):
    """The expected rows: the hold value on exactly the 4 selected blank cells."""
    yes = {"ACQ-20190909-MRI-001", "ACQ-20190909-MRI-002", "ACQ-20210420-MRI-001", "ACQ-20210420-MRI-002"}
    return [dict(r, operator=HOLD) if r["acq_id"] in yes else r for r in rows]


def test_blank_from_needs_both_selectors():
    print("repair_operator_hold: a blank --from is refused without BOTH selectors:")
    rows = selector_rows()
    with tempfile.TemporaryDirectory() as d:
        nas = write_nas(d, registry_bytes(rows), rows)
        before = snapshot(d)
        for args, why in ((["--from-blank"], "--from-blank alone"),
                          (["--from", ""], "--from \"\" alone"),
                          (["--from-blank", "--instrument", "MRI"], "--from-blank with --instrument only"),
                          (["--from-blank", "--config-prefix", PFX_A], "--from-blank with --config-prefix only"),
                          (["--from", "", "--config-prefix", PFX_A], "--from \"\" with --config-prefix only"),
                          (["--from-blank", "--instrument", "MRI", "--config-prefix", " "], "a blank --config-prefix"),
                          (["--from-blank", "--from", "x"], "--from-blank together with --from")):
            rc, _o, err = run_tool("--nas-root", nas, *args)
            check(rc == 2 and snapshot(d) == before, f"{why}: exit 2, nothing written")
        rc, _o, err = run_tool("--nas-root", nas, "--from-blank", "--instrument", "MRI", "--apply", "--expect", "4",
                               "--backup-dir", os.path.join(d, "bk"))
        check(rc == 2 and snapshot(d) == before and not os.path.exists(os.path.join(d, "bk")),
              "--apply with --instrument only: exit 2, no backup made, nothing written")
        check("BOTH row selectors" in err, "and the message names the two selectors")


def test_selectors_dry_run():
    print("repair_operator_hold: the selectors pick only internal MRI blanks under the prefixes (dry run):")
    rows = selector_rows()
    with tempfile.TemporaryDirectory() as d:
        nas = write_nas(d, registry_bytes(rows), rows)
        before = snapshot(d)
        rc, out, err = run_tool("--nas-root", nas, *SEL_ARGS)
        check(rc == 0, f"exit 0 (got {rc}; {err.strip()[-200:]})")
        check(f"operator cells matching: {N_SEL}" in out, f"{N_SEL} cells selected")
        check(f"by prefix:   {2:6d}  {PFX_A}" in out,
              "reported per prefix: drive3_mri/ 2 (one spelled with forward slashes, one with backslashes)")
        check(f"by prefix:   {2:6d}  {PFX_B}" in out, "reported per prefix: the 1019 family 2")
        check("by instrument: MRI=4" in out, "all MRI")
        check("CELL=1" in out and "XMRI=1" in out and "left alone" in out,
              "the CELL and XMRI blanks under the same prefix are reported as left alone")
        check("selectors:     instrument == 'MRI' AND ingest_config starts with one of" in out, "the selectors are printed")
        check("outside a matching operator cell" not in err, "a blank --from raises no 'text elsewhere' warning")
        check(snapshot(d) == before, "nothing written")
        rc, _o, _e = run_tool("--nas-root", nas, *SEL_ARGS, "--expect", "5")
        check(rc == 1 and snapshot(d) == before, "--expect with the wrong count: refused")
        # a prefix given with backslashes selects forward-slash configs, and vice versa
        rc, out, _e = run_tool("--nas-root", nas, "--from-blank", "--instrument", "MRI",
                               "--config-prefix", PFX_A.replace("/", "\\"))
        check(rc == 0 and "operator cells matching: 2" in out, "a backslash prefix selects both spellings (2)")
        # the selector is exact on instrument: XMRI alone
        rc, out, _e = run_tool("--nas-root", nas, "--from-blank", "--instrument", "XMRI", "--config-prefix", PFX_A)
        check(rc == 0 and "operator cells matching: 1" in out and "by instrument: XMRI=1\n" in out,
              "--instrument XMRI selects the XMRI row only (exact match, not a substring)")


def test_selectors_apply():
    print("repair_operator_hold: --apply with selectors changes exactly the selected blank cells:")
    rows = selector_rows()
    data = registry_bytes(rows)
    expected = registry_bytes(selected_oracle(rows))
    with tempfile.TemporaryDirectory() as d:
        nas = write_nas(d, data, rows)
        bk = os.path.join(d, "bk")
        rc, _o, err = run_tool("--nas-root", nas, *SEL_ARGS, "--apply", "--expect", "3", "--backup-dir", bk)
        check(rc == 1 and read(reg_path(nas)) == data and not os.path.exists(bk),
              "--expect 3 but 4 selected: refused, no backup, nothing written")
        rc, out, err = run_tool("--nas-root", nas, *SEL_ARGS, "--apply", "--expect", str(N_SEL), "--backup-dir", bk)
        new = read(reg_path(nas))
        check(rc == 0, f"exit 0 (got {rc}; {err.strip()[-300:]})")
        check(new == expected, "only the 4 selected cells changed (compared with an independent csv.writer rebuild)")
        check(len(new) - len(data) == N_SEL * len(HOLD), f"the size grew by exactly {N_SEL} x len('{HOLD}')")
        check(read(os.path.join(bk, "registry_raw.csv")) == data, "the backup is the old file")
        issues, _n = validate(nas)
        check(issues.operator_hold == N_SEL + 1,
              f"the validator counts {N_SEL + 1} hold rows (the 4 new + the 1 already held)")
        rc, out, _e = run_tool("--nas-root", nas, *SEL_ARGS)
        check(rc == 0 and "operator cells matching: 0" in out, "a second dry run selects nothing")


def test_selectors_verify_catches_an_unselected_change():
    print("repair_operator_hold: the verification rejects a change to a record the selectors did not pick:")
    rows = selector_rows()
    data = registry_bytes(rows)
    sel = rah.Selectors("MRI", [PFX_A, PFX_B])
    plan = rah.find_matches(data, "", HOLD, sel)
    check(len(plan.matches) == N_SEL and all(m.record for m in plan.matches), "the plan records the record numbers")
    every_blank = rah.find_matches(data, "", HOLD, rah.Selectors("MRI", ["tools/"]))
    other = [m for m in every_blank.matches if m.record not in {x.record for x in plan.matches}]
    check(len(other) >= 1, "(fixture: an unselected blank MRI cell exists)")
    # the same NUMBER of changes, but one of them on the wrong record
    swapped = plan.matches[:-1] + [other[0]]
    bad = rah.splice(data, sorted(swapped, key=lambda m: m.start), HOLD)
    with tempfile.TemporaryDirectory() as d:
        old_p, new_p = os.path.join(d, "old.csv"), os.path.join(d, "new.csv")
        for p, b in ((old_p, data), (new_p, bad)):
            with open(p, "wb") as f:
                f.write(b)
        problems = rah.verify_repair(old_p, new_p, plan)
        check(any("not one of the planned" in p for p in problems), "caught: a same-count edit on an unselected record")
        check(any("planned, but unchanged" in p for p in problems), "caught: the selected record left unchanged")
        good = rah.splice(data, plan.matches, HOLD)
        with open(new_p, "wb") as f:
            f.write(good)
        check(rah.verify_repair(old_p, new_p, plan) == [], "the correct result verifies")


def test_selectors_with_a_named_from():
    print("repair_operator_hold: selectors narrow a non-blank --from too:")
    rows = [reg_row("ACQ-20220118-MRI-001", operator=PH, ingest_config=PFX_A + "a.yaml"),
            reg_row("ACQ-20220118-MRI-002", operator=PH, ingest_config="tools/configs/mri_jrc_pilot.yaml")]
    with tempfile.TemporaryDirectory() as d:
        nas = write_nas(d, registry_bytes(rows), rows)
        rc, out, _e = run_tool("--nas-root", nas, "--config-prefix", PFX_A)
        check(rc == 0 and "operator cells matching: 1" in out, "--config-prefix alone narrows the default --from to 1")
        rc, out, _e = run_tool("--nas-root", nas)
        check(rc == 0 and "operator cells matching: 2" in out, "without selectors: both, as before")


# ---- Run -------------------------------------------------------------------

def main():
    for fn in (test_constant,
               test_validator_accepts_hold_in_operator,
               test_validator_errors_on_hold_elsewhere,
               test_validator_ignores_a_note_that_mentions_the_hold,
               test_residue_check_unchanged,
               test_field_spans,
               test_dry_run_writes_nothing,
               test_cli_subprocess,
               test_apply_refusals,
               test_apply_happy_path,
               test_apply_bare_cells_and_blank,
               test_unparseable_records_refused,
               test_arguments_refused,
               test_verify_repair_catches_tampering,
               test_failed_verification_restores_the_backup,
               test_backup_must_verify,
               test_blank_from_needs_both_selectors,
               test_selectors_dry_run,
               test_selectors_apply,
               test_selectors_verify_catches_an_unselected_change,
               test_selectors_with_a_named_from):
        fn()
    print()
    if FAILS:
        print(f"FAILED ({len(FAILS)}):")
        for m in FAILS:
            print(f"  - {m}")
        sys.exit(1)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
