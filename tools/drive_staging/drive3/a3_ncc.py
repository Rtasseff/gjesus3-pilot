"""A3 step 5 -- resolve cine label stacks to production ACQ-IDs by direct pixel cross-correlation (read-only).

The DS-SEG-0003 / DS-SEG-0004 method, applied to every (study, label dims) pair a3_trace.py found:
the masks were traced on per-phase split volumes (Time_<t>_rat_<study>.mhd, one 3-D stack per cardiac
phase, no world coordinates). Each split slice z is a copy of ONE single-slice cine acquisition's frame t.
For phases t in {1, 8, 15} (those the drive holds), every split slice is normalised-cross-correlated
against frame t of every production acquisition of the study (every reconstruction kept, every one of the
8 in-plane orientations), and assigned to the best. A stack is 'direct-ncc' when, at every phase checked,
each slice's best match is unique, NCC >= 0.80, the runner-up acquisition is at least 0.02 lower, no
acquisition is used twice, and the phases agree. Anything else is recorded as what it is -- never forced.

Input : a3_cine_ncc_todo.csv (from a3_trace.py), a3_inventory.csv, a3_headers.csv, the production index.
Output: a3_ncc_stacks.csv (one row per stack), a3_ncc_slices.csv (one row per stack x slice x phase).
"""
import os
import re
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a3_common as C  # noqa: E402

import numpy as np  # noqa: E402
import pydicom  # noqa: E402
import SimpleITK as sitk  # noqa: E402

SPLIT_RE = re.compile(r"^Time_(?P<t>\d+)_rat_(?P<study>.+)\.mhd$", re.I)
PHASES = (1, 8, 15)
NCC_MIN, MARGIN_MIN = 0.80, 0.02


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


def load_prod_files():
    acqs = {a["acq_id"]: a for a in C.read_csv_dicts(C.PROD_ACQS)}
    files = defaultdict(dict)   # acq -> {(recon, frame): relpath}
    with open(C.PROD_SHA, encoding="utf-8") as f:
        next(f)
        for line in f:
            sha, acq, inst, proj, rel = line.rstrip("\n").split(",", 4)
            if inst != "MRI":
                continue
            m = re.search(r"recon(\d+)_frame(\d+)\.dcm$", rel)
            if m:
                files[acq][(int(m.group(1)), int(m.group(2)))] = rel
    by_study = defaultdict(list)
    by_session = defaultdict(list)
    for a in acqs.values():
        if a["instrument"] == "MRI" and "/" in a["original_name"]:
            a["study"] = re.sub(r"__\d+$", "", a["original_name"].split("/")[0])
            by_study[a["study"]].append(a)
            if a["session_id"]:
                by_session[a["session_id"]].append(a)
    return acqs, files, by_study, by_session


def prod_path(acq_row, rel):
    return os.path.join(C.GJ, acq_row["canonical_path"].strip("/").replace("/", os.sep), rel.replace("/", os.sep))


def read_dcm(path):
    d = pydicom.dcmread(C.lp(path), force=True)
    return d.pixel_array.astype(np.float64)


