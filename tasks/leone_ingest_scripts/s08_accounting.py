"""Final accounting: every LEONE member -> one disposition. Plus the proposed new-acquisition table."""
import csv, collections
S = r"C:\Users\rtasseff\temp\scratch_leone-ingest"
D = r"D:\projects\gjesus3\staging\_analysis\leone-ingest"
csv.field_size_limit(10**8)
dts = {}
for r in csv.DictReader(open(S + r"\dts24_sop_index.csv", encoding="utf-8")):
    dts[r["SOPInstanceUID"]] = r["acq_id"]
DERIV_CLASSES = {"1.2.840.10008.5.1.4.1.1.7", "1.2.840.10008.5.1.4.1.1.88.33", "1.2.840.10008.5.1.4.1.1.88.59", "1.3.46.670589.2.5.1.1",
                 "1.2.840.10008.5.1.4.1.1.11.1"}
L = list(csv.DictReader(open(S + r"\leone.csv", encoding="utf-8")))
disp = collections.Counter(); dispb = collections.Counter()
seen = set()
out = open(D + r"\leone_member_disposition.csv", "w", newline="", encoding="utf-8")
w = csv.writer(out); w.writerow(["member", "size", "disposition", "detail"])
for r in L:
    m = r["member"]; sz = int(r["size"] or 0); name = m.rsplit("/", 1)[-1]
    if r["is_dicom"] != "1":
        if r["note"] == "NESTED_ZIP":
            d, det = "container: nested zip (members accounted individually)", ""
        elif name.startswith("._"):
            d, det = "excluded: macOS AppleDouble metadata", ""
        elif name == ".DS_Store":
            d, det = "excluded: macOS .DS_Store", ""
        elif name == "DICOMDIR":
            d, det = "excluded: DICOMDIR index (regenerable, references paths)", ""
        elif sz == 0:
            d, det = "excluded: 0-byte file", ""
        elif name.endswith(".ipynb"):
            d, det = "excluded: personal notebook (ExportLeone/decompress_dicom.ipynb), not data", ""
        elif "MASTER HF2021 SEC" in m:
            d, det = "excluded: unrelated course material (pdf/pptx/docx) in LEONE 1.13", ""
        else:
            d, det = "UNCLASSIFIED", ""
    else:
        s = r["SOPInstanceUID"]
        if s in seen:
            d, det = "duplicate copy within LEONE (same SOPInstanceUID)", ""
        else:
            seen.add(s)
            if s in dts:
                d, det = "already in DTS24 (same SOPInstanceUID; pixel-identical re-export)", dts[s]
            elif r["SOPClassUID"] in DERIV_CLASSES:
                d, det = "NEW derivative (SC/SR/PR/KO) -> project folder", r["Modality"]
            elif r["Modality"] == "US":
                d, det = "NEW raw: echo (US)", ""
            elif r["SOPClassUID"].endswith(".1.1.66"):
                d, det = "NEW raw: MR Philips Raw Data Storage object", ""
            else:
                d, det = "NEW raw: MR image", r["SeriesDescription"]
    disp[d] += 1; dispb[d] += sz
    w.writerow([m, sz, d, det])
out.close()
tot = sum(disp.values())
print("TOTAL members", tot, round(sum(dispb.values()) / 1e9, 2), "GB")
for k, v in sorted(disp.items(), key=lambda x: -x[1]):
    print(f"{v:8d} {dispb[k]/1e9:8.2f} GB  {k}")
