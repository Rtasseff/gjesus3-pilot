"""Per-file catalog of the staged historical-microscopy drives: what each file IS, from its own bytes.

Reads the manifests written by stage_copy.py (never the source drives, never anything under a
staged `files\\` tree except to read), and writes one row per file plus one row per archive
member to <out>\\ -- default D:\\projects\\gjesus3\\staging\\_analysis\\catalog\\. Facts about
CONTENT only: class, instrument (by device serial -- see tools/reference/microscopy_instruments.yaml),
true acquisition date, duplicate copies, and whether production gjesus3 already holds the bytes.
Which project / animal / researcher a *path* claims is somebody else's table; join on (drive, relpath).

    python catalog.py production   # J:\\ registry + every checksums.json -> production_hashes.csv, audit
    python catalog.py probe        # .czi / .tif / .lsm / .dcm headers  -> probe.jsonl        (resumable)
    python catalog.py archives     # list + stream-hash every archive member -> archive_*.jsonl (resumable)
    python catalog.py assemble     # -> files.csv archives.csv archive_members.csv dup_groups.csv summary.md
    python catalog.py all          # the four above, in order

Everything except `production` is read-only against the staged data. `production` reads small files
(registry, checksums.json, metadata.json) from the NAS and never an image. Nothing is extracted to disk
except one .7z/.rar at a time into <out>\\_tmp\\ (deleted after hashing); `LEONE.zip` (human clinical MRI)
is stream-hashed only.

Every pass prints an error tally at the end and records it in <out>\\stats.json.
"""
import argparse
import concurrent.futures as cf
import csv
import datetime as dt
import glob
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stage_copy import CHUNK, Log, gb, keep_awake, load_manifest, longpath  # noqa: E402

VERSION = "1.0 (2026-09-29)"
STAGING = r"D:\projects\gjesus3\staging"
NAS_ROOT = r"J:\gjesus3-data"
SEVENZIP = r"C:\Program Files\7-Zip\7z.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
INSTRUMENTS_YAML = os.path.join(HERE, "..", "reference", "microscopy_instruments.yaml")

CZI_XML_CAP = 200_000_000
CZI_HEAD = 32 + 4 + 4 + 248          # segment header + XmlSize + AttachmentSize + spare

# ---------------------------------------------------------------------------------------------
# classification (rules from the handoff, first match wins; deviations documented in the findings)
# ---------------------------------------------------------------------------------------------
SYSTEM_DIRS = {"$recycle.bin", ".spotlight-v100", ".fseventsd", "system volume information"}
SYSTEM_NAMES = {".ds_store", "thumbs.db", "desktop.ini"}
SOFTWARE_EXT = {".exe", ".dll", ".msi", ".cab", ".jar", ".sys", ".ocx", ".pyd", ".so", ".dylib",
                ".bat", ".cmd", ".ps1", ".vbs", ".dmg"}
ARCHIVE_EXT = {".zip", ".7z", ".rar", ".tar", ".tgz", ".tar.gz"}
VOLUME_EXT = {".dcm", ".nii", ".nii.gz", ".mhd", ".jcamp"}
EM_EXT = {".dm3", ".dm4"}
NMR_EXT = {".mnova"}
ANALYSIS_EXT = {".zmes", ".scanprogram", ".job0", ".edb", ".csv", ".xlsx", ".xls", ".opju", ".opj",
                ".ijm", ".py", ".m", ".r", ".stl", ".vtk", ".qpdata",
                # added 2026-09-29 (seen in the scan): analysis/project files of the same kind
                ".mat", ".pzfx", ".fcs", ".sciprj", ".qpproj", ".itksnap", ".voistat", ".ipynb",
                ".job1", ".refscan", ".rpt", ".rnk", ".gmt", ".cls", ".dts", ".jws"}
FIGURE_EXT = {".png", ".jpg", ".jpeg", ".jfif", ".bmp", ".gif", ".svg"}
DOCUMENT_EXT = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".pptm", ".txt", ".md", ".rtf", ".odt",
                ".ods"}
VIDEO_EXT = {".avi", ".mp4", ".mov"}
# ParaVision / TopSpin extension-less files (added: 15,831 + 9,904 files would otherwise be `other`)
BRUKER_NAMES = {"fid", "ser", "2dseq", "acqp", "acqus", "acqu", "method", "visu_pars", "reco", "d3proc",
                "procs", "proc", "proc2s", "subject", "id", "1r", "1i", "title", "pulseprogram", "specpar",
                "configscan", "adjstateperscan", "adjstateperstudy", "methreco", "outd", "scon2",
                "prosol_history", "shimvalues", "fq1list", "intrng", "peaks", "peakrng", "roi", "clevels",
                "cpdprg2", "used_from", "results", "resultstate", "b0", "traj", "isa", "profiles", "1roi"}
BRUKER_RE = re.compile(r"^(spnam\d+|stanprogram\d+|preemp_default_.*)$")
PERSONAL_EXACT = {"cv", "dni", "personal"}
PERSONAL_PREFIX = ("admin", "nomina", "nómina", "contrato", "factura", "pasaporte", "certificado", "beca")

CLASSES = ["czi-raw", "czi-processed", "czi-preview", "czi-unreadable", "lsm", "tif", "volume", "bruker",
           "em", "nmr", "analysis", "figure", "document", "video", "software", "archive", "system", "other"]


def file_ext(name):
    low = name.lower()
    for e in (".preview.czi", ".nii.gz", ".tar.gz"):
        if low.endswith(e):
            return e
    return os.path.splitext(low)[1]


def split_parts(rel):
    return rel.replace("/", "\\").split("\\")


def is_bruker_name(low):
    return low in BRUKER_NAMES or bool(BRUKER_RE.match(low))


def path_class(rel, mhd_stems=frozenset()):
    """Class from the path alone. Returns 'czi' for a non-preview .czi (refined from its metadata)."""
    parts = split_parts(rel)
    name = parts[-1]
    low = name.lower()
    dirs = [p.lower() for p in parts[:-1]]
    ext = file_ext(name)
    if (any(d in SYSTEM_DIRS for d in dirs) or low in SYSTEM_NAMES or low.startswith("~$")
            or low.endswith(".tmp")):
        return "system"
    if ext in SOFTWARE_EXT or any(d == "fiji.app" or "crack" in d for d in dirs):
        return "software"
    if ext in ARCHIVE_EXT:
        return "archive"
    if ext == ".preview.czi":
        return "czi-preview"
    if ext == ".czi":
        return "czi"
    if ext == ".lsm":
        return "lsm"
    if ext in (".tif", ".tiff"):
        return "tif"
    if ext in VOLUME_EXT or low == "2dseq":
        return "volume"
    if ext == ".raw" and "\\".join(parts[:-1] + [os.path.splitext(name)[0].lower()]) in mhd_stems:
        return "volume"
    if ext in EM_EXT:
        return "em"
    if ext in NMR_EXT:
        return "nmr"
    if not ext and is_bruker_name(low):
        return "bruker"
    if ext in ANALYSIS_EXT:
        return "analysis"
    if ext in FIGURE_EXT:
        return "figure"
    if ext in DOCUMENT_EXT:
        return "document"
    if ext in VIDEO_EXT:
        return "video"
    return "other"


