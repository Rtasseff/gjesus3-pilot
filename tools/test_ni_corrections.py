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

# 3. write_plan + read_corrections round-trip
with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, "corr.csv")
    nc.write_plan(path, [
        {"session_path": "1207/260212/0324_m61", "project": "0324",
         "animal_codes": "61", "extra_metadata": "tracer=FDG"},
        {"session_path": "1207/260212/0525_m12", "project": "0525"},
    ])
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

print("\nALL NI-CORRECTIONS CHECKS PASSED" if _fail == 0 else f"\n{_fail} CHECK(S) FAILED")
sys.exit(1 if _fail else 0)
