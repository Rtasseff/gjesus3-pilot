"""Verify one real-run batch in production (read-only).
usage: python verify_batch.py <config relpath as recorded in ingest_config> <expected rows> <rows before>"""
import sys, os, csv, re, subprocess, collections
REPO = r"C:\Users\rtasseff\OneDrive - CIC biomaGUNE\projects\DataInfra\gjesus3-archive\gjesus3-dev\drives-dicom"
sys.path.insert(0, os.path.join(REPO, "tools"))
import verify_checksums as vc
NAS = "J:/gjesus3-data"
cfg, expected, before = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
with open(os.path.join(NAS, "registries", "registry_raw.csv"), newline="", encoding="utf-8-sig") as fh:
    rows = list(csv.DictReader(fh))
mine = [r for r in rows if r["ingest_config"].replace("\\", "/") == cfg]
fails = []
print(f"registry rows {len(rows)} (before {before}, +{len(rows) - before}); rows from this config {len(mine)}; expected {expected}")
if len(mine) != expected: fails.append("row count")
if len(rows) - before != expected: fails.append("registry delta")
ids = [r["acq_id"] for r in mine]
if len(set(ids)) != len(ids): fails.append("duplicate ACQ-IDs")
today = [r["acq_id"] for r in mine if r["acq_id"][4:8] == "2026" or r["acquisition_datetime"].startswith("2026")]
if today: fails.append(f"dated 2026: {today[:3]}")
dup_on = collections.Counter((r["acquisition_datetime"][:10], r["original_name"]) for r in rows)
d2 = [k for k, n in dup_on.items() if n > 1 and any(k == (r["acquisition_datetime"][:10], r["original_name"]) for r in mine)]
if d2: fails.append(f"dedup-key duplicates {d2[:3]}")
st = collections.Counter(); nodcm = 0; linkok = linkbad = linkmissing = 0
projects = {}
with open(os.path.join(NAS, "registries", "registry_projects.csv"), newline="", encoding="utf-8-sig") as fh:
    for p in csv.DictReader(fh):
        projects[p["project_id"]] = p["name"]
for r in mine:
    folder = os.path.join(NAS, r["canonical_path"].strip("/"))
    res = vc.verify_acquisition(folder)
    st[res["status"]] += 1
    if res["status"] != "PASS": fails.append(f"checksum {r['acq_id']} {res['status']}")
    data = os.path.join(folder, r["primary_file_name"])
    files = [os.path.join(data, f) for f in os.listdir(data)] if os.path.isdir(data) else ([data] if os.path.isfile(data) else [])
    dcms = [f for f in files if f.lower().endswith(".dcm")]
    if not dcms:
        nodcm += 1; continue
    if not r["project_id"]:
        continue
    pdir = os.path.join(NAS, "projects", projects[r["project_id"]], "raw_linked")
    target = dcms[0]
    found = False
    for name in os.listdir(pdir):
        p = os.path.join(pdir, name)
        cand = os.path.join(p, os.path.basename(target)) if os.path.isdir(p) else p
        if os.path.exists(cand) and os.path.samefile(cand, target):
            found = True; break
    if found: linkok += 1
    else: linkmissing += 1; fails.append(f"link missing {r['acq_id']}")
print(f"checksums {dict(st)}; acqs with no DICOM (regen worklist) {nodcm}; project links samefile OK {linkok}, missing {linkmissing}")
v = subprocess.run([sys.executable, os.path.join(REPO, "tools", "validate_registries.py"), "--nas-root", NAS], capture_output=True, text=True, encoding="utf-8", errors="replace")
errs = [l for l in v.stdout.splitlines() if l.strip().startswith("ERROR:")]
classes = collections.Counter(re.sub(r"\[ACQ-[^]]*\]|\d+", "N", l).strip() for l in errs)
print(f"validator errors {len(errs)}; classes {len(classes)}")
if len(errs) != 10314 or len(classes) != 1: fails.append(f"validator {len(errs)} errors / {len(classes)} classes")
print("RESULT:", "PASS" if not fails else "FAIL " + "; ".join(fails[:10]))
