"""A1 step 2d: how production's recon<idx>_frame<NN>.dcm relate to the scanner's MRIm<NN>.dcm.

Every byte comparison in A1 rests on this, so it is checked on real files, not assumed:
  1. The ingest code (tools/ingest_raw.py, mri_paravision_v2; tools/ingest/paravision_metadata.py
     _plan_dcm_target) copies pdata/<idx>/dicom/MRIm<NN>.dcm with shutil.copyfile to
     <ACQ-ID>.data/recon<idx>_frame<NN>.dcm: a rename, not a rewrite.
  2. Measured over every name-matched exam in a1_22 (class a1: identical SHA-256 under that
     mapping), and re-hashed here for a sample, from the production file on J: (read-only).
  3. For the exams whose files carry the same names but different bytes (class b-export), a
     sample of file pairs is opened with pydicom: is the pixel data identical? which header
     elements differ? (values of identifying elements are never written; only element names
     and, for times/UIDs, whether they differ).

Writes a1\\dicom_relation_sample.csv and a1\\dicom_relation_summary.txt.

    python a1_23_dicom_relation.py
"""
import collections
import hashlib
import os
import random

from a1_common import (NAS, cache_load, load_prod_acqs, lp, out_path, sha256_file, staged, write_csv)

SAFE_SHOW = {"InstanceCreationDate", "InstanceCreationTime", "ContentDate", "ContentTime", "SeriesDate",
             "SeriesTime", "AcquisitionDate", "AcquisitionTime", "StudyDate", "StudyTime",
             "SoftwareVersions", "ImplementationVersionName", "ImplementationClassUID",
             "TransferSyntaxUID", "SeriesNumber", "InstanceNumber", "ImageType", "Rows", "Columns",
             "WindowCenter", "WindowWidth", "PixelSpacing", "SliceThickness", "Manufacturer",
             "ManufacturerModelName", "StationName", "SeriesDescription", "ProtocolName"}


def elements(ds):
    out = {}
    for el in ds.iterall():
        if el.tag == (0x7FE0, 0x0010):
            continue
        kw = el.keyword or str(el.tag)
        try:
            out[kw] = repr(el.value)[:200]
        except Exception:  # noqa: BLE001
            out[kw] = "?"
    return out


def compare_pair(drive_rel, prod_abs):
    import pydicom
    a = pydicom.dcmread(lp(staged(drive_rel)), force=True)
    b = pydicom.dcmread(lp(prod_abs), force=True)
    pa = hashlib.sha256(a.PixelData).hexdigest() if "PixelData" in a else ""
    pb = hashlib.sha256(b.PixelData).hexdigest() if "PixelData" in b else ""
    ea, eb = elements(a), elements(b)
    meta_a = {e.keyword: repr(e.value)[:120] for e in a.file_meta} if hasattr(a, "file_meta") else {}
    meta_b = {e.keyword: repr(e.value)[:120] for e in b.file_meta} if hasattr(b, "file_meta") else {}
    diff = sorted(k for k in set(ea) | set(eb) if ea.get(k) != eb.get(k))
    mdiff = sorted(k for k in set(meta_a) | set(meta_b) if meta_a.get(k) != meta_b.get(k))
    shown = {k: (ea.get(k, "-"), eb.get(k, "-")) for k in diff if k in SAFE_SHOW}
    return {"pixel_equal": "Y" if pa and pa == pb else ("no-pixels" if not pa else "N"),
            "n_elements_drive": len(ea), "n_elements_prod": len(eb), "differing_elements": ";".join(diff),
            "differing_file_meta": ";".join(mdiff),
            "shown_values (drive || prod)": " ; ".join(f"{k}: {v[0]} || {v[1]}" for k, v in sorted(shown.items()))}


