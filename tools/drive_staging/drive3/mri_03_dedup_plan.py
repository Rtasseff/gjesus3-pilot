"""Stream M, step 3: the dedup-proof set -- every exam of the drive that production ALREADY holds (read-only).

    python mri_03_dedup_plan.py

A1 found 3,965 of the drive's exams in production (classes a and b, 232 studies). This stages, for each of them, only
what the ingest's discovery reads to decide "already registered": the study's subject, the exam's acqp / method /
visu_pars and every pdata\\<idx>\\visu_pars and reco (no DICOM, no 2dseq, no k-space). The dry run of
drive3_mri_dedup_proof.yaml over this tree must then list 0 and skip every exam as "already in registry": proof that
stream M's staging (flat <study>/<exam>) and its datetime rule (visu_pars VisuCreationDate, else acqp ACQ_time) give
the same (date, original_name) key production holds, so the batches cannot register a study twice and a later ingest
of the same exam (the platform's archive) is skipped in turn.
Writes out\\plan_dedup_exams.csv and out\\plan_stage_files_dedup.csv (staged under stage\\DEDUP\\).
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mri_common as C  # noqa: E402

KEEP = {"acqp", "method", "visu_pars", "reco"}


def main():
    ex = [r for r in C.rows(os.path.join(C.A1, "mri_exams.csv")) if r["class"] in ("a", "b")]
    cp = C.rows(os.path.join(C.A1, "mri_exam_copies.csv"))
    canon = {r["exam_key"]: r["exam_dir"] for r in cp if r["canonical"] == "Y"}
    reg = C.live_registry()
    by_name = collections.defaultdict(list)
    for r in reg:
        by_name[r["original_name"].replace("\\", "/")].append(r)
    plan = []
    for e in ex:
        hits = by_name.get(f"{e['study']}/{e['exam']}", [])
        plan.append({"exam_key": e["exam_key"], "study": e["study"], "exam": e["exam"], "class_detail": e["class_detail"],
                     "drive_exam_dir": canon[e["exam_key"]], "prod_acq_ids": ";".join(h["acq_id"] for h in hits),
                     "prod_dates": ";".join(h["acquisition_datetime"][:10] for h in hits),
                     "prod_configs": ";".join(h["ingest_config"].replace("\\", "/").split("/")[-1] for h in hits)})
    dirs = {p["drive_exam_dir"]: p for p in plan}
    study_dirs = collections.defaultdict(set)
    for p in plan:
        study_dirs[p["drive_exam_dir"].rsplit("\\", 1)[0]].add(p["study"])
    man = C.manifest_under(sorted({d.split("\\", 1)[0] for d in dirs}))
    files, subj = [], {}
    for rel, (size, sha) in man.items():
        d, name = rel.rsplit("\\", 1)
        if name == "subject" and d in study_dirs:
            for s in study_dirs[d]:
                subj.setdefault(s, (rel, size, sha))
            continue
        if name not in KEEP:
            continue
        parts = rel.split("\\")
        # <exam_dir>\name  or  <exam_dir>\pdata\<idx>\name
        for head in ("\\".join(parts[:-1]), "\\".join(parts[:-3]) if len(parts) > 3 and parts[-3] == "pdata" else None):
            if head and head in dirs:
                p = dirs[head]
                files.append({"batch": "DEDUP", "exam_key": p["exam_key"], "drive_relpath": rel,
                              "staged_rel": f"DEDUP\\{p['study']}\\{p['exam']}\\{rel[len(head) + 1:]}", "size": size,
                              "sha256": sha})
                break
    for s, (rel, size, sha) in sorted(subj.items()):
        files.append({"batch": "DEDUP", "exam_key": "", "drive_relpath": rel, "staged_rel": f"DEDUP\\{s}\\subject",
                      "size": size, "sha256": sha})
    C.write_csv(C.out("plan_dedup_exams.csv"), plan)
    C.write_csv(C.out("plan_stage_files_dedup.csv"), files)
    per = collections.Counter(f["exam_key"] for f in files if f["exam_key"])
    print(f"exams {len(plan)} in {len({p['study'] for p in plan})} studies; with a production row by name now: "
          f"{sum(1 for p in plan if p['prod_acq_ids'])}; with >1 row: {sum(1 for p in plan if ';' in p['prod_acq_ids'])}; "
          f"files {len(files)} ({sum(f['size'] for f in files) / 1e6:.0f} MB); "
          f"exams with no file: {sum(1 for p in plan if not per[p['exam_key']])}; studies with subject {len(subj)}")


if __name__ == "__main__":
    main()
