"""Stream M -> the second placement batch P2 (coordinator, 2026-10-06): the input lists for stream P's tool (read-only).

    python mri_16_p2_lists.py

From out\\for_stream_P.csv (mri_12_for_stream_p.py: what stream M does not register) writes, in out\\p2\\:
  p2a_handover.csv   the MRI files, for `p_plan.py handover`: kind notregistered:<no-recon|non-image> for the 71 exams
                     (never-acquired exams count as no-recon: parameter files, no image), `other` for the 2dseq-only
                     reconstructions and the divergent copies; project = the exam's (plan_exams.csv), except the 2021
                     `1019` MRS sessions, which go to holding as their image exams carry no project (STATUS D6), and
                     M08's study (no project).
                     LEFT OUT: a file whose bytes stream M registers (a divergent copy shares DICOM with the registered
                     reconstruction): after the write they are in /raw/, and raw is never placed.
  p2b_handover.csv   the 31 pig-folder files for CNIC-HEARDS (27 DICOMDIR + 4 MATLAB files named *.cache, the latter
                     with keep_despite_name=Y: taken by path, not by name)
  p2b_mapping.csv    a 2b worksheet with one row per group key of the pig set's holding rows in stream P's executed
                     manifest, project CNIC-HEARDS, for `nonraw_placement.py remap` (the masks from holding)
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mri_common as C  # noqa: E402

sys.path.insert(0, os.path.join(C.WT, "tools", "drive_staging"))
import nonraw_placement as NP  # noqa: E402

P_MANIFEST = r"D:\projects\gjesus3\drive3_streams\placement\manifest_check2_20261006\placement_manifest.csv"
PIG = "Otros\\Segmentaciones ITK SNAP\\Segmentaciones Arteria Pulmonar cerdos\\"
KIND = {"e-neveracquired (no k-space, no 2dseq)": "notregistered:no-recon", "e-norecon (k-space, no 2dseq)": "notregistered:no-recon",
        "e-nonimage (PRESS)": "notregistered:non-image", "e-nonimage (STEAM)": "notregistered:non-image"}


def main():
    od = os.path.join(C.OUT, "p2")
    os.makedirs(od, exist_ok=True)
    plan = {p["original_name"]: p for p in C.rows(os.path.join(C.OUT, "plan_exams.csv"))}
    # /raw/ keeps the DICOM only (copy strategy mri_paravision_v2): the staged parameter files and 2dseq are NOT raw
    registered = {r["sha256"] for r in C.rows(os.path.join(C.OUT, "stage_result.csv"))
                  if r["staged_rel"].lower().endswith(".dcm")}
    fp = C.rows(os.path.join(C.OUT, "for_stream_P.csv"))
    a, b, left = [], [], collections.Counter()
    for r in fp:
        why = r["reason"]
        if why.startswith("pig-export"):
            name = r["drive_relpath"].split("\\")[-1].lower()
            row = {"relpath": r["drive_relpath"], "kind": "other", "project": "CNIC-HEARDS", "sha256": r["sha256"],
                   "reason": ("the DICOMDIR of the exported series (its images are registered as XMRI)" if name == "dicomdir"
                              else "a MATLAB 5.0 file named " + name + " (not a cache), beside the pig series")}
            if name in ("thumbs.cache", "folders.cache"):
                row["keep_despite_name"] = "Y"
            b.append(row)
            continue
        if r["sha256"] in registered:
            left[why.split(" (")[0].split(":")[0]] += 1
            continue
        p = plan[r["original_name"]]
        proj = p["project_name"]
        if p["protocol"] == "1019" and p["year"] == "2021":
            proj = ""
        if why.startswith("not-registered:"):
            kind, reason = KIND[p["class_detail"]], f"{p['class_detail']}; exam {p['original_name']}"
        elif why.startswith("recon-without-dicom"):
            kind, reason = "other", f"reconstruction without DICOM (2dseq only) of registered exam {p['original_name']}"
        else:
            kind, reason = "other", f"another copy of registered exam {p['original_name']} that differs from it"
        a.append({"relpath": r["drive_relpath"], "kind": kind, "project": proj, "reason": reason, "sha256": r["sha256"]})
    fields = ["relpath", "kind", "project", "reason", "parent_acq_ids", "sha256", "keep_despite_name"]
    C.write_csv(os.path.join(od, "p2a_handover.csv"), a, fields)
    C.write_csv(os.path.join(od, "p2b_handover.csv"), b, fields)
    # the masks: stream P's executed manifest, the pig set's holding rows -> their 2b group keys
    # A 2b mapping moves a whole GROUP. A key that also holds files outside the pig folder is left out (the
    # no-claim key `Otros\Segmentaciones ITK SNAP` also holds two mouse London segmentations): its pig files stay
    # in holding, listed in p2b_unmapped_pig.csv for the coordinator.
    keys, other = collections.Counter(), collections.Counter()
    pig_rows = collections.defaultdict(list)
    for r in C.rows(P_MANIFEST):
        if r["decision"] == "holding" and NP.mappable(r["reason"]):
            d, who, series, _k = NP.manifest_group(r)
            k = NP.key_string(d, who, series)
            if r["relpath"].startswith(PIG):
                keys[k] += 1
                pig_rows[k].append(r)
            else:
                other[k] += 1
    pure = {k: n for k, n in keys.items() if not other[k]}
    mixed = {k: (n, other[k]) for k, n in keys.items() if other[k]}
    m = [{"group": f"P2-{i}", "project": "CNIC-HEARDS", "note_for_ryan": "stream M P2: the pig set into CNIC-HEARDS",
          "nonraw_files": n, "group_key": k} for i, (k, n) in enumerate(sorted(pure.items()), 1)]
    C.write_csv(os.path.join(od, "p2b_mapping.csv"), m, NP.WORKSHEET_FIELDS)
    C.write_csv(os.path.join(od, "p2b_unmapped_pig.csv"),
                [{"group_key": k, "relpath": r["relpath"], "size": r["size"], "sha256": r["sha256"]}
                 for k in mixed for r in pig_rows[k]], ["group_key", "relpath", "size", "sha256"])
    print(f"p2a: {len(a)} files {dict(collections.Counter((x['kind'], x['project'] or '(holding)') for x in a))}")
    print(f"     left out (bytes stream M registers): {dict(left)}")
    print(f"p2b: {len(b)} files ({sum(1 for x in b if x.get('keep_despite_name'))} kept despite their name)")
    print(f"masks: {sum(pure.values())} holding rows in {len(pure)} pure group keys -> CNIC-HEARDS; left in holding "
          f"(their key also holds other files): {mixed}")


if __name__ == "__main__":
    main()
