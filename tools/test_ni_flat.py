#!/usr/bin/env python3
"""test_ni_flat.py — the fan-in discovery for the S:\\gnuclear historical pull.

Run:  PYTHONPATH=tools python tools/test_ni_flat.py

Covers the behaviours that would silently corrupt the registry if they broke:
grouping per reconstruction, directory-independent identity (this source copies
one reconstruction into up to 48 folders), the frame-file naming that keeps a
flat-source acquisition shaped like a box-source one, cross-source dedup against
rows already in production, and the difference between "nothing here" and
"already ingested".
"""
import csv
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from ingest import ni_flat  # noqa: E402
import ni_gnuclear_discover as nd  # noqa: E402

_checks = [0, 0]


def check(cond, label):
    _checks[0] += 1
    if cond:
        print(f"  ok   {label}")
    else:
        _checks[1] += 1
        print(f"  FAIL {label}")


def touch(root, rel):
    p = os.path.join(root, rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(b"\x00" * 16)
    return p


def write_registry(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["acq_id", "acquisition_datetime", "instrument"])
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main():
    tmp = tempfile.mkdtemp(prefix="ni_flat_test_")
    try:
        src = os.path.join(tmp, "snap")

        # --- one reconstruction, four dynamic-PET frames, in a Frames/ tree
        base = "2026/Jesus/irene/0324/0324_m59_m60/Frames"
        for fr in (1, 2, 3, 4):
            touch(src, f"{base}/{fr}/20260212100620_PET_OSEM_1_frame{fr}_iter30.dcm")
        # --- a second, single-file reconstruction of the SAME scan
        touch(src, "2026/Jesus/irene/0324/0324_m59_m60/20260212100620_PET_OSEM_0.dcm")
        # --- the SAME reconstruction copied into a second analysis folder
        touch(src, "2026/Jesus/irene/0324/working copy/deep/20260212100620_PET_OSEM_0.dcm")
        # --- a CT with no protocol code anywhere in its path
        touch(src, "2026/Jesus/Jordi/Starget/68Ga_DOTA/260108/3219/0h/20260108143751_CT_ISRA_0.dcm")

        print("grouping + identity")
        m, idx, n = ni_flat.discover(src, require_project=False)
        keys = sorted(v["acq_key"] for v in idx.values())
        check(n == 7, f"saw all 7 DICOM files (got {n})")
        check(len(m) == 3, f"3 acquisitions, not 7 files (got {len(m)})")
        check(keys == ["20260108143751_CT_ISRA_0",
                       "20260212100620_PET_OSEM_0",
                       "20260212100620_PET_OSEM_1"], f"acquisition keys {keys}")

        recon1 = [v for v in idx.values() if v["acq_key"].endswith("OSEM_1")][0]
        check(len(recon1["members"]) == 4, "4 frames grouped into one reconstruction")
        check(sorted(x["dst"] for x in recon1["members"]) ==
              ["recon1_frame1.dcm", "recon1_frame2.dcm",
               "recon1_frame3.dcm", "recon1_frame4.dcm"],
              "frames get box-compatible .data/ names")

        recon0 = [v for v in idx.values() if v["acq_key"].endswith("OSEM_0")][0]
        check(len(recon0["members"]) == 1,
              "the same reconstruction copied into 2 folders stays ONE file")
        check(recon0["discovered"]["source_relpath"].count("/") == 5,
              "canonical copy is the shallowest path, not the working copy")

        print("\nthe two reconstructions of one scan are separate acquisitions")
        check(len([k for k in keys if k.startswith("20260212100620")]) == 2,
              "recon 0 and recon 1 are distinct acquisitions (per-recon model)")

        print("\nrequire_project")
        m2, idx2, _ = ni_flat.discover(src, require_project=True)
        check(all(not v["acq_key"].startswith("20260108") for v in idx2.values()),
              "an acquisition with no protocol code is held back")
        check(len(m2) == 2, f"2 acquisitions survive require_project (got {len(m2)})")

        print("\ncross-source dedup against the registry")
        reg = os.path.join(tmp, "registries", "registry_raw.csv")
        write_registry(reg, [{"acq_id": "ACQ-1",
                              "acquisition_datetime": "2026-02-12T10:06:20Z",
                              "instrument": "PET"}])
        m3, _idx3, n3 = ni_flat.discover(src, registry_path=reg, require_project=True)
        check(n3 == 7, "still walked every file")
        check(len(m3) == 0,
              "both reconstructions of an already-registered scan are skipped")
        check(m3 == [] and n3 > 0,
              "already-ingested is an empty result WITH files seen (a clean no-op, "
              "not an error)")

        print("\nempty source is distinguishable from already-ingested")
        empty = os.path.join(tmp, "empty")
        os.makedirs(empty)
        m4, _i4, n4 = ni_flat.discover(empty)
        check((m4, n4) == ([], 0), "empty source reports 0 files seen")

        print("\ndst_basename mapping")
        check(ni_flat.dst_basename("20260212100620_PET_OSEM_0.dcm", 0) == "recon0.dcm",
              "plain reconstruction -> recon0.dcm")
        check(ni_flat.dst_basename("20260212100620_PET_OSEM_1_frame7_iter30.dcm", 1)
              == "recon1_frame7.dcm", "per-frame -> recon1_frame7.dcm")
        check(ni_flat.dst_basename("20260212100620_PET_OSEM_0_frameMULTI_iter30.dcm", 0)
              == "recon0_frameMULTI.dcm", "the MULTI bundle keeps a distinct name")

        print("\nsubject/anchor parsing")
        r = nd.analyse("2022/Jesus/MOLECUBES/211217/245_2h30min/"
                       "20211217132857_CT/recon_0/20211217132857_CT_ISRA_0.dcm")
        check(r["subject_folder"] == "245_2h30min",
              "the machine anchor folder is not mistaken for the subject")
        r2 = nd.analyse("2023/Jesus/Ermal/dhp1/pet1/220307/RAT63/"
                        "20220307124919_PET_OSEM_0.dcm")
        check(r2["animals"] == "r63", "RAT63 normalises to the r63 animal form")
        r3 = nd.analyse("2024/Jesus/Marina/1321/140224/103/"
                        "20240214090459_CT_ISRA_0.dcm")
        check("date-off" not in r3["flags"],
              "DDMMYY folder dates are not flagged as decades off")

        # --- protocol-code validation (REVIEW_FINDINGS_2026-08-13 §1) ---------
        # Fixed fake code set; the real one comes from the facility DB.
        print("\nprotocol-code validation + walk-up recovery")
        VALID = {"0522", "1321", "0421", "0324", "1024", "1122"}

        a = nd.analyse("2023/Jesus/MJ/0522/230217-FDG/16/"
                       "20230217122714_PET_OSEM_0.dcm", valid_codes=VALID)
        check(a["project"] == "0522", "a DATE read as a code (2302) recovers to 0522")
        check("project-recovered:2302->0522" in a["flags"], "the repair is flagged, not silent")

        b = nd.analyse("2023/Jesus/Marina/1321/231120/100/Respiratory gated/"
                       "20231120090000_CT_ISRA_0.dcm", valid_codes=VALID)
        check(b["project"] == "1321", "an ANIMAL number read as a code (100) recovers to 1321")

        c = nd.analyse("2023/Jesus/Kepa/cancer/241/1 week/"
                       "20230711124726_SPECT_MLEM_0_iter50.dcm", valid_codes=VALID)
        check(c["project"] == "" and "project-rejected:241" in c["flags"],
              "no valid code anywhere -> rejected, not invented")

        # THE regression guard for the whole-segment rule: a looser prototype
        # rescued 245 -> 1217 by finding a 4-digit run INSIDE the date folder
        # 211217. That is the same guessing problem in a new place.
        d = nd.analyse("2022/Jesus/MOLECUBES/211217/245_2h30min/"
                       "20211217132857_CT_ISRA_0.dcm", valid_codes=VALID)
        check(d["project"] == "",
              "the date folder 211217 must NOT yield 1217 (whole segments only)")

        e = nd.analyse("2025/Jesus/Irene/250117_Ermal/0324_19/"
                       "20250117141509_PET_OSEM_0.dcm", valid_codes=VALID)
        check(e["project"] == "0324" and not any(
            f.startswith("project-") for f in e["flags"].split(",")),
            "an already-valid code passes through untouched and unflagged")

        # The AE_CODE_RE anchor: `AE-biomaGUNE-1317/PRO-AE-SS-101` yields 1317,
        # never 101. An unanchored match is the animal_db bug this run also fixes.
        check(nd.AE_CODE_RE.findall("AE-biomaGUNE-1317/PRO-AE-SS-101") == ["1317"],
              "AE_CODE_RE is anchored: 1317, not 101")

        # require_project must drop a rejected code the same as a missing one.
        src2 = os.path.join(tmp, "snap2")
        touch(src2, "2023/Jesus/Kepa/cancer/241/1 week/"
                    "20230711124726_SPECT_MLEM_0_iter50.dcm")
        touch(src2, "2025/Jesus/Irene/250117_Ermal/0324_19/"
                    "20250117141509_PET_OSEM_0.dcm")
        _real = nd.valid_protocol_codes
        nd.valid_protocol_codes = lambda conn=None: VALID
        try:
            m5, idx5, _n5 = ni_flat.discover(src2, require_project=True)
        finally:
            nd.valid_protocol_codes = _real
        check(len(m5) == 1, "a rejected code is held back like a missing one")
        check(list(idx5.values())[0]["discovered"]["source_relpath"].startswith("2025/"),
              "the surviving acquisition is the one with a real protocol code")

        # REGRESSION: the validated code must be PUBLISHED in discovered, because
        # expand_batch's subject_parse block re-derives `project` from the raw
        # grammar unless the key is already present (it uses setdefault). Missing
        # this wrote AE-biomaGUNE-2302 into a sandbox registry while every count
        # still verified — analyse() decides what is HELD BACK, subject_parse
        # decided what got WRITTEN. Assert on the value the registry actually sees.
        print("\ndiscovered.project is the validated code (the ingest seam)")
        src3 = os.path.join(tmp, "snap3")
        touch(src3, "2023/Jesus/MJ/0522/2302-PAH male/230217-FDG/21/"
                    "20230220093623_PET_OSEM_0.dcm")
        nd.valid_protocol_codes = lambda conn=None: VALID
        try:
            _m6, idx6, _n6 = ni_flat.discover(src3, require_project=True)
        finally:
            nd.valid_protocol_codes = _real
        d6 = list(idx6.values())[0]["discovered"]
        check(d6.get("project") == "0522",
              f"discovered.project is the RECOVERED 0522, not 2302 (got {d6.get('project')!r})")
        check("project" in d6,
              "the project key exists so subject_parse's setdefault cannot override it")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    total, failed = _checks
    print(f"\n{total - failed}/{total} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
