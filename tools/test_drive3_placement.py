#!/usr/bin/env python3
"""test_drive3_placement.py -- stream P, the M. Jesus drive's non-raw placement
(tools/drive_staging/drive3/p_plan.py and p_verify.py), pinned to the coordinator's calls of 2026-10-06:

  C1 1121 reopened -> place;  C2 0118 under AE-biomaGUNE-0118, Monocrotalina placed, the rest HELD (M1);
  C3 1521/0618 closed -> HELD;  C4 A2 D5 also placed in drive 3's project;  C5 model outputs -> holding;
  P1 an archive is expanded;  then A2's content-level step and "one study folder per content" dedup.
  `release` re-plans held rows; `handover` is a second batch that lands in batch 1's folders;
  `p_verify` proves a window kept every earlier index row and added the new ones once.

Run:  python tools/test_drive3_placement.py
"""
import csv
import hashlib
import io
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "drive_staging", "drive3"))
sys.path.insert(0, os.path.join(HERE, "drive_staging"))
sys.path.insert(0, HERE)
import p_plan as P  # noqa: E402
import p_verify as V  # noqa: E402
import nonraw_placement as N  # noqa: E402
import historical_paths as H  # noqa: E402

FAILS = []


def check(cond, msg):
    print(f"  {'ok:  ' if cond else 'FAIL:'} {msg}")
    if not cond:
        FAILS.append(msg)


def _sha(b):
    return hashlib.sha256(b).hexdigest()


PROJECTS = {n: {"project_id": f"PROJ-{i:04d}", "name": n, "status": s, "folder_location": f"/projects/{n}/"}
            for i, (n, s) in enumerate([("AE-biomaGUNE-0118", "active"), ("AE-biomaGUNE-0619", "active"),
                                        ("AE-biomaGUNE-1121", "active"), ("AE-biomaGUNE-1521", "closed"),
                                        ("AE-biomaGUNE-0424", "active")], 1)}


def a2(relpath, dec, proj="", root="", sha=None, cls="document", verdict="CONFIRMED", placed12="", reading=""):
    return {"relpath": relpath, "top": relpath.split("\\")[0], "size": "5", "sha256": sha or _sha(relpath.encode()),
            "cls": cls, "claim_id": "CL-1", "verdict": verdict, "reading": reading, "dec_rec": dec,
            "rec_project": proj, "dest": "", "root_rec": root, "placed12": placed12}


def test_rules():
    print("the calls, one by one")
    mo = P.model_output
    check(mo(r"MRI\Proyecto 1019\P1\S\Splits\Predict_Slicer\Time_11_m9_1019_Cardiac_Segmentation.mha").startswith("C5"),
          "Predict_Slicer -> model output")
    for n in ("Pred_time_8_rat_x.mhd", "Postprocessed_time_8_rat_x.raw", "Modificated_Postprocessed_time_1_rat_x.mhd"):
        check(mo(P.RAT_2DG + "20190911_124202_jrc190911_r121_2DG_1_1\\8\\" + n).startswith("C5"), f"2DG RATAS {n.split('_')[0]}_ -> model output")
    check(mo(P.RAT_2DG + "20190911_124202_jrc190911_r121_2DG_1_1\\8\\Time_8_rat_x.mhd") == "",
          "a 2DG RATAS split volume (the input image) is not a model output")
    check(mo(r"Otros\PH_analysis_Segmentation_tool\PH_segmentation_tool\Seg_models\M.h5") == "",
          "the tool itself is D8, not C5")
    pre = {"place": "candidate", "place-after-reopen": "candidate", "closed-project": "candidate",
           "covered-by-twin": "unattributed", "holding": "unattributed", "already-placed": "already-placed",
           "placed-elsewhere": "placed-elsewhere", "deferred-biomaGUNE-MJ": "deferred-biomaGUNE-MJ"}
    check(all(P.a2_pre(a2("x\\y", d, "P" if d != "holding" else "")) == v for d, v in pre.items()), "a2_pre")
    check(P.a2_pre(a2("x\\y", "duplicate-copy", "P")) == "candidate" and P.a2_pre(a2("x\\y", "duplicate-copy")) == "unattributed",
          "a duplicate-copy was a candidate when it had a project, else unattributed")
    t = P.target("Proyecto-0118-Monocrotalina", P.MONO_PREFIX + "MRI 2DG ratas\\x.xlsx", PROJECTS)
    check(t[:3] == ("AE-biomaGUNE-0118", "place", ""), f"C2: Monocrotalina documents placed now in AE-biomaGUNE-0118 {t[:3]}")
    t = P.target("Proyecto-0118-rats-hipoxia", "MRI\\Proyecto 0118 (Ratas hipoxia)\\x.mhd", PROJECTS)
    check(t[:3] == ("AE-biomaGUNE-0118", "held", "M1-0118"), f"C2: the rest of 0118 is held on M1 {t[:3]}")
    t = P.target("Proyecto-0118-Monocrotalina", "Otros\\x.docx", PROJECTS)
    check(t[1] == "held", "C2: only the Monocrotalina folder itself is placed now")
    check(P.target("AE-biomaGUNE-1521", "x", PROJECTS)[1:3] == ("held", "reopen-AE-biomaGUNE-1521"), "C3: closed -> held")
    check(P.target("AE-biomaGUNE-0619", "x", PROJECTS)[1] == "place", "active -> place")
    try:
        P.target("AE-biomaGUNE-9999", "x", PROJECTS)
        check(False, "an unknown project must stop the run")
    except SystemExit:
        check(True, "an unknown project stops the run")


