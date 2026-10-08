#!/usr/bin/env python3
"""test_drive3_bmj.py -- the third placement batch, `biomaGUNE MJ` (tools/drive_staging/drive3/bmj_plan.py), and the
three small changes it needed in stream P's tools:

  bmj_plan   the personal/administrative screen (judged names only; an unjudged hit STOPS); the folders whose
             name gives two protocols (TWO: no claim of their own; R5: a nearer single-code claim stands when
             the folder is its only disagreement and its own evidence is not contrary; R3b: a date folder reads
             the next claim out);
  p_plan     `handover` takes a row an earlier manifest only DEFERRED; carries class / claim_id / verdict; a
             holding row keeps a mappable reason ("no claim", "(C) claim") so a later 2b round can map it;
  README     the 0522 / 0619 / 0424 trees carry the researchers' note that the drive's masks are drafts
             (0522 also: IRE = Irene's corrections); every other tree keeps PROJECT_README byte for byte, and
             p_verify expects exactly what the copy publishes.

Run:  python tools/test_drive3_bmj.py
"""
import csv
import hashlib
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "drive_staging", "drive3"))
sys.path.insert(0, os.path.join(HERE, "drive_staging"))
sys.path.insert(0, HERE)
import bmj_plan as B  # noqa: E402
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


PROJECTS = {n: {"project_id": f"PROJ-{i:04d}", "name": n, "status": "active", "folder_location": f"/projects/{n}/"}
            for i, n in enumerate(["AE-biomaGUNE-0424", "AE-biomaGUNE-1019", "AE-biomaGUNE-0522", "AE-biomaGUNE-0619",
                                   "AE-biomaGUNE-0118"], 1)}
AGED = B.BMJ + "PAH aged_Proyecto 0424 & 1019 (female and male)"
DIETS = B.BMJ + "PAH diets_Proyecto 0619 & 0522 (female and male)"


def test_personal_screen():
    print("the personal / administrative screen: names only, every hit judged, an unjudged hit stops")
    j = B.judge_personal
    check(j(B.BMJ + r"Proteomica\Muestras\IMG_20220905_135733.jpg")[0] == "personal", "a phone-camera photo -> personal")
    check(j(B.BMJ + r"X\Raw data\PET\59\someone_picture.jpg")[0] == "personal", "a picture named after a person -> personal")
    check(j(B.BMJ + r"Metformina\TO DO LIST en mi ausencia.docx")[0] == "personal", "a note about the owner's absence -> personal")
    check(j(B.BMJ + r"X\Documentos\v2-for-ep-03v09_formulario_de_solicitud_de_evaluacion_de_proyecto.docx")[0] == "screened-project",
          "a CEEA form is project paperwork, not personal")
    check(j(B.BMJ + r"X\admin_2024-10-15 16-24-48_BR009379 -  Quantification Cq Results.xlsx")[0] == "screened-project",
          "the qPCR export named admin_ is project material")
    check(j(B.BMJ + r"X\Sacrificio 1123.xlsx") == ("", ""), "an ordinary name is no hit")
    for name in (r"X\CV Maria.pdf", r"X\nomina enero.pdf", r"X\contrato.docx", r"X\holiday.jpg", r"X\DNI.pdf"):
        try:
            j(B.BMJ + name)
            check(False, f"an unjudged hit must STOP: {name}")
        except SystemExit as e:
            check("nobody has judged" in str(e), f"an unjudged hit STOPS the run: {name}")


