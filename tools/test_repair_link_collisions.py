#!/usr/bin/env python3
"""test_repair_link_collisions.py -- the link audit classifies by file id, and the repair is additive.

A scratch NAS reproduces what the OLD linker did (2026-10-04 and before: `makedirs(exist_ok)` and
"link only the files that do not exist yet"), in each of its shapes:

  A + B   two studies of one animal, same exam and recons, the SAME file names: B got nothing
          -> A OK, B MISSING (by planned name)
  C + D   same, but D has more frames: D's extra files went into C's folder
          -> C POLLUTED (partner D), D MISSING (its files sit in C's folder)
  E       an exact link -> OK
  F       its link deleted by a researcher, name free -> RESEARCHER-PRUNED
  G + H   G's link was removed, and H (same planned name) was linked there later; provenance says
          the name was created for G -> G RESEARCHER-PRUNED (not a merge victim), H OK
  Q       its link plus a researcher's notes file -> OK-EXTRA
  R       its link with one file deleted -> PARTIAL-OWN
  S       no link, queued in pending_links.csv -> PENDING-LINK
  P1 + P2 two file primaries (microscopy), one name: P2 skipped -> P2 MISSING, repair BLOCKED
          (no new convention outside MRI)
  Z       in a closed project -> CLOSED-PROJECT
  K       an MRI acquisition with an EMPTY primary whose planned name is E's -> EMPTY-PRIMARY, with
          E named as the partner (a collision with nothing to link)
  L1 + L2 file primaries whose names differ only in case (Windows only): L2 was skipped, yet the
          case-sensitive provenance check gave it a row -> L2 MISSING, not "pruned"
  P3      a third same-day `slide.czi` -> with --include-file-primaries P2 gets the dated name and
          P3 falls back to the ACQ-ID name

Then the repair: a dry run plans B and D under the new MRI convention (the study time from their
own study folder) and writes nothing; --execute links them, verifies, adds provenance, removes
nothing (C stays polluted); a re-audit shows B and D OK; a second repair plans nothing.

Run:  python tools/test_repair_link_collisions.py
"""
import contextlib
import csv
import io
import json
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import repair_link_collisions as R  # noqa: E402
from ingest import linker, provenance, registry  # noqa: E402

FAILED = []


def check(cond, msg):
    print(f"  {'ok' if cond else 'FAIL'}:   {msg}")
    if not cond:
        FAILED.append(msg)


