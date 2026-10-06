"""Stream M, part 2, step 1: the CNIC pig images, every DICOM header read (read-only).

    python mri_20_pig_probe.py --plan      # out\\plan_stage_files_pig.csv, then: mri_02_stage.py <that file>
    python mri_20_pig_probe.py             # the probe, reading the STAGED copy on D: (stage\\PIG\\)

Reads, with pydicom (stop_before_pixels), the staged copy (D:, hash-checked against the drive manifest) of every
image file under
  Otros\\Segmentaciones ITK SNAP\\Segmentaciones Arteria Pulmonar cerdos\\Imágenes\\RL\\<series folder>\\
of the staged drive copy (27 series folders: a DICOMDIR, DICOM\\IM_<n>, and a Split\\ of MetaImage volumes).
Settles the row unit (BACKLOG: "external collaborator archives are one row per EXAM, not per series"): how many
studies, series and instances each folder holds, whether two folders hold the same bytes, and the header fields a
sidecar would carry. **No identifier is written**: PatientName / PatientID / PatientBirthDate are reduced to flags
(does the value look like the pig code of the folder; is it a human-looking name). A header that suggests human data
is a STOP (HANDOFF: "No human data is expected (pigs); if a header suggests otherwise, stop and report").
Writes out\\pig_series.csv, out\\pig_files.csv, out\\pig_probe.txt.
"""
import collections
import os
import re
import sys

import pydicom

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mri_common as C  # noqa: E402

PIG = "Otros\\Segmentaciones ITK SNAP\\Segmentaciones Arteria Pulmonar cerdos"
RL = PIG + "\\Imágenes\\RL"
TAGS = ["SOPClassUID", "SOPInstanceUID", "StudyInstanceUID", "SeriesInstanceUID", "SeriesNumber", "AcquisitionNumber",
        "InstanceNumber", "Modality", "ImageType", "StudyDate", "StudyTime", "SeriesDate", "SeriesTime",
        "AcquisitionDate", "AcquisitionTime", "ContentDate", "SeriesDescription", "ProtocolName", "StudyDescription",
        "BodyPartExamined", "Manufacturer", "ManufacturerModelName", "InstitutionName", "StationName",
        "MagneticFieldStrength", "SoftwareVersions", "PatientName", "PatientID", "PatientBirthDate", "PatientSex",
        "PatientAge", "PatientWeight", "PatientSpeciesDescription", "PatientBreedDescription", "Rows", "Columns",
        "NumberOfFrames", "EchoTime", "RepetitionTime"]


def s(v):
    return "" if v is None else str(v).strip()


def plan():
    """out\\plan_stage_files_pig.csv: every file of the 27 series folders except Split\\ (derived MetaImage volumes,
    which stay project material), staged flat as stage\\PIG\\<series folder>\\<inner path>."""
    man = C.manifest_under([RL])
    files = []
    for rel, (size, sha) in sorted(man.items()):
        sub = rel[len(RL) + 1:]
        if "\\" not in sub or sub.split("\\")[1] == "Split":
            continue
        files.append({"batch": "PIG", "exam_key": sub.split("\\", 1)[0], "drive_relpath": rel,
                      "staged_rel": "PIG\\" + sub, "size": size, "sha256": sha})
    C.write_csv(C.out("plan_stage_files_pig.csv"), files)
    print(f"pig files to stage: {len(files)}, {sum(f['size'] for f in files) / 1e9:.2f} GB; not staged (top-level "
          f"or Split): {len(man) - len(files)}")


