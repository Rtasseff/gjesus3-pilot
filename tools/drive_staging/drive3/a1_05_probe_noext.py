"""A1 step 1a: which extension-less files outside Bruker folders are DICOM (bytes 128..131 == 'DICM')?

Reads only the first 132 bytes of each candidate from the staged copy (read-only), then, for the
DICOM ones, a handful of header tags with pydicom (stop_before_pixels). No patient identifier is
written: PatientName / PatientID / PatientBirthDate are reduced to presence flags.

Writes a1\\noext_dicom_probe.csv (one row per candidate) and caches the DICM set.

    python a1_05_probe_noext.py
"""
import concurrent.futures as cf
import os

from a1_common import cache_save, classify, load_manifest, lp, staged, write_csv

TAGS = ["Modality", "Manufacturer", "ManufacturerModelName", "StudyDate", "InstitutionName",
        "PatientSpeciesDescription", "BodyPartExamined", "SeriesDescription", "PatientName",
        "PatientID", "PatientBirthDate", "StationName"]


def probe(rp):
    out = {"relpath": rp, "is_dicm": "N", "err": ""}
    try:
        with open(lp(staged(rp)), "rb") as f:
            head = f.read(132)
        if head[128:132] != b"DICM":
            return out
        out["is_dicm"] = "Y"
        import pydicom
        with open(lp(staged(rp)), "rb") as f:
            ds = pydicom.dcmread(f, stop_before_pixels=True, force=True, specific_tags=TAGS)

        def g(k):
            return " ".join(str(ds.get(k, "") or "").split())
        out.update({"modality": g("Modality"), "manufacturer": g("Manufacturer"),
                    "model": g("ManufacturerModelName"), "study_year": g("StudyDate")[:4],
                    "institution": g("InstitutionName"), "station": g("StationName"),
                    "species": g("PatientSpeciesDescription"), "body_part": g("BodyPartExamined"),
                    "series_description": g("SeriesDescription"),
                    "has_patient_name": "Y" if g("PatientName") else "N",
                    "has_patient_id": "Y" if g("PatientID") else "N",
                    "has_birth_date": "Y" if g("PatientBirthDate") else "N"})
    except Exception as e:  # noqa: BLE001 -- recorded per file
        out["err"] = f"{type(e).__name__}: {str(e)[:120]}"
    return out


def main():
    df = classify(load_manifest())
    cand = df[(df["ext"] == "") & (df["a1class"] == "other")]
    print(f"candidates (extension-less, outside Bruker/TopSpin folders, not junk): {len(cand):,}")
    rows = []
    with cf.ThreadPoolExecutor(16) as ex:
        for i, r in enumerate(ex.map(probe, cand["relpath"]), 1):
            rows.append(r)
            if i % 5000 == 0:
                print(f"  {i:,}")
    rows.sort(key=lambda r: r["relpath"])
    write_csv("noext_dicom_probe.csv", rows,
              ["relpath", "is_dicm", "modality", "manufacturer", "model", "study_year", "institution",
               "station", "species", "body_part", "series_description", "has_patient_name",
               "has_patient_id", "has_birth_date", "err"])
    dicm = frozenset(r["relpath"] for r in rows if r["is_dicm"] == "Y")
    cache_save("dicm_noext", dicm)
    errs = sum(1 for r in rows if r["err"])
    print(f"DICM: {len(dicm):,}   errors: {errs}")


if __name__ == "__main__":
    main()