def _claims():
    rows = [
        # the two-code folders, as the engine read them (one code CONFIRMED, the other SHADOWED / C)
        {"claim_id": "CL-T1", "claim_root": AGED, "token": "1019", "source": "folder", "verdict": "CONFIRMED",
         "proposed_project": "AE-biomaGUNE-1019", "evidence": ""},
        {"claim_id": "CL-T2", "claim_root": AGED, "token": "0424", "source": "folder", "verdict": "SHADOWED",
         "proposed_project": "", "evidence": ""},
        {"claim_id": "CL-T3", "claim_root": DIETS, "token": "0522", "source": "folder", "verdict": "C",
         "proposed_project": "", "evidence": "valid protocol but cross-checks FAIL"},
        # nearer single-code claims
        {"claim_id": "CL-F", "claim_root": AGED + r"\PAH aged Female_Proyecto 0424", "token": "0424", "source": "folder",
         "verdict": "CONFIRMED", "proposed_project": "AE-biomaGUNE-0424", "evidence": ""},
        {"claim_id": "CL-K", "claim_root": DIETS + r"\Machos KD diet-2303-0522", "token": "0522", "source": "folder",
         "verdict": "CONFIRMED", "proposed_project": "AE-biomaGUNE-0522", "evidence": ""},
        {"claim_id": "CL-D1", "claim_root": DIETS + r"\Machos KD diet-2303-0522\2305-Machos KD", "token": "2305",
         "source": "folder", "verdict": "C", "proposed_project": "", "evidence": "x | " + B.DATE_EVIDENCE},
        {"claim_id": "CL-D2", "claim_root": DIETS + r"\Machos HCH diet-2311", "token": "2311", "source": "folder",
         "verdict": "C", "proposed_project": "", "evidence": "x | " + B.DATE_EVIDENCE},
        {"claim_id": "CL-X", "claim_root": AGED + r"\PAH aged Female_Proyecto 0424\PET", "token": "0422", "source": "filename",
         "verdict": "CONFIRMED", "proposed_project": "AE-biomaGUNE-0422", "evidence": ""},
        {"claim_id": "CL-Z", "claim_root": B.BMJ + "Other_Proyecto 0118", "token": "0118", "source": "folder",
         "verdict": "CONFIRMED", "proposed_project": "AE-biomaGUNE-0118", "evidence": ""},
    ]
    return B.Claims(rows)


def f(rel, verdict, cid, prop="", conflict=""):
    return {"relpath": rel, "verdict": verdict, "claim_id": cid, "proposed_project": prop, "conflict": conflict}


def test_two_code_rules():
    print("folders that give two protocols: TWO, R5, R3b; everything else as the engine says")
    cl = _claims()
    rels = [AGED + r"\a\x.nii", DIETS + r"\b\y.nii", B.BMJ + r"Bleomicina Mice_Proyecto 1123\z.nii",
            B.BMJ + r"Machos KD diet-2303-0522\w.nii"]
    tf = B.two_code_folders(rels, PROJECTS)
    check(set(tf) == {AGED, DIETS} and tf[AGED] == ["0424", "1019"],
          f"only folders whose name gives two gjesus3 protocols count (not `diet-2303-0522`: 2303 is no project) {tf}")
    po = B.project_of
    r = po(f(AGED + r"\Sacrificio\s.xlsx", "CONFIRMED", "CL-T1", "AE-biomaGUNE-1019"), cl, tf)
    check(r[:3] == ("", "TWO", "C"), f"TWO: the engine's CONFIRMED read of the two-code folder itself -> no project {r[:3]}")
    r = po(f(AGED + r"\PAH aged Female_Proyecto 0424\MRI\m.nii", "C", "CL-F",
             conflict="nested claims disagree: nearest 0424 (CONFIRMED) vs outer 1019; animal 4 is found in BOTH 0424 and 1019, "
                      "and the DB dates do not separate them (procedure-date match none)"), cl, tf)
    check(r[:2] == ("AE-biomaGUNE-0424", "R5"), f"R5: the nearer 0424 claim stands (inconclusive animal evidence) {r[:2]}")
    r = po(f(DIETS + r"\Machos KD diet-2303-0522\PV\ID 34-0522.txt", "C", "CL-K",
             conflict="nested claims disagree: nearest 0522 (CONFIRMED) vs outer 0619,2303; no animal number to decide between them -> C"),
           cl, tf)
    check(r[:2] == ("AE-biomaGUNE-0522", "R5"), f"R5: a never-confirmed YYMM token in the outer list does not contradict {r[:2]}")
    r = po(f(AGED + r"\PAH aged Female_Proyecto 0424\MRI\m.nii", "C", "CL-F",
             conflict="nested claims disagree: nearest 0424 (CONFIRMED) vs outer 1019,0118; no animal number to decide between them -> C"),
           cl, tf)
    check(r[0] == "", "not R5 when the outer list holds a confirmed protocol the folder does not give (0118)")
    r = po(f(AGED + r"\PAH aged Female_Proyecto 0424\MRI\m.nii", "C", "CL-F",
             conflict="nested claims disagree: nearest 0424 (CONFIRMED) vs outer 1019; animal 4 is NOT found in 0424 -> C"), cl, tf)
    check(r[0] == "", "not R5 when the file's own evidence is contrary")
    r = po(f(AGED + r"\PAH aged Female_Proyecto 0424\PET\SUV-m4-0422.nii", "C", "CL-X",
             conflict="nested claims disagree: nearest 0422 (CONFIRMED) vs outer 0424,1019; animal 4 is found in BOTH 0422 and "
                      "0424,1019, and the DB dates do not separate them"), cl, tf)
    check(r[0] == "", "not R5 when the nearer code is not one the folder gives (0422 in a 0424 & 1019 folder)")
    r = po(f(AGED + r"\PAH gathered aged\g.png", "C", "CL-T1",
             conflict="nested claims disagree: nearest 1019 (CONFIRMED) vs outer 0424; no animal number to decide between them -> C"), cl, tf)
    check(r[0] == "", "a file whose nearest claim IS the two-code folder stays without a project")
    r = po(f(DIETS + r"\Machos KD diet-2303-0522\2305-Machos KD\list.xlsx", "C", "CL-D1",
             conflict="nested claims disagree: nearest 2305 (C) vs outer 0522,0619,2303; nearest is unresolved -> C"), cl, tf)
    check(r[:2] == ("AE-biomaGUNE-0522", "R3b"), f"R3b: a date folder reads the next claim out (0522) {r[:2]}")
    r = po(f(DIETS + r"\Machos HCH diet-2311\list.xlsx", "C", "CL-D2",
             conflict="nested claims disagree: nearest 2311 (C) vs outer 0522,0619; nearest is unresolved -> C"), cl, tf)
    check(r[0] == "", "R3b finds nothing when the next claim out is the two-code folder itself -> no project")
    r = po(f(B.BMJ + r"Other_Proyecto 0118\o.pdf", "CONFIRMED", "CL-Z", "AE-biomaGUNE-0118"), cl, tf)
    check(r[:2] == ("AE-biomaGUNE-0118", "engine"), "a single-code claim outside any two-code folder: the engine's")
    check(po(f(B.BMJ + r"x\b.pdf", "B", "", "Project-0521"), cl, tf)[0] == "Project-0521" and
          po(f(B.BMJ + r"x\b.pdf", "B", "", "Project-0924"), cl, tf)[0] == "", "(B) per code: only Project-0521")
    check(po(f(B.BMJ + r"x\n.pdf", "NO-CLAIM", ""), cl, tf)[0] == "", "no claim -> no project")


