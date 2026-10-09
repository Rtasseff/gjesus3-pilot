"""Stream AR, step 2: every exam of every extracted study, classed as stream M / A1 class them (read-only).

    python ar_02_inventory.py [--check-parser]

For each extracted study (extract\\_manifests\\*.done) and each exam folder (a study-level entry whose name starts with
a digit, the ingest's pattern "*/[0-9]*"), from the extracted files and the extraction member list (k-space is listed
there, not extracted):
  method (method Method / acqp ACQ_method), scan name, station -> model, VisuCreationDate (exam visu_pars) and
  acqp ACQ_time, the pdata indices, those with a 2dseq, those with DICOM, the DICOM count and the DICOM-set digest
  (stream M's rule: SHA-256 over the sorted "recon<idx>_frame<NN>.dcm <sha256>" lines, from the extraction hashes),
  k-space present, the non-image marker (ingest/paravision_regen.is_nonimage_exam: STEAM / PRESS / WOBBLE), and
  class: c (DICOM present) / d (2dseq, image method: convert first) / e-nonimage / e-norecon / e-neveracquired.
Writes out\\inventory_exams.csv, out\\inventory_studies.csv, out\\inventory_summary.txt.
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ar_common as C  # noqa: E402

sys.path.insert(0, os.path.join(C.WT, "tools"))
from ingest import jcampdx  # noqa: E402
from ingest import paravision_regen as PR  # noqa: E402

MODEL = {"Biospec 70/30": "Bruker BioSpec 7T", "BIOSPEC 500": "Bruker BioSpec 11.7T"}


def clean(v):
    if isinstance(v, list):
        v = v[0] if v else ""
    return str(v or "").strip().strip("<>").strip()


def jget_slow(path, *keys):
    if not os.path.isfile(C.lp(path)):
        return ["" for _ in keys]
    try:
        d = jcampdx.parse_file(path)
    except Exception:  # noqa: BLE001 -- an unreadable parameter file is reported as blank
        return ["" for _ in keys]
    return [clean(d.get(k)) for k in keys]


jget = C.jcamp_get


def check_parser(n=400):
    """The fast reader against tools/ingest/jcampdx (and is_nonimage_exam) on n exams of the extracted studies."""
    import random
    done = C.extracted()
    exams = []
    for s, info in sorted(done.items()):
        exams += [os.path.join(info["dir"], e) for e in os.listdir(info["dir"]) if e[:1].isdigit()]
    random.seed(1)
    sample = random.sample(exams, min(n, len(exams)))
    bad = []
    for ex in sample:
        for f, keys in (("method", ("Method",)), ("acqp", ("ACQ_method", "ACQ_scan_name", "ACQ_station", "ACQ_time", "PULPROG")),
                        ("visu_pars", ("VisuCreationDate",))):
            a, b = C.jcamp_get(os.path.join(ex, f), *keys), jget_slow(os.path.join(ex, f), *keys)
            if a != b:
                bad.append((ex, f, a, b))
        if C.nonimage_marker(ex) != (PR.is_nonimage_exam(ex)[1] if os.path.isdir(ex) else ""):
            bad.append((ex, "nonimage"))
    print(f"parser check: {len(sample)} exams; disagreements {len(bad)} {bad[:5]}")
    return not bad


def num_key(x):
    return (0, int(x)) if x.isdigit() else (1, x)


def inventory_study(study, info, plan_row):
    sdir = info["dir"]
    mem = C.members(study)
    by_exam = collections.defaultdict(list)
    for m in mem:
        parts = m["member"].split("/")
        if len(parts) >= 3 and parts[1][:1].isdigit():
            by_exam[parts[1]].append((parts[2:], m))
    exams = sorted({e for e in by_exam} | {e for e in os.listdir(sdir) if e[:1].isdigit()}, key=num_key)
    out = []
    for e in exams:
        ex = os.path.join(sdir, e)
        ms = by_exam.get(e, [])
        isdir = os.path.isdir(ex)
        pdata = collections.defaultdict(lambda: {"seq": False, "dcm": []})
        ksp, kbytes = [], 0
        for parts, m in ms:
            if m["kind"] != "file":
                if len(parts) == 2 and parts[0] == "pdata" and m["kind"] == "dir":
                    pdata[parts[1]]
                continue
            if len(parts) == 1 and C.is_kspace(parts[0]):
                ksp.append(parts[0])
                kbytes += int(m["size"])
            elif len(parts) >= 2 and parts[0] == "pdata":
                rec = pdata[parts[1]]
                if len(parts) == 3 and parts[2] == "2dseq":
                    rec["seq"] = True
                elif len(parts) == 4 and parts[2] == "dicom" and parts[3].lower().endswith(".dcm"):
                    rec["dcm"].append((C.dcm_prod_name(parts[1], parts[3]), m["sha256"], int(m["size"])))
        method, = jget(os.path.join(ex, "method"), "Method")
        acq_method, scan, station, acq_time = jget(os.path.join(ex, "acqp"), "ACQ_method", "ACQ_scan_name",
                                                   "ACQ_station", "ACQ_time")
        visu, = jget(os.path.join(ex, "visu_pars"), "VisuCreationDate")
        marker = C.nonimage_marker(ex) if isdir else ""
        nonimage = bool(marker)
        idx = sorted(pdata, key=num_key)
        seq = [i for i in idx if pdata[i]["seq"]]
        dcm_idx = [i for i in idx if pdata[i]["dcm"]]
        dcms = [d for i in idx for d in pdata[i]["dcm"]]
        if dcms:
            cls, detail = "c", "c-native-dicom" + (" (some reconstructions without DICOM)" if set(seq) - set(dcm_idx) else "")
        elif nonimage:
            cls, detail = "e", f"e-nonimage ({marker})"
        elif seq:
            cls, detail = "d", "d-convertible (2dseq, image method)"
        elif ksp:
            cls, detail = "e", "e-norecon (k-space, no 2dseq)"
        else:
            cls, detail = "e", "e-neveracquired (no k-space, no 2dseq)"
        out.append({
            "study": study, "tier": plan_row["tier"], "exam": e, "original_name": f"{study}/{e}",
            "is_dir": "Y" if isdir else "N", "method": method or acq_method, "scan_name": scan, "station": station,
            "model": MODEL.get(station, f"UNKNOWN:{station}"), "visu_creation_date": visu, "acq_time": acq_time,
            "acq_datetime": visu or acq_time, "date_source": "visu_pars.VisuCreationDate" if visu else
            ("acqp.ACQ_time" if acq_time else ""), "pdata": ";".join(idx), "recons_2dseq": ";".join(seq),
            "recons_dicom": ";".join(dcm_idx), "recons_without_dicom": ";".join(i for i in seq if i not in dcm_idx),
            "n_dicom": len(dcms), "dicom_bytes": sum(d[2] for d in dcms), "zero_byte_dicom": sum(1 for d in dcms if d[2] == 0),
            "dicom_set_sha256": C.dicom_set_digest([(d[0], d[1]) for d in dcms]) if dcms else "",
            "kspace": ";".join(ksp), "kspace_bytes": kbytes, "nonimage_marker": marker,
            "class": cls, "class_detail": detail, "files": len(ms)})
    subj_id, subj_study = jget(os.path.join(sdir, "subject"), "SUBJECT_id", "SUBJECT_study_name")
    return out, {"subject_id": subj_id, "subject_study_name": subj_study}


def main():
    if "--check-parser" in sys.argv:
        sys.exit(0 if check_parser() else 1)
    plan = C.pull_plan()
    done = C.extracted()
    exams, studies = [], []
    for i, (study, info) in enumerate(sorted(done.items()), 1):
        if not info["dir"]:
            raise SystemExit(f"{study}: extracted, but its folder is not found under {C.EXTRACT}")
        p = plan[study]
        ex, subj = inventory_study(study, info, p)
        exams += ex
        cc = collections.Counter(e["class"] for e in ex)
        studies.append({"study": study, "tier": p["tier"], "census_kind": p["kind"], "census_protocol": p["protocol"],
                        "census_animal": p["animal"], "dir": info["dir"], "exams": len(ex), "c": cc["c"], "d": cc["d"],
                        "e": cc["e"], "n_dicom": sum(e["n_dicom"] for e in ex),
                        "models": ";".join(sorted({e["model"] for e in ex if e["class"] != "e"})),
                        "first_date": min((e["acq_datetime"][:10] for e in ex if e["acq_datetime"]), default=""),
                        "dates": ";".join(sorted({e["acq_datetime"][:10] for e in ex if e["acq_datetime"]})),
                        **subj})
        if i % 100 == 0:
            print(f"  {i}/{len(done)}", flush=True)
    C.write_csv(C.out("inventory_exams.csv"), exams)
    C.write_csv(C.out("inventory_studies.csv"), studies)
    L = [f"studies extracted and inventoried: {len(studies)} {dict(collections.Counter(s['tier'] for s in studies))}",
         f"exams: {len(exams)}; by tier and class: "
         f"{dict(sorted(collections.Counter((e['tier'], e['class']) for e in exams).items()))}",
         f"class detail: {dict(collections.Counter(e['class_detail'] for e in exams).most_common())}",
         f"models (registerable exams): {dict(collections.Counter(e['model'] for e in exams if e['class'] != 'e'))}",
         f"date source (registerable): {dict(collections.Counter(e['date_source'] for e in exams if e['class'] != 'e'))}",
         f"VisuCreationDate day != ACQ_time day (registerable): "
         f"{sum(1 for e in exams if e['class'] != 'e' and e['visu_creation_date'][:10] != e['acq_time'][:10])}",
         f"zero-byte DICOM: {sum(e['zero_byte_dicom'] for e in exams)}; exam entries that are not folders: "
         f"{sum(1 for e in exams if e['is_dir'] != 'Y')}",
         f"studies with no registerable exam: {sum(1 for s in studies if not (s['c'] or s['d']))} "
         f"{dict(collections.Counter(s['tier'] for s in studies if not (s['c'] or s['d'])))}"]
    open(C.out("inventory_summary.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
