"""Tests for ingest/inplace.py: a hard link to the target sees the new content; a new target is created.

Run: python tools/ingest/test_inplace.py   (or pytest)
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # tools/ on path
from ingest import inplace  # noqa: E402


def test_hard_link_stays_the_same_file():
    with tempfile.TemporaryDirectory() as d:
        raw, link, tmp = (os.path.join(d, n) for n in ("metadata.json", "link.json", "metadata.json.tmp"))
        open(raw, "w", encoding="utf-8").write('{"old": true, "padding": "xxxxxxxxxxxxxxxxxxxxxxxx"}\n')
        os.link(raw, link)
        open(tmp, "w", encoding="utf-8").write('{"new": true}\n')
        inplace.replace_keeping_links(tmp, raw)
        assert os.path.samefile(raw, link)
        assert open(link, encoding="utf-8").read() == '{"new": true}\n'  # shorter content: truncated, no tail left
        assert not os.path.exists(tmp)


def test_missing_target_is_created():
    with tempfile.TemporaryDirectory() as d:
        path, tmp = os.path.join(d, "a.json"), os.path.join(d, "a.json.tmp")
        open(tmp, "w", encoding="utf-8").write("x\n")
        inplace.replace_keeping_links(tmp, path)
        assert open(path, encoding="utf-8").read() == "x\n" and not os.path.exists(tmp)


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
