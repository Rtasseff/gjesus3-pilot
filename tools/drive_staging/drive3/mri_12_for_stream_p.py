"""Stream M: the raw MRI on the drive that stream M does NOT register, handed to stream P (read-only).

    python mri_12_for_stream_p.py

Ryan's 2026-10-04 rule registers MRI only with DICOM; what has none, and what /raw/ will not hold, must not be lost when
the staged copy goes (drive3_production_plan.md, close-out 3). Stream P places it as other data with a README (its
second batch). One row per FILE, with the reason:
  not-registered:<class>     every file of the 71 exams of class (e) (spectroscopy, k-space without reconstruction,
                             never acquired), every copy
  recon-without-dicom        the pdata\\<idx>\\ folder of a registered exam whose reconstruction has a 2dseq but no DICOM
                             (/raw/ stores the DICOM reconstructions only)
  divergent-copy             a second copy of a registered exam that differs from the registered one (m175 / m178: the
                             other reconstruction; jrc200305_m34_flow/4: another rawdata.job1); k-space included
  ...-after-convert          an exam of class (d) whose conversion failed (out\\not_registered_after_convert.csv)
`already_held` = Y when the drives 1+2 holding folder holds the same bytes (its manifest, by SHA-256).
Writes out\\for_stream_P.csv and out\\for_stream_P_summary.txt.
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mri_common as C  # noqa: E402

HOLDING_MANIFEST = os.path.join(C.NAS, "staging", "historical_drives_unassigned", "manifest.csv")


def main():
    plan = C.rows(os.path.join(C.OUT, "plan_exams.csv"))
    cp = collections.defaultdict(list)
    for r in C.rows(os.path.join(C.A1, "mri_exam_copies.csv")):
        cp[r["exam_key"]].append(r)
    after = C.rows(os.path.join(C.OUT, "not_registered_after_convert.csv"))
    nodcm = C.rows(os.path.join(C.OUT, "recon_no_dicom.csv"))
    held = {r["sha256"] for r in C.rows(HOLDING_MANIFEST)}
    want = []                                   # (drive dir prefix, reason, original_name, file filter)
    for p in plan:
        if p["disposition"] != "register":
            for c in cp[p["exam_key"]]:
                want.append((c["exam_dir"], f"not-registered:{p['class_detail']}", p["original_name"], None))
        else:
            for c in cp[p["exam_key"]]:
                if c["exam_dir"] != p["drive_exam_dir"] and c["vs_canonical"].startswith("divergent") or (
                        c["exam_dir"] != p["drive_exam_dir"] and p["study"] in (
                        "20210902_082356_jrc210902_m175_ermal_1_1", "20210902_115741_jrc210902_m178_ermal_1_1")):
                    want.append((c["exam_dir"], "divergent-copy (another reconstruction or k-space of a registered exam)",
                                 p["original_name"], None))
    for a in after:
        for c in cp[a["exam_key"]]:
            want.append((c["exam_dir"], f"not-registered-after-convert: {a['reason']}", a["original_name"], None))
    for n in nodcm:
        for idx in n["recons_without_dicom"].split(";"):
            want.append((n["drive_exam_dir"] + f"\\pdata\\{idx}", "recon-without-dicom (2dseq only; /raw/ keeps DICOM)",
                         n["original_name"], None))
    tops = sorted({w[0].split("\\", 1)[0] for w in want})
    man = C.manifest_under(tops)
    prefixes = {}
    for d, why, on, _ in want:
        prefixes.setdefault(d, (why, on))
    rows_ = []
    for rel, (size, sha) in man.items():
        head = rel
        while "\\" in head:
            head = head.rsplit("\\", 1)[0]
            if head in prefixes:
                why, on = prefixes[head]
                rows_.append({"drive_relpath": rel, "size": size, "sha256": sha, "reason": why, "original_name": on,
                              "already_held": "Y" if sha in held else "N"})
                break
    # part 2: the pig folder's files that are neither registered (P01) nor derived Split\ volumes
    for r in C.rows(os.path.join(C.OUT, "pig_not_registered.csv")):
        rows_.append({"drive_relpath": r["drive_relpath"], "size": int(r["size"]), "sha256": r["sha256"],
                      "reason": f"pig-export: {r['why']} (to CNIC-HEARDS with the masks; not junk)",
                      "original_name": r["folder"], "already_held": "Y" if r["sha256"] in held else "N"})
    C.write_csv(C.out("for_stream_P.csv"), rows_)
    by = collections.defaultdict(lambda: [0, 0, 0, set()])
    for r in rows_:
        k = r["reason"].split(":")[0].split(" (")[0]
        by[k][0] += 1
        by[k][1] += r["size"]
        by[k][2] += r["already_held"] == "Y"
        by[k][3].add(r["original_name"])
    L = [f"{len(rows_)} files, {sum(r['size'] for r in rows_) / 1e9:.2f} GB, from {len(prefixes)} folders"]
    for k, v in sorted(by.items()):
        L.append(f"  {k}: {v[0]} files, {v[1] / 1e9:.3f} GB, {len(v[3])} exams; already in the drives 1+2 holding "
                 f"folder by SHA-256: {v[2]} files")
    open(C.out("for_stream_P_summary.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
