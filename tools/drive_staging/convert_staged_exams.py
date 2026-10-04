#!/usr/bin/env python3
"""One-off (historical drives, DICOM stream): CONVERT FIRST, then ingest only what converted.

Ryan's rule (2026-10-04): register an MRI exam only if it has DICOM or we actually produced
it. No row is ever registered empty; the placeholder + regen-later route is not used for
drive data, because drive data cannot be re-pulled once the staging is erased.

For every exam listed in a batch case table (original_name = "<study>/<exam>"), relative to
the batch's SCRATCH staging dir, this classifies it and, where possible, writes Dicomifier
DICOMs INTO THE STAGED EXAM (pdata/<idx>/dicom/), using the production module
tools/ingest/paravision_regen.py (Dicomifier 2.5.3 + the PixelSpacing / Window / slice-order
workarounds). It writes only under the staging dir. Status per exam:
  had-dicom            pdata/<idx>/dicom/*.dcm already present
  converted            produced N DICOMs now
  notregistered:non-image          spectroscopy / calibration method (STEAM, PRESS, ...)
  notregistered:no-recon           no pdata/<idx>/2dseq (no reconstructed image)
  notregistered:conversion-failed  Dicomifier failed (reason recorded)
Run in WSL with the dicomifier-pilot env (source conda.sh FIRST):
  PYTHONPATH=tools python tools/drive_staging/convert_staged_exams.py <staging_dir> <cases.csv> <out.csv>
"""
import csv, os, sys, glob
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from ingest import paravision_regen as pr

def log(msg, level="INFO"):
    if level != "INFO":
        print(f"  [{level}] {msg}", flush=True)

def main(staging, cases, out):
    ok, ver = pr.check_dicomifier_available()
    if not ok:
        sys.exit(f"Dicomifier not available ({ver}); source conda.sh and activate dicomifier-pilot first")
    rows = list(csv.DictReader(open(cases, encoding="utf-8")))
    res = []
    for i, r in enumerate(rows, 1):
        on = r["original_name"]; ex = os.path.join(staging, *on.split("/"))
        dcm = glob.glob(os.path.join(ex, "pdata", "*", "dicom", "*.dcm"))
        seq = glob.glob(os.path.join(ex, "pdata", "*", "2dseq"))
        st, n, why = "", len(dcm), ""
        if dcm:
            st = "had-dicom"
        else:
            nonimage, marker = pr.is_nonimage_exam(ex)
            if nonimage:
                st, why = "notregistered:non-image", f"spectroscopy/calibration method ({marker}); no reconstructed image"
            elif not seq:
                st, why = "notregistered:no-recon", "no pdata/<idx>/2dseq: no reconstructed image"
            else:
                try:
                    n = pr.regenerate_exam_dicoms(ex, ex, log)
                    st = "converted" if n > 0 else "notregistered:conversion-failed"
                    if n == 0: why = "Dicomifier produced 0 DICOMs"
                except Exception as e:  # noqa: BLE001 -- recorded per exam, never swallowed
                    st, why = "notregistered:conversion-failed", f"Dicomifier: {str(e)[:200]}"
        res.append({"original_name": on, "status": st, "n_dicom": n, "reason": why})
        print(f"[{i}/{len(rows)}] {on}: {st} {n} {why[:90]}", flush=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["original_name", "status", "n_dicom", "reason"]); w.writeheader(); w.writerows(res)
    from collections import Counter
    print("SUMMARY", dict(Counter(x["status"] for x in res)))

if __name__ == "__main__":
    main(*sys.argv[1:4])
