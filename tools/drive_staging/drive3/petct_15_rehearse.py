"""Stream N: the rehearsal. The two batch configs run FOR REAL into the rehearsal NAS root on D:, then again
(the idempotent re-run), each bracketed by fingerprints of PRODUCTION's registries and of the 100 snapshot
source files (both must stay untouched: the rehearsal reads them only).

    python petct_15_rehearse.py first|rerun

Logs: out\\rehearsal_<phase>_<config stem>.log
"""
import json
import os
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import petct_10_bracket as n11_bracket  # noqa: E402
from petct_12_dryruns import summarize  # noqa: E402

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))      # the repository root (tools/drive_staging/drive3/<this>)
OUT = r"D:\projects\gjesus3\drive3_streams\petct\out"
REH = "D:/projects/gjesus3/drive3_streams/petct/rehearsal_nas"
PROD = "J:/gjesus3-data"
SNAP = r"J:\gjesus3-data\staging\ni_gnuclear_20260812"
CONFIGS = ["tools/configs/drive3_petct/drive3_petct_snapshot.yaml",
           "tools/configs/drive3_petct/drive3_petct_drive.yaml"]


def snapshot_sources(label):
    import csv
    plan = [r for r in csv.DictReader(open(os.path.join(OUT, "plan_202.csv"), encoding="utf-8"))
            if r["source"] == "snapshot"]
    d = {}
    for r in plan:
        p = os.path.join(SNAP, r["source_rel"].replace("/", os.sep))
        st = os.stat(p)
        d[r["source_rel"]] = [st.st_size, st.st_mtime_ns]
    with open(os.path.join(OUT, f"sources_{label}.json"), "w", encoding="utf-8") as f:
        json.dump(d, f)
    return d


def main():
    phase = sys.argv[1]
    assert os.path.isdir(os.path.join(REH, "registries"))
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=os.path.join(WT, "tools"),
               PYTHONIOENCODING="utf-8")
    n11_bracket.snap(PROD, f"reh_{phase}_prod_before")
    src_before = snapshot_sources(f"reh_{phase}_before")
    for cfg in CONFIGS:
        stem = os.path.splitext(os.path.basename(cfg))[0]
        cmd = [sys.executable, os.path.join(WT, "tools", "ingest_raw.py"), "--config", cfg, "--nas-root", REH]
        assert "--dry-run" not in cmd and cmd[-1] == REH
        r = subprocess.run(cmd, cwd=WT, env=env, capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        log = r.stdout + "\n--- stderr ---\n" + r.stderr
        with open(os.path.join(OUT, f"rehearsal_{phase}_{stem}.log"), "w", encoding="utf-8") as f:
            f.write(log)
        s = summarize(log)
        ids = s.pop("acq_ids")
        print(f"[rehearsal {phase}] {stem}: rc={r.returncode} {s} first/last id: {ids[:1]} {ids[-1:]}")
    n11_bracket.snap(PROD, f"reh_{phase}_prod_after")
    n11_bracket.compare(f"reh_{phase}_prod_before", f"reh_{phase}_prod_after")
    src_after = snapshot_sources(f"reh_{phase}_after")
    print("snapshot source files unchanged (size, mtime):", src_before == src_after)


if __name__ == "__main__":
    main()
