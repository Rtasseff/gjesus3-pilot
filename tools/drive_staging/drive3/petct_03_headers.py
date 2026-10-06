"""Stream N, step 2: the DICOM header facts of every drive reconstruction (read-only).

For each of the 492 acquisition keys in out\\acq_inventory.csv, opens the canonical drive copy
(J:\\_staging_drive3_MJ\\...\\files\\<relpath>, mode 'rb', header only) and records the elements
that identify the acquisition: the timestamp the scanner writes into the file name
(AcquisitionDateTime), the modality and cube, and what was typed at the console
(PatientID = animal, SeriesDescription = "<animal> / <protocol> / <algorithm>",
StudyDescription = protocol code, PatientName = "<operator>^/ <protocol> / <yymmdd>").

Writes out\\acq_headers.csv.
"""
import concurrent.futures as cf
import csv
import os
import sys

sys.dont_write_bytecode = True
csv.field_size_limit(2 ** 31 - 1)
OUT = r"D:\projects\gjesus3\drive3_streams\petct\out"
STAGED = r"J:\_staging_drive3_MJ\drive3_MJesus_WX22D623YP29\files"
TAGS = ["Modality", "Manufacturer", "ManufacturerModelName", "AcquisitionDateTime", "StudyDate", "StudyTime",
        "AcquisitionDate", "AcquisitionTime", "SeriesDescription", "StudyDescription", "PatientID", "PatientName",
        "ReferringPhysicianName", "PerformingPhysicianName", "PatientWeight", "StudyInstanceUID",
        "SeriesInstanceUID", "NumberOfFrames", "ImageType", "SoftwareVersions", "DeviceSerialNumber",
        "InstitutionName", "SOPClassUID"]


def lp(p):
    ap = os.path.abspath(p)
    return ap if ap.startswith("\\\\?\\") else "\\\\?\\" + ap


def flat(v):
    if isinstance(v, (list, tuple)) or type(v).__name__ == "MultiValue":
        v = "\\".join(str(x) for x in v)
    return " ".join(str(v if v is not None else "").split())


def read(rel):
    import pydicom
    try:
        with open(lp(os.path.join(STAGED, rel)), "rb") as f:
            ds = pydicom.dcmread(f, stop_before_pixels=True, force=True)
        out = {k: flat(ds.get(k, "")) for k in TAGS}
        dose = ""
        try:
            rp = ds.get("RadiopharmaceuticalInformationSequence")
            if rp:
                dose = flat(rp[0].get("RadionuclideTotalDose", ""))
        except Exception:  # noqa: BLE001
            pass
        out["RadionuclideTotalDose"] = dose
        out["hdr_err"] = ""
    except Exception as e:  # noqa: BLE001
        out = {k: "" for k in TAGS}
        out["RadionuclideTotalDose"] = ""
        out["hdr_err"] = f"{type(e).__name__}: {str(e)[:120]}"
    return rel, out


def main():
    inv = list(csv.DictReader(open(os.path.join(OUT, "acq_inventory.csv"), encoding="utf-8", newline="")))
    rels = [r["canonical_drive_relpath"] for r in inv]
    with cf.ThreadPoolExecutor(12) as ex:
        hdr = dict(ex.map(read, rels))
    rows = []
    for r in inv:
        h = hdr[r["canonical_drive_relpath"]]
        rows.append({"acq_key": r["acq_key"], "coverage": r["coverage"],
                     "canonical_drive_relpath": r["canonical_drive_relpath"], **h})
    fields = list(rows[0].keys())
    with open(os.path.join(OUT, "acq_headers.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    errs = [r for r in rows if r["hdr_err"]]
    print(f"headers read: {len(rows)}, errors: {len(errs)}")
    for r in errs:
        print("  ", r["acq_key"], r["hdr_err"])


if __name__ == "__main__":
    main()
