"""A3 step 2 -- header + voxel-value census of every distinct NIfTI / Analyze / MetaImage file (read-only).

One read per distinct SHA-256 (the drive holds the same file up to 7 times). For each:
  * header: dims, voxel size, datatype, NIfTI q/sform codes and affine, or MetaImage DimSize /
    ElementSpacing / ElementType / Offset / TransformMatrix (MetaImage .mhd headers are parsed as text);
  * census: the set of voxel values and their counts. This is what decides LABEL vs IMAGE -- never the
    name. Policy (measured, no extrapolation):
      - integer-typed volumes up to 256 MB uncompressed: full census;
      - float volumes: a strided sample (every 4th voxel per axis) first; if the sample is integer-valued
        with <= 256 distinct values it gets a full census (a float-typed mask), otherwise it is an image;
      - MetaImage split volumes named Time_*_rat_* / *flujo* (per-phase image stacks): header only, plus a
        full census of every 50th distinct one to confirm they are images (recorded as census_mode=sample50);
      - MetaImage files named Pred_ / Postprocessed_ / Modificated_ / other: full census.
    label_like = integer-valued and <= 64 distinct values (0 included); label_empty = all zero.
Resumable: rows already in a3_headers.csv are kept and skipped.

Output: D:\\projects\\gjesus3\\drive3_analysis\\a3\\a3_headers.csv (keyed by sha256)
"""
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a3_common as C  # noqa: E402

import numpy as np  # noqa: E402
import nibabel as nib  # noqa: E402
import SimpleITK as sitk  # noqa: E402

OUT = os.path.join(C.OUT_DIR, "a3_headers.csv")
FMTS = (".nii", ".nii.gz", ".mha", ".mhd", ".hdr", ".nrrd")
MAX_FULL = 256e6


def fmt_vals(u, c, limit=40):
    if len(u) <= limit:
        return ";".join(f"{v:g}" for v in u), ";".join(str(int(x)) for x in c)
    return ";".join(f"{v:g}" for v in u[:10]) + ";...", ""


def census(arr, rec, mode):
    a = np.asarray(arr)
    rec["census_mode"] = mode
    if a.size == 0:
        rec["n_unique"] = 0
        return rec
    if np.issubdtype(a.dtype, np.floating):
        finite = np.isfinite(a)
        intlike = bool(finite.all() and np.all(np.mod(a[finite], 1) == 0))
    else:
        intlike = True
    u, c = np.unique(a, return_counts=True)
    rec["n_unique"] = len(u)
    rec["integer_valued"] = "Y" if intlike else "N"
    rec["vmin"] = f"{float(u[0]):g}"
    rec["vmax"] = f"{float(u[-1]):g}"
    rec["values"], rec["value_counts"] = fmt_vals(u, c)
    nz = int(a.size - (c[u == 0].sum() if (u == 0).any() else 0))
    rec["nonzero_voxels"] = nz
    if a.ndim >= 3 and intlike and len(u) <= 64:
        sl = (a != 0).reshape(a.shape[0], a.shape[1], a.shape[2], -1).any(axis=(0, 1, 3))
        rec["slices_with_label"] = int(sl.sum())
        rec["slices_total"] = int(a.shape[2])
    if intlike and len(u) <= 64:
        rec["kind"] = "label_empty" if nz == 0 else "label"
    else:
        rec["kind"] = "image"
    return rec


SPLIT_NAME = re.compile(r"^(time_\d+_rat_|flujo)", re.I)   # per-phase IMAGE stacks (not Predict_Slicer output)


