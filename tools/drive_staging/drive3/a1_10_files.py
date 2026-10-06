"""A1 step 1: every file on the drive, classified, and matched by SHA-256 against production.

"Already in production" is reported in its three senses (HANDOFF section 1):
  in_prod_raw   the file's SHA-256 is in a production /raw/ checksums.json (prod_raw_sha256.csv)
  in_d12_placed the SHA-256 is in a drives-1+2 placement _INDEX.csv (non-raw placed in a project)
  in_d12_hold   the SHA-256 is in the drives-1+2 holding folder manifest
and, for context, on_d12 = byte-identical to some file of drives 1/2 (the hub's
drive3_duplicates_of_12.csv), whatever happened to it.

Writes (a1\\):
  a1_files.csv.gz                 one row per drive file (621,969)
  coverage_by_top_class.csv       per top-level folder x A1 class
  coverage_by_class.csv           per A1 class, whole drive
  hub_class_crosswalk.csv         the hub's content_classes.py class vs the A1 class (files, bytes)

    python a1_10_files.py
"""
import collections
import csv
import gzip
import os
import re

from a1_common import (CLASS_ORDER, D12_RECORDS, RAW_CLASSES, TOP_ORDER, cache_load, cache_save,
                       classify, gb, load_manifest, load_prod_index, lp, out_path, snapshot)

# --- the hub's classifier, verbatim from records\content_classes.py (for the crosswalk only) ---
H_RAW = {".czi", ".lif", ".lifext", ".nd2"}
H_BRUKER = {".job0", ".job1", ".par", ".scanprogram", ".raw", ".spr", ".visu_pars", ".acqp", ".method",
            ".jcamp", ".info", ".mhd"}
H_BRUKER_NAMES = {"2dseq", "fid", "acqp", "method", "visu_pars", "reco", "id", "methreco", "procs",
                  "configscan", "specpar", "pulseprogram", "adjstateperscan", "adjstateperstudy",
                  "subject", "resultstate", "traj", "b0", "spnam0", "spnam5", "gradcalib",
                  "adjrefgprofiles.dat", "result.jcamp", "uxnmr.info", "acqus", "proc", "reco_info"}
H_JUNK = {"desktop.ini", "thumbs.db", ".ds_store"}
H_DICOM = {".dcm", ".ima"}
H_DERIVED = {".nii", ".gz", ".voi", ".hdr", ".img", ".mha", ".nrrd", ".seg"}
H_DOCS = {".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".pdf", ".txt", ".rtf", ".csv"}
H_ANALYSIS = {".mat", ".m", ".py", ".r", ".ipynb", ".pzfx", ".prism", ".adicht", ".sav", ".spv"}
H_IMAGES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".svg", ".eps"}
H_ARCHIVE = {".zip", ".rar", ".7z", ".tar"}


def hub_cls(p):
    e = os.path.splitext(p)[1].lower()
    n = os.path.basename(p.replace("\\", "/")).lower()
    if n in H_JUNK:
        return "junk"
    if e in H_RAW:
        return "raw-microscopy"
    if e in H_BRUKER or n in H_BRUKER_NAMES or n.startswith("spnam") or n.startswith("adjstate"):
        return "raw-bruker"
    if e in H_DICOM:
        return "raw-dicom"
    if e in H_DERIVED:
        return "derived/segmentation"
    if e in H_DOCS:
        return "documents"
    if e in H_ANALYSIS:
        return "analysis"
    if e in H_IMAGES:
        return "images/figures"
    if e in H_ARCHIVE:
        return "archives"
    return "other"