def test_decide():
    print("decide: A2's plan + the calls, then A2's content-level step and dedup re-run")
    twin = _sha(b"twin")
    dup = _sha(b"dup")
    same = _sha(b"same folder")
    held_sha = _sha(b"hold")
    model = _sha(b"model")
    rows = [
        a2("Pili y Mili\\Proyecto 1121 London\\a.docx", "place-after-reopen", "AE-biomaGUNE-1121", "pili y mili|proyecto 1121 london"),
        a2(P.MONO_PREFIX + "MRI 2DG ratas\\m.xlsx", "place", "Proyecto-0118-Monocrotalina", "pili y mili|proyecto 0118 monocrotalina"),
        a2("MRI\\Proyecto 0118 (Ratas hipoxia)\\Splits\\s.mhd", "place", "Proyecto-0118-rats-hipoxia", "mri|proyecto 0118 (ratas hipoxia)", sha=held_sha),
        a2("Pili y Mili\\Proyecto 1521 Fumadores\\2a\\d.xlsx", "closed-project", "AE-biomaGUNE-1521", "pili y mili|proyecto 1521 fumadores"),
        a2("Pili y Mili\\Proyecto 1121 London\\Info\\ceea.pdf", "placed-elsewhere", "AE-biomaGUNE-1121", "", placed12="AE-biomaGUNE-1019"),
        a2("MRI\\Proyecto 0619\\S\\Splits\\Predict_Slicer\\T_1.mha", "place", "AE-biomaGUNE-0619", "mri|proyecto 0619", sha=model, cls="volume"),
        a2("PET\\loose\\copy_of_model.mha", "covered-by-twin", "", "", sha=model, verdict="NO-CLAIM"),
        a2("Pili y Mili\\Proyecto 0619 Ratones PAH\\fig.png", "place", "AE-biomaGUNE-0619", "pili y mili|proyecto 0619 ratones pah", sha=twin),
        a2("PET\\nocode\\fig_copy.png", "covered-by-twin", "", "", sha=twin, verdict="NO-CLAIM"),
        a2("Otros\\nocode\\alone.docx", "holding", "", "", verdict="NO-CLAIM"),
        a2("Pili y Mili\\Proyecto 0619 Ratones PAH\\x\\d.xlsx", "place", "AE-biomaGUNE-0619", "pili y mili|proyecto 0619 ratones pah", sha=dup),
        a2("MRI\\Proyecto 0619\\y\\d.xlsx", "duplicate-copy", "AE-biomaGUNE-0619", "mri|proyecto 0619", sha=dup),
        a2("Pili y Mili\\Proyecto 0619 Ratones PAH\\p\\s.tif", "place", "AE-biomaGUNE-0619", "pili y mili|proyecto 0619 ratones pah", sha=same),
        a2("Pili y Mili\\Proyecto 0619 Ratones PAH\\q\\s.tif", "place", "AE-biomaGUNE-0619", "pili y mili|proyecto 0619 ratones pah", sha=same),
        a2("Otros\\h1\\t.pdf", "holding", "", "", sha=_sha(b"h"), verdict="C"),
        a2("Otros\\h2\\t.pdf", "holding", "", "", sha=_sha(b"h"), verdict="C"),
        a2(P.D8_PREFIX + "PH_segmentation_tool\\M.h5", "holding", "", "", verdict="NO-CLAIM", cls="analysis"),
        a2("biomaGUNE MJ\\x\\Predict_Slicer\\T.mha", "deferred-biomaGUNE-MJ", "AE-biomaGUNE-0619", "", cls="volume"),
        a2("Pili y Mili\\z.txt", "exclude-zero-byte"),
        a2(P.MONO_PREFIX + "old.xlsx", "already-placed", "Proyecto-0118-Monocrotalina", "", placed12="AE-biomaGUNE-0118"),
        a2("Pili y Mili\\Proyecto 0424 Envejecimiento y PAH\\OH\\r.zip", "place", "AE-biomaGUNE-0424",
           "pili y mili|proyecto 0424 envejecimiento y pah", cls="archive"),
    ]
    zm = {rows[-1]["relpath"]: [("a.docx", 3, _sha(b"aaa")), ("b.docx", 4, _sha(b"bbbb"))]}
    work = P.decide(rows, PROJECTS, lambda rel, proj: "pili y mili|proyecto 1121 london", zm)
    by = {(w["relpath"], w["member"]): w for w in work}

    def dec(rel, mem=""):
        w = by[(rel, mem)]
        return w["decision"], w["project"], w["hold"]
    check(dec(rows[0]["relpath"]) == ("place", "AE-biomaGUNE-1121", ""), "C1: 1121 place-after-reopen -> place")
    check(dec(rows[1]["relpath"]) == ("place", "AE-biomaGUNE-0118", ""), "C2: Monocrotalina -> place in AE-biomaGUNE-0118")
    check(dec(rows[2]["relpath"]) == ("held", "AE-biomaGUNE-0118", "M1-0118"), "C2: the rest of 0118 -> held M1")
    check(dec(rows[3]["relpath"]) == ("held", "AE-biomaGUNE-1521", "reopen-AE-biomaGUNE-1521"), "C3: 1521 -> held")
    w = by[(rows[4]["relpath"], "")]
    check((w["decision"], w["project"], w["root"]) == ("place", "AE-biomaGUNE-1121", "pili y mili|proyecto 1121 london"),
          "C4: placed-elsewhere -> placed in drive 3's project, with a study folder")
    check(dec(rows[5]["relpath"])[0] == "holding" and by[(rows[5]["relpath"], "")]["root"] == "", "C5: model output -> holding")
    check(dec(rows[6]["relpath"])[0] == "holding",
          "C5 side effect: a copy that was covered only by the model output is no longer covered -> holding")
    w = by[(rows[8]["relpath"], "")]
    check(w["decision"] == "covered-by-twin" and rows[7]["relpath"] in w["note"], "an unclaimed copy of placed bytes -> covered-by-twin")
    check(dec(rows[9]["relpath"])[0] == "holding", "an unclaimed file with no twin -> holding")
    w = by[(rows[11]["relpath"], "")]
    check(dec(rows[10]["relpath"])[0] == "place" and w["decision"] == "duplicate-copy" and rows[10]["relpath"] in w["note"],
          "dedup: a copy in another study folder of the same project -> duplicate-copy (Pili y Mili first)")
    check(dec(rows[12]["relpath"])[0] == dec(rows[13]["relpath"])[0] == "place", "dedup: copies in ONE study folder are all kept")
    check(dec(rows[14]["relpath"])[0] == dec(rows[15]["relpath"])[0] == "holding", "dedup: holding keeps every copy")
    check(P.reason_of(by[(rows[16]["relpath"], "")]).startswith("A2 D8"), "the tool's reason says D8")
    check(dec(rows[17]["relpath"])[0] == "deferred", "biomaGUNE MJ stays deferred, even a model output")
    check(dec(rows[18]["relpath"])[0] == "exclude", "zero-byte -> exclude")
    check(dec(rows[19]["relpath"])[:2] == ("already-placed", "AE-biomaGUNE-0118"), "already placed under 0118 -> AE-biomaGUNE-0118")
    z = rows[20]["relpath"]
    check(dec(z)[0] == "expanded" and dec(z, "a.docx") == ("place", "AE-biomaGUNE-0424", "") and dec(z, "b.docx")[0] == "place",
          "P1: the zip is expanded, its members placed")
    check(by[(z, "a.docx")]["root"] == "pili y mili|proyecto 0424 envejecimiento y pah", "P1: members keep the zip's study folder")
    r = P.reason_of(by[(rows[2]["relpath"], "")])
    check(P.HELD_SEP in r and "M1" in r, f"a held row's reason says what it waits on: {r[:60]}")
    check(N.mappable(P.reason_of(by[(rows[9]["relpath"], "")])) and not N.mappable(P.reason_of(by[(rows[5]["relpath"], "")])),
          "a (C)/no-claim holding row stays mappable in a 2b round; a decided one (C5) does not")
    mrows = P.manifest_rows(work, PROJECTS, {})
    check([m["relpath"] for m in mrows if m["member"]] == [z, z] and all(m["archive"] == z for m in mrows if m["member"]),
          "manifest: a member row carries the archive in relpath and archive (the drives 1+2 convention)")


