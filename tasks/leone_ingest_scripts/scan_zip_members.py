"""Member-level scan of a zip (recursing into nested .zip members).

For every file member: sha256, size, and (when it parses as DICOM) identifying
UIDs + a few descriptive tags. Read-only on the source archive.

Patient name / birth date are written ONLY to a separate *_identifiers.csv
(kept on D:, never committed) so the later privacy grep has its needles.

usage: python scan_zip_members.py <zip> <out_prefix> [--worker i --nworkers n] [--label L]
"""
import argparse, csv, hashlib, io, sys, time, zipfile, traceback
import pydicom
from pydicom.errors import InvalidDicomError

TAGS = ["PatientID", "StudyInstanceUID", "SeriesInstanceUID", "SOPInstanceUID",
        "SOPClassUID", "StudyDate", "SeriesDate", "StudyTime", "SeriesNumber",
        "SeriesDescription", "StudyDescription", "Modality", "Manufacturer",
        "ManufacturerModelName", "InstitutionName", "PatientSex", "PatientAge",
        "BodyPartExamined", "NumberOfFrames"]
ID_TAGS = ["PatientName", "PatientBirthDate", "OtherPatientIDs", "AccessionNumber"]


def parse(data):
    if len(data) < 132:
        return None
    try:
        ds = pydicom.dcmread(io.BytesIO(data), stop_before_pixels=True, force=False)
    except InvalidDicomError:
        # tolerate preamble-less DICOM (no 'DICM' magic)
        try:
            ds = pydicom.dcmread(io.BytesIO(data), stop_before_pixels=True, force=True)
            if "SOPInstanceUID" not in ds:
                return None
        except Exception:
            return None
    except Exception:
        return None
    out = {}
    for t in TAGS + ID_TAGS:
        try:
            v = ds.get(t, "")
            out[t] = "" if v is None else str(v)
        except Exception:
            out[t] = "?"
    if not out.get("SOPInstanceUID"):
        return None
    return out


def walk(zf, prefix, emit, worker, nworkers, counter):
    for zi in zf.infolist():
        if zi.is_dir():
            continue
        name = zi.filename
        idx = counter[0]; counter[0] += 1
        is_nested = name.lower().endswith(".zip")
        # nested zips are always handled by worker 0 (they are few and small)
        if not is_nested and idx % nworkers != worker:
            continue
        if is_nested and worker != 0:
            continue
        try:
            with zf.open(zi) as fh:
                data = fh.read()
        except Exception as e:
            emit(prefix + name, zi.file_size, "", None, "READ_ERROR:" + repr(e)[:200])
            continue
        sha = hashlib.sha256(data).hexdigest()
        if is_nested:
            emit(prefix + name, len(data), sha, None, "NESTED_ZIP")
            try:
                nz = zipfile.ZipFile(io.BytesIO(data))
                walk(nz, prefix + name + "!/", emit, 0, 1, [0])
            except Exception as e:
                emit(prefix + name, len(data), sha, None, "NESTED_OPEN_ERROR:" + repr(e)[:200])
            continue
        emit(prefix + name, len(data), sha, parse(data), "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("zip"); ap.add_argument("out_prefix")
    ap.add_argument("--worker", type=int, default=0); ap.add_argument("--nworkers", type=int, default=1)
    ap.add_argument("--label", default="")
    a = ap.parse_args()
    t0 = time.time()
    f = open(a.out_prefix + ".csv", "w", newline="", encoding="utf-8")
    g = open(a.out_prefix + "_identifiers.csv", "w", newline="", encoding="utf-8")
    w = csv.writer(f); wi = csv.writer(g)
    w.writerow(["container", "member", "size", "sha256", "is_dicom", "note"] + TAGS)
    wi.writerow(["container", "member", "SOPInstanceUID"] + ID_TAGS)
    n = [0, 0, 0]

    def emit(member, size, sha, d, note):
        n[0] += 1
        if d:
            n[1] += 1
            w.writerow([a.label, member, size, sha, 1, note] + [d.get(t, "") for t in TAGS])
            wi.writerow([a.label, member, d["SOPInstanceUID"]] + [d.get(t, "") for t in ID_TAGS])
        else:
            if note.startswith(("READ_ERROR", "NESTED_OPEN_ERROR")):
                n[2] += 1
            w.writerow([a.label, member, size, sha, 0, note] + [""] * len(TAGS))
        if n[0] % 20000 == 0:
            f.flush(); g.flush()
            print(f"{a.label} w{a.worker}: {n[0]} members, {n[1]} dicom, {n[2]} errors, {time.time()-t0:.0f}s", flush=True)

    zf = zipfile.ZipFile(a.zip)
    walk(zf, "", emit, a.worker, a.nworkers, [0])
    f.close(); g.close()
    print(f"DONE {a.label} w{a.worker}: {n[0]} members, {n[1]} dicom, {n[2]} errors, {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
