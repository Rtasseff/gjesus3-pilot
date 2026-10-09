"""Unit tests for tools/ingest/ni_corrections.py — NI per-session corrections.

No NAS, no network. Run: python tools/test_ni_corrections.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from ingest import ni_corrections as nc

_fail = 0


def check(cond, msg):
    global _fail
    print(("  ok:   " if cond else "  FAIL: ") + msg)
    if not cond:
        _fail += 1


# 1. session_key from the RAW path components
disc = {"series": "1207", "date": "260212", "subject": "0324_m61", "project": "0324"}
check(nc.session_key(disc) == "1207/260212/0324_m61", "session_key = series/date/subject")
check(nc.session_key({"series": "1207"}) is None, "session_key None if a component is missing")

# 2. parse_extra
check(nc.parse_extra("tracer=FDG; dose=10 MBq") == {"tracer": "FDG", "dose": "10 MBq"},
      "parse_extra splits ; and first =")
check(nc.parse_extra("") == {}, "parse_extra('') -> {}")
check(nc.parse_extra("nokey; =noval; ok=1") == {"ok": "1"}, "parse_extra skips keyless/blank pieces")

# 3. append_new_rows + read_corrections round-trip
with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, "corr.csv")
    n = nc.append_new_rows(path, [
        {"session_path": "1207/260212/0324_m61", "project": "0324",
         "animal_codes": "61", "extra_metadata": "tracer=FDG"},
        {"session_path": "1207/260212/0525_m12", "project": "0525"},
    ])
    check(n == 2, "append_new_rows creates the file and reports 2 added")
    corr = nc.read_corrections(path)
    check(len(corr) == 2, "read_corrections -> 2 rows")
    check(corr["1207/260212/0324_m61"]["extra_metadata"] == "tracer=FDG",
          "round-trips the extra_metadata cell")
    check(nc.read_corrections(os.path.join(d, "nope.csv")) == {}, "missing file -> {}")

    # 4. assert_header: unknown column raises; missing session_path raises
    bad = os.path.join(d, "bad.csv")
    with open(bad, "w", encoding="utf-8", newline="") as f:
        f.write("session_path,project,WUT\n")
    try:
        nc.assert_header(bad); check(False, "unknown column should raise")
    except RuntimeError:
        check(True, "assert_header rejects an unknown column")
    nokey = os.path.join(d, "nokey.csv")
    with open(nokey, "w", encoding="utf-8", newline="") as f:
        f.write("project,animal_codes\n")
    try:
        nc.assert_header(nokey); check(False, "missing session_path should raise")
    except RuntimeError:
        check(True, "assert_header requires session_path")

# 5. apply_pre overrides discovered.{project,animal_codes} on a session match
corrections = {
    "1207/260212/0324_m61": {
        "session_path": "1207/260212/0324_m61",
        "project": "0325", "animal_codes": "60",
        "extra_metadata": "tracer=FDG",
    }
}
case = {"discovered": {"series": "1207", "date": "260212", "subject": "0324_m61",
                       "project": "0324", "animal_codes": "61"}}
row = nc.apply_pre(case, corrections)
check(row is not None, "apply_pre returns the matched row")
check(case["discovered"]["project"] == "0325", "apply_pre overrides discovered.project (REMI typo fix)")
check(case["discovered"]["animal_codes"] == "60", "apply_pre overrides discovered.animal_codes (mouse-id fix)")
# raw path components are NOT touched (session key stays stable)
check(case["discovered"]["subject"] == "0324_m61", "apply_pre leaves the raw subject (dedup/session key) intact")

# 6. apply_post stashes session_extra and overrides NOTHING resolved
nc.apply_post(case, row)
check(case.get("session_extra") == {"tracer": "FDG"}, "apply_post stashes session_extra (tracer)")
# session_id / sample_id are DERIVED (from the corrected project + animal_codes), never
# hand-set. Pinning this stops anyone re-adding them as columns: a hand-set sample_id
# went stale the moment a project correction re-derived project_hint (0324->0325 left
# sample_id reading 0324_m61 in true production, 2026-06-29).
check("session_id" not in case, "apply_post does NOT set session_id (derived)")
check("sample_id" not in case, "apply_post does NOT set sample_id (derived)")
check("session_id" not in nc.NI_CORRECTION_FIELDS, "session_id is not a corrections column")
check("sample_id" not in nc.NI_CORRECTION_FIELDS, "sample_id is not a corrections column")
# a stale worksheet carrying the dropped columns must fail loudly, not silently ignore
with tempfile.TemporaryDirectory() as _d:
    _p = os.path.join(_d, "stale.csv")
    with open(_p, "w", newline="", encoding="utf-8") as f:
        f.write("session_path,project,animal_codes,session_id,sample_id,extra_metadata\n")
    try:
        nc.assert_header(_p)
        check(False, "stale header with dropped columns should be rejected")
    except RuntimeError:
        check(True, "assert_header rejects a stale worksheet carrying session_id/sample_id")

# 7. no match / empty corrections -> no-op
case2 = {"discovered": {"series": "9999", "date": "260212", "subject": "x", "project": "p"}}
check(nc.apply_pre(case2, corrections) is None, "apply_pre no-op when session not in corrections")
check(case2["discovered"]["project"] == "p", "apply_pre leaves discovered untouched on no match")
check(nc.apply_pre(case2, {}) is None, "apply_pre no-op on empty corrections")

# 8. ONE file, append-only, owned by the operator (2026-08-07)
with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, "ni_corrections_irene.csv")
    check(nc.read_corrections(path) == {}, "a file that doesn't exist yet -> {}")

    # --plan pass 1: two sessions discovered, both new
    plan1 = [{"session_path": "1207/260212/0324_m61", "project": "0324",
              "animal_codes": "61", "extra_metadata": ""},
             {"session_path": "1207/260212/0525_m12", "project": "0525",
              "animal_codes": "12", "extra_metadata": ""}]
    check(nc.append_new_rows(path, plan1) == 2, "--plan adds both new sessions")

    # the operator edits IN PLACE: fixes a project, adds a tracer
    rows = nc.read_corrections(path)
    rows["1207/260212/0324_m61"]["project"] = "0326"
    rows["1207/260212/0324_m61"]["extra_metadata"] = "tracer=FDG"
    with open(path, "w", encoding="utf-8", newline="") as f:
        import csv as _csv
        w = _csv.DictWriter(f, fieldnames=nc.NI_CORRECTION_FIELDS)
        w.writeheader()
        for r in rows.values():
            w.writerow({k: r.get(k, "") for k in nc.NI_CORRECTION_FIELDS})

    # --plan pass 2: same sessions re-discovered -> nothing added, edits intact.
    # This is what makes the steady state one command.
    check(nc.append_new_rows(path, plan1) == 0, "--plan adds nothing on a re-run")
    after = nc.read_corrections(path)
    check(after["1207/260212/0324_m61"]["project"] == "0326",
          "a re-run NEVER overwrites the operator's edit")
    check(after["1207/260212/0324_m61"]["extra_metadata"] == "tracer=FDG",
          "a re-run NEVER overwrites the operator's extra_metadata")

    # --plan pass 3: a genuinely new session is appended alongside the edited ones
    check(nc.append_new_rows(path, plan1 + [
        {"session_path": "1207/260408/0522_143", "project": "0522",
         "animal_codes": "143", "extra_metadata": ""}]) == 1,
        "--plan appends only the session it has never seen")
    check(len(nc.read_corrections(path)) == 3, "file now holds 3 sessions")
    check(nc.read_corrections(path)["1207/260212/0324_m61"]["project"] == "0326",
          "the append left the edited row alone")

    # THE ACCEPTANCE TEST: a reconstruction discovered on a LATER sync, with no
    # worksheet passed at all, still gets the correction. This is the case the
    # per-run-file design got silently wrong.
    late = {"discovered": {"series": "1207", "date": "260212",
                           "subject": "0324_m61", "project": "0324",
                           "animal_codes": "61", "ni_recon_idx": "3"}}
    row = nc.apply_pre(late, nc.read_corrections(path))
    check(row is not None, "a late recon matches its session in the file")
    check(late["discovered"]["project"] == "0326",
          "late recon inherits the correction with NOTHING re-entered")
    nc.apply_post(late, row)
    check(late.get("session_extra") == {"tracer": "FDG"},
          "late recon inherits the tracer metadata too")

# 8b. append survives the two Excel hazards (BOM, no trailing newline)
with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, "excel.csv")
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        f.write("session_path,project,animal_codes,extra_metadata\r\n"
                "a/b/c,0324,61,tracer=FDG")          # BOM + NO final newline
    check(nc.append_new_rows(path, [{"session_path": "d/e/f", "project": "0525"}]) == 1,
          "appends to a BOM'd file with no trailing newline")
    got = nc.read_corrections(path)
    check(len(got) == 2, "both rows readable after the append (no concatenation)")
    check(got["a/b/c"]["extra_metadata"] == "tracer=FDG",
          "the operator's last row survived the append intact")

    # the operator may delete columns they don't use — honour the file's header
    trimmed = os.path.join(d, "trimmed.csv")
    with open(trimmed, "w", encoding="utf-8", newline="") as f:
        f.write("session_path,project\n")
    nc.append_new_rows(trimmed, [{"session_path": "x/y/z", "project": "0525",
                                  "extra_metadata": "tracer=FDG"}])
    check(nc.csv_safe.read_header(trimmed) == ["session_path", "project"],
          "append uses the file's own header, not NI_CORRECTION_FIELDS")

# 9. where the file lives — derived from the running code's own path
check(nc.corrections_filename("irene") == "ni_corrections_irene.csv",
      "corrections_filename -> ni_corrections_<researcher>.csv")
check(nc.corrections_filename("Maria G") == "ni_corrections_maria-g.csv",
      "corrections_filename lowercases + slugifies")
check(nc.corrections_filename("") == "ni_corrections_unknown.csv",
      "corrections_filename never returns a bare prefix")

# NB: the root is compared by suffix — os.path.abspath on Windows prepends the
# current drive to a POSIX-absolute path, so an equality check would only pass on
# the Mac. Year and group are exact either way.
_mac = nc.gnuclear_anchor("/Volumes/shares/gnuclear/2026/Jesus/Ryan/ni-live-test")
check(_mac[0].replace("\\", "/").endswith("/Volumes/shares/gnuclear")
      and _mac[1:] == ("2026", "Jesus"),
      "gnuclear_anchor reads root/year/group off a Mac mount path")
check(nc.gnuclear_anchor(r"S:\gnuclear\2026\Jesus\Ryan\ni-live-test\tools")
      [1:] == ("2026", "Jesus"),
      "gnuclear_anchor reads the same off a Windows S:\\ path")
check(nc.gnuclear_anchor("/home/someone/repo/tools") is None,
      "gnuclear_anchor -> None when the code isn't staged under a year folder")

with tempfile.TemporaryDirectory() as d:
    # not on gnuclear -> next to the code (dev checkout / local copy)
    check(nc.resolve_path("irene", start_dir=d)
          == os.path.join(d, "ni_corrections_irene.csv"),
          "off gnuclear, the file falls back to sitting next to the code")

    # a gnuclear-shaped tree: 2025 already holds Irene's file, code staged in 2026
    root = os.path.join(d, "gnuclear")
    os.makedirs(os.path.join(root, "2025", "Jesus", "Irene"))
    os.makedirs(os.path.join(root, "2026", "Jesus", "Ryan", "ni-live-test"))
    staged = os.path.join(root, "2026", "Jesus", "Ryan", "ni-live-test")
    fresh = nc.resolve_path("claudia", start_dir=staged)
    check(fresh == os.path.join(root, "2026", "Jesus", "claudia",
                                "ni_corrections_claudia.csv"),
          "a new researcher's file is created under the code's own year/group")

    old = os.path.join(root, "2025", "Jesus", "Irene", "ni_corrections_irene.csv")
    with open(old, "w", encoding="utf-8", newline="") as f:
        f.write("session_path,project,animal_codes,extra_metadata\n")
    # case-insensitive folder match (Mac says `irene`, gnuclear says `Irene`)
    # AND the existing file wins over the current year: a correction must not
    # expire just because the calendar turned over.
    check(nc.resolve_path("irene", start_dir=staged) == old,
          "an existing file is reused wherever it already is (no year hop)")

print("\nALL NI-CORRECTIONS CHECKS PASSED" if _fail == 0 else f"\n{_fail} CHECK(S) FAILED")
sys.exit(1 if _fail else 0)
