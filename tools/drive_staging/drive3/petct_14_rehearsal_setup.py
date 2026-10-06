"""Stream N: build the rehearsal NAS root on D: from live production (read-only on J:).

    python petct_14_rehearsal_setup.py [--fresh]

D:\\projects\\gjesus3\\drive3_streams\\petct\\rehearsal_nas\\
  registries\\   byte copies of production's registries (registry_raw, _projects, _subjects, retired,
                 pending_*, ingest_manifest, datasets, .acq_id_seq.json): the ACQ-IDs, the dedup and the
                 project resolution then behave exactly as they would in production
  projects\\<p>\\  the five target projects: their four subfolders, _project.yaml and provenance.csv
                 (copied, so the appended provenance rows are what production would get); raw_linked\\ starts
                 empty (production's own raw_linked was checked by the dry run's link pre-flight)
  raw\\          empty
Writes rehearsal_nas\\_SETUP.txt with the SHA-256 of every copied file.
"""
import datetime
import hashlib
import os
import shutil
import sys

sys.dont_write_bytecode = True
PROD = r"J:\gjesus3-data"
REH = r"D:\projects\gjesus3\drive3_streams\petct\rehearsal_nas"
REGS = ["registry_raw.csv", "registry_projects.csv", "registry_subjects.csv", "retired_acquisitions.csv",
        "pending_subject_metadata.csv", "pending_dicom_regen.csv", "ingest_manifest.csv",
        "registry_datasets.csv", ".acq_id_seq.json"]
PROJECTS = ["AE-biomaGUNE-0619", "AE-biomaGUNE-0320", "AE-biomaGUNE-1019", "AE-biomaGUNE-1123",
            "AE-biomaGUNE-1422"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(8 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    if os.path.exists(REH):
        if "--fresh" not in sys.argv:
            raise SystemExit(f"{REH} exists; pass --fresh to rebuild it")
        assert os.path.abspath(REH).lower() == r"d:\projects\gjesus3\drive3_streams\petct\rehearsal_nas"
        shutil.rmtree(REH)
    lines = [f"built {datetime.datetime.now().isoformat(timespec='seconds')} from {PROD} (read-only)"]
    os.makedirs(os.path.join(REH, "registries"))
    os.makedirs(os.path.join(REH, "raw"))
    for n in REGS:
        s, d = os.path.join(PROD, "registries", n), os.path.join(REH, "registries", n)
        h1 = sha(s)
        shutil.copyfile(s, d)
        assert sha(d) == h1 == sha(s), n
        lines.append(f"registries/{n} {os.path.getsize(d)} {h1}")
    for p in PROJECTS:
        src = os.path.join(PROD, "projects", p)
        dst = os.path.join(REH, "projects", p)
        for sub in ("metadata", "outputs", "raw_linked", "working"):
            os.makedirs(os.path.join(dst, sub))
        for n in ("_project.yaml", "provenance.csv"):
            if os.path.exists(os.path.join(src, n)):
                shutil.copyfile(os.path.join(src, n), os.path.join(dst, n))
                lines.append(f"projects/{p}/{n} {os.path.getsize(os.path.join(dst, n))} {sha(os.path.join(dst, n))}")
    with open(os.path.join(REH, "_SETUP.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
