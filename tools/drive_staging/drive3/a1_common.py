"""Part A1 of the drive-3 (M. Jesus) assessment: shared paths, loaders and the file classifier.

READ-ONLY on J:\\ (production and the staged copy) and on K:\\. Every script of part A1 writes
only under D:\\projects\\gjesus3\\drive3_analysis\\a1\\ (out_path() refuses anything else).

Inputs (prepared by the coordinator, see the worktree HANDOFF.md section 3):
  drive3_manifest.csv   relpath,size,mtime,birthtime,atime,mtime_ns,sha256 (621,969 rows; relpath
                        relative to the staged files\\ folder, backslash-separated)
  prod_raw_sha256.csv   sha256,acq_id,instrument,project_id,relpath (every production checksums.json)
  prod_raw_acqs.csv     one row per production acquisition
and dated snapshots of the live registries that a1_00_snapshot.py copies into a1\\_inputs\\.

Sizes: "GB" in every A1 output is decimal (1e9 bytes). The CoS hub's brief printed GiB under the
label "GB"; where a number is compared with the hub's, both are given.
"""
import csv
import hashlib
import os
import pickle
import re
import sys

sys.dont_write_bytecode = True          # never leave __pycache__ beside these scripts or on J:
csv.field_size_limit(2 ** 31 - 1)

BASE = r"D:\projects\gjesus3\drive3_analysis"
OUT = os.path.join(BASE, "a1")
INPUTS = os.path.join(OUT, "_inputs")
CACHE = os.path.join(OUT, "_cache")
MANIFEST = os.path.join(BASE, "drive3_manifest.csv")
PROD_SHA = os.path.join(BASE, "prod_raw_sha256.csv")
PROD_ACQS = os.path.join(BASE, "prod_raw_acqs.csv")
STAGED = r"J:\_staging_drive3_MJ\drive3_MJesus_WX22D623YP29\files"
NAS = r"J:\gjesus3-data"
REGISTRIES = os.path.join(NAS, "registries")
HUB = (r"C:\Users\rtasseff\OneDrive - CIC biomaGUNE\projects\DataInfra\gjesus3-archive"
       r"\historical-mjesus-drive\records")
D12_RECORDS = os.path.join(NAS, "staging", "historical_drives_records")
D12_HOLDING_MANIFEST = os.path.join(NAS, "staging", "historical_drives_unassigned", "manifest.csv")
HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))          # <worktree>\tools

TOP_ORDER = ["MRI", "Otros", "Pili y Mili", "biomaGUNE MJ", "PET", "Microscopio", "(root files)"]


# ---------------------------------------------------------------------------------------------
# safety
# ---------------------------------------------------------------------------------------------
def out_path(*parts):
    """A path under a1\\ (created). Refuses to hand out anything that is not under OUT."""
    p = os.path.abspath(os.path.join(OUT, *parts))
    if not p.lower().startswith(os.path.abspath(OUT).lower() + os.sep) and p.lower() != OUT.lower():
        raise RuntimeError(f"refusing to write outside {OUT}: {p}")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def lp(path):
    """Long-path form for reading on Windows (some staged paths exceed 260 characters)."""
    if os.name != "nt" or path.startswith("\\\\?\\"):
        return path
    ap = os.path.abspath(path)
    if ap.startswith("\\\\"):
        return "\\\\?\\UNC\\" + ap[2:]
    return "\\\\?\\" + ap


def staged(relpath):
    return os.path.join(STAGED, relpath)


def read_bytes(path, n=None, offset=0):
    """Read-only open (mode 'rb'); never creates or modifies anything."""
    with open(lp(path), "rb") as f:
        if offset:
            f.seek(offset)
        return f.read() if n is None else f.read(n)


def sha256_file(path, chunk=8 * 1024 * 1024):
    h = hashlib.sha256()
    with open(lp(path), "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


# ---------------------------------------------------------------------------------------------
# cache
# ---------------------------------------------------------------------------------------------
def cache_load(name):
    p = os.path.join(CACHE, name + ".pkl")
    if os.path.exists(p):
        with open(p, "rb") as f:
            return pickle.load(f)
    return None


def cache_save(name, obj):
    with open(out_path("_cache", name + ".pkl"), "wb") as f:
        pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)


# ---------------------------------------------------------------------------------------------
# loaders
# ---------------------------------------------------------------------------------------------
def read_csv_dicts(path, encoding="utf-8-sig"):
    with open(lp(path), encoding=encoding, newline="") as f:
        return list(csv.DictReader(f))


def write_csv(name, rows, fields):
    p = out_path(name)
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return p


def snapshot(name):
    """Path of the dated registry snapshot a1_00_snapshot.py took (fails loudly if missing)."""
    p = os.path.join(INPUTS, name)
    if not os.path.exists(p):
        raise SystemExit(f"missing {p}: run a1_00_snapshot.py first")
    return p


