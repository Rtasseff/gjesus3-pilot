"""A1 step 2c: match every drive exam to production three ways, and class it (a)-(e).

Three independent matches, each reported, disagreements listed:
  name     registry original_name == "<study>/<exam>" (or X1's "<study>__<exam>"), instrument MRI/XMRI
  session  registry session_id == the study name's jrc id (production regexes) AND the same exam no.
  bytes    the SHA-256 of the drive exam's pdata\\<n>\\dicom\\MRIm<NN>.dcm (any copy) is in a
           production checksums.json (prod_raw_sha256.csv)
Retired acquisitions (retired_acquisitions.csv tombstones) are matched by name too, and reported.

How production's files relate to the drive's (established here, on every name-matched exam, and
spot-checked byte by byte in a1_23_dicom_relation.py): the ingest (tools/ingest_raw.py,
copy_strategy mri_paravision_v2) copies pdata/<idx>/dicom/MRIm<NN>.dcm VERBATIM to
<ACQ-ID>.data/recon<idx>_frame<NN>.dcm (NN zero-padded to 2), so a native exported DICOM is
byte-identical under the new name. Dicomifier-regenerated DICOM (pending_dicom_regen.csv
status 'regenerated') cannot match any drive file.

Class of each exam key (canonical copy; DICOM presence over all copies):
  (a)  in production; every drive DICOM byte-identical to a file of that acquisition under the
       mapped name. a1 = identical sets; a2 = the drive copy holds a subset of production's files
  (b)  in production, not byte-identical. Reason: b-regen (production DICOM is Dicomifier output),
       b-recon (the drive has reconstructions production lacks, or vice versa, others identical),
       b-export (same names, different bytes: a different export), b-nodicom-drive (the drive copy
       has no DICOM; production has), b-empty-prod (production row holds no file)
  (c)  not in production; native DICOM on the drive
  (d)  not in production; no DICOM; a pdata/<n>/2dseq exists and the method is an image method:
       convertible with tools/drive_staging/convert_staged_exams.py (Ryan, 2026-10-04)
  (e)  not in production; not convertible: e-nonimage (STEAM/PRESS/WOBBLE), e-norecon (k-space
       but no 2dseq), e-neveracquired (neither k-space nor 2dseq: a set-up scan never run)
  (f)  not an exam: reported per study-named folder in a1_25 (Splits, NIfTI, segmentations)

Writes (a1\\): mri_exams.csv (one row per exam key), mri_studies.csv (one row per study name),
mri_disagreements.csv, mri_match_summary.txt.

    python a1_22_mri_match.py
"""
import collections
import csv
import io
import os
import re

from a1_common import (cache_load, cache_save, gb, load_prod_index, out_path, parse_study, snapshot,
                       write_csv, read_csv_dicts, PROD_SHA)

CODE_IN_SEG = re.compile(r"(?<!\d)(\d{4})(?!\d)")


def path_claims(study_dir):
    """Protocol codes claimed by the folders ABOVE the study folder: (nearest-claim codes, all)."""
    segs = study_dir.split("\\")[:-1]
    nearest, allc = [], []
    for seg in reversed(segs):
        low = seg.lower()
        codes = [c for c in CODE_IN_SEG.findall(seg) if not c.startswith(("19", "20"))]
        if not codes:
            continue
        if "proyecto" in low or "project" in low or re.fullmatch(r"\d{4}", seg.strip()) \
                or re.search(r"[_ -](\d{4})[_ -]", f"_{seg}_"):
            allc.extend(codes)
            if not nearest:
                nearest = codes
    return nearest, sorted(set(allc))


