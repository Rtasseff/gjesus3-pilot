#!/usr/bin/env python3
"""hardlink_test.py -- can THIS machine and account make hard links on the data root?

The one test that can sink a move to a new machine or account: ingest and the project
folders rest on os.link working over SMB against the NAS. Run it as the account that will
do the work.

    python tools/diagnostics/hardlink_test.py --nas-root "J:\\gjesus3-data"         # says what it would do
    python tools/diagnostics/hardlink_test.py --nas-root "J:\\gjesus3-data" --run   # does it

With --run it writes one small file to <root>/tmp, links it, checks the link, and removes
both, even on a failure. It touches nothing else and refuses if <root>/tmp is missing.

Success is os.path.samefile, not the link count: through SMB a true hard link reports
st_nlink = 1, so a count check makes it look like a copy.

Exit: 0 hard links work; 1 they do not; 2 bad root, or nothing was run.
"""
import argparse
import getpass
import os
import socket
import sys
import time


def run_test(tmp_dir, log=print):
    """Make one hard link in tmp_dir and remove it. Returns (ok, detail)."""
    stem = f"hardlink_test_{socket.gethostname()}_{os.getpid()}_{int(time.time())}"
    src = os.path.join(tmp_dir, stem + "_src.txt")
    dst = os.path.join(tmp_dir, stem + "_link.txt")
    payload = f"hardlink test {getpass.getuser()}\n".encode("utf-8")
    try:
        with open(src, "wb") as f:
            f.write(payload)
        os.link(src, dst)
        if not os.path.samefile(src, dst):
            return False, "os.link returned, but the two paths are not the same file"
        with open(dst, "rb") as f:
            if f.read() != payload:
                return False, "the link does not read back the source's bytes"
        return True, "os.link worked and samefile confirms it"
    except OSError as e:
        return False, f"{type(e).__name__}: {e}"
    finally:
        for path in (dst, src):
            try:
                if os.path.lexists(path):
                    os.remove(path)
            except OSError as e:
                log(f"WARN: could not remove {path}: {e}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--nas-root", required=True)
    p.add_argument("--run", action="store_true", help="actually write (default: say what would happen)")
    args = p.parse_args(argv)

    tmp_dir = os.path.join(args.nas_root, "tmp")
    who = f"{getpass.getuser()} on {socket.gethostname()}"
    if not os.path.isdir(os.path.join(args.nas_root, "registries")):
        print(f"ERROR: {args.nas_root!r} has no registries/ folder: not a data root")
        return 2
    if not os.path.isdir(tmp_dir):
        print(f"ERROR: {tmp_dir!r} does not exist; this test writes nowhere else")
        return 2
    if not args.run:
        print(f"Would write one small file to {tmp_dir} as {who}, hard-link it, check it, and remove both.")
        print("Nothing written. Re-run with --run.")
        return 2
    ok, detail = run_test(tmp_dir)
    print(f"{'PASS' if ok else 'FAIL'}: {who}: {tmp_dir}: {detail}")
    leftovers = [n for n in os.listdir(tmp_dir) if n.startswith("hardlink_test_")]
    if leftovers:
        print(f"WARN: leftovers in {tmp_dir}: {leftovers}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