def personal_hit(rel):
    """Report-only heuristic: a folder/file name token that looks personal or administrative."""
    hits = []
    for part in split_parts(rel):
        for tok in re.split(r"[\W_]+", part.lower()):
            if tok in PERSONAL_EXACT or (tok and tok.startswith(PERSONAL_PREFIX)):
                hits.append(tok)
    return sorted(set(hits))


# ---------------------------------------------------------------------------------------------
# instrument fingerprint
# ---------------------------------------------------------------------------------------------
def load_instruments(path=INSTRUMENTS_YAML):
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)["instruments"]


def fingerprint(ref, serials, keys, stand):
    """(instrument, rule, all_fired). First entry in `ref` that fires wins; 'unknown' when none."""
    serials, keys = set(serials), set(keys)
    fired = []
    for ent in ref:
        rule = None
        ser = [s for s in ent.get("serials", []) if s in serials]
        if ser:
            rule = f"serial:{ser[0]}"
        elif ent.get("stand_keys_any") and keys & set(ent["stand_keys_any"]):
            rule = "stand-key:" + "+".join(sorted(keys & set(ent["stand_keys_any"])))
        elif (ent.get("no_serials") and not serials and ent.get("stand_keys_exact")
              and keys == set(ent["stand_keys_exact"])
              and (not ent.get("stand_name") or stand == ent["stand_name"])):
            rule = "no-serial+keys=" + "+".join(sorted(keys)) + "+stand"
        if rule:
            fired.append((ent["code"], rule))
    if not fired:
        return "unknown", "none", fired
    return fired[0][0], fired[0][1], fired


def fp_inputs_from_dict(raw, fallback_stand=""):
    """The same rule inputs from a production sidecar's microscopy._raw_metadata (xmltodict-like)."""
    serials, keys = set(), set()

    def val(v):
        if isinstance(v, dict):
            v = v.get("#text", "")
        return v.strip() if isinstance(v, str) else ""

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "SerialNumber":
                    s = val(v)
                    if s:
                        serials.add(s)
                elif k == "StandCharacteristic":
                    for it in (v if isinstance(v, list) else [v]):
                        if isinstance(it, dict):
                            key = it.get("Key") or (it.get("@attrs") or {}).get("Key")
                            if key:
                                keys.add(key)
                else:
                    walk(v)
        elif isinstance(o, list):
            for i in o:
                walk(i)

    hw = raw.get("HardwareSetting") if isinstance(raw, dict) else None
    walk(hw)
    stand = fallback_stand
    try:
        m = raw["Information"]["Instrument"]["Microscopes"]["Microscope"]
        m = m[0] if isinstance(m, list) else m
        stand = (m.get("@attrs") or {}).get("Name") or m.get("Name") or stand
    except (KeyError, TypeError, IndexError):
        pass
    return serials, keys, stand, hw is not None


# ---------------------------------------------------------------------------------------------
# CZI metadata (metadata segment only, never the image data)
# ---------------------------------------------------------------------------------------------
def czi_read_xml(path, cap=CZI_XML_CAP):
    """(xml_bytes, None) or (None, reason). Seeks straight to the metadata segment."""
    with open(longpath(path), "rb") as f:
        head = f.read(160)
        if not head.startswith(b"ZISRAWFILE") or len(head) < 100:
            return None, "no-ZISRAWFILE-header"
        pos = struct.unpack_from("<q", head, 92)[0]
        size = os.fstat(f.fileno()).st_size
        if not 0 < pos < size - 32:
            return None, "bad-metadata-position"
        f.seek(pos)
        if not f.read(32).startswith(b"ZISRAWMETADATA"):
            return None, "no-metadata-segment"
        xml_size = struct.unpack("<i", f.read(4))[0]
        f.read(4 + 248)
        if not 0 < xml_size <= cap:
            return None, f"bad-xml-size:{xml_size}"
        data = f.read(xml_size)
        if len(data) < xml_size:
            return None, "truncated-xml"
        return data, None


class CziCapture:
    """Pulls the metadata XML out of a stream that is being read sequentially anyway (archive members)."""

    def __init__(self, cap=CZI_XML_CAP):
        self.cap, self.pos, self.end, self.err = cap, None, None, None
        self.buf, self.sized = bytearray(), False

    def feed(self, off, b):
        if off == 0:
            if not b.startswith(b"ZISRAWFILE") or len(b) < 100:
                self.err = "no-ZISRAWFILE-header"
                return
            self.pos = struct.unpack_from("<q", b, 92)[0]
            if self.pos <= 0:
                self.err = "bad-metadata-position"
                return
            self.end = self.pos + CZI_HEAD
        if self.err or self.end is None:
            return
        self._take(off, b)
        if not self.sized and len(self.buf) >= CZI_HEAD:
            if not self.buf.startswith(b"ZISRAWMETADATA"):
                self.err = "no-metadata-segment"
                return
            xs = struct.unpack_from("<i", self.buf, 32)[0]
            if not 0 < xs <= self.cap:
                self.err = f"bad-xml-size:{xs}"
                return
            self.sized, self.end = True, self.pos + CZI_HEAD + xs
            self._take(off, b)

    def _take(self, off, b):
        lo, hi = max(off, self.pos + len(self.buf)), min(off + len(b), self.end)
        if hi > lo:
            self.buf += b[lo - off:hi - off]

    def result(self):
        if self.err:
            return None, self.err
        if not self.sized or len(self.buf) < self.end - self.pos:
            return None, "metadata-not-reached"
        return bytes(self.buf[CZI_HEAD:]), None


def _text(e, path):
    x = e.find(path)
    return " ".join((x.text or "").split()) if x is not None and x.text else ""


def parse_czi_xml(xml_bytes):
    """Fields the catalog records (handoff §4). Raises ET.ParseError on unparseable XML."""
    root = ET.fromstring(xml_bytes)
    # NB: there are several <HardwareSetting> elements (the top-level one that carries the device list,
    # and presets inside <HardwareSettingsPool>); a first-match find() lands on a preset and misses
    # every serial. Union over all of them.
    hws = list(root.iter("HardwareSetting"))
    hw = hws[0] if hws else None
    serials = set()
    keys = set()
    for h in hws:
        for d in h.iter("Device"):
            s = (d.get("SerialNumber") or "").strip()
            if s:
                serials.add(s)
    for k in root.iter("StandCharacteristic"):          # stand keys can also sit outside HardwareSetting
        if k.get("Key"):
            keys.add(k.get("Key"))
    m = root.find(".//Information/Instrument/Microscopes/Microscope")
    stand = (m.get("Name") or "") if m is not None else ""
    modes, seen = [], set()
    for a in root.iter("AcquisitionMode"):
        t = (a.text or "").strip()
        if t and t not in seen:
            seen.add(t)
            modes.append(t)
    cams = sorted({(c.get("Id") or "").rsplit(".", 1)[-1] for c in root.iter("Camera") if c.get("Id")})
    objs = []
    for o in root.findall(".//Information/Instrument/Objectives/Objective"):
        mag = _text(o, "NominalMagnification")
        objs.append(((o.get("Name") or "").strip() + (f" {mag}x" if mag else "")).strip())
    app = " ".join(x for x in (_text(root, ".//Information/Application/Name"),
                               _text(root, ".//Information/Application/Version")) if x)
    return {
        "stand": stand,
        "system": _text(m, "System") if m is not None else "",
        "type": _text(m, "Type") if m is not None else "",
        "serials": sorted(serials),
        "keys": sorted(keys),
        "modes": modes,
        "cameras": cams,
        "acq_dt": _text(root, ".//Information/Image/AcquisitionDateAndTime"),
        "objective": ";".join(dict.fromkeys(objs)),
        "zen": app,
        "user": _text(root, ".//Information/User/DisplayName") or _text(root, ".//Information/Document/UserName"),
        "has_hw": hw is not None,
        "has_exp": root.find(".//Experiment") is not None,
    }


