"""Placement manifest for Ryan's ruling (2026-10-02): no DTS24 duplicates; the NEW content goes into
projects\\DTS24\\working\\historical_drives\\<drive tag>\\LEONE\\{echo,mr_supplements,derived}\\ as files.

Identity comes from the DICOM header (PatientID, normalised LEONE-1.04 -> LEONE_1.04), never the
folder name. Second level is header-driven: <category>\\<case>\\<studydate>_<modality>\\[<series>\\]<file>.
Destination paths here are RELATIVE to ...\\LEONE\\; stream A's compaction function is applied on top.
No names/DOBs are read or written: input is new_members.csv (UIDs/descriptions only).
"""
import csv, collections, re, os
D = r"D:\projects\gjesus3\staging\_analysis\leone-ingest"
DERIV = {"1.2.840.10008.5.1.4.1.1.7", "1.2.840.10008.5.1.4.1.1.88.33", "1.2.840.10008.5.1.4.1.1.88.59",
         "1.3.46.670589.2.5.1.1"}


def safe(s, n=40):
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", (s or "").strip())
    s = re.sub(r"\s+", "_", s)
    return s[:n].rstrip("._") or "unnamed"


rows = list(csv.DictReader(open(D + r"\new_members.csv", encoding="utf-8")))
out = []
for r in rows:
    case = r["PatientID"].replace("LEONE-", "LEONE_")
    if r["SOPClassUID"] in DERIV:
        cat = "derived"
    elif r["Modality"] == "US":
        cat = "echo"
    else:
        cat = "mr_supplements"
    exam = f"{r['StudyDate']}_{r['Modality'] if cat != 'mr_supplements' else 'MR'}"
    parts = [cat, safe(case), exam]
    if cat == "mr_supplements":
        sn = r["SeriesNumber"] or "0"
        parts.append(safe(f"S{sn}_{r['SeriesDescription'] or ('rawdata' if r['SOPClassUID'].endswith('.1.1.66') else 'noname')}"))
    base = r["member"].rsplit("/", 1)[-1]
    out.append({"category": cat, "case_id_from_header": case, "study_date": r["StudyDate"], "modality": r["Modality"],
                "series_number": r["SeriesNumber"], "series_description": r["SeriesDescription"],
                "sop_class": r["SOPClassUID"], "sop_instance_uid": r["SOPInstanceUID"],
                "study_instance_uid": r["StudyInstanceUID"], "dest_rel": "\\".join(parts + [base]),
                "source_member_in_LEONE_zip": r["member"], "size": r["size"], "sha256": r["sha256"]})
# filename collisions within a destination folder -> suffix with the SOP UID tail
seen = collections.Counter(o["dest_rel"].lower() for o in out)
coll = 0
for o in out:
    if seen[o["dest_rel"].lower()] > 1:
        d, b = o["dest_rel"].rsplit("\\", 1)
        o["dest_rel"] = f"{d}\\{b}__{o['sop_instance_uid'][-12:]}"; coll += 1
assert len({o["dest_rel"].lower() for o in out}) == len(out), "collision remains"
with open(D + r"\placement_manifest.csv", "w", newline="", encoding="utf-8") as g:
    w = csv.DictWriter(g, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
c = collections.Counter(); b = collections.Counter(); cases = collections.defaultdict(set)
for o in out:
    c[o["category"]] += 1; b[o["category"]] += int(o["size"]); cases[o["category"]].add(o["case_id_from_header"])
print("files", len(out), "GB", round(sum(b.values()) / 1e9, 2), "renamed-for-collision", coll)
for k in c:
    print(f"  {k:15} {c[k]:6d} files {b[k]/1e9:7.2f} GB  cases {len(cases[k])}")
print("longest dest_rel", max(len(o["dest_rel"]) for o in out))
print("example", out[0]["dest_rel"])
