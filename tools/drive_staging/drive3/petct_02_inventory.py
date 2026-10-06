"""Stream N, step 1: the drive's Molecubes reconstructions at the ACQUISITION level (read-only).

Inputs (all read-only):
  A1's pet_files.csv (one row per drive file, coverage by SHA-256 / name / time)
  the registry snapshot taken by n02 (out\\_inputs\\<stamp>\\registry_raw.csv)
  the S:\\gnuclear snapshot manifest copy (same folder, _manifest.jsonl)
  the production SHA index D:\\projects\\gjesus3\\drive3_analysis\\prod_raw_sha256.csv

Writes out\\acq_inventory.csv (one row per distinct acquisition key = (ts14, MOD, ALGO, recon))
and prints the breakdowns the gate needs:
  - the 290 in production: which researcher folder / config / project they came in under
  - the 100 snapshot-only and the 102 new, per drive folder
"""
import collections
import csv
import glob
import json
import os
import re
import sys

sys.dont_write_bytecode = True
csv.field_size_limit(2 ** 31 - 1)
A1 = r"D:\projects\gjesus3\drive3_analysis\a1"
OUT = r"D:\projects\gjesus3\drive3_streams\petct\out"
INPUTS = sorted(glob.glob(os.path.join(OUT, "_inputs", "2*")))[-1]
PROD_SHA = r"D:\projects\gjesus3\drive3_analysis\prod_raw_sha256.csv"
KEY_RE = re.compile(r"(\d{14})_(PET|CT|SPECT)_([A-Z]+)_(\d+)", re.I)