def _nas(tmp, projects):
    nas = os.path.join(tmp, "nas")
    os.makedirs(os.path.join(nas, "registries"))
    with open(os.path.join(nas, "registries", "registry_projects.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["project_id", "name", "description", "owner", "start_date", "status",
                                           "last_activity", "folder_location", "notes"], lineterminator="\r\n")
        w.writeheader()
        for n, p in projects.items():
            w.writerow({"project_id": p["project_id"], "name": n, "status": p["status"], "folder_location": p["folder_location"]})
    with open(os.path.join(nas, "registries", "registry_raw.csv"), "w", encoding="utf-8", newline="") as fh:
        fh.write("acq_id,registration_datetime,instrument,project_id,canonical_path\n")
    from ingest import provenance
    for n in projects:
        provenance.write_empty(os.path.join(nas, "projects", n, "provenance.csv"))
    return nas


def test_handover_third_batch():
    print("handover: batch 1's deferred rows are a later batch's input; class / claim / verdict carried; holding mappable")
    tmp = tempfile.mkdtemp(prefix="bmj_handover_")
    saved = (P.MANIFEST_COPY, P.MANIFEST_NAS, P.claim_roots)
    try:
        nas = _nas(tmp, PROJECTS)
        files = {B.BMJ + r"Metformina Male PAH_Proyecto 0522\Figuras\f.png": b"figure",
                 B.BMJ + r"Proteomica\p.xlsx": b"proteomics",
                 B.BMJ + r"Proteomica\q.xlsx": b"decided in batch 1"}
        man = os.path.join(tmp, "drive_manifest.csv")
        with open(man, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["relpath", "size", "mtime", "birthtime", "atime", "mtime_ns", "sha256"])
            for rel, b in files.items():
                w.writerow([rel, len(b), "", "", "", "", _sha(b)])
        P.MANIFEST_COPY = P.MANIFEST_NAS = man
        P.claim_roots = lambda: (lambda rel, proj: "biomagune mj|metformina male pah_proyecto 0522")
        rels = list(files)
        b1 = os.path.join(tmp, "b1", "placement_manifest.csv")
        N.wcsv(b1, N.MANIFEST_FIELDS, [
            {"row": 1, "drive": "D3", "relpath": rels[0], "member": "", "decision": "deferred", "sha256": _sha(b"figure")},
            {"row": 2, "drive": "D3", "relpath": rels[1], "member": "", "decision": "deferred", "sha256": _sha(b"proteomics")},
            {"row": 3, "drive": "D3", "relpath": rels[2], "member": "", "decision": "holding", "sha256": _sha(b"decided in batch 1")}])
        lst = os.path.join(tmp, "bmj_handover.csv")
        N.wcsv(lst, B.HANDOVER_FIELDS, [
            {"relpath": rels[0], "kind": "other", "project": "AE-biomaGUNE-0522", "reason": "claim CONFIRMED",
             "class": "figure", "claim_id": "CL-2981", "verdict": "CONFIRMED"},
            {"relpath": rels[1], "kind": "other", "project": "", "reason": "no claim", "class": "document"},
            {"relpath": rels[2], "kind": "other", "project": "", "reason": "no claim", "class": "document"}])
        idx = os.path.join(tmp, "raw.csv")
        N.wcsv(idx, ["sha256"], [])
        out = os.path.join(tmp, "b3")
        rc = P.main(["--nas", nas, "handover", "--manifest", b1, "--csv", lst, "--stream", "BMJ", "--raw-index", idx, "--out", out])
        rows = {r["relpath"]: r for r in csv.DictReader(open(os.path.join(out, "placement_manifest.csv"), encoding="utf-8", newline=""))}
        check(set(rows) == set(rels[:2]) and rc == 1,
              "the deferred rows are taken; the row batch 1 DECIDED (holding) is still refused")
        r0, r1 = rows[rels[0]], rows[rels[1]]
        check((r0["decision"], r0["class"], r0["claim_id"], r0["verdict"]) == ("place", "figure", "CL-2981", "CONFIRMED"),
              f"class, claim and verdict are carried into the manifest {r0['class'], r0['claim_id'], r0['verdict']}")
        check(N.prov_entry(r0, "RUN", "t", "x")["notes"].endswith("claim CL-2981") and "class figure" in
              N.prov_entry(r0, "RUN", "t", "x")["process_description"], "so provenance names the class and the claim")
        check(r1["decision"] == "holding" and r1["reason"] == "no claim" and N.mappable(r1["reason"]) and "BMJ" in r1["note"],
              f"a holding row keeps its mappable reason (a later 2b round can map it); the stream is in note ({r1['reason']!r})")
        idx_rows = list(csv.DictReader(open(os.path.join(out, "trees", r"projects__AE-biomaGUNE-0522__working__historical_drives",
                                                         H.INDEX_NAME), encoding="utf-8-sig", newline="")))
        check(idx_rows and idx_rows[0]["claim_id"] == "CL-2981", "the tree's index row carries the claim")
    finally:
        P.MANIFEST_COPY, P.MANIFEST_NAS, P.claim_roots = saved
        shutil.rmtree(tmp, ignore_errors=True)


