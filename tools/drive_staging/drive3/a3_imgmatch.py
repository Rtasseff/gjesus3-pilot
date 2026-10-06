"""A3 step 5b -- identify NIfTI exam conversions that sit beside labels but name no study (read-only).

Some label folders (e.g. 'NIFTI-m91-0522') carry the animal and protocol but no session or date. The
label's dims + affine equal a NIfTI conversion beside it (a3_trace.py), and that conversion is a copy of one
production acquisition's reconstruction. Its first 2-D frame is normalised-cross-correlated (8 in-plane
orientations) against frame 01 of every reconstruction of every production MRI acquisition of that animal
(subject <animal>-AE-biomaGUNE-<protocol>). Decided only when the best match is bit-identical (NCC >= 0.9999)
and no other acquisition is; the exam number in the image's name is then checked against the matched
original_name as an independent confirmation.
Input : a3_img_todo.csv. Output: a3_imgmatch.csv.
"""
import os
import re
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a3_common as C  # noqa: E402

import numpy as np  # noqa: E402
import pydicom  # noqa: E402


def ncc(a, b):
    a = a - a.mean()
    b = b - b.mean()
    d = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / d) if d > 0 else 0.0


def orientations(img):
    out = []
    for t in (img, img.T):
        out += [t, t[::-1, :], t[:, ::-1], t[::-1, ::-1]]
    return out


def main():
    todo = C.read_csv_dicts(os.path.join(C.OUT_DIR, "a3_img_todo.csv"))
    reg = C.read_csv_dicts(os.path.join(C.REG, "registry_raw.csv"))
    acqs = {a["acq_id"]: a for a in C.read_csv_dicts(C.PROD_ACQS)}
    by_subj = defaultdict(list)
    for r in reg:
        if r["instrument"] == "MRI":
            for s in r["subject_ids"].split(";"):
                if s:
                    by_subj[s].append(r["acq_id"])
    frames = defaultdict(dict)
    with open(C.PROD_SHA, encoding="utf-8") as f:
        next(f)
        for line in f:
            sha, acq, inst, proj, rel = line.rstrip("\n").split(",", 4)
            m = re.search(r"recon(\d+)_frame01\.dcm$", rel) if inst == "MRI" else None
            if m:
                frames[acq][int(m.group(1))] = rel

    def one(t):
        out = dict(t)
        subj = f"{t['animal']}-AE-biomaGUNE-{t['protocol']}" if t["animal"] and t["protocol"] else ""
        cands = by_subj.get(subj, [])
        out.update(subject=subj, n_candidates=len(cands), status="", best_acq="", best_original_name="",
                   best_ncc="", runner_up_acq="", runner_up_ncc="", exam_check="")
        if not cands:
            out["status"] = "no-production-acquisitions-for-subject"
            return out
        im = C.load_nifti(C.staged_path(t["image_relpath"]))
        a = np.asanyarray(im.dataobj).astype(np.float64)
        while a.ndim > 2:
            a = a[..., 0]
        scores = []
        for acq in cands:
            for k, rel in frames.get(acq, {}).items():
                row = acqs[acq]
                p = os.path.join(C.GJ, row["canonical_path"].strip("/").replace("/", os.sep), rel.replace("/", os.sep))
                try:
                    f = pydicom.dcmread(C.lp(p), force=True).pixel_array.astype(np.float64)
                except Exception:  # noqa: BLE001
                    continue
                best = max((ncc(a, o) for o in orientations(f) if o.shape == a.shape), default=-2.0)
                scores.append((best, acq, k))
        scores.sort(reverse=True)
        if not scores:
            out["status"] = "no-comparable-frames"
            return out
        top = scores[0]
        second = next((s for s in scores[1:] if s[1] != top[1]), (0.0, "", 0))
        on = acqs[top[1]]["original_name"]
        out.update(best_acq=top[1], best_original_name=on, best_ncc=round(top[0], 5),
                   runner_up_acq=second[1], runner_up_ncc=round(second[0], 5))
        exam = on.split("/")[-1] if "/" in on else ""
        out["exam_check"] = "match" if exam == t["exam_in_name"] else f"name says exam {t['exam_in_name']}, production exam {exam}"
        out["status"] = "bit-identical" if (top[0] >= 0.9999 and second[0] < 0.9999) else "not-decided"
        return out

    with ThreadPoolExecutor(max_workers=6) as ex:
        res = list(ex.map(one, todo))
    C.write_csv(os.path.join(C.OUT_DIR, "a3_imgmatch.csv"), res)
    from collections import Counter
    print(len(res), Counter(r["status"] for r in res), Counter(r["exam_check"][:5] for r in res))


if __name__ == "__main__":
    main()
