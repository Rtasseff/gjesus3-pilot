"""Drill-down: (1) what the per-exam 'new' MR SOPs are, (2) why shared SOPs differ in bytes,
(3) identifier presence in LEONE vs DTS24 headers (counts only, no values printed), (4) US totals."""
import csv, collections, io, zipfile, difflib
import pydicom
S = r"C:\Users\rtasseff\temp\scratch_leone-ingest"
D = r"D:\projects\gjesus3\staging\_analysis\leone-ingest"
csv.field_size_limit(10**8)
dts = {}
for r in csv.DictReader(open(S + r"\dts24_sop_index.csv", encoding="utf-8")):
    dts[r["SOPInstanceUID"]] = (r["acq_id"], r["member"])
L = list(csv.DictReader(open(S + r"\leone.csv", encoding="utf-8")))
ex = [r for r in L if r["is_dicom"] == "1" and "/ExportLeone/" in r["member"]]

# (1) new SOPs in MR studies of ExportLeone: modality / series description
new = collections.Counter(); new302 = collections.Counter(); newser = collections.Counter()
for r in ex:
    if r["SOPInstanceUID"] in dts or r["Modality"] == "US":
        continue
    if r["PatientID"] == "LEONE_3.02":
        new302[(r["Modality"], r["SeriesNumber"], r["SeriesDescription"])] += 1
    else:
        new[(r["Modality"], r["SOPClassUID"][-20:])] += 1
        newser[r["SeriesDescription"]] += 1
print("(1) new non-US SOPs (excl 3.02) by modality/SOPClass:", new.most_common(10))
print("    by series description:", newser.most_common(12))
print("    3.02 new by series:", new302.most_common(12))

# (4) US / SR totals
us = collections.Counter(); usb = collections.Counter()
for r in ex:
    if r["SOPInstanceUID"] not in dts:
        us[r["Modality"]] += 1; usb[r["Modality"]] += int(r["size"])
print("(4) ExportLeone not-in-DTS24 by modality:", dict(us), {k: round(v / 1e9, 2) for k, v in usb.items()})
pids_us = sorted({r["PatientID"] for r in ex if r["Modality"] == "US"})
print("    US patients:", len(pids_us))

# (3) identifier presence (counts only)
def presence(path):
    c = collections.Counter()
    for r in csv.DictReader(open(path, encoding="utf-8")):
        c["rows"] += 1
        c["PatientName"] += bool(r["PatientName"].strip())
        c["PatientBirthDate"] += bool(r["PatientBirthDate"].strip())
        c["OtherPatientIDs"] += bool(r["OtherPatientIDs"].strip())
        c["AccessionNumber"] += bool(r["AccessionNumber"].strip())
    return dict(c)
print("(3) LEONE identifiers present:", presence(D + r"\scan\leone_identifiers.csv"))
import glob
tot = collections.Counter()
for p in glob.glob(D + r"\scan\dts24_ACQ-*_identifiers.csv"):
    tot.update(presence(p))
print("    DTS24 identifiers present:", dict(tot))

# (2) byte diff of one shared SOP pair (header-level element diff, values elided)
zl = zipfile.ZipFile(S + r"\LEONE.zip")
for r in ex:
    if r["SOPInstanceUID"] in dts and r["Modality"] == "MR":
        acq, mem = dts[r["SOPInstanceUID"]]
        break
canon = [x for x in csv.DictReader(open(D + r"\dts24_registry_rows.csv", encoding="utf-8")) if x["acq_id"] == acq][0]
zd = zipfile.ZipFile("J:/gjesus3-data" + canon["canonical_path"] + canon["primary_file_name"])
a = zl.read(r["member"]); b = zd.read(mem)
da = pydicom.dcmread(io.BytesIO(a), force=True); db = pydicom.dcmread(io.BytesIO(b), force=True)
print("(2) pair", acq, "LEONE bytes", len(a), "DTS24 bytes", len(b))
print("    transfer syntax LEONE", da.file_meta.get("TransferSyntaxUID"), "| DTS24", db.file_meta.get("TransferSyntaxUID"))
print("    impl LEONE", da.file_meta.get("ImplementationVersionName"), "| DTS24", db.file_meta.get("ImplementationVersionName"))
ka = {e.tag for e in da.iterall()}; kb = {e.tag for e in db.iterall()}
print("    tags only in LEONE:", len(ka - kb), sorted(str(t) for t in ka - kb)[:15])
print("    tags only in DTS24:", len(kb - ka), sorted(str(t) for t in kb - ka)[:15])
diffv = []
for e in da:
    if e.tag in db and e.VR not in ("SQ", "OB", "OW") and e.tag != 0x7FE00010:
        if str(e.value) != str(db[e.tag].value):
            diffv.append(f"{e.tag} {e.keyword}")
print("    top-level tags with different values:", diffv[:25])
print("    pixel equal:", da.get("PixelData") == db.get("PixelData") if "PixelData" in da and "PixelData" in db else "n/a")
