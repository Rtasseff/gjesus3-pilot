"""Combine the 45 DTS24 member scans into one SOP index + per-acq/exam summary."""
import csv, glob, collections, os
D = r"D:\projects\gjesus3\staging\_analysis\leone-ingest"
rows = 0; dic = 0
sop = {}
dupsop = 0
exams = collections.defaultdict(lambda: {"n": 0, "series": set(), "acq": set(), "pid": set(), "date": set(), "mods": collections.Counter()})
nondicom = collections.Counter()
with open(D + r"\dts24_sop_index.csv", "w", newline="", encoding="utf-8") as g:
    w = csv.writer(g); w.writerow(["SOPInstanceUID", "acq_id", "member", "sha256", "StudyInstanceUID", "SeriesInstanceUID", "PatientID", "StudyDate", "Modality"])
    for p in sorted(glob.glob(D + r"\scan\dts24_ACQ-*.csv")):
        if p.endswith("_identifiers.csv"):
            continue
        for r in csv.DictReader(open(p, encoding="utf-8")):
            rows += 1
            if r["is_dicom"] != "1":
                nondicom[os.path.basename(r["member"])[:20] if "/" in r["member"] else r["member"]] += 1
                continue
            dic += 1
            if r["SOPInstanceUID"] in sop:
                dupsop += 1
            sop[r["SOPInstanceUID"]] = r["container"]
            w.writerow([r["SOPInstanceUID"], r["container"], r["member"], r["sha256"], r["StudyInstanceUID"], r["SeriesInstanceUID"], r["PatientID"], r["StudyDate"], r["Modality"]])
            e = exams[r["StudyInstanceUID"]]
            e["n"] += 1; e["series"].add(r["SeriesInstanceUID"]); e["acq"].add(r["container"]); e["pid"].add(r["PatientID"]); e["date"].add(r["StudyDate"]); e["mods"][r["Modality"]] += 1
print("rows", rows, "dicom", dic, "unique SOP", len(sop), "dup SOP within DTS24", dupsop)
print("non-dicom top names", nondicom.most_common(8))
with open(D + r"\dts24_exams.csv", "w", newline="", encoding="utf-8") as g:
    w = csv.writer(g); w.writerow(["StudyInstanceUID", "acq_ids", "PatientID", "StudyDate", "instances", "series", "modalities"])
    for k, e in exams.items():
        w.writerow([k, ";".join(sorted(e["acq"])), ";".join(sorted(e["pid"])), ";".join(sorted(e["date"])), e["n"], len(e["series"]), dict(e["mods"])])
print("exams (StudyInstanceUID)", len(exams))
print("acqs with >1 study", collections.Counter(len([1 for e in exams.values() if a in e["acq"]]) for a in {x for e in exams.values() for x in e["acq"]}))