def load_manifest():
    """The drive manifest as a pandas DataFrame with derived columns (cached)."""
    import pandas as pd
    df = cache_load("manifest")
    if df is not None:
        return df
    df = pd.read_csv(MANIFEST, dtype={"relpath": str, "sha256": str, "mtime": str, "birthtime": str},
                     keep_default_na=False, usecols=["relpath", "size", "mtime", "birthtime", "sha256"])
    rp = df["relpath"]
    df["top"] = [r.split("\\", 1)[0] if "\\" in r else "(root files)" for r in rp]
    df["name"] = [r.rsplit("\\", 1)[-1] for r in rp]
    df["dir"] = [r.rsplit("\\", 1)[0] if "\\" in r else "" for r in rp]
    df["ext"] = [file_ext(n) for n in df["name"]]
    cache_save("manifest", df)
    return df


def load_prod_index():
    """sha256 -> (acq_id, instrument, project_id, relpath) from every production checksums.json."""
    idx = cache_load("prod_index")
    if idx is not None:
        return idx
    idx = {}
    with open(PROD_SHA, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            idx[r["sha256"]] = (r["acq_id"], r["instrument"], r["project_id"], r["relpath"])
    cache_save("prod_index", idx)
    return idx


def load_prod_acqs():
    return {r["acq_id"]: r for r in read_csv_dicts(PROD_ACQS)}


def load_registry():
    return read_csv_dicts(snapshot("registry_raw.csv"))


# ---------------------------------------------------------------------------------------------
# file classification (A1's corrected version of the hub's content_classes.py)
# ---------------------------------------------------------------------------------------------
def file_ext(name):
    low = name.lower()
    for e in (".preview.czi", ".nii.gz", ".tar.gz"):
        if low.endswith(e):
            return e
    return os.path.splitext(low)[1]


JUNK_NAMES = {"desktop.ini", "thumbs.db", ".ds_store", "folders.cache", "thumbs.cache"}
SOFTWARE_EXT = {".exe", ".dmg", ".msi", ".dll", ".pyc", ".lnk"}
BRUKER_STUDY_NAMES = {"subject", "adjstateperstudy", "resultstate", "scanprogram.scanprogram",
                      "result.jcamp"}
KSPACE = re.compile(r"^(fid|ser|rawdata\.job\d+)$", re.I)
MRIM = re.compile(r"^MRIm(\d+)\.dcm$", re.I)
NIFTI = {".nii", ".nii.gz"}
VOLUME_OTHER = {".mha", ".nrrd", ".hdr", ".img", ".v", ".am", ".voi", ".labels", ".filtered", ".vtk",
                ".stl", ".seg"}
TIF = {".tif", ".tiff"}
FIGURE = {".png", ".jpg", ".jpeg", ".jfif", ".bmp", ".gif", ".svg", ".eps"}
DOCUMENT = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".pptm", ".xls", ".xlsx", ".txt", ".rtf", ".odt",
            ".ods", ".csv", ".tsv", ".html", ".css", ".md", ".ps", ".pages", ".eml", ".xml", ".json"}
ANALYSIS = {".mat", ".m", ".py", ".r", ".ipynb", ".pzfx", ".pzf", ".prism", ".adicht", ".adiset", ".sav",
            ".spv", ".edb", ".gmt", ".rnk", ".cls", ".rpt", ".gct", ".grp", ".gedata", ".gesup", ".ijm",
            ".ij", ".qpdata", ".qpproj", ".table", ".mvisl", ".voistat", ".h5", ".itksnap", ".mnova",
            ".g2i", ".ased", ".refscan", ".hx", ".backup"}
VIDEO = {".mp4", ".mov", ".avi", ".mpg"}
ARCHIVE = {".zip", ".rar", ".7z", ".tar", ".tar.gz", ".gz"}

# classes that are raw imaging (or part of a raw scan folder)
RAW_CLASSES = ["mri-dicom", "mri-2dseq", "mri-kspace", "mri-params", "mri-study-params",
               "dicom-standalone", "dicom-noext", "microscopy-czi", "microscopy-lif"]
CLASS_ORDER = RAW_CLASSES + [
    "mri-exam-foreign", "mri-study-foreign", "nmr-topspin", "microscopy-czi-preview",
    "microscopy-annotation", "volume-mhd", "volume-nifti", "volume-other", "image-tif", "figure",
    "document", "analysis", "video", "archive", "software", "junk", "other"]


def bruker_index(df):
    """Exam folders (a folder holding acqp or method), their study folders, TopSpin folders."""
    low = df["name"].str.lower()
    exam_dirs = set(df.loc[low.isin(["acqp", "method"]), "dir"])
    study_dirs = {d.rsplit("\\", 1)[0] for d in exam_dirs if "\\" in d}
    nmr_dirs = set(df.loc[low.isin(["acqus", "acqu"]), "dir"])
    return exam_dirs, study_dirs, nmr_dirs


def _ancestors(d):
    out = []
    while d:
        out.append(d)
        d = d.rsplit("\\", 1)[0] if "\\" in d else ""
    return out


