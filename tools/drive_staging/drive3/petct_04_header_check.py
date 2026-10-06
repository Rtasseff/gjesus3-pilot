"""Stream N, step 3: headers against names (read-only analysis of out\\acq_headers.csv).

For every drive reconstruction:
  - the file-name timestamp vs the header AcquisitionDateTime (and StudyDate+StudyTime);
  - the folder's animal vs the header PatientID and the animal at the head of SeriesDescription;
  - the claimed protocol (A1's claim, pet_claims.csv; for the 290 the production project) vs
    StudyDescription and the protocol in PatientName "<operator>^/ <protocol> / <yymmdd>".
Prints every disagreement; writes out\\acq_header_check.csv.
"""
import collections
import csv
import os
import re
import sys

sys.dont_write_bytecode = True
csv.field_size_limit(2 ** 31 - 1)
OUT = r"D:\projects\gjesus3\drive3_streams\petct\out"
A1 = r"D:\projects\gjesus3\drive3_analysis\a1"
ANIMAL_DIR = re.compile(r"^(?:[mMrR])?0*(\d{1,4})$")


def folder_animal(relpath):
    """The animal folder: the nearest folder above the file that is a bare number (or m/r+number)."""
    segs = relpath.split("\\")[:-1]
    for s in reversed(segs):
        m = ANIMAL_DIR.match(s.strip())
        if m:
            return m.group(1)
        m2 = re.match(r"^(\d{1,4})\s+\S", s.strip())        # e.g. "173 FALTA"
        if m2:
            return m2.group(1) + "?"
    return ""


def main():
    hdr = list(csv.DictReader(open(os.path.join(OUT, "acq_headers.csv"), encoding="utf-8", newline="")))
    inv = {r["acq_key"]: r for r in csv.DictReader(open(os.path.join(OUT, "acq_inventory.csv"), encoding="utf-8", newline=""))}
    claims = {}
    for r in csv.DictReader(open(os.path.join(A1, "pet_claims.csv"), encoding="utf-8", newline="")):
        claims[r["ni_key"]] = r
    rows = []
    for h in hdr:
        k = h["acq_key"]
        ts = k[:14]
        adt = re.sub(r"\D", "", h["AcquisitionDateTime"])[:14]
        sdt = (h["StudyDate"] + re.sub(r"\D", "", h["StudyTime"])[:6])
        fa = folder_animal(h["canonical_drive_relpath"])
        pid = h["PatientID"].strip()
        sd_an = (re.match(r"^\s*([^/]+?)\s*/", h["SeriesDescription"]) or [None, ""])[1]
        sd_an_num = re.sub(r"^\d{4}_", "", sd_an)                     # "1123_23" -> "23"
        pn = h["PatientName"]
        pn_m = re.match(r"^\s*([^\^/]*)\^?/?\s*([^/]*?)\s*/\s*(\d{6})?", pn)
        pn_op = pn_m.group(1).strip() if pn_m else ""
        pn_proto = pn_m.group(2).strip() if pn_m else ""
        pn_date = (pn_m.group(3) or "") if pn_m else ""
        cl = claims.get(k, {})
        claim = cl.get("claim_code", "")
        problems = []
        if adt != ts:
            problems.append(f"ts {ts} != AcquisitionDateTime {adt}")
        if sdt != ts:
            problems.append(f"StudyDate+Time {sdt}")
        fa_n = fa.rstrip("?")
        if fa and pid and pid.lstrip("0") != fa_n.lstrip("0"):
            problems.append(f"folder animal {fa} != PatientID {pid}")
        if fa and sd_an_num and sd_an_num.lstrip("0") != fa_n.lstrip("0"):
            problems.append(f"folder animal {fa} != SeriesDescription head {sd_an}")
        if claim and h["StudyDescription"] and h["StudyDescription"].strip() != claim:
            problems.append(f"claim {claim} != StudyDescription {h['StudyDescription']}")
        if claim and pn_proto and pn_proto != claim:
            problems.append(f"claim {claim} != PatientName protocol {pn_proto!r}")
        if pn_date and pn_date != ts[2:8]:
            problems.append(f"PatientName date {pn_date} != {ts[2:8]}")
        rows.append({"acq_key": k, "coverage": h["coverage"], "relpath": h["canonical_drive_relpath"],
                     "ts": ts, "AcquisitionDateTime": adt, "folder_animal": fa, "PatientID": pid,
                     "SeriesDescription": h["SeriesDescription"], "StudyDescription": h["StudyDescription"],
                     "PatientName": pn, "console_user": pn_op, "pn_protocol": pn_proto, "pn_date": pn_date,
                     "claim": claim, "claim_verdict": cl.get("verdict", ""), "model": h["ManufacturerModelName"],
                     "modality_hdr": h["Modality"], "StudyInstanceUID": h["StudyInstanceUID"],
                     "PatientWeight": h["PatientWeight"], "dose": h["RadionuclideTotalDose"],
                     "frames": h["NumberOfFrames"], "problems": "; ".join(problems)})
    with open(os.path.join(OUT, "acq_header_check.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    for cov in ("NEW", "only", "in production"):
        sub = [r for r in rows if r["coverage"].startswith(cov)]
        bad = [r for r in sub if r["problems"]]
        print(f"\n=== {cov}: {len(sub)} acquisitions, {len(bad)} with a disagreement")
        print("  console users:", collections.Counter(r["console_user"] for r in sub).most_common())
        print("  models:", collections.Counter((r["modality_hdr"], r["model"]) for r in sub).most_common())
        for r in bad:
            print(f"  {r['acq_key']:28s} {r['relpath'][-70:]:70s} | {r['problems']}")
    # PET+CT of one visit: one StudyInstanceUID?
    by_study = collections.defaultdict(list)
    for r in rows:
        by_study[r["StudyInstanceUID"]].append(r)
    shapes = collections.Counter(tuple(sorted(x["modality_hdr"] for x in v)) for v in by_study.values())
    print("\nStudyInstanceUID groups (modalities per study):", shapes.most_common())


if __name__ == "__main__":
    main()
