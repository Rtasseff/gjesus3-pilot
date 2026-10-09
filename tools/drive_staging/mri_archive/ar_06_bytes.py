"""Stream AR, step 6: the byte-level dedup check -- no planned DICOM file is already in production (read-only).

    python ar_06_bytes.py

Reads checksums.json of every MRI / XMRI acquisition in the LIVE registry (J:, read-only; 8 reader threads) into a
{sha256: acq_id} index (out\\prod_mri_dicom_sha256.csv), then checks every DICOM file of every planned exam (out\\
plan_exams.csv; the extraction hashes) and of every Dicomifier output once converted (re-hashed on D:) against it.
A name-based dedup cannot see a re-registration under another study name; this can (A1's "0 SHA-256 matches").
Writes out\\bytes_check.csv (one row per planned exam with any file production holds) and out\\bytes_check.txt.
"""
import collections
import concurrent.futures as cf
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ar_common as C  # noqa: E402


def read_cj(r):
    p = os.path.join(C.NAS, r["canonical_path"].strip("/").replace("/", os.sep), "checksums.json")
    try:
        return r["acq_id"], json.load(open(p, encoding="utf-8")).get("files", {}), ""
    except Exception as e:  # noqa: BLE001 -- reported
        return r["acq_id"], {}, f"{type(e).__name__}: {e}"


def main():
    reg = [r for r in C.live_registry() if r["instrument"] in ("MRI", "XMRI")]
    idx, errs = {}, []
    with cf.ThreadPoolExecutor(8) as ex:
        for i, (acq, files, err) in enumerate(ex.map(read_cj, reg), 1):
            if err:
                errs.append((acq, err))
            for k, h in files.items():
                idx.setdefault(h, acq)
            if i % 2000 == 0:
                print(f"  {i}/{len(reg)}", flush=True)
    C.write_csv(C.out("prod_mri_dicom_sha256.csv"), [{"sha256": h, "acq_id": a} for h, a in idx.items()])
    plan = [x for x in C.rows(os.path.join(C.OUT, "plan_exams.csv")) if x["disposition"] != "not-registered"]
    done = C.extracted()
    hits, n_files = [], 0
    by_exam = {}
    for s in sorted({x["study"] for x in plan}):
        for m in C.members(s):
            parts = m["member"].split("/")
            if m["action"] == "extracted" and len(parts) == 6 and parts[2] == "pdata" and parts[4] == "dicom":
                by_exam.setdefault(f"{s}/{parts[1]}", []).append(m["sha256"])
    for x in plan:
        hs = list(by_exam.get(x["original_name"], []))
        if x["disposition"] == "convert-first":
            for f in glob.glob(os.path.join(done[x["study"]]["dir"], x["exam"], "pdata", "*", "dicom", "*.dcm")):
                hs.append(C.sha256(f))
        n_files += len(hs)
        h = [idx[v] for v in hs if v in idx]
        if h:
            hits.append({"original_name": x["original_name"], "files": len(hs), "in_production": len(h),
                         "acq_ids": ";".join(sorted(set(h))[:10])})
    C.write_csv(C.out("bytes_check.csv"), hits, ["original_name", "files", "in_production", "acq_ids"])
    L = [f"production MRI/XMRI acquisitions read: {len(reg)}; unreadable checksums.json: {len(errs)} {errs[:3]}; "
         f"distinct DICOM sha256: {len(idx)}",
         f"planned exams checked: {len(plan)}; DICOM files hashed: {n_files}; exams with any file production holds: "
         f"{len(hits)} {hits[:5]}"]
    open(C.out("bytes_check.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