def main():
    rows = cache_load("mri_exam_rows")
    copies = cache_load("mri_copies")
    keys = cache_load("mri_keys")
    acqs = load_prod_acqs()
    rnd = random.Random(20261006)
    out, L = [], []

    def canon(key):
        return next(copies[e] for e in keys[key] if copies[e]["canonical"])

    def prod_path(acq, name):
        cp = acqs[acq]["canonical_path"].strip("/").replace("/", os.sep)
        return os.path.join(NAS, cp, f"{acq}.data", name)

    # 1+2: re-hash a sample of class-a1 pairs from the production files themselves
    a1 = [r for r in rows if r["class_detail"] == "a1-identical"]
    by_cfg = collections.defaultdict(list)
    for r in a1:
        by_cfg[r["prod_config"]].append(r)
    sample_a = []
    for cfg, rs in sorted(by_cfg.items()):
        sample_a += rnd.sample(rs, min(3, len(rs)))
    def inner_of(c):
        out_ = {}
        for p in c["inner"]:
            parts = p.split("\\")
            if len(parts) == 4 and parts[0].lower() == "pdata" and parts[2].lower() == "dicom" \
                    and parts[3].lower().startswith("mrim"):
                n = parts[3][4:-4]
                out_[f"recon{parts[1]}_frame{n.zfill(2) if len(n) < 2 else n}.dcm"] = p
        return out_

    for r in sample_a:
        c = canon(r["exam_key"])
        acq = r["acq_ids"].split(";")[0]
        name = sorted(c["dcm"])[0]
        src = c["exam_dir"] + "\\" + inner_of(c)[name]
        pp = prod_path(acq, name)
        h_prod = sha256_file(pp)
        out.append({"check": "a1 re-hash", "exam_key": r["exam_key"], "acq_id": acq, "prod_config": r["prod_config"],
                    "drive_file": src, "prod_file": pp, "drive_sha_manifest": c["dcm"][name],
                    "prod_sha_rehashed": h_prod, "equal": "Y" if h_prod == c["dcm"][name] else "N"})
    L.append(f"a1 re-hash sample: {len(sample_a)} exams over {len(by_cfg)} ingest configs; "
             f"equal {sum(1 for o in out if o['equal'] == 'Y')}/{len(out)}")
    L.append("a1 exams per production ingest config: " + "; ".join(f"{k.rsplit('/',1)[-1]} {len(v)}" for k, v in sorted(by_cfg.items())))

    # 3: open EVERY same-name/different-bytes pair of the b-export / b-mixed exams (not a sample)
    bx = [r for r in rows if r["class_detail"].startswith("b-export") or r["class_detail"].startswith("b-mixed")]
    studies = sorted({r["study"] for r in bx})
    L.append(f"b-export/b-mixed: {len(bx)} exams in {len(studies)} studies; configs "
             + str(collections.Counter(r['prod_config'] for r in bx)))
    import csv as _csv
    from a1_common import PROD_SHA
    pfiles = collections.defaultdict(dict)
    want = {r["acq_ids"].split(";")[0] for r in bx}
    with open(PROD_SHA, encoding="utf-8", newline="") as f:
        for x in _csv.DictReader(f):
            if x["acq_id"] in want:
                pfiles[x["acq_id"]][x["relpath"].rsplit("/", 1)[-1]] = x["sha256"]
    pairs = []
    for r in bx:
        c = canon(r["exam_key"])
        acq = r["acq_ids"].split(";")[0]
        # drive inner path for each mapped name
        inner_of = {}
        for p in c["inner"]:
            parts = p.split("\\")
            if len(parts) == 4 and parts[0].lower() == "pdata" and parts[2].lower() == "dicom" and parts[3].lower().startswith("mrim"):
                n = parts[3][4:-4]
                inner_of[f"recon{parts[1]}_frame{n.zfill(2) if len(n) < 2 else n}.dcm"] = p
        for name, sha in c["dcm"].items():
            ps = pfiles[acq].get(name)
            if ps and ps != sha:
                pairs.append((r, acq, c["exam_dir"] + "\\" + inner_of[name], prod_path(acq, name)))
    agg_diff = collections.Counter()
    pix = collections.Counter()
    import concurrent.futures as cf

    def job(t):
        r, acq, src, pp = t
        try:
            return t, compare_pair(src, pp)
        except Exception as e:  # noqa: BLE001
            return t, {"pixel_equal": f"error {type(e).__name__}", "differing_elements": "", "differing_file_meta": "",
                       "n_elements_drive": "", "n_elements_prod": "", "shown_values (drive || prod)": str(e)[:100]}
    with cf.ThreadPoolExecutor(12) as ex:
        res_all = list(ex.map(job, pairs))
    for (r, acq, src, pp), res in res_all:
        pix[res["pixel_equal"]] += 1
        agg_diff[res["differing_elements"] or "(none)"] += 1
        out.append({"check": "b-export pair", "exam_key": r["exam_key"], "acq_id": acq, "prod_config": r["prod_config"],
                    "drive_file": src, "prod_file": pp, **res})
    L.append(f"b-export/b-mixed: ALL {len(pairs)} same-name, different-bytes file pairs opened; pixel data equal: {dict(pix)}")
    L.append("sets of differing header elements (pairs): " + "; ".join(f"[{k}] {v}" for k, v in agg_diff.most_common()))
    fields = ["check", "exam_key", "acq_id", "prod_config", "drive_file", "prod_file", "drive_sha_manifest",
              "prod_sha_rehashed", "equal", "pixel_equal", "n_elements_drive", "n_elements_prod",
              "differing_elements", "differing_file_meta", "shown_values (drive || prod)"]
    write_csv("dicom_relation_sample.csv", out, fields)
    with open(out_path("dicom_relation_summary.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
