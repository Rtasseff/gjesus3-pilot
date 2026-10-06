"""Before/after snapshot for the LEONE copy: SHA-256 of every registry CSV, and a listing
(name, size, mtime) of every DTS24 acquisition folder in /raw/. Read-only.

  python s14_snapshot.py <out.json>
"""
import csv, hashlib, io, json, os, sys

NAS = r"J:\gjesus3-data"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(8 << 20), b""):
            h.update(b)
    return h.hexdigest()


snap = {"registries": {}, "dts24_raw": {}}
reg = os.path.join(NAS, "registries")
for n in sorted(os.listdir(reg)):
    p = os.path.join(reg, n)
    if os.path.isfile(p) and n.lower().endswith(".csv"):
        snap["registries"][n] = [os.path.getsize(p), sha(p)]
with io.open(os.path.join(reg, "registry_raw.csv"), encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))
snap["registry_raw_rows"] = len(rows)
for r in rows:
    if r["project_id"] == "PROJ-0054":
        d = os.path.join(NAS, r["canonical_path"].strip("/").replace("/", "\\"))
        snap["dts24_raw"][r["acq_id"]] = sorted(
            [e.name, e.stat().st_size, int(e.stat().st_mtime)] for e in os.scandir(d))
json.dump(snap, open(sys.argv[1], "w"), indent=1, sort_keys=True)
print("registries", len(snap["registries"]), "| registry_raw rows", snap["registry_raw_rows"],
      "| DTS24 raw folders", len(snap["dts24_raw"]))
