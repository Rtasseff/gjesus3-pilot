"""Post-copy verification for LEONE -> DTS24 (read-only on J:).

1. Walk the published tree: every manifest file present with the right size, no extra files
   (other than the publishing files); counts + bytes per category vs the manifest.
2. Fresh SHA-256 re-hash from the NAS: all 72 derived + a seeded random 300 of the rest.
3. _INDEX.csv / _PATHMAP.csv on the NAS: our rows are all present and match.
4. Registries + DTS24 /raw/ unchanged: compare a fresh snapshot with snapshot_before.json.
(The DOB grep on the published text files is run separately with s13_privacy_grep.py.)
"""
import csv, hashlib, io, json, os, random, subprocess, sys

NAS = r"J:\gjesus3-data"
EVID = r"D:\projects\gjesus3\staging\_analysis\leone-ingest"
BASE = os.path.join(NAS, r"projects\DTS24\working\historical_drives")
ROOT = os.path.join(BASE, r"FRIO-X6\LEONE")
PUBLISHING = {"readme.txt", "_origin.txt", "_index.csv", "_pathmap.csv"}
HERE = os.path.dirname(os.path.abspath(__file__))


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(8 << 20), b""):
            h.update(b)
    return h.hexdigest()


man = list(csv.DictReader(io.open(EVID + r"\placement_manifest.csv", encoding="utf-8", newline="")))
want = {os.path.join(ROOT, r["dest_rel"]).lower(): r for r in man}
fail = 0

# 1. tree walk
found, extra = {}, []
for dp, dn, fn in os.walk(ROOT):
    for f in fn:
        p = os.path.join(dp, f)
        if p.lower() in want:
            found[p.lower()] = os.path.getsize(p)
        elif f.lower() not in PUBLISHING:
            extra.append(p)
missing = [k for k in want if k not in found]
badsize = [k for k in found if found[k] != int(want[k]["size"])]
cat = {}
for k, r in want.items():
    c = cat.setdefault(r["category"], [0, 0, 0, 0])
    c[0] += 1; c[1] += int(r["size"])
    if k in found:
        c[2] += 1; c[3] += found[k]
print("1. tree:")
for k, (n, b, fn_, fb) in sorted(cat.items()):
    ok = n == fn_ and b == fb
    fail += not ok
    print(f"   {k:15} manifest {n:5d} files {b:>12d} B | NAS {fn_:5d} files {fb:>12d} B  {'OK' if ok else 'MISMATCH'}")
print(f"   missing {len(missing)}, wrong size {len(badsize)}, unexpected files {len(extra)}")
fail += bool(missing or badsize or extra)

# 2. re-hash sample
random.seed(20261004)
der = [k for k, r in want.items() if r["category"] == "derived"]
rest = [k for k, r in want.items() if r["category"] != "derived"]
sample = der + random.sample(rest, 300)
bad = [k for k in sample if k in found and sha(k) != want[k]["sha256"]]
print(f"2. fresh re-hash from NAS: {len(sample)} files ({len(der)} derived + 300 random), mismatches {len(bad)}")
fail += bool(bad)

# 3. published index / pathmap
idx = list(csv.DictReader(io.open(os.path.join(BASE, "_INDEX.csv"), encoding="utf-8-sig", newline="")))
mine = [r for r in idx if r["new_path"].lower().startswith("frio-x6\\leone\\")]
by_np = {r["new_path"].lower(): r for r in mine}
idx_ok = sum(1 for k, r in want.items()
             if (by_np.get(k[len(BASE) + 1:]) or {}).get("sha256") == r["sha256"])
pm = list(csv.DictReader(io.open(os.path.join(BASE, "_PATHMAP.csv"), encoding="utf-8-sig", newline="")))
print(f"3. _INDEX.csv rows total {len(idx)}, LEONE rows {len(mine)}, matching manifest {idx_ok}/{len(want)}; "
      f"_PATHMAP rows {len(pm)} (LEONE {sum(r['node_key'].startswith('D1:LEONE.zip|layout:') for r in pm)})")
print(f"   README.txt at base: {os.path.exists(os.path.join(BASE, 'README.txt'))}; LEONE README.txt: "
      f"{os.path.exists(os.path.join(ROOT, 'README.txt'))}; _ORIGIN.txt: {os.path.exists(os.path.join(ROOT, '_ORIGIN.txt'))}")
fail += idx_ok != len(want)

# 4. unchanged registries + DTS24 raw
after = EVID + r"\snapshot_after.json"
subprocess.run([sys.executable, os.path.join(HERE, "s14_snapshot.py"), after], check=True)
b, a = json.load(open(EVID + r"\snapshot_before.json")), json.load(open(after))
same_raw = b["dts24_raw"] == a["dts24_raw"]
diff_reg = [n for n in set(b["registries"]) | set(a["registries"]) if b["registries"].get(n) != a["registries"].get(n)]
print(f"4. registry_raw rows {b['registry_raw_rows']} -> {a['registry_raw_rows']}; registry files changed: "
      f"{diff_reg or 'none'}; DTS24 /raw/ folders unchanged: {same_raw}")
fail += bool(diff_reg) or not same_raw or b["registry_raw_rows"] != a["registry_raw_rows"]
print("VERIFY", "PASS" if fail == 0 else f"FAIL ({fail})")
sys.exit(1 if fail else 0)
