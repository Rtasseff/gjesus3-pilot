"""A3 step 9 -- check the promoted datasets' slice maps against this drive's split volumes (read-only).

DS-SEG-0001 was promoted with slice_order_verified = no, because the Mes-10 split volumes were believed
deleted. This drive holds split volumes for sessions of DS-SEG-0001 / -0003 / -0004; a3_ncc.py resolved each
such stack by direct pixel cross-correlation against the production DICOM. Here the two orders are compared
slice by slice. Nothing is changed in curated_datasets\\ -- this only reports agreement or disagreement.
Output: a3_slicemap_check.csv (one row per dataset session x slice).
"""
import glob
import os
import sys
from collections import defaultdict

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a3_common as C  # noqa: E402


def main():
    acqs = {a["acq_id"]: a for a in C.read_csv_dicts(C.PROD_ACQS)}
    stacks = defaultdict(list)   # session -> [(study, dims, [acq...], status)]
    for s in C.read_csv_dicts(os.path.join(C.OUT_DIR, "a3_ncc_stacks.csv")):
        if s["status"] == "direct-ncc":
            ids = s["stack_acq_ids"].split(";")
            sess = acqs.get(ids[0], {}).get("session_id", "")
            stacks[sess].append((s["study"], s["dims"], ids))
    rows = []
    for d in sorted(glob.glob(os.path.join(C.CDS, "segmentation", "*", "DS-SEG-*"))):
        sm = os.path.join(d, "slice_map.csv")
        if not os.path.exists(sm):
            continue
        ds = os.path.basename(d)
        per = defaultdict(list)
        for r in C.read_csv_dicts(sm):
            if not r["slice_index"].strip().isdigit() or r.get("excluded_from_v1", ""):
                continue   # rows of sessions the dataset itself excluded (e.g. DS-SEG-0001's Predict_Slicer session)
            per[r["session_id"]].append((int(r["slice_index"]), r["acq_id"], r.get("order_verified", "")))
        for sess, sl in sorted(per.items()):
            sl.sort()
            ds_order = [a for _, a, _ in sl]
            drive = stacks.get(sess, [])
            if not drive:
                rows.append({"dataset": ds, "session": sess, "slices": len(sl), "drive_stack": "none on drive",
                             "agreement": "", "dataset_order_verified": sl[0][2], "detail": ""})
                continue
            for study, dims, ids in drive:
                if len(ids) != len(ds_order):
                    agree = f"different slice count (drive {len(ids)} vs dataset {len(ds_order)})"
                elif ids == ds_order:
                    agree = "identical order"
                elif ids == ds_order[::-1]:
                    agree = "same members, reversed order"
                elif set(ids) == set(ds_order):
                    diff = [i for i, (a, b) in enumerate(zip(ids, ds_order)) if a != b]
                    agree = f"same members, order differs at slice(s) {diff}"
                else:
                    agree = f"different members ({len(set(ids) ^ set(ds_order))} differ)"
                rows.append({"dataset": ds, "session": sess, "slices": len(sl), "drive_stack": f"{study} {dims}",
                             "agreement": agree, "dataset_order_verified": sl[0][2],
                             "detail": "drive=" + ";".join(ids) + " | dataset=" + ";".join(ds_order)})
    C.write_csv(os.path.join(C.OUT_DIR, "a3_slicemap_check.csv"), rows)
    from collections import Counter
    print(Counter((r["dataset"], r["agreement"] or "none on drive") for r in rows))


if __name__ == "__main__":
    main()
