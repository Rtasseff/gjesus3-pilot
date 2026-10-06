"""Stream N, step 7: what sits beside the 202 reconstructions on the drive, and where A2 plans it (read-only).

For every drive copy of the 202 (all copies, not only the canonical one), lists the other files of the same
folder from A2's file table (D:\\projects\\gjesus3\\drive3_analysis\\a2\\files.csv: owner, class) and the
decision A2's placement plan gives each (placement\\placement_plan.csv). Answers: are the Molecubes companion
files (reconparams.txt, protocol.txt, ...) planned as non-raw for stream P, and is any of them a
reconstruction we would otherwise miss.

Also reports what production's NI acquisitions hold (a sample of the 1,648 acquisition folders: file names
inside <ACQ-ID>.data\\), read-only on J:.

Writes out\\companions_202.csv.
"""
import collections
import csv
import os
import random
import sys

sys.dont_write_bytecode = True
csv.field_size_limit(2 ** 31 - 1)
OUT = r"D:\projects\gjesus3\drive3_streams\petct\out"
A2 = r"D:\projects\gjesus3\drive3_analysis\a2"
NAS = r"J:\gjesus3-data"


def main():
    plan = list(csv.DictReader(open(os.path.join(OUT, "plan_202.csv"), encoding="utf-8")))
    inv = {r["acq_key"]: r for r in csv.DictReader(open(os.path.join(OUT, "acq_inventory.csv"), encoding="utf-8"))}
    dirs = {}
    for p in plan:
        for rp in inv[p["acq_key_a1"]]["all_drive_relpaths"].split(" | "):
            dirs.setdefault(rp.rsplit("\\", 1)[0], set()).add(p["acq_key"])
    files = {}
    with open(os.path.join(A2, "files.csv"), encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            d = r["relpath"].rsplit("\\", 1)[0] if "\\" in r["relpath"] else ""
            if d in dirs:
                files[r["relpath"]] = r
    pl = {}
    with open(os.path.join(A2, "placement", "placement_plan.csv"), encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["relpath"] in files:
                pl[r["relpath"]] = r
    rows = []
    for rp, r in sorted(files.items()):
        name = rp.rsplit("\\", 1)[-1]
        p = pl.get(rp, {})
        rows.append({"relpath": rp, "name": name, "ext": os.path.splitext(name)[1].lower(), "size": r["size"],
                     "owner": r["owner"], "cls": r["cls"], "a2_decision": p.get("dec_rec", "") or p.get("dec_engine", ""),
                     "a2_dest": p.get("dest", ""), "acqs_in_folder": ";".join(sorted(dirs[rp.rsplit("\\", 1)[0]]))})
    with open(os.path.join(OUT, "companions_202.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"folders holding a copy of the 202: {len(dirs)}; files in them: {len(rows)}")
    print("by owner x class:", collections.Counter((r["owner"], r["cls"]) for r in rows).most_common())
    comp = [r for r in rows if r["owner"] != "A1"]
    print(f"\nnon-raw companions (owner A2 / junk): {len(comp)}")
    print("  by extension:", collections.Counter(r["ext"] for r in comp).most_common())
    print("  by name (top):", collections.Counter(r["name"] for r in comp).most_common(12))
    print("  A2 decision:", collections.Counter(r["a2_decision"] or "(not in plan)" for r in comp).most_common())
    raw_other = [r for r in rows if r["owner"] == "A1" and r["ext"] != ".dcm"]
    print(f"\nraw-class files beside them that are not .dcm: {len(raw_other)}")
    for r in raw_other[:10]:
        print("   ", r["relpath"], r["cls"])
    dcm_other = [r for r in rows if r["ext"] == ".dcm" and r["owner"] == "A1"]
    print(f".dcm files in those folders (owner A1): {len(dcm_other)}")

    # production NI acquisitions: what their .data folders hold (sample, read-only)
    reg = list(csv.DictReader(open(sorted(
        os.path.join(OUT, "_inputs", d, "registry_raw.csv") for d in os.listdir(os.path.join(OUT, "_inputs")))[-1],
        encoding="utf-8-sig", newline="")))
    ni = [r for r in reg if r["instrument"] in ("PET", "CT", "SPECT")]
    random.seed(7)
    sample = random.sample(ni, 60)
    ext = collections.Counter()
    top = collections.Counter()
    for r in sample:
        acq = os.path.join(NAS, r["canonical_path"].strip("/").replace("/", os.sep))
        for root, _d, fns in os.walk(acq):
            for fn in fns:
                if os.path.basename(root).endswith(".data"):
                    ext[os.path.splitext(fn)[1].lower()] += 1
                else:
                    top[fn] += 1
    print(f"\nproduction NI sample ({len(sample)} of {len(ni)} acquisitions): files inside <ACQ-ID>.data: {dict(ext)}; "
          f"beside it: {dict(top)}")


if __name__ == "__main__":
    main()
