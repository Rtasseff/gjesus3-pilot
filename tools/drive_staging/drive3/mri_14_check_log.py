"""Stream M: check a dry-run log case by case against its case table (read-only).

    python mri_14_check_log.py <log> <batch>          e.g. out\\dryrun_prod_drive3_mri_M01_0118.log M01

Every row of tools/configs/drive3_mri/cases_<batch>.csv must be previewed exactly once (its `Original:` line), with
the ACQ date of its case-table datetime, an instrument of MRI (XMRI for P01), and, when it has a project, a project link
reported "(free)" under the planned name; no row may be previewed that is not in the table, and none dated 2026.
"""
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mri_common as C  # noqa: E402


def main():
    log, batch = sys.argv[1], sys.argv[2]
    cases = {c["original_name"]: c for c in C.rows(os.path.join(C.CFG_DIR, f"cases_{batch}.csv"))}
    links = {l["original_name"]: l for l in C.rows(os.path.join(C.OUT, "link_names.csv"))} if batch != "P01" else {}
    text = open(log, encoding="utf-8").read()
    blocks = re.split(r"Generated ACQ-ID: ", text)[1:]
    seen = collections.Counter()
    bad = []
    for b in blocks:
        acq = b.split()[0]
        m = re.search(r"Original:\s+(\S+)", b)
        if not m:
            continue
        on = m.group(1).replace("\\", "/").rstrip("/")
        seen[on] += 1
        c = cases.get(on)
        if not c:
            bad.append(f"{on}: previewed, not in the case table")
            continue
        d8 = c["drv_acq_datetime"][:10].replace("-", "")
        if f"Acq Date:    {d8}" not in b or not acq.startswith(f"ACQ-{d8}-"):
            bad.append(f"{on}: date {acq} vs case {d8}")
        if acq.startswith("ACQ-2026"):
            bad.append(f"{on}: dated 2026")
        inst = "XMRI" if batch == "P01" else "MRI"
        if f"Instrument:  {inst}" not in b:
            bad.append(f"{on}: instrument")
        lk = re.search(r"Link:\s+(.*)", b)
        lk = lk.group(1) if lk else ""
        proj = c.get("drv_project", "CNIC-HEARDS" if batch == "P01" else "")
        if proj:
            want = links[on]["link_name"] if on in links else ""
            if "(free)" not in lk or (want and want not in lk):
                bad.append(f"{on}: link '{lk[:120]}' (want {want} free)")
        elif lk and "no project link" not in lk:
            bad.append(f"{on}: expected no project link, got '{lk[:80]}'")
    missing = [k for k in cases if seen[k] == 0]
    twice = [k for k, n in seen.items() if n > 1]
    print(f"{batch}: cases {len(cases)}; previewed {sum(seen.values())}; missing {len(missing)}; twice {len(twice)}; "
          f"disagreements {len(bad)}")
    for x in (bad + [f"missing {m}" for m in missing])[:12]:
        print("   ", x)
    sys.exit(1 if bad or missing or twice else 0)


if __name__ == "__main__":
    main()
