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
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    total, failed = _checks
    print(f"\n{total - failed}/{total} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
