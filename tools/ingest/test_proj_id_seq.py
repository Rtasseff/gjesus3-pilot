"""PROJ ids are never reused, even when the highest project is deleted (BACKLOG 2026-11-06; PROJ-0054 on 2026-08-12).

Run: python tools/ingest/test_proj_id_seq.py   (or pytest)
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # tools/ on path
from ingest import projects_registry as pr  # noqa: E402


def _rows(*nums):
    return [{"project_id": f"PROJ-{n:04d}"} for n in nums]


def test_no_seq_file_is_max_plus_one():
    with tempfile.TemporaryDirectory() as d:
        assert pr.next_project_id(_rows(1, 2, 66), d) == "PROJ-0067"
        assert pr.next_project_id(_rows(1, 2, 66)) == "PROJ-0067"


def test_deleting_the_highest_does_not_free_its_number():
    with tempfile.TemporaryDirectory() as d:
        assert pr.allocate_project_id(_rows(52, 53), d) == "PROJ-0054"   # 99_test, 2026-08-12
        assert json.load(open(os.path.join(d, pr.PROJ_SEQ_FILENAME)))["PROJ"] == 54
        # 0054 removed from the registry by hand; the next project must not get 0054 again
        assert pr.allocate_project_id(_rows(52, 53), d) == "PROJ-0055"


def test_registry_ahead_of_seq_wins_and_preview_writes_nothing():
    with tempfile.TemporaryDirectory() as d:
        pr.allocate_project_id(_rows(3), d)                      # seq 4
        assert pr.next_project_id(_rows(3, 4, 10), d) == "PROJ-0011"
        assert json.load(open(os.path.join(d, pr.PROJ_SEQ_FILENAME)))["PROJ"] == 4


def test_corrupt_seq_file_falls_back_to_registry():
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, pr.PROJ_SEQ_FILENAME), "w").write("not json")
        assert pr.next_project_id(_rows(7), d) == "PROJ-0008"


def main():
    fails = []
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok: {name}")
            except Exception as e:  # noqa: BLE001 - report every failure
                fails.append(name)
                print(f"FAIL: {name}: {type(e).__name__}: {e}")
    print("FAILED: " + ", ".join(fails) if fails else "ALL CHECKS PASSED")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
