"""Stream AR: run ingest_raw.py on configs, each bracketed by a fingerprint of the target root's registries.

    python ar_09_run.py <nas_root> <tag> [--real] [--refresh-index=projects] <config> [<config> ...]

Stream M's runner (tools/drive_staging/drive3/mri_07_dryruns.py) for this stream's paths. Without --real:
`ingest_raw.py --config <c> --nas-root <root> --dry-run`, and the registries under <root> must be byte-identical
before and after. --real runs only against this stream's rehearsal root (refuses J: and anything else).
Logs: out\\<dryrun|run>_<tag>_<config stem>.log; fingerprints out\\bracket_*.json.
"""
import hashlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ar_common as C  # noqa: E402

sys.path.insert(0, os.path.join(C.WT, "tools", "drive_staging", "drive3"))
from mri_07_dryruns import summarize  # noqa: E402  (pure: parses a log)


def snap(root, label):
    reg = os.path.join(root, "registries")
    d = {}
    for n in sorted(os.listdir(reg)):
        p = os.path.join(reg, n)
        if os.path.isfile(p):
            st = os.stat(p)
            d[n] = [st.st_size, st.st_mtime_ns, hashlib.sha256(open(p, "rb").read()).hexdigest()]
    json.dump({"root": root, "files": d}, open(C.out(f"bracket_{label}.json"), "w", encoding="utf-8"), indent=1)
    return d


def main():
    args = sys.argv[1:]
    real = "--real" in args
    extra = ["--refresh-index", "projects"] if "--refresh-index=projects" in args else []
    args = [a for a in args if a not in ("--real", "--refresh-index=projects")]
    root, tag, configs = args[0], args[1], args[2:]
    if real and os.path.abspath(root).lower() != C.REH.lower():
        raise SystemExit(f"--real runs only against the rehearsal root {C.REH}")
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=os.path.join(C.WT, "tools"), PYTHONIOENCODING="utf-8")
    rc_all = 0
    for cfg in configs:
        stem = os.path.splitext(os.path.basename(cfg))[0]
        before = snap(root, f"{tag}_{stem}_before")
        cmd = [sys.executable, os.path.join(C.WT, "tools", "ingest_raw.py"), "--config", cfg, "--nas-root", root] + extra
        if not real:
            cmd.append("--dry-run")
        r = subprocess.run(cmd, cwd=C.WT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
        log = r.stdout + "\n--- stderr ---\n" + r.stderr
        open(C.out(f"{'run' if real else 'dryrun'}_{tag}_{stem}.log"), "w", encoding="utf-8").write(log)
        after = snap(root, f"{tag}_{stem}_after")
        changed = sorted(n for n in set(before) | set(after) if before.get(n) != after.get(n))
        s = summarize(log)
        print(f"[{tag}] {stem}: rc={r.returncode} {s} registries changed={changed if changed else False}", flush=True)
        if r.returncode:
            rc_all = 1
            print(r.stderr[-1500:])
        if not real and changed:
            rc_all = 1
    sys.exit(rc_all)


if __name__ == "__main__":
    main()
