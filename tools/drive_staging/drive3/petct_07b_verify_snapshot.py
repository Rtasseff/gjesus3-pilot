"""Stream N, step 6b: re-hash the 100 snapshot files (read-only) and compare them with the drive manifest.

The 100 are ingested from J:\\gjesus3-data\\staging\\ni_gnuclear_20260812\\ (pulled 2026-08-12,
verified 2,485 ok then). This proves, today, that each snapshot file is byte-identical to the drive's
copy (drive manifest SHA-256) and to the snapshot's own manifest.
"""
import csv
import hashlib
import json
import os
import sys

sys.dont_write_bytecode = True
OUT = r"D:\projects\gjesus3\drive3_streams\petct\out"
SNAP = r"J:\gjesus3-data\staging\ni_gnuclear_20260812"


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(8 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    plan = [r for r in csv.DictReader(open(os.path.join(OUT, "plan_202.csv"), encoding="utf-8"))
            if r["source"] == "snapshot"]
    man = {}
    for line in open(os.path.join(SNAP, "_manifest.jsonl"), encoding="utf-8"):
        j = json.loads(line)
        man[j["rel"]] = j
    ok = bad = 0
    rows = []
    for r in plan:
        p = os.path.join(SNAP, r["source_rel"].replace("/", os.sep))
        h = sha256(p)
        m = man[r["source_rel"]]
        good = (h == r["sha256"] == m["sha256"]) and os.path.getsize(p) == int(r["size"]) == m["size"]
        ok += good
        bad += not good
        rows.append({"acq_key": r["acq_key"], "snapshot_rel": r["source_rel"], "sha256_now": h,
                     "sha256_drive_manifest": r["sha256"], "sha256_snapshot_manifest": m["sha256"],
                     "identical": "Y" if good else "N"})
    with open(os.path.join(OUT, "snapshot_100_rehash.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"snapshot files re-hashed: {len(rows)}; identical to the drive manifest and the snapshot manifest: "
          f"{ok}; different: {bad}")


if __name__ == "__main__":
    main()
