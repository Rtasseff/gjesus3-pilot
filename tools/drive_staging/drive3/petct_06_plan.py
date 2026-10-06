"""Stream N, step 5: the per-acquisition plan for the 202, with its evidence (read-only; facility DB SELECT).

One row per acquisition the drive holds and production lacks (A1 section 4):
  source          'snapshot' (the 100 also in J:\\gjesus3-data\\staging\\ni_gnuclear_20260812, byte-identical
                  to the drive; ingested from there) or 'drive' (the 102 found nowhere else; staged to D:)
  source_rel      the path the ingest discovers: the snapshot rel, or the staged rel
                  <year>/Jesus/MJ/<drive relpath, '/'-separated> (the two renamed files get the scanner's name)
  discovered_*    what this branch's ni_gnuclear_discover.analyse() derives from source_rel (DB code set)
  evidence        the folder claim (A1), the header (PatientID / protocol / console user), the facility DB
                  (is (project, animal) found, and what does it log within 3 days of the scan)
  decision        project / subject / animal / sample_type / researcher / note, as the case tables carry them

Also writes, for the dedup-proof staging, the staged rel of every other drive reconstruction (the 290 in
production and the drive copies of the 100). Outputs: out\\plan_202.csv, out\\plan_stage_all.csv.
"""
import collections
import csv
import datetime as dt
import os
import re
import sys

sys.dont_write_bytecode = True
csv.field_size_limit(2 ** 31 - 1)
WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))      # the repository root (tools/drive_staging/drive3/<this>)
sys.path.insert(0, os.path.join(WT, "tools"))
import animal_db  # noqa: E402
import ni_gnuclear_discover as nd  # noqa: E402

OUT = r"D:\projects\gjesus3\drive3_streams\petct\out"
A1 = r"D:\projects\gjesus3\drive3_analysis\a1"
RESEARCHER = "MJ"          # M. Jesus: the drive's owner; production's token for her S:\gnuclear folder (216 rows)
PHANTOM = "20220518123914_PET_OSEM_0"


def staged_rel(acq_key, drive_rel):
    """<year>/Jesus/MJ/<drive relpath> with the file named as the scanner names it."""
    parts = drive_rel.split("\\")
    fname = parts[-1]
    if not nd.DCM_RE.match(fname):
        fname = f"{acq_key}.dcm"            # the renamed reconstructions (key rebuilt below)
    return "/".join([acq_key[:4], "Jesus", RESEARCHER] + parts[:-1] + [fname])


def header_animal(pid):
    """'1123_23' -> 23, '0522-80-FDG' -> 80, '173' -> 173; '' when not a number."""
    s = pid.strip()
    m = re.match(r"^(?:\d{4}[_-])?0*(\d{1,4})(?:[-_ ].*)?$", s)
    return m.group(1) if m else ""


def header_protocol(study_desc, valid):
    m = re.match(r"^\s*(\d{4})(?:[-_ ]|$)", study_desc or "")
    return m.group(1) if (m and m.group(1) in valid) else ""


