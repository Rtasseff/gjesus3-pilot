"""Stream M: run ingest_raw.py on a list of configs, each bracketed by a fingerprint of the target root's registries.

    python mri_07_dryruns.py <nas_root> <tag> [--real] [--refresh-index=projects] <config> [<config> ...]

Without --real: `ingest_raw.py --config <c> --nas-root <root> --dry-run`, and the registries under <root> must be
byte-identical before and after (a dry run writes nothing). With --real (the rehearsal root only; refuses J:): the
real run, logged the same way. Logs: out\\<dryrun|run>_<tag>_<config stem>.log; fingerprints out\\bracket_*.json.
Prints, per config: rc, Total / Success / Failed, the SKIP reasons, the link pre-flight counts, ACQ-ID dates, and
whether the registries changed.
"""
import collections
import hashlib
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mri_common as C  # noqa: E402


def snap(root, label):
    reg = os.path.join(root, "registries")
    d = {}
    for n in sorted(os.listdir(reg)):
        p = os.path.join(reg, n)
        if os.path.isfile(p):
            st = os.stat(p)
            h = hashlib.sha256(open(p, "rb").read()).hexdigest()
            d[n] = [st.st_size, st.st_mtime_ns, h]
    json.dump({"root": root, "files": d}, open(C.out(f"bracket_{label}.json"), "w", encoding="utf-8"), indent=1)
    return d


def summarize(log):
    s = {}
    for k, rx in (("total", r"^\s*Total:\s+(\d+)"), ("success", r"^\s*Success:\s+(\d+)"),
                  ("failed", r"^\s*Failed:\s+(\d+)")):
        m = re.search(rx, log, re.M)
        s[k] = int(m.group(1)) if m else None
    s["skip_registered"] = len(re.findall(r"already in registry \(idempotent re-run\)", log))
    s["skip_case_table"] = len(re.findall(r"has no row in auto_discover\.case_table", log))
    s["skip_other"] = len(re.findall(r"\[expand_batch\] SKIP", log)) - s["skip_registered"] - s["skip_case_table"]
    s["not_parsed_lines"] = len(re.findall(r"NOT PARSED", log))
    s["link_free"] = len(re.findall(r"Link:\s+project link .*\(free\)", log))
    s["link_taken"] = len(re.findall(r"already taken|also planned for", log))
    s["no_project_link"] = len(re.findall(r"no project link", log))
    s["errors"] = len(re.findall(r"\] ERROR:", log))
    s["warns"] = collections.Counter(re.sub(r"ACQ-\S+|\d+", "N", m)[:90] for m in re.findall(r"WARN: (.*)", log)).most_common(6)
    s["today"] = len(re.findall(r"Generated ACQ-ID: ACQ-2026", log))
    s["acq_dates"] = dict(collections.Counter(m[:4] for m in re.findall(r"Generated ACQ-ID: ACQ-(\d{8})", log)))
    return s


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
        cmd = [sys.executable, os.path.join(C.WT, "tools", "ingest_raw.py"), "--config", cfg, "--nas-root", root]
        cmd += extra
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