def test_readme_notes():
    print("README.txt: the drafts note in 0522 / 0619 / 0424 only; published by copy, expected by p_verify")
    base = lambda p: f"projects\\{p}\\working\\historical_drives"  # noqa: E731
    r22 = H.project_readme(base("AE-biomaGUNE-0522"))
    check(r22.startswith(H.PROJECT_README) and "drafts" in r22 and "0522" in r22 and "IRE" in r22, "0522: drafts + IRE note")
    r19 = H.project_readme(base("AE-biomaGUNE-0619"))
    check("drafts" in r19 and "0619" in r19 and "IRE" not in r19, "0619: the drafts note, no IRE line")
    check("0424" in H.project_readme(base("AE-biomaGUNE-0424")), "0424: the drafts note")
    check(H.project_readme(base("AE-biomaGUNE-1019")) == H.PROJECT_README and H.project_readme(N.HOLDING_BASE) == H.PROJECT_README
          and H.project_readme() == H.PROJECT_README, "every other tree keeps PROJECT_README byte for byte")
    check(all(len(l) <= 79 for l in r22.splitlines()), "the note keeps the README's line width")
    tmp = tempfile.mkdtemp(prefix="bmj_readme_")
    old = N.DRIVES
    try:
        projects = {p: PROJECTS[p] for p in ("AE-biomaGUNE-0522", "AE-biomaGUNE-1019")}
        nas = _nas(tmp, projects)
        stage = os.path.join(tmp, "stage")
        rows = []
        for i, proj in enumerate(projects, 1):
            folder = f"Proyecto {proj[-4:]}"
            os.makedirs(os.path.join(stage, "files", "biomaGUNE MJ", folder))
            data = f"file of {proj}".encode()
            with open(os.path.join(stage, "files", "biomaGUNE MJ", folder, "x.nii"), "wb") as fh:
                fh.write(data)
            r = {k: "" for k in N.MANIFEST_FIELDS}
            r.update(row=i, drive="D3", drive_label="drive3_MJesus-MFB", relpath=rf"biomaGUNE MJ\{folder}\x.nii",
                     size=str(len(data)), sha256=_sha(data), decision="place", project_name=proj, reason="claim CONFIRMED",
                     root_key=f"biomagune mj|{folder.lower()}", **{"class": "volume"})
            rows.append(r)
        N.DRIVES = dict(old, D3=("drive3_MJesus-MFB", stage))
        out = os.path.join(tmp, "out")
        N.assign_destinations(rows, N.load_projects(nas), nas, out, lambda m: None, {}, None)
        m = os.path.join(out, "placement_manifest.csv")
        N.wcsv(m, N.MANIFEST_FIELDS, rows)
        snap = os.path.join(tmp, "snap")
        V.main(["snapshot", "--manifest", m, "--nas", nas, "--to", snap])
        N.main(["--out", out, "--nas", nas, "copy", "--manifest", m, "--execute", "--scratch", os.path.join(tmp, "scr")])
        t22 = os.path.join(nas, "projects", "AE-biomaGUNE-0522", "working", "historical_drives", H.README_NAME)
        t19 = os.path.join(nas, "projects", "AE-biomaGUNE-1019", "working", "historical_drives", H.README_NAME)
        check(open(t22, "rb").read() == r22.replace("\n", "\r\n").encode("utf-8"), "the 0522 tree's README carries the note")
        check(open(t19, "rb").read() == H.PROJECT_README.replace("\n", "\r\n").encode("utf-8"), "the 1019 tree's README is unchanged")
        check(V.main(["verify", "--manifest", m, "--nas", nas, "--snapshot", snap, "--rehash", "all"]) == 0,
              "p_verify expects exactly what was published (both trees PASS)")
        with open(t22, "wb") as fh:
            fh.write(H.PROJECT_README.replace("\n", "\r\n").encode("utf-8"))
        check(V.main(["verify", "--manifest", m, "--nas", nas, "--snapshot", snap, "--rehash", "none"]) == 1,
              "and a 0522 README without the note is caught")
    finally:
        N.DRIVES = old
        shutil.rmtree(tmp, ignore_errors=True)


