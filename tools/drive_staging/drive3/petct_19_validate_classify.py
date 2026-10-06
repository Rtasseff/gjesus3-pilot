"""Stream N: run tools/validate_registries.py on a NAS root and sort its findings into classes.

    python petct_19_validate_classify.py <nas_root> <tag> [--no-enrichment]

Every ERROR / WARN line is reduced to a class (acq id, paths and numbers stripped) and attributed to
"new" (one of the plan's 202, by the registry's original_name) or "old". On the rehearsal root the
27,120 production rows have no /raw/ folder there, so their "acquisition folder not found" ERROR is the
expected class; any other class, or any finding on a new row beyond the documented unknown sentinels,
is a finding. Writes out\\validate_<tag>.txt (the full report) and prints the classes.
"""
import collections
import csv
import io
import os
import re
import subprocess
import sys

sys.dont_write_bytecode = True
csv.field_size_limit(2 ** 31 - 1)
WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))      # the repository root (tools/drive_staging/drive3/<this>)
OUT = r"D:\projects\gjesus3\drive3_streams\petct\out"


def main():
    root, tag = sys.argv[1], sys.argv[2]
    args = [sys.executable, os.path.join(WT, "tools", "validate_registries.py"), "--nas-root", root]
    if "--no-enrichment" in sys.argv:
        args.append("--no-enrichment")
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=os.path.join(WT, "tools"),
               PYTHONIOENCODING="utf-8")
    r = subprocess.run(args, cwd=WT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    rep = r.stdout + "\n--- stderr ---\n" + r.stderr
    with open(os.path.join(OUT, f"validate_{tag}.txt"), "w", encoding="utf-8") as f:
        f.write(rep)
    plan = {p["acq_key"] for p in csv.DictReader(open(os.path.join(OUT, "plan_202.csv"), encoding="utf-8"))}
    with io.open(os.path.join(root, "registries", "registry_raw.csv"), encoding="utf-8-sig", newline="") as f:
        new_ids = {row["acq_id"] for row in csv.DictReader(f) if row["original_name"] in plan}
    classes = collections.Counter()
    for line in rep.splitlines():
        m = re.match(r"\s*(ERROR|WARN):\s+(?:\[([^\]]+)\]\s+)?(.*)$", line)
        if not m:
            continue
        level, acq, msg = m.groups()
        cls = re.sub(r"[A-Za-z]:[\\/][^ ]*|/raw/[^ ']*|ACQ-\d{8}-[A-Z]+-\d{3}|\d+", "#", msg)[:110]
        classes[(level, "new" if acq in new_ids else "old", cls)] += 1
    head = [l for l in rep.splitlines() if l.startswith(("rows checked", "errors:", "warnings:", "operator awaiting"))]
    print(f"[{tag}] rc={r.returncode}; " + "; ".join(head) + f"; new rows in this root: {len(new_ids)}")
    for (lvl, who, cls), n in sorted(classes.items(), key=lambda x: (-x[1], x[0])):
        print(f"   {n:6d}  {lvl:5s} {who:3s}  {cls}")


if __name__ == "__main__":
    main()