def main():
    inv = {r["acq_key"]: r for r in csv.DictReader(open(os.path.join(OUT, "acq_inventory.csv"), encoding="utf-8"))}
    hdr = {r["acq_key"]: r for r in csv.DictReader(open(os.path.join(OUT, "acq_header_check.csv"), encoding="utf-8"))}
    claims = {r["ni_key"]: r for r in csv.DictReader(open(os.path.join(A1, "pet_claims.csv"), encoding="utf-8"))}

    # The two renamed reconstructions: algorithm from the header, recon index from the session's siblings.
    renamed = {k: v for k, v in inv.items() if "(renamed)" in k}
    rekey = {}
    for k, v in renamed.items():
        ts, mod = k[:14], k.split("_")[1]
        algo = hdr[k]["SeriesDescription"].split("/")[-1].strip().upper()
        sib = [x for x in inv if x[:8] == ts[:8] and "(renamed)" not in x and x.split("_")[1] == mod
               and x.split("_")[2] == algo]
        idx = {x.split("_")[3] for x in sib}
        assert len(idx) == 1, (k, sib)
        rekey[k] = f"{ts}_{mod}_{algo}_{idx.pop()}"
        assert rekey[k] not in inv, rekey[k]

    conn = animal_db.get_connection()
    try:
        valid = nd.valid_protocol_codes(conn)
        rows = []
        stage_all = []
        for key0, r in sorted(inv.items()):
            key = rekey.get(key0, key0)
            cov = r["coverage"]
            drive_rel = r["canonical_drive_relpath"]
            srel = staged_rel(key, drive_rel)
            stage_all.append({"acq_key": key, "coverage": cov, "drive_relpath": drive_rel, "staged_rel": srel,
                              "sha256": r["sha256"], "size": r["size"]})
            if cov.startswith("in production"):
                continue
            source = "snapshot" if cov.startswith("only in the S") else "drive"
            source_rel = r["snapshot_rels"] if source == "snapshot" else srel
            a = nd.analyse(source_rel, 0, valid)
            assert a and a["acq_key"] == key, (key, source_rel, a and a["acq_key"])
            h = hdr[key0]
            cl = claims.get(key0, {})
            claim = cl.get("claim_code", "")
            f_animal = (re.match(r"^\s*0*(\d+)", h["folder_animal"]) or [None, ""])[1]
            h_animal = header_animal(h["PatientID"])
            h_proto = header_protocol(h["StudyDescription"], valid)
            user = h["console_user"]

            # --- decision ---------------------------------------------------------------------------
            sample_type, researcher = "organism", a["researcher"]
            project, animal, subject = claim, f_animal, f_animal
            notes = []
            if key == PHANTOM:
                sample_type, project, animal, researcher = "phantom", "", "", ""
                subject = "phantom_18F_20ml"
                notes.append("NOT an animal: an 18F phantom (20 ml) scanned by the NI platform (DICOM: console "
                             "user unai, StudyDescription '18f phantom', PatientID '20ml', weight 0.001 kg), "
                             "filed in animal 201's folder of 0619 BrEt PAH 220518")
            if key0 in renamed:
                notes.append(f"renamed on the drive as {drive_rel.split(chr(92))[-1]}; the scanner's name "
                             f"{key} is rebuilt from the header (AcquisitionDateTime, Modality, algorithm) "
                             f"with recon index {key.split('_')[3]} from the session's other reconstructions")
            if sample_type == "organism" and h_animal and h_animal != animal:
                notes.append(f"DICOM PatientID {h['PatientID']} disagrees with the folder's animal {animal}; "
                             f"registered under the folder's animal (both logged a PET that day)")
            if sample_type == "organism" and h_proto and h_proto != project and h_proto != "1207":
                notes.append(f"protocol typed {h_proto} at the console; the facility DB confirms {project}/"
                             f"{animal} (not {h_proto}/{animal}) for this scan")
            if a["subject_folder"] != subject and sample_type == "organism":
                notes.append(f"subject folder '{a['subject_folder']}' is not an animal number; the animal is "
                             f"the folder above it ({animal}), as the header says ({h['PatientID']})"
                             if a["subject_folder"].lower() == "gated" else
                             f"subject folder '{a['subject_folder']}'; the animal is {animal} (header "
                             f"PatientID {h['PatientID']})")
            if "234628" in h["PatientName"]:
                notes.append("the console's protocol and date fields were typed as '234628' / '1422'")
            notes.append(f"DICOM console user: {user}")

            # --- facility DB --------------------------------------------------------------------------
            db = ""
            if sample_type == "organism":
                res = animal_db.lookup(project, int(animal), conn=conn, use_cache=False)
                if res.status == "unreachable":
                    raise SystemExit("facility DB unreachable")
                if res.status != "found":
                    db = f"NOT FOUND {project}/{animal}"
                else:
                    t = dt.date(int(key[:4]), int(key[4:6]), int(key[6:8]))
                    near = []
                    for pr in res.subject.get("procedures", []):
                        try:
                            d = dt.date.fromisoformat(str(pr["date"])[:10])
                        except ValueError:
                            continue
                        if abs((d - t).days) <= 3:
                            near.append(f"{pr['type']}@{d}")
                    db = (f"found {res.subject['facility_animal_id']} ({res.subject['species']}); "
                          + ("; ".join(near) if near else "NOTHING logged within 3 days"))

            rows.append({
                "acq_key": key, "acq_key_a1": key0, "source": source, "source_rel": source_rel,
                "drive_relpath": drive_rel, "sha256": r["sha256"], "size": r["size"],
                "modality": key.split("_")[1], "acq_date": key[:8],
                "discovered_project": a["project"], "discovered_subject": a["subject_folder"],
                "discovered_animals": a["animals"], "discovered_flags": a["flags"],
                "a1_claim": claim, "a1_verdict": cl.get("verdict", ""),
                "folder_animal": h["folder_animal"], "hdr_PatientID": h["PatientID"],
                "hdr_StudyDescription": h["StudyDescription"], "hdr_PatientName": h["PatientName"],
                "hdr_console_user": user, "hdr_model": h["model"], "hdr_AcquisitionDateTime": h["AcquisitionDateTime"],
                "db_evidence": db,
                "project": project, "project_name": f"AE-biomaGUNE-{project}" if project else "",
                "subject": subject, "animal_codes": animal, "sample_type": sample_type,
                "researcher_folder": researcher, "note": "; ".join(notes) + ".",
            })
    finally:
        conn.close()

    with open(os.path.join(OUT, "plan_202.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(OUT, "plan_stage_all.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(stage_all[0].keys()))
        w.writeheader()
        w.writerows(stage_all)

    print(f"planned: {len(rows)}  by source: {collections.Counter(r['source'] for r in rows)}")
    print("renamed:", rekey)
    print("by source x project:", sorted(collections.Counter((r["source"], r["project"]) for r in rows).items()))
    print("sample types:", collections.Counter(r["sample_type"] for r in rows))
    mism = [r for r in rows if r["sample_type"] == "organism" and r["discovered_project"] != r["project"]]
    print(f"discovered project != decided project: {len(mism)}")
    for r in mism:
        print(f"   {r['acq_key']} {r['source']} discovered={r['discovered_project']!r} decided={r['project']} "
              f"({r['source_rel']})")
    anim = [r for r in rows if r["sample_type"] == "organism"
            and r["discovered_animals"].lstrip("mr").lstrip("0") != r["animal_codes"]]
    print(f"discovered animal != decided animal: {len(anim)}")
    for r in anim:
        print(f"   {r['acq_key']} discovered={r['discovered_animals']!r} subject={r['discovered_subject']!r} "
              f"decided={r['animal_codes']}")
    print("DB:", collections.Counter((r["db_evidence"].split(";")[0][:5] if r["db_evidence"] else "(phantom)")
                                     for r in rows))
    weak = [r for r in rows if r["sample_type"] == "organism" and ("NOT" in r["db_evidence"])]
    print(f"DB not confirming: {len(weak)}")
    for r in weak:
        print("   ", r["acq_key"], r["db_evidence"])
    print("notes beyond the console user:")
    for r in rows:
        if r["note"].count(";") > 0:
            print(f"   {r['acq_key']}: {r['note'][:220]}")


if __name__ == "__main__":
    main()
