"""Stream N: check a dry-run (or real-run) log case by case against the plan (out\\plan_202.csv).

    python petct_13_check_log.py <log> <source: snapshot|drive>

For every case block of the log: original name, instrument, acquisition date, the project link the
pre-flight planned (project + link name), and the ACQ-ID prefix. Each must equal what the plan decided;
the set of cases must equal the plan's set for that source exactly.
"""
import csv
import os
import re
import sys

sys.dont_write_bytecode = True
OUT = r"D:\projects\gjesus3\drive3_streams\petct\out"


def blocks(log):
    parts = re.split(r"\n\[[0-9:]+\] INFO: Case \d+/\d+: ", log)
    return parts[1:]


def main():
    log = open(sys.argv[1], encoding="utf-8").read()
    source = sys.argv[2]
    plan = {p["acq_key"]: p for p in csv.DictReader(open(os.path.join(OUT, "plan_202.csv"), encoding="utf-8"))
            if p["source"] == source}
    seen, bad = set(), []
    for b in blocks(log):
        def g(rx):
            m = re.search(rx, b, re.M)
            return m.group(1).strip() if m else ""
        orig = g(r"Original:\s+(.+)$")
        inst = g(r"Instrument:\s+(\S+)")
        adate = g(r"Acq Date:\s+(\d+)")
        acq = g(r"Generated ACQ-ID: (ACQ-\S+)")
        link = g(r"Link:\s+project link (.+?) \((?:free|the project will be created)\)")
        p = plan.get(orig)
        if not p:
            bad.append(f"{orig}: not in the plan")
            continue
        seen.add(orig)
        exp_link = (f"{p['project_name']}/raw_linked/{p['modality']}_{p['subject']}_{p['acq_date']}_"
                    f"{p['acq_key'][:14]}_recon{p['acq_key'].split('_')[3]}") if p["project_name"] else ""
        probs = []
        if inst != p["modality"]:
            probs.append(f"instrument {inst} != {p['modality']}")
        if adate != p["acq_date"]:
            probs.append(f"date {adate} != {p['acq_date']}")
        if not acq.startswith(f"ACQ-{p['acq_date']}-{p['modality']}-"):
            probs.append(f"ACQ-ID {acq}")
        if link != exp_link:
            probs.append(f"link {link!r} != {exp_link!r}")
        if probs:
            bad.append(f"{orig}: " + "; ".join(probs))
    missing = sorted(set(plan) - seen)
    print(f"{os.path.basename(sys.argv[1])}: cases {len(seen)} of the plan's {len(plan)} ({source}); "
          f"missing {len(missing)}; disagreements {len(bad)}")
    for x in missing[:10]:
        print("   missing:", x)
    for x in bad[:20]:
        print("   ", x)
    return 1 if (missing or bad) else 0


if __name__ == "__main__":
    sys.exit(main())