def main():
    if "--plan" in sys.argv:
        return plan()
    man = C.manifest_under([RL])
    by_folder = collections.defaultdict(list)
    for rel, (size, sha) in man.items():
        sub = rel[len(RL) + 1:]
        if "\\" not in sub:
            continue
        folder = sub.split("\\", 1)[0]
        by_folder[folder].append((rel, size, sha))
    series_rows, file_rows, flags = [], [], collections.Counter()
    sha_owner = collections.defaultdict(set)
    for folder in sorted(by_folder):
        pig_code = re.match(r"HEARDSMRI(\d+)P_(\d+)_(\d+)", folder)
        per = collections.defaultdict(set)
        first = None
        n_dcm = n_dicomdir = n_split = n_other = 0
        bytes_dcm = 0
        for rel, size, sha in sorted(by_folder[folder]):
            inner = rel[len(RL) + 1 + len(folder) + 1:]
            kind = ("split" if inner.startswith("Split\\") else "dicomdir" if inner.upper() == "DICOMDIR"
                    else "image" if inner.startswith("DICOM\\") else "other")
            rec = {"folder": folder, "inner": inner, "kind": kind, "size": size, "sha256": sha}
            if kind == "image":
                sha_owner[sha].add(folder)
                ds = pydicom.dcmread(C.lp(os.path.join(C.STAGE, "PIG", folder, inner)), stop_before_pixels=True,
                                     force=True, specific_tags=TAGS)
                for t in ("StudyInstanceUID", "SeriesInstanceUID", "SeriesNumber", "SOPClassUID", "Modality",
                          "SeriesDescription", "ProtocolName", "StudyDate", "SeriesDate", "AcquisitionNumber"):
                    per[t].add(s(getattr(ds, t, None)))
                per["ImageType"].add("\\".join(getattr(ds, "ImageType", []) or []))
                rec["sop"] = s(getattr(ds, "SOPInstanceUID", None))
                rec["instance"] = s(getattr(ds, "InstanceNumber", None))
                if first is None:
                    first = ds
                n_dcm += 1
                bytes_dcm += size
            elif kind == "dicomdir":
                n_dicomdir += 1
            elif kind == "split":
                n_split += 1
            else:
                n_other += 1
            file_rows.append(rec)
        # identity flags, never values
        pn, pid, pbd = s(getattr(first, "PatientName", None)), s(getattr(first, "PatientID", None)), s(getattr(first, "PatientBirthDate", None))
        code = pig_code.group(1) if pig_code else "?"
        def looks_pig(v):
            return bool(v) and (code in v or "HEARDS" in v.upper() or re.search(r"cerd|pig|porc", v, re.I) is not None)
        human_name = bool(pn) and not looks_pig(pn) and re.search(r"[A-Za-z]{3,}\^[A-Za-z]{3,}", pn) is not None
        species = s(getattr(first, "PatientSpeciesDescription", None))
        if human_name or (species and not re.search(r"sus|pig|porc|cerd", species, re.I)):
            flags["HUMAN-SUGGESTED"] += 1
        sop = [r["sop"] for r in file_rows if r["folder"] == folder and r["kind"] == "image"]
        series_rows.append({
            "folder": folder, "pig": code, "session": pig_code.group(2) if pig_code else "",
            "series_in_name": pig_code.group(3) if pig_code else "",
            "n_image_files": n_dcm, "image_bytes": bytes_dcm, "n_dicomdir": n_dicomdir, "n_split": n_split,
            "n_other": n_other, "n_study_uid": len(per["StudyInstanceUID"]), "n_series_uid": len(per["SeriesInstanceUID"]),
            "n_sop_unique": len(set(sop)), "series_numbers": ";".join(sorted(per["SeriesNumber"])),
            "acq_numbers": len(per["AcquisitionNumber"]), "sop_classes": ";".join(sorted(per["SOPClassUID"])),
            "modality": ";".join(sorted(per["Modality"])), "image_types": len(per["ImageType"]),
            "series_description": ";".join(sorted(per["SeriesDescription"])),
            "protocol": ";".join(sorted(per["ProtocolName"])), "study_dates": ";".join(sorted(per["StudyDate"])),
            "series_dates": ";".join(sorted(per["SeriesDate"])),
            "series_time": s(getattr(first, "SeriesTime", None)), "study_time": s(getattr(first, "StudyTime", None)),
            "acq_date": s(getattr(first, "AcquisitionDate", None)), "acq_time": s(getattr(first, "AcquisitionTime", None)),
            "study_description": s(getattr(first, "StudyDescription", None)),
            "body_part": s(getattr(first, "BodyPartExamined", None)),
            "manufacturer": s(getattr(first, "Manufacturer", None)), "model": s(getattr(first, "ManufacturerModelName", None)),
            "institution": s(getattr(first, "InstitutionName", None)), "station": s(getattr(first, "StationName", None)),
            "field_t": s(getattr(first, "MagneticFieldStrength", None)), "software": s(getattr(first, "SoftwareVersions", None)),
            "patient_name_is_pig_code": looks_pig(pn), "patient_name_human_like": human_name,
            "patient_id_is_pig_code": looks_pig(pid), "patient_birthdate_present": bool(pbd),
            "patient_sex": s(getattr(first, "PatientSex", None)), "patient_age": s(getattr(first, "PatientAge", None)),
            "patient_weight": s(getattr(first, "PatientWeight", None)), "species_tag": species,
            "breed_tag": s(getattr(first, "PatientBreedDescription", None)),
            "rows_cols": f"{s(getattr(first, 'Rows', None))}x{s(getattr(first, 'Columns', None))}",
            "frames": s(getattr(first, "NumberOfFrames", None)),
        })
        print(folder, n_dcm, "study_uids", len(per["StudyInstanceUID"]), "series_uids", len(per["SeriesInstanceUID"]),
              flush=True)
    # cross-folder byte duplicates of image files
    shared = collections.Counter()
    for sha, owners in sha_owner.items():
        if len(owners) > 1:
            shared[tuple(sorted(owners))] += 1
    C.write_csv(C.out("pig_series.csv"), series_rows)
    C.write_csv(C.out("pig_files.csv"), file_rows,
                ["folder", "inner", "kind", "size", "sha256", "sop", "instance"])
    study_uids = collections.Counter()
    L = [f"series folders {len(series_rows)}; image files {sum(r['n_image_files'] for r in series_rows)} "
         f"({sum(r['image_bytes'] for r in series_rows) / 1e9:.2f} GB); DICOMDIR {sum(r['n_dicomdir'] for r in series_rows)}; "
         f"Split files {sum(r['n_split'] for r in series_rows)}; other {sum(r['n_other'] for r in series_rows)}",
         f"folders with >1 SeriesInstanceUID: {[r['folder'] for r in series_rows if r['n_series_uid'] != 1]}",
         f"folders with >1 StudyInstanceUID: {[r['folder'] for r in series_rows if r['n_study_uid'] != 1]}",
         f"folders where SOP UIDs repeat: {[r['folder'] for r in series_rows if r['n_sop_unique'] != r['n_image_files']]}",
         f"image files whose bytes occur in more than one folder: {sum(shared.values())} {dict(shared)}",
         f"HUMAN-SUGGESTED: {flags['HUMAN-SUGGESTED']}",
         f"patient name looks like the pig code: {collections.Counter(r['patient_name_is_pig_code'] for r in series_rows)}; "
         f"patient id: {collections.Counter(r['patient_id_is_pig_code'] for r in series_rows)}; birth date present: "
         f"{collections.Counter(r['patient_birthdate_present'] for r in series_rows)}",
         f"species tag: {collections.Counter(r['species_tag'] for r in series_rows)}; sex {collections.Counter(r['patient_sex'] for r in series_rows)}",
         f"models: {collections.Counter((r['manufacturer'], r['model'], r['field_t'], r['institution']) for r in series_rows)}",
         f"descriptions: {collections.Counter((r['series_description'], r['protocol']) for r in series_rows)}"]
    open(C.out("pig_probe.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
