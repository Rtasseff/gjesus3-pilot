"""Shared paths and parsing helpers for part A3 (drive 3 segmentations as a curated-dataset candidate).

READ-ONLY by construction: every function here reads the manifest, the production index, the live
registries or the staged files. Nothing writes outside OUT_DIR (D:\\projects\\gjesus3\\drive3_analysis\\a3).
Import with `sys.dont_write_bytecode = True` set first, so no __pycache__ lands anywhere.
"""
import csv
import os
import re
import sys

sys.dont_write_bytecode = True

ANALYSIS = r"D:\projects\gjesus3\drive3_analysis"
OUT_DIR = os.path.join(ANALYSIS, "a3")
MANIFEST = os.path.join(ANALYSIS, "drive3_manifest.csv")
PROD_SHA = os.path.join(ANALYSIS, "prod_raw_sha256.csv")
PROD_ACQS = os.path.join(ANALYSIS, "prod_raw_acqs.csv")
STAGED = r"J:\_staging_drive3_MJ\drive3_MJesus_WX22D623YP29\files"
GJ = r"J:\gjesus3-data"
REG = os.path.join(GJ, "registries")
CDS = os.path.join(GJ, "curated_datasets")

csv.field_size_limit(10 ** 9)

JUNK_NAMES = {"desktop.ini", "thumbs.db", ".ds_store", "icon", "icon\r"}


def ext_of(name):
    n = name.lower()
    for e in (".nii.gz", ".seg.nrrd", ".tar.gz"):
        if n.endswith(e):
            return e
    return os.path.splitext(n)[1] or ""


def is_junk(name):
    n = name.lower()
    return n.startswith("._") or n in JUNK_NAMES or n.startswith("icon")


def staged_path(relpath):
    return os.path.join(STAGED, relpath)


# --- file access that survives this drive's paths ---------------------------------------------------
# TRAP (measured 2026-10-06): 951 staged files sit at full paths of 260-277 characters. A plain Windows
# path then raises FileNotFoundError. SimpleITK accepts the \\?\ prefix but FAILS on any non-ASCII path
# ('Imágenes', 'Lucía'); nibabel rewrites \\?\ to //?/ and fails. Python's own open() handles both, so
# every read below goes through open(lp(path)) and parses the bytes in memory.
def lp(path):
    p = os.path.abspath(path)
    return p if p.startswith("\\\\?\\") else "\\\\?\\" + p


def read_bytes(path, n=None):
    with open(lp(path), "rb") as f:
        return f.read() if n is None else f.read(n)


def load_nifti(path):
    """nibabel image from bytes (works for long and non-ASCII paths). Raises on truncated gzip."""
    import gzip
    import nibabel as nib
    b = read_bytes(path)
    if path.lower().endswith(".gz"):
        b = gzip.decompress(b)
    return nib.Nifti1Image.from_bytes(b) if b[344:348] in (b"n+1\x00", b"ni1\x00") else nib.Nifti2Image.from_bytes(b)


MET_TYPES = {"MET_UCHAR": "u1", "MET_CHAR": "i1", "MET_USHORT": "u2", "MET_SHORT": "i2", "MET_UINT": "u4",
             "MET_INT": "i4", "MET_ULONG": "u8", "MET_LONG": "i8", "MET_FLOAT": "f4", "MET_DOUBLE": "f8"}


def read_metaimage(path, header_only=False):
    """Minimal MetaImage (.mhd + data file, or .mha with LOCAL data) reader. Returns (header dict, array or None).
    The array is in (x, y, z) order, like nibabel's, so dims compare directly with NIfTI labels."""
    import zlib
    import numpy as np
    raw = read_bytes(path)
    hdr, pos = {}, 0
    while True:
        nl = raw.find(b"\n", pos)
        if nl < 0:
            break
        line = raw[pos:nl].decode("latin-1").strip()
        pos = nl + 1
        if "=" in line:
            k, v = line.split("=", 1)
            hdr[k.strip()] = v.strip()
            if k.strip() == "ElementDataFile":
                break
    if header_only:
        return hdr, None
    dims = [int(x) for x in hdr["DimSize"].split()]
    dt = np.dtype(("<" if hdr.get("BinaryDataByteOrderMSB", hdr.get("ElementByteOrderMSB", "False")) == "False" else ">")
                  + MET_TYPES[hdr["ElementType"]])
    edf = hdr.get("ElementDataFile", "LOCAL")
    data = raw[pos:] if edf == "LOCAL" else read_bytes(os.path.join(os.path.dirname(path), edf))
    if hdr.get("CompressedData", "False") == "True":
        data = zlib.decompress(data)
    ncomp = int(hdr.get("ElementNumberOfChannels", "1"))
    n = int(np.prod(dims)) * ncomp
    arr = np.frombuffer(data[: n * dt.itemsize], dtype=dt)
    arr = arr.reshape(list(reversed(dims)) + ([ncomp] if ncomp > 1 else []))
    return hdr, arr.transpose(tuple(reversed(range(len(dims)))) + ((len(dims),) if ncomp > 1 else ()))


