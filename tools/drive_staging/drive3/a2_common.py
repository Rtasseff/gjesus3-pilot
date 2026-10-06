#!/usr/bin/env python3
"""a2_common.py -- shared inputs and rules for part A2 of the drive-3 (M. Jesus) assessment.

Part A2 = projects, descriptions and the non-raw placement plan (HANDOFF.md §6 of the
review/drive3-mjesus-assessment worktree; report tasks/drive3_projects_and_placement.md).

READ-ONLY. Nothing here writes to J:\\ (production or the staged copy) or K:\\. Every output goes to
D:\\projects\\gjesus3\\drive3_analysis\\a2\\ (regenerable). Run the a2_*.py scripts with
PYTHONDONTWRITEBYTECODE=1 so no __pycache__ appears anywhere.

THE A1 / A2 BOUNDARY (per file, `classify`). A1 owns raw imaging: .czi/.lif/.lifext/.lsm/.nd2, every
DICOM (.dcm/.ima and the extension-less Philips-style IM_####/XX_####/PS_####/DICOMDIR exports, checked
by their DICM magic), and every ParaVision artifact (the scan directories' own files). A2 owns
everything else: Splits/MetaImage volumes, NIfTI, PMOD images, segmentations, VOIs, figures, exported
.tif, documents, analysis, physiology recordings, TopSpin HR-MAS NMR, video. Junk is excluded (Ryan's
ruled list plus the additions marked `addition`).
"""
import collections
import csv
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.dirname(HERE)            # tools/drive_staging
TOOLS = os.path.dirname(DS)           # tools
REPO = os.path.dirname(TOOLS)
for _p in (TOOLS, DS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import historical_paths as H  # noqa: E402  (THE destination rule, reused unchanged)
from catalog import BRUKER_NAMES, BRUKER_RE, file_ext, path_class, personal_hit  # noqa: E402

ANALYSIS = r"D:\projects\gjesus3\drive3_analysis"
OUT = os.path.join(ANALYSIS, "a2")
MANIFEST = os.path.join(ANALYSIS, "drive3_manifest.csv")
PROD_SHA = os.path.join(ANALYSIS, "prod_raw_sha256.csv")
PROD_ACQS = os.path.join(ANALYSIS, "prod_raw_acqs.csv")
NAS = r"J:\gjesus3-data"
STAGED_ROOT = r"J:\_staging_drive3_MJ\drive3_MJesus_WX22D623YP29"
STAGED = os.path.join(STAGED_ROOT, "files")
HOLDING_MANIFEST = os.path.join(NAS, "staging", "historical_drives_unassigned", "manifest.csv")
LONG = "\\\\?\\"
assert LONG == "\\" + "\\" + "?" + "\\", repr(LONG)   # heredocs have mangled this before

# The drive's code in the shared path rule. historical_paths knows D1/D2 only; registering D3 here
# (in memory, the module file is untouched) lets the unchanged Planner place drive-3 material.
DRIVE = "D3"
DRIVE_TAG = "MJesus-MFB"
DRIVE_LABEL = "drive3_MJesus-MFB"
H.TAGS.setdefault(DRIVE, DRIVE_TAG)
H.DRIVE_LABELS.setdefault(DRIVE, DRIVE_LABEL)

TOP_ORDER = ["Pili y Mili", "MRI", "PET", "Otros", "Microscopio", "biomaGUNE MJ"]  # canonical-copy priority


def say(*a):
    print(*a, flush=True)


def out_path(*parts):
    p = os.path.join(OUT, *parts)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def stdout_utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="backslashreplace")
        except AttributeError:
            pass


