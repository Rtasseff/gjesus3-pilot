"""Tests for relink_split_sidecars.py: finds a split project copy, relinks it, never writes /raw.

Run: python tools/test_relink_split_sidecars.py   (or pytest)
"""
import csv
import os
import tempfile

import relink_split_sidecars as rs
from ingest import registry as reg


def _nas(root, split):
    os.makedirs(os.path.join(root, "registries"))
    with open(os.path.join(root, "registries", "registry_raw.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=reg.REGISTRY_FIELDS)
        w.writeheader()
        w.writerow({"acq_id": "A1", "canonical_path": "/raw/A1/"})
    with open(os.path.join(root, "registries", "registry_projects.csv"), "w", newline="", encoding="utf-8") as f:
        f.write("project_id,name,folder_location\nPROJ-0001,P1,/projects/P1/\n")
    raw = os.path.join(root, "raw", "A1")
    os.makedirs(raw)
    with open(os.path.join(raw, "metadata.json"), "w", encoding="utf-8") as f:
        f.write('{"new": true}\n')
    link = os.path.join(root, "projects", "P1", "raw_linked", "X_A1")
    os.makedirs(link)
    with open(os.path.join(root, "projects", "P1", "provenance.csv"), "w", newline="", encoding="utf-8") as f:
        f.write("file_id,output_path,output_name,file_type,date_created,creator,input_refs\n"
                "FILE-0001,raw_linked/X_A1,X_A1,hardlink-folder,2026-11-07,,A1\n")
    if split:
        with open(os.path.join(link, "metadata.json"), "w", encoding="utf-8") as f:
            f.write('{"old": true}\n')
    else:
        os.link(os.path.join(raw, "metadata.json"), os.path.join(link, "metadata.json"))
    return os.path.join(raw, "metadata.json"), os.path.join(link, "metadata.json")


def test_dry_run_reports_and_changes_nothing():
    with tempfile.TemporaryDirectory() as d:
        raw, link = _nas(d, split=True)
        assert rs.main(["--nas-root", d]) == 0
        assert not os.path.samefile(raw, link)
        assert open(link, encoding="utf-8").read() == '{"old": true}\n'


def test_apply_relinks_and_leaves_raw_untouched():
    with tempfile.TemporaryDirectory() as d:
        raw, link = _nas(d, split=True)
        before = os.stat(raw)
        assert rs.main(["--nas-root", d, "--apply"]) == 0
        assert os.path.samefile(raw, link)
        assert open(link, encoding="utf-8").read() == '{"new": true}\n'
        after = os.stat(raw)
        assert (before.st_ino, before.st_mtime_ns, before.st_size) == (after.st_ino, after.st_mtime_ns, after.st_size)


def test_same_file_is_left_alone():
    with tempfile.TemporaryDirectory() as d:
        raw, link = _nas(d, split=False)
        pairs = list(rs.find_pairs(d))
        assert len(pairs) == 1
        assert rs.main(["--nas-root", d, "--apply"]) == 0
        assert os.path.samefile(raw, link)


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