def main():
    pet = list(csv.DictReader(open(os.path.join(A1, "pet_files.csv"), encoding="utf-8", newline="")))
    rec = [r for r in pet if r["kind"] == "molecubes-recon"]
    reg = list(csv.DictReader(open(os.path.join(INPUTS, "registry_raw.csv"), encoding="utf-8-sig", newline="")))
    by_acq = {r["acq_id"]: r for r in reg}
    ni = [r for r in reg if r["instrument"] in ("PET", "CT", "SPECT", "OI")]
    reg_by_name = collections.defaultdict(list)
    reg_by_time = collections.defaultdict(list)
    for r in ni:
        m = KEY_RE.search(r["original_name"])
        if m:
            reg_by_name[f"{m.group(1)}_{m.group(2).upper()}_{m.group(3).upper()}_{int(m.group(4))}"].append(r["acq_id"])
        t = re.sub(r"\D", "", r["acquisition_datetime"])[:14]
        reg_by_time[(t, r["instrument"])].append(r["acq_id"])
    prod_sha = {}
    with open(PROD_SHA, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            prod_sha[r["sha256"]] = r["acq_id"]
    snap = [json.loads(l) for l in open(os.path.join(INPUTS, "_manifest.jsonl"), encoding="utf-8")]
    snap_by_sha = collections.defaultdict(list)
    snap_by_key = collections.defaultdict(list)
    for j in snap:
        snap_by_sha[j["sha256"]].append(j)
        snap_by_key[j["acq_key"].upper()].append(j)

    groups = collections.defaultdict(list)
    for r in rec:
        groups[r["ni_key"]].append(r)
    out = []
    for key, fs in sorted(groups.items()):
        shas = sorted({f["sha256"] for f in fs})
        assert len(shas) == 1, key
        sha = shas[0]
        cov = fs[0]["coverage"]
        assert all(f["coverage"] == cov for f in fs), key
        first = [f for f in fs if f["first_copy"] == "Y"]
        canon = sorted(fs, key=lambda f: ({"PET": 0, "Pili y Mili": 1, "biomaGUNE MJ": 2}.get(f["top"], 3),
                                           f["relpath"].count("\\"), f["relpath"]))[0]
        p_acq = prod_sha.get(sha, "")
        p_row = by_acq.get(p_acq, {})
        sn = snap_by_sha.get(sha, [])
        # name/time match in production, for any coverage (a cross-check of A1)
        nm = reg_by_name.get(key, []) if "(renamed)" not in key else []
        tm = reg_by_time.get((fs[0]["ts"], fs[0]["modality_name"]), [])
        out.append({
            "acq_key": key, "ts": fs[0]["ts"], "modality": fs[0]["modality_name"], "coverage": cov,
            "sha256": sha, "size": fs[0]["size"], "n_drive_copies": len(fs),
            "canonical_drive_relpath": canon["relpath"],
            "all_drive_relpaths": " | ".join(sorted(f["relpath"] for f in fs)),
            "prod_acq_id_by_sha": p_acq, "prod_researcher": p_row.get("researcher", ""),
            "prod_project": p_row.get("project_id", ""), "prod_config": p_row.get("ingest_config", ""),
            "prod_original_name": p_row.get("original_name", ""),
            "prod_by_name": ";".join(nm), "prod_by_time": ";".join(tm),
            "snapshot_rels": " | ".join(j["rel"] for j in sn),
            "snapshot_key_rels": " | ".join(j["rel"] for j in snap_by_key.get(key.upper(), [])),
            "hdr_modality": fs[0]["hdr_modality"], "hdr_model": fs[0]["hdr_model"],
            "hdr_series": fs[0]["hdr_series"], "hdr_study_date": fs[0]["hdr_study_date"],
        })
    fields = list(out[0].keys())
    p = os.path.join(OUT, "acq_inventory.csv")
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(out)
    print(f"inputs: {INPUTS}")
    print(f"acquisition keys on the drive: {len(out)}")
    print(collections.Counter(r["coverage"] for r in out))
    inprod = [r for r in out if r["coverage"].startswith("in production")]
    print("\nin production: by researcher x config x project")
    for k, v in collections.Counter((r["prod_researcher"], r["prod_config"], r["prod_project"]) for r in inprod).most_common():
        print(f"  {v:4d}  {k}")
    print("  name-match cross-check:", collections.Counter(bool(r["prod_by_name"]) for r in inprod),
          " time-match:", collections.Counter(bool(r["prod_by_time"]) for r in inprod))
    print("  production original_name == drive key:", collections.Counter(
        r["prod_original_name"].upper() == r["acq_key"].upper() for r in inprod))
    lacking = [r for r in out if not r["coverage"].startswith("in production")]
    print("\nlacking: any production name/time match? ",
          collections.Counter((bool(r["prod_by_name"]), bool(r["prod_by_time"])) for r in lacking))
    snaponly = [r for r in out if r["coverage"].startswith("only in the S")]
    print("snapshot-only: distinct snapshot copies per key:",
          collections.Counter(len(r["snapshot_rels"].split(" | ")) for r in snaponly))
    print("snapshot-only: snapshot researcher folder:", collections.Counter(
        "/".join(x.split("/")[:4]) for r in snaponly for x in r["snapshot_rels"].split(" | ")[:1]))
    new = [r for r in out if r["coverage"].startswith("NEW")]
    print("new: in the snapshot by key (bytes differ)?", collections.Counter(bool(r["snapshot_key_rels"]) for r in new))

    def folder(rp):
        parts = rp.split("\\")
        return "\\".join(parts[:3]) if parts[0] == "PET" else "\\".join(parts[:2])
    print("\nnew (102) by canonical drive folder:")
    for k, v in sorted(collections.Counter(folder(r["canonical_drive_relpath"]) for r in new).items()):
        print(f"  {v:4d}  {k}")
    print("snapshot-only (100) by canonical drive folder:")
    for k, v in sorted(collections.Counter(folder(r["canonical_drive_relpath"]) for r in snaponly).items()):
        print(f"  {v:4d}  {k}")
    print("in production (290) by canonical drive folder:")
    for k, v in sorted(collections.Counter(folder(r["canonical_drive_relpath"]) for r in inprod).items()):
        print(f"  {v:4d}  {k}")
    print(f"\nwrote {p}")


if __name__ == "__main__":
    main()
