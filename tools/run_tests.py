#!/usr/bin/env python3
"""run_tests.py -- run every `test_*.py` under tools/ and report one line per suite.

The suites are hand-rolled scripts (no pytest): each one is a program that
prints `ok:` / `FAIL:` lines and exits 0 on success. Until 2026-10-10 the only
way to run "the suites" was a shell loop someone wrote on the spot (issue #22,
the test-collection half). This runner is that loop, kept:

- discovers `tools/**/test_*.py` (sorted, so the order is stable);
- runs each in its OWN directory (the suites put their directory on sys.path
  and some import siblings by name), with `tools/` and the repo root on
  PYTHONPATH, under a timeout;
- prints PASS / FAIL with the time taken, the tail of a failing suite's output,
  and a summary; exits 1 when any suite failed.

Some suites can only pass on the production workstation: they build paths
with backslashes or Windows long paths (`\\\\?\\`), need `~/.my.cnf` for the
animal-facility DB, or a network drive. On another platform those report
FAIL with a telling last line (a `FileNotFoundError` on a path holding `\\`,
"credentials file not found"); read the tail before blaming a change, and
compare against `main` on the same machine. In a Linux container on
2026-10-10, 11 of the 52 suites were of that kind: `test_claim_workbooks`,
`test_drive3_bmj`, `test_drive3_closeout`, `test_drive3_placement`,
`test_drive_catalog`, `test_drives_ingest_plan`, `test_drives_r4_groups`,
`test_mri_archive`, `test_ni_flat`, `test_nonraw_placement`,
`test_retire_acquisition_v2`; the other 41 passed.

Usage:
    python tools/run_tests.py                 # everything
    python tools/run_tests.py --only retire   # suites whose path contains "retire"
    python tools/run_tests.py --skip drive3 --skip drives   # leave some out
    python tools/run_tests.py --list          # just the names
    python tools/run_tests.py -j 4            # four at a time (suites use temp dirs; safe)
    python tools/run_tests.py --verbose       # the full output of every suite
"""

import argparse
import concurrent.futures
import os
import subprocess
import sys
import time

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TOOLS_DIR)
DEFAULT_TIMEOUT = 900  # seconds per suite
TAIL_LINES = 15


def discover(root=TOOLS_DIR):
    """Every tools/**/test_*.py, repo-relative, sorted."""
    found = []
    for base, dirs, files in os.walk(root):
        # diagnostics/ holds scripts to run by hand ON a machine against its
        # mounted share (test_oslink.py); they take arguments and are not suites.
        dirs[:] = sorted(d for d in dirs
                         if d not in ("__pycache__", "diagnostics") and not d.startswith("."))
        for fn in sorted(files):
            if fn.startswith("test_") and fn.endswith(".py"):
                found.append(os.path.relpath(os.path.join(base, fn), REPO_ROOT))
    return found


def select(suites, only=None, skip=None):
    out = []
    for s in suites:
        norm = s.replace(os.sep, "/")
        if only and not any(o in norm for o in only):
            continue
        if skip and any(k in norm for k in skip):
            continue
        out.append(s)
    return out


def run_one(rel_path, timeout=DEFAULT_TIMEOUT):
    """Run one suite; return dict(name, rc, seconds, output)."""
    abs_path = os.path.join(REPO_ROOT, rel_path)
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (TOOLS_DIR, REPO_ROOT, env.get("PYTHONPATH", "")) if p)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    t0 = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, os.path.basename(abs_path)],
            cwd=os.path.dirname(abs_path), env=env,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout,
        )
        rc, output = proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired as exc:
        rc = 124
        output = ((exc.stdout or b"").decode("utf-8", "replace") if isinstance(exc.stdout, bytes)
                  else (exc.stdout or "")) + f"\n[run_tests] TIMEOUT after {timeout}s"
    return {"name": rel_path.replace(os.sep, "/"), "rc": rc,
            "seconds": time.time() - t0, "output": output}


def report(result, verbose=False, out=sys.stdout):
    status = "PASS" if result["rc"] == 0 else "FAIL"
    print(f"{status}  {result['name']}  ({result['seconds']:.1f}s"
          + ("" if result["rc"] == 0 else f", exit {result['rc']}") + ")", file=out)
    if verbose or result["rc"] != 0:
        lines = result["output"].rstrip().splitlines()
        shown = lines if verbose else lines[-TAIL_LINES:]
        if not verbose and len(lines) > TAIL_LINES:
            print(f"      ... ({len(lines) - TAIL_LINES} earlier lines)", file=out)
        for line in shown:
            print(f"      {line}", file=out)


def main(argv=None):
    p = argparse.ArgumentParser(description="Run the tools/ test suites.")
    p.add_argument("--only", action="append", default=None, metavar="SUBSTR",
                   help="Run only suites whose path contains SUBSTR (repeatable).")
    p.add_argument("--skip", action="append", default=None, metavar="SUBSTR",
                   help="Skip suites whose path contains SUBSTR (repeatable).")
    p.add_argument("--list", action="store_true", help="List the suites and exit.")
    p.add_argument("-j", "--jobs", type=int, default=1, help="Suites to run at a time (default 1).")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Seconds per suite.")
    p.add_argument("--verbose", action="store_true", help="Print every suite's full output.")
    args = p.parse_args(argv)

    suites = select(discover(), args.only, args.skip)
    if args.list:
        for s in suites:
            print(s.replace(os.sep, "/"))
        return 0
    if not suites:
        print("no suites selected", file=sys.stderr)
        return 2

    print(f"running {len(suites)} suite(s) with {sys.executable}")
    t0 = time.time()
    results = []
    if args.jobs > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
            for r in ex.map(lambda s: run_one(s, args.timeout), suites):
                results.append(r)
                report(r, args.verbose)
    else:
        for s in suites:
            r = run_one(s, args.timeout)
            results.append(r)
            report(r, args.verbose)

    failed = [r["name"] for r in results if r["rc"] != 0]
    print()
    print(f"{len(results) - len(failed)} passed, {len(failed)} failed, "
          f"{time.time() - t0:.0f}s")
    for name in failed:
        print(f"  FAILED: {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
