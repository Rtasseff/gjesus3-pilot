"""Stream N: everything after the first rehearsal run, in order, logged to out\\post_rehearsal.txt.

  1. the independent verifier against the baseline (out\\_inputs\\rehearsal_base)
  2. the validator, classified (no-enrichment and full)
  3. the ACQ-ID ranges given
  4. the idempotent re-run of both batches (for real, into the rehearsal root)
  5. dry runs against the rehearsal root: census, dedup proof, and the snapshot backfill re-run
     (IAZ_MJ, MJ, Marina): the 100 must now be skipped as registered
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REH = "D:/projects/gjesus3/drive3_streams/petct/rehearsal_nas"
BASE = r"D:\projects\gjesus3\drive3_streams\petct\out\_inputs\rehearsal_base"
STEPS = [
    ["petct_16_verify.py", REH, BASE],
    ["petct_19_validate_classify.py", REH, "reh_noenrich", "--no-enrichment"],
    ["petct_19_validate_classify.py", REH, "reh_full"],
    ["petct_21_acq_ranges.py", REH],
    ["petct_15_rehearse.py", "rerun"],
    ["petct_12_dryruns.py", REH, "reh",
     "tools/configs/drive3_petct/drive3_petct_census.yaml",
     "tools/configs/drive3_petct/drive3_petct_dedup_proof.yaml",
     "tools/configs/ni_gnuclear_prod_IAZ_MJ.yaml",
     "tools/configs/ni_gnuclear_prod_MJ.yaml",
     "tools/configs/ni_gnuclear_prod_Marina.yaml"],
]


def main():
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    for step in STEPS:
        print(f"\n######## {' '.join(step)}", flush=True)
        r = subprocess.run([sys.executable, "-u", os.path.join(HERE, step[0])] + step[1:], cwd=HERE, env=env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(r.stdout, flush=True)
        if r.stderr.strip():
            print("--- stderr ---\n" + r.stderr[-3000:], flush=True)
        print(f"(exit {r.returncode})", flush=True)


if __name__ == "__main__":
    main()