def _nas(tmp, projects):
    nas = os.path.join(tmp, "nas")
    os.makedirs(os.path.join(nas, "registries"))
    with open(os.path.join(nas, "registries", "registry_projects.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["project_id", "name", "description", "owner", "start_date", "status",
                                          "last_activity", "folder_location", "notes"], lineterminator="\r\n")
        w.writeheader()
        for n, p in projects.items():
            w.writerow({"project_id": p["project_id"], "name": n, "status": p["status"], "folder_location": p["folder_location"]})
    from ingest import provenance
    for n in projects:
        provenance.write_empty(os.path.join(nas, "projects", n, "provenance.csv"))
    return nas


def test_release():
    print("release: held rows -> a NEW manifest of only them, re-planned against the NAS")
    tmp = tempfile.mkdtemp(prefix="p_release_")
    try:
        nas = _nas(tmp, PROJECTS)
        base = {k: "" for k in N.MANIFEST_FIELDS}
        rows = [dict(base, row=1, drive="D3", drive_label="drive3_MJesus-MFB", relpath=r"MRI\Proyecto 0118 (Ratas hipoxia)\s.mhd",
                     size="3", sha256="x", decision="held", hold="M1-0118", project_name="AE-biomaGUNE-0118",
                     reason="claim CONFIRMED" + P.HELD_SEP + "C2", root_key="mri|proyecto 0118 (ratas hipoxia)"),
                dict(base, row=2, drive="D3", drive_label="drive3_MJesus-MFB", relpath=r"Pili y Mili\x.docx", size="3",
                     sha256="y", decision="place", project_name="AE-biomaGUNE-0619", reason="claim CONFIRMED", root_key="-")]
        m = os.path.join(tmp, "b1", "placement_manifest.csv")
        N.wcsv(m, N.MANIFEST_FIELDS, rows)
        out = os.path.join(tmp, "rel")
        rc = P.main(["--nas", nas, "release", "--manifest", m, "--hold", "M1-0118", "--project", "Proyecto-0118-rats-hipoxia", "--out", out])
        check(rc == 2, "release into a project that does not exist yet is refused (create it first)")
        rc = P.main(["--nas", nas, "release", "--manifest", m, "--hold", "M1-0118", "--out", os.path.dirname(m)])
        check(rc == 2, "release refuses to write over the batch's own folder")
        rc = P.main(["--nas", nas, "release", "--manifest", m, "--hold", "M1-0118", "--out", out])
        new = list(csv.DictReader(open(os.path.join(out, "placement_manifest.csv"), encoding="utf-8", newline="")))
        check(rc == 0 and len(new) == 1 and new[0]["decision"] == "place" and new[0]["hold"] == "", "only the released rows, as place")
        check(new[0]["dest_rel"] == r"projects\AE-biomaGUNE-0118\working\historical_drives\MJesus-MFB\Proyecto 0118 (Ratas hipoxia)\s.mhd",
              f"its destination: {new[0]['dest_rel']}")
        check("released" in new[0]["reason"] and P.HELD_SEP not in new[0]["reason"], f"reason: {new[0]['reason']}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _raw(nas, acqs):
    """A live /raw/ on a temp NAS: registry_raw.csv + per acquisition a folder holding its data file, with a
    checksums.json (as every ingest writes one) or without (then raw-dedup hashes the folder itself)."""
    import json
    with open(os.path.join(nas, "registries", "registry_raw.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["acq_id", "registration_datetime", "instrument", "project_id", "canonical_path"])
        w.writeheader()
        for acq, data, with_json in acqs:
            cp = f"/raw/MICROSCOPY/2026/2026-10/{acq}/"
            w.writerow({"acq_id": acq, "registration_datetime": "2026-10-06T09:03:49Z", "instrument": "ZWSI",
                        "project_id": "PROJ-0002", "canonical_path": cp})
            d = os.path.join(nas, "raw", "MICROSCOPY", "2026", "2026-10", acq)
            os.makedirs(d)
            with open(os.path.join(d, f"{acq}.czi"), "wb") as g:
                g.write(data)
            with open(os.path.join(d, "metadata.json"), "w", encoding="utf-8") as g:
                g.write("{}")
            if with_json:
                with open(os.path.join(d, "checksums.json"), "w", encoding="utf-8") as g:
                    json.dump({"algorithm": "sha256", "files": {f"{acq}.czi": _sha(data)}}, g)


def test_handover_second_batch():
    print("handover: a second batch (stream M's not-registered exams, stream C's derivatives) lands in batch 1's folders")
    tmp = tempfile.mkdtemp(prefix="p_handover_")
    saved = (P.MANIFEST_COPY, P.MANIFEST_NAS, P.claim_roots)
    try:
        nas = _nas(tmp, PROJECTS)
        files = {r"Pili y Mili\Proyecto 0619 Ratones PAH\MRI\20200101_000000_m1_0619_1_1\7\acqp": b"acqp bytes",
                 r"Pili y Mili\Proyecto 0619 Ratones PAH\MRI\20200101_000000_m1_0619_1_1\7\method": b"method bytes",
                 r"Pili y Mili\Proyecto 0619 Ratones PAH\Histo\scalebar.czi": b"scale bar czi",
                 r"Pili y Mili\Proyecto 0619 Ratones PAH\Histo\nocopy.czi": b"no parent",
                 r"Pili y Mili\Proyecto 0619 Ratones PAH\fig.png": b"batch one",
                 r"Pili y Mili\Proyecto 0619 Ratones PAH\raw.czi": b"in raw",
                 r"Pili y Mili\Proyecto 0619 Ratones PAH\again.tif": b"already in the tree",
                 r"Pili y Mili\Proyecto 0619 Ratones PAH\raw2.czi": b"in raw, no checksums.json"}
        man = os.path.join(tmp, "drive_manifest.csv")
        with open(man, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["relpath", "size", "mtime", "birthtime", "atime", "mtime_ns", "sha256"])
            for rel, b in files.items():
                w.writerow([rel, len(b), "", "", "", "", _sha(b)])
        # /raw/ is read LIVE (each acquisition's checksums.json; one without it is hashed directly)
        _raw(nas, [("ACQ-20261006-ZWSI-001", b"in raw", True), ("ACQ-20261006-ZWSI-002", b"in raw, no checksums.json", False)])
        P.MANIFEST_COPY = P.MANIFEST_NAS = man
        P.claim_roots = lambda: (lambda rel, proj: "pili y mili|proyecto 0619 ratones pah")
        # batch 1 already on the NAS: fig.png placed, its folder frozen, and again.tif's bytes indexed
        tree = os.path.join(nas, "projects", "AE-biomaGUNE-0619", "working", "historical_drives")
        os.makedirs(tree)
        H.write_pathmap(os.path.join(tree, H.PATHMAP_NAME),
                        [{"node_key": r"D3:Pili y Mili\Proyecto 0619 Ratones PAH", "rendered": r"MJesus-MFB\Proyecto 0619 Ratones PAH"}])
        H.write_index(os.path.join(tree, H.INDEX_NAME), [
            {"new_path": r"MJesus-MFB\Proyecto 0619 Ratones PAH\fig.png", "drive": "drive3_MJesus-MFB", "archive": "",
             "original_path": r"drive3_MJesus-MFB\Pili y Mili\Proyecto 0619 Ratones PAH\fig.png", "size": "9",
             "sha256": _sha(b"batch one"), "claim_id": "", "shortened": "N", "why": "", "note": ""},
            {"new_path": r"FRIO-X6\Other\again_copy.tif", "drive": "drive1_FRIO-X6", "archive": "",
             "original_path": r"drive1_FRIO-X6\Other\again_copy.tif", "size": "19", "sha256": _sha(b"already in the tree"),
             "claim_id": "", "shortened": "N", "why": "", "note": ""}])
        b1 = os.path.join(tmp, "b1", "placement_manifest.csv")
        N.wcsv(b1, N.MANIFEST_FIELDS, [{"row": 1, "drive": "D3", "relpath": r"Pili y Mili\Proyecto 0619 Ratones PAH\fig.png",
                                        "member": "", "decision": "place", "project_name": "AE-biomaGUNE-0619",
                                        "sha256": _sha(b"batch one")}])
        lst = os.path.join(tmp, "handover.csv")
        with open(lst, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["relpath", "kind", "project", "reason", "parent_acq_ids", "sha256"])
            w.writeheader()
            for rel in list(files)[:2]:
                w.writerow({"relpath": rel, "kind": "notregistered:non-image", "project": "AE-biomaGUNE-0619", "reason": "PRESS spectroscopy"})
            w.writerow({"relpath": list(files)[2], "kind": "derivative", "project": "AE-biomaGUNE-0619",
                        "reason": "scale-bar copy", "parent_acq_ids": "ACQ-20200101-CELL-001"})
            w.writerow({"relpath": list(files)[3], "kind": "derivative", "project": "AE-biomaGUNE-0619"})
            w.writerow({"relpath": list(files)[4], "kind": "other", "project": "AE-biomaGUNE-0619"})
            w.writerow({"relpath": list(files)[5], "kind": "other", "project": "AE-biomaGUNE-0619"})
            w.writerow({"relpath": list(files)[6], "kind": "other", "project": "AE-biomaGUNE-0619"})
            w.writerow({"relpath": list(files)[7], "kind": "other", "project": "AE-biomaGUNE-0619"})
            w.writerow({"relpath": "not\\on the drive.txt", "kind": "other"})
        out = os.path.join(tmp, "b2")
        rc = P.main(["--nas", nas, "handover", "--manifest", b1, "--csv", lst, "--stream", "M", "--out", out])
        rows = {r["relpath"]: r for r in csv.DictReader(open(os.path.join(out, "placement_manifest.csv"), encoding="utf-8", newline=""))}
        check(rc == 1, "refusals make the run exit non-zero, so they are read")
        check(set(rows) == set(list(files)[:3]) | {list(files)[6]},
              f"refused: the derivative without a parent, the batch-1 file, both /raw/ files (one found through "
              f"checksums.json, one hashed live), the unknown path ({sorted(rows)})")
        idx = os.path.join(tmp, "live_raw.csv")
        check(V.main(["raw-dedup", "--manifest", b1, "--nas", nas, "--write-index", idx]) == 0, "raw-dedup writes a live index")
        out2 = os.path.join(tmp, "b2b")
        P.main(["--nas", nas, "handover", "--manifest", b1, "--csv", lst, "--stream", "M", "--out", out2, "--raw-index", idx])
        rows2 = {r["relpath"] for r in csv.DictReader(open(os.path.join(out2, "placement_manifest.csv"), encoding="utf-8", newline=""))}
        check(rows2 == set(rows), "a saved live index (--raw-index) refuses the same /raw/ files")
        acqp = rows[list(files)[0]]
        check(acqp["decision"] == "place" and acqp["dest_rel"].startswith(
              r"projects\AE-biomaGUNE-0619\working\historical_drives\MJesus-MFB\Proyecto 0619 Ratones PAH\MRI\\"[:-1]),
              f"lands inside batch 1's study folder (frozen): {acqp['dest_rel']}")
        check(acqp["why"] == N.NOTREG_WHY["non-image"], "not-registered rows carry the plain reason")
        nr = list(csv.DictReader(open(os.path.join(out, "trees", r"projects__AE-biomaGUNE-0619__working__historical_drives", "_NOTREG.csv"),
                                      encoding="utf-8", newline="")))
        check(len(nr) == 1 and nr[0]["folder"].endswith(r"20200101_000000_m1_0619_1_1\7"), f"one README_not_registered per exam folder {nr}")
        d = rows[list(files)[2]]
        check(d["reason"].startswith("R3 derivative of ACQ-20200101-CELL-001"), "a derivative's reason carries its parent ACQ-ID")
        check(N.prov_entry(d, "RUN", "t", "x")["input_refs"].startswith("ACQ-20200101-CELL-001; "),
              "so its provenance input_refs start with the parent")
        check(rows[list(files)[6]]["decision"] == "already-placed", "bytes already in the tree (another drive's row) -> already-placed")
    finally:
        P.MANIFEST_COPY, P.MANIFEST_NAS, P.claim_roots = saved
        shutil.rmtree(tmp, ignore_errors=True)


def test_raw_dedup():
    print("raw-dedup: no copied or held file is an acquisition file in /raw/ (read live, checksums.json or hashed)")
    tmp = tempfile.mkdtemp(prefix="p_rawdedup_")
    try:
        nas = _nas(tmp, PROJECTS)
        _raw(nas, [("ACQ-20261006-ZWSI-001", b"czi one", True), ("ACQ-20261006-ZWSI-002", b"czi two", False)])
        idx = V.live_raw_index(nas, say=lambda m: None)
        check({x["sha256"] for x in idx} == {_sha(b"czi one"), _sha(b"czi two")} and len(idx) == 2,
              "the live index has both acquisitions' data files (and not the generated metadata.json)")
        check({x["source"] for x in idx} == {"checksums.json", "hashed"}, "one through checksums.json, one hashed directly")
        base = {k: "" for k in N.MANIFEST_FIELDS}
        m = os.path.join(tmp, "m", "placement_manifest.csv")
        N.wcsv(m, N.MANIFEST_FIELDS, [dict(base, row=1, relpath="a", decision="place", sha256=_sha(b"not raw")),
                                      dict(base, row=2, relpath="b", decision="duplicate-copy", sha256=_sha(b"czi one"))])
        check(V.main(["raw-dedup", "--manifest", m, "--nas", nas]) == 0, "PASS when only a listed-only row matches /raw/")
        N.wcsv(m, N.MANIFEST_FIELDS, [dict(base, row=1, relpath="a", decision="holding", sha256=_sha(b"czi two"))])
        check(V.main(["raw-dedup", "--manifest", m, "--nas", nas]) == 1, "FAIL when a copied row's bytes are in /raw/")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_verify_window():
    print("p_verify: snapshot before, verify after -- earlier rows kept, new rows once, temp files caught")
    tmp = tempfile.mkdtemp(prefix="p_verify_")
    old = N.DRIVES
    try:
        projects = {"AE-biomaGUNE-0118": PROJECTS["AE-biomaGUNE-0118"]}
        nas = _nas(tmp, projects)
        tree = os.path.join(nas, "projects", "AE-biomaGUNE-0118", "working", "historical_drives")
        os.makedirs(os.path.join(tree, "FRIO-X6", "S"))
        old9 = ["new_path", "drive", "archive", "original_path", "size", "sha256", "claim_id", "shortened", "note"]
        with open(os.path.join(tree, H.INDEX_NAME), "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=old9, lineterminator="\r\n")
            w.writeheader()
            w.writerow({"new_path": r"FRIO-X6\S\a.pdf", "drive": "drive1_FRIO-X6", "original_path": r"drive1_FRIO-X6\X\S\a.pdf",
                        "size": "1", "sha256": "s1", "shortened": "N"})
        H.write_pathmap(os.path.join(tree, H.PATHMAP_NAME), [{"node_key": r"D1:X\S", "rendered": r"FRIO-X6\S"}])
        with open(os.path.join(tree, "FRIO-X6", "S", H.ORIGIN_NAME), "wb") as f:
            f.write(H.origin_text([r"drive1_FRIO-X6\X\S"]).encode("utf-8"))
        stage = os.path.join(tmp, "stage")
        os.makedirs(os.path.join(stage, "files", "Pili y Mili", "Proyecto 0118 Monocrotalina"))
        with open(os.path.join(stage, "files", "Pili y Mili", "Proyecto 0118 Monocrotalina", "m.xlsx"), "wb") as f:
            f.write(b"monocrotalina")
        N.DRIVES = dict(old, D3=("drive3_MJesus-MFB", stage))
        rows = [{k: "" for k in N.MANIFEST_FIELDS}]
        rows[0].update(row=1, drive="D3", drive_label="drive3_MJesus-MFB", relpath=r"Pili y Mili\Proyecto 0118 Monocrotalina\m.xlsx",
                       size=str(len(b"monocrotalina")), sha256=_sha(b"monocrotalina"), decision="place",
                       project_name="AE-biomaGUNE-0118", reason="claim CONFIRMED", root_key="pili y mili|proyecto 0118 monocrotalina",
                       **{"class": "document"})
        out = os.path.join(tmp, "out")
        N.assign_destinations(rows, N.load_projects(nas), nas, out, lambda m: None, {}, None)
        m = os.path.join(out, "placement_manifest.csv")
        N.wcsv(m, N.MANIFEST_FIELDS, rows)
        snap = os.path.join(tmp, "snap")
        check(V.main(["snapshot", "--manifest", m, "--nas", nas, "--to", snap]) == 0, "snapshot taken")
        check(os.path.exists(os.path.join(snap, "projects", "AE-biomaGUNE-0118", "working", "historical_drives", "FRIO-X6", "S", H.ORIGIN_NAME)),
              "the snapshot keeps the NAS layout (it can serve as a rehearsal root)")
        check(V.main(["snapshot", "--manifest", m, "--nas", nas, "--to", snap]) == 2, "a second snapshot into the same folder is refused")
        check(V.main(["verify", "--manifest", m, "--nas", nas, "--snapshot", snap, "--rehash", "all"]) == 1,
              "verify FAILS before the copy (the file is missing)")
        N.main(["--out", out, "--nas", nas, "copy", "--manifest", m, "--execute", "--scratch", os.path.join(tmp, "scr")])
        check(V.main(["verify", "--manifest", m, "--nas", nas, "--snapshot", snap, "--rehash", "all"]) == 0,
              "verify PASSES after the copy: drive 1's row kept, the new row added once, provenance, README, registries")
        # a SECOND batch into the same tree (a release / a handover): batch 1's file is there before, not extra
        with open(os.path.join(stage, "files", "Pili y Mili", "Proyecto 0118 Monocrotalina", "n.xlsx"), "wb") as f:
            f.write(b"second batch")
        rows2 = [dict(rows[0], row=1, relpath=r"Pili y Mili\Proyecto 0118 Monocrotalina\n.xlsx", dest_rel="", shortened="",
                      size=str(len(b"second batch")), sha256=_sha(b"second batch"))]
        out2 = os.path.join(tmp, "out2")
        N.assign_destinations(rows2, N.load_projects(nas), nas, out2, lambda m: None, {}, None)
        m2 = os.path.join(out2, "placement_manifest.csv")
        N.wcsv(m2, N.MANIFEST_FIELDS, rows2)
        snap2 = os.path.join(tmp, "snap2")
        V.main(["snapshot", "--manifest", m2, "--nas", nas, "--to", snap2])
        N.main(["--out", out2, "--nas", nas, "copy", "--manifest", m2, "--execute", "--scratch", os.path.join(tmp, "scr")])
        check(V.main(["verify", "--manifest", m2, "--nas", nas, "--snapshot", snap2, "--rehash", "all"]) == 0,
              "a second batch verifies clean: the first batch's file is 'there before', its index row kept")
        os.remove(os.path.join(tree, "MJesus-MFB", "Proyecto 0118 Monocrotalina", "m.xlsx"))
        check(V.main(["verify", "--manifest", m2, "--nas", nas, "--snapshot", snap2, "--rehash", "none"]) == 1,
              "and a first-batch file that vanished during the second window is caught")
        with open(os.path.join(tree, "MJesus-MFB", "Proyecto 0118 Monocrotalina", "m.xlsx"), "wb") as f:
            f.write(b"monocrotalina")
        part = os.path.join(tree, "MJesus-MFB", "Proyecto 0118 Monocrotalina", ".~nonraw-deadbeef.part")
        open(part, "wb").close()
        check(V.main(["verify", "--manifest", m, "--nas", nas, "--snapshot", snap, "--rehash", "none"]) == 1,
              "a temp file left by an interrupted copy is caught")
        os.remove(part)
        idx = os.path.join(tree, H.INDEX_NAME)
        keep = [r for r in csv.DictReader(open(idx, encoding="utf-8-sig", newline="")) if r["drive"] != "drive1_FRIO-X6"]
        with open(idx, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(keep[0].keys()))
            w.writeheader()
            w.writerows(keep)
        check(V.main(["verify", "--manifest", m, "--nas", nas, "--snapshot", snap, "--rehash", "none"]) == 1,
              "a lost drive-1 index row is caught")
    finally:
        N.DRIVES = old
        shutil.rmtree(tmp, ignore_errors=True)


def test_verify_two_trees():
    print("p_verify over two trees in one window (the state of one tree must not leak into the next)")
    tmp = tempfile.mkdtemp(prefix="p_verify2_")
    old = N.DRIVES
    try:
        projects = {p: PROJECTS[p] for p in ("AE-biomaGUNE-0118", "AE-biomaGUNE-0619")}
        nas = _nas(tmp, projects)
        stage = os.path.join(tmp, "stage")
        rows = []
        for i, (proj, folder) in enumerate([("AE-biomaGUNE-0118", "Proyecto 0118 Monocrotalina"),
                                            ("AE-biomaGUNE-0619", "Proyecto 0619 Ratones PAH")], 1):
            os.makedirs(os.path.join(stage, "files", "Pili y Mili", folder))
            data = f"file of {proj}".encode()
            with open(os.path.join(stage, "files", "Pili y Mili", folder, "x.xlsx"), "wb") as f:
                f.write(data)
            r = {k: "" for k in N.MANIFEST_FIELDS}
            r.update(row=i, drive="D3", drive_label="drive3_MJesus-MFB", relpath=rf"Pili y Mili\{folder}\x.xlsx",
                     size=str(len(data)), sha256=_sha(data), decision="place", project_name=proj, reason="claim CONFIRMED",
                     root_key=f"pili y mili|{folder.lower()}", **{"class": "document"})
            rows.append(r)
        N.DRIVES = dict(old, D3=("drive3_MJesus-MFB", stage))
        out = os.path.join(tmp, "out")
        N.assign_destinations(rows, N.load_projects(nas), nas, out, lambda m: None, {}, None)
        m = os.path.join(out, "placement_manifest.csv")
        N.wcsv(m, N.MANIFEST_FIELDS, rows)
        snap = os.path.join(tmp, "snap")
        V.main(["snapshot", "--manifest", m, "--nas", nas, "--to", snap])
        N.main(["--out", out, "--nas", nas, "copy", "--manifest", m, "--execute", "--scratch", os.path.join(tmp, "scr")])
        check(V.main(["verify", "--manifest", m, "--nas", nas, "--snapshot", snap, "--rehash", "all"]) == 0,
              "both trees verify in one run")
    finally:
        N.DRIVES = old
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    test_rules()
    test_decide()
    test_release()
    test_handover_second_batch()
    test_raw_dedup()
    test_verify_window()
    test_verify_two_trees()
    print(f"\n{'FAILED: ' + str(len(FAILS)) if FAILS else 'all passed'}")
    sys.exit(1 if FAILS else 0)
