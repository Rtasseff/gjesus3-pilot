#!/usr/bin/env python3
"""a2_verify_placed.py -- are the drives-1+2 copies that drive-3 files are deduplicated against REALLY on
the NAS? For every A2 file the plan calls already-placed / already-in-holding, stat (read-only) each
indexed copy with the same SHA-256 and compare its size. No sampling: every file.

Output: a2\\placement\\verify_placed.txt.
"""
import collections
import concurrent.futures as cf
import os

import a2_common as C


def main():
    C.stdout_utf8()
    plan = [f for f in C.it(os.path.join(C.OUT, "placement", "placement_plan.csv"))
            if f["dec_rec"] in ("already-placed", "already-in-holding")]
    want = collections.defaultdict(set)
    for f in plan:
        want[f["sha256"]].add(int(f["size"]))
    targets = []
    proj_dir = os.path.join(C.NAS, "projects")
    for folder in sorted(os.listdir(proj_dir)):
        base = os.path.join(proj_dir, folder, "working", "historical_drives")
        idx = os.path.join(base, C.H.INDEX_NAME)
        if os.path.isfile(idx):
            for r in C.it(idx):
                if r.get("sha256") in want:
                    targets.append((r["sha256"], os.path.join(base, r["new_path"])))
    hbase = os.path.dirname(C.HOLDING_MANIFEST)
    for r in C.it(C.HOLDING_MANIFEST):
        if r.get("sha256") in want:
            targets.append((r["sha256"], os.path.join(hbase, r["new_path"])))

    def check(t):
        sha, p = t
        try:
            st = os.stat(C.LONG + p)
            return sha, "ok" if st.st_size in want[sha] else f"size {st.st_size}"
        except OSError as e:
            return sha, f"missing ({type(e).__name__})"

    res = collections.Counter()
    sha_ok = set()
    with cf.ThreadPoolExecutor(16) as ex:
        for sha, st in ex.map(check, targets):
            res[st.split(" ")[0]] += 1
            if st == "ok":
                sha_ok.add(sha)
    covered = sum(1 for f in plan if f["sha256"] in sha_ok)
    lines = [f"drive-3 files deduplicated against drives 1+2: {len(plan):,} ({len(want):,} distinct contents)",
             f"indexed NAS copies with those contents: {len(targets):,}; stat result: {dict(res)}",
             f"drive-3 files with at least one verified NAS copy (exists, same size): {covered:,} of {len(plan):,}"]
    for ln in lines:
        print(ln)
    with open(os.path.join(C.OUT, "placement", "verify_placed.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