def write(path, data=b"x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def old_merge(project, name, primary):
    """The pre-2026-10-05 create_hardlink, verbatim in behaviour: the silent merge."""
    dest = os.path.join(project, "raw_linked", name)
    if os.path.isdir(primary):
        os.makedirs(dest, exist_ok=True)
        for fn in os.listdir(primary):
            if not os.path.exists(os.path.join(dest, fn)):
                os.link(os.path.join(primary, fn), os.path.join(dest, fn))
    elif not os.path.exists(dest):
        os.link(primary, dest)
    return dest


STUDY1 = "20260710_114705_jrc20260710_m12_1125_jrc20260710_m12_1125_1_1"
STUDY2 = "20260710_130855_jrc20260710_m12_1125_jrc20260710_m12_1125_1_2"
MRI_CFG = "tools/templates/instruments/mri_bruker.yaml"


def main():
    with tempfile.TemporaryDirectory() as nas:
        reg = os.path.join(nas, "registries")
        os.makedirs(reg)
        with open(os.path.join(reg, "registry_projects.csv"), "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["project_id", "name", "description", "owner", "start_date", "status",
                        "last_activity", "folder_location", "notes"])
            w.writerow(["PROJ-0001", "alpha", "", "", "", "active", "", "/projects/alpha/", ""])
            w.writerow(["PROJ-0002", "gone", "", "", "", "closed", "", "/projects/gone/", ""])
        proj = os.path.join(nas, "projects", "alpha")
        os.makedirs(os.path.join(proj, "raw_linked"))
        provenance.write_empty(os.path.join(proj, "provenance.csv"))

        rows, prim = [], {}

        def mri(acq, study, exam, nframes, project="PROJ-0001", recons="1"):
            canon = f"/raw/DICOM/2026/2026-07/{acq}/"
            d = os.path.join(nas, canon.strip("/"), acq + ".data")
            os.makedirs(d, exist_ok=True)
            for i in range(1, nframes + 1):
                write(os.path.join(d, f"recon1_frame{i:02d}.dcm"), f"{acq}-{i}".encode())
            write(os.path.join(nas, canon.strip("/"), "metadata.json"), json.dumps(
                {"discovered": {"mri_exam_number": str(exam), "mri_recon_indices": recons}}).encode())
            rows.append({"acq_id": acq, "instrument": "MRI", "canonical_path": canon,
                         "primary_file_name": acq + ".data", "primary_kind": "folder",
                         "project_id": project, "sample_id": "m12_1125",
                         "original_name": f"{study}/{exam}", "ingest_config": MRI_CFG,
                         "acquisition_datetime": "2026-07-10T12:00:00"})
            prim[acq] = d
            return d

        def czi(acq, name):
            canon = f"/raw/MICROSCOPY/2026/2026-07/{acq}/"
            p = os.path.join(nas, canon.strip("/"), acq + ".czi")
            write(p, acq.encode())
            rows.append({"acq_id": acq, "instrument": "ZWSI", "canonical_path": canon,
                         "primary_file_name": acq + ".czi", "primary_kind": "file",
                         "project_id": "PROJ-0001", "sample_id": "s", "original_name": name,
                         "ingest_config": "tools/templates/instruments/axioscan7.yaml",
                         "acquisition_datetime": "2026-07-10T12:00:00"})
            prim[acq] = p
            return p

        A = mri("ACQ-20260710-MRI-001", STUDY1, 2, 3)
        B = mri("ACQ-20260710-MRI-002", STUDY2, 2, 3)
        C = mri("ACQ-20260710-MRI-003", STUDY1, 5, 3)
        D = mri("ACQ-20260710-MRI-004", STUDY2, 5, 15)
        E = mri("ACQ-20260710-MRI-005", STUDY1, 7, 2)
        mri("ACQ-20260710-MRI-006", STUDY1, 8, 2)                      # F: pruned
        G = mri("ACQ-20260710-MRI-007", STUDY1, 9, 2)
        H = mri("ACQ-20260710-MRI-008", STUDY2, 9, 2)
        Q = mri("ACQ-20260710-MRI-009", STUDY1, 10, 2)
        Rr = mri("ACQ-20260710-MRI-010", STUDY1, 11, 3)
        mri("ACQ-20260710-MRI-011", STUDY1, 12, 2)                     # S: pending
        mri("ACQ-20260710-MRI-012", STUDY1, 13, 2, project="PROJ-0002")  # Z: closed project
        P1 = czi("ACQ-20260710-ZWSI-001", "slide.czi")
        P2 = czi("ACQ-20260710-ZWSI-002", "sub/slide.czi")
        P3 = czi("ACQ-20260710-ZWSI-003", "other/slide.czi")
        mri("ACQ-20260710-MRI-013", STUDY2, 7, 0)                       # K: empty primary
        L1 = czi("ACQ-20260710-ZWSI-004", "a/Lipo_1.czi")
        L2 = czi("ACQ-20260710-ZWSI-005", "b/lipo_1.czi")

        with open(os.path.join(reg, "registry_raw.csv"), "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=registry.REGISTRY_FIELDS, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow(r)
        with open(os.path.join(reg, "pending_links.csv"), "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["acq_id", "project_id", "link_name", "status"])
            w.writerow(["ACQ-20260710-MRI-011", "PROJ-0001", "MRI_m12_1125_20260710_12_1", "pending"])

        n = "MRI_m12_1125_20260710_{}_1".format
        old_merge(proj, n(2), A)
        old_merge(proj, n(2), B)          # every name clashes: B gets nothing
        old_merge(proj, n(5), C)
        old_merge(proj, n(5), D)          # D's frames 4..15 land in C's folder
        old_merge(proj, n(7), E)
        old_merge(proj, n(9), G)
        provenance.append_entry(os.path.join(proj, "provenance.csv"), {
            "output_path": f"raw_linked/{n(9)}", "output_name": n(9), "file_type": "hardlink-folder",
            "input_refs": "ACQ-20260710-MRI-007"})
        for fn in os.listdir(os.path.join(proj, "raw_linked", n(9))):     # G's link removed ...
            os.remove(os.path.join(proj, "raw_linked", n(9), fn))
        old_merge(proj, n(9), H)          # ... and H linked there later
        q = old_merge(proj, n(10), Q)
        write(os.path.join(q, "notes.txt"), b"a researcher's notes")
        r_ = old_merge(proj, n(11), Rr)
        os.remove(os.path.join(r_, "recon1_frame02.dcm"))
        old_merge(proj, "ZWSI_slide.czi", P1)
        old_merge(proj, "ZWSI_slide.czi", P2)   # skipped silently
        old_merge(proj, "ZWSI_slide.czi", P3)   # skipped silently
        old_merge(proj, "ZWSI_Lipo_1.czi", L1)
        old_merge(proj, "ZWSI_lipo_1.czi", L2)  # Windows: the same name -> skipped silently ...
        for acq, nm in (("ACQ-20260710-ZWSI-004", "ZWSI_Lipo_1.czi"), ("ACQ-20260710-ZWSI-005", "ZWSI_lipo_1.czi")):
            provenance.append_entry(os.path.join(proj, "provenance.csv"), {   # ... yet both get a row
                "output_path": f"raw_linked/{nm}", "output_name": nm, "file_type": "hardlink",
                "input_refs": acq})

        print("audit")
        quiet = io.StringIO()
        with contextlib.redirect_stdout(quiet):
            results, polluted, per = R.audit(nas, log=lambda *a, **k: None)
        cls = {x["acq_id"]: x["class"] for x in results}
        want = {"ACQ-20260710-MRI-001": "OK", "ACQ-20260710-MRI-002": "MISSING",
                "ACQ-20260710-MRI-003": "POLLUTED", "ACQ-20260710-MRI-004": "MISSING",
                "ACQ-20260710-MRI-005": "OK", "ACQ-20260710-MRI-006": "RESEARCHER-PRUNED",
                "ACQ-20260710-MRI-007": "RESEARCHER-PRUNED", "ACQ-20260710-MRI-008": "OK",
                "ACQ-20260710-MRI-009": "OK-EXTRA", "ACQ-20260710-MRI-010": "PARTIAL-OWN",
                "ACQ-20260710-MRI-011": "PENDING-LINK", "ACQ-20260710-MRI-012": "CLOSED-PROJECT",
                "ACQ-20260710-ZWSI-001": "OK", "ACQ-20260710-ZWSI-002": "MISSING",
                "ACQ-20260710-ZWSI-003": "MISSING", "ACQ-20260710-MRI-013": "EMPTY-PRIMARY",
                "ACQ-20260710-ZWSI-004": "OK"}
        if sys.platform == "win32":
            want["ACQ-20260710-ZWSI-005"] = "MISSING"
        for acq, c in want.items():
            check(cls.get(acq) == c, f"{acq} -> {c} (got {cls.get(acq)})")
        by = {x["acq_id"]: x for x in results}
        check(by["ACQ-20260710-MRI-003"]["partners"] == "ACQ-20260710-MRI-004", "C's partner is D")
        check(by["ACQ-20260710-MRI-002"]["partners"] == "ACQ-20260710-MRI-001", "B's partner is A")
        check(len(polluted) == 1 and polluted[0]["link"] == n(5)
              and polluted[0]["complete_for"] == "ACQ-20260710-MRI-003"
              and polluted[0]["missing_victims"] == "ACQ-20260710-MRI-004",
              "one polluted folder: C's, holding D's files")
        check(by["ACQ-20260710-MRI-013"]["partners"] == "ACQ-20260710-MRI-005",
              "the empty-primary acquisition names E as the holder of its planned name")
        n_missing = 5 if sys.platform == "win32" else 4
        check(per["PROJ-0001"][1]["MISSING"] == n_missing and per["PROJ-0002"][1]["CLOSED-PROJECT"] == 1,
              "per-project counts")

        print("repair: dry run")
        before = sorted(os.listdir(os.path.join(proj, "raw_linked")))
        prov_before = open(os.path.join(proj, "provenance.csv"), "rb").read()
        plan = R.plan_repair(nas, results)
        act = {x["acq_id"]: (x["action"], x.get("new_link", "")) for x in plan}
        check(act.get("ACQ-20260710-MRI-002") == ("create", "MRI_m12_1125_20260710_1308_2_1"),
              f"B planned under the new convention with ITS study time (got {act.get('ACQ-20260710-MRI-002')})")
        check(act.get("ACQ-20260710-MRI-004") == ("create", "MRI_m12_1125_20260710_1308_5_1"),
              "D planned under the new convention")
        check(act.get("ACQ-20260710-ZWSI-002", ("",))[0] == "blocked",
              "the microscopy victim is blocked (no new convention outside MRI): a decision")
        plan_fp = R.plan_repair(nas, results, include_file_primaries=True)
        act_fp = {x["acq_id"]: (x["action"], x.get("new_link", "")) for x in plan_fp}
        check(act_fp.get("ACQ-20260710-ZWSI-002") == ("create", "ZWSI_slide_20260710.czi"),
              f"--include-file-primaries: P2 gets the dated name (got {act_fp.get('ACQ-20260710-ZWSI-002')})")
        check(act_fp.get("ACQ-20260710-ZWSI-003") == ("create", "ZWSI_slide_ACQ-20260710-ZWSI-003.czi"),
              f"... and P3, same day, falls back to the ACQ-ID name (got {act_fp.get('ACQ-20260710-ZWSI-003')})")
        check(sorted(os.listdir(os.path.join(proj, "raw_linked"))) == before
              and open(os.path.join(proj, "provenance.csv"), "rb").read() == prov_before,
              "the dry run wrote nothing")

        print("repair: execute")
        with tempfile.TemporaryDirectory() as bk:
            made, errors = R.execute_repair(nas, plan, "test", backup_root=bk,
                                            log=lambda *a, **k: None, regenerate_index=False)
            check((made, errors) == (2, 0), f"2 links made, 0 errors (got {made}, {errors})")
            check(any(f.endswith("provenance.csv") for d in os.listdir(bk)
                      for f in os.listdir(os.path.join(bk, d))), "provenance backed up first")
        for acq, d in (("ACQ-20260710-MRI-002", B), ("ACQ-20260710-MRI-004", D)):
            st = linker.inspect_link_target(proj, act[acq][1], d)[0]
            check(st == linker.LINK_OWN, f"{acq}'s new link is exactly its files")
        after = set(os.listdir(os.path.join(proj, "raw_linked")))
        check(set(before) <= after and len(after) == len(before) + 2, "additive: nothing removed or renamed")
        check(len(os.listdir(os.path.join(proj, "raw_linked", n(5)))) == 15,
              "C's polluted folder is left exactly as it was (removal is Ryan's decision)")
        prov = list(csv.DictReader(open(os.path.join(proj, "provenance.csv"), encoding="utf-8")))
        check(sum(1 for p in prov if "Link-collision repair" in (p.get("process_description") or "")) == 2,
              "one provenance row per repaired link")

        print("re-audit and re-run")
        with contextlib.redirect_stdout(io.StringIO()):
            results2, polluted2, _ = R.audit(nas, log=lambda *a, **k: None)
        cls2 = {x["acq_id"]: x["class"] for x in results2}
        check(cls2["ACQ-20260710-MRI-002"] == "OK" and cls2["ACQ-20260710-MRI-004"] == "OK",
              "B and D now audit OK")
        check(cls2["ACQ-20260710-MRI-003"] == "POLLUTED", "C is still listed POLLUTED")
        plan2 = R.plan_repair(nas, results2)
        check(all(x["action"] == "blocked" for x in plan2) and len(plan2) == n_missing - 2,
              "a second repair plans nothing new (only the blocked file-primary victims remain)")

        print("prune-foreign")
        # A second polluted folder: M1 (2 frames), then M2 (4 frames, the same name) -> M2's frames
        # 3-4 sit in M1's folder; M2 has NO link of its own yet; plus a researcher's note in it.
        M1 = mri("ACQ-20260710-MRI-014", STUDY1, 20, 2)
        M2 = mri("ACQ-20260710-MRI-015", STUDY2, 20, 4)
        with open(os.path.join(reg, "registry_raw.csv"), "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=registry.REGISTRY_FIELDS, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow(r)
        old_merge(proj, n(20), M1)
        old_merge(proj, n(20), M2)
        write(os.path.join(proj, "raw_linked", n(20), "notes.txt"), b"a researcher's note")
        cdir, ddir = os.path.join(proj, "raw_linked", n(5)), os.path.join(proj, "raw_linked", act["ACQ-20260710-MRI-004"][1])
        c_ids = {os.stat(os.path.join(C, f)).st_ino for f in os.listdir(C)}
        d_link_before = R.tree_names(ddir)
        with contextlib.redirect_stdout(io.StringIO()):
            res3, pol3, _ = R.audit(nas, log=lambda *a, **k: None)
        check(sorted(p["link"] for p in pol3) == sorted([n(5), n(20)]), "two polluted folders")
        pplan = R.plan_prune(nas, res3, pol3)
        rm = [x for x in pplan if x["action"] == "remove"]
        keep = [x for x in pplan if x["action"] == "keep"]
        check(len(rm) == 12 and all(x["folder"] == n(5) and x["file_owner"] == "ACQ-20260710-MRI-004"
                                    for x in rm), "12 removals planned: D's names in C's folder")
        check(sorted(x["name"] for x in keep) == ["notes.txt", "recon1_frame03.dcm", "recon1_frame04.dcm"],
              "kept: M2's names (M2 has no link of its own yet) and the researcher's note")
        check(not any(x.get("file_id") in c_ids for x in pplan), "the owner's files are never in the plan")
        check(len(os.listdir(cdir)) == 15, "planning wrote nothing")
        with tempfile.TemporaryDirectory() as bk:
            removed, errors, verified, checked = R.execute_prune(
                nas, pplan, "test", backup_root=bk, log=lambda *a, **k: None, regenerate_index=False)
            check((removed, errors) == (12, 0), f"12 names removed, 0 errors (got {removed}, {errors})")
            check((verified, checked) == (1, 2), f"C's folder verified; M1's not, as expected (got {verified}/{checked})")
            check(any(f == "prune_manifest.csv" for d in os.listdir(bk) for f in os.listdir(os.path.join(bk, d))),
                  "the manifest of names is backed up before any removal")
        check(linker.inspect_link_target(proj, n(5), C)[0] == linker.LINK_OWN,
              "C's folder is now exactly C's files")
        check({os.stat(os.path.join(cdir, f)).st_ino for f in os.listdir(cdir)} == c_ids,
              "every one of C's own files is still there")
        check(R.tree_names(ddir) == d_link_before and all(os.path.isfile(os.path.join(D, f)) for f in os.listdir(D)),
              "D keeps every file in /raw/ and in its own link (never the last name)")
        check(len(os.listdir(os.path.join(proj, "raw_linked", n(20)))) == 5, "M1's folder untouched")
        prov = list(csv.DictReader(open(os.path.join(proj, "provenance.csv"), encoding="utf-8")))
        ev = [p for p in prov if p.get("file_type") == "hardlink-removed"]
        check(len(ev) == 1 and ev[0]["output_path"] == f"raw_linked/{n(5)}"
              and ev[0]["input_refs"] == "ACQ-20260710-MRI-004", "one provenance event, for C's folder")

        print("prune-foreign: after M2 gets its own link")
        with contextlib.redirect_stdout(io.StringIO()):
            res4, _p, _ = R.audit(nas, log=lambda *a, **k: None)
        with tempfile.TemporaryDirectory() as bk:
            R.execute_repair(nas, [x for x in R.plan_repair(nas, res4) if x["acq_id"] == "ACQ-20260710-MRI-015"],
                             "test", backup_root=bk, log=lambda *a, **k: None, regenerate_index=False)
        with contextlib.redirect_stdout(io.StringIO()):
            res5, pol5, _ = R.audit(nas, log=lambda *a, **k: None)
        pplan5 = R.plan_prune(nas, res5, pol5)
        check(sorted((x["action"], x["name"]) for x in pplan5) ==
              [("keep", "notes.txt"), ("remove", "recon1_frame03.dcm"), ("remove", "recon1_frame04.dcm")],
              "now M2's two names are removable; the note never is")
        with tempfile.TemporaryDirectory() as bk:
            removed, errors, verified, checked = R.execute_prune(
                nas, pplan5, "test", backup_root=bk, log=lambda *a, **k: None, regenerate_index=False)
        check((removed, errors) == (2, 0), "M2's 2 names removed")
        with contextlib.redirect_stdout(io.StringIO()):
            res6, pol6, _ = R.audit(nas, log=lambda *a, **k: None)
        cls6 = {x["acq_id"]: x["class"] for x in res6}
        check(pol6 == [] and cls6["ACQ-20260710-MRI-003"] == "OK" and cls6["ACQ-20260710-MRI-014"] == "OK-EXTRA",
              "POLLUTED 0: C is OK, M1 is OK-EXTRA (the researcher's note stays)")
        n_events = sum(1 for p in csv.DictReader(open(os.path.join(proj, "provenance.csv"), encoding="utf-8"))
                       if p.get("file_type") == "hardlink-removed")
        with tempfile.TemporaryDirectory() as bk:
            again = R.execute_prune(nas, R.plan_prune(nas, res6, pol6), "test", backup_root=bk,
                                    log=lambda *a, **k: None, regenerate_index=False)
        check(again[:2] == (0, 0) and n_events == 2 and sum(
              1 for p in csv.DictReader(open(os.path.join(proj, "provenance.csv"), encoding="utf-8"))
              if p.get("file_type") == "hardlink-removed") == 2, "a re-run removes nothing and adds no event")

        print("a repaired link a researcher later deletes is never re-made")
        b_link = os.path.join(proj, "raw_linked", act["ACQ-20260710-MRI-002"][1])
        for f in os.listdir(b_link):
            os.remove(os.path.join(b_link, f))
        os.rmdir(b_link)
        with contextlib.redirect_stdout(io.StringIO()):
            res7, _p, _ = R.audit(nas, log=lambda *a, **k: None)
        cls7 = {x["acq_id"]: x["class"] for x in res7}
        check(cls7["ACQ-20260710-MRI-002"] == "RESEARCHER-PRUNED", f"B is RESEARCHER-PRUNED (got {cls7['ACQ-20260710-MRI-002']})")
        check("ACQ-20260710-MRI-002" not in {x["acq_id"] for x in R.plan_repair(nas, res7)}, "... and not re-planned")

        print("reopen_project ignores removal events")
        import reopen_project
        names = reopen_project.link_names_from_provenance([os.path.join(proj, "provenance.csv")])
        check(names.get("ACQ-20260710-MRI-004") == act["ACQ-20260710-MRI-004"][1],
              "D's link name is its own repaired link, not C's folder named in the removal event")

    print()
    if FAILED:
        print(f"{len(FAILED)} CHECK(S) FAILED")
        for m in FAILED:
            print("  -", m)
        sys.exit(1)
    print("ALL LINK-REPAIR CHECKS PASSED")


if __name__ == "__main__":
    main()
