"""A1 step 2a: every ParaVision exam folder on the drive, every copy of it, and a canonical copy.

From the manifest only (no file is opened). Units, as in tasks/mri_unparsed_rescan_review.md:
  exam folder   a folder holding `acqp` or `method` (here every one holds both)
  study folder  the parent of an exam folder
  exam key      "<study folder name>/<exam folder name>", the production original_name shape
A study can sit in several places on the drive (MRI\\, Pili y Mili\\, biomaGUNE MJ\\ ...). Each place
is a COPY. Copies are compared file by file by SHA-256 (inner path -> SHA-256).

Canonical copy of an exam key: the copy with the most distinct SHA-256 values, then the most
bytes, then the preferred top folder (MRI, Otros, Pili y Mili, biomaGUNE MJ), then the shortest
path. Every other copy is classed against it: identical (same inner path -> SHA-256 map),
subset (every file of the copy is in the canonical, byte-identical), or divergent (a shared inner
path with different bytes, or files the canonical lacks).

Writes (a1\\): mri_exam_copies.csv (one row per exam folder), and caches the structures.

    python a1_20_mri_inventory.py
"""
import collections
import re

from a1_common import MRIM, TOP_ORDER, cache_load, cache_save, write_csv

PREF = {t: i for i, t in enumerate(TOP_ORDER)}


def main():
    df = cache_load("files")
    if df is None:
        raise SystemExit("run a1_10_files.py first")
    ex = df[df["exam_dir"] != ""]
    copies = {}
    for rp, ed, sd, top, size, sha, cls in zip(ex["relpath"], ex["exam_dir"], ex["study_dir"], ex["top"],
                                                ex["size"], ex["sha256"], ex["a1class"]):
        c = copies.get(ed)
        if c is None:
            study = sd.rsplit("\\", 1)[-1]
            exam = ed.rsplit("\\", 1)[-1]
            c = copies[ed] = {"exam_dir": ed, "study_dir": sd, "study": study, "exam": exam,
                              "key": f"{study}/{exam}", "top": top, "inner": {}, "bytes": 0,
                              "dcm": {}, "dcm_bytes": 0, "seq": set(), "kspace": [], "kspace_bytes": 0,
                              "acqp_sha": "", "method_sha": ""}
        inner = rp[len(ed) + 1:]
        c["inner"][inner] = sha
        c["bytes"] += size
        parts = inner.split("\\")
        low = parts[-1].lower()
        if cls == "mri-dicom":
            m = MRIM.match(parts[3])
            n = m.group(1)
            c["dcm"][f"recon{parts[1]}_frame{n.zfill(2) if len(n) < 2 else n}.dcm"] = sha
            c["dcm_bytes"] += size
        elif cls == "mri-2dseq" and len(parts) == 3 and parts[0].lower() == "pdata":
            c["seq"].add(parts[1])
        elif cls == "mri-kspace":
            c["kspace"].append(inner)
            c["kspace_bytes"] += size
        if len(parts) == 1 and low == "acqp":
            c["acqp_sha"] = sha
        if len(parts) == 1 and low == "method":
            c["method_sha"] = sha
    # the study-level subject file of each study copy
    subj = df[(df["name"].str.lower() == "subject")]
    subj_sha = dict(zip(subj["dir"], subj["sha256"]))
    for c in copies.values():
        c["subject_sha"] = subj_sha.get(c["study_dir"], "")
        c["n_files"] = len(c["inner"])
        c["n_distinct"] = len(set(c["inner"].values()))
    # group by exam key, pick canonical
    keys = collections.defaultdict(list)
    for c in copies.values():
        keys[c["key"]].append(c)
    for k, cs in keys.items():
        cs.sort(key=lambda c: (-c["n_distinct"], -c["bytes"], PREF.get(c["top"], 99), len(c["exam_dir"]),
                               c["exam_dir"]))
        can = cs[0]
        for i, c in enumerate(cs):
            c["canonical"] = i == 0
            c["n_copies"] = len(cs)
            if i == 0:
                c["vs_canonical"] = "canonical"
                continue
            same = all(can["inner"].get(p) == s for p, s in c["inner"].items())
            if same and len(c["inner"]) == len(can["inner"]):
                c["vs_canonical"] = "identical"
            elif same:
                c["vs_canonical"] = "subset"
            else:
                diff = sum(1 for p, s in c["inner"].items() if p in can["inner"] and can["inner"][p] != s)
                extra = sum(1 for p in c["inner"] if p not in can["inner"])
                c["vs_canonical"] = f"divergent ({diff} differ, {extra} extra)"
    # same acquisition under different exam keys (a renamed study folder): identical acqp bytes
    by_acqp = collections.defaultdict(set)
    for c in copies.values():
        if c["acqp_sha"]:
            by_acqp[c["acqp_sha"]].add(c["key"])
    for c in copies.values():
        others = sorted(by_acqp.get(c["acqp_sha"], set()) - {c["key"]})
        c["same_acqp_other_keys"] = ";".join(others)
    cache_save("mri_copies", copies)
    cache_save("mri_keys", {k: [c["exam_dir"] for c in cs] for k, cs in keys.items()})
    rows = []
    for c in sorted(copies.values(), key=lambda c: (c["key"], not c["canonical"], c["exam_dir"])):
        rows.append({"exam_key": c["key"], "study": c["study"], "exam": c["exam"], "top": c["top"],
                     "exam_dir": c["exam_dir"], "canonical": "Y" if c["canonical"] else "N",
                     "vs_canonical": c["vs_canonical"], "n_copies": c["n_copies"], "n_files": c["n_files"],
                     "bytes": c["bytes"], "n_dcm": len(c["dcm"]), "dcm_bytes": c["dcm_bytes"],
                     "dcm_recons": ";".join(sorted({n.split("_")[0][5:] for n in c["dcm"]}, key=lambda x: int(x) if x.isdigit() else 0)),
                     "seq_recons": ";".join(sorted(c["seq"], key=lambda x: int(x) if x.isdigit() else 0)),
                     "kspace": ";".join(sorted(c["kspace"])), "kspace_bytes": c["kspace_bytes"],
                     "acqp_sha": c["acqp_sha"], "same_acqp_other_keys": c["same_acqp_other_keys"]})
    write_csv("mri_exam_copies.csv", rows, list(rows[0].keys()))
    n_st = len({c["study"] for c in copies.values()})
    n_st_copies = len({c["study_dir"] for c in copies.values()})
    print(f"exam folders (copies): {len(copies):,}   exam keys: {len(keys):,}   study names: {n_st}   "
          f"study folders (copies): {n_st_copies}")
    print("copies per exam key:", collections.Counter(len(v) for v in keys.values()))
    print("vs canonical:", collections.Counter(c["vs_canonical"].split(" (")[0] for c in copies.values()))
    ren = {c["key"] for c in copies.values() if c["same_acqp_other_keys"]}
    print(f"exam keys whose acqp bytes also occur under another key: {len(ren)}")


if __name__ == "__main__":
    main()
