"""Verify 'shared SOP = same image': for each DTS24 acquisition that LEONE overlaps, compare
PixelData (and key geometry tags) for N random shared SOPs. Reads DTS24 zips over SMB (members only)."""
import csv, collections, io, random, zipfile
import pydicom
S = r"C:\Users\rtasseff\temp\scratch_leone-ingest"
D = r"D:\projects\gjesus3\staging\_analysis\leone-ingest"
csv.field_size_limit(10**8)
N = 20
random.seed(20261002)
dts = {}
for r in csv.DictReader(open(S + r"\dts24_sop_index.csv", encoding="utf-8")):
    dts[r["SOPInstanceUID"]] = (r["acq_id"], r["member"])
by_acq = collections.defaultdict(list)
for r in csv.DictReader(open(S + r"\leone.csv", encoding="utf-8")):
    if r["is_dicom"] == "1" and r["SOPInstanceUID"] in dts:
        by_acq[dts[r["SOPInstanceUID"]][0]].append((r["member"], r["SOPInstanceUID"]))
reg = {x["acq_id"]: x for x in csv.DictReader(open(D + r"\dts24_registry_rows.csv", encoding="utf-8"))}
zl = zipfile.ZipFile(S + r"\LEONE.zip")
GEOM = ["Rows", "Columns", "PixelSpacing", "SliceThickness", "ImagePositionPatient", "ImageOrientationPatient", "NumberOfFrames", "SeriesInstanceUID", "StudyInstanceUID"]
tot = collections.Counter()
with open(D + r"\pixel_verify_sample.csv", "w", newline="", encoding="utf-8") as g:
    w = csv.writer(g); w.writerow(["acq_id", "SOPInstanceUID", "pixel_equal", "geometry_equal", "leone_ts", "dts_ts", "note"])
    for acq in sorted(by_acq):
        c = reg[acq]
        zd = zipfile.ZipFile("J:/gjesus3-data" + c["canonical_path"] + c["primary_file_name"])
        pick = random.sample(by_acq[acq], min(N, len(by_acq[acq])))
        for mem, sop in pick:
            try:
                a = pydicom.dcmread(io.BytesIO(zl.read(mem)), force=True)
                b = pydicom.dcmread(io.BytesIO(zd.read(dts[sop][1])), force=True)
                hp = "PixelData" in a and "PixelData" in b
                pe = (a.PixelData == b.PixelData) if hp else None
                ge = all(str(a.get(t, "")) == str(b.get(t, "")) for t in GEOM)
                w.writerow([acq, sop, pe, ge, a.file_meta.get("TransferSyntaxUID", ""), b.file_meta.get("TransferSyntaxUID", ""), "" if hp else "no PixelData"])
                tot["checked"] += 1
                tot["pixel_equal" if pe else ("no_pixeldata" if pe is None else "PIXEL_DIFFERENT")] += 1
                tot["geom_equal" if ge else "GEOM_DIFFERENT"] += 1
            except Exception as e:
                w.writerow([acq, sop, "", "", "", "", "ERROR " + repr(e)[:150]]); tot["error"] += 1
        print(acq, dict(tot), flush=True)
print("FINAL", len(by_acq), "acqs", dict(tot))