def rd(path):
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def it(path):
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def wcsv(path, fields, rows, bom=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8-sig" if bom else "utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def load_manifest():
    """[{relpath, size(int), mtime, sha256}] in manifest order."""
    out = []
    for r in it(MANIFEST):
        out.append({"relpath": r["relpath"], "size": int(r["size"] or 0), "mtime": r["mtime"],
                    "sha256": r["sha256"]})
    return out


def top_of(relpath):
    parts = relpath.split("\\")
    return parts[0] if len(parts) > 1 else "(drive root)"


def gb(n):
    return f"{n / 1e9:.2f}"


# ------------------------------------------------------------------------------------- classify

JUNK_RULED = {"desktop.ini": "desktop.ini", "thumbs.db": "Thumbs.db", ".ds_store": ".DS_Store"}
WD_INSTALLERS = {"otros\\install western digital software for windows.exe",
                 "otros\\install western digital software for mac.dmg"}
VIEWER_CACHE = {"folders.cache", "thumbs.cache"}
DICOM_NAME_RE = re.compile(r"^(?:IM|XX|PS)_\d+$|^DICOMDIR$")
PARAVISION_EXT = {".job0", ".job1", ".jcamp", ".scanprogram"}
PARAVISION_NAMES = {"uxnmr.par", "uxnmr.info", "adjrefgprofiles.dat", "assocs"}
PARAVISION_RE = re.compile(r"^(?:acqu\d+s?|proc\d+s?)$", re.I)
PARAVISION_DIRS = {"adjresult", "adjprotocols"}
STUDY_MARKERS = {"subject", "adjstateperstudy", "resultstate"}
EXAM_MARKERS = {"acqp", "method"}
RAW_MICROSCOPY = {".czi", ".lif", ".lifext", ".lsm", ".nd2", ".preview.czi"}
VOLUME_EXT = {".nii", ".nii.gz", ".mha", ".mhd", ".hdr", ".img", ".v", ".am", ".vtk", ".nrrd", ".filtered",
              ".opening", ".labels", ".hx", ".matchprot"}
SEG_RE = re.compile(r"(?i)segment|(?<![a-z])seg(?![a-z])|mask|label|(?<![a-z])voi")


class DirFacts:
    """Per-directory facts the per-file rules need, from the manifest alone."""

    def __init__(self, rows):
        names = collections.defaultdict(set)
        for r in rows:
            d, n = os.path.split(r["relpath"])
            names[d].add(n.lower())
        self.study_dirs = {d for d, s in names.items() if s & STUDY_MARKERS}
        self.exam_dirs = {d for d, s in names.items() if s & EXAM_MARKERS}
        # TopSpin (HR-MAS NMR) experiment: acqus without ParaVision's acqp/method
        self.topspin_dirs = {d for d, s in names.items() if "acqus" in s and not (s & EXAM_MARKERS)}
        self.mhd_stems = {os.path.splitext(r["relpath"])[0].lower() for r in rows
                          if r["relpath"].lower().endswith(".mhd")}

    @staticmethod
    def ancestors(relpath):
        parts = relpath.split("\\")[:-1]
        return ["\\".join(parts[:i]) for i in range(len(parts), 0, -1)]

    def in_paravision(self, relpath):
        return any(a in self.study_dirs or a in self.exam_dirs for a in self.ancestors(relpath))

    def in_topspin(self, relpath):
        return any(a in self.topspin_dirs for a in self.ancestors(relpath))

    def study_folder(self, relpath):
        """The nearest ParaVision study folder above the file, or ''."""
        for a in self.ancestors(relpath):
            if a in self.study_dirs:
                return a
        return ""


def classify(r, facts, dicom_magic=None):
    """-> (owner, cls, detail). owner: junk | A1 | A2.

    `dicom_magic`: {relpath: True/False} from a2_dicom_magic (the DICM preamble of extension-less
    candidates); None = trust the Philips-style name alone."""
    rel = r["relpath"]
    parts = rel.split("\\")
    name = parts[-1]
    low = name.lower()
    ext = file_ext(name)
    dirs_low = [p.lower() for p in parts[:-1]]
    # ---- junk (Ryan's ruled list first, then the additions, each marked) ------------------------
    if low in JUNK_RULED:
        return "junk", "junk", f"ruled: {JUNK_RULED[low]}"
    if name.startswith("._"):
        return "junk", "junk", "ruled: macOS AppleDouble ._ file"
    if rel.lower() in WD_INSTALLERS:
        return "junk", "junk", "ruled: WD installer"
    if low in ("icon\r", "icon\uf00d"):
        return "junk", "junk", "addition: macOS folder-icon file (Icon<CR>)"
    if low in VIEWER_CACHE:
        return "junk", "junk", "addition: image-viewer thumbnail cache (folders.cache / thumbs.cache)"
    if low.startswith("~$") or (low.startswith("~wrl") and low.endswith(".tmp")):
        return "junk", "junk", "addition: Office temporary / owner file (~$, ~WRL*.tmp)"
    # ---- A1: raw imaging ----------------------------------------------------------------------
    if ext in RAW_MICROSCOPY:
        return "A1", "raw-microscopy", ext
    if ext in (".dcm", ".ima"):
        return "A1", "dicom", ext
    if not ext and dicom_magic is not None and dicom_magic.get(rel) == "Y":
        why = ("extension-less DICOM export (IM_/XX_/PS_/DICOMDIR)" if DICOM_NAME_RE.match(name)
               else "extension-less file with a DICM preamble (DICOM without an extension)")
        return "A1", "dicom", why
    if not ext and dicom_magic is None and DICOM_NAME_RE.match(name):
        return "A1", "dicom", "extension-less DICOM export (name only; run a2_dicom_magic.py)"
    topspin = facts.in_topspin(rel)
    if topspin:
        return "A2", "nmr-topspin", "TopSpin (HR-MAS) experiment file"
    pv_name = (not ext and (low in BRUKER_NAMES or BRUKER_RE.match(low) or PARAVISION_RE.match(low))) \
        or ext in PARAVISION_EXT or low in PARAVISION_NAMES
    if pv_name:
        return "A1", "paravision", "ParaVision scan file"
    in_pv = facts.in_paravision(rel)
    if in_pv and any(d in PARAVISION_DIRS for d in dirs_low):
        return "A1", "paravision", "ParaVision AdjResult/AdjProtocols"
    # ---- A2: everything else ------------------------------------------------------------------
    base = path_class(rel, facts.mhd_stems)
    if ext == ".raw" and os.path.splitext(rel)[0].lower() in facts.mhd_stems:
        cls = "volume"
    elif ext in VOLUME_EXT:
        cls = "volume"
    elif ext in (".voi", ".voistat"):
        cls = "voi"
    elif ext == ".adicht":
        cls = "physiology"
    elif ext == ".g2i":
        cls = "gel-image"
    elif ext == ".ndpa":
        cls = "annotation"
    elif ext in (".h5",):
        cls = "analysis"
    elif ext in (".mpg", ".mov", ".mp4", ".avi"):
        cls = "video"
    elif ext in (".tsv", ".html", ".table", ".ps", ".edb", ".gct", ".gedata", ".xml", ".tiff_metadata.xml"):
        cls = "analysis"
    elif ext in (".csv", ".xlsx", ".xls"):
        cls = "document"
    elif base in ("tif", "figure", "document", "analysis", "video", "nmr", "em", "archive"):
        cls = base
    elif base == "volume":
        cls = "volume"
    elif not ext and r["size"] >= 1_000_000 and not in_pv:
        cls = "volume"   # extension-less PMOD/Analyze-style images (`m62_PETCTbrain`, `SUV 187`)
    else:
        cls = "other"
    detail = "inside a ParaVision study folder" if in_pv else ""
    return "A2", cls, detail


def is_segmentation(rel, cls):
    if cls not in ("volume", "voi", "other"):
        return False
    return bool(SEG_RE.search(rel.split("\\")[-1])) or bool(re.search(r"(?i)\\segmentaci", rel))


# ------------------------------------------------------------------------------------- registries

def load_dicom_magic():
    p = os.path.join(OUT, "dicom_magic.csv")
    if not os.path.exists(p):
        raise SystemExit("run a2_dicom_magic.py first (it measures which extension-less files are DICOM)")
    return {r["relpath"]: r["dicm"] for r in it(p)}


def load_projects():
    rows = rd(os.path.join(NAS, "registries", "registry_projects.csv"))
    return {r["name"]: r for r in rows}


def load_dedup_sources(say_=say):
    """SHA-256 sets for "already in production" (HANDOFF §1): /raw/, the drives-1+2 placements (every
    project tree's working\\historical_drives\\_INDEX.csv on the NAS), and the drives-1+2 holding folder.
    -> (raw {sha: [acq_id]}, placed {sha: {project folder: [new_path]}}, holding {sha: [new_path]})"""
    raw = collections.defaultdict(list)
    for r in it(PROD_SHA):
        raw[r["sha256"]].append(r["acq_id"])
    placed = collections.defaultdict(lambda: collections.defaultdict(list))
    n_idx = n_rows = 0
    proj_dir = os.path.join(NAS, "projects")
    for folder in sorted(os.listdir(proj_dir)):
        idx = os.path.join(proj_dir, folder, "working", "historical_drives", H.INDEX_NAME)
        if not os.path.isfile(idx):
            continue
        n_idx += 1
        for r in it(idx):
            if r.get("sha256"):
                placed[r["sha256"]][folder].append(r["new_path"])
                n_rows += 1
    holding = collections.defaultdict(list)
    for r in it(HOLDING_MANIFEST):
        if r.get("sha256"):
            holding[r["sha256"]].append(r.get("new_path") or r.get("relpath") or "")
    say_(f"dedup sources: /raw/ {len(raw):,} distinct sha256; drives-1+2 placements {n_rows:,} rows in "
         f"{n_idx} project indexes ({len(placed):,} distinct); holding {sum(len(v) for v in holding.values()):,} "
         f"rows ({len(holding):,} distinct)")
    return raw, placed, holding


def project_folder_name(row):
    return (row.get("folder_location") or "").strip("/").split("/")[-1]