def czi_from_bytes(xml_bytes, err):
    """probe dict for a czi given (bytes, err) from either reader."""
    if xml_bytes is None:
        return {"ok": False, "err": err}
    try:
        return {"ok": True, **parse_czi_xml(xml_bytes)}
    except ET.ParseError as e:
        return {"ok": False, "err": f"xml-parse-error:{e}"}


def czi_class(p):
    if not p["ok"]:
        return "czi-unreadable"
    if p["has_hw"] or p["serials"] or p["keys"]:
        return "czi-raw"
    if not p["has_exp"]:
        return "czi-processed"
    return "czi-raw"


# ---------------------------------------------------------------------------------------------
# TIFF / DICOM header probes
# ---------------------------------------------------------------------------------------------
def tiff_probe(path):
    import tifffile
    with open(longpath(path), "rb") as fh, tifffile.TiffFile(fh) as tf:
        page = tf.pages[0]
        tags = page.tags

        def tv(name):
            t = tags.get(name)
            return "" if t is None else " ".join(str(t.value).split())
        desc = tv("ImageDescription")
        return {"ok": True, "software": tv("Software"), "make": tv("Make"), "model": tv("Model"),
                "desc_head": desc[:60], "is_ome": "Y" if tf.is_ome else "N",
                "lsminfo": "Y" if tags.get(34412) is not None else "N", "pages": len(tf.pages)}


def dicom_magic(path):
    try:
        with open(longpath(path), "rb") as f:
            return f.read(132)[128:132] == b"DICM"
    except OSError:
        return False


def dicom_probe(path):
    """Header fields only. The patient name / birth date are reduced to presence flags."""
    import pydicom
    with open(longpath(path), "rb") as fh:
        ds = pydicom.dcmread(fh, stop_before_pixels=True, force=True, specific_tags=[
            "Modality", "Manufacturer", "ManufacturerModelName", "StudyDate",
            "PatientSpeciesDescription", "PatientName", "PatientBirthDate"])
    if "Modality" not in ds and "Manufacturer" not in ds and "StudyDate" not in ds:
        return {"ok": False, "err": "not-dicom"}

    def g(k):
        return " ".join(str(ds.get(k, "") or "").split())
    return {"ok": True, "modality": g("Modality"), "manufacturer": g("Manufacturer"),
            "model": g("ManufacturerModelName"), "study_date": g("StudyDate"),
            "species": g("PatientSpeciesDescription"),
            "has_name": "Y" if g("PatientName") else "N", "has_birth": "Y" if g("PatientBirthDate") else "N"}


