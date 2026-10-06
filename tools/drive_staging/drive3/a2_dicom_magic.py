#!/usr/bin/env python3
"""a2_dicom_magic.py -- are the extension-less IM_####/XX_####/PS_####/DICOMDIR files really DICOM?

Reads 132 bytes of each candidate from the staged copy (read-only open) and checks the `DICM` preamble
marker at offset 128. Also checks every other extension-less file that is neither a ParaVision/TopSpin
name nor junk, so nothing extension-less is classified by its name alone.

    python tools/drive_staging/drive3/a2_dicom_magic.py      -> a2\\dicom_magic.csv
"""
import concurrent.futures as cf
import os
import re

import a2_common as C


def magic(rel):
    p = C.LONG + os.path.join(C.STAGED, rel)
    try:
        with open(p, "rb") as f:
            head = f.read(132)
        return "Y" if head[128:132] == b"DICM" else "N", ""
    except OSError as e:
        return "?", f"{type(e).__name__}: {e}"


def main():
    C.stdout_utf8()
    rows = C.load_manifest()
    cands = []
    for r in rows:
        name = r["relpath"].split("\\")[-1]
        low = name.lower()
        if C.file_ext(name):
            continue
        if low in C.BRUKER_NAMES or C.BRUKER_RE.match(low) or C.PARAVISION_RE.match(low):
            continue
        if low in C.JUNK_RULED or name.startswith("._") or low in ("icon\r", "icon"):
            continue
        if r["size"] < 132:
            continue
        cands.append(r)
    C.say(f"extension-less candidates: {len(cands)}")
    out = []
    with cf.ThreadPoolExecutor(8) as ex:
        for r, (m, err) in zip(cands, ex.map(lambda x: magic(x["relpath"]), cands)):
            out.append({"relpath": r["relpath"], "size": r["size"], "dicm": m, "error": err,
                        "named_like_dicom": "Y" if C.DICOM_NAME_RE.match(r["relpath"].split("\\")[-1]) else "N"})
    C.wcsv(C.out_path("dicom_magic.csv"), ["relpath", "size", "dicm", "named_like_dicom", "error"], out)
    tab = {}
    for o in out:
        k = (o["named_like_dicom"], o["dicm"])
        tab[k] = tab.get(k, 0) + 1
    for k, n in sorted(tab.items()):
        C.say(f"  named_like_dicom={k[0]} dicm={k[1]}: {n}")
    for o in out:
        if o["named_like_dicom"] == "N" and o["dicm"] == "Y":
            C.say("  DICOM without a DICOM-like name:", o["relpath"])


if __name__ == "__main__":
    main()
