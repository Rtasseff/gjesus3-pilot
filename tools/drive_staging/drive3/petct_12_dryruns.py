"""Stream N: the dry runs, each bracketed by a fingerprint of the target root's registries.

    python petct_12_dryruns.py <nas_root> <tag> <config> [<config> ...]

Runs `tools/ingest_raw.py --config <config> --nas-root <nas_root> --dry-run` from the worktree root
(PYTHONPATH=tools, no bytecode), logs to out\\dryrun_<tag>_<config stem>.log, and checks that the
registries under <nas_root> are byte-identical before and after (a dry run must write nothing).
"""
import os
import re
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import petct_10_bracket as n11_bracket  # noqa: E402

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))      # the repository root (tools/drive_staging/drive3/<this>)
OUT = r"D:\projects\gjesus3\drive3_streams\petct\out"


def summarize(log):
    s = {}
    for k, rx in (("total", r"^\s*Total:\s+(\d+)"), ("success", r"^\s*Success:\s+(\d+)"),
                  ("failed", r"^\s*Failed:\s+(\d+)")):
        m = re.search(rx, log, re.M)
        s[k] = int(m.group(1)) if m else None
    for k, rx in (("discovered", r"\[ni_flat\] (\d+) acquisition\(s\) discovered from (\d+) DICOM"),
                  ("skipped_registered", r"\[ni_flat\] (\d+) acquisition\(s\) skipped"),
                  ("held_back", r"\[ni_flat\] (\d+) acquisition\(s\) HELD BACK"),
                  ("found_higher", r"\[ni_flat\] (\d+) acquisition\(s\) had NO protocol code"),
                  ("recovered_wrong", r"\[ni_flat\] (\d+) acquisition\(s\) had a path-derived")):
        m = re.search(rx, log)
        s[k] = int(m.group(1)) if m else 0
    s["files_seen"] = int(re.search(r"discovered from (\d+) DICOM", log).group(1)) if "discovered from" in log else None
    s["case_table_skips"] = len(re.findall(r"has no row in auto_discover\.case_table", log))
    s["idempotent_skips"] = len(re.findall(r"already in registry \(idempotent re-run\)", log))
    s["link_free"] = len(re.findall(r"Link:\s+project link .* \(free\)", log))
    s["link_taken"] = len(re.findall(r"already taken|also planned for", log))
    s["no_project_link"] = len(re.findall(r"no project link", log))
    s["acq_ids"] = re.findall(r"Generated ACQ-ID: (ACQ-\S+)", log)
    return s


def main():
    root, tag, configs = sys.argv[1], sys.argv[2], sys.argv[3:]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=os.path.join(WT, "tools"),
               PYTHONIOENCODING="utf-8")
    for cfg in configs:
        stem = os.path.splitext(os.path.basename(cfg))[0]
        n11_bracket.snap(root, f"{tag}_{stem}_before")
        r = subprocess.run([sys.executable, os.path.join(WT, "tools", "ingest_raw.py"), "--config", cfg,
                            "--nas-root", root, "--dry-run"], cwd=WT, env=env, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        log = r.stdout + "\n--- stderr ---\n" + r.stderr
        with open(os.path.join(OUT, f"dryrun_{tag}_{stem}.log"), "w", encoding="utf-8") as f:
            f.write(log)
        n11_bracket.snap(root, f"{tag}_{stem}_after")
        changed = n11_bracket.compare(f"{tag}_{stem}_before", f"{tag}_{stem}_after")
        s = summarize(log)
        ids = s.pop("acq_ids")
        print(f"[{tag}] {stem}: rc={r.returncode} {s} registries changed={bool(changed)}")
        if r.returncode:
            print(r.stderr[-2000:])


if __name__ == "__main__":
    main()
