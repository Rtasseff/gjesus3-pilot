"""Per-patient (case) classification table: LEONE vs DTS24, LIONS/US/nested kept separate."""
import csv, collections
S = r"C:\Users\rtasseff\temp\scratch_leone-ingest"
D = r"D:\projects\gjesus3\staging\_analysis\leone-ingest"
csv.field_size_limit(10**8)
reg = {x["acq_id"]: x for x in csv.DictReader(open(D + r"\dts24_registry_rows.csv", encoding="utf-8"))}
dts_sop = {}; dts_pid_acq = {}
for r in csv.DictReader(open(S + r"\dts24_sop_index.csv", encoding="utf-8")):
    dts_sop[r["SOPInstanceUID"]] = r["acq_id"]
for a, x in reg.items():
    dts_pid_acq.setdefault(x["sample_id"], []).append(a)
disp = {}
for r in csv.DictReader(open(D + r"\leone_member_disposition.csv", encoding="utf-8")):
    disp[r["member"]] = r["disposition"]
cases = collections.defaultdict(lambda: {"groups": set(), "mr_shared": 0, "new_us": 0, "new_us_gb": 0.0, "new_mr_img": 0,
                                         "new_mr_raw": 0, "new_deriv": 0, "us_studies": set(), "mr_studies": set(), "dates": set()})
leone_sops_by_acq = collections.Counter()
for r in csv.DictReader(open(S + r"\leone.csv", encoding="utf-8")):
    if r["is_dicom"] != "1":
        continue
    pid = r["PatientID"].replace("LEONE-", "LEONE_")
    c = cases[pid]
    m = r["member"]
    grp = ("nested " + m.split("!/")[0].split("/")[-1]) if "!/" in m else m.split("/")[1]
    c["groups"].add(grp)
    d = disp[m]
    if r["Modality"] == "US":
        c["us_studies"].add(r["StudyInstanceUID"]); c["dates"].add("US " + r["StudyDate"])
    elif r["Modality"] == "MR":
        c["mr_studies"].add(r["StudyInstanceUID"]); c["dates"].add("MR " + r["StudyDate"])
    if d.startswith("already in DTS24"):
        c["mr_shared"] += 1; leone_sops_by_acq[dts_sop[r["SOPInstanceUID"]]] += 1
    elif d == "NEW raw: echo (US)":
        c["new_us"] += 1; c["new_us_gb"] += int(r["size"]) / 1e9
    elif d == "NEW raw: MR image":
        c["new_mr_img"] += 1
    elif d.startswith("NEW raw: MR Philips"):
        c["new_mr_raw"] += 1
    elif d.startswith("NEW derivative"):
        c["new_deriv"] += 1
dts_n = collections.Counter(dts_sop.values())
allp = sorted(set(cases) | {x["sample_id"] for x in reg.values() if x["data_source"] == "collaborator:LIONS"})
with open(D + r"\case_table.csv", "w", newline="", encoding="utf-8") as g:
    w = csv.writer(g)
    w.writerow(["case", "LEONE_groups", "LEONE_dates", "DTS24_acq", "DTS24_instances", "shared_unique_SOPs", "DTS24_missing_from_LEONE",
                "new_MR_images", "new_MR_rawdata_objs", "new_US", "new_US_GB", "new_derivatives", "classification"])
    for p in allp:
        c = cases.get(p)
        acqs = dts_pid_acq.get(p, [])
        dn = sum(dts_n[a] for a in acqs)
        if c is None:
            w.writerow([p, "", "", ";".join(acqs), dn, 0, dn, 0, 0, 0, 0, 0, "DTS24 only (exam not in LEONE)"]); continue
        shared = sum(leone_sops_by_acq[a] for a in acqs)
        # unique-SOP shared count (leone_sops_by_acq counts first copies only via disposition)
        miss = dn - shared
        parts = []
        if c["mr_studies"] and acqs:
            if c["new_mr_img"] > 100:
                parts.append("MR: same exam, LEONE superset (extra series)")
            elif c["new_mr_img"] + c["new_mr_raw"] + c["new_deriv"] > 0 or miss > 0:
                parts.append("MR: same exam, near-identical (LEONE adds Philips raw-data/derived objects)" if shared > 100 else "MR: same exam, LEONE holds a fragment")
            else:
                parts.append("MR: identical")
        elif c["mr_studies"]:
            parts.append("MR: NEW exam")
        if c["us_studies"]:
            parts.append("US: NEW exam" + (" (patient has no MR in DTS24)" if not acqs else " (different exam, same patient)"))
        w.writerow([p, ";".join(sorted(c["groups"])), ";".join(sorted(c["dates"])), ";".join(acqs), dn, shared, miss,
                    c["new_mr_img"], c["new_mr_raw"], c["new_us"], round(c["new_us_gb"], 2), c["new_deriv"], " + ".join(parts)])
rows = list(csv.DictReader(open(D + r"\case_table.csv", encoding="utf-8")))
print(len(rows), "cases")
print(collections.Counter(r["classification"] for r in rows))
for r in rows:
    print(r["case"], "|", r["LEONE_groups"][:60], "|", r["DTS24_acq"], r["DTS24_instances"], "shared", r["shared_unique_SOPs"], "miss", r["DTS24_missing_from_LEONE"],
          "newMR", r["new_MR_images"], "raw", r["new_MR_rawdata_objs"], "US", r["new_US"], r["new_US_GB"], "der", r["new_derivatives"], "|", r["classification"])
