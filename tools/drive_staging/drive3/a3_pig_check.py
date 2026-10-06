"""A3 step 13 -- the pig pulmonary-artery set: what instrument, when, and is the source on the drive? (read-only)

Reads ONE DICOM header per image series folder under Otros\\Segmentaciones ITK SNAP\\Segmentaciones Arteria
Pulmonar cerdos\\Imagenes\\RL\\ (the source images the ROIs were drawn on) and reports scanner, site, field
strength, study date, series description and whether PatientID equals the folder's 'HEARDSMRI<pig>P' token.
Identifiers are compared in code and NEVER written out (the animals are pigs, but the rule is the rule).
Also measures the ROI-folder -> image-folder pairing (series number + 3) and the split-volume geometry.
Output: a3_pig_series.csv
"""
import os
import re
import sys
from collections import Counter, defaultdict

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a3_common as C  # noqa: E402

import pydicom  # noqa: E402

BASE = "Otros\\Segmentaciones ITK SNAP\\Segmentaciones Arteria Pulmonar cerdos\\"


def main():
    inv = C.read_csv_dicts(os.path.join(C.OUT_DIR, "a3_inventory.csv"))
    first_dcm = {}
    roi_folders = Counter()
    split_dims = {}
    hdr = {r["sha256"]: r for r in C.read_csv_dicts(os.path.join(C.OUT_DIR, "a3_headers.csv"))}
    for r in inv:
        if not r["relpath"].startswith(BASE):
            continue
        parts = r["relpath"][len(BASE):].split("\\")
        if parts[0].startswith("HEARDSMRI") and r["ext"] == ".nii.gz" and not r["name"].startswith("._"):
            roi_folders[parts[0]] += 1
        if len(parts) >= 5 and parts[3] == "DICOM" and r["name"].upper().startswith("IM_"):
            first_dcm.setdefault(parts[2], r["relpath"])
        if len(parts) >= 5 and parts[3] == "Split" and r["ext"] == ".mhd":
            split_dims.setdefault(parts[2], hdr.get(r["sha256"], {}).get("dims", ""))
    rows = []
    for series, rel in sorted(first_dcm.items()):
        d = pydicom.dcmread(C.lp(C.staged_path(rel)), stop_before_pixels=True, force=True)
        m = re.match(r"HEARDSMRI(\d+)P_(\d+)_(\d+)", series)
        pid = str(d.get("PatientID", ""))
        roi = f"HEARDSMRI{m.group(1)}P_{m.group(2)}_{int(m.group(3)) - 3}" if m else ""
        rows.append({"image_series_folder": series, "pig": m.group(1) if m else "", "session": m.group(2) if m else "",
                     "series_number_in_folder": m.group(3) if m else "", "study_date": str(d.get("StudyDate", "")),
                     "manufacturer": str(d.get("Manufacturer", "")), "model": str(d.get("ManufacturerModelName", "")),
                     "institution": str(d.get("InstitutionName", "")), "field_T": str(d.get("MagneticFieldStrength", "")),
                     "series_description": str(d.get("SeriesDescription", "")).strip(), "protocol": str(d.get("ProtocolName", "")),
                     "body_part": str(d.get("BodyPartExamined", "")), "patient_id_matches_folder_pig": "Y" if m and f"{m.group(1)}P" in pid else "N",
                     "roi_folder_expected": roi, "roi_files_in_that_folder": roi_folders.get(roi, 0),
                     "split_dims": split_dims.get(series, "")})
    C.write_csv(os.path.join(C.OUT_DIR, "a3_pig_series.csv"), rows)
    print(len(rows), "image series;", Counter(r["study_date"][:4] for r in rows), Counter(r["model"] + "@" + r["institution"] for r in rows))
    print("pigs:", sorted({r["pig"] for r in rows}), "PatientID matches folder:", Counter(r["patient_id_matches_folder_pig"] for r in rows))
    print("ROI folders:", len(roi_folders), "with an image series at +3:", sum(1 for r in rows if r["roi_files_in_that_folder"]))
    print("ROI folders without a matching image series:", sorted(set(roi_folders) - {r["roi_folder_expected"] for r in rows}))


if __name__ == "__main__":
    main()
