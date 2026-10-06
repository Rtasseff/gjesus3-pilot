"""A3 step 11 -- inventory roll-up for the report (read-only, local CSVs only).

* every segmentation-relevant file by top-level folder x final class (label / image / split volume / other),
  files and bytes, so the hub's extension-only 'segmentation' byte counts can be corrected;
* the Otros\\Segmentaciones ITK SNAP folder in full (all 41,728 files);
* flow ROIs by structure (pulmonary artery vs aorta, from the file name);
* label modification dates: how many distinct labels carry a plausible authoring time versus a bulk-copy
  stamp (the top mtime days, and how many labels share them).
Outputs: a3_inventory_summary.csv, a3_itksnap_folder.csv, a3_label_dates.csv
"""
import os
import re
import sys
from collections import Counter, defaultdict

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a3_common as C  # noqa: E402


def main():
    inv = C.read_csv_dicts(os.path.join(C.OUT_DIR, "a3_inventory.csv"))
    hdr = {r["sha256"]: r for r in C.read_csv_dicts(os.path.join(C.OUT_DIR, "a3_headers.csv"))}
    labels = {r["relpath"]: r for r in C.read_csv_dicts(os.path.join(C.OUT_DIR, "a3_labels_final.csv"))}

    def cls(r):
        if r["relpath"] in labels:
            return "label (" + labels[r["relpath"]]["set_id"] + ")"
        k = hdr.get(r["sha256"], {}).get("kind", "")
        role = r["role_guess"]
        if role == "image_split":
            return "split volume (image)"
        if k == "image":
            return "image volume (NIfTI/MHA/Interfile)"
        if role in ("image_dicom_source", "image_dicom_index", "aux_cache"):
            return "source DICOM beside labels (pig MRI)"
        if role == "junk":
            return "junk (AppleDouble, .DS_Store, Icon, desktop.ini)"
        if role == "model_weights":
            return "model weights (.h5)"
        return "other (" + role + ")"

    agg = defaultdict(lambda: [0, 0])
    itk = defaultdict(lambda: [0, 0])
    for r in inv:
        c = cls(r)
        agg[(r["top"], c)][0] += 1
        agg[(r["top"], c)][1] += int(r["size"])
        if r["in_itk_snap_folder"] == "Y":
            sub = r["relpath"].split("\\")[2] if r["relpath"].count("\\") >= 2 else "(root)"
            itk[(sub, c)][0] += 1
            itk[(sub, c)][1] += int(r["size"])
    C.write_csv(os.path.join(C.OUT_DIR, "a3_inventory_summary.csv"),
                [{"top": k[0], "class": k[1], "files": v[0], "bytes": v[1], "GB": round(v[1] / 1e9, 3)} for k, v in sorted(agg.items())])
    C.write_csv(os.path.join(C.OUT_DIR, "a3_itksnap_folder.csv"),
                [{"subfolder": k[0], "class": k[1], "files": v[0], "bytes": v[1], "GB": round(v[1] / 1e9, 3)} for k, v in sorted(itk.items())])
    # flow structures
    D = C.read_csv_dicts(os.path.join(C.OUT_DIR, "a3_labels_distinct.csv"))
    fl = Counter()
    for d in D:
        if d["set_id"] == "S-FLOW-ROI":
            n = d["example_relpath"].rsplit("\\", 1)[-1].lower()
            fl["aorta" if "aort" in n else ("pulmonary artery (MPA)" if re.search(r"mpa|pa_|flow", n) else "unnamed")] += 1
    print("flow ROI structures (distinct):", dict(fl))
    # label dates
    days = Counter(d["earliest_mtime"][:10] for d in D)
    rows = [{"date": k, "distinct_labels": v} for k, v in days.most_common(25)]
    C.write_csv(os.path.join(C.OUT_DIR, "a3_label_dates.csv"), rows)
    print("top label mtime days:", days.most_common(8))
    print("label mtime years:", sorted(Counter(d["earliest_mtime"][:4] for d in D).items()))
    tot = defaultdict(lambda: [0, 0])
    for (top, c), v in agg.items():
        tot[c][0] += v[0]
        tot[c][1] += v[1]
    for c, v in sorted(tot.items(), key=lambda kv: -kv[1][1]):
        print(f"  {c:55s} {v[0]:7d} files {v[1] / 1e9:8.2f} GB")


if __name__ == "__main__":
    main()
