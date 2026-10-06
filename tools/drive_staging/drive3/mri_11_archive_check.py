"""Stream M: the list for the later check against the MRI platform's archive (BACKLOG, Ryan's M2).

    python mri_11_archive_check.py [<nas_root>]

One row per registered exam (from the case tables and the staged exams; with <nas_root>, the ACQ-ID each was given,
looked up by original_name): study, exam, project, the drive copy it came from and every other copy on the drive, how
its DICOM was made, the DICOM count, and a digest of its DICOM set (SHA-256 over the sorted lines
"<production file name> <sha256>", so one value per exam matches checksums.json in /raw/). A later compare against the
archive's copy decides per exam: bytes equal, pixels equal (a re-export, A1 2.2), or different.
Writes tasks/drive3_mri_for_archive_check.csv (in the worktree) and out\\archive_check_summary.txt.
"""
import collections
import glob
import hashlib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mri_common as C  # noqa: E402

DCM_RE = re.compile(r"^MRIm(?P<n>\d+)\.dcm$", re.I)
BATCHES = ["M01", "M02", "M03", "M04", "M05", "M06", "M07", "M08", "M09"]


def main():
    nas = sys.argv[1] if len(sys.argv) > 1 else None
    plan = {p["original_name"]: p for p in C.rows(os.path.join(C.OUT, "plan_exams.csv"))}
    copies = collections.defaultdict(list)
    for r in C.rows(os.path.join(C.A1, "mri_exam_copies.csv")):
        copies[r["exam_key"]].append(r["exam_dir"])
    stage_sha = {os.path.join(C.STAGE, r["staged_rel"]): r["sha256"] for r in C.rows(os.path.join(C.OUT, "stage_result.csv"))}
    acq = {}
    if nas:
        for r in C.live_registry(nas):
            acq[r["original_name"].replace("\\", "/")] = r["acq_id"]
    out = []
    for b in BATCHES:
        p_ = os.path.join(C.CFG_DIR, f"cases_{b}.csv")
        if not os.path.exists(p_):
            continue
        for c in C.rows(p_):
            p = plan[c["original_name"]]
            lines, n = [], 0
            for f in sorted(glob.glob(os.path.join(C.STAGE, b, p["study"], p["exam"], "pdata", "*", "dicom", "*.dcm"))):
                idx = f.split(os.sep)[-3]
                m = DCM_RE.match(os.path.basename(f))
                name = f"recon{idx}_frame{m.group('n').zfill(2)}.dcm" if m else f"recon{idx}_{os.path.basename(f)}"
                lines.append(f"{name} {stage_sha.get(f) or C.sha256(f)}")
                n += 1
            digest = hashlib.sha256("\n".join(sorted(lines)).encode()).hexdigest()
            out.append({"study": p["study"], "exam": p["exam"], "original_name": p["original_name"],
                        "acq_id": acq.get(p["original_name"], ""), "batch": b, "project": p["project_name"],
                        "acq_datetime": c["drv_acq_datetime"], "scanner": p["model"], "method": p["method"],
                        "dicom_origin": "scanner" if p["class"] == "c" else "dicomifier", "n_dicom": n,
                        "dicom_set_sha256": digest, "drive_copy": p["drive_exam_dir"],
                        "other_drive_copies": " | ".join(x for x in copies[p["exam_key"]] if x != p["drive_exam_dir"]),
                        "archive_result": ""})
    path = os.path.join(C.WT, "tasks", "drive3_mri_for_archive_check.csv")
    C.write_csv(path, out)
    s = (f"{len(out)} exams in {len({o['study'] for o in out})} studies; with an ACQ-ID: {sum(1 for o in out if o['acq_id'])}; "
         f"origin {dict(collections.Counter(o['dicom_origin'] for o in out))}; written {path}")
    open(C.out("archive_check_summary.txt"), "w", encoding="utf-8").write(s + "\n")
    print(s)


if __name__ == "__main__":
    main()
