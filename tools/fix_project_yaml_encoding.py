#!/usr/bin/env python3
"""fix_project_yaml_encoding.py -- convert project `_project.yaml` files that are not UTF-8 (cp1252) to UTF-8.

    python tools/fix_project_yaml_encoding.py --nas-root "J:\\gjesus3-data"
    python tools/fix_project_yaml_encoding.py --nas-root "J:\\gjesus3-data" --apply ^
        --backup-dir "C:\\Users\\rtasseff\\temp\\gjesus3_project_yaml_backup_20261020"

WHY. Until 2026-10 `create_project.py` wrote `_project.yaml` in the Windows default encoding, so a
description with an accent or an em dash was stored as cp1252 and a UTF-8 reader fails on it. On
2026-10-07, 10 of 65 production files were affected (BACKLOG "10 project `_project.yaml` files are
not UTF-8"). Every writer now pins UTF-8; this converts the files written before that.

WHAT IT DOES. Looks at every `projects/*/_project.yaml`. A file that decodes as UTF-8 is left
alone. One that does not is decoded as cp1252 and re-encoded as UTF-8 -- the text is identical,
only the bytes of the non-ASCII characters change; line endings and everything else stay as they
are. A file that is neither UTF-8 nor cp1252 is reported and never touched.

Dry run by default: lists each non-UTF-8 file and the lines that hold non-ASCII text, as they will
read after conversion. Writes nothing.
--apply needs --backup-dir, a directory that must NOT exist yet. Each file is first copied there
(under its project folder's name) and the copy verified by SHA-256; then the UTF-8 bytes are written
to a temp file and swapped in, and the result is re-read and checked to decode to the same text.
A `manifest.csv` in the backup dir records each file's SHA-256 before and after.
"""
import argparse
import csv
import glob
import os
import shutil
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
from ingest import checksum  # noqa: E402

UTF8, CP1252, UNKNOWN = "utf-8", "cp1252", "unknown"


def classify(raw):
    """(encoding, text): UTF8 when the bytes are valid UTF-8, CP1252 when they decode as cp1252
    (strictly: the five bytes cp1252 leaves undefined fail), else (UNKNOWN, None)."""
    try:
        return UTF8, raw.decode("utf-8")
    except UnicodeDecodeError:
        pass
    try:
        return CP1252, raw.decode("cp1252")
    except UnicodeDecodeError:
        return UNKNOWN, None


def scan(nas_root):
    """[(path, encoding, text)] for every projects/*/_project.yaml, sorted by path."""
    out = []
    for path in sorted(glob.glob(os.path.join(nas_root, "projects", "*", "_project.yaml"))):
        with open(path, "rb") as f:
            enc, text = classify(f.read())
        out.append((path, enc, text))
    return out


def non_ascii_lines(text):
    return [(i, ln.rstrip("\r\n")) for i, ln in enumerate(text.splitlines(True), 1)
            if any(ord(c) > 127 for c in ln)]


def convert(path, text, backup_dir):
    """Back up, write UTF-8, re-read. Returns (sha_before, sha_after); raises on any failed check."""
    folder = os.path.basename(os.path.dirname(path))
    bdir = os.path.join(backup_dir, folder)
    os.makedirs(bdir)
    bpath = os.path.join(bdir, os.path.basename(path))
    shutil.copy2(path, bpath)
    before = checksum.sha256_file(path)
    if checksum.sha256_file(bpath) != before:
        raise RuntimeError(f"backup of {path} does not verify")
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "wb") as f:
        f.write(text.encode("utf-8"))
    os.replace(tmp, path)
    with open(path, "rb") as f:
        if f.read().decode("utf-8") != text:
            raise RuntimeError(f"{path} does not re-read as the same text after conversion "
                               f"(the original is at {bpath})")
    return before, checksum.sha256_file(path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--nas-root", required=True)
    ap.add_argument("--apply", action="store_true", help="convert (default: dry run)")
    ap.add_argument("--backup-dir", help="with --apply: a NEW directory for the verified backups")
    args = ap.parse_args(argv)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass
    nas = os.path.normpath(args.nas_root)
    files = scan(nas)
    todo = [(p, t) for p, e, t in files if e == CP1252]
    unknown = [p for p, e, _t in files if e == UNKNOWN]
    tag = "" if args.apply else "[dry-run] "

    print(f"{tag}{len(files)} _project.yaml file(s); {len(files) - len(todo) - len(unknown)} UTF-8, "
          f"{len(todo)} cp1252, {len(unknown)} neither")
    for p, t in todo:
        print(f"{tag}cp1252: {p}")
        for i, ln in non_ascii_lines(t):
            print(f"{tag}    line {i}: {ln}")
    for p in unknown:
        print(f"{tag}NEITHER UTF-8 NOR cp1252 (left alone, look at it by hand): {p}")

    if not args.apply:
        if todo:
            print("[dry-run] nothing written; re-run with --apply --backup-dir <new dir>")
        return 0
    if not todo:
        print("nothing to convert")
        return 0
    if not args.backup_dir:
        print("REFUSED: --apply needs --backup-dir <a new directory>")
        return 2
    bk = os.path.abspath(args.backup_dir)
    if os.path.exists(bk):
        print(f"REFUSED: backup dir {bk} already exists (use a new one)")
        return 3
    os.makedirs(bk)
    rows, failed = [], 0
    for p, t in todo:
        try:
            before, after = convert(p, t, bk)
            rows.append({"path": p, "sha256_before": before, "sha256_after": after, "result": "converted"})
            print(f"converted: {p}")
        except Exception as e:  # noqa: BLE001 -- reported; the rest carry on
            failed += 1
            rows.append({"path": p, "sha256_before": "", "sha256_after": "", "result": f"FAILED: {e}"})
            print(f"FAILED: {p}: {e}")
    with open(os.path.join(bk, "manifest.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["path", "sha256_before", "sha256_after", "result"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows) - failed} converted, {failed} failed; backups and manifest.csv in {bk}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