def classify(df, dicm_noext=frozenset()):
    """Adds exam_dir, study_dir and a1class to the manifest frame (in place) and returns it.

    dicm_noext: relpaths of extension-less files outside Bruker folders whose bytes 128..131 are
    'DICM' (a1_05_probe_noext.py); they are DICOM written without an extension.
    """
    exam_dirs, study_dirs, nmr_dirs = bruker_index(df)
    mhd_stems = set(df.loc[df["ext"] == ".mhd", "relpath"].str[:-4].str.lower())
    exam_of, study_of, cls = [], [], []
    for rp, name, d, ext in zip(df["relpath"], df["name"], df["dir"], df["ext"]):
        low = name.lower()
        e = s = ""
        nmr = False
        for a in _ancestors(d):
            if not e and a in exam_dirs:
                e = a
            if a in study_dirs:
                s = a
                break
            if a in nmr_dirs:
                nmr = True
        exam_of.append(e)
        study_of.append(s)
        if low in JUNK_NAMES or low.startswith("._") or low.startswith("~$") or ext in (".tmp", ".temp"):
            c = "junk"
        elif ext in SOFTWARE_EXT:
            c = "software"
        elif e:
            inner = rp[len(e) + 1:].split("\\")
            if (len(inner) == 4 and inner[0].lower() == "pdata" and inner[2].lower() == "dicom"
                    and MRIM.match(inner[3])):
                c = "mri-dicom"
            elif low == "2dseq":
                c = "mri-2dseq"
            elif KSPACE.match(low):
                c = "mri-kspace"
            elif ext in ("", ".par", ".info", ".jcamp", ".dat", ".scanprogram", ".xml", ".txt") \
                    or low.startswith("spnam"):
                c = "mri-params"
            else:
                c = "mri-exam-foreign"
        elif s:
            if low in BRUKER_STUDY_NAMES or ext in ("", ".jcamp", ".scanprogram", ".dat", ".xml") :
                c = "mri-study-params"
            else:
                c = "mri-study-foreign"
        elif nmr or d in nmr_dirs:
            c = "nmr-topspin"
        elif ext == ".dcm":
            c = "dicom-standalone"
        elif ext == "" and rp in dicm_noext:
            c = "dicom-noext"
        elif ext == ".czi":
            c = "microscopy-czi"
        elif ext == ".preview.czi":
            c = "microscopy-czi-preview"
        elif ext in (".lif", ".lifext"):
            c = "microscopy-lif"
        elif ext == ".ndpa" or low.endswith(".czi.ndpa"):
            c = "microscopy-annotation"
        elif ext == ".mhd" or (ext == ".raw" and rp[:-4].lower() in mhd_stems):
            c = "volume-mhd"
        elif ext in NIFTI:
            c = "volume-nifti"
        elif ext in VOLUME_OTHER:
            c = "volume-other"
        elif ext in TIF:
            c = "image-tif"
        elif ext in FIGURE or ext.startswith(".jpg-"):
            c = "figure"
        elif ext in DOCUMENT or ext == ".pptx#":
            c = "document"
        elif ext in ANALYSIS:
            c = "analysis"
        elif ext in VIDEO:
            c = "video"
        elif ext in ARCHIVE:
            c = "archive"
        else:
            c = "other"
        cls.append(c)
    df["exam_dir"] = exam_of
    df["study_dir"] = study_of
    df["a1class"] = cls
    return df


# ---------------------------------------------------------------------------------------------
# MRI naming
# ---------------------------------------------------------------------------------------------
# the two production study-name regexes (tools/configs/mri_jrc_animalfirst.yaml, mri_jrc_projfirst.yaml),
# applied with re.search exactly as ingest.filename_parser.parse_regex does
RX_ANIMALFIRST = re.compile(r"(?P<jrc_id>(?P<pi_initials>[a-z]+)_?\d{6,8}_m(?P<animal_num>\d+)_(?P<project_code>\d{4}))")
RX_PROJFIRST = re.compile(r"(?P<jrc_id>(?P<pi_initials>[a-z]+)_?\d{6,8}_(?P<project_code>\d{4})_m(?P<animal_num>\d+))")
STUDY_RX = re.compile(r"^(?P<date>\d{8})_(?P<time>\d{6})_(?P<rest>.+)$")
INITIALS_RX = re.compile(r"^(?P<ini>[A-Za-z]+)_?(?P<d>\d{6,8})")


def parse_study(name):
    """What the study-folder name itself says: date, console initials, parse result under the two
    production regexes, and (only for a regex parse) the protocol code and animal number."""
    out = {"study_date": "", "study_time": "", "initials": "", "parse": "neither", "jrc_id": "",
           "code_by_regex": "", "animal_by_regex": ""}
    m = STUDY_RX.match(name)
    if m:
        out["study_date"], out["study_time"] = m.group("date"), m.group("time")
        mi = INITIALS_RX.match(m.group("rest"))
        if mi:
            out["initials"] = mi.group("ini")
    for label, rx in (("animal-first", RX_ANIMALFIRST), ("project-first", RX_PROJFIRST)):
        mm = rx.search(name)
        if mm:
            out["parse"] = label
            out["jrc_id"] = mm.group("jrc_id")
            out["code_by_regex"] = mm.group("project_code")
            out["animal_by_regex"] = mm.group("animal_num")
            break
    return out


def gb(n):
    return round(n / 1e9, 3)
