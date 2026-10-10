#!/usr/bin/env python3
"""test_ingest_write_guards.py -- the registry write guards of 2026-10-10 (issue #14).

  1. ingest_raw._refuse_if_registered_meanwhile: the commit-time dedup re-check.
     The (acq_date, original_name) key is read fresh, under the lock, at the
     commit point -- so a case another run registered after this batch's
     expand_batch snapshot raises DuplicateAtCommit instead of landing twice.
     Retired rows count (06_REGISTRIES §2.9); a blank original_name never keys.
     The call sits inside the registry lock, before append_row.
  2. provenance.has_entry_for_output compares case-insensitively and treats
     `/` and `\\` alike (the share is case-insensitive), so append_entry is a
     no-op for a path that differs only in case.

Temporary directories only: no NAS, no database, no pytest.

Run:  python tools/test_ingest_write_guards.py      (exit 0 = pass)
"""

import csv
import inspect
import io
import os
import sys
import tempfile

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from ingest import provenance, registry, retired  # noqa: E402
import ingest_raw  # noqa: E402

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok:   {msg}")


def write_registry(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(registry.REGISTRY_FIELDS)
        for acq, adt, oname in rows:
            row = dict.fromkeys(registry.REGISTRY_FIELDS, "")
            row.update({"acq_id": acq, "acquisition_datetime": adt, "original_name": oname})
            w.writerow([row[c] for c in registry.REGISTRY_FIELDS])


def raises_dup(*args):
    try:
        ingest_raw._refuse_if_registered_meanwhile(*args)
    except ingest_raw.DuplicateAtCommit:
        return True
    return False


def test_commit_recheck():
    print("[the commit-time dedup re-check]")
    with tempfile.TemporaryDirectory() as d:
        regs = os.path.join(d, "registries")
        os.makedirs(regs)
        reg = os.path.join(regs, "registry_raw.csv")
        write_registry(reg, [
            ("ACQ-20260710-MRI-018", "2026-07-10T11:47:00+02:00", "jrc20260710_m12_1125_bis/5"),
            ("ACQ-20260304-ZWSI-001", "2026-03-04T09:00:00Z", "20260304/MFB_AUA_1123_ID12_PR_10x.czi"),
        ])
        check(raises_dup("2026-07-10T11:47:00+02:00", "jrc20260710_m12_1125_bis/5", reg),
              "a key committed meanwhile raises DuplicateAtCommit")
        check(raises_dup("20260304", "20260304/MFB_AUA_1123_ID12_PR_10x.czi", reg),
              "a compact YYYYMMDD date keys the same as the ISO one")
        check(not raises_dup("2026-07-10T11:47:00+02:00", "jrc20260710_m12_1125_bis/6", reg),
              "a different original_name passes")
        check(not raises_dup("2026-07-11T11:47:00+02:00", "jrc20260710_m12_1125_bis/5", reg),
              "the same name on another date passes (the key is the pair)")
        check(not raises_dup("2026-07-10", "", reg), "a blank original_name never keys")
        check(not raises_dup("", "MFB_AUA_1123_ID12_PR_10x.czi", reg),
              "a different staging-relative name is a different key (the known gap, issue #5)")

        # a retired row keeps blocking (as expand_batch does)
        tomb = retired.retired_path(regs)
        with open(tomb, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=retired.RETIRED_FIELDS)
            w.writeheader()
            t = {k: "" for k in retired.RETIRED_FIELDS}
            t.update({"acq_id": "ACQ-20260304-ZWSI-023", "disposition": "duplicate",
                      "bytes_fate": sorted(retired.BYTES_FATES)[0],
                      "superseded_by": "ACQ-20260304-ZWSI-001"})
            orig = dict.fromkeys(registry.REGISTRY_FIELDS, "")
            orig.update({"acq_id": "ACQ-20260304-ZWSI-023", "acquisition_datetime": "2026-03-04T09:00:00Z",
                         "original_name": "MFB_AUA_1123_ID12_PR_10x.czi"})
            buf = io.StringIO()
            csv.writer(buf, lineterminator="").writerow([orig[c] for c in registry.REGISTRY_FIELDS])
            t["registry_raw_row"] = buf.getvalue()   # the removed record, verbatim
            w.writerow(t)
        tombs = retired.read_retired(tomb)
        orig_row = retired.original_row(tombs["ACQ-20260304-ZWSI-023"], registry.REGISTRY_FIELDS)
        check(orig_row.get("original_name") == "MFB_AUA_1123_ID12_PR_10x.czi", "tombstone fixture parses")
        check(raises_dup("2026-03-04", "MFB_AUA_1123_ID12_PR_10x.czi", reg),
              "a retired row's key still blocks at commit (06_REGISTRIES §2.9)")

    src = inspect.getsource(ingest_raw.ingest_single)
    i_lock = src.index("with locking.registry_lock(registries_dir):", src.index("Step 10: Update registry"))
    i_check = src.index("_refuse_if_registered_meanwhile(", i_lock)
    i_append = src.index("registry.append_row(registry_path, row)", i_lock)
    check(i_lock < i_check < i_append, "the re-check runs inside the lock, before append_row")
    check(issubclass(ingest_raw.DuplicateAtCommit, RuntimeError),
          "DuplicateAtCommit is caught by the commit's except (rollback, case fails)")


def test_provenance_case():
    print("[provenance output_path: case-insensitive, / == \\]")
    with tempfile.TemporaryDirectory() as d:
        prov = os.path.join(d, "provenance.csv")
        first = provenance.append_entry(prov, {
            "output_path": "raw_linked/MRI_m12_0525_20260224_1147_5_1",
            "output_name": "MRI_m12_0525_20260224_1147_5_1",
            "file_type": "link", "input_refs": "ACQ-20260224-MRI-020",
        })
        check(first == "FILE-0001", f"first row written ({first})")
        check(provenance.has_entry_for_output(prov, "raw_linked/MRI_m12_0525_20260224_1147_5_1"), "exact match")
        check(provenance.has_entry_for_output(prov, "raw_linked/mri_M12_0525_20260224_1147_5_1"),
              "a case-variant is the same entry")
        check(provenance.has_entry_for_output(prov, "raw_linked\\MRI_m12_0525_20260224_1147_5_1"),
              "a backslash spelling is the same entry")
        check(not provenance.has_entry_for_output(prov, "raw_linked/MRI_m12_0525_20260224_1147_5_2"),
              "a different name is not")
        check(not provenance.has_entry_for_output(prov, ""), "blank is never found")
        again = provenance.append_entry(prov, {
            "output_path": "RAW_LINKED/MRI_M12_0525_20260224_1147_5_1",
            "output_name": "x", "file_type": "link", "input_refs": "ACQ-20260224-MRI-020",
        })
        check(again is None, "append_entry is a no-op for the case-variant")
        with open(prov, encoding="utf-8", newline="") as f:
            n = sum(1 for _ in csv.DictReader(f))
        check(n == 1, f"still one row ({n})")


def main():
    test_commit_recheck()
    test_provenance_case()
    print()
    if FAILS:
        print(f"{len(FAILS)} FAILURE(S):")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print("ALL WRITE-GUARD CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
