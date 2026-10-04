#!/usr/bin/env python3
"""r4_index_rehearsal.py -- rehearse `r4_groups.py index --execute` on a SCRATCH copy of the six project trees.

ONE-TIME smoke test for stream D's index step (close-out plan Step 5 item 3). It never touches production: it builds
<OUT>\\rehearsal_nas\\gjesus3-data (OUT = D:\\projects\\gjesus3\\staging\\_analysis\\drives-r4-cleanup), copies
registry_projects.csv and each target project's `_INDEX.csv` / `_PATHMAP.csv` from the NAS (read-only), creates the
destination files of the lists at their exact sizes (zero-filled, as the retire run would have placed them), and runs
`r4_groups.py --nas <scratch> index ...` through its steps:

  1. nothing placed: the dry run reports 0 present; --execute refuses; the scratch indexes are untouched
  2. the scalebars placed: --execute adds exactly their rows, leaves every row of stream A's untouched and in order,
     adds only new folders to _PATHMAP.csv, writes UTF-8 BOM + CRLF, leaves no temp file
  3. the same list again: byte-identical (idempotent)
  4. the exports on top: 63 retired-derivative rows in all, A's rows still untouched (the folders of the WHOLE plan
     were frozen at step 2, so a later list cannot drift)
  5. a tampered index row is a conflict: REFUSED, nothing written
  6. a destination file that is gone: REFUSED

Run:  python tools/drive_staging/r4_index_rehearsal.py      (about a minute; writes ~1.6 GB of zero-filled files to D:)
It deletes and rebuilds its own scratch folder each time. Exit 0 = every check passed.
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r4_destinations as D  # noqa: E402
import r4_groups as R  # noqa: E402

REAL = R.NAS
SCRATCH_ROOT = os.path.join(R.OUT, "rehearsal_nas")
SCR = os.path.join(SCRATCH_ROOT, "gjesus3-data")
PROJECTS = ["AE-biomaGUNE-0219", "AE-biomaGUNE-0420", "AE-biomaGUNE-0721", "AE-biomaGUNE-1019", "AE-biomaGUNE-1123",
            "AE-biomaGUNE-1321"]
FAILS = []


def check(cond, msg):
    print(f"  {'ok:  ' if cond else 'FAIL:'} {msg}")
    if not cond:
        FAILS.append(msg)


def main():
    H, NP = D.load_stream_a()

    def run(*args):
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
        p = subprocess.run([sys.executable, "-B", os.path.join(HERE, "r4_groups.py"), "--nas", SCR, *args],
                           capture_output=True, text=True, encoding="utf-8", env=env)
        return p.returncode, p.stdout + p.stderr

    def rd(path):
        return R.rcsv(NP.lp(path))

    def tree(proj):
        return os.path.join(SCR, "projects", proj, "working", "historical_drives")

    def retired(rows):
        return [r for r in rows if "retired derivative" in (r.get("note") or "")]

    # a clean scratch (the paths pass 260 characters here: the \\?\ form)
    assert SCRATCH_ROOT.startswith(R.OUT) and SCRATCH_ROOT.endswith("rehearsal_nas")
    if os.path.exists(SCRATCH_ROOT):
        shutil.rmtree(NP.lp(SCRATCH_ROOT))
    os.makedirs(os.path.join(SCR, "registries"))
    shutil.copy2(os.path.join(REAL, "registries", "registry_projects.csv"), os.path.join(SCR, "registries"))
    for proj in PROJECTS:
        os.makedirs(tree(proj))
        for name in ("_INDEX.csv", "_PATHMAP.csv"):
            shutil.copy2(os.path.join(REAL, "projects", proj, "working", "historical_drives", name), os.path.join(tree(proj), name))
    before = {p: rd(os.path.join(tree(p), "_INDEX.csv")) for p in PROJECTS}
    members = {m["acq_id"]: m for m in R.rcsv(os.path.join(R.OUT, "members.csv"))}
    print("scratch NAS:", SCR)

    def place(listname):
        n = 0
        for r in R.rcsv(os.path.join(R.RETIRE_LISTS, R.LIST_FILES[R.LIST_SHORT[listname]])):
            p = NP.lp(os.path.join(SCR, "projects", r["to_project"], r["subfolder"], r["dest_name"]))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as f:
                f.truncate(int(members[r["acq_id"]]["size"]))
            n += 1
        return n

    print("\n1. nothing placed yet")
    rc, out = run("index", "--lists", "scalebars")
    check(rc == 0 and "destination files present: 0/3" in out and "nothing written" in out, "dry run: 0/3 present, nothing written")
    rc, out = run("index", "--lists", "scalebars", "--execute")
    check(rc == 1 and "REFUSED" in out, "--execute refuses while the files are not at their destinations")
    check(all(rd(os.path.join(tree(p), "_INDEX.csv")) == before[p] for p in PROJECTS), "and the scratch indexes are untouched")

    print("\n2. scalebars placed: execute")
    check(place("scalebars") == 3, "3 scale-bar copies placed")
    rc, out = run("index", "--lists", "scalebars", "--execute")
    check(rc == 0 and "verified" in out, "--execute succeeds and verifies")
    for proj in PROJECTS:
        rows = rd(os.path.join(tree(proj), "_INDEX.csv"))
        kept = [r for r in rows if r not in retired(rows)]
        check(kept == before[proj] and len(rows) == len(before[proj]) + len(retired(rows)),
              f"{proj}: every existing index row unchanged and in order, {len(retired(rows))} added")
    raw = open(NP.lp(os.path.join(tree("AE-biomaGUNE-0721"), "_INDEX.csv")), "rb").read()
    check(raw.startswith(b"\xef\xbb\xbf") and raw.count(b"\n") == raw.count(b"\r\n"), "UTF-8 BOM and CRLF only, like A's")
    check(not [f for f in os.listdir(tree("AE-biomaGUNE-0721")) if f.endswith(".tmp")], "no temp file left behind")

    print("\n3. the same list again")
    snap = {p: open(NP.lp(os.path.join(tree(p), "_INDEX.csv")), "rb").read() for p in PROJECTS}
    rc, out = run("index", "--lists", "scalebars", "--execute")
    check(rc == 0 and all(open(NP.lp(os.path.join(tree(p), "_INDEX.csv")), "rb").read() == snap[p] for p in PROJECTS),
          "a second --execute leaves every index byte-identical")

    print("\n4. the exports on top")
    check(place("exports") == 60, "60 small exports placed")
    rc, out = run("index", "--lists", "exports", "--execute")
    total = sum(len(retired(rd(os.path.join(tree(p), "_INDEX.csv")))) for p in PROJECTS)
    check(rc == 0 and total == 63, f"--execute succeeds: {total} retired-derivative rows in all (3 + 60)")
    for proj in PROJECTS:
        rows = rd(os.path.join(tree(proj), "_INDEX.csv"))
        check([r for r in rows if r not in retired(rows)] == before[proj], f"{proj}: A's rows still unchanged and in order")

    print("\n5. a tampered row is a conflict")
    p1321 = os.path.join(tree("AE-biomaGUNE-1321"), "_INDEX.csv")
    good = open(NP.lp(p1321), "rb").read()
    rows = rd(p1321)
    retired(rows)[0]["sha256"] = "0" * 64
    header = D.read_header(NP.lp(p1321))              # read before the file is opened for writing
    with open(NP.lp(p1321), "wb") as f:
        f.write(D.serialize_index(rows, H, header))
    snap = open(NP.lp(p1321), "rb").read()
    rc, out = run("index", "--lists", "exports", "--execute")
    check(rc == 1 and "different row" in out and open(NP.lp(p1321), "rb").read() == snap, "REFUSED, and the index is left as it was")
    with open(NP.lp(p1321), "wb") as f:
        f.write(good)

    print("\n6. a missing file")
    victim = R.rcsv(os.path.join(R.RETIRE_LISTS, R.LIST_FILES["b"]))[0]
    os.remove(NP.lp(os.path.join(SCR, "projects", victim["to_project"], victim["subfolder"], victim["dest_name"])))
    rc, out = run("index", "--lists", "exports", "--execute")
    check(rc == 1 and "REFUSED" in out, "a destination file that is gone: REFUSED")
    rc, out = run("index", "--lists", "exports")
    check("destination files present: 59/60" in out, "the dry run counts 59/60")

    print()
    print(("REHEARSAL FAILED: " + "; ".join(FAILS)) if FAILS else "REHEARSAL PASSED")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
