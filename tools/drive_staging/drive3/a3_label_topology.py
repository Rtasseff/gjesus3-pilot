"""A3 step 6 -- what do the label values mean? A measured topology test on every cine mask (read-only).

The open question carried by DS-SEG-0001/0003/0004 is whether the 0/1/2 maps are LV/RV, or LV blood pool /
LV myocardium; and the 0-4 maps (Massventricles, Predict_Slicer, the 2020 hand masks) have no recorded
meaning at all. An ITK-SNAP label description found three times on this drive says
1 'LV Endo', 2 'LV Epi', 3 'RV Endo', 4 'RV Epi'. This step tests the geometry, not the names:

  exterior_contact(a) = of label a's boundary pixels (2-D, per slice), the fraction 4-adjacent to
                        background that lies OUTSIDE the filled union of all foreground labels.
  A label enclosed by another (a blood pool inside a myocardial ring) has exterior_contact ~ 0.
  Two side-by-side regions (LV beside RV) both touch the outside along much of their boundary.
  enclosed_by(a, b)   = fraction of label a's voxels lying inside the 2-D filled hull of label b
                        (binary_fill_holes(b)) -- ~1 when b is a closed ring around a.
Computed for every DISTINCT label file of the cine sets (one read per SHA-256).
Output: a3_label_topology.csv (one row per distinct label file x foreground value).
"""
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a3_common as C  # noqa: E402

import numpy as np  # noqa: E402
import nibabel as nib  # noqa: E402
import SimpleITK as sitk  # noqa: E402
from scipy import ndimage as ndi  # noqa: E402

CINE_SETS = {"S-CINE-LVRV", "S-CINE-MASS", "S-CINE-PRED-VICOMTECH", "S-RAT-0118-RESP", "S-RAT-2DG-2019-PRED"}
N4 = ndi.generate_binary_structure(2, 1)


def load(rel):
    p = C.staged_path(rel)
    if rel.lower().endswith((".nii", ".nii.gz")):
        return np.asanyarray(C.load_nifti(p).dataobj)      # long-path / non-ASCII safe
    return C.read_metaimage(p)[1]                          # (x, y, z)


def solidity(mask2d):
    """area / convex-hull area of the largest 2-D component (round LV cavity ~0.9; RV crescent lower)."""
    from skimage.measure import label as cc, regionprops
    lab = cc(mask2d, connectivity=1)
    if lab.max() == 0:
        return None
    rp = max(regionprops(lab), key=lambda r: r.area)
    return float(rp.solidity) if rp.area >= 12 else None


def one(sha, rel, set_id):
    rows = []
    try:
        a = np.asarray(load(rel))
        if a.ndim == 4:
            a = a[..., 0]
        if a.ndim == 2:
            a = a[..., None]
        vals = [int(v) for v in np.unique(a) if v != 0]
        stats = {v: {"vox": 0, "bnd": 0, "ext": 0, "sol": [], "inside": {w: 0 for w in vals if w != v}} for v in vals}
        for z in range(a.shape[2]):
            sl = a[:, :, z]
            if not sl.any():
                continue
            fg = sl != 0
            filled = ndi.binary_fill_holes(fg)
            exterior = ~filled
            ext_adj = ndi.binary_dilation(exterior, structure=N4)
            hulls = {w: ndi.binary_fill_holes(sl == w) for w in vals}
            for v in vals:
                m = sl == v
                if not m.any():
                    continue
                bnd = m & ~ndi.binary_erosion(m, structure=N4, border_value=0)
                stats[v]["vox"] += int(m.sum())
                stats[v]["bnd"] += int(bnd.sum())
                stats[v]["ext"] += int((bnd & ext_adj).sum())
                s_ = solidity(m)
                if s_ is not None:
                    stats[v]["sol"].append(s_)
                for w in vals:
                    if w != v:
                        stats[v]["inside"][w] += int((m & hulls[w] & (sl != w)).sum())
        for v, s in stats.items():
            rows.append({"sha256": sha, "relpath": rel, "set_id": set_id, "value": v, "voxels": s["vox"],
                         "exterior_contact": round(s["ext"] / s["bnd"], 4) if s["bnd"] else "",
                         "solidity_median": round(float(np.median(s["sol"])), 4) if s["sol"] else "",
                         **{f"enclosed_by_{w}": round(n / s["vox"], 4) if s["vox"] else "" for w, n in s["inside"].items()}})
    except Exception as e:  # noqa: BLE001
        rows.append({"sha256": sha, "relpath": rel, "set_id": set_id, "error": f"{type(e).__name__}: {e}"})
    return rows


def main():
    labs = C.read_csv_dicts(os.path.join(C.OUT_DIR, "a3_labels.csv"))
    todo = {}
    for r in labs:
        if r["set_id"] in CINE_SETS and r["kind"] == "label" and r["fmt"] in ("nifti", "metaimage"):
            todo.setdefault(r["sha256"], (r["relpath"], r["set_id"]))
    out = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        for rows in ex.map(lambda kv: one(kv[0], *kv[1]), todo.items()):
            out += rows
    fields = ["sha256", "relpath", "set_id", "value", "voxels", "exterior_contact", "solidity_median"] + \
             [f"enclosed_by_{w}" for w in range(1, 9)] + ["error"]
    C.write_csv(os.path.join(C.OUT_DIR, "a3_label_topology.csv"), out, fields)
    print(f"distinct label files {len(todo)}, rows {len(out)}, errors {sum(1 for o in out if o.get('error'))}")


if __name__ == "__main__":
    main()
