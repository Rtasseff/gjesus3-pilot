"""Stream AR, Part 1: drive 3's MRI (stream M, in production) against the MRI platform's archive copy (read-only).

    python ar_03_archive_check.py [--no-pixels]

For every exam stream M registered (tasks/drive3_mri_for_archive_check.csv, 3,309 rows with their ACQ-IDs):
  * production's DICOM set: <ACQ>\\checksums.json read on J: (read-only), its digest by stream M's rule, and equal to the
    list's digest (made from the staged drive copy);
  * the archive's copy of the exam (tier C, extracted; out\\inventory_exams.csv and the extraction hashes);
  * per reconstruction (recon_states), production's DICOM against the archive's:
      identical / pixel-identical (same instances; the differing bytes carry equal pixel data and geometry: a re-export,
      A1 2.2's method, the differing tags listed in out/archive_check_pixel_detail.csv) / different (pixels, geometry or
      the instance set) / "DICOM not in the archive; 2dseq identical|differs" (the archive copy predates the DICOM
      export: its 2dseq, visu_pars and reco are compared with the drive copy stream M staged, out/stage_result.csv) /
      "reconstruction not in the archive" / "reconstruction's DICOM only in the archive"; for a Dicomifier exam:
      source-identical|source-different (the archive holds 2dseq only), or "scanner DICOM only in the archive
      (production: Dicomifier's)";
  * result per exam (the worst of its reconstructions): identical / pixel-identical / source-identical (Dicomifier
    exams) / missing on one side / different; or "not in the archive" (the study is not in it: 11.7 T, or a 7 T day the
    archive lacks; census);
  * for every exam: the ParaVision non-k-space files (junk aside) compared with the drive copy (source_shared_equal).
Also every exam of the 130 archive studies that stream M did NOT register (the other direction: "missing on the
production side"), with its class and what stream M decided for it.
Writes tasks/drive3_mri_archive_check.csv (the list with archive_result filled) and out\\archive_check_*.csv/.txt.
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ar_common as C  # noqa: E402

PIXEL_TAGS = ["Rows", "Columns", "NumberOfFrames", "PixelSpacing", "SliceThickness", "ImagePositionPatient",
              "ImageOrientationPatient", "BitsAllocated", "PixelRepresentation", "RescaleSlope", "RescaleIntercept"]

JUNK = {".ds_store", "thumbs.db", "folders.cache", "thumbs.cache", "desktop.ini"}
SOURCE = ("2dseq", "visu_pars", "reco")


def junk(k):
    b = k.split("/")[-1].lower()
    return b in JUNK or b.startswith("._")


def compare_recons(r, prod, src_drive, src_arch, arch_dir, pdir, acq, pixels, detail):
    """{recon idx: state} for one exam: production's DICOM per reconstruction against the archive's copy."""
    adcm = collections.defaultdict(dict)
    for k, v in src_arch.items():
        p = k.split("/")
        if len(p) == 4 and p[0] == "pdata" and p[2] == "dicom" and p[3].lower().endswith(".dcm"):
            adcm[p[1]][C.dcm_prod_name(p[1], p[3])] = (v, k)
    pr = collections.defaultdict(dict)
    for n, h in prod.items():
        pr[n.split("_")[0][5:]][n] = h
    states = {}
    for idx in sorted(set(pr) | set(adcm), key=lambda x: (0, int(x)) if x.isdigit() else (1, x)):
        P, A = pr.get(idx, {}), adcm.get(idx, {})
        src_keys = [f"pdata/{idx}/{f}" for f in SOURCE]
        src_same = all(src_drive.get(k) and src_drive.get(k) == src_arch.get(k) for k in src_keys)
        has_seq = f"pdata/{idx}/2dseq" in src_arch
        if P and A and r["dicom_origin"] == "dicomifier":
            states[idx] = "scanner DICOM only in the archive (production: Dicomifier's)" + (
                "; 2dseq identical" if src_same else "; 2dseq differs")
        elif P and A:
            if set(P) != set(A):
                states[idx] = (f"different instances: {len(set(A) - set(P))} only in the archive, "
                               f"{len(set(P) - set(A))} only in production")
                continue
            diff = sorted(n for n in P if P[n] != A[n][0])
            if not diff:
                states[idx] = "identical"
            elif not pixels:
                states[idx] = "bytes differ (pixels not compared)"
            else:
                bad, tags = [], collections.Counter()
                for n in diff:
                    ok, d = pixel_compare(os.path.join(arch_dir, r["exam"], *A[n][1].split("/")),
                                          os.path.join(pdir, f"{acq}.data", n))
                    tags.update(d["other_tags_differ"])
                    if not ok:
                        bad.append((n, d))
                detail.append({"original_name": r["original_name"], "acq_id": acq, "recon": idx,
                               "differing": len(diff), "bad": len(bad), "tags": dict(tags.most_common(12)),
                               "first_bad": str(bad[0]) if bad else ""})
                states[idx] = ("pixel-identical" if not bad else
                               f"different pixels/geometry in {len(bad)} of {len(diff)} re-exported instances")
        elif P:
            if r["dicom_origin"] == "dicomifier" and has_seq:
                states[idx] = "source-identical" if src_same else "source-different"
            elif has_seq:
                states[idx] = ("DICOM not in the archive" + ("; 2dseq identical" if src_same else "; 2dseq differs"))
            else:
                states[idx] = "reconstruction not in the archive"
        elif A:
            states[idx] = "reconstruction's DICOM only in the archive"
    return states


def summarize_exam(states, origin):
    v = set(states.values())
    detail = " | ".join(f"recon {k}: {s}" for k, s in states.items())
    if any(x.startswith("different") or x.endswith("differs") or x == "source-different" for x in v):
        return "different", detail
    if any("only in the archive" in x or "not in the archive" in x for x in v):
        return "missing on one side", detail
    if v == {"source-identical"}:
        return "source-identical", detail
    if v and v <= {"identical"}:
        return "identical", ""
    if v and v <= {"identical", "pixel-identical"}:
        return "pixel-identical", detail
    return "unclassified", detail


def prod_dir(nas, acq):
    d8 = acq.split("-")[1]
    return os.path.join(nas, "raw", "DICOM", d8[:4], f"{d8[:4]}-{d8[4:6]}", acq)


def pixel_compare(a_path, p_path):
    """(equal: bool, detail) for two DICOM files: pixel data and geometry; and the other tags that differ."""
    import pydicom
    a = pydicom.dcmread(C.lp(a_path))
    b = pydicom.dcmread(C.lp(p_path))
    geo = [t for t in PIXEL_TAGS if str(a.get(t, "")) != str(b.get(t, ""))]
    pa, pb = a.get("PixelData"), b.get("PixelData")
    pix = pa is not None and pa == pb
    if not pix and pa is not None and pb is not None:
        try:
            import numpy as np
            pix = np.array_equal(a.pixel_array, b.pixel_array)
        except Exception:  # noqa: BLE001
            pix = False
    other = sorted({el.keyword or str(el.tag) for el in a if el.tag != (0x7FE0, 0x0010)
                    and (el.tag not in b or b[el.tag].value != el.value)} |
                   {el.keyword or str(el.tag) for el in b if el.tag not in a})
    return pix and not geo, {"pixels_equal": pix, "geometry_differs": geo, "other_tags_differ": other[:12]}


def main():
    pixels = "--no-pixels" not in sys.argv
    nas = C.NAS
    lst = C.rows(os.path.join(C.WT, "tasks", "drive3_mri_for_archive_check.csv"))
    inv = {e["original_name"]: e for e in C.rows(os.path.join(C.OUT, "inventory_exams.csv")) if e["tier"] == "C"}
    inv_studies = {e["study"] for e in inv.values()}
    plan = C.pull_plan()
    tierc = {s for s, p in plan.items() if p["tier"] == "C"}
    d3 = {r["study"]: r for r in C.rows(os.path.join(C.CENSUS, "drive3_vs_archive_20261007.csv"))}
    done = C.extracted()
    # stream M: staged drive-copy hashes (every non-k-space file of each registered exam) and its per-exam plan
    stage = collections.defaultdict(dict)
    for r in C.rows(os.path.join(C.M_BASE, "out", "stage_result.csv")):
        parts = r["staged_rel"].split("\\")
        if len(parts) >= 4:
            stage[f"{parts[1]}/{parts[2]}"]["/".join(parts[3:])] = r["sha256"]
    mplan = {p["original_name"]: p for p in C.rows(os.path.join(C.M_BASE, "out", "plan_exams.csv"))}
    # archive files per exam (extraction hashes, k-space excluded)
    arch = collections.defaultdict(dict)
    for s in inv_studies:
        for m in C.members(s):
            parts = m["member"].split("/")
            if m["action"] == "extracted" and len(parts) >= 3 and parts[1][:1].isdigit():
                arch[f"{s}/{parts[1]}"]["/".join(parts[2:])] = m["sha256"]

    out, detail = [], []
    for r in lst:
        on, acq = r["original_name"], r["acq_id"]
        res = {**r}
        e = inv.get(on)
        pdir = prod_dir(nas, acq) if acq else ""
        prod = {}
        if acq:
            cj = json.load(open(os.path.join(pdir, "checksums.json"), encoding="utf-8"))["files"]
            prod = {k.replace("\\", "/").split("/")[-1]: v for k, v in cj.items()}
        res["prod_n_dicom"] = len(prod)
        res["prod_digest"] = C.dicom_set_digest(prod.items()) if prod else ""
        res["prod_digest_equals_list"] = "Y" if res["prod_digest"] == r["dicom_set_sha256"] else "N"
        # source files (non-k-space, junk aside) vs the drive copy stream M staged
        src_drive = {k: v for k, v in stage.get(on, {}).items() if not junk(k)}
        src_arch = {k: v for k, v in arch.get(on, {}).items() if not junk(k)}
        par_drive = {k: v for k, v in src_drive.items() if "/dicom/" not in f"/{k}"}
        par_arch = {k: v for k, v in src_arch.items() if "/dicom/" not in f"/{k}"}
        sdiff = sorted(k for k in set(par_drive) & set(par_arch) if par_drive[k] != par_arch[k])
        res["source_files_drive"], res["source_files_archive"] = len(par_drive), len(par_arch)
        res["source_only_drive"] = ";".join(sorted(set(par_drive) - set(par_arch))[:8])
        res["source_only_archive"] = ";".join(sorted(set(par_arch) - set(par_drive))[:8])
        res["source_differ"] = ";".join(sdiff[:8])
        res["source_shared_equal"] = ("Y" if par_arch and par_drive and not sdiff else "N" if par_arch else "")
        res["archive_class"] = e["class_detail"] if e else ""
        res["archive_n_dicom"] = e["n_dicom"] if e else ""
        res["archive_digest"] = e["dicom_set_sha256"] if e else ""
        why, recon_states = "", {}
        if r["study"] not in tierc:
            a = d3.get(r["study"], {})
            result = f"not in the archive ({a.get('why_absent') or 'census'})"
        elif r["study"] not in done:
            result = "pending (archive not extracted yet)"
        elif not e:
            trunc = (done[r["study"]].get("truncated") or {})
            result = "missing on one side"
            why = ("the exam is not in the archive's copy" +
                   (f" (the archive's tarball is short: it ends in exam {trunc.get('incomplete_exam')})" if trunc else ""))
        else:
            recon_states = compare_recons(r, prod, src_drive, src_arch, done[r["study"]]["dir"], pdir, acq, pixels, detail)
            result, why = summarize_exam(recon_states, r["dicom_origin"])
        res["archive_result"] = result
        res["archive_detail"] = why
        res["recon_states"] = " | ".join(f"{k}={v}" for k, v in recon_states.items())
        out.append(res)

    # the other direction: archive exams of the 130 studies that stream M did not register
    listed = {r["original_name"] for r in lst}
    other = []
    for on, e in sorted(inv.items()):
        if on in listed:
            continue
        mp = mplan.get(on)
        other.append({"original_name": on, "archive_class": e["class_detail"], "archive_n_dicom": e["n_dicom"],
                      "method": e["method"], "scan_name": e["scan_name"], "acq_datetime": e["acq_datetime"],
                      "stream_m": (f"{mp['disposition']} ({mp['class_detail']})" if mp else "not on the drive copy"),
                      "note": ("images production lacks" if e["class"] in ("c", "d") else "not an image (as stream M)")})
    path = os.path.join(C.WT, "tasks", "drive3_mri_archive_check.csv")
    C.write_csv(path, out)
    C.write_csv(C.out("archive_check_other_direction.csv"), other)
    C.write_csv(C.out("archive_check_pixel_detail.csv"), detail)
    by_res = collections.Counter(o["archive_result"] for o in out)
    st = collections.defaultdict(collections.Counter)
    for o in out:
        st[o["study"]][o["archive_result"]] += 1
    L = [f"stream M exams: {len(out)}; results: {dict(by_res.most_common())}",
         f"by origin: {dict(collections.Counter((o['dicom_origin'], o['archive_result']) for o in out))}",
         f"production digest == the list's digest (staged drive copy): "
         f"{dict(collections.Counter(o['prod_digest_equals_list'] for o in out if o['acq_id']))}",
         f"ParaVision source files shared with the drive copy all equal (archive studies): "
         f"{dict(collections.Counter(o['source_shared_equal'] for o in out if o['study'] in tierc))}",
         f"reconstruction states: {dict(collections.Counter(v.split('=', 1)[1] for o in out for v in o['recon_states'].split(' | ') if '=' in v).most_common())}",
         f"results by batch: {dict(sorted(collections.Counter((o['batch'], o['archive_result']) for o in out if o['study'] in tierc).items()))}",
         f"studies: {len(st)}; in the archive {sum(1 for s in st if s in tierc)}; all exams identical "
         f"{sum(1 for s, c in st.items() if set(c) == {'identical'})}",
         f"archive exams of these studies NOT registered by stream M: {len(other)}: "
         f"{dict(collections.Counter((o['note'], o['stream_m'][:40]) for o in other).most_common(8))}"]
    open(C.out("archive_check_summary.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
