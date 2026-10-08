"""Stream AR: check a dry-run log case by case against its case table (read-only).

    python ar_10_check_log.py <log> <batch>       e.g. out\\dryrun_pre_mri_archive_AR01_0118.log AR01_0118
    python ar_10_check_log.py <log> DEDUP

Batches (stream M's mri_14_check_log.py, plus the skip set): every row of cases_<batch>.csv previewed exactly once
(`Original:`), with the ACQ date of its case-table datetime, instrument MRI, and -- when it has a project -- a project
link "(free)" under the planned name (out\\link_names.csv); none dated 2026; nothing previewed that is not in the table;
and the exams skipped "no row in auto_discover.case_table" are exactly the batch's exams NOT registered
(out\\plan_exams.csv not-registered + out\\not_registered_after_convert.csv).
DEDUP: nothing previewed; every row of cases_DEDUP.csv skipped "already in registry"; the other skips are by name.
"""
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ar_common as C  # noqa: E402

SKIP_RE = re.compile(r"\[expand_batch\] SKIP[^\n]*?(\d{8}_\d{6}_[^\s/\\]+[/\\][0-9][^\s:'\"]*)[^\n]*")


def skipped(text, why):
    out = collections.Counter()
    for line in text.splitlines():
        if "[expand_batch] SKIP" in line and why in line:
            m = SKIP_RE.search(line)
            if m:
                out[m.group(1).replace("\\", "/").rstrip("/")] += 1
    return out


def main():
    log, batch = sys.argv[1], sys.argv[2]
    text = open(log, encoding="utf-8").read()
    cases = {c["original_name"]: c for c in C.rows(os.path.join(C.CFG_DIR, f"cases_{batch}.csv"))}
    blocks = re.split(r"Generated ACQ-ID: ", text)[1:]
    if batch == "DEDUP":
        reg = skipped(text, "already in registry")
        noc = skipped(text, "has no row in auto_discover.case_table")
        missing = [k for k in cases if k not in reg]
        print(f"DEDUP: cases {len(cases)}; previewed {len(blocks)}; skipped as registered {sum(reg.values())} "
              f"(of the cases: {sum(1 for k in cases if k in reg)}); skipped by name {sum(noc.values())}; "
              f"cases not skipped as registered {len(missing)} {missing[:5]}")
        sys.exit(1 if blocks or missing else 0)
    links = {l["original_name"]: l for l in C.rows(os.path.join(C.OUT, "link_names.csv"))}
    seen, bad = collections.Counter(), []
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
        if "Instrument:  MRI" not in b:
            bad.append(f"{on}: instrument")
        lk = re.search(r"Link:\s+(.*)", b)
        lk = lk.group(1) if lk else ""
        if c["drv_project"]:
            want = links[on]["link_name"] if on in links else ""
            if "(free)" not in lk or (want and want not in lk):
                bad.append(f"{on}: link '{lk[:140]}' (want {want} free)")
        elif lk and "no project link" not in lk:
            bad.append(f"{on}: expected no project link, got '{lk[:80]}'")
    missing = [k for k in cases if seen[k] == 0]
    twice = [k for k, n in seen.items() if n > 1]
    plan = [x for x in C.rows(os.path.join(C.OUT, "plan_exams.csv")) if x["batch"] == batch]
    nra = os.path.join(C.OUT, "not_registered_after_convert.csv")
    after = {x["original_name"] for x in C.rows(nra)} if os.path.exists(nra) else set()
    want_skip = {x["original_name"] for x in plan if x["disposition"] == "not-registered"} | \
                {x["original_name"] for x in plan if x["original_name"] in after}
    got_skip = set(skipped(text, "has no row in auto_discover.case_table"))
    skip_diff = sorted(want_skip ^ got_skip)
    print(f"{batch}: cases {len(cases)}; previewed {sum(seen.values())}; missing {len(missing)}; twice {len(twice)}; "
          f"disagreements {len(bad)}; skipped by name {len(got_skip)} (planned not-registered {len(want_skip)}; "
          f"differ {len(skip_diff)})")
    for x in (bad + [f"missing {m}" for m in missing] + [f"skip set differs: {d}" for d in skip_diff])[:12]:
        print("   ", x)
    sys.exit(1 if bad or missing or twice or skip_diff else 0)


if __name__ == "__main__":
    main()
