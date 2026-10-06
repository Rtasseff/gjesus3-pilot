"""A3 step 5c -- cine stacks with NO split volume on the drive: membership by sidecar geometry (read-only).

When the per-phase split volumes are gone, pixels cannot be compared. What can still be measured is the
DS-SEG-0001 'image-geometry-stack' evidence: in the production study, the self-gated cine acquisitions
(Bruker IgFLASH, PVM_NMovieFrames = the label's phase count range) whose matrix fits the label's in-plane
dims, grouped by slice orientation, form ONE contiguous series of ACQ_slice_offset values spaced by the slice
thickness, with exactly as many members as the label has slices. Then the stack MEMBERSHIP is established
(which acquisitions), but the slice ORDER is not (DS-SEG-0003 found 10 of 28 sessions run ascending), so it
is recorded as order_verified = no -- exactly the level DS-SEG-0001 was promoted at.
Input : a3_labels.csv (trace route session-only, why_not says no split volume). Output: a3_geostack.csv.
"""
import json
import os
import re
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a3_common as C  # noqa: E402


def sidecar(row):
    p = os.path.join(C.GJ, row["canonical_path"].strip("/").replace("/", os.sep), "metadata.json")
    with open(C.lp(p), encoding="utf-8") as f:
        return json.load(f)


def num(v):
    try:
        return float(str(v).strip("[]").split(",")[0])
    except ValueError:
        return None


def main():
    labs = C.read_csv_dicts(os.path.join(C.OUT_DIR, "a3_labels.csv"))
    todo = defaultdict(int)
    for r in labs:
        if r["trace_route"] == "session-only" and r["prod_study"] and "no split volume" in r["why_not"]:
            todo[(r["prod_study"], "x".join(r["dims"].split("x")[:3]))] += 1
    acqs = C.read_csv_dicts(C.PROD_ACQS)
    by_study = defaultdict(list)
    for a in acqs:
        if a["instrument"] == "MRI" and "/" in a["original_name"]:
            by_study[re.sub(r"__\d+$", "", a["original_name"].split("/")[0])].append(a)

    def one(key):
        study, dims = key
        X, Y, S = (int(v) for v in dims.split("x"))
        out = {"study": study, "dims": dims, "n_labels": todo[key], "status": "", "stack_acq_ids": "",
               "offsets": "", "n_cine": 0, "groups": "", "note": ""}
        cine = []
        for a in by_study.get(study, []):
            d = sidecar(a)
            disc = d.get("discovered", {})
            raw = d.get("mri", {}).get("_raw_metadata", {})
            meth = raw.get("method", {}) if isinstance(raw.get("method"), dict) else {}
            acqp = raw.get("acqp", {}) if isinstance(raw.get("acqp"), dict) else {}
            if "IgFLASH" not in (disc.get("mri_sequence_name") or ""):
                continue
            mx = [int(v) for v in (disc.get("mri_matrix") or "0x0").split("x")]
            if sorted(mx) != sorted([X, Y]):
                continue
            geo = d.get("mri", {}).get("geometry", {})
            orient = tuple(round(v, 2) for v in (geo.get("orientation") or [])[:6])
            cine.append({"acq": a["acq_id"], "exam": a["original_name"].split("/")[-1], "orient": orient,
                         "offset": num(acqp.get("ACQ_slice_offset", meth.get("PVM_SPackArrSliceOffset"))),
                         "thick": num(meth.get("PVM_SliceThick", geo.get("slice_thickness"))),
                         "frames": disc.get("mri_frame_count")})
        out["n_cine"] = len(cine)
        groups = defaultdict(list)
        for c in cine:
            groups[c["orient"]].append(c)
        out["groups"] = ";".join(str(len(g)) for g in sorted(groups.values(), key=len, reverse=True))
        if not groups:
            out["status"] = "no-cine-in-production"
            return out
        g = max(groups.values(), key=len)
        offs = sorted((c["offset"] for c in g if c["offset"] is not None), reverse=True)
        th = g[0]["thick"] or 0.8
        steps = [round(a - b, 3) for a, b in zip(offs, offs[1:])]
        contiguous = bool(steps) and all(abs(s - th) <= 0.11 for s in steps)
        out["offsets"] = ";".join(f"{o:g}" for o in offs)
        if len(g) == S and contiguous and len(set(offs)) == S:
            out["status"] = "geometry-stack"
            out["stack_acq_ids"] = ";".join(c["acq"] for c in sorted(g, key=lambda c: -c["offset"]))
            out["note"] = f"{S} contiguous short-axis IgFLASH members (step ~{th} mm); listed by descending offset; order NOT verified"
        elif len(g) > S:
            out["status"] = "more-candidates-than-slices"
            out["note"] = f"{len(g)} same-orientation cine acquisitions for a {S}-slice label; membership not decidable without pixels"
        elif len(g) < S:
            out["status"] = "production-incomplete"
            out["note"] = f"production holds {len(g)} same-orientation cine acquisitions for a {S}-slice label"
        else:
            out["status"] = "not-contiguous"
            out["note"] = f"offset steps {steps}"
        return out

    with ThreadPoolExecutor(max_workers=6) as ex:
        res = list(ex.map(one, list(todo)))
    C.write_csv(os.path.join(C.OUT_DIR, "a3_geostack.csv"), res)
    from collections import Counter
    print(len(res), Counter(r["status"] for r in res))


if __name__ == "__main__":
    main()
