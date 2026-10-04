"""US (echo) characterisation + privacy-relevant tags (counts only; no values printed).
Also builds the 'new member' list = ingest candidates, keyed to one copy each."""
import csv, collections, io, zipfile
import pydicom
S = r"C:\Users\rtasseff\temp\scratch_leone-ingest"
D = r"D:\projects\gjesus3\staging\_analysis\leone-ingest"
csv.field_size_limit(10**8)
dts = set(r["SOPInstanceUID"] for r in csv.DictReader(open(S + r"\dts24_sop_index.csv", encoding="utf-8")))
L = [r for r in csv.DictReader(open(S + r"\leone.csv", encoding="utf-8")) if r["is_dicom"] == "1"]

# one copy per new SOP: prefer ExportLeone (it holds everything)
best = {}
for r in L:
    s = r["SOPInstanceUID"]
    if s in dts:
        continue
    if s not in best or ("/ExportLeone/" in r["member"] and "/ExportLeone/" not in best[s]["member"]):
        best[s] = r
print("new unique SOPs", len(best), "of which in ExportLeone", sum("/ExportLeone/" in r["member"] for r in best.values()))
outside = [r for r in best.values() if "/ExportLeone/" not in r["member"]]
print("new SOPs with no ExportLeone copy:", len(outside), collections.Counter(r["member"].split("/")[1] for r in outside))

# per patient/study exam table of NEW content
ex = collections.defaultdict(lambda: {"n": 0, "b": 0, "mods": collections.Counter(), "series": set(), "date": set(), "sopc": collections.Counter()})
for r in best.values():
    e = ex[(r["PatientID"], r["StudyInstanceUID"])]
    e["n"] += 1; e["b"] += int(r["size"]); e["mods"][r["Modality"]] += 1; e["series"].add(r["SeriesInstanceUID"]); e["date"].add(r["StudyDate"])
    e["sopc"][r["SOPClassUID"]] += 1
with open(D + r"\new_content_by_exam.csv", "w", newline="", encoding="utf-8") as g:
    w = csv.writer(g); w.writerow(["PatientID", "StudyInstanceUID", "StudyDate", "new_instances", "GB", "series", "modalities", "sop_classes"])
    for k in sorted(ex, key=lambda k: (k[0], sorted(ex[k]["date"]))):
        e = ex[k]
        w.writerow([k[0], k[1], ";".join(sorted(e["date"])), e["n"], round(e["b"] / 1e9, 3), len(e["series"]), dict(e["mods"]), dict(e["sopc"])])
with open(D + r"\new_members.csv", "w", newline="", encoding="utf-8") as g:
    w = csv.writer(g); w.writerow(["member", "size", "sha256", "PatientID", "StudyInstanceUID", "SeriesInstanceUID", "SOPInstanceUID", "SOPClassUID", "Modality", "StudyDate", "SeriesNumber", "SeriesDescription"])
    for r in best.values():
        w.writerow([r[k] for k in ["member", "size", "sha256", "PatientID", "StudyInstanceUID", "SeriesInstanceUID", "SOPInstanceUID", "SOPClassUID", "Modality", "StudyDate", "SeriesNumber", "SeriesDescription"]])
us_ex = [k for k in ex if ex[k]["mods"].get("US")]
print("exams with new US:", len(us_ex), "patients:", len({k[0] for k in us_ex}))
print("exam count by modality-set:", collections.Counter(tuple(sorted(ex[k]["mods"])) for k in ex))

# privacy-relevant tags on a sample of US + all-type files (read from SSD copy)
z = zipfile.ZipFile(S + r"\LEONE.zip")
samp = collections.defaultdict(list)
for r in best.values():
    if len(samp[r["Modality"]]) < 60:
        samp[r["Modality"]].append(r)
for mod, rs in samp.items():
    c = collections.Counter()
    for r in rs:
        ds = pydicom.dcmread(io.BytesIO(z.read(r["member"])), stop_before_pixels=True, force=True)
        c["n"] += 1
        bia = str(ds.get("BurnedInAnnotation", "<absent>"))
        c["BurnedInAnnotation=" + bia] += 1
        c["PatientTelephoneNumbers nonempty"] += bool(str(ds.get("PatientTelephoneNumbers", "")).strip())
        c["PatientAddress nonempty"] += bool(str(ds.get("PatientAddress", "")).strip())
        c["ReferringPhysicianName nonempty"] += bool(str(ds.get("ReferringPhysicianName", "")).strip())
        c["InstitutionName nonempty"] += bool(str(ds.get("InstitutionName", "")).strip())
        c["SOPClass " + str(ds.get("SOPClassUID", ""))] += 1
        c["Manufacturer " + str(ds.get("Manufacturer", ""))] += 1
    print(mod, dict(c))
