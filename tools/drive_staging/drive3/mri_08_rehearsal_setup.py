"""Stream M: build the rehearsal NAS root on D: from live production (read-only on J:).

    python mri_08_rehearsal_setup.py [--fresh]

D:\\projects\\gjesus3\\drive3_streams\\mri\\rehearsal_nas\\
  registries\\   byte copies of every file of production's registries\\ (registry_raw, _projects, _subjects, retired,
                 pending_*, ingest_manifest, datasets, .acq_id_seq.json, ...): ACQ-IDs, dedup and project resolution
                 then behave exactly as in production
  projects\\<p>\\  the six target projects: their four subfolders, _project.yaml and provenance.csv (copied, so the
                 appended provenance rows are what production would get), and raw_linked\\ seeded with EMPTY folders
                 of production's link names (so a taken name is refused here exactly as there)
  raw\\          empty
Writes rehearsal_nas\\_SETUP.txt with the SHA-256 of every copied file.
"""
import datetime
import hashlib
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mri_common as C  # noqa: E402

PROJECTS = ["AE-biomaGUNE-0118", "AE-biomaGUNE-0619", "AE-biomaGUNE-1019", "AE-biomaGUNE-0320",
            "AE-biomaGUNE-1116", "AE-biomaGUNE-0522"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(8 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    if os.path.exists(C.REH):
        if "--fresh" not in sys.argv:
            raise SystemExit(f"{C.REH} exists; pass --fresh to rebuild it")
        assert os.path.abspath(C.REH).lower() == r"d:\projects\gjesus3\drive3_streams\mri\rehearsal_nas"
        shutil.rmtree(C.REH)
    lines = [f"built {datetime.datetime.now().isoformat(timespec='seconds')} from {C.NAS} (read-only)"]
    os.makedirs(os.path.join(C.REH, "registries"))
    os.makedirs(os.path.join(C.REH, "raw"))
    src_reg = os.path.join(C.NAS, "registries")
    for n in sorted(os.listdir(src_reg)):
        s, d = os.path.join(src_reg, n), os.path.join(C.REH, "registries", n)
        if not os.path.isfile(s):
            continue
        h1 = sha(s)
        shutil.copyfile(s, d)
        assert sha(d) == h1 == sha(s), f"{n} changed while copied: re-run"
        lines.append(f"registries/{n} {os.path.getsize(d)} {h1}")
    for p in PROJECTS:
        src = os.path.join(C.NAS, "projects", p)
        dst = os.path.join(C.REH, "projects", p)
        for sub in ("metadata", "outputs", "raw_linked", "working"):
            os.makedirs(os.path.join(dst, sub))
        for n in ("_project.yaml", "provenance.csv"):
            if os.path.exists(os.path.join(src, n)):
                shutil.copyfile(os.path.join(src, n), os.path.join(dst, n))
                lines.append(f"projects/{p}/{n} {os.path.getsize(os.path.join(dst, n))} {sha(os.path.join(dst, n))}")
        names = os.listdir(os.path.join(src, "raw_linked"))
        for n in names:
            os.makedirs(os.path.join(dst, "raw_linked", n))
        lines.append(f"projects/{p}/raw_linked: {len(names)} production names seeded as empty folders")
    open(os.path.join(C.REH, "_SETUP.txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
