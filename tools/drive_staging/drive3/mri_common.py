"""Stream M (the M. Jesus drive's MRI, and the CNIC pig images): shared paths and helpers.

READ-ONLY on J:\\ (production and the staged copy J:\\_staging_drive3_MJ\\) and on K:\\. Every
script of stream M writes only under D:\\projects\\gjesus3\\drive3_streams\\mri\\ (w() refuses
anything else), except the ingest itself, which writes only to the --nas-root it is given.

Gate document: tasks/drive3_mri_gate.md. Assessment: tasks/drive3_raw_coverage.md (A1) and
tasks/drive3_segmentations_cds.md (A3), whose outputs are read from D:\\projects\\gjesus3\\drive3_analysis\\.
"""
import csv
import hashlib
import io
import os
import sys

sys.dont_write_bytecode = True
csv.field_size_limit(2 ** 31 - 1)

BASE = r"D:\projects\gjesus3\drive3_streams\mri"
OUT = os.path.join(BASE, "out")
STAGE = os.path.join(BASE, "stage")
REH = os.path.join(BASE, "rehearsal_nas")
A1 = r"D:\projects\gjesus3\drive3_analysis\a1"
A3 = r"D:\projects\gjesus3\drive3_analysis\a3"
MANIFEST = r"D:\projects\gjesus3\drive3_analysis\drive3_manifest.csv"   # == J:\_staging_drive3_MJ\...\manifest.csv
DRIVE_MANIFEST_NAS = r"J:\_staging_drive3_MJ\drive3_MJesus_WX22D623YP29\manifest.csv"
DRIVE = r"J:\_staging_drive3_MJ\drive3_MJesus_WX22D623YP29\files"
NAS = r"J:\gjesus3-data"
K0118 = r"K:\gjesus\MRI\Proyecto 0118"
HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))            # the worktree root
CFG_DIR_REL = "tools/configs/drive3_mri"
CFG_DIR = os.path.join(WT, *CFG_DIR_REL.split("/"))
KSPACE = ("fid", "ser")                                                  # + rawdata.job<N>
CHUNK = 8 << 20


def w(*parts):
    """A path under BASE (parent created). Refuses anything outside it."""
    p = os.path.abspath(os.path.join(*parts))
    if not p.lower().startswith(BASE.lower() + os.sep):
        raise RuntimeError(f"refusing to write outside {BASE}: {p}")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def out(name):
    return w(OUT, name)


def lp(path):
    """Long-path form (951 staged paths are 260-277 characters)."""
    if os.name != "nt" or path.startswith("\\\\?\\"):
        return path
    ap = os.path.abspath(path)
    if ap.startswith("\\\\"):
        return "\\\\?\\UNC\\" + ap[2:]
    return "\\\\?\\" + ap


def sha256(path):
    h = hashlib.sha256()
    with open(lp(path), "rb") as f:
        for b in iter(lambda: f.read(CHUNK), b""):
            h.update(b)
    return h.hexdigest()


def is_kspace(name):
    n = name.lower()
    return n in KSPACE or n.startswith("rawdata.job")


def rows(path, encoding="utf-8-sig"):
    with io.open(lp(path), encoding=encoding, newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, recs, fields=None):
    fields = fields or (list(recs[0].keys()) if recs else [])
    with open(path, "w", encoding="utf-8", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        wr.writeheader()
        wr.writerows(recs)
    return path


def manifest_under(prefixes):
    """{relpath: (size, sha256)} for every drive-manifest row under any of the given relpath prefixes."""
    pre = tuple(p.rstrip("\\") + "\\" for p in prefixes)
    res = {}
    with open(MANIFEST, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["relpath"].startswith(pre):
                res[r["relpath"]] = (int(r["size"]), r["sha256"])
    return res


def live_registry(nas=NAS):
    return rows(os.path.join(nas, "registries", "registry_raw.csv"))


def live_projects(nas=NAS):
    return rows(os.path.join(nas, "registries", "registry_projects.csv"))
