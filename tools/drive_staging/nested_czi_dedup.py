"""Dedup the czi-raw found inside nested archives: by SHA-256 against production and the drives,
and by (instrument, acquisition timestamp to the second, lower-cased file name)."""
import csv, io, os, collections
A = r"D:\projects\gjesus3\staging\_analysis"
OUT = A + r"\drives-nonraw-placement\nested_czi_dedup.csv"
rd = lambda p: csv.DictReader(io.open(p, encoding="utf-8-sig", newline=""))
nested = [r for r in rd(A + r"\drives-nonraw-placement\nested_members.csv") if r["class"] == "czi-raw"]
prod_sha = {}
for r in rd(A + r"\catalog\production_hashes.csv"):
    prod_sha.setdefault(r["sha256"], r["acq_id"])
def ts(x):
    return (x or "")[:19].replace(" ", "T")
reg = collections.defaultdict(list)
for r in rd(r"J:\gjesus3-data\registries\registry_raw.csv"):
    name = os.path.basename((r.get("original_name") or "").replace("\\", "/")).lower()
    reg[(r["instrument"], ts(r["acquisition_datetime"]), name)].append(r["acq_id"])
reg_ts = collections.defaultdict(list)  # (instrument, ts) only, for a looser hint
for (i, t, n), ids in reg.items():
    reg_ts[(i, t)] += ids
drive_sha = collections.defaultdict(list)
drive_key = collections.defaultdict(list)
for f in rd(A + r"\catalog\files.csv"):
    if f["ext"] == ".czi":
        drive_sha[f["sha256"]].append(f"{f['drive']}:{f['relpath']}")
        drive_key[(f["instrument"], ts(f["czi_acq_datetime"]), os.path.basename(f["relpath"]).lower())].append(f["relpath"])
for m in rd(A + r"\catalog\archive_members.csv"):
    if m["ext"] == ".czi":
        drive_sha[m["sha256"]].append(f"{m['drive']}:{m['archive_relpath']}!{m['member']}")
out, tally = [], collections.Counter()
for n in nested:
    name = os.path.basename(n["inner"]).lower()
    k = (n["czi_instrument"], ts(n["czi_acq_datetime"]), name)
    if n["sha256"] in prod_sha:
        v, d = "in-production-sha", prod_sha[n["sha256"]]
    elif reg.get(k):
        v, d = "in-production-same-acq", ";".join(reg[k])
    elif drive_sha.get(n["sha256"]):
        v, d = "copy-on-drive-sha", ";".join(drive_sha[n["sha256"]][:3])
    elif drive_key.get(k):
        v, d = "same-acq-on-drive", ";".join(drive_key[k][:3])
    elif reg_ts.get(k[:2]):
        v, d = "NEW (same instrument+second in production, other name)", ";".join(reg_ts[k[:2]][:3])
    else:
        v, d = "NEW", ""
    tally[v] += 1
    out.append(dict(n, dedup=v, detail=d))
with io.open(OUT, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
    w.writeheader()
    w.writerows(out)
print(dict(tally))
by = collections.Counter((os.path.basename(r["nested"]), r["dedup"]) for r in out)
for k, c in sorted(by.items()):
    print(" ", k, c)
for r in out:
    if r["dedup"].startswith("NEW"):
        print("  NEW:", os.path.basename(r["nested"]), r["inner"], r["czi_instrument"], r["czi_acq_datetime"], r["detail"][:80])
