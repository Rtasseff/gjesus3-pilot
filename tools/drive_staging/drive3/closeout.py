#!/usr/bin/env python3
"""closeout.py -- the M. Jesus drive's close-out: the fate of every file of the staged copy, by SHA-256, before
the copy is deleted. Record: tasks/drive3_closeout.md.

READ-ONLY. Production (J:\\gjesus3-data) and the staged copy (J:\\_staging_drive3_MJ) are only read; every output
goes to --out (keep it off the NAS). Nothing is copied or deleted anywhere. No file of the drive is re-hashed: the
staged copy's own manifest.csv carries every SHA-256 (only the members of a .zip are hashed, read from the zip).

    set PYTHONDONTWRITEBYTECODE=1
    python tools/drive_staging/drive3/closeout.py --out DIR [--raw-index CSV] [--stat] [--walk]

Each row of the staged copy's manifest.csv gets ONE category, the first that applies:

  not kept  zero-byte                 no content (stream P's rule: zero-byte files are counted, never placed)
  KEPT      in-raw                    its bytes are a file of a registered acquisition: every live acquisition's
                                      checksums.json (p_verify.live_raw_index), or --raw-index saved the same day
            placed                    its bytes are listed in a project's working\\historical_drives\\_INDEX.csv
                                      (every registered project, every drive and batch)
            holding                   its bytes are listed in the holding folder's manifest.csv
            archive-expanded          a .zip whose every member's bytes are kept (stream P's P1: archives are
                                      expanded, Ryan 2026-10-02); the members are read from the staged zip
  not kept  junk                      Ryan's list (2026-09-30: desktop.ini, Thumbs.db, .DS_Store, AppleDouble ._*,
                                      the two WD installers) and A2's accepted additions (Office temp files,
                                      Icon<CR>, folders.cache / thumbs.cache): a2_common's lists
            personal                  biomaGUNE MJ's personal screen (bmj_plan.judge_personal; Ryan 2026-10-08:
                                      ignore them)
            mri-kspace, mri-2dseq,    ParaVision files of an exam /raw/ holds as DICOM (Ryan 2026-10-04: MRI is
            mri-params                registered with DICOM only): the exam's <study>/<exam> is a live registry
                                      original_name (and a 2dseq's reconstruction is among the acquisition's
                                      recon<idx>_*.dcm); study-level files of a study with a registered exam.
                                      NOT for a DICOM-less placeholder (no file in /raw/): Ryan 2026-10-08 retires
                                      them and keeps their files, so their drive files block until placed
            mri-dicom-reexport        DICOM of a registered exam that A1 found re-exported (the same instances,
                                      other bytes: A1 §2.2, exam class b-export / b-mixed)
            czi-resave-of-production  stream C §1.4: a re-save of a production acquisition (same instrument,
                                      second and name); its parent ACQ-ID is live
            czi-resave-within-drive   stream C §1.4 (gate R2): a same-name, pixel-identical re-save whose kept twin
                                      is in /raw/
  BLOCKER   anything else, listed with its folder and a hint.

--stat     stats one kept location per content on the NAS (exists, same size), and every member of an expanded
           archive; a content with no good location blocks.
--walk     walks the staged tree: a file in it that its manifest does not list blocks (it would be deleted
           unreconciled).

The last line is the verdict: READY TO DELETE, or BLOCKED: <n> files.
"""
import argparse
import collections
import concurrent.futures
import csv
import gzip
import hashlib
import io
import json
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))       # tools/drive_staging/drive3
DS = os.path.dirname(HERE)                              # tools/drive_staging
TOOLS = os.path.dirname(DS)                             # tools
REPO = os.path.dirname(TOOLS)
for _p in (TOOLS, DS, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import historical_paths as H  # noqa: E402
import nonraw_placement as NP  # noqa: E402
import a2_common as A2  # noqa: E402  (the junk lists, unchanged)
import bmj_plan as B  # noqa: E402  (the personal screen, unchanged)
import p_plan as P  # noqa: E402  (the staged copy's location)
import p_verify as V  # noqa: E402  (the live /raw/ index)

ANALYSIS = P.ANALYSIS
STREAMS = r"D:\projects\gjesus3\drive3_streams"
A1_FILES = os.path.join(ANALYSIS, "a1", "a1_files.csv.gz")
A1_EXAMS = os.path.join(ANALYSIS, "a1", "mri_exams.csv")
CZI_EXCLUDED = os.path.join(STREAMS, "czi", "plan", "excluded.csv")
CZI_OUT_OF_SCOPE = os.path.join(STREAMS, "czi", "plan", "out_of_scope.csv")
ARCHIVE_CHECK = os.path.join(REPO, "tasks", "drive3_mri_archive_check.csv")
ARCHIVE_STUDIES = r"D:\projects\gjesus3\mri_archive\census\archive_studies_20261007.csv"
DRIVE_LABEL = P.LABEL                                   # drive3_MJesus-MFB
BMJ = B.BMJ

KEPT = ("in-raw", "placed", "holding", "archive-expanded")
NOT_KEPT = ("zero-byte", "junk", "personal", "mri-kspace", "mri-2dseq", "mri-params", "mri-dicom-reexport",
            "czi-resave-of-production", "czi-resave-within-drive")
BLOCKER = "BLOCKER"
ORDER = ("in-raw", "placed", "holding", "archive-expanded") + NOT_KEPT + (BLOCKER,)
RULES = {
    "in-raw": "bytes = a file of a registered acquisition (live checksums.json)",
    "placed": "bytes listed in a project's working\\historical_drives\\_INDEX.csv",
    "holding": "bytes listed in the holding folder's manifest.csv",
    "archive-expanded": "a .zip stream P expanded (P1, Ryan 2026-10-02: no zips); every member's bytes kept",
    "zero-byte": "no content (stream P: zero-byte files are counted, never placed)",
    "junk": "Ryan 2026-09-30 (desktop.ini, Thumbs.db, .DS_Store, ._*, 2 WD installers) + A2's accepted additions",
    "personal": "bmj gate §4 personal screen; Ryan 2026-10-08: ignore",
    "mri-kspace": "Ryan 2026-10-04: MRI in /raw/ is DICOM only; k-space of a registered exam",
    "mri-2dseq": "Ryan 2026-10-04: DICOM only; 2dseq of a reconstruction /raw/ holds as DICOM",
    "mri-params": "Ryan 2026-10-04: DICOM only; ParaVision parameter files of a registered exam / study",
    "mri-dicom-reexport": "the exam is registered; this DICOM is a re-export of the same instances (A1 §2.2)",
    "czi-resave-of-production": "stream C gate §1.4: re-save of a production acquisition (parent ACQ-ID live)",
    "czi-resave-within-drive": "stream C gate §1.4 / R2: same-name pixel-identical re-save; its twin is in /raw/",
    BLOCKER: "in no category: must be kept somewhere, or ruled, before the deletion",
}
MRI_CLASSES = {"mri-kspace": "mri-kspace", "mri-2dseq": "mri-2dseq", "mri-params": "mri-params",
               "mri-study-params": "mri-params"}
RECON_RE = re.compile(r"(?:^|\\)pdata\\(\d+)\\2dseq$", re.I)
RAW_RECON_RE = re.compile(r"(?:^|[\\/])recon(\d+)_", re.I)
ACQ_RE = re.compile(r"ACQ-\d{8}-[A-Z0-9]+-\d+")
KEPT_TWIN_RE = re.compile(r"kept ([0-9a-f]{64})")
SHORT_TARBALLS = {"20200615_115642_jrc200615_m21_1019_1_1"}   # archive check finding 2: the archive copy is short


# ------------------------------------------------------------------------------------------- io

def lp(p):
    return NP.lp(p)


def it(path):
    opener = gzip.open if path.lower().endswith(".gz") else open
    with opener(lp(path), "rb") as fb:
        with io.TextIOWrapper(fb, encoding="utf-8-sig", newline="") as f:
            yield from csv.DictReader(f)


def wcsv(path, fields, rows):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    opener = gzip.open if path.lower().endswith(".gz") else open
    with opener(path, "wb") as fb:
        with io.TextIOWrapper(fb, encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow(r)


def sha256_file(path, bufsize=8 << 20):
    h = hashlib.sha256()
    with open(lp(path), "rb") as f:
        for b in iter(lambda: f.read(bufsize), b""):
            h.update(b)
    return h.hexdigest()


def gb(n):
    return f"{n / 1e9:,.2f}"


# ------------------------------------------------------------------------------------- the inputs

class Ctx:
    """Everything a row is judged against. Every production part is read live, read-only."""

    def __init__(self):
        self.raw = collections.defaultdict(list)       # sha256 -> [(acq_id, relpath in the acquisition)]
        self.recons = collections.defaultdict(set)     # acq_id -> {reconstruction index held as DICOM}
        self.acq_with_files = set()                    # acquisitions with at least one file in /raw/
        self.acq_path = {}                             # acq_id -> canonical_path (live registry)
        self.acq_registered = {}                       # acq_id -> registration_datetime (live registry)
        self.mri_exam = collections.defaultdict(list)  # "<study>/<exam>" -> [acq_id] (MRI, live)
        self.mri_study = {}                            # study -> one acq_id of it
        self.placed = collections.defaultdict(list)    # sha256 -> [(project, new_path, original_path)]
        self.placed_by_orig = {}                       # original_path (lower) -> (project, new_path)
        self.holding = collections.defaultdict(list)   # sha256 -> [(new_path, original_path)]
        self.hold_by_orig = {}
        self.projects = {}
        self.a1 = {}                                   # relpath -> (a1class, exam_dir, study_dir)
        self.exam_class = {}                           # "<study>/<exam>" -> A1 class_detail
        self.czi = {}                                  # sha256 -> (stream C reason, detail)
        self.oos = {}                                  # sha256 -> stream C out-of-scope reason
        self.staged_files = ""                         # the staged tree (for the zip members)
        self.archive_members = {}                      # relpath -> [(member, size, sha256)]
        self.facts = []                                # what was read, for the report


def exam_key_of(exam_dir):
    parts = (exam_dir or "").split("\\")
    return f"{parts[-2]}/{parts[-1]}" if len(parts) >= 2 else ""


def mri_name_key(original_name):
    """A registry original_name -> '<study>/<exam>' ('<study>/<exam>', or X1's '<study>__<exam>')."""
    n = (original_name or "").strip()
    if "/" in n:
        return n
    if "__" in n:
        s, e = n.rsplit("__", 1)
        return f"{s}/{e}"
    return n


def load_registry(ctx, nas):
    rows = list(it(os.path.join(nas, "registries", "registry_raw.csv")))
    for a in rows:
        ctx.acq_path[a["acq_id"]] = a.get("canonical_path") or ""
        ctx.acq_registered[a["acq_id"]] = a.get("registration_datetime") or ""
        if a.get("instrument") == "MRI":
            k = mri_name_key(a.get("original_name"))
            if "/" in k:
                ctx.mri_exam[k].append(a["acq_id"])
                ctx.mri_study.setdefault(k.split("/")[0], a["acq_id"])
    ctx.facts.append(f"registry_raw.csv: {len(rows):,} live acquisitions; MRI exams by <study>/<exam>: "
                     f"{len(ctx.mri_exam):,} in {len(ctx.mri_study):,} studies")
    return rows


def load_raw_index(ctx, nas, raw_index, out, say):
    if raw_index:
        src = f"--raw-index {raw_index}"
        rows = it(raw_index)
    else:
        rows = V.live_raw_index(nas, say=say)
        NP.wcsv(os.path.join(out, "live_raw_index.csv"), V.RAW_INDEX_FIELDS, rows)
        src = "built live now (saved as live_raw_index.csv)"
    n = 0
    acqs = {}
    for r in rows:
        ctx.raw[r["sha256"]].append((r["acq_id"], r["relpath"]))
        acqs[r["acq_id"]] = r.get("registration_datetime") or ""
        m = RAW_RECON_RE.search(r["relpath"])
        if m:
            ctx.recons[r["acq_id"]].add(str(int(m.group(1))))
        n += 1
    # A saved index is today's only if no indexed acquisition has left the registry and none was registered
    # after the newest one it holds. A live acquisition with no file in its checksums.json (an MRI
    # placeholder) has no index row: counted, not a difference.
    ctx.acq_with_files = set(acqs)
    gone = sorted(set(acqs) - set(ctx.acq_path))
    newest = max(acqs.values() or [""])
    newer = sorted(a for a, t in ctx.acq_registered.items() if a not in acqs and t > newest)
    empty = sum(1 for a in ctx.acq_path if a not in acqs) - len(newer)
    ctx.facts.append(f"/raw/ index ({src}): {n:,} files of {len(acqs):,} acquisitions, "
                     f"{len(ctx.raw):,} distinct SHA-256; {empty:,} live acquisitions list no file (placeholders)")
    return newer, gone


def load_trees(ctx, nas):
    ctx.projects = NP.load_projects(nas)
    n = trees = 0
    for name in sorted(ctx.projects):
        p = os.path.join(nas, "projects", NP.project_folder(name, ctx.projects), *NP.SUBDIR, H.INDEX_NAME)
        if not os.path.exists(lp(p)):
            continue
        trees += 1
        for r in it(p):
            if r.get("new_path") and r.get("sha256"):
                ctx.placed[r["sha256"]].append((name, r["new_path"], r.get("original_path") or ""))
                ctx.placed_by_orig.setdefault((r.get("original_path") or "").lower(), (name, r["new_path"]))
                n += 1
    hp = os.path.join(nas, NP.HOLDING_BASE, "manifest.csv")
    nh = 0
    for r in it(hp):
        if r.get("new_path") and r.get("sha256"):
            ctx.holding[r["sha256"]].append((r["new_path"], r.get("original_path") or ""))
            ctx.hold_by_orig.setdefault((r.get("original_path") or "").lower(), r["new_path"])
            nh += 1
    ctx.facts.append(f"project trees: {trees} _INDEX.csv of {len(ctx.projects)} registered projects, {n:,} rows "
                     f"({len(ctx.placed):,} distinct SHA-256); holding manifest.csv: {nh:,} rows")


def load_a1(ctx, a1_files, a1_exams):
    for r in it(a1_files):
        ctx.a1[r["relpath"]] = (r["a1class"], r["exam_dir"], r["study_dir"])
    for r in it(a1_exams):
        ctx.exam_class[r["exam_key"]] = r["class_detail"]
    ctx.facts.append(f"A1: {len(ctx.a1):,} files classed, {len(ctx.exam_class):,} MRI exams")


def load_czi(ctx, excluded, out_of_scope):
    """`excluded`: one or more stream-C-style excluded.csv (stream C's; a later .czi batch's built with its tools)."""
    for path in ([excluded] if isinstance(excluded, str) else excluded):
        for r in it(path):
            ctx.czi.setdefault(r["sha256"], (r["reason"], r.get("detail") or ""))
    for r in it(out_of_scope):
        ctx.oos[r["sha256"]] = r.get("reason") or ""
    ctx.facts.append(f"stream C: {len(ctx.czi):,} excluded contents, {len(ctx.oos):,} out-of-scope files")


def load_manifest(path):
    """[(relpath, size, sha256)] of the staged copy's manifest; STOP on a repeated relpath."""
    out, seen = [], set()
    for r in it(path):
        rel = r["relpath"]
        if rel in seen:
            raise SystemExit(f"STOP: the manifest lists {rel!r} twice")
        seen.add(rel)
        out.append((rel, int(r["size"] or 0), r["sha256"]))
    return out


# ------------------------------------------------------------------------------------- the rules

def junk_rule(rel):
    """A2's junk rules (a2_common.classify, its junk branch, unchanged lists): '' if not junk."""
    name = rel.split("\\")[-1]
    low = name.lower()
    if low in A2.JUNK_RULED:
        return f"ruled 2026-09-30: {A2.JUNK_RULED[low]}"
    if name.startswith("._"):
        return "ruled 2026-09-30: macOS AppleDouble ._ file"
    if rel.lower() in A2.WD_INSTALLERS:
        return "ruled 2026-09-30: WD installer"
    if low in ("icon\r", "icon\uf00d"):
        return "A2's addition: macOS folder-icon file (Icon<CR>)"
    if low in A2.VIEWER_CACHE:
        return "A2's addition: image-viewer cache (folders.cache / thumbs.cache)"
    if low.startswith("~$") or (low.startswith("~wrl") and low.endswith(".tmp")):
        return "A2's addition: Office temporary / owner file"
    return ""


def personal_rule(rel):
    if not rel.startswith(BMJ):
        return ""
    try:
        verdict, why = B.judge_personal(rel)
    except SystemExit:                  # an unjudged screen hit: no ruling covers it
        return ""
    return why if verdict == "personal" else ""


def is_placeholder(acqs, ctx):
    """Every registered acquisition of the exam holds no file in /raw/ (a DICOM-less placeholder: pending_dicom_regen
    no-source / not-applicable). Ryan 2026-10-08: they are retired, their files kept; so the DICOM-only rule cannot
    rule out their drive files, which must be placed (tasks/drive3_closeout_handover.csv)."""
    return not any(a in ctx.acq_with_files for a in acqs)


def mri_rule(rel, ctx):
    """-> (category, acq_id, detail) or None."""
    a = ctx.a1.get(rel)
    if not a:
        return None
    cls, exam_dir, study_dir = a
    if cls == "mri-dicom":
        key = exam_key_of(exam_dir)
        acqs = ctx.mri_exam.get(key)
        ec = ctx.exam_class.get(key, "")
        if acqs and ec.startswith(("b-export", "b-mixed")):
            return "mri-dicom-reexport", acqs[0], f"{key}: A1 {ec}"
        return None
    cat = MRI_CLASSES.get(cls)
    if not cat:
        return None
    if exam_dir:
        key = exam_key_of(exam_dir)
        acqs = ctx.mri_exam.get(key)
        if not acqs or is_placeholder(acqs, ctx):
            return None       # a placeholder's drive files are its only data: kept, never ruled out (Ryan 2026-10-08)
        if cat == "mri-2dseq":
            m = RECON_RE.search(rel)
            idx = str(int(m.group(1))) if m else ""
            held = [x for x in acqs if idx and idx in ctx.recons.get(x, ())]
            if not held:
                return None
            return cat, held[0], f"{key} reconstruction {idx}"
        return cat, acqs[0], key
    study = os.path.basename(study_dir) if study_dir else ""
    if study and study in ctx.mri_study:
        return cat, ctx.mri_study[study], f"{study} (study-level)"
    return None


def czi_rule(sha, ctx):
    x = ctx.czi.get(sha)
    if not x:
        return None
    reason, detail = x
    if reason == "resave-of-production":
        m = ACQ_RE.search(detail)
        if m and m.group(0) in ctx.acq_path:
            return "czi-resave-of-production", m.group(0), detail
    if reason == "resave-within-plan":
        m = KEPT_TWIN_RE.search(detail)
        if m and m.group(1) in ctx.raw:
            return "czi-resave-within-drive", ctx.raw[m.group(1)][0][0], detail
    return None


def archive_rule(rel, ctx):
    """A .zip whose every member's bytes are kept -> ('archive-expanded', where, detail); else None."""
    if os.path.splitext(rel)[1].lower() != ".zip" or not ctx.staged_files:
        return None
    path = os.path.join(ctx.staged_files, rel)
    if not os.path.exists(lp(path)):
        return None
    mem = []
    with zipfile.ZipFile(lp(path)) as z:
        for zi in z.infolist():
            if zi.is_dir():
                continue
            h = hashlib.sha256()
            with z.open(zi) as f:
                for b in iter(lambda: f.read(1 << 20), b""):
                    h.update(b)
            mem.append((zi.filename, zi.file_size, h.hexdigest()))
    ctx.archive_members[rel] = mem
    if not mem:
        return None
    where = []
    for name, size, sha in mem:
        if size == 0:
            continue
        loc = kept_where(sha, ctx, rel, name)
        if loc is None:
            return None
        where.append(loc[0])
    return "archive-expanded", ";".join(sorted(set(where))), f"{len(mem)} members, every one kept"


def kept_where(sha, ctx, rel, member=""):
    """(category, where, detail) when the bytes are kept, else None. A location of THIS file (or of this
    member of the archive `rel`) is preferred over another file with the same bytes."""
    if sha in ctx.raw:
        acq, f = ctx.raw[sha][0]
        return "in-raw", acq, f
    orig = H.original_display(DRIVE_LABEL, rel, rel if member else "", member)
    if sha in ctx.placed:
        own = ctx.placed_by_orig.get(orig.lower())
        if own and any(p == own[0] and n == own[1] for p, n, _o in ctx.placed[sha]):
            return "placed", own[0], own[1]
        p, n, _o = ctx.placed[sha][0]
        return "placed", p, n + f" (same bytes; {len(ctx.placed[sha])} location(s))"
    if sha in ctx.holding:
        own = ctx.hold_by_orig.get(orig.lower())
        if own and any(n == own for n, _o in ctx.holding[sha]):
            return "holding", "(holding)", own
        n, _o = ctx.holding[sha][0]
        return "holding", "(holding)", n + " (same bytes)"
    return None


def hint(rel, sha, ctx):
    if sha in ctx.oos:
        return f"outside-instrument raw (stream C §1.7: {ctx.oos[sha][:60]}): feat/drive3-foreign-raw"
    x = ctx.czi.get(sha)
    if x and x[0] == "derivative-nonraw":
        return ("stream C derivative for stream P (tasks/drive3_czi_nonraw_for_stream_p.csv): never handed over "
                "(p_plan.py handover --stream C)")
    if x:
        return f"stream C {x[0]} whose condition fails today: {x[1][:80]}"
    a = ctx.a1.get(rel)
    if a and a[0].startswith("mri-"):
        cls, exam_dir, study_dir = a
        if exam_dir:
            key = exam_key_of(exam_dir)
            if key in ctx.mri_exam and is_placeholder(ctx.mri_exam[key], ctx):
                return (f"MRI {cls} of a DICOM-less placeholder exam ({key}, {';'.join(ctx.mri_exam[key])}; Ryan "
                        f"2026-10-08: retired, files kept): place it (tasks/drive3_closeout_handover.csv)")
            if key in ctx.mri_exam and cls == "mri-2dseq":
                return (f"2dseq of a reconstruction /raw/ holds no DICOM of ({key}): place it as stream M §3.2 / P2 "
                        f"placed such reconstructions")
            if key in ctx.mri_exam:
                return f"MRI {cls} of the registered exam {key}, bytes not in /raw/ (A1 {ctx.exam_class.get(key, '?')})"
            return f"MRI {cls} of an exam /raw/ does not hold ({key}; A1 {ctx.exam_class.get(key, '?')})"
        return (f"MRI {cls} of a study with no registered exam ({os.path.basename(study_dir or '?')}): place it with "
                f"the study's exam folders")
    return f"no category (A1 class {a[0] if a else '?'})"


def classify(rel, size, sha, ctx):
    """One manifest row -> (category, where, detail). The first rule that applies wins (module docstring)."""
    if size == 0:
        return "zero-byte", "", ""
    k = kept_where(sha, ctx, rel) or archive_rule(rel, ctx)
    if k:
        return k
    j = junk_rule(rel)
    if j:
        return "junk", "", j
    pr = personal_rule(rel)
    if pr:
        return "personal", "", pr
    m = mri_rule(rel, ctx)
    if m:
        return m
    c = czi_rule(sha, ctx)
    if c:
        return c
    return BLOCKER, "", hint(rel, sha, ctx)


def fate_of(category):
    return "kept" if category in KEPT else "not kept" if category in NOT_KEPT else "BLOCKER"


def verdict_line(n_block):
    return "READY TO DELETE" if n_block == 0 else f"BLOCKED: {n_block} files"


# ------------------------------------------------------------------------------- checks on the NAS

def kept_candidates(sha, ctx, nas):
    out = []
    for acq, f in ctx.raw.get(sha, ()):
        cp = (ctx.acq_path.get(acq) or "").strip("/").replace("/", "\\")
        if cp:
            out.append(os.path.join(nas, cp, f.replace("/", "\\")))
    for p, n, _o in ctx.placed.get(sha, ()):
        out.append(os.path.join(nas, "projects", NP.project_folder(p, ctx.projects), *NP.SUBDIR, n))
    for n, _o in ctx.holding.get(sha, ()):
        out.append(os.path.join(nas, NP.HOLDING_BASE, n))
    return out


def _stat_one(args):
    sha, size, cands = args
    tried = 0
    for c in cands:
        tried += 1
        try:
            if os.stat(lp(c)).st_size == size:
                return sha, c, tried
        except OSError:
            continue
    return sha, "", tried


def stat_kept(results, ctx, nas, workers, say):
    """One good location (exists, same size) per kept content. -> {sha256: path or ''}."""
    need = {}
    for rel, size, sha, cat, _w, _d in results:
        if cat in ("in-raw", "placed", "holding") and sha not in need:
            need[sha] = (size, kept_candidates(sha, ctx, nas))
        elif cat == "archive-expanded":
            for _n, msize, msha in ctx.archive_members.get(rel, ()):
                if msize and msha not in need:
                    need[msha] = (msize, kept_candidates(msha, ctx, nas))
    say(f"stat: {len(need):,} kept contents, one location each ({workers} threads) ...")
    got, done = {}, 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        for sha, path, _t in ex.map(_stat_one, ((s, z, c) for s, (z, c) in need.items()), chunksize=256):
            got[sha] = path
            done += 1
            if done % 50000 == 0:
                say(f"  ... {done:,}/{len(need):,}")
    return got


def walk_staged(files_root, manifest, workers, say):
    """The staged tree against its manifest: -> (unlisted [(rel, size)], missing [rel], size_differs [rel])."""
    want = {rel: size for rel, size, _s in manifest}
    base = lp(files_root)

    def scan_dir(d):
        found, subdirs = [], []
        with os.scandir(d) as entries:
            for e in entries:
                if e.is_dir(follow_symlinks=False):
                    subdirs.append(e.path)
                else:
                    found.append((e.path[len(base) + 1:], e.stat(follow_symlinks=False).st_size))
        return found, subdirs

    def walk_tree(start):
        out, stack = [], [start]
        while stack:
            f, s = scan_dir(stack.pop())
            out += f
            stack += s
        return out

    found, level1 = scan_dir(base)          # the first two levels in order, then each subtree in parallel
    tasks = []
    for d in level1:
        f, s = scan_dir(d)
        found += f
        tasks += s
    say(f"walk: {files_root} ({len(level1)} top-level folders, {len(tasks)} subtrees) ...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        for part in ex.map(walk_tree, tasks):
            found += part
    seen = dict(found)
    unlisted = sorted((r, s) for r, s in seen.items() if r not in want)
    missing = sorted(r for r in want if r not in seen)
    differs = sorted(r for r in want if r in seen and seen[r] != want[r])
    say(f"walk: {len(seen):,} files in the staged tree; manifest {len(want):,}; unlisted {len(unlisted)}, "
        f"missing {len(missing)}, size differs {len(differs)}")
    return unlisted, missing, differs


# ------------------------------------------------------------------------------- the MRI statement

def mri_statement(results, ctx, archive_check, archive_studies, say):
    """The ParaVision originals (k-space, 2dseq, parameters) not kept, by whether the platform's archive holds
    the exam. -> rows for mri_originals.csv."""
    check = {}
    if archive_check and os.path.exists(lp(archive_check)):
        for r in it(archive_check):
            check[r["original_name"]] = r["archive_result"]
    studies = set()
    if archive_studies and os.path.exists(lp(archive_studies)):
        studies = {r["study"] for r in it(archive_studies)}
    exams = collections.OrderedDict()
    for rel, size, sha, cat, acq, detail in results:
        if cat not in ("mri-kspace", "mri-2dseq", "mri-params"):
            continue
        a = ctx.a1.get(rel)
        key = exam_key_of(a[1]) if a and a[1] else (os.path.basename(a[2]) + "/(study)" if a else "?")
        study = key.split("/")[0]
        e = exams.get(key)
        if e is None:
            if key in check:
                res = check[key]
                group = "M: not in the archive" if res.startswith("not in the archive") else "M: in the archive"
            elif key.endswith("/(study)"):
                group = "study-level: archive holds the study" if study in studies else "study-level: not in the archive"
                res = ""
            else:
                res = "study in the archive listing" if study in studies else "study not in the archive listing"
                group = "earlier: " + ("in the archive" if study in studies else "not in the archive")
            e = exams[key] = {"exam": key, "acq_id": acq, "group": group, "archive_result": res,
                              "a1_class": ctx.exam_class.get(key, ""), "year": study[:4],
                              "short_tarball": "Y" if study in SHORT_TARBALLS else "",
                              "files": 0, "bytes": 0, "kspace_bytes": 0, "2dseq_bytes": 0, "params_bytes": 0,
                              "_sha": {}}
        e["files"] += 1
        e["bytes"] += size
        e[{"mri-kspace": "kspace_bytes", "mri-2dseq": "2dseq_bytes", "mri-params": "params_bytes"}[cat]] += size
        e["_sha"][sha] = (size, cat)
    for e in exams.values():
        e["distinct_bytes"] = sum(s for s, _c in e["_sha"].values())
        e["distinct_kspace_bytes"] = sum(s for s, c in e["_sha"].values() if c == "mri-kspace")
    groups = collections.OrderedDict()
    for e in exams.values():
        g = groups.setdefault(e["group"], collections.Counter())
        g["exams"] += 1
        for k in ("files", "bytes", "kspace_bytes", "2dseq_bytes", "params_bytes", "distinct_bytes",
                  "distinct_kspace_bytes"):
            g[k] += e[k]
    say("\nMRI ORIGINALS NOT KEPT (k-space, 2dseq, parameters), by whether the platform's archive holds the exam")
    say(f"  {'group':42s} {'exams':>6s} {'files':>9s} {'GB all':>9s} {'GB distinct':>11s} {'k-space GB':>10s}")
    for name, g in sorted(groups.items()):
        say(f"  {name:42s} {g['exams']:6,d} {g['files']:9,d} {gb(g['bytes']):>9s} {gb(g['distinct_bytes']):>11s} "
            f"{gb(g['distinct_kspace_bytes']):>10s}")
    nm = [e for e in exams.values() if e["group"] == "M: not in the archive"]
    say(f"  stream M exams not in the archive: {len(nm):,} of {sum(1 for v in check.values() if v.startswith('not in the archive')):,} "
        f"listed by the archive check; their originals: {gb(sum(e['distinct_bytes'] for e in nm))} GB distinct "
        f"(k-space {gb(sum(e['distinct_kspace_bytes'] for e in nm))} GB), {sum(e['files'] for e in nm):,} files")
    for label, sel in (("11.7 T (the archive is the 7 T's)",
                        lambda e: e["group"] == "M: not in the archive" and "11.7" in check.get(e["exam"], "")),
                       ("7 T days the archive lacks",
                        lambda e: e["group"] == "M: not in the archive" and "11.7" not in check.get(e["exam"], ""))):
        xs = [e for e in exams.values() if sel(e)]
        say(f"    {label:38s} {len(xs):5,d} exams {gb(sum(e['distinct_bytes'] for e in xs)):>8s} GB distinct, "
            f"k-space {gb(sum(e['distinct_kspace_bytes'] for e in xs))} GB")
    st = [e for e in exams.values() if e["short_tarball"]]
    if st:
        say(f"  the study whose archive tarball is short ({', '.join(sorted(SHORT_TARBALLS))}): {len(st)} exams, "
            f"{gb(sum(e['distinct_bytes'] for e in st))} GB distinct originals (k-space "
            f"{gb(sum(e['distinct_kspace_bytes'] for e in st))} GB) on the drive")
    ep = [e for e in exams.values() if e["a1_class"].startswith("b-empty-prod")]
    if ep:
        say(f"  exams production holds as an EMPTY placeholder (A1 b-empty-prod): {len(ep)} exams, "
            f"{sum(e['files'] for e in ep):,} files, k-space {gb(sum(e['kspace_bytes'] for e in ep))} GB "
            f"(all copies): the only data of those exams on the drive")
    ny = collections.Counter()
    for e in exams.values():
        if e["group"] == "earlier: not in the archive":
            ny[e["year"]] += e["distinct_bytes"]
    if ny:
        say("  earlier exams (registered before stream M) whose study is not in the archive listing, GB distinct "
            "by year: " + ", ".join(f"{y} {gb(b)}" for y, b in sorted(ny.items())))
    return list(exams.values())


# ------------------------------------------------------------------------------------------- main

def run(args, say):
    ctx = Ctx()
    out = args.out
    os.makedirs(out, exist_ok=True)
    nas = args.nas
    # the manifest: the staged copy's own, checked against the D: copy and the copy run's totals
    say(f"manifest: {args.manifest}")
    man_sha = sha256_file(args.manifest)
    manifest = load_manifest(args.manifest)
    tot = sum(s for _r, s, _h in manifest)
    say(f"  {len(manifest):,} files, {tot:,} bytes ({gb(tot)} GB); SHA-256 of the file {man_sha}")
    problems = []
    if args.drive_manifest:
        if os.path.exists(lp(args.drive_manifest)):
            d = sha256_file(args.drive_manifest)
            say(f"  D: copy {args.drive_manifest}: {'IDENTICAL' if d == man_sha else 'DIFFERENT'}")
            if d != man_sha:
                problems.append("the D: copy of the manifest differs from the staged one")
        else:
            say(f"  D: copy {args.drive_manifest}: absent (not compared)")
    ri = os.path.join(os.path.dirname(args.manifest), "run_info.json")
    if os.path.exists(lp(ri)):
        runs = [json.loads(x) for x in io.open(lp(ri), encoding="utf-8") if x.strip()]
        last = runs[-1]
        same = last.get("files") == len(manifest) and last.get("bytes") == tot
        say(f"  run_info.json (last run {last.get('started')}): {last.get('files'):,} files, {last.get('bytes'):,} bytes: "
            f"{'equal' if same else 'DIFFERENT'}")
        if not same:
            problems.append("the manifest's totals differ from run_info.json")
    ctx.staged_files = os.path.join(os.path.dirname(args.manifest), "files")
    # production, live
    say("reading production (read-only) ...")
    load_registry(ctx, nas)
    newer, gone = load_raw_index(ctx, nas, args.raw_index, out, say)
    if newer or gone:
        say(f"  WARNING: the /raw/ index is older than the live registry: {len(newer)} acquisitions registered after it "
            f"(e.g. {newer[:3]}), {len(gone)} indexed acquisitions no longer live (e.g. {gone[:3]}): rebuild it")
        problems.append("the /raw/ index is not today's registry")
    load_trees(ctx, nas)
    load_a1(ctx, args.a1_files, args.a1_exams)
    load_czi(ctx, args.czi_excluded, args.czi_out_of_scope)
    for f in ctx.facts:
        say("  " + f)
    # classify
    say("classifying ...")
    results = []
    for rel, size, sha in manifest:
        cat, where, detail = classify(rel, size, sha, ctx)
        results.append((rel, size, sha, cat, where, detail))
    # optional NAS checks
    stat_bad = set()
    if args.stat:
        got = stat_kept(results, ctx, nas, args.workers, say)
        bad_sha = {s for s, p in got.items() if not p}
        for rel, size, sha, cat, _w, _d in results:
            if cat in ("in-raw", "placed", "holding") and sha in bad_sha:
                stat_bad.add(rel)
            elif cat == "archive-expanded" and any(m[2] in bad_sha for m in ctx.archive_members.get(rel, ())):
                stat_bad.add(rel)
        say(f"stat: {len(got) - len(bad_sha):,} of {len(got):,} kept contents found on the NAS with the right size; "
            f"{len(bad_sha)} not found -> {len(stat_bad)} manifest rows")
    unlisted = []
    if args.walk:
        unlisted, missing, differs = walk_staged(ctx.staged_files, manifest, args.workers, say)
        wcsv(os.path.join(out, "walk_differences.csv"), ["relpath", "what", "size"],
             [{"relpath": r, "what": "unlisted", "size": s} for r, s in unlisted]
             + [{"relpath": r, "what": "missing", "size": ""} for r in missing]
             + [{"relpath": r, "what": "size differs", "size": ""} for r in differs])
        cats = {r[0]: r[3] for r in results}
        if differs:
            say("  size differs, by category: " + str(dict(collections.Counter(cats[r] for r in differs))))
    # the table
    by = collections.OrderedDict((c, collections.Counter()) for c in ORDER)
    dist = collections.defaultdict(dict)
    for rel, size, sha, cat, _w, _d in results:
        by[cat]["files"] += 1
        by[cat]["bytes"] += size
        dist[cat][sha] = size
    say("\nRECONCILIATION: every file of the staged copy, one category each")
    say(f"  {'fate':9s} {'category':26s} {'files':>9s} {'GB':>9s} {'distinct':>9s} {'GB dist.':>9s}  rule")
    cat_rows = []
    for c in ORDER:
        n = by[c]
        if not n["files"] and c != BLOCKER:
            continue
        say(f"  {fate_of(c):9s} {c:26s} {n['files']:9,d} {gb(n['bytes']):>9s} {len(dist[c]):9,d} "
            f"{gb(sum(dist[c].values())):>9s}  {RULES[c]}")
        cat_rows.append({"fate": fate_of(c), "category": c, "files": n["files"], "bytes": n["bytes"],
                         "gb": gb(n["bytes"]), "distinct": len(dist[c]), "distinct_bytes": sum(dist[c].values()),
                         "rule": RULES[c]})
    for fate in ("kept", "not kept", "BLOCKER"):
        f = sum(by[c]["files"] for c in ORDER if fate_of(c) == fate)
        b = sum(by[c]["bytes"] for c in ORDER if fate_of(c) == fate)
        say(f"  {'= ' + fate:36s} {f:9,d} {gb(b):>9s}")
    say(f"  {'= total':36s} {len(results):9,d} {gb(tot):>9s}")
    jc = collections.Counter(d for _r, _s, _h, c, _w, d in results if c == "junk")
    say("  junk, by rule: " + "; ".join(f"{k} {v:,}" for k, v in jc.most_common()))
    # blockers
    blockers = [r for r in results if r[3] == BLOCKER]
    say(f"\nBLOCKERS: {len(blockers):,} files, {gb(sum(r[1] for r in blockers))} GB")
    bh = collections.OrderedDict()
    for rel, size, sha, _c, _w, d in blockers:
        key = (d, os.path.dirname(rel))
        e = bh.setdefault(key, [0, 0])
        e[0] += 1
        e[1] += size
    byhint = collections.Counter()
    byhint_b = collections.Counter()
    for (d, _f), (n, b) in bh.items():
        byhint[d] += n
        byhint_b[d] += b
    for d, n in byhint.most_common():
        say(f"  {n:6,d} files {gb(byhint_b[d]):>8s} GB  {d}")
    say("  by folder (largest 25):")
    for (d, folder), (n, b) in sorted(bh.items(), key=lambda t: -t[1][1])[:25]:
        say(f"    {n:5,d} {gb(b):>8s} GB  {folder}")
    wcsv(os.path.join(out, "blockers.csv"), ["relpath", "size", "sha256", "folder", "a1_class", "hint"],
         [{"relpath": r, "size": s, "sha256": h, "folder": os.path.dirname(r),
           "a1_class": (ctx.a1.get(r) or ("",))[0], "hint": d} for r, s, h, _c, _w, d in blockers])
    wcsv(os.path.join(out, "blockers_by_folder.csv"), ["hint", "folder", "files", "bytes"],
         [{"hint": d, "folder": f, "files": n, "bytes": b} for (d, f), (n, b) in bh.items()])
    # MRI statement
    exams = mri_statement(results, ctx, args.archive_check, args.archive_studies, say)
    wcsv(os.path.join(out, "mri_originals.csv"),
         ["exam", "acq_id", "group", "archive_result", "a1_class", "year", "short_tarball", "files", "bytes",
          "kspace_bytes", "2dseq_bytes", "params_bytes", "distinct_bytes", "distinct_kspace_bytes"], exams)
    # outputs
    wcsv(os.path.join(out, "categories.csv"),
         ["fate", "category", "files", "bytes", "gb", "distinct", "distinct_bytes", "rule"], cat_rows)
    wcsv(os.path.join(out, "closeout_files.csv.gz"), ["relpath", "size", "sha256", "fate", "category", "where", "detail"],
         ({"relpath": r, "size": s, "sha256": h, "fate": fate_of(c), "category": c, "where": w, "detail": d}
          for r, s, h, c, w, d in results))
    if stat_bad:
        wcsv(os.path.join(out, "stat_failures.csv"), ["relpath", "category", "where"],
             [{"relpath": r, "category": c, "where": w} for r, _s, _h, c, w, _d in results if r in stat_bad])
    # verdict
    block = {r[0] for r in blockers} | stat_bad | {r for r, _s in unlisted}
    say("")
    for p in problems:
        say(f"PROBLEM: {p}")
    say(f"blocking: {len(blockers):,} files in no category; {len(stat_bad):,} kept files with no good copy on the NAS"
        f"{' (not checked: --stat)' if not args.stat else ''}; {len(unlisted):,} files in the staged tree its "
        f"manifest does not list{' (not checked: --walk)' if not args.walk else ''}"
        + (f"; {len(problems)} input problem(s)" if problems else ""))
    if problems and not block:
        line = f"BLOCKED: 0 files, {len(problems)} input problem(s)"
    else:
        line = verdict_line(len(block))
    say(line)
    return 0 if line == "READY TO DELETE" else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", required=True, help="output folder (off the NAS)")
    ap.add_argument("--nas", default=NP.NAS_DEFAULT)
    ap.add_argument("--manifest", default=P.MANIFEST_NAS, help="the staged copy's own manifest.csv")
    ap.add_argument("--drive-manifest", default=P.MANIFEST_COPY, help="the D: copy, compared byte for byte ('' to skip)")
    ap.add_argument("--raw-index", default="", help="a /raw/ index saved TODAY (p_verify.py raw-dedup --write-index); "
                                                    "default: built live")
    ap.add_argument("--a1-files", default=A1_FILES)
    ap.add_argument("--a1-exams", default=A1_EXAMS)
    ap.add_argument("--czi-excluded", nargs="+", default=[CZI_EXCLUDED],
                    help="stream C's excluded.csv, and any later .czi batch's built with its tools (e.g. the foreign raw's)")
    ap.add_argument("--czi-out-of-scope", default=CZI_OUT_OF_SCOPE)
    ap.add_argument("--archive-check", default=ARCHIVE_CHECK, help="tasks/drive3_mri_archive_check.csv")
    ap.add_argument("--archive-studies", default=ARCHIVE_STUDIES, help="the archive census's study list")
    ap.add_argument("--stat", action="store_true", help="stat one kept location per content on the NAS")
    ap.add_argument("--walk", action="store_true", help="walk the staged tree against its manifest")
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args(argv)
    B.stdout_utf8()
    lines = []

    def say(m=""):
        print(m, flush=True)
        lines.append(m)

    try:
        return run(args, say)
    finally:
        os.makedirs(args.out, exist_ok=True)
        with io.open(os.path.join(args.out, "closeout_summary.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(main())
