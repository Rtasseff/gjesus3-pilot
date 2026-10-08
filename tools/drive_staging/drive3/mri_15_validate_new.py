"""Stream M: run validate_registries.py on a root and split its findings into "on stream M's rows" and "other" (read-only).

    python mri_15_validate_new.py <nas_root> <tag> [--full]

Stream M's rows are those whose ingest_config is under tools/configs/drive3_mri/. In the rehearsal root, production's
own rows have no /raw/ folder, so they fail by design; what matters is that the new rows add nothing. --full also runs
the enrichment (sidecar) checks. Writes out\\validate_<tag>.txt.
"""
import collections
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mri_common as C  # noqa: E402


def main():
    root, tag = sys.argv[1], sys.argv[2]
    full = "--full" in sys.argv
    mine = {r["acq_id"] for r in C.live_registry(root) if "drive3_mri/" in r["ingest_config"].replace("\\", "/")}
    cmd = [sys.executable, os.path.join(C.WT, "tools", "validate_registries.py"), "--nas-root", root]
    if not full:
        cmd.append("--no-enrichment")
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=os.path.join(C.WT, "tools"), PYTHONIOENCODING="utf-8")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=C.WT)
    out = r.stdout + r.stderr
    open(C.out(f"validate_{tag}.txt"), "w", encoding="utf-8").write(out)
    lines = [l for l in out.splitlines() if re.search(r"\b(ERROR|WARN)\b", l)]
    on_mine, other = collections.Counter(), collections.Counter()
    for l in lines:
        ids = set(re.findall(r"ACQ-\d{8}-[A-Z]+-\d{3}", l))
        cls = re.sub(r"ACQ-\d{8}-[A-Z]+-\d{3}|\d+", "N", l.split("] ", 1)[-1])[:140]
        (on_mine if ids & mine else other)[cls] += 1
    info = [l for l in out.splitlines() if "pending-claim" in l or "validation" in l.lower()][-4:]
    print(f"stream-M rows in this root: {len(mine)}; findings on them: {sum(on_mine.values())}; other findings: "
          f"{sum(other.values())} in {len(other)} classes")
    for k, n in on_mine.most_common(10):
        print(f"  ON NEW ROWS {n}: {k}")
    for k, n in other.most_common(5):
        print(f"  other {n}: {k}")
    for l in info:
        print("  ", l.strip()[:200])


if __name__ == "__main__":
    main()