def do_one(sha, rel, role):
    p = C.staged_path(rel)
    low = rel.lower()
    rec = {"sha256": sha, "rep_relpath": rel, "role_guess": role}
    try:
        if low.endswith(".hdr") and C.read_bytes(p, 13) == b"!INTERFILE :=":
            head = C.read_bytes(p, 3000).decode("latin-1")
            rec["fmt"] = "interfile"
            rec["kind"] = "image"
            rec["census_mode"] = "header-only"
            m = re.search(r"conversion program :=(.*)\r?\n!program version :=(.*)\r?\n", head)
            rec["descrip"] = ("PMOD Interfile export " + (m.group(2).strip() if m else "")).strip()
            return rec
        if low.endswith((".nii", ".nii.gz", ".hdr")):
            im = C.load_nifti(p) if not low.endswith(".hdr") else nib.load(C.lp(p))
            h = im.header
            rec["fmt"] = "nifti" if low.endswith((".nii", ".nii.gz")) else "analyze"
            rec["dims"] = "x".join(str(int(s)) for s in im.shape)
            rec["spacing"] = "x".join(f"{float(z):.6g}" for z in h.get_zooms()[:3])
            rec["dtype"] = str(h.get_data_dtype())
            if rec["fmt"] == "nifti":
                rec["qform_code"] = int(h["qform_code"])
                rec["sform_code"] = int(h["sform_code"])
                rec["descrip"] = h["descrip"].tobytes().rstrip(b"\0").decode("latin-1")[:80]
            aff = im.affine
            rec["affine"] = ";".join(f"{v:.6g}" for v in aff[:3, :].ravel())
            nbytes = int(np.prod(im.shape)) * h.get_data_dtype().itemsize
            isfloat = np.issubdtype(h.get_data_dtype(), np.floating)
            if not isfloat and nbytes <= MAX_FULL:
                census(np.asanyarray(im.dataobj), rec, "full")
            elif isfloat:
                sl = tuple(slice(None, None, 4) for _ in im.shape[:3]) + tuple(slice(None) for _ in im.shape[3:])
                samp = np.asanyarray(im.dataobj[sl]) if len(im.shape) >= 3 else np.asanyarray(im.dataobj)
                census(samp, rec, "sample4")
                if rec.get("integer_valued") == "Y" and int(rec.get("n_unique", 999)) <= 256 and nbytes <= MAX_FULL:
                    census(np.asanyarray(im.dataobj), rec, "full")
            else:
                sl = tuple(slice(None, None, 4) for _ in im.shape[:3])
                census(np.asanyarray(im.dataobj[sl]), rec, "sample4")
        elif low.endswith((".mhd", ".mha")):
            rec["fmt"] = "metaimage"
            h, _ = C.read_metaimage(p, header_only=True)
            rec["dims"] = "x".join(h.get("DimSize", "").split())
            rec["spacing"] = "x".join(f"{float(v):.6g}" for v in h.get("ElementSpacing", h.get("ElementSize", "")).split())
            rec["dtype"] = h.get("ElementType", "")
            rec["affine"] = "offset=" + h.get("Offset", h.get("Position", h.get("Origin", ""))) + "|tm=" + \
                h.get("TransformMatrix", h.get("Orientation", "")) + "|" + h.get("AnatomicalOrientation", "")
            rec["descrip"] = "datafile=" + h.get("ElementDataFile", "")
            is_split = bool(SPLIT_NAME.match(os.path.basename(low)))
            if not is_split or (int(sha[:8], 16) % 50 == 0):
                _, a = C.read_metaimage(p)
                census(a, rec, "full" if not is_split else "sample50")
            else:
                rec["census_mode"] = "header-only"
                rec["kind"] = "image" if rec["dtype"] in ("MET_DOUBLE", "MET_FLOAT") else "unknown"
        elif low.endswith(".nrrd"):
            rec["fmt"] = "nrrd"
            img = sitk.ReadImage(C.lp(p))
            rec["dims"] = "x".join(str(s) for s in img.GetSize())
            rec["spacing"] = "x".join(f"{s:.6g}" for s in img.GetSpacing())
            rec["dtype"] = img.GetPixelIDTypeAsString()
            a = sitk.GetArrayFromImage(img)
            census(a.transpose(2, 1, 0) if a.ndim == 3 else a, rec, "full")
    except Exception as e:  # recorded, never fatal
        rec["error"] = f"{type(e).__name__}: {str(e)[:200]}"
    return rec


def main():
    global OUT
    if os.environ.get("A3_TEST"):
        OUT = OUT.replace(".csv", "_TEST.csv")
    inv = C.read_csv_dicts(os.path.join(C.OUT_DIR, "a3_inventory.csv"))
    todo = {}
    for r in inv:
        if r["ext"] in FMTS and r["role_guess"] != "junk":
            todo.setdefault(r["sha256"], (r["relpath"], r["role_guess"]))
    done = {}
    if os.path.exists(OUT):
        for r in C.read_csv_dicts(OUT):
            if not r.get("error") and r.get("kind") not in ("unknown", ""):
                done[r["sha256"]] = r
    work = [(s, v[0], v[1]) for s, v in todo.items() if s not in done]
    if os.environ.get("A3_TEST"):   # quick smoke test: N files of each role, written to a scratch name
        import itertools
        n = int(os.environ["A3_TEST"])
        work = list(itertools.chain.from_iterable(
            [w for w in work if w[2] == role][:n] for role in sorted({w[2] for w in work})))
    print(f"distinct files {len(todo)}, already done {len(done)}, to do {len(work)}", flush=True)
    rows = list(done.values())
    t0 = time.time()
    workers = int(os.environ.get("A3_WORKERS", "6"))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(do_one, *w) for w in work]
        for i, f in enumerate(as_completed(futs), 1):
            rows.append(f.result())
            if i % 500 == 0:
                print(f"  {i}/{len(work)}  {time.time() - t0:.0f}s", flush=True)
                C.write_csv(OUT, rows, FIELDS)
    C.write_csv(OUT, rows, FIELDS)
    from collections import Counter
    print("kinds:", Counter(r.get("kind", "?") for r in rows))
    print("errors:", sum(1 for r in rows if r.get("error")))


FIELDS = ["sha256", "rep_relpath", "role_guess", "fmt", "dims", "spacing", "dtype", "qform_code", "sform_code",
          "affine", "descrip", "census_mode", "kind", "n_unique", "integer_valued", "vmin", "vmax", "values",
          "value_counts", "nonzero_voxels", "slices_with_label", "slices_total", "error"]

if __name__ == "__main__":
    main()
