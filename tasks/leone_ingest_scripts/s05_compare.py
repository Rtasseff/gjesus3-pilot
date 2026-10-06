"""LEONE vs DTS24, member by member (SOPInstanceUID first, SHA-256 second).

Groups LEONE members by SOURCE GROUP (where in LEONE.zip they sit) so LIONS case
folders, CNIC/MR, CNIC/ECO, ExportLeone and each nested Leone-*.zip stay separate.
Writes outputs to the D: analysis folder (no identifiers in any of them).
"""
import csv, collections, re
S = r"C:\Users\rtasseff\temp\scratch_leone-ingest"
O = r"D:\projects\gjesus3\staging\_analysis\leone-ingest"
csv.field_size_limit(10**8)

# ---- DTS24 index
dts = {}  # sop -> (acq, sha, study, pid)
dts_by_acq = collections.Counter()
dts_study_acq = {}
for r in csv.DictReader(open(S + r"\dts24_sop_index.csv", encoding="utf-8")):
    dts[r["SOPInstanceUID"]] = (r["acq_id"], r["sha256"], r["StudyInstanceUID"], r["PatientID"])
    dts_by_acq[r["acq_id"]] += 1
    dts_study_acq[r["StudyInstanceUID"]] = r["acq_id"]
print("DTS24 sops", len(dts))


def group_of(m):
    if "!/" in m:
        return "NESTED " + m.split("!/")[0].split("/")[-1]
    p = m.split("/")
    if len(p) < 3:
        return "ROOT-FILES"
    if p[1] == "CNIC" and len(p) > 3:
        return "CNIC/" + p[2]
    if p[1] == "ExportLeone":
        return "ExportLeone"
    return p[1]


# ---- LEONE scan
L = list(csv.DictReader(open(S + r"\leone.csv", encoding="utf-8")))
print("LEONE rows", len(L))
nondicom = collections.Counter()
nd_rows = []
leone_sops = collections.defaultdict(list)  # sop -> [(group, sha)]
# per (group, pid, study)
agg = collections.defaultdict(lambda: {"n": 0, "bytes": 0, "series": set(), "in_dts_same": 0,
                                       "in_dts_diffsha": 0, "only_leone": 0, "dts_acq": set(),
                                       "date": set(), "mods": collections.Counter(), "dup_in_leone": 0})
for r in L:
    g = group_of(r["member"])
    if r["is_dicom"] != "1":
        name = r["member"].rsplit("/", 1)[-1]
        kind = ("NESTED_ZIP" if r["note"] == "NESTED_ZIP" else
                "appledouble ._*" if name.startswith("._") else
                ".DS_Store" if name == ".DS_Store" else
                "DICOMDIR" if name == "DICOMDIR" else
                "DIRFILE" if name == "DIRFILE" else
                (name.rsplit(".", 1)[-1].lower() if "." in name else "no-ext:" + name[:12]))
        nondicom[(g, kind)] += 1
        nd_rows.append([g, kind, r["member"], r["size"], r["sha256"], r["note"]])
        continue
    sop = r["SOPInstanceUID"]
    seen_before = sop in leone_sops
    leone_sops[sop].append((g, r["sha256"]))
    k = (g, r["PatientID"], r["StudyInstanceUID"])
    a = agg[k]
    a["n"] += 1; a["bytes"] += int(r["size"] or 0); a["series"].add(r["SeriesInstanceUID"])
    a["date"].add(r["StudyDate"]); a["mods"][r["Modality"]] += 1
    if seen_before:
        a["dup_in_leone"] += 1
    d = dts.get(sop)
    if d:
        a["dts_acq"].add(d[0])
        if d[1] == r["sha256"]:
            a["in_dts_same"] += 1
        else:
            a["in_dts_diffsha"] += 1
    else:
        a["only_leone"] += 1

with open(O + r"\compare_by_group_case_study.csv", "w", newline="", encoding="utf-8") as g:
    w = csv.writer(g)
    w.writerow(["group", "PatientID", "StudyInstanceUID", "StudyDate", "modalities", "instances", "GB",
                "series", "in_DTS24_same_sha", "in_DTS24_diff_sha", "only_in_LEONE", "dup_within_LEONE",
                "DTS24_acq", "DTS24_acq_of_study"])
    for k in sorted(agg, key=lambda k: (k[0], k[1], sorted(agg[k]["date"]))):
        a = agg[k]
        w.writerow([k[0], k[1], k[2], ";".join(sorted(a["date"])), dict(a["mods"]), a["n"],
                    round(a["bytes"] / 1e9, 3), len(a["series"]), a["in_dts_same"], a["in_dts_diffsha"],
                    a["only_leone"], a["dup_in_leone"], ";".join(sorted(a["dts_acq"])),
                    dts_study_acq.get(k[2], "")])

with open(O + r"\leone_nondicom_members.csv", "w", newline="", encoding="utf-8") as g:
    w = csv.writer(g); w.writerow(["group", "kind", "member", "size", "sha256", "note"]); w.writerows(nd_rows)

# ---- DTS24 members missing from LEONE, per acq
miss = collections.Counter()
for sop, (acq, sha, st, pid) in dts.items():
    if sop not in leone_sops:
        miss[acq] += 1
with open(O + r"\dts24_missing_from_leone.csv", "w", newline="", encoding="utf-8") as g:
    w = csv.writer(g); w.writerow(["acq_id", "dts24_instances", "missing_from_LEONE"])
    for acq in sorted(dts_by_acq):
        w.writerow([acq, dts_by_acq[acq], miss[acq]])

# ---- unique-SOP summary per group
print("\nLEONE unique SOPs", len(leone_sops))
grp = collections.defaultdict(lambda: collections.Counter())
for sop, lst in leone_sops.items():
    gs = {g for g, _ in lst}
    for g in gs:
        c = grp[g]; c["unique_sops"] += 1
        if sop in dts:
            c["in_dts"] += 1
            c["in_dts_same_sha"] += any(s == dts[sop][1] for gg, s in lst if gg == g)
        else:
            c["new"] += 1
        if len(gs) > 1:
            c["also_in_other_LEONE_group"] += 1
for g in sorted(grp):
    print(f"{g:28} {dict(grp[g])}")
print("\nLEONE SOPs not in DTS24:", sum(1 for s in leone_sops if s not in dts))
print("DTS24 SOPs not in LEONE:", sum(miss.values()), "across", sum(1 for a in miss if miss[a]), "acqs")
print("\nnon-DICOM by group/kind:")
for k, v in sorted(nondicom.items()):
    print(f"  {v:6d} {k}")
