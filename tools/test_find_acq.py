#!/usr/bin/env python3
"""test_find_acq.py — the registry Finder (find_acq join + filters + generate_index HTML).

Run:  PYTHONPATH=tools python tools/test_find_acq.py
"""
import csv
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import find_acq  # noqa: E402
import generate_index  # noqa: E402
from ingest import registry as reg  # noqa: E402

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok:   {msg}")


def _seed(d):
    regd = os.path.join(d, "registries")
    os.makedirs(regd)
    with open(os.path.join(regd, "registry_projects.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["project_id", "short_name", "description", "owner", "start_date",
                    "status", "last_activity", "folder_location", "notes"])
        w.writerow(["PROJ-0003", "ae-biomegune-0424", "AE biomaGUNE 0424 cardiac study",
                    "MBC", "", "active", "", "/projects/proj-ae-biomegune-0424/", ""])
    rows = [
        {"acq_id": "ACQ-20260219-ZWSI-001", "acquisition_datetime": "2026-02-19T00:00:00Z",
         "instrument": "ZWSI", "modalities_in_study": "WSI", "sample_id": "0424_ID29H",
         "subject_ids": "29-AE-biomaGUNE-0424", "sample_organism": "Mus musculus",
         "anatomical_entity": "heart", "researcher": "MBC", "operator": "MBC",
         "project_hint": "PROJ-0003", "sample_type": "tissue", "file_size_mb": "120",
         "canonical_path": "/raw/MICROSCOPY/2026/2026-02/ACQ-20260219-ZWSI-001/",
         "original_name": "MFB_MBC_0424_ID29H_WGA_10x.czi"},
        {"acq_id": "ACQ-20251016-MRI-018", "acquisition_datetime": "2025-10-16T08:00:00Z",
         "instrument": "MRI", "modalities_in_study": "MR", "sample_id": "m17_0424",
         "subject_ids": "17-AE-biomaGUNE-0424", "anatomical_entity": "heart",
         "researcher": "jrc", "project_hint": "PROJ-0003",
         "canonical_path": "/raw/DICOM/2025/2025-10/ACQ-20251016-MRI-018/",
         "original_name": "jrc_251016_m17_0424/18"},
        {"acq_id": "ACQ-20260101-CELL-001", "acquisition_datetime": "2026-01-01T00:00:00Z",
         "instrument": "CELL", "sample_id": "x", "project_hint": "PROJ-9999",
         "canonical_path": "/raw/MICROSCOPY/2026/2026-01/ACQ-20260101-CELL-001/"},
    ]
    with open(os.path.join(regd, "registry_raw.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=reg.REGISTRY_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in reg.REGISTRY_FIELDS})
    return d


def test_build_records():
    print("[build_records join]")
    with tempfile.TemporaryDirectory() as d:
        _seed(d)
        recs, pidx = find_acq.build_records(d)
        check(len(recs) == 3, "3 records built")
        z = next(r for r in recs if r["acq_id"] == "ACQ-20260219-ZWSI-001")
        check(z["_raw_path"] == "/raw/MICROSCOPY/2026/2026-02/ACQ-20260219-ZWSI-001/", "raw path carried")
        check(z["_project_folder"] == "/projects/proj-ae-biomegune-0424/", "project folder resolved")
        check(z["_project_owner"] == "MBC", "project owner resolved")
        check(z["_project_desc"] == "AE biomaGUNE 0424 cardiac study", "project description resolved")
        check("id29h" in z["_search"] and "heart" in z["_search"], "search blob lower-cased")
        c = next(r for r in recs if r["acq_id"] == "ACQ-20260101-CELL-001")
        check(c["_project_folder"] == "", "unresolved project -> empty folder")
        pay = generate_index._payload(recs, r"\\GJESUS3\gjesus3\gjesus3-data")
        pz = next(p for p in pay if p["acq"] == "ACQ-20260219-ZWSI-001")
        check(pz["sample_type"] == "tissue", "payload carries sample_type")
        check(pz["proj_short"] == "ae-biomegune-0424", "payload carries proj_short")
        check(pz["proj_owner"] == "MBC", "payload carries proj_owner")
        check(pz["proj_desc"] == "AE biomaGUNE 0424 cardiac study", "payload carries proj_desc")


def test_matches():
    print("[matches / CLI filters]")
    with tempfile.TemporaryDirectory() as d:
        _seed(d)
        recs, _ = find_acq.build_records(d)
        f = lambda **kw: {r["acq_id"] for r in recs if find_acq.matches(r, **kw)}
        check(f(query="m17") == {"ACQ-20251016-MRI-018"}, "free-text 'm17' -> the MRI acq")
        check(f(query="heart") == {"ACQ-20260219-ZWSI-001", "ACQ-20251016-MRI-018"}, "free-text 'heart' -> both")
        check(f(instrument="ZWSI") == {"ACQ-20260219-ZWSI-001"}, "instrument filter")
        check(f(anatomy="heart") == {"ACQ-20260219-ZWSI-001", "ACQ-20251016-MRI-018"}, "anatomy filter")
        check(f(subject="29") == {"ACQ-20260219-ZWSI-001"}, "subject filter (subject_ids/sample)")
        check(f(since="2026-01-01") == {"ACQ-20260219-ZWSI-001", "ACQ-20260101-CELL-001"}, "since filter")
        check(f(until="2025-12-31") == {"ACQ-20251016-MRI-018"}, "until filter")
        check(f(project="PROJ-0003") == {"ACQ-20260219-ZWSI-001", "ACQ-20251016-MRI-018"}, "project filter")


def test_winpath():
    print("[generate_index._winpath]")
    w = generate_index._winpath
    check(w(r"\\GJESUS3\gjesus3", "/raw/x/ACQ-1/") == r"\\GJESUS3\gjesus3\raw\x\ACQ-1", "UNC join + slash flip")
    check(w(r"\\GJESUS3\gjesus3", "") == "", "empty rel -> empty")


def test_render_html():
    print("[render_html self-contained]")
    with tempfile.TemporaryDirectory() as d:
        _seed(d)
        recs, _ = find_acq.build_records(d)
        html = generate_index.render_html(recs, r"\\GJESUS3\gjesus3", "T")
        check("ACQ-20260219-ZWSI-001" in html, "acq id embedded")
        check("const DATA =" in html, "data embedded inline")
        check("GJESUS3" in html and "MICROSCOPY" in html, "share path embedded")
        check("Sample type" in html, "new 'Sample type' column header present")
        check("Copy" in html, "detail copy button label present")
        check(html.count("</script>") == 1, "exactly one </script> (no data breakout)")


def test_generate_main_out():
    print("[generate_index.main --out + --per-project]")
    with tempfile.TemporaryDirectory() as d:
        _seed(d)
        out = os.path.join(d, "preview")
        generate_index.main(["--nas-root", d, "--per-project", "--out", out])
        check(os.path.isfile(os.path.join(out, "index.html")), "global index written")
        check(os.path.isfile(os.path.join(out, "PROJ-0003", "index.html")), "per-project index written")
        check(not os.path.isdir(os.path.join(out, "PROJ-9999")), "unresolved project skipped (no folder)")


def main():
    test_build_records()
    test_matches()
    test_winpath()
    test_render_html()
    test_generate_main_out()
    print()
    if FAILS:
        print(f"FAILED ({len(FAILS)}):")
        for m in FAILS:
            print(f"  - {m}")
        return 1
    print("ALL PASS (registry Finder: find_acq + generate_index)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
