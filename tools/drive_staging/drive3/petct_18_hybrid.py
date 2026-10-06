"""Stream N: how the Molecubes PET and CT of one animal visit relate in DICOM, and how production groups them.

Read-only. For the 492 drive reconstructions (out\\acq_header_check.csv):
  - per StudyInstanceUID, which modalities it holds (one DICOM Study per animal visit = PET + CT?);
For the 290 that production already holds: does production's session_id group exactly the
reconstructions that share a StudyInstanceUID (the registry snapshot taken by n02)?
For the 202: the same grouping as the plan's session_id (<subject>_<date8>).
"""
import collections
import csv
import glob
import os
import sys

sys.dont_write_bytecode = True
csv.field_size_limit(2 ** 31 - 1)
OUT = r"D:\projects\gjesus3\drive3_streams\petct\out"


def main():
    hdr = list(csv.DictReader(open(os.path.join(OUT, "acq_header_check.csv"), encoding="utf-8")))
    inv = {r["acq_key"]: r for r in csv.DictReader(open(os.path.join(OUT, "acq_inventory.csv"), encoding="utf-8"))}
    plan = {r["acq_key_a1"]: r for r in csv.DictReader(open(os.path.join(OUT, "plan_202.csv"), encoding="utf-8"))}
    reg = list(csv.DictReader(open(sorted(glob.glob(os.path.join(OUT, "_inputs", "2*", "registry_raw.csv")))[-1],
                                   encoding="utf-8-sig", newline="")))
    by_acq = {r["acq_id"]: r for r in reg}
    by_study = collections.defaultdict(list)
    for h in hdr:
        by_study[h["StudyInstanceUID"]].append(h)
    shape = collections.Counter(tuple(sorted(x["modality_hdr"] for x in v)) for v in by_study.values())
    print(f"drive reconstructions: {len(hdr)}; DICOM studies: {len(by_study)}")
    for k, v in shape.most_common():
        print(f"   {v:4d} studies hold {k}")
    # production's session_id vs the DICOM study, for the 290
    agree = disagree = 0
    ex = []
    for uid, v in by_study.items():
        inprod = [x for x in v if x["coverage"].startswith("in production")]
        if len(inprod) < 2:
            continue
        sess = set()
        for x in inprod:
            a = by_acq.get(inv[x["acq_key"]]["prod_acq_id_by_sha"])
            sess.add(a["session_id"] if a else "?")
        if len(sess) == 1:
            agree += 1
        else:
            disagree += 1
            ex.append((uid[-12:], sorted(sess)))
    print(f"in production, studies with >= 2 reconstructions: session_id the same for all {agree}, "
          f"split {disagree}")
    for e in ex[:8]:
        print("   ", e)
    # the plan's session_id vs the DICOM study, for the 202
    agree = disagree = 0
    ex = []
    for uid, v in by_study.items():
        ours = [x for x in v if x["acq_key"] in plan]
        if len(ours) < 2:
            continue
        sess = {f"{plan[x['acq_key']]['subject']}_{plan[x['acq_key']]['acq_date']}" for x in ours}
        if len(sess) == 1:
            agree += 1
        else:
            disagree += 1
            ex.append((uid[-12:], sorted(sess), [x["acq_key"] for x in ours]))
    print(f"stream N, studies with >= 2 of the 202: one session_id {agree}, split {disagree}")
    for e in ex[:8]:
        print("   ", e)


if __name__ == "__main__":
    main()