def load_d12():
    """sha256 -> project folder of a drives-1+2 placement; set of holding-folder sha256."""
    placed = collections.defaultdict(set)
    d12 = os.path.dirname(snapshot(os.path.join("d12", "holding_manifest.csv")))
    for fn in os.listdir(d12):
        if fn.endswith("__INDEX.csv"):
            proj = fn[:-len("__INDEX.csv")]
            with open(os.path.join(d12, fn), encoding="utf-8-sig", newline="") as f:
                for r in csv.DictReader(f):
                    if r.get("sha256"):
                        placed[r["sha256"]].add(proj)
    hold = set()
    with open(os.path.join(d12, "holding_manifest.csv"), encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("sha256"):
                hold.add(r["sha256"])
    # every SHA-256 known on drives 1/2: both loose-file manifests AND every archive member the
    # drives-1+2 catalog hashed (the hub's drive3_duplicates_of_12.csv saw loose files only)
    on12 = cache_load("d12_all_sha")
    if on12 is None:
        on12 = set()
        for p in (os.path.join(D12_RECORDS, "drive1_FRIO-X6_2322E4A111E7", "manifest.csv"),
                  os.path.join(D12_RECORDS, "drive2_MFB-Disco-2_2322E4A112BD", "manifest.csv"),
                  os.path.join(D12_RECORDS, "_analysis", "catalog", "archive_members.csv")):
            with open(lp(p), encoding="utf-8-sig", newline="") as f:
                for r in csv.DictReader(f):
                    if r.get("sha256"):
                        on12.add(r["sha256"])
        cache_save("d12_all_sha", on12)
    hub12 = set()
    with open(snapshot("hub_drive3_duplicates_of_12.csv"), encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            hub12.add(r["drive3_relpath"])
    return placed, hold, on12, hub12


def main():
    df = load_manifest()
    dicm = cache_load("dicm_noext") or frozenset()
    df = classify(df, dicm)
    prod = load_prod_index()
    placed, hold, on12, hub12 = load_d12()
    sha = df["sha256"]
    df["hub_on_d12"] = df["relpath"].isin(hub12)
    print(f"hub's drive3_duplicates_of_12.csv: {int(df['hub_on_d12'].sum()):,} files; "
          f"A1 (loose files + archive members of drives 1/2): {int(sha.isin(on12).sum()):,} files")
    df["in_prod_raw"] = sha.map(lambda s: s in prod)
    df["prod_acq_id"] = sha.map(lambda s: prod[s][0] if s in prod else "")
    df["prod_instrument"] = sha.map(lambda s: prod[s][1] if s in prod else "")
    df["prod_project"] = sha.map(lambda s: prod[s][2] if s in prod else "")
    df["in_d12_placed"] = sha.map(lambda s: ";".join(sorted(placed[s])) if s in placed else "")
    df["in_d12_hold"] = sha.isin(hold)
    df["on_d12"] = sha.isin(on12)
    df["n_copies"] = df.groupby("sha256")["sha256"].transform("size")
    # one canonical row per SHA-256 inside the drive: preferred top folder, then shortest path
    pref = {t: i for i, t in enumerate(TOP_ORDER)}
    df["_k1"] = df["top"].map(lambda t: pref.get(t, 99))
    df["_k2"] = df["relpath"].str.len()
    order = df.sort_values(["sha256", "_k1", "_k2", "relpath"]).index
    first = df.loc[order].drop_duplicates("sha256").index
    df["first_copy"] = False
    df.loc[first, "first_copy"] = True
    df["hub_class"] = df["relpath"].map(hub_cls)
    df.drop(columns=["_k1", "_k2"], inplace=True)
    cache_save("files", df)

    cols = ["relpath", "top", "size", "sha256", "ext", "a1class", "hub_class", "exam_dir", "study_dir",
            "in_prod_raw", "prod_acq_id", "prod_instrument", "prod_project", "in_d12_placed",
            "in_d12_hold", "on_d12", "n_copies", "first_copy", "mtime"]
    p = out_path("a1_files.csv.gz")
    with gzip.open(p, "wt", encoding="utf-8", newline="") as f:
        df[cols].to_csv(f, index=False)
    print(f"wrote {p}")

    def agg(g):
        anyprod = g["in_prod_raw"] | (g["in_d12_placed"] != "") | g["in_d12_hold"]
        u = g[g["first_copy"]]
        uany = u["in_prod_raw"] | (u["in_d12_placed"] != "") | u["in_d12_hold"]
        return {
            "files": len(g), "GB": gb(g["size"].sum()),
            "prod_raw_files": int(g["in_prod_raw"].sum()), "prod_raw_GB": gb(g.loc[g["in_prod_raw"], "size"].sum()),
            "d12_placed_files": int((g["in_d12_placed"] != "").sum()),
            "d12_placed_GB": gb(g.loc[g["in_d12_placed"] != "", "size"].sum()),
            "d12_hold_files": int(g["in_d12_hold"].sum()), "d12_hold_GB": gb(g.loc[g["in_d12_hold"], "size"].sum()),
            "any_prod_files": int(anyprod.sum()), "any_prod_GB": gb(g.loc[anyprod, "size"].sum()),
            "on_d12_files": int(g["on_d12"].sum()), "on_d12_GB": gb(g.loc[g["on_d12"], "size"].sum()),
            "distinct_sha": len(u), "distinct_GB": gb(u["size"].sum()),
            "distinct_new_files": int((~uany).sum()), "distinct_new_GB": gb(u.loc[~uany, "size"].sum()),
        }

    fields = ["top", "a1class", "raw_imaging", "files", "GB", "prod_raw_files", "prod_raw_GB",
              "d12_placed_files", "d12_placed_GB", "d12_hold_files", "d12_hold_GB", "any_prod_files",
              "any_prod_GB", "on_d12_files", "on_d12_GB", "distinct_sha", "distinct_GB",
              "distinct_new_files", "distinct_new_GB"]
    rows = []
    for t in TOP_ORDER:
        for c in CLASS_ORDER:
            g = df[(df["top"] == t) & (df["a1class"] == c)]
            if len(g):
                rows.append({"top": t, "a1class": c, "raw_imaging": "Y" if c in RAW_CLASSES else "N", **agg(g)})
        g = df[df["top"] == t]
        rows.append({"top": t, "a1class": "(all)", "raw_imaging": "", **agg(g)})
        g = df[(df["top"] == t) & df["a1class"].isin(RAW_CLASSES)]
        if len(g):
            rows.append({"top": t, "a1class": "(all raw imaging)", "raw_imaging": "Y", **agg(g)})
    # note: distinct_* within a top folder dedups inside that folder only
    from a1_common import write_csv
    write_csv("coverage_by_top_class.csv", rows, fields)
    rows2 = []
    for c in CLASS_ORDER:
        g = df[df["a1class"] == c]
        if len(g):
            rows2.append({"top": "(drive)", "a1class": c, "raw_imaging": "Y" if c in RAW_CLASSES else "N", **agg(g)})
    rows2.append({"top": "(drive)", "a1class": "(all raw imaging)", "raw_imaging": "Y",
                  **agg(df[df["a1class"].isin(RAW_CLASSES)])})
    rows2.append({"top": "(drive)", "a1class": "(all)", "raw_imaging": "", **agg(df)})
    write_csv("coverage_by_class.csv", rows2, fields)
    cw = df.groupby(["hub_class", "a1class"]).agg(files=("size", "size"), bytes=("size", "sum")).reset_index()
    cw["GB"] = cw["bytes"].map(gb)
    cw["GiB"] = (cw["bytes"] / 2 ** 30).round(3)
    write_csv("hub_class_crosswalk.csv", cw.to_dict("records"), ["hub_class", "a1class", "files", "bytes", "GB", "GiB"])
    tot = agg(df)
    print("whole drive:", tot)
    raw = agg(df[df["a1class"].isin(RAW_CLASSES)])
    print("raw imaging:", raw)


if __name__ == "__main__":
    main()
