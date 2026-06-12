#!/usr/bin/env python3
"""test_ni_live_discover.py — the NI live-machine subject grammar (§3A).

Pins the validated `parse_subject` grammar to the *documented* example table in
`equipment/nuclear-imaging/live_machine_data_layout_and_sync_rules.md` §3A, plus
the project-conflict near-miss flag (NI-LIVE-09) and the
`facility_id` <-> `animal_db.compose_subject_id` contract. This is the
regression net for the strict Program-B parser that will grow from here.

Run:  PYTHONPATH=tools python tools/test_ni_live_discover.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ni_live_discover as nd  # noqa: E402

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok:   {msg}")


def nums(p):
    return [a["number"] for a in p["animals"]]


def test_grammar_happy_path():
    print("[sec 3A grammar - documented examples]")
    # 0525_m25 (irene) | parent 0525 -> project 0525, [25] mouse, clean.
    p = nd.parse_subject("0525_m25", "0525")
    check(p["project"] == "0525" and nums(p) == [25], "0525_m25 -> project 0525, animal 25")
    check(p["animals"][0]["species"] == "m" and p["flags"] == [], "0525_m25 species=mouse, no flags")

    # 0324_m59_m60 -> 2 animals, one acquisition.
    p = nd.parse_subject("0324_m59_m60", "0324")
    check(nums(p) == [59, 60] and p["timepoint"] is None, "0324_m59_m60 -> [59,60], no timepoint")

    # 0324_m59_m60_2h -> 2 animals + timepoint.
    p = nd.parse_subject("0324_m59_m60_2h", "0324")
    check(nums(p) == [59, 60] and p["timepoint"] == "2h", "0324_m59_m60_2h -> [59,60] + 2h")

    # 0522_120 (irene) | parent 1207 -> subject prefix WINS (0522), no m -> species-unknown,
    # and NO project-conflict (1207 is the funded series, wholesale-different — §5).
    p = nd.parse_subject("0522_120", "1207")
    check(p["project"] == "0522" and nums(p) == [120], "0522_120 -> project 0522 (subject wins over parent 1207)")
    check("species-unknown" in p["flags"], "0522_120 bare number -> species-unknown")
    check(not any(f.startswith("project-conflict") for f in p["flags"]),
          "0522_120 vs 1207 is NOT flagged (series != protocol, by design)")

    # 0324_r20 (ermal) -> RAT, not mouse.
    p = nd.parse_subject("0324_r20", "0324")
    check(nums(p) == [20] and p["animals"][0]["species"] == "r", "0324_r20 -> rat 20")

    # 64 (claudia) | parent 0622_WELAB -> bare number, project recovered FROM parent.
    p = nd.parse_subject("64", "0622_WELAB")
    check(p["project"] == "0622" and "project<-parent" in p["flags"], "64 -> project 0622 recovered from parent")
    check(nums(p) == [64], "64 -> animal 64")

    # 11-12-13 (claudia) -> 3 animals, '-' separated.
    p = nd.parse_subject("11-12-13", "1622_idif_florbetaben5")
    check(nums(p) == [11, 12, 13], "11-12-13 -> [11,12,13]")

    # 6-8-9 (claudia) -> non-contiguous EXPLICIT list, NOT a range -> no possible-range.
    p = nd.parse_subject("6-8-9", "1622_x")
    check(nums(p) == [6, 8, 9] and "possible-range" not in p["flags"], "6-8-9 -> explicit list, no range flag")

    # 0124_2-4-5-6 (claudia) -> the max case: 4 animals, none over cap.
    p = nd.parse_subject("0124_2-4-5-6", "979_0124_fdg4")
    check(nums(p) == [2, 4, 5, 6] and "gt-4-animals" not in p["flags"], "0124_2-4-5-6 -> 4 animals, within cap")


def test_flags_and_edges():
    print("[sec 3A flags - phantom, range, typo, cap]")
    # phantom -> QC, no DB link.
    p = nd.parse_subject("phantom5_6", "0421")
    check(p["phantom"] and p["animals"] == [] and p["flags"] == ["phantom"], "phantom5_6 -> phantom, no animals")

    # m6-7 -> obvious consecutive PAIR (gap 1), no range flag.
    p = nd.parse_subject("0525_m6-7", "0525")
    check(nums(p) == [6, 7] and "possible-range" not in p["flags"], "m6-7 -> pair, no range flag")

    # m10-15 -> AMBIGUOUS (gap 5): could be a 6-animal range -> possible-range flag.
    p = nd.parse_subject("1015_m10-15", "1015")
    check(nums(p) == [10, 15] and "possible-range" in p["flags"], "m10-15 -> possible-range flag")

    # 12-1314 (claudia) -> missing-separator TYPO surfaces as possible-range (gap 1302).
    p = nd.parse_subject("12-1314", "0323_3tgad_fdg")
    check(nums(p) == [12, 1314] and "possible-range" in p["flags"], "12-1314 typo -> possible-range")

    # > cap -> gt-4-animals flag (synthetic 5-animal).
    p = nd.parse_subject("0124_2-4-5-6-7", "979")
    check(len(p["animals"]) == 5 and "gt-4-animals" in p["flags"], "5 animals -> gt-4-animals flag")

    # bare-number, no recoverable project -> no-project flag (ermal 141-144 cohort).
    p = nd.parse_subject("141", "ermal_misc")
    check(p["project"] is None and "no-project" in p["flags"], "141 (no parent digits) -> no-project")


def test_project_conflict_near_miss():
    print("[NI-LIVE-09 - near-miss project conflict surfaced, not resolved]")
    # subject 1015 under parent 1025: one-digit typo -> flag, do NOT pick.
    p = nd.parse_subject("1015_m6-7", "1025")
    check("project-conflict:1025" in p["flags"], "1015 vs 1025 -> project-conflict:1025")
    check(p["project"] == "1015", "conflict flags but still does NOT silently change project (subject prefix kept)")

    # 0324 vs 0314: also a one-digit near-miss.
    p = nd.parse_subject("0324_m63", "0314")
    check("project-conflict:0314" in p["flags"], "0324 vs 0314 -> project-conflict:0314")

    # the _near_miss predicate itself: typos in, wholesale-different out.
    check(nd._near_miss("1015", "1025") and nd._near_miss("0324", "0314"), "_near_miss: one-digit typos True")
    check(not nd._near_miss("0522", "1207"), "_near_miss: wholesale-different False")
    check(not nd._near_miss("1320", "979"), "_near_miss: different length False")
    check(not nd._near_miss("1015", "1015"), "_near_miss: identical False (zero diffs)")


def test_facility_id_contract():
    print("[facility_id mirrors animal_db.compose_subject_id]")
    try:
        import animal_db
    except Exception as e:  # pragma: no cover - environment without the module
        print(f"  skip: animal_db unavailable ({e})")
        return
    for code, proj in ((25, "0525"), (64, "0622"), (20, "0324")):
        check(nd.facility_id(code, proj) == animal_db.compose_subject_id(code, proj),
              f"facility_id({code},{proj}) == compose_subject_id (== {animal_db.compose_subject_id(code, proj)})")
    # leading-zero project must NOT be coerced to int (0525 stays 0525).
    check(nd.facility_id(13, "0525") == "13-AE-biomaGUNE-0525", "facility_id keeps the project's leading zero")
    check(nd.facility_id(13, None) is None, "facility_id(_, None) -> None (no project, no key)")


def main():
    test_grammar_happy_path()
    test_flags_and_edges()
    test_project_conflict_near_miss()
    test_facility_id_contract()
    print()
    if FAILS:
        print(f"FAILED ({len(FAILS)}):")
        for m in FAILS:
            print(f"  - {m}")
        return 1
    print("ALL PASS (ni_live_discover subject grammar)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