# --- ParaVision study / session tokens -------------------------------------------------------
# A ParaVision study folder: 20200428_114035_jrc200428_m41_1019_1_1 (sometimes _1_2, _2_1, _1_1_1,
# and copies with " (1)", " 2", "-copia" appended by the researcher).
STUDY_RE = re.compile(r"(?P<study>(?P<date>\d{8})_(?P<time>\d{6})_(?P<body>.+?)_(?P<n1>\d+)_(?P<n2>\d+)(?:_(?P<n3>\d+))?)"
                      r"(?=$|\s*\(\d+\)$|\s+\d+$|\s*-\s*copia$|\.mhd$|\.raw$|_Cardiac|_\d+_\d+)", re.I)
# A session token without the timestamp prefix (folder names such as Splits_jrc210728_m158_0619,
# NIFTI_jrc241001_m100_0522, jrc220207_m135_1019): pi initials + yymmdd + animal + suffix.
SESSION_RE = re.compile(r"(?P<sess>(?P<pi>jrc|irene|ire|mj)_?(?P<yymmdd>\d{6})_(?P<animal>[mr]?\d+[a-z]?)_(?P<rest>[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*))", re.I)
PROJECT_FOLDER_RE = re.compile(r"proyecto[\s_-]*(\d{4})", re.I)
CODE4_RE = re.compile(r"(?<![\d])(0\d{3}|1\d{3})(?![\d])")


def study_tokens(relpath):
    """Every ParaVision study-folder name found in the path components (dir names and Split file names)."""
    out = []
    for comp in relpath.split("\\"):
        c = comp.strip()
        # Split volumes: Time_10_rat_<study>.mhd ; predictions: Time_11_jrc201014_m9_1019_Cardiac_Segmentation.mha
        m = re.search(r"rat_(\d{8}_\d{6}_.+?_\d+_\d+(?:_\d+)?)\.(?:mhd|raw)$", c, re.I)
        if m:
            out.append(m.group(1))
            continue
        m = re.match(r"^(\d{8}_\d{6}_.+?_\d+_\d+(?:_\d+)?)(?:\s*\(\d+\)|\s+\d+|\s*-\s*copia)?$", c, re.I)
        if m:
            out.append(m.group(1))
    return out


def session_from_study(study):
    """Production-style session id from a study name: strip the leading timestamp and the trailing _n_n[_n]."""
    # the trailing ParaVision counters are 1-2 digits (_1_1, _1_2, _1_1_1); a 4-digit protocol code is
    # part of the body (a lazy \d+ here once swallowed '_1519' and returned 'jrc220221_m28').
    m = re.match(r"^\d{8}_\d{6}_(.+?)_\d{1,2}_\d{1,2}(?:_\d{1,2})?$", study)
    return m.group(1) if m else ""


COUNTERS = re.compile(r"_\d{1,2}_\d{1,2}(?:_\d{1,2})?$")


def norm_session(tok):
    """'jrc220216_m42_0320_1_1' -> 'jrc220216_m42_0320' (folder names keep ParaVision's counters)."""
    return COUNTERS.sub("", tok)


def split_study(token, by_session):
    """Split volumes are named Time_<t>_rat_<study>.mhd, or Time_<t>_rat_<session>.mhd (no timestamp).
    `by_session` maps production session_id -> rows carrying a 'study' key. Returns the production study for a
    session-named split when exactly one exists; otherwise the token unchanged (never a guess)."""
    if re.match(r"^\d{8}_\d{6}_", token):
        return token
    cands = {a["study"] for a in by_session.get(norm_session(token), []) if a.get("study")}
    return next(iter(cands)) if len(cands) == 1 else token


def session_tokens(relpath):
    """jrc-style session tokens anywhere in the path (no timestamp)."""
    toks = []
    for comp in relpath.split("\\"):
        for m in SESSION_RE.finditer(comp):
            toks.append(m.group("sess"))
    return toks


def project_codes_in_path(relpath):
    codes = []
    for comp in relpath.split("\\")[:-1]:
        for m in PROJECT_FOLDER_RE.finditer(comp):
            codes.append(m.group(1))
    return codes


def read_csv_dicts(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if fields is None:
        fields = []
        seen = set()
        for r in rows:
            for k in r:
                if k not in seen:
                    seen.add(k)
                    fields.append(k)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    os.replace(tmp, path)
    return path
