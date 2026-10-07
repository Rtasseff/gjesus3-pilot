"""Stream M, part 2: the CNIC pig images -- one row per exported series folder; its staging, case table and checks.

    python mri_21_pig_rows.py

The row unit (settled from every header, mri_20_pig_probe.py and the gate's Part 2): each of the 27 folders
`HEARDSMRI<pig>P_<session>_<series>` is ONE Philips phase-contrast flow series (SeriesNumber = the folder's last number;
magnitude M_FFE + VELOCITY MAP images under one SeriesInstanceUID), plus the small companion objects the scanner
exported with it: an instance of the study's Raw Data Storage object (SOP 1.2.840.10008.5.1.4.1.1.66, series 0), and in
one folder two presentation states. One row per folder = one row per image series, the internal-MRI unit (BACKLOG
"external collaborator archives are one row per EXAM, not per series"); session_id = the scanner study (pig + session).
Registered: every file of the folder's DICOM\\ with the DICM preamble. NOT registered (to stream P, with the masks):
DICOMDIR (the export's index), Split\\ (derived MetaImage), folders.cache / thumbs.cache (one of them, 212 MB, is a
MATLAB 5.0 file, not a cache).
Builds stage\\P01\\<folder>\\<instance> as HARD LINKS of stage\\PIG\\ (same volume, no bytes), writes
tools/configs/drive3_mri/cases_P01.csv and out\\pig_rows.csv / out\\pig_not_registered.csv.
"""
import collections
import os
import sys
import warnings

import pydicom

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mri_common as C  # noqa: E402

warnings.filterwarnings("ignore")
SRC = os.path.join(C.STAGE, "PIG")
DST = os.path.join(C.STAGE, "P01")
PIG = "Otros\\Segmentaciones ITK SNAP\\Segmentaciones Arteria Pulmonar cerdos\\Imágenes\\RL"


def s(v):
    return "" if v is None else str(v).strip()


def main():
    stage = {r["staged_rel"]: r for r in C.rows(os.path.join(C.OUT, "stage_result_pig.csv"))}
    rows_, notreg, problems = [], [], []
    for folder in sorted(os.listdir(SRC)):
        pig, sess, ser = folder.replace("HEARDSMRI", "").split("_")
        pig = pig.rstrip("P")
        reg, image_series, studies, companions = [], collections.Counter(), set(), collections.Counter()
        first = None
        for dirpath, _d, files in os.walk(os.path.join(SRC, folder)):
            for n in sorted(files):
                p = os.path.join(dirpath, n)
                rel = os.path.relpath(p, SRC)
                with open(p, "rb") as f:
                    magic = f.read(132)[128:132] == b"DICM"
                inner = os.path.relpath(p, os.path.join(SRC, folder))
                if inner.startswith("DICOM" + os.sep) and magic:
                    ds = pydicom.dcmread(p, stop_before_pixels=True, force=True)
                    sop = s(getattr(ds, "SOPClassUID", ""))
                    if sop == "1.2.840.10008.5.1.4.1.1.4":
                        image_series[s(getattr(ds, "SeriesInstanceUID", ""))] += 1
                        if first is None or "M_FFE" in "\\".join(getattr(ds, "ImageType", []) or []):
                            first = first or ds
                    else:
                        companions[f"{s(getattr(ds, 'Modality', ''))}:{sop.split('.')[-1]}"] += 1
                    studies.add(s(getattr(ds, "StudyInstanceUID", "")))
                    reg.append((p, n))
                else:
                    notreg.append({"folder": folder, "inner": inner, "size": os.path.getsize(p),
                                   "sha256": stage["PIG\\" + rel]["sha256"], "drive_relpath": stage["PIG\\" + rel]["drive_relpath"],
                                   "why": "DICOMDIR (export index)" if n == "DICOMDIR" else
                                          ("MATLAB file named " + n if open(p, "rb").read(10).startswith(b"MATLAB") else
                                           f"not DICOM ({n})")})
        if len(image_series) != 1 or len({x for x in studies if x}) != 1:
            problems.append(f"{folder}: image series {len(image_series)}, studies {len(studies)}")
        if s(getattr(first, "SeriesNumber", "")) != ser:
            problems.append(f"{folder}: SeriesNumber {getattr(first, 'SeriesNumber', '')} != folder {ser}")
        names = [n for _p, n in reg]
        if len(set(names)) != len(names):
            problems.append(f"{folder}: instance names repeat once flattened")
        os.makedirs(os.path.join(DST, folder), exist_ok=True)
        for p, n in reg:
            d = os.path.join(DST, folder, n)
            if not os.path.exists(d):
                os.link(p, d)
            elif not os.path.samefile(p, d):
                problems.append(f"{folder}: {n} exists and is not the staged file")
        sd, st = s(getattr(first, "SeriesDate", "")), s(getattr(first, "SeriesTime", ""))
        dt = f"{sd[:4]}-{sd[4:6]}-{sd[6:8]}T{st[:2]}:{st[2:4]}:{st[4:6]}"
        proto = s(getattr(first, "ProtocolName", ""))
        rows_.append({
            "original_name": folder, "drv_acq_datetime": dt, "drv_acq_time_source": "DICOM SeriesDate+SeriesTime",
            "drv_sample": f"HEARDSMRI{pig}P", "drv_session": f"HEARDSMRI{pig}P_{sess}", "drv_series": ser,
            "drv_model": f"Philips Achieva {s(getattr(first, 'MagneticFieldStrength', ''))}T",
            "drv_sex": s(getattr(first, "PatientSex", "")),
            "drv_note": (f"External MRI (Philips Achieva 3T, CNIC Madrid, study label HEARDS), pig {pig}, session {sess}, "
                         f"series {ser} '{proto}' {s(getattr(first, 'SeriesDescription', ''))}: phase-contrast flow "
                         f"(magnitude + velocity map, {sum(image_series.values())} images) + {sum(companions.values())} "
                         f"companion object(s) {dict(companions)}; the source images of the pig pulmonary-artery masks "
                         f"(project folder); historical drive 3 (M. Jesus, MJesus-MFB, WD WX22D623YP29): {PIG}\\{folder}; "
                         f"registered as XMRI collaborator data (Ryan, 2026-10-06)"),
            "n_files": len(reg), "n_images": sum(image_series.values()), "companions": dict(companions)})
    fields = ["original_name", "drv_acq_datetime", "drv_acq_time_source", "drv_sample", "drv_session", "drv_series",
              "drv_model", "drv_sex", "drv_note"]
    C.write_csv(os.path.join(C.CFG_DIR, "cases_P01.csv"), rows_, fields)
    C.write_csv(C.out("pig_rows.csv"), rows_)
    C.write_csv(C.out("pig_not_registered.csv"), notreg)
    L = [f"rows {len(rows_)}; files to register {sum(r['n_files'] for r in rows_)} (images {sum(r['n_images'] for r in rows_)}); "
         f"sessions {len({r['drv_session'] for r in rows_})}; pigs {len({r['drv_sample'] for r in rows_})}; "
         f"dates {sorted({r['drv_acq_datetime'][:10] for r in rows_})}",
         f"not registered: {len(notreg)} files, {sum(n['size'] for n in notreg) / 1e6:.0f} MB "
         f"{dict(collections.Counter(n['why'] for n in notreg))}",
         f"problems: {problems}"]
    open(C.out("pig_rows.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
