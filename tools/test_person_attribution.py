#!/usr/bin/env python3
"""test_person_attribution.py -- person fields enter the registry correctly (issue #15).

  1. ingest_raw._unreplaced_placeholders: a registry value or the top-level
     operator still holding the template's "<REQUIRED ...>" instruction (or an
     unresolved ${...} / {{...}}) is found; blanks and real names are not.
  2. ingest_single refuses such a case BEFORE Step 3 (nothing allocated or
     copied): the check sits between Step 2 and Step 3 and returns (None, False).

Temporary directories only: no NAS, no database, no pytest.

Run:  python tools/test_person_attribution.py      (exit 0 = pass)
"""

import inspect
import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import ingest_raw  # noqa: E402

FAILS = []

PH = "<REQUIRED - set via mri-ingest --operator, or replace here>"


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok:   {msg}")


def test_detector():
    print("[_unreplaced_placeholders]")
    found = ingest_raw._unreplaced_placeholders({"researcher": PH, "operator": PH, "instrument": "MRI"})
    check(sorted(f for f, _v in found) == ["operator", "researcher"],
          f"the template's researcher + operator placeholders are both found ({found})")
    found = ingest_raw._unreplaced_placeholders({"researcher": "Irene", "operator": "Irene"})
    check(found == [], "real names pass")
    found = ingest_raw._unreplaced_placeholders({"researcher": "", "operator": None})
    check(found == [], "blank / None pass (unknown is allowed; the placeholder is not)")
    found = ingest_raw._unreplaced_placeholders({"instrument_model": "Bruker BioSpec <7T|11.7T>"})
    check(found == [("instrument_model", "Bruker BioSpec <7T|11.7T>")],
          "the 2026-08-20 instrument_model placeholder is caught too (every registry column)")
    found = ingest_raw._unreplaced_placeholders({"notes": "see ${discovered.folder_name}"})
    check(found and found[0][0] == "notes", "an unresolved ${...} reference is caught")
    found = ingest_raw._unreplaced_placeholders({"source_path": "/tmp/<x>/y", "discovered": {"a": "<b>"}})
    check(found == [], "non-registry keys (source_path, discovered) are not inspected")
    found = ingest_raw._unreplaced_placeholders({"operator": "pending-claim"})
    check(found == [], "the hold value pending-claim is a value, not a placeholder")


def test_refusal_position():
    print("[the refusal sits between Step 2 and Step 3]")
    src = inspect.getsource(ingest_raw.ingest_single)
    i2 = src.index("Step 2: Resolve instrument code")
    i2b = src.index("_unreplaced_placeholders(cfg_single)")
    i3 = src.index("Step 3: Resolve ACQ-ID date prefix")
    i4 = src.index("Step 4: Generate ACQ-ID")
    check(i2 < i2b < i3 < i4, "placeholder check after Step 2, before the date and the ACQ-ID allocation")
    tail = src[i2b:i3]
    check("return None, False" in tail and '"ERROR"' in tail, "a hit logs ERROR and returns (None, False)")


def main():
    test_detector()
    test_refusal_position()
    print()
    if FAILS:
        print(f"{len(FAILS)} FAILURE(S):")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print("ALL PERSON-ATTRIBUTION CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
