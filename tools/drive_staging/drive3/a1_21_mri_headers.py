"""A1 step 2b: read the ParaVision parameter files of every canonical exam copy (read-only).

For each canonical exam folder: `acqp` and `method` (JCAMP-DX, parsed with the repo's
tools/ingest/jcampdx.py); for each study folder copy: `subject`. Nothing else is opened.
The non-image test is the production one (tools/ingest/paravision_regen.py is_nonimage_exam):
a case-insensitive STEAM / PRESS / WOBBLE in `Method` + `PULPROG`.

Writes a1\\mri_exam_headers.csv and caches the parsed fields.

    python a1_21_mri_headers.py
"""
import concurrent.futures as cf
import os
import sys

from a1_common import TOOLS, cache_load, cache_save, lp, staged, write_csv

sys.path.insert(0, TOOLS)
from ingest import jcampdx  # noqa: E402  (pure parser; no I/O beyond opening the given file)

NONIMAGE = ("STEAM", "PRESS", "WOBBLE")          # = paravision_regen._NONIMAGE_METHOD_MARKERS
ACQP_KEYS = ["ACQ_scan_name", "ACQ_method", "PULPROG", "ACQ_time", "ACQ_abs_time", "ACQ_station",
             "ACQ_sw_version", "ACQ_protocol_name", "ACQ_operator", "ACQ_institution", "NR", "NI", "ACQ_dim"]
SUBJ_KEYS = ["SUBJECT_id", "SUBJECT_study_name", "SUBJECT_name_string", "SUBJECT_date", "SUBJECT_type",
             "SUBJECT_study_nr", "SUBJECT_remarks", "SUBJECT_weight"]


def s(v):
    if isinstance(v, (list, tuple)):
        v = " ".join(str(x) for x in v)
    return " ".join(str(v).split()) if v is not None else ""


def read_exam(c):
    out = {"exam_dir": c["exam_dir"], "err": ""}
    try:
        a = jcampdx.parse_file(lp(staged(os.path.join(c["exam_dir"], "acqp"))))
        m = jcampdx.parse_file(lp(staged(os.path.join(c["exam_dir"], "method"))))
        for k in ACQP_KEYS:
            out[k] = s(a.get(k, ""))
        out["Method"] = s(m.get("Method", ""))
        sig = (out["Method"] + " " + out["PULPROG"]).lower()
        out["nonimage_marker"] = next((x for x in NONIMAGE if x.lower() in sig), "")
    except Exception as e:  # noqa: BLE001 -- recorded per exam
        out["err"] = f"{type(e).__name__}: {str(e)[:150]}"
    return out


def read_subject(sd):
    out = {"study_dir": sd, "err": ""}
    try:
        d = jcampdx.parse_file(lp(staged(os.path.join(sd, "subject"))))
        for k in SUBJ_KEYS:
            out[k] = s(d.get(k, ""))
    except Exception as e:  # noqa: BLE001
        out["err"] = f"{type(e).__name__}: {str(e)[:150]}"
    return out


def main():
    copies = cache_load("mri_copies")
    can = [c for c in copies.values() if c["canonical"]]
    print(f"canonical exam copies: {len(can):,}")
    with cf.ThreadPoolExecutor(16) as ex:
        hdr = list(ex.map(read_exam, can))
    sds = sorted({c["study_dir"] for c in copies.values()})
    with cf.ThreadPoolExecutor(16) as ex:
        subj = list(ex.map(read_subject, sds))
    cache_save("mri_headers", {h["exam_dir"]: h for h in hdr})
    cache_save("mri_subjects", {h["study_dir"]: h for h in subj})
    keyed = {c["exam_dir"]: c for c in can}
    rows = []
    for h in hdr:
        c = keyed[h["exam_dir"]]
        sj = next((x for x in subj if x["study_dir"] == c["study_dir"]), {})
        rows.append({"exam_key": c["key"], "exam_dir": c["exam_dir"], **{k: h.get(k, "") for k in ACQP_KEYS},
                     "Method": h.get("Method", ""), "nonimage_marker": h.get("nonimage_marker", ""),
                     **{k: sj.get(k, "") for k in SUBJ_KEYS}, "err": h["err"] or sj.get("err", "")})
    rows.sort(key=lambda r: r["exam_key"])
    write_csv("mri_exam_headers.csv", rows, list(rows[0].keys()))
    print(f"errors: exams {sum(1 for h in hdr if h['err'])}, subjects {sum(1 for h in subj if h['err'])}")
    print(f"non-image (STEAM/PRESS/WOBBLE): {sum(1 for h in hdr if h.get('nonimage_marker'))}")


if __name__ == "__main__":
    main()