def resolve(task, splits_for, acqs_in_study, files):
    st, dims = task["study"], task["dims"]
    res = {"study": st, "dims": dims, "status": "", "n_slices": "", "phases_checked": "", "stack_acq_ids": "",
           "recon_used": "", "orientation": "", "ncc_min": "", "margin_min": "", "n_candidates": 0, "note": ""}
    slice_rows = []
    by_phase = {}
    acqs_with_frames = set()
    cands = [a for a in acqs_in_study.get(st, [])]
    res["n_candidates"] = len(cands)
    if not cands:
        res["status"] = "no-production-acquisitions"
        return res, slice_rows
    for t in PHASES:
        sp = [x for x in splits_for.get(st, {}).get(t, []) if x[2].split("x")[:3] == dims.split("x")[:3]]
        if not sp:
            continue
        # long-path / non-ASCII safe reader; (x, y, z) -> (z, y, x) = SimpleITK's slice order
        _, arr = C.read_metaimage(C.staged_path(sp[0][1]))
        vol = np.ascontiguousarray(arr.transpose(2, 1, 0)).astype(np.float64)   # (S, Y, X)
        S = vol.shape[0]
        # frame t of every candidate acquisition, every recon kept
        frames = []
        for a in cands:
            for (k, fr), rel in files.get(a["acq_id"], {}).items():
                if fr == t:
                    try:
                        frames.append((a["acq_id"], k, read_dcm(prod_path(a, rel))))
                    except Exception as e:  # noqa: BLE001
                        res["note"] += f" read-fail {a['acq_id']} r{k}: {type(e).__name__};"
        if not frames:
            continue
        acqs_with_frames.update(a for a, _, _ in frames)
        best = []
        for z in range(S):
            sl = vol[z]
            scores = []
            for acq, k, fimg in frames:
                bo, bi = -2.0, -1
                for oi, o in enumerate(orientations(fimg)):
                    if o.shape == sl.shape:
                        v = ncc(sl, o)
                        if v > bo:
                            bo, bi = v, oi
                if bi >= 0:
                    scores.append((bo, acq, k, bi))
            scores.sort(reverse=True)
            if not scores:
                best.append(None)
                continue
            top = scores[0]
            second = next((s for s in scores[1:] if s[1] != top[1]), (0.0, "", 0, -1))
            best.append((top, second))
            slice_rows.append({"study": st, "dims": dims, "phase": t, "z": z, "acq_id": top[1], "recon": top[2],
                               "orientation": top[3], "ncc": round(top[0], 4), "runner_up_acq": second[1],
                               "runner_up_ncc": round(second[0], 4), "margin": round(top[0] - second[0], 4)})
        by_phase[t] = best
    if not by_phase:
        res["status"] = "no-frames-or-splits"
        return res, slice_rows
    # agreement and quality. A slice is decided when its best match is BIT-IDENTICAL (NCC >= 0.9999) to one
    # acquisition and to no other, or else when NCC >= NCC_MIN with a runner-up at least MARGIN_MIN lower.
    # (Adjacent short-axis slices of one stack correlate at 0.98-0.99, so a bit-identical best beats them.)
    def decided(b):
        if not b:
            return False
        (best, _, _, _), (second, _, _, _) = b
        return (best >= 0.9999 and second < 0.9999) or (best >= NCC_MIN and best - second >= MARGIN_MIN)
    stacks = {t: [b[0][1] if b else None for b in v] for t, v in by_phase.items()}
    first = next(iter(stacks.values()))
    agree = all(s == first for s in stacks.values())
    ok_scores = all(decided(b) for v in by_phase.values() for b in v)
    n_with_frames = len(acqs_with_frames)
    unique = all(len([x for x in s if x]) == len(set(x for x in s if x)) for s in stacks.values())
    allb = [b for v in by_phase.values() for b in v if b]
    res.update(n_slices=len(first), phases_checked=";".join(str(t) for t in by_phase),
               stack_acq_ids=";".join(x or "?" for x in first),
               recon_used=";".join(sorted({str(b[0][2]) for b in allb})),
               orientation=";".join(sorted({str(b[0][3]) for b in allb})),
               ncc_min=round(min(b[0][0] for b in allb), 4), margin_min=round(min(b[0][0] - b[1][0] for b in allb), 4))
    bit = all(b and b[0][0] >= 0.9999 for v in by_phase.values() for b in v)
    if agree and ok_scores and unique and None not in first:
        res["status"] = "direct-ncc"
        res["note"] += " every slice bit-identical (NCC>=0.9999) to its production frame" if bit else ""
    elif n_with_frames < len(first):
        res["status"] = "production-incomplete"
        res["note"] += f" production holds {n_with_frames} acquisition(s) with these frames for a {len(first)}-slice stack"
    else:
        why = []
        if not agree:
            why.append("phases disagree")
        if not ok_scores:
            why.append(f"some slice below NCC {NCC_MIN} or margin {MARGIN_MIN}")
        if not unique:
            why.append("an acquisition matched two slices")
        res["status"] = "ambiguous"
        res["note"] += " " + "; ".join(why)
    return res, slice_rows


def main():
    todo = C.read_csv_dicts(os.path.join(C.OUT_DIR, "a3_cine_ncc_todo.csv"))
    inv = C.read_csv_dicts(os.path.join(C.OUT_DIR, "a3_inventory.csv"))
    hdr = {r["sha256"]: r for r in C.read_csv_dicts(os.path.join(C.OUT_DIR, "a3_headers.csv"))}
    acqs, files, by_study, by_session = load_prod_files()
    splits_for = defaultdict(lambda: defaultdict(list))
    for r in inv:
        if r["role_guess"] == "image_split" and r["ext"] == ".mhd":
            m = SPLIT_RE.match(r["name"])
            if m:
                st = C.split_study(m.group("study"), by_session)   # session-named splits -> production study
                splits_for[st][int(m.group("t"))].append((r["sha256"], r["relpath"], hdr.get(r["sha256"], {}).get("dims", "")))
    if os.environ.get("A3_TEST"):
        todo = todo[: int(os.environ["A3_TEST"])]
    stacks, slices = [], []
    # resume: keep stacks already resolved (and their slice rows); recompute errors only
    st_path, sl_path = os.path.join(C.OUT_DIR, "a3_ncc_stacks.csv"), os.path.join(C.OUT_DIR, "a3_ncc_slices.csv")
    if not os.environ.get("A3_TEST") and os.path.exists(st_path):
        keep = {(r["study"], r["dims"]): r for r in C.read_csv_dicts(st_path)
                if r.get("status") not in ("error", "", "no-frames-or-splits", "ambiguous")}
        stacks = list(keep.values())
        if os.path.exists(sl_path):
            slices = [r for r in C.read_csv_dicts(sl_path) if (r["study"], r["dims"]) in keep]
        todo = [t for t in todo if (t["study"], t["dims"]) not in keep]
        print(f"resume: {len(keep)} stacks kept, {len(todo)} to do", flush=True)
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=int(os.environ.get("A3_WORKERS", "6"))) as ex:
        futs = {ex.submit(resolve, t, splits_for, by_study, files): t for t in todo}
        for i, f in enumerate(as_completed(futs), 1):
            try:
                res, sl = f.result()
            except Exception as e:  # noqa: BLE001
                t = futs[f]
                res, sl = {"study": t["study"], "dims": t["dims"], "status": "error", "note": f"{type(e).__name__}: {e}"}, []
            stacks.append(res)
            slices += sl
            if i % 20 == 0:
                print(f"  {i}/{len(todo)} {time.time() - t0:.0f}s", flush=True)
    suffix = "_TEST" if os.environ.get("A3_TEST") else ""
    C.write_csv(os.path.join(C.OUT_DIR, f"a3_ncc_stacks{suffix}.csv"), sorted(stacks, key=lambda x: x["study"]))
    C.write_csv(os.path.join(C.OUT_DIR, f"a3_ncc_slices{suffix}.csv"), slices)
    from collections import Counter
    print("status:", Counter(s["status"] for s in stacks))


if __name__ == "__main__":
    main()
