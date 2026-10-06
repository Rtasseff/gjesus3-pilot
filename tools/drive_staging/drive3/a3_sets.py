"""A3 step 7 -- final trace per label, per-set and per-cohort traceability, DS-SEG session overlap (read-only).

Merges a3_labels.csv (route found by a3_trace.py) with a3_ncc_stacks.csv (cine stacks verified by pixels)
and a3_imgmatch.csv (beside-label NIfTI images matched by pixels), then:
  * per COPY: final trace_level in {acquisition, acquisition-stack, acquisition-group, session, none};
  * per DISTINCT label (SHA-256): the copies are the same bytes, so a trace found for one copy holds for all
    -- unless two copies were traced to different acquisitions (reported as 'conflict', never resolved here);
  * per SET and per COHORT (set x protocol x year): label counts, traceability rate against 12 §6.2
    ("every label traces to a valid RAW acquisition"), value schemes, reader hints, overlap with the
    promoted DS-SEG datasets and with drives 1+2 placements.
Traced = acquisition | acquisition-stack | acquisition-group. 'acquisition-group' (a flow ROI valid on the
magnitude cine AND the velocity map of the same slice) is reported separately as well.
Outputs: a3_labels_final.csv, a3_labels_distinct.csv, a3_sets.csv, a3_cohorts.csv, a3_dsseg_session_overlap.csv
"""
import glob
import os
import re
import sys
from collections import Counter, defaultdict

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a3_common as C  # noqa: E402

TRACED = ("acquisition", "acquisition-stack", "acquisition-stack-geometry", "acquisition-group")
RANK = {"acquisition": 3, "acquisition-stack": 3, "acquisition-stack-geometry": 2.5, "acquisition-group": 2,
        "session": 1, "none": 0}


