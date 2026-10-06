"""Stream N, step 0: dated read-only copies of the live registries and the snapshot manifest.

Reads J:\\gjesus3-data\\registries\\*.csv (+ .acq_id_seq.json) and the S:\\gnuclear snapshot's
_manifest.jsonl; writes copies + SNAPSHOT.txt (SHA-256 of each source, taken twice to
detect a concurrent write) under D:\\projects\\gjesus3\\drive3_streams\\petct\\out\\_inputs\\<stamp>\\.
Nothing on J: is opened for writing.
"""
import datetime
import hashlib
import os
import shutil
import sys

sys.dont_write_bytecode = True
REG = r"J:\gjesus3-data\registries"
SNAP_MANIFEST = r"J:\gjesus3-data\staging\ni_gnuclear_20260812\_manifest.jsonl"
OUT = r"D:\projects\gjesus3\drive3_streams\petct\out\_inputs"
FILES = ["registry_raw.csv", "registry_projects.csv", "registry_subjects.csv", "retired_acquisitions.csv",
         "pending_subject_metadata.csv", "pending_dicom_regen.csv", "ingest_manifest.csv",
         "registry_datasets.csv", ".acq_id_seq.json"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(8 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = os.path.join(OUT, stamp)
    os.makedirs(dst, exist_ok=False)
    lines = [f"taken {stamp} (local time) from {REG} and {SNAP_MANIFEST}"]
    srcs = [os.path.join(REG, n) for n in FILES] + [SNAP_MANIFEST]
    for s in srcs:
        if not os.path.exists(s):
            lines.append(f"MISSING {s}")
            continue
        h1 = sha(s)
        d = os.path.join(dst, os.path.basename(s))
        shutil.copyfile(s, d)
        h2 = sha(s)
        hd = sha(d)
        ok = "OK" if h1 == h2 == hd else "CHANGED-DURING-COPY"
        lines.append(f"{ok} {os.path.basename(s)} {os.path.getsize(d)} {hd}")
    with open(os.path.join(dst, "SNAPSHOT.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(dst)


if __name__ == "__main__":
    main()