# ---------------------------------------------------------------------------------------------
# shared helpers
# ---------------------------------------------------------------------------------------------
class Ctx:
    def __init__(self, staging, out, nas):
        self.staging, self.out, self.nas = staging, out, nas
        self.drives = {}
        for tag, pat in (("D1", "drive1_*"), ("D2", "drive2_*")):
            hits = glob.glob(os.path.join(staging, pat))
            if hits:
                self.drives[tag] = hits[0]
        os.makedirs(out, exist_ok=True)
        self.log = Log(os.path.join(out, "catalog.log"))

    def p(self, name):
        return os.path.join(self.out, name)

    def manifest(self):
        """{(drive, relpath): row} -- the LAST manifest row per path, as stage_copy.load_manifest does."""
        rows = {}
        for tag, root in self.drives.items():
            for rel, r in load_manifest(os.path.join(root, "manifest.csv")).items():
                rows[(tag, rel)] = r
        return rows

    def file_path(self, drive, rel):
        return os.path.join(self.drives[drive], "files", rel)

    def stats_update(self, name, d):
        p = self.p("stats.json")
        cur = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
        cur[name] = d
        with open(p, "w", encoding="utf-8") as f:
            json.dump(cur, f, indent=1, ensure_ascii=False)

    def stats(self):
        p = self.p("stats.json")
        return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def read_jsonl(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue      # a torn last line from an interrupted run; the item is redone


def stream_hash(fobj, want_czi=False):
    """(sha256 hex, bytes read, dicom_magic, czi (bytes|None, err|None) | None) reading fobj once."""
    h = hashlib.sha256()
    off, dm = 0, False
    cap = CziCapture() if want_czi else None
    while True:
        b = fobj.read(CHUNK)
        while b and len(b) < CHUNK:                 # a short read is not EOF for some stream objects
            more = fobj.read(CHUNK - len(b))
            if not more:
                break
            b += more
        if not b:
            break
        if off == 0:
            dm = len(b) >= 132 and b[128:132] == b"DICM"
        h.update(b)
        if cap:
            cap.feed(off, b)
        off += len(b)
    return h.hexdigest(), off, dm, (cap.result() if cap else None)


def czi_summary(p, ref):
    """Flatten a czi probe dict + fingerprint for the row writers."""
    if not p or not p.get("ok"):
        return {}
    inst, rule, fired = fingerprint(ref, p["serials"], p["keys"], p["stand"])
    p = dict(p)
    p["instrument"], p["rule"] = inst, rule
    p["conflict"] = len({c for c, _ in fired}) > 1
    return p


# ---------------------------------------------------------------------------------------------
# stage 1: production hashes + instrument audit
# ---------------------------------------------------------------------------------------------
def production(ctx, args):
    ref = load_instruments()
    reg_path = os.path.join(ctx.nas, "registries", "registry_raw.csv")
    with open(reg_path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    ctx.log(f"production: registry {len(rows):,} rows ({dt.datetime.fromtimestamp(os.path.getmtime(reg_path)):%Y-%m-%d %H:%M})")
    tally = Counter()

    def read_checksums(r):
        p = os.path.join(ctx.nas, r["canonical_path"].strip("/\\").replace("/", os.sep), "checksums.json")
        try:
            with open(p, encoding="utf-8") as f:
                return r, json.load(f).get("files", {}), None
        except (OSError, ValueError) as e:
            return r, {}, f"{type(e).__name__}"
    out_tmp = ctx.p("production_hashes.csv.part")
    n = 0
    with cf.ThreadPoolExecutor(16) as ex, open(out_tmp, "w", newline="", encoding="utf-8") as fo:
        w = csv.writer(fo)
        w.writerow(["sha256", "acq_id", "instrument", "file"])
        t0 = time.time()
        for i, (r, files, err) in enumerate(ex.map(read_checksums, rows), 1):
            if err:
                tally["checksums.json " + err] += 1
            for name, sha in files.items():
                w.writerow([sha, r["acq_id"], r["instrument"], name])
                n += 1
            if i % 2000 == 0:
                ctx.log(f"  {i:,}/{len(rows):,} acquisitions, {n:,} hashes, {time.time() - t0:.0f}s")
    os.replace(out_tmp, ctx.p("production_hashes.csv"))
    ctx.log(f"production_hashes.csv: {n:,} rows from {len(rows):,} acquisitions")

    # instrument audit: registry instrument vs fingerprint rule, for every production microscopy acquisition
    micro = [r for r in rows if r["data_ecosystem"] == "MICROSCOPY"]

    def audit_one(r):
        p = os.path.join(ctx.nas, r["canonical_path"].strip("/\\").replace("/", os.sep), "metadata.json")
        try:
            with open(p, encoding="utf-8") as f:
                s = json.load(f)
        except (OSError, ValueError) as e:
            return r, None, f"metadata.json {type(e).__name__}"
        m = s.get("microscopy") or {}
        raw = m.get("_raw_metadata")
        if not isinstance(raw, dict):
            return r, None, "no-_raw_metadata"
        serials, keys, stand, has_hw = fp_inputs_from_dict(raw, (m.get("instrument") or {}).get("microscope_name", ""))
        return r, (serials, keys, stand, has_hw), None
    audit_rows, mism = [], 0
    with cf.ThreadPoolExecutor(8) as ex:
        for r, fp, err in ex.map(audit_one, micro):
            if err:
                tally["audit " + err] += 1
                audit_rows.append([r["acq_id"], r["instrument"], "", "", "", "", "", "", err])
                continue
            serials, keys, stand, has_hw = fp
            inst, rule, fired = fingerprint(ref, serials, keys, stand)
            agree = "Y" if inst == r["instrument"] else "N"
            mism += agree == "N"
            audit_rows.append([r["acq_id"], r["instrument"], inst, rule, agree, ";".join(sorted(serials)),
                               ";".join(sorted(keys)), stand, "" if has_hw else "no-HardwareSetting"])
    with open(ctx.p("production_instrument_audit.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["acq_id", "registry_instrument", "fingerprint_instrument", "rule", "agree",
                    "serials", "stand_keys", "stand", "flag"])
        w.writerows(audit_rows)
    conf = Counter((a[1], a[2]) for a in audit_rows if a[4] == "N")
    ctx.log(f"production audit: {len(audit_rows):,} microscopy acquisitions, {mism} disagree: {dict(conf)}")
    ctx.log(f"production error tally: {dict(tally) or 'none'}")
    ctx.stats_update("production", {"registry_rows": len(rows), "hash_rows": n, "audit_rows": len(audit_rows),
                                    "audit_disagree": mism, "errors": dict(tally),
                                    "registry_mtime": f"{dt.datetime.fromtimestamp(os.path.getmtime(reg_path)):%Y-%m-%d %H:%M}"})


# ---------------------------------------------------------------------------------------------
# stage 2: header probes of loose files
# ---------------------------------------------------------------------------------------------
def probe_kind(rel):
    ext = file_ext(split_parts(rel)[-1])
    low = split_parts(rel)[-1].lower()
    if ext == ".czi":
        return "czi"
    if ext in (".tif", ".tiff", ".lsm"):
        return "tif"
    if ext == ".dcm":
        return "dcm"
    if not ext and not is_bruker_name(low) and low not in SYSTEM_NAMES:
        return "sniff"          # extension-less: DICOM if it carries the DICM magic
    return None


def probe(ctx, args):
    man = ctx.manifest()
    ppath = ctx.p("probe.jsonl")
    done = {}
    for r in read_jsonl(ppath):
        done[(r["d"], r["r"])] = r
    if args.retry_errors:
        done = {k: v for k, v in done.items() if not (v.get("ok") is False and v.get("io"))}
    todo = []
    for (d, rel), r in sorted(man.items()):
        if any(x in SYSTEM_DIRS for x in (p.lower() for p in split_parts(rel)[:-1])):
            continue
        k = probe_kind(rel)
        if k and (d, rel) not in done and (not args.only or args.only in rel):
            todo.append((d, rel, k, int(r["size"])))
    if args.limit:
        todo = todo[:args.limit]
    ctx.log(f"probe: {len(todo):,} to do, {len(done):,} already done")
    tally = Counter()
    t0 = last = time.time()
    n = 0
    with open(ppath, "a", encoding="utf-8") as fo:
        for d, rel, kind, size in todo:
            path = ctx.file_path(d, rel)
            row = {"d": d, "r": rel, "size": size, "kind": kind}
            try:
                if kind == "sniff":
                    if size < 132 or not dicom_magic(path):
                        continue                       # not DICOM: nothing recorded, nothing to redo
                    kind = row["kind"] = "dcm"
                if kind == "czi":
                    row.update(czi_from_bytes(*czi_read_xml(path)))
                elif kind == "tif":
                    row.update(tiff_probe(path))
                else:
                    row.update(dicom_probe(path))
            except OSError as e:
                row.update(ok=False, io=True, err=f"{type(e).__name__}:{e}")
            except Exception as e:                      # a parser failing on one file must not stop the pass
                row.update(ok=False, err=f"{type(e).__name__}:{e}"[:200])
            if not row.get("ok"):
                tally[f"{kind}: {row.get('err', '?').split(':')[0]}"] += 1
            tally[f"probed {kind}"] += 1
            fo.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
            if n % 200 == 0:
                fo.flush()
            if time.time() - last >= 60:
                last = time.time()
                ctx.log(f"  probe {n:,}/{len(todo):,}  {n / (last - t0):.0f} files/s  errors {sum(v for k, v in tally.items() if not k.startswith('probed'))}")
    ctx.log(f"probe DONE: {n:,} files in {(time.time() - t0) / 60:.1f} min. tally: {dict(tally)}")
    ctx.stats_update("probe", {"this_run": dict(tally)})


# ---------------------------------------------------------------------------------------------
# stage 3: archives
# ---------------------------------------------------------------------------------------------
def list_7z(path):
    """(members [(name,size,is_dir,encrypted)], error|None) via `7z l -slt`."""
    r = subprocess.run([SEVENZIP, "l", "-slt", "-sccUTF-8", "-scsUTF-8", path], capture_output=True)
    text = r.stdout.decode("utf-8", "replace").replace("\r\n", "\n")
    err = None
    low = (text + r.stderr.decode("utf-8", "replace")).lower()
    if "unexpected end of archive" in low or "unexpected end of data" in low:
        err = "truncated"
    elif "wrong password" in low or "cannot open encrypted" in low:
        err = "encrypted"
    elif r.returncode >= 2 and "----------" not in text:
        err = "unreadable"
    members = []
    if "----------" in text:
        for blk in text.split("----------", 1)[1].split("\n\n"):
            kv = dict(l.split(" = ", 1) for l in blk.strip().splitlines() if " = " in l)
            if "Path" in kv:
                members.append((kv["Path"], int(kv.get("Size") or 0) if (kv.get("Size") or "0").isdigit() else 0,
                                kv.get("Folder") == "+", kv.get("Encrypted") == "+"))
    return members, err, r.returncode


def archives(ctx, args):
    ref = load_instruments()
    man = ctx.manifest()
    arcs = sorted(((d, rel, int(r["size"])) for (d, rel), r in man.items()
                   if file_ext(split_parts(rel)[-1]) in ARCHIVE_EXT), key=lambda x: x[2])
    mpath, apath = ctx.p("archive_members.jsonl"), ctx.p("archives_done.jsonl")
    done = {(r["d"], r["a"]) for r in read_jsonl(apath)}
    partial = defaultdict(set)
    for r in read_jsonl(mpath):
        partial[(r["d"], r["a"])].add(r["m"])
    tmp_root = ctx.p("_tmp")
    if os.path.isdir(tmp_root):
        shutil.rmtree(longpath(tmp_root), ignore_errors=True)   # leftovers of an interrupted run
    ctx.log(f"archives: {len(arcs)} total, {len(done)} already done")
    tally = Counter()
    with open(mpath, "a", encoding="utf-8") as fm, open(apath, "a", encoding="utf-8") as fa:
        for idx, (d, rel, size) in enumerate(arcs):
            if (d, rel) in done or (args.only and args.only not in rel):
                continue
            path = ctx.file_path(d, rel)
            ext = file_ext(split_parts(rel)[-1])
            t0 = time.time()
            ctx.log(f"archive {d}:{rel}  ({gb(size)})")
            info = {"d": d, "a": rel, "size": size, "ext": ext, "status": "ok", "err": "", "hashed": "Y",
                    "members": 0, "bytes": 0, "member_errors": 0}
            try:
                if ext == ".zip":
                    _do_zip(ctx, ref, path, d, rel, info, partial[(d, rel)], fm, tally)
                else:
                    _do_7z(ctx, ref, path, d, rel, idx, info, fm, tally)
            except Exception as e:
                info.update(status="unreadable", err=f"{type(e).__name__}:{e}"[:300])
                tally["archive exception"] += 1
            tally[f"archive status {info['status']}"] += 1
            fm.flush()
            fa.write(json.dumps(info, ensure_ascii=False) + "\n")
            fa.flush()
            ctx.log(f"  -> {info['status']}, {info['members']:,} members, {gb(info['bytes'])}, "
                    f"{info['member_errors']} member errors, hashed={info['hashed']}, {(time.time() - t0) / 60:.1f} min {info['err']}")
    ctx.log(f"archives DONE. tally: {dict(tally)}")
    ctx.stats_update("archives", {"this_run": dict(tally)})


def _member_row(ref, d, rel, name, size, sha, dm, czi, err):
    row = {"d": d, "a": rel, "m": name, "size": size, "sha": sha, "dm": dm}
    if err:
        row["err"] = err
    if czi is not None:
        p = czi_from_bytes(*czi)
        row["czi"] = {k: v for k, v in p.items()}
    return row


def _do_zip(ctx, ref, path, d, rel, info, have, fm, tally):
    try:
        zf = zipfile.ZipFile(longpath(path))
    except zipfile.BadZipFile as e:
        info.update(status="truncated", err=f"BadZipFile: {e} (no central directory)", hashed="N:cannot-open")
        return
    t0 = last = time.time()
    with zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        info["members"] = len(infos)
        info["bytes"] = sum(i.file_size for i in infos)
        nbytes = 0
        for n, zi in enumerate(infos, 1):
            if zi.filename in have:
                continue
            if zi.flag_bits & 0x1:
                info["status"] = "encrypted"
                fm.write(json.dumps({"d": d, "a": rel, "m": zi.filename, "size": zi.file_size, "sha": "",
                                     "dm": False, "err": "encrypted"}) + "\n")
                continue
            want = zi.filename.lower().endswith(".czi") and not zi.filename.lower().endswith(".preview.czi")
            try:
                with zf.open(zi) as f:
                    sha, nb, dm, czi = stream_hash(f, want)
                row = _member_row(ref, d, rel, zi.filename, zi.file_size, sha, dm, czi, None if nb == zi.file_size else f"size-mismatch:{nb}")
            except (zipfile.BadZipFile, EOFError, OSError, RuntimeError, NotImplementedError, ValueError) as e:
                msg = f"{type(e).__name__}:{e}"[:160]
                row = {"d": d, "a": rel, "m": zi.filename, "size": zi.file_size, "sha": "", "dm": False, "err": msg}
                info["member_errors"] += 1
                tally["zip member " + type(e).__name__] += 1
                if isinstance(e, EOFError) or "truncat" in msg.lower() or "end-of-stream" in msg.lower():
                    info["status"] = "truncated"
            fm.write(json.dumps(row, ensure_ascii=False) + "\n")
            nbytes += zi.file_size
            if time.time() - last >= 60:
                last = time.time()
                ctx.log(f"    {n:,}/{len(infos):,} members, {gb(nbytes)} of {gb(info['bytes'])}  {nbytes / (last - t0) / 1e6:.0f} MB/s")


def _do_7z(ctx, ref, path, d, rel, idx, info, fm, tally):
    members, err, rc = list_7z(path)
    files = [m for m in members if not m[2]]
    info["members"] = len(files)
    info["bytes"] = sum(m[1] for m in files)
    if err and not files:
        info.update(status=err, err=f"7z l exit {rc}", hashed="N:cannot-list")
        return
    if err:
        info.update(status=err, err=f"7z l exit {rc} (partial listing)")
    if any(m[3] for m in files):
        info["status"] = "encrypted"
    if files and all(path_class(m[0].replace("/", "\\")) == "software" for m in files):
        for name, size, _, _ in files:
            fm.write(json.dumps({"d": d, "a": rel, "m": name.replace("\\", "/"), "size": size, "sha": "",
                                 "dm": False, "err": "listed-only"}) + "\n")
        info["hashed"] = "N:all-members-software"
        return
    if info["status"] in ("encrypted", "unreadable"):
        info["hashed"] = "N:" + info["status"]
        return
    tmp = os.path.join(ctx.p("_tmp"), f"a{idx}")
    need = info["bytes"] * 1.05 + 5e9
    free = shutil.disk_usage(ctx.out).free
    if need > free:
        info.update(status="unreadable", err=f"not enough free space to extract ({gb(free)} free, need {gb(need)})", hashed="N:no-space")
        return
    os.makedirs(longpath(tmp), exist_ok=True)
    try:
        r = subprocess.run([SEVENZIP, "x", "-y", "-bd", "-sccUTF-8", "-scsUTF-8", f"-o{tmp}", path], capture_output=True)
        text = (r.stdout + r.stderr).decode("utf-8", "replace")
        if r.returncode >= 2:
            info["status"] = "truncated" if "unexpected end" in text.lower() else "unreadable"
            info["err"] = f"7z x exit {r.returncode}: " + " ".join(text.split())[-200:]
        elif r.returncode == 1:
            info["err"] = "7z x warning: " + " ".join(text.split())[-160:]
        nfiles = 0
        for base, _, names in os.walk(longpath(tmp)):
            for nm in sorted(names):
                full = os.path.join(base, nm)
                relm = os.path.relpath(full, longpath(tmp)).replace("\\", "/")
                want = nm.lower().endswith(".czi") and not nm.lower().endswith(".preview.czi")
                try:
                    with open(full, "rb") as f:
                        sha, nb, dm, czi = stream_hash(f, want)
                    row = _member_row(ref, d, rel, relm, nb, sha, dm, czi, None)
                except OSError as e:
                    row = {"d": d, "a": rel, "m": relm, "size": 0, "sha": "", "dm": False, "err": f"{type(e).__name__}:{e}"[:160]}
                    info["member_errors"] += 1
                    tally["7z member OSError"] += 1
                fm.write(json.dumps(row, ensure_ascii=False) + "\n")
                nfiles += 1
        if nfiles != len(files):
            info["err"] = (info["err"] + f" extracted {nfiles} files, listing has {len(files)}").strip()
            tally["7z extracted-vs-listing mismatch"] += 1
    finally:
        shutil.rmtree(longpath(ctx.p("_tmp")), ignore_errors=True)


# ---------------------------------------------------------------------------------------------
# stage 4: assemble
# ---------------------------------------------------------------------------------------------
FILES_COLS = ["drive", "relpath", "size", "mtime", "sha256", "ext", "class", "dup_n", "archive_copies",
              "in_production", "czi_stand", "czi_system", "czi_serials", "czi_stand_keys", "czi_modes",
              "czi_cameras", "czi_acq_datetime", "czi_objective", "czi_zen", "czi_user", "czi_no_hwsetting",
              "instrument", "instrument_rule", "tif_software", "tif_make", "tif_model", "tif_desc_head",
              "tif_is_ome", "tif_lsminfo", "tif_pages", "tif_sibling_czi", "dcm_modality", "dcm_manufacturer",
              "dcm_model", "dcm_study_date", "dcm_species", "dcm_has_patient_name", "dcm_has_birth_date", "flag"]


def czi_cols(p):
    if not p or not p.get("ok"):
        return {}
    return {"czi_stand": p["stand"], "czi_system": p["system"], "czi_serials": ";".join(p["serials"]),
            "czi_stand_keys": ";".join(p["keys"]), "czi_modes": ";".join(p["modes"]),
            "czi_cameras": ";".join(p["cameras"]), "czi_acq_datetime": p["acq_dt"],
            "czi_objective": p["objective"], "czi_zen": p["zen"], "czi_user": p["user"],
            "czi_no_hwsetting": "Y" if (not p["has_hw"] and not p["has_exp"]) else "N",
            "instrument": p["instrument"], "instrument_rule": p["rule"]}


def assemble(ctx, args):
    ref = load_instruments()
    man = ctx.manifest()
    log = ctx.log
    summary_p = ctx.p("summary.md")
    if os.path.exists(summary_p):
        os.remove(summary_p)          # its presence is the sign that files.csv is complete: write it LAST
    probes = {(r["d"], r["r"]): r for r in read_jsonl(ctx.p("probe.jsonl"))}
    arch_info = {(r["d"], r["a"]): r for r in read_jsonl(ctx.p("archives_done.jsonl"))}
    members = defaultdict(list)                     # (d, archive) -> latest row per member name
    seen = {}
    for r in read_jsonl(ctx.p("archive_members.jsonl")):
        seen[(r["d"], r["a"], r["m"])] = r
    for k, r in seen.items():
        members[(k[0], k[1])].append(r)
    del seen

    # ---- sets for sibling checks
    czi_stems = set()
    mhd_stems = set()
    for (d, rel) in man:
        parts = split_parts(rel)
        stem = "\\".join(parts[:-1] + [os.path.splitext(parts[-1])[0].lower()])
        ext = file_ext(parts[-1])
        if ext == ".czi":
            czi_stems.add((d, stem))
        elif ext == ".mhd":
            mhd_stems.add(stem)

    # ---- pass 1: the class + dedup keys of every loose file
    loose = {}                                      # (d, rel) -> dict(class, probe)
    by_sha = defaultdict(list)
    for (d, rel), r in man.items():
        by_sha[r["sha256"]].append(f"{d}:{rel}")
    class_of = {}
    arch_software = {k for k, v in arch_info.items()
                     if v.get("hashed", "").startswith("N:all-members-software")}
    for (d, rel), r in man.items():
        c = path_class(rel, mhd_stems)
        if c == "czi":
            c = czi_class(probes.get((d, rel), {"ok": False}))
        if c == "archive" and (d, rel) in arch_software:
            c = "software"
        if c == "other" and (d, rel) in probes and probes[(d, rel)].get("kind") == "dcm" and probes[(d, rel)].get("ok"):
            c = "volume"
        class_of[(d, rel)] = c

    # ---- member classes / czi results
    member_rows = []
    arch_class_counts = {}
    for (d, a), ms in members.items():
        cnt = Counter()
        for m in ms:
            c = path_class(m["m"].replace("/", "\\"))
            cz = czi_summary(m.get("czi"), ref) if m.get("czi") else {}
            if c == "czi":
                c = czi_class(m["czi"]) if m.get("czi") else "czi-unreadable"
            if c == "other" and m.get("dm"):
                c = "volume"
            m["_class"], m["_czi"] = c, cz
            cnt[c] += 1
        arch_class_counts[(d, a)] = cnt

    # ---- hashes we need to look up in production
    need = set(by_sha)
    for ms in members.values():
        need.update(m["sha"] for m in ms if m.get("sha"))
    prod = defaultdict(list)                        # sha -> [(acq, instrument, file)]
    pp = ctx.p("production_hashes.csv")
    if os.path.exists(pp):
        with open(pp, newline="", encoding="utf-8") as f:
            rd = csv.reader(f)
            next(rd)
            for sha, acq, inst, fn in rd:
                if sha in need:
                    prod[sha].append((acq, inst, fn))
    else:
        log("WARNING: production_hashes.csv missing -- in_production will be blank")

    # ---- dup groups over loose files + members
    locs = defaultdict(list)                        # sha -> [(kind, 'D:loc', size)]
    sz = {}
    for (d, rel), r in man.items():
        locs[r["sha256"]].append(("loose", f"{d}:{rel}"))
        sz[r["sha256"]] = int(r["size"])
    for (d, a), ms in members.items():
        for m in ms:
            if m.get("sha"):
                locs[m["sha"]].append(("member", f"{d}:{a}!{m['m']}"))
                sz.setdefault(m["sha"], m["size"])
    loose_by_sha = {s: [x for k, x in v if k == "loose"] for s, v in locs.items()}

    # ---- files.csv
    flags_tally = Counter()
    files_bytes = 0
    n_rows = 0
    inst_rows = []
    with open(ctx.p("files.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FILES_COLS)
        w.writeheader()
        for (d, rel), r in sorted(man.items()):
            sha = r["sha256"]
            row = {"drive": d, "relpath": rel, "size": r["size"], "mtime": r["mtime"], "sha256": sha,
                   "ext": file_ext(split_parts(rel)[-1]), "class": class_of[(d, rel)],
                   "dup_n": len(loose_by_sha[sha]),
                   "archive_copies": sum(1 for k, _ in locs[sha] if k == "member")}
            hit = prod.get(sha)
            if hit:
                row["in_production"] = ";".join(sorted({a for a, _, _ in hit}))
            flags = []
            p = probes.get((d, rel))
            if p:
                if p["kind"] == "czi":
                    cs = czi_summary(p, ref)
                    row.update(czi_cols(cs))
                    if cs and cs["conflict"]:
                        flags.append("fingerprint-conflict")
                    if cs and cs["instrument"] == "LSM9" and cs["rule"].startswith("stand-key"):
                        flags.append("LSM-key-without-LSM900-serial")
                    if cs and cs.get("has_exp") and not (cs["has_hw"] or cs["serials"] or cs["keys"]):
                        flags.append("experiment-only")
                elif p["kind"] == "tif":
                    if p.get("ok"):
                        row.update(tif_software=p["software"], tif_make=p["make"], tif_model=p["model"],
                                   tif_desc_head=p["desc_head"], tif_is_ome=p["is_ome"], tif_lsminfo=p["lsminfo"],
                                   tif_pages=p["pages"])
                    parts = split_parts(rel)
                    stem = "\\".join(parts[:-1] + [os.path.splitext(parts[-1])[0].lower()])
                    row["tif_sibling_czi"] = "Y" if (d, stem) in czi_stems else "N"
                elif p["kind"] == "dcm" and p.get("ok"):
                    row.update(dcm_modality=p["modality"], dcm_manufacturer=p["manufacturer"], dcm_model=p["model"],
                               dcm_study_date=p["study_date"], dcm_species=p["species"],
                               dcm_has_patient_name=p["has_name"], dcm_has_birth_date=p["has_birth"])
                if not p.get("ok"):
                    flags.append(f"probe-error:{p.get('err', '?')}"[:120])
            if row["class"] == "czi-processed":
                flags.append("no-HardwareSetting-or-Experiment")
            if file_ext(split_parts(rel)[-1]) == ".gz":
                flags.append("bare-gz")
            if int(r["size"]) == 0:
                flags.append("zero-byte")
            ph = personal_hit(rel)
            if ph:
                flags.append("personal-admin-heuristic:" + "+".join(ph))
            row["flag"] = ";".join(flags)
            for fl in flags:
                flags_tally[fl.split(":")[0]] += 1
            w.writerow(row)
            files_bytes += int(r["size"])
            n_rows += 1
            if row.get("instrument"):
                inst_rows.append((d, rel, row["instrument"], sha))
    log(f"files.csv: {n_rows:,} rows, {gb(files_bytes)}")

    # ---- archives.csv / archive_members.csv
    with open(ctx.p("archives.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["drive", "archive_relpath", "size", "ext", "status", "err", "members", "uncompressed_bytes",
                    "member_errors", "nested_archives", "classes", "hashed"])
        for (d, a), ai in sorted(arch_info.items()):
            cnt = arch_class_counts.get((d, a), Counter())
            w.writerow([d, a, ai["size"], ai["ext"], ai["status"], ai["err"], ai["members"], ai["bytes"],
                        ai["member_errors"], cnt.get("archive", 0),
                        ";".join(f"{k}:{v}" for k, v in sorted(cnt.items())), ai["hashed"]])
    nm = 0
    with open(ctx.p("archive_members.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["drive", "archive_relpath", "member", "size", "sha256", "ext", "class", "in_production",
                    "on_drives", "flag", "instrument", "czi_acq_datetime"])
        for (d, a), ms in sorted(members.items()):
            for m in ms:
                sha = m.get("sha", "")
                hit = prod.get(sha)
                on = loose_by_sha.get(sha, []) if sha else []
                flag = ";".join(x for x in (m.get("err", ""),
                                            "personal-admin-heuristic" if personal_hit(m["m"]) else "") if x)
                cz = m["_czi"]
                w.writerow([d, a, m["m"], m["size"], sha, file_ext(m["m"].split("/")[-1]), m["_class"],
                            ";".join(sorted({x[0] for x in hit})) if hit else "", ";".join(on), flag,
                            cz.get("instrument", ""), cz.get("acq_dt", "")])
                nm += 1
    log(f"archive_members.csv: {nm:,} rows")

    # ---- dup_groups.csv
    ngroups = 0
    with open(ctx.p("dup_groups.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sha256", "size", "n_locations", "kind", "location"])
        for sha, ls in locs.items():
            if len(ls) > 1:
                ngroups += 1
                for kind, loc in ls:
                    w.writerow([sha, sz[sha], len(ls), kind, loc])
    log(f"dup_groups.csv: {ngroups:,} groups")

    # ---- validation 2: drive instrument vs the production row holding the same bytes
    val_rows, disagree = 0, []
    for d, rel, inst, sha in inst_rows:
        for acq, pinst, _ in prod.get(sha, [])[:1]:
            val_rows += 1
            if pinst != inst:
                disagree.append((d, rel, inst, acq, pinst))
    with open(ctx.p("validation_drive_vs_production.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["drive", "relpath", "drive_fingerprint_instrument", "production_acq_id", "production_instrument"])
        w.writerows(disagree)

    write_summary(ctx, ref, man, class_of, probes, arch_info, members, arch_class_counts, prod, locs,
                  sz, files_bytes, n_rows, flags_tally, val_rows, disagree, nm, ngroups)


def write_summary(ctx, ref, man, class_of, probes, arch_info, members, arch_class_counts, prod, locs, sz,
                  files_bytes, n_rows, flags_tally, val_rows, disagree, n_members, n_groups):
    L = []
    P = L.append
    stats = ctx.stats()
    P(f"# Drive catalog summary\n\nGenerated {dt.datetime.now():%Y-%m-%d %H:%M} by `catalog.py` {VERSION}. "
      f"Writing this file is the LAST step; its presence means `files.csv` is complete.\n")
    # reconciliation
    per_drive = defaultdict(lambda: [0, 0])
    for (d, _), r in man.items():
        per_drive[d][0] += 1
        per_drive[d][1] += int(r["size"])
    P("## Reconciliation\n")
    P(f"- `files.csv` rows: **{n_rows:,}** (manifests: {sum(v[0] for v in per_drive.values()):,}); "
      f"bytes {gb(files_bytes)}")
    for d, (n, b) in sorted(per_drive.items()):
        P(f"  - {d}: {n:,} files, {gb(b)}")
    st = Counter(v["status"] for v in arch_info.values())
    P(f"- archives read: {len(arch_info)} ({dict(st)}); members catalogued: {n_members:,}")
    pr = stats.get("production", {})
    P(f"- registry rows in production at the time of the `production` pass: {pr.get('registry_rows', '?')} "
      f"(registry file mtime {pr.get('registry_mtime', '?')})\n")
    # class by drive
    P("## Class by drive (files, GB)\n\n| class | D1 files | D1 GB | D2 files | D2 GB |\n|---|---:|---:|---:|---:|")
    cc = defaultdict(lambda: [0, 0, 0, 0])
    for (d, rel), r in man.items():
        c = cc[class_of[(d, rel)]]
        i = 0 if d == "D1" else 2
        c[i] += 1
        c[i + 1] += int(r["size"])
    for c in CLASSES + sorted(set(cc) - set(CLASSES)):
        if c in cc:
            v = cc[c]
            P(f"| {c} | {v[0]:,} | {v[1] / 1e9:,.1f} | {v[2]:,} | {v[3] / 1e9:,.1f} |")
    # czi instruments
    P("\n## .czi: instrument by class (files, GB, acquisition years)\n\n| class | instrument | files | GB | years |\n|---|---|---:|---:|---|")
    tab = defaultdict(lambda: [0, 0, set()])
    unknown_fp = Counter()
    lsm_serials = Counter()
    lsm_no_serial = []
    ext_dirs = Counter()
    czi_probe_seen = 0
    for (d, rel), r in man.items():
        p = probes.get((d, rel))
        if not p or p["kind"] != "czi":
            continue
        czi_probe_seen += 1
        cs = czi_summary(p, ref)
        c = class_of[(d, rel)]
        inst = cs.get("instrument", "(unreadable)") if cs else "(unreadable)"
        t = tab[(c, inst)]
        t[0] += 1
        t[1] += int(r["size"])
        y = (cs.get("acq_dt") or "")[:4] if cs else ""
        if y:
            t[2].add(y)
        if cs:
            if inst == "unknown":
                unknown_fp[(";".join(cs["serials"]) or "(none)", ";".join(cs["keys"]) or "(none)", cs["stand"] or "(none)")] += 1
            if "LSM" in cs["keys"]:
                for s in cs["serials"]:
                    lsm_serials[s] += 1
                if "03761880" not in cs["serials"]:
                    lsm_no_serial.append(f"{d}:{rel}")
            if inst == "EXTERNAL:AxioImagerZ2":
                ext_dirs["\\".join(split_parts(rel)[:-1][:6])] += 1
    for (c, inst), (n, b, ys) in sorted(tab.items()):
        P(f"| {c} | {inst} | {n:,} | {b / 1e9:,.1f} | {min(ys) + '-' + max(ys) if ys else ''} |")
    P(f"\n### Unknown fingerprints (serials | stand keys | stand)\n")
    if unknown_fp:
        P("| serials | stand keys | stand | files |\n|---|---|---|---:|")
        for (s, k, st_), n in unknown_fp.most_common(30):
            P(f"| {s} | {k} | {st_} | {n} |")
    else:
        P("none")
    P("\n### LSM-serial check (does the full scan find another LSM?)\n")
    P("Serials seen on files with stand key `LSM`: " + (", ".join(f"`{s}` x{n}" for s, n in lsm_serials.most_common(12)) or "none"))
    P(f"\n**Files with key `LSM` but WITHOUT serial 03761880: {len(lsm_no_serial)}**")
    for x in lsm_no_serial[:20]:
        P(f"- {x}")
    P("\n### External Axio Imager.Z2 (serial 784053): folders\n")
    for k, n in ext_dirs.most_common(10):
        P(f"- {n:,} files: `{k}`")
    # duplicates
    P("\n## Duplicates (loose files only, by sha256)\n")
    by_sha = defaultdict(list)
    for (d, rel), r in man.items():
        by_sha[r["sha256"]].append((d, int(r["size"])))
    uniq = sum(v[0][1] for v in by_sha.values())
    tot = files_bytes
    within = defaultdict(lambda: [0, 0])
    for s, v in by_sha.items():
        if len(v) > 1:
            ds = {x[0] for x in v}
            k = "both drives" if len(ds) == 2 else f"{next(iter(ds))} only"
            within[k][0] += 1
            within[k][1] += v[0][1] * (len(v) - 1)
    P(f"- distinct content: **{len(by_sha):,}** files, {gb(uniq)}; redundant: {gb(tot - uniq)} ({(tot - uniq) / tot:.1%})")
    for k, (n, b) in sorted(within.items()):
        P(f"  - repeated on {k}: {n:,} contents, {gb(b)} redundant")
    P(f"- `dup_groups.csv` groups (loose + archive members): {n_groups:,}")
    # in production
    P("\n## Already in production (by sha256)\n")
    inprod = Counter()
    inprod_b = Counter()
    top = Counter()
    for (d, rel), r in man.items():
        if r["sha256"] in prod:
            inst = probes.get((d, rel)) and czi_summary(probes[(d, rel)], ref).get("instrument", "")
            k = inst or "(non-czi / no fingerprint)"
            inprod[k] += 1
            inprod_b[k] += int(r["size"])
            top[(d, split_parts(rel)[0])] += 1
    for k, n in inprod.most_common():
        P(f"- {k}: {n:,} files, {gb(inprod_b[k])}")
    P("- by top folder: " + "; ".join(f"{d}:{t} {n:,}" for (d, t), n in top.most_common(8)))
    P(f"\n**Validation 2** (drive fingerprint vs production instrument for the same bytes): {val_rows:,} compared, "
      f"**{len(disagree)} disagree**.")
    for d, rel, i, acq, pi in disagree[:25]:
        P(f"- {d}:{rel} drive={i} production={acq}/{pi}")
    pa = ctx.p("production_instrument_audit.csv")
    if os.path.exists(pa):
        with open(pa, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        bad = Counter((r["registry_instrument"], r["fingerprint_instrument"]) for r in rows if r["agree"] == "N")
        P(f"\n**Validation 1** (production audit): {len(rows):,} microscopy acquisitions, "
          f"{sum(bad.values())} disagree: " + (", ".join(f"registry `{a}` -> rule `{b}` x{n}" for (a, b), n in bad.items()) or "none"))
    # archives
    P("\n## Archives\n\n| drive | archive | status | members | GB | nested | hashed | classes |\n|---|---|---|---:|---:|---:|---|---|")
    for (d, a), ai in sorted(arch_info.items(), key=lambda kv: -kv[1]["size"]):
        cnt = arch_class_counts.get((d, a), Counter())
        P(f"| {d} | `{a[-60:]}` | {ai['status']} | {ai['members']:,} | {ai['bytes'] / 1e9:,.1f} | {cnt.get('archive', 0)} | {ai['hashed']} | "
          + ", ".join(f"{k}:{v}" for k, v in cnt.most_common(4)) + " |")
    # dicom
    P("\n## DICOM / volume files (counts only)\n")
    dcm = Counter()
    dates = []
    name_n = birth_n = 0
    for (d, rel), p in probes.items():
        if p["kind"] == "dcm" and p.get("ok"):
            dcm[(p["modality"] or "?", p["manufacturer"] or "?")] += 1
            if p["study_date"]:
                dates.append(p["study_date"])
            name_n += p["has_name"] == "Y"
            birth_n += p["has_birth"] == "Y"
    for (m, mf), n in dcm.most_common(15):
        P(f"- modality `{m}`, manufacturer `{mf}`: {n:,}")
    P(f"- study dates {min(dates) if dates else ''} .. {max(dates) if dates else ''}; "
      f"**with a patient name: {name_n:,}; with a birth date: {birth_n:,}** of {sum(dcm.values()):,} readable DICOM")
    vc = Counter(file_ext(split_parts(rel)[-1]) or "(none)" for (d, rel), c in class_of.items() if c == "volume")
    P("- volume class by extension: " + ", ".join(f"{e} {n:,}" for e, n in vc.most_common(10)))
    # personal
    P("\n## Personal/admin heuristic hits (report-only)\n")
    ph = Counter()
    for (d, rel) in man:
        for h in personal_hit(rel):
            ph[h] += 1
    P("token counts: " + (", ".join(f"`{t}` {n:,}" for t, n in ph.most_common(15)) or "none"))
    # error tally
    P("\n## Error tallies\n")
    P(f"- flags in files.csv: {dict(flags_tally)}")
    for k, v in ctx.stats().items():
        P(f"- pass `{k}`: `{json.dumps(v, ensure_ascii=False)[:600]}`")
    # probe totals from the cache (the pass tallies only cover the last run)
    pt = Counter()
    for p in probes.values():
        pt[f"{p['kind']} {'ok' if p.get('ok') else 'ERR ' + str(p.get('err', '?')).split(':')[0]}"] += 1
    P(f"- probe cache, all runs: {dict(pt)}")
    with open(ctx.p("summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    ctx.log("summary.md written")


# ---------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["production", "probe", "archives", "assemble", "all"])
    ap.add_argument("--staging", default=STAGING)
    ap.add_argument("--out", default=None, help="default <staging>\\_analysis\\catalog")
    ap.add_argument("--nas", default=NAS_ROOT)
    ap.add_argument("--limit", type=int, default=0, help="probe: only the first N pending files (testing)")
    ap.add_argument("--only", default="", help="probe/archives: only paths containing this text (testing)")
    ap.add_argument("--retry-errors", action="store_true", help="probe: redo files that failed with an I/O error")
    args = ap.parse_args()
    keep_awake()
    ctx = Ctx(args.staging, args.out or os.path.join(args.staging, "_analysis", "catalog"), args.nas)
    ctx.log(f"catalog {VERSION} stage={args.stage} out={ctx.out}")
    stages = ["production", "probe", "archives", "assemble"] if args.stage == "all" else [args.stage]
    for s in stages:
        globals()[s](ctx, args)


if __name__ == "__main__":
    main()