def main():
    O = C.OUT_DIR
    labels = C.read_csv_dicts(os.path.join(O, "a3_labels.csv"))
    ncc = {(r["study"], r["dims"]): r for r in C.read_csv_dicts(os.path.join(O, "a3_ncc_stacks.csv"))}
    img = defaultdict(list)
    for r in C.read_csv_dicts(os.path.join(O, "a3_imgmatch.csv")):
        img[r["image_sha"]].append(r)
    over = {r["relpath"]: r for r in C.read_csv_dicts(os.path.join(O, "a3_overlap.csv"))}
    geo = {(r["study"], r["dims"]): r for r in C.read_csv_dicts(os.path.join(O, "a3_geostack.csv"))} \
        if os.path.exists(os.path.join(O, "a3_geostack.csv")) else {}
    acqs = {a["acq_id"]: a for a in C.read_csv_dicts(C.PROD_ACQS)}
    reg = {r["acq_id"]: r for r in C.read_csv_dicts(os.path.join(C.REG, "registry_raw.csv"))}
    projname = {p["project_id"]: p["name"] for p in C.read_csv_dicts(os.path.join(C.REG, "registry_projects.csv"))}

    # ---- per copy
    for r in labels:
        route, lvl, ids, ver = r["trace_route"], "none", r["acq_ids"], ""
        if route in ("dsseg-twin", "sha-source", "name-source", "subject-date", "nifti-exam"):
            lvl = "acquisition"
            ver = {"dsseg-twin": "byte-identical to a promoted DS-SEG label", "sha-source": "source DICOM SHA-256",
                   "name-source": "source DICOM original_name", "subject-date": "animal+protocol+date in path",
                   "nifti-exam": "dims+affine = exam conversion"}[route]
        elif route == "nifti-exam-group":
            lvl, ver = "acquisition-group", "dims+affine = conversions of N exams on one slice"
        elif route == "cine-split":
            d3 = "x".join(r["dims"].split("x")[:3])
            st = ncc.get((r["prod_study"], d3))
            if st and st["status"] == "direct-ncc":
                lvl, ids, ver = "acquisition-stack", st["stack_acq_ids"], "direct pixel NCC vs production DICOM (phases " + st["phases_checked"] + ")"
                if float(st.get("ncc_min") or 0) >= 0.9999:
                    ver += ", every slice pixel-identical to its production frame (NCC 1.0000, up to intensity scaling)"
            else:
                lvl, ids = "session", ""
                r["why_not"] = (r["why_not"] + "; " if r["why_not"] else "") + f"stack {st['status'] if st else 'not checked'}: {st['note'].strip() if st else ''}"
        elif route == "image-ncc-pending":
            res = [m for s in r["img_hit_shas"].split(";") if s for m in img.get(s, [])]
            ok = [m for m in res if m["status"] == "bit-identical" and m["exam_check"] == "match"]
            if res and len(ok) == len(res):
                studies = {acqs[m["best_acq"]]["original_name"].split("/")[0] for m in ok}
                found = sorted({m["best_acq"] for m in ok})
                if len(studies) == 1:
                    lvl = "acquisition" if len(found) == 1 else "acquisition-group"
                    ids, ver = ";".join(found), "beside-image bit-identical to production frame; exam number in name confirmed"
                    r["prod_study"] = next(iter(studies))
                else:
                    r["why_not"] = "beside images matched acquisitions of different studies"
            else:
                st_ = Counter(m["status"] for m in res)
                r["why_not"] = f"beside-image pixel match: {dict(st_) or 'no candidates'}"
        elif route == "session-only":
            lvl = "session"
            g = geo.get((r["prod_study"], "x".join(r["dims"].split("x")[:3])))
            if g and g["status"] == "geometry-stack" and "no split volume" in r["why_not"]:
                lvl, ids = "acquisition-stack-geometry", g["stack_acq_ids"]
                ver = "sidecar geometry: " + g["note"]
            elif g:
                r["why_not"] += f"; geometry check: {g['status']} ({g['note']})"
        r["final_level"], r["final_acq_ids"], r["verification"] = lvl, ids if lvl in TRACED else "", ver
        o = over.get(r["relpath"], {})
        r["overlap"] = o.get("match_sources", "")
        # production context of the traced acquisitions
        first = (r["final_acq_ids"].split(";") or [""])[0]
        a = acqs.get(first, {})
        g = reg.get(first, {})
        r["prod_project"] = a.get("project_id", "")
        r["prod_project_name"] = projname.get(a.get("project_id", ""), "")
        r["prod_session"] = a.get("session_id", "")
        r["prod_subject"] = g.get("subject_ids", "")
        r["prod_acq_datetime"] = a.get("acquisition_datetime", "")
    C.write_csv(os.path.join(O, "a3_labels_final.csv"), labels)

    # ---- per distinct label
    by_sha = defaultdict(list)
    for r in labels:
        by_sha[r["sha256"]].append(r)
    distinct = []
    for sha, cps in by_sha.items():
        traced = [c for c in cps if c["final_level"] in TRACED]
        acqsets = {c["final_acq_ids"] for c in traced}
        best = max(cps, key=lambda c: RANK[c["final_level"]])
        lvl = best["final_level"]
        note = ""
        if len(acqsets) > 1:
            # a stack traced from one copy and a single acquisition from another can both be right only if nested
            sets_ = [set(x.split(";")) for x in acqsets]
            if not all(s <= max(sets_, key=len) for s in sets_):
                lvl, note = "conflict", "copies traced to different acquisitions: " + " | ".join(sorted(acqsets))[:300]
        sets_id = Counter(c["set_id"] for c in cps).most_common()
        distinct.append({
            "sha256": sha, "set_id": sets_id[0][0], "set_ids_all": ";".join(s for s, _ in sets_id), "copies": len(cps),
            "size": cps[0]["size"], "fmt": cps[0]["fmt"], "dims": cps[0]["dims"], "spacing": cps[0]["spacing"],
            "values": cps[0]["values"], "kind": cps[0]["kind"], "final_level": lvl,
            "final_acq_ids": best["final_acq_ids"] if lvl in TRACED else "", "verification": best["verification"],
            "trace_from_copy": best["relpath"] if lvl in TRACED else "", "prod_study": best["prod_study"],
            "prod_project": best["prod_project"], "prod_project_name": best["prod_project_name"],
            "prod_session": best["prod_session"], "prod_subject": best["prod_subject"],
            "prod_acq_datetime": best["prod_acq_datetime"], "phase": best["phase"],
            "studies_named": ";".join(sorted({s for c in cps for s in c["studies"].split(";") if s}))[:300],
            "reader_hints": ";".join(sorted({h for c in cps for h in c["reader_hints"].split(";") if h})),
            "overlap": ";".join(sorted({s for c in cps for s in c["overlap"].split(";") if s})),
            "earliest_mtime": min(c["mtime"] for c in cps), "earliest_birthtime": min(c["birthtime"] for c in cps),
            "why_not": "" if lvl in TRACED else (best["why_not"] or cps[0]["why_not"]), "note": note,
            "example_relpath": cps[0]["relpath"], "all_relpaths": " | ".join(c["relpath"] for c in cps)[:2000],
        })
    C.write_csv(os.path.join(O, "a3_labels_distinct.csv"), distinct)

    # ---- per set
    def summarise(rows, copies):
        n = len(rows)
        lv = Counter(r["final_level"] for r in rows)
        tr = sum(lv[k] for k in TRACED)
        return {"distinct_labels": n, "copies": copies,
                "traced": tr, "traced_single_or_stack": lv["acquisition"] + lv["acquisition-stack"],
                "traced_stack_geometry_only": lv["acquisition-stack-geometry"],
                "traced_group": lv["acquisition-group"], "session_only": lv["session"], "none": lv["none"],
                "conflict": lv["conflict"], "rate": f"{tr / n:.1%}" if n else "",
                "label_empty": sum(1 for r in rows if r["kind"] == "label_empty"),
                "schemes": "; ".join(f"{k}:{v}" for k, v in Counter("{" + r["values"].replace(";", ",") + "}" if r["values"] else r["fmt"] for r in rows).most_common(5)),
                "readers": "; ".join(f"{k}:{v}" for k, v in Counter(h for r in rows for h in (r["reader_hints"].split(";") if r["reader_hints"] else ["(none)"])).most_common(6)),
                "in_dsseg": sum(1 for r in rows if "DS-SEG" in r["overlap"]),
                "in_drives12_projects": sum(1 for r in rows if "drives12_placed" in r["overlap"]),
                "in_drives12_holding": sum(1 for r in rows if "drives12_held" in r["overlap"]),
                "bytes_distinct": sum(int(r["size"]) for r in rows),
                "projects_traced": "; ".join(f"{k}:{v}" for k, v in Counter(r["prod_project_name"] for r in rows if r["final_level"] in TRACED).most_common(8)),
                "years": "; ".join(f"{k}:{v}" for k, v in sorted(Counter(year_of(r) for r in rows).items()))}

    sets = []
    cps_by_set = Counter(r["set_id"] for r in labels)
    desc = {r["set_id"]: r["set_desc"] for r in labels}
    for s in sorted({d["set_id"] for d in distinct}):
        rows = [d for d in distinct if d["set_id"] == s]
        sets.append({"set_id": s, "description": desc.get(s, ""), **summarise(rows, cps_by_set[s])})
    allrows = summarise(distinct, len(labels))
    sets.append({"set_id": "ALL", "description": "every label on the drive", **allrows})
    C.write_csv(os.path.join(O, "a3_sets.csv"), sets)

    # ---- per cohort (set x protocol x year)
    coh = defaultdict(list)
    for d in distinct:
        coh[(d["set_id"], protocol_of(d), year_of(d))].append(d)
    crow = []
    for (s, p, y), rows in sorted(coh.items()):
        crow.append({"set_id": s, "protocol": p, "year": y, **summarise(rows, sum(r["copies"] for r in rows)),
                     "sessions": len({r["prod_session"] or r["studies_named"] for r in rows})})
    C.write_csv(os.path.join(O, "a3_cohorts.csv"), crow)

    # ---- overlap with the sessions of the promoted datasets
    ds_sessions = defaultdict(set)
    for d in sorted(glob.glob(os.path.join(C.CDS, "segmentation", "*", "DS-SEG-*"))):
        for r in C.read_csv_dicts(os.path.join(d, "provenance.csv")):
            for a in (r.get("acq_ids_all") or r.get("acq_id") or "").split(";"):
                if a:
                    ds_sessions[acqs.get(a, {}).get("session_id", "")].add(os.path.basename(d))
    ov = []
    for d in distinct:
        if d["final_level"] in TRACED and d["prod_session"] in ds_sessions:
            ov.append({"sha256": d["sha256"], "prod_session": d["prod_session"], "datasets": ";".join(sorted(ds_sessions[d["prod_session"]])),
                       "byte_identical_to_dsseg": "Y" if "DS-SEG" in d["overlap"] else "N", "values": d["values"],
                       "reader_hints": d["reader_hints"], "phase": d["phase"], "example_relpath": d["example_relpath"]})
    C.write_csv(os.path.join(O, "a3_dsseg_session_overlap.csv"), ov)
    for s in sets:
        print(f"{s['set_id']:24s} distinct {s['distinct_labels']:5d} copies {s['copies']:5d} traced {s['traced']:5d} "
              f"({s['rate']}) group {s['traced_group']:4d} session {s['session_only']:4d} none {s['none']:5d} conflict {s['conflict']}")
    print("DS-SEG session overlap rows:", len(ov), Counter((o["datasets"], o["byte_identical_to_dsseg"]) for o in ov))


def year_of(d):
    if d.get("prod_acq_datetime"):
        return d["prod_acq_datetime"][:4]
    m = re.search(r"(?<!\d)(20[12]\d)(\d{2})(\d{2})_\d{6}_", d.get("studies_named", ""))
    if m:
        return m.group(1)
    m = re.search(r"jrc_?(\d{2})\d{4}_", d.get("studies_named", "") + " " + d.get("example_relpath", ""))
    if m:
        return "20" + m.group(1)
    return "unknown"


def protocol_of(d):
    if d.get("prod_project_name"):
        return d["prod_project_name"].replace("AE-biomaGUNE-", "")
    rel = d.get("example_relpath", "")
    m = re.search(r"(?i)proyecto[\s_-]*(\d{4})", rel)
    if m:
        return m.group(1)
    m = re.search(r"jrc_?\d{6}_[mr]\d+[a-z]?_(\d{4})", rel)
    return m.group(1) if m else "unknown"


if __name__ == "__main__":
    main()