def main():
    copies = cache_load("mri_copies")
    keys = cache_load("mri_keys")
    hdr = cache_load("mri_headers")
    subj = cache_load("mri_subjects")
    prod = load_prod_index()
    reg = read_csv_dicts(snapshot("registry_raw.csv"))
    regby = {r["acq_id"]: r for r in reg}
    regen = {r["acq_id"]: r for r in read_csv_dicts(snapshot("pending_dicom_regen.csv"))}
    projects = {r["project_id"]: r for r in read_csv_dicts(snapshot("registry_projects.csv"))}
    proj_by_name = {r["name"]: r for r in projects.values()}
    # production files per acquisition (basename -> sha256)
    acq_files = collections.defaultdict(dict)
    with open(PROD_SHA, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            acq_files[r["acq_id"]][r["relpath"].rsplit("/", 1)[-1]] = r["sha256"]
    # name and session indexes over MRI/XMRI rows
    by_name, by_sess = collections.defaultdict(list), collections.defaultdict(list)
    prod_study_names = set()
    for r in reg:
        if r["instrument"] not in ("MRI", "XMRI"):
            continue
        on = r["original_name"]
        if "/" in on:
            st, exn = on.rsplit("/", 1)
        elif "__" in on:
            st, exn = on.rsplit("__", 1)
        else:
            continue
        prod_study_names.add(st)
        by_name[(st, exn)].append(r["acq_id"])
        if r["session_id"]:
            by_sess[(r["session_id"], exn)].append(r["acq_id"])
    # retired tombstones (the registry row is kept as CSV text)
    retired_by_name = collections.defaultdict(list)
    regcols = list(reg[0].keys())
    for t in read_csv_dicts(snapshot("retired_acquisitions.csv")):
        try:
            row = next(csv.reader(io.StringIO(t["registry_raw_row"])))
            rr = dict(zip(regcols, row))
        except Exception:  # noqa: BLE001
            continue
        on = rr.get("original_name", "")
        if rr.get("instrument") in ("MRI", "XMRI") and ("/" in on or "__" in on):
            st, exn = on.rsplit("/", 1) if "/" in on else on.rsplit("__", 1)
            retired_by_name[(st, exn)].append(f"{t['acq_id']}({t['disposition']})")

    exam_rows, disagreements = [], []
    for key, eds in sorted(keys.items()):
        cs = [copies[e] for e in eds]
        can = next(c for c in cs if c["canonical"])
        h = hdr.get(can["exam_dir"], {})
        study, exn = can["study"], can["exam"]
        ps = parse_study(study)
        # --- the three matches
        m_name = sorted(set(by_name.get((study, exn), [])))
        m_sess = sorted(set(by_sess.get((ps["jrc_id"], exn), []))) if ps["jrc_id"] else []
        union_dcm = {}
        for c in cs:
            for n, s in c["dcm"].items():
                union_dcm.setdefault(n, set()).add(s)
        byte_hits = collections.Counter()
        for n, ss in union_dcm.items():
            for s in ss:
                if s in prod:
                    byte_hits[prod[s][0]] += 1
        m_bytes = sorted(byte_hits)
        m_retired = retired_by_name.get((study, exn), [])
        acqs = m_name or m_sess or m_bytes
        how = "name" if m_name else ("session" if m_sess else ("bytes" if m_bytes else ""))
        dis = []
        if m_name and m_sess and set(m_name) != set(m_sess):
            dis.append(f"name {m_name} vs session {m_sess}")
        if m_name and m_bytes and not set(m_bytes) <= set(m_name):
            dis.append(f"name {m_name} vs bytes {m_bytes}")
        if not m_name and m_sess:
            dis.append(f"session match only (study folder named differently in production): {m_sess}")
        if not m_name and not m_sess and m_bytes:
            dis.append(f"bytes match only: {m_bytes}")
        if len(acqs) > 1:
            dis.append(f"several production acquisitions: {acqs}")
        # --- comparison with the production acquisition
        any_dcm = any(c["dcm"] for c in cs)
        cmp_ = {"prod_files": "", "same": "", "differ": "", "prod_only": "", "drive_only": ""}
        cls, why = "", ""
        if acqs:
            a = acqs[0]
            pf = acq_files.get(a, {})
            dd = can["dcm"] if can["dcm"] else next((c["dcm"] for c in cs if c["dcm"]), {})
            same = sum(1 for n, s in dd.items() if pf.get(n) == s)
            differ = sum(1 for n, s in dd.items() if n in pf and pf[n] != s)
            prod_only = sum(1 for n in pf if n not in dd)
            drive_only = sum(1 for n in dd if n not in pf)
            cmp_ = {"prod_files": len(pf), "same": same, "differ": differ, "prod_only": prod_only,
                    "drive_only": drive_only}
            rg = regen.get(a, {})
            if not pf:
                cls, why = "b", "b-empty-prod"
                if rg:
                    why += f" (pending_dicom_regen: {rg.get('status')}{', ' + rg['nonimage_marker'] if rg.get('nonimage_marker') else ''})"
            elif not dd:
                cls, why = "b", "b-nodicom-drive"
                if rg.get("status") == "regenerated":
                    why += " (production DICOM regenerated by Dicomifier)"
            elif differ == 0 and drive_only == 0 and prod_only == 0:
                cls, why = "a", "a1-identical"
            elif differ == 0 and drive_only == 0:
                cls, why = "a", "a2-drive-subset"
            elif rg.get("status") == "regenerated":
                cls, why = "b", "b-regen (production DICOM regenerated by Dicomifier; the drive has native DICOM)"
            elif differ == 0:
                cls, why = "b", "b-recon (the drive has reconstructions production lacks)"
            elif same == 0:
                cls, why = "b", "b-export (same names, different bytes)"
            else:
                cls, why = "b", "b-mixed (some identical, some different)"
        else:
            seq = any(c["seq"] for c in cs)
            ksp = any(c["kspace"] for c in cs)
            if any_dcm:
                cls, why = "c", "c-native-dicom"
                if not all(set(c["seq"]) <= {n.split("_")[0][5:] for n in c["dcm"]} for c in cs if c["dcm"]):
                    why += " (some reconstructions without DICOM)"
            elif h.get("nonimage_marker"):
                cls, why = "e", f"e-nonimage ({h['nonimage_marker']})"
            elif seq:
                cls, why = "d", "d-convertible (2dseq, image method)"
            elif ksp:
                cls, why = "e", "e-norecon (k-space, no 2dseq)"
            else:
                cls, why = "e", "e-neveracquired (no k-space, no 2dseq)"
        near, allc = path_claims(can["study_dir"])
        sj = subj.get(can["study_dir"], {})
        prow = regby.get(acqs[0], {}) if acqs else {}
        row = {
            "exam_key": key, "study": study, "exam": exn, "class": cls, "class_detail": why,
            "match_how": how, "acq_ids": ";".join(acqs), "name_match": ";".join(m_name),
            "session_match": ";".join(m_sess), "bytes_match": ";".join(f"{a}:{byte_hits[a]}" for a in m_bytes),
            "retired_match": ";".join(m_retired), "prod_project": prow.get("project_id", ""),
            "prod_config": prow.get("ingest_config", ""),
            "prod_files": cmp_["prod_files"], "dcm_same": cmp_["same"], "dcm_differ": cmp_["differ"],
            "prod_only": cmp_["prod_only"], "drive_only": cmp_["drive_only"],
            "n_copies": len(cs), "copies_vs_canonical": ";".join(sorted({c["vs_canonical"] for c in cs if not c["canonical"]})),
            "tops": ";".join(sorted({c["top"] for c in cs})), "canonical_dir": can["exam_dir"],
            "n_dcm": len(can["dcm"]), "any_copy_dcm": "Y" if any_dcm else "N",
            "dcm_recons": ";".join(sorted({n.split("_")[0][5:] for n in can["dcm"]}, key=lambda x: int(x) if x.isdigit() else 0)),
            "seq_recons": ";".join(sorted(can["seq"], key=lambda x: int(x) if x.isdigit() else 0)),
            "kspace": "Y" if can["kspace"] else "N", "bytes": can["bytes"], "dcm_bytes": can["dcm_bytes"],
            "kspace_bytes": can["kspace_bytes"],
            "distinct_bytes_all_copies": 0,
            "scan_name": h.get("ACQ_scan_name", ""), "method": h.get("Method", ""), "pulprog": h.get("PULPROG", ""),
            "acq_time": h.get("ACQ_time", ""), "station": h.get("ACQ_station", ""), "pv": h.get("ACQ_sw_version", ""),
            "nonimage_marker": h.get("nonimage_marker", ""),
            "subject_id": sj.get("SUBJECT_id", ""), "subject_study_name": sj.get("SUBJECT_study_name", ""),
            "study_date": ps["study_date"], "year": ps["study_date"][:4], "initials": ps["initials"],
            "regex_parse": ps["parse"], "jrc_id": ps["jrc_id"], "code_by_regex": ps["code_by_regex"],
            "animal_by_regex": ps["animal_by_regex"], "path_claim_nearest": ";".join(near),
            "path_claim_all": ";".join(allc), "disagreement": " | ".join(dis),
        }
        exam_rows.append(row)
        if dis:
            disagreements.append({"exam_key": key, "class": cls, "detail": " | ".join(dis),
                                  "name_match": row["name_match"], "session_match": row["session_match"],
                                  "bytes_match": row["bytes_match"], "canonical_dir": can["exam_dir"]})
    # distinct bytes per exam over all copies (SHA-256 dedup), from the files table
    df = cache_load("files")
    sizes = dict(zip(df["sha256"], df["size"]))
    for row in exam_rows:
        shas = set()
        for e in keys[row["exam_key"]]:
            shas.update(copies[e]["inner"].values())
        row["distinct_bytes_all_copies"] = sum(sizes[s] for s in shas)
    cache_save("mri_exam_rows", exam_rows)
    write_csv("mri_exams.csv", exam_rows, list(exam_rows[0].keys()))
    write_csv("mri_disagreements.csv", disagreements,
              ["exam_key", "class", "detail", "name_match", "session_match", "bytes_match", "canonical_dir"])

    # ---- per study
    st_rows = []
    by_study = collections.defaultdict(list)
    for r in exam_rows:
        by_study[r["study"]].append(r)
    study_dirs = collections.defaultdict(set)
    for c in copies.values():
        study_dirs[c["study"]].add(c["study_dir"])
    for st, rs in sorted(by_study.items()):
        cc = collections.Counter(r["class"] for r in rs)
        cd = collections.Counter(r["class_detail"].split(" (")[0] for r in rs)
        r0 = rs[0]
        st_rows.append({
            "study": st, "exams": len(rs), "a": cc["a"], "b": cc["b"], "c": cc["c"], "d": cc["d"], "e": cc["e"],
            "detail": "; ".join(f"{k} {v}" for k, v in sorted(cd.items())),
            "in_production_by_name": "Y" if st in prod_study_names else "N",
            "any_exam_in_production": "Y" if (cc["a"] + cc["b"]) else "N",
            "copies": len(study_dirs[st]), "locations": " | ".join(sorted(study_dirs[st])),
            "year": r0["year"], "study_date": r0["study_date"], "initials": r0["initials"],
            "regex_parse": r0["regex_parse"], "jrc_id": r0["jrc_id"], "code_by_regex": r0["code_by_regex"],
            "animal_by_regex": r0["animal_by_regex"], "subject_id": r0["subject_id"],
            "path_claim_nearest": r0["path_claim_nearest"], "path_claim_all": r0["path_claim_all"],
            "prod_projects": ";".join(sorted({r["prod_project"] for r in rs if r["prod_project"]})),
            "distinct_bytes": sum(r["distinct_bytes_all_copies"] for r in rs),
            "new_exam_bytes": sum(r["distinct_bytes_all_copies"] for r in rs if r["class"] in ("c", "d", "e")),
            "dcm_bytes_new": sum(r["dcm_bytes"] for r in rs if r["class"] == "c"),
        })
    write_csv("mri_studies.csv", st_rows, list(st_rows[0].keys()))
    cache_save("mri_study_rows", st_rows)

    # ---- summary
    L = []
    cc = collections.Counter(r["class"] for r in exam_rows)
    cd = collections.Counter(r["class_detail"].split(" (")[0] for r in exam_rows)
    L.append(f"exam keys: {len(exam_rows):,}   study names: {len(st_rows)}")
    L.append("classes: " + ", ".join(f"{k} {cc[k]:,}" for k in "abcde"))
    for k, v in sorted(cd.items()):
        L.append(f"   {k:40s} {v:6,d}")
    L.append("match how: " + str(collections.Counter(r["match_how"] for r in exam_rows)))
    L.append(f"disagreements: {len(disagreements)}")
    L.append(f"studies with any exam in production: {sum(1 for s in st_rows if s['any_exam_in_production']=='Y')}; "
             f"none: {sum(1 for s in st_rows if s['any_exam_in_production']=='N')}")
    L.append(f"studies whose NAME is in production (hub method, today): {sum(1 for s in st_rows if s['in_production_by_name']=='Y')}")
    txt = "\n".join(L)
    with open(out_path("mri_match_summary.txt"), "w", encoding="utf-8") as f:
        f.write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