def test_readme_only_and_c5():
    print("readme: a tree that gets a note but no file in this batch (0619); C5 sends model outputs to holding")
    check(P.model_output(B.BMJ + r"PAH 2DG_Proyecto 0619 (female and male)\Raw data\MRI\S\Splits\Predict_Slicer\Time_5_x.mha")
          .startswith("C5"), "C5: a Predict_Slicer file inside biomaGUNE MJ is a model output (holding, beside the tool)")
    tmp = tempfile.mkdtemp(prefix="bmj_readme_only_")
    try:
        projects = {p: PROJECTS[p] for p in ("AE-biomaGUNE-0619", "AE-biomaGUNE-1019")}
        nas = _nas(tmp, projects)
        trees = {}
        for p in projects:
            t = os.path.join(nas, "projects", p, "working", "historical_drives")
            os.makedirs(t)
            with open(os.path.join(t, H.README_NAME), "wb") as fh:
                fh.write(H.PROJECT_README.replace("\n", "\r\n").encode("utf-8"))
            trees[p] = os.path.join(t, H.README_NAME)
        before = open(trees["AE-biomaGUNE-0619"], "rb").read()
        check(B.main(["--nas", nas, "readme", "--project", "AE-biomaGUNE-0619"]) == 0 and
              open(trees["AE-biomaGUNE-0619"], "rb").read() == before, "a dry run writes nothing")
        check(B.main(["--nas", nas, "readme", "--project", "AE-biomaGUNE-0619", "--execute"]) == 0, "--execute runs")
        want = H.project_readme(r"projects\AE-biomaGUNE-0619\working\historical_drives").replace("\n", "\r\n").encode("utf-8")
        check(open(trees["AE-biomaGUNE-0619"], "rb").read() == want, "0619's README now carries the note")
        check(not [x for x in os.listdir(os.path.dirname(trees["AE-biomaGUNE-0619"])) if x.endswith(".tmp")], "no temp file left")
        check(B.main(["--nas", nas, "readme", "--project", "AE-biomaGUNE-1019", "--execute"]) == 2 and
              open(trees["AE-biomaGUNE-1019"], "rb").read() == H.PROJECT_README.replace("\n", "\r\n").encode("utf-8"),
              "a project without a note is refused and untouched")
        check(B.main(["--nas", nas, "readme", "--project", "AE-biomaGUNE-0522"]) == 2, "a project not in the registry is refused")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    test_personal_screen()
    test_two_code_rules()
    test_handover_third_batch()
    test_readme_notes()
    test_readme_only_and_c5()
    print(f"\n{'FAILED: ' + str(len(FAILS)) if FAILS else 'all passed'}")
    sys.exit(1 if FAILS else 0)
